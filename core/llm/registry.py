"""V0.09 (P5): ModelRegistry — per-model context windows as DATA.

WHY THIS MODULE EXISTS
──────────────────────
Pre-P5, the model's context window was never a property of the MODEL — it
was 4 hardcoded numbers scattered across the app (settings.py:204
``max_context_tokens`` 32768, llamacpp 65536, a VRAM ladder in
summarizer.py, and UI spinboxes), none of which knew anything about the
model actually loaded.  The Task 3-b audit's headline finding: "app NEVER
queries Ollama /api/show for context length; the '-1M' tag in the new
model's name is parsed by nothing".  Concretely, the rig's 220k-context
llama.cpp model (``Ternary-Bonsai-2-27B*``, Task 8 decision #4) ran the
entire 32k-era pipeline: 4k-token map-reduce chunks, 40k map-reduce
threshold, 12k B4 threshold — none derived from the live window.

This module makes the window resolvable per (model, backend) from a
priority ladder of sources (highest first):

  1. ``llm.context_window_overrides`` settings key (dict model → int) —
     the user's explicit per-model word.  ABSENT by default (P5 adds no
     settings defaults — see the spec's backward-compat rule).
  2. ``/api/show`` probe (Ollama backend only) — ``model_info["context_length"]``.
     Short timeout, try/except, NEVER fires when offline (falls through);
     injectable for tests (monkeypatch ``_ollama_show_probe`` or set
     ``PROBE_ENABLED = False``).
  3. Modelfile ``num_ctx`` harvest (Ollama backend only) — reuses
     ``core.llm.modelfile_integrity``'s parser (spec rung 3).
  4. The static :data:`REGISTRY` table below (known models).
  5. Name-pattern hints (``-220k`` → 220000; ``1M``-style tags on API
     backends → 1M — the audit's "parsed by nothing" tag).
  6. Backend default (:data:`BACKEND_DEFAULTS`) — ollama 32768 (matches
     settings.py:204), llamacpp 65536 (matches the provider default),
     openai_compat 131072, claude 200000.

CAPS (Task 8 decision #2): local backends (ollama, llamacpp) are capped
at :data:`LOCAL_CONTEXT_CAP` = 220,144; API backends are uncapped (1M
windows allowed — "deepseek v4 flash" class models).

VRAM BOUND (spec: "reuse the EXISTING _auto_detect_context_limit ladder"):
``vram_limit_fn`` is an optional callable (the Summarizer passes its
existing ladder) bounding DISCOVERED capabilities on local backends.
Explicit values (the override dict, the caller's ``configured``/``base``)
are never ladder-reduced — that preserves the pre-P5 semantics where an
explicit request ctx was never lowered by the ladder (it only ever
replaced <= 16000 values or raised the 32768 floor).

BEHAVIOR PRESERVATION AT TODAY'S DEFAULTS (the P5 hard constraint): with
no ``llm.context_window_overrides``, no probe success, and a model absent
from the table/hints, every resolution returns exactly today's values —
ollama 32768, llamacpp 65536, the ctx_clamp/IQ2_S caps untouched (they
stay a POST-cap layer; this registry does not override them).

IMPORT RULES (P5 constraint): module-level imports are stdlib ONLY.
``utils.settings`` / ``utils.network`` / ``core.llm.modelfile_integrity``
are imported lazily INSIDE functions so this module can never participate
in an import cycle (it must NOT import core.summarisation / core.system —
both of which import core.llm).
"""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from collections.abc import Callable

logger = logging.getLogger(__name__)

__all__ = [
    "ModelRegistry",
    "get_registry",
    "backend_for_provider",
    "invalidate_registry",
    "REGISTRY",
    "BACKEND_DEFAULTS",
    "LOCAL_BACKENDS",
    "LOCAL_CONTEXT_CAP",
]

# ── Backend taxonomy ────────────────────────────────────────────────────────

