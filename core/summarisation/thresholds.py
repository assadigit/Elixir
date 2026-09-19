"""V13.27.0 (P2.1): Centralized anti-hallucination thresholds.

Before V13.27.0, the codebase had 5 different "grounding" thresholds
scattered across 5 files with no principled reason for the divergence:

  F4 source overlap:      0.25  (token overlap)      bullet_pipeline.py
  Phase 2.2 semantic:     0.50  (embedding cosine)   bullet_pipeline.py
  Content Judge Q2:       0.50  (embedding cosine)   content_judge.py
  Packets validation:     0.42  (embedding cosine)   packets.py
  Recovery pass:          0.30  (token overlap)      quarantine.py

This module is the SINGLE SOURCE OF TRUTH for these thresholds. Each is
documented with its rationale. Call sites import from here instead of
hardcoding.

Thresholds are organized into 2 tiers:

  ── Token overlap (fast, cheap, deterministic) ──
  F4_SOURCE_OVERLAP_DROP       0.25  — bullets below this are dropped (F4)
  F4_SOURCE_OVERLAP_RECOVER    0.30  — bullets above this can be resurrected
  VERIFY_BULLETS_MARK          0.50  — bullets below this are marked ⚠️ (Layer A)

  ── Embedding cosine (slow, accurate, semantic) ──
  SEMANTIC_FACT_CHECK_DROP     0.50  — Phase 2.2 + Content Judge Q2 drop threshold
  PACKETS_VALIDATION_TRACE     0.42  — packets validation sentence-trace threshold

The asymmetry between F4 drop (0.25) and recovery (0.30) is intentional:
bullets in [0.25, 0.30] are dropped by F4 but NOT resurrected by recovery
(because they're borderline — better to drop than risk a hallucination).

The packets validation threshold (0.42) is lower than Phase 2.2/Judge (0.50)
because packet synthesis produces multi-sentence paragraphs where the
closing framing sentence synthesizes across all bullets — it won't trace
to any single bullet above 0.50, but 0.42 catches real hallucinations.
(See V13.22.0 CHANGELOG for the full rationale.)
"""

from __future__ import annotations

# V18.1 (audit O1): threshold scale factor. Read from settings.embedding.threshold_scale.
# When the embedder model changes, the similarity distribution shifts. This scale
# multiplies all embedding-cosine thresholds so users can adjust without editing code.
# Default 1.0 = use the raw values below. Callers should use get_scaled_threshold()
# instead of reading the constants directly.
_THRESHOLD_SCALE: float = 1.0


def _get_threshold_scale() -> float:
    """Read the threshold scale from settings (cached after first read).

    V18.2.7: Auto-calibrates based on the embedder model. Different embedders
    produce different similarity distributions — the 0.50 threshold was
    calibrated for MiniLM. BGE models produce lower cosine similarities, so
    the threshold needs to be lowered to avoid false drops.

    Auto-calibration map:
      - all-MiniLM-L6-v2:   1.00 (baseline — thresholds as-is)
      - BAAI/bge-small:     0.85 (lower — bge produces lower sims)
      - BAAI/bge-base:      0.85 (same family)
      - BAAI/bge-large:     0.85
      - Qwen3-Embedding:    0.80 (even lower — different training)
      - nomic-embed:        0.85
      - intfloat/e5:        0.85
      - paraphrase-multilingual: 0.90

    If the user has manually set ``embedding.threshold_scale`` to something
    other than 1.0, that manual value is respected (auto-calibration only
    fires when threshold_scale is at the default 1.0).
    """
    global _THRESHOLD_SCALE
    if _THRESHOLD_SCALE != 1.0:
        return _THRESHOLD_SCALE
    try:
        from utils.settings import Settings

        _s = Settings()
        _manual_scale = float(_s.get("embedding.threshold_scale", 1.0))
        _embed_model = str(_s.get("embedding.model", "all-MiniLM-L6-v2"))

        # V18.2.7: If user manually set threshold_scale != 1.0, respect it
        if _manual_scale != 1.0:
            _THRESHOLD_SCALE = _manual_scale
            return _THRESHOLD_SCALE

        # Auto-calibrate based on embedder model
        _embed_lower = _embed_model.lower()
        if "minilm" in _embed_lower:
            _auto_scale = 1.0  # baseline — thresholds calibrated for MiniLM
        elif "bge-" in _embed_lower or "bge_" in _embed_lower:
            _auto_scale = 0.85  # bge produces lower cosine sims
        elif "qwen" in _embed_lower and "embed" in _embed_lower:
            _auto_scale = 0.80  # Qwen embeddings — even lower
        elif "nomic" in _embed_lower or "e5" in _embed_lower or "multilingual-e5" in _embed_lower:
            _auto_scale = 0.85
        elif "paraphrase" in _embed_lower:
            _auto_scale = 0.90
        else:
            _auto_scale = 1.0  # unknown model — use baseline

        _THRESHOLD_SCALE = _auto_scale
        if _auto_scale != 1.0:
            import logging as _logging

            _logging.getLogger(__name__).info(
                "V18.2.7: Auto-calibrated threshold_scale=%.2f for embedder '%s' "
                "(drop threshold: %.2f → %.2f)",
                _auto_scale,
                _embed_model,
                SEMANTIC_FACT_CHECK_DROP,
                SEMANTIC_FACT_CHECK_DROP * _auto_scale,
            )
    except Exception:
        pass
    return _THRESHOLD_SCALE


