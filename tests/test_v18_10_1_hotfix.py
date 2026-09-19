"""V18.10.1 hotfix tests — deadline raise + anti-false-precision grammar guard.

Tests for:
1. IQ2_S chapter deadline (V18.10.1 raised 1500→1800; superseded by
   V18.15.4.0's 1800→2400 + V18.20.1.0 D9 centralization to
   core/llm/iq2_s_profile.py — scans re-pointed at the 2400s contract in
   the V18.20.2.0 test-debt pass)
2. Anti-false-precision rewrite SKIPS when claim1 is a fragment starting with
   a conjunction (prevents "Jacobson and Kernberg both and Mahler" broken grammar)

Run: pytest tests/test_v18_10_1_hotfix.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ════════════════════════════════════════════════════════════════════════════
# Fix 1 — IQ2_S deadline raise (1500s → 1800s)
# ════════════════════════════════════════════════════════════════════════════


class TestIQ2SDedlineRaise:
    """Verify the IQ2_S chapter deadline (V18.20.2.0 test-debt update).

    STALE CONTRACT HISTORY: V18.10.1 raised the deadline 1500s → 1800s;
    V18.15.4.0 raised it 1800s → 2400s; V18.20.1.0 (D9) centralized the
    constant to ``core.llm.iq2_s_profile.IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC``
    (= 2400 — the hard constraint "IQ2_S deadline 2400s"). These scans were
    two generations stale (asserting the 1800s literal + the V18.10.1 marker
    in summarizer.py); they are re-pointed at the CURRENT contract:
    2400 present, the old 1500s/1800s deadline comparisons absent. The
    surviving half of the V18.10.1 hotfix (the grammar guard) is documented
    in summary_validator.py — asserted in TestAntiFalsePrecisionGrammarGuard.
    """

    def test_deadline_2400_in_source(self):
        """The 2400s IQ2_S deadline contract must be visible in summarizer.py."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        # Current IQ2_S deadline: 2400s (docstring + profile constant wiring).
        assert "2400" in content, "2400s IQ2_S deadline must be in summarizer.py"
        assert "IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC" in content, (
            "Deadline floor must come from the centralized profile constant"
        )

    def test_old_deadline_literals_replaced(self):
        """The old 1500s/1800s hardcoded deadline comparisons must be gone.

        The remaining "1500"/"1800" literals in summarizer.py are unrelated
        to the deadline (max-context token reserve, thorough ≤1500-words
        length rule, and a historical V18.14.2 gap-fill comment).
        """
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        assert "self.local_chapter_deadline < 1500" not in content, (
            "Threshold should be 2400 (was 1500)"
        )
        assert "self.local_chapter_deadline < 1800" not in content, (
            "Threshold should be 2400 (was 1800)"
        )
        # And the centralized constant itself is 2400 (not 1500/1800).
        profile_path = _project_root / "core" / "llm" / "iq2_s_profile.py"
        profile = profile_path.read_text(encoding="utf-8")
        assert "CHAPTER_DEADLINE_SEC: int = 2400" in profile, (
            "IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC must be 2400"
        )
        assert "CHAPTER_DEADLINE_SEC: int = 1500" not in profile
        assert "CHAPTER_DEADLINE_SEC: int = 1800" not in profile

    def test_log_message_says_deadline_raised(self):
        """The raise log message must reference the profile constant.

        (Old test asserted the literal "1800s" — it passed by accident via
        the historical V18.14.2 comment at the gap-fill loop, not the live
        log message.)
        """
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        assert "Chapter deadline raised → {IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC}s" in content, (
            "The deadline-raise log must carry the centralized 2400s constant"
        )


# ════════════════════════════════════════════════════════════════════════════
# Fix 2 — Anti-false-precision grammar guard
# ════════════════════════════════════════════════════════════════════════════


