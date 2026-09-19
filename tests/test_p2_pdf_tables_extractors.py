"""P2 (Test-Net Deepening) — hermetic tests for core/pdf/table_extractor.py and
core/pdf/table_graph_extractor.py.

Baselines: table_extractor.py 12% (88/100 missed), table_graph_extractor.py 0%
(166/166 missed).

Hermeticity strategy:
  - REAL PyMuPDF (fitz) is used to build small in-memory PDFs (drawn table
    grids via draw_rect + insert_text, an embedded real PNG image, text pages)
    and REAL pdfplumber shape detection runs against that page geometry.
  - REAL pdf2image (poppler's pdftoppm) renders the actual page screenshots.
  - REAL camelot is installed but its "lattice" flavor needs the ghostscript
    Python module (absent here) → the genuine per-page/per-call exception
    branches are exercised for free. The camelot SUCCESS paths are driven by
    monkeypatching ``camelot.read_pdf`` to return fake Table objects backed by
    real pandas DataFrames (the heavy external dep; everything downstream —
    markdown conversion, screenshot capture, .md building — runs real logic).
  - tabula-py shells out to java: monkeypatched (no subprocess in tests).

Run: COVERAGE_FILE=.coverage.p2b2 python3 -m pytest tests/test_p2_pdf_tables_extractors.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.pdf.table_extractor import TableExtractor  # noqa: E402
from core.pdf.table_graph_extractor import TableGraphExtractor  # noqa: E402

# ── fitz PDF factory ────────────────────────────────────────────────────────


def _make_grid_pdf(path: Path, rows: int = 4, cols: int = 3) -> Path:
    """A real PDF containing a drawn table grid with cell text."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    x0, y0, cw, ch = 50, 50, 100, 50
    for r in range(rows):
        for c in range(cols):
            rect = fitz.Rect(x0 + c * cw, y0 + r * ch, x0 + (c + 1) * cw, y0 + (r + 1) * ch)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((x0 + c * cw + 10, y0 + r * ch + 30), f"cell{r}{c}", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def _make_noise_png(size: int = 200) -> bytes:
    """A deterministic PNG (> 5 KB) built with PIL + numpy."""
    import io

    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _make_image_pdf(path: Path) -> Path:
    """A real PDF whose page 1 embeds a real > 5 KB PNG image."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_image(fitz.Rect(50, 100, 350, 400), stream=_make_noise_png())
    doc.save(str(path))
    doc.close()
    return path


def _make_text_pdf(path: Path, n_lines: int = 12) -> Path:
    """A text-heavy page (no shapes, no images → NOT visual per the scorer)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    line = "the quick brown fox jumps over the lazy dog while running through golden fields"
    y = 60
    for _ in range(n_lines):
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    doc.save(str(path))
    doc.close()
    return path


def _make_mixed_pdf(path: Path) -> Path:
    """3 pages: 1 = text-heavy, 2 = table grid, 3 = embedded image."""
    import fitz

    doc = fitz.open()
    # page 1 — text heavy
    page = doc.new_page(width=612, height=792)
    line = "the quick brown fox jumps over the lazy dog while running through golden fields"
    y = 60
    for _ in range(12):
        page.insert_text((50, y), line, fontsize=10)
        y += 15
    # page 2 — table grid
    page = doc.new_page(width=400, height=300)
    for r in range(4):
        for c in range(3):
            rect = fitz.Rect(50 + c * 100, 50 + r * 50, 50 + (c + 1) * 100, 50 + (r + 1) * 50)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((60 + c * 100, 80 + r * 50), f"cell{r}{c}", fontsize=10)
    # page 3 — image
    page = doc.new_page(width=400, height=600)
    page.insert_image(fitz.Rect(50, 100, 350, 400), stream=_make_noise_png())
    doc.save(str(path))
    doc.close()
    return path


# ── fake camelot/tabula stand-ins (success paths) ───────────────────────────


class _FakeCamelotTable:
    """Duck-typed camelot Table: .page + .df (real pandas DataFrame)."""

    def __init__(self, page: int, df):
        self.page = page
        self.df = df


class _NoMarkdownDf:
    """Duck-typed DataFrame WITHOUT .to_markdown → drives the manual fallback.

    Supports the full protocol both extractors need: .empty, .astype(),
    .itertuples(), .iterrows(), .columns (a pandas Index gives tolist()).
    """

    def __init__(self, columns, rows):
        import pandas as pd

        self.columns = pd.Index(columns)
        self._rows = rows
        self.empty = False

    def astype(self, _dtype):
        return self

    def itertuples(self, index=False):
        return list(self._rows)

    def iterrows(self):
        for row in self._rows:
            yield 0, row


def _pd():
    import pandas as pd

    return pd


@pytest.fixture()
def grid_pdf(tmp_path: Path) -> Path:
    return _make_grid_pdf(tmp_path / "grid.pdf")


@pytest.fixture()
def mixed_pdf(tmp_path: Path) -> Path:
    return _make_mixed_pdf(tmp_path / "mixed.pdf")


# ════════════════════════════════════════════════════════════════════════════
# TableExtractor
# ════════════════════════════════════════════════════════════════════════════


class TestTableExtractorInit:
    def test_defaults(self):
        te = TableExtractor()
        assert te.method == "camelot"
        assert te._camelot is None
        assert te._tabula is None
        assert callable(te.log)

    def test_init_camelot_real(self):
        te = TableExtractor()
        assert te._init_camelot() is True
        assert te._camelot is not None

    def test_init_camelot_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "camelot", None)
        te = TableExtractor()
        assert te._init_camelot() is False

    def test_init_tabula_real(self):
        te = TableExtractor()
        assert te._init_tabula() is True
        assert te._tabula is not None

    def test_init_tabula_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "tabula", None)
        te = TableExtractor()
        assert te._init_tabula() is False


