"""V0.6.3 — the modal button clipping, defect-driven.

USER REPORT (verbatim, abridged):

  "Make sure all modals have enough space, for example in this example
   Open file location is truncated."

ROOT CAUSE (reproduced offscreen with the shipped QSS, light + dark):
the Summarization success modal ("Σ Summarization Complete") — short
message text + three QSS-padded buttons — renders 355px wide, 19px
NARROWER than its own sizeHint (374px): "📂 Open File Location" gets
132px where its sizeHint needs 142px (the user-visible clipped tail)
and "🔄 Try Another" gets 95px where it needs 104px (the missing final
"r"). QMessageBox's internal post-show sizing can settle below
sizeHint when the text label is narrow; QPushButton then CLIPS its
label.

THE FIX: per-button minimum widths (each raised to the button's own
sizeHint width) propagate up the layout chain — button minimum →
QDialogButtonBox minimum → the QMessageBox layout's totalMinimumSize →
dialog geometry — so the dialog can never render narrower than its
button row. Applied globally via a QApplication event filter on
QEvent.Show (installed once in ui_qt.app.run) + belt-and-braces at the
evidenced site (shared._show_success_modal).

The empirical REJECTION of the dialog-level setMinimumWidth floor is
pinned below (test_dialog_level_floor_is_ineffective): layout
activation during show() overwrites the widget minimum with the
layout's totalMinimumSize, silently undoing the floor — the reason the
fix works at the button level, not the dialog level.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent


# ── Qt availability gate (the tests construct QMessageBox widgets) ─────────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def qss_theme():
    """Apply the shipped QSS around a test; restore the previous sheet after.

    The stylesheet lives on the shared QApplication (session-scoped), so
    without the restore every LATER test in the session would inherit the
    elixir theme metrics (order-dependence — the exact class conftest's
    tikgate exists to prevent).
    """
    app = _app()
    previous = app.styleSheet()
    from ui_qt.theme import PALETTES, _qss

    app.setStyleSheet(_qss(PALETTES["light"]))
    try:
        yield app
    finally:
        app.setStyleSheet(previous)


@pytest.fixture()
def no_global_filter():
    """Temporarily remove the global ModalButtonFitFilter from the shared app.

    The raw-construction tests (the defect pin, the floor rejection)
    must observe QMessageBox's UNFIXED behavior — without this, running
    the filter tests first would auto-fit every box session-wide.
    Import-tolerant so the characterization tests also run on the
    PRE-FIX HEAD (no module → no filter installed → the raw behavior).
    """
    try:
        from ui_qt.components import modal_button_fit as mbf
    except ImportError:  # pre-fix HEAD — the module does not exist yet
        yield None
        return
    app = _app()
    installed = mbf._installed
    if installed is not None:
        app.removeEventFilter(installed)
    try:
        yield app
    finally:
        if installed is not None and mbf._installed is installed:
            app.installEventFilter(installed)


def _build_success_modal(parent=None):
    """The EXACT evidenced construction: shared._show_success_modal's box."""
    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox(parent)
    msg.setWindowTitle("Σ Summarization Complete")
    msg.setIcon(QMessageBox.Information)
    msg.setText("pasted > 1.md (5,644 chars)\n(detailed + analysis) = Format: Markdown (.md)")
    buttons = [
        msg.addButton("📂 Open File Location", QMessageBox.AcceptRole),
        msg.addButton("🔄 Try Another", QMessageBox.ActionRole),
        msg.addButton("✓ Close", QMessageBox.RejectRole),
    ]
    return msg, buttons


def _assert_buttons_unclipped(buttons):
    """Every button must render at (or above) its full sizeHint width."""
    for btn in buttons:
        hint = btn.sizeHint().width()
        assert btn.width() >= hint, (
            f"button {btn.text()!r} clipped: width {btn.width()} < sizeHint {hint}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# The defect pin — the raw construction clips (why the fix must exist)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6 not importable")
