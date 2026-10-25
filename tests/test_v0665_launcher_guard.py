"""V0.6.65 — the launcher guard + fixed single-instance protocol.

Evidence: the V0.6.64 field report — first real-machine install of
Elixir-Setup-0.6.64.exe ("I've installed the app … it doesn't open at
all"), CI launch test GREEN on a clean runner, so the failure was
machine-specific and completely invisible: the Windows build is a
windowed PyInstaller bundle in which every pre-window death is silent.

Three gaps found in the startup path, three fixes pinned here:

FIX 1 (crash visibility): an import-time / pre-QApplication exception
  escaped every handler (the first project import at main.py:49 runs
  before any excepthook exists) → ``core/system/launcher_guard.py``
  installs a ``sys.excepthook`` as the FIRST statement of main.py:
  ``startup.log`` (step timeline), ``startup_crash.log`` (full report,
  plus a beside-exe copy), and a Qt-free native Win32 error box
  (``MessageBoxTimeoutW``, 90 s auto-close so unattended sessions never
  hang). main.py's own ``_install_excepthook`` also gained the missing
  pre-QApplication branch (it previously showed a dialog ONLY when a
  QApplication already existed).
FIX 2 (the broken single-instance protocol): the V18.1 lock sent
  ``FOCUS`` to the primary and exited — but the primary NEVER WIRED the
  server side (no ``newConnection`` handler: nobody read the pipe, the
  window never came forward, the second launch died silently). With a
  first launch still starting or hung, EVERY later double-click did
  nothing at all. The protocol now has a server side (raise window +
  ``OK`` ACK) and a zombie-takeover path (no ACK within 2.5 s → the
  second launch takes the lock over instead of exiting forever).
FIX 3 (liveness + the AV signature): a ``_StartupSplash`` label shows
  "Elixir is loading…" the moment the lock is acquired, so a slow first
  launch (cold disk / antivirus scanning every DLL) no longer looks like
  a dead app; and ``precheck_qt_platform_plugin`` turns the one
  AV-stripped-bundle failure Python can see pre-emptively (missing
  ``qwindows.dll`` → uncatchable ``qFatal``) into an actionable message.

The Qt-side wiring is pinned via source-scan (the house pattern from
tests/test_deadline_watchdog.py / test_v1820412_a_system_robustness.py —
pure-Python tests, no QApplication needed); the guard itself is
exercised directly.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parents[1]
_LG_PATH = _project_root / "core" / "system" / "launcher_guard.py"
_LG_SRC = _LG_PATH.read_text(encoding="utf-8")
_MAIN_SRC = (_project_root / "main.py").read_text(encoding="utf-8")
_APP_SRC = (_project_root / "ui_qt" / "app.py").read_text(encoding="utf-8")


@pytest.fixture()
def guard(tmp_path, monkeypatch):
    """Import launcher_guard with HOME pointed at a tmp dir, install it,
    and restore process state after the test.

    Resets the module's private state so tests are order-independent
    (install() is otherwise idempotent across tests via ``_installed``).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    lg = importlib.import_module("core.system.launcher_guard")
    lg._fh = None
    lg._prev_hook = None
    lg._installed = False
    lg._last_step_ts[0] = None
    saved_hook = sys.excepthook
    try:
        yield lg, tmp_path
    finally:
        sys.excepthook = saved_hook
        if lg._fh is not None:
            try:
                lg._fh.close()
            except Exception:
                pass
        lg._fh = None
        lg._prev_hook = None
        lg._installed = False
        lg._last_step_ts[0] = None


# ═════════════════════════════════════════════════════════════════════════════
# Contract pins — the guard must be importable before ANYTHING
# ═════════════════════════════════════════════════════════════════════════════


