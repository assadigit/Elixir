"""V0.6.0 (the dedicated-tools verification campaign) — Tool: the OCR
Service (``ocr_service``), end-to-end.

Inventory + trace (evidence-first):
- Card: ``ocr_service`` — ``ui_qt/views/tool_dashboard.py:94`` TOOL_CARDS
  row 3 (EXTRACT).
- Routing: ``ui_qt/views/convert_view.py:159`` ``_on_tool_clicked`` →
  ``base_dialog.OcrServiceDialog`` (facade) →
  ``ui_qt/views/service_dialogs/dialogs/ocr_service_dialog.py`` (the
  V18.20.4.6 O-b2 split).
- Dialog: ``_do_convert`` :759 → SimpleWorker → ``_ocr_work`` :869 →
  per-engine backends ``_ocr_auto`` :1005 / ``_ocr_pypdf`` :1036 /
  ``_ocr_ollama`` :1055 / ``_ocr_tesseract`` :1128; page-range parser
  ``_parse_page_range`` :716.
- Service: ``core/ocr/`` — ``service.py`` (``process_pdf`` :291 — the
  converter's Step-3 entry, cf. ``core/pipeline/conversion/extraction.py``),
  ``ocr_prescan.py`` (``prescan_pages`` — the V18.2.16 deterministic
  pre-scan), ``unlimited_ocr.py`` (``UnlimitedOCREngine`` — SWOT W8: 0%
  coverage), ``qwen_ocr.py`` (``QwenOCREngine`` — the Ollama vision
  adapter the dialog delegates to), ``base.py`` (the ``OCREngine`` ABC).
- Existing coverage: prescan on MOCKED readers (tests/test_ocr_prescan.py)
  + the mocked-boundary cascade (tests/test_p4_edge_cases_ocr.py). This
  file adds the LIVE pieces: real tesseract + real poppler on real fitz
  fixtures, the unlimited_ocr contract (0% → netted), the qwen adapter
  contract, and the full dialog worker drive.

LIVE vs CONTRACT in this sandbox (rig facts from the session bootstrap):
- tesseract 5.5.0 IS at /usr/bin/tesseract with eng+osd only (no fas) —
  tesseract 5.5 treats a missing ``fas`` as a WARNING, so the hardcoded
  ``lang="eng+fas"`` calls still succeed via ``eng`` (verified live).
- pdftoppm (poppler) IS installed → the rasterization paths run for real.
- torch/transformers are NOT installed → ``UnlimitedOCREngine.load()``
  fails LIVE (the fail-open contract is exercised for real).
- qwen/vision-model OCR + Persian (fas) tessdata + PaddleOCR are
  RIG-CHECKLIST items (see the worklog Task 4-c entry): live qwen vision
  run, ``ollama pull`` of a vision model, fas.traineddata install,
  PaddleOCR init, and a real Unlimited-OCR model folder.

V0.6.0 (4-c) defects netted by this file (fixes in core/ocr + the dialog,
all content-agnostic):
- O1 tesseract binary never auto-resolves off Windows: the default
  ``paths.tesseract`` is the Windows installer path
  (utils/settings.py:541) → service.py pinned a broken
  ``pytesseract.tesseract_cmd`` (TesseractNotFoundError / PermissionError
  for the blanked value) and the dialog's image branch exec'd it directly
  → scanned pages degraded to "all OCR methods failed" while a working
  tesseract sat on PATH. Fix: ``shutil.which`` fallback in
  OCRService.__init__ + the dialog's ``_ocr_tesseract`` (mirrors the
  existing poppler auto-detection).
- O2 garbage page range silently OCR'd the WHOLE document: a non-empty
  unparseable range ("abc", "0", "5-", or a pasted en-dash "2–4") parsed
  to None = all pages. Fix: dash normalization in ``_parse_page_range`` +
  a refuse-guard in ``_do_convert`` (the same C1 fix the cutter got).
- O3 ``UnlimitedOCREngine.process_batch`` mislabeled page numbers when a
  page's rasterization returned empty (page_map keyed by zip index, read
  by image index) → results keyed by wrong numbers (or the bogus -1).
  Fix: key the map by image path.

Layers (house UI-test pattern, cf. test_v0600_tool_cutter_e2e.py):
1. Pure characterization — the dialog's page-range parser + the pre-scan
   on REAL PDFs (the text-coverage threshold split).
2. Service-level end-to-end: LIVE tesseract cascade through
   ``OCRService.process_pdf`` on real fitz-built PDFs (digital page +
   image-of-text page), the unlimited_ocr fail-open contract, and the
   qwen adapter contract (mocked HTTP boundary only).
3. Dialog-level drive: the real SimpleWorker QThread + queued signals +
   ``_on_convert_finished`` on the main thread (offscreen QApplication,
   the modal monkeypatched to a recorder so ``msg.exec()`` never blocks).
"""

from __future__ import annotations

import io
import json
import sys
import types
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ── Module-import hygiene (house pattern from tests/test_p4_edge_cases_ocr.py) ─


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    Earlier-collected files install MagicMock stubs for pypdf/PIL/pdf2image/
    pytesseract and never remove them; the LIVE paths below need the real
    modules (and the monkeypatch boundaries must land on the real ones).
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
from PIL import Image, ImageDraw  # noqa: E402 — after stub cleanup
from pypdf import PdfReader, PdfWriter  # noqa: E402 — after stub cleanup

