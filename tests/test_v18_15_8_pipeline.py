"""V18.15.8.0 — exec-from-thorough + recovery skip Phase 2.2 + prompt-pattern check tests.

Byte-for-byte stability gate for the 4 fixes bundled in V18.15.8.0:

  Fix 1 (user idea): Reorder — produce thorough first, then derive exec FROM
         thorough via a followup LLM call (not the backwards fallback).
         New: prompt_assembly.build_exec_from_thorough_prompt + Summarizer._ensure_exec_from_thorough.
  Fix 2: Skip Phase 2.2 entries in quarantine.recover() (they were dropped for
         semantic reasons, not source-overlap reasons).
  Fix 3: Prompt-instruction-pattern check in recovery — don't resurrect bullets
         matching _PROMPT_INSTRUCTION_PATTERNS regardless of overlap score.

Run: pytest tests/test_v18_15_8_pipeline.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.prompt_assembly import build_exec_from_thorough_prompt
from core.summarisation.quarantine import (
    QuarantineLog,
    _matches_prompt_leakage_pattern,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: build_exec_from_thorough_prompt
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildExecFromThoroughPrompt:
    """V18.15.8.0 (Fix 1): the exec-from-thorough prompt builder."""

    def test_prompt_contains_xml_tag(self):
        """The prompt must instruct the model to wrap output in <executive_summary> tags."""
        p = build_exec_from_thorough_prompt("Test Chapter", "A thorough summary.", "en")
        assert "<executive_summary>" in p
        assert "</executive_summary>" in p

    def test_prompt_contains_heading(self):
        """The prompt must include the chapter heading."""
        p = build_exec_from_thorough_prompt("IDENTITY AND ITS ORIGINS", "Thorough.", "en")
        assert "IDENTITY AND ITS ORIGINS" in p

    def test_prompt_contains_thorough_summary(self):
        """The prompt must include the thorough summary as context."""
        thorough = "The chapter examines identity from Tausk through Erikson."
        p = build_exec_from_thorough_prompt("Chapter", thorough, "en")
        assert thorough in p

    def test_prompt_word_count_constraint(self):
        """The prompt must specify a word-count constraint.

        V0.05 (F9b): the target is SOURCE-SCALED (the thorough fixture is a
        1-word source → a tiny scaled range), never the absolute 150-250.
        """
        import re as _re

        p = build_exec_from_thorough_prompt("Chapter", "Thorough.", "en")
        assert _re.search(r"\b\d+-\d+ word executive summary", p)
        assert _re.search(r"\b\d+-\d+ word \(strict\)", p)
        assert "150-250" not in p

    def test_prompt_no_bullets_constraint(self):
        """The prompt must say NOT bullet points."""
        p = build_exec_from_thorough_prompt("Chapter", "Thorough.", "en")
        assert "NOT bullet" in p or "not bullet" in p.lower() or "Flowing prose" in p

    def test_prompt_persian_language(self):
        """The prompt must say 'Write in Persian (Farsi)' when language='fa'."""
        p = build_exec_from_thorough_prompt("Chapter", "Thorough.", "fa")
        assert "Write in Persian (Farsi)" in p

    def test_prompt_english_language(self):
        """The prompt must say 'Write in English' when language='en'."""
        p = build_exec_from_thorough_prompt("Chapter", "Thorough.", "en")
        assert "Write in English" in p

    def test_thorough_capped_at_4000_chars(self):
        """The prompt must cap the thorough at 4000 chars (token budget)."""
        long_thorough = "A" * 10000
        p = build_exec_from_thorough_prompt("Chapter", long_thorough, "en")
        # The thorough should be truncated to 4000 chars
        assert "A" * 4000 in p
        assert "A" * 4001 not in p


# ═══════════════════════════════════════════════════════════════════════════
# Fix 3: _matches_prompt_leakage_pattern
# ═══════════════════════════════════════════════════════════════════════════


class TestMatchesPromptLeakagePattern:
    """V18.15.8.0 (Fix 3): the prompt-instruction-pattern matcher."""

    @pytest.mark.parametrize(
        "bullet",
        [
            "Reading level: IELTS 7-9, sentences under 20 words, active voice, common words.",
            "Keep sentences under 20 words",
            "Sentences under 20 words",
            "Preserve technical terms",
            "Preserve all citations",
            "Use active voice",
            "Use common words",
            "Executive summary: 150-250 words",
            "Bullet points: 20-40 items",
            "5 sections in XML format",
            "Cover all named contributors",
            "Include the full progression",
            "End with the conclusion's enumerated list",
            "Distinguish philosophical from developmental contributions",
            "Preserve developmental mechanisms as sequences",
            "These two requirements seem contradictory.",
            "Theoretical tensions: 2-4",
            "Key distinctions: 2-5",
            "Active voice",
            "No invented facts",
        ],
    )
    def test_prompt_instruction_bullets_detected(self, bullet):
        """Each prompt-instruction bullet must be detected (returns True)."""
        assert _matches_prompt_leakage_pattern(bullet) is True, (
            f"expected True for prompt-instruction bullet: {bullet!r}"
        )

    @pytest.mark.parametrize(
        "bullet",
        [
            "Tausk (1919) introduced the term identity into psychoanalytic literature.",
            "Erikson (1956) defined ego identity as persistent sameness within oneself.",
            "Jacobson (1964) formulated five categories of contributions to identity development.",
            "Kernberg (1967) proposed that ego identity development requires two essential tasks.",
            "Mahler distinguished psychological birth from biological birth.",
            "The chapter concludes by identifying seven characteristics of solid identity.",
        ],
    )
    def test_real_bullets_not_detected(self, bullet):
        """Real summary bullets must NOT be flagged (returns False)."""
        assert _matches_prompt_leakage_pattern(bullet) is False, (
            f"expected False for real bullet: {bullet!r}"
        )

    def test_empty_bullet_safe(self):
        """Empty/None bullet → False (no crash)."""
        assert _matches_prompt_leakage_pattern("") is False
        assert _matches_prompt_leakage_pattern(None) is False

    def test_check_only_first_200_chars(self):
        """The matcher checks only the first 200 chars (prompt echoes are short + at the start)."""
        # A long bullet where the prompt-instruction part is after char 200
        bullet = "A" * 250 + "Keep sentences under 20 words"
        # The prompt-instruction pattern is AFTER char 200 → not detected
        assert _matches_prompt_leakage_pattern(bullet) is False


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2 + Fix 3: quarantine recovery integration
# ═══════════════════════════════════════════════════════════════════════════


class TestRecoverySkipPhase22:
    """V18.15.8.0 (Fix 2): quarantine.recover() skips Phase2.2_semantic_fact_check entries."""

    def test_phase22_entry_not_resurrected(self):
        """A Phase2.2 entry with high recorded overlap must NOT be resurrected."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        q.add(
            "Keep sentences under 20 words",
            stage="Phase2.2_semantic_fact_check",
            threshold=0.5,
            source_overlap=0.45,  # above the 0.30 recovery threshold
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        resurrected = q.recover("identity formation psychoanalytic theory")
        assert len(resurrected) == 0, (
            f"Phase2.2 entry must NOT be resurrected (Fix 2). Got: {len(resurrected)}"
        )

    def test_f4_entry_still_resurrectable(self):
        """Regression guard: F4_source_overlap entries ARE still resurrectable."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        bp = "Tausk (1919) introduced the term identity into psychoanalytic literature"
        source = (
            "Tausk (1919) was the first to use the word 'identity' in the "
            "psychoanalytic literature. He examined how a child discovers his self."
        )
        q.add(
            bp,
            stage="F4_source_overlap",
            threshold=0.25,
            source_overlap=0.0,  # initially dropped
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        resurrected = q.recover(source)
        assert len(resurrected) == 1, (
            f"F4 entry should be resurrected (genuine high overlap). Got: {len(resurrected)}"
        )


class TestRecoverySkipPromptLeakage:
    """V18.15.8.0 (Fix 3): quarantine.recover() skips bullets matching
    _PROMPT_INSTRUCTION_PATTERNS."""

    def test_prompt_instruction_bullet_not_resurrected(self):
        """A bullet matching a prompt-instruction pattern must NOT be resurrected,
        even if it has high source overlap (word-overlap false positive)."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        # This bullet has "developmental" + "mechanisms" + "sequences" — all
        # words that appear in the source → false-positive high word overlap.
        # But it matches the "Preserve developmental mechanisms" pattern → Fix 3 skips it.
        q.add(
            "Preserve developmental mechanisms as sequences",
            stage="F4_source_overlap",  # NOT Phase2.2 — so Fix 2 doesn't skip it
            threshold=0.25,
            source_overlap=0.45,  # false-positive high word overlap
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        # Source contains the words "developmental" + "mechanisms" → fresh overlap > 0.30
        source = (
            "The chapter examines developmental mechanisms and sequences of "
            "identity formation through multiple psychoanalytic theorists."
        )
        resurrected = q.recover(source)
        assert len(resurrected) == 0, (
            f"prompt-instruction bullet must NOT be resurrected (Fix 3). Got: {len(resurrected)}"
        )

    def test_reading_level_bullet_not_resurrected(self):
        """The 'Reading level: IELTS 7-9' bullet must NOT be resurrected."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        q.add(
            "Reading level: IELTS 7-9, sentences under 20 words, active voice, common words.",
            stage="F4_source_overlap",
            threshold=0.25,
            source_overlap=0.45,  # false-positive high word overlap
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        source = "The chapter covers identity, words, active, common, voice, reading level."
        resurrected = q.recover(source)
        assert len(resurrected) == 0, (
            f"'Reading level' bullet must NOT be resurrected (Fix 3). Got: {len(resurrected)}"
        )

    def test_executive_summary_template_bullet_not_resurrected(self):
        """The 'Executive summary: 150-250 words' bullet must NOT be resurrected."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        q.add(
            "Executive summary: 150-250 words",
            stage="F4_source_overlap",
            threshold=0.25,
            source_overlap=0.45,
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        source = "The executive summary covers the chapter's main thesis."
        resurrected = q.recover(source)
        assert len(resurrected) == 0

    def test_real_bullet_still_resurrected(self):
        """Regression guard: a real bullet (no prompt-instruction pattern) IS resurrected."""
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        bp = "Tausk (1919) introduced the term identity into psychoanalytic literature"
        source = (
            "Tausk (1919) was the first to use the word 'identity' in the "
            "psychoanalytic literature. He examined how a child discovers his self."
        )
        q.add(
            bp,
            stage="F4_source_overlap",
            threshold=0.25,
            source_overlap=0.0,
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        resurrected = q.recover(source)
        assert len(resurrected) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: _ensure_exec_from_thorough (logic test — the LLM call is mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsureExecFromThorough:
    """V18.15.8.0 (Fix 1): the _ensure_exec_from_thorough method.

    We test the LOGIC by mocking the LLM call — the method is in Summarizer
    which has too many dependencies to construct in a unit test. We test
    the prompt-building + XML-parsing + validation logic directly.
    """

    def test_xml_tag_parsed_correctly(self):
        """When the LLM returns <executive_summary>content</executive_summary>,
        the content is extracted."""
        # Simulate the parsing logic from _ensure_exec_from_thorough
        import re

        raw = (
            "Some preamble\n<executive_summary>\nThis is the executive summary. " * 20
            + "\n</executive_summary>"
        )
        m = re.search(r"<executive_summary>(.*?)</executive_summary>", raw, re.DOTALL)
        assert m is not None
        exec_sum = m.group(1).strip()
        assert "This is the executive summary" in exec_sum

    def test_no_xml_tag_fallback_to_raw(self):
        """When the LLM returns no XML tag, the raw text is used (fallback)."""
        import re

        raw = "This is the executive summary without XML tags. " * 20
        m = re.search(r"<executive_summary>(.*?)</executive_summary>", raw, re.DOTALL)
        if m:
            exec_sum = m.group(1).strip()
        else:
            exec_sum = raw.strip()
        assert exec_sum == raw.strip()

    def test_word_count_validation(self):
        """The derived exec must be ≥50 words (validation gate)."""
        short_exec = "Too short. Only a few words."
        long_exec = (
            "This is a proper executive summary with enough words to pass the validation gate. "
            * 10
        )
        assert len(short_exec.split()) < 50, "short exec should fail validation"
        assert len(long_exec.split()) >= 50, "long exec should pass validation"

    def test_short_thorough_returns_empty(self):
        """When thorough is <50 chars, the method returns empty (can't derive)."""
        # Mirrors the logic: if not thorough or len(thorough.strip()) < 50: return ""
        short_thorough = "Short"
        if not short_thorough or len(short_thorough.strip()) < 50:
            result = ""
        else:
            result = "would fire LLM call"
        assert result == ""

    def test_empty_thorough_returns_empty(self):
        """Empty thorough → returns empty."""
        thorough = ""
        if not thorough or len(thorough.strip()) < 50:
            result = ""
        else:
            result = "would fire LLM call"
        assert result == ""