def scaled_threshold(base: float) -> float:
    """Apply the threshold_scale to a base threshold value."""
    scale = _get_threshold_scale()
    return min(0.99, max(0.1, base * scale))


# ── Token overlap thresholds (rapidfuzz / content-word overlap) ─────────────

F4_SOURCE_OVERLAP_DROP = 0.25
"""F4 source overlap drop threshold. Bullets with content-word overlap below
this are dropped as ungrounded. Used in bullet_pipeline.apply_f4_source_overlap."""

F4_SOURCE_OVERLAP_RECOVER = 0.30
"""Recovery pass resurrection threshold. Bullets in quarantine with source
overlap above this can be resurrected. Higher than F4_DROP so borderline
bullets in [0.25, 0.30] stay dropped. Used in quarantine.recover."""

VERIFY_BULLETS_MARK = 0.50
"""Layer A (_verify_bullets) mark threshold. Bullets with rapidfuzz
partial_ratio below this are marked ⚠️ Unverified (but NOT dropped — the
mark is for user visibility + quarantine logging). Used in summarizer._verify_bullets."""

# ── Embedding cosine thresholds (sentence-transformers all-MiniLM-L6-v2) ────

SEMANTIC_FACT_CHECK_DROP = 0.50
"""Phase 2.2 + Content Judge Q2 drop threshold. Bullets whose best embedding
cosine similarity to any source sentence is below this are dropped as
ungrounded. Used in bullet_pipeline.apply_phase22_semantic_fact_check and
content_judge.ContentJudge.judge."""

PACKETS_VALIDATION_TRACE = 0.42
"""Packets validation sentence-trace threshold. Each sentence in a synthesized
packet paragraph must have embedding similarity >= this to at least one source
bullet. Lower than SEMANTIC_FACT_CHECK_DROP because packet synthesis produces
closing framing sentences that synthesize across bullets. Used in
packets._validate_packet."""

# ── Dedup thresholds (for reference — defined in dedup_service.py) ──────────
# These are kept in dedup_service.py because they're tightly coupled to the
# DedupService class. Listed here for documentation:
#   WITHIN_CHAPTER_THRESHOLD  = 75   (rapidfuzz token_set_ratio)
#   CROSS_CHAPTER_THRESHOLD   = 80   (rapidfuzz token_set_ratio)
#   KEYPOINTS_EMBEDDING       = 0.85 (cosine similarity)
#   PACKETS_DEDUP_RAPIDFUZZ   = 70   (rapidfuzz token_set_ratio)
#   PACKETS_DEDUP_JACCARD     = 0.50 (content-word Jaccard overlap)

# ── Coverage thresholds (for reference — 3 tiers) ───────────────────────────
# COVERAGE_SUMMARIZER_REPROMPT = 0.70  — summarizer reprompts below this
# COVERAGE_JUDGE_GAP_FILL      = 0.75  — judge triggers gap-fill below this
# COVERAGE_HARD_REJECTION      = 0.30  — chapter is hard-rejected below this
