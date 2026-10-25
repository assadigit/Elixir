"""V18.20.4.5 (P4, task 2-c) — dialog lifecycle + window geometry.

Covers the three P4 items owned by this task per the approved V18.20.4.0
SWOT roadmap:

- **W-b9 (dialog-tree leak):** every ``dlg.exec()`` open in
  ``convert_view.py`` (11 named service dialogs + the podcast_maker inline
  QDialog + ``_open_wizard`` = 13 sites) and in ``app.py`` (5 sites:
  wizard, hallucination audit, about/system, validate, settings) parented a
  dialog to the window and never released it — each open accumulated a
  hidden widget tree (the wizard alone is 10 step widgets). Every site now
  sets ``Qt.WA_DeleteOnClose`` so the C++ tree is destroyed on close.
  QMessageBox/QFileDialog static-modal calls are deliberately NOT covered
  (not applicable).
- **W-b10 support:** ``convert_view._register_callbacks`` now passes
  ``owner="convert_view`` so the wizard's closeEvent and the queue's
  callback install/restore can check ownership instead of
  unconditionally stealing/restoring callbacks.
- **T-b5 (window restored off-screen):** ``app._restore_geometry`` used to
  restore saved x/y blindly — after a monitor change the window came back
  fully off-screen and the app looked "dead on launch". The new
  Qt-free ``utils/geometry.py`` decides whether the restored window is
  visible on any screen; on failure the app falls back to the default
  608x432 centered on the primary screen. (The helper is pure Python so
  this file needs NO PySide6 — headless rig safe.)
- **T-b2 (QThread abort on close):** the live-transcribe worker was
  parented to the dialog with no closeEvent guard — closing while
  recording aborted with "QThread: Destroyed while thread is still
  running". The worker is now un-parented and the dialog guards the
  close (ask → stop → wait → keep-alive for a still-winding-down thread).

Two layers per the house pattern: pure-Py behavioral tests for the
geometry helpers (always run) + headless-safe source pins for the
Qt-touching edits (PySide6 is not installed on the rig).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.geometry import rects_intersect, restored_geometry_is_visible  # noqa: E402

_CONVERT_VIEW = _project_root / "ui_qt" / "views" / "convert_view.py"
_APP = _project_root / "ui_qt" / "app.py"
_LIVE = _project_root / "ui_qt" / "views" / "service_dialogs" / "live_transcribe.py"
_GEOMETRY = _project_root / "utils" / "geometry.py"

# Exact WA_DeleteOnClose site counts implemented by this task:
#   convert_view.py = 13 (11 named service dialogs + podcast_maker inline
#   QDialog + _open_wizard); app.py = 5 (wizard, hallucination audit,
#   about/system, validate, settings). The QMessageBox success box in
# convert_view._on_complete and the QFileDialog/QMessageBox static modals
# are deliberately excluded (W-b9 does not apply to them).
_WA_LINE = "dlg.setAttribute(Qt.WA_DeleteOnClose, True)"
_CONVERT_VIEW_WA_SITES = 13
_APP_WA_SITES = 5


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _method_body(src: str, name: str) -> str:
    """Crude slice of a method body: from ``def name(`` to the next method
    definition at the same indentation (good enough for pinning)."""
    m = re.search(rf"def {re.escape(name)}\(.*?(?=\n    def |\n    # ═)", src, re.S)
    assert m is not None, f"method {name} not found"
    return m.group(0)


def _exec_contexts(src: str, window: int = 4):
    """(lineno, preceding-context) for every ``dlg.exec()`` line — used to
    prove each open is immediately preceded by the WA_DeleteOnClose call.
    (``_box.exec()`` / static modals never match ``dlg.exec()``.)"""
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if "dlg.exec()" in line:
            yield i + 1, "\n".join(lines[max(0, i - window) : i + 1])


# ═══════════════════════════════════════════════════════════════════════════
# Behavioral — utils/geometry.py (pure Python, no Qt)
# ═══════════════════════════════════════════════════════════════════════════


class TestRectsIntersect:
    def test_identical_rects_intersect(self):
        assert rects_intersect((10, 20, 100, 50), (10, 20, 100, 50)) is True

    def test_disjoint_rects_do_not_intersect(self):
        assert rects_intersect((0, 0, 10, 10), (100, 100, 10, 10)) is False
        assert rects_intersect((0, 0, 10, 10), (0, 100, 10, 10)) is False

    def test_edge_touching_shares_no_positive_area(self):
        # a's right edge == b's left edge → boundary only, no area.
        assert rects_intersect((0, 0, 100, 100), (100, 0, 100, 100)) is False
        # a's bottom edge == b's top edge.
        assert rects_intersect((0, 0, 100, 100), (0, 100, 100, 100)) is False

    def test_contained_and_partial_overlaps_intersect(self):
        assert rects_intersect((0, 0, 1920, 1080), (500, 500, 10, 10)) is True
        assert rects_intersect((100, 100, 200, 200), (250, 250, 200, 200)) is True

    def test_zero_size_rect_never_intersects(self):
        assert rects_intersect((0, 0, 0, 100), (0, 0, 100, 100)) is False
        assert rects_intersect((0, 0, 100, 0), (0, 0, 100, 100)) is False

    def test_negative_size_rect_never_intersects(self):
        assert rects_intersect((-10, 0, -5, 100), (0, 0, 100, 100)) is False
        assert rects_intersect((0, 0, 100, 100), (0, 0, 100, -1)) is False


class TestRestoredGeometryIsVisible:
    SCREEN = (0, 0, 1920, 1080)

    def test_window_fully_on_screen(self):
        assert restored_geometry_is_visible(100, 100, 608, 432, [self.SCREEN])

    def test_window_fully_offscreen_right(self):
        assert restored_geometry_is_visible(2500, 100, 608, 432, [self.SCREEN]) is False

    def test_window_fully_offscreen_below(self):
        assert restored_geometry_is_visible(100, 2000, 608, 432, [self.SCREEN]) is False

    def test_1px_edge_graze_is_invisible(self):
        # Grazing the right edge by 1px × 50px = 50px² < the 100px²
        # default threshold — still effectively invisible.
        assert restored_geometry_is_visible(1919, 0, 50, 50, [self.SCREEN]) is False
        # Same for the bottom edge.
        assert restored_geometry_is_visible(960, 1079, 50, 40, [self.SCREEN]) is False

    def test_partial_overlap_over_threshold_is_visible(self):
        # 320px × 400px = 128,000px² of overlap — clearly visible.
        assert restored_geometry_is_visible(1600, 500, 600, 400, [self.SCREEN]) is True

    def test_no_screens_is_false(self):
        # Fail-safe: no screens (headless / probe failure) → caller falls
        # back to the default geometry.
        assert restored_geometry_is_visible(0, 0, 608, 432, []) is False

    def test_nonpositive_window_size_is_false(self):
        assert restored_geometry_is_visible(0, 0, 0, 432, [self.SCREEN]) is False
        assert restored_geometry_is_visible(0, 0, 608, 0, [self.SCREEN]) is False
        assert restored_geometry_is_visible(0, 0, -608, 432, [self.SCREEN]) is False

    def test_left_monitor_negative_coordinates(self):
        # Classic monitor-change case: a second monitor LEFT of primary.
        screens = [(-1920, 0, 1920, 1080), (0, 0, 1920, 1080)]
        assert restored_geometry_is_visible(-1820, 100, 600, 400, screens) is True

    def test_offscreen_left_of_all_monitors(self):
        screens = [(-1920, 0, 1920, 1080), (0, 0, 1920, 1080)]
        assert restored_geometry_is_visible(-3000, 0, 600, 400, screens) is False

    def test_custom_min_overlap_area_threshold(self):
        # The 50px² graze is invisible at the default 100px² threshold...
        assert (
            restored_geometry_is_visible(1919, 0, 50, 50, [self.SCREEN], min_overlap_area=100)
            is False
        )
        # ...but visible if the caller lowers the bar to 40px².
        assert (
            restored_geometry_is_visible(1919, 0, 50, 50, [self.SCREEN], min_overlap_area=40)
            is True
        )

    def test_degenerate_screen_rect_is_ignored(self):
        # A zero-width "screen" can never satisfy the overlap threshold.
        assert restored_geometry_is_visible(0, 0, 600, 400, [(0, 0, 0, 1080)]) is False


# ═══════════════════════════════════════════════════════════════════════════
# Source pins — W-b9 / W-b10 (convert_view.py)
# ═══════════════════════════════════════════════════════════════════════════


class TestConvertViewPins:
    def test_wa_delete_on_close_exact_site_count(self):
        """13 sites exactly: 11 named service dialogs + the podcast_maker
        inline QDialog + _open_wizard (the file has exactly 13 dlg.exec()
        opens; the _on_complete QMessageBox is excluded by design)."""
        src = _src(_CONVERT_VIEW)
        code = _strip_comments(src)
        assert code.count(_WA_LINE) == _CONVERT_VIEW_WA_SITES, (
            f"expected exactly {_CONVERT_VIEW_WA_SITES} WA_DeleteOnClose "
            f"calls, found {code.count(_WA_LINE)}"
        )
        # The Qt enum must be importable in this module (it was not before).
        assert "from PySide6.QtCore import Qt" in src
        # One W-b9 defect comment per site.
        assert src.count("# V18.20.4.5 (W-b9):") == _CONVERT_VIEW_WA_SITES

    def test_every_dlg_exec_is_preceded_by_delete_on_close(self):
        src = _src(_CONVERT_VIEW)
        execs = list(_exec_contexts(src))
        assert len(execs) == _CONVERT_VIEW_WA_SITES, (
            f"expected {_CONVERT_VIEW_WA_SITES} dlg.exec() opens, found {len(execs)}"
        )
        for lineno, ctx in execs:
            assert _WA_LINE in ctx, (
                f"dlg.exec() at line {lineno} is not preceded by "
                f"WA_DeleteOnClose within 4 lines (W-b9)"
            )

    def test_podcast_maker_inline_dialog_is_covered(self):
        m = re.search(
            r'elif tool_key == "podcast_maker".*?dlg\.exec\(\)', _src(_CONVERT_VIEW), re.S
        )
        assert m is not None, "podcast_maker branch not found"
        assert _WA_LINE in m.group(0), (
            "the podcast_maker inline QDialog must also delete on close (W-b9)"
        )

    def test_register_callbacks_carries_owner_tag(self):
        body = _method_body(_src(_CONVERT_VIEW), "_register_callbacks")
        assert 'owner="convert_view"' in body, (
            "convert_view must register its callbacks with the "
            'owner="convert_view" tag (W-b10 support)'
        )
        # The four bridge emitters stay wired (happy path unchanged).
        for emitter in ("emit_progress", "emit_status", "emit_log", "emit_complete"):
            assert emitter in body


# ═══════════════════════════════════════════════════════════════════════════
# Source pins — W-b9 / T-b5 (app.py)
# ═══════════════════════════════════════════════════════════════════════════


class TestAppPins:
    def test_wa_delete_on_close_exact_site_count(self):
        """5 sites exactly: _open_wizard, _open_hallucination_audit,
        _open_about_system, _open_validate, _open_settings."""
        src = _src(_APP)
        code = _strip_comments(src)
        assert code.count(_WA_LINE) == _APP_WA_SITES, (
            f"expected exactly {_APP_WA_SITES} WA_DeleteOnClose calls, found {code.count(_WA_LINE)}"
        )
        assert src.count("# V18.20.4.5 (W-b9):") == _APP_WA_SITES

    def test_every_dlg_exec_is_preceded_by_delete_on_close(self):
        src = _src(_APP)
        execs = list(_exec_contexts(src))
        assert len(execs) == _APP_WA_SITES, (
            f"expected {_APP_WA_SITES} dlg.exec() opens, found {len(execs)}"
        )
        for lineno, ctx in execs:
            assert _WA_LINE in ctx, (
                f"dlg.exec() at line {lineno} is not preceded by "
                f"WA_DeleteOnClose within 4 lines (W-b9)"
            )

    def test_restore_geometry_validates_against_screens(self):
        # V0.6.67: the validation moved into the pure
        # utils.geometry.sanitize_restore_plan (unit-tested in
        # test_v0667_window_visibility.py); _restore_geometry applies the
        # plan.  The T-b5 contract survives: restored geometry IS validated
        # against the CURRENT screens, and — the V0.6.67 fix — maximized
        # restores are validated too (the old code skipped them, which is
        # how a window could maximize onto a detached monitor forever).
        body = _method_body(_src(_APP), "_restore_geometry")
        assert "sanitize_restore_plan(" in body, (
            "_restore_geometry must apply the validated restore plan (T-b5 → V0.6.67)"
        )
        assert "_screens_rects(QApplication.instance())" in body

    def test_offscreen_fallback_resizes_and_warns(self):
        body = _method_body(_src(_APP), "_restore_geometry")
        # V0.6.68: the fallback resizes to the geometry module's constants
        # (760x540 — the restored original default; equality pinned in
        # test_v0667_window_visibility.py's constants-mirror test).
        assert "self.resize(DEFAULT_W, DEFAULT_H)" in body, (
            "the off-screen fallback must reset the default size (T-b5)"
        )
        assert "logger.warning(" in body
        # The warning message is split across two string literals in the
        # source — pin the contiguous fragment.
        assert "visible on any screen" in body
        # Centered on the primary screen, never off its top-left corner
        # (V0.6.67: via _center_on_primary).
        assert "_center_on_primary" in body

    def test_geometry_helper_imported(self):
        assert "from utils.geometry import (" in _src(_APP), (
            "app.py must import the Qt-free geometry helpers (T-b5; V0.6.68 — "
            "the import is parenthesized and now also carries DEFAULT_W/H)"
        )
        assert "restored_geometry_is_visible" in _src(_APP), (
            "app.py must import the Qt-free geometry helper (T-b5)"
        )
        assert "sanitize_restore_plan" in _src(_APP), (
            "app.py must import the V0.6.67 restore-plan helper"
        )
        # The helper itself stays Qt-free (importable on the headless rig —
        # its docstring MENTIONS PySide6, so pin the absence of imports).
        gsrc = _src(_GEOMETRY)
        assert "from PySide6" not in gsrc
        assert "import PySide6" not in gsrc
        assert "QtWidgets" not in gsrc
        assert "QtCore" not in gsrc


# ═══════════════════════════════════════════════════════════════════════════
# Source pins — T-b2 (live_transcribe.py)
# ═══════════════════════════════════════════════════════════════════════════


class TestLiveTranscribePins:
    def test_worker_is_constructed_unparented(self):
        src = _strip_comments(_src(_LIVE))
        assert "_LiveTranscribeWorker(model_name, language, None)" in src, (
            "the worker must NOT be parented to the dialog (T-b2) — a Qt "
            "parent made dialog destruction kill a running QThread"
        )
        assert "_LiveTranscribeWorker(model_name, language, self)" not in src

    def test_close_event_guards_running_thread(self):
        body = _method_body(_src(_LIVE), "closeEvent")
        assert "worker.isRunning()" in body, "closeEvent must guard on the running worker (T-b2)"
        assert "worker.stop()" in body
        assert "worker.wait(2000)" in body
        # The user is asked first, and No keeps the dialog open.
        assert "QMessageBox.question(" in body
        assert "event.ignore()" in body
        assert "event.ignore()" in body and "super().closeEvent(event)" in body

    def test_retired_workers_keepalive(self):
        """Un-parenting alone is not enough: a still-winding-down thread
        must never lose its last Python reference (that is itself the
        'QThread: Destroyed while thread is still running' abort)."""
        src = _src(_LIVE)
        assert "self._retired_workers" in src
        assert "worker.finished.connect(worker.deleteLater)" in src
        # The Stop button still works — routed through the retire helper.
        stop_body = _method_body(src, "_stop")
        assert "_stop_and_retire_worker()" in stop_body
