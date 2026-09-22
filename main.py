#!/usr/bin/env python3

import logging

logger = logging.getLogger(__name__)
"""Elixir — entry point.

Launches the PySide6 UI (``ui_qt``).

Run::

    python main.py
"""

import os
import shutil
import sys
from pathlib import Path as _P  # V18.2.22: module-level for Bootstrap call

from utils.settings import (
    user_data_dir,  # V18.20.4.11 rebrand: migrates the legacy user dir → ~/.elixir
)

# V18.2.37 (CRITICAL fix): ensure new .py files are loaded, not stale .pyc.
# On Windows, deleting __pycache__ while the process is running can crash
# (PermissionError on locked .pyc files). Instead of deleting, we:
# 1. Set PYTHONDONTWRITEBYTECODE so Python won't create NEW .pyc files
# 2. Delete __pycache__ with ignore_errors=True (best-effort, never crashes)
# 3. If deletion fails (locked files), Python will still load the .py
#    because we also check the .py mtime vs .pyc mtime
#
# The V18.2.36 conversion log proved stale .pyc was the root cause: the
# V18.2.35 lazy-load fix and V18.2.36 CPU-force fix were in the .py files
# but NOT in the .pyc cache — Python loaded the old .pyc and the fixes
# silently didn't fire.
_APP_DIR = _P(__file__).resolve().parent

# Set this BEFORE any imports so Python doesn't write new .pyc files
# that could be stale. This ensures every import recompiles from .py.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# Best-effort pycache cleanup — never crashes (ignore_errors=True + try/except)
_pycache_deleted = 0
try:
    for _pc in _APP_DIR.rglob("__pycache__"):
        try:
            shutil.rmtree(_pc, ignore_errors=True)
            _pycache_deleted += 1
        except Exception:
            pass
except Exception:
    pass
if _pycache_deleted > 0:
    print(f"[V18.2.37] Deleted {_pycache_deleted} stale __pycache__ directory(ies).")

# V13.33.1 note: PYTHONDONTWRITEBYTECODE above is the whole stale-pyc strategy.

# V5.4.4: Suppress HuggingFace symlink warning on Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# ── V18.20.3.3 (crash fix #5): arm crash visibility BEFORE the torch import ────
# faulthandler + threading.excepthook → native-crash / thread-death evidence in
# ~/.elixir/ (V18.20.3 died with zero trace). Best-effort, never raises.
try:
    from core.system.crash_visibility import arm_crash_visibility, rotate_log_if_large

    arm_crash_visibility()
except Exception as _e:
    print(f"[V18.20.3.3] crash-visibility arm failed: {type(_e).__name__}: {_e}")

# ── V11.48.0: Import torch BEFORE PySide6 ─────────────────────────────────
# CRITICAL FIX: PySide6/Qt loads its own DLLs (Qt6Gui, OpenGL, etc.) which
# can SHADOW torch's CUDA DLLs on Windows. When torch is imported AFTER
# PySide6 + QApplication, torch.cuda.is_available() can return False even
# though the same torch returns True in a clean CLI process.
#
# Importing torch (and probing CUDA) BEFORE any PySide6 import forces
# torch's CUDA DLLs to load first, so Qt's DLLs can't shadow them.
# This is a well-known fix for the "torch works in CLI but not in Qt app"
# problem on Windows.
#
# We also log the probe result to a startup file so we can verify the
# in-app CUDA state.
_TORCH_CUDA_PROBE = {
    "checked": False,
    "available": False,
    "cuda_tag": None,
    "device_name": None,
    "error": None,
}
try:
    import torch as _torch_early

    _TORCH_CUDA_PROBE["checked"] = True
    _TORCH_CUDA_PROBE["cuda_tag"] = getattr(_torch_early.version, "cuda", None)
    _TORCH_CUDA_PROBE["available"] = bool(_torch_early.cuda.is_available())
    if _TORCH_CUDA_PROBE["available"]:
        _TORCH_CUDA_PROBE["device_name"] = _torch_early.cuda.get_device_name(0)
