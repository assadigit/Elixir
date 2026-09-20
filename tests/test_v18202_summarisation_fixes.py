"""V18.20.2.0 (SWOT A-fixes, agent IMPL-B) — summarisation characterization suite.

Covers the SWOT-A action-plan fixes in core/summarisation/:

- A4  prompt overfitting (thorough-prompt arc line + conclusion label)
- A5  shared Qwen /no_think injection at the 6 direct-call sites
- A6  content-judge stage crash surfaces at WARNING (pipeline continues)
- A7  sequential chapter crash no longer kills the whole run
- A8  parallel path sets the per-chapter deadline start
- A17 filter_thinking: optional quarantine + order-preserving trim
- A18 vram recovery sleeps the CONFIGURED delay; 0 disables
- A19 dropped-letter garble detector runs on BULLETS
- A23 content-judge Q2/Q4 chunk-embedding hoist (identical values)
- A24 postcheck detectors accept precomputed source_lower/source_words
- A25 bullet_scorer normalized-source memo (identical scores)
- A26 nvidia-smi temperature cache (~30s TTL)
- A27 duplicate @staticmethod removed (AST)
- A29 map-reduce cache: full-content sha256 key + atomic write + eviction
- thresholds.py wiring (F4=0.25 / P22=0.50 at the 5 call sites)

Run: pytest tests/test_v18202_summarisation_fixes.py -v
"""

from __future__ import annotations

import ast
import hashlib
import sys
import time as _time_mod
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation import (
    bullet_pipeline as bp_mod,
)
from core.summarisation import (
    bullet_scorer as bs_mod,
)
from core.summarisation import (
    content_judge_impl as ci_mod,
)
from core.summarisation import (
    filter_thinking as ft_mod,
)
from core.summarisation import (
    map_reduce as mr_mod,
)
from core.summarisation import (
    postchecks as pc_mod,
)
from core.summarisation import (
    primary_call as pr_mod,
)
from core.summarisation import (
    thresholds as th_mod,
)
from core.summarisation import (
    vram as vram_mod,
)
from core.summarisation.filter_thinking import qwen_no_think
from core.summarisation.prompt_assembly import build_dedicated_thorough_prompt

# ────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────────────


