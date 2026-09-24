"""Phase-7 O2/O10 (SWOT W2, first tranche): characterization net for
``Summarizer._summarize_inner`` (``core/summarisation/summarizer.py:1429-1777``).

WHY THIS FILE EXISTS
--------------------
The 349-line ``_summarize_inner`` is the **V0.11 W1 god-class residue** — the
single method that SWOT Phase 7 (O2/O10) flagged as "the next de-monolithization
target" and the NEW_SESSION_PROMPT flagged as "too risky to extract" (the
5,853-test net + eval gate now make it safely testable; it wasn't at the
V18.6.3 crash that froze ``_build_prompt`` extraction). This file is the
**characterization FIRST** step that makes the eventual extraction safe:
it pins the orchestrator's behavior BEFORE any move so a future refactor
that silently changes the stage sequence, the control-flow branches, the
status strings, or the return-value shape breaks the test.

The previous Phase-5 characterization nets (test_conversion_postprocess_*
/ visual_features_* / output_runner_characterization.py — the A2 work)
followed the Phase-3 net precedent (``test_converter_phase3_characterization.py``,
2,336 ln): hermetic fakes (``_FakeConverter`` / ``_FakeRequest``), the
``_RecordingSelf`` pattern, and **source-pin tests** that assert the
literal log skeletons on the live source so a refactor can't silently
reword a status string. This file follows the SAME discipline — but
adapts the harness: ``_summarize_inner`` orchestrates the REAL chapter
pipeline (15+ stages, 5+ phase calls, the speculative-scholar machinery),
so we use the proven hermetic harness from ``test_p2_summarizer_harness.py``
(``Settings._test_override`` DI hook, absent-machine embedder/spacy
singletons, deterministic ``ScriptedLLM`` at the ``_call_llm`` funnel).

WHAT IS PINNED HERE (the orchestrator's surface — NOT the inner stages,
which are pinned by ``test_p2_summarizer_pipeline_phases.py`` + the
per-stage modules' own nets):

* **Source-pins** — the method's signature, docstring stage list, the
  phase-call sequence in the live source (literal ``self._phase_*`` calls
  in order), the constants (``MAP_REDUCE_THRESHOLD``, ``_P6_SCHOLAR_INPUT_KEYS``),
  the log-message skeletons the ORCHESTRATOR emits (P6 strategy log, the
  map-reduce switch log, the V0.3.1 map-reduce success log, the
  speculative-scholar log set).
* **Orchestration contract** — for the empty-input gate path, ONLY
  ``_phase_setup_and_gate`` fires (the rest are skipped); for the
  single-pass happy path, the 10 phase calls fire in the documented order.
* **Control-flow branches** — the empty-input gate (<80 tokens → early
  SummaryResult), the primary-model failure hint ladder (timeout / oom /
  not_found / empty), the map-reduce route (strategy log + switch log +
  the documented ``_pipeline`` UnboundLocalError that test_p2 already
  locks — pinned here as a characterization point too), the deadline-exceeded
  path (3 deadline-skip WARNING+INFO pairs).
* **Return-value shape** — the SummaryResult fields ``_summarize_inner``
  populates (success / chapter_heading / executive_summary / bullet_points /
  thorough_summary / error_msg / input_tokens / output_tokens /
  key_distinctions / theoretical_tensions / scholar_reflections /
  source_excerpts / recall_floor / run_id / app_version / run_started /
  include_executive_summary / include_thorough_summary / include_keypoints /
  model_used), and the difference between the populated happy-path shape
  vs the fail-soft early-exit shapes (empty provenance on early exits).
* **Fail-soft paths** — the speculative-scholar machinery's 4 return-None
  branches (lever off, dual-model, scholar_reflections_enabled, deadline
  exceeded), the handle dict's 3 callable keys, the snapshot's 5-key tuple,
  the abort() no-op.
* **Coverage floor + theorist floor invocation** — the V18.20.3.13 thorough
  theorist floor + the deterministic recall-floor probe both fire on the
  happy path; the recall-floor dict's keys are pinned.

This is the FIRST TRANCHE — a focused ~45-test net pinning the
orchestrator's MOST IMPORTANT branches. The exhaustive Phase-3-pattern
net (every log variant + every branch) is a follow-up phase; the
EXTRACTION itself is rig-required (output-equivalence validation needs
the real LLM + the real embedder to compare pre/post-move summary bytes).

APPROACH
--------
Every LLM-touching test uses ``ScriptedLLM`` (installed at
``summarizer._call_llm``) so the test is hermetic (no real LLM, no real
embedder, no real PDF/OCR stack — the proven test_p2 recipe). Every
expected value was probed empirically against the live code before
writing (see the worklog B4 entry's Work Log) — NO invented expected
values. Where a behavior can't be pinned without the real LLM (e.g. the
actual gap-fill content), the CONTROL FLOW + log skeleton + return shape
are pinned instead (per the brief); the test's docstring notes this.

Rule-1 compliance: all fixtures use generic content ("Chapter One",
"Paragraph N", "operative" / "baseline" / "environment" — generic
section names like origin / perspectives / features / conclusion). NO
book-derived names.

Run: ``pytest tests/test_summarize_inner_characterization.py -v --no-cov``
"""

from __future__ import annotations

import inspect
import re
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Reuse the proven hermetic harness from the P2 test net — gives us
# make_summarizer + ScriptedLLM + hermetic_env + golden_chapter + the
# deadline helpers + the build_primary_response grounded XML builder.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p2_summarizer_harness import (  # noqa: E402
    ScriptedLLM,
    a_chapter,
    armed_deadline,
    assert_logged,
    build_primary_response,
    fresh_deadline,
    golden_chapter,
    hermetic_env,
    make_summarizer,
    write_analysis_tree,
)

# ════════════════════════════════════════════════════════════════════════════
# Section 0 — module-level setup (the harness pattern)
# ════════════════════════════════════════════════════════════════════════════

_SUMMARIZER_SRC_PATH = _project_root / "core" / "summarisation" / "summarizer.py"
_CHAPTER_PHASES_SRC_PATH = _project_root / "core" / "summarisation" / "chapter_phases.py"


def _summarizer_src() -> str:
    """The current summarizer.py source (for source-pin tests)."""
    return _SUMMARIZER_SRC_PATH.read_text(encoding="utf-8")


