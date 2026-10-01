"""V0.4.20 — three user-reported crash/UX fixes (screenshots 3434.png / 454545.png).

1. TypeCard icons rendered top-LEFT (user: "must be top center, above their
   titles"). Root cause: a fixed-size QLabel added to a QVBoxLayout with
   default alignment keeps the origin-side position when it cannot fill
   the cell — the V1.5 "centered design" never actually centered the icon
   label. Fix: explicit ``Qt.AlignHCenter`` on ``lay.addWidget``.

2. Wizard Step 5 with the llama.cpp backend selected: "information and
   details are cramped and not visible". Root cause: the step's content
   sizeHint (~733px) exceeds the compact wizard's step viewport (~400px
   at the V7.4.0 minimum 740x540) and Step5Models — unlike Step4Outputs /
   Step7bFineTune — hosted its boxes directly, so the bottom of the Local
   configuration box and everything below was clipped and unreachable.
   Fix: the house frameless-QScrollArea host pattern.

3. "a numpy mismatch happened that crashed the app". Two root causes:
   a) the V0.4.4 startup probe list (numpy/pypdf/pdfplumber/PIL) contains
      no module with compiled numpy code, so it could never fire — the
      real culprits (torch/pandas/onnxruntime/scipy/cv2) crashed later,
      lazily; b) requirements.lock pinned numpy==2.5.3, violating the
      app's own numpy<2 requirement and reproducing the ABI crash for
      anyone installing via the lock. Fix: hardened probe + lock pin.

Two layers per the house UI-test pattern (see test_v182038_audit_fixes /
test_v1820314_ui_cta_crash): source-pin tests (always run, headless-safe)
and behavioral widget tests (offscreen QApplication; skipped gracefully
when PySide6/offscreen is unavailable).
"""

from __future__ import annotations

import builtins
import importlib.util as _ilu
import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_TYPE_CARD = _project_root / "ui_qt" / "components" / "type_card.py"
_STEP5 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step5_models.py"
_LLAMACPP_CFG = _project_root / "ui_qt" / "components" / "llamacpp_config.py"
_ABI_CHECK = _project_root / "core" / "system" / "numpy_abi_check.py"
_REQS = _project_root / "requirements.txt"
_LOCK = _project_root / "requirements.lock"


def _qt_available() -> bool:
    """True when PySide6 imports AND the offscreen platform works."""
    try:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


# ── Policy / source-pin layer (headless-safe, always runs) ──────────────────


class TestTypeCardIconCentered:
    """The icon label must be added with an explicit horizontal-center
    alignment — the default box-layout position for a fixed-size widget
    is the left edge of the cell."""

    def test_icon_addwidget_uses_align_hcenter(self) -> None:
        src = _TYPE_CARD.read_text(encoding="utf-8")
        assert re.search(r"lay\.addWidget\(self\.icon_label,\s*0,\s*Qt\.AlignHCenter\)", src), (
            "TypeCard must center its icon: lay.addWidget(self.icon_label, 0, Qt.AlignHCenter)"
        )

    def test_icon_still_above_title(self) -> None:
        """The centered icon stays the FIRST child of the card layout
        (icon → title → subtitle reading order)."""
        src = _TYPE_CARD.read_text(encoding="utf-8")
        icon_pos = src.index("lay.addWidget(self.icon_label")
        title_pos = src.index("lay.addWidget(self.title_label")
        assert icon_pos < title_pos, "icon must be added before (above) the title"


class TestStep5ScrollHost:
    """Step5Models must host its boxes inside a frameless QScrollArea —
    same pattern as Step4Outputs / Step7bFineTune — so the compact
    wizard's small step viewport can scroll to the clipped content."""

    def test_imports_scroll_area(self) -> None:
        src = _STEP5.read_text(encoding="utf-8")
        assert re.search(r"^\s+QScrollArea,$", src, re.M), "QScrollArea must be imported"
        assert re.search(r"^\s+QFrame,$", src, re.M), "QFrame must be imported (NoFrame)"

    def test_scroll_host_pattern(self) -> None:
        src = _STEP5.read_text(encoding="utf-8")
        assert "scroll.setWidgetResizable(True)" in src
        assert "scroll.setFrameShape(QFrame.NoFrame)" in src
        assert "scroll.setWidget(host)" in src
        assert re.search(r"lay\.addWidget\(scroll,\s*1\)", src), "scroll takes the step's stretch"

    def test_boxes_live_in_host_layout(self) -> None:
        """All the group boxes must be added to the scroll host's layout,
        never directly to the step layout.

        V0.6.14 (single-model order): "self.fast_api_box" removed from
        the tuple (4 boxes remain) — the Fast API box is RETIRED from
        step5, one model does every LLM task."""
        src = _STEP5.read_text(encoding="utf-8")
        for widget in (
            "arch_box",
            "self.local_box",
            "self.heavy_api_box",
            "params_box",
        ):
            assert re.search(rf"host_lay\.addWidget\({re.escape(widget)}\)", src), (
                f"{widget} must be added to host_lay (the scroll host)"
            )

    def test_no_direct_step_adds_for_boxes(self) -> None:
        """The old clipped layout added boxes straight to the step layout;
        those lines must be gone."""
        src = _STEP5.read_text(encoding="utf-8")
        # V0.6.14 (single-model order): "self.fast_api_box" removed from
        # the tuple — the Fast API box is RETIRED from step5.
        for widget in (
            "arch_box",
            "self.local_box",
            "self.heavy_api_box",
            "params_box",
        ):
            assert not re.search(rf"^\s*lay\.addWidget\({re.escape(widget)}\)\s*$", src, re.M), (
                f"{widget} may not be added directly to the step layout (clips)"
            )


