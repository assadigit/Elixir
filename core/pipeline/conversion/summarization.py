"""V10.11.0 (Phase 8F): Summarization phase — extracted from converter.convert().

Contains the LLM summarization orchestration that runs as Step 9 of the
conversion — the largest + most complex phase.  Covers:

  - Force-unload the OCR model to free VRAM before summarization
  - Apply content filter (remove non-content pages) if enabled
  - Skip reference/bibliography/appendix sections from summarization
  - Build a ClaimExtractor for Layer 8 (langextract) grounding
  - Detect the GPU thermal profile + cap max_workers for VRAM safety
  - Initialize + start the ThermalSafetyController (pre-flight check,
    output-count guard, model recommendation)
  - Run the Summarizer (with deterministic concept/callout extraction)
  - Chapter-level resume (skip already-summarized chapters)
  - Best-match chapter selection (when user selected specific chapters)
  - Merge loaded + newly-generated summaries
  - Incremental saving (atomic write each summary as it's generated)
  - Build the book summary (Book.summary.md)
  - Stash judge_results for downstream outputs (keypoints/flashcards)

Returns :class:`SummarizationResult` (summaries) on success, or
:class:`ConversionResult` (success=False) on early exit (user cancel
or thermal pre-flight failure).

Extracted into its own module so the converter's ``convert()`` method
is shorter and the summarization orchestration is testable independently.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

from core.models import ConversionResult, SummaryResult
from core.summarisation import Summarizer

# V18.20.4.12 (W-a11): /no_think gated on Qwen-family models via the
# shared helper — the directive is a Qwen3 soft-switch; for other models
# it is prompt pollution.
from core.summarisation.filter_thinking import qwen_no_think
from core.system.timeouts import FAST_LLM_TIMEOUT_S, LLM_REQUEST_TIMEOUT_S

# V18.20.2.0 (SWOT A30): module-level import — the per-chapter write loop
# previously imported this INSIDE the loop body, which left the name
# unbound for the Book.summary.md write below when ``summaries`` was empty.
from utils.atomic_io import atomic_write_text
from utils.error_trace import log_swallow

logger = logging.getLogger(__name__)


@dataclass
class SummarizationResult:
    """The state produced by the summarization phase.

    Fields:
        summaries: the list of SummaryResult objects (merged loaded + new).
    """

    summaries: list[SummaryResult]


def compute_final_positions(
    segments: list[Any],
    todo_headings: set,
    loaded_headings: set,
) -> dict:
    """Map each UNAMBIGUOUS chapter heading to its final merged position.

    Walks the segment order counting every segment that will have a
    summary (this run's todo chapters + resume-loaded chapters) — the
    same numbering the end-of-run writer produces for the merged list.

    V0.6.6 (review-loop A1): a heading carried by TWO summarized
    chapters (duplicate headings — two "Introduction" segments;
    content-agnostic, any book can have them) is deliberately LEFT OUT
    of the map. The checkpoint saver keys its filenames by this map, so
    a duplicate heading would collapse BOTH chapters onto one
    filename: the second chapter's summary was silently LOST (the
    write-once guarantee skips it) while the first was saved TWICE
    (once per-run-index, once per-map-position) and the second's
    per-chapter DOCX overwrote the first's. Colliding headings fall
    back to the saver's per-run chapter index — unique per chapter and
    identical to the end-of-run writer's numbering whenever no resume
    merge shifts positions.
    """
    from collections import Counter

    counted = Counter(
        s.heading for s in segments if s.heading in todo_headings or s.heading in loaded_headings
    )
    positions: dict = {}
    fp = 0
    for seg in segments:
        if seg.heading in todo_headings or seg.heading in loaded_headings:
            fp += 1
            if counted[seg.heading] == 1:
                positions[seg.heading] = fp
    return positions


def _save_chapter_summaries_write_once(
    converter: Any,
    segments: list[Any],
    summaries: list[SummaryResult],
    log: Any,
) -> None:
    """V0.6.7 (review-loop B6): the per-chapter end-of-run summary save
    block, moved VERBATIM from run_summarization (V0.6.6 lines 992-1175) so
    it can be characterized directly — the finding's "extraction +
    characterization candidate". Pure move: the statement sequence is
    AST-identical to the original block (verified at extraction time); the
    behavior contract is pinned in tests/test_v067_review_loop_fixes.py.
    The only rebindings
    are the enclosing-scope names → parameters (``converter`` /
    ``segments`` / ``summaries`` / ``log`` were the only outsiders the
    block touched). It writes files + logs only — nothing downstream
    consumed its locals.

    Behavior contract (pinned by TestSaveChapterSummariesWriteOnce):
    failed/empty summaries are skipped; filenames are run-stamped (legacy
    unstamped results keep the exact legacy name); a pre-existing file
    WITH the COMPLETE sentinel is never rewritten (write-once
    crash-safety) — without the sentinel, or unreadable, it is rewritten;
    the verification layer is fail-open; errno-28 raises the actionable
    disk-full error, any other OSError propagates unchanged.
    """
    # ── Incremental saving (atomic write each summary) ──────────────
    # V10.24.0: Write summaries to the summaries/ subfolder (not
    # markdown/chapters/summaries/).  The markdown/ folder should only
    # contain markitdown-generated .md files, not LLM-generated summaries.
    # V18.20.3.0: the per-chapter markdown is now rendered by the shared
    # ``render_summary_markdown`` helper (same bytes the incremental
    # chapter-checkpoint saver writes mid-run), and the write is WRITE-ONCE:
    # a file that already exists WITH the COMPLETE sentinel is never
    # rewritten — completed chapters stay byte-identical even if the
    # end-of-run writer sees them again.
    summary_folder = converter.paths.book_summary.parent
    summary_folder.mkdir(exist_ok=True)
    from core.pipeline.chapter_checkpoint import render_summary_markdown

    # V0.4.40: build a heading->source map for the post-conversion
    # verification + polish LAYER (verify_and_polish_summary). The
    # verification runs AFTER render on the assembled per-chapter output;
    # it needs the chapter source to check Dates/Names/Omissions/
    # Hallucinations. Best-effort heading match (exact, then
    # case-insensitive, then contains) — fail-open (no match → the
    # verification skips that chapter, the original output ships).
    # V0.5.2 (BUG fix): build from `segments` (ALL segments, not just
    # `segments_for_summary` which may have been filtered) + add a
    # fallback (largest segment = the main chapter content) + log the
    # match result so the audit can see whether the LAYER fired.
    _source_by_heading: dict[str, str] = {}
    for _seg in segments:
        if getattr(_seg, "heading", None) and getattr(_seg, "content", None):
            _source_by_heading[_seg.heading] = _seg.content

    def _source_for_summary(_summ_heading: str) -> str:
        """Best-effort match the summary's heading to a segment's source.

        V0.5.2: if no heading match, fall back to the LARGEST segment
        (the main chapter content is usually the largest). This ensures
        the verification LAYER fires even when the heading match fails.
        """
        if not _summ_heading:
            # Fallback: return the largest segment's content.
            _largest = max(
                _source_by_heading.values(),
                key=len,
                default="",
            )
            if _largest:
                log(
                    f"    ℹ️  V0.5.2 verification: no heading match — "
                    f"using largest segment ({len(_largest)} chars) as source.",
                    "DEBUG",
                )
            return _largest
        if _summ_heading in _source_by_heading:
            return _source_by_heading[_summ_heading]
        _hl = _summ_heading.lower()
        for _h, _c in _source_by_heading.items():
            if _h.lower() == _hl or _hl in _h.lower() or _h.lower() in _hl:
                return _c
        # Fallback: return the largest segment's content.
        _largest = max(_source_by_heading.values(), key=len, default="")
        if _largest:
            log(
                f"    ℹ️  V0.5.2 verification: heading "
                f"'{_summ_heading[:50]}' not matched — using largest "
                f"segment ({len(_largest)} chars) as source.",
                "DEBUG",
            )
        return _largest

    for i, summ in enumerate(summaries, 1):
        # V18.2.4: Don't save failed/empty summaries. Previously the pipeline
        # saved EVERY summary (including failed ones with empty exec_summary),
        # which created empty files with <!-- COMPLETE --> markers. This caused
        # false "Conversion complete" reports and confused the user.
        # Now: skip saving if the summary failed or has no content.
        if not getattr(summ, "success", True) or (
            not summ.executive_summary and not summ.bullet_points and not summ.thorough_summary
        ):
            log(
                f"  ⚠️ Skipped saving FAILED summary {i}/{len(summaries)}: "
                f"{summ.chapter_heading[:50]}… (no content — model returned empty)",
                "WARNING",
            )
            continue
        safe_heading = converter._sanitize_filename(summ.chapter_heading)
        # V0.4.25: run-stamped filename — each conversion's chapter summary
        # gets a unique name (``{NNN}_{heading}_v{ver}_{run_id}_summary.md``)
        # so the operator's file-transfer layer (which caches by filename)
        # can never deliver a stale run's bytes. The stamp comes from the
        # summary's OWN provenance: an adopted (resume-reused) chapter keeps
        # its ORIGINAL run's stamp — the filename always tells the truth
        # about which run produced the content. Unstamped (legacy) results
        # fall back to the exact legacy filename for write-once compat.
        _stamp = ""
        try:
            from core.system.provenance import run_stamp_suffix

            _stamp = run_stamp_suffix(getattr(summ, "app_version", ""), getattr(summ, "run_id", ""))
        except Exception:  # pragma: no cover — stamping must never break the save
            _stamp = ""
        if safe_heading:
            sf_name = f"{i:03d}_{safe_heading}{_stamp}_summary.md"
        else:
            sf_name = f"{i:03d}{_stamp}_summary.md"
        sf = summary_folder / sf_name
        # V18.20.3.0: write-once — the incremental checkpoint saver already
        # persisted this chapter the moment it completed; a completed
        # chapter is NEVER rewritten (crash-safety guarantee: files that
        # existed before a crash stay untouched by the recovery run).
        if sf.exists():
            try:
                _existing_sf = sf.read_text(encoding="utf-8")
                # V18.20.3.7: accepts both the legacy bare sentinel and the
                # run-id-stamped form; logs the adoption when the existing
                # file came from a different run (the V18.20.3.6 stale-file
                # confusion killer — the log now names the producing run).
                from core.system.provenance import (
                    adoption_note,
                    has_complete_sentinel,
                )

                if has_complete_sentinel(_existing_sf):
                    _prov_note = adoption_note(
                        _existing_sf,
                        render_summary_markdown(summ),
                    )
                    log(
                        f"  💾 Summary {i}/{len(summaries)} already saved — leaving untouched: {sf_name}"
                        + (f" 🪪 {_prov_note}" if _prov_note else ""),
                        "DEBUG",
                    )
                    continue
            except OSError:
                pass  # unreadable → rewrite below
        # V18.20.2.0 (SWOT A30): atomic_write_text is imported at module
        # level (see top of file) — same-dir temp + fsync + os.replace.
        try:
            # V0.4.40: the post-conversion verification + polish LAYER.
            # Runs AFTER render on the assembled per-chapter output. The
            # generation LLM did a ~7/10 job; this LLM layer (in a
            # VERIFICATION role, not generation) fills holes + fixes
            # mistakes (Dates/Names/Omissions/Hallucinations) to make it
            # 9/10-10/10. Targeted corrections (verbatim string
            # replacements, NOT a full rewrite) + D3-style guard +
            # fail-open. Non-skippable (catches LLM-variance-driven defects
            # every conversion). Content-agnostic (Rule 1). No-op when no
            # model configured (the common test path) OR no source match.
            _rendered = render_summary_markdown(summ)
            _v_source = _source_for_summary(summ.chapter_heading)
            if _v_source:
                try:
                    from core.summarisation.verification_phase import (
                        verify_and_polish_summary,
                    )

                    _rendered, _v_issues = verify_and_polish_summary(
                        _rendered, _v_source, converter.settings, log
                    )
                    # V0.5.1 (BUG fix): LOG the verification issues to the
                    # conversion log (was silently dropped — the audit
                    # couldn't see the date-check + LLM verification output).
                    for _vi in _v_issues or []:
                        log(
                            f"    ✨ V0.5.1 verification: [{_vi.detector}/{_vi.severity}] "
                            f"{_vi.detail[:120]}",
                            "DEBUG" if _vi.severity == "fix" else "WARNING",
                        )
                except Exception as _ve:  # pragma: no cover — the layer must never break the write
                    log(
                        f"    ⚠️  V0.4.40 verification crashed (non-fatal): "
                        f"{type(_ve).__name__}: {_ve}",
                        "WARNING",
                    )
            atomic_write_text(sf, _rendered)
        except OSError as _owe:
            if _owe.errno == 28 or "No space left" in str(_owe):
                raise OSError(
                    f"Disk is full — cannot save summary "
                    f"{sf_name}. Free space on "
                    f"{sf.anchor} and re-run (resume will skip "
                    f"completed chapters). Original error: {_owe}"
                ) from _owe
            raise
        log(f"  💾 Saved summary {i}/{len(summaries)}: {sf_name}", "DEBUG")
    log(f"📝 {len(summaries)} summaries → {summary_folder}")


# ── V0.6.11 (B14-a): the summarization-phase context ──────────────────────


@dataclass
class _SummCtx:
    """V0.6.11 (B14-a): the phase-shared state for ONE ``run_summarization`` run.

    The V0.6.7/B12 god-function decomposition pattern: the 6 public
    parameters, the converter surface the phase reads (``log`` /
    ``update_status`` / ``update_progress`` / ``request``), and the derived
    per-phase state (the resolved language, the filtered segment list, the
    claim extractor, the GPU profile + thermal controller, the summarizer,
    the chapter dicts, the resume split, the merged summaries) live HERE so
    each phase helper is a thin ``ctx`` reader/writer and the orchestrator
    keeps the original statement order. Nothing here is public — the module
    API is still ``run_summarization`` + ``SummarizationResult``.
    """

    # the 6 public parameters (same order as the signature)
    converter: Any
    segments: list[Any]
    segments_folder: Any
    detected_lang: str
    book_title: str
    elapsed_fn: Any
    # the converter surface (V0.6.11 / B14-a — was locals at function top)
    log: Any
    update_status: Any
    update_progress: Any
    request: Any
    # derived per-phase state (V0.6.11 / B14-a — names match the original locals)
    summary_lang: str = ""
    segments_for_summary: list = field(default_factory=list)
    claim_extractor: Any = None
    gpu_name: str = ""
    gpu_profile: Any = None
    thermal_safety: Any = None
    summarizer: Any = None
    chapter_dicts: list = field(default_factory=list)
    loaded_summaries: list = field(default_factory=list)
    summaries: list[SummaryResult] = field(default_factory=list)


def _rs_unload_ocr_vram(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim force-unload block — frees the LLM-OCR
    model's VRAM before summarization starts."""
    log = ctx.log
    request = ctx.request
    # ── Force-unload OCR model to free VRAM ──────────────────────────
    if request.use_llm_ocr and request.primary_ocr_model:
        from core.llm import ModelManager

        mm = ModelManager()
        loaded = mm.get_loaded_models()
        if request.primary_ocr_model in loaded:
            log(
                f"  🔓 Force-unloading OCR model '{request.primary_ocr_model}' "
                "before summarisation to free VRAM…",
                "INFO",
            )
            mm.force_unload(request.primary_ocr_model)
        import time as _time

        _time.sleep(2)


