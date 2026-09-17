"""
Controller — manages conversion threads and UI↔core communication.

FIXES in this version:
  - Removed on_ocr_recommendation from set_callbacks() and all related wiring.
    The OCR recommendation dialog was being scheduled from the background
    conversion thread. On Windows, tkinter messageboxes called from non-main
    threads can render invisible behind the main window, causing the 34-minute
    freeze seen in the first test run.
  - Removed the patching of converter._get_user_override in _run_conversion().
    converter.py now handles the recommendation silently (auto-accept + log).
  - set_tk_root() and _tk_call() remain for all other UI callbacks
    (progress, status, log, complete) which still need thread-safe dispatch.
  - Added manual_segments, temperature, self_consistency, fast_model, heavy_model,
    and coverage_threshold to build_request_from_ui().
  - Added save_book_settings() and load_book_settings() for per-book configuration.
  - NEW: Added page_range_start, page_range_end, selected_chapters to build_request_from_ui().
  - NEW: Added advanced document handling fields: extract_tables, extract_math,
    layout_analysis, table_extraction_method, math_model.
  - NEW: Added source_type, include_executive_summary, include_thorough_summary,
    include_keypoints to build_request_from_ui() and save_book_settings().
  - NEW: Added enable_content_filter and academic_rigor to build_request_from_ui()
    and save_book_settings().
  - NEW: Sprint 2 – Added simplified_keypoints_enabled to build_request_from_ui()
    and save_book_settings().
  - NEW: Sprint 3 – Added max_workers and extract_figure_text to build_request_from_ui()
    and save_book_settings().
"""

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.models import ConversionRequest, ConversionResult
from core.pipeline import Converter
from utils.logging import get_main_logger
from utils.settings import Settings

logger = get_main_logger()


