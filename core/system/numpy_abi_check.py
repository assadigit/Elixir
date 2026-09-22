"""numpy 2.x ABI compatibility probe (V0.4.4 intro, V0.4.20 hardened).

The V0.4.19 campaign extracted this VERBATIM from main.py (which was past
its <320-line pin). V0.4.20 fixes the probe's blind spot that let a real
user crash through: the V0.4.4 probe list (numpy / pypdf / pdfplumber /
PIL) contained NO module with compiled numpy code, so the guard could
never fire — the actual culprits (torch / pandas / onnxruntime / scipy /
cv2) imported lazily in OCR/TTS workers and crashed the app later.

The V0.4.20 probe list covers the compiled numpy consumers that can
appear in an Elixir install:

  torch          vision OCR stack / TTS / transcribe (extras) — imported
                 EARLY by main.py (V11.48.0 CUDA-DLL fix), so this import
                 hits sys.modules and is effectively free in the healthy
                 case; in the broken case the early import failed, Python
                 removed the half-initialised module, and this retry raises
                 the ABI error — exactly what we want to catch.
  pandas         markitdown[all] closure (core install)
  onnxruntime    markitdown[all] closure (rapidocr vision models)
  scipy          [tts] extra
  cv2            optional vision installs

Each candidate is pre-checked with importlib.util.find_spec so absent
modules skip instantly, and the marker match is broadened beyond the
exact V0.4.4 RuntimeError string to the other shapes numpy 1.x/2.x
mismatches take (ImportError/ValueError variants included).
"""

from __future__ import annotations

import sys


def check_numpy_abi_compatibility() -> None:
    """V0.4.4 / V0.4.20: detect numpy 2.x ABI mismatch with compiled deps.

    The user's screenshot (4545.png) showed:
        RuntimeError: module compiled against ABI version 0x1000009
        but this version of numpy is 0x2000000

    This happens when a compiled C extension (torch / transformers /
    pandas / scipy / onnxruntime) was built against numpy 1.x but the
    installed numpy is 2.x. The error fires at import time — deep in
    a signal handler or the settings dialog — and the global
    ``sys.excepthook`` catches it as a generic "Unexpected error",
    which is unhelpful.

    This guard imports numpy + the compiled numpy consumers BEFORE the
    app's main window opens. If the ABI mismatch is detected, it shows a
    focused dialog with the exact fix command (``pip install "numpy<2"``)
    instead of a generic crash report.

    Content-agnostic: the probe is generic — it catches ANY exception
    carrying a known numpy-ABI marker during a controlled import of the
    candidate modules.
    """
    import importlib.util as _ilu
    import traceback as _tb

    # V0.4.20: every known string shape of the numpy 1.x-compiled /
    # numpy 2.x-runtime mismatch (RuntimeError, ImportError, ValueError
    # variants — see numpy's own compatibility errors).
    _ABI_MARKERS = (
        "ABI version",  # classic: RuntimeError from torch et al.
        "compiled using NumPy 1.x",  # numpy 2.x's own ImportError message
        "_ARRAY_API not found",  # numpy 2.x import-time ValueError
        "multiarray failed to import",  # legacy ImportError shape
    )

    def _is_abi_error(e: BaseException) -> bool:
        s = str(e)
        return any(m in s for m in _ABI_MARKERS)

    def _try_import(module_name: str) -> Exception | None:
        try:
            __import__(module_name)
            return None
        except Exception as e:  # noqa: BLE001 — probe, must never raise
            return e if _is_abi_error(e) else None

    # V0.4.20: the compiled numpy consumers that can exist in an Elixir
    # install, in probe order (see module docstring for the why of each).
    # find_spec pre-check: absent modules skip without an import attempt,
    # and a broken install (spec raises) is skipped the same way.
    _candidates = [
        "numpy",  # already imported by the app — free sanity probe
        "torch",
        "pandas",
        "onnxruntime",
        "scipy",
        "cv2",
        # Original V0.4.4 probes kept: cheap (all already imported by
        # main.py's dependency check) and they pin the probe contract.
        "pypdf",
        "pdfplumber",
        "PIL",
    ]
    probes: list[str] = []
    for mod in _candidates:
        try:
            if _ilu.find_spec(mod) is not None:
                probes.append(mod)
        except Exception:  # noqa: BLE001 — find_spec itself broke: skip
            continue

    abi_error: Exception | None = None
    for mod in probes:
        err = _try_import(mod)
        if err is not None:
            abi_error = err
            break

    if abi_error is None:
        return  # no ABI mismatch detected — proceed normally

    err_text = str(abi_error)
    tb_text = "".join(_tb.format_exception(type(abi_error), abi_error, abi_error.__traceback__))

    print("\n" + "=" * 60)
    print("STARTUP ERROR — numpy 2.x ABI mismatch:")
    print(f"  {err_text}")
    print("=" * 60 + "\n")

    # Show a focused dialog with the exact fix.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        msg = (
            "Elixir detected a numpy 2.x ABI incompatibility with one of\n"
            "its compiled dependencies (torch, pandas, onnxruntime, or\n"
            "scipy). This happens when numpy was upgraded to 2.x but a\n"
            "compiled module was built against numpy 1.x.\n\n"
            f"Error:\n  {err_text}\n\n"
            "Fix: open a terminal and run:\n"
            '  pip install "numpy<2"\n\n'
            "IMPORTANT: if you installed with requirements.lock, note that\n"
            "older lock files pinned numpy 2.x — re-install with\n"
            "  pip install -r requirements.txt\n"
            "or update your lock file (V0.4.20+ pins numpy 1.26.4).\n\n"
            "Then restart Elixir.\n\n"
            "See V0.4.4 / V0.4.20 CHANGELOG for details."
        )
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("numpy 2.x ABI mismatch — fix required")
        box.setText(msg)
        box.setDetailedText(tb_text)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
    except Exception as _e:
        import logging

        logging.getLogger(__name__).debug("numpy ABI dialog failed: %s: %s", type(_e).__name__, _e)

    sys.exit(1)
