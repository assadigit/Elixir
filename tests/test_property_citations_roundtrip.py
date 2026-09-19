"""Property-based tests: citation round-trips through the shared Unicode classes
(roadmap 2.2 — task 2.2 "Hypothesis property suites").

Targets ``core/preprocessing/citations_regex.py`` (the shared APOS / NAME_SEP
Unicode punctuation classes) and the extractors that embed them:
``core.summarisation.postcheck_detectors`` (``_SUMMARY_CITATION_RE``,
``_BOLD_NAME_RE``, ``_AUTHOR_RE``, ``_YEAR_IN_PARENS_RE``, ``_BARE_YEAR_RE``,
``validate_years``, ``detect_dropped_digit_years``) and
``core.preprocessing.deterministic_analyzer.extract_citations``.

Core property — ROUND-TRIP: build a citation string from generated components
(surname, optional compound separator, optional possessive apostrophe, year,
surrounding context), run the extractor, and recover the components exactly.

Additional invariants:

* DEBT-08 regression: citations using ANY apostrophe variant in APOS (ASCII,
  U+2019, U+2018) and ANY compound separator in NAME_SEP are extracted by the
  postcheck-side regex — never silently skipped.
* ``validate_years`` flags years outside [1800, MAX_YEAR] but ONLY within the
  1xxx/20xx/21xx token scope of ``_BARE_YEAR_RE`` (characterization: 9999
  and 2200 are invisible to the year check), never rewrites text, and flags
  ungrounded authors (fuzzy-safe gibberish names) while accepting grounded
  ones.
* ``detect_dropped_digit_years`` repairs any single dropped digit (year
  remains a subsequence of the source year) and is a fixpoint: applying it
  twice changes nothing.
* ``_snippet`` windows are bounded (<= width + 2 chars) and whitespace-
  collapsed; ``_is_subsequence`` is reflexive and rejects over-long shorts;
  ``PostCheckReport`` counts fix/flag issues exactly.

KNOWN BUG (documented, NOT fixed here — characterization test pins the
current behavior): ``deterministic_analyzer.extract_citations`` truncates
compound surnames whose separator is em-dash U+2014 / U+2010 / U+2011
("Smith—Jones (1983)" → author "Jones") because its own compound classes are
still ASCII ``[-\\u2013]`` — the DEBT-08 sharing of NAME_SEP was applied to
the postcheck-side regexes only.  See the module report in
worklog-P2-D.md.
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from core.preprocessing.citations_regex import APOS, NAME_SEP
from core.preprocessing.deterministic_analyzer import (
    _ENGLISH_FALSE_POSITIVES,
    extract_citations,
)
from core.summarisation.postcheck_detectors import (
    _AUTHOR_RE,
    _BARE_YEAR_RE,
    _BOLD_NAME_RE,
    _SUMMARY_CITATION_RE,
    _YEAR_IN_PARENS_RE,
    MAX_YEAR,
    MIN_YEAR,
    Issue,
    PostCheckReport,
    _is_subsequence,
    _snippet,
    detect_dropped_digit_years,
    validate_years,
)

# ── settings profiles ────────────────────────────────────────────────────────
S_FAST = settings(max_examples=100, deadline=None)
S_MED = settings(max_examples=40, deadline=None)

_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_LOWER = "abcdefghijkmnpqrstuvwxyz"
_APOS_CHARS = ["'", "\u2019", "\u2018"]  # the APOS class, expanded
_NAME_SEP_CHARS = ["-", "\u2013", "\u2014", "\u2010", "\u2011"]  # the NAME_SEP class

# Names that can never fuzzy-match (rapidfuzz token_set_ratio < 82) the
# grounded author pool used below.
_IMPOSSIBLE_AUTHORS = ["Qzvx", "Xkqj", "Vvwq", "Zzqx", "Wvkj", "Jxqz"]
_GROUNDED_AUTHORS = ["Freud", "Jung", "Erikson", "Marcia", "Federn"]


@st.composite
def _surname(draw):
    name = draw(st.sampled_from(_UPPER)) + draw(st.text(alphabet=_LOWER, min_size=2, max_size=9))
    # never collide with the extractor's English stopword list ("The", "In"…)
    return name if name not in _ENGLISH_FALSE_POSITIVES else name + "q"


@st.composite
def _citation_name(draw):
    """A surname, optionally compound (any NAME_SEP char), optionally
    possessive (any APOS char + optional s/S)."""
    name = draw(_surname())
    if draw(st.booleans()):
        sep = draw(st.sampled_from(_NAME_SEP_CHARS))
        name = name + sep + draw(_surname())
    poss = draw(
        st.sampled_from(["", *[apos + opt for apos in _APOS_CHARS for opt in ("", "s", "S")]])
    )
    return name + poss


@st.composite
def _year_token(draw, min_value=1000, max_value=2999):
    y = draw(st.integers(min_value=min_value, max_value=max_value))
    suffix = draw(st.sampled_from(["", "a", "b", "z"]))
    return f"{y:04d}{suffix}"


@st.composite
def _context(draw):
    """Lowercase prose context — can never start a citation match itself."""
    return draw(st.text(alphabet=_LOWER + " ,.", min_size=0, max_size=24))


# ═══════════════════════════════════════════════════════════════════════════
# _SUMMARY_CITATION_RE round-trips
# ═══════════════════════════════════════════════════════════════════════════


@S_MED
@given(name=_citation_name(), year=_year_token(), lead=_context(), trail=_context())
def test_summary_citation_roundtrip_parenthesized(name, year, lead, trail):
    """``<ctx> Name's (1952a) <ctx>`` → the extractor recovers (name, year)."""
    text = f"{lead} {name} ({year}) {trail}".strip()
    matches = _SUMMARY_CITATION_RE.findall(text)
    assert matches, f"citation not found in {text!r}"
    assert matches[0] == (name, year)