class TestTableExtractorCamelot:
    def test_extract_success_with_fake_tables(self, grid_pdf, monkeypatch):
        import camelot

        pd = _pd()
        df1 = pd.DataFrame([["a", "b"], ["c", "d"]], columns=["H1", "H2"])
        df2 = pd.DataFrame([[1, 2], [3, 4]], columns=["C1", "C2"])
        monkeypatch.setattr(
            camelot,
            "read_pdf",
            lambda *a, **k: [_FakeCamelotTable(2, df1), _FakeCamelotTable(2, df2)],
        )
        logs: list[tuple[str, str]] = []
        te = TableExtractor(log_callback=lambda m, level="INFO": logs.append((m, level)))
        results = te.extract_tables_from_pdf(grid_pdf, pages="2")
        assert set(results) == {2}
        assert len(results[2]) == 2
        assert "H1" in results[2][0] and "a" in results[2][0]
        assert any("Camelot extracted 2 tables" in m for m, _ in logs)

    def test_extract_real_camelot_fails_gracefully(self, grid_pdf):
        # REAL camelot is installed but its lattice flavor requires the
        # ghostscript Python module (absent) → the except-branch must catch it.
        logs: list[tuple[str, str]] = []
        te = TableExtractor(log_callback=lambda m, level="INFO": logs.append((m, level)))
        results = te.extract_tables_from_pdf(grid_pdf, pages="1")
        assert results == {}
        assert any("Camelot extraction failed" in m for m, _ in logs)

    def test_extract_empty_dataframe_skipped(self, grid_pdf, monkeypatch):
        import camelot

        pd = _pd()
        monkeypatch.setattr(
            camelot, "read_pdf", lambda *a, **k: [_FakeCamelotTable(1, pd.DataFrame())]
        )
        te = TableExtractor()
        results = te.extract_tables_from_pdf(grid_pdf, pages="1")
        assert results == {}

    def test_extract_fallback_markdown_df(self, grid_pdf, monkeypatch):
        # a df-like object without .to_markdown still yields markdown rows
        import camelot

        fake_df = _NoMarkdownDf(columns=["A", "B"], rows=[("x", "y"), ("z", "w")])
        monkeypatch.setattr(camelot, "read_pdf", lambda *a, **k: [_FakeCamelotTable(3, fake_df)])
        te = TableExtractor()
        results = te.extract_tables_from_pdf(grid_pdf, pages="3")
        assert results == {3: ["| A | B |\n|---|---|\n| x | y |\n| z | w |"]}

    def test_camelot_table_to_markdown(self):
        pd = _pd()
        te = TableExtractor()
        md = te._camelot_table_to_markdown(
            _FakeCamelotTable(1, pd.DataFrame([["k", "v"]], columns=["K", "V"]))
        )
        assert md.splitlines()[0].startswith("| K")
        assert "| k | v |" in md