# Repair production bindings possibly made against a MagicMock pypdf /
# pdf2image (same repair the p4 suite applies).
import core.ocr.qwen_ocr as _qwen_ocr_module  # noqa: E402 — after stub cleanup
import core.ocr.service as _ocr_service_module  # noqa: E402 — after stub cleanup
import core.pdf.analyzer as _analyzer_module  # noqa: E402 — after stub cleanup
from core.models import (  # noqa: E402 — after stub cleanup
    ConversionRequest,
    OcrEngine,
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
    _ocr_service_module.PdfWriter = PdfWriter
if not isinstance(_qwen_ocr_module.PdfWriter, type):
    _qwen_ocr_module.PdfWriter = PdfWriter
if not isinstance(_qwen_ocr_module.convert_from_bytes, types.FunctionType):
    _qwen_ocr_module.convert_from_bytes = pdf2image.convert_from_bytes


# ── Layer 0: availability gates ─────────────────────────────────────────────

_DEAD_ENDPOINT = "http://127.0.0.1:9"  # connection refused, instantly, no egress


def _qt_available() -> bool:
    try:
        os_environ = __import__("os").environ
        os_environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _fitz_available() -> bool:
    try:
        import fitz  # noqa: F401

        return True
    except Exception:
        return False


def _tesseract_live() -> bool:
    """True when a real tesseract binary answers (the LIVE engine gate)."""
    try:
        langs = pytesseract.get_languages(config="")
        return bool(langs)
    except Exception:
        return False


def _pdftoppm_live() -> bool:
    import shutil

    return shutil.which("pdftoppm") is not None


# ── Real fitz fixtures ───────────────────────────────────────────────────────

DIGITAL_TEXT = "Digital page text that is long enough to be meaningful for the analyzer."
IMG_LINE_1 = "RAPID VISION TEST PAGE"
IMG_LINE_2 = "OPTICAL CHARACTER RECOGNITION WORKS"


def _text_image_png() -> bytes:
    """A PIL-rendered image OF text (no extractable text layer)."""
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), IMG_LINE_1, fill="black")
    draw.text((100, 200), IMG_LINE_2, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mixed_pdf(tmp_path: Path, name: str = "mixed.pdf") -> Path:
    """Page 1: real embedded text. Page 2: a rendered IMAGE of text (the
    classic mixed book shape — page 2 is what the pre-scan must flag)."""
    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 60), DIGITAL_TEXT, fontsize=11)
    p2 = doc.new_page(width=612, height=792)
    p2.insert_image(fitz.Rect(50, 100, 562, 700), stream=_text_image_png())
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return path


def _text_rich_pdf(tmp_path: Path, n_pages: int = 2, name: str = "digital.pdf") -> Path:
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), DIGITAL_TEXT, fontsize=11)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return path


def _image_only_pdf(tmp_path: Path, n_pages: int = 2, name: str = "imageonly.pdf") -> Path:
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_image(fitz.Rect(50, 100, 562, 700), stream=_text_image_png())
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return path


# ── Hermetic settings / model-manager stand-ins (p4 house pattern) ──────────


class _TestSettings:
    """Deterministic offline Settings (real Settings._test_override DI hook).

    ``paths.tesseract: ""`` reproduces the O1 defect shape (unset/blank
    binary path → must auto-resolve via PATH). The dead endpoint makes
    every Ollama HTTP probe fail instantly and hermetically.
    """

    def __init__(self, values: dict | None = None):
        self._values = {
            "paths.poppler": "/usr/bin" if _pdftoppm_live() else "",
            "paths.tesseract": "",
            "ocr.use_paddleocr": False,
            "ocr.unlimited_ocr_path": "",
            "ocr.image_dpi": 300,
            "ocr.timeout": 120,
            "local.ocr_parallel_workers": 1,
            "ocr.vlm_fallback_model": "",
            "ocr.primary_model": "test-ocr-model",
            "summarisation.provider": "ollama",
            "summarisation.endpoint": _DEAD_ENDPOINT,
            "llm.ollama_url": _DEAD_ENDPOINT,
            "quick_services.defaults.ocr_engine": "",
            "quick_services.defaults.ocr_format": "",
            "quick_services.ocr.engine": "auto",
            "quick_services.ocr.format": ".md",
            "summarisation.model": "",
        }
        if values:
            self._values.update(values)

    def get(self, key: str, default=None):
        return self._values.get(key, default)

    def set(self, key: str, value) -> None:
        self._values[key] = value

    def save(self) -> bool:
        return True

    def get_ollama_url(self) -> str:
        return _DEAD_ENDPOINT


class _StubModelManager:
    """No Ollama/torch/network — records every model probe (p4 shape)."""

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


def _default_ocr_model() -> str:
    try:
        from core.llm.model_taxonomy import DEFAULT_FALLBACK_OCR_MODEL

        return DEFAULT_FALLBACK_OCR_MODEL
    except Exception:
        return "qwen3-vl:8b"


def _make_service(
    pdf_path: Path,
    pages_to_ocr: list[int],
    use_llm_ocr: bool = False,
    model_exists: bool = False,
    values: dict | None = None,
):
    """Build the OCRService the way run_extraction does (the converter's
    Step-3 entry): analyzer classification → request → OCRService. The
    model manager is stubbed (no Ollama), markitdown is disabled (pypdf
    tier — deterministic across environments), tesseract + poppler run LIVE.

    ``values`` are merged into the Settings override (both ``__init__``
    and ``process_pdf`` re-read Settings at call time — e.g.
    ``ocr.unlimited_ocr_path``)."""
    logs: list[tuple[str, str]] = []

    def log(msg, level="INFO"):
        logs.append((level, msg))

    if values:
        Settings._test_override = _TestSettings(values=values)
    total = len(PdfReader(str(pdf_path)).pages)
    request = ConversionRequest(
        input_path=pdf_path, output_dir=pdf_path.parent, use_llm_ocr=use_llm_ocr
    )
    scanned = list(pages_to_ocr)
    from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation

    analysis = PdfAnalysisResult(
        total_pages=total,
        scanned_pages=scanned,
        text_pages=[p for p in range(1, total + 1) if p not in set(scanned)],
        recommendation=PdfRecommendation.LLM_OCR if scanned else PdfRecommendation.NO_OCR,
        per_page=[
            PageAnalysis(i, i in set(scanned), "", "ocr" if i in set(scanned) else "skip")
            for i in range(1, total + 1)
        ],
    )
    service = OCRService(request, analysis, scanned, log_callback=log)
    service.model_manager = _StubModelManager(exists=model_exists)
    service._md_tool = None  # pypdf tier — deterministic across environments
    return service, logs