def _chapter_phases_src() -> str:
    """The current chapter_phases.py source (for source-pin tests)."""
    return _CHAPTER_PHASES_SRC_PATH.read_text(encoding="utf-8")


def _full_response(source: str) -> str:
    """The grounded canned XML (all five sections, from the bench builder)."""
    return build_primary_response(source)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Hermetic env + no-op sleep (the test_p2 pattern)."""
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    with hermetic_env():
        yield


# A model absent from the context-window registry keeps the request's 32768
# window (gemma3:12b is raised to 131072 by the P5 registry, which switches
# decide_strategy to the ADAPTIVE regime where B4 is disabled and map-reduce
# needs a >125k-token chapter). With the legacy window the P6 cascade is
# byte-identical to the pre-P6 thresholds. (Same constant as test_p2.)
LEGACY_MODEL = "mystery-model-x"


# ════════════════════════════════════════════════════════════════════════════
# Section 1 — source-pin tests (the orchestrator's literal surface)
# ════════════════════════════════════════════════════════════════════════════


class TestSourcePinMethodShape:
    """Pin the method's signature + docstring + the orchestrator's
    phase-call skeleton so a future extraction (or any rename) breaks the
    test at the source level (Phase-3 / A2 precedent)."""

    def test_method_defined_on_summarizer(self):
        from core.summarisation.summarizer import Summarizer

        assert hasattr(Summarizer, "_summarize_inner"), "Summarizer must define _summarize_inner"
        assert callable(Summarizer._summarize_inner)

    def test_method_has_documented_5_arg_signature(self):
        """The signature pinned in the V18.1 docstring: heading + content
        + optional concepts/callouts/book_context."""
        from core.summarisation.summarizer import Summarizer

        sig = inspect.signature(Summarizer._summarize_inner)
        params = list(sig.parameters.keys())
        assert params == ["self", "heading", "content", "concepts", "callouts", "book_context"]
        assert sig.parameters["concepts"].default is None
        assert sig.parameters["callouts"].default is None
        assert sig.parameters["book_context"].default == ""

    def test_method_docstring_documents_15_stage_pipeline(self):
        """The docstring's first line names the '15-stage bullet pipeline'."""
        from core.summarisation.summarizer import Summarizer

        doc = Summarizer._summarize_inner.__doc__ or ""
        assert "15-stage bullet pipeline" in doc
        # The docstring enumerates the stages
        assert "Stages (in execution order)" in doc

    def test_method_source_calls_phase_methods_in_documented_order(self):
        """The orchestrator's body must call the phase methods in the order
        the V0.18 (Phase 5.1) decomposition documented. Pin the call
        sequence on the live source so a future extraction can't silently
        reorder or drop a phase."""
        src = _summarizer_src()
        # Find the _summarize_inner body
        m = re.search(
            r"def _summarize_inner\(.*?(?=\n    def |\n    @|\nclass )",
            src,
            re.DOTALL,
        )
        assert m is not None, "could not locate _summarize_inner body in source"
        body = m.group(0)
        # The phase-call sequence (the V0.18 de-monolithization contract)
        phase_calls = [
            "_phase_setup_and_gate",
            "_p6_decide_strategy",  # the strategy decision (imported inline)
            "_map_reduce_summarize",  # the map-reduce leg
            "_phase_single_pass_primary",  # the single-pass leg
            "_phase_thorough_and_coverage",
            "_p6_prepare_speculative_scholar",
            "_phase_validation_and_judge",
            "_phase_recovery_pass",
            "_phase_deterministic_judge",
            "_phase_postchecks_and_floors",
            "_phase_finalize",
        ]
        offsets = []
        for name in phase_calls:
            idx = body.find(name)
            assert idx != -1, f"_summarize_inner body does not reference {name!r}"
            offsets.append(idx)
        # The order in the source must be monotonic (a phase that appears
        # earlier in the documented sequence must appear earlier in the body)
        for i in range(len(phase_calls) - 1):
            assert offsets[i] < offsets[i + 1], (
                f"phase {phase_calls[i]!r} appears AFTER {phase_calls[i + 1]!r} in the "
                f"source — the documented sequence is broken"
            )

    def test_method_body_contains_p6_strategy_log_literal(self):
        """The P6 strategy log skeleton must appear verbatim in the source
        (the V0.10 P6 entry-point log — pinning it makes a future rename
        or rewording a visible test break)."""
        src = _summarizer_src()
        # The skeleton spans an f-string with several interpolations; pin
        # the LITERAL pieces (the emojis + the field labels).
        for fragment in (
            "🧭 V0.10 (P6): strategy=",
            "(src=",
            "tok / window=",
            "/ output=",
            ") — ",
        ):
            assert fragment in src, f"P6 strategy log literal {fragment!r} missing from source"

    def test_method_body_contains_map_reduce_switch_log_literal(self):
        """The map-reduce switch log skeleton (split across 3 f-string
        literals — pin skeletons WITHIN single literals per the A2
        precedent)."""
        src = _summarizer_src()
        for fragment in (
            "🗺️ Chapter too large for single call (",
            "tokens) — ",
            "switching to Map-Reduce (",
            "-token chunks,",
            "% overlap)",
        ):
            assert fragment in src, f"map-reduce switch log literal {fragment!r} missing"

    def test_method_body_contains_v031_map_reduce_log_literal(self):
        """The V0.3.1 map-reduce success log skeleton (split across two
        implicit-concatenated f-string literals — the Phase-3 / A2
        pattern of pinning skeletons WITHIN a single literal, not
        across literals)."""
        src = _summarizer_src()
        assert "✅ V0.3.1 map-reduce: master=" in src
        # The second literal: f"bullets={...}, exec={...}w"
        assert "bullets=" in src
        assert ", exec=" in src

    def test_method_body_contains_map_reduce_failure_literals(self):
        """The map-reduce failure SummaryResult literals (the early-exit
        shape that's the only documented 'fail-fast at the orchestrator'
        path inside _summarize_inner itself)."""
        src = _summarizer_src()
        assert "[Error: Map-Reduce failed]" in src
        assert "Map-Reduce returned no response" in src

    def test_method_body_returns_summary_result_from_finalize(self):
        """The orchestrator's final return must route through
        ``_phase_finalize`` (the only legit construction site for the
        successful SummaryResult)."""
        src = _summarizer_src()
        m = re.search(
            r"def _summarize_inner\(.*?(?=\n    def |\n    @|\nclass )",
            src,
            re.DOTALL,
        )
        assert m is not None
        body = m.group(0)
        # The final return statement (the last `return` in the body)
        returns = [r.start() for r in re.finditer(r"^\s+return\s", body, re.MULTILINE)]
        assert returns, "no return statement in _summarize_inner body"
        last_return = body[returns[-1] :]
        assert "_phase_finalize" in last_return, (
            "the final return of _summarize_inner must call _phase_finalize"
        )


