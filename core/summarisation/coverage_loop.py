"""V0.7.5 (wizard rework ⑦, 7c / D11) — the honest coverage close-the-loop.

The audit's finding (§W12): the coverage threshold was weakly coupled —
a keyword-overlap metric with no regeneration loop, the default-on
over-delivery target (1.0) dominating the user's threshold
(summarizer_init.py:413-415), and a best-effort acceptance floor
``max(0.60, t−0.10)`` that only logged a WARNING
(chapter_phases.py:1878-1917 pre-rework). The owner's requirement
(D11): *threshold 85 must deliver ≥ ~85% measured coverage, within a
few points of LLM randomness.*

The rework (content-agnostic, Rule 1 — works on any book; the trigger
list comes from the runtime keyword extractor only, never a book-derived
list):

  1. ONE target: the user threshold is THE target (see
     ``summarizer_init._effective_target`` — the over-delivery
     domination and the t−0.10 floor are gone with this release).
  2. Close-the-loop: measure (the existing concept-coverage metric,
     ``summary_validator.compute_coverage`` — unchanged) → below
     ``target − 3`` → targeted gap-fill reprompt on the MISSING
     concepts (the existing Tier-2 machinery + prompts —
     ``Summarizer._targeted_gap_fill``'s parallel focused calls) →
     re-measure → up to ``MAX_COVERAGE_ROUNDS`` (3, cost-bounded;
     each round caps at the machinery's own 12-concept trim) → the
     honest terminal report.
  3. Truth in UI: Step 7b's spin now says what the loop does
     ("regenerates until measured coverage reaches this level, ±3 for
     model randomness, max 3 rounds").

Deferred backlog (plan §5): an embedding-based recall metric (semantic,
not keyword) if the keyword metric proves gameable.
"""

from __future__ import annotations

from collections.abc import Callable

# ── The loop's constants (pinned by tests/test_v0750_steps7_7b.py) ─────────
MAX_COVERAGE_ROUNDS = 3
COVERAGE_TOLERANCE = 0.03  # ±3 points — the LLM-randomness band (D11)

# Type aliases (duck-typed — the house convention).
LogCallback = Callable[[str, str], None]
KeywordsFn = Callable[[str, int], list[str]]
GapFillFn = Callable[[str, str, list[str]], list[str]]
FilterFn = Callable[..., list[str]]
ComputeCoverageFn = Callable[[str, str], float]
NearDupFn = Callable[[str, list[str]], bool]


def _noop_log(msg: str, level: str = "INFO") -> None:
    pass


