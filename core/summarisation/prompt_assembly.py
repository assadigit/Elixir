"""V18.6 (Phase 4, Task 4.2): Prompt-assembly pure functions.

Extracted from ``Summarizer`` (god-class decomposition Stage 1). These are
the 5 LOW-RISK ``_build_*`` methods — pure string construction with only
``self.language`` as the ``self`` dependency. The 6th method, ``_build_prompt``
(325 lines, 9 ``self`` dependencies), is NOT extracted here — it's too
coupled to extract safely without a golden-master LLM gate.

**Extraction map** (what moved where):

| Summarizer method (old)              | prompt_assembly function (new)            | self deps |
|---------------------------------------|-------------------------------------------|-----------|
| ``_build_thorough_followup``          | ``build_thorough_followup``               | language  |
| ``_build_dedicated_thorough_prompt``  | ``build_dedicated_thorough_prompt``       | language  |
| ``_build_dedicated_bullet_prompt``    | ``build_dedicated_bullet_prompt``         | language  |
| ``_build_missing_keywords_reprompt``  | ``build_missing_keywords_reprompt``       | language  |
| ``_build_chunked_prompt``             | ``build_chunked_prompt``                  | calls build_full_prompt |

Each function is extracted VERBATIM — the only change is ``self.language``
becomes a ``language`` parameter. The Summarizer methods now delegate:
``return build_thorough_followup(heading, text, exec_sum, self.language)``.

Characterization tests: ``tests/test_prompt_assembly.py`` captures canned
inputs → golden prompt string. Byte-for-byte stability gate.

Why ``_build_prompt`` is NOT extracted:
  - 325 lines, 9 ``self`` dependencies (language, provider, academic_rigor,
    _select_prompt, active_prompt, prompt_manager, request, log,
    primary_model).
  - Calls ``self.prompt_manager.render`` (stateful), ``self._select_prompt``
    (depends on model taxonomy), ``get_content_preset`` (depends on
    request.source_type), ``calculate_reading_level`` (external import).
  - Any mistake changes the LLM prompt → changes the output. The
    golden-master gate (score >= 9/10) requires a live Ollama run.
  - Deferred to the next session with user hardware.

V18.20.4.7 (P5 phase 2 / W-a3): the dead ``PromptContext`` +
``build_primary_prompt`` twin that used to live at the bottom of this
module (kept after the V18.6.4 rollback) was deleted — the LIVE inline
``Summarizer._build_prompt`` in summarizer.py is the only builder.
"""
from __future__ import annotations

import re


def _lang_str(language: str) -> str:
    """Build the language instruction string (was inline in each method)."""
    if language == "fa":
        return "Write in Persian (Farsi)."
    return "Write in English."


# V0.05 (rig audit F9b): every prompt builder in this module SCALES its
# length demands to the source via core.summarisation.length_policy — the
# absolute "800-1200 word" / "30-50 bullets" / "150-250 word" demands are
# what force-fed padding and invention on short chapters (the V0.04 rig:
# thorough sections 1.55-2.76× their sources). One helper, one rule.
def _scaled_targets(text: str) -> tuple[str, str, str, str]:
    """(exec_words, thorough_words, bullet_range, compression_note) for text."""
    from core.summarisation.length_policy import (
        bullet_range_phrase,
        count_source_words,
        exec_words_phrase,
        thorough_words_phrase,
    )
    _w = count_source_words(text)
    return (
        exec_words_phrase(_w),
        thorough_words_phrase(_w),
        bullet_range_phrase(_w),
        "The target scales to this chapter's length: a summary section must "
        "be SHORTER than its source — if you cannot fill the target with "
        "content the chapter actually states, write less; NEVER pad, "
        "elaborate, or invent content to reach a length.",
    )


def build_thorough_followup(heading: str, text: str, exec_sum: str,
                            language: str = "en") -> str:
    """Build the thorough-summary followup prompt.

    Extracted verbatim from ``Summarizer._build_thorough_followup``.
    Only change: ``self.language`` -> ``language`` parameter.
    V0.05 (F9b): the word target scales to the source (was 800-1200).
    """
    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    _exec_w, _th_w, _bp_r, _note = _scaled_targets(text)
    return f"""You are an expert summariser. {lang}

You already wrote this executive summary for "{heading}":
{exec_sum[:400]}…

Now write a comprehensive, detailed thorough summary of {_th_w} covering the full chapter in depth. Write in FLOWING PROSE PARAGRAPHS (not bullet points, not one-sentence-per-line). {_note} Include all key points, examples, and reasoning. Wrap it exactly like this:

<thorough_summary>
your detailed narrative here
</thorough_summary>

Full chapter content:
{text}"""