@S_MED
@given(name=_citation_name(), year=_year_token(), lead=_context(), trail=_context())
def test_summary_citation_roundtrip_inline(name, year, lead, trail):
    """``<ctx> Name's 1952a. <ctx>`` (no parens) → (name, year) recovered."""
    text = f"{lead} {name} {year}. {trail}".strip()
    matches = _SUMMARY_CITATION_RE.findall(text)
    assert matches
    assert matches[0] == (name, year)


@S_FAST
@given(apos=st.sampled_from(_APOS_CHARS), surname=_surname(), year=_year_token())
def test_every_apos_variant_is_extracted(apos, surname, year):
    """DEBT-08 regression: curly/straight apostrophes are never skipped."""
    for poss in ("", "s", "S"):
        text = f"{surname}{apos}{poss} ({year})"
        matches = _SUMMARY_CITATION_RE.findall(text)
        assert matches and matches[0][0] == f"{surname}{apos}{poss}"
        assert matches[0][1] == year


@S_FAST
@given(sep=st.sampled_from(_NAME_SEP_CHARS), a=_surname(), b=_surname(), year=_year_token())
def test_every_name_sep_variant_is_extracted(sep, a, b, year):
    """DEBT-08 regression: every Unicode dash in NAME_SEP is honoured."""
    text = f"{a}{sep}{b} ({year})"
    matches = _SUMMARY_CITATION_RE.findall(text)
    assert matches and matches[0][0] == f"{a}{sep}{b}"


@S_FAST
@given(name=_citation_name(), year=_year_token())
def test_citation_at_string_start(name, year):
    """A citation opening the text (no leading context) is still found."""
    assert _SUMMARY_CITATION_RE.findall(f"{name} ({year})") == [(name, year)]


@S_FAST
@given(name=_citation_name(), year=_year_token(), n_extra=st.integers(min_value=1, max_value=3))
def test_multiple_citations_all_recovered(name, year, n_extra):
    """Repeated distinct citations are each extracted."""
    text = " ".join(f"{name} ({year})" for _ in range(n_extra + 1))
    matches = _SUMMARY_CITATION_RE.findall(text)
    assert (name, year) in matches


# ═══════════════════════════════════════════════════════════════════════════
# _BOLD_NAME_RE round-trips
# ═══════════════════════════════════════════════════════════════════════════


@st.composite
def _claim(draw):
    words = draw(st.lists(st.text(alphabet=_LOWER, min_size=3, max_size=8), min_size=2, max_size=5))
    claim = " ".join(words)
    if len(claim) < 10:
        claim = claim + " " + "padding"
    return claim