def _rs_apply_content_filter(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim content-filter block (opt-in page
    cleanup before summarization)."""
    log = ctx.log
    converter = ctx.converter
    request = ctx.request
    segments = ctx.segments
    # ── Apply content filter ONLY if enabled ─────────────────────────
    if request.enable_content_filter:
        log("  🧹 Content filter enabled – removing non‑content pages.", "INFO")
        for seg in segments:
            seg.content = converter._filter_segment_content(seg)
    else:
        log("  ⏭️ Content filter disabled – keeping all pages.", "INFO")


def _rs_filter_reference_sections(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim front-matter skip (references /
    bibliography / appendix families) with the selected-chapters DISABLE —
    sets ``ctx.segments_for_summary``."""
    log = ctx.log
    request = ctx.request
    segments = ctx.segments
    # ── Skip reference/supplementary sections from summarization ─────
    # V0.02 (false-success RCA): when the user EXPLICITLY selected chapters,
    # this skip is DISABLED. The real incident: the user's two selected
    # chapters were absorbed into a 'Preface' segment by Layer-3 merging
    # (full-TOC segmentation on a partial extraction — fixed in
    # segmentation.py), the skip list then matched the merged segment's
    # heading → 0 summaries → "✅ Conversion complete." A section the user
    # deliberately picked is never "non-content" — and a deliberately
    # selected Preface/Foreword must be summarized too.
    if request.selected_chapters:
        log(
            f"  ⏭️ Chapter selection active ({len(request.selected_chapters)} "
            f"title(s)) — front-matter skip disabled (selected sections are "
            f"always summarized).",
            "INFO",
        )
        ctx.segments_for_summary = segments
    else:
        _skip_patterns = [
            (r"^references\s*$", "references"),
            (r"^bibliography\s*$", "bibliography"),
            (r"^works cited\s*$", "works cited"),
            (r"^supplementary", "supplementary materials"),
            (r"^appendix", "appendix"),
            (r"^supporting information", "supporting information"),
            (r"^acknowledg", "acknowledgements"),
            # V10.24.0: Add dedication, preface, foreword, copyright, table of contents
            # These sections are too short for meaningful summarization and produce
            # garbage output (the LLM has < 100 tokens of source → hallucinates).
            (r"^dedication", "dedication"),
            (r"^preface", "preface"),
            (r"^foreword", "foreword"),
            (r"^copyright", "copyright"),
            (r"^table of contents", "table of contents"),
            (r"^about the author", "about the author"),
            (r"^index\s*$", "index"),
        ]
        _filtered_segments = []
        _skipped_count = 0
        for seg in segments:
            heading_lower = seg.heading.strip().lower()
            should_skip = False
            for pattern, label in _skip_patterns:
                if re.match(pattern, heading_lower):
                    log(
                        f"  ⏭️ Skipping '{seg.heading[:50]}' from summarization ({label})",
                        "INFO",
                    )
                    should_skip = True
                    _skipped_count += 1
                    break
            if not should_skip:
                _filtered_segments.append(seg)
        if _skipped_count > 0:
            log(
                f"  📋 Skipped {_skipped_count} reference/supplementary section(s) from summarization",
                "INFO",
            )
            ctx.segments_for_summary = _filtered_segments
        else:
            ctx.segments_for_summary = segments


def _rs_build_claim_extractor(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim Layer-8 (langextract) claim-extractor
    init with its three fail-open exits — sets ``ctx.claim_extractor``."""
    log = ctx.log
    # ── Build ClaimExtractor for Layer 8 (langextract) grounding ─────
    ctx.claim_extractor = None
    try:
        from core.grounding import ClaimExtractor, is_langextract_available
        from utils.settings import Settings as _S

        ctx.claim_extractor = ClaimExtractor(
            settings=_S(),
            log_callback=log,
        )
        if ctx.claim_extractor._is_enabled():
            if is_langextract_available():
                log(
                    f"  🛡️ Source grounding ENABLED "
                    f"(backend={ctx.claim_extractor._get_backend().value}) — "
                    f"Layer 8 (langextract) active",
                    "INFO",
                )
            else:
                log(
                    "  🛡️⚠️ Source grounding enabled in settings but "
                    "langextract is NOT installed. Layer 8 will be "
                    "skipped (Layers 1-7 still active). "
                    "Run: pip install langextract",
                    "WARNING",
                )
        else:
            # V15.0.4: Check if user enabled grounding but the backend is
            # local Ollama (which can't produce char_intervals).
            _reason = getattr(ctx.claim_extractor, "_disabled_reason", None)
            if _reason == "ollama_no_char_intervals":
                # V18.2.19: Downgraded WARNING → INFO. This is INTENTIONAL
                # behavior (Decision #4 in the handout): local models can't
                # produce char_intervals, so Layer 8 is disabled. The old
                # WARNING with ❌ scared users into thinking something was
                # broken. This is by-design — Layers 1-7 still provide
                # semantic grounding.
                log(
                    "  🛡️ Source grounding: Layer 8 (langextract verbatim) is "
                    "DISABLED because backend='ollama' (local). Local models "
                    "cannot produce char_intervals — this is by design "
                    "(Decision #4). Layers 1-7 (semantic checks + judge "
                    "appeal) remain active. To enable Layer 8: Settings → "
                    "Grounding → backend = 'cloud'.",
                    "INFO",
                )
    except (ImportError, OSError) as _ce:
        log(
            f"  🛡️ ClaimExtractor init failed ({type(_ce).__name__}: {_ce}) — "
            f"Layer 8 disabled, using Layers 1-7 only",
            "WARNING",
        )
        ctx.claim_extractor = None
    except Exception as _ce:
        log(
            f"  🛡️❌ Unexpected error in ClaimExtractor init "
            f"({type(_ce).__name__}: {_ce}) — Layer 8 disabled",
            "ERROR",
        )
        ctx.claim_extractor = None


def _rs_detect_gpu_profile(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim GPU thermal-profile detection + the two
    max_workers caps (thermal profile cap; the VRAM-calculator 85% cap) —
    sets ``ctx.gpu_name`` / ``ctx.gpu_profile``."""
    log = ctx.log
    request = ctx.request
    converter = ctx.converter
    # ── Detect GPU thermal profile + cap max_workers ────────────────
    ctx.gpu_name = ""
    ctx.gpu_profile = None
    try:
        from core.system.hardware_monitor import detect_gpu_profile_from_system

        ctx.gpu_name, ctx.gpu_profile = detect_gpu_profile_from_system()
        if ctx.gpu_name:
            log(f"  🎯 GPU detected: {ctx.gpu_name}", "INFO")
            log(
                f"  🌡️ Thermal profile: {ctx.gpu_profile.name} — "
                f"warning {ctx.gpu_profile.warning_c}°C, "
                f"caution {ctx.gpu_profile.caution_c}°C, "
                f"critical {ctx.gpu_profile.critical_c}°C "
                f"(hotspot delta ~{ctx.gpu_profile.hotspot_delta_c}°C)",
                "INFO",
            )
            current_workers = getattr(request, "max_workers", 2)
            if ctx.gpu_profile.max_safe_workers < current_workers:
                log(
                    f"  🚨 VRAM protection: max_workers capped "
                    f"{current_workers} → {ctx.gpu_profile.max_safe_workers} "
                    f"for {ctx.gpu_profile.name}.  LLM inference is a "
                    f"memory-bandwidth-bound workload — multiple workers "
                    f"multiply VRAM heat.  This cap protects your card's "
                    f"VRAM from thermal damage.",
                    "WARNING",
                )
                request.max_workers = ctx.gpu_profile.max_safe_workers

            # V13.28.0 (P2.9): VRAM-based max_workers cap — complements the
            # thermal cap above. Uses the V13.26.0 VRAM calculator (with
            # quantization + KV cache) to check if the model fits at the
            # current worker count. If peak VRAM > 85% of total, cap to 1.
            try:
                from core.vram_calculator import calculate_vram_budget, get_total_vram

                _total_vram = get_total_vram()
                if _total_vram and request.max_workers > 1:
                    _sum_model = (
                        getattr(request, "summarisation_model", "")
                        or getattr(request, "primary_model", "")
                        or converter.settings.get("summarisation.model", "")
                    )
                    _ctx_tokens = converter.settings.get("summarisation.max_context_tokens", 32768)
                    _estimates, _peak, _total, _rec = calculate_vram_budget(
                        summarization_model=_sum_model,
                        max_workers=request.max_workers,
                        context_tokens=_ctx_tokens,
                    )
                    if _peak > _total_vram * 0.85:
                        log(
                            f"  🧠 VRAM calculator: max_workers capped "
                            f"{request.max_workers} → 1 — peak VRAM "
                            f"{_peak:.1f} GB / {_total_vram:.1f} GB "
                            f"({_peak / _total_vram * 100:.0f}%) at "
                            f"{request.max_workers} workers would risk OOM. "
                            f"Model: {_sum_model} at {_ctx_tokens // 1000}k context.",
                            "WARNING",
                        )
                        request.max_workers = 1
                    else:
                        log(
                            f"  🧠 VRAM calculator: peak {_peak:.1f} GB / "
                            f"{_total_vram:.1f} GB at {request.max_workers} "
                            f"worker(s) — OK",
                            "DEBUG",
                        )
            except Exception as _vram_e:
                log(f"  ℹ️ VRAM calculator check skipped ({_vram_e})", "DEBUG")
            if ctx.gpu_profile.emergency_mode:
                log(
                    f"  🚨 EMERGENCY MODE: {ctx.gpu_profile.name}. "
                    f"If you see visual artifacts (red dots/lines on "
                    f"your monitor) during this conversion, STOP "
                    f"IMMEDIATELY — the VRAM is overheating.  The "
                    f"auto-pause will fire at {ctx.gpu_profile.critical_c}°C "
                    f"core (est. {ctx.gpu_profile.critical_c + ctx.gpu_profile.hotspot_delta_c}°C "
                    f"VRAM).  If artifacts appear BELOW this threshold, "
                    f"the VRAM thermal pads need physical replacement — "
                    f"no software setting can fix that.",
                    "WARNING",
                )
    except (ImportError, OSError, subprocess.TimeoutExpired) as _ge:
        log(
            f"  ℹ️ GPU profile detection failed ({type(_ge).__name__}: {_ge}), "
            f"using default profile",
            "WARNING",
        )
        try:
            from core.system.hardware_monitor import _PROFILE_DEFAULT

            ctx.gpu_profile = _PROFILE_DEFAULT
        except Exception as _e:
            ctx.gpu_profile = None
    except Exception as _ge:
        log(
            f"  ❌ Unexpected error in GPU profile detection "
            f"({type(_ge).__name__}: {_ge}) — using default profile",
            "ERROR",
        )
        try:
            from core.system.hardware_monitor import _PROFILE_DEFAULT

            ctx.gpu_profile = _PROFILE_DEFAULT
        except Exception as _e:
            ctx.gpu_profile = None


def _rs_start_thermal_safety(ctx: _SummCtx) -> ConversionResult | None:
    """V0.6.11 (B14-a): the verbatim Thermal Safety System pre-flight + start
    block — sets ``ctx.thermal_safety`` (and the converter stash). Returns the
    built error result when the pre-flight fails (the original early return),
    else ``None`` (return plumbing — the declared normalization)."""
    log = ctx.log
    converter = ctx.converter
    request = ctx.request
    # ── Thermal Safety System — pre-flight + start ──────────────────
    ctx.thermal_safety = None
    if ctx.gpu_profile is not None:
        try:
            from core.system.thermal_safety import (
                ThermalSafetyController,
                check_output_count_safety,
                recommend_thermal_safe_models,
            )

            ctx.thermal_safety = ThermalSafetyController(
                log_callback=log,
                profile=ctx.gpu_profile,
            )

            # 1. Output count guard
            check_output_count_safety(
                request,
                ctx.gpu_profile,
                log_callback=log,
            )

            # 2. Model recommendation
            recommend_thermal_safe_models(
                getattr(request, "summarisation_model", ""),
                ctx.gpu_profile,
                log_callback=log,
            )

            # 3. Pre-flight thermal check
            _nvidia_smi = ""
            try:
                from core.system.hardware_monitor import HardwareMonitor

                _nvidia_smi = HardwareMonitor._find_nvidia_smi() or ""
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
            _pf_passed, _pf_msg = ctx.thermal_safety.preflight_check(
                nvidia_smi_path=_nvidia_smi,
                model_manager=None,  # skip warmup — too slow for pre-flight
                model_name=getattr(request, "summarisation_model", ""),
            )
            if not _pf_passed:
                log(
                    "  🚨 Pre-flight thermal check FAILED. Conversion aborted to protect the GPU.",
                    "ERROR",
                )
                return converter._build_error_result(_pf_msg)

            # 4. Start the thermal safety controller
            ctx.thermal_safety.start()
            converter._thermal_safety = ctx.thermal_safety  # stash for later
        except Exception as _tse:
            log(
                f"  ℹ️ Thermal Safety System init skipped ({_tse})",
                "DEBUG",
            )
    else:
        log(
            "  ℹ️ Thermal Safety System skipped (GPU profile not available)",
            "DEBUG",
        )
    return None


def _rs_init_summarizer(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim Summarizer construction + the V0.4.25
    run-id unification — sets ``ctx.summarizer``."""
    log = ctx.log
    converter = ctx.converter
    request = ctx.request
    summary_lang = ctx.summary_lang
    _claim_extractor = ctx.claim_extractor
    # ── Run the Summarizer ───────────────────────────────────────────
    summarizer = Summarizer(
        request,
        log_callback=log,
        language=summary_lang,
        claim_extractor=_claim_extractor,
    )
    # V0.4.25: ONE run id per conversion — the Summarizer generates its own
    # run_id in __init__ (a second id), which is how one conversion ended
    # up with a log stamped run X and chapter summaries stamped run Y
    # (b3e7f026 vs 491d1bf4 in the V4.23 audit). Overwrite it with the
    # converter-level id so the conversion log, every chapter summary, the
    # book summary, AND every output FILENAME stamp share one identifier —
    # an audit can correlate all artifacts by a single id.
    try:
        _conv_rid = getattr(getattr(converter, "conv_logger", None), "_conversion_run_id", "")
        if _conv_rid:
            summarizer._run_id = _conv_rid
    except Exception:  # pragma: no cover — unification must never break the phase
        pass
    ctx.summarizer = summarizer


def _rs_thread_glossary_handoff(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim V0.5.20 glossary-handoff block — threads
    the unified run id + the run's output dir onto the request so the deep
    stack persists the glossary INSIDE the run folder."""
    request = ctx.request
    converter = ctx.converter
    summarizer = ctx.summarizer
    # V0.5.20 (the rig-run-2 glossary handoff break): thread the RUN's
    # output dir + the unified run id onto the REQUEST object (the same
    # attached-attribute pattern ``_run_id`` already uses) so the deep
    # summarization stack — the V0.5.7 glossary extraction call in
    # ``primary_call._extract_glossary_for_call`` — persists the
    # .glossary.md INSIDE the run's per-book output folder.
    #
    # The V0.5.19.1 FULL-BOOK run (20260928-155851-011587f0) proved the
    # fragility: ``request.output_dir`` is the BASE dir the user picked
    # (``…\Desktop\5.19.1``), while the converter ALWAYS creates the
    # per-book run folder under it (``…\5.19.1\<the book's run folder>
    # \``) — the glossary landed at
    # ``…\5.19.1\summaries\.glossaries\…`` (OUTSIDE the run's output dir),
    # and every audit-trail line reported "Glossary: (none)" (the dict
    # never carried its path). Defensive setattr — fail-open (the glossary
    # call falls back to ``request.output_dir``, the harness behavior).
    try:
        request._run_id = getattr(summarizer, "_run_id", "") or ""
        _run_out = getattr(converter, "output_dir", None)
        if _run_out is not None:
            request._run_output_dir = str(_run_out)
    except Exception:  # pragma: no cover — the handoff must never break the phase
        pass


def _rs_make_concept_llm_fn(ctx: _SummCtx):
    """V0.6.11 (B14-a): the verbatim V15.2.0/V16.0.9 concept-extraction LLM
    factory — the 4-mode architecture selection (dual_api / dual_local /
    single_local / single_api) + the qwen-gated ``_llm_call_fn`` closure with
    the empty-response nudge retry. Returns the callable, or ``None`` on the
    documented degradation path (the original inner try/except; the
    ``_llm_call_fn = None`` init became the ``return None`` — the declared
    normalization)."""
    log = ctx.log
    request = ctx.request
    try:
        # Lazy import to avoid circular dependency
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings as _S

        _settings = _S()
        _arch = (
            getattr(request, "model_architecture", None)
            or _settings.get("summarisation.model_architecture", "single_local")
            or "single_local"
        )
        # V16.0.9: backward-compat — legacy "single" → "single_local"
        if _arch == "single":
            _arch = "single_local"

        if _arch == "dual_api":
            # Use the OpenAI-compatible cloud API for fast concept extraction.
            _api_url = getattr(request, "fast_api_url", "") or _settings.get(
                "summarisation.fast_api_url", ""
            )
            # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
            from core.system.secrets import get_secret

            _api_key = getattr(request, "fast_api_key", "") or get_secret(
                "summarisation.fast_api_key", _settings, ""
            )
            _api_model = getattr(request, "fast_api_model", "") or _settings.get(
                "summarisation.fast_api_model", ""
            )
            if _api_url and _api_model:
                _provider = create_provider(
                    provider="openai_compatible",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                # Override the cloud settings to point at the fast API.
                # V0.6.8 (audit B4): the override now sets the PUBLIC
                # provider attributes — the old hasattr("_base_url"/
                # "_api_key"/"_model") guards were always False
                # (OpenAICompatProvider stores self.base_url/self.api_key
                # — openai_compat_provider.py:39-40), so the fast-API
                # URL/key were silently ignored and calls kept hitting
                # the settings cloud endpoint. Pinned by
                # tests/test_v068_review_loop_fixes.py.
                _provider.base_url = _api_url
                _provider.api_key = _api_key
                _provider.model = _api_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = FAST_LLM_TIMEOUT_S
                _summ_model = _api_model
                log(
                    f"  🚀 V16.0.8 concept extraction: dual_api mode "
                    f"(fast cloud model = {_api_model})",
                    "INFO",
                )
            else:
                log(
                    "  ⚠️ V16.0.8 dual_api configured but fast_api_url or "
                    "fast_api_model is empty — falling back to primary "
                    "summarisation model for concept extraction",
                    "WARNING",
                )
                _provider = create_provider(
                    provider="ollama",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                _summ_model = _settings.get("summarisation.model", "gemma4-12b:latest")
                # V0.6.8 (audit B4): public attr — the "_model" guard was
                # always False (OllamaProvider exposes self.model).
                if hasattr(_provider, "model"):
                    _provider.model = _summ_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = LLM_REQUEST_TIMEOUT_S
        elif _arch == "dual_local":
            # Use the local fast model via Ollama for fast concept extraction.
            _fast_model = getattr(request, "fast_model", "") or _settings.get(
                "summarisation.fast_model", ""
            )
            if _fast_model:
                _provider = create_provider(
                    provider="ollama",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                # V0.6.8 (audit B4): public attr — the "_model" guard was
                # always False (OllamaProvider exposes self.model).
                if hasattr(_provider, "model"):
                    _provider.model = _fast_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = FAST_LLM_TIMEOUT_S  # fast model = shorter timeout
                _summ_model = _fast_model
                log(
                    f"  🚀 V16.0.8 concept extraction: dual_local mode "
                    f"(fast Ollama model = {_fast_model})",
                    "INFO",
                )
            else:
                log(
                    "  ⚠️ V16.0.8 dual_local configured but fast_model is "
                    "empty — falling back to primary summarisation model "
                    "for concept extraction",
                    "WARNING",
                )
                _provider = create_provider(
                    provider="ollama",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                _summ_model = _settings.get("summarisation.model", "gemma4-12b:latest")
                # V0.6.8 (audit B4): public attr — the "_model" guard was
                # always False (OllamaProvider exposes self.model).
                if hasattr(_provider, "model"):
                    _provider.model = _summ_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = LLM_REQUEST_TIMEOUT_S
        else:
            # single_local or single_api — primary heavy model.
            # single_local  → provider is ollama (or lmstudio/llamacpp)
            #                 → local model
            # single_api    → provider is openai_compatible   → cloud model
            # The provider is read from settings so the wizard's mode
            # choice (which sets ``summarisation.provider``) is honoured.
            _prov = _settings.get("summarisation.provider", "ollama")
            if _prov == "llamacpp":
                # V0.04: llama.cpp server — a local backend with its own
                # provider (NOT an Ollama-shaped call). The 300 s budget
                # override below does not apply: llama.cpp generates
                # stream-first (per-chunk timeout), so the provider's
                # own budget-derived timeouts govern.
                _provider = create_provider(
                    provider="llamacpp",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                _summ_model = _settings.get(
                    "summarisation.llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision"
                )
                if hasattr(_provider, "model"):
                    _provider.model = _summ_model
                log(
                    f"  🚀 V0.04 concept extraction: single_local mode "
                    f"(llama.cpp model = {_summ_model})",
                    "INFO",
                )
            elif _prov in ("ollama", "lmstudio", "fusion"):
                _provider = create_provider(
                    provider="ollama",
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                _summ_model = _settings.get("summarisation.model", "gemma4-12b:latest")
                # V0.6.8 (audit B4): public attr — the "_model" guard was
                # always False (OllamaProvider exposes self.model).
                if hasattr(_provider, "model"):
                    _provider.model = _summ_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = LLM_REQUEST_TIMEOUT_S  # 5 min for concept extraction
                log(
                    f"  🚀 V16.0.9 concept extraction: single_local mode "
                    f"(heavy local model = {_summ_model})",
                    "INFO",
                )
            else:
                # Cloud provider (openrouter / openai / openai_compatible /
                # claude / freellmapi). create_provider reads api_base_url,
                # api_key, cloud_model from settings automatically.
                _cloud_prov = "openai_compatible" if _prov not in ("claude",) else _prov
                _provider = create_provider(
                    provider=_cloud_prov,
                    settings=_settings,
                    log_callback=log,
                    supervisor=None,
                )
                _summ_model = _settings.get("summarisation.cloud_model", "gpt-4o-mini")
                # V0.6.8 (audit B4): public attr — the "_model" guard was
                # always False (OpenAICompatProvider exposes self.model).
                if hasattr(_provider, "model"):
                    _provider.model = _summ_model
                if hasattr(_provider, "timeout"):
                    _provider.timeout = LLM_REQUEST_TIMEOUT_S
                log(
                    f"  🚀 V16.0.9 concept extraction: single_api mode "
                    f"(heavy cloud model = {_summ_model})",
                    "INFO",
                )

        def _llm_call_fn(prompt):
            # V18.20.4.12 (W-a11): /no_think is now GATED on Qwen-family
            # models via the shared ``qwen_no_think`` helper — was the
            # V16.0.4 unconditional "/no_think\n\n" prefix "for ALL
            # models" (prompt pollution for non-Qwen models; the
            # directive is a Qwen3 soft-switch). The empty-response
            # nudge retry below is UNTOUCHED.
            _actual_prompt = qwen_no_think(prompt, _summ_model)
            try:
                _result = _provider.complete(
                    prompt=_actual_prompt,
                    temperature=1.0,
                    max_tokens=800,
                    model=_summ_model,
                )
                if _result and len(_result.strip()) >= 20:
                    return _result
                # V16.0.4: Retry with nudge suffix
                _nudge_prompt = _actual_prompt + "\n\nPlease output the response now."
                _result2 = _provider.complete(
                    prompt=_nudge_prompt,
                    temperature=1.0,
                    max_tokens=800,
                    model=_summ_model,
                )
                return _result2 if _result2 and len(_result2.strip()) >= 20 else None
            except Exception:
                return None

        return _llm_call_fn
    except Exception as _e:
        log(f"  ℹ️ V15.2.0: LLM-assisted concept extraction unavailable ({_e})", "DEBUG")
        return None


def _rs_build_chapter_dicts(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim V15.2.0 concept-extraction block — the
    per-segment concepts/callouts loop with the deterministic-analysis skip
    and the fail-open fallback — sets ``ctx.chapter_dicts``. The LLM factory
    moved to ``_rs_make_concept_llm_fn`` (same body, one indent shallower)."""
    log = ctx.log
    request = ctx.request
    segments_for_summary = ctx.segments_for_summary
    segments = ctx.segments
    try:
        from core.summarisation.text_preprocessor import (
            DeterministicPreprocessor,
            extract_concepts_rich,
        )

        pp = DeterministicPreprocessor()
        # V15.2.0: Build a lightweight LLM call function for Technique #5.
        # This calls the primary summarisation model with a low temp for
        # deterministic concept extraction.
        #
        # V16.0.9: 4-mode model architecture — route concept extraction to the
        # fast model when ``model_architecture`` is ``dual_local`` or
        # ``dual_api``. In ``single_local`` / ``single_api`` mode it uses the
        # primary summarisation model (local Ollama or cloud API, depending on
        # provider). Legacy ``single`` is mapped to ``single_local`` for
        # backward compat. Architecture is read from the request first
        # (per-conversion override) and then from settings as a fallback.
        _llm_call_fn = _rs_make_concept_llm_fn(ctx)
        chapter_dicts = []
        for s in segments_for_summary:
            # V17.4/V17.5: When the deterministic analysis is available (V17.2),
            # skip the LLM-assisted concept extraction (#5) AND raise the
            # concept cap from 18 to 50 (the deterministic layer found all
            # authors — don't cap them).
            #
            # V17.5 fix: uses analysis_exists() instead of fragile heading matching.
            _skip_llm_concepts = False
            _concept_cap = 18  # default
            try:
                from core.preprocessing.deterministic_analyzer import analysis_exists

                _has_analysis = analysis_exists(
                    request.output_dir,
                    log_fn=lambda msg, level="DEBUG": log(msg, level),
                )
                if _has_analysis:
                    _skip_llm_concepts = True
                    _concept_cap = 50  # V17.5: raised from 18 — don't cap authors
                    log(
                        "  📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)",
                        "INFO",
                    )
            except Exception as _e:
                log(f"  ⚠️ V17.5: analysis_exists check failed: {_e}", "WARNING")

            try:
                concepts = extract_concepts_rich(
                    s.content,
                    max_terms=_concept_cap,
                    llm_call_fn=(None if _skip_llm_concepts else _llm_call_fn),
                    log_fn=log,
                )
            except Exception as _e:
                log(
                    f"  ⚠️ V15.2.0 enhanced extraction failed ({_e}), falling back to old method",
                    "DEBUG",
                )
                try:
                    from core.summarisation.text_preprocessor import extract_all_concepts

                    concepts = extract_all_concepts(s.content)
                except Exception:
                    concepts = pp.extract_concepts(s.content)
            callouts = pp.extract_callouts(s.content)
            if concepts:
                log(
                    f"  🎯 '{s.heading[:40]}…': {len(concepts)} concepts extracted (V15.2.0 enhanced)",
                    "DEBUG",
                )
            chapter_dicts.append(
                {
                    "heading": s.heading,
                    "content": s.content,
                    "concepts": concepts,
                    "callouts": callouts,
                    # V18.3.2 (P3-partial): thread page info for page-based matching fallback.
                    "start_page": getattr(s, "start_page", None),
                    "end_page": getattr(s, "end_page", None),
                }
            )
        ctx.chapter_dicts = chapter_dicts
    except Exception as e:
        log(f"  ⚠️ Concept extraction skipped: {e}", "DEBUG")
        chapter_dicts = [
            {
                "heading": s.heading,
                "content": s.content,
                "start_page": getattr(s, "start_page", None),
                "end_page": getattr(s, "end_page", None),
            }
            for s in segments
        ]


def _rs_split_resume(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim chapter-level resume split — loads
    previously-completed chapters and narrows the todo set — sets
    ``ctx.loaded_summaries`` / ``ctx.chapter_dicts``."""
    log = ctx.log
    converter = ctx.converter
    # ── Chapter-level resume ─────────────────────────────────────────
    resume_enabled = converter.settings.get("summarisation.resume_enabled", True)
    ctx.loaded_summaries: list[SummaryResult] = []
    if resume_enabled:
        from core.pipeline.chapter_resume import (
            detect_processed_chapters,
            split_chapters_for_resume,
        )

        processed = detect_processed_chapters(converter.output_dir)
        if processed:
            todo_chapters, ctx.loaded_summaries = split_chapters_for_resume(
                ctx.chapter_dicts,
                processed,
                log,
            )
            if ctx.loaded_summaries and not todo_chapters:
                log(
                    "  ✅ All chapters already processed — skipping "
                    "summarization entirely (whole-book outputs will "
                    "still regenerate from loaded summaries).",
                    "INFO",
                )
            ctx.chapter_dicts = todo_chapters


def _rs_summarize_chapters(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim summarize block — the short-chapter
    warnings, the selected-chapter matcher with its FAIL-CLOSED
    ChapterMatchFailure, the incremental checkpoint-saver wiring, and the
    ``summarize_chapters`` call — sets ``ctx.summaries``."""
    log = ctx.log
    converter = ctx.converter
    request = ctx.request
    segments = ctx.segments
    summarizer = ctx.summarizer
    book_title = ctx.book_title
    ctx.summaries = []
    if ctx.chapter_dicts:
        # V10.24.0: Warn about very short chapters (< 200 tokens)
        # These produce garbage summaries because the LLM doesn't have enough
        # source text to work with.
        for _cd in ctx.chapter_dicts:
            try:
                from utils.token_counter import count_tokens

                _tok = count_tokens(_cd.get("content", ""))
                if _tok < 200:
                    log(
                        f"  ⚠️ Chapter '{_cd.get('heading', '?')[:40]}' is very short "
                        f"({_tok} tokens) — summary quality may be poor.",
                        "WARNING",
                    )
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
        _selected_count = len(request.selected_chapters) if request.selected_chapters else 0
        _to_summarize = len(ctx.chapter_dicts)
        log(
            f"📚 Summarising {_to_summarize} chapter(s) with {request.max_workers} worker(s)...",
            "INFO",
        )
        for _ci, _cd in enumerate(ctx.chapter_dicts, 1):
            log(
                f"  📖 Chapter {_ci}/{len(ctx.chapter_dicts)}: "
                f"'{_cd['heading'][:50]}' ({len(_cd['content'])} chars)",
                "INFO",
            )
        if request.selected_chapters:
            log(f"  🎯 User selected: {request.selected_chapters}", "INFO")
        if _selected_count > 0 and _to_summarize > _selected_count:
            log(
                f"  ⚠️ WARNING: User selected {_selected_count} chapter(s) "
                f"but {_to_summarize} are being summarized. "
                f"This may indicate a segmentation issue. "
                f"Chapters: {[cd['heading'][:40] for cd in ctx.chapter_dicts]}",
                "WARNING",
            )
            _selected_titles = request.selected_chapters or []
            # V18.3.1 (P0): capture the available headings BEFORE filtering,
            # so the ChapterMatchFailure error can list what segments exist.
            _all_available_headings = [cd["heading"] for cd in ctx.chapter_dicts]
            # V18.3.3 (F4): use the unified ChapterMatcher — replaces the
            # inline heading-text + page-based logic. This is the SAME matcher
            # used by Stage 1 (segmentation), so the two stages now agree.
            from core.segmentation.chapter_matcher import ChapterMatcher

            _matcher = ChapterMatcher(
                toc_entries=getattr(converter, "toc_entries", []) or [],
            )
            _matched = _matcher.match(
                _selected_titles,
                ctx.chapter_dicts,
                max_results=len(_selected_titles) if _selected_titles else None,
            )
            ctx.chapter_dicts = [seg for _, seg in _matched]
            log(
                f"  ✂️ Selected best {len(ctx.chapter_dicts)} match(es): "
                f"{[cd['heading'][:40] for cd in ctx.chapter_dicts]}",
                "INFO",
            )

            # V18.3.1 (P0 hotfix) + V18.3.2 (page fallback) + V18.3.3 (F4 unified):
            # FAIL-CLOSED — if the user selected chapters but the unified matcher
            # (heading-text + aliases + page-based) found 0 matches, ABORT with
            # an actionable error instead of silently producing an empty summary.
            if _selected_titles and not ctx.chapter_dicts:
                from core.errors import ChapterMatchFailure

                _sel_preview = [t[:50] for t in _selected_titles[:3]]
                _avail_preview = [h[:50] for h in _all_available_headings[:8]]
                _msg = (
                    f"Chapter selection matched 0 of {len(_all_available_headings)} segments "
                    f"(heading + aliases + page fallback all failed). "
                    f"User selected: {_sel_preview}. "
                    f"Available segments: {_avail_preview}. "
                    f"This usually means the segmenter produced unexpected headings. "
                    f"Fix: pick a chapter title from the Available list above, or re-run without chapter selection."
                )
                log(f"  🚫 FATAL: {_msg}", "ERROR")
                raise ChapterMatchFailure(
                    _msg,
                    selected=_selected_titles,
                    available=_all_available_headings,
                )
        _thermal_cb = None
        if ctx.thermal_safety is not None:
            _thermal_cb = ctx.thermal_safety.wait_if_paused
        # ── V18.20.3.0: incremental chapter checkpointing ───────────────
        # Compute each todo chapter's FINAL position in the merged
        # (loaded + new) summary list UP FRONT — positions are the segment
        # order restricted to segments that will have summaries — so the
        # checkpoint files written mid-run carry the same numbering the
        # end-of-run writer produces, and resume numbering stays stable.
        # V0.6.6: duplicate headings are excluded from the map (see
        # compute_final_positions) — they fall back to the saver's
        # per-run chapter index so no chapter is ever lost to a filename
        # collision.
        _todo_headings = {cd["heading"] for cd in ctx.chapter_dicts}
        _loaded_headings = {s.chapter_heading for s in ctx.loaded_summaries}
        _final_positions = compute_final_positions(segments, _todo_headings, _loaded_headings)
        _cp_saver = None
        if converter.settings.get("summarisation.incremental_chapter_save", True):
            from core.pipeline.chapter_checkpoint import ChapterCheckpointSaver

            _cp_saver = ChapterCheckpointSaver(
                converter,
                heading_positions=_final_positions,
                chapters_total=len(ctx.chapter_dicts) + len(ctx.loaded_summaries),
                build_docx=bool(getattr(request, "generate_docx", False)),
                book_title=book_title,
            )
            log(
                "  🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — "
                "each chapter (summary + DOCX) is saved the moment it "
                "completes; a crash/cancel never loses finished chapters.",
                "INFO",
            )
        ctx.summaries = summarizer.summarize_chapters(
            ctx.chapter_dicts,
            progress_callback=converter._summarisation_progress,
            cancel_event=converter.cancel_event,
            thermal_pause_callback=_thermal_cb,
            chapter_done_callback=(_cp_saver.on_chapter_done if _cp_saver is not None else None),
        )


def _rs_merge_loaded_summaries(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim loaded+new merge — re-orders the merged
    list by segment order — updates ``ctx.summaries``."""
    log = ctx.log
    segments = ctx.segments
    # ── Merge loaded + new summaries ────────────────────────────────
    if ctx.loaded_summaries:
        from core.pipeline.chapter_resume import merge_summaries

        all_headings = [s.heading for s in segments]
        ctx.summaries = merge_summaries(ctx.summaries, ctx.loaded_summaries, all_headings)
        log(
            f"  📂 Merged {len(ctx.loaded_summaries)} loaded + "
            f"{len(ctx.summaries) - len(ctx.loaded_summaries)} new summaries",
            "INFO",
        )


def _rs_write_book_summary(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim book-summary block — the build, the
    V18.20.3.7 provenance stamp + visible footer, the atomic write, and the
    V0.4.25 run-stamped copy."""
    log = ctx.log
    converter = ctx.converter
    book_title = ctx.book_title
    summarizer = ctx.summarizer
    summaries = ctx.summaries
    if converter.settings.get("summarisation.include_book_summary", True):
        # V0.03 (P1-6): collect the ACTUAL aggregated bullet count — the
        # provenance stamp previously passed len(summaries) (the CHAPTER
        # count) as "bullets=N", stamping bullets=2 on a 70-bullet book.
        _bk_stats: dict = {}
        book_summary = summarizer.build_book_summary(summaries, book_title, stats=_bk_stats)
        _bk_bullet_count = _bk_stats.get("bullets") or sum(
            len(s.bullet_points or []) for s in summaries
        )
        # V18.20.3.7: provenance stamp — the book-level summary names the
        # app version + run id that produced it (same self-identification
        # the chapter summaries carry; no sentinel — this file is always
        # regenerated).
        try:
            from core.system.provenance import (
                get_app_version,
                make_run_id,
                provenance_comment,
                run_started_iso,
                visible_footer,
            )

            _first_stamped = next(
                (s for s in summaries if getattr(s, "run_id", "")),
                None,
            )
            _bk_rid = getattr(_first_stamped, "run_id", "") or make_run_id()
            _bk_started = getattr(_first_stamped, "run_started", "") or run_started_iso()
            _bk_ver = getattr(_first_stamped, "app_version", "") or get_app_version()
            _bk_prov = provenance_comment(
                _bk_ver,
                _bk_rid,
                _bk_started,
                _bk_bullet_count,  # V0.03: real bullet count
            )
            if not book_summary.startswith("<!--"):
                book_summary = f"{_bk_prov}\n\n{book_summary}"
            # V18.20.4.3 (P2 / G-3, the F8 follow-up): visible footer on
            # the book summary too — the comment stamp alone is invisible
            # in rendered markdown, which is how stale artifacts from old
            # app-version folders pass a casual glance.
            book_summary = f"{book_summary.rstrip()}\n{visible_footer(_bk_ver, _bk_rid, _bk_started, _bk_bullet_count)}"  # V0.03: real bullet count
        except Exception as _e:
            # V0.4.27 (Phase-5 P1 / W3-E1, audit backlog): surface the
            # silent Rule-4 violation — a failure here ships an UNSTAMPED
            # book summary with no log at all. The write still proceeds
            # (stamping must never break it), but the WARNING makes the
            # defect visible + traceable via the structured-log handler.
            log_swallow(
                "stamp_book_summary_provenance",
                _e,
                level=logging.WARNING,
                detail=f"book={getattr(converter, 'summary_md_path', '?')}",
            )
        # V18.20.2.0 (SWOT A30): atomic write (same-dir temp + fsync +
        # os.replace) — a crash mid-write previously left a truncated
        # Book.summary.md on disk.  ``atomic_write_text`` creates the
        # parent dir (replaces the ``_ensure`` call) and keeps utf-8.
        atomic_write_text(converter.summary_md_path, book_summary)
        log(f"📋 Book summary → {converter.summary_md_path}")
        # V0.4.25: run-stamped COPY of the book summary — the canonical
        # ``{stem}.summary.md`` stays stable for every consumer (output
        # scanner, validator, translation lookup, multi-PDF merge), while
        # the stamped sibling is the unique, attach-without-cache-collision
        # artifact for the operator's audits. Same content, both written.
        try:
            from core.system.provenance import run_stamp_suffix

            _bk_stamp = run_stamp_suffix(_bk_ver, _bk_rid)
            if _bk_stamp:
                _stamped_summary_path = converter.summary_md_path.with_name(
                    converter.summary_md_path.stem + _bk_stamp + ".summary.md"
                )
                atomic_write_text(_stamped_summary_path, book_summary)
                log(f"💎 Run-stamped copy → {_stamped_summary_path.name}")
        except Exception:  # pragma: no cover — the stamped copy must never break the save
            pass


def _rs_finalize(ctx: _SummCtx) -> None:
    """V0.6.11 (B14-a): the verbatim finalize block — the 0.80 progress, the
    cancel-leaves-checkpoint-pending contract (SWOT A15), the judge_results
    stash + Layer-8 count, and the best-effort torch VRAM cleanup."""
    log = ctx.log
    converter = ctx.converter
    summarizer = ctx.summarizer
    summaries = ctx.summaries
    update_progress = ctx.update_progress
    update_progress(0.80)  # Summaries done
    # V18.20.2.0 (SWOT A15): a cancelled run must NOT mark the
    # summarization phase checkpoint-done on PARTIAL state —
    # ``Checkpoint.should_run``/``is_done`` would make a resume skip
    # summarization entirely with an incomplete chapter set.  Leave the
    # phase pending: the chapter-resume sentinels (<!-- COMPLETE -->)
    # already record which chapters genuinely finished, so a re-run
    # resumes at the right chapter.
    if converter.cancel_event.is_set():
        log(
            "  ⏹️ Cancelled — summarization checkpoint left pending "
            "(partial state, resume will re-enter this phase)",
            "INFO",
        )
    else:
        converter.checkpoint.mark_done("summarization", chapters=len(summaries))

    # Stash judge_results for downstream outputs.
    converter._judge_results = list(getattr(summarizer, "judge_results", []))
    if converter._judge_results:
        _l8_active = sum(
            1
            for jr in converter._judge_results
            if jr and getattr(jr, "grounding_layer8_available", False)
        )
        if _l8_active:
            log(
                f"  🛡️ Layer 8 grounding ran for {_l8_active}/"
                f"{len(converter._judge_results)} chapter(s)",
                "INFO",
            )

    # V10.33.0 (Sprint 5.6): Free GPU VRAM between phases.
    # After summarization completes, the LLM model is still loaded.  Calling
    # torch.cuda.empty_cache() releases the unused KV cache memory so the
    # next phase (translation / TTS / output generators) has maximum VRAM
    # available.  This prevents OOM on 12GB cards when chaining LLM-heavy
    # phases.  Best-effort — never crashes if torch is unavailable.
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            log("  🧹 VRAM cache cleared (torch.cuda.empty_cache)", "DEBUG")
    except ImportError:
        pass
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)  # never crash on VRAM cleanup


def run_summarization(
    converter: Any,
    segments: list[Any],
    segments_folder: Any,
    detected_lang: str,
    book_title: str,
    elapsed_fn: Any,
) -> SummarizationResult | ConversionResult:
    """Run the summarization phase (Step 9).

    Args:
        converter: the Converter instance (accessed for ``self.request``,
            ``self._log``, ``self._update_status``, ``self._update_progress``,
            ``self.settings``, ``self.output_dir``, ``self.paths``,
            ``self.checkpoint``, ``self.cancel_event``,
            ``self._filter_segment_content``, ``self._match_chapter``,
            ``self._summarisation_progress``, ``self._sanitize_filename``,
            ``self._build_error_result``, ``self.summary_md_path``).
        segments: the segment list (from segmentation phase).
        segments_folder: the folder where segment files were saved (used
            for the summaries subfolder).
        detected_lang: the detected language code (from output_save phase).
        book_title: the detected book title (from output_save phase).
        elapsed_fn: a callable returning the elapsed-time string (the
            converter's ``_elapsed`` closure timer).  Called once at the
            start of the phase for the "Summary phase starting" log line.

    Returns:
        ``SummarizationResult`` (summaries) on success, or
        ``ConversionResult`` (success=False) on early exit.

    V0.6.11 (B14-a): the body is now the phase sequence behind ``_SummCtx``
    (unload-VRAM → content filter → reference-skip → claim extractor → GPU
    profile → thermal safety → summarizer init → glossary handoff → chapter
    dicts → resume split → summarize → merge → save → book summary →
    finalize) — the public signature, the call/statement ORDER, and every
    moved block are unchanged (AST-identity pinned by
    tests/test_v0611_wave7_godfunction_decomp.py).
    """
    ctx = _SummCtx(
        converter=converter,
        segments=segments,
        segments_folder=segments_folder,
        detected_lang=detected_lang,
        book_title=book_title,
        elapsed_fn=elapsed_fn,
        log=converter._log,
        update_status=converter._update_status,
        update_progress=converter._update_progress,
        request=converter.request,
    )
    log = ctx.log
    update_status = ctx.update_status
    update_progress = ctx.update_progress
    request = ctx.request

    if not request.generate_summaries:
        return SummarizationResult(summaries=ctx.summaries)

    if converter.cancel_event.is_set():
        return ConversionResult(success=False, error_msg="Cancelled by user")

    update_status("Generating summaries…")
    log(f"  ⏱️ Summary phase starting | [{elapsed_fn()}]", "INFO")
    update_progress(0.25)  # Summary phase starts here (0.25-0.80)

    _rs_unload_ocr_vram(ctx)
    # ── Determine summary language ───────────────────────────────────
    lang_setting = converter.settings.get("summarisation.language", "auto")
    ctx.summary_lang = detected_lang if lang_setting == "auto" else lang_setting
    _rs_apply_content_filter(ctx)
    _rs_filter_reference_sections(ctx)
    _rs_build_claim_extractor(ctx)
    _rs_detect_gpu_profile(ctx)
    _error = _rs_start_thermal_safety(ctx)
    if _error is not None:
        return _error
    _rs_init_summarizer(ctx)
    _rs_thread_glossary_handoff(ctx)
    _rs_build_chapter_dicts(ctx)
    _rs_split_resume(ctx)
    _rs_summarize_chapters(ctx)
    _rs_merge_loaded_summaries(ctx)
    _save_chapter_summaries_write_once(converter, segments, ctx.summaries, log)
    _rs_write_book_summary(ctx)
    _rs_finalize(ctx)
    return SummarizationResult(summaries=ctx.summaries)
