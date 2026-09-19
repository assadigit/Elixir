"""V18.11 (Phase 5 Stage 3, Batch 1.2): Bullet quality scorer.

Extracted verbatim from ``Summarizer._score_bullet`` (god-class decomposition
Stage 3). This is the 0-100 quality score used to rank bullets and drop
low-quality ones (< 40).

**Extraction map**:

| Summarizer method (old) | bullet_scorer function (new) | self deps                       |
|------------------------|-----------------------------|---------------------------------|
| ``_score_bullet``       | ``score_bullet``            | NONE (already pure — 0 self!)  |

This method was ALREADY PURE in the V18.10.1 source — it uses only its
parameters (``bullet``, ``concepts``, ``source_text``) plus module-level
``re`` and an optional local ``rapidfuzz`` import. There is literally zero
``self`` usage in the body. The extraction is a mechanical move; the
``Summarizer._score_bullet`` method becomes a one-line delegate.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context
object). Since the original had no ``self`` deps, this is the lowest-risk
extraction possible — it cannot regress behaviour.

Characterization tests: ``tests/test_bullet_scorer.py`` captures canned
inputs → golden score outputs. Byte-for-byte stability gate. The existing
``tests/test_summarizer.py::TestScoreBullet`` (4 tests) exercises the
delegate and must continue to pass unchanged.
"""

from __future__ import annotations

import re

# ── V18.20.2.0 (SWOT A25): identity-keyed memo for the normalized source ────
#
# score_bullet is called PER BULLET (filter_thinking_bullets' quality-scorer
# pass + gap-fill validation), and the source-overlap criterion used to run
# ``re.sub(r'[^\w\s]', '', source_text.lower())`` over the FULL ~200KB source
# on every call (~60 re.sub full-source scans per chapter, measured 0.39s/
# 60 bullets with real rapidfuzz). The normalized source is a PURE function
# of ``source_text`` (immutable str), so it is memoized keyed by the object's
# id, guarded by an identity check on the object itself. The entry holds a
# strong reference to the source string, which both prevents id-reuse while
# the entry is alive and keeps the memo bounded (few live entries ≈ few
# scoring runs' sources; FIFO-capped regardless). Scores are IDENTICAL —
# only the redundant re.sub scans are skipped.

_SOURCE_NORM_CACHE: dict = {}
_SOURCE_NORM_CACHE_MAX = 4


def _normalized_source(source_text: str) -> str:
    r"""V18.20.2.0 (SWOT A25): ``re.sub(r'[^\w\s]', '', source_text.lower())``
    computed at most once per distinct source-string object."""
    _key = id(source_text)
    _cached = _SOURCE_NORM_CACHE.get(_key)
    if _cached is not None and _cached[0] is source_text:
        return _cached[1]
    _norm = re.sub(r"[^\w\s]", "", source_text.lower())
    if len(_SOURCE_NORM_CACHE) >= _SOURCE_NORM_CACHE_MAX:
        _SOURCE_NORM_CACHE.pop(next(iter(_SOURCE_NORM_CACHE)))
    _SOURCE_NORM_CACHE[_key] = (source_text, _norm)
    return _norm


# ── score_bullet (extracted verbatim from Summarizer._score_bullet) ────────


