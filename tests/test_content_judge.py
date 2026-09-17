"""V10.30.0 (Sprint 3.2): Unit tests for the Content Judge (grounding).

Tests the ``ContentJudge`` class (``core/summarisation/content_judge.py``)
which was previously at 0 unit tests despite being the final pre-output
validation gate.  Covers:

  - JudgeResult dataclass construction + format_report
  - _extract_key_claims deterministic extraction (numbers, causal,
    definition, comparison, named-entity patterns)
  - _split_into_sentences + _chunk_text
  - judge() auto-passes short source (<200 chars)
  - judge() auto-passes empty summary
  - judge() detects ungrounded bullets (Jaccard fallback when
    sentence-transformers is unavailable)
  - llm_judge_grounding() parses GROUNDED/NOT_GROUNDED verdicts
  - build_gap_fill_prompt() produces a well-formed prompt

The ContentJudge module imports ``core.models.SummaryResult`` (pure
dataclass, no heavy deps) and uses a Jaccard fallback for semantic
similarity when sentence-transformers isn't installed — so the tests run
in the sandbox without stubbing.

Run: ``pytest tests/test_content_judge.py -v``
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load content_judge.py directly to bypass core.summarisation.__init__
# (which imports Summarizer → tiktoken).  content_judge only needs
# core.models.SummaryResult, which is a pure dataclass.
# Pre-load core.models so the `from core.models import SummaryResult`
# inside content_judge resolves.
import core.models  # noqa: F401  (ensures core.models is importable)

_spec = importlib.util.spec_from_file_location(
    "core.summarisation.content_judge",
    _project_root / "core" / "summarisation" / "content_judge.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

ContentJudge = _mod.ContentJudge
JudgeResult = _mod.JudgeResult
_extract_key_claims = _mod._extract_key_claims
_split_into_sentences = _mod._split_into_sentences
_chunk_text = _mod._chunk_text

from core.models import SummaryResult

# ── 1. JudgeResult dataclass ────────────────────────────────────────────────


class TestJudgeResult:
    def test_default_construction(self):
        """JudgeResult constructs with all defaults."""
        r = JudgeResult(chapter_heading="Ch.1")
        assert r.chapter_heading == "Ch.1"
        assert r.total_source_claims == 0
        assert r.coverage_pct == 0.0
        assert r.ungrounded_bullets == []
        assert r.passed is False

    def test_format_report_pass(self):
        """format_report shows ✅ PASS when passed=True."""
        r = JudgeResult(
            chapter_heading="Ch.1",
            total_source_claims=10, covered_claims=8,
            coverage_pct=0.80,
            total_bullets=5, grounded_bullets=5,
            grounding_pct=1.0,
            passed=True,
        )
        report = r.format_report()
        assert "80%" in report
        assert "5/5" in report
        assert "✅ PASS" in report

    def test_format_report_fail(self):
        """format_report shows ❌ FAIL when passed=False."""
        r = JudgeResult(chapter_heading="Ch.1", passed=False)
        assert "❌ FAIL" in r.format_report()

    def test_format_report_layer8(self):
        """format_report includes Layer 8 stats when available."""
        r = JudgeResult(
            chapter_heading="Ch.1",
            grounding_layer8_available=True,
            strong_grounded_bullets=3,
            weak_grounded_bullets=1,
            ungrounded_strong=["bad bullet"],
            passed=True,
        )
        report = r.format_report()
        assert "L8=3S/1W/1U" in report


# ── 2. _extract_key_claims (deterministic) ──────────────────────────────────


class TestExtractKeyClaims:
    def test_extracts_numeric_claims(self):
        """Sentences with numbers are extracted as claims."""
        text = (
            "The study found that 42% of participants improved. "
            "This is a plain sentence with no claim markers."
        )
        claims = _extract_key_claims(text)
        assert len(claims) == 1
        assert "42%" in claims[0]

    def test_extracts_causal_claims(self):
        """Sentences with causal language are extracted."""
        text = (
            "Therefore the mechanism activates. "
            "The weather is nice today."
        )
        claims = _extract_key_claims(text)
        assert any("Therefore" in c for c in claims)

    def test_extracts_definition_claims(self):
        """Sentences with definition language are extracted."""
        text = (
            "Photosynthesis is defined as the process by which plants convert light. "
            "It was a sunny day."
        )
        claims = _extract_key_claims(text)
        assert any("is defined as" in c for c in claims)

    def test_skips_figure_table_captions(self):
        """Figure/Table captions are skipped."""
        text = (
            "Figure 1 shows the results. "
            "The results demonstrate a 30% improvement."
        )
        claims = _extract_key_claims(text)
        # "Figure 1 shows the results." should be skipped, the second kept
        assert not any("Figure" in c for c in claims)
        assert any("30%" in c for c in claims)

    def test_caps_at_8_claims_per_chunk(self):
        """Claims are capped at 8 per chunk (performance guard)."""
        sentences = [f"The result shows {i}% improvement." for i in range(20)]
        text = " ".join(sentences)
        claims = _extract_key_claims(text)
        assert len(claims) <= 8

    def test_short_sentences_skipped(self):
        """Sentences <30 chars are skipped (not meaningful claims)."""
        text = "Ok. Hi. The study found 50% improvement."
        claims = _extract_key_claims(text)
        assert all(len(c) > 30 for c in claims)


# ── 3. _chunk_text + _split_into_sentences ─────────────────────────────────


class TestChunking:
    def test_short_text_returns_single_chunk(self):
        """Text ≤ chunk_chars returns [text]."""
        assert _chunk_text("short text") == ["short text"]

    def test_long_text_splits_on_paragraphs(self):
        """Long text splits on paragraph boundaries."""
        para = "A" * 4000 + "."
        text = "\n\n".join([para, para, para])
        chunks = _chunk_text(text, chunk_chars=8000)
        assert len(chunks) >= 2

    def test_split_into_sentences(self):
        """_split_into_sentences splits on . ! ? + capital."""
        # Sentences must be >30 chars to survive the length filter.
        text = (
            "This is the first sentence with enough words. "
            "Here is the second sentence with enough words! "
            "And the third sentence also has enough words? "
            "The fourth sentence rounds it out."
        )
        sents = _split_into_sentences(text)
        assert len(sents) >= 3

    def test_split_skips_short_sentences(self):
        """Sentences <30 chars are filtered out."""
        text = "Hi. Ok. This is a longer sentence with enough words to pass."
        sents = _split_into_sentences(text)
        assert all(len(s) > 30 for s in sents)


# ── 4. judge() — the main entry point ───────────────────────────────────────


class TestJudge:
    @pytest.fixture
    def judge(self):
        return ContentJudge(log_callback=lambda msg, level="INFO": None)

    def test_short_source_auto_pass(self, judge: ContentJudge):
        """Source <200 chars → auto-pass (can't judge reliably)."""
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="A summary.",
            bullet_points=["A bullet."],
            thorough_summary="A thorough summary.",
        )
        result = judge.judge(summary, "short source")
        assert result.passed is True
        assert "auto-pass" in result.summary.lower()

    def test_empty_summary_fails(self, judge: ContentJudge):
        """Empty summary → FAIL."""
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="",
            bullet_points=[],
            thorough_summary="",
        )
        long_source = "The study found that 50% of users improved significantly. " * 10
        result = judge.judge(summary, long_source)
        assert result.passed is False
        assert "empty" in result.summary.lower()

    def test_no_source_claims_auto_passes_coverage(self, judge: ContentJudge):
        """When the source has no extractable claims, coverage auto-passes."""
        # Source with no numbers, no causal language, no definitions, no
        # named entities — just plain sentences >30 chars.
        source = (
            "The weather was pleasant and the birds were singing in the trees. "
            "People walked along the path enjoying the afternoon sunshine. "
        ) * 10
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="A summary of the pleasant weather.",
            bullet_points=["The weather was pleasant."],
            thorough_summary="A thorough summary of the day.",
        )
        result = judge.judge(summary, source)
        # No claims → coverage auto-set to 1.0
        assert result.coverage_pct == 1.0
        assert result.total_source_claims == 0

    def test_grounding_detects_ungrounded_bullet(self, judge: ContentJudge):
        """A bullet with no word overlap with the source is flagged ungrounded."""
        source = (
            "The study found that 50% of participants improved significantly. "
            "Researchers demonstrated that the treatment causes recovery. "
        ) * 10
        summary = SummaryResult(
            chapter_heading="Ch.1",
            executive_summary="The study shows improvement.",
            bullet_points=[
                "The study found 50% improvement.",  # grounded (word overlap)
                "Quantum entanglement transcends spacetime dimensions.",  # ungrounded
            ],
            thorough_summary="The treatment causes recovery in participants.",
        )
        result = judge.judge(summary, source)
        assert result.total_bullets == 2
        # The ungrounded bullet should be in the ungrounded list
        # (Jaccard similarity will be ~0 for "Quantum entanglement...")
        assert any("Quantum" in b for b in result.ungrounded_bullets)


