"""V10.8.0 (Phase 8C): Extraction phase — extracted from converter.convert().

Contains the PDF analysis + OCR + markdown-building pipeline that runs
as Steps 1–4 of the conversion:

  Step 1: Analyse PDF (PdfAnalyzer → page classification + scanned detection)
  Step 2: Extract TOC (TocExtractor → chapter headings from the PDF's TOC)
  Step 3: Extract text (OCRService → markitdown for text pages, OlmOCR for
          scanned pages; respects page range + chapter selection)
  Step 4: Build raw markdown (OCRService.build_markdown → assemble pages
          into a single markdown string)

This is the first phase of the converter pipeline.  It produces the
``raw_markdown`` string that post-processing (Phase 8B) refines and
segmentation (Step 5) splits into chapters.

Returns an :class:`ExtractionResult` on success, or a
:class:`ConversionResult` (success=False) on early exit (0-page PDF or
user cancel).  The caller checks the return type and either unpacks the
result or returns the error immediately.

Extracted into its own module so the converter's ``convert()`` method is
shorter and the extraction logic is testable independently.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.models import ConversionResult, PdfRecommendation
from core.ocr.service import OCRService
from core.pdf import PdfAnalyzer, TocExtractor

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """The state produced by the extraction phase, consumed by later phases.

    Fields:
        raw_markdown: the assembled markdown text (input to post-processing).
        analysis: the PdfAnalysisResult (has total_pages, scanned_pages, etc.).
        pages_to_ocr: the list/set of page numbers that were OCR'd.
        effective_start_page: the first page in the effective range (after
            applying the user's page_range_start/end).
        effective_end_page: the last page in the effective range.
        effective_total_pages: the count of pages in the effective range
            (end - start + 1).  Used by output_save for frontmatter.
        toc_entries: the TOC entries (list of (heading, page) tuples), or [].
        valid_pages: the set of pages within selected chapters INCLUDING the
            ±1 boundary-overlap pages (or None if chapter selection is
            inactive → process ALL pages).
        selected_pages: the set of pages the user explicitly selected
            (manual page ranges or TOC-derived chapter ranges), BEFORE the
            ±1 boundary overlap is added.  V18.20.3.6: this is the honest
            "pages processed" count — the overlap pages are deduped in
            post-processing and never reach the output, so reporting the
            overlap-inflated set (or worse, the whole PDF's total) in the
            completion modal misleads (a 397-page book showed "397" for an
            18-page chapter run).  None when no selection is active.
    """
    raw_markdown: str
    analysis: Any
    pages_to_ocr: Any  # list or set
    effective_start_page: int
    effective_end_page: int
    effective_total_pages: int
    toc_entries: list
    valid_pages: set[int] | None
    selected_pages: set[int] | None = None


def expand_with_overlap(valid_pages: set[int], total_pages: int) -> set[int]:
    """Add ±1 boundary pages to a selected page set.

    Extracted from ``run_extraction`` (V18.20.3.6) so the boundary-overlap
    behaviour is unit-testable.  The overlap pages exist only so a chapter
    boundary never splits a sentence mid-way; they are deduped in
    post-processing and are NOT part of the user's selection.
    """
    overlap_pages = set()
    for p in valid_pages:
        if p > 1:
            overlap_pages.add(p - 1)
        if p < total_pages:
            overlap_pages.add(p + 1)
    return valid_pages | overlap_pages


def run_extraction(converter: Any) -> ExtractionResult | ConversionResult:
    """Run the extraction phase (Steps 1–4).

    Args:
        converter: the Converter instance (accessed for ``self.request``,
            ``self._log``, ``self._update_status``, ``self._update_progress``,
            ``self._get_user_override``, ``self._extract_covers``,
            ``self._derive_page_ranges_from_toc``, ``self.cancel_event``).

    Returns:
        ``ExtractionResult`` on success — the caller unpacks it and
        continues to the post-processing phase.

        ``ConversionResult`` (success=False) on early exit — the caller
        returns it immediately.  Early exits happen when:
          - the PDF has 0 pages (belt-and-suspenders; the analyzer's
            EmptyPdfError usually fires first), or
          - the user cancels during OCR.
    """
    log = converter._log
    update_status = converter._update_status
    update_progress = converter._update_progress
    request = converter.request

    # V10.22.1: Multi-format input — detect non-PDF files and route accordingly
    _input_suffix = Path(request.input_path).suffix.lower()
    if _input_suffix != ".pdf":
        from core.pipeline.multi_format_reader import extract_text, is_supported_format
        if not is_supported_format(Path(request.input_path)):
            return ConversionResult(
                success=False,
                error_msg=f"Unsupported format: {_input_suffix}. Supported: PDF, EPUB, DOCX, TXT, MD, HTML"
            )
        log(f"  📄 Non-PDF input ({_input_suffix}) — using multi-format reader.", "INFO")
        raw_text, page_count = extract_text(Path(request.input_path), request.password, log)
        if not raw_text:
            return ConversionResult(success=False, error_msg="Text extraction failed.")
        # Build synthetic analysis (all text pages, no scanned)
        from core.models import PageAnalysis, PdfAnalysisResult
        from core.models import PdfRecommendation as PR
        per_page = [PageAnalysis(page_num=i+1, is_scanned=False, extracted_text_preview="", recommended_action="skip") for i in range(page_count)]
        analysis = PdfAnalysisResult(total_pages=page_count, scanned_pages=[], text_pages=list(range(1, page_count+1)), recommendation=PR.NO_OCR, per_page=per_page)
        pages_to_ocr = []
        effective_total_pages = page_count
        effective_start_page = 1
        effective_end_page = page_count
        toc_entries = []
        valid_pages = None
        raw_markdown = raw_text
        log(f"  ✅ Extracted {len(raw_text):,} chars, ~{page_count} pages", "INFO")
        # Skip to Step 4 — build raw markdown (already done)
        update_progress(0.18)
        return ExtractionResult(
            raw_markdown=raw_markdown, analysis=analysis, pages_to_ocr=[],
            effective_start_page=1, effective_end_page=page_count,
            effective_total_pages=page_count, toc_entries=[], valid_pages=None,
            selected_pages=None,
        )

    # ── Step 1: Analyse PDF ──────────────────────────────────────────
    update_status("Analysing PDF…")
    update_progress(0.05)

    # V10.22.1: Differential re-run — check which pages changed
    try:
        from core.pipeline.page_diff import get_changed_pages
        _changed = get_changed_pages(Path(request.input_path), converter.output_dir)
        if _changed and len(_changed) < 100:  # only log if meaningful
            log(f"  📄 Differential: {len(_changed)} pages changed since last run.", "INFO")
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # V10.22.1: Docling — if available + academic, use for extraction
    _use_docling = False
    try:
        import docling  # noqa: F401
        if request.source_type == "academic_paper" and not request.force_ocr_all_pages:
            _use_docling = True
            log("  🔧 Docling available — using for technical PDF extraction (tables + code).", "INFO")
    except ImportError:
        pass

    analyzer = PdfAnalyzer(password=request.password)
    analysis = analyzer.analyze(request.input_path)
    override = converter._get_user_override(analysis)
    pages_to_ocr = analyzer.get_pages_to_ocr(analysis, override)

    # ── Apply page range filtering (if set) ──────────────────────────
    if request.page_range_start is not None or request.page_range_end is not None:
        start = request.page_range_start or 1
        end = request.page_range_end or analysis.total_pages
        # Clamp to valid range
        start = max(1, min(start, analysis.total_pages))
        end = max(start, min(end, analysis.total_pages))
        # Filter pages_to_ocr
        pages_to_ocr = [p for p in pages_to_ocr if start <= p <= end]
        # Store effective page range for later use
        effective_total_pages = end - start + 1
        effective_start_page = start
        effective_end_page = end
        log(f"  📄 Page range applied: {start}–{end} (effective pages: {effective_total_pages})", "INFO")
    else:
        effective_total_pages = analysis.total_pages
        effective_start_page = 1
        effective_end_page = analysis.total_pages

    if pages_to_ocr:
        log(
            f"📋 {len(pages_to_ocr)} scanned pages will be OCR'd: "
            f"{pages_to_ocr[:10]}{'…' if len(pages_to_ocr) > 10 else ''}", "INFO"
        )
    else:
        log("📄 All pages have extractable text — no OCR needed", "INFO")

    # Deterministic content-type auto-detection — replaces the old
    # scanned-only check with a full multi-signal detector.  Runs AFTER
    # extraction (when raw_markdown is available) but the early scan
    # check here catches the scanned-PDF case before OCR.  The full
    # detection runs later (after Step 4) when we have text.
    try:
        from core.llm.content_presets import detect_scanned_pdf
        if detect_scanned_pdf(len(pages_to_ocr), analysis.total_pages):
            log(
                f"  📋 Auto-detected scanned PDF ({len(pages_to_ocr)}/"
                f"{analysis.total_pages} pages scanned) — switching to "
                f"scanned_pdf preset",
                "INFO",
            )
            request.source_type = "scanned_pdf"
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # ── 0-page PDF guard (belt-and-suspenders; analyzer's EmptyPdfError
    # usually fires first, but this catches the edge case where the
    # analyzer returned a result without raising) ────────────────────
    if analysis.total_pages == 0:
        msg = "PDF has 0 pages — cannot convert."
        log(f"❌ {msg}", "ERROR")
        return ConversionResult(success=False, error_msg=msg)

    # ── Step 2: Extract TOC ──────────────────────────────────────────
    # V10.12.1 bugfix: TOC extraction moved BEFORE cover extraction.
    # ``_extract_covers`` needs ``toc_entries`` to screenshot selected-
    # chapter pages; previously covers were extracted before TOC existed,
    # and the method referenced a bare ``toc_entries`` that was never in
    # scope (NameError when selected_chapters was truthy).  Now TOC is
    # extracted first, then passed to _extract_covers as a parameter.
    update_status("Reading Table of Contents…")
    toc_extractor = TocExtractor(log_callback=log)
    toc_entries = toc_extractor.extract(
        request.input_path, request.password
    )
    if toc_entries:
        log(f"📑 TOC: {len(toc_entries)} entries found → will be used for chapter headings", "INFO")
        log(f"  [TOC] Entries passed to segmenter: {len(toc_entries)}", "DEBUG")
        for h, p in toc_entries[:3]:
            log(f"  [TOC] - p.{p}: {h[:40]}", "DEBUG")
        if len(toc_entries) > 3:
            log(f"  [TOC] … and {len(toc_entries) - 3} more", "DEBUG")

        # Log selected chapters with their TOC page numbers
        if request.selected_chapters:
            log(
                f"  🎯 User selected {len(request.selected_chapters)} chapter(s):",
                "INFO",
            )
            for sel in request.selected_chapters:
                _sel_norm = sel.strip().lower()
                _toc_page = None
                for _h, _p in toc_entries:
                    if _h.strip().lower() == _sel_norm:
                        _toc_page = _p
                        break
                if _toc_page:
                    log(f"    → '{sel[:50]}' (TOC page {_toc_page})", "INFO")
                else:
                    # Try partial match
                    for _h, _p in toc_entries:
                        if _sel_norm[:20] in _h.strip().lower():
                            _toc_page = _p
                            break
                    if _toc_page:
                        log(f"    → '{sel[:50]}' (TOC page {_toc_page}, partial match)", "INFO")
                    else:
                        log(f"    → '{sel[:50]}' (page unknown — not in TOC)", "WARNING")
    else:
        log("📑 TOC: not found — relying on heading detection only", "INFO")

    # ── Cover extraction (V10.12.1: moved after TOC so toc_entries is
    # available for the selected-chapter screenshot block) ───────────
    converter._extract_covers(analysis.total_pages, toc_entries=toc_entries)

    # ── Step 3: Extract text ─────────────────────────────────────────
    update_status(f"Extracting text — {len(pages_to_ocr)} page(s) need OCR…")
    update_progress(0.10)

    # A3 fix: Derive page ranges from TOC + selected_chapters if
    # manual_segments is not explicitly set. This ensures the OCR/text
    # extraction only processes selected chapter pages, skipping
    # unselected chapters entirely (massive time savings).
    total_pages_for_range = analysis.total_pages
    valid_pages: set | None = None  # None = process ALL pages

    if request.manual_segments:
        # User explicitly provided page ranges (from chapter selector)
        valid_pages = set()
        for seg_start, seg_end in request.manual_segments:
            for p in range(max(1, seg_start), min(total_pages_for_range + 1, seg_end + 1)):
                valid_pages.add(p)
        log(
            f"  📄 Chapter selection: {len(valid_pages)} pages in "
            f"{len(request.manual_segments)} range(s) "
            f"(skipping {total_pages_for_range - len(valid_pages)} unselected pages)",
            "INFO",
        )
    elif request.selected_chapters and toc_entries:
        # Derive page ranges from TOC entries matching selected chapters
        valid_pages = converter._derive_page_ranges_from_toc(
            toc_entries, request.selected_chapters, total_pages_for_range
        )
        if valid_pages:
            log(
                f"  📄 Derived {len(valid_pages)} pages from TOC for "
                f"{len(request.selected_chapters)} selected chapter(s) "
                f"(skipping {total_pages_for_range - len(valid_pages)} unselected pages)",
                "INFO",
            )

    # V18.20.3.6: snapshot the user's explicit selection BEFORE the ±1
    # boundary overlap is merged below.  This is the number the completion
    # modal reports as "Pages processed" (see compute_pages_processed in
    # converter_impl) — the overlap pages are context-only, deduped later.
    _selected_pages: set | None = (
        set(valid_pages) if valid_pages is not None else None
    )

    # If we have valid_pages (chapter selection active), filter
    # pages_to_ocr and pass to OCRService so it ONLY processes those pages.
    # Add ±1 page overlap to avoid splitting sentences at chapter
    # boundaries. The overlap pages are deduped in post-processing.
    if valid_pages is not None:
        valid_pages = expand_with_overlap(valid_pages, total_pages_for_range)
        # FIX: pages_to_ocr may be a list — convert to set for intersection
        pages_to_ocr_set = set(pages_to_ocr) if not isinstance(pages_to_ocr, set) else pages_to_ocr
        original_ocr_count = len(pages_to_ocr_set)
        pages_to_ocr_set = pages_to_ocr_set & valid_pages
        pages_to_ocr = sorted(pages_to_ocr_set)
        # Also filter the analysis pages
        if hasattr(analysis, "per_page"):
            analysis.per_page = [p for p in analysis.per_page if p.page_num in valid_pages]
        log(
            f"  📄 OCR pages filtered: {original_ocr_count} → {len(pages_to_ocr)} "
            f"(only scanning pages within selected chapters)",
            "INFO",
        )

    # V10.21.0: Docling integration — if docling is available and the
    # source is technical/academic, use it for text extraction (preserves
    # tables + code blocks that markitdown mangles).
    _docling_used = False
    try:
        import docling  # noqa: F401
        if request.source_type in ("academic_paper",) and not request.force_ocr_all_pages:
            log("  🔧 Docling available — will use for technical PDF extraction.", "INFO")
            _docling_used = True
            # When docling is available, don't force OlmOCR — let docling
            # extract tables/code, then only OlmOCR pages that are garbled
    except ImportError:
        pass

    # V10.14.0 (D1): Two-stage OCR for academic papers.
    # Scientific papers are typically two-column PDFs that markitdown
    # extracts with vertical column reading (garbled text).  Previously,
    # ALL pages were forced through OlmOCR (slow — 1 min/page).
    #
    # The two-stage approach:
    #   Stage 1: markitdown extracts all pages (fast — 1-2 sec/page)
    #   Stage 2: OlmOCR re-processes ONLY the garbled pages
    #
    # This is 5-10x faster on papers where most pages extract cleanly
    # (only the two-column pages need OlmOCR).  On papers where ALL pages
    # are garbled, it degrades gracefully to the old behavior (OlmOCR all).
    #
    # We can't do the garble-check here (markitdown hasn't run yet), so
    # we DON'T force all pages as scanned.  Instead, we let OCRService
    # run markitdown on all pages, and the postprocess phase (V10.7.0)
    # will detect garbled text and call _targeted_ocr_repair on just
    # those pages.
    #
    # The ONLY case where we still force OlmOCR on all pages is when
    # force_ocr_all_pages is explicitly True (user override).
    if getattr(request, "source_type", "") == "academic_paper" and not getattr(request, "force_ocr_all_pages", False):
        log(
            "  🔬 Academic paper detected — using two-stage OCR: "
            "markitdown first, OlmOCR only on garbled pages. "
            "(V10.14.0: was forcing OlmOCR on ALL pages — 5-10x slower).",
            "INFO",
        )
        # Don't force all pages as scanned — let markitdown try first.
        # The postprocess phase's targeted OCR repair will catch garbled pages.
    elif getattr(request, "source_type", "") == "academic_paper" and getattr(request, "force_ocr_all_pages", False):
        log(
            "  🔬 Academic paper + Force OCR All Pages — forcing OlmOCR on ALL pages.",
            "INFO",
        )
        # Mark all pages as scanned so OCRService uses OlmOCR
        _all_pages = list(range(1, analysis.total_pages + 1))
        if valid_pages:
            _all_pages = sorted(valid_pages)
        analysis.scanned_pages = _all_pages
        analysis.text_pages = []
        analysis.recommendation = PdfRecommendation.LLM_OCR
        for p in analysis.per_page:
            p.is_scanned = True
            p.recommended_action = "llm_ocr"
        pages_to_ocr = set(_all_pages)

    ocr_service = OCRService(
        request, analysis, pages_to_ocr,
        log_callback=log,
        progress_callback=update_progress,
        status_callback=update_status,
        valid_pages=valid_pages,  # restrict text extraction to these pages
    )
    ocr_results = ocr_service.process_pdf(request.input_path, request.password)

    if converter.cancel_event.is_set():
        return ConversionResult(success=False, error_msg="Cancelled by user")

    # ── Filter OCR results by page range if set ──────────────────────
    if request.page_range_start is not None or request.page_range_end is not None:
        filtered_results = {}
        for page_num, result in ocr_results.items():
            if effective_start_page <= page_num <= effective_end_page:
                filtered_results[page_num] = result
        ocr_results = filtered_results
        log(f"  📄 Filtered OCR results to pages {effective_start_page}–{effective_end_page} ({len(ocr_results)} pages)", "INFO")

    # ── Step 4: Build raw markdown ───────────────────────────────────
    update_progress(0.18)  # OCR done, building markdown
    raw_markdown = OCRService.build_markdown(ocr_results)

    return ExtractionResult(
        raw_markdown=raw_markdown,
        analysis=analysis,
        pages_to_ocr=pages_to_ocr,
        effective_start_page=effective_start_page,
        effective_end_page=effective_end_page,
        effective_total_pages=effective_total_pages,
        toc_entries=toc_entries,
        valid_pages=valid_pages,
        selected_pages=_selected_pages,
    )
