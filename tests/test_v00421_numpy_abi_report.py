"""V0.4.21 — numpy ABI report tailoring (first V0.4.20 field report).

The field report: the user's cv2 raised the legacy
``ImportError: numpy.core.multiarray failed to import`` (an
opencv-python build compiled against the numpy 1.x ABI, with numpy 2.x
installed by mistake — the user confirmed the wrong numpy). The guard
FIRED as designed, but the V0.4.20 fix dialog had three gaps:

a) it enumerated "(torch, pandas, onnxruntime, or scipy)" — four
   modules that had NOT failed — while never naming cv2, the module
   that actually had;
b) it never showed which numpy was installed, so the user could not
   tell which side of the mismatch they were on;
c) it offered only the numpy-downgrade fix, which is wrong advice when
   the installed numpy is 1.x and the module targets a different ABI.

V0.4.21 rebuilds the report as a pure function
(``_build_abi_error_report``) that names every failing module with its
pip package name, shows the installed numpy version, and tailors the
two fix commands to the actual mismatch direction. This file pins the
builder directly (no Qt needed) and one end-to-end run of the real
check against a simulated copy of the user's machine.
"""

from __future__ import annotations

import builtins
import importlib.util as _ilu
import re
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.system.numpy_abi_check import (
    _build_abi_error_report,
    _installed_numpy_version,
    check_numpy_abi_compatibility,
)

_ABI_CHECK = _project_root / "core" / "system" / "numpy_abi_check.py"


def _exc(msg: str) -> ImportError:
    """A real exception carrying a real traceback (details must show it)."""
    try:
        raise ImportError(msg)
    except ImportError as e:
        return e


def _qt_available() -> bool:
    """True when PySide6 imports AND the offscreen platform works."""
    try:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


# ── Builder: the report names the machine that actually broke ──────────────


class TestReportNamesTheBrokenModules:
    """Gap (a): the failing module(s) — and their pip package names —
    must be named; modules that did NOT fail must not be enumerated."""

    def test_user_report_case_cv2_with_numpy2(self) -> None:
        """The exact field report: cv2 legacy ImportError + numpy 2.x →
        2.x console header, cv2 AND opencv-python named, numpy restore
        as fix [A] and the opencv upgrade as fix [B]."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
        )
        assert "numpy 2.x ABI mismatch" in report.console[0]
        assert "cv2: numpy.core.multiarray failed to import" in "\n".join(report.console)
        assert "cv2" in report.message
        assert "opencv-python" in report.message, (
            "the pip package name must appear — 'pip install cv2' is wrong"
        )
        assert 'python -m pip install --force-reinstall "numpy==1.26.4"' in report.message
        assert "python -m pip install --upgrade opencv-python" in report.message
        assert "2.5.3" in report.message, "the installed numpy version must be shown"
        assert "numpy>=1.26.0,<2.0.0" in report.message, "Elixir's own pin must be shown"
        assert "numpy ABI mismatch" in report.title

    def test_module_that_did_not_fail_is_not_enumerated(self) -> None:
        """Only cv2 failed → the message must not claim torch/pandas/
        onnxruntime/scipy broke (the V0.4.20 gap (a))."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
        )
        # No generic four-module enumeration may appear as a claim about
        # THIS machine — only cv2 is named as failing.
        assert not re.search(r"torch, pandas, onnxruntime", report.message), (
            "the V0.4.20 generic module enumeration must not come back"
        )
        assert "failing module(s): cv2" in report.message

    def test_all_failures_collected_not_just_the_first(self) -> None:
        """Multiple broken modules → every one is named (module + pip
        package), and the upgrade command covers all of them."""
        report = _build_abi_error_report(
            [
                ("cv2", _exc("numpy.core.multiarray failed to import")),
                ("torch", _exc("module compiled against ABI version 0x1000009")),
            ],
            "2.5.3",
        )
        assert "cv2" in report.message and "torch" in report.message
        assert "opencv-python torch" in report.message, "sorted pip names in one command"
        assert "--- cv2 ---" in report.details and "--- torch ---" in report.details
        assert "failing module(s): cv2, torch" in report.message

    def test_details_carry_real_tracebacks(self) -> None:
        """The 'Show Details' pane keeps the full traceback per module
        (what the user pasted in the field report)."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
        )
        assert "Traceback (most recent call last)" in report.details
        assert "in _exc" in report.details, "the raising frame must be visible"


class TestReportTailorsFixDirection:
    """Gap (c): the primary fix must match the actual mismatch direction."""

    def test_numpy1_direction_offers_module_upgrade_first(self) -> None:
        """numpy 1.x installed (module built against a different ABI) →
        module upgrade is fix [A]; the report must NOT claim numpy 2.x."""
        report = _build_abi_error_report(
            [("torch", _exc("module compiled against ABI version 0x1000009"))],
            "1.26.4",
        )
        joined = "\n".join(report.console)
        assert "numpy ABI mismatch (numpy 1.26.4 installed)" in joined
        assert "numpy 2.x ABI mismatch" not in joined, (
            "must not claim 2.x when the installed numpy is 1.x"
        )
        assert "python -m pip install --upgrade torch" in report.message
        # The numpy-restore path is still offered as the alternative.
        assert '"numpy==1.26.4"' in report.message

    def test_unknown_version_degrades_to_both_paths(self) -> None:
        """Unreadable numpy version → no crash, generic direction text,
        both fix commands still present."""
        report = _build_abi_error_report([("scipy", _exc("_ARRAY_API not found"))], "unknown")
        assert "numpy unknown" in report.message
        assert "python -m pip install --upgrade scipy" in report.message
        assert '"numpy==1.26.4"' in report.message

    def test_lockfile_trap_warning_kept(self) -> None:
        """The V0.4.20 contract is preserved: the report still warns
        about the stale requirements.lock numpy 2.x install path."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
        )
        assert "requirements.lock" in report.message