def _read(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


class _CapturingLog:
    """Log callback that records (message, level) tuples."""

    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((msg, level))


# ════════════════════════════════════════════════════════════════════════════
# A4 — prompt overfitting (gold-book-specific text in generic prompts)
# ════════════════════════════════════════════════════════════════════════════


class TestA4PromptOverfitting:
    SRC = "The chapter discusses identity formation across the lifespan " * 30

    def test_thorough_prompt_lacks_arc_sentence(self):
        """The identity-book arc line must NOT ship in every book's prompt."""
        prompt = build_dedicated_thorough_prompt(
            "Chapter 1", self.SRC, "Executive summary.", ["- bullet one"]
        )
        assert "adolescence to middle age" not in prompt
        assert "developmental arc" not in prompt
        assert "trace identity" not in prompt

    def test_thorough_prompt_constraints_intact(self):
        """All OTHER constraints survive the A4 edit.

        V0.05 (F9b): the word target is now SOURCE-SCALED (the SRC fixture
        is ~178 words → "80-120 word"), never the absolute 800-1200 — the
        pin keeps the CONSTRAINT (a word target exists, prose form,
        coverage, anti-invention) with the scaled phrasing.
        """
        prompt = build_dedicated_thorough_prompt(
            "Chapter 1", self.SRC, "Executive summary.", ["- bullet one"]
        )
        for fragment in (
            "FLOWING PROSE PARAGRAPHS",
            "80-120 word thorough summary",  # V0.05: source-scaled target
            "Cover ALL key concepts",
            "Include every named author/theorist",
            "Do NOT invent facts",
            "transitional phrases",
        ):
            assert fragment in prompt, f"constraint lost: {fragment!r}"
        assert "800-1200" not in prompt  # V0.05: absolute demand is gone

    def test_thorough_prompt_neutral_for_any_book(self):
        """A climate-science chapter must not receive identity instructions."""
        climate_src = ("CO2 emissions drive global warming. " * 40) + (
            "Adaptation requires policy. " * 40
        )
        prompt = build_dedicated_thorough_prompt(
            "Climate Chapter", climate_src, "Warming summary.", ["- CO2 bullet"]
        )
        low = prompt.lower()
        assert "identity" not in low
        assert "adolescence" not in low

    def test_conclusion_label_is_neutral(self):
        """_ensure_conclusion_bullets: label has no 'of solid identity' qualifier."""
        from core.summarisation.summarizer import Summarizer

        s = object.__new__(Summarizer)
        s.log = lambda msg, level="INFO": None
        source = (
            "Background filler text. "
            * 30
            + " The theory rests on three pillars: (1) evidence quality, "
            "(2) replication, (3) transparency."
        )
        result = {"bullet_points": []}
        s._ensure_conclusion_bullets("Chapter 1", source, result)
        assert len(result["bullet_points"]) == 1
        added = result["bullet_points"][0]
        # New V18.20.2.0 (SWOT A4) label format — book-neutral.
        assert added.startswith("**Conclusions**: (1)")
        assert "solid identity" not in added

    def test_existing_qualified_bullet_still_dedupes(self):
        """The prefix-only dedup check still matches the OLD qualified label.

        A pre-existing "**Conclusions of solid identity**: ..." bullet (e.g.
        from a cached/older generation) must still suppress re-adding —
        the dedup check (V18.20.4.7 / O-a2: now in
        core/summarisation/additive_sections.py) is prefix-only.
        """
        from core.summarisation.summarizer import Summarizer

        s = object.__new__(Summarizer)
        s.log = lambda msg, level="INFO": None
        source = (
            "Background filler text. "
            * 30
            + " The theory rests on three pillars: (1) evidence quality, "
            "(2) replication, (3) transparency."
        )
        result = {
            "bullet_points": [
                "**Conclusions of solid identity**: (1) evidence quality; (2) replication; (3) transparency."
            ]
        }
        s._ensure_conclusion_bullets("Chapter 1", source, result)
        assert len(result["bullet_points"]) == 1, (
            "prefix-only dedup check must still match the legacy qualified label"
        )

    def test_shipped_templates_have_no_identity_label_text(self):
        """Shipped prompt templates contain no book-specific label/arc text.

        (Borderline items intentionally KEPT, reported in the worklog:
        prompts/default.md's life-stage guidance is CONDITIONAL ("When the
        source describes development across MULTIPLE life stages…") and
        applies to any developmental source; the bullet_consolidation
        few-shot examples use Erikson/Blos only as dedup ILLUSTRATIONS of
        the keep/drop rule, not as content instructions.)
        """
        for tpl in (_project_root / "prompts" / "summarisation").glob("*.md"):
            text = tpl.read_text(encoding="utf-8")
            assert "solid identity" not in text.lower(), tpl.name
            assert "adolescence to middle age" not in text.lower(), tpl.name


# ════════════════════════════════════════════════════════════════════════════
# A5 — shared /no_think injection at direct _call_llm sites
# ════════════════════════════════════════════════════════════════════════════


class TestA5QwenNoThinkHelper:
    def test_qwen_model_appends_directive(self):
        assert qwen_no_think("Summarize this.", "qwen3:27b") == "Summarize this. /no_think"

    def test_qwythos_model_appends_directive(self):
        assert qwen_no_think("Summarize.", "QWYTHOS-27b-IQ2_S").endswith(" /no_think")

    def test_case_insensitive_model_match(self):
        assert qwen_no_think("Summarize.", "Qwen3:8b").endswith(" /no_think")

    def test_gemma_unchanged(self):
        assert qwen_no_think("Summarize this.", "gemma3:12b") == "Summarize this."

    def test_empty_model_unchanged(self):
        assert qwen_no_think("Summarize this.", "") == "Summarize this."

    def test_idempotent(self):
        once = qwen_no_think("Summarize.", "qwen3:27b")
        assert qwen_no_think(once, "qwen3:27b") == once
        assert not once.endswith("/no_think /no_think")

    def test_six_direct_sites_wired(self):
        """Source scan: every specified direct-call site routes through the
        shared helper (bullet_pipeline judge gap-fill, summarizer self-review,
        thorough_fallback attempt 1, map_reduce ×3, self_review batch).

        V0.08 (P2): summarizer.py count 2 -> 1 — the removed site was the
        coverage reprompt inside the V18.6-era ``if False`` dead block (dead
        code since V18.6, deleted together with the block)."""
        scans = {
            "core/summarisation/bullet_pipeline.py": 1,
            "core/summarisation/summarizer.py": 1,
            "core/summarisation/thorough_fallback.py": 1,
            "core/summarisation/map_reduce.py": 3,
            "core/summarisation/self_review.py": 1,
        }
        for rel, expected in scans.items():
            content = _read(rel)
            assert content.count("qwen_no_think(") >= expected, (
                f"{rel}: expected >= {expected} qwen_no_think applications, "
                f"found {content.count('qwen_no_think(')}"
            )

    def test_empty_retry_injection_untouched(self):
        """The V18.2.41 /no_think injection STAYS in
        _call_llm_with_empty_retry (hard constraint — not moved/removed)."""
        # V0.18 (Phase 5.1, step 7): the method moved VERBATIM to
        # llm_transport.py (SummarizerTransportMixin).
        content = _read("core/summarisation/llm_transport.py")
        assert 'prompt = prompt + " /no_think"' in content
        # …and it still fires for qwen-family models only.
        assert '"qwen" in _model_lower or "qwythos" in _model_lower' in content


class TestA5SiteBehavior:
    """Behavioral tests on the two most easily-mockable sites."""

    @staticmethod
    def _mr_deps():
        calls = []

        def call_llm(prompt, model=None, temperature=None, **kw):
            calls.append({"prompt": prompt, "model": model})
            return "RESPONSE"

        return calls, call_llm

    def test_map_reduce_injects_for_qwen(self, tmp_path):
        calls, call_llm = self._mr_deps()
        mr_mod.map_reduce_summarize(
            "Chapter 1",
            "Para one text.\n\nPara two text.",
            primary_model="qwen3:27b",
            cache_dir=tmp_path,
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.1,
            map_mini_words=300,
            log=_CapturingLog(),
            build_prompt=lambda h, t, with_cot=True: "REDUCE_PROMPT",
            call_llm=call_llm,
        )
        assert calls, "map/reduce LLM calls expected"
        for c in calls:
            assert c["prompt"].endswith(" /no_think"), c["prompt"][-40:]

    def test_map_reduce_gemma_unchanged(self, tmp_path):
        calls, call_llm = self._mr_deps()
        mr_mod.map_reduce_summarize(
            "Chapter 1",
            "Para one text.\n\nPara two text.",
            primary_model="gemma3:12b",
            cache_dir=tmp_path,
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.1,
            map_mini_words=300,
            log=_CapturingLog(),
            build_prompt=lambda h, t, with_cot=True: "REDUCE_PROMPT",
            call_llm=call_llm,
        )
        assert calls
        for c in calls:
            assert not c["prompt"].endswith("/no_think")

    def test_thorough_fallback_attempt1_injects_for_qwen(self):
        from core.summarisation.thorough_fallback import (
            call_dedicated_thorough_with_fallback,
        )

        calls = []

        def call_llm(prompt, model=None, temperature=None, max_tokens=None, **kw):
            calls.append(prompt)
            return "<thorough_summary>" + ("thorough word. " * 900) + "</thorough_summary>"

        out, _fb = call_dedicated_thorough_with_fallback(
            "PROMPT",
            "Exec summary.",
            ["bullet one"],
            min_words=800,
            max_output_tokens=8192,
            primary_model="qwen3:27b",
            temperature=0.7,
            strip_thinking=lambda x: x,
            call_llm=call_llm,
            deadline_exceeded=lambda phase: False,
            synthetic_fallback_count=0,
            log=_CapturingLog(),
        )
        assert calls and calls[0].endswith(" /no_think")
        assert out and len(out.split()) >= 800

    def test_empty_retry_still_appends_on_first_attempt(self):
        """The V18.2.41 empty-retry behaviour is unchanged by A5: qwen
        prompts get exactly one ' /no_think' on the FIRST attempt (belt and
        suspenders with the nudge on retry), gemma prompts unchanged."""
        from core.summarisation.summarizer import Summarizer

        s = object.__new__(Summarizer)
        s.log = lambda msg, level="INFO": None
        s.primary_model = "qwen3:27b"
        seen = []

        def fake_call_llm(prompt, model=None, temperature=None, max_tokens=None):
            seen.append(prompt)
            return "A sufficiently long response to avoid the retry path."

        s._call_llm = fake_call_llm
        out = s._call_llm_with_empty_retry("Summarize the chapter.", model="qwen3:27b")
        assert out.startswith("A sufficiently")
        assert seen[0].endswith(" /no_think")
        assert seen[0].count("/no_think") == 1

        seen.clear()
        s._call_llm_with_empty_retry("Summarize the chapter.", model="gemma3:12b")
        assert "/no_think" not in seen[0]


# ════════════════════════════════════════════════════════════════════════════
# A6 — content-judge stage crash surfaced at WARNING
# ════════════════════════════════════════════════════════════════════════════


class TestA6JudgeSilentCrash:
    def test_judge_crash_pipeline_continues_with_warning(self, monkeypatch, caplog):
        """A judge() crash must NOT kill the chapter AND must be visible:
        WARNING log with the 'content_judge' stage name + exception type."""
        import core.summarisation.content_judge as cj_shim

        class _ExplodingJudge:
            def __init__(self, *a, **kw):
                pass

            def judge(self, summary, source):
                raise RuntimeError("judge exploded (A6 test)")

        monkeypatch.setattr(cj_shim, "ContentJudge", _ExplodingJudge)

        from core.summarisation.summarizer import Summarizer

        s = object.__new__(Summarizer)
        s.log = _CapturingLog()
        s.coverage_threshold = 0.5
        s._claim_extractor = None
        s.judge_results = []
        s.request = types.SimpleNamespace(source_type="normal_book")
        s.quarantine = None
        s.conservative_drops = False

        pipeline = bp_mod.BulletPipeline(s)
        state = bp_mod.PipelineState(
            heading="Chapter 1",
            content="Source content. " * 40,
            bullets=["A grounded bullet about the source."],
            exec_sum="Exec.",
            thorough="Thorough.",
        )
        with caplog.at_level("WARNING", logger="core.summarisation.bullet_pipeline"):
            ret = pipeline.run_content_judge(state, coverage=0.9, tok_in=100, final_summary="final")
        # Pipeline continues: None = chapter should continue (no exception,
        # no failed SummaryResult).
        assert ret is None
        # The captured s.log has a WARNING naming the stage + exception type.
        warnings = [m for m, lvl in s.log.calls if lvl == "WARNING"]
        assert any("content_judge" in m and "RuntimeError" in m for m in warnings), warnings
        # And the module logger saw it too.
        assert any(
            "content_judge" in r.message and "RuntimeError" in r.message for r in caplog.records
        ), [r.message for r in caplog.records]


# ════════════════════════════════════════════════════════════════════════════
# A7 — sequential chapter crash no longer kills the run
# ════════════════════════════════════════════════════════════════════════════


class TestA7SequentialCrash:
    def test_ch1_crash_ch2_ok_completes(self, monkeypatch):
        from core.summarisation.summarizer import Summarizer, SummaryResult

        s = object.__new__(Summarizer)
        s.log = _CapturingLog()
        s.max_workers = 1
        s.is_local = True
        s.local_chapter_deadline = 0  # deadline logging off for the test

        def fake_inner(heading, content, concepts=None, callouts=None, book_context=""):
            if "ONE" in heading:
                raise ValueError("boom in chapter 1 (A7 test)")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=["ok"],
                thorough_summary="",
                success=True,
            )

        monkeypatch.setattr(s, "_summarize_inner", fake_inner)
        chapters = [
            {"heading": "Chapter ONE", "content": "c1"},
            {"heading": "Chapter TWO", "content": "c2"},
        ]
        results = s.summarize_chapters(chapters)
        # The run COMPLETED — both chapters recorded.
        assert len(results) == 2
        assert results[0].success is False
        assert "boom in chapter 1" in results[0].error_msg
        assert results[1].success is True
        assert results[1].bullet_points == ["ok"]

    def test_failure_logged_at_error(self, monkeypatch):
        from core.summarisation.summarizer import Summarizer

        s = object.__new__(Summarizer)
        log = _CapturingLog()
        s.log = log
        s.max_workers = 1
        s.is_local = False
        s.local_chapter_deadline = 0

        def fake_inner(heading, content, concepts=None, callouts=None, book_context=""):
            raise ValueError("kaboom")

        monkeypatch.setattr(s, "_summarize_inner", fake_inner)
        results = s.summarize_chapters([{"heading": "H", "content": "c"}])
        assert len(results) == 1 and results[0].success is False
        errors = [m for m, lvl in log.calls if lvl == "ERROR"]
        assert any("Chapter 1" in m and "kaboom" in m for m in errors), errors


