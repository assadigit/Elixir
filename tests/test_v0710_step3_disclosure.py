"""V0.7.1 (wizard rework ③, item 3d) — Step 3's auto-first rework pins.

The five flat checkboxes collapse into ONE primary choice ("Automatic —
recommended", the audit §W5 honest copy) + a folded advanced disclosure
("Manual control" opens it). The disclosure is MODE-AWARE: Step 1 owns
the reading-mode axis (``ocr_mode`` — landed V0.7.0); this step never
fights it:

- auto    → the full per-page cascade controls (vision pass, figure/
            table extraction, PaddleOCR fallback, timeout);
- digital → no page-OCR controls (text layer only; extraction + timeout
            stay);
- scanned → the engine set is locked by D2 — the disclosure shows the
            set as INFORMATION (the engine set line), not toggles that
            would lie; timeout stays.

Choosing "Automatic" saves the plan's honest defaults (vision on,
Paddle off — figure/table follow Step 1's cards); "Manual control"
saves exactly what the visible controls say. A control the mode makes
meaningless is never written over (a no-op, not a lie).

B3's UI half (the honest 120/180/300 band) is pinned here together
with its wiring pins in tests/test_v0710_ocr_controls_wiring.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP3 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step3_ocr.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source pins (Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


class TestStep3SourcePins:
    def test_primary_choice_exists(self):
        src = _src(_STEP3)
        assert 'QRadioButton("Automatic — recommended")' in src
        assert 'QRadioButton("Manual control")' in src
        assert "def _on_mode_radio(self" in src
        assert "self.disclosure.setVisible(self.manual_rb.isChecked())" in src

    def test_honest_auto_caption(self):
        """The audit §W5 honest-auto copy — identical to Step 1's Auto
        card so the two surfaces never disagree."""
        src = _src(_STEP3)
        assert (
            '"I scan every page and OCR only the ones that need it, '
            'with the best available engine."' in src
        )

    def test_mode_awareness_exists(self):
        src = _src(_STEP3)
        assert "def _refresh_mode_dependents(self)" in src
        assert 'self.vision_cb.setVisible(mode == "auto")' in src
        assert 'self.paddleocr_cb.setVisible(mode == "auto")' in src
        assert 'self.figures_cb.setVisible(mode in ("auto", "digital"))' in src
        assert "def showEvent(self, event)" in src, "refresh on every show"

    def test_engine_set_lines(self):
        src = _src(_STEP3)
        assert "Engine set (locked): your vision model" in src, "the scanned-mode D2 set"
        assert "Tesseract, PaddleOCR and the local-VLM fallback are" in src
        assert "No page OCR — the PDF's own text layer is read." in src, (
            "the digital-mode honest line"
        )
        assert "engine that succeeds wins." in src, "the auto-mode cascade"

    def test_timeout_items_are_the_honest_band(self):
        src = _src(_STEP3)
        assert 'self.timeout_combo.addItems(["120", "180", "300"])' in src

    def test_save_semantics_mode_aware(self):
        src = _src(_STEP3)
        # Automatic = the plan's honest defaults.
        assert "self.state.use_llm_ocr = True" in src
        assert "self.state.use_paddleocr = False" in src
        # Manual saves the visible controls; the no-op controls are
        # never written over.
        assert 'if mode == "auto":' in src
        assert "D2 forces both regardless" in src

    def test_no_five_flat_checkboxes(self):
        """The old surface (five always-visible checkboxes) is gone."""
        src = _src(_STEP3)
        assert 'QCheckBox("Use LLM OCR for scanned pages' not in src
        assert 'QCheckBox("Force OCR on every page' not in src
        assert "force_ocr_cb" not in src

    def test_ampersand_label_is_escaped(self):
        """'Figure & table' must use Qt's '&&' escape — a bare '&' becomes
        a mnemonic and the ampersand vanishes from the render (caught by
        the VLM pass on the first render of this step)."""
        src = _src(_STEP3)
        assert 'QCheckBox("Figure && table text extraction' in src


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


class _StubController:
    def __init__(self):
        self._settings: dict = {}

    def get_setting(self, path, default=None):
        return self._settings.get(path, default)

    def update_setting(self, path, value):
        self._settings[path] = value


class TestStep3Offscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _build(self, ocr_mode: str = "auto"):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step3_ocr import Step3Ocr

        state = WizardState()
        state.ocr_mode = ocr_mode
        return Step3Ocr(_StubController(), state), state

    def test_default_automatic_disclosure_hidden(self, app):
        step, _ = self._build()
        try:
            assert step.auto_rb.isChecked()
            assert not step.disclosure.isVisibleTo(step)
        finally:
            step.hide()
            step.deleteLater()

    def test_manual_opens_disclosure(self, app):
        step, _ = self._build()
        try:
            step.manual_rb.setChecked(True)
            assert step.disclosure.isVisibleTo(step)
            step.auto_rb.setChecked(True)
            assert not step.disclosure.isVisibleTo(step)
        finally:
            step.hide()
            step.deleteLater()

    def test_digital_mode_hides_page_ocr_controls(self, app):
        step, state = self._build("digital")
        try:
            step.manual_rb.setChecked(True)
            step._refresh_mode_dependents()
            assert not step.vision_cb.isVisibleTo(step.disclosure)
            assert not step.paddleocr_cb.isVisibleTo(step.disclosure)
            assert step.figures_cb.isVisibleTo(step.disclosure)
            assert step.tables_cb.isVisibleTo(step.disclosure)
            assert step.timeout_combo.isVisibleTo(step.disclosure)
            assert "text layer" in step.engineset_lbl.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_scanned_mode_shows_engine_set_not_toggles(self, app):
        """Scanned-mode runs show the engine set, not the Paddle toggle
        (D2 excludes it — a toggle there would lie)."""
        step, state = self._build("scanned")
        try:
            step.manual_rb.setChecked(True)
            step._refresh_mode_dependents()
            assert not step.paddleocr_cb.isVisibleTo(step.disclosure)
            assert not step.vision_cb.isVisibleTo(step.disclosure)
            assert not step.figures_cb.isVisibleTo(step.disclosure)
            assert "locked" in step.engineset_lbl.text()
            assert "excluded" in step.engineset_lbl.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_save_manual_writes_visible_controls(self, app):
        step, state = self._build("auto")
        try:
            step.manual_rb.setChecked(True)
            step.vision_cb.setChecked(False)
            step.paddleocr_cb.setChecked(True)
            step.figures_cb.setChecked(False)
            step.tables_cb.setChecked(False)
            step.timeout_combo.setCurrentText("300")
            step.save_to_state()
            assert state.use_llm_ocr is False
            assert state.use_paddleocr is True
            assert state.extract_figure_text is False
            assert state.extract_tables is False
            assert state.ocr_timeout == 300
        finally:
            step.hide()
            step.deleteLater()

    def test_save_automatic_applies_honest_defaults(self, app):
        step, state = self._build("auto")
        try:
            step.manual_rb.setChecked(True)
            step.paddleocr_cb.setChecked(True)
            step.auto_rb.setChecked(True)  # back to Automatic
            step.save_to_state()
            assert state.use_llm_ocr is True
            assert state.use_paddleocr is False
        finally:
            step.hide()
            step.deleteLater()

    def test_save_scanned_manual_never_writes_noops(self, app):
        step, state = self._build("scanned")
        state.use_llm_ocr = False  # what the user last had
        state.extract_figure_text = False  # Step 1's card set this
        try:
            step.manual_rb.setChecked(True)
            step.save_to_state()
            assert state.use_llm_ocr is False, "never written over in scanned"
            assert state.extract_figure_text is False
        finally:
            step.hide()
            step.deleteLater()

    def test_fits_its_viewport(self, app):
        step, _ = self._build()
        try:
            step.resize(740, 540)
            hint = step.minimumSizeHint() if hasattr(step, "minimumSizeHint") else None
            assert hint is None or hint.height() <= 540, (
                f"Step 3 needs {hint.height()}px — overflows the 540px viewport"
            )
        finally:
            step.hide()
            step.deleteLater()

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size):
        """The phase-gate render: Step 3 (manual disclosure open, auto
        mode — the richest state) at 740×540 and 820×600, both themes."""
        from ui_qt.theme import theme_manager
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step3_ocr import Step3Ocr

        theme_manager.apply(app, theme)
        state = WizardState()
        step = Step3Ocr(_StubController(), state)
        try:
            step.manual_rb.setChecked(True)  # richest visible state
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step3_{theme}_{size[0]}x{size[1]}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default