class TestSourcePinSpeculativeScholar:
    """Pin the speculative-scholar machinery's literal log skeletons +
    the snapshot key tuple (so a future refactor can't silently reword
    a Phase-6.2 status string or drop a snapshot key)."""

    def test_p6_scholar_input_keys_is_5_tuple(self):
        """The 5 keys the scholar reflection reads (the snapshot pin)."""
        from core.summarisation.summarizer import Summarizer

        keys = Summarizer._P6_SCHOLAR_INPUT_KEYS
        assert keys == (
            "bullet_points",
            "executive_summary",
            "thorough_summary",
            "key_distinctions",
            "theoretical_tensions",
        )

    def test_dual_model_skip_log_literal(self):
        """The dual-model DEBUG skip log skeleton."""
        src = _summarizer_src()
        for fragment in (
            "ℹ️ Phase 6.2: judge∥scholar speculation skipped",
            "dual-model architecture switches models mid-call)",
        ):
            assert fragment in src, f"dual-model skip log literal {fragment!r} missing"

    def test_scholar_launch_log_literal(self):
        """The launch INFO log skeleton."""
        src = _summarizer_src()
        for fragment in (
            "🎓 Phase 6.2: speculative scholar reflection launched",
            "overlapping the judge tail",
            "summarisation.parallel_stages_judge_scholar",
        ):
            assert fragment in src, f"scholar launch log literal {fragment!r} missing"

    def test_scholar_crash_warning_literal(self):
        """The crash WARNING log skeleton (the fail-soft path)."""
        src = _summarizer_src()
        for fragment in (
            "⚠️ Phase 6.2: speculative scholar crashed",
            "non-fatal, sequential fallback",
        ):
            assert fragment in src, f"scholar crash warning literal {fragment!r} missing"

    def test_scholar_discard_log_literal(self):
        """The DISCARD INFO log skeleton (the merge-or-rerun gate's
        'state changed' leg). Skeletons pinned WITHIN single f-string
        literals (the source splits the line across 3 literals; per the
        A2 precedent, pin fragments that live within ONE literal)."""
        src = _summarizer_src()
        for fragment in (
            "ℹ️ Phase 6.2: speculative scholar DISCARDED",
            "tail changed the summary state",
            "re-running sequentially",
            "pre-V0.19 behavior",
        ):
            assert fragment in src, f"scholar discard log literal {fragment!r} missing"

    def test_scholar_merge_log_literal(self):
        """The MERGE INFO log skeleton (the merge-or-rerun gate's golden
        path — judge tail left the state unchanged). Skeletons pinned
        WITHIN single f-string literals (the A2 precedent: multi-line
        f-strings use the skeleton-set check since the constants are
        joined in the JoinedStr)."""
        src = _summarizer_src()
        for fragment in (
            "🎓 Phase 6.2: speculative scholar reflection MERGED",
            "judge tail left the summary state unchanged",
            "result is the sequential result",
        ):
            assert fragment in src, f"scholar merge log literal {fragment!r} missing"

    def test_handle_dict_has_three_callable_keys(self):
        """The handle dict returned by _p6_prepare_speculative_scholar
        must expose the 3 documented callable keys (the merge-or-rerun
        contract's seam with the rest of the orchestrator)."""
        # Build a bare Summarizer + arm the lever
        with hermetic_env():
            tmp = Path("/tmp/_char_p6_src")
            tmp.mkdir(parents=True, exist_ok=True)
            heading, source = golden_chapter()
            s = make_summarizer(
                tmp,
                settings_values={
                    "summarisation.parallel_stages": True,
                    "summarisation.parallel_stages_judge_scholar": True,
                },
            )
            fresh_deadline(s)
            parsed = {
                "bullet_points": ["b1", "b2"],
                "executive_summary": "exec",
                "thorough_summary": "tho",
                "key_distinctions": "kd",
                "theoretical_tensions": "tt",
            }
            handle = s._p6_prepare_speculative_scholar(heading, source, parsed)
            assert handle is not None
            assert set(handle.keys()) == {"prejudge_hook", "scholar_runner", "abort"}
            for k in ("prejudge_hook", "scholar_runner", "abort"):
                assert callable(handle[k]), f"handle[{k!r}] must be callable"

    def test_abort_is_a_no_op(self):
        """The abort() callable is the hard-reject path's no-op (the
        daemonized thread's result is never consumed — pin that the call
        returns None and raises nothing)."""
        with hermetic_env():
            tmp = Path("/tmp/_char_p6_abort")
            tmp.mkdir(parents=True, exist_ok=True)
            heading, source = golden_chapter()
            s = make_summarizer(
                tmp,
                settings_values={
                    "summarisation.parallel_stages": True,
                    "summarisation.parallel_stages_judge_scholar": True,
                },
            )
            fresh_deadline(s)
            handle = s._p6_prepare_speculative_scholar(heading, source, {})
            assert handle is not None
            # abort() must return None (it's the documented "pass" body)
            assert handle["abort"]() is None

    def test_snapshot_returns_5_key_tuple_with_lists_as_tuples(self):
        """The snapshot converts each list value to a tuple so the
        comparison is BY VALUE (the V18.20.4.11 P2 / W-a1 contract —
        identity changes are irrelevant)."""
        with hermetic_env():
            tmp = Path("/tmp/_char_p6_snap")
            tmp.mkdir(parents=True, exist_ok=True)
            s = make_summarizer(tmp)
            parsed = {
                "bullet_points": ["x", "y"],
                "executive_summary": "e",
                "thorough_summary": "t",
                "key_distinctions": "k",
                "theoretical_tensions": "tt",
                "ignored_extra_key": "does not appear",
            }
            snap = s._p6_scholar_input_snapshot(parsed)
            assert len(snap) == 5
            keys = [k for (k, _v) in snap]
            assert keys == [
                "bullet_points",
                "executive_summary",
                "thorough_summary",
                "key_distinctions",
                "theoretical_tensions",
            ]
            # The list value MUST be tuple-coerced (not the original list)
            bp_entry = next(s for s in snap if s[0] == "bullet_points")
            assert isinstance(bp_entry[1], tuple)
            assert bp_entry[1] == ("x", "y")


