"""V10.7.0 (Phase 8B): Post-processing phase — extracted from
converter.convert().

Contains the markdown post-processing pipeline that runs AFTER raw
markdown is built from OCR/extraction and BEFORE segmentation.  This
includes:

1. Deterministic hyphenation repair ("net-\\nworking" → "networking")
2. Smart paragraph joining (join lines broken mid-sentence)
3. Header/footer removal (detect + strip repeating lines across pages)
4. Figure/table extraction for academic papers (crop + manifest injection)
5. Targeted OCR repair for garbled sections (full + partial garbling)
6. Content-type auto-detection (multi-signal detector → auto-switch preset)
7. Layout reorder for academic papers (multi-column + figure captions +
   abstract detection + lightweight layout detection)
8. Advanced document handling (tables / math / layout analysis)
9. Vision OCR for figures (extract text from figure regions)

All of this is deterministic (no LLM calls) — it's pure text/PDF
processing.  Extracted into its own module so the converter's
``convert()`` method is shorter and the post-processing logic is
testable independently.

The function takes a context object (the converter instance, which has
``request``, ``temp_markdown_path``, ``output_dir``, ``_poppler_path``,
``_log``, ``_update_status``, ``_targeted_ocr_repair``) plus the
analysis result + page-range info, mutates the raw markdown in place,
and writes it back to the temp file.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_postprocess(
    converter: Any,
    raw_markdown: str,
    analysis: Any,
    pages_to_ocr: list,
    effective_start_page: int,
    effective_end_page: int,
    valid_pages: list | None = None,
    toc_entries: list | None = None,
) -> str:
    """Run the full post-processing pipeline on ``raw_markdown``.

    Args:
        converter: the Converter instance (accessed for ``self.request``,
            ``self.temp_markdown_path``, ``self.output_dir``,
            ``self._poppler_path``, ``self._log``, ``self._update_status``,
            ``self._targeted_ocr_repair``).  Passed as a context object
            rather than individual args to keep the signature manageable
            (the block touches ~8 converter attributes).
        raw_markdown: the raw markdown text to post-process.
        analysis: the PdfAnalysisResult (has ``total_pages``).
        pages_to_ocr: the list of pages that were OCR'd.
        effective_start_page / effective_end_page: the effective page range
            (after applying the user's page_range_start/end).
        valid_pages: optional list of valid pages for figure/table cropping.
        toc_entries: optional TOC entries (unused here, kept for signature
            symmetry with the converter's flow).

    Returns:
        The post-processed raw_markdown string.  Also writes it back to
        ``converter.temp_markdown_path`` at key checkpoints.
    """
    log = converter._log
    update_status = converter._update_status
    request = converter.request
    temp_path = converter.temp_markdown_path

    # ── 1. Deterministic hyphenation repair — fix "net-\nworking" ──────
    # Pure regex, zero LLM cost.
    try:
        from core.summarisation.text_preprocessor import repair_hyphenation
        pre_len = len(raw_markdown)
        raw_markdown = repair_hyphenation(raw_markdown)
        if len(raw_markdown) != pre_len:
            log(f"  🔧 Hyphenation repair: {pre_len - len(raw_markdown)} line-break joins", "DEBUG")
    except Exception as e:
        log(f"  ⚠️ Hyphenation repair skipped: {e}", "DEBUG")

    # ── 1b. V13.33.2: Replace tabs with spaces (PDF layout artifact) ──
    # Many PDFs use tab characters for layout alignment. When extracted to
    # text, these become literal \t characters between words, producing
    # "This\tview\tis\ta\tcomprehensive" instead of "This view is a comprehensive".
    # Replace all tabs with single spaces, then collapse multiple spaces.
    _tab_count = raw_markdown.count('\t')
    if _tab_count > 0:
        raw_markdown = raw_markdown.replace('\t', ' ')
        raw_markdown = re.sub(r' {2,}', ' ', raw_markdown)
        log(f"  🧹 Tab cleanup: replaced {_tab_count} tab character(s) with spaces", "DEBUG")

    # ── 2. Smart paragraph joining — join lines broken mid-sentence ───
    try:
        from core.summarisation.text_preprocessor import smart_paragraph_joining
        raw_markdown = smart_paragraph_joining(raw_markdown)
    except Exception as e:
        log(f"  ⚠️ Paragraph joining skipped: {e}", "DEBUG")

    # ── 3. Header/footer removal — detect repeating lines across pages ─
    try:
        from core.summarisation.text_preprocessor import remove_headers_footers
        pre_len = len(raw_markdown)
        raw_markdown = remove_headers_footers(raw_markdown)
        if len(raw_markdown) != pre_len:
            log(f"  🧹 Header/footer removal: {pre_len - len(raw_markdown)} chars stripped", "DEBUG")
    except Exception as e:
        log(f"  ⚠️ Header/footer removal skipped: {e}", "DEBUG")

    temp_path.parent.mkdir(parents=True, exist_ok=True)  # lazy dir
    temp_path.write_text(raw_markdown, encoding="utf-8")
    # NOTE: the "📝 Raw markdown: N chars | [elapsed]" log line is emitted
    # by the converter AFTER this function returns (it needs _elapsed(),
    # a closure-local timer inside convert() that isn't accessible here).

    # ── 4. Figure/table extraction for academic papers ────────────────
    # For academic papers, crop every figure/chart/table so the user can
    # verify the data visually.  Inject a manifest into the markdown.
    if getattr(request, "source_type", "") == "academic_paper":
        try:
            from core.pdf.figure_table_cropper import (
                build_figure_table_manifest,
                extract_figures_and_tables,
            )
            _figs, _tbls = extract_figures_and_tables(
                pdf_path=Path(request.input_path),
                output_dir=converter.output_dir,
                total_pages=analysis.total_pages if analysis else 17,
                log_callback=log,
                valid_pages=valid_pages,
            )
            if _figs or _tbls:
                _manifest = build_figure_table_manifest(_figs, _tbls)
                raw_markdown += _manifest
                temp_path.write_text(raw_markdown, encoding="utf-8")
                log(
                    f"  📊 Injected {len(_figs)} figure(s) + {len(_tbls)} table(s) "
                    f"manifest into markdown",
                    "INFO",
                )
        except Exception as _fte:
            log(f"  ⚠️ Figure/table extraction skipped: {_fte}", "DEBUG")

    # ── 5. Targeted OCR repair for garbled sections ───────────────────
    # Instead of OCR-ing the entire PDF when garbled text is detected,
    # this system:
    #   1. Finds the garbled sections (character ranges in the text)
    #   2. Maps those ranges to PDF page numbers
    #   3. Adds 1 page before + 1 page after as overlap context
    #   4. OCRs ONLY those pages (not the whole PDF)
    #   5. Finds the overlap between OCR text and clean markitdown text
    #   6. Replaces the garbled section with the OCR text, preserving
    #      the clean parts
    # Much faster than full OCR (only garbled pages get OCR'd) and
    # preserves the clean text from pages that extracted fine.
    from utils.text_quality import find_garbled_ranges, find_partial_garbled_ranges

    _garbled_ranges = find_garbled_ranges(raw_markdown)

    if _garbled_ranges:
        _total_garbled = sum(end - start for start, end in _garbled_ranges)
        log(
            f"  🔴 Garbled text detected: {_total_garbled:,} chars in "
            f"{len(_garbled_ranges)} section(s). Running targeted OCR...",
            "WARNING",
        )
        _fixed_text = converter._targeted_ocr_repair(
            raw_markdown, _garbled_ranges,
            total_pages=analysis.total_pages if analysis else 17,
            pages_to_ocr=pages_to_ocr,
        )
        if _fixed_text and _fixed_text != raw_markdown:
            raw_markdown = _fixed_text
            temp_path.write_text(raw_markdown, encoding="utf-8")
            log(
                f"  ✅ Targeted OCR repair complete: {len(raw_markdown):,} chars "
                f"of clean text (garbled sections replaced with OCR output).",
                "SUCCESS",
            )
        else:
            log(
                "  ⚠️ Targeted OCR did not improve the text — "
                "continuing with original extraction.",
                "WARNING",
            )
    else:
        # For academic papers, also check partial garbling
        # (avg word length < 3.5 in any 1000-char window)
        if getattr(request, "source_type", "") == "academic_paper":
            _partial_ranges = find_partial_garbled_ranges(raw_markdown)
            if _partial_ranges:
                _total_partial = sum(end - start for start, end in _partial_ranges)
                log(
                    f"  🔴 Partial garbling detected in academic paper: "
                    f"{_total_partial:,} chars in {len(_partial_ranges)} section(s). "
                    f"Running targeted OCR...",
                    "WARNING",
                )
                _fixed_text = converter._targeted_ocr_repair(
                    raw_markdown, _partial_ranges,
                    total_pages=analysis.total_pages if analysis else 17,
                    pages_to_ocr=pages_to_ocr,
                )
                if _fixed_text and _fixed_text != raw_markdown:
                    raw_markdown = _fixed_text
                    temp_path.write_text(raw_markdown, encoding="utf-8")
                    log(
                        f"  ✅ Targeted OCR repair complete: {len(raw_markdown):,} chars "
                        f"of clean text.",
                        "SUCCESS",
                    )

    # ── 6. Content-type auto-detection ────────────────────────────────
    # Deterministic content-type auto-detection.  If the user hasn't
    # manually selected a specific preset (still on the default
    # "normal_book"), run the full multi-signal detector on the raw
    # markdown and auto-switch to the detected type.
    if request.source_type == "normal_book" and len(raw_markdown) > 500:
        try:
            from core.llm.content_detector import detect_content_type
            detection = detect_content_type(
                raw_markdown, analysis.total_pages, len(pages_to_ocr)
            )
            log(
                f"  🔍 Content auto-detection: {detection.explanation()}",
                "INFO",
            )
            if detection.recommended and detection.content_type != "normal_book":
                log(
                    f"  ✅ Auto-switching to '{detection.label()}' preset "
                    f"(confidence {detection.confidence:.0%})",
                    "INFO",
                )
                request.source_type = detection.content_type
                # Log the signal breakdown for transparency
                for t, s in detection.scores.items():
                    if s > 0:
                        log(
                            f"    {t}: score={s:.1f} ({detection.signals.get(t, '')})",
                            "DEBUG",
                        )
            elif not detection.recommended:
                log(
                    f"  ℹ️ Detection confidence too low ({detection.confidence:.0%}) — "
                    f"keeping normal_book preset",
                    "DEBUG",
                )
        except Exception as e:
            log(f"  ⚠️ Content auto-detection failed: {e}", "DEBUG")

    # ── 7. Layout reorder for Academic Papers ─────────────────────────
    # V18.15.3.2: HARD GUARDRAIL — before even activating layout reorder,
    # do a quick 2-page multi-column sampling check. If the PDF is single-
    # column (95% of books), skip the ENTIRE layout reorder block — don't
    # even instantiate LayoutReorder, don't log "enabling layout reorder",
    # don't produce the misleading "no changes" warning. The content
    # auto-detector classifies based on citations/keywords (not layout), so
# a domain textbook with 4 citations gets "academic_paper" even
    # though it's single-column. This guardrail prevents that false activation.
    if request.source_type == "academic_paper":
        from core.pdf import LayoutReorder as _LR_Guard
        _guard = _LR_Guard(log_callback=lambda msg, level="DEBUG": None)
        _is_multi_column = False
        if _guard.is_available():
            _pages = _guard._split_markdown_into_pages(raw_markdown)
            _sample_nums = list(_pages.keys())[:2]
            _is_multi_column = _guard._detect_multi_column(request.input_path, _sample_nums)

        if not _is_multi_column:
            log(
                "  V18.15.3.2: Layout reorder NOT activated — content classified as "
                "'academic_paper' but sampling confirms single-column layout "
                "(reorder unnecessary, skipped entire block).",
                "INFO"
            )
        else:
            update_status("Reordering layout for multi‑column...")
            log("  📐 Multi-column layout detected – enabling layout reorder.", "INFO")
            from core.pdf import LayoutReorder
            _pre_reorder_len = len(raw_markdown)
            reorder = LayoutReorder(log_callback=log)
            if reorder.is_available():
                raw_markdown = reorder.reorder_markdown(raw_markdown, request.input_path)
                temp_path.parent.mkdir(parents=True, exist_ok=True)  # lazy dir
                temp_path.write_text(raw_markdown, encoding="utf-8")
                log("  ✅ Layout reorder complete.", "INFO")
                # warn if reorder didn't change anything — may indicate
                # CID-font garbling on Elsevier/ScienceDirect PDFs.
                if len(raw_markdown) == _pre_reorder_len:
                    log(
                        "  ⚠️ Layout reorder produced no changes — the PDF may use "
                        "custom font encodings (common in Elsevier/ScienceDirect). "
                        "If text appears garbled, try enabling Force OCR All Pages.",
                        "WARNING",
                    )
            else:
                log("  ⚠️ Layout reorder skipped (missing pdfplumber or PyMuPDF).", "WARNING")

        # Extract figure captions and append them at the end of the raw
        # markdown so the summarizer can see them.
        try:
            import re as _re_fig
            fig_captions = _re_fig.findall(
                r"(?:Figure|Fig\.?)\s*\d+[:.]?\s*(.+?)(?:\n\n|\n[A-Z]|\Z)",
                raw_markdown,
                _re_fig.DOTALL | _re_fig.IGNORECASE,
            )
            if fig_captions:
                caption_text = "\n\n## Figure Captions\n\n"
                for i, cap in enumerate(fig_captions[:30], 1):  # cap at 30
                    caption_text += f"{i}. {cap.strip()[:300]}\n"
                raw_markdown += caption_text
                log(f"  📊 Extracted {len(fig_captions)} figure caption(s) into markdown", "DEBUG")
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Detect the abstract section and log it (for the summarizer to
        # use as executive summary guidance).
        try:
            import re as _re_abs
            abs_match = _re_abs.search(
                r"(?:^|\n)\s*(?:Abstract|ABSTRACT)\s*\n(.+?)(?:\n\s*(?:Keywords|Introduction|1\.\s|I\.\s))",
                raw_markdown,
                _re_abs.DOTALL,
            )
            if abs_match:
                abstract_text = abs_match.group(1).strip()[:2000]
                log(
                    f"  📄 Abstract detected ({len(abstract_text)} chars) — "
                    f"will guide executive summary generation",
                    "INFO",
                )
                # Store for the summarizer to use
                converter._detected_abstract = abstract_text
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Lightweight multi-column detection (no detectron2 needed)
        try:
            from core.pdf.lightweight_layout import LightweightLayoutDetector
            detector = LightweightLayoutDetector(log_callback=log)
            # Detect and reorder multi-column pages
            page_list = list(range(effective_start_page, effective_end_page + 1))
            reordered = detector.detect_and_reorder(request.input_path, page_list)
            if reordered:
                log(f"  📐 Phase 4.1: {len(reordered)} multi-column page(s) reordered", "INFO")
        except Exception as e:
            log(f"  ⚠️ Phase 4.1: Lightweight layout detection skipped: {e}", "DEBUG")

    # ── 8. Advanced document handling ─────────────────────────────────
    if request.extract_tables or request.extract_math or request.layout_analysis:
        update_status("Applying advanced document features…")
        log("  🧩 Running advanced document handling…", "INFO")

        # Prepare list of pages to process (respect page range)
        pages_to_process = list(range(effective_start_page, effective_end_page + 1))

        # ── Table extraction ─────────────────────────────────────────
        if request.extract_tables:
            log("  📊 Extracting tables…", "INFO")
            try:
                from core.pdf import TableExtractor
                extractor = TableExtractor(
                    log_callback=log,
                    method=request.table_extraction_method,
                )
                tables = extractor.extract_tables_from_pdf(
                    request.input_path,
                    pages="all",
                )
                if tables:
                    filtered_tables = {p: tbls for p, tbls in tables.items() if p in pages_to_process}
                    if filtered_tables:
                        raw_markdown = extractor.insert_tables_into_markdown(raw_markdown, filtered_tables)
                        log(f"  ✅ Inserted tables from {len(filtered_tables)} pages.", "INFO")
                    else:
                        log("  ℹ️ No tables found in page range.", "INFO")
                else:
                    log("  ℹ️ No tables found.", "INFO")
            except Exception as e:
                log(f"  ❌ Table extraction failed: {e}", "WARNING")

        # ── Math extraction ──────────────────────────────────────────
        if request.extract_math:
            log("  📐 Extracting math formulae…", "INFO")
            try:
                from core.pdf import MathExtractor
                extractor = MathExtractor(
                    log_callback=log,
                    model=request.math_model,
                    poppler_path=converter._poppler_path,
                )
                math_pages = pages_to_process[:20]
                math_results = extractor.extract_math_from_pdf(
                    request.input_path,
                    math_pages,
                )
                if math_results:
                    raw_markdown = extractor.insert_math_into_markdown(raw_markdown, math_results)
                    log(f"  ✅ Inserted math from {len(math_results)} pages.", "INFO")
                else:
                    log("  ℹ️ No math formulae found.", "INFO")
            except Exception as e:
                log(f"  ❌ Math extraction failed: {e}", "WARNING")

        # ── Layout analysis ──────────────────────────────────────────
        if request.layout_analysis:
            log("  📐 Analyzing layout…", "INFO")
            try:
                from core.pdf import LayoutAnalyzer
                analyzer = LayoutAnalyzer(log_callback=log)
                layout_pages = pages_to_process[:20]
                layout_info = analyzer.analyze_layout(
                    request.input_path,
                    layout_pages,
                )
                if layout_info:
                    raw_markdown = analyzer.reorder_markdown_by_layout(raw_markdown, layout_info)
                    log("  ✅ Layout analysis completed.", "INFO")
                else:
                    log("  ℹ️ Layout analysis found no text blocks.", "INFO")
            except Exception as e:
                log(f"  ❌ Layout analysis failed: {e}", "WARNING")

        temp_path.parent.mkdir(parents=True, exist_ok=True)  # lazy dir
        temp_path.write_text(raw_markdown, encoding="utf-8")
        log("📝 Enhanced markdown saved (with advanced features).", "INFO")

    # ── 9. Vision OCR for Figures ─────────────────────────────────────
    if request.extract_figure_text:
        update_status("Extracting text from figures…")
        log("  🖼️ Extracting text from figures using vision model…", "INFO")
        try:
            from core.pdf import VisionFigureExtractor
            model = request.primary_ocr_model  # OlmOCR by default
            fallback = request.fallback_ocr_model or "qwen3-vl:8b"
            extractor = VisionFigureExtractor(
                pdf_path=request.input_path,
                model_name=model,
                fallback_model=fallback,
                log_callback=log,
            )
            # Determine pages to process (respect page range)
            if request.page_range_start is not None or request.page_range_end is not None:
                start = request.page_range_start or 1
                end = request.page_range_end or analysis.total_pages
                pages = list(range(start, end + 1))
            else:
                pages = None  # all pages

            figure_texts = extractor.extract(pages=pages)
            if figure_texts:
                raw_markdown = extractor.insert_into_markdown(raw_markdown)
                temp_path.parent.mkdir(parents=True, exist_ok=True)  # lazy dir
                temp_path.write_text(raw_markdown, encoding="utf-8")
                log(f"  ✅ Extracted text from {len(figure_texts)} pages with figures.", "INFO")
            else:
                log("  ℹ️ No figures found or no text extracted.", "INFO")
        except Exception as e:
            log(f"  ⚠️ Figure extraction failed: {e}", "WARNING")

    return raw_markdown
