"""V0.5.0: deterministic date-extraction module for the verification phase.

A comprehensive, content-agnostic date extractor covering the major date
formats found in English-language books (per the user's exhaustive list,
Parts 1-8): BC/AD/BCE/CE era designations, plain years, approximate
dates (c./ca./circa/~/?), date ranges, centuries/decades/millennia, full
calendar dates, scientific notation (BP/ka/Ma/Mya), and historical
calendar eras (AH/AM/AUC/SH/BE/Saka/VS).

Used by the post-conversion verification LAYER (V0.4.40) to
deterministically verify dates: extract all dates from the SOURCE +
the SUMMARY, then compare (summary dates NOT in the source = potential
hallucinations; source dates NOT in the summary = potential omissions).

Content-agnostic (Rule 1 ✓): the patterns are generic date-structure
regexes — no hardcoded years, no domain-specific dates. Works on any
book in any discipline.

The module is structured as a list of (name, regex, parser) entries so
new date formats can be added without modifying the extraction logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DateMatch:
    """A date-like expression found in text."""

    text: str  # the matched text
    start: int  # position in the source text
    end: int
    format_type: str  # e.g. "plain_year", "bc_ad", "circa", "range", "century"
    year: int | None = None  # the extracted year number (None if unparseable)
    year_end: int | None = None  # for ranges, the end year
    era: str = "ad"  # "ad"/"bc"/"bce"/"ce"/"bp"/"ah"/"am"/"auc"/"sh"/"be"/...
    is_approximate: bool = False
    is_uncertain: bool = False
    normalized: str = ""  # canonical form for comparison

    def __post_init__(self):
        if not self.normalized:
            self.normalized = _normalize(self)


# ─────────────────────────────────────────────────────────────────────────────
# Month names (for full-date patterns)
# ─────────────────────────────────────────────────────────────────────────────

# V0.5.0 had _MONTHS/_MONTH_ABBR/_ALL_MONTHS dict helpers here (FIX-P3-6):
# DELETED — they were defined but never referenced outside their own
# construction (only the _MONTH_PATTERN regex below is used, with month
# strings inlined). The dict forms were dead.
_MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?"
)

# ─────────────────────────────────────────────────────────────────────────────
# Century word-forms
# ─────────────────────────────────────────────────────────────────────────────

_CENTURY_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "twenty-first": 21,
}


# ─────────────────────────────────────────────────────────────────────────────
# Date format patterns
# Each entry: (format_type, compiled_regex, parser_function)
# The parser takes a regex Match + returns a DateMatch (or None to skip).
# ─────────────────────────────────────────────────────────────────────────────

# Part 1: BC/AD/BCE/CE era-labeled years.
# Covers: 500 BC, 500 B.C., 500 BCE, 500 B.C.E., AD 500, A.D. 500, 500 CE, 500 C.E.
_ERA_YEAR_SUFFIX = re.compile(
    r"\b(\d{1,4})\s*(B\.?C\.?(?:E\.?)?|A\.?D\.?|C\.?E\.?)\b",
    re.IGNORECASE,
)
_ERA_YEAR_PREFIX = re.compile(
    r"\b(A\.?D\.?)\s+(\d{1,4})\b",
    re.IGNORECASE,
)

# Part 2: Plain 4-digit years (1000-2999). Must NOT be preceded by a letter
# (to avoid matching parts of words like "abc1891") or followed by more digits.
_PLAIN_YEAR = re.compile(r"(?<!\w)(1\d{3}|2\d{3})(?!\d)")

# Part 2b: Letter-suffixed academic years (e.g. "1921a", "1908b", "1973a").
# V0.5.4 (Track E2): academic-citation convention disambiguates multiple
# publications by the same author in the same year with a single lowercase
# letter suffix. Without this pattern, extract_dates silently collapsed
# "1921a"/"1921b" → "1921" (a FN for the letter-suffix format — distinct
# papers became indistinguishable in the audit log). The new pattern
# captures the full "1921a" text in DateMatch.text while normalising to
# the bare year (ce:1921) so summary-vs-source matching still treats a
# bare "1921" as a match for a suffixed "1921a" (Rule 1: no hardcoded
# years/authors — generic \d{4}[a-z] structure).
_LETTER_SUFFIX_YEAR = re.compile(r"(?<!\w)(1\d{3}|2\d{3})([a-z])\b")

# Part 3: Approximate dates.
# V0.5.1 (TUNING): exclude ~NNN when preceded by "p." or in a "(p. ~NNN)"
# context — inject_page_refs uses ~ before page numbers, which the
# extractor falsely matched as circa years (e.g. "(p. ~137)" → circa 137).
# The negative lookbehind (?<!p\.\s) and (?<!p\.\s\() block the page-ref
# context. The word-based prefixes (c./ca./circa/about/around) are
# unaffected.
_PAGE_REF_PREFIX = re.compile(r"p\.\s*~?\d", re.IGNORECASE)
_APPROX_PREFIX = re.compile(
    r"(?<!\w)(c\.|ca\.|circa|about|around|approx\.|approximately|~)\s*(\d{1,4})\b",
    re.IGNORECASE,
)
_APPROX_SUFFIX = re.compile(r"\b(\d{1,4})(\?)")

# Part 4: Date ranges.
# V0.5.4 (Track A — A3 fix): the character class accepts en-dash (U+2013),
# em-dash (U+2014), AND ASCII hyphen (U+002D) for defense-in-depth — but the
# real normalization happens at the top of extract_dates() (see
# _DASH_TRANSLATE), which additionally covers the minus-sign (U+2212, used
# by some NLP processors + academic typesetting) and guarantees the
# downstream regexes see a single canonical dash regardless of input
# typographic conventions.
_YEAR_RANGE_DASH = re.compile(r"\b(\d{3,4})\s*[–—-]\s*(\d{2,4})\b")
_YEAR_RANGE_SLASH = re.compile(r"\b(\d{4})/(\d{2,4})\b")
_YEAR_RANGE_FROMTO = re.compile(r"\bfrom\s+(\d{3,4})\s+to\s+(\d{3,4})\b", re.IGNORECASE)

# Part 5: Centuries, decades, millennia.
_CENTURY_ORDINAL = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)\s+(century|c\.?)(?:\s*(AD|CE|BC|BCE))?\b",
    re.IGNORECASE,
)
_CENTURY_WORD = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
    r"|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth"
    r"|seventeenth|eighteenth|nineteenth|twentieth|twenty-first)\s+century\b",
    re.IGNORECASE,
)
_DECADE = re.compile(r"\b(\d{3})0s\b")
_DECADE_SHORT = re.compile(r"\b'(\d)0s\b")
_MILLENNIUM = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\s+millennium\b", re.IGNORECASE)

# Part 6: Full dates (day-month-year, month-day-year, ISO, numeric).
_FULL_DATE_DMY = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_FULL_DATE_MDY = re.compile(
    rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
_NUMERIC_DATE_YMD = re.compile(r"\b(\d{4})[/.](\d{1,2})[/.](\d{1,2})\b")
# V0.5.0 had _COMPACT_DATE = re.compile(r"\b(\d{8})\b") here (FIX-P3-6):
# DELETED — it was never wired into _PATTERNS and would have been a severe
# false-positive risk (matches phone numbers, ZIP+4, ISBNs, credit-card
# prefixes). The compact 8-digit date use case (e.g. 19951012) is already
# covered by _ISO_DATE + _NUMERIC_DATE_YMD when the user uses separators.

# Part 7: Historical calendar eras.
_CALENDAR_ERA = re.compile(
    r"\b(\d{1,4})\s*(A\.?H\.?|A\.?M\.?|A\.?U\.?C\.?|S\.?H\.?|B\.?E\.?|Saka|VS|Vikram\s+Samvat)\b",
    re.IGNORECASE,
)

# Part 8: Scientific notation.
_SCIENTIFIC_BP = re.compile(r"\b(\d[\d,]*)\s*(?:cal\s+)?(?:k?a\s*)?BP\b", re.IGNORECASE)
_SCIENTIFIC_MA = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:Ma|Mya)\b", re.IGNORECASE)
_YR_BP = re.compile(r"\b(\d{1,5})\s*yr\s*BP\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────────


def _normalize(dm: DateMatch) -> str:
    """Produce a canonical comparison string for a DateMatch.

    Examples:
        "500 BC" -> "bce:500"
        "AD 500" -> "ce:500"
        "c. 1891" -> "ce:1891~"
        "19th century" -> "century:19"
        "1890s" -> "decade:1890"
        "5000 BP" -> "bp:5000"
        "1447 AH" -> "ah:1447"
        "1891-1895" -> "range:1891-1895"
    """
    era = dm.era.lower()
    # Normalize BC/BCE to "bce", AD/CE to "ce".
    if era in ("bc", "b.c.", "bce", "b.c.e."):
        era = "bce"
    elif era in ("ad", "a.d.", "ce", "c.e."):
        era = "ce"

    if dm.format_type == "century":
        return f"century:{dm.year}"
    if dm.format_type == "century_word":
        return f"century:{dm.year}"
    if dm.format_type == "decade":
        return f"decade:{dm.year}"
    if dm.format_type == "decade_short":
        return f"decade:{dm.year}0"
    if dm.format_type == "millennium":
        return f"millennium:{dm.year}"
    if dm.format_type in ("range_dash", "range_slash", "range_fromto"):
        return f"range:{dm.year}-{dm.year_end}"

    suffix = "~" if dm.is_approximate else ""
    uncertain = "?" if dm.is_uncertain else ""
    if dm.year is not None:
        return f"{era}:{dm.year}{suffix}{uncertain}"
    return f"{era}:?{suffix}{uncertain}"


# ─────────────────────────────────────────────────────────────────────────────
# Pattern parsers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_era_suffix(m: re.Match) -> DateMatch | None:
    year = int(m.group(1))
    era_raw = m.group(2).upper().replace(".", "")
    # Normalize: BC/BCE -> "bce"; AD/CE -> "ce".
    if era_raw in ("BC", "BCE"):
        era = "bce"
    elif era_raw in ("AD", "CE"):
        era = "ce"
    else:
        era = era_raw.lower()
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="era_suffix",
        year=year,
        era=era,
    )


def _parse_era_prefix(m: re.Match) -> DateMatch | None:
    era_raw = m.group(1).upper().replace(".", "")
    year = int(m.group(2))
    era = "ce" if era_raw in ("AD", "CE") else era_raw.lower()
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="era_prefix",
        year=year,
        era=era,
    )


def _parse_plain_year(m: re.Match) -> DateMatch | None:
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="plain_year",
        year=int(m.group(0)),
        era="ce",  # default to CE (common era)
    )


def _parse_letter_suffix_year(m: re.Match) -> DateMatch | None:
    """V0.5.4 (Track E2): capture academic-citation year + letter suffix.

    E.g. "1921a", "1908b" — disambiguates multiple publications by the
    same author in the same year. The full text (with letter) is preserved
    in DateMatch.text for the audit log; the normalised form is the bare
    year (ce:1921) so a summary that cites just "1921" still matches a
    source that cites "1921a"/"1921b" (avoids introducing false-positive
    "hallucination" flags when the summary is less precise than the source).
    """
    year = int(m.group(1))
    return DateMatch(
        text=m.group(0),  # full "1921a"
        start=m.start(),
        end=m.end(),
        format_type="letter_suffix",
        year=year,
        era="ce",
        normalized=f"ce:{year}",  # bare-year normalisation preserves matching
    )


def _parse_approx_prefix(m: re.Match) -> DateMatch | None:
    year = int(m.group(2))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="circa",
        year=year,
        era="ce",
        is_approximate=True,
    )


def _parse_approx_suffix(m: re.Match) -> DateMatch | None:
    year = int(m.group(1))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="uncertain",
        year=year,
        era="ce",
        is_uncertain=True,
    )


def _parse_range_dash(m: re.Match) -> DateMatch | None:
    y1 = int(m.group(1))
    y2 = int(m.group(2))
    # Handle 2-digit end (e.g. 1891-95 -> 1891-1895).
    if len(m.group(2)) <= 2:
        century = y1 // 100 * 100
        y2 = century + int(m.group(2))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="range_dash",
        year=y1,
        year_end=y2,
        era="ce",
    )


def _parse_range_slash(m: re.Match) -> DateMatch | None:
    y1 = int(m.group(1))
    y2 = int(m.group(2))
    if len(m.group(2)) <= 2:
        century = y1 // 100 * 100
        y2 = century + int(m.group(2))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="range_slash",
        year=y1,
        year_end=y2,
        era="ce",
    )


def _parse_range_fromto(m: re.Match) -> DateMatch | None:
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="range_fromto",
        year=int(m.group(1)),
        year_end=int(m.group(2)),
        era="ce",
    )


def _parse_century_ordinal(m: re.Match) -> DateMatch | None:
    century = int(m.group(1))
    era_raw = (m.group(3) or "CE").upper().replace(".", "")
    era = "bce" if era_raw in ("BC", "BCE") else "ce"
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="century",
        year=century,
        era=era,
    )


def _parse_century_word(m: re.Match) -> DateMatch | None:
    word = m.group(1).lower()
    century = _CENTURY_WORDS.get(word, 0)
    if not century:
        return None
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="century_word",
        year=century,
        era="ce",
    )


def _parse_decade(m: re.Match) -> DateMatch | None:
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="decade",
        year=int(m.group(1) + "0"),  # 189 -> 1890
        era="ce",
    )


def _parse_decade_short(m: re.Match) -> DateMatch | None:
    # '90s -> 90 (context-dependent century)
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="decade_short",
        year=int(m.group(1)),
        era="ce",
    )


def _parse_millennium(m: re.Match) -> DateMatch | None:
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="millennium",
        year=int(m.group(1)),
        era="ce",
    )


def _parse_full_date_dmy(m: re.Match) -> DateMatch | None:
    year = int(m.group(3))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="full_date_dmy",
        year=year,
        era="ce",
    )


def _parse_full_date_mdy(m: re.Match) -> DateMatch | None:
    year = int(m.group(3))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="full_date_mdy",
        year=year,
        era="ce",
    )


def _parse_iso_date(m: re.Match) -> DateMatch | None:
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="iso_date",
        year=int(m.group(1)),
        era="ce",
    )


def _parse_calendar_era(m: re.Match) -> DateMatch | None:
    year = int(m.group(1))
    era_raw = m.group(2).upper().replace(".", "").replace(" ", "")
    era_map = {
        "AH": "ah",
        "AM": "am",
        "AUC": "auc",
        "SH": "sh",
        "BE": "be",
        "SAKA": "saka",
        "VS": "vs",
        "VIKRAMSAMVAT": "vs",
    }
    era = era_map.get(era_raw, era_raw.lower())
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="calendar_era",
        year=year,
        era=era,
    )


def _parse_scientific_bp(m: re.Match) -> DateMatch | None:
    year = int(m.group(1).replace(",", ""))  # strip commas (e.g. "10,000 BP")
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="scientific_bp",
        year=year,
        era="bp",
    )


def _parse_scientific_ma(m: re.Match) -> DateMatch | None:
    val = float(m.group(1))
    return DateMatch(
        text=m.group(0),
        start=m.start(),
        end=m.end(),
        format_type="scientific_ma",
        year=int(val),
        era="ma",
    )


# ─────────────────────────────────────────────────────────────────────────────
# The pattern registry: (name, regex, parser)
# Ordered by specificity (most specific first to avoid overlapping matches).
# ─────────────────────────────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern, callable]] = [
    # Most specific patterns first (to claim their text before generic patterns).
    ("iso_date", _ISO_DATE, _parse_iso_date),
    (
        "numeric_date",
        _NUMERIC_DATE,
        lambda m: DateMatch(
            text=m.group(0),
            start=m.start(),
            end=m.end(),
            format_type="numeric_date",
            year=int(m.group(3)),
            era="ce",
        ),
    ),
    (
        "numeric_date_ymd",
        _NUMERIC_DATE_YMD,
        lambda m: DateMatch(
            text=m.group(0),
            start=m.start(),
            end=m.end(),
            format_type="numeric_date_ymd",
            year=int(m.group(1)),
            era="ce",
        ),
    ),
    ("full_date_dmy", _FULL_DATE_DMY, _parse_full_date_dmy),
    ("full_date_mdy", _FULL_DATE_MDY, _parse_full_date_mdy),
    ("era_prefix", _ERA_YEAR_PREFIX, _parse_era_prefix),
    ("era_suffix", _ERA_YEAR_SUFFIX, _parse_era_suffix),
    ("calendar_era", _CALENDAR_ERA, _parse_calendar_era),
    ("scientific_bp", _SCIENTIFIC_BP, _parse_scientific_bp),
    ("scientific_ma", _SCIENTIFIC_MA, _parse_scientific_ma),
    (
        "yr_bp",
        _YR_BP,
        lambda m: DateMatch(
            text=m.group(0),
            start=m.start(),
            end=m.end(),
            format_type="yr_bp",
            year=int(m.group(1)),
            era="bp",
        ),
    ),
    ("century_ordinal", _CENTURY_ORDINAL, _parse_century_ordinal),
    ("century_word", _CENTURY_WORD, _parse_century_word),
    ("millennium", _MILLENNIUM, _parse_millennium),
    ("decade", _DECADE, _parse_decade),
    ("decade_short", _DECADE_SHORT, _parse_decade_short),
    ("range_dash", _YEAR_RANGE_DASH, _parse_range_dash),
    ("range_slash", _YEAR_RANGE_SLASH, _parse_range_slash),
    ("range_fromto", _YEAR_RANGE_FROMTO, _parse_range_fromto),
    ("approx_prefix", _APPROX_PREFIX, _parse_approx_prefix),
    ("approx_suffix", _APPROX_SUFFIX, _parse_approx_suffix),
    # V0.5.4 (Track E2): letter-suffixed academic years MUST come before
    # plain_year so the letter isn't dropped (the bare-year lookbehind
    # (?<!\w) on _PLAIN_YEAR would otherwise claim only "1921" from
    # "1921a", losing the disambiguating suffix).
    ("letter_suffix", _LETTER_SUFFIX_YEAR, _parse_letter_suffix_year),
    # Plain year LAST (least specific — matches bare 4-digit numbers).
    ("plain_year", _PLAIN_YEAR, _parse_plain_year),
]


# V0.5.4 (Track A — A3 fix): normalize en-dash (U+2013), em-dash (U+2014),
# and minus-sign (U+2212) to ASCII hyphen (U+002D) BEFORE the regex pass.
# Each source character is a single Unicode codepoint that maps 1:1 to a
# single ASCII hyphen — codepoint offsets are preserved (the regex engine
# works on codepoint positions, not bytes), so DateMatch.start/end remain
# valid against the ORIGINAL text. Without this, "1887–1902" (en-dash,
# common in publisher copy-edit pipelines) and "1887−1902" (minus-sign,
# used by some academic typesetting + NLP postprocessors) would slip past
# the _YEAR_RANGE_DASH regex and produce false "omitted" date flags.
# Generic typographic normalization (Rule 1 ✓ — no book/author content).
_DASH_TRANSLATE = str.maketrans(
    {
        "\u2013": "-",  # en-dash
        "\u2014": "-",  # em-dash
        "\u2212": "-",  # minus-sign
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def extract_dates(text: str) -> list[DateMatch]:
    """Extract all date-like expressions from text.

    Covers: BC/AD/BCE/CE, plain years, approximate (c./ca./circa/~/?),
    ranges (dash/slash/from-to), centuries (ordinal+word), decades,
    millennia, full dates (DMY/MDY/ISO/numeric), scientific notation
    (BP/ka/Ma/Mya), and historical calendar eras (AH/AM/AUC/SH/BE/Saka/VS).

    Overlapping matches are resolved by preferring the more specific
    pattern (e.g. "500 BC" is claimed by the era_suffix pattern, not
    plain_year).

    V0.5.4 (Track A — A3 fix): en-dash / em-dash / minus-sign are
    normalized to ASCII hyphen before the regex pass, so range patterns
    match regardless of the source's typographic dash convention. Offset
    preservation: each non-ASCII dash is a single codepoint that maps 1:1
    to a single ASCII hyphen, so DateMatch.start/end remain valid against
    the original (un-normalized) text.

    Args:
        text: the text to scan.

    Returns:
        A list of DateMatch objects, sorted by position.
    """
    if not text:
        return []

    # V0.5.4 (Track A — A3 fix): normalize en-dash / em-dash / minus-sign
    # to ASCII hyphen in a working copy of the text BEFORE the regex pass.
    # 1:1 codepoint substitution → offsets preserved (DateMatch.start/end
    # remain valid against the original text).
    _normalized_text = text.translate(_DASH_TRANSLATE)

    # V0.5.1 (TUNING): mask page-reference patterns ("p. ~137", "(p. ~141)")
    # before running the date patterns — inject_page_refs uses ~ before page
    # numbers, which the ~-prefix approx regex would falsely match as circa
    # years. Masking replaces the page-ref text with spaces (preserving
    # positions) so the date patterns don't see them.
    _masked_text = _PAGE_REF_PREFIX.sub(lambda m: " " * len(m.group(0)), _normalized_text)

    all_matches: list[DateMatch] = []
    claimed: list[tuple[int, int]] = []  # (start, end) ranges already claimed

    for _name, regex, parser in _PATTERNS:
        for m in regex.finditer(_masked_text):
            # Skip if this match overlaps with an already-claimed range.
            if any(m.start() < c_end and m.end() > c_start for c_start, c_end in claimed):
                continue
            dm = parser(m)
            if dm is not None:
                all_matches.append(dm)
                claimed.append((m.start(), m.end()))

    all_matches.sort(key=lambda d: d.start)
    return all_matches


def _year_covered_by_range(year: int, ranges: list[tuple[int, int]]) -> bool:
    """Return True if ``year`` falls within any (start, end) range (inclusive).

    V0.5.4 (Track A — A2 fix): used by :func:`compare_dates` to suppress
    the range-component false-positive class — e.g. a summary that
    references the range endpoints "1887" + "1902" as plain years must
    NOT be flagged as hallucinated when the source has the contiguous
    range "1887-1902" (and vice versa for omissions).

    Args:
        year: the candidate year (e.g. 1887).
        ranges: a list of (start, end) inclusive integer tuples.

    Returns:
        True if ``start <= year <= end`` for any range; False otherwise
        (including when ``ranges`` is empty).
    """
    return any(start <= year <= end for start, end in ranges)


def compare_dates(
    summary_dates: list[DateMatch],
    source_dates: list[DateMatch],
) -> dict:
    """Compare summary dates against source dates.

    Returns a dict with:
        - "hallucinated": summary dates NOT found in the source (potential fabrications)
        - "omitted": source dates NOT found in the summary (potential omissions)
        - "matched": dates present in both

    Comparison is by normalized form (e.g. "ce:1891", "bce:500", "century:19").
    Approximate dates (e.g. "c. 1891") match the corresponding exact date
    (e.g. "1891") — the "~" suffix is stripped for the comparison.

    V0.5.4 (Track A — A2 fix): a summary year that is NOT in the source's
    normalized set is still NOT flagged as a hallucination if it falls
    within a source range (e.g. summary "1887" + "1902" vs source range
    "1887-1902" — both endpoints are covered, so neither is hallucinated).
    The symmetric check applies to omissions (source years covered by a
    summary range are NOT flagged as omitted).
    """

    # Strip the approximate / uncertain suffixes for set comparison.
    def _strip_norm(d: DateMatch) -> str:
        return d.normalized.replace("~", "").replace("?", "")

    source_set = {_strip_norm(d) for d in source_dates}
    summary_set = {_strip_norm(d) for d in summary_dates}

    # V0.5.4 (Track A — A2 fix): collect (start, end) inclusive ranges
    # from both sides so a plain year that falls within a range on the
    # other side is not flagged as a hallucination/omission.
    source_ranges = [
        (d.year, d.year_end) for d in source_dates if d.year is not None and d.year_end is not None
    ]
    summary_ranges = [
        (d.year, d.year_end) for d in summary_dates if d.year is not None and d.year_end is not None
    ]

    hallucinated: list[DateMatch] = []
    for d in summary_dates:
        if _strip_norm(d) in source_set:
            continue
        # V0.5.4 (Track A — A2 fix): a summary year covered by a source
        # range is NOT a hallucination (the source has the contiguous
        # range; the summary merely references a sub-component).
        if d.year is not None and _year_covered_by_range(d.year, source_ranges):
            continue
        hallucinated.append(d)

    omitted: list[DateMatch] = []
    for d in source_dates:
        if _strip_norm(d) in summary_set:
            continue
        # V0.5.4 (Track A — A2 fix): a source year covered by a summary
        # range is NOT an omission (the summary has the contiguous range;
        # the source merely references a sub-component).
        if d.year is not None and _year_covered_by_range(d.year, summary_ranges):
            continue
        omitted.append(d)

    matched = source_set & summary_set

    return {
        "hallucinated": hallucinated,
        "omitted": omitted,
        "matched": sorted(matched),
        "hallucinated_count": len(hallucinated),
        "omitted_count": len(omitted),
        "matched_count": len(matched),
    }


__all__ = ["DateMatch", "extract_dates", "compare_dates"]