def build_dedicated_thorough_prompt(heading: str, text: str, exec_sum: str,
                                    bullets: list[str],
                                    language: str = "en",
                                    draft: str | None = None) -> str:
    """V18.2.34: Dedicated thorough-summary prompt.

    Extracted verbatim from ``Summarizer._build_dedicated_thorough_prompt``.
    Only change: ``self.language`` -> ``language`` parameter.

    Unlike ``build_thorough_followup`` (a small followup call appended to
    the primary LLM response that shares output budget with the other 4
    sections), this is a STANDALONE call that gets the full output budget
    for the thorough summary alone. Used when the primary-call thorough
    came back short (<800 words) and we want a deeper, more comprehensive
    expansion that doesn't compete with exec/bullets/key_distinctions/
    glossary for token budget.

    V18.20.2.0 (SWOT A4): removed the gold-book-specific constraint line
    "Preserve the developmental arc: trace identity from its earliest
    origins through adolescence to middle age" — an identity-book
    instruction that shipped in EVERY book's thorough prompt (actively
    corrupting non-identity books). Generic life-stage arc preservation
    remains available as CONDITIONAL guidance in prompts/default.md
    ("When the source describes development across MULTIPLE life
    stages…"). All other constraints are unchanged. Golden-master
    re-validation on the real rig is required for this prompt change.

    V18.20.3.11 (Phase 3.b, .3.9 rig audit §2 — "truncation paid twice"):
    optional ``draft`` — the PARTIAL thorough the primary call produced
    before hitting its 8192 output cap. Three rig runs (.3.7/.3.8/.3.9)
    truncated the primary at ~33-35k chars and left a 423-763-word
    partial thorough that was DISCARDED, then this call re-derived the
    thorough from scratch (~371s). Passing the draft makes this call the
    primary's DESIGNATED CONTINUATION: complete and deepen the draft
    instead of starting cold (keeps the partial's generation from being
    wasted AND anchors the continuation in the model's own framing).
    """
    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    _exec_w, _th_w, _bp_r, _note = _scaled_targets(text)
    _bullets_text = "\n".join(f"- {b}" for b in bullets[:30]) if bullets else "(no bullets yet)"
    _max_source_chars = min(len(text), 40000)
    _source = text[:_max_source_chars]
    _draft_block = ""
    if draft and str(draft).strip():
        _draft_text = str(draft).strip()[:6000]
        _draft_block = f"""### DRAFT FROM THE PRIMARY PASS ###
A partial thorough draft was cut at the primary call's output cap:

<draft>
{_draft_text}
</draft>

COMPLETE and DEEPEN this draft: preserve its valid findings (correct any
partially-written sentence at the cut point), extend it to the full
{_th_w} target, and weave in the remaining chapter content it missed. Do
not re-derive what the draft already covers.

"""
    return f"""### ROLE ###
You are a senior academic summarizer. Your task is to write ONE comprehensive thorough summary. {lang}

### CONTEXT ###
Chapter: "{heading}"

You already produced this executive summary:
{exec_sum[:600]}

And these key bullet points:
{_bullets_text}

{_draft_block}### TASK ###
Write a comprehensive {_th_w} thorough summary of the chapter above. This is a DEDICATED call — you have the FULL output budget for this summary alone. {_note}

### CONSTRAINTS ###
- Write FLOWING PROSE PARAGRAPHS (not bullet points, not one-sentence-per-line)
- Organize into 2-4 paragraphs, each with a clear topic sentence followed by 2-4 supporting sentences
- Use transitional phrases between paragraphs
- Cover ALL key concepts, frameworks, named contributors, and examples from the chapter
- Include every named author/theorist mentioned in the chapter
- Do NOT repeat the bullet points — weave them into flowing narrative
- Do NOT invent facts, numbers, or attributions not in the source

### INPUT ###
Chapter content:
{_source}

### OUTPUT FORMAT ###
Output ONLY the thorough summary wrapped in XML tags. No preamble, no commentary.

<thorough_summary>
Your {_th_w} detailed analysis here.
</thorough_summary>"""


