"""V0.6.4 — the Summarizer Tool's fine-tuned depth prompts.

The user supplied three prompt texts (Fast / Standard / Thorough) and
directed they be used VERBATIM for the standalone Summarizer Tool. They
live here as code constants (the V0.6.1 precedent: a versioned prompt
contract pinned by tests — NOT a ``prompts/`` bank file, so the
prompt-manifest / eval-baseline identity is untouched and no
always-overwrite re-sync can silently change the tool's behavior).

Design notes:
  - Wording is the user's, verbatim. Only the chat-mangled line breaks were
    re-flowed (the pasted Thorough text had ``STRICT RULES:- Use ONLY…``
    run together on one line).
  - Every depth carries ``"Write in the same language as the text."`` —
    the Farsi fix (requirement 4). The old path rendered the shared
    ``default.md`` bank prompt with an empty ``{{language}}`` variable, so
    a Farsi paste came back summarized (and translated) in English.
  - ``render_tool_prompt`` keeps the V18.2.21 prompt-injection defense
    (``wrap_untrusted`` fence) with the V18.2.29 low-bit-quant skip, and
    fails open if the sanitizer crashes (the ``render_template``
    precedent: hardening, never a gate).
  - ``normalize_depth_headings`` upgrades the bare section labels the
    FORMAT contract elicits (``Overview:``, ``"Key Points":`` …) into
    ``##`` markdown headings so the docx/pdf writers emit real Heading
    styles and the Obsidian formatter can map callouts.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# max_tokens per depth — unchanged from the V11 contract (the token budget
# is a ceiling, not a target: every depth prompt's LENGTH rules constrain
# the actual output far below these).
DEPTH_MAX_TOKENS: dict[str, int] = {
    "fast": 1024,
    "standard": 2048,
    "thorough": 4096,
}

DEFAULT_DEPTH = "standard"

# ── The user-supplied depth prompts (verbatim) ──────────────────────────────

TOOL_PROMPTS: dict[str, str] = {
    "fast": (
        "You are a summarizer. Your only job is to shorten the text you are given. "
        "You never write new content.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY information that is written in the text. Do not add facts, "
        "examples, opinions, advice, or explanations from your own knowledge.\n"
        "- If something is unclear or missing in the text, leave it out. Never guess.\n"
        "- Keep names, numbers, dates, and technical terms exactly as they appear.\n"
        "- Write in the same language as the text.\n"
        "- Do not write an introduction or a closing sentence. Start directly with "
        "the summary.\n\n"
        "FORMAT:\n"
        "1. One or two sentences that state the main point of the text.\n"
        "2. Then a bullet list of the most important facts or ideas. Maximum 10 "
        "bullets. Each bullet must be one or two short lines.\n\n"
        "LENGTH:\n"
        "Aim for about 200 words. The summary must NEVER go above 300 words. If the "
        "original text is short, make the summary even shorter. The summary must "
        "never be longer than the original text. Skip minor examples, side stories, "
        "and small details. Keep the main ideas and the most important facts."
    ),
    "standard": (
        "You are a summarizer. Your only job is to condense and organize the text "
        "you are given. You never write new content.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY information that is written in the text. Do not add facts, "
        "examples, opinions, advice, conclusions, or explanations from your own "
        "knowledge.\n"
        "- If something is unclear or missing in the text, leave it out. Never "
        "guess.\n"
        "- Do not judge or evaluate the text. Report what it says, not what you "
        "think about it.\n"
        "- Keep names, numbers, dates, and technical terms exactly as they appear.\n"
        "- Write in the same language as the text.\n"
        "- Do not write an introduction or a closing sentence. Start directly with "
        "the summary.\n\n"
        "FORMAT:\n"
        '1. "Overview": 2 to 3 sentences explaining what the text is about and its '
        "main message.\n"
        '2. "Key Points": a bullet list of the main ideas, in the same order they '
        "appear in the text. Each bullet is 1 to 2 sentences.\n"
        '3. "Important Details": specific facts, numbers, names, or steps that '
        "matter (only if the text contains them).\n\n"
        'The "Key Points" and "Important Details" sections together must have a '
        "maximum of 20 bullets.\n\n"
        "LENGTH:\n"
        "The whole summary must NEVER go above 500 words. If the original text is "
        "short, make the summary much shorter. The summary must never be longer "
        "than the original text. Keep the main arguments and the important "
        "supporting details. Remove repetition, filler, and minor examples."
    ),
    "thorough": (
        "You are a summarizer. Your only job is to condense, organize, and "
        "structure the text you are given so that nothing important is lost. You "
        "never write new content.\n\n"
        "STRICT RULES:\n"
        "- Use ONLY information that is written in the text. Do not add facts, "
        "examples, opinions, advice, conclusions, or explanations from your own "
        "knowledge.\n"
        "- If something is unclear or missing in the text, leave it out. Never "
        "guess or fill gaps.\n"
        "- Do not judge or evaluate the text. Report what it says, not what you "
        "think about it.\n"
        "- Keep names, numbers, dates, quotes, and technical terms exactly as they "
        "appear.\n"
        "- If the author gives a definition, a step-by-step process, a list, or a "
        "comparison, keep its structure.\n"
        "- Write in the same language as the text.\n"
        "- Do not write an introduction or a closing sentence. Start directly with "
        "the summary.\n\n"
        "FORMAT:\n"
        "Write the summary as dense bullet points. Pack as much information as "
        "possible into each bullet, and use short, compact wording instead of long "
        "sentences. There is no limit on the number of bullets. Use as many as "
        "needed to cover the text.\n\n"
        '1. "Overview": 3 to 4 sentences on the purpose of the text, who or what '
        "it is about, and its main message.\n"
        '2. "Detailed Summary": follow the text\'s own structure. Create one '
        "heading for each major section or topic in the text. Under each heading, "
        "write bullet points covering its arguments, explanations, examples, and "
        "supporting evidence. Keep the original order.\n"
        '3. "Key Facts and Figures": a bullet list of all important numbers, '
        "dates, names, definitions, and terms that appear in the text.\n"
        '4. "Conclusions and Takeaways": the conclusions, recommendations, or '
        "final points that the AUTHOR states. If the author states none, write "
        '"None stated in the text." Do not create your own.\n\n'
        "LENGTH:\n"
        "There is no fixed word limit, but the summary must NEVER be longer than "
        "60 percent of the original text. Cover every main topic and keep the "
        "important examples and reasoning. Remove only repetition and filler."
    ),
}

# ── Prompt rendering ─────────────────────────────────────────────────────────


def render_tool_prompt(depth: str, text: str, model: str = "") -> tuple[str, int]:
    """Build the Summarizer Tool prompt for the chosen depth.

    Returns ``(prompt, max_tokens)``. An unknown depth falls back to the
    Standard prompt (the V0.6.0-era ``quality`` fallback contract).

    The untrusted source text rides the prompt inside the V18.2.21
    ``<untrusted_source>`` fence (with the V18.2.29 low-bit-quant skip and
    the fail-open-on-crash rule — both mirrored from
    ``PromptManager.render_template``).
    """
    template = TOOL_PROMPTS.get(depth, TOOL_PROMPTS[DEFAULT_DEPTH])
    max_tokens = DEPTH_MAX_TOKENS.get(depth, DEPTH_MAX_TOKENS[DEFAULT_DEPTH])

    fenced = text
    if text:
        try:
            from core.llm.model_taxonomy import is_low_bit_quant

            _skip_sanitizer = is_low_bit_quant(model or "")
            if _skip_sanitizer:
                logger.debug(
                    "V0.6.4: skipping prompt_sanitizer for low-bit model '%s' "
                    "(fence tags confuse the quant)",
                    model,
                )
            else:
                from core.llm.prompt_sanitizer import is_untrusted_wrapped, wrap_untrusted

                if not is_untrusted_wrapped(text):
                    text = wrap_untrusted(
                        text,
                        log_callback=lambda msg, level="INFO": logger.log(
                            getattr(logging, level, logging.WARNING), msg
                        ),
                    ).text
        except Exception as exc:  # noqa: BLE001 — defense-in-depth fail-open
            logger.debug(
                "tool_prompts: sanitizer skipped (%s: %s) — raw text substituted",
                type(exc).__name__,
                exc,
            )
        fenced = text

    prompt = f"{template}\n\n### TEXT TO SUMMARIZE ###\n\n{fenced}"
    return prompt, max_tokens


# ── Heading normalisation ────────────────────────────────────────────────────

# The section labels the depth prompts' FORMAT contract elicits (canonical
# display spelling). A line that BEGINS with one of these (optionally
# quoted, optionally colon-terminated, case-insensitive) is a heading —
# anything else (``Note: prose``, a label mid-sentence, a bullet) is
# ordinary text and is never touched.
_DEPTH_SECTION_LABELS: tuple[str, ...] = (
    "Overview",
    "Key Points",
    "Important Details",
    "Detailed Summary",
    "Key Facts and Figures",
    "Conclusions and Takeaways",
)
_CANONICAL_LABEL = {lbl.lower(): lbl for lbl in _DEPTH_SECTION_LABELS}
_LABELS_ALT = "|".join(re.escape(lbl) for lbl in _DEPTH_SECTION_LABELS)
# A line that is ONLY a (possibly quoted, possibly colon-terminated) label.
_DEPTH_LABEL_LINE_RE = re.compile(
    rf'^["\']?\s*({_LABELS_ALT})\s*[\"\']?\s*:?\s*$',
    re.IGNORECASE,
)
# A label followed by a colon and prose on the SAME line (the Standard
# FORMAT shape: ``"Overview": 2 to 3 sentences…``). The colon is REQUIRED
# here so a prose sentence merely STARTING with a label word
# (``Overview of the chapter…``) is never re-styled.
_DEPTH_LABEL_PROSE_RE = re.compile(
    rf'^["\']?\s*({_LABELS_ALT})\s*[\"\']?\s*:\s*(.+)$',
    re.IGNORECASE,
)


def normalize_depth_headings(text: str) -> str:
    """Upgrade bare depth-section labels to ``##`` markdown headings.

    The depth FORMAT contract elicits lines like ``Overview:``, ``"Key
    Points":`` (with or without trailing prose on the same line) — plain
    text the docx/pdf writers would render as body paragraphs. Normalising
    them to ``## Overview`` gives every output format real heading styles
    (and lets the Obsidian formatter map its callouts). Only the KNOWN
    labels are touched; ``Note: prose``, prose that merely starts with a
    label word, and labels inside sentences are left alone. Idempotent.
    """
    if not text:
        return text
    out_lines: list[str] = []
    for line in text.splitlines():
        m = _DEPTH_LABEL_PROSE_RE.match(line)
        if m:
            # Label + prose on one line → heading, then the prose on its
            # own line (``(.+)`` guarantees non-empty).
            out_lines.append(f"## {_CANONICAL_LABEL[m.group(1).lower()]}")
            out_lines.append(m.group(2).strip())
            continue
        m = _DEPTH_LABEL_LINE_RE.match(line)
        if m:
            out_lines.append(f"## {_CANONICAL_LABEL[m.group(1).lower()]}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)
