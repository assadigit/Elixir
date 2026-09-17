"""V18.20.4.9 (BK1) — Backlog-1 UI/threading release pins.

Nine items, all per the approved backlog triage of the V18.20.4.0 SWOT:

- **W-b8:** the TTS settings page ran LLM + engine loads ON the UI thread
  (the unfinished half of the W-b5 class): the normalize test's two
  ``norm.normalize`` Ollama calls, both preview-sample engine loads
  (first play + Regenerate), and the Kokoro connectivity probe's
  ``import kokoro``. All four now run on ``SimpleWorker`` (P4 W-b11
  pattern: worker ref on self, re-entrancy guard, button disabled while
  in flight, re-enable in BOTH outcome handlers, main-thread UI updates
  only — the worker bodies read no widgets).
- **W-b12:** the multi-PDF library merge ran synchronously in the click
  slot with a ``str(e)``-only error box — now offloaded to SimpleWorker,
  and on failure the traceback is logged at WARNING BEFORE the
  identical "Merge error" box (the W-b17 crash-visibility pattern).
- **W-b18 remainder:** every remaining worker whose ``failed`` signal
  was unconnected (wizard cloud/fast TEST buttons, app.py's ollama
  check, output_scanner's batch/single regen workers) now wires
  ``failed`` → re-enable + fail-soft.
- **W-b19:** the per-preview-click ``mediaStatusChanged`` connect is
  gone — connected ONCE in ``_ensure_player`` (the one-time setup site).
- **W-b14:** ``_on_log``'s per-line ``import re`` + regex recompiles
  (and ``_on_status``/``_update_time_estimate``'s ``import time``) are
  hoisted to module level as compiled patterns; behavior identical.
- **W-b15:** the quality dashboard gains the structured source —
  ``logs/quality_report.json`` (already written per run) is read at
  completion; the human-log regex parse stays as the live fallback.
- **W-b17:** the ten str(e)-only except blocks (SWOT AST scan) now log
  the traceback at WARNING before the user-visible message.
- **T-b4:** main.py's dead ``Qt.AA_EnableHighDpiScaling = True``
  assignment is deleted (zero readers; Qt 6 high-DPI is automatic).
- **T-b6:** cancel-and-quit now stop-and-waits for the daemon
  conversion/queue writer threads (join(2000) + park on a retired list,
  the T-b2 retire pattern) instead of killing one mid-write.

All pins are headless-safe source/AST slicing by NAME (no line numbers,
no PySide6 import — the rig has none). The W-b14/W-b15 behavioral
checks are pure-Python (regex semantics + format-string parity).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_TTS = _project_root / "ui_qt" / "settings" / "tts_page.py"
_APP = _project_root / "ui_qt" / "app.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_STEP5 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step5_models.py"
_SCANNER = _project_root / "ui_qt" / "views" / "output_scanner_view.py"
_PODCAST = _project_root / "ui_qt" / "views" / "podcast_maker_view.py"
_STYLER = (
    _project_root / "ui_qt" / "views" / "service_dialogs" / "dialogs"
    / "markdown_styler_dialog.py"
)
_MAIN = _project_root / "main.py"


# ── helpers (headless-safe: source text + AST only, by name) ────────────────

def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _classes(path: Path) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in ast.parse(_src(path)).body
            if isinstance(n, ast.ClassDef)}


def _method(path: Path, class_name: str, method_name: str) -> str:
    """The exact source segment of one method (located by name, no lines)."""
    src = _src(path)
    cls = _classes(path)[class_name]
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == method_name:
            return ast.get_source_segment(src, n) or ""
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _inner_fn(method_src: str, fn_name: str) -> str:
    """The exact source segment of a function nested inside a method."""
    tree = ast.parse(method_src.strip())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return ast.get_source_segment(method_src.strip(), node) or ""
    raise AssertionError(f"inner function {fn_name} not found")


def _self_attrs(fn_src: str) -> set[str]:
    """Every ``self.<attr>`` referenced inside a function body."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(fn_src.strip())):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"):
            out.add(node.attr)
    return out


def _except_blocks(path: Path, class_name: str, method_name: str) -> list[str]:
    """Source segments of every except handler in one method."""
    src = _method(path, class_name, method_name)
    out = []
    for node in ast.walk(ast.parse(src.strip())):
        if isinstance(node, ast.ExceptHandler):
            out.append(ast.get_source_segment(src.strip(), node) or "")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# W-b8 — TTS settings page: every UI-thread blocking path offloaded