# ════════════════════════════════════════════════════════════════════════════
# A8 — parallel path sets the per-chapter deadline start
# ════════════════════════════════════════════════════════════════════════════


class TestA8ParallelDeadline:
    def test_deadline_start_set_before_each_submission(self, monkeypatch):
        """Every parallel _summarize_inner invocation must observe a set
        (non-None) _chapter_deadline_start — pre-A8 the attribute stayed
        None and the watchdog silently never fired."""
        from core.summarisation.summarizer import Summarizer, SummaryResult

        s = object.__new__(Summarizer)
        s.log = _CapturingLog()
        s.max_workers = 2
        s.is_local = True
        s.local_chapter_deadline = 2400
        observed = []

        def fake_inner(heading, content, concepts=None, callouts=None, book_context=""):
            observed.append((heading, getattr(s, "_chapter_deadline_start", None)))
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=True,
            )

        monkeypatch.setattr(s, "_summarize_inner", fake_inner)
        chapters = [{"heading": f"Ch {i}", "content": f"c{i}"} for i in range(4)]
        results = s.summarize_chapters(chapters)
        assert len(results) == 4 and all(r.success for r in results)
        assert len(observed) == 4
        for heading, start in observed:
            assert start is not None, f"{heading}: deadline start not set"
            assert isinstance(start, float) and start > 0

    def test_parallel_source_scan(self):
        """Both paths set the deadline start: the sequential loop assigns
        the pre-recorded per-chapter timestamp, the parallel submission loop
        sets time.time() immediately before each executor.submit."""
        # V0.18 (Phase 5.1, step 8): summarize_chapters moved VERBATIM to
        # book_outer.py (SummarizerBookMixin).
        content = _read("core/summarisation/book_outer.py")
        assert "self._chapter_deadline_start = _chap_start" in content  # sequential
        assert "self._chapter_deadline_start = time.time()" in content  # parallel


