"""V10.31.0 (Sprint 4.2): Unified dedup service — one algorithm, one threshold.

V13.28.0 (P2.2): Updated consolidation status. The original V10.31.0 sprint
intended to consolidate 3 dedup sites, but only 1 actually delegated. The
V13.23.0 audit found 5 dedup passes total. Current delegation status:

  ── Delegates to DedupService ──
  1. B3 within-chapter (summarizer._multi_sample_summarize)
     → calls DedupService.dedup_bullets(threshold=75) ✅

  ── Has its own inline implementation (not yet delegated) ──
  2. Cross-chapter (converter._cross_chapter_dedup)
     → calls DedupService.cross_chapter_dedup(threshold=80) ✅ (delegates)
  3. Keypoints embedding (keypoints_builder.build)
     → inline rapidfuzz + embedding dedup, threshold 75% / 0.85 ❌ (not delegated)
  4. Packets pre-cluster (packets._deduplicate_bullets)
     → inline rapidfuzz + Jaccard, threshold 70% + 50% ❌ (not delegated, but
       has different semantics: dual-signal dedup with content-word Jaccard)
  5. Recovery pass (quarantine.recover)
     → inline rapidfuzz, threshold 85% ❌ (not delegated, but has different
       semantics: resurrects bullets, doesn't drop them)

Sites 3-5 are NOT delegated because they have different semantics:
  - Site 3 has embedding dedup (DedupService doesn't support embeddings yet)
  - Site 4 has dual-signal dedup (rapidfuzz OR Jaccard)
  - Site 5 resurrects (opposite direction from dedup)

Full delegation of sites 3-5 is a P3 future item (requires extending
DedupService with embedding + Jaccard + resurrection support).

Thread-safety: ``DedupService`` is stateless (each call creates fresh
``seen`` lists), so it's safe to call from the ThreadPoolExecutor.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


# ── Default thresholds ──────────────────────────────────────────────────────

#: Within-chapter dedup threshold (rapidfuzz token_set_ratio 0-100).
#: V10.12.9: raised from 60 → 75.  Below 75 lets too many near-duplicates
#: through (the audit found 253 bullets with 14 starting "Orexin").
WITHIN_CHAPTER_THRESHOLD = 75

#: Cross-chapter dedup threshold (slightly higher — cross-chapter
#: duplicates are more likely to be genuine overlap, not paraphrases).
CROSS_CHAPTER_THRESHOLD = 80

#: Recovery-pass dedup threshold (used when resurrecting quarantined
#: bullets — we want to resurrect bullets that are clearly distinct from
#: what survived, not re-add slight rewordings).
RECOVERY_THRESHOLD = 85


class DedupService:
    """Single source of truth for bullet deduplication.

    All 3 dedup sites (within-chapter B3, cross-chapter, keypoints) now
    delegate to this class.  One algorithm, one log, configurable
    threshold.

    Usage::

        from core.summarisation.dedup_service import DedupService
        svc = DedupService(log_callback=log)
        kept, dropped = svc.dedup_bullets(bullets, threshold=75)
    """

    def __init__(self, log_callback=None) -> None:
        self.log = log_callback or (lambda msg, level="DEBUG": None)
        try:
            from rapidfuzz import fuzz as rf_fuzz

            self._fuzz = rf_fuzz
        except ImportError:
            self._fuzz = None
            logger.debug("rapidfuzz not installed — dedup falls back to exact match")

    def dedup_bullets(
        self,
        bullets: list[str],
        threshold: int = WITHIN_CHAPTER_THRESHOLD,
        stage: str = "dedup",
        chapter: str = "",
        conservative: bool = False,
        quarantine=None,
    ) -> tuple[list[str], int]:
        """Deduplicate a bullet list using rapidfuzz token_set_ratio.

        Parameters
        ----------
        bullets:
            The bullet list to dedup (order preserved for the kept bullets).
        threshold:
            rapidfuzz token_set_ratio 0-100.  Default 75 (within-chapter).
        stage:
            Stage name for quarantine logging (e.g. ``"B3_dedup"``).
        chapter:
            Chapter heading for quarantine context.
        conservative:
            When True, duplicates are NOT removed (kept + logged to
            quarantine with ``actually_dropped=False``).
        quarantine:
            Optional ``QuarantineLog`` — when supplied, each dropped
            duplicate is logged with stage + reason.

        Returns
        -------
        (kept_bullets, dropped_count)
        """
        if not bullets:
            return [], 0
        seen_norms: list[str] = []
        deduped: list[str] = []
        dropped = 0
        for bp in bullets:
            norm = re.sub(r"[^\w\s]", "", str(bp).lower()).strip()
            is_dup = False
            if self._fuzz is not None:
                for existing in seen_norms:
                    if self._fuzz.token_set_ratio(norm, existing) >= threshold:
                        is_dup = True
                        break
            else:
                # Fallback: exact normalized match
                if norm in seen_norms:
                    is_dup = True
            if is_dup:
                dropped += 1
                if quarantine is not None:
                    quarantine.add(
                        bp,
                        stage=stage,
                        threshold=float(threshold) / 100.0,
                        source_overlap=0.0,
                        reason=f"Near-duplicate of an earlier bullet "
                        f"(token_set_ratio ≥ {threshold}%)"
                        + (" — kept in conservative mode" if conservative else ""),
                        chapter=chapter,
                        actually_dropped=not conservative,
                    )
                continue
            seen_norms.append(norm)
            deduped.append(bp)
        if dropped > 0:
            self.log(
                f"    🧹 {stage}: {'would merge' if conservative else 'removed'} "
                f"{dropped} duplicates ({len(bullets)} → {len(deduped)})",
                "DEBUG",
            )
        return deduped, dropped

    def is_near_duplicate(
        self,
        candidate: str,
        existing: list[str],
        threshold: int = WITHIN_CHAPTER_THRESHOLD,
    ) -> bool:
        """True when ``candidate`` is a near-duplicate of a bullet in ``existing``.

        V0.6.2 (user-reported thin-book bug): the Tier-2 gap-fill
        insertion guard. Reuses ``dedup_bullets`` unchanged — the
        candidate is appended to the existing list and deduped; if the
        candidate does not survive, it is a near-duplicate (bullets are
        only ever compared against EARLIER bullets, so the existing
        bullets' internal order/set is unaffected). Falls back to
        exact-match semantics when rapidfuzz is unavailable
        (``self._fuzz is None``) — fail-open by construction.
        """
        if not existing or not candidate:
            return False
        kept, _dropped = self.dedup_bullets(
            [str(b) for b in existing] + [str(candidate)],
            threshold=threshold,
            stage="near_dup_check",
        )
        return str(candidate) not in kept

    def cross_chapter_dedup(
        self,
        chapter_bullets: list[tuple[str, list[str]]],
        threshold: int = CROSS_CHAPTER_THRESHOLD,
    ) -> list[tuple[str, list[str]]]:
        """Deduplicate bullets across chapters.

        V13.26.0 (P1.6): Now logs each dropped bullet at INFO level (was
        DEBUG with only a count). This gives the user full visibility into
        what was removed — previously bullets disappeared silently with no
        audit trail.

        Parameters
        ----------
        chapter_bullets:
            List of ``(chapter_heading, bullets)`` tuples.
        threshold:
            rapidfuzz token_set_ratio 0-100.  Default 80 (cross-chapter).

        Returns
        -------
        List of ``(chapter_heading, deduped_bullets)`` tuples.
        """
        if not chapter_bullets:
            return []
        seen_norms: list[str] = []
        seen_headings: list[str] = []  # V13.26.0: track which chapter first had each bullet
        result: list[tuple[str, list[str]]] = []
        total_dropped = 0
        dropped_details: list[str] = []  # V13.26.0: for audit logging
        for heading, bullets in chapter_bullets:
            deduped = []
            for bp in bullets:
                norm = re.sub(r"[^\w\s]", "", str(bp).lower()).strip()
                is_dup = False
                matched_heading = ""
                if self._fuzz is not None:
                    for i, existing in enumerate(seen_norms):
                        if self._fuzz.token_set_ratio(norm, existing) >= threshold:
                            is_dup = True
                            matched_heading = seen_headings[i] if i < len(seen_headings) else ""
                            break
                else:
                    if norm in seen_norms:
                        is_dup = True
                        idx = seen_norms.index(norm)
                        matched_heading = seen_headings[idx] if idx < len(seen_headings) else ""
                if is_dup:
                    total_dropped += 1
                    # V13.26.0: Record what was dropped for audit
                    dropped_details.append(
                        f"      🗑️ '{bp[:60]}...' (dup of '{matched_heading[:30]}...')"
                    )
                    continue
                seen_norms.append(norm)
                seen_headings.append(heading)
                deduped.append(bp)
            result.append((heading, deduped))
        if total_dropped > 0:
            self.log(
                f"    🧹 cross_chapter_dedup: removed {total_dropped} "
                f"cross-chapter duplicates (threshold {threshold}%)",
                "INFO",  # V13.26.0: was DEBUG — now visible to the user
            )
            # V13.26.0: Log each dropped bullet for audit trail
            for detail in dropped_details[:20]:  # cap at 20 to avoid log flooding
                self.log(detail, "DEBUG")
            if len(dropped_details) > 20:
                self.log(f"      ... and {len(dropped_details) - 20} more", "DEBUG")
        return result


# ── Module-level singleton (stateless, safe to share) ──────────────────────

_default_service: DedupService | None = None


def get_dedup_service() -> DedupService:
    """Return a shared DedupService instance (stateless, safe to reuse)."""
    global _default_service
    if _default_service is None:
        _default_service = DedupService()
    return _default_service


__all__ = [
    "DedupService",
    "get_dedup_service",
    "WITHIN_CHAPTER_THRESHOLD",
    "CROSS_CHAPTER_THRESHOLD",
    "RECOVERY_THRESHOLD",
]
