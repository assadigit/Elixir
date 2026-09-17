"""V10.9.0 (Phase 8D): Segmentation phase — extracted from converter.convert().

Contains the chapter/chunk segmentation pipeline that runs as Step 5 of
the conversion, after extraction (Steps 1–4) and post-processing (which
refines the raw markdown):

  - Extract page markers from the raw markdown (for page-range tracking)
  - Pre-locate TOC headings in the markdown (if TOC entries exist) via
    ``TocExtractor.locate_headings``
  - Run the ``Segmenter`` to split the markdown into chapters/chunks
  - Update page markers after segmentation (segments may span pages)
  - Fallback: if no segments, create a single segment covering the whole
    document
  - Filter segments by selected chapters (exact match → loose keyword
    match → keep all if no matches)
  - Log per-segment token counts (flags SHORT segments < 150 tokens)

Returns a :class:`SegmentationResult` (segments + page_markers + total_pages)
on success, or a :class:`ConversionResult` (success=False) on early exit
(user cancel during segmentation).

Extracted into its own module so the converter's ``convert()`` method is
shorter and the segmentation logic is testable independently.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.models import ConversionResult, Segment
from core.pdf import TocExtractor
from core.postprocess.page_marker import (
    extract_page_markers,
    update_page_markers_after_segmentation,
)
from core.segmentation import Segmenter

logger = logging.getLogger(__name__)


@dataclass
class SegmentationResult:
    """The state produced by the segmentation phase.

    Fields:
        segments: the list of Segment objects (chapters/chunks).
        page_markers: the page-marker list (used by validation later).
        total_pages: the total page count from the analysis (used by
            frontmatter, checkpoint, validation, and screenshots).
    """
    segments: list[Segment]
    page_markers: list
    total_pages: int


def run_segmentation(
    converter: Any,
    raw_markdown: str,
    analysis: Any,
    toc_entries: list,
) -> SegmentationResult | ConversionResult:
    """Run the segmentation phase (Step 5).

    # V13.33.0: Version verification — log the actual code path being used
    try:
        from pathlib import Path as _P
        _version_file = _P(__file__).resolve().parent.parent.parent.parent / "VERSION"
        if _version_file.exists():
            _version = _version_file.read_text().strip()
            log(f"  [Segmentation] Code version: {_version} (segmentation.py)", "DEBUG")
    except Exception:
        pass

    Args:
        converter: the Converter instance (accessed for ``self.request``,
            ``self._log``, ``self._update_status``, ``self._update_progress``,
            ``self.cancel_event``, ``self._match_chapter``).
        raw_markdown: the post-processed markdown text to segment.
        analysis: the PdfAnalysisResult (has ``total_pages``).
        toc_entries: the TOC entries from the extraction phase (list of
            (heading, page) tuples, may be empty).

    Returns:
        ``SegmentationResult`` on success — the caller unpacks it and
        continues to the output-saving phase.

        ``ConversionResult`` (success=False) on early exit — the caller
        returns it immediately.  Early exit happens when the user cancels
        during segmentation.
    """
    log = converter._log
    update_status = converter._update_status
    update_progress = converter._update_progress
    request = converter.request

    update_status("Detecting chapters…")
    update_progress(0.22)  # Segmentation phase

    total_pages = analysis.total_pages
    page_markers = extract_page_markers(raw_markdown)

    # ── FIX: Sort markers to ensure binary search works ─────────────
    page_markers.sort(key=lambda x: x[1])

    # ── Pre-locate headings if we have TOC entries ──────────────────
    # V10.9.0: recreate the TocExtractor here (the extraction phase
    # created one to extract the TOC; we need one here to locate the
    # headings in the markdown).  TocExtractor is stateless — creating
    # a second instance is cheap and keeps this module self-contained
    # (no need to thread the extractor through ExtractionResult).
    toc_result = None
    if toc_entries:
        # V13.32.12: Skip LLM heading labeler when the PDF has native outlines.
        # The PDF's native outline (the sidebar TOC that PDF readers show) is
        # authoritative — 100% accurate page numbers, set by the publisher.
        # Even if the outline is FLAT (all level 0, no hierarchy), it still
        # contains the correct chapter boundaries. The LLM labeler only adds
        # noise (author names, sub-sections) that fragments chapters.
        # The old check only skipped when levels > 0 (hierarchy present).
        # Now we skip whenever we have ANY TOC entries from the PDF outline
        # (which means the PDF has native outlines — the extraction phase
        # already logged "Using PDF outlines: N entries").
        _has_native_outlines = len(toc_entries) >= 2
        if _has_native_outlines:
            log(
                f"  [Converter] PDF has {len(toc_entries)} native outline entries "
                f"\u2014 skipping LLM heading labeler (outlines are authoritative). "
                f"The 3-Layer chapter-level segmentation will use these directly.",
                "INFO"
            )
            toc_result = None
        else:
            log("  [Converter] Pre‑locating TOC headings in markdown…", "INFO")
            toc_extractor = TocExtractor(log_callback=log)
            toc_result = toc_extractor.locate_headings(
                toc_entries,
                raw_markdown,
                page_markers,
            )
            if toc_result and toc_result.entries:
                located = sum(1 for e in toc_result.entries if e.is_heading_found)
                log(f"  [Converter] Located {located}/{len(toc_result.entries)} headings (confidence: {toc_result.confidence:.2f})", "INFO")
                for e in toc_result.entries[:3]:
                    log(f"    - '{e.title[:40]}' → line {e.line} (conf: {e.confidence:.2f})", "DEBUG")

                # V10.12.9: Ultra-Precise TOC — if the fuzzy locate_headings
                # failed to find most headings (confidence < 0.50 or located <
                # 50%), fall back to LLM-based heading labeling.  This handles
                # OCR-mangled text where the heading text doesn't match the
                # TOC entries exactly.  The LLM can recognize headings even
                # when they're slightly mangled.
                if toc_result.confidence < 0.50 or located < len(toc_result.entries) * 0.5:
                    log(
                        f"  🎯 Ultra-Precise TOC: fuzzy matching found only "
                        f"{located}/{len(toc_result.entries)} headings — trying "
                        f"LLM-based heading labeling…",
                        "INFO",
                    )
                    try:
                        from core.pdf.llm_heading_labeler import label_headings_with_llm
                        _llm_headings = label_headings_with_llm(
                            raw_markdown=raw_markdown,
                            page_markers=page_markers,
                            model=request.summarisation_model,
                            log_callback=log,
                        )
                        if _llm_headings and len(_llm_headings) >= 3:
                            log(
                                f"  ✅ Ultra-Precise TOC: LLM labeled "
                                f"{len(_llm_headings)} headings — using these "
                                f"instead of fuzzy-matched TOC",
                                "INFO",
                            )
                            # Replace the toc_entries with the LLM-labeled headings
                            toc_entries = _llm_headings
                            toc_result = None  # force the segmenter to use raw entries
                    except Exception as _e:
                        log(f"  ⚠️ Ultra-Precise TOC failed: {_e}", "DEBUG")
            else:
                log("  [Converter] TOC location failed – will use fallback segmentation.", "WARNING")
                # V10.12.9: Even if we have no TOC result, try LLM labeling
                # if we have TOC entries (the segmenter can use them directly)
                if toc_entries and len(toc_entries) >= 3:
                    log(
                        "  🎯 Ultra-Precise TOC: trying LLM-based heading labeling…",
                        "INFO",
                    )
                    try:
                        from core.pdf.llm_heading_labeler import label_headings_with_llm
                        _llm_headings = label_headings_with_llm(
                            raw_markdown=raw_markdown,
                            page_markers=page_markers,
                            model=request.summarisation_model,
                            log_callback=log,
                        )
                        if _llm_headings and len(_llm_headings) >= 3:
                            log(
                                f"  ✅ Ultra-Precise TOC: LLM labeled "
                                f"{len(_llm_headings)} headings",
                                "INFO",
                            )
                            toc_entries = _llm_headings
                            toc_result = None
                    except Exception as _e:
                        log(f"  ⚠️ Ultra-Precise TOC failed: {_e}", "DEBUG")

    # Pass the TOC result (or raw entries) to the segmenter
    segmenter = Segmenter(
        request,
        log_callback=log,
        toc_entries=toc_result if toc_result else toc_entries,
    )
    segments = segmenter.segment(raw_markdown, total_pages, page_markers)

    if converter.cancel_event.is_set():
        return ConversionResult(success=False, error_msg="Cancelled by user")

    segments = update_page_markers_after_segmentation(segments, page_markers)

    if not segments:
        log("⚠️ No segments — creating single fallback", "WARNING")
        segments = [Segment(
            heading=request.input_path.stem.replace("_", " ").title(),
            content=raw_markdown, start_page=1, end_page=total_pages, segment_type="chunk",
        )]

    # Release raw_markdown — segments now hold their own content copies.
    # This frees 50-100K chars of memory for the summarization phase.
    # NOTE: the caller (converter) owns raw_markdown; we can't del it
    # here.  The converter dels it after this function returns.

    # ── ENHANCED: Filter segments by selected chapters ──────────────
    # V18.3.3 (F4): use the unified ChapterMatcher — SAME matcher as Stage 2.
    # Before V18.3.3, Stage 1 used loose word-substring matching while Stage 2
    # used strict _match_chapter — the inconsistency caused silent failures
    # (Stage 1 kept segments Stage 2 rejected). Now both stages agree.
    if request.selected_chapters and len(request.selected_chapters) > 0:
        selected_list = request.selected_chapters
        original_count = len(segments)
        log(f"  🔍 Chapter selection: {len(selected_list)} titles selected.", "DEBUG")
        log(f"     Selected: {selected_list[:3]}{'…' if len(selected_list) > 3 else ''}", "DEBUG")

        from core.segmentation.chapter_matcher import ChapterMatcher
        _toc_entries = getattr(converter, "toc_entries", []) or []
        _matcher = ChapterMatcher(toc_entries=_toc_entries)
        # Convert segments to dicts for the matcher (it works with dicts)
        _seg_dicts = [
            {
                "heading": s.heading,
                "start_page": getattr(s, "start_page", None),
                "end_page": getattr(s, "end_page", None),
                "aliases": getattr(s, "aliases", None) or [],
                "segment_type": getattr(s, "segment_type", ""),
            }
            for s in segments
        ]
        _matched = _matcher.match(selected_list, _seg_dicts)
        _matched_headings = set()
        for _score, _sd in _matched:
            _matched_headings.add(_sd["heading"])
        filtered_segments = [s for s in segments if s.heading in _matched_headings]

        if filtered_segments:
            segments = filtered_segments
            log(f"  📑 Filtered segments: kept {len(segments)} of {original_count}", "INFO")
        else:
            log(f"  ⚠️ No matches found (heading + aliases + page); keeping all {original_count} segments.", "WARNING")

    return SegmentationResult(
        segments=segments,
        page_markers=page_markers,
        total_pages=total_pages,
    )


def log_segment_summary(
    converter: Any,
    segments: list[Segment],
    elapsed: str = "",
) -> None:
    """Log the per-segment token-count summary.

    Extracted as a separate function because it needs ``_elapsed()`` (a
    closure-local timer in convert()) that isn't accessible from
    :func:`run_segmentation`.  The converter calls this after unpacking
    the SegmentationResult + deleting raw_markdown.
    """
    log = converter._log
    suffix = f" | [{elapsed}]" if elapsed else ""
    log(f"📚 {len(segments)} segment(s) detected{suffix}", "INFO")
    from utils.token_counter import count_tokens as _ct
    for _si, _seg in enumerate(segments, 1):
        _tok = _ct(_seg.content)
        _flag = "⚠️ SHORT" if _tok < 150 else "✅"
        log(
            f"  {_flag} Seg {_si}/{len(segments)}: "
            f"'{_seg.heading[:45]}' | {_tok:,} tokens | "
            f"p.{_seg.start_page}–{_seg.end_page}", "DEBUG"
        )
