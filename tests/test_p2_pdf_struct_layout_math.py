"""Phase 2 (Test-Net Deepening) — hermetic tests for layout & math modules:

* ``core/pdf/lightweight_layout.py`` — pdfplumber-based multi-column
  detection and reading-order reordering, exercised against REAL two-column
  PDFs built with fitz.
* ``core/pdf/layout_analyzer.py`` — LayoutParser/Detectron2 integration.
  Neither package is installed here, so the ImportError path runs for real;
  the happy path is driven through stub ``layoutparser`` +
  ``pdf2image.convert_from_path`` modules (the model boundary).
* ``core/pdf/math_extractor.py`` — Pix2Tex / LaTeX-OCR integration. Neither
  engine is installed (real ImportError paths); happy paths use stub engine
  modules + a patched pdf2image renderer.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import fitz

from core.pdf.layout_analyzer import LayoutAnalyzer
from core.pdf.lightweight_layout import LightweightLayoutDetector
from core.pdf.math_extractor import MathExtractor


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    ``test_chapter_matcher_robust`` (and friends) install MagicMock stubs for
    heavy optional deps (pdfplumber among them) at collection time and never
    remove them; collection is alphabetical, so the stub is already in place
    when this file is imported and would silently poison the real-pdfplumber
    word-geometry tests below. Real modules are ``types.ModuleType``
    instances — MagicMocks are not — so drop it and let ``detect_and_reorder``'s
    lazy ``import pdfplumber`` resolve the real installed package.
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pdfplumber")
_ensure_real_module("PIL")  # real pdfplumber/Pillow interplay stays genuine

# ────────────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────────────


def _write(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


def _column_pdf(tmp_path: Path) -> Path:
    """Page 1: two columns; page 2: single column; page 3: sparse (<10 words)."""
    doc = fitz.open()
    # page 1 — two columns with a wide gutter (50..170 vs 320..440)
    p1 = doc.new_page(width=612, height=792)
    y = 100
    for i in range(3):
        p1.insert_text((50, y), f"Left column line {i}", fontname="cour", fontsize=10)
        p1.insert_text((320, y), f"Right column line {i}", fontname="cour", fontsize=10)
        y += 30
    # page 2 — single column, words spread across the midline
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((100, 100), "Single column wide text spanning", fontname="cour", fontsize=10)
    p2.insert_text((140, 130), "across the middle of the page", fontname="cour", fontsize=10)
    p2.insert_text((120, 160), "with plenty of words present", fontname="cour", fontsize=10)
    # page 3 — sparse (only 6 words)
    p3 = doc.new_page(width=612, height=792)
    p3.insert_text((50, 100), "Left column line", fontname="cour", fontsize=10)
    p3.insert_text((320, 100), "Right column line", fontname="cour", fontsize=10)
    return _write(doc, tmp_path, "columns.pdf")


# ────────────────────────────────────────────────────────────────────────────
# lightweight_layout
# ────────────────────────────────────────────────────────────────────────────


class TestLightweightLayoutDetectAndReorder:
    def test_two_column_page_reordered(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(_column_pdf(tmp_path), [1])
        assert 1 in results
        text = results[1]
        # left column comes first even though right-column text sits higher
        # on the page in extraction order
        assert text.index("Left column line 0") < text.index("Right column line 0")
        assert text.index("Left column line 2") < text.index("Right column line 0")

    def test_single_column_page_not_in_results(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(_column_pdf(tmp_path), [2])
        assert 2 not in results

    def test_sparse_page_skipped(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(_column_pdf(tmp_path), [3])
        assert 3 not in results

    def test_invalid_page_numbers_skipped(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(_column_pdf(tmp_path), [0, -1, 99])
        assert results == {}

    def test_missing_file_returns_empty(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(tmp_path / "nope.pdf", [1])
        assert results == {}

    def test_pdfplumber_import_error_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        detector = LightweightLayoutDetector()
        assert detector.detect_and_reorder(_column_pdf(tmp_path), [1]) == {}

    def test_spacing_cleanup_in_output(self, tmp_path):
        detector = LightweightLayoutDetector()
        results = detector.detect_and_reorder(_column_pdf(tmp_path), [1])
        # no double spaces survive the cleanup pass
        assert "  " not in results[1]


class TestDetectColumns:
    def _detector(self):
        return LightweightLayoutDetector()

    def _word(self, x0, x1, text="w"):
        return {"x0": x0, "x1": x1, "text": text, "top": 0}

    def test_no_left_words_single_column(self):
        cols = self._detector()._detect_columns([self._word(400, 420)], 612)
        assert cols == [(0, 612)]

    def test_no_right_words_single_column(self):
        cols = self._detector()._detect_columns([self._word(50, 70)], 612)
        assert cols == [(0, 612)]

    def test_small_gap_single_column(self):
        # left word ends at 290; right word starts at 310 — past the 306
        # midline, so both halves are populated, but the 20pt gutter is
        # under 5% of the 612pt page -> single column.
        words = [self._word(50, 290), self._word(310, 500)]
        cols = self._detector()._detect_columns(words, 612)
        assert cols == [(0, 612)]  # gap 20 < 5% of 612

    def test_wide_gap_two_columns(self):
        words = [self._word(50, 170), self._word(320, 500)]
        cols = self._detector()._detect_columns(words, 612)
        assert len(cols) == 2
        assert cols[0] == (50, 170)
        assert cols[1] == (320, 500)


class TestReorderByColumns:
    def test_words_sorted_column_then_position(self):
        detector = LightweightLayoutDetector()
        words = [
            {"x0": 320, "x1": 400, "top": 50, "text": "right-top"},
            {"x0": 50, "x1": 100, "top": 200, "text": "left-bottom"},
            {"x0": 50, "x1": 100, "top": 50, "text": "left-top"},
        ]
        reordered = detector._reorder_by_columns(words, [(50, 100), (320, 400)])
        assert [w["text"] for w in reordered] == ["left-top", "left-bottom", "right-top"]

    def test_word_outside_all_columns_dropped(self):
        detector = LightweightLayoutDetector()
        words = [
            {"x0": 50, "x1": 100, "top": 10, "text": "inside"},
            {"x0": 500, "x1": 550, "top": 10, "text": "outside"},
        ]
        reordered = detector._reorder_by_columns(words, [(50, 100)])
        assert [w["text"] for w in reordered] == ["inside"]


# ────────────────────────────────────────────────────────────────────────────
# layout_analyzer
# ────────────────────────────────────────────────────────────────────────────


class _FakeBlock:
    def __init__(self, block_type, x1=0, y1=0, x2=10, y2=10):
        self.type = block_type
        self.x_1 = x1
        self.y_1 = y1
        self.x_2 = x2
        self.y_2 = y2


def _make_layoutparser_stub(blocks, detect_raises=False):
    """A stub `layoutparser` module whose Detectron2 model returns `blocks`."""
    module = types.ModuleType("layoutparser")
    models = types.ModuleType("layoutparser.models")

    class _FakeModel:
        init_kwargs = None

        def __init__(self, config, extra_config=None, label_map=None):
            _FakeModel.init_kwargs = {
                "config": config,
                "extra_config": extra_config,
                "label_map": label_map,
            }

        def detect(self, img):
            if detect_raises:
                raise RuntimeError("detectron exploded")
            return blocks

    models.Detectron2LayoutModel = _FakeModel
    module.models = models
    return module, _FakeModel


class TestLayoutAnalyzer:
    def test_init_without_layoutparser(self):
        analyzer = LayoutAnalyzer()
        # layoutparser is not installed in this environment
        assert analyzer._init_layoutparser() is False
        assert analyzer._layoutparser is None

    def test_init_with_stubbed_module(self, monkeypatch):
        module, _ = _make_layoutparser_stub([])
        monkeypatch.setitem(sys.modules, "layoutparser", module)
        analyzer = LayoutAnalyzer()
        assert analyzer._init_layoutparser() is True
        assert analyzer._layoutparser is module

    def test_analyze_layout_without_engine_returns_empty(self, tmp_path):
        analyzer = LayoutAnalyzer()
        assert analyzer.analyze_layout(tmp_path / "any.pdf", [1]) == {}

    def test_analyze_layout_happy_path(self, tmp_path, monkeypatch):
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        path = _write(doc, tmp_path, "layout.pdf")
        blocks = [
            _FakeBlock("Text", 10, 10, 100, 50),
            _FakeBlock("Title", 10, 60, 100, 90),
            _FakeBlock("List", 10, 95, 100, 120),
            _FakeBlock("Figure", 200, 10, 400, 300),  # filtered out
        ]
        module, model_cls = _make_layoutparser_stub(blocks)
        monkeypatch.setitem(sys.modules, "layoutparser", module)
        monkeypatch.setitem(sys.modules, "layoutparser.models", module.models)
        monkeypatch.setattr("pdf2image.convert_from_path", lambda *a, **k: ["img1", "img2"])
        logs: list[tuple[str, str]] = []
        analyzer = LayoutAnalyzer(log_callback=lambda m, l="INFO": logs.append((l, m)))
        results = analyzer.analyze_layout(path, [1, 2])
        assert set(results.keys()) == {1, 2}
        for page_blocks in results.values():
            assert [b["type"] for b in page_blocks] == ["Text", "Title", "List"]
            assert page_blocks[0] == {"type": "Text", "x1": 10, "y1": 10, "x2": 100, "y2": 50}
        # model wired with the PubLayNet config
        assert "PubLayNet" in model_cls.init_kwargs["config"]
        assert any("found 3 text blocks" in m for _, m in logs)

    def test_analyze_layout_detect_failure_returns_empty(self, tmp_path, monkeypatch):
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        path = _write(doc, tmp_path, "layout2.pdf")
        module, _ = _make_layoutparser_stub([], detect_raises=True)
        monkeypatch.setitem(sys.modules, "layoutparser", module)
        monkeypatch.setattr("pdf2image.convert_from_path", lambda *a, **k: ["img1"])
        logs: list[tuple[str, str]] = []
        analyzer = LayoutAnalyzer(log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert analyzer.analyze_layout(path, [1]) == {}
        assert any("Layout analysis failed" in m for _, m in logs)

    def test_reorder_markdown_empty_layout_unchanged(self):
        analyzer = LayoutAnalyzer()
        assert analyzer.reorder_markdown_by_layout("some markdown", {}) == "some markdown"

    def test_reorder_markdown_logs_and_returns_unchanged(self):
        logs: list[tuple[str, str]] = []
        analyzer = LayoutAnalyzer(log_callback=lambda m, l="INFO": logs.append((l, m)))
        layout = {1: [{"type": "Text", "x1": 0, "y1": 0, "x2": 10, "y2": 10}]}
        result = analyzer.reorder_markdown_by_layout("# Heading\nbody", layout)
        assert result == "# Heading\nbody"
        assert any("reordering not yet implemented" in m for _, m in logs)


# ────────────────────────────────────────────────────────────────────────────
# math_extractor
# ────────────────────────────────────────────────────────────────────────────


def _make_pix2tex_stub(result="$x^2$"):
    module = types.ModuleType("pix2tex")

    class _Pix2Tex:
        calls = []

        def __init__(self):
            pass

        def __call__(self, img):
            _Pix2Tex.calls.append(img)
            return result

    module.Pix2Tex = _Pix2Tex
    return module, _Pix2Tex


def _make_latexocr_stub(result="$y = f(x)$"):
    module = types.ModuleType("latexocr")

    class _LatexOCR:
        calls = []

        def __init__(self):
            pass

        def __call__(self, img):
            _LatexOCR.calls.append(img)
            return result

    module.LatexOCR = _LatexOCR
    return module, _LatexOCR


class TestMathExtractorInit:
    def test_pix2tex_not_installed(self):
        logs: list[tuple[str, str]] = []
        extractor = MathExtractor(log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert extractor._init_pix2tex() is False
        assert any("Pix2Tex not installed" in m for _, m in logs)

    def test_latexocr_not_installed(self):
        logs: list[tuple[str, str]] = []
        extractor = MathExtractor(log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert extractor._init_latexocr() is False
        assert any("LaTeX-OCR not installed" in m for _, m in logs)

    def test_pix2tex_stubbed_success(self, monkeypatch):
        module, _ = _make_pix2tex_stub()
        monkeypatch.setitem(sys.modules, "pix2tex", module)
        logs: list[tuple[str, str]] = []
        extractor = MathExtractor(log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert extractor._init_pix2tex() is True
        assert any("Pix2Tex loaded" in m for _, m in logs)

    def test_latexocr_stubbed_success(self, monkeypatch):
        module, _ = _make_latexocr_stub()
        monkeypatch.setitem(sys.modules, "latexocr", module)
        extractor = MathExtractor()
        assert extractor._init_latexocr() is True


class TestExtractMathFromPdf:
    def _pdf(self, tmp_path):
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        doc.new_page(width=612, height=792)
        return _write(doc, tmp_path, "math.pdf")

    def test_pix2tex_engine_not_installed_returns_empty(self, tmp_path):
        extractor = MathExtractor()
        assert extractor.extract_math_from_pdf(self._pdf(tmp_path), [1, 2]) == {}

    def test_latexocr_engine_not_installed_returns_empty(self, tmp_path):
        extractor = MathExtractor(model="latexocr")
        assert extractor.extract_math_from_pdf(self._pdf(tmp_path), [1, 2]) == {}

    def test_pix2tex_success(self, tmp_path, monkeypatch):
        module, cls = _make_pix2tex_stub("$x^2$")
        monkeypatch.setitem(sys.modules, "pix2tex", module)
        monkeypatch.setattr("pdf2image.convert_from_path", lambda *a, **k: ["img-1", "img-2"])
        logs: list[tuple[str, str]] = []
        extractor = MathExtractor(log_callback=lambda m, l="INFO": logs.append((l, m)))
        results = extractor.extract_math_from_pdf(self._pdf(tmp_path), [1, 2])
        assert results == {1: ["$x^2$"], 2: ["$x^2$"]}
        assert len(cls.calls) == 2
        assert any("Extracted math from page 1" in m for _, m in logs)

    def test_latexocr_success(self, tmp_path, monkeypatch):
        module, cls = _make_latexocr_stub()
        monkeypatch.setitem(sys.modules, "latexocr", module)
        monkeypatch.setattr("pdf2image.convert_from_path", lambda *a, **k: ["img-1"])
        extractor = MathExtractor(model="latexocr")
        results = extractor.extract_math_from_pdf(self._pdf(tmp_path), [1])
        assert results == {1: ["$y = f(x)$"]}

    def test_empty_latex_skipped(self, tmp_path, monkeypatch):
        module, _ = _make_pix2tex_stub(result="   ")
        monkeypatch.setitem(sys.modules, "pix2tex", module)
        monkeypatch.setattr("pdf2image.convert_from_path", lambda *a, **k: ["img-1"])
        extractor = MathExtractor()
        assert extractor.extract_math_from_pdf(self._pdf(tmp_path), [1]) == {}

    def test_rendering_failure_returns_empty(self, tmp_path, monkeypatch):
        module, _ = _make_pix2tex_stub()
        monkeypatch.setitem(sys.modules, "pix2tex", module)

        def _boom(*a, **k):
            raise RuntimeError("poppler missing")

        monkeypatch.setattr("pdf2image.convert_from_path", _boom)
        logs: list[tuple[str, str]] = []
        extractor = MathExtractor(log_callback=lambda m, l="INFO": logs.append((l, m)))
        assert extractor.extract_math_from_pdf(self._pdf(tmp_path), [1]) == {}
        assert any("Math extraction failed" in m for _, m in logs)


class TestInsertMathIntoMarkdown:
    def test_empty_math_dict_unchanged(self):
        extractor = MathExtractor()
        md = "<!-- original page 1 -->\n# Heading\nbody"
        assert extractor.insert_math_into_markdown(md, {}) == md

    def test_math_inserted_after_page_markers(self):
        extractor = MathExtractor()
        md = "<!-- original page 1 -->\n# Heading\n<!-- original page 2 -->\n## Second\n"
        result = extractor.insert_math_into_markdown(md, {1: ["$a$", "$b$"], 3: ["$c$"]})
        lines = result.splitlines()
        assert lines[0] == "<!-- original page 1 -->"
        assert lines[1:7] == ["```latex", "$a$", "```", "", "```latex", "$b$"]
        # page 2 has no math: its marker is followed by the heading directly
        assert "<!-- original page 2 -->" in lines
        idx2 = lines.index("<!-- original page 2 -->")
        assert lines[idx2 + 1] == "## Second"
        # page 3 is not in the markdown -> its math is simply not inserted
        assert "$c$" not in result
