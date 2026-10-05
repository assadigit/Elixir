"""V0.4.26 (Phase 3 de-monolithization, commit 1 of 3): the reporting
responsibility — extracted from converter_impl.py (evidence: SWOT W2 +
README roadmap item 12, "convert 1,055 lines"; plan: Task 3-plan).

Two moves, byte-identical bodies:

- ``ConverterReportingMixin._generate_quality_report`` — the whole method
  (L584-739 of the pre-move converter_impl.py, commit 29b6c58) moved
  VERBATIM.  Mixed into ``Converter`` (appended after the existing
  mixins — the house mixin pattern, V0.18 Phase 5 / V0.4.19); the
  convert() call site ``self._generate_quality_report(segments,
  summaries)`` is unchanged and resolves through the MRO.

- ``run_diagnostic_summary`` — the 208-line end-of-run diagnostic block
  that sat inline inside ``convert()`` (L1771-1978 pre-move), moved with
  exactly three mechanical edits, per the convert()-block precedent
  (visual_features.py): (a) ``self.`` -> ``converter.``; (b) dedented one
  try-level out (12 -> 4 spaces); (c) the ONE bare ``self`` in the block
  (``getattr(self, "_cache_stats_start", ...)``) -> ``converter``.  One
  further line reflowed by the house ruff-format gate (the
  ``stamp_diagnostic(...)`` call now fits the 100-col line at the
  shallower indent) — AST-identical, documented + guarded in the
  characterization test's verbatim check.  Every convert() local the
  block reads is threaded in as a keyword parameter named EXACTLY like
  the local, so the body text is otherwise unchanged:

      ``book_title``, ``total_pages``, ``segments``, ``summaries``,
      ``warnings`` — read-only (``warnings`` is iterated, never appended
      to; nothing the block assigns is read later in convert()).
      ``_pages_processed`` — read-only (also feeds
      ConversionResult.pages_processed back in convert()).
      ``_t_start`` — the RAW ``_time_mod.time()`` timer start captured at
      the top of convert(); the block computes a numeric wall-time share
      (``_run_s = _time_mod.time() - _t_start``), not the ``_elapsed()``
      string, so the start float is threaded directly — the same
      explicit-threading discipline as run_summarization's ``elapsed_fn``.

Module-level names the moved bodies reference: ``logger`` and
``_time_mod``.  ``logger`` binds ``get_main_logger()`` — the SAME
"Elixir" logger object the bodies reached through converter_impl's module
globals before the move (not ``logging.getLogger(__name__)`` like the
other conversion modules: a verbatim move must not change the routing of
the ``logger.debug(...)`` failure traces).  ``_time_mod`` mirrors
converter_impl's ``import time as _time_mod``.

Leaf module: no ``core.pipeline`` imports (acyclic, like every other
conversion/* module).
"""

from __future__ import annotations

import time as _time_mod
from typing import Any

from utils.logging import get_main_logger

logger = get_main_logger()


class ConverterReportingMixin:
    """Reporting machinery for the Converter (see module docstring).

    Expects the host class to provide: ``self.request``, ``self.paths``,
    ``self._log`` — the standard Converter surface.
    """

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


def run_diagnostic_summary(
    converter: Any,
    *,
    book_title: str,
    total_pages: int,
    _pages_processed: int,
    segments: list[Any],
    summaries: list[Any],
    warnings: list[str],
    _t_start: float,
) -> None:
    """Print the end-of-conversion diagnostic summary (VERBATIM move from
    convert(); see the module docstring for the parameter threading).

    Read-only over every parameter — returns None.  Every lazy import and
    ``logger.debug`` trace is exactly as it was inline.
    """
    # End-of-conversion diagnostic summary — captures the
    # final state (counts, timings, output paths, warnings) so the
    # user can paste this block when reporting issues.  This is the
    # "gimmicks/nuances/micro-mistakes" snapshot the user asked for.
    # version header now reads from VERSION file (was stale
    # "V7.5.1" hardcoded).
    converter._log("", "INFO")
    converter._log(
        f"━━━ Elixir v{converter._get_app_version()} Conversion Diagnostic Summary ━━━", "INFO"
    )
    converter._log(f"  Book: {book_title}", "INFO")
    converter._log(f"  Total pages: {total_pages}", "INFO")
    # V18.20.3.6: when a chapter selection / page range limited the
    # run, say so right next to the book total — the completion
    # modal reports the same number (previously it showed the whole
    # book's total for a single-chapter run, e.g. "397" for 18).
    if _pages_processed != total_pages:
        converter._log(
            f"  Pages processed: {_pages_processed} "
            f"(selection active — {_pages_processed} of {total_pages} pages)",
            "INFO",
        )
    converter._log(
        f"  Segments: {len(segments)} "
        f"(chapters: {len([s for s in segments if s.segment_type == 'chapter'])}, "
        f"chunks: {len([s for s in segments if s.segment_type == 'chunk'])})",
        "INFO",
    )
    converter._log(f"  Summaries generated: {len(summaries) if summaries else 0}", "INFO")
    if summaries:
        ok = sum(1 for s in summaries if s.success)
        failed = len(summaries) - ok
        total_bullets = sum(len(s.bullet_points) for s in summaries)
        converter._log(
            f"    Success: {ok}, Failed: {failed}, Total bullets: {total_bullets}", "INFO"
        )
        # Coverage stats from the quality report if available
        try:
            import json as _json

            qr = converter.paths.quality_report
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
                converter._log(f"    Coverage: {_cov_str}", "INFO")
                _rf = totals.get("recall_floor") or {}
                if _rf.get("theorists_total"):
                    converter._log(
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
    converter._log(f"  Warnings: {len(warnings)}", "INFO")
    for w in warnings:
        converter._log(f"    ⚠️ {w}", "WARNING")
    converter._log(f"  Output dir: {converter.output_dir}", "INFO")
    converter._log(f"  Log file: {converter.conv_logger.log_path}", "INFO")
    converter._log(f"  Diagnostic JSONL: {converter.conv_logger.diagnostic_path}", "INFO")
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
        _summ_root = converter.paths.summaries_dir
        if _summ_root.exists():
            _mds = sorted(_summ_root.rglob("*.md"))
            if _mds:
                converter._log(f"  Summary files ({len(_mds)}):", "INFO")
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
                    _level, _msg = stamp_diagnostic(str(_sf), _text, current_version=_app_ver)
                    converter._log(f"    {_msg}", _level)
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
            converter._log(
                f"  LLM calls: {_tel['calls']} — "
                f"{_tel['total_s']:.0f}s total "
                f"({_tel['total_s'] / _run_s * 100:.0f}% of run wall-time), "
                f"truncated {_tel['truncated']}",
                "INFO",
            )
            for _rank, _c in enumerate(_tel["slowest"], 1):
                converter._log(
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
        _start = getattr(converter, "_cache_stats_start", None) or {}
        _d_hits = _st.get("hits", 0) - _start.get("hits", 0)
        _d_miss = _st.get("misses", 0) - _start.get("misses", 0)
        if _d_hits or _d_miss:
            converter._log(
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
            converter._log(
                f"  Models still in Ollama server memory at exit: "
                f"{list(loaded.keys())} — normal (server-managed "
                f"keep-alive; speeds up the next run)",
                "INFO",
            )
        else:
            converter._log("  Models loaded at exit: (none — all unloaded)", "INFO")
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
    converter._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")
