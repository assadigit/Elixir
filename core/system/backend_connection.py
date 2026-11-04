"""V0.6.85 (Round-5 §5) — the backend connection-state model (Qt-free).

THE ROUND-5 SPEC: the bottom-left status word used to read ``Ready``
merely because the GUI had launched — misleading whenever the configured
LLM backend was actually down. This module is the honest replacement: a
small, explicit connection-state model derived from the app's REAL
provider architecture (inspected, not invented):

* ``summarisation.provider`` is the authoritative provider key the whole
  pipeline already routes on (``ollama`` / ``llamacpp`` /
  ``openai_compatible`` / ``claude`` — the ``create_provider`` factory's
  supported set; anything else falls back to the ollama branch exactly
  like the factory does).
* Local providers reuse the EXISTING V0.6.69 liveness poll
  (``core.system.local_llm_monitor`` — loopback GETs, 2 s budget, worker
  thread, 5 s cadence): no new polling loop, no new endpoints.
* API providers get ONE bounded async check at startup and after the
  Settings dialog closes (a configuration change) — the app's OWN
  pre-flight verifier ``test_cloud_connection`` for OpenAI-compatible
  endpoints and a Claude-shaped probe mirroring ``ClaudeProvider``'s
  exact request for Anthropic. NEVER a repeating poll against a paid
  endpoint (spec §5.2: "Avoid aggressive polling").

STATES (spec §5.1 — only what the implementation can actually verify):

  CHECKING           a connection check is in progress
  CONNECTED          the selected provider passed a real check
  BACKEND_OFFLINE    the selected local backend cannot be reached
  API_UNAVAILABLE    the selected API provider cannot be reached / answered
  NOT_CONFIGURED     no usable provider configuration (e.g. no API key)
  MODEL_UNAVAILABLE  provider reachable but the selected model is not
                     usable — only when the backend exposes enough
                     information to verify this (Ollama's /api/tags is
                     authoritative; llama.cpp's /v1/models may be absent
                     on older builds, so an EMPTY list is not evidence)

SEVERITY (spec §5.3): ok → muted green, warn → amber, bad → muted red,
neutral → gray. The LABEL always carries the state (never color alone).

DESIGN RULES (mirroring local_llm_monitor):
1. Qt-free + never raises — imported by tests headlessly and run on a
   worker thread for the app's whole lifetime.
2. Snapshot in, snapshot out — ``snapshot_backend_config()`` reads
   settings/secrets on the MAIN thread; workers only receive frozen
   dataclasses.
3. No secrets in states — the detail strings never include API keys
   (spec §8: "Do not expose API keys or secrets in status labels").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = [
    "CHECKING",
    "CONNECTED",
    "BACKEND_OFFLINE",
    "API_UNAVAILABLE",
    "NOT_CONFIGURED",
    "MODEL_UNAVAILABLE",
    "STATE_LABELS",
    "STATE_SEVERITY",
    "BackendConfig",
    "snapshot_backend_config",
    "derive_local_backend_state",
    "test_api_provider_connection",
    "test_local_backend_connection",
    "provider_mode",
]

# ── the states (spec §5.1) ──────────────────────────────────────────────────

CHECKING = "checking"
CONNECTED = "connected"
BACKEND_OFFLINE = "backend_offline"
API_UNAVAILABLE = "api_unavailable"
NOT_CONFIGURED = "not_configured"
MODEL_UNAVAILABLE = "model_unavailable"

#: The bottom-strip word for each state (plain, truthful, color-independent).
STATE_LABELS: dict[str, str] = {
    CHECKING: "Checking backend…",
    CONNECTED: "Connected",
    BACKEND_OFFLINE: "Backend offline",
    API_UNAVAILABLE: "API unavailable",
    NOT_CONFIGURED: "Not configured",
    MODEL_UNAVAILABLE: "Model unavailable",
}

#: The dot tint class per state (spec §5.3):
#:   ok=verified green · warn=amber · bad=muted red · neutral=gray.
STATE_SEVERITY: dict[str, str] = {
    CHECKING: "warn",
    CONNECTED: "ok",
    BACKEND_OFFLINE: "bad",
    API_UNAVAILABLE: "bad",
    NOT_CONFIGURED: "neutral",
    MODEL_UNAVAILABLE: "warn",
}

#: The provider keys the pipeline's ``create_provider`` factory supports
#: (core/llm/llm_provider_impl.py — inspected, not invented). Anything
#: else falls back to the ollama branch, exactly like the factory.
_API_PROVIDERS = frozenset({"openai_compatible", "claude"})
_LOCAL_PROVIDERS = frozenset({"ollama", "llamacpp"})


@dataclass(frozen=True)
class BackendConfig:
    """A main-thread snapshot of everything the state model needs (see
    DESIGN RULE 2 — workers never touch settings).

    ``client_key`` is the local_llm_monitor client the LOCAL provider's
    verdict is read from; ``is_api`` selects the API check path instead.
    """

    provider: str
    model: str
    display_name: str
    is_api: bool
    client_key: str
    api_base_url: str = ""
    api_key: str = ""
    api_model: str = ""


def snapshot_backend_config(settings) -> BackendConfig:
    """Read the provider configuration ONCE (call on the main thread).

    Never raises — a settings hiccup falls back to the factory's own
    defaults (provider ``ollama``), which is exactly what the pipeline
    would run with.
    """
    try:
        provider = str(settings.get("summarisation.provider", "ollama") or "ollama").strip().lower()
    except Exception:
        provider = "ollama"
    if provider not in _LOCAL_PROVIDERS and provider not in _API_PROVIDERS:
        provider = "ollama"  # the create_provider fallback branch

    try:
        model = str(settings.get("summarisation.model", "") or "").strip()
    except Exception:
        model = ""

    display_name = {
        "ollama": "Ollama",
        "llamacpp": "llama.cpp",
        "openai_compatible": "OpenAI-compatible API",
        "claude": "Claude API",
    }.get(provider, provider)

    if provider in _API_PROVIDERS:
        base_key = (
            "summarisation.claude_base_url"
            if provider == "claude"
            else "summarisation.api_base_url"
        )
        model_key = (
            "summarisation.claude_model" if provider == "claude" else "summarisation.cloud_model"
        )
        default_base = (
            "https://api.anthropic.com/v1"
            if provider == "claude"
            else "https://openrouter.ai/api/v1"
        )
        try:
            base = str(settings.get(base_key, default_base) or default_base).strip()
        except Exception:
            base = default_base
        try:
            api_model = str(settings.get(model_key, "") or "").strip()
        except Exception:
            api_model = ""
        api_key = ""
        try:
            from core.system.secrets import get_secret

            secret_key = (
                "summarisation.claude_api_key" if provider == "claude" else "summarisation.api_key"
            )
            api_key = str(get_secret(secret_key, settings, "") or "")
        except Exception:
            logger.debug("api key secret unavailable for the status snapshot", exc_info=True)
        return BackendConfig(
            provider=provider,
            model=model,
            display_name=display_name,
            is_api=True,
            client_key="",
            api_base_url=base,
            api_key=api_key,
            api_model=api_model,
        )

    # Local: which monitor client answers for this provider. The LM Studio
    # backend is configured as ai.backend="LM Studio" (provider stays
    # "ollama" — the settings section's own mapping); its verdict is the
    # lmstudio client's probe, not the ollama one.
    client_key = "ollama"
    try:
        backend = str(settings.get("ai.backend", "Ollama") or "Ollama").strip()
    except Exception:
        backend = "Ollama"
    if provider == "llamacpp":
        client_key = "llamacpp"
    elif backend == "LM Studio":
        client_key = "lmstudio"
    return BackendConfig(
        provider=provider,
        model=model,
        display_name=display_name,
        is_api=False,
        client_key=client_key,
    )


# ── the local verdict (fed by the EXISTING V0.6.69 poll) ────────────────────


def derive_local_backend_state(
    statuses: list | None,
    client_key: str,
    model: str,
) -> tuple[str, str]:
    """Map the latest local-LLM probe verdicts onto the state model.

    ``statuses`` is ``probe_local_llm_clients()``'s output (one
    ``LocalLLMStatus`` per client). Returns ``(state, detail)`` where
    ``detail`` is the one-line tooltip (never a secret — the probe layer
    only ever saw endpoint URLs).
    """
    status = None
    for st in statuses or []:
        if getattr(st, "key", None) == client_key:
            status = st
            break
    if status is None:
        # No verdict yet (the first probe is still in flight) — CHECKING
        # is the honest word, never a guessed Connected.
        return CHECKING, "Waiting for the first backend probe…"
    if not getattr(status, "online", False):
        return BACKEND_OFFLINE, getattr(status, "detail", "not running")
    # Online — can the selected MODEL be verified? Ollama's /api/tags
    # listing is authoritative (an empty list means nothing is pulled);
    # llama.cpp / LM Studio listings may be absent on older builds, so an
    # empty list there is NOT evidence (spec §5.1's "if the backend
    # exposes enough information").
    models = tuple(getattr(status, "models", ()) or ())
    if client_key == "ollama":
        if not models:
            return (
                MODEL_UNAVAILABLE,
                "Backend running but no models are available (ollama pull a model)",
            )
        if model and model not in models:
            return (
                MODEL_UNAVAILABLE,
                f"Backend running · model “{model}” is not in the {len(models)} available model(s)",
            )
    elif models and model and model not in models:
        return MODEL_UNAVAILABLE, f"Backend running · model “{model}” is not listed by the server"
    return CONNECTED, getattr(status, "detail", "running")


# ── the Settings "Test connection" helpers (Round-5 §4.2) ───────────────────


def test_local_backend_connection(
    backend: str,
    model: str,
    custom_url: str = "",
    llamacpp_base_url: str = "",
    llamacpp_api_key: str = "",
    timeout: int = 10,
) -> tuple[bool, str]:
    """One-shot verification of a LOCAL backend selection (the Settings
    AI → Local Model section's Test button — the same transports the
    V0.6.69 monitor uses, run once on demand).

    ``backend`` is the section's own picker vocabulary ("Ollama" /
    "llama.cpp server" / "LM Studio" / "Custom"); the llama.cpp endpoints
    default to the app's settings when the caller passes nothing (read
    them on the MAIN thread — DESIGN RULE 2).

    Returns ``(ok, message)``; never raises.
    """
    from core.system.timeouts import SUBSECOND_PROBE_TIMEOUT_S

    t = min(timeout, max(2, SUBSECOND_PROBE_TIMEOUT_S * 5))
    try:
        if backend == "llama.cpp server":
            from core.llm.llamacpp_provider import test_llamacpp_connection

            base = (llamacpp_base_url or "").strip() or "http://127.0.0.1:8080/v1"
            key = (llamacpp_api_key or "").strip() or "local"
            return test_llamacpp_connection(base, key, model)
        if backend == "LM Studio":
            from core.llm.llamacpp_provider import list_llamacpp_models

            url = "http://localhost:1234/v1"
            models = list_llamacpp_models(url, "", timeout=t)
            if models:
                return True, f"running · serving {models[0]} @ {url}"
            return False, f"not running @ {url} (start LM Studio's local server)"
        # Ollama + Custom (the custom URL expects the Ollama /api/tags shape)
        from utils.network import is_ollama_reachable, list_ollama_models

        url = (
            (custom_url or "").strip().rstrip("/")
            if backend == "Custom"
            else "http://localhost:11434"
        )
        if not url:
            return False, "No backend URL set."
        if not is_ollama_reachable(url, timeout=t):
            return False, f"not running @ {url} (start it, or run: ollama serve)"
        models = list_ollama_models(url, timeout=t)
        if not models:
            return False, f"running but no models are available @ {url} (ollama pull a model)"
        if model and model not in models:
            return (
                False,
                f"running · model “{model}” is not in the {len(models)} available model(s)",
            )
        return True, f"running · {len(models)} model{'s' if len(models) != 1 else ''} @ {url}"
    except Exception as e:
        logger.debug("local backend test exploded", exc_info=True)
        return False, f"probe error: {e}"


def provider_mode(settings) -> str:
    """The AI page's mode summary — "local" or "api" (the provider key's
    family; mirrors the factory's fallback)."""
    try:
        provider = str(settings.get("summarisation.provider", "ollama") or "ollama").strip().lower()
    except Exception:
        provider = "ollama"
    return "api" if provider in _API_PROVIDERS else "local"


