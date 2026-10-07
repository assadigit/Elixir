"""V0.6.12: the llama.cpp-first local-LLM fallback policy.

THE USER POLICY (the Packets of Knowledge session report, verbatim
intent): Ollama is the always-on default (auto-start); llama.cpp
(``llama-server``) is started deliberately, only when needed — so
"llama.cpp is up" MEANS "route to it and the model it serves".
Every raw-request LOCAL call site (Packets of Knowledge, the
new-output riders) therefore asks this module BEFORE dispatching.

V0.6.55 (P1a — the transcribe-tool redesign): llama.cpp's default PORT
keeps shifting. The app default is 8080; the operator's rig runs
``llama-server`` on **8000** (llama.cpp's current default — its console
prints "server default port will be changed to :9931 in a future
release"), and 9931 is the announced future default. A hard-coded
8080 probe therefore concludes "llama.cpp not reachable" on a rig
where llama.cpp IS the deliberately-started backend — the V0.6.54
CHANGELOG's flagged configuration trap. The fix: when the configured
base URL is the UNMODIFIED app default, the well-known alternates
(8000, then 9931) are probed too — first LIVE port wins, both here
(``decide_llamacpp_first`` / ``resolve_llamacpp_base_url``) and in
``create_provider``'s llamacpp branch (via the same helper). An
EXPLICIT operator-configured URL is never second-guessed (the V0.6.12
deliberate-choice contract is unchanged).

V0.6.13 extends the wired sites (the operator's follow-up report:
"tts, TRANSCRIBE SERVICE AND PODCAST HAVE SAME PROBLEM, THEY FIND
LLM ON OLLAMA ONLY"): the transcribe summary
(``summarize_transcript``), the Podcast Maker script generator
(``generate_podcast_script`` + ``_generate_podcast_title``), and the
TTS text normalizer (``create_normalizer_from_settings`` — also the
podcast-audio normalize step). The sites WITHOUT a provider concept
(podcast ``ollama_url``, TTS ``tts.normalize_endpoint``) consult the
policy only when their configured URL is LOCAL (``is_local_url``) — a
deliberately-configured remote endpoint passes through untouched, the
same treatment cloud providers get.

  1. A live llama.cpp server at ``summarisation.llamacpp_base_url``?
     → the call routes THERE (OpenAI-compatible, the served model
     detected via GET /v1/models — the V0.4.30 factory precedent:
     detected wins over configured).
  2. No llama.cpp? → the call site's configured backend runs
     UNCHANGED (Ollama, the always-on default).

Cloud providers are NEVER overridden — a cloud selection
(openrouter / openai / openai_compatible / freellmapi / claude) is a
deliberate non-local choice and is not probed at all.

Scope (the honest boundary): this policy is consulted by the
raw-request tool call sites only. The main conversion pipeline keeps
its wizard-selected provider — its VRAM budget gate (V0.6.9, restored)
is confirmed against the CONFIGURED model, and a silent mid-run swap to
a different llama.cpp model would bypass that confirmed budget.

Kill switch: ``local.llamacpp_first = false`` restores the pre-V0.6.12
behavior at every wired site (no probe, straight passthrough).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from core.llm.llamacpp_provider import list_llamacpp_models
from core.system.timeouts import UI_PROBE_TIMEOUT_S

# The llama.cpp default (single source: the wizard mixin's
# LLAMACPP_DEFAULT_URL and the settings.py defaults block).
LLAMACPP_DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"

# V0.6.55 (P1a): llama.cpp's shifting default PORTS, probe order:
#   8000 — llama.cpp's CURRENT default (the operator's rig runs it here;
#          the V0.6.54 CHANGELOG "configuration, not code" note)
#   9931 — the ANNOUNCED future default (llama-server's console notice)
# NOT listed: 8080 — that is LLAMACPP_DEFAULT_BASE_URL itself and is
# always probed FIRST (a live default keeps byte-identical V0.6.12
# behavior; the alternates only fire when the default is DEAD).
LLAMACPP_ALT_BASE_URLS = (
    "http://127.0.0.1:8000/v1",
    "http://127.0.0.1:9931/v1",
)

# Providers that are deliberate NON-local choices — never probed, never
# overridden (single source with create_provider's dispatch set,
# core/llm/llm_provider_impl.py:201). "cloud" is the packets dialog's
# legacy name for the same family.
CLOUD_PROVIDERS = frozenset(
    {"cloud", "openrouter", "openai", "openai_compatible", "freellmapi", "claude"}
)

# Loopback hostnames (case-insensitive) — the URL-locality predicate
# below. ``urlparse().hostname`` lowercases and strips the brackets off
# IPv6 literals, so "::1" is compared bare.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def is_local_url(url: str) -> bool:
    """True when ``url`` points at this machine's loopback interface.

    V0.6.13: the policy only overrides LOCAL call sites. A tool whose
    configured endpoint is a DELIBERATE non-local choice (a LAN Ollama,
    a hosted OpenAI-compatible URL) passes through untouched — the same
    treatment cloud providers get. Used by the wired sites that have no
    provider concept and only a URL (the podcast script generator's
    ``ollama_url``, the TTS normalizer's ``tts.normalize_endpoint``).

    Empty / malformed input → False (never probe, never take over — the
    conservative answer that leaves the caller's own path alone).
    """
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
    except Exception:
        return False
    return host in _LOCAL_HOSTS


@dataclass(frozen=True)
class LlamacppFirstDecision:
    """The routing decision for ONE local LLM call site.

    ``use_llamacpp`` True → route the call to ``base_url`` with
    ``model`` and the ``api_key`` bearer (llama-server enforces the key
    only when started with ``--api-key`` — the V0.04 provider contract).

    ``use_llamacpp`` False → keep the call site's own configured path
    exactly as before V0.6.12 (base/model/key fields empty).

    ``note`` is one human-readable line for the tool's log ("" when
    there is nothing to say — cloud passthrough, policy off).
    """

    use_llamacpp: bool
    base_url: str
    model: str
    api_key: str
    note: str


_PASSTHROUGH = LlamacppFirstDecision(False, "", "", "", "")

# ── the probe cache ────────────────────────────────────────────────────────
# The packets generator resolves once per packet (5+ resolutions per run);
# without the cache every resolution re-probes /v1/models (5 s worst case
# each on a blackholed URL — the UI-probe family budget). TTL 30 s keeps a
# llama-server started mid-session picked up on the next resolution after
# expiry, while a normal run pays the probe cost at most twice.
_PROBE_CACHE: dict[tuple[str, str], tuple[float, list[str]]] = {}
_PROBE_CACHE_TTL_S = 30.0
_PROBE_LOCK = threading.Lock()


def clear_llamacpp_probe_cache() -> None:
    """Test hook: drop the cached /v1/models results."""
    with _PROBE_LOCK:
        _PROBE_CACHE.clear()


def _probe_llamacpp(base_url: str, api_key: str) -> list[str]:
    """Cached GET ``{base_url}/models`` → the served model ids.

    ``[]`` = no live llama.cpp here (refused / timed out / non-200 /
    empty list / any exception — never raises; "dead" is a valid answer
    the caller acts on, not an error).
    """
    now = time.monotonic()
    key = (base_url, api_key)
    with _PROBE_LOCK:
        hit = _PROBE_CACHE.get(key)
        if hit is not None and now - hit[0] < _PROBE_CACHE_TTL_S:
            return hit[1]
    try:
        models = list(list_llamacpp_models(base_url, api_key, timeout=UI_PROBE_TIMEOUT_S))
    except Exception:
        models = []
    with _PROBE_LOCK:
        _PROBE_CACHE[key] = (now, models)
    return models


def _configured_base_url(settings: Any) -> str:
    """The configured llama.cpp base URL, stripped + defaulted.

    Shared by ``resolve_llamacpp_base_url`` and ``decide_llamacpp_first``
    so both read EXACTLY the same value (single source).
    """
    base = str(
        settings.get("summarisation.llamacpp_base_url", LLAMACPP_DEFAULT_BASE_URL)
        or LLAMACPP_DEFAULT_BASE_URL
    ).strip()
    return base or LLAMACPP_DEFAULT_BASE_URL


def _probe_candidates(base: str, api_key: str) -> list[tuple[str, list[str]]]:
    """Probe the base URL first; if it is the UNMODIFIED app default and
    it is dead, probe the well-known alternates in order.

    Returns the probed (url, served_models) pairs in probe order — the
    caller picks the first live one (or acts on the all-dead list).
    Never raises; a probe that explodes counts as dead (the
    ``_probe_llamacpp`` contract).
    """
    probed: list[tuple[str, list[str]]] = [(base, _probe_llamacpp(base, api_key))]
    if base == LLAMACPP_DEFAULT_BASE_URL and not probed[0][1]:
        for alt in LLAMACPP_ALT_BASE_URLS:
            served = _probe_llamacpp(alt, api_key)
            probed.append((alt, served))
            if served:
                break  # first live wins — no over-probing
    return probed


def resolve_llamacpp_base_url(settings: Any, api_key: str | None = None) -> str:
    """V0.6.55 (P1a): the single source for "which llama.cpp URL to talk to".

    - An EXPLICIT operator-configured URL is returned as-is (never
      probed here — a deliberate choice, the V0.6.12 contract).
    - The unmodified default setting: the first LIVE well-known port
      (8080 first, then 8000, then 9931). All dead → the default
      (byte-identical to pre-V0.6.55 callers).

    Consumed by ``create_provider``'s llamacpp branch so every
    factory-built provider follows the auto-detection (not just the
    routing decision). The probe cache bounds the cost: one pass per
    30s TTL window per (url, key).
    """
    base = _configured_base_url(settings)
    if base != LLAMACPP_DEFAULT_BASE_URL:
        return base
    if api_key is None:
        from core.system.secrets import get_secret

        api_key = str(get_secret("summarisation.llamacpp_api_key", settings, "local") or "local")
    for url, served in _probe_candidates(base, api_key):
        if served:
            return url
    return base


def decide_llamacpp_first(
    settings: Any,
    requested_provider: str,
) -> LlamacppFirstDecision:
    """Apply the llama.cpp-first policy to one local LLM call.

    Pure routing logic + the cached probe — no HTTP call of its own
    beyond the probe, no settings writes, never raises.
    """
    provider = (requested_provider or "").strip().lower()

    # Cloud selections are deliberate non-local choices — never probed.
    if provider in CLOUD_PROVIDERS:
        return _PASSTHROUGH

    try:
        policy_on = bool(settings.get("local.llamacpp_first", True))
    except Exception:
        policy_on = True
    if not policy_on:
        return _PASSTHROUGH

    from core.system.secrets import get_secret

    api_key = str(get_secret("summarisation.llamacpp_api_key", settings, "local") or "local")

    # V0.6.55 (P1a): the default port may be dead while llama.cpp lives
    # on a shifting default (8000 today, 9931 announced). Explicit
    # operator URLs are still probed alone (deliberate choice, V0.6.12).
    base = _configured_base_url(settings)
    probed = _probe_candidates(base, api_key)
    live = [(url, served) for url, served in probed if served]
    if not live:
        probed_urls = ", ".join(url for url, _ in probed)
        return LlamacppFirstDecision(
            use_llamacpp=False,
            base_url="",
            model="",
            api_key="",
            note=(
                f"llama.cpp not reachable at {base}"
                + (
                    f" (probed {probed_urls} — auto-detection)"
                    if len(probed) > 1
                    else ""
                )
                + " — using the configured backend"
            ),
        )
    base, served = live[0]
    auto = (
        f" (port auto-detected — configured default "
        f"{LLAMACPP_DEFAULT_BASE_URL} was not reachable)"
        if len(probed) > 1 and base != LLAMACPP_DEFAULT_BASE_URL
        else ""
    )

    # V0.4.30 factory precedent: the DETECTED served model wins over the
    # configured name (a llama-server at this URL serving a different
    # model is addressed by what it actually serves).
    configured = str(settings.get("summarisation.llamacpp_model", "") or "").strip()
    model = served[0]
    extra = f" (configured '{configured}' overridden)" if configured and configured != model else ""
    return LlamacppFirstDecision(
        use_llamacpp=True,
        base_url=base,
        model=model,
        api_key=api_key,
        note=f"llama.cpp detected at {base} (model '{model}'){auto}{extra} — routing to it",
    )
