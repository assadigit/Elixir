"""V18.20.4.7 (P5 phase 2 / O-a2): additive-sections machinery — a
Summarizer mixin.

The P5 O-a2 orchestrator decomposition (approved selected scope): the
``Summarizer`` methods that guarantee the ADDITIVE summary sections moved
out of the ~5.2k-line ``summarizer.py`` monolith into this module,
re-homed via the mixin pattern — ``Summarizer`` inherits
``SummarizerAdditiveMixin``, so every ``self.<attr>`` / ``self.<method>``
reference resolves exactly as before and external importers of
``Summarizer`` are unaffected (same module, same name).

VERBATIM CONTRACT (the house decomposition pattern): every method body is
byte-identical to the V18.20.4.6 zip's ``summarizer.py`` — verified by
``ast.get_source_segment`` comparison in
``tests/test_v182047_p5_core_decomp.py``. Only this module's imports (the
re-homed module-level dependencies) and docstring are new.

What lives here (moved VERBATIM, in the original relative order):

  - ``_ensure_conclusion_bullets``    — V18.15.9.1 the ONE consolidated
    Conclusions/Characteristics bullet (the V18.20.2.0 A4 book-neutral
    label; double-dash + prefix-only dedup fixes).
  - ``_normalize_empty_section``      — V13.39.0 delegate to
    ``summary_validator.normalize_empty_section``.
  - ``_verify_additive_section_item`` — V13.39.0 delegate (staticmethod).
  - ``_verify_additive_sections``     — V13.39.0 delegate (quarantine +
    log wiring).
  - ``_ensure_additive_sections``     — V13.40.0 the key_distinctions /
    theoretical_tensions followup call, incl. the V18.20.3.1 (D1) 4096
    budget + honest per-section reporting and the V18.20.3.2 (P1-e)
    retry-on-mass-drop.

NOT moved (stays in summarizer.py): ``_recover_vram`` (generic VRAM
recovery, not additive-sections machinery) and ``_summarize_inner``
itself (too entangled — explicitly out of the approved P5 scope).
"""

from __future__ import annotations

import re

