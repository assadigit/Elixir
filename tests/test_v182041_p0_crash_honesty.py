"""V18.20.4.1 (P0) — the crash + honesty-integrity release.

Four fixes, per the approved V18.20.4.0 SWOT roadmap:

- **W-b1 (Critical, live):** dropping a PDF on any non-Queue tab crashed
  with ``AttributeError: 'NoneType' object has no attribute 'set_path'``
  — ``app.dropEvent`` forwarded to ``convert_view.handle_dropped_file``,
  which dereferenced ``input_picker`` (None since V11.0.0), the same
  V11.0.0-latent class as the V18.20.3.14 ``_on_complete`` crash. Drops
  now route to the Queue view from ANY tab, and ``dragEnterEvent``
  accepts PDF only (matching the overlay's "Drop a PDF here" promise).
- **W-b13:** the ~350-line dead V11.0.0 legacy block in convert_view.py
  (16 methods + 14 None/never-assigned widget attributes) is DELETED —
  the .3.14 crash class is closed structurally.
- **W-a2:** the fabricated ``coverage=0.92`` placeholder shipped to
  library.json for every book is replaced by the MEASURED
  ``totals.avg_coverage`` from quality_report.json (None — stored
  honestly as unknown — when no report exists); ``get_stats`` averages
  only measured values.
- **W-b2 / W-b3 / W-b4 (wizard):** HardwareMonitor callbacks no longer
  write to Qt widgets from the polling thread (auto-pause now runs on
  the main thread via the ``auto_pause_requested`` signal); the
  controller bridge's ``connect_*`` are idempotent (a wizard re-run can
  no longer duplicate every signal → double completion modals / double
  post-completion action); closing the wizard mid-conversion stops the
  hardware monitor + elapsed timer instead of orphaning them.

Two layers, per the house pattern: headless-safe source pins + pure-Py
behavioral tests always run; offscreen Qt behavioral tests skip when
PySide6 is unavailable (the headless rig).
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline import chain loadable for the library_manager
# behavioral tests).
_APP = _project_root / "ui_qt" / "app.py"
_CONVERT_VIEW = _project_root / "ui_qt" / "views" / "convert_view.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_BRIDGE = _project_root / "ui_qt" / "controller_bridge.py"
_CONVERTER = _project_root / "core" / "pipeline" / "converter_impl.py"
# V0.4.26 (Phase 3 commit 3): the library-tracking block (the W-a2
# measured-coverage read) moved VERBATIM to run_library_tracking in
# core/pipeline/conversion/finalization.py — the W-a2 pins read the UNION
# of both files (the established repoint discipline).
_FINALIZATION = _project_root / "core" / "pipeline" / "conversion" / "finalization.py"
_LIBRARY = _project_root / "core" / "pipeline" / "library_manager.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        # naive inline-comment strip (no '#' inside the string literals we
        # assert against in these bodies)
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════
# W-b1 — the drag-and-drop crash (the live Critical)
# ═══════════════════════════════════════════════════════════════════════════


class TestWb1DropRouting:
    def test_drop_event_no_longer_forwards_to_convert_view(self):
        """The crash path (app.py → convert_view.handle_dropped_file →
        input_picker.set_path on None) must be gone from dropEvent."""
        src = _strip_comments(_src(_APP))
        drop_start = src.find("def dropEvent")
        assert drop_start != -1
        body = src[drop_start : src.find("\n    def ", drop_start)]
        assert "convert_view.handle_dropped_file" not in body, (
            "dropEvent must not forward to convert_view.handle_dropped_file "
            "(W-b1: input_picker is None since V11.0.0 — the crash)"
        )
        assert "queue_view.handle_dropped_files" in body, (
            "dropEvent must route drops to the Queue view (the only live drop consumer)"
        )

    def test_drop_overlay_only_advertises_pdf(self):
        """dragEnterEvent accepts PDF only — the old 4-suffix set
        (.pdf/.md/.txt/.docx) advertised drops no live view accepts."""
        src = _strip_comments(_src(_APP))
        enter_start = src.find("def dragEnterEvent")
        assert enter_start != -1
        body = src[enter_start : src.find("\n    def ", enter_start)]
        assert '".pdf"' in body
        assert ".md" not in body and ".txt" not in body and ".docx" not in body

    def test_convert_view_has_no_drop_entry_point(self):
        """handle_dropped_file (and its _on_input_changed companion, which
        dereferenced the never-assigned chapter_count_lbl) is deleted."""
        src = _src(_CONVERT_VIEW)
        assert "def handle_dropped_file" not in src
        assert "def _on_input_changed" not in src
        assert "chapter_count_lbl" not in src.replace("# ``input_picker.set_path``", "")


# ═══════════════════════════════════════════════════════════════════════════
# W-b13 — the legacy minefield deletion
# ═══════════════════════════════════════════════════════════════════════════


class TestWb13LegacyMinefieldDeleted:
    DEAD_METHODS = (
        "_on_type_selected",
        "_on_input_changed",
        "_on_chapter_checkbox_toggled",
        "_on_output_toggle",
        "_on_output_changed",
        "_refresh_output_count",
        "_open_output_types_dialog",
        "_load_previous_settings",
        "_start_conversion",
        "_start_diagnostic",
        "_run_diagnostic",
        "_finalize_diagnostic",
        "_cancel_diagnostic",
        "_ask_password_if_needed",
        "_parse_int",
        "handle_dropped_file",
    )

    def test_no_dead_legacy_methods_remain(self):
        src = _src(_CONVERT_VIEW)
        for name in self.DEAD_METHODS:
            assert f"def {name}" not in src, (
                f"{name} was deleted in V18.20.4.1 (W-b13) — the V18.20.3.14 "
                "crash class must stay closed structurally"
            )

    def test_no_dead_none_widget_attributes_remain(self):
        """The V11.0.0 None-widget attributes that only the dead methods
        dereferenced are gone; convert_btn/test_btn STAY (pinned by the
        .3.14 regression tests, routed through _set_cta_enabled)."""
        src = _src(_CONVERT_VIEW)
        for attr in (
            "self.input_picker",
            "self.full_ocr_cb",
            "self.select_chapters_cb",
            "self.page_start",
            "self.page_end",
            "self.load_prev_btn",
            "self.output_types_btn",
            "self.output_count_lbl",
            "self._chapter_dialog",
            "self._type_cards",
            "self._type_head",
            "self._doc_head",
            "self._selected_type",
            "self._diagnostic_thread",
            "self._diagnostic_cancel",
        ):
            assert attr not in src, f"dead attribute {attr} must be gone"
        assert "self.convert_btn = None" in src  # .3.14 contract preserved
        assert "self.test_btn = None" in src

    def test_live_methods_survived(self):
        """The deletion must not take live plumbing with it."""
        src = _src(_CONVERT_VIEW)
        for name in (
            "def _register_callbacks",
            "def _on_tool_clicked",
            "def _open_wizard",
            "def _on_complete",
            "def _on_status",
            "def _set_cta_enabled",
            "def refresh_theme",
            "def apply_ui_preferences",
            "def _cancel_conversion",
            "def _cancel_any_operation",
            "def _wire_bridge",
        ):
            assert name in src, f"live method {name} must survive W-b13"

    def test_file_parses(self):
        """Headless syntax guard for the big deletion (PySide6 not needed
        for ast.parse)."""
        ast.parse(_src(_CONVERT_VIEW))

    def test_no_dangling_imports_for_deleted_code(self):
        """The imports that only served the dead block are gone."""
        src = _src(_CONVERT_VIEW)
        for gone in (
            "import threading",
            "from typing import Any",
            "SimpleWorker",
            "SOURCE_PRESETS",
            "ChapterSelectorDialog",
            "request_conversion",
            "request_diagnostic",
        ):
            assert gone not in src, f"stale import/declaration: {gone}"


# ═══════════════════════════════════════════════════════════════════════════
# W-a2 — the fabricated coverage stat
# ═══════════════════════════════════════════════════════════════════════════


class TestWa2MeasuredCoverage:
    def test_no_placeholder_092(self):
        # V0.4.26 (Phase 3 commit 3): union read — the block moved, so the
        # absence pins must cover its new home too (same intent, wider net).
        src = _strip_comments(_src(_CONVERTER)) + "\n" + _strip_comments(_src(_FINALIZATION))
        assert "coverage=0.92" not in src, "the fabricated 0.92 placeholder must be gone (W-a2)"
        assert "Placeholder — will be updated" not in src

    def test_library_call_reads_measured_coverage(self):
        """The add_book call passes the value read from the quality
        report's totals.avg_coverage (same source the diagnostic reads)."""
        # V0.4.26 (Phase 3 commit 3): the block moved VERBATIM to
        # run_library_tracking in conversion/finalization.py (the last
        # function in that module) — union read + the block's own tail
        # (the partial-failure handler) as the end bound; same asserted
        # content (the established repoint discipline).
        src = _strip_comments(_src(_CONVERTER)) + "\n" + _strip_comments(_src(_FINALIZATION))
        lib_start = src.find('"library tracking"')
        assert lib_start != -1
        _lib_tail = '_record_partial_failure("Library tracking", e)'
        lib_end = src.find(_lib_tail, lib_start)
        assert lib_end != -1
        block = src[lib_start : lib_end + len(_lib_tail)]
        assert "coverage=_cov_lib" in block
        assert 'get("totals", {})' in block
        assert 'get("avg_coverage")' in block
        assert "isinstance(_cov_val_lib, (int, float))" in block, (
            "non-numeric/missing reports must degrade to None, never a guess"
        )

    def test_library_manager_signature_is_optional(self):
        src = _src(_LIBRARY)
        assert "coverage: float | None = None" in src

    def test_library_manager_stores_none_safely(self):
        src = _src(_LIBRARY)
        assert "isinstance(coverage, (int, float))" in src
        assert "round(coverage, 3)" in src


