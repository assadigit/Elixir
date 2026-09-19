"""V18.20.3.14 — ConvertView legacy-CTA crash (user-reported, real run).

Reproduces the crash from the .3.13 Windows rig run (wizard-driven
conversion completing after the Process Wizard restored ConvertView's
controller callbacks on close)::

    File "...\\ui_qt\\views\\convert_view.py", line 655, in _on_complete
        self.convert_btn.setEnabled(True)
    AttributeError: 'NoneType' object has no attribute 'setEnabled'

Root cause: since V11.0.0 the Convert / Test Book buttons are removed
from the primary page and ``self.convert_btn`` / ``self.test_btn`` are
deliberately ``None`` ("kept so existing methods don't crash"), but four
touchers still called ``.setEnabled`` unguarded — including the live
``_on_complete`` bridge slot. Fixed by routing all four through
``ConvertView._set_cta_enabled`` (None-guarded).

V18.20.4.1 update (P0 / W-b13): the three DEAD touchers
(``_start_conversion`` / ``_start_diagnostic`` / ``_finalize_diagnostic``)
were deleted outright with the V11.0.0 legacy block — the crash class is
closed structurally. The pins below now assert the STRONGER contract:
the only surviving toucher is ``_on_complete``, it routes through the
helper, and the dead methods may not come back.

Two layers, per the house UI-test pattern (see test_v182038_audit_fixes):
- Policy/source-pin tests (always run, headless-safe).
- Behavioral widget tests (offscreen QApplication; skipped gracefully
  when PySide6 is unavailable — e.g. the headless rig).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_CONVERT_VIEW = _project_root / "ui_qt" / "views" / "convert_view.py"


# ── Policy / source-pin layer (headless-safe, always runs) ──────────────────


class TestLegacyCtaTouchersAreGuarded:
    """Every .setEnabled on the V11.0.0-removed buttons must be inside
    the None-guarded helper — no unguarded toucher may come back."""

    def _toucher_lines(self, src: str) -> dict[int, str]:
        out: dict[int, str] = {}
        for i, line in enumerate(src.splitlines(), start=1):
            s = line.strip()
            for attr in ("self.convert_btn", "self.test_btn"):
                if s.startswith("#"):
                    continue
                if f"{attr}.setEnabled" in s:
                    out[i] = s
        return out

    def _helper_span(self, src: str) -> tuple[int, int]:
        lines = src.splitlines()
        start = end = -1
        for i, line in enumerate(lines, start=1):
            if "def _set_cta_enabled" in line:
                start = i
            elif start != -1 and line.startswith("    def ") and i > start:
                end = i - 1
                break
        assert start != -1, "_set_cta_enabled helper missing"
        if end == -1:  # helper is the last method
            end = len(lines)
        return start, end

    def test_all_setenabled_calls_live_inside_the_guard(self):
        src = _CONVERT_VIEW.read_text(encoding="utf-8")
        lo, hi = self._helper_span(src)
        stray = {i: line for i, line in self._toucher_lines(src).items() if not (lo <= i <= hi)}
        assert not stray, (
            "Unguarded .setEnabled on the V11.0.0-removed CTA buttons "
            f"(must route through _set_cta_enabled): {stray}"
        )

    def test_the_only_surviving_toucher_routes_through_the_helper(self):
        """V18.20.4.1 (W-b13): the three dead legacy touchers are DELETED —
        ``_on_complete`` (the live bridge slot, the original crash site) is
        the only survivor and must route through the None-guarded helper."""
        src = _CONVERT_VIEW.read_text(encoding="utf-8")
        for site in (
            "def _start_conversion",
            "def _start_diagnostic",
            "def _finalize_diagnostic",
        ):
            assert src.find(site) == -1, (
                f"{site} was deleted in V18.20.4.1 (W-b13, the V11.0.0 legacy "
                "minefield) — it must not come back"
            )
        pos = src.find("def _on_complete")
        assert pos != -1, "_on_complete not found"
        body = src[pos : src.find("\n    def ", pos + 1)]
        assert "_set_cta_enabled(" in body, "_on_complete must call _set_cta_enabled (V18.20.3.14)"

    def test_helper_guards_both_buttons(self):
        src = _CONVERT_VIEW.read_text(encoding="utf-8")
        lo, hi = self._helper_span(src)
        body = "\n".join(src.splitlines()[lo - 1 : hi])
        for attr in ("self.convert_btn", "self.test_btn"):
            assert f"if {attr} is not None:" in body, f"{attr} not None-guarded in _set_cta_enabled"

    def test_v11000_none_invariant_still_documented(self):
        """The buttons are still deliberately None on this page — the fix
        must not silently resurrect removed UI."""
        src = _CONVERT_VIEW.read_text(encoding="utf-8")
        assert "self.convert_btn = None" in src
        assert "self.test_btn = None" in src


# ── Behavioral layer (offscreen Qt; skips without PySide6) ──────────────────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestConvertViewCompletionBehaviour:
    """Widget-level tests (offscreen). The failed-result path is used for
    _on_complete so the modal success QMessageBox never blocks the test —
    the crash site (the CTA re-enable) is executed BEFORE the branch."""

    @pytest.fixture(scope="class")
    def app(self):
        from PySide6.QtWidgets import QApplication

        inst = QApplication.instance() or QApplication([])
        yield inst

    @pytest.fixture
    def view(self, app):
        from controller import Controller
        from ui_qt.views.convert_view import ConvertView

        v = ConvertView(Controller())
        yield v
        v.deleteLater()

    def test_v11000_buttons_are_none_on_this_page(self, view):
        assert view.convert_btn is None
        assert view.test_btn is None

    def test_on_complete_with_none_ctas_no_crash(self, view):
        """The exact user-reported repro: _on_complete must not raise
        AttributeError when the legacy buttons are None."""
        from core.models import ConversionResult

        view.is_converting = True
        result = ConversionResult(success=False, error_msg="rig repro")
        view._on_complete(result)  # must not raise
        assert view.is_converting is False

    def test_on_complete_reenables_real_buttons(self, view):
        """Guard must not break the buttons-present path (older UIs /
        subclasses that still build the CTAs)."""
        from PySide6.QtWidgets import QPushButton

        from core.models import ConversionResult

        view.convert_btn = QPushButton("Convert")
        view.test_btn = QPushButton("Test")
        view.convert_btn.setEnabled(False)
        view.test_btn.setEnabled(False)
        view._on_complete(ConversionResult(success=False, error_msg="x"))
        assert view.convert_btn.isEnabled()
        assert view.test_btn.isEnabled()

    def test_set_cta_enabled_toggles_real_buttons(self, view):
        from PySide6.QtWidgets import QPushButton

        view.convert_btn = QPushButton("Convert")
        view.test_btn = QPushButton("Test")
        view._set_cta_enabled(False)
        assert not view.convert_btn.isEnabled()
        assert not view.test_btn.isEnabled()
        view._set_cta_enabled(True)
        assert view.convert_btn.isEnabled()
        assert view.test_btn.isEnabled()