@S_MED
@given(a=_surname(), b=_surname(), sep=st.sampled_from(_NAME_SEP_CHARS), claim=_claim())
def test_bold_name_roundtrip_compound(a, b, sep, claim):
    """``**Smith-Jones**: <claim>`` → (full compound name, claim)."""
    text = f"**{a}{sep}{b}**: {claim}"
    matches = _BOLD_NAME_RE.findall(text)
    assert matches
    assert matches[0] == (f"{a}{sep}{b}", claim)


@S_MED
@given(name=_surname(), claim=_claim())
def test_bold_name_roundtrip_simple(name, claim):
    text = f"**{name}**: {claim}"
    assert _BOLD_NAME_RE.findall(text) == [(name, claim)]


@S_FAST
@given(name=_surname(), claim=_claim())
def test_bold_name_requires_colon(name, claim):
    """Without the colon the bold-name pattern does not fire."""
    assert _BOLD_NAME_RE.findall(f"**{name}** {claim}") == []


@S_FAST
@given(name=_surname(), short_claim=st.text(alphabet=_LOWER + " ", min_size=0, max_size=8))
def test_bold_name_requires_10char_claim(name, short_claim):
    """A claim of at most 8 chars (+ the separator space = 9) never reaches
    the 10-char minimum."""
    assert _BOLD_NAME_RE.findall(f"**{name}**: {short_claim}") == []


def test_bold_name_nine_char_claim_matches_with_space():
    """Characterization: a 9-char claim DOES match because the regex counts
    the separating space into the 10-char minimum (group 2 = ' abcdefghi')."""
    matches = _BOLD_NAME_RE.findall("**Federn**: abcdefghi")
    assert matches == [("Federn", " abcdefghi")]


# ═══════════════════════════════════════════════════════════════════════════
# _AUTHOR_RE / _YEAR_IN_PARENS_RE / _BARE_YEAR_RE
# ═══════════════════════════════════════════════════════════════════════════


@S_MED
@given(
    name=_surname(),
    year=_year_token(1000, 2199),
    sep=st.sampled_from(["-", "\u2013"]),
    lead=_context(),
)
def test_author_re_roundtrip_compound(name, year, sep, lead):
    """The exec-bullet author regex supports ASCII hyphen + en-dash compounds."""
    text = f"{lead} {name}{sep}{name} ({year}).".strip()
    matches = _AUTHOR_RE.findall(text)
    assert matches
    assert matches[0] == (f"{name}{sep}{name}", year)


@S_MED
@given(name=_surname(), year=_year_token(1000, 2199), lead=_context())
def test_author_re_roundtrip_simple(name, year, lead):
    text = f"{lead} {name} ({year}).".strip()
    assert _AUTHOR_RE.findall(text)[0] == (name, year)


@S_MED
@given(
    name=_surname(),
    year3=st.integers(min_value=100, max_value=999),
    year4=st.integers(min_value=1000, max_value=2999),
    suffix=st.sampled_from(["", "a", "b"]),
)
def test_year_in_parens_matches_3_and_4_digit_years(name, year3, year4, suffix):
    """3-digit years (dropped digit) and 4-digit years both match."""
    assert _YEAR_IN_PARENS_RE.findall(f"{name} ({year3})") == [(name, str(year3))]
    assert _YEAR_IN_PARENS_RE.findall(f"{name} ({year4}{suffix})") == [(name, f"{year4}{suffix}")]


@S_FAST
@given(y=st.integers(min_value=1000, max_value=2199))
def test_bare_year_re_matches_yearlike_tokens(y):
    assert _BARE_YEAR_RE.findall(f"in {y} the work") == [str(y)]


@S_FAST
@given(
    y=st.one_of(
        st.integers(min_value=0, max_value=999),
        st.integers(min_value=2200, max_value=9999),
    ),
    pre=st.sampled_from(["x", ""]),
    post=st.sampled_from(["abc", ""]),
)
def test_bare_year_re_ignores_non_yearlike_tokens(y, pre, post):
    """Characterization: outside 1xxx/20xx/21xx, or glued to letters, a
    year-like number is invisible to the bare-year check."""
    token = f"{pre}{y}{post}"
    if pre or post:
        assert _BARE_YEAR_RE.findall(token) == []
    else:
        assert _BARE_YEAR_RE.findall(token) == []


# ═══════════════════════════════════════════════════════════════════════════
# extract_citations (deterministic_analyzer) round-trips
# ═══════════════════════════════════════════════════════════════════════════


