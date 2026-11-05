"""V0.7.0 (wizard rework ②, item 2d) — the ocr_mode backend pins (D3 + D2).

New ``ConversionRequest.ocr_mode`` (digital / scanned / auto, default
auto); ``extraction.py`` branches on it; the scanned branch SUPERSEDES
the academic-only ``force_ocr_all_pages`` gate (B2) — the old flag maps
to ``ocr_mode="scanned"`` as a deprecated alias for one release. The
scanned-mode ENGINE SET per D2: vision-capable summarisation model →
``primary_ocr_model`` → OlmOCR → Qwen VL — Tesseract, PaddleOCR, and the
local-VLM fallback are EXCLUDED (never constructed, never called).

Round-trip pin: WizardState.ocr_mode → to_ui_data → _REQUEST_FIELD_MAP →
ConversionRequest (the audit's dead-control lesson, §1).
"""

from __future__ import annotations

import dataclasses
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_MODELS = _project_root / "core" / "models" / "models.py"
_EXTRACTION = _project_root / "core" / "pipeline" / "conversion" / "extraction.py"
_SERVICE = _project_root / "core" / "ocr" / "service.py"
_CONTROLLER = _project_root / "controller.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Request-field + resolver pins
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrModeRequestField:
    def test_field_exists_with_auto_default(self):
        from core.models import ConversionRequest

        fields = {f.name: f for f in dataclasses.fields(ConversionRequest)}
        assert "ocr_mode" in fields, "ConversionRequest.ocr_mode must exist"
        assert fields["ocr_mode"].default == "auto"

    def test_resolver_passthrough_and_normalisation(self):
        from core.pipeline.conversion.extraction import resolve_ocr_mode

        for mode in ("digital", "scanned", "auto"):
            req = types.SimpleNamespace(ocr_mode=mode, force_ocr_all_pages=False)
            assert resolve_ocr_mode(req) == mode
        # Truly unknown / empty / missing values degrade to auto.
        for bad in ("SCANNED?", "weird", "", None):
            req = types.SimpleNamespace(ocr_mode=bad, force_ocr_all_pages=False)
            assert resolve_ocr_mode(req) == "auto", f"{bad!r} must degrade to auto"
        req = types.SimpleNamespace(force_ocr_all_pages=False)
        assert resolve_ocr_mode(req) == "auto"
        # Whitespace + case are normalised into the canonical vocabulary.
        req = types.SimpleNamespace(ocr_mode="  Digital  ", force_ocr_all_pages=False)
        assert resolve_ocr_mode(req) == "digital"

    def test_deprecated_alias_maps_to_scanned_for_any_source(self):
        """THE B2 FIX: force_ocr_all_pages honored the all-pages branch only
        for academic papers (extraction.py:472-490) — the Full-OCR and
        Infographics presets were silent no-ops on any other source. As a
        deprecated alias it now maps to scanned for ANY source type."""
        from core.pipeline.conversion.extraction import resolve_ocr_mode

        for source in ("normal_book", "academic_paper", "visual_catalogue"):
            req = types.SimpleNamespace(
                ocr_mode="auto", force_ocr_all_pages=True, source_type=source
            )
            assert resolve_ocr_mode(req) == "scanned", (
                f"B2: the alias must map to scanned for {source}"
            )

    def test_explicit_mode_wins_over_alias(self):
        """An explicit digital/scanned choice is never overridden by the
        legacy flag; the alias only fires from auto."""
        from core.pipeline.conversion.extraction import resolve_ocr_mode

        req = types.SimpleNamespace(ocr_mode="digital", force_ocr_all_pages=True)
        assert resolve_ocr_mode(req) == "digital"
        req = types.SimpleNamespace(ocr_mode="scanned", force_ocr_all_pages=False)
        assert resolve_ocr_mode(req) == "scanned"


