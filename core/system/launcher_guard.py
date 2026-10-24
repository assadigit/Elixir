"""V0.6.65: launcher guard — crash visibility for the pre-window startup path.

WHY THIS MODULE EXISTS
======================
Field report (V0.6.64, first real-machine install of Elixir-Setup-0.6.64.exe):
"I've installed the app … it doesn't open at all."  The Windows build is a
WINDOWED PyInstaller onedir bundle (``console=False``), so every failure
before the main window exists is INVISIBLE — no console, no dialog, no trace
the user can see or report.  The CI launch test (a real window check) was
green on a clean runner, so the failure was machine-specific — and the app
had no way to tell the user WHAT failed on THEIR machine.

The gaps this module closes (evidence → fix, Rule-2 sized):

  1. An import-time / early-startup exception escaping before
     ``main.py``'s ``_install_excepthook()`` runs (notably the very first
     ``from utils.settings import user_data_dir`` and the whole torch-probe
     block) killed the process with zero evidence → ``install()`` arms a
     ``sys.excepthook`` at the TOP of ``main.py``, before every other
     project import: the traceback lands in ``startup_crash.log`` plus a
     Qt-free native Win32 error box (``MessageBoxTimeoutW`` — works before
     QApplication, needs no plugins, auto-closes after 90 s so unattended
     CI sessions never hang on it).
  2. "Nothing happens at all" with NO log files at all is the classic
     antivirus signature on unsigned PyInstaller bundles (files stripped
     from the installed folder).  The one such failure Python can detect
     pre-emptively is a missing Qt Windows platform plugin →
     :func:`precheck_qt_platform_plugin` verifies ``qwindows.dll`` exists
     in the bundle BEFORE QApplication is created (a missing plugin is a
     hard ``qFatal`` abort — uncatchable in Python, so pre-checking is the
     only way to turn it into a message a user can act on).
  3. "Doesn't open" with no timeline → ``startup.log`` records every
     startup step with timestamps, so any future first-launch report ends
     at the step that died (and support can read the whole journey).

CONTRACT (mirrors ``core/system/crash_visibility.py``): STDLIB-ONLY at
import time (pinned mechanically by test_v0665_launcher_guard), ZERO side
effects on import (files open only inside :func:`install` /
:func:`report_fatal`), and every entry point is best-effort — nothing here
may ever raise or block startup.  Write locations follow the frozen-aware
rule: ``%LOCALAPPDATA%\\\\Elixir`` when frozen on Windows, else the
historical ``~/.elixir``.
"""

from __future__ import annotations

import datetime
import os
import sys
import traceback
from pathlib import Path

APP_NAME = "Elixir"
STARTUP_LOG_NAME = "startup.log"
CRASH_LOG_NAME = "startup_crash.log"

# Beside-exe copy of the crash report: the per-user install folder
# (%LOCALAPPDATA%\\Programs\\Elixir) is user-writable, so a report sitting
# next to Elixir.exe is the easiest thing in the world for a non-technical
# user to find and attach.
BESIDE_EXE_CRASH_NAME = "Elixir-startup-crash.txt"

_ROTATE_MAX_BYTES = 256 * 1024  # startup.log rotates once past 256 KiB

# Module state. install() opens the startup.log handle (process lifetime);
# _prev_hook remembers the excepthook we replaced so the chain survives.
_fh = None
_prev_hook = None
_installed = False
_last_step_ts: list[datetime.datetime | None] = [None]


def _user_data_dir() -> Path:
    """PACKAGING: %LOCALAPPDATA%\\Elixir when frozen on Windows, else
    ~/.elixir. Inlined on purpose — this module must stay stdlib-only and
    importable before ANY project import (same contract as
    crash_visibility._user_data_dir, which it mirrors)."""
    if getattr(sys, "frozen", False) and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    return Path.home() / ".elixir"


def _rotate_if_large(path: Path, max_bytes: int = _ROTATE_MAX_BYTES) -> None:
    """Single-generation rotation for the append-only startup logs.

    Same best-effort contract as ``crash_visibility.rotate_log_if_large``
    (inlined here so this module needs zero project imports). NEVER raises.
    """
    try:
        if path.stat().st_size > max_bytes:
            os.replace(path, path.with_suffix(path.suffix + ".old"))
    except Exception:
        pass


def _stamp(dt: datetime.datetime | None = None) -> str:
    now = dt or datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _env_summary() -> str:
    """One block of machine context for the crash report (plain words)."""
    lines = [
        f"python: {sys.version.split()[0]}",
        f"argv: {sys.argv[:4] if sys.argv else '(none)'}",
        f"frozen: {bool(getattr(sys, 'frozen', False))}",
        f"os: {os.name}",
    ]
    try:  # Windows-only API — absent elsewhere
        lines.append(f"windows: {sys.getwindowsversion()}")  # type: ignore[attr-defined]
    except Exception:
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        lines.append(f"bundle: {meipass}")
    return "\n".join(lines)


