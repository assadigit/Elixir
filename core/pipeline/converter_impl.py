"""
Main conversion orchestrator.

NEW in this version:
  - TOC extraction step added before segmentation.
  - Page‑range selection: if page_range_start/end are set, only pages within
    that range are processed (OCR, markdown, segmentation, summaries).
  - Chapter selection: if selected_chapters is provided, only segments whose
    heading matches one of the selected titles are kept.
  - Advanced document handling:
    * Table extraction (Camelot or Tabula)
    * Math formula extraction (Pix2Tex or LaTeX-OCR)
    * Layout analysis (LayoutParser)
  - FIX: TOC entries are now correctly passed to the Segmenter.
  - Added debug logging for TOC entries.
  - NEW: ContentFilter integration – filters out non‑content pages (TOC, index,
    copyright, etc.) before summarisation to save tokens and improve quality.
  - FIX: Pre‑locate TOC headings before segmentation to avoid expensive
    repeated fuzzy matching (speed fix).
  - FIX: page_markers sorted to ensure binary search works correctly.
  - ENHANCED: Chapter selection with full debug logging – shows comparisons.
  - ENHANCED: Content filter re‑enabled with increased min_chars.
  - ENHANCED: Chapter selection uses fuzzy matching (rapidfuzz) and ellipsis stripping.
  - NEW: filter_segment_content now uses token‑based fallback (never < 100 tokens).
  - NEW: ContentFilter instantiated with min_content_chars=80 (was 200) and
    toc_density_threshold=0.40 (was 0.35) for more permissive filtering.
  - NEW: Source Type support – "normal_book", "academic_paper", "catalogue".
  - NEW: Layout Reorder for Academic Papers using pdfplumber or PyMuPDF.
  - NEW: Quick Mode – three checkboxes control which summary parts are output.
  - NEW: Content filter is now optional – controlled by enable_content_filter flag.
  - NEW: Academic Rigor flag passed to summarizer.
  - NEW: Sprint 2 – Simplified Keypoints Digest integration.
  - NEW: Sprint 3 – Vision OCR for Figures integration.
    * After layout reorder and before segmentation, if extract_figure_text is True,
      uses VisionFigureExtractor to extract text from images (graphs, diagrams).
    * Inserts extracted text as blockquotes into the markdown.
  - NEW: Phase 5 – status_callback passed to OCRService for UI progress updates.
"""

import re
import threading
import time as _time_mod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

# V18.19.2.0 (Debt D4): the three eager `from core.summarisation import ...`
# lines (Summarizer, KeypointsBuilder, SimplifiedKeypointsBuilder) were moved
# LAZY into convert() to break the controller→pipeline→converter→
# core.summarisation→summarizer→postchecks circular import. Summarizer was a
# dead import here (summarization delegates to conversion.summarization).
from core.docx.builder import DocxBuilder
from core.models import (
    ConversionRequest,
    ConversionResult,
    PdfAnalysisResult,
    PdfRecommendation,
    Segment,
    SummaryResult,
)

# ── NEW: Advanced feature imports ──────────────────────────────────────────
# ── NEW: Content filtering for summarisation ──────────────────────────────
# ── NEW: Layout reorder for Academic Papers ───────────────────────────────
# ── NEW: Sprint 2 – Simplified Keypoints Digest ────────────────────────────
# V18.19.2.0 (Debt D4): SimplifiedKeypointsBuilder import moved LAZY (inside convert()).
# Was: from core.summarisation import SimplifiedKeypointsBuilder
# ── NEW: Sprint 3 – Vision OCR for Figures ────────────────────────────────
from core.pdf import (
    ContentFilter,
)
from core.postprocess.page_marker import (
    extract_page_markers,
)
from utils.file_utils import create_output_folder
from utils.logging import ConversionLogger, get_main_logger
from utils.settings import Settings
from utils.text_utils import detect_persian_text

# Try to import rapidfuzz for fuzzy matching
try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    fuzz = None
    RAPIDFUZZ_AVAILABLE = False

logger = get_main_logger()


def compute_pages_processed(
    selected_pages: set | None,
    page_range_start: int | None,
    page_range_end: int | None,
    effective_start_page: int,
    effective_end_page: int,
    effective_total_pages: int,
    total_pages: int,
) -> int:
    """V18.20.3.6: the honest ``pages_processed`` for the completion modal.

    ``ConversionResult.pages_processed`` used to be filled with
    ``analysis.total_pages`` — the WHOLE PDF's page count — so converting a
    single 18-page chapter of a 397-page book reported "Pages processed:
    397".  The rule below reports the most specific page set the user
    actually asked for, in precedence order:

      1. ``selected_pages`` — the explicit chapter/page-range selection
         (manual segments or TOC-derived chapter ranges, BEFORE the ±1
         boundary overlap).  When a page range is ALSO set, the two are
         intersected (extraction already filters OCR results to the range).
      2. the effective page range (``page_range_start/end``) — its size.
      3. otherwise — the whole document's page count (previous behaviour).

    Pure page arithmetic: works for any book, any chapter, any range — no
    chapter-specific logic anywhere.
    """
    if selected_pages is not None:
        if page_range_start is not None or page_range_end is not None:
            return len(
                {p for p in selected_pages if effective_start_page <= p <= effective_end_page}
            )
        return len(selected_pages)
    if page_range_start is not None or page_range_end is not None:
        return effective_total_pages
    return total_pages