class TestTableExtractorTabula:
    def test_extract_success_with_fake_dfs(self, grid_pdf, monkeypatch):
        import tabula

        pd = _pd()
        df = pd.DataFrame([["m", "n"], ["o", "p"]], columns=["M", "N"])
        monkeypatch.setattr(tabula, "read_pdf", lambda *a, **k: [df, pd.DataFrame()])
        logs: list[tuple[str, str]] = []
        te = TableExtractor(
            method="tabula", log_callback=lambda m, level="INFO": logs.append((m, level))
        )
        results = te.extract_tables_from_pdf(grid_pdf, pages="all")
        # tabula tables land under page 0 (page unknown) — empty DFs skipped
        assert set(results) == {0}
        assert len(results[0]) == 1
        assert any("Tabula extracted 2 tables" in m for m, _ in logs)

    def test_extract_tabula_failure_logged(self, grid_pdf, monkeypatch):
        import tabula

        def _boom(*a, **k):
            raise RuntimeError("java exploded")

        monkeypatch.setattr(tabula, "read_pdf", _boom)
        logs: list[tuple[str, str]] = []
        te = TableExtractor(
            method="tabula", log_callback=lambda m, level="INFO": logs.append((m, level))
        )
        results = te.extract_tables_from_pdf(grid_pdf)
        assert results == {}
        assert any("Tabula extraction failed" in m for m, _ in logs)

    def test_extract_tabula_not_installed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "tabula", None)
        logs: list[tuple[str, str]] = []
        te = TableExtractor(
            method="tabula", log_callback=lambda m, level="INFO": logs.append((m, level))
        )
        assert te.extract_tables_from_pdf(Path("/nonexistent.pdf")) == {}
        assert any("Tabula not installed" in m for m, _ in logs)

    def test_extract_camelot_not_installed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "camelot", None)
        logs: list[tuple[str, str]] = []
        te = TableExtractor(log_callback=lambda m, level="INFO": logs.append((m, level)))
        assert te.extract_tables_from_pdf(Path("/nonexistent.pdf")) == {}
        assert any("Camelot not installed" in m for m, _ in logs)


class TestTableExtractorMarkdown:
    def test_dataframe_to_markdown_empty(self):
        pd = _pd()
        assert TableExtractor()._dataframe_to_markdown(pd.DataFrame()) == ""

    def test_dataframe_to_markdown_aligned(self):
        pd = _pd()
        df = pd.DataFrame([["short", "a"], ["muchlongervalue", "b"]], columns=["Head", "H"])
        md = TableExtractor()._dataframe_to_markdown(df)
        lines = md.splitlines()
        assert len(lines) == 4  # header + separator + 2 rows
        assert lines[1].startswith("|-") or set(lines[1]) <= {"-", "|"}
        # separator column widths follow the widest cell
        assert lines[0].index("|", 3) == lines[1].index("|", 3)

    def test_dataframe_to_markdown_stringifies_ints(self):
        pd = _pd()
        df = pd.DataFrame([[7, 8]], columns=["X", "Y"])
        md = TableExtractor()._dataframe_to_markdown(df)
        assert "| 7 | 8 |" in md


