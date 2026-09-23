"""V0.4.23 (audit V0.4.22, backlog #1): the author-name garbage filter.

The V0.4.22 ch.4 run's gap-fill hunted "theorists" from a deterministic
author list polluted by four garbage families (each one shipped or wasted
a gap-fill round):

  1. **Month names** — "May 1975" / "December (1983)" matched the
     ``Author Year`` citation patterns (H1: a fabricated "May" bullet was
     stitched from two real theorists' claims by gap-fill).
  2. **Mirrored-table OCR strings** — TABLE 4-1's reversed text contains
     "TeUOT}BIOA 0۲۲۶ 8" and "[Tey ۸۶8۵ ueD": Python's ``\\d`` matches
     ARABIC-INDIC digits too, so "BIOA 0۲۲۶" passed as ``Author (4
     Unicode digits)`` and "Tey ۸۶8۵" as ``Author Year``.
  3. **Implausible years** — "JOQuUI 8225/48" produced author "JOQuUI"
     with year 8225 (no plausible publication year).
  4. **Non-Latin / embedded-digit / ALL-CAPS / mixed-case tokens** —
     "JeuoNes0A", "SUIMPIPYIIM", "aTQNJ", "S1ay}O" (mirrored-table
     fragments that matched a citation shape by accident), and acronym
     citations like "DSM-III (1980)" that are NOT author names.

This module is the single source of truth for "is this extracted author a
plausible Latin-script surname (with a plausible year)?" — used at the
ROOT (:func:`deterministic_analyzer.extract_citations` ``_add``) so every
consumer (author counts, the judge, gap-fill author hunting, the recall
floor, ``check_coverage``) sees a clean list, and mirrored at the summary
side (``postchecks.attribution.validate_years`` — a "May (1975)" in the
MODEL'S output must not be flagged as "name corruption" either).

Content-agnostic: language-level structure (months, digits, scripts,
letter-case shapes), no book-specific terms.
"""

from __future__ import annotations

import re
from datetime import date

# ── The closed classes ──────────────────────────────────────────────────────

#: Month names + common abbreviations. "May" is the classic citation-regex
#: false positive ("May 1975"); the rest ship from dates in prose/tables.
MONTHS = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }
)

#: Publication years outside this window are OCR/table garbage ("8225",
#: "190789", "0۲۲۶"). 1500 comfortably precedes every printing-press-era
#: citation a book chapter can carry (a mid-19th-century legal-medical
#: treatise included — 1500 precedes every printable-era citation).
_PLAUSIBLE_YEAR_MIN = 1500
_PLAUSIBLE_YEAR_MAX = date.today().year + 1

#: Solid-prefix particles whose FOLLOWING capital is legitimate surname
#: orthography (McElroy, O'Brien→via apostrophe, DeVries, VanDyke, …).
#: Everything else with a lowercase→uppercase transition inside one token
#: is mirrored-table garbage ("JOQuUI", "aTQNJ", "JeuoNes0A").
_ALLOWED_SOLID_PREFIXES = (
    "mc",
    "mac",
    "o'",
    "d'",
    "l'",
    "v'",
    "de",
    "del",
    "di",
    "da",
    "du",
    "la",
    "le",
    "les",
    "van",
    "von",
    "der",
    "den",
    "ter",
    "ten",
    "ben",
    "abu",
    "ibn",
    "al",
    "el",
    "st",
)

#: Latin-script letters + the separators a surname can carry. Anything
#: outside (Cyrillic, Greek, CJK, Arabic-Indic digits, mirrored-table
#: punctuation like ``}``) marks the token as garbage. ASCII digits are
#: allowed at this layer (check 3 handles embedded-digit garbage like
#: "JeuoNes0A" precisely); whitespace and the Unicode dash family
#: (U+2010-U+2015) are allowed — multi-author captures can span a source
#: line break and typographic-dash surname compounds are real citations.
_NON_LATIN_RE = re.compile(r"[^A-Za-z0-9À-ÖØ-öø-ÿ'’\u2018\u2019\-\s\u2010-\u2015]")

#: A digit inside an otherwise-letter token ("JeuoNes0A", "pesrydei30a8").
_EMBEDDED_DIGIT_RE = re.compile(r"(?<=[A-Za-z])\d|(?<=\d)[A-Za-z]")

#: ALL-CAPS letter token of length >= 3 ("BIOA", "DSM", "SUIMPIPYIIM").
#: Running-text citations never write surnames in caps — these tokens are
#: acronyms (DSM-III, ICD, MMPI) or OCR table fragments.
_ALL_CAPS_RE = re.compile(r"[A-Z]{3,}")