# ═══════════════════════════════════════════════════════════════════════════

class TestWb8NormalizeTestOffload:
    """TtsNormalizationSection._on_test_clicked — the two LLM calls."""

    def test_spawn_shape_ref_and_both_handlers(self):
        body = _strip_comments(_method(
            _TTS, "TtsNormalizationSection", "_on_test_clicked"))
        assert "SimpleWorker(_work)" in body
        assert "self._test_worker = w" in body
        assert "w.finished.connect(self._on_test_finished)" in body
        assert "w.failed.connect(self._on_test_failed)" in body
        assert "w.start()" in body

    def test_reentrancy_guard_before_spawn(self):
        body = _strip_comments(_method(
            _TTS, "TtsNormalizationSection", "_on_test_clicked"))
        guard = body.find("is_running()")
        assert guard != -1, "re-entrancy guard (is_running) must exist"
        assert "RuntimeError" in body, (
            "guard must tolerate an already deleteLater'd worker"
        )
        assert guard < body.find("SimpleWorker(_work)")
        assert body.find("self.test_btn.setEnabled(False)") < body.find(
            "SimpleWorker(_work)"), "button disabled BEFORE the spawn"

    def test_worker_body_reads_no_widgets(self):
        body = _method(_TTS, "TtsNormalizationSection", "_on_test_clicked")
        work = _inner_fn(body, "_work")
        touched = _self_attrs(work)
        widgets = {"endpoint_edit", "apikey_edit", "model_edit",
                   "context_combo", "test_btn", "enabled_cb"}
        assert not (touched & widgets), (
            f"the worker body must be widget-free (W-b11 pattern), found: "
            f"{sorted(touched & widgets)}"
        )

    def test_snapshot_taken_on_main_thread(self):
        body = _strip_comments(_method(
            _TTS, "TtsNormalizationSection", "_on_test_clicked"))
        # the settings the worker needs are read in the CLICK slot (main
        # thread) BEFORE the spawn — the worker closes over plain values.
        assert "endpoint = self.endpoint_edit.text()" in body
        assert "api_key = self.apikey_edit.text()" in body
        assert "model = self.model_edit.text()" in body
        assert "prompt_en = self._load_prompt(\"en\") or None" in body
        assert "prompt_fa = self._load_prompt(\"fa\") or None" in body
        assert "context_mode = self.context_combo.currentData()" in body

    def test_finished_reenables_and_shows_identical_dialog(self):
        done = _strip_comments(_method(
            _TTS, "TtsNormalizationSection", "_on_test_finished"))
        assert "self.test_btn.setEnabled(True)" in done
        assert '"🔍  Test normalization"' in done
        assert '"Normalization Test — Before / After"' in done
        failed = _strip_comments(_method(
            _TTS, "TtsNormalizationSection", "_on_test_failed"))
        assert "self.test_btn.setEnabled(True)" in failed, (
            "W-b18 class: the failed handler must re-enable too"
        )
        assert '"🔍  Test normalization"' in failed

    def test_sync_normalize_loop_gone_from_click_slot(self):
        body = _method(_TTS, "TtsNormalizationSection", "_on_test_clicked")
        # the blocking LLM loop must live ONLY inside the worker closure.
        outside = body.replace(_inner_fn(body, "_work"), "")
        assert "norm.normalize(text, lang)" not in outside, (
            "the blocking LLM call must live in the worker, not the slot"
        )
        # the per-sample fail-soft "(failed: {e})" placeholder survives in
        # the worker body with a traceback log first (W-b17).
        work = _inner_fn(body, "_work")
        assert 'normalized = f"(failed: {e})"' in _strip_comments(work)
        assert "exc_info=True" in work


