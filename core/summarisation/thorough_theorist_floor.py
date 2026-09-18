"""V18.20.4.7 (P5 phase 2 / O-a2): the thorough-theorist floor — a
Summarizer mixin.

The V18.20.3.13 (Phase 5 / W7+O3) thorough gap-fill machinery — exactly one
runtime method, ``_thorough_theorist_floor`` — moved out of the ~5.2k-line
``summarizer.py`` monolith into this module, re-homed via the mixin
pattern (``Summarizer`` inherits ``SummarizerThoroughFloorMixin``). The
call site (``thorough = self._thorough_theorist_floor(...)``) stays in
``_summarize_inner`` — that orchestrator is explicitly NOT moved (out of
the approved P5 scope).

VERBATIM CONTRACT: the method body is byte-identical to the V18.20.4.6
zip's ``summarizer.py`` (``ast.get_source_segment`` comparison in
``tests/test_v182047_p5_core_decomp.py``). Only this module's imports +
docstring are new.
"""
from __future__ import annotations

import re

from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()


class SummarizerThoroughFloorMixin:
    """Thorough-theorist floor for :class:`Summarizer` (see the module
    docstring). The method body is byte-identical to summarizer.py's."""

    def _thorough_theorist_floor(
        self,
        heading: str,
        content: str,
        thorough: str,
        analysis: str,
        scaled_target_hi: int | None = None,
    ) -> str:
        """V18.20.3.13 (Phase 5 / W7+O3): thorough-theorist floor + ONE targeted gap-fill.

        Why this exists (the .3.7 SWOT W7 gap, approved as O3 for this
        phase): the recall floor (V18.20.3.4) guarantees theorist coverage
        in the BULLETS, and the V18.14 thorough-only judge line is purely
        informational — when the thorough missed theorists, nothing
        repaired it and nothing enforced a floor. This method (a) measures
        the floor on the FINAL thorough text with the same
        ``check_coverage(analysis, text)`` machinery the thorough-only
        judge uses, (b) logs it in the recall-floor house style (INFO when
        met / WARNING when not), and (c) when authors are missing, the
        deadline allows it, and the thorough is non-trivial, fires exactly
        ONE targeted LLM call (``_call_llm_with_empty_retry`` — one logical
        call per the O3 design) asking for 1-2 flowing paragraphs that
        weave in ONLY the missing contributors, source-grounded, appended
        to the thorough. After the append it re-runs the coverage check and
        logs the honest before/after line.

        Book-agnostic (.3.9 standing rule): the missing-author list comes
        from the RUNTIME deterministic analysis passed in as ``analysis``
        (the same ``find_analysis_for_heading`` result the recall floor
        uses) — no author/theorist/person name is hardcoded here, and the
        names only ever flow from analysis → prompt at runtime.

        Fail-soft (house pattern): any crash logs a WARNING and the
        original thorough is returned unchanged — the chapter is never
        broken by the floor itself.

        Args:
            heading: chapter heading (prompt context).
            content: chapter source text (prompt grounding, clamped).
            thorough: the FINAL thorough summary text.
            analysis: the deterministic analysis text for this chapter
                (``_analysis_rf`` from the caller — "" disables the floor,
                same as the recall floor's no-analysis behaviour).

        Returns:
            The thorough text — with the gap-fill paragraphs appended when
            the one targeted call succeeded, otherwise the original.
        """
        try:
            if not analysis or not (thorough or "").strip():
                # Nothing measurable — the recall-floor house style logs
                # nothing when there is no analysis (theorist list) to
                # measure against.
                return thorough
            from core.preprocessing.deterministic_analyzer import check_coverage
            _cov = check_coverage(analysis, thorough)
            _total = _cov.get("total") or 0
            if not _total:
                return thorough
            _covered = len(_cov.get("covered", []) or [])
            _missing = list(_cov.get("missing", []) or [])
            # V18.20.3.13 floor line — recall-floor house style (INFO when
            # met / WARNING when not; missing names listed like the V18.14
            # judge lists them so the operator can act without re-running).
            self.log(
                f"    🎯 V18.20.3.13 Thorough theorist floor: {_covered}/{_total} authors in thorough"
                + (
                    f" — MISSING from thorough: {_missing[:5]}"
                    if _missing else " — ALL IN THOROUGH ✅"
                ),
                "INFO" if not _missing else "WARNING",
            )
            if not _missing:
                return thorough
            # ── Repair decision (O3: one targeted call, deadline-gated) ──
            # The deadline check itself logs the honest "skipping optional
            # phase" WARNING when exceeded, so the floor line above stays
            # the recorded verdict and the repair simply does not fire.
            if self._deadline_exceeded("thorough theorist floor gap-fill"):
                return thorough
            _tf_words = len((thorough or "").split())
            # V0.05 (rig audit F9b): BUDGET GATE — the 150-300-word append is
            # skipped when the thorough already meets its SOURCE-SCALED target
            # (``scaled_target_hi`` from length_policy.thorough_target). The
            # V0.04 rig's short chapters were padded past their sources by
            # exactly this append; a summary section never grows beyond its
            # scaled ceiling to chase a name that the bullets already carry.
            if scaled_target_hi is not None and _tf_words >= int(scaled_target_hi):
                self.log(
                    f"    ⏭️  V0.05: Thorough gap-fill skipped — thorough "
                    f"({_tf_words} words) already meets its source-scaled "
                    f"target ({scaled_target_hi} words); the missing "
                    f"contributor(s) are covered by the bullets/recall floor",
                    "INFO",
                )
                return thorough
            if _tf_words < 50:
                # A stub thorough (empty/exec-copy/degenerate) cannot be
                # safely extended with "continuation" prose — report and
                # leave the floor verdict as the honest record.
                self.log(
                    f"    ⏭️  V18.20.3.13: Thorough gap-fill skipped — thorough "
                    f"too short ({_tf_words} words) to extend; floor stays "
                    f"{_covered}/{_total}",
                    "INFO",
                )
                return thorough
            # ── ONE targeted gap-fill call (the O3 design — no loops) ──
            # Source clamp mirrors the dedicated-thorough prompt
            # (prompt_assembly: ~40k chars); the thorough TAIL (~4k chars,
            # the exec-from-thorough prompt's thorough cap) gives the model
            # the prose style to match without re-sending the whole field.
            _source = (content or "")[:40000]
            _tail = (thorough or "")[-4000:]
            _names = ", ".join(_missing)
            _lang = (
                "Write in Persian (Farsi)."
                if self.language == "fa" else "Write in English."
            )
            # V18.20.3.13: inline f-string prompt (the same ROLE/CONTEXT/
            # TASK/CONSTRAINTS/INPUT shape the prompt_assembly helpers
            # use) — no new prompt FILE; every name in it arrives at
            # runtime from the deterministic analysis.
            _prompt = f"""### ROLE ###
You are a senior academic summarizer. Your task is to write a short prose addition to an existing thorough summary. {_lang}

### CONTEXT ###
Chapter: "{heading}"

The final paragraphs of the existing thorough summary (for style matching only):
<thorough_tail>
{_tail}
</thorough_tail>

### TASK ###
The thorough summary above does not yet mention every named contributor from the chapter. Write ONE to TWO flowing paragraphs (roughly 150-300 words) that weave in ONLY the contributors listed below, each with their SPECIFIC contribution as described in the chapter source:

{_names}

### CONSTRAINTS ###
- Flowing academic prose that matches the style of the thorough summary above — no bullet points, no headings, no lists
- ONLY the listed contributors — do not repeat contributors the thorough summary already covers
- Ground every attribution in the chapter source below; do NOT invent facts, dates, works, or attributions
- The paragraphs will be APPENDED to the thorough summary — write them as a natural continuation with no preamble
- Do NOT include thinking/reasoning — only the final prose
- Wrap the output exactly like this:

<thorough_addition>
your one-to-two paragraphs here
</thorough_addition>

### INPUT ###
Chapter content:
{_source}"""
            _raw = self._call_llm_with_empty_retry(
                _prompt,
                model=self.primary_model,
                temperature=self.temperature,
                max_tokens=2048,
            )
            if not _raw or not _raw.strip():
                self.log(
                    f"    ⚠️ V18.20.3.13: Thorough gap-fill call returned empty — "
                    f"thorough unchanged, floor stays {_covered}/{_total}",
                    "WARNING",
                )
                return thorough
            _raw = self._strip_thinking(_raw)
            # V18.16.0.1-class CoT guard (same as _ensure_exec_from_thorough):
            # a thinking-mode response must never be appended as prose.
            from core.summarisation.postchecks import detect_cot_narrative
            _raw_cleaned, _cot_issues = detect_cot_narrative(_raw, "thorough")
            if _cot_issues:
                self.log(
                    f"    ⚠️ V18.20.3.13: Thorough gap-fill output looks like CoT "
                    f"({_cot_issues[0].detail[:60]}) — discarding, floor stays "
                    f"{_covered}/{_total}",
                    "WARNING",
                )
                return thorough
            _m = re.search(
                r'<thorough_addition>(.*?)</thorough_addition>',
                _raw_cleaned, re.DOTALL,
            )
            _addition = _m.group(1).strip() if _m else _raw_cleaned.strip()
            if len(_addition.split()) < 20:
                self.log(
                    f"    ⚠️ V18.20.3.13: Thorough gap-fill addition too short "
                    f"({len(_addition.split())} words) — discarding, floor stays "
                    f"{_covered}/{_total}",
                    "WARNING",
                )
                return thorough
            thorough = (thorough or "").rstrip() + "\n\n" + _addition
            # Re-run the SAME coverage check on the appended thorough so the
            # after-line is a measurement, not a promise.
            _cov_after = check_coverage(analysis, thorough)
            self.log(
                f"    ✅ V18.20.3.13 Thorough gap-fill: floor {_covered}/{_total} → "
                f"{len(_cov_after.get('covered', []) or [])}/{_cov_after.get('total') or 0} "
                f"(added paragraphs for {len(_missing)} authors)",
                "INFO",
            )
            return thorough
        except Exception as _tf_e:
            # Fail-soft (house pattern): the floor must never break the
            # chapter — log visibly and ship the thorough unchanged.
            self.log(
                f"    ⚠️ V18.20.3.13: Thorough theorist floor failed (non-fatal): "
                f"{type(_tf_e).__name__}: {_tf_e}",
                "WARNING",
            )
            logger.debug(
                "thorough theorist floor failed: %s: %s",
                type(_tf_e).__name__, _tf_e,
            )
            return thorough
