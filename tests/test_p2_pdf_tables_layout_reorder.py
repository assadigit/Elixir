"""P2 (Test-Net Deepening) — hermetic tests for core/pdf/layout_reorder.py.

Baseline: layout_reorder.py 54% (112/243 lines missed).

Hermeticity strategy:
  - REAL PyMuPDF (fitz) builds two-column and single-column PDFs (two text
    columns at x=50 / x=380 on a 612pt page, right column inserted first so
    the raw content-stream order differs from reading order). REAL pdfplumber
    and REAL fitz geometry drive the detection + reorder algorithms.
  - No network, no subprocess.

TWO REAL BUGS PINNED HERE (reported, not fixed — no production edits allowed):

  BUG A (feature-dead, pdfplumber ≥ 0.10): ``_get_words_pdfplumber`` requires
  word dicts to contain "y0"/"y1", but pdfplumber's ``extract_words`` returns
  "top"/"bottom" instead. With pdfplumber installed (the normal case) the
  helper ALWAYS returns [] → ``_is_two_column_pdfplumber`` is always False →
  ``reorder_markdown`` always takes the V18.13 "skip" branch. The whole
  layout-reorder feature never runs in production.

  BUG B (crash): ``_reorder_page_pymupdf`` passes a list of SPAN DICTS to
  ``_reconstruct_text_from_lines``, which iterates ``for word in line`` —
  iterating a dict yields its KEYS (strings) → ``TypeError: string indices
  must be integers``. Any page with text crashes the PyMuPDF reorder path;
  ``reorder_markdown``'s per-page except swallows it and keeps the original.

Tests that reach code behind these bugs use a documented, minimal bridge:
  - ``_bridge_words`` adds y0/y1 (from top/bottom) to REAL pdfplumber words;
  - ``_shim_reconstruct`` wraps non-list lines for the pymupdf span shape.
Both are applied per-instance via monkeypatch and clearly commented.

Run: COVERAGE_FILE=.coverage.p2b2 python3 -m pytest tests/test_p2_pdf_tables_layout_reorder.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.pdf.layout_reorder import LayoutReorder  # noqa: E402

LEFT = "alpha beta gamma delta epsilon zeta"
RIGHT = "omega psi chi phi upsilon tau"


# ── fitz PDF factory ────────────────────────────────────────────────────────


def _make_two_col_pdf(path: Path, n_pages: int = 2, n_lines: int = 11) -> Path:
    """Two-column pages; the RIGHT column is inserted first, so the raw
    content-stream order (right column, then left) differs from reading order
    (left column first)."""
    import fitz

    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        ys = [60 + 15 * i for i in range(n_lines)]
        for y in ys:
            page.insert_text((380, y), RIGHT, fontsize=10)  # right first
        for y in ys:
            page.insert_text((50, y), LEFT, fontsize=10)  # left second
    doc.save(str(path))
    doc.close()
    return path


def _make_single_col_pdf(path: Path) -> Path:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    line = "the quick brown fox jumps over the lazy dog while running through golden fields"
    y = 60
    for _ in range(6):
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    doc.save(str(path))
    doc.close()
    return path


def _make_empty_pdf(path: Path) -> Path:
    import fitz

    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return path


def _raw_page_content() -> str:
    """What a converter would emit in raw (content-stream) order:
    all RIGHT-column lines, then all LEFT-column lines."""
    return "\n".join([RIGHT] * 11 + [LEFT] * 11)


def _bridge_words(page):
    """Bridge for BUG A: real pdfplumber words, plus the y0/y1 keys the
    production code expects (pdfplumber ≥ 0.10 uses top/bottom)."""

    def _get(p, **kw):
        words = p.extract_words(x_tolerance=3, y_tolerance=3)
        for w in words:
            if "y0" not in w:
                w["y0"] = w["top"]
                w["y1"] = w["bottom"]
        return words

    return _get(page)


def _install_bridge(lr: LayoutReorder) -> None:
    lr._get_words_pdfplumber = lambda page: _bridge_words(page)


def _install_reconstruct_shim(lr: LayoutReorder) -> None:
    """Bridge for BUG B: accept the span-dict shape _reorder_page_pymupdf
    actually passes (a list of dicts, not a list of lists of dicts)."""
    real = lr._reconstruct_text_from_lines

    def shim(lines):
        return real([ln if isinstance(ln, list) else [ln] for ln in lines])

    lr._reconstruct_text_from_lines = shim


@pytest.fixture()
def two_col_pdf(tmp_path: Path) -> Path:
    return _make_two_col_pdf(tmp_path / "twocol.pdf")


@pytest.fixture()
def single_col_pdf(tmp_path: Path) -> Path:
    return _make_single_col_pdf(tmp_path / "onecol.pdf")


@pytest.fixture()
def empty_pdf(tmp_path: Path) -> Path:
    return _make_empty_pdf(tmp_path / "empty.pdf")


def _md(pages: dict[int, str]) -> str:
    return "\n\n".join(f"<!-- original page {n} -->\n{c}" for n, c in pages.items())


# ── dependency probing ──────────────────────────────────────────────────────


class TestDependencies:
    def test_real_init_pdfplumber_available(self):
        lr = LayoutReorder()
        assert lr._pdfplumber_available is True
        assert lr._pymupdf_available is False  # only probed when pdfplumber missing
        assert lr.is_available() is True

    def test_pdfplumber_missing_falls_back_to_pymupdf(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        msgs: list[tuple[str, str]] = []
        lr = LayoutReorder(log_callback=lambda m, l: msgs.append((m, l)))
        assert lr._pdfplumber_available is False
        assert lr._pymupdf_available is True
        assert lr.is_available() is True
        assert any("pdfplumber not installed" in m for m, _ in msgs)

    def test_no_library_at_all(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        monkeypatch.setitem(sys.modules, "fitz", None)
        msgs: list[tuple[str, str]] = []
        lr = LayoutReorder(log_callback=lambda m, l: msgs.append((m, l)))
        assert lr.is_available() is False
        assert any("No layout detection library" in m for m, _ in msgs)


# ── reorder_markdown — entry/skip paths ─────────────────────────────────────


class TestReorderMarkdownSkip:
    def test_unavailable_returns_original(self):
        lr = LayoutReorder.__new__(LayoutReorder)
        lr.log = lambda msg, level="INFO": None
        lr._pdfplumber_available = False
        lr._pymupdf_available = False
        md = _md({1: "hello"})
        assert lr.reorder_markdown(md, Path("/fake.pdf")) == md

    def test_no_page_markers_returns_original(self, single_col_pdf):
        lr = LayoutReorder()
        md = "just some markdown without any page markers at all"
        assert lr.reorder_markdown(md, single_col_pdf) == md

    def test_single_column_skipped_v18_13(self, single_col_pdf):
        lr = LayoutReorder()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        md = _md({1: "content of page one", 2: "content of page two"})
        assert lr.reorder_markdown(md, single_col_pdf) == md
        assert any("Layout reorder skipped" in m and "V18.13" in m for m, _ in msgs)

    def test_two_column_also_skipped_with_real_pdfplumber_bug_a(self, two_col_pdf):
        """BUG A pin: with real pdfplumber (unbridged) even a genuine
        two-column page is NOT detected — the feature is dead in production."""
        lr = LayoutReorder()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        md = _md({1: _raw_page_content(), 2: _raw_page_content()})
        assert lr.reorder_markdown(md, two_col_pdf) == md
        assert any("Layout reorder skipped" in m for m, _ in msgs)


# ── reorder_markdown — PyMuPDF path ─────────────────────────────────────────


class TestReorderMarkdownPymupdf:
    def _pymupdf_lr(self) -> LayoutReorder:
        lr = LayoutReorder()
        lr._pdfplumber_available = False
        lr._pymupdf_available = True
        return lr

    def test_real_two_column_reordered_with_shim(self, two_col_pdf):
        lr = self._pymupdf_lr()
        _install_reconstruct_shim(lr)
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        md = _md({1: _raw_page_content(), 2: _raw_page_content()})
        out = lr.reorder_markdown(md, two_col_pdf)
        assert out != md
        assert any("Reordering 2 pages" in m for m, _ in msgs)
        # reading order: left column now comes first
        assert out.find(LEFT) < out.find(RIGHT)
        assert "<!-- original page 1 -->" in out and "<!-- original page 2 -->" in out

    def test_pymupdf_path_crashes_and_is_swallowed_bug_b(self, two_col_pdf):
        """BUG B pin: without the reconstruct shim the per-page PyMuPDF
        reorder raises TypeError; reorder_markdown catches it and keeps the
        original page content (with a warning)."""
        lr = self._pymupdf_lr()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        md = _md({1: _raw_page_content()})
        out = lr.reorder_markdown(md, two_col_pdf)
        assert LEFT in out and RIGHT in out  # original content kept
        assert any("Layout reorder failed for page 1" in m for m, _ in msgs)

    def test_reorder_page_pymupdf_raises_typeerror_root_cause(self, two_col_pdf):
        lr = self._pymupdf_lr()
        with pytest.raises(TypeError, match="string indices"):
            lr._reorder_page_pymupdf(two_col_pdf, 1, _raw_page_content())

    def test_reorder_page_pymupdf_with_shim_reorders(self, two_col_pdf):
        lr = self._pymupdf_lr()
        _install_reconstruct_shim(lr)
        out = lr._reorder_page_pymupdf(two_col_pdf, 1, _raw_page_content())
        assert out != _raw_page_content()
        assert out.find(LEFT) < out.find(RIGHT)

    def test_reorder_page_pymupdf_same_content_returns_original(self, two_col_pdf):
        lr = self._pymupdf_lr()
        _install_reconstruct_shim(lr)
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        # page content already in (y, x) sorted order → reorder is a no-op
        already_ordered = "\n".join([LEFT, RIGHT] * 11)
        out = lr._reorder_page_pymupdf(two_col_pdf, 1, already_ordered)
        assert out == already_ordered
        assert any("didn't change page 1" in m for m, _ in msgs)

    def test_reorder_page_pymupdf_page_beyond_doc(self, two_col_pdf):
        lr = self._pymupdf_lr()
        assert lr._reorder_page_pymupdf(two_col_pdf, 99, "keep me") == "keep me"

    def test_reorder_page_pymupdf_no_text_blocks(self, empty_pdf):
        lr = self._pymupdf_lr()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        assert lr._reorder_page_pymupdf(empty_pdf, 1, "empty page") == "empty page"
        assert any("No text blocks found" in m for m, _ in msgs)


# ── reorder_markdown — pdfplumber path (bridged) ────────────────────────────


class TestReorderMarkdownPdfplumber:
    def _bridged_lr(self) -> LayoutReorder:
        lr = LayoutReorder()
        lr._pymupdf_available = False
        _install_bridge(lr)
        return lr

    def test_real_two_column_reordered(self, two_col_pdf):
        lr = self._bridged_lr()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        md = _md({1: _raw_page_content(), 2: _raw_page_content()})
        out = lr.reorder_markdown(md, two_col_pdf)
        assert out != md
        # clustering merges same-baseline words: each output line is
        # left-line + right-line in reading order
        assert f"{LEFT} {RIGHT}" in out
        assert any("Reordered page 1 (pdfplumber)" in m for m, _ in msgs)

    def test_single_column_unchanged_via_bridge(self, single_col_pdf):
        lr = self._bridged_lr()
        line = "the quick brown fox jumps over the lazy dog while running through golden fields"
        content = "\n".join([line] * 6)
        md = _md({1: content})
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        out = lr.reorder_markdown(md, single_col_pdf)
        assert out == md  # single-column: detection gate skips everything
        assert any("Layout reorder skipped" in m for m, _ in msgs)

    def test_reorder_page_pdfplumber_no_words_without_bridge(self, two_col_pdf):
        """BUG A pin (unit level): real pdfplumber words lack y0 → the helper
        returns [] and the reorder is skipped with a debug message."""
        lr = LayoutReorder()  # unbridged
        lr._pymupdf_available = False
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        out = lr._reorder_page_pdfplumber(two_col_pdf, 1, "original text")
        assert out == "original text"
        assert any("No words found on page 1" in m for m, _ in msgs)

    def test_reorder_page_pdfplumber_falls_back_to_pymupdf(self, two_col_pdf, monkeypatch):
        lr = LayoutReorder()
        lr._pymupdf_available = True
        monkeypatch.setattr(lr, "_reorder_page_pymupdf", lambda *a, **k: "PYMUPDF RESULT")
        out = lr._reorder_page_pdfplumber(two_col_pdf, 1, "original text")
        assert out == "PYMUPDF RESULT"

    def test_reorder_page_pdfplumber_missing_keys_fallback(self, two_col_pdf, monkeypatch):
        lr = LayoutReorder()
        lr._pymupdf_available = True

        def _words_without_x1(page, **kw):
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            for w in words:
                w.pop("x1", None)
            return words

        monkeypatch.setattr(lr, "_get_words_pdfplumber", _words_without_x1)
        monkeypatch.setattr(lr, "_reorder_page_pymupdf", lambda *a, **k: "FALLBACK")
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        out = lr._reorder_page_pdfplumber(two_col_pdf, 1, "original")
        assert out == "FALLBACK"
        assert any("missing position keys" in m for m, _ in msgs)

    def test_reorder_page_pdfplumber_missing_keys_no_fallback(self, two_col_pdf, monkeypatch):
        lr = LayoutReorder()
        lr._pymupdf_available = False

        def _words_without_text(page, **kw):
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            for w in words:
                w.pop("text", None)
            return words

        monkeypatch.setattr(lr, "_get_words_pdfplumber", _words_without_text)
        out = lr._reorder_page_pdfplumber(two_col_pdf, 1, "original")
        assert out == "original"

    def test_reorder_page_pdfplumber_same_content_returns_original(self, two_col_pdf):
        lr = self._bridged_lr()
        msgs: list[tuple[str, str]] = []
        lr.log = lambda m, l: msgs.append((m, l))
        # content already in clustered reading order → no change
        already = "\n".join([f"{LEFT} {RIGHT}"] * 11)
        out = lr._reorder_page_pdfplumber(two_col_pdf, 1, already)
        assert out == already
        assert any("didn't change page 1" in m for m, _ in msgs)

    def test_reorder_page_pdfplumber_page_beyond_doc(self, two_col_pdf):
        lr = self._bridged_lr()
        assert lr._reorder_page_pdfplumber(two_col_pdf, 99, "keep") == "keep"


# ── two-column detection ────────────────────────────────────────────────────


class TestIsTwoColumn:
    def test_pymupdf_real_two_column(self, two_col_pdf):
        lr = LayoutReorder()
        assert lr._is_two_column_pymupdf(two_col_pdf, 1) is True

    def test_pymupdf_real_single_column(self, single_col_pdf):
        lr = LayoutReorder()
        assert lr._is_two_column_pymupdf(single_col_pdf, 1) is False

    def test_pymupdf_empty_page(self, empty_pdf):
        lr = LayoutReorder()
        assert lr._is_two_column_pymupdf(empty_pdf, 1) is False

    def test_pymupdf_page_beyond_doc(self, two_col_pdf):
        lr = LayoutReorder()
        assert lr._is_two_column_pymupdf(two_col_pdf, 99) is False

    def test_pymupdf_zero_width_page(self, monkeypatch):
        import types

        import fitz

        class _Page:
            rect = types.SimpleNamespace(width=0)

            def get_text(self, *a):
                return {"blocks": []}

        class _Doc:
            page_count = 1

            def __getitem__(self, i):
                return _Page()

            def close(self):
                pass

        monkeypatch.setattr(fitz, "open", lambda *a, **k: _Doc())
        lr = LayoutReorder()
        assert lr._is_two_column_pymupdf(Path("/fake.pdf"), 1) is False

    def test_pdfplumber_bridged_real_two_column(self, two_col_pdf):
        lr = LayoutReorder()
        _install_bridge(lr)
        assert lr._is_two_column_pdfplumber(two_col_pdf, 1) is True

    def test_pdfplumber_bridged_real_single_column(self, single_col_pdf):
        lr = LayoutReorder()
        _install_bridge(lr)
        assert lr._is_two_column_pdfplumber(single_col_pdf, 1) is False

    def test_pdfplumber_page_beyond_doc(self, two_col_pdf):
        lr = LayoutReorder()
        assert lr._is_two_column_pdfplumber(two_col_pdf, 99) is False

    def test_pdfplumber_too_few_words(self, two_col_pdf):
        lr = LayoutReorder()

        def _few(page, **kw):
            return [{"x0": 50, "x1": 70, "y0": 10, "y1": 20, "text": "a"}] * 5

        lr._get_words_pdfplumber = _few
        assert lr._is_two_column_pdfplumber(two_col_pdf, 1) is False

    def test_pdfplumber_zero_width_page(self, monkeypatch):
        class _Page:
            width = 0

            def extract_words(self, **kw):
                return [{"x0": 1, "x1": 2, "y0": 3, "y1": 4, "text": "w"}] * 30

        class _Pdf:
            pages = [_Page()]

        class _Ctx:
            def __enter__(self):
                return _Pdf()

            def __exit__(self, *a):
                return False

        class _MockPdfplumber:
            @staticmethod
            def open(path):
                return _Ctx()

        monkeypatch.setitem(sys.modules, "pdfplumber", _MockPdfplumber)
        lr = LayoutReorder()
        assert lr._is_two_column_pdfplumber(Path("/fake.pdf"), 1) is False


class TestDetectMultiColumn:
    def test_true_when_any_sample_two_column(self, two_col_pdf):
        lr = LayoutReorder()
        lr._pdfplumber_available = False
        lr._pymupdf_available = True
        assert lr._detect_multi_column(two_col_pdf, [1, 2]) is True

    def test_false_when_all_single(self, single_col_pdf):
        lr = LayoutReorder()
        lr._pdfplumber_available = False
        lr._pymupdf_available = True
        assert lr._detect_multi_column(single_col_pdf, [1]) is False

    def test_empty_sample(self, two_col_pdf):
        lr = LayoutReorder()
        assert lr._detect_multi_column(two_col_pdf, []) is False

    def test_exception_in_probe_continues(self, two_col_pdf, monkeypatch):
        lr = LayoutReorder()
        monkeypatch.setattr(
            lr,
            "_is_two_column_pdfplumber",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
        )
        assert lr._detect_multi_column(two_col_pdf, [1, 2]) is False


# ── markdown page splitting ─────────────────────────────────────────────────


class TestSplitMarkdownIntoPages:
    def test_multiple_pages(self):
        md = "<!-- original page 1 -->\nA\n\n<!-- original page 2 -->\nB"
        pages = LayoutReorder()._split_markdown_into_pages(md)
        assert pages == {1: "A", 2: "B"}

    def test_trailing_text_after_last_marker_kept(self):
        md = "<!-- original page 3 -->\nstart\nmiddle end"
        pages = LayoutReorder()._split_markdown_into_pages(md)
        assert pages == {3: "start\nmiddle end"}

    def test_no_markers(self):
        assert LayoutReorder()._split_markdown_into_pages("plain text") == {}

    def test_preamble_before_first_marker_dropped(self):
        # characterization: text before the first marker is NOT captured
        md = "PREAMBLE\n<!-- original page 1 -->\ncontent"
        pages = LayoutReorder()._split_markdown_into_pages(md)
        assert pages == {1: "content"}


# ── word helpers ────────────────────────────────────────────────────────────


class TestGetWordsPdfplumber:
    def test_first_attempt_success(self):
        class _Page:
            def extract_words(self, x_tolerance=3, y_tolerance=3, **kw):
                return [{"x0": 1, "y0": 2, "text": "ok"}]

        lr = LayoutReorder()
        assert lr._get_words_pdfplumber(_Page()) == [{"x0": 1, "y0": 2, "text": "ok"}]

    def test_fallback_attempts_until_keep_blank(self):
        calls: list[tuple] = []

        class _Page:
            def extract_words(self, x_tolerance=None, y_tolerance=None, keep_blank_chars=None):
                calls.append((x_tolerance, keep_blank_chars))
                if keep_blank_chars is False:
                    return [{"x0": 1, "y0": 2, "text": "late"}]
                return [{"x0": 1, "text": "no y0"}]  # missing y0

        lr = LayoutReorder()
        words = lr._get_words_pdfplumber(_Page())
        assert words == [{"x0": 1, "y0": 2, "text": "late"}]
        assert len(calls) == 4  # (3,3) → (5,5) → () → (3,3,keep_blank_chars=False)

    def test_keep_blank_exception_returns_empty(self):
        class _Page:
            def extract_words(self, x_tolerance=None, y_tolerance=None, keep_blank_chars=None):
                if keep_blank_chars is False:
                    raise TypeError("unexpected kwarg")
                return [{"x0": 1, "text": "no y0"}]

        assert LayoutReorder()._get_words_pdfplumber(_Page()) == []

    def test_second_tolerance_attempt_succeeds(self):
        calls: list[tuple] = []

        class _Page:
            def extract_words(self, x_tolerance=None, y_tolerance=None, **kw):
                calls.append(x_tolerance)
                if x_tolerance == 5:
                    return [{"x0": 1, "y0": 2, "text": "wide"}]
                return [{"x0": 1, "text": "no y0"}]

        assert LayoutReorder()._get_words_pdfplumber(_Page()) == [
            {"x0": 1, "y0": 2, "text": "wide"}
        ]
        assert calls == [3, 5]

    def test_third_no_args_attempt_succeeds(self):
        calls: list[tuple] = []

        class _Page:
            def extract_words(self, x_tolerance=None, y_tolerance=None, **kw):
                calls.append((x_tolerance, y_tolerance))
                if x_tolerance is None:
                    return [{"x0": 1, "y0": 2, "text": "plain"}]
                return [{"x0": 1, "text": "no y0"}]

        assert LayoutReorder()._get_words_pdfplumber(_Page()) == [
            {"x0": 1, "y0": 2, "text": "plain"}
        ]
        assert calls == [(3, 3), (5, 5), (None, None)]

    def test_all_attempts_fail_returns_empty(self):
        class _Page:
            def extract_words(self, **kw):
                return [{"x0": 1, "text": "never has y0"}]

        assert LayoutReorder()._get_words_pdfplumber(_Page()) == []

    def test_real_pdfplumber_words_lack_y0_bug_a(self, two_col_pdf):
        """BUG A pin: against real pdfplumber the helper always returns []."""
        import pdfplumber

        with pdfplumber.open(str(two_col_pdf)) as pdf:
            assert pdf.pages[0].extract_words(x_tolerance=3, y_tolerance=3)  # words exist…
            assert LayoutReorder()._get_words_pdfplumber(pdf.pages[0]) == []  # …but none pass


class TestClusterAndReconstruct:
    def test_cluster_empty(self):
        assert LayoutReorder()._cluster_words_into_lines([]) == []

    def test_cluster_two_levels_and_x_sort(self):
        words = [
            {"x0": 200, "y0": 100, "text": "b1"},
            {"x0": 10, "y0": 100, "text": "a1"},
            {"x0": 10, "y0": 150, "text": "a2"},
            {"x0": 200, "y0": 150, "text": "b2"},
        ]
        lines = LayoutReorder()._cluster_words_into_lines(words)
        assert len(lines) == 2
        assert [w["text"] for w in lines[0]] == ["a1", "b1"]  # x-sorted
        assert [w["text"] for w in lines[1]] == ["a2", "b2"]

    def test_cluster_tolerance_boundary(self):
        # exactly 5px apart → new line (abs() < 5 is False)
        words = [
            {"x0": 10, "y0": 100, "text": "first"},
            {"x0": 10, "y0": 105, "text": "second"},
        ]
        lines = LayoutReorder()._cluster_words_into_lines(words)
        assert len(lines) == 2

    def test_reconstruct(self):
        lines = [[{"text": "a"}, {"text": "b"}], [{"text": "c"}]]
        assert LayoutReorder()._reconstruct_text_from_lines(lines) == "a b\nc"

    def test_is_same_content_ignores_whitespace(self):
        lr = LayoutReorder()
        assert lr._is_same_content("a b\nc", "ab\nc ") is True
        assert lr._is_same_content("a b", "b a") is False
