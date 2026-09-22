"""numpy 2.x ABI compatibility probe (V0.4.4 intro, V0.4.20 hardened,
V0.4.21 report-tailored).

The V0.4.19 campaign extracted this VERBATIM from main.py (which was
past its <320-line pin). V0.4.20 fixed the probe's blind spot that let
a real user crash through: the V0.4.4 probe list (numpy / pypdf /
pdfplumber / PIL) contained NO module with compiled numpy code, so the
guard could never fire — the actual culprits (torch / pandas /
onnxruntime / scipy / cv2) imported lazily in OCR/TTS workers and
crashed the app later.

V0.4.21 tailors the report to the machine that actually broke, based on
the first V0.4.20 field report: the user's cv2 raised the legacy
``ImportError: numpy.core.multiarray failed to import`` (an
opencv-python build compiled against the numpy 1.x ABI, with numpy 2.x
installed by mistake — the user confirmed the wrong numpy). The
V0.4.20 fix dialog (a) enumerated four modules that had NOT failed
while never naming cv2, (b) did not show which numpy was actually
installed, and (c) offered only the numpy-downgrade fix. The V0.4.21
report names exactly the failing module(s) with their pip package
names, shows the installed numpy version, and gives both fix paths
tailored to the actual mismatch direction.

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
  cv2            markitdown[all] → rapidocr vision chain; its pip package
                 name is opencv-python, which the fix commands must say

Each candidate is pre-checked with importlib.util.find_spec so absent
modules skip instantly, and the marker match is broadened beyond the
exact V0.4.4 RuntimeError string to the other shapes numpy 1.x/2.x
mismatches take (ImportError/ValueError variants included).
"""

from __future__ import annotations

import sys
from typing import NamedTuple

# V0.4.21: import name → pip package name, for every probed module whose
# pip name differs from its import name (fix commands must be
# copy-pasteable — "pip install cv2" would install the wrong thing).
_PIP_NAMES: dict[str, str] = {
    "cv2": "opencv-python",
}


class _AbiReport(NamedTuple):
    """V0.4.21: the startup-error report for a detected ABI mismatch."""

    title: str
    message: str
    details: str
    console: list[str]


def _installed_numpy_version() -> str:
    """V0.4.21: best-effort read of the installed numpy version.

    Used to tailor the fix advice to the actual mismatch direction
    (numpy 2.x installed → restoring numpy 1.26.4 is the primary fix;
    a module built against a different numpy → upgrading that module
    is). Never raises: an unreadable version degrades to "unknown" and
    the report shows both fix paths.
    """
    try:
        mod = sys.modules.get("numpy") or __import__("numpy")
        return str(getattr(mod, "__version__", "unknown"))
    except Exception:  # noqa: BLE001 — diagnostic, must never raise
        return "unknown"


