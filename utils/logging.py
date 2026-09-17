"""
Logging system for Elixir.
Provides structured, verbose logging for all phases of conversion,
including per-chapter timings, token counts, and model usage.
"""

import json
import logging
import queue
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# ── Global queue for GUI callbacks ──────────────────────────────────────────
_log_queue: queue.Queue = queue.Queue()
_gui_callback: Callable[[str], None] | None = None


def set_gui_log_callback(callback: Callable[[str], None]) -> None:
    global _gui_callback
    _gui_callback = callback


def _emit_to_gui(message: str) -> None:
    if _gui_callback:
        _log_queue.put(message)


# ── Queue handler for GUI ──────────────────────────────────────────────────
class QueueHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _emit_to_gui(msg)


# ── Structured JSON formatter (V10.4.0 Phase 6B-1) ────────────────────────
# Emits one JSON object per log record, written to structured.jsonl alongside
# the human-readable system.log.  Machine-parseable for log aggregation,
# dashboards, and post-mortem analysis.  Existing human-readable handlers
# are untouched — both formats are written in parallel.
class StructuredJsonFormatter(logging.Formatter):
    """Formats a LogRecord as a single-line JSON object.

    Fields: ts, level, logger, msg, module, func, line, plus any non-standard
    attributes the caller attached to the record (via ``logger.info(msg,
    extra={...})``) under the ``extra`` key.
    """

    # Standard LogRecord attributes that should NOT be folded into ``extra``.
    _STD_ATTRS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # Ensure record.message is populated.
        record.message = record.getMessage()
        payload: dict[str, Any] = {
            # V18.2.24 (Phase 4.2): use timezone-aware datetime (was
            # utcfromtimestamp, deprecated in 3.12 + removed in 3.15).
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        # Fold non-standard attributes into ``extra``.
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._STD_ATTRS and not k.startswith("_")
        }
        if extras:
            payload["extra"] = extras
        # Include exception info if present.
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_structured_logger(name: str = "Elixir") -> logging.Logger:
    """Return a logger that emits structured JSON to ``structured.jsonl``.

    The JSONL handler is attached to the root ``Elixir`` logger by
    ``setup_main_logger()``; child loggers (``Elixir.core.summariser``,
    etc.) inherit it automatically.  This helper is the canonical entry point
    for new code that wants structured logging::

        from utils.logging import get_structured_logger
        slog = get_structured_logger(__name__)
        slog.info("chapter summarised", extra={"chapter": 3, "tokens": 1200})

    The ``extra`` dict is folded into the JSON record under the ``extra`` key.
    """
    logger = logging.getLogger(name)
    if not logging.getLogger("Elixir").handlers:
        setup_main_logger()
    return logger


# ── Main logger setup ──────────────────────────────────────────────────────
def setup_main_logger() -> logging.Logger:
    log_dir = Path.home() / ".elixir"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "system.log"
    structured_log_file = log_dir / "structured.jsonl"

    logger = logging.getLogger("Elixir")
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Human-readable rotating file handler.
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # V10.4.0 (Phase 6B-1): Structured JSONL handler — machine-parseable.
    # Writes alongside system.log.  Rotating 10MB x 5 (same as the human log).
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

    # V13.28.0 (P2.11): Apply per-module log levels after setup
    try:
        apply_module_log_levels()
    except Exception:
        pass  # don't crash if settings aren't available yet

    return logger


# ── V13.28.0 (P2.11): Per-module log levels ────────────────────────────────

# Default per-module log levels. Each key is a logger name suffix (matched
# against the full logger name). The first match wins. If no match, the root
# logger's level (DEBUG) is used.
#
# Users can override these via settings: logging.module_levels (a dict of
# module_name → level_string, e.g. {"packets": "DEBUG", "ocr": "WARNING"}).
_DEFAULT_MODULE_LEVELS: dict[str, str] = {
    "packets": "INFO",           # packets generation — verbose by default
    "summarizer": "INFO",        # summarization pipeline
    "bullet_pipeline": "INFO",   # anti-hallucination layers
    "content_judge": "INFO",     # grounding checks
    "keypoints_builder": "INFO", # keypoints generation
    "ocr": "WARNING",            # OCR — can be noisy (per-page logs)
    "translation": "INFO",       # translation pipeline
    "tts": "WARNING",            # TTS — can be noisy
    "converter": "INFO",         # main pipeline
    "vram_calculator": "WARNING",# VRAM budget (only log warnings)
    "checkpoint": "INFO",        # checkpoint/resume
    "dedup_service": "INFO",     # dedup passes
    "quarantine": "INFO",        # quarantine system
    "llm_provider": "INFO",      # LLM provider
}

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def apply_module_log_levels(settings_overrides: dict[str, str] | None = None) -> None:
    """V13.28.0 (P2.11): Apply per-module log levels.

    Reads from ``settings_overrides`` (if provided) or from
    ``Settings().get("logging.module_levels", {})``.

    For each module, sets the log level on the corresponding Python logger.
    Module names are matched as suffixes of the full logger name:
    - "packets" matches "Elixir.core.outputs.packets"
    - "summarizer" matches "Elixir.core.summarisation.summarizer"

    This lets the user crank up packets logging (DEBUG) while silencing OCR
    noise (WARNING) during debugging.
    """
    try:
        from utils.settings import Settings
        s = Settings()
        user_levels = settings_overrides or s.get("logging.module_levels", {})
    except Exception:
        user_levels = settings_overrides or {}

    # Merge defaults with user overrides (user wins)
    levels = dict(_DEFAULT_MODULE_LEVELS)
    levels.update(user_levels)

    # Apply levels to existing loggers + store for future loggers
    for module_suffix, level_str in levels.items():
        level = _LEVEL_MAP.get(level_str.upper(), logging.INFO)
        # Set on any existing logger that ends with this suffix
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.endswith(module_suffix) or module_suffix in name:
                logging.getLogger(name).setLevel(level)
        # Also set on the short name (e.g. "packets" → "Elixir.packets")
        logging.getLogger(f"Elixir.{module_suffix}").setLevel(level)

    # Log what we did (at DEBUG so it doesn't spam)
    root = logging.getLogger("Elixir")
    if root.handlers:
        root.debug(f"Per-module log levels applied: {levels}")


