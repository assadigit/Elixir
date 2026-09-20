"""Phase 6.2 (V0.19) — bounded intra-chapter LLM-call overlap (thread-based).

The problem (Phase-1 baseline, ``docs/baseline/timings_V0.13.md``)
------------------------------------------------------------------
A chapter's pipeline makes 5+ LLM calls that are **strictly sequential**
within the chapter (primary → grounding/judge → gap-fill → scholar →
scholar-retry). LLM time is 98.5% of chapter wall-clock at full latency,
so the only optimizations that matter either reduce round-trips or
overlap them. Chapter-level parallelism is already near-linear (329%
overlap @ 4 workers); the remaining serialization is *within* a chapter.

Why threads and not ``async_provider.gather_calls``
---------------------------------------------------
The roadmap (Phase 6.2) allows "``async_provider.gather_calls`` or a
thread-based equivalent if the httpx path underperforms". The thread
equivalent is the right call here for three structural reasons:

1. **Provider coverage** — ``AsyncOllamaProvider`` speaks Ollama only.
   The pipeline's providers are ollama, llamacpp, claude, openai-compat
   (openrouter/openai/freellmapi). A thread-based overlap works for every
   provider because it wraps the SAME sync callables the sequential path
   already uses.
2. **No event-loop plumbing** — the app is a PySide6 desktop app; the
   conversion runs on Qt worker threads. ``asyncio.run`` inside
   ``run_async`` cannot be nested in a running loop and the sync bridge
   blocks the calling thread anyway — the gain over a thread pool is
   zero for HTTP-bound work (both wait on the socket).
3. **Already-proven concurrency** — the transport (``_call_llm`` →
   requests + locked response cache) is *already* exercised concurrently
   by cross-chapter ThreadPoolExecutor workers in production. Intra-
   chapter overlap reuses exactly that proven path.

Semantics contract (what "safe overlap" means here)
---------------------------------------------------
Every lever must be **byte-identical on its success path** and
**independently disableable** (roadmap Phase-6 rollback plan). The
helpers below guarantee the mechanical part:

- **Ordered results** — ``run_independent`` returns results in input
  order regardless of completion order, so downstream merges see the
  same list the sequential loop would have built.
- **Sequential fallback** — ``max_workers <= 1`` or a single callable
  runs inline (zero thread overhead, zero behavior delta). The default
  for every lever is OFF (``summarisation.parallel_stages``), so the
  shipped default behavior is bit-for-bit the pre-V0.19 pipeline.
- **Sequential exception semantics** — if several overlapped calls
  raise, the exception of the LOWEST-INDEX call is re-raised (the call
  the sequential loop would have died on). Calls after the first
  failure may still have run to completion; their side effects are
  limited to idempotent response-cache writes and log lines (each
  lever's callables are pure w.r.t. pipeline state — verified per
  lever, see the module docstrings of ``map_reduce`` /
  ``multi_sample`` / the judge-scholar orchestrator seam).

Settings (all default OFF — the roadmap's "default off → on after soak")
------------------------------------------------------------------------
- ``summarisation.parallel_stages``            master switch (bool)
- ``summarisation.parallel_stages_map``        map-reduce chunk overlap (default True when master on)
- ``summarisation.parallel_stages_b3``         B3 multi-sample overlap (default True when master on)
- ``summarisation.parallel_stages_judge_scholar``  speculative scholar ∥ judge (default True when master on)
- ``summarisation.parallel_stages_max_workers``    concurrency bound, default 4, clamped 1..8

The master switch OFF forces every lever OFF regardless of the
per-lever values (one switch to disable everything — the rollback
plan's "each lever independently disableable" plus a global kill).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from utils.settings import Settings

logger = logging.getLogger(__name__)

# Concurrency bound clamp — enough to hide I/O latency on the busiest
# lever (map-reduce waves), small enough to never look like a load test
# against a local Ollama server or a cloud rate limit.
_MAX_WORKERS_CLAMP = 8
_DEFAULT_MAX_WORKERS = 4

# Per-lever setting keys → (lever name, per-lever default when master on).
_LEVER_KEYS: dict[str, tuple[str, str]] = {
    "map": ("summarisation.parallel_stages_map", "parallel_stages_map"),
    "b3": ("summarisation.parallel_stages_b3", "parallel_stages_b3"),
    "judge_scholar": (
        "summarisation.parallel_stages_judge_scholar",
        "parallel_stages_judge_scholar",
    ),
}

_MASTER_KEY = "summarisation.parallel_stages"
_WORKERS_KEY = "summarisation.parallel_stages_max_workers"


def master_enabled() -> bool:
    """True iff the ``summarisation.parallel_stages`` master switch is on.

    Fail-closed: any read error → False (the sequential pipeline).
    """
    try:
        return bool(Settings().get(_MASTER_KEY, False))
    except Exception:  # pragma: no cover — Settings is in-memory safe; belt & braces
        return False


def lever_enabled(lever: str) -> bool:
    """True iff the master switch AND the per-lever switch are both on.

    Per-lever defaults are True when the master is on (opt out of a
    lever by setting its key to False). Unknown lever names → False.
    """
    entry = _LEVER_KEYS.get(lever)
    if entry is None:
        return False
    key, _name = entry
    if not master_enabled():
        return False
    try:
        return bool(Settings().get(key, True))
    except Exception:  # pragma: no cover
        return False


def lever_workers() -> int:
    """The concurrency bound for the levers (clamped 1..8, default 4)."""
    try:
        n = int(Settings().get(_WORKERS_KEY, _DEFAULT_MAX_WORKERS))
    except Exception:  # pragma: no cover
        return _DEFAULT_MAX_WORKERS
    return max(1, min(_MAX_WORKERS_CLAMP, n))


def run_independent[T](
    fns: Sequence[Callable[[], T]],
    *,
    max_workers: int = 2,
    label: str = "",
) -> list[T]:
    """Run independent callables concurrently; return results in input order.

    - ``len(fns) <= 1`` or ``max_workers <= 1`` → runs INLINE (no pool):
      the sequential pipeline, zero overhead, byte-identical.
    - Otherwise the callables run on a bounded ``ThreadPoolExecutor``.
      Results are collected in input order — the merge code downstream
      sees exactly the list the sequential loop would have produced.
    - Exceptions: all callables are awaited (no cancellation mid-flight),
      then the exception of the lowest-index failed callable is re-raised
      — the same exception the sequential loop would have propagated.
      Later callables may have completed despite the earlier failure;
      their side effects are idempotent (response-cache puts, logs).

    ``label`` is used only for the failure log line (debuggability).
    """
    if len(fns) <= 1 or max_workers <= 1:
        return [fn() for fn in fns]

    results: list[T | None] = [None] * len(fns)
    errors: dict[int, BaseException] = {}

    def _run_one(idx: int, fn: Callable[[], T]) -> None:
        try:
            results[idx] = fn()
        except BaseException as exc:  # noqa: BLE001 — re-raised in order below
            errors[idx] = exc

    with ThreadPoolExecutor(max_workers=min(max_workers, len(fns))) as pool:
        futures = [pool.submit(_run_one, i, fn) for i, fn in enumerate(fns)]
        for fut in futures:
            # Await every callable — see the exception semantics above.
            try:
                fut.result()
            except Exception:  # noqa: BLE001 — already recorded per-index
                pass

    if errors:
        first = min(errors)
        if label:
            logger.debug(
                "stage_overlap[%s]: callable %d/%d failed (%s: %s) — "
                "re-raising in sequential order",
                label,
                first + 1,
                len(fns),
                type(errors[first]).__name__,
                errors[first],
            )
        raise errors[first]
    return list(results)  # type: ignore[return-value] — all set on success


__all__ = [
    "master_enabled",
    "lever_enabled",
    "lever_workers",
    "run_independent",
]