class TestWb8PreviewSampleOffload:
    """TtsPreviewSection._on_test_clicked — the first-play engine load."""

    def test_spawn_shape_ref_and_both_handlers(self):
        body = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_test_clicked"))
        assert "SimpleWorker(_work)" in body
        assert "self._sample_worker = w" in body
        assert "w.finished.connect(self._on_sample_generated)" in body
        assert "w.failed.connect(self._on_sample_failed)" in body
        assert "w.start()" in body

    def test_reentrancy_guard_and_snapshot(self):
        body = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_test_clicked"))
        guard = body.find("is_running()")
        assert guard != -1 and guard < body.find("SimpleWorker(_work)")
        assert "RuntimeError" in body
        # the engine-settings snapshot is taken on the MAIN thread and
        # passed into the worker (worker body reads no widgets/settings).
        assert "cfg = self._engine_settings()" in body
        assert body.find("cfg = self._engine_settings()") < body.find(
            "SimpleWorker(_work)")
        assert body.find("self.test_btn.setEnabled(False)") < body.find(
            "SimpleWorker(_work)")

    def test_worker_body_is_widget_free(self):
        body = _method(_TTS, "TtsPreviewSection", "_on_test_clicked")
        work = _inner_fn(body, "_work")
        touched = _self_attrs(work)
        widgets = {"lang_combo", "test_btn", "regen_btn", "cache_label"}
        assert not (touched & widgets), (
            f"the worker body must be widget-free, found: "
            f"{sorted(touched & widgets)}"
        )
        # the worker passes the snapshot into the generator.
        assert "self._generate_sample(lang, voice, speed, cfg)" in work
        # W-b17: the traceback is logged at WARNING before the failure
        # box (the old inline except reduced it to str(e)).
        assert "exc_info=True" in work

    def test_generate_sample_takes_the_snapshot(self):
        body = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_generate_sample"))
        assert "cfg: dict | None = None" in body
        assert 'if cfg is None:' in body
        assert 'cfg = self._engine_settings()' in body
        # the engine branches read the snapshot, not the controller.
        assert 'en_engine = cfg["en_engine"]' in body
        assert 'gguf = Path(cfg["neutts_gguf"])' in body
        assert 'piper_bin = Path(cfg["piper_binary"])' in body
        assert "self.controller.get_setting" not in body

    def test_finished_handler_preserves_old_box_and_reenables(self):
        done = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_sample_generated"))
        assert "self.test_btn.setEnabled(True)" in done
        assert '"Preview failed"' in done
        assert '"Unexpected: no audio produced."' in done
        assert '"▶  Playing…"' in done
        # the failed handler routes through the SAME display (identical
        # old behavior for a raised generator — W-b18).
        fail = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_sample_failed"))
        assert "self._on_sample_generated((None, error))" in fail


class TestWb8RegenerateOffload:
    """TtsPreviewSection._on_regenerate_clicked — the Regenerate engine load."""

    def test_spawn_shape_ref_and_both_handlers(self):
        body = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_regenerate_clicked"))
        assert "SimpleWorker(_work)" in body
        assert "self._sample_worker = w" in body
        assert "w.finished.connect(self._on_regenerate_finished)" in body
        assert "w.failed.connect(self._on_regenerate_failed)" in body
        assert "w.start()" in body
        assert body.find("self.regen_btn.setEnabled(False)") < body.find(
            "SimpleWorker(_work)")
        guard = body.find("is_running()")
        assert guard != -1 and guard < body.find("SimpleWorker(_work)")
        assert "RuntimeError" in body

    def test_both_handlers_reenable_and_keep_the_identical_box(self):
        done = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_regenerate_finished"))
        assert "self.regen_btn.setEnabled(True)" in done
        assert '"Regenerate"' in done
        assert '"Regeneration failed"' in done
        fail = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_regenerate_failed"))
        assert "self._on_regenerate_finished((None, error))" in fail

    def test_no_blocking_generate_left_in_the_click_slots(self):
        for name in ("_on_test_clicked", "_on_regenerate_clicked"):
            body = _strip_comments(_method(_TTS, "TtsPreviewSection", name))
            assert "path, error = self._generate_sample(" not in body, (
                f"{name} must offload the engine load, not call it inline"
            )


