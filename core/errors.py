"""V7.0.0: Error classes for the conversion pipeline (adopted subset).

The original V7.0.0 "unified hierarchy" defined 17 exception classes
(one per phase), but callers only ever adopted four — the other 13
(OCRError, SegmentationError, SummarizationError, KeypointsError,
SimplifiedKeypointsError, DocxError, OutputError, PodcastScriptError,
TTSError, TranslationError, HarakatError, RAGError, ScreenshotError)
had zero references repo-wide since introduction and were removed in
the V0.4.25 Phase-4 dead-code audit (phases report their failures via
``result.errors`` / logging instead of raising typed subclasses).

The converter collects instances of these classes in ``result.errors``
and presents them in the completion modal — no silent failures logged
as DEBUG.

Usage::

    from core.errors import ChapterMatchFailure

    try:
        ...
    except ChapterMatchFailure as e:
        # logged as WARNING, added to result.errors
        result.add_error("summarization", str(e))
"""

from __future__ import annotations


class ConversionError(Exception):
    """Base class for all conversion-related errors."""

    def __init__(self, message: str, phase: str = "unknown") -> None:
        super().__init__(message)
        self.phase = phase
        self.message = message


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


class ValidationError(ConversionError):
    """Error during translation validation (back-translation + judge)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, phase="validation")


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
