"""Phase 4.5 (Edge-case fixtures) — the SCANNED-PDF OCR DECISION CASCADE,
characterized end-to-end on REAL in-memory PDFs with boundary mocks.

The cascade under test is ``OCRService.process_pdf`` — the exact entry the
converter calls (core.pipeline.conversion.extraction.run_extraction, Step 3):

    analyzer flags pages → OCRService(pages_to_ocr) → per page:
      * page in pages_to_ocr      → _ocr_scanned_page:
          poppler missing?  → "[Page N: OCR skipped — poppler not installed]"
          rasterize (pdf2image) → Qwen/OlmOCR (Ollama HTTP) → Paddle (off)
          → local VLM (unconfigured) → Tesseract → "[Page N: all OCR methods failed]"
      * page NOT in pages_to_ocr  → _extract_digital_page:
          markitdown (>50 alnum) → vision OCR (if flagged) → pypdf extract_text()

Mocking discipline (house pattern from tests/test_p2_pdf_struct_toc_parsers.py
/ test_p2_pdf_struct_layout_math.py): REAL fitz builds the PDFs; the raster-
ization boundary (``pdf2image.convert_from_bytes``), the OCR boundary
(``pytesseract.image_to_string``) and the LLM boundary
(``core.ocr.service.safe_ollama_request``) are monkeypatched. No network, no
tesseract binary, no Ollama, no model downloads — the real tesseract binary
is never invoked even where installed.

Already pinned elsewhere (not duplicated): the pre-scan heuristic on MOCKED
readers (tests/test_ocr_prescan.py), the analyzer's page classification
(tests/test_p2_pdf_struct_analyzer.py), and the digital-tier extraction
output for multi-column/table/Farsi pages (tests/test_p4_edge_cases_pdf.py).

Notable pins (characterization, not opinion):
  * pypdf-tier digital pages are labeled ``engine_used=markitdown``.
  * On Linux, ``_detect_poppler`` returns "" (use PATH) but __init__ treats
    "" as not-found → ``_poppler_path=None`` → the OCR cascade is DISABLED
    with "[Page N: OCR skipped — poppler not installed]" even when
    poppler-utils is installed (only an explicit paths.poppler setting
    re-enables it).
  * A DIGITAL page wrongly flagged scanned LOSES its extractable text when
    the OCR engines fail — _ocr_scanned_page has no pypdf fallback.
  * The V18.2.16 pre-scan can decide "0 pages need OCR — digital pages will
    be extracted via markitdown", yet the per-page loop still rasterizes +
    tesseracts those pages (pages_to_ocr is never refined).
  * Tesseract is always invoked with lang="eng+fas" (hardcoded bilingual).
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

    House hygiene: earlier-collected files install MagicMock stubs for
    pypdf/PIL/pdf2image/pytesseract and never remove them; the boundary
    monkeypatches below MUST land on the real modules.
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pypdf")
_ensure_real_module("PIL")
_ensure_real_module("pdf2image")
_ensure_real_module("pytesseract")

import fitz  # noqa: E402 — after stub cleanup
import pdf2image  # noqa: E402 — after stub cleanup
import pytesseract  # noqa: E402 — after stub cleanup
import pytest  # noqa: E402 — after stub cleanup
from PIL import Image  # noqa: E402 — after stub cleanup
from pypdf import PdfReader  # noqa: E402 — after stub cleanup

# Repair production bindings possibly made against a MagicMock pypdf.
import core.ocr.service as _ocr_service_module  # noqa: E402 — after stub cleanup
import core.pdf.analyzer as _analyzer_module  # noqa: E402 — after stub cleanup
from core.models import (  # noqa: E402 — after stub cleanup
    ConversionRequest,
    OcrEngine,
    OcrResult,
    PageAnalysis,
    PdfAnalysisResult,
    PdfRecommendation,
)
from core.ocr.ocr_prescan import prescan_pages  # noqa: E402 — after stub cleanup
from core.ocr.service import OCRService  # noqa: E402 — after stub cleanup
from core.pdf.analyzer import PdfAnalyzer  # noqa: E402 — after stub cleanup
from utils.settings import Settings  # noqa: E402 — after stub cleanup

if not isinstance(_analyzer_module.PdfReader, type):
    _analyzer_module.PdfReader = PdfReader
if not isinstance(_ocr_service_module.PdfReader, type):
    _ocr_service_module.PdfReader = PdfReader
if not isinstance(_ocr_service_module.PdfWriter, type):
    from pypdf import PdfWriter

    _ocr_service_module.PdfWriter = PdfWriter

DIGITAL_TEXT = "Digital page text that is long enough to be meaningful for the analyzer."
TESSERACT_TEXT = "Tesseract recovery text for the scanned page."
DEFAULT_OCR_MODEL = "qwen3-vl:8b"  # core.llm.model_taxonomy.DEFAULT_FALLBACK_OCR_MODEL


# ── fitz PDF factories ──────────────────────────────────────────────────────


def _write(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


def _digital_pdf(tmp_path: Path, n_pages: int = 2) -> Path:
    """Every page has a real text layer (analyzer: NOT scanned)."""
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), DIGITAL_TEXT, fontsize=11)
    return _write(doc, tmp_path, "digital.pdf")


def _noise_png(size: int = 60) -> bytes:
    """A deterministic PNG image (no extractable text)."""
    import io

    import numpy as np

    rng = np.random.default_rng(7)
    arr = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _scanned_pdf(tmp_path: Path) -> Path:
    """Page 1: image-only (a real embedded PNG). Page 2: blank. Neither has
    any text layer — the classic 'scanned PDF' shape."""
    doc = fitz.open()
    p1 = doc.new_page(width=400, height=600)
    p1.insert_image(fitz.Rect(50, 100, 350, 400), stream=_noise_png())
    doc.new_page(width=400, height=600)  # blank
    return _write(doc, tmp_path, "scanned.pdf")


def _mixed_pdf(tmp_path: Path) -> Path:
    """Page 1: digital text. Page 2: image-only. Page 3: blank."""
    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 60), DIGITAL_TEXT, fontsize=11)
    p2 = doc.new_page(width=400, height=600)
    p2.insert_image(fitz.Rect(50, 100, 350, 400), stream=_noise_png())
    doc.new_page(width=400, height=600)
    return _write(doc, tmp_path, "mixed.pdf")


# ── hermetic stand-ins ──────────────────────────────────────────────────────


class _P4Settings:
    """Deterministic offline Settings (real Settings._test_override DI hook)."""

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
    """No Ollama/torch/network — records every model probe."""

    def __init__(self, exists=False, acquire=False):
        self._exists = exists
        self._acquire = acquire
        self.exists_calls: list[str] = []
        self.acquire_calls: list[str] = []
        self.release_calls: list[str] = []

    def get_loaded_models(self):
        return []

    def model_exists(self, name):
        self.exists_calls.append(name)
        return self._exists

    def acquire_model(self, name, *a, **k):
        self.acquire_calls.append(name)
        return self._acquire

    def release_model(self, name, *a, **k):
        self.release_calls.append(name)

    def force_unload(self, *a, **k):
        pass


class _FakeMarkItDown:
    """Duck-typed MarkItDown: ``convert(path)`` → ``.text_content``."""

    def __init__(self, text: str):
        self._text = text
        self.converted_paths: list[str] = []

    def convert(self, path):
        self.converted_paths.append(str(path))
        return types.SimpleNamespace(text_content=self._text)


@pytest.fixture(autouse=True)
def _hermetic_env():
    """Offline Settings + snapshot of the pytesseract global the service
    mutates (production sets ``pytesseract.pytesseract.tesseract_cmd`` —
    restore it so later suites see the pristine value)."""
    prev_override = Settings._test_override
    prev_cmd = pytesseract.pytesseract.tesseract_cmd
    Settings._test_override = _P4Settings()
    yield
    pytesseract.pytesseract.tesseract_cmd = prev_cmd
    Settings._test_override = prev_override


class _Boundary:
    """Recording boundary mocks: rasterization + tesseract + Ollama HTTP."""

    def __init__(
        self,
        monkeypatch,
        tesseract_text=None,
        tesseract_raises=False,
        raster_raises=False,
    ):
        self.raster_calls: list[dict] = []
        self.tesseract_calls: list[dict] = []
        self.ollama_calls: list[str] = []

        def fake_convert_from_bytes(data, **kwargs):
            self.raster_calls.append(dict(kwargs))
            if raster_raises:
                raise RuntimeError("pdftoppm exploded")
            return [Image.new("RGB", (10, 10), "white")]

        def fake_image_to_string(img, lang=None):
            self.tesseract_calls.append({"lang": lang})
            if tesseract_raises:
                raise RuntimeError("tesseract binary not available")
            return tesseract_text if tesseract_text is not None else TESSERACT_TEXT

        def fake_ollama_request(method, url, **kwargs):
            self.ollama_calls.append(url)
            raise RuntimeError("no ollama server")

        monkeypatch.setattr(pdf2image, "convert_from_bytes", fake_convert_from_bytes)
        monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)
        monkeypatch.setattr(_ocr_service_module, "safe_ollama_request", fake_ollama_request)


def _make_service(
    pdf_path: Path,
    pages_to_ocr: list[int],
    use_llm_ocr: bool = False,
    model_exists: bool = False,
    model_acquire: bool = False,
    md_tool=None,
    poppler: str | None = None,
):
    """Build the OCRService exactly as run_extraction does. ``poppler``:
    None → leave whatever auto-detection produced (Linux default: disabled);
    a string → an explicit, truthy poppler path (cascade enabled)."""
    logs: list[tuple[str, str]] = []

    def log(msg, level="INFO"):
        logs.append((level, msg))

    total = len(PdfReader(str(pdf_path)).pages)
    request = ConversionRequest(
        input_path=pdf_path, output_dir=pdf_path.parent, use_llm_ocr=use_llm_ocr
    )
    scanned = list(pages_to_ocr)
    analysis = PdfAnalysisResult(
        total_pages=total,
        scanned_pages=list(scanned),
        text_pages=[p for p in range(1, total + 1) if p not in set(scanned)],
        recommendation=PdfRecommendation.LLM_OCR if scanned else PdfRecommendation.NO_OCR,
        per_page=[
            PageAnalysis(i, i in set(scanned), "", "ocr" if i in set(scanned) else "skip")
            for i in range(1, total + 1)
        ],
    )
    service = OCRService(request, analysis, list(scanned), log_callback=log)
    service.model_manager = _StubModelManager(exists=model_exists, acquire=model_acquire)
    service._md_tool = md_tool  # None → pypdf tier (deterministic across envs)
    if poppler is not None:
        service._poppler_path = poppler
    return service, logs


# ════════════════════════════════════════════════════════════════════════════
# 1. Digital-tier cascade decisions
# ════════════════════════════════════════════════════════════════════════════


class TestDigitalTier:
    def test_text_layer_page_never_rasterizes_or_ocrs(self, tmp_path, monkeypatch):
        """(a) A page WITH a text layer never touches the OCR machinery:
        no rasterization, no tesseract, no Ollama — pure text extraction."""
        path = _digital_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, _logs = _make_service(path, pages_to_ocr=[])
        results = service.process_pdf(path)

        assert set(results) == {1, 2}
        assert all(r.success for r in results.values())
        # CHARACTERIZATION: the pypdf tier is labeled engine_used=markitdown.
        assert all(r.engine_used == OcrEngine.MARKITDOWN for r in results.values())
        assert results[1].text == DIGITAL_TEXT
        assert boundary.raster_calls == []
        assert boundary.tesseract_calls == []
        assert boundary.ollama_calls == []
        assert service.model_manager.exists_calls == []  # never probed Ollama

    def test_markitdown_tier1_gate_accepts_long_text(self, tmp_path, monkeypatch):
        """markitdown output with > 50 alnum chars is accepted as the final
        text (tier-1 short-circuit); the page is written to a temp .pdf for
        the per-page conversion."""
        path = _digital_pdf(tmp_path, n_pages=1)
        boundary = _Boundary(monkeypatch)
        md = _FakeMarkItDown("Markitdown extracted plenty of alphanumeric characters here.")
        service, _logs = _make_service(path, pages_to_ocr=[], md_tool=md)
        results = service.process_pdf(path)

        assert results[1].text == "Markitdown extracted plenty of alphanumeric characters here."
        assert results[1].engine_used == OcrEngine.MARKITDOWN
        assert len(md.converted_paths) == 1 and md.converted_paths[0].endswith(".pdf")
        assert boundary.raster_calls == []  # accepted at tier 1 — no vision path

    def test_markitdown_short_text_falls_through_to_pypdf(self, tmp_path, monkeypatch):
        """markitdown output with <= 50 alnum chars on a page NOT flagged for
        OCR falls through to the pypdf tier (tier-3)."""
        path = _digital_pdf(tmp_path, n_pages=1)
        _Boundary(monkeypatch)
        md = _FakeMarkItDown("tiny")  # 4 alnum chars
        service, logs = _make_service(path, pages_to_ocr=[], md_tool=md)
        results = service.process_pdf(path)

        assert results[1].text == DIGITAL_TEXT  # pypdf tier recovered the page
        assert results[1].engine_used == OcrEngine.MARKITDOWN
        assert any("returned only 4 alnum chars" in m for _, m in logs)

    def test_markitdown_short_text_in_ocr_set_goes_vision_then_tesseract(
        self, tmp_path, monkeypatch
    ):
        """A short markitdown yield on a page that IS flagged for OCR enters
        the vision cascade: rasterize → Qwen (Ollama down) → VLM (unconfigured)
        → Tesseract recovery."""
        path = _digital_pdf(tmp_path, n_pages=1)
        boundary = _Boundary(monkeypatch)
        md = _FakeMarkItDown("tiny")
        service, _logs = _make_service(path, pages_to_ocr=[1], md_tool=md, poppler="/usr/bin")
        results = service.process_pdf(path)

        assert results[1].success is True
        assert results[1].engine_used == OcrEngine.TESSERACT
        assert results[1].text == TESSERACT_TEXT
        assert len(boundary.raster_calls) == 1
        assert len(boundary.tesseract_calls) == 1


# ════════════════════════════════════════════════════════════════════════════
# 2. Poppler gating (the Linux finding)
# ════════════════════════════════════════════════════════════════════════════


class TestPopplerGate:
    def test_autodetect_returns_empty_on_linux_and_disables_ocr(self, tmp_path, monkeypatch):
        """CHARACTERIZATION (finding): on non-Windows, _detect_poppler returns
        "" (meaning "poppler is on PATH, use pdf2image defaults"), but
        __init__ treats "" as NOT FOUND → _poppler_path=None → _check_poppler()
        is False. On a Linux/macOS host the OCR cascade is therefore disabled
        by default even with poppler-utils installed — only an explicit
        ``paths.poppler`` setting re-enables it."""
        monkeypatch.setattr(_ocr_service_module.platform, "system", lambda: "Linux")
        assert OCRService._detect_poppler() == ""

        path = _scanned_pdf(tmp_path)
        service, logs = _make_service(path, pages_to_ocr=[1, 2])
        assert service._poppler_path is None
        assert service._check_poppler() is False
        assert any("Poppler not found" in m for _, m in logs)

    def test_scanned_page_with_poppler_missing_emits_skip_marker(self, tmp_path, monkeypatch):
        """The default Linux cascade for a scanned page: no rasterization, no
        tesseract — a graceful '[Page N: OCR skipped — poppler not installed]'
        placeholder that build_markdown turns into 'content unavailable'."""
        monkeypatch.setattr(_ocr_service_module.platform, "system", lambda: "Linux")
        path = _scanned_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, _logs = _make_service(path, pages_to_ocr=[1, 2])
        results = service.process_pdf(path)

        assert boundary.raster_calls == [] and boundary.tesseract_calls == []
        for pn in (1, 2):
            assert results[pn].success is False
            assert results[pn].engine_used == OcrEngine.NONE
            assert results[pn].text == f"[Page {pn}: OCR skipped — poppler not installed]"
        markdown = OCRService.build_markdown(results)
        assert markdown == (
            "<!-- original page 1 -->\n[Page 1: content unavailable]\n\n"
            "<!-- original page 2 -->\n[Page 2: content unavailable]"
        )

    def test_rasterization_kwargs_are_pinned(self, tmp_path, monkeypatch):
        """With poppler enabled, each scanned page is rasterized as a
        single-page 300-dpi PNG via convert_from_bytes (exact kwargs pin —
        dpi comes from settings ocr.image_dpi)."""
        path = _scanned_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, _logs = _make_service(path, pages_to_ocr=[1, 2], poppler="/usr/bin")
        service.process_pdf(path)

        assert len(boundary.raster_calls) == 2
        for kwargs in boundary.raster_calls:
            assert kwargs == {
                "fmt": "png",
                "first_page": 1,
                "last_page": 1,
                "dpi": 300,
                "poppler_path": "/usr/bin",
            }


# ════════════════════════════════════════════════════════════════════════════
# 3. Tesseract tier: recovery and failure
# ════════════════════════════════════════════════════════════════════════════


class TestTesseractTier:
    def test_scanned_page_is_recovered_by_tesseract(self, tmp_path, monkeypatch):
        """(b) A page with NO text layer, poppler enabled, OCR model absent →
        rasterize → tesseract (the only engine left) → success."""
        path = _scanned_pdf(tmp_path)
        _Boundary(monkeypatch)
        service, logs = _make_service(path, pages_to_ocr=[1, 2], poppler="/usr/bin")
        results = service.process_pdf(path)

        for pn in (1, 2):
            assert results[pn].success is True
            assert results[pn].engine_used == OcrEngine.TESSERACT
            assert results[pn].text == TESSERACT_TEXT
        markdown = OCRService.build_markdown(results)
        assert markdown.startswith(
            f"<!-- original page 1 -->\n{TESSERACT_TEXT}\n\n<!-- original page 2 -->\n{TESSERACT_TEXT}"
        )
        assert any("PDF processing done: 2/2 pages extracted" in m for _, m in logs)

    def test_tesseract_is_hardcoded_to_eng_fas(self, tmp_path, monkeypatch):
        """CHARACTERIZATION: every tesseract call uses lang='eng+fas'
        (English + Farsi), regardless of the document language."""
        path = _scanned_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, _logs = _make_service(path, pages_to_ocr=[1], poppler="/usr/bin")
        service.process_pdf(path)

        assert len(boundary.tesseract_calls) == 1
        assert boundary.tesseract_calls[0] == {"lang": "eng+fas"}

    def test_tesseract_failure_degrades_gracefully(self, tmp_path, monkeypatch):
        """(c) OCR engine unavailable: rasterization works, Qwen/VLM/Paddle
        are down/unconfigured, tesseract raises (binary missing) → the page
        degrades to '[Page N: all OCR methods failed]' with success=False —
        no exception escapes, and build_markdown renders 'content
        unavailable'."""
        path = _scanned_pdf(tmp_path)
        _Boundary(monkeypatch, tesseract_raises=True)
        service, logs = _make_service(path, pages_to_ocr=[1, 2], poppler="/usr/bin")
        results = service.process_pdf(path)

        for pn in (1, 2):
            assert results[pn].success is False
            assert results[pn].engine_used == OcrEngine.TESSERACT
            assert results[pn].text == f"[Page {pn}: all OCR methods failed]"
            assert "tesseract binary not available" in results[pn].error_msg
        assert any("page(s) failed to extract" in m for _, m in logs)
        assert "[Page 1: content unavailable]" in OCRService.build_markdown(results)

    def test_digital_page_wrongly_flagged_scanned_loses_its_text(self, tmp_path, monkeypatch):
        """CHARACTERIZATION (headline cascade finding): a DIGITAL page that
        the analyzer wrongly flagged as scanned (e.g. a short Farsi title
        page — see test_p4_edge_cases_pdf.py) goes down _ocr_scanned_page,
        which has NO pypdf fallback. If the OCR engines fail, the page's
        perfectly extractable text is REPLACED by a failure marker — the
        digital text is never consulted."""
        path = _digital_pdf(tmp_path, n_pages=1)
        # Contrast probe: the very same page yields rich text via pypdf…
        assert PdfReader(str(path)).pages[0].extract_text() == DIGITAL_TEXT

        _Boundary(monkeypatch, tesseract_raises=True)
        service, _logs = _make_service(path, pages_to_ocr=[1], poppler="/usr/bin")
        results = service.process_pdf(path)

        assert results[1].success is False
        assert results[1].text == "[Page 1: all OCR methods failed]"
        assert DIGITAL_TEXT not in results[1].text  # the digital text is LOST


