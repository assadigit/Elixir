"""V0.4.26 (Phase 3 de-monolithization, commit 3 of 3): the finalization
responsibility — extracted from converter_impl.py (evidence: SWOT W2 +
README roadmap item 12, "convert 1,055 lines"; plan: Task 3-plan).

Three pieces:

1. ``assess_completion`` — the completion-assessment decision logic that
   sat inline in ``convert()`` (the old-plan L1625-1712 block + the
   terminal ``success=``/``error_msg=`` result expressions), now a PURE
   function: no converter/self state — every input is an explicit
   parameter (the V18.6.3 explicit-parameters crash-mitigation
   convention).  It holds the crown-jewel false-success guards, moved
   VERBATIM (only the ``self.request.X`` -> ``X`` parameter threading
   and the emission conversion documented below):
   - V18.2.4 — all-chapters-failed ERROR (with the "ollama pull" hint);
   - V18.20.2.0 (SWOT A15) — cancel-aware completion status;
   - V0.02 (false-success RCA) — zero summaries with an explicit
     chapter selection is a HARD failure; without one it stays a
     success but is announced with a loud WARNING;
   - partial-failure counting (the "N chapter(s) failed … M succeeded"
     line).

   EMISSION DESIGN (the one sanctioned non-verbatim edit): the decision
   no longer emits inline — each branch's ``self._update_status(msg)``
   became ``status_message = msg`` and each ``self._log(msg, level)``
   became ``log_lines.append((level, msg))`` (the message/level source
   text is byte-identical).  ``convert()`` replays the returned values
   at the exact inline position: the status first, then the log lines
   in order.  Every branch emits exactly ONE status before its log
   lines, so this single-assessment replay preserves the emitted output
   byte-identically (the chosen design — rather than splitting the
   decision across multiple assess calls or keeping interleaved
   emissions in convert(), both of which would change the shape of the
   guard block).

2. ``run_screenshots_and_graphs`` — the opt-in screenshots/graphs block
   moved VERBATIM (``self.`` -> ``converter.``); ``book_title`` /
   ``total_pages`` / ``toc_entries`` are threaded convert() locals.
   The ``_derive_page_ranges_from_toc`` helper STAYS on the Converter
   class (the runner reaches it through ``converter.``).

3. ``run_library_tracking`` — the library/recording block moved VERBATIM
   (``self.`` -> ``converter.``); the convert() local ``_kp_final_count``
   is threaded as the ``kp_final_count`` parameter (runner-convention
   name, no leading underscore).

Module-level names the moved bodies reference: ``logger`` — the SAME
"Elixir" main-logger object the bodies reached through converter_impl's
module globals before the move (``get_main_logger()``, not
``logging.getLogger(__name__)``: a verbatim move must not change the
routing of the ``logger.debug`` traces).

Leaf module: no ``core.pipeline`` imports (acyclic, like every other
conversion/* module).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.logging import get_main_logger

logger = get_main_logger()


@dataclass
class CompletionAssessment:
    """The completion decision convert()'s tail needs (see module docstring).

    Fields:
        success: the ``ConversionResult.success`` value (the false-success
            guards folded into one boolean — V18.2.4 / SWOT A15 / V0.02).
        error_msg: the ``ConversionResult.error_msg`` value (None on
            success; the cancelled / all-failed / zero-summaries messages).
        status_message: the ONE terminal status the inline block pushed
            through ``self._update_status`` — every branch emits exactly
            one, always before its log lines; convert() replays it first.
        log_lines: the ordered ``(level, message)`` pairs the inline block
            pushed through ``self._log`` — convert() replays them in order,
            so the emitted output is byte-identical.
    """

    success: bool
    error_msg: str | None = None
    status_message: str | None = None
    log_lines: list[tuple[str, str]] = field(default_factory=list)


def assess_completion(
    summaries: list[Any],
    *,
    generate_summaries: Any,
    selected_chapters: Any,
    cancel_event: Any,
) -> CompletionAssessment:
    """Decide the terminal completion status (PURE — no converter state).

    Every input is an explicit parameter (the V18.6.3 convention): the
    ``self.request.generate_summaries`` / ``self.request.selected_chapters``
    reads became the ``generate_summaries`` / ``selected_chapters``
    parameters, and ``self.cancel_event`` became the ``cancel_event``
    parameter (read once, exactly where the inline block read it).
    The guard logic is the VERBATIM pre-move convert() block; the inline
    emissions became the returned ``status_message`` + ordered
    ``log_lines`` (see the module docstring for why that preserves the
    emitted output byte-identically).
    """
    status_message: str | None = None
    log_lines: list[tuple[str, str]] = []

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
    _cancelled = cancel_event.is_set()

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
    _zero_summaries = not summaries and bool(generate_summaries) and not _cancelled
    _selection_active = bool(selected_chapters)
    if _all_failed:
        status_message = "Conversion FAILED — all chapters returned empty"
        log_lines.append(("ERROR", "❌ Conversion FAILED: all chapters returned empty responses."))
        log_lines.append(
            (
                "ERROR",
                f"   {_failed_count} chapter(s) failed — model produced no content. "
                f"Likely causes: model not installed, VRAM insufficient, or quantization "
                f"too aggressive for the prompt complexity. "
                f"Try: ollama pull <model>, or switch to a less aggressive quant (IQ2_M "
                f"instead of IQ2_XXS), or raise temperature to 1.0.",
            )
        )
    elif _zero_summaries and _selection_active:
        status_message = "Conversion FAILED — no selected chapters summarized"
        log_lines.append(
            (
                "ERROR",
                f"❌ Conversion FAILED: none of the {len(selected_chapters)} "
                f"selected chapter(s) produced a summary — the selection "
                f"matched no summarizable section (every surviving segment "
                f"was skipped as front/reference matter). No summary "
                f"outputs were written.",
            )
        )
        log_lines.append(
            (
                "ERROR",
                "   Try: re-open the chapter selector and re-pick chapters "
                "(per-chapter author/annotation bookmarks are no longer "
                "listed), or convert the whole book.",
            )
        )
    elif _zero_summaries:
        status_message = "Conversion completed!"
        log_lines.append(("SUCCESS", "✅ Conversion complete."))
        log_lines.append(
            (
                "WARNING",
                "   ⚠️ Zero sections were summarized — every segment was "
                "skipped as front/reference matter while summaries were "
                "requested. Markdown/DOCX outputs were still written; if "
                "you expected chapter summaries, disable the content "
                "filter or select chapters explicitly.",
            )
        )
    elif _cancelled:
        status_message = "Conversion cancelled"
        log_lines.append(
            (
                "WARNING",
                "⏹️ Conversion cancelled — partial summaries saved; downstream phases skipped.",
            )
        )
    else:
        status_message = "Conversion completed!"
        log_lines.append(("SUCCESS", "✅ Conversion complete."))
        if _failed_count > 0:
            log_lines.append(
                (
                    "WARNING",
                    f"   ⚠️ {_failed_count} chapter(s) failed (empty response) — "
                    f"{len(_valid_summaries)} succeeded.",
                )
            )

    return CompletionAssessment(
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
                f"None of the {len(selected_chapters)} selected chapter(s) "
                f"were summarized — the selection matched no summarizable section. "
                f"Re-pick chapters in the selector (per-chapter author bookmarks "
                f"are no longer listed) or convert the whole book."
                if (_zero_summaries and _selection_active)
                else None
            )
        ),
        status_message=status_message,
        log_lines=log_lines,
    )


def run_screenshots_and_graphs(
    converter: Any,
    *,
    book_title: str,
    total_pages: int,
    toc_entries: Any,
) -> None:
    """Run the opt-in screenshots/graphs extraction (VERBATIM move from
    convert(); see the module docstring).  ``book_title`` / ``total_pages``
    / ``toc_entries`` are threaded convert() locals; everything else is
    read through ``converter`` — including ``_derive_page_ranges_from_toc``,
    which STAYS on the Converter class.
    """
    # Screenshots + graphs — now opt-in (default OFF)
    # Previously captured 174 screenshots automatically, adding 10+ minutes.
    # Now only runs if the user explicitly enabled it.
    # V18.20.2.0 (SWOT A15): cancel gate — screenshots are opt-in but
    # run 10+ minutes when enabled; a cancelled run must not start them.
    if converter.settings.get(
        "outputs_optin.screenshots", False
    ) and not converter._cancel_requested("screenshots/graphs"):
        try:
            from core.pdf.table_graph_extractor import TableGraphExtractor

            extractor = TableGraphExtractor(log_callback=converter._log)
            # screenshots now respect ALL page-selection
            # mechanisms — page range, manual_segments, AND selected_chapters.
            # Previously only manual_segments was checked, so screenshots
            # captured ALL pages even when chapter selection was active.
            page_list = list(range(1, total_pages + 1))
            # 1. Apply page range
            if converter.request.page_range_start or converter.request.page_range_end:
                _start = converter.request.page_range_start or 1
                _end = converter.request.page_range_end or total_pages
                page_list = [p for p in page_list if _start <= p <= _end]
            # 2. Apply manual_segments (chapter selector page ranges)
            if converter.request.manual_segments:
                seg_pages = set()
                for start, end in converter.request.manual_segments:
                    for p in range(max(1, start), min(total_pages + 1, end + 1)):
                        seg_pages.add(p)
                page_list = [p for p in page_list if p in seg_pages]
            # 3. Apply selected_chapters (derived page ranges from TOC)
            elif converter.request.selected_chapters:
                toc_page_set = converter._derive_page_ranges_from_toc(
                    toc_entries, converter.request.selected_chapters, total_pages
                )
                if toc_page_set:
                    page_list = [p for p in page_list if p in toc_page_set]
            result = extractor.extract(
                converter.request.input_path,
                converter.output_dir,
                page_list,
                book_title=book_title,
            )
            if result["table_count"] > 0 or result["graph_count"] > 0:
                converter._log(
                    f"  📊 Tables: {result['table_count']}, Graphs: {result['graph_count']} → tables.md + graphs.md",
                    "INFO",
                )
        except Exception as e:
            converter._record_partial_failure("Table/graph extraction", e)
    else:
        converter._log("  ⏭️ Screenshots/graphs skipped (opt-in, disabled)", "DEBUG")


def run_library_tracking(
    converter: Any,
    *,
    book_title: str,
    summaries: list[Any],
    segments: list[Any],
    kp_final_count: int | None,
) -> None:
    """Record the converted book in the library (VERBATIM move from
    convert(); see the module docstring).  ``kp_final_count`` is the
    convert() local ``_kp_final_count`` (the W11 deduped count) threaded
    under the runner-convention name.
    """
    # Library tracking — add book to library
    # V18.20.2.0 (SWOT A15): cancel gate — a cancelled run must not
    # register the partial book in the library.
    if not converter._cancel_requested("library tracking"):
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

                _qr_lib = converter.paths.quality_report
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
            lib = LibraryManager(log_callback=converter._log)
            lib.add_book(
                title=book_title,
                source_file=converter.request.input_path.name,
                chapters_processed=len(summaries) if summaries else 0,
                total_chapters=len(segments) if segments else 0,
                concepts_extracted=sum(len(s.bullet_points) for s in summaries) if summaries else 0,
                # V18.20.3.10 (W11): the DEDUPED count that shipped in
                # the keypoints file (was the raw bullet sum — the
                # 41-vs-36 mismatch, .3.7 SWOT W11).
                keypoints_count=(
                    kp_final_count
                    if kp_final_count is not None
                    else (sum(len(s.bullet_points) for s in summaries) if summaries else 0)
                ),
                coverage=_cov_lib,
                output_dir=str(converter.output_dir),
            )
        except Exception as e:
            converter._record_partial_failure("Library tracking", e)
