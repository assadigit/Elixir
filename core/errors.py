"""V7.0.0: Unified error hierarchy for the conversion pipeline.

Every phase of the conversion (OCR, summarization, keypoints, outputs, TTS,
translation) catches its specific errors and raises the appropriate subclass.
The converter collects these in result.errors and presents them in the
completion modal — no more silent failures logged as DEBUG.

Usage::

    from core.errors import SummarizationError, TTSError

    try:
        generate_podcast(...)
    except TTSError as e:
        # logged as WARNING, added to result.errors
        result.add_error("podcast", str(e))
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

class ConversionError(Exception):
    """Base class for all conversion-related errors."""

    def __init__(self, message: str, phase: str = "unknown") -> None:
        super().__init__(message)
        self.phase = phase
        self.message = message


class OCRError(ConversionError):
    """Error during PDF text extraction or OCR."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="ocr")


class SegmentationError(ConversionError):
    """Error during chapter/segment detection."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="segmentation")


class SummarizationError(ConversionError):
    """Error during LLM summarization of a chapter."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="summarization")


class VramOverbudgetError(ConversionError):
    """V18.20.4.10 (P0-c): the pre-flight VRAM budget check determined the
    planned model(s) do not fit on the GPU and the configured policy says
    abort (``local.vram_overbudget_policy`` = "abort", or "ask" without an
    interactive acknowledgment). Raised by the converter BEFORE extraction
    so nothing is wasted — the alternative (warn-and-continue) is what let
    a 20.2 GB model start on a 12 GB card and stall for hours in the
    V18.20.4.9 97-Things incident."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="preflight")


class KeypointsError(ConversionError):
    """Error during keypoints extraction or classification."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="keypoints")


class SimplifiedKeypointsError(ConversionError):
    """Error during simplified keypoints generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="simplified_keypoints")


class DocxError(ConversionError):
    """Error during DOCX report generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="docx")


class OutputError(ConversionError):
    """Error during Output Studio generation (briefing, flashcards, etc.)."""

    def __init__(self, message: str, output_type: str = "") -> None:
        super().__init__(message, phase=f"output:{output_type}" if output_type else "output")
        self.output_type = output_type


class PodcastScriptError(OutputError):
    """Error during podcast script generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, output_type="podcast_script")


class TTSError(ConversionError):
    """Error during text-to-speech audio generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="tts")


class TranslationError(ConversionError):
    """Error during translation (NLLB or Ollama)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="translation")


class HarakatError(ConversionError):
    """Error during Persian harakat (diacritization) generation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="harakat")


class ValidationError(ConversionError):
    """Error during translation validation (back-translation + judge)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="validation")


class RAGError(ConversionError):
    """Error during RAG indexing."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="rag")


class ScreenshotError(ConversionError):
    """Error during screenshot capture."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="screenshots")


class ChapterMatchFailure(ConversionError):
    """V18.3.1 (P0 hotfix): User selected chapter(s) but 0 matched any segment.

    This is the **silent-failure guard**. Before V18.3.1, when the segmenter
    renamed chapters (e.g. "Chapter 2: Spotting" → "Part Two: Spy Skills")
    and ``_match_chapter`` returned False for every segment, the pipeline
    silently produced an empty summary and reported "✅ Conversion complete".

    Now this guard fires: if ``selected_chapters`` is non-empty but the matcher
    found 0 matches, the conversion ABORTS with this error instead of writing
    an empty file. The user sees an actionable message listing what they
    selected vs what segments exist.

    Non-retryable — the user must either (a) pick a chapter title that matches
    a segment heading, or (b) fix the segmenter (P3 — prefer TOC headings).
    """

    def __init__(self, message: str, selected: list = None, available: list = None) -> None:
        super().__init__(message, phase="summarization")
        self.selected = selected or []
        self.available = available or []