class TestInsertTablesIntoMarkdown:
    MD = "<!-- original page 1 -->\nFirst page text.\n\n<!-- original page 3 -->\nThird page text."

    def test_empty_dict_unchanged(self):
        te = TableExtractor()
        assert te.insert_tables_into_markdown(self.MD, {}) == self.MD

    def test_inline_insertion_at_marker(self):
        te = TableExtractor()
        out = te.insert_tables_into_markdown(self.MD, {3: ["| a | b |"]})
        assert "| a | b |" in out
        assert "### 📊 Tables from page 3" in out
        # inserted right after the page-3 marker, before its original text
        assert out.index("Tables from page 3") < out.index("Third page text.")

    def test_missing_marker_appended(self):
        te = TableExtractor()
        out = te.insert_tables_into_markdown(self.MD, {5: ["| q | r |"]})
        assert "## Extracted Tables" in out
        assert "### Tables from page 5" in out
        assert "| q | r |" in out

    def test_page_zero_lands_in_unknown_section(self):
        te = TableExtractor()
        out = te.insert_tables_into_markdown(self.MD, {0: ["| z |"]})
        assert "### Tables (page unknown)" in out
        assert "| z |" in out

    def test_mixed_inline_and_appended(self):
        te = TableExtractor()
        out = te.insert_tables_into_markdown(self.MD, {3: ["| a |"], 0: ["| b |"]})
        assert "### 📊 Tables from page 3" in out
        assert "### Tables (page unknown)" in out

    def test_multiple_tables_same_page(self):
        te = TableExtractor()
        out = te.insert_tables_into_markdown(self.MD, {3: ["| a |", "| b |"]})
        assert "| a |" in out and "| b |" in out


# ════════════════════════════════════════════════════════════════════════════
# TableGraphExtractor
# ════════════════════════════════════════════════════════════════════════════


class TestTableGraphExtractorInit:
    def test_defaults(self):
        tge = TableGraphExtractor()
        assert callable(tge.log)

    def test_log_callback(self):
        msgs: list[tuple[str, str]] = []
        tge = TableGraphExtractor(log_callback=lambda m, level="INFO": msgs.append((m, level)))
        tge.log("hello", "DEBUG")
        assert msgs == [("hello", "DEBUG")]


