"""V0.6.54 — the transcribe-dialog NameError regression pin.

THE BUG (introduced in V0.6.53, fixed in V0.6.54):

  Commit 3a44cd9 ("V0.6.53 -- empty-text guard + log extracted text
  length + use _transcript_text") renamed the local that holds the
  whisper-extracted plain text from ``_transcript_text`` to
  ``_extracted_text`` for the log line (line 508), but LEFT the two
  ``summarize_transcript(...)`` call sites in Step 4 (Summary) and
  Step 5 (Tutorial) still referencing the OLD name ``_transcript_text``.

  Symptom (the operator's report, verbatim intent): "The transcriber
  tool is supposed to transcribe using whisper to raw text (which takes
  30-40 seconds) then give that text to llm model for summarize and
  tutorial, but it doesn't happen."

  Root cause: ``_do_transcribe`` reached Step 4 and raised
  ``NameError: name '_transcript_text' is not defined``. The
  ``BaseWorker._thread_started`` wrapper (ui_qt/components/base_worker.py:65)
  caught it and emitted the ``failed`` signal, so the dialog showed
  "❌ Transcription Failed: name '_transcript_text' is not defined" —
  BUT only AFTER Step 3 had already written the raw transcript file.
  So the raw .md appeared on disk while no summary / tutorial ever did.

THE PIN: a pure-AST walk of the dialog source. A ``Name`` node with id
``_transcript_text`` MUST NOT exist anywhere in the module (comments and
docstrings are invisible to the AST, so the explanatory comment block
that mentions the old name for the reader's benefit does not trip the
assert). AND the two ``summarize_transcript`` calls MUST receive the
``_extracted_text`` Name (the assigned local) as their first positional
argument. This is a compile-time guarantee — the NameError cannot
return unless someone re-introduces the mismatched name.

The pin is hermetic (no PySide6, no Qt offscreen platform, no audio
files, no LLM) — it reads the source and walks the AST.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_DIALOG = _project_root / "ui_qt" / "views" / "service_dialogs" / "dialogs" / "transcribe_service_dialog.py"


@pytest.fixture(scope="module")
def _source_tree() -> ast.Module:
    """Parse the dialog source once for the whole module."""
    src = _DIALOG.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(_DIALOG))
    assert isinstance(tree, ast.Module)
    return tree


def _walk_names(tree: ast.Module) -> list[str]:
    """Every Name node's id in the module (Load/Store/Delete alike)."""
    return [n.id for n in ast.walk(tree) if isinstance(n, ast.Name)]


class TestV0654NameErrorFix:
    """The two-call-site NameError introduced in V0.6.53 is gone for good."""

    def test_transcript_text_name_is_absent_from_the_ast(self, _source_tree):
        """No ``_transcript_text`` Name node anywhere — comments and
        docstrings are invisible to the AST, so the V0.6.54 fix block
        that quotes the old name for the reader does not trip this."""
        names = _walk_names(_source_tree)
        assert "_transcript_text" not in names, (
            "the V0.6.53 NameError source is back — `_transcript_text` is "
            "referenced in the dialog but never assigned there"
        )

    def test_extracted_text_name_is_assigned(self, _source_tree):
        """The renamed local ``_extracted_text`` MUST be assigned somewhere
        (the V0.6.53 log-line introduction) — otherwise the fix is moot
        and we'd just have a different NameError."""
        names = _walk_names(_source_tree)
        assert "_extracted_text" in names, (
            "`_extracted_text` is not referenced at all — the V0.6.54 fix "
            "was reverted or the local was renamed again"
        )

    def test_extracted_text_is_assigned_before_use(self, _source_tree):
        """The ``_extracted_text = ...`` assignment MUST come before the
        ``summarize_transcript(_extracted_text, ...)`` call sites in
        source order — Python resolves names at call time, not def time,
        but pinning source-order protects against a future reordering
        that moves the assignment inside an ``if`` branch the summarize
        calls don't share."""
        # Collect (line, is_assignment) for every _extracted_text Name node.
        events: list[tuple[int, bool]] = []
        for node in ast.walk(_source_tree):
            if isinstance(node, ast.Name) and node.id == "_extracted_text":
                events.append((node.lineno, isinstance(node.ctx, ast.Store)))
        events.sort()
        assert events, "no _extracted_text references found"
        first_assign = next((ln for ln, is_store in events if is_store), None)
        first_load = next((ln for ln, is_store in events if not is_store), None)
        assert first_assign is not None, (
            "`_extracted_text` is read but never assigned — a read-only "
            "NameError by another name"
        )
        if first_load is not None:
            assert first_assign <= first_load, (
                f"`_extracted_text` is read at line {first_load} before being "
                f"assigned at line {first_assign} — a NameError in waiting"
            )