#: Backends whose models run on the local GPU(s) — subject to the 220,144
#: local cap and (for discovered capabilities) the VRAM ladder.
LOCAL_BACKENDS = frozenset({"ollama", "llamacpp"})

#: Registry backend defaults (capability ladder rung 6).  These match the
#: pre-P5 hardcoded values EXACTLY (settings.py:204 for ollama, the
#: llm_provider_impl llamacpp default for llamacpp) so a bare
#: ``get_context_window(model, backend)`` call reproduces today's numbers.
BACKEND_DEFAULTS: dict[str, int] = {
    "ollama": 32768,
    "llamacpp": 65536,
    "openai_compat": 131072,
    "claude": 200000,
}

#: Fallback for unknown backend strings (mirrors create_provider's
#: default-to-ollama else-branch).
FALLBACK_DEFAULT_WINDOW = 32768

# Task 8 decision #2: local models are capped at 220,144 (the "keep the
# existing GUI ceiling" number the user chose); 1M-class windows are
# API-backends-only.  NOTE: the wizard spinboxes still allow up to 262144
# (step5_models.py:394) — the registry caps the EFFECTIVE window at
# 220144 for local backends regardless of what the spinbox sent.
LOCAL_CONTEXT_CAP = 220_144

#: provider string (Summarizer/dispatcher vocabulary) → registry backend.
PROVIDER_TO_BACKEND: dict[str, str] = {
    "ollama": "ollama",
    "llamacpp": "llamacpp",
    "openrouter": "openai_compat",
    "openai": "openai_compat",
    "openai_compatible": "openai_compat",
    "freellmapi": "openai_compat",
    "claude": "claude",
    # fusion's PRIMARY is always Ollama (rewritten in _init_provider_config)
    "fusion": "ollama",
}


def backend_for_provider(provider: str | None) -> str:
    """Map a provider string ("openrouter", "freellmapi", ...) to a registry
    backend ("ollama" | "llamacpp" | "openai_compat" | "claude").

    Canonical backend names (the :data:`BACKEND_DEFAULTS` keys) pass
    through unchanged, so callers may hand either vocabulary to every
    registry method.  Unknown providers normalize to ``"ollama"`` — the
    same default ``create_provider`` applies (its else-branch re-dispatches
    as ollama).
    """
    if not provider:
        return "ollama"
    name = str(provider).strip().lower()
    if name in BACKEND_DEFAULTS:
        return name
    return PROVIDER_TO_BACKEND.get(name, "ollama")


# ── Static capability table (ladder rung 4) ─────────────────────────────────
#
# Keys are LOWERCASE.  A trailing ``*`` means prefix-match (e.g. the rig's
# llama.cpp model family "Ternary-Bonsai-2-27B*" — Task 8 decision #4);
# keys without ``*`` match the model name exactly (case-insensitive).
# Exact matches beat prefix matches; longer prefixes beat shorter ones.
#
# VALUES ARE RAW CAPABILITIES (what the model supports) — the local
# 220,144 cap and the VRAM ladder are applied by get_context_window, NOT
# here.  Low values are inert at the Summarizer (discovery only ever
# RAISES the pipeline window there — see get_context_window's ``base``).
REGISTRY: dict[str, int] = {
    # The user's 220k-context llama.cpp model (custom build, prism AI) —
    # the model that motivated Mission-4/P5.  Prefix match covers
    # "Ternary-Bonsai-2-27B-Instruct-Vision" and future variants.
    "ternary-bonsai-2-27b*": 220_000,
    # A handful of common Ollama models (honest capabilities).
    "llama3:8b": 8_192,
    "llama3.1:8b": 131_072,
    "llama3.2:3b": 131_072,
    "mistral:7b": 32_768,
    "gemma3:12b": 128_000,
    # API models (Task 8 decision #2: 1M-class is API-backends-only).
    # Exact "deepseek v4 flash" (the user's 1M example) beats the
    # "deepseek*" prefix.
    "deepseek v4 flash": 1_000_000,
    "deepseek*": 128_000,
}

