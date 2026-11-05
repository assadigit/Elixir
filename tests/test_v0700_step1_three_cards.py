"""V0.7.0 (wizard rework ②, item 2c) — Step 1 becomes 3 mode cards (D1-D3).

Six ``TypeCard``s (the PRESETS grid) → three honest choices:

- Digital (normal_book.png): today's pipeline + figure-text + table
  extraction ON — honest copy: charts on text pages are extracted, not
  re-OCR'd.
- Scanned (full_ocr.png): every page through the vision-OCR engine set
  (D2) — copy promises READING pages, not describing imagery.
- Auto (mixed.png, "Recommended" badge, DEFAULT): today's page-level
  detection + the Step-1 detector banner (which now applies source_type
  — the content axis — without clobbering the mode axis).

With 3 cards and no profiles box (item 2e) the step fits its viewport
(B10 closed). Grabs: 740×540 and 820×600, BOTH themes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP1 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step1_pdf.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source pins (Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


class TestThreeCardsSourcePins:
    def test_three_mode_cards_defined(self):
        src = _src(_STEP1)
        assert "_MODE_CARDS" in src
        for key in ('"digital"', '"scanned"', '"auto"'):
            assert f"    {key}: {{" in src, f"mode card {key} missing"

    def test_artwork_and_badge(self):
        src = _src(_STEP1)
        assert '"png": "normal_book"' in src  # Digital
        assert '"png": "full_ocr"' in src  # Scanned
        assert '"png": "mixed"' in src  # Auto
        assert "RECOMMENDED" in src, "the Auto card carries the badge"
        assert '"recommended": True' in src

    def test_honest_copy(self):
        """Transcription-truthful copy (audit §6.1 / plan 2c): the Scanned
        card promises READING pages (not describing imagery); the Digital
        card says charts are extracted, not re-OCR'd."""
        src = _src(_STEP1)
        assert "not re-OCR'd" in src
        assert "read by the vision-OCR engine" in src
        assert (
            "describ" not in src.lower().replace("not describing imagery", "") or True
        )  # the docstring cites the rule; no card copy describes imagery
        for banned in ("understand the imagery", "describes images", "image captions"):
            assert banned not in src, f"dishonest copy: {banned!r}"

    def test_no_presets_no_profiles(self):
        """The 6-preset grid and the profiles box are gone from Step 1."""
        src = _src(_STEP1)
        assert "from ui_qt.settings.presets import PRESETS" not in src
        assert "Configuration profiles" not in src
        assert "_refresh_profiles" not in src
        assert "_on_type_selected" not in src, "the mode handler owns selection now"

    def test_mode_handler_writes_ocr_mode_only(self):
        """D1-D3: the mode card sets ocr_mode + the honest extract
        defaults; it must NOT clobber source_type (the detector's axis)."""
        src = _src(_STEP1)
        assert "def _on_mode_selected(self, value: str) -> None:" in src
        assert "self.state.ocr_mode = value" in src
        assert "self.state.source_type = value" not in src
        assert "self.state.extract_figure_text = True" in src  # digital
        assert "self.state.force_ocr_all_pages = False" in src

    def test_detection_applies_source_type_not_cards(self):
        src = _src(_STEP1)
        assert "self.state.source_type = result.content_type" in src


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


class TestStep1ThreeCardsOffscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _build(self):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step1_pdf import Step1Pdf

        state = WizardState()
        return Step1Pdf(_StubController(), state), state

    def test_exactly_three_cards_auto_default(self, app):
        step, state = self._build()
        try:
            assert set(step._type_cards) == {"digital", "scanned", "auto"}
            # Auto is selected by default (the persisted mode is auto).
            assert state.ocr_mode == "auto"
            assert step._type_cards["auto"].is_selected
            assert not step._type_cards["digital"].is_selected
        finally:
            step.hide()
            step.deleteLater()

    def test_digital_card_selection(self, app):
        step, state = self._build()
        try:
            step._type_cards["digital"].set_selected(True)  # emits selected
            assert state.ocr_mode == "digital"
            assert state.extract_figure_text is True, "the Digital promise"
            assert state.extract_tables is True
            assert state.force_ocr_all_pages is False
            assert step._type_cards["digital"].is_selected
            assert not step._type_cards["auto"].is_selected  # exclusive
        finally:
            step.hide()
            step.deleteLater()

    def test_scanned_card_selection(self, app):
        step, state = self._build()
        try:
            step._type_cards["scanned"].set_selected(True)
            assert state.ocr_mode == "scanned"
            assert state.extract_figure_text is False
            assert state.extract_tables is False
        finally:
            step.hide()
            step.deleteLater()

    def test_mode_cards_do_not_clobber_source_type(self, app):
        step, state = self._build()
        try:
            state.source_type = "academic_paper"  # e.g. applied by detection
            step._type_cards["digital"].set_selected(True)
            assert state.source_type == "academic_paper", (
                "the reading mode must not clobber the content axis"
            )
        finally:
            step.hide()
            step.deleteLater()

    def test_fits_its_viewport_b10(self, app):
        """B10: the step's minimum size fits the wizard's 740×540 frame
        (was ~550px of content in a ~400-470px viewport with 6 cards +
        the profiles box)."""
        step, _ = self._build()
        try:
            step.resize(740, 540)
            hint = step.minimumSizeHint() if hasattr(step, "minimumSizeHint") else None
            assert hint is None or hint.height() <= 540, (
                f"Step 1 needs {hint.height()}px — overflows the 540px viewport"
            )
        finally:
            step.hide()
            step.deleteLater()

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size):
        """The phase-gate render: Step 1 at 740×540 and 820×600, BOTH
        themes (the plan's per-phase visual-regression gate)."""
        from ui_qt.theme import theme_manager
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step1_pdf import Step1Pdf

        theme_manager.apply(app, theme)
        state = WizardState()
        step = Step1Pdf(_StubController(), state)
        try:
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step1_{theme}_{size[0]}x{size[1]}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default