class TestWa2LibraryBehavior:
    """Pure-Python behavioral tests (no Qt) for the honest coverage."""

    @pytest.fixture
    def lib_file(self, tmp_path, monkeypatch):
        f = tmp_path / "library.json"
        monkeypatch.setattr("core.pipeline.library_manager._LIBRARY_FILE", f)
        return f

    def test_real_coverage_rounds_and_persists(self, lib_file):
        from core.pipeline.library_manager import LibraryManager

        lib = LibraryManager()
        lib.add_book("Book A", coverage=0.87654, chapters_processed=3)
        stored = lib.get_book("Book A")["coverage"]
        assert stored == 0.877
        # persisted to disk
        import json

        data = json.loads(lib_file.read_text(encoding="utf-8"))
        assert data["books"]["Book A"]["coverage"] == 0.877

    def test_unknown_coverage_stored_as_none(self, lib_file):
        from core.pipeline.library_manager import LibraryManager

        lib = LibraryManager()
        lib.add_book("Book B", coverage=None, chapters_processed=2)
        assert lib.get_book("Book B")["coverage"] is None

    def test_stats_average_only_measured_books(self, lib_file):
        from core.pipeline.library_manager import LibraryManager

        lib = LibraryManager()
        lib.add_book("Book C", coverage=0.5, chapters_processed=1)
        lib.add_book("Book D", coverage=None, chapters_processed=1)
        lib.add_book("Book E", coverage=1.0, chapters_processed=1)
        stats = lib.get_stats()
        # only the two measured books count: (0.5 + 1.0) / 2
        assert stats["avg_coverage"] == 0.75
        assert stats["total_books"] == 3

    def test_stats_all_unknown_stay_zero(self, lib_file):
        from core.pipeline.library_manager import LibraryManager

        lib = LibraryManager()
        lib.add_book("Book F", coverage=None, chapters_processed=1)
        lib.add_book("Book G", coverage=None, chapters_processed=1)
        assert lib.get_stats()["avg_coverage"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# W-b2 — hardware-monitor callbacks cross the thread boundary safely
# ═══════════════════════════════════════════════════════════════════════════


class TestWb2HwMonitorThreading:
    def test_log_callback_routes_through_bridge(self):
        """The monitor's log callback must NOT call self._on_log directly
        (a QTextBrowser write from the polling thread)."""
        src = _src(_WIZARD)
        start = src.find("def _start_hardware_monitor")
        assert start != -1
        body = src[start : src.find("\n    def ", start)]
        assert "self.bridge.emit_log" in body, (
            "log_callback must emit via the bridge signal (queued to the main thread)"
        )
        assert "lambda msg, level: self._on_log(msg, level)" not in body

    def test_auto_pause_is_a_main_thread_signal(self):
        src = _src(_WIZARD)
        assert "auto_pause_requested = Signal()" in src, "the class-level signal must exist"
        start = src.find("def _start_hardware_monitor")
        body = src[start : src.find("\n    def ", start)]
        assert "self.auto_pause_requested.emit()" in body, (
            "_auto_pause must EMIT the signal, not touch widgets/Qt state from the polling thread"
        )
        # the slot: main-thread execution, logs + cancels
        slot = src.find("def _on_auto_pause")
        assert slot != -1
        slot_body = src[slot : src.find("\n    def ", slot)]
        assert "self._on_log" in slot_body
        assert "self.controller.cancel_conversion()" in slot_body

    def test_slot_is_wired(self):
        src = _src(_WIZARD)
        assert "self.auto_pause_requested.connect(self._on_auto_pause)" in src


# ═══════════════════════════════════════════════════════════════════════════
# W-b3 — idempotent bridge connections (no duplicate delivery)
# ═══════════════════════════════════════════════════════════════════════════


class TestWb3IdempotentBridge:
    def test_all_connectors_route_through_connect_unique(self):
        src = _src(_BRIDGE)
        for connector in (
            "def connect_progress",
            "def connect_status",
            "def connect_log",
            "def connect_complete",
        ):
            pos = src.find(connector)
            assert pos != -1, f"{connector} missing"
            body = src[pos : src.find("\n    def ", pos)]
            assert "_connect_unique" in body, (
                f"{connector} must be idempotent (W-b3: wizard re-runs "
                "duplicated every signal — double completion modals, double "
                "post-completion action)"
            )

    def test_connect_unique_disconnects_first(self):
        src = _src(_BRIDGE)
        pos = src.find("def _connect_unique")
        assert pos != -1
        body = src[pos : src.find("\n    def ", pos)]
        assert "signal.disconnect(slot)" in body
        assert "TypeError" in body and "RuntimeError" in body, (
            "both not-connected (TypeError) and dead-receiver (RuntimeError) must be tolerated"
        )


# ═══════════════════════════════════════════════════════════════════════════
# W-b4 — closing the wizard stops the monitor + elapsed timer
# ═══════════════════════════════════════════════════════════════════════════


class TestWb4WizardCloseStopsMonitor:
    def test_close_event_stops_both(self):
        src = _src(_WIZARD)
        pos = src.find("def closeEvent")
        assert pos != -1
        body = src[pos : src.find("\n    def ", pos)]
        assert "self._stop_hardware_monitor()" in body, (
            "closeEvent must stop the hw monitor (was orphaned forever when "
            "the wizard closed mid-conversion — _on_complete was the only "
            "stop path and closeEvent disconnects its delivery signals)"
        )
        assert "self._stop_elapsed_timer()" in body

    def test_stops_happen_before_bridge_disconnect(self):
        """Stopping first matters: the monitor's final snapshot is logged
        via the still-connected bridge signals."""
        src = _src(_WIZARD)
        pos = src.find("def closeEvent")
        body = src[pos : src.find("\n    def ", pos)]
        stop_pos = body.find("self._stop_hardware_monitor()")
        disc_pos = body.find("sig.disconnect()")
        assert stop_pos != -1 and disc_pos != -1
        assert stop_pos < disc_pos


# ═══════════════════════════════════════════════════════════════════════════
# Behavioral layer (offscreen Qt; skips without PySide6)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestWb3BridgeBehavior:
    @pytest.fixture(scope="class")
    def app(self):
        from PySide6.QtWidgets import QApplication

        inst = QApplication.instance() or QApplication([])
        yield inst

    def test_repeated_connect_delivers_once(self, app):
        from ui_qt.controller_bridge import QtControllerBridge

        bridge = QtControllerBridge()
        calls: list[str] = []

        def slot(msg: str, level: str) -> None:
            calls.append(msg)

        bridge.connect_log(slot)
        bridge.connect_log(slot)  # re-run with the SAME slot (W-b3 "Convert again")
        bridge.emit_log("one", "INFO")
        assert calls == ["one"], (
            "a repeated connect_* of the same slot must not duplicate delivery (W-b3)"
        )

    def test_different_slots_both_deliver(self, app):
        from ui_qt.controller_bridge import QtControllerBridge

        bridge = QtControllerBridge()
        a: list[str] = []
        b: list[str] = []
        bridge.connect_log(lambda msg, level: a.append(msg))
        bridge.connect_log(lambda msg, level: b.append(msg))
        bridge.emit_log("x", "INFO")
        assert a == ["x"] and b == ["x"], "idempotency must only dedupe the SAME slot"