@pytest.fixture(autouse=True)
def _hermetic_env():
    """Offline Settings + snapshot of the pytesseract global the service
    mutates (production pins ``pytesseract.pytesseract.tesseract_cmd`` —
    restore it so later suites see the pristine value)."""
    prev_override = Settings._test_override
    prev_cmd = pytesseract.pytesseract.tesseract_cmd
    Settings._test_override = _TestSettings()
    yield
    pytesseract.pytesseract.tesseract_cmd = prev_cmd
    Settings._test_override = prev_override


# ════════════════════════════════════════════════════════════════════════════
# Layer 1: pure characterization (no Qt event loop, no workers)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestParsePageRangeCharacterization:
    """Pin the exact current semantics of the OCR dialog's range parser.

    O2 context (V0.6.0): a NON-EMPTY unparseable range ("abc", "0", "5-")
    still returns None at the PARSER level, but since V0.6.0 ``_do_convert``
    refuses to run on that shape (status warning, no worker) — the silent
    whole-document OCR is closed at the dialog layer. Typographic dashes
    are normalized BEFORE parsing (the pasted-from-PDF "2–4" family).
    """

    def _dialog_cls(self):
        from ui_qt.views.service_dialogs.dialogs.ocr_service_dialog import (
            OcrServiceDialog,
        )

        return OcrServiceDialog

    def test_all_and_empty_mean_none(self):
        assert self._dialog_cls()._parse_page_range("all") is None
        assert self._dialog_cls()._parse_page_range("") is None
        assert self._dialog_cls()._parse_page_range("  ALL  ") is None

    def test_simple_ranges(self):
        assert self._dialog_cls()._parse_page_range("1-3") == [1, 2, 3]
        assert self._dialog_cls()._parse_page_range("2-2") == [2]
        assert self._dialog_cls()._parse_page_range("1,3,5") == [1, 3, 5]
        assert self._dialog_cls()._parse_page_range("1, 3, 5") == [1, 3, 5]
        assert self._dialog_cls()._parse_page_range("1-3,5,7-9") == [1, 2, 3, 5, 7, 8, 9]

    def test_reversed_range_is_normalized(self):
        assert self._dialog_cls()._parse_page_range("3-1") == [1, 2, 3]

    def test_zero_filtered_out(self):
        assert self._dialog_cls()._parse_page_range("0-2") == [1, 2]
        assert self._dialog_cls()._parse_page_range("0") is None  # O2 pin

    def test_duplicates_collapse_sorted(self):
        assert self._dialog_cls()._parse_page_range("5,3,5,3") == [3, 5]

    def test_unparseable_parts_skipped(self):
        assert self._dialog_cls()._parse_page_range("1,abc,3") == [1, 3]

    # O2 pins (parser-level None shapes — the _do_convert guard is the fix)
    def test_o2_garbage_means_none_parser_level(self):
        assert self._dialog_cls()._parse_page_range("abc") is None

    def test_o2_open_ended_range_means_none_parser_level(self):
        assert self._dialog_cls()._parse_page_range("5-") is None

    # V0.6.0 (O2 fix): typographic dash normalization — ranges pasted from
    # PDFs/TOCs arrive with en/em/minus dashes.
    def test_endash_range_parses(self):
        assert self._dialog_cls()._parse_page_range("2\u20134") == [2, 3, 4]

    def test_emdash_range_parses(self):
        assert self._dialog_cls()._parse_page_range("2\u20144") == [2, 3, 4]

    def test_minus_sign_range_parses(self):
        assert self._dialog_cls()._parse_page_range("2\u22124") == [2, 3, 4]

    def test_endash_list_mixed_with_ascii(self):
        assert self._dialog_cls()._parse_page_range("1\u20133, 5, 7\u20138") == [1, 2, 3, 5, 7, 8]


@pytest.mark.skipif(not _fitz_available(), reason="pymupdf unavailable (fixture builder)")
class TestPrescanOnRealPdfs:
    """The deterministic pre-scan (core/ocr/ocr_prescan.py:148
    ``prescan_pages``) on REAL PDFs — the text-coverage threshold split.
    (The mocked-reader pins live in tests/test_ocr_prescan.py; these are
    the real-extraction shapes.)"""

    def test_text_rich_pdf_needs_no_ocr(self, tmp_path):
        path = _text_rich_pdf(tmp_path)
        scan = prescan_pages(path, [1, 2])
        assert scan.scanned_pages == []
        assert scan.digital_pages == [1, 2]
        assert scan.skip_model_load is True

    def test_mixed_pdf_flags_only_the_image_page(self, tmp_path):
        path = _mixed_pdf(tmp_path)
        scan = prescan_pages(path, [1, 2])
        assert scan.scanned_pages == [2]
        assert scan.digital_pages == [1]
        assert scan.skip_model_load is False

    def test_image_only_pdf_flags_every_page(self, tmp_path):
        path = _image_only_pdf(tmp_path)
        scan = prescan_pages(path, [1, 2])
        assert scan.scanned_pages == [1, 2]
        assert scan.skip_model_load is False

    def test_empty_candidate_list_is_a_noop(self, tmp_path):
        scan = prescan_pages(_mixed_pdf(tmp_path), [])
        assert scan.scanned_pages == [] and scan.digital_pages == []
        assert scan.total_scanned == 0

    def test_fail_open_on_unreadable_pdf(self, tmp_path):
        scan = prescan_pages(tmp_path / "nope.pdf", [1, 2])
        assert scan.scanned_pages == []  # fail-open: empty result
        assert scan.skip_model_load is True

    def test_analyzer_and_prescan_agree_on_mixed(self, tmp_path):
        """The pre-scan heuristic mirrors the analyzer (same regex, same
        extractor) — on a real mixed PDF the two never disagree."""
        path = _mixed_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        scan = prescan_pages(path, [1, 2])
        assert analysis.scanned_pages == [2]
        assert scan.scanned_pages == analysis.scanned_pages
        assert scan.digital_pages == analysis.text_pages == [1]


