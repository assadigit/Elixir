"""V18.13 — Layout reorder sampling-based multi-column detection tests.

Characterization tests for the bin-based multi-column detection algorithm.
Tests the pure logic (bin counting, gutter ratio, column ratio) without
requiring a real PDF file — uses mock word lists.

Run: pytest tests/test_layout_reorder_sampling.py -v
"""
from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load layout_reorder.py directly via importlib (bypasses core/pdf/__init__.py
# which imports markitdown — not available in the sandbox). Same pattern as
# test_v18219_fixes.py loads postchecks.py.
_lr_path = _project_root / "core" / "pdf" / "layout_reorder.py"
_spec = spec_from_file_location("_v18_13_layout_reorder", str(_lr_path))
_lr = module_from_spec(_spec)
sys.modules["_v18_13_layout_reorder"] = _lr
_spec.loader.exec_module(_lr)
LayoutReorder = _lr.LayoutReorder


def _make_words_2column(n_left=50, n_right=50, page_width=612.0):
    """Generate mock words for a 2-column page (gap in the middle).

    Left column: x_center in [50, 250] (0-40% of 612)
    Right column: x_center in [360, 560] (60-100% of 612)
    Gutter: [250, 360] (40-60%) — NO words.
    """
    words = []
    for i in range(n_left):
        x0 = 50 + (i * 4) % 200
        words.append({"x0": x0, "x1": x0 + 20, "y0": 100, "y1": 110, "text": f"L{i}"})
    for i in range(n_right):
        x0 = 360 + (i * 4) % 200
        words.append({"x0": x0, "x1": x0 + 20, "y0": 100, "y1": 110, "text": f"R{i}"})
    return words


def _make_words_1column(n=100, page_width=612.0):
    """Generate mock words for a single-column page (words across full width).

    x_center distributed across [50, 560] (8-92% of 612) — no gap.
    """
    words = []
    for i in range(n):
        x0 = 50 + (i * 5) % 500
        words.append({"x0": x0, "x1": x0 + 20, "y0": 100, "y1": 110, "text": f"W{i}"})
    return words


class _MockPage:
    """Mock pdfplumber page with width + extract_words()."""
    def __init__(self, words, width=612.0):
        self.width = width
        self._words = words

    def extract_words(self, x_tolerance=3, y_tolerance=3, **kw):
        return self._words


class _MockPdfplumber:
    """Mock pdfplumber module."""
    def __init__(self, pages):
        self._pages = pages

    def open(self, path):
        outer = self
        class _Ctx:
            def __enter__(self):
                class _Pdf:
                    pages = outer._pages
                return _Pdf()
            def __exit__(self, *a):
                pass
        return _Ctx()


class TestMultiColumnDetection:
    """Test the bin-based 2-column detection algorithm."""

    def _make_reorder(self, pages_dict):
        """Build a LayoutReorder with mocked pdfplumber."""
        mock_pdfplumber = _MockPdfplumber(pages_dict)
        old_module = sys.modules.get("pdfplumber")
        sys.modules["pdfplumber"] = mock_pdfplumber

        lr = LayoutReorder.__new__(LayoutReorder)
        lr.log = lambda msg, level="INFO": None
        lr._pdfplumber_available = True
        lr._pymupdf_available = False
        return lr, old_module

    def _cleanup(self, old_module):
        if old_module is not None:
            sys.modules["pdfplumber"] = old_module
        else:
            sys.modules.pop("pdfplumber", None)

    def test_two_column_detected(self):
        """A page with words in 2 clusters (gap in middle) → detected as 2-column."""
        words = _make_words_2column(n_left=50, n_right=50)
        page = _MockPage(words)
        lr, old = self._make_reorder([page])
        try:
            result = lr._is_two_column_pdfplumber(Path("/fake.pdf"), 1)
            assert result is True
        finally:
            self._cleanup(old)

    def test_single_column_not_detected(self):
        """A page with words spread across full width → NOT detected as 2-column."""
        words = _make_words_1column(n=100)
        page = _MockPage(words)
        lr, old = self._make_reorder([page])
        try:
            result = lr._is_two_column_pdfplumber(Path("/fake.pdf"), 1)
            assert result is False
        finally:
            self._cleanup(old)

    def test_too_few_words_not_detected(self):
        """A page with < 20 words → not detected (insufficient data)."""
        words = _make_words_2column(n_left=5, n_right=5)  # 10 words total
        page = _MockPage(words)
        lr, old = self._make_reorder([page])
        try:
            result = lr._is_two_column_pdfplumber(Path("/fake.pdf"), 1)
            assert result is False
        finally:
            self._cleanup(old)

    def test_no_words_not_detected(self):
        """A page with no words → not detected."""
        page = _MockPage([])
        lr, old = self._make_reorder([page])
        try:
            result = lr._is_two_column_pdfplumber(Path("/fake.pdf"), 1)
            assert result is False
        finally:
            self._cleanup(old)

    def test_detect_multi_column_any_sample_true(self):
        """_detect_multi_column returns True if ANY sampled page is 2-column."""
        single = _MockPage(_make_words_1column(100))
        multi = _MockPage(_make_words_2column(50, 50))
        lr, old = self._make_reorder([single, multi])
        try:
            result = lr._detect_multi_column(Path("/fake.pdf"), [1, 2])
            assert result is True
        finally:
            self._cleanup(old)

    def test_detect_multi_column_all_single_false(self):
        """_detect_multi_column returns False if all sampled pages are single-column."""
        p1 = _MockPage(_make_words_1column(100))
        p2 = _MockPage(_make_words_1column(100))
        lr, old = self._make_reorder([p1, p2])
        try:
            result = lr._detect_multi_column(Path("/fake.pdf"), [1, 2])
            assert result is False
        finally:
            self._cleanup(old)

    def test_detect_multi_column_empty_sample_false(self):
        """_detect_multi_column returns False for empty sample list."""
        lr, old = self._make_reorder([])
        try:
            result = lr._detect_multi_column(Path("/fake.pdf"), [])
            assert result is False
        finally:
            self._cleanup(old)

    def test_reorder_skips_when_single_column(self):
        """reorder_markdown returns the original markdown unchanged when the
        sample pages are single-column (the 95% case — the V18.13 optimization)."""
        markdown = ("<!-- original page 1 -->\nSome text on page 1.\n\n"
                    "<!-- original page 2 -->\nMore text on page 2.\n\n"
                    "<!-- original page 3 -->\nEven more text on page 3.")
        pages = [_MockPage(_make_words_1column(100)), _MockPage(_make_words_1column(100)),
                 _MockPage(_make_words_1column(100))]
        lr, old = self._make_reorder(pages)
        log_msgs = []
        lr.log = lambda msg, level="INFO": log_msgs.append((msg, level))
        try:
            result = lr.reorder_markdown(markdown, Path("/fake.pdf"))
            # Original markdown returned unchanged
            assert result == markdown
            # An INFO log about the skip
            infos = [m for m, l in log_msgs if l == "INFO"]
            assert any("Layout reorder skipped" in i and "V18.13" in i for i in infos)
        finally:
            self._cleanup(old)

    def test_reorder_proceeds_when_two_column(self):
        """reorder_markdown proceeds with the per-page reorder when the sample
        pages ARE multi-column (the 5% case — actual scientific papers)."""
        markdown = ("<!-- original page 1 -->\nSome text on page 1.\n\n"
                    "<!-- original page 2 -->\nMore text on page 2.")
        pages = [_MockPage(_make_words_2column(50, 50)), _MockPage(_make_words_2column(50, 50))]
        lr, old = self._make_reorder(pages)
        log_msgs = []
        lr.log = lambda msg, level="INFO": log_msgs.append((msg, level))
        try:
            result = lr.reorder_markdown(markdown, Path("/fake.pdf"))
            # Did NOT return the original unchanged (the reorder ran)
            # (The reorder may not change the content since our mock words
            # produce different text than the markdown, but the key check is
            # that it did NOT log the skip.)
            infos = [m for m, l in log_msgs if l == "INFO"]
            assert not any("Layout reorder skipped" in i for i in infos), \
                "Should NOT have skipped — multi-column detected"
        finally:
            self._cleanup(old)