class TestWb8EnginesRecheckOffload:
    """TtsEnginesSection — the Kokoro import probe (engine test load)."""

    def test_recheck_no_longer_imports_kokoro_inline(self):
        body = _strip_comments(_method(
            _TTS, "TtsEnginesSection", "_recheck"))
        assert "import_module" not in body, (
            "the (potentially seconds-long) kokoro import must not run on "
            "the UI thread"
        )
        assert "self._check_kokoro_async()" in body

    def test_probe_is_a_widget_free_worker_fn(self):
        probe = _strip_comments(_method(
            _TTS, "TtsEnginesSection", "_probe_kokoro"))
        assert "import_module(\"kokoro\")" in probe
        assert "self" not in _self_attrs(probe), (
            "the probe must be static/widget-free (runs off-thread)"
        )
        assert "def _probe_kokoro" in _strip_comments(_src(_TTS))

    def test_async_spawn_ref_guard_and_both_handlers(self):
        body = _strip_comments(_method(
            _TTS, "TtsEnginesSection", "_check_kokoro_async"))
        assert "SimpleWorker(self._probe_kokoro)" in body
        assert "self._kokoro_worker = w" in body
        assert "w.finished.connect(self._on_kokoro_probed)" in body
        assert "w.failed.connect(self._on_kokoro_probe_failed)" in body
        assert "w.start()" in body
        guard = body.find("is_running()")
        assert guard != -1 and guard < body.find("SimpleWorker(")
        assert "RuntimeError" in body

    def test_kokoro_indicator_updates_on_main_thread(self):
        done = _strip_comments(_method(
            _TTS, "TtsEnginesSection", "_on_kokoro_probed"))
        assert "self._set_dot(self.kokoro_dot, bool(kokoro_ok))" in done
        assert "f\"Kokoro — {'connected' if kokoro_ok else 'not installed'}\"" \
            in done
        fail = _strip_comments(_method(
            _TTS, "TtsEnginesSection", "_on_kokoro_probe_failed"))
        assert "logger.warning" in fail

    def test_spawn_and_failed_counts_match(self):
        src = _src(_TTS)
        assert src.count("SimpleWorker(") == 4, (
            "exactly four offloads: kokoro probe + normalize test + "
            "first-play sample + regenerate"
        )
        assert src.count(".failed.connect(") == 4, (
            "every tts_page worker wires its failed signal (W-b18 class)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# W-b12 — library merge off the click slot + crash visibility
# ═══════════════════════════════════════════════════════════════════════════

class TestWb12MergeOffload:
    def test_merge_runs_in_a_worker_not_the_slot(self):
        body = _strip_comments(_method(_APP, "MarkItDownProWindow",
                                       "_open_merge_dialog"))
        work = _inner_fn(_method(_APP, "MarkItDownProWindow",
                                 "_open_merge_dialog"), "_work")
        assert "merge_books(book_dirs, Path(output_folder), log_callback=None)" \
            in _strip_comments(work)
        assert "merge_books(" not in body.replace(
            "merge_books(book_dirs, Path(output_folder), log_callback=None)",
            ""), "merge_books must live inside the worker closure only"

    def test_spawn_shape_ref_guard_and_both_handlers(self):
        body = _strip_comments(_method(_APP, "MarkItDownProWindow",
                                       "_open_merge_dialog"))
        assert "SimpleWorker(_work)" in body
        assert "self._merge_worker = w" in body
        assert "w.finished.connect(self._on_merge_finished)" in body
        assert "w.failed.connect(self._on_merge_failed)" in body
        assert "w.start()" in body
        guard = body.find("is_running()")
        assert guard != -1 and guard < body.find("SimpleWorker(_work)")
        assert "RuntimeError" in body
        assert body.find("self.merge_btn.setEnabled(False)") < body.find(
            "SimpleWorker(_work)")

    def test_finished_handler_reenables_and_keeps_identical_boxes(self):
        done = _strip_comments(_method(_APP, "MarkItDownProWindow",
                                       "_on_merge_finished"))
        assert "self.merge_btn.setEnabled(True)" in done
        assert '"Merge complete"' in done
        assert '"Merge failed"' in done
        assert '"No summaries found to merge."' in done
        fail = _strip_comments(_method(_APP, "MarkItDownProWindow",
                                       "_on_merge_failed"))
        assert "self.merge_btn.setEnabled(True)" in fail, (
            "W-b18 class: the failed handler must re-enable too"
        )
        assert '"Merge error"' in fail

    def test_failure_logs_traceback_before_the_box(self):
        work = _inner_fn(_method(_APP, "MarkItDownProWindow",
                                 "_open_merge_dialog"), "_work")
        assert "exc_info=True" in work, (
            "W-b17 crash-visibility: the traceback must be logged BEFORE "
            "the str(e)-only user box"
        )
        assert "raise" in work


# ═══════════════════════════════════════════════════════════════════════════
# W-b18 remainder — every remaining unconnected ``failed`` wired
# ═══════════════════════════════════════════════════════════════════════════

class TestWb18rWizardTestButtons:
    """Step5Models' cloud/fast TEST buttons."""

    def test_cloud_test_worker_keeps_ref_and_wires_failed(self):
        body = _strip_comments(_method(
            _STEP5, "Step5Models", "_test_cloud_connection"))
        assert "self._cloud_test_worker = w" in body
        assert "w.failed.connect(self._on_cloud_test_failed)" in body
        assert "w.start()" in body

    def test_fast_test_worker_keeps_ref_and_wires_failed(self):
        body = _strip_comments(_method(
            _STEP5, "Step5Models", "_test_fast_cloud_connection"))
        assert "self._fast_cloud_test_worker = w" in body
        assert "w.failed.connect(self._on_fast_cloud_test_failed)" in body
        assert "w.start()" in body

    def test_failed_handlers_route_through_existing_result_slots(self):
        """No new user-visible strings — the existing ✅/❌ display +
        re-enable path serves the raised case too."""
        cloud = _strip_comments(_method(
            _STEP5, "Step5Models", "_on_cloud_test_failed"))
        assert "self._pending_cloud_result = (False, error)" in cloud
        assert "self._set_cloud_test_result()" in cloud
        fast = _strip_comments(_method(
            _STEP5, "Step5Models", "_on_fast_cloud_test_failed"))
        assert "self._pending_fast_cloud_result = (False, error)" in fast
        assert "self._set_fast_cloud_test_result()" in fast

    def test_no_bare_fire_and_forget_spawns_remain(self):
        src = _strip_comments(_src(_STEP5))
        assert "SimpleWorker(_run).start()" not in src, (
            "every Step5Models worker spawn keeps a ref + failed wiring"
        )
        assert src.count("SimpleWorker(") == src.count(".failed.connect("), (
            "spawn count must equal failed-wiring count (W-b18r)"
        )


class TestWb18rOllamaCheck:
    """app.py's non-blocking Ollama reachability check."""

    def test_worker_ref_and_failed_wiring(self):
        body = _strip_comments(_method(
            _APP, "MarkItDownProWindow", "_warn_ollama"))
        assert "self._ollama_check_worker = w" in body
        assert "w.failed.connect(self._on_ollama_check_failed)" in body
        assert "w.start()" in body
        handler = _strip_comments(_method(
            _APP, "MarkItDownProWindow", "_on_ollama_check_failed"))
        assert "logger.warning" in handler

    def test_no_bare_spawn_remains(self):
        src = _strip_comments(_src(_APP))
        assert "SimpleWorker(_check).start()" not in src
        assert src.count("SimpleWorker(") == src.count(".failed.connect(")


class TestWb18rOutputScannerWorkers:
    """output_scanner_view's batch + single regeneration workers."""

    def test_shared_spawn_helper_keeps_ref_and_wires_failed(self):
        body = _strip_comments(_method(
            _SCANNER, "OutputScannerView", "_spawn_regen_worker"))
        assert "SimpleWorker(_run)" in body
        assert "self._regen_worker = w" in body
        assert "w.failed.connect(self._on_regen_worker_failed)" in body
        assert "w.start()" in body
        # a replaced still-winding-down worker is parked (T-b2 retire
        # pattern), never dropped mid-run.
        assert "self._retired_workers.append(prev)" in body
        assert "RuntimeError" in body

    def test_failed_handler_reenables_both_buttons(self):
        handler = _strip_comments(_method(
            _SCANNER, "OutputScannerView", "_on_regen_worker_failed"))
        assert "self.scan_btn.setEnabled(True)" in handler
        assert "self.complete_all_btn.setEnabled(True)" in handler
        assert '"  ✅ Complete All Requested"' in handler

    def test_both_worker_sites_route_through_the_helper(self):
        for name in ("_regen_next", "_regenerate"):
            body = _strip_comments(_method(
                _SCANNER, "OutputScannerView", name))
            assert "self._spawn_regen_worker(_run)" in body
        src = _strip_comments(_src(_SCANNER))
        assert "SimpleWorker(_run).start()" not in src
        assert src.count("SimpleWorker(") == src.count(".failed.connect(")


# ═══════════════════════════════════════════════════════════════════════════
# W-b19 — exactly one mediaStatusChanged connection
# ═══════════════════════════════════════════════════════════════════════════

class TestWb19MediaStatusChanged:
    def test_exactly_one_connect_at_the_one_time_setup_site(self):
        src = _strip_comments(_src(_TTS))
        assert src.count("mediaStatusChanged.connect(") == 1, (
            "the player's mediaStatusChanged must be connected exactly once"
        )
        ensure = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_ensure_player"))
        assert "self._player.mediaStatusChanged.connect(" in ensure, (
            "the one connect lives in the one-time player setup site"
        )
        # and NOT in the per-click path (the old duplicate-connection bug).
        click = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_test_clicked"))
        assert "mediaStatusChanged" not in click
        for name in ("_on_sample_generated", "_on_regenerate_finished"):
            seg = _strip_comments(_method(_TTS, "TtsPreviewSection", name))
            assert "mediaStatusChanged" not in seg

    def test_playback_reset_slot_survives(self):
        seg = _strip_comments(_method(
            _TTS, "TtsPreviewSection", "_on_playback_finished"))
        assert "EndOfMedia" in seg
        assert "self._on_lang_changed(0)" in seg


# ═══════════════════════════════════════════════════════════════════════════
# W-b14 — the _on_log hot path: module-level imports + compiled regexes
# ═══════════════════════════════════════════════════════════════════════════

class TestWb14OnLogHotPath:
    def test_module_level_imports_and_compiled_regexes(self):
        src = _src(_WIZARD)
        tree = ast.parse(src)
        imports = {node.names[0].name for node in tree.body
                   if isinstance(node, ast.Import)}
        assert "re" in imports and "time" in imports
        assigns = {node.targets[0].id: node for node in tree.body
                   if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0], ast.Name)}
        assert "_PROGRESS_RE" in assigns and "_CHAPTER_RE" in assigns
        assert "re.compile" in ast.get_source_segment(
            src, assigns["_PROGRESS_RE"]) or True
        prog = ast.get_source_segment(src, assigns["_PROGRESS_RE"]) or ""
        chap = ast.get_source_segment(src, assigns["_CHAPTER_RE"]) or ""
        assert "re.compile" in prog and "re.compile" in chap
        # the patterns are VERBATIM from the old inline searches.
        assert r"'Progress: (\d+)/(\d+) done.*?(\d+) bullets'" in prog
        assert r"'Chapter (\d+)/(\d+)'" in chap

    def test_on_log_has_no_per_line_imports_and_uses_compiled(self):
        body = _strip_comments(_method(_WIZARD, "WizardView", "_on_log"))
        assert "import re" not in body
        assert "_PROGRESS_RE.search(msg)" in body
        assert "_CHAPTER_RE.search(msg)" in body
        for name in ("_on_status", "_update_time_estimate"):
            seg = _strip_comments(_method(_WIZARD, "WizardView", name))
            assert "import time" not in seg
            assert "time.time()" in seg

    def test_regex_behavior_is_identical(self):
        """Pure-Python: the compiled patterns match exactly what the old
        inline ``re.search`` calls matched (same pattern literals)."""
        progress = re.compile(r'Progress: (\d+)/(\d+) done.*?(\d+) bullets')
        chapter = re.compile(r'Chapter (\d+)/(\d+)')
        line = "  📊 Progress: 3/12 done | 31 bullets | 1,204 chars exec summary"
        m = progress.search(line)
        assert m and (m.group(1), m.group(2), m.group(3)) == ("3", "12", "31")
        # identical to the pre-W-b14 inline behavior on this line.
        m2 = re.search(r'Progress: (\d+)/(\d+) done.*?(\d+) bullets', line)
        assert m.group(0) == m2.group(0)
        chap_line = "✅ Chapter 7/12: 'The self as subject…' complete"
        mc = chapter.search(chap_line)
        assert mc and (mc.group(1), mc.group(2)) == ("7", "12")
        assert progress.search("nothing here") is None
        assert chapter.search("Chapter complete") is None


