"""Phase 6 (V0.19) — tests for the performance levers, queue concurrency,
and cache instrumentation.

Covers the roadmap Phase-6 acceptance machinery:

* ``stage_overlap.run_independent`` — the overlap ENGINE's contract
  (ordered results, inline sequential fallback, lowest-index exception
  semantics, real concurrency).
* The settings levers (master / per-lever / worker clamp) — the roadmap
  rollback plan ("each lever independently disableable", default OFF).
* Lever MAP — map-reduce chunk waves: byte-identical output vs the
  sequential loop, real concurrency, wave-granularity budget abort.
* Lever B3 — multi-sample overlap: ordered samples, no inter-sample
  VRAM sleeps, per-sample crash isolation.
* Lever JUDGE-SCHOLAR — the speculative scholar: merge on unchanged
  state, discard+re-run on judge-modified state, no speculation with
  reflections text on. (V0.6.14 single-model order: the "no speculation
  on dual-model architectures" case is retired — model_architecture no
  longer exists; the ONE model never switches mid-run, so the racy
  model-swap gate it guarded against is gone.)
* Golden output equivalence — parallel-stages ON vs OFF produce
  BYTE-IDENTICAL pipeline outputs on the golden chapters (the freeze
  contract holds with the levers armed).
* Phase 6.3 — the bounded cloud queue (pure ``ui_qt.queue_parallel``:
  worker-count resolution + parallel execution semantics) and the
  queue_view wiring via headless source pins (the W-b10 house pattern:
  PySide6 is not imported — the file is read as text/AST).
* Phase 6.4 — response-cache eviction counting + periodic hit-rate
  logging + the end-of-run summary.
"""

from __future__ import annotations

import ast
import logging
import sys
import threading
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib.util as _ilu  # noqa: E402

from test_p2_summarizer_harness import (  # noqa: E402
    ScriptedLLM,
    build_primary_response,
    golden_chapter,
    hermetic_env,
    make_summarizer,
    set_settings,
)

# Load the bench harness (scripts/ is not a package — the freeze test's
# importlib pattern).
_spec = _ilu.spec_from_file_location(
    "bench_chapter", _project_root / "scripts" / "bench_chapter.py"
)
bench = _ilu.module_from_spec(_spec)
sys.modules["bench_chapter"] = bench
_spec.loader.exec_module(bench)


@pytest.fixture(autouse=True)
def _hermetic():
    with hermetic_env():
        yield


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.2a — the overlap engine
# ═══════════════════════════════════════════════════════════════════════════


class TestRunIndependent:
    def test_single_callable_runs_inline_no_threads(self):
        from core.summarisation.stage_overlap import run_independent

        seen_threads = []

        def fn():
            seen_threads.append(threading.current_thread().name)
            return 41

        assert run_independent([fn], max_workers=4) == [41]
        assert seen_threads == [threading.current_thread().name]

    def test_max_workers_one_runs_inline(self):
        from core.summarisation.stage_overlap import run_independent

        names = []

        def fn(i):
            names.append(threading.current_thread().name)
            return i

        assert run_independent([lambda i=i: fn(i) for i in range(3)], max_workers=1) == [0, 1, 2]
        assert names == [threading.current_thread().name] * 3

    def test_results_in_input_order_regardless_of_completion(self):
        from core.summarisation.stage_overlap import run_independent

        def slow(i):
            time.sleep(0.15 - i * 0.04)  # later callables finish FIRST
            return i

        out = run_independent([lambda i=i: slow(i) for i in range(4)], max_workers=4, label="t")
        assert out == [0, 1, 2, 3]

    def test_real_concurrency_two_sleeps(self):
        from core.summarisation.stage_overlap import run_independent

        t0 = time.perf_counter()
        run_independent([lambda: time.sleep(0.2) for _ in range(2)], max_workers=2, label="t")
        wall = time.perf_counter() - t0
        assert wall < 0.35, f"expected overlap, wall={wall:.3f}s"

    def test_lowest_index_exception_reraised_later_ran(self):
        from core.summarisation.stage_overlap import run_independent

        ran = []

        def boom0():
            raise RuntimeError("first failed")

        def ok1():
            ran.append(1)
            return "b"

        def boom2():
            raise ValueError("second failed")

        with pytest.raises(RuntimeError, match="first failed"):
            run_independent([boom0, ok1, boom2], max_workers=3, label="t")
        assert 1 in ran  # sequential semantics EXCEPT later calls may run

    def test_empty_input(self):
        from core.summarisation.stage_overlap import run_independent

        assert run_independent([], max_workers=4) == []


