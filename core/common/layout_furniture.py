"""V0.5.20 — the page-furniture line shapes (the layout-independent joins).

The V0.5.19.1 rig run #2 (the FULL-BOOK ingestion, run
``20260928-155851-011587f0`` — ``audit/results/bench_v0519_1_ch9_histrionic_schizotypal_rig2/``)
proved the V0.5.19/.1 continuation joins extraction-LAYOUT-fragile: the same
source content, extracted from the 397-page PDF with a different pagination,
broke the paragraph-adjacency heuristics (the six-grounds list
regressed to 5/6, a dangling ``and (4).`` marker shipped, a criteria item
truncated mid-phrase, and both reproduced schizotypal criteria blocks were
prefix-truncated at extraction layout boundaries).

One of the layouts' shared failure modes: a PAGE BOUNDARY inserts furniture
lines into the extracted text — a bare page-number line (``224``) or a
short ALL-CAPS running-header line (the book/chapter title repeated at the
top of every page). These lines are not content, but every structure
heuristic that walks lines/paragraphs (the enumeration join, the criteria
cluster collector) treats them as prose and derails:

* the enumeration join sees the furniture PARAGRAPH between the list and
  its continuation and never considers the pair (the V0.4.24 join is
  adjacent-pairs only);
* the criteria cluster collector sees the furniture LINE between two
  sub-items as a prose line and CLOSES the cluster (an uppercase/digit
  start is not a lowercase continuation) — the remaining sub-items arrive
  with no parent letter and are skipped (the 5/8 + 3/9 schizotypal
  prefix-truncations).

This module holds the ONE shared shape test (``is_page_furniture_line`` +
``is_furniture_paragraph``), used by both join sites so the furniture
definition can never drift between them.

Shape-based only (Rule 1 ✓ — no book content):

1. a BARE PAGE NUMBER — a line whose stripped content is 1-4 digits
   (optionally wrapped in quotes/brackets or trailing punctuation —
   extractors emit ``224``, ``- 224 -``, ``"224"``, ``224.``).
   A digits-only line is never English item text.
2. a SHORT MULTI-TOKEN ALL-CAPS RUNNING HEADER — ≤ 60 chars, ≥ 2
   whitespace-separated tokens, NO lowercase letters, no sentence-terminal
   punctuation (``THE BOOK TITLE``, ``CHAPTER NINE``, ``PART TWO THE
   SECTION HEADING``). A single-token all-caps line is
   deliberately NOT furniture (``DSM-III`` mid-item is a legitimate
   hard-wrapped fragment — only multi-token title shapes qualify).

Fail-closed by design: anything ambiguous is NOT furniture (the callers
only ever SKIP furniture lines — a false furniture verdict would drop
content from an item, so the test must be conservative).
"""

from __future__ import annotations

import re

__all__ = ["is_page_furniture_line", "is_furniture_paragraph"]

# 1-4 digits, optionally wrapped in quotes/brackets/dashes, optionally
# followed by sentence punctuation (extractor variance).
_BARE_PAGE_NUMBER_RE = re.compile(
    r"^[\s\"'\u2018\u2019\u201c\u201d([{<\u2013\u2014-]*"  # optional opening furniture
    r"\d{1,4}"
    r"[\s\"'.,;:!?\u2018\u2019\u201c\u201d)\]}> \u2013\u2014-]*$"  # optional closing/punct
)

# Multi-token ALL-CAPS running header: letters/digits/spaces/hyphens/quotes,
# >= 2 tokens, no lowercase, no sentence-terminal punctuation.
_ALL_CAPS_HEADER_RE = re.compile(r"^[A-Z0-9 '\u2019\u2013\u2014.,-]+$")
_TERMINAL_PUNCT = ".!?…" + "\u201d"


def is_page_furniture_line(line: str) -> bool:
    """V0.5.20: True when a line is page furniture (a bare page number or a
    short multi-token ALL-CAPS running header), not content.

    Conservative: ambiguous shapes return False (a false positive would
    drop content; a false negative only costs a missed join — the callers
    skip furniture lines, never keep them as content).
    """
    s = (line or "").strip()
    if not s or len(s) > 60:
        return False
    if _BARE_PAGE_NUMBER_RE.match(s):
        return True
    # multi-token ALL-CAPS header: no lowercase letters anywhere, >= 2
    # tokens, and NOT sentence-terminated (a real prose line in caps ends
    # like a sentence; a running header does not).
    if _ALL_CAPS_HEADER_RE.match(s) and s[-1] not in _TERMINAL_PUNCT:
        tokens = s.split()
        if len(tokens) >= 2 and sum(1 for ch in s if ch.isalpha()) >= 4:
            return True
    return False


def is_furniture_paragraph(para_text: str, max_lines: int = 2) -> bool:
    """V0.5.20: True when a WHOLE paragraph (≤ ``max_lines`` non-blank
    lines) is nothing but page furniture — the between-paragraphs shape
    the enumeration join must look PAST to find a list's continuation on
    the far side of a page boundary."""
    lines = [ln for ln in (para_text or "").split("\n") if ln.strip()]
    if not lines or len(lines) > max_lines:
        return False
    return all(is_page_furniture_line(ln) for ln in lines)
