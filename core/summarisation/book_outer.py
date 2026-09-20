"""V0.18 (Phase 5.1, step 8) — Summarizer book-level outer loop.

summarize_chapters (the ThreadPoolExecutor chapter loop + deadline +
checkpoint wiring), build_book_summary, and _distill_book_context moved
out of summarizer.py. summarize_chapters sets self._chapter_deadline_start
immediately before calling _summarize_inner — the ordering pin in
test_deadline_watchdog.py follows the move.

Moved VERBATIM (byte-identical bodies) from ``summarizer.py`` during the
V0.18 Phase 5.1 de-monolithization, re-homed via the house mixin pattern
(cf. additive_sections / chapter_phases). ``SummarizerBookMixin`` joined the
Summarizer bases; every ``self.<attr>`` / ``self.<method>`` reference
resolves exactly as before.
"""

from __future__ import annotations

import concurrent.futures
import re
import threading
import time
from collections.abc import Callable

from core.common.progress_events import progress_json_line
from core.models import SummaryResult
from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()


class SummarizerBookMixin:
    """See the module docstring."""

    def _distill_book_context(
        self,
        prev_context: str,
        chapter_exec_summary: str,
        chapter_heading: str,
    ) -> str:
        """V18.1 (audit Q2): Build a rolling cross-chapter context.

        After each chapter is summarized, this method distills the chapter's
        executive summary into a brief entry appended to the running context.
        The running context is capped at ~600 words (4 chapters × ~150 words)
        to keep the prompt size manageable. When the cap is exceeded, the
        oldest entries are truncated.

        This is a deterministic (non-LLM) distillation — we take the first
        ~150 words of the executive summary, prefixed with the chapter
        heading. This is fast (no extra LLM call) and sufficient for giving
        the next chapter's prompt awareness of what came before.

        For a more sophisticated synthesis (LLM-distilled), set
        ``summarisation.cross_chapter_context_mode = "llm"`` — this will
        make an extra LLM call to synthesize the context, at the cost of
        ~30s per chapter. Default is ``"deterministic"`` (fast, free).
        """
        if not chapter_exec_summary:
            return prev_context

        # Deterministic mode: take first ~150 words of the exec summary
        _words = chapter_exec_summary.split()
        _chapter_entry = f"[{chapter_heading}]: " + " ".join(_words[:150])
        if len(_words) > 150:
            _chapter_entry += "…"

        if prev_context:
            _new = prev_context + "\n\n" + _chapter_entry
        else:
            _new = _chapter_entry

        # Cap at ~600 words (trim oldest entries from the front)
        _all_words = _new.split()
        if len(_all_words) > 600:
            _new = "…[earlier context trimmed]… " + " ".join(_all_words[-600:])

        return _new

    def summarize_chapters(
        self,
        chapters: list[dict[str, str]],
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_event: threading.Event | None = None,
        thermal_pause_callback: Callable[[], None] | None = None,
        chapter_done_callback: Callable[..., None] | None = None,
    ) -> list[SummaryResult]:
        """
        Summarise multiple chapters in parallel using ThreadPoolExecutor.
        VRAM‑aware: if heavy_model is set, max_workers is forced to 1.

        P1-1: ``cancel_event`` is checked between chapters so cancel
        takes effect quickly, not after every chapter finishes.

        ``thermal_pause_callback`` is called between chapters.
        If the thermal safety controller has triggered a mandatory
        cool-down, this callback blocks until the cool-down is complete.
        Pass ``None`` to disable (no thermal pausing).

        V18.20.3.0: ``chapter_done_callback(idx, summary, chapter)`` is
        invoked IMMEDIATELY after each chapter's SummaryResult is
        produced (sequential and parallel paths). It is used by the
        incremental chapter-checkpoint saver to persist each chapter
        (summary .md + per-chapter .docx) the moment it completes, so a
        crash / power cut / user-cancel never loses completed chapters.
        Callback failures are logged at WARNING and NEVER propagate —
        checkpointing is strictly best-effort.
        """
        total = len(chapters)
        if total == 0:
            return []

        self.log(f"📚 Summarising {total} chapters with {self.max_workers} worker(s)...", "INFO")

        # If only one chapter or max_workers == 1, process sequentially
        if total == 1 or self.max_workers == 1:
            results = []
            # V18.1 (audit Q2): Cross-chapter running context.
            # After each chapter, distill its executive summary into a 150-word
            # rolling synthesis. Inject into the NEXT chapter's prompt for continuity.
            # Only applies in sequential mode (max_workers=1) — parallel mode
            # processes chapters out of order, so running context doesn't apply.
            _running_book_context = ""
            # V18.1 (audit Q2): Read cross-chapter context setting (Settings is a singleton)
            from utils.settings import Settings as _Settings

            _cross_chapter_enabled = _Settings().get("summarisation.cross_chapter_context", True)
            for idx, chap in enumerate(chapters, 1):
                # check cancel between chapters
                if cancel_event and cancel_event.is_set():
                    self.log("  ⏹️ Summarisation cancelled by user — stopping.", "WARNING")
                    break
                # check thermal pause — blocks if cool-down in progress
                if thermal_pause_callback:
                    thermal_pause_callback()
                if progress_callback:
                    progress_callback(idx / total, f"Chapter {idx}/{total} – processing")
                self.log(f"📚 Chapter {idx}/{total}: {chap['heading'][:55]}…", "INFO")
                # V18.2.15 (P4): Per-chapter wall-clock deadline. Record the
                # start time so we can detect a stuck generation AFTER the
                # call returns (the in-flight Ollama call has its own HTTP
                # timeout; this catches the case where the call technically
                # returned but took far too long, indicating a model stall).
                _chap_start = time.time()
                # V18.2.22 (BUG-4): also set the instance field so
                # _summarize_inner can check it at phase boundaries and
                # short-circuit optional phases (scholar reflection, dedup,
                # consolidation) when the deadline is already exceeded.
                self._chapter_deadline_start = _chap_start
                # V18.2.25 (Phase 4.1): tracing span for the chapter root.
                # No-op when tracing disabled (span() yields None internally).
                from core.obs.tracing import span as _otel_span

                with _otel_span(
                    "chapter.summarize",
                    chapter_idx=idx,
                    chapter_total=total,
                    chapter_heading=chap["heading"][:100],
                    model=getattr(self, "primary_model", ""),
                ):
                    try:
                        _result = self._summarize_inner(
                            chap["heading"],
                            chap["content"],
                            concepts=chap.get("concepts"),
                            callouts=chap.get("callouts"),
                            book_context=_running_book_context,
                        )
                    except Exception as e:
                        # V18.20.2.0 (SWOT A7): mirror the parallel path's
                        # per-chapter handler (process_chapter below) exactly —
                        # log the crash at ERROR and record a failed
                        # SummaryResult instead of letting ONE chapter's
                        # unexpected crash kill the whole sequential run
                        # (the ONLY mode on the target machine, max_workers=1).
                        # The loop's existing FAILED branch below logs the
                        # final ❌ line, same as the as_completed loop does
                        # for the parallel path.
                        self.log(f"  ❌ Chapter {idx} failed: {e}", "ERROR")
                        logger.exception(
                            "Chapter %d/%d crashed in sequential loop (heading='%s')",
                            idx,
                            total,
                            chap["heading"][:60],
                        )
                        _result = SummaryResult(
                            chapter_heading=chap["heading"],
                            executive_summary="",
                            bullet_points=[],
                            thorough_summary="",
                            success=False,
                            error_msg=str(e),
                        )
                _chap_elapsed = time.time() - _chap_start
                # V18.2.15 (P4): Deadline check — log a traceable WARNING if
                # the chapter exceeded the budget. We DON'T hard-fail the
                # chapter (it may have produced a valid summary, just slowly),
                # but the WARNING leaves a permanent trace for diagnosis.
                # If the chapter also FAILED, the elapsed time helps explain
                # whether it was a stall (long) or a parse error (short).
                if (
                    self.is_local
                    and self.local_chapter_deadline > 0
                    and _chap_elapsed > self.local_chapter_deadline
                ):
                    self.log(
                        f"  ⏱️⚠️ V18.2.15 Chapter {idx}/{total} exceeded deadline: "
                        f"{_chap_elapsed:.0f}s > {self.local_chapter_deadline}s "
                        f"(heading='{chap['heading'][:40]}') — possible model stall. "
                        f"Summary {'kept' if _result.success else 'failed'}, but "
                        f"this chapter consumed {_chap_elapsed:.0f}s of the budget.",
                        "WARNING",
                    )
                    logger.warning(
                        "Chapter %d/%d exceeded deadline: %.0fs > %ds (heading='%s')",
                        idx,
                        total,
                        _chap_elapsed,
                        self.local_chapter_deadline,
                        chap["heading"][:60],
                    )
                else:
                    # V18.2.15 (P4): Always log the per-chapter elapsed time
                    # at DEBUG so the conversion log has a full timing trace
                    # for post-mortem diagnosis (even when under budget).
                    self.log(
                        f"  ⏱️ Chapter {idx}/{total} took {_chap_elapsed:.0f}s "
                        f"(deadline {self.local_chapter_deadline}s)",
                        "DEBUG",
                    )
                if _result.success:
                    self.log(f"✅ Chapter {idx}/{total}: {chap['heading'][:40]}… complete", "INFO")
                    # V10.16.0 (C1): Progressive output preview — show partial
                    # summary stats as each chapter finishes, so the user sees
                    # progress during the long summarization phase.
                    _bp_count = len(_result.bullet_points) if _result.bullet_points else 0
                    _exec_len = len(_result.executive_summary) if _result.executive_summary else 0
                    # V18.20.4.12 (W-b15): structured progress line — the
                    # wizard's live quality dashboard parses this JSON-first
                    # (core/common/progress_events.py); the human line below
                    # stays byte-identical as the old-log fallback source.
                    self.log(
                        progress_json_line(idx, total, _bp_count, _exec_len),
                        "DEBUG",
                    )
                    self.log(
                        f"  📊 Progress: {idx}/{total} done | "
                        f"{_bp_count} bullets | {_exec_len:,} chars exec summary",
                        "DEBUG",
                    )
                    # V18.1 (audit Q2): Update running context for the next chapter.
                    # Distill this chapter's executive summary into ~150 words.
                    if _cross_chapter_enabled and _result.executive_summary:
                        _running_book_context = self._distill_book_context(
                            _running_book_context, _result.executive_summary, chap["heading"]
                        )
                else:
                    self.log(
                        f"❌ Chapter {idx}/{total}: {chap['heading'][:40]}… FAILED: {_result.error_msg}",
                        "ERROR",
                    )
                results.append(_result)
                # V18.20.3.0: incremental checkpoint — fire the moment the
                # chapter's result exists (BEFORE the next chapter starts),
                # so a crash never loses a completed chapter.
                if chapter_done_callback is not None:
                    try:
                        chapter_done_callback(idx, _result, chap)
                    except Exception as _cb_e:
                        self.log(
                            f"  ⚠️ V18.20.3.0 chapter checkpoint callback "
                            f"failed (chapter {idx}): {_cb_e!r} — continuing.",
                            "WARNING",
                        )
            # Phase 6.4 (V0.19): end-of-run cache hit-rate summary.
            self._log_cache_stats()
            return results

        # Parallel processing
        results: list[SummaryResult | None] = [None] * total
        completed = 0

        def process_chapter(idx: int, chap: dict[str, str]) -> tuple[int, SummaryResult]:
            """Wrapper to process a single chapter and return its index."""
            # V18.20.4.11 (P2 / W-a1): stamp the per-chapter deadline start ON
            # THE WORKER THREAD. The V18.20.2.0 (SWOT A8) fix set it on the
            # MAIN thread immediately before each executor.submit against a
            # SHARED attribute, so concurrent workers all measured from the
            # MOST RECENT submission (under-approximation — the old comment
            # there already deferred "a per-worker thread-local is the full
            # fix"). Now that _chapter_deadline_start is a thread-local
            # property shim, each worker stamps its own start at pickup:
            # EXACT per-chapter elapsed time, and the watchdog stays ENABLED
            # (a main-thread-only write would leave workers seeing the None
            # default = deadline silently disabled — a regression, not a fix).
            self._chapter_deadline_start = time.time()
            try:
                result = self._summarize_inner(
                    chap["heading"],
                    chap["content"],
                    concepts=chap.get("concepts"),
                    callouts=chap.get("callouts"),
                )
                return idx, result
            except Exception as e:
                self.log(f"  ❌ Chapter {idx + 1} failed: {e}", "ERROR")
                return idx, SummaryResult(
                    chapter_heading=chap["heading"],
                    executive_summary="",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg=str(e),
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, chap in enumerate(chapters):
                # V18.20.2.0 (SWOT A8): per-chapter deadline start — now
                # stamped INSIDE process_chapter on the worker thread itself
                # (V18.20.4.11 / W-a1 thread-local fix; see the comment
                # there for why a pre-submit main-thread write no longer
                # works now that the attribute is thread-local).
                futures[executor.submit(process_chapter, i, chap)] = i

            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed += 1
                if progress_callback:
                    progress_callback(completed / total, f"Chapter {idx + 1}/{total} – complete")
                # log FAILED vs SUCCESS correctly — was always
                # logging "✅ complete" even when the chapter failed, which
                # was misleading (the user saw green checkmarks for failed chapters).
                if result.success:
                    self.log(
                        f"✅ Chapter {idx + 1}/{total}: {result.chapter_heading[:40]}… complete",
                        "INFO",
                    )
                else:
                    self.log(
                        f"❌ Chapter {idx + 1}/{total}: {result.chapter_heading[:40]}… FAILED: {result.error_msg}",
                        "ERROR",
                    )
                # V18.20.3.0: incremental checkpoint — fire as each parallel
                # future completes (chapters[idx] carries the chapter dict).
                if chapter_done_callback is not None:
                    try:
                        chapter_done_callback(idx + 1, result, chapters[idx])
                    except Exception as _cb_e:
                        self.log(
                            f"  ⚠️ V18.20.3.0 chapter checkpoint callback "
                            f"failed (chapter {idx + 1}): {_cb_e!r} — continuing.",
                            "WARNING",
                        )
                # check cancel — cancel remaining futures
                if cancel_event and cancel_event.is_set():
                    self.log(
                        "  ⏹️ Summarisation cancelled by user — stopping pending chapters.",
                        "WARNING",
                    )
                    for f in futures:
                        f.cancel()
                    break

        # Ensure all results are SummaryResult (not None)
        final_results = []
        for i, r in enumerate(results):
            if r is None:
                # Fallback for any missing results
                self.log(
                    f"  ⚠️ Chapter {i + 1} returned None – creating error placeholder.", "WARNING"
                )
                final_results.append(
                    SummaryResult(
                        chapter_heading=chapters[i]["heading"],
                        executive_summary="[Error: No result]",
                        bullet_points=[],
                        thorough_summary="",
                        success=False,
                        error_msg="No result returned from summarisation",
                    )
                )
            else:
                final_results.append(r)

        # Phase 6.4 (V0.19): end-of-run cache hit-rate summary.
        self._log_cache_stats()
        return final_results

    def _log_cache_stats(self) -> None:
        """Phase 6.4 (V0.19): end-of-run cache hit-rate summary (INFO).

        One line per cache, after the last chapter: hit-rate, size vs
        budget, and evictions — the roadmap Phase-6.4 "cache
        instrumentation" deliverable. Budget TUNING stays data-driven:
        the budgets are unchanged until a real rig shows evictions > 0
        (an eviction is the only signal that the 1000-entry FIFO cap is
        losing reusable responses)."""
        try:
            from core.llm.response_cache import response_cache

            rs = response_cache.stats()
            self.log(
                f"  💾 Response cache: {rs['hits']} hits / {rs['misses']} misses "
                f"({rs['hit_rate']:.0%} hit-rate), {rs['size']}/{rs['max']} entries, "
                f"{rs['evictions']} evictions",
                "INFO",
            )
        except Exception as _e:
            logger.debug("response-cache stats skipped: %s: %s", type(_e).__name__, _e)
        try:
            from core.llm.embedding_cache import embedding_cache

            es = embedding_cache.stats()
            _total_e = int(es.get("hits", 0)) + int(es.get("misses", 0))
            _rate_e = (es.get("hits", 0) / _total_e) if _total_e > 0 else 0.0
            self.log(
                f"  🧮 Embedding cache: {es.get('hits', 0)} hits / "
                f"{es.get('misses', 0)} misses ({_rate_e:.0%} hit-rate), "
                f"{es.get('size', 0)} entries",
                "INFO",
            )
        except Exception as _e:
            logger.debug("embedding-cache stats skipped: %s: %s", type(_e).__name__, _e)

    def build_book_summary(
        self, summaries: list[SummaryResult], book_title: str, stats: dict | None = None
    ) -> str:
        """V0.03 (P1-6): optional ``stats`` out-param receives the ACTUAL
        aggregated numbers ("bullets" = the deduped cross-chapter count,
        "chapters" = chapter count) so the caller's provenance stamp stops
        labelling chapter count as bullet count (the V0.02 rig stamped
        ``bullets=2`` on a file containing 70).

        V0.06 (rig audit F3 — GENERAL RULE: a deliverable never lists the
        same content block twice): the V0.05 book file opened with
        "## 📌 All Key Takeaways" (a concatenation of EVERY chapter's
        bullets) followed by "## 📖 Chapter-by-Chapter …" which repeated
        each chapter's FULL bullet list again — every takeaway shipped
        twice in one file. The aggregate view already exists as its own
        deliverable (keypoints/*.Keypoints.md, classified core/supporting/
        additional), so the book summary keeps the structured per-chapter
        view ONLY. Section content additionally honors the per-chapter
        output-selection flags (F1-c).
        """
        lines = [
            f"# Book Summary: {book_title}",
            "",
            f"> Provider: {self.provider} | Language: {self.language} | Chapters: {len(summaries)} | {time.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
        ]
        seen = set()
        all_bullets = []
        for s in summaries:
            for bp in s.bullet_points:
                norm = re.sub(r"[^\w\s]", "", bp.lower()).strip()
                if norm and norm not in seen and len(bp) > 10:
                    seen.add(norm)
                    all_bullets.append(bp)
        if stats is not None:
            try:
                stats["bullets"] = len(all_bullets)
                stats["chapters"] = len(summaries)
            except Exception:
                pass  # stats must never break the book summary build
        # V0.06 (F3): the global "All Key Takeaways" concatenation is
        # DELIBERATELY ABSENT — each chapter's takeaways appear exactly
        # once, under their own chapter heading below. The aggregate
        # takeaway view is the keypoints deliverable.
        lines += ["## 📖 Chapter-by-Chapter Executive Summaries", ""]
        for idx, s in enumerate(summaries, 1):
            if not s.success:
                lines += [
                    f"### {idx}. {s.chapter_heading}",
                    "",
                    f"⚠️ Summary failed: {s.error_msg or 'unknown error'}",
                    "",
                ]
                continue
            _inc_exec_s = getattr(s, "include_executive_summary", True)
            _inc_kp_s = getattr(s, "include_keypoints", True)
            _inc_th_s = getattr(s, "include_thorough_summary", True)
            if _inc_exec_s and (s.executive_summary or "").strip():
                lines += [f"### {idx}. {s.chapter_heading}", "", s.executive_summary.strip(), ""]
            else:
                lines += [f"### {idx}. {s.chapter_heading}", ""]
            if _inc_kp_s and s.bullet_points:
                lines.append("**Key takeaways:**")
                for bp in s.bullet_points:
                    bp_str = str(bp) if not isinstance(bp, str) else bp
                    lines.append(f"- {bp_str}")
                lines.append("")
            if _inc_th_s and s.thorough_summary and s.thorough_summary.strip():
                lines += [
                    "<details><summary>Detailed summary</summary>",
                    "",
                    s.thorough_summary,
                    "",
                    "</details>",
                    "",
                ]
        return "\n".join(lines)