class TestScorePageVisual:
    """The static scorer — driven with duck-typed pages for every threshold
    branch, plus REAL pdfplumber pages from the fitz factory."""

    @staticmethod
    def _page(rects=(), lines=(), curves=(), images=(), words=()):
        class _P:
            pass

        p = _P()
        p.rects = list(rects)
        p.lines = list(lines)
        p.curves = list(curves)
        p.images = list(images)
        p.words = list(words)
        p.extract_words = lambda: list(words)
        return p

    def test_no_shapes_many_words_scores_zero(self):
        # a wordy page with no shapes/images → score 0 (words ≥ 100 → no bonus)
        page = self._page(words=[f"w{i}" for i in range(120)])
        assert TableGraphExtractor._score_page_visual(page) == 0

    def test_barely_any_words_scores_two(self):
        # a nearly-empty page (no words at all) gets the "mostly visual" bonus
        page = self._page()
        assert TableGraphExtractor._score_page_visual(page) == 2

    def test_image_strong_signal(self):
        page = self._page(images=["img"])
        assert TableGraphExtractor._score_page_visual(page) >= 3

    def test_many_rects(self):
        page = self._page(rects=[f"r{i}" for i in range(11)], words=[f"w{i}" for i in range(60)])
        # 2 (rects>10) + 1 (50≤words<100) = 3
        assert TableGraphExtractor._score_page_visual(page) == 3

    def test_medium_rects(self):
        page = self._page(rects=[f"r{i}" for i in range(6)], words=[f"w{i}" for i in range(60)])
        # 1 (5<rects≤10) + 1 = 2
        assert TableGraphExtractor._score_page_visual(page) == 2

    def test_curves(self):
        page = self._page(curves=[f"c{i}" for i in range(6)], words=[f"w{i}" for i in range(120)])
        # 2 (curves>5), words ≥ 100 → no bonus
        assert TableGraphExtractor._score_page_visual(page) == 2

    def test_few_curves(self):
        page = self._page(curves=["c"], words=[f"w{i}" for i in range(120)])
        assert TableGraphExtractor._score_page_visual(page) == 1

    def test_many_lines(self):
        page = self._page(lines=[f"l{i}" for i in range(21)], words=[f"w{i}" for i in range(120)])
        assert TableGraphExtractor._score_page_visual(page) == 1

    def test_low_word_count(self):
        page = self._page(words=["w1", "w2"])
        assert TableGraphExtractor._score_page_visual(page) == 2

    def test_exception_returns_zero(self):
        class _Broken:
            @property
            def rects(self):
                raise RuntimeError("no rects for you")

        assert TableGraphExtractor._score_page_visual(_Broken()) == 0

    def test_real_grid_page_is_visual(self, grid_pdf):
        import pdfplumber

        with pdfplumber.open(str(grid_pdf)) as pdf:
            page = pdf.pages[0]
            # drawn grid → 12 "curves" (+2), 12 words < 50 (+2) → 4 ≥ 3
            assert TableGraphExtractor._score_page_visual(page) >= 3

    def test_real_text_page_not_visual(self, tmp_path):
        import pdfplumber

        text_pdf = _make_text_pdf(tmp_path / "text.pdf")
        with pdfplumber.open(str(text_pdf)) as pdf:
            assert TableGraphExtractor._score_page_visual(pdf.pages[0]) < 3


class TestDetectVisualPages:
    def test_real_pdf_only_visual_pages(self, mixed_pdf):
        tge = TableGraphExtractor()
        visual = tge._detect_visual_pages(mixed_pdf, [1, 2, 3])
        # page 1 = text only; page 2 = grid (score 4); page 3 = image (score 3+)
        assert 2 in visual and 3 in visual
        assert 1 not in visual

    def test_out_of_range_pages_skipped(self, mixed_pdf):
        tge = TableGraphExtractor()
        assert tge._detect_visual_pages(mixed_pdf, [99]) == []

    def test_failure_falls_back_to_all_pages(self, tmp_path):
        tge = TableGraphExtractor()
        missing = tmp_path / "missing.pdf"
        assert tge._detect_visual_pages(missing, [4, 5]) == [4, 5]


class TestMarkdownBuilders:
    def test_build_tables_md_empty(self):
        out = TableGraphExtractor()._build_tables_md([])
        assert "No tables detected" in out

    def test_build_tables_md_entries(self):
        out = TableGraphExtractor()._build_tables_md(
            [{"number": 1, "page": 5, "markdown": "| a | b |", "screenshot": "/tmp/t.png"}]
        )
        assert "## Table 1 (Page 5)" in out
        assert "| a | b |" in out
        assert "/tmp/t.png" in out
        assert "Total tables extracted:** 1" in out

    def test_build_graphs_md_empty(self):
        out = TableGraphExtractor()._build_graphs_md([], total_pages=12, visual_count=0)
        assert "No pages with charts" in out
        assert "Pages scanned:** 12" in out

    def test_build_graphs_md_entries(self):
        out = TableGraphExtractor()._build_graphs_md(
            [
                {
                    "number": 1,
                    "page": 7,
                    "screenshot": "/tmp/g.png",
                    "note": "Page with detected visual elements",
                }
            ],
            total_pages=20,
            visual_count=1,
        )
        assert "## Page 7" in out
        assert "Visual pages detected:** 1" in out
        assert "/tmp/g.png" in out

    def test_df_to_markdown_fallback(self):
        fake_df = _NoMarkdownDf(columns=["A", "B"], rows=[("x", "y"), ("z", "w")])
        out = TableGraphExtractor()._df_to_markdown(fake_df)
        assert out == "| A | B |\n| --- | --- |\n| x | y |\n| z | w |"


