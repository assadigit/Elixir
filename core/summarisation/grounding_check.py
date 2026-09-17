"""V18.15.3 (Phase 5 Stage 3, Batch 4.3): LLM-as-judge grounding check.

Extracted verbatim from ``Summarizer._llm_grounding_check`` (god-class
decomposition Stage 4 — the 15th extraction). The langextract fallback: when
langextract is unavailable, the summarizer model verifies each bullet against
the source text. The LLM is asked to judge whether each bullet is supported.

**Extraction map**:

| Summarizer method (old) | grounding_check function (new) | self deps |
|------------------------|-------------------------------|-----------|
| ``_llm_grounding_check`` | ``llm_grounding_check`` | ``prompt_manager``, ``fusion_enabled``, ``fusion_use_for_grounding``, ``_call_cloud``, ``fusion_cloud_temperature``, ``_call_llm_with_empty_retry``, ``temperature``, ``log`` |

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-3 pattern. Zero mutable state —
the function is read-only w.r.t. the Summarizer instance.

Characterization tests: ``tests/test_grounding_check.py`` captures the
empty-input path, the chunking behaviour (10 bullets/chunk), the YES/NO
verdict parsing, the cloud-vs-local routing, the empty-response skip, and
the exception-per-chunk continue.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
CallCloudFn = Callable[..., str | None]
CallLlmRetryFn = Callable[..., str | None]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


def _noop_call(prompt, **kw):
    """Default no-op LLM call (returns empty → caller skips chunk)."""
    return ""


# ── llm_grounding_check (extracted verbatim) ───────────────────────────────

def llm_grounding_check(
    bullets: list[str],
    source_text: str,
    prompt_manager: PromptManagerLike = None,
    fusion_enabled: bool = False,
    fusion_use_for_grounding: bool = False,
    call_cloud: CallCloudFn | None = None,
    fusion_cloud_temperature: float = 0.3,
    call_llm_with_empty_retry: CallLlmRetryFn | None = None,
    temperature: float = 0.7,
    log: LogCallback | None = None,
) -> list[str]:
    """LLM-as-judge grounding check (langextract fallback).

    Returns a list of bullets the LLM flagged as NOT supported (ungrounded).
    These are then dropped by the caller.
    """
    if log is None:
        log = _noop_log
    if call_cloud is None:
        call_cloud = _noop_call
    if call_llm_with_empty_retry is None:
        call_llm_with_empty_retry = _noop_call

    if not bullets or not source_text:
        return []

    # V13.28.0 P2.8: Increased from 8000 → 20000 chars.
    # The old 8000 truncation was too aggressive — for a 15K-char chapter,
    # bullets grounded in the second half were falsely flagged as ungrounded.
    max_source_chars = 20000
    truncated_source = source_text[:max_source_chars]
    if len(source_text) > max_source_chars:
        truncated_source += "\n[... source truncated ...]"

    ungrounded = []
    calls_made = 0

    # V13.28.0 P2.8: Chunk bullets into groups of 10 to avoid prompt
    # length issues with 40+ bullets.
    CHUNK_SIZE = 10
    chunks = [bullets[i:i + CHUNK_SIZE] for i in range(0, len(bullets), CHUNK_SIZE)]

    for chunk_idx, bullet_chunk in enumerate(chunks):
        # Build a single LLM call with this chunk of bullets
        offset = chunk_idx * CHUNK_SIZE
        bullet_list = "\n".join(f"{offset + i + 1}. {bp}" for i, bp in enumerate(bullet_chunk))
        prompt = prompt_manager.render_template(
            "summarisation/grounding_check",
            truncated_source=truncated_source,
            bullet_list=bullet_list,
        )

        try:
            # V13.36.0: Use fusion cloud for grounding check when enabled
            # (site B — bullet verification). Also fixes a pre-existing bug:
            # the old code called _call_ollama(prompt, temp=0.0, max_tokens=4096)
            # but _call_ollama's signature is (prompt, model, temp, max_tokens)
            # — so temp=0.0 was passed as the model name (broken for cloud users).
            if fusion_enabled and fusion_use_for_grounding:
                response = call_cloud(prompt, max_tokens=4096,
                                      temperature=fusion_cloud_temperature)
            else:
                # V13.37.0: Use temperature (model's optimal), not 0.2.
                # V18.8 (Phase 5.3): Route through _call_llm_with_empty_retry
                # instead of _call_llm directly — gets the same 2-attempt retry
                # + Qwen3 /no_think injection as all other LLM calls.
                response = call_llm_with_empty_retry(
                    prompt, temperature=temperature, max_tokens=4096,
                )
            calls_made += 1
            if not response:
                continue  # LLM call failed — don't drop anything from this chunk

            # Parse the response
            for line in response.strip().splitlines():
                line = line.strip()
                m = re.match(r'^(\d+)\s*:\s*(YES|NO)', line, re.IGNORECASE)
                if m:
                    idx = int(m.group(1)) - 1  # 0-indexed
                    verdict = m.group(2).upper()
                    if verdict == "NO" and 0 <= idx < len(bullets):
                        ungrounded.append(bullets[idx])
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            continue  # error — don't drop anything from this chunk

    if calls_made > 0:
        log(
            f"    🔬 LLM grounding check: {calls_made} call(s) for "
            f"{len(bullets)} bullets — {len(ungrounded)} flagged ungrounded",
            "DEBUG",
        )

    return ungrounded
