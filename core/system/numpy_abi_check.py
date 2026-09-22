"""V0.4.19: numpy 2.x ABI compatibility probe — extracted VERBATIM from main.py.

The V0.4.4 fix inlined ~90 lines into main.py, which pushed main.py past its
<320-line pin (tests/test_bootstrap.py::TestMainPyIntegration::test_main_py_shorter
and tests/test_v1820412_a_system_robustness.py::TestRotationSourcePins::test_main_py_still_under_260_lines).
The body below is byte-identical to the original main.py implementation —
behavior unchanged, only the address changed.
"""

from __future__ import annotations

import sys


def check_numpy_abi_compatibility() -> None:
    """V0.4.4: detect numpy 2.x ABI mismatch with compiled deps.

    The user's screenshot (4545.png) showed:
        RuntimeError: module compiled against ABI version 0x1000009
        but this version of numpy is 0x2000000

    This happens when a compiled C extension (torch / transformers /
    pandas / scipy / langextract) was built against numpy 1.x but the
    installed numpy is 2.x. The error fires at import time — deep in
    a signal handler or the settings dialog — and the global
    ``sys.excepthook`` catches it as a generic "Unexpected error",
    which is unhelpful.

    This guard imports numpy + pypdf + a few other critical deps and
    probes for the ABI error BEFORE the app's main window opens. If the
    ABI mismatch is detected, it shows a focused dialog with the exact
    fix command (``pip install "numpy<2"``) instead of a generic crash
    report.

    Content-agnostic: the probe is generic — it catches ANY
    ``RuntimeError`` containing "ABI version" during a controlled
    import of known-numpy-dependent modules.
    """
    import traceback as _tb

    def _try_import(module_name: str) -> Exception | None:
        try:
            __import__(module_name)
            return None
        except RuntimeError as e:
            if "ABI version" in str(e):
                return e
            return None  # unrelated RuntimeError — not our concern
        except Exception:
            return None  # import errors are handled by _check_dependencies

    # Probe the most common numpy-dependent compiled modules. The order
    # matters: torch/transformers are the most common culprits; pypdf
    # and pdfplumber use numpy indirectly.
    probes = ["numpy", "pypdf", "pdfplumber", "PIL"]
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
            "its compiled dependencies (torch, transformers, pandas, or\n"
            "scipy). This happens when numpy was upgraded to 2.x but a\n"
            "compiled module was built against numpy 1.x.\n\n"
            f"Error:\n  {err_text}\n\n"
            "Fix: open a terminal and run:\n"
            '  pip install "numpy<2"\n\n'
            "Then restart Elixir.\n\n"
            "See V0.4.4 CHANGELOG for details."
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