class TestCapturePageScreenshot:
    def test_png_success(self, grid_pdf, tmp_path):
        tge = TableGraphExtractor()
        out = tmp_path / "shot.png"
        assert tge._capture_page_screenshot(grid_pdf, 1, out) is True
        assert out.read_bytes()[:4] == b"\x89PNG"

    def test_jpeg_success(self, grid_pdf, tmp_path):
        tge = TableGraphExtractor()
        out = tmp_path / "shot.jpg"
        assert tge._capture_page_screenshot(grid_pdf, 1, out, jpeg=True) is True
        assert out.read_bytes()[:2] == b"\xff\xd8"  # JPEG SOI

    def test_failure_returns_false(self, tmp_path):
        tge = TableGraphExtractor()
        assert tge._capture_page_screenshot(tmp_path / "nope.pdf", 1, tmp_path / "o.png") is False

    def test_pdf2image_missing_returns_false(self, grid_pdf, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdf2image", None)
        tge = TableGraphExtractor()
        assert tge._capture_page_screenshot(grid_pdf, 1, tmp_path / "o.png") is False


class TestTableGraphExtractorExtract:
    """Full extract() runs against a REAL 3-page PDF with real pdfplumber
    detection + real poppler rendering. Only camelot.read_pdf is stubbed for
    the table-found paths (the real camelot needs ghostscript → its genuine
    failure branch is asserted in the first test)."""

    def test_full_run_no_camelot_tables(self, mixed_pdf, tmp_path):
        logs: list[tuple[str, str]] = []
        tge = TableGraphExtractor(log_callback=lambda m, level="INFO": logs.append((m, level)))
        out_dir = tmp_path / "out"
        result = tge.extract(mixed_pdf, out_dir, [1, 2, 3], book_title="Agent of Influence!?")

        # camelot (real) fails per page on the missing ghostscript module
        assert result["table_count"] == 0
        # visual detection: grid page + image page
        assert result["graph_count"] == 2
        # every page screenshotted once (JPEG) + 2 graph PNGs
        assert result["screenshot_count"] == 3
        assert len(result["screenshots"]) == 5
        assert result["tables_md"] is None

        # tables.md — no entries variant
        tables_md = out_dir / "tables.md"
        assert "No tables detected" in tables_md.read_text(encoding="utf-8")
        # graphs.md — entries variant
        graphs_md = out_dir / "graphs.md"
        gtxt = graphs_md.read_text(encoding="utf-8")
        assert "## Page 2" in gtxt and "## Page 3" in gtxt
        assert "## Page 1" not in gtxt

        # folders + sanitized title in full-screenshot names
        screenshots_dir = out_dir / "screenshots"
        names = sorted(p.name for p in screenshots_dir.iterdir())
        assert names == [
            "page_001_Agent_of_Influence.jpg",
            "page_002_Agent_of_Influence.jpg",
            "page_003_Agent_of_Influence.jpg",
        ]
        assert (out_dir / "graphs" / "page_002.png").exists()
        assert (out_dir / "graphs" / "page_003.png").exists()

        debug_msgs = [m for m, lvl in logs if lvl == "DEBUG"]
        assert any("Table extraction p." in m for m in debug_msgs)  # real camelot failure
        assert any("Visual page detection: 2/3" in m for m, lvl in logs if lvl == "INFO")

    def test_full_run_empty_title_uses_page_word(self, mixed_pdf, tmp_path):
        tge = TableGraphExtractor()
        out_dir = tmp_path / "out"
        tge.extract(mixed_pdf, out_dir, [1], book_title="")
        names = sorted(p.name for p in (out_dir / "screenshots").iterdir())
        assert names == ["page_001_page.jpg"]

    def test_full_run_with_stubbed_camelot_tables(self, mixed_pdf, tmp_path, monkeypatch):
        import camelot

        pd = _pd()
        df = pd.DataFrame([["h1", "h2"], ["v1", "v2"]], columns=["H1", "H2"])

        def fake_read_pdf(path, pages=None, flavor=None, **kw):
            return [_FakeCamelotTable(int(pages), df)] if pages == "2" else []

        monkeypatch.setattr(camelot, "read_pdf", fake_read_pdf)

        tge = TableGraphExtractor()
        out_dir = tmp_path / "out"
        result = tge.extract(mixed_pdf, out_dir, [1, 2], book_title="Book")
        assert result["table_count"] == 1
        assert result["tables_md"] == out_dir / "tables.md"

        tables_md = (out_dir / "tables.md").read_text(encoding="utf-8")
        assert "## Table 1 (Page 2)" in tables_md
        assert "H1" in tables_md  # real pandas to_markdown output
        # table screenshot was really rendered
        assert (out_dir / "tables" / "table_001_p2.png").exists()

    def test_full_run_camelot_fallback_markdown(self, mixed_pdf, tmp_path, monkeypatch):
        import camelot

        fake_df = _NoMarkdownDf(columns=["A", "B"], rows=[("x", "y")])

        def fake_read_pdf(path, pages=None, flavor=None, **kw):
            return [_FakeCamelotTable(int(pages), fake_df)] if pages == "1" else []

        monkeypatch.setattr(camelot, "read_pdf", fake_read_pdf)

        tge = TableGraphExtractor()
        out_dir = tmp_path / "out"
        result = tge.extract(mixed_pdf, out_dir, [1], book_title="B")
        assert result["table_count"] == 1
        assert "| A | B |" in (out_dir / "tables.md").read_text(encoding="utf-8")

    def test_full_run_camelot_not_installed(self, mixed_pdf, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "camelot", None)
        logs: list[tuple[str, str]] = []
        tge = TableGraphExtractor(log_callback=lambda m, level="INFO": logs.append((m, level)))
        result = tge.extract(mixed_pdf, tmp_path / "out", [1], book_title="B")
        assert result["table_count"] == 0
        assert any("Camelot not installed" in m for m, _ in logs)

    def test_graph_screenshot_exception_is_caught(self, mixed_pdf, tmp_path, monkeypatch):
        tge = TableGraphExtractor()

        def _boom(pdf_path, page_num, output_path, jpeg=False):
            raise RuntimeError("renderer exploded")

        monkeypatch.setattr(tge, "_capture_page_screenshot", _boom)
        logs: list[tuple[str, str]] = []
        tge.log = lambda m, level="INFO": logs.append((m, level))
        result = tge.extract(mixed_pdf, tmp_path / "out", [2], book_title="B")
        # the visual page screenshot raised → no graph counted, no crash
        assert result["graph_count"] == 0
        assert any("Graph screenshot p.2" in m for m, _ in logs)

    def test_full_screenshot_exception_is_caught(self, mixed_pdf, tmp_path, monkeypatch):
        tge = TableGraphExtractor()
        real = tge._capture_page_screenshot

        def _raise_only_jpeg(pdf_path, page_num, output_path, jpeg=False):
            if jpeg:
                raise RuntimeError("jpeg render exploded")
            return real(pdf_path, page_num, output_path, jpeg=jpeg)

        monkeypatch.setattr(tge, "_capture_page_screenshot", _raise_only_jpeg)
        result = tge.extract(mixed_pdf, tmp_path / "out", [1], book_title="B")
        # every full-page (JPEG) screenshot raised → count 0, no crash
        assert result["screenshot_count"] == 0
