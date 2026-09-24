"""V18.12 (Phase 5 Stage 3, Batch 2.7): Concept gap-fill.

Extracted verbatim from ``Summarizer._gap_fill_concepts`` (god-class
decomposition Stage 3). Detects uncovered concepts and makes targeted LLM
calls to fill them; also runs the V17.3 deterministic judge for author coverage.

**Extraction map**:

| Summarizer method (old) | gap_filler function (new) | self deps |
|------------------------|--------------------------|-----------|
| ``_gap_fill_concepts``  | ``gap_fill_concepts``    | ``request.output_dir``, ``log``, ``_recover_vram``, ``prompt_manager``, ``_call_fast_llm``, ``_strip_thinking``, ``_switch_to_fast_model``, ``overdeliver_enabled``, ``overdeliver_target``, ``coverage_threshold``, ``_effective_target``, ``temperature`` |

**Mutable-state handling**: ``self._last_coverage`` is mutated at the end of
the method (set to the post-gap-fill coverage %). The extracted function takes
``last_coverage`` as a parameter and returns the (possibly updated) new value
alongside the extended bullets — but to keep the signature simple and match the
original return type (``List[str]``), the function instead takes a
``set_last_coverage`` callback that the delegate uses to set
``self._last_coverage``. This preserves the original's return type (just the
bullets list) and the side-effect (``self._last_coverage`` updated).

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1-2 pattern.

Characterization tests: ``tests/test_gap_filler.py`` captures the
analysis-skip path, coverage-threshold-skip path, concept gap-fill, and
deterministic-judge paths with mocked ``call_fast_llm`` / ``prompt_manager``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from utils.error_trace import log_swallow

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
PromptManagerLike = Any
CallFastLlmFn = Callable[..., str | None]
RecoverVramFn = Callable[..., None]
StripThinkingFn = Callable[[str], str]
SwitchToFastModelFn = Callable[[], None]
SetLastCoverageFn = Callable[[float], None]
CheckCoverageFn = Callable[[Any, str], dict]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── gap_fill_concepts (extracted verbatim) ─────────────────────────────────


def gap_fill_concepts(
    heading: str,
    content: str,
    bullets: list[str],
    concepts: list[str],
    exec_summary: str,
    thorough_summary: str,
    *,
    output_dir: Any,
    temperature: float,
    effective_target: float,
    overdeliver_enabled: bool,
    overdeliver_target: float,
    coverage_threshold: float,
    prompt_manager: PromptManagerLike,
    recover_vram: RecoverVramFn,
    call_fast_llm: CallFastLlmFn,
    strip_thinking: StripThinkingFn,
    switch_to_fast_model: SwitchToFastModelFn,
    set_last_coverage: SetLastCoverageFn,
    log: LogCallback | None = None,
) -> list[str]:
    """V3.2.0 C2: Detect uncovered concepts and make a targeted LLM call.

    F2: Now builds a concept coverage matrix before gap-filling.
    Checks each concept against ALL summary sections (exec, bullets, thorough),
    not just bullets. Only gap-fills concepts that are truly missing from
    ALL sections.

    Extracted verbatim from ``Summarizer._gap_fill_concepts``. The only
    changes are ``self.X`` → named parameters. The V17.4/V17.5 early-skip when
    deterministic analysis exists, the V13.37.0 whitespace-normalized coverage
    matrix, the V13.40.5 coverage-threshold skip (with V15.1.0 over-deliver
    target), the 30s VRAM recovery, the V15.2.0 12-concept cap, the V17.1.2
    routing to fast model, the V16.0.4 post-gap-fill coverage matrix (sets
    ``self._last_coverage`` via the ``set_last_coverage`` callback), and the
    V17.3 deterministic author-coverage judge with targeted gap-fill for
    missing authors are byte-for-byte identical.
    """
    log = log or _noop_log
    if not concepts or not bullets:
        return bullets

    # V17.4/V17.5: If the deterministic analysis is available, skip the old
    # sequential gap-fill entirely. The V17.3 deterministic judge (which
    # runs at the END of this method) will handle gap-filling with
    # pre-located source sentences — much faster and more accurate.
    #
    # V17.5 fix: uses analysis_exists() instead of fragile heading matching.
    try:
        from core.preprocessing.deterministic_analyzer import analysis_exists

        _has_analysis = analysis_exists(
            output_dir,
            log_fn=lambda msg, level="DEBUG": log(msg, level),
        )
        if _has_analysis:
            log(
                "    \U0001f4ca V17.4: Deterministic analysis found \u2014 "
                "skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)",
                "INFO",
            )
            return bullets
    except Exception as _e:
        log(f"    \u26a0\ufe0f V17.5: analysis_exists check failed: {_e}", "WARNING")

    # Build concept coverage matrix
    # V13.37.0: Normalize whitespace before matching. The old code used a
    # naive substring match (concept.lower() in summary.lower()) which
    # failed when concepts contained newlines (e.g. "Nai\nB" from PDF table
    # extraction) or when the summary used different whitespace. Now we
    # normalize all whitespace to single spaces on both sides.
    all_summary_text = f"{exec_summary} {' '.join(bullets)} {thorough_summary}"
    all_summary_norm = re.sub(r"\s+", " ", all_summary_text).strip().lower()
    covered = []
    uncovered = []
    for concept in concepts:
        # Normalize the concept the same way (newlines → spaces)
        concept_norm = re.sub(r"\s+", " ", concept).strip().lower()
        if not concept_norm:
            continue  # skip empty/garbage concepts
        if concept_norm in all_summary_norm:
            covered.append(concept)
        else:
            uncovered.append(concept)

    # Log the coverage matrix
    if concepts:
        matrix_lines = []
        for c in concepts:
            status = "\u2705" if c in covered else "\u274c"
            # Find where it's covered
            locations = []
            if c.lower() in exec_summary.lower():
                locations.append("exec")
            if c.lower() in " ".join(bullets).lower():
                locations.append("bullets")
            if c.lower() in thorough_summary.lower():
                locations.append("thorough")
            loc_str = "/".join(locations) if locations else "MISSING"
            matrix_lines.append(f"    {status} {c} \u2192 {loc_str}")
        log(
            f"    \U0001f4cb Concept coverage matrix ({len(covered)}/{len(concepts)} covered):\n"
            + "\n".join(matrix_lines),
            "DEBUG",
        )

    if not uncovered:
        log(f"    \u2705 All {len(concepts)} concepts covered \u2014 no gap-fill needed", "DEBUG")
        return bullets

    # V13.40.5: Skip gap-fill when coverage is already >= threshold.
    # The V13.40.4 condition (<=25% uncovered) was too strict — even at 92%
    # coverage with 77% uncovered concepts, gap-fill shouldn't run because:
    # 1. The uncovered concepts are mostly garbage (PDF table artifacts)
    # 2. The GPU is exhausted after B4 + B3 — gap-fill will return empty
    # 3. The coverage is already good — the summary is factually accurate
    _current_coverage = len(covered) / len(concepts) if concepts else 1.0
    # V15.1.0: Use _effective_target (over-delivery target when enabled).
    # Gap-fill keeps running until we reach the over-delivery target (92%
    # by default), not just the minimum threshold (85%). The "most are
    # likely garbage" comment from V13.40.5 is now gated behind a check
    # that only applies when NOT over-delivering.
    if _current_coverage >= effective_target:
        _od_note = ""
        if overdeliver_enabled and overdeliver_target > coverage_threshold:
            _od_note = f" (over-deliver target {overdeliver_target:.0%})"
        log(
            f"    \u23ed\ufe0f Gap-fill skipped \u2014 coverage {_current_coverage:.0%} \u2265 {effective_target:.0%}"
            f"{_od_note}",
            "INFO",
        )
        return bullets

    # V13.40.4: Increased VRAM recovery from 10s → 30s. The 10s delay was
    # insufficient after 28+ minutes of continuous GPU load (B4 + additive
    # followup + self-review). 30s gives the GPU more time to cool and
    # Ollama more time to reload the model properly.
    recover_vram(context="pre-gap-fill", delay_sec=30.0)

    log(
        f"    \U0001f50d Gap-fill: {len(uncovered)}/{len(concepts)} concepts uncovered: "
        f"{uncovered[:5]}\u2026{'\u2026' if len(uncovered) > 5 else ''}",
        "INFO",
    )

    # Find source sentences for each uncovered concept
    sentences = re.split(r"(?<=[.!?])\s+", content)
    gap_bullets = []
    for _gi, concept in enumerate(
        uncovered[:12]
    ):  # V15.2.0: raised cap 8→12 (better concepts worth filling)
        # V15.1.0: VRAM recovery between gap-fill calls (from V15.0.2).
        if _gi > 0:
            recover_vram(context=f"gap-fill-{_gi + 1}", delay_sec=30.0)
        # Find sentences containing this concept
        concept_lower = concept.lower()
        relevant = [s.strip() for s in sentences if concept_lower in s.lower()][:3]
        if not relevant:
            continue

        # Build a targeted prompt
        context = " ".join(relevant)[:800]
        prompt = prompt_manager.render_template(
            "summarisation/gap_fill_concept",
            heading=heading,
            concept=concept,
            context=context,
        )

        # V17.1.2: Route gap-fill to the FAST model per the task delegation table.
        # Gap-fill is a simple paraphrasing task (write one bullet for an
        # uncovered concept given the source sentence) — the fast model
        # handles it well and saves the heavy model's VRAM/attention for
        # B4/synthesis/judge. In single_local/single_api mode, _call_fast_llm
        # routes back to the heavy model automatically (no behaviour change).
        try:
            # On the first call, switch VRAM to the fast model. Subsequent
            # calls already have the fast model loaded — the gap-fill loop's
            # own 30s VRAM recovery between calls handles any contention.
            if _gi == 0:
                switch_to_fast_model()
            raw = call_fast_llm(
                prompt,
                max_tokens=200,
                temperature=temperature,
            )
        except Exception as _gfe:
            log(
                f"    \u26a0\ufe0f Gap-fill call {_gi + 1} crashed "
                f"({type(_gfe).__name__}: {_gfe}) \u2014 skipping concept "
                f"'{concept[:40]}'",
                "WARNING",
            )
            logger.warning("Gap-fill call %d crashed: %s: %s", _gi + 1, type(_gfe).__name__, _gfe)
            raw = None
        if raw:
            # Clean up the response
            gap_bullet = strip_thinking(raw).strip()
            # Remove leading "- " if the model added it
            gap_bullet = re.sub(r"^[-\d.\s]+", "", gap_bullet).strip()
            # Remove surrounding quotes if present
            gap_bullet = gap_bullet.strip("\"'")
            if gap_bullet and 10 < len(gap_bullet) < 300:
                gap_bullets.append(gap_bullet)

    if gap_bullets:
        log(f"    \u2705 Gap-fill: added {len(gap_bullets)} bullets for uncovered concepts", "INFO")
        bullets.extend(gap_bullets)
    else:
        log(
            "    \u2139\ufe0f Gap-fill: no bullets generated (LLM returned nothing useful)", "DEBUG"
        )

    # V16.0.4: Post-gap-fill coverage matrix
    try:
        _post_summary = f"{exec_summary} {' '.join(bullets)} {thorough_summary}"
        _post_norm = re.sub(r"\s+", " ", _post_summary).strip().lower()
        _post_covered = sum(
            1 for c in concepts if re.sub(r"\s+", " ", c).strip().lower() in _post_norm
        )
        _post_pct = _post_covered / len(concepts) if concepts else 1.0
        log(
            f"    \U0001f4cb V16.0.4 Post-gap-fill coverage: {_post_covered}/{len(concepts)} ({_post_pct:.0%})",
            "INFO",
        )
        set_last_coverage(_post_pct)
    except Exception as _e:
        # V18.2.14 (B4): was silent ``pass`` — now traceable.
        log_swallow("post_gapfill_coverage_check", _e)

    # V17.3: Deterministic judge — check if gemma covered all the
    # authors/theorists that the deterministic layer found.
    # This is a 100%-reliable regex check (not LLM-based).
    # If gaps are found, they're added to the bullets via targeted gap-fill.
    # V17.5 fix: uses find_analysis_for_heading() instead of fragile heading matching.
    try:
        from core.preprocessing.deterministic_analyzer import (
            check_coverage,
            extract_authors_from_analysis,
            find_analysis_for_heading,
        )

        _seg_path, _analysis = find_analysis_for_heading(
            output_dir,
            heading,
            log_fn=lambda msg, level="DEBUG": log(msg, level),
        )
        if _analysis:
            _det_authors = extract_authors_from_analysis(_analysis)
            if _det_authors:
                # Check coverage
                _full_summary = f"{exec_summary} {' '.join(bullets)} {thorough_summary}"
                _cov = check_coverage(_analysis, _full_summary)
                _missing = _cov["missing"]
                _total = _cov["total"]
                _pct = _cov["coverage_pct"]
                log(
                    f"    \U0001f4ca V17.3 Deterministic judge: {_cov['covered']}/{_total} "
                    f"authors covered ({_pct:.0%})"
                    + (
                        f" \u2014 MISSING: {_missing[:5]}"
                        if _missing
                        else " \u2014 ALL COVERED \u2705"
                    ),
                    "INFO",
                )
                # If authors are missing, do targeted gap-fill for them
                # V17.9: raised cap from 12 to 20
                if _missing and len(_missing) <= 20:
                    log(
                        f"    \U0001f50d V17.3: Gap-filling {len(_missing)} missing authors: "
                        f"{_missing[:5]}\u2026{'\u2026' if len(_missing) > 5 else ''}",
                        "INFO",
                    )
                    # Find source sentences for each missing author
                    _sentences = re.split(r"(?<=[.!?])\s+", content)
                    for _author in _missing[:8]:  # cap at 8
                        _author_lower = _author.lower()
                        _relevant = [s.strip() for s in _sentences if _author_lower in s.lower()][
                            :3
                        ]
                        if not _relevant:
                            continue
                        _context = " ".join(_relevant)[:800]
                        _gap_prompt = prompt_manager.render_template(
                            "summarisation/gap_fill_concept",
                            heading=heading,
                            concept=_author,
                            context=_context,
                        )
                        if _gap_prompt:
                            try:
                                _raw = call_fast_llm(
                                    _gap_prompt,
                                    max_tokens=200,
                                    temperature=temperature,
                                )
                                if _raw:
                                    _gap_bullet = strip_thinking(_raw).strip()
                                    _gap_bullet = re.sub(r"^[-\d.\s]+", "", _gap_bullet).strip()
                                    _gap_bullet = _gap_bullet.strip("\"'")
                                    if _gap_bullet and 10 < len(_gap_bullet) < 300:
                                        bullets.append(f"- {_gap_bullet}")
                                        log(
                                            f"    \u2705 V17.3: Added gap-fill for '{_author}'",
                                            "INFO",
                                        )
                            except Exception as _e:
                                # V18.2.14 (B4): was silent ``pass`` — now traceable.
                                log_swallow(
                                    "gap_fill_concept_individual", _e, detail=f"author={_author}"
                                )
        else:
            log(
                "    [V17.5] No analysis found for judge \u2014 skipping deterministic coverage check",
                "DEBUG",
            )
    except Exception as _e:
        log(f"    \u26a0\ufe0f V17.5: Deterministic judge failed: {_e}", "WARNING")

    return bullets


__all__ = [
    "gap_fill_concepts",
    "LogCallback",
]