def _build_abi_error_report(
    failures: list[tuple[str, Exception]],
    numpy_version: str,
) -> _AbiReport:
    """V0.4.21: build the (title, message, details, console) startup-error
    report for a detected ABI mismatch — a pure function so the dialog
    content is unit-testable without Qt.

    ``failures``: (module_name, exception) for EVERY probed module whose
    import raised a numpy-ABI marker — all of them, not just the first:
    the report must name everything that is broken on this machine.
    """
    import traceback as _tb

    numpy_is_2 = numpy_version.split(".", 1)[0] == "2"
    upgrade_pkgs = (
        " ".join(sorted({_PIP_NAMES.get(mod, mod) for mod, _err in failures if mod != "numpy"}))
        or "numpy"
    )

    failing_lines = "\n".join(f"  {mod}: {err}" for mod, err in failures)
    failing_names = ", ".join(mod for mod, _err in failures)

    if numpy_is_2:
        direction = (
            f"numpy {numpy_version} is a 2.x release, but the failing module(s) "
            "above were built against the numpy 1.x ABI — exactly the mismatch "
            "Elixir's numpy<2 pin (requirements.txt) protects against."
        )
        fix_a_label = "[A] Restore the numpy Elixir is built for (recommended):"
        fix_a_cmd = 'python -m pip install --force-reinstall "numpy==1.26.4"'
        fix_b_label = "[B] Or upgrade the failing module(s) to numpy 2.x-compatible builds:"
        fix_b_cmd = f"python -m pip install --upgrade {upgrade_pkgs}"
        fix_b_note = "    (Elixir itself is tested with numpy 1.26.x)"
        header = f"STARTUP ERROR — numpy 2.x ABI mismatch (numpy {numpy_version} installed):"
    else:
        direction = (
            f"numpy {numpy_version} is installed, but the failing module(s) above "
            "were built against a different numpy ABI than the installed one — "
            "either they target a different numpy, or the install is mixed."
        )
        fix_a_label = "[A] Upgrade the failing module(s) to builds matching the installed numpy:"
        fix_a_cmd = f"python -m pip install --upgrade {upgrade_pkgs}"
        fix_b_label = "[B] Or restore Elixir's tested numpy 1.26.4:"
        fix_b_cmd = 'python -m pip install --force-reinstall "numpy==1.26.4"'
        fix_b_note = "    (use this if those modules target the numpy 1.x ABI)"
        header = f"STARTUP ERROR — numpy ABI mismatch (numpy {numpy_version} installed):"

    title = "numpy ABI mismatch — fix required"
    message = (
        "Elixir detected a numpy ABI incompatibility in your Python "
        f"environment — failing module(s): {failing_names} — and cannot "
        "start safely.\n\n"
        f"Import error(s):\n{failing_lines}\n\n"
        f"Installed numpy: {numpy_version} "
        "(Elixir requires numpy>=1.26.0,<2.0.0)\n\n"
        f"{direction}\n\n"
        "Fix — open a terminal and run ONE of:\n"
        f"  {fix_a_label}\n"
        f"      {fix_a_cmd}\n"
        f"  {fix_b_label}\n"
        f"      {fix_b_cmd}\n"
        f"{fix_b_note}\n\n"
        "IMPORTANT: if you installed with requirements.lock, note that\n"
        "older lock files pinned numpy 2.x — re-install with\n"
        "  pip install -r requirements.txt\n"
        "or update your lock file (V0.4.20+ pins numpy 1.26.4).\n\n"
        "Then restart Elixir.\n\n"
        "See the V0.4.4 / V0.4.20 / V0.4.21 CHANGELOG entries for details."
    )
    details = "\n\n".join(
        f"--- {mod} ---\n" + "".join(_tb.format_exception(type(err), err, err.__traceback__))
        for mod, err in failures
    )
    console = [
        header,
        *(f"  {mod}: {err}" for mod, err in failures),
        f"  fix: {fix_a_cmd}",
        f"  (alternative: {fix_b_cmd})",
    ]
    return _AbiReport(title, message, details, console)


def check_numpy_abi_compatibility() -> None:
    """V0.4.4 / V0.4.20 / V0.4.21: detect numpy ABI mismatch with
    compiled deps BEFORE the main window opens.

    The V0.4.4 user screenshot showed:
        RuntimeError: module compiled against ABI version 0x1000009
        but this version of numpy is 0x2000000

    and the V0.4.20 field report showed the legacy shape:
        ImportError: numpy.core.multiarray failed to import   (cv2)

    Both happen when a compiled C extension (torch / pandas /
    onnxruntime / scipy / cv2) was built against a different numpy ABI
    than the installed numpy. The error fires at import time — deep in
    a worker — and the global ``sys.excepthook`` would catch it as a
    generic "Unexpected error", which is unhelpful. This guard imports
    numpy + the compiled numpy consumers up front; on mismatch it shows
    a focused, machine-specific report (failing modules, installed
    numpy version, tailored fix commands) instead of a generic crash.

    Content-agnostic: the probe is generic — it catches ANY exception
    carrying a known numpy-ABI marker during a controlled import of the
    candidate modules.
    """
    import importlib.util as _ilu

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

    # V0.4.21: collect EVERY ABI failure instead of stopping at the
    # first — the report must name all modules broken on this machine
    # (the V0.4.20 dialog could not even name the one that failed).
    failures: list[tuple[str, Exception]] = []
    for mod in probes:
        err = _try_import(mod)
        if err is not None:
            failures.append((mod, err))

    if not failures:
        return  # no ABI mismatch detected — proceed normally

    report = _build_abi_error_report(failures, _installed_numpy_version())

    print("\n" + "=" * 60)
    for line in report.console:
        print(line)
    print("=" * 60 + "\n")

    # Show a focused dialog with the machine-specific fix.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(report.title)
        box.setText(report.message)
        box.setDetailedText(report.details)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
    except Exception as _e:
        import logging

        logging.getLogger(__name__).debug("numpy ABI dialog failed: %s: %s", type(_e).__name__, _e)

    sys.exit(1)