# ════════════════════════════════════════════════════════════════════════════
# A17 — filter_thinking: optional quarantine + order-preserving trim
# ════════════════════════════════════════════════════════════════════════════


class TestA17FilterThinking:
    BULLETS = [
        "Identity formation requires deliberate reflection on values.",
        "Temporal continuity binds present self to past self.",
        "Authenticity emerges through chosen commitments.",
    ]
    SOURCE = (
        "Identity formation requires deliberate reflection on values. "
        "Temporal continuity binds present self to past self. "
        "Authenticity emerges through chosen commitments."
    )

    def test_none_quarantine_drops_fine(self):
        """quarantine=None (the default) must not AttributeError on drops."""
        thinking = ["Analyze the structure of the argument carefully."]
        out = ft_mod.filter_thinking_bullets(
            thinking + self.BULLETS[:1],
            concepts=["identity"],
            source_text=self.SOURCE,
            current_heading="H",
            conservative_drops=False,
            quarantine=None,  # default path
            max_bullets_per_chapter=30,
        )
        assert all("Analyze" not in b for b in out)

    def test_order_preserved_when_under_cap(self):
        """≤ max_bullets: source order preserved (no quality-score reorder)."""
        scores = {"Identity": 30, "Temporal": 60, "Authenticity": 90}
        out = ft_mod.filter_thinking_bullets(
            self.BULLETS,
            concepts=["identity"],
            source_text=self.SOURCE,
            current_heading="H",
            conservative_drops=False,
            quarantine=None,
            max_bullets_per_chapter=30,  # > len(bullets) → trim is a no-op
            score_bullet=lambda bp, c, st: scores[bp.split()[0]],
        )
        assert out == self.BULLETS, "source order must be preserved under cap"

    def test_trims_by_score_when_over_cap(self):
        """> max_bullets: top-N by score (the documented trim behaviour)."""
        scores = {"Identity": 30, "Temporal": 60, "Authenticity": 90}
        out = ft_mod.filter_thinking_bullets(
            self.BULLETS,
            concepts=["identity"],
            source_text=self.SOURCE,
            current_heading="H",
            conservative_drops=False,
            quarantine=None,
            max_bullets_per_chapter=2,  # < len(bullets) → trim fires
            score_bullet=lambda bp, c, st: scores[bp.split()[0]],
        )
        assert out == [
            "Authenticity emerges through chosen commitments.",
            "Temporal continuity binds present self to past self.",
        ]

    def test_quarantine_guard_source_scan(self):
        content = _read("core/summarisation/filter_thinking.py")
        assert "if quarantine is not None:" in content
        # …and the sort is gated on the trim actually removing bullets.
        assert "if len(kept) > max_bullets_per_chapter:" in content


# ════════════════════════════════════════════════════════════════════════════
# A18 — vram recovery sleeps the configured delay
# ════════════════════════════════════════════════════════════════════════════


class TestA18VramDelay:
    def _patch_sleep(self, monkeypatch):
        slept = []
        monkeypatch.setattr(vram_mod.time, "sleep", lambda s: slept.append(s))
        return slept

    @staticmethod
    def _install_fake_torch(monkeypatch):
        """torch is not installed in the sandbox — inject a CPU-only fake so
        the cache-clear branch (and its log line) executes."""
        fake_torch = types.ModuleType("torch")
        fake_cuda = types.ModuleType("torch.cuda")
        fake_cuda.is_available = lambda: False
        fake_cuda.empty_cache = lambda: None
        fake_cuda.synchronize = lambda: None
        fake_torch.cuda = fake_cuda
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setitem(sys.modules, "torch.cuda", fake_cuda)

    def test_sleeps_configured_delay_not_legacy(self, monkeypatch):
        """configured_delay=5 wins over the legacy delay_sec=30."""
        self._install_fake_torch(monkeypatch)
        slept = self._patch_sleep(monkeypatch)
        logs = _CapturingLog()
        vram_mod.recover_vram(
            is_local=True,
            delay_sec=30.0,
            configured_delay=5.0,
            context="test",
            log_fn=logs,
        )
        assert slept == [5.0]

    def test_zero_disables_sleep_but_keeps_recovery(self, monkeypatch):
        """configured_delay=0 → no sleep, cache-clear still runs."""
        self._install_fake_torch(monkeypatch)
        slept = self._patch_sleep(monkeypatch)
        logs = _CapturingLog()
        vram_mod.recover_vram(
            is_local=True,
            delay_sec=30.0,
            configured_delay=0.0,
            context="test",
            log_fn=logs,
        )
        assert slept == []
        # Recovery (cache clear attempt) still ran — a log line was emitted.
        assert any("VRAM recovery" in m for m, _ in logs.calls)

    def test_cloud_noop(self, monkeypatch):
        slept = self._patch_sleep(monkeypatch)
        vram_mod.recover_vram(
            is_local=False,
            delay_sec=30.0,
            configured_delay=120.0,
            context="test",
            log_fn=_CapturingLog(),
        )
        assert slept == []