def run_coverage_close_loop(
    heading: str,
    text: str,
    content: str,
    bullets: list[str],
    exec_summary: str,
    thorough_summary: str,
    coverage: float,
    *,
    coverage_threshold: float,
    extract_keywords: KeywordsFn,
    targeted_gap_fill: GapFillFn,
    filter_thinking_bullets: FilterFn,
    compute_coverage: ComputeCoverageFn,
    is_near_duplicate: NearDupFn | None = None,
    log: LogCallback | None = None,
) -> tuple[list[str], float, int]:
    """Measure → gap-fill the missing concepts → re-measure, up to 3 rounds.

    Returns ``(bullets, final_coverage, rounds_used)`` — ``bullets`` is the
    input list possibly extended by the guarded gap-fill bullets (thinking
    filter + near-dup guard, mirroring the Tier-2 insertion path in
    ``coverage_guarantee.apply_3tier_coverage``); the caller's result dict /
    combined summary must be rebuilt from the returned values.
    """
    log = log or _noop_log
    bullets = list(bullets or [])

    def _combined() -> str:
        return f"{exec_summary} {' '.join(bullets)} {thorough_summary}"

    target = float(coverage_threshold)
    tol = COVERAGE_TOLERANCE

    # Already inside the band → nothing to do; the honest report still fires.
    if coverage >= target - tol:
        _report_met(log, coverage, target)
        return bullets, coverage, 0

    # The same normalized matcher the Tier-2 trigger uses (the loop is
    # more rounds of the SAME machinery — not a new heuristic).
    from core.summarisation.coverage_guarantee import _kw_missing
    from core.summarisation.summary_validator import _normalize_for_coverage

    rounds_used = 0
    stalled_reason = ""
    while coverage < target - tol and rounds_used < MAX_COVERAGE_ROUNDS:
        rounds_used += 1
        all_kw = extract_keywords(content, n=18)
        combined_norm = _normalize_for_coverage(_combined())
        missing = [k for k in all_kw if _kw_missing(k, combined_norm)]
        if not missing:
            stalled_reason = "no-candidates"
            break
        log(
            f"    🔄 Coverage loop, round {rounds_used}/{MAX_COVERAGE_ROUNDS}: "
            f"gap-filling {len(missing)} missing concept(s)…",
            "INFO",
        )
        raw_new = targeted_gap_fill(heading, text, missing) or []
        # The Tier-2 insertion guards (thinking/prompt-leakage filter +
        # near-dup; fail-open on a guard crash — the F4 precedent).
        guarded: list[str] = []
        for bp in raw_new:
            bp_str = str(bp) if not isinstance(bp, str) else bp
            if not bp_str:
                continue
            filtered = filter_thinking_bullets([bp_str])
            if not filtered:
                log(
                    f"    🎓 Dropped a gap-fill bullet (prompt-leakage/thinking): {bp_str[:60]}…",
                    "DEBUG",
                )
                continue
            if is_near_duplicate is not None and is_near_duplicate(filtered[0], bullets):
                log(
                    f"    🧹 Skipped a gap-fill bullet — near-duplicate of an existing one: {bp_str[:60]}…",
                    "DEBUG",
                )
                continue
            guarded.append(filtered[0])
        if not guarded:
            stalled_reason = "no-output"
            break
        bullets.extend(guarded)
        prev = coverage
        coverage = compute_coverage(content, _combined())
        log(
            f"    📈 Coverage loop, round {rounds_used}: {prev:.0%} → {coverage:.0%} "
            f"(+{len(guarded)} bullet(s))",
            "INFO",
        )

    if coverage >= target - tol:
        _report_met(log, coverage, target)
    elif stalled_reason == "no-candidates":
        log(
            f"    ⚠️ Reached {coverage:.0%} (target {target:.0%}); no fillable gaps "
            f"remain — every sampled keyword is already covered. The metric's "
            f"full keyword/concept set is the bottleneck, not the loop.",
            "WARNING",
        )
    elif stalled_reason == "no-output":
        log(
            f"    ⚠️ Reached {coverage:.0%} (target {target:.0%}) after {rounds_used} "
            f"attempt(s); the gap-fill calls produced nothing usable. Remaining "
            f"gaps stay in the output.",
            "WARNING",
        )
    else:
        # Rounds exhausted while still below the band — the honest terminal
        # report (the plan's form): what was reached, after how many
        # attempts, and what is still missing.
        combined_norm = _normalize_for_coverage(_combined())
        all_kw = extract_keywords(content, n=18)
        remaining = [k for k in all_kw if _kw_missing(k, combined_norm)]
        log(
            f"    ⚠️ Reached {coverage:.0%} after {rounds_used} attempts "
            f"(target {target:.0%}); remaining gaps: "
            f"{', '.join(remaining[:8])}{'…' if len(remaining) > 8 else ''}",
            "WARNING",
        )
    return bullets, coverage, rounds_used


def _report_met(log: LogCallback, coverage: float, target: float) -> None:
    if coverage >= target:
        log(f"    ✅ Coverage {coverage:.0%} — target met", "INFO")
    else:
        log(
            f"    ✅ Coverage {coverage:.0%} — target met (within ±3 of the {target:.0%} target)",
            "INFO",
        )


__all__ = [
    "MAX_COVERAGE_ROUNDS",
    "COVERAGE_TOLERANCE",
    "run_coverage_close_loop",
    "LogCallback",
]
