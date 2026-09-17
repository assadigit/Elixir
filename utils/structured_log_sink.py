"""V18.10 (Phase 6.1): Structured-log sink — optional JSON when settings.observability.structured=true.

This module wraps the existing ``StructuredJsonFormatter`` (V10.4.0) with a
settings gate. When ``observability.structured`` is ``False`` (the default),
the JSONL handler is NOT attached — only the human-readable log is written.
When ``True``, the JSONL handler is attached alongside the human log.

**Why a separate module**: The existing ``utils/logging.py`` always attaches
the JSONL handler. This module provides the gated version
(``setup_main_logger_gated``) that respects the setting. The non-gated
``setup_main_logger`` remains for backward compatibility.

Usage::

    from utils.structured_log_sink import setup_main_logger_gated
    setup_main_logger_gated(structured=settings.get("observability.structured", False))

Or via the settings helper::

    from utils.structured_log_sink import is_structured_logging_enabled
    if is_structured_logging_enabled():
        # emit structured fields
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.settings import Settings

__all__ = [
    "is_structured_logging_enabled",
    "setup_main_logger_gated",
    "StructuredJsonFormatter",
]


def is_structured_logging_enabled() -> bool:
    """Check if structured JSON logging is enabled in settings.

    Returns ``True`` if ``settings.observability.structured`` is ``True``,
    ``False`` otherwise (including when the setting is missing).
    """
    try:
        return bool(Settings().get("observability.structured", False))
    except Exception:
        return False


def setup_main_logger_gated(structured: bool | None = None) -> logging.Logger:
    """Set up the main logger with optional structured JSONL handler.

    Args:
        structured: If ``None``, reads from ``settings.observability.structured``.
            If ``True`` or ``False``, overrides the setting.

    This is the V18.10 gated version of ``utils.logging.setup_main_logger``.
    The existing ``setup_main_logger`` (in ``utils/logging.py``) always
    attaches the JSONL handler — this version respects the setting.
    """
    from utils.logging import QueueHandler, StructuredJsonFormatter

    if structured is None:
        structured = is_structured_logging_enabled()

    log_dir = Path.home() / ".elixir"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "system.log"
    structured_log_file = log_dir / "structured.jsonl"

    logger = logging.getLogger("Elixir")
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Human-readable rotating file handler (always on).
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # V18.10 (Phase 6.1): Structured JSONL handler — gated by setting.
    if structured:
        json_handler = RotatingFileHandler(
            structured_log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        json_handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(json_handler)

    queue_handler = QueueHandler()
    queue_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )
    queue_handler.setFormatter(queue_formatter)
    logger.addHandler(queue_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    console.setFormatter(file_formatter)
    logger.addHandler(console)

    return logger
