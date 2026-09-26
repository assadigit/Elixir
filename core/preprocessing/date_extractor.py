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

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_ABBR = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_ALL_MONTHS = {**_MONTHS, **_MONTH_ABBR}
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
_COMPACT_DATE = re.compile(r"\b(\d{8})\b")

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
    # Plain year LAST (least specific — matches bare 4-digit numbers).
    ("plain_year", _PLAIN_YEAR, _parse_plain_year),
]


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

    Args:
        text: the text to scan.

    Returns:
        A list of DateMatch objects, sorted by position.
    """
    if not text:
        return []

    # V0.5.1 (TUNING): mask page-reference patterns ("p. ~137", "(p. ~141)")
    # before running the date patterns — inject_page_refs uses ~ before page
    # numbers, which the ~-prefix approx regex would falsely match as circa
    # years. Masking replaces the page-ref text with spaces (preserving
    # positions) so the date patterns don't see them.
    _masked_text = _PAGE_REF_PREFIX.sub(lambda m: " " * len(m.group(0)), text)

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
    """
    source_set = {d.normalized.replace("~", "").replace("?", "") for d in source_dates}
    summary_set = {d.normalized.replace("~", "").replace("?", "") for d in summary_dates}

    hallucinated = [
        d for d in summary_dates if d.normalized.replace("~", "").replace("?", "") not in source_set
    ]
    omitted = [
        d for d in source_dates if d.normalized.replace("~", "").replace("?", "") not in summary_set
    ]
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
