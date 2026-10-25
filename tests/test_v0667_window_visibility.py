"""V0.6.67 — the window-visibility release (evidence: Elixir-diagnostics.zip).

Field evidence, 2026-10-25 (the first diagnostics the Collect Diagnostics
tool produced — the V0.6.66 investment paying off):

* ``startup.log``: EVERY launch reached "Qt UI launch".  The interleaved
  elapsed-ms suffixes prove the 20:04 launches all completed the logged
  startup — nothing hung in the import chain.
* ``elixir-processes.txt`` (collected 20:05:14): the FIRST launch of the
  session (pid 4336, "Qt UI launch" at 20:04:54.4) was STILL ALIVE —
  sitting in ``exec()`` with a window the user could not see.  The two
  later launches were GONE: they connected to the first instance's lock
  server, sent FOCUS, got ACKed (the invisible primary's event loop was
  perfectly healthy — it raised an invisible window), and exited(0)
  silently.  ``SystemExit`` bypasses ``sys.excepthook``, so no crash log,
  no error box — the signature of every "second click does nothing".
* Net effect: the app "never opens" while a healthy invisible window runs
  the whole time.  The restore-time visibility check existed but was
  SKIPPED for maximized restores, and nothing re-validated the window's
  position AFTER ``show()``; ``showNormal``/``raise_`` cannot rescue a
  window stranded on a detached monitor.
* CI stayed green because the launch test only checked
  ``MainWindowHandle != 0`` — an off-screen window passes that.

The V0.6.67 fixes pinned by this file:

1. ``utils.geometry.sanitize_restore_plan`` — the pure restore decision:
   maximized restores are validated too, and every unvalidated position
   degrades to "center on the primary screen".
2. ``utils.single_instance`` — the honest-ACK FOCUS protocol: the primary
   reports whether its window is really on a screen after self-healing;
   a second launch only defers to a primary that can prove visibility.
3. ``ui_qt.app`` wiring — the post-show rescue, the save-side hardening
   (never persist minimized/maximized-phantom geometry), the honest reply,
   and the ``window shown`` / ``event loop finished`` startup.log steps.
4. ``build_installer.py`` — WINDOW_SHOWN now means visible AND on-screen.
5. ``collect_diagnostics.cmd`` — collects window_geometry.json + screen
   inventory + DPI; every PowerShell step leaves a file even when blocked.
"""

from __future__ import annotations

from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_MAIN_SRC = (_project_root / "main.py").read_text(encoding="utf-8")
_APP_SRC = (_project_root / "ui_qt" / "app.py").read_text(encoding="utf-8")
_BUILD_SRC = (_project_root / "build_installer.py").read_text(encoding="utf-8")
_DIAG_CMD = (_project_root / "packaging" / "collect_diagnostics.cmd").read_text(encoding="utf-8")

# One 1080p primary with a taskbar (available height 1040) + one secondary.
SCREENS = [(0, 0, 1920, 1040), (1920, 0, 1280, 1024)]


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1 — the restore plan (pure, Qt-free)
# ═════════════════════════════════════════════════════════════════════════════


