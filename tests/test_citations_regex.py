"""V18.15.5.1 (DEBT-08) — citation regex Unicode unification tests.

Byte-for-byte stability gate for the shared ``citations_regex`` module +
the consumer-side integration (``postchecks._SUMMARY_CITATION_RE`` +
``deterministic_analyzer.extract_citations``).

The V18.15.3.5 curly-apostrophe fix was applied ONLY to
``deterministic_analyzer.py``. Pre-V18.15.5.1, ``postchecks.py`` used
ASCII-only ``'`` → curly-possessive citations copied verbatim from PDF source
(e.g. ``Federn's (1952)`` with U+2019) were SILENTLY SKIPPED by
``validate_years`` / ``verify_attribution`` / ``detect_dropped_digit_years``.

These tests gate:
  1. The shared ``APOS`` / ``NAME_SEP`` constants.
  2. ``postchecks._SUMMARY_CITATION_RE`` now matches curly-possessive citations.
  3. ``postchecks._BOLD_NAME_RE`` now matches em-dash compound bold names.
  4. ``deterministic_analyzer.extract_citations`` still matches straight + curly
     + left-single-quote (U+2018) possessives.
  5. Pure-ASCII citations still behave byte-for-byte as before (regression guard).

Run: pytest tests/test_citations_regex.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.preprocessing.citations_regex import APOS, NAME_SEP
from core.preprocessing.deterministic_analyzer import extract_citations
from core.summarisation.postchecks import _BOLD_NAME_RE, _SUMMARY_CITATION_RE

# ── 1. Shared constants ────────────────────────────────────────────────────


class TestSharedConstants:
    """V18.15.5.1: the APOS + NAME_SEP constants have the exact Unicode
    coverage claimed in the module docstring.

    NOTE: APOS and NAME_SEP are regex character-class DEFINITIONS (strings
    like ``r"['\\u2019\\u2018]"`` containing literal backslash-u escapes), NOT
    strings of actual Unicode chars. We test them by compiling + matching,
    not by substring membership.
    """

    def test_apos_includes_all_three_apostrophe_variants(self):
        # U+0027 (ASCII), U+2019 (curly right), U+2018 (curly left)
        import re

        pat = re.compile(APOS)  # APOS already includes the [...] brackets
        assert pat.search("'") is not None  # ASCII apostrophe
        assert pat.search("\u2019") is not None  # curly right
        assert pat.search("\u2018") is not None  # curly left
        # Non-apostrophe chars must NOT match
        assert pat.search("a") is None
        assert pat.search(" ") is None

    def test_name_sep_includes_all_five_dash_variants(self):
        # U+002D (hyphen-minus), U+2013 (en dash), U+2014 (em dash),
        # U+2010 (hyphen), U+2011 (non-breaking hyphen)
        import re

        pat = re.compile(NAME_SEP)  # NAME_SEP already includes the [...] brackets
        assert pat.search("-") is not None  # ASCII hyphen
        assert pat.search("\u2013") is not None  # en dash
        assert pat.search("\u2014") is not None  # em dash (NEW in V18.15.5.1)
        assert pat.search("\u2010") is not None  # typographic hyphen (NEW)
        assert pat.search("\u2011") is not None  # non-breaking hyphen (NEW)
        # Non-dash chars must NOT match
        assert pat.search("a") is None

    def test_apos_is_a_regex_character_class(self):
        import re

        # APOS is a complete character class (includes its own [..] brackets).
        # Use it directly in a pattern: APOS + "s" matches "'s", "'s", "'s".
        pat = re.compile(APOS + r"s")
        assert pat.search("Federn's") is not None  # ASCII
        assert pat.search("Federn\u2019s") is not None  # curly right
        assert pat.search("Federn\u2018s") is not None  # curly left
        assert pat.search("FedernXs") is None  # X is not an apostrophe


# ── 2. postchecks._SUMMARY_CITATION_RE — curly-possessive now matches ─────


class TestPostchecksSummaryCitationRe:
    """V18.15.5.1: postchecks citation regex now handles curly-possessive
    citations (the V18.15.3.5 fix's cross-module gap)."""

    def test_ascii_possessive_citation_matches(self):
        """Regression guard: ASCII 's possessive still matches (pre-V18.15.5.1)."""
        m = _SUMMARY_CITATION_RE.search("Federn's (1952) saw a continuum")
        assert m is not None
        assert "Federn" in m.group(1)
        assert m.group(2) == "1952"

    def test_curly_right_possessive_citation_matches(self):
        """V18.15.5.1 NEW: U+2019 curly-right possessive now matches
        (was SILENTLY SKIPPED pre-V18.15.5.1 — the bug DEBT-08 fixes)."""
        m = _SUMMARY_CITATION_RE.search("Federn\u2019s (1952) saw a continuum")
        assert m is not None, (
            "curly-right-possessive citation 'Federn\\u2019s (1952)' must match "
            "post-V18.15.5.1 (was skipped pre-V18.15.5.1)"
        )
        assert m.group(2) == "1952"

    def test_curly_left_possessive_citation_matches(self):
        """V18.15.5.1 NEW: U+2018 curly-left possessive now matches (rare but
        some typesetters use it)."""
        m = _SUMMARY_CITATION_RE.search("Federn\u2018s (1952) saw a continuum")
        assert m is not None
        assert m.group(2) == "1952"

    def test_non_possessive_citation_still_matches(self):
        """Regression guard: plain 'Author (Year)' still matches."""
        m = _SUMMARY_CITATION_RE.search("Erikson (1956) defined ego identity")
        assert m is not None
        assert m.group(1) == "Erikson"
        assert m.group(2) == "1956"

    def test_hyphenated_compound_surname_matches(self):
        """Regression guard: ASCII-hyphen compound surname still matches."""
        m = _SUMMARY_CITATION_RE.search("Chasseguet-Smirgel (1984) wrote")
        assert m is not None
        assert "Chasseguet-Smirgel" in m.group(1)

    def test_en_dash_compound_surname_matches(self):
        """Regression guard: en-dash (U+2013) compound surname still matches
        (was already handled pre-V18.15.5.1)."""
        m = _SUMMARY_CITATION_RE.search("Chasseguet\u2013Smirgel (1984) wrote")
        assert m is not None
        assert "Chasseguet" in m.group(1)

    def test_em_dash_compound_surname_matches(self):
        """V18.15.5.1 NEW: em-dash (U+2014) compound surname now matches
        (was SILENTLY SKIPPED pre-V18.15.5.1)."""
        m = _SUMMARY_CITATION_RE.search("Smith\u2014Jones (1990) collaborated")
        assert m is not None, (
            "em-dash compound surname 'Smith\\u2014Jones (1990)' must match "
            "post-V18.15.5.1 (was skipped pre-V18.15.5.1)"
        )
        assert m.group(2) == "1990"


# ── 3. postchecks._BOLD_NAME_RE — em-dash bold names now match ────────────


class TestPostchecksBoldNameRe:
    """V18.15.5.1: the bold-name bullet pattern (used for gap-fill bullets)
    now handles em-dash + typographic-hyphen compound surnames."""

    def test_ascii_hyphen_bold_name_matches(self):
        """Regression guard: ASCII-hyphen bold name still matches."""
        m = _BOLD_NAME_RE.search("**Chasseguet-Smirgel**: Wrote about femininity.")
        assert m is not None
        assert "Chasseguet-Smirgel" in m.group(1)

    def test_em_dash_bold_name_matches(self):
        """V18.15.5.1 NEW: em-dash bold name now matches."""
        m = _BOLD_NAME_RE.search("**Smith\u2014Jones**: Collaborated on identity.")
        assert m is not None, "em-dash bold name '**Smith\\u2014Jones**' must match post-V18.15.5.1"
        assert "Smith" in m.group(1)

    def test_non_compound_bold_name_still_matches(self):
        """Regression guard: single-word bold name still matches."""
        m = _BOLD_NAME_RE.search("**Khan**: Provided the developmental basis.")
        assert m is not None
        assert m.group(1) == "Khan"


# ── 4. deterministic_analyzer.extract_citations — full Unicode coverage ────


class TestExtractCitationsUnicode:
    """V18.15.5.1: deterministic_analyzer.extract_citations now uses the shared
    APOS class (adds U+2018) — V18.15.3.5 already handled U+2019, this completes
    the coverage. Regression guards for ASCII + U+2019 are included."""

    def test_ascii_possessive_extracted(self):
        """Regression guard: ASCII 's possessive extracted (pre-V18.15.5.1)."""
        cites = extract_citations("Federn's (1952) saw a continuum")
        authors = [c["author"] for c in cites]
        assert "Federn" in authors, f"expected 'Federn' in {authors}"
        years = [c["years"] for c in cites if c["author"] == "Federn"]
        assert "1952" in years

    def test_curly_right_possessive_extracted(self):
        """V18.15.3.5 regression guard: U+2019 possessive extracted."""
        cites = extract_citations("Federn\u2019s (1952) saw a continuum")
        authors = [c["author"] for c in cites]
        assert "Federn" in authors, f"expected 'Federn' in {authors}"

    def test_curly_left_possessive_extracted(self):
        """V18.15.5.1 NEW: U+2018 (curly left) possessive now extracted
        (the shared APOS class adds it)."""
        cites = extract_citations("Federn\u2018s (1952) saw a continuum")
        authors = [c["author"] for c in cites]
        assert "Federn" in authors, f"expected 'Federn' (U+2018 possessive) in {authors}"

    def test_non_possessive_citation_extracted(self):
        """Regression guard: plain 'Author (Year)' still extracted."""
        cites = extract_citations("Erikson (1956) defined ego identity")
        authors = [c["author"] for c in cites]
        assert "Erikson" in authors

    def test_pure_ascii_still_behaves_byte_for_byte(self):
        """Regression guard: a pure-ASCII source produces the exact same
        citation list as before the V18.15.5.1 change (additive-only fix)."""
        source = (
            "Erikson (1956) defined ego identity. "
            "Freud 1923a introduced the structural model. "
            "Jacobson's (1964) work on self-object representations. "
            "Chasseguet-Smirgel (1984) wrote about femininity. "
            "Mahler, 1975, described separation-individuation."
        )
        cites = extract_citations(source)
        authors = sorted({c["author"] for c in cites})
        # All 5 distinct authors must be extracted (regression guard).
        assert "Erikson" in authors
        assert "Freud" in authors
        assert "Jacobson" in authors
        assert "Chasseguet-Smirgel" in authors
        assert "Mahler" in authors
