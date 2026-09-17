"""V18.20.4.5 (P4-a) — W-b5 + T-b2 source pins for
``ui_qt/views/service_dialogs/base_dialog.py``.

**W-b5** — the four service dialogs that still did their blocking work on
the UI thread with ``QApplication.processEvents()`` repaint hacks (the
OCR per-file loop, the Summarization pre-flight + LLM loop, the
QuickConvert extraction + write, the PDF/DOCX cut) now run that work on
a ``SimpleWorker`` background thread, with per-step updates routed
through the worker's queued ``progress`` signal (BaseWorker contract:
emitting from the worker thread queues the slot onto the main thread)
and completion landing in main-thread ``_on_x_finished`` handlers.

**T-b2** — every worker-owning dialog in the file gets a ``closeEvent``
guard: closing while a QThread worker runs used to abort the process
("QThread: Destroyed while thread is still running") or fire queued
slots into dead widgets. The guards ask for confirmation and, on "close
anyway", detach the worker (disconnect its signals; unparent raw
QThreads parented to the dialog).

PySide6 is NOT installed in the headless rig, so these are SOURCE PINS
(read the .py source, assert on content + ordering, never line numbers)
following the house pattern of tests/test_v182043_p2_settings_integrity.py
and tests/test_v182044_p3_tts_subprocess.py. Hermetic: nothing is
imported from ui_qt (the module import chain needs Qt).

V18.20.4.6 (P5 / O-b2) EVOLVED PIN — slicing follows the code, assertions
unchanged (house precedent: the V18.20.4.5 test_v182043 P2 anchor move,
the P5-1b evolution of test_v182045_p4b for the wizard split).
base_dialog.py was decomposed into
ui_qt/views/service_dialogs/dialogs/ (one module per dialog + shared.py
for the cross-dialog plumbing; class bodies moved VERBATIM) and is now a
pure re-export facade. ``SRC`` below is therefore the union of the facade
+ every dialogs/*.py (whole-family invariants: the 10 closeEvent
guards, zero processEvents, the module-level SimpleWorker import keep
spanning the entire dialog family), and per-class / per-helper slicing
reads the module that defines the name via the class→file map. No
assertion, string literal, or count changed.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVICE_DIALOGS = PROJECT_ROOT / "ui_qt" / "views" / "service_dialogs"
DIALOGS_DIR = _SERVICE_DIALOGS / "dialogs"

# V18.20.4.6 (P5 / O-b2): SRC = facade + every dialogs/*.py (sorted for
# determinism) — the split dialog family read as one virtual file.
SRC = "\n".join(
    [(_SERVICE_DIALOGS / "base_dialog.py").read_text(encoding="utf-8")]
    + sorted(p.read_text(encoding="utf-8") for p in DIALOGS_DIR.glob("*.py"))
)

# module → source, for name-based slicing into the defining module
_MODULE_SRC = {
    p.name: p.read_text(encoding="utf-8") for p in DIALOGS_DIR.glob("*.py")
}

# class name → the dialogs/ module that defines it (split map)
_CLASS_TO_FILE = {
    "PlainTextTextEdit": "shared.py",
    "BaseServiceDialog": "shared.py",
    "OcrServiceDialog": "ocr_service_dialog.py",
    "SummarizationServiceDialog": "summarization_service_dialog.py",
    "TranslationServiceDialog": "translation_service_dialog.py",
    "TtsServiceDialog": "tts_service_dialog.py",
    "QuickConvertDialog": "quick_convert_dialog.py",
    "PdfDocxCutterDialog": "pdf_docx_cutter_dialog.py",
    "MarkdownStylerDialog": "markdown_styler_dialog.py",
    "_PacketWorker": "packets_tool_dialog.py",
    "PacketsToolDialog": "packets_tool_dialog.py",
    "_HallucinationAuditWorker": "hallucination_audit_dialog.py",
    "HallucinationAuditDialog": "hallucination_audit_dialog.py",
    "ImageExtractorDialog": "image_extractor_dialog.py",
    "TranscribeServiceDialog": "transcribe_service_dialog.py",
}

# module-level function name → the dialogs/ module that defines it
_FUNC_TO_FILE = {
    "_show_success_modal": "shared.py",
    "_worker_is_running": "shared.py",
    "_detach_worker_signals": "shared.py",
    "_confirm_close_with_running_worker": "shared.py",
}


def _defining_src(name: str) -> str:
    """Source of the dialogs/ module that defines ``name`` (split map)."""
    fname = _CLASS_TO_FILE.get(name) or _FUNC_TO_FILE.get(name)
    assert fname is not None, f"no split-map entry for {name!r}"
    return _MODULE_SRC[fname]


# ── source slicing helpers (content + ordering, never line numbers) ─────────

def _class_src(name: str) -> str:
    """Return the source of top-level ``class <name>`` (up to the next
    top-level class/def) — read from the dialogs/ module that defines it
    (V18.20.4.6 split: base_dialog.py is a pure facade)."""
    file_src = _defining_src(name)
    m = re.search(rf"^class {re.escape(name)}\b.*$", file_src, re.M)
    assert m is not None, f"class not found: {name}"
    rest = file_src[m.end():]
    nxt = re.search(r"^(?=class |def )", rest, re.M)
    return file_src[m.start():m.end() + (nxt.start() if nxt else len(rest))]


def _method_src(class_src: str, name: str) -> str:
    """Return the source of ``def <name>`` inside ``class_src`` (up to the
    next method definition). Nested closures (8-space indent) never match."""
    m = re.search(rf"^    def {re.escape(name)}\(", class_src, re.M)
    assert m is not None, f"method not found: {name}"
    rest = class_src[m.end():]
    nxt = re.search(r"^    def ", rest, re.M)
    return class_src[m.start():m.end() + (nxt.start() if nxt else len(rest))]


def _module_func_src(name: str) -> str:
    """Return the source of a top-level ``def <name>`` (up to the next
    top-level class/def — searched AFTER the def's own first line) — read
    from the dialogs/ module that defines it (V18.20.4.6 split)."""
    file_src = _defining_src(name)
    m = re.search(rf"^def {re.escape(name)}\(", file_src, re.M)
    assert m is not None, f"module function not found: {name}"
    rest = file_src[m.end():]
    nxt = re.search(r"^(?=class |def )", rest, re.M)
    return file_src[m.start():m.end() + (nxt.start() if nxt else len(rest))]


def _close_event_src(class_name: str) -> str:
    return _method_src(_class_src(class_name), "closeEvent")


# The four W-b5 dialogs: (class, _do_* action method, _*_work worker body,
# progress/finished/failed handler basenames).
W_B5_DIALOGS = [
    ("OcrServiceDialog", "_do_convert", "_ocr_work", "_on_convert"),
    ("SummarizationServiceDialog", "_do_summarize", "_summarize_work",
     "_on_summarize"),
    ("QuickConvertDialog", "_do_convert", "_convert_work", "_on_convert"),
    ("PdfDocxCutterDialog", "_do_cut", "_cut_work", "_on_cut"),
]

# Widget attribute names that must NEVER be referenced from a worker body.
_WIDGET_ATTRS = (
    "self.status_label", "self.action_btn", "self.progress_bar",
    "self.again_btn", "self.out_edit", "self.in_edit", "self.file_list",
    "self.engine_combo", "self.fmt_combo", "self.range_edit",
    "self.model_combo", "self.quality_combo", "self.obsidian_chk",
    "self.text_input", "self.tabs", "self.process_btn", "self.gen_btn",
    "self.audit_btn", "self.results_table",
)

# Every worker-owning dialog that needs a T-b2 closeEvent guard.
T_B2_DIALOGS = [
    "BaseServiceDialog",
    "OcrServiceDialog",
    "SummarizationServiceDialog",
    "QuickConvertDialog",
    "PdfDocxCutterDialog",
    "TtsServiceDialog",
    "PacketsToolDialog",
    "HallucinationAuditDialog",
    "ImageExtractorDialog",
    "TranscribeServiceDialog",
]


# ═══════════════════════════════════════════════════════════════════════════
# W-b5 — the four offloaded work paths
# ═══════════════════════════════════════════════════════════════════════════

class TestWb5WorkerSpawns:
    """Each _do_* spawns a SimpleWorker with the shared W-b5 shape."""

    def test_each_do_method_spawns_simple_worker(self):
        for cls, do, work, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert "self._worker = SimpleWorker(" in do_src, f"{cls}.{do}"
            # The spawn targets THIS dialog's _x_work method.
            assert f"self.{work}(" in do_src, f"{cls}.{do} → {work}"

    def test_spawn_lambda_passes_progress_emit(self):
        # report= is the worker's progress.emit (the BaseWorker queued
        # signal contract — emitting from the worker thread queues the
        # slot onto the main thread).
        for cls, do, _w, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert "report=self._worker.progress.emit" in do_src, cls

    def test_spawn_lambda_late_binding_comment(self):
        # House rule: the lambda referencing self._worker needs the
        # one-line closure late-binding explanation at every spawn site.
        for cls, do, _w, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert "late-bind" in do_src, f"{cls}.{do} closure comment"

    def test_worker_signal_connections(self):
        for cls, do, _w, h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert f"self._worker.progress.connect(self.{h}_progress)" in do_src, cls
            assert f"self._worker.finished.connect(self.{h}_finished)" in do_src, cls
            assert f"self._worker.failed.connect(self.{h}_failed)" in do_src, cls
            assert "self._worker.start()" in do_src, cls

    def test_reentrancy_guard_before_spawn(self):
        # The guard must exist AND precede the spawn (a second click while
        # a worker runs must be a no-op, not a second worker).
        for cls, do, _w, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            guard = ("if self._worker is not None and "
                     "self._worker.is_running():")
            assert guard in do_src, f"{cls}.{do} re-entrancy guard"
            assert do_src.index(guard) < do_src.index(
                "self._worker = SimpleWorker("), f"{cls}.{do} guard order"

    def test_worker_initialized_in_init(self):
        # The guard would AttributeError without the __init__ init.
        for cls in ("OcrServiceDialog", "SummarizationServiceDialog",
                    "QuickConvertDialog", "PdfDocxCutterDialog"):
            assert ("self._worker: SimpleWorker | None = None"
                    in _class_src(cls)), cls

    def test_button_disabled_and_progress_visible_before_spawn(self):
        for cls, do, _w, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert "self.action_btn.setEnabled(False)" in do_src, cls
            assert "Processing…" in do_src, cls


class TestWb5WorkerBodies:
    """The _x_work bodies are pure work — zero widget access."""

    def test_work_methods_exist_with_report_param(self):
        for cls, _do, work, _h in W_B5_DIALOGS:
            work_src = _method_src(_class_src(cls), work)
            assert "report=None" in work_src, f"{cls}.{work} report kwarg"

    def test_work_bodies_never_touch_widgets(self):
        for cls, _do, work, _h in W_B5_DIALOGS:
            work_src = _method_src(_class_src(cls), work)
            for attr in _WIDGET_ATTRS:
                assert attr not in work_src, f"{cls}.{work} touches {attr}"
            # Docstrings may MENTION the old QApplication hack; an actual
            # import or invocation is what's forbidden in the worker body.
            assert ("from PySide6.QtWidgets import QApplication"
                    not in work_src), f"{cls}.{work} QApplication import"
            assert re.search(r"^[ \t]+QApplication\.processEvents\(\)",
                             work_src, re.M) is None, f"{cls}.{work} call"
            assert "_show_success_modal(" not in work_src, f"{cls}.{work} modal"

    def test_work_bodies_return_plain_result_dicts(self):
        shapes = {
            "OcrServiceDialog._ocr_work":
                ('"results"', '"total"', '"pages_desc"'),
            "SummarizationServiceDialog._summarize_work":
                ('"results"', '"total"', '"persist_model"', '"file_arg"'),
            "QuickConvertDialog._convert_work":
                ('"success"', '"status"'),
            "PdfDocxCutterDialog._cut_work":
                ('"error"', '"out_path"'),
        }
        for cls, _do, work, _h in W_B5_DIALOGS:
            work_src = _method_src(_class_src(cls), work)
            for key in shapes[f"{cls}.{work}"]:
                assert key in work_src, f"{cls}.{work} result key {key}"

    def test_progress_reported_from_work_bodies(self):
        # Per-file/per-step updates go through report(pct, msg). The
        # cutter has no per-page updates to stream (the old code had none
        # either) — it only ACCEPTS report for pattern parity.
        for cls, _do, work, _h in W_B5_DIALOGS:
            if cls == "PdfDocxCutterDialog":
                continue
            work_src = _method_src(_class_src(cls), work)
            assert re.search(r"report\(\s*(int\(|0)", work_src), f"{cls}.{work}"

    def test_cutter_work_keeps_old_error_strings(self):
        work_src = _method_src(_class_src("PdfDocxCutterDialog"), "_cut_work")
        # The exact legacy strings, now surviving the thread hop as error
        # results instead of direct status writes.
        assert "❌ Only .pdf and .docx are supported." in work_src
        assert 'f"❌ Error: {type(e).__name__}: {e}"' in work_src


class TestWb5Handlers:
    """Main-thread handlers: progress → status text, finished → modal."""

    def test_progress_handlers_only_set_status_text(self):
        for cls, _do, _w, h in W_B5_DIALOGS:
            prog_src = _method_src(_class_src(cls), f"{h}_progress")
            assert "self.status_label.setText(msg)" in prog_src, f"{cls}.{h}_progress"
            assert "processEvents" not in prog_src, f"{cls}.{h}_progress"

    def test_finished_handlers_show_success_modal(self):
        modals = {
            "OcrServiceDialog": "🔍 OCR Complete",
            "SummarizationServiceDialog": "Σ Summarization Complete",
            "QuickConvertDialog": "📄 Document → Markdown Complete",
            "PdfDocxCutterDialog": "✂ Cut Complete",
        }
        # Only OCR + Summarization have a busy progress bar to hide
        # (QuickConvert / Cutter never had one).
        progress_bar_dialogs = ("OcrServiceDialog", "SummarizationServiceDialog")
        for cls, _do, _w, h in W_B5_DIALOGS:
            fin_src = _method_src(_class_src(cls), f"{h}_finished")
            assert "_show_success_modal(" in fin_src, cls
            assert modals[cls] in fin_src, cls
            if cls in progress_bar_dialogs:
                # The busy bar is hidden on completion.
                assert "self.progress_bar.setVisible(False)" in fin_src, cls

    def test_failed_handlers_reenable_the_button(self):
        for cls, _do, _w, h in W_B5_DIALOGS:
            fail_src = _method_src(_class_src(cls), f"{h}_failed")
            assert "self.action_btn.setEnabled(True)" in fail_src, cls

    def test_finished_handlers_touch_widgets_not_work(self):
        # The completion UI lives on the main thread (finished handler),
        # not in the worker body — assert the handlers reference widgets.
        for cls, _do, _w, h in W_B5_DIALOGS:
            fin_src = _method_src(_class_src(cls), f"{h}_finished")
            assert "self.status_label.setText" in fin_src, cls


class TestWb5GlobalInvariants:
    """Whole-file invariants for the W-b5 release."""

    def test_zero_actual_process_events_invocations(self):
        # Every remaining mention must be inside a comment/docstring.
        # An actual call is an indented statement: ^<ws>QApplication.processEvents()
        assert re.search(r"^[ \t]+QApplication\.processEvents\(\)", SRC,
                         re.M) is None

    def test_no_qapplication_import_inside_the_four_do_methods(self):
        for cls, do, _w, _h in W_B5_DIALOGS:
            do_src = _method_src(_class_src(cls), do)
            assert "import QApplication" not in do_src, f"{cls}.{do}"

    def test_each_work_body_is_connected_to_its_finished_handler(self):
        # The worker returns a dict; the finished handler consumes it with
        # .get(...) (shape contract between the thread sides).
        for cls, _do, _w, h in W_B5_DIALOGS:
            fin_src = _method_src(_class_src(cls), f"{h}_finished")
            assert "result.get(" in fin_src, f"{cls}.{h}_finished"

    def test_simpleworker_import_is_module_level(self):
        # The module imports SimpleWorker once at the top (line ~58) — the
        # four dialogs rely on it, not on function-local imports.
        assert re.search(
            r"^from ui_qt\.components\.simple_worker import SimpleWorker$",
            SRC, re.M) is not None


# ═══════════════════════════════════════════════════════════════════════════
# W-b5 — Summarization specifics (_call_llm report + main-thread refresh)
# ══════════════════════════════════════════════════════════════════════════════

class TestWb5SummarizationSpec:
    """The spec'd SummarizationServiceDialog details."""

    def test_call_llm_accepts_report_kwarg(self):
        m = re.search(r"^    def _call_llm\(([^)]*)\)", SRC, re.M)
        assert m is not None, "_call_llm signature not found"
        assert "report=None" in m.group(1), m.group(1)

    def test_call_llm_on_chunk_routes_through_report(self):
        # With report provided, chunks ride the queued signal instead of
        # touching status_label; the legacy no-report path keeps the
        # direct status-label update (main-thread callers only). The
        # docstring may mention the old hack — the invocation is gone.
        call_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_call_llm")
        assert "if report is not None:" in call_src
        assert "report(0, html)" in call_src
        assert "self.status_label.setText(html)" in call_src
        assert re.search(r"^[ \t]+QApplication\.processEvents\(\)",
                         call_src, re.M) is None

    def test_call_llm_forwarded_by_worker_body(self):
        work_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_summarize_work")
        assert "report=report" in work_src

    def test_preflight_reports_verifying_model(self):
        work_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_summarize_work")
        assert 'report(0, "Verifying model…")' in work_src
        assert "self._fetch_installed_models(timeout=3.0)" in work_src

    def test_model_missing_returns_error_result(self):
        work_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_summarize_work")
        assert '"model_missing": True' in work_src
        assert '"error_html"' in work_src

    def test_model_combo_refresh_only_on_main_thread(self):
        # _refresh_models touches the combo + status label — it must be
        # called from the FINISHED handler, never from the worker body.
        work_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_summarize_work")
        fin_src = _method_src(_class_src("SummarizationServiceDialog"),
                              "_on_summarize_finished")
        assert "_refresh_models" not in work_src
        assert "self._refresh_models()" in fin_src
        # And the finished handler shows the worker-built error HTML first
        # (same setText-then-refresh order as the old inline code).
        assert fin_src.index('"model_missing"') < fin_src.index(
            "self._refresh_models()")

    def test_model_persistence_in_finished_handler(self):
        # s.set("summarisation.model", ...) + save happen on the MAIN
        # thread now, gated on the worker-computed persist flag (V11.19
        # semantics: only when a concrete model was picked).
        work_src = _method_src(_class_src("SummarizationServiceDialog"),
                               "_summarize_work")
        fin_src = _method_src(_class_src("SummarizationServiceDialog"),
                              "_on_summarize_finished")
        assert '"persist_model"' in work_src
        assert 'result.get("persist_model")' in fin_src
        assert 's.set("summarisation.model"' in fin_src
        assert 's.set("summarisation.model"' not in work_src

    def test_worker_receives_plain_captured_values(self):
        # Everything the worker captures is a plain value (no widget reads
        # inside the thread): the spawn passes locals, and out_folder /
        # out_path are normalized to None per mode before the spawn.
        do_src = _method_src(_class_src("SummarizationServiceDialog"),
                             "_do_summarize")
        assert "if is_multi:" in do_src
        assert "out_path = None" in do_src
        assert "out_folder = None" in do_src


class TestWb5QuickConvertSpec:
    """The spec'd QuickConvertDialog details (anydoc log_callback)."""

    def test_anydoc_log_callback_wraps_report(self):
        # report is (int, str); anydoc's log_callback is (str) — the worker
        # wraps: lambda msg: report(0, msg). The old _cb definition (which
        # wrote status_label + processEvents on the UI thread) is gone.
        work_src = _method_src(_class_src("QuickConvertDialog"),
                               "_convert_work")
        assert "lambda msg: report(0, msg)" in work_src
        assert "log_callback=log_cb" in work_src
        assert "def _cb" not in work_src

    def test_validation_stays_in_do_method(self):
        # Validation + engine/format checks are UI-thread early-returns
        # (status text + return, before the worker spawn).
        do_src = _method_src(_class_src("QuickConvertDialog"), "_do_convert")
        assert "❌ AnyDoc does not support" in do_src
        assert "❌ markitdown does not support" in do_src
        assert do_src.index("❌ AnyDoc does not support") < do_src.index(
            "self._worker = SimpleWorker(")

    def test_legacy_error_strings_survive(self):
        work_src = _method_src(_class_src("QuickConvertDialog"),
                               "_convert_work")
        assert "AnyDoc is not installed. Run: pip install anydoc" in work_src
        assert "⚠️ Very little text extracted." in work_src
        assert 'f"❌ Write failed: {type(e).__name__}: {e}"' in work_src


# ═══════════════════════════════════════════════════════════════════════════
# T-b2 — closeEvent guards for running workers
# ═══════════════════════════════════════════════════════════════════════════

class TestTb2CloseEventGuards:
    """Every worker-owning dialog has a closeEvent guard."""

    def test_close_event_count(self):
        # Exactly the 10 worker-owning dialogs (Base + the four W-b5
        # dialogs + Tts + Packets + Hallucination + ImageExtractor +
        # Transcribe). MarkdownStylerDialog has no worker → no guard.
        assert SRC.count("def closeEvent") == len(T_B2_DIALOGS)
        assert SRC.count("def closeEvent") == 10

    def test_every_worker_dialog_has_close_event(self):
        for cls in T_B2_DIALOGS:
            assert "def closeEvent" in _class_src(cls), cls

    def test_markdown_styler_has_no_close_event(self):
        # Deterministic + instant (no worker, self._worker is dead code) —
        # deliberately untouched by T-b2.
        cls_src = _class_src("MarkdownStylerDialog")
        assert "def closeEvent" not in cls_src
        assert "SimpleWorker(" not in cls_src

    def test_each_guard_shape(self):
        # Worker reference + shared confirm guard + event.ignore() on veto
        # + super() delegation. TtsServiceDialog guards its PREVIEW worker
        # first and delegates the main-worker guard to the base class.
        for cls in T_B2_DIALOGS:
            ce = _close_event_src(cls)
            assert "_confirm_close_with_running_worker(self," in ce, f"{cls} guard call"
            assert ("self._worker" in ce or "self._preview_worker" in ce), \
                f"{cls} worker reference"
            assert "event.ignore()" in ce, f"{cls} event.ignore()"
            assert "super().closeEvent(event)" in ce, f"{cls} super()"
            assert "V18.20.4.5 (T-b2)" in ce, f"{cls} tag"

    def test_each_guard_cites_the_abort_class(self):
        # Every guard comment explains the old defect class (whitespace-
        # and comment-marker-normalized — comment wrapping is free).
        pat = re.compile(r"QThread:\s*Destroyed\s*while\s*thread\s*is\s*"
                         r"still\s*running")
        for cls in T_B2_DIALOGS:
            flat = re.sub(r"[\s#]+", " ", _close_event_src(cls))
            assert pat.search(flat), cls

    def test_base_service_dialog_single_guard_covers_subclasses(self):
        # ONE guard on the base class; the subclasses (Translation /
        # TTS main worker) inherit it and none of them override
        # closeEvent themselves.
        base = _class_src("BaseServiceDialog")
        assert base.count("def closeEvent") == 1
        for cls in ("TranslationServiceDialog", "TtsServiceDialog"):
            sub = _class_src(cls)
            # TtsServiceDialog DOES override — to guard the preview worker
            # first — but must delegate to the base guard via super().
            if "def closeEvent" in sub:
                assert "super().closeEvent(event)" in _method_src(sub, "closeEvent")
            else:
                assert "closeEvent" not in sub


class TestTb2SharedGuardHelper:
    """The shared _confirm_close_with_running_worker machinery."""

    def test_helper_exists_and_prompts(self):
        helper = _module_func_src("_confirm_close_with_running_worker")
        assert "QMessageBox.question(" in helper
        assert '"Work in progress"' in helper
        assert "The task will continue but its result will be discarded." in helper
        assert "QMessageBox.Yes | QMessageBox.No, QMessageBox.No" in helper
        # No → the caller vetoes (event.ignore); Yes → detach + proceed.
        assert "if ret != QMessageBox.Yes:" in helper
        assert "_detach_worker_signals(worker)" in helper

    def test_detach_disconnects_all_worker_signal_shapes(self):
        detach = _module_func_src("_detach_worker_signals")
        for sig in ("finished", "failed", "progress", "done_signal",
                    "log_signal"):
            assert f'"{sig}"' in detach, sig
        assert "sig.disconnect()" in detach

    def test_detach_rearms_simpleworker_autodelete(self):
        # The blanket disconnect() also removes SimpleWorker's internal
        # finished/failed → deleteLater wiring; it must be re-armed so the
        # detached worker still frees itself.
        detach = _module_func_src("_detach_worker_signals")
        assert "isinstance(worker, SimpleWorker)" in detach
        assert "worker.deleteLater()" in detach

    def test_detach_unparents_raw_qthread_workers(self):
        # _PacketWorker/_HallucinationAuditWorker are constructed with
        # parent=dialog — unparenting is what actually prevents the
        # "QThread: Destroyed while thread is still running" abort when
        # the dialog tree is deleted.
        detach = _module_func_src("_detach_worker_signals")
        assert "isinstance(worker, QThread)" in detach
        assert "worker.setParent(None)" in detach

    def test_worker_is_running_supports_both_shapes(self):
        check = _module_func_src("_worker_is_running")
        # Raw QThread workers (isRunning) AND BaseWorker/SimpleWorker
        # (is_running) — plus the None short-circuit.
        assert "worker.isRunning()" in check
        assert "worker.is_running()" in check
        assert "if worker is None:" in check


class TestTb2RawQThreadWorkers:
    """The two raw-QThread dialogs keep their workers guarded too."""

    def test_packets_worker_still_qthread_with_signals(self):
        # Unchanged worker class (V13.23.0) — the guard just adapts to it.
        w = _class_src("_PacketWorker")
        assert "class _PacketWorker(QThread):" in w
        assert "done_signal" in w
        assert "log_signal" in w
        dlg = _class_src("PacketsToolDialog")
        assert "self._worker = _PacketWorker(" in dlg

    def test_hallucination_worker_still_qthread(self):
        w = _class_src("_HallucinationAuditWorker")
        assert "class _HallucinationAuditWorker(QThread):" in w
        assert "done_signal" in w
        dlg = _class_src("HallucinationAuditDialog")
        assert "self._worker = _HallucinationAuditWorker(" in dlg


class TestTb2TtsPreviewWorker:
    """TtsServiceDialog's preview worker is now guardable."""

    def test_preview_worker_stored_on_self(self):
        # Was a function-local `worker` — unguardable. Now it lives on
        # self so closeEvent can ask before discarding a generating clip.
        dlg = _class_src("TtsServiceDialog")
        assert "self._preview_worker: SimpleWorker | None = None" in dlg
        preview = _method_src(dlg, "_on_preview")
        assert "self._preview_worker = SimpleWorker(_do_preview)" in preview
        assert "self._preview_worker.start()" in preview
        # No orphan local spawn left behind.
        assert "\n        worker = SimpleWorker(" not in preview

    def test_tts_close_event_guards_both_workers(self):
        ce = _close_event_src("TtsServiceDialog")
        assert "self._preview_worker" in ce
        assert "_confirm_close_with_running_worker(self, self._preview_worker)" in ce
        # Delegates to BaseServiceDialog's guard for the main worker.
        assert "super().closeEvent(event)" in ce


class TestTb2ExistingWorkersUntouched:
    """The pre-existing SimpleWorker dialogs keep their spawn shape."""

    def test_image_extractor_spawn_unchanged(self):
        dlg = _class_src("ImageExtractorDialog")
        proc = _method_src(dlg, "_on_process")
        assert "self._worker = SimpleWorker(_work)" in proc
        assert "self._worker.progress.connect(self._on_progress)" in proc

    def test_transcribe_spawn_unchanged(self):
        dlg = _class_src("TranscribeServiceDialog")
        proc = _method_src(dlg, "_on_process")
        assert "self._worker = SimpleWorker(_work)" in proc
        assert "self._worker.progress.connect(self._on_progress)" in proc

    def test_base_service_dialog_spawn_unchanged(self):
        # BaseServiceDialog._on_process already used the SimpleWorker
        # pattern (V11.21/V11.29.2) — regression pin.
        dlg = _class_src("BaseServiceDialog")
        proc = _method_src(dlg, "_on_process")
        assert "self._worker = SimpleWorker(self._process, input_data, options)" in proc
        assert "self._worker.finished.connect(self._on_finished)" in proc
        assert "self._worker.failed.connect(self._on_error)" in proc
        assert "self._worker.progress.connect(self._on_progress)" in proc
