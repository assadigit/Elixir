"""V18.20.3.4 (RC-6) / V18.20.3.5 (audit v182034 — the RC-6 follow-up):

Deterministic MUST-HAVE recall floor, measured on the FINAL bullet set.

The V18.20.3.3 run's auto-judge reported coverage=100% (46/46 claims)
while the content audit measured ~90% — claim-recall is not content-recall
(the app itself logged that caveat). This probe is the honest,
hallucination-proof complement: regex-measured (a) theorist recall from
the deterministic analysis and (b) enumerated-conclusion item recall.
Zero LLM cost.

V18.20.3.5 root cause of the silent no-show in the V18.20.3.4 rig run:
the probe iterated ``for _item_rf in _concl_rf`` and called
``_item_rf.lower()`` — but :func:`detect_enumerated_conclusions` returns
``(number, text)`` TUPLES, so the very first conclusion raised
``AttributeError: 'tuple' object has no attribute 'lower'``. The except
clause swallowed it via ``logger.debug`` — invisible in the conversion
log. Two lessons encoded here:
  1. the unpacking is fixed (``for _num, _text in conclusions``);
  2. the probe now lives in its own function with a stable contract and
     its own tests, so a type change in the data source can never again
     silently kill it.

V18.20.3.8 (Phase 1 / W2): the two internal probes used to end in
``except Exception: pass`` — this module's own docstring admitted the
exact pattern silently killed the probe in V18.20.3.4, yet the RC-6 fix
only moved the CONTRACT, not the internal silent-death mode: the
caller-level WARNING fires only if the WHOLE call raises, so an INTERNAL
probe failure still yielded zeros with no log. Probe failures now surface
in BOTH the module log (WARNING) and ``log_parts`` (so the caller's INFO
line can never silently omit a probe). This module also gained
:func:`coverage_aware_cap` — the V18.15.7.0 80-bullet hard cap previously
ran AFTER the floor probe and applied a plain head-cap that deleted
exactly the tail bullets (gap-fill / quarantine-recovery output) the
coverage work had just added; the cap is now coverage-aware and the floor
is measured on the SHIPPED set.

Content-agnostic: pure regex/token statistics, no word lists.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)


# V18.20.3.8 (Phase 1 / W2): the historical 80-bullet hard cap
# (V18.15.7.0 Fix 3) — kept as the module-level default so the cap policy
# lives beside the floor policy (both are "deterministic final-set
# integrity" concerns).
DEFAULT_BULLET_CAP = 80


def deterministic_recall_floor(
    analysis: str,
    bullets: list[str],
    thorough: str,
    source_text: str,
) -> dict:
    """Measure the recall floor of the FINAL summary set.

    Args:
        analysis: the deterministic analysis text for this chapter (from
            find_analysis_for_heading) — supplies the theorist list.
        bullets: the FINAL bullet list (post-quarantine, post-dedup,
            post-postcheck drops, POST-CAP since V18.20.3.8).
        thorough: the final thorough summary (may be empty).
        source_text: the chapter source (for enumerated conclusions).

    Returns a dict with keys::

        {
          "theorists_covered": int, "theorists_total": int,
          "theorists_missing": [str, ...],
          "conclusion_items_covered": int, "conclusion_items_total": int,
          "conclusion_items_missing": [str, ...],
          "log_parts": [str, ...],   # human-readable fragments
          "theorists_probe_failed": bool,
          "conclusion_items_probe_failed": bool,
        }

    Every value is regex/token-derived — no LLM, no judgments. The probe
    never raises; internal failures are visible via log_parts + module
    WARNING instead of silent zeros.
    """
    out: dict = {
        "theorists_covered": 0, "theorists_total": 0, "theorists_missing": [],
        "conclusion_items_covered": 0, "conclusion_items_total": 0,
        "conclusion_items_missing": [], "log_parts": [],
        "theorists_probe_failed": False,
        "conclusion_items_probe_failed": False,
    }
    bullets = [b for b in (bullets or []) if b]
    bullets_text = " ".join(str(b) for b in bullets)

    # (a) theorist recall on the FINAL bullet set
    if analysis:
        try:
            from core.preprocessing.deterministic_analyzer import check_coverage
            cov = check_coverage(analysis, bullets_text)
            if cov.get("total"):
                out["theorists_covered"] = len(cov.get("covered", []))
                out["theorists_total"] = cov["total"]
                out["theorists_missing"] = list(cov.get("missing", []))
                out["log_parts"].append(
                    f"theorists {out['theorists_covered']}/{out['theorists_total']} "
                    f"in final bullets"
                    + (
                        f" (missing: {out['theorists_missing'][:5]})"
                        if out["theorists_missing"] else ""
                    )
                )
        except Exception as _probe_e:  # pragma: no cover — probe must never raise
            # V18.20.3.8 (Phase 1 / W2): internal probe failures must be
            # VISIBLE (module log + log_parts), never a silent zero. The
            # never-raise contract is preserved.
            logger.warning(
                "recall-floor theorist probe failed: %s: %s",
                type(_probe_e).__name__, _probe_e,
            )
            out["log_parts"].append(
                f"theorists probe FAILED — number unavailable "
                f"({type(_probe_e).__name__}); treat the floor as unmeasured"
            )
            out["theorists_probe_failed"] = True

    # (b) enumerated-conclusion item recall (bullets + thorough)
    try:
        from core.summarisation.post_processing import (
            detect_enumerated_conclusions,
        )
        conclusions = detect_enumerated_conclusions(source_text or "")
        if conclusions:
            haystack = (bullets_text + " " + (thorough or "")).lower()
            missing: list[str] = []
            covered = 0
            # V18.20.3.5: conclusions are (number, text) TUPLES — unpack
            # explicitly. The V18.20.3.4 inline probe called .lower() on
            # the tuple itself and died with an invisible AttributeError.
            for _num, item_text in conclusions:
                words = [
                    w for w in re.split(r"\W+", str(item_text).lower())
                    if len(w) > 4
                ][:6]
                if not words:
                    covered += 1  # nothing checkable — count as present
                    continue
                hits = sum(1 for w in words if w in haystack)
                if hits / len(words) >= 0.5:
                    covered += 1
                else:
                    missing.append(str(item_text)[:50])
            out["conclusion_items_covered"] = covered
            out["conclusion_items_total"] = len(conclusions)
            out["conclusion_items_missing"] = missing
            out["log_parts"].append(
                f"conclusion items {covered}/{len(conclusions)}"
                + (f" (missing: {missing[:3]})" if missing else "")
            )
    except Exception as _probe_e:  # pragma: no cover — probe must never raise
        # V18.20.3.8 (Phase 1 / W2): same rule as probe (a).
        logger.warning(
            "recall-floor conclusion-item probe failed: %s: %s",
            type(_probe_e).__name__, _probe_e,
        )
        out["log_parts"].append(
            f"conclusion-items probe FAILED — number unavailable "
            f"({type(_probe_e).__name__}); treat the floor as unmeasured"
        )
        out["conclusion_items_probe_failed"] = True

    return out


# ── V18.20.3.8 (Phase 1 / W2): coverage-aware bullet cap ─────────────────


def coverage_aware_cap(
    bullets: list[str],
    analysis: str,
    limit: int = DEFAULT_BULLET_CAP,
    log_fn: Callable[..., None] | None = None,
) -> list[str]:
    """Cap the bullet list at ``limit`` WITHOUT losing sole-cover bullets.

    Context (V18.20.3.7 SWOT, W2b): the V18.15.7.0 hard cap ran AFTER the
    recall-floor probe and applied a plain head-cap (``bullets[:80]``).
    Gap-fill and quarantine-recovery bullets are appended at the END of
    the list, so whenever the final count exceeded 80, the cap deleted
    exactly the coverage-critical tail bullets — AFTER the floor had been
    measured, making the logged "honest number" overstate the shipped set.

    Policy now (deterministic, zero LLM cost, content-agnostic — the same
    ``check_coverage`` regex the judge and the floor use):

    1. ``len(bullets) <= limit`` → unchanged (no log, no work).
    2. No analysis / probe failure → plain head-cap (byte-identical to
       V18.15.7.0), honestly logged.
    3. With analysis: a tail bullet that is the ONLY bullet covering some
       analysis author is RESCUED into the capped set, displacing the last
       non-protected head bullet. Standing rule honored: "more bullets is
       better than lower coverage" — the cap still bounds the total at
       ``limit``, but no author's only representative is cut while a
       redundant bullet survives. Every rescue is logged.

    Never raises: any internal failure degrades to the plain head-cap
    with a visible WARNING through ``log_fn`` and the module logger.
    """
    def _log(msg: str, level: str = "WARNING") -> None:
        if log_fn is None:
            return
        try:
            log_fn(msg, level)
        except Exception:
            pass

    bullets = [b for b in (bullets or []) if b]
    if len(bullets) <= limit:
        return bullets

    if not analysis:
        _log(
            f"    ✂️ V18.15.7.0: Capping bullets {len(bullets)} → {limit} "
            f"(hard cap; no deterministic analysis available — plain "
            f"head-cap, sole-cover rescue unavailable)"
        )
        return bullets[:limit]

    try:
        from core.preprocessing.deterministic_analyzer import check_coverage
        # author -> set of bullet indices that cover it (garble-tolerant,
        # the same matching the judge and the floor use).
        author_hits: dict[str, set] = {}
        for idx, b in enumerate(bullets):
            cov = check_coverage(analysis, str(b))
            for a in cov.get("covered", []) or []:
                author_hits.setdefault(a, set()).add(idx)
    except Exception as _cap_e:
        logger.warning(
            "coverage-aware cap probe failed — plain head-cap: %s: %s",
            type(_cap_e).__name__, _cap_e,
        )
        _log(
            f"    ⚠️ V18.20.3.8: coverage-aware cap probe failed "
            f"({type(_cap_e).__name__}: {_cap_e}) — plain head-cap applied"
        )
        return bullets[:limit]

    head_idx = list(range(limit))
    tail_idx = list(range(limit, len(bullets)))

    # Head bullets that are the sole cover of some author are protected
    # from displacement.
    protected: set = set()
    for _a, hits in author_hits.items():
        if len(hits) == 1:
            only = next(iter(hits))
            if only < limit:
                protected.add(only)

    final = list(head_idx)
    rescued = 0
    for t in tail_idx:
        # Which authors does this tail bullet sole-cover (i.e. no other
        # surviving bullet — head or already-rescued — covers them)?
        sole_authors = [
            a for a, hits in author_hits.items()
            if t in hits and not (hits - {t}) & set(final)
        ]
        if not sole_authors:
            continue
        # Displacement candidate: the LAST non-protected surviving bullet
        # (deterministic; never a protected sole-cover).
        displacable = [i for i in reversed(final) if i not in protected]
        if not displacable:
            _log(
                f"    ⚠️ V18.20.3.8: cap rescue stopped — all {len(final)} "
                f"kept bullets are sole-cover protected; author(s) "
                f"{sorted(sole_authors)[:3]} remain at risk (reported "
                f"honestly, not silently dropped)"
            )
            break
        out_idx = displacable[0]
        final.remove(out_idx)
        final.append(t)
        protected.add(t)
        rescued += 1
        _log(
            f"    🩹 V18.20.3.8: cap rescue — kept tail bullet {t + 1} "
            f"(sole cover of {sorted(sole_authors)[:3]}), displaced "
            f"redundant bullet {out_idx + 1}"
        )

    _log(
        f"    ✂️ V18.15.7.0: Capping bullets {len(bullets)} → {len(final)} "
        f"(hard cap; V18.20.3.8: {rescued} sole-cover rescue(s), "
        f"coverage-aware)"
    )
    # Preserve the original relative order of the surviving bullets.
    return [bullets[i] for i in sorted(final)]
