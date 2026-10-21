"""V18.20.3.3: Crash visibility — faulthandler + threading.excepthook.

WHY THIS MODULE EXISTS
======================
The V18.20.3 startup crash left exactly ONE line in the conversion log and
zero other evidence.  Three distinct silent-death paths were open:

  (a) A ``SystemExit`` (or any ``BaseException`` that is not an
      ``Exception``) escaping a dependency's import code slipped past both
      ``except Exception`` handlers in the startup path — the worker thread
      died with no dialog, no log line, nothing, and the wizard stayed
      stuck on "Starting conversion…" forever.

  (b) A NATIVE crash (DLL load failure / access violation in a C
      extension) kills the process with zero Python-level trace — unless a
      ``faulthandler`` was armed BEFORE the offending import, nothing is
      written anywhere by Python.

  (c) Fatal errors raised in *background* threads (thermal monitor,
      hardware monitor, embedding workers) were printed to stderr at best
      — invisible when the app was launched from a GUI shortcut.

This module closes (b) and (c) process-wide, at the earliest possible
moment: ``main.py`` arms it BEFORE the first heavy import (torch), so a
native crash anywhere in the startup path still dumps the faulting
thread's stack to disk.  Path (a) is closed at the two escape sites
themselves (``preflight_check._is_importable`` and
``controller._run_conversion`` now catch ``BaseException`` — crash fixes
#3 and #4).

ARMED ARTIFACTS
===============
  - ``~/.elixir/faulthandler.log``  — native-crash dumps (all
    threads' stacks) for SIGSEGV / SIGABRT / SIGFPE / stack overflow /
    Windows access violations, plus a startup header per run so runs are
    easy to tell apart.
  - ``~/.elixir/thread_crash.log``  — one block per background
    thread death: timestamp, thread name, exception type, full traceback.
    The default stderr print is preserved on top (console launches look
    unchanged).

Both files are append-only and best-effort — arming must NEVER raise and
NEVER block startup.  This module is therefore stdlib-only (no PySide6,
no torch, no numpy, no project imports) so it can be imported before
anything else in ``main.py``.
"""

from __future__ import annotations

import datetime
import faulthandler
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any


# V0.6.63: stdlib-only user-data root — crash modules must not import app
# code (TestCrashVisibilityStdlibOnly pins it; the arm runs before any
# heavy import). Mirrors app_paths: frozen → %LOCALAPPDATA%\Elixir,
# source → ~/.elixir.
def _user_data_root() -> Path:
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "Elixir"
    return Path.home() / ".elixir"


_HOME_DIR = _user_data_root()
FAULTHANDLER_LOG = _HOME_DIR / "faulthandler.log"
THREAD_CRASH_LOG = _HOME_DIR / "thread_crash.log"

# Module-level reference to the open faulthandler file handle.  It MUST stay
# alive for the whole process — if it were garbage-collected, faulthandler
# would try to write into a closed file at fault time.
_fh_file = None

_armed_status: dict = {"faulthandler": False, "thread_excepthook": False}


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── V18.20.4.12 (W-c14): append-only log rotation ──────────────────────────


def rotate_log_if_large(path: Path, max_bytes: int = 1_048_576) -> None:
    """Rotate an append-only diagnostic log once it grows past ``max_bytes``.

    V18.20.4.12 (W-c14): the crash-path logs (``faulthandler.log``,
    ``thread_crash.log`` — and ``main.py``'s ``gpu_probe.log``, which
    imports this helper) are opened in append mode on every launch /
    every background-thread death and were NEVER rotated, so they grow
    without bound for the lifetime of the install.  Call this immediately
    before opening a log for append: when the existing file exceeds
    ``max_bytes`` it is renamed to ``<name><suffix>.old`` (single
    generation — the previous ``.old`` copy is replaced on each
    rotation), so the fresh append starts from a small file while the
    most recent megabyte of crash evidence survives.

    NEVER raises — same best-effort contract as the rest of this module:
    these are crash-path logs, so rotation must not be able to break the
    crash handler or boot.  Stdlib-only (``os`` + ``pathlib``), like the
    rest of the module.
    """
    try:
        if path.stat().st_size > max_bytes:
            os.replace(path, path.with_suffix(path.suffix + ".old"))
    except Exception:
        # Missing file, unreadable, or a race with another writer — all
        # fine: the caller just opens the log in append mode as usual.
        pass


# ── Layer 1: faulthandler (native crashes) ─────────────────────────────────


