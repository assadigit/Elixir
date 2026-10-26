"""V0.6.69 — the local-LLM liveness monitor (the probe layer, Qt-free).

THE FIELD REPORT (2026-10-26, V0.6.68 follow-up): the user asked for the
startup "Ollama not running" ERROR DIALOG to go away, replaced by live
status LIGHTS that actively watch for locally-running LLM clients::

    "do not show the error of ollama when app loads. instead show a green
     light that shows whether ollama or any other locally famous LLM client
     is on or not, it must actively look for ollama or llama.cpp server as
     they're online and show a green light for them on ui instead"

This module is the probe half of that story (the UI half lives in
``ui_qt/components/llm_lights.py``; the poll loop lives in
``ui_qt/app.py``). It is deliberately Qt-free and raises NOTHING — it is
imported by tests headlessly and executed on a worker thread every few
seconds for the whole app lifetime.

The three locally-famous clients Elixir already speaks to:

* **Ollama** — ``GET {ollama_url}/api/tags`` (``utils.network`` — the
  proxy-proof transport, audit B5's rule that a misconfigured HTTP_PROXY
  must never fake "Ollama down").
* **llama.cpp server** (``llama-server``) — ``GET {base}/v1/models`` with
  the configured bearer key. The V0.6.55 port auto-detection order is
  mirrored here (8080 first, then llama.cpp's CURRENT default 8000, then
  the ANNOUNCED future default 9931) — but ONLY when the operator still
  runs the app's unmodified default URL; an explicitly configured URL is
  a deliberate choice and is probed alone (the V0.6.12 contract,
  ``resolve_llamacpp_base_url`` precedent).
* **LM Studio** — ``GET {lmstudio_url}/v1/models`` (OpenAI shape; the
  wizard's third local backend).

DESIGN RULES (each pinned by tests/test_v0669_local_llm_lights.py):

1. **Fresh, never cached** — this layer calls the transport helpers
   DIRECTLY and deliberately does NOT go through
   ``local_fallback._probe_llamacpp`` (whose 30 s TTL exists to bound
   ROUTING cost, not to keep a status light honest). A server started
   mid-session must go green on the NEXT tick, not 30 s later.
2. **Snapshot in, snapshot out** — ``snapshot_endpoints()`` reads the
   settings/secrets ON THE MAIN THREAD; the worker thread only receives
   the frozen :class:`LocalLLMEndpoints` (no cross-thread settings
   access at all).
3. **Never raises** — every probe is wrapped; "dead" is a valid answer
   the lights render gray, not an error (a status light that can crash
   the app is worse than no light).
4. **Cheap** — every timeout is ``SUBSECOND_PROBE_TIMEOUT_S`` (2 s); all
   endpoints are loopback, where "dead" is an instant connection-refused.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.llm.llamacpp_provider import list_llamacpp_models
from core.llm.local_fallback import LLAMACPP_ALT_BASE_URLS, LLAMACPP_DEFAULT_BASE_URL
from core.system.timeouts import SUBSECOND_PROBE_TIMEOUT_S
from utils.network import is_ollama_reachable, list_ollama_models

logger = logging.getLogger(__name__)

# How often the UI polls (owned by the window's QTimer; defined here so
# tests + the UI share one number — "actively look for ollama or llama.cpp
# server as they're online" needs a short, constant cadence; loopback
# GETs of /api/tags + /v1/models are ~free even while a conversion runs).
LLM_LIGHTS_POLL_INTERVAL_S = 5

# llama.cpp port auto-detection — the EXACT V0.6.55 order (imported from
# local_fallback, the single source; the default 8080 is always probed
# FIRST and is deliberately NOT in the alternates tuple).

# The three clients, in display order (the lights render this order).
OLLAMA_KEY = "ollama"
LLAMACPP_KEY = "llamacpp"
LMSTUDIO_KEY = "lmstudio"

_CLIENT_NAMES = {
    OLLAMA_KEY: "Ollama",
    LLAMACPP_KEY: "llama.cpp",
    LMSTUDIO_KEY: "LM Studio",
}


@dataclass(frozen=True)
class LocalLLMEndpoints:
    """A main-thread snapshot of every local-LLM endpoint the monitor
    probes (see DESIGN RULE 2 — the worker never touches settings)."""

    ollama_url: str = "http://localhost:11434"
    llamacpp_base_url: str = LLAMACPP_DEFAULT_BASE_URL
    llamacpp_api_key: str = "local"
    lmstudio_url: str = "http://localhost:1234/v1"


@dataclass(frozen=True)
class LocalLLMStatus:
    """The liveness verdict for ONE client — everything the light and its
    tooltip render. ``detail`` is one short human line; ``probed`` lists
    the endpoints that were tried (the llama.cpp port order evidence)."""

    key: str
    name: str
    online: bool
    detail: str
    endpoint: str
    probed: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tooltip(self) -> str:
        """The multi-line hover text for the light."""
        head = f"{self.name} — {'running' if self.online else 'not running'}"
        lines = [head, self.detail]
        if self.probed and not self.online:
            lines.append("probed: " + ", ".join(self.probed))
        return "\n".join(lines)


def snapshot_endpoints(settings) -> LocalLLMEndpoints:
    """Read the configured endpoints + key ONCE (call on the main thread).

    Never raises — a settings layer hiccup falls back to every default
    (the lights then probe the well-known ports, which is exactly what a
    default-configured rig runs).
    """
    try:
        ollama_url = str(
            settings.get("summarisation.ollama_url", "http://localhost:11434")
            or "http://localhost:11434"
        ).strip()
    except Exception:
        ollama_url = "http://localhost:11434"
    try:
        llamacpp_base_url = str(
            settings.get("summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_BASE_URL)
            or LLAMACPP_DEFAULT_BASE_URL
        ).strip()
    except Exception:
        llamacpp_base_url = LLAMACPP_DEFAULT_BASE_URL
    try:
        lmstudio_url = str(
            settings.get("summarisation.lmstudio_url", "http://localhost:1234/v1")
            or "http://localhost:1234/v1"
        ).strip()
    except Exception:
        lmstudio_url = "http://localhost:1234/v1"
    # The bearer key llama-server enforces only when started with --api-key
    # (the V0.04 provider contract); mirror resolve_llamacpp_base_url's
    # "local" fallback so the light probes EXACTLY what a real call would.
    api_key = "local"
    try:
        from core.system.secrets import get_secret

        api_key = str(get_secret("summarisation.llamacpp_api_key", settings, "local") or "local")
    except Exception:
        logger.debug("llamacpp api-key secret unavailable — probing with 'local'", exc_info=True)
    return LocalLLMEndpoints(
        ollama_url=ollama_url or "http://localhost:11434",
        llamacpp_base_url=llamacpp_base_url or LLAMACPP_DEFAULT_BASE_URL,
        llamacpp_api_key=api_key,
        lmstudio_url=lmstudio_url or "http://localhost:1234/v1",
    )


def _probe_ollama(spec: LocalLLMEndpoints) -> LocalLLMStatus:
    url = spec.ollama_url
    try:
        if is_ollama_reachable(url, timeout=SUBSECOND_PROBE_TIMEOUT_S):
            models = list_ollama_models(url, timeout=SUBSECOND_PROBE_TIMEOUT_S)
            n = len(models)
            return LocalLLMStatus(
                key=OLLAMA_KEY,
                name=_CLIENT_NAMES[OLLAMA_KEY],
                online=True,
                detail=(
                    f"running · {n} model{'s' if n != 1 else ''} @ {url}"
                    if n
                    else f"running (no models pulled yet) @ {url}"
                ),
                endpoint=url,
                probed=(url,),
            )
    except Exception:
        logger.debug("ollama liveness probe exploded", exc_info=True)
    return LocalLLMStatus(
        key=OLLAMA_KEY,
        name=_CLIENT_NAMES[OLLAMA_KEY],
        online=False,
        detail=f"not running @ {url} (start it, or run: ollama serve)",
        endpoint=url,
        probed=(url,),
    )


def _llamacpp_probe_order(spec: LocalLLMEndpoints) -> list[str]:
    """The probe order for llama.cpp — the V0.6.55 contract, mirrored:

    * an EXPLICIT operator URL → that URL alone (a deliberate choice);
    * the unmodified app default (8080) → default first, then the
      well-known alternates 8000 / 9931 (llama.cpp's shifting defaults).
    """
    base = spec.llamacpp_base_url
    if base != LLAMACPP_DEFAULT_BASE_URL:
        return [base]
    return [LLAMACPP_DEFAULT_BASE_URL, *LLAMACPP_ALT_BASE_URLS]


def _probe_llamacpp_client(spec: LocalLLMEndpoints) -> LocalLLMStatus:
    probed: list[str] = []
    try:
        for base in _llamacpp_probe_order(spec):
            probed.append(base)
            models = list_llamacpp_models(
                base, spec.llamacpp_api_key, timeout=SUBSECOND_PROBE_TIMEOUT_S
            )
            if models:
                auto = ""
                if base != LLAMACPP_DEFAULT_BASE_URL and base in LLAMACPP_ALT_BASE_URLS:
                    auto = " (port auto-detected)"
                return LocalLLMStatus(
                    key=LLAMACPP_KEY,
                    name=_CLIENT_NAMES[LLAMACPP_KEY],
                    online=True,
                    detail=f"running{auto} · serving {models[0]} @ {base}",
                    endpoint=base,
                    probed=tuple(probed),
                )
    except Exception:
        logger.debug("llama.cpp liveness probe exploded", exc_info=True)
    return LocalLLMStatus(
        key=LLAMACPP_KEY,
        name=_CLIENT_NAMES[LLAMACPP_KEY],
        online=False,
        detail="not running (llama-server / llama.cpp server is offline)",
        endpoint=spec.llamacpp_base_url,
        probed=tuple(probed) or (spec.llamacpp_base_url,),
    )


def _probe_lmstudio(spec: LocalLLMEndpoints) -> LocalLLMStatus:
    url = spec.lmstudio_url
    try:
        # LM Studio serves the same OpenAI /v1/models shape llama-server
        # does (the wizard's third local backend) — the llamacpp listing
        # call IS the probe, just pointed at LM Studio's port.
        models = list_llamacpp_models(url, "", timeout=SUBSECOND_PROBE_TIMEOUT_S)
        if models:
            return LocalLLMStatus(
                key=LMSTUDIO_KEY,
                name=_CLIENT_NAMES[LMSTUDIO_KEY],
                online=True,
                detail=f"running · serving {models[0]} @ {url}",
                endpoint=url,
                probed=(url,),
            )
    except Exception:
        logger.debug("lm studio liveness probe exploded", exc_info=True)
    return LocalLLMStatus(
        key=LMSTUDIO_KEY,
        name=_CLIENT_NAMES[LMSTUDIO_KEY],
        online=False,
        detail=f"not running @ {url}",
        endpoint=url,
        probed=(url,),
    )


def probe_local_llm_clients(spec: LocalLLMEndpoints) -> list[LocalLLMStatus]:
    """Probe every client once — THE entry point the poll loop runs.

    Returns one :class:`LocalLLMStatus` per client, in display order
    (Ollama, llama.cpp, LM Studio). Never raises (DESIGN RULE 3); a probe
    that explodes anywhere inside is rendered "not running" by the
    per-client guards.
    """
    return [
        _probe_ollama(spec),
        _probe_llamacpp_client(spec),
        _probe_lmstudio(spec),
    ]