# ════════════════════════════════════════════════════════════════════════════
# 4. The V18.2.16 pre-scan inside process_pdf
# ════════════════════════════════════════════════════════════════════════════


class TestPrescanIntegration:
    def test_all_digital_skips_model_load_but_still_tesseracts(self, tmp_path, monkeypatch):
        """CHARACTERIZATION (inconsistency): with use_llm_ocr on + poppler
        enabled, the pre-scan can report '0 pages need OCR — digital pages
        will be extracted via markitdown' and skip the model load — yet the
        per-page loop still rasterizes + tesseracts every page in
        pages_to_ocr (the set is never refined by the pre-scan)."""
        path = _digital_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, logs = _make_service(
            path, pages_to_ocr=[1, 2], use_llm_ocr=True, poppler="/usr/bin"
        )
        results = service.process_pdf(path)

        # The pre-scan ran and skipped the model load…
        assert any("V18.2.16 Pre-scan" in m for _, m in logs)
        assert any("SKIPPING OCR model load" in m for _, m in logs)
        assert service.model_manager.exists_calls == []
        assert service.model_manager.acquire_calls == []
        # …but both "digital" pages were STILL rasterized + tesseracted.
        assert len(boundary.raster_calls) == 2
        assert len(boundary.tesseract_calls) == 2
        for pn in (1, 2):
            assert results[pn].engine_used == OcrEngine.TESSERACT
            assert results[pn].text == TESSERACT_TEXT  # not the pypdf text!

    def test_mixed_pdf_refines_targets_and_model_probe_is_pinned(self, tmp_path, monkeypatch):
        """On a genuinely mixed PDF the pre-scan keeps the scanned targets,
        the Ollama model probe happens exactly once with the default model
        name, and the digital page goes down the text tier while the scanned
        pages are tesseracted."""
        path = _mixed_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, logs = _make_service(
            path, pages_to_ocr=[2, 3], use_llm_ocr=True, poppler="/usr/bin"
        )
        results = service.process_pdf(path)

        # Digital page 1: text tier, exact pypdf text, never rasterized.
        assert results[1].engine_used == OcrEngine.MARKITDOWN
        assert results[1].text == DIGITAL_TEXT
        # Scanned pages 2-3: rasterized + tesseract recovery.
        for pn in (2, 3):
            assert results[pn].engine_used == OcrEngine.TESSERACT
            assert results[pn].text == TESSERACT_TEXT
        assert len(boundary.raster_calls) == 2
        # Exactly one Ollama probe, with the request's default OCR model.
        assert service.model_manager.exists_calls == [DEFAULT_OCR_MODEL]
        assert any(f"Model '{DEFAULT_OCR_MODEL}' not found in Ollama" in m for _, m in logs)

    def test_analyzer_and_prescan_agree_on_real_pages(self, tmp_path):
        """The pre-scan heuristic MIRRORS the analyzer (same regex, same
        extractor) — on a real mixed PDF the two never disagree, so the
        pre-scan can only skip model loads, never reclassify a page."""
        path = _mixed_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        scan = prescan_pages(path, [1, 2, 3])

        assert analysis.scanned_pages == [2, 3]  # image-only + blank pages
        assert scan.scanned_pages == analysis.scanned_pages
        assert scan.digital_pages == analysis.text_pages == [1]


