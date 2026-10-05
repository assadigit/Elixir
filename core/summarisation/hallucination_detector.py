"""V13.24.0 (P0.2): HallucinationDetector — unified facade for the standalone
Hallucination Audit tool.

WHY THIS EXISTS
---------------
The HallucinationAuditDialog (in ``ui_qt/views/service_dialogs/base_dialog.py``)
was broken since V13.20.1 — it imported ``HallucinationDetector`` from this
module, but the module didn't exist. Every click of "🛡️ Audit Bullets" threw
``ModuleNotFoundError``.

The functionality the dialog needed (4-signal hallucination check) already
existed in scattered functions across the codebase:
  - ``compute_source_overlap`` — F4 content-word overlap (text_preprocessor.py)
  - ``semantic_fact_check`` — Phase 2.2 embedding similarity (text_preprocessor.py)
  - ``verify_numbers_and_quotes`` — C4 number/quote verification (text_preprocessor.py)
  - langextract verbatim grounding — Layer 8 (claim_extractor.py, optional)

This module is a thin facade that unifies these signals into the
``HallucinationDetector.detect_and_filter()`` API the dialog expects. It does
NOT re-implement any logic — it delegates to the existing functions.

4-SIGNAL CHECK
--------------
For each bullet, the detector computes:

1. **Content-word overlap** (F4) — what % of the bullet's content words
   appear in the source? (``compute_source_overlap``)
2. **Semantic similarity** (Phase 2.2) — best embedding cosine similarity
   to any source sentence. (``semantic_fact_check``)
3. **Number/quote verification** (C4) — are all numbers/quotes in the bullet
   found verbatim in the source? (``verify_numbers_and_quotes``)
4. **Verbatim grounding** (Layer 8, optional) — does langextract find a
   verbatim source span? Falls back to rapidfuzz partial_ratio if
   langextract is unavailable.

VERDICT LOGIC
-------------
- **🗑️ Dropped**: bullet fails ≥2 of the 4 signals (clearly hallucinated)
- **⚠️ Flagged**: bullet fails exactly 1 signal (suspicious, needs review)
- **✅ Grounded**: bullet passes all signals (or fails none critically)

The ``detect_and_filter`` method returns ``(filtered_bullets, reports)`` where:
- ``filtered_bullets``: list of bullets that were NOT dropped (grounded + flagged)
- ``reports``: list of per-bullet dicts with keys:
  - ``bullet`` (str): the original bullet text
  - ``action`` (str): "kept" / "flagged" / "dropped"
  - ``reason`` (str): human-readable explanation
  - ``source_overlap`` (float 0-1): F4 content-word overlap
  - ``semantic_similarity`` (float 0-1): best embedding similarity
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class HallucinationDetector:
    """V13.24.0: Unified hallucination detection facade.

    Wraps the existing 4 anti-hallucination signals into a single API
    for the standalone Hallucination Audit tool. Does NOT re-implement
    any logic — delegates to:
      - ``text_preprocessor.compute_source_overlap`` (F4)
      - ``text_preprocessor.semantic_fact_check`` (Phase 2.2)
      - ``text_preprocessor.verify_numbers_and_quotes`` (C4)
      - ``claim_extractor.ClaimExtractor`` (Layer 8, optional)
    """

    # Thresholds (aligned with the existing pipeline layers)
    OVERLAP_THRESHOLD = 0.25  # F4: drop if below
    SEMANTIC_THRESHOLD = 0.42  # V13.22.0 relaxed threshold (was 0.50)
    PARTIAL_RATIO_THRESHOLD = 0.50  # rapidfuzz fallback for verbatim

    def detect_and_filter(
        self,
        bullets: list[str],
        source_text: str,
        label: str = "Audit",
    ) -> tuple[list[str], list[dict]]:
        """Run the 4-signal hallucination check on each bullet.

        Args:
            bullets: List of bullet strings to check.
            source_text: The original source text to check against.
            label: A label for logging (e.g., chapter heading).

        Returns:
            ``(filtered_bullets, reports)`` where:
            - filtered_bullets: bullets NOT dropped (grounded + flagged)
            - reports: per-bullet dicts with verdict + signals
        """
        if not bullets or not source_text:
            return list(bullets), []

        # Lazy imports (these modules may have optional deps)
        try:
            from core.summarisation.text_preprocessor import (
                compute_source_overlap,
                semantic_fact_check,
                verify_numbers_and_quotes,
            )
        except ImportError as e:
            logger.error("Cannot import text_preprocessor signals: %s", e)
            # Fail-open: return all bullets as "kept" with empty reports
            return list(bullets), [
                {
                    "bullet": b,
                    "action": "kept",
                    "reason": "signal import failed — fail-open",
                    "source_overlap": 0.0,
                    "semantic_similarity": 0.0,
                }
                for b in bullets
            ]

        # Optional: langextract verbatim grounding (Layer 8)
        claim_extractor = None
        try:
            from core.grounding.claim_extractor import ClaimExtractor

            claim_extractor = ClaimExtractor()
        except Exception:
            # langextract is optional — fall back to rapidfuzz partial_ratio
            pass

        reports: list[dict] = []
        filtered: list[str] = []

        for bullet in bullets:
            report = self._check_single_bullet(
                bullet,
                source_text,
                compute_source_overlap,
                semantic_fact_check,
                verify_numbers_and_quotes,
                claim_extractor,
            )
            reports.append(report)
            if report["action"] != "dropped":
                filtered.append(bullet)

        # Log summary
        grounded = sum(1 for r in reports if r["action"] == "kept")
        flagged = sum(1 for r in reports if r["action"] == "flagged")
        dropped = sum(1 for r in reports if r["action"] == "dropped")
        logger.info(
            "%s: %d grounded, %d flagged, %d dropped (of %d total)",
            label,
            grounded,
            flagged,
            dropped,
            len(reports),
        )

        return filtered, reports

    def _check_single_bullet(
        self,
        bullet: str,
        source_text: str,
        compute_source_overlap,
        semantic_fact_check,
        verify_numbers_and_quotes,
        claim_extractor=None,
    ) -> dict:
        """Run all 4 signals on a single bullet and produce a report."""

        # Signal 1: F4 content-word overlap
        try:
            overlap = compute_source_overlap(bullet, source_text)
        except Exception:
            overlap = 1.0  # fail-open
        overlap_pass = overlap >= self.OVERLAP_THRESHOLD

        # Signal 2: Phase 2.2 semantic similarity
        try:
            sem_result = semantic_fact_check(
                bullet,
                source_text,
                threshold=self.SEMANTIC_THRESHOLD,
            )
            similarity = sem_result.get("best_similarity", 0.0)
            sem_pass = sem_result.get("is_grounded", True)
        except Exception:
            similarity = 1.0
            sem_pass = True  # fail-open
        sem_pass = sem_pass and similarity >= self.SEMANTIC_THRESHOLD

        # Signal 3: C4 number/quote verification
        try:
            num_valid, num_reasons = verify_numbers_and_quotes(bullet, source_text)
            num_pass = num_valid
        except Exception:
            num_pass = True  # fail-open
            num_reasons = []

        # Signal 4: Verbatim grounding (Layer 8 or rapidfuzz fallback)
        verbatim_pass = False
        verbatim_reason = ""
        if claim_extractor is not None:
            try:
                claims = claim_extractor.extract(bullet, source_text)
                if claims:
                    verbatim_pass = any(c.get("char_interval") is not None for c in claims)
                    # V0.6.0: the reason must match the verdict — claims
                    # without a span used to report "verbatim span found"
                    # on a FAILED verbatim check.
                    verbatim_reason = (
                        "langextract verbatim span found" if verbatim_pass else "no verbatim span"
                    )
                else:
                    verbatim_reason = "no verbatim span"
            except Exception as e:
                logger.debug("Layer 8 failed, falling back to rapidfuzz: %s", e)
                verbatim_pass = self._rapidfuzz_verbatim_check(bullet, source_text)
                verbatim_reason = "rapidfuzz fallback"
        else:
            verbatim_pass = self._rapidfuzz_verbatim_check(bullet, source_text)
            verbatim_reason = "rapidfuzz (langextract unavailable)"

        # Count failures
        failures = []
        if not overlap_pass:
            failures.append(f"F4 overlap {overlap:.0%} < {self.OVERLAP_THRESHOLD:.0%}")
        if not sem_pass:
            failures.append(f"semantic sim {similarity:.2f} < {self.SEMANTIC_THRESHOLD}")
        if not num_pass:
            failures.append(f"numbers/quotes: {'; '.join(num_reasons[:2])}")
        if not verbatim_pass:
            failures.append(f"no verbatim grounding ({verbatim_reason})")

        # Verdict logic
        if len(failures) >= 2:
            action = "dropped"
            reason = f"Dropped: {'; '.join(failures[:3])}"
        elif len(failures) == 1:
            action = "flagged"
            reason = f"Flagged: {failures[0]}"
        else:
            action = "kept"
            reason = "All 4 signals passed"

        return {
            "bullet": bullet,
            "action": action,
            "reason": reason,
            "source_overlap": overlap,
            "semantic_similarity": similarity,
        }

    def _rapidfuzz_verbatim_check(self, bullet: str, source_text: str) -> bool:
        """Fallback verbatim check using rapidfuzz partial_ratio.

        Slides an 80-char window across the source and checks if any window
        has a partial_ratio >= the threshold. This is the same approach as
        the pipeline's Layer A (_verify_bullets).
        """
        try:
            from rapidfuzz import fuzz as _rf_fuzz
        except ImportError:
            try:
                # Simple check: is the bullet a substring of the source?
                return bullet.lower() in source_text.lower()
            except Exception:
                return True  # fail-open

        try:
            window_size = 80
            bullet_len = len(bullet)
            source_lower = source_text.lower()

            # If bullet is longer than the window, compare directly
            if bullet_len >= window_size:
                score = _rf_fuzz.partial_ratio(bullet.lower(), source_lower)
                return score >= self.PARTIAL_RATIO_THRESHOLD * 100

            # Slide a window across the source
            for i in range(0, len(source_text) - window_size + 1, 20):
                window = source_text[i : i + window_size + bullet_len]
                score = _rf_fuzz.partial_ratio(bullet.lower(), window.lower())
                if score >= self.PARTIAL_RATIO_THRESHOLD * 100:
                    return True
            return False
        except Exception:
            return True  # fail-open
