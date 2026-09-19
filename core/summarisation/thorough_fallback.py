"""V18.11 (Phase 5 Stage 3, Batch 2.3): Dedicated thorough call + 3-attempt fallback.

Extracted verbatim from ``Summarizer._call_dedicated_thorough_with_fallback``
(god-class decomposition Stage 3). Hardens the dedicated thorough summary path
with 3 LLM attempts (normal → directive nudge → greedy temperature 0.0) and a
deterministic synthetic fallback built from the exec summary + bullets.

**Extraction map**:

| Summarizer method (old)                  | thorough_fallback function (new)         | self deps |
|------------------------------------------|------------------------------------------|-----------|
| ``_call_dedicated_thorough_with_fallback`` | ``call_dedicated_thorough_with_fallback`` | ``request.summarisation_max_output_tokens``, ``_strip_thinking``, ``_call_llm``, ``primary_model``, ``temperature``, ``log``, ``_deadline_exceeded``, ``_synthetic_thorough_fallback_count`` (mutable int) |

**Mutable-state handling**: ``_synthetic_thorough_fallback_count`` is a plain
``int`` incremented in the synthetic-fallback branch. Like the
``_leak_guard_fire_count`` in Batch 1.4, it's passed in as an int and the
(possibly incremented) new count is returned alongside the thorough text:

    thorough, self._synthetic_thorough_fallback_count = (
        tf_call_dedicated_thorough_with_fallback(
            ..., synthetic_fallback_count=self._synthetic_thorough_fallback_count, ...
        )
    )

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).

Characterization tests: ``tests/test_thorough_fallback.py`` captures the
3-attempt + synthetic-fallback paths with mocked ``call_llm`` /
``strip_thinking`` / ``deadline_exceeded``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

# Type aliases (duck-typed).
LogCallback = Callable[[str, str], None]
CallLlmFn = Callable[..., str | None]
StripThinkingFn = Callable[[str], str]
DeadlineExceededFn = Callable[[str], bool]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── call_dedicated_thorough_with_fallback (extracted verbatim) ────────────


def call_dedicated_thorough_with_fallback(
    prompt: str,
    exec_sum: str,
    bullets: list[str],
    *,
    min_words: int = 800,
    max_output_tokens: int,
    primary_model: str,
    temperature: float,
    strip_thinking: StripThinkingFn,
    call_llm: CallLlmFn,
    deadline_exceeded: DeadlineExceededFn,
    synthetic_fallback_count: int,
    log: LogCallback | None = None,
) -> tuple[str | None, int]:
    """V18.2.44 (Next Step #6): Dedicated thorough call with 3 attempts + a
    deterministic non-empty fallback.

    Extracted verbatim from ``Summarizer._call_dedicated_thorough_with_fallback``.
    Returns ``(thorough_text, new_synthetic_fallback_count)`` — the caller
    unpacks and re-assigns the count to ``self._synthetic_thorough_fallback_count``
    (kept as a plain int).

    The V18.2.34 dedicated thorough call used ``_call_llm_with_empty_retry``
    which does exactly 2 attempts (1 retry). The V18.2.43 session log showed
    this sometimes BOTH attempts returning empty on the IQ2_S 27B model
    (transient VRAM eviction mid-generation), leaving the thorough summary
    empty and silently degrading to ``thorough = exec_sum`` (a 1-paragraph
    stub instead of the documented 800-1200 word analysis).

    This helper hardens the path:
      - Attempt 1: the normal dedicated prompt (via call_llm).
      - Attempt 2 (if #1 empty/short): retry with a terse directive nudge +
        a 3s VRAM-reload delay (the model may have been evicted).
      - Attempt 3 (if #2 empty/short): retry at temperature 0.0 (greedy
        decoding — maximally deterministic, least likely to wander into an
        empty generation).
      - If ALL 3 fail OR the winner is still < ``min_words``: synthesize a
        deterministic thorough from ``exec_sum`` + the bullets (joined as
        flowing prose). This is material the model ALREADY produced and
        the user already saw — it is guaranteed non-empty and guaranteed
        on-topic, so it is strictly better than the V18.2.43 silent
        ``thorough = exec_sum`` fallback (which dropped ALL bullets).

    Returns the best thorough text found (stripped of thinking), or the
    synthetic fallback. NEVER returns None when ``exec_sum`` or ``bullets``
    contain any usable text.
    """
    log = log or _noop_log
    # Local mutable copy of the fallback counter — incremented only in the
    # synthetic-fallback branch; returned to the caller for re-assignment.
    fallback_count = synthetic_fallback_count
    _max_tok = min(max_output_tokens or 8192, 8192)

    def _parse_thorough(raw: str | None) -> str | None:
        if not raw:
            return None
        raw = strip_thinking(raw)
        m = re.search(r"<thorough_summary>(.*?)</thorough_summary>", raw, re.DOTALL)
        if m:
            return m.group(1).strip()
        return raw.strip() or None

    best: str | None = None
    best_words: int = 0

    # ── Attempt 1: the normal prompt (temperature * 0.5, as before). ──
    # V18.12.1 hotfix: wrap call_llm in try/except so a persistent Ollama 500
    # (or any exception that exhausts the retry_llm_call decorator) falls
    # through to attempt 2 instead of crashing the conversion. The V18.12.0
    # golden-master run hit this: Ollama 500'd after the 7-min primary call
    # (GPU hot/stressed), the retry decorator re-raised, and the uncaught
    # exception crashed _summarize_inner. This was a pre-existing gap in the
    # V18.10.1 original (the 3-attempt fallback only handled call_llm
    # returning None, not call_llm raising). Now each attempt catches
    # exceptions and proceeds to the next, with the synthetic fallback as
    # the last resort.
    try:
        # V18.20.2.0 (SWOT A5): attempt 1 uses the plain dedicated prompt and
        # calls call_llm DIRECTLY, bypassing the V18.2.41 /no_think injection
        # in _call_llm_with_empty_retry (attempts 2/3 carry it in their nudges).
        # Inject it here for Qwen-family models via the shared helper.
        from core.summarisation.filter_thinking import qwen_no_think

        raw1 = call_llm(
            qwen_no_think(prompt, primary_model),
            model=primary_model,
            temperature=temperature * 0.5,
            max_tokens=_max_tok,
        )
    except Exception as _e1:
        log(
            f"    \u26a0\ufe0f Attempt 1/3 dedicated thorough crashed "
            f"({type(_e1).__name__}: {_e1}) \u2014 falling through to attempt 2",
            "WARNING",
        )
        logger.warning("dedicated thorough attempt 1 crashed: %s: %s", type(_e1).__name__, _e1)
        raw1 = None
    t1 = _parse_thorough(raw1)
    if t1:
        best, best_words = t1, len(t1.split())
        log(f"    \U0001f4d6 Attempt 1/3: dedicated thorough = {best_words} words", "INFO")
        if best_words >= min_words:
            return best, fallback_count

    # ── Attempt 2: terse directive nudge + 3s VRAM-reload delay. ──
    if deadline_exceeded("dedicated thorough (attempt 2)"):
        log("    \u23f1\ufe0f Skipping thorough attempt 2 (chapter deadline exceeded)", "DEBUG")
    else:
        log(
            "    \u26a0\ufe0f Attempt 1 empty/short — retrying with directive nudge after 3s",
            "DEBUG",
        )
        try:
            import time as _time

            _time.sleep(3)
        except Exception:
            pass
        _nudge = (
            "\n\nWrite the thorough summary NOW. Do not think out loud, do not "
            "explain your plan. Output the <thorough_summary> block immediately. /no_think"
        )
        raw2 = None
        try:
            raw2 = call_llm(
                prompt + _nudge,
                model=primary_model,
                temperature=temperature * 0.5,
                max_tokens=_max_tok,
            )
        except Exception as _e2:
            log(
                f"    \u26a0\ufe0f Attempt 2/3 dedicated thorough crashed "
                f"({type(_e2).__name__}: {_e2}) \u2014 falling through to attempt 3",
                "WARNING",
            )
            logger.warning("dedicated thorough attempt 2 crashed: %s: %s", type(_e2).__name__, _e2)
        t2 = _parse_thorough(raw2)
        if t2:
            _w2 = len(t2.split())
            if _w2 > best_words:
                best, best_words = t2, _w2
                log(f"    \U0001f4d6 Attempt 2/3: dedicated thorough = {_w2} words", "INFO")
            if best_words >= min_words:
                return best, fallback_count

    # ── Attempt 3: greedy decoding (temperature 0.0) — most deterministic. ──
    if deadline_exceeded("dedicated thorough (attempt 3)"):
        log("    \u23f1\ufe0f Skipping thorough attempt 3 (chapter deadline exceeded)", "DEBUG")
    else:
        log(
            "    \u26a0\ufe0f Attempt 2 empty/short — retrying at temperature 0.0 (greedy)", "DEBUG"
        )
        raw3 = None
        try:
            raw3 = call_llm(prompt, model=primary_model, temperature=0.0, max_tokens=_max_tok)
        except Exception as _e3:
            log(
                f"    \u26a0\ufe0f Attempt 3/3 dedicated thorough crashed "
                f"({type(_e3).__name__}: {_e3}) \u2014 falling through to synthetic fallback",
                "WARNING",
            )
            logger.warning("dedicated thorough attempt 3 crashed: %s: %s", type(_e3).__name__, _e3)
        t3 = _parse_thorough(raw3)
        if t3:
            _w3 = len(t3.split())
            if _w3 > best_words:
                best, best_words = t3, _w3
                log(f"    \U0001f4d6 Attempt 3/3: dedicated thorough = {_w3} words", "INFO")

    # ── If we got ANYTHING usable (even < min_words), return it. ──
    if best and best_words > 0:
        if best_words < min_words:
            log(
                f"    \u2139\ufe0f All 3 thorough attempts returned < {min_words} words "
                f"(best={best_words}) — keeping best-effort result",
                "WARNING",
            )
        return best, fallback_count

    # ── Total failure: synthesize a deterministic non-empty thorough. ──
    # Built ONLY from material the model already produced (exec + bullets),
    # so it is guaranteed on-topic and non-empty. This is strictly better
    # than the V18.2.43 silent ``thorough = exec_sum`` fallback (which
    # dropped all bullets) and better than an empty thorough.
    log(
        "    \U0001f9ec V18.2.44: all 3 dedicated thorough attempts failed — "
        "synthesizing deterministic fallback from executive summary + bullets",
        "WARNING",
    )
    _parts: list[str] = []
    if exec_sum and exec_sum.strip():
        _parts.append(exec_sum.strip())
    if bullets:
        _bullet_prose = " ".join(f"\u2022 {b.strip()}." for b in bullets if b and b.strip())
        if _bullet_prose:
            _parts.append(_bullet_prose)
    if _parts:
        _synthetic = "\n\n".join(_parts)
        # V18.4 (Phase 2, Task 5): increment the per-conversion counter
        # and escalate to a louder WARNING at >=2 fires. A single fire is
        # a plausible transient (VRAM eviction mid-generation); >=2 fires
        # in one book conversion indicates the dedicated thorough call is
        # SYSTEMATICALLY failing — almost always a model/config issue
        # (empty Modelfile template, presence_penalty=0 thinking-mode
        # leak, or a quant that can't follow the thorough prompt), not a
        # one-off VRAM blip. Surface the count + a diagnostic hint so the
        # user can act on it (check the Modelfile / presence_penalty /
        # try a different quant) instead of silently degrading every
        # chapter's thorough summary to exec+bullets prose.
        fallback_count += 1
        _count = fallback_count
        if _count >= 2:
            log(
                f"    \u26a0\ufe0f\u26a0\ufe0f V18.4: synthetic-thorough fallback has "
                f"now fired {_count}\u00d7 in this conversion — the dedicated "
                f"thorough LLM call is SYSTEMATICALLY failing (not a "
                f"transient VRAM blip). Likely causes: (1) Modelfile "
                f"template is empty/broken for '{primary_model}', "
                f"(2) presence_penalty=0.0 activating thinking mode "
                f"(should be 1.5 for Instruct), (3) the quant can't follow "
                f"the <thorough_summary> prompt. Diagnostics: check the "
                f"conversion log for 'ThinkingModeViolation' or empty "
                f"responses, verify the Modelfile, and consider a "
                f"different quant. Each fire degrades that chapter's "
                f"thorough to exec+bullets prose (on-topic but not the "
                f"documented 800-1200 word analysis).",
                "WARNING",
            )
        log(
            f"    \u2705 Synthetic thorough fallback: {len(_synthetic.split())} words "
            f"(exec + {len([b for b in bullets if b and b.strip()])} bullets)",
            "INFO",
        )
        return _synthetic, fallback_count
    # Truly nothing to work with — return None (caller keeps exec_sum).
    return None, fallback_count


__all__ = [
    "call_dedicated_thorough_with_fallback",
    "LogCallback",
]
