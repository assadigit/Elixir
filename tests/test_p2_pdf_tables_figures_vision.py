"""P2 (Test-Net Deepening) — hermetic tests for core/pdf/figure_table_cropper.py
and core/pdf/vision_figure_extractor.py.

Baselines: figure_table_cropper.py 0% (124/124 missed),
vision_figure_extractor.py 12% (131/149 missed).

Hermeticity strategy:
  - REAL PyMuPDF (fitz) builds the fixture PDFs: pages with drawn table grids
    (draw_rect + insert_text + caption text), pages embedding a REAL > 5 KB
    PNG (built deterministically with PIL + numpy), tiny-logo pages, blank and
    text pages. Extraction then runs REAL fitz / pdfplumber geometry — no PDF
    object is mocked.
  - The vision-model path (Ollama HTTP) is fully mocked: ModelManager is
    replaced by a recording fake and safe_ollama_request by canned responses.
  - fitz-absent branches use monkeypatch.setattr(module, "fitz", None) /
    sys.modules[...] = None (auto-restored).

REAL BUG PINNED HERE (reported, not fixed — no production edits allowed):
  pdfplumber 0.11.9's PageImage.save() quantizes to palette mode by default,
  so ``im.save(path, format="JPEG")`` raises OSError("cannot write mode P as
  JPEG"). figure_table_cropper.py:151 therefore NEVER saves a table crop on
  this stack — the per-table except swallows it silently. One test pins the
  failure; another shims PageImage.save (documented) to reach the success
  lines behind it (markdown writeout + manifest entries).

Run: COVERAGE_FILE=.coverage.p2b2 python3 -m pytest tests/test_p2_pdf_tables_figures_vision.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import core.pdf.vision_figure_extractor as vfe  # noqa: E402
from core.pdf.figure_table_cropper import (  # noqa: E402
    _extract_caption,
    _extract_caption_pdfplumber,
    _table_to_markdown,
    build_figure_table_manifest,
    extract_figures_and_tables,
)

# ── fitz PDF factory ────────────────────────────────────────────────────────


def _noise_png(size: int = 200) -> bytes:
    import io

    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _tiny_png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _make_figures_pdf(path: Path) -> Path:
    """4 pages:
    1 — drawn 4x3 table grid + "Table 1 ..." caption
    2 — embedded >5KB PNG + "Figure 1 ..." caption
    3 — embedded tiny logo PNG (must be skipped: < 5 KB)
    4 — plain text page (no figures/tables)
    """
    import fitz

    doc = fitz.open()
    # page 1 — table grid + caption
    page = doc.new_page(width=400, height=300)
    for r in range(4):
        for c in range(3):
            rect = fitz.Rect(50 + c * 100, 50 + r * 50, 50 + (c + 1) * 100, 50 + (r + 1) * 50)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((60 + c * 100, 80 + r * 50), f"cell{r}{c}", fontsize=10)
    page.insert_text((50, 280), "Table 1 Experimental data for the study.", fontsize=10)
    # page 2 — real figure
    page = doc.new_page(width=400, height=600)
    page.insert_text((40, 50), "Figure 1 A test figure showing results.", fontsize=10)
    page.insert_image(fitz.Rect(50, 100, 350, 400), stream=_noise_png())
    # page 3 — tiny logo (skipped by the 5KB rule)
    page = doc.new_page(width=400, height=600)
    page.insert_image(fitz.Rect(50, 100, 90, 140), stream=_tiny_png())
    # page 4 — plain text
    page = doc.new_page(width=400, height=600)
    page.insert_text((50, 100), "Just plain body text on the last page.", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def figures_pdf(tmp_path: Path) -> Path:
    return _make_figures_pdf(tmp_path / "figures.pdf")


@pytest.fixture()
def empty_pdf(tmp_path: Path) -> Path:
    import fitz

    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page(width=300, height=400)
    doc.new_page(width=300, height=400)
    doc.save(str(p))
    doc.close()
    return p


def _shim_pdfplumber_jpeg_save(monkeypatch):
    """Shim PageImage.save so JPEG saving works (works around the pdfplumber
    0.11.x palette-quantize incompatibility — see module docstring). The
    surrounding crop/markdown logic stays 100% real."""

    def _save(self, dest, format="PNG", **kwargs):  # noqa: A002 — PIL API name
        self.annotated.save(dest, format="JPEG", quality=85)

    monkeypatch.setattr("pdfplumber.display.PageImage.save", _save)


# ════════════════════════════════════════════════════════════════════════════
# figure_table_cropper — helpers
# ════════════════════════════════════════════════════════════════════════════


class TestTableToMarkdown:
    def test_empty(self):
        assert _table_to_markdown([]) == ""

    def test_none_cells_become_empty(self):
        out = _table_to_markdown([["a", None], [None, "d"]])
        assert out == "| a |  |\n| --- | --- |\n|  | d |"

    def test_normal(self):
        out = _table_to_markdown([["H1", "H2"], ["v1", "v2"]])
        assert out == "| H1 | H2 |\n| --- | --- |\n| v1 | v2 |"


class TestExtractCaptionFitz:
    def test_real_caption(self, figures_pdf):
        import fitz

        doc = fitz.open(str(figures_pdf))
        try:
            cap = _extract_caption(doc[1], 2, "figure")
        finally:
            doc.close()
        assert cap == "Figure 1 A test figure showing results."

    def test_no_caption_returns_empty(self, figures_pdf):
        import fitz

        doc = fitz.open(str(figures_pdf))
        try:
            assert _extract_caption(doc[3], 4, "figure") == ""
        finally:
            doc.close()

    def test_broken_page_returns_empty(self):
        class _BrokenPage:
            def get_text(self):
                raise RuntimeError("no text")

        assert _extract_caption(_BrokenPage(), 1, "figure") == ""

    def test_truncated_at_200_chars(self):
        class _Page:
            def get_text(self):
                return "Figure 9 " + "x" * 300 + ". end"

        cap = _extract_caption(_Page(), 1, "figure")
        assert len(cap) <= 200


class TestExtractCaptionPdfplumber:
    def test_real_caption(self, figures_pdf):
        import pdfplumber

        with pdfplumber.open(str(figures_pdf)) as pdf:
            cap = _extract_caption_pdfplumber(pdf.pages[0], 1, "table")
        assert cap == "Table 1 Experimental data for the study."

    def test_no_caption_returns_empty(self, figures_pdf):
        import pdfplumber

        with pdfplumber.open(str(figures_pdf)) as pdf:
            assert _extract_caption_pdfplumber(pdf.pages[3], 4, "table") == ""

    def test_broken_page_returns_empty(self):
        class _BrokenPage:
            def extract_text(self):
                raise RuntimeError("no text")

        assert _extract_caption_pdfplumber(_BrokenPage(), 1, "table") == ""


class TestBuildManifest:
    FIGS = [{"page": 2, "path": "/g/f.png", "caption": "Figure 1 caption", "type": "figure"}]
    TBLS = [{"page": 1, "path": "/t/t.jpg", "caption": "", "type": "table"}]

    def test_empty(self):
        out = build_figure_table_manifest([], [])
        assert "(No figures or tables detected in this document.)" in out

    def test_figures_only(self):
        out = build_figure_table_manifest(self.FIGS, [])
        assert "### Figures" in out
        assert "**Figure 1 caption** (page 2) — `/g/f.png`" in out
        assert "### Tables" not in out

    def test_tables_only(self):
        out = build_figure_table_manifest([], self.TBLS)
        assert "### Tables" in out
        assert "**Table** (page 1) — `/t/t.jpg`" in out

    def test_both(self):
        out = build_figure_table_manifest(self.FIGS, self.TBLS)
        assert "### Figures" in out and "### Tables" in out


# ════════════════════════════════════════════════════════════════════════════
# figure_table_cropper — extract_figures_and_tables
# ════════════════════════════════════════════════════════════════════════════


class TestExtractFiguresAndTables:
    def test_real_run_table_crop_save_fails_on_pdfplumber_011(self, figures_pdf, tmp_path):
        """REAL-BUG pin: with pdfplumber 0.11.9 the table crop's
        im.save(..., format="JPEG") raises OSError (palette mode) — the
        per-table except swallows it, so tables come back EMPTY despite a
        perfectly detected 4x3 grid. Figures (fitz part) still work."""
        logs: list[tuple[str, str]] = []
        figures, tables = extract_figures_and_tables(
            figures_pdf, tmp_path, total_pages=4, log_callback=lambda m, l: logs.append((m, l))
        )
        # Part 1 (fitz) — the real >5KB PNG is extracted with its caption
        assert len(figures) == 1
        fig = figures[0]
        assert fig["page"] == 2
        assert fig["type"] == "figure"
        assert fig["caption"] == "Figure 1 A test figure showing results."
        saved = tmp_path / "graphs" / "page2_figure1.png"
        assert saved.exists() and saved.stat().st_size > 5000
        assert fig["path"] == str(saved)
        # tiny logo on page 3 skipped (< 5 KB)
        assert not (tmp_path / "graphs" / "page3_figure2.png").exists()

        # Part 2 (pdfplumber) — the grid IS detected but the JPEG save fails
        assert tables == []
        assert any("Table extraction p.1 tbl 0" in m for m, _ in logs)
        assert not (tmp_path / "tables").exists() or not list((tmp_path / "tables").iterdir())

    def test_real_run_with_save_shim_extracts_table(self, figures_pdf, tmp_path, monkeypatch):
        """Same real PDF, with only PageImage.save shimmed (the documented
        pdfplumber incompatibility) → the full table pipeline runs: crop jpg,
        markdown twin file, manifest entry with caption + data."""
        _shim_pdfplumber_jpeg_save(monkeypatch)
        figures, tables = extract_figures_and_tables(figures_pdf, tmp_path, total_pages=4)

        assert len(tables) == 1
        tbl = tables[0]
        assert tbl["page"] == 1
        assert tbl["type"] == "table"
        assert tbl["caption"] == "Table 1 Experimental data for the study."
        jpg = tmp_path / "tables" / "page1_table1.jpg"
        assert jpg.exists() and jpg.read_bytes()[:2] == b"\xff\xd8"
        md = tmp_path / "tables" / "page1_table1.md"
        md_txt = md.read_text(encoding="utf-8")
        assert md_txt.startswith("| cell00")
        assert len(tbl["data"]) == 4  # 4 rows really extracted from the grid
        assert len(figures) == 1

    def test_valid_pages_restricts_scan(self, figures_pdf, tmp_path, monkeypatch):
        _shim_pdfplumber_jpeg_save(monkeypatch)
        figures, tables = extract_figures_and_tables(
            figures_pdf, tmp_path, total_pages=4, valid_pages={1}
        )
        # page 2 (the figure) was not scanned
        assert figures == []
        assert len(tables) == 1

    def test_total_pages_beyond_document(self, figures_pdf, tmp_path, monkeypatch):
        _shim_pdfplumber_jpeg_save(monkeypatch)
        figures, _tables = extract_figures_and_tables(figures_pdf, tmp_path, total_pages=9)
        # pages 5..9 don't exist — silently skipped, no crash
        assert len(figures) == 1

    def test_single_row_table_skipped(self, tmp_path, monkeypatch):
        import fitz

        p = tmp_path / "onrow.pdf"
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        for c in range(3):
            rect = fitz.Rect(50 + c * 100, 50, 50 + (c + 1) * 100, 100)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((60 + c * 100, 80), f"c{c}", fontsize=10)
        doc.save(str(p))
        doc.close()

        _shim_pdfplumber_jpeg_save(monkeypatch)
        figures, tables = extract_figures_and_tables(p, tmp_path / "out", total_pages=1)
        assert figures == []
        assert tables == []  # 1-row "table" is not worth extracting

    def test_fitz_missing_skips_figures(self, figures_pdf, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "fitz", None)
        logs: list[tuple[str, str]] = []
        figures, _tables = extract_figures_and_tables(
            figures_pdf, tmp_path, total_pages=1, log_callback=lambda m, l: logs.append((m, l))
        )
        assert figures == []
        assert any("PyMuPDF (fitz) not installed" in m for m, _ in logs)

    def test_pdfplumber_missing_skips_tables(self, figures_pdf, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        logs: list[tuple[str, str]] = []
        figures, tables = extract_figures_and_tables(
            figures_pdf, tmp_path, total_pages=2, log_callback=lambda m, l: logs.append((m, l))
        )
        assert tables == []
        assert len(figures) == 1  # fitz part unaffected
        assert any("pdfplumber not installed" in m for m, _ in logs)

    def test_garbage_file_fails_soft(self, tmp_path):
        bad = tmp_path / "garbage.pdf"
        bad.write_bytes(b"this is definitely not a pdf")
        logs: list[tuple[str, str]] = []
        figures, tables = extract_figures_and_tables(
            bad, tmp_path / "out", total_pages=1, log_callback=lambda m, l: logs.append((m, l))
        )
        assert figures == [] and tables == []
        msgs = [m for m, _ in logs]
        assert any("Figure extraction failed" in m for m in msgs)
        assert any("Table extraction failed" in m for m in msgs)

    def test_broken_xref_logged_and_skipped(self, figures_pdf, tmp_path, monkeypatch):
        import fitz

        def _boom(self, xref):
            raise RuntimeError("corrupt xref")

        monkeypatch.setattr(fitz.Document, "extract_image", _boom)
        logs: list[tuple[str, str]] = []
        figures, _tables = extract_figures_and_tables(
            figures_pdf, tmp_path, total_pages=2, log_callback=lambda m, l: logs.append((m, l))
        )
        assert figures == []
        assert any("Figure extraction p.2 img 0" in m for m, _ in logs)

    def test_base_image_none_skipped(self, figures_pdf, tmp_path, monkeypatch):
        import fitz

        monkeypatch.setattr(fitz.Document, "extract_image", lambda self, xref: None)
        figures, _tables = extract_figures_and_tables(figures_pdf, tmp_path, total_pages=2)
        assert figures == []

    def test_empty_image_bytes_skipped(self, figures_pdf, tmp_path, monkeypatch):
        import fitz

        monkeypatch.setattr(
            fitz.Document, "extract_image", lambda self, xref: {"image": b"", "ext": "png"}
        )
        figures, _tables = extract_figures_and_tables(figures_pdf, tmp_path, total_pages=2)
        assert figures == []

    def test_no_images_no_tables_document(self, empty_pdf, tmp_path, monkeypatch):
        _shim_pdfplumber_jpeg_save(monkeypatch)
        figures, tables = extract_figures_and_tables(empty_pdf, tmp_path, total_pages=2)
        assert figures == [] and tables == []
        # V10.2.2: no lazy folders created when nothing was found
        assert not (tmp_path / "graphs").exists()
        assert not (tmp_path / "tables").exists()


# ════════════════════════════════════════════════════════════════════════════
# vision_figure_extractor
# ════════════════════════════════════════════════════════════════════════════


class _FakeModelManager:
    """Recording stand-in for core.llm.ModelManager (no Ollama/network)."""

    def __init__(self):
        self.exists: set[str] = set()
        self.acquire_result = True
        self.calls: list[tuple[str, str]] = []

    def model_exists(self, name):
        self.calls.append(("exists", name))
        return name in self.exists

    def acquire_model(self, name, model_type=None, **kw):
        self.calls.append(("acquire", name))
        return self.acquire_result

    def release_model(self, name):
        self.calls.append(("release", name))
        return True


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture()
def fake_mm(monkeypatch):
    mm = _FakeModelManager()
    monkeypatch.setattr(vfe, "ModelManager", lambda: mm)
    return mm


def _vision_pdf(path: Path) -> Path:
    """2 pages: page 1 embeds a real PNG, page 2 has none."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    page.insert_image(fitz.Rect(50, 100, 350, 400), stream=_noise_png())
    doc.new_page(width=400, height=600)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def vision_pdf(tmp_path: Path) -> Path:
    return _vision_pdf(tmp_path / "vision.pdf")