@S_MED
@given(
    surname=_surname(),
    apos=st.sampled_from(_APOS_CHARS),
    poss=st.sampled_from(["", "s"]),
    year=_year_token(1000, 2199),
    lead=_context(),
    trail=_context(),
)
def test_extract_citations_parenthetical_roundtrip(surname, apos, poss, year, lead, trail):
    """``Federn's (1952)`` → {author: 'Federn', years: '1952'} — the
    possessive is stripped, the surname and year recovered exactly."""
    text = f"{lead} {surname}{apos}{poss} ({year}) {trail}".strip()
    cits = extract_citations(text)
    assert {"author": surname, "years": year, "type": "parenthetical"} in cits


@S_MED
@given(surname=_surname(), year=_year_token(1000, 2199), lead=_context(), trail=_context())
def test_extract_citations_inline_roundtrip(surname, year, lead, trail):
    text = f"{lead} {surname} {year} {trail}".strip()
    cits = extract_citations(text)
    assert {"author": surname, "years": year, "type": "inline"} in cits


@S_MED
@given(
    a=_surname(),
    b=_surname(),
    sep=st.sampled_from(["-", "\u2013"]),  # supported compound seps (see bug note)
    year=_year_token(1000, 2199),
)
def test_extract_citations_compound_roundtrip(a, b, sep, year):
    """Compound surnames with the SUPPORTED separators round-trip intact."""
    cits = extract_citations(f"{a}{sep}{b} ({year})")
    assert {"author": f"{a}{sep}{b}", "years": year, "type": "parenthetical"} in cits


@S_FAST
@given(sep=st.sampled_from(["\u2014", "\u2010", "\u2011"]))
def test_extract_citations_em_dash_compound_truncates(sep):
    """KNOWN BUG (characterization, report-only): em-dash / typographic-hyphen
    compounds are NOT supported by deterministic_analyzer's own compound
    classes (still ASCII ``[-\\u2013]``) — the FIRST surname is silently
    dropped and only the second is extracted, while the postcheck-side
    _SUMMARY_CITATION_RE (shared NAME_SEP) extracts the full compound.
    DEBT-08 shared APOS/NAME_SEP with the postcheck regexes but not with
    these patterns."""
    cits = extract_citations(f"Smith{sep}Jones (1983)")
    assert cits == [{"author": "Jones", "years": "1983", "type": "parenthetical"}]
    # the postcheck-side regex DOES see the full compound
    assert _SUMMARY_CITATION_RE.findall(f"Smith{sep}Jones (1983)") == [(f"Smith{sep}Jones", "1983")]


@S_FAST
@given(lead=_context(), n=st.integers(min_value=1, max_value=4))
def test_extract_citations_multiple_citations_all_found(lead, n):
    text = " ".join(f"Author{chr(65 + i)} (19{50 + i})" for i in range(n))
    cits = extract_citations(f"{lead} {text}")
    assert len(cits) == n


# ═══════════════════════════════════════════════════════════════════════════
# validate_years
# ═══════════════════════════════════════════════════════════════════════════


@S_FAST
@given(y=st.integers(min_value=MIN_YEAR, max_value=min(MAX_YEAR, 2100)))
def test_validate_years_in_range_years_not_flagged(y):
    text, issues = validate_years(f"Erikson ({y}) defined the stage.", "exec")
    assert issues == []


@S_FAST
@given(y=st.integers(min_value=1000, max_value=MIN_YEAR - 1))
def test_validate_years_below_min_flagged(y):
    _, issues = validate_years(f"In {y} the theory emerged.", "exec")
    assert len(issues) == 1
    assert issues[0].detector == "year"
    assert issues[0].severity == "flag"
    assert str(y) in issues[0].detail


@S_FAST
@given(y=st.integers(min_value=MAX_YEAR + 1, max_value=max(MAX_YEAR + 1, 2199)))
def test_validate_years_above_max_flagged(y):
    _, issues = validate_years(f"By {y} the framework had changed.", "exec")
    assert len(issues) == 1
    assert issues[0].detector == "year"