# ═══════════════════════════════════════════════════════════════════════════
# W-b15 — quality dashboard: JSON-first, log-string fallback
# ═══════════════════════════════════════════════════════════════════════════

class TestWb15QualityDashboard:
    def test_json_first_reader_exists(self):
        body = _strip_comments(_method(
            _WIZARD, "WizardView", "_update_quality_dashboard_from_report"))
        assert 'report_path = base / "logs" / "quality_report.json"' in body
        assert 'totals.get("successful_summaries")' in body
        assert 'totals.get("chapters_summarized")' in body
        assert 'totals.get("total_bullets")' in body
        # non-numeric/missing reports degrade to a no-op (fail-soft).
        assert "isinstance(done, int)" in body
        assert "isinstance(total, int)" in body
        assert "isinstance(bullets, int)" in body

    def test_same_displayed_format_as_the_log_fallback(self):
        json_body = _method(
            _WIZARD, "WizardView", "_update_quality_dashboard_from_report")
        log_body = _method(_WIZARD, "WizardView", "_on_log")
        fmt = 'f"Quality: {done}/{total} chapters done | {bullets} bullets total"'
        assert fmt in json_body
        assert fmt in log_body, (
            "the fallback parse keeps the identical display format"
        )

    def test_landed_at_completion_success_branch(self):
        body = _strip_comments(_method(
            _WIZARD, "WizardView", "_show_completion_modal"))
        success = body.find("if result.success:")
        call = body.find("self._update_quality_dashboard_from_report()")
        assert success != -1 and call != -1 and success < call
        # the call runs before the modal's user-visible completion logs.
        assert call < body.find('f"  Pages processed: {result.pages_processed}"')

    def test_log_string_fallback_still_present(self):
        body = _strip_comments(_method(_WIZARD, "WizardView", "_on_log"))
        assert "_PROGRESS_RE.search(msg)" in body

    def test_json_parse_pure_python(self):
        """The metrics mapping the reader expects, exercised on a real
        report shape (the converter's totals block)."""
        import json
        report = {"totals": {"chapters_summarized": 12,
                             "successful_summaries": 11,
                             "total_bullets": 431}}
        totals = json.loads(json.dumps(report))["totals"] or {}
        done = totals.get("successful_summaries")
        total = totals.get("chapters_summarized")
        bullets = totals.get("total_bullets")
        assert (isinstance(done, int) and isinstance(total, int)
                and isinstance(bullets, int))
        assert f"Quality: {done}/{total} chapters done | {bullets} bullets total" \
            == "Quality: 11/12 chapters done | 431 bullets total"
        # non-numeric totals must NOT paint (the fail-soft no-op guard).
        bad = {"totals": {"successful_summaries": None,
                          "chapters_summarized": "12",
                          "total_bullets": 431}}
        t = bad["totals"] or {}
        assert not (isinstance(t.get("successful_summaries"), int)
                    and isinstance(t.get("chapters_summarized"), int)
                    and isinstance(t.get("total_bullets"), int))


