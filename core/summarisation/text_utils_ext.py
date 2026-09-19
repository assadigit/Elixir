"""V18.11 (Phase 5 Stage 3, Batch 1.1): Smart-truncation text utility.

Extracted verbatim from ``Summarizer._smart_truncate`` (god-class
decomposition Stage 3). This is a paragraph-aware truncation that keeps the
first/last paragraph as anchors, scores the middle paragraphs by information
density, and greedily fills the middle budget with the highest-scoring
paragraphs (preserving original order).

**Extraction map**:

| Summarizer method (old) | text_utils_ext function (new) | self deps                  |
|------------------------|-------------------------------|----------------------------|
| ``_smart_truncate``     | ``smart_truncate``            | ``log`` (single call)      |

The method was almost pure — only ONE ``self`` reference (a single ``self.log``
call at the end to report the token reduction). All other dependencies
(``count_tokens``, ``truncate_by_tokens`` from ``utils.token_counter`` and
``re``) are module-level imports, not ``self`` attributes. The extraction is a
mechanical move: ``self.log(...)`` → ``log(...)`` with ``_noop_log`` default.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object
like the failed ``PromptContext``). This matches the proven Phase 4 + Phase 5
pattern (``post_processing.py``, ``summary_validator.py``, ``llm_dispatcher.py``
— 8 consecutive golden-master runs at 9/10, 0 hallucinations).

Characterization tests: ``tests/test_text_utils_ext.py`` captures canned
inputs → golden outputs. Byte-for-byte stability gate (the log callback is
injected, so the returned truncated string is deterministic).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from utils.token_counter import count_tokens, truncate_by_tokens

# Type alias for the duck-typed log callback (matches summary_validator convention).
LogCallback = Callable[[str, str], None]


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── smart_truncate (extracted verbatim from Summarizer._smart_truncate) ────


def smart_truncate(
    text: str,
    max_tokens: int,
    *,
    log: LogCallback | None = None,
) -> str:
    """Paragraph-aware truncation that keeps anchor paragraphs + dense middle.

    Extracted verbatim from ``Summarizer._smart_truncate``. The only change is
    ``self.log(...)`` → ``log(...)`` (with ``_noop_log`` default). All logic —
    the anchor/tail/middle budget split, the STOPWORDS set, the inner ``score``
    function, the greedy fill, the "[… content omitted …]" gap markers — is
    byte-for-byte identical to the V18.10.1 source.

    Behaviour:
    - If the text has ≤3 paragraphs, falls back to plain token truncation.
    - Otherwise: keep the first ``max_tokens/5`` tokens as the anchor, the last
      ``max_tokens/5`` as the tail, and fill the middle with the highest-
      information-density paragraphs (scored by content-word ratio + entity /
      number / quote boosts) up to ``max_tokens - anchor - tail - 50`` tokens.
    - Oversized middle paragraphs are truncated instead of skipped (H5 fix).
    - Gaps between non-adjacent kept paragraphs are marked with
      "[… content omitted …]".
    """
    log = log or _noop_log
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 3:
        return truncate_by_tokens(text, max_tokens=max_tokens, add_ellipsis=True)

    anchor_budget = max_tokens // 5
    tail_budget = max_tokens // 5
    middle_budget = max_tokens - anchor_budget - tail_budget - 50

    anchor_parts, used = [], 0
    for p in paragraphs:
        t = count_tokens(p)
        if used + t > anchor_budget:
            break
        anchor_parts.append(p)
        used += t
    if not anchor_parts:
        anchor_parts = [
            truncate_by_tokens(paragraphs[0], max_tokens=anchor_budget, add_ellipsis=False)
        ]

    tail_parts, used = [], 0
    for p in reversed(paragraphs):
        t = count_tokens(p)
        if used + t > tail_budget:
            break
        tail_parts.insert(0, p)
        used += t
    if not tail_parts:
        tail_parts = [
            truncate_by_tokens(paragraphs[-1], max_tokens=tail_budget, add_ellipsis=False)
        ]

    anchor_set = {id(p) for p in anchor_parts}
    tail_set = {id(p) for p in tail_parts}
    middle_paras = [
        (i, p)
        for i, p in enumerate(paragraphs)
        if id(p) not in anchor_set and id(p) not in tail_set
    ]

    STOPWORDS = {
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "but",
        "is",
        "it",
        "its",
        "this",
        "that",
        "was",
        "are",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "with",
        "from",
        "by",
        "as",
        "not",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "their",
        "our",
        "his",
        "her",
        "which",
        "who",
        "what",
        "when",
        "where",
        "how",
        "all",
        "one",
        "two",
        "three",
        "also",
        "can",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "do",
        "did",
    }

    def score(p: str) -> float:
        """H5 fix: score paragraphs by information density, not just
        content-word ratio.  Keep dialogue/quotes/conclusions (which the
        old scorer dropped because they have many stopwords/pronouns).
        """
        words = re.findall(r"\b[a-z]{3,}\b", p.lower())
        if not words:
            return 0.0
        content = [w for w in words if w not in STOPWORDS]
        content_ratio = len(content) / len(words)
        # Boost paragraphs with named entities (Capitalized words),
        # numbers, or quotation marks — these carry key claims.
        has_entity = bool(re.search(r"\b[A-Z][a-z]{2,}", p))
        has_number = bool(re.search(r"\b\d+%?\b", p))
        has_quote = '"' in p or '"' in p or '"' in p
        boost = 0.15 * (has_entity + has_number + has_quote)
        # Penalise only clearly-filler paragraphs (very short, no verbs)
        if len(words) < 5 and not has_number:
            return 0.0
        return content_ratio + boost

    scored = sorted(middle_paras, key=lambda x: score(x[1]), reverse=True)
    selected, used = [], 0
    for orig_idx, p in scored:
        t = count_tokens(p)
        if used + t > middle_budget:
            # H5 fix: truncate oversized paragraphs instead of skipping
            if t > middle_budget:
                p = truncate_by_tokens(p, max_tokens=middle_budget - used, add_ellipsis=True)
                t = count_tokens(p)
            else:
                continue
        selected.append((orig_idx, p))
        used += t
        if used >= middle_budget * 0.95:
            break

    selected.sort(key=lambda x: x[0])
    parts = anchor_parts[:]
    prev_idx = -1
    for orig_idx, p in selected:
        if prev_idx >= 0 and orig_idx > prev_idx + 1:
            parts.append("[… content omitted …]")
        parts.append(p)
        prev_idx = orig_idx
    parts.append("[… content omitted …]")
    parts += tail_parts

    result = "\n\n".join(parts)
    log(
        f"    \U0001f50d Smart truncation: {count_tokens(text):,} \u2192 {count_tokens(result):,} tokens",
        "INFO",
    )
    return result


__all__ = [
    "smart_truncate",
    "LogCallback",
]
