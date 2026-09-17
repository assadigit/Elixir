"""V18.20.3.5 (audit v182034): per-call LLM truncation metadata.

The V18.20.3.4 rig run's scholar reflection hit the num_predict cap
(``done_reason=length``, 26,237 chars out) and the response was cut BEFORE
the ``<gap_fill_bullets>`` section ever opened. The section-tag heuristic
in scholar_reflection only recognizes truncation when that tag is present
but unclosed — so the cut response parsed as "no reflections, no gap
bullets" and the pipeline logged a clean ``Scholar reflection: no
significant gaps found`` from an analysis that never finished (audit
defect: truncated verdict). The provider had the authoritative signal
(``done_reason``) but only LOGGED it — nothing downstream could see it.

This module propagates it without changing any call signature: the
provider sets a ContextVar after every response; the caller that cares
(scholar reflection, and any future verdict-parsing stage) reads it
immediately after its call. ContextVars are isolated per thread, so
parallel summarisation workers cannot read each other's flags, and the
flag is set on EVERY response (True only for ``done_reason == "length"``)
so a stale True can never leak across calls.

Content-agnostic by construction — no text inspection at all.
"""
from __future__ import annotations

import contextvars
import threading
from typing import Any

# True when the MOST RECENT LLM call in this thread/context stopped at the
# num_predict cap (done_reason == "length"). Set by the provider layer on
# every response; consumed-and-reset by verdict-critical callers.
_last_call_truncated: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "llm_last_call_truncated", default=False
)


def mark_call_truncated(truncated: bool) -> None:
    """Provider-side setter — call after EVERY response (not only truncated
    ones) so the flag always reflects the latest call in this context."""
    _last_call_truncated.set(bool(truncated))


def consume_call_truncated() -> bool:
    """Caller-side read-and-reset: True if the just-finished call was cut
    at the output cap. Resetting on read prevents a later stage from
    acting on a stale flag."""
    try:
        return _last_call_truncated.get()
    finally:
        _last_call_truncated.set(False)


# ═════════════════════════════════════════════════════════════════════════════
# V18.20.3.9 (Phase 3.a / C1 — per-call telemetry): process-wide LLM call
# registry. The provider layer records one entry per completed call
# (model, wall-clock duration, prompt/eval token counts, done_reason);
# the end-of-run diagnostic prints the aggregate + the slowest calls.
# This replaces estimate-driven perf statements with measured ones — the
# same data the .3.7/.3.8 rig audits had to reconstruct by hand from log
# timestamps. Thread-safe (parallel summarisation workers); best-effort
# (recording must NEVER fail a call).
# ═════════════════════════════════════════════════════════════════════════════
_CALL_RECORDS: list[dict[str, Any]] = []
_CALL_LOCK = threading.Lock()
_MAX_RECORDS = 10000  # bound the registry (a full book ≈ hundreds of calls)


def record_call_telemetry(
    model: Any,
    duration_s: float,
    prompt_tokens: Any,
    output_tokens: Any,
    done_reason: Any,
) -> None:
    """Provider-side: record one completed LLM call. Never raises."""
    try:
        with _CALL_LOCK:
            _CALL_RECORDS.append(
                {
                    "model": str(model),
                    "duration_s": float(duration_s),
                    "prompt_tokens": prompt_tokens,
                    "output_tokens": output_tokens,
                    "done_reason": str(done_reason),
                }
            )
            if len(_CALL_RECORDS) > _MAX_RECORDS:
                del _CALL_RECORDS[: len(_CALL_RECORDS) - _MAX_RECORDS]
    except Exception:
        pass  # best-effort — telemetry must never break a call


def get_call_telemetry() -> list[dict[str, Any]]:
    """Snapshot copy of the recorded calls (this run, so far)."""
    with _CALL_LOCK:
        return list(_CALL_RECORDS)


def call_telemetry_summary(top_n: int = 5) -> dict[str, Any]:
    """Aggregate for the end-of-run diagnostic: call count, total LLM
    wall-time, truncated-call count, and the N slowest calls."""
    with _CALL_LOCK:
        records = list(_CALL_RECORDS)
    if not records:
        return {"calls": 0, "total_s": 0.0, "truncated": 0, "slowest": []}
    total = sum(r["duration_s"] for r in records)
    truncated = sum(1 for r in records if r["done_reason"] == "length")
    slowest = sorted(records, key=lambda r: -r["duration_s"])[:top_n]
    return {
        "calls": len(records),
        "total_s": total,
        "truncated": truncated,
        "slowest": slowest,
    }


def reset_call_telemetry() -> None:
    """Clear the registry (called at conversion start so each run's
    diagnostic reports only that run's calls)."""
    with _CALL_LOCK:
        _CALL_RECORDS.clear()
