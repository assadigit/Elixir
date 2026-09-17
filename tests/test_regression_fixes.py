"""V18.2.28 (regression fix) — Tests for dropped-digit year + pronoun auto-fix."""
from __future__ import annotations

from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.postchecks import detect_dropped_digit_years, detect_pronoun_mismatch


class TestDroppedDigitYears:
    def test_kovel_181_fixed_to_1981(self):
        """The exact V18.2.27 bug: 'Kovel (181)' → 'Kovel (1981)'."""
        source = "Fromm (1955), Wheelis (1958), and Kovel (1981) contributed."
        summary = "Fromm (1955), Wheelis (1958), and Kovel (181) contributed."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert "Kovel (1981)" in cleaned
        assert "Kovel (181)" not in cleaned
        assert len(issues) == 1
        assert issues[0].severity == "fix"
        assert "dropped-digit" in issues[0].detail

    def test_extra_digit_fixed(self):
        """'19881' doesn't match the year regex (5 digits) — test with a
        4-digit extra-digit case instead: '189' vs '1989'."""
        source = "Erikson (1989) described identity."
        summary = "Erikson (189) described identity formation."
        cleaned, issues = detect_dropped_digit_years(summary, source, "thorough")
        assert "Erikson (189)" not in cleaned
        assert "Erikson (1989)" in cleaned

    def test_correct_year_not_changed(self):
        source = "Erikson (1959) described identity."
        summary = "Erikson (1959) described identity formation."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert cleaned == summary
        assert issues == []

    def test_author_not_in_source_no_fix(self):
        source = "Erikson (1959) described identity."
        summary = "UnknownAuthor (181) wrote something."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert "UnknownAuthor (181)" in cleaned  # unchanged
        assert issues == []

    def test_empty_inputs(self):
        assert detect_dropped_digit_years("", "source", "exec") == ("", [])
        assert detect_dropped_digit_years("summary", "", "exec")[1] == []

    def test_book_agnostic_works_on_any_discipline(self):
        source = "Darwin (1859) proposed natural selection."
        summary = "Darwin (159) proposed natural selection."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert "Darwin (1859)" in cleaned
        assert len(issues) == 1

    def test_hyphenated_surname(self):
        source = "Chasseguet-Smirgel (1983) described the long path."
        summary = "Chasseguet-Smirgel (183) described the long path."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert "Chasseguet-Smirgel (1983)" in cleaned
        assert len(issues) == 1

    def test_multiple_dropped_digits_in_one_text(self):
        source = "Erikson (1959) and Kernberg (1967) contributed."
        summary = "Erikson (159) and Kernberg (167) contributed."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert "Erikson (1959)" in cleaned
        assert "Kernberg (1967)" in cleaned
        assert len(issues) == 2

    def test_year_with_letter_suffix(self):
        """'1980b' should match '1980b' — no false positive."""
        source = "Kernberg (1980b) described middle age."
        summary = "Kernberg (1980b) described middle age."
        cleaned, issues = detect_dropped_digit_years(summary, source, "exec")
        assert issues == []
        assert cleaned == summary


class TestPronounAutoFix:
    """V18.2.19/V18.2.28 pronoun-mismatch characterization.

    V18.20.3.1 (real-rig audit D2): the V18.2.28 auto-fix re.sub was DEAD
    CODE — every production call site discards the returned text
    (``_, issues = detect_pronoun_mismatch(...)`` in postchecks.py) while
    the Issue detail claimed "Auto-fixed". The fix block is removed; the
    detector is honestly flag-only (matching its original docstring).
    These tests now pin the NEW contract: text unchanged + severity
    "flag" + no "Auto-fixed" claim."""

    def test_greenacre_he_flagged_not_rewritten(self):
        """The exact V18.2.27 bug case: 'Greenacre... He' vs source 'She' →
        flagged, text returned UNCHANGED (the auto-fix was dead code)."""
        source = "Greenacre (1958) proposed a continuum. She emphasized vision."
        summary = "Greenacre (1958) proposed a continuum. He emphasized vision."
        cleaned, issues = detect_pronoun_mismatch(summary, source, "thorough")
        assert cleaned == summary  # V18.20.3.1: flag-only — never rewritten
        assert len(issues) == 1
        assert issues[0].severity == "flag"
        assert "Auto-fixed" not in issues[0].detail
        assert "she" in issues[0].detail  # names the source pronoun for review

    def test_matching_pronoun_no_fix(self):
        source = "Darwin (1859) proposed selection. He wrote extensively."
        summary = "Darwin (1859) proposed selection. He wrote extensively."
        cleaned, issues = detect_pronoun_mismatch(summary, source, "exec")
        assert issues == []  # matching pronoun → no issue

    def test_his_to_her_flagged_not_rewritten(self):
        source = "Mahler (1958) described separation. Her work was influential."
        summary = "Mahler (1958) described separation. His work was influential."
        cleaned, issues = detect_pronoun_mismatch(summary, source, "thorough")
        assert cleaned == summary  # V18.20.3.1: flag-only
        assert len(issues) == 1
        assert issues[0].severity == "flag"
        assert "Auto-fixed" not in issues[0].detail

    def test_same_gender_different_form_no_fix(self):
        """'he' vs 'his' — same gender, different form → no issue."""
        source = "Erikson (1959) described identity. He was influential."
        summary = "Erikson (1959) described identity. His work was influential."
        cleaned, issues = detect_pronoun_mismatch(summary, source, "exec")
        # Both masculine → no gender mismatch → no fix
        assert issues == []

    def test_empty_inputs(self):
        assert detect_pronoun_mismatch("", "source", "exec")[1] == []
        assert detect_pronoun_mismatch("summary", "", "exec")[1] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
