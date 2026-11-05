"""V0.7.0 (wizard rework ②, item 2a) — the StageBar pins.

The stage-chip header (V1): a NEW reusable widget
(``ui_qt/components/stage_bar.py``) replaces the 42px dot strip
(``wizard_view.py:174-207`` — the ``●`` + 10px-label rows + ``━``
separators). The 10 steps group into 5 named stages (SOURCE · OUTPUTS ·
MODELS · TUNING · REVIEW); presentation only — every step keeps its
identity (plan D1).

Pin layers (the house pattern, cf. test_v0686_wizard_hotfix.py):
- Source pins run Qt-less (wizard_view consumes StageBar; the dot strip
  is gone).
- The offscreen layer renders the real widget and sweeps the state
  transitions (done/current/future across all 10 steps).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STAGE_BAR = _project_root / "ui_qt" / "components" / "stage_bar.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Source pins (Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


class TestStageBarSourcePins:
    """The widget module exists and the wizard consumes it."""

    def test_stage_bar_module_exists(self):
        assert _STAGE_BAR.exists(), "ui_qt/components/stage_bar.py must exist"

    def test_wizard_consumes_stage_bar(self):
        src = _src(_WIZARD)
        assert "from ui_qt.components.stage_bar import StageBar, StageSpec" in src
        assert "self.stage_bar = StageBar(" in src, "the wizard must build a StageBar"
        assert "self.stage_bar.set_current_step(self._current_step)" in src, (
            "_update_step must drive the StageBar"
        )

    def test_dot_strip_is_gone(self):
        """The old 42px dot strip (● labels + ━ separators) is deleted."""
        src = _src(_WIZARD)
        for gone in ("_step_dots", "_step_labels", "_STEP_LABELS", '"━"', '"●"'):
            assert gone not in src, f"dot-strip leftover {gone!r} still in wizard_view.py"

    def test_five_named_stages(self):
        src = _src(_WIZARD)
        for name in ("Source", "Outputs", "Models", "Tuning", "Review"):
            assert f'name="{name}"' in src, f"stage {name!r} missing from _WIZARD_STAGES"

    def test_stage_bar_token_driven(self):
        """No raw hex colours in the StageBar — palette tokens only, so
        BOTH themes render correctly (the plan's V1 ask)."""
        src = _src(_STAGE_BAR)
        assert "theme_manager.palette" in src
        for token in ("p.accent", "p.accent_soft", "p.border", "p.text_muted"):
            assert token in src, f"palette token {token!r} unused in stage_bar.py"
        # No raw hex colour literals in the widget source (comments aside).
        import re

        body_hex = re.findall(r"#[0-9A-Fa-f]{6}\b", src)
        assert not body_hex, f"raw hex colours in stage_bar.py: {body_hex}"

    def test_compact_threshold_780(self):
        src = _src(_STAGE_BAR)
        assert "_COMPACT_WIDTH = 780" in src, "sub-captions must drop below 780px"


# ═══════════════════════════════════════════════════════════════════════════
# Offscreen layer (needs PySide6)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


def _wizard_stages():
    from ui_qt.components.stage_bar import StageSpec

    return [
        StageSpec(name="Source", steps=("pdf", "range", "ocr")),
        StageSpec(name="Outputs", steps=("outputs",)),
        StageSpec(name="Models", steps=("models", "translation")),
        StageSpec(name="Tuning", steps=("adv", "fine")),
        StageSpec(name="Review", steps=("review", "logs")),
    ]


# The stage→step layout of the real wizard (indices are global, 0-based):
#   SOURCE 0,1,2 · OUTPUTS 3 · MODELS 4,5 · TUNING 6,7 · REVIEW 8,9
_EXPECTED_LAYOUT = [(0, 3), (3, 1), (4, 2), (6, 2), (8, 2)]


class TestStageBarOffscreen:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_build_and_render(self, app, tmp_path):
        from ui_qt.components.stage_bar import StageBar

        bar = StageBar(_wizard_stages())
        bar.resize(740, bar.sizeHint().height())
        bar.show()
        assert bar.stage_count == 5
        assert bar.step_count == 10
        grab = bar.grab()
        assert not grab.isNull()
        out = tmp_path / "stage_bar.png"
        assert grab.save(str(out)) and out.stat().st_size > 0
        bar.hide()
        bar.deleteLater()

    def test_state_transition_sweep(self, app):
        """Every step index produces the exact done/current/future map."""
        from ui_qt.components.stage_bar import StageBar

        bar = StageBar(_wizard_stages())
        for current in range(10):
            bar.set_current_step(current)
            pos = 0
            for stage_i, (_, n_steps) in enumerate(_EXPECTED_LAYOUT):
                for step_i in range(n_steps):
                    state = bar.segment_state(stage_i, step_i)
                    if pos < current:
                        assert state == "done", (current, stage_i, step_i)
                    elif pos == current:
                        assert state == "current", (current, stage_i, step_i)
                    else:
                        assert state == "future", (current, stage_i, step_i)
                    pos += 1
        # Past-the-end (a finished wizard) — everything done, nothing current.
        bar.set_current_step(10)
        assert all(
            bar.segment_state(s, i) == "done"
            for s, (_, n) in enumerate(_EXPECTED_LAYOUT)
            for i in range(n)
        )
        bar.deleteLater()

    def test_compact_below_780(self, app):
        """Below 780px width the sub-captions drop (the compact form)."""
        from ui_qt.components.stage_bar import StageBar

        bar = StageBar(_wizard_stages())
        bar.resize(820, bar.sizeHint().height())
        bar.show()
        assert not bar.is_compact(), "820px is the roomy form"
        bar.resize(740, bar.sizeHint().height())
        assert bar.is_compact(), "740px must switch to the compact form"
        bar.hide()
        bar.deleteLater()

    def test_real_wizard_builds_the_bar(self, app, tmp_path, monkeypatch):
        """The REAL WizardView (stub controller, the V0.6.86 pattern) builds
        a StageBar and drives it through _update_step."""
        import tempfile

        monkeypatch.setenv("HOME", tempfile.mkdtemp(prefix="elixir-v0700-home-"))

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

        from ui_qt.views.wizard_view import WizardView

        view = WizardView(_StubController())
        try:
            assert view.stage_bar.step_count == 10
            assert view.stage_bar.segment_state(0, 0) == "current"
            # Drive the bar directly (no _go_next: an invalid step 1 pops a
            # modal warning, which blocks forever offscreen).
            view._current_step = 4
            view._update_step()
            assert view.stage_bar.segment_state(0, 2) == "done"
            assert view.stage_bar.segment_state(1, 0) == "done"
            assert view.stage_bar.segment_state(2, 0) == "current"
            assert view.stage_bar.segment_state(4, 0) == "future"
            grab = view.grab()
            assert not grab.isNull()
        finally:
            view.hide()
            view.deleteLater()
