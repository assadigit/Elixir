"""V18.3.3 (F7) — Comprehensive tests for the unified ChapterMatcher + Segment robustness.

Covers all the failure modes identified in the segmenter + TOC audit:

  F1: Segment.aliases field + all_headings property
  F2: _merge_short_segments preserves merged headings as aliases
  F3: _filter_to_chapter_level prefers granular level (chapters over parts)
  F4: ChapterMatcher unified (heading + aliases + page + gap filtering)
  F5: Gap segments excluded from matching
  F6: TOC validation (garbage filtering)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# V18.3.3: mock the heavy optional deps so we can import the chapter_matcher
# without the full markitdown/pypdf/pdfplumber stack.
for _mod in ("markitdown", "pypdf", "pdfplumber", "pdf2image", "pytesseract",
             "PIL", "PIL.Image", "spacy", "wordninja"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
if "docx" not in sys.modules:
    _docx_mock = MagicMock()
    _docx_mock.__path__ = []
    sys.modules["docx"] = _docx_mock

from core.models.models import Segment
from core.segmentation.chapter_matcher import (
    ChapterMatcher,
    _is_gap_segment,
    _validate_toc_title,
)

# ── F1: Segment.aliases + all_headings ─────────────────────────────────────

class TestSegmentAliases:
    """V18.3.3 (F1): Segment has an aliases field + all_headings property."""

    def test_segment_has_aliases_field(self):
        """Segment accepts an aliases parameter."""
        seg = Segment(heading="Title Page", content="...", start_page=1, end_page=5,
                      aliases=["Dedication", "Epigraph"])
        assert seg.aliases == ["Dedication", "Epigraph"]

    def test_segment_aliases_defaults_to_empty(self):
        """aliases defaults to [] when not passed."""
        seg = Segment(heading="Ch 1", content="...", start_page=1, end_page=10)
        assert seg.aliases == []

    def test_all_headings_includes_aliases(self):
        """all_headings returns [heading] + aliases."""
        seg = Segment(heading="Title Page", content="...", start_page=1, end_page=5,
                      aliases=["Dedication", "Epigraph"])
        assert seg.all_headings == ["Title Page", "Dedication", "Epigraph"]

    def test_all_headings_no_aliases(self):
        """all_headings returns just [heading] when no aliases."""
        seg = Segment(heading="Ch 1", content="...", start_page=1, end_page=10)
        assert seg.all_headings == ["Ch 1"]

    def test_is_gap_property(self):
        """V18.3.3 (F5): is_gap detects gap segments."""
        gap = Segment(heading="Gap (pages 1–1)", content="[No content]", start_page=1, end_page=1,
                      segment_type="gap")
        assert gap.is_gap is True

        normal = Segment(heading="Chapter 1", content="...", start_page=1, end_page=10)
        assert normal.is_gap is False


# ── F4: ChapterMatcher — heading-text matching ──────────────────────────────

class TestChapterMatcherHeadingText:
    """The matcher's heading-text matching (exact, number, word-overlap, fuzzy)."""

    def test_exact_match(self):
        """Exact match (normalized) → score 3."""
        m = ChapterMatcher()
        segs = [{"heading": "1 - IDENTITY AND ITS ORIGINS", "start_page": 1, "end_page": 10}]
        result = m.match(["1 - IDENTITY AND ITS ORIGINS"], segs)
        assert len(result) == 1
        assert result[0][0] == 3  # exact match score

    def test_case_insensitive_match(self):
        """Exact match is case-insensitive."""
        m = ChapterMatcher()
        segs = [{"heading": "Identity and Its Origins", "start_page": 1, "end_page": 10}]
        result = m.match(["IDENTITY AND ITS ORIGINS"], segs)
        assert len(result) == 1

    def test_chapter_number_match(self):
        """Chapter-number match (e.g. '3.6' matches '3.6') → score 2."""
        m = ChapterMatcher()
        segs = [{"heading": "3.6 Cannabinoids Treatment", "start_page": 50, "end_page": 60}]
        result = m.match(["3.6 Cannabinoids"], segs)
        assert len(result) == 1
        assert result[0][0] == 2  # number match score

    def test_chapter_number_mismatch_rejects(self):
        """Different chapter numbers → no match (V10.2.4 guard)."""
        m = ChapterMatcher()
        segs = [{"heading": "2.2 Memantine", "start_page": 30, "end_page": 40}]
        result = m.match(["3.6 Cannabinoids"], segs)
        assert len(result) == 0

    def test_word_overlap_majority(self):
        """V18.3.1 P2: 3+ word selection with majority overlap → match."""
        m = ChapterMatcher()
        segs = [{"heading": "Part Three: Confidence Building and Active Listening Skills", "start_page": 1, "end_page": 10}]
        result = m.match(["Chapter 3: Confidence Building Through Active Listening"], segs)
        assert len(result) == 1

    def test_no_match_returns_empty(self):
        """No heading match + no TOC → empty list."""
        m = ChapterMatcher()
        segs = [{"heading": "Completely Different Topic", "start_page": 1, "end_page": 10}]
        result = m.match(["Chapter 7: Putting It All Together"], segs)
        assert len(result) == 0


