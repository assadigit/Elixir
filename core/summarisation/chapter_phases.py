"""V0.18 (Phase 5.1, step 1) — chapter-phase methods for Summarizer.

The post-judge tail of ``Summarizer._summarize_inner`` (the recovery pass,
deterministic judge, post-checks + recall floors, and the finalize/ship
phase — lines 4705-5559 of the pre-V0.18 summarizer.py) moved VERBATIM
into this module, re-homed via the house mixin pattern
(``SummarizerChapterPhasesMixin``): every ``self.<attr>`` / ``self.<method>``
reference resolves exactly as before.

VERBATIM CONTRACT (the house decomposition pattern, cf. additive_sections):
every method body is byte-identical to the V0.17 summarizer.py source —
only the method signature (state passed in) and the trailing ``return``
(rebound state passed out) are new. The orchestrator in summarizer.py
threads the same local names through the phase calls in the same order.

What lives here (moved VERBATIM, in the original relative order):

  - ``_phase_recovery_pass``         quarantine recovery, scholar
    reflection (+ gap-fill-only + anti-false-precision), first semantic
    dedup + normalization, VRAM recovery + bullet consolidation.
  - ``_phase_deterministic_judge``   V17.6 deterministic judge: analysis
    lookup, bullets-only + thorough-only judges, gfb batch gap-fill,
    Lists & Frameworks injection.
  - ``_phase_postchecks_and_floors`` conclusion bullets, second semantic
    dedup (non-skippable), the deterministic post-checks block (ship-time
    cap, excerpt pruning, thorough re-derivation, thorough-judge re-run,
    exec fallback), recall-floor analysis, 80-bullet coverage-aware cap,
    thorough-theorist floor, recall-floor probe.
  - ``_phase_finalize``              per-chapter quarantine record + the
    final ``SummaryResult`` construction.

NOT moved (stays in summarizer.py): ``_summarize_inner`` itself — now the
≤300-line orchestrator that owns the strategy dispatch and threads state
between these phases.
"""

from __future__ import annotations

import re
import time

from core.models import SummaryResult
from core.summarisation.gap_fill_batch import batch_gap_fill as gfb_batch_gap_fill
from utils.logging import get_main_logger
from utils.token_counter import count_tokens

# The SAME logger object summarizer.py's module-level ``logger`` holds (the
# main app logger) — the moved bodies' ``logger.debug`` fail-soft lines
# behave identically to pre-move.
logger = get_main_logger()