# ════════════════════════════════════════════════════════════════════════════
# Layer 2: service-level end-to-end — LIVE tesseract cascade
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _fitz_available(), reason="pymupdf unavailable (fixture builder)")
@pytest.mark.skipif(not _tesseract_live(), reason="tesseract binary unavailable (LIVE gate)")
@pytest.mark.skipif(not _pdftoppm_live(), reason="pdftoppm unavailable (LIVE gate)")
class TestOcrServiceLiveCascade:
    """``OCRService.process_pdf`` with REAL poppler rasterization and REAL
    tesseract OCR on real PDFs — the auto-cascade the converter drives.
    (The mocked-boundary pins live in tests/test_p4_edge_cases_ocr.py.)"""

    def test_mixed_pdf_cascade_recovers_image_page_with_tesseract(self, tmp_path):
        """The headline LIVE flow: analyzer flags the image page →
        rasterize (real pdftoppm) → tesseract returns the actual text."""
        path = _mixed_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        assert analysis.scanned_pages == [2]

        service, logs = _make_service(path, analysis.scanned_pages)
        # O1 fix evidence: the blank setting resolved to the real binary.
        import shutil

        assert service._tesseract_cmd == shutil.which("tesseract")

        results = service.process_pdf(path)

        assert results[1].success is True
        assert results[1].engine_used == OcrEngine.MARKITDOWN  # pypdf tier (deterministic)
        assert results[1].text == DIGITAL_TEXT
        assert results[2].success is True
        assert results[2].engine_used == OcrEngine.TESSERACT
        assert "RAPID" in results[2].text.upper()
        assert "OPTICAL" in results[2].text.upper()
        assert any("Tesseract p.2" in m for _, m in logs)

        markdown = OCRService.build_markdown(results)
        assert "RAPID" in markdown.upper() and DIGITAL_TEXT in markdown
        assert "<!-- original page 1 -->" in markdown
        assert "<!-- original page 2 -->" in markdown

    def test_text_rich_pdf_skips_model_and_ocr_machinery(self, tmp_path):
        """A text-rich PDF needs no OCR: no model probe, no rasterization,
        every page extracted via the digital tier."""
        path = _text_rich_pdf(tmp_path)
        rasterized: list[dict] = []
        real_cfb = pdf2image.convert_from_bytes

        def counting_cfb(data, **kwargs):
            rasterized.append(kwargs)
            return real_cfb(data, **kwargs)

        pdf2image.convert_from_bytes = counting_cfb
        try:
            service, _logs = _make_service(path, [], use_llm_ocr=True)
            results = service.process_pdf(path)
        finally:
            pdf2image.convert_from_bytes = real_cfb

        assert set(results) == {1, 2}
        assert all(r.success for r in results.values())
        assert all(r.engine_used == OcrEngine.MARKITDOWN for r in results.values())
        assert all(r.text == DIGITAL_TEXT for r in results.values())
        assert rasterized == []  # never rasterized
        assert service.model_manager.exists_calls == []  # never probed Ollama

    def test_prescan_refines_target_and_tesseract_recovers(self, tmp_path):
        """use_llm_ocr path on a real mixed PDF: the V18.2.16 pre-scan keeps
        the scanned page as the OCR target, the Ollama model is probed
        exactly once (stub: not found), the digital page stays digital, and
        the scanned page is recovered by LIVE tesseract."""
        path = _mixed_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        service, logs = _make_service(path, analysis.scanned_pages, use_llm_ocr=True)

        results = service.process_pdf(path)

        assert any("V18.2.16 Pre-scan" in m for _, m in logs)
        assert any("Pre-scan refined OCR target" in m for _, m in logs)
        assert service.model_manager.exists_calls == [_default_ocr_model()]
        assert any(f"Model '{_default_ocr_model()}' not found in Ollama" in m for _, m in logs)
        assert results[1].engine_used == OcrEngine.MARKITDOWN
        assert results[1].text == DIGITAL_TEXT
        assert results[2].engine_used == OcrEngine.TESSERACT
        assert results[2].success is True
        assert "RAPID" in results[2].text.upper()

    def test_unlimited_ocr_fail_open_falls_through_to_tesseract(self, tmp_path):
        """ocr.unlimited_ocr_path configured (torch/transformers absent in
        this sandbox → the engine's load() fails for real): the batch comes
        back 0-success, the page is NOT marked handled, and the normal
        cascade recovers it with LIVE tesseract. This is the fail-open
        contract between service.py:308 (the unlimited phase) and the
        per-page loop."""
        path = _mixed_pdf(tmp_path)
        analysis = PdfAnalyzer().analyze(path)
        values = {"ocr.unlimited_ocr_path": str(tmp_path / "no-such-unlimited-model")}
        service, logs = _make_service(path, analysis.scanned_pages, values=values)

        results = service.process_pdf(path)

        assert any("UnlimitedOCR: batch processing 1 scanned pages" in m for _, m in logs)
        assert any("UnlimitedOCR batch done: 0/1 pages extracted" in m for _, m in logs)
        assert results[2].success is True
        assert results[2].engine_used == OcrEngine.TESSERACT
        assert "RAPID" in results[2].text.upper()

    def test_pages_to_ocr_respected_for_digital_pages_too(self, tmp_path):
        """A page flagged scanned is OCR'd even when its sibling is digital
        — the per-page loop honors pages_to_ocr exactly."""
        path = _mixed_pdf(tmp_path)
        service, _logs = _make_service(path, [2])
        results = service.process_pdf(path)
        assert set(results) == {1, 2}
        assert results[1].engine_used == OcrEngine.MARKITDOWN
        assert results[2].engine_used == OcrEngine.TESSERACT


# ════════════════════════════════════════════════════════════════════════════
# Layer 2: UnlimitedOCREngine contract (core/ocr/unlimited_ocr.py — 0% → netted)
# ════════════════════════════════════════════════════════════════════════════