def get_module_level(module_name: str) -> int:
    """V13.28.0 (P2.11): Get the effective log level for a module.

    Returns the level that WOULD be applied if apply_module_log_levels()
    were called. Useful for debugging "why isn't my log showing?"
    """
    for suffix, level_str in _DEFAULT_MODULE_LEVELS.items():
        if module_name.endswith(suffix) or suffix in module_name:
            return _LEVEL_MAP.get(level_str.upper(), logging.INFO)
    return logging.DEBUG  # root level


def get_main_logger() -> logging.Logger:
    logger = logging.getLogger("Elixir")
    if not logger.handlers:
        setup_main_logger()
    return logger


# ── ConversionLogger (existing, enhanced) ──────────────────────────────
class ConversionLogger:
    """Writes the per-book conversion log + JSONL diagnostics.

    V7.5.1: logs now go to ``output/{book}/logs/`` (the V7.5.0 subfolder
    layout) instead of the legacy ``conversion_logs/``.  For backward
    compatibility, if a ``conversion_logs/`` dir already exists from a
    resumed V7.4 run, it's left in place — the new log just starts fresh
    in ``logs/``.
    """

    def __init__(self, output_dir: Path, base_filename: str):
        self.output_dir = Path(output_dir)
        self.base_filename = base_filename
        # V7.5.1: use the logs/ subfolder (created by OutputPaths).
        # Fall back to conversion_logs/ if that's where an existing log lives
        # (resume scenario from V7.4).
        new_log_dir = self.output_dir / "logs"
        legacy_log_dir = self.output_dir / "conversion_logs"
        if legacy_log_dir.exists() and not new_log_dir.exists():
            self.log_dir = legacy_log_dir
        else:
            self.log_dir = new_log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{base_filename}.conversion.log.md"
        self.diagnostic_path = self.log_dir / f"{base_filename}.diagnostic.jsonl"
        self._file_handle = None
        self._diag_handle = None
        self._open()

    def _open(self) -> None:
        self._file_handle = open(self.log_path, "w", encoding="utf-8")
        self._file_handle.write(f"# Conversion Log: {self.base_filename}\n\n")
        self._file_handle.write(f"Started at: {datetime.now().isoformat()}\n\n")
        self._file_handle.write("---\n\n")

        # V10.25.0: Don't create the diagnostic.jsonl file upfront.
        # Only create it when log_diagnostic() is actually called.
        self._diag_handle = None
        self._diag_path = self.diagnostic_path
        self.diagnostic_path = None  # will be set when first diagnostic is written

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] [{level}] {message}"
        if self._file_handle:
            self._file_handle.write(f"{full_msg}\n\n")
            self._file_handle.flush()
        main_logger = get_main_logger()
        log_level = getattr(logging, level.upper(), logging.INFO)
        main_logger.log(log_level, message)

    def log_diagnostic(self, data: dict[str, Any]) -> None:
        """Write a structured diagnostic entry as JSON Lines."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            **data
        }
        # V10.25.0: Create the diagnostic file lazily (only when first
        # diagnostic is written — prevents empty .jsonl files).
        if self._diag_handle is None and hasattr(self, "_diag_path") and self._diag_path:
            self._diag_handle = open(self._diag_path, "w", encoding="utf-8")
            self.diagnostic_path = self._diag_path
        if self._diag_handle:
            self._diag_handle.write(json.dumps(entry) + "\n")
            self._diag_handle.flush()

    def close(self) -> None:
        if self._file_handle:
            self._file_handle.write(f"\n---\nFinished at: {datetime.now().isoformat()}\n")
            self._file_handle.close()
            self._file_handle = None
        if self._diag_handle:
            self._diag_handle.close()
            self._diag_handle = None


# ── Timing context manager ────────────────────────────────────────────────
@contextmanager
def measure_time(name: str, logger: ConversionLogger, **extra):
    """Context manager to measure duration of a block and log it."""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        entry = {
            "phase": name,
            "duration_seconds": round(duration, 2),
            **extra
        }
        logger.log_diagnostic(entry)
        logger.log(f"⏱️ {name} took {duration:.2f}s", "DEBUG")


# ── Setup at module load ──────────────────────────────────────────────────
setup_main_logger()
