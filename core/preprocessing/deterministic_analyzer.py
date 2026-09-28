"""Deterministic markdown analyzer — content-agnostic regex-based extraction.

V17.2: This module sits between Stage 3 (output_save) and Stage 4 (summarization).
It extracts metadata that gemma4-12b previously had to "find" itself (and missed
some — e.g. one theorist with 12 mentions). By pre-extracting this data with 100%-reliable
regex, gemma receives a complete, reliable metadata package and only needs to do
semantic work (summaries, synthesis).

Extracted (all 100% reliable via regex):
    1. Headings (H1-H6) → Table of Contents
    2. ALL-CAPS section titles (common in academic PDFs)
    3. Citations (Author (Year) + Author Year) → sorted by frequency
    4. Numbered lists → with section context
    5. Bulleted lists → with section context
    6. Bold terms → potential key concepts
    7. Italic terms → potential key definitions
    8. Block quotes → epigraphs
    9. Section word counts → identifies longest sections
    10. Citations per section → density map

Content-agnostic: works on any book chapter — fiction, academic, technical.
No chapter-specific logic, no hardcoded terms, no overfitting.
"""

from __future__ import annotations

import difflib
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from core.common.heading_utils import segment_filename_slug

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Content-agnostic English stopword filter (for citation false-positive removal)
# This is a GENERIC English-language filter, not chapter-specific.
# ─────────────────────────────────────────────────────────────────────────────