def build_exec_from_thorough_prompt(heading: str, thorough_summary: str,
                                    language: str = "en") -> str:
    """V18.15.8.0 (Fix 1): Build the exec-from-thorough followup prompt.

    This is fired when the primary call produced an empty ``executive_summary``
    but the ``thorough_summary`` is populated (via the dedicated thorough call
    at ``summarizer.py:3060``). The thorough summary has a dedicated system
    with 100% coverage — we derive the executive summary FROM it, rather than
    the pre-V18.15.8.0 backwards fallback (``thorough = exec_sum`` which copied
    an empty string when exec was also empty).

    The call is cheap (~2000 tokens input = the thorough, ~300 tokens output =
    the 150-250 word exec summary) and uses the model's optimal temperature.

    Args:
        heading: the chapter heading.
        thorough_summary: the populated thorough summary (800-1200 words).
        language: "en" or "fa".

    Returns:
        The prompt string for the exec-from-thorough followup LLM call.
    """
    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    _exec_w, _th_w, _bp_r, _note = _scaled_targets(thorough_summary or "")
    # Cap the thorough at 4000 chars (~1000 words) to stay within token budget.
    _thorough = (thorough_summary or "")[:4000]
    return f"""### ROLE ###
You are a senior academic summarizer. Your task is to write ONE executive summary. {lang}

### CONTEXT ###
Chapter: "{heading}"

You already produced this comprehensive thorough summary:
{_thorough}

### TASK ###
Write a {_exec_w} executive summary that captures the chapter's main thesis, key conclusions, and central argument. This is a DERIVATIVE call — synthesize the thorough summary above into a concise overview. Do NOT introduce new information. Do NOT include bullet points. Write in flowing prose.

### CONSTRAINTS ###
- {_exec_w} (strict)
- Flowing prose paragraphs (NOT bullet points)
- Capture the main thesis + key conclusions
- Do NOT introduce facts not in the thorough summary
- Do NOT include thinking/reasoning — only the final summary
- Wrap the output exactly like this:

<executive_summary>
your {_exec_w} executive summary here
</executive_summary>"""


def build_dedicated_bullet_prompt(heading: str, text: str, exec_sum: str,
                                  existing_bullets: list[str],
                                  language: str = "en") -> str:
    """V18.2.34: Dedicated bullet-expansion prompt.

    Extracted verbatim from ``Summarizer._build_dedicated_bullet_prompt``.
    Only change: ``self.language`` -> ``language`` parameter.

    Standalone call (full output budget) used when the primary-call
    bullet_points list came back short (<30 bullets). Asks for 30-50 NEW
    bullets that don't repeat the existing ones — gives the chapter full
    coverage of every named contributor, framework, and example.
    """
    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    _exec_w, _th_w, _bp_r, _note = _scaled_targets(text)
    _existing_text = "\n".join(f"- {b}" for b in existing_bullets[:20]) if existing_bullets else "(none yet)"
    _max_source_chars = min(len(text), 40000)
    _source = text[:_max_source_chars]
    return f"""### ROLE ###
You are a senior academic summarizer. Your task is to produce a comprehensive list of bullet points. {lang}

### CONTEXT ###
Chapter: "{heading}"
You already produced this executive summary:
{exec_sum[:400]}
And these existing bullet points (do NOT repeat these — add NEW ones):
{_existing_text}

### TASK ###
Produce enough NEW bullet points to reach a total of {_bp_r} for the chapter (one distinct takeaway per ~50 source words), covering the key concepts, named contributors, frameworks, and examples that are NOT yet covered above. {_note}

### CONSTRAINTS ###
- One bullet per line, prefixed with "- "
- Each bullet: 1-2 sentences max
- Cover every named author/theorist in the chapter
- Do NOT repeat the existing bullets above
- Do NOT invent facts not in the source
- Do NOT fragment or pad — a bullet must carry a distinct claim the source actually states

### INPUT ###
Chapter content:
{_source}

### OUTPUT FORMAT ###
Output ONLY bullet points, one per line, prefixed with "- ".

- First new bullet point
- Second new bullet point
- ..."""


def build_missing_keywords_reprompt(heading: str, text: str,
                                    missing: list[str],
                                    language: str = "en") -> str:
    """P4 fix: augmentation, not replacement. Ask for NEW bullets about
    the missing concepts, not a whole new summary.

    Extracted verbatim from ``Summarizer._build_missing_keywords_reprompt``.
    Only change: ``self.language`` -> ``language`` parameter.
    """
    lang = "Write in Persian (Farsi)." if language == "fa" else "Write in English."
    return f"""The chapter "{heading}" discusses these concepts that may have been missed: {', '.join(missing)}.

For EACH concept listed above, output 2-5 bullet points explaining what the chapter says about it. {lang}

Rules:
- Each bullet must be a self-contained claim grounded in the source text.
- One bullet per line, prefixed with "- ".
- Do NOT output XML tags or a full summary — ONLY the new bullet points.
- If a concept is not actually discussed in the chapter, output nothing for it.

Chapter content:
{text}

New bullet points only:"""


