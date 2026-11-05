"""V0.7.1 (wizard rework ③, items 3a+3b) — Step 2's promotion pins.

3a — the page range card: 15px field labels, 32px spinboxes, a LIVE
feedback line ("Pages 12-340 — 329 of 397 pages (~83%) will be
processed."), tooltips; "Process all pages" stays the default and the
range fields enable on uncheck (unchanged mechanics).

3b — the TOC detection promotion: the old "🔍 Detect chapters from TOC"
secondary button becomes a prominent card-level action — professional
icon (D9: no emoji on controls), the title "Detect chapters from the
table of contents", the honest caption "Most accurate — reads the
book's own outline". The dialog/checkbox mechanics are unchanged (the
backend is solid, audit §W4).

Grabs: 740×540 and 820×600, BOTH themes (the phase-gate render, the
test_v0700_step1_three_cards.py pattern).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP2 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step2_range.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source pins (Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


class TestStep2SourcePins:
    def test_page_range_card_controls(self):
        src = _src(_STEP2)
        # 15px field labels + 32px spinboxes (the audit's "small and
        # quiet" complaint).
        assert "font-size: 15px" in src
        assert "spin.setFixedHeight(32)" in src
        assert 'spin.setStyleSheet("font-size: 14px;")' in src

    def test_live_feedback_line_exists(self):
        src = _src(_STEP2)
        assert "def _refresh_feedback(self)" in src
        # The feedback refreshes on every spin change, not just on toggle.
        assert "valueChanged.connect(lambda *_: self._refresh_feedback())" in src

    def test_feedback_states_wording(self):
        src = _src(_STEP2)
        assert "'from' must be ≤ 'to'." in src, "the invalid-range state"
        assert "will be processed." in src, "the range state"
        assert "chapter(s) selected from the table of contents." in src, (
            "the TOC-selection state (the honest count — never a guess)"
        )

    def test_total_pages_is_best_effort_never_guessed(self):
        src = _src(_STEP2)
        assert "def _read_total_pages(self)" in src
        assert "except Exception:" in src
        assert "self._total_pages = None" in src

    def test_toc_action_promoted(self):
        src = _src(_STEP2)
        assert 'self.chapter_btn.setObjectName("Primary")' in src, (
            "the promoted action is a Primary button (was Secondary)"
        )
        assert "Detect chapters from the table of contents" in src
        assert "Most accurate — reads the book's own outline." in src
        assert 'pixmap("list-checks"' in src, "the professional icon (D9)"

    def test_no_emoji_on_controls(self):
        src = _src(_STEP2)
        assert "🔍 Detect" not in src, "D9: the emoji is gone from the control"

    def test_dialog_mechanics_unchanged(self):
        """The V10.1.1 button-always-enabled + auto-check contract, and
        the custom-range-disables-chapters rule, survive the promotion."""
        src = _src(_STEP2)
        assert "ChapterSelectorDialog(self, output_dir=candidate_out)" in src
        assert "self.chapter_btn.setEnabled(True)" in src
        assert "self.select_chapters_cb.setChecked(False)" in src


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


class TestStep2Offscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _build(self):
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step2_range import Step2Range

        state = WizardState()
        return Step2Range(_StubController(), state), state

    def test_default_state_all_pages(self, app):
        step, _ = self._build()
        try:
            assert step.all_pages_cb.isChecked()
            assert not step.start_spin.isEnabled()
            assert not step.end_spin.isEnabled()
            assert step.blocks_auto_cb.isEnabled()
            assert "All pages will be processed." in step.feedback_lbl.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_uncheck_enables_range_and_disables_chapters(self, app):
        step, _ = self._build()
        try:
            step.all_pages_cb.setChecked(False)
            assert step.start_spin.isEnabled() and step.end_spin.isEnabled()
            assert not step.select_chapters_cb.isEnabled()
            assert not step.chapter_btn.isEnabled()
        finally:
            step.hide()
            step.deleteLater()

    def test_feedback_is_live_on_spin_changes(self, app):
        step, _ = self._build()
        try:
            step.all_pages_cb.setChecked(False)
            step.start_spin.setValue(12)
            step.end_spin.setValue(340)
            assert step.feedback_lbl.text() == "Pages 12-340 — 329 pages will be processed."
            step.start_spin.setValue(340)
            step.end_spin.setValue(12)
            assert "'from' must be ≤ 'to'." in step.feedback_lbl.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_chapter_selection_reflects_in_feedback(self, app):
        step, _ = self._build()
        try:
            step._selected_chapters = ["A", "B", "C"]
            step._refresh_feedback()
            assert "3 chapter(s) selected" in step.feedback_lbl.text()
            step._selected_chapters = None
            step._on_chapter_toggled(False)
            assert "chapter" not in step.feedback_lbl.text()
        finally:
            step.hide()
            step.deleteLater()

    def test_fits_its_viewport(self, app):
        step, _ = self._build()
        try:
            step.resize(740, 540)
            hint = step.minimumSizeHint() if hasattr(step, "minimumSizeHint") else None
            assert hint is None or hint.height() <= 540, (
                f"Step 2 needs {hint.height()}px — overflows the 540px viewport"
            )
        finally:
            step.hide()
            step.deleteLater()

    @pytest.mark.parametrize("theme", ["light", "dark"])
    @pytest.mark.parametrize("size", [(740, 540), (820, 600)])
    def test_grabs_both_themes_both_sizes(self, app, tmp_path, theme, size):
        """The phase-gate render: Step 2 at 740×540 and 820×600, BOTH
        themes (the plan's per-phase visual-regression gate)."""
        from ui_qt.theme import theme_manager
        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step2_range import Step2Range

        theme_manager.apply(app, theme)
        state = WizardState()
        state.page_range_start = None
        step = Step2Range(_StubController(), state)
        try:
            step.resize(*size)
            step.show()
            app.processEvents()
            grab = step.grab()
            assert not grab.isNull()
            out = tmp_path / f"step2_{theme}_{size[0]}x{size[1]}.png"
            assert grab.save(str(out)), "the render artifact must save"
            assert out.stat().st_size > 500, "a real render is never tiny"
        finally:
            step.hide()
            step.deleteLater()
            theme_manager.apply(app, "light")  # restore the default
