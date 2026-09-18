"""V0.09 (P5): tokenizer-aware context budget math.

WHY THIS MODULE EXISTS
──────────────────────
Pre-P5, the provider layer estimated prompt size with ``len(text) // 4``
(a 4-chars-per-token heuristic) at every fit decision:
``OllamaProvider._adaptive_context``, ``LlamaCppProvider.fit_max_tokens``.
That heuristic over-counts repetitive text by ~2x (tiktoken merges runs
like ``"xxxx"`` into single tokens — a 240,000-char wall of ``x`` is only
~30,000 cl100k tokens) and under-counts CJK/emoji.  The app ALREADY ships
a tiktoken-based counter (``utils.token_counter.count_tokens``, cl100k_base
with a words*4//3 fallback) that the segmentation/map-reduce/_prepare_text
paths use — the provider path just never adopted it.  P5 (Mission-4
"context as data") centralizes the fit math here so P6 can drive every
strategy threshold (MAP_REDUCE_THRESHOLD 40000 / b4 12000 / chunk 12000 /
MAP_CHUNK_TOKENS 4000) from ONE budget object instead of 4 inconsistent
inline checks (see the Task 3-c audit: ""Does it fit?" is answered 4x
inconsistently").

32K LEGACY PARITY (the hard constraint)
───────────────────────────────────────
At the default window (32768) with the default reserve (8192) the budget
reproduces the load-bearing legacy numbers EXACTLY:

  - ``chunk_size`` == 4000 — the legacy ``MAP_CHUNK_TOKENS``
    (summarizer.py:523).  Windows <= 32768 NEVER scale the chunk.
  - ``max_source_tokens`` == 32768 - 8192 - 512 - 700 == 23364 — the
    ``_prepare_text``-style source budget (ctx - out - margin).  The
    legacy ``_prepare_text`` (summarizer.py) computes ``ctx - out - 700``
    (23876 at 32k) with NO prompt_overhead term; this module's extra 512
    is a slightly more conservative reserve for the prompt scaffold
    (instructions + XML contract), adopted deliberately so P6's switchover
    can never OVERFLOW where the legacy code fit.  (``_prepare_text`` is
    NOT rewired in P5 — its behavior is unchanged until P6.)

IMPORT RULES (P5 constraint): this module imports ONLY from ``utils/`` and
the stdlib — never ``core.summarisation`` / ``core.system`` — so it can sit
at the bottom of the dependency graph and be consumed by every layer.
"""

from __future__ import annotations

from dataclasses import dataclass

# V0.09 (P5): thin re-export so provider-layer call sites have ONE import
# for all token math (and tests can pin that the provider path no longer
# uses chars//4). utils.token_counter is tiktoken cl100k_base with a
# words*4//3 fallback when tiktoken is unavailable.
from utils.token_counter import count_tokens  # noqa: F401 — re-export per spec

__all__ = [
    "ContextBudget",
    "make_budget",
    "count_tokens",
    "fits",
    "max_source_tokens",
    "chunk_size",
]

# ── The four load-bearing constants ─────────────────────────────────────────
# LEGACY_CHUNK_TOKENS (summarizer.MAP_CHUNK_TOKENS == 4000): map-reduce chunk
# size at every window <= 32768 (i.e. every pre-P5 configuration).  Kept as a
# local constant (NOT imported from summarizer) so this module never imports
# core.summarisation — the value is pinned by characterization tests.
LEGACY_CHUNK_TOKENS = 4000
# The window at/under which the legacy 4000-token chunk is preserved exactly.
LEGACY_WINDOW = 32768
# Prompt scaffold overhead: instructions + output-contract XML + system
# preamble that ride along with the source text in the real prompt.
PROMPT_OVERHEAD_TOKENS = 512
# The legacy _prepare_text safety margin (summarizer.py: "ctx - out - 700").
# Kept as the default margin so 32k parity is byte-identical.
DEFAULT_MARGIN_TOKENS = 700
# Default output reserve at large windows; matches the user's max_output
# rule for Ollama models (Task 8 decision #1).
DEFAULT_OUTPUT_RESERVE = 8192
# Chunk-scaling bounds for windows ABOVE the legacy 32k (P6 will consume
# these; e.g. the 220k model gets 220000//8 = 27500-token map chunks).
MIN_CHUNK_TOKENS = 4000
MAX_CHUNK_TOKENS = 32000


@dataclass(frozen=True)
class ContextBudget:
    """The token arithmetic for one (window, output-reserve) pair.

    Attributes:
        window: the EFFECTIVE context window (registry-resolved, already
            capped — see ``core.llm.registry.get_context_window``).
        output_reserve: tokens reserved for the model's answer.
        prompt_overhead: tokens reserved for the prompt scaffold around the
            source text (instructions + XML contract).
        margin: the legacy safety margin (700) — never spent.
    """

    window: int
    output_reserve: int
    prompt_overhead: int = PROMPT_OVERHEAD_TOKENS
    margin: int = DEFAULT_MARGIN_TOKENS


def make_budget(window: int, output_reserve: int | None = None) -> ContextBudget:
    """Build a :class:`ContextBudget` for ``window``.

    ``output_reserve`` defaults to ``min(8192, window // 4)`` — the user's
    Task-8 rule #1 (8192 max output for Ollama-class models), scaled down
    for small windows so a 8k window doesn't reserve its entire self for
    output.  At the default 32768 window this is exactly 8192, matching the
    legacy max_output used throughout the 32k era.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window!r}")
    if output_reserve is None:
        reserve = min(DEFAULT_OUTPUT_RESERVE, int(window) // 4)
    else:
        reserve = int(output_reserve)
    return ContextBudget(
        window=int(window),
        output_reserve=reserve,
        prompt_overhead=PROMPT_OVERHEAD_TOKENS,
        margin=DEFAULT_MARGIN_TOKENS,
    )


def fits(src_tokens: int, budget: ContextBudget) -> bool:
    """Can a ``src_tokens``-token source fit in ``budget`` in ONE call?

    ``src_tokens + prompt_overhead + output_reserve <= window - margin``
    — all values are TOKEN counts (never chars; use :func:`count_tokens`
    to convert).
    """
    return (
        src_tokens + budget.prompt_overhead + budget.output_reserve <= budget.window - budget.margin
    )


def max_source_tokens(budget: ContextBudget) -> int:
    """The largest single-call source (in tokens) that fits ``budget``.

    32k parity pin: ``(32768, 8192)`` → ``32768 - 8192 - 512 - 700 = 23364``.
    """
    return budget.window - budget.margin - budget.prompt_overhead - budget.output_reserve


def chunk_size(budget: ContextBudget, strategy: str = "map_reduce") -> int:
    """The map-reduce chunk size (in tokens) for ``budget``'s window.

    LEGACY PARITY: at ``window <= 32768`` this is EXACTLY 4000 — the
    hardcoded ``MAP_CHUNK_TOKENS`` every pre-P5 run used.  Larger windows
    scale as ``window // 8`` clamped to [4000, 32000] (the 220k model gets
    27500-token chunks — the "no map-reduce for 40k-token chapters at 220k
    window" adaptation P6 drives).

    ``strategy`` is accepted for forward-compatibility (P6's strategy
    engine passes its name); every strategy currently shares the
    map-reduce chunk rule.
    """
    _ = strategy  # reserved for P6 per-strategy chunk rules
    if budget.window <= LEGACY_WINDOW:
        return LEGACY_CHUNK_TOKENS
    scaled = budget.window // 8
    return max(MIN_CHUNK_TOKENS, min(MAX_CHUNK_TOKENS, scaled))
