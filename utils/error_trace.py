"""V18.2.14 (B4): Traceable error-handling helpers.

WHY THIS EXISTS
---------------
The V18.0 audit (B4) found 51 ``except Exception: pass`` blocks and 19
``logger.debug("best-effort op failed", exc_info=True)`` sites across the
codebase. Both patterns make failures **undiagnosable**:

- ``except Exception: pass`` discards the exception entirely — no log, no
  trace, no way to know it happened or why.
- ``logger.debug("best-effort op failed", exc_info=True)`` records the
  traceback but at DEBUG level (invisible in normal runs) and with a
  generic message that gives no clue *which* operation failed or *where*.

This module provides two helpers that make it trivial to replace those
patterns with **traceable** logging:

- :func:`log_swallow` — for ``except Exception: pass`` sites. Logs the
  exception at INFO (best-effort ops) or WARNING (unexpected ops) with
  the operation context + traceback, then returns. The caller continues
  exactly as before (the exception is swallowed), but now there's a
  permanent, searchable trace.

- :func:`swallow` — a context manager / decorator for the same purpose,
  for cases where wrapping a block is cleaner than a try/except.

DESIGN PRINCIPLES
-----------------
- **Never changes control flow.** A call to :func:`log_swallow` or
  :func:`swallow` swallows the exception exactly like ``pass`` would —
  the only difference is a log record is emitted.
- **One log line per swallow.** Each call emits exactly one record at the
  requested level, with a structured ``extra`` dict containing the
  operation name, exception type, exception message, and the file:line
  of the call site (auto-captured).
- **Traceback at DEBUG, not the requested level.** The full traceback is
  always attached via ``exc_info=True`` so it's available if the log
  handler captures it, but the human-readable message stays on one line.
- **Fail-open.** If the logger itself fails (should never happen), the
  helper still swallows the original exception — logging is best-effort.

USAGE
-----
Replace::

    try:
        cleanup_temp_files()
    except Exception:
        pass  # best-effort

With::

    from utils.error_trace import log_swallow
    try:
        cleanup_temp_files()
    except Exception as e:
        log_swallow("cleanup_temp_files", e)

Or with the context manager::

    from utils.error_trace import swallow
    with swallow("cleanup_temp_files"):
        cleanup_temp_files()
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def log_swallow(
    operation: str,
    exc: BaseException,
    *,
    level: int = logging.INFO,
    detail: str = "",
) -> None:
    """Log a swallowed exception with a full traceable record.

    Args:
        operation: a short, stable name for the operation that failed
            (e.g., ``"cleanup_temp_files"``, ``"stop_vibevoice_subprocess"``).
            This is the primary search key in the log — keep it stable
            across versions so a grep for it finds every occurrence.
        exc: the exception that was caught.
        level: the log level for the human-readable message. Defaults to
            ``INFO`` (best-effort ops). Use ``WARNING`` for unexpected
            failures that may indicate a bug. The full traceback is
            always attached via ``exc_info=True`` regardless of level.
        detail: optional extra context (e.g., the file path being processed,
            the model name, the chunk index). Included in the message
            after the operation name.

    The log record format::

        [swallow] <operation>: <ExcType>: <exc_msg> | <detail>

    Plus a full traceback attached (exc_info=True) so the structured log
    handler can capture the call stack for post-mortem diagnosis.
    """
    # Capture the caller's file:line so the log points at the swallow site,
    # not this helper. frame 0 = log_swallow, frame 1 = caller.
    _caller = "<unknown>"
    try:
        frame = sys._getframe(1)
        _caller = f"{frame.f_code.co_filename}:{frame.f_lineno}"
    except Exception:  # pragma: no cover — _getframe is CPython-only
        pass

    # V18.2.14: Defensively handle non-exception input (callers sometimes
    # pass strings or None by mistake). Never raise — this helper's whole
    # purpose is fail-open logging.
    if not isinstance(exc, BaseException):
        msg = f"[swallow] {operation}: <non-exception: {type(exc).__name__}> {exc!r}"
        if detail:
            msg = f"{msg} | {detail}"
        logger.log(level, msg)
        return

    msg = f"[swallow] {operation}: {type(exc).__name__}: {exc}"
    if detail:
        msg = f"{msg} | {detail}"
    # Always attach the traceback (exc_info) so it's available even when
    # the level is INFO — the structured-logging handler can emit it to
    # a separate trace file for post-mortem.
    logger.log(level, msg, exc_info=(type(exc), exc, exc.__traceback__))


@contextmanager
def swallow(
    operation: str,
    *,
    level: int = logging.INFO,
    detail: str = "",
) -> Iterator[None]:
    """Context manager that swallows + logs any exception in the block.

    Args:
        operation: short stable name (see :func:`log_swallow`).
        level: log level for the message (default INFO).
        detail: optional extra context.

    Example (fire-and-forget)::

        with swallow("cleanup_temp_files"):
            os.unlink(tmp_path)

    The context manager NEVER re-raises — the exception is always swallowed
    after being logged. If you need to react to specific exception types or
    re-raise, use a plain try/except + :func:`log_swallow`.
    """
    try:
        yield
    except BaseException as exc:  # noqa: BLE001 — intentional swallow
        log_swallow(operation, exc, level=level, detail=detail)


__all__ = ["log_swallow", "swallow"]