# ════════════════════════════════════════════════════════════════════════════
# Section 2 — orchestration contract (the phase-call sequence)
# ════════════════════════════════════════════════════════════════════════════


class TestOrchestrationContract:
    """Pin which phases fire (and in what order) for a given input shape.
    The pin uses monkeypatch to record each phase-call (the A2 _RecordingSelf
    precedent) so a future extraction that drops or reorders a phase
    breaks the test.

    NB: the wrappers are installed via pytest's ``monkeypatch`` fixture
    (NOT bare ``setattr(type(s), ...)``) so the patches are torn down at
    test exit — bare setattr would poison the Summarizer class for every
    later test in the session (the V0.18 de-monolithization inheritance
    net at ``test_v182047_p5_core_decomp`` checks the methods live on
    the mixin, not on Summarizer itself, and would break)."""

    @staticmethod
    def _recording_summarizer(tmp_path, monkeypatch, log_lines=None):
        """A real Summarizer where each ``_phase_*`` method is wrapped to
        record its call. The wrappers delegate to the REAL method so the
        pipeline runs as production."""
        heading, source = golden_chapter()
        s = make_summarizer(tmp_path, log_lines=log_lines or [])
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        calls: list[str] = []

        def _wrap(name, real_method):
            def _wrapper(self_inner, *a, **kw):
                calls.append(name)
                return real_method(self_inner, *a, **kw)

            return _wrapper

        for phase in (
            "_phase_setup_and_gate",
            "_phase_single_pass_primary",
            "_phase_thorough_and_coverage",
            "_p6_prepare_speculative_scholar",
            "_phase_validation_and_judge",
            "_phase_recovery_pass",
            "_phase_deterministic_judge",
            "_phase_postchecks_and_floors",
            "_phase_finalize",
        ):
            real = getattr(type(s), phase)
            monkeypatch.setattr(type(s), phase, _wrap(phase, real), raising=False)
        return s, calls, (heading, source)

    def test_empty_input_gate_skips_every_phase_after_setup(self, tmp_path, monkeypatch):
        """The <80-token gate is the FIRST early-exit: ``_phase_setup_and_gate``
        returns a SummaryResult and the orchestrator returns it WITHOUT
        calling any other phase."""
        s, calls, _ = self._recording_summarizer(tmp_path, monkeypatch)
        # Drive the gate path
        s._summarize_inner("Tiny", "Far too small to summarize safely.")
        # ONLY _phase_setup_and_gate should fire — nothing else.
        assert calls == ["_phase_setup_and_gate"], (
            f"empty-input gate should skip every later phase; got {calls!r}"
        )

    def test_happy_path_fires_all_phases_in_documented_order(self, tmp_path, monkeypatch):
        """The single-pass happy path fires the full sequence in the V0.18
        documented order (setup → single_pass → thorough_and_coverage →
        spec scholar (None by default) → validation+judge → recovery →
        deterministic judge → postchecks → finalize).

        NOTE: the speculative-scholar hook IS called (returns None by
        default — the lever is off) but does NOT appear in the
        phase-call list because it's NOT one of the orchestrator's
        ``_phase_*`` methods — it's the V0.19 seam. We pin it separately
        in TestSpeculativeScholar."""
        s, calls, (heading, source) = self._recording_summarizer(tmp_path, monkeypatch)
        result = s._summarize_inner(heading, source)
        assert result.success is True
        # The documented order — pin it.
        assert calls == [
            "_phase_setup_and_gate",
            "_phase_single_pass_primary",
            "_phase_thorough_and_coverage",
            "_p6_prepare_speculative_scholar",
            "_phase_validation_and_judge",
            "_phase_recovery_pass",
            "_phase_deterministic_judge",
            "_phase_postchecks_and_floors",
            "_phase_finalize",
        ], f"phase-call order broken; got {calls!r}"


# ════════════════════════════════════════════════════════════════════════════
# Section 3 — control-flow branches (live behavior pins)
# ════════════════════════════════════════════════════════════════════════════


class TestEmptyInputGate:
    """The <80-token gate (the hallucination-prevention early exit)."""

    def test_tiny_chapter_returns_failure_result(self, tmp_path):
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        result = s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert result.success is False
        assert "too small" in result.error_msg
        assert "skipping to prevent hallucination" in result.error_msg

    def test_tiny_chapter_does_not_call_llm(self, tmp_path):
        """The empty-input gate fires BEFORE any LLM call (the
        hallucination-prevention contract)."""
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        llm = ScriptedLLM(primary_response="irrelevant").install(s)
        fresh_deadline(s)
        s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert llm.calls == [], "empty-input gate must fire BEFORE the LLM call"

    def test_tiny_chapter_logs_warning_with_token_count(self, tmp_path):
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert_logged(logs, "Segment too small")
        assert_logged(logs, "tokens) — skipping to prevent hallucination")

    def test_tiny_chapter_zero_output_tokens(self, tmp_path):
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        result = s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert result.output_tokens == 0
        # input_tokens = the small src_tokens the gate measured
        assert result.input_tokens > 0
        assert result.input_tokens < 80

    def test_tiny_chapter_provenance_fields_empty(self, tmp_path):
        """The early-exit SummaryResult does NOT carry the provenance
        fields (no _phase_finalize = no run_id/app_version/run_started stamp)."""
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        result = s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert result.run_id == ""
        assert result.app_version == ""
        assert result.run_started == ""
        assert result.model_used == ""

    def test_tiny_chapter_bullets_thorough_exec_empty(self, tmp_path):
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        result = s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert result.bullet_points == []
        assert result.thorough_summary == ""
        assert result.executive_summary == ""

    def test_tiny_chapter_recall_floor_is_none(self, tmp_path):
        """The recall-floor probe runs in _phase_postchecks_and_floors,
        which is SKIPPED on the empty-input gate → recall_floor is None."""
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response="never").install(s)
        fresh_deadline(s)
        result = s._summarize_inner("Tiny", "Far too small to summarize safely.")
        assert result.recall_floor is None


