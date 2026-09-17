"""V18.2.26 (Phase 5.1 / A12) — Structured per-stage progress model.

The problem
-----------
The existing progress callback is ``Callable[[float, str], None]`` — a
fraction (0.0-1.0) + a free-text message ("Chapter 3/12 – processing"). The
UI shows aggregate progress but no per-stage breakdown (exec vs thorough vs
gap-fill vs grounding vs self-review). A chapter's pipeline has 5-10 LLM
stages; the user has no visibility into which stage is running or how long
each takes.

The fix (Phase 5.1)
-------------------
A structured ``ProgressEvent`` dataclass with ``stage``, ``chapter``,
``chapter_total``, ``pct``, and ``message``. Emitted by the summarizer at
each phase boundary. The existing float+str callback is preserved for
backward compatibility — ``ProgressEvent.to_legacy()`` converts to the
old (fraction, message) tuple.

Design: backward-compatible, additive
-------------------------------------
The existing ``progress_callback(float, str)`` signature is unchanged. The
new structured events are emitted via an OPTIONAL second callback
(``stage_callback``) so the UI can opt-in to the richer signal. Old UI code
keeps working; new UI code can render a multi-segment progress bar.

Book-agnostic (Key Decision #3): stage names are structural, not content.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ProgressEvent:
    """A structured progress event emitted at a pipeline phase boundary.

    Attributes:
        stage: the pipeline stage name. One of the STAGE_* constants below.
        chapter: 1-based chapter index (or 0 for book-level events).
        chapter_total: total number of chapters.
        pct: 0.0-1.0 fraction of THIS stage's expected work complete
            (usually 0.0 at start, 1.0 at end). For stage-level granularity.
        overall_pct: 0.0-1.0 fraction of the WHOLE conversion complete
            (book-level progress, what the existing float callback reports).
        message: human-readable message for the legacy log/UI.
        elapsed_sec: optional wall-clock time for this stage (set on completion).
    """

    stage: str
    chapter: int = 0
    chapter_total: int = 0
    pct: float = 0.0
    overall_pct: float = 0.0
    message: str = ""
    elapsed_sec: float = 0.0

    def to_legacy(self) -> tuple[float, str]:
        """Convert to the legacy (fraction, message) callback signature."""
        return (self.overall_pct, self.message or self.stage)

    def to_dict(self) -> dict:
        """Serialize to a dict (for JSON logging / structured.jsonl)."""
        return {
            "stage": self.stage,
            "chapter": self.chapter,
            "chapter_total": self.chapter_total,
            "pct": round(self.pct, 3),
            "overall_pct": round(self.overall_pct, 3),
            "message": self.message,
            "elapsed_sec": round(self.elapsed_sec, 1),
        }


# ── Stage name constants (structural, not content) ────────────────────────

# Book-level stages (chapter == 0)
STAGE_PDF_ANALYSIS = "pdf_analysis"
STAGE_SEGMENTATION = "segmentation"
STAGE_OCR = "ocr"
STAGE_BOOK_SUMMARY = "book_summary"

# Chapter-level stages (chapter >= 1)
STAGE_CHAPTER_START = "chapter_start"
STAGE_PRIMARY_SUMMARY = "primary_summary"          # the main LLM call
STAGE_COVERAGE_CHECK = "coverage_check"            # _compute_coverage
STAGE_3TIER_GUARANTEE = "3tier_guarantee"          # _apply_3tier_coverage
STAGE_BULLET_VERIFY = "bullet_verify"              # _verify_bullets
STAGE_ADDITIVE_SECTIONS = "additive_sections"      # _ensure_additive_sections
STAGE_THOROUGH_FOLLOWUP = "thorough_followup"      # _build_thorough_followup
STAGE_CONTENT_JUDGE = "content_judge"              # ContentJudge.judge
STAGE_SCHOLAR_REFLECTION = "scholar_reflection"    # _scholar_reflection
STAGE_SEMANTIC_DEDUP = "semantic_dedup"            # _semantic_dedup_bullets
STAGE_CONSOLIDATION = "consolidation"              # _consolidate_bullets
STAGE_GAP_FILL = "gap_fill"                        # _gap_fill_concepts
STAGE_POSTCHECKS = "postchecks"                    # run_postchecks
STAGE_CHAPTER_COMPLETE = "chapter_complete"

# Output stages
STAGE_KEYPOINTS = "keypoints"
STAGE_DOCX = "docx"


class ProgressEmitter:
    """Emits structured progress events + legacy float callbacks.

    Usage::

        emitter = ProgressEmitter(
            progress_callback=existing_float_str_callback,
            stage_callback=optional_new_structured_callback,
            total_chapters=12,
        )
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=3, pct=0.0)
        # ... do the LLM call ...
        emitter.emit_stage(STAGE_PRIMARY_SUMMARY, chapter=3, pct=1.0, elapsed_sec=45.2)

    The legacy ``progress_callback`` is always called (backward compat).
    The ``stage_callback`` is called only if provided (opt-in structured UI).
    """

    def __init__(
        self,
        progress_callback: Callable[[float, str], None] | None = None,
        stage_callback: Callable[[ProgressEvent], None] | None = None,
        total_chapters: int = 0,
    ) -> None:
        self._legacy = progress_callback
        self._stage_cb = stage_callback
        self._total = max(1, total_chapters)  # avoid div-by-zero
        self._completed_chapters = 0
        self._current_chapter = 0
        self._current_stage = ""

    @property
    def total_chapters(self) -> int:
        return self._total

    def emit_stage(
        self,
        stage: str,
        *,
        chapter: int = 0,
        pct: float = 0.0,
        message: str = "",
        elapsed_sec: float = 0.0,
    ) -> ProgressEvent:
        """Emit a structured progress event + the legacy float callback.

        Args:
            stage: one of the STAGE_* constants.
            chapter: 1-based chapter index (0 for book-level).
            pct: 0.0-1.0 fraction of THIS stage complete.
            message: human-readable message (defaults to the stage name).
            elapsed_sec: wall-clock seconds for this stage (on completion).

        Returns:
            The ProgressEvent that was emitted (for logging/testing).
        """
        if chapter > 0:
            self._current_chapter = chapter
        self._current_stage = stage

        # Compute overall_pct: completed chapters + fraction of current.
        # Within a chapter, assume 8 major stages (rough weighting).
        stage_weights = {
            STAGE_PRIMARY_SUMMARY: 0.30,      # the main LLM call is the biggest
            STAGE_COVERAGE_CHECK: 0.05,
            STAGE_3TIER_GUARANTEE: 0.10,
            STAGE_CONTENT_JUDGE: 0.10,
            STAGE_SCHOLAR_REFLECTION: 0.15,
            STAGE_SEMANTIC_DEDUP: 0.05,
            STAGE_CONSOLIDATION: 0.10,
            STAGE_POSTCHECKS: 0.05,
            STAGE_GAP_FILL: 0.10,
        }
        stage_weight = stage_weights.get(stage, 0.05)
        chapter_progress = pct * stage_weight  # fraction of this stage's weight
        overall = (
            (self._completed_chapters + chapter_progress) / self._total
            if chapter > 0
            else (self._completed_chapters / self._total) + pct * 0.01
        )
        overall = min(1.0, max(0.0, overall))

        event = ProgressEvent(
            stage=stage,
            chapter=chapter,
            chapter_total=self._total,
            pct=pct,
            overall_pct=overall,
            message=message or stage,
            elapsed_sec=elapsed_sec,
        )

        # Always call the legacy callback (backward compat).
        if self._legacy:
            try:
                frac, msg = event.to_legacy()
                self._legacy(frac, msg)
            except Exception:
                pass  # never let progress emission crash the pipeline

        # Call the structured callback (opt-in).
        if self._stage_cb:
            try:
                self._stage_cb(event)
            except Exception:
                pass

        return event

    def mark_chapter_complete(self, chapter: int) -> ProgressEvent:
        """Mark a chapter as fully complete (advances the completed count)."""
        self._completed_chapters = chapter
        return self.emit_stage(
            STAGE_CHAPTER_COMPLETE,
            chapter=chapter,
            pct=1.0,
            message=f"Chapter {chapter}/{self._total} complete",
        )

    def summary(self) -> str:
        """Human-readable progress summary for logging."""
        return (
            f"ProgressEmitter(completed={self._completed_chapters}/{self._total}, "
            f"current_chapter={self._current_chapter}, current_stage={self._current_stage})"
        )
