"""V0.5.18 — citation-run roster capture + the author-year consistency check.

Two ch.9-audit findings, one file (both live in the citation layer):

1. **MEDIUM (the roster gap)** — ``extract_citations`` missed:
   - PARENTHETICAL CITATION RUNS: ``(A et al. 1968, 1975, B et al. 1968,
     1971, C et al. 1974)`` — comma/semicolon enumerations of name+years
     inside one paren pair. Patterns 1-5 require per-name paren years or a
     single bare-name-year, so co-cited authors vanished from the roster
     every author-coverage veto judges against (→ NEW Pattern 6).
   - POSSESSIVE MULTI-YEAR LETTER SUFFIXES: ``A's (1921,\\n1924a,b)`` —
     the trailing comma-letter run broke Pattern 1's years group (→ the
     group now tolerates a trailing ``(?:,s*,s*[a-z])*`` run).

2. **E2 (the cross-field year slip)** — ``validate_years`` check 3: a
   KNOWN source author cited with a year that is neither in the roster's
   author→years set NOR citation-shaped-adjacent to the name in the raw
   source (``Name[^\\d]{0,48}?year`` — an intervening digit blocks false
   long-range joins across adjacent citations). The summary-side citation
   regex also now sees the markdown/comma shapes the shipped bullets use
   ("A et al., 1984" / "B *1987*").

Content-agnostic (Rule 1): synthetic Authorone/... fixtures.

Run: ``pytest tests/test_v0518_citation_runs_year_consistency.py -v``
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.preprocessing.deterministic_analyzer import extract_citations
from core.summarisation.postchecks.attribution import (
    _SUMMARY_CITATION_RE,
    validate_years,
)


def _authors(text: str) -> dict[str, list[str]]:
    return {c["author"]: c["years"] for c in extract_citations(text)}


# ── Pattern 6: parenthetical citation runs ──────────────────────────────────


def test_citation_run_three_names_all_captured():
    text = (
        "The adoptive studies (Authorone et al. 1968, 1975, Authortwo et al. "
        "1968, 1971, Authorthree et al. 1974) further highlighted the syndrome."
    )
    got = _authors(text)
    assert "Authorone" in got and "1968" in got["Authorone"] and "1975" in got["Authorone"]
    assert "Authortwo" in got and "1971" in got["Authortwo"]
    assert "Authorthree" in got and "1974" in got["Authorthree"]


def test_citation_run_plain_names_no_et_al():
    text = "The label debate (Authorx 1980, Authoret et al. 1980, Authorzet et al. 1988) continued."
    got = _authors(text)
    assert "Authorx" in got and got["Authorx"] == "1980"
    assert "Authoret" in got and got["Authoret"] == "1980"
    assert "Authorzet" in got and got["Authorzet"] == "1988"


def test_citation_run_single_item():
    text = "The genetic studies (Authorone et al. 1968, 1975) shaped the criteria."
    got = _authors(text)
    assert "Authorone" in got
    assert "1968" in got["Authorone"] and "1975" in got["Authorone"]


def test_citation_run_semicolon_separator():
    text = "Earlier reviews (Authorx 1970; Authoret 1971) disagreed."
    got = _authors(text)
    assert "Authoret" in got and got["Authoret"] == "1971"


def test_citation_run_fp_guards():
    # "(In 1965)" — a discourse marker, not a citation run
    got = _authors("The era changed (In 1965, Authorx 1970) for the field.")
    assert "In" not in got
    assert "Authorx" in got
    # lowercase lead-ins never match the item shape
    got2 = _authors("As noted (see Authorx 1970; cf. Authoret 1971) the field moved.")
    assert "see" not in got2 and "cf" not in got2


def test_citation_run_possessive_item():
    text = "Authorone's (1921,\n1924a,b) early papers on the topic remain foundational."
    got = _authors(text)
    assert "Authorone" in got
    years = {y.strip() for y in got["Authorone"].replace("\n", " ").split(",")}
    assert "1921" in years and "1924a" in years


# ── the summary-side citation regex: markdown/comma joins (E2) ───────────────


def test_summary_citation_re_sees_comma_and_italic_forms():
    m = _SUMMARY_CITATION_RE.search("more common in women (Authoret et al., 1984, Authorzet 1987).")
    assert m and m.group(1) == "Authoret et al." and m.group(2) == "1984"
    m2 = _SUMMARY_CITATION_RE.search("Authorzet *1987* corroborated.")
    assert m2 and m2.group(1) == "Authorzet" and m2.group(2) == "1987"
    m3 = _SUMMARY_CITATION_RE.search("Authorzet (*1985a*, *1983*) clarified.")
    assert m3 and m3.group(2) == "1985a"
    # the legacy shapes still match
    m4 = _SUMMARY_CITATION_RE.search("Authorzet (1987) clarified.")
    assert m4 and m4.group(2) == "1987"
    m5 = _SUMMARY_CITATION_RE.search("Authoret's 1986 review.")
    assert m5 and m5.group(1) == "Authoret's" and m5.group(2) == "1986"


# ── validate_years check 3: author-year consistency ──────────────────────────

_SRC = (
    "Authorone et al. (1970) described the framework.\n"
    "Authortwo (1986, Reich 1987) found the difference.\n"
    "Authorthree and Authorfour (1921,\n1924a,b) wrote the early papers.\n"
    "The men-citation (Authorfive 1989a, Authorsix et al. 1984, Authorseven 1987) "
    "and the women-citation (Authortwo et al. 1986) differ."
)

_ROSTER = ["Authorone", "Authortwo", "Authorthree", "Authorfour", "Authorfive", "Authorsix", "Authorseven"]


def _consistency_flags(text: str) -> list[str]:
    _, issues = validate_years(text, "bullet[0]", _ROSTER, _SRC)
    return [i.detail for i in issues if "consistency" in i.detail or "cites this author with" in i.detail]


def test_cross_field_year_slip_flagged():
    """The E2 shape: a KNOWN author cited with the ADJACENT citation's year."""
    flags = _consistency_flags(
        "The disorders occur more often in women (Authortwo et al., 1984, Authorseven 1987)."
    )
    assert any("Authortwo" in f and "1984" in f for f in flags), flags
    # Authorseven 1987 is faithful — not flagged
    assert not any("Authorseven" in f for f in flags), flags


