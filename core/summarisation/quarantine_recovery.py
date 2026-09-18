"""V18.15 (Phase 5 Stage 3, Batch 3.1): Quarantine recovery pass.

Extracted verbatim from ``Summarizer._recover_quarantined`` (god-class
decomposition Stage 3). Re-scans the quarantine and resurrects bullets
whose source overlap exceeds the recovery threshold.

**Extraction map**:

| Summarizer method (old) | quarantine_recovery function (new) | self deps |
|--------------------------|-------------------------------------|-----------|
| ``_recover_quarantined``  | ``recover_quarantined``            | ``quarantine``, ``log`` |

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

LogCallback = Callable[[str, str], None]
QuarantineLike = Any


def _noop_log(msg: str, level: str = "INFO") -> None:
    pass


def recover_quarantined(
    bullets: list[str],
    source_text: str,
    *,
    quarantine: QuarantineLike,
    log: LogCallback = None,
    bullet_cap: int | None = None,
) -> list[str]:
    """Re-scan the quarantine and resurrect high-overlap bullets.

    Extracted verbatim from ``Summarizer._recover_quarantined``. The only
    changes are ``self.X`` → named parameters.

    Called once at the end of ``_summarize_inner``, after every drop site
    has run. Asks the ``QuarantineLog`` to find entries whose ``source_overlap``
    exceeds the recovery threshold (0.30 by default) and marks them
    ``recovered=True`` on disk. This method then re-inserts the resurrected
    bullet texts into ``bullets``.

    Dedup-aware: a resurrected bullet that is a near-duplicate of one already
    in ``bullets`` is skipped (we don't want to resurrect a bullet that was
    already kept under a different wording).

    V0.06 (rig audit F4-b): ``bullet_cap`` (the source-scaled budget from
    length_policy.bullet_cap) is a HARD CAP — resurrection stops when the
    chapter is at its cap (``None``/``<= 0`` = uncapped, legacy behaviour).
    """
    log = log or _noop_log
    try:
        resurrected = quarantine.recover(source_text=source_text)
    except Exception as _e:
        # V18.20.3.8 (Phase 1 / W9): a crashed recovery pass used to
        # return the bullets unchanged at DEBUG — invisible. The pass is
        # still non-fatal (the chapter must not break over a recovery
        # issue), but the skipped pass is now reported through the
        # conversion log too, so a missing recovery is never mistaken for
        # "nothing to recover".
        logger.warning(
            "recovery pass crashed: %s: %s — bullets returned unchanged "
            "(no resurrection attempted)",
            type(_e).__name__, _e,
        )
        log(
            f"  ⚠️ Quarantine recovery pass CRASHED "
            f"({type(_e).__name__}: {_e}) — no bullets resurrected",
            "WARNING",
        )
        return bullets

    if not resurrected:
        return bullets

    try:
        from rapidfuzz import fuzz as rf_fuzz
        _has_fuzz = True
    except Exception:
        _has_fuzz = False

    existing_norms = [
        re.sub(r'[^\w\s]', '', str(b).lower()).strip() for b in bullets
    ]
    # V0.06 (F4-b): the source-scaled bullet budget is a hard cap at this
    # insertion site too — no resurrection past the cap.
    _cap_qr = int(bullet_cap) if isinstance(bullet_cap, (int, float)) and bullet_cap else 0
    added = 0
    for entry in resurrected:
        if _cap_qr > 0 and len(bullets) >= _cap_qr:
            if added == 0:
                log(
                    f"    \u267b\ufe0f  V0.06: bullet budget reached "
                    f"({len(bullets)}/{_cap_qr}) — quarantine recovery pass "
                    f"re-inserted nothing (eligible entries stay in "
                    f"logs/drops.jsonl).",
                    "INFO",
                )
            break
        bp = entry.bullet
        if not bp or bp.strip() in [b.strip() for b in bullets]:
            continue
        norm = re.sub(r'[^\w\s]', '', bp.lower()).strip()
        is_dup = False
        if _has_fuzz:
            for ex in existing_norms:
                if rf_fuzz.token_set_ratio(norm, ex) >= 85:
                    is_dup = True
                    break
        if is_dup:
            continue
        bullets.append(bp)
        existing_norms.append(norm)
        added += 1

    if added:
        log(
            f"    \u267b\ufe0f  Recovery: re-inserted {added} quarantined bullet(s) "
            f"with source overlap > {quarantine.recovery_threshold:.0%}. "
            f"Bullet count: {len(bullets) - added} \u2192 {len(bullets)}.",
            "INFO",
        )
    return bullets


__all__ = ["recover_quarantined", "LogCallback"]
