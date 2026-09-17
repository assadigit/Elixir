"""V18.2.24 (Phase 3.2) — Tests for PromptBudget token accounting + compaction.

Covers:
1. estimate_tokens heuristic
2. fits() correctly reports when text fits/exceeds budget
3. compact() drops the middle, preserves head + tail
4. compact() is idempotent (already-fitting text returned unchanged)
5. allocate() tracks cumulative usage across calls
6. reset() clears state for a new chapter
7. diagnostics: compaction_count, tokens_saved, summary()
8. edge cases: empty text, tiny budget, tail-only reduction
"""
from __future__ import annotations

from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.prompt_budget import PromptBudget, estimate_tokens


class TestEstimateTokens:
    def test_empty_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        assert estimate_tokens(None) == 0  # type: ignore[arg-type]

    def test_short_text(self):
        # 4 chars = 1 token
        assert estimate_tokens("test") == 1

    def test_longer_text(self):
        assert estimate_tokens("a" * 40) == 10

    def test_minimum_1_for_nonempty(self):
        assert estimate_tokens("a") == 1


class TestFits:
    def test_fits_when_small(self):
        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000)
        assert budget.fits("short text")

    def test_does_not_fit_when_large(self):
        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000, safety_margin=4096)
        # available = 32768 - 16000 - 4096 = 12672 tokens = 50688 chars
        big = "x" * 60000  # 15000 tokens > 12672
        assert not budget.fits(big)

    def test_reserved_reduces_available(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        # available = 900 tokens = 3600 chars
        assert budget.fits("x" * 100, reserved=0)  # 25 + 0 = 25 <= 900
        # With reserved=850: 25 + 850 = 875 <= 900 → still fits
        assert budget.fits("x" * 100, reserved=850)
        # But with reserved=880: 25 + 880 = 905 > 900 → doesn't fit
        assert not budget.fits("x" * 100, reserved=880)


class TestCompact:
    def test_already_fitting_returned_unchanged(self):
        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000)
        text = "short text"
        assert budget.compact(text) == text

    def test_drops_middle_preserves_head_tail(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        # available = 900 tokens = 3600 chars
        text = "HEAD " + "x" * 10000 + " TAIL"  # ~2501 tokens, way over
        compacted = budget.compact(text)
        assert "HEAD" in compacted
        assert "TAIL" in compacted
        assert "compacted" in compacted.lower() or "omitted" in compacted.lower()
        assert len(compacted) < len(text)

    def test_head_tail_fractions(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        text = "A" * 4000 + "B" * 4000 + "C" * 4000  # 12000 chars = 3000 tokens
        compacted = budget.compact(text, keep_head=0.1, keep_tail=0.1)
        # Should keep ~10% head + 10% tail
        assert "A" * 100 in compacted  # head preserved
        assert "C" * 100 in compacted  # tail preserved
        assert "B" * 1000 not in compacted  # middle dropped

    def test_compact_tracks_diagnostics(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        text = "x" * 10000
        budget.compact(text)
        assert budget.compaction_count == 1
        assert budget.tokens_saved > 0

    def test_compact_idempotent(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        text = "x" * 5000
        first = budget.compact(text)
        second = budget.compact(first)  # already fits
        assert first == second
        assert budget.compaction_count == 1  # only compacted once

    def test_empty_text(self):
        budget = PromptBudget()
        assert budget.compact("") == ""

    def test_tail_reduced_if_head_tail_exceed_target(self):
        """If head + tail still exceeds target, tail is reduced (last resort)."""
        budget = PromptBudget(max_context_tokens=100, max_output_tokens=10, safety_margin=0)
        # available = 90 tokens = 360 chars
        text = "x" * 10000
        compacted = budget.compact(text, keep_head=0.5, keep_tail=0.5)
        # head=0.5 would be 5000 chars (1250 tokens) — way over.
        # Tail + head must be reduced to fit 90 tokens.
        compacted_tokens = estimate_tokens(compacted)
        assert compacted_tokens <= 90 + 50, f"compacted is {compacted_tokens} tokens (target ~90)"  # within tolerance


class TestAllocate:
    def test_tracks_cumulative_usage(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        assert budget.used_tokens == 0
        budget.allocate(prompt_tokens=200, response_tokens=100)
        assert budget.used_tokens == 300
        budget.allocate(prompt_tokens=200, response_tokens=100)
        assert budget.used_tokens == 600

    def test_allocate_reduces_available(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        initial_available = budget.available
        budget.allocate(prompt_tokens=200, response_tokens=100)
        assert budget.available == initial_available - 300

    def test_available_never_negative(self):
        budget = PromptBudget(max_context_tokens=100, max_output_tokens=50, safety_margin=10)
        budget.allocate(prompt_tokens=1000, response_tokens=1000)
        assert budget.available == 0  # clamped, not negative


class TestReset:
    def test_resets_usage(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        budget.allocate(200, 100)
        budget.compact("x" * 5000)
        assert budget.used_tokens > 0
        assert budget.compaction_count > 0
        budget.reset()
        assert budget.used_tokens == 0
        assert budget.compaction_count == 0
        assert budget.tokens_saved == 0


class TestDiagnostics:
    def test_summary_string(self):
        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000)
        s = budget.summary()
        assert "PromptBudget" in s
        assert "used=0" in s
        assert "available" in s

    def test_summary_after_usage(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        budget.allocate(200, 100)
        budget.compact("x" * 5000)
        s = budget.summary()
        assert "used=300" in s
        assert "compactions=1" in s


class TestRealisticScenario:
    """Simulate a chapter pipeline: content → compact → allocate → next call."""

    def test_chapter_pipeline_budget_tracking(self):
        budget = PromptBudget(max_context_tokens=32768, max_output_tokens=16000, safety_margin=4096)
        # available = 12672 tokens = 50688 chars
        # Chapter content: 80000 chars = 20000 tokens (over budget)
        chapter = "Chapter intro. " + "x" * 70000 + " Chapter conclusion."
        assert not budget.fits(chapter)
        compacted = budget.compact(chapter)
        assert budget.fits(compacted)
        # Simulate the LLM call with a SMALL response so budget remains
        budget.allocate(prompt_tokens=estimate_tokens(compacted), response_tokens=2000)
        # Next call has less budget but a short followup still fits
        assert budget.available < 12672
        followup = "Write a thorough summary of the chapter."
        assert budget.fits(followup)

    def test_multiple_calls_deplete_budget(self):
        budget = PromptBudget(max_context_tokens=1000, max_output_tokens=100, safety_margin=0)
        # available = 900 tokens
        calls = 0
        while budget.available > 50:
            budget.allocate(prompt_tokens=100, response_tokens=50)
            calls += 1
            if calls > 20:
                break
        assert budget.available < 100  # depleted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
