"""Phase 2 (Test-Net Deepening) — hermetic tests for the parsing/validation half
of ``core/pdf/toc_extractor.py``.

Covers (all via direct method calls on the real TocExtractor — pure logic,
no I/O unless stated):

* the 7 rule-based TOC parsers (single_line, multiline, three_line,
  column_layout, numbered_sections, headings_only, roman_numerals),
* parser scoring (incl. the sequential-chapter-number penalty),
* adaptive offset detection & correction,
* validate_and_correct (chapter-number sequences, clamping, anchoring),
* locate_headings (marker windows, page estimation, global fallbacks),
* _build_marker_map, _find_toc_page, _looks_like_body.

Plus a few extract()-level edge cases that need real PDFs: footer-only
entries, empty OCR yield, and the page-labels exception branch.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import fitz
import pytest

from core.models import TOCResult
from core.pdf.toc_extractor import TocExtractor


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    ``test_chapter_matcher_robust`` (and friends) install MagicMock stubs for
    heavy optional deps (pypdf/pytesseract/pdf2image/...) at collection time
    and never remove them; collection is alphabetical, so those stubs are
    already in place when this file is imported and would silently poison the
    real-PdfReader / Tesseract-fallback paths exercised below. Real modules
    are ``types.ModuleType`` instances — MagicMocks are not — so drop them
    and let the late import below resolve the real installed package.
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pypdf")
_ensure_real_module("pytesseract")
_ensure_real_module("pdf2image")
_ensure_real_module("PIL")  # real pypdf probes PIL.__version__ at import
from pypdf import PdfReader  # noqa: E402 — after stub cleanup

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


class _StubSettings:
    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}

    def get(self, path, default=None):
        return self.overrides.get(path, default)


def _make_extractor(adaptive: bool = False) -> tuple[TocExtractor, list[tuple[str, str]]]:
    logs: list[tuple[str, str]] = []
    ex = TocExtractor(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
    ex._settings = _StubSettings()
    ex._adaptive_enabled = adaptive
    ex._llm_model = "test-model:latest"
    ex._ollama_base_url = "http://localhost:11434"
    return ex, logs


def _write_pdf(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


# ────────────────────────────────────────────────────────────────────────────
# 1. Rule-based parsers (direct)
# ────────────────────────────────────────────────────────────────────────────


class TestParseSingleLine:
    def test_dotted_leader_variant(self):
        ex, _ = _make_extractor()
        entries = ex._parse_single_line(["Introduction ......... 5"], 10)
        assert entries == [("Introduction", 5)]

    def test_tab_variant(self):
        ex, _ = _make_extractor()
        assert ex._parse_single_line(["Introduction\t\t5"], 10) == [("Introduction", 5)]

    def test_wide_space_variant(self):
        ex, _ = _make_extractor()
        assert ex._parse_single_line(["A Sufficiently Long Title   12"], 20) == [
            ("A Sufficiently Long Title", 12)
        ]

    def test_narrow_space_variant_requires_long_title(self):
        ex, _ = _make_extractor()
        assert ex._parse_single_line(["Another Long Title 7"], 20) == [("Another Long Title", 7)]
        # titles shorter than 12 chars need 3+ spaces or leaders
        assert ex._parse_single_line(["Short 7"], 20) == []

    def test_noise_and_toc_headers_skipped(self):
        ex, _ = _make_extractor()
        lines = ["Table of Contents", "Contents", "page 4", "12", "iv", "ab 3", ""]
        assert ex._parse_single_line(lines, 20) == []

    def test_short_heading_and_page_range_filtered(self):
        ex, _ = _make_extractor()
        # NOTE: "ab ......... 3" is rejected by the dotted pattern (heading
        # < 3 chars) but the narrow-space pattern then matches it with the
        # leader dots kept in the heading — characterized as-is.
        lines = ["ab ......... 3", "Good Title Here ......... 999", "Good Title Here ......... 4"]
        assert ex._parse_single_line(lines, 10) == [
            ("ab .........", 3),
            ("Good Title Here", 4),
        ]

    def test_duplicates_removed_and_sorted_by_page(self):
        ex, _ = _make_extractor()
        lines = [
            "Beta Title ......... 8",
            "Alpha Title ......... 2",
            "Beta Title ......... 8",
            "Alpha Title ......... 2",
        ]
        assert ex._parse_single_line(lines, 10) == [("Alpha Title", 2), ("Beta Title", 8)]


class TestParseMultiline:
    def test_chapter_heading_then_page_number(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 1", "", "3", "Chapter 2", "", "7"]
        assert ex._parse_multiline(lines, 10) == [("Chapter 1", 3), ("Chapter 2", 7)]

    def test_non_chapter_like_skipped(self):
        ex, _ = _make_extractor()
        assert ex._parse_multiline(["Just Some Title", "", "4"], 10) == []
        # word-numbered ("Chapter One") is NOT chapter-like for this parser
        assert ex._parse_multiline(["Chapter One", "", "4"], 10) == []

    def test_single_word_chapter_like_skipped(self):
        ex, _ = _make_extractor()
        assert ex._parse_multiline(["Appendix", "", "4"], 10) == []

    def test_page_out_of_range_skipped(self):
        ex, _ = _make_extractor()
        assert ex._parse_multiline(["Chapter 1", "", "99"], 10) == []

    def test_next_line_must_be_bare_number(self):
        ex, _ = _make_extractor()
        assert ex._parse_multiline(["Chapter 1", "", "page 4"], 10) == []

    def test_heading_at_end_without_page_skipped(self):
        ex, _ = _make_extractor()
        assert ex._parse_multiline(["Chapter 1", "Chapter 2"], 10) == []


class TestParseColumnLayout:
    # NOTE (reported, not fixed): _parse_column_layout is dead-on-arrival in
    # the pipeline — the class-level NOISE pattern (^(\d{1,4}\s*$)) filters
    # standalone page-number lines BEFORE the parser's own bare-number branch
    # can collect them, so `pages` is always empty and the parser always
    # returns []. These tests characterise that reality.

    def test_interleaved_headings_and_pages_collect_nothing(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 1", "3", "Chapter 2", "7"]
        assert ex._parse_column_layout(lines, 10) == []

    def test_headings_and_pages_never_balanced(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 1"] + ["3", "4", "5", "6", "7", "8"]
        assert ex._parse_column_layout(lines, 10) == []

    def test_pages_only_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_column_layout(["3", "7", "9"], 10) == []

    def test_headings_only_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_column_layout(["Chapter One", "Chapter Two"], 10) == []

    def test_noise_headers_not_treated_as_headings(self):
        ex, _ = _make_extractor()
        assert ex._parse_column_layout(["Contents", "3"], 10) == []


class TestParseThreeLine:
    def test_heading_blank_then_number(self):
        ex, logs = _make_extractor()
        lines = ["Some Heading Title", "", "5"]
        assert ex._parse_three_line(lines, 10) == [("Some Heading Title", 5)]
        assert any("three-line" in m for _, m in logs)

    def test_noise_previous_line_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_three_line(["page", "", "5"], 10) == []

    def test_numeric_previous_line_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_three_line(["42", "", "5"], 10) == []

    def test_short_previous_line_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_three_line(["abc", "", "5"], 10) == []

    def test_page_out_of_range_rejected(self):
        ex, _ = _make_extractor()
        assert ex._parse_three_line(["Some Heading Title", "", "99"], 10) == []

    def test_first_line_number_ignored(self):
        ex, _ = _make_extractor()
        assert ex._parse_three_line(["5"], 10) == []


class TestParseNumberedSections:
    def test_trailing_page_number(self):
        ex, logs = _make_extractor()
        entries = ex._parse_numbered_sections(["1 - First Topic 3"], 10)
        assert entries == [("1 - First Topic 3", 3)]
        assert any("numbered sections" in m for _, m in logs)

    def test_page_number_on_next_line(self):
        ex, _ = _make_extractor()
        assert ex._parse_numbered_sections(["2 - Second Topic", "5"], 10) == [
            ("2 - Second Topic", 5)
        ]

    def test_standalone_page_pool_fallback(self):
        ex, _ = _make_extractor()
        lines = ["3", "7", "2 - Second Topic", "1 - First Topic"]
        assert ex._parse_numbered_sections(lines, 10) == [
            ("2 - Second Topic", 3),
            ("1 - First Topic", 7),
        ]

    def test_no_page_available_keeps_zero(self):
        ex, _ = _make_extractor()
        assert ex._parse_numbered_sections(["4 - Fourth Topic"], 10) == [("4 - Fourth Topic", 0)]

    def test_duplicates_removed(self):
        ex, _ = _make_extractor()
        assert ex._parse_numbered_sections(["1 - Topic", "3", "1 - Topic", "3"], 10) == [
            ("1 - Topic", 3)
        ]


class TestParseHeadingsOnly:
    def test_pending_flushed_by_blank_line_with_embedded_number(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 1", ""]
        assert ex._parse_headings_only(lines, 10) == [("Chapter 1", 1)]

    def test_pending_flushed_by_toc_header(self):
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 2", "Contents"], 10) == [("Chapter 2", 2)]

    # NOTE (reported, not fixed): the bare-number flush branch (lines with
    # only "\d{1,4}") is DEAD — the class NOISE pattern matches those lines
    # first, so the flush always runs via the noise path and uses the FIRST
    # number embedded in the pending heading as the page.

    def test_bare_number_line_flushes_via_noise_path(self):
        ex, _ = _make_extractor()
        # "6" is NOISE -> flush uses the embedded "3" as the page
        assert ex._parse_headings_only(["Chapter 3", "6"], 10) == [("Chapter 3", 3)]

    def test_out_of_range_number_still_uses_embedded_page(self):
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 4", "99"], 10) == [("Chapter 4", 4)]

    def test_chapter_like_transition_flushes_previous(self):
        ex, _ = _make_extractor()
        lines = ["1. First Section 2", "2. Second Section 4"]
        assert ex._parse_headings_only(lines, 10) == [
            ("1. First Section 2", 1),
            ("2. Second Section 4", 2),
        ]

    def test_continuation_words_merged_into_pending(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 5", "extra continuation words", "3"]
        # trailing "3" is NOISE -> flush uses the embedded "5"
        assert ex._parse_headings_only(lines, 10) == [("Chapter 5 extra continuation words", 5)]

    def test_section_starters_not_merged(self):
        # "Index of the book" is a section-starter: it neither merges into the
        # pending heading nor starts a new pending — only "Chapter Six" lands.
        ex, _ = _make_extractor()
        lines = ["Chapter 6", "Index of the book", "4"]
        assert ex._parse_headings_only(lines, 10) == [("Chapter 6", 6)]

    def test_all_caps_continuation_not_merged(self):
        ex, _ = _make_extractor()
        lines = ["Chapter 7", "ALL CAPS TEXT", "5"]
        assert ex._parse_headings_only(lines, 10) == [("Chapter 7", 7)]

    def test_embedded_page_out_of_range_becomes_zero(self):
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 99", ""], 10) == [("Chapter 99", 0)]

    def test_transition_flush_out_of_range_page_becomes_zero(self):
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 99", "Chapter 1"], 10) == [
            ("Chapter 99", 0),
            ("Chapter 1", 1),
        ]

    def test_final_flush_out_of_range_page_becomes_zero(self):
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 99"], 10) == [("Chapter 99", 0)]

    def test_duplicate_pending_headings_deduplicated(self):
        # the transition flush and the final flush see the same heading
        ex, _ = _make_extractor()
        assert ex._parse_headings_only(["Chapter 1 x", "Chapter 1 x"], 10) == [("Chapter 1 x", 1)]

    def test_final_pending_flushed_at_end(self):
        ex, _ = _make_extractor()
        # final flush uses the FIRST embedded number as the page
        assert ex._parse_headings_only(["Chapter 8 7"], 10) == [("Chapter 8 7", 8)]

    def test_numbered_section_lines_become_pending(self):
        ex, _ = _make_extractor()
        # NUMBERED_SECTION match: "3 - Third" starts a new pending
        lines = ["Chapter 9", "3 - Third Topic", "8"]
        assert ex._parse_headings_only(lines, 10) == [("Chapter 9", 9), ("3 - Third Topic", 3)]


class TestRomanNumerals:
    def test_roman_to_int(self):
        ex, _ = _make_extractor()
        assert ex._roman_to_int("I") == 1
        assert ex._roman_to_int("IV") == 4
        assert ex._roman_to_int("ix") == 9
        assert ex._roman_to_int("MCMXCIV") == 1994
        assert ex._roman_to_int("Z") == 0  # unknown chars contribute 0

    def test_map_roman_page(self):
        ex, _ = _make_extractor()
        assert ex._map_roman_page("IV") == 4
        assert ex._map_roman_page("") == 0
        assert ex._map_roman_page("ii", ["i", "ii", "iii", "iv"]) == 2  # via labels
        assert ex._map_roman_page("IV", ["i", "ii", "iii", "iv"]) == 4

    def test_parse_roman_numerals_basic(self):
        ex, logs = _make_extractor()
        lines = ["I. First Heading", "II. Second Heading", "III. Third Heading"]
        assert ex._parse_roman_numerals(lines, 10) == [
            ("First Heading", 1),
            ("Second Heading", 2),
            ("Third Heading", 3),
        ]
        assert any("Roman numeral parser" in m for _, m in logs)

    def test_parse_roman_out_of_range_becomes_zero(self):
        ex, logs = _make_extractor()
        entries = ex._parse_roman_numerals(["X. Big Range Header"], 5)
        assert entries == [("Big Range Header", 0)]
        assert any("treating as chapter number" in m for _, m in logs)

    def test_parse_roman_skips_noise_and_short_lines(self):
        ex, _ = _make_extractor()
        lines = ["I", "IV", "Contents", "ab", "V. Real Heading Here"]
        assert ex._parse_roman_numerals(lines, 10) == [("Real Heading Here", 5)]

    def test_map_roman_page_guard_returns_zero_on_conversion_error(self, monkeypatch):
        # Fault injection on the except-guard contract (lines 601-604): the
        # real ``_roman_to_int`` never raises on ``[IVXLCDM]+`` input (regex
        # pre-validated), so this branch is defensive-only — if the converter
        # ever malfunctions, the mapper must degrade to page 0, not propagate.
        ex, _ = _make_extractor()

        def _boom(roman):
            raise ValueError("corrupt numeral")

        monkeypatch.setattr(ex, "_roman_to_int", _boom)
        assert ex._map_roman_page("IV") == 0

    def test_parse_roman_skips_entry_mapping_to_page_zero(self, monkeypatch):
        # Guard contract (line 636): a roman numeral that maps to page 0
        # (unmappable) is skipped via ``continue`` instead of being emitted
        # with a bogus page. Reachable today only through a misbehaving
        # ``_map_roman_page`` (see test above) — direct injection keeps this
        # honest without pretending a real input triggers it.
        ex, _ = _make_extractor()

        def _map(roman, labels=None):
            return 0 if roman.strip().upper() == "I" else 2

        monkeypatch.setattr(ex, "_map_roman_page", _map)
        lines = ["I. Ghost Heading", "II. Real Heading"]
        assert ex._parse_roman_numerals(lines, 10) == [("Real Heading", 2)]


# ────────────────────────────────────────────────────────────────────────────
# 2. Scoring
# ────────────────────────────────────────────────────────────────────────────


class TestScoreParserResult:
    def test_empty_entries_score_zero(self):
        ex, _ = _make_extractor()
        assert ex._score_parser_result([], 10) == 0.0

    def test_sequential_chapter_numbers_penalised(self):
        ex, logs = _make_extractor()
        entries = [("Chapter One", 1), ("Chapter Two", 2), ("Chapter Three", 3)]
        score = ex._score_parser_result(entries, 150)
        # base 80 * 0.7 = 56, bonus min(20, 3/2.5) = 1.2
        assert score == pytest.approx(57.2)
        assert any("sequential chapter numbers" in m for _, m in logs)

    def test_non_sequential_full_score(self):
        ex, _ = _make_extractor()
        entries = [("Chapter One", 1), ("Chapter Two", 5), ("Chapter Three", 9)]
        score = ex._score_parser_result(entries, 150)
        assert score == pytest.approx(81.2)

    def test_invalid_pages_reduce_ratio(self):
        ex, _ = _make_extractor()
        entries = [("Good", 1), ("Bad", 999)]
        assert ex._score_parser_result(entries, 10) == pytest.approx(40.0)

    def test_bonus_capped_at_100(self):
        ex, _ = _make_extractor()
        entries = [(f"Chapter {i}", i + 1) for i in range(60)]
        assert ex._score_parser_result(entries, 100) == 100.0


class TestChapterNumberSequence:
    def test_empty_is_false(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([], 100) is False

    def test_small_document_is_false(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([1, 2, 3], 50) is False

    def test_large_page_number_is_false(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([1, 2, 40], 100) is False

    def test_non_sequential_is_false(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([1, 3, 5], 100) is False

    def test_first_number_too_large_is_false(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([7, 8, 9], 100) is False

    def test_real_sequence_is_true(self):
        ex, _ = _make_extractor()
        assert ex._is_likely_chapter_number_sequence([1, 2, 3, 4], 100) is True


# ────────────────────────────────────────────────────────────────────────────
# 3. validate_and_correct + adaptive offset correction
# ────────────────────────────────────────────────────────────────────────────


def _offset_markdown() -> tuple[str, list[tuple[int, int]]]:
    """3-page markdown with plain 'Chapter N' headings.

    Returns (markdown, page_markers) where markers are (page, char_pos).
    """
    pages = {
        1: "Chapter One\nbody text one",
        2: "Chapter Two\nbody text two",
        3: "Chapter Three\nbody text three",
        4: "plain body four",
        5: "plain body five",
    }
    parts = []
    markers = []
    pos = 0
    for page, text in pages.items():
        marker_line = f"<!-- original page {page} -->"
        part = marker_line + "\n" + text
        markers.append((page, pos))
        parts.append(part)
        pos += len(part) + 2  # "\n\n" join
    return "\n\n".join(parts), markers


class TestValidateAndCorrect:
    def test_empty_entries(self):
        ex, _ = _make_extractor()
        assert ex.validate_and_correct([], 10) == []

    def test_no_positive_pages_returns_unchanged(self):
        ex, _ = _make_extractor()
        entries = [("A", 0), ("B", -1)]
        assert ex.validate_and_correct(entries, 10) == entries

    def test_chapter_number_sequence_zeroed(self):
        ex, logs = _make_extractor()
        entries = [("Chapter One", 1), ("Chapter Two", 2), ("Chapter Three", 3)]
        result = ex.validate_and_correct(entries, 100)
        assert result == [("Chapter One", 0), ("Chapter Two", 0), ("Chapter Three", 0)]
        assert any("chapter numbers" in m for _, m in logs)

    def test_out_of_range_pages_clamped(self):
        ex, logs = _make_extractor()
        entries = [("Low", 0), ("High", 99)]
        assert ex.validate_and_correct(entries, 10) == [("Low", 1), ("High", 10)]
        assert any("out of range" in m for _, m in logs)

    def test_uniform_offset_corrected(self):
        ex, logs = _make_extractor()
        md, markers = _offset_markdown()
        # every TOC page is +1 off the actual page
        entries = [("Chapter One", 2), ("Chapter Two", 3), ("Chapter Three", 4)]
        result = ex.validate_and_correct(entries, 10, markdown_text=md, page_markers=markers)
        assert result == [("Chapter One", 1), ("Chapter Two", 2), ("Chapter Three", 3)]
        assert any("Adaptive offset correction applied" in m for _, m in logs)

    def test_heading_anchored_to_markdown_page(self):
        ex, logs = _make_extractor()
        md, markers = _offset_markdown_with_hashes()
        # page 9 is within range for a 10-page doc but wrong; the heading only
        # exists on page 1 -> anchoring corrects it.
        entries = [("Chapter One", 9), ("Chapter Two", 9), ("Chapter Three", 9)]
        result = ex.validate_and_correct(entries, 10, markdown_text=md, page_markers=markers)
        assert result == [("Chapter One", 1), ("Chapter Two", 2), ("Chapter Three", 3)]
        assert any("Anchored" in m for _, m in logs)

    def test_zero_pages_are_clamped_then_anchored(self):
        # page 0 is clamped to 1 by the range check; the ghost heading cannot
        # be anchored so it keeps the clamped page.
        ex, _ = _make_extractor()
        md, markers = _offset_markdown_with_hashes()
        entries = [("Ghost", 0), ("Chapter One", 1), ("Chapter Two", 2)]
        result = ex.validate_and_correct(entries, 10, markdown_text=md, page_markers=markers)
        assert result == [("Ghost", 1), ("Chapter One", 1), ("Chapter Two", 2)]


def _offset_markdown_with_hashes() -> tuple[str, list[tuple[int, int]]]:
    pages = {
        1: "# Chapter One\nbody text one",
        2: "# Chapter Two\nbody text two",
        3: "# Chapter Three\nbody text three",
    }
    parts = []
    markers = []
    pos = 0
    for page, text in pages.items():
        part = f"<!-- original page {page} -->\n{text}"
        markers.append((page, pos))
        parts.append(part)
        pos += len(part) + 2
    return "\n\n".join(parts), markers


class TestDetectAndCorrectOffset:
    def test_too_few_entries_unchanged(self):
        ex, _ = _make_extractor()
        md, markers = _offset_markdown()
        entries = [("Chapter One", 2)]
        assert ex._detect_and_correct_offset(entries, md, markers) == entries

    def test_no_markdown_unchanged(self):
        ex, _ = _make_extractor()
        entries = [("A", 1), ("B", 2), ("C", 3)]
        assert ex._detect_and_correct_offset(entries, "", []) == entries

    def test_all_pages_outside_marker_range_unchanged(self):
        ex, _ = _make_extractor()
        md, markers = _offset_markdown()  # markers only cover pages 1-3
        entries = [("A", 10), ("B", 11), ("C", 12)]
        assert ex._detect_and_correct_offset(entries, md, markers) == entries

    def test_unmatched_heading_keeps_original_page(self):
        # matched headings sit at offset -3; the unmatched one reports 0.
        # |−3 − 0| > 2 splits the clusters, so only the matched pair shifts.
        ex, logs = _make_extractor()
        md, markers = _offset_markdown()
        entries = [
            ("Chapter One", 4),
            ("Chapter Two", 5),
            ("Totally Missing Heading", 5),
        ]
        result = ex._detect_and_correct_offset(entries, md, markers)
        assert result == [
            ("Chapter One", 1),
            ("Chapter Two", 2),
            ("Totally Missing Heading", 5),
        ]

    def test_adjacent_offsets_merge_into_one_cluster(self):
        # offsets -1 (matched) and 0 (unmatched) differ by <= 2, so they merge
        # into ONE cluster whose median (0) nullifies the correction.
        ex, _ = _make_extractor()
        md, markers = _offset_markdown()
        entries = [
            ("Chapter One", 2),
            ("Chapter Two", 3),
            ("Totally Missing Heading", 2),
        ]
        result = ex._detect_and_correct_offset(entries, md, markers)
        assert result == entries  # unchanged: median of [-1, 0] is 0

    def test_global_candidate_fallback_when_window_empty(self):
        ex, _ = _make_extractor()
        # 600-line doc; markers for pages 1-3; heading of interest lives at
        # line ~500 — far from the estimated window of toc page 1.
        lines = [f"plain filler sentence number {i}" for i in range(600)]
        lines[0] = "<!-- original page 1 -->"
        lines[200] = "<!-- original page 2 -->"
        lines[400] = "<!-- original page 3 -->"
        lines[500] = "Distant Heading"
        md = "\n".join(lines)
        markers = [
            (1, 0),
            (2, sum(len(l) + 1 for l in lines[:200])),
            (3, sum(len(l) + 1 for l in lines[:400])),
        ]
        # NOTE (reported, not fixed): entries whose TOC page exceeds the
        # marker range are silently DROPPED from the corrected result.
        entries = [("Distant Heading", 1), ("Dropped One", 10), ("Dropped Two", 11)]
        result = ex._detect_and_correct_offset(entries, md, markers)
        assert result == [("Distant Heading", 3)]


# ────────────────────────────────────────────────────────────────────────────
# 4. locate_headings
# ────────────────────────────────────────────────────────────────────────────


def _two_page_heading_markdown() -> str:
    return (
        "<!-- original page 1 -->\n"
        "# Chapter One\n"
        "filler content\n"
        "<!-- original page 2 -->\n"
        "# Chapter Two\n"
        "more filler content"
    )


class TestLocateHeadings:
    def test_empty_entries_returns_none_result(self):
        ex, _ = _make_extractor()
        result = ex.locate_headings([], "whatever", [])
        assert isinstance(result, TOCResult)
        assert result.method == "none"
        assert result.confidence == 0.0
        assert result.validation_report == "No TOC entries"

    def test_marker_window_match(self):
        ex, _ = _make_extractor()
        md = _two_page_heading_markdown()
        result = ex.locate_headings([("Chapter One", 1), ("Chapter Two", 2)], md, [])
        assert result.method == "rule_based"
        assert result.confidence == 1.0
        assert all(e.is_heading_found for e in result.entries)
        assert [e.line for e in result.entries] == [1, 4]
        assert all(e.match_method.startswith("fuzzy_") for e in result.entries)
        assert "located: 2/2" in result.validation_report

    def test_page_estimation_without_marker(self):
        ex, _ = _make_extractor()
        md = "<!-- original page 1 -->\n# Solo Chapter\nfiller line"
        result = ex.locate_headings([("Solo Chapter", 2)], md, [])
        assert result.entries[0].is_heading_found is True

    def test_none_page_entries_are_skipped(self):
        ex, _ = _make_extractor()
        md = _two_page_heading_markdown()
        result = ex.locate_headings([("Ghost Heading", 0)], md, [])
        assert result.entries[0].is_heading_found is False
        assert result.confidence == 0.0
        assert result.entries[0].page is None

    def test_failed_match_lowers_confidence(self):
        ex, _ = _make_extractor()
        md = _two_page_heading_markdown()
        result = ex.locate_headings([("Completely Unrelated Heading", 1)], md, [])
        entry = result.entries[0]
        assert entry.is_heading_found is False
        assert entry.match_method == "failed"
        assert entry.confidence == pytest.approx(0.9)  # 1.0 - 0.1
        assert "1 via failed" in result.validation_report

    def test_global_fallback_after_empty_window(self):
        ex, _ = _make_extractor()
        # 400 lines; entry page 5 has no marker -> estimated line 400; the
        # only matching candidate lives at line 200 (outside the window but
        # inside the global "> 150" fallback).
        lines = [f"plain filler line number {i}" for i in range(400)]
        lines[0] = "<!-- original page 1 -->"
        lines[200] = "# Beta Heading"
        lines[390] = "<!-- original page 2 -->"
        md = "\n".join(lines)
        result = ex.locate_headings([("Beta Heading", 5)], md, [])
        assert result.entries[0].is_heading_found is True
        assert result.entries[0].line == 200

    def test_global_fallback_last_resort_uses_all_candidates(self):
        ex, _ = _make_extractor()
        # every candidate sits at line <= 150 -> the "> 150" fallback list is
        # empty -> the full candidate list is the last resort.
        lines = [f"plain filler line number {i}" for i in range(300)]
        lines[0] = "<!-- original page 1 -->"
        lines[20] = "# Gamma Heading"
        md = "\n".join(lines)
        result = ex.locate_headings([("Gamma Heading", 2)], md, [])
        assert result.entries[0].is_heading_found is True
        assert result.entries[0].line == 20


class TestBuildMarkerMap:
    def test_first_occurrence_wins(self):
        ex, _ = _make_extractor()
        md = (
            "<!-- original page 1 -->\n"
            "text\n"
            "<!-- original page 2 -->\n"
            "more\n"
            "<!-- original page 2 -->\n"
            "duplicate marker"
        )
        markers = ex._build_marker_map(md)
        assert markers[1] == 0
        assert markers[2] == 2  # first occurrence, not the duplicate at line 4


# ────────────────────────────────────────────────────────────────────────────
# 5. Internal helpers
# ────────────────────────────────────────────────────────────────────────────


class TestFindTocPage:
    def _reader(self, tmp_path, pages_text, name="findtoc.pdf"):
        doc = fitz.open()
        for text in pages_text:
            page = doc.new_page(width=612, height=792)
            if text:
                y = 60
                for line in text.splitlines():
                    page.insert_text((50, y), line, fontname="cour", fontsize=11)
                    y += 16
        path = _write_pdf(doc, tmp_path, name)
        return PdfReader(str(path))

    def test_toc_page_found(self, tmp_path):
        ex, _ = _make_extractor()
        reader = self._reader(
            tmp_path, ["plain intro page", "Table of Contents", "plain body page"]
        )
        assert ex._find_toc_page(reader, 3) == 1

    def test_persian_toc_keyword_found(self):
        ex, _ = _make_extractor()

        class _FakePage:
            @staticmethod
            def extract_text():
                return "فهرست مطالب"

        class _FakeReader:
            pages = [_FakePage()]

        assert ex._find_toc_page(_FakeReader(), 1) == 0

    def test_not_found_returns_none(self, tmp_path):
        ex, _ = _make_extractor()
        reader = self._reader(tmp_path, ["plain narrative page", "another plain page"])
        assert ex._find_toc_page(reader, 2) is None

    def test_exception_per_page_swallowed(self):
        ex, _ = _make_extractor()

        class _BoomPage:
            def extract_text(self):
                raise RuntimeError("boom")

        class _BoomReader:
            pages = [_BoomPage()]

        assert ex._find_toc_page(_BoomReader(), 1) is None

    def test_blank_page_uses_ocr_fallback(self, tmp_path, monkeypatch):
        ex, _ = _make_extractor()
        doc = fitz.open()
        doc.new_page(width=612, height=792)  # blank
        path = _write_pdf(doc, tmp_path, "blank.pdf")
        reader = PdfReader(str(path))
        monkeypatch.setattr(
            "pytesseract.image_to_string", lambda img, lang=None: "Contents\n1. Intro ......... 2"
        )
        assert ex._find_toc_page(reader, 1) == 0


class TestLooksLikeBody:
    def test_long_lines_detected_as_body(self):
        ex, _ = _make_extractor()
        lines = ["x" * 95] * 4
        assert ex._looks_like_body(lines) is True

    def test_short_lines_not_body(self):
        ex, _ = _make_extractor()
        assert ex._looks_like_body(["short line", "another one"]) is False


# ────────────────────────────────────────────────────────────────────────────
# 6. extract()-level edge cases that need real PDFs
# ────────────────────────────────────────────────────────────────────────────


class TestExtractEdgeCases:
    def test_footer_only_entries_produce_nothing(self, tmp_path):
        # Both dotted entries match back-matter footer patterns -> filtered
        # before scoring -> "No parser produced any valid entries".
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
        y = 90
        for line in ["About the Author ......... 3", "Index ......... 5"]:
            page.insert_text((50, y), line, fontname="cour", fontsize=11)
            y += 20
        for _ in range(5):
            body = doc.new_page(width=612, height=792)
            body.insert_text((50, 60), "body page text", fontname="cour", fontsize=11)
        path = _write_pdf(doc, tmp_path, "footer_only.pdf")
        ex, logs = _make_extractor()
        assert ex.extract(path) == []
        assert any("No parser produced any valid entries" in m for _, m in logs)

    def test_no_text_from_toc_pages_returns_empty(self, tmp_path, monkeypatch):
        # _find_toc_page finds the TOC via the OCR fallback, but the very same
        # fallback yields nothing during collection -> toc_lines stays empty.
        calls = {"n": 0}

        def _fake_ocr(img, lang=None):
            calls["n"] += 1
            return "Contents" if calls["n"] == 1 else ""

        monkeypatch.setattr("pytesseract.image_to_string", _fake_ocr)
        doc = fitz.open()
        doc.new_page(width=612, height=792)  # blank "TOC" page
        doc.new_page(width=612, height=792)  # blank body page
        path = _write_pdf(doc, tmp_path, "ocr_empty.pdf")
        ex, logs = _make_extractor()
        assert ex.extract(path) == []
        assert any("No text extracted from TOC pages even with OCR fallback" in m for _, m in logs)

    def test_page_labels_exception_is_swallowed(self, tmp_path, monkeypatch):
        real_reader = PdfReader

        class _LabelsBoomReader:
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, item):
                return getattr(self._inner, item)

            @property
            def page_labels(self):
                raise RuntimeError("labels boom")

        monkeypatch.setattr(
            "pypdf.PdfReader", lambda path: _LabelsBoomReader(real_reader(str(path)))
        )
        ex, logs = _make_extractor()
        entries = ex.extract(_bookmarked_path(tmp_path))
        assert [(e.title, e.page) for e in entries] == [("Chapter One", 1), ("Chapter Two", 2)]
        # the debug path swallowed the page-labels exception and continued

    def test_tesseract_import_error_returns_pypdf_text(self, tmp_path, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "pytesseract", None)  # ImportError
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
        doc.new_page(width=612, height=792)
        path = _write_pdf(doc, tmp_path, "no_pytesseract.pdf")
        reader = PdfReader(str(path))
        ex, _ = _make_extractor()
        # page 0 has 8 chars (< 50) -> OCR attempted -> ImportError -> pass
        assert ex._extract_page_text(reader, 0) == "Contents"

    def test_pypdf_extraction_exception_falls_to_empty(self):
        ex, logs = _make_extractor()

        class _BoomPage:
            def extract_text(self):
                raise RuntimeError("pypdf exploded")

        class _BoomReader:
            pages = [_BoomPage()]

        assert ex._extract_page_text(_BoomReader(), 0) == ""
        assert any("Tesseract OCR failed" in m for _, m in logs)

    def test_outline_without_destinations_returns_none(self):
        ex, _ = _make_extractor()

        class _WeirdReader:
            outline = [12345]  # neither Destination nor nested list

        assert ex._extract_outlines(_WeirdReader()) is None


def _bookmarked_path(tmp_path: Path) -> Path:
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=612, height=792)
    doc.set_toc([[1, "Chapter One", 1], [1, "Chapter Two", 2]])
    return _write_pdf(doc, tmp_path, "bookmarked_edge.pdf")