class TestHappyPath:
    """The grounded single-pass happy path — pins the populated
    SummaryResult shape (the orchestrator's success contract)."""

    def test_happy_path_returns_success(self, tmp_path):
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.success is True

    def test_happy_path_provenance_fields_populated(self, tmp_path):
        """The provenance fields are stamped in _phase_finalize — the
        happy path reaches it, so they're populated."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.run_id != ""
        assert result.app_version != ""
        assert result.run_started != ""

    def test_happy_path_model_used_set(self, tmp_path):
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        # The model label comes from parsed["model"] (defaulting to primary_model)
        assert result.model_used == s.primary_model

    def test_happy_path_include_flags_default_true(self, tmp_path):
        """The output-selection contract stamps include_* flags onto the
        result — default request has all three True."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.include_executive_summary is True
        assert result.include_thorough_summary is True
        assert result.include_keypoints is True

    def test_happy_path_input_output_tokens_positive(self, tmp_path):
        """input_tokens = the source's token count (count_tokens(content));
        output_tokens = count_tokens(final_summary) — both must be > 0
        on the happy path."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.input_tokens > 0
        assert result.output_tokens > 0

    def test_happy_path_summary_fields_populated(self, tmp_path):
        """The SummaryResult must carry executive_summary, bullet_points,
        thorough_summary, key_distinctions, theoretical_tensions (the
        full summary contract)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.executive_summary
        assert result.bullet_points
        assert result.thorough_summary
        # key_distinctions + theoretical_tensions are populated by the
        # additive-sections phase; the canned response carries them.
        assert result.key_distinctions or result.key_distinctions == ""
        assert result.theoretical_tensions or result.theoretical_tensions == ""

    def test_happy_path_p6_strategy_log_fires(self, tmp_path):
        """The P6 strategy log fires on EVERY non-tiny chapter (after the
        setup gate, before either map_reduce or single_pass)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source)
        # Pin the skeleton (the V0.10 P6 entry-point log)
        assert_logged(logs, "🧭 V0.10 (P6): strategy=")
        assert_logged(logs, "(src=")
        assert_logged(logs, "tok / window=")
        assert_logged(logs, "/ output=")
        # Happy path = single_pass strategy
        assert_logged(logs, "strategy=single_pass")

    def test_happy_path_emits_using_primary_model_log(self, tmp_path):
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source)
        assert_logged(logs, "⚡ Using primary model:")


class TestPrimaryModelFailureHints:
    """The 4 primary-model failure hint branches (timeout / oom / not_found /
    empty) — the orchestrator's failure-hint ladder. Pin the exact hint
    fragment per error type (probed live)."""

    @pytest.mark.parametrize(
        ("err_type", "fragment"),
        [
            ("timeout", "timed out after"),
            ("oom", "ran out of VRAM"),
            ("not_found", "is not installed in Ollama"),
            (None, "returned an empty/short response after retry"),
        ],
    )
    def test_primary_failure_hint_by_error_type(self, tmp_path, err_type, fragment):
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        s._last_llm_error_type = err_type
        ScriptedLLM(responder=lambda *a, **k: None).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.success is False
        assert fragment in result.error_msg
        # The primary-failure path also reaches _phase_single_pass_primary
        # (the failure happens INSIDE that phase) and the result is
        # constructed there — not by _phase_finalize. So provenance is empty.
        assert result.run_id == ""
        assert result.app_version == ""
        assert result.run_started == ""

    def test_primary_failure_input_tokens_preserved(self, tmp_path):
        """The failure SummaryResult carries input_tokens = the source
        token count (so the caller can see what was attempted)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        s._last_llm_error_type = "timeout"
        ScriptedLLM(responder=lambda *a, **k: None).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.input_tokens > 0
        assert result.output_tokens == 0

    def test_primary_failure_logs_error_hint(self, tmp_path):
        """The hint is also logged at ERROR level (the user-facing
        diagnostic line)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        s._last_llm_error_type = "not_found"
        ScriptedLLM(responder=lambda *a, **k: None).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source)
        # The ERROR-level hint log
        assert any(level == "ERROR" and "💡 Likely cause:" in msg for (level, msg) in logs), (
            "the 💡 hint must be logged at ERROR level"
        )
        # The ❌ primary-failure log
        assert any(
            "❌ Primary model" in msg and "returned no response" in msg for (_lvl, msg) in logs
        )


class TestMapReduceRoute:
    """The P6 map-reduce route — the second strategy branch (pin the
    log skeletons + the documented _pipeline UnboundLocalError that
    test_p2_summarizer_pipeline_phases.py already locks; pinned here
    as a characterization point too because it's part of the
    orchestrator's CURRENT observable behavior)."""

    def test_map_reduce_route_emits_strategy_log_with_map_reduce(self, tmp_path):
        """When src_tokens > MAP_REDUCE_THRESHOLD, the P6 strategy log
        names strategy=map_reduce."""
        heading = "Big Chapter"
        source = a_chapter(60)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
            log_lines=logs,
        )
        s.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        try:
            s._summarize_inner(heading, source)
        except Exception:
            pass  # the documented _pipeline crash is pinned below
        assert_logged(logs, "🧭 V0.10 (P6): strategy=map_reduce")
        # The reason fragment
        assert_logged(logs, "legacy window 32,768 <= 32,768:")

    def test_map_reduce_route_emits_switch_log(self, tmp_path):
        heading = "Big Chapter"
        source = a_chapter(60)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
            log_lines=logs,
        )
        s.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        try:
            s._summarize_inner(heading, source)
        except Exception:
            pass
        # The map-reduce switch log skeleton
        assert_logged(logs, "🗺️ Chapter too large for single call (")
        assert_logged(logs, "tokens) — switching to Map-Reduce (")
        assert_logged(logs, "-token chunks,")
        assert_logged(logs, "% overlap)")

    def test_map_reduce_route_emits_v031_success_log(self, tmp_path):
        """When the map-reduce reduce phase produces a master summary ≥ 50
        words, the V0.3.1 success log fires (the derive-bullets + derive-exec
        path)."""
        heading = "Big Chapter"
        source = a_chapter(60)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
            log_lines=logs,
        )
        s.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        try:
            s._summarize_inner(heading, source)
        except Exception:
            pass
        assert_logged(logs, "✅ V0.3.1 map-reduce: master=")
        assert_logged(logs, "w, bullets=")
        assert_logged(logs, ", exec=")
        assert_logged(logs, "w")

    def test_map_reduce_route_crashes_on_unbound_pipeline(self, tmp_path):
        """The documented P0 bug (test_p2_summarizer_pipeline_phases locks
        it): the map-reduce route never assigns ``_pipeline`` / ``_pstate``
        (those are only assigned in the single-pass leg), so the
        validation_and_judge call site raises UnboundLocalError. Pin it
        here as part of the orchestrator's CURRENT behavior — a future
        extraction that fixes this WILL break the test (the desired
        outcome)."""
        heading = "Big Chapter"
        source = a_chapter(60)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
            log_lines=logs,
        )
        s.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        with pytest.raises(UnboundLocalError, match="_pipeline|_pstate"):
            s._summarize_inner(heading, source)

    def test_map_reduce_failure_returns_error_result(self, tmp_path):
        """When the map-reduce reduce phase returns no raw, the
        orchestrator constructs the early-exit SummaryResult (the only
        'fail-fast at the orchestrator' construction site inside
        _summarize_inner itself)."""
        heading = "Big Chapter"
        source = a_chapter(60)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
            log_lines=logs,
        )
        s.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(responder=lambda *a, **k: None).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.success is False
        assert result.executive_summary == "[Error: Map-Reduce failed]"
        assert result.bullet_points == []
        assert result.thorough_summary == ""
        assert "Map-Reduce returned no response" in result.error_msg
        assert result.output_tokens == 0