@S_FAST
@given(y=st.one_of(st.integers(2200, 9999), st.integers(0, 999)))
def test_validate_years_far_out_of_scope_not_flagged(y):
    """Characterization: _BARE_YEAR_RE only scans 1xxx/20xx/21xx tokens —
    far-future or short numbers are invisible to the year check."""
    _, issues = validate_years(f"By {y} nothing happened.", "exec")
    assert issues == []


@S_MED
@given(bad=st.sampled_from(_IMPOSSIBLE_AUTHORS), year=_year_token(1900, 2020))
def test_validate_years_unknown_author_flagged(bad, year):
    text, issues = validate_years(
        f"{bad} ({year}) formulated the concept.", "exec", source_authors=_GROUNDED_AUTHORS
    )
    assert any(i.detector == "year" and bad in i.detail for i in issues)


@S_MED
@given(good=st.sampled_from(_GROUNDED_AUTHORS), year=_year_token(1900, 2020))
def test_validate_years_grounded_author_not_flagged(good, year):
    _, issues = validate_years(
        f"{good} ({year}) formulated the concept.", "exec", source_authors=_GROUNDED_AUTHORS
    )
    assert issues == []


@S_FAST
@given(
    text=st.text(min_size=0, max_size=120),
    authors=st.none() | st.lists(st.text(min_size=0, max_size=10), max_size=3),
)
def test_validate_years_never_rewrites_text(text, authors):
    """Year/name validation only flags — the text is returned unchanged."""
    out, _ = validate_years(text, "exec", source_authors=authors)
    assert out == text


@S_FAST
@given(text=st.text(min_size=0, max_size=80))
def test_validate_years_empty_text_short_circuits(text):
    out, issues = validate_years("", "exec", source_authors=["Freud"])
    assert out == ""
    assert issues == []


# ═══════════════════════════════════════════════════════════════════════════
# detect_dropped_digit_years
# ═══════════════════════════════════════════════════════════════════════════


@st.composite
def _dropped_digit_year(draw):
    """A 4-digit year with one digit dropped (any position)."""
    y = draw(st.integers(min_value=1000, max_value=2999))
    s = f"{y:04d}"
    pos = draw(st.integers(min_value=0, max_value=3))
    return s, s[:pos] + s[pos + 1 :]


@S_MED
@given(pair=_dropped_digit_year(), author=_surname())
def test_dropped_digit_year_is_repaired(pair, author):
    full, dropped = pair
    text = f"{author} ({dropped}) described the model."
    source = f"{author} ({full}) described the model."
    fixed, issues = detect_dropped_digit_years(text, source, "bullet0")
    assert f"{author} ({full})" in fixed
    assert any(i.detector == "dropped_digit_year" and i.severity == "fix" for i in issues)


@S_MED
@given(pair=_dropped_digit_year(), author=_surname())
def test_dropped_digit_year_fix_is_fixpoint(pair, author):
    """Applying the fix a second time changes nothing (convergence)."""
    full, dropped = pair
    text = f"{author} ({dropped}) described the model."
    source = f"{author} ({full}) described the model."
    once, issues1 = detect_dropped_digit_years(text, source, "f")
    twice, issues2 = detect_dropped_digit_years(once, source, "f")
    assert twice == once
    assert issues2 == []


@S_MED
@given(year=_year_token(1000, 2999), author=_surname())
def test_matching_years_left_alone(year, author):
    text = f"{author} ({year}) described the model."
    source = f"{author} ({year}) described the model."
    out, issues = detect_dropped_digit_years(text, source, "f")
    assert out == text
    assert issues == []


@S_MED
@given(year=_year_token(1000, 2999), author=_surname(), other=_surname())
def test_unknown_author_years_left_alone(year, author, other):
    """Author absent from the source: the year cannot be verified → untouched."""
    text = f"{author} ({year}) described the model."
    source = f"{other} (1234) described something else."
    if author.lower() == other.lower():
        return
    out, issues = detect_dropped_digit_years(text, source, "f")
    assert out == text
    assert issues == []


def test_extra_digit_year_vs_three_digit_source_repaired():
    """Case 2 branch: a 4-digit summary year against a 3-digit source year
    (the source's own dropped digit) is repaired to the source's year."""
    fixed, issues = detect_dropped_digit_years("Author (1981) wrote.", "Author (181) wrote.", "f")
    assert "Author (181)" in fixed
    assert any(i.severity == "fix" for i in issues)