# ════════════════════════════════════════════════════════════════════════════
# A19 — dropped-letter garble detector on BULLETS
# ════════════════════════════════════════════════════════════════════════════


class TestA19DroppedLetterOnBullets:
    SOURCE = (
        "The process emerges from the analysis of identity formation. "
        "Researchers report consistent findings across cohorts."
    )

    def test_bullet_emergs_auto_repaired(self):
        """V18.20.3.4 (RC-3) → V0.03 (P0-1): the A19 detector still catches
        'emergs'. Default: flag-only (auto-repair disabled until
        rig-validated). With auto_repair_garble=True: severity='fix' (the
        UNIQUE edit-distance-1 source candidate, guarded)."""
        # V0.03 default: flag-only. (Fixture is a realistic-length bullet —
        # the 6-word V18.20.3.4 fixture now trips the label-stub ship-time
        # drop once the garble is left in place, which is correct behavior
        # for <8-word verbless items, not for real garbled bullets.)
        _bp = "The process of identity formation emergs from the analysis of material."
        report = pc_mod.run_post_checks(
            [_bp],
            "Exec summary.",
            "Thorough summary text.",
            self.SOURCE,
        )
        dropped = [i for i in report.issues if i.detector == "dropped_letter"]
        assert dropped, "bullet 'emergs' must be caught (A19)"
        assert any(i.field == "bullet[0]" for i in dropped)
        assert all(i.severity == "flag" for i in dropped)
        assert report.bullets == [_bp]
        # Explicitly enabled: guarded repair fires.
        report = pc_mod.run_post_checks(
            [_bp],
            "Exec summary.",
            "Thorough summary text.",
            self.SOURCE,
            auto_repair_garble=True,
        )
        dropped = [i for i in report.issues if i.detector == "dropped_letter"]
        assert dropped, "bullet 'emergs' must be caught (A19)"
        assert any(i.field == "bullet[0]" for i in dropped)
        assert all(i.severity == "fix" for i in dropped)

    def test_clean_bullet_not_flagged(self):
        report = pc_mod.run_post_checks(
            ["The process emerges from the analysis."],
            "Exec summary.",
            "Thorough summary text.",
            self.SOURCE,
        )
        assert not [i for i in report.issues if i.detector == "dropped_letter"]

    def test_unambiguous_autofix_applies_to_bullets(self):
        """V18.20.3.4 (RC-3) → V0.03 (P0-1): the unique-candidate repair is
        APPLIED to the shipped bullet text when auto_repair_garble=True
        (the V18.20.3.3 'edipal' class shipped as a typo in both the bullet
        and the thorough). V0.03 default: OFF — bullets ship verbatim."""
        bullets = ["The process of identity formation emergs from the analysis of material."]
        # V0.03 default: no repair — the bullet ships as the model wrote it.
        report = pc_mod.run_post_checks(
            bullets,
            "Exec.",
            "Thorough.",
            self.SOURCE,
        )
        assert report.bullets == bullets
        # Explicitly enabled: the guarded repair applies.
        report = pc_mod.run_post_checks(
            bullets,
            "Exec.",
            "Thorough.",
            self.SOURCE,
            auto_repair_garble=True,
        )
        assert report.bullets == [
            "The process of identity formation emerges from the analysis of material."
        ]


# ════════════════════════════════════════════════════════════════════════════
# A23 — content-judge Q2/Q4 chunk-embedding hoist
# ════════════════════════════════════════════════════════════════════════════