class TestDeadlineExceeded:
    """The deadline-exceeded path — pin the 3 deadline-skip WARNING+INFO
    log pairs (scholar reflection, semantic dedup, bullet consolidation).

    NOTE: the deadline short-circuits fire INSIDE _phase_recovery_pass
    (the chapter_phases module), not directly inside _summarize_inner's
    body — but they're observable BEHAVIOR of the orchestrator's
    execution, so we pin them at this level. (If the post-judge tail is
    ever extracted into its own orchestrator, these pins will still
    apply at that level.)"""

    def test_deadline_armed_emits_three_skip_pairs(self, tmp_path):
        """Armed deadline (10_000s ago) → 3 deadline-skip pairs in the
        recovery phase (scholar / semantic-dedup / consolidation)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        armed_deadline(s, elapsed=10_000.0)
        result = s._summarize_inner(heading, source)
        assert result.success is True
        # The three skip-pair phases
        for phase in ("scholar reflection", "semantic dedup", "bullet consolidation"):
            assert_logged(
                logs,
                f"⏱️⚠️ Deadline exceeded (10000s > 600s) — skipping optional phase: {phase}",
            )
            assert_logged(logs, f"⏭️  {phase.capitalize()} skipped (deadline exceeded)")

    def test_deadline_armed_scholar_skipped_first(self, tmp_path):
        """The scholar-reflection skip is the FIRST deadline-skip (the
        scholar runs first in the recovery pass)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        armed_deadline(s, elapsed=10_000.0)
        s._summarize_inner(heading, source)
        # Find the index of the first scholar skip vs the first dedup skip
        scholar_idx = next(
            (i for i, (l, m) in enumerate(logs) if "scholar reflection" in m and "Deadline" in m),
            None,
        )
        dedup_idx = next(
            (i for i, (l, m) in enumerate(logs) if "semantic dedup" in m and "Deadline" in m),
            None,
        )
        assert scholar_idx is not None
        assert dedup_idx is not None
        assert scholar_idx < dedup_idx

    def test_deadline_armed_still_succeeds(self, tmp_path):
        """The deadline skips OPTIONAL phases only — the chapter still
        ships successfully (the fail-soft contract)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        armed_deadline(s, elapsed=10_000.0)
        result = s._summarize_inner(heading, source)
        assert result.success is True
        # Provenance still populated (finalize still ran)
        assert result.run_id != ""


# ════════════════════════════════════════════════════════════════════════════
# Section 4 — concepts/callouts injection (the prompt-augmentation log)
# ════════════════════════════════════════════════════════════════════════════


class TestConceptsCalloutsInjection:
    """Pin the 'Injecting N concepts + M callouts' log skeleton — the
    V3.2.0 B1 prompt-augmentation entry point."""

    def test_concepts_and_callouts_injection_logged(self, tmp_path):
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source, concepts=["casing", "baseline"], callouts=["tip"])
        # The exact skeleton
        assert_logged(logs, "Injecting 2 concepts + 1 callouts into prompt")

    def test_no_concepts_no_injection_log(self, tmp_path):
        """Without concepts, the DEBUG injection log does NOT fire."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source)
        # No 'Injecting' log
        assert not any("Injecting" in msg for (_lvl, msg) in logs)


# ════════════════════════════════════════════════════════════════════════════
# Section 5 — speculative-scholar machinery (fail-soft paths)
# ════════════════════════════════════════════════════════════════════════════


