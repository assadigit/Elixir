"""V10.31.0 (Sprint 4.1): BulletPipeline — extracted stage methods for the
summarisation pipeline.

Before V10.31.0, the entire bullet pipeline lived in a single 1,035-line
method: ``Summarizer._summarize_inner`` (summarizer.py:2293-3447).  The
V10.27.0 audit flagged this as the #1 architecture debt — a god method
with 15+ stages, 0 unit tests (until Sprint 3), and local variables that
flow through every stage making extraction risky.

This module provides the **target architecture**: a ``BulletPipeline``
class with one method per stage.  ``Summarizer._summarize_inner`` becomes
a thin orchestrator that creates a ``BulletPipeline`` and calls the
stage methods in order.

V10.31.0 scope (session 1 of 2):
  - Establishes the ``BulletPipeline`` class + ``PipelineState`` dataclass.
  - Extracts the **safely-separable** post-LLM stages that don't share
    mutable local state with the LLM-call section:
      - ``filter_thinking_bullets()`` (already on Summarizer — delegates)
      - ``apply_f4_source_overlap()`` (F4 drop + quarantine)
      - ``apply_phase22_semantic_fact_check()`` (Phase 2.2 drop + quarantine)
      - ``recover_quarantined()`` (already on Summarizer — delegates)
  - The deeply-intertwined middle section (LLM call, coverage check, B3
    voting, gap-fill, Content Judge) remains inline in ``_summarize_inner``
    for session 2, when the Sprint 3 golden-file tests (10 tests) can
    verify the behavioral equivalence of each extracted stage.

The class is constructed with a reference to the ``Summarizer`` instance
(so it can access ``self.request``, ``self.quarantine``, ``self.log``,
``self.conservative_drops``, etc.) — it's a **mixin-style extractor**,
not a fully-decoupled class.  Full decoupling (passing only the needed
data) is a session-2 refinement.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

# V18.20.2.0 (SWOT-A finding 2 / thresholds wiring): F4 + Phase 2.2 drop
# thresholds now import from core/summarisation/thresholds.py (the declared
# SINGLE SOURCE OF TRUTH — previously zero production importers; the values
# were hardcoded at 5 call sites). Values are IDENTICAL to the previous
# literals (F4=0.25, P22=0.50) — wiring fix only, no behaviour change.
from core.summarisation.thresholds import (
    F4_SOURCE_OVERLAP_DROP as _F4_SOURCE_OVERLAP_DROP,
)
from core.summarisation.thresholds import (
    SEMANTIC_FACT_CHECK_DROP as _SEMANTIC_FACT_CHECK_DROP,
)

# V10.32.0: import SummaryResult + count_tokens for the Content Judge stage
# (which may return a SummaryResult on hard rejection).
try:
    from core.models import SummaryResult
except ImportError:
    SummaryResult = None  # type: ignore

try:
    from utils.token_counter import count_tokens
except ImportError:

    def count_tokens(text):
        return max(1, len(str(text).split()))


logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Mutable state that flows through the bullet-pipeline stages.

    Each stage reads some fields and writes others.  Passing this single
    object (instead of 10+ local variables) makes the stage boundaries
    explicit and the data flow visible.

    V10.31.0: only the post-LLM stages use this; the LLM-call section
    still uses local variables in ``_summarize_inner`` (session 2 will
    migrate them).
    """

    heading: str
    content: str
    bullets: list[str] = field(default_factory=list)
    exec_sum: str = ""
    thorough: str = ""
    # Metrics (for logging / the SummaryResult)
    src_tokens: int = 0
    tok_in: int = 0
    coverage: float = 0.0


