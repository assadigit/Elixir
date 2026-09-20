"""Phase 4.5 (Edge-case fixtures) — EXTRACTION-side characterization.

Multi-column, monospaced tables, and Farsi/RTL pages, pinned against REAL
in-memory PDFs built with PyMuPDF (fitz).

Survey — what is already pinned elsewhere (NOT duplicated here):
  * Reading-order REPAIR modules: core/pdf/layout_reorder.py (including the
    BUG A "feature-dead" and BUG B "crash" pins) in
    tests/test_p2_pdf_tables_layout_reorder.py; core/pdf/lightweight_layout.py
    in tests/test_p2_pdf_struct_layout_math.py.
  * Per-page scanned/digital classification of plain text + blank pages in
    tests/test_p2_pdf_struct_analyzer.py; the pre-scan heuristic (mocked
    readers) in tests/test_ocr_prescan.py.
  * Table grids WITH drawn ruling lines + camelot success paths in
    tests/test_p2_pdf_tables_extractors.py.
  * The SUMMARIZATION side of OCR-artifact / multicolumn-interleaved / Farsi
    text: Phase 4.1 golden chapters + tests/test_golden_freeze.py.

What this file ADDS (the extraction side — PDF → raw_markdown):
  * What the converter's digital-extraction tier actually emits. The entry
    point is OCRService.process_pdf + build_markdown (called by
    core.pipeline.conversion.extraction.run_extraction, Step 3/4). The dev
    sandbox has no markitdown, so ``_md_tool`` is forced to None — pinning
    the pypdf tier deterministically (markitdown's own output shape is
    version-dependent and is only the tier-1 gate, pinned separately in
    test_p4_edge_cases_ocr.py).
  * Raw-extractor reading order: pypdf returns CONTENT-STREAM (insertion)
    order — a two-column page whose right column was written first extracts
    right-column-first; pdfplumber merges same-baseline lines ROW-INTERLEAVED.
  * Monospaced whitespace tables: pypdf preserves the column alignment,
    pdfplumber collapses it to single spaces, and camelot's "lattice" flavor
    finds NOTHING without ruling lines (camelot is an optional extra anyway).
  * Farsi pages embedded with real Arabic shaping (PyMuPDF Story engine,
    ``insert_htmlbox`` — hermetic: bundled fallback fonts, verified to work
    with an empty fontconfig): BOTH extractors return PRESENTATION-FORM
    codepoints (U+FB50–U+FEFF) in visual (per-word reversed) order; the
    logical string is NOT recoverable; a short Persian page is misclassified
    as "scanned" because the analyzer word regex covers U+0600–U+06FF but
    NOT the presentation forms.

Hermeticity: real fitz/pypdf/pdfplumber only; no network; no tesseract; the
OCRService is driven with a stub ModelManager and a Settings override so no
Ollama/torch is ever probed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    Same hygiene as the p2 pdf suites: test_chapter_matcher_robust (and
    friends) install MagicMock stubs for pypdf/PIL/pdfplumber at collection
    time and never remove them; collection is alphabetical, so a stub may
    already be in place when this file is imported. Real modules are
    ``types.ModuleType`` instances — MagicMocks are not — so drop them before
    the real imports below.
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pypdf")
_ensure_real_module("PIL")
_ensure_real_module("pdfplumber")

import fitz  # noqa: E402 — after stub cleanup
import pdfplumber  # noqa: E402 — after stub cleanup
import pytest  # noqa: E402 — after stub cleanup
from pypdf import PdfReader  # noqa: E402 — after stub cleanup

import core.ocr.service as _ocr_service_module  # noqa: E402 — after stub cleanup

# Repair production bindings that may have been made while a MagicMock pypdf
# was in sys.modules (house pattern from test_p2_pdf_struct_analyzer.py).
import core.pdf.analyzer as _analyzer_module  # noqa: E402 — after stub cleanup
from core.models import (  # noqa: E402 — after stub cleanup
    ConversionRequest,
    PageAnalysis,
    PdfAnalysisResult,
    PdfRecommendation,
)
from core.ocr.ocr_prescan import prescan_pages  # noqa: E402 — after stub cleanup
from core.ocr.service import OCRService  # noqa: E402 — after stub cleanup
from core.pdf.analyzer import PdfAnalyzer  # noqa: E402 — after stub cleanup
from core.pdf.lightweight_layout import LightweightLayoutDetector  # noqa: E402 — after stub cleanup
from core.pdf.table_extractor import TableExtractor  # noqa: E402 — after stub cleanup
from utils.settings import Settings  # noqa: E402 — after stub cleanup

if not isinstance(_analyzer_module.PdfReader, type):
    _analyzer_module.PdfReader = PdfReader
if not isinstance(_ocr_service_module.PdfReader, type):
    _ocr_service_module.PdfReader = PdfReader
if not isinstance(_ocr_service_module.PdfWriter, type):
    from pypdf import PdfWriter

    _ocr_service_module.PdfWriter = PdfWriter

# ── fixture content ─────────────────────────────────────────────────────────
# Two coherent, distinct column texts (Suez-canal themed, matching the Phase
# 4.1 golden chapter family). Both fit inside their half of a 612pt page so
# fitz does not clip the last glyphs off the page edge.

LEFT_TEXT = "The port city grew around a safe natural harbour."
RIGHT_TEXT = "Engineers surveyed the desert route twice."
N_LINES = 3

TABLE_ROWS = [
    ["Name", "Qty", "Price", "Total"],
    ["Widget", "3", "12.50", "37.50"],
    ["Gadget", "12", "4.25", "51.00"],
]

# The Persian fixture is copied (at test time, byte-exactly) from the frozen
# Phase 4.1 golden chapter tests/golden/farsi/source_chapter.md — first
# sentence of the first paragraph.
PERSIAN_WORD = "کانال سوئز"


def _golden_farsi_sentence() -> str:
    src = Path(__file__).resolve().parent / "golden" / "farsi" / "source_chapter.md"
    text = src.read_text(encoding="utf-8")
    para = next(p for p in text.split("\n\n") if p.strip() and not p.startswith("#"))
    return para.split(".")[0] + "."


# ── fitz PDF factories ──────────────────────────────────────────────────────


def _write(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


def _two_col_pdf(tmp_path: Path, right_first: bool = True, n_pages: int = 2) -> Path:
    """Two-column pages (left x=50, right x=320 — 150pt gutter).

    By default the RIGHT column is inserted first, so the raw content-stream
    order (right, then left) differs from reading order (left first) — the
    classic academic-paper shape the layout-repair modules exist for.
    """
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        columns = [(50, LEFT_TEXT), (320, RIGHT_TEXT)]
        if right_first:
            columns.reverse()  # right column written first => content-stream order
        for x, text in columns:
            for i in range(N_LINES):
                page.insert_text((x, 80 + 20 * i), text, fontsize=11)
    return _write(doc, tmp_path, "twocol.pdf")


def _table_pdf(tmp_path: Path) -> Path:
    """A 3x4 value grid laid out as monospaced columns — one text insert per
    row, cells padded with .ljust(12). NO ruling lines are drawn: this is the
    whitespace-only table shape (plain-text style), not camelot's lattice."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 100
    for row in TABLE_ROWS:
        page.insert_text(
            (72, y), "".join(cell.ljust(12) for cell in row), fontname="cour", fontsize=11
        )
        y += 20
    return _write(doc, tmp_path, "table.pdf")