def test_five_digit_year_not_repaired():
    """Characterization: _YEAR_IN_PARENS_RE caps at 4 digits — a 5-digit year
    never matches, so the extra-digit branch cannot fire for it."""
    fixed, issues = detect_dropped_digit_years("Author (19981) wrote.", "Author (1981) wrote.", "f")
    assert fixed == "Author (19981) wrote."
    assert issues == []


# ═══════════════════════════════════════════════════════════════════════════
# Shared constants / helpers
# ═══════════════════════════════════════════════════════════════════════════


@S_FAST
@given(ch=st.sampled_from(_APOS_CHARS + _NAME_SEP_CHARS))
def test_shared_classes_are_regex_character_classes(ch):
    """APOS and NAME_SEP are complete character classes (brackets included,
    escape sequences as text) — compiling them directly yields classes that
    match exactly the documented codepoints."""
    assert len(ch) == 1
    apos_cls = re.compile(APOS)
    sep_cls = re.compile(NAME_SEP)
    assert (apos_cls.fullmatch(ch) is not None) == (ch in _APOS_CHARS)
    assert (sep_cls.fullmatch(ch) is not None) == (ch in _NAME_SEP_CHARS)
    assert apos_cls.fullmatch("a") is None and sep_cls.fullmatch("a") is None


def test_citations_regex_constants_are_the_documented_codepoints():
    """Characterization: the exact class bodies (ASCII apostrophe + both
    single quotes; ASCII hyphen + en/em dash + U+2010/U+2011) as raw
    escape-sequence text."""
    assert APOS == r"['\u2019\u2018]"
    assert NAME_SEP == r"[-\u2013\u2014\u2010\u2011]"
    apos_cls = re.compile(APOS)
    for ch in _APOS_CHARS:
        assert apos_cls.fullmatch(ch)
    sep_cls = re.compile(NAME_SEP)
    for ch in _NAME_SEP_CHARS:
        assert sep_cls.fullmatch(ch)


@S_FAST
@given(
    text=st.text(min_size=0, max_size=200),
    pos=st.integers(min_value=-5, max_value=250),
    width=st.integers(min_value=0, max_value=100),
)
def test_snippet_is_bounded_and_collapsed(text, pos, width):
    s = _snippet(text, pos % (len(text) + 1) if text else 0, width)
    assert len(s) <= width + 2
    assert "\n" not in s
    assert "  " not in s


@S_FAST
@given(pos=st.integers(min_value=0, max_value=50))
def test_snippet_empty_text_returns_empty(pos):
    assert _snippet("", pos) == ""


@S_FAST
@given(s=st.text(min_size=0, max_size=40))
def test_is_subsequence_reflexive(s):
    assert _is_subsequence(s, s)
    assert _is_subsequence("", s)
    assert _is_subsequence(s, s + s)


@S_FAST
@given(
    a=st.text(alphabet="ab", min_size=0, max_size=10),
    b=st.text(alphabet="ab", min_size=0, max_size=10),
)
def test_is_subsequence_matches_two_pointer_reference(a, b):
    """_is_subsequence agrees with an independent two-pointer implementation."""
    it = iter(b)
    reference = all(c in it for c in a)  # same semantics, spelled differently
    if reference:
        assert len(a) <= len(b)  # a subsequence can never be longer
    assert _is_subsequence(a, b) == reference


@S_FAST
@given(
    n_fix=st.integers(min_value=0, max_value=5),
    n_flag=st.integers(min_value=0, max_value=5),
)
def test_postcheck_report_counts_fix_and_flag(n_fix, n_flag):
    report = PostCheckReport()
    for _ in range(n_fix):
        report.add(Issue(detector="d", severity="fix", field="f", snippet="s", detail="x"))
    for _ in range(n_flag):
        report.add(Issue(detector="d", severity="flag", field="f", snippet="s", detail="x"))
    assert report.fixed_count == n_fix
    assert report.flagged_count == n_flag
    assert report.total_findings == n_fix + n_flag == len(report.issues)


@S_FAST
@given(
    detector=st.sampled_from(["year", "garbled", "space"]), field=st.text(min_size=0, max_size=10)
)
def test_issue_dataclass_holds_fields(detector, field):
    issue = Issue(detector=detector, severity="flag", field=field, snippet="s", detail="d")
    assert issue.detector == detector
    assert issue.severity == "flag"
    assert issue.field == field