class TestLlamaCppBoxPolish:
    """The llama.cpp endpoint rows breathe (spacing 8) and the URL/model
    line edits keep a readable minimum width."""

    def test_row_spacing(self) -> None:
        src = _LLAMACPP_CFG.read_text(encoding="utf-8")
        assert "lay.setSpacing(8)" in src, "llama.cpp box rows need the wizard-standard 8px spacing"

    def test_minimum_widths(self) -> None:
        src = _LLAMACPP_CFG.read_text(encoding="utf-8")
        assert "self.llamacpp_url_edit.setMinimumWidth(260)" in src
        assert "self.llamacpp_model_edit.setMinimumWidth(260)" in src


class TestNumpyAbiProbeHardened:
    """The V0.4.20 probe must cover the compiled numpy consumers, not the
    V0.4.4 pure-python list that could never raise the ABI error."""

    def test_probe_candidates_present(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        for mod in ("torch", "pandas", "onnxruntime", "scipy", "cv2"):
            assert f'"{mod}"' in src, f"probe list must include the compiled culprit {mod!r}"

    def test_find_spec_prefilter(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "find_spec" in src, "absent modules must be skipped via find_spec (fast, no import)"

    def test_abi_markers_broadened(self) -> None:
        """Beyond the classic RuntimeError string, the other numpy 1.x/2.x
        mismatch shapes must be recognised."""
        src = _ABI_CHECK.read_text(encoding="utf-8")
        for marker in (
            "ABI version",
            "compiled using NumPy 1.x",
            "_ARRAY_API not found",
            "multiarray failed to import",
        ):
            assert marker in src, f"ABI marker {marker!r} must be matched"

    def test_dialog_mentions_lockfile_trap(self) -> None:
        src = _ABI_CHECK.read_text(encoding="utf-8")
        assert "requirements.lock" in src, (
            "the fix dialog must warn about the stale-lock install path"
        )


class TestLockFileNumpyPin:
    """requirements.lock must respect the app's own numpy<2 requirement
    (the V0.4.20 crash: the lock shipped numpy==2.5.3)."""

    def test_requirements_pin_numpy_below_2(self) -> None:
        src = _REQS.read_text(encoding="utf-8")
        m = re.search(r"^numpy([^\n#]*)", src, re.M)
        assert m, "requirements.txt must pin numpy"
        assert "<2" in m.group(1), f"requirements.txt numpy pin must stay <2: {m.group(1)!r}"

    def test_lock_pins_numpy_1x(self) -> None:
        src = _LOCK.read_text(encoding="utf-8")
        m = re.search(r"^numpy==(\d+)\.(\d+)\.(\d+)", src, re.M)
        assert m, "requirements.lock must pin an exact numpy version"
        major, minor, _ = (int(g) for g in m.groups())
        assert major == 1, f"requirements.lock numpy must be 1.x, got {major}.{minor}"

    def test_lock_has_no_numpy_2_pins(self) -> None:
        """No numpy 2.x line may reappear anywhere in the lock."""
        src = _LOCK.read_text(encoding="utf-8")
        assert not re.search(r"^numpy==2\.", src, re.M), "numpy==2.x must never return to the lock"


# ── Behavioral layer (offscreen Qt; skips without PySide6) ───────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTypeCardIconGeometry:
    """Widget-level proof: the icon label's center sits within ±3px of the
    card's horizontal center (was: pinned to the left edge + margin)."""

    def test_icon_is_horizontally_centered(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QGridLayout, QVBoxLayout, QWidget

        app = QApplication.instance() or QApplication([])

        from ui_qt.components.type_card import TypeCard

        host = QWidget()
        lay = QVBoxLayout(host)
        grid = QGridLayout()
        tc = TypeCard(
            value="normal_book",
            icon_name="book",
            title="Book",
            subtitle="Standard text — novels, biographies, business books.",
            png_name="normal_book",
        )
        grid.addWidget(tc, 0, 0)
        lay.addLayout(grid)
        host.resize(790, 400)
        host.show()
        app.processEvents()

        icon = tc.icon_label
        icon_center_x = icon.geometry().center().x()
        card_center_x = tc.width() / 2
        assert tc.width() > 120, "card must be wider than the icon for centering to be measurable"
        assert abs(icon_center_x - card_center_x) <= 3, (
            f"icon center {icon_center_x} must match card center {card_center_x} (±3px)"
        )

        # Reading order: icon above title.
        assert icon.geometry().bottom() <= tc.title_label.geometry().top() + 2

        # Icon is at the TOP of the card content, not beside the title.
        assert icon.geometry().y() < tc.title_label.geometry().y()
        host.hide()


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestStep5ScrollBehavior:
    """Widget-level proof: with llama.cpp selected, all the boxes are
    inside the scroll host and the full content is reachable.

    V0.6.14 (single-model order): the expected-title set updated to the
    4-box single-model layout — "Model architecture" is now the 2-option
    "Where does the model run?" (Local/Cloud, writes provider), the ONE
    cloud box is "☁️ Cloud API configuration (the model)", and the
    "⚡ Fast API configuration (cheap workhorse)" box is RETIRED."""

    class _StubCtl:
        """Minimal controller — reads only the keys Step5Models touches."""

        def get_setting(self, key, default=None):
            return {
                "summarisation.provider": "llamacpp",
                # V0.6.14 (single-model order): the "summarisation.
                # model_architecture" stub key REMOVED — the setting is
                # retired (the arch combo now writes provider only).
                "summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1",
                "summarisation.llamacpp_model": "Ternary-Bonsai-2-27B-Instruct-Vision",
                "summarisation.llamacpp_context_tokens": 65536,
                "summarisation.llamacpp_max_output_tokens": 12288,
                "summarisation.max_context_tokens": 32768,
                "summarisation.max_output_tokens": 16000,
            }.get(key, default)

        def get_secret(self, key, default=None):
            return default

        def update_setting(self, k, v):
            pass

    def test_scroll_area_hosts_all_boxes(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QScrollArea

        app = QApplication.instance() or QApplication([])

        from ui_qt.views.wizard_steps.shared import WizardState
        from ui_qt.views.wizard_steps.step5_models import Step5Models

        state = WizardState()
        # V0.6.14 (single-model order): the state.model_architecture stub
        # assignment REMOVED — the WizardState field is retired.
        step = Step5Models(self._StubCtl(), state)
        step.resize(790, 400)  # the compact wizard's step viewport
        step.show()
        app.processEvents()

        scrolls = step.findChildren(QScrollArea)
        assert scrolls, "Step5Models must own a QScrollArea"
        scroll = scrolls[0]
        assert scroll.widgetResizable()

        host = scroll.widget()
        box_titles = {b.title() for b in host.findChildren(type(step.local_box))}
        assert box_titles == {
            "Where does the model run?",
            "Parameters",
            "☁️ Cloud API configuration (the model)",
            "🏠 Local configuration",
        }, f"all four boxes must live in the scroll host, got {sorted(box_titles)}"

        # The content exceeds the compact viewport → scrolling works and
        # nothing is clipped: the host gets its full sizeHint height.
        app.processEvents()
        assert host.height() > scroll.viewport().height() or scroll.widgetResizable(), (
            "content must be scrollable when taller than the viewport"
        )

        # The llama.cpp surface is present in the (now reachable) content.
        assert step.llamacpp_test_btn is not None
        assert step.llamacpp_url_edit.minimumWidth() >= 260
        step.hide()


class TestNumpyAbiProbeBehavior:
    """Behavioral probe tests (no Qt needed): a fake import surface drives
    every ABI marker shape and the healthy path."""

    @staticmethod
    def _patch_imports(monkeypatch, spec_names, raise_for):
        """find_spec admits only ``spec_names``; ``__import__`` raises
        ``raise_for[name]`` for the given names, else real import."""
        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name in spec_names else None

        def fake_import(name, *a, **kw):
            if name in raise_for:
                raise raise_for[name]
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

    @pytest.fixture()
    def _no_dialog(self, monkeypatch):
        """The fix dialog must not block: QMessageBox.exec returns at once."""
        try:
            from PySide6.QtWidgets import QMessageBox

            monkeypatch.setattr(QMessageBox, "exec", lambda self=None: 0, raising=True)
        except Exception:
            pass

    def test_classic_runtime_error_fires_guard(self, monkeypatch, capsys, _no_dialog):
        """The V0.4.4-era string (from the user's screenshot) must fire the
        guard: focused STARTUP ERROR print + SystemExit(1)."""
        self._patch_imports(
            monkeypatch,
            spec_names={"numpy", "torch"},
            raise_for={
                # V0.4.22: numpy ITSELF failing is the FATAL branch
                # (STARTUP ERROR). torch failing alone is the optional
                # branch (STARTUP WARNING + Continue-anyway dialog).
                "numpy": RuntimeError(
                    "module compiled against ABI version 0x1000009 "
                    "but this version of numpy is 0x2000000"
                ),
                "torch": RuntimeError(
                    "module compiled against ABI version 0x1000009 "
                    "but this version of numpy is 0x2000000"
                ),
            },
        )
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        with pytest.raises(SystemExit) as ei:
            check_numpy_abi_compatibility()
        assert ei.value.code == 1
        out = capsys.readouterr().out
        # V0.4.21/V0.4.22: header is version-aware; pin the invariant wording.
        assert "STARTUP ERROR" in out and "ABI mismatch" in out
        assert "0x1000009" in out, "the exact error text must be surfaced to the user"
        assert "torch" in out, "V0.4.21: the failing module must be named in the console report"
        assert re.search(r"numpy \d+\.\d+\.\d+ installed", out), (
            "V0.4.21: the installed numpy version must be surfaced in the console report"
        )
        assert "fix:" in out, "V0.4.21: the console report ends with the fix command"

    def test_numpy2_importerror_shape_fires_guard(self, monkeypatch, _no_dialog):
        """numpy 2.x's own ImportError wording must be recognised too."""
        self._patch_imports(
            monkeypatch,
            spec_names={"numpy", "pandas"},
            raise_for={
                "pandas": ImportError(
                    "A module that was compiled using NumPy 1.x cannot be run in "
                    "NumPy 2.x as it may crash."
                )
            },
        )
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        with pytest.raises(SystemExit):
            check_numpy_abi_compatibility()

    def test_array_api_valueerror_shape_fires_guard(self, monkeypatch, _no_dialog):
        """The ValueError variant ('_ARRAY_API not found') must be caught."""
        self._patch_imports(
            monkeypatch,
            spec_names={"numpy", "onnxruntime"},
            raise_for={"onnxruntime": ValueError("_ARRAY_API not found (required for NumPy 2.x)")},
        )
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        with pytest.raises(SystemExit):
            check_numpy_abi_compatibility()

    def test_legacy_multiarray_shape_fires_guard(self, monkeypatch, _no_dialog):
        """The legacy 'numpy.core.multiarray failed to import' shape."""
        self._patch_imports(
            monkeypatch,
            spec_names={"numpy", "cv2"},
            raise_for={"cv2": ImportError("numpy.core.multiarray failed to import")},
        )
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        with pytest.raises(SystemExit):
            check_numpy_abi_compatibility()

    def test_non_abi_errors_pass_through(self, monkeypatch):
        """Unrelated import failures (missing module pieces, DLL errors)
        must NOT fire the guard — those belong to the dependency check."""
        self._patch_imports(
            monkeypatch,
            spec_names={"numpy", "torch", "pandas", "onnxruntime", "scipy", "cv2"},
            raise_for={
                "torch": OSError("CUDA DLL load failed"),
                "pandas": ImportError("No module named 'pandas.missing_piece'"),
            },
        )
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        # Must simply return — no SystemExit, no dialog.
        check_numpy_abi_compatibility()

    def test_healthy_path_is_silent(self, monkeypatch):
        """Everything imports cleanly → the probe returns quietly."""
        self._patch_imports(monkeypatch, spec_names={"numpy", "torch"}, raise_for={})
        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        check_numpy_abi_compatibility()

    def test_absent_modules_are_skipped(self, monkeypatch):
        """find_spec → None (module not installed) means no import attempt
        at all — the probe never turns a missing module into anything."""
        imported: list[str] = []
        real_import = builtins.__import__

        def fake_find_spec(name, *a, **kw):
            return object() if name == "numpy" else None

        def fake_import(name, *a, **kw):
            imported.append(name)
            return real_import(name, *a, **kw)

        monkeypatch.setattr(_ilu, "find_spec", fake_find_spec, raising=True)
        monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

        from core.system.numpy_abi_check import check_numpy_abi_compatibility

        check_numpy_abi_compatibility()
        assert "torch" not in imported, "torch must not be imported when find_spec says absent"