except Exception as _e:
    _TORCH_CUDA_PROBE["error"] = f"{type(_e).__name__}: {_e}"

# Write the probe result to a startup log (best-effort).
try:
    import datetime as _dt

    _probe_log = (
        user_data_dir() / "gpu_probe.log"
    )  # earliest disk touch → runs the rebrand migration
    _probe_log.parent.mkdir(parents=True, exist_ok=True)
    rotate_log_if_large(_probe_log)  # V18.20.4.12 (W-c14): rotate before append — never raises
    with open(_probe_log, "a", encoding="utf-8") as _f:
        _f.write(f"\n{'=' * 60}\n")
        _f.write(f"{_dt.datetime.now().isoformat()}\n")
        _f.write(f"Python: {sys.executable}\n")
        _f.write(f"torch: {getattr(_torch_early, '__version__', 'NOT INSTALLED')}\n")
        _f.write(f"torch.version.cuda: {_TORCH_CUDA_PROBE['cuda_tag']!r}\n")
        _f.write(f"cuda.is_available(): {_TORCH_CUDA_PROBE['available']}\n")
        _f.write(f"device_name: {_TORCH_CUDA_PROBE['device_name']}\n")
        if _TORCH_CUDA_PROBE["error"]:
            _f.write(f"probe_error: {_TORCH_CUDA_PROBE['error']}\n")
        _f.write("(probe ran BEFORE PySide6 import)\n")
except Exception:
    pass


def get_startup_cuda_probe() -> dict:  # Expose the probe for the UI to read.
    """Return the early torch CUDA probe result (run before PySide6)."""
    return dict(_TORCH_CUDA_PROBE)


# V18.20.4.9 (T-b4): the old ``Qt.AA_EnableHighDpiScaling = True`` line here
# was a dead assignment (zero readers) — Qt 6 enables high-DPI scaling
# automatically, so nothing needs to be set before QApplication.
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

# Ensure the project root is on the import path regardless of launch directory.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _check_dependencies() -> list[str]:
    """Return a list of missing critical packages."""
    missing = []
    critical = {
        "PySide6": "PySide6>=6.6",
        "markitdown": "markitdown[all]>=0.1.0",
        "pypdf": "pypdf>=4.3.0",
        "requests": "requests>=2.31.0",
        "PIL": "Pillow>=10.4.0",
        "tiktoken": "tiktoken>=0.7.0",
        "docx": "python-docx>=1.1.0",
    }
    for module, pkg in critical.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    return missing


def _show_missing_deps_error(missing: list[str]) -> None:
    msg = (
        "Elixir could not start because the following\n"
        "Python packages are not installed:\n\n"
        + "\n".join(f"  • {p}" for p in missing)
        + "\n\nFix: open a terminal and run:\n"
        "  pip install -r requirements.txt"
    )
    print("\n" + "=" * 60)
    print("STARTUP ERROR — missing dependencies:")
    print(msg)
    print("=" * 60 + "\n")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        QMessageBox.critical(None, "Missing dependencies", msg)
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
    sys.exit(1)


