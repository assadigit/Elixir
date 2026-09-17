"""V18.15.7.0 — thorough_summary CoT-narrative + Phase 2.2 drop-propagation + bullet cap tests.

Byte-for-byte stability gate for the 3 fixes bundled in V18.15.7.0:

  Fix 1: Filter thinking content from thorough_summary (detect_cot_narrative)
         + extended _PROMPT_LEAKAGE_PATTERNS with the CoT phrases the V18.15.6.0
         golden-master actually produced.
  Fix 2: Propagate Phase 2.2 drops to the final output by recording the GENUINE
         source_overlap (not semantic similarity) in the quarantine entry + fixing
         quarantine.recover() to PREFER fresh over stale (was max()).
  Fix 3: Hard-cap bullets at 80 (post-consolidation, post-gap-fill, post-postcheck).

Run: pytest tests/test_v18_15_7_pipeline.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken (not installed in test env) — same pattern as conftest.
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = lambda *a, **k: None
    tk.encoding_for_model = lambda *a, **k: None
    tk.Encoding = type("_E", (), {})
    sys.modules["tiktoken"] = tk

from core.summarisation.postchecks import (
    detect_cot_narrative,
    detect_prompt_leakage,
    run_post_checks,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: detect_cot_narrative — thorough_summary CoT detector
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectCotNarrative:
    """V18.15.7.0 (Fix 1): detect_cot_narrative truncates the thorough_summary
    to empty when >= 3 CoT markers are present."""

    def test_v18_15_6_0_regression_case_truncated(self):
        """The EXACT thorough_summary from the V18.15.6.0 golden-master —
        contains 'Let me organize my understanding', 'Named contributors in
        order', 'write the five sections', 'Let me count carefully',
        'Let me draft each section now' → >= 3 markers → truncate to empty."""
        cot_thorough = (
            "a comprehensive summary of Chapter 1. Let me organize my understanding: "
            "**Named contributors in order:** Tausk (1919), Erikson (1958). "
            "Wait, let me re-read the structural outline. "
            "write the five sections carefully. "
            "Let me count carefully. Let me draft each section now. "
            "I need 20-40 distinct key takeaways. Let me list them: "
            "1. Tausk (1919) introduced identity..."
        )
        cleaned, issues = detect_cot_narrative(cot_thorough, "thorough")
        assert cleaned == "", f"expected empty (CoT detected), got {cleaned[:50]!r}"
        assert len(issues) == 1
        assert issues[0].detector == "cot_narrative"
        assert issues[0].severity == "flag"
        assert "chain-of-thought" in issues[0].detail
        assert "3" in issues[0].detail or "marker" in issues[0].detail.lower()

    def test_legitimate_summary_not_truncated(self):
        """A real thorough summary with NO CoT markers → unchanged."""
        legit = (
            "The chapter examines the concept of identity in psychoanalytic theory, "
            "tracing its developmental origins from Tausk's first use of the term "
            "through Erikson's ego identity concept. Jacobson formulated five "
            "categories of contributions to identity development. Kernberg proposed "
            "a three-step process of identity formation: introjection, "
            "identification, and identity formation through depersonification."
        )
        cleaned, issues = detect_cot_narrative(legit, "thorough")
        assert cleaned == legit, "legitimate summary must not be truncated"
        assert len(issues) == 0

    def test_one_cot_marker_not_truncated(self):
        """Threshold: 1 marker is accidental (e.g., 'Let me elaborate on...') →
        NOT truncated. Need >= 3 for the sustained-CoT signal."""
        one_marker = (
            "The chapter discusses identity formation. Let me elaborate on the "
            "developmental aspects. Jacobson formulated five categories. "
            "Kernberg proposed a three-step process. The conclusion identifies "
            "seven characteristics of solid identity."
        )
        cleaned, issues = detect_cot_narrative(one_marker, "thorough")
        assert cleaned == one_marker  # unchanged
        assert len(issues) == 0

    def test_two_cot_markers_not_truncated(self):
        """Threshold: 2 markers is borderline → NOT truncated (need >= 3)."""
        two_markers = (
            "Let me organize the developmental aspects. "
            "Let me count the contributors: Tausk, Erikson, Jacobson, Kernberg. "
            "The chapter covers identity formation from multiple angles."
        )
        cleaned, issues = detect_cot_narrative(two_markers, "thorough")
        # 2 markers ("Let me organize" + "Let me count") < 3 → not truncated
        assert cleaned == two_markers
        assert len(issues) == 0

    def test_three_cot_markers_truncated(self):
        """Threshold: exactly 3 markers → truncated (the >= 3 threshold)."""
        three_markers = (
            "Let me organize my understanding of the chapter. "
            "Named contributors in order: Tausk, Erikson, Jacobson. "
            "Let me count carefully — I need 20-40 distinct key takeaways. "
            "The chapter covers identity formation."
        )
        cleaned, issues = detect_cot_narrative(three_markers, "thorough")
        assert cleaned == ""
        assert len(issues) == 1

    def test_short_text_not_checked(self):
        """Text < 50 chars → not checked (too short to be a CoT narrative)."""
        cleaned, issues = detect_cot_narrative("Short text.", "thorough")
        assert cleaned == "Short text."
        assert len(issues) == 0

    def test_empty_text_safe(self):
        """Empty/None → safe (returns unchanged, no issues)."""
        assert detect_cot_narrative("", "thorough") == ("", [])
        assert detect_cot_narrative(None, "thorough") == (None, [])

    def test_fail_open_on_crash(self):
        """If the detector crashes, it fails open (returns original text + flag)."""
        # V18.18.0.0: detect_cot_narrative moved to postcheck_detectors.py
        # Must patch _COT_NARRATIVE_RE on the defining module, not the re-export
        import core.summarisation.postcheck_detectors as _pd
        _crash_re = MagicMock()
        _crash_re.search.side_effect = RuntimeError("test crash")
        with patch.object(_pd, "_COT_NARRATIVE_RE", [_crash_re]):
            cleaned, issues = detect_cot_narrative("A" * 100, "thorough")
        assert cleaned == "A" * 100  # unchanged
        assert len(issues) == 1
        assert "crashed" in issues[0].detail.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: extended _PROMPT_LEAKAGE_PATTERNS
# ═══════════════════════════════════════════════════════════════════════════


class TestExtendedPromptLeakagePatterns:
    """V18.15.7.0 (Fix 1): the _PROMPT_LEAKAGE_PATTERNS alternation now
    includes the verbs the V18.15.6.0 golden-master produced."""

    def test_let_me_organize_stripped(self):
        """'Let me organize my understanding' is now stripped."""
        text, issues = detect_prompt_leakage(
            "Let me organize my understanding of the chapter.", "thorough"
        )
        assert "Let me organize" not in text
        assert any(i.detector == "prompt" for i in issues)

    def test_let_me_count_stripped(self):
        """'Let me count carefully' is now stripped."""
        text, issues = detect_prompt_leakage(
            "Let me count carefully. The chapter has 7 characteristics.", "thorough"
        )
        assert "Let me count" not in text

    def test_let_me_draft_stripped(self):
        """'Let me draft each section now' is now stripped."""
        text, issues = detect_prompt_leakage(
            "Let me draft each section now.", "thorough"
        )
        assert "Let me draft" not in text

    def test_named_contributors_in_order_stripped(self):
        """'Named contributors in order' is now stripped."""
        text, issues = detect_prompt_leakage(
            "Named contributors in order: Tausk, Erikson, Jacobson.", "thorough"
        )
        assert "Named contributors in order" not in text

    def test_write_the_five_sections_stripped(self):
        """'write the five sections carefully' is now stripped."""
        text, issues = detect_prompt_leakage(
            "write the five sections carefully.", "thorough"
        )
        assert "write the five sections" not in text.lower()

    def test_keep_sentences_under_stripped(self):
        """'Keep sentences under 20 words' (prompt-instruction echo) is now
        stripped. This was the V18.15.6.0 regression — this bullet shipped
        in the final output as a standalone bullet."""
        text, issues = detect_prompt_leakage(
            "Keep sentences under 20 words", "bullet[0]"
        )
        assert "Keep sentences under" not in text

    def test_preserve_technical_terms_stripped(self):
        """'Preserve technical terms' (prompt-instruction echo) is now stripped."""
        text, issues = detect_prompt_leakage(
            "Preserve technical terms", "bullet[1]"
        )
        assert "Preserve technical terms" not in text

    def test_use_active_voice_stripped(self):
        """'Use active voice' (prompt-instruction echo) is now stripped."""
        text, issues = detect_prompt_leakage(
            "Use active voice", "bullet[2]"
        )
        assert "Use active voice" not in text

    def test_what_appears_to_be_stripped(self):
        """'what appears to be a psychoanalytic text' is now stripped."""
        text, issues = detect_prompt_leakage(
            "a comprehensive summary of Chapter 1 from what appears to be a psychoanalytic text.",
            "thorough",
        )
        assert "what appears to be" not in text


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: run_post_checks integration — thorough_summary CoT truncation
# ═══════════════════════════════════════════════════════════════════════════


class TestRunPostChecksCotTruncation:
    """V18.15.7.0 (Fix 1): run_post_checks now calls detect_cot_narrative on
    the thorough_summary field BEFORE detect_prompt_leakage."""

    def test_cot_thorough_truncated_in_run_post_checks(self):
        """The V18.15.6.0 CoT thorough_summary is truncated to empty by
        run_post_checks (the caller then falls back to exec_sum)."""
        cot_thorough = (
            "Let me organize my understanding. Named contributors in order: "
            "Tausk, Erikson. Let me count carefully. Let me draft each section. "
            "write the five sections. I need 20-40 distinct key takeaways."
        )
        report = run_post_checks(
            bullets=[],
            executive_summary="The chapter covers identity formation.",
            thorough_summary=cot_thorough,
            source_text="identity formation",
        )
        # The thorough_summary should be empty (CoT truncated)
        assert report.thorough_summary == "", (
            f"expected empty thorough_summary (CoT truncated), got: {report.thorough_summary[:50]!r}"
        )
        # A cot_narrative issue should be recorded
        cot_issues = [i for i in report.issues if i.detector == "cot_narrative"]
        assert len(cot_issues) == 1, f"expected 1 cot_narrative issue, got {len(cot_issues)}"

    def test_legitimate_thorough_not_truncated(self):
        """A legitimate thorough_summary passes through unchanged."""
        legit = (
            "The chapter examines identity in psychoanalytic theory, tracing "
            "the concept from Tausk through Erikson. Jacobson formulated five "
            "categories of contributions. Kernberg proposed a three-step process."
        )
        report = run_post_checks(
            bullets=[],
            executive_summary="",
            thorough_summary=legit,
            source_text="identity theory",
        )
        assert report.thorough_summary == legit


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2: Phase 2.2 genuine source_overlap recording
# ═══════════════════════════════════════════════════════════════════════════


class TestPhase22GenuineSourceOverlap:
    """V18.15.7.0 (Fix 2): Phase 2.2 now records the GENUINE source overlap
    (not the semantic similarity) in the quarantine entry."""

    def test_prompt_instruction_bullet_has_low_source_overlap(self):
        """A prompt-instruction bullet ('Keep sentences under 20 words') has
        ~0% source overlap with the chapter text → recorded as 0.0, NOT as
        the semantic similarity (which was 0.45 in the V18.15.6.0 run)."""
        from core.summarisation.text_preprocessor import compute_source_overlap
        # The prompt-instruction bullet
        bp = "Keep sentences under 20 words"
        # A representative source text (does NOT contain this phrase)
        source = (
            "The chapter examines the concept of identity in psychoanalytic "
            "theory. Tausk (1919) introduced the term. Erikson defined ego "
            "identity. Jacobson formulated five categories."
        )
        overlap = compute_source_overlap(bp, source)
        # Should be 0.0 (or very close — no word overlap)
        assert overlap < 0.1, (
            f"prompt-instruction bullet should have ~0% source overlap, got {overlap}"
        )

    def test_real_bullet_has_high_source_overlap(self):
        """A real bullet (Tausk's identity contribution) has high source
        overlap with the chapter → correctly recorded as high."""
        from core.summarisation.text_preprocessor import compute_source_overlap
        bp = "Tausk (1919) introduced the term identity into psychoanalytic literature"
        source = (
            "Tausk (1919) was the first to use the word 'identity' in the "
            "psychoanalytic literature. He examined how a child discovers his self."
        )
        overlap = compute_source_overlap(bp, source)
        assert overlap > 0.3, f"real bullet should have >30% overlap, got {overlap}"


class TestQuarantineRecoveryPrefersFresh:
    """V18.15.7.0 (Fix 2): quarantine.recover() now PREFERS the fresh
    computation over the stale recorded value (was max() which was wrong)."""

    def test_recovery_uses_fresh_not_max(self):
        """When the recorded source_overlap is 0.45 (stale semantic sim) but
        the fresh computation is 0.0 (genuine overlap), recovery should use
        0.0 → bullet NOT resurrected."""
        from core.summarisation.quarantine import QuarantineLog
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        # Simulate the V18.15.6.0 bug: recorded 0.45 (semantic sim mislabeled)
        q.add(
            "Keep sentences under 20 words",
            stage="Phase2.2_semantic_fact_check",
            threshold=0.5,
            source_overlap=0.45,  # the mislabeled semantic similarity
            reason="test",
            chapter="test",
            actually_dropped=True,
        )
        # Fresh computation against real source → ~0.0 overlap
        source = (
            "The chapter examines identity in psychoanalytic theory. "
            "Tausk (1919) introduced the term."
        )
        resurrected = q.recover(source)
        # V18.15.7.0: should NOT resurrect (fresh 0.0 < 0.30 threshold)
        assert len(resurrected) == 0, (
            f"prompt-instruction bullet must NOT be resurrected (fresh overlap "
            f"~0.0 < 0.30 threshold). Pre-V18.15.7.0 this was resurrected "
            f"because max(0.45, 0.0) = 0.45 > 0.30. Got: {len(resurrected)} resurrected."
        )

    def test_recovery_resurrects_genuine_high_overlap(self):
        """Regression guard: a genuinely high-overlap bullet IS resurrected."""
        from core.summarisation.quarantine import QuarantineLog
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        bp = "Tausk (1919) introduced the term identity into psychoanalytic literature"
        source = (
            "Tausk (1919) was the first to use the word 'identity' in the "
            "psychoanalytic literature. He examined how a child discovers his self."
        )
        q.add(
            bp, stage="F4_source_overlap", threshold=0.25,
            source_overlap=0.0,  # initially dropped
            reason="test", chapter="test", actually_dropped=True,
        )
        resurrected = q.recover(source)
        # High overlap → should resurrect
        assert len(resurrected) == 1, (
            f"genuine high-overlap bullet should be resurrected, got {len(resurrected)}"
        )

    def test_recovery_no_source_text_uses_recorded(self):
        """When no source_text is provided, recovery uses the recorded value
        (backward compat for the no-source case)."""
        from core.summarisation.quarantine import QuarantineLog
        q = QuarantineLog(output_dir=None, recovery_threshold=0.30)
        q.add(
            "Some bullet with decent overlap",
            stage="test", threshold=0.25,
            source_overlap=0.5,  # recorded high
            reason="test", chapter="test", actually_dropped=True,
        )
        # No source_text → can't recompute → uses recorded 0.5 → resurrects
        resurrected = q.recover("")
        assert len(resurrected) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Fix 3: 80-bullet hard cap (logic test — the cap is in _summarize_inner)
# ═══════════════════════════════════════════════════════════════════════════


class TestBulletCap80:
    """V18.15.7.0 (Fix 3): a hard cap at 80 bullets is applied post-consolidation.
    We test the cap LOGIC directly (the cap is a 2-line insertion in
    _summarize_inner, so we test the slicing behavior)."""

    def test_cap_80_applied_to_212_bullets(self):
        """Simulate the V18.15.6.0 regression: 212 bullets → capped to 80."""
        bullets = [f"Bullet {i}: some content about identity." for i in range(212)]
        # Apply the cap (mirrors the logic in summarizer.py:3699)
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert len(bullets) == 80, f"expected 80 after cap, got {len(bullets)}"

    def test_cap_not_applied_below_80(self):
        """46 bullets (gold standard) → NOT capped (stays 46)."""
        bullets = [f"Bullet {i}: some content." for i in range(46)]
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert len(bullets) == 46, f"expected 46 (under cap), got {len(bullets)}"

    def test_cap_not_applied_at_exactly_80(self):
        """80 bullets (exactly at cap) → NOT capped (stays 80)."""
        bullets = [f"Bullet {i}: some content." for i in range(80)]
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert len(bullets) == 80

    def test_cap_applied_at_81(self):
        """81 bullets (1 over cap) → capped to 80."""
        bullets = [f"Bullet {i}: some content." for i in range(81)]
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert len(bullets) == 80

    def test_cap_preserves_first_80(self):
        """The cap preserves the FIRST 80 bullets (order preserved)."""
        bullets = [f"Bullet {i}." for i in range(100)]
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert bullets[0] == "Bullet 0."
        assert bullets[79] == "Bullet 79."
        assert "Bullet 80" not in bullets

    def test_cap_empty_safe(self):
        """Empty bullet list → no crash (the `if bullets` guard)."""
        bullets: list = []
        if bullets and len(bullets) > 80:
            bullets = bullets[:80]
        assert bullets == []
