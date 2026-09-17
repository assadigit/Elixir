"""Network utilities for Ollama — completely proxy-proof."""

import logging
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def create_no_proxy_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.proxies = {"http": "", "https": ""}
    adapter = HTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# V18.20.2.0 (SWOT A21): module-level shared no-proxy session (connection
# pooling). The old safe_ollama_request created AND closed a new
# requests.Session on every call — zero connection reuse for every LLM,
# embed, and /api/tags request (TCP + port churn, ~50ms+ per call on
# localhost). The shared session is thread-safe for concurrent simple
# requests (requests.Session documentation) — the summarizer's worker
# threads share the pool. trust_env=False + empty proxies make it
# proxy-immune WITHOUT the old thread-unsafe os.environ pop/restore.
_SHARED_SESSION: requests.Session | None = None
_SHARED_SESSION_LOCK = threading.Lock()


def get_shared_session() -> requests.Session:
    """Return the process-lifetime shared no-proxy session (lazily built).

    V18.20.2.0 (SWOT A21): exposed as a function (not a bare module global)
    so tests can reset pooling behavior and callers (e.g. streaming requests
    that must NOT close the shared session) share one pool.
    """
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        with _SHARED_SESSION_LOCK:
            if _SHARED_SESSION is None:
                _SHARED_SESSION = create_no_proxy_session()
    return _SHARED_SESSION


# V18.20.4.11 (P3 / O-c5): shared CLOUD session — the transport-unification
# counterpart of the no-proxy local session. Unlike the local session
# (trust_env=False + empty proxies, because a misconfigured HTTP_PROXY must
# never break localhost Ollama), cloud endpoints (OpenRouter / OpenAI /
# Anthropic / any /v1 API) legitimately go through corporate proxies, so
# this one TRUSTS the environment. Pooled + process-lifetime, thread-safe
# for concurrent simple requests. Before this, every cloud call site built
# its own bare ``requests.post`` (new TCP session per call, zero reuse).
_CLOUD_SESSION: requests.Session | None = None
_CLOUD_SESSION_LOCK = threading.Lock()


def get_shared_cloud_session() -> requests.Session:
    """Return the process-lifetime shared cloud (proxy-trusting) session."""
    global _CLOUD_SESSION
    if _CLOUD_SESSION is None:
        with _CLOUD_SESSION_LOCK:
            if _CLOUD_SESSION is None:
                _CLOUD_SESSION = requests.Session()  # trust_env=True (default)
    return _CLOUD_SESSION


def session_for_url(url: str) -> requests.Session:
    """V18.20.4.11 (P3 / O-c5): pick the shared session by endpoint locality.

    Localhost URLs (localhost / 127.0.0.1 / [::1] / 0.0.0.0, any port) → the
    no-proxy pooled session (proxy-immune, as ``safe_ollama_request`` has
    always been). Everything else → the pooled cloud session (proxy-trusting).

    This is the ONE routing rule every LLM HTTP call site uses so transport
    behavior is uniform tree-wide: pooling + correct proxy handling, while
    each site keeps its OWN timeout / retry / status-handling semantics.
    """
    try:
        host = (url or "").split("://", 1)[-1].split("/", 1)[0]
        if host.startswith("["):
            # IPv6 literal: [::1]:11434 → ::1
            host = host[1:].split("]", 1)[0]
        else:
            host = host.split(":", 1)[0]
        host = host.strip().lower()
    except Exception:
        host = ""
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return get_shared_session()
    return get_shared_cloud_session()


def extract_openai_content(data) -> str:
    """V18.20.4.11 (P3 / O-c5): safe deep-index for OpenAI-compat responses.

    The old one-liner ``data["choices"][0]["message"]["content"].strip()``
    (duplicated across 6+ call sites) raised KeyError/IndexError/TypeError
    on every provider that returned an error payload, a truncated body, or
    an unexpected schema — leaving sites that had no outer guard crashed
    and sites that DID have one with a masked real error. Returns "" on any
    shape mismatch; the caller decides what "" means (retry / fallback /
    fail-soft), same as an empty-but-valid response.
    """
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    return content.strip()


def safe_ollama_request(
    method: str,
    url: str,
    timeout: int = 300,
    retries: int = 0,
    backoff_factor: float = 1.0,
    **kwargs,
) -> requests.Response:
    # V18.20.2.0 (SWOT A21): the old implementation (1) popped/restored the
    # HTTP_PROXY/HTTPS_PROXY env vars around each call — thread-unsafe under
    # the summarizer's ThreadPoolExecutor and redundant given trust_env=False,
    # and (2) created + closed a NEW Session per call — zero connection
    # pooling. Now the common path (retries=0) reuses the shared session.
    # The rare retries>0 path keeps a per-call session because mounting a
    # Retry-configured adapter would mutate the shared session for everyone.
    if retries > 0:
        session = create_no_proxy_session()
        try:
            retry_strategy = Retry(
                total=retries,
                backoff_factor=backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            response = session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        finally:
            session.close()

    session = get_shared_session()
    response = session.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response


def is_ollama_reachable(base_url: str = "http://localhost:11434", timeout: int = 5) -> bool:
    try:
        resp = safe_ollama_request("GET", f"{base_url}/api/tags", timeout=timeout, retries=0)
        return resp.status_code == 200
    except (ConnectionError, TimeoutError, OSError):
        return False


def list_ollama_models(base_url: str = "http://localhost:11434") -> list:
    try:
        resp = safe_ollama_request("GET", f"{base_url}/api/tags", timeout=10)
        data = resp.json()
        return [model["name"] for model in data.get("models", [])]
    except (ConnectionError, TimeoutError, OSError):
        return []