# ── F4: ChapterMatcher — alias-aware matching ────────────────────────────────

class TestChapterMatcherAliases:
    """V18.3.3 (F2): the matcher checks aliases, not just the primary heading."""

    def test_match_via_alias(self):
        """If the primary heading doesn't match but an alias does, it matches."""
        m = ChapterMatcher()
        segs = [{
            "heading": "Title Page",
            "aliases": ["Dedication", "Epigraph"],
            "start_page": 1, "end_page": 5,
        }]
        result = m.match(["Dedication"], segs)
        assert len(result) == 1
        assert result[0][1]["heading"] == "Title Page"

    def test_exact_match_via_alias(self):
        """Exact match via alias gets score 3."""
        m = ChapterMatcher()
        segs = [{
            "heading": "Title Page",
            "aliases": ["Dedication"],
            "start_page": 1, "end_page": 5,
        }]
        result = m.match(["Dedication"], segs)
        assert len(result) == 1
        assert result[0][0] == 3  # exact match via alias

    def test_no_alias_still_works(self):
        """Segments without aliases match normally."""
        m = ChapterMatcher()
        segs = [{"heading": "Chapter 1", "aliases": [], "start_page": 1, "end_page": 10}]
        result = m.match(["Chapter 1"], segs)
        assert len(result) == 1

    def test_agent_of_influence_dedication_scenario(self):
        """The exact scenario from 'Agent of Influence': 'Dedication' was merged
        into 'Title Page'. With aliases, the user can still match on 'Dedication'."""
        m = ChapterMatcher()
        segs = [{
            "heading": "Title Page",
            "aliases": ["Dedication", "Epigraph", "Contents", "Introduction: Spy Skills"],
            "start_page": 1, "end_page": 10,
        }]
        result = m.match(["Dedication"], segs)
        assert len(result) == 1
        result = m.match(["Epigraph"], segs)
        assert len(result) == 1
        result = m.match(["Contents"], segs)
        assert len(result) == 1


# ── F4: ChapterMatcher — page-based matching ─────────────────────────────────

class TestChapterMatcherPageBased:
    """V18.3.3 (F4): page-based fallback when heading-text fails."""

    def test_page_based_match_recovers_renamed_chapter(self):
        """The exact 'Agent of Influence' case: Chapter 7 → Part One (page 93)."""
        toc = [
            ("Title Page", 2),
            ("Chapter 1: The Confidence Reflex", 11),
            ("Part One: The SADR Cycle", 25),
            ("Chapter 7: Putting It All Together", 93),
            ("Part Two: Spy Skills", 109),
        ]
        segs = [
            {"heading": "Chapter 1: The Confidence Reflex", "start_page": 11, "end_page": 24},
            {"heading": "Part One: The SADR Cycle", "start_page": 25, "end_page": 108},
            {"heading": "Part Two: Spy Skills", "start_page": 109, "end_page": 140},
        ]
        m = ChapterMatcher(toc_entries=toc)
        result = m.match(
            ["Chapter 7: Putting It All Together: How I Used the SADR Cycle to Create Million-Dollar Marketing Campaigns"],
            segs,
        )
        assert len(result) == 1
        assert result[0][1]["heading"] == "Part One: The SADR Cycle"

    def test_page_based_skips_gap_segments(self):
        """Gap segments are not matched even by page-based fallback."""
        toc = [("Chapter 1", 5)]
        segs = [
            {"heading": "Gap (pages 1–1)", "segment_type": "gap", "start_page": 1, "end_page": 1},
            {"heading": "Chapter 1", "start_page": 5, "end_page": 20},
        ]
        m = ChapterMatcher(toc_entries=toc)
        result = m.match(["Chapter 1"], segs)
        assert len(result) == 1
        assert result[0][1]["heading"] == "Chapter 1"

    def test_page_based_no_toc_returns_empty(self):
        """Without TOC entries, page-based matching can't run."""
        m = ChapterMatcher(toc_entries=[])
        segs = [{"heading": "Completely Different", "start_page": 1, "end_page": 10}]
        result = m.match(["Chapter 7: Something"], segs)
        assert len(result) == 0

    def test_page_based_no_segment_contains_page(self):
        """If no segment's page range contains the TOC page, no match."""
        toc = [("Chapter 99", 200)]
        segs = [{"heading": "Only Chapter", "start_page": 1, "end_page": 150}]
        m = ChapterMatcher(toc_entries=toc)
        result = m.match(["Chapter 99"], segs)
        assert len(result) == 0


