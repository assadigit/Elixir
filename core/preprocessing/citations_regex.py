r"""V18.15.5.1 (DEBT-08): Shared citation-regex Unicode classes.

WHY THIS EXISTS
---------------
The V18.15.3.5 curly-apostrophe fix was applied ONLY to
``core/preprocessing/deterministic_analyzer.py``. The four citation regexes in
``core/summarisation/postchecks.py`` (``_SUMMARY_CITATION_RE``,
``_BOLD_NAME_RE``, ``_AUTHOR_RE``, ``_YEAR_IN_PARENS_RE``) all used ASCII-only
``'`` — meaning a curly-possessive citation copied verbatim from a PDF source
(e.g. ``Federn's (1952)`` with U+2019) was SILENTLY SKIPPED by
``validate_years`` / ``verify_attribution`` / ``detect_dropped_digit_years``.

This module is the single source of truth for the Unicode punctuation classes
used by BOTH citation extractors, so the inconsistency can never recur.

DESIGN
-----
- Pure constants (regex character-class strings), no compiled patterns, no
  functions. Zero behavioral risk — callers embed the constants in their own
  patterns exactly where the old ASCII-only classes were.
- Conservative: only ADDS Unicode handling (U+2018 left single quote,
  U+2014 em-dash, U+2010/U+2011 typographic hyphens). Never removes existing
  matches. This matches the V18.15.3.5 fix's additive philosophy.

USAGE
-----
    from core.preprocessing.citations_regex import APOS, NAME_SEP
    _SUMMARY_CITATION_RE = re.compile(
        rf'([A-Z][a-zA-Z]+(?:{NAME_SEP}[A-Z][a-zA-Z]+)?'
        rf'(?:{APOS}[sS]?)?)'
        rf'\s*\(?(\d{4}[a-z]?)\)?'
    )
"""

from __future__ import annotations

# ── Apostrophe class ───────────────────────────────────────────────────────
# Covers all 3 Unicode apostrophe variants a PDF/typesetter can emit:
#   U+0027  '  ASCII apostrophe (straight)
#   U+2019  '  RIGHT SINGLE QUOTATION MARK (curly apostrophe — most common in PDFs)
#   U+2018  '  LEFT SINGLE QUOTATION MARK (rare as apostrophe, but some typesetters use it)
APOS = r"['\u2019\u2018]"

# ── Compound-surname separator class ────────────────────────────────────────
# Covers all Unicode dash/hyphen variants that can separate compound surnames:
#   U+002D  -  ASCII HYPHEN-MINUS (the common case)
#   U+2013  –  EN DASH (common in typeset text — already handled pre-V18.15.5.1)
#   U+2014  —  EM DASH (rare in surnames but possible: "Smith—Jones")
#   U+2010  ‐  HYPHEN (Unicode typographic hyphen — PDFs sometimes emit this)
#   U+2011  ‑  NON-BREAKING HYPHEN (PDFs sometimes emit this)
NAME_SEP = r"[-\u2013\u2014\u2010\u2011]"
