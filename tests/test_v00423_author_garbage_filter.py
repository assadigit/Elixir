"""V0.4.23 (audit V0.4.22, backlog #1): the author-name garbage filter.

Regression vectors are the V0.4.22 ch.4 run's four garbage families:
month names (the fabricated "May" bullet, H1), mirrored-table OCR
strings matched via UNICODE digits ("BIOA 0۲۲۶", "Tey ۸۶8۵"), the
implausible-year capture ("JOQuUI 8225"), and acronym/shape garbage
("DSM-III (1980)" flagged as name corruption at ship time).
"""

from __future__ import annotations

import pytest

from core.preprocessing.author_garbage import (
    MONTHS,
    garbage_author_reason,
    is_plausible_author,
)


class TestGarbageAuthorReason:
    def test_months_are_garbage(self):
        for m in ("May", "December", "March", "January", "Sept"):
            assert garbage_author_reason(m) is not None, m
            assert garbage_author_reason(f"{m} 1975") is not None, m

    def test_mirrored_table_shapes(self):
        assert "all-caps" in (garbage_author_reason("BIOA") or "")
        assert "mixed-case" in (garbage_author_reason("JOQuUI") or "")
        assert "mixed-case" in (garbage_author_reason("aTQNJ") or "")
        assert "embedded digit" in (garbage_author_reason("JeuoNes0A") or "")
        assert "non-Latin" in (garbage_author_reason("S1ay}O") or "")

    def test_real_surnames_are_plausible(self):
        for name in ("Knight", "Masterson", "Grinker", "Perry and Klerman", "van der Waerden"):
            assert is_plausible_author(name), name

    def test_particle_shapes_survive(self):
        for name in ("McElroy", "O'Brien", "DeVries", "VanDyke", "MacMillan"):
            assert is_plausible_author(name), name

    def test_synthetic_author_letters_survive(self):
        """The AuthorA/AuthorB fixture class (one trailing capital) must NOT
        be flagged (uppercase-minority shape is a legitimate surname)."""
        for name in ("AuthorA", "AuthorB", "AuthorZ"):
            assert is_plausible_author(name), name

    def test_typographic_dash_compounds_survive(self):
        for dash in ("-", "\u2013", "\u2014"):
            assert is_plausible_author(f"Aaa{dash}Aaa"), dash

    def test_implausible_year_opt_in(self):
        # extraction-time (default): shape-faithful — the year is not checked
        assert garbage_author_reason("Jones", "8225") is None
        # summary-side (opt-in): the year IS checked
        assert "implausible year" in (garbage_author_reason("Jones", "8225", check_year=True) or "")
        assert garbage_author_reason("Jones", "1983", check_year=True) is None

    def test_empty_and_never_raises(self):
        assert garbage_author_reason("") == "empty"
        assert garbage_author_reason(None) == "empty"  # type: ignore[arg-type]
        # a month as SECOND token (multi-word) — first token rules
        assert garbage_author_reason("van May") is None