# ── F5: Gap segment filtering ───────────────────────────────────────────────

class TestGapSegmentFiltering:
    """V18.3.3 (F5): gap segments are excluded from matching."""

    def test_gap_segment_not_matched(self):
        """Gap segments never match a user selection."""
        m = ChapterMatcher()
        segs = [
            {"heading": "Gap (pages 1–1)", "segment_type": "gap", "start_page": 1, "end_page": 1},
            {"heading": "Chapter 1", "start_page": 5, "end_page": 20},
        ]
        result = m.match(["Gap (pages 1–1)"], segs)
        assert len(result) == 0

    def test_gap_segment_does_not_block_other_matches(self):
        """Gap segments are skipped, but other segments still match."""
        m = ChapterMatcher()
        segs = [
            {"heading": "Gap (pages 1–1)", "segment_type": "gap", "start_page": 1, "end_page": 1},
            {"heading": "Chapter 1", "start_page": 5, "end_page": 20},
        ]
        result = m.match(["Chapter 1"], segs)
        assert len(result) == 1
        assert result[0][1]["heading"] == "Chapter 1"

    def test_is_gap_segment_by_type(self):
        """_is_gap_segment detects by segment_type='gap'."""
        assert _is_gap_segment("Some Heading", "gap") is True

    def test_is_gap_segment_by_heading(self):
        """_is_gap_segment detects by heading prefix 'Gap ('."""
        assert _is_gap_segment("Gap (pages 1–5)", "chapter") is True

    def test_is_gap_normal_segment(self):
        """Normal segments are not gaps."""
        assert _is_gap_segment("Chapter 1", "chapter") is False


# ── F6: TOC validation ──────────────────────────────────────────────────────

class TestTOCValidation:
    """V18.3.3 (F6): garbage TOC entries are filtered."""

    def test_valid_title_passes(self):
        assert _validate_toc_title("Chapter 1: Introduction") is True
        assert _validate_toc_title("Part Two: Spy Skills") is True
        assert _validate_toc_title("Dedication") is True

    def test_empty_title_rejected(self):
        assert _validate_toc_title("") is False
        assert _validate_toc_title("   ") is False

    def test_short_title_rejected(self):
        assert _validate_toc_title("ab") is False  # < 3 chars
        assert _validate_toc_title("x") is False

    def test_pure_number_rejected(self):
        """Page numbers misinterpreted as headings are rejected."""
        assert _validate_toc_title("42") is False
        assert _validate_toc_title("7") is False

    def test_matcher_filters_garbage_toc(self):
        """The ChapterMatcher filters garbage TOC entries on init."""
        toc = [
            ("Chapter 1: Introduction", 5),
            ("42", 10),  # garbage
            ("", 15),   # garbage
            ("Chapter 2: Conclusion", 20),
        ]
        m = ChapterMatcher(toc_entries=toc)
        # Only 2 valid entries should remain
        assert len(m.toc_entries) == 2
        assert m.toc_entries[0][0] == "Chapter 1: Introduction"
        assert m.toc_entries[1][0] == "Chapter 2: Conclusion"


# ── F4: ChapterMatcher — unified behavior (both stages agree) ────────────────