class TestDefectPin:
    def test_raw_success_modal_clips_its_buttons(self, qss_theme, no_global_filter):
        """The user's exact screenshot, reproduced: no fit → clipped labels.

        This is a CHARACTERIZATION of Qt's behavior (valid before AND after
        the fix — the fix lives in our code paths, not in Qt): the box with
        a short message + three padded buttons renders narrower than the
        button row, so at least one label clips. It is the reason
        fit_message_box_buttons / the filter must exist.
        """
        app = qss_theme
        msg, buttons = _build_success_modal()
        try:
            msg.resize(msg.sizeHint())
            msg.show()
            app.processEvents()
            clipped = [b for b in buttons if b.width() < b.sizeHint().width()]
            # The empirical defect: on this rig (QSS light) the Open button
            # renders 132px vs sizeHint 142px and Try 95px vs 104px. Guard
            # the class of defect, not the exact pixel numbers.
            assert clipped, "expected the raw unfitted construction to clip on this rig"
        finally:
            msg.hide()
            msg.deleteLater()
            app.processEvents()

    def test_dialog_level_floor_is_ineffective(self, qss_theme, no_global_filter):
        """The REJECTED approach, pinned: setMinimumWidth on the dialog does
        NOT survive QMessageBox's show — layout activation overwrites the
        widget minimum with the layout's totalMinimumSize, so the clip
        stays. This documents WHY the fix works at the button level."""
        app = qss_theme
        from PySide6.QtWidgets import QDialogButtonBox

        msg, buttons = _build_success_modal()
        try:
            lay = msg.layout()
            row_w = 0
            for i in range(lay.count()):
                item = lay.itemAt(i)
                w = item.widget() if item is not None else None
                if isinstance(w, QDialogButtonBox):
                    row_w = w.sizeHint().width()
                    break
            m = lay.contentsMargins()
            needed = row_w + m.left() + m.right()
            msg.setMinimumWidth(needed)
            msg.resize(msg.sizeHint())
            msg.show()
            app.processEvents()
            assert msg.width() < needed, (
                "the dialog-level floor unexpectedly survived show(); "
                "if so, the module docstring's rejection story is stale"
            )
        finally:
            msg.hide()
            msg.deleteLater()
            app.processEvents()


# ═══════════════════════════════════════════════════════════════════════════
# The fix — fit_message_box_buttons (the unit)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6 not importable")
class TestFitFunction:
    def test_fit_raises_minimums_to_sizehints(self, qss_theme, no_global_filter):
        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        msg, buttons = _build_success_modal()
        try:
            fit_message_box_buttons(msg)
            for btn in buttons:
                assert btn.minimumWidth() >= btn.sizeHint().width()
        finally:
            msg.deleteLater()
            qss_theme.processEvents()

    def test_fitted_modal_renders_full_width(self, qss_theme, no_global_filter):
        """THE fix behavior: apply the fit, show, no label clips."""
        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        app = qss_theme
        msg, buttons = _build_success_modal()
        try:
            fit_message_box_buttons(msg)
            msg.resize(msg.sizeHint())
            msg.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
        finally:
            msg.hide()
            msg.deleteLater()
            app.processEvents()

    def test_fit_is_idempotent(self, qss_theme, no_global_filter):
        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        msg, buttons = _build_success_modal()
        try:
            w1 = fit_message_box_buttons(msg)
            mins1 = [b.minimumWidth() for b in buttons]
            w2 = fit_message_box_buttons(msg)
            assert w1 == w2
            assert [b.minimumWidth() for b in buttons] == mins1
        finally:
            msg.deleteLater()
            qss_theme.processEvents()

    def test_fit_never_lowers_a_larger_existing_minimum(self, qss_theme):
        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        msg, buttons = _build_success_modal()
        try:
            buttons[0].setMinimumWidth(500)
            fit_message_box_buttons(msg)
            assert buttons[0].minimumWidth() == 500
        finally:
            msg.deleteLater()
            qss_theme.processEvents()

    def test_fit_noop_without_buttons(self, qss_theme):
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        msg = QMessageBox(None)
        try:
            assert fit_message_box_buttons(msg) == 0
        finally:
            msg.deleteLater()
            qss_theme.processEvents()


# ═══════════════════════════════════════════════════════════════════════════
# The fix — the other modal shapes + both themes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6 not importable")
class TestModalShapes:
    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_success_modal_both_themes(self, theme, no_global_filter):
        from ui_qt.components.modal_button_fit import fit_message_box_buttons
        from ui_qt.theme import PALETTES, _qss

        app = _app()
        previous = app.styleSheet()
        app.setStyleSheet(_qss(PALETTES[theme]))
        try:
            msg, buttons = _build_success_modal()
            fit_message_box_buttons(msg)
            msg.resize(msg.sizeHint())
            msg.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
            msg.hide()
            msg.deleteLater()
            app.processEvents()
        finally:
            app.setStyleSheet(previous)

    def test_vram_overbudget_shape(self, qss_theme, no_global_filter):
        """The wizard's box: long text + a 230px-class button label."""
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        app = qss_theme
        box = QMessageBox(None)
        try:
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("VRAM Overbudget — start anyway?")
            box.setText(
                "⚠️ VRAM Overbudget!\n\nPeak VRAM estimate: 18.4 GB\n"
                "Available VRAM: 8.0 GB\n\nThe model does NOT fit on the GPU."
            )
            buttons = [
                box.addButton("Proceed anyway (at my own risk)", QMessageBox.ButtonRole.AcceptRole),
                box.addButton("Abort", QMessageBox.ButtonRole.RejectRole),
            ]
            fit_message_box_buttons(box)
            box.resize(box.sizeHint())
            box.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
        finally:
            box.hide()
            box.deleteLater()
            app.processEvents()

    def test_podcast_complete_shape(self, qss_theme, no_global_filter):
        """The podcast box: HTML text + two buttons."""
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        app = qss_theme
        box = QMessageBox(None)
        try:
            box.setWindowTitle("✅ Podcast Complete")
            box.setIcon(QMessageBox.Information)
            box.setText("<h3>🎧 Podcast generated!</h3><p><b>Audio:</b> ep.wav</p>")
            buttons = [
                box.addButton("📂 Open Folder", QMessageBox.AcceptRole),
                box.addButton("✓ Close", QMessageBox.RejectRole),
            ]
            fit_message_box_buttons(box)
            box.resize(box.sizeHint())
            box.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
        finally:
            box.hide()
            box.deleteLater()
            app.processEvents()

    def test_standard_button_box_shape(self, qss_theme, no_global_filter):
        """The static-convenience shape: standard Save/Discard/Cancel buttons
        with a short text (the QMessageBox.question family)."""
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.components.modal_button_fit import fit_message_box_buttons

        app = qss_theme
        box = QMessageBox(None)
        try:
            box.setText("Continue?")
            buttons = [
                box.addButton(QMessageBox.StandardButton.Save),
                box.addButton(QMessageBox.StandardButton.Discard),
                box.addButton(QMessageBox.StandardButton.Cancel),
            ]
            fit_message_box_buttons(box)
            box.resize(box.sizeHint())
            box.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
        finally:
            box.hide()
            box.deleteLater()
            app.processEvents()