_ENGLISH_FALSE_POSITIVES = frozenset(
    {
        "In",
        "By",
        "The",
        "A",
        "An",
        "For",
        "With",
        "From",
        "About",
        "Around",
        "During",
        "Since",
        "Until",
        "After",
        "Before",
        "Between",
        "Within",
        "Near",
        "Beyond",
        "Through",
        "Throughout",
        "Following",
        "Prior",
        "This",
        "That",
        "These",
        "Those",
        "There",
        "Then",
        "Thus",
        "When",
        "Where",
        "While",
        "What",
        "Which",
        "Who",
        "Whom",
        "How",
        "Why",
        "And",
        "But",
        "Or",
        "Nor",
        "Yet",
        "So",
        "If",
        "As",
        "At",
        "On",
        "To",
        "Of",
        "Up",
        "Out",
        "Over",
        "Under",
        "Above",
        "Below",
        "Here",
        "Now",
        "Today",
        "Tomorrow",
        "Yesterday",
        "Soon",
        "Later",
        "Always",
        "Never",
        "Sometimes",
        "Often",
        "Rarely",
        "Usually",
        "However",
        "Therefore",
        "Moreover",
        "Furthermore",
        "Nevertheless",
        "Meanwhile",
        "Although",
        "Because",
        "Unless",
        "Whether",
        # V18.20.3.5 (audit v182034): the missing members of the discourse-
        # connective closed class. "Finally" shipped as a THEORIST in the
        # V18.20.3.4 rig run ("Finally, AuthorL (1964)" was captured by the
        # multi-author enumeration pattern). These are general-English function
        # words (the same word class as the entries above — every English
        # academic text starts sentences with them); completing the class is
        # language-level structure, NOT chapter-specific tuning.
        "Finally",
        "Additionally",
        "Notably",
        "Importantly",
        "Interestingly",
        "Significantly",
        "Specifically",
        "Similarly",
        "Likewise",
        "Conversely",
        "Nonetheless",
        "Regardless",
        "Certainly",
        "Clearly",
        "Obviously",
        "Indeed",
        "Perhaps",
        "Remarkably",
        "Noteworthy",
        "Accordingly",
        "Consequently",
        "Equally",
        "Namely",
        "Overall",
        "Alternatively",
        "Ultimately",
        "Briefly",
        "Lastly",
        "Subsequently",
        "Simultaneously",
        "Paradoxically",
        "Strikingly",
        "Surprisingly",
        "Each",
        "Every",
        "Some",
        "Any",
        "All",
        "None",
        "Both",
        "Either",
        "Neither",
        "Few",
        "Many",
        "Much",
        "More",
        "Most",
        "Less",
        "Least",
        "First",
        "Second",
        "Third",
        "Last",
        "Next",
        "Previous",
        "Final",
        "New",
        "Old",
        "Young",
        "Good",
        "Bad",
        "Great",
        "Small",
        "Large",
        "Long",
        "Short",
        "High",
        "Low",
        "Fast",
        "Slow",
        "Hard",
        "Easy",
        "Right",
        "Left",
        "Front",
        "Back",
        "Top",
        "Bottom",
        "Side",
        "Middle",
        "Year",
        "Month",
        "Day",
        "Week",
        "Hour",
        "Minute",
        "Man",
        "Woman",
        "Child",
        "Boy",
        "Girl",
        "Person",
        "People",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Hundred",
        "Thousand",
        "Million",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic extractors — all 100% reliable (pure regex)
# ─────────────────────────────────────────────────────────────────────────────


def extract_headings(md_text: str) -> list[dict]:
    """Extract markdown headings (H1-H6). Generic regex."""
    headings = []
    for i, line in enumerate(md_text.split("\n"), 1):
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            headings.append(
                {
                    "level": len(match.group(1)),
                    "title": match.group(2).strip(),
                    "line": i,
                }
            )
    return headings


def extract_all_caps_sections(md_text: str) -> list[dict]:
    """Extract ALL-CAPS section titles (common in academic PDFs). Generic pattern."""
    sections = []
    for i, line in enumerate(md_text.split("\n"), 1):
        stripped = line.strip()
        if (
            len(stripped) > 3
            and stripped.isupper()
            and any(c.isalpha() for c in stripped)
            and not stripped.startswith(("#", "-", "*", "|", ">", "<"))
            and not stripped.endswith(":")
            and not re.search(r"[a-z]", stripped)
        ):
            # Must be a phrase (2+ words) OR a long single word (>=8 chars)
            # 8+ chars catches: CONCLUSION (10), FOREWORD (9), PREFACE (8), REFERENCES (10)
            if len(stripped.split()) >= 2 or len(stripped) >= 8:
                sections.append({"title": stripped, "line": i})
    return sections


# V0.5.4 (Track B3): generic structured-table marker + content extractor.
# Academic / clinical textbooks mark tables with "TABLE N-N." (digits + dash)
# followed by a title line and the markdown-table body (lines starting with
# ``|``). Conservative scope (per task V054-TRACK-B3): ONLY reproduce tables
# explicitly marked ``TABLE N-N.`` — implicit prose tables are not detected.
# Content-agnostic (Rule 1 ✓): the regex matches ANY digit-dash-digit marker,
# no book-specific table numbers are hardcoded.
_TABLE_MARKER_RE = re.compile(
    r"^[ \t]*(TABLE\s+\d+[-\u2013]\d+\.?)\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_MD_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


def extract_structured_tables(md_text: str) -> list[dict]:
    """V0.5.4 (Track B3): extract tables explicitly marked ``TABLE N-N.``.

    Conservative scope (per the V054-TRACK-B3 brief): only tables whose marker
    matches the generic ``TABLE <digits>-<digits>`` shape are reproduced.
    Implicit tables (prose formatted as columns) are NOT detected — the
    explicit-marker contract keeps the reproduction honest (a wrong-shape
    extraction would inject noise).

    Each table is returned as::

        {
            "marker": "TABLE 6-1.",            # the bare marker as it appears
            "title": "<marker's trailing title>",  # marker's trailing title (or "")
            "content_lines": ["| ... |", ...], # the markdown-table rows
            "start_line": int,                 # 1-based marker line
            "end_line": int,                   # 1-based line of last row
        }

    Returns an empty list when no explicit markers are found (the legacy
    behaviour — the renderer falls back to no-table output).
    """
    if not md_text:
        return []
    lines = md_text.split("\n")
    tables: list[dict] = []
    for m in _TABLE_MARKER_RE.finditer(md_text):
        # locate the marker's 1-based line number
        start_line = md_text.count("\n", 0, m.start()) + 1
        # group 1 = the bare "TABLE N-N." marker; group 2 = the trailing
        # title text (everything after the marker on the same line).
        marker = (m.group(1) or "").strip()
        title = (m.group(2) or "").strip()
        # collect contiguous markdown-table rows that follow the marker line.
        content_lines: list[str] = []
        cursor = start_line  # 1-based
        while cursor < len(lines):
            raw = lines[cursor]
            if _MD_TABLE_ROW_RE.match(raw):
                content_lines.append(raw.rstrip())
                cursor += 1
                continue
            # tolerate a single blank line directly under the marker before
            # the first row (PDF extraction sometimes inserts a blank)
            if not content_lines and not raw.strip():
                cursor += 1
                continue
            break
        # require at least one header + one separator + one data row, otherwise
        # this is a marker without a real table body — skip it.
        if len(content_lines) < 2:
            continue
        end_line = start_line + (len(content_lines) - 1)
        tables.append(
            {
                "marker": marker,
                "title": title,
                "content_lines": content_lines,
                "start_line": start_line,
                "end_line": end_line,
            }
        )
    return tables


# V0.5.4 (Track B4): generic structured-diagnostic-criteria extractor.
# Clinical / regulatory documents number criteria with ``a. b. c. d.`` (lower
# Latin letters) and sub-items with ``(i) (ii) (iii)`` (lower Roman numerals
# in parens). Conservative scope: only reproduce lettered lists WITH Roman
# sub-items — prose-only criteria are not reproduced.
# Content-agnostic (Rule 1 ✓): the regex matches the generic shape, no
# book-specific criteria content is hardcoded.
_CRITERION_LETTER_RE = re.compile(
    r"^\s*([a-z])\.\s+(.+)$",
)
_CRITERION_ROMAN_SUBITEM_RE = re.compile(
    r"^\s*\(([ivx]+)\)\s+(.+)$",
)

# V0.5.19: the Roman-numeral sequence machinery for the criteria
# continuation rules — value lookup for the "sequence-extending embedded
# marker" split (rule 4) + the reverse map for the sub-item name.
_ROMAN_ITEM_VALUES = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
_ROMAN_VALUE_NAMES = {v: k for k, v in _ROMAN_ITEM_VALUES.items()}


def _split_embedded_roman_segments(line: str, last_roman_value: int) -> list[tuple[str, int, str]] | None:
    """V0.5.19 (criteria rule 4): split a prose line at EMBEDDED,
    sequence-extending ``(roman)`` markers.

    The PDF hard-wrap family: a wrapped sub-item tail and the NEXT
    sub-item's text land on ONE physical line — "…even if superficially
    warm and charming. (ii) egocentric, self-indulgent, …". The split
    fires ONLY when the embedded marker EXTENDS the active sub-item
    sequence (value == last + 1) — a random ``(iv)`` mention in
    discussion prose never matches the expected value, so the line stays
    prose (no false split).

    Returns ``[("tail", 0, "<pre-marker text>"), ("item", 2, "<text>"),
    …]`` or None when no sequence-extending marker is embedded.
    """
    expected = last_roman_value + 1
    cuts: list[tuple[re.Match, int]] = []
    for mm in re.finditer(r"\(([ivx]+)\)", line):
        rv = _ROMAN_ITEM_VALUES.get(mm.group(1))
        if rv is not None and rv == expected:
            cuts.append((mm, rv))
            expected += 1
    if not cuts:
        return None
    out: list[tuple[str, int, str]] = []
    tail = line[: cuts[0][0].start()].strip().strip(",;")
    if tail:
        out.append(("tail", 0, tail))
    for idx, (mm, rv) in enumerate(cuts):
        end = cuts[idx + 1][0].start() if idx + 1 < len(cuts) else len(line)
        txt = line[mm.end() : end].strip().strip(",;")
        if txt:
            out.append(("item", rv, txt))
    return out


def extract_structured_criteria(md_text: str) -> list[dict]:
    """V0.5.4 (Track B4): extract ``a. b. c. d.`` + ``(i) (ii)`` criteria.

    Conservative scope (per the V054-TRACK-B4 brief): only reproduce lists whose
    items are lettered ``a.`` ``b.`` ``c.`` ``d.`` AND have parenthesized Roman
    sub-items ``(i) (ii) (iii)``. The combination (lettered parent + Roman
    sub-items) is the standard DSM-style diagnostic-criteria shape; bare prose
    or numbered-only lists are not reproduced.

    Returns a list of criteria clusters. Each cluster is the contiguous run of
    lettered items + their Roman sub-items found before a sustained prose break
    (a prose line that does NOT immediately follow a letter or sub-item — the
    signal that the document has moved on to discussion prose). One cluster per
    DSM-style block. Each cluster is::

        {
            "items": [
                {
                    "letter": "a",
                    "text": "Pervasive, unwarranted ...",
                    "sub_items": [("i", "expectation of trickery ..."), ...],
                },
                ...
            ],
            "start_line": int,
        }

    Returns an empty list when no lettered+Roman pattern is found.

    Boundary heuristic: a single blank line between ``a.`` and ``(i)`` is NOT a
    cluster boundary (PDF→MD extraction often wraps the letter on its own line
    with a blank line before the sub-items). The cluster terminates only when a
    non-letter, non-Roman, non-blank prose line appears AND the previous
    non-blank line was itself prose (a sustained prose passage, not a one-line
    continuation of the previous letter's text).
    """
    if not md_text:
        return []
    lines = md_text.split("\n")
    clusters: list[dict] = []
    current_items: list[dict] = []
    current_letter: str | None = None
    current_text: str = ""
    current_subs: list[tuple[str, str]] = []
    cluster_start: int | None = None
    # True when the previous non-blank line was a letter marker or a Roman
    # sub-item — i.e., the cluster is still "active" and a following prose
    # line is a continuation, not a cluster-terminating prose break.
    last_was_marker = False

    def _flush_letter():
        nonlocal current_letter, current_text, current_subs
        if current_letter is not None:
            current_items.append(
                {
                    "letter": current_letter,
                    "text": current_text.strip(),
                    "sub_items": list(current_subs),
                }
            )
        current_letter = None
        current_text = ""
        current_subs = []

    def _flush_cluster():
        nonlocal current_items, cluster_start
        _flush_letter()
        if current_items and cluster_start is not None:
            clusters.append(
                {
                    "items": current_items,
                    "start_line": cluster_start,
                }
            )
        current_items = []
        cluster_start = None

    # V0.5.19 (criteria continuation rules — the "Reproduced Criteria"
    # garble family): the ch.9 V0.5.18 re-run shipped a garbled criteria
    # section because PDF hard-wraps slice sub-item text across lines and
    # paragraph breaks. Four rules fix the family (all shape-based,
    # Rule 1 ✓):
    #   1. a prose line that CONTINUES the pending text must start
    #      LOWERCASE (a mid-sentence wrap); an UPPERCASE-start prose line
    #      after a marker is a NEW paragraph (discussion prose) and CLOSES
    #      the cluster — the old code glued it into the letter's text.
    #   2. a continuation after a SUB-ITEM marker appends to the LAST
    #      SUB-ITEM (the old code appended it to the parent letter's
    #      text — the "(i) ... even if\n\nsuperficially warm and
    #      charming." truncation family).
    #   3. multi-paragraph continuations: a lowercase line may also
    #      continue when the PREVIOUS non-blank line was itself a
    #      lowercase continuation (the "not associated with\npanic
    #      attacks" family).
    #   4. an EMBEDDED sequence-extending ``(roman)`` marker mid-line
    #      splits the line: the pre-marker tail continues the pending
    #      sub-item, the post-marker text starts the next sub-item (the
    #      "charming. (ii) egocentric, ..." family).
    # Plus a duplicate-tail guard (the PDF double-print family — a
    # repeated final word as its own line) and continuation length caps.
    last_roman_value = 0
    last_was_lower_prose = False

    def _append_continuation(txt: str) -> None:
        """Append a continuation line to the pending target: the LAST
        SUB-ITEM when the last marker was a sub-item, else the letter
        text (V0.5.19 rule 2). Duplicate-tail guarded + length capped."""
        nonlocal current_text, current_subs
        t = txt.strip().strip(",;")
        if not t:
            return
        if current_subs and last_roman_value > 0:
            _m0, _t0 = current_subs[-1]
            if _t0.rstrip().lower().endswith(t.lower()):
                return  # duplicate-tail PDF artifact — already the tail
            current_subs[-1] = (_m0, (_t0 + " " + t).strip()[:1000])
        else:
            if current_text.rstrip().lower().endswith(t.lower()):
                return
            current_text = (current_text + " " + t).strip()[:1000]

    for i, raw in enumerate(lines, 1):
        stripped = raw.strip()
        m_let = _CRITERION_LETTER_RE.match(raw)
        m_rom = _CRITERION_ROMAN_SUBITEM_RE.match(raw)
        if m_let:
            if cluster_start is None:
                cluster_start = i
            _flush_letter()
            current_letter = m_let.group(1)
            current_text = m_let.group(2).strip()
            current_subs = []
            last_was_marker = True
            last_was_lower_prose = False
            last_roman_value = 0
        elif m_rom:
            # require an active letter (sub-items under a parent) —
            # otherwise this is a stray Roman list, not a criterion cluster.
            if current_letter is None:
                continue
            current_subs.append((m_rom.group(1), m_rom.group(2).strip()))
            last_was_marker = True
            last_was_lower_prose = False
            last_roman_value = _ROMAN_ITEM_VALUES.get(m_rom.group(1), 0)
        elif stripped == "":
            # blank line: do NOT terminate the cluster (PDF→MD extraction
            # often wraps letters and sub-items on separate lines with a
            # blank in between). Just skip — the next letter/sub-item or
            # prose will decide the cluster's fate.
            continue
        else:
            # prose line — V0.5.19: first try the embedded-marker split
            # (rule 4), then the lowercase-continuation test (rules 1-3).
            _split = _split_embedded_roman_segments(stripped, last_roman_value)
            if _split is not None and current_letter is not None:
                for _kind, _rv, _txt in _split:
                    if _kind == "tail":
                        _append_continuation(_txt)
                    else:
                        current_subs.append((_ROMAN_VALUE_NAMES[_rv], _txt[:1000]))
                        last_roman_value = _rv
                last_was_marker = True
                last_was_lower_prose = False
                continue
            _starts_lower = stripped[:1].islower()
            if (
                current_letter is not None
                and _starts_lower
                and (last_was_marker or last_was_lower_prose)
                and len(stripped) <= 400
            ):
                # a mid-sentence continuation of the pending item text.
                _append_continuation(stripped)
                last_was_marker = False
                last_was_lower_prose = True
            else:
                # NOT a continuation — an uppercase-start prose line (a
                # new paragraph / discussion prose) or a detached line:
                # close the cluster if one is active.
                if cluster_start is not None:
                    _flush_cluster()
                last_was_marker = False
                last_was_lower_prose = False
    if cluster_start is not None:
        _flush_cluster()
    # Final conservative gate: a cluster must have at least one lettered
    # item WITH at least one Roman sub-item (the DSM-style shape contract).
    return [
        {
            "items": [
                it
                for it in c["items"]
                if it.get("sub_items")  # only items that have Roman sub-items
            ],
            "start_line": c["start_line"],
        }
        for c in clusters
        if any(it.get("sub_items") for it in c["items"])
    ]


# V0.5.4 (Track C1): generic author→ALL-CAPS-section mapping.
# Used by the renderer to group key-takeaway bullets under the source's
# ALL-CAPS section headings. Each section's text range is the line interval
# from the section's ALL-CAPS title line to the next ALL-CAPS title line (or
# EOF). Within each interval the existing citation regex extracts authors;
# the union of those authors is the section's author set.
# Content-agnostic (Rule 1 ✓): section boundaries come from the runtime
# extract_all_caps_sections call (generic ALL-CAPS shape); authors come from
# the runtime extract_citations call (generic citation shape). No book-
# specific section names or author names are hardcoded.
def map_authors_to_all_caps_sections(md_text: str) -> list[dict]:
    """V0.5.4 (Track C1): map cited authors to their ALL-CAPS section.

    For each ALL-CAPS section detected by :func:`extract_all_caps_sections`,
    extract the author-year citations in that section's line interval and
    return the section title + the unique authors (in first-appearance order).

    Returns::

        [
            {
                "section_title": "DESCRIPTIVE STUDIES",
                "start_line": int,
                "end_line": int,            # exclusive (next section's line)
                "authors": ["<cited-author-1>", "<cited-author-2>", ...],
            },
            ...
        ]

    Sections with no citations get an empty ``authors`` list (the renderer
    leaves their bullets ungrouped — strict improvement, never a regression).
    """
    if not md_text:
        return []
    sections = extract_all_caps_sections(md_text)
    if not sections:
        return []
    lines = md_text.split("\n")
    section_line_starts = [s["line"] for s in sections]
    out: list[dict] = []
    for idx, sec in enumerate(sections):
        start = sec["line"]
        end = section_line_starts[idx + 1] if idx + 1 < len(section_line_starts) else len(lines) + 1
        # the title line itself is part of the section but rarely carries a
        # citation; slice [start-1 : end-1] (0-based) covers (start .. end-1)
        chunk = "\n".join(lines[start - 1 : end - 1])
        # extract_citations returns deduped authors; preserve first-appearance
        # order for deterministic output across runs.
        cites = extract_citations(chunk)
        seen: set[str] = set()
        authors: list[str] = []
        for c in cites:
            a = c.get("author", "")
            if a and a not in seen:
                seen.add(a)
                authors.append(a)
        out.append(
            {
                "section_title": sec["title"],
                "start_line": start,
                "end_line": end,
                "authors": authors,
            }
        )
    return out


# V0.4.23 (audit V0.4.22, backlog #1): module-level garbage ledger —
# populated by the most recent extract_citations call so the analysis
# report (run_deterministic_analysis) can print the honest filtered line
# without changing the extractor's return contract.
_LAST_GARBAGE_DROPPED: list[tuple[str, str]] = []

# V0.5.7 (audit V0.5.6, the "Maj sey" garble fix): the closed class of
# space-separated surname particles that can appear BEFORE the capitalized
# token of a multi-word surname (van der Waerden / de la Cruz / von Braun).
# V0.5.6's regex had a buggy ``\s+[a-z]{1,4}`` AFTER the capitalized token
# which matched ANY 1-4 letter lowercase word (so OCR-garble "Maj sey 1302"
# was extracted as a 14th-century theorist). The V0.5.7 fix REMOVES the
# after-token group + adds this BEFORE-token restricted-particle prefix
# instead. Content-agnostic (Rule 1 ✓): the list is the closed class of
# generic Romance/Germanic/Arabic surname particles — no book content.
# Source: ``_ALLOWED_SOLID_PREFIXES`` in ``author_garbage.py`` (the
# solid-prefix mirror of the same closed class).
_CIT_PARTICLES = (
    r"(?:van|von|de|del|di|da|du|la|le|les|den|der|ter|ten|"
    r"ben|abu|ibn|al|el|st|lo)\s+"
)

# V0.5.7: the negative-lookbehind-anchored particle prefix group —
# ``(?<!\w)`` ensures the particle starts at a word boundary (so a
# capitalized token like "Maj" is NOT consumed as a particle fragment of
# "aj Sey" — the V0.5.6 bug surfaced when the regex backtracked into the
# interior of a capitalized token). Quantifier ``*`` accepts 0 particles
# (single-token surname) up to 2+ (van der Waerden has 2 particles).
_CIT_PARTICLE_PREFIX = r"(?<!\w)(?:" + _CIT_PARTICLES + r")*"


def extract_citations(md_text: str) -> list[dict]:
    r"""Extract author-year citations. V17.8: Much more robust regex.

    Handles ALL common academic citation styles:
    1. Author (Year) — standard APA/Chicago
    2. Author's (Year) — possessive (Federn's (1952))
    3. Author Year — inline without parens (AuthorZ 1926a)
    4. Author, Year — comma-separated (AuthorI, 1956)
    5. Author et al. (Year) — multi-author
    6. Author and Author (Year) — two authors
    7. (Author, Year) — parenthetical full citation
    8. Author's Year — possessive without parens (AuthorAA's 1950)
    9. Author's concept of X (Year) — mid-sentence possessive
    10. Multi-word surnames (AuthorA, van der Waerden)

    V0.5.7 (audit V0.5.6, the "Maj sey" name-extraction garble fix):
    the V0.5.6 regex captured OCR-garble lines like ``Maj sey 1302`` as
    a 14th-century theorist because of a buggy ``\s+[a-z]{1,4}`` group
    AFTER the capitalized surname token — the group matched ANY 1-4
    letter lowercase word, so the V0.5.6 conv log wasted 4 gap-fill
    rounds trying to attribute a bullet to "Maj sey" before the
    V18.20.3.4 attribution veto gave up. The fix:
    - REMOVES the ``\s+[a-z]{1,4}`` after-token group (the garble's
      root cause — the particle handling is now done by the BEFORE-token
      ``_CIT_PARTICLE_PREFIX`` group).
    - ADDS ``_CIT_PARTICLE_PREFIX`` BEFORE the capitalized surname token,
      restricted to the closed class of Romance/Germanic/Arabic surname
      particles (van / von / de / del / di / da / du / la / le / les /
      den / der / ter / ten / ben / abu / ibn / al / el / st / lo) — so
      multi-word particle-prefix surnames (``van der Waerden (1927)``)
      are now captured as ONE token (was: only "Waerden" — the particle
      prefix was lost).
    - EXTENDS the hyphenated-surname group from ``[-\u2013][A-Z]`` (which
      required the second part to be Capitalized, so ``Maj-sey`` with a
      lowercase second part was silently skipped) to the shared
      ``NAME_SEP[a-zA-Z]+`` class — so hyphenated surnames with a
      lowercase second part are captured as ONE token (the V0.5.4
      ``_SUMMARY_CITATION_RE`` in attribution.py already required
      Capitalized second part via NAME_SEP; the V0.5.7 source-side
      extractor is now consistent with that summary-side mirror's
      NAME_SEP usage, but additionally allows lowercase second parts
      because real-world hyphenated surnames use lowercase second parts
      in Latin script).

    Content-agnostic: no chapter-specific terms.
    """
    citations = []
    seen = set()
    # V0.4.23 (audit V0.4.22, backlog #1): the garbage ledger — every
    # candidate dropped by the shape filter is recorded here (deduped in
    # the return path) so the analysis report can print the honest
    # "garbage-filtered" line for the conversion log.
    _garbage_dropped: list[tuple[str, str]] = []
    # V18.15.5.1 (DEBT-08): shared Unicode-aware apostrophe + dash classes.
    # Used by _add (possessive strip) + all 4 citation patterns below.
    # V0.5.7 (audit V0.5.6): NAME_SEP also imported — the V0.5.7 fix
    # unifies the source-side extractor's hyphenated-surname handling with
    # the summary-side ``_SUMMARY_CITATION_RE`` in attribution.py (which
    # already used NAME_SEP via the V18.15.5.1 DEBT-08 fix).
    from core.preprocessing.citations_regex import APOS as _APOS
    from core.preprocessing.citations_regex import NAME_SEP as _NAME_SEP

    def _add(author, years, cite_type):
        """Deduplicate and add a citation."""
        # V17.9 FIX: Only remove possessive "'s" or "'" SUFFIX, not rstrip
        # (rstrip("'s") was eating trailing 's' from names like 'AuthorJ' → 'Blo')
        # V18.15.3.5: Also handle curly apostrophe (U+2019) from PDF extraction.
        # V18.15.5.1 (DEBT-08): use shared APOS class (adds U+2018 left quote).
        author = re.sub(
            _APOS + r"s$", "", author
        )  # "Federn's" / "Federn's" / "Federn's" → "Federn"
        author = author.rstrip("\u2019\u2018'").strip(
            "',.;:\u2019\u2018"
        )  # trailing apostrophe/punct
        # Remove "et al." suffix for dedup (keep the primary author)
        author = re.sub(r"\s+et\s+al\.?", "", author).strip()
        # V0.4.23: collapse internal whitespace — multi-author captures
        # can span a source line break ("Perry and\nKlerman (1978)");
        # the analysis report and every author-list consumer should see
        # one clean line ("Perry and Klerman").
        author = re.sub(r"\s+", " ", author)
        if not author or len(author) < 2:
            return
        # V0.4.23 (audit V0.4.22, backlog #1): SHAPE FILTER at the root —
        # month names ("May 1975"), mirrored-table OCR strings
        # ("BIOA 0\u06f2\u06f2\u06f6", "Tey \u06f8\u06f68\u06f5", "JOQuUI 8225"),
        # embedded digits ("JeuoNes0A"), ALL-CAPS acronyms ("DSM"),
        # non-Latin scripts and implausible years are NOT authors.
        # Filtered HERE so every consumer (counts, judge, gap-fill
        # hunting, recall floor, check_coverage) sees a clean list —
        # the V0.4.22 run wasted 2 of 5 gap-fill rounds hunting
        # BIOA/Tey/JOQuUI and shipped a fabricated "May" bullet.
        from core.preprocessing.author_garbage import garbage_author_reason

        _reason = garbage_author_reason(author, years)
        if _reason:
            _garbage_dropped.append((author, _reason))
            return
        # V17.9 FIX: Check if the FIRST word is a stopword (catches 'In the', 'By the', etc.)
        _first_word = author.split()[0] if author.split() else author
        if _first_word in _ENGLISH_FALSE_POSITIVES:
            return
        key = f"{author}|{years}"
        if key not in seen:
            seen.add(key)
            citations.append({"author": author, "years": years, "type": cite_type})

    # Pattern 1: Author['s] (Year) or (Year, Year, ...)
    # Handles: "AuthorI (1956)", "AuthorAC's (1952)", "AuthorL's (1964)"
    # Also handles: "AuthorA (1984)", "van der Waerden (1927)" (V0.5.7)
    # V18.15.3.5: Handle curly apostrophes (U+2019) in addition to straight '.
    # PDF extraction often produces curly apostrophes: "Federn's (1952)" —
    # the old regex only matched straight ', missing these citations.
    # V18.15.5.1 (DEBT-08): _APOS imported at function top (shared class
    # adds U+2018 left single quote for completeness).
    # V0.5.7 (audit V0.5.6, "Maj sey" garble fix): the old regex had a buggy
    # ``(?:\s+[a-z]{1,4})?`` group AFTER ``[A-Z][a-zA-Z]+`` that matched ANY
    # 1-4 letter lowercase word — so OCR-garble "Maj sey 1302" was extracted
    # as a 14th-century theorist. Removed; the BEFORE-token
    # ``_CIT_PARTICLE_PREFIX`` (restricted to the closed particle class —
    # van/von/de/der/etc.) now handles multi-word surnames correctly. Also
    # extended the hyphenated-surname group from ``[-\u2013][A-Z]`` (which
    # required Capitalized second part — so "Maj-sey" with lowercase second
    # part was silently skipped) to ``NAME_SEP[a-zA-Z]+`` (allows lowercase
    # second part — unified with the V18.15.5.1 NAME_SEP class).
    for match in re.finditer(
        r"(" + _CIT_PARTICLE_PREFIX + r"[A-Z][a-zA-Z]+(?:" + _NAME_SEP + r"[a-zA-Z]+)?"
        r"(?:" + _APOS + r"[sS]?)?"
        r"(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+(?:" + _NAME_SEP + r"[a-zA-Z]+)?)?"
        r"(?:\s+et\s+al\.?)?)"
        r"\s*\(([0-9]{4}[a-z]?(?:,\s*[0-9]{4}[a-z]?)*(?:\s*,\s*[a-z])*)\)",
        md_text,
    ):
        _add(match.group(1), match.group(2), "parenthetical")

    # Pattern 2: Author['s] Year (without parens) — e.g., "AuthorZ 1926a", "AuthorAA's 1950"
    # V0.5.7: same fix as Pattern 1 (drop buggy ``\s+[a-z]{1,4}`` AFTER group,
    # add ``_CIT_PARTICLE_PREFIX`` BEFORE group, extend hyphenated group to
    # ``NAME_SEP[a-zA-Z]+`` for lowercase-second-part surnames).
    for match in re.finditer(
        r"(" + _CIT_PARTICLE_PREFIX + r"[A-Z][a-zA-Z]+(?:" + _NAME_SEP + r"[a-zA-Z]+)?"
        r"(?:" + _APOS + r"[sS]?)?)"
        r"\s+([0-9]{4}[a-z]?)\b",
        md_text,
    ):
        _add(match.group(1), match.group(2), "inline")

    # Pattern 3: (Author, Year) — parenthetical full citation
    # e.g., "(AuthorZ, 1923a)", "(AuthorL, 1964; AuthorD, 1967)"
    # V0.5.7: extend hyphenated-surname group to ``NAME_SEP[a-zA-Z]+`` (was
    # ``[-\u2013][A-Z]`` which required Capitalized second part — see
    # Pattern 1's V0.5.7 note). No particle-prefix needed inside parens —
    # the open-paren already provides the word boundary that the
    # ``(?<!\w)`` lookbehind would enforce.
    for match in re.finditer(
        r"\(([A-Z][a-zA-Z]+(?:"
        + _NAME_SEP
        + r"[a-zA-Z]+)?(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+(?:"
        + _NAME_SEP
        + r"[a-zA-Z]+)?)?"
        r"(?:\s+et\s+al\.?)?),?\s*([0-9]{4}[a-z]?(?:;\s*[A-Z][a-zA-Z]+(?:"
        + _NAME_SEP
        + r"[a-zA-Z]+)?,?\s*[0-9]{4}[a-z]?)*)\)",
        md_text,
    ):
        _add(match.group(1), match.group(2), "parenthetical_full")

    # Pattern 4: Author, Year (comma-separated, no parens)
    # e.g., "AuthorI, 1956" or "as noted by AuthorL, 1964,"
    # V0.5.7: extend hyphenated-surname group to ``NAME_SEP[a-zA-Z]+`` (was
    # ``[-\u2013][A-Z]`` which required Capitalized second part — see
    # Pattern 1's V0.5.7 note).
    for match in re.finditer(
        r"([A-Z][a-zA-Z]+(?:" + _NAME_SEP + r"[a-zA-Z]+)?),\s*([0-9]{4}[a-z]?)\b", md_text
    ):
        _add(match.group(1), match.group(2), "comma_separated")

    # Pattern 5 (V18.20.3.4, RC-5b — audit v182033): MULTI-AUTHOR
    # enumeration followed by a shared year: "A, B, and C (Year)",
    # "A, B and C (Year)", "A and B (Year)", "A, B, C (Year)".
    # The V18.20.3.3 run's post-checks flagged "AuthorH (1946) not found in
    # source's 34 citations" as a possible name corruption — a FALSE
    # POSITIVE: the source explicitly cites "AuthorV, AuthorH, and AuthorR
    # (1946)", but only the LAST surname before the year ("AuthorR")
    # was extracted by Patterns 1-4, so "AuthorH" and "AuthorV" were absent
    # from the source-author list used for grounding. This pattern adds
    # EVERY name in the enumeration with the shared year. Additive only:
    # existing matches are unaffected (the `seen` dedup keys on
    # author|years, and each split surname is a new key).
    # V0.5.7: extend the multi-author per-name pattern to ``NAME_SEP[a-zA-Z]+``
    # (was ``[-\u2013][A-Z]`` which required Capitalized second part — see
    # Pattern 1's V0.5.7 note). This makes ``"Maj-sey, Tobak (1984)"`` correctly
    # yield 2 surnames ("Maj-sey" + "Tobak") instead of pre-V0.5.7's 0-match
    # (the lowercase second part "sey" failed the old ``[A-Z]`` requirement).
    _NAME = r"[A-Z][a-zA-Z]+(?:" + _NAME_SEP + r"[a-zA-Z]+)?"
    # Two shapes, either of which must be followed by "(Year)":
    #   (a) comma list, optional trailing "and C":  "A, B, C" / "A, B, and C"
    #   (b) plain "and"/"&" pair (no comma):        "A and B" / "A & B"
    _MULTI_NAME_BLOCK = (
        r"(?:"
        + _NAME
        + r"(?:\s*,\s*"
        + _NAME
        + r")+"
        + r"(?:\s*,?\s*(?:and|&)\s+"
        + _NAME
        + r")?"
        + r"|"
        + _NAME
        + r"\s*,?\s+(?:and|&)\s+"
        + _NAME
        + r")"
    )
    for match in re.finditer(
        r"(" + _MULTI_NAME_BLOCK + r")\s*\(([0-9]{4}[a-z]?(?:,\s*[0-9]{4}[a-z]?)*)\)", md_text
    ):
        _names_block, _years = match.group(1), match.group(2)
        # Split the captured block into individual surnames. Split on
        # commas (optionally followed by the "and"/"&" connector) or on a
        # standalone " and " connector — so "A, B, and C" yields
        # ["A", "B", "C"] with no "and C" fragment.
        _name_list = [
            n.strip()
            for n in re.split(r"\s*,\s*(?:(?:and|&)\s+)?|\s+(?:and|&)\s+", _names_block)
            if n.strip()
        ]
        # V18.20.3.5 (audit v182034, 'Finally' bug): STRUCTURAL rejection of
        # sentence-adverb captures. The V18.20.3.4 rig run extracted
        # "Finally" as a theorist because "Finally, AuthorL (1964)" matches
        # the comma-enumeration shape "A, B (Year)". But that shape is NOT a
        # real multi-author citation: standard styles write two authors as
        # "A and B (Year)" / "A & B (Year)" — never "A, B (Year)". A
        # two-name comma list with NO and/& connector is therefore either a
        # sentence-initial discourse marker ("Finally, AuthorL (1964)") or
        # a name-comma-year false shape; in both cases Pattern 1 already
        # captures the real surname ("AuthorL"), so rejecting the whole
        # match loses nothing. Purely structural — no word list. Lists of
        # 3+ names ("A, B, C (Year)") and any list with an and/& connector
        # remain accepted.
        _has_connector = bool(re.search(r"\b(?:and|&)\b", _names_block))
        if len(_name_list) == 2 and not _has_connector:
            continue
        for _nm in _name_list:
            _add(_nm, _years, "multi_author")

    # Pattern 6 (V0.5.18, ch.9 audit MEDIUM): PARENTHETICAL CITATION RUNS —
    # a comma/semicolon enumeration of ``Name[ et al.] year[, year...]``
    # items inside ONE paren pair, with the years NOT in their own parens:
    #   ``(A et al. 1968, 1975, B et al. 1968, 1971, C et al. 1974)``
    #   ``(A 1980, B et al. 1980, C et al. 1988)``
    #   ``(A et al. 1968, 1975)``  (single item)
    # Patterns 1-5 all require the years in their OWN parens (``A et al.
    # (1968)``) or a single name before a bare year (``A 1968``) — the run
    # shape therefore captured only what another pattern happened to hit,
    # so co-cited authors vanished from the deterministic roster (the
    # ch.9 audit found a three-name run that yielded ONE name — the two
    # co-cited authors were absent from the roster every author-coverage
    # veto judges against). Each item is added with ITS years. Additive:
    # existing ``author|years`` keys are deduped by ``_add``; single-item
    # shapes overlap Pattern 2 harmlessly.
    # FP guards: names must start capitalized (so "(see A 1970)" and "(cf.
    # A 1970)" never match) and ``_add``'s existing stopword/garbage
    # filters ("In"/"By"/... — "(In 1965)" is not a citation) apply
    # unchanged. Content-agnostic (Rule 1 ✓): pure citation grammar.
    _RUN_NAME = (
        _NAME
        + r"(?:\s+et\s+al\.?)?"
        + r"(?:" + _APOS + r"[sS]?)?"
    )
    _RUN_ITEM = (
        r"(" + _RUN_NAME + r")"
        r"\s+"
        r"([0-9]{4}[a-z]?(?:\s*,\s*[0-9]{4}[a-z]?)*(?:\s*,\s*[a-z])*)"
    )
    for match in re.finditer(
        r"\((" + _RUN_ITEM + r"(?:\s*[,;]\s*" + _RUN_ITEM + r"*)*)\)",
        md_text,
    ):
        _run = match.group(1)
        for _item in re.finditer(_RUN_ITEM, _run):
            _add(_item.group(1), _item.group(2), "citation_run")

    # V0.4.23: expose the garbage ledger (module-level, deduped,
    # order-preserving) for the analysis report's honest line.
    global _LAST_GARBAGE_DROPPED
    _seen_g: set = set()
    _LAST_GARBAGE_DROPPED = [
        (a, r) for a, r in _garbage_dropped if not (a in _seen_g or _seen_g.add(a))
    ]
    return citations


def count_author_mentions(citations: list[dict], md_text: str) -> list[tuple[str, int, str]]:
    """Count mentions per author, collect years. Generic logic."""
    author_mentions: Counter = Counter()
    author_years: dict[str, set] = defaultdict(set)

    for cite in citations:
        author = cite["author"]
        author_mentions[author] += 1
        for year in re.findall(r"[0-9]{4}[a-z]?", cite["years"]):
            author_years[author].add(year)

    # Count raw text mentions (case-insensitive)
    for author in list(author_mentions.keys()):
        if author in _ENGLISH_FALSE_POSITIVES:
            continue
        # V0.4.23: belt-and-braces — a garbage shape that slipped one of
        # the extraction patterns is dropped here too.
        from core.preprocessing.author_garbage import garbage_author_reason

        if garbage_author_reason(author):
            continue
        count = len(re.findall(r"\b" + re.escape(author) + r"\b", md_text, re.IGNORECASE))
        author_mentions[author] = max(author_mentions[author], count)

    result = []
    for author, count in author_mentions.most_common():
        years = sorted(author_years[author])
        years_str = ", ".join(years) if years else "(no year)"
        result.append((author, count, years_str))
    return result


def extract_numbered_lists(md_text: str, headings: list[dict]) -> list[dict]:
    """Extract numbered lists with section context. Generic regex."""
    lines = md_text.split("\n")
    lists = []
    current_list = []
    last_heading = "(before first heading)"
    heading_at_line = {h["line"]: h["title"] for h in headings}

    for i, line in enumerate(lines, 1):
        if i in heading_at_line:
            if current_list:
                lists.append(
                    {
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
            last_heading = heading_at_line[i]
            continue
        match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if match:
            current_list.append(
                {
                    "number": int(match.group(1)),
                    "text": match.group(2).strip(),
                    "line": i,
                }
            )
        else:
            if current_list and line.strip() == "":
                lists.append(
                    {
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
    if current_list:
        lists.append(
            {"context": last_heading, "items": current_list, "start_line": current_list[0]["line"]}
        )
    return lists


def extract_all_lists_comprehensive(md_text: str, headings: list[dict]) -> list[dict]:
    """V17.7: Extract ALL types of lists from the document.

    Detects:
    1. Numbered lists: "1. item", "2. item" or "1) item"
    2. Bulleted lists: "- item", "* item", "bullet item"
    3. Lettered lists: "A. item", "B. item", "a) item", "b) item", "(a) item", "(b) item"
    4. Roman numeral lists: "I. item", "II. item", "i. item", "ii. item"
    5. Parenthetical numbered: "(1) item", "(2) item"

    Each list is returned with:
    - type: "numbered" | "bulleted" | "lettered" | "roman" | "parenthetical"
    - context: the heading/section the list appears under
    - items: list of {marker, text, line}
    """
    lines = md_text.split("\n")
    lists = []
    current_list = []
    current_type = None
    last_heading = "(before first heading)"
    heading_at_line = {h["line"]: h["title"] for h in headings}

    patterns = {
        "numbered": re.compile(r"^(\d+)[\.\)]\s+(.+)"),
        "bulleted": re.compile(r"^[-*\u2022]\s+(.+)"),
        "lettered_upper": re.compile(r"^([A-Z])[\.\)]\s+(.+)"),
        "lettered_lower": re.compile(r"^([a-z])[\.\)]\s+(.+)"),
        "lettered_paren": re.compile(r"^\(([a-zA-Z])\)\s+(.+)"),
        "roman_upper": re.compile(r"^([IVXLCDM]+)[\.\)]\s+(.+)"),
        "roman_lower": re.compile(r"^([ivxlcdm]+)[\.\)]\s+(.+)"),
        "parenthetical_num": re.compile(r"^\((\d+)\)\s+(.+)"),
    }

    def detect_list_type(line):
        for ptype, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                if ptype == "bulleted":
                    return "bulleted", "\u2022", match.group(1)
                elif ptype == "parenthetical_num":
                    return "parenthetical", f"({match.group(1)})", match.group(2)
                elif ptype == "lettered_paren":
                    return "lettered", f"({match.group(1)})", match.group(2)
                elif ptype in ("lettered_upper", "lettered_lower"):
                    return "lettered", f"{match.group(1)}.", match.group(2)
                elif ptype in ("roman_upper", "roman_lower"):
                    return "roman", f"{match.group(1)}.", match.group(2)
                else:
                    return "numbered", f"{match.group(1)}.", match.group(2)
        return None, None, None

    for i, line in enumerate(lines, 1):
        if i in heading_at_line:
            if current_list:
                lists.append(
                    {
                        "type": current_type,
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
                current_type = None
            last_heading = heading_at_line[i]
            continue

        stripped = line.strip()
        if not stripped:
            if current_list:
                lists.append(
                    {
                        "type": current_type,
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
                current_type = None
            continue

        ltype, marker, text = detect_list_type(stripped)
        if ltype:
            if not current_list:
                current_type = ltype
            current_list.append({"marker": marker, "text": text, "line": i})
        else:
            if current_list and not stripped.startswith(("  ", "\t")):
                lists.append(
                    {
                        "type": current_type,
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
                current_type = None

    if current_list:
        lists.append(
            {
                "type": current_type,
                "context": last_heading,
                "items": current_list,
                "start_line": current_list[0]["line"],
            }
        )

    lists = [lst for lst in lists if len(lst["items"]) >= 2]
    return lists


def extract_inline_lists(md_text: str, headings: list[dict]) -> list[dict]:
    """V18.0: Extract INLINE lists from within paragraphs using context-aware detection.

    Finds (N)...(N+1) sequences, captures 500 chars before the first item
    for header detection, and groups consecutive numbered items.
    Also detects N) item N) item patterns and ordinal lists.

    Returns candidates with context — the LLM verifier (in the summarizer)
    will confirm which are real lists and extract their headers.
    """
    lists = []
    lines = md_text.split("\n")

    heading_at_line = {h["line"]: h["title"] for h in headings}
    last_heading = "(before first heading)"

    # Build paragraphs by joining consecutive non-empty lines
    paragraphs = []
    current_para = []
    for i, line in enumerate(lines, 1):
        if i in heading_at_line:
            if current_para:
                paragraphs.append((" ".join(current_para), last_heading, i - len(current_para)))
                current_para = []
            last_heading = heading_at_line[i]
            continue
        stripped = line.strip()
        if stripped:
            current_para.append(stripped)
        else:
            if current_para:
                paragraphs.append((" ".join(current_para), last_heading, i - len(current_para)))
                current_para = []
    if current_para:
        paragraphs.append((" ".join(current_para), last_heading, len(lines) - len(current_para)))

    # V0.5.19 (paragraph-break join — the numbered-list continuation family):
    # a PDF hard-wrap can split a numbered list item mid-sentence across a
    # paragraph break (the ch.9 audit's 6-ground list captured 5/6 with
    # item (5) truncated — the continuation paragraph "while … ; and (6) …"
    # was never attached). A list paragraph joins its successor when:
    #   - it carries ≥2 inline numbered markers (either `` (N) `` shape),
    #   - it does NOT end with sentence-final punctuation (period/question/
    #     exclamation/colon, after stripping trailing quotes/brackets),
    #   - the successor starts with a LOWERCASE letter (a mid-sentence
    #     continuation — a new discourse paragraph starts uppercase), and
    #   - the joined text stays ≤ 6000 chars + at most 3 joins (bounded).
    # All shape-based (Rule 1 ✓) — no book content involved.
    _v0519_joined: list[tuple[str, str, int]] = []
    _pi = 0
    while _pi < len(paragraphs):
        _ptxt, _phead, _pline = paragraphs[_pi]
        _joins = 0
        while _joins < 3 and _pi + 1 < len(paragraphs):
            _ntxt, _nhead, _nline = paragraphs[_pi + 1]
            if _nhead != _phead:
                break  # a heading boundary never joins
            if len(re.findall(r"\(\d{1,2}\)|(?<!\d)\d{1,2}\)", _ptxt)) < 2:
                break  # not a numbered-list paragraph
            if _ptxt.rstrip("\"'\u201d\u2019)]").rstrip()[-1:] in ".?!:":
                break  # the paragraph is sentence-complete
            if not _ntxt[:1].islower():
                break  # the successor is not a mid-sentence continuation
            if len(_ptxt) + len(_ntxt) + 1 > 6000:
                break  # bounded join
            _ptxt = _ptxt + " " + _ntxt
            _pi += 1
            _joins += 1
        _v0519_joined.append((_ptxt, _phead, _pline))
        _pi += 1
    paragraphs = _v0519_joined

    for para_text, para_heading, para_line in paragraphs:
        # Pattern 1: (1) item (2) item — parenthetical numbered
        # V17.9: Only 1-2 digit numbers (excludes years)
        inline_num = list(re.finditer(r"\((\d{1,2})\)", para_text))
        if len(inline_num) >= 2:
            # Group consecutive items (num increments by 1, or resets to 1)
            groups = []
            current = [inline_num[0]]
            for j in range(1, len(inline_num)):
                prev_num = int(current[-1].group(1))
                curr_num = int(inline_num[j].group(1))
                gap = inline_num[j].start() - current[-1].end()
                if (curr_num == prev_num + 1 or curr_num == 1) and gap < 1000:
                    current.append(inline_num[j])
                else:
                    if len(current) >= 2:
                        groups.append(current)
                    current = [inline_num[j]]
            if len(current) >= 2:
                groups.append(current)

            for grp in groups:
                nums = [int(m.group(1)) for m in grp]
                # Extract item texts: text between this (N) and the next (N+1)
                items = []
                for k, m in enumerate(grp):
                    start = m.end()
                    if k + 1 < len(grp):
                        end = grp[k + 1].start()
                    else:
                        # V18.2.9: Last item — find the sentence boundary.
                        # The old code took 500 chars, which included the
                        # continuation paragraph after the list. Now: find
                        # the first ". " (period + space + capital letter +
                        # word > 2 chars) that indicates a new sentence.
                        _remaining = para_text[start:]
                        _end = len(_remaining)
                        # Search for sentence boundary: ". " followed by capital
                        for _sm in re.finditer(r"\.\s+([A-Z][a-z]{2,})", _remaining):
                            _end = _sm.start() + 1  # include the period
                            break
                        # If no sentence boundary found within 300 chars, cap at 300
                        if _end > 300:
                            _end = 300
                        end = start + _end
                    item_text = para_text[start:end].strip().rstrip(",;.")
                    if item_text and len(item_text) > 3:
                        items.append(
                            {"marker": f"({nums[k]})", "text": item_text, "line": para_line}
                        )

                if len(items) >= 2:
                    # Capture 500 chars before the list for header detection
                    ctx_start = max(0, grp[0].start() - 500)
                    context_before = para_text[ctx_start : grp[0].start()].strip()
                    lists.append(
                        {
                            "type": "inline_numbered",
                            "context": para_heading,
                            "items": items,
                            "start_line": para_line,
                            "header_context": context_before,
                        }
                    )
            continue

        # Pattern 2: 1) item 2) item — closing paren numbered
        # V18.0: Also filter — only match if preceded by a non-digit (not a year fragment)
        close_paren = list(re.finditer(r"(?<!\d)(\d{1,2})\)", para_text))
        if len(close_paren) >= 2:
            groups = []
            current = [close_paren[0]]
            for j in range(1, len(close_paren)):
                prev_num = int(current[-1].group(1))
                curr_num = int(close_paren[j].group(1))
                gap = close_paren[j].start() - current[-1].end()
                if (curr_num == prev_num + 1 or curr_num == 1) and gap < 1000:
                    current.append(close_paren[j])
                else:
                    if len(current) >= 2:
                        groups.append(current)
                    current = [close_paren[j]]
            if len(current) >= 2:
                groups.append(current)

            for grp in groups:
                nums = [int(m.group(1)) for m in grp]
                items = []
                for k, m in enumerate(grp):
                    start = m.end()
                    if k + 1 < len(grp):
                        end = grp[k + 1].start()
                    else:
                        # V18.2.9: Same sentence-boundary fix as Pattern 1
                        _remaining = para_text[start:]
                        _end = len(_remaining)
                        for _sm in re.finditer(r"\.\s+([A-Z][a-z]{2,})", _remaining):
                            _end = _sm.start() + 1
                            break
                        if _end > 300:
                            _end = 300
                        end = start + _end
                    item_text = para_text[start:end].strip().rstrip(",;.")
                    if item_text and len(item_text) > 3:
                        items.append(
                            {"marker": f"{nums[k]})", "text": item_text, "line": para_line}
                        )

                if len(items) >= 2:
                    ctx_start = max(0, grp[0].start() - 500)
                    context_before = para_text[ctx_start : grp[0].start()].strip()
                    lists.append(
                        {
                            "type": "inline_numbered_paren",
                            "context": para_heading,
                            "items": items,
                            "start_line": para_line,
                            "header_context": context_before,
                        }
                    )

    return lists


def format_lists_section(md_text: str) -> str:
    """V18.0: Format ALL lists (block + inline) as a clean reference section.

    This produces a '## Lists & Frameworks' section containing every list
    found in the source chapter — block lists AND inline lists.
    ALWAYS injected (not just when missing).

    V18.0: Inline lists now include their header_context (the text before
    the list that describes what it's about).
    """
    headings = extract_headings(md_text)
    block_lists = extract_all_lists_comprehensive(md_text, headings)
    inline_lists = extract_inline_lists(md_text, headings)

    # Combine and sort by line number
    all_lists = block_lists + inline_lists
    all_lists.sort(key=lambda lst: lst.get("start_line", 0))

    # V18.2.7: Filter out noise lists:
    # 1. YAML frontmatter tags (items that are just quoted words < 15 chars)
    # 2. Lists with only 1 item (not really a list)
    # 3. Lists where all items are < 5 chars (noise)
    filtered_lists = []
    for lst in all_lists:
        items = lst.get("items", [])
        if len(items) < 2:
            continue
        # Check if all items are short quoted words (YAML tags)
        _all_short = all(len(it.get("text", "").strip().strip("\"'")) < 15 for it in items)
        if _all_short:
            # Skip — this is likely YAML frontmatter tags, not a real list
            continue
        filtered_lists.append(lst)
    all_lists = filtered_lists

    if not all_lists:
        return ""

    lines = []
    lines.append("## Lists & Frameworks")
    lines.append("")
    lines.append(
        "<!-- All lists from the source chapter, extracted deterministically (100% reliable)."
    )
    lines.append("Includes block lists (numbered, bulleted, lettered, roman) and inline lists")
    lines.append("(parenthetical numbered, ordinal patterns). -->")
    lines.append("")

    for _i, lst in enumerate(all_lists, 1):
        type_label = {
            "numbered": "Numbered",
            "bulleted": "Bulleted",
            "lettered": "Lettered",
            "roman": "Roman Numeral",
            "parenthetical": "Parenthetical Numbered",
            "inline_numbered": "Inline Numbered (parenthetical)",
            "inline_numbered_paren": "Inline Numbered (closing paren)",
            "inline_lettered": "Inline Lettered",
            "ordinal": "Ordinal (first/second/third)",
        }.get(lst["type"], lst["type"])

        # V18.0: Try to extract a header from the context_before
        header = ""
        if "header_context" in lst and lst["header_context"]:
            ctx = lst["header_context"]

            # V18.2.9: Strategy 1 — Find the last sentence ending with ":"
            # before the list. This sentence almost always introduces the list.
            # Example: "AuthorK emphasized that two conditions must be met for
            # organization of the ego and neutralization of drives to arrive at
            # a sense of identity:" → "Two conditions for ego organization"
            _colon_sentences = re.findall(r"([A-Z][^:]{15,120}):\s*(?=\(\d|$)", ctx)
            if _colon_sentences:
                # Take the last colon-ending sentence as the header
                header = _colon_sentences[-1].strip()
                # Clean up: if it starts with "The" or "This", strip it
                header = re.sub(r"^(The|This|These|Those)\s+", "", header)
            else:
                # V18.2.9: Strategy 2 — Look for "N <plural noun>" patterns
                count_match = re.search(
                    r"(?:(\d+|two|three|four|five|six|seven|eight|nine|ten)\s+)"
                    r"(conditions|categories|aspects|characteristics|factors|"
                    r"types|phases|stages|steps|components|elements|dimensions|"
                    r"forces|connotations|origins|sources|routes|paths|tasks|"
                    r"areas|foundations)\s*(?:of\s+)?([A-Z][^.!?]{5,60})?",
                    ctx,
                    re.IGNORECASE,
                )
                if count_match:
                    num = count_match.group(1)
                    noun = count_match.group(2)
                    subject = count_match.group(3) or ""
                    if subject:
                        header = f"{num} {noun} of {subject}"
                    else:
                        header = f"{num} {noun}"
                else:
                    # V18.2.9: Strategy 3 — Look for "consists of" / "provides"
                    # / "accomplished by" patterns
                    _intro_match = re.search(
                        r"([A-Z][^.!?]{15,80}?)\s+"
                        r"(?:consists of|provides|accomplished by|"
                        r"divided into|organized into|categorized into|"
                        r"described as|proposed|identified)\s",
                        ctx,
                    )
                    if _intro_match:
                        header = _intro_match.group(1).strip()
                    else:
                        header = ""  # no header found — use context

        if header:
            # V18.2.7: Bold the header + add page number if available
            _page = lst.get("page", "")
            _page_str = f" (p.{_page})" if _page else ""
            lines.append(f"### **{header}** — {type_label}, {len(lst['items'])} items{_page_str}")
        else:
            # V18.2.7: Try harder to find a meaningful header from the context
            # If no header found, use the section heading + item count
            _page = lst.get("page", "")
            _page_str = f" (p.{_page})" if _page else ""
            _ctx = lst.get("context", "")
            lines.append(f"### **{_ctx}** — {type_label}, {len(lst['items'])} items{_page_str}")
        lines.append("")
        for item in lst["items"]:
            lines.append(f"{item['marker']} {item['text']}")
        lines.append("")

    return "\n".join(lines)


def extract_bulleted_lists(md_text: str, headings: list[dict]) -> list[dict]:
    """Extract bulleted lists with section context. Generic regex."""
    lines = md_text.split("\n")
    lists = []
    current_list = []
    last_heading = "(before first heading)"
    heading_at_line = {h["line"]: h["title"] for h in headings}

    for i, line in enumerate(lines, 1):
        if i in heading_at_line:
            if current_list:
                lists.append(
                    {
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
            last_heading = heading_at_line[i]
            continue
        match = re.match(r"^[-*]\s+(.+)$", line)
        if match:
            current_list.append({"text": match.group(1).strip(), "line": i})
        else:
            if current_list and line.strip() == "":
                lists.append(
                    {
                        "context": last_heading,
                        "items": current_list,
                        "start_line": current_list[0]["line"],
                    }
                )
                current_list = []
    if current_list:
        lists.append(
            {"context": last_heading, "items": current_list, "start_line": current_list[0]["line"]}
        )
    return lists


def extract_bold_terms(md_text: str) -> list[str]:
    """Extract bold terms. Generic regex."""
    terms = re.findall(r"\*\*(.+?)\*\*", md_text)
    terms.extend(re.findall(r"__(.+?)__", md_text))
    seen = set()
    unique = []
    for t in terms:
        if t not in seen and len(t) > 2:
            seen.add(t)
            unique.append(t)
    return unique


def extract_italic_terms(md_text: str) -> list[str]:
    """Extract italic terms. Generic regex."""
    terms = re.findall(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", md_text)
    seen = set()
    unique = []
    for t in terms:
        if t not in seen and len(t) > 2 and not t.startswith("http"):
            seen.add(t)
            unique.append(t)
    return unique


def extract_block_quotes(md_text: str) -> list[str]:
    """Extract block quotes. Generic regex."""
    return [match.group(1).strip() for match in re.finditer(r"^>\s+(.+)$", md_text, re.MULTILINE)]


def count_words_per_section(md_text: str, headings: list[dict]) -> list[dict]:
    """Count words per section. Generic."""
    if not headings:
        return [
            {
                "section": "(entire document)",
                "word_count": len(md_text.split()),
                "char_count": len(md_text),
            }
        ]
    lines = md_text.split("\n")
    heading_lines = sorted(h["line"] for h in headings)
    sections = []
    for i, h in enumerate(headings):
        start = h["line"]
        end = heading_lines[i + 1] if i + 1 < len(heading_lines) else len(lines) + 1
        text = "\n".join(lines[start:end])
        sections.append(
            {
                "section": h["title"],
                "level": h["level"],
                "word_count": len(text.split()),
                "char_count": len(text),
            }
        )
    return sections


def count_citations_per_section(md_text: str, headings: list[dict]) -> list[dict]:
    """Count citations per section. Generic."""
    if not headings:
        return []
    lines = md_text.split("\n")
    heading_lines = sorted(h["line"] for h in headings)
    sections = []
    for i, h in enumerate(headings):
        start = h["line"]
        end = heading_lines[i + 1] if i + 1 < len(heading_lines) else len(lines) + 1
        text = "\n".join(lines[start:end])
        parenthetical = len(re.findall(r"[A-Z][a-z]+\s*\(\d{4}", text))
        inline = len(re.findall(r"[A-Z][a-z]+\s+\d{4}[a-z]?\b", text))
        sections.append({"section": h["title"], "citation_count": parenthetical + inline})
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# V0.03 (P1-5): Section byline extraction — the anthology attribution signal
# ─────────────────────────────────────────────────────────────────────────────

# A standalone byline: "By" + 1–4 capitalized name tokens (letters,
# apostrophes, hyphens, periods — covers "O'Brien", "Jean-Pierre",
# "St. John"), optional trailing period. Must occupy the WHOLE line —
# "by the way..." mid-sentence never matches (case + whole-line anchors).
_BYLINE_RE = re.compile(
    r"^By\s+([A-Z][A-Za-z.'’\u2019-]*(?:\s+[A-Z][A-Za-z.'’\u2019-]*){0,3})\.?\s*$",
    re.MULTILINE,
)


def extract_bylines(md_text: str) -> list[str]:
    """V0.03 (P1-5): extract standalone ``By <Name>`` bylines, in order.

    Anthologies and essay collections credit each section with its own
    byline. Returns the deduped names in order of first appearance. GENERAL
    pattern only — no name lists, no book-specific tuning. A "byline" that
    is a whole-line ``By ...`` construction with capitalized name tokens.
    """
    if not md_text:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for m in _BYLINE_RE.finditer(md_text):
        name = m.group(1).strip().rstrip(".")
        # Skip degenerate matches ("By The" — a single capitalized token is
        # rarely a name; require ≥2 tokens OR a known-name shape is NOT
        # assumed — keep it simple: 1-token bylines are kept only if the
        # token is ≥4 chars, e.g. "By Voltaire").
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


# ─────────────────────────────────────────────────────────────────────────────
# Main analyzer — runs all extractors + formats output
# ─────────────────────────────────────────────────────────────────────────────


def run_deterministic_analysis(md_text: str) -> str:
    """Run all extractors and format as markdown report. Content-agnostic.

    Returns the analysis as a markdown string.
    """
    headings = extract_headings(md_text)
    all_caps = extract_all_caps_sections(md_text)
    citations = extract_citations(md_text)
    author_counts = count_author_mentions(citations, md_text)
    numbered_lists = extract_numbered_lists(md_text, headings)
    bulleted_lists = extract_bulleted_lists(md_text, headings)
    bold_terms = extract_bold_terms(md_text)
    italic_terms = extract_italic_terms(md_text)
    block_quotes = extract_block_quotes(md_text)
    section_words = count_words_per_section(md_text, headings)
    section_citations = count_citations_per_section(md_text, headings)
    bylines = extract_bylines(md_text)  # V0.03 (P1-5)

    total_words = len(md_text.split())
    total_lines = len(md_text.split("\n"))

    lines = []
    lines.append("# DETERMINISTIC ANALYSIS (100% reliable — produced by regex)")
    lines.append(f"<!-- Generated: {datetime.now().isoformat()} -->")
    lines.append("<!-- Content-agnostic: works on any book, any topic -->")
    lines.append("")

    lines.append("## Document Statistics")
    lines.append(f"- Total lines: {total_lines}")
    lines.append(f"- Total words: {total_words}")
    lines.append(f"- Total characters: {len(md_text)}")
    lines.append(f"- Markdown headings: {len(headings)}")
    lines.append(f"- ALL-CAPS section titles: {len(all_caps)}")
    lines.append(f"- Unique citations: {len(citations)}")
    lines.append(f"- Unique authors: {len(author_counts)}")
    lines.append(f"- Numbered lists: {len(numbered_lists)}")
    lines.append(f"- Bulleted lists: {len(bulleted_lists)}")
    lines.append(f"- Bold terms: {len(bold_terms)}")
    lines.append(f"- Italic terms: {len(italic_terms)}")
    lines.append(f"- Block quotes: {len(block_quotes)}")
    lines.append("")

    lines.append("## Table of Contents")
    if headings:
        for h in headings:
            indent = "  " * (h["level"] - 1)
            lines.append(f"{indent}- [H{h['level']}] {h['title']} (line {h['line']})")
    else:
        lines.append("(no markdown headings found)")
    lines.append("")

    if all_caps:
        lines.append("## ALL-CAPS Section Titles")
        for s in all_caps:
            lines.append(f"- {s['title']} (line {s['line']})")
        lines.append("")

    if author_counts:
        lines.append("## Citations (sorted by mention count)")
        lines.append(f"**Total unique authors: {len(author_counts)}**")
        # V0.4.23 (audit V0.4.22, backlog #1): the honest garbage line —
        # every extraction candidate dropped by the shape filter, with
        # its reason. Keeps the conversion-log audit trail (the V0.4.22
        # ch.4 run hunted BIOA/Tey/JOQuUI "theorists" with no trace of
        # where they came from).
        _dropped = list(_LAST_GARBAGE_DROPPED)
        if _dropped:
            lines.append("")
            lines.append(
                f"Garbage-filtered author candidates: {len(_dropped)} "
                + "; ".join(f"{a} ({r})" for a, r in _dropped[:12])
                + (" …" if len(_dropped) > 12 else "")
            )
        lines.append("")
        for i, (author, count, years) in enumerate(author_counts, 1):
            lines.append(f"{i}. **{author}** ({count} mentions): {years}")
        lines.append("")

    # V0.03 (P1-5, real-rig audit): section bylines. Anthology books credit
    # each essay with a standalone "By <Name>" line. The V0.02 rig summaries
    # erased authorship entirely (zero author names in an 8-author extract)
    # — for anthologies, attribution IS core content. GENERAL pattern: a
    # line consisting solely of "By" + a 1–4 token capitalized name.
    if bylines:
        lines.append("## Section Bylines (anthology authors — attribute ideas to these authors)")
        for i, name in enumerate(bylines, 1):
            lines.append(f"{i}. {name}")
        lines.append("")

    if numbered_lists:
        lines.append("## Numbered Lists")
        for i, nl in enumerate(numbered_lists, 1):
            lines.append(f"### List {i} (under: {nl['context']}, {len(nl['items'])} items)")
            for item in nl["items"]:
                lines.append(f"{item['number']}. {item['text']}")
            lines.append("")
        lines.append("")

    if bulleted_lists:
        lines.append("## Bulleted Lists")
        for i, bl in enumerate(bulleted_lists, 1):
            lines.append(f"### List {i} (under: {bl['context']}, {len(bl['items'])} items)")
            for item in bl["items"]:
                lines.append(f"- {item['text']}")
            lines.append("")
        lines.append("")

    if bold_terms:
        lines.append("## Bold Terms (potential key concepts)")
        for term in bold_terms:
            lines.append(f"- {term}")
        lines.append("")

    if italic_terms:
        lines.append("## Italic Terms (potential key definitions)")
        for term in italic_terms[:50]:
            lines.append(f"- {term}")
        if len(italic_terms) > 50:
            lines.append(f"- ... and {len(italic_terms) - 50} more")
        lines.append("")

    if block_quotes:
        lines.append("## Block Quotes")
        for q in block_quotes:
            lines.append(f"> {q}")
        lines.append("")

    if section_words:
        lines.append("## Section Word Counts")
        for s in sorted(section_words, key=lambda s: s["word_count"], reverse=True):
            lines.append(f"- **{s['section']}**: {s['word_count']} words")
        lines.append("")

    if section_citations:
        lines.append("## Citations Per Section")
        for s in sorted(section_citations, key=lambda s: s["citation_count"], reverse=True):
            lines.append(f"- **{s['section']}**: {s['citation_count']} citations")
        lines.append("")

    return "\n".join(lines)


def analyze_segment_file(segment_path) -> str:
    """Run deterministic analysis on a segment .md file.

    Reads the segment, runs the analysis, and writes the result to
    ``{segment_stem}_analysis.md`` in the same directory.

    Args:
        segment_path: path to the segment .md file (str or Path)

    Returns:
        The path to the analysis file (as a string).

    Raises:
        Exception if the segment file cannot be read.
    """
    segment_path = Path(segment_path)
    md_text = segment_path.read_text(encoding="utf-8")
    analysis = run_deterministic_analysis(md_text)
    analysis_path = segment_path.parent / f"{segment_path.stem}_analysis.md"
    analysis_path.write_text(analysis, encoding="utf-8")
    return str(analysis_path)


def load_analysis_for_segment(segment_path) -> str:
    """Load the pre-computed analysis for a segment, if it exists.

    Args:
        segment_path: path to the segment .md file (str or Path)

    Returns:
        The analysis text, or empty string if the analysis file
        doesn't exist (non-fatal — the pipeline falls back to no-analysis mode).
    """
    segment_path = Path(segment_path)
    analysis_path = segment_path.parent / f"{segment_path.stem}_analysis.md"
    if analysis_path.exists():
        try:
            return analysis_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read analysis for %s: %s", segment_path.name, e)
            return ""
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# V17.5: Shared helper — replaces the fragile heading-to-filename matching
# ─────────────────────────────────────────────────────────────────────────────

# V18.20.4.8 (P6 / O-a6): module-level scan cache for the whole-tree
# *_analysis.md listing. Key: resolved output-dir path. Value:
# (dir mtime_ns, analysis_files list). A second call with the same dir and
# an unchanged dir mtime reuses the cached listing instead of re-walking
# the tree. Invalidation: the output dir's own mtime (a new/deleted direct
# entry, e.g. the segments folder mkdir at output-save time, bumps it).
# Capped FIFO (dicts preserve insertion order) so a long-lived process
# cycling output dirs can't grow it unboundedly.
_ANALYSIS_SCAN_CACHE: dict[str, tuple[int, list]] = {}
_ANALYSIS_SCAN_CACHE_MAX = 32


def _list_analysis_files(output_dir: Path) -> list:
    """List *_analysis.md under output_dir, cached per dir + dir mtime (O-a6)."""
    try:
        key = str(output_dir.resolve())
    except Exception:
        key = str(output_dir)
    try:
        dir_mtime = output_dir.stat().st_mtime_ns
    except OSError:
        dir_mtime = -1  # missing/unreadable dir — rglob yields nothing anyway
    cached = _ANALYSIS_SCAN_CACHE.get(key)
    if cached is not None and cached[0] == dir_mtime:
        return cached[1]
    files = list(output_dir.rglob("*_analysis.md"))
    if len(_ANALYSIS_SCAN_CACHE) >= _ANALYSIS_SCAN_CACHE_MAX:
        _ANALYSIS_SCAN_CACHE.pop(next(iter(_ANALYSIS_SCAN_CACHE)), None)
    _ANALYSIS_SCAN_CACHE[key] = (dir_mtime, files)
    return files


# V18.20.4.11 (P1): heading-aware analysis lookup. Previously
# find_analysis_for_heading IGNORED its heading parameter and returned the
# FIRST readable *_analysis.md file tree-wide — in multi-segment books (the
# norm since the V18.20.4.10 segmentation fixes) EVERY chapter therefore got
# segment-001's analysis injected: wrong-chapter authors/keywords polluted
# prompts, coverage probes, gap-fill, the recall floor and the thorough-
# theorist floor. The helpers below implement the matching ladder.


def _analysis_segment_stem(analysis_path: Path) -> str:
    """V18.20.4.11 (P1): analysis file stem minus its TRAILING _analysis
    marker (= the segment file's stem, as written by output_save). Unlike
    the former ``.replace("_analysis", "")`` this leaves an embedded
    ``_analysis`` (a heading that literally contains that word) intact."""
    stem = analysis_path.stem
    if stem.endswith("_analysis"):
        return stem[: -len("_analysis")]
    return stem


def _select_analysis_for_heading(analysis_files, heading, log_fn=None):
    """V18.20.4.11 (P1): pick THIS heading's analysis file among many.

    Matching ladder (see find_analysis_for_heading):
      1. exact slug   — segment_filename_slug(heading) vs the file stem
                        (``{idx:03d}_{slug}`` or bare ``{slug}``); >1 hit
                        (duplicate chapter headings) → WARNING + first
                        (deterministic, no worse than the old first-match)
      2. fuzzy        — difflib ratio ≥ 0.75, normalized heading vs
                        stem-minus-index; ties → first + WARNING
      3. no match     → (None, "no-match") — caller FAILS CLOSED

    Never raises; returns (Path, method) or (None, reason).
    """
    # V18.20.4.11 (P1): iterate in NAME order, not rglob/filesystem order —
    # "the first" candidate must be deterministic across platforms (rglob
    # yields scandir order, which differs between ext4/tmpfs/APFS). With the
    # zero-padded {idx:03d} prefix, name order == segment order.
    ordered = sorted(analysis_files, key=lambda p: p.name)
    slug = segment_filename_slug(heading or "")

    # ── 1. exact slug match ──
    candidates = []
    if slug:
        _pat = re.compile(rf"^\d+_{re.escape(slug)}$")
        for f in ordered:
            stem = _analysis_segment_stem(f)
            if _pat.match(stem) or stem == slug:
                candidates.append(f)
    if len(candidates) == 1:
        if log_fn:
            log_fn(
                f"    [V17.5] Analysis for '{heading}' → {candidates[0].name} (match: exact slug)",
                "INFO",
            )
        return candidates[0], "exact-slug"
    if len(candidates) > 1:
        if log_fn:
            log_fn(
                f"    [V17.5] ⚠️ AMBIGUOUS analysis match for heading '{heading}': "
                f"{len(candidates)} files share the same segment slug "
                f"({', '.join(f.name for f in candidates)}) — using the first",
                "WARNING",
            )
        return candidates[0], "slug-ambiguous"

    # ── 2. fuzzy fallback (near-miss headings: whitespace/case drift) ──
    norm_h = re.sub(r"\s+", " ", (heading or "").strip().lower())
    if norm_h:
        best = None
        best_ratio = 0.0
        tied = False
        for f in ordered:
            stem_n = re.sub(r"^\d+_", "", _analysis_segment_stem(f), count=1)
            stem_n = re.sub(r"\s+", " ", stem_n.replace("_", " ").strip().lower())
            if not stem_n:
                continue
            ratio = difflib.SequenceMatcher(None, norm_h, stem_n).ratio()
            if ratio > best_ratio:
                best, best_ratio, tied = f, ratio, False
            elif ratio == best_ratio and best is not None:
                tied = True
        if best is not None and best_ratio >= 0.75:
            if tied:
                if log_fn:
                    log_fn(
                        f"    [V17.5] ⚠️ fuzzy analysis match for heading '{heading}' "
                        f"is TIED at {best_ratio:.2f} — using first: {best.name}",
                        "WARNING",
                    )
                return best, "fuzzy-tied"
            if log_fn:
                log_fn(
                    f"    [V17.5] Analysis for '{heading}' → {best.name} (match: fuzzy {best_ratio:.2f})",
                    "INFO",
                )
            return best, "fuzzy"

    # ── 3. fail-closed ──
    if log_fn:
        log_fn(
            f"    [V17.5] ⚠️ No analysis matches heading '{heading}' "
            f"({len(analysis_files)} candidates found) — injecting NOTHING "
            f"(fail-closed: a missing analysis degrades gracefully, a "
            f"wrong-chapter analysis is hallucination fuel)",
            "WARNING",
        )
    return None, "no-match"


def find_analysis_for_heading(output_dir, heading: str, log_fn=None) -> tuple[str, str]:
    """V17.5/V18.20.4.11: Find the deterministic analysis for a given chapter heading.

    V18.20.4.11 (P1): the ``heading`` parameter is now USED (V17.5 ignored
    it and returned the FIRST readable *_analysis.md tree-wide — every
    chapter in a multi-segment book got segment-001's analysis). Matching
    ladder, in order:

    1. No analysis files anywhere → ("", "") (unchanged).
    2. Exactly ONE analysis file → returned regardless of heading
       (legacy single-segment behavior; preserves all V17.5-era pins).
    3. MULTIPLE files → exact slug match on
       ``segment_filename_slug(heading)`` (the same transformation
       output_save uses to name ``{idx:03d}_{slug}.md`` / its
       ``_analysis.md`` twin): 1 hit wins; >1 hits (duplicate chapter
       headings) → WARNING + first (deterministic).
    4. No slug hit → difflib fuzzy fallback (ratio ≥ 0.75) on the
       normalized heading vs stem-minus-index; ties → first + WARNING.
    5. Still nothing → LOUD WARNING + ("", "") — FAIL-CLOSED: a missing
       analysis degrades gracefully (probes report unavailable per the S1
       fail-soft design) while a wrong-chapter analysis is hallucination
       fuel. (V17.5 injected the first file = wrong-chapter content.)

    Args:
        output_dir: the conversion output directory (Path or str)
        heading: the chapter heading (USED since V18.20.4.11 — matched
            against the segment-filename slug produced by output_save)
        log_fn: optional log callback(msg, level)

    Returns:
        (segment_path, analysis_text) — or ("", "") if not found.
    """
    output_dir = Path(output_dir)

    if log_fn:
        log_fn(f"    [V17.5] Searching for analysis files in: {output_dir}", "DEBUG")

    # Search the entire output tree for *_analysis.md files
    # V18.20.4.8 (P6 / O-a6): the whole-tree rglob was re-run on EVERY call
    # (2x/chapter + gap-fill = O(chapters * tree)); the scan is now cached
    # per resolved output dir with mtime invalidation (see
    # _list_analysis_files). Analysis files are written by output_save
    # BEFORE summarization starts and don't change mid-run, and the mtime
    # check catches direct-entry changes; the per-file read_text below is
    # still live (fresh text each call, iteration order preserved).
    analysis_files = _list_analysis_files(output_dir)

    if not analysis_files:
        if log_fn:
            log_fn(f"    [V17.5] No *_analysis.md files found anywhere under {output_dir}", "DEBUG")
        return "", ""

    if log_fn:
        log_fn(
            f"    [V17.5] Found {len(analysis_files)} analysis file(s): {[f.name for f in analysis_files]}",
            "DEBUG",
        )

    # V18.20.4.11 (P1): heading-aware selection. Single analysis file →
    # legacy behavior (it is THE analysis for the whole run — single-
    # segment books, all V17.5-era expectations). Multiple files → the
    # matching ladder in _select_analysis_for_heading; no match → FAIL
    # CLOSED ("", "") rather than injecting another chapter's analysis.
    if len(analysis_files) == 1:
        selected = analysis_files[0]
        method = "single-file"
    else:
        selected, method = _select_analysis_for_heading(analysis_files, heading, log_fn=log_fn)
        if selected is None:
            # _select_analysis_for_heading already logged the LOUD WARNING.
            return "", ""

    # The segment file is the same name without the trailing _analysis marker
    segment_stem = _analysis_segment_stem(selected)
    segment_path = selected.parent / f"{segment_stem}.md"

    try:
        analysis_text = selected.read_text(encoding="utf-8")
    except Exception as e:
        if log_fn:
            log_fn(f"    [V17.5] Failed to read {selected.name}: {e}", "WARNING")
        return "", ""
    if not analysis_text:
        # V18.20.4.11 (P1): empty selected analysis → fail-closed (the old
        # loop skipped it and silently fell through to the NEXT chapter's
        # file — same wrong-content class as the heading bug).
        if log_fn and method != "single-file":
            log_fn(
                f"    [V17.5] ⚠️ Selected analysis file is empty: {selected.name} — injecting NOTHING",
                "WARNING",
            )
        return "", ""

    if log_fn:
        log_fn(
            f"    [V17.5] Using analysis: {selected.name} ({len(analysis_text)} chars), segment: {segment_path.name}",
            "DEBUG",
        )
    return str(segment_path), analysis_text


def analysis_exists(output_dir, log_fn=None) -> bool:
    """V17.5: Simple check — does ANY analysis file exist in the output dir?

    Used by the V17.4 skip conditions (concept extraction #5, gap-fill) to
    decide whether to skip the old LLM-based approaches.

    Args:
        output_dir: the conversion output directory (Path or str)
        log_fn: optional log callback

    Returns:
        True if at least one *_analysis.md file exists, False otherwise.
    """
    output_dir = Path(output_dir)
    analysis_files = list(output_dir.rglob("*_analysis.md"))
    exists = len(analysis_files) > 0
    if log_fn:
        if exists:
            log_fn(
                f"    [V17.5] Analysis exists: {len(analysis_files)} file(s) found — V17.4 skips ENABLED",
                "DEBUG",
            )
        else:
            log_fn(
                "    [V17.5] No analysis files found — V17.4 skips DISABLED (old behavior)", "DEBUG"
            )
    return exists


def extract_authors_from_analysis(analysis: str) -> list[str]:
    """Extract author names from the deterministic analysis output.

    Parses the '## Citations' section and returns a list of author names.

    V18.20.4.8 (P6 / O-a3): the regex parse of the Citations section is now
    memoized (``_extract_authors_cached``) — this helper is called 11+ times
    per chapter (judges, gap-fill, recall floor, thorough floor), including
    inside a per-bullet loop (``recall_floor.coverage_aware_cap``), and the
    analysis text is the SAME string each time. The public wrapper still
    returns a fresh list per call (identical semantics for callers that
    mutate the result).
    """
    if not analysis:
        return []
    return list(_extract_authors_cached(analysis))


@lru_cache(maxsize=512)
def _extract_authors_cached(analysis: str) -> tuple:
    """Immutable core of :func:`extract_authors_from_analysis` (O-a3).

    Pure: (analysis text) -> tuple of author names — no mutable state, no
    I/O, no globals; identical output for identical input, so caching is
    sound. Returns a tuple (hashable, immutable) so cached entries can
    never be poisoned by caller-side mutation.
    """
    # Find the citations section
    cite_match = re.search(r"## Citations.*?\n(.*?)(?=\n## |\Z)", analysis, re.DOTALL)
    if not cite_match:
        return ()
    cite_block = cite_match.group(1)
    # Each line: "N. **Author** (count mentions): years"
    authors = []
    for line in cite_block.split("\n"):
        m = re.match(r"\d+\.\s+\*\*(.+?)\*\*", line)
        if m:
            authors.append(m.group(1).strip())
    return tuple(authors)


def _edit_distance_le1(a: str, b: str) -> bool:
    """True when two equal-length lowercase words differ in at most one
    position, or either is the other plus/minus one character (classic
    bounded edit distance 1, early-exit). Used only for words >= 4 chars
    with the same first letter, which keeps it tight."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b, strict=False) if x != y) <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la  # a is now the shorter
    # deletion check: b must reduce to a by removing one char
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _author_in_summary(author: str, summary_lower: str, summary_tokens: set) -> bool:
    """V18.20.3.5 (audit v182034, a false-missing pair from a dropped-letter garble):
        garble-tolerant author-presence check.

        The V18.14 judge ran on the pre-repair summary text in which the model
    had written "AuthorM and AuthorN-garble" (single-char garble of the second name).
    The exact substring check failed, the pair
        was reported missing from bullets AND thorough, and gap-fill generated
        a redundant bullet for an author that was already covered — the exact
        duplicate class the V18.20.3.4 dedup then had to clean up.

        Fundamental fix (content-agnostic): an author is covered when every
        NAME token of the author (connectors \"and\"/\"&\" skipped) appears in
        the summary either exactly or as an edit-distance-1 neighbor (same
        first letter, length >= 4) of some summary token. This matches the
    same garble class the postcheck auto-repair fixes (dropped-letter
        same garble class the postcheck auto-repair fixes (dropped-letter
        'emergs'->'emerges'), so the judge and the repair layer finally agree
        match — d1 on short words is too noisy.
    """
    if author.lower() in summary_lower:
        return True  # fast path: exact substring
    tokens = [t for t in author.split() if t not in ("and", "&")]
    if not tokens:
        return False
    for tok in tokens:
        tl = tok.lower()
        if tl in summary_tokens:
            continue  # this token found exactly
        if len(tl) < 4:
            return False  # short name token absent — not covered
        # garble-tolerant: some summary token within edit distance 1,
        # same first letter, comparable length
        if not any(
            len(st) >= 4
            and st[0] == tl[0]
            and abs(len(st) - len(tl)) <= 1
            and _edit_distance_le1(st, tl)
            for st in summary_tokens
        ):
            return False
    return True


def check_coverage(analysis: str, summary_text: str) -> dict:
    """V17.3: Deterministic coverage check — did gemma mention all authors?

    This is the JUDGE step: after gemma produces its summary, this function
    checks whether every author from the deterministic analysis appears in
    the summary text.

    Args:
        analysis: the deterministic analysis text (from the analysis .md file)
        summary_text: gemma's summary (exec_summary + bullets + thorough_summary combined)

    Returns:
        Dict with:
            - 'total': total authors found by deterministic layer
            - 'covered': list of authors found in the summary
            - 'missing': list of authors NOT found in the summary
            - 'coverage_pct': float 0.0-1.0

    V18.20.4.8 (P6 / O-a3): the computation is memoized on
    (analysis, summary_text) via ``_check_coverage_cached`` (the per-bullet
    recall-floor loop calls this with the same analysis and up to ~100
    distinct bullets). The public wrapper rebuilds a fresh dict per call —
    identical semantics for callers that read (or mutate) the result.
    """
    _total, _covered, _missing, _pct = _check_coverage_cached(analysis, summary_text)
    return {
        "total": _total,
        "covered": list(_covered),
        "missing": list(_missing),
        "coverage_pct": _pct,
    }


@lru_cache(maxsize=512)
def _check_coverage_cached(analysis: str, summary_text: str) -> tuple:
    """Immutable core of :func:`check_coverage` (O-a3).

    Pure: (analysis, summary_text) -> (total, covered_tuple, missing_tuple,
    coverage_pct) — no mutable state, no I/O, no globals. The author parse
    reuses ``_extract_authors_cached`` so the Citations regex runs once per
    distinct analysis text, not once per call site / per bullet.
    """
    if not analysis:
        return (0, (), (), 1.0)
    authors = _extract_authors_cached(analysis)
    if not authors:
        return (0, (), (), 1.0)

    summary_lower = summary_text.lower()
    # V18.20.3.5: token set built once for the garble-tolerant path.
    summary_tokens = set(re.findall(r"\b[a-z][a-z]{2,}\b", summary_lower))
    covered = []
    missing = []
    for author in authors:
        # V18.20.3.5: exact substring OR garble-tolerant token match
        if _author_in_summary(author, summary_lower, summary_tokens):
            covered.append(author)
        else:
            missing.append(author)

    coverage_pct = len(covered) / len(authors) if authors else 1.0
    return (len(authors), tuple(covered), tuple(missing), coverage_pct)


def check_numbered_list_coverage(analysis: str, summary_text: str) -> dict:
    """V17.3: Check if numbered list items from the analysis are covered.

    For each numbered list item in the analysis, check if key words from
    that item appear in the summary.
    """
    if not analysis:
        return {"total": 0, "covered": [], "missing": [], "coverage_pct": 1.0}

    # Find numbered list sections
    list_matches = re.findall(
        r"### List \d+ \(under: (.+?), (\d+) items\)\n((?:\d+\..+\n?)+)", analysis
    )
    if not list_matches:
        return {"total": 0, "covered": [], "missing": [], "coverage_pct": 1.0}

    all_items = []
    for _context, _count, items_block in list_matches:
        for item_match in re.finditer(r"\d+\.\s+(.+)", items_block):
            all_items.append(item_match.group(1).strip())

    if not all_items:
        return {"total": 0, "covered": [], "missing": [], "coverage_pct": 1.0}

    summary_lower = summary_text.lower()
    covered = []
    missing = []
    for item in all_items:
        # Check if key words (first 3 words) appear in the summary
        words = item.lower().split()[:4]
        if all(w in summary_lower for w in words):
            covered.append(item)
        else:
            missing.append(item)

    coverage_pct = len(covered) / len(all_items) if all_items else 1.0
    return {
        "total": len(all_items),
        "covered": covered,
        "missing": missing,
        "coverage_pct": coverage_pct,
    }
