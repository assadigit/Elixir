"""V0.4.19 — author-surname garble cross-check and repair.

``detect_and_repair_author_garbles`` (and its ``_AUTHOR_YEAR_RE`` pattern)
moved VERBATIM from ``garble.py`` during the V0.4.19 de-monolithization.
``_edit_distance_one_neighbors`` lives in ``garble.lexicon`` and is
imported by name.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.garble.lexicon import _edit_distance_one_neighbors
from core.summarisation.postchecks.shared import Issue

# ── V0.20.5 (Quality Campaign, brainstorm D1): surname-garble cross-check ──


# Pattern: "Surname (year)" or "Surname (<em>year</em>)" — the author-year
# citation form the summary uses. Strips <em> tags before matching so the
# year is a clean 4-digit string.
_AUTHOR_YEAR_RE = re.compile(
    r"\b([A-Z][a-z]{2,}(?:[-\s][A-Z][a-z]+)?)\s*\(\s*(?:<em[^>]*>)?\s*(\d{4})",
)


def detect_and_repair_author_garbles(
    text: str,
    field_label: str,
    source_authors: list[str] | None = None,
) -> tuple[str, list[Issue]]:
    """V0.20.5 (brainstorm D1): cross-check every "Surname (year)" pattern in
    the summary against the source's author list. If a surname is edit-
    distance-1 from a source author (e.g., a dropped-letter garble of a
    cited author's surname), auto-repair it.

    Content-agnostic: the source author list comes from the RUNTIME
    deterministic analysis (extract_citations on the source text), not a
    hardcoded list. No book-derived names are embedded in this code.

    Args:
        text: the summary field text (bullet, exec, or thorough).
        field_label: "bullet", "exec", or "thorough".
        source_authors: the surnames extracted from the source chapter
            (from extract_citations). When None or empty, the detector is
            a no-op (returns the text unchanged, no issues).

    Returns:
        ``(repaired_text, issues)``. Each issue is a ``name_garble`` fix
        with the repaired surname.
    """
    issues: list[Issue] = []
    if not text or not source_authors:
        return text, issues
    try:
        # Build a casefold set of source author surnames for fast lookup.
        source_set = {a.casefold(): a for a in source_authors if len(a) >= 4}
        if not source_set:
            return text, issues

        # Build edit-distance-1 neighbors for each source author. If a
        # summary surname matches a neighbor, it's a garble of that author.
        # (e.g., a source author's surname with one dropped letter.)
        author_neighbors: dict[str, str] = {}  # casefold garble → original source author
        for src_auth in source_authors:
            if len(src_auth) < 4:
                continue
            for neighbor in _edit_distance_one_neighbors(src_auth.casefold()):
                # Only register a neighbor if it's NOT itself a source author
                # (avoids "Gediman" matching itself as a garble of "Gediman").
                if neighbor not in source_set:
                    author_neighbors[neighbor] = src_auth

        # Find all "Surname (year)" patterns and check for garbles.
        # V0.4 (Quality Campaign, audit V0.3 ch.3): add a fuzzy-matching
        # fallback for SEVERE garbles (edit distance >>1) — a cited author's
        # name corrupted beyond one-letter drops. The edit-distance-1 check
        # above catches one-letter drops; the fuzzy check below catches
        # multi-character corruption using rapidfuzz similarity ratio.
        # Threshold: >=80% similarity to a source author (with length >= 4)
        # that is NOT an exact match. Content-agnostic (uses the runtime list).
        try:
            from rapidfuzz import fuzz as _rf_fuzz

            _has_fuzz = True
        except ImportError:
            _has_fuzz = False

        def _repair_match(m: re.Match) -> str:
            surname = m.group(1)
            surname_cf = surname.casefold()
            # If the surname is already an exact source author, no garble.
            if surname_cf in source_set:
                return m.group(0)
            # Check 1: edit-distance-1 (fast, catches one-letter drops).
            if surname_cf in author_neighbors:
                correct = author_neighbors[surname_cf]
                issues.append(
                    Issue(
                        detector="name_garble",
                        severity="fix",
                        field=field_label,
                        snippet=m.group(0)[:60],
                        detail=(
                            f"repaired author-name garble: {surname!r} → {correct!r} "
                            f"(edit-distance-1 from source author; cross-checked "
                            f"against the runtime analysis author list)"
                        ),
                    )
                )
                return m.group(0).replace(surname, correct, 1)
            # Check 2 (V0.4): fuzzy matching for severe garbles (>=80%
            # similarity to a source author). Catches a severely corrupted
            # cited author's name (the V0.3 ch.3 audit defect). Only fires
            # when rapidfuzz is available AND the surname is >= 4 chars AND
            # no exact/ed-1 match was found.
            if _has_fuzz and len(surname) >= 4:
                _best_ratio = 0.0
                _best_match: str | None = None
                for src_cf, src_orig in source_set.items():
                    if abs(len(surname) - len(src_cf)) > max(len(surname), len(src_cf)) // 2:
                        continue  # skip if length difference is too large
                    _ratio = _rf_fuzz.ratio(surname_cf, src_cf)
                    if _ratio > _best_ratio:
                        _best_ratio = _ratio
                        _best_match = src_orig
                if _best_match and _best_ratio >= 80.0:
                    issues.append(
                        Issue(
                            detector="name_garble",
                            severity="fix",
                            field=field_label,
                            snippet=m.group(0)[:60],
                            detail=(
                                f"repaired author-name garble (fuzzy): {surname!r} → "
                                f"{_best_match!r} ({_best_ratio:.0f}% similarity to "
                                f"source author; cross-checked against the runtime "
                                f"analysis author list)"
                            ),
                        )
                    )
                    return m.group(0).replace(surname, _best_match, 1)
            return m.group(0)

        repaired = _AUTHOR_YEAR_RE.sub(_repair_match, text)
        return repaired, issues
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("name-garble detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues
