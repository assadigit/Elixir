"""V18.15.3 (Phase 5 Stage 3, Batch 4.7): Primary summarization call.

Extracted verbatim from ``Summarizer._summarize_with_model`` (god-class
decomposition Stage 4 — the 19th and final extraction). The primary
single-chapter summarization entry point: decides chunked vs single-pass
(thermal-aware), tries structured JSON output first, falls back to the XML
path, and annotates the parsed result with raw/model/temperature metadata.

**Extraction map**:

| Summarizer method (old) | primary_call function (new) | self deps |
|------------------------|----------------------------|-----------|
| ``_summarize_with_model`` | ``summarize_with_model`` | ``request`` (read-only), ``log``, ``_chunked_summarize``, ``_build_prompt``, ``_call_llm_structured``, ``_call_llm_with_empty_retry``, ``_strip_thinking``, ``_parse_response`` |

**Note on ``request``**: ``ConversionRequest`` is the primary read-only INPUT
data object (accessed only via ``getattr`` for ``summarisation_max_output_tokens``),
not a ``PromptContext``-style context object. Passing it explicitly is
consistent with the V18.6.3 crash mitigation.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Zero mutable state — the function is read-only w.r.t. the Summarizer instance.

**Hard constraints honored** (preserved verbatim):
- ``max_output=8192`` (the ``summarisation_max_output_tokens`` getattr default)
- chunking threshold 12000 input tokens + thermal guard (<78°C)
- structured-JSON-first, XML-fallback dispatch
- Qwen3 ``/no_think`` injection stays in ``_call_llm_with_empty_retry`` (NOT moved)

Characterization tests: ``tests/test_primary_call.py`` captures the
chunked-path success, chunked-failure fallback, thermal-skip, structured-JSON
success, empty-response None, and the XML-parse success path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# V0.10 (P6): the legacy-window boundary for the chunked-output gate —
# at windows > 32768 the strategy engine (core/summarisation/strategy.py)
# disables b4_sections/chunked_output entirely.
from core.llm.context_budget import LEGACY_WINDOW

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
RequestLike = Any
ChunkedSummarizeFn = Callable[..., dict[str, Any] | None]
BuildPromptFn = Callable[..., str]
CallLlmStructuredFn = Callable[..., dict[str, Any] | None]
CallLlmRetryFn = Callable[..., str | None]
StripThinkingFn = Callable[[str], str]
ParseResponseFn = Callable[[str], dict[str, Any]]

logger = logging.getLogger(__name__)


# ── V18.20.2.0 (SWOT A26): module-level nvidia-smi temperature cache ────────
#
# summarize_with_model is invoked for the primary call AND for every B3
# sample / B4 section / self-consistency extra — each invocation used to
# spawn a fresh ``nvidia-smi`` subprocess (5s timeout) on the thermal-
# critical path (100-200+ spawns per book). GPU temperature moves on the
# order of seconds-to-minutes, so a short-TTL module-level cache removes
# the subprocess churn without meaningfully staleness-ing the ≥78°C
# thermal guard. Only SUCCESSFUL readings are cached — a failed spawn keeps
# the original fallback (temp 0.0 → thermal_ok True) and is retried on the
# next call (no persistent negative caching). Best-effort: the dict update
# is GIL-atomic, so under the (max_workers>1) parallel path two threads
# may occasionally both spawn a probe — harmless.

_GPU_TEMP_CACHE_TTL_SEC = 30.0
_gpu_temp_cache: dict[str, float] = {"ts": 0.0, "temp": 0.0, "valid": 0.0}


def _read_gpu_temp_c() -> float:
    """V18.20.2.0 (SWOT A26): GPU temperature via nvidia-smi, cached ~30s.

    Returns 0.0 when the reading is unavailable (the caller treats 0.0 as
    "unknown" → thermal check passes), exactly as the pre-cache inline code
    did. Reset by tests via ``_gpu_temp_cache["valid"] = 0.0``.
    """
    import time as _time_thermal

    _now = _time_thermal.monotonic()
    if _gpu_temp_cache["valid"] and (_now - _gpu_temp_cache["ts"]) < _GPU_TEMP_CACHE_TTL_SEC:
        return _gpu_temp_cache["temp"]
    _temp = 0.0
    try:
        import subprocess as _sub_thermal

        _r = _sub_thermal.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if _r.returncode == 0 and _r.stdout.strip():
            _temp = float(_r.stdout.strip().split()[0])
    except Exception:
        # Failure fallback (unchanged): unknown temp → 0.0 → thermal_ok True.
        # Deliberately NOT cached — the next call retries the probe.
        return 0.0
    _gpu_temp_cache["ts"] = _now
    _gpu_temp_cache["temp"] = _temp
    _gpu_temp_cache["valid"] = 1.0
    return _temp


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── summarize_with_model (extracted verbatim) ──────────────────────────────


def summarize_with_model(
    heading: str,
    text: str,
    model: str,
    temp: float,
    with_cot: bool = True,
    max_tokens: int | None = None,
    concepts: list[str] | None = None,
    callouts: list[str] | None = None,
    request: RequestLike = None,
    log: LogCallback | None = None,
    chunked_summarize: ChunkedSummarizeFn | None = None,
    build_prompt: BuildPromptFn | None = None,
    call_llm_structured: CallLlmStructuredFn | None = None,
    call_llm_with_empty_retry: CallLlmRetryFn | None = None,
    strip_thinking: StripThinkingFn | None = None,
    parse_response: ParseResponseFn | None = None,
) -> dict[str, Any] | None:
    """Primary single-chapter summarization call.

        V18.3.5 (F1+F3): CHUNKED OUTPUT for large chapters — FIXED thresholds.
    V18.3.4 had 3 bugs that caused the rig-test book's failure:
          1. len(text)//4 overestimates (4.7 chars/token) → chunked unnecessarily.
          2. The 10000 threshold was too low — 9,139-token chapters fit in a
             single 8192-output call (proven by V18.2.44 gold standard).
          3. No thermal guard — chunking makes 2 calls (2× heat) → thermal
             throttling → 300s timeout → model stall.
        FIX: use ACTUAL token count (not char estimate), raise threshold to
        12000, and DON'T chunk when the GPU is already hot (≥78°C).
    """
    if log is None:
        log = _noop_log

    from utils.token_counter import count_tokens as _count_tokens_chunk

    _input_tokens_actual = _count_tokens_chunk(text)  # actual token count
    _max_out = max_tokens or getattr(request, "summarisation_max_output_tokens", 8192) or 8192
    # F1: raised threshold from 10000 → 12000 (a 9,139-token chapter must NOT chunk).
    # F3: check GPU temp — don't chunk if ≥78°C (thermal throttling risk).
    # Uses nvidia-smi (the app's standard method — torch doesn't expose temp).
    # V18.20.2.0 (SWOT A26): the probe goes through the ~30s module-level
    # cache (_read_gpu_temp_c) — same 0.0-on-failure fallback, same <78°C
    # guard, but one subprocess per 30s instead of one per call.
    _gpu_temp_c = _read_gpu_temp_c()
    _thermal_ok = _gpu_temp_c < 78.0 if _gpu_temp_c > 0 else True
    # Chunk ONLY when: input > 12000 AND output < 14000 AND GPU not too hot
    # V0.10 (P6): …AND window <= 32768. At larger windows (the 220k rig)
    # the chunked-output path NEVER fires — a >12000-token input that
    # reached the primary call fits the window trivially, and splitting
    # the output call in two only exists to dodge truncation. At legacy
    # windows the gate is byte-identical to V18.3.5 (default 32768 when
    # the request carries no context value).
    _window_tokens = int(
        getattr(request, "summarisation_max_context_tokens", LEGACY_WINDOW) or LEGACY_WINDOW
    )
    _should_chunk = (
        _input_tokens_actual > 12000
        and _max_out < 14000
        and _thermal_ok
        and _window_tokens <= LEGACY_WINDOW
    )
    # V0.20.2 (Quality Campaign, conversion-log audit Defect L4, §7b — the
    # owner's "chunk outputs" suggestion): ALSO chunk when the model is a
    # LOW-BIT QUANT (output-capped at 8192 by V18.2.37d, prone to CoT
    # inundation) and the input is MODERATE (> 6000 tok). The V0.18 rig run
    # (run 20260920-084745-c0874728) had input 8566 tok (under the 12000
    # gate) and STILL truncated: the model produced a 17313-char CoT
    # response that hit the 8192 output cap, the 5-section XML was inside
    # the thinking block, and only 30 bullets survived. 286s produced
    # almost nothing. The existing 12000-tok gate missed this because it
    # gates on INPUT size, but the truncation was on OUTPUT.
    #
    # Content-agnostic (no chapter-specific thresholds): the second
    # condition gates on a MODEL property (is_low_bit_quant — the same
    # detector V18.2.37d uses to cap output at 8192) + a SIZE threshold
    # (6000 tok). 6000 is chosen to capture the V0.18 rig's 8566-tok
    # chapter while leaving a 4.6× margin below the smallest golden
    # chapter (1262 tok) — the golden corpus never triggers this path.
    # The low-bit + moderate-input combination is the exact risk profile
    # the V0.18 rig exhibited: a model that fills its 8192-output budget
    # with thinking on a chapter big enough to warrant 5 sections.
    _v0202_chunk_logged = False
    if not _should_chunk and _max_out < 14000 and _thermal_ok and _window_tokens <= LEGACY_WINDOW:
        try:
            from core.llm.model_taxonomy import is_low_bit_quant as _is_lbq_v0202

            _is_low_bit_model = _is_lbq_v0202(model or "")
        except Exception:  # pragma: no cover — taxonomy must never break the call
            _is_low_bit_model = False
        if _is_low_bit_model and _input_tokens_actual > 6000:
            _should_chunk = True
            _v0202_chunk_logged = True
            log(
                f"    📦 V0.20.2: chunked output (low-bit quant + moderate "
                f"input) — model {model!r} is low-bit (output capped at "
                f"{_max_out}), input {_input_tokens_actual} tok > 6000 "
                f"→ splitting 5-section primary call into 2 sequential calls "
                f"(avoids the V0.18 rig Defect L4: CoT inundation + output "
                f"truncation on a single 8192-output call)",
                "INFO",
            )
    if _should_chunk:
        if not _v0202_chunk_logged:
            log(
                f"    📦 V18.3.5: chunked output — input {_input_tokens_actual} tok, output cap {_max_out} "
                f"→ splitting 5-section primary call into 2 sequential calls (no truncation)",
                "INFO",
            )
        _chunked_result = chunked_summarize(
            heading,
            text,
            model,
            temp,
            with_cot,
            concepts,
            callouts,
            _max_out,
        )
        if _chunked_result is not None:
            return _chunked_result
        # Fall through to single-pass if chunked failed
        log("    ⚠️ V18.3.4: chunked output failed — falling back to single-pass", "WARNING")

    prompt = build_prompt(heading, text, with_cot=with_cot, concepts=concepts, callouts=callouts)
    # V18.2.22 (Phase 2.2 PoC): Try structured JSON output first (when the
    # model supports it), falling back to the XML path on any failure.
    # This is the bridge from the 30-regex XML parser to provider JSON mode.
    # Low-bit quants (IQ2_XXS) skip this (supports_json_mode returns False)
    # and use the XML path directly — Key Decision #5.
    _structured = call_llm_structured(prompt, model=model, temperature=temp, max_tokens=max_tokens)
    if _structured is not None:
        _structured["raw"] = ""  # no raw XML (was JSON)
        _structured["model"] = model
        _structured["temperature"] = temp
        return _structured
    # V13.35.0: Use retry wrapper to recover from transient empty responses
    # (VRAM eviction on RTX 3060 12GB with Gemma 4 12B ~10.9 GB VRAM).
    raw = call_llm_with_empty_retry(prompt, model=model, temperature=temp, max_tokens=max_tokens)
    if not raw:
        return None
    # Strip thinking from the raw response before parsing
    raw = strip_thinking(raw)
    # debug log the first 500 chars of the raw response so we
    # can see what tag format the model is using (for parser debugging)
    log(f"    📋 Raw response (first 500 chars): {raw[:500]!r}", "DEBUG")
    parsed = parse_response(raw)
    parsed["raw"] = raw
    parsed["model"] = model
    parsed["temperature"] = temp
    return parsed
