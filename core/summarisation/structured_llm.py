"""V18.15.3 (Phase 5 Stage 3, Batch 4.1): Structured (JSON) LLM output.

Extracted verbatim from ``Summarizer._call_llm_structured`` (god-class
decomposition Stage 4 — the 13th extraction). Calls the LLM requesting JSON,
validates against ``SummarySchema``, and falls back to the XML parser on ANY
failure. Opt-in: only activates when ``supports_json_mode()`` returns True for
the provider+model combination (low-bit quants like IQ2_XXS are excluded per
Key Decision #5).

**Extraction map**:

| Summarizer method (old) | structured_llm function (new) | self deps |
|------------------------|------------------------------|-----------|
| ``_call_llm_structured`` | ``call_llm_structured`` | ``provider`` (str), ``_parse_response`` (callback), ``log`` (callback) |

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-3 pattern. Zero mutable state —
the function is read-only w.r.t. the Summarizer instance.

Characterization tests: ``tests/test_structured_llm.py`` captures the
import-unavailable path, the unsupported-model path, the provider-build-failure
path, and the success path (JSON validated) with mocked
``complete_structured`` / ``supports_json_mode``.

**V18.20.2.0 (SWOT A16) — DECISION (behavior preservation)**: the old
provider construction called ``create_provider(provider=…, model=…,
settings=…)`` — a signature that does not exist (the real one is
``create_provider(provider, settings, log_callback, supervisor)``) — so it
raised ``TypeError`` on EVERY chapter and the blanket ``except Exception``
swallowed it, making ``call_llm_structured`` return None with zero visibility
through 4 consecutive golden runs. The construction below is now CORRECT, but
the structured/JSON path itself stays intentionally DISABLED: activating it
would flip every chapter to an untested code path (SWOT Threat T2 — a golden
cliff in either direction). The function therefore fails fast with a ONE-TIME
INFO log ("structured path unavailable — using fallback") and returns the
documented fallback (None → the caller's XML path). Behavior is byte-for-byte
identical to the accidental-but-golden "always None" contract; the difference
is purely visibility.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
ParseResponseFn = Callable[[str], dict[str, Any]]

logger = logging.getLogger(__name__)

# V18.20.2.0 (SWOT A16): the structured/JSON production path is OFF. It has
# been dead through 4 consecutive golden runs (V18.19.2.4 → V18.20.1.2); the
# provider-level ``json_mode=True`` flag is never passed anywhere in the
# production path (see core/llm/structured_io.py — unchanged). Flip this flag
# ONLY together with a golden-master re-validation on the real rig.
_STRUCTURED_PATH_ENABLED = False

# One-time notice guard (per process) — the fallback notice must not spam
# the log on every chapter, it fires once.
_STRUCTURED_PATH_NOTICE_LOGGED = False


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


def _noop_parse_response(raw: str) -> dict[str, Any]:
    """Default no-op fallback parser (returns empty dict)."""
    return {}


# ── call_llm_structured (extracted verbatim) ───────────────────────────────


def call_llm_structured(
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    provider: str = "ollama",
    parse_response: ParseResponseFn | None = None,
    log: LogCallback | None = None,
) -> dict[str, Any] | None:
    """Call the LLM requesting JSON, validate against SummarySchema.

    Behaviour is byte-for-byte identical to the original
    ``Summarizer._call_llm_structured``:

    1. Append the JSON-format instruction to the prompt (handled by
       ``complete_structured``).
    2. Call the provider with ``json_mode=True``.
    3. Validate the response against ``SummarySchema``.
    4. On ANY failure (no JSON, validation error, provider error),
       fall back to the existing XML parser (``parse_response``).

    Returns a parsed dict (same shape as ``parse_response``) or None.

    V18.20.2.0 (SWOT A16): with ``_STRUCTURED_PATH_ENABLED = False`` (the
    production default) the function returns None after a one-time INFO
    notice — identical to the historical (accidental) always-None contract.
    """
    if log is None:
        log = _noop_log
    if parse_response is None:
        parse_response = _noop_parse_response

    try:
        from core.llm.structured_io import complete_structured, supports_json_mode
    except ImportError:
        return None  # structured_io unavailable — caller uses XML path

    # Determine the provider (was self.provider in the original).
    provider_name = provider or "ollama"
    if not supports_json_mode(provider_name, model):
        # Model can't follow JSON reliably (e.g. IQ2_XXS) — use XML path.
        return None

    # V18.20.2.0 (SWOT A16): fail fast + one-time INFO when the structured
    # path is disabled (the production default). This replaces the old
    # per-chapter swallowed TypeError — the outcome (None) is identical,
    # but the operator now sees WHY once per process.
    global _STRUCTURED_PATH_NOTICE_LOGGED
    if not _STRUCTURED_PATH_ENABLED:
        if not _STRUCTURED_PATH_NOTICE_LOGGED:
            _STRUCTURED_PATH_NOTICE_LOGGED = True
            logger.info(
                "structured path unavailable — using fallback (structured/JSON "
                "output intentionally disabled since V18.15.3; the V18.20.2.0 "
                "A16 fix corrected the provider construction but kept the path "
                "inert to preserve golden-run behavior)"
            )
        return None  # documented fallback: caller uses the XML path

    # Get the LLMProvider instance. The summarizer delegates via
    # _call_via_llm_provider / _call_llm which build a provider per call.
    # For this PoC, we build one inline via create_provider.
    #
    # V18.20.2.0 (SWOT A16): the call below now matches the REAL signature
    # create_provider(provider, settings, log_callback, supervisor). The old
    # code passed model=… (not a parameter) → TypeError → swallowed → the
    # structured path silently died on every chapter. The model is set on
    # the provider instance afterwards instead.
    try:
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings as _Settings

        _s = _Settings()
        prov = create_provider(provider=provider_name, settings=_s)
        # create_provider uses the settings default model — override it with
        # the per-chapter model this function was called with.
        if hasattr(prov, "model"):
            prov.model = model
    except Exception as exc:
        logger.info(
            "structured path unavailable (provider construction failed: %s: %s) — using fallback",
            type(exc).__name__,
            exc,
        )
        return None  # provider unavailable — caller uses XML path

    # Call with structured output, falling back to the XML parser.
    result = complete_structured(
        prov,
        prompt,
        fallback_parser=parse_response,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    if result is not None:
        log(
            f"    📋 Structured output: JSON validated against SummarySchema "
            f"({len(result.get('bullet_points', []))} bullets)",
            "DEBUG",
        )
    return result