from core.summarisation.summary_validator import (
    normalize_empty_section as sv_normalize_empty_section,
)
from core.summarisation.summary_validator import (
    verify_additive_section_item as sv_verify_additive_section_item,
)
from core.summarisation.summary_validator import (
    verify_additive_sections as sv_verify_additive_sections,
)
from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds (the
# main app logger) — the moved bodies' ``logger.debug`` fail-soft lines
# behave identically to pre-move.
logger = get_main_logger()


class SummarizerAdditiveMixin:
    """Additive-sections machinery for :class:`Summarizer` (see the module
    docstring). Method bodies are byte-identical to summarizer.py's."""

    def _ensure_conclusion_bullets(self, heading: str, text: str, result: dict) -> None:
        """V18.15.9.1: Ensure the source's enumerated conclusions appear as ONE
        consolidated bullet (not scattered).

        The V18.15.9.0 implementation added N separate "Characteristic N:" bullets
        (scattered). The user's V18.15.9.0 audit feedback: "THIS SYSTEM SHOULD
        CONSOLIDATE ALL 7 CHARACTERISTICS AS A BULLET, NOT SCATTERED." V18.15.9.1
        redesigns to add ONE consolidated bullet listing all N conclusions.

        The V18.15.9.0 audit also found 3 defects:
        1. Double-dash prefix (`- - **Characteristic N**:`) — the method added
           `- **Characteristic**:` but the markdown formatter adds ANOTHER `- `.
           V18.15.9.1 Fix: the bullet text does NOT start with `- ` (the
           formatter adds it).
        2. Characteristic 3 MISSING — the fuzzy check `t[:40] in _existing` found
           "genuineness and authenticity" inside another bullet's text (which
           lists all 7). V18.15.9.1 Fix: check if a DISTINCT conclusion bullet
           already exists (by looking for the `_label` prefix), not text anywhere.
        3. Characteristic 6 malformed (newline + trailing "and"). V18.15.9.1 Fix:
           the extraction now collapses newlines + strips trailing "and" (in
           post_processing._extract_sequential_run).

        V18.15.9.1 redesign:
        - Detect enumerated conclusions in the source.
        - Check if a DISTINCT consolidated conclusion bullet already exists
          (look for bullets starting with "**Characteristics**:" or
          "**Conclusions**:"). If yes, no-op (don't scatter).
        - If no, add ONE consolidated bullet: "**Characteristics of solid
          identity**: (1) selfsameness; (2) temporal continuity; (3) ...; (7) ..."
        - The bullet text does NOT start with `- ` (the markdown formatter
          adds the list marker — avoids the double-dash bug).

        Deterministic — no LLM call. Runs AFTER the deterministic judge +
        gap-fill, BEFORE postchecks.

        Args:
            heading: the chapter heading.
            text: the source chapter text.
            result: the parsed result dict (mutated in place — adds 1 bullet).
        """
        from core.summarisation.post_processing import detect_enumerated_conclusions

        conclusions = detect_enumerated_conclusions(text)
        if not conclusions:
            return  # no enumerated conclusion in source — nothing to do
        # V18.15.9.1 Fix 2: Check if a DISTINCT conclusion bullet already exists.
        # Look for bullets starting with "**Characteristics**" or "**Conclusions**"
        # (the labels we use). This prevents false-negatives from the V18.15.9.0
        # fuzzy check that matched conclusion TEXT inside other bullets.
        _label_plural = "Characteristics" if len(conclusions) >= 5 else "Conclusions"
        _existing_bullets = result.get("bullet_points", [])
        for bp in _existing_bullets:
            # V18.15.9.1: strip leading "- " / "* " list markers (but NOT the
            # ** bold markers we're looking for). Use a targeted regex: strip
            # leading whitespace + an optional "- " or "* " prefix.
            _bp_clean = re.sub(r"^\s*(?:[-\u2022]\s+)?", "", str(bp)).strip()
            # V18.15.9.1: check if the bullet starts with "**Characteristics" or
            # "**Conclusions" (the label prefix). We check the prefix (not the
            # full "**Characteristics**") because the label may be
            # "**Characteristics of solid identity**:" (with a qualifier).
            if _bp_clean.lower().startswith(f"**{_label_plural.lower()}"):
                self.log(
                    f"    ✅ V18.15.9.1: Source has {len(conclusions)} enumerated "
                    f"{_label_plural.lower()} — consolidated bullet already exists",
                    "DEBUG",
                )
                return  # distinct conclusion bullet already exists — don't scatter
        # V18.15.9.1: Build ONE consolidated bullet (not N scattered bullets).
        # Format: "Characteristics: (1) selfsameness; (2) temporal continuity;
        # (3) authenticity; ...; (7) conscience." (V18.20.2.0 SWOT A4: dropped
        # the book-specific " of solid identity" qualifier from the label.)
        # The bullet text does NOT start with "- " — the markdown formatter
        # adds the list marker (avoids the V18.15.9.0 double-dash bug).
        _items_text = "; ".join(f"({n}) {t}" for n, t in conclusions)
        # V18.20.2.0 (SWOT A4): the label is now book-neutral — was
        # "**{_label_plural} of solid identity**: ..." (gold-book overfitting:
        # a climate book shipped "Conclusions of solid identity"). The
        # distinct-bullet prefix check above ("**characteristics" /
        # "**conclusions") still matches the new label because it is
        # prefix-only.
        _consolidated = f"**{_label_plural}**: {_items_text}."
        # V18.15.9.1 Fix 1: Do NOT prefix with "- " — the formatter adds it.
        # The bullet is added to result["bullet_points"] as plain text; the
        # markdown formatter wraps each bullet_points entry with "- " later.
        result["bullet_points"].append(_consolidated)
        self.log(
            f"    ✅ V18.15.9.1: Added 1 consolidated {_label_plural} bullet "
            f"(all {len(conclusions)} items, verbatim from source) — not scattered",
            "INFO",
        )

    def _ensure_enumeration_bullets(self, heading: str, text: str, result: dict) -> None:
        """V0.4.23 (user directive): guarantee EVERY enumerated list's items
        appear in the summary — "if they are seven, seven must be captured".

        Generalizes V18.15.9.1 (the consolidated conclusion bullet) from the
        single (N)-style last-30% list to EVERY list the universal
        enumeration detector finds (bullets, a-d, 1-4, I-VI, ordinals,
        labeled, run-in — the full ``ENUMERATION_TEMPLATE``), across the
        WHOLE chapter:

        - For each detected list, measure per-item coverage against the
          current bullets + thorough (the same ≥50%-word-hit heuristic the
          recall floor uses).
        - A list with ANY uncovered item gets ONE consolidated bullet
          carrying ALL of its items verbatim (consolidated, not scattered —
          the V18.15.9.1 design). A list already fully covered adds nothing
          (this also makes it a no-op when the V18.15.9.1 conclusion bullet
          already carries the items verbatim).
        - Lists with < 3 items are skipped (not a list — the detector's
          own minimum).

        Deterministic — no LLM call. Runs AFTER the deterministic judge +
        gap-fill + conclusion bullets (so the model and gap-fill have every
          chance to cover the items naturally first), BEFORE postchecks.
        With the V0.4.23 no-cap policy, the added bullets ship — nothing
        displaces them.
        """
        from core.summarisation.enumeration import (
            clean_enum_text,
            detect_enumerations,
            enumeration_item_covered,
            stem_label,
        )

        try:
            enums = detect_enumerations(text)
            if not enums:
                return
            bullets = [str(b) for b in result.get("bullet_points", []) or []]
            thorough = str(result.get("thorough_summary", "") or "")
            haystack = (" ".join(bullets) + " " + thorough).lower()
            added = 0
            # V0.4.24 (audit backlog #3): the exact bullet texts are stashed
            # on the result so the SHIP-TIME POSTCHECKS can exempt them from
            # the truncation drop. The V4.23 run's Stern escape: the
            # guarantee's consolidated bullet (garbled stem + a source item
            # cut at a paragraph break, "…organic insecurity or a") tripped
            # is_truncated() and postcheck_bullets DROPPED it — 4 enumerated
            # items silently lost AFTER the guarantee had "covered" them.
            # Guarantee bullets carry verbatim source items — verifiable
            # against the source — so the "unverifiable cut claim" rationale
            # for the drop does not apply to them.
            guarantee_stash = result.setdefault("_enum_guarantee_texts", [])
            for enum in enums:
                if enum.count < 3:
                    continue
                missing = [
                    it for it in enum.items if not enumeration_item_covered(it.text, haystack)
                ]
                if not missing:
                    continue  # fully covered — nothing to guarantee
                # Build ONE consolidated bullet with ALL items (verbatim,
                # comma-joined) — the label derives from the list's stem.
                label = stem_label(enum.stem, enum.count)
                items_text = "; ".join(
                    f"({k}) {clean_enum_text(it.text)}" for k, it in enumerate(enum.items, 1)
                )
                consolidated = f"**{label}** — {enum.count} items from the source: {items_text}."
                # The bullet text does NOT start with "- " (the markdown
                # formatter adds the marker — the V18.15.9.1 double-dash
                # lesson).
                result.setdefault("bullet_points", []).append(consolidated)
                guarantee_stash.append(consolidated)
                added += 1
                # refresh the haystack so later lists see this bullet too
                haystack += " " + consolidated.lower()
                self.log(
                    f"    ✅ V0.4.23: enumeration guarantee — added 1 "
                    f"consolidated bullet for a {enum.count}-item "
                    f"{enum.style} list ({len(missing)} item(s) were "
                    f"uncovered; all {enum.count} now carried verbatim)",
                    "INFO",
                )
            if added == 0 and enums:
                self.log(
                    f"    ✅ V0.4.23: enumeration guarantee — all "
                    f"{sum(e.count for e in enums)} item(s) across "
                    f"{len(enums)} detected list(s) already covered "
                    f"(no bullets added)",
                    "DEBUG",
                )
        except Exception as _enum_e:
            self.log(
                f"    ⚠️ V0.4.23: enumeration-guarantee check failed (non-fatal): {_enum_e}",
                "WARNING",
            )

    def _final_enumeration_repair(
        self, heading: str, text: str, parsed: dict, bullets: list[str], thorough: str
    ) -> int:
        """V0.4.24 (audit backlog #3, layer-4 enforcement): LAST-CHANCE
        enumeration repair — re-run the ship-time guarantee against the
        FINAL bullet set, AFTER every ship-time filter.

        The V0.4.23 floor only REPORTED the missing items ("113/117 …
        missing: [runin_arabic] tendency to respond negatively…") — it
        never repaired them. Whatever path lost the items (the truncation
        drop that killed the Stern bullet, a dedup merge, a scar drop),
        this repair re-measures coverage on the text that actually ships
        and re-adds consolidated bullets for any list with an uncovered
        item. Deterministic — no LLM call; runs after postchecks, so the
        re-added bullets are verbatim source content by construction.

        Returns the number of bullets added (0 when nothing was missing).
        Never raises.
        """
        try:
            # sync BOTH haystack inputs to the FINAL text (the local
            # bullets/thorough are post-everything; parsed may be stale)
            parsed["bullet_points"] = [b for b in (bullets or []) if b]
            parsed["thorough_summary"] = thorough or ""
            _n_before = len(parsed["bullet_points"])
            self._ensure_enumeration_bullets(heading, text, parsed)
            _added = len(parsed.get("bullet_points", []) or []) - _n_before
            if _added:
                self.log(
                    f"    🩹 V0.4.24: last-chance enumeration repair — "
                    f"{_added} consolidated bullet(s) re-added after all "
                    f"ship-time filters (the floor's missing items are "
                    f"guaranteed on the set that actually ships).",
                    "INFO",
                )
            return _added
        except Exception as _rep_e:
            self.log(
                f"    ⚠️ V0.4.24: final enumeration repair failed (non-fatal): {_rep_e}",
                "WARNING",
            )
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    # V13.39.0: Anti-hallucination verification for additive sections
    # (key_distinctions + theoretical_tensions)
    # ─────────────────────────────────────────────────────────────────────────

    # V18.20.2.0 (SWOT A27): removed the duplicated @staticmethod decorator
    # (AST-verified duplicate — harmless on Python ≥3.10 but a TypeError at
    # class-definition time on ≤3.9).
    @staticmethod
    def _normalize_empty_section(text: str) -> str:
        """V13.39.0: Normalize empty section — delegates to summary_validator.normalize_empty_section.

        V18.7 (Phase 5.2): extracted verbatim to
        ``summary_validator.normalize_empty_section``. Pure static method.
        """
        return sv_normalize_empty_section(text)

    @staticmethod
    def _verify_additive_section_item(item: str, source_text: str) -> bool:
        """V13.39.0: Verify additive item — delegates to summary_validator.verify_additive_section_item.

        V18.7 (Phase 5.2): extracted verbatim to
        ``summary_validator.verify_additive_section_item``. Pure static method.
        """
        return sv_verify_additive_section_item(item, source_text)

    def _verify_additive_sections(self, heading: str, text: str, result: dict) -> None:
        """V13.39.0: Verify additive sections — delegates to summary_validator.verify_additive_sections.

        V18.7 (Phase 5.2): extracted verbatim to
        ``summary_validator.verify_additive_sections``.
        """
        sv_verify_additive_sections(
            heading=heading,
            text=text,
            result=result,
            quarantine=getattr(self, "quarantine", None),
            log=self.log,
        )

    def _ensure_additive_sections(self, heading: str, text: str, result: dict) -> None:
        """V13.40.0: Ensure key_distinctions + theoretical_tensions are populated.

        In academic-rigor JSON mode, the model often ignores the new keys and
        only returns executive_summary/bullet_points/thorough_summary. This
        method detects empty additive sections and runs a SEPARATE followup LLM
        call specifically for them — guaranteeing the sections are produced
        even when the main summary didn't include them.

        The followup call is cheap (~500 tokens input, ~300 tokens output) and
        uses the model's optimal temperature. The result is then verified by
        _verify_additive_sections (called separately in the pipeline).
        """
        _kd = result.get("key_distinctions", "") or ""
        _tt = result.get("theoretical_tensions", "") or ""
        if _kd.strip() and _tt.strip():
            return  # both already populated — nothing to do

        # At least one section is empty — run a followup call for both
        self.log(
            "    📝 Additive sections missing — running followup call for distinctions + tensions…",
            "INFO",
        )
        lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
        max_src = max(self.request.summarisation_max_context_tokens - 1500, 8000)
        src_text = text[: max_src * 4]

        prompt = self.prompt_manager.render_template(
            self._select_prompt("summarisation/additive_sections"),
            heading=heading,
            src_text=src_text,
            language=lang,
        )

        try:
            # V18.20.3.1 (real-rig audit D1): 2048 → 4096. The V18.20.3.0
            # the rig-test book run showed the additive followup needs
            # ~2700 tokens (9388 chars) for this prompt pair — the 2048 cap
            # cut the response mid-key_distinctions (done_reason=length),
            # shipping a truncated distinction AND killing theoretical_tensions
            # entirely (the model never reached it). 4096 stays well under
            # the 8192 output ceiling.
            # V18.20.3.2 (audit D1 yield / P1-e): RETRY-ON-MASS-DROP. The
            # V18.20.3.1 run produced 9 additive items of which 5 were later
            # dropped as truncated (postchecks) — a >50% loss that one fresh
            # generation would likely beat. The retry criterion uses the SAME
            # deterministic is_truncated() the postchecks drop uses, so the
            # decision matches what will actually ship. One retry, keep the
            # better attempt.
            def _parse_additive(raw_text: str):
                """Parse kd/tt from a raw additive response. Returns
                (kd_text, tt_text, kd_cut, tt_text_cut, truncated_lines,
                total_lines)."""
                import re as _re2

                from core.summarisation.post_processing import is_truncated as _is_trunc
                from core.summarisation.response_parser import strip_truncated_section_tail

                _raw_lower2 = raw_text.lower()
                kdm2 = _re2.search(
                    r"<key_distinctions>\s*(.*?)(?:</key_distinctions>|<theoretical_tensions>|$)",
                    raw_text,
                    _re2.DOTALL | _re2.IGNORECASE,
                )
                ttm2 = _re2.search(
                    r"<theoretical_tensions>\s*(.*?)(?:</theoretical_tensions>|$)",
                    raw_text,
                    _re2.DOTALL | _re2.IGNORECASE,
                )
                kd_out, tt_out, kd_cut2, tt_cut2 = "", "", False, False
                if kdm2:
                    _body = kdm2.group(1).strip()
                    _closed = "</key_distinctions>" in _raw_lower2
                    _clean = strip_truncated_section_tail(_body, closing_tag_present=_closed)
                    kd_cut2 = _clean != _body
                    kd_out = _clean
                if ttm2:
                    _body = ttm2.group(1).strip()
                    _closed = "</theoretical_tensions>" in _raw_lower2
                    _clean = strip_truncated_section_tail(_body, closing_tag_present=_closed)
                    tt_cut2 = _clean != _body
                    tt_out = _clean
                # Count lines the postchecks drop would remove (the exact
                # criterion used at ship time).
                _trunc_n = 0
                _total_n = 0
                for _sec_text in (kd_out, tt_out):
                    for _ln in _sec_text.split("\n"):
                        _ls = _ln.strip().lstrip("-•* ").strip()
                        if not _ls:
                            continue
                        _total_n += 1
                        if _is_trunc(_ls):
                            _trunc_n += 1
                return kd_out, tt_out, kd_cut2, tt_cut2, _trunc_n, _total_n

            raw = self._call_llm_with_empty_retry(
                prompt, temperature=self.temperature, max_tokens=4096
            )
            if not raw:
                self.log("    ⚠️ Additive-section followup returned empty", "WARNING")
                return
            raw = self._strip_thinking(raw)
            _kd_body, _tt_body, _kd_cut, _tt_cut, _trunc_lines, _total_lines = _parse_additive(raw)

            # P1-e: mass-drop → ONE retry with a fresh generation.
            if (
                _total_lines >= 3
                and _trunc_lines / _total_lines > 0.5
                and not self._deadline_exceeded("additive-section retry")
            ):
                self.log(
                    f"    ⚠️ V18.20.3.2: additive followup mass-truncation "
                    f"({_trunc_lines}/{_total_lines} lines would be dropped) — "
                    f"retrying the additive call once with a fresh generation",
                    "WARNING",
                )
                _retry_raw = self._call_llm_with_empty_retry(
                    prompt,
                    temperature=self.temperature,
                    max_tokens=4096,
                )
                if _retry_raw:
                    _retry_raw = self._strip_thinking(_retry_raw)
                    _kd_r, _tt_r, _kdc_r, _ttc_r, _trunc_r, _total_r = _parse_additive(_retry_raw)
                    _retry_yield = _total_r - _trunc_r
                    _first_yield = _total_lines - _trunc_lines
                    if _retry_yield > _first_yield:
                        self.log(
                            f"    ✅ V18.20.3.2: additive retry improved yield: "
                            f"{_first_yield} → {_retry_yield} usable lines",
                            "INFO",
                        )
                        raw = _retry_raw
                        _kd_body, _tt_body, _kd_cut, _tt_cut = _kd_r, _tt_r, _kdc_r, _ttc_r
                        _trunc_lines, _total_lines = _trunc_r, _total_r
                    else:
                        self.log(
                            f"    ℹ️ V18.20.3.2: additive retry did not improve "
                            f"yield ({_retry_yield} ≤ {_first_yield}) — keeping "
                            f"the first attempt",
                            "INFO",
                        )

            # Parse the two sections
            if _kd_body and not _kd.strip():
                if _kd_cut:
                    self.log(
                        "    ✂️ Additive followup truncated mid-key_distinctions — dropped "
                        "the incomplete trailing line.",
                        "WARNING",
                    )
                result["key_distinctions"] = _kd_body
            if _tt_body and not _tt.strip():
                if _tt_cut:
                    self.log(
                        "    ✂️ Additive followup truncated mid-theoretical_tensions — dropped "
                        "the incomplete trailing line.",
                        "WARNING",
                    )
                result["theoretical_tensions"] = _tt_body
            # V18.20.3.1 (D1): honest per-section reporting. The old single
            # "✅ populated" line hid the V18.20.3.0 failure mode (response
            # truncated → only 1 of 2 sections present, the other silently
            # absent from the final output).
            _kd_now = result.get("key_distinctions", "") or ""
            _tt_now = result.get("theoretical_tensions", "") or ""
            _kd_state = f"{len(_kd_now)} chars" if _kd_now.strip() else "MISSING"
            _tt_state = f"{len(_tt_now)} chars" if _tt_now.strip() else "MISSING"
            if _kd_now.strip() or _tt_now.strip():
                self.log(
                    f"    ✅ Additive sections via followup call: key_distinctions={_kd_state}, "
                    f"theoretical_tensions={_tt_state}"
                    + (
                        f" ({_trunc_lines}/{_total_lines} lines will be dropped as truncated)"
                        if _trunc_lines
                        else ""
                    )
                    + (
                        " (response hit the output cap — retry may recover the missing section)"
                        if (_kd_cut or _tt_cut or not _tt_now.strip() or not _kd_now.strip())
                        else ""
                    ),
                    "INFO",
                )
            elif _kd_cut or _tt_cut:
                self.log("    ⚠️ Additive followup truncated — no usable section content", "WARNING")
        except Exception as e:
            self.log(f"    ⚠️ Additive-section followup failed: {e}", "WARNING")
            logger.debug("additive-section followup failed: %s: %s", type(e).__name__, e)