# ── Installed-version helper ────────────────────────────────────────────────


class TestInstalledNumpyVersion:
    def test_reads_sys_modules_numpy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = types.ModuleType("numpy")
        stub.__version__ = "9.9.9"
        monkeypatch.setitem(sys.modules, "numpy", stub)
        assert _installed_numpy_version() == "9.9.9"

    def test_never_raises_on_broken_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(sys.modules, "numpy", raising=False)
        real_import = builtins.__import__

        def boom(name: str, *a, **kw):
            if name == "numpy":
                raise ImportError("numpy itself is broken")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", boom, raising=True)
        assert _installed_numpy_version() == "unknown"


# ── End-to-end: the user's machine, simulated ───────────────────────────────


class _StubMessageBox:
    """Records the ABI dialog's calls (no real Qt rendering, never blocks)."""

    Critical = "critical"
    Ok = "ok"
    instances: list[_StubMessageBox] = []

    def __init__(self) -> None:
        self.calls: dict[str, tuple] = {}
        _StubMessageBox.instances.append(self)

    def setIcon(self, icon) -> None:
        self.calls["icon"] = (icon,)

    def setWindowTitle(self, title: str) -> None:
        self.calls["title"] = (title,)

    def setText(self, text: str) -> None:
        self.calls["text"] = (text,)

    def setDetailedText(self, text: str) -> None:
        self.calls["details"] = (text,)

    def setStandardButtons(self, buttons) -> None:
        self.calls["buttons"] = (buttons,)

    def exec(self) -> int:
        self.calls["exec"] = ()
        return 0


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestFieldReportEndToEnd:
    """The user's exact machine state: numpy 2.x installed + cv2 built
    against the numpy 1.x ABI → the guard fires with the tailored
    report reaching BOTH the console and the dialog."""

    @pytest.fixture()
    def _stub_dialog(self, monkeypatch: pytest.MonkeyPatch):
        import PySide6.QtWidgets as qtw

        _StubMessageBox.instances.clear()
        monkeypatch.setattr(qtw, "QMessageBox", _StubMessageBox, raising=True)
        yield

    def test_user_machine_cv2_abi(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, _stub_dialog
    ) -> None:
        # numpy 2.5.3 "installed" (a stub module with that version) …
        stub_np = types.ModuleType("numpy")
        stub_np.__version__ = "2.5.3"
        monkeypatch.setitem(sys.modules, "numpy", stub_np)

        # … and cv2 broken with the legacy error, everything else absent.
        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name in {"numpy", "cv2"} else None

        def fake_import(name, *a, **kw):
            if name == "cv2":
                raise ImportError("numpy.core.multiarray failed to import")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

        with pytest.raises(SystemExit) as ei:
            check_numpy_abi_compatibility()
        assert ei.value.code == 1

        out = capsys.readouterr().out
        assert "numpy 2.x ABI mismatch" in out
        assert "cv2: numpy.core.multiarray failed to import" in out
        assert 'fix: python -m pip install --force-reinstall "numpy==1.26.4"' in out

        assert _StubMessageBox.instances, "the fix dialog must have been created"
        box = _StubMessageBox.instances[0]
        assert "numpy ABI mismatch" in box.calls["title"][0]
        text = box.calls["text"][0]
        assert "cv2" in text
        assert "opencv-python" in text, "the dialog must name the pip package"
        assert "2.5.3" in text, "the dialog must show the installed numpy version"
        assert "numpy==1.26.4" in text, "the dialog must carry the tailored fix command"
        assert "Traceback (most recent call last)" in box.calls["details"][0]


# ── Source pins ─────────────────────────────────────────────────────────────


class TestSourcePins:
    def test_pip_name_mapping_present(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert '"cv2": "opencv-python"' in src, (
            "cv2's pip package name must be mapped (copy-pasteable fix commands)"
        )

    def test_report_built_via_pure_function(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "_build_abi_error_report(failures, _installed_numpy_version())" in src, (
            "the dialog must consume the tested report builder, not ad-hoc text"
        )
