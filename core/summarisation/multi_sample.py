"""V18.11 (Phase 5 Stage 3, Batch 2.2): Multi-sample (B3) summarization + voting.

Extracted verbatim from ``Summarizer._multi_sample_summarize`` (god-class
decomposition Stage 3). Generates N summaries at the model's optimal
temperature and votes on the best (keeping any bullet that appears in ≥1
sample; the best exec/thorough are picked by coverage, or by the cloud
fusion judge when enabled).

**Extraction map**:

| Summarizer method (old)        | multi_sample function (new) | self deps |
|--------------------------------|-----------------------------|-----------|
| ``_multi_sample_summarize``    | ``multi_sample_summarize``   | ``temperature``, ``primary_model``, ``_recover_vram``, ``log``, ``_summarize_with_model``, ``conservative_drops``, ``quarantine``, ``_current_heading``, ``fusion_enabled``, ``fusion_use_for_b3_judge``, ``_b3_cloud_judge``, ``_compute_coverage`` |

Each dependency is passed as an EXPLICIT parameter (not a context object —
the V18.6.3 crash pattern). ``_compute_coverage`` is itself a delegate to
``summary_validator.compute_coverage`` (Phase 5 Batch A) — passed as a callable.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS. The 12 deps are all
named kwargs; no ``PromptContext``-style bundle. Matches the proven Phase 5
Batch B pattern (``verify_bullets`` took ~8 explicit params).

Characterization tests: ``tests/test_multi_sample.py`` captures the no-samples,
single-sample, N-sample voting, and fusion-judge paths with mocked
``summarize_with_model`` / ``compute_coverage`` / ``b3_cloud_judge``.
"""
from __future__ import annotations

import logging
import re
from collections import Counter as _Counter
from collections.abc import Callable
from typing import Any

from utils.error_trace import log_swallow

# Type aliases (duck-typed).
LogCallback = Callable[[str, str], None]
SummarizeWithModelFn = Callable[..., dict | None]
RecoverVramFn = Callable[..., None]
ComputeCoverageFn = Callable[[str, str], float]
B3CloudJudgeFn = Callable[[list[dict], str, str], tuple]
QuarantineLike = Any

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── multi_sample_summarize (extracted verbatim) ────────────────────────────


