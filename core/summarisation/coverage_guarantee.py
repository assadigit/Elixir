"""V18.15.3 (Phase 5 Stage 3, Batch 4.5): 3-Tier coverage guarantee.

Extracted verbatim from ``Summarizer._apply_3tier_coverage`` (god-class
decomposition Stage 4 — the 17th extraction). The V16.0.3 coverage guarantee:
Tier 1 = synthesis coverage, Tier 2 = targeted gap-fill (filtered), Tier 3 =
force-insert missing concepts. Each tier is measured + logged.

**Extraction map**:

| Summarizer method (old) | coverage_guarantee function (new) | self deps |
|------------------------|-----------------------------------|-----------|
| ``_apply_3tier_coverage`` | ``apply_3tier_coverage`` | ``coverage_threshold``, ``_extract_keywords``, ``log``, ``_targeted_gap_fill``, ``_filter_thinking_bullets``, ``max_bullets_per_chapter``, ``_compute_coverage``, ``_force_insert_missing`` |

**Mutable-state handling**: ``result`` is a passed-in mutable dict that the
function appends bullets to and sets ``result["model"]`` on — exactly as the
original (in-place mutation, no return-value indirection). This matches how
``_force_insert_missing`` already mutates ``result`` in the original.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-3 pattern.

Characterization tests: ``tests/test_coverage_guarantee.py`` captures the
threshold-satisfied short-circuit, the no-missing-keywords path, the Tier 2
gap-fill (filtered) path, the max_bullets cap, the Tier 3 force-insert path,
and the coverage-breakdown log.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
ExtractKeywordsFn = Callable[[str, int], list[str]]
TargetedGapFillFn = Callable[[str, str, list[str]], list[str]]
FilterThinkingFn = Callable[[list[str]], list[str]]
ComputeCoverageFn = Callable[[str, str], float]
ForceInsertFn = Callable[[str, list[str], dict[str, Any]], None]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# V0.05 (rig audit F3-a — P1): ONE coverage matcher everywhere. The Tier-2/3
# trigger lists previously used RAW SUBSTRING (``k not in combined.lower()``)
# while the final recompute used the V0.03-normalized ``_keyword_covered``
# (hyphen/plural/parts tolerance) — so a keyword already covered by a
# PARAPHRASE (e.g. "smart/effective architect") re-triggered gap-fill and
# force-insert remediation, producing duplicate bullets/excerpts and FALSE
# "not covered" claims in the shipped Source-Excerpts header. The matcher
# is imported from summary_validator — the single source of truth.
def _kw_missing(kw: str, normalized_combined: str) -> bool:
    """True when ``kw`` is NOT covered by the combined summary text.

    ``normalized_combined`` must already be normalized via
    ``_normalize_for_coverage`` (the caller normalizes once per pass).
    Falls back to raw substring when the import is unavailable so direct
    callers/tests never crash.
    """
    try:
        from core.summarisation.summary_validator import _keyword_covered
        return not _keyword_covered(kw, normalized_combined)
    except Exception:
        return (kw or "").lower() not in normalized_combined


# ── apply_3tier_coverage (extracted verbatim) ──────────────────────────────

def apply_3tier_coverage(
    heading: str,
    text: str,
    content: str,
    result: dict[str, Any],
    coverage: float,
    coverage_threshold: float = 0.85,
    extract_keywords: ExtractKeywordsFn | None = None,
    log: LogCallback | None = None,
    targeted_gap_fill: TargetedGapFillFn | None = None,
    filter_thinking_bullets: FilterThinkingFn | None = None,
    max_bullets_per_chapter: int = 30,
    compute_coverage: ComputeCoverageFn | None = None,
    force_insert_missing: ForceInsertFn | None = None,
    bullet_cap: int | None = None,
) -> float:
    """V16.0.3 3-Tier coverage guarantee.

    Mutates ``result`` in place (appends gap-fill bullets, sets model tag).
    Returns the final coverage fraction.
    """
    if log is None:
        log = _noop_log

    if round(coverage, 2) >= coverage_threshold:
        return coverage  # V13.34.2: round to avoid float edge cases
    _bps = [str(b) if not isinstance(b, str) else b for b in result.get('bullet_points', []) if b]
    # V13.39.0: Include key_distinctions + theoretical_tensions in coverage check
    # so the additive sections contribute to (and are checked by) coverage.
    # V0.03 (P0-2/P0-3): source_excerpts count too — a keyword already covered
    # by a framed excerpt must not re-trigger Tier-2/Tier-3 remediation.
    _kd = result.get('key_distinctions', '') or ''
    _tt = result.get('theoretical_tensions', '') or ''
    _ex = [str(e) if not isinstance(e, str) else e for e in result.get('source_excerpts', []) or []]
    combined = f"{result.get('executive_summary', '')} {' '.join(_bps)} {result.get('thorough_summary', '')} {_kd} {_tt} {' '.join(_ex)}"
    all_kw = extract_keywords(content, n=18)
    # V0.05 (F3-a): normalized matcher for the Tier-2 trigger list.
    from core.summarisation.summary_validator import _normalize_for_coverage
    _combined_norm = _normalize_for_coverage(combined)
    missing = [k for k in all_kw if _kw_missing(k, _combined_norm)]
    if not missing:
        return coverage
    log(f"    V16.0.3 3-Tier Guarantee: {len(missing)} concepts missing, gap-filling...", "DEBUG")
    # V0.06 (rig audit F4-b — GENERAL RULE: the source-scaled bullet budget
    # is a HARD CAP at every insertion site): when the chapter is already at
    # its cap there is NO room for Tier-2 gap-fill — the shortfall is logged
    # honestly and left to Tier-3 (bounded framed excerpts), never padded
    # away with more bullets. With partial room, only as many missing
    # concepts as there is room for are sent to the focused calls (no LLM
    # calls whose output cannot ship).
    _cap = int(bullet_cap) if isinstance(bullet_cap, (int, float)) and bullet_cap else 0
    if _cap > 0:
        _room = _cap - len(_bps)
        if _room <= 0:
            log(
                f"    ✂️ V0.06: bullet budget reached ({len(_bps)}/{_cap} for this "
                f"chapter) — Tier-2 gap-fill SKIPPED; the coverage shortfall "
                f"stands (Tier-3 excerpts remain available).",
                "INFO",
            )
            missing = []
        elif len(missing) > _room:
            log(
                f"    ✂️ V0.06: bullet budget leaves room for {_room} more "
                f"bullet(s) ({len(_bps)}/{_cap}) — Tier-2 gap-fill trimmed "
                f"from {len(missing)} to {_room} concept(s).",
                "INFO",
            )
            missing = missing[:_room]
    new_bullets = targeted_gap_fill(heading, text, missing) if missing else []
    if new_bullets:
        for bp in new_bullets:
            bp_str = str(bp) if not isinstance(bp, str) else bp
            if bp_str and bp_str not in result.get("bullet_points", []):
                # V18.12.3: Filter the Tier 2 gap-fill bullet through
                # _filter_thinking_bullets BEFORE appending. The V18.12.2
                # audit found the Tier 2 _targeted_gap_fill path was leaking
                # the prompt template into the Key Takeaways. Now each Tier 2
                # candidate is filtered in light mode.
                _filtered = filter_thinking_bullets(
                    [bp_str],
                )
                if _filtered:
                    result["bullet_points"].append(_filtered[0])
                else:
                    log(
                        f"    🎓 V18.12.3: Dropped Tier 2 gap-fill bullet "
                        f"(prompt-leakage/thinking): {bp_str[:60]}\u2026",
                        "DEBUG",
                    )
        result["bullet_points"] = result["bullet_points"][:max_bullets_per_chapter]
        result["model"] = result.get("model", "primary") + "+gapfill"
    _bps2 = [str(b) if not isinstance(b, str) else b for b in result.get('bullet_points', []) if b]
    _ex2 = [str(e) if not isinstance(e, str) else e for e in result.get('source_excerpts', []) or []]
    combined2 = f"{result.get('executive_summary', '')} {' '.join(_bps2)} {result.get('thorough_summary', '')} {' '.join(_ex2)}"
    coverage2 = compute_coverage(content, combined2)
    if coverage2 < coverage_threshold:
        # V0.05 (F3-a): normalized matcher for the Tier-3 trigger list — the
        # SAME matcher the Tier-2 trigger and the final recompute use.
        _combined2_norm = _normalize_for_coverage(combined2)
        still_missing = [k for k in all_kw if _kw_missing(k, _combined2_norm)]
        if still_missing:
            force_insert_missing(text, still_missing, result)
    _bps3 = [str(b) if not isinstance(b, str) else b for b in result.get('bullet_points', []) if b]
    # V0.03 (P0-2): Tier-3 excerpts live in result['source_excerpts'] now —
    # they are part of the delivered summary (framed section), so they must
    # count toward the final coverage recompute.
    _ex3 = [str(e) if not isinstance(e, str) else e for e in result.get('source_excerpts', []) or []]
    combined3 = f"{result.get('executive_summary', '')} {' '.join(_bps3)} {result.get('thorough_summary', '')} {' '.join(_ex3)}"
    final_coverage = compute_coverage(content, combined3)
    log(f"    \U0001f4ca Coverage breakdown: Tier 1 (synthesis) {coverage:.0%} \u2192 Tier 2 (gap-fill) {coverage2:.0%} \u2192 Tier 3 (force-insert) {final_coverage:.0%}", "INFO")
    if final_coverage >= coverage_threshold:
        log(f"    \u2705 Coverage {final_coverage:.0%} \u2265 {coverage_threshold:.0%} \u2014 GUARANTEED", "INFO")
    return final_coverage
