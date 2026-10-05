"""V18.11 (Phase 5 Stage 3, Batch 2.4): Batched self-review.

Extracted verbatim from ``Summarizer._self_review_batched`` (god-class
decomposition Stage 3). Reviews bullets in chunks of 10 against the source
text, collecting all verdicts into a merged JSON array.

**Extraction map**:

| Summarizer method (old) | self_review function (new) | self deps |
|------------------------|---------------------------|-----------|
| ``_self_review_batched`` | ``self_review_batched``   | ``primary_model``, ``log``, ``request.summarisation_max_context_tokens``, ``prompt_manager``, ``_recover_vram``, ``_call_llm``, ``temperature``, ``_strip_thinking`` |

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).

Characterization tests: ``tests/test_self_review.py`` captures the batched
review flow with mocked ``call_llm`` / ``prompt_manager`` / ``recover_vram``.
"""

from __future__ import annotations

import json as _json
import logging
import re as _re
from collections.abc import Callable
from typing import Any

# V18.20.2.0 (SWOT A5): shared Qwen-family /no_think injection for the
# direct call_llm site below (bypasses _call_llm_with_empty_retry's
# V18.2.41 injection). Import is safe — filter_thinking has no dependency
# on this module (no import cycle).
from core.summarisation.filter_thinking import qwen_no_think

# Type aliases (duck-typed).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
CallLlmFn = Callable[..., str | None]
RecoverVramFn = Callable[..., None]
StripThinkingFn = Callable[[str], str]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── self_review_batched (extracted verbatim) ───────────────────────────────


def self_review_batched(
    heading: str,
    text: str,
    bullets: list,
    thorough: str,
    *,
    primary_model: str,
    max_context_tokens: int,
    temperature: float,
    prompt_manager: PromptManagerLike,
    recover_vram: RecoverVramFn,
    call_llm: CallLlmFn,
    strip_thinking: StripThinkingFn,
    log: LogCallback | None = None,
) -> str | None:
    """V13.45.4: Batched self-review — reviews bullets in chunks of 10.

    Extracted verbatim from ``Summarizer._self_review_batched``. The only
    changes are ``self.X`` → named parameters. The batch-of-10 splitting, the
    global-index numbering, the per-batch VRAM recovery (30s delay from
    V15.1.0), the JSON-array verdict extraction, and the merged-result return
    are byte-for-byte identical.

    The user explicitly requested: "Instead of skipping self-review, chunk
    them and partially review them, like in 5 x 10 batches. Skipping hurts
    quality/accuracy. Time is the second priority."

    This method:
    1. Splits bullets into batches of 10
    2. Sends each batch + the full source to the LLM for fact-checking
    3. Collects all verdicts into a single merged JSON array
    4. Returns the merged result (same format as _self_review)

    Each batch is a separate LLM call (~1-2 min per batch with Gemma 4).
    With 100 bullets → 10 batches → ~15-20 min total (vs 20 min wasted on
    2 timeouts that produced nothing).

    VRAM recovery: a 30s delay between batches prevents GPU exhaustion
    (V15.1.0: increased from 5s after V15.0.2 batch-6 crash).

    NOTE: the ``thorough`` parameter is part of the method signature for
    call-site compatibility but is NOT used in the body (kept verbatim).
    """
    log = log or _noop_log
    # V0.6.14 (single-model order): the heavy-model reviewer is retired —
    # THE model reviews its own output.
    review_model = primary_model
    if not review_model:
        log("    \u23ed\ufe0f Batched self\u2011review skipped (no model available).", "INFO")
        return None

    # Truncate source to fit context window (same as _self_review)
    max_src = max(max_context_tokens - 2000, 8000)
    src_text = text[: max_src * 4]

    # Split bullets into batches of 10
    BATCH_SIZE = 10
    batches = [bullets[i : i + BATCH_SIZE] for i in range(0, len(bullets), BATCH_SIZE)]
    log(
        f"    \U0001f52c Batched self-review: {len(bullets)} bullets \u2192 {len(batches)} batch(es) of {BATCH_SIZE}",
        "INFO",
    )

    all_verdicts = []
    for batch_idx, batch in enumerate(batches):
        batch_start_idx = batch_idx * BATCH_SIZE
        # Number the bullets with their GLOBAL index (so the caller can
        # map verdicts back to the original bullet list)
        numbered_bullets = "\n".join(
            f"{batch_start_idx + i + 1}. {bp}" for i, bp in enumerate(batch)
        )

        prompt = prompt_manager.render_template(
            "summarisation/self_review_batched",
            heading=heading,
            src_text=src_text,
            numbered_bullets=numbered_bullets,
            batch_index=batch_idx + 1,
            batch_count=len(batches),
            batch_size=len(batch),
            batch_start_index=batch_start_idx + 1,
        )

        log(
            f"    \U0001f52c Batch {batch_idx + 1}/{len(batches)}: reviewing claims {batch_start_idx + 1}-{batch_start_idx + len(batch)}\u2026",
            "DEBUG",
        )

        # V15.1.0: Increased VRAM recovery from 5s → 30s (from V15.0.3).
        # Batches use the SAME model (gemma4-12b, ~9.3 GB VRAM) with the SAME
        # 32K context as B4/B3 calls — the VRAM footprint is identical. 5s was
        # insufficient and caused a crash on batch 6 in V15.0.2.
        if batch_idx > 0:
            recover_vram(context=f"self-review-batch-{batch_idx + 1}", delay_sec=30.0)

        try:
            # V18.20.2.0 (SWOT A5): inject /no_think for Qwen-family models —
            # this is a direct call_llm site (no empty-retry wrapper).
            raw = call_llm(
                qwen_no_think(prompt, review_model),
                model=review_model,
                temperature=temperature,
            )
            if not raw:
                log(f"    \u26a0\ufe0f Batch {batch_idx + 1} returned empty — skipping", "WARNING")
                continue
            raw = strip_thinking(raw)

            json_match = _re.search(r"(\[.*\])", raw, _re.DOTALL)
            if json_match:
                try:
                    batch_verdicts = _json.loads(json_match.group(0))
                    if isinstance(batch_verdicts, list):
                        all_verdicts.extend(batch_verdicts)
                        unsupported = sum(
                            1
                            for v in batch_verdicts
                            if v.get("verdict") in ("unsupported", "partially_supported")
                        )
                        log(
                            f"    \u2705 Batch {batch_idx + 1}: {len(batch_verdicts)} claims reviewed, "
                            f"{unsupported} flagged",
                            "DEBUG",
                        )
                except _json.JSONDecodeError:
                    log(
                        f"    \u26a0\ufe0f Batch {batch_idx + 1} JSON parse failed — skipping",
                        "WARNING",
                    )
            else:
                log(f"    \u26a0\ufe0f Batch {batch_idx + 1} no JSON found — skipping", "WARNING")
        except Exception as e:
            log(f"    \u26a0\ufe0f Batch {batch_idx + 1} failed: {e}", "WARNING")
            logger.debug("batch %d failed: %s", batch_idx + 1, e)

    if not all_verdicts:
        log("    \u26a0\ufe0f Batched self-review produced no verdicts", "WARNING")
        return None

    # Return as JSON array string (same format as _self_review)
    log(
        f"    \u2705 Batched self-review complete: {len(all_verdicts)} claims reviewed across {len(batches)} batches",
        "INFO",
    )
    return _json.dumps(all_verdicts)


__all__ = [
    "self_review_batched",
    "LogCallback",
]
