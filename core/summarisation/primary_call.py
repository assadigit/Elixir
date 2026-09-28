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


# ── V0.5.7: separate glossary extraction helper ─────────────────────────────
#
# The V0.5.6 fused approach (the master-summary LLM call also asked for the
# ``<name_glossary>`` block) overwhelmed the model — 3 empty master-summary
# returns + a fallback to the 5-in-1 single-pass path, which had no glossary
# wired. The loosened quote-guard + the V0.5.6 final-check round 4 + the 📖
# .glossary.md persistence all stayed DORMANT.
#
# V0.5.7 separates the glossary extraction into a DEDICATED LLM call (via
# ``extract_glossary_via_llm`` in ``glossary_parser.py``). This helper wraps
# the call + the ``set_chapter_glossary`` side-channel population so the 3
# call sites in ``summarize_with_model`` (master-summary-success path +
# structured 5-in-1 fallback + raw 5-in-1 fallback) are one-liners each.
#
# Fail-open: NEVER raises — any crash in the glossary extraction wiring is
# logged + the empty glossary is returned (the verification LAYER falls back
# to the regex ``extract_citations`` backstop — the V0.5.5 behavior).
#
# Content-agnostic (Rule 1 ✓): the source text + the model name + the
# output_dir are pulled from the runtime ``request``/``call_llm``/``heading``
# args — NO hardcoded book/author/chapter names.