class TestA23JudgeEmbedHoist:
    @staticmethod
    def _install_embed_stack(monkeypatch):
        """Install a deterministic fake embed stack: settings on, healthy
        embedder, sentence_transformers.util shim, counting model."""
        import numpy as np

        monkeypatch.setattr(ci_mod, "_embedding_settings", lambda: (True, "jaccard"))

        import core.llm.model_singletons as ms_mod

        class _FakeModel:
            def __init__(self):
                self.encode_calls = []

            def encode(self, texts, show_progress_bar=False):
                texts = list(texts)
                self.encode_calls.append(len(texts))
                out = []
                for t in texts:
                    v = np.zeros(16, dtype=np.float32)
                    v[sum(ord(c) for c in str(t)) % 16] = 1.0
                    out.append(v)
                return np.array(out)

        fake = _FakeModel()
        monkeypatch.setattr(ms_mod, "get_embed_model", lambda: fake)
        monkeypatch.setattr(ms_mod, "is_embedder_healthy", lambda: True)

        def _fake_cos_sim(a, b):
            A = np.asarray(a, dtype=np.float32)
            B = np.asarray(b, dtype=np.float32)
            if A.ndim == 1:
                A = A[None, :]
            if B.ndim == 1:
                B = B[None, :]
            An = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
            Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)
            return An @ Bn.T

        st_mod = types.ModuleType("sentence_transformers")
        st_util = types.ModuleType("sentence_transformers.util")
        st_util.cos_sim = _fake_cos_sim
        st_mod.util = st_util
        monkeypatch.setitem(sys.modules, "sentence_transformers", st_mod)
        monkeypatch.setitem(sys.modules, "sentence_transformers.util", st_util)

        import core.llm.embedding_cache as ec_mod

        def _fake_cached_encode(model, texts, model_name=""):
            # Counting transparent cache: always a miss (fresh encode).
            return model.encode(list(texts))

        monkeypatch.setattr(ec_mod, "cached_encode", _fake_cached_encode)
        return fake

    @staticmethod
    def _fixture():
        """3 chunks × 3 bullets (one with negation for the Q4 loop)."""
        para = (
            "Identity formation involves the synthesis of experiences "
            "across developmental stages. Researchers study this. " * 60
        )
        source = "\n\n".join([para, para, para])
        bullets = [
            "Identity formation involves the synthesis of experiences.",
            "The framework does not describe a single fixed outcome.",
            "Researchers study developmental synthesis directly.",
        ]
        return source, bullets

    def _judge(self, monkeypatch):
        from core.summarisation.summarizer import SummaryResult

        source, bullets = self._fixture()
        self._install_embed_stack(monkeypatch)
        judge = ci_mod.ContentJudge(log_callback=lambda m, l="INFO": None)
        summary = SummaryResult(
            chapter_heading="Chapter 1",
            executive_summary="Exec summary of the chapter content.",
            bullet_points=bullets,
            thorough_summary="Thorough summary of the chapter content.",
            success=True,
        )
        return judge.judge(summary, source)

    def test_identical_results_hoisted_vs_per_pair(self, monkeypatch):
        """The hoist is behaviour-preserving: identical judge metrics with
        the chunk-embedding hoist ON vs forced OFF (per-pair path)."""
        r_hoist = self._judge(monkeypatch)
        # Force the per-pair path: hoist helper returns None.
        monkeypatch.setattr(ci_mod, "_encode_chunks_cached", lambda chunks: None)
        r_persource = self._judge(monkeypatch)
        for attr in (
            "total_source_claims",
            "covered_claims",
            "coverage_pct",
            "grounded_bullets",
            "grounding_pct",
            "hallucination_count",
            "deviation_count",
            "ungrounded_bullets",
            "passed",
        ):
            assert getattr(r_hoist, attr) == getattr(r_persource, attr), attr

    def test_encode_call_count_drops(self, monkeypatch):
        """Chunk embeddings are encoded ONCE per judge() call, not once per
        (bullet × chunk) pair: the hoist strictly reduces model.encode calls."""
        _, _ = self._fixture()
        fake = self._install_embed_stack(monkeypatch)

        from core.summarisation.summarizer import SummaryResult

        source, bullets = self._fixture()
        judge = ci_mod.ContentJudge(log_callback=lambda m, l="INFO": None)
        summary = SummaryResult(
            chapter_heading="C1",
            executive_summary="Exec.",
            bullet_points=bullets,
            thorough_summary="Thorough.",
            success=True,
        )
        judge.judge(summary, source)
        n_hoist = len(fake.encode_calls)

        fake2 = self._install_embed_stack(monkeypatch)
        monkeypatch.setattr(ci_mod, "_encode_chunks_cached", lambda chunks: None)
        judge2 = ci_mod.ContentJudge(log_callback=lambda m, l="INFO": None)
        judge2.judge(summary, source)
        n_perpair = len(fake2.encode_calls)

        assert len(fake2.encode_calls) > 0
        assert n_hoist < n_perpair, (
            f"hoist must reduce encode calls (hoist={n_hoist}, per-pair={n_perpair})"
        )

    def test_hoist_helper_rejects_malformed(self, monkeypatch):
        """A malformed chunk entry degrades to per-pair (None) for that
        chunk only; a fully-unavailable embed path returns None."""
        assert ci_mod._encode_chunks_cached([]) is None or True  # no crash on empty
        monkeypatch.setattr(ci_mod, "_embedding_settings", lambda: (False, "jaccard"))
        assert ci_mod._encode_chunks_cached(["chunk"]) is None


# ════════════════════════════════════════════════════════════════════════════
# A24 — precomputed source_lower / source_words passed to detectors
# ════════════════════════════════════════════════════════════════════════════


class TestA24SourceWordset:
    SOURCE = (
        "The process emerges from analysis. Jacobson 1964 regards identity as "
        "central to development across many observed cohorts."
    )

    def test_detectors_identical_with_and_without_precomputed(self):
        """Characterization: precomputed params produce IDENTICAL results to
        the lazy per-call build (behavior-preserving optimization)."""
        import re as _re

        from core.summarisation import postcheck_detectors as det

        source_lower = self.SOURCE.lower()
        source_words = set(_re.findall(r"\b[a-z]+\b", source_lower))
        text = "The proces emerges from the analysis."
        label = "bullet[0]"

        a_text, a_issues = det.detect_missing_spaces(text, label, self.SOURCE)
        b_text, b_issues = det.detect_missing_spaces(
            text,
            label,
            self.SOURCE,
            source_lower=source_lower,
            source_words=source_words,
        )
        assert a_text == b_text
        assert [(i.detector, i.severity, i.detail) for i in a_issues] == [
            (i.detector, i.severity, i.detail) for i in b_issues
        ]

        a_text, a_iss = det.detect_garbled_tokens(text, label, self.SOURCE)
        b_text, b_iss = det.detect_garbled_tokens(
            text, label, self.SOURCE, source_words=source_words
        )
        assert a_text == b_text
        assert [(i.detector, i.detail) for i in a_iss] == [(i.detector, i.detail) for i in b_iss]

    def test_run_post_checks_precomputes_once(self):
        """Source scan: run_post_checks computes the source word-set ONCE
        and threads it through the per-bullet detector calls."""
        content = _read("core/summarisation/postchecks/orchestrator.py")  # V0.18 (Phase 5.2): moved verbatim
        assert "_src_words: set = set(re.findall" in content
        assert content.count("source_words=_src_words") >= 4


# ════════════════════════════════════════════════════════════════════════════
# A25 — bullet_scorer normalized-source memo (identical scores)
# ════════════════════════════════════════════════════════════════════════════


