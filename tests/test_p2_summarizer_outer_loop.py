"""Phase 2 (P2-C1): ``Summarizer.summarize_chapters`` + book-level helpers.

The OUTER chapter loop (sequential + parallel), the per-chapter deadline
watchdog, cancel/thermal/callback plumbing, the cross-chapter rolling
context, ``build_book_summary``, ``_distill_book_context``,
``_prepare_text``/``_smart_truncate`` and the module-level
``_lp_bullet_cap_fn`` — the Phase-5 de-monolithization safety net for
everything AROUND the 1,712-line ``_summarize_inner``.

Sequential/parallel structure tests stub ``_summarize_inner`` at the
instance seam (the real inner is driven end-to-end by
``test_p2_summarizer_pipeline_phases.py``); the cross-chapter-context
test drives the REAL inner on two small chapters.

Run: ``COVERAGE_FILE=.coverage.p2c1 python3 -m pytest tests/test_p2_summarizer_outer_loop.py -v``
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_p2_summarizer_harness import (  # noqa: E402
    ScriptedLLM,
    a_chapter,
    assert_logged,
    build_primary_response,
    hermetic_env,
    make_summarizer,
)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    with hermetic_env():
        yield


def _ok_result(heading: str, exec_text: str = "A grounded executive summary."):
    """A minimal successful SummaryResult (for outer-loop structure tests)."""
    from core.summarisation.summarizer import SummaryResult

    return SummaryResult(
        chapter_heading=heading,
        executive_summary=exec_text,
        bullet_points=["One grounded bullet about the chapter."],
        thorough_summary="A thorough summary paragraph with real content.",
        success=True,
    )


def _chapters(n: int = 2) -> list[dict[str, str]]:
    return [{"heading": f"Chapter {i + 1}", "content": a_chapter(paragraphs=20)} for i in range(n)]


# ── Sequential path (real _summarize_inner) ─────────────────────────────────


class TestSequentialLoop:
    def test_two_chapters_build_rolling_book_context(self, tmp_path):
        """Sequential mode distills each chapter's exec into the rolling
        cross-chapter context (V18.1) and injects it into the NEXT call."""
        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        primary = build_primary_response(chapters[0]["content"])
        llm = ScriptedLLM(primary_response=primary)
        llm.install(s)

        seen_contexts: list[str] = []

        real_inner = s._summarize_inner

        def _spy_inner(heading, content, concepts=None, callouts=None, book_context=""):
            seen_contexts.append(book_context)
            return real_inner(
                heading, content, concepts=concepts, callouts=callouts, book_context=book_context
            )

        s._summarize_inner = _spy_inner  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert all(r.success for r in results), [r.error_msg for r in results]
        assert len(results) == 2
        # Chapter 1: no context yet; chapter 2: the distilled chapter-1 exec.
        assert seen_contexts[0] == ""
        assert "Chapter 1" in seen_contexts[1]
        assert_logged(logs, "📚 Summarising 2 chapters with 1 worker(s)")
        assert_logged(logs, "Chapter 1/2")
        assert_logged(logs, "Chapter 2/2")

    def test_empty_chapter_list_short_circuits(self, tmp_path):
        s = make_summarizer(tmp_path)
        assert s.summarize_chapters([]) == []

    def test_cancel_event_stops_between_chapters(self, tmp_path):
        chapters = _chapters(3)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        cancel = threading.Event()
        cancel.set()  # already cancelled → the FIRST chapter never runs
        results = s.summarize_chapters(chapters, cancel_event=cancel)
        assert results == []
        assert_logged(logs, "Summarisation cancelled by user — stopping")

    def test_thermal_pause_callback_invoked_per_chapter(self, tmp_path):
        chapters = _chapters(2)
        s = make_summarizer(tmp_path)
        calls = []
        s._summarize_inner = lambda heading, content, **k: _ok_result(heading)  # type: ignore[method-assign]
        s.summarize_chapters(chapters, thermal_pause_callback=lambda: calls.append(1))
        assert calls == [1, 1]

    def test_progress_callback_reports_fraction(self, tmp_path):
        chapters = _chapters(2)
        s = make_summarizer(tmp_path)
        seen = []
        s._summarize_inner = lambda heading, content, **k: _ok_result(heading)  # type: ignore[method-assign]
        s.summarize_chapters(chapters, progress_callback=lambda frac, msg: seen.append((frac, msg)))
        assert [f for f, _m in seen] == [0.5, 1.0]

    def test_inner_crash_yields_failed_result_not_dead_run(self, tmp_path):
        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)

        def _boom(heading, content, concepts=None, callouts=None, book_context=""):
            if heading == "Chapter 1":
                raise RuntimeError("inner exploded")
            return _ok_result(heading)

        s._summarize_inner = _boom  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert results[0].success is False
        assert "inner exploded" in results[0].error_msg
        assert results[1].success is True
        assert_logged(logs, "Chapter 1 failed: inner exploded")
        assert_logged(logs, "FAILED")

    def test_deadline_exceeded_logs_stall_warning(self, tmp_path):
        chapters = _chapters(1)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        # 100ns budget: any real chapter processing exceeds it deterministically.
        s.local_chapter_deadline = 1e-7
        s._summarize_inner = lambda heading, content, **k: _ok_result(heading)  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert results[0].success is True
        assert_logged(logs, "exceeded deadline")
        assert_logged(logs, "possible model stall")

    def test_failed_chapter_logs_error_line(self, tmp_path):
        from core.summarisation.summarizer import SummaryResult

        chapters = _chapters(1)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)

        def _fail(heading, content, **k):
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=False,
                error_msg="too small",
            )

        s._summarize_inner = _fail  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert results[0].success is False
        assert_logged(logs, "FAILED: too small")

    def test_chapter_done_callback_ok_and_failure(self, tmp_path):
        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        s._summarize_inner = lambda heading, content, **k: _ok_result(heading)  # type: ignore[method-assign]
        got = []

        def _cb(idx, result, chapter):
            if idx == 1:
                got.append((idx, result.chapter_heading))
            else:
                raise RuntimeError("checkpoint exploded")

        s.summarize_chapters(chapters, chapter_done_callback=_cb)
        assert got == [(1, "Chapter 1")]
        assert_logged(logs, "chapter checkpoint callback failed (chapter 2)")


# ── Parallel path ───────────────────────────────────────────────────────────


class TestParallelLoop:
    def _parallel_summarizer(self, tmp_path, logs):
        s = make_summarizer(tmp_path, log_lines=logs)
        s.max_workers = 2
        return s

    def test_parallel_two_chapters_all_succeed(self, tmp_path):
        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = self._parallel_summarizer(tmp_path, logs)
        s._summarize_inner = lambda heading, content, **k: _ok_result(heading)  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert all(r.success for r in results)
        assert [r.chapter_heading for r in results] == ["Chapter 1", "Chapter 2"]
        assert_logged(logs, "complete")

    def test_parallel_failed_chapter_logs_error(self, tmp_path):
        from core.summarisation.summarizer import SummaryResult

        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = self._parallel_summarizer(tmp_path, logs)

        def _maybe_fail(heading, content, **k):
            if heading == "Chapter 2":
                return SummaryResult(
                    chapter_heading=heading,
                    executive_summary="",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg="judge rejected",
                )
            return _ok_result(heading)

        s._summarize_inner = _maybe_fail  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert results[0].success is True
        assert results[1].success is False
        assert_logged(logs, "FAILED: judge rejected")

    def test_parallel_inner_crash_yields_failed_result(self, tmp_path):
        chapters = _chapters(2)
        logs: list[tuple[str, str]] = []
        s = self._parallel_summarizer(tmp_path, logs)

        def _boom(heading, content, concepts=None, callouts=None):
            raise RuntimeError("worker exploded")

        s._summarize_inner = _boom  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters)
        assert all(r.success is False for r in results)
        assert all("worker exploded" in r.error_msg for r in results)
        assert_logged(logs, "failed: worker exploded")

    def test_parallel_cancel_mid_run_creates_placeholders(self, tmp_path):
        """Cancel set from the first completed chapter's checkpoint callback →
        the still-QUEUED third future is cancelled and the released-but-
        unprocessed second chapter is never read back → both slots ship as
        ``[Error: No result]`` placeholders (the V18.20.2.0 fallback).

        Deterministic by construction: chapters 2 and 3 are gated on an
        Event the callback releases, so chapter 1 is the ONLY future that
        can complete before the loop breaks (yield order of already-done
        futures in ``as_completed`` is implementation-defined — this design
        leaves exactly one completable future)."""
        chapters = _chapters(3)
        logs: list[tuple[str, str]] = []
        s = self._parallel_summarizer(tmp_path, logs)
        cancel = threading.Event()
        release = threading.Event()

        def _gated(heading, content, concepts=None, callouts=None):
            if heading in ("Chapter 2", "Chapter 3"):
                release.wait(timeout=10)
            return _ok_result(heading)

        def _cb(_idx, _result, _chapter):
            cancel.set()
            release.set()  # let the gated chapters finish for shutdown

        s._summarize_inner = _gated  # type: ignore[method-assign]
        results = s.summarize_chapters(chapters, cancel_event=cancel, chapter_done_callback=_cb)
        assert len(results) == 3
        assert results[0].success is True
        assert results[0].chapter_heading == "Chapter 1"
        # The cancelled/unprocessed chapters became error placeholders.
        for r in results[1:]:
            assert r.success is False
            assert r.executive_summary == "[Error: No result]"
            assert "No result returned" in r.error_msg
        assert_logged(logs, "Summarisation cancelled by user — stopping pending chapters")


# ── build_book_summary ──────────────────────────────────────────────────────


class TestBuildBookSummary:
    def _summaries(self):
        ok = _ok_result("Good Chapter", "First executive summary text.")
        ok.bullet_points = [
            "A bullet that is definitely long enough to count.",
            "A bullet that is definitely long enough to count.",  # exact dup
            "short",  # filtered by the len > 10 rule
        ]
        ok.thorough_summary = "A thorough narrative for the details block."
        from core.summarisation.summarizer import SummaryResult

        bad = SummaryResult(
            chapter_heading="Bad Chapter",
            executive_summary="",
            bullet_points=[],
            thorough_summary="",
            success=False,
            error_msg="coverage too low",
        )
        return [ok, bad]

    def test_renders_sections_and_stats(self):
        logs: list[tuple[str, str]] = []
        s = make_summarizer(Path("/tmp"), log_lines=logs)
        stats: dict = {}
        text = s.build_book_summary(self._summaries(), "My Book", stats=stats)
        assert text.startswith("# Book Summary: My Book")
        assert "⚠️ Summary failed: coverage too low" in text
        assert "**Key takeaways:**" in text
        assert "<details><summary>Detailed summary</summary>" in text
        # stats out-param: deduped bullets + chapter count.
        assert stats["bullets"] == 1
        assert stats["chapters"] == 2

    def test_output_selection_flags_honored(self):
        ok = _ok_result("Flagged Chapter")
        ok.include_executive_summary = False
        ok.include_keypoints = False
        ok.include_thorough_summary = False
        s = make_summarizer(Path("/tmp"))
        text = s.build_book_summary([ok], "Flag Book")
        assert "**Key takeaways:**" not in text
        assert "<details>" not in text

    def test_raising_stats_object_never_breaks_the_build(self):
        class _BrokenStats(dict):
            def __setitem__(self, key, value):
                raise RuntimeError("stats exploded")

        s = make_summarizer(Path("/tmp"))
        text = s.build_book_summary(self._summaries(), "S Book", stats=_BrokenStats())
        assert "# Book Summary: S Book" in text


# ── Cross-chapter context distillation ──────────────────────────────────────


class TestDistillBookContext:
    def test_empty_exec_returns_prev_context(self):
        s = make_summarizer(Path("/tmp"))
        assert s._distill_book_context("previous", "", "Chapter 1") == "previous"
        assert s._distill_book_context("previous", None, "Chapter 1") == "previous"  # type: ignore[arg-type]

    def test_first_entry_and_long_exec_ellipsis(self):
        s = make_summarizer(Path("/tmp"))
        long_exec = " ".join(f"word{i}" for i in range(200))  # > 150 words
        ctx = s._distill_book_context("", long_exec, "Chapter 1")
        assert ctx.startswith("[Chapter 1]:")
        assert ctx.endswith("…")
        assert len(ctx.split()) <= 152

    def test_prev_context_appended_then_trimmed_at_600_words(self):
        s = make_summarizer(Path("/tmp"))
        ctx = ""
        for i in range(6):
            ctx = s._distill_book_context(
                ctx,
                f"exec summary {i} " + " ".join(f"w{i}_{j}" for j in range(100)),
                f"Chapter {i + 1}",
            )
        # The cap keeps the LAST 600 words and marks the trim.
        assert ctx.startswith("…[earlier context trimmed]…")
        assert 600 <= len(ctx.split()) <= 604


# ── _prepare_text / _smart_truncate / module cap fn ─────────────────────────


class TestPrepareText:
    def test_short_text_untouched_for_every_provider(self):
        s = make_summarizer(Path("/tmp"))
        text = a_chapter(paragraphs=3)
        for provider in (
            "ollama",
            "freellmapi",
            "claude",
            "openrouter",
            "openai",
            "openai_compatible",
        ):
            s.provider = provider
            assert s._prepare_text(text) == text

    def test_long_text_truncates(self):
        # Cloud provider budget: cloud_max_tokens - 2000 = 7000 → floor 8000.
        # a_chapter(300) ≈ 9.3k tokens > 8000 → paragraph-aware truncation.
        s = make_summarizer(Path("/tmp"))
        s.provider = "openrouter"
        s.cloud_max_tokens = 9000
        long_text = a_chapter(paragraphs=300)
        out = s._prepare_text(long_text)
        assert out != long_text
        assert len(out) < len(long_text)

    def test_cloud_token_budgets(self):
        s = make_summarizer(Path("/tmp"))
        s.provider = "openrouter"
        s.cloud_max_tokens = 9000
        # non-local: no truncation for small text
        assert s._prepare_text("small") == "small"

    def test_smart_truncate_delegate(self):
        s = make_summarizer(Path("/tmp"))
        text = "\n\n".join(f"Paragraph {i} with content words {i}." for i in range(50))
        out = s._smart_truncate(text, 100)
        assert isinstance(out, str)
        assert len(out) > 0


class TestModuleBulletCapFn:
    def test_probe_crash_returns_none(self, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        def _boom(_words):
            raise RuntimeError("probe exploded")

        monkeypatch.setattr(sz_mod, "_lp_count_source_words_mod", _boom)
        assert sz_mod._lp_bullet_cap_fn("some source text") is None

    def test_probe_success_returns_no_cap(self):
        """V0.4.23 (user directive): there is NO bullet cap — the probe
        helper returns 0 (= "no cap" for every consumer; ``None`` remains
        the crash-mode fail-open value)."""
        import core.summarisation.summarizer as sz_mod

        cap = sz_mod._lp_bullet_cap_fn(a_chapter(paragraphs=10))
        assert cap == 0, f"expected 0 (no cap, V0.4.23), got {cap}"
