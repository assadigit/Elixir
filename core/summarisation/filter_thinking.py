"""V18.15.3 (Phase 5 Stage 3, Batch 4.6): Bullet thinking/narrative filter.

Extracted verbatim from ``Summarizer._filter_thinking_bullets`` (god-class
decomposition Stage 4 — the 18th extraction). Filters out bullets that are
thinking-process contamination AND narrative/story bullets that describe plot
rather than concepts. The pure classification logic is already in
``post_processing.classify_bullets`` (V18.6); this module keeps the
quarantine-logging side-effect + the quality-scoring trim.

**Extraction map**:

| Summarizer method (old) | filter_thinking function (new) | self deps |
|------------------------|-------------------------------|-----------|
| ``_filter_thinking_bullets`` | ``filter_thinking_bullets`` | ``_current_heading`` (str), ``conservative_drops`` (bool), ``quarantine`` (obj), ``_score_bullet`` (callback), ``max_bullets_per_chapter`` (int), ``log`` (callback) |

**Mutable-state handling**: ``self._last_quarantined`` is mutated at the end of
the method (rebuilt from ``quarantine.entries``). The extracted function takes
a ``set_last_quarantined`` callback that the delegate uses to set
``self._last_quarantined``. This preserves the original's return type (just the
filtered bullets list) and the side-effect (``self._last_quarantined`` updated).
Matches the ``gap_filler.set_last_coverage`` precedent exactly.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-3 pattern.

Characterization tests: ``tests/test_filter_thinking.py`` captures the
classify-delegate path, conservative-mode keep-back, quality-scoring trim,
low-score quarantine logging, and the _last_quarantined rebuild.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
ScoreBulletFn = Callable[[str, list[str] | None, str], int]
SetLastQuarantinedFn = Callable[[list[Any]], None]
QuarantineLike = Any

logger = logging.getLogger(__name__)


# ── V18.20.2.0 (SWOT A5): shared Qwen-family /no_think injection helper ────


def qwen_no_think(prompt: str, model: str) -> str:
    """V18.20.2.0 (SWOT A5): append ``/no_think`` for Qwen-family models.

    The V18.2.41 ``/no_think`` injection lives in
    ``Summarizer._call_llm_with_empty_retry`` (and MUST stay there per the
    hard constraint) — but several call sites invoke ``_call_llm`` DIRECTLY,
    bypassing that injection: the judge gap-fill reprompt
    (bullet_pipeline.py), self-review (summarizer.py + self_review.py),
    the coverage reprompt, the dedicated-thorough first attempt
    (thorough_fallback.py), and the map-reduce map/reduce calls
    (map_reduce.py). On Qwen/Qwythos-family thinking-capable models those
    paths can return chain-of-thought that the empty-retry logic never
    sees (the first attempt "succeeds" per the V18.2.41 rationale),
    reopening the CoT-becomes-summary catastrophic class (the V18.16.0.0
    2/10 regression).

    This helper provides ONE shared, idempotent injection point for those
    direct ``_call_llm`` sites. Cloud paths (``_call_cloud``) must NOT use
    it — the directive is an Ollama/Qwen-family mechanism.

    Args:
        prompt: the prompt string about to be sent.
        model: the model name (case-insensitive match on ``qwen`` /
            ``qwythos``).

    Returns:
        ``prompt + " /no_think"`` for Qwen-family models (skipped when the
        prompt already ends with ``/no_think`` — idempotent), otherwise the
        prompt unchanged.
    """
    _model_lower = (model or "").lower()
    if "qwen" not in _model_lower and "qwythos" not in _model_lower:
        return prompt
    if prompt.rstrip().endswith("/no_think"):
        return prompt  # already injected — idempotent
    return prompt + " /no_think"


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


def _noop_set_last_quarantined(value: list[Any]) -> None:
    """Default no-op setter for _last_quarantined."""
    pass


def _default_score_bullet(bullet, concepts=None, source_text=""):
    """Default scorer — returns 100 (keeps everything) when none supplied."""
    return 100


# ── filter_thinking_bullets (extracted verbatim) ───────────────────────────

def filter_thinking_bullets(
    bullets: list,
    concepts: list[str] | None = None,
    source_text: str = "",
    current_heading: str = "",
    conservative_drops: bool = False,
    quarantine: QuarantineLike | None = None,
    score_bullet: ScoreBulletFn | None = None,
    max_bullets_per_chapter: int = 30,
    log: LogCallback | None = None,
    set_last_quarantined: SetLastQuarantinedFn | None = None,
) -> list[str]:
    """Filter out thinking-process contamination AND narrative/story bullets.

    For non-fiction books, keypoints should be concepts, principles, and
    actionable insights — NOT narrative descriptions. Thinking-process
    contamination: the model sometimes leaks its reasoning into the
    bullet_points list. Narrative bullets: describe what happened in the
    story rather than the concept being illustrated.

    The pure classification logic is delegated to
    ``post_processing.classify_bullets`` (pattern matching + drop-reason
    recording). This function keeps the quarantine-logging side-effect (it
    calls ``quarantine.add()`` for each drop record, applying the
    conservative-mode decision) + the quality-scoring trim.
    """
    if log is None:
        log = _noop_log
    if score_bullet is None:
        score_bullet = _default_score_bullet
    if set_last_quarantined is None:
        set_last_quarantined = _noop_set_last_quarantined

    from core.summarisation.post_processing import classify_bullets as _pp_classify

    # V18.20.3.1 (real-rig audit D5): snapshot the quarantine entry count at
    # ENTRY — the end-of-call summary only logs when this call added entries
    # (the gap-fill loop calls this function per added bullet; without the
    # snapshot the unchanged cumulative summary was re-logged 8×).
    _q_before = len(getattr(quarantine, "entries", []) or []) if quarantine is not None else 0

    _chapter_ctx = current_heading or ""
    _cons = conservative_drops

    # Delegate the pure classification logic.
    filtered, drops = _pp_classify(bullets, concepts=concepts, source_text=source_text)

    # In conservative mode, conservative-gated drops (always_drop=False)
    # are KEPT — they're logged but not actually dropped. Add them back
    # to filtered so they appear in the output. (always_drop=True drops
    # are structural contamination — always excluded.)
    if _cons:
        for _bp, _stage, _reason, _always in drops:
            if not _always and len(_bp) > 2:
                filtered.append(_bp)

    # Apply the quarantine-logging side-effect for each drop record.
    # always_drop=True → structural contamination, dropped even in
    # conservative mode. always_drop=False → conservative-gated, logged
    # but kept in conservative mode.
    # V18.20.2.0 (SWOT A17): quarantine is OPTIONAL (default None) — guard
    # every quarantine use so direct callers that omit it get the DROP
    # behaviour without an AttributeError on the first drop. The drop
    # itself is NOT conditional: classification happens above; only the
    # audit-trail logging is skipped.
    dropped = 0
    narrative_dropped = 0
    for _bp, _stage, _reason, _always in drops:
        _actually = _always or (not _cons)
        if _actually:
            if "narrative" in _stage:
                narrative_dropped += 1
            else:
                dropped += 1
        if quarantine is not None:
            quarantine.add(
                _bp, stage=_stage, reason=_reason + (
                    " (kept — conservative mode)." if (_cons and not _always) else "."
                ),
                chapter=_chapter_ctx, actually_dropped=_actually,
            )

    # Bullet quality scoring — score each bullet 0-100 and
    # drop those below 40. This replaces ad-hoc filtering with principled
    # quality gates. Bullets are ranked by score; top N kept.
    # (NOT extracted — depends on score_bullet + max_bullets_per_chapter)
    if filtered and concepts is not None:
        scored = [(bp, score_bullet(bp, concepts, source_text)) for bp in filtered]
        # Drop bullets below 40/100
        kept = [(bp, sc) for bp, sc in scored if sc >= 25]  # V10.26.0: was 40 (too aggressive)
        low_dropped = len(scored) - len(kept)
        # V18.20.2.0 (SWOT A17): sort by quality score ONLY when the trim
        # will actually remove bullets (len(kept) > max_bullets_per_chapter).
        # Previously the sort reordered ALL bullets even when the cap made
        # the slice a no-op (e.g. max_bullets=99999) — final Key Takeaways
        # shipped in score order instead of source order. `kept` preserves
        # source order (it is an order-preserving filter of `scored`).
        if len(kept) > max_bullets_per_chapter:
            kept.sort(key=lambda x: -x[1])
            filtered = [bp for bp, _ in kept[:max_bullets_per_chapter]]
        else:
            filtered = [bp for bp, _ in kept]
        if low_dropped > 0:
            for bp, sc in scored:
                if sc < 25:
                    if quarantine is not None:
                        quarantine.add(
                            bp, stage="quality_scorer",
                            threshold=25.0, source_overlap=0.0,
                            reason=f"Quality score {sc}/100 < 25 threshold"
                                   + (" (kept — conservative mode)" if _cons else ""),
                            chapter=_chapter_ctx,
                            actually_dropped=not _cons,
                        )
            log(
                f"    🎯 Quality scorer: {'would drop' if _cons else 'dropped'} "
                f"{low_dropped} low-score bullets "
                f"(avg score: {sum(sc for _, sc in scored) / len(scored):.0f}/100)",
                "DEBUG",
            )
            # In conservative mode, keep ALL bullets (don't apply the
            # score-based trim).  The max_bullets_per_chapter cap is the
            # only thing that still applies, and even that is relaxed
            # below.
            if _cons:
                filtered = [bp for bp, _ in scored]

    if dropped > 0 or narrative_dropped > 0:
        log(
            f"    🧹 Filtered {dropped} thinking + {narrative_dropped} narrative bullets "
            f"+ 0 truncated (kept {len(filtered)})",
            "DEBUG",
        )
    # V10.28.0 (Sprint 1): Log the unified quarantine summary.  The
    # quarantine log is the single source of truth — rebuild the legacy
    # _last_quarantined list from it for backward compatibility.
    # V18.20.2.0 (SWOT A17): quarantine is optional — skip the audit-trail
    # summary when no quarantine object was supplied.
    # V18.20.3.1 (real-rig audit D5): emit the summary ONLY when this call
    # actually added entries (or dropped bullets). The backward-compat
    # set_last_quarantined still runs whenever a quarantine exists.
    _q_summary = quarantine.summary() if quarantine is not None else {}
    if _q_summary:
        _q_now = len(getattr(quarantine, "entries", []) or []) or sum(_q_summary.values())
        if _q_now > _q_before or dropped > 0 or narrative_dropped > 0:
            log(
                f"    📋 Quarantine: {sum(_q_summary.values())} bullet drop(s) recorded. "
                f"Stages: {_q_summary}",
                "INFO",
            )
        set_last_quarantined([
            (e.bullet[:80], e.stage) for e in quarantine.entries
        ])
    return filtered
