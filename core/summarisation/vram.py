"""V18.2.19 (M1): VRAM recovery — extracted from Summarizer god class.

WHY THIS EXISTS
---------------
The Summarizer (6000+ lines) had 13 ``_recover_vram()`` call sites +
the method definition inline. This module extracts the VRAM recovery
logic into a standalone function so:

  - The Summarizer is ~30 lines smaller.
  - The VRAM logic is testable in isolation (no Summarizer instance needed).
  - Other modules (e.g. the OCR service's post-OCR clear) can reuse it.

The Summarizer's ``_recover_vram`` method now delegates to
:func:`recover_vram` here, keeping backward compat for the 13 call sites.

BOOK-AGNOSTIC
-------------
VRAM management is pure infrastructure — no domain-specific terms.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable

from utils.error_trace import log_swallow

logger = logging.getLogger(__name__)


def recover_vram(
    is_local: bool,
    delay_sec: float,
    configured_delay: float,
    context: str,
    log_fn: Callable[[str, str], None],
) -> None:
    """Recover VRAM between heavy LLM phases to prevent empty responses.

    This is a NO-OP when using cloud APIs (``is_local == False``). Cloud APIs
    don't have VRAM — the delay would just waste time. All delay durations
    are configurable via settings (``local.vram_recovery_delay_sec``).

    Args:
        is_local: True if running on local Ollama/LMStudio (VRAM matters).
        delay_sec: legacy per-site fallback delay. Unused as a sleep source
            since V18.20.2.0 (SWOT A18) — the configured delay is
            authoritative; kept for call-site/signature compatibility.
        configured_delay: the user-configured delay (from
            ``local.vram_recovery_delay_sec``). When >0, it is the sleep
            duration. When 0 (or negative), the recovery DELAY is disabled:
            no sleep, but the cache-clear part of the recovery still runs
            (V18.20.2.0 SWOT A18 — previously the code slept the hardcoded
            ``delay_sec`` instead, so "0 disables" never actually worked).
        context: a label for the log (e.g. "B4-section-3").
        log_fn: ``fn(message, level)`` callback for traceable logs.

    V18.2.19 (M1): Extracted from Summarizer._recover_vram (line ~1302).
    """
    if not is_local:
        return  # Cloud API — no VRAM to recover, no delay needed

    # V18.20.2.0 (SWOT A18): sleep the CONFIGURED delay (was: slept the
    # hardcoded per-site delay_sec even when the user configured a
    # different value), and honor configured 0 as "delay disabled" (was:
    # fell back to delay_sec, so 0 never disabled anything). The cache
    # clear below still runs when the delay is disabled.
    _delay = float(configured_delay) if configured_delay > 0 else 0.0
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            log_fn(
                f"    🧹 VRAM recovery{' (' + context + ')' if context else ''} "
                f"— cache cleared"
                + (f", waiting {_delay:.0f}s…" if _delay > 0 else " (delay disabled)"),
                "DEBUG",
            )
        else:
            log_fn(
                f"    🧹 VRAM recovery{' (' + context + ')' if context else ''} "
                f"— no CUDA"
                + (f", waiting {_delay:.0f}s…" if _delay > 0 else " (delay disabled)"),
                "DEBUG",
            )
    except Exception as _e:
        # V18.2.14 (B4): was silent ``pass`` — now traceable.
        log_swallow("vram_recovery_cuda_clear", _e, detail=f"context={context}")
    if _delay > 0:
        try:
            time.sleep(_delay)
        except Exception as _e:
            # V18.2.14 (B4): was silent ``pass`` — now traceable.
            log_swallow("vram_recovery_sleep", _e, detail=f"delay={_delay}")


__all__ = ["recover_vram"]
