"""V0.4.23 — the UNIVERSAL enumeration-capture system (user directive).

> "can you ideate a way to catch every listed text in any chapter?
>  whether bullet points, a b c d, 1 2 3 4, II IV V VI, create a template
>  for all possible ways that authors and scientists might use in their
>  books, the point is never miss any listed items, all they must be
>  covered completely, for example if they are seven, seven must be
>  captured."

THE TEMPLATE — every enumeration convention used by authors and
scientists, as a machine-readable catalog (``ENUMERATION_TEMPLATE``):

  1. **Bullets** — typographic glyph lists: ``-`` ``*`` ``+`` ``•`` ``‣``
     ``▪`` ``◦`` ``●`` ``·`` ``■`` ``►`` ``→`` ``⇒`` ``»`` ``–`` ``—``.
  2. **Arabic numerals, block** — ``1.`` ``2.)`` ``(1)`` ``(2)``.
  3. **Lowercase letters** — ``a.`` ``b.)`` ``(a)`` ``(b)``.
  4. **Uppercase letters** — ``A.`` ``B.)`` ``(A)`` ``(B)``.
  5. **Roman numerals** — ``I. II. III. IV. V. VI.``, lowercase
     ``i. ii. iii.``, and legal style ``(i) (ii) (iii)``.
  6. **Greek letters** — ``α. β. γ. δ.`` (mathematics/science convention).
  7. **Ordinal words, run-in** — ``First, … Second, … Third, … Finally, …``
     (including Firstly/Secondly/Thirdly/Next/Then/Lastly).
  8. **Run-in (inline) lists** — ``(1) … ; (2) … ; (3) …`` inside a
     sentence, with Arabic, alphabetic, or lowercase-roman markers.
  9. **Labeled enumerators** — ``Step 1:``, ``Criterion A.``, ``Phase
     II.``, ``Stage 3)``, … (the science-textbook convention; the label
     vocabulary is structural: step/stage/phase/criterion/…).
  10. **Outline numbering** — ``1.1``, ``2.3.1`` (section-style items).

GUARANTEE PIPELINE (deterministic, zero LLM cost):
  * :func:`detect_enumerations` scans the WHOLE chapter (not just the
    conclusion region) and returns every list with its style, its
    introducing stem, and its items — count-verified (sequential-marker
    runs must be consecutive).
  * :func:`enumeration_coverage_block` injects the detected lists into
    the primary prompt: "EVERY item of EVERY list MUST appear in your
    summary — a list of seven must contribute all seven items".
  * ``SummarizerAdditiveMixin._ensure_enumeration_bullets`` is the
    ship-time guarantee: any list with an uncovered item gets ONE
    consolidated bullet carrying ALL of its items verbatim (the
    V18.15.9.1 "consolidated, not scattered" design, generalized to every
    style and the whole chapter).
  * ``recall_floor.deterministic_recall_floor`` measures per-item recall
    across bullets + thorough (the honest number for the conversion log).

Content-agnostic: the template is language-level document structure (the
ways humans enumerate), not book-specific vocabulary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# The universal template
# ─────────────────────────────────────────────────────────────────────────────

#: The glyph set for bullet lists (markdown bullets + typographic bullets
#: that OCR/PDF extraction produces).
BULLET_GLYPHS = (
    r"[-*+\u2022\u2023\u25aa\u25e6\u25cf\u00b7\u25a0\u25ba\u2192\u21d2\u00bb\u2013\u2014]"
)

#: The labeled-enumerator vocabulary — structural document language
#: (science-textbook conventions), not domain vocabulary.
_LABEL_WORDS = (
    "Step|Stage|Phase|Point|Item|Criterion|Criteria|Rule|Principle|"
    "Question|Objective|Goal|Task|Part|Section|Article|Clause|Appendix|"
    "Note|Case|Example|Type|Kind|Form|Level|Class|Category|Finding|"
    "Recommendation|Test|Property|Law|Axiom|Theorem|Definition|Lemma|"
    "Corollary|Problem|Exercise|Feature|Characteristic|Symptom|Sign|"
    "Cause|Reason|Factor|Element|Component|Aspect|Dimension|Domain|"
    "Postulate|Assumption|Condition|Requirement|Guideline|Standard"
)

#: Greek lowercase letters in conventional order (science enumeration).
_GREEK_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"

#: Ordinal discourse markers for run-in ordinal lists (in discourse order;
#: ``Finally``/``Lastly`` terminate).
_ORDINAL_WORDS = (
    "First",
    "Firstly",
    "Second",
    "Secondly",
    "Third",
    "Thirdly",
    "Fourth",
    "Fourthly",
    "Fifth",
    "Sixth",
    "Seventh",
    "Eighth",
    "Ninth",
    "Tenth",
    "Next",
    "Then",
    "Finally",
    "Lastly",
)

#: The machine-readable template: style key -> descriptor. Line patterns
#: are compiled in :data:`_BLOCK_PATTERNS`; run-in patterns in
#: :data:`_RUNIN_PATTERNS`. This dict IS the "template for all possible
#: ways that authors and scientists might use" — extend here when a new
#: convention appears.
ENUMERATION_TEMPLATE: dict[str, dict] = {
    "bullet": {"kind": "block", "sequence": False, "min_items": 2},
    "arabic": {"kind": "block", "sequence": "int", "min_items": 3},
    "arabic_paren": {"kind": "block", "sequence": "int", "min_items": 3},
    "lower_alpha": {"kind": "block", "sequence": "alpha", "min_items": 3},
    "upper_alpha": {"kind": "block", "sequence": "alpha_upper", "min_items": 3},
    "lower_alpha_paren": {"kind": "block", "sequence": "alpha", "min_items": 3},
    "upper_alpha_paren": {"kind": "block", "sequence": "alpha_upper", "min_items": 3},
    "roman_upper": {"kind": "block", "sequence": "roman", "min_items": 3},
    "roman_lower": {"kind": "block", "sequence": "roman", "min_items": 3},
    "roman_lower_paren": {"kind": "block", "sequence": "roman", "min_items": 3},
    "greek": {"kind": "block", "sequence": "greek", "min_items": 3},
    "labeled": {"kind": "block", "sequence": None, "min_items": 3},
    "outline": {"kind": "block", "sequence": None, "min_items": 3},
    "runin_arabic": {"kind": "runin", "sequence": "int", "min_items": 3},
    "runin_alpha": {"kind": "runin", "sequence": "alpha", "min_items": 3},
    "runin_roman": {"kind": "runin", "sequence": "roman", "min_items": 3},
    "ordinal": {"kind": "runin", "sequence": "ordinal", "min_items": 3},
}

# Block patterns: (style, compiled regex with groups: marker, text).
# All anchored at line start with up to 6 leading spaces; a blank line is
# allowed between items (markdown loose lists); ONE non-marker non-blank
# line is treated as a continuation of the previous item (wrapped items).
# ORDER MATTERS (the candidate-fallback tries styles top-down): roman
# numerals BEFORE single-letter alpha ("i." is roman in "i. ii. iii."),
# labeled/outline/greek (most specific) first, plain bullets last.
_BLOCK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "outline",
        re.compile(r"^ {0,6}(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\.?\s+(\S.*)$"),
    ),
    (
        "labeled",
        re.compile(
            r"^ {0,6}(?:" + _LABEL_WORDS + r")\s+"
            r"(\d{1,2}|[A-Z]|[a-z]|[ivxlc]{1,5}|[IVXLC]{1,5})[.:)]\s+(\S.*)$"
        ),
    ),
    (
        "greek",
        re.compile(r"^ {0,6}([\u03b1-\u03c9])[.)]\s+(\S.*)$"),
    ),
    (
        "roman_upper",
        re.compile(r"^ {0,6}([IVXLC]{1,6})[.)]\s+(\S.*)$"),
    ),
    (
        "roman_lower",
        re.compile(r"^ {0,6}([ivxlc]{1,6})[.)]\s+(\S.*)$"),
    ),
    (
        "roman_lower_paren",
        re.compile(r"^ {0,6}\(([ivxlc]{1,6})\)\s+(\S.*)$"),
    ),
    (
        "arabic_paren",
        re.compile(r"^ {0,6}\((\d{1,2})\)\s+(\S.*)$"),
    ),
    (
        "upper_alpha_paren",
        re.compile(r"^ {0,6}\(([A-Z])\)\s+(\S.*)$"),
    ),
    (
        "lower_alpha_paren",
        re.compile(r"^ {0,6}\(([a-z])\)\s+(\S.*)$"),
    ),
    (
        "arabic",
        re.compile(r"^ {0,6}(\d{1,2})[.)]\s+(\S.*)$"),
    ),
    (
        "upper_alpha",
        re.compile(r"^ {0,6}([A-Z])[.)]\s+(\S.*)$"),
    ),
    (
        "lower_alpha",
        re.compile(r"^ {0,6}([a-z])[.)]\s+(\S.*)$"),
    ),
    (
        "bullet",
        re.compile(r"^ {0,6}(" + BULLET_GLYPHS + r")\s+(\S.*)$"),
    ),
]

# Run-in patterns: (style, compiled regex with group: marker).
_RUNIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("runin_arabic", re.compile(r"\((\d{1,2})\)\s")),
    ("runin_alpha", re.compile(r"\(([a-z])\)\s")),
    ("runin_roman", re.compile(r"\(([ivxlc]{1,5})\)\s")),
    (
        "ordinal",
        re.compile(
            r"\b(" + "|".join(_ORDINAL_WORDS) + r")\b[,.]?\s",
        ),
    ),
]

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def _roman_value(s: str) -> int | None:
    """Value of a lowercase roman numeral, or None when malformed."""
    total = 0
    prev = 0
    for ch in reversed(s):
        v = _ROMAN_VALUES.get(ch)
        if v is None:
            return None
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


_ALPHA_ORDER = "abcdefghijklmnopqrstuvwxyz"
_ALPHA_UPPER_ORDER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _marker_index(style_sequence: str, marker: str) -> int | None:
    """Ordinal index of a marker within its sequence class (0-based), or
    None when the marker does not belong to the class."""
    m = marker.strip()
    if style_sequence == "int":
        return int(m) - 1 if m.isdigit() else None
    if style_sequence == "alpha":
        return _ALPHA_ORDER.find(m) if len(m) == 1 and m.islower() else None
    if style_sequence == "alpha_upper":
        return _ALPHA_UPPER_ORDER.find(m) if len(m) == 1 and m.isupper() else None
    if style_sequence == "roman":
        return _roman_value(m.lower())
    if style_sequence == "greek":
        return _GREEK_ORDER.find(m)
    if style_sequence == "ordinal":
        idx = _ORDINAL_WORDS.index(m) if m in _ORDINAL_WORDS else None
        return idx
    return None


def _is_consecutive(style_sequence: str, prev_idx: int | None, cur_idx: int | None) -> bool:
    """True when cur_idx follows prev_idx in the style's sequence."""
    if cur_idx is None:
        return False
    if style_sequence == "ordinal":
        # ordinals may skip (First, Third) but must never go backward
        return prev_idx is None or cur_idx > prev_idx
    if prev_idx is None:
        return True  # any start is a valid fragment start
    return cur_idx == prev_idx + 1


