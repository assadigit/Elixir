"""Phase 6.3 (V0.19) — bounded cross-book queue concurrency (cloud only).

Roadmap Phase 6.3: "Bounded cross-book workers in the Queue view when
provider ≠ ollama (VRAM not a constraint in cloud)". The queue worker
(``ui_qt/views/queue_view.py``) processes books strictly sequentially
today; with a CLOUD provider there is no local VRAM constraint, so
several books can convert concurrently — bounded, opt-in by setting.

This module is deliberately PySide6-FREE (pure Python + threading) so it
is unit-testable on headless CI (the house pattern: the Qt view wires
signals; the concurrency semantics live here and are pinned by direct
tests — see ``tests/test_v182045_p4b_callbacks_async.py`` for the
pattern's precedent).

Behavior contract
-----------------
- ``resolve_parallel_books`` returns 1 (the exact pre-V0.19 sequential
  behavior) unless ALL of: the provider is cloud, more than one book is
  pending, and the ``queue.max_parallel_books`` setting asks for more.
  Local providers (ollama / llamacpp / anything unrecognized) ALWAYS get
  1 — the Phase-6 acceptance "VRAM behavior unchanged on 12 GB rig
  (max_workers logic untouched for local path)".
- ``run_books_parallel`` gives every book its OWN cancel event (a stop
  request cancels every active book), never lets one book's crash kill
  the others (per-book try/except → failed outcome), and returns
  outcomes in input order regardless of completion order.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Providers whose inference runs remotely — no local VRAM constraint.
# Anything else (ollama, llamacpp, empty, typos) is treated as LOCAL and
# always stays sequential (fail-closed to the current behavior).
CLOUD_PROVIDERS = frozenset({"claude", "freellmapi", "openrouter", "openai", "openai_compatible"})

MAX_PARALLEL_BOOKS_SETTING = "queue.max_parallel_books"
DEFAULT_MAX_PARALLEL_BOOKS = 2
ABSOLUTE_MAX_PARALLEL_BOOKS = 4


def resolve_parallel_books(provider: str, setting: int, pending_count: int) -> int:
    """The bounded cross-book worker count for a queue run.

    1 = sequential (the pre-V0.19 behavior). Only a CLOUD provider with
    more than one pending book and a setting > 1 unlocks parallelism;
    the result is clamped to ``ABSOLUTE_MAX_PARALLEL_BOOKS``.
    """
    if provider not in CLOUD_PROVIDERS:
        return 1
    if pending_count <= 1:
        return 1
    try:
        n = int(setting)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_PARALLEL_BOOKS
    if n <= 1:
        return 1
    return max(1, min(ABSOLUTE_MAX_PARALLEL_BOOKS, n))


@dataclass
class BookOutcome:
    """One book's parallel-queue result (input order preserved)."""

    idx: int
    ok: bool
    error: str = ""


def run_books_parallel(
    jobs: list[tuple[int, Callable[[threading.Event], object]]],
    *,
    max_workers: int,
    on_started: Callable[[int, threading.Event], None] | None = None,
    on_finished: Callable[[BookOutcome], None] | None = None,
) -> list[BookOutcome]:
    """Run per-book conversions concurrently, bounded by ``max_workers``.

    Args:
        jobs: ``(book_index, fn)`` pairs. ``fn(cancel_event)`` runs ONE
            conversion end-to-end and returns its result; it must honor
            the cancel event it is handed (the per-book Converter gets it).
        max_workers: the bound (already resolved via ``resolve_parallel_books``).
        on_started: called with ``(idx, cancel_event)`` just before each
            book starts (the caller can register the event for stopping).
        on_finished: called with the book's outcome the moment it completes
            (completion order, NOT input order — for live status updates).

    Returns:
        Outcomes in INPUT order. A book whose ``fn`` raised becomes a
        failed outcome (the pool never crashes); the exception text is
        the error. ``fn``'s return value is not interpreted here.
    """
    outcomes: dict[int, BookOutcome] = {}
    cancel_events: dict[int, threading.Event] = {}

    def _run_one(idx: int, fn: Callable[[threading.Event], object]) -> None:
        event = threading.Event()
        cancel_events[idx] = event
        if on_started is not None:
            try:
                on_started(idx, event)
            except Exception:  # noqa: BLE001 — UI callback must not kill the book
                logger.debug("on_started(%d) crashed", idx, exc_info=True)
        try:
            fn(event)
            outcomes[idx] = BookOutcome(idx=idx, ok=True)
        except Exception as exc:  # noqa: BLE001 — one book's crash never kills the queue
            logger.exception("parallel queue book %d crashed", idx)
            outcomes[idx] = BookOutcome(idx=idx, ok=False, error=str(exc))
        if on_finished is not None:
            try:
                on_finished(outcomes[idx])
            except Exception:  # noqa: BLE001
                logger.debug("on_finished(%d) crashed", idx, exc_info=True)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as pool:
        futures = [pool.submit(_run_one, idx, fn) for idx, fn in jobs]
        for fut in futures:
            try:
                fut.result()
            except Exception:  # noqa: BLE001 — already recorded per-book
                pass

    return [outcomes[idx] for idx, _ in jobs]


__all__ = [
    "CLOUD_PROVIDERS",
    "MAX_PARALLEL_BOOKS_SETTING",
    "DEFAULT_MAX_PARALLEL_BOOKS",
    "ABSOLUTE_MAX_PARALLEL_BOOKS",
    "resolve_parallel_books",
    "BookOutcome",
    "run_books_parallel",
]
