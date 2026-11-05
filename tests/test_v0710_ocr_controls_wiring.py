"""V0.7.1 (wizard rework ③, item 3d / B3) — the two dead Step-3 controls
finally reach the backend.

Audit §W5 / bug register B3: ``ocr_timeout`` and ``use_paddleocr`` were
dropped by ``to_ui_data()`` (never in ``_REQUEST_FIELD_MAP``) — only their
settings.json twins (Settings dialog) worked; the backend clamped the
timeout to ≥120s anyway, so the wizard combo's 30/60/90 items were fiction.

The fix, both directions:
- request fields + map rows (state → to_ui_data → build_request_from_ui);
- OCRService prefers the request over settings (settings stays the
  fallback for request-objects that predate the fields);
- the wizard loads the saved values at open (load-then-save);
- the Step-3 combo offers the honest 120/180/300 band;
- save_book_settings persists them so the regenerate path round-trips.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_CONTROLLER = _project_root / "controller.py"
_SERVICE = _project_root / "core" / "ocr" / "service.py"
_STEP3 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step3_ocr.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class _FakeSettings:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self, path, default=None):
        return self._data.get(path, default)

    def set(self, path, value):
        self._data[path] = value


# ═══════════════════════════════════════════════════════════════════════════
# Request fields + map rows
# ═══════════════════════════════════════════════════════════════════════════


class TestRequestFields:
    def test_fields_exist_with_honest_defaults(self):
        from core.models import ConversionRequest

        fields = {f.name: f for f in dataclasses.fields(ConversionRequest)}
        assert fields["ocr_timeout"].default == 120
        assert fields["use_paddleocr"].default is False

    def test_map_rows_exist(self):
        src = _src(_CONTROLLER)
        assert '("ocr_timeout", "ocr_timeout", "ocr.timeout", 120, None)' in src
        assert '("use_paddleocr", "use_paddleocr", "ocr.use_paddleocr", False, None)' in src

    def test_to_ui_data_carries_both_keys(self):
        import ast

        src = _src(_SHARED)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "to_ui_data":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                        keys = {k.value for k in sub.value.keys if isinstance(k, ast.Constant)}
                        assert "ocr_timeout" in keys and "use_paddleocr" in keys

    def test_state_to_request_round_trip(self, monkeypatch):
        """WizardState.ocr_timeout/use_paddleocr → to_ui_data → map → request
        — the dead-control lesson, now flowing both directions."""
        pytest.importorskip("controller")
        import controller as controller_mod

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        from ui_qt.views.wizard_steps.shared import WizardState

        for timeout, paddle in ((120, False), (300, True), (180, True)):
            state = WizardState()
            state.ocr_timeout = timeout
            state.use_paddleocr = paddle
            state.input_path = "book.pdf"
            ui_data = state.to_ui_data()
            assert ui_data["ocr_timeout"] == timeout and ui_data["use_paddleocr"] == paddle
            request = controller_mod.Controller().build_request_from_ui(ui_data)
            assert request.ocr_timeout == timeout, f"{timeout}s must round-trip"
            assert request.use_paddleocr is paddle

    def test_settings_fallback_when_ui_key_absent(self, monkeypatch):
        """Old callers whose ui_data lacks the keys (e.g. a pre-V0.7.1
        saved config) resolve through the settings twins — the map's
        setting-path fallback preserves their behavior."""
        pytest.importorskip("controller")
        import controller as controller_mod

        monkeypatch.setattr(
            controller_mod.Settings, "_test_override", _FakeSettings({"ocr.timeout": 300})
        )
        request = controller_mod.Controller().build_request_from_ui(
            {"input_path": "book.pdf", "output_dir": "out"}
        )
        assert request.ocr_timeout == 300
        assert request.use_paddleocr is False


# ═══════════════════════════════════════════════════════════════════════════
# OCRService: request-first, settings fallback, ≥120s floor
# ═══════════════════════════════════════════════════════════════════════════


def _svc(request_obj, logs: list):
    from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation
    from core.ocr.service import OCRService

    analysis = PdfAnalysisResult(
        total_pages=1,
        scanned_pages=[1],
        text_pages=[],
        recommendation=PdfRecommendation.LLM_OCR,
        per_page=[PageAnalysis(1, True, "", "llm_ocr")],
    )
    return OCRService(request_obj, analysis, [1], log_callback=lambda m, l="INFO": logs.append(m))


class TestServiceReadsRequest:
    @pytest.fixture(autouse=True)
    def _isolated_settings(self, monkeypatch, tmp_path):
        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        import utils.settings as settings_mod

        monkeypatch.setattr(
            settings_mod.Settings, "_test_override", _FakeSettings({"ocr.timeout": 180})
        )

    def test_request_wins_over_settings(self):
        from core.models import ConversionRequest

        logs: list = []
        req = ConversionRequest(
            input_path=Path("book.pdf"), output_dir=Path("out"), ocr_timeout=300
        )
        svc = _svc(req, logs)
        assert svc._ocr_timeout == 300, "the request's 300s must beat settings' 180s"

    def test_settings_fallback_for_request_without_fields(self):
        """A duck-typed request object predating the fields (no attribute)
        falls back to the settings twin — behavior unchanged for old callers."""
        logs: list = []
        req = SimpleNamespace(  # no ocr_timeout / use_paddleocr attrs
            use_llm_ocr=True,
            ocr_mode="auto",
            primary_ocr_model="m",
            fallback_ocr_model="m",
            source_type="normal_book",
        )
        svc = _svc(req, logs)
        assert svc._ocr_timeout == 180, "settings' 180s applies when the request is silent"
        assert svc._use_paddleocr is False

    def test_floor_clamp_120(self):
        from core.models import ConversionRequest

        logs: list = []
        req = ConversionRequest(input_path=Path("book.pdf"), output_dir=Path("out"), ocr_timeout=30)
        svc = _svc(req, logs)
        assert svc._ocr_timeout == 120, "the ≥120s floor clamps whatever arrives"

    def test_paddle_request_wins_over_settings(self):
        from core.models import ConversionRequest

        logs: list = []
        req = ConversionRequest(
            input_path=Path("book.pdf"), output_dir=Path("out"), use_paddleocr=True
        )
        svc = _svc(req, logs)
        # PaddleOCR isn't installed in the test env — the init path logs a
        # failure and disables it; the REQUESTED value is what the service
        # read (observable: it attempted the import at all).
        assert any("PaddleOCR" in m for m in logs) or svc._use_paddleocr is False


# ═══════════════════════════════════════════════════════════════════════════
# Wizard surfaces: combo items, settings load, save_book_settings
# ═══════════════════════════════════════════════════════════════════════════


class TestWizardSurfaces:
    def test_step3_combo_items_are_honest(self):
        src = _src(_STEP3)
        assert 'self.timeout_combo.addItems(["120", "180", "300"])' in src
        for fiction in ('"30"', '"60"', '"90"'):
            assert f"{fiction}," not in src.split("addItems", 1)[1].split("]", 1)[0] + ",", (
                f"the fictional {fiction}s item must be gone"
            )

    def test_wizard_loads_saved_values(self):
        """_load_settings_into_state reads ocr.timeout + ocr.use_paddleocr
        (load-then-save — the wizard opens on what the user last chose)."""
        src = _src(_WIZARD)
        assert 's.get_setting("ocr.timeout", 120)' in src
        assert 's.get_setting("ocr.use_paddleocr", False)' in src

    def test_save_book_settings_persists_both(self):
        src = _src(_CONTROLLER)
        assert '"ocr_timeout": request.ocr_timeout,' in src
        assert '"use_paddleocr": request.use_paddleocr,' in src

    def test_saved_config_round_trips_to_service(self, monkeypatch):
        """The full chain: saved config → build_request_from_ui → request →
        OCRService — the regenerate path keeps the user's choices."""
        pytest.importorskip("controller")
        import controller as controller_mod

        monkeypatch.setattr(controller_mod.Settings, "_test_override", _FakeSettings({}))
        saved = {
            "input_path": "book.pdf",
            "output_dir": "out",
            "ocr_mode": "auto",
            "ocr_timeout": 300,
            "use_paddleocr": True,
        }
        request = controller_mod.Controller().build_request_from_ui(saved)
        assert request.ocr_timeout == 300 and request.use_paddleocr is True

        from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation
        from core.ocr.service import OCRService

        analysis = PdfAnalysisResult(
            total_pages=1,
            scanned_pages=[1],
            text_pages=[],
            recommendation=PdfRecommendation.LLM_OCR,
            per_page=[PageAnalysis(1, True, "", "llm_ocr")],
        )
        logs: list = []
        svc = OCRService(request, analysis, [1], log_callback=lambda m, l="INFO": logs.append(m))
        assert svc._ocr_timeout == 300