def _install_excepthook() -> None:
    """Install a global excepthook that catches unhandled exceptions.

    Without this, a crash deep in a signal handler (e.g. the enum-``|``
    RecursionError that crashed the settings gear in V1.2) silently kills
    the app.  With it, the user gets a friendly dialog with the traceback
    so they can report it, and the app stays alive.

    V10.34.0 (Sprint 6.9): Also generates a crash report zip (traceback +
    redacted settings + system info) so the user has a single file to
    attach to a bug report.
    """
    import traceback as _tb

    def _hook(exc_type, exc_value, exc_tb):
        # Ctrl-C / KeyboardInterrupt → let the default handler deal with it
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(_tb.format_exception(exc_type, exc_value, exc_tb))
        # always log to stderr
        print(f"\n{'=' * 60}\nUNHANDLED EXCEPTION:\n{tb_text}{'=' * 60}\n", file=sys.stderr)
        # V10.34.0 (Sprint 6.9): generate a crash report zip (best-effort).
        # V13.29.0 (P3.8): Pass recent log lines so the crash zip includes
        # context from before the crash (was dormant — extra_log_lines never
        # passed, so recent_log.txt was never written).
        _crash_path = None
        try:
            from core.system.crash_report import generate_crash_report

            # V13.29.0: Collect the last 200 lines of system.log
            _extra_lines = None
            try:
                from pathlib import Path as _P

                _log_file = _P.home() / ".elixir" / "system.log"
                if _log_file.exists():
                    # Read last 200 lines efficiently (don't load whole file)
                    with open(_log_file, encoding="utf-8", errors="replace") as _f:
                        from collections import deque

                        _lines = deque(_f, maxlen=200)
                    _extra_lines = list(_lines)
            except Exception as _e:
                logger.debug(
                    "could not read system.log for crash report: %s: %s", type(_e).__name__, _e
                )

            _crash_path = generate_crash_report(
                exc_type,
                exc_value,
                exc_tb,
                extra_log_lines=_extra_lines,
            )
        except Exception as _e:
            logger.debug("crash report generation failed: %s: %s", type(_e).__name__, _e)

        # try to show a friendly dialog (best-effort — never crash here)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            if app is not None:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                # V0.4.4: detect the numpy 2.x ABI mismatch at runtime (it
                # fires lazily when the user opens settings or triggers
                # the OCR module which imports torch). Show a focused
                # fix dialog instead of a generic "Unexpected error".
                _exc_text = str(exc_value)
                if (
                    issubclass(exc_type, RuntimeError)
                    and "ABI version" in _exc_text
                    and "numpy" in _exc_text.lower()
                ):
                    msg.setWindowTitle("numpy 2.x ABI mismatch — fix required")
                    msg.setText(
                        "Elixir hit a numpy 2.x ABI incompatibility with one of\n"
                        "its compiled dependencies (torch, transformers, pandas,\n"
                        "or scipy). This happens when numpy was upgraded to 2.x\n"
                        "but a compiled module was built against numpy 1.x.\n\n"
                        f"Error:\n  {_exc_text}\n\n"
                        "Fix: open a terminal and run:\n"
                        '  pip install "numpy<2"\n\n'
                        "Then restart Elixir.\n\n"
                        "See V0.4.4 CHANGELOG for details."
                    )
                else:
                    msg.setWindowTitle("Unexpected error")
                    crash_info = f"\n\nCrash report saved to:\n{_crash_path}" if _crash_path else ""
                    msg.setText(
                        f"The app hit an unexpected error:\n\n{exc_type.__name__}: {exc_value}"
                        f"{crash_info}"
                    )
                msg.setDetailedText(tb_text)
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    sys.excepthook = _hook


if __name__ == "__main__":
    missing = _check_dependencies()
    if missing:
        _show_missing_deps_error(missing)

    # V0.4.4: numpy 2.x ABI mismatch probe (torch/pandas/onnxruntime/
    # scipy/cv2) — catches every ABI error shape early and shows a
    # machine-specific fix dialog (V0.4.21: failing module(s) + pip
    # names + installed numpy version + tailored fix commands).
    from core.system.numpy_abi_check import check_numpy_abi_compatibility

    check_numpy_abi_compatibility()

    _install_excepthook()

    # V18.2.22 (Phase 2.1): Bootstrap extracted from inline to
    # core.system.bootstrap.Bootstrap — each step is now independently
    # testable. The 90+ lines of pycache cleanup + prompt refresh +
    # settings force-reset + keyring migration now live in clean methods.
    # run() never raises — one failing step doesn't block the others.
    try:
        from core.system.bootstrap import Bootstrap

        Bootstrap(user_data_dir(), app_dir=_P(__file__).resolve().parent).run()
    except Exception as _e:
        logger.debug("bootstrap skipped: %s: %s", type(_e).__name__, _e)

    from ui_qt.app import run

    run()