class TestSanitizeRestorePlan:
    def test_valid_position_honored(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": 700, "h": 500, "x": 100, "y": 100}, SCREENS)
        assert plan["move_to"] == (100, 100)
        assert plan["center_default"] is False
        assert plan["w"] == 700 and plan["h"] == 500
        assert plan["maximized"] is False

    def test_offscreen_position_degrades_to_centered_default(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": 700, "h": 500, "x": 5000, "y": 5000}, SCREENS)
        assert plan["move_to"] is None
        assert plan["center_default"] is True

    def test_maximized_offscreen_target_rejected(self):
        """THE field-report hole: a maximized restore whose normal target
        sits on a monitor that is no longer attached must NOT be honored —
        the old code skipped the visibility check for maximized windows
        and maximized the window onto the phantom screen forever."""
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan(
            {"w": 700, "h": 500, "x": 5000, "y": 5000, "maximized": True}, SCREENS
        )
        assert plan["move_to"] is None
        assert plan["center_default"] is True
        assert plan["maximized"] is True  # still maximized — on the default screen

    def test_maximized_onscreen_target_honored(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan(
            {"w": 700, "h": 500, "x": 2200, "y": 100, "maximized": True}, SCREENS
        )
        assert plan["move_to"] == (2200, 100)  # secondary screen — valid
        assert plan["center_default"] is False
        assert plan["maximized"] is True

    def test_no_position_centers(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": 608, "h": 432}, SCREENS)
        assert plan["move_to"] is None
        assert plan["center_default"] is True

    def test_size_clamps_and_defaults(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": 10000, "h": 10000, "x": 10, "y": 10}, SCREENS)
        assert plan["w"] == 900 and plan["h"] == 620
        plan = sanitize_restore_plan({}, SCREENS)
        assert plan["w"] == 608 and plan["h"] == 432

    def test_no_screens_fails_safe_to_centered(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": 700, "h": 500, "x": 100, "y": 100}, [])
        assert plan["move_to"] is None
        assert plan["center_default"] is True

    def test_garbage_values_degrade_not_crash(self):
        from utils.geometry import sanitize_restore_plan

        plan = sanitize_restore_plan({"w": "junk", "h": None, "x": "x", "y": 3.5}, SCREENS)
        assert plan["w"] == 608 and plan["h"] == 432
        assert plan["move_to"] is None
        assert plan["center_default"] is True


# ═════════════════════════════════════════════════════════════════════════════
# FIX 2 — the honest-ACK FOCUS protocol (pure, stdlib-only)
# ═════════════════════════════════════════════════════════════════════════════


class TestFocusProtocol:
    def test_replies(self):
        from utils.single_instance import primary_reply

        assert primary_reply(True) == b"OK-VISIBLE"
        assert primary_reply(False) == b"OK-INVISIBLE"

    def test_visible_ack_defers(self):
        from utils.single_instance import focus_ack_indicates_visible

        assert focus_ack_indicates_visible(b"OK-VISIBLE") is True

    def test_invisible_ack_takes_over(self):
        """The field-report fix: a primary that admits its window is
        off-screen must lose the lock — the second launch takes over and
        shows its own (force-onscreen) window instead of exiting."""
        from utils.single_instance import focus_ack_indicates_visible

        assert focus_ack_indicates_visible(b"OK-INVISIBLE") is False

    def test_legacy_ok_still_defers(self):
        from utils.single_instance import focus_ack_indicates_visible

        assert focus_ack_indicates_visible(b"OK") is True

    def test_empty_or_garbage_never_defers(self):
        from utils.single_instance import focus_ack_indicates_visible

        assert focus_ack_indicates_visible(b"") is False
        assert focus_ack_indicates_visible(b"FOCUS") is False
        assert focus_ack_indicates_visible(b"nonsense") is False

    def test_cross_version_compatibility(self):
        """An OLD (≤ V0.6.66) second instance parses ``b"OK" in reply`` —
        both new reply shapes keep that substring so upgrades-in-place
        never wedge (old behavior is the floor, never worse)."""
        from utils.single_instance import REPLY_INVISIBLE, REPLY_VISIBLE

        assert b"OK" in REPLY_VISIBLE
        assert b"OK" in REPLY_INVISIBLE


# ═════════════════════════════════════════════════════════════════════════════
# FIX 3 — ui_qt/app.py wiring (source pins, the V0.6.65 pattern)
# ═════════════════════════════════════════════════════════════════════════════


class TestAppWiring:
    def test_post_show_rescue_after_show_before_exec(self):
        show_pos = _APP_SRC.find("window.show()")
        # the indented CALL inside run() — not the `def` line
        rescue_pos = _APP_SRC.find("    _ensure_window_onscreen(window)")
        exec_pos = _APP_SRC.find("rc = app.exec()")
        assert 0 < show_pos < rescue_pos < exec_pos, (
            "the on-screen rescue must run on the FINAL post-show position, "
            "before the event loop starts"
        )

    def test_focus_handler_heals_before_raising(self):
        heal_pos = _APP_SRC.find("_ensure_window_onscreen(_primary_window)")
        raise_pos = _APP_SRC.find("_primary_window.raise_()")
        assert 0 < heal_pos < raise_pos, "never raise an invisible window"

    def test_focus_reply_is_honest(self):
        assert "sock.write(primary_reply(_window_is_onscreen(_primary_window)))" in _APP_SRC

    def test_window_shown_step_logged(self):
        assert 'f"window shown — frame={window.frameGeometry().getRect()} screens=' in _APP_SRC
        assert "event loop finished (rc={rc})" in _APP_SRC

    def test_save_geometry_never_persists_minimized(self):
        assert "if self.isMinimized():" in _APP_SRC
        save_pos = _APP_SRC.find("def _save_geometry")
        guard_pos = _APP_SRC.find("if self.isMinimized():")
        assert 0 < save_pos < guard_pos

    def test_save_geometry_uses_normal_geometry_when_maximized(self):
        assert (
            "geo = self.normalGeometry() if self.isMaximized() else self.frameGeometry()"
            in _APP_SRC
        )

    def test_restore_uses_the_pure_plan(self):
        assert "sanitize_restore_plan(" in _APP_SRC
        assert "_center_on_primary" in _APP_SRC

    def test_geometry_module_constants_mirror_app(self):
        """The pure module's defaults must not drift from the UI's."""
        import re

        from utils import geometry as geom

        assert (geom.DEFAULT_W, geom.DEFAULT_H) == (608, 432)
        assert (geom.MAX_W, geom.MAX_H) == (900, 620)
        assert bool(re.search(r"resize\(608, 432\)", _APP_SRC))


# ═════════════════════════════════════════════════════════════════════════════
# FIX 4 — main.py gpu probe (torch not bundled on Windows → no NameError)
# ═════════════════════════════════════════════════════════════════════════════


class TestGpuProbe:
    def test_probe_no_longer_references_torch_early_directly(self):
        """The V0.6.66 gpu_probe.log showed 3 header lines then nothing on
        every launch: `_torch_early` raised NameError inside the write
        block when torch isn't bundled (the Windows build)."""
        assert 'sys.modules.get("torch")' in _MAIN_SRC
        assert "torch: {getattr(_t, '__version__', 'NOT INSTALLED')}" in _MAIN_SRC
        assert "torch not bundled in this build" in _MAIN_SRC

    def test_import_probe_still_wrapped(self):
        assert "import torch as _torch_early" in _MAIN_SRC  # the probe itself is unchanged


# ═════════════════════════════════════════════════════════════════════════════
# FIX 5 — the CI launch gate + the diagnostics collector
# ═════════════════════════════════════════════════════════════════════════════


class TestBuildInstallerGate:
    def test_launch_test_requires_visible_window(self):
        assert "IsWindowVisible" in _BUILD_SRC

    def test_launch_test_requires_onscreen_rect(self):
        assert "GetWindowRect" in _BUILD_SRC
        assert "$area -ge 10000" in _BUILD_SRC

    def test_offscreen_is_a_failure_result(self):
        assert "WINDOW_OFFSCREEN" in _BUILD_SRC
        assert "WINDOW_HIDDEN" in _BUILD_SRC


class TestDiagnosticsCollector:
    def test_collects_window_geometry(self):
        assert "window_geometry.json" in _DIAG_CMD

    def test_collects_screen_inventory_and_dpi(self):
        assert "Win32_DesktopMonitor" in _DIAG_CMD
        assert "Win32_VideoController" in _DIAG_CMD
        assert "AppliedDPI" in _DIAG_CMD

    def test_powershell_steps_leave_a_file_even_when_blocked(self):
        """The 2026-10-25 report's Defender + disk-space files were simply
        absent — PowerShell was presumably blocked; every step must leave
        a trace file saying so."""
        assert "powershell-available.txt" in _DIAG_CMD
        assert _DIAG_CMD.count("if not exist") >= 4
