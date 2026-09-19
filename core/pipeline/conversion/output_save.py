"""V10.10.0 (Phase 8E): Output-saving phase — extracted from converter.convert().

Contains the markdown cleaning, language detection, book-title detection +
folder rename, full-markdown assembly + save, per-segment file saving,
checkpoint marking, and S19 summarisation-model pre-warm that runs as
Steps 6–8 of the conversion:

  Step 6: Post-process — clean each segment's markdown via MarkdownCleaner
  Step 7: Detect language — sample the first long segment for lang detection
  Step 8: Save output files — detect book title, rename folder if needed,
          assemble + write full markdown, write per-segment files, mark
          checkpoint phases done, pre-warm the summarisation model

This phase has significant side effects:
  - Mutates ``seg.content`` for each segment (cleaning)
  - May rename the output folder (re-points converter.output_dir, .paths,
    .conv_logger, .checkpoint)
  - Writes full markdown + segment files to disk
  - Marks checkpoint phases done (pdf_extraction, segmentation)
  - Spawns a background thread to pre-warm the summarisation model (S19)

Returns :class:`OutputSaveResult` (book_title, detected_lang, source_name)
on success.  No early-exit paths (no cancel check in this phase — the
previous phase already checked).

Extracted into its own module so the converter's ``convert()`` method is
shorter and the output-saving logic is testable independently.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from core.common.heading_utils import segment_filename_slug
from core.models import Segment
from core.postprocess.cleaner import MarkdownCleaner

logger = logging.getLogger(__name__)


def insert_toc_boundary_headings(
    content: str,
    seg_start_page: int,
    seg_end_page: int,
    toc_entries: list,
    log=None,
) -> tuple[str, int]:
    """V0.03 (P0-4): insert ``## <TOC title>`` at every interior TOC boundary.

    The V0.02 rig output glued 7 of 8 selected essay titles into body text
    (the full-book markdown had exactly TWO headings for a 10-essay extract
    — things 2-8 and 10 were unfindable by any heading-aware chunker, and
    the RAG frontmatter's chunking claim was hollow for 70% of the content).

    GENERAL rule: when a segment spans multiple TOC entries (merged runs,
    full-book runs, part-level segmentation), every TOC entry whose start
    page falls STRICTLY INSIDE the segment gets a real markdown heading at
    its page marker. Entries sharing the segment's start page are skipped
    (the segment heading already covers position 0); same-page entries are
    deduped keep-first (the _segment_by_chapters convention). When the text
    carries no page markers, boundaries cannot be located — content is
    returned unchanged (never guess).

    Returns ``(new_content, n_inserted)``. Never raises (fail-open).
    """
    try:
        if not content or not toc_entries:
            return content, 0
        entries: list[tuple[str, int]] = []
        for e in toc_entries:
            try:
                if isinstance(e, (tuple, list)):
                    title = str(e[0]).strip() if e else ""
                    page = e[1] if len(e) > 1 else None
                else:
                    title = str(getattr(e, "title", "") or "").strip()
                    page = getattr(e, "page", None)
            except Exception:
                continue
            if not title or not page:
                continue
            try:
                page_i = int(page)
            except (TypeError, ValueError):
                continue
            if page_i > 0:
                entries.append((title, page_i))
        if not entries:
            return content, 0
        # Dedupe by page (keep first) + keep only INTERIOR boundaries.
        seen_pages: set[int] = set()
        interior: dict[int, str] = {}
        for title, page in sorted(entries, key=lambda t: t[1]):
            if page in seen_pages:
                continue
            seen_pages.add(page)
            if seg_start_page < page <= seg_end_page:
                interior[page] = title
        if not interior:
            return content, 0
        try:
            from core.postprocess.page_marker import extract_page_markers

            markers = extract_page_markers(content)
        except Exception:
            return content, 0
        if not markers:
            return content, 0
        # Insert AFTER the marker line, from the LAST marker backwards so
        # earlier positions stay valid. A heading directly following the
        # insertion point is never duplicated.
        inserted = 0
        for page, pos in sorted(markers, key=lambda m: m[1], reverse=True):
            title = interior.get(page)
            if not title:
                continue
            line_end = content.find("\n", pos)
            if line_end == -1:
                line_end = len(content) - 1
            rest = content[line_end + 1 :]
            if rest.lstrip().startswith("#"):
                continue  # a heading already sits at this boundary
            heading_line = f"## {title}\n\n"
            content = content[: line_end + 1] + heading_line + rest
            inserted += 1
        if inserted and log is not None:
            log(
                f"  [TOC-Headings] Inserted {inserted} interior TOC heading(s) "
                f"into segment pages {seg_start_page}–{seg_end_page} "
                f"(V0.03 P0-4 — every TOC boundary inside a segment becomes "
                f"a real markdown heading for RAG chunking).",
                "DEBUG",
            )
        return content, inserted
    except Exception as e:  # fail-open — headings are an enhancement, not a gate
        if log is not None:
            log(f"  [TOC-Headings] insertion skipped (non-fatal): {e}", "DEBUG")
        return content, 0


@dataclass
class OutputSaveResult:
    """The state produced by the output-saving phase.

    Fields:
        book_title: the detected (or fallback) book title.  Used by
            summarisation, output-studio, frontmatter, and DOCX.
        detected_lang: the ISO language code detected from the content.
        source_name: the input PDF filename (for frontmatter).
        segments_folder: the folder where segment files were saved (used
            by summarization for the summaries subfolder).
    """

    book_title: str
    detected_lang: str
    source_name: str
    segments_folder: Any  # pathlib.Path


def run_output_save(
    converter: Any,
    segments: list[Segment],
    raw_markdown: str,
    effective_total_pages: int,
    total_pages: int,
    elapsed: str,
) -> OutputSaveResult:
    """Run the output-saving phase (Steps 6–8).

    Args:
        converter: the Converter instance (accessed for ``self.request``,
            ``self._log``, ``self._update_status``, ``self._update_progress``,
            ``self.settings``, ``self.output_dir``, ``self.paths``,
            ``self.checkpoint``, ``self._detect_language``,
            ``self._book_frontmatter``, ``self._chapter_frontmatter``,
            ``self._strip_page_markers``, and the legacy path attributes).
        segments: the segment list from the segmentation phase.
        raw_markdown: the post-processed raw markdown (used for book-title
            detection + full-markdown assembly).
        effective_total_pages: the effective page count (after page-range
            filtering).
        total_pages: the total page count from the analysis.
        elapsed: the elapsed-time string (from the converter's ``_elapsed()``
            closure timer) — used for the checkpoint ``mark_done`` call.

    Returns:
        ``OutputSaveResult`` with book_title, detected_lang, source_name.
    """
    log = converter._log
    update_status = converter._update_status
    update_progress = converter._update_progress
    request = converter.request

    # ── Step 6: Post-process — clean each segment's markdown ────────
    update_status("Cleaning markdown…")
    update_progress(0.24)  # Post-process (quick)

    cleaner = MarkdownCleaner(request=request, log_callback=log)
    for seg in segments:
        seg.content = cleaner.clean(seg.content)

    # ── Step 7: Detect language ──────────────────────────────────────
    sample = next((s.content for s in segments if len(s.content) > 200), "")
    detected_lang = converter._detect_language(sample)
    log(f"🌐 Detected language: {detected_lang}", "INFO")

    # ── Step 8: Save output files ────────────────────────────────────
    update_status("Saving output files…")
    update_progress(0.25)  # Pre-summary save

    # detect the real book title from content.
    # If the PDF filename looks like a hash (e.g. "afsrf454.pdf"),
    # scan the extracted markdown for the actual title (e.g. "Black
    # Swan") and rename the output folder to match.
    from core.pipeline.book_title_detector import detect_book_title

    pdf_stem = request.input_path.stem
    book_title = detect_book_title(pdf_stem, raw_markdown, log)
    # If the detected title differs from the current folder name,
    # rename the output folder + re-point all paths.
    desired_folder = request.output_dir / book_title
    current_folder = converter.output_dir
    if book_title != current_folder.name and not desired_folder.exists():
        try:
            current_folder.rename(desired_folder)
            converter.output_dir = desired_folder
            # Rebuild OutputPaths for the new folder + title.
            from core.pipeline.output_paths import OutputPaths

            converter.paths = OutputPaths(converter.output_dir, book_title)
            # Re-point the legacy attribute names (they're used downstream).
            converter.full_markdown_path = converter.paths.full_markdown
            converter.temp_markdown_path = converter.paths.temp_markdown
            converter.chapters_folder = converter.paths.chapters_dir
            converter.chunks_folder = converter.paths.chunks_dir
            converter.docx_path = converter.paths.docx
            converter.summary_md_path = converter.paths.book_summary
            # fix stale log_path — re-create the logger
            # in the new folder instead of leaving it pointing at the old one.
            from utils.logging import ConversionLogger

            # V18.2.27 (warnings fix): close the OLD logger's file handle before
            # replacing it — otherwise the open file handle leaks (ResourceWarning:
            # unclosed file). The old logger pointed at the pre-rename folder.
            old_logger = getattr(converter, "conv_logger", None)
            if old_logger is not None:
                try:
                    old_logger.close()
                except Exception:
                    pass  # best-effort — never block the rename on close
            converter.conv_logger = ConversionLogger(converter.output_dir, book_title)
            # update checkpoint output_dir too
            converter.checkpoint.set_output_dir(converter.output_dir)
            converter.checkpoint.book_name = book_title
            log(
                f"  📁 Renamed output folder: {current_folder.name} → {book_title}",
                "INFO",
            )
        except Exception as e:
            log(
                f"  ⚠️ Could not rename output folder: {e}\n"
                f"  💡 Tip: close any file explorer windows showing the "
                f"output folder, then try again. Using '{current_folder.name}' instead.",
                "WARNING",
            )
            book_title = current_folder.name  # fall back to stem

    source_name = request.input_path.name
    clean_markers = converter.settings.get("rag.clean_page_markers", True)
    include_frontmatter = converter.settings.get("rag.include_frontmatter", True)
    # V0.03 (P0-4): the extraction-phase TOC entries (stored on the converter
    # after extraction) power interior boundary headings.
    _toc_entries = getattr(converter, "toc_entries", None) or []

    full_parts = []
    if include_frontmatter:
        total_pages_effective = (
            effective_total_pages if request.page_range_start is not None else total_pages
        )
        full_parts.append(
            converter._book_frontmatter(
                total_pages_effective, len(segments), source_name, book_title, detected_lang
            )
        )
    _toc_heading_count = 0
    for seg in segments:
        # V0.03 (P0-4): interior TOC boundaries become real markdown headings
        # BEFORE marker stripping (positions come from the page markers).
        _content, _n_ins = insert_toc_boundary_headings(
            seg.content, seg.start_page, seg.end_page, _toc_entries, log
        )
        _toc_heading_count += _n_ins
        content = converter._strip_page_markers(_content) if clean_markers else _content
        full_parts.append(f"# {seg.heading}\n\n{content}")
    if _toc_heading_count:
        log(
            f"📑 V0.03: inserted {_toc_heading_count} interior TOC heading(s) "
            f"into the full markdown (RAG chunking can now find every "
            f"selected section)",
            "INFO",
        )

    full_markdown = "\n\n---\n\n".join(full_parts)
    # lazy dir — ensure markdown/ exists before writing.
    # V18.20.2.0 (SWOT A30): atomic write (same-dir temp + fsync +
    # os.replace) — a crash mid-write previously left a truncated full
    # markdown that downstream phases (footnotes, citation graph, translation)
    # would then read as if it were complete.  atomic_write_text creates the
    # parent dir (replaces the ``_ensure`` call) and keeps utf-8.
    from utils.atomic_io import atomic_write_text

    atomic_write_text(converter.full_markdown_path, full_markdown)
    log(f"💾 Full markdown → {converter.full_markdown_path}")

    segments_folder = (
        converter.chapters_folder
        if any(s.segment_type == "chapter" for s in segments)
        else converter.chunks_folder
    )
    segments_folder.mkdir(parents=True, exist_ok=True)

    for idx, seg in enumerate(segments, 1):
        # V18.20.4.11 (P1): shared slug helper (core.common.heading_utils) —
        # byte-identical transformation, single source of truth;
        # deterministic_analyzer.find_analysis_for_heading uses the SAME
        # helper to map a chapter heading back to its segment/analysis files.
        safe = segment_filename_slug(seg.heading) or f"segment_{idx:03d}"
        seg_file = segments_folder / f"{idx:03d}_{safe}.md"
        # V0.03 (P0-4): interior TOC headings in the per-segment files too —
        # the deterministic analyzer + summarizer see real section structure.
        _content, _ = insert_toc_boundary_headings(
            seg.content, seg.start_page, seg.end_page, _toc_entries, log
        )
        content = converter._strip_page_markers(_content) if clean_markers else _content
        seg_text = ""
        if include_frontmatter:
            seg_text += converter._chapter_frontmatter(
                seg, idx, len(segments), book_title, source_name, detected_lang
            )
        seg_text += f"# {seg.heading}\n\n{content}"
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial
        # segment file behind (same helper as the full-markdown write above).
        atomic_write_text(seg_file, seg_text, encoding="utf-8")

    log(f"📂 {len(segments)} segment files → {segments_folder}")

    # V17.2: Run deterministic analysis on each segment file.
    # This produces a {segment_stem}_analysis.md file next to each segment,
    # containing 100%-reliable regex-extracted metadata (citations, headings,
    # lists, bold terms, section word counts). The summarizer prepends this
    # to gemma's prompt so gemma doesn't need to "find" these — it just
    # needs to "cover" them.
    #
    # Content-agnostic: works on any book, any topic.
    # Non-fatal: if analysis fails, the pipeline continues without it.
    try:
        from core.preprocessing.deterministic_analyzer import analyze_segment_file

        analysis_count = 0
        for idx, seg in enumerate(segments, 1):
            # V18.20.4.11 (P1): shared slug helper — must stay in lockstep
            # with the segment-write loop above so the analysis lands next
            # to ITS segment file (same transformation, one implementation).
            safe = segment_filename_slug(seg.heading) or f"segment_{idx:03d}"
            seg_file = segments_folder / f"{idx:03d}_{safe}.md"
            if seg_file.exists():
                try:
                    analyze_segment_file(seg_file)
                    analysis_count += 1
                except Exception as _ae:
                    log(f"  ⚠️ Deterministic analysis failed for {seg_file.name}: {_ae}", "WARNING")
        if analysis_count:
            log(
                f"📊 V17.2 Deterministic analysis: {analysis_count}/{len(segments)} segments analyzed (regex-based, 100% reliable)",
                "INFO",
            )
            # V17.5: Log the exact path so the summarizer can verify it looks in the right place
            log(f"   [V17.5] Analysis files written to: {segments_folder}", "DEBUG")
            for _sf in segments_folder.glob("*_analysis.md"):
                log(f"   [V17.5] Analysis file: {_sf.name} ({_sf.stat().st_size} bytes)", "DEBUG")
    except ImportError:
        log("  ℹ️ V17.2 deterministic analyzer not available — skipping (non-fatal)", "DEBUG")
    except Exception as _e:
        log(f"  ⚠️ V17.2 deterministic analysis skipped: {_e}", "WARNING")

    # checkpoint — mark phases done
    converter.checkpoint.mark_done("pdf_extraction", elapsed_s=elapsed, pages=total_pages)
    converter.checkpoint.mark_done("segmentation", segments=len(segments))

    # Pre-warm the summarisation model during the gap
    # between segmentation and summarisation.  The model load (which
    # can take 30-60s on HDD) runs in a background thread while the
    # main thread does post-processing (hyphenation repair, paragraph
    # joining, header/footer removal).  By the time summarisation
    # starts, the model is already in VRAM.
    #
    # V10.12.5: Force-unload the OCR model BEFORE pre-warming the
    # summarizer.  Previously the OCR unload happened later (in the
    # summarization phase), which meant the pre-warm could load the
    # summarizer WHILE the OCR model was still in VRAM — both models
    # loaded simultaneously (11/12GB on the user's RTX 3060).  Now
    # the OCR model is unloaded first, freeing ~6GB before the
    # summarizer loads.
    if request.generate_summaries and request.summarisation_model:
        provider = converter.settings.get("summarisation.provider", "ollama")
        if provider == "ollama" and request.summarisation_model:
            # V10.12.5: unload OCR model first (if still loaded)
            if request.use_llm_ocr and request.primary_ocr_model:
                try:
                    from core.llm import ModelManager

                    _mm = ModelManager()
                    _loaded = _mm.get_loaded_models()
                    if request.primary_ocr_model in _loaded:
                        log(
                            f"  🔓 Force-unloading OCR model "
                            f"'{request.primary_ocr_model}' before pre-warming "
                            f"summariser (frees VRAM)…",
                            "INFO",
                        )
                        _mm.force_unload(request.primary_ocr_model)
                except Exception as e:
                    log(f"  ℹ️ OCR pre-unload skipped: {e}", "DEBUG")

            def _prewarm():
                try:
                    from core.llm import ModelManager, ModelType

                    mm = ModelManager()
                    if mm.is_running() and mm.model_exists(request.summarisation_model):
                        log(
                            f"  🔥 S19: Pre-warming summarisation model "
                            f"'{request.summarisation_model}'…",
                            "INFO",
                        )
                        mm.acquire_model(
                            request.summarisation_model,
                            model_type=ModelType.SUMMARISATION,
                            skip_vram_check=True,
                        )
                        log(
                            f"  ✅ S19: Pre-warmed '{request.summarisation_model}'",
                            "DEBUG",
                        )
                except Exception as e:
                    log(f"  ℹ️ S19: Pre-warm skipped: {e}", "DEBUG")

            threading.Thread(target=_prewarm, daemon=True).start()

    return OutputSaveResult(
        book_title=book_title,
        detected_lang=detected_lang,
        source_name=source_name,
        segments_folder=segments_folder,
    )
