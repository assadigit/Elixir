"""V0.4.19 — Converter visual-feature machinery (cover screenshots, OCR repair,
vision-region cropper, footnote extraction) moved VERBATIM from converter_impl.py
(de-monolithization). Mixed into Converter via ConverterVisualMixin.

The whole methods (``_extract_covers``, ``_re_extract_with_ocr``,
``_targeted_ocr_repair``) are byte-identical moves; the two ``_run_*``
methods carry convert()'s inline cropper/footnote blocks VERBATIM (dedented
one level out of the big ``try:``), with the convert() locals the blocks read
threaded in as parameters:

- ``_run_visual_region_cropping(total_pages, toc_entries)`` — the V0.4.3
  Vision-Region Cropper block (reads only those two convert() locals; the
  try/except with ``self._record_partial_failure`` stays inside).
- ``_run_footnote_extraction(book_title)`` — the footnote block (``full_text``
  is computed inside from ``self.full_markdown_path``, exactly as before).

Following the house mixin pattern (V0.18 Phase 5 / V0.4.19): no
``core.pipeline`` imports here, so no import cycle; ``Converter`` appends
``ConverterVisualMixin`` at the end of its bases.
"""

from __future__ import annotations

from pathlib import Path

# _targeted_ocr_repair maps garbled character ranges to source pages via the
# canonical ``<!-- page N -->`` markers (V18.1 P8 binary search).
from core.postprocess.page_marker import extract_page_markers


