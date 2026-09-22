"""numpy 2.x ABI compatibility probe (V0.4.4 intro, V0.4.20 hardened,
V0.4.21 report-tailored, V0.4.22 continuance).

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
installed by mistake). The report names exactly the failing module(s)
with their pip package names, shows the installed numpy version, and
gives both fix paths tailored to the actual mismatch direction.

V0.4.22 fixes the lockout exposed by the SECOND field report (same
user, same machine, now on V0.4.21 — screenshot 4343.png: dialog
complete and readable, numpy 2.5.3 shown, yet the user still could not
get past it):

a) the fix commands said ``python -m pip ...`` — on Windows with more
   than one Python installed, bare ``python``/``pip`` frequently
   targets a DIFFERENT interpreter than the one running Elixir, so the
   command "succeeds" and fixes nothing. Commands now embed
   ``sys.executable`` (always quoted) so a copy-paste always targets
   the Python that is actually running Elixir.
b) a broken OPTIONAL module (cv2 feeds only the rapidocr vision-OCR
   chain — Elixir's own code never imports it) hard-blocked the ENTIRE
   app at startup. Only numpy itself is core. Optional-module failures
   now offer "Continue anyway" (default) with a loud warning naming the
   affected features; the console report becomes a STARTUP WARNING and
   the app opens with everything except those features working.
   numpy-itself-broken stays fatal (mixed/corrupt install — exit 1).
c) the message is now compact and fix-first (the user's window is
   816×510): one diagnostic line, then the copy-paste commands, then
   the impact line; tracebacks remain in Show Details.

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

# V0.4.22: which Elixir features each probed module actually feeds —
# only numpy itself is core; everything below is optional, and a broken
# optional module must NOT lock the user out of the whole app.
_FEATURE_IMPACT: dict[str, str] = {
    "torch": "vision OCR / TTS (extras)",
    "pandas": "QuickConvert fallback (markitdown)",
    "onnxruntime": "rapidocr vision OCR",
    "scipy": "TTS (extras)",
    "cv2": "rapidocr vision OCR",
}


class _AbiReport(NamedTuple):
    """V0.4.21/V0.4.22: the startup report for a detected ABI mismatch.

    ``fatal``: True when numpy ITSELF failed (mixed/corrupt numpy
    install — the app cannot run); False when only optional compiled
    modules failed (the app runs minus the features they feed).
    ``continue_warning``: console lines printed when the user chooses
    "Continue anyway" (optional failures only).
    """

    title: str
    message: str
    details: str
    console: list[str]
    fatal: bool
    continue_warning: list[str]


def _installed_numpy_version() -> str:
    """V0.4.21/V0.4.22: best-effort read of the installed numpy version.

    Layer 1: the already-imported (or importable) numpy's __version__.
    Layer 2 (V0.4.22): importlib.metadata — when numpy itself is broken
    and cannot import, the distribution metadata still reports what is
    ACTUALLY installed, which is exactly what a mixed-install diagnosis
    needs. Never raises; degrades to "unknown".
    """
    try:
        mod = sys.modules.get("numpy")
        if mod is None:
            mod = __import__("numpy")
        v = str(getattr(mod, "__version__", ""))
        if v:
            return v
    except Exception:  # noqa: BLE001 — diagnostic, must never raise
        pass
    try:
        import importlib.metadata as _im

        return str(_im.version("numpy"))
    except Exception:  # noqa: BLE001 — metadata gone too: give up softly
        return "unknown"


def _build_abi_error_report(
    failures: list[tuple[str, Exception]],
    numpy_version: str,
    python_exe: str | None = None,
) -> _AbiReport:
    """V0.4.21/V0.4.22: build the (title, message, details, console,
    fatal, continue_warning) startup report for a detected ABI
    mismatch — a pure function so the dialog content is unit-testable
    without Qt.

    ``failures``: (module_name, exception) for EVERY probed module whose
    import raised a numpy-ABI marker. ``python_exe``: the interpreter
    the fix commands must target (defaults to sys.executable — V0.4.22:
    bare "python" targets the wrong interpreter far too often on
    Windows machines with several Pythons).
    """
    import traceback as _tb

    exe = f'"{python_exe or sys.executable or "python"}"'
    fatal = any(mod == "numpy" for mod, _err in failures)
    numpy_is_2 = numpy_version.split(".", 1)[0] == "2"
    upgrade_pkgs = (
        " ".join(sorted({_PIP_NAMES.get(mod, mod) for mod, _err in failures if mod != "numpy"}))
        or "numpy"
    )

    failing_names = ", ".join(mod for mod, _err in failures)

    # V0.4.22: the Elixir features the failing modules actually feed
    # (deduped, order-preserving); unknown modules claim only "an
    # optional feature".
    impacts: list[str] = []
    for mod, _err in failures:
        if mod == "numpy":
            continue
        label = _FEATURE_IMPACT.get(mod, "an optional feature")
        if label not in impacts:
            impacts.append(label)
    impact_line = "; ".join(impacts) or "none"

    details = "\n\n".join(
        f"--- {mod} ---\n" + "".join(_tb.format_exception(type(err), err, err.__traceback__))
        for mod, err in failures
    )

    if fatal:
        title = "numpy ABI mismatch — fix required (cannot start)"
        message = (
            "Elixir cannot start: numpy itself failed to import with an "
            "ABI error — the numpy installation is broken (usually mixed "
            f"numpy versions). Failing module(s): {failing_names}.\n\n"
            "Reinstall numpy:\n"
            f'    {exe} -m pip install --force-reinstall "numpy==1.26.4"\n\n'
            "After fixing, restart Elixir.\n"
            "See Show Details for the full tracebacks."
        )
        console = [
            f"STARTUP ERROR — numpy install broken / ABI mismatch (numpy {numpy_version} installed):",
            *(f"  {mod}: {err}" for mod, err in failures),
            f'  fix: {exe} -m pip install --force-reinstall "numpy==1.26.4"',
        ]
        return _AbiReport(title, message, details, console, True, [])

    # ── Optional-module failures: continuable (V0.4.22) ────────────────
    title = "numpy ABI mismatch — optional module(s) broken"
    if numpy_is_2:
        direction = (
            "They were built against the numpy 1.x ABI, but the installed "
            f"numpy is {numpy_version} (Elixir requires numpy>=1.26.0,<2.0.0)."
        )
        fix_a_cmd = f'{exe} -m pip install --force-reinstall "numpy==1.26.4"'
        fix_a_note = "(recommended — restores the numpy Elixir is built for)"
        fix_b_cmd = f"{exe} -m pip install --upgrade {upgrade_pkgs}"
        fix_b_note = "(upgrades the failing module(s) to numpy 2.x-compatible builds)"
        header = f"STARTUP WARNING — numpy 2.x ABI mismatch (numpy {numpy_version} installed):"
    else:
        direction = (
            "They were built against a different numpy ABI than the "
            f"installed numpy {numpy_version}."
        )
        fix_a_cmd = f"{exe} -m pip install --upgrade {upgrade_pkgs}"
        fix_a_note = "(recommended — matches the failing module(s) to the installed numpy)"
        fix_b_cmd = f'{exe} -m pip install --force-reinstall "numpy==1.26.4"'
        fix_b_note = "(restores the numpy Elixir is tested with, 1.26.4)"
        header = f"STARTUP WARNING — numpy ABI mismatch (numpy {numpy_version} installed):"

    message = (
        f"numpy ABI mismatch — failing module(s): {failing_names}. {direction}\n\n"
        "Fix — copy-paste ONE of these into a terminal:\n"
        f"    {fix_a_cmd}\n"
        f"    {fix_a_note}\n"
        f"    {fix_b_cmd}\n"
        f"    {fix_b_note}\n\n"
        f"Affected until fixed: {impact_line}. "
        "Everything else works — you can continue now and fix later.\n\n"
        "(Installed via requirements.lock? Older locks pinned numpy 2.x — "
        "reinstall with requirements.txt; V0.4.20+ pins numpy 1.26.4.)"
    )
    console = [
        header,
        *(f"  {mod}: {err}" for mod, err in failures),
        f"  fix: {fix_a_cmd}",
        f"  (alternative: {fix_b_cmd})",
        f"  affected features: {impact_line} — everything else works",
    ]
    continue_warning = [
        f"WARNING — continuing with broken module(s): {failing_names}",
        f"  affected features: {impact_line}",
        f"  fix later: {fix_a_cmd}",
    ]
    return _AbiReport(title, message, details, console, False, continue_warning)


def check_numpy_abi_compatibility() -> None:
    """V0.4.4 / V0.4.20 / V0.4.21 / V0.4.22: detect numpy ABI mismatch
    with compiled deps BEFORE the main window opens.

    Known field-report shapes (both caught):
        RuntimeError: module compiled against ABI version 0x1000009 …
        ImportError: numpy.core.multiarray failed to import   (cv2)

    numpy itself broken → fatal: focused dialog + SystemExit(1).
    Optional compiled module(s) broken (torch / pandas / onnxruntime /
    scipy / cv2 — none of them core to the PDF→Markdown pipeline) →
    STARTUP WARNING + dialog offering "Continue anyway" (default) or
    "Exit and fix now"; the fix commands embed sys.executable so they
    always target the interpreter actually running Elixir.

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
    # first — the report must name all modules broken on this machine.
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

    # Show the focused dialog. V0.4.22: fatal (numpy itself broken) →
    # single Ok + exit; optional-only failures → "Continue anyway"
    # (default) or "Exit and fix now". If the dialog cannot be shown at
    # all, exit(1) — never continue silently past a broken dialog.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical if report.fatal else QMessageBox.Warning)
        box.setWindowTitle(report.title)
        box.setText(report.message)
        box.setDetailedText(report.details)
        if report.fatal:
            box.setStandardButtons(QMessageBox.Ok)
            box.exec()
            sys.exit(1)
        box.addButton("Exit and fix now", QMessageBox.RejectRole)
        cont_btn = box.addButton("Continue anyway", QMessageBox.AcceptRole)
        box.setDefaultButton(cont_btn)
        box.exec()
        if box.clickedButton() is cont_btn:
            print("\n" + "=" * 60)
            for line in report.continue_warning:
                print(line)
            print("=" * 60 + "\n")
            return
        sys.exit(1)
    except Exception as _e:
        import logging

        logging.getLogger(__name__).debug("numpy ABI dialog failed: %s: %s", type(_e).__name__, _e)
        sys.exit(1)