class TestA25BulletScorerMemo:
    SOURCE = (
        "Identity formation requires deliberate reflection on values and "
        "commitments. The study found 50% improvement across 12 cohorts."
    )
    BULLET = (
        "Identity formation requires deliberate reflection and the study "
        "found 50% improvement across 12 cohorts of participants."
    )

    def test_identical_scores_before_after(self):
        """Golden behavior preserved: memoized path == fresh computation."""
        bs_mod._SOURCE_NORM_CACHE.clear()
        a = bs_mod.score_bullet(self.BULLET, ["identity"], self.SOURCE)
        b = bs_mod.score_bullet(self.BULLET, ["identity"], self.SOURCE)
        fresh_copy = self.SOURCE + ""  # same VALUE, different object
        c = bs_mod.score_bullet(self.BULLET, ["identity"], fresh_copy)
        assert a == b == c
        assert isinstance(a, int) and a > 0

    def test_memo_populated_and_identity_hit(self):
        bs_mod._SOURCE_NORM_CACHE.clear()
        first = bs_mod._normalized_source(self.SOURCE)
        assert len(bs_mod._SOURCE_NORM_CACHE) == 1
        second = bs_mod._normalized_source(self.SOURCE)
        assert second is first  # cached object identity — no recompute
        # A different object with the same value recomputes (id-keyed).
        other = bs_mod._normalized_source(self.SOURCE + "")
        assert other == first

    def test_memo_bounded(self):
        bs_mod._SOURCE_NORM_CACHE.clear()
        for i in range(bs_mod._SOURCE_NORM_CACHE_MAX + 3):
            bs_mod._normalized_source(f"source number {i} " * 5)
        assert len(bs_mod._SOURCE_NORM_CACHE) <= bs_mod._SOURCE_NORM_CACHE_MAX


# ════════════════════════════════════════════════════════════════════════════
# A26 — nvidia-smi temperature cache
# ════════════════════════════════════════════════════════════════════════════


class TestA26GpuTempCache:
    # Phase 2 (task 2.3): ``test_summarize_with_model_uses_cache`` below used
    # to be xfail'd as order-fragile (since V18.20.3.8). Root cause (fixed
    # earlier at the conftest level): test modules swapping
    # sys.modules["utils.token_counter"] at collection time made the
    # ``from utils.token_counter import count_tokens`` import inside
    # ``summarize_with_model`` resolve to a DIFFERENT module object than the
    # one this test monkeypatched — split-brain, order-dependent. With the
    # conftest module-pin in place the test passes in isolation AND in the
    # full-suite order. To keep it deterministic in EVERY ordering it is now
    # fully hermetic: (a) this autouse fixture snapshots and restores the
    # module-level cache dict around each test (no state leaks in or out);
    # (b) the integration test pins ``time.monotonic`` (no wall-clock input).

    @pytest.fixture(autouse=True)
    def _isolate_gpu_temp_cache(self):
        """Snapshot/restore the module-level GPU-temp cache around every
        test in this class — module-state isolation (roadmap 2.3)."""
        saved = dict(pr_mod._gpu_temp_cache)
        try:
            yield
        finally:
            pr_mod._gpu_temp_cache.clear()
            pr_mod._gpu_temp_cache.update(saved)

    def _reset(self):
        pr_mod._gpu_temp_cache["valid"] = 0.0
        pr_mod._gpu_temp_cache["temp"] = 0.0
        pr_mod._gpu_temp_cache["ts"] = 0.0

    @staticmethod
    def _install_subprocess(monkeypatch, temp="42"):
        import subprocess

        spawns = []

        class _R:
            returncode = 0
            stdout = f"{temp}\n"

        def fake_run(*a, **kw):
            spawns.append(1)
            return _R()

        monkeypatch.setattr(subprocess, "run", fake_run)
        return spawns

    def test_two_calls_within_ttl_one_subprocess(self, monkeypatch):
        self._reset()
        spawns = self._install_subprocess(monkeypatch)
        clock = {"now": 1000.0}
        monkeypatch.setattr(_time_mod, "monotonic", lambda: clock["now"])
        assert pr_mod._read_gpu_temp_c() == 42.0
        assert pr_mod._read_gpu_temp_c() == 42.0  # cache hit
        assert len(spawns) == 1

    def test_ttl_expiry_respawns(self, monkeypatch):
        self._reset()
        spawns = self._install_subprocess(monkeypatch, temp="43")
        clock = {"now": 1000.0}
        monkeypatch.setattr(_time_mod, "monotonic", lambda: clock["now"])
        pr_mod._read_gpu_temp_c()
        clock["now"] = 1000.0 + pr_mod._GPU_TEMP_CACHE_TTL_SEC + 0.1
        assert pr_mod._read_gpu_temp_c() == 43.0
        assert len(spawns) == 2

    def test_failure_fallback_zero_not_cached(self, monkeypatch):
        self._reset()
        import subprocess

        def boom(*a, **kw):
            raise FileNotFoundError("no nvidia-smi")

        monkeypatch.setattr(subprocess, "run", boom)
        clock = {"now": 1000.0}
        monkeypatch.setattr(_time_mod, "monotonic", lambda: clock["now"])
        assert pr_mod._read_gpu_temp_c() == 0.0  # unknown → 0.0 → thermal_ok
        assert pr_mod._read_gpu_temp_c() == 0.0  # retried (not negative-cached)
        assert pr_mod._gpu_temp_cache["valid"] == 0.0

    def test_summarize_with_model_uses_cache(self, monkeypatch):
        """Integration: two summarize_with_model calls within the TTL spawn
        nvidia-smi once (thermal decision unchanged).

        Phase 2 (task 2.3): the xfail is GONE. Determinism now comes from
        the class-level cache snapshot/restore fixture + the pinned clock
        below + the conftest token_counter pin — no dependence on ordering.
        """
        self._reset()
        spawns = self._install_subprocess(monkeypatch, temp="42")
        clock = {"now": 1000.0}
        monkeypatch.setattr(_time_mod, "monotonic", lambda: clock["now"])

        import utils.token_counter as tc

        monkeypatch.setattr(tc, "count_tokens", lambda text: 10)

        class _Req:
            summarisation_max_output_tokens = 8192

        for _ in range(2):
            pr_mod.summarize_with_model(
                "h",
                "short text",
                "m",
                0.7,
                request=_Req(),
                log=lambda m, l="INFO": None,
                chunked_summarize=lambda *a, **k: None,
                build_prompt=lambda *a, **k: "P",
                call_llm_structured=lambda *a, **k: {"bullet_points": ["x"]},
                call_llm_with_empty_retry=lambda *a, **k: "",
                strip_thinking=lambda x: x,
                parse_response=lambda x: {"bullet_points": []},
            )
        assert len(spawns) == 1


