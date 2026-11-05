"""V0.7.0 (wizard rework ②, item 2b) — the wizard chrome restyle pins.

The V2 shell: every step gets the numbered ``StepHeader`` (badge + title
+ plain-word caption — one visual grammar across all 10); the nav bar is
Cancel (ghost) left, ‹ Back (secondary) + Next › (primary) right, 40px+
targets; the steps share the shell's 20px frame margins. The shell lands
NOW so phases ③-⑦ build inside it; per-step polish lands with each
phase's functional rework (Round-2 plan §2 Phase ②).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_STEPS_DIR = _project_root / "ui_qt" / "views" / "wizard_steps"

_STEP_MODULES = [
    "step1_pdf",
    "step2_range",
    "step3_ocr",
    "step4_outputs",
    "step5_models",
    "step6_translation",
    "step7_advanced",
    "step7b_fine_tune",
    "step8_review",
    "step9_logs",
]


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source pins (Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


class TestStepHeaderGrammarPins:
    def test_every_step_declares_step_header(self):
        for mod in _STEP_MODULES:
            src = _src(_STEPS_DIR / f"{mod}.py")
            assert "STEP_HEADER = (" in src, f"{mod} must declare STEP_HEADER"

    def test_step_headers_numbered_1_to_10(self):
        import re

        numbers = []
        for mod in _STEP_MODULES:
            m = re.search(r"STEP_HEADER = \(\s*(\d+),", _src(_STEPS_DIR / f"{mod}.py"))
            assert m, f"{mod}: unparseable STEP_HEADER"
            numbers.append(int(m.group(1)))
        assert numbers == list(range(1, 11)), (
            f"steps must number 1..10 in wizard order, got {numbers}"
        )

    def test_no_step_builds_its_own_h2_title(self):
        """The old per-step H2 title labels are gone — the base's
        StepHeader owns the title grammar now."""
        for mod in _STEP_MODULES:
            src = _src(_STEPS_DIR / f"{mod}.py")
            assert 'setObjectName("H2")' not in src, f"{mod} still builds its own H2 title label"

    def test_base_installs_header_and_shell_margins(self):
        src = _src(_STEPS_DIR / "shared.py")
        assert "STEP_HEADER: tuple[int, str, str] | None = None" in src
        assert "_install_step_header" in src
        assert "_apply_shell_margins" in src
        assert "SPACE.xxl" in src, "the shell's 20px frame margins"


class TestNavBarPins:
    def test_nav_grammar(self):
        src = _src(_WIZARD)
        for needle in (
            'QPushButton("Cancel")',
            'QPushButton("‹ Back")',
            'QPushButton("Next ›")',
            'setObjectName("Secondary")',
            'setObjectName("Primary")',
            "setMinimumHeight(40)",
        ):
            assert needle in src, f"nav pin {needle!r} missing"

    def test_start_button_no_control_emoji(self):
        """D9 (control labels carry no emoji): the review-step Start button
        dropped its 🚀 prefix with the shell restyle. Log lines keep
        their emoji (D9's explicit carve-out), so the pin scopes to
        setText calls — the control-label surface."""
        src = _src(_WIZARD)
        settext_lines = [ln for ln in src.splitlines() if ".setText(" in ln]
        for ln in settext_lines:
            assert "🚀" not in ln, f"control label still carries an emoji: {ln.strip()}"
        assert any('"Start ›"' in ln for ln in settext_lines), (
            "the review-step Start button must exist with the shell grammar"
        )


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

    def get_secret(self, path, default=""):
        return default

    def set_secret(self, path, value):
        pass

    def list_ollama_models(self):
        return []


class TestChromeOffscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_real_wizard_chrome(self, app, tmp_path, monkeypatch):
        """The REAL wizard: 10 numbered StepHeaders, 40px+ nav targets,
        the shell margins, and a non-null render."""
        import tempfile

        monkeypatch.setenv("HOME", tempfile.mkdtemp(prefix="elixir-v0700c-home-"))
        from ui_qt.components.step_header import StepHeader
        from ui_qt.views.wizard_view import WizardView

        view = WizardView(_StubController())
        try:
            headers = []
            for step in view.steps:
                headers.extend(step.findChildren(StepHeader))
            assert len(headers) == 10, f"10 StepHeaders expected, got {len(headers)}"
            nums = [int(h.badge_label.text()) for h in headers]
            assert nums == list(range(1, 11))
            # 40px+ click targets on the nav bar (plan item 2b).
            for btn in (view.cancel_wizard_btn, view.back_btn, view.next_btn):
                assert btn.minimumHeight() >= 40, f"{btn.text()}: target < 40px"
            assert view.back_btn.objectName() == "Secondary"
            assert view.next_btn.objectName() == "Primary"
            # The shell margins (20px sides).
            m = view.step1.layout().contentsMargins()
            assert (m.left(), m.right()) == (20, 20)
            view.show()
            grab = view.grab()
            assert not grab.isNull()
            out = tmp_path / "v0700_chrome.png"
            assert grab.save(str(out)) and out.stat().st_size > 0
        finally:
            view.hide()
            view.deleteLater()