# ═══════════════════════════════════════════════════════════════════════════
# The global guarantee — the QApplication event filter
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6 not importable")
class TestGlobalFilter:
    def test_filter_fits_on_show_with_no_explicit_calls(self, qss_theme):
        """The 'ALL modals' guarantee: a RAW box (no fit call, no resize call)
        gets fitted purely by the filter's Show-event handling."""
        from ui_qt.components.modal_button_fit import install_modal_button_fit

        app = qss_theme
        install_modal_button_fit(app)
        msg, buttons = _build_success_modal()
        try:
            msg.show()
            app.processEvents()
            _assert_buttons_unclipped(buttons)
        finally:
            msg.hide()
            msg.deleteLater()
            app.processEvents()

    def test_install_is_idempotent(self, qss_theme):
        from ui_qt.components import modal_button_fit as mbf

        app = qss_theme
        f1 = mbf.install_modal_button_fit(app)
        f2 = mbf.install_modal_button_fit(app)
        assert f1 is f2, "install_modal_button_fit must be idempotent (one filter)"
        # and the app actually has it installed exactly once
        app.removeEventFilter(f1)
        try:
            app.removeEventFilter(f1)  # second removal: no error, already gone
        except Exception:  # pragma: no cover - defensive
            pytest.fail("double removeEventFilter raised")
        app.installEventFilter(f1)

    def test_wiring_app_run_installs_the_filter(self):
        """The wiring pin: ui_qt.app.run installs the filter after the theme
        (source-scan — run() needs a live QApplication to execute)."""
        src = (_project_root / "ui_qt" / "app.py").read_text(encoding="utf-8")
        run_at = src.index("def run() -> None:")
        apply_at = src.index("theme_manager.apply(app)", run_at)
        install_at = src.index("install_modal_button_fit(app)", run_at)
        assert install_at > apply_at, (
            "install_modal_button_fit must be called inside run(), after theme_manager.apply"
        )


# ═══════════════════════════════════════════════════════════════════════════
# The evidenced site — shared._show_success_modal (belt-and-braces)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(not _qt_available(), reason="PySide6 not importable")
class TestSharedModalSite:
    def test_success_modal_fits_buttons_before_exec(self, qss_theme, no_global_filter, monkeypatch):
        """_show_success_modal calls exec() (a modal loop) — patch it out and
        capture the box at the moment it would have blocked, asserting the
        buttons are already fitted (the belt-and-braces call)."""
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.views.service_dialogs.dialogs import shared

        app = qss_theme
        captured = []

        def fake_exec(self):
            captured.append(self)
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        shared._show_success_modal(
            None,
            "Σ Summarization Complete",
            "pasted > 1.md (5,644 chars)\n(detailed + analysis) = Format: Markdown (.md)",
            file_path="/tmp/does-not-need-to-exist.md",
            on_try_another=None,
        )
        assert len(captured) == 1
        box = captured[0]
        try:
            for btn in box.buttons():
                assert btn.minimumWidth() >= btn.sizeHint().width(), (
                    f"button {btn.text()!r} not fitted before exec()"
                )
        finally:
            box.deleteLater()
            app.processEvents()

    def test_success_modal_without_file_path_still_fits(
        self, qss_theme, no_global_filter, monkeypatch
    ):
        """The two-button variant (file_path=None → no Open button)."""
        from PySide6.QtWidgets import QMessageBox

        from ui_qt.views.service_dialogs.dialogs import shared

        captured = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: captured.append(self) or 0)
        shared._show_success_modal(
            None,
            "OCR Complete",
            "Done! 1 file(s) processed",
            file_path=None,
            on_try_another=lambda: None,
        )
        box = captured[0]
        try:
            assert len(box.buttons()) == 2  # Try Another + Close
            for btn in box.buttons():
                assert btn.minimumWidth() >= btn.sizeHint().width()
        finally:
            box.deleteLater()
            qss_theme.processEvents()
