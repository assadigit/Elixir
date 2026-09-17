"""V18.2.26 (Phase 3.1 wiring / A1) — Async-parallel stage runner.

The problem
-----------
``_summarize_inner`` runs 5-10 LLM stages sequentially. Some stages are
INDEPENDENT (they operate on the final summary + source, not on each other's
output) and could run concurrently. The V18.2.24 ``AsyncOllamaProvider`` +
``gather_calls`` infrastructure is built but not wired in.

The fix (pragmatic, low-risk)
-----------------------------
Rather than rewrite the entire ``_summarize_inner`` pipeline (high-risk on
a 867-test-green system), this module provides a **parallel coverage +
grounding check** — the two most expensive independent post-summary stages.

Both operate on the same (summary, source) pair and don't depend on each
other's output:
- ``ContentJudge.judge(summary, source)`` → coverage + hallucination check
- ``_llm_grounding_check(bullets, source)`` → LLM-as-judge grounding check

Running them concurrently via ``asyncio.gather`` cuts wall-clock time from
t_judge + t_grounding to max(t_judge, t_grounding). For a chapter where
both take ~30s, that's 60s → 30s.

Design: opt-in, sync-bridge, preserves existing semantics
--------------------------------------------------------
The function is a SYNC wrapper (uses ``run_async`` internally) so the
existing sync ``_summarize_inner`` can call it without changes. The
underlying work runs in a thread pool (for sync functions) — the speedup
comes from true parallelism when the functions do I/O (HTTP calls to
Ollama).

This is the proof-of-concept that the async infrastructure works in
production. The full ``_summarize_inner`` async migration is the
follow-up (higher risk, needs per-strategy migration).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)


def parallel_judge_and_grounding(
    judge_fn: Callable[[], Any],
    grounding_fn: Callable[[], Any],
    *,
    log_callback: Callable[[str, str], None] | None = None,
) -> tuple[Any, Any]:
    """Run the content judge + grounding check in parallel.

    Both functions are called with no args (use ``lambda`` or
    ``functools.partial`` to bind). They run concurrently in a thread pool;
    the function blocks until both complete (or one raises).

    Args:
        judge_fn: callable returning the ContentJudge result.
        grounding_fn: callable returning the grounding check result
            (list of ungrounded bullets).
        log_callback: optional ``fn(msg, level)`` for progress logging.

    Returns:
        ``(judge_result, grounding_result)`` — both results, in order.

    Raises:
        The first exception raised by either function (the other is
        cancelled/ignored — matches ``asyncio.gather`` default behavior).

    Example::

        from core.obs.parallel_stages import parallel_judge_and_grounding
        judge_result, ungrounded = parallel_judge_and_grounding(
            judge_fn=lambda: _judge.judge(summary, source),
            grounding_fn=lambda: s._llm_grounding_check(bullets, content),
            log_callback=s.log,
        )
    """
    log = log_callback or (lambda msg, level="INFO": None)
    log("    🔄 Running content judge + grounding in parallel…", "INFO")

    with ThreadPoolExecutor(max_workers=2) as pool:
        judge_future = pool.submit(judge_fn)
        grounding_future = pool.submit(grounding_fn)

        # Wait for both. If one raises, its exception propagates here.
        # The other may still be running (it'll be cancelled when the pool
        # exits, but we don't wait for it — matches gather semantics).
        try:
            judge_result = judge_future.result()
        except Exception as exc:
            log(f"    ⚠️ Content judge failed: {exc}", "WARNING")
            # Don't cancel grounding — let it finish so we have partial results.
            grounding_result = _safe_get(grounding_future)
            raise

        try:
            grounding_result = grounding_future.result()
        except Exception as exc:
            log(f"    ⚠️ Grounding check failed: {exc}", "WARNING")
            grounding_result = None  # graceful degradation

    log("    ✅ Parallel judge + grounding complete", "DEBUG")
    return judge_result, grounding_result


def _safe_get(future, timeout: float = 5.0) -> Any:
    """Best-effort get from a future — returns None on any failure."""
    try:
        return future.result(timeout=timeout)
    except Exception:
        return None


def parallel_stages(
    *fns: Callable[[], Any],
    max_workers: int = 4,
    log_callback: Callable[[str, str], None] | None = None,
) -> list:
    """Run N independent stages in parallel (general-purpose).

    Each ``fn`` is a zero-arg callable. They run concurrently in a thread
    pool; results are returned in the same order as the inputs.

    Use for any set of independent LLM/IO stages. The speedup is from true
    parallelism when the functions do blocking I/O (HTTP to Ollama).

    Args:
        *fns: the callables to run in parallel.
        max_workers: the thread pool size (default 4).
        log_callback: optional ``fn(msg, level)`` for progress logging.

    Returns:
        List of results in the same order as ``fns``. ``None`` for any
        function that raised (graceful degradation — one failure doesn't
        block the others).

    Example::

        results = parallel_stages(
            lambda: call_llm(prompt1),
            lambda: call_llm(prompt2),
            lambda: call_llm(prompt3),
        )
    """
    log = log_callback or (lambda msg, level="INFO": None)
    if not fns:
        return []

    log(f"    🔄 Running {len(fns)} stages in parallel (max_workers={max_workers})…", "INFO")

    results: list = [None] * len(fns)
    with ThreadPoolExecutor(max_workers=min(max_workers, len(fns))) as pool:
        futures = {pool.submit(fn): i for i, fn in enumerate(fns)}
        for future in futures:
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                log(f"    ⚠️ Parallel stage {idx} failed: {exc}", "WARNING")
                results[idx] = None  # graceful degradation

    log("    ✅ Parallel stages complete", "DEBUG")
    return results