def test_faithful_years_not_flagged():
    assert _consistency_flags("Authortwo et al. (1986) found the difference.") == []
    assert _consistency_flags("Authorone et al. (1970) described the framework.") == []
    # letter-suffix base-year tolerance: 1924b vs the roster's 1924a
    assert _consistency_flags("Authorthree and Authorfour (1924b) wrote the early papers.") == []


def test_prose_adjacency_exemption():
    """A year the roster build missed but the source genuinely pairs with
    the name in prose (citation-shaped window) is NOT flagged."""
    src = _SRC + "\nAuthoreight (1970) formalized it. Authoreight noted in 1984 that the pattern held."
    _, issues = validate_years(
        "Authoreight (1984) noted the pattern.", "bullet[0]", _ROSTER + ["Authoreight"], src
    )
    flags = [i.detail for i in issues if "cites this author with" in i.detail]
    assert not any("Authoreight" in f for f in flags), flags


def test_unknown_author_skips_consistency():
    """Check 3 only judges KNOWN roster authors (unknown names are check 2's
    domain)."""
    flags = _consistency_flags("Authornine (1234) fabricated a year.")
    assert not any("Authornine" in f and "cites this author with" in f for f in flags)


def test_stopword_shapes_never_consistency_flagged():
    assert _consistency_flags("His (1986) framework held.") == []
    assert _consistency_flags("In (1965) the field changed.") == []