class ConverterVisualMixin:
    """Visual-feature machinery for the Converter (see module docstring).

    Expects the host class to provide: ``self.settings``, ``self.request``,
    ``self.paths``, ``self.output_dir``, ``self.full_markdown_path``,
    ``self._log``, ``self._update_progress``, ``self._update_status``,
    ``self._cancel_requested``, ``self._record_partial_failure``,
    ``self._derive_page_ranges_from_toc`` — the standard Converter surface.
    """

    def _extract_covers(self, total_pages: int, toc_entries: list | None = None) -> None:
        """Render front and back cover pages as JPEG — zero new dependencies.

        V10.12.1 bugfix: ``toc_entries`` is now a parameter (was a bare name
        reference to a local in convert() that was never in scope — a
        pre-existing latent NameError that fired whenever the user selected
        chapters).  When ``toc_entries`` is None (called before TOC
        extraction), the chapter-screenshot block is skipped.
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            return

        poppler_path = self.settings.get("paths.poppler") or None

        pages = [1] + ([total_pages] if total_pages >= 2 else [])
        for page_num in pages:
            try:
                label = "front_cover" if page_num == 1 else "back_cover"
                out = self.paths.screenshot(label)
                # ensure the screenshots dir exists before checking
                out.parent.mkdir(parents=True, exist_ok=True)
                if out.exists():
                    continue  # already extracted (re-run guard)
                kwargs: dict = {
                    "first_page": page_num,
                    "last_page": page_num,
                    "dpi": 200,
                    "fmt": "jpeg",
                }
                if poppler_path:
                    kwargs["poppler_path"] = poppler_path
                images = convert_from_path(str(self.request.input_path), **kwargs)
                if images:
                    images[0].save(str(out), format="JPEG", quality=90)
                    self._log(f"  📸 {label} → {out.name}", "INFO")
            except Exception as e:
                self._log(f"  ⚠️ Cover p.{page_num}: {e}", "WARNING")

        # Screenshot selected chapter pages as visual proof.
        # For each selected chapter, render its pages as JPEGs so the user
        # can verify exactly what was processed.
        # V10.12.1: use the toc_entries PARAMETER (not the bare name that
        # caused the NameError).  When None, skip — the basic covers above
        # are already done.
        if self.request.selected_chapters and toc_entries:
            try:
                _chap_pages = self._derive_page_ranges_from_toc(
                    toc_entries, self.request.selected_chapters, total_pages
                )
                if _chap_pages:
                    self._log(
                        f"  📸 Screenshotting {len(_chap_pages)} selected chapter page(s)...",
                        "INFO",
                    )
                    for _pn in sorted(_chap_pages):
                        try:
                            _label = f"chapter_page_{_pn}"
                            _out = self.paths.screenshot(_label)
                            _out.parent.mkdir(parents=True, exist_ok=True)
                            if _out.exists():
                                continue
                            _kwargs = {
                                "first_page": _pn,
                                "last_page": _pn,
                                "dpi": 200,
                                "fmt": "jpeg",
                            }
                            if poppler_path:
                                _kwargs["poppler_path"] = poppler_path
                            _imgs = convert_from_path(str(self.request.input_path), **_kwargs)
                            if _imgs:
                                _imgs[0].save(str(_out), format="JPEG", quality=85)
                                self._log(f"  📸 p.{_pn} → {_out.name}", "DEBUG")
                        except Exception as e:
                            self._log(f"  ⚠️ Screenshot p.{_pn}: {e}", "DEBUG")
            except Exception as e:
                self._record_partial_failure("Chapter screenshots", e)

    def _re_extract_with_ocr(self, page_nums: list) -> str:
        """Re-extract text from the PDF using OCR (render pages as images).

        fixed the import — OCRService is in core/ocr/service.py.
        robust instantiation — create a dummy analysis if None,
        pass valid_pages to restrict OCR to only the needed pages, and
        wrap everything in a try/except so the converter never crashes.
        """
        try:
            self._log(
                f"  🔁 OCR re-extraction: rendering {len(page_nums)} page(s) as images...",
                "INFO",
            )
            from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation
            from core.ocr.service import OCRService

            # create a minimal analysis if we don't have one
            _analysis = getattr(self, "_analysis", None)
            if _analysis is None:
                # Build a dummy analysis that marks all pages as "not scanned"
                # (digital text extraction), so OCRService knows these are
                # pages that need re-extraction via OCR.
                _dummy_pages = []
                for p in page_nums:
                    _dummy_pages.append(
                        PageAnalysis(
                            page_num=p,
                            is_scanned=False,
                            extracted_text_preview="",
                            recommended_action="no_ocr",
                        )
                    )
                _analysis = PdfAnalysisResult(
                    total_pages=max(page_nums) if page_nums else 1,
                    scanned_pages=[],
                    text_pages=list(page_nums),
                    recommendation=PdfRecommendation.NO_OCR,
                    per_page=_dummy_pages,
                )

            # pass valid_pages to restrict processing to ONLY
            # the garbled pages — don't re-process the entire PDF.
            ocr_service = OCRService(
                self.request,
                analysis=_analysis,
                pages_to_ocr=page_nums,
                log_callback=self._log,
                progress_callback=self._update_progress,
                status_callback=self._update_status,
                valid_pages=set(page_nums),
            )
            ocr_results = ocr_service.process_pdf(
                Path(self.request.input_path), self.request.password
            )
            if ocr_results:
                text = OCRService.build_markdown(ocr_results)
                return text
        except Exception as e:
            self._log(f"  ⚠️ OCR re-extraction failed: {e}", "WARNING")
            import traceback

            self._log(f"  📋 Traceback: {traceback.format_exc()[-300:]}", "DEBUG")
        return ""

    def _targeted_ocr_repair(
        self,
        text: str,
        garbled_ranges: list,
        total_pages: int = 17,
        pages_to_ocr: list = None,
    ) -> str:
        """V10.1.13: Repair garbled sections with targeted OCR.

        User's idea:
        1. Find garbled sections (character ranges)
        2. Map those ranges to PDF page numbers
        3. Add 1 page before + 1 page after for overlap context
        4. OCR ONLY those pages
        5. Find overlap between OCR text and clean markitdown text
        6. Replace garbled section with OCR text, preserving clean parts

        This is much faster than OCR-ing the entire PDF.
        """
        if not garbled_ranges:
            return text
        text_len = len(text)

        # Step 1: Map garbled ranges to page numbers.
        # V18.1 (P8): use ``<!-- page N -->`` markers + binary search to
        # map char offsets to source pages (accurate on figure-heavy
        # pages). V18.2.15 (P8): traceable logging at both paths.
        page_markers = extract_page_markers(text)
        ocr_pages = set()
        if page_markers:
            self._log(
                f"  🎯 V18.2.15 Targeted OCR: page-marker mapping "
                f"({len(page_markers)} markers, {len(garbled_ranges)} ranges)",
                "INFO",
            )
            import bisect

            marker_positions = [pos for _, pos in page_markers]
            marker_pages = [pn for pn, _ in page_markers]
            for start, end in garbled_ranges:
                # Find the last marker whose position is <= start (and end).
                # bisect_right - 1 gives the index of the marker that
                # starts the page containing the offset.
                start_idx = bisect.bisect_right(marker_positions, start) - 1
                if start_idx < 0:
                    start_idx = 0
                end_idx = bisect.bisect_right(marker_positions, end) - 1
                if end_idx < 0:
                    end_idx = 0
                start_page = marker_pages[start_idx]
                end_page = marker_pages[end_idx]
                # ±1 page overlap for context (preserves old behaviour).
                if start_page > 1:
                    start_page -= 1
                if end_page < total_pages:
                    end_page += 1
                for p in range(start_page, end_page + 1):
                    ocr_pages.add(p)
        else:
            # Fallback: very short PDFs or marker-stripped text — use the
            # old proportional heuristic so we still make progress.
            self._log(
                "  ⚠️ No page markers found — falling back to proportional "
                "page mapping (less accurate on figure-heavy pages).",
                "DEBUG",
            )
            for start, end in garbled_ranges:
                start_page = max(1, int(start / text_len * total_pages) - 1)
                end_page = min(total_pages, int(end / text_len * total_pages) + 2)
                for p in range(start_page, end_page + 1):
                    ocr_pages.add(p)

        # If pages_to_ocr is specified (chapter selection), intersect
        if pages_to_ocr:
            valid_set = set(pages_to_ocr) if not isinstance(pages_to_ocr, set) else pages_to_ocr
            # Also include adjacent pages for overlap
            expanded_valid = set()
            for p in valid_set:
                expanded_valid.add(p)
                if p > 1:
                    expanded_valid.add(p - 1)
                if p < total_pages:
                    expanded_valid.add(p + 1)
            ocr_pages = ocr_pages & expanded_valid

        ocr_pages = sorted(ocr_pages)
        if not ocr_pages:
            return text

        self._log(
            f"  🎯 Targeted OCR: {len(ocr_pages)} page(s) to OCR "
            f"(pages {ocr_pages[0]}-{ocr_pages[-1]} if contiguous, "
            f"else scattered). Original text: {text_len:,} chars, "
            f"garbled: {sum(e - s for s, e in garbled_ranges):,} chars.",
            "INFO",
        )

        # Step 2: OCR only the needed pages
        ocr_text = self._re_extract_with_ocr(ocr_pages)
        if not ocr_text or len(ocr_text) < 100:
            self._log("  ⚠️ Targeted OCR produced no text", "WARNING")
            return text

        # Step 3: Find overlap between OCR text and clean markitdown text
        # Look for the first and last 200 chars of each garbled range in
        # the OCR text to find where to splice.
        # If we can't find overlap, just replace the entire garbled range
        # with the OCR text for the corresponding pages.

        # Strategy: replace each garbled range with OCR text, using
        # the clean text before/after the range as anchors.
        result = text
        offset = 0  # track offset from replacements
        for start, end in garbled_ranges:
            adj_start = start + offset
            adj_end = end + offset
            # Get clean text before and after the garbled section (200 chars each)
            before_text = result[max(0, adj_start - 200) : adj_start].strip()
            after_text = result[adj_end : min(len(result), adj_end + 200)].strip()

            # Try to find before_text in the OCR text (overlap anchor)
            ocr_before_pos = -1
            if before_text and len(before_text) > 30:
                # Search for the last 50 chars of before_text in OCR
                search = before_text[-50:]
                ocr_before_pos = ocr_text.find(search)

            # Try to find after_text in the OCR text
            ocr_after_pos = -1
            if after_text and len(after_text) > 30:
                search = after_text[:50]
                ocr_after_pos = ocr_text.find(search)

            # Extract the OCR text between the anchors
            if ocr_before_pos >= 0 and ocr_after_pos >= 0 and ocr_after_pos > ocr_before_pos:
                # Found both anchors — extract between them
                ocr_replacement = ocr_text[
                    ocr_before_pos + len(before_text[-50:]) : ocr_after_pos
                ].strip()
            elif ocr_before_pos >= 0:
                # Found only the before anchor — take everything after it
                ocr_replacement = ocr_text[ocr_before_pos + 50 :].strip()
            elif ocr_after_pos >= 0:
                # Found only the after anchor — take everything before it
                ocr_replacement = ocr_text[:ocr_after_pos].strip()
            else:
                # No anchors found — use the entire OCR text as replacement
                ocr_replacement = ocr_text.strip()

            if ocr_replacement and len(ocr_replacement) > 20:
                # Replace the garbled section with the OCR text
                result = result[:adj_start] + "\n" + ocr_replacement + "\n" + result[adj_end:]
                offset += len(ocr_replacement) + 2 - (adj_end - adj_start)
                self._log(
                    f"  🔧 Replaced garbled section ({end - start:,} chars) "
                    f"with OCR text ({len(ocr_replacement):,} chars)",
                    "DEBUG",
                )

        return result

    def _run_visual_region_cropping(
        self, total_pages: int, toc_entries: list | None = None
    ) -> None:
        """V0.4.19 (de-monolithization): the V0.4.3 Vision-Region Cropper
        block moved VERBATIM from convert().  ``total_pages`` and
        ``toc_entries`` are the two convert() locals the block reads
        (threaded as parameters); the try/except with
        ``self._record_partial_failure`` stays inside, exactly as before.
        """
        # ── V0.4.3: Vision-Region Cropper (default ON) ───────────────────
        # Crops diagrams/charts/tables at high DPI and embeds inline in
        # the chapter markdown. Layer A (vector-graphics clustering)
        # always runs; Layer B (VLM region detection) auto-enables when
        # a vision model is available (reuses V0.4.1's vision probe via
        # build_vlm_callable_from_request). Content-agnostic. See
        # docs/FEASIBILITY_vision_crop.md for the full design.
        extract_vr = bool(getattr(self.request, "extract_visual_regions", True))
        if extract_vr and not self._cancel_requested("visual-region crops"):
            try:
                from core.pdf.vision_region_cropper import (
                    build_inline_markdown,
                    build_vlm_callable_from_request,
                    extract_visual_regions,
                )

                # Derive the page list using the same 3-step logic as
                # the screenshots block above (page range → manual
                # segments → selected chapters).
                vr_page_list = list(range(1, total_pages + 1))
                if self.request.page_range_start or self.request.page_range_end:
                    _start = self.request.page_range_start or 1
                    _end = self.request.page_range_end or total_pages
                    vr_page_list = [p for p in vr_page_list if _start <= p <= _end]
                if self.request.manual_segments:
                    seg_pages = set()
                    for start, end in self.request.manual_segments:
                        for p in range(max(1, start), min(total_pages + 1, end + 1)):
                            seg_pages.add(p)
                    vr_page_list = [p for p in vr_page_list if p in seg_pages]
                elif self.request.selected_chapters:
                    toc_page_set = self._derive_page_ranges_from_toc(
                        toc_entries, self.request.selected_chapters, total_pages
                    )
                    if toc_page_set:
                        vr_page_list = [p for p in vr_page_list if p in toc_page_set]

                # Cap the page count for the VLM probe (Layer B cost
                # scales with page count; default to the selected
                # chapter pages only — same scope as the chapter
                # screenshots above).
                if len(vr_page_list) > 200:
                    self._log(
                        f"  📐 Visual-region cropper: {len(vr_page_list)} pages "
                        f"is a lot — capping to first 200 to control VLM cost",
                        "DEBUG",
                    )
                    vr_page_list = vr_page_list[:200]

                self._log(
                    f"  📐 Visual-region cropper: scanning {len(vr_page_list)} page(s) "
                    f"for diagrams/charts/tables",
                    "INFO",
                )

                # Build the VLM callable (returns None if no vision
                # model — Layer B is gracefully disabled, Layer A still
                # runs). This reuses V0.4.1's provider-agnostic vision
                # probe via core.llm.llm_provider_impl.create_provider.
                vlm_callable = build_vlm_callable_from_request(self.request, log=self._log)

                # Run the cropper. V0.4.11: enable_existing_extractors
                # is now True when extract_visual_regions is ON — the
                # V0.4.3 code set it to False (assuming the existing
                # figure_table_cropper already ran above), but that
                # block is gated behind outputs_optin.screenshots
                # (default OFF), so on most runs Layer 0 never fires.
                # This means embedded images (photos, raster charts) in
                # the PDF were never detected. Now: when the visual-
                # region cropper is enabled (default ON), it also runs
                # the existing PyMuPDF image + pdfplumber table
                # extraction, so the user gets crops even without
                # enabling the screenshots opt-in.
                vr_result = extract_visual_regions(
                    pdf_path=self.request.input_path,
                    output_dir=self.output_dir,
                    pages=vr_page_list,
                    vlm_callable=vlm_callable,
                    log_callback=self._log,
                    enable_existing_extractors=True,  # V0.4.11: was False
                    enable_vector_clustering=True,
                    enable_vlm=vlm_callable is not None,
                )

                # Log the result counts.
                n_regions = len(vr_result.regions)
                by_src: dict[str, int] = {}
                for r in vr_result.regions:
                    by_src[r.source] = by_src.get(r.source, 0) + 1
                src_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())) or "none"
                self._log(
                    f"  📐 Visual-region cropper: {n_regions} region(s) ({src_summary}) "
                    f"→ {self.paths.regions_dir}",
                    "INFO",
                )

                # Embed the crops inline in the chapter markdown at
                # the right page markers (Layer C). The cropper returns
                # a manifest; we also inject the inline embeds into
                # the full markdown file so the summary LLM can see
                # the figures in context.
                if vr_result.regions and self.full_markdown_path.exists():
                    try:
                        md_text = self.full_markdown_path.read_text(encoding="utf-8")
                        md_text = build_inline_markdown(md_text, vr_result.regions)
                        self.full_markdown_path.write_text(md_text, encoding="utf-8")
                        n_embedded = sum(1 for r in vr_result.regions if r.crop_path)
                        self._log(
                            f"  📐 Inline-embedded {n_embedded} region crop(s) into the markdown",
                            "INFO",
                        )
                    except Exception as e:
                        self._log(
                            f"  ⚠️ Inline-embed of region crops failed: {type(e).__name__}: {e}",
                            "WARNING",
                        )
            except Exception as e:
                self._record_partial_failure("Visual-region cropper", e)
        else:
            if not extract_vr:
                self._log("  ⏭️ Visual-region cropper skipped (disabled in settings)", "DEBUG")

    def _run_footnote_extraction(self, book_title: str) -> None:
        """V0.4.19 (de-monolithization): the footnote-extraction block moved
        VERBATIM from convert().  ``book_title`` is the convert() local the
        block reads (threaded as a parameter); ``full_text`` is computed
        inside from ``self.full_markdown_path``, exactly as before.
        """
        # Footnote extraction
        # V18.20.2.0 (SWOT A15): cancel gate — skip on cancel.
        if not self._cancel_requested("footnote extraction"):
            try:
                from core.pdf.footnote_extractor import extract_footnotes

                full_text = (
                    self.full_markdown_path.read_text(encoding="utf-8")
                    if self.full_markdown_path.exists()
                    else ""
                )
                if full_text:
                    fn_result = extract_footnotes(full_text)
                    if fn_result["total_notes"] > 0:
                        self._log(f"  📝 Footnotes: {fn_result['total_notes']} extracted", "INFO")
                        # Save footnotes to separate file
                        fn_path = self.paths.footnotes(book_title)
                        from core.pdf.footnote_extractor import format_footnotes_for_summary

                        fn_path.parent.mkdir(parents=True, exist_ok=True)  # lazy dir
                        fn_path.write_text(
                            format_footnotes_for_summary(
                                fn_result["footnotes"], fn_result["endnotes"]
                            ),
                            encoding="utf-8",
                        )
            except Exception as e:
                self._record_partial_failure("Footnote extraction", e)