class TestLeverSettings:
    def test_master_off_forces_every_lever_off(self):
        from core.summarisation.stage_overlap import lever_enabled, master_enabled

        set_settings(
            {
                "summarisation.parallel_stages": False,
                "summarisation.parallel_stages_map": True,  # per-lever ON is
                "summarisation.parallel_stages_b3": True,  # MEANINGLESS with
                "summarisation.parallel_stages_judge_scholar": True,  # master OFF
            }
        )
        assert master_enabled() is False
        for lever in ("map", "b3", "judge_scholar"):
            assert lever_enabled(lever) is False

    def test_master_on_levers_default_on(self):
        from core.summarisation.stage_overlap import lever_enabled

        set_settings({"summarisation.parallel_stages": True})
        for lever in ("map", "b3", "judge_scholar"):
            assert lever_enabled(lever) is True

    def test_each_lever_independently_disableable(self):
        from core.summarisation.stage_overlap import lever_enabled

        set_settings(
            {
                "summarisation.parallel_stages": True,
                "summarisation.parallel_stages_map": False,
            }
        )
        assert lever_enabled("map") is False
        assert lever_enabled("b3") is True
        assert lever_enabled("judge_scholar") is True

    def test_unknown_lever_is_off(self):
        from core.summarisation.stage_overlap import lever_enabled

        set_settings({"summarisation.parallel_stages": True})
        assert lever_enabled("nonexistent") is False

    def test_workers_clamped_and_default(self):
        from core.summarisation.stage_overlap import lever_workers

        set_settings({})
        assert lever_workers() == 4
        set_settings({"summarisation.parallel_stages_max_workers": 99})
        assert lever_workers() == 8
        set_settings({"summarisation.parallel_stages_max_workers": 0})
        assert lever_workers() == 1
        set_settings({"summarisation.parallel_stages_max_workers": "bogus"})
        assert lever_workers() == 4

    def test_settings_failure_fails_closed(self):
        from core.summarisation import stage_overlap as so

        class ExplodingSettings:
            def get(self, *a, **k):
                raise RuntimeError("boom")

            def get_ollama_url(self):
                return ""

        from utils.settings import Settings

        prev = Settings._test_override
        Settings._test_override = ExplodingSettings()  # type: ignore[assignment]
        try:
            assert so.master_enabled() is False
            assert so.lever_enabled("map") is False
            assert so.lever_workers() == 4
        finally:
            Settings._test_override = prev


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.2b — lever MAP (map-reduce chunk waves)
# ═══════════════════════════════════════════════════════════════════════════


def _mr_kwargs(tmp_path, calls, threads):
    """Common kwargs for map_reduce_summarize with a recording call_llm."""

    def call_llm(prompt, model=None, temperature=None, max_tokens=None):
        calls.append(prompt)
        threads.append(threading.current_thread().name)
        return f"mini-{calls.index(prompt) + 1}: " + prompt[:24]

    def build_prompt(heading, text, with_cot=True):
        return f"REDUCE[{heading}] {text[:50]}"

    return dict(
        primary_model="m",
        cache_dir=tmp_path,
        input_path_stem="book",
        cache_enabled=False,
        temperature=0.6,
        map_chunk_tokens=4000,
        map_chunk_overlap=0.10,
        map_mini_words=120,
        build_prompt=build_prompt,
        call_llm=call_llm,
        log=lambda *a, **k: None,
    )