# ── Public: install + step log ──────────────────────────────────────────────


def install(startup_log: Path | None = None) -> bool:
    """Arm the guard: open ``startup.log`` and install the crash hook.

    Called as the FIRST statement of ``main.py`` (before every other
    project import).  Returns True when armed; on any failure the app boots
    exactly as it did before this module existed (guard-less, never
    blocked).  Re-installing (e.g. a test re-importing main) is a no-op.
    """
    global _fh, _prev_hook, _installed
    if _installed:
        return True
    try:
        path = startup_log if startup_log is not None else _user_data_dir() / STARTUP_LOG_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_large(path)
        _fh = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 — deliberate process-lifetime handle
        _fh.write(
            f"\n{'=' * 60}\n[{_stamp()}] Elixir startup "
            f"(pid={os.getpid()}, {os.name})\n{'=' * 60}\n"
        )
        _fh.write(f"[{_stamp()}] {STARTUP_LOG_NAME} opened — guard armed\n")
        _fh.flush()
        _prev_hook = sys.excepthook
        sys.excepthook = _guard_hook
        _installed = True
        return True
    except Exception:
        _fh = None
        return False


def startup_step(name: str) -> None:
    """Append one timestamped startup step to ``startup.log``.

    Each line also carries the milliseconds elapsed since the previous
    step, so a report shows not just WHERE startup died but where it got
    SLOW. Best-effort: a silent no-op before install() or after any I/O
    failure — step logging must never break the startup it observes.
    """
    try:
        if _fh is None:
            return
        now = datetime.datetime.now()
        prev = _last_step_ts[0]
        elapsed = "" if prev is None else f" (+{round((now - prev).total_seconds() * 1000)} ms)"
        _fh.write(f"[{_stamp(now)}] {name}{elapsed}\n")
        _fh.flush()
        _last_step_ts[0] = now
    except Exception:
        pass


# ── Crash reporting (file + Qt-free native error box) ───────────────────────


def report_fatal(tb_text: str, log_dir: Path | None = None) -> Path | None:
    """Persist a fatal-startup report and return its path.

    Writes ``startup_crash.log`` into the user-data dir (or ``log_dir`` for
    tests) and, when frozen, a copy named :data:`BESIDE_EXE_CRASH_NAME`
    next to the executable. NEVER raises; returns None when nothing could
    be written (disk full / permissions — the native box still tries).
    """
    out: Path | None = None
    try:
        target_dir = log_dir if log_dir is not None else _user_data_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        out = target_dir / CRASH_LOG_NAME
        _rotate_if_large(out)
        with open(out, "a", encoding="utf-8") as f:
            f.write(
                f"\n{'=' * 60}\n[{_stamp()}] STARTUP FAILURE\n{'=' * 60}\n"
                f"{tb_text}\n---- environment ----\n{_env_summary()}\n"
            )
    except Exception:
        out = None
    try:
        if getattr(sys, "frozen", False) and sys.executable:
            beside = Path(sys.executable).resolve().parent / BESIDE_EXE_CRASH_NAME
            beside.write_text(tb_text, encoding="utf-8", errors="replace")
    except Exception:
        pass
    return out


def compose_error_text(tb_text: str, crash_path: Path | None) -> str:
    """The user-facing box text: the LAST error line plus where the full
    report lives. Plain words — the audience is a non-technical user."""
    last = ""
    for line in reversed(tb_text.strip().splitlines()):
        line = line.strip()
        if line and not line.startswith(" "):
            last = line
            break
    if not last:
        last = tb_text.strip().splitlines()[-1] if tb_text.strip() else "(no details)"
    where = f"\n\nA full report was saved here:\n{crash_path}" if crash_path else ""
    return (
        "Elixir could not start on this computer.\n\n"
        f"{last[:400]}\n"
        f"{where}\n\n"
        "If this keeps happening, please send that report file to the "
        "developer (or post it in the repository issue tracker)."
    )


def _native_error_box(text: str, title: str = "Elixir — startup problem") -> None:
    """Show a Qt-free Windows message box (or print to stderr elsewhere).

    ``MessageBoxTimeoutW`` is used with a 90-second auto-close so an
    unattended session (CI launch test, scheduled task) can never hang on
    the dialog; the plain ``MessageBoxW`` is the fallback for exotic
    setups missing the timeout export. NEVER raises.
    """
    if os.name != "nt":
        try:
            print(f"\n{'=' * 60}\n{title}\n{text}\n{'=' * 60}\n", file=sys.stderr)
        except Exception:
            pass
        return
    try:
        import ctypes

        flags = 0x0 | 0x10 | 0x10000 | 0x40000  # OK | ICONERROR | SETFOREGROUND | TOPMOST
        try:
            ctypes.windll.user32.MessageBoxTimeoutW(0, text, title, flags, 0, 90_000)
        except Exception:
            ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        pass