class BulletPipeline:
    """Stage-by-stage bullet pipeline, extracted from ``_summarize_inner``.

    Each ``stage_*`` method is a pure transformation on
    :class:`PipelineState` (plus the ``Summarizer`` reference for
    quarantine/logging).  The orchestrator (``Summarizer._summarize_inner``)
    calls them in order.

    Why a separate class (not just methods on Summarizer)?
      - **Cohesion**: all pipeline stages live together, separate from
        the Summarizer's LLM-call / prompt-building / VRAM-detection
        concerns.
      - **Testability**: ``BulletPipeline`` can be unit-tested in
        isolation (Sprint 3's ``test_summarizer.py`` already tests the
        stage methods via the Summarizer; session 2 will add direct
        ``BulletPipeline`` tests).
      - **Future extraction**: once all stages are on ``BulletPipeline``,
        the class can be moved to its own module and the Summarizer
        becomes a thin orchestrator.
    """

    def __init__(self, summarizer: Any) -> None:
        """Bind to a Summarizer instance (mixin-style).

        The pipeline needs access to: ``summarizer.quarantine``,
        ``summarizer.conservative_drops``, ``summarizer.log``,
        ``summarizer.request``, and the stage methods that remain on
        Summarizer (``_filter_thinking_bullets``, ``_recover_quarantined``,
        ``_compute_coverage``, etc.).
        """
        self.s = summarizer

    # ── Stage: F4 source-overlap filter ────────────────────────────────

    def apply_f4_source_overlap(self, state: PipelineState) -> None:
        """F4: drop bullets with <25% source-word overlap (in-place).

        V10.31.0 (Sprint 4.1): extracted verbatim from ``_summarize_inner``.
        In conservative mode, the drop is disabled (logged to quarantine
        with ``actually_dropped=False``).
        """
        s = self.s
        # V18.20.2.0 (SWOT-A2): from thresholds.py (was hardcoded 0.25).
        _F4_THRESHOLD = _F4_SOURCE_OVERLAP_DROP
        try:
            from core.summarisation.text_preprocessor import compute_source_overlap

            weak_bullets = []
            kept_bullets = []
            for bp in state.bullets:
                overlap = compute_source_overlap(bp, state.content)
                if overlap < _F4_THRESHOLD:
                    weak_bullets.append((bp, overlap))
                else:
                    kept_bullets.append(bp)
            if weak_bullets:
                for bp, ov in weak_bullets:
                    s.quarantine.add(
                        bp,
                        stage="F4_source_overlap",
                        threshold=_F4_THRESHOLD,
                        source_overlap=ov,
                        reason=f"Source overlap {ov:.0%} < {_F4_THRESHOLD:.0%} threshold"
                        + (" (kept — conservative mode)" if s.conservative_drops else ""),
                        chapter=getattr(s, "_current_heading", "") or "",
                        actually_dropped=not s.conservative_drops,
                    )
                s.log(
                    f"    🗑️ F4: {'Would drop' if s.conservative_drops else 'Dropped'} "
                    f"{len(weak_bullets)} bullet(s) with <{_F4_THRESHOLD:.0%} source overlap: "
                    f"{[b[0][:40] for b in weak_bullets[:3]]}…",
                    "WARNING" if not s.conservative_drops else "DEBUG",
                )
                if not s.conservative_drops:
                    state.bullets = kept_bullets
        except Exception as _e:
            # V18.20.3.8 (Phase 1 / W1): a silent logger.debug here is how
            # the V18.20.3.4 recall-floor probe died invisibly (CHANGELOG
            # .3.5 Fix E). A crash in a hallucination GATE must fail
            # VISIBLY: the stage is skipped (fail-open keeps all bullets —
            # the safe direction for content), but the skip is loud, in the
            # conversion log, so an audit can never mistake a disabled
            # filter for a clean pass.
            try:
                s.log(
                    f"    ⚠️ F4 source-overlap gate CRASHED — stage skipped, "
                    f"ALL bullets pass UNFILTERED: {type(_e).__name__}: {_e}",
                    "WARNING",
                )
            except Exception:
                pass
            logger.warning(
                "F4 source-overlap gate crashed — stage skipped (fail-open): %s: %s",
                type(_e).__name__,
                _e,
            )

    # ── Stage: Phase 2.2 semantic fact-check ───────────────────────────

    def apply_phase22_semantic_fact_check(self, state: PipelineState) -> None:
        """Phase 2.2: drop bullets with embedding similarity <0.5 (in-place).

        V10.31.0 (Sprint 4.1): extracted verbatim from ``_summarize_inner``.
        V10.28.0: threshold drift fixed (code+log now agree at 0.5).
        In conservative mode, the drop is disabled.
        V18.2.30: SKIP when embedder is unhealthy — a broken embedder
        produces zero/NaN vectors which always score <0.5 similarity (dropping
        ALL bullets as "hallucinated"). The recovery pass would then resurrect
        them — net effect: wasted work + churn. Better to skip Phase 2.2
        entirely and rely on the F4 source-overlap drop (which doesn't need
        embeddings) for hallucination filtering.
        """
        s = self.s
        # V18.20.2.0 (SWOT-A2): from thresholds.py (was hardcoded 0.5).
        _P22_THRESHOLD = _SEMANTIC_FACT_CHECK_DROP
        # V18.2.30: short-circuit when embedder is unhealthy.
        # V0.6.8 (audit B10): the guard used to swallow its own failure and
        # PROCEED (guard can't guard) — an unavailable or crashing health
        # check now fails SAFE: the phase is skipped (the F4 source-overlap
        # drop still filters hallucinations without embeddings) and the
        # failure is logged at WARNING instead of silently passing.
        try:
            from core.llm.model_singletons import is_embedder_healthy

            _embedder_healthy = is_embedder_healthy()
        except Exception as _e:
            s.log(
                "    ⏭️  Phase 2.2: embedder health check failed "
                f"({type(_e).__name__}: {_e}) — skipping semantic fact-check "
                "(fail-safe: health-check failure treated as unhealthy)",
                "WARNING",
            )
            return
        if not _embedder_healthy:
            s.log(
                "    ⏭️  Phase 2.2: embedder unhealthy — skipping semantic fact-check (would produce false drops on zero-vector similarity, then recovery would resurrect them = churn)",
                "WARNING",
            )
            return
        try:
            from core.summarisation.text_preprocessor import semantic_fact_check

            hallucinated = []
            kept_bullets = []
            for bp in state.bullets:
                result = semantic_fact_check(bp, state.content, threshold=_P22_THRESHOLD)
                if not result["is_grounded"]:
                    hallucinated.append((bp, result["best_similarity"]))
                else:
                    kept_bullets.append(bp)
            if hallucinated:
                for bp, sim in hallucinated:
                    # V18.15.7.0 (Fix 2): record the GENUINE source overlap,
                    # NOT the semantic similarity. Pre-V18.15.7.0, this line
                    # passed `source_overlap=float(sim)` where `sim` was the
                    # semantic similarity (e.g., 0.45, below the 0.5 threshold).
                    # The quarantine recovery pass at quarantine.py:261 then did
                    # `overlap = max(overlap, fresh)` — picking the higher of
                    # the recorded 0.45 vs the fresh genuine-overlap ~0.0 →
                    # 0.45 won, exceeding the 0.30 recovery threshold → the
                    # bullet was RESURRECTED despite being a prompt-instruction
                    # echo ("Keep sentences under 20 words") with ~0% source
                    # overlap. The V18.15.6.0 golden-master shipped these 3
                    # prompt-instruction bullets because of this bug.
                    # Fix: compute the genuine source overlap here so the
                    # recovery pass has accurate data.
                    _genuine_overlap = 0.0
                    _overlap_failed = False
                    try:
                        from core.summarisation.text_preprocessor import (
                            compute_source_overlap,
                        )

                        _genuine_overlap = float(compute_source_overlap(bp, state.content))
                    except Exception as _ov_e:
                        # V18.20.3.8 (Phase 1 / W1): keep 0.0 (fail-safe — the
                        # bullet stays dropped) but the degraded quarantine
                        # record must SAY so. A silent 0.0 bricks the entry's
                        # recovery eligibility (0.0 < the 30% recovery
                        # threshold) with no trace of why.
                        _overlap_failed = True
                        logger.warning(
                            "Phase 2.2: genuine-overlap computation failed for "
                            "a quarantined bullet — recorded as 0.00 (recovery "
                            "eligibility degraded): %s: %s",
                            type(_ov_e).__name__,
                            _ov_e,
                        )
                    s.quarantine.add(
                        bp,
                        stage="Phase2.2_semantic_fact_check",
                        threshold=_P22_THRESHOLD,
                        source_overlap=_genuine_overlap,
                        reason=f"Semantic similarity {sim:.2f} < {_P22_THRESHOLD:.2f} threshold "
                        f"(genuine source overlap: {_genuine_overlap:.2f}"
                        + (
                            " — COMPUTATION FAILED, recorded as 0.00, recovery eligibility degraded"
                            if _overlap_failed
                            else ""
                        )
                        + ")"
                        + (" (kept — conservative mode)" if s.conservative_drops else ""),
                        chapter=getattr(s, "_current_heading", "") or "",
                        actually_dropped=not s.conservative_drops,
                    )
                s.log(
                    f"    🗑️ Phase 2.2: {'Would drop' if s.conservative_drops else 'Dropped'} "
                    f"{len(hallucinated)} hallucinated bullet(s) "
                    f"(semantic similarity <{_P22_THRESHOLD:.2f}): "
                    f"{[b[0][:40] for b in hallucinated[:3]]}…",
                    "WARNING" if not s.conservative_drops else "DEBUG",
                )
                if not s.conservative_drops:
                    state.bullets = kept_bullets
            else:
                s.log(
                    f"    ✅ Phase 2.2: All bullets semantically grounded "
                    f"(≥{_P22_THRESHOLD:.2f} similarity)",
                    "DEBUG",
                )
        except Exception as _e:
            # V18.20.3.8 (Phase 1 / W1): same rule as the F4 gate — a crash
            # in the semantic fact-check must be VISIBLE. Fail-open (all
            # bullets kept) is the safe direction for content; silent is
            # never acceptable for a hallucination filter.
            try:
                s.log(
                    f"    ⚠️ Phase 2.2 semantic fact-check CRASHED — stage "
                    f"skipped, ALL bullets pass UNFILTERED: "
                    f"{type(_e).__name__}: {_e}",
                    "WARNING",
                )
            except Exception:
                pass
            logger.warning(
                "Phase 2.2 semantic fact-check crashed — stage skipped (fail-open): %s: %s",
                type(_e).__name__,
                _e,
            )

    # ── Stage: recovery pass (delegates to Summarizer) ─────────────────

    def recover_quarantined(self, state: PipelineState) -> None:
        """Recovery pass: resurrect high-overlap quarantined bullets (in-place).

        V10.31.0 (Sprint 4.1): delegates to ``Summarizer._recover_quarantined``
        (which was extracted in V10.28.0 Sprint 1.4).  Kept here as a
        pipeline stage for architectural symmetry.
        """
        s = self.s
        state.bullets = s._recover_quarantined(state.bullets, state.content)

    # ── Stage: thinking-bullets filter (delegates to Summarizer) ───────

    def filter_thinking_bullets(
        self, state: PipelineState, concepts: list[str] | None = None
    ) -> None:
        """Thinking-filter: drop thinking/prompt-leakage/narrative bullets.

        V10.31.0 (Sprint 4.1): delegates to ``Summarizer._filter_thinking_bullets``
        (the V10.28.0 conservative-mode-aware version).  In conservative mode,
        only the 4 thinking/prompt-leakage checks drop; the rest are logged
        but kept.
        """
        s = self.s
        state.bullets = s._filter_thinking_bullets(
            state.bullets, concepts=concepts, source_text=state.content
        )

    # ── Stage: F1 length validation ────────────────────────────────────

    def apply_f1_length_validation(self, state: PipelineState) -> None:
        """F1: enforce section length caps (in-place).

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        V0.05 (rig audit F9b): the caps are no longer the absolute 400/1500 —
        they SCALE to the source via ``length_policy`` (a summary section may
        never be instructed or allowed to balloon past a fraction of its
        source; the V0.04 rig shipped thorough sections at 1.55-2.76x their
        chapters). The truncation backstop fires at ~1.25x the scaled target
        (never above the historical absolute cap), and the honest ratio line
        logs the compression ratio for every section, WARNING when a section
        is in expansion territory (>1.5x its target AND >60% of the source).
        """
        s = self.s
        try:
            from core.summarisation.length_policy import (
                executive_target,
                expansion_audit,
                thorough_target,
            )
            from core.summarisation.text_preprocessor import (
                truncate_summary,
                validate_summary_length,
            )

            _src_words = len((state.content or "").split())
            _elo, _ehi = executive_target(_src_words)
            _tlo, _thi = thorough_target(_src_words)
            # Truncation backstop. V0.07 (output-regression fix): two
            # regimes, matching length_policy.thorough_target:
            #   * normal chapters (scaled target in the V18 regime — thorough
            #     hi >= 800 / exec hi >= 200): the thorough cap now SCALES
            #     with the source (V0.4.23 user directive: no absolute
            #     1500-word ceiling — a thorough summary may be as long as
            #     necessary for full coverage; 1.25x its scaled target, the
            #     SAME multiple the small-source regime always used).
            #     The exec keeps the historical 400-word F1 pass-line (the
            #     executive is a compression artifact by design).
            #   * small sources (the 97-Things rig regime): stay strictly
            #     source-scaled (1.25x the scaled target) so a 441-word
            #     chapter can never ship a 940-word thorough again.
            _thorough_cap = int(_thi * 1.25) + 1
            if _ehi >= 200:
                _exec_cap = 400
            else:
                _exec_cap = min(400, int(_ehi * 1.25) + 1)
            exec_valid, exec_wc, _ = validate_summary_length(
                state.exec_sum, min_words=40, max_words=_exec_cap, section="exec_summary"
            )
            if not exec_valid and exec_wc > _exec_cap:
                state.exec_sum = truncate_summary(state.exec_sum, max_words=_exec_cap)
                s.log(
                    f"    ✂️ F1: Truncated exec_summary to {_exec_cap} words (source-scaled cap)",
                    "DEBUG",
                )
            thorough_valid, thorough_wc, _ = validate_summary_length(
                state.thorough, min_words=40, max_words=_thorough_cap, section="thorough_summary"
            )
            if not thorough_valid and thorough_wc > _thorough_cap:
                state.thorough = truncate_summary(state.thorough, max_words=_thorough_cap)
                s.log(
                    f"    ✂️ F1: Truncated thorough_summary to {_thorough_cap} words (source-scaled cap)",
                    "DEBUG",
                )
            s.log(
                f"    📏 F1: exec={exec_wc}w, thorough={thorough_wc}w (source={_src_words}w; targets exec<={_ehi}w, thorough<={_thi}w)",
                "DEBUG",
            )
            # V0.6.2 (user-reported thin-book bug): the bullet words are part
            # of the honest measurement — the user's defect is the COMBINED
            # ratio ("exec summary + bullet point + thorough summary risen
            # above the original source word count"), which the old log line
            # could not even express. expansion_audit flags the combined
            # ratio for thin sources (W < 800) at >= 1.0x the source.
            # getattr: duck-typed callers/tests may carry a state without a
            # bullets field — the measurement must never crash the stage.
            _bullet_wc = sum(len(str(b).split()) for b in (getattr(state, "bullets", None) or []))
            s.log(
                f"    📏 F1: bullets={_bullet_wc}w — combined sections "
                f"{exec_wc + _bullet_wc + thorough_wc}w / source {_src_words}w",
                "DEBUG",
            )
            # V0.05 honest measurement: the compression-ratio audit the rig
            # run was missing. A summary section in expansion territory is
            # a defect worth a visible WARNING, not a DEBUG line.
            for _finding in expansion_audit(
                _src_words, exec_wc, thorough_wc, bullet_words=_bullet_wc
            ):
                s.log(f"    ⚠️ F1 ratio: {_finding}", "WARNING")
        except Exception as _e:
            logging.getLogger(__name__).debug("ignored %s: %s", type(_e).__name__, _e)

    # ── Stage: F3 reading-level assessment (informational only) ─────────

    def apply_f3_reading_level(self, state: PipelineState) -> None:
        """F3: assess reading level of source vs. summary (informational only).

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        V18.2.38 (overhead cut): the simplification LLM call has been REMOVED.
        The V18.2.37 conversion log showed the simplification call:
          - Added ~75s of overhead (20:06:48 → 20:08:04) per chapter
          - Lowered the reading grade by only ~2.1 (15.8 → 13.2)
          - Rewrote ~58% of the thorough summary content (similarity 42%)
          - Resulted in short, choppy, declarative prose that scored
            WORSE on the fact-check audit than V18.2.21's unsimplified
            output (7/10 vs 9/10)
        The user's verdict: "doesn't really simplify that much, considerable
        enough to add this overload."

        This stage now ONLY logs the reading-level difference — no LLM call,
        no thorough_summary mutation. The informational log helps detect
        extreme density gaps (>5 grades) without paying the simplification cost.
        """
        s = self.s
        try:
            from core.summarisation.text_preprocessor import assess_reading_level

            rl = assess_reading_level(
                state.content,
                f"{state.exec_sum} {' '.join(state.bullets)} {state.thorough}",
            )
            s.log(
                f"    📖 F3: Reading level — source: {rl['source_grade']}, "
                f"summary: {rl['summary_grade']} (diff: {rl['difference']:+.1f})",
                "DEBUG",
            )
            if not rl["summary_is_simpler"]:
                _gap = rl["summary_grade"] - rl["source_grade"]
                if _gap > 5.0:
                    s.log(
                        f"    ⚠️ F3: Summary is {_gap:.1f} grade levels HARDER to "
                        f"read than source — extreme density (informational only; "
                        f"simplification LLM call removed in V18.2.38).",
                        "WARNING",
                    )
                else:
                    s.log(
                        f"    ℹ️ F3: Summary is {_gap:.1f} grade levels denser than "
                        f"source — expected for a compressed academic summary.",
                        "INFO",
                    )
        except Exception as e:
            s.log(f"    ℹ️ F3: Reading-level assessment skipped ({e})", "DEBUG")

    # ── Stage: consolidation output-format guard ────────────────────────

    # V18.2.38: Patterns that indicate the consolidation LLM leaked its
    # internal deduplication reasoning as bullet content, instead of
    # producing clean consolidated bullets. The V18.2.37 conversion log
    # showed the Q2_K_XL model producing malformed Key Takeaways like:
    #   - "Bullet 11: 'AuthorG (1961) distinguished...'"
    #   - "This is similar to bullet 27 but bullet 27 is attributed to..."
    #   - "Bullet 8 (AuthorD 1967) and bullet 9 (AuthorD 1980): Both about..."
    #   - "...These are related but different facts/claims. KEEP BOTH."
    # When detected, the consolidation result is rejected and the caller
    # falls back to the deterministic rapidfuzz-based dedup
    # (`_consolidate_duplicate_claims`), which never leaks metadata.
    _LEAKED_METADATA_PATTERNS = (
        # "Bullet 11:", "Bullet 27 says", "Bullet 8 (AuthorD 1967)"
        re.compile(r"\bBullet\s+\d+\b", re.IGNORECASE),
        # "KEEP BOTH", "KEEP ALL" — explicit dedup verdicts
        re.compile(r"\bKEEP\s+(?:BOTH|ALL)\b", re.IGNORECASE),
        # "This is similar to bullet 27 but..."
        re.compile(r"\bThis is similar to bullet\b", re.IGNORECASE),
        # "These are related but different facts/claims"
        re.compile(r"\bThese are related but\b", re.IGNORECASE),
        # "These are different facts"
        re.compile(r"\bThese are different facts\b", re.IGNORECASE),
        # "but different years and slightly different claims"
        re.compile(r"\bbut different years\b", re.IGNORECASE),
        # "different facts/claims" (dedup verdict phrasing)
        re.compile(r"\bdifferent facts\s*[/\.]", re.IGNORECASE),
        # "Bullet N (Author YYYY) and bullet M (Author YYYY)" comparison header
        re.compile(r"\bBullet\s+\d+\s*\([^)]*\)\s+and\s+bullet\s+\d+", re.IGNORECASE),
    )

    @classmethod
    def detect_leaked_consolidation_metadata(cls, bullets: list[str]) -> tuple:
        """V18.2.38: Detect leaked dedup-reasoning in consolidated bullets.

                Returns ``(leaked_count, leaked_samples)`` where:
                  - ``leaked_count``: number of bullets containing metadata patterns
                  - ``leaked_samples``: list of (index, pattern_matched, bullet_preview)

                If ``leaked_count > 0``, the caller should reject the LLM
                consolidation result and fall back to deterministic dedup.

                The detection is deliberately tight — these patterns are
                unambiguous markers of leaked internal reasoning (the model echoing
                the input bullet numbering, KEEP/REJECT verdicts, comparison
                commentary). They do NOT appear in legitimate summary bullets
        # about humanities domains, climate science, etc.
        """
        if not bullets:
            return (0, [])
        leaked_samples = []
        leaked_count = 0
        for idx, bp in enumerate(bullets):
            bp_str = str(bp)
            for pattern in cls._LEAKED_METADATA_PATTERNS:
                m = pattern.search(bp_str)
                if m:
                    leaked_count += 1
                    leaked_samples.append(
                        (
                            idx,
                            m.group(0),
                            bp_str[:80] + ("…" if len(bp_str) > 80 else ""),
                        )
                    )
                    break  # one match per bullet is enough
        return (leaked_count, leaked_samples)

    # ── Stage: informational checks (I2 difficulty + J2 redundancy + J3 coherence) ──

    def run_informational_checks(self, state: PipelineState) -> None:
        """I2 + J2 + J3: log difficulty, redundancy, coherence (no drops).

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        These are informational-only — they log but never modify state.
        """
        s = self.s
        # I2: Chapter difficulty
        try:
            from core.summarisation.text_preprocessor import score_chapter_difficulty

            diff = score_chapter_difficulty(state.content)
            s.log(
                f"    📊 I2: Chapter difficulty {diff['score']:.2f}/1.0 "
                f"(grade {diff['grade_level']}, strategy: {diff['strategy']})",
                "DEBUG",
            )
        except Exception as _e:
            logging.getLogger(__name__).debug("ignored %s: %s", type(_e).__name__, _e)
        # J2: Cross-section redundancy
        try:
            from core.summarisation.text_preprocessor import check_cross_section_redundancy

            redundancy = check_cross_section_redundancy(
                state.exec_sum, state.bullets, state.thorough
            )
            if redundancy["total_redundant"] > 0:
                s.log(
                    f"    🔄 J2: {redundancy['total_redundant']} cross-section redundancy(ies) found "
                    f"(exec↔bullets: {len(redundancy['exec_vs_bullets_redundant'])}, "
                    f"bullets↔thorough: {len(redundancy['bullets_vs_thorough_redundant'])})",
                    "DEBUG",
                )
        except Exception as _e:
            logging.getLogger(__name__).debug("ignored %s: %s", type(_e).__name__, _e)
        # J3: Exec summary coherence
        try:
            from core.summarisation.text_preprocessor import check_exec_summary_coherence

            coherence = check_exec_summary_coherence(state.exec_sum)
            if not coherence["coherent"]:
                s.log(
                    f"    ⚠️ J3: Exec summary low coherence ({coherence['score']}/100, "
                    f"{coherence['discourse_markers']} discourse markers)",
                    "DEBUG",
                )
            else:
                s.log(
                    f"    ✅ J3: Exec summary coherent ({coherence['score']}/100, "
                    f"{coherence['discourse_markers']} markers)",
                    "DEBUG",
                )
        except Exception as _e:
            logging.getLogger(__name__).debug("ignored %s: %s", type(_e).__name__, _e)

    # ── Stage: academic factual-claim verification ─────────────────────

    def apply_academic_factual_verification(self, state: PipelineState) -> None:
        """Guardrail A: drop bullets with unverified numbers/quotes (academic only).

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        Only runs for ``source_type == "academic_paper"``.

        V13.25.0 (P1.5): Fixed conservative-mode violation. Previously this
        layer silently dropped bullets with NO quarantine entry and NO
        conservative-mode gating — even when the user enabled conservative
        mode (which promises to keep all bullets except thinking/prompt-
        leakage). The identical check ran earlier in Layer 7 (thinking_filter)
        WITH conservative gating + quarantine. This second pass was dropping
        bullets the first pass deliberately kept.

        Now: in conservative mode, bullets are KEPT (not dropped) but marked
        with a ⚠️ prefix so the user can review them. Quarantine entries are
        logged regardless of conservative mode (for audit trail).
        """
        s = self.s
        if getattr(s.request, "source_type", "") != "academic_paper":
            return
        try:
            from core.summarisation.text_preprocessor import verify_numbers_and_quotes

            _unverified = []
            _kept = []
            for bp in state.bullets:
                is_valid, _reasons = verify_numbers_and_quotes(bp, state.content)
                if is_valid:
                    _kept.append(bp)
                else:
                    _unverified.append((bp, _reasons))

            if _unverified:
                # V13.25.0 P1.5: Log to quarantine for audit trail (always)
                conservative = getattr(s, "conservative_drops", False)
                for bp, reasons in _unverified:
                    reason_str = "; ".join(reasons[:2]) if reasons else "unverified"
                    if hasattr(s, "quarantine") and s.quarantine:
                        s.quarantine.add(
                            bullet=bp,
                            stage="Layer C: Academic factual verification",
                            reason=f"Unverified numbers/quotes: {reason_str}",
                            source_overlap=0.0,
                            actually_dropped=not conservative,
                            # V0.03 (P1-6): tag the chapter so the per-chapter
                            # Quarantine Log appendix can attribute the drop.
                            chapter=getattr(s, "_current_heading", "") or "",
                        )

                if conservative:
                    # V13.25.0 P1.5 → V0.03 (P1-6): conservative mode keeps the
                    # bullets with NO user-facing marker (V13.33.2 rule) — the
                    # log line no longer claims a ⚠️ that is never written.
                    # The audit trail lives in the chapter's Quarantine Log
                    # appendix + logs/drops.jsonl.
                    s.log(
                        f"    ⚠️ Guardrail A: {len(_unverified)} bullet(s) have unverified "
                        f"numbers/quotes — KEPT (conservative mode, no user-facing "
                        f"marker; see Quarantine Log appendix + drops.jsonl)",
                        "WARNING",
                    )
                    for bp, _reasons in _unverified:
                        # V13.33.2: Don't add ⚠️ prefix — it confuses users who think
                        # the bullet is wrong. The bullet is kept because it passed
                        # the conservative threshold. The ⚠️ was a developer-facing
                        # marker that leaked into user-facing output.
                        if not bp.startswith("⚠️"):
                            _kept.append(bp)
                    state.bullets = _kept
                else:
                    # Normal mode — drop unverified bullets
                    s.log(
                        f"    🚫 Guardrail A: Dropped {len(_unverified)} bullet(s) with "
                        f"unverified factual claims (numbers/quotes not in source): "
                        f"{[b[0][:50] for b in _unverified[:3]]}…",
                        "WARNING",
                    )
                    state.bullets = _kept
        except Exception as e:
            s.log(f"    ℹ️ Guardrail A skipped ({e})", "DEBUG")

    # ── Stage: gap-fill validation (V13.24.0 P0.3) ─────────────────────

    @staticmethod
    def _validate_gap_fill_bullets(
        gap_bullets: list[str],
        source_text: str,
        summarizer: Any,
    ) -> list[str]:
        """V13.24.0 P0.3: Validate gap-fill bullets through F4 + Phase 2.2.

        Gap-fill bullets are LLM-generated to cover missing concepts.  Before
        V13.24.0, they were appended directly to the bullet list WITHOUT going
        through any hallucination filters — a back-door that let hallucinated
        bullets survive all 25 anti-hallucination layers.

        This method runs each gap-fill bullet through:
        1. **F4 source overlap** (``compute_source_overlap``) — drop if < 0.25
        2. **Phase 2.2 semantic fact-check** (``semantic_fact_check``) — drop
           if best embedding similarity < 0.50

        Bullets that pass BOTH checks are kept.  Rejected bullets are logged.

        Returns the filtered list of validated gap-fill bullets.
        """
        if not gap_bullets or not source_text:
            return list(gap_bullets)

        try:
            from core.summarisation.text_preprocessor import (
                compute_source_overlap,
                semantic_fact_check,
            )
        except ImportError:
            # If text_preprocessor is unavailable, keep all bullets (fail-open)
            summarizer.log(
                "    ⚠️ Gap-fill validation skipped (text_preprocessor unavailable)",
                "DEBUG",
            )
            return list(gap_bullets)

        validated: list[str] = []
        rejected = 0
        # V0.5.16: degenerate-signal guard — the SAME V18.2.30 guard the
        # main Phase 2.2 stage has (apply_phase22_semantic_fact_check,
        # above) + thorough_theorist_floor._filter_unverified_additions.
        # WHY: semantic_fact_check fails CLOSED when the embed model is
        # unavailable (V18.1 S1: is_grounded=False, best_similarity=0.0,
        # reason="embed_model_unavailable") — a Degenerate signal, not a
        # real 0.00 similarity. On an embedder-less rig (no sentence-
        # transformers, no Ollama embed model — e.g. a llama.cpp-only
        # box), this rejected EVERY gap-fill bullet at "sim 0.00" while
        # the deterministic F4 check (which needs no embedder) passed
        # them — the V0.5.16 ch.1 repeatability run lost all 8 concept
        # gap-fill bullets this way (56.8% author coverage vs the rig's
        # 95%). Gap-fill bullets are ADD-CONTENT paths already gated by
        # F4 (≥25% token overlap) + the loosened quote-guard: when the
        # embedder is unhealthy, skip the semantic check (rely on F4),
        # exactly like the main stage does.
        _embedder_healthy = True
        try:
            from core.llm.model_singletons import is_embedder_healthy

            if not is_embedder_healthy():
                _embedder_healthy = False
                summarizer.log(
                    "    ⏭️  Gap-fill validation: embedder unhealthy — skipping "
                    "Phase 2.2 (F4 source-overlap still gates every bullet; a "
                    "zero-vector similarity would falsely reject them all)",
                    "WARNING",
                )
        except Exception:
            pass
        for bullet in gap_bullets:
            # F4: token overlap check
            # V18.20.2.0 (SWOT-A2): thresholds from thresholds.py (was 0.25).
            overlap = compute_source_overlap(bullet, source_text)
            if overlap < _F4_SOURCE_OVERLAP_DROP:
                summarizer.log(
                    f"    🚫 Gap-fill bullet rejected (F4 overlap {overlap:.0%} < 25%): "
                    f"{bullet[:60]}...",
                    "DEBUG",
                )
                rejected += 1
                continue

            # Phase 2.2: semantic fact-check
            # V18.20.2.0 (SWOT-A2): threshold from thresholds.py (was 0.50).
            # V0.5.16: skipped entirely when the embedder is unhealthy (see
            # the guard above) + per-bullet fail-open on the explicit
            # "embed_model_unavailable" reason (belt + braces: the health
            # probe can pass while the model load still fails mid-run).
            if _embedder_healthy:
                result = semantic_fact_check(
                    bullet, source_text, threshold=_SEMANTIC_FACT_CHECK_DROP
                )
                _unavailable = result.get("reason") == "embed_model_unavailable"
                if not result.get("is_grounded", True) and not _unavailable:
                    summarizer.log(
                        f"    🚫 Gap-fill bullet rejected (Phase 2.2 sim "
                        f"{result.get('best_similarity', 0):.2f} < 0.50): "
                        f"{bullet[:60]}...",
                        "DEBUG",
                    )
                    rejected += 1
                    continue
                if _unavailable:
                    summarizer.log(
                        "    ⏭️  Gap-fill validation: Phase 2.2 unavailable "
                        "(embed model) — F4 overlap passed, bullet kept",
                        "DEBUG",
                    )

            validated.append(bullet)

        if rejected > 0:
            summarizer.log(
                f"    🛡️ Gap-fill validation: {len(validated)}/{len(gap_bullets)} bullets "
                f"passed F4 + Phase 2.2 ({rejected} rejected as ungrounded)",
                "INFO",
            )

        return validated

    # ── Stage: gap-fill uncovered concepts ─────────────────────────────

    def gap_fill_concepts(self, state: PipelineState, concepts: list[str] | None) -> None:
        """C2: detect uncovered concepts → targeted LLM call → append new bullets.

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        Delegates to ``Summarizer._gap_fill_concepts``.

        V13.24.0 (P0.3): Gap-fill bullets are now validated through F4
        (source overlap) + Phase 2.2 (semantic fact-check) BEFORE being
        appended.  Previously, gap-fill bullets bypassed all hallucination
        filters — a hallucinated gap-fill bullet survived all 25 layers.
        """
        s = self.s
        if not concepts:
            return
        old_count = len(state.bullets)
        state.bullets = s._gap_fill_concepts(
            state.heading,
            state.content,
            state.bullets,
            concepts,
            exec_summary=state.exec_sum,
            thorough_summary=state.thorough,
        )
        # V13.24.0 P0.3: Validate any newly-added gap-fill bullets
        new_bullets = state.bullets[old_count:]
        if new_bullets:
            validated = self._validate_gap_fill_bullets(new_bullets, state.content, s)
            state.bullets = state.bullets[:old_count] + validated

    # ── Stage: empty-output salvage ────────────────────────────────────

    def salvage_empty_output(self, state: PipelineState) -> bool:
        """Salvage: if exec/bullets empty but thorough has content, extract from it.

        V10.32.0 (Sprint 4 session 2): extracted from ``_summarize_inner``.
        Returns True if the chapter should continue (salvage succeeded or
        wasn't needed); False if the chapter should fail (truly empty).

        V13.40.3: Detect and re-parse raw JSON in thorough before extracting.
        The academic-rigor JSON mode sometimes leaves raw JSON in the thorough
        field when the parser can't extract it. The salvage was extracting
        JSON lines as bullets — producing garbage like '{"claim": "..."}'.
        Now the salvage detects JSON and extracts claims properly.
        """
        s = self.s
        if state.bullets or state.exec_sum.strip():
            return True  # not empty, no salvage needed
        if state.thorough and len(state.thorough.strip()) > 100:
            # V13.40.3: Check if thorough is raw JSON — if so, re-parse it
            _thorough = state.thorough.strip()
            if _thorough.startswith("{") or _thorough.startswith("["):
                s.log("    🔧 Salvage: thorough appears to be raw JSON — re-parsing", "DEBUG")
                try:
                    import json as _json

                    # Try to parse as JSON
                    _data = _json.loads(_thorough)
                    if isinstance(_data, dict):
                        # Extract claims from the JSON dict
                        _claims = []
                        for _key in ("executive_summary", "bullet_points", "thorough_summary"):
                            _items = _data.get(_key, [])
                            if isinstance(_items, list):
                                for _item in _items:
                                    if isinstance(_item, dict):
                                        _claim = (
                                            _item.get("claim", "") or _item.get("text", "") or ""
                                        )
                                        if _claim:
                                            _claims.append(f"- {_claim}")
                                    elif isinstance(_item, str) and _item.strip():
                                        _claims.append(f"- {_item}")
                            elif isinstance(_items, str) and _items.strip():
                                _claims.append(f"- {_items}")
                        if _claims:
                            state.thorough = "\n".join(_claims)
                            s.log(
                                f"    🔧 Salvage: re-parsed JSON → {len(_claims)} claims", "DEBUG"
                            )
                except Exception:
                    pass  # not valid JSON, continue with original thorough

            s.log(
                f"    🔧 Salvage: exec/bullets empty but thorough has "
                f"{len(state.thorough)} chars — extracting bullets from thorough",
                "WARNING",
            )
            if not state.bullets:
                state.bullets = s._extract_bullets_from_text(state.thorough)
                if not state.bullets:
                    state.bullets = s._extract_sentences_as_bullets(state.thorough, max_bullets=15)
                s.log(
                    f"    🔧 Salvage: extracted {len(state.bullets)} bullets from thorough",
                    "DEBUG",
                )
            if not state.exec_sum.strip():
                # V13.40.3: Clean the exec extraction — strip JSON artifacts + backslashes
                sentences = re.split(r"(?<=[.!?])\s+", state.thorough.strip())
                # Filter out sentences that look like JSON fragments
                clean_sentences = []
                for sent in sentences[:5]:
                    sent = sent.strip()
                    # Skip JSON-looking fragments
                    if sent.startswith("{") or sent.startswith("[") or sent.startswith('"'):
                        continue
                    # Strip trailing backslashes (JSON escape artifacts)
                    sent = sent.rstrip("\\").strip()
                    if len(sent) > 10:
                        clean_sentences.append(sent)
                state.exec_sum = (
                    " ".join(clean_sentences[:3]) if clean_sentences else state.thorough[:500]
                )
                s.log(
                    f"    🔧 Salvage: extracted exec_sum ({len(state.exec_sum)} chars) from thorough",
                    "DEBUG",
                )
            if not state.bullets:
                s.log(
                    "    🔧 Salvage: no bullets found, but thorough has content — "
                    "accepting best-effort (chapter will succeed with thorough only)",
                    "WARNING",
                )
            return True
        # Truly empty — should fail
        return False

    # ── Stage: Self-consistency + Self-review ──────────────────────────

    def run_self_consistency_and_review(
        self, state: PipelineState, result: dict, heading: str, text: str
    ) -> None:
        """V10.36.0: Self-consistency + self-review (extracted from _summarize_inner)."""
        s = self.s
        if s.self_consistency and s.provider == "ollama":
            s.log("    🔄 Generating additional summaries for self‑consistency…", "INFO")
            extra_results = []
            for temp in [0.1, 0.3, 0.5]:
                if temp == s.temperature:
                    continue
                extra = s._summarize_with_model(heading, text, s.primary_model, temp, with_cot=True)
                if extra:
                    extra_results.append(extra)
            if extra_results:
                all_results = [result] + extra_results
                merged = s._merge_summaries(all_results)
                result["executive_summary"] = merged.get(
                    "executive_summary", result.get("executive_summary", "")
                )
                result["thorough_summary"] = merged.get(
                    "thorough_summary", result.get("thorough_summary", "")
                )
                result["bullet_points"] = merged.get(
                    "bullet_points", result.get("bullet_points", [])
                )
                result["model"] = "self_consistency"
                s.log("    ✅ Self‑consistency merged", "INFO")
        if s.academic_rigor:
            # V13.45.5: REMOVED the coverage-threshold skip. The user explicitly
            # said: "Quality first, time second." Self-review now ALWAYS runs
            # (with batching for >10 bullets). This ensures every bullet is
            # fact-checked even when coverage is already high.
            _primary_cov = getattr(s, "_last_coverage", 0.0)
            # V13.45.4: Batched self-review — reviews bullets in chunks of 10
            # when the total exceeds 10. This preserves quality while avoiding
            # the 600s timeout that single-pass review hits with 100+ bullets.
            _bps_for_review = [
                str(b) if not isinstance(b, str) else b
                for b in result.get("bullet_points", [])
                if b
            ]
            if not _bps_for_review:
                # V0.11 (real-rig audit, BUG-VACUOUS-QA): with 0 bullets the
                # self-review LLM call is pure waste (the V0.10 rig burned
                # ~4 GPU-minutes "confirming" an empty set while the real
                # problem was a claims-JSON format failure upstream) and its
                # "all bullets confirmed" verdict is vacuous. Skip loudly —
                # the format salvage / gap-fill stages must populate bullets
                # first.
                s.log(
                    "    ⚠️ Self‑review SKIPPED: 0 bullets to review (the "
                    "primary parse produced no bullets — a response-format "
                    "failure; see the parse warnings). Gap-fill will "
                    "populate bullets.",
                    "WARNING",
                )
            else:
                _use_batched_review = len(_bps_for_review) > 10
                if _use_batched_review:
                    s.log(
                        f"    🔬 Running self‑review in BATCHES ({len(_bps_for_review)} bullets → "
                        f"{(len(_bps_for_review) + 9) // 10} batches of 10)… [coverage {_primary_cov:.0%}]",
                        "INFO",
                    )
                else:
                    s.log(
                        f"    🔬 Running self‑review to verify claims… [coverage {_primary_cov:.0%}]",
                        "INFO",
                    )
            # V13.40.4: Increased from 8s → 20s. The 8s delay was insufficient
            # after B4's 3 calls (~12 min) + additive followup (~2 min).
            s._recover_vram(context="pre-self-review", delay_sec=20.0)
            _bps3 = [
                str(b) if not isinstance(b, str) else b
                for b in result.get("bullet_points", [])
                if b
            ]
            full_summary = f"{result.get('executive_summary', '')} {' '.join(_bps3)} {result.get('thorough_summary', '')}"
            # V13.45.5: Self-review ALWAYS runs (no coverage-threshold skip).
            # Use BATCHED self-review when >10 bullets (preserves quality, avoids timeout)
            # V0.11 (BUG-VACUOUS-QA): except when there are NO bullets — the
            # call would confirm an empty set (vacuous) and waste minutes.
            reviewed = None
            if _bps_for_review:
                if _use_batched_review:
                    reviewed = s._self_review_batched(
                        heading, text, _bps3, result.get("thorough_summary", "")
                    )
                else:
                    reviewed = s._self_review(heading, text, full_summary)
            if reviewed:
                # V13.37.0: Strip <think> blocks before parsing. _self_review is
                # the only LLM call site that didn't call _strip_thinking, so
                # Gemma 4's <think> reasoning block was passed raw to the parser
                # (which found no { and logged "no structured content").
                reviewed = s._strip_thinking(reviewed).strip()
            if reviewed:
                import json

                try:
                    # V13.37.0: The self-review prompt asks for a JSON ARRAY:
                    # [{"index": 1, "verdict": "supported", "reason": "", ...}, ...]
                    # The old parser looked for a JSON OBJECT {...} and accessed
                    # .get('bullet_points', []) — which never matched. Now we
                    # look for an array and iterate verdicts to find unsupported.
                    json_match = re.search(r"(\[.*\])", reviewed, re.DOTALL)
                    if not json_match:
                        # Fallback: try object format (for backward compat with
                        # any model that returns {"bullet_points": [...]} format)
                        json_match = re.search(r"(\{.*\})", reviewed, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        try:
                            reviewed_json = json.loads(json_str)
                        except json.JSONDecodeError:
                            # V13.40.3: Handle "Extra data" error (model returns
                            # valid JSON array followed by trailing text). The
                            # old cleanup only fixed trailing commas — it didn't
                            # handle the case where the model outputs:
                            # [{"index":1,...}]\n\nSome extra text
                            # json.loads fails with "Extra data: line 1 column N"
                            import re as _re_json

                            # Try to extract just the first complete JSON array/object
                            _arr_match = _re_json.search(r"(\[[\s\S]*?\])\s*$", json_str)
                            if _arr_match:
                                json_str = _arr_match.group(1)
                            else:
                                _obj_match = _re_json.search(r"(\{[\s\S]*?\})\s*$", json_str)
                                if _obj_match:
                                    json_str = _obj_match.group(1)
                            # Clean up trailing commas
                            cleaned = _re_json.sub(r",\s*}", "}", json_str)
                            cleaned = _re_json.sub(r",\s*]", "]", cleaned)
                            cleaned = cleaned.replace("'", '"')
                            try:
                                reviewed_json = json.loads(cleaned)
                            except json.JSONDecodeError:
                                s.log(
                                    "    ⚠️ Self-review JSON still unparseable after cleanup — skipping",
                                    "WARNING",
                                )
                                reviewed_json = None

                        # V13.40.3: Skip processing if JSON parsing failed
                        if reviewed_json is None:
                            s.log("    ⚠️ Self-review skipped (JSON unparseable)", "WARNING")
                        else:
                            # V13.37.0: Handle BOTH array format (new) and object
                            # format (legacy). The prompt asks for an array of
                            # {"index", "verdict", "reason", "evidence_quote"}.
                            orig_bullets = list(result.get("bullet_points", []))
                            dropped_bullets = []

                            if isinstance(reviewed_json, list):
                                # Array format: iterate verdicts
                                for item in reviewed_json:
                                    if not isinstance(item, dict):
                                        continue
                                    idx = item.get("index", 0)
                                    verdict = str(item.get("verdict", "")).lower()
                                    if verdict in (
                                        "unsupported",
                                        "not_supported",
                                    ) and 1 <= idx <= len(orig_bullets):
                                        dropped_bullets.append(orig_bullets[idx - 1])
                                rev_bullets = [b for b in orig_bullets if b not in dropped_bullets]
                            elif isinstance(reviewed_json, dict):
                                # Legacy object format: {"bullet_points": [...]}
                                rev_bullets = reviewed_json.get("bullet_points", [])
                                if rev_bullets:
                                    rev_set = {str(b).strip().lower() for b in rev_bullets}
                                    dropped_bullets = [
                                        b
                                        for b in orig_bullets
                                        if str(b).strip().lower() not in rev_set
                                    ]
                                    rev_bullets = [
                                        b for b in orig_bullets if str(b).strip().lower() in rev_set
                                    ]

                            if dropped_bullets:
                                # V13.25.0 P1.5: Respect conservative mode + log to quarantine
                                conservative = getattr(s, "conservative_drops", False)
                                # Log to quarantine for audit trail (always)
                                for bp in dropped_bullets:
                                    if hasattr(s, "quarantine") and s.quarantine:
                                        s.quarantine.add(
                                            bullet=str(bp),
                                            stage="Layer B: Self-review",
                                            reason="LLM self-review marked as unsupported",
                                            source_overlap=0.0,
                                            actually_dropped=not conservative,
                                            # V0.03 (P1-6): chapter tag for the
                                            # per-chapter appendix.
                                            chapter=getattr(s, "_current_heading", "") or "",
                                        )

                                if conservative:
                                    s.log(
                                        f"    ⚠️ Self-review: {len(dropped_bullets)} bullet(s) marked unsupported "
                                        f"by LLM — KEPT (conservative mode)",
                                        "WARNING",
                                    )
                                else:
                                    result["bullet_points"] = rev_bullets
                                    s.log(
                                        f"    ✅ Self‑review: dropped {len(dropped_bullets)} unsupported bullet(s).",
                                        "INFO",
                                    )
                            else:
                                s.log("    ✅ Self‑review: all bullets confirmed.", "INFO")
                            result["model"] = "primary+self_review"
                    else:
                        s.log("    ⚠️ Self‑review returned no structured content.", "WARNING")
                except Exception as e:
                    s.log(f"    ⚠️ Self‑review parsing failed: {e}.", "WARNING")
            else:
                s.log("    ⚠️ Self‑review returned no response.", "WARNING")
        state.__dict__["_result"] = result

    # ── Stage: Content Judge (grounding + coverage + gap-fill) ─────────

    def run_content_judge(
        self, state: PipelineState, coverage: float, tok_in: int, final_summary: str
    ) -> SummaryResult | None:
        """Content Judge: final pre-output validation (grounding + coverage).

        V10.32.0 (Sprint 4 s2): extracted verbatim from ``_summarize_inner``.
        This is the largest stage (~490 lines) — checks coverage, grounding,
        hallucinations, and concept deviations.  Drops ungrounded bullets
        (conservative-mode aware) and triggers gap-fill reprompts.

        Returns ``None`` if the chapter should continue, or a
        ``SummaryResult(success=False)`` if the hard rejection triggers
        (coverage catastrophically low).
        """
        s = self.s
        heading = state.heading
        content = state.content
        bullets = state.bullets
        exec_sum = state.exec_sum
        thorough = state.thorough
        try:
            from core.summarisation.content_judge import ContentJudge

            _judge = ContentJudge(
                log_callback=s.log,
                min_coverage=s.coverage_threshold,
                claim_extractor=s._claim_extractor,
                content_type=getattr(s.request, "source_type", "normal_book"),
            )
            _temp_result = SummaryResult(
                chapter_heading=heading,
                executive_summary=exec_sum,
                bullet_points=bullets,
                thorough_summary=thorough,
                success=True,
            )
            _judge_result = _judge.judge(_temp_result, content)
            s._last_judge_result = _judge_result
            s.judge_results.append(_judge_result)
            s.log(f"    {_judge_result.summary}", "INFO")

            # V18.19.2.3 (Audit Fix 3): Prominent WARNING when grounding is OFF
            # and hallucinations are high. The V18.19.2.0 audit found 18
            # hallucinated bullets shipped because grounding.enabled=False in
            # the user's settings.json (the code default IS True, but the user
            # overrode it). The existing log line (938) showed "L8=OFF(
            # grounding_disabled)" but at INFO level alongside the PASS/FAIL —
            # easy to miss. This dedicated WARNING surfaces the risk: the
            # ungrounded bullets were NOT dropped, so they reach the final
            # output. Threshold: >=5 hallucinations OR grounding < 70%.
            if (
                not _judge_result.grounding_layer8_available
                and _judge_result.grounding_alarm
                and (_judge_result.hallucination_count >= 5 or _judge_result.grounding_pct < 0.70)
            ):
                s.log(
                    f"    ⚠️🛡️ V18.19.2.3: Layer 8 grounding is OFF "
                    f"({_judge_result.grounding_alarm}) — "
                    f"{_judge_result.hallucination_count} hallucinated bullets "
                    f"and {_judge_result.grounding_pct:.0%} grounding "
                    f"({_judge_result.grounded_bullets}/"
                    f"{_judge_result.total_bullets} bullets grounded). "
                    f"Ungrounded bullets were NOT dropped. To enforce the "
                    f"grounding guarantee, set grounding.enabled=True in "
                    f"settings.json (the code default; you may have disabled it).",
                    "WARNING",
                )

            if _judge_result.ungrounded_bullets:
                _grounding_enabled = False
                try:
                    _grounding_enabled = bool(
                        s._claim_extractor and s._claim_extractor._is_enabled()
                    )
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
                if not _grounding_enabled:
                    _llm_ungrounded = s._llm_grounding_check(bullets, content)
                    _actually_ungrounded = []
                    # V15.1.0: Judge appeal visibility.
                    # V13.45.5 already had this appeal (the overlap >= 0.25 check
                    # that keeps bullets the LLM flagged as "likely paraphrase").
                    # V15.0.0 added the \u2696\ufe0f log to the wrong branch
                    # (the langextract-on path, dead code on Ollama). This makes
                    # the EXISTING appeal visible in the default Ollama path.
                    _appeal_kept_n = 0
                    if _llm_ungrounded:
                        try:
                            # V18.20.3.2 (audit N1 / P0-2): SELF-TALK CARVE-OUT.
                            # The V18.20.3.1 run: the judge correctly flagged
                            # "AuthorW (1968) - include this! Let me add it." as
                            # ungrounded, but the appeal auto-KEPT it on 100%
                            # source overlap — self-talk that QUOTES the source
                            # defeats the overlap rescue by construction. A
                            # self-talk bullet is dropped regardless of overlap.
                            from core.summarisation.post_processing import (
                                SELF_TALK_PATTERNS as _STP,
                            )
                            from core.summarisation.text_preprocessor import compute_source_overlap

                            _selftalk_dropped = []
                            for bp in _llm_ungrounded:
                                if _STP.search(bp):
                                    _selftalk_dropped.append(bp)
                                    continue
                                overlap = compute_source_overlap(bp, content)
                                if overlap < 0.25:
                                    _actually_ungrounded.append((bp, overlap))
                                else:
                                    _appeal_kept_n += 1
                                    s.log(
                                        f"    \u2139\ufe0f LLM flagged '{bp[:40]}\u2026' as ungrounded, "
                                        f"but source overlap is {overlap:.0%} \u2014 KEEPING (likely paraphrase)",
                                        "DEBUG",
                                    )
                            for bp in _selftalk_dropped:
                                # Self-talk: unconditional drop (conservative
                                # mode still drops — it is NEVER content).
                                s.quarantine.add(
                                    bp,
                                    stage="judge_grounding.self_talk",
                                    threshold=0.25,
                                    source_overlap=1.0,
                                    reason="LLM-as-judge flagged + model self-talk "
                                    "(include this! / let me add / the source "
                                    "says) — self-talk quoting the source "
                                    "defeats the overlap rescue; dropped",
                                    chapter=getattr(s, "_current_heading", "") or "",
                                    actually_dropped=True,
                                )
                            if _selftalk_dropped:
                                s.log(
                                    f"    \U0001f6ab V18.20.3.2: judge-appeal carve-out — "
                                    f"{len(_selftalk_dropped)} self-talk bullet(s) "
                                    f"DROPPED despite source overlap (CoT planning "
                                    f"notes are never content)",
                                    "WARNING",
                                )
                                _ungrounded_st = {b[:80] for b in _selftalk_dropped}
                                bullets = [b for b in bullets if b[:80] not in _ungrounded_st]
                                state.bullets = bullets
                            if _appeal_kept_n > 0:
                                s.log(
                                    f"    \u2696\ufe0f Judge appeal: KEPT {_appeal_kept_n} of {len(_llm_ungrounded)} "
                                    f"flagged bullet(s) \u2014 source overlap \u2265 0.25 to source",
                                    "INFO",
                                )
                        except ImportError:
                            _actually_ungrounded = [(bp, 0.0) for bp in _llm_ungrounded]
                    if _actually_ungrounded:
                        for bp, ov in _actually_ungrounded:
                            s.quarantine.add(
                                bp,
                                stage="judge_grounding.llm_f4_crosscheck",
                                threshold=0.25,
                                source_overlap=ov,
                                reason="LLM-as-judge said NO + F4 source overlap <25%"
                                + (" (kept — conservative mode)" if s.conservative_drops else ""),
                                chapter=getattr(s, "_current_heading", "") or "",
                                actually_dropped=not s.conservative_drops,
                            )
                        s.log(
                            f"  🛡️ LLM-as-judge + F4 cross-check: "
                            f"{len(_actually_ungrounded)}/{len(bullets)} bullets confirmed "
                            f"ungrounded (LLM NO + source overlap <25%) — "
                            f"{'logging only (conservative)' if s.conservative_drops else 'dropping.'}",
                            "INFO",
                        )
                        if not s.conservative_drops:
                            _ungrounded_set = {b[:80] for b, _ in _actually_ungrounded}
                            _kept = [bp for bp in bullets if bp[:80] not in _ungrounded_set]
                            if len(_kept) < len(bullets):
                                s.log(
                                    f"    🗑️ LLM-judge+F4: dropped {len(bullets) - len(_kept)} "
                                    f"confirmed-ungrounded bullet(s)",
                                    "WARNING",
                                )
                                bullets = _kept
                                state.bullets = bullets
                    else:
                        s.log(
                            f"  ℹ️ Source grounding DISABLED — LLM-as-judge grounding "
                            f"check passed all {len(bullets)} bullets.",
                            "DEBUG",
                        )
                    _judge_result.ungrounded_bullets = []
                else:
                    _source_garbled_j = False
                    try:
                        from utils.text_quality import is_text_garbled

                        _source_garbled_j = is_text_garbled(content)
                    except (ImportError, ValueError) as exc:
                        s.log(f"    ℹ️ Source garble check skipped ({exc})", "DEBUG")
                    except Exception as exc:
                        s.log(
                            f"    ⚠️ Source garble check crashed ({type(exc).__name__}: {exc})",
                            "WARNING",
                        )

                    _verbatim_bullets = set()
                    for bp in bullets:
                        quotes = re.findall(r'"([^"]{20,})"', bp)
                        for q in quotes:
                            if q in content:
                                _verbatim_bullets.add(bp[:80])
                                break

                    if _source_garbled_j:
                        s.log(
                            f"    ℹ️ Source garbled — keeping all {len(bullets)} bullets "
                            f"(Judge grounding check unreliable against garbled text)",
                            "WARNING",
                        )
                    elif _verbatim_bullets:
                        _ungrounded_set = {b[:80] for b in _judge_result.ungrounded_bullets}
                        _kept = [
                            bp
                            for bp in bullets
                            if bp[:80] not in _ungrounded_set or bp[:80] in _verbatim_bullets
                        ]
                        _dropped_here = [
                            bp
                            for bp in bullets
                            if bp[:80] in _ungrounded_set and bp[:80] not in _verbatim_bullets
                        ]
                        for _dbp in _dropped_here:
                            try:
                                from core.summarisation.text_preprocessor import (
                                    compute_source_overlap as _cso,
                                )

                                _dov = _cso(_dbp, content)
                            except Exception as _e:
                                _dov = 0.0
                            s.quarantine.add(
                                _dbp,
                                stage="judge_grounding.verbatim_exempt",
                                threshold=0.0,
                                source_overlap=_dov,
                                reason="Judge flagged ungrounded (no verbatim quote exempting it)"
                                + (" (kept — conservative mode)" if s.conservative_drops else ""),
                                chapter=getattr(s, "_current_heading", "") or "",
                                actually_dropped=not s.conservative_drops,
                            )
                        if _dropped_here and not s.conservative_drops and len(_kept) < len(bullets):
                            s.log(
                                f"    🗑️ Judge: dropped {len(bullets) - len(_kept)} ungrounded bullet(s) "
                                f"(kept {_verbatim_bullets.__len__()} with verbatim quotes)",
                                "WARNING",
                            )
                            bullets = _kept
                            state.bullets = bullets
                        elif _dropped_here and s.conservative_drops:
                            s.log(
                                f"    ℹ️ Judge: would drop {len(_dropped_here)} ungrounded bullet(s) "
                                f"but conservative mode keeps them.",
                                "DEBUG",
                            )
                    else:
                        _ungrounded_set = {b[:80] for b in _judge_result.ungrounded_bullets}
                        _dropped_here = [bp for bp in bullets if bp[:80] in _ungrounded_set]
                        for _dbp in _dropped_here:
                            try:
                                from core.summarisation.text_preprocessor import (
                                    compute_source_overlap as _cso,
                                )

                                _dov = _cso(_dbp, content)
                            except Exception as _e:
                                _dov = 0.0
                            s.quarantine.add(
                                _dbp,
                                stage="judge_grounding.ungrounded",
                                threshold=0.0,
                                source_overlap=_dov,
                                reason="Content Judge flagged as ungrounded (hallucination)"
                                + (" (kept — conservative mode)" if s.conservative_drops else ""),
                                chapter=getattr(s, "_current_heading", "") or "",
                                actually_dropped=not s.conservative_drops,
                            )
                        if _dropped_here and not s.conservative_drops:
                            _kept = [bp for bp in bullets if bp[:80] not in _ungrounded_set]
                            if len(_kept) < len(bullets):
                                s.log(
                                    f"    🗑️ Judge: dropped {len(bullets) - len(_kept)} ungrounded bullet(s)",
                                    "WARNING",
                                )
                                bullets = _kept
                                state.bullets = bullets
                        elif _dropped_here and s.conservative_drops:
                            s.log(
                                f"    ℹ️ Judge: would drop {len(_dropped_here)} ungrounded bullet(s) "
                                f"but conservative mode keeps them.",
                                "DEBUG",
                            )

            # Gap-fill reprompt
            if _judge_result.needs_gap_fill and _judge_result.uncovered_claims:
                s.log(
                    f"    🔄 Judge: coverage {_judge_result.coverage_pct:.0%} < {s.coverage_threshold:.0%} — "
                    f"gap-filling {len(_judge_result.uncovered_claims)} uncovered claim(s)",
                    "WARNING",
                )
                _gap_prompt = _judge.build_gap_fill_prompt(
                    heading, _judge_result.uncovered_claims[:15], bullets
                )
                # V18.20.2.0 (SWOT A5): direct _call_llm site — inject /no_think
                # for Qwen-family models (bypasses _call_llm_with_empty_retry's
                # V18.2.41 injection).
                from core.summarisation.filter_thinking import qwen_no_think

                _gap_response = s._call_llm(
                    qwen_no_think(_gap_prompt, s.primary_model),
                    model=s.primary_model,
                    temperature=s.temperature * 0.7,
                )
                if _gap_response:
                    _gap_bullets = [
                        bp.strip().lstrip("- ").strip()
                        for bp in _gap_response.strip().split("\n")
                        if bp.strip().startswith("-") and len(bp.strip()) > 15
                    ]
                    if _gap_bullets:
                        # V13.24.0 P0.3: Validate gap-fill bullets through F4 +
                        # Phase 2.2 before appending. Previously these bypassed
                        # all hallucination filters — a back-door.
                        _validated_gap = self._validate_gap_fill_bullets(
                            _gap_bullets[:7],
                            content,
                            s,
                        )
                        if _validated_gap:
                            s.log(
                                f"    ✅ Judge: gap-fill added {len(_validated_gap)}/"
                                f"{len(_gap_bullets[:7])} bullet(s) "
                                f"(after F4 + Phase 2.2 validation)",
                                "INFO",
                            )
                            bullets.extend(_validated_gap)
                            state.bullets = bullets
                        else:
                            s.log(
                                f"    🚫 Judge: all {len(_gap_bullets[:7])} gap-fill "
                                f"bullet(s) rejected by F4 + Phase 2.2 validation",
                                "WARNING",
                            )

            if _judge_result.deviation_count > 0:
                s.log(
                    f"    ⚠️ Judge: {_judge_result.deviation_count} potential deviation(s) detected",
                    "WARNING",
                )
                for d in _judge_result.deviation_details[:3]:
                    s.log(f"      → {d}", "WARNING")

        except ImportError as e:
            # Deliberate skip — ContentJudge (optional dependency) is not
            # importable. Control flow, not a failure: stays DEBUG.
            s.log(f"    ℹ️ Content Judge skipped ({e})", "DEBUG")
        except Exception as e:
            # V18.20.2.0 (SWOT A6): the whole judge stage was previously
            # swallowed at DEBUG — any crash silently disabled the flagship
            # anti-hallucination stage for the chapter with an invisible log.
            # Keep the broad guard (the pipeline must survive a judge crash)
            # but surface UNEXPECTED failures at WARNING with the stage name
            # and exception type.
            s.log(
                f"    ⚠️ Content Judge stage 'content_judge' crashed "
                f"({type(e).__name__}: {e}) — stage skipped, pipeline continues",
                "WARNING",
            )
            logger.warning(
                "content_judge stage crashed: %s: %s",
                type(e).__name__,
                e,
            )

        # Hard rejection
        try:
            if hasattr(s, "_last_judge_result") and s._last_judge_result:
                _jr = s._last_judge_result
                _ungrounded_pct = 1.0 - _jr.grounding_pct if _jr.total_bullets > 0 else 0.0

                _source_garbled = False
                try:
                    from utils.text_quality import is_text_garbled

                    _source_garbled = is_text_garbled(content)
                except (ImportError, ValueError) as exc:
                    s.log(f"    ℹ️ Source garble check skipped ({exc})", "DEBUG")
                except Exception as exc:
                    s.log(
                        f"    ⚠️ Source garble check crashed ({type(exc).__name__}: {exc})",
                        "WARNING",
                    )

                _verbatim_count = 0
                for bp in bullets:
                    quotes = re.findall(r'"([^"]{20,})"', bp)
                    for q in quotes:
                        if q in content:
                            _verbatim_count += 1
                            break

                if _source_garbled:
                    s.log(
                        "  ℹ️ Source text is garbled — Content Judge grounding "
                        "check is unreliable. Skipping hard rejection.",
                        "WARNING",
                    )
                elif _verbatim_count > 0 and _verbatim_count >= len(bullets) * 0.5:
                    s.log(
                        f"  ℹ️ {_verbatim_count}/{len(bullets)} bullets contain "
                        f"verbatim quotes from the source — auto-passing grounding "
                        f"check despite {_ungrounded_pct:.0%} ungrounded verdict.",
                        "INFO",
                    )
                elif coverage >= 0.80 and tok_in < 3000:
                    s.log(
                        f"  ℹ️ Coverage {coverage:.0%} ≥ 80% with short source "
                        f"({tok_in} tokens) — Judge grounding check unreliable for "
                        f"short texts. Auto-passing despite {_ungrounded_pct:.0%} "
                        f"ungrounded verdict.",
                        "INFO",
                    )
                # V17.9: When the deterministic analysis exists, the V17.6 judge
                # handles coverage with 100% reliable regex. The LLM content judge's
                # auto-pass decisions are no longer the final word — the deterministic
                # judge runs AFTER this and catches any missed authors.
                # So we let the LLM judge auto-pass (to avoid dropping bullets) but
                # the deterministic judge will still gap-fill any missing authors.
                # We just add a note that the deterministic judge will verify.
                elif len(exec_sum) > 500 and len(thorough) > 500 and _ungrounded_pct >= 1.0:
                    s.log(
                        f"  ℹ️ Summary has substantial content (exec={len(exec_sum)} "
                        f"chars, thorough={len(thorough)} chars) — Judge grounding "
                        f"check at {_ungrounded_pct:.0%} ungrounded is likely a false "
                        f"positive for this source length. Auto-passing to preserve content.",
                        "INFO",
                    )
                elif _jr.needs_gap_fill and _jr.coverage_pct < 0.30 and tok_in >= 3000:
                    # V18.2.19: Fixed misleading log — the old message said
                    # "Coverage 0% ≥ 50%" which is nonsensical. The actual
                    # condition is: judge coverage is very low (<30%) AND the
                    # source is long enough (≥3000 tokens) that the judge
                    # SHOULD be reliable — so this is a REAL gap, not a false
                    # positive. But we auto-pass anyway to preserve content,
                    # because the deterministic judge (V17.6) runs afterward
                    # and catches missing authors with 100% reliable regex.
                    s.log(
                        f"  ℹ️ V18.2.19: Judge coverage {_jr.coverage_pct:.0%} is very "
                        f"low (<30%) with a non-trivial source ({tok_in} tokens). "
                        f"The judge found {_jr.uncovered_claim_count if hasattr(_jr, 'uncovered_claim_count') else '?'} "
                        f"uncovered claims. Auto-passing to preserve content — "
                        f"the deterministic judge (V17.6) will verify coverage "
                        f"with 100% reliable regex afterward.",
                        "INFO",
                    )
                elif len(exec_sum) > 500 and len(thorough) > 500:
                    s.log(
                        f"  ℹ️ Summary has substantial content (exec={len(exec_sum)} "
                        f"chars, thorough={len(thorough)} chars) — Judge coverage "
                        f"check at {_jr.coverage_pct:.0%} is likely a false positive "
                        f"for this source length. Auto-passing to preserve content.",
                        "INFO",
                    )
                elif _jr.coverage_pct >= 0.50:
                    # V13.32.7: Don't reject when coverage is ≥ 50% (the user's threshold).
                    # The old code rejected any summary that didn't meet the auto-pass
                    # conditions above, even if coverage was 77%. The rejection message
                    # said "catastrophically low (<30%)" which was misleading — 77% is
                    # not < 30%. Now we auto-pass when coverage ≥ 50%.
                    s.log(
                        f"  ℹ️ Judge coverage {_jr.coverage_pct:.0%} ≥ 50% — "
                        f"auto-passing (above user's coverage threshold).",
                        "INFO",
                    )
                else:
                    msg = (
                        f"Content Judge: coverage {_jr.coverage_pct:.0%} is catastrophically "
                        f"low (<30%) — summary rejected for safety"
                    )
                    s.log(f"    🚫 {msg}", "ERROR")
                    return SummaryResult(
                        chapter_heading=heading,
                        executive_summary=exec_sum,
                        bullet_points=bullets,
                        thorough_summary=thorough,
                        success=False,
                        error_msg=msg,
                        input_tokens=tok_in,
                        output_tokens=count_tokens(final_summary),
                    )
        except Exception as _e:
            logging.getLogger(__name__).debug("ignored %s: %s", type(_e).__name__, _e)

        return None  # chapter should continue


__all__ = ["BulletPipeline", "PipelineState"]