class TestExtractCitationsRootFilter:
    """The V0.4.22 ch.4 mirrored-table vectors, end to end."""

    SRC = (
        "Intro text mentioning real work by Knight (1953) and Masterson (1972).\n"
        "TABLE 4-1. Clinical Features\n"
        "010331 TeUOT}BIOA 0\u06f2\u06f2\u06f6 8 \u0645\u0646\u0648\u062f }0 2010828066 25108 21\u06f2\u06f88112\n"
        "\u200euPPAO], 2S0Y} \u06f5\u06f80] JO INO [Tey \u06f8\u06f68\u06f5 ueD\n"
        "JOQuUI 8225/48 SNOIZYOI 31\u06f40800 \u06f2\u06f2\n"
        "In May 1954 the first congress met; by December 1955 it had grown.\n"
        "Real analysis continues with Grinker et al. (1968) and Kernberg (1975a).\n"
    )

    def test_garbage_never_extracted(self):
        from core.preprocessing.deterministic_analyzer import extract_citations

        names = [c["author"] for c in extract_citations(self.SRC)]
        for bad in ("May", "December", "BIOA", "Tey", "JOQuUI"):
            assert bad not in names, bad

    def test_real_authors_survive(self):
        from core.preprocessing.deterministic_analyzer import extract_citations

        names = [c["author"] for c in extract_citations(self.SRC)]
        for good in ("Knight", "Masterson", "Grinker", "Kernberg"):
            assert good in names, good

    def test_ledger_records_the_drops(self):
        import core.preprocessing.deterministic_analyzer as da

        da.extract_citations(self.SRC)
        ledger = da._LAST_GARBAGE_DROPPED
        dropped_names = [a for a, _r in ledger]
        assert "May" in dropped_names
        assert "December" in dropped_names
        assert "JOQuUI" in dropped_names

    def test_analysis_report_prints_garbage_line(self):
        import core.preprocessing.deterministic_analyzer as da

        text = self.SRC + ("Supporting prose. " * 40)
        report = da.run_deterministic_analysis(text)
        assert "Garbage-filtered author candidates:" in report
        assert "month name" in report

    def test_unicode_digit_years_never_match(self):
        """The ROOT fix: citation years are ASCII-only — Python's \\d matches
        Arabic-Indic digits, which let 'BIOA 0۲۲۶' pass as a citation."""
        from core.preprocessing.deterministic_analyzer import extract_citations

        cits = extract_citations("BIOA 0\u06f2\u06f2\u06f6 8 mirrored garbage row\n")
        assert cits == []

    def test_roundtrip_years_still_extract_verbatim(self):
        from core.preprocessing.deterministic_analyzer import extract_citations

        cits = extract_citations("Smith (1000) wrote early.")
        assert cits == [{"author": "Smith", "years": "1000", "type": "parenthetical"}]


class TestValidateYearsExemptions:
    """The summary-side mirror: 'May (1980)' / 'DSM-III (1980)' / the
    text-quoted-name false positive (the Prichard-class flag)."""

    def test_month_citation_not_flagged_as_corruption(self):
        from core.summarisation.postchecks.attribution import validate_years

        _text, issues = validate_years(
            "The term appeared in May (1980) according to the chronology.",
            "exec",
            source_authors=["Knight", "Masterson"],
        )
        assert not [i for i in issues if "name corruption" in i.detail]

    def test_all_caps_acronym_not_flagged(self):
        from core.summarisation.postchecks.attribution import validate_years

        _text, issues = validate_years(
            "The diagnosis shifted after DSM-III (1980) redefined the criteria.",
            "exec",
            source_authors=["Knight", "Masterson"],
        )
        assert not [i for i in issues if "name corruption" in i.detail]

    def test_text_quoted_name_exempt_via_source_text(self):
        """A name quoted IN the chapter prose (but not in the citation list)
        is not name corruption — presence in the source is grounding."""
        from core.summarisation.postchecks.attribution import validate_years

        source = (
            "The early alienists, as quoted in Mack (1975), included "
            "Prichard among the moral physicians of the 1830s."
        )
        _text, issues = validate_years(
            "Prichard (1835) is quoted as a historical source.",
            "exec",
            source_authors=["Mack"],
            source_text=source,
        )
        assert not [i for i in issues if "name corruption" in i.detail]

    def test_true_corruption_still_flagged(self):
        from core.summarisation.postchecks.attribution import validate_years

        source = "Knight (1953) described the borderline group of patients."
        _text, issues = validate_years(
            "Dukhaim (1951) wrote about borderline patients.",
            "exec",
            source_authors=["Knight"],
            source_text=source,
        )
        flagged = [i for i in issues if "name corruption" in i.detail]
        assert flagged, "the real corruption vector must still be flagged"


@pytest.mark.parametrize("month", sorted(MONTHS))
def test_every_month_is_garbage(month):
    assert garbage_author_reason(month.capitalize()) is not None