#: Per-model max-output overrides for API backends (get_max_output rung);
#: local backends use the user's Task-8 rule #1 (ollama 8192, llamacpp
#: per its 65536-context config).
MAX_OUTPUT_REGISTRY: dict[str, int] = {
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "deepseek*": 8_192,
    "claude*": 8_192,
}

# ── Name-pattern hints (ladder rung 5) ──────────────────────────────────────
#
# The audit's "parsed by nothing" finding: a "-220k" or "-1M" tag in a
# model NAME is a context declaration the app used to ignore.
#
#   r"[-_](\d+)k\b"  →  <N>k tokens (e.g. "-220k" → 220000).  Case-sensitive
#       lowercase ``k`` so quant tags like "Q4_K_M" can never match
#       (there are no digits between the ``_`` and the ``K``).
#   r"(\d+)m\b" (IGNORECASE, API backends ONLY)  →  <N>M tokens — the
#       "1M" class.  API-only per Task 8 decision #2: local "…-1M-…"
#       Ollama names (e.g. Qwythos-…-1M-Q4_K_M) must NOT claim 1M.
_KCTX_PATTERN = re.compile(r"[-_](\d+)k\b")
_MCTX_PATTERN = re.compile(r"(\d+)m\b", re.IGNORECASE)

# ── Probe configuration ─────────────────────────────────────────────────────

#: /api/show probe timeout (seconds).  Short by design: the probe runs on
#: the capability ladder; a slow/unreachable Ollama must fall through to
#: the next rung quickly, never block a conversion start.
PROBE_TIMEOUT_SEC = 5

#: Kill switch for the built-in HTTP probe.  Production default True; a
#: hermetic test run (or an air-gapped rig that DOES have something on
#: port 11434) can set ``registry.PROBE_ENABLED = False`` to force the
#: ladder to skip rung 2 entirely.  The probe is ALSO injectable: patch
#: ``core.llm.registry._ollama_show_probe`` (see tests/test_p5_model_registry.py).
PROBE_ENABLED = True


def _ollama_show_probe(model: str, base_url: str) -> int | None:
    """Ladder rung 2: ask a live Ollama ``/api/show`` for the real window.

    Returns ``model_info["context_length"]`` (or ``None`` on ANY failure —
    offline, 404, malformed payload, disabled switch).  NEVER raises: the
    ladder must fall through, not crash, when the rig is unreachable.
    """
    if not PROBE_ENABLED:
        return None
    try:
        # Lazy import (P5 constraint): utils.network pulls in ``requests``;
        # keeping it out of module level guarantees this module imports
        # with stdlib only and can never cycle.
        from utils.network import safe_ollama_request

        resp = safe_ollama_request(
            "POST",
            f"{base_url.rstrip('/')}/api/show",
            json={"model": model},
            timeout=PROBE_TIMEOUT_SEC,
        )
        data = resp.json()
        info = data.get("model_info") or {}
        value = info.get("context_length")
        if value is None:
            return None
        value = int(value)
        return value if value > 0 else None
    except Exception as exc:  # noqa: BLE001 — the probe must never raise
        logger.debug(
            "registry: /api/show probe unavailable for model=%s (%s: %s) — "
            "falling through to next capability source",
            model,
            type(exc).__name__,
            exc,
        )
        return None


def _modelfile_num_ctx(model: str) -> int | None:
    """Ladder rung 3: harvest ``PARAMETER num_ctx`` from the Modelfile.

    Reuses ``core.llm.modelfile_integrity``'s parser (spec rung 3 — the
    num_ctx parse at :55 of that module) instead of duplicating the
    PARAMETER regex.  Lazy import: that module is stdlib-only, but the
    P5 import constraint keeps ALL non-stdlib imports inside functions.
    Returns None when the ``ollama`` CLI is absent (offline sandbox:
    FileNotFoundError → instant) or the Modelfile has no num_ctx.
    """
    try:
        from core.llm.modelfile_integrity import _run_ollama_show, parse_modelfile

        text = _run_ollama_show(model)
        if not text:
            return None
        params = parse_modelfile(text)
        raw = params.get("num_ctx")
        if raw is None:
            return None
        value = int(raw)
        return value if value > 0 else None
    except Exception as exc:  # noqa: BLE001 — harvest must never raise
        logger.debug(
            "registry: Modelfile num_ctx harvest unavailable for model=%s "
            "(%s: %s) — falling through",
            model,
            type(exc).__name__,
            exc,
        )
        return None


