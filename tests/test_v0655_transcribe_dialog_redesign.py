"""V0.6.55 — the Transcribe Service dialog redesign pins (source/AST).

WHY SOURCE PINS: this sandbox has no PySide6 (and no display) — the
dialog cannot be INSTANTIATED here. The house precedent (V0.6.54's
test_v0654_transcribe_dialog_nameerror_fix.py) pins the dialog's
CONTRACT on the AST: the structure that must exist for the behavior to
be possible. The behavior the pins guarantee:

  - P1c  the 🔌 Test button exists, runs the health check on a WORKER
         thread (never the UI thread), persists an auto-detected port,
         and renders the three verdicts (healthy / slow-CPU-fallback /
         unreachable) with the right message boxes.
  - P1   the engine combo DEFAULTS to transcribe.cpp (matching the
         service default since V0.6.42 and the operator's Vulkan rig)
         and the initial visibility call applies it on first paint.
  - P3   when BOTH summary and tutorial are requested, ONE combined
         round trip runs; the split-failure path falls back to the
         separate tutorial call.
  - P4   EVERY LLM call passes ``on_chunk=`` — the status label shows
         the generation growing.
  - P5   ``except TranscribeError`` renders the structured failures;
         unexpected exceptions wrap as TranscribePipelineError (the
         V0.6.53 NameError class can never reach the user raw again).

All pins are pure source/AST walks — hermetic by construction.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)


@pytest.fixture(scope="module")
def tree() -> ast.Module:
    src = _DIALOG.read_text(encoding="utf-8")
    return ast.parse(src, filename=str(_DIALOG))


def _method(t: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(t):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    pytest.fail(f"method {name} not found in the dialog source")


def _summarize_calls(node: ast.AST) -> list[ast.Call]:
    return [
        c
        for c in ast.walk(node)
        if isinstance(c, ast.Call)
        and isinstance(c.func, ast.Name)
        and c.func.id in ("summarize_transcript", "summarize_transcript_combined")
    ]


# ═════════════════════════════════════════════════════════════════════════════
# P1 — the engine default flip + first-paint visibility
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655EngineDefault:
    def test_transcribe_cpp_is_the_first_engine_item(self, tree):
        """The combo's first item (the DEFAULT selection) is
        transcribe.cpp — matching the service default since V0.6.42 and
        the operator's Vulkan rig. Pre-fix the first item was
        faster-whisper: dialog default and service default disagreed."""
        add_items = [
            c
            for c in ast.walk(_method(tree, "_build_options"))
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "addItem"
            and isinstance(c.func.value, ast.Attribute)
            and c.func.value.attr == "engine_combo"
        ]
        assert add_items, "engine_combo.addItem calls not found"
        first_data = add_items[0].args[-1]
        assert isinstance(first_data, ast.Constant) and first_data.value == "transcribe_cpp"

    def test_initial_visibility_call_exists(self, tree):
        """_on_engine_changed() is called explicitly at build time —
        the slot only fires on index CHANGE, so without this call the
        whisper-model row would stay visible under the new default
        engine (a stale first paint)."""
        build = _method(tree, "_build_options")
        calls = [
            c
            for c in ast.walk(build)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "_on_engine_changed"
        ]
        assert calls, "_build_options must call self._on_engine_changed()"

    def test_initial_visibility_call_comes_after_the_whisper_row_creation(self, tree):
        """CONSTRUCTION-ORDER PIN (the Task 9 review BLOCKER): the
        initial ``_on_engine_changed()`` call touches whisper_combo /
        whisper_browse_btn — the call MUST come AFTER both widgets are
        created, or the dialog crashes with AttributeError inside
        __init__ on every real PySide6 install (this sandbox cannot see
        it: no PySide6, and the AST pin above only checked the call
        EXISTS). The failure class is exactly the V0.6.53 NameError the
        redesign was meant to eliminate."""
        build = _method(tree, "_build_options")
        call_lines = [
            c.lineno
            for c in ast.walk(build)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "_on_engine_changed"
        ]
        assign_lines = [
            node.lineno
            for node in ast.walk(build)
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr in ("whisper_combo", "whisper_browse_btn")
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "self"
        ]
        assert call_lines and assign_lines, "expected the call and the widget stores"
        assert min(call_lines) > max(assign_lines), (
            f"_on_engine_changed() called at line {min(call_lines)} but the "
            f"whisper widgets are created up to line {max(assign_lines)} — "
            "the dialog would crash on construction (AttributeError)"
        )

    def test_do_transcribe_engine_fallback_default(self, tree):
        """options.get('engine', ...) defaults to transcribe_cpp — the
        V0.6.42 service default, no longer the stale faster_whisper."""
        method = _method(tree, "_do_transcribe")
        for node in ast.walk(method):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "engine"
            ):
                default = node.args[1] if len(node.args) > 1 else None
                assert default is not None and isinstance(default, ast.Constant)
                assert default.value == "transcribe_cpp"
                return
        pytest.fail("engine options.get default not found")


# ═════════════════════════════════════════════════════════════════════════════
# P1c — the 🔌 Test button + its worker-thread discipline
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655TestButton:
    def test_button_is_created_and_wired(self, tree):
        src = _DIALOG.read_text(encoding="utf-8")
        assert "self.llm_test_btn = _QPB(" in src
        assert "self.llm_test_btn.clicked.connect(self._on_test_llm)" in src

    def test_button_visibility_follows_the_llm_row(self, tree):
        """The Test button hides when neither summary nor tutorial is
        checked (it probes the backend those outputs depend on)."""
        src = _DIALOG.read_text(encoding="utf-8")
        assert "self.llm_test_btn.setVisible(needs_llm)" in src

    def test_health_check_runs_on_a_worker_thread(self, tree):
        """The probe blocks for seconds — it must NEVER run on the UI
        thread (the V0.6.54 worker discipline). _on_test_llm builds a
        SimpleWorker whose callable calls check_llm_for_transcribe."""
        src = _DIALOG.read_text(encoding="utf-8")
        method = _method(tree, "_on_test_llm")
        msrc = ast.get_source_segment(
            _DIALOG.read_text(encoding="utf-8"), method
        ) or ""
        assert "SimpleWorker" in msrc, "the check must run via SimpleWorker"
        assert "check_llm_for_transcribe" in msrc
        assert ".start()" in msrc
        assert ".finished.connect(self._on_test_llm_done)" in src
        assert ".failed.connect(self._on_test_llm_failed)" in src

    def test_done_handler_persists_the_auto_detected_port(self, tree):
        """save_url → Settings().set('summarisation.llamacpp_base_url',
        …) — one click fixes every future run, and the operator was
        told in the message first."""
        method = _method(tree, "_on_test_llm_done")
        msrc = ast.get_source_segment(_DIALOG.read_text(encoding="utf-8"), method) or ""
        assert "save_url" in msrc
        assert "summarisation.llamacpp_base_url" in msrc

    def test_done_handler_renders_the_three_verdicts(self, tree):
        """healthy → information / slow-cpu-fallback-suspected →
        warning (the n_gpu_layers guidance) / unreachable → critical."""
        method = _method(tree, "_on_test_llm_done")
        msrc = ast.get_source_segment(_DIALOG.read_text(encoding="utf-8"), method) or ""
        assert "slow-cpu-fallback-suspected" in msrc
        assert "QMessageBox.warning" in msrc
        assert "QMessageBox.critical" in msrc
        assert "QMessageBox.information" in msrc


# ═════════════════════════════════════════════════════════════════════════════
# P3 — one combined round trip for notes + tutorial
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655CombinedDialogWiring:
    def test_combined_call_guards_on_both_outputs(self, tree):
        """``if save_summary and save_tutorial:`` → the combined call.
        Pre-fix there was NO combined path: two sequential calls always
        ran when both outputs were checked."""
        method = _method(tree, "_do_transcribe")
        found = False
        for node in ast.walk(method):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if (
                isinstance(test, ast.BoolOp)
                and isinstance(test.op, ast.And)
                and {getattr(v, "id", None) for v in test.values} == {"save_summary", "save_tutorial"}
            ):
                body_calls = _summarize_calls(node)
                if any(
                    isinstance(c.func, ast.Name)
                    and c.func.id == "summarize_transcript_combined"
                    for c in body_calls
                ):
                    found = True
        assert found, "the both-outputs branch must call summarize_transcript_combined"

    def test_split_failure_falls_back_to_a_separate_tutorial_call(self, tree):
        """``if not combined['split_ok']:`` → a separate tutorial call
        (correctness over speed — the pre-V0.6.55 behavior as the net)."""
        method = _method(tree, "_do_transcribe")
        src = ast.get_source_segment(_DIALOG.read_text(encoding="utf-8"), method) or ""
        assert "split_ok" in src
        # the fallback tutorial call keeps output_type="tutorial"
        tutorial_calls = [
            c for c in _summarize_calls(method) if c.func.id == "summarize_transcript"
            and any(
                k.arg == "output_type"
                and isinstance(k.value, ast.Constant)
                and k.value.value == "tutorial"
                for k in c.keywords
            )
        ]
        assert len(tutorial_calls) == 2, (
            "expected exactly 2 tutorial summarize calls "
            "(the split-failure fallback + the tutorial-only branch), found "
            f"{len(tutorial_calls)}"
        )

    def test_every_llm_call_passes_on_chunk(self, tree):
        """P4: ALL FOUR LLM call sites forward on_chunk — the frozen
        status label cannot return unless someone drops the kwarg."""
        method = _method(tree, "_do_transcribe")
        calls = _summarize_calls(method)
        assert len(calls) == 4, f"expected 4 LLM call sites, found {len(calls)}"
        for c in calls:
            kws = {k.arg for k in c.keywords}
            assert "on_chunk" in kws, f"{c.func.id} at line {c.lineno} lacks on_chunk"

    def test_all_calls_pass_the_extracted_text_local(self, tree):
        """The V0.6.54 NameError guard, extended to the combined call:
        every call site's first positional arg is the
        ``_extracted_text`` Name."""
        method = _method(tree, "_do_transcribe")
        for c in _summarize_calls(method):
            assert c.args, f"{c.func.id} at line {c.lineno} has no positional args"
            first = c.args[0]
            assert isinstance(first, ast.Name) and first.id == "_extracted_text", (
                f"{c.func.id} at line {c.lineno} must pass _extracted_text"
            )


# ═════════════════════════════════════════════════════════════════════════════
# P5 — structured errors in the dialog
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655DialogErrorHandling:
    def test_transcribe_error_is_caught(self, tree):
        """``except TranscribeError`` in _do_transcribe — the structured
        family renders as results['error'] (stage + message + fix)."""
        method = _method(tree, "_do_transcribe")
        handlers = [
            h.type
            for node in ast.walk(method)
            if isinstance(node, ast.Try)
            for h in node.handlers
        ]
        names = {getattr(t, "id", getattr(t, "attr", None)) for t in handlers}
        assert "TranscribeError" in names, f"handlers: {names}"

    def test_unexpected_exceptions_wrap_as_pipeline_error(self, tree):
        """``except Exception`` → TranscribePipelineError — the raw
        traceback (the V0.6.53 NameError) goes to the LOG, the friendly
        message goes to the user."""
        method = _method(tree, "_do_transcribe")
        src = ast.get_source_segment(_DIALOG.read_text(encoding="utf-8"), method) or ""
        assert "TranscribePipelineError" in src
        assert "logger.exception" in src

    def test_the_error_results_key_still_carries_the_four_key_contract(self, tree):
        """The V0.6.44 results dict contract (raw_path / summary_path /
        tutorial_path / error) is unchanged — the completion dialog and
        the e2e pins depend on it.

        V0.6.62 STALE-PIN REFRESH, documented: the pin matched the
        dict's OLD single-line source literal; the results dict is
        now multi-line and EXTENDED (srt_path / vtt_path /
        subtitle_cues — the subtitle deliverables). The four V0.6.44
        keys still init to None; the structural check below pins the
        whole key set (old four + new three) instead of a formatting
        accident."""
        method = _method(tree, "_do_transcribe")
        init_dicts = [
            n
            for n in ast.walk(method)
            if isinstance(n, ast.Dict)
            and any(
                isinstance(k, ast.Constant) and k.value == "raw_path" for k in n.keys
            )
        ]
        assert init_dicts, "the results init dict must exist in _do_transcribe"
        keys = {k.value for k in init_dicts[0].keys if isinstance(k, ast.Constant)}
        assert {"raw_path", "summary_path", "tutorial_path", "error"} <= keys
        assert {"srt_path", "vtt_path", "subtitle_cues"} <= keys
        # The four V0.6.44 keys must init to None (the "not written"
        # sentinel); subtitle_cues is a COUNTER and inits to 0.
        sentinel = {
            k.value: v
            for k, v in zip(init_dicts[0].keys, init_dicts[0].values, strict=True)
            if isinstance(k, ast.Constant) and k.value != "subtitle_cues"
        }
        assert all(
            isinstance(v, ast.Constant) and v.value is None for v in sentinel.values()
        ), "every non-counter results key must init to None"