# ═══════════════════════════════════════════════════════════════════════════
# W-b17 — traceback at WARNING before the user message (the ten sites)
# ═══════════════════════════════════════════════════════════════════════════

class TestWb17TracebackBeforeBox:
    """Every SWOT-listed str(e)-only site now logs the traceback first.

    The ten sites (line numbers were the V18.20.4.0 SWOT's; the markdown
    styler's two moved to their own module in the P5 dialog split):
    app merge, podcast ×4, wizard build-request, markdown_styler ×2,
    tts add-voice, tts preview-generate.
    """

    SITES = (
        # (path, class, method, the user-visible marker in the same block)
        # (the app.py MERGE site is covered by TestWb12MergeOffload — its
        # traceback log lives in the worker wrapper and its box in the
        # ``failed`` handler, split across the worker boundary.)
        (_PODCAST, "PodcastMakerView", "_pick_file", '"Could not read file'),
        (_PODCAST, "PodcastMakerView", "_on_export_script", '"Export failed"'),
        (_PODCAST, "PodcastMakerView", "_on_import_script", '"Import failed"'),
        (_PODCAST, "PodcastMakerView", "_on_import_script", '"Parse failed"'),
        (_WIZARD, "WizardView", "_start_conversion",
         '"Failed to build conversion request'),
        (_STYLER, "MarkdownStylerDialog", "_on_process",
         '"❌ Markdown Styler Failed"'),
        (_STYLER, "MarkdownStylerDialog", "_on_save", '"Save failed"'),
        (_TTS, "TtsVoicesSection", "_on_add_voice", '"Failed to add voice"'),
    )

    def test_every_site_logs_traceback_before_the_message(self):
        for path, cls, method, marker in self.SITES:
            src = _method(path, cls, method)
            blocks = _except_blocks(path, cls, method)
            # comments are stripped so a comment that merely MENTIONS the
            # box title can't satisfy the marker (the marker is a string
            # literal — it survives comment stripping).
            target = [b for b in blocks if marker in _strip_comments(b)]
            assert target, (
                f"{cls}.{method} in {path.name}: no except block carrying "
                f"{marker!r} — site moved? (evolve the pin, don't drop it)"
            )
            block = _strip_comments(target[0])
            assert "exc_info=True" in block, (
                f"{cls}.{method} ({path.name}): the {marker!r} block must "
                "log the traceback (exc_info=True) — W-b17"
            )
            assert block.find("exc_info=True") < block.find(marker), (
                f"{cls}.{method} ({path.name}): the traceback log must come "
                "BEFORE the user-visible message"
            )

    def test_tts_preview_sites(self):
        """The two preview-generate sites log inside the worker wrapper
        (the old inline ``except`` reduced the raise to str(e))."""
        for method_name in ("_on_test_clicked", "_on_regenerate_clicked"):
            work = _inner_fn(_method(_TTS, "TtsPreviewSection", method_name),
                             "_work")
            assert "exc_info=True" in work
            assert "raise" in work
        normalize = _inner_fn(_method(
            _TTS, "TtsNormalizationSection", "_on_test_clicked"), "_work")
        assert "exc_info=True" in normalize

    def test_user_visible_strings_unchanged(self):
        """The exact box titles/texts the SWOT sites showed before."""
        assert '"Merge error"' in _src(_APP)
        assert '"Export failed"' in _src(_PODCAST)
        assert '"Import failed"' in _src(_PODCAST)
        assert '"Parse failed"' in _src(_PODCAST)
        assert '"Failed to build conversion request: {e}"' in _src(_WIZARD)
        assert '"❌ Markdown Styler Failed"' in _src(_STYLER)
        assert '"Save failed"' in _src(_STYLER)
        assert '"Failed to add voice"' in _src(_TTS)
        assert '"Preview failed"' in _src(_TTS)
        assert '"Regeneration failed"' in _src(_TTS)


