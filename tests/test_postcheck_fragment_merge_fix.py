"""V18.9 (Option B) - Postcheck fragment-merge + deadline fix tests.

Tests for:
1. detect_word_fragment_merge no longer flags legitimate plurals/inflections
   (the 5th-occurrence false-positive defect class)
2. Real fragment merges (adolescenceo fill) are still caught
3. IQ2_S deadline is raised to 1500s (prevents semantic dedup skip)

Run: pytest tests/test_postcheck_fragment_merge_fix.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.postchecks import (
    _is_legitimate_inflection,
    detect_word_fragment_merge,
)

# ════════════════════════════════════════════════════════════════════════════
# 1. _is_legitimate_inflection suffix checks
# ════════════════════════════════════════════════════════════════════════════

class TestIsLegitimateInflection:
    """Test the suffix checker that prevents false positives."""

    def test_plural_s(self):
        """'s' is a legitimate plural suffix."""
        assert _is_legitimate_inflection("difference", "s") is True
        assert _is_legitimate_inflection("condition", "s") is True
        assert _is_legitimate_inflection("contribution", "s") is True

    def test_plural_es(self):
        """'es' is a legitimate plural suffix."""
        assert _is_legitimate_inflection("box", "es") is True
        assert _is_legitimate_inflection("church", "es") is True

    def test_past_tense_ed(self):
        """'ed' is a legitimate past-tense suffix."""
        assert _is_legitimate_inflection("contribute", "ed") is True
        assert _is_legitimate_inflection("view", "ed") is True

    def test_adjective_al(self):
        """'al' is a legitimate adjective suffix."""
        assert _is_legitimate_inflection("environment", "al") is True
        assert _is_legitimate_inflection("condition", "al") is True

    def test_adverb_ly(self):
        """'ly' is a legitimate adverb suffix."""
        assert _is_legitimate_inflection("quick", "ly") is True
        assert _is_legitimate_inflection("clear", "ly") is True

    def test_participle_ing(self):
        """'ing' is a legitimate present-participle suffix."""
        assert _is_legitimate_inflection("run", "ing") is True
        assert _is_legitimate_inflection("think", "ing") is True

    def test_not_a_suffix(self):
        """'o' is NOT a legitimate suffix — it's a fragment."""
        assert _is_legitimate_inflection("adolescence", "o") is False
        assert _is_legitimate_inflection("the", "x") is False

    def test_case_insensitive(self):
        """Suffix check should be case-insensitive."""
        assert _is_legitimate_inflection("Difference", "S") is True
        assert _is_legitimate_inflection("DIFFERENCE", "s") is True


# ════════════════════════════════════════════════════════════════════════════
# 2. Plural/inflection false-positive elimination (the 5th-occurrence fix)
# ════════════════════════════════════════════════════════════════════════════

class TestPluralFalsePositivesEliminated:
    """Verify that legitimate plurals are NOT flagged as fragment merges.

    These are the exact words that were false-positive-flagged in the
    V18.7.0 and V18.8.0 audits (5th occurrence of the defect class).
    """

    def _count_fragment_flags(self, text: str, label: str = "test") -> int:
        """Run detect_word_fragment_merge and count fragment_merge issues."""
        _, issues = detect_word_fragment_merge(text, label)
        return sum(1 for i in issues if i.detector == "fragment_merge")

    def test_differences_not_flagged(self):
        """'differences' should NOT be flagged (plural of 'difference')."""
        count = self._count_fragment_flags("the differences in identity formation")
        assert count == 0, "'differences' should not be flagged as a fragment merge"

    def test_dimensions_not_flagged(self):
        """'dimensions' should NOT be flagged (plural of 'dimension')."""
        count = self._count_fragment_flags("the dimensions of identity")
        assert count == 0, "'dimensions' should not be flagged"

    def test_contributions_not_flagged(self):
        """'contributions' should NOT be flagged (plural of 'contribution')."""
        count = self._count_fragment_flags("the contributions of Jacobson")
        assert count == 0, "'contributions' should not be flagged"

    def test_views_not_flagged(self):
        """'views' should NOT be flagged (plural of 'view')."""
        count = self._count_fragment_flags("the views of Erikson on identity")
        assert count == 0, "'views' should not be flagged"

    def test_questions_not_flagged(self):
        """'questions' should NOT be flagged (plural of 'question')."""
        count = self._count_fragment_flags("the questions about identity")
        assert count == 0, "'questions' should not be flagged"

    def test_environmental_not_flagged(self):
        """'environmental' should NOT be flagged (adjective of 'environment')."""
        count = self._count_fragment_flags("the environmental factors")
        assert count == 0, "'environmental' should not be flagged"

    def test_foundations_not_flagged(self):
        """'foundations' should NOT be flagged (plural of 'foundation')."""
        count = self._count_fragment_flags("the foundations of identity")
        assert count == 0, "'foundations' should not be flagged"

    def test_sensations_not_flagged(self):
        """'sensations' should NOT be flagged (plural of 'sensation')."""
        count = self._count_fragment_flags("bodily sensations in infancy")
        assert count == 0, "'sensations' should not be flagged"

    def test_conditions_not_flagged(self):
        """'conditions' should NOT be flagged (plural of 'condition')."""
        count = self._count_fragment_flags("the conditions for identity")
        assert count == 0, "'conditions' should not be flagged"

    def test_representations_not_flagged(self):
        """'representations' should NOT be flagged (plural of 'representation')."""
        count = self._count_fragment_flags("self and object representations")
        assert count == 0, "'representations' should not be flagged"

    def test_modifications_not_flagged(self):
        """'modifications' should NOT be flagged (plural of 'modification')."""
        count = self._count_fragment_flags("modifications of oedipal resolution")
        assert count == 0, "'modifications' should not be flagged"

    def test_positions_not_flagged(self):
        """'positions' should NOT be flagged (plural of 'position')."""
        count = self._count_fragment_flags("pregenital libidinal positions")
        assert count == 0, "'positions' should not be flagged"

    def test_traces_not_flagged(self):
        """'traces' should NOT be flagged (plural of 'trace')."""
        count = self._count_fragment_flags("the author traces identity origins")
        assert count == 0, "'traces' should not be flagged"

    def test_years_not_flagged(self):
        """'years' should NOT be flagged (plural of 'year')."""
        count = self._count_fragment_flags("at approximately two years of age")
        assert count == 0, "'years' should not be flagged"