class TestV0654SummarizeCallSites:
    """The two ``summarize_transcript`` calls MUST pass the transcript
    text — the plain-text local, not the timestamped ``raw_text`` (which
    is only defined inside the ``if save_raw`` branch and would itself
    be a NameError when raw saving is off)."""

    def _summarize_calls(self, tree: ast.Module) -> list[ast.Call]:
        """Every ``summarize_transcript(...)`` call expression in the module."""
        calls: list[ast.Call] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "summarize_transcript"
            ):
                calls.append(node)
        return calls

    def test_there_are_two_summarize_calls(self, _source_tree):
        """Step 4 (summary) + Step 5 (tutorial) — exactly two call sites."""
        calls = self._summarize_calls(_source_tree)
        assert len(calls) == 2, (
            f"expected 2 summarize_transcript call sites (summary + tutorial), "
            f"found {len(calls)}"
        )

    def test_both_calls_pass_extracted_text_as_first_arg(self, _source_tree):
        """Both call sites MUST pass ``_extracted_text`` (the plain-text
        local) as the first positional argument — the V0.6.54 fix."""
        calls = self._summarize_calls(_source_tree)
        for i, call in enumerate(calls, start=1):
            assert call.args, (
                f"summarize_transcript call #{i} has no positional args — "
                "the transcript text isn't being passed"
            )
            first = call.args[0]
            assert isinstance(first, ast.Name) and first.id == "_extracted_text", (
                f"summarize_transcript call #{i} (line {call.lineno}) passes "
                f"{ast.dump(first)} as its first arg — must be the "
                "`_extracted_text` Name"
            )

    def test_tutorial_call_sets_output_type_tutorial(self, _source_tree):
        """The second summarize_transcript call (the tutorial guide)
        MUST pass ``output_type='tutorial'`` so the prompt manager picks
        the tutorial template, not the notes template."""
        calls = self._summarize_calls(_source_tree)
        assert len(calls) >= 2
        tutorial_call = calls[1]
        kw = {kw.arg: kw.value for kw in tutorial_call.keywords if kw.arg}
        assert "output_type" in kw, (
            "the tutorial summarize_transcript call has no output_type kwarg "
            "— it would generate a summary, not a tutorial"
        )
        val = kw["output_type"]
        assert isinstance(val, ast.Constant) and val.value == "tutorial", (
            "the tutorial summarize_transcript call's output_type MUST be "
            "the literal 'tutorial'"
        )


class TestV0654ResultsDictContract:
    """The ``results`` dict the worker returns MUST carry the three
    output paths the completion dialog enumerates — the V0.6.44 contract.
    The V0.6.54 fix does not touch this, but pinning it guards against a
    careless refactor that drops a key and silently breaks the completion
    message (the same 'it didn't happen' symptom, different cause)."""

    def test_results_keys_are_raw_summary_tutorial(self, _source_tree):
        """The results dict literal MUST be the four-key contract
        (raw_path / summary_path / tutorial_path / error)."""
        keys: set[str] = set()
        for node in ast.walk(_source_tree):
            if isinstance(node, ast.Dict):
                for k in node.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        if k.value.endswith("_path") or k.value == "error":
                            keys.add(k.value)
        for required in ("raw_path", "summary_path", "tutorial_path", "error"):
            assert required in keys, (
                f"the results-dict key '{required}' is missing from the dialog "
                "— the completion dialog would not mention this output"
            )


# ── the compile-level guarantee ──────────────────────────────────────────────

class TestV0654ModuleCompiles:
    """The dialog source MUST parse cleanly — a SyntaxError would prevent
    the module from importing, taking the whole Transcribe Service down
    (the same user-visible 'doesn't happen' symptom). This is the
    compile-time floor under the AST pins above."""

    def test_module_has_valid_python_syntax(self):
        src = _DIALOG.read_text(encoding="utf-8")
        try:
            ast.parse(src, filename=str(_DIALOG))
        except SyntaxError as e:
            pytest.fail(f"the dialog source has a SyntaxError: {e}")

    def test_do_transcribe_method_is_defined(self, _source_tree):
        """The ``_do_transcribe`` method MUST exist on the dialog class —
        the SimpleWorker calls it. A rename would silently make the
        worker call a missing method (AttributeError, same symptom)."""
        method_names: list[str] = []
        for node in ast.walk(_source_tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                method_names.append(node.name)
        assert "_do_transcribe" in method_names, (
            "the `_do_transcribe` method is missing — the worker would call "
            "a non-existent method"
        )
