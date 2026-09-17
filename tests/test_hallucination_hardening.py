"""V18.2.25 (Phase 4.3) — Tests for hallucination hardening postchecks.

Covers:
1. detect_exec_bullet_inconsistency: exec author not in bullets → flag
2. detect_exec_bullet_inconsistency: all exec authors in bullets → no issue
3. detect_exec_bullet_inconsistency: empty inputs → no issue
4. detect_exec_bullet_inconsistency: hyphenated surnames
5. detect_citation_coverage_gap: <80% coverage → flag with missing names
6. detect_citation_coverage_gap: ≥80% coverage → no issue
7. detect_citation_coverage_gap: too few source authors → skip
8. detect_citation_coverage_gap: empty inputs → no issue
9. Book-agnostic: works on any discipline
"""
from __future__ import annotations

from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.postchecks import (
    detect_citation_coverage_gap,
    detect_exec_bullet_inconsistency,
)


class TestExecBulletInconsistency:
    def test_exec_author_not_in_bullets_flagged(self):
        """Exec mentions 'Freud (1923)' but no bullet does → flag."""
        exec_sum = "Freud (1923) described the structural model of the psyche."
        bullets = ["Erikson (1959) described identity formation across stages."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert len(issues) == 1
        assert issues[0].detector == "consistency"
        assert issues[0].severity == "flag"
        assert "freud" in issues[0].detail.lower()

    def test_all_exec_authors_in_bullets_no_issue(self):
        exec_sum = "Freud (1923) and Erikson (1959) both contributed."
        bullets = [
            "Freud (1923) described the id, ego, and superego.",
            "Erikson (1959) described eight stages of development.",
        ]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert issues == []

    def test_empty_exec_no_issue(self):
        issues = detect_exec_bullet_inconsistency("", ["bullet 1"])
        assert issues == []

    def test_empty_bullets_no_issue(self):
        issues = detect_exec_bullet_inconsistency("Freud (1923) wrote.", [])
        assert issues == []

    def test_hyphenated_surname_matched(self):
        """Chasseguet-Smirgel should match if either part appears in bullets."""
        exec_sum = "Chasseguet-Smirgel (1973) wrote about the ego."
        bullets = ["Chasseguet-Smirgel (1973) described ego ideal formation."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert issues == []  # author IS in bullets

    def test_hyphenated_surname_missing_flagged(self):
        exec_sum = "Chasseguet-Smirgel (1973) wrote about the ego."
        bullets = ["Kernberg (1975) described borderline personality."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert len(issues) == 1
        assert "chasseguet" in issues[0].detail.lower()

    def test_multiple_missing_authors(self):
        exec_sum = "Freud (1923), Erikson (1959), and Mahler (1968) contributed."
        bullets = ["Some other author wrote about stages."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert len(issues) == 3

    def test_book_agnostic_works_on_biology(self):
        exec_sum = "Darwin (1859) proposed natural selection."
        bullets = ["Mendel (1866) described genetic inheritance."]
        issues = detect_exec_bullet_inconsistency(exec_sum, bullets)
        assert len(issues) == 1
        assert "darwin" in issues[0].detail.lower()


class TestCitationCoverageGap:
    def test_low_coverage_flagged(self):
        """Source names 10 authors, summary mentions 2 → 20% < 80% → flag."""
        names = ["Adams", "Baker", "Clark", "Davis", "Evans", "Foster", "Green", "Harris", "Irwin", "Jones"]
        source = ". ".join([f"{n} ({1900+i}) wrote about topic {i}." for i, n in enumerate(names)])
        summary = "Adams (1910) wrote about topic 0. Baker (1920) discussed topic 1."
        issues = detect_citation_coverage_gap(source, summary)
        assert len(issues) == 1
        assert issues[0].detector == "citation_coverage"
        assert "coverage gap" in issues[0].detail.lower()
        assert "missing" in issues[0].detail.lower()

    def test_good_coverage_no_issue(self):
        """Source names 10 authors, summary mentions 9 → 90% ≥ 80% → no flag."""
        names = ["Adams", "Baker", "Clark", "Davis", "Evans", "Foster", "Green", "Harris", "Irwin", "Jones"]
        source = ". ".join([f"{n} ({1900+i}) wrote about topic {i}." for i, n in enumerate(names)])
        summary = ". ".join([f"{n} ({1900+i}) discussed topic {i}." for i, n in enumerate(names[:9])])
        issues = detect_citation_coverage_gap(source, summary)
        assert issues == []

    def test_too_few_authors_skipped(self):
        """Source names <5 authors → skip (not enough to enforce a floor)."""
        source = "Freud (1923) and Erikson (1959) both contributed."
        summary = "Some unrelated text."
        issues = detect_citation_coverage_gap(source, summary)
        assert issues == []

    def test_empty_source_no_issue(self):
        issues = detect_citation_coverage_gap("", "summary text")
        assert issues == []

    def test_empty_summary_no_issue(self):
        source = "Freud (1923) wrote. Erikson (1959) wrote. " * 3
        issues = detect_citation_coverage_gap(source, "")
        assert issues == []

    def test_custom_coverage_floor(self):
        """With a 100% floor, even 90% coverage should flag."""
        names = ["Adams", "Baker", "Clark", "Davis", "Evans", "Foster", "Green", "Harris", "Irwin", "Jones"]
        source = ". ".join([f"{n} ({1900+i}) wrote about topic {i}." for i, n in enumerate(names)])
        summary = ". ".join([f"{n} ({1900+i}) discussed topic {i}." for i, n in enumerate(names[:9])])
        # 9/10 = 90% → with floor=1.0, should flag
        issues = detect_citation_coverage_gap(source, summary, coverage_floor=1.0)
        assert len(issues) == 1

    def test_missing_authors_listed(self):
        """The flag should list the missing author names."""
        names = ["Adams", "Baker", "Clark", "Davis", "Evans", "Foster", "Green", "Harris", "Irwin", "Jones"]
        source = ". ".join([f"{n} ({1900+i}) wrote about topic {i}." for i, n in enumerate(names)])
        summary = "Only Adams (1910) is mentioned."
        issues = detect_citation_coverage_gap(source, summary)
        assert len(issues) == 1
        # The missing authors should be named in the detail
        assert "Baker" in issues[0].detail
        assert "Clark" in issues[0].detail

    def test_book_agnostic_works_on_physics(self):
        names = ["Newton", "Einstein", "Bohr", "Heisenberg", "Schrodinger", "Dirac", "Pauli", "Fermi", "Feynman", "GellMann"]
        source = ". ".join([f"{n} ({1900+i}) discovered law {i}." for i, n in enumerate(names)])
        summary = "Galileo (1600) described motion. Hubble (1920) described expansion."
        issues = detect_citation_coverage_gap(source, summary)
        # 0/10 source authors covered → flag
        assert len(issues) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