def score_bullet(
    bullet: str,
    concepts: list[str] | None = None,
    source_text: str = "",
) -> int:
    """V3.2.4 C1 / V10.14.0 (D3): Score a bullet 0-100 for quality.

    Extracted verbatim from ``Summarizer._score_bullet``. ZERO ``self`` deps
    in the original — this is a pure function. Byte-for-byte identical
    scoring.

    V10.14.0 enhancements:
    - Added specificity check (citations [N], percentages, dosages) → +10
    - Added source-overlap check (bullet text appears in source) → +10
    - Broadened person-name check (was only checking book character names)
    - Broadened narrative-marker check (was only checking story verbs)

    Criteria:
    - Contains a concept keyword (from A5)           → +15
    - Contains an action verb (should/must/requires) → +10
    - Does NOT contain narrative markers             → +10
    - Length 10-35 words                             → +10
    - Contains a number/statistic from source        → +10
    - V10.14.0: Contains specificity markers [N]/%   → +10
    - V10.14.0: Has source text overlap (>40%)        → +10
    - Starts with capital, ends with punctuation     → +5
    - Does NOT contain thinking markers              → +10
    - Does NOT contain prompt-leakage text           → +5
    - Does NOT contain meta-commentary               → +5
    Total possible: 100. Drop below 40.
    """
    score = 0
    bp = bullet.strip()
    bp_lower = bp.lower()
    words = bp.split()

    # +15: Contains a concept keyword
    if concepts:
        for c in concepts:
            if c.lower() in bp_lower:
                score += 15
                break

    # +10: Contains an action verb
    if re.search(
        r"\b(?:should|must|need\s+to|requires?|involves?|ensures?|establish|create|develop|use|build|maintain|avoid|adapt|assess|identify|define|leverage|prioritize|recognize|invest|pursue|showed|demonstrated|found|reported|suggests|indicates)\b",
        bp_lower,
    ):
        score += 10

    # +10: Does NOT contain narrative markers (V10.14.0: broadened)
    if not re.search(
        r"\b(?:went|goes|arrives|arrived|meets|met|tells|told|says|said|decides|decided|begins|began|story|novel|chapter\'s narrative)\b",
        bp_lower,
    ):
        score += 10

    # +10: Length 10-35 words
    word_count = len(words)
    if 10 <= word_count <= 35:
        score += 10
    elif 5 <= word_count <= 45:
        score += 5  # partial credit

    # +10: Contains a number/statistic from source
    numbers = re.findall(r"\b\d+(?:\.\d+)?(?:%| percent)?\b", bp)
    if numbers and source_text:
        for num in numbers:
            if num in source_text:
                score += 10
                break

    # V10.14.0 (D3): +10: Contains specificity markers
    # (academic citations [N], percentages %, dosages mg, trial IDs NCT)
    if re.search(r"\[\d+\]|\d+%|\d+\s*mg\b|NCT\d+", bp):
        score += 10

    # V10.14.0 (D3): +10: Has source text overlap (>40%)
    # Check if a significant portion of the bullet's words appear in the
    # source text.  This catches hallucinated bullets that have NO
    # connection to the source.
    if source_text and word_count > 3:
        try:
            from rapidfuzz import fuzz as rf_fuzz

            bp_norm = re.sub(r"[^\w\s]", "", bp_lower).strip()
            # V18.20.2.0 (SWOT A25): the full-source normalization is hoisted
            # through the identity-keyed memo (once per source object, not
            # once per bullet) — same string value, identical score.
            src_norm = _normalized_source(source_text)
            if rf_fuzz.token_set_ratio(bp_norm, src_norm) >= 40:
                score += 10
        except ImportError:
            pass

    # +5: Starts with capital, ends with punctuation
    if bp and bp[0].isupper() and bp[-1] in ".!?":
        score += 5

    # +10: Does NOT contain thinking markers
    if not re.search(
        r"(?:<think|<thinking|Analyze|Process|Draft|Check |Refine|I\'ll|I will|Let\'s|Let me)",
        bp,
        re.IGNORECASE,
    ):
        score += 10

    # +5: Does NOT contain prompt-leakage text
    if not re.search(
        r"(?:Source Text|Target Concepts|Task:|Format:|Rules:|Instructions:|Output:|Input:)",
        bp,
        re.IGNORECASE,
    ):
        score += 5

    # V10.14.0 (D3): +5: Does NOT contain meta-commentary
    if not re.search(
        r"(?:This captures|This is a complete sentence|not identical|covers point|This bullet|This keypoint)",
        bp,
        re.IGNORECASE,
    ):
        score += 5

    return min(score, 100)


__all__ = [
    "score_bullet",
    "_normalized_source",
]