# ════════════════════════════════════════════════════════════════════════════
# 5. Qwen/VLM tier (Ollama down) and total failure
# ════════════════════════════════════════════════════════════════════════════


class TestQwenTier:
    def test_qwen_loaded_but_ollama_down_falls_back_to_tesseract(self, tmp_path, monkeypatch):
        """The model 'loads' (acquire ok) but every Ollama HTTP call fails →
        the VLM fallback is unconfigured → Tesseract recovers the page."""
        path = _scanned_pdf(tmp_path)
        boundary = _Boundary(monkeypatch)
        service, logs = _make_service(
            path,
            pages_to_ocr=[1],
            use_llm_ocr=True,
            model_exists=True,
            model_acquire=True,
            poppler="/usr/bin",
        )
        results = service.process_pdf(path)

        assert boundary.ollama_calls  # Qwen was genuinely attempted
        assert results[1].success is True
        assert results[1].engine_used == OcrEngine.TESSERACT
        assert results[1].text == TESSERACT_TEXT
        assert any("Qwen failed p.1 → Tesseract recovered" in m for _, m in logs)
        # The model phase is properly closed even though Ollama never answered.
        assert service.model_manager.release_calls == [DEFAULT_OCR_MODEL]

    def test_all_engines_down_reports_image_only(self, tmp_path, monkeypatch):
        """Model loaded, Ollama down, VLM unconfigured, Tesseract raising →
        engine NONE with the image-only message (distinct from the
        'all OCR methods failed' text of the model-less path)."""
        path = _scanned_pdf(tmp_path)
        _Boundary(monkeypatch, tesseract_raises=True)
        service, logs = _make_service(
            path,
            pages_to_ocr=[1],
            use_llm_ocr=True,
            model_exists=True,
            model_acquire=True,
            poppler="/usr/bin",
        )
        results = service.process_pdf(path)

        assert results[1].success is False
        assert results[1].engine_used == OcrEngine.NONE
        assert results[1].text == ""
        assert "image-only" in results[1].error_msg
        assert any("all OCR methods returned < 20 chars" in m for _, m in logs)

    def test_page_to_image_failure_short_circuits(self, tmp_path, monkeypatch):
        """Rasterization itself failing (pdf2image/poppler error) stops the
        cascade before any engine runs: 'Page-to-image conversion failed'."""
        path = _scanned_pdf(tmp_path)
        boundary = _Boundary(monkeypatch, raster_raises=True)
        service, logs = _make_service(path, pages_to_ocr=[1], poppler="/usr/bin")
        results = service.process_pdf(path)

        assert results[1].success is False
        assert results[1].engine_used == OcrEngine.NONE
        assert results[1].error_msg == "Page-to-image conversion failed"
        assert boundary.tesseract_calls == []  # never got that far
        assert any("→ image failed" in m for _, m in logs)


# ════════════════════════════════════════════════════════════════════════════
# 6. build_markdown assembly
# ════════════════════════════════════════════════════════════════════════════


class TestBuildMarkdown:
    def test_assembly_rules(self):
        """Page markers in sorted order; successful text kept verbatim;
        failed pages AND whitespace-only 'successes' rendered as
        '[Page N: content unavailable]'; parts joined by a blank line."""
        results = {
            2: OcrResult(2, "second page text", True, OcrEngine.TESSERACT),
            1: OcrResult(1, "first page text", True, OcrEngine.MARKITDOWN),
            3: OcrResult(3, "", False, OcrEngine.NONE, "failed"),
            4: OcrResult(4, "   \n  ", True, OcrEngine.MARKITDOWN),  # blank success
        }
        assert OCRService.build_markdown(results) == (
            "<!-- original page 1 -->\nfirst page text\n\n"
            "<!-- original page 2 -->\nsecond page text\n\n"
            "<!-- original page 3 -->\n[Page 3: content unavailable]\n\n"
            "<!-- original page 4 -->\n[Page 4: content unavailable]"
        )