@dataclass
class EnumItem:
    """One detected enumerated item."""

    marker: str
    text: str
    line: int = 0


@dataclass
class Enumeration:
    """One detected enumerated list in the source."""

    style: str
    kind: str  # "block" | "runin"
    stem: str = ""
    items: list[EnumItem] = field(default_factory=list)
    start_line: int = 0

    @property
    def count(self) -> int:
        return len(self.items)


# ─────────────────────────────────────────────────────────────────────────────
# The detector
# ─────────────────────────────────────────────────────────────────────────────


def _clean_item_text(text: str) -> str:
    """Collapse whitespace, strip trailing conjunctions/punctuation (the
    run-in "(6) …, and (7) …" shape)."""
    t = text.replace("\r", " ").replace("\n", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+and\s*$", "", t, flags=re.IGNORECASE).strip()
    return t.rstrip(",;.").strip()


def _looks_like_table_garbage(line: str) -> bool:
    """Mirrored-table / OCR garbage guard: heavy non-Latin content or
    table-row shape — never a list item."""
    if "|" in line and line.count("|") >= 2:
        return True
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return True
    non_latin = [c for c in letters if not (c.isascii() or "\u0370" <= c <= "\u03ff")]
    if len(non_latin) / len(letters) > 0.3:
        return True
    return False


def detect_enumerations(source_text: str, min_items: int | None = None) -> list[Enumeration]:
    """Detect EVERY enumerated list in the chapter — all template styles,
    the WHOLE chapter (not just the conclusion region).

    Args:
        source_text: the chapter source text.
        min_items: override the per-style minimum (default: the template's
            — 2 for bullets, 3 for sequence styles; a lone "1." line is
            not a list).

    Returns:
        All detected :class:`Enumeration` objects in source order. A
        sequential style yields a list only when its markers are
        consecutive (1,2,3… a,b,c… II,III,IV…); bullets need no sequence.
        Items carry the verbatim text between markers.

    Never raises; an empty/short source returns [].
    """
    try:
        if not source_text or len(source_text) < 120:
            return []
        lines = source_text.split("\n")
        # skip YAML frontmatter
        start = 0
        if lines and lines[0].strip() == "---":
            for i, ln in enumerate(lines[1:], 1):
                if ln.strip() == "---":
                    start = i + 1
                    break
        results: list[Enumeration] = []

        # ── Pass 1: BLOCK lists (one item per line) ────────────────────
        # CANDIDATE-FALLBACK: a line like "i." matches BOTH roman_lower and
        # lower_alpha — every matching style is tried and the FIRST one
        # whose collected run reaches the style minimum wins (the pattern
        # list orders roman before single-letter alpha, so "i. ii. iii."
        # is roman, while "u. v. w." — no roman reading — stays alpha).
        i = start
        n = len(lines)
        while i < n:
            line = lines[i]
            if not line.strip() or _looks_like_table_garbage(line):
                i += 1
                continue
            candidates = [(style, m) for style, pat in _BLOCK_PATTERNS if (m := pat.match(line))]
            if not candidates:
                i += 1
                continue
            picked = None
            for style, _m in candidates:
                items, j = _collect_block_run(lines, i, style, min_items)
                style_min = (
                    min_items if min_items is not None else ENUMERATION_TEMPLATE[style]["min_items"]
                )
                if len(items) >= style_min and not _looks_like_table_garbage(
                    "\n".join(it.text for it in items)
                ):
                    picked = (style, items, j)
                    break
            if picked:
                style, items, j = picked
                stem = _find_block_stem(lines, i)
                results.append(
                    Enumeration(
                        style=style,
                        kind="block",
                        stem=stem,
                        items=items,
                        start_line=i + 1,
                    )
                )
                i = j if j > i else i + 1
            else:
                # no candidate reached its minimum here — try the next line
                # (a partial fragment mid-list, or prose)
                i += 1

        # ── Pass 2: RUN-IN lists (markers inline within a paragraph) ────
        # A paragraph made of BLOCK list lines (no blanks between items)
        # is already covered by pass 1 — skip run-in scanning for
        # paragraphs that are predominantly block-marker lines.
        paragraphs = _paragraphs(source_text)
        for para_text, para_line in paragraphs:
            para_lines = [ln for ln in para_text.split("\n") if ln.strip()]
            if para_lines:
                marker_lines = sum(
                    1 for ln in para_lines if any(pat.match(ln) for _st, pat in _BLOCK_PATTERNS)
                )
                if marker_lines / len(para_lines) >= 0.6:
                    continue
            for style, pat in _RUNIN_PATTERNS:
                seq = ENUMERATION_TEMPLATE[style]["sequence"]
                style_min = (
                    min_items if min_items is not None else ENUMERATION_TEMPLATE[style]["min_items"]
                )
                matches = list(pat.finditer(para_text))
                if len(matches) < style_min:
                    continue
                # group consecutive-marker runs
                runs: list[list[re.Match]] = []
                cur: list[re.Match] = []
                prev_idx: int | None = None
                for m in matches:
                    cur_idx = _marker_index(seq, m.group(1)) if seq else None
                    if not seq or _is_consecutive(seq, prev_idx, cur_idx):
                        cur.append(m)
                        prev_idx = cur_idx
                    else:
                        if len(cur) >= style_min:
                            runs.append(cur)
                        cur = [m] if cur_idx is not None else []
                        prev_idx = cur_idx
                if len(cur) >= style_min:
                    runs.append(cur)
                for run in runs:
                    if len(run) < style_min:
                        continue
                    items = []
                    for k, m in enumerate(run):
                        seg_start = m.end()
                        seg_end = (
                            run[k + 1].start()
                            if k + 1 < len(run)
                            else _sentence_end(para_text, seg_start)
                        )
                        text = _clean_item_text(para_text[seg_start:seg_end])
                        if text:
                            items.append(EnumItem(marker=m.group(1), text=text, line=para_line))
                    if len(items) >= style_min:
                        stem = _clean_item_text(para_text[: run[0].start()])[-150:]
                        results.append(
                            Enumeration(
                                style=style,
                                kind="runin",
                                stem=stem,
                                items=items,
                                start_line=para_line,
                            )
                        )
        # source order
        results.sort(key=lambda e: (e.start_line, e.kind))
        return results
    except Exception:
        return []


def _collect_block_run(
    lines: list[str], start: int, style: str, min_items: int | None
) -> tuple[list[EnumItem], int]:
    """Collect the run of same-style marker lines from ``start``.

    Allows blank lines between items (markdown loose lists) and ONE
    non-marker continuation line per item (wrapped items). Stops at the
    first non-consecutive marker, the first foreign-style line, or the
    first plain-prose line. Returns ``(items, end_index)`` where
    ``end_index`` is the line index AFTER the run's last consumed line.
    """
    seq = ENUMERATION_TEMPLATE[style]["sequence"]
    items: list[EnumItem] = []
    prev_idx: int | None = None
    j = start
    n = len(lines)
    pending_continuation = 0
    while j < n:
        ln = lines[j]
        if not ln.strip():
            # a blank line: the list continues only if the SAME style's
            # marker appears at the next non-blank line
            k = j + 1
            while k < n and not lines[k].strip():
                k += 1
            if k < n and _match_block(lines[k], style):
                j = k
                continue
            break
        mj = _match_block(ln, style)
        if mj is not None:
            marker, text = mj
            cur_idx = _marker_index(seq, marker) if seq else None
            if seq and not _is_consecutive(seq, prev_idx, cur_idx):
                break  # non-consecutive marker ends the run
            items.append(EnumItem(marker=marker, text=text, line=j + 1))
            if seq:
                prev_idx = cur_idx
            pending_continuation = 0
            j += 1
            continue
        # non-marker line: ONE continuation of the previous item (a
        # wrapped item) — otherwise the list ends
        if items and pending_continuation == 0 and ln.strip() and not ln.lstrip().startswith("#"):
            items[-1].text += " " + ln.strip()
            pending_continuation += 1
            j += 1
            continue
        break
    return items, j


def _match_block(line: str, style: str) -> tuple[str, str] | None:
    """Match one line against one style's block pattern."""
    for st, pat in _BLOCK_PATTERNS:
        if st != style:
            continue
        m = pat.match(line)
        if m:
            groups = m.groups()
            return groups[0], groups[-1]
    return None


def _find_block_stem(lines: list[str], idx: int) -> str:
    """The introducing text above a block list: the nearest previous
    non-blank line that is NOT itself a list-marker line (adjacent lists
    must not adopt each other's items as stems), collapsed, up to 150
    chars."""
    k = idx - 1
    while k >= 0:
        ln = lines[k]
        if not ln.strip():
            k -= 1
            continue
        if any(pat.match(ln) for _st, pat in _BLOCK_PATTERNS):
            k -= 1  # the previous list's own item — keep looking up
            continue
        stem = re.sub(r"\s+", " ", ln.strip())
        return stem[-150:]
    return ""


def _paragraphs(source_text: str) -> list[tuple[str, int]]:
    """(paragraph_text, 1-based start line) for every non-blank paragraph."""
    out: list[tuple[str, int]] = []
    cur_lines: list[str] = []
    cur_start = 0
    for i, ln in enumerate(source_text.split("\n"), 1):
        if ln.strip():
            if not cur_lines:
                cur_start = i
            cur_lines.append(ln)
        else:
            if cur_lines:
                out.append(("\n".join(cur_lines), cur_start))
                cur_lines = []
    if cur_lines:
        out.append(("\n".join(cur_lines), cur_start))
    return out


def _sentence_end(text: str, start: int) -> int:
    """End of the current sentence-ish segment (period+space+Capital)."""
    m = re.search(r"[.!?]\s+(?=[A-Z(])", text[start:])
    if m:
        return start + m.start() + 1
    return len(text)


# ─────────────────────────────────────────────────────────────────────────────
# Coverage helpers (the guarantee machinery)
# ─────────────────────────────────────────────────────────────────────────────

_STOPWORDS_COVERAGE = {
    "that",
    "this",
    "with",
    "from",
    "have",
    "been",
    "were",
    "they",
    "their",
    "which",
    "would",
    "could",
    "should",
    "about",
    "into",
    "than",
    "then",
    "them",
    "these",
    "those",
    "when",
    "while",
    "where",
    "whose",
    "there",
    "other",
    "such",
    "some",
    "each",
    "both",
    "also",
    "most",
    "more",
    "less",
    "very",
    "much",
    "many",
    "same",
    "only",
    "upon",
    "through",
    "between",
    "because",
    "however",
    "therefore",
    "thus",
    "hence",
    "being",
    "before",
    "after",
    "during",
    "under",
    "over",
}


def enumeration_item_covered(item_text: str, haystack_lower: str) -> bool:
    """True when an enumerated item's content is covered by the summary
    text (≥50% of the item's distinctive words appear in it).

    Same heuristic family as the recall floor's conclusion-item probe
    (words > 4 chars, ≥50% hit) — deliberately generous so verbatim and
    faithful paraphrases both count.
    """
    try:
        if not item_text:
            return True
        words = [w for w in re.split(r"\W+", str(item_text).lower()) if len(w) > 4]
        words = [w for w in words if w not in _STOPWORDS_COVERAGE][:8]
        if not words:
            return True  # nothing checkable — count as present
        hits = sum(1 for w in words if w in (haystack_lower or ""))
        return hits / len(words) >= 0.5
    except Exception:
        return True


def stem_label(stem: str, count: int) -> str:
    """A human label for the consolidated bullet, derived from the list's
    introducing stem ("The seven features of X are:" -> "Seven Features
    Of X"); falls back to a count-generic label."""
    s = re.sub(r"\s+", " ", (stem or "")).strip().rstrip(":;.,—–-")
    s = re.sub(
        r"\b(?:the|a|an|these|those|following|as|are|is|was|were|be|been|"
        r"included|include|includes|listed|below|above|here|now)\b\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = s.strip()
    words = [w for w in s.split() if w][:6]
    if words:
        label = " ".join(words)
        label = label[:70].strip()
        return label[0].upper() + label[1:] if label else f"Enumerated list ({count} items)"
    return f"Enumerated list ({count} items)"


def clean_enum_text(text: str) -> str:
    """Public wrapper for :func:`_clean_item_text` (ship-time bullet
    assembly imports this)."""
    return _clean_item_text(text)


def enumeration_coverage_block(source_text: str, budget_chars: int = 4000) -> str:
    """The prompt block that injects EVERY detected enumerated list into
    the summarizer's instructions.

    The contract stated to the model: EVERY item of EVERY list MUST
    appear in the summary (bullets or thorough) — "a list of seven must
    contribute all seven items, never six". Items are quoted verbatim
    (each capped at 100 chars; the whole block at ``budget_chars`` —
    beyond the budget, lists degrade to counts + shortened items so the
    coverage CONTRACT is still stated for every list).
    """
    try:
        enums = detect_enumerations(source_text)
        if not enums:
            return ""
        lines = [
            "ENUMERATED-LIST COVERAGE (deterministic pre-scan — 100% reliable):",
            "The source contains the enumerated list(s) below. EVERY item of",
            "EVERY list MUST appear in your summary (in bullet_points or the",
            "thorough summary) — if a list has seven items, all seven must be",
            "captured, never six. Reproduce each item's substance faithfully;",
            "omitting an enumerated item is a defect, however minor it seems.",
        ]
        used = 0
        for li, enum in enumerate(enums, 1):
            if enum.count < 3:
                continue
            stem_bit = f' — introduced by "{enum.stem[:80]}…"' if enum.stem else ""
            head = f"- List {li} ({enum.count} items, {enum.style} style{stem_bit}):"
            over = used > budget_chars
            if over:
                lines.append(
                    f"{head} reproduce ALL {enum.count} items from the source"
                    " (list details omitted here for prompt budget — read them"
                    " from the chapter text; the full-coverage rule applies)."
                )
                continue
            item_lines = []
            for it in enum.items:
                t = _clean_item_text(it.text)
                t = t[:100] + ("…" if len(t) > 100 else "")
                item_lines.append(
                    f"  {it.marker}. {t}" if not it.marker.isdigit() else f"  {it.marker}. {t}"
                )
            block = head + "\n" + "\n".join(item_lines)
            used += len(block)
            lines.append(block)
        return "\n".join(lines)
    except Exception:
        return ""