def build_chunked_prompt(heading: str, text: str,
                         full_prompt: str,
                         with_cot: bool = True,
                         chunk: int = 1,
                         include_executive: bool = True,
                         include_thorough: bool = True,
                         include_keypoints: bool = True) -> str:
    """V18.3.4 (E3): Build a chunked prompt — only requests SOME sections.

    Extracted verbatim from ``Summarizer._build_chunked_prompt``.
    Change: instead of calling ``self._build_prompt(...)``, the caller
    passes the already-built full prompt string (``full_prompt``). This
    decouples the chunking logic from the prompt-builder (which has 9
    self-deps and isn't extracted yet).

    chunk=1: executive_summary + bullet_points + thorough_summary
    chunk=2: key_distinctions + theoretical_tensions

    V0.05 (rig audit F9a/F9b): the chunk-1 section list respects the
    user's output-selection flags (an unrequested section is not demanded
    back in via the chunk override), every length target scales to the
    source via length_policy, and the output-format replacement now stops
    at ``Chapter content:`` — the old to-end-of-string pattern ate
    EVERYTHING after the format block, chapter content included, on any
    real (non-synthetic) full prompt.
    """
    _exec_w, _th_w, _bp_r, _note = _scaled_targets(text)
    # Find the output_format section and replace it with the chunked version
    if chunk == 1:
        _c1_sections = []
        if include_executive:
            _c1_sections.append(
                f"<executive_summary>\nA {_exec_w} narrative overview of the "
                "chapter's main argument and conclusions.\n</executive_summary>"
            )
        if include_keypoints:
            _c1_sections.append(
                f"<bullet_points>\nA comprehensive list of {_bp_r} distinct "
                "key takeaways. One bullet per line, each prefixed with "
                '"- ". Each bullet must be a complete, self-contained '
                "sentence expressing a single claim, finding, or concept. "
                "Cover every section of the chapter.\n</bullet_points>"
            )
        if include_thorough:
            _c1_sections.append(
                f"<thorough_summary>\nA {_th_w} detailed summary covering "
                "ALL major topics, contributors, and examples. Write in "
                "flowing prose paragraphs. Preserve all enumerated lists and "
                "multi-step processes. Do NOT truncate.\n</thorough_summary>"
            )
        _c1_names = [s.split("\n")[0] for s in _c1_sections]
        _c1_skip = [t for t, on in (
            ("key_distinctions", True), ("theoretical_tensions", True),
        ) if on]
        _chunk_format = (
            f"\nOutput ONLY these {len(_c1_sections)} XML sections "
            "(chunk 1 of 2):\n\n"
            + "\n\n".join(_c1_sections)
            + f"\n\nDo NOT output {' or '.join(_c1_skip)} in this chunk — they "
              "will be generated in chunk 2.\n"
            + f"\n{_note}\n"
        )
    else:
        _chunk_format = """
Output ONLY these two XML sections (chunk 2 of 2):

<key_distinctions>
2-5 distinctions (each: "claim" = the contrast + why it matters, "supporting_text" = verbatim quote). Prioritize technical-term contrasts, competing positions, normal-vs-pathological.
</key_distinctions>

<theoretical_tensions>
2-4 tensions (each: "claim" = the tension + diverging positions, "supporting_text" = verbatim quote). Prioritize opposing-force dialectics, school-vs-school debates, unresolved ambiguities. Name BOTH poles.
</theoretical_tensions>

Do NOT output executive_summary, bullet_points, or thorough_summary in this chunk — they were generated in chunk 1.
"""
    # Replace the output_format section of the full prompt.
    # V0.05: the replacement window ends at "Chapter content:" (or end of
    # prompt) — the chapter text always survives the chunk override.
    _end_guard = r'(?=\nChapter content:|\nFull chapter content:|$)'
    # Try JSON-format first (academic_rigor path)
    _pattern_json = re.compile(
        r'Output a JSON object with (?:five|these) sections:.*?' + _end_guard,
        re.DOTALL,
    )
    if _pattern_json.search(full_prompt):
        return _pattern_json.sub(
            _chunk_format.strip()
            + '\n\nDo NOT describe the JSON structure. Only output the JSON object.',
            full_prompt,
        )
    # Try XML-format
    _pattern_xml = re.compile(
        r'You MUST output exactly these (?:five )?XML sections:.*?' + _end_guard,
        re.DOTALL,
    )
    if _pattern_xml.search(full_prompt):
        return _pattern_xml.sub(_chunk_format.strip(), full_prompt)
    # Fallback: append the chunk instruction
    return full_prompt + "\n\n" + _chunk_format


__all__ = [
    "build_thorough_followup",
    "build_dedicated_thorough_prompt",
    "build_dedicated_bullet_prompt",
    "build_missing_keywords_reprompt",
    "build_chunked_prompt",
]


# ── V18.20.4.7 (P5 phase 2 / W-a3) ────────────────────────────────────────
# The dead V18.6.3 twin was deleted: ``PromptContext`` +
# ``build_primary_prompt`` (~305 lines) were the verbatim copy kept after
# the V18.6.4 rollback restored the LIVE inline
# ``Summarizer._build_prompt`` (summarizer.py). ZERO runtime callers
# tree-wide (only the characterization tests, removed with it); the 5
# live pure functions above are untouched.