# ═══════════════════════════════════════════════════════════════════════════
# Extraction-branch AST pins
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractionBranchPins:
    def test_three_mode_branch_exists(self):
        src = _src(_EXTRACTION)
        assert "def resolve_ocr_mode(" in src
        assert "_ocr_mode = resolve_ocr_mode(request)" in src
        assert "request.ocr_mode = _ocr_mode" in src, (
            "the normalised mode must be written back for OCRService (D2)"
        )
        for needle in ('_ocr_mode == "scanned"', '_ocr_mode == "digital"'):
            assert needle in src, f"mode branch {needle!r} missing"

    def test_scanned_branch_marks_all_pages(self):
        src = _src(_EXTRACTION)
        assert "analysis.recommendation = PdfRecommendation.LLM_OCR" in src
        assert 'p.recommended_action = "llm_ocr"' in src

    def test_digital_branch_disables_detection(self):
        src = _src(_EXTRACTION)
        assert "analysis.recommendation = PdfRecommendation.NO_OCR" in src
        assert "request.extract_figure_text = True" in src, (
            "digital mode turns figure-text extraction on (the card's promise)"
        )
        assert "request.extract_tables = True" in src

    def test_academic_force_gate_is_gone(self):
        """The old academic-only force branch (B2) is superseded."""
        src = _src(_EXTRACTION)
        assert (
            "forcing OlmOCR on ALL pages"
            not in src.replace("every page goes through the vision-OCR", "")
            or "Academic paper + Force OCR All Pages" not in src
        )
        assert "Academic paper + Force OCR All Pages" not in src

    def test_digital_gates_the_scanned_pdf_auto_switch(self):
        """Digital mode (the explicit 'trust the text layer' choice) turns
        the scanned-PDF content-type auto-detection OFF."""
        src = _src(_EXTRACTION)
        assert '_ocr_mode != "digital" and detect_scanned_pdf(' in src


# ═══════════════════════════════════════════════════════════════════════════
# D2 engine-set pins (scanned mode never constructs/calls Tesseract/Paddle/VLM)
# ═══════════════════════════════════════════════════════════════════════════


def _make_service(ocr_mode: str, logs: list) -> object:
    from core.models import (
        ConversionRequest,
        PageAnalysis,
        PdfAnalysisResult,
        PdfRecommendation,
    )
    from core.ocr.service import OCRService

    request = ConversionRequest(
        input_path=Path("book.pdf"),
        output_dir=Path("out"),
        ocr_mode=ocr_mode,
    )
    analysis = PdfAnalysisResult(
        total_pages=1,
        scanned_pages=[1],
        text_pages=[],
        recommendation=PdfRecommendation.LLM_OCR,
        per_page=[PageAnalysis(1, True, "", "llm_ocr")],
    )
    svc = OCRService(request, analysis, [1], log_callback=lambda m, l="INFO": logs.append(m))
    return svc