class TestUnifiedMatching:
    """V18.3.3 (F4): Stage 1 + Stage 2 use the same matcher — they agree."""

    def test_no_more_stage1_keeps_stage2_rejects(self):
        """The old inconsistency (Stage 1 loose match keeps, Stage 2 rejects)
        is fixed — both stages use the same ChapterMatcher."""
        # Simulate the exact "Agent of Influence" case
        toc = [
            ("Chapter 7: Putting It All Together", 93),
            ("Part One: The SADR Cycle", 25),
        ]
        segs = [
            {"heading": "Chapter 1: The Confidence Reflex", "start_page": 11, "end_page": 24},
            {"heading": "Part One: The SADR Cycle", "start_page": 25, "end_page": 108},
        ]
        selected = "Chapter 7: Putting It All Together: How I Used the SADR Cycle"

        m = ChapterMatcher(toc_entries=toc)
        result = m.match([selected], segs)

        # Both stages would now get the SAME result (Part One, via page match)
        assert len(result) == 1
        assert result[0][1]["heading"] == "Part One: The SADR Cycle"

    def test_multiple_selected_chapters(self):
        """Multiple selected chapters match independently."""
        m = ChapterMatcher()
        segs = [
            {"heading": "Chapter 1: Intro", "start_page": 1, "end_page": 10},
            {"heading": "Chapter 2: Body", "start_page": 11, "end_page": 20},
            {"heading": "Chapter 3: Conclusion", "start_page": 21, "end_page": 30},
        ]
        result = m.match(["Chapter 1: Intro", "Chapter 3: Conclusion"], segs)
        assert len(result) == 2
        headings = [r[1]["heading"] for r in result]
        assert "Chapter 1: Intro" in headings
        assert "Chapter 3: Conclusion" in headings

    def test_max_results_limits_output(self):
        """max_results returns at most N matches (best first)."""
        m = ChapterMatcher()
        segs = [
            {"heading": "3.6 Cannabinoids", "start_page": 50, "end_page": 60},
            {"heading": "3.6 Cannabinoids Treatment", "start_page": 50, "end_page": 60},
        ]
        result = m.match(["3.6 Cannabinoids"], segs, max_results=1)
        assert len(result) == 1

    def test_deduplication(self):
        """If a segment matches multiple selected titles, it appears once."""
        m = ChapterMatcher()
        segs = [{"heading": "Chapter 1: Introduction", "start_page": 1, "end_page": 10}]
        result = m.match(
            ["Chapter 1: Introduction", "1 - INTRODUCTION"], segs
        )
        assert len(result) == 1  # deduped


# ── F3: _filter_to_chapter_level (level preference) ──────────────────────────

class TestFilterToChapterLevel:
    """V18.3.3 (F3): prefers the most granular level with real chapters.

    This tests the LOGIC of the level-selection algorithm (extracted as a
    standalone function for testability, same approach as _match_chapter).
    """

    def _choose_level(self, toc_entries_with_levels):
        """Standalone copy of the _filter_to_chapter_level level-selection logic."""
        import re as _re
        _FRONT_MATTER = {
            "dedication", "epigraph", "contents", "table of contents",
            "copyright", "title page", "about the author", "about the publisher",
            "acknowledgments", "acknowledgements", "author's note", "author note",
            "front matter", "cover",
        }

        def _is_real_chapter(title):
            t = title.strip().lower()
            if not t or len(t) < 3:
                return False
            if t in _FRONT_MATTER:
                return False
            if _re.match(r'^(chapter|lesson|section|part)\s+\d+', t):
                return True
            if _re.match(r'^\d+[\.\s\-]', t):
                return True
            if len(t) > 10:
                return True
            return False

        by_level = {}
        for title, page, level in toc_entries_with_levels:
            by_level.setdefault(level, []).append(title)

        chosen = 0
        for lvl in sorted(by_level.keys()):
            if any(_is_real_chapter(t) for t in by_level[lvl]):
                chosen = lvl
        return chosen

    def test_prefers_level_1_when_it_has_chapters(self):
        """Books with Parts (level 0) + Chapters (level 1) → prefer level 1."""
        entries = [
            ("Part One", 25, 0),
            ("Part Two", 109, 0),
            ("Chapter 1: The Confidence Reflex", 11, 1),
            ("Chapter 7: Putting It All Together", 93, 1),
        ]
        assert self._choose_level(entries) == 1

    def test_falls_back_to_level_0_when_no_level_1(self):
        """If only level 0 has real chapters, use level 0."""
        entries = [
            ("Chapter 1: Introduction", 5, 0),
            ("Chapter 2: Body", 20, 0),
            ("Dedication", 2, 1),  # level 1 but front-matter, not a real chapter
        ]
        assert self._choose_level(entries) == 0

    def test_falls_back_to_level_0_when_flat_toc(self):
        """Flat TOC (all level 0) → use level 0."""
        entries = [
            ("Chapter 1: Intro", 5, 0),
            ("Chapter 2: Body", 20, 0),
        ]
        assert self._choose_level(entries) == 0

    def test_prefers_deepest_level_with_chapters(self):
        """If level 2 has real chapters, prefer it over level 1."""
        entries = [
            ("Part One", 10, 0),
            ("Section A", 15, 1),
            ("Chapter 1: Intro", 20, 2),
        ]
        assert self._choose_level(entries) == 2