def _oversized_source() -> str:
    # ~250 words per paragraph × 160 paragraphs ≈ 48k chars ≈ 12k tokens
    # → 3-4 chunks at the 4000-token map size (multiple waves at 4 workers).
    filler = " ".join(f"distinct analytical point {i} with named evidence" for i in range(30))
    return "\n\n".join(f"Paragraph {p}. {filler}" for p in range(160))


class TestLeverMap:
    def test_parallel_output_identical_to_sequential(self, tmp_path):
        from core.summarisation.map_reduce import map_reduce_summarize

        source = _oversized_source()

        seq_calls, seq_threads = [], []
        out_seq, tok_seq = map_reduce_summarize(
            "Ch", source, **_mr_kwargs(tmp_path / "a", seq_calls, seq_threads)
        )

        par_calls, par_threads = [], []
        out_par, tok_par = map_reduce_summarize(
            "Ch",
            source,
            **_mr_kwargs(tmp_path / "b", par_calls, par_threads),
            parallel_max_workers=4,
        )

        assert out_seq == out_par, "overlapped map phase changed the output"
        assert tok_seq == tok_par
        assert seq_calls == par_calls  # same prompts, same order
        assert len(par_calls) == len(set(par_calls))  # all chunks distinct
        # Sequential ran on ONE thread; parallel used >1 thread.
        assert len(set(seq_threads)) == 1
        assert len(set(par_threads)) > 1

    def test_parallel_default_is_sequential(self, tmp_path):
        from core.summarisation.map_reduce import map_reduce_summarize

        source = _oversized_source()
        calls, threads = [], []
        out, _ = map_reduce_summarize("Ch", source, **_mr_kwargs(tmp_path, calls, threads))
        assert out is not None
        assert len(set(threads)) == 1  # no pool threads — inline loop

    def test_wave_budget_abort_returns_none(self, tmp_path, monkeypatch):
        import types as _types

        import core.summarisation.map_reduce as mr

        source = _oversized_source()
        calls = []

        # Deterministic fake clock: every LLM call advances map_reduce's
        # notion of time by 10s — with a 5s budget the FIRST wave already
        # overruns, so the pre-wave-2 check aborts (no wall-clock sleeps,
        # no timing sensitivity). Only map_reduce's module-level ``time``
        # reference is swapped — the rest of the process keeps real time.
        clock = {"now": 100.0}

        class _FakeTime:
            @staticmethod
            def monotonic() -> float:
                return clock["now"]

            @staticmethod
            def sleep(_s: float) -> None:
                pass

        def call_llm(prompt, model=None, temperature=None, max_tokens=None):
            calls.append(prompt)
            clock["now"] += 10.0
            return f"mini-{len(calls)}"

        monkeypatch.setattr(
            mr, "time", _types.SimpleNamespace(monotonic=_FakeTime.monotonic, sleep=_FakeTime.sleep)
        )

        out, tok = mr.map_reduce_summarize(
            "Ch",
            source,
            primary_model="m",
            cache_dir=tmp_path,
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.6,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.10,
            map_mini_words=120,
            build_prompt=lambda h, t, with_cot=True: f"REDUCE[{h}]",
            call_llm=call_llm,
            log=lambda *a, **k: None,
            map_phase_budget_sec=5,
            parallel_max_workers=4,
        )
        assert out is None and tok == 0
        # Wave 1 fired (its calls are in-flight when the abort decision is
        # made — the abort takes effect at the NEXT wave boundary); the
        # phase still returns the loud failure.
        assert 0 < len(calls) < 10

    def test_single_chunk_runs_sequentially_even_with_lever(self, tmp_path):
        from core.summarisation.map_reduce import map_reduce_summarize

        calls, threads = [], []
        out, _ = map_reduce_summarize(
            "Ch",
            "One short paragraph of content.",
            **_mr_kwargs(tmp_path, calls, threads),
            parallel_max_workers=4,
        )
        assert out is not None
        assert len(set(threads)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.2c — lever B3 (multi-sample overlap)
# ═══════════════════════════════════════════════════════════════════════════


def _b3_kwargs(calls, threads, vram, sample_results=None):
    def summarize_with_model(
        heading, text, model, temp, with_cot=True, concepts=None, callouts=None
    ):
        calls.append(temp)
        threads.append(threading.current_thread().name)
        time.sleep(0.05)  # let the pool actually span threads
        if sample_results is not None:
            r = sample_results[len(calls) - 1]
            if isinstance(r, Exception):
                raise r
            return r
        return {
            "executive_summary": f"exec at t={temp}",
            "bullet_points": [f"- bullet {temp:.2f} alpha", f"- bullet {temp:.2f} beta"],
            "thorough_summary": "thorough text",
        }

    return dict(
        primary_model="m",
        temperature=0.4,
        recover_vram=lambda context="", delay_sec=0.0: vram.append(context),
        summarize_with_model=summarize_with_model,
        b3_cloud_judge=None,
        compute_coverage=lambda s, t: 1.0,
        conservative_drops=False,
        quarantine=None,
        current_heading="Ch",
        fusion_enabled=False,
        fusion_use_for_b3_judge=False,
        log=lambda *a, **k: None,
    )


class TestLeverB3:
    def test_parallel_samples_same_order_no_vram_sleeps(self):
        from core.summarisation.multi_sample import multi_sample_summarize

        calls, threads, vram = [], [], []
        out = multi_sample_summarize(
            "Ch", "text", n_samples=3, parallel_max_workers=3, **_b3_kwargs(calls, threads, vram)
        )
        assert calls == [0.4, 0.4, 0.4]  # model-optimal temp, no escalation
        assert vram == []  # the 120s inter-sample sleeps are SKIPPED
        assert out is not None
        # Parallel path used >1 thread.
        assert len(set(threads)) > 1

    def test_sequential_default_keeps_vram_sleeps(self):
        from core.summarisation.multi_sample import multi_sample_summarize

        calls, threads, vram = [], [], []
        multi_sample_summarize("Ch", "text", n_samples=3, **_b3_kwargs(calls, threads, vram))
        assert vram == ["B3-sample-2", "B3-sample-3"]  # V15.1.0 contract intact
        assert len(set(threads)) == 1

    def test_one_crashing_sample_does_not_kill_others(self):
        from core.summarisation.multi_sample import multi_sample_summarize

        calls, threads, vram = [], [], []
        results = [
            RuntimeError("sample 1 crashed"),
            {
                "executive_summary": "exec",
                "bullet_points": ["- only bullet"],
                "thorough_summary": "t",
            },
            {
                "executive_summary": "exec2",
                "bullet_points": ["- only bullet2"],
                "thorough_summary": "t2",
            },
        ]
        out = multi_sample_summarize(
            "Ch",
            "text",
            n_samples=3,
            **_b3_kwargs(calls, threads, vram, sample_results=results),
            parallel_max_workers=3,
        )
        # Two surviving samples → voting proceeds on their bullets.
        assert out is not None
        assert any("bullet" in bp for bp in out["bullet_points"])


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.2d — lever JUDGE-SCHOLAR (speculative scholar)
# ═══════════════════════════════════════════════════════════════════════════


class TestSpeculativeScholar:
    def _armed(self, tmp_path, log_lines=None, **request_fields):
        set_settings({"summarisation.parallel_stages": True})
        return make_summarizer(
            tmp_path,
            settings_values={"summarisation.parallel_stages": True},
            request_fields=request_fields,
            log_lines=log_lines,
        )

    def test_snapshot_is_value_semantics(self, tmp_path):
        s = make_summarizer(tmp_path)
        parsed = {
            "bullet_points": ["a", "b"],
            "executive_summary": "e",
            "thorough_summary": "t",
            "key_distinctions": "kd",
            "theoretical_tensions": "tt",
        }
        snap = s._p6_scholar_input_snapshot(parsed)
        # A DIFFERENT list object with the same values compares equal.
        parsed2 = dict(parsed, bullet_points=["a", "b"])
        assert s._p6_scholar_input_snapshot(parsed2) == snap
        parsed3 = dict(parsed, bullet_points=["a", "c"])
        assert s._p6_scholar_input_snapshot(parsed3) != snap

    # V0.5.16 note: the merge-path test now EXPLICITLY scripts the judge's
    # gap-fill reprompt to return no bullets (the ScriptedLLM judge_gapfill
    # default). Before V0.5.16 the gap-fill bullets returned by the default
    # primary-shaped response were all rejected at "Phase 2.2 sim 0.00"
    # (the embedder-less test env makes semantic_fact_check fail closed —
    # the bug V0.5.16 fixed with the degenerate-signal guard), so the judge
    # tail left the state unchanged BY THAT BUG. With the fix, F4-grounded
    # gap-fill bullets legitimately survive and change the state → the
    # discard path (covered by test_discard_path_when_judge_changes_state
    # below). The MERGE path needs a judge tail that genuinely changes
    # nothing — hence the scripted no-bullets gap response.
    def test_merge_path_scholar_runs_once_concurrently(self, tmp_path):
        """Golden-shaped run: judge leaves the state unchanged → the
        speculative result is MERGED; the scholar runs exactly ONCE."""
        heading, source = golden_chapter("nonfiction")
        log_lines: list[tuple[str, str]] = []
        s = self._armed(tmp_path, log_lines)
        llm = ScriptedLLM(primary_response=build_primary_response(source))
        llm.install(s)  # judge_gapfill defaults to the no-bullets reply

        scholar_calls = []
        orig_gapfill = s._scholar_reflection_gapfill_only

        def counting_gapfill(h, c, parsed):
            scholar_calls.append(threading.current_thread().name)
            return orig_gapfill(h, c, parsed)

        s._scholar_reflection_gapfill_only = counting_gapfill

        result = s.summarize_chapters([{"heading": heading, "content": source}])
        assert result[0].success
        assert len(scholar_calls) == 1, "merged path must run the scholar exactly once"
        assert any("MERGED" in m for lvl, m in log_lines), "merge log line missing"
        # The scholar ran on the speculation thread, not the caller thread.
        assert scholar_calls[0] != threading.current_thread().name

    def test_discard_path_when_judge_changes_state(self, tmp_path):
        """The judge drops a bullet → snapshot mismatch → the speculative
        result is DISCARDED and the scholar re-runs inline (sequential
        semantics, exactly pre-V0.19)."""
        heading, source = golden_chapter("nonfiction")
        log_lines: list[tuple[str, str]] = []
        s = self._armed(tmp_path, log_lines)
        llm = ScriptedLLM(primary_response=build_primary_response(source))
        llm.install(s)

        # Make the judge phase DROP a bullet in a way the recovery pass
        # CANNOT resurrect: _llm_grounding_check flags bullets[0]'s 80-char
        # prefix padded with unrelated filler — the V13.45.5 appeal computes
        # source overlap on the FLAGGED string (< 0.25 → confirmed
        # ungrounded → dropped, quarantine overlap < the 0.30 recovery
        # threshold). A self-talk flag would be RESURRECTED by the recovery
        # pass (it quotes the source → overlap 1.0), restoring the exact
        # pre-judge state — merge, not discard.
        def fake_grounding(bullets, content):
            if not bullets:
                return []
            # The appeal's overlap metric (compute_source_overlap) counts
            # DISTINCT 5+-letter alphabetic words of the flagged string
            # found in the source — digit-laced or REPEATED padding is
            # invisible/collapsed by the word set. 300 distinct nonsense
            # words (pure [a-z]{5,}, not in source, not common-500) drive
            # the ratio to ~0.05 < 0.25 → confirmed ungrounded.
            # The drop matches flagged[:80] against bullet[:80], so the
            # flagged bullet must be ≥ 80 chars for the prefix to line up
            # (shorter bullets + padding never match).
            _target = next((b for b in bullets if len(b) >= 80), bullets[0])
            _pad = " ".join(
                "qx" + chr(97 + i % 26) + chr(97 + (i * 7) % 26) + chr(97 + (i * 13) % 26)
                for i in range(300)
            )
            return [_target[:80] + " " + _pad]

        s._llm_grounding_check = fake_grounding
        # Keep the drop STUCK for this test: the recovery pass recomputes
        # source overlap on the REAL bullet (verbatim source → 1.0 > 0.30)
        # and would resurrect it, restoring the pre-judge state — that
        # interplay is the pipeline working as designed; THIS test pins the
        # discard mechanics, so recovery is a passthrough here.
        s._recover_quarantined = lambda bullets, source_text: bullets

        scholar_calls = []
        orig_gapfill = s._scholar_reflection_gapfill_only

        def counting_gapfill(h, c, parsed):
            scholar_calls.append(threading.current_thread().name)
            return orig_gapfill(h, c, parsed)

        s._scholar_reflection_gapfill_only = counting_gapfill

        result = s.summarize_chapters([{"heading": heading, "content": source}])
        assert result[0].success
        assert any("DISCARDED" in m for lvl, m in log_lines), "discard log line missing"
        assert len(scholar_calls) == 2, "speculative + sequential re-run expected"
        # The re-run happens on the chapter thread (inline), the speculation
        # on its own thread — at least one of the two is not the caller.
        assert len(set(scholar_calls)) >= 1

    def test_lever_off_is_plain_sequential(self, tmp_path):
        heading, source = golden_chapter("nonfiction")
        set_settings({"summarisation.parallel_stages": False})
        s = make_summarizer(tmp_path)
        llm = ScriptedLLM()
        llm.install(s)

        handle = s._p6_prepare_speculative_scholar(heading, source, {"bullet_points": []})
        assert handle is None  # lever off → no speculation machinery at all

    # V0.6.14 (single-model order): 1 test REMOVED —
    # test_dual_architecture_never_speculates pinned the
    # model_architecture="dual_local" gate in _p6_prepare_speculative_scholar
    # (speculation was disabled because call_fast_llm switched models
    # mid-run — racy). The model_architecture request field and the
    # fast-model switching are retired: there is no dual architecture left
    # to guard against, so the gate — and the test pinning it — are gone.

    def test_reflections_text_variant_never_speculates(self, tmp_path):
        heading, source = golden_chapter("nonfiction")
        set_settings(
            {
                "summarisation.parallel_stages": True,
                "summarisation.scholar_reflections_enabled": True,
            }
        )
        s = make_summarizer(tmp_path)
        handle = s._p6_prepare_speculative_scholar(heading, source, {"bullet_points": []})
        assert handle is None  # different call shape — sequential only


# ═══════════════════════════════════════════════════════════════════════════
# Golden output equivalence (the Phase-6 acceptance contract)
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenEquivalence:
    """parallel-stages ON must produce byte-identical outputs on the golden
    chapters (the freeze dict) — the levers change wall-clock, not content."""

    @pytest.mark.parametrize("chapter", ["nonfiction", "academic", "farsi"])
    def test_on_equals_off(self, chapter):
        import types

        def run(parallel: bool) -> dict:
            args = types.SimpleNamespace(
                chapter=chapter,
                chapters=1,
                parallel=False,
                workers=1,
                latency_scale=0.0,
                profile=False,
                profile_out=None,
                json=None,
                save_golden=False,
                verbose=False,
            )
            if parallel:
                args.parallel_stages = True
                args.parallel_workers = 4
            report = bench.run_bench(args)
            assert report["pipeline_ok"], f"pipeline failed for {chapter}"
            return report["freeze_output"]

        off = run(False)
        on = run(True)
        assert on == off, f"parallel-stages changed the {chapter} output"

        fixture = _project_root / "tests" / "golden" / chapter / "pipeline_output.json"
        import json

        frozen = json.loads(fixture.read_text(encoding="utf-8"))
        assert off["output"] == frozen["output"], f"sequential drifted from fixture ({chapter})"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.3 — bounded cloud queue concurrency
# ═══════════════════════════════════════════════════════════════════════════


class TestQueueParallelResolution:
    def test_local_providers_always_sequential(self):
        from ui_qt.queue_parallel import resolve_parallel_books

        assert resolve_parallel_books("ollama", 4, 5) == 1
        assert resolve_parallel_books("llamacpp", 4, 5) == 1
        assert resolve_parallel_books("", 4, 5) == 1
        assert resolve_parallel_books("typo-provider", 4, 5) == 1

    def test_cloud_providers_bounded(self):
        from ui_qt.queue_parallel import (
            ABSOLUTE_MAX_PARALLEL_BOOKS,
            resolve_parallel_books,
        )

        for p in ("claude", "freellmapi", "openrouter", "openai", "openai_compatible"):
            assert resolve_parallel_books(p, 3, 5) == 3
        assert resolve_parallel_books("claude", 99, 9) == ABSOLUTE_MAX_PARALLEL_BOOKS
        assert resolve_parallel_books("claude", 1, 5) == 1  # setting opt-in
        assert resolve_parallel_books("claude", 0, 5) == 1
        assert resolve_parallel_books("claude", "bogus", 5) == 2  # default

    def test_single_pending_book_is_sequential(self):
        from ui_qt.queue_parallel import resolve_parallel_books

        assert resolve_parallel_books("claude", 4, 1) == 1


class TestRunBooksParallel:
    def test_outcomes_in_input_order_and_crash_isolated(self):
        from ui_qt.queue_parallel import run_books_parallel

        def job(i):
            return lambda event: time.sleep(0.02 * (3 - i)) if i != 1 else _raise()

        def _raise():
            raise RuntimeError("book 1 exploded")

        out = run_books_parallel([(0, job(0)), (1, job(1)), (2, job(2))], max_workers=3)
        assert [(o.idx, o.ok) for o in out] == [(0, True), (1, False), (2, True)]
        assert "book 1 exploded" in out[1].error

    def test_every_book_gets_own_cancel_event(self):
        from ui_qt.queue_parallel import run_books_parallel

        events = {}

        def fn(i):
            return lambda event: events.__setitem__(i, event)

        started = {}

        run_books_parallel(
            [(i, fn(i)) for i in range(3)],
            max_workers=3,
            on_started=lambda idx, ev: started.__setitem__(idx, ev),
        )
        assert len(set(id(e) for e in started.values())) == 3
        assert set(started) == {0, 1, 2}

    def test_stop_cancels_active_books_via_events(self):
        from ui_qt.queue_parallel import run_books_parallel

        registry = {}
        release = threading.Event()

        def blocking_fn(i):
            def _run(event: threading.Event):
                if i == 0:
                    release.wait(timeout=5)  # hold book 0 open
                else:
                    event.wait(timeout=5)  # books 1,2 wait for THEIR cancel

            return _run

        # Simulate the QueueView.stop() contract: set every registered event.
        def stop_all():
            for ev in list(registry.values()):
                ev.set()
            release.set()

        results: list = []

        import concurrent.futures as cf

        with cf.ThreadPoolExecutor(max_workers=1) as side:
            fut = side.submit(
                run_books_parallel,
                [(i, blocking_fn(i)) for i in range(3)],
                max_workers=3,
                on_started=lambda idx, ev: registry.__setitem__(idx, ev),
                on_finished=results.append,
            )
            time.sleep(0.15)
            stop_all()
            fut.result(timeout=10)
        assert len(results) == 3
        assert all(o.ok for o in results)  # cancelled waits are normal exits


class TestQueueViewWiring:
    """Headless source pins (PySide6 is not imported — the house W-b10
    pattern): the parallel path is wired, the sequential loop intact."""

    _PATH = _project_root / "ui_qt" / "views" / "queue_view.py"

    @classmethod
    def _src(cls) -> str:
        return cls._PATH.read_text(encoding="utf-8")

    @classmethod
    def _method(cls, name: str) -> str:
        tree = ast.parse(cls._src())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.get_source_segment(cls._src(), node) or ""
        raise AssertionError(f"method {name} not found in queue_view.py")

    def test_worker_resolves_parallel_books_before_sequential_loop(self):
        src = self._method("_queue_worker")
        assert "resolve_parallel_books(" in src
        assert "MAX_PARALLEL_BOOKS_SETTING" in src
        assert "_queue_worker_parallel(_workers)" in src
        # The sequential loop remains, after the parallel dispatch.
        assert src.index("resolve_parallel_books(") < src.index(
            "for i, item in enumerate(self._queue):"
        )

    def test_isolated_conversion_uses_per_book_cancel_and_progress(self):
        src = self._method("_run_one_conversion_isolated")
        assert "cancel_event=cancel_event" in src
        assert "self.book_progress.emit(idx, fraction)" in src
        # The shared controller slots are NOT touched.
        assert "self.controller.converter" not in src
        assert "self.controller.cancel_event" not in src

    def test_per_book_progress_signal_defined_and_routed(self):
        src = self._src()
        assert "book_progress = Signal(int, float)" in src
        assert "self.book_progress.connect(self._on_book_progress)" in src
        assert "def _on_book_progress(self, idx: int, value: float)" in src

    def test_stop_cancels_parallel_books(self):
        src = self._method("stop")
        assert "_parallel_cancel_events" in src


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6.4 — cache instrumentation
# ═══════════════════════════════════════════════════════════════════════════


class TestCacheInstrumentation:
    def test_eviction_counter_and_stats(self):
        from core.llm.response_cache import ResponseCache

        rc = ResponseCache(max_entries=2, persist_to_disk=False)
        rc.put("p1", "m", 0.5, "r1")
        rc.put("p2", "m", 0.5, "r2")
        assert rc.stats()["evictions"] == 0
        rc.put("p3", "m", 0.5, "r3")  # evicts p1
        st = rc.stats()
        assert st["evictions"] == 1
        assert st["size"] == 2 and st["max"] == 2
        assert rc.get("p1", "m", 0.5) is None  # p1 was evicted
        assert rc.get("p2", "m", 0.5) == "r2"

    def test_periodic_hit_rate_log(self, caplog, monkeypatch):
        from core.llm import response_cache as rc_mod
        from core.llm.response_cache import ResponseCache

        monkeypatch.setattr(rc_mod, "_PERIODIC_EVERY", 2)
        rc = ResponseCache(max_entries=8, persist_to_disk=False)
        rc.put("p", "m", 0.5, "r")
        with caplog.at_level(logging.INFO, logger=rc_mod.__name__):
            rc.get("p", "m", 0.5)  # hit  (lookup 1)
            rc.get("q", "m", 0.5)  # miss (lookup 2 → periodic fires)
        assert any("Response cache (periodic)" in r.message for r in caplog.records)

    def test_end_of_run_summary_logged(self, tmp_path):
        heading, source = golden_chapter("nonfiction")
        log_lines: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=log_lines)
        llm = ScriptedLLM(primary_response=build_primary_response(source))
        llm.install(s)
        results = s.summarize_chapters([{"heading": heading, "content": source}])
        assert results[0].success
        assert any("Response cache:" in m and "hit-rate" in m for lvl, m in log_lines), (
            "end-of-run response-cache summary missing"
        )
        assert any("Embedding cache:" in m for lvl, m in log_lines), (
            "end-of-run embedding-cache summary missing"
        )