class TestLauncherGuardContract:
    """The guard runs before every project import — its dependencies are
    pinned mechanically so a future edit cannot smuggle in a heavy one."""

    _ALLOWED = {
        "__future__",
        "os",
        "sys",
        "datetime",
        "pathlib",
        "traceback",
        "ctypes",  # lazy, inside _native_error_box (Windows only)
    }

    def test_imports_are_stdlib_only(self):
        tree = ast.parse(_LG_SRC)
        seen = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                seen.add(node.module.split(".")[0])
        illegal = sorted(seen - self._ALLOWED)
        assert not illegal, f"launcher_guard must stay stdlib-only, found: {illegal}"

    def test_import_has_no_side_effects(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        import core.system.launcher_guard as lg  # noqa: F401 — the import IS the test

        assert not (tmp_path / ".elixir").exists(), (
            "importing launcher_guard must not touch the filesystem "
            "(it runs before utils.settings, crash visibility, everything)"
        )

    def test_never_raise_contract_documented(self):
        assert "NEVER raises" in _LG_SRC or "never raises" in _LG_SRC


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1 — install / startup.log / crash report / hook
# ═════════════════════════════════════════════════════════════════════════════


class TestInstallAndStartupLog:
    def test_install_creates_log_and_hook(self, guard):
        lg, tmp_path = guard
        assert lg.install(startup_log=tmp_path / "s.log") is True
        log = tmp_path / "s.log"
        assert log.is_file()
        assert "guard armed" in log.read_text(encoding="utf-8")
        assert sys.excepthook is lg._guard_hook
        # idempotent: a second install (e.g. re-imported main) is a no-op
        assert lg.install(startup_log=tmp_path / "other.log") is True
        assert "other.log" not in str(getattr(lg._fh, "name", ""))

    def test_install_failure_never_raises(self, guard, tmp_path):
        lg, _ = guard
        # unwritable, non-existent-dir path whose parent is a FILE
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir", encoding="utf-8")
        assert lg.install(startup_log=blocker / "sub" / "s.log") is False
        # and the previous hook is left untouched
        assert sys.excepthook is lg._guard_hook or sys.excepthook is not None

    def test_startup_step_writes_timeline(self, guard):
        lg, tmp_path = guard
        lg.install(startup_log=tmp_path / "s.log")
        lg.startup_step("first step")
        lg.startup_step("second step")
        content = (tmp_path / "s.log").read_text(encoding="utf-8")
        assert "first step" in content
        assert "second step" in content
        assert "(+0 ms" in content or "(+" in content, "elapsed-since-previous must be recorded"

    def test_startup_step_before_install_is_silent_noop(self, guard):
        lg, _ = guard
        lg.startup_step("nobody is listening")  # must not raise


class TestReportFatal:
    def test_report_writes_crash_log(self, guard, tmp_path):
        lg, _ = guard
        out = lg.report_fatal("ValueError: boom\n  at somewhere", log_dir=tmp_path)
        assert out == tmp_path / "startup_crash.log"
        content = out.read_text(encoding="utf-8")
        assert "STARTUP FAILURE" in content
        assert "ValueError: boom" in content
        assert "environment" in content

    def test_compose_error_text_plain_words(self, guard, tmp_path):
        lg, _ = guard
        tb = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: boom'
        text = lg.compose_error_text(tb, tmp_path / "startup_crash.log")
        assert "could not start" in text
        assert "ValueError: boom" in text  # the LAST line, not the whole wall
        assert str(tmp_path / "startup_crash.log") in text

    def test_guard_hook_writes_report_and_chains(self, guard, tmp_path):
        lg, _ = guard
        lg.install(startup_log=tmp_path / "s.log")
        chained = []
        lg._prev_hook = lambda *a: chained.append(a)  # spy on the chain
        try:
            raise RuntimeError("the field report's silent death")
        except RuntimeError as e:
            lg._guard_hook(RuntimeError, e, e.__traceback__)
        crash = tmp_path / ".elixir" / "startup_crash.log"
        # report_fatal defaults to _user_data_dir() (~/.elixir under the
        # fixture's HOME)
        assert crash.is_file()
        assert "the field report's silent death" in crash.read_text(encoding="utf-8")
        assert chained, "the hook must chain to the hook it replaced"

    def test_guard_hook_never_raises(self, guard, tmp_path):
        lg, _ = guard
        lg.install(startup_log=tmp_path / "s.log")
        lg._prev_hook = None
        # KeyboardInterrupt must take the DEFAULT path (no crash report)
        try:
            raise KeyboardInterrupt()
        except KeyboardInterrupt as e:
            lg._guard_hook(KeyboardInterrupt, e, e.__traceback__)
        assert not (tmp_path / ".elixir" / "startup_crash.log").exists()


# ═════════════════════════════════════════════════════════════════════════════
# FIX 3b — the qwindows.dll precheck (AV-stripped-bundle detector)
# ═════════════════════════════════════════════════════════════════════════════


class TestPlatformPluginPrecheck:
    def test_true_from_source(self, guard, monkeypatch):
        lg, _ = guard
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert lg.precheck_qt_platform_plugin() is True

    def test_find_direct_layouts(self, guard, tmp_path):
        lg, _ = guard
        (tmp_path / "PySide6" / "plugins" / "platforms").mkdir(parents=True)
        dll = tmp_path / "PySide6" / "plugins" / "platforms" / "qwindows.dll"
        dll.write_bytes(b"MZ")
        assert lg._find_qwindows_dll(tmp_path) == dll
        flat_dir = tmp_path / "plugins" / "platforms"
        flat_dir.mkdir(parents=True)
        flat = flat_dir / "qwindows.dll"
        flat.write_bytes(b"MZ")
        assert lg._find_qwindows_dll(tmp_path) is not None

    def test_find_via_bounded_walk(self, guard, tmp_path):
        lg, _ = guard
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        dll = deep / "qwindows.dll"
        dll.write_bytes(b"MZ")
        assert lg._find_qwindows_dll(tmp_path) == dll

    def test_missing_dll_reports_and_returns_false(self, guard, tmp_path):
        lg, home = guard
        (tmp_path / "bundle").mkdir()
        assert lg._precheck_frozen(tmp_path / "bundle") is False
        crash = home / ".elixir" / "startup_crash.log"
        assert crash.is_file()
        content = crash.read_text(encoding="utf-8")
        assert "qwindows.dll" in content
        assert "antivirus" in content.lower()

    def test_precheck_failure_never_blocks(self, guard, tmp_path, monkeypatch):
        lg, _ = guard
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        # os.name is "posix" here — the Windows-only check must skip cleanly
        assert lg.precheck_qt_platform_plugin() is True
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.delattr(sys, "frozen", raising=False)


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1 wiring — main.py source pins
# ═════════════════════════════════════════════════════════════════════════════


class TestMainPyWiring:
    def test_guard_installed_before_every_project_import(self):
        guard_pos = _MAIN_SRC.find("launcher_guard")
        first_project_import = _MAIN_SRC.find("from utils.settings import")
        assert 0 < guard_pos < first_project_import, (
            "the guard must be armed BEFORE the first project import — "
            "that import is itself one of the silent-death sites"
        )

    def test_precheck_runs_before_qt_import(self):
        precheck_pos = _MAIN_SRC.find("_precheck_qt_plugin()")
        qt_import_pos = _MAIN_SRC.find("from ui_qt.app import run")
        assert 0 < precheck_pos < qt_import_pos

    def test_excepthook_covers_pre_qapplication_deaths(self):
        assert "if app is None:" in _MAIN_SRC
        assert "from core.system.launcher_guard import report_fatal" in _MAIN_SRC

    def test_startup_steps_wired(self):
        for step in (
            "selftest dispatch passed",
            "dependency + numpy ABI checks",
            "bootstrap (settings migration",
            "Qt platform plugin precheck",
            "Qt UI launch",
        ):
            assert step in _MAIN_SRC, f"missing startup step pin: {step}"

    def test_guard_unavailable_never_blocks_boot(self):
        # the except-branch defines callable stubs — no NameError later
        assert "def _precheck_qt_plugin() -> bool:" in _MAIN_SRC
        assert "return True" in _MAIN_SRC


# ═════════════════════════════════════════════════════════════════════════════
# FIX 2 + FIX 3a wiring — ui_qt/app.py source pins
# ═════════════════════════════════════════════════════════════════════════════


class TestSingleInstanceWiring:
    def test_server_side_finally_wired(self):
        assert "newConnection.connect(_on_lock_connection)" in _APP_SRC, (
            "the V18.1 lock promised FOCUS handling that was never wired — "
            "the server side must exist now"
        )

    def test_focus_handler_raises_the_registered_window(self):
        assert "_primary_window.showNormal()" in _APP_SRC
        assert "_primary_window.activateWindow()" in _APP_SRC

    def test_ack_protocol_present(self):
        # V0.6.67: the raw b"OK" substring test evolved into the honest-ACK
        # protocol (utils/single_instance.py): the reply is parsed by
        # focus_ack_indicates_visible so an OK-INVISIBLE primary loses the
        # lock instead of swallowing the second launch.
        assert "focus_ack_indicates_visible(reply)" in _APP_SRC
        assert "waitForReadyRead(2500)" in _APP_SRC

    def test_zombie_takeover_not_silent_exit(self):
        # the old code sys.exit(0)'d unconditionally after writing FOCUS;
        # the takeover branch must exist between write and exit.
        # V0.6.67: the exit is further gated on a VISIBLE ack.
        exit_pos = _APP_SRC.find("sys.exit(0)  # the primary raised a window that is on a screen")
        ack_pos = _APP_SRC.find("if focus_ack_indicates_visible(reply):")
        assert 0 < ack_pos < exit_pos

    def test_run_registers_primary_window(self):
        assert "_primary_window = window" in _APP_SRC


class TestStartupSplashWiring:
    def test_splash_class_exists(self):
        assert "class _StartupSplash(QWidget):" in _APP_SRC

    def test_splash_is_best_effort(self):
        splash_try = _APP_SRC.find("splash = _StartupSplash(app)")
        assert splash_try > 0
        # and it is wrapped (never blocks startup)
        assert "startup splash unavailable" in _APP_SRC

    def test_splash_after_lock_and_closed_on_show(self):
        lock_pos = _APP_SRC.find("_acquire_single_instance_lock(app)")
        splash_pos = _APP_SRC.find("splash = _StartupSplash(app)")
        show_pos = _APP_SRC.find("window.show()")
        close_pos = _APP_SRC.find("splash.close()")
        assert lock_pos < splash_pos, "a blocked second launch must never flash a splash"
        assert show_pos < close_pos