def _table_lookup(table: dict[str, int], model: str) -> int | None:
    """Lookup ``model`` in a registry table (exact beats prefix; longest
    prefix wins).  Case-insensitive; ``*`` suffix = prefix match."""
    name = (model or "").strip().lower()
    if not name:
        return None
    if name in table:
        return table[name]
    best_prefix: str | None = None
    for key in table:
        if (
            key.endswith("*")
            and name.startswith(key[:-1])
            and (best_prefix is None or len(key) > len(best_prefix))
        ):
            best_prefix = key
    return table[best_prefix] if best_prefix is not None else None


class ModelRegistry:
    """Per-model context-window resolution with an LRU-ish discovery cache.

    Thread-safe (the cache is lock-guarded; resolution itself is pure).
    Use :func:`get_registry` for the process-wide singleton.
    """

    def __init__(self, cache_max: int = 128) -> None:
        self._lock = threading.Lock()
        # (backend, model_lower) → discovered capability (rungs 2-5).
        # Only successful discoveries are cached — failures re-attempt so
        # a model pulled mid-session is found on the next call (and
        # offline attempts cost ~1ms: refused connect).
        self._cache: OrderedDict[tuple[str, str], int] = OrderedDict()
        self._cache_max = cache_max

    # ── Public API (spec section A) ─────────────────────────────────────

    def get_context_window(
        self,
        model: str,
        backend: str,
        *,
        configured: int | None = None,
        base: int | None = None,
        vram_limit_fn: Callable[[], int] | None = None,
        allow_probe: bool = True,
        base_url: str | None = None,
    ) -> int:
        """The EFFECTIVE context window for (model, backend).

        Roughly ``min(capability, cap, vram_limit)`` where the capability
        resolves through the priority ladder — plus two caller shapes:

        - ``configured`` — the caller's explicitly configured window (the
          SETTINGS value at ``create_provider``).  When present it WINS
          over every discovery source (rungs 2-5), so the factory is
          byte-identical at today's defaults: the settings value passes
          through untouched unless ``llm.context_window_overrides`` names
          the model or the local 220,144 cap applies.
        - ``base`` — the pipeline floor (the Summarizer's request value).
          Discovery may only ever RAISE the window above the base (a
          model whose known capability is SMALLER never shrinks the
          pipeline — that lowering decision belongs to P6); when nothing
          is discovered the base is returned UNCHANGED.

        The ``llm.context_window_overrides`` settings rung (when it names
        the model) replaces everything — it is the user's explicit
        per-model word and may lower the window.

        ``vram_limit_fn`` (the Summarizer's existing
        ``_auto_detect_context_limit`` ladder) bounds DISCOVERED
        capabilities on local backends only — explicit values are never
        ladder-reduced (pre-P5, an explicit request ctx was never lowered
        by the ladder either).
        """
        backend = backend_for_provider(backend)

        # Kill switch: "llm.model_registry_enabled" == False → pure legacy
        # passthrough (no discovery, no caps — the value the caller had).
        if not self._registry_enabled():
            if configured is not None:
                return int(configured)
            if base is not None:
                return int(base)
            return BACKEND_DEFAULTS.get(backend, FALLBACK_DEFAULT_WINDOW)

        override = self._override_for(model)
        if override is not None:
            window = override
        elif configured is not None:
            window = int(configured)
        else:
            discovered = self._discover(model, backend, allow_probe=allow_probe, base_url=base_url)
            if discovered is None:
                # Nothing known about this model: the pipeline base (when
                # given) or the backend default — both byte-identical to
                # today for unknown models.
                window = (
                    int(base)
                    if base is not None
                    else BACKEND_DEFAULTS.get(backend, FALLBACK_DEFAULT_WINDOW)
                )
            else:
                window = int(discovered)
                if backend in LOCAL_BACKENDS:
                    window = min(window, LOCAL_CONTEXT_CAP)
                    if vram_limit_fn is not None:
                        limit = self._safe_limit(vram_limit_fn)
                        if limit > 0:
                            window = min(window, limit)
                if base is not None:
                    # Discovery only ever RAISES the pipeline floor.
                    window = max(window, int(base))
                    if backend in LOCAL_BACKENDS:
                        # The (explicit) base is subject to the local cap
                        # too — Task 8 rule #2 applies to every local
                        # window, however it was configured.
                        window = min(window, LOCAL_CONTEXT_CAP)
            return window

        # Explicit values (override dict / configured): local-capped but
        # never ladder-reduced (see module docstring — pre-P5 semantics).
        if backend in LOCAL_BACKENDS:
            window = min(window, LOCAL_CONTEXT_CAP)
        return window

    def get_capability(
        self,
        model: str,
        backend: str,
        *,
        allow_probe: bool = True,
        base_url: str | None = None,
    ) -> int | None:
        """What the model SUPPORTS (ladder rungs 1-5), with NO caps.

        Returns ``None`` when nothing resolves — a bare backend default is
        NOT a capability (get_context_window applies it as the last rung),
        so callers can distinguish "known 8192-token model" from "unknown
        model".  Rung 1 (``llm.context_window_overrides``) is included:
        an explicit user override IS the model's capability as far as the
        app is concerned.
        """
        backend = backend_for_provider(backend)
        override = self._override_for(model)
        if override is not None:
            return override
        if not self._registry_enabled():
            # Kill switch: no discovery at all — nothing is "known".
            return None
        return self._discover(model, backend, allow_probe=allow_probe, base_url=base_url)

    def get_max_output(self, model: str, backend: str) -> int:
        """The max OUTPUT tokens for (model, backend) — Task 8 rule #1.

        - ollama → 8192 (the user's hard rule — raising it caused the
          V18.3.6 thermal-throttling regressions);
        - llamacpp → the 65536-context config's output value
          (``summarisation.llamacpp_max_output_tokens``, default 12288 —
          "llama.cpp uses the 65536-context config");
        - API backends → 8192, or the per-model MAX_OUTPUT_REGISTRY value.

        Low-bit quant rules (iq2_s_profile CONTEXT_CAP / LOW_BIT caps)
        stay authoritative where they already apply — this method does
        NOT override them (ctx_clamp remains the post-cap layer).
        """
        backend = backend_for_provider(backend)
        if backend == "llamacpp":
            try:
                from utils.settings import Settings

                value = Settings().get("summarisation.llamacpp_max_output_tokens", 12288)
                return int(value or 12288)
            except Exception:
                return 12288
        if backend == "ollama":
            return 8192
        hit = _table_lookup(MAX_OUTPUT_REGISTRY, model)
        return int(hit) if hit is not None else 8192

    def invalidate(self, model: str, backend: str) -> None:
        """Drop the cached discovery for (model, backend).

        Call after pulling/deleting a model or changing its Modelfile so
        the next resolution re-probes instead of serving the cached
        capability.
        """
        backend = backend_for_provider(backend)
        key = (backend, (model or "").strip().lower())
        with self._lock:
            self._cache.pop(key, None)

    # ── Internals ───────────────────────────────────────────────────────

    def _discover(
        self,
        model: str,
        backend: str,
        *,
        allow_probe: bool = True,
        base_url: str | None = None,
    ) -> int | None:
        """Ladder rungs 2-5 (probe → Modelfile → table → name hints).

        The result (when non-None) is cached per (backend, model).  The
        override dict (rung 1) is deliberately NOT cached — it is a cheap
        in-memory Settings read that must reflect changes immediately.
        """
        key = (backend, (model or "").strip().lower())
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached

        capability: int | None = None
        if backend == "ollama":
            if allow_probe:
                if base_url is None:
                    base_url = self._ollama_base_url()
                capability = _ollama_show_probe(model, base_url)
            if capability is None:
                capability = _modelfile_num_ctx(model)
        if capability is None:
            capability = _table_lookup(REGISTRY, model)
        if capability is None:
            capability = self._name_hint(model, backend)

        if capability is not None and capability > 0:
            with self._lock:
                self._cache[key] = int(capability)
                while len(self._cache) > self._cache_max:
                    self._cache.popitem(last=False)
            return int(capability)
        return None

    def _name_hint(self, model: str, backend: str) -> int | None:
        """Ladder rung 5: context declarations embedded in the NAME."""
        name = model or ""
        match = _KCTX_PATTERN.search(name)
        if match:
            try:
                value = int(match.group(1)) * 1000
                if value > 0:
                    return value
            except ValueError:
                pass
        if backend not in LOCAL_BACKENDS:
            match = _MCTX_PATTERN.search(name)
            if match:
                try:
                    value = int(match.group(1)) * 1_000_000
                    if value > 0:
                        return value
                except ValueError:
                    pass
        return None

    def _override_for(self, model: str) -> int | None:
        """Ladder rung 1: ``llm.context_window_overrides`` (absent = None).

        The key is deliberately NOT in Settings._defaults() (P5 spec: new
        keys absent by default — no settings.json churn, no behavior
        change until the user writes it).  Same lookup semantics as the
        static table: exact (case-insensitive) beats prefix ``*``.
        """
        try:
            from utils.settings import Settings

            raw = Settings().get("llm.context_window_overrides", {})
        except Exception:
            return None
        if not isinstance(raw, dict) or not raw:
            return None
        # Tolerate string values from hand-edited settings.json.
        table: dict[str, int] = {}
        for key, value in raw.items():
            try:
                table[str(key).strip().lower()] = int(value)
            except (TypeError, ValueError):
                continue
        if not table:
            return None
        return _table_lookup(table, model)

    def _registry_enabled(self) -> bool:
        """``llm.model_registry_enabled`` (default True; absent = enabled).

        When False the registry is a pure passthrough — "no-op when no
        overrides/probes resolve" per the spec, made explicit for rigs
        that want the pre-P5 behavior bit-for-bit.
        """
        try:
            from utils.settings import Settings

            return bool(Settings().get("llm.model_registry_enabled", True))
        except Exception:
            return True

    @staticmethod
    def _ollama_base_url() -> str:
        try:
            from utils.settings import Settings

            return str(Settings().get("llm.ollama_url", "http://localhost:11434"))
        except Exception:
            return "http://localhost:11434"

    @staticmethod
    def _safe_limit(vram_limit_fn: Callable[[], int]) -> int:
        """Call the VRAM ladder defensively — a broken ladder must not
        crash window resolution (return 0 = "no bound available")."""
        try:
            return int(vram_limit_fn())
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "registry: vram_limit_fn failed (%s: %s) — ignoring bound",
                type(exc).__name__,
                exc,
            )
            return 0


# ── Process-wide singleton ──────────────────────────────────────────────────

_REGISTRY_SINGLETON: ModelRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_registry() -> ModelRegistry:
    """The process-wide ModelRegistry (one shared discovery cache)."""
    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        with _REGISTRY_LOCK:
            if _REGISTRY_SINGLETON is None:
                _REGISTRY_SINGLETON = ModelRegistry()
    return _REGISTRY_SINGLETON


def invalidate_registry(model: str, backend: str) -> None:
    """Convenience wrapper: invalidate on the singleton."""
    get_registry().invalidate(model, backend)