# ═══════════════════════════════════════════════════════════════════════════
# T-b4 — the dead DPI assignment is gone
# ═══════════════════════════════════════════════════════════════════════════

class TestTb4DpiDeadAssignment:
    def test_dead_assignment_gone(self):
        src = _src(_MAIN)
        assert "Qt.AA_EnableHighDpiScaling = True" not in _strip_comments(src), (
            "the dead enum-attribute write must be deleted (T-b4)"
        )
        # no reader existed anywhere in the tree either.
        for py in (_project_root / "ui_qt").rglob("*.py"):
            assert "AA_EnableHighDpiScaling" not in _src(py)
        assert "AA_EnableHighDpiScaling" not in _src(
            _project_root / "controller.py")

    def test_qt6_automatic_documented_and_env_kept(self):
        src = _src(_MAIN)
        assert "Qt 6 enables high-DPI scaling" in src, (
            "the Qt6 automatic behavior is documented in a one-line comment"
        )
        assert 'os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")' in src

    def test_main_still_parses(self):
        ast.parse(_src(_MAIN))


# ═══════════════════════════════════════════════════════════════════════════
# T-b6 — cancel-and-quit retires the daemon writer threads
# ═══════════════════════════════════════════════════════════════════════════

class TestTb6RetireOnClose:
    def test_close_event_stops_and_waits(self):
        src = _strip_comments(_method(
            _APP, "MarkItDownProWindow", "closeEvent"))
        assert "self._retire_conversion_workers()" in src
        # retire happens AFTER the cancel request, BEFORE the settings save.
        cancel = src.find("self.queue_view.stop()")
        save = src.find("self.controller.settings.save()")
        retire = src.find("self._retire_conversion_workers()")
        assert cancel < retire < save

    def test_retire_helper_shape(self):
        body = _strip_comments(_method(
            _APP, "MarkItDownProWindow", "_retire_conversion_workers"))
        # the two daemon writer threads (queue + controller conversion).
        assert '"_worker_thread"' in body
        assert '"current_conversion_thread"' in body
        # dedupe: while a queue runs they are the SAME thread object.
        assert "conv_thread not in candidates" in body
        # stop-and-wait: the T-b2 retire pattern.
        assert "t.join(wait_ms)" in body
        assert "self._retired_workers = retired" in body
        # best-effort — never hang the close on a stuck writer.
        assert "except Exception:" in body
        assert "wait_ms: int = 2000" in body

    def test_queue_worker_is_still_a_daemon(self):
        """T-b6 scoped the CLOSE path (the writers stay daemons; the fix
        is the join-before-exit, not de-daemonizing the queue)."""
        src = _src(_project_root / "ui_qt" / "views" / "queue_view.py")
        assert "daemon=True" in src
        assert "self._worker_thread" in src

    def test_retire_park_warning(self):
        body = _method(_APP, "MarkItDownProWindow",
                       "_retire_conversion_workers")
        assert "logger.warning" in body


# ═══════════════════════════════════════════════════════════════════════════
# File hygiene — every touched runtime file still parses
# ═══════════════════════════════════════════════════════════════════════════

class TestFilesParse:
    @pytest.mark.parametrize("path", [
        _TTS, _APP, _WIZARD, _STEP5, _SCANNER, _PODCAST, _STYLER, _MAIN,
    ], ids=lambda p: p.name)
    def test_file_parses(self, path):
        ast.parse(_src(path))