class TestVisionInit:
    def test_defaults(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.pdf_path == vision_pdf
        assert v.model_name == "OlmOCR-2-7B:latest"
        assert v.fallback_model == "qwen3-vl:8b"
        assert v.timeout == 180
        assert v.retries == 2
        assert v._page_figure_text == {}
        assert v.ollama_base_url.startswith("http")

    def test_log_callback(self, vision_pdf, fake_mm):
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        v.log("hi", "DEBUG")
        assert msgs == [("hi", "DEBUG")]


class TestVisionExtractUnavailablePaths:
    def test_fitz_none_returns_empty(self, vision_pdf, fake_mm, monkeypatch):
        monkeypatch.setattr(vfe, "fitz", None)
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.extract() == {}
        assert any("PyMuPDF (fitz) not installed" in m for m, _ in msgs)

    def test_bad_pdf_returns_empty(self, tmp_path, fake_mm):
        missing = tmp_path / "missing.pdf"
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(missing, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.extract() == {}
        assert any("Failed to open PDF" in m for m, _ in msgs)

    def test_no_model_at_all(self, vision_pdf, fake_mm):
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        fake_mm.exists = set()  # neither primary nor fallback exists
        assert v.extract() == {}
        assert any("No vision model available" in m for m, _ in msgs)
        # no acquire/release attempted
        assert [c for c in fake_mm.calls if c[0] in ("acquire", "release")] == []

    def test_acquire_failure(self, vision_pdf, fake_mm):
        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        fake_mm.acquire_result = False
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.extract() == {}
        assert any("Failed to load vision model" in m for m, _ in msgs)

    def test_fallback_model_selected(self, vision_pdf, fake_mm, monkeypatch):
        fake_mm.exists = {"qwen3-vl:8b"}  # only the fallback exists
        responses: list[_FakeResponse] = []

        def fake_request(method, url, json=None, timeout=None, **kw):
            responses.append((method, url, json))
            return _FakeResponse({"response": "extracted axis labels"})

        monkeypatch.setattr(vfe, "safe_ollama_request", fake_request)
        v = vfe.VisionFigureExtractor(vision_pdf)
        result = v.extract(pages=[1])
        assert v.model_name == "qwen3-vl:8b"
        assert result == {1: ["extracted axis labels"]}
        assert ("acquire", "qwen3-vl:8b") in fake_mm.calls
        assert ("release", "qwen3-vl:8b") in fake_mm.calls
        # the request payload carries the fallback model + base64 image
        _method, _url, payload = responses[0]
        assert payload["model"] == "qwen3-vl:8b"
        assert payload["images"][0]


class TestVisionExtractSuccess:
    def _make(self, vision_pdf, fake_mm, monkeypatch, response_seq):
        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        calls: list[tuple] = []

        def fake_request(method, url, json=None, timeout=None, **kw):
            calls.append((method, url, json, timeout))
            return _FakeResponse(response_seq.pop(0) if response_seq else {"response": "txt"})

        monkeypatch.setattr(vfe, "safe_ollama_request", fake_request)
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        return v, calls, msgs

    def test_success_pages_list(self, vision_pdf, fake_mm, monkeypatch):
        v, calls, msgs = self._make(
            vision_pdf, fake_mm, monkeypatch, [{"response": "  chart labels  "}]
        )
        result = v.extract(pages=[1])
        assert result == {1: ["chart labels"]}
        assert ("release", "OlmOCR-2-7B:latest") in fake_mm.calls
        assert any("Page 1: extracted text from 1 images" in m for m, _ in msgs)
        # real prompt + b64 image sent to the (mocked) endpoint
        _m, url, payload, timeout = calls[0]
        assert url.endswith("/api/generate")
        assert payload["model"] == "OlmOCR-2-7B:latest"
        assert "Extract ALL text" in payload["prompt"]
        assert timeout == 180

    def test_success_all_pages_when_none(self, vision_pdf, fake_mm, monkeypatch):
        v, _calls, _msgs = self._make(vision_pdf, fake_mm, monkeypatch, [{"response": "r"}])
        result = v.extract()  # pages=None → every page
        # page 2 has no images → only page 1 in the result
        assert set(result) == {1}

    def test_page_beyond_document_skipped(self, vision_pdf, fake_mm, monkeypatch):
        v, _calls, _msgs = self._make(vision_pdf, fake_mm, monkeypatch, [])
        assert v.extract(pages=[99]) == {}
        # model still acquired and released
        assert ("acquire", "OlmOCR-2-7B:latest") in fake_mm.calls
        assert ("release", "OlmOCR-2-7B:latest") in fake_mm.calls

    def test_extract_image_none_continues(self, vision_pdf, fake_mm, monkeypatch):
        import fitz

        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        monkeypatch.setattr(fitz.Document, "extract_image", lambda self, xref: None)
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.extract(pages=[1]) == {}

    def test_extract_image_empty_bytes_continues(self, vision_pdf, fake_mm, monkeypatch):
        import fitz

        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        monkeypatch.setattr(fitz.Document, "extract_image", lambda self, xref: {"image": b""})
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.extract(pages=[1]) == {}

    def test_per_image_exception_logged(self, vision_pdf, fake_mm, monkeypatch):
        import fitz

        def _boom(self, xref):
            raise RuntimeError("cannot decode")

        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        monkeypatch.setattr(fitz.Document, "extract_image", _boom)
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.extract(pages=[1]) == {}
        assert any("Failed to process image 0 on page 1" in m for m, _ in msgs)

    def test_outer_loop_exception_logged(self, vision_pdf, fake_mm, monkeypatch):
        import fitz

        def _boom(self, full=False):
            raise ValueError("page exploded")

        fake_mm.exists = {"OlmOCR-2-7B:latest"}
        monkeypatch.setattr(fitz.Page, "get_images", _boom)
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.extract(pages=[1]) == {}
        assert any("Figure extraction error" in m for m, _ in msgs)
        # finally-branch: model released despite the exception
        assert ("release", "OlmOCR-2-7B:latest") in fake_mm.calls


class TestVisionExtractTextFromImage:
    def _v(self, vision_pdf, fake_mm, monkeypatch, responses, retries=2):
        fake_mm.exists = {"OlmOCR-2-7B:latest"}

        def fake_request(method, url, json=None, timeout=None, **kw):
            item = responses.pop(0) if responses else {"response": ""}
            if isinstance(item, Exception):
                raise item
            return _FakeResponse(item)

        monkeypatch.setattr(vfe, "safe_ollama_request", fake_request)
        monkeypatch.setattr(vfe.time, "sleep", lambda _s: None)  # no real retry backoff
        v = vfe.VisionFigureExtractor(vision_pdf)
        v.retries = retries
        return v

    def test_success_first_try(self, vision_pdf, fake_mm, monkeypatch):
        v = self._v(vision_pdf, fake_mm, monkeypatch, [{"response": "hello"}])
        assert v._extract_text_from_image(b"imgbytes", 1, 0) == "hello"

    def test_empty_then_success_retries(self, vision_pdf, fake_mm, monkeypatch):
        v = self._v(
            vision_pdf, fake_mm, monkeypatch, [{"response": "  "}, {"response": "second try"}]
        )
        assert v._extract_text_from_image(b"imgbytes", 1, 0) == "second try"

    def test_all_empty_returns_none(self, vision_pdf, fake_mm, monkeypatch):
        v = self._v(vision_pdf, fake_mm, monkeypatch, [{"response": ""}, {"response": ""}])
        assert v._extract_text_from_image(b"imgbytes", 1, 0) is None

    def test_exception_then_success(self, vision_pdf, fake_mm, monkeypatch):
        v = self._v(
            vision_pdf,
            fake_mm,
            monkeypatch,
            [RuntimeError("conn reset"), {"response": "recovered"}],
        )
        assert v._extract_text_from_image(b"imgbytes", 1, 0) == "recovered"

    def test_all_exceptions_returns_none(self, vision_pdf, fake_mm, monkeypatch):
        v = self._v(
            vision_pdf,
            fake_mm,
            monkeypatch,
            [RuntimeError("boom"), RuntimeError("boom2")],
        )
        assert v._extract_text_from_image(b"imgbytes", 1, 0) is None


class TestVisionInsertIntoMarkdown:
    def test_empty_cache_unchanged(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        md = "some markdown\n<!-- original page 1 -->\ntext\n"
        assert v.insert_into_markdown(md) == md

    def test_inserts_after_matching_marker(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        v._page_figure_text = {1: ["chart labels here"]}
        md = "intro\n<!-- original page 1 -->\nbody text\n<!-- original page 2 -->\nmore body"
        out = v.insert_into_markdown(md)
        assert "> **Figure extracted text:** chart labels here" in out
        # inserted directly after the page-1 marker line
        assert out.index("chart labels here") < out.index("body text")
        # page 2 marker untouched
        assert out.count("Figure extracted text") == 1

    def test_long_text_truncated_to_500(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        v._page_figure_text = {1: ["x" * 600]}
        out = v.insert_into_markdown("<!-- original page 1 -->\nbody")
        assert "x" * 500 in out
        assert "x" * 501 not in out

    def test_excess_newlines_collapsed(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        v._page_figure_text = {1: ["line1\n\n\n\n\nline2"]}
        out = v.insert_into_markdown("<!-- original page 1 -->\nbody")
        assert "line1\nline2" in out or "line1\n\nline2" in out
        assert "\n\n\n" not in out.split("Figure extracted text:** ")[1].split("\n\n")[0] + "\n"

    def test_multiple_texts_for_same_page(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        v._page_figure_text = {1: ["first", "second"]}
        out = v.insert_into_markdown("<!-- original page 1 -->\nbody")
        assert out.count("Figure extracted text") == 2


class TestVisionPageScanning:
    def test_page_has_figures_true_and_false(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.page_has_figures(1) is True
        assert v.page_has_figures(2) is False

    def test_page_has_figures_beyond_doc(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.page_has_figures(99) is False

    def test_page_has_figures_missing_file_crashes(self, tmp_path, fake_mm):
        # Suspected bug (pinned): fitz raises pymupdf.FileNotFoundError, which
        # is a RuntimeError subclass — NOT an OSError — so the ``except OSError``
        # in page_has_figures does not catch it and the call CRASHES on a
        # missing file instead of returning False.
        v = vfe.VisionFigureExtractor(tmp_path / "nope.pdf")
        with pytest.raises(RuntimeError):
            v.page_has_figures(1)

    def test_page_has_figures_fitz_none(self, vision_pdf, fake_mm, monkeypatch):
        monkeypatch.setattr(vfe, "fitz", None)
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.page_has_figures(1) is False

    def test_get_pages_with_figures(self, vision_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.get_pages_with_figures() == [1]

    def test_get_pages_with_figures_page_limit(self, vision_pdf, fake_mm):
        # page 1 is the only figure page; a limit of 1 still finds it,
        # while scanning a doc where figures are later would stop early.
        v = vfe.VisionFigureExtractor(vision_pdf)
        assert v.get_pages_with_figures(page_limit=1) == [1]

    def test_get_pages_with_figures_empty_doc(self, empty_pdf, fake_mm):
        v = vfe.VisionFigureExtractor(empty_pdf)
        assert v.get_pages_with_figures() == []

    def test_get_pages_with_figures_bad_file(self, tmp_path, fake_mm):
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(
            tmp_path / "nope.pdf", log_callback=lambda m, l: msgs.append((m, l))
        )
        assert v.get_pages_with_figures() == []
        assert any("Error scanning for figures" in m for m, _ in msgs)

    def test_get_pages_with_figures_fitz_none(self, vision_pdf, fake_mm, monkeypatch):
        monkeypatch.setattr(vfe, "fitz", None)
        msgs: list[tuple[str, str]] = []
        v = vfe.VisionFigureExtractor(vision_pdf, log_callback=lambda m, l: msgs.append((m, l)))
        assert v.get_pages_with_figures() == []
        assert any("PyMuPDF (fitz) not installed" in m for m, _ in msgs)