def _guard_hook(exc_type, exc_value, exc_tb) -> None:
    """Replacement ``sys.excepthook`` — the guard's crash path.

    Any uncaught exception before ``main.py``'s richer
    ``_install_excepthook()`` takes over (import-time deaths, the whole
    pre-QApplication startup) lands here: full traceback to
    ``startup_crash.log``, native box with the plain-words summary, then
    the chain continues to the hook we replaced (a no-op print in a
    windowed build). NEVER raises.
    """
    try:
        if isinstance(exc_value, KeyboardInterrupt) or (
            isinstance(exc_type, type) and issubclass(exc_type, KeyboardInterrupt)
        ):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        except Exception:
            tb_text = f"{exc_type}: {exc_value}\n(no traceback available)\n"
        crash_path = report_fatal(tb_text)
        _native_error_box(compose_error_text(tb_text, crash_path))
    except Exception:
        pass  # a crash handler that crashes helps no one
    try:
        hook = _prev_hook if _prev_hook is not None else sys.__excepthook__
        hook(exc_type, exc_value, exc_tb)
    except Exception:
        pass


# ── Qt platform-plugin precheck (the AV-stripped-bundle detector) ───────────


_PLUGIN_CANDIDATES = (
    "PySide6/plugins/platforms/qwindows.dll",  # PyInstaller 6 one-dir layout
    "plugins/platforms/qwindows.dll",  # older hook layouts
    "PySide6/Qt/plugins/platforms/qwindows.dll",  # wheel-shaped layout
    "platforms/qwindows.dll",  # QT_PLUGIN_PATH-style flat layout
)


def _find_qwindows_dll(mepass: Path) -> Path | None:
    """Locate the Qt Windows platform plugin inside the bundle (or None).

    Direct candidates first (O(1)); a depth- and visit-capped walk as the
    fallback so an unexpected layout is still found, while a huge bundle
    can never make this precheck slow. Pure path logic — testable on any
    OS.
    """
    for rel in _PLUGIN_CANDIDATES:
        cand = mepass / rel
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    try:
        base_depth = len(mepass.resolve().parts)
        visited = 0
        for root, dirs, files in os.walk(mepass):
            if len(Path(root).parts) - base_depth > 4:
                dirs[:] = []
                continue
            visited += 1
            if visited > 1500:
                break
            if any(f.lower() == "qwindows.dll" for f in files):
                return Path(root) / "qwindows.dll"
    except Exception:
        return None
    return None


def _precheck_frozen(mepass: Path) -> bool:
    """The frozen-Windows core of the precheck (testable on any OS)."""
    found = _find_qwindows_dll(mepass)
    if found is not None:
        startup_step(f"qt platform plugin ok: {found}")
        return True
    message = (
        "Elixir cannot start because a required file is missing from its "
        "install folder:\n\n"
        "    qwindows.dll (the Qt Windows plugin)\n\n"
        "The most common cause on a fresh install is antivirus software "
        "removing files from unsigned applications. To fix:\n"
        "  1. Open your antivirus (Windows Security → Virus & threat "
        "protection → Protection history).\n"
        "  2. If Elixir files were quarantined, restore them and add the "
        "Elixir install folder to the allowed list.\n"
        "  3. Reinstall Elixir if files were deleted.\n"
        "The install folder is shown in the report below."
    )
    crash_path = report_fatal(
        message + f"\n\nbundle folder: {mepass}\n---- environment ----\n{_env_summary()}"
    )
    _native_error_box(compose_error_text(message, crash_path))
    return False


def precheck_qt_platform_plugin() -> bool:
    """Before QApplication: verify the Qt Windows platform plugin exists.

    A missing ``qwindows.dll`` is a hard ``qFatal`` abort inside Qt —
    uncatchable from Python and completely silent in a windowed build.
    Checking first turns it into an actionable message (see
    :func:`_precheck_frozen`). Skipped (returns True) when running from
    source or on non-Windows — this only guards frozen Windows installs.
    """
    try:
        if not getattr(sys, "frozen", False) or os.name != "nt":
            return True
        mepass = getattr(sys, "_MEIPASS", None)
        if not mepass:
            startup_step("qt platform plugin: bundle path unknown — precheck skipped")
            return True
        return _precheck_frozen(Path(mepass))
    except Exception:
        # The precheck itself must never block startup — a false negative
        # is annoying, a broken launcher is fatal.
        return True


__all__ = [
    "install",
    "startup_step",
    "report_fatal",
    "compose_error_text",
    "precheck_qt_platform_plugin",
    "STARTUP_LOG_NAME",
    "CRASH_LOG_NAME",
    "BESIDE_EXE_CRASH_NAME",
]