def arm_faulthandler(log_path: Path = FAULTHANDLER_LOG) -> bool:
    """Arm ``faulthandler`` to dump native-crash stacks to ``log_path``.

    Catches fatal signals (SIGSEGV, SIGABRT, SIGFPE, bus error, illegal
    instruction, stack overflow) and — on Windows — fatal structured
    exceptions like access violations and DLL load failures, then dumps
    ALL threads' Python stacks to the file before the process dies.

    Returns ``True`` when the file-backed handler is armed, ``False``
    (never raises) when it isn't.  On failure it still tries the
    stderr-only fallback so native faults at least reach the console.
    """
    global _fh_file
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # V18.20.4.12 (W-c14): rotate the append-only crash log before open.
        rotate_log_if_large(log_path)
        _fh_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — deliberate process-lifetime handle for faulthandler
        _fh_file.write(
            f"\n{'=' * 60}\n"
            f"[{_stamp()}] faulthandler armed "
            f"(pid={os.getpid()}, python={sys.version.split()[0]}, "
            f"argv0={sys.argv[0] if sys.argv else '?'})\n"
            f"{'=' * 60}\n"
        )
        _fh_file.flush()
        faulthandler.enable(file=_fh_file, all_threads=True)
        return True
    except Exception:
        # Best-effort: a failed arm must never block startup.  Fall back to
        # the stderr-only handler so native faults still hit the console.
        try:
            faulthandler.enable(all_threads=True)
        except Exception:
            pass
        return False


# ── Layer 2: threading.excepthook (background-thread deaths) ───────────────


def _format_thread_death(args: Any) -> str:
    """Format a ``threading.ExceptHookArgs`` into a readable evidence block."""
    try:
        thread = getattr(args, "thread", None)
        thread_name = getattr(thread, "name", "<unknown>") if thread else "<unknown>"
    except Exception:
        thread_name = "<unknown>"
    try:
        tb_text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
    except Exception:
        tb_text = f"{args.exc_type}: {args.exc_value}\n(no traceback available)\n"
    return (
        f"\n{'=' * 60}\n[{_stamp()}] BACKGROUND THREAD DIED: {thread_name}\n{tb_text}{'=' * 60}\n"
    )


def _thread_excepthook(args: Any) -> None:
    """Replacement ``threading.excepthook`` — leaves evidence for thread deaths.

    Python 3.8+ invokes this for EVERY unhandled exception (including
    ``SystemExit`` and ``KeyboardInterrupt``) in ANY non-main thread — the
    thermal monitor, the hardware monitor, the embedding workers, the
    conversion worker itself.  Without it those deaths were invisible when
    the app was launched without a console.

    Preserves the default stderr print, then appends a block to
    ``~/.elixir/thread_crash.log``.  Never raises.
    """
    # 1. Preserve the default behaviour (formatted print to stderr).
    try:
        threading.__excepthook__(args)
    except Exception:
        try:
            sys.stderr.write(_format_thread_death(args))
            sys.stderr.flush()
        except Exception:
            pass
    # 2. Persist to the crash log file.
    try:
        THREAD_CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
        # V18.20.4.12 (W-c14): rotate the append-only crash log before open.
        rotate_log_if_large(THREAD_CRASH_LOG)
        with open(THREAD_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(_format_thread_death(args))
    except Exception:
        # Nowhere left to report — swallow.  Visibility is best-effort.
        pass


def arm_thread_excepthook() -> bool:
    """Install the global ``threading.excepthook`` (covers ALL threads).

    Applies to every thread created after arming (and, since the hook is
    consulted at death time, threads that were already running pick it up
    too).  Returns ``True`` on success — never raises.
    """
    try:
        threading.excepthook = _thread_excepthook
        return True
    except Exception:
        return False


# ── Combined armament ──────────────────────────────────────────────────────


def arm_crash_visibility() -> dict:
    """Arm BOTH crash-visibility layers.  Call as early as possible.

    ``main.py`` calls this BEFORE the first torch import so that a native
    DLL crash during any heavy import (torch / transformers / PySide6 /
    sentence_transformers) still leaves a full faulting-thread stack in
    ``~/.elixir/faulthandler.log``.

    Returns ``{"faulthandler": bool, "thread_excepthook": bool}``.
    """
    _armed_status["faulthandler"] = arm_faulthandler()
    _armed_status["thread_excepthook"] = arm_thread_excepthook()
    return dict(_armed_status)


def is_crash_visibility_armed() -> dict:
    """Read-only accessor (tests, diagnostics, crash-report generator)."""
    return dict(_armed_status)


__all__ = [
    "arm_faulthandler",
    "arm_thread_excepthook",
    "arm_crash_visibility",
    "is_crash_visibility_armed",
    "rotate_log_if_large",
    "FAULTHANDLER_LOG",
    "THREAD_CRASH_LOG",
]
