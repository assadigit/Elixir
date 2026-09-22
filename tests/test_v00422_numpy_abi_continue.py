"""V0.4.22 — the ABI guard no longer locks the user out (second field
report, screenshot 4343.png).

The second field report: same user, same machine, now on V0.4.21 — the
V0.4.21 dialog rendered COMPLETELY (failing module cv2, installed numpy
2.5.3, both fix commands visible, nothing clipped), yet the user still
could not get past it. Two product defects, not message defects:

a) the fix commands said ``python -m pip ...`` — with several Pythons
   installed (their Elixir runs under
   C:\\Users\\...\\Python312\\python.exe), bare ``python`` targets the
   WRONG interpreter far too often: the command "succeeds", fixes
   nothing, and the dialog comes back. Commands now embed
   ``sys.executable`` (quoted) so a copy-paste always targets the
   interpreter actually running Elixir.

b) cv2 feeds ONLY the rapidocr vision-OCR chain (markitdown[all]
   closure) — Elixir's own code never imports it — yet a broken cv2
   hard-blocked the ENTIRE app at startup. Only numpy itself is core.
   Optional-module failures now offer "Continue anyway" (default) with
   a loud warning naming the affected features; numpy-itself-broken
   stays fatal (SystemExit(1)).

Also: compact fix-first message (the user's window is 816×510) and the
installed-numpy read gains an importlib.metadata fallback (when numpy
itself cannot import, the dist metadata still reports what is
installed — the mixed-install diagnosis).
"""

from __future__ import annotations

import builtins
import importlib.util as _ilu
import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.system.numpy_abi_check import _build_abi_error_report, check_numpy_abi_compatibility

try:
    from tests.test_v00421_numpy_abi_report import _exc, _qt_available, _StubMessageBox
except ImportError:  # pytest rootdir mode: tests/ itself is on sys.path
    from test_v00421_numpy_abi_report import _exc, _qt_available, _StubMessageBox

_ABI_CHECK = _project_root / "core" / "system" / "numpy_abi_check.py"
_EXE = "C:/Program Files/Python312/python.exe"


# ── Severity split: only numpy itself is fatal ──────────────────────────────