class Converter:
    def __init__(
        self,
        request: ConversionRequest,
        progress_callback: Callable[[float], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
        log_callback: Callable[[str, str], None] | None = None,
        cancel_event: threading.Event | None = None,
    ):
        self.request = request
        self.progress_callback = progress_callback or (lambda p: None)
        self.status_callback = status_callback or (lambda msg: None)
        self.log_callback = log_callback or (lambda msg, level: None)
        self.cancel_event = cancel_event or threading.Event()
        self.settings = Settings()

        self.output_dir = create_output_folder(
            request.output_dir, request.input_path.stem, per_book=True
        )
        # Organised subfolders (goal #6).  self.paths is the single
        # resolver; the legacy attribute names below are kept (pointing into
        # subfolders) so the ~30 downstream references keep working unchanged.
        from core.pipeline.output_paths import OutputPaths

        self.paths = OutputPaths(self.output_dir, request.input_path.stem)
        self.full_markdown_path = self.paths.full_markdown
        self.temp_markdown_path = self.paths.temp_markdown
        self.chapters_folder = self.paths.chapters_dir
        self.chunks_folder = self.paths.chunks_dir
        self.docx_path = self.paths.docx
        self.summary_md_path = self.paths.book_summary
        self.conv_logger = ConversionLogger(self.output_dir, request.input_path.stem)

        # ── Get poppler_path for advanced features ────────────────────────
        self._poppler_path = self.settings.get("paths.poppler") or None

        # ── NEW: Initialise content filter with academic awareness ────────
        # The filter is instantiated regardless, but only applied if enable_content_filter is True.
        self.content_filter = ContentFilter(
            min_content_chars=80,
            toc_density_threshold=0.40,
            is_academic=self.request.source_type == "academic_paper",
            log_callback=self._log,
        )

        # V18.2.14 (M4): ``_partial_failures`` moved from CLASS attr (shared
        # across instances — failures leaked between conversions) to INSTANCE
        # attr (fresh per instance). The old ``hasattr`` mitigation in
        # ``_record_partial_failure`` is now a traceable WARNING fallback.
        self._partial_failures: list[str] = []

    def _log(self, message: str, level: str = "INFO"):
        # V10.4.0 (Phase 6B-2): Structured-logging bridge.
        # Every ``self._log(...)`` call across the converter (283 call sites)
        # now ALSO emits a structured JSON record to structured.jsonl, with
        # the book name + phase context folded into ``extra``.  This gives
        # machine-parseable logs for the entire conversion without rewriting
        # the 283 call sites — the human-readable .conversion.log.md and the
        # GUI log viewer still work exactly as before via conv_logger +
        # log_callback.
        try:
            from utils.logging import get_structured_logger

            slog = get_structured_logger("Elixir.converter")
            log_level = getattr(__import__("logging"), level.upper(), None)
            if log_level is None:
                log_level = 20  # INFO
            slog.log(
                log_level,
                message,
                extra={
                    "book": getattr(self, "_book_name", None)
                    or getattr(self.request, "input_path", None)
                    and self.request.input_path.stem,
                    "phase": getattr(self, "_current_phase", None),
                },
            )
        except Exception as _e:
            # Structured logging is best-effort — never break conversion.
            # V18.1 (P9): surface unexpected structured-logging failures at
            # WARNING (with traceback) so they don't silently disappear
            # into the debug log. The downstream ``conv_logger.log`` /
            # ``log_callback`` calls below are NOT affected — the
            # human-readable log path keeps working even if structured
            # logging is broken.
            logger.warning(
                "structured log write failed: %s: %s",
                type(_e).__name__,
                _e,
                exc_info=True,
            )
        self.conv_logger.log(message, level)
        self.log_callback(message, level)

    def _update_progress(self, value: float):
        self.progress_callback(min(1.0, max(0.0, value)))

    def _update_status(self, message: str):
        self.status_callback(message)

    def _cancel_requested(self, phase: str) -> bool:
        """V18.20.2.0 (SWOT A15): post-summarization phase-gate cancel check.

        Mirrors the established gate idiom (extraction.py:388,
        segmentation.py:213, summarization.py:93) but for the phases AFTER
        summarization, where a cancel must SKIP the phase cleanly instead
        of returning early — the partial summaries already saved to disk
        still need to flow into the final ConversionResult (reported as
        cancelled via the existing plumbing: success=False +
        error_msg="Cancelled by user").  Skipped phases are left out of
        the checkpoint entirely (pending, not done/skipped) so a resume
        re-runs them.
        """
        if self.cancel_event.is_set():
            self._log(f"  ⏹️ Cancelled — skipping {phase}", "WARNING")
            return True
        return False

    @staticmethod
    def _sanitize_filename(heading: str) -> str:
        """V6.0.0 Fix 5: Sanitize a chapter heading for use as a filename.

        Removes characters that are illegal in Windows filenames (: ? * < > | " \\ /)
        and truncates to a reasonable length.
        """
        if not heading:
            return ""
        import re

        # Remove illegal characters
        safe = re.sub(r'[:?*<>|"\\/]', "", heading)
        # Collapse whitespace to underscores
        safe = re.sub(r"\s+", "_", safe.strip())
        # Truncate to 80 chars to avoid path length issues
        return safe[:80]

    @staticmethod
    def _get_app_version() -> str:
        """V10.1.2: Read the app version from the VERSION file.

        Single source of truth — the VERSION file at the project root is
        the canonical version.  This replaces the stale hardcoded strings
        ("7.5.1" / "8.0.0") that were lying in the conversion log header
        and diagnostic summary.  Falls back to "unknown" if the file can't
        be read (should never happen in a shipped build).
        """
        try:
            from pathlib import Path

            # The VERSION file lives at the project root, two levels up
            # from core/pipeline/converter.py → ../VERSION
            vpath = Path(__file__).resolve().parent.parent.parent / "VERSION"
            if vpath.exists():
                return vpath.read_text(encoding="utf-8").strip() or "unknown"
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return "unknown"

    def _log_conversion_settings(self) -> None:
        """V6.0.0 Fix 8 / Dump ALL request settings + environment +
        VRAM + provider/cloud + translation config to the conversion log.

        Verbosity is the point: this is the single most valuable diagnostic
        artifact when a conversion fails 4 hours in.  Every setting that
        could influence the outcome is logged at INFO (so it appears in the
        UI log viewer + the .conversion.log.md file).  Nothing here is
        secret (API keys are masked).

        V10.6.0 (Phase 8A-2): now delegates to
        ``core.pipeline.conversion.settings_logger.log_conversion_settings``.
        The inline 186-line implementation is replaced by a thin delegate
        that builds the context dict + calls the extracted function.  The
        extracted module is now an exact match for the inline version
        (including VRAM budget, page range, segmentation, post-processing,
        DOCX, output paths, and resume-status sections).
        """
        from core.pipeline.conversion.settings_logger import log_conversion_settings

        log_conversion_settings(
            ctx={
                "request": self.request,
                "settings": self.settings,
                "paths": self.paths,
                "output_dir": self.output_dir,
                "app_version": self._get_app_version(),
            },
            log=self._log,
        )

    def _get_user_override(self, analysis: PdfAnalysisResult) -> PdfRecommendation | None:
        scanned = len(analysis.scanned_pages)
        total = analysis.total_pages
        self._log(
            f"PDF analysis: {analysis.recommendation.value} — {scanned}/{total} pages are scanned",
            "INFO",
        )
        if analysis.scanned_pages:
            preview = analysis.scanned_pages[:10]
            suffix = "…" if len(analysis.scanned_pages) > 10 else ""
            self._log(f"  Scanned page numbers: {preview}{suffix}", "INFO")
        return None

    def _archive_stale_run_artifacts(self) -> None:
        """V0.05 (rig audit F7 — P2): move previous-run summary/log
        artifacts into ``_archive/<UTC-timestamp>/`` so nothing from an old
        run ships beside the current run's outputs.

        GENERAL rule (run-scoped output): the summaries dir and the logs dir
        may only contain THIS run's artifacts. At run start, any pre-existing
        ``*.summary.md`` / ``*.summary.docx`` (book-level and per-chapter)
        and ``*.log.md`` / ``drops.jsonl`` files are archived with their
        relative structure preserved. Skipped entirely when resume is
        enabled (resume deliberately reuses existing chapter summaries).
        Fail-soft: any error is swallowed (logged DEBUG) — archiving must
        never block a conversion.
        """
        from datetime import datetime as _dt

        try:
            _resume_on = bool(self.settings.get("summarisation.resume_enabled", False))
        except Exception:
            _resume_on = bool(getattr(self.request, "resume_enabled", False))
        if _resume_on:
            self._log(
                "  🗄️ V0.05: Resume enabled — stale-artifact archiving skipped "
                "(existing chapter summaries are reused).",
                "DEBUG",
            )
            return

        _root = Path(self.output_dir)
        if not _root.exists():
            return

        _patterns = ["*.summary.md", "*.summary.docx"]
        _candidates: list[Path] = []
        _summ = Path(self.paths.summaries_dir)
        if _summ.exists():
            _candidates.extend(p for pat in _patterns for p in _summ.rglob(pat))
        for _sub in ("logs",):
            _subdir = _root / _sub
            if _subdir.exists():
                _candidates.extend(_subdir.rglob("*.log.md"))
                _drops = _subdir / "drops.jsonl"
                if _drops.exists():
                    _candidates.append(_drops)
        # top-level conversion log (legacy flat location)
        _candidates.extend(_root.glob("*.conversion.log.md"))
        # never archive anything already inside _archive/
        _candidates = [
            p for p in _candidates if p.is_file() and "_archive" not in p.relative_to(_root).parts
        ]
        if not _candidates:
            return

        _stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
        _archive_dir = _root / "_archive" / _stamp
        _moved = 0
        for p in _candidates:
            try:
                _rel = p.relative_to(_root)
                _dest = _archive_dir / _rel
                _dest.parent.mkdir(parents=True, exist_ok=True)
                if _dest.exists():
                    continue
                p.rename(_dest)
                _moved += 1
            except Exception as _e:
                logger.debug("archive move skipped (%s): %s", p, _e)
        if _moved:
            self._log(
                f"  🗄️ V0.05: Archived {_moved} stale artifact(s) from previous "
                f"run(s) → _archive/{_stamp}/ — this folder now contains only "
                f"this run's outputs.",
                "INFO",
            )

    def _enforce_vram_budget(self) -> str | None:
        """V18.20.4.10 (P0-c): enforce ``local.vram_overbudget_policy``.

        Recomputes the same peak/total budget the settings block just
        logged and decides whether the conversion may start when the plan
        is overbudget (peak > total VRAM):

        - ``"proceed"``  → WARNING + continue (the old behaviour, now an
          explicit user choice).
        - ``"abort"``    → always abort with a clear error.
        - ``"ask"`` (default) → abort UNLESS the request carries an
          interactive acknowledgment (the wizard's "Proceed anyway"
          button sets ``request.vram_overbudget_acknowledged``). Queue
          and service-dialog starts cannot ask → they abort.

        Returns ``None`` to continue, or an error message to fail fast
        with (caller wraps it in a failed ConversionResult). Any internal
        failure of the check itself is fail-open with a DEBUG line — the
        budget calculator must never block a conversion it cannot compute
        (unchanged V7.1.0 semantics).
        """
        try:
            from core.vram_calculator import calculate_vram_budget, get_total_vram

            r = self.request
            _total_vram = get_total_vram()
            if not _total_vram:
                return None  # no GPU detected (CPU-only rig) — nothing to enforce
            estimates, peak, total, _rec = calculate_vram_budget(
                ocr_model=r.primary_ocr_model if r.use_llm_ocr else "",
                summarization_model=r.summarisation_model,
                fast_model=r.fast_model,
                heavy_model=r.heavy_model or "",
                translation_backend=(
                    self.settings.get("translation.backend", "")
                    if self.settings.get("translation.enabled")
                    else ""
                ),
                translation_model=self.settings.get("translation.model", ""),
                harakat_model=self.settings.get("translation.harakat_model", ""),
                judge_model=self.settings.get("translation.judge_model", ""),
                tts_enabled=r.output_tts,
                max_workers=r.max_workers,
            )
            if peak <= _total_vram:
                return None  # fits — nothing to enforce
            policy = str(self.settings.get("local.vram_overbudget_policy", "ask")).strip().lower()
            if policy == "proceed":
                self._log(
                    f"  ⚠️ VRAM OVERBUDGET (peak {peak:.1f} GB > {_total_vram:.1f} GB) "
                    f"— local.vram_overbudget_policy=proceed: continuing at "
                    f"explicit user choice (expect heavy CPU offload).",
                    "WARNING",
                )
                return None
            if policy == "ask" and getattr(r, "vram_overbudget_acknowledged", False):
                self._log(
                    f"  ⚠️ VRAM OVERBUDGET (peak {peak:.1f} GB > {_total_vram:.1f} GB) "
                    f"— acknowledged interactively by the user: continuing.",
                    "WARNING",
                )
                return None
            # abort (explicit) or ask-without-acknowledgment (non-interactive)
            self._log(
                f"  🛑 VRAM OVERBUDGET — ABORTING: peak {peak:.1f} GB > "
                f"{_total_vram:.1f} GB available (model '{r.summarisation_model}' "
                f"does not fit). A local model this large CPU-offloads at "
                f"~0.2 tokens/s — long chapters become hours-long map-reduce "
                f"stalls. Fix: use a smaller model (fits {_total_vram:.0f} GB), "
                f"or set local.vram_overbudget_policy='proceed' to force it, "
                f"or start from the wizard and click 'Proceed anyway'.",
                "ERROR",
            )
            return (
                f"VRAM overbudget: peak {peak:.1f} GB > {_total_vram:.1f} GB "
                f"available. Conversion aborted by "
                f"local.vram_overbudget_policy='{policy or 'ask'}' before any "
                f"work was done. Use a smaller model, or set "
                f"local.vram_overbudget_policy='proceed' to continue anyway."
            )
        except Exception as _e:
            logger.debug("VRAM budget enforcement skipped: %s", _e)
            return None

    def _derive_page_ranges_from_toc(
        self,
        toc_entries: list[tuple],
        selected_chapters: list[str],
        total_pages: int,
    ) -> set | None:
        """Derive a set of page numbers from TOC entries matching selected chapters.

        For each selected chapter title, find the corresponding TOC entry
        (using fuzzy word-overlap matching). The chapter's page range extends
        from its start page to the page before the next TOC entry's start page.

        Returns a set of page numbers, or None if no matches found.
        """
        if not toc_entries or not selected_chapters:
            return None

        # Sort TOC entries by page number
        sorted_toc = sorted(toc_entries, key=lambda x: x[1] if len(x) > 1 and x[1] else 0)

        def _normalize(s: str) -> set:
            """Extract lowercase word set for overlap matching."""
            return set(re.findall(r"[a-z0-9]+", s.lower()))

        def _match_score(selected_title: str, toc_heading: str) -> float:
            """Word-overlap match score between 0 and 1."""
            s_words = _normalize(selected_title)
            t_words = _normalize(toc_heading)
            if not s_words or not t_words:
                return 0.0
            # Use rapidfuzz if available for better fuzzy matching
            if RAPIDFUZZ_AVAILABLE:
                try:
                    return fuzz.token_set_ratio(selected_title.lower(), toc_heading.lower()) / 100.0
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
            # Fallback: Jaccard-like word overlap
            overlap = len(s_words & t_words)
            return overlap / max(len(s_words | t_words), 1)

        # For each selected chapter, find the best-matching TOC entry
        matched_indices = set()
        for selected in selected_chapters:
            best_idx = -1
            best_score = 0.0
            for idx, (heading, _page) in enumerate(sorted_toc):
                score = _match_score(selected, heading)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0 and best_score >= 0.3:
                matched_indices.add(best_idx)
                self._log(
                    f"  [TOC-Range] Matched '{selected[:50]}…' → "
                    f"'{sorted_toc[best_idx][0][:50]}…' (p.{sorted_toc[best_idx][1]}, score={best_score:.2f})",
                    "DEBUG",
                )

        if not matched_indices:
            self._log("  [TOC-Range] No TOC entries matched selected chapters.", "WARNING")
            return None

        # Build page ranges: each matched chapter spans from its start page
        # to the page before the NEXT TOC entry (any entry, not just matched).
        # V0.03 (P0-4, real-rig audit): dedupe SAME-PAGE entries first (keep
        # the first, mirroring _segment_by_chapters' convention). The raw
        # outline often places a metadata/author bookmark on the same page as
        # its chapter ("Act with Prudence" + "Seb Rose" both p.28); computing
        # next_start − 1 against the bookmark collapsed the chapter to ZERO
        # pages (start 28 > end 27 → guard dropped it silently) — the V0.02
        # false-success incident's root precondition.
        _deduped: list = []
        _last_page = None
        for _entry in sorted_toc:
            _page = _entry[1] if len(_entry) > 1 and _entry[1] else 0
            if _page == _last_page:
                continue
            _last_page = _page
            _deduped.append(_entry)
        valid_pages = set()
        for idx in sorted(matched_indices):
            start_page = sorted_toc[idx][1]
            # Find the next TOC entry (on a LATER page) after this one.
            end_page = total_pages
            for _entry in _deduped:
                _page = _entry[1] if len(_entry) > 1 and _entry[1] else 0
                if _page > start_page:
                    end_page = _page - 1
                    break
            # Clamp to valid range
            start_page = max(1, start_page)
            end_page = min(total_pages, end_page)
            if start_page <= end_page:
                for p in range(start_page, end_page + 1):
                    valid_pages.add(p)

        return valid_pages if valid_pages else None

    def _generate_quality_report(self, segments, summaries) -> None:
        """V3.4.0 H1: Generate a quality_report.json with quantitative metrics.

        Collects metrics throughout the pipeline and saves them as JSON for
        tracking quality trends across versions and identifying bottlenecks.
        """
        from datetime import datetime

        # Collect metrics
        report = {
            "version": "3.4.0",
            "timestamp": datetime.now().isoformat(),
            "book_title": self.request.input_path.stem.replace("_", " ").title(),
            "chapters": [],
            "totals": {
                "chapters_summarized": len(summaries),
                "total_bullets": 0,
                "total_concepts": 0,
                "avg_coverage": 0.0,
                "successful_summaries": 0,
                "failed_summaries": 0,
            },
        }

        total_coverage = 0.0
        total_bullets = 0
        total_concepts = 0

        for i, summ in enumerate(summaries, 1):
            chapter_data = {
                "chapter_index": i,
                "heading": summ.chapter_heading[:80],
                "success": summ.success,
                "bullet_count": len(summ.bullet_points) if summ.bullet_points else 0,
                "model_used": summ.model_used or "unknown",
                "input_tokens": summ.input_tokens,
                "output_tokens": summ.output_tokens,
                # V18.20.3.5: the deterministic recall-floor numbers measured
                # on the FINAL set (theorist recall + enumerated-conclusion
                # recall). Regex-measured — the honest complement to the
                # LLM judge's claim-recall (which overstates content recall
                # for long sources).
                "recall_floor": getattr(summ, "recall_floor", None) or {},
            }

            # Try to extract concepts for this chapter
            try:
                from core.summarisation.text_preprocessor import DeterministicPreprocessor

                pp = DeterministicPreprocessor()
                if i <= len(segments):
                    concepts = pp.extract_concepts(segments[i - 1].content)
                    # Also extract academic terms
                    try:
                        from core.summarisation.text_preprocessor import extract_all_concepts

                        concepts = extract_all_concepts(segments[i - 1].content)
                    except Exception as _e:
                        logger.debug("ignored %s: %s", type(_e).__name__, _e)
                    chapter_data["concept_count"] = len(concepts)
                    chapter_data["concepts"] = concepts
                    total_concepts += len(concepts)

                    # Check concept coverage
                    all_summary = f"{summ.executive_summary} {' '.join(summ.bullet_points or [])} {summ.thorough_summary}".lower()
                    covered = [c for c in concepts if c.lower() in all_summary]
                    chapter_data["concepts_covered"] = len(covered)
                    chapter_data["concepts_uncovered"] = len(concepts) - len(covered)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

            # Compute coverage
            try:
                if i <= len(segments):
                    content = segments[i - 1].content
                    combined = f"{summ.executive_summary} {' '.join(summ.bullet_points or [])} {summ.thorough_summary}"
                    # Quick coverage estimate
                    from core.summarisation.text_preprocessor import extract_ngram_keywords

                    keywords = extract_ngram_keywords(content, n=18)
                    if keywords:
                        found = sum(1 for k in keywords if k in combined.lower())
                        chapter_data["coverage"] = found / len(keywords)
                        total_coverage += chapter_data["coverage"]
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

            total_bullets += chapter_data["bullet_count"]
            # Fix 4: a chapter with 0 bullets AND < 100 input_tokens
            # is a hallucinated essay (empty input → LLM fabricated content).
            # Mark as failed, not success.
            if (
                summ.success
                and chapter_data["bullet_count"] == 0
                and chapter_data["input_tokens"] < 100
            ):
                chapter_data["success"] = False
                chapter_data["error"] = "Empty input — summary likely hallucinated"
                self._log(
                    f"  ⚠️ Quality report: Chapter {i} '{summ.chapter_heading[:40]}' "
                    f"has 0 bullets + {chapter_data['input_tokens']} input tokens — "
                    f"marking as FAILED (hallucination risk)",
                    "WARNING",
                )
                report["totals"]["successful_summaries"] = (
                    report["totals"].get("successful_summaries", 0) - 1
                    if not summ.success
                    else report["totals"].get("successful_summaries", 0)
                )
                report["totals"]["failed_summaries"] = (
                    report["totals"].get("failed_summaries", 0) + 1
                )
            elif summ.success:
                report["totals"]["successful_summaries"] += 1
            else:
                report["totals"]["failed_summaries"] += 1

            report["chapters"].append(chapter_data)

        # Compute averages
        if summaries:
            report["totals"]["avg_coverage"] = total_coverage / len(summaries)
        report["totals"]["total_bullets"] = total_bullets
        report["totals"]["total_concepts"] = total_concepts
        # V18.20.3.5 (audit v182034): aggregate the deterministic recall
        # floor across chapters — the end-of-conversion diagnostic prints
        # THESE numbers (the old block read non-existent keys
        # 'coverage_percent'/'avg_similarity' and always printed "?").
        try:
            _rf_chapters = [(c.get("recall_floor") or {}) for c in report["chapters"]]
            _t_total = sum(int(r.get("theorists_total", 0)) for r in _rf_chapters)
            _t_cov = sum(int(r.get("theorists_covered", 0)) for r in _rf_chapters)
            _c_total = sum(int(r.get("conclusion_items_total", 0)) for r in _rf_chapters)
            _c_cov = sum(int(r.get("conclusion_items_covered", 0)) for r in _rf_chapters)
            report["totals"]["recall_floor"] = {
                "theorists_covered": _t_cov,
                "theorists_total": _t_total,
                "theorists_pct": round(_t_cov / _t_total, 4) if _t_total else None,
                "conclusion_items_covered": _c_cov,
                "conclusion_items_total": _c_total,
                "conclusion_items_pct": round(_c_cov / _c_total, 4) if _c_total else None,
            }
        except Exception as _rf_agg_e:  # pragma: no cover — report must build
            logger.debug("recall-floor aggregation failed: %s", _rf_agg_e)

        # Save
        report_path = self.paths.quality_report
        # V18.20.2.0 (SWOT A30): atomic write — a crash mid-write previously
        # left a truncated quality_report.json that broke the A/B comparison
        # reader and the diagnostic summary.  atomic_write_json creates the
        # parent dir (replaces the lazy mkdir) and serializes identically
        # (indent=2, ensure_ascii=False).
        from utils.atomic_io import atomic_write_json

        atomic_write_json(report_path, report, indent=2, ensure_ascii=False)
        self._log(f"  📊 Quality report → {report_path}", "INFO")

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

    def _detect_language(self, text: str) -> str:
        return "fa" if detect_persian_text(text, threshold=0.15) else "en"

    def _strip_page_markers(self, text: str) -> str:
        text = re.sub(r"<!-- original page \d+ -->\s*\n?", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _make_frontmatter(self, meta: dict[str, Any]) -> str:
        lines = ["---"]
        for key, value in meta.items():
            if isinstance(value, str):
                safe = value.replace('"', '\\"')
                lines.append(f'{key}: "{safe}"')
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{key}: []")
                else:
                    lines.append(f"{key}:")
                    for item in value:
                        lines.append(f'  - "{item}"' if isinstance(item, str) else f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
        lines += ["---", ""]
        return "\n".join(lines)

    def _chapter_frontmatter(self, seg, idx, total, book_title, source_name, language) -> str:
        import re as _re

        _STOP = frozenset(
            {
                "the",
                "a",
                "an",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "and",
                "or",
                "but",
                "is",
                "it",
                "its",
                "this",
                "that",
                "was",
                "are",
                "were",
                "have",
                "has",
                "had",
                "with",
                "from",
                "by",
                "as",
                "not",
                "they",
                "we",
                "you",
                "which",
                "who",
                "also",
                "can",
                "will",
                "their",
                "about",
            }
        )
        _words = _re.findall(r"\b[a-z]{4,}\b", seg.content.lower())
        _freq: dict = {}
        for w in _words:
            if w not in _STOP:
                _freq[w] = _freq.get(w, 0) + 1
        _tags = sorted(_freq, key=lambda w: _freq[w], reverse=True)[:6]

        from utils.token_counter import count_tokens as _ct

        return self._make_frontmatter(
            {
                "title": seg.heading,
                "book": book_title,
                "source_file": source_name,
                "chapter_index": f"{idx} of {total}",
                "chapter_number": idx,
                "start_page": seg.start_page,
                "end_page": seg.end_page,
                "page_count": max(0, seg.end_page - seg.start_page + 1),
                "segment_type": seg.segment_type,
                "language": language,
                "word_count": len(seg.content.split()),
                "token_count": _ct(seg.content),
                "source_type": self.settings.get("source_type", "normal_book"),
                "tags": _tags,
                "doc_type": "book_chapter",
                "date_processed": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )

    def _book_frontmatter(
        self, total_pages, total_chapters, source_name, book_title, language
    ) -> str:
        return self._make_frontmatter(
            {
                "title": book_title,
                "source_file": source_name,
                "total_pages": total_pages,
                "total_chapters": total_chapters,
                "language": language,
                "doc_type": "book",
                "rag_format": self.settings.get("rag.target_format", "chromadb"),
                "date_processed": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )

    def _summarisation_progress(self, fraction: float, status: str):
        # Summarization gets 55% of the bar (0.25-0.80) since it's
        # the longest phase. Was 0.70-0.90 (20%) which was backwards.
        self._update_progress(0.25 + fraction * 0.55)
        self._update_status(status)

    # ─────────────────────────────────────────────────────────────────────────
    # Content Filtering for Summarisation – NEW: conditional
    # ─────────────────────────────────────────────────────────────────────────

    def _filter_segment_content(self, seg: Segment) -> str:
        """
        Apply content filter to a segment with safety fallback.
        Uses the new filter_segment_content method which guarantees at least
        100 tokens of content.
        """
        return self.content_filter.filter_segment_content(
            seg.content, start_page=seg.start_page, end_page=seg.end_page, min_tokens_keep=100
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Chapter selection helper with fuzzy matching
    # ─────────────────────────────────────────────────────────────────────────

    def _match_chapter(self, heading: str, selected: str) -> bool:
        """V10.2.4: Strict chapter matching — number-based, not word-overlap.

        The old code used fuzzy word-overlap which matched "3.6 Cannabinoids"
        against "2.2 Memantine" because they share words like "Treatment".

        The new logic:
        1. Extract the chapter NUMBER (e.g., "3.6", "2.2.1") from both
           the selected title and the segment heading.
        2. If both have numbers, match ONLY on the number.
        3. If no numbers, match on the first 5 significant words (not
           common words like "Treatment", "Acute", "Preventive").
        4. Never match different chapter numbers.
        """
        heading_clean = heading.strip()
        selected_clean = selected.strip()

        def normalize(s):
            s = s.lower()
            s = re.sub(r"[^\w\s]", "", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        heading_norm = normalize(heading_clean)
        selected_norm = normalize(selected_clean)

        # 1. Exact match (normalised)
        if heading_norm == selected_norm:
            return True

        # 2. Extract chapter numbers (e.g., "3.6", "2.2.1", "1")
        def extract_chapter_number(s):
            # Match patterns like "3.6", "2.2.1", "1", "3.6 Cannabinoids"
            m = re.match(r"^(\d+(?:\.\d+)*)\s", s)
            if m:
                return m.group(1)
            return None

        heading_num = extract_chapter_number(heading_clean)
        selected_num = extract_chapter_number(selected_clean)

        if heading_num and selected_num:
            # Both have numbers — match ONLY on the number
            if heading_num == selected_num:
                return True
            # Also check if the selected number is a prefix (e.g., "2" matches "2.1")
            # But only if the selected number is SHORTER AND followed by a dot
            # V13.33.5: Fixed substring bug — "1" was matching "10", "11", "12"
            # because "1" is a substring of "10". Now requires the heading number
            # to start with selected_num + "." (e.g., "2." in "2.1") for parent
            # chapter matching.
            if heading_num.startswith(selected_num + ".") and len(selected_num) < len(heading_num):
                return True
            # Numbers don't match — definitely not the same chapter
            return False

        # 3. No chapter numbers — match on significant words only
        # Exclude common academic words that appear in every title
        _COMMON = {
            "chapter",
            "part",
            "section",
            "appendix",
            "the",
            "of",
            "a",
            "an",
            "and",
            "or",
            "to",
            "in",
            "for",
            "with",
            "on",
            "at",
            "by",
            "from",
            # Common academic title words that should NOT be used for matching:
            "treatment",
            "acute",
            "preventive",
            "prevention",
            "study",
            "evidence",
            "trial",
            "clinical",
            "practice",
            "review",
            "introduction",
            "conclusion",
            "conclusions",
            "future",
            "therapeutics",
            "management",
            "therapy",
            "drug",
            "drugs",
            "migraine",
            "headache",
            "pain",
            "receptor",
            "antagonist",
            "agonist",
            "inhibition",
            "action",
            "mode",
            "proposed",
        }
        heading_words = {w for w in heading_norm.split() if len(w) > 2 and w not in _COMMON}
        selected_words = {w for w in selected_norm.split() if len(w) > 2 and w not in _COMMON}

        if heading_words and selected_words:
            overlap = heading_words & selected_words
            # V18.3.1 (P2): relaxed the word-overlap rule from "ALL" to
            # "majority" for 3+ word selections. The original V10.2.4 rule
            # required ALL selected significant words to appear — this was too
            # strict for books where the segmenter renamed chapters (e.g.
            # "Chapter 2: Confidence Building" → "Part Two: Building Trust
            # and Confidence" — 2 of 3 significant words overlap, was rejected).
            #
            # New rule:
            #   - 1-2 word selections: still require ALL (prevents 1-2 word
            #     false positives like "Cannabinoids" matching "Memantine").
            #   - 3+ word selections: require max(3, len//2) overlap words —
            #     at least 3 words OR half the selected words, whichever is
            #     more. This is conservative enough to avoid false positives
            #     but loose enough to handle minor renames.
            if len(selected_words) <= 2:
                # Small selection: require ALL words (original strict rule)
                if len(overlap) == len(selected_words) and len(selected_words) >= 2:
                    return True
                if len(selected_words) == 1 and overlap == selected_words:
                    return True
            else:
                # 3+ word selection: require majority (≥ max(3, half))
                _threshold = max(3, len(selected_words) // 2)
                if len(overlap) >= _threshold:
                    return True

        # 4. Fuzzy ratio — only as a last resort, very strict (95%)
        if RAPIDFUZZ_AVAILABLE:
            score = fuzz.token_set_ratio(heading_norm, selected_norm)
            if score >= 95:
                return True

        return False

    # ─────────────────────────────────────────────────────────────────────────

    def _build_error_result(self, error_msg: str) -> ConversionResult:
        """V10.1.5: Build a ConversionResult for a pre-flight failure."""
        return ConversionResult(
            success=False,
            error_msg=error_msg,
            pages_processed=0,
            chapters_detected=0,
            chunks_created=0,
            summaries_generated=0,
        )

    # V10.34.0 (Sprint 6.10): Track partial failures for the success modal.
    # Before V10.34.0, sub-system failures (screenshots, citation graph,
    # table extraction, footnotes, library tracking) were logged at DEBUG
    # and silently dropped.  Now they're collected in _partial_failures
    # and surfaced in the ConversionResult.warnings list so the user sees
    # "⚠️ 3 sub-systems had partial failures" in the success modal.
    #
    # V18.2.14 (M4): The class-level ``_partial_failures: List[str] = []``
    # was REMOVED — it was a shared mutable default that leaked failures
    # across Converter instances. The list is now initialized per-instance
    # in ``__init__`` (see above). This stub comment documents the history;
    # no attribute is declared here.

    def _record_partial_failure(self, subsystem: str, error: Exception) -> None:
        """V10.34.0 (Sprint 6.10): Record a sub-system failure for the success modal.

        V18.2.14 (M4): Removed the ``hasattr`` defensive re-init —
        ``_partial_failures`` is now guaranteed to exist on every instance
        (initialized in ``__init__``). If it somehow doesn't, we log a
        WARNING with a full traceback rather than silently re-creating it.
        """
        msg = f"{subsystem}: {type(error).__name__}: {error}"
        self._log(f"  ⚠️ Partial failure — {msg}", "WARNING")
        if not hasattr(self, "_partial_failures"):
            # V18.2.14 (M4): This branch should never execute (init guarantees
            # the attr). If it does, log a traceable WARNING so we can find
            # the code path that bypassed __init__.
            logger.warning(
                "_partial_failures missing on Converter instance (subsystem=%s) "
                "— initializing defensively. This indicates __init__ was "
                "bypassed; please report this code path.",
                subsystem,
                exc_info=True,
            )
            self._partial_failures = []
        self._partial_failures.append(msg)

    def _cross_chapter_dedup(self, summaries: list[SummaryResult]) -> list[SummaryResult]:
        """V10.13.0 (D4): Remove near-duplicate bullets across chapters.

        The B3 multi-sample dedup only deduplicates within a single chapter.
        This pass deduplicates ACROSS chapters: if the same concept appears
        in chapter 1 and chapter 3 (as a near-duplicate bullet), it's kept
        in chapter 1 (first occurrence) and removed from chapter 3.

        V10.32.0 (Sprint 4 s2): Delegates to ``DedupService.cross_chapter_dedup``
        — the unified dedup implementation.  One algorithm, one threshold,
        one log.  The cross-chapter threshold is 80% (slightly higher than
        within-chapter's 75% — cross-chapter duplicates are more likely to
        be genuine overlap, not paraphrases).
        """
        from core.summarisation.dedup_service import CROSS_CHAPTER_THRESHOLD, DedupService

        chapter_bullets = [
            (s.chapter_heading, [str(b) for b in s.bullet_points])
            for s in summaries
            if s.bullet_points
        ]
        svc = DedupService(log_callback=self._log)
        deduped = svc.cross_chapter_dedup(chapter_bullets, threshold=CROSS_CHAPTER_THRESHOLD)
        # Write back the deduplicated bullet lists
        idx = 0
        for summ in summaries:
            if summ.bullet_points:
                summ.bullet_points = deduped[idx][1]
                idx += 1
        return summaries

    # ─────────────────────────────────────────────────────────────────────────
    # Garbled text detection: moved to utils/text_quality.py (V10.2.6)
    # Remaining methods: _re_extract_with_ocr, _targeted_ocr_repair
    # ─────────────────────────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────────────────
    # _find_garbled_ranges, _find_partial_garbled_ranges, _merge_ranges:
    # moved to utils/text_quality.py (V10.2.6)
    # ─────────────────────────────────────────────────────────────────────────

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

    def convert(self) -> ConversionResult:
        _t_start = _time_mod.time()

        def _elapsed() -> str:
            return f"{_time_mod.time() - _t_start:.1f}s"

        self._log("🚀 Starting conversion…", "SUCCESS")
        self._update_status("Initialising…")

        # V18.20.3.9 (Phase 3.a / C1): reset the per-call LLM telemetry
        # registry so the end-of-run diagnostic aggregates exactly THIS
        # run's calls (records are process-wide otherwise — a second
        # conversion in the same session would double-count).
        try:
            from core.llm.call_meta import reset_call_telemetry

            reset_call_telemetry()
        except Exception as _e:
            logger.debug("telemetry reset ignored: %s", _e)

        # V18.20.3.10 (O7): snapshot the opt-in response-cache stats so the
        # end-of-run diagnostic can report THIS run's hits/misses (the
        # singleton's counters are process-wide, like the telemetry above).
        self._cache_stats_start = None
        try:
            from core.llm.response_cache import response_cache

            self._cache_stats_start = response_cache.stats()
        except Exception as _e:
            logger.debug("response cache snapshot ignored: %s", _e)

        # V10.13.0 (A5): Pre-flight dependency check — verify all required
        # optional deps are importable BEFORE starting a 90-min conversion.
        # Fails fast with a clear message instead of crashing 7 min in.
        from core.system.preflight_check import run_preflight_check

        _missing = run_preflight_check(self.request, log_callback=self._log)
        if _missing:
            return ConversionResult(success=False, error_msg=_missing)

        # Log ALL conversion settings at the start for diagnostics
        self._log_conversion_settings()

        # V0.05 (rig audit F7 — P2): RUN-SCOPED OUTPUT. The output folder
        # previously mixed runs — the V0.04 rig's folder shipped V0.02
        # chapter summaries, a stale book-level summary, and an old
        # conversion log beside the new run's files, and the audit's first
        # pass mis-attributed evidence because of it. GENERAL rule: nothing
        # from a previous run ever ships beside a new run's outputs — at run
        # start, pre-existing summary/log artifacts are moved to
        # ``_archive/<UTC-timestamp>/`` with one log line. Skipped when
        # resume is enabled (the resume path deliberately reuses existing
        # chapter summaries).
        try:
            self._archive_stale_run_artifacts()
        except Exception as _e:
            logger.debug("stale-artifact archive ignored: %s: %s", type(_e).__name__, _e)

        # V18.20.4.10 (P0-c): enforce the VRAM budget. The V18.20.4.9
        # behaviour was warn-and-continue: the settings block printed
        # "❌ OVERBUDGET: Peak VRAM 20.2 GB exceeds available 12.0 GB" and
        # the pipeline started anyway (the wizard's only dialog defaulted
        # to OK; queue/service starts had no gate at all). A 20.2 GB model
        # on a 12 GB card CPU-offloads at ~0.2 tok/s — every long chapter
        # becomes an hours-long map-reduce (the 97-Things stall). Now the
        # configured policy (local.vram_overbudget_policy) decides:
        # "proceed" → continue (explicit user choice), "abort" → fail
        # fast, "ask" (default) → fail fast UNLESS an interactive user
        # already acknowledged the overbudget plan (the wizard stamps
        # request.vram_overbudget_acknowledged on "Proceed anyway").
        _vram_err = self._enforce_vram_budget()
        if _vram_err:
            return ConversionResult(success=False, error_msg=_vram_err)

        # Disk-space pre-check — warn if the output drive has
        # less than 1 GB free (a big book with TTS can produce 500MB+).
        try:
            import shutil

            usage = shutil.disk_usage(self.output_dir)
            free_gb = usage.free / (1024**3)
            if free_gb < 1.0:
                self._log(
                    f"  ⚠️ Low disk space: {free_gb:.1f} GB free on {self.output_dir.anchor}. "
                    f"A big book with TTS/packets can produce 500MB+. "
                    f"Conversion may fail mid-way if disk fills up.",
                    "WARNING",
                )
            else:
                self._log(f"  💾 Disk space: {free_gb:.1f} GB free", "DEBUG")
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Track output generation results for graceful degradation summary
        self._output_results: dict[
            str, str
        ] = {}  # phase → "✅ done" / "❌ failed: msg" / "⏭️ skipped"

        # JudgeResult list from the Summarizer (Layer 8 grounding).
        # Populated after summarization; stays empty when grounding is off or
        # summarization is skipped.  Consumed by keypoints/flashcards/evidence-map.
        self._judge_results: list[Any] = []

        # Wire the checkpoint system — tracks phase completion so the
        # Output Scanner can report what ran, and future resume logic can skip
        # completed phases.  Created after the folder rename (which happens
        # later in convert()), so we init it here and set_output_dir later.
        from core.pipeline.checkpoint import Checkpoint

        # V13.25.0 (P1.1): Phase-level resume — load existing checkpoint
        # instead of always creating a fresh one. If a checkpoint exists
        # in the output dir with some phases done, those phases will be
        # skipped (see should_run() checks in the output runner).
        existing_cp = Checkpoint.load(self.output_dir)
        if existing_cp:
            self.checkpoint = existing_cp
            self.checkpoint.set_output_dir(self.output_dir)
            # Log what we're resuming from
            resume_point = self.checkpoint.get_resume_point()
            done_count = sum(1 for p in self.checkpoint.phases.values() if p.status == "done")
            if resume_point and done_count > 0:
                self._log(
                    f"  📋 Checkpoint loaded — resuming from '{resume_point}' "
                    f"({done_count} phase(s) already done)",
                    "INFO",
                )
            else:
                self._log("  📋 Checkpoint loaded (no phases to resume)", "DEBUG")
        else:
            self.checkpoint = Checkpoint(
                book_name=self.request.input_path.stem,
                input_path=str(self.request.input_path),
            )
            self.checkpoint.set_output_dir(self.output_dir)
            self._log(
                f"  📋 Checkpoint system initialized → {self.checkpoint.checkpoint_path}", "DEBUG"
            )

        try:
            # ── Steps 1–4: Extraction phase (V10.8.0 Phase 8C) ─────────────
            # The 238-line extraction block (analyse PDF, extract TOC, extract
            # text via OCR/markitdown, build raw markdown) is now a delegate
            # call to ``run_extraction`` in core.pipeline.conversion.extraction.
            # The extracted module returns an ExtractionResult (success) or a
            # ConversionResult (early exit: 0-page PDF or user cancel).
            from core.pipeline.conversion.extraction import (
                run_extraction as _run_extraction,
            )

            _extract = _run_extraction(converter=self)
            if isinstance(_extract, ConversionResult):
                return _extract  # early exit (0-page or cancel)
            analysis = _extract.analysis
            pages_to_ocr = _extract.pages_to_ocr
            effective_start_page = _extract.effective_start_page
            effective_end_page = _extract.effective_end_page
            effective_total_pages = _extract.effective_total_pages
            toc_entries = _extract.toc_entries
            # V18.20.3.6: the user's explicit page selection (chapter
            # selection / manual ranges), BEFORE the ±1 boundary overlap.
            # Drives the honest "Pages processed" number (modal +
            # diagnostic) — see compute_pages_processed above.
            selected_pages = _extract.selected_pages
            _pages_processed = compute_pages_processed(
                selected_pages=selected_pages,
                page_range_start=getattr(self.request, "page_range_start", None),
                page_range_end=getattr(self.request, "page_range_end", None),
                effective_start_page=effective_start_page,
                effective_end_page=effective_end_page,
                effective_total_pages=effective_total_pages,
                # In every no-range path (PDF + non-PDF) effective_total_pages
                # IS the whole-document count — analysis.total_pages by
                # construction — so the fallback needs no extra attr access.
                total_pages=effective_total_pages,
            )
            # V18.3.2 (P3-partial): store toc_entries on self so the summarization
            # phase can do page-based chapter matching as a fallback when the
            # heading-text matcher fails (e.g. segmenter renamed "Chapter 7" →
            # "Part One" but Chapter 7's page 93 falls within Part One's 92-107).
            self.toc_entries = toc_entries or []
            valid_pages = _extract.valid_pages
            raw_markdown = _extract.raw_markdown

            # ── Post-processing pipeline (V10.7.0 Phase 8B) ────────────────
            # The 348-line post-processing block (hyphenation repair, paragraph
            # joining, header/footer removal, figure/table extraction for
            # academic papers, targeted OCR repair for garbled sections,
            # content-type auto-detection, layout reorder, advanced document
            # handling, vision OCR for figures) is now a delegate call to
            # ``run_postprocess`` in core.pipeline.conversion.postprocess.
            # The extracted module is an exact match for the inline code;
            # the converter owns the pipeline flow + state, the module owns
            # the post-processing logic.
            from core.pipeline.conversion.postprocess import run_postprocess

            raw_markdown = run_postprocess(
                converter=self,
                raw_markdown=raw_markdown,
                analysis=analysis,
                pages_to_ocr=pages_to_ocr,
                effective_start_page=effective_start_page,
                effective_end_page=effective_end_page,
                valid_pages=valid_pages,
                toc_entries=toc_entries,
            )
            self._log(f"📝 Raw markdown: {len(raw_markdown):,} chars | [{_elapsed()}]", "INFO")
            # ── Step 5: Segment (V10.9.0 Phase 8D) ────────────────────────
            # The 103-line segmentation block (extract page markers, pre-locate
            # TOC headings, run Segmenter, update page markers, fallback single
            # segment, filter by selected chapters) is now a delegate call to
            # ``run_segmentation`` in core.pipeline.conversion.segmentation.
            # The extracted module returns SegmentationResult (success) or
            # ConversionResult (early exit: user cancel).
            from core.pipeline.conversion.segmentation import (
                log_segment_summary as _log_seg_sum,
            )
            from core.pipeline.conversion.segmentation import (
                run_segmentation as _run_seg,
            )

            _seg = _run_seg(
                converter=self,
                raw_markdown=raw_markdown,
                analysis=analysis,
                toc_entries=toc_entries,
            )
            if isinstance(_seg, ConversionResult):
                return _seg  # early exit (cancel)
            segments = _seg.segments
            page_markers = _seg.page_markers
            total_pages = _seg.total_pages
            # NOTE: raw_markdown is NOT deleted here — run_output_save (Step 6-8)
            # still needs it for book-title detection + full-markdown assembly.
            # It's deleted after run_output_save returns (the last user).
            # Log per-segment token summary (needs _elapsed(), a closure-local
            # timer — called here, not inside the extracted module).
            _log_seg_sum(self, segments, elapsed=_elapsed())

            # ── Steps 6–8: Clean + detect language + save output (V10.10.0 Phase 8E)
            # The 136-line block (clean segments, detect language, detect book
            # title + rename folder, assemble + write full markdown, write
            # per-segment files, mark checkpoint, S19 pre-warm) is now a
            # delegate call to ``run_output_save`` in
            # core.pipeline.conversion.output_save.  The extracted module
            # mutates converter state (output_dir, paths, conv_logger,
            # checkpoint) for the folder rename, and returns OutputSaveResult
            # (book_title, detected_lang, source_name).  The elapsed timer
            # string is passed as a param for the checkpoint mark_done call.
            from core.pipeline.conversion.output_save import (
                run_output_save as _run_save,
            )

            _save = _run_save(
                converter=self,
                segments=segments,
                raw_markdown=raw_markdown,
                effective_total_pages=effective_total_pages,
                total_pages=total_pages,
                elapsed=_elapsed(),
            )
            book_title = _save.book_title
            detected_lang = _save.detected_lang
            segments_folder = _save.segments_folder
            # Release raw_markdown — run_output_save was the last user (for
            # book-title detection + full-markdown assembly).  Summarization
            # doesn't need it (segments hold their own content copies).
            # This frees 50-100K chars of memory for the summarization phase.
            del raw_markdown

            # ── Step 9: Summarisation (V10.11.0 Phase 8F) ────────────────
            # The 476-line summarization orchestration block (force-unload OCR,
            # content filter, skip reference sections, ClaimExtractor, GPU
            # thermal profile + max_workers cap, ThermalSafetyController,
            # Summarizer with concept extraction, chapter resume, best-match
            # selection, incremental atomic save, judge_results stash) is now
            # a delegate call to ``run_summarization`` in
            # core.pipeline.conversion.summarization.  The extracted module
            # returns SummarizationResult (success) or ConversionResult (early
            # exit: cancel or thermal pre-flight fail).  The elapsed_fn param
            # passes the _elapsed closure for the "Summary phase starting" log.
            from core.pipeline.conversion.summarization import (
                run_summarization as _run_summ,
            )

            _summ = _run_summ(
                converter=self,
                segments=segments,
                segments_folder=segments_folder,
                detected_lang=detected_lang,
                book_title=book_title,
                elapsed_fn=_elapsed,
            )
            if isinstance(_summ, ConversionResult):
                return _summ  # early exit (cancel or thermal pre-flight fail)
            summaries = _summ.summaries

            # V10.13.0 (D4): Cross-chapter bullet dedup — remove near-duplicate
            # bullets that appear in multiple chapters BEFORE feeding to
            # keypoints/briefing/flashcards.  The B3 dedup only dedups within
            # a chapter; this pass dedups ACROSS chapters (same concept
            # mentioned in ch.1 and ch.3 → keep in ch.1 only).
            if len(summaries) > 1:
                summaries = self._cross_chapter_dedup(summaries)

            # ── Step 10: DOCX ────────────────────────────────────────────────
            docx_path = None
            if self.request.generate_docx and not self._cancel_requested("DOCX build"):
                self._update_status("Building DOCX report…")
                self._log(f"  ⏱️ DOCX phase starting | [{_elapsed()}]", "INFO")
                builder = DocxBuilder(self.request, log_callback=self._log)
                if builder.build_report(
                    summaries,
                    [{"heading": s.heading, "content": s.content} for s in segments],
                    self.request.input_path,
                    self.docx_path,
                ):
                    docx_path = self.docx_path

            # ── Keypoints (always when summaries exist) ───────────────────────
            keypoints_md_path = None
            keypoints_docx_path = None
            # V18.20.3.10 (W11): the DEDUPED keypoint count from the builder —
            # the library must record the number that actually shipped in
            # the keypoints file (36), not the raw bullet count (41).
            _kp_final_count = None
            if summaries and not self._cancel_requested("keypoints build"):
                self._update_status("Building Keypoints files…")
                # V18.19.2.0 (Debt D4): lazy import breaks the converter→core.summarisation
                # eager import cycle. KeypointsBuilder is only needed when summaries exist.
                from core.summarisation import KeypointsBuilder

                kp = KeypointsBuilder(log_callback=self._log)
                # Pass segments + concepts for J1 ordering, K1 confidence,
                # K2 source excerpts, H2 page traceability
                all_concepts = []
                try:
                    from core.summarisation.text_preprocessor import DeterministicPreprocessor

                    pp = DeterministicPreprocessor()
                    for seg in segments:
                        all_concepts.extend(pp.extract_concepts(seg.content))
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
                keypoints_md_path, keypoints_docx_path = kp.build(
                    summaries,
                    book_title=self.request.input_path.stem,
                    output_dir=self.paths.keypoints_dir,
                    segments=segments,
                    concepts=all_concepts,
                    judge_results=getattr(self, "_judge_results", None),
                )
                # V18.20.3.10 (W11): capture the deduped count for the
                # library record (falls back to the raw sum below when the
                # builder didn't run or predates the attribute).
                _kp_final_count = getattr(kp, "final_keypoint_count", None)
                if keypoints_md_path:
                    self._log(f"📌 Keypoints MD  → {keypoints_md_path}", "SUCCESS")
                if keypoints_docx_path:
                    self._log(f"📌 Keypoints DOCX → {keypoints_docx_path}", "SUCCESS")

            # ── NEW: Sprint 2 – Simplified Keypoints Digest ──────────────────
            # Robust error handling — if simplification model fails to
            # load or any error occurs, gracefully skip simplification instead
            # of crashing the entire pipeline. The keypoints (already generated)
            # are preserved. The user gets a clear warning instead of a crash.
            if (
                self.request.simplified_keypoints_enabled
                and summaries
                and not self._cancel_requested("simplified keypoints")
            ):
                self._update_status("Generating Simplified Keypoints Digest…")
                self._log("  📌 Generating simplified keypoints (jargon‑free digest)…", "INFO")
                try:
                    # V18.19.2.0 (Debt D4): lazy import breaks the eager import cycle.
                    from core.summarisation import SimplifiedKeypointsBuilder

                    builder = SimplifiedKeypointsBuilder(
                        request=self.request,
                        log_callback=self._log,
                    )
                    output_path = builder.build(
                        summaries=summaries,
                        book_title=book_title,
                        output_dir=self.paths.keypoints_dir,
                    )
                    if output_path:
                        self._log(f"  ✅ Simplified keypoints saved to: {output_path}", "SUCCESS")
                except (OSError, ConnectionError, TimeoutError) as e:
                    # Model load failure, Ollama connection error, timeout
                    self._log(f"  ⚠️ Simplification skipped (model unavailable): {e}", "WARNING")
                    self._log(
                        "  ℹ️ Keypoints and summaries are still available without simplification.",
                        "INFO",
                    )
                except Exception as e:
                    # Any other error — don't crash the pipeline
                    error_msg = str(e).lower()
                    if any(
                        kw in error_msg
                        for kw in (
                            "model",
                            "load",
                            "ollama",
                            "connection",
                            "timeout",
                            "memory",
                            "vram",
                        )
                    ):
                        self._log(
                            f"  ⚠️ Simplification skipped (infrastructure error): {e}", "WARNING"
                        )
                        self._log(
                            "  ℹ️ Keypoints and summaries are still available without simplification.",
                            "INFO",
                        )
                    else:
                        self._log(f"  ❌ Failed to generate simplified keypoints: {e}", "WARNING")

            # ── A4: Glossary Extraction ──────────────────────────────────
            # REMOVED in Glossary feature removed — dictionary-based
            # filtering could not reliably distinguish book jargon ("Focus Base")
            # from common phrases. The feature caused more frustration than value.
            # See CHANGELOG.md for details.

            self._update_progress(0.96)  # Simplified keypoints + DOCX done

            # ── Output Studio — opt-in output types ───────────────
            # Each output is gated by its own ConversionRequest flag and runs
            # only when enabled. All failures are graceful (logged at DEBUG)
            # so one broken output never crashes the conversion. The 3 V4.0.0
            # outputs (briefing/podcast/flashcards) are ON by default via the
            # settings layer; the 4 outputs are opt-in.
            #
            # V10.6.0 (Phase 8A-3): the 150-line inline output-studio loop is
            # now a delegate call to ``run_output_studio``.  The extracted
            # module handles the OUTPUT_PLAN, the per-output generate()
            # signature routing (evidence_map 4-arg, flashcards judge_results
            # kwarg), the verbose TTS diagnostics, and the packets extensions
            # (PDF/lecture/audio).  Failures are still graceful — each output
            # is wrapped in try/except inside the runner.
            if summaries and len(summaries) > 0 and not self._cancel_requested("output studio"):
                from core.pipeline.conversion.output_runner import run_output_studio

                self._output_results.update(
                    run_output_studio(
                        request=self.request,
                        summaries=summaries,
                        segments=segments,
                        book_title=book_title,
                        paths=self.paths,
                        log=self._log,
                        update_status=self._update_status,
                        judge_results=getattr(self, "_judge_results", None),
                        progress_callback=getattr(
                            self, "_output_progress_callback", None
                        ),  # V10.37.0
                        checkpoint=getattr(self, "checkpoint", None),  # V13.25.0 P1.1
                    )
                )

            # V10.21.0: Citation graph — extract [N] citations and build graph
            if not self._cancel_requested("citation graph"):
                try:
                    from core.outputs.citation_graph import generate_citation_graph

                    if hasattr(self, "temp_markdown_path") and self.temp_markdown_path.exists():
                        _raw_md = self.temp_markdown_path.read_text(encoding="utf-8")
                        generate_citation_graph(
                            summaries=summaries,
                            segments=segments,
                            raw_markdown=_raw_md,
                            book_title=book_title,
                            output_dir=self.paths.logs_dir.parent,
                            log_callback=self._log,
                        )
                except Exception as e:
                    self._record_partial_failure("Citation graph", e)

            # ── Validation ───────────────────────────────────────────────────
            warnings = []
            # Suppress page-count mismatch warning when chapter selection is
            # active — it's EXPECTED that only selected chapter pages are marked
            # (e.g. 41 of 174). Only warn when processing the full document.
            chapter_selection_active = (
                self.request.manual_segments is not None
                or self.request.selected_chapters is not None
            )
            if page_markers and len(page_markers) != total_pages and not chapter_selection_active:
                warnings.append(
                    f"Page count mismatch: {total_pages} expected, {len(page_markers)} marked."
                )
            if summaries:
                for summ in summaries:
                    if summ.success and not summ.bullet_points:
                        warnings.append(f"'{summ.chapter_heading[:40]}': no bullet points.")
            for w in warnings[:5]:
                self._log(f"  ⚠️ {w}", "WARNING")

            if self.temp_markdown_path.exists():
                self.temp_markdown_path.unlink()

            self._update_progress(1.0)

            # V18.2.4: Check if summarization actually produced any content.
            # Previously the pipeline reported "✅ Conversion complete" even
            # when ALL chapters failed (model returned empty). Now: if no
            # summaries have content, report failure.
            _valid_summaries = [
                s
                for s in summaries
                if s
                and getattr(s, "success", True)
                and (s.executive_summary or s.bullet_points or s.thorough_summary)
            ]
            _failed_count = len(summaries) - len(_valid_summaries) if summaries else 0
            _all_failed = summaries and len(_valid_summaries) == 0

            # V18.20.2.0 (SWOT A15): cancel-aware completion status.  A run
            # cancelled mid/after summarization previously logged
            # "✅ Conversion complete." and returned success=True even though
            # every downstream phase had (or should have) been skipped.
            _cancelled = self.cancel_event.is_set()

            # V0.02 (false-success RCA): ZERO chapters entered summarization.
            # The V18.2.4 guard above requires ``summaries`` to be non-empty —
            # when every segment is filtered out BEFORE the summarizer (the
            # real incident: the user's selected chapters were merged into a
            # 'Preface' segment, the front-matter skip dropped it),
            # ``summaries == []`` sailed past it into "✅ Conversion complete."
            # with empty outputs. With an explicit chapter selection that is a
            # hard failure (the user asked for specific chapters and got
            # nothing); without one it stays a success (markdown/DOCX are
            # still produced) but is announced with a loud WARNING instead
            # of silence.
            _zero_summaries = (
                not summaries and bool(self.request.generate_summaries) and not _cancelled
            )
            _selection_active = bool(self.request.selected_chapters)
            if _all_failed:
                self._update_status("Conversion FAILED — all chapters returned empty")
                self._log("❌ Conversion FAILED: all chapters returned empty responses.", "ERROR")
                self._log(
                    f"   {_failed_count} chapter(s) failed — model produced no content. "
                    f"Likely causes: model not installed, VRAM insufficient, or quantization "
                    f"too aggressive for the prompt complexity. "
                    f"Try: ollama pull <model>, or switch to a less aggressive quant (IQ2_M "
                    f"instead of IQ2_XXS), or raise temperature to 1.0.",
                    "ERROR",
                )
            elif _zero_summaries and _selection_active:
                self._update_status("Conversion FAILED — no selected chapters summarized")
                self._log(
                    f"❌ Conversion FAILED: none of the {len(self.request.selected_chapters)} "
                    f"selected chapter(s) produced a summary — the selection "
                    f"matched no summarizable section (every surviving segment "
                    f"was skipped as front/reference matter). No summary "
                    f"outputs were written.",
                    "ERROR",
                )
                self._log(
                    "   Try: re-open the chapter selector and re-pick chapters "
                    "(per-chapter author/annotation bookmarks are no longer "
                    "listed), or convert the whole book.",
                    "ERROR",
                )
            elif _zero_summaries:
                self._update_status("Conversion completed!")
                self._log("✅ Conversion complete.", "SUCCESS")
                self._log(
                    "   ⚠️ Zero sections were summarized — every segment was "
                    "skipped as front/reference matter while summaries were "
                    "requested. Markdown/DOCX outputs were still written; if "
                    "you expected chapter summaries, disable the content "
                    "filter or select chapters explicitly.",
                    "WARNING",
                )
            elif _cancelled:
                self._update_status("Conversion cancelled")
                self._log(
                    "⏹️ Conversion cancelled — partial summaries saved; downstream phases skipped.",
                    "WARNING",
                )
            else:
                self._update_status("Conversion completed!")
                self._log("✅ Conversion complete.", "SUCCESS")
                if _failed_count > 0:
                    self._log(
                        f"   ⚠️ {_failed_count} chapter(s) failed (empty response) — "
                        f"{len(_valid_summaries)} succeeded.",
                        "WARNING",
                    )

            # Output generation summary — show what succeeded/failed
            # Only show outputs that were actually requested + generated
            # with real content.  Skip outputs where the generator said "done"
            # but produced no content (e.g. "No chapter summaries to synthesize").
            if hasattr(self, "_output_results") and self._output_results:
                self._log("", "INFO")
                self._log("━━━ Output Generation Summary ━━━", "INFO")
                for phase, result in self._output_results.items():
                    # Check if this output was actually requested
                    _attr = phase
                    _is_requested = (
                        getattr(self.request, _attr, False)
                        if hasattr(self.request, _attr)
                        else True
                    )
                    if not _is_requested:
                        # Skip outputs that weren't requested
                        continue
                    self._log(f"  {phase}: {result}", "INFO")
                    # checkpoint — mark each output phase
                    if "✅" in result:
                        self.checkpoint.mark_done(phase)
                    elif "❌" in result:
                        self.checkpoint.mark_failed(phase, result)
                    elif "⏭️" in result:
                        self.checkpoint.mark_skipped(phase)
                self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")

            # Stop the thermal safety system IMMEDIATELY after
            # "Conversion complete" — before quality reports + diagnostic
            # summary.  This prevents the hardware monitor from continuing
            # to poll during the report generation (which delays the modal).
            _ts = getattr(self, "_thermal_safety", None)
            if _ts:
                _ts.stop()

            # Generate quality report JSON
            if not self._cancel_requested("quality report"):
                try:
                    self._generate_quality_report(segments, summaries)
                except Exception as e:
                    # V18.20.4.11 (P2 / W-a12): raised DEBUG → WARNING — the
                    # quality report now feeds the coverage chain (W-a2) and
                    # the end-of-conversion diagnostic summary; its failure
                    # is user-visible degradation, not an invisible detail.
                    self._log(f"  ⚠️ Quality report generation failed: {e}", "WARNING")

            # V10.17.0 (G4): A/B comparison disabled — produced an unused
            # JSON file that nobody reads. V18.20.4.7 (P5 / W-a13): the
            # retained-for-backward-compat method
            # ``_generate_ab_comparison`` was deleted (dead since V10.17.0;
            # zero live callers tree-wide — only this commented call site).

            # Thermal safety report (after reports, before diagnostic)
            if _ts:
                _ts.log_report()

            # End-of-conversion diagnostic summary — captures the
            # final state (counts, timings, output paths, warnings) so the
            # user can paste this block when reporting issues.  This is the
            # "gimmicks/nuances/micro-mistakes" snapshot the user asked for.
            # version header now reads from VERSION file (was stale
            # "V7.5.1" hardcoded).
            self._log("", "INFO")
            self._log(
                f"━━━ Elixir v{self._get_app_version()} Conversion Diagnostic Summary ━━━", "INFO"
            )
            self._log(f"  Book: {book_title}", "INFO")
            self._log(f"  Total pages: {total_pages}", "INFO")
            # V18.20.3.6: when a chapter selection / page range limited the
            # run, say so right next to the book total — the completion
            # modal reports the same number (previously it showed the whole
            # book's total for a single-chapter run, e.g. "397" for 18).
            if _pages_processed != total_pages:
                self._log(
                    f"  Pages processed: {_pages_processed} "
                    f"(selection active — {_pages_processed} of {total_pages} pages)",
                    "INFO",
                )
            self._log(
                f"  Segments: {len(segments)} "
                f"(chapters: {len([s for s in segments if s.segment_type == 'chapter'])}, "
                f"chunks: {len([s for s in segments if s.segment_type == 'chunk'])})",
                "INFO",
            )
            self._log(f"  Summaries generated: {len(summaries) if summaries else 0}", "INFO")
            if summaries:
                ok = sum(1 for s in summaries if s.success)
                failed = len(summaries) - ok
                total_bullets = sum(len(s.bullet_points) for s in summaries)
                self._log(
                    f"    Success: {ok}, Failed: {failed}, Total bullets: {total_bullets}", "INFO"
                )
                # Coverage stats from the quality report if available
                try:
                    import json as _json

                    qr = self.paths.quality_report
                    if qr.exists():
                        report = _json.loads(qr.read_text(encoding="utf-8"))
                        totals = report.get("totals", {})
                        # V18.20.3.5 (audit v182034): the old line read
                        # 'coverage_percent'/'avg_similarity' — keys that
                        # _generate_quality_report NEVER writes — so every
                        # run printed "Coverage: ?%, avg similarity: ?".
                        # Read the real keys, plus the deterministic
                        # recall floor (regex-measured on the final set).
                        _cov_val = totals.get("avg_coverage")
                        _cov_str = f"{_cov_val:.0%}" if isinstance(_cov_val, (int, float)) else "?"
                        self._log(f"    Coverage: {_cov_str}", "INFO")
                        _rf = totals.get("recall_floor") or {}
                        if _rf.get("theorists_total"):
                            self._log(
                                f"    Recall floor (deterministic, final set): "
                                f"theorists {_rf.get('theorists_covered', 0)}/"
                                f"{_rf['theorists_total']}"
                                + (
                                    f" ({_rf['theorists_pct']:.0%})"
                                    if _rf.get("theorists_pct") is not None
                                    else ""
                                )
                                + f", conclusion items "
                                f"{_rf.get('conclusion_items_covered', 0)}/"
                                f"{_rf.get('conclusion_items_total', 0)}"
                                + (
                                    f" ({_rf['conclusion_items_pct']:.0%})"
                                    if _rf.get("conclusion_items_pct") is not None
                                    else ""
                                ),
                                "INFO",
                            )
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
            self._log(f"  Warnings: {len(warnings)}", "INFO")
            for w in warnings:
                self._log(f"    ⚠️ {w}", "WARNING")
            self._log(f"  Output dir: {self.output_dir}", "INFO")
            self._log(f"  Log file: {self.conv_logger.log_path}", "INFO")
            self._log(f"  Diagnostic JSONL: {self.conv_logger.diagnostic_path}", "INFO")
            # V18.20.3.9 (Phase 2 / B1, V18.20.3.8 rig audit F1): print each
            # written summary file's provenance stamp INSIDE the diagnostic
            # block. The generated-by comment in every summaries/*.md written
            # since V18.20.3.7 names the exact app version + run_id that
            # produced the file — with the stamps in the log, any file the
            # user later uploads is self-verifying against THIS log, and a
            # pre-V18.20.3.7 stale artifact is visible in seconds instead of
            # after a full four-pillar audit (the stale-file class hit four
            # consecutive rig-audit uploads).
            # V18.20.3.10 (rig audit F6): the stamp is located with the
            # canonical whole-text parser (provenance.stamp_diagnostic), NOT
            # by peeking line 2 — chapter files stamp line 3 (title/blank/
            # stamp) and book files stamp line 1, so the old line-2 peek
            # false-flagged every fresh file as unstamped on the .3.9 run.
            try:
                _summ_root = self.paths.summaries_dir
                if _summ_root.exists():
                    _mds = sorted(_summ_root.rglob("*.md"))
                    if _mds:
                        self._log(f"  Summary files ({len(_mds)}):", "INFO")
                        from core.system.provenance import (
                            get_app_version as _get_app_ver,
                        )
                        from core.system.provenance import (
                            stamp_diagnostic,
                        )

                        # V18.20.4.3 (P2 / G-1 + G-2, the F8 follow-up):
                        # (a) each line now carries the file's FULL PATH —
                        # the user had only file NAMES before, and with
                        # identically-named outputs across per-version
                        # folders the log never said WHICH file to
                        # upload; (b) the running app version is passed
                        # in so a stamp from a DIFFERENT version (a
                        # stale artifact sitting in this folder) is
                        # escalated to a WARNING naming it as not-this-
                        # run's-output — the class that burned three
                        # rig-audit uploads.
                        _app_ver = _get_app_ver()
                        for _sf in _mds:
                            try:
                                _text = _sf.read_text(encoding="utf-8", errors="replace")
                            except Exception:
                                _text = ""
                            _level, _msg = stamp_diagnostic(
                                str(_sf), _text, current_version=_app_ver
                            )
                            self._log(f"    {_msg}", _level)
            except Exception as _e:
                logger.debug("provenance stamp scan ignored: %s", _e)
            # V18.20.3.9 (Phase 3.a / C1): LLM-call telemetry table — the
            # measured per-call data (registry filled by the provider layer
            # on every completed call) replaces estimate-driven perf
            # statements. Total + truncated + the slowest calls give the
            # Phase 3.b cap-right-sizing work its numbers directly from
            # the run (no more log-timestamp archaeology).
            try:
                from core.llm.call_meta import call_telemetry_summary

                _tel = call_telemetry_summary()
                if _tel.get("calls"):
                    _run_s = _time_mod.time() - _t_start
                    self._log(
                        f"  LLM calls: {_tel['calls']} — "
                        f"{_tel['total_s']:.0f}s total "
                        f"({_tel['total_s'] / _run_s * 100:.0f}% of run wall-time), "
                        f"truncated {_tel['truncated']}",
                        "INFO",
                    )
                    for _rank, _c in enumerate(_tel["slowest"], 1):
                        self._log(
                            f"    {_rank}. {_c['model']} — "
                            f"{_c['duration_s']:.0f}s "
                            f"(in {_c['prompt_tokens']}, "
                            f"out {_c['output_tokens']}, "
                            f"done={_c['done_reason']})",
                            "INFO",
                        )
            except Exception as _e:
                logger.debug("telemetry summary ignored: %s", _e)
            # V18.20.3.10 (O7): the opt-in response cache's effect made
            # VISIBLE — hits skip LLM calls entirely (the .3.9 audit's O7:
            # "audit iteration loop" payoff line). Only printed when the
            # run actually consulted the cache (cache is opt-in, default
            # off, so most runs see nothing here).
            try:
                from core.llm.response_cache import response_cache

                _st = response_cache.stats()
                _start = getattr(self, "_cache_stats_start", None) or {}
                _d_hits = _st.get("hits", 0) - _start.get("hits", 0)
                _d_miss = _st.get("misses", 0) - _start.get("misses", 0)
                if _d_hits or _d_miss:
                    self._log(
                        f"  Response cache: {_d_hits} hit(s) / {_d_miss} "
                        f"miss(es) this run — {_st.get('size', 0)} entries "
                        f"persisted on disk (opt-in; hits skip the LLM call)",
                        "INFO",
                    )
            except Exception as _e:
                logger.debug("response cache stats ignored: %s", _e)
            # Final VRAM state (helps diagnose "did models unload?")
            # V18.20.3.10 (F5, .3.8 rig audit): models resident in the
            # Ollama server at exit are a KNOWN COSMETIC class, not an app
            # failure — the server manages its own keep-alive/eviction, and
            # staying loaded speeds up the NEXT conversion. Downgraded
            # WARNING→INFO with the explanation so clean runs no longer end
            # on a scary line that masked nothing (rig runs .3.7-.3.9 all
            # ended on it).
            try:
                from core.llm import ModelManager

                mm = ModelManager()
                loaded = mm.get_loaded_models()
                if loaded:
                    self._log(
                        f"  Models still in Ollama server memory at exit: "
                        f"{list(loaded.keys())} — normal (server-managed "
                        f"keep-alive; speeds up the next run)",
                        "INFO",
                    )
                else:
                    self._log("  Models loaded at exit: (none — all unloaded)", "INFO")
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
            self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")

            # RAG indexing REMOVED entirely.  The app now only PRODUCES
            # RAG-friendly output (YAML frontmatter, clean markdown, JSONL
            # chunks) — it no longer indexes into ChromaDB or runs RAG queries.
            # RAG-friendly output formatting (postprocess) is unaffected.
            self._log("  ⏭️ RAG indexing removed — app produces RAG-friendly output only", "DEBUG")

            # Screenshots + graphs — now opt-in (default OFF)
            # Previously captured 174 screenshots automatically, adding 10+ minutes.
            # Now only runs if the user explicitly enabled it.
            # V18.20.2.0 (SWOT A15): cancel gate — screenshots are opt-in but
            # run 10+ minutes when enabled; a cancelled run must not start them.
            if self.settings.get("outputs_optin.screenshots", False) and not self._cancel_requested(
                "screenshots/graphs"
            ):
                try:
                    from core.pdf.table_graph_extractor import TableGraphExtractor

                    extractor = TableGraphExtractor(log_callback=self._log)
                    # screenshots now respect ALL page-selection
                    # mechanisms — page range, manual_segments, AND selected_chapters.
                    # Previously only manual_segments was checked, so screenshots
                    # captured ALL pages even when chapter selection was active.
                    page_list = list(range(1, total_pages + 1))
                    # 1. Apply page range
                    if self.request.page_range_start or self.request.page_range_end:
                        _start = self.request.page_range_start or 1
                        _end = self.request.page_range_end or total_pages
                        page_list = [p for p in page_list if _start <= p <= _end]
                    # 2. Apply manual_segments (chapter selector page ranges)
                    if self.request.manual_segments:
                        seg_pages = set()
                        for start, end in self.request.manual_segments:
                            for p in range(max(1, start), min(total_pages + 1, end + 1)):
                                seg_pages.add(p)
                        page_list = [p for p in page_list if p in seg_pages]
                    # 3. Apply selected_chapters (derived page ranges from TOC)
                    elif self.request.selected_chapters:
                        toc_page_set = self._derive_page_ranges_from_toc(
                            toc_entries, self.request.selected_chapters, total_pages
                        )
                        if toc_page_set:
                            page_list = [p for p in page_list if p in toc_page_set]
                    result = extractor.extract(
                        self.request.input_path,
                        self.output_dir,
                        page_list,
                        book_title=book_title,
                    )
                    if result["table_count"] > 0 or result["graph_count"] > 0:
                        self._log(
                            f"  📊 Tables: {result['table_count']}, Graphs: {result['graph_count']} → tables.md + graphs.md",
                            "INFO",
                        )
                except Exception as e:
                    self._record_partial_failure("Table/graph extraction", e)
            else:
                self._log("  ⏭️ Screenshots/graphs skipped (opt-in, disabled)", "DEBUG")

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
                            self._log(
                                f"  📝 Footnotes: {fn_result['total_notes']} extracted", "INFO"
                            )
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

            # Library tracking — add book to library
            # V18.20.2.0 (SWOT A15): cancel gate — a cancelled run must not
            # register the partial book in the library.
            if not self._cancel_requested("library tracking"):
                try:
                    from core.pipeline.library_manager import LibraryManager

                    # V18.20.4.1 (P0 / W-a2): the coverage stat stored in
                    # library.json is the MEASURED number from
                    # quality_report.json ("totals.avg_coverage" — the same
                    # source the end-of-conversion diagnostic reads). The
                    # literal 0.92 placeholder shipped with EVERY book
                    # since V3.9.0 ("will be updated from quality report" —
                    # never was), and library stats averaged the
                    # fabrication — a contradiction of the honesty
                    # machinery's own standard. When the report is missing,
                    # unreadable, or non-numeric, we store None and
                    # library_manager omits the field (honest "unknown",
                    # never a fabricated value).
                    _cov_lib: float | None = None
                    try:
                        import json as _json_lib

                        _qr_lib = self.paths.quality_report
                        if _qr_lib.exists():
                            _cov_val_lib = (
                                _json_lib.loads(_qr_lib.read_text(encoding="utf-8"))
                                .get("totals", {})
                                .get("avg_coverage")
                            )
                            if isinstance(_cov_val_lib, (int, float)):
                                _cov_lib = float(_cov_val_lib)
                    except Exception as _e:
                        logger.debug("ignored %s: %s", type(_e).__name__, _e)
                    lib = LibraryManager(log_callback=self._log)
                    lib.add_book(
                        title=book_title,
                        source_file=self.request.input_path.name,
                        chapters_processed=len(summaries) if summaries else 0,
                        total_chapters=len(segments) if segments else 0,
                        concepts_extracted=sum(len(s.bullet_points) for s in summaries)
                        if summaries
                        else 0,
                        # V18.20.3.10 (W11): the DEDUPED count that shipped in
                        # the keypoints file (was the raw bullet sum — the
                        # 41-vs-36 mismatch, .3.7 SWOT W11).
                        keypoints_count=(
                            _kp_final_count
                            if _kp_final_count is not None
                            else (sum(len(s.bullet_points) for s in summaries) if summaries else 0)
                        ),
                        coverage=_cov_lib,
                        output_dir=str(self.output_dir),
                    )
                except Exception as e:
                    self._record_partial_failure("Library tracking", e)

            # V10.34.0 (Sprint 6.10): Merge partial failures into warnings
            # so they surface in the success modal.
            _all_warnings = list(warnings)
            _pf = getattr(self, "_partial_failures", [])
            if _pf:
                _all_warnings.append(f"⚠️ {len(_pf)} sub-system(s) had partial failures:")
                _all_warnings.extend(f"  • {pf}" for pf in _pf)

            return ConversionResult(
                # V18.20.2.0 (SWOT A15): a cancelled run reports through the
                # SAME plumbing as the existing early-exit gates
                # (extraction.py:389, segmentation.py:214,
                # summarization.py:94): success=False +
                # error_msg="Cancelled by user".  ConversionResult has no
                # dedicated cancelled field, so no new plumbing is invented.
                # V0.02 (false-success RCA): an explicit chapter selection
                # that summarized NOTHING is also a failure — the old
                # ``(not _all_failed if summaries else True)`` treated an
                # empty ``summaries`` list as unconditionally successful.
                success=(
                    (not _all_failed if summaries else True)
                    and not _cancelled
                    and not (_zero_summaries and _selection_active)
                ),
                error_msg=(
                    "Cancelled by user"
                    if _cancelled
                    else (
                        "All chapters returned empty responses — model may not be installed, "
                        "VRAM insufficient, or quantization too aggressive. "
                        "Try: ollama pull <model>, use IQ2_M instead of IQ2_XXS, "
                        "or raise temperature to 1.0."
                    )
                    if _all_failed
                    else (
                        f"None of the {len(self.request.selected_chapters)} selected chapter(s) "
                        f"were summarized — the selection matched no summarizable section. "
                        f"Re-pick chapters in the selector (per-chapter author bookmarks "
                        f"are no longer listed) or convert the whole book."
                        if (_zero_summaries and _selection_active)
                        else None
                    )
                ),
                full_markdown_path=self.full_markdown_path,
                chapters_folder=self.chapters_folder if self.chapters_folder.exists() else None,
                chunks_folder=self.chunks_folder if self.chunks_folder.exists() else None,
                docx_path=docx_path,
                # V18.20.3.6: the pages THIS run actually covered (selection
                # > range > whole document) — was ``total_pages``, which
                # reported the whole book for a single-chapter conversion.
                pages_processed=_pages_processed,
                chapters_detected=len([s for s in segments if s.segment_type == "chapter"]),
                chunks_created=len([s for s in segments if s.segment_type == "chunk"]),
                summaries_generated=len(summaries),
                segments=segments,
                summaries=summaries,
                log_file_path=self.conv_logger.log_path,
                warnings=_all_warnings,
            )

        except Exception as e:
            self._log(f"❌ Fatal error: {e}", "ERROR")
            import traceback

            self._log(traceback.format_exc(), "ERROR")
            return ConversionResult(success=False, error_msg=str(e))
        finally:
            self.conv_logger.close()
