"""V18.15.3 (Phase 5 Stage 3, Batch 4.2): B3 cloud-judge sample selection.

Extracted verbatim from ``Summarizer._b3_cloud_judge`` (god-class decomposition
Stage 4 — the 14th extraction). Uses the fusion cloud model to pick the best
B3 multi-sample (executive + thorough) instead of coverage-based keyword
overlap. Falls back to coverage-based picking on any failure.

**Extraction map**:

| Summarizer method (old) | b3_judge function (new) | self deps |
|------------------------|------------------------|-----------|
| ``_b3_cloud_judge`` | ``b3_cloud_judge`` | ``prompt_manager``, ``_call_cloud``, ``fusion_cloud_temperature``, ``log``, ``_compute_coverage`` |

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-3 pattern. Zero mutable state —
the function is read-only w.r.t. the Summarizer instance.

Characterization tests: ``tests/test_b3_judge.py`` captures the success path
(picks exec#N + thorough#M from cloud response), the empty-response path
(defaults to #0), the exception-fallback path (coverage-based picking), and
the out-of-range index path.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
CallCloudFn = Callable[..., Any]
ComputeCoverageFn = Callable[[str, str], float]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


def _default_compute_coverage(source: str, candidate: str) -> float:
    """Default coverage stub (returns 0.0 — only used if none supplied)."""
    return 0.0


# ── b3_cloud_judge (extracted verbatim) ────────────────────────────────────


def b3_cloud_judge(
    samples: list[dict],
    source: str,
    heading: str,
    prompt_manager: PromptManagerLike = None,
    call_cloud: CallCloudFn | None = None,
    fusion_cloud_temperature: float = 0.3,
    log: LogCallback | None = None,
    compute_coverage: ComputeCoverageFn | None = None,
) -> tuple[dict, dict]:
    """Use the fusion cloud model to pick the best B3 sample.

    Returns (best_exec_sample, best_thorough_sample) — each is a sample dict.
    Falls back to coverage-based picking on any failure.
    """
    if log is None:
        log = _noop_log
    if compute_coverage is None:
        compute_coverage = _default_compute_coverage

    try:
        execs = [s.get("executive_summary", "") for s in samples]
        thoroughs = [s.get("thorough_summary", "") for s in samples]

        # Judge executive summaries
        candidates_block = ""
        for i, e in enumerate(execs):
            candidates_block += f"--- Summary {i + 1} ---\n{e[:1000]}\n\n"
        exec_prompt = prompt_manager.render_template(
            "summarisation/b3_judge_exec",
            heading=heading,
            n_candidates=len(execs),
            candidates_block=candidates_block,
        )

        exec_resp = call_cloud(exec_prompt, max_tokens=10, temperature=fusion_cloud_temperature)
        best_exec_idx = 0
        if exec_resp:
            m = re.search(r"(\d+)", exec_resp.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(samples):
                    best_exec_idx = idx

        # Judge thorough summaries
        candidates_block = ""
        for i, t in enumerate(thoroughs):
            candidates_block += f"--- Summary {i + 1} ---\n{t[:1500]}\n\n"
        thorough_prompt = prompt_manager.render_template(
            "summarisation/b3_judge_thorough",
            heading=heading,
            n_candidates=len(thoroughs),
            candidates_block=candidates_block,
        )

        thorough_resp = call_cloud(
            thorough_prompt, max_tokens=10, temperature=fusion_cloud_temperature
        )
        best_thorough_idx = 0
        if thorough_resp:
            m = re.search(r"(\d+)", thorough_resp.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(samples):
                    best_thorough_idx = idx

        log(
            f"    🔀 B3 cloud judge picked exec#{best_exec_idx + 1}, thorough#{best_thorough_idx + 1}",
            "DEBUG",
        )
        return samples[best_exec_idx], samples[best_thorough_idx]
    except Exception as e:
        log(f"    🔀 B3 cloud judge failed ({e}) — falling back to coverage", "WARNING")
        logger.debug("B3 cloud judge failed: %s: %s", type(e).__name__, e)
        best_exec = max(
            samples, key=lambda s: compute_coverage(source, s.get("executive_summary", ""))
        )
        best_thorough = max(
            samples, key=lambda s: compute_coverage(source, s.get("thorough_summary", ""))
        )
        return best_exec, best_thorough