class TestSpeculativeScholarFailSoft:
    """Pin the 4 return-None branches of _p6_prepare_speculative_scholar
    (the V0.19 lever's fail-soft paths) — each branch is observable via
    the logs it emits (or doesn't)."""

    def test_lever_off_returns_none(self, tmp_path):
        """Default (lever off) → None. No Phase 6.2 logs."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        fresh_deadline(s)
        handle = s._p6_prepare_speculative_scholar(heading, source, {})
        assert handle is None
        assert not any("Phase 6.2" in m for (_lvl, m) in logs)

    def test_dual_model_architecture_returns_none_with_debug_log(self, tmp_path):
        """Dual-model architecture → None + the DEBUG skip log (model
        switching mid-call would race)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
            },
            request_fields={"model_architecture": "dual_local"},
            log_lines=logs,
        )
        fresh_deadline(s)
        handle = s._p6_prepare_speculative_scholar(heading, source, {})
        assert handle is None
        # The dual-model skip log fires at DEBUG
        msgs = [m for (lvl, m) in logs if lvl == "DEBUG" and "Phase 6.2" in m]
        assert any("judge∥scholar speculation skipped" in m for m in msgs)
        assert any("dual-model architecture switches models mid-call" in m for m in msgs)

    def test_scholar_reflections_enabled_returns_none(self, tmp_path):
        """When scholar_reflections_enabled is True, the speculative path
        runs the reflections-text variant (a different call shape) →
        return None (the sequential pipeline handles it)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
                "summarisation.scholar_reflections_enabled": True,
            },
            log_lines=logs,
        )
        fresh_deadline(s)
        handle = s._p6_prepare_speculative_scholar(heading, source, {})
        assert handle is None

    def test_deadline_exceeded_returns_none(self, tmp_path):
        """Armed deadline → None (the speculative scholar would run after
        the deadline — skip it)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
            },
            log_lines=logs,
        )
        armed_deadline(s, elapsed=10_000.0)
        handle = s._p6_prepare_speculative_scholar(heading, source, {})
        assert handle is None
        # The deadline WARNING fires (the helper's _deadline_exceeded log)
        assert any("Deadline exceeded" in m and "scholar reflection" in m for (_lvl, m) in logs)

    def test_lever_on_returns_handle_dict(self, tmp_path):
        """Lever on + single local + fresh deadline + reflections
        disabled → the handle dict is returned (the speculative-scholar
        machinery's 'armed' state)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
            },
            log_lines=logs,
        )
        fresh_deadline(s)
        handle = s._p6_prepare_speculative_scholar(heading, source, {})
        assert handle is not None
        # The RETURNED handle exposes ONLY the 3 callable keys — the
        # internal 'started'/'ok'/'snapshot'/'copy' keys live in the
        # closure (NOT exposed to the orchestrator). This is the V0.19
        # contract's seam: the orchestrator only calls the 3 hooks.
        assert set(handle.keys()) == {"prejudge_hook", "scholar_runner", "abort"}
        # None of the 3 has fired yet (prejudge_hook not called)
        # — pin this by verifying no Phase 6.2 launch log has fired.
        assert not any("Phase 6.2" in m for (_lvl, m) in logs)

    def test_prejudge_hook_marks_started(self, tmp_path):
        """The prejudge hook (called by _phase_validation_and_judge after
        its deterministic prologue) launches the speculative scholar
        thread and emits the launch INFO log (the V0.19 merge-or-rerun
        gate's armed state — pin the launch log skeleton).

        NOTE: the returned handle dict exposes ONLY the 3 callable keys
        (prejudge_hook / scholar_runner / abort). The internal
        'started'/'ok'/'snapshot'/'copy' keys are captured in the
        closure (NOT exposed to the orchestrator) — so we pin the
        externally-observable launch log instead of the internal flag."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
            },
            log_lines=logs,
        )
        fresh_deadline(s)
        parsed = {
            "bullet_points": ["b1", "b2"],
            "executive_summary": "exec",
            "thorough_summary": "tho",
            "key_distinctions": "kd",
            "theoretical_tensions": "tt",
        }
        handle = s._p6_prepare_speculative_scholar(heading, source, parsed)
        assert handle is not None
        # Call the prejudge hook (the judge phase's call site)
        handle["prejudge_hook"](["b1", "b2"], "exec", "tho")
        # The launch INFO log fires (the externally-observable signal
        # that the speculative scholar thread was started)
        assert any(
            "🎓 Phase 6.2: speculative scholar reflection launched" in m
            and "overlapping the judge tail" in m
            for (_lvl, m) in logs
        )

    def test_scholar_runner_discards_when_state_changed(self, tmp_path):
        """The merge-or-rerun gate: when the snapshot changed (the judge
        tail mutated the state), the speculative result is DISCARDED and
        the sequential pipeline re-runs it inline. Pin the discard INFO
        log skeleton (the V0.19 contract's 'state changed' leg)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(
            tmp_path,
            settings_values={
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_judge_scholar": True,
            },
            log_lines=logs,
        )
        fresh_deadline(s)
        parsed = {
            "bullet_points": ["b1", "b2"],
            "executive_summary": "exec",
            "thorough_summary": "tho",
            "key_distinctions": "kd",
            "theoretical_tensions": "tt",
        }
        handle = s._p6_prepare_speculative_scholar(heading, source, parsed)
        assert handle is not None
        # Start the speculative scholar (prejudge hook)
        handle["prejudge_hook"](["b1", "b2"], "exec", "tho")
        # Mutate the parsed_now state the scholar_runner sees
        parsed_now = dict(parsed)
        parsed_now["bullet_points"] = ["DIFFERENT"]  # state changed
        # The scholar_runner should detect the mismatch and discard
        # (the discard path re-runs sequentially — but scholar_enabled
        # is False by default → calls _scholar_reflection_gapfill_only,
        # which is mocked-via-ScriptedLLM as the aux response)
        handle["scholar_runner"](parsed_now, scholar_enabled=False)
        # The discard log fires
        assert any(
            "Phase 6.2: speculative scholar DISCARDED" in m
            and "judge tail changed the summary state" in m
            for (_lvl, m) in logs
        )


# ════════════════════════════════════════════════════════════════════════════
# Section 6 — coverage floor + theorist floor invocation
# ════════════════════════════════════════════════════════════════════════════


class TestCoverageAndTheoristFloors:
    """Pin that the V18.20.3.13 thorough-theorist floor + the V18.20.3.5
    deterministic recall-floor probe both fire on the happy path
    (the V0.4.24 audit backlog #3's layer-4 enforcement)."""

    def test_recall_floor_dict_populated_on_happy_path(self, tmp_path):
        """The recall-floor dict is stamped onto the SummaryResult
        (parsed['recall_floor'] → result.recall_floor) — pin its 9 keys."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        result = s._summarize_inner(heading, source)
        assert result.recall_floor is not None
        assert isinstance(result.recall_floor, dict)
        # The 9 keys deterministic_recall_floor returns (pinned on the
        # live source behavior — see core/summarisation/recall_floor.py)
        expected_keys = {
            "theorists_covered",
            "theorists_total",
            "theorists_missing",
            "conclusion_items_covered",
            "conclusion_items_total",
            "conclusion_items_missing",
            "log_parts",
            "theorists_probe_failed",
            "conclusion_items_probe_failed",
        }
        assert expected_keys <= set(result.recall_floor.keys()), (
            f"recall_floor missing keys: {expected_keys - set(result.recall_floor.keys())}"
        )

    def test_recall_floor_log_skeleton_when_log_parts_nonempty(self, tmp_path):
        """When the recall-floor probe has log_parts to emit, the V18.20.3.4
        INFO log skeleton fires (pin the literal). This requires an analysis
        file under the output dir — write a minimal one."""
        # write_analysis_tree is imported at module top (from test_p2_summarizer_harness)

        heading, source = golden_chapter()
        # Write an analysis tree with one generic author so the recall floor
        # has something to measure (the floor's regex probes the analysis
        # file's "Citations" + "Conclusion" sections).
        write_analysis_tree(tmp_path, authors=["Author A"])
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        s._summarize_inner(heading, source)
        # The V18.20.3.4 log skeleton (the deterministic recall floor)
        assert_logged(logs, "📏 V18.20.3.4: Deterministic recall floor (final set):")
        # The honest-coverage label
        assert_logged(logs, "the honest coverage number")

    def test_thorough_theorist_floor_invoked_when_thorough_requested(self, tmp_path, monkeypatch):
        """The V18.20.3.13 thorough-theorist floor mixin is invoked from
        _phase_postchecks_and_floors when ``_inc_thorough_lp`` is True
        (the default request has thorough requested). Pin the call by
        recording it (the A2 _RecordingSelf pattern; monkeypatch
        auto-restores so the Summarizer class isn't poisoned for later
        tests in the session)."""
        heading, source = golden_chapter()
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        ScriptedLLM(primary_response=_full_response(source)).install(s)
        fresh_deadline(s)
        # Wrap _thorough_theorist_floor to record the call.
        # NB: this is set on the class (not the instance) because the
        # mixin dispatch resolves through the MRO. monkeypatch restores
        # at test exit (no class poisoning).
        calls: list[str] = []

        real_floor = type(s)._thorough_theorist_floor

        def _wrap(self_inner, *a, **kw):
            calls.append("_thorough_theorist_floor")
            return real_floor(self_inner, *a, **kw)

        monkeypatch.setattr(type(s), "_thorough_theorist_floor", _wrap, raising=False)
        result = s._summarize_inner(heading, source)
        assert result.success is True
        assert "_thorough_theorist_floor" in calls, (
            "the thorough-theorist floor must be invoked on the happy path"
        )


# ════════════════════════════════════════════════════════════════════════════
# Section 7 — return-shape summary (cross-branch pins)
# ════════════════════════════════════════════════════════════════════════════


class TestReturnShapeAcrossBranches:
    """Cross-branch pins: each branch the orchestrator can exit through
    has a DISTINCT SummaryResult shape. Pin the distinguishing fields
    so a future extraction that conflates two branches breaks the test."""

    def test_empty_input_gate_shape_distinct_from_primary_failure(self, tmp_path):
        """The empty-input gate's error_msg starts with 'Segment too
        small'; the primary-failure's starts with 'Primary model'.
        Pin BOTH so a future merge of the two early-exit paths is
        visible."""
        # Empty-input
        s1 = make_summarizer(tmp_path)
        ScriptedLLM(primary_response="never").install(s1)
        fresh_deadline(s1)
        r1 = s1._summarize_inner("Tiny", "Far too small to summarize safely.")
        # Primary failure
        heading, source = golden_chapter()
        s2 = make_summarizer(Path(str(tmp_path) + "_2"))
        s2._last_llm_error_type = "timeout"
        ScriptedLLM(responder=lambda *a, **k: None).install(s2)
        fresh_deadline(s2)
        r2 = s2._summarize_inner(heading, source)
        assert r1.error_msg.startswith("Segment too small")
        assert r2.error_msg.startswith("Primary model")
        # Both fail
        assert r1.success is False and r2.success is False

    def test_map_reduce_failure_shape_distinct_from_primary_failure(self, tmp_path):
        """The map-reduce failure's executive_summary = '[Error: Map-Reduce
        failed]'; the primary-failure's executive_summary = ''."""
        heading = "Big Chapter"
        source = a_chapter(60)
        # Map-reduce failure
        s1 = make_summarizer(
            tmp_path,
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
        )
        s1.MAP_REDUCE_THRESHOLD = 500
        ScriptedLLM(responder=lambda *a, **k: None).install(s1)
        fresh_deadline(s1)
        r1 = s1._summarize_inner(heading, source)
        # Primary failure
        s2 = make_summarizer(
            Path(str(tmp_path) + "_mr2"),
            model=LEGACY_MODEL,
            request_fields={"summarisation_max_context_tokens": 32768},
        )
        s2._last_llm_error_type = "timeout"
        ScriptedLLM(responder=lambda *a, **k: None).install(s2)
        fresh_deadline(s2)
        r2 = s2._summarize_inner(heading, source)
        assert r1.executive_summary == "[Error: Map-Reduce failed]"
        assert r2.executive_summary == ""
        assert r1.error_msg != r2.error_msg

    def test_happy_path_shape_distinct_from_failure_paths(self, tmp_path):
        """The happy-path result has populated provenance + populated
        summary content; all failure paths have empty provenance and at
        least one empty summary field."""
        heading, source = golden_chapter()
        s_ok = make_summarizer(tmp_path)
        ScriptedLLM(primary_response=_full_response(source)).install(s_ok)
        fresh_deadline(s_ok)
        r_ok = s_ok._summarize_inner(heading, source)

        # Tiny
        s_tiny = make_summarizer(Path(str(tmp_path) + "_tiny"))
        ScriptedLLM(primary_response="never").install(s_tiny)
        fresh_deadline(s_tiny)
        r_tiny = s_tiny._summarize_inner("Tiny", "Far too small to summarize safely.")

        assert r_ok.success is True
        assert r_tiny.success is False
        # The happy path's provenance is populated; the failure path's isn't.
        assert r_ok.run_id != ""
        assert r_tiny.run_id == ""
        # The happy path's summary content is populated; the failure path's isn't.
        assert r_ok.executive_summary != ""
        assert r_tiny.executive_summary == ""
        assert r_ok.bullet_points != []
        assert r_tiny.bullet_points == []
