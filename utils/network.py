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