def multi_sample_summarize(
    heading: str,
    text: str,
    *,
    concepts: list[str] | None = None,
    callouts: list[str] | None = None,
    n_samples: int = 3,
    primary_model: str,
    temperature: float,
    recover_vram: RecoverVramFn,
    summarize_with_model: SummarizeWithModelFn,
    b3_cloud_judge: B3CloudJudgeFn | None,
    compute_coverage: ComputeCoverageFn,
    conservative_drops: bool,
    quarantine: QuarantineLike,
    current_heading: str,
    fusion_enabled: bool,
    fusion_use_for_b3_judge: bool,
    log: LogCallback | None = None,
) -> dict | None:
    """V3.3.0 B3: Generate N summaries and vote on the best.

    Extracted verbatim from ``Summarizer._multi_sample_summarize``. The only
    changes are ``self.X`` → named parameters. The optimal-temp lookup, the
    per-sample VRAM recovery + try/except, the bullet-voting (threshold=1),
    the V13.40.3 dedup-skip, and the fusion-judge / coverage-pick branches
    are byte-for-byte identical.

    V13.32.8: All samples use the model's optimal temperature (read from
    llm.model_profiles in settings) — NO escalation. The old 0.2/0.4/0.6
    escalation was removed because it hurt Gemma 4 (whose optimal temp is
    1.0 — low temps produce empty/degenerate output on that model).

    Bullet voting: keep any bullet that appears in >=1 sample (threshold
    is 1, not 2-of-3). The old 2-of-3 threshold dropped too many legitimate
    paraphrases. The best executive_summary and thorough_summary are
    picked separately by per-field coverage against the source text.
    """
    log = log or _noop_log
    # V13.32.8: Use model's optimal temperature for ALL samples (no escalation).
    optimal_temp = temperature
    model_lower = (primary_model or "").lower()
    try:
        from utils.settings import Settings
        _s = Settings()
        profiles = _s.get("llm.model_profiles", {})
        if isinstance(profiles, dict):
            for key, val in profiles.items():
                if key.lower() == model_lower or (key.lower() in model_lower and len(key) > 5):
                    if isinstance(val, dict) and "temperature" in val:
                        optimal_temp = val["temperature"]
                    break
    except Exception as _e:
        # V18.2.14 (B4): was silent ``pass`` — now traceable.
        log_swallow("model_temp_profile_lookup", _e,
                    detail=f"model={model_lower[:40]}")
    temps = [optimal_temp] * n_samples
    samples = []
    for i, temp in enumerate(temps):
        # V15.1.0: VRAM recovery between B3 samples (from V15.0.1).
        # Prevents CUDA OOM / Ollama hard-crash on local GPUs at high VRAM.
        if i > 0:
            recover_vram(context=f"B3-sample-{i+1}", delay_sec=120.0)
        log(f"    \U0001f916 B3 sample {i+1}/{n_samples} (t={temp:.2f})\u2026", "DEBUG")
        # V15.1.0: per-sample try/except so one crash doesn't kill the app.
        try:
            result = summarize_with_model(
                heading, text, primary_model, temp, with_cot=True,
                concepts=concepts, callouts=callouts,
            )
        except Exception as _b3e:
            log(
                f"    \u26a0\ufe0f B3 sample {i+1}/{n_samples} crashed "
                f"({type(_b3e).__name__}: {_b3e}) \u2014 skipping, continuing "
                f"with remaining samples",
                "WARNING",
            )
            logger.warning("B3 sample %d crashed: %s: %s", i + 1, type(_b3e).__name__, _b3e)
            result = None
        if result:
            samples.append(result)

    if not samples:
        return None

    if len(samples) == 1:
        return samples[0]

    # Bullet voting: normalize each bullet and count across samples
    bullet_votes = _Counter()
    bullet_map = {}  # normalized → original text
    for s in samples:
        seen = set()
        for bp in s.get("bullet_points", []):
            norm = re.sub(r'[^\w\s]', '', str(bp).lower()).strip()
            if norm and norm not in seen:
                seen.add(norm)
                bullet_votes[norm] += 1
                if norm not in bullet_map:
                    bullet_map[norm] = str(bp)

    # Lowered voting threshold from ceil(n/2) to 1 (keep all bullets
    # from any sample). The original threshold of 2/3 was too strict — it
    # dropped good bullets that appeared in only 1 sample. Since the post-
    # filter handles dedup and quality, we keep all unique bullets here.
    voted_bullets = [bullet_map[norm] for norm, count in bullet_votes.items() if count >= 1]

    # Dedup voted bullets immediately using model-profile threshold.
    # B3 voting with threshold=1 produces 50+ bullets — many are near-duplicates
    # from different samples. Dedup them here BEFORE returning, so downstream
    # (keypoints_builder + simplification) doesn't get flooded with 50 bullets.
    # V10.12.9: raised the floor from 60 → 75 — the old threshold let too
    # many near-duplicates through (253 bullets with 14 starting "Orexin",
    # 18 "Memantine", 12 "Glutamate" — many were slight rewordings).
    #
    # V10.28.0 (Sprint 1): In conservative mode the dedup MERGE is
    # DISABLED (duplicates are kept) — but each would-be-merged duplicate
    # is logged to the quarantine so the user can audit the redundancy.
    # The recovery pass does not resurrect dedup drops (they're
    # duplicates, not grounding failures), so source_overlap=0.0.
    #
    # V10.31.0 (Sprint 4.2): Delegates to DedupService (the unified
    # dedup implementation).  The model-profile threshold lookup is
    # preserved — DedupService takes the resolved threshold as a param.
    #
    # V13.40.3: SKIP dedup after B3 voting. The 75% threshold was killing
    # ALL bullets when 3 samples at temp=1.0 produce slightly different
    # wording of the same claims. B3 voting already filters (threshold=1
    # keeps all unique bullets); the downstream pipeline has its own
    # dedup. Running DedupService here with 75% on voted bullets produces
    # 0 bullets (observed in V13.40.2 log — "kept 0" after dedup).
    # The dedup is now skipped — bullets pass through to the pipeline
    # which handles dedup at the keypoints_builder stage with proper
    # context.
    # (V0.08 / P2: the `_skip_b3_dedup = True` flag and its permanently-dead
    # `if not _skip_b3_dedup:` branch were removed; the behaviour is
    # unchanged — dedup after B3 voting has been skipped since V13.40.3.)

    # Pick best exec_summary + thorough by coverage
    source = text
    # V13.36.0: When fusion is enabled, use the cloud model as the B3 judge
    # (site D). Instead of picking by keyword-overlap coverage (which can't
    # assess nuance), the cloud model reads all N samples and picks the best.
    if fusion_enabled and fusion_use_for_b3_judge and len(samples) > 1 and b3_cloud_judge is not None:
        best_exec, best_thorough = b3_cloud_judge(samples, source, heading)
    else:
        best_exec = max(samples, key=lambda s: compute_coverage(source, s.get("executive_summary", "")))
        best_thorough = max(samples, key=lambda s: compute_coverage(source, s.get("thorough_summary", "")))

    return {
        "executive_summary": best_exec.get("executive_summary", ""),
        "bullet_points": voted_bullets,
        "thorough_summary": best_thorough.get("thorough_summary", ""),
        "model": "multi_sample_voted",
        "temperature": "voted",
    }


__all__ = [
    "multi_sample_summarize",
    "LogCallback",
]