class TestFatalVsOptional:
    def test_optional_module_failure_is_continuable(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert report.fatal is False
        assert report.continue_warning, "a continuable report must carry the warning lines"

    def test_numpy_itself_failing_is_fatal(self) -> None:
        report = _build_abi_error_report(
            [
                ("numpy", _exc("numpy.core.multiarray failed to import")),
                ("cv2", _exc("numpy.core.multiarray failed to import")),
            ],
            "unknown",
            python_exe=_EXE,
        )
        assert report.fatal is True
        assert "cannot start" in report.message
        assert "STARTUP ERROR" in report.console[0]
        assert report.continue_warning == [], "fatal reports must not offer to continue"

    def test_optional_console_is_a_warning_not_an_error(self) -> None:
        """The optional branch prints STARTUP WARNING (the app will run);
        only the fatal branch prints STARTUP ERROR."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert "STARTUP WARNING" in report.console[0]
        assert "STARTUP ERROR" not in "\n".join(report.console)


# ── Feature impact: which Elixir features the broken modules feed ──────────


class TestFeatureImpact:
    def test_cv2_impact_is_rapidocr_vision_ocr(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert "Affected until fixed: rapidocr vision OCR." in report.message
        assert "affected features: rapidocr vision OCR" in "\n".join(report.console)
        assert "rapidocr vision OCR" in "\n".join(report.continue_warning)

    def test_impacts_dedupe_and_join(self) -> None:
        """cv2 + onnxruntime both feed rapidocr vision OCR → one entry;
        torch adds its own."""
        report = _build_abi_error_report(
            [
                ("cv2", _exc("numpy.core.multiarray failed to import")),
                ("onnxruntime", _exc("numpy.core.multiarray failed to import")),
                ("torch", _exc("module compiled against ABI version 0x1000009")),
            ],
            "2.5.3",
            python_exe=_EXE,
        )
        assert "Affected until fixed: rapidocr vision OCR; vision OCR / TTS (extras)." in (
            report.message
        )

    def test_unknown_module_claims_only_an_optional_feature(self) -> None:
        report = _build_abi_error_report(
            [("somemod", _exc("_ARRAY_API not found"))], "2.5.3", python_exe=_EXE
        )
        assert "Affected until fixed: an optional feature." in report.message


# ── The fix commands target the RUNNING interpreter ─────────────────────────


class TestExeTargetedCommands:
    def test_commands_embed_the_given_interpreter_quoted(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe="C:/Program Files/Python312/python.exe",
        )
        # Spaces in the path must be quoted or cmd.exe splits the command.
        assert '"C:/Program Files/Python312/python.exe" -m pip install' in report.message

    def test_console_fix_line_targets_running_interpreter(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert f'fix: "{_EXE}" -m pip install' in "\n".join(report.console)

    def test_default_is_sys_executable(self) -> None:
        """No explicit exe → the report targets sys.executable (the
        interpreter ACTUALLY running Elixir — the 4343.png lesson)."""
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))], "2.5.3"
        )
        assert f'"{sys.executable}" -m pip install' in report.message


# ── Compact, fix-first message (the user's window is 816×510) ───────────────


class TestMessageShape:
    def test_optional_message_is_compact(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert len(report.message.splitlines()) <= 12, (
            "the optional-case message must stay compact for small screens "
            f"(got {len(report.message.splitlines())} lines)"
        )

    def test_fix_comes_before_the_lockfile_footnote(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert 0 <= report.message.index("Fix") < report.message.index("requirements.lock")

    def test_message_names_the_continue_option(self) -> None:
        report = _build_abi_error_report(
            [("cv2", _exc("numpy.core.multiarray failed to import"))],
            "2.5.3",
            python_exe=_EXE,
        )
        assert "you can continue now and fix later" in report.message


# ── Behavioral: the Continue-anyway / Exit dialog flow ──────────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestContinueOrExitFlow:
    """The user's machine (numpy 2.5.3 + ABI-broken cv2) drives the full
    check with a recording QMessageBox stub; the button choice decides
    continue vs exit."""

    @staticmethod
    def _box_class(click):
        """A QMessageBox stand-in whose clickedButton() reports `click`.

        A class (not a lambda): the production code reads class attrs
        (QMessageBox.Warning / RejectRole / AcceptRole) off the patched
        symbol before instantiating it.
        """

        class _Box(_StubMessageBox):
            def __init__(self) -> None:
                super().__init__(click=click)

        return _Box

    @staticmethod
    def _user_machine(monkeypatch: pytest.MonkeyPatch, click: str) -> None:
        import PySide6.QtWidgets as qtw

        _StubMessageBox.instances.clear()
        monkeypatch.setattr(
            qtw, "QMessageBox", TestContinueOrExitFlow._box_class(click), raising=True
        )

        stub_np = types.ModuleType("numpy")
        stub_np.__version__ = "2.5.3"
        monkeypatch.setitem(sys.modules, "numpy", stub_np)

        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name in {"numpy", "cv2"} else None

        def fake_import(name, *a, **kw):
            if name == "cv2":
                raise ImportError("numpy.core.multiarray failed to import")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

    def test_continue_button_opens_the_app(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """Clicking 'Continue anyway' → the check RETURNS (no SystemExit)
        and prints the loud warning with the affected features + the fix
        for later."""
        self._user_machine(monkeypatch, click="Continue anyway")

        check_numpy_abi_compatibility()  # must NOT raise

        out = capsys.readouterr().out
        assert "WARNING — continuing with broken module(s): cv2" in out
        assert "affected features: rapidocr vision OCR" in out
        assert "fix later:" in out

    def test_exit_button_stops_the_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clicking 'Exit and fix now' → SystemExit(1)."""
        self._user_machine(monkeypatch, click="Exit and fix now")
        with pytest.raises(SystemExit) as ei:
            check_numpy_abi_compatibility()
        assert ei.value.code == 1

    def test_ambiguous_click_stops_the_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """clickedButton() → None (dialog dismissed without a choice) must
        take the SAFE branch: exit, never a silent continue."""
        self._user_machine(monkeypatch, click=None)
        with pytest.raises(SystemExit):
            check_numpy_abi_compatibility()

    def test_numpy_itself_broken_is_fatal_even_with_buttons(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """numpy failing its own import → STARTUP ERROR + SystemExit(1)
        regardless of any button (mixed/corrupt numpy install)."""
        import PySide6.QtWidgets as qtw

        _StubMessageBox.instances.clear()
        monkeypatch.setattr(qtw, "QMessageBox", self._box_class("Continue anyway"), raising=True)

        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name in {"numpy", "cv2"} else None

        def fake_import(name, *a, **kw):
            if name in {"numpy", "cv2"}:
                raise ImportError("numpy.core.multiarray failed to import")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

        with pytest.raises(SystemExit) as ei:
            check_numpy_abi_compatibility()
        assert ei.value.code == 1
        out = capsys.readouterr().out
        assert "STARTUP ERROR" in out

    def test_broken_dialog_stops_the_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the dialog itself cannot be built (Qt broken), the guard
        must exit(1), never continue silently."""

        class _BrokenBox:
            def __init__(self) -> None:
                raise RuntimeError("Qt is broken")

        import PySide6.QtWidgets as qtw

        monkeypatch.setattr(qtw, "QMessageBox", _BrokenBox, raising=True)

        stub_np = types.ModuleType("numpy")
        stub_np.__version__ = "2.5.3"
        monkeypatch.setitem(sys.modules, "numpy", stub_np)

        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name in {"numpy", "cv2"} else None

        def fake_import(name, *a, **kw):
            if name == "cv2":
                raise ImportError("numpy.core.multiarray failed to import")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

        with pytest.raises(SystemExit):
            check_numpy_abi_compatibility()


# ── Source pins ─────────────────────────────────────────────────────────────


class TestSourcePins:
    def test_continue_button_is_default(self) -> None:
        """A broken OPTIONAL module must not lock the user out: the
        Continue button exists and is the dialog default."""
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert '"Continue anyway"' in src
        assert '"Exit and fix now"' in src
        assert "box.setDefaultButton(cont_btn)" in src

    def test_commands_target_sys_executable(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "sys.executable" in src, (
            "fix commands must embed the running interpreter (4343.png: "
            "bare 'python' targeted the wrong one)"
        )

    def test_metadata_version_fallback_present(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "importlib.metadata" in src, (
            "numpy-itself-broken still reports the installed dist version"
        )

    def test_feature_impact_map_present(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "_FEATURE_IMPACT" in src
        assert '"cv2": "rapidocr vision OCR"' in src