# ── the API check (one bounded request, worker thread) ──────────────────────


def test_api_provider_connection(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = 10,
) -> tuple[bool, str]:
    """Verify the configured API provider with ONE tiny real request.

    Uses the app's OWN pre-flight mechanism per provider family:

    * ``openai_compatible`` → ``core.llm.cloud_client.test_cloud_connection``
      (a minimal ``/chat/completions`` call — the same verifier the
      wizard's Test button runs; it distinguishes 401/404/400/model
      errors in its message).
    * ``claude`` → the identical tiny probe in Anthropic's shape, using
      ``ClaudeProvider``'s exact headers (``x-api-key`` +
      ``anthropic-version``) against ``{base}/messages``.

    Returns ``(ok, message)``; never raises. The caller classifies a
    missing base URL / key / model as NOT_CONFIGURED BEFORE calling (a
    configuration gap is not a connectivity result); the message is safe
    for a tooltip (no key material is ever echoed).
    """
    if provider == "claude":
        return _test_claude_connection(base_url, api_key, (model or "").strip(), timeout)
    from core.llm.cloud_client import test_cloud_connection

    return test_cloud_connection(base_url, api_key, (model or "").strip(), timeout=timeout)


def _test_claude_connection(
    base_url: str,
    api_key: str,
    model: str,
    timeout: int,
) -> tuple[bool, str]:
    """The Claude-shaped twin of ``test_cloud_connection`` — a minimal
    ``/messages`` call with ``ClaudeProvider``'s exact header contract,
    classified into the same message families (auth / not-found / model
    errors / connection failures)."""
    import requests

    url = f"{base_url.rstrip('/')}/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "Reply with the single word: OK"}],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection failed: {e}"
    except requests.exceptions.Timeout:
        return False, f"Timed out after {timeout}s — endpoint may be unreachable."
    except Exception as e:
        return False, f"Request error: {e}"
    if resp.status_code in (401, 403):
        return False, "Unauthorized — check your API key."
    if resp.status_code == 404:
        return False, "Not found (404) — check the base URL."
    if resp.status_code == 429:
        return False, "Rate limited (429) — the endpoint is reachable; try again shortly."
    if resp.status_code == 400:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            detail = resp.text[:200]
        return False, f"Bad request (400): {detail}"
    if not resp.ok:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    try:
        data = resp.json()
        blocks = data.get("content", []) or []
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict)).strip()
    except Exception:
        return False, "Unexpected response shape (no content blocks)"
    if not text:
        return False, "Empty response from the model"
    preview = text[:60] + ("…" if len(text) > 60 else "")
    return True, f"Connected ✓ — model replied: {preview!r}"