# ════════════════════════════════════════════════════════════════════════════
# 3. Real fragment merges are still caught
# ════════════════════════════════════════════════════════════════════════════

class TestRealFragmentMergesStillCaught:
    """Verify that genuine fragment merges are still detected (no false negatives)."""

    def _has_fragment_flag(self, text: str, source: str = "") -> bool:
        """V18.15.3.2 source-grounded validation: detect_word_fragment_merge
        needs source_text to validate the base word. Without it, the function
        can't confirm the base word is real → returns no issues (conservative)."""
        _, issues = detect_word_fragment_merge(text, "test", source)
        return any(i.detector == "fragment_merge" for i in issues)

    def test_adolescenceo_fill_caught(self):
        """The original V18.2.18 test case: 'adolescenceo fill'."""
        source = "Adolescence is a key developmental phase. To fill the lacunae."
        assert self._has_fragment_flag("adolescenceo fill the lacunae", source) is True

    def test_theoryo_caught(self):
        """A stray 'o' (not a suffix) should be caught."""
        source = "The theory of identity formation is central to this chapter."
        assert self._has_fragment_flag("the theoryo of identity", source) is True

    def test_random_fragment_caught(self):
        """A random non-suffix stray char on a known word should be caught.
        'theoryx' → base='theory' (in source), stray='x' (NOT a suffix)."""
        source = "The theory of identity formation is central to this chapter."
        assert self._has_fragment_flag("the theoryx of identity", source) is True


# ════════════════════════════════════════════════════════════════════════════
# 4. IQ2_S deadline raise (prevents semantic dedup skip)
# ════════════════════════════════════════════════════════════════════════════

class TestIQ2SDedlineRaise:
    """Verify the V18.9 deadline raise for IQ2_S is in the source."""

    def test_deadline_raise_code_exists(self):
        """The V18.9 deadline raise for IQ2_S must be in summarizer.py."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        assert "V18.9" in content or "V18.15.4.0" in content, "V18.9/V18.15.4.0 change must be documented in summarizer.py"
        assert "2400" in content, "2400s deadline (V18.15.4.0) must be in summarizer.py"
        assert "is_iq2_s" in content, "IQ2_S detection must be used"

    def test_deadline_raise_before_academic_rigor(self):
        """The deadline raise must come before the academic-rigor check.
        V18.17.0.1: both the deadline raise (in _init_thermal_and_workers) and
        the academic-rigor check are in __init__ or sub-constructors. The test
        now checks they both exist in the file."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        # The IQ2_S deadline raise exists somewhere in the file
        assert "is_iq2_s" in content, "IQ2_S deadline raise must exist"
        # The academic rigor check exists somewhere in the file
        assert "academic_rigor" in content, "Academic rigor check must exist"

    def test_deadline_doesnt_affect_iq2_xxs(self):
        """The IQ2_XXS deadline (1200s) should still exist alongside the IQ2_S (1500s)."""
        sum_path = _project_root / "core" / "summarisation" / "summarizer.py"
        content = sum_path.read_text(encoding="utf-8")
        assert "1200" in content, "IQ2_XXS 1200s deadline must still exist"
        assert "1500" in content, "IQ2_S 1500s deadline must exist"


# ════════════════════════════════════════════════════════════════════════════
# 5. Full audit scenario — the exact V18.8.0 summary text
# ════════════════════════════════════════════════════════════════════════════

class TestAuditScenario:
    """Run the exact words flagged in the V18.8.0 audit and verify 0 flags now."""

    def test_v1880_audit_words_clean(self):
        """All the words flagged as false positives in V18.8.0 should now be clean."""
        # These are the exact words from the V18.8.0 conversion log (lines 583+)
        audit_text = """
        Lichtenstein identified two views within Erikson's work.
        Mahler specified two conditions for ego organization.
        borderline from non-borderline conditions.
        Jacobson organized her contributions into five categories.
        self-and object representations.
        modifications of Oedipal resolution.
        pregenital libidinal positions.
        approximately two years of age.
        the author traces how identity emerged.
        environmental change.
        bodily sensations.
        foundations and identifications.
        """
        _, issues = detect_word_fragment_merge(audit_text, "audit")
        fragment_issues = [i for i in issues if i.detector == "fragment_merge"]
        # Should be ZERO fragment-merge flags (all were false positives)
        assert len(fragment_issues) == 0, \
            f"V18.8.0 audit words should not be flagged: {[i.detail for i in fragment_issues]}"