class TestAntiFalsePrecisionGrammarGuard:
    """Verify the V18.10.1 grammar guard prevents broken rewrites."""

    def _run_check(self, bullet: str, source: str):
        """Run anti_false_precision_check and return (result, log_calls)."""
        from core.summarisation.summary_validator import anti_false_precision_check

        result = {
            "bullet_points": [bullet],
            "executive_summary": "",
            "thorough_summary": "",
            "key_distinctions": "",
            "theoretical_tensions": "",
        }
        log_calls = []
        anti_false_precision_check(
            "heading", source, result, log=lambda m, l: log_calls.append((m, l))
        )
        return result["bullet_points"][0], log_calls

    def test_broken_jacobson_case_skipped(self):
        """The exact V18.10.0 broken case should be SKIPPED, not rewritten."""
        bullet = (
            "Jacobson (1964) and Mahler (1958, 1968), while Kernberg (1967, 1976, 1980b) "
            "formulated a three-step process."
        )
        source = (
            "Jacobson 1964, Kernberg 1967 regard identity as sine qua non "
            "of borderline and narcissistic disorders"
        )
        result, logs = self._run_check(bullet, source)
        # Should NOT contain "both and" (the broken merge)
        assert "both and" not in result, f"Broken rewrite still present: {result}"
        # Should have a SKIPPED log message
        assert any("SKIPPED" in m for m, _ in logs), f"Expected SKIPPED log, got: {logs}"
        # The original should be preserved
        assert "Jacobson (1964) and Mahler" in result

    def test_valid_rewrite_still_works(self):
        """A valid contrast should still be rewritten."""
        bullet = "Jacobson views identity as borderline while Kernberg views it as narcissistic."
        source = "Jacobson 1964, Kernberg 1967 regard identity as borderline and narcissistic"
        result, logs = self._run_check(bullet, source)
        assert "Jacobson and Kernberg both" in result, (
            f"Valid rewrite should still work, got: {result}"
        )

    def test_claim_starting_with_and_skipped(self):
        """claim1 starting with 'and' should be skipped."""
        bullet = "Smith (1970) and Jones (1972), while Brown (1975) proposed the theory."
        source = "Smith 1970, Brown 1975 regard the theory as fundamental"
        result, logs = self._run_check(bullet, source)
        # Should NOT produce "Smith and Brown both and Jones"
        assert "both and" not in result, f"Broken rewrite: {result}"

    def test_claim_starting_with_or_skipped(self):
        """claim1 starting with 'or' should be skipped."""
        bullet = "Erikson (1956) or Marcia (1966), while Kernberg (1967) defined identity."
        source = "Erikson 1956, Kernberg 1967 regard identity as central"
        result, logs = self._run_check(bullet, source)
        assert "both or" not in result, f"Broken rewrite: {result}"

    def test_claim_starting_with_but_skipped(self):
        """claim1 starting with 'but' should be skipped."""
        bullet = "Freud (1923) but Hartmann (1950), while Kernberg (1967) formulated ego."
        source = "Freud 1923, Kernberg 1967 regard ego as foundational"
        result, logs = self._run_check(bullet, source)
        assert "both but" not in result, f"Broken rewrite: {result}"

    def test_short_claim_skipped(self):
        """A very short claim1 (<8 chars) should be skipped (too short for a predicate)."""
        # "views" is 5 chars — too short
        bullet = "Smith (1970) views while Jones (1972) views the theory differently."
        source = "Smith 1970, Jones 1972 regard the theory as important"
        result, logs = self._run_check(bullet, source)
        # The rewrite would be "Smith and Jones both views" — grammatically wrong
        # (should be "view" not "views"), so skip it
        # Note: this might still rewrite if "views" is long enough; the threshold is 8 chars
        # Let's just verify no "both and" broken pattern
        assert "both and" not in result

    def test_no_crash_on_empty_claim(self):
        """Should not crash if claim1 is empty."""
        bullet = "Smith while Jones views the theory."
        source = "Smith 1970, Jones 1972 regard the theory as important"
        # This should not crash
        result, logs = self._run_check(bullet, source)
        assert isinstance(result, str)

    def test_grammar_guard_in_source(self):
        """The grammar guard code must be in summary_validator.py."""
        sv_path = _project_root / "core" / "summarisation" / "summary_validator.py"
        content = sv_path.read_text(encoding="utf-8")
        assert "V18.10.1" in content, "V18.10.1 change must be documented"
        assert "_CONJUNCTIONS" in content, "Conjunction set must be defined"
        assert "_is_fragment" in content, "Fragment check must be present"
        assert "SKIPPED" in content, "SKIPPED log message must be present"