def _persian_pdf(tmp_path: Path, sentence: str | None = None, name: str = "farsi.pdf") -> Path:
    """A real shaped-Persian page (PyMuPDF Story engine: proper bidi + Arabic
    shaping + bundled fallback fonts — verified hermetic against an empty
    fontconfig). This is what real-world Farsi PDFs embed: presentation-form
    glyphs, not logical-order characters."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    sent = sentence if sentence is not None else _golden_farsi_sentence()
    rc = page.insert_htmlbox(fitz.Rect(50, 80, 560, 260), f"<p>{PERSIAN_WORD}</p><p>{sent}</p>")
    assert rc[1] == 1.0  # fully placed
    return _write(doc, tmp_path, name)


# ── hermetic OCRService (converter digital-extraction tier) ────────────────


class _P4Settings:
    """Deterministic offline Settings (drives the real Settings._test_override
    DI hook — same recipe as tests/test_p2_summarizer_harness.py)."""

    def __init__(self, values: dict | None = None):
        self._values = {
            "paths.poppler": "",
            "paths.tesseract": "",
            "ocr.use_paddleocr": False,
            "ocr.unlimited_ocr_path": "",
            "ocr.image_dpi": 300,
            "ocr.timeout": 120,
            "local.ocr_parallel_workers": 1,
            "ocr.vlm_fallback_model": "",
        }
        if values:
            self._values.update(values)

    def get(self, key: str, default=None):
        return self._values.get(key, default)

    def get_ollama_url(self) -> str:
        return "http://localhost:11434"


class _StubModelManager:
    """No Ollama, no torch, no network — records probes for assertions."""

    def __init__(self):
        self.exists_calls: list[str] = []
        self.acquire_calls: list[str] = []

    def get_loaded_models(self):
        return []

    def model_exists(self, name):
        self.exists_calls.append(name)
        return False

    def acquire_model(self, name, *a, **k):
        self.acquire_calls.append(name)
        return False

    def release_model(self, *a, **k):
        pass

    def force_unload(self, *a, **k):
        pass


@pytest.fixture(autouse=True)
def _hermetic_settings():
    prev = Settings._test_override
    Settings._test_override = _P4Settings()
    yield
    Settings._test_override = prev


def _converter_extraction(pdf_path: Path, md_tool=None):
    """Run the converter's extraction phase exactly as
    core.pipeline.conversion.extraction.run_extraction does (Steps 3–4):
    OCRService(...).process_pdf() → build_markdown(). No page is flagged
    scanned, so every page goes down the DIGITAL tier — the path a text-layer
    multi-column / table / Farsi page actually takes."""
    logs: list[tuple[str, str]] = []

    def log(msg, level="INFO"):
        logs.append((level, msg))

    total = len(PdfReader(str(pdf_path)).pages)
    request = ConversionRequest(input_path=pdf_path, output_dir=pdf_path.parent)
    analysis = PdfAnalysisResult(
        total_pages=total,
        scanned_pages=[],
        text_pages=list(range(1, total + 1)),
        recommendation=PdfRecommendation.NO_OCR,
        per_page=[PageAnalysis(i, False, "", "skip") for i in range(1, total + 1)],
    )
    service = OCRService(request, analysis, [], log_callback=log)
    service.model_manager = _StubModelManager()
    service._md_tool = md_tool  # None → pin the pypdf tier (markitdown is env-dependent)
    results = service.process_pdf(pdf_path)
    return results, OCRService.build_markdown(results), logs


# ════════════════════════════════════════════════════════════════════════════
# 1. Multi-column
# ════════════════════════════════════════════════════════════════════════════


class TestMultiColumnExtraction:
    def test_pypdf_extraction_follows_content_stream_order(self, tmp_path):
        """pypdf (tier-3 digital extraction + the analyzer's scanned probe)
        returns text in CONTENT-STREAM order: with the right column written
        first, all RIGHT lines precede all LEFT lines — block-sequential, NOT
        reading order."""
        path = _two_col_pdf(tmp_path, right_first=True)
        text = PdfReader(str(path)).pages[0].extract_text()
        assert text == "\n".join([RIGHT_TEXT] * N_LINES + [LEFT_TEXT] * N_LINES)

    def test_pypdf_order_flips_with_insertion_order(self, tmp_path):
        """Proof the order is insertion-driven, not geometry-driven: the same
        page with the LEFT column written first extracts LEFT-first."""
        path = _two_col_pdf(tmp_path, right_first=False)
        text = PdfReader(str(path)).pages[0].extract_text()
        assert text == "\n".join([LEFT_TEXT] * N_LINES + [RIGHT_TEXT] * N_LINES)

    def test_pdfplumber_extraction_is_row_interleaved(self, tmp_path):
        """pdfplumber clusters same-baseline words into one line: each output
        line is LEFT + " " + RIGHT — row-interleaved, the third possible
        reading order (neither block-sequential nor per-word mixed)."""
        path = _two_col_pdf(tmp_path)
        with pdfplumber.open(str(path)) as pdf:
            text = pdf.pages[0].extract_text()
        assert text == "\n".join([f"{LEFT_TEXT} {RIGHT_TEXT}"] * N_LINES)

    def test_fitz_get_text_also_content_stream_order(self, tmp_path):
        """fitz's own extractor returns the same content-stream order as pypdf
        (right-first), and the last glyph is NOT clipped (the fixture keeps
        both columns inside the page width)."""
        path = _two_col_pdf(tmp_path)
        doc = fitz.open(str(path))
        text = doc[0].get_text()
        doc.close()
        assert text.split("\n")[0] == RIGHT_TEXT
        assert text.count(RIGHT_TEXT) == N_LINES and text.count(LEFT_TEXT) == N_LINES

    def test_converter_extraction_emits_both_columns_with_page_markers(self, tmp_path):
        """End-to-end converter pin: process_pdf + build_markdown produce
        ``<!-- original page N -->`` markers followed by the pypdf-tier text
        for every page (exact full-string pin)."""
        path = _two_col_pdf(tmp_path)
        results, markdown, _logs = _converter_extraction(path)
        page_text = "\n".join([RIGHT_TEXT] * N_LINES + [LEFT_TEXT] * N_LINES)
        assert markdown == (
            f"<!-- original page 1 -->\n{page_text}\n\n<!-- original page 2 -->\n{page_text}"
        )
        assert all(r.success for r in results.values())

    def test_converter_raw_markdown_reading_order_is_content_stream(self, tmp_path):
        """CHARACTERIZATION (surprising but true): the raw markdown a
        two-column PDF produces is in the WRONG reading order — the right
        column (written first) precedes the left. The layout-repair modules
        (LayoutReorder / LightweightLayoutDetector) exist to fix this, but
        the repair only runs for source_type == "academic_paper", and the
        postprocess LightweightLayoutDetector result is computed then
        DISCARDED (postprocess.py computes ``reordered`` only to log it —
        it is never merged into raw_markdown). For every other source type
        this order flows straight into segmentation + summarization."""
        path = _two_col_pdf(tmp_path)
        _results, markdown, _logs = _converter_extraction(path)
        assert RIGHT_TEXT in markdown and LEFT_TEXT in markdown
        assert markdown.index(RIGHT_TEXT) < markdown.index(LEFT_TEXT)

    def test_two_column_page_is_not_classified_scanned(self, tmp_path):
        """Column geometry never influences the scanned heuristic — a
        two-column page with meaningful text is a DIGITAL page (NO_OCR)."""
        path = _two_col_pdf(tmp_path, n_pages=1)
        analysis = PdfAnalyzer().analyze(path)
        assert analysis.scanned_pages == []
        assert analysis.recommendation == PdfRecommendation.NO_OCR

    def test_lightweight_detector_classifies_and_repairs_the_fixture(self, tmp_path):
        """Cross-check against REAL pdfplumber word geometry (the existing
        p2 pins use synthetic word dicts): _detect_columns returns the two
        column spans (left 50..~175, right 320..~455 — the 150pt gutter is
        > 5% of the 612pt page), and detect_and_reorder reorders the page
        left-first — i.e. the repair the pipeline computes (and then
        discards, see above) is correct."""
        path = _two_col_pdf(tmp_path, n_pages=1)
        detector = LightweightLayoutDetector()

        with pdfplumber.open(str(path)) as pdf:
            words = pdf.pages[0].extract_words(use_text_flow=False)
        columns = detector._detect_columns(words, pdf.pages[0].width)
        assert len(columns) == 2  # NOT the single-column [(0, 612)] fallback
        assert columns[0][0] == 50 and columns[1][0] == 320  # left first, gutter kept

        results = detector.detect_and_reorder(path, [1])
        assert 1 in results
        assert results[1].index("harbour") < results[1].index("surveyed")


# ════════════════════════════════════════════════════════════════════════════
# 2. Tables
# ════════════════════════════════════════════════════════════════════════════


class TestTableExtraction:
    def _expected_rows(self):
        return "\n".join("".join(cell.ljust(12) for cell in row) for row in TABLE_ROWS)

    def test_pypdf_preserves_monospaced_column_alignment(self, tmp_path):
        """pypdf serializes the padded monospaced rows VERBATIM — the column
        structure survives as whitespace (exact string, padding included)."""
        path = _table_pdf(tmp_path)
        text = PdfReader(str(path)).pages[0].extract_text()
        assert text == self._expected_rows()

    def test_pdfplumber_collapses_table_whitespace(self, tmp_path):
        """CHARACTERIZATION: pdfplumber's default word clustering collapses
        the column padding to single spaces — any downstream consumer built
        on pdfplumber words loses the visual table alignment that pypdf
        keeps."""
        path = _table_pdf(tmp_path)
        with pdfplumber.open(str(path)) as pdf:
            text = pdf.pages[0].extract_text()
        assert text == "\n".join(" ".join(row) for row in TABLE_ROWS)
        assert "  " not in text  # the alignment whitespace is gone

    def test_converter_extraction_keeps_table_rows_verbatim(self, tmp_path):
        """The converter's digital tier emits the padded rows byte-for-byte
        (with the page marker) — whitespace tables reach the summarizer as
        aligned text, not as markdown tables."""
        path = _table_pdf(tmp_path)
        _results, markdown, _logs = _converter_extraction(path)
        assert f"<!-- original page 1 -->\n{self._expected_rows()}" in markdown
        for row in TABLE_ROWS:
            for cell in row:
                assert cell in markdown

    def test_monospaced_table_page_is_not_classified_scanned(self, tmp_path):
        path = _table_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        assert analysis.scanned_pages == []
        assert analysis.recommendation == PdfRecommendation.NO_OCR

    def test_table_extractor_lattice_finds_nothing_without_ruling_lines(self, tmp_path):
        """A whitespace-only table yields ZERO extracted tables — via either
        mechanism this environment takes: (a) camelot's lattice backend needs
        the ghostscript Python module (absent here — the per-call exception
        branch, same situation as the p2 tables suite) or (b) on a fully
        provisioned env, lattice genuinely detects no ruling lines. The pin
        is the empty result either way (dev-env-only — camelot is an optional
        extra, hence importorskip)."""
        pytest.importorskip("camelot")
        path = _table_pdf(tmp_path)
        logs: list[tuple[str, str]] = []
        extractor = TableExtractor(log_callback=lambda m, lvl="INFO": logs.append((lvl, m)))
        assert extractor.extract_tables_from_pdf(path, pages="1") == {}
        # Either the lattice backend errored, or it found no tables:
        assert any(
            "Camelot extraction failed" in m or "Camelot extracted 0 tables" in m for _, m in logs
        )

    def test_table_extractor_absent_camelot_is_a_noop(self, tmp_path, monkeypatch):
        """CI/default-install pin: camelot is NOT in requirements.txt, so the
        default behavior is a logged warning and an empty result."""
        monkeypatch.setitem(sys.modules, "camelot", None)
        logs: list[tuple[str, str]] = []
        extractor = TableExtractor(log_callback=lambda m, lvl="INFO": logs.append((lvl, m)))
        assert extractor.extract_tables_from_pdf(tmp_path / "any.pdf") == {}
        assert any("Camelot not installed" in m for _, m in logs)


# ════════════════════════════════════════════════════════════════════════════
# 3. Non-Latin (Farsi / RTL)
# ════════════════════════════════════════════════════════════════════════════

# Exact extraction pins, as codepoints (ASCII-safe in source; the shaped
# glyphs are RTL presentation forms that are easy to corrupt by hand).
# Captured against PyMuPDF 1.26.x + pypdf 6.x — a pymupdf/pypdf upgrade that
# changes shaping or the ToUnicode map SHOULD trip these (that is the point
# of a characterization pin).
#
# _FITZ_LINE1 = shaped(کانال سوئز) in visual reading order:
#   ﮐﺎﻧﺎﻝ ﺳﻮﺋﺰ  (presentation forms of each letter, correct RTL order)
_FITZ_LINE1_CP = "64400 65166 65255 65166 65245 32 65203 65262 65163 65200"

# _PYPDF_FULL = the same shaped forms but each WORD's characters reversed
# (visual LTR serialization), words separated by two spaces; includes the
# U+0628 (ب) mojibake mix-in inside 'دستاوردها' where the embedded subset
# font's ToUnicode map yields the LOGICAL codepoint instead of the
# presentation form.
_PYPDF_FULL_CP = (
    "65245 65166 65255 65166 64400 32 32 65200 65163 65262 65203 32 10 "
    "65257 65165 65197 32 32 65254 65259 65153 32 32 64509 64401 64510 "
    "32 32 65199 65165 32 32 65250 65260 65251 32 32 65254 64510 65198 "
    "65175 32 32 64508 65166 65259 65193 65197 65261 65166 65176 65203 "
    "65193 32 32 64508 65197 65261 65166 65256 65235 32 32 65197 65193 "
    "32 32 65253 65198 65239 32 32 65250 65259 65193 65199 65262 65255 "
    "32 32 64508 65193 1576 32 32 65193 65262 65169 32 32 65258 64400 "
    "32 32 65198 64511 65204 65251 32 32 65173 65197 65166 65184 65175 "
    "32 32 65261 32 65198 65236 65203 32 32 65165 65197 32 32 65197 "
    "65193 32 32 65198 65203 65165 65198 65203 32 32 65253 65166 65260 "
    "65183 32 10 65253 65262 64404 65198 64404 65193 32 32 65193 65198 "
    "64400 32 46"
)


def _cp(text: str) -> str:
    """Decode a space-separated codepoint string (ASCII-safe pin storage)."""
    return "".join(chr(int(token)) for token in text.split())


class TestFarsiExtraction:
    def test_both_extractors_return_shaped_presentation_forms(self, tmp_path):
        """CHARACTERIZATION (headline): a properly-embedded Persian page does
        NOT round-trip. Both extractors return Arabic PRESENTATION-FORM
        codepoints (U+FB50–U+FDFF / U+FE70–U+FEFF) — not the logical
        U+0600–U+06FF characters — and neither contains the original logical
        string."""
        path = _persian_pdf(tmp_path)
        doc = fitz.open(str(path))
        fitz_text = doc[0].get_text()
        doc.close()
        pypdf_text = PdfReader(str(path)).pages[0].extract_text()

        fitz_line1 = fitz_text.split("\n")[0]
        assert fitz_line1 == _cp(_FITZ_LINE1_CP)
        assert pypdf_text == _cp(_PYPDF_FULL_CP)

        sentence = _golden_farsi_sentence()
        for extracted in (fitz_text, pypdf_text):
            assert PERSIAN_WORD not in extracted
            assert sentence not in extracted

    def test_pypdf_reverses_each_persian_word(self, tmp_path):
        """pypdf's serialization reverses the characters WITHIN each word
        (visual LTR order) while keeping the word order — derivable rule:
        line1 == "  ".join(word[::-1] for word in fitz_line1.split()) + " "."""
        path = _persian_pdf(tmp_path)
        doc = fitz.open(str(path))
        fitz_line1 = doc[0].get_text().split("\n")[0]
        doc.close()
        pypdf_line1 = PdfReader(str(path)).pages[0].extract_text().split("\n")[0]
        assert pypdf_line1 == "  ".join(w[::-1] for w in fitz_line1.split()) + " "

    def test_short_persian_page_is_classified_scanned(self, tmp_path):
        """CHARACTERIZATION (finding): a Persian page whose extractable text
        is short (< 30 chars) is classified SCANNED and pushed to the OCR
        cascade — the analyzer/prescan word regex is
        ``[A-Za-z\\u0600-\\u06FF]{2,}`` and does NOT match the presentation
        forms the extractors actually return. A Farsi title-only page is
        therefore always an "OCR" page in this pipeline."""
        path = _persian_pdf(tmp_path, sentence=PERSIAN_WORD, name="farsi_short.pdf")
        analysis = PdfAnalyzer().analyze(path)
        assert analysis.scanned_pages == [1]
        assert analysis.recommendation == PdfRecommendation.LLM_OCR
        # The pre-scan (which decides whether the OCR model loads) agrees:
        scan = prescan_pages(path, [1])
        assert scan.scanned_pages == [1]
        assert scan.skip_model_load is False
        # Root cause: the shaped word is invisible to the word regex.
        shaped = PdfReader(str(path)).pages[0].extract_text()
        assert PdfAnalyzer()._is_text_meaningful(shaped.strip()) is False

    def test_long_persian_page_is_digital_but_shaped(self, tmp_path):
        """A full Persian paragraph passes the scanned heuristic ONLY through
        the ≥-30-chars branch (not by word count): it is extracted as a
        DIGITAL page, and the shaped/visual-order text flows downstream."""
        path = _persian_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        assert analysis.scanned_pages == []
        assert analysis.recommendation == PdfRecommendation.NO_OCR
        scan = prescan_pages(path, [1])
        assert scan.digital_pages == [1] and scan.skip_model_load is True
        # Contrast: the LOGICAL-order sentence (what OCR engines would emit)
        # IS recognized as words by the same heuristic.
        assert PdfAnalyzer()._is_text_meaningful(_golden_farsi_sentence()) is True

    def test_converter_extraction_emits_shaped_forms(self, tmp_path):
        """End-to-end: the raw markdown the converter builds for a Farsi page
        carries the shaped, per-word-reversed presentation forms (the
        summarizer never sees the logical Persian string on the digital
        path)."""
        path = _persian_pdf(tmp_path)
        _results, markdown, _logs = _converter_extraction(path)
        expected_line1 = _cp(_PYPDF_FULL_CP).split("\n")[0]
        assert markdown.startswith(f"<!-- original page 1 -->\n{expected_line1}")
        assert PERSIAN_WORD not in markdown