class SummarizerChapterPhasesMixin:
    """Chapter-phase methods for :class:`Summarizer` (see module docstring)."""

    def _phase_recovery_pass(self, heading, content, parsed, exec_sum, bullets, thorough):
        # ── V10.28.0 (Sprint 1.4): Recovery pass ──────────────────────────
        # After ALL drop sites have run, re-scan the quarantine and
        # resurrect any bullet whose source_overlap exceeds the recovery
        # threshold (default 0.30).  This catches bullets that were dropped
        # by a strict threshold (F4/Phase 2.2/Judge) but are actually
        # well-grounded paraphrases.  Resurrected bullets are re-inserted
        # into the live bullet list and marked ``recovered: true`` in
        # ``drops.jsonl``.
        #
        # In conservative mode this is a no-op: nothing was actually dropped
        # (only logged), so there is nothing to recover.  We still call it
        # for the audit log (it records "0 eligible" at DEBUG level).
        bullets = self._recover_quarantined(bullets, content)

        # V13.41.0: Scholar reflection — meta-cognitive gap analysis.
        # Runs AFTER all processing (B4, gap-fill, judge, recovery) when the
        # summary is in its final form. The LLM reviews its own output and
        # identifies chapter-specific gaps ("what did I miss?").
        # Update parsed with final values so the reflection sees the final summary.
        # V13.41.1: Wrapped in try/except to prevent ANY crash from killing
        # the conversion. The scholar reflection is optional — if it fails,
        # the summary is still complete without it.
        parsed["bullet_points"] = bullets
        parsed["executive_summary"] = exec_sum
        parsed["thorough_summary"] = thorough
        try:
            # V18.2 (audit Fix 2): Scholar's Reflections is now optional (default OFF).
            # The user's analysis showed this section was the #1 defect — it
            # contradicts itself by claiming content is "missing" that appears
            # elsewhere in the summary (caused by the truncation bug, now fixed).
            # The gap-fill mechanism still runs (it adds genuinely missing content
            # as new bullets), but the "what's missing" TEXT section is suppressed
            # by default. Enable via settings: summarisation.scholar_reflections_enabled
            from utils.settings import Settings as _Settings

            _scholar_enabled = _Settings().get("summarisation.scholar_reflections_enabled", False)
            # V18.2.22 (BUG-4): Skip scholar reflection if the chapter deadline
            # is already exceeded — it's optional and consumes an LLM call
            # (~2.5 min in the V18.2.20 conversion log).
            if not self._deadline_exceeded("scholar reflection"):
                if _scholar_enabled:
                    self._scholar_reflection(heading, content, parsed)
                else:
                    # Still run gap-fill (adds missing content), but skip the
                    # self-contradicting "reflections" text section.
                    self._scholar_reflection_gapfill_only(heading, content, parsed)
            else:
                self.log("    ⏭️  Scholar reflection skipped (deadline exceeded)", "INFO")
        except Exception as _e:
            self.log(f"    ⚠️ Scholar reflection crashed (non-fatal): {_e}", "WARNING")
            logger.debug("scholar reflection crashed: %s: %s", type(_e).__name__, _e)
            parsed["scholar_reflections"] = ""  # ensure empty, not None

        # V13.45.0: CRITICAL FIX — the scholar reflection's gap-fill bullets
        # were being LOST because SummaryResult used the local `bullets`
        # variable (the OLD list) instead of parsed["bullet_points"] (the NEW
        # list with gap-fill bullets appended). This bug has been present since
        # V13.42.0 and silently discarded every gap-fill bullet. Now we read
        # the updated bullets back from parsed.
        bullets = parsed.get("bullet_points", bullets) or bullets
        exec_sum = parsed.get("executive_summary", exec_sum) or exec_sum
        thorough = parsed.get("thorough_summary", thorough) or thorough

        # V13.45.0: Anti-false-precision post-check — scans the final summary
        # for "Author A views X while Author B views Y" patterns where the
        # source actually groups A and B together. Rewrites to preserve the
        # grouping. Deterministic, no LLM call.
        try:
            self._anti_false_precision_check(heading, content, parsed)
            # Re-read in case the check rewrote bullets/exec/thorough
            bullets = parsed.get("bullet_points", bullets) or bullets
            exec_sum = parsed.get("executive_summary", exec_sum) or exec_sum
            thorough = parsed.get("thorough_summary", thorough) or thorough
        except Exception as _e:
            self.log(f"    ⚠️ Anti-false-precision check crashed (non-fatal): {_e}", "WARNING")
            logger.debug("anti-false-precision crashed: %s: %s", type(_e).__name__, _e)

        # V18.2.22 (BUG-4): Skip semantic dedup if deadline exceeded — it's
        # optional and uses the embedder (which may be the broken one that
        # caused the 37-dropped-then-resurrected churn in V18.2.20).
        if self._deadline_exceeded("semantic dedup"):
            self.log("    ⏭️  Semantic dedup skipped (deadline exceeded)", "INFO")
        else:
            # V13.45.5: Semantic dedup pass — after scholar reflection adds gap-fill
            # bullets, there may be semantic duplicates (same concept, different
            # wording). Use embeddings to detect and remove them. This runs AFTER
            # all bullet-generation stages (B4, B3, gap-fill, scholar reflection)
            # to catch cross-stage redundancy that rapidfuzz missed.
            try:
                before_count = len(bullets)
                bullets = self._semantic_dedup_bullets(bullets)
                after_count = len(bullets)
                if before_count != after_count:
                    self.log(
                        f"    🧹 Semantic dedup: {before_count} → {after_count} bullets "
                        f"(removed {before_count - after_count} semantic duplicates)",
                        "INFO",
                    )
                    parsed["bullet_points"] = bullets
            except Exception as _e:
                self.log(f"    ⚠️ Semantic dedup crashed (non-fatal): {_e}", "WARNING")
                logger.debug("semantic dedup crashed: %s: %s", type(_e).__name__, _e)
        # V16.0.2: Normalization — its own try/except
        try:
            bullets = self._normalize_bullets(bullets)
            parsed["bullet_points"] = bullets
            self.log(
                f"    \U0001f9f9 V16.0.2 Bullet normalization: {len(bullets)} bullets normalized",
                "DEBUG",
            )
        except Exception as _e:
            self.log(f"    \u26a0\ufe0f Bullet normalization crashed (non-fatal): {_e}", "WARNING")

        # V16.0.1: VRAM recovery BEFORE consolidation
        self._recover_vram(context="pre-bullet-consolidation", delay_sec=30.0)

        # V16.0.2: Bullet consolidation — its own try/except with timeout
        # V18.15: User rule: "Only consolidate bullets if you're 100% sure it
        # won't hurt coverage or accuracy. More bullets is better than lower
        # coverage/accuracy." Removed the min floor (10), the max cap (80),
        # and the post-consolidation warning — no min/max constraints on
        # bullet count. The LLM consolidation (merges 95%+ identical) is the
        # ONLY consolidation that runs. If it's skipped (deadline), ALL
        # bullets pass through unconsolidated — more bullets is better than
        # losing coverage.
        if self._deadline_exceeded("bullet consolidation"):
            self.log("    ⏭️  Bullet consolidation skipped (deadline exceeded)", "INFO")
        else:
            try:
                # V18.20.3.7 (RC-A): heading passed so the delegate can arm
                # the deterministic coverage assertion (reject any
                # consolidation that would lose a covered author; salvage
                # on truncated responses). See bullet_consolidation.py.
                bullets = self._consolidate_bullets(bullets, heading=heading)
                parsed["bullet_points"] = bullets
            except Exception as _e:
                self.log(
                    f"    \u26a0\ufe0f Bullet consolidation crashed (non-fatal): {_e}", "WARNING"
                )
        return bullets, exec_sum, thorough

    def _phase_deterministic_judge(self, heading, content, exec_sum, bullets, thorough):
        # V17.6: Deterministic judge — moved here from inside _gap_fill_concepts().
        # V17.5 had a bug: the V17.4 early-return from _gap_fill_concepts() skipped
        # PAST the judge block at the end of that method. Now the judge runs HERE,
        # AFTER all bullet-generation stages (B4, 3-Tier, self-review, content
        # judge, scholar reflection, consolidation) — the final coverage check.
        #
        # This is the BINDING check: if the deterministic analysis found 31 authors
        # and gemma only covered 28, the judge gap-fills the 3 missing ones.
        # Unlike the LLM content judge (which can be auto-passed), this check
        # is 100% reliable regex — it cannot be overridden.
        try:
            from core.preprocessing.deterministic_analyzer import (
                check_coverage,
                extract_authors_from_analysis,
                find_analysis_for_heading,
            )

            _seg_path, _analysis = find_analysis_for_heading(
                self.request.output_dir,
                heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
            if _analysis:
                _det_authors = extract_authors_from_analysis(_analysis)
                if _det_authors:
                    # V18.14: Check bullets ALONE and thorough ALONE as
                    # independent units. The old code checked the COMBINED
                    # exec+bullets+thorough text — so a theorist mentioned only
                    # in the thorough (but NOT in the bullets) was considered
                    # "covered." This is wrong: a user who only reads bullets
                    # must get 100% coverage. Compensating bullet gaps with the
                    # thorough summary is NOT accepted.
                    #
                    # Now we check:
                    # 1. Bullets-only coverage — if a theorist is missing from
                    #    the bullets, gap-fill them INTO the bullets.
                    # 2. Thorough-only coverage — if a theorist is missing from
                    #    the thorough, log a WARNING (the thorough is a
                    #    narrative, so we don't force gap-fill, but the user
                    #    is notified).
                    _bullets_only = " ".join(bullets) if bullets else ""
                    _cov = check_coverage(_analysis, _bullets_only)
                    _missing = _cov["missing"]
                    _total = _cov["total"]
                    _pct = _cov["coverage_pct"]
                    self.log(
                        f"    📊 V18.14 Bullets-only judge: {_cov['covered']}/{_total} "
                        f"authors in bullets ({_pct:.0%})"
                        + (
                            f" — MISSING from bullets: {_missing[:5]}"
                            if _missing
                            else " — ALL IN BULLETS ✅"
                        ),
                        "INFO",
                    )
                    # Also check thorough-only coverage (informational)
                    _thorough_only = thorough or exec_sum or ""
                    _cov_thorough = check_coverage(_analysis, _thorough_only)
                    _missing_thorough = _cov_thorough["missing"]
                    _pct_thorough = _cov_thorough["coverage_pct"]
                    self.log(
                        f"    📊 V18.14 Thorough-only judge: {_cov_thorough['covered']}/{_total} "
                        f"authors in thorough ({_pct_thorough:.0%})"
                        + (
                            f" — MISSING from thorough: {_missing_thorough[:5]}"
                            if _missing_thorough
                            else " — ALL IN THOROUGH ✅"
                        ),
                        "INFO" if not _missing_thorough else "WARNING",
                    )
                    # If authors are missing from bullets, do targeted gap-fill.
                    # V18.14.1: Removed the len(_missing) <= 20 cap — the V18.14.0
                    # audit found that when 23 theorists were missing from bullets
                    # (23 > 20), the gap-fill SKIPPED entirely, leaving 74% of
                    # theorists missing from the bullets. Now the gap-fill runs
                    # regardless of how many are missing, processing 8 at a time
                    # in a loop until all are covered or the deadline is exceeded.
                    # V18.14.1: Added the loop — the old code processed only
                    # _missing[:8] in one LLM call, leaving 15+ theorists
                    # uncovered. Now it loops: 8 at a time, re-checking coverage
                    # after each batch, until all are covered or the deadline
                    # fires.
                    if _missing:
                        # V18.20.3.12 (Phase 4 / W6-O5 god-class decomposition):
                        # the ~478-line V18.14.1 batch gap-fill loop (rounds of
                        # 8 missing authors, re-checking coverage, the
                        # V18.20.3.4 veto/mention-only/give-up accounting, the
                        # V18.20.3.7 zero-yield escalation + telemetry) is
                        # extracted verbatim to
                        # ``gap_fill_batch.batch_gap_fill``. The loop's locals
                        # (``_total_added`` / ``_still_missing`` /
                        # ``_given_up`` / ``_gap_fill_round``) were never read
                        # after the block, so the outcome return value is
                        # ignored here (all reporting happens inside the loop,
                        # verbatim). The ``bullets`` list is mutated IN-PLACE
                        # (appended to) by the callee, exactly as the inline
                        # code did. The callables and the judge locals
                        # (``_analysis``, ``_det_authors``, ``check_coverage``)
                        # are passed as explicit parameters — the proven-safe
                        # pattern, NOT a context object. Byte-for-byte
                        # identical behaviour (characterization tests in
                        # ``tests/test_gap_fill_batch.py``).
                        gfb_batch_gap_fill(
                            heading,
                            content,
                            bullets,
                            _missing,
                            _analysis,
                            _det_authors,
                            check_coverage=check_coverage,
                            call_fast_llm=self._call_fast_llm,
                            temperature=self.temperature,
                            strip_thinking=self._strip_thinking,
                            filter_thinking_bullets=self._filter_thinking_bullets,
                            log=self.log,
                        )

                    # V17.7: Inject ALL lists from the source as a dedicated
                    # "## Lists & Frameworks" section. V18.2.18 Improvement 3:
                    # This is now CONDITIONAL on a setting (default: off).
                    # The user's V18.2.15 analysis said "I'd remove this section
                    # entirely for a human-facing summary" because it duplicates
                    # info already in Key Takeaways. Power users who want the
                    # raw list extraction can enable it via
                    # `summarisation.inject_lists_section: true`.
                    try:
                        from utils.settings import Settings as _S

                        _inject_lists = _S().get("summarisation.inject_lists_section", False)
                    except Exception:
                        _inject_lists = False
                    if _inject_lists:
                        try:
                            from pathlib import Path as _P

                            from core.preprocessing.deterministic_analyzer import (
                                format_lists_section,
                            )

                            _seg_path_obj = _P(_seg_path) if _seg_path else None
                            if _seg_path_obj and _seg_path_obj.exists():
                                _seg_content = _seg_path_obj.read_text(encoding="utf-8")
                                _lists_section = format_lists_section(_seg_content)
                                if _lists_section:
                                    _list_count = _lists_section.count("### List ")
                                    thorough = (thorough or "") + "\n\n" + _lists_section
                                    self.log(
                                        f"    📝 V17.7: Injected Lists & Frameworks section ({_list_count} lists, all types) [inject_lists_section=true]",
                                        "INFO",
                                    )
                        except Exception as _le:
                            self.log(
                                f"    ⚠️ V17.7: Lists section injection failed: {_le}", "WARNING"
                            )
                    else:
                        self.log(
                            "    📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)",
                            "DEBUG",
                        )
            else:
                self.log(
                    "    [V17.6] No analysis found for judge — skipping deterministic coverage check",
                    "DEBUG",
                )
        except Exception as _e:
            self.log(f"    ⚠️ V17.6: Deterministic judge failed: {_e}", "WARNING")
        return thorough

    def _phase_postchecks_and_floors(
        self,
        heading,
        content,
        parsed,
        exec_sum,
        bullets,
        thorough,
        _inc_thorough_lp,
        _inc_kp_lp,
        _src_words_lp,
        _th_hi_lp,
        _bp_lo_lp,
        _bp_hi_lp,
    ):
        # V18.15.9.0: Ensure the source's enumerated conclusions (e.g., the 7
        # characteristics of solid identity) appear as a DISTINCT bullet group.
        # The V18.15.8.0 audit found these were in the thorough summary but NOT
        # as distinct bullets (the gold standard V18.15.3.2 had them as distinct
        # bullets). This is a DETERMINISTIC guarantee (no LLM call) — runs AFTER
        # the deterministic judge + gap-fill (so gap-fill has a chance to add
        # them naturally first), but BEFORE postchecks (so the new bullets get
        # post-checked too).
        try:
            self._ensure_conclusion_bullets(heading, content, parsed)
            bullets = parsed.get("bullet_points", bullets) or bullets
        except Exception as _e:
            self.log(f"    ⚠️ V18.15.9.0: Conclusion-bullets check failed: {_e}", "WARNING")

        # V18.20.3.2 (audit N6 / P1-b): SECOND semantic-dedup pass AFTER all
        # bullet-generation stages. The first pass runs BEFORE the V17.6
        # deterministic judge + V18.14.1 batch gap-fill + conclusion bullets —
        # so bullets added by those stages were never deduped. The V18.20.3.1
        # run shipped a near-verbatim duplicate pair from gap-fill ("AuthorM
        # and AuthorN: Made significant contributions to the specific area of
        # gender identity consolidation" / "Meyer: Provided significant
        # contributions to the specific area of gender identity
        # consolidation"). The embedder is already loaded from the first pass
        # — this costs ~1s.
        # V18.20.3.4 (RC-2, audit v182033): this dedup is NO LONGER
        # deadline-skippable. The V18.20.3.3 run hit the chapter deadline
        # (2634s > 2400s) exactly here — "skipping optional phase:
        # post-gap-fill semantic dedup" — and shipped 6 duplicate bullets
        # (#17/#18/#26/#34/#35 + #25 duplicating #8/#15-16/#21/#23; audit
        # defect F8). The "optional" classification dates from when dedup
        # meant 4416 per-pair encode calls; since the EmbeddingCache batch
        # encode landed the whole pass costs ~1-2s ("46/46 claims… 2 batch
        # encode calls"), i.e. it is effectively free. It is also the ONLY
        # pass that runs AFTER the gap-fill rounds, so skipping it ships
        # every duplicate the gap-fill introduced. Keep the try/except
        # (an embedder OUTAGE must not kill the chapter) but never skip on
        # deadline.
        try:
            _before2 = len(bullets)
            _dedup_started = time.time()
            bullets = self._semantic_dedup_bullets(bullets)
            if len(bullets) != _before2:
                self.log(
                    f"    🧹 V18.20.3.2: Post-gap-fill semantic dedup: "
                    f"{_before2} → {len(bullets)} bullets (removed "
                    f"{_before2 - len(bullets)} gap-fill/conclusion duplicates; "
                    f"{time.time() - _dedup_started:.1f}s, non-skippable per "
                    f"V18.20.3.4)",
                    "INFO",
                )
                parsed["bullet_points"] = bullets
        except Exception as _e:
            self.log(
                f"    ⚠️ V18.20.3.2: Post-gap-fill semantic dedup crashed (non-fatal): {_e}",
                "WARNING",
            )
            logger.debug("post-gap-fill dedup crashed: %s: %s", type(_e).__name__, _e)

        # V18.2.13: Deterministic post-checks — final sweep for the four
        # classes of garbled-token artifacts that low-bit quantization
        # (IQ2_XXS, 2.1 bits/param) introduces: name corruption ("Dukhaim"
        # vs "AuthorY"), missing spaces ("thesonic"→"the sonic"), prompt
        # leakage ("( provided in the input"), and implausible years.
        # Purely deterministic — zero LLM cost, ~1 ms/chapter. Runs AFTER
        # every bullet-generation stage (B4, B3, gap-fill, judge, lists) so
        # it catches artifacts introduced by ANY stage. See
        # core/summarisation/postchecks.py for the full design.
        try:
            from core.summarisation.postchecks import run_post_checks
            from utils.settings import Settings as _PcSettings

            _pc = run_post_checks(
                bullets=bullets,
                executive_summary=exec_sum,
                thorough_summary=thorough,
                source_text=content,
                key_distinctions=parsed.get("key_distinctions", "") or "",
                theoretical_tensions=parsed.get("theoretical_tensions", "") or "",
                # V0.03 (P0-1): dropped-letter auto-repair is OFF by default
                # (settings: summarisation.dropped_letter_auto_repair). The
                # V0.02 rig run corrupted 12/13 valid paraphrase words.
                auto_repair_garble=bool(
                    _PcSettings().get("summarisation.dropped_letter_auto_repair", False)
                ),
            )
            bullets = _pc.bullets
            exec_sum = _pc.executive_summary
            thorough = _pc.thorough_summary

            # ── V0.06 (rig audit F4-c — GENERAL RULE: the source-scaled
            # bullet budget is a HARD CAP, enforced at ship time) ─────────
            # The V0.05 length policy gated only the dedicated expansion
            # call; every other bullet-INSERTION engine (Tier-2 gap-fill,
            # Tier-3-adjacent scholar gap-fill, quarantine recovery) kept
            # appending freely — the rig shipped 19/18/15/14/12 bullets
            # against source-scaled targets of 5-7/5-7/6-9/6-9/5-8, with
            # the surplus being near-duplicate restatements of the same
            # claims. The cap is bullet_target(source).hi — the SAME single
            # source of truth every prompt uses. Primary-synthesis bullets
            # come first (they are the model's deliberate selection);
            # remediation bullets (appended later by gap-fill engines) are
            # the ones trimmed. Coverage shortfall below the cap is logged
            # honestly rather than padded away.
            if _inc_kp_lp and len(bullets) > _bp_hi_lp:
                self.log(
                    f"    ✂️ V0.06: bullet budget enforced at ship time — "
                    f"{len(bullets)} → {_bp_hi_lp} (target {_bp_lo_lp}-{_bp_hi_lp} "
                    f"for a {_src_words_lp}-word chapter; primary bullets kept, "
                    f"remediation bullets trimmed).",
                    "INFO",
                )
                bullets = list(bullets[:_bp_hi_lp])
                parsed["bullet_points"] = bullets

            # ── V0.06 (rig audit F7-a — GENERAL RULE: Tier-3 excerpts are
            # re-validated against the FINAL summary at ship time) ────────
            # Excerpts are recorded mid-pipeline for keywords the summary
            # "did not cover" — but later stages (scholar gap-fill, Tier-2)
            # can add bullets that cover the very same sentences, and
            # nothing re-checked the excerpt list. The rig shipped framed
            # excerpts duplicating bullets that paraphrased the identical
            # source sentence. An excerpt whose quoted sentence is already
            # covered by the final summary text is dropped; the excerpt
            # section keeps only genuinely-uncovered material.
            _se_pre = list(parsed.get("source_excerpts", []) or [])
            if _se_pre:
                _se_post = self._prune_covered_excerpts(
                    bullets=bullets,
                    exec_sum=exec_sum,
                    thorough=thorough,
                    excerpts=_se_pre,
                )
                if len(_se_post) != len(_se_pre):
                    self.log(
                        f"    🔖 V0.06: pruned {len(_se_pre) - len(_se_post)} "
                        f"source excerpt(s) whose sentence the FINAL summary "
                        f"already covers (kept {len(_se_post)}).",
                        "INFO",
                    )
                    parsed["source_excerpts"] = _se_post
            # V18.19.2.2 (Audit Fix 2): Re-populate thorough when run_post_checks
            # truncated it to empty (CoT narrative detected). The V18.19.2.0 audit
            # (audit/results/audit_V18.19.2.0_2026-08-28.md) found that the thorough
            # was 100% CoT, detect_cot_narrative correctly truncated it to empty
            # (postchecks.py:262), and the log said "caller falls back to exec_sum"
            # — but NOTHING actually repopulated thorough. The exec-from-thorough
            # fallback at line 3068 ran BEFORE run_post_checks, so it couldn't
            # catch this case. Result: the delivered summary had an EMPTY
            # "## Thorough Summary" section. This fix closes that gap: after
            # run_post_checks, if thorough is empty but exec is populated, copy
            # exec into thorough (the last-resort fallback the log message
            # promised). A short thorough (the exec) is strictly better than an
            # empty thorough — the reader gets at least the executive summary
            # content rather than a blank section.
            # V18.20.3.2 (audit N2+N3 / P0-1b): FINAL thorough re-derivation
            # from the FINAL bullet set — replaces the V18.19.2.2 exec-copy
            # fallback (which shipped a verbatim duplicate of the 191-word
            # exec as the "Thorough Summary", adding zero information). Now
            # the thorough is re-derived from exec + the FINAL bullets (all
            # generation stages complete: expansion, gap-fill, consolidation,
            # postcheck drops) — mirroring the V18.15.8.0 exec-derivation
            # pattern (derive the missing section from verified material the
            # model already produced). Fires when:
            #   (a) thorough is empty after postchecks (CoT-nuked or never
            #       produced), OR
            #   (b) the thorough came from the V18.2.44 SYNTHETIC fallback
            #       (exec + the EARLY bullet set only — the final set is
            #       strictly richer).
            # V0.05 (F9a): the re-derivation exists to repair a REQUESTED
            # thorough that was lost (CoT-nuked / synthetic). When the user
            # did not request a thorough summary, an empty one is CORRECT —
            # deriving one would fabricate the unrequested section again.
            _need_final_derive = _inc_thorough_lp and (
                (not thorough or not thorough.strip())
                or getattr(self, "_thorough_is_synthetic", False)
            )
            if _need_final_derive:
                _final_bullets_fd = [
                    b for b in (parsed.get("bullet_points") or bullets or []) if b and b.strip()
                ]
                _parts_fd = []
                if exec_sum and exec_sum.strip():
                    _parts_fd.append(exec_sum.strip())
                if _final_bullets_fd:
                    _parts_fd.append(" ".join(f"\u2022 {b.strip()}." for b in _final_bullets_fd))
                if _parts_fd:
                    _derive_reason = (
                        "primary-call CoT was nuked at parse time"
                        if getattr(self, "_primary_thorough_cot_nuked", False)
                        else "dedicated thorough call fell back to the synthetic "
                        "synthesis (early bullets only)"
                    )
                    _derived_words = len(" ".join(_parts_fd).split())
                    thorough = "\n\n".join(_parts_fd)
                    self.log(
                        f"    📝 V18.20.3.2: Thorough re-derived from exec + FINAL "
                        f"bullet set ({_derived_words} words, "
                        f"{len(_final_bullets_fd)} bullets) — {_derive_reason}. "
                        f"This material is model-verified content, not a "
                        f"duplicated exec.",
                        "INFO",
                    )
            elif _inc_thorough_lp and not thorough and exec_sum and len(exec_sum.strip()) >= 50:
                # V18.19.2.2 legacy fallback — only when the CoT-nuke path
                # above did not apply (no primary CoT detected; e.g. a
                # postchecks CoT-nuke on a dedicated-call thorough).
                self.log(
                    f"    📝 V18.19.2.2: Thorough truncated to empty by CoT "
                    f"detection — falling back to exec summary ({len(exec_sum.split())} "
                    f"words) so the Thorough section is not blank.",
                    "INFO",
                )
                thorough = exec_sum
            # V18.20.3.2 (P0-1c): after any re-derivation, re-run the
            # V18.14 thorough-only coverage judge against the text that will
            # actually SHIP. The V18.20.3.1 run logged "29/34 authors in
            # thorough" — measured against 100% CoT that was nuked 33s later;
            # the shipped exec-copy covered ~19/34. The re-run makes the
            # logged verdict honest.
            try:
                if getattr(self, "_primary_thorough_cot_nuked", False) or getattr(
                    self, "_thorough_is_synthetic", False
                ):
                    from core.preprocessing.deterministic_analyzer import (
                        check_coverage,
                        extract_authors_from_analysis,
                        find_analysis_for_heading,
                    )

                    _seg_path_rr, _analysis_rr = find_analysis_for_heading(
                        self.request.output_dir,
                        heading,
                        log_fn=lambda msg, level="DEBUG": self.log(msg, level),
                    )
                    if _analysis_rr:
                        _det_authors_rr = extract_authors_from_analysis(_analysis_rr)
                        if _det_authors_rr:
                            _cov_rr = check_coverage(
                                _analysis_rr,
                                thorough or exec_sum or "",
                            )
                            self.log(
                                f"    📊 V18.20.3.2: Thorough-judge RE-RUN (post "
                                f"re-derivation): {_cov_rr['covered']}/{_cov_rr['total']} "
                                f"authors in the SHIPPED thorough "
                                f"({_cov_rr['coverage_pct']:.0%})"
                                + (
                                    f" — still missing: {_cov_rr['missing'][:5]}"
                                    if _cov_rr["missing"]
                                    else " ✅"
                                ),
                                "INFO" if not _cov_rr["missing"] else "WARNING",
                            )
            except Exception as _rr_e:
                logger.debug(
                    "thorough-judge re-run failed (non-fatal): %s: %s", type(_rr_e).__name__, _rr_e
                )
                # V18.20.4.11 (P2 / W-a12): the re-run exists to make the
                # logged thorough-coverage verdict HONEST (V18.20.3.2 P0-1c);
                # a crashed re-run silently reverts to the dishonest verdict
                # the fix was built to remove. Keep the debug trace, ADD a
                # visible WARNING (honesty-machinery failures must be LOUD).
                self.log(
                    f"    ⚠️ V18.20.4.11: thorough-judge re-run failed (non-fatal — "
                    f"shipped-thorough coverage unverified for this chapter): "
                    f"{type(_rr_e).__name__}: {_rr_e}",
                    "WARNING",
                )
            # V18.19.2.2 (Audit Fix 2b): Same gap can hit exec — if run_post_checks
            # truncated exec to empty (CoT detected on exec, postchecks.py:208) but
            # thorough survived, fall back exec from thorough. Symmetric with the
            # above. (This case is rarer because the V18.15.8.0 exec-from-thorough
            # path + V18.16.0.1 CoT-check already guards exec before postchecks,
            # but run_post_checks can still truncate exec via detect_cot_narrative
            # if the CoT markers weren't caught by the pre-check. Defense-in-depth.)
            if not exec_sum and thorough and len(thorough.strip()) >= 50:
                self.log(
                    "    📝 V18.19.2.2: Exec truncated to empty by CoT "
                    "detection — falling back to thorough summary.",
                    "INFO",
                )
                exec_sum = thorough
            # V18.19.2.2 (Audit Fix 2c): If BOTH are empty after postchecks (the
            # catastrophic V18.15.7.0 cascade case), log at ERROR. The exec-from-
            # thorough + last-resort fallbacks above should prevent this, but if
            # both the primary AND dedicated calls produced CoT, we have nothing.
            # Surface it loudly rather than silently shipping empty sections.
            if not exec_sum and not thorough:
                self.log(
                    "    🚨 V18.19.2.2: BOTH exec and thorough are empty after "
                    "postchecks — the chapter will ship with blank summary sections. "
                    "This indicates the model produced CoT on every call (primary + "
                    "dedicated thorough + exec-from-thorough). Investigate the "
                    "model temperature / prompt / context window.",
                    "ERROR",
                )
            # V18.15.3.4: Use the cleaned additive sections too
            parsed["key_distinctions"] = _pc.key_distinctions
            parsed["theoretical_tensions"] = _pc.theoretical_tensions
            parsed["bullet_points"] = bullets
            parsed["executive_summary"] = exec_sum
            parsed["thorough_summary"] = thorough
            if _pc.total_findings:
                self.log(
                    f"    🛡️ V18.2.13 Post-checks: {_pc.fixed_count} fixed, "
                    f"{_pc.flagged_count} flagged "
                    f"(of {len(bullets)} bullets + exec + thorough)",
                    "INFO",
                )
                # Log each finding at DEBUG for the conversion log.
                for _iss in _pc.issues:
                    self.log(
                        f"      [{_iss.detector}/{_iss.severity}] {_iss.field}: "
                        f"{_iss.detail}  |  {_iss.snippet}",
                        "DEBUG",
                    )
            else:
                self.log("    ✅ V18.2.13 Post-checks: clean (no artifacts found)", "DEBUG")
        except Exception as _e:
            self.log(f"    ⚠️ V18.2.13 Post-checks crashed (non-fatal): {_e}", "WARNING")
            logger.debug("post-checks crashed: %s: %s", type(_e).__name__, _e)

        # V18.20.3.4 (RC-6, audit v182033): deterministic MUST-HAVE recall
        # floor, measured on the FINAL bullet set (post-quarantine,
        # post-dedup, post-postcheck drops). The V18.20.3.3 run's auto-judge
        # reported coverage=100% (46/46 claims) while the content audit
        # measured ~90% — claim-recall is not content-recall (the app itself
        # logged the caveat). This probe is the honest, hallucination-proof
        # complement: regex-measured (a) theorist recall from the
        # deterministic analysis (the V18.14 bullets-only judge pattern,
        # re-run on the final set) and (b) enumerated-conclusion item recall
        # (the V18.15.9.0 pattern). Zero LLM cost. Informational: prose-level
        # omissions (e.g. the AuthorJ ego-ideal gap in that audit) are invisible
        # to a deterministic probe — but the numbers it DOES print are real.
        #
        # V18.20.3.5 (audit v182034): the inline version of this probe NEVER
        # RAN on the rig — it iterated the conclusion tuples and called
        # .lower() on the TUPLE, raising AttributeError, which the except
        # clause swallowed via logger.debug (invisible in the conversion
        # log — the audit's "RC-6 not observable" finding). The logic now
        # lives in core/summarisation/recall_floor.py (unit-tested, stable
        # contract), failures log VISIBLY at WARNING, and the numbers are
        # stashed on the SummaryResult so the quality report and the
        # end-of-conversion diagnostic can print them instead of "?".
        # V18.20.3.8 (Phase 1 / W2): the 80-bullet cap now runs BEFORE the
        # recall-floor probe. Previously the probe measured the PRE-cap set
        # while the cap then deleted the list TAIL — exactly where gap-fill
        # and quarantine-recovery bullets are appended — so the logged
        # "honest number" could overstate the shipped set whenever the
        # count exceeded 80. The cap is also coverage-aware now: a tail
        # bullet that is the ONLY cover of an analysis author is rescued
        # into the capped set, displacing a redundant head bullet
        # ("more bullets is better than lower coverage" — the standing
        # rule, applied to the cap).
        _analysis_rf = ""
        try:
            from core.preprocessing.deterministic_analyzer import (
                find_analysis_for_heading,
            )

            _seg_path_rf, _analysis_rf = find_analysis_for_heading(
                self.request.output_dir,
                heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
        except Exception as _rf_e:
            # V18.20.3.5: a silent logger.debug here is how the .3.4 run
            # lost the probe entirely. Deterministic probes must fail
            # VISIBLY.
            self.log(
                f"    ⚠️ V18.20.3.5: Recall-floor analysis lookup failed: "
                f"{type(_rf_e).__name__}: {_rf_e}",
                "WARNING",
            )
            logger.debug("recall-floor analysis lookup failed: %s: %s", type(_rf_e).__name__, _rf_e)

        # V18.15.7.0 (Fix 3): Hard-cap bullets at 80 (gold standard ≈ 46;
        # V18.15.6.0 shipped 212). Applied AFTER consolidation + gap-fill +
        # postchecks so consolidation can merge duplicates first, then the
        # cap catches overflow. The pre-V18.15.7.0 cap was 99999 (effectively
        # unlimited since V13.45.5) — this was a misinterpretation of the
        # "more bullets > lower coverage" rule (which was meant to prevent
        # MINIMUM caps, not MAXIMUM caps). A cap of 80 = 1.7× the gold
        # standard, allowing generous coverage while preventing the 212-bullet
        # explosion. The "more bullets > lower coverage" principle is preserved
        # — we never drop below the gold standard's 46; we only cap overflow.
        # V18.20.3.8: the cap delegates to coverage_aware_cap (same limit,
        # same head-cap behaviour when no analysis exists — plus the
        # sole-cover rescue).
        if bullets and len(bullets) > 80:
            try:
                from core.summarisation.recall_floor import coverage_aware_cap

                bullets = coverage_aware_cap(
                    bullets,
                    _analysis_rf or "",
                    limit=80,
                    log_fn=lambda msg, level="WARNING": self.log(msg, level),
                )
                parsed["bullet_points"] = bullets
            except Exception as _cap_e:
                # Never break the chapter over the cap: degrade to the
                # plain V18.15.7.0 head-cap, visibly.
                self.log(
                    f"    ⚠️ V18.20.3.8: coverage-aware cap failed "
                    f"({type(_cap_e).__name__}: {_cap_e}) — plain head-cap "
                    f"applied",
                    "WARNING",
                )
                logger.warning(
                    "coverage-aware cap failed — plain head-cap: %s: %s",
                    type(_cap_e).__name__,
                    _cap_e,
                )
                bullets = bullets[:80]
                parsed["bullet_points"] = bullets

        # V18.20.3.13 (Phase 5 / W7+O3, .3.7 SWOT W7): thorough-theorist
        # FLOOR + one targeted gap-fill. Placement rationale: this is the
        # first point where the thorough is FINAL — every mutation is done
        # (dedicated expansion, postcheck repairs, the V18.20.3.2 re-derivation
        # from the final bullet set, the exec-copy fallbacks, Lists injection
        # which runs pre-postchecks) and the bullets are final too (cap
        # applied above) — so the floor measures the text that actually
        # ships. It runs BEFORE the recall-floor probe below so that probe's
        # conclusion-item measurement (bullets + thorough) sees the
        # post-gap-fill thorough. The theorist list comes from the SAME
        # runtime analysis lookup (``_analysis_rf``) the recall floor uses —
        # no second tree-walk, no hardcoded names (.3.9 rule). Fail-soft:
        # the method logs a WARNING and returns the thorough unchanged on
        # any internal crash.
        # V0.05 (F9a/F9b): skipped entirely when the user did not request a
        # thorough summary (nothing to measure/extend), and the gap-fill
        # append is budget-gated inside the mixin by the scaled target —
        # the 150-300-word append must never push a short chapter's thorough
        # past its source-scaled ceiling.
        if _inc_thorough_lp:
            thorough = self._thorough_theorist_floor(
                heading,
                content,
                thorough,
                _analysis_rf or "",
                scaled_target_hi=_th_hi_lp,
            )
        parsed["thorough_summary"] = thorough

        try:
            from core.summarisation.recall_floor import deterministic_recall_floor

            _rf = deterministic_recall_floor(
                _analysis_rf or "",
                bullets,
                thorough,
                content,
            )
            if _rf.get("log_parts"):
                self.log(
                    f"    📏 V18.20.3.4: Deterministic recall floor (final set): "
                    f"{'; '.join(_rf['log_parts'])}. This regex-measured floor is "
                    f"the honest coverage number — the LLM judge's claim-recall "
                    f"measures a different thing and overstates content recall "
                    f"for long sources.",
                    "INFO",
                )
            # V18.20.3.5: stash for the quality report / diagnostic summary.
            parsed["recall_floor"] = _rf
        except Exception as _rf_e:
            # V18.20.3.5: a silent logger.debug here is how the .3.4 run
            # lost the probe entirely. Deterministic probes must fail
            # VISIBLY.
            self.log(
                f"    ⚠️ V18.20.3.5: Deterministic recall-floor probe failed: "
                f"{type(_rf_e).__name__}: {_rf_e}",
                "WARNING",
            )
            logger.debug("recall-floor probe failed: %s: %s", type(_rf_e).__name__, _rf_e)
        return bullets, exec_sum, thorough

    def _phase_finalize(
        self,
        heading,
        parsed,
        exec_sum,
        bullets,
        thorough,
        final_summary,
        tok_in,
        _inc_exec_lp,
        _inc_thorough_lp,
        _inc_kp_lp,
    ):
        # ── V0.03 (P1-6): quarantine record for THIS chapter ───────────────
        # V0.06 (rig audit F2 — GENERAL RULE: pipeline bookkeeping never
        # ships in the deliverable): the per-drop record stays in the LOGS
        # (logs/drops.jsonl — the QuarantineLog has written every entry there
        # since V13.x) and the conversion log gets one honest count line.
        # The V0.05 rig rendered a "## Quarantine Log (quality-pipeline
        # drops)" section into every chapter's .md and DOCX — internal
        # quality-process metadata the user explicitly does not want in the
        # output ("keep it for your logs"). The appendix field is no longer
        # populated; the render sites were removed in the same release.
        try:
            _qa_entries = [
                e
                for e in (getattr(self.quarantine, "entries", None) or [])
                if getattr(e, "chapter", "") == heading and not getattr(e, "recovered", False)
            ]
            if _qa_entries:
                self.log(
                    f"    📋 Quarantine: {len(_qa_entries)} bullet drop(s) "
                    f"recorded for this chapter → logs/drops.jsonl "
                    f"(NOT rendered in the delivered files).",
                    "INFO",
                )
        except Exception as _qa_e:
            logger.debug("quarantine count log failed: %s: %s", type(_qa_e).__name__, _qa_e)

        model_label = parsed.get("model", self.primary_model)
        return SummaryResult(
            chapter_heading=heading,
            executive_summary=exec_sum,
            bullet_points=bullets,
            # V0.06 (F1-b): the output-selection contract enforced at the
            # SOURCE — an unrequested section never enters the result, so
            # every renderer (markdown, DOCX, book summary) and every
            # consumer sees the contract state even before the render-side
            # flag gates (F1-c) run.
            thorough_summary=(thorough if _inc_thorough_lp else ""),
            success=True,
            model_used=model_label,
            input_tokens=tok_in,
            output_tokens=count_tokens(final_summary),
            # V13.40.1: Pass the additive sections through to SummaryResult
            # so they reach the DOCX + markdown output renderers.
            key_distinctions=parsed.get("key_distinctions", "") or "",
            theoretical_tensions=parsed.get("theoretical_tensions", "") or "",
            # V13.41.0: Scholar reflections — meta-cognitive gap analysis
            scholar_reflections=parsed.get("scholar_reflections", "") or "",
            # V0.03 (P0-2): Tier-3 framed source excerpts (separate section,
            # never Key Takeaways).
            source_excerpts=list(parsed.get("source_excerpts", []) or []),
            # V0.06 (F2): quarantine_appendix intentionally NOT set — the
            # drop record lives in logs/drops.jsonl only.
            # V18.20.3.5: deterministic recall-floor numbers for the
            # quality report + diagnostic summary (replaces the "?").
            recall_floor=parsed.get("recall_floor"),
            # V18.20.3.7: output provenance — which conversion produced
            # this summary (rendered into the summary files + sentinel).
            run_id=getattr(self, "_run_id", ""),
            app_version=getattr(self, "_app_version", ""),
            run_started=getattr(self, "_run_started", ""),
            # V0.06 (F1-c): stamp the output-selection flags onto the
            # result — renderers skip a section whose flag is False even if
            # content leaked into it (defense in depth behind the F1-b
            # parse gate).
            include_executive_summary=_inc_exec_lp,
            include_thorough_summary=_inc_thorough_lp,
            include_keypoints=_inc_kp_lp,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # V10.28.0 (Sprint 1.4): Quarantine recovery pass

    def _phase_setup_and_gate(self, heading, content, book_context):
        """V0.18 (Phase 5.1): moved VERBATIM from _summarize_inner."""
        self._source_text = content
        # V10.28.0 (Sprint 1): track the current chapter heading so every
        # quarantine entry records which chapter the dropped bullet came from.
        self._current_heading = heading
        # V18.20.3.2 (P0-1): per-chapter CoT/synthetic flags — RESET every
        # chapter so a CoT nuke in chapter N never leaks into chapter N+1's
        # re-derivation decisions.
        self._primary_thorough_cot_nuked = False
        self._primary_exec_cot_nuked = False
        self._thorough_is_synthetic = False
        src_tokens = count_tokens(content)
        text = content
        tok_in = 0

        # V17.2/V17.5: Prepend deterministic analysis to the text gemma sees.
        # V17.5 fix: uses find_analysis_for_heading() instead of fragile
        # heading-to-filename matching. Searches the ENTIRE output tree.
        try:
            from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

            _seg_path, _analysis = find_analysis_for_heading(
                self.request.output_dir,
                heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
            if _analysis:
                # V18.1 (audit Q2): Inject cross-chapter running context BEFORE
                # the deterministic analysis and chapter text. This gives the LLM
                # awareness of what previous chapters already covered, preventing
                # repetition and improving cross-chapter synthesis.
                _book_ctx_block = ""
                if book_context:
                    _book_ctx_block = (
                        f"## PREVIOUS CHAPTERS SYNTHESIS (for continuity — "
                        f"do NOT repeat this content, focus on THIS chapter's NEW content):\n"
                        f"{book_context}\n\n---\n\n"
                    )
                text = _book_ctx_block + _analysis + "\n\n---\n\n## CHAPTER TEXT\n\n" + text
                self.log(
                    f"    📊 V17.2: Prepended deterministic analysis ({len(_analysis)} chars) — citation recall 78%→100%",
                    "INFO",
                )
                if book_context:
                    self.log(
                        f"    📚 V18.1: Cross-chapter context injected ({len(book_context)} chars from previous chapters)",
                        "INFO",
                    )
            else:
                self.log(
                    "    ⚠️ V17.5: No deterministic analysis found — running without prepend (old behavior)",
                    "DEBUG",
                )
        except Exception as _e:
            self.log(f"    ⚠️ V17.5: Deterministic analysis load failed: {_e}", "WARNING")

        # Empty/near-empty input gate — if the segment
        # has almost no content (< 80 tokens), DO NOT call the LLM.  Sending
        # an empty prompt causes the model to fabricate an entire essay from
        # its training data (the karsan2022 Memantine hallucination).  Mark
        # as failed instead.
        if src_tokens < 80:
            msg = f"Segment too small ({src_tokens} tokens) — skipping to prevent hallucination"
            self.log(f"    🚫 {msg}", "WARNING")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=False,
                error_msg=msg,
                input_tokens=src_tokens,
                output_tokens=0,
            )
        return src_tokens, text, tok_in

    def _phase_single_pass_primary(
        self,
        heading,
        content,
        concepts,
        callouts,
        _p6_b4_threshold,
        _p6_decide_strategy,
        _p6_output,
        _p6_window,
    ):
        """V0.18 (Phase 5.1): moved VERBATIM from _summarize_inner (dedented one level from the single-pass else leg)."""
        # ── Prepare text (truncate if needed) ──────────────────────────
        text = self._prepare_text(content)
        tok_in = count_tokens(text)

        # ── Primary model pass (V3.2.0 B1: pass concepts + callouts) ───
        # For long chapters (>8000 tokens), try section map-reduce
        # first — it guarantees every section gets LLM attention.
        model = self.primary_model
        self.log(f"    ⚡ Using primary model: {model}", "INFO")
        if concepts:
            self.log(
                f"    🎯 Injecting {len(concepts)} concepts + {len(callouts or [])} callouts into prompt",
                "DEBUG",
            )

        result = None
        # B4: Section map-reduce for long chapters
        # V18.2 (audit): Threshold is now configurable via
        # settings.summarisation.b4_threshold_tokens (default 12000).
        # Was hardcoded 8000, which triggered B4 for a 9127-token chapter
        # = 3 LLM calls + must-have pre-flight + consolidation = 6 calls.
        # On a 27B/12GB card (spilling to CPU), each call takes 10+ min,
        # so 6 calls = 1 hour. Raising to 12000 lets most chapters
        # (under ~50 pages) do single-pass = 1 call = ~10 min.
        # The original V13.40.3 comment said B4 gave 85% coverage vs 62%
        # single-pass at 9k tokens — but that was with Gemma 12B.
        # For 27B models with larger context windows, single-pass at 9k
        # tokens should be fine. Users can lower to 8000 if coverage drops.
        # V0.10 (P6): the B4 gate ALSO routes through decide_strategy —
        # computed on tok_in (the POST-_prepare_text token count,
        # exactly what the legacy gate compared). At legacy windows its
        # b4_sections decision is EXACTLY `tok_in > _b4_threshold`
        # (byte-parity, both legs agree); at windows > 32768 B4 is
        # DISABLED — a chapter that fits the window in one call has no
        # truncation for B4 to recover from. The settings read moved to
        # the P6 decision block above (same value, read once).
        _b4_threshold = _p6_b4_threshold
        _b4_decision = _p6_decide_strategy(
            tok_in,
            _p6_window,
            _p6_output,
            b4_threshold=_b4_threshold,
            map_reduce_threshold=self.MAP_REDUCE_THRESHOLD,
        )
        if tok_in > _b4_threshold and _b4_decision.strategy == "b4_sections":
            self.log(
                f"    📑 Chapter is long ({tok_in:,} tokens > {_b4_threshold:,} threshold) — trying section map-reduce (B4)…",
                "INFO",
            )
            result = self._section_map_reduce(heading, text, concepts, callouts)
            if result:
                self.log("    ✅ Section map-reduce succeeded", "INFO")
                # V13.40.0: Recover VRAM after B4 map-reduce. The 3+ sequential
                # LLM calls (each ~4 min) leave the GPU stressed. Without
                # recovery, subsequent self-review + gap-fill return empty.
                self._recover_vram(context="post-B4-map-reduce", delay_sec=10.0)
            else:
                self.log("    ℹ️ Section map-reduce not applicable — using single-pass", "DEBUG")

        # Standard single-pass if B4 didn't apply or failed
        if not result:
            result = self._summarize_with_model(
                heading,
                text,
                model,
                self.temperature,
                with_cot=True,
                concepts=concepts,
                callouts=callouts,
            )

        if not result:
            msg = f"Primary model {model} returned no response"
            self.log(f"    ❌ {msg}", "ERROR")
            # V18.15.6.0 (Fix B): distinguish "model not installed" (404)
            # from "model timed out during generation" (HTTP timeout). The
            # pre-V18.15.6.0 code always said "not installed" even when the
            # model WAS loaded (S19 pre-warm succeeded 20 min earlier) and
            # the real cause was a per-call HTTP timeout mid-generation.
            # The _last_llm_error_type is set by _call_ollama based on the
            # error_tracker out-param propagated from llm_dispatcher.
            _err_type = getattr(self, "_last_llm_error_type", None)
            if _err_type == "timeout":
                hint = (
                    f"Likely cause: model '{model}' timed out after {self.timeout}s "
                    f"during generation (the model WAS loaded — S19 pre-warm succeeded; "
                    f"the per-call HTTP timeout fired mid-generation). "
                    f"Fix: raise `local.http_timeout_sec` in Settings (current: {self.timeout}s), "
                    f"or reduce input size, or switch to a faster quant."
                )
            elif _err_type == "oom":
                hint = (
                    f"Likely cause: model '{model}' ran out of VRAM (OOM). "
                    f"Fix: reduce `summarisation_max_context_tokens` in Settings, "
                    f"or switch to a smaller model."
                )
            elif _err_type == "not_found":
                hint = (
                    f"Likely cause: model '{model}' is not installed in Ollama. "
                    f"Fix: `ollama pull {model}`, or change the model in Settings → Summarisation."
                )
            else:
                # "empty" or unknown — keep the legacy hint (covers the
                # short-response-after-retry case where no exception fired).
                hint = (
                    f"Likely cause: model '{model}' returned an empty/short response after retry. "
                    f"If persistent: check Ollama is running (`ollama list` shows '{model}'), "
                    f"or raise `local.http_timeout_sec` in Settings, or switch to a faster quant."
                )
            self.log(f"    💡 {hint}", "ERROR")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=False,
                error_msg=f"{msg}. {hint}",
                input_tokens=tok_in,
                output_tokens=0,
            )

        # ── Verbose: log what the model returned ───────────────────────
        _bps_count = len([b for b in result.get("bullet_points", []) if b])
        _exec_len = len(result.get("executive_summary", ""))
        _thorough_len = len(result.get("thorough_summary", ""))
        self.log(
            f"    📝 Parsed: exec={_exec_len} chars, bullets={_bps_count}, thorough={_thorough_len} chars",
            "DEBUG",
        )

        # V0.06 (rig audit F1-b — GENERAL RULE: the output selection is
        # the contract, enforced at PARSE time): when the user did not
        # request a thorough summary, ANY thorough content the model
        # produced anyway (the parser's leftover fallback can capture
        # unrequested additive-section output; a low-bit model may emit
        # the tag regardless) is discarded HERE, so every downstream
        # stage (coverage, judges, expansion gates, render) sees the
        # contract state: no thorough. The V0.05 rig shipped "Thorough
        # Summary" sections to a user who unchecked the output because
        # this gate did not exist.
        if not bool(getattr(self.request, "include_thorough_summary", True)):
            if (result.get("thorough_summary", "") or "").strip():
                self.log(
                    f"    V0.06: thorough_summary not requested — discarding "
                    f"{_thorough_len} chars of unrequested thorough content "
                    f"(output-selection contract).",
                    "DEBUG",
                )
            result["thorough_summary"] = ""
        if not bool(getattr(self.request, "include_keypoints", True)):
            if result.get("bullet_points", []):
                self.log(
                    f"    V0.06: keypoints not requested — discarding "
                    f"{_bps_count} unrequested bullet(s) "
                    f"(output-selection contract).",
                    "DEBUG",
                )
            result["bullet_points"] = []
        if not bool(getattr(self.request, "include_executive_summary", True)):
            if (result.get("executive_summary", "") or "").strip():
                self.log(
                    f"    V0.06: executive_summary not requested — discarding "
                    f"{_exec_len} chars of unrequested exec content "
                    f"(output-selection contract).",
                    "DEBUG",
                )
            result["executive_summary"] = ""

        # ── V18.20.3.2 (audit N2+N3 / P0-1a): PARSE-TIME CoT gate ──────
        # The V18.20.3.1 real-rig run's primary call returned exec=0 and
        # a 34,794-char thorough that was 100% chain-of-thought. Nothing
        # detected it until run_post_checks fired the V18.19.2.2 CoT-nuke
        # 26 MINUTES later — by then every thorough-section gate (the
        # V18.14 thorough-only judge, gap-fill decisions) had already
        # validated the CoT text, and the shipped "Thorough Summary" was
        # a verbatim copy of the 191-word exec. Nuking HERE means every
        # downstream stage sees the REAL state: the dedicated-thorough
        # path regenerates a real thorough, coverage is computed on real
        # text (CoT inflates it — the model's reasoning mentions
        # everything), and the V18.14 judges measure what ships.
        try:
            from core.summarisation.postchecks import detect_cot_narrative

            _p_tho = result.get("thorough_summary", "") or ""
            if _p_tho:
                _p_tho_clean, _p_tho_cot = detect_cot_narrative(_p_tho, "thorough")
                if _p_tho_cot:
                    self.log(
                        f"    🚨 V18.20.3.2: primary-call thorough is CoT "
                        f"narrative ({len(_p_tho)} chars, {_p_tho_cot[0].detail[:60]}…) "
                        f"— DISCARDED AT PARSE TIME. The dedicated-thorough "
                        f"call will regenerate a real one; all downstream "
                        f"gates will judge the REAL text.",
                        "WARNING",
                    )
                    result["thorough_summary"] = ""
                    self._primary_thorough_cot_nuked = True
            _p_exec = result.get("executive_summary", "") or ""
            if _p_exec:
                _p_exec_clean, _p_exec_cot = detect_cot_narrative(_p_exec, "exec")
                if _p_exec_cot:
                    self.log(
                        f"    🚨 V18.20.3.2: primary-call exec is CoT "
                        f"narrative ({len(_p_exec)} chars) — DISCARDED AT "
                        f"PARSE TIME (exec-from-thorough will re-derive).",
                        "WARNING",
                    )
                    result["executive_summary"] = ""
                    self._primary_exec_cot_nuked = True
        except Exception as _cot_e:
            logger.debug(
                "parse-time CoT gate crashed (non-fatal): %s: %s", type(_cot_e).__name__, _cot_e
            )
            # V18.20.4.11 (P2 / W-a12): the CoT gate is anti-hallucination
            # machinery — a crashed gate silently re-admits CoT narrative
            # as "summary" text. The DEBUG-only trace made that invisible
            # in every real-rig log. Keep the debug trace, ADD a visible
            # WARNING (honesty-machinery failures must be LOUD).
            self.log(
                f"    ⚠️ V18.20.4.11: parse-time CoT gate crashed (non-fatal — "
                f"gate skipped for this chapter): "
                f"{type(_cot_e).__name__}: {_cot_e}",
                "WARNING",
            )

        # ── Compute coverage ────────────────────────────────────────────
        _bps = [
            str(b) if not isinstance(b, str) else b for b in result.get("bullet_points", []) if b
        ]
        combined_summary = f"{result.get('executive_summary', '')} {' '.join(_bps)} {result.get('thorough_summary', '')}"
        coverage = self._compute_coverage(content, combined_summary)
        self._last_coverage = coverage  # V13.40.4: for self-review skip decision
        self.log(
            f"    📊 Primary coverage: {coverage:.0%} | keywords: {self._extract_keywords(content, n=8)}",
            "INFO",
        )

        # DEBUG — log which keywords are found vs missing for
        # diagnosing low-coverage chapters (e.g. Chapter 3 at 61%).
        _all_kw = self._extract_keywords(content, n=18)
        _sl = combined_summary.lower()
        _found = [k for k in _all_kw if k in _sl]
        _missing = [k for k in _all_kw if k not in _sl]
        self.log(
            f"    🔍 Coverage detail: {len(_found)}/{len(_all_kw)} keywords found | "
            f"missing: {_missing[:8]}{'…' if len(_missing) > 8 else ''}",
            "DEBUG",
        )

        # ── Heavy model fallback ──────────────────────────────────────────
        # Multi-sampling + voting fallback for low coverage
        _used_b3_voting = False
        # V15.1.1: B3 disabled by default — damages conceptual depth.
        # The consensus voting produces bland exec summaries (402 chars
        # vs V13.45.5's 974 chars) and loses specific theorist details.
        # When disabled, coverage falls through to 3-Tier + gap-fill +
        # over-delivery, which is deterministic and targeted.
        if (
            round(coverage, 2) < self.coverage_threshold
            and not self.heavy_model
            and self.b3_voting_enabled
        ):  # V15.1.1: gated
            self.log(
                f"    🔄 Coverage {coverage:.0%} < {self.coverage_threshold:.0%} – trying multi-sample voting (B3)…",
                "INFO",
            )
            voted = self._multi_sample_summarize(heading, text, concepts, callouts, n_samples=3)
            if voted:
                _vbps = [
                    str(b) if not isinstance(b, str) else b
                    for b in voted.get("bullet_points", [])
                    if b
                ]
                voted_combined = f"{voted.get('executive_summary', '')} {' '.join(_vbps)} {voted.get('thorough_summary', '')}"
                voted_coverage = self._compute_coverage(content, voted_combined)
                self.log(f"    📊 Voted coverage: {voted_coverage:.0%}", "INFO")
                if voted_coverage > coverage:
                    result = voted
                    coverage = voted_coverage
                    _used_b3_voting = True
                    self._last_coverage = coverage  # V13.40.5: update for self-review skip
                    self.log(
                        f"    ✅ Multi-sample voting improved coverage to {coverage:.0%}",
                        "INFO",
                    )
        elif round(coverage, 2) < self.coverage_threshold and not self.b3_voting_enabled:
            self.log(
                f"    ℹ️ Coverage {coverage:.0%} < {self.coverage_threshold:.0%} — B3 voting disabled, "
                f"will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward {self._effective_target:.0%}",
                "INFO",
            )

        if coverage < self.coverage_threshold and self.heavy_model:
            self.log(
                f"    🔥 Coverage {coverage:.0%} < {self.coverage_threshold:.0%} – using heavy model: {self.heavy_model}",
                "INFO",
            )
            heavy_result = self._summarize_with_model(
                heading, text, self.heavy_model, self.temperature * 0.5, with_cot=True
            )
            if heavy_result:
                _hbps = [
                    str(b) if not isinstance(b, str) else b
                    for b in heavy_result.get("bullet_points", [])
                    if b
                ]
                heavy_combined = f"{heavy_result.get('executive_summary', '')} {' '.join(_hbps)} {heavy_result.get('thorough_summary', '')}"
                heavy_coverage = self._compute_coverage(content, heavy_combined)
                self.log(f"    📊 Heavy coverage: {heavy_coverage:.0%}", "INFO")
                if heavy_coverage > coverage:
                    merged_bullets = list(heavy_result.get("bullet_points", []))
                    for bp in result.get("bullet_points", []):
                        if bp not in merged_bullets:
                            merged_bullets.append(bp)
                    result["executive_summary"] = heavy_result.get(
                        "executive_summary", result.get("executive_summary", "")
                    )
                    result["thorough_summary"] = heavy_result.get(
                        "thorough_summary", result.get("thorough_summary", "")
                    )
                    result["bullet_points"] = merged_bullets[: self.max_bullets_per_chapter]
                    result["model"] = "primary+heavy"
                    self.log("    ✅ Merged primary + heavy summaries", "INFO")
                else:
                    for bp in heavy_result.get("bullet_points", []):
                        if bp not in result.get("bullet_points", []):
                            result["bullet_points"].append(bp)
                    result["bullet_points"] = result["bullet_points"][
                        : self.max_bullets_per_chapter
                    ]
                    result["model"] = "primary+heavy_bullets"
                    self.log("    ✅ Added unique heavy bullets to primary summary", "INFO")
            else:
                self.log("    ⚠️ Heavy model returned no response, keeping primary", "WARNING")

        # ── V13.32.8: 3-Tier Coverage Guarantee System ──────────────────
        # V15.1.0: Use _effective_target (over-delivery target when enabled,
        # falls back to coverage_threshold). This is the "don't settle" logic:
        # if user set 85% but over-delivery target is 92%, we keep gap-filling
        # until 92% (or no more concepts to fill).
        if coverage < self._effective_target:
            _od_note = ""
            if self.overdeliver_enabled and self.overdeliver_target > self.coverage_threshold:
                _od_note = f" (over-deliver: floor {self.coverage_threshold:.0%} → target {self.overdeliver_target:.0%})"
            self.log(
                f"    📈 Coverage {coverage:.0%} < effective target {self._effective_target:.0%}"
                f"{_od_note} — applying 3-Tier Guarantee",
                "INFO",
            )
            coverage = self._apply_3tier_coverage(
                heading,
                text,
                content,
                result,
                coverage,
            )

        # ── Old academic-rigor gap-fill: removed in V0.08 (P2) — it was an
        # `if False` dead block since V18.6, superseded by the 3-Tier
        # coverage guarantee above. ──

        # ── Post-filter: remove thinking-process bullets + quality scoring ─
        # Pass concepts + source_text for quality scoring
        # Skip aggressive C1/C4 filtering if B3 voting was used —
        # voted bullets are already consensus-validated across 3 samples.
        if _used_b3_voting:
            # Light filtering only: strip thinking + narrative, no quality scoring
            result["bullet_points"] = self._filter_thinking_bullets(
                result.get("bullet_points", []),
                concepts=None,  # None = skip C1 quality scoring
                source_text="",  # empty = skip C4 numeric verification
            )
            self.log(
                f"    ℹ️ B3 voted bullets — skipping aggressive C1/C4 filtering (kept {len(result.get('bullet_points', []))})",
                "DEBUG",
            )
        else:
            result["bullet_points"] = self._filter_thinking_bullets(
                result.get("bullet_points", []),
                concepts=concepts,
                source_text=content,
            )
        result["executive_summary"] = self._strip_thinking(result.get("executive_summary", ""))
        result["thorough_summary"] = self._strip_thinking(result.get("thorough_summary", ""))

        # V18.19.2.4 (Crash Fix) / V18.20.1.2 (refactored to _save_checkpoint):
        # Emergency checkpoint save of the primary-call output BEFORE the
        # additive-sections / judge / postchecks phases. See _save_checkpoint
        # docstring for the full rationale. See audit/results/audit_V18.19.2.3_crash.md.
        self._save_checkpoint(heading, result, label="primary")

        # ── A3: Fact-Checking Pipeline (deterministic) ────────────────
        # For each bullet, fuzzy-match against the source text. If no
        # match > 60% similarity, mark as "⚠️ Unverified".
        result["bullet_points"] = self._verify_bullets(result.get("bullet_points", []), content)

        # V13.39.0: Anti-hallucination verification for additive sections.
        # V13.40.0: First, ensure the sections are populated — in academic-rigor
        # JSON mode, the model often omits key_distinctions/theoretical_tensions.
        # This followup call populates them if empty, then verification checks them.
        self._ensure_additive_sections(heading, content, result)
        self._verify_additive_sections(heading, content, result)

        # V18.20.1.2 (crash mitigation): SECOND checkpoint AFTER additive
        # sections + bullet verification. The V18.19.2.4 crash (process killed
        # during additive-sections) + the V18.20.1.1 crash (process killed
        # during thorough-expansion, which runs AFTER additive-sections)
        # showed that the primary-call checkpoint alone isn't enough — the
        # additive-sections call is expensive and can crash, losing its output.
        # This checkpoint captures the state AFTER additive sections are
        # populated, so if the thorough-expansion call (the next expensive
        # phase) crashes, the user still gets exec + bullets + key_distinctions
        # + theoretical_tensions. The thorough may be empty (if the primary
        # didn't produce it), but that's strictly better than losing everything.
        self._save_checkpoint(heading, result, label="post-additive-sections")

        # V13.6.0: Create BulletPipeline + PipelineState EARLY — needed
        # by self-consistency/review (line 2654) and academic factual
        # verification (line 2730), which both run BEFORE the F4/Phase2.2
        # pipeline stages. Previously _pipeline was created at line ~2772,
        # causing UnboundLocalError when academic_rigor triggered the
        # self-review path.
        from core.summarisation.bullet_pipeline import BulletPipeline, PipelineState

        _pipeline = BulletPipeline(self)
        _pstate = PipelineState(
            heading=heading,
            content=content,
            bullets=result.get("bullet_points", []),
            exec_sum=result.get("executive_summary", ""),
            thorough=result.get("thorough_summary", ""),
        )

        # V10.36.0: Self-consistency + self-review extracted to BulletPipeline.
        _pipeline.run_self_consistency_and_review(_pstate, result, heading, text)
        result = _pstate.__dict__.get("_result", result)  # get updated result if modified
        parsed = result
        return _pipeline, _pstate, coverage, parsed, text, tok_in

    def _phase_thorough_and_coverage(self, heading, content, text, parsed):
        """V0.18 (Phase 5.1): moved VERBATIM from _summarize_inner."""
        # ── Ensure thorough is long enough ──────────────────────────────────
        exec_sum = parsed.get("executive_summary", "")
        bullets = parsed.get("bullet_points", [])
        thorough = parsed.get("thorough_summary", "")
        # V18.2.34: Replaced the old "len(thorough) < len(exec_sum) * 2" check
        # (a fragile character-length heuristic) with a strict 800-word floor.
        # V0.05 (rig audit F9b — GENERAL RULE REPLACEMENT): the floor is no
        # longer the absolute 800 — it SCALES to the source (length_policy:
        # thorough_target). The V0.04 rig proved the absolute floor's failure
        # mode end-to-end: 321-441-word chapters were force-EXPANDED to >=800
        # words (the delivered thorough sections measured 1.55-2.76x their
        # sources, padded with invented context — hallucination-by-
        # instruction). A short chapter's thorough summary is ALLOWED to be
        # short: ~90-150 words for a 340-word chapter is the correct
        # deliverable. The dedicated expansion call now only fires when the
        # thorough is short RELATIVE TO ITS SCALED TARGET — and never when
        # the user did not request a thorough summary at all (F9a).
        from core.summarisation.length_policy import (
            bullet_target as _bp_target_lp,
        )
        from core.summarisation.length_policy import (
            count_source_words as _csw_lp,
        )
        from core.summarisation.length_policy import (
            thorough_target as _th_target_lp,
        )

        _src_words_lp = _csw_lp(text)
        _th_lo_lp, _th_hi_lp = _th_target_lp(_src_words_lp)
        _bp_lo_lp, _bp_hi_lp = _bp_target_lp(_src_words_lp)
        _inc_thorough_lp = bool(getattr(self.request, "include_thorough_summary", True))
        _inc_exec_lp = bool(getattr(self.request, "include_executive_summary", True))
        _inc_kp_lp = bool(getattr(self.request, "include_keypoints", True))
        _thorough_words = len(thorough.split()) if thorough else 0
        # V0.07 (output-regression fix): normal chapters (scaled thorough
        # hi >= 800 — the V18 regime) expand below 800 words, restoring
        # MarkItDown V18's expansion contract; small sources (the 97-Things
        # rig regime, hi < 800) keep the source-scaled lo so tiny chapters
        # are never force-expanded to 800+ words.
        _new_threshold = (800 if _th_hi_lp >= 800 else _th_lo_lp) if _inc_thorough_lp else 0
        # V18.20.3.2 (P0-1b): snapshot the synthetic-fallback counter BEFORE
        # the dedicated call — if it increments, the returned thorough is the
        # deterministic exec+bullets synthesis built from the EARLY bullet
        # set (pre-expansion, pre-gap-fill). The final stage re-derives it
        # from the FINAL bullet set in that case (see the postchecks block).
        _syn_fb_before = getattr(self, "_synthetic_thorough_fallback_count", 0)
        if _inc_thorough_lp and (not thorough or _thorough_words < _new_threshold):
            self.log(
                f"    ⚠️ thorough_summary too short ({_thorough_words} words < {_new_threshold} threshold) — requesting dedicated expansion…",
                "WARNING",
            )
            # V18.2.44 (Next Step #6): replaced the 2-attempt
            # ``_call_llm_with_empty_retry`` with the new 3-attempt +
            # synthetic-fallback helper. The V18.2.43 session noted the
            # dedicated expansion "sometimes fails (empty responses)" — this
            # makes the path robust: 3 attempts at varying temperature /
            # nudges, then a deterministic exec+bullets synthesis so the
            # thorough is NEVER empty (was silently degrading to a 1-para
            # ``thorough = exec_sum`` stub before).
            _dedicated_prompt = self._build_dedicated_thorough_prompt(
                heading,
                text,
                exec_sum,
                bullets,
                # V18.20.3.11 (Phase 3.b, .3.9 rig audit §2): pass the
                # primary's partial thorough as the continuation draft —
                # it was cut at the primary's output cap (423-763 words
                # across rig runs .3.7-.3.9) and previously discarded,
                # paying the truncation twice. Empty/CoT-nuked thorough
                # renders the block inert (draft=None path).
                draft=(thorough or None),
            )
            fu_raw = self._call_dedicated_thorough_with_fallback(
                _dedicated_prompt,
                exec_sum=exec_sum,
                bullets=bullets,
                min_words=_new_threshold,
            )
            if fu_raw:
                fu_raw = self._strip_thinking(fu_raw)
                m = re.search(r"<thorough_summary>(.*?)</thorough_summary>", fu_raw, re.DOTALL)
                if m:
                    _new_thorough = m.group(1).strip()
                else:
                    _new_thorough = fu_raw.strip()
                if _new_thorough and len(_new_thorough.split()) > _thorough_words:
                    thorough = _new_thorough
                    self.log(
                        f"    ✅ thorough_summary expanded via dedicated call: {_thorough_words} → {len(thorough.split())} words",
                        "INFO",
                    )
                elif _new_thorough:
                    self.log(
                        f"    ℹ️ Dedicated thorough call returned {len(_new_thorough.split())} words (not longer than original {_thorough_words}) — keeping original",
                        "DEBUG",
                    )
        # V18.20.3.2 (P0-1b): flag when the dedicated call fell back to the
        # deterministic synthesis (early bullets only) — the final stage
        # rebuilds it from the final bullet set.
        self._thorough_is_synthetic = (
            getattr(self, "_synthetic_thorough_fallback_count", 0) > _syn_fb_before
        )
        # V18.15.8.0 (Fix 1): Reorder — produce thorough first, then derive
        # exec FROM thorough. The thorough summary has a dedicated system with
        # 100% coverage (the dedicated thorough call at line 3060 ensures
        # thorough is NEVER empty). When exec_sum is empty, we derive it FROM
        # the thorough summary via a followup LLM call — NOT the pre-V18.15.8.0
        # backwards fallback (``thorough = exec_sum`` which copied an empty
        # string when exec was also empty, causing the V18.15.7.0 cascade
        # failure where BOTH exec + thorough were empty).
        # V0.05 (F9a): the exec-from-thorough derivation only fires when the
        # user actually requested an executive summary — the flags are the
        # contract.
        if _inc_exec_lp and not exec_sum and thorough and len(thorough.strip()) >= 50:
            exec_sum = self._ensure_exec_from_thorough(heading, thorough)
            if exec_sum:
                parsed["executive_summary"] = exec_sum
        # Last-resort fallback (rare now — only fires if BOTH the dedicated
        # thorough call AND the exec-from-thorough call failed).
        # V0.05 (F9a): never fabricate a thorough the user did not request.
        if not thorough and _inc_thorough_lp:
            thorough = exec_sum

        # V18.2.34: Dedicated bullet expansion. If the primary call returned
        # <30 bullets, fire a STANDALONE bullet-expansion LLM call (full
        # output budget) asking for 30-50 NEW bullets. The existing bullets
        # are kept; new bullets are de-duplicated against them before being
        # appended. This addresses the V18.2.28 regression where the
        # primary call was truncated by the 2048-token output cap and
        # returned only 4-7 bullets per chapter.
        bullets = parsed.get("bullet_points", bullets) or bullets
        # V18.15.4.0: Skip bullet expansion for short chapters (< 10000 tokens)
        # that already have >= 20 bullets. The expansion call adds ~7 minutes
        # and is unnecessary for short chapters with adequate coverage. The
        # gap-fill loop will still add any missing theorists. This prevents
        # the deadline from being consumed by expansion on chapters that
        # don't need it (the the rig-test chapter is 9120 tokens with 24
        # bullets — expansion to 71 was overkill and pushed past the deadline).
        _input_tok = count_tokens(text)
        # V18.15.4.3: Raised threshold 9000 -> 10000 tok (the V18.15.4.0 run hit
        # 9120 tok and the skip didn't fire, pushing past the 2400s deadline).
        # V0.05 (rig audit F9b — GENERAL RULE): the expansion floor/ceiling now
        # SCALE to the source (length_policy.bullet_target) instead of the
        # absolute "<30 → ask for 30-50". The V0.04 rig shipped 29-36 bullets
        # for 321-441-word chapters (one bullet per ~12 source words — the
        # chapter restated as bullets) because this machinery pushed every
        # chapter toward 30+. A 340-word chapter's target is ~5-7 bullets; the
        # expansion call does not fire at all when the primary already met the
        # SCALED target. Also gated on the user's keypoints selection (F9a).
        _skip_expansion = not _inc_kp_lp or bool(bullets and len(bullets) >= _bp_lo_lp)
        if _skip_expansion and _inc_kp_lp:
            self.log(
                f"    V0.05: Skipping bullet expansion — {len(bullets or [])} bullets "
                f"already meet the source-scaled target ({_bp_lo_lp}-{_bp_hi_lp} for "
                f"a {_src_words_lp}-word chapter; gap-fill will handle missing "
                f"concepts).",
                "INFO",
            )
        elif not _inc_kp_lp:
            self.log(
                "    V0.05 (F9a): Keypoints not requested — bullet expansion "
                "disabled for this chapter.",
                "DEBUG",
            )
        if (
            _inc_kp_lp
            and bullets
            and len(bullets) < _bp_lo_lp
            and not self._deadline_exceeded("dedicated bullet expansion")
            and not _skip_expansion
        ):
            self.log(
                f"    ⚠️ Only {len(bullets)} bullets — requesting dedicated bullet expansion (full output budget)…",
                "INFO",
            )
            _bp_raw = self._call_llm_with_empty_retry(
                self._build_dedicated_bullet_prompt(heading, text, exec_sum, bullets),
                model=self.primary_model,
                temperature=self.temperature,
                max_tokens=min(self.request.summarisation_max_output_tokens, 8192),
            )
            if _bp_raw:
                _bp_raw = self._strip_thinking(_bp_raw)
                _new_bullets = self._extract_bullets_from_text(_bp_raw)
                if _new_bullets and len(_new_bullets) > len(bullets):
                    _existing_lower = {b.lower()[:60] for b in bullets}
                    # V18.20.3.2 (audit N1 / P0-2): BATCH-filter the expansion
                    # candidates in ONE call, then append the survivors. The
                    # V18.20.3.1 path filtered per-bullet (37 separate filter
                    # calls): the aggregate log line ("Filtered 1 thinking …
                    # kept 0") described only the LAST call, hiding that 36
                    # unfiltered candidates had sailed through — and two
                    # model SELF-TALK lines ("AuthorW (1968) - include this!
                    # Let me add it.") shipped to the final output because the
                    # start-anchored thinking patterns missed them (they start
                    # with an author-year token). One batch call = one honest
                    # aggregate log + the new mid-bullet self-talk patterns
                    # (SELF_TALK_PATTERNS) catch the planning-note class.
                    _candidates = [
                        nb for nb in _new_bullets if nb.lower()[:60] not in _existing_lower
                    ]
                    _filtered = self._filter_thinking_bullets(
                        _candidates,
                        concepts=None,
                        source_text="",
                    )
                    _added = 0
                    for fb in _filtered:
                        if fb.lower()[:60] not in _existing_lower:
                            bullets.append(fb)
                            _existing_lower.add(fb.lower()[:60])
                            _added += 1
                    _dropped_exp = len(_candidates) - _added
                    if _dropped_exp > 0:
                        self.log(
                            f"    🎓 V18.20.3.2: Expansion filter dropped "
                            f"{_dropped_exp}/{len(_candidates)} candidate bullet(s) "
                            f"(thinking/prompt-leakage/self-talk) before merge",
                            "INFO",
                        )
                    if _added > 0:
                        self.log(
                            f"    ✅ Bullet expansion: {len(bullets) - _added} → {len(bullets)} bullets (added {_added} new via dedicated call)",
                            "INFO",
                        )
                        parsed["bullet_points"] = bullets

        # ── Final coverage check ─────────────────────────────────────────────
        # Sanitize bullets — ensure all items are strings (academic-rigor JSON
        # parsing can leave dicts in the list, which crashes str.join).
        bullets = [str(b) if not isinstance(b, str) else b for b in bullets if b]
        final_summary = f"{exec_sum} {' '.join(bullets)} {thorough}"
        coverage = self._compute_coverage(content, final_summary)

        # Adaptive coverage threshold — start at the
        # configured threshold (now 70%+ by default), but after 3 retries,
        # accept best-effort rather than looping forever.  change:
        # the floor is raised from 50% → 60%, and when best-effort is accepted
        # BELOW the 70% target, the warning explicitly says so (no silent
        # acceptance of low coverage).  This honours the "70% minimum" goal
        # while still terminating on hard books.
        if not hasattr(self, "_coverage_retry_counts"):
            self._coverage_retry_counts = {}
        chapter_retry_key = heading[:50]
        self._coverage_retry_counts[chapter_retry_key] = (
            self._coverage_retry_counts.get(chapter_retry_key, 0) + 1
        )
        retry_count = self._coverage_retry_counts[chapter_retry_key]

        effective_threshold = self.coverage_threshold
        if retry_count > 3:
            # floor at 60% (was 50%) — never silently accept below that.
            effective_threshold = max(0.60, self.coverage_threshold - 0.10)
            if coverage < 0.70:
                self.log(
                    f"    ⚠️ Coverage at {coverage:.0%} after {retry_count} retries — "
                    f"BELOW the 70% target. Accepting best-effort to avoid "
                    f"infinite retries, but this chapter needs manual review.",
                    "WARNING",
                )
            else:
                self.log(
                    f"    📉 Coverage at {coverage:.0%} after {retry_count} retries — "
                    f"accepting best effort (threshold {self.coverage_threshold:.0%})",
                    "WARNING",
                )

        if coverage < effective_threshold:
            self.log(
                f"    ⚠️ Final coverage {coverage:.0%} below {effective_threshold:.0%} threshold",
                "WARNING",
            )
        else:
            self.log(f"    ✅ Final coverage {coverage:.0%}", "INFO")
        return (
            _bp_hi_lp,
            _bp_lo_lp,
            _inc_exec_lp,
            _inc_kp_lp,
            _inc_thorough_lp,
            _src_words_lp,
            _th_hi_lp,
            bullets,
            coverage,
            exec_sum,
            final_summary,
            thorough,
        )

    def _phase_validation_and_judge(
        self,
        heading,
        content,
        concepts,
        tok_in,
        coverage,
        exec_sum,
        bullets,
        thorough,
        final_summary,
        _pipeline,
        _pstate,
    ):
        """V0.18 (Phase 5.1): moved VERBATIM from _summarize_inner."""
        # ── Strip thinking from all final fields one more time ──────────────
        exec_sum = self._strip_thinking(exec_sum)
        bullets = [self._strip_thinking(bp) for bp in bullets]
        thorough = self._strip_thinking(thorough)
        thorough = self._strip_narrative_from_thorough(thorough)

        # V10.32.0 (Sprint 4 s2): Academic factual-claim verification
        # delegated to BulletPipeline. (extracted verbatim — see
        # BulletPipeline.apply_academic_factual_verification)
        _pstate.bullets = bullets
        _pstate.content = content
        _pipeline.apply_academic_factual_verification(_pstate)
        bullets = _pstate.bullets

        # V10.32.0 (Sprint 4 s2): Empty-output salvage delegated to BulletPipeline.
        # (extracted verbatim — see BulletPipeline.salvage_empty_output)
        # Returns True if the chapter should continue, False if it should fail.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        if not _pipeline.salvage_empty_output(_pstate):
            msg = "Summary is empty after all validation checks — marking as failed"
            self.log(f"    🚫 {msg}", "ERROR")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary=thorough,
                success=False,
                error_msg=msg,
                input_tokens=tok_in,
                output_tokens=count_tokens(final_summary),
            )
        bullets = _pstate.bullets
        exec_sum = _pstate.exec_sum
        thorough = _pstate.thorough

        # V10.32.0 (Sprint 4 s2): F1 length validation delegated to BulletPipeline.
        # (extracted verbatim — see BulletPipeline.apply_f1_length_validation)
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f1_length_validation(_pstate)
        exec_sum = _pstate.exec_sum
        thorough = _pstate.thorough

        # ── V10.31.0 (Sprint 4.1): F4 + Phase 2.2 stages delegated to
        # BulletPipeline.  The inline implementations were extracted verbatim
        # into ``core/summarisation/bullet_pipeline.py`` (BulletPipeline
        # .apply_f4_source_overlap + .apply_phase22_semantic_fact_check).
        # This is the first step of the Sprint 4 architecture refactor —
        # ``_summarize_inner`` will progressively delegate more stages until
        # it's a ≤100-line orchestrator (session 2 completes the extraction).
        # V13.6.0: _pipeline + _pstate already created above (before self-review).
        # Just refresh the state with current bullets/exec_sum/thorough.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f4_source_overlap(_pstate)
        _pipeline.apply_phase22_semantic_fact_check(_pstate)
        bullets = _pstate.bullets

        # ── V10.32.0 (Sprint 4 s2): F3 reading level + informational checks
        # extracted to BulletPipeline.  These are informational-only (log
        # but don't modify state, except F3 which may simplify thorough).
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f3_reading_level(_pstate)
        _pipeline.run_informational_checks(_pstate)
        thorough = _pstate.thorough

        # ── V10.32.0 (Sprint 4 s2): gap-fill extracted to BulletPipeline ─
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.gap_fill_concepts(_pstate, concepts)
        bullets = _pstate.bullets

        # V10.32.0 (Sprint 4 s2): F3 reading level, I2/J2/J3 informational
        # checks, and gap-fill are now delegated to BulletPipeline above.
        # The inline implementations were extracted verbatim — see
        # BulletPipeline.apply_f3_reading_level / .run_informational_checks
        # / .gap_fill_concepts.

        # V10.32.0 (Sprint 4 s2): Content Judge stage extracted to
        # BulletPipeline.run_content_judge().  This was the largest inline
        # block (~490 lines) — grounding checks, gap-fill reprompts, hard
        # rejection.  Returns None to continue, or a SummaryResult on hard reject.
        # V13.41.1: VRAM recovery + try/except wrapper. The content judge
        # runs langextract which loads a second model into VRAM — after B4 +
        # gap-fill, the GPU is exhausted and langextract can OOM-crash.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        self._recover_vram(context="pre-content-judge", delay_sec=15.0)
        try:
            _reject = _pipeline.run_content_judge(_pstate, coverage, tok_in, final_summary)
        except Exception as _e:
            self.log(f"    ⚠️ Content judge crashed (non-fatal): {_e}", "WARNING")
            logger.debug("content judge crashed: %s: %s", type(_e).__name__, _e)
            _reject = None  # skip the judge, continue with current bullets
        if _reject is not None:
            return _reject
        bullets = _pstate.bullets
        return bullets, exec_sum, thorough