class _FakeUnlimitedModel:
    """Duck-typed Unlimited-OCR model: ``infer_multi`` writes one .md (or
    .json) file per input image, exactly like the real engine."""

    def __init__(self, ext: str = ".md", text_field: str | None = None):
        self.ext = ext
        self.text_field = text_field
        self.calls: list[dict] = []

    def infer_multi(self, tokenizer, prompt, image_files, output_path, image_size, max_length):
        self.calls.append(
            {
                "prompt": prompt,
                "image_files": list(image_files),
                "output_path": str(output_path),
                "image_size": image_size,
                "max_length": max_length,
            }
        )
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in image_files:
            stem = Path(f).stem
            if self.ext == ".json":
                payload = {"text": f"JSON TEXT {stem}"}
                (out_dir / f"{stem}.json").write_text(json.dumps(payload), encoding="utf-8")
            else:
                (out_dir / f"{stem}{self.ext}").write_text(
                    f"FAKE TEXT FOR {stem}", encoding="utf-8"
                )


@pytest.mark.skipif(not _fitz_available(), reason="pymupdf unavailable (fixture builder)")
class TestUnlimitedOcrContract:
    """The W8 coverage-desert module. What it IS: a batch OCR engine that
    rasterizes the flagged pypdf pages to JPEG (real pdftoppm), hands them
    to a transformers model's ``infer_multi`` in ONE call (32K context —
    the whole point vs per-page Qwen), then reads the per-image .md/.json
    outputs back into OcrResults keyed by page number. The model itself is
    a GPU/external artifact → contract-level here, LIVE on the rig."""

    def _engine(self, model=None) -> object:
        from core.ocr.unlimited_ocr import UnlimitedOCREngine

        logs: list[tuple[str, str]] = []

        def log(msg, level="INFO"):
            logs.append((level, msg))

        eng = UnlimitedOCREngine(model_path="bogus-model-path", log_callback=log)
        if model is not None:
            eng._model = model
            eng._tokenizer = object()
        eng._logs = logs
        return eng

    def test_engine_is_an_ocr_engine_abc(self):
        from core.ocr.base import OCREngine

        eng = self._engine()
        assert isinstance(eng, OCREngine)
        assert callable(eng.process_page) and callable(eng.engine_name)

    def test_engine_name_reports_model_folder(self, tmp_path):
        model_dir = tmp_path / "my-ocr-model"
        model_dir.mkdir()
        from core.ocr.unlimited_ocr import UnlimitedOCREngine

        eng = UnlimitedOCREngine(model_path=str(model_dir))
        assert "my-ocr-model" in eng.engine_name()
        assert "UnlimitedOCR" in eng.engine_name()

    def test_load_fails_without_torch(self, monkeypatch):
        """load() is fail-closed with a traceable ERROR log when the
        torch/transformers stack is missing (the sandbox shape; on the rig
        the same ImportError branch fires via the sys.modules trick)."""
        monkeypatch.setitem(sys.modules, "torch", None)
        monkeypatch.setitem(sys.modules, "transformers", None)
        eng = self._engine()
        assert eng.load() is False
        assert any("UnlimitedOCR requires" in m and lvl == "ERROR" for lvl, m in eng._logs), (
            eng._logs
        )

    def test_process_batch_not_loaded_reports_all_pages_failed(self, tmp_path):
        """No model (and load disabled) → every page gets a failed
        OcrResult — never a crash, never a silent skip."""
        from core.models import OcrEngine as _OE

        eng = self._engine(model=None)
        eng.load = lambda: False  # force the not-loaded branch deterministically
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        res = eng.process_batch(list(pages), [1, 2])
        assert set(res) == {1, 2}
        for r in res.values():
            assert r.success is False
            assert r.engine_used == _OE.NONE
            assert r.error_msg == "UnlimitedOCR not loaded"

    def test_process_batch_full_flow_with_real_rasterization(self, tmp_path):
        """LIVE pdftoppm: the flagged pages are rasterized to JPEG, handed
        to infer_multi in ONE call with the pinned prompt + sizes, and the
        .md outputs are read back keyed by the right page numbers.

        V0.6.0 (4-c) pin: the caller's ``image_max_size`` reaches the
        model (service.py:310 passes ``request.image_max_size`` — the
        parameter used to be dead and the constructor default always won)."""
        model = _FakeUnlimitedModel()
        eng = self._engine(model=model)
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages

        res = eng.process_batch(list(pages), [1, 2], image_max_size=999, poppler_path="/usr/bin")

        assert set(res) == {1, 2}
        for pn, r in res.items():
            assert r.success is True
            assert r.text == f"FAKE TEXT FOR page_{pn:04d}"
        assert len(model.calls) == 1  # ONE batch call — the module's whole point
        call = model.calls[0]
        assert call["prompt"] == "<image>document parsing."
        assert call["image_size"] == 999
        assert all(f.endswith(".jpg") for f in call["image_files"])

    def test_process_batch_image_size_falls_back_to_constructor(self, tmp_path):
        """No caller value → the constructor's ``image_size`` wins (1024 by
        default — the pre-V0.6.0 behavior, now only the fallback)."""
        model = _FakeUnlimitedModel()
        eng = self._engine(model=model)
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        eng.process_batch(list(pages), [1], poppler_path="/usr/bin")
        assert model.calls[0]["image_size"] == 1024

    def test_process_batch_json_output_shape(self, tmp_path):
        """The .json output shape: ``{"text": ...}`` (or ``content``) is
        unwrapped; priority .md > .json > .txt."""
        model = _FakeUnlimitedModel(ext=".json")
        eng = self._engine(model=model)
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        res = eng.process_batch(list(pages), [1], poppler_path="/usr/bin")
        assert res[1].success is True
        assert res[1].text == "JSON TEXT page_0001"

    def test_empty_rasterization_keeps_page_numbers_correct(self, tmp_path, monkeypatch):
        """O3 (V0.6.0): when a page's rasterization returns EMPTY, that
        page is skipped — and every LATER result must still be keyed by
        its own page number. Before the fix the image_paths enumeration
        shifted relative to the zip enumeration → page 2's text landed
        under key -1 and page 3's under key 2."""
        model = _FakeUnlimitedModel()
        eng = self._engine(model=model)
        pdf = _image_only_pdf(tmp_path, n_pages=3, name="three.pdf")
        pages = PdfReader(str(pdf)).pages

        real_cfb = pdf2image.convert_from_bytes
        state = {"n": 0}

        def empty_first(data, **kwargs):
            state["n"] += 1
            if state["n"] == 1:
                return []  # page 1 rasterization yields nothing
            return real_cfb(data, **kwargs)

        monkeypatch.setattr(pdf2image, "convert_from_bytes", empty_first)
        res = eng.process_batch(list(pages), [1, 2, 3], poppler_path="/usr/bin")

        assert set(res) == {2, 3}  # page 1 skipped, no bogus -1 key
        assert res[2].success is True and res[2].text == "FAKE TEXT FOR page_0002"
        assert res[3].success is True and res[3].text == "FAKE TEXT FOR page_0003"

    def test_inference_failure_reports_all_pages(self, tmp_path):
        """infer_multi raising → every page gets a failed result carrying
        the error (never a crash, never a partial silent result)."""
        from core.models import OcrEngine as _OE

        class ExplodingModel:
            def infer_multi(self, *a, **k):
                raise RuntimeError("CUDA out of memory")

        eng = self._engine(model=ExplodingModel())
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        res = eng.process_batch(list(pages), [1, 2], poppler_path="/usr/bin")
        assert set(res) == {1, 2}
        for r in res.values():
            assert r.success is False
            assert r.engine_used == _OE.NONE
            assert "CUDA out of memory" in r.error_msg

    def test_process_page_delegates_to_batch(self, tmp_path):
        model = _FakeUnlimitedModel()
        eng = self._engine(model=model)
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        r = eng.process_page(pages[0], 1)
        assert r.success is True
        assert r.text == "FAKE TEXT FOR page_0001"

    def test_process_page_empty_batch_default(self, tmp_path, monkeypatch):
        """When the batch yields NO result at all (rasterization returned
        nothing), process_page returns the explicit empty-batch failure."""
        eng = self._engine(model=_FakeUnlimitedModel())
        pages = PdfReader(str(_image_only_pdf(tmp_path))).pages
        monkeypatch.setattr(pdf2image, "convert_from_bytes", lambda data, **kwargs: [])
        r = eng.process_page(pages[0], 7)
        assert r.success is False
        assert r.error_msg == "Batch returned no result"


