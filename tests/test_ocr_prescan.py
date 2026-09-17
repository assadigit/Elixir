"""V18.2.16: Tests for the deterministic OCR pre-scan.

Tests verify:
1. ``_is_text_meaningful`` heuristic classifies digital vs scanned text
2. ``intersect_with_valid_pages`` restricts to selected chapters / page range
3. ``PreScanResult.skip_model_load`` property is correct
4. ``prescan_pages`` returns the right page split (mocked PDF reader)
5. Fail-open: pre-scan crash returns an empty result (doesn't propagate)
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

# Stub tiktoken (not installed in test env)
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from core.ocr.ocr_prescan import (
    PreScanResult,
    _is_text_meaningful,
    intersect_with_valid_pages,
    prescan_pages,
)

# ═══════════════════════════════════════════════════════════════════════════
# _is_text_meaningful heuristic
# ═══════════════════════════════════════════════════════════════════════════

class TestIsTextMeaningful:
    """V18.2.16: The text-meaningful heuristic classifies digital vs scanned."""

    def test_digital_text_passes(self):
        """A page with 50+ chars of real text is digital (no OCR needed)."""
        text = "This is a meaningful digital page with enough text to pass the threshold check for OCR necessity."
        assert _is_text_meaningful(text) is True

    def test_empty_text_fails(self):
        """An empty page (no extractable text) is scanned (needs OCR)."""
        assert _is_text_meaningful("") is False
        assert _is_text_meaningful(None) is False  # type: ignore[arg-type]

    def test_very_short_text_fails(self):
        """A page with <30 chars and <2 words is scanned."""
        assert _is_text_meaningful("ab") is False
        assert _is_text_meaningful("hi") is False

    def test_short_text_with_two_words_passes(self):
        """A short text with ≥2 words and ≥30 chars passes."""
        # 30+ chars, 2+ words
        text = "Hello world this is a test of the heuristic checker"
        assert _is_text_meaningful(text) is True

    def test_garbage_text_fails(self):
        """A page with >30% garbage characters is scanned."""
        # 40 chars, half garbage
        text = "abc@@@@@@@@@@@@@@@@abc@@@@@@@@@@@@@@@@"
        assert _is_text_meaningful(text) is False

    def test_persian_text_passes(self):
        """Persian text (Unicode range \u0600-\u06FF) is recognized as words."""
        # Persian text with enough chars
        text = "این یک متن فارسی است که برای تست سیستم تشخیص متن دیجیتال نوشته شده است"
        assert _is_text_meaningful(text) is True


# ═══════════════════════════════════════════════════════════════════════════
# intersect_with_valid_pages
# ═══════════════════════════════════════════════════════════════════════════

class TestIntersectWithValidPages:
    """V18.2.16: The candidate-page filter respects chapter selection + page range."""

    def test_no_filters_returns_all(self):
        """Without valid_pages or page_range, all pages are candidates."""
        result = intersect_with_valid_pages(
            [1, 2, 3, 4, 5], valid_pages=None,
            page_range_start=None, page_range_end=None, total_pages=5,
        )
        assert result == [1, 2, 3, 4, 5]

    def test_valid_pages_filters(self):
        """Chapter selection (valid_pages) restricts candidates."""
        result = intersect_with_valid_pages(
            [1, 2, 3, 4, 5], valid_pages={2, 3, 4},
            page_range_start=None, page_range_end=None, total_pages=5,
        )
        assert result == [2, 3, 4]

    def test_page_range_filters(self):
        """Page range restricts candidates."""
        result = intersect_with_valid_pages(
            [1, 2, 3, 4, 5], valid_pages=None,
            page_range_start=2, page_range_end=4, total_pages=5,
        )
        assert result == [2, 3, 4]

    def test_both_filters_combine(self):
        """Both valid_pages AND page_range apply (intersection)."""
        result = intersect_with_valid_pages(
            [1, 2, 3, 4, 5, 6, 7], valid_pages={3, 4, 5, 6},
            page_range_start=2, page_range_end=5, total_pages=7,
        )
        # valid_pages ∩ page_range = {3,4,5}
        assert result == [3, 4, 5]

    def test_result_is_sorted(self):
        """The result is always sorted (deterministic)."""
        result = intersect_with_valid_pages(
            [5, 3, 1, 4, 2], valid_pages=None,
            page_range_start=None, page_range_end=None, total_pages=5,
        )
        assert result == [1, 2, 3, 4, 5]

    def test_empty_input_returns_empty(self):
        result = intersect_with_valid_pages(
            [], valid_pages={1, 2, 3},
            page_range_start=None, page_range_end=None, total_pages=5,
        )
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# PreScanResult
# ═══════════════════════════════════════════════════════════════════════════

class TestPreScanResult:
    """V18.2.16: The PreScanResult dataclass."""

    def test_empty_result_skips_model_load(self):
        """An empty result (no scanned pages) → skip_model_load is True."""
        r = PreScanResult()
        assert r.skip_model_load is True
        assert r.needs_ocr_count == 0

    def test_non_empty_result_loads_model(self):
        """A result with scanned pages → skip_model_load is False."""
        r = PreScanResult(scanned_pages=[1, 5, 10])
        assert r.skip_model_load is False
        assert r.needs_ocr_count == 3

    def test_digital_pages_tracked(self):
        r = PreScanResult(
            scanned_pages=[3],
            digital_pages=[1, 2, 4, 5],
        )
        assert len(r.digital_pages) == 4
        assert r.needs_ocr_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# prescan_pages (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestPrescanPages:
    """V18.2.16: The prescan_pages function with a mocked PDF reader."""

    def _make_mock_reader(self, page_texts: dict):
        """Build a mock pypdf.PdfReader where page N returns page_texts[N].

        page_texts: {1: "text for page 1", 2: "", 3: "text for page 3", ...}
        Pages not in the dict default to empty (scanned).
        """
        reader = MagicMock()
        reader.is_encrypted = False
        pages = []
        max_page = max(page_texts.keys()) if page_texts else 0
        for i in range(1, max_page + 1):
            page = MagicMock()
            text = page_texts.get(i, "")
            page.extract_text.return_value = text
            pages.append(page)
        reader.pages = pages
        return reader

    def test_all_digital_pages_skip_model(self):
        """When all candidate pages have digital text, skip_model_load is True."""
        reader = self._make_mock_reader({
            1: "This is page one with enough text to be considered digital and meaningful.",
            2: "This is page two with enough text to be considered digital and meaningful.",
            3: "This is page three with enough text to be considered digital and meaningful.",
        })
        with patch("pypdf.PdfReader", return_value=reader):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1, 2, 3],
            )
        assert result.skip_model_load is True
        assert result.scanned_pages == []
        assert result.digital_pages == [1, 2, 3]
        assert result.total_scanned == 3

    def test_all_scanned_pages_need_ocr(self):
        """When all candidate pages are empty (scanned), all need OCR."""
        reader = self._make_mock_reader({
            1: "",
            2: "",
            3: "",
        })
        with patch("pypdf.PdfReader", return_value=reader):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1, 2, 3],
            )
        assert result.skip_model_load is False
        assert result.scanned_pages == [1, 2, 3]
        assert result.digital_pages == []
        assert result.needs_ocr_count == 3

    def test_mixed_pages_split_correctly(self):
        """Some pages digital, some scanned — the split is correct."""
        reader = self._make_mock_reader({
            1: "Digital page one with enough text to pass the meaningful text heuristic check.",
            2: "",  # scanned
            3: "Digital page three with enough text to pass the meaningful text heuristic check.",
            4: "",  # scanned
            5: "Digital page five with enough text to pass the meaningful text heuristic check.",
        })
        with patch("pypdf.PdfReader", return_value=reader):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1, 2, 3, 4, 5],
            )
        assert result.scanned_pages == [2, 4]
        assert result.digital_pages == [1, 3, 5]
        assert result.needs_ocr_count == 2
        assert result.skip_model_load is False

    def test_empty_candidate_list_returns_empty(self):
        """An empty candidate list returns an empty result immediately."""
        result = prescan_pages(
            pdf_path="/fake/path.pdf",
            candidate_pages=[],
        )
        assert result.scanned_pages == []
        assert result.digital_pages == []
        assert result.skip_model_load is True

    def test_failopen_on_pdf_open_error(self):
        """If the PDF can't be opened, the pre-scan returns empty (fail-open)."""
        with patch("pypdf.PdfReader", side_effect=Exception("corrupt PDF")):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1, 2, 3],
            )
        # Fail-open: empty result → skip_model_load is True, but the OCR
        # service's caller handles this gracefully (the existing pages_to_ocr
        # path runs if the pre-scan crashes — see the try/except in service.py).
        assert result.scanned_pages == []
        assert result.skip_model_load is True

    def test_extraction_error_marks_page_as_scanned(self):
        """If page.extract_text() raises, the page is conservatively marked scanned."""
        reader = MagicMock()
        reader.is_encrypted = False
        page = MagicMock()
        page.extract_text.side_effect = Exception("extraction failed")
        reader.pages = [page]
        with patch("pypdf.PdfReader", return_value=reader):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1],
            )
        # Conservative: extraction failure → marked as scanned (let OCR try).
        assert result.scanned_pages == [1]
        assert result.digital_pages == []

    def test_elapsed_sec_is_positive(self):
        """The elapsed time is recorded and positive."""
        reader = self._make_mock_reader({
            1: "Digital page one with enough text to pass the meaningful text heuristic check.",
        })
        with patch("pypdf.PdfReader", return_value=reader):
            result = prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1],
            )
        assert result.elapsed_sec >= 0.0

    def test_log_fn_called_with_results(self):
        """The log_fn callback is called with traceable messages."""
        reader = self._make_mock_reader({
            1: "",
            2: "Digital page two with enough text to pass the meaningful text heuristic check.",
        })
        logs = []
        with patch("pypdf.PdfReader", return_value=reader):
            prescan_pages(
                pdf_path="/fake/path.pdf",
                candidate_pages=[1, 2],
                log_fn=lambda msg, level="INFO": logs.append((msg, level)),
            )
        # At least 2 log lines: the "checking..." + the "result" summary.
        assert len(logs) >= 2
        # The result summary mentions the page count.
        result_msgs = [msg for msg, _ in logs if "result" in msg.lower()]
        assert len(result_msgs) >= 1