def _has_allowed_particle_shape(token: str) -> bool:
    """True when the token's internal capital is the legit particle form
    (McElroy / DeVries / VanDyke / O'Brien)."""
    low = token.lower()
    for p in _ALLOWED_SOLID_PREFIXES:
        if low.startswith(p) and len(token) > len(p):
            rest = token[len(p) :]
            if rest and rest[0].isupper():
                return True
    # Apostrophe-separated internal capital: O'Brien, D'Arcy
    if "'" in token or "\u2019" in token:
        return True
    return False


def garbage_author_reason(
    author: str, year: str | None = None, check_year: bool = False
) -> str | None:
    """Return a human-readable reason when ``author`` is extraction
    garbage, else ``None`` (a plausible Latin-script surname).

    Args:
        author: the candidate author string (post possessive-strip).
        year: the optional extracted year string.
        check_year: OPT-IN implausible-year check (outside 1500..now+1,
            e.g. "8225"). OFF by default — the EXTRACTION layer must stay
            shape-faithful (the citation roundtrip property extracts any
            4-digit year verbatim; year plausibility is
            ``postchecks.validate_years``'s own check). The SUMMARY-side
            mirror turns it on (a model-written "X (8225)" citation is
            garbage on its face).

    Checks, in order:
      1. month name (whole author or its first token — "May", "March");
      2. non-Latin-script characters (Arabic-Indic digits, CJK, ``}``);
      3. digits embedded inside letter tokens ("JeuoNes0A");
      4. ALL-CAPS letter tokens of length >= 3 ("BIOA", "DSM");
      5. internal mixed-case beyond allowed particle shapes ("JOQuUI");
      6. implausible year outside 1500..now+1 ("8225") — only when
         ``check_year`` is True and ``year`` is given.

    Never raises; empty input returns ``"empty"``.
    """
    try:
        if not author or not author.strip():
            return "empty"
        name = author.strip()
        # 1. Month names — the whole string or its first token (dates in
        # prose: "May 1975" captures author "May").
        first_tok = name.split()[0].strip(".,;:()'’")
        if first_tok.lower() in MONTHS and (len(name.split()) == 1 or first_tok == name.split()[0]):
            return f"month name ({first_tok})"
        # 2. Non-Latin script / mirrored punctuation.
        if _NON_LATIN_RE.search(name):
            return "non-Latin characters"
        # Token-level shape checks (skip pure particles like "van", "der").
        for tok in name.split():
            tok_c = tok.strip(".,;:()'")
            if not tok_c or not any(c.isalpha() for c in tok_c):
                continue
            # 3. Digit embedded mid-token (letter→digit or digit→letter
            #    boundary inside one token).
            if _EMBEDDED_DIGIT_RE.search(tok_c):
                return f"embedded digit in token ({tok_c})"
            letters = [c for c in tok_c if c.isalpha()]
            if not letters:
                continue
            # 4. ALL-CAPS letter token >= 3 (BIOA / DSM / SUIMPIPYIIM).
            if len(letters) >= 3 and all(c.isupper() for c in letters):
                return f"all-caps token ({tok_c})"
            # 5. Internal mixed-case garbage — an uppercase-MAJORITY token
            #    that also contains lowercase ("JOQuUI": 5 caps/1 lower,
            #    "aTQNJ": 4/1) is mirrored-table noise. Uppercase-minority
            #    shapes are legitimate surnames ("McElroy", "DeVries", and
            #    the synthetic "AuthorA" class: 2 caps/5 lower) unless they
            #    are allowed particle forms anyway.
            has_lower = any(c.islower() for c in letters)
            has_upper = any(c.isupper() for c in letters)
            if (
                has_lower
                and has_upper
                and not _has_allowed_particle_shape(tok_c)
                and sum(1 for c in letters if c.isupper()) > sum(1 for c in letters if c.islower())
            ):
                return f"mixed-case garbage token ({tok_c})"
        # 6. Implausible year (mirrored-table "8225" years) — OPT-IN:
        # extraction stays shape-faithful; the summary-side mirror and
        # postchecks opt in.
        if year and check_year:
            m = re.search(r"[0-9]{4}", str(year))
            if m:
                yv = int(m.group(0))
                if yv < _PLAUSIBLE_YEAR_MIN or yv > _PLAUSIBLE_YEAR_MAX:
                    return f"implausible year ({yv})"
        return None
    except Exception:
        # Never let a shape heuristic raise into the extraction path.
        return None


def is_plausible_author(author: str, year: str | None = None) -> bool:
    """Convenience boolean wrapper around :func:`garbage_author_reason`."""
    return garbage_author_reason(author, year) is None