# ════════════════════════════════════════════════════════════════════════════
# Layer 2: QwenOCREngine contract (core/ocr/qwen_ocr.py — GPU/vision model →
# contract-level here; the live Ollama vision run is a RIG CHECKLIST item)
# ════════════════════════════════════════════════════════════════════════════


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(self._payload)

    def json(self):
        return self._payload


@pytest.mark.skipif(not _fitz_available(), reason="pymupdf unavailable (fixture builder)")
class TestQwenOcrContract:
    """The Ollama vision adapter the OCR dialog delegates to
    (ocr_service_dialog.py:1055 ``_ocr_ollama`` → ``QwenOCREngine``).
    The HTTP boundary is mocked; rasterization runs LIVE where possible."""

    def _engine(self, **kwargs):
        from core.ocr.qwen_ocr import QwenOCREngine

        defaults = {"model_name": "test-vision-model", "retries": 1}
        defaults.update(kwargs)
        return QwenOCREngine(**defaults)

    def test_engine_shape(self):
        from core.ocr.base import OCREngine

        eng = self._engine()
        assert isinstance(eng, OCREngine)
        assert eng.engine_name() == "Qwen3-VL (test-vision-model)"

    def test_page_to_image_bytes_live_rasterization(self, tmp_path):
        """REAL pdftoppm: a pypdf page becomes PNG bytes (the ``size``
        kwarg — width-capped rasterization, no dpi)."""
        pages = PdfReader(str(_mixed_pdf(tmp_path))).pages
        raw = self._engine()._page_to_image_bytes(pages[0])
        assert raw is not None and raw[:8] == b"\x89PNG\r\n\x1a\n"

    def test_page_to_image_bytes_none_on_raster_failure(self, monkeypatch):
        import core.ocr.qwen_ocr as qwen_mod

        def boom(data, **kwargs):
            raise RuntimeError("pdftoppm exploded")

        monkeypatch.setattr(qwen_mod, "convert_from_bytes", boom)
        eng = self._engine()
        assert eng._page_to_image_bytes(object()) is None

    def test_try_endpoint_generate_response_key(self, monkeypatch):

        seen: dict = {}

        def fake_safe(method, url, **kwargs):
            seen.update({"method": method, "url": url, "payload": kwargs.get("json")})
            return _FakeResponse(200, {"response": "  generate text  "})

        monkeypatch.setattr("utils.network.safe_ollama_request", fake_safe)
        text = self._engine()._try_endpoint("/api/generate", {"model": "m"}, "response")
        assert text == "generate text"
        assert seen["method"] == "POST" and seen["url"].endswith("/api/generate")
        assert seen["payload"]["model"] == "m"

    def test_try_endpoint_chat_nested_response_key(self, monkeypatch):
        monkeypatch.setattr(
            "utils.network.safe_ollama_request",
            lambda *a, **k: _FakeResponse(200, {"message": {"content": "chat text"}}),
        )
        text = self._engine()._try_endpoint("/api/chat", {"model": "m"}, "message.content")
        assert text == "chat text"

    def test_try_endpoint_400_raises_vision400_with_body(self, monkeypatch):
        """A 400 carries the actual Ollama error body (e.g. 'model does
        not support images') — the user sees the specific reason."""
        from core.ocr.qwen_ocr import _Vision400Error

        monkeypatch.setattr(
            "utils.network.safe_ollama_request",
            lambda *a, **k: _FakeResponse(400, {"error": "model does not support images"}),
        )
        with pytest.raises(_Vision400Error) as excinfo:
            self._engine()._try_endpoint("/api/generate", {}, "response")
        assert excinfo.value.detail == "model does not support images"

    def test_call_ollama_vision_unreachable_returns_none(self, monkeypatch):
        """Ollama down (connection refused) → None after the retries —
        the caller (dialog auto-cascade) falls through to Tesseract."""
        import requests as _requests

        def refuse(method, url, **kwargs):
            raise _requests.ConnectionError("Connection refused")

        monkeypatch.setattr("utils.network.safe_ollama_request", refuse)
        assert self._engine(retries=1)._call_ollama_vision(b"imgbytes") is None

    def test_call_ollama_vision_400_both_endpoints_returns_none(self, monkeypatch):
        """Both endpoints 400 (the text-only-GGUF-without-mmproj shape) →
        the specific guidance is logged, the engine returns None (no
        exception escapes to the caller)."""
        monkeypatch.setattr(
            "utils.network.safe_ollama_request",
            lambda *a, **k: _FakeResponse(400, {"error": "no vision projector"}),
        )
        assert self._engine(retries=1)._call_ollama_vision(b"imgbytes") is None

    def test_call_ollama_vision_success(self, monkeypatch):
        monkeypatch.setattr(
            "utils.network.safe_ollama_request",
            lambda *a, **k: _FakeResponse(200, {"response": "extracted page text"}),
        )
        assert self._engine(retries=1)._call_ollama_vision(b"imgbytes") == "extracted page text"

    def test_process_page_success_shape(self, monkeypatch):
        from core.models import OcrEngine as _OE

        eng = self._engine()
        monkeypatch.setattr(eng, "_page_to_image_bytes", lambda page: b"png")
        monkeypatch.setattr(eng, "_call_ollama_vision", lambda b: "page text here")
        r = eng.process_page(object(), 3)
        assert r.success is True
        assert r.page_num == 3 and r.text == "page text here"
        assert r.engine_used == _OE.QWEN_VL

    def test_process_page_no_text_failure_shape(self, monkeypatch):
        eng = self._engine()
        monkeypatch.setattr(eng, "_page_to_image_bytes", lambda page: b"png")
        monkeypatch.setattr(eng, "_call_ollama_vision", lambda b: None)
        r = eng.process_page(object(), 3)
        assert r.success is False
        assert r.error_msg == "Qwen VL returned no text after all retries"

    def test_process_page_raster_failure_shape(self, monkeypatch):
        eng = self._engine()
        monkeypatch.setattr(eng, "_page_to_image_bytes", lambda page: None)
        r = eng.process_page(object(), 5)
        assert r.success is False
        assert r.error_msg == "Failed to render page as image"


