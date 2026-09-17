"""V18.3.3 (F4): Unified chapter matcher — the single source of truth for
matching user-selected chapter titles against segmented chapters.

Before V18.3.3, the matching logic was duplicated in TWO places with DIFFERENT
rules:
  - Stage 1 (segmentation.py:256-271): loose word-substring matching.
  - Stage 2 (summarization.py:706-720): strict _match_chapter + page fallback.

The inconsistency caused silent failures: Stage 1 kept segments that Stage 2
rejected, and vice versa.

This module provides ONE ``ChapterMatcher`` class used by BOTH stages. It
tries, in order:
  1. **Exact match** (normalized) on heading + aliases.
  2. **Chapter-number match** (e.g. "3.6" matches "3.6").
  3. **Word-overlap match** (V18.3.1 relaxed rule: majority for 3+ words).
  4. **Fuzzy match** (rapidfuzz token_set_ratio >= 95%).
  5. **Page-based match** (if toc_entries available: find the selected
     chapter's TOC page, then find the segment whose [start_page, end_page]
     contains that page — handles renamed chapters like "Chapter 7" → "Part One").

The matcher also:
  - Checks ALL of a segment's headings (primary + aliases) — so merged
    segments are findable by any of their original headings.
  - Skips gap segments (segment_type="gap" or heading starts with "Gap (").
  - Returns a scored list of matches so the caller can pick the best N.

Usage::

    from core.segmentation.chapter_matcher import ChapterMatcher

    matcher = ChapterMatcher(toc_entries=toc_entries)
    matches = matcher.match(selected_titles, chapter_dicts)
    # matches = [(score, chapter_dict), ...] sorted by score descending
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    fuzz = None  # type: ignore


# Common words excluded from significant-word matching.
_COMMON_WORDS = {
    "chapter", "part", "section", "appendix", "the", "of", "a", "an",
    "and", "or", "to", "in", "for", "with", "on", "at", "by", "from",
    "treatment", "acute", "preventive", "prevention", "study",
    "evidence", "trial", "clinical", "practice", "review",
    "introduction", "conclusion", "conclusions", "future",
    "therapeutics", "management", "therapy", "drug", "drugs",
    "migraine", "headache", "pain", "receptor", "antagonist",
    "agonist", "inhibition", "action", "mode", "proposed",
}


def _normalize(s: str) -> str:
    """Normalize a heading for comparison (lowercase, strip punctuation)."""
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _extract_chapter_number(s: str) -> str | None:
    """Extract the chapter number (e.g. "3.6", "2", "1.2.1") from a heading.

    Returns None if the heading doesn't start with a number.
    """
    m = re.match(r'^(\d+(?:\.\d+)*)\s', s)
    if m:
        return m.group(1)
    # Also match "Chapter N" / "Lesson N"
    m = re.match(r'^(?:chapter|lesson|section|part)\s+(\d+(?:\.\d+)*)\b', s, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _significant_words(s: str) -> set:
    """Extract significant words (>2 chars, not in _COMMON_WORDS)."""
    norm = _normalize(s)
    return set(w for w in norm.split() if len(w) > 2 and w not in _COMMON_WORDS)


def _is_gap_segment(heading: str, segment_type: str = "") -> bool:
    """V18.3.3 (F5): True if this is a gap segment (not matchable)."""
    return segment_type == "gap" or heading.strip().lower().startswith("gap (")


def _validate_toc_title(title: str) -> bool:
    """V18.3.3 (F6): True if the TOC title looks valid (not garbage).

    Filters out: empty titles, pure numbers, single characters,
    titles that are just page numbers, etc.
    """
    t = title.strip()
    if not t or len(t) < 3:
        return False
    # Pure number (e.g. "42" — a page number misinterpreted as a heading)
    if re.match(r'^\d+$', t):
        return False
    # Single character + punctuation (e.g. "1." or "a)")
    if len(re.sub(r'[^\w]', '', t)) < 2:
        return False
    return True


class ChapterMatcher:
    """V18.3.3 (F4): Unified chapter matcher used by BOTH Stage 1 + Stage 2.

    Tries heading-text matching first (exact → number → word-overlap → fuzzy),
    then falls back to page-based matching if a TOC is available. Checks ALL
    of a segment's headings (primary + aliases). Skips gap segments.
    """

    def __init__(self, toc_entries: list | None = None):
        """Initialize with optional TOC entries for page-based matching.

        Args:
            toc_entries: list of (title, page) tuples or TOCEntry objects.
                        Used for the page-based fallback.
        """
        self.toc_entries = self._normalize_toc_entries(toc_entries or [])

    @staticmethod
    def _normalize_toc_entries(entries: list) -> list[tuple[str, int]]:
        """V18.3.3 (F6): normalize + validate TOC entries.

        Filters out garbage (pure numbers, single chars, empty titles).
        Returns a list of (title, page) tuples.
        """
        result = []
        for e in entries:
            if hasattr(e, 'title') and hasattr(e, 'page'):
                title, page = e.title, e.page
            elif isinstance(e, (tuple, list)) and len(e) >= 2:
                title, page = e[0], e[1]
            else:
                continue
            if page is None or (isinstance(page, (int, float)) and page <= 0):
                continue
            if not _validate_toc_title(str(title)):
                continue
            result.append((str(title), int(page)))
        return result

    def _match_heading_text(self, heading: str, selected: str) -> tuple[bool, int]:
        """Match a single heading against a selected title.

        Returns (matched, score) where score is:
          3 = exact match (normalized)
          2 = chapter-number match
          1 = word-overlap or fuzzy match
          0 = no match
        """
        heading_norm = _normalize(heading)
        selected_norm = _normalize(selected)

        # 1. Exact match (normalized)
        if heading_norm == selected_norm:
            return True, 3

        # 2. Chapter-number match
        heading_num = _extract_chapter_number(heading)
        selected_num = _extract_chapter_number(selected)
        if heading_num and selected_num:
            if heading_num == selected_num:
                return True, 2
            if heading_num.startswith(selected_num + ".") and len(selected_num) < len(heading_num):
                return True, 2
            return False, 0  # different numbers → definitely not the same

        # 3. Word-overlap match (V18.3.1 relaxed rule)
        heading_words = _significant_words(heading)
        selected_words = _significant_words(selected)
        if heading_words and selected_words:
            overlap = heading_words & selected_words
            if len(selected_words) <= 2:
                if len(overlap) == len(selected_words) and len(selected_words) >= 2:
                    return True, 1
                if len(selected_words) == 1 and overlap == selected_words:
                    return True, 1
            else:
                _threshold = max(3, len(selected_words) // 2)
                if len(overlap) >= _threshold:
                    return True, 1

        # 4. Fuzzy match (95% threshold)
        if _RAPIDFUZZ_AVAILABLE:
            score = fuzz.token_set_ratio(heading_norm, selected_norm)
            if score >= 95:
                return True, 1

        return False, 0

    def _match_segment_heading(self, segment: dict, selected: str) -> tuple[bool, int]:
        """Match a segment against a selected title, checking ALL headings.

        V18.3.3 (F2): checks heading + aliases. Returns the BEST score
        across all headings.
        """
        best_score = 0
        matched = False
        # Check the primary heading
        m, s = self._match_heading_text(segment.get('heading', ''), selected)
        if m and s > best_score:
            matched, best_score = True, s
        # V18.3.3 (F2): check aliases
        for alias in (segment.get('aliases') or []):
            m, s = self._match_heading_text(alias, selected)
            if m and s > best_score:
                matched, best_score = True, s
        return matched, best_score

    def _find_toc_page(self, selected: str) -> int | None:
        """Find the TOC page for a selected chapter title (fuzzy match)."""
        if not self.toc_entries:
            return None
        best_idx, best_score = -1, 0.0
        for idx, (title, page) in enumerate(self.toc_entries):
            if _RAPIDFUZZ_AVAILABLE:
                sc = fuzz.token_set_ratio(selected.lower(), title.lower()) / 100.0
            else:
                sw = set(re.findall(r'[a-z0-9]+', selected.lower()))
                tw = set(re.findall(r'[a-z0-9]+', title.lower()))
                sc = len(sw & tw) / max(len(sw | tw), 1) if (sw or tw) else 0.0
            if sc > best_score:
                best_score, best_idx = sc, idx
        if best_idx >= 0 and best_score >= 0.3:
            return self.toc_entries[best_idx][1]
        return None

    def _match_by_page(self, selected: str, segments: list[dict]) -> dict | None:
        """V18.3.3 (F4): page-based matching — find the segment whose
        [start_page, end_page] contains the selected chapter's TOC page.
        """
        sel_page = self._find_toc_page(selected)
        if sel_page is None:
            return None
        for seg in segments:
            if _is_gap_segment(seg.get('heading', ''), seg.get('segment_type', '')):
                continue
            sp = seg.get('start_page')
            ep = seg.get('end_page')
            if sp is not None and ep is not None and sp <= sel_page <= ep:
                return seg
        return None

    def match(
        self,
        selected_titles: list[str],
        segments: list[dict],
        max_results: int | None = None,
    ) -> list[tuple[int, dict]]:
        """Match selected titles against segments.

        Tries heading-text matching (checking heading + aliases) first.
        If 0 matches, falls back to page-based matching.

        Args:
            selected_titles: the titles the user selected (from the TOC).
            segments: list of chapter dicts with keys: heading, start_page,
                      end_page, aliases (optional), segment_type (optional).
            max_results: if set, return at most this many matches (best first).

        Returns:
            List of (score, segment_dict) tuples, sorted by score descending.
            Empty list if no matches (caller should raise ChapterMatchFailure).
        """
        # Filter out gap segments — they're never matchable
        matchable = [s for s in segments
                     if not _is_gap_segment(s.get('heading', ''), s.get('segment_type', ''))]

        results: list[tuple[int, dict]] = []
        for sel in selected_titles:
            best_score = 0
            best_seg = None
            for seg in matchable:
                matched, score = self._match_segment_heading(seg, sel)
                if matched and score > best_score:
                    best_score = score
                    best_seg = seg
            if best_seg is not None:
                results.append((best_score, best_seg))

        # V18.3.3 (F4): if heading-text matching found 0, try page-based.
        if not results and selected_titles:
            for sel in selected_titles:
                page_seg = self._match_by_page(sel, matchable)
                if page_seg is not None:
                    results.append((1, page_seg))  # score 1 = page-based match

        # Deduplicate by segment identity (a segment may match multiple titles)
        seen = set()
        deduped = []
        for score, seg in results:
            key = id(seg)
            if key not in seen:
                seen.add(key)
                deduped.append((score, seg))

        # Sort by score descending
        deduped.sort(key=lambda x: x[0], reverse=True)

        if max_results is not None:
            deduped = deduped[:max_results]

        return deduped


def filter_toc_entries_for_selection(
    toc_entries: list,
    selected_titles: list[str],
    log=None,
) -> tuple[list, int]:
    """V0.02 (false-success RCA): restrict a TOC entry list to the user's
    chapter selection — used BEFORE segmentation so the segmenter only
    creates segments for chapters the user actually picked.

    Why: with a chapter selection active, the extraction phase only extracts
    the selected chapters' pages — but the segmenter still received the FULL
    TOC. For "97 Things" (198 outline entries, 6 extracted pages) that
    produced ~97 phantom "no marker" segments which Layer-3 then merged into
    the real chapters, contaminating the selection (the user's chapters were
    absorbed into a 'Preface' segment that the content filter then skipped —
    0 summaries, yet the pipeline reported "✅ Conversion complete").

    Matching uses :class:`ChapterMatcher` — the same rules as the
    post-segmentation selection filter (exact → chapter-number → word
    overlap → fuzzy → page), so both stages agree (V18.3.3 F4 principle).

    Args:
        toc_entries: homogeneous list of TOCEntry objects or (heading, page)
            tuples (whatever the caller feeds the Segmenter — elements are
            returned as-is, never rebuilt).
        selected_titles: the user's selected chapter titles.
        log: optional ``log(message, level)`` callback for DEBUG/WARNING
            lines.

    Returns:
        ``(filtered_entries, dropped_count)``. If NO selected title matches
        any entry, returns ``(toc_entries, 0)`` UNCHANGED — the post-
        segmentation filter's "no matches → keep all" fallback remains the
        safety net (never make the pipeline summarize less than it would
        have).
    """

    def _entry_heading(e) -> str:
        return e[0] if isinstance(e, (tuple, list)) else getattr(e, "title", "") or ""

    def _entry_page(e):
        return e[1] if isinstance(e, (tuple, list)) else getattr(e, "page", None)

    if not toc_entries or not selected_titles:
        return toc_entries, 0

    _dbg = (lambda msg: log(msg, "DEBUG")) if log else (lambda msg: None)
    _warn = (lambda msg: log(msg, "WARNING")) if log else (lambda msg: None)

    # Match selected titles against TOC-entry dicts using HEADING-TEXT
    # matching only (exact → chapter-number → word-overlap → fuzzy — the
    # same ladder ``match()`` uses). The PAGE-BASED fallback is deliberately
    # NOT used here: it exists for post-segmentation matching (a selected
    # title whose segment was renamed by merging is found via its TOC page),
    # but pre-segmentation a spurious page match would SHRINK the TOC to a
    # wrong chapter — far worse than not filtering at all.
    matcher = ChapterMatcher()  # no toc_entries → page fallback impossible
    _toc_dicts = []
    for e in toc_entries:
        _p = _entry_page(e)
        _toc_dicts.append({
            "heading": _entry_heading(e),
            "start_page": _p,
            "end_page": _p,
            "aliases": [],
            "segment_type": "chapter",
        })
    _matched_headings: set[str] = set()
    for _sel in selected_titles:
        for _d in _toc_dicts:
            _m, _score = matcher._match_segment_heading(_d, _sel)
            if _m:
                _matched_headings.add(_normalize(_d["heading"]))
    if not _matched_headings:
        _warn(
            "  [Selection] No TOC entries matched the selected chapters — "
            "segmenting the full TOC (post-segmentation filter stays active)."
        )
        return toc_entries, 0

    filtered = [
        e for e in toc_entries
        if _normalize(_entry_heading(e)) in _matched_headings
    ]
    dropped = len(toc_entries) - len(filtered)
    _dbg(
        f"  [Selection] TOC restricted to selection: kept {len(filtered)} "
        f"of {len(toc_entries)} entries ({dropped} unselected dropped before "
        f"segmentation — no phantom segments, no merge contamination)."
    )
    return filtered, dropped