class Controller:
    def __init__(self):
        self.current_conversion_thread: threading.Thread | None = None
        self.cancel_event  = threading.Event()
        # V9.0.0: conversion lock — atomic check-and-set to prevent the
        # TOCTOU race where Convert tab + Queue tab both pass is_converting()
        # simultaneously and spawn two worker threads (P1-7).
        self._conversion_lock = threading.Lock()
        self.converter: Converter | None = None
        self.settings  = Settings()

        self.on_progress: Callable[[float], None] | None          = None
        self.on_status:   Callable[[str], None] | None            = None
        self.on_log:      Callable[[str, str], None] | None       = None
        self.on_complete: Callable[[ConversionResult], None] | None= None
        # V18.20.4.5 (W-b10): ownership tag for the four callbacks above
        # ("convert_view" / "queue" / "wizard"; None for legacy callers).
        # Three UI components swap these callbacks mid-session, and the
        # wizard's closeEvent used to blindly re-register ConvertView's —
        # silently stealing them from a RUNNING queue (its on_complete
        # result-capture stopped firing, per-book modals popped from a
        # hidden tab). The tag lets closeEvent refuse that steal.
        self.callback_owner: str | None = None

        self._tk_root = None
        # Generic main-thread scheduler (used by the PySide6 UI).
        # When set, _tk_call routes through it instead of Tkinter's after().
        self._scheduler: Callable[..., None] | None = None

    def set_tk_root(self, root) -> None:
        """Store the Tkinter root so callbacks can be safely dispatched to the main thread."""
        self._tk_root = root

    def set_scheduler(self, scheduler) -> None:
        """Set a generic main-thread scheduler.

        Used by non-Tkinter front-ends (e.g. PySide6).  ``scheduler`` must be a
        callable ``scheduler(fn, *args)`` that guarantees ``fn(*args)`` runs on
        the UI main thread.  When set, it takes priority over the Tkinter root.
        """
        self._scheduler = scheduler

    def set_callbacks(
        self,
        on_progress=None,
        on_status=None,
        on_log=None,
        on_complete=None,
        # on_ocr_recommendation intentionally removed — see module docstring
        owner: str | None = None,
    ):
        # V18.20.4.5 (W-b10): ``owner`` tags WHO installed this callback set
        # ("convert_view" / "queue" / "wizard"). Purely advisory state for
        # UI components — the four callbacks behave exactly as before. The
        # kwarg is trailing + defaulted, so all positional/keyword callers
        # (tests, legacy front-ends, convert_view/queue_view/wizard_view)
        # remain source-compatible.
        self.on_progress = on_progress
        self.on_status   = on_status
        self.on_log      = on_log
        self.on_complete = on_complete
        self.callback_owner = owner

    # ─────────────────────────────────────────────────────────────────────────
    # Thread-safe UI helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _tk_call(self, fn, *args):
        """Schedule fn(*args) on the UI main thread.

        Priority: generic scheduler (PySide6) → Tkinter root.after() → direct call.
        """
        if self._scheduler is not None:
            try:
                self._scheduler(fn, *args)
                return
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
        if self._tk_root:
            try:
                self._tk_root.after(0, lambda: fn(*args))
                return
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
        fn(*args)   # fallback: call directly (safe when already on main thread)

    def _safe_progress(self, value):
        if self.on_progress:
            self._tk_call(self.on_progress, value)

    def _safe_status(self, msg):
        if self.on_status:
            self._tk_call(self.on_status, msg)

    def _safe_log(self, msg, level="INFO"):
        if self.on_log:
            self._tk_call(self.on_log, msg, level)

    def _safe_complete(self, result):
        """V10.2.4: Ensure the completion callback always fires.

        The old code used _tk_call which could silently fail if the
        scheduler and tk_root were both None (falling through to a direct
        call on the background thread, where Qt widgets can't be accessed).

        The new code always tries the on_complete callback directly first
        (since the Qt bridge's emit_complete is thread-safe — it just
        emits a signal which Qt marshals to the main thread).
        """
        if self.on_complete:
            try:
                self.on_complete(result)
            except Exception as e:
                logger.error(f"Completion callback failed: {e}")
                # Try via _tk_call as a fallback
                try:
                    self._tk_call(self.on_complete, result)
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # ─────────────────────────────────────────────────────────────────────────
    # V18.20.3.3 (crash fix #4): crash-evidence recorder — no conversion
    # death is ever silent again.
    # ─────────────────────────────────────────────────────────────────────────

    def _record_conversion_crash(
        self, request: ConversionRequest, exc: BaseException,
    ) -> str:
        """Record a conversion-thread death EVERYWHERE it can be observed.

        The V18.20.3 startup crash left exactly ONE log line and zero other
        evidence — the process died inside the pre-flight dependency-import
        window and the worker thread vanished without a dialog, without a
        traceback, and without a line in the .conversion.log.md file.

        Called from BOTH the ``except Exception`` and ``except
        BaseException`` branches of ``_run_conversion``.  Writes the full
        traceback to, in order:
          1. the UI log viewer (``_safe_log``, ERROR level);
          2. the conversion log FILE — the Converter's own
             ConversionLogger when it exists (its log() flushes every
             line), else the newest ``*.conversion.log.md`` under the
             request's output dir, else a standalone crash file next to
             the crash zip;
          3. a crash-report zip (traceback + redacted settings + system
             info — ``core.system.crash_report.generate_crash_report``).

        Returns the user-facing error message (includes the crash-report
        path so the failure dialog points at the evidence).  Never raises.
        """
        import traceback as _tb
        _tb_text = "".join(
            _tb.format_exception(type(exc), exc, exc.__traceback__)
        )
        _lines = _tb_text.rstrip().splitlines() or [
            f"{type(exc).__name__}: {exc}"
        ]

        # 1. UI log viewer — the tail of the traceback (the crash site +
        #    every relevant frame) keeps the viewer readable.
        self._safe_log(
            f"💥 Conversion thread died: {type(exc).__name__}: {exc}", "ERROR"
        )
        for _line in _lines[-60:]:
            self._safe_log(f"    {_line}", "ERROR")

        # 2. Conversion log FILE — full traceback, no truncation.
        _file_note = ""
        try:
            _conv_logger = getattr(
                getattr(self, "converter", None), "conv_logger", None
            )
            if _conv_logger is not None:
                _conv_logger.log(
                    f"💥 FATAL — conversion thread died: "
                    f"{type(exc).__name__}: {exc}",
                    "ERROR",
                )
                for _line in _lines:
                    _conv_logger.log(f"    {_line}", "ERROR")
            else:
                # The Converter was never constructed (or died inside its
                # own __init__) — write the evidence wherever we can.
                _file_note = self._write_crash_to_output_dir(
                    request, _tb_text, exc
                )
        except Exception as _e:
            logger.debug(
                "crash write to conversion log failed: %s: %s",
                type(_e).__name__, _e,
            )

        # 3. Crash-report zip (traceback + redacted settings + system info).
        _crash_path = None
        try:
            from core.system.crash_report import generate_crash_report
            _crash_path = generate_crash_report(type(exc), exc, exc.__traceback__)
        except Exception as _e:
            logger.debug(
                "crash report generation failed: %s: %s", type(_e).__name__, _e
            )

        _msg = f"{type(exc).__name__}: {exc}"
        if _crash_path is not None:
            _msg += f"\n\nFull crash report saved to:\n{_crash_path}"
        if _file_note:
            _msg += f"\n{_file_note}"
        if _crash_path is None:
            _msg += (
                "\n\n(No crash-report zip could be generated — the full "
                "traceback is above and in the conversion log.)"
            )
        return _msg

    def _write_crash_to_output_dir(
        self, request: ConversionRequest, tb_text: str, exc: BaseException,
    ) -> str:
        """Best-effort fallback when no ConversionLogger exists yet.

        Appends the traceback to the newest ``*.conversion.log.md`` found
        under the request's output dir (resume / early-death case).  When
        none exists (the crash happened before the Converter created one),
        writes a standalone ``conversion_crash_<timestamp>.md`` into
        ``~/.markitdown_pro/crash_reports/`` instead — the evidence ALWAYS
        lands in a file, never only in a UI viewer that dies with the
        wizard.  Returns a human-readable note for the failure dialog, or
        "" when nothing could be written.  Never raises.
        """
        from datetime import datetime as _dt
        from pathlib import Path as _P

        _block = (
            f"\n\n[{_dt.now().strftime('%H:%M:%S')}] [ERROR] "
            f"💥 FATAL — conversion thread died BEFORE the log was wired: "
            f"{type(exc).__name__}: {exc}\n"
            + "\n".join(
                f"    {ln}" for ln in tb_text.rstrip().splitlines()
            )
            + "\n"
        )

        # (a) newest conversion log under the output dir
        try:
            _root = _P(str(getattr(request, "output_dir", "") or "."))
            if _root.exists():
                _stem = getattr(
                    getattr(request, "input_path", None), "stem", ""
                ) or ""
                _cands = [
                    p for p in _root.rglob("*.conversion.log.md")
                    if not _stem or _stem in p.name
                ]
                if _cands:
                    _target = max(_cands, key=lambda p: p.stat().st_mtime)
                    with open(_target, "a", encoding="utf-8") as _f:
                        _f.write(_block)
                    return f"Traceback appended to: {_target}"
        except Exception as _e:
            logger.debug(
                "crash append to conversion log failed: %s: %s",
                type(_e).__name__, _e,
            )

        # (b) standalone crash file next to the crash zips
        try:
            _dir = _P.home() / ".markitdown_pro" / "crash_reports"
            _dir.mkdir(parents=True, exist_ok=True)
            _target = _dir / f"conversion_crash_{_dt.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(_target, "a", encoding="utf-8") as _f:
                _f.write(_block)
            return f"Traceback saved to: {_target}"
        except Exception as _e:
            logger.debug(
                "standalone crash file write failed: %s: %s",
                type(_e).__name__, _e,
            )
        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # Conversion thread
    # ─────────────────────────────────────────────────────────────────────────

    def _run_conversion(self, request: ConversionRequest):
        try:
            # V18.20.2.0 (SWOT A14): the redundant ``self.cancel_event.clear()``
            # that used to live here is REMOVED.  start_conversion() already
            # clears the event under ``_conversion_lock`` BEFORE spawning this
            # thread (Finding 1.1/1.2); re-clearing at worker start erased a
            # cancel clicked in the thread-start window, so a "cancelled"
            # conversion ran to completion.  The only clear lives under the
            # lock in start_conversion() now.

            self.converter = Converter(
                request=request,
                progress_callback=self._safe_progress,
                status_callback=self._safe_status,
                log_callback=self._safe_log,
                cancel_event=self.cancel_event,
            )
            # NOTE: no patching of converter._get_user_override here.
            # converter.py now accepts the analyzer recommendation automatically.

            result = self.converter.convert()

            # ── Save settings to the output folder ────────────────────────
            if result.success and result.full_markdown_path:
                self.save_book_settings(result.full_markdown_path.parent, request)

            # ── V4.7.25: Auto-translate outputs if translation is enabled ──
            # V5.3.7: Moved BEFORE _safe_complete so the wizard doesn't show
            # "complete" while translation is still running.
            if result.success and result.full_markdown_path:
                self._maybe_translate_outputs(result)

            # ── Signal completion AFTER all post-conversion steps finish ──
            # V5.3.7: This was previously called before translation, causing
            # the wizard to show "Conversion complete" while translation,
            # RAG indexing, and screenshots were still running.
            self._safe_complete(result)

        except Exception as e:
            logger.exception("Conversion thread crashed")
            self._safe_log(f"Fatal error: {e}", "ERROR")
            # V18.20.3.3 (crash fix #4): the old handler logged only
            # str(e) — no traceback, nothing in the conversion log FILE,
            # no crash zip.  Now every conversion death leaves full
            # evidence in all three places (UI log + file + crash zip)
            # and the failure dialog points at it.
            _msg = self._record_conversion_crash(request, e)
            self._safe_complete(ConversionResult(success=False, error_msg=_msg))
        except BaseException as e:
            # V18.20.3.3 (crash fix #4): SystemExit and every other
            # non-Exception escape used to bypass the handler above and
            # silently kill this worker thread — no dialog, no log line,
            # and the wizard stayed stuck on "Starting conversion…"
            # forever (the V18.20.3 startup crash).  Same evidence
            # treatment, then the normal failure path (dialog included).
            logger.exception("Conversion thread died (BaseException)")
            _msg = self._record_conversion_crash(request, e)
            self._safe_complete(ConversionResult(success=False, error_msg=_msg))
        finally:
            self.current_conversion_thread = None

    def start_conversion(self, request: ConversionRequest) -> bool:
        # V9.0.0: atomic check-and-set under the conversion lock — prevents
        # the TOCTOU race where Convert + Queue both pass is_converting()
        # simultaneously (P1-7).  Also clears cancel_event BEFORE spawning
        # the thread (Finding 1.1/1.2 — was cleared inside the worker,
        # which could lose a cancel if the user clicked fast).
        with self._conversion_lock:
            if self.is_converting():
                self._safe_log("Conversion already in progress.", "WARNING")
                return False
            # Clear cancel BEFORE spawning so the worker starts clean
            self.cancel_event.clear()
            self.current_conversion_thread = threading.Thread(
                target=self._run_conversion, args=(request,), daemon=True
            )
            self.current_conversion_thread.start()
        return True

    def cancel_conversion(self) -> bool:
        if not self.is_converting():
            return False
        self.cancel_event.set()
        self._safe_log("Cancellation requested…", "WARNING")
        return True

    def is_converting(self) -> bool:
        return (
            self.current_conversion_thread is not None
            and self.current_conversion_thread.is_alive()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # V4.7.25: Post-conversion translation
    # ─────────────────────────────────────────────────────────────────────────

    def _maybe_translate_outputs(self, result) -> None:
        """Auto-translate outputs if translation is enabled in settings.

        Called after a successful conversion. Runs in the same background
        thread as the conversion. If translation is disabled or no outputs
        are selected, this is a no-op.
        """
        try:
            if not self.settings.get("translation.enabled", False):
                return

            from core.translation.service import TranslationService

            book_dir = result.full_markdown_path.parent
            book_name = result.full_markdown_path.stem

            self._safe_log("🌐 Starting translation…", "INFO")

            # V7.5.0: Proactive phase-boundary unload — free the summarizer /
            # OCR / judge models from VRAM before translation starts.  NLLB
            # runs on the GPU via HuggingFace and needs the memory; Ollama
            # translation only needs the translator model.  This prevents the
            # "translation crashed mid-book with OOM" failure mode on the
            # RTX 3060 12 GB during long (6-7h) conversions.
            try:
                from core.llm import ModelManager
                mm = ModelManager()
                # V13.31.0 (#13): default backend is now "ollama" (was "nllb")
                t_backend = self.settings.get("translation.backend", "ollama")
                t_model = self.settings.get("translation.model", "")
                mm.unload_for_translation(
                    translation_backend=t_backend,
                    translation_model=t_model,
                    log_callback=lambda msg, level: self._safe_log(msg, level),
                )
            except Exception as e:
                self._safe_log(f"  ℹ️ Proactive unload skipped: {e}", "DEBUG")

            service = TranslationService.from_settings(
                log_callback=lambda msg, level: self._safe_log(f"  {msg}", level)
            )
            if service is None:
                self._safe_log("  ⚠️ Translation service not configured (no model set)", "WARNING")
                return

            results = service.translate_book_outputs(
                book_output_dir=book_dir,
                book_name=book_name,
                progress_callback=lambda p: self._safe_log(
                    f"  [{p.stage}] {p.message}", "INFO"
                ),
            )

            if results:
                self._safe_log(
                    f"  ✅ Translation complete: {len(results)} file(s) translated", "SUCCESS"
                )
            else:
                self._safe_log("  ℹ️ No files selected for translation", "INFO")

        except Exception as e:
            self._safe_log(f"  ⚠️ Translation error: {e}", "WARNING")

    # ─────────────────────────────────────────────────────────────────────────
    # Settings access
    # ─────────────────────────────────────────────────────────────────────────

    def get_settings(self) -> dict[str, Any]:
        # V18.20.4.3 (P2 / W-c3): isolated snapshot — the previous
        # live-``_data`` return bypassed the Settings RLock and handed
        # callers a mutable alias of the store the conversion worker
        # mutates via ``Settings.set`` ("dictionary changed size during
        # iteration" race) — and external mutations never persisted.
        # Callers now get a locked deep-copy; ``get_setting``/
        # ``update_setting`` remain the write path.
        return self.settings.snapshot()

    def update_setting(self, path: str, value: Any) -> None:
        self.settings.set(path, value)

    def get_setting(self, path: str, default: Any = None) -> Any:
        return self.settings.get(path, default)

    # ─────────────────────────────────────────────────────────────────────────
    # Per‑book configuration
    # ─────────────────────────────────────────────────────────────────────────

    def save_book_settings(self, output_dir: Path, request: ConversionRequest) -> None:
        """Save the conversion parameters to a config file in the output folder."""
        config_path = output_dir / ".conversion_config.json"
        data = {
            "input_path": str(request.input_path),
            "output_dir": str(request.output_dir),
            "use_llm_ocr": request.use_llm_ocr,
            "primary_ocr_model": request.primary_ocr_model,
            "fallback_ocr_model": request.fallback_ocr_model,
            "auto_detect_scanned": request.auto_detect_scanned,
            "force_ocr_all_pages": request.force_ocr_all_pages,
            "image_max_size": request.image_max_size,
            "clean_markdown": request.clean_markdown,
            "fix_missing_spaces": request.fix_missing_spaces,
            "token_saver": request.token_saver,
            "remove_page_number_headings": request.remove_page_number_headings,
            "convert_separators_to_comments": request.convert_separators_to_comments,
            "segment_strategy": request.segment_strategy,
            "custom_keywords": request.custom_keywords,
            "custom_regex_patterns": request.custom_regex_patterns,
            "chunk_by_page_groups": request.chunk_by_page_groups,
            "page_group_size": request.page_group_size,
            "token_limit_per_segment": request.token_limit_per_segment,
            "enable_semantic_segmentation": request.enable_semantic_segmentation,
            "generate_summaries": request.generate_summaries,
            "summarisation_model": request.summarisation_model,
            "summarisation_max_context_tokens": request.summarisation_max_context_tokens,
            "summarisation_max_output_tokens": request.summarisation_max_output_tokens,
            "summarisation_cache_enabled": request.summarisation_cache_enabled,
            "generate_docx": request.generate_docx,
            "docx_author": request.docx_author,
            "docx_include_toc": request.docx_include_toc,
            "max_workers": request.max_workers,
            "temperature": request.temperature,
            "self_consistency": request.self_consistency,
            "fast_model": request.fast_model,
            "heavy_model": request.heavy_model,
            # V16.0.9: 4-mode model architecture
            "model_architecture": getattr(request, "model_architecture", "single_local"),
            "fast_api_url": getattr(request, "fast_api_url", ""),
            "fast_api_key": getattr(request, "fast_api_key", ""),
            "fast_api_model": getattr(request, "fast_api_model", ""),
            "coverage_threshold": request.coverage_threshold,
            "manual_segments": request.manual_segments,
            # ── NEW fields ──────────────────────────────────────────────────
            "page_range_start": request.page_range_start,
            "page_range_end": request.page_range_end,
            "selected_chapters": request.selected_chapters,
            # ── NEW Advanced document handling ─────────────────────────────
            "extract_tables": request.extract_tables,
            "extract_math": request.extract_math,
            "layout_analysis": request.layout_analysis,
            "table_extraction_method": request.table_extraction_method,
            "math_model": request.math_model,
            # ── NEW Sprint 1 fields ────────────────────────────────────────
            "source_type": request.source_type,
            "include_executive_summary": request.include_executive_summary,
            "include_thorough_summary": request.include_thorough_summary,
            "include_keypoints": request.include_keypoints,
            # ── NEW Sprint 2 fields ────────────────────────────────────────
            "enable_content_filter": request.enable_content_filter,
            "academic_rigor": request.academic_rigor,
            "simplified_keypoints_enabled": request.simplified_keypoints_enabled,
            # ── NEW Sprint 3 fields ────────────────────────────────────────
            "extract_figure_text": request.extract_figure_text,
            # V7.9.0: save output_* flags so the Output Scanner can
            # distinguish "not requested" from "missing/failed".
            "output_briefing":     getattr(request, "output_briefing", False),
            "output_podcast":      getattr(request, "output_podcast", False),
            "output_flashcards":   getattr(request, "output_flashcards", False),
            "output_packets":      getattr(request, "output_packets", False),
            "output_obsidian":     getattr(request, "output_obsidian", False),
            "output_study_guide":  getattr(request, "output_study_guide", False),
            "output_social":       getattr(request, "output_social", False),
            "output_mindmap":      getattr(request, "output_mindmap", False),
            "output_tts":          getattr(request, "output_tts", False),
            # V10.1.0: langextract evidence map
            "output_evidence_map": getattr(request, "output_evidence_map", False),
        }
        try:
            # V18.20.2.0 (SWOT A30): atomic write — a crash mid-write of
            # .conversion_config.json corrupts the regeneration contract
            # (load_book_settings can't parse a truncated file → regenerate
            # breaks permanently).  Same payload: indent=2, non-ASCII kept.
            from utils.atomic_io import atomic_write_json
            atomic_write_json(config_path, data, indent=2, ensure_ascii=False)
            self._safe_log(f"💾 Saved settings to {config_path}", "INFO")
        except Exception as e:
            self._safe_log(f"Failed to save book settings: {e}", "WARNING")

    def load_book_settings(self, input_path: Path, output_dir: Path) -> dict[str, Any] | None:
        """Load settings from the config file in the output directory or input directory."""
        # Look in output_dir first, then input_dir
        config_candidates = [
            output_dir / ".conversion_config.json",
            input_path.parent / ".conversion_config.json",
        ]
        for config_path in config_candidates:
            if config_path.exists():
                try:
                    with open(config_path, encoding="utf-8") as f:
                        data = json.load(f)
                    self._safe_log(f"📂 Loaded settings from {config_path}", "INFO")
                    return data
                except Exception as e:
                    self._safe_log(f"Failed to load book settings from {config_path}: {e}", "WARNING")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Request builder
    # ─────────────────────────────────────────────────────────────────────────

    # V10.31.0 (Sprint 4.4): Auto-mapper table for build_request_from_ui.
    # Replaces the 200-line hand-mapped method with a declarative table +
    # 30-line generic loop.  Each entry is:
    #   (request_attr, ui_key, setting_path_or_None, default, transform_or_None)
    # The transform is a callable applied to the resolved value (e.g.
    # Path, /100.0, enum .value).  Adding a new field is a one-line table
    # change — no more hand-mapped kwargs that can silently drift (the
    # V10.24.0 outputs_X vs output_X bug class is now structurally impossible).
    _REQUEST_FIELD_MAP = [
        # ── Path fields (transform=Path) ──────────────────────────────
        ("input_path",  "input_path",  None, None, lambda v: Path(v)),
        ("output_dir",  "output_dir",  None, None, lambda v: Path(v)),
        # ── Simple fields (no settings lookup) ────────────────────────
        ("password",                    "password",                    None, None, None),
        ("manual_segments",             "manual_segments",             None, None, None),
        ("page_range_start",            "page_range_start",            None, None, None),
        ("page_range_end",              "page_range_end",              None, None, None),
        ("selected_chapters",           "selected_chapters",           None, None, None),
        ("output_qa",                   "output_qa",                   None, False, None),
        ("output_glossary",             "output_glossary",             None, False, None),
        ("output_patterns",             "output_patterns",             None, False, None),
        ("output_cheatsheet",           "output_cheatsheet",           None, False, None),
        ("output_skill",                "output_skill",                None, False, None),
        # V10.35.0: New outputs
        ("output_epub",                 "output_epub",                 None, False, None),
        ("output_quote_bank",           "output_quote_bank",           None, False, None),
        ("compact_summaries",           "compact_summaries",           None, False, None),
        ("conservative_drops",          "conservative_drops",          None, False, None),
        # ── Settings-backed fields (ui_key, setting_path, default) ────
        ("use_llm_ocr",                 "use_llm_ocr",                 "ocr.use_llm", True, None),
        # V18.20.4.3 (P2 / W-c1): fallback defaults unified with the
        # canonical ``utils/settings.py`` defaults + USER_OLLAMA_MODELS.md
        # (these fire only when the settings file lacks the key — the old
        # disagreeing literals ``qwen3-vl:8b`` named models the rig never
        # had installed).
        ("primary_ocr_model",           "primary_ocr_model",           "ocr.primary_model", "OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest", None),
        ("fallback_ocr_model",          "fallback_ocr_model",          "ocr.fallback_model", "OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest", None),
        ("auto_detect_scanned",         "auto_detect_scanned",         "ocr.auto_detect_scanned", True, None),
        ("force_ocr_all_pages",         "force_ocr_all_pages",         "ocr.force_ocr_all_pages", False, None),
        ("image_max_size",              "image_max_size",              "ocr.image_max_size", 1200, None),
        ("clean_markdown",              "clean_markdown",              "postprocess.clean_markdown", True, None),
        ("fix_missing_spaces",          "fix_missing_spaces",          "postprocess.fix_missing_spaces", False, None),
        ("token_saver",                 "token_saver",                 "postprocess.token_saver", True, None),
        ("remove_page_number_headings", "remove_page_number_headings", "postprocess.remove_page_number_headings", True, None),
        ("convert_separators_to_comments", "convert_separators_to_comments", "postprocess.convert_separators_to_comments", False, None),
        ("custom_keywords",             "custom_keywords",             "segmentation.custom_keywords", [], None),
        ("custom_regex_patterns",       "custom_regex_patterns",       "segmentation.custom_regex_patterns", [], None),
        ("chunk_by_page_groups",        "chunk_by_page_groups",        "segmentation.chunk_by_page_groups", True, None),
        ("page_group_size",             "page_group_size",             "segmentation.page_group_size", 10, None),
        ("token_limit_per_segment",     "token_limit_per_segment",     "segmentation.token_limit", 2000, None),
        ("enable_semantic_segmentation","enable_semantic_segmentation","segmentation.enable_semantic", True, None),
        ("generate_summaries",          "generate_summaries",          "summarisation.enabled", False, None),
        # V18.20.4.3 (P2 / W-c1): same unification — the request-builder
        # fallback now matches ``settings.py`` (``gemma4-12b:latest``, the
        # documented rig default since V13.45.4) instead of ``gemma3:12b``.
        ("summarisation_model",         "summarisation_model",         "summarisation.model", "gemma4-12b:latest", None),
        ("summarisation_max_context_tokens", "summarisation_max_context_tokens", "summarisation.max_context_tokens", 16000, None),
        ("summarisation_max_output_tokens",  "summarisation_max_output_tokens",  "summarisation.max_output_tokens", 4096, None),
        ("summarisation_cache_enabled", "summarisation_cache_enabled", "summarisation.cache_enabled", False, None),
        ("generate_docx",               "generate_docx",               "docx.enabled", False, None),
        ("docx_author",                 "docx_author",                 "docx.author", "MarkItDown Pro", None),
        ("docx_include_toc",            "docx_include_toc",            "docx.include_toc", True, None),
        ("max_workers",                 "max_workers",                 "summarisation.max_workers", 2, None),
        ("temperature",                 "temperature",                 "summarisation.temperature", 0.2, None),
        ("self_consistency",            "self_consistency",            "summarisation.self_consistency", False, None),
        # V15.1.0: Over-delivery — keep improving coverage past minimum threshold
        ("overdeliver_enabled",         "overdeliver_enabled",          "summarisation.overdeliver_enabled", True, None),
        ("overdeliver_target",          "overdeliver_target",           "summarisation.overdeliver_target", 1.0, lambda v: float(v) / 100.0 if v > 1.0 else float(v)),
        ("b3_voting_enabled",           "b3_voting_enabled",            "summarisation.b3_voting_enabled", False, None),
        # V18.20.4.3 (P2 / W-c1): fast_model fallback unified — the
        # canonical settings default is "" (use the main model); the old
        # "gemma3:12b" literal named a model the rig never had (it is on
        # the known-bad-default blacklist in core/tts/normalizer.py).
        ("fast_model",                  "fast_model",                  "summarisation.fast_model", "", None),
        ("heavy_model",                 "heavy_model",                 "summarisation.heavy_model", "", None),
        # V16.0.9: 4-mode model architecture (single_local | dual_local | single_api | dual_api)
        ("model_architecture",          "model_architecture",          "summarisation.model_architecture", "single_local", None),
        ("fast_model_temperature",      "fast_model_temperature",      "summarisation.fast_model_temperature", 0.1, None),
        ("fast_model_context",          "fast_model_context",          "summarisation.fast_model_context", 131072, None),
        ("fast_api_url",                "fast_api_url",                "summarisation.fast_api_url", "", None),
        ("fast_api_key",                "fast_api_key",                "summarisation.fast_api_key", "", None),
        ("fast_api_model",              "fast_api_model",              "summarisation.fast_api_model", "", None),
        ("simplification_model",        "simplification_model",        "summarisation.simplification_model", "", None),
        ("extract_tables",              "extract_tables",              "advanced.extract_tables", False, None),
        ("extract_math",                "extract_math",                "advanced.extract_math", False, None),
        ("layout_analysis",             "layout_analysis",             "advanced.layout_analysis", False, None),
        ("table_extraction_method",     "table_extraction_method",     "advanced.table_method", "camelot", None),
        ("math_model",                  "math_model",                  "advanced.math_model", "pix2tex", None),
        ("source_type",                 "source_type",                 "source_type", "normal_book", None),
        ("include_executive_summary",   "include_executive_summary",   "summarisation.include_executive_summary", True, None),
        ("include_thorough_summary",    "include_thorough_summary",    "summarisation.include_thorough_summary", True, None),
        ("include_keypoints",           "include_keypoints",           "summarisation.include_keypoints", True, None),
        ("enable_content_filter",       "enable_content_filter",       "content_filter.enabled", True, None),
        ("academic_rigor",              "academic_rigor",              "summarisation.academic_rigor", False, None),
        ("simplified_keypoints_enabled","simplified_keypoints_enabled","summarisation.simplified_keypoints_enabled", False, None),
        ("extract_figure_text",         "extract_figure_text",         "advanced.extract_figure_text", False, None),
        ("output_briefing",             "output_briefing",             "outputs.briefing", True, None),
        ("output_podcast",              "output_podcast",              "outputs.podcast", True, None),
        ("output_flashcards",           "output_flashcards",           "outputs.flashcards", True, None),
        ("output_packets",              "output_packets",              "outputs.packets", False, None),
        ("output_obsidian",             "output_obsidian",             "outputs.obsidian", False, None),
        ("output_study_guide",          "output_study_guide",          "outputs.study_guide", False, None),
        ("output_social",               "output_social",               "outputs.social", False, None),
        ("output_mindmap",              "output_mindmap",              "outputs.mindmap", False, None),
        ("output_tts",                  "output_tts",                  "outputs.tts", False, None),
        ("output_evidence_map",         "output_evidence_map",         "outputs.evidence_map", False, None),
    ]

    def build_request_from_ui(self, ui_data: dict[str, Any]) -> ConversionRequest:
        """Build a ConversionRequest from the wizard/UI data dict.

        V10.31.0 (Sprint 4.4): Replaced the 200-line hand-mapped method with
        a declarative table (``_REQUEST_FIELD_MAP``) + a 30-line generic
        loop.  Adding a new field is now a one-line table change — the
        V10.24.0 ``outputs_X`` vs ``output_X`` silent-drift bug class is
        structurally impossible because the table is the single source.

        Special handling (not table-driven):
          - ``input_path`` / ``output_dir`` → wrapped in ``Path()``
          - ``output_dir`` defaults to ``input_path``'s parent
          - ``segment_strategy`` → enum ``.value`` extraction
          - ``coverage_threshold`` → divided by 100.0 (UI is 0-100, request is 0.0-1.0)
        """
        # ── Special: input_path + output_dir (Path + parent default) ────
        input_path = Path(ui_data["input_path"])
        output_dir = Path(ui_data.get("output_dir", input_path.parent))

        # ── Special: segment_strategy (enum .value extraction) ──────────
        strat = ui_data.get("segment_strategy", "auto")
        if hasattr(strat, "value"):
            strat = strat.value

        # ── Special: coverage_threshold (/100.0 transform) ─────────────
        cov = ui_data.get(
            "coverage_threshold",
            self.get_setting("summarisation.coverage_threshold", 50),
        ) / 100.0

        # ── Generic table-driven field resolution ───────────────────────
        kwargs: dict[str, Any] = {
            "input_path": input_path,
            "output_dir": output_dir,
            "segment_strategy": strat,
            "coverage_threshold": cov,
        }
        for req_attr, ui_key, setting_path, default, transform in self._REQUEST_FIELD_MAP:
            if req_attr in kwargs:
                continue  # already handled by the special cases above
            if setting_path is not None:
                value = ui_data.get(ui_key, self.get_setting(setting_path, default))
            else:
                value = ui_data.get(ui_key, default)
            if transform is not None and value is not None:
                try:
                    value = transform(value)
                except Exception:
                    pass  # keep raw value if transform fails
            kwargs[req_attr] = value

        return ConversionRequest(**kwargs)

    # ─────────────────────────────────────────────────────────────────────────
    # V7.9.0: Regenerate a single output from the Output Scanner
    # ─────────────────────────────────────────────────────────────────────────

    # Maps scanner output keys to (generator_class_name, setting_flag_attr)
    # V10.29.0 (Sprint 2.2): Now generated from core.outputs.registry — the
    # single source of truth.  Previously this dict hardcoded 10 entries
    # and silently missed the 5 V10.20.0/V10.21.0 outputs (qa, glossary,
    # patterns, cheatsheet, skill), so they couldn't be regenerated from
    # the Output Scanner.  The registry now drives all 4 surfaces.
    from core.outputs.registry import get_regenerate_map as _get_regen_map
    _REGENERATE_MAP = _get_regen_map()

    def regenerate_output(
        self,
        output_dir: Path,
        output_key: str,
        log_callback=None,
    ) -> tuple:
        """Re-run a single output generator for an already-converted book.

        Loads the saved settings + summaries from disk, instantiates the
        generator, and calls its ``generate()`` method.  Does NOT re-run
        extraction, OCR, or summarization — only the requested output.

        Args:
            output_dir: the book's output directory.
            output_key: one of the keys in ``_REGENERATE_MAP``.
            log_callback: ``fn(msg, level)`` for progress.

        Returns ``(success: bool, message: str)``.
        """
        log = log_callback or (lambda msg, level: None)
        output_dir = Path(output_dir)

        if output_key not in self._REGENERATE_MAP:
            return (False, f"Cannot regenerate '{output_key}' — not a regenerable output type.")

        gen_class_name, flag_attr = self._REGENERATE_MAP[output_key]

        # 1. Load saved settings
        config_path = output_dir / ".conversion_config.json"
        if not config_path.exists():
            return (False, f"No saved settings found ({config_path.name}). Cannot reconstruct request.")
        try:
            import json
            saved = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            return (False, f"Failed to load settings: {e}")

        # 2. Build a ConversionRequest from saved settings
        try:
            request = self.build_request_from_ui(saved)
            # Override the output_dir to point at the existing folder
            # V18.20.4.3 (P2 / W-c18): Path, not str — every other
            # construction path passes ``Path``; the str assignment
            # silently changed the field's type for the whole regenerate
            # request (downstream ``output_dir / …`` joins worked only
            # by str-concatenation luck on Windows).
            request.output_dir = Path(output_dir)
            # Force the specific output flag on
            setattr(request, flag_attr, True)
        except Exception as e:
            return (False, f"Failed to build request from saved settings: {e}")

        # 3. Load existing summaries from disk (chapter resume system)
        try:
            from core.pipeline.chapter_resume import detect_processed_chapters
            processed = detect_processed_chapters(output_dir)
            summaries = list(processed.values())
            if not summaries:
                return (False, "No valid chapter summaries found on disk. Run the main conversion first.")
            log(f"  📂 Loaded {len(summaries)} summaries from disk", "INFO")
        except Exception as e:
            return (False, f"Failed to load summaries: {e}")

        # 4. Detect book title
        book_title = saved.get("input_path", "")
        if book_title:
            book_title = Path(book_title).stem.replace("_", " ").title()
        else:
            book_title = output_dir.name

        # 5. Instantiate the generator + run it
        try:
            import core.outputs as _outputs
            gen_cls = getattr(_outputs, gen_class_name, None)
            if gen_cls is None:
                return (False, f"Generator class '{gen_class_name}' not found.")
            gen = gen_cls(request, log_callback=log)
            log(f"  🔄 Regenerating {output_key} via {gen_class_name}…", "INFO")

            # Determine the output subfolder
            from core.pipeline.output_paths import OutputPaths
            paths = OutputPaths(output_dir, output_dir.name)
            subfolder_map = {
                "briefing":       paths.briefing_dir,
                "podcast_script": paths.podcast_dir,
                "packets":        paths.packets_dir,
                "flashcards":     paths.flashcards_dir,
                "obsidian":       paths.obsidian_dir,
                "study_guide":    paths.study_guide_dir,
                "social":         paths.social_dir,
                "mindmap":        paths.mindmap_dir,
                "podcast_audio":  paths.podcast_dir,
                # V10.1.0: Scientific Evidence Map
                "evidence_map":   paths.evidence_dir,
            }
            out_subdir = subfolder_map.get(output_key, output_dir)

            # V10.1.0: EvidenceMap needs the raw source segments, which
            # the other generators don't.  Reconstruct them from the
            # markdown/chapters/ folder if it exists.
            if output_key == "evidence_map":
                segments = self._load_segments_from_disk(output_dir, log)
                result = gen.generate(summaries, segments, book_title, out_subdir)
            else:
                result = gen.generate(summaries, book_title, out_subdir)
            if result:
                log(f"  ✅ {output_key} regenerated successfully", "SUCCESS")
                return (True, f"Regenerated {output_key} ({len(result) if isinstance(result, list) else 1} file(s)).")
            else:
                log(f"  ⚠️ {output_key} regeneration returned no output", "WARNING")
                return (False, "Generator ran but produced no output. Check the log for errors.")
        except Exception as e:
            import traceback
            log(f"  ❌ {output_key} regeneration failed: {e}", "ERROR")
            log(traceback.format_exc()[-500:], "DEBUG")
            return (False, f"Generator failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # V10.1.0: helper for EvidenceMap regeneration — reconstruct segments
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_segments_from_disk(output_dir: Path, log=None) -> list:
        """Reconstruct Segment objects from the markdown/chapters/ folder.

        The Evidence Map generator needs the raw chapter source text to run
        langextract against.  When regenerating from the Output Scanner, the
        original segments aren't in memory — but the converter wrote each
        chapter's markdown to ``markdown/chapters/``.  We read those files
        back into lightweight Segment-like objects.

        Returns an empty list if the folder doesn't exist (the generator
        will then emit its guidance HTML).
        """
        from pathlib import Path
        chapters_dir = Path(output_dir) / "markdown" / "chapters"
        if not chapters_dir.is_dir():
            if log:
                log(f"  ℹ️ No chapters folder at {chapters_dir} — EvidenceMap "
                    f"will use summary text as source fallback", "DEBUG")
            return []

        # Build a minimal stand-in for Segment with the two attributes the
        # EvidenceMap generator actually reads: .heading and .content.
        class _SegStub:
            __slots__ = ("heading", "content", "start_page", "end_page")

            def __init__(self, heading, content):
                self.heading = heading
                self.content = content
                self.start_page = 0
                self.end_page = 0

        segments = []
        # Sort by filename so chapter order is stable
        try:
            chapter_files = sorted(chapters_dir.glob("*.md"),
                                   key=lambda p: p.name)
        except Exception:
            chapter_files = list(chapters_dir.glob("*.md"))
        for cf in chapter_files:
            try:
                content = cf.read_text(encoding="utf-8")
            except Exception as e:
                if log:
                    log(f"  ⚠️ Could not read {cf.name}: {e}", "DEBUG")
                continue
            heading = cf.stem.replace("_", " ").title()
            segments.append(_SegStub(heading, content))
        if log:
            log(f"  📂 Loaded {len(segments)} chapter segment(s) from disk",
                "DEBUG")
        return segments