def _extract_glossary_for_call(
    heading: str,
    text: str,
    model: str,
    call_llm: CallLlmRetryFn | None,
    request: RequestLike,
    log: LogCallback | None = None,
) -> dict:
    """V0.5.7: extract the source glossary via a SEPARATE LLM call + stash
    it into the verification LAYER's module-level side-channel cache.

    Called from the 3 return paths of ``summarize_with_model`` (the
    master-summary-success path, the structured 5-in-1 fallback, + the raw
    5-in-1 fallback) so the glossary is extracted in BOTH paths (the V0.5.6
    audit's "0 glossary mentions" gap — the 5-in-1 fallback had no glossary
    wired + the master-summary's empty returns meant the glossary never
    fired).

    Returns the parsed glossary dict (3 keys: ``names`` / ``dates`` /
    ``terms``). Empty 3-key dict on any failure — NEVER raises.
    """
    if log is None:
        log = _noop_log
    try:
        from pathlib import Path as _Path

        from core.summarisation.glossary_parser import extract_glossary_via_llm
        from core.summarisation.verification_phase import set_chapter_glossary

        glossary = extract_glossary_via_llm(
            source_text=text,
            call_llm=call_llm,
            primary_model=model,
            temperature=0.3,
            max_output_tokens=8192,  # V0.5.9: was 4096 (overrode the V0.5.8 default) — the glossary for 74 authors needs >4096
            log=log,
            chapter_heading=heading,
            # V0.5.20 (the rig-run-2 handoff break): persist into the RUN's
            # output dir, not the user's base dir. ``request.output_dir`` is
            # the BASE the user picked; the converter ALWAYS creates a
            # per-book run folder under it (``create_output_folder(…,
            # per_book=True)`` → ``…\5.19.1\<the book's run folder>\``)
            # and attaches it to the request as ``_run_output_dir`` (the
            # run_summarization wiring, right next to the ``_run_id``
            # unification). The V0.5.19.1 full-book run persisted the
            # glossary OUTSIDE the run's output dir
            # (``…\5.19.1\summaries\.glossaries\…`` vs
            # ``…\5.19.1\<the book's run folder>\``) — an audit
            # looking for the .glossary.md in the run dir found nothing.
            # Fall back to ``request.output_dir`` (the harness path, where
            # the request IS the run dir). Content-agnostic (Rule 1 ✓).
            output_dir=str(
                getattr(request, "_run_output_dir", None)
                or getattr(request, "output_dir", _Path("."))
            ),
            run_id=str(getattr(request, "_run_id", "")),
        )
        # Stash the glossary into the verification LAYER's module-level
        # side-channel cache so callers WITHOUT a SummaryResult in scope
        # (the ChapterCheckpointSaver path) can still pick it up via
        # ``get_chapter_glossary(chapter_heading)``. None/empty → the
        # entry is removed (fail-open to the V0.5.5 regex behavior).
        set_chapter_glossary(heading, glossary if glossary else None)
        return glossary
    except Exception as _e:  # noqa: BLE001 — fail-open (NEVER crash the summary)
        logger.warning(
            "V0.5.7: glossary extraction wiring failed (non-fatal — "
            "the verification LAYER will fall back to the regex "
            "extract_citations): %s: %s",
            type(_e).__name__,
            _e,
        )
        log(
            f"    ⚠️ V0.5.7: glossary extraction wiring failed (non-fatal — "
            f"falling back to regex) ({type(_e).__name__})",
            "WARNING",
        )
        return {}


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
    # V0.4: the old chunking gates (_should_chunk, low-bit-quant gate) are
    # REMOVED. The master-summary 3-call architecture is now the DEFAULT
    # for ALL chapters (see the V0.4 block below). The strategy engine
    # (core/summarisation/strategy.py) decides map-reduce vs single-pass
    # based on the context window — for large-context models (> 32k),
    # the adaptive path scales the threshold automatically. The
    # _window_tokens variable is kept for the fallback path below.
    # V0.4 (Quality Campaign): make the master-summary 3-call architecture
    # the DEFAULT for ALL chapters, regardless of model type or size. The
    # V0.3 audit proved this architecture scores 9/10 (ch.2) — the old 5-in-1
    # primary call caused every regression (V0.18 truncation, V0.20.2 CoT,
    # V0.20.5 outline). Now the 5-in-1 call is the FALLBACK (only used if the
    # master-summary call fails).
    #
    # The chunked_summarize function (which contains the 3-call pipeline:
    # master summary → derive bullets → derive exec) now runs for every
    # chapter. The old chunking gates (input > 12000, low-bit quant + 6000)
    # are removed — the master-summary architecture doesn't need them because
    # each call has a focused output (one section, not five).
    #
    # For large chapters that need map-reduce (input > 75% of num_ctx), the
    # map-reduce path fires BEFORE this point (in _summarize_inner's strategy
    # engine), so chunked_summarize only handles single-pass chapters.
    log(
        f"    📦 V0.4: master-summary architecture (default) — "
        f"input {_input_tokens_actual} tok, output cap {_max_out}",
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
        # V0.5.7: extract the source glossary via a SEPARATE LLM call (the
        # V0.5.6 fused approach overwhelmed the model — the master-summary
        # prompt no longer carries the <name_glossary> block). Stash it onto
        # the result dict + the verification LAYER's side-channel cache so
        # the LAYER can use it as the coverage ground truth (richer than the
        # regex extract_citations backstop). Fail-open: an empty glossary is
        # stashed as None (the LAYER falls back to the regex behavior).
        _chunked_result["source_glossary"] = _extract_glossary_for_call(
            heading=heading,
            text=text,
            model=model,
            call_llm=call_llm_with_empty_retry,
            request=request,
            log=log,
        )
        return _chunked_result
    # Fall through to the old 5-in-1 single-pass if master-summary failed
    log(
        "    ⚠️ V0.4: master-summary architecture failed — falling back to 5-in-1 single-pass",
        "WARNING",
    )

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
        # V0.5.7: the 5-in-1 fallback path ALSO extracts the glossary via the
        # separate call (the V0.5.6 audit's gap — the 5-in-1 path had no
        # glossary wired). Same wiring as the master-summary-success path.
        _structured["source_glossary"] = _extract_glossary_for_call(
            heading=heading,
            text=text,
            model=model,
            call_llm=call_llm_with_empty_retry,
            request=request,
            log=log,
        )
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
    # V0.5.7: the 5-in-1 raw fallback path ALSO extracts the glossary via
    # the separate call (the V0.5.6 audit's gap — the 5-in-1 path had no
    # glossary wired). Same wiring as the master-summary-success path +
    # the structured 5-in-1 path.
    parsed["source_glossary"] = _extract_glossary_for_call(
        heading=heading,
        text=text,
        model=model,
        call_llm=call_llm_with_empty_retry,
        request=request,
        log=log,
    )
    return parsed