class TestScannedEngineSet:
    @pytest.fixture(autouse=True)
    def _isolated_settings(self, monkeypatch, tmp_path):
        """Isolated settings store with PaddleOCR requested ON — the D2
        exclusion is only observable when the user asked for it."""
        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))

        class _FakeSettings:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, path, default=None):
                return self._data.get(path, default)

            def set(self, path, value):
                self._data[path] = value

        import utils.settings as settings_mod

        fake = _FakeSettings({"ocr.use_paddleocr": True})
        monkeypatch.setattr(settings_mod.Settings, "_test_override", fake)
        yield

    def test_scanned_mode_excludes_paddle(self):
        logs: list = []
        svc = _make_service("scanned", logs)
        assert svc._scanned_mode is True
        assert svc._use_paddleocr is False, "D2: PaddleOCR must be excluded"
        assert svc._paddle_ocr is None, "D2: PaddleOCR must never be constructed"
        assert any("PaddleOCR excluded" in m for m in logs), (
            "the exclusion must be logged (observability)"
        )

    def test_auto_mode_keeps_paddle_toggle(self):
        """Auto mode keeps today's behavior — the settings toggle flows
        through untouched (paddle not installed here → the init logs it
        and disables it, but the D2 exclusion line must NOT appear)."""
        logs: list = []
        svc = _make_service("auto", logs)
        assert svc._scanned_mode is False
        assert not any("PaddleOCR excluded from the engine set" in m for m in logs)

    def test_scanned_page_never_calls_excluded_engines(self):
        """A failing vision cascade in scanned mode is an honest failure:
        _tesseract_ocr / _paddle_ocr_single / _vlm_ocr_fallback must never
        be invoked (each is monkeypatched to raise)."""
        from core.models import OcrEngine

        logs: list = []
        svc = _make_service("scanned", logs)

        def _forbidden(*a, **k):  # pragma: no cover - must never run
            raise AssertionError("D2: excluded engine was called in scanned mode")

        svc._page_to_image_bytes = lambda page, pn: b"fake-image"
        svc._provider_vision_ocr = lambda ib, pn: type(
            "R",
            (),
            {
                "page_num": pn,
                "text": "",
                "success": False,
                "engine_used": OcrEngine.NONE,
                "error_msg": "no vision",
            },
        )()
        svc._tesseract_ocr = _forbidden
        svc._paddle_ocr_single = _forbidden
        svc._vlm_ocr_fallback = _forbidden

        # qwen not loaded → the honest-failure path.
        result = svc._ocr_scanned_page(object(), page_num=1, qwen_loaded=False, poppler_ok=True)
        assert result.success is False
        assert "Scanned mode" in result.error_msg or "scanned mode" in result.error_msg

        # qwen loaded + vision fails → still no excluded engines.
        svc._qwen_ocr_single = lambda ib, pn, attempt=1: type(
            "R",
            (),
            {
                "page_num": pn,
                "text": "",
                "success": False,
                "engine_used": OcrEngine.NONE,
                "error_msg": "qwen failed",
            },
        )()
        result = svc._ocr_scanned_page(object(), page_num=1, qwen_loaded=True, poppler_ok=True)
        assert result.success is False

    def test_scanned_mode_forces_vision_with_llm_ocr_off(self):
        """D2: the user chose full vision OCR — the cascade runs even when
        use_llm_ocr is off (the vision path is the whole engine set)."""
        from core.models import OcrEngine

        logs: list = []
        svc = _make_service("scanned", logs)
        svc.request.use_llm_ocr = False
        svc._page_to_image_bytes = lambda page, pn: b"fake-image"
        svc._provider_vision_ocr = lambda ib, pn: type(
            "R",
            (),
            {
                "page_num": pn,
                "text": "read the page",
                "success": True,
                "engine_used": OcrEngine.QWEN_VL,
                "error_msg": "",
            },
        )()
        result = svc._ocr_scanned_page(object(), page_num=1, qwen_loaded=False, poppler_ok=True)
        assert result.success is True
        assert result.text == "read the page"


# ═══════════════════════════════════════════════════════════════════════════
# Round-trip pin (to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest)
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrModeRoundTrip:
    def test_map_row_exists(self):
        src = _src(_CONTROLLER)
        assert '("ocr_mode", "ocr_mode", "ocr.mode", "auto", None)' in src

    def test_state_to_request_round_trip(self, monkeypatch):
        """The real Controller's build_request_from_ui maps the wizard
        state's ocr_mode onto the request (the dead-control lesson)."""
        pytest.importorskip("controller")
        import controller as controller_mod

        class _FakeSettings:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, path, default=None):
                return self._data.get(path, default)

            def set(self, path, value):
                self._data[path] = value

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        from ui_qt.views.wizard_steps.shared import WizardState

        for mode in ("digital", "scanned", "auto"):
            state = WizardState()
            state.ocr_mode = mode
            state.input_path = "book.pdf"
            ui_data = state.to_ui_data()
            assert ui_data["ocr_mode"] == mode
            request = controller_mod.Controller().build_request_from_ui(ui_data)
            assert request.ocr_mode == mode, f"{mode} must round-trip to the request"

    def test_settings_default_is_auto(self):
        src = _src(_project_root / "utils" / "settings.py")
        assert '"mode": "auto"' in src, "the ocr.mode settings default"

    def test_wizard_loads_saved_mode(self):
        """_load_settings_into_state reads ocr.mode (open on what the user
        last chose) — the load-then-save discipline."""
        src = _src(_project_root / "ui_qt" / "views" / "wizard_view.py")
        assert '"ocr.mode"' in src
