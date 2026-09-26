"""V0.18 (Phase 5.1, step 6) — Summarizer prompt builders.

The primary-prompt builder (_build_prompt) + the dedicated thorough/bullet
prompt builders + the dedicated-thorough fallback call moved out of
summarizer.py. All existing instance-level monkeypatch seams
(s._build_prompt = ..., s._call_dedicated_thorough_with_fallback = ...)
keep working (class-attr lookup through the instance).

Moved VERBATIM (byte-identical bodies) from ``summarizer.py`` during the
V0.18 Phase 5.1 de-monolithization, re-homed via the house mixin pattern
(cf. additive_sections / chapter_phases). ``SummarizerPromptMixin`` joined the
Summarizer bases; every ``self.<attr>`` / ``self.<method>`` reference
resolves exactly as before.
"""

from __future__ import annotations

import re

from core.summarisation.thorough_fallback import (
    call_dedicated_thorough_with_fallback as tf_call_dedicated_thorough_with_fallback,
)
from utils.error_trace import log_swallow
from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()


class SummarizerPromptMixin:
    """See the module docstring."""

    def _build_prompt(
        self,
        heading: str,
        text: str,
        with_cot: bool = True,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
    ) -> str:
        """V18.6.4 (ROLLBACK of V18.6.3): _build_prompt is INLINE again.

        V18.6.3 extracted this to prompt_assembly.build_primary_prompt, but
        it caused a crash on the user's machine after clicking Process in
        the wizard. Rolling back to the inline version (the V18.6.1 code)
        to restore stability. V18.20.4.7 (P5 / W-a3): the dead twin that
        stayed behind in prompt_assembly.py after this rollback was
        deleted there — this inline builder is the only one.

        The 5 low-risk _build_* methods (thorough_followup, dedicated_thorough,
        dedicated_bullet, missing_keywords, chunked) REMAIN extracted — only
        the high-risk _build_prompt is rolled back.
        """
        lang = (
            "Write your entire response in Persian (Farsi)."
            if self.language == "fa"
            else "Write your entire response in English."
        )

        # V0.05 (rig audit F9a/F9b — the user's "I didn't ask for a thorough
        # summary but it produced" + "thorough longer than the chapter"):
        # the request's output-selection flags are THE CONTRACT — they were
        # previously logged (settings_logger) but never enforced here, so an
        # unchecked Thorough Summary was still demanded, generated, expanded
        # (the 800-word floor), and rendered. And every length target now
        # SCALES to the source (a summary section may never be instructed to
        # exceed a fraction of its source — absolute word demands force the
        # model to pad/invent for short chapters: hallucination-by-instruction).
        from core.summarisation.length_policy import (
            bullet_range_phrase,
            count_source_words,
            exec_words_phrase,
            length_budget_block,
            thorough_words_phrase,
        )

        _source_words = count_source_words(text)
        _exec_words = exec_words_phrase(_source_words)
        _bullet_range = bullet_range_phrase(_source_words)
        _thorough_words = thorough_words_phrase(_source_words)
        _inc_exec = bool(getattr(self.request, "include_executive_summary", True))
        _inc_thorough = bool(getattr(self.request, "include_thorough_summary", True))
        _inc_keypoints = bool(getattr(self.request, "include_keypoints", True))

        callout_block = ""
        if callouts:
            callout_list = "\n".join(f'  - "{c}"' for c in callouts[:10])
            callout_block = f"""
HIGH-VALUE CALLOUTS from the author (these appear as highlighted tips in the chapter — your summary MUST capture the concept behind each):
{callout_list}
"""
        structural_block = ""
        try:
            import re as _re_so

            _so_matches = _re_so.findall(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4})",
                text[:200000],
            )
            _so_stop = {
                "The",
                "This",
                "These",
                "Those",
                "A",
                "An",
                "In",
                "While",
                "When",
                "If",
                "It",
                "He",
                "She",
                "They",
                "We",
                "Page",
                "Chapter",
                "Figure",
                "Table",
                "Note",
                "See",
                "As",
                "For",
                "Later",
                "Also",
                "Then",
                "However",
                "Moreover",
                "First",
                "Second",
                "Third",
            }
            _so_seen = set()
            _so_sequence = []
            for _name, _year in _so_matches:
                if _name in _so_stop or len(_name) < 3:
                    continue
                _key = f"{_name} ({_year})"
                if _key not in _so_seen:
                    _so_seen.add(_key)
                    _so_sequence.append(_key)
            if len(_so_sequence) >= 3:
                structural_block = f"""
STRUCTURAL OUTLINE — The source mentions these named contributors in this order:
{", ".join(_so_sequence[:20])}

Your THOROUGH SUMMARY must cover the FULL sequence above. Do NOT stop early —
narrate through the complete progression, ending with the source's conclusion.
If the source ends with an enumerated list or summary framework, your thorough
summary must reach that conclusion.
"""
        except Exception as _e:
            log_swallow("structural_outline_build", _e, detail=f"heading={heading[:60]}")

        # V0.03 (P1-5, real-rig audit): ANTHOLOGY ATTRIBUTION. The V0.02 rig
        # summarized an 8-author extract with ZERO author names — for an
        # anthology, bylines are core content. GENERAL rule: when the chapter
        # text carries standalone "By <Name>" bylines, require the summary
        # to attribute ideas to their authors.
        # V0.05 (rig audit F5 — P1): the block fires at >=1 byline. The old
        # >=2 threshold could never fire for a PER-CHAPTER segment of an
        # anthology (exactly one byline), leaving attribution to model whim
        # — the V0.04 rig's chapter-2 output named Neal Ford only inside a
        # critique bullet. A byline is attribution content, full stop; the
        # multi-author framing text remains for >=2.
        attribution_block = ""
        try:
            from core.preprocessing.deterministic_analyzer import extract_bylines

            _bylines = extract_bylines(text[:200000])
            if len(_bylines) >= 2:
                attribution_block = (
                    "\nANTHOLOGY ATTRIBUTION — This section collects work by "
                    f"multiple named authors ({', '.join(_bylines[:12])}). "
                    "Attribute each idea to the author the source credits "
                    '(e.g. "Nygard argues…", "per Braithwaite…"). Do NOT '
                    "collapse multi-author sections into anonymous prose.\n"
                )
            elif len(_bylines) == 1:
                attribution_block = (
                    f"\nATTRIBUTION — This chapter is by {_bylines[0]}. Name "
                    f'the author in the summary prose (e.g. "{_bylines[0].split()[-1]} '
                    'argues…"); a chapter summary that never names its author '
                    "is incomplete.\n"
                )
        except Exception as _e:
            log_swallow("byline_attribution_build", _e, detail=f"heading={heading[:60]}")

        try:
            from core.summarisation.text_preprocessor import calculate_reading_level

            _source_grade = calculate_reading_level(text[:5000])
            if _source_grade > 14:
                reading_level_instruction = """- Write for a specialist audience. Use technical terminology appropriate to the field. Maintain the academic register of the source."""
            elif _source_grade > 10:
                reading_level_instruction = """- Write for an educated general audience. Define technical terms on first use. Use clear, professional language."""
            else:
                reading_level_instruction = """"""
        except Exception as _e:
            reading_level_instruction = """
READING LEVEL REQUIREMENT (MANDATORY): Write for a non-native English reader at IELTS Reading level 7-9.
- Keep sentences under 20 words each. If a sentence is longer, split it into two.
- Use ACTIVE voice, not passive. "The author argues" not "It is argued by the author".
- Use common words. If you use a technical term or jargon, define it in plain words the first time it appears.
- Do NOT use idioms, metaphors, or culturally specific expressions a non-native reader may not know.
- Do NOT use words like "comprehensive", "methodology", "facilitate", "leverage", "utilize" — use "full", "method", "help", "use" instead.
- The summary MUST be EASIER to read than the source text, not harder.
- Write clearly and directly. Avoid academic jargon unless the source requires it.
"""
        if self.provider not in ("ollama", "lmstudio", "llamacpp", ""):
            reading_level_instruction += """
QUALITY (cloud model): You are a high-capability model. Go beyond extraction:
- Synthesise across paragraphs; show how ideas connect.
- Preserve the author's nuance and conditional statements ("however", "except when").
- Never invent facts, quotes, or examples not present in the source.
- If the source is ambiguous, say so explicitly rather than guessing.
"""

        if not self.academic_rigor:
            _active_prompt = self._select_prompt(self.active_prompt)
            rendered = self.prompt_manager.render(_active_prompt, heading, text, lang)
            if rendered:
                if callout_block:
                    inject = f"\n{callout_block}\n"
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace("Chapter content:", inject + "Chapter content:")
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace("{{text}}", inject + "{{text}}")
                    else:
                        rendered += inject
                if structural_block:
                    inject_so = f"\n{structural_block}\n"
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace(
                            "Chapter content:", inject_so + "Chapter content:"
                        )
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace("{{text}}", inject_so + "{{text}}")
                    else:
                        rendered += inject_so
                # V0.03 (P1-5): the anthology attribution block rides the
                # same injection path as callouts/structural outline.
                if attribution_block:
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace(
                            "Chapter content:", attribution_block + "Chapter content:"
                        )
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace("{{text}}", attribution_block + "{{text}}")
                    else:
                        rendered += attribution_block
                rendered += "\n" + reading_level_instruction
                rendered += "\nIMPORTANT: Only include specific numbers (percentages, dosages, counts, dates) if they appear VERBATIM in the source text. Do NOT invent, approximate, or round any numbers. If you are unsure whether a number is in the source, omit it."
                rendered += "\nANTI-HALLUCINATION: Use ONLY information from the source text. Do NOT add external knowledge, invented facts, or personal opinions. If you are unsure whether a claim is supported by the source, OMIT it."
                from core.llm.content_presets import get_content_preset

                _preset = get_content_preset(getattr(self.request, "source_type", "normal_book"))
                if _preset.prompt_addendum:
                    rendered += "\n" + _preset.prompt_addendum
                if _preset.tone_instruction:
                    rendered += "\n" + _preset.tone_instruction
                if _preset.preserve_domain_terms:
                    rendered += "\nDOMAIN TERMS: Preserve all technical/domain terminology exactly as written. Do NOT simplify or replace with common words."
                # V0.05 (F9a): strip the spec blocks of every section the user
                # did NOT select — an unrequested <thorough_summary> spec in
                # the prompt is what generated unrequested thorough sections
                # on the rig (the flag was logged but never enforced).
                if not _inc_exec:
                    rendered = re.sub(
                        r"<executive_summary>.*?</executive_summary>\s*",
                        "",
                        rendered,
                        flags=re.DOTALL,
                    )
                if not _inc_keypoints:
                    rendered = re.sub(
                        r"<bullet_points>.*?</bullet_points>\s*",
                        "",
                        rendered,
                        flags=re.DOTALL,
                    )
                if not _inc_thorough:
                    rendered = re.sub(
                        r"<thorough_summary>.*?</thorough_summary>\s*",
                        "",
                        rendered,
                        flags=re.DOTALL,
                    )
                _wanted = [
                    _t
                    for _t, _on in (
                        ("<executive_summary>", _inc_exec),
                        ("<bullet_points>", _inc_keypoints),
                        ("<thorough_summary>", _inc_thorough),
                        ("<key_distinctions>", True),
                        ("<theoretical_tensions>", True),
                    )
                    if _on
                ]
                if len(_wanted) < 5:
                    rendered += (
                        "\nOUTPUT SECTIONS (OVERRIDES any section list above): "
                        "output ONLY these sections, in this order: " + ", ".join(_wanted) + ".\n"
                    )
                # V0.05 (F9b): the source-relative length budget — appended to
                # EVERY rendered template so the scaled targets override any
                # absolute numbers a user-edited template still carries.
                rendered += "\n" + length_budget_block(
                    _source_words,
                    include_executive=_inc_exec,
                    include_thorough=_inc_thorough,
                    include_keypoints=_inc_keypoints,
                )
                # V0.4.23 (user directive — "never miss any listed items"): the
                # ENUMERATED-LIST COVERAGE block. Deterministic pre-scan of
                # the chapter's EVERY enumerated list (all template styles,
                # whole chapter); the model is told each list's items and
                # the full-coverage contract. Appended on BOTH prompt paths
                # (template + inline) beside the length budget.
                try:
                    from core.summarisation.enumeration import (
                        enumeration_coverage_block,
                    )

                    _enum_blk = enumeration_coverage_block(text)
                    if _enum_blk:
                        rendered += "\n\n" + _enum_blk
                except Exception:
                    pass
                return rendered

        # V0.05 (F9a/F9b): the inline fallback formats build ONLY the
        # requested sections, with targets scaled to the source.
        _sections_json = []
        if _inc_exec:
            _sections_json.append('- "executive_summary": 3-5 findings.')
        if _inc_keypoints:
            _sections_json.append(
                f'- "bullet_points": {_bullet_range} findings. Include ALL '
                "items from any enumerated lists in the source."
            )
        if _inc_thorough:
            _sections_json.append(
                f'- "thorough_summary": {_bullet_range} findings. CRITICAL: '
                "Cover ALL major topics and contributors in the chapter. Do "
                "NOT truncate — if running low on output space, make claims "
                "shorter rather than omitting topics. Preserve all "
                "enumerated lists and multi-step processes."
            )
        _sections_json += [
            '- "key_distinctions": 2-5 distinctions (each: "claim" = the contrast + why it matters, "supporting_text" = verbatim quote). Prioritize technical-term contrasts, developmental phase distinctions, competing positions, normal-vs-pathological.',
            '- "theoretical_tensions": 2-4 tensions (each: "claim" = the tension + diverging positions, "supporting_text" = verbatim quote). Prioritize opposing-force dialectics, school-vs-school debates, unresolved ambiguities, clinical-vs-theoretical. Name BOTH poles.',
        ]
        _sections_xml = []
        if _inc_exec:
            _sections_xml.append(
                f"<executive_summary>\nA {_exec_words} word narrative overview "
                "of the chapter's main argument and conclusions.\n</executive_summary>"
            )
        if _inc_keypoints:
            _sections_xml.append(
                f"<bullet_points>\nA comprehensive list of {_bullet_range} "
                "distinct key takeaways. One bullet per line, each prefixed "
                'with "- ". Each bullet must be a complete, self-contained '
                "sentence expressing a single claim, finding, or concept. "
                "Cover every section of the chapter.\n</bullet_points>"
            )
        if _inc_thorough:
            _sections_xml.append(
                f"<thorough_summary>\nA {_thorough_words} word detailed "
                "narrative that walks through the chapter section by section, "
                "explaining the argument, evidence, and reasoning in depth. "
                "The target scales to this chapter's length — never pad or "
                "invent content to reach it.\n</thorough_summary>"
            )
        _sections_xml += [
            '<key_distinctions>\nList 2-5 important DISTINCTIONS the chapter explicitly draws between related concepts. ONLY include distinctions that the chapter ACTUALLY discusses — each must be traceable to a specific passage. If the chapter does not draw any explicit distinctions, output "None" (do NOT invent distinctions). Format: one distinction per line, prefixed with "- ". Prioritize: technical-term contrasts, developmental phase distinctions, competing positions, normal-vs-pathological.\n</key_distinctions>',
            '<theoretical_tensions>\nIdentify 2-4 theoretical TENSIONS, DEBATES, or AMBIGUITIES the author EXPLICITLY discusses. ONLY include tensions that are actually present in the text — each must be traceable to a specific passage. If the chapter does not discuss any tensions, output "None" (do NOT fabricate debates to fill space). Prioritize: opposing-force dialectics, school-vs-school debates, unresolved ambiguities, clinical-vs-theoretical tensions. Name BOTH poles for each.\n</theoretical_tensions>',
        ]

        output_format = ""
        if self.academic_rigor:
            output_format = f"""
You are a clinical summariser. Extract the key findings from the chapter titled "{heading}".

For each finding, provide:
- "claim": A short, PRECISE summary (one sentence). Do NOT oversimplify or reinterpret. If the source says "used the word identity 92 times, only once in a technical sense," write exactly that — do NOT write "mentioned identity only once."
- "supporting_text": A DIRECT QUOTE from the chapter (verbatim, in quotes).
- "source_reference": Page/line reference if available, or author+year.

LIST PRESERVATION: If the source contains enumerated or numbered lists, reproduce ALL items as separate findings.
DETAIL PRESERVATION: When the source describes a multi-step process or set of conditions, preserve ALL steps/components as separate findings.
ANTI-FALSE-PRECISION: Do NOT invent distinctions between authors the source groups together. PRESERVE the source's grouping.
THEORIST COVERAGE: Every named author in the source MUST appear, including minor/secondary contributors.
SUB-COMPONENT COMPLETENESS: When the source describes a model with numbered sub-components, reproduce EVERY sub-component.
ANTI-OVERSPECIFICATION: Do NOT add interpretive adjectives not in the source. Quote the source's exact characterization.
ANTI-CONTEXT-STRIPPING: PRESERVE context qualifiers. Do NOT generalize context-specific statements to universal ones.
DEPTH PRESERVATION: Preserve philosophical articulations verbatim. Do NOT reduce rich characterizations to generic phrases.

Output a JSON object with these sections:
{chr(10).join(_sections_json)}

PRECISION RULE: Every claim must be traceable to a specific passage. The supporting_text MUST be a verbatim quote from the source. Do NOT paraphrase loosely — if the source says "contains the history of object choices," write exactly that, not "holds history."

Do NOT describe the JSON structure. Only output the JSON object.
"""
        else:
            output_format = "\nYou MUST output exactly these XML sections:\n\n" + "\n\n".join(
                _sections_xml
            )
        # V0.05 (F9b): the length budget rides BOTH inline paths.
        output_format += "\n\n" + length_budget_block(
            _source_words,
            include_executive=_inc_exec,
            include_thorough=_inc_thorough,
            include_keypoints=_inc_keypoints,
        )
        # V0.4.23 (user directive): the ENUMERATED-LIST COVERAGE block rides
        # both inline paths too (see the template path above).
        try:
            from core.summarisation.enumeration import enumeration_coverage_block

            _enum_blk_inline = enumeration_coverage_block(text)
            if _enum_blk_inline:
                output_format += "\n\n" + _enum_blk_inline
        except Exception:
            pass

        number_instruction = """
IMPORTANT: Focus on descriptive findings, mechanisms, relationships, and qualitative conclusions.
Only include specific numbers (percentages, dosages, counts, dates) if they appear VERBATIM in the source text. Do NOT invent, approximate, or round any numbers. If you are unsure whether a number is in the source, omit it.
"""

        model_specific = ""
        model_lower = (self.primary_model or "").lower()
        if "qwen" in model_lower:
            model_specific = "\nNOTE: You are a thinking model. Do NOT include your chain-of-thought reasoning in the output. Output ONLY the final summary.\n"
        elif "qwythos" in model_lower or "claude" in model_lower or "mythos" in model_lower:
            model_specific = "\nNOTE: Be concise — each bullet should be a single, distinct concept (one sentence, max ~25 words). Do not pad bullets with narrative filler.\n"

        from core.llm.content_presets import detect_source_type, get_content_preset

        source_type = getattr(self.request, "source_type", "normal_book")
        if source_type == "normal_book":
            detected = detect_source_type(text)
            if detected != "normal_book":
                source_type = detected
                self.log(f"    📋 Auto-detected source type: {source_type}", "DEBUG")
        preset = get_content_preset(source_type)
        tone_instruction = preset.tone_instruction
        content_addendum = preset.prompt_addendum

        if preset.bullet_style == "nuanced":
            model_specific += f"\nNOTE: Write longer, nuanced bullets (20-40 words each) that preserve philosophical arguments. Aim for {preset.max_bullets} bullets.\n"
        elif preset.bullet_style == "actionable":
            model_specific += f"\nNOTE: Frame bullets as actionable advice. Aim for {preset.max_bullets} bullets.\n"
        elif preset.bullet_style == "conceptual" and source_type == "academic_paper":
            model_specific += f"\nNOTE: Aim for {preset.max_bullets} bullets covering methodology, results, and conclusions separately.\n"

        return f"""You are an expert book summariser. {lang}

You are summarising a chapter titled: "{heading}".

GOAL: Produce a comprehensive, faithful summary that a reader could use to recall every key concept, argument, framework, and example from the chapter. Depth over brevity.

INSTRUCTIONS:
1. Read the entire chapter content carefully.
2. Identify every distinct claim, concept, definition, example, and recommendation.
3. If you are unsure whether a claim is supported by the source, OMIT it. Do not invent facts.
4. Use the chapter's own terminology; do not substitute synonyms for technical terms.
5. Paraphrase PRECISELY. Do not oversimplify or reinterpret the source. If the source says "contains the history of object choices," write exactly that — do NOT write "holds history" or other loose paraphrases. Preserve the author's exact meaning.
6. LIST PRESERVATION: If the source contains enumerated or numbered lists (e.g., "1. ... 2. ... 3. ...", bullet-pointed characteristics, numbered criteria, step-by-step processes), reproduce ALL items in your summary. Do NOT condense numbered lists to "among other things" or "including several factors." Each listed item is there for a reason — the reader needs all of them.
7. DETAIL PRESERVATION: When the source describes a multi-step process, a set of conditions, a causal mechanism, or a specific procedure, do NOT reduce it to a single sentence. Preserve the steps, conditions, or components. For example, if the source says "two conditions must be met: (1) ... and (2) ...", include BOTH conditions. If it describes a staged process, include every step with its specific name and what each step involves.
8. ANTI-FALSE-PRECISION: Do NOT invent scholarly distinctions between authors the source groups together. PRESERVE the source's grouping.
9. THEORIST COVERAGE: Every named author in the source MUST appear, including minor/secondary contributors.
10. SUB-COMPONENT COMPLETENESS: When the source describes a model with numbered sub-components, reproduce EVERY sub-component.
11. ANTI-OVERSPECIFICATION: Do NOT add interpretive adjectives not in the source. If source says "in passing", write "in passing" — not "non-technical" or "colloquial".
12. ANTI-CONTEXT-STRIPPING: PRESERVE context qualifiers. If source says "in the short path, X does not occur", do NOT write "X does not occur".
13. DEPTH PRESERVATION: Preserve philosophical articulations verbatim. Do NOT reduce "two limits of human experience incompatible but complementary" to "two opposing forces".
14. DO NOT output your thinking process, analysis steps, or reasoning. Output ONLY the final summary in the XML format below.
{model_specific}
{number_instruction}
{reading_level_instruction}
{tone_instruction}
{content_addendum}
{callout_block}
{attribution_block}
{output_format}

Chapter content:
{text}

Output ONLY the XML sections specified above. No preamble, no commentary, no thinking process, no markdown code fences.
"""

    def _build_dedicated_thorough_prompt(
        self, heading: str, text: str, exec_sum: str, bullets: list[str], draft: str | None = None
    ) -> str:
        """V18.2.34: Dedicated thorough-summary prompt.

        V18.6 (Phase 4, Task 4.2): delegates to
        ``prompt_assembly.build_dedicated_thorough_prompt``. Byte-for-byte
        identical output (characterization tests in ``test_prompt_assembly.py``).

        Unlike ``_build_thorough_followup`` (a small followup call appended to
        the primary LLM response that shares output budget with the other 4
        sections), this is a STANDALONE call that gets the full output budget
        for the thorough summary alone. Used when the primary-call thorough
        came back short (<800 words) and we want a deeper, more comprehensive
        expansion that doesn't compete with exec/bullets/key_distinctions/
        glossary for token budget.
        """
        from core.summarisation.prompt_assembly import (
            build_dedicated_thorough_prompt as _pa_ded_thorough,
        )

        # V18.20.3.11 (Phase 3.b): the primary's PARTIAL thorough (cut at the
        # 8192 output cap) travels as ``draft`` so the dedicated call is a
        # continuation, not a cold re-derivation.
        return _pa_ded_thorough(heading, text, exec_sum, bullets, self.language, draft=draft)

    def _call_dedicated_thorough_with_fallback(
        self,
        prompt: str,
        exec_sum: str,
        bullets: list[str],
        min_words: int = 800,
    ) -> str | None:
        """V18.2.44 (Next Step #6): Dedicated thorough call with 3 attempts + a
        deterministic non-empty fallback.

        V18.11 (Phase 5 Stage 3, Batch 2.3): logic extracted verbatim to
        ``thorough_fallback.call_dedicated_thorough_with_fallback``. The
        mutable ``self._synthetic_thorough_fallback_count`` is passed in
        as an int param and the (possibly incremented) new count is
        returned alongside the thorough text; this delegate unpacks and
        re-assigns it (kept as a plain int per the V18.4 contract).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_thorough_fallback.py``).
        """
        result, self._synthetic_thorough_fallback_count = tf_call_dedicated_thorough_with_fallback(
            prompt,
            exec_sum,
            bullets,
            min_words=min_words,
            max_output_tokens=getattr(self.request, "summarisation_max_output_tokens", 8192)
            or 8192,
            primary_model=self.primary_model,
            temperature=self.temperature,
            temperature_multiplier=float(
                getattr(self.settings, "thorough_temperature_multiplier", 0.5)
            ),
            strip_thinking=self._strip_thinking,
            call_llm=self._call_llm,
            deadline_exceeded=self._deadline_exceeded,
            synthetic_fallback_count=self._synthetic_thorough_fallback_count,
            log=self.log,
        )
        return result

    def _build_dedicated_bullet_prompt(
        self, heading: str, text: str, exec_sum: str, existing_bullets: list[str]
    ) -> str:
        """V18.2.34: Dedicated bullet-expansion prompt.

        V18.6 (Phase 4, Task 4.2): delegates to
        ``prompt_assembly.build_dedicated_bullet_prompt``. Byte-for-byte
        identical output (characterization tests in ``test_prompt_assembly.py``).

        Standalone call (full output budget) used when the primary-call
        bullet_points list came back short (<30 bullets). Asks for 30-50 NEW
        bullets that don't repeat the existing ones — gives the chapter full
        coverage of every named contributor, framework, and example.
        """
        from core.summarisation.prompt_assembly import (
            build_dedicated_bullet_prompt as _pa_ded_bullet,
        )

        return _pa_ded_bullet(heading, text, exec_sum, existing_bullets, self.language)

    def _build_exec_from_thorough_prompt(self, heading: str, thorough_summary: str) -> str:
        """V18.15.8.0 (Fix 1): Build the exec-from-thorough followup prompt.

        Delegates to ``prompt_assembly.build_exec_from_thorough_prompt``.
        See that function's docstring for the full rationale.
        """
        from core.summarisation.prompt_assembly import (
            build_exec_from_thorough_prompt as _pa_exec_from_thorough,
        )

        return _pa_exec_from_thorough(heading, thorough_summary, self.language)