# ════════════════════════════════════════════════════════════════════════════
# Layer 2/3: dialog-level — engine backends direct, then the worker drive
# ════════════════════════════════════════════════════════════════════════════


def _make_dialog():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from ui_qt.views.service_dialogs.dialogs.ocr_service_dialog import (
        OcrServiceDialog,
    )

    return OcrServiceDialog(_StubController()), app


class _StubController:
    """The OCR dialog stores the controller but never calls it (verified:
    the only controller reference is the __init__ assignment)."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _tesseract_live(), reason="tesseract binary unavailable (LIVE gate)")
class TestDialogEngineBackends:
    """The dialog's per-engine backends, called directly (no worker) —
    the LIVE tesseract paths including the O1 image-branch fix."""

    def test_tesseract_on_image_file_live(self, tmp_path):
        """O1 fix evidence: a bare IMAGE file goes through the subprocess
        branch with the auto-resolved binary (was: exec of the Windows
        default path → FileNotFoundError)."""
        png = tmp_path / "scan.png"
        png.write_bytes(_text_image_png())

        dlg, _ = _make_dialog()
        text = dlg._ocr_tesseract(png, pages=None)
        assert "RAPID" in text.upper()
        assert "OPTICAL" in text.upper()

    def test_tesseract_on_pdf_page_filter_live(self, tmp_path):
        """PDF branch with a page selection: only the requested page is
        rasterized + OCR'd, with the ``<!-- page N -->`` marker."""
        pdf = _mixed_pdf(tmp_path)
        dlg, _ = _make_dialog()
        text = dlg._ocr_tesseract(pdf, pages=[2])
        assert "<!-- page 2 -->" in text
        assert "<!-- page 1 -->" not in text
        assert "RAPID" in text.upper()

    def test_pypdf_backend_page_filter(self, tmp_path):
        pdf = _text_rich_pdf(tmp_path, n_pages=2)
        dlg, _ = _make_dialog()
        text = dlg._ocr_pypdf(pdf, pages=[2])
        assert "<!-- page 2 -->" in text and "<!-- page 1 -->" not in text
        assert DIGITAL_TEXT in text

    def test_pypdf_backend_out_of_range_pages_skipped(self, tmp_path):
        pdf = _text_rich_pdf(tmp_path, n_pages=1)
        dlg, _ = _make_dialog()
        assert dlg._ocr_pypdf(pdf, pages=[99]) == ""

    def test_auto_engine_uses_pypdf_for_text_rich_pdf(self, tmp_path):
        """Auto-cascade step 1: a digital PDF returns at the pypdf tier —
        no Ollama, no tesseract."""
        pdf = _text_rich_pdf(tmp_path)
        dlg, _ = _make_dialog()
        text = dlg._ocr_auto(pdf)
        assert DIGITAL_TEXT in text

    def test_auto_engine_cascade_falls_through_to_tesseract_live(self, tmp_path):
        """Auto-cascade on an IMAGE (no pypdf tier for images): Ollama
        vision fails (dead endpoint, hermetic) → VLM fails → LIVE
        tesseract recovers the text. The full 4-step cascade, for real."""
        png = tmp_path / "scan.png"
        png.write_bytes(_text_image_png())
        dlg, _ = _make_dialog()
        text = dlg._ocr_auto(png)
        assert "RAPID" in text.upper()


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _fitz_available(), reason="pymupdf unavailable (fixture builder)")
@pytest.mark.skipif(not _tesseract_live(), reason="tesseract binary unavailable (LIVE gate)")
class TestOcrDialogEndToEndDrive:
    """Drive ``_do_convert`` exactly as the UI does: the SimpleWorker
    thread, the queued signals, ``_on_convert_finished`` on the main
    thread, the modal (monkeypatched to a recorder — ``msg.exec()`` must
    never block a test)."""

    def _spin_until_done(self, app, dlg, timeout_ms: int = 120000) -> None:
        import time

        waited = 0
        while waited < timeout_ms:
            app.processEvents()
            if dlg.action_btn.text() == "Close" or dlg.status_label.text().startswith("❌"):
                break
            time.sleep(0.02)
            waited += 20

    def test_full_tesseract_flow_lands_success(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])

        import ui_qt.views.service_dialogs.dialogs.ocr_service_dialog as ocr_mod

        recorded: list[tuple[str, str, str | None]] = []
        monkeypatch.setattr(
            ocr_mod,
            "_show_success_modal",
            lambda parent, title, message, file_path=None, on_try_another=None: recorded.append(
                (title, message, file_path)
            ),
        )

        dlg = ocr_mod.OcrServiceDialog(_StubController())
        src = _mixed_pdf(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        dlg._files.append(str(src))
        dlg.file_list.addItem(str(src))
        dlg.out_edit.setText(str(out_dir))
        idx = dlg.engine_combo.findData("tesseract")
        assert idx >= 0
        dlg.engine_combo.setCurrentIndex(idx)

        dlg._do_convert()
        self._spin_until_done(app, dlg)

        out = out_dir / f"{src.stem}_ocr.md"
        assert out.exists(), dlg.status_label.text()
        content = out.read_text(encoding="utf-8")
        assert "<!-- page 1 -->" in content
        assert "<!-- page 2 -->" in content
        assert "RAPID" in content.upper()
        assert DIGITAL_TEXT in content

        assert dlg.action_btn.text() == "Close"
        assert dlg.action_btn.isEnabled()
        assert dlg.status_label.text().startswith("Done! 1 file(s) processed")
        assert not dlg.again_btn.isHidden()

        assert recorded and recorded[0][0] == "🔍 OCR Complete"
        assert recorded[0][2] == str(out_dir)

    def test_endash_page_range_cuts_through_the_worker(self, tmp_path, monkeypatch):
        """V0.6.0 (O2): the pasted-from-PDF en-dash range now selects the
        requested pages (was: parse-as-garbage → silently ALL pages)."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])

        import ui_qt.views.service_dialogs.dialogs.ocr_service_dialog as ocr_mod

        monkeypatch.setattr(ocr_mod, "_show_success_modal", lambda *a, **k: None)
        dlg = ocr_mod.OcrServiceDialog(_StubController())
        src = _mixed_pdf(tmp_path)
        out_dir = tmp_path / "out2"
        out_dir.mkdir()
        dlg._files.append(str(src))
        dlg.out_edit.setText(str(out_dir))
        dlg.engine_combo.setCurrentIndex(dlg.engine_combo.findData("tesseract"))
        dlg.range_edit.setText("2\u20132")  # pages 2–2 via en-dash

        dlg._do_convert()
        self._spin_until_done(app, dlg)

        out = out_dir / f"{src.stem}_ocr.md"
        assert out.exists(), dlg.status_label.text()
        content = out.read_text(encoding="utf-8")
        assert "<!-- page 2 -->" in content
        assert "<!-- page 1 -->" not in content  # the range was honored
        assert "RAPID" in content.upper()

    def test_o2_garbage_range_guards_no_worker_spawned(self, tmp_path, monkeypatch):
        """V0.6.0 (O2): an unparseable NON-EMPTY range warns and refuses
        to run — the silent whole-document OCR is closed."""
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])

        import ui_qt.views.service_dialogs.dialogs.ocr_service_dialog as ocr_mod

        dlg = ocr_mod.OcrServiceDialog(_StubController())
        dlg._files.append(str(_mixed_pdf(tmp_path)))
        out_dir = tmp_path / "guard"
        out_dir.mkdir()
        dlg.out_edit.setText(str(out_dir))

        for garbage in ("abc", "0", "5-"):
            dlg.range_edit.setText(garbage)
            dlg._do_convert()
            assert dlg.status_label.text().startswith("⚠️ Couldn't read that page range")
            assert dlg._worker is None
        assert not list(out_dir.iterdir())

    def test_missing_files_and_folder_guards(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])

        import ui_qt.views.service_dialogs.dialogs.ocr_service_dialog as ocr_mod

        dlg = ocr_mod.OcrServiceDialog(_StubController())
        dlg._do_convert()  # no files
        assert dlg.status_label.text() == "⚠️ Add at least one file first."
        assert dlg._worker is None

        dlg._files.append(str(_mixed_pdf(tmp_path)))
        dlg._do_convert()  # files but no output folder
        assert dlg.status_label.text() == "⚠️ Please choose an output folder."
        assert dlg._worker is None

    def test_reentrancy_guard_while_worker_runs(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])

        import ui_qt.views.service_dialogs.dialogs.ocr_service_dialog as ocr_mod

        monkeypatch.setattr(ocr_mod, "_show_success_modal", lambda *a, **k: None)
        dlg = ocr_mod.OcrServiceDialog(_StubController())
        src = _mixed_pdf(tmp_path)
        out_dir = tmp_path / "out3"
        out_dir.mkdir()
        dlg._files.append(str(src))
        dlg.out_edit.setText(str(out_dir))
        dlg.engine_combo.setCurrentIndex(dlg.engine_combo.findData("tesseract"))

        dlg._do_convert()
        assert dlg._worker is not None and dlg._worker.is_running()
        dlg._do_convert()  # second click while running
        assert dlg.status_label.text().startswith("⏳ Already converting")
        self._spin_until_done(app, dlg)
        assert dlg.action_btn.text() == "Close"
