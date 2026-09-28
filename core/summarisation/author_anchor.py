"""V0.5.18: shared boundary-safe author-name anchoring.

WHY THIS MODULE EXISTS — the V0.5.17 ch.9 operator-rig audit found that the
V0.5.4 B1 word-boundary rule (``r"\\b" + re.escape(name) + r"\\b"``) can
NEVER match a source/glossary author name that ends in ``"et al."``: the
terminal ``\\b`` after the escaped period requires a following WORD
character, and prose always has ``"et al. "`` + space/paren/comma. All six
"X et al." glossary names in the flagged-8 list were present in the shipped
text — 6 of 8 verification-coverage flags were FALSE POSITIVES.

The same boundary shape bites any name whose last character is non-word
(trailing-period initials, "et al." suffixes). Two anchors fix the family:

1. **The et-al strip** — a presence check asks "is this author represented
   in the text?", and ``"AuthorA et al. (1975)"`` in the summary means
   AuthorA IS represented, whatever prose form the mention takes
   ("AuthorA et al.", "AuthorA's", "AuthorA and colleagues", bare
   "AuthorA"). So the check anchors on the PRIMARY SURNAME (everything
   before the ``" et al."`` suffix), not on the full multi-word form.

2. **Lookaround boundaries** — ``(?<!\\w)name(?!.\\w)`` instead of
   ``\\bname\\b``. For names that start AND end with word characters the
   two are equivalent; the lookaround form additionally works when the
   name's first/last character is non-word (periods, hyphens at the edges),
   and it keeps the B1 property (a 3-letter surname never matches inside a
   longer word — ``(?<!\\w)abc`` will not match inside "Xyzabc").

Consumers (V0.5.18): the verification-LAYER coverage check
(verification_phase.py — glossary ground truth), the V0.5.17 near-dup
author-coverage veto (postchecks/orchestrator.py), the NEW semantic-dedup
author-coverage veto (summary_validator.semantic_dedup_bullets), and the
repeatability audit scorecard (scripts/repeatability_audit.py).

Content-agnostic (Rule 1): every name comes from the runtime
extract_citations roster / LLM glossary — no book-specific strings here.
"""

from __future__ import annotations

import re

__all__ = [
    "author_anchor",
    "author_anchor_patterns",
    "author_in_text",
    "source_author_surnames",
]

# The multi-author suffix (case-insensitive, optional trailing period,
# anchored at the name's end). ``"AuthorB et al."`` → ``"AuthorB"``.
_ET_AL_SUFFIX_RE = re.compile(r"\s+et\s+al\.?\s*$", re.IGNORECASE)

# Trailing punctuation that carries no identity (periods/commas/colons that
# survive name extraction). ``"Smith, J. A."`` → ``"Smith, J. A"`` (only the
# trailing dot goes; INTERNAL punctuation is identity and is kept).
_TRAILING_PUNCT = ".,;:"


def author_anchor(name: str) -> str:
    """Return the lowercased presence-check anchor for an author name.

    ``"AuthorA et al."`` → ``"authora"``; ``"AuthorB"`` → ``"authorb"``;
    ``"van der Waerden et al."`` → ``"van der waerden"``.

    Fail-open: if the et-al strip would leave nothing (a degenerate
    ``"et al."``-only name), the original name is returned unchanged — the
    anchor must never be empty.
    """
    n = (name or "").strip()
    stripped = _ET_AL_SUFFIX_RE.sub("", n).strip().rstrip(_TRAILING_PUNCT).strip()
    if not stripped:
        stripped = n
    return stripped.lower()


def author_anchor_patterns(name: str) -> list[re.Pattern[str]]:
    """Boundary-anchored regex patterns for a name's presence check.

    Returns the anchor pattern plus the V0.5.4 crude plural variant
    (``"Adams"`` also matches "Adam") — the same tolerance the B1 rule
    always had, now boundary-safe for non-word-edge names.
    """
    anchor = author_anchor(name)
    patterns = [re.compile(r"(?<!\w)" + re.escape(anchor) + r"(?!\w)")]
    # Crude plural-strip heuristic (V0.5.4 B1): "Adams" covered by "Adam".
    plural = anchor.rstrip("s")
    if plural and plural != anchor:
        patterns.append(re.compile(r"(?<!\w)" + re.escape(plural) + r"(?!\w)"))
    return patterns


def author_in_text(name: str, text_lower: str) -> bool:
    """True if the author's anchor matches ``text_lower`` (pre-lowered)."""
    if not text_lower:
        return False
    return any(p.search(text_lower) for p in author_anchor_patterns(name))


def source_author_surnames(source_text: str | None) -> list[str]:
    """The runtime author roster for a piece of source text: surnames from
    ``extract_citations``, first-appearance order, de-duplicated.

    Mirrors the surname logic ``run_post_checks`` uses for its near-dup
    veto roster, so every author-coverage veto in the pipeline judges
    against the SAME roster (the V0.5.17/V0.5.18 single-source-of-truth).
    Fail-open: any extractor error returns ``[]`` (no veto, never a crash).
    """
    if not source_text:
        return []
    try:
        from core.preprocessing.deterministic_analyzer import extract_citations

        cites = extract_citations(source_text)
        seen: set[str] = set()
        authors: list[str] = []
        for c in cites:
            a = (c.get("author") or "").strip()
            if not a or len(a) < 3:
                continue
            # Surname (last token) — handles "First Middle Last" → "Last".
            surname = a.split()[-1] if " " in a else a
            key = surname.casefold()
            if key in seen:
                continue
            seen.add(key)
            authors.append(surname)
        return authors
    except Exception:  # noqa: BLE001 — fail-open (a veto must never crash a chapter)
        return []
