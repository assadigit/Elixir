"""V18.2.18 (B3/M3): ConversionContext — a typed interface for the Converter.

WHY THIS EXISTS
---------------
The Phase modules (extraction, segmentation, summarization, postprocess,
output_save, output_runner) all take ``converter: Any`` and reach into its
attributes. This is implicit coupling — there's no interface, no contract,
and no type checking. The audit (B3, M3) flagged this as a maintainability
smell that blocks the god-class refactor (Phase 5 / M1).

This module defines a :class:`ConversionContext` Protocol (structural
typing) that declares the attributes + methods the phase modules actually
access. The existing ``Converter`` class already satisfies this Protocol
(structural — no inheritance needed). Phase modules can now declare their
parameter as ``converter: ConversionContext`` instead of ``converter: Any``,
giving them:

  - IDE autocompletion for converter attributes
  - mypy type checking (when strict is tightened)
  - A documented contract of what the phase needs

MIGRATION
---------
This is a **gradual migration**. The Protocol is defined here but the phase
modules still take ``converter: Any`` (to avoid breaking the 100+ attribute
accesses in one shot). The migration path:

  1. V18.2.18 (this version): Define the Protocol + tighten mypy config.
  2. Future: Migrate phase modules one-by-one to ``converter: ConversionContext``
     (each migration is a mechanical type-annotation change).
  3. Phase 5 (god-class refactor): The Protocol makes it safe to split
     Converter into smaller classes — as long as they implement the Protocol,
     the phase modules don't break.

BOOK-AGNOSTIC
-------------
The Protocol is completely domain-agnostic — it describes conversion
plumbing (paths, settings, logging, progress), not any book content.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from core.models import ConversionRequest, ConversionResult


@runtime_checkable
class ConversionContext(Protocol):
    """Typed interface for the Converter, consumed by phase modules.

    The existing ``Converter`` class in ``core/pipeline/converter.py``
    already satisfies this Protocol (structural typing — no inheritance
    needed). Phase modules can declare their ``converter`` parameter as
    ``ConversionContext`` instead of ``Any`` for type safety + IDE support.

    Attributes are grouped by the phase that typically accesses them.
    """

    # ── Core request + output paths (all phases) ──────────────────────────
    request: ConversionRequest
    output_dir: Path
    settings: Any  # Settings singleton (kept as Any to avoid circular import)

    # ── Output path resolver (extraction, output_save) ─────────────────────
    paths: Any  # OutputPaths instance

    # ── Markdown file paths (extraction, postprocess, output_save) ────────
    full_markdown_path: Path
    temp_markdown_path: Path
    chapters_folder: Path
    chunks_folder: Path
    docx_path: Path
    summary_md_path: Path

    # ── Logging + progress (all phases) ───────────────────────────────────
    def _log(self, message: str, level: str = "INFO") -> None: ...
    def _update_progress(self, value: float) -> None: ...
    def _update_status(self, message: str) -> None: ...

    # ── Cancellation + threading (all phases) ─────────────────────────────
    cancel_event: threading.Event

    # ── Checkpoint + resume (output_runner, summarization) ────────────────
    checkpoint: Any  # CheckpointManager or None

    # ── Partial failures (all phases) ─────────────────────────────────────
    _partial_failures: list[str]

    def _record_partial_failure(self, subsystem: str, error: Exception) -> None: ...

    # ── Error result builder (all phases) ─────────────────────────────────
    def _build_error_result(self, error_msg: str, **kwargs: Any) -> ConversionResult: ...

    # ── Segment helpers (segmentation, summarization) ─────────────────────
    def _filter_segment_content(self, segment: Any) -> Any: ...
    def _match_chapter(self, heading: str, chapters: list[Any]) -> Any: ...
    def _sanitize_filename(self, name: str) -> str: ...

    # ── Summarization progress (summarization) ────────────────────────────
    def _summarisation_progress(self, value: float, message: str) -> None: ...

    # ── Thermal safety (summarization) ─────────────────────────────────────
    _thermal_safety: Any  # ThermalSafetyController or None


__all__ = ["ConversionContext"]