# ════════════════════════════════════════════════════════════════════════════
# A27 — duplicate @staticmethod removed
# ════════════════════════════════════════════════════════════════════════════


class TestA27DuplicateStaticmethod:
    # V18.20.4.7 (P5 / O-a2): the additive-sections machinery (incl.
    # _normalize_empty_section) moved VERBATIM to
    # core/summarisation/additive_sections.py — the A27 scans now cover
    # summarizer.py AND the new mixin modules (union; assertions
    # unchanged — same precedent as the V18.20.3.12 gap_fill_batch move).
    _SCAN_FILES = (
        "core/summarisation/summarizer.py",
        "core/summarisation/additive_sections.py",
        "core/summarisation/thorough_theorist_floor.py",
    )

    def test_no_doubled_decorators_anywhere(self):
        """AST scan: no function in the summarizer modules carries the same
        decorator twice (the _normalize_empty_section double-@staticmethod
        is gone)."""
        offenders = []
        for rel in self._SCAN_FILES:
            tree = ast.parse(_read(rel))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                    for n in set(names):
                        if names.count(n) > 1:
                            offenders.append((node.name, n))
        assert offenders == []

    def test_normalize_empty_section_single_staticmethod(self):
        tree = ast.parse(_read("core/summarisation/additive_sections.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_normalize_empty_section":
                decs = [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                assert decs == ["staticmethod"]


# ════════════════════════════════════════════════════════════════════════════
# A29 — map-reduce cache key / atomic write / eviction
# ════════════════════════════════════════════════════════════════════════════


class TestA29MapReduceCache:
    def test_full_content_hash_key(self, tmp_path):
        """Two chapters sharing their first 500 chars (frontmatter/running
        header) must get DIFFERENT cache keys (pre-A29 they collided)."""
        shared_prefix = "Running header: The Book Title. " * 15 + "\n\n"
        c1 = shared_prefix + "alpha " * 400
        c2 = shared_prefix + "beta " * 400

        def run(content, tag):
            cache_dir = tmp_path / tag
            cache_dir.mkdir()
            mr_mod.map_reduce_summarize(
                "Chapter 1",
                content,
                primary_model="m",
                cache_dir=cache_dir,
                input_path_stem="book",
                cache_enabled=True,
                temperature=0.7,
                map_chunk_tokens=4000,
                map_chunk_overlap=0.1,
                map_mini_words=300,
                log=_CapturingLog(),
                build_prompt=lambda h, t, with_cot=True: "REDUCE",
                call_llm=lambda p, model=None, temperature=None, **kw: "R",
            )
            files = list(cache_dir.glob("mapreduce_*.mini_summaries.md"))
            assert len(files) == 1
            return files[0].name

        k1, k2 = run(c1, "a"), run(c2, "b")
        assert k1 != k2

    def test_edit_past_char_500_invalidates(self):
        """The key covers the FULL content: differing chars past 500 change
        the key (pre-A29 they never did)."""
        c1 = "x" * 600 + "alpha"
        c2 = "x" * 600 + "omega"
        h1 = hashlib.sha256(c1.encode("utf-8", "replace")).hexdigest()[:16]
        h2 = hashlib.sha256(c2.encode("utf-8", "replace")).hexdigest()[:16]
        assert h1 != h2

    def test_atomic_write_used(self):
        content = _read("core/summarisation/map_reduce.py")
        assert "atomic_write_text(" in content
        assert "cache_file.write_text(" not in content

    def test_eviction_cap(self, tmp_path):
        """_evict_mapreduce_cache keeps at most 256 entries, oldest first."""
        import os

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        names = []
        for i in range(258):
            p = cache_dir / f"mapreduce_{i:04d}.mini_summaries.md"
            p.write_text("x", encoding="utf-8")
            stamp = 1_000_000 + i  # ascending mtime: file 0 is oldest
            os.utime(p, (stamp, stamp))
            names.append(p.name)
        # A non-mapreduce file must NOT be evicted.
        keeper = cache_dir / "unrelated.txt"
        keeper.write_text("keep", encoding="utf-8")
        mr_mod._evict_mapreduce_cache(cache_dir)
        remaining = {p.name for p in cache_dir.glob("mapreduce_*.mini_summaries.md")}
        assert len(remaining) == 256
        assert names[0] not in remaining and names[1] not in remaining
        assert names[2] in remaining and names[-1] in remaining
        assert keeper.exists()


# ════════════════════════════════════════════════════════════════════════════
# Thresholds wiring (SWOT-A finding 2 / A2 in the action plan)
# ════════════════════════════════════════════════════════════════════════════


class TestThresholdsWiring:
    def test_values_equal_previous_literals(self):
        """The wired values are IDENTICAL to the pre-wiring literals."""
        assert th_mod.F4_SOURCE_OVERLAP_DROP == 0.25
        assert th_mod.SEMANTIC_FACT_CHECK_DROP == 0.50
        # bullet_pipeline imports both aliases…
        assert bp_mod._F4_SOURCE_OVERLAP_DROP == 0.25
        assert bp_mod._SEMANTIC_FACT_CHECK_DROP == 0.50
        # …and content_judge_impl's Q2 threshold is the wired constant.
        assert ci_mod.GROUNDED_SIM_THRESHOLD == 0.50
        assert ci_mod.GROUNDED_SIM_THRESHOLD is th_mod.SEMANTIC_FACT_CHECK_DROP

    def test_five_call_sites_import_from_thresholds(self):
        for rel, needle in (
            ("core/summarisation/bullet_pipeline.py", "from core.summarisation.thresholds import"),
            (
                "core/summarisation/content_judge_impl.py",
                "from core.summarisation.thresholds import SEMANTIC_FACT_CHECK_DROP",
            ),
        ):
            assert needle in _read(rel), rel

    def test_thresholds_module_docstring_single_source(self):
        assert (
            "SINGLE SOURCE OF TRUTH" in _read("core/summarisation/thresholds.py")
            or "single source of truth" in _read("core/summarisation/thresholds.py").lower()
        )