# ── 5. llm_judge_grounding ──────────────────────────────────────────────────


class TestLlmJudgeGrounding:
    @pytest.fixture
    def judge(self):
        return ContentJudge(log_callback=lambda msg, level="INFO": None)

    def test_parses_grounded_verdicts(self, judge: ContentJudge):
        """llm_judge_grounding parses 'GROUNDED: N' / 'NOT_GROUNDED: N' lines."""
        bullets = ["bullet one", "bullet two", "bullet three"]
        source = "Some source text. " * 50

        def fake_llm(prompt):
            return "GROUNDED: 1\nNOT_GROUNDED: 2\nGROUNDED: 3\n"

        result = judge.llm_judge_grounding(bullets, source, fake_llm)
        assert result is not None
        grounded_count, total, ungrounded = result
        assert total == 3
        assert grounded_count == 2
        assert len(ungrounded) == 1
        assert ungrounded[0] == "bullet two"

    def test_llm_judge_returns_none_on_empty_response(self, judge: ContentJudge):
        """Empty LLM response → None."""
        result = judge.llm_judge_grounding(
            ["b1"], "source", lambda p: ""
        )
        assert result is None

    def test_llm_judge_returns_none_on_exception(self, judge: ContentJudge):
        """LLM call exception → None (graceful fallback)."""
        def raising_llm(prompt):
            raise RuntimeError("connection error")
        result = judge.llm_judge_grounding(
            ["b1"], "source", raising_llm
        )
        assert result is None

    def test_llm_judge_missing_verdict_assumes_grounded(self, judge: ContentJudge):
        """A bullet with no explicit verdict is assumed grounded (safe default)."""
        bullets = ["bullet one", "bullet two"]
        source = "source. " * 50
        # Only verdict for bullet 1; bullet 2 is missing
        def fake_llm(prompt):
            return "GROUNDED: 1\n"
        result = judge.llm_judge_grounding(bullets, source, fake_llm)
        assert result is not None
        grounded_count, total, ungrounded = result
        assert grounded_count == 2  # bullet 2 assumed grounded
        assert len(ungrounded) == 0


# ── 6. build_gap_fill_prompt ────────────────────────────────────────────────


class TestGapFillPrompt:
    @pytest.fixture
    def judge(self):
        return ContentJudge(log_callback=lambda msg, level="INFO": None)

    def test_prompt_contains_uncovered_claims(self, judge: ContentJudge):
        """build_gap_fill_prompt includes the uncovered claims."""
        prompt = judge.build_gap_fill_prompt(
            "Chapter 5",
            ["Claim about X", "Claim about Y"],
            ["existing bullet"],
        )
        assert "Chapter 5" in prompt
        assert "Claim about X" in prompt
        assert "Claim about Y" in prompt
        assert "existing bullet" in prompt

    def test_prompt_instructs_new_bullets_only(self, judge: ContentJudge):
        """Prompt must say 'NEW bullets' and 'no preamble'."""
        prompt = judge.build_gap_fill_prompt("Ch", ["c1"], ["b1"])
        assert "NEW" in prompt
        assert "preamble" in prompt.lower()
