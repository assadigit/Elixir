"""V0.10 (P6): the adaptive strategy engine — ONE pure decision function.

WHY THIS MODULE EXISTS
──────────────────────
Pre-P6, "does this chapter fit in one call?" was answered FOUR different
ways at four different dispatch sites, and NONE of them looked at the
model's real context window (Task 3-c audit, "DISPATCH"):

  * map-reduce dispatch   — ``src_tokens > 40000``  (``MAP_REDUCE_THRESHOLD``,
    summarizer.py, hardcoded since the V18.11 era)
  * B4 section map-reduce — ``tok_in > b4_threshold`` (default 12000,
    ``summarisation.b4_threshold_tokens``, utils/settings.py:304)
  * chunked-output gate   — ``input > 12000 and output < 14000``
    (primary_call.py, V18.3.5 F1+F3)
  * ``_prepare_text``     — ``ctx - out - 700`` (the truncation safety net)

At the legacy 32k window those thresholds were tuned compromises.  At a
220k window (P5/V0.09 made the context window DATA via ModelRegistry)
they are pure waste: a 100k-token chapter FITS in one call at 220k, yet
the legacy gates would still shred it into 4k-token map-reduce chunks
(25+ LLM calls) or B4 sections (6+ calls).  P6 replaces the four
inconsistent answers with ONE decision that every dispatch site consults.

THE GOVERNING PRINCIPLE (hard constraint from the approved architecture)
──────────────────────────────────────────────────────────────────────
``decide_strategy`` is a PURE function of ``(src_tokens, window,
output_target)``: no I/O, no Settings reads, no LLM calls, no registry
probes — callers pass every value in.  At ``window <= 32768`` it
reproduces the CURRENT hardcoded thresholds EXACTLY so every pre-220k
model keeps byte-identical dispatch behavior (pinned by the parity table
in tests/test_p6_strategy.py).  Adaptive math only activates ABOVE
32768:

  * ``usable = window - output_target - 700 (the _prepare_text margin)
    - 512 (prompt overhead, from context_budget)``
  * ``single_pass``  iff ``src_tokens <= usable``
  * ``map_reduce``   otherwise, with ``map_chunk_tokens =
    clamp(window // 8, 4000, 32000)`` (the 220k rig gets 27,500-token
    chunks — 7x fewer map calls than the legacy 4k)
  * ``b4_sections`` and ``chunked_output`` are DISABLED at large
    windows — their reason for existing (truncation avoidance) vanishes
    when the source fits the window in one call.

``_prepare_text`` itself is NOT rewired (P6 spec B.4): its
``ctx - out - 700`` floor-8000 math stays the final truncation safety
net behind whatever the strategy decides.

IMPORT RULES (P6 constraint): stdlib + ``core.llm.context_budget`` ONLY.
The fit math (``usable`` / chunk size) comes from the P5 budget module
so those numbers live in exactly one place; this module never imports
``core.summarisation.summarizer`` (the legacy threshold VALUES are
re-declared here and parity-pinned by tests, same pattern as
context_budget's ``LEGACY_CHUNK_TOKENS``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.llm.context_budget import (
    LEGACY_WINDOW,
    chunk_size,
    make_budget,
    max_source_tokens,
)

__all__ = [
    "StrategyDecision",
    "decide_strategy",
    "LEGACY_MAP_REDUCE_THRESHOLD",
    "LEGACY_B4_THRESHOLD",
    "LEGACY_CHUNKED_INPUT_THRESHOLD",
    "LEGACY_CHUNKED_OUTPUT_THRESHOLD",
    "LEGACY_MAP_OVERLAP",
]

# ── The legacy thresholds (the CURRENT hardcoded values — parity-pinned) ────
# WHY local constants instead of importing summarizer: (a) the strategy
# module must stay import-clean (stdlib + context_budget only) so it can
# sit at the bottom of the dependency graph; (b) the values are pinned by
# tests/test_p6_strategy.py against the live constants, so drift is caught.

# summarizer.py ``self.MAP_REDUCE_THRESHOLD`` (V18.11 era): map-reduce for
# chapters above 40k SOURCE tokens (pre-_prepare_text count).
LEGACY_MAP_REDUCE_THRESHOLD = 40000
# utils/settings.py ``summarisation.b4_threshold_tokens`` default (V18.2):
# B4 section map-reduce above 12k tokens.
LEGACY_B4_THRESHOLD = 12000
# primary_call.py V18.3.5 (F1+F3) chunked-output gate: split the 5-section
# primary output call in two when the INPUT is above 12k tokens and the
# OUTPUT cap is below 14k.
LEGACY_CHUNKED_INPUT_THRESHOLD = 12000
LEGACY_CHUNKED_OUTPUT_THRESHOLD = 14000
# summarizer.py ``self.MAP_CHUNK_OVERLAP`` — 10% map-chunk overlap.
# Never scaled by the window (overlap exists to keep chunk boundaries
# coherent, which is window-independent).
LEGACY_MAP_OVERLAP = 0.10


@dataclass(frozen=True)
class StrategyDecision:
    """The immutable outcome of one ``decide_strategy`` call.

    Attributes:
        strategy: the dispatch verdict —
            * ``"single_pass"``    — one primary call on the whole chapter;
            * ``"map_reduce"``     — chunk + map + reduce (very large input);
            * ``"b4_sections"``    — section map-reduce (legacy windows only);
            * ``"chunked_output"`` — split the OUTPUT call in two (legacy
              windows only; the runtime thermal guard still applies inside
              primary_call).
        map_chunk_tokens: the map-reduce chunk size (in tokens) for this
            window — EXACTLY 4000 at legacy windows (``MAP_CHUNK_TOKENS``
            parity), ``clamp(window // 8, 4000, 32000)`` above.  Consumed
            only by the map-reduce path.
        overlap: the map-chunk overlap fraction (0.10, never scaled).
        reason: human-readable WHY (shown in the per-chapter INFO log) —
            includes the deciding numbers (thresholds at legacy windows,
            the usable-budget arithmetic at adaptive ones).
    """

    strategy: Literal["single_pass", "map_reduce", "b4_sections", "chunked_output"]
    map_chunk_tokens: int
    overlap: float
    reason: str


def decide_strategy(
    src_tokens: int,
    window: int,
    output_target: int,
    *,
    b4_threshold: int | None = None,
    map_reduce_threshold: int | None = None,
) -> StrategyDecision:
    """Decide how one chapter is summarized — PURE, no I/O.

    Args:
        src_tokens: the chapter's source token count (tiktoken;
            ``utils.token_counter.count_tokens`` / ``context_budget``).
        window: the EFFECTIVE context window (the live
            ``request.summarisation_max_context_tokens`` AFTER the P5
            registry raise — never a hardcoded default).
        output_target: the output token budget (the live
            ``request.summarisation_max_output_tokens``).
        b4_threshold: the settings-driven B4 threshold
            (``summarisation.b4_threshold_tokens``, default 12000).  Kept a
            parameter so the settings value keeps flowing through
            UNCHANGED at legacy windows — this function never reads
            Settings itself.
        map_reduce_threshold: the map-reduce threshold (the Summarizer's
            ``MAP_REDUCE_THRESHOLD`` constant, default 40000).  Same
            pass-through rationale.

    Returns:
        A frozen :class:`StrategyDecision`.

    Raises:
        ValueError: if ``window <= 0`` (via ``context_budget.make_budget``).

    LEGACY PARITY (window <= 32768) — the dispatch cascade in priority
    order, byte-identical to the pre-P6 code:

        1. ``map_reduce``      iff ``src_tokens > map_reduce_threshold`` (40000)
        2. ``b4_sections``     iff ``src_tokens > b4_threshold`` (12000)
        3. ``chunked_output``  iff ``src_tokens > 12000 and output_target < 14000``
        4. ``single_pass``     otherwise

    (The real pipeline checks B4 on the POST-``_prepare_text`` token count
    and the chunked gate inside ``summarize_with_model`` with a thermal
    guard — the wiring passes those live counts here; the cascade order is
    what this function pins.)

    ADAPTIVE (window > 32768): ``single_pass`` iff the source fits the
    usable budget, else ``map_reduce`` with a window-scaled chunk; B4 and
    chunked-output are disabled (a chapter that fits has no truncation to
    recover from).
    """
    b4_thr = LEGACY_B4_THRESHOLD if b4_threshold is None else int(b4_threshold)
    mr_thr = (
        LEGACY_MAP_REDUCE_THRESHOLD if map_reduce_threshold is None else int(map_reduce_threshold)
    )
    # The P5 budget object owns the fit arithmetic (margin 700 + overhead
    # 512 + output reserve) and the chunk-scaling rule, so the numbers
    # live in exactly one module.
    budget = make_budget(int(window), int(output_target))
    chunk = chunk_size(budget)  # 4000 at legacy windows; clamp(window//8, 4000, 32000) above
    overlap = LEGACY_MAP_OVERLAP

    if int(window) <= LEGACY_WINDOW:
        # ── LEGACY cascade (byte-identical thresholds) ──────────────────
        if src_tokens > mr_thr:
            return StrategyDecision(
                strategy="map_reduce",
                map_chunk_tokens=chunk,
                overlap=overlap,
                reason=(
                    f"legacy window {window:,} <= {LEGACY_WINDOW:,}: "
                    f"src {src_tokens:,} > map_reduce_threshold {mr_thr:,}"
                ),
            )
        if src_tokens > b4_thr:
            return StrategyDecision(
                strategy="b4_sections",
                map_chunk_tokens=chunk,
                overlap=overlap,
                reason=(
                    f"legacy window {window:,} <= {LEGACY_WINDOW:,}: "
                    f"src {src_tokens:,} > b4_threshold {b4_thr:,}"
                ),
            )
        if (
            src_tokens > LEGACY_CHUNKED_INPUT_THRESHOLD
            and output_target < LEGACY_CHUNKED_OUTPUT_THRESHOLD
        ):
            return StrategyDecision(
                strategy="chunked_output",
                map_chunk_tokens=chunk,
                overlap=overlap,
                reason=(
                    f"legacy window {window:,} <= {LEGACY_WINDOW:,}: "
                    f"src {src_tokens:,} > {LEGACY_CHUNKED_INPUT_THRESHOLD:,} "
                    f"and output {output_target:,} < {LEGACY_CHUNKED_OUTPUT_THRESHOLD:,}"
                ),
            )
        return StrategyDecision(
            strategy="single_pass",
            map_chunk_tokens=chunk,
            overlap=overlap,
            reason=(
                f"legacy window {window:,} <= {LEGACY_WINDOW:,}: "
                f"src {src_tokens:,} within legacy thresholds "
                f"(map_reduce {mr_thr:,} / b4 {b4_thr:,} / chunked {LEGACY_CHUNKED_INPUT_THRESHOLD:,})"
            ),
        )

    # ── ADAPTIVE math (window > 32768) ───────────────────────────────────
    usable = max_source_tokens(budget)  # window - output_target - 700 - 512
    if src_tokens <= usable:
        return StrategyDecision(
            strategy="single_pass",
            map_chunk_tokens=chunk,
            overlap=overlap,
            reason=(
                f"adaptive window {window:,} > {LEGACY_WINDOW:,}: "
                f"src {src_tokens:,} <= usable {usable:,} "
                f"(window - output {output_target:,} - margin {budget.margin} "
                f"- overhead {budget.prompt_overhead})"
            ),
        )
    return StrategyDecision(
        strategy="map_reduce",
        map_chunk_tokens=chunk,
        overlap=overlap,
        reason=(
            f"adaptive window {window:,} > {LEGACY_WINDOW:,}: "
            f"src {src_tokens:,} > usable {usable:,} "
            f"(window - output {output_target:,} - margin {budget.margin} "
            f"- overhead {budget.prompt_overhead})"
        ),
    )
