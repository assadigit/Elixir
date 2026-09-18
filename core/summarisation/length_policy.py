"""V0.05 (rig audit F9): source-relative length policy — the single source
of truth for every summary-section length target.

THE GENERAL RULE (book-agnostic, chapter-agnostic)
==================================================

A summary section must NEVER be instructed to be longer than a fraction of
its source. The V0.04 rig run (97-Things, llama.cpp + Bonsai 27B) proved the
failure mode end-to-end: the prompts demanded an absolute "800-1200 word"
thorough summary, the wizard promised it, the 800-word floor FORCED a
dedicated expansion call, and the bullet machinery pushed every chapter
toward 30+ bullets — for chapters that are **321-441 words long**. The
delivered "Thorough Summary" sections measured 549-940 words = **1.55x-2.76x
the source**. A summary longer than its source is not a summary: the model
must pad, elaborate, and invent plausible-sounding context to satisfy the
absolute number (hallucination-by-instruction — the rig's thorough sections
contain invented examples the source never states).

Every length target in this app therefore SCALES to the source:

  * thorough summary: at most ~45% of the source (never more than the
    source, never more than the historical 1200-word ceiling, at least ~120
    words when the source itself is that small);
  * executive summary: at most ~20% of the source (floored at ~60 words,
    ceiling stays 250);
  * bullet points: one distinct takeaway per ~50 source words (4-40, the
    historical range).

Scaling is a PURE function of the source word count — same rule for a
1-page essay and a 40-page chapter. Nothing here knows about any book.

Consumers (all read the SAME functions — one source of truth):
  * ``Summarizer._build_prompt`` (inline academic + non-academic formats)
  * ``PromptManager.render`` (template placeholders + the legacy-absolute-
    number backstop for user-edited templates)
  * ``prompt_assembly`` dedicated thorough / bullet / exec-from-thorough
    prompts
  * the thorough-expansion threshold (``_new_threshold`` — was the hardcoded
    800-word floor) and the bullet-expansion threshold (was ``< 30``)
  * ``BulletPipeline.apply_f1_length_validation`` (truncation caps)
  * the thorough-theorist floor (skip the 150-300-word append when the
    thorough is already at its scaled ceiling)
  * ``structured_io.build_json_instruction`` (json-mode schema wording)
"""
from __future__ import annotations

import re

# ── Policy constants (one place, deliberately explicit) ─────────────────────

# A summary section may target at most this fraction of its source's words.
THOROUGH_SOURCE_FRACTION = 0.45
EXEC_SOURCE_FRACTION = 0.20
# Absolute ceilings — the historical prompt maxima, kept as hard caps so a
# 40-page chapter's thorough summary stays the documented 1200-word deliverable.
THOROUGH_ABS_MAX = 1200
EXEC_ABS_MAX = 250
# Small-source floors: for a source smaller than this, the target scales
# down with the source (never instructing MORE than the source itself).
THOROUGH_SMALL_SOURCE = 120
EXEC_SMALL_SOURCE = 60
# Ratio between the target's low and high bound.
THOROUGH_LO_FRACTION = 0.6
EXEC_LO_FRACTION = 0.6
# Bullets: one takeaway per this many source words, clamped to the historic
# 4..40 window (the old prompt demanded "20-40" unconditionally).
BULLET_WORDS_PER_TAKEAWAY = 50
BULLET_ABS_MIN = 4
BULLET_ABS_MAX = 40
BULLET_LO_FRACTION = 0.67
# A ship-time section that exceeds this multiple of its scaled target (AND
# this much of its source) is logged as an expansion-ratio warning.
EXPANSION_WARN_TARGET_MULTIPLE = 1.5
EXPANSION_WARN_SOURCE_FRACTION = 0.60


def count_source_words(text: str | None) -> int:
    """Word count of the source chapter (whitespace-separated tokens).

    Deliberately naive — it mirrors how the model reads the source, not how
    a tokenizer counts. Markdown emphasis characters are not words.
    """
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


def thorough_target(source_words: int) -> tuple[int, int]:
    """(lo, hi) word target for the thorough summary, scaled to the source.

    hi = min(THOROUGH_ABS_MAX, max(round(0.45 * W), min(120, W)))
       — never above 1200, never above the source (both branches are ≤ W),
         at least ~120 for anything but tiny sources.
    lo = max(80, round(hi * 0.6)).
    """
    w = max(0, int(source_words))
    hi = min(THOROUGH_ABS_MAX, max(round(THOROUGH_SOURCE_FRACTION * w),
                                   min(THOROUGH_SMALL_SOURCE, w)))
    lo = max(80, round(hi * THOROUGH_LO_FRACTION))
    if lo > hi:
        lo = hi
    return lo, hi


def executive_target(source_words: int) -> tuple[int, int]:
    """(lo, hi) word target for the executive summary, scaled to the source."""
    w = max(0, int(source_words))
    hi = min(EXEC_ABS_MAX, max(round(EXEC_SOURCE_FRACTION * w),
                               min(EXEC_SMALL_SOURCE, w)))
    lo = max(40, round(hi * EXEC_LO_FRACTION))
    if lo > hi:
        lo = hi
    return lo, hi


def bullet_target(source_words: int) -> tuple[int, int]:
    """(lo, hi) bullet-count target, scaled to the source.

    hi = clamp(round(W / 50), 4, 40); lo = max(3, round(hi * 0.67)).
    A 340-word chapter targets ~4-7 bullets (the rig shipped 29-36 — one
    bullet per 12 words, nearly the source restated as bullets).
    """
    w = max(0, int(source_words))
    hi = max(BULLET_ABS_MIN, min(BULLET_ABS_MAX, round(w / BULLET_WORDS_PER_TAKEAWAY)))
    lo = max(3, round(hi * BULLET_LO_FRACTION))
    if lo > hi:
        lo = hi
    return lo, hi


def bullet_cap(source_words: int) -> int:
    """V0.06 (rig audit F4): the HARD cap on bullets for a chapter this size.

    The same ``hi`` every prompt target uses (``bullet_target``), exposed as
    the single source of truth for the insertion-site + ship-time caps: the
    V0.05 length policy gated only the dedicated expansion call, while
    Tier-2 gap-fill, scholar gap-fill, and quarantine recovery kept appending
    freely (the rig shipped 19/18/15/14/12 bullets against 5-7/5-7/6-9/6-9/5-8
    targets). Consumers treat a result ``<= 0`` as "no cap" (fail-open).
    """
    return bullet_target(source_words)[1]


# ── Prompt-facing strings (one phrasing, every consumer) ────────────────────

def thorough_words_phrase(source_words: int) -> str:
    lo, hi = thorough_target(source_words)
    return f"{lo}-{hi} word"


def exec_words_phrase(source_words: int) -> str:
    lo, hi = executive_target(source_words)
    return f"{lo}-{hi} word"


def bullet_range_phrase(source_words: int) -> str:
    lo, hi = bullet_target(source_words)
    return f"{lo}-{hi}"


def length_budget_block(
    source_words: int,
    include_executive: bool = True,
    include_thorough: bool = True,
    include_keypoints: bool = True,
) -> str:
    """The LENGTH BUDGET prompt block — appended to the primary prompt.

    States the chapter's own length, the scaled targets, and the compression
    contract: a summary section must be SHORTER than its source; never pad,
    elaborate, or invent content to reach a length. This block overrides any
    other length numbers in the prompt (belt-and-braces for user-edited
    templates that still carry absolute ranges — see the backstop in
    ``prompt_manager``).
    """
    lines = [
        f"LENGTH BUDGET — this chapter is approximately {source_words} words."
        " All section-length targets below are scaled to that length and"
        " OVERRIDE any other length numbers in this prompt:",
    ]
    if include_executive:
        elo, ehi = executive_target(source_words)
        lines.append(
            f"- executive_summary: {elo}-{ehi} words."
        )
    if include_keypoints:
        blo, bhi = bullet_target(source_words)
        lines.append(
            f"- bullet_points: {blo}-{bhi} bullets (one distinct takeaway per"
            " ~50 source words — do NOT fragment or pad to inflate the count)."
        )
    if include_thorough:
        tlo, thi = thorough_target(source_words)
        lines.append(
            f"- thorough_summary: {tlo}-{thi} words."
        )
    lines.append(
        "COMPRESSION CONTRACT: this is a SUMMARY — every section must be"
        " SHORTER than the chapter itself. If you cannot fill a section's"
        " target with content the source actually states, write less; NEVER"
        " pad, elaborate, generalize, or invent examples to reach a length."
        " A shorter, faithful summary is correct; a longer, padded one is a"
        " defect."
    )
    return "\n".join(lines)


# ── Ship-time honest measurement ────────────────────────────────────────────

def expansion_audit(
    source_words: int,
    exec_words: int,
    thorough_words: int,
) -> list[str]:
    """Honest per-section compression-ratio findings (for the log line).

    Returns human-readable findings; empty when every section is within
    policy. A section flags when it exceeds 1.5x its scaled target AND
    60% of its source — i.e. it is in expansion territory, not summary
    territory. Measurement only — truncation is NOT done here (prose must
    never be cut by a ratio heuristic; the F1 caps and the prompt-side
    scaling are the enforcement).
    """
    findings: list[str] = []
    if source_words > 0 and thorough_words > 0:
        _tlo, thi = thorough_target(source_words)
        if (thorough_words >= thi * EXPANSION_WARN_TARGET_MULTIPLE
                and thorough_words >= source_words * EXPANSION_WARN_SOURCE_FRACTION):
            findings.append(
                f"thorough {thorough_words}w = {thorough_words / source_words:.1f}x "
                f"its {source_words}w source (target {thi}w) — expansion, not summary"
            )
    if source_words > 0 and exec_words > 0:
        _elo, ehi = executive_target(source_words)
        if (exec_words >= ehi * EXPANSION_WARN_TARGET_MULTIPLE
                and exec_words >= source_words * EXPANSION_WARN_SOURCE_FRACTION):
            findings.append(
                f"exec {exec_words}w = {exec_words / source_words:.1f}x "
                f"its {source_words}w source (target {ehi}w) — expansion, not summary"
            )
    return findings


# ── Legacy absolute-number backstop (user-edited templates) ─────────────────
# The builtin templates ship with {{...}} placeholders, but a user-edited
# copy (or an imported old template) may still carry the historical absolute
# ranges. Every rendered prompt passes through apply_backstop so the class
# can never re-enter silently. Patterns are deliberately narrow: they match
# the exact builtin phrasings, not arbitrary numbers.

_BACKSTOP_RULES: list[tuple[re.Pattern[str], str]] = [
    # "An 800-1200 word detailed analysis/walkthrough/narrative/literary analysis"
    # (the *phrase* helpers already include the trailing "word" — the
    # replacement templates below must NOT append it again)
    (re.compile(r"\b800\s*-\s*1200\s+word\b"), "{thorough_words}"),
    (re.compile(r"\b1000\s*-\s*1500\s+word\b"), "{thorough_words}"),
    # "A 150-250 word overview/narrative overview" (executive)
    (re.compile(r"\b150\s*-\s*250\s+word\b"), "{exec_words}"),
    (re.compile(r"\b200\s*-\s*300\s+word\b"), "{exec_words}"),
    # "20-40 distinct key takeaways" / "A comprehensive list of 20-40 ..."
    (re.compile(r"\b20\s*-\s*40\s+distinct\b"), "{bullet_range} distinct"),
    # academic json inline: "15-25 findings" (bullets + thorough)
    (re.compile(r'"bullet_points":\s*15\s*-\s*25\s+findings'),
     '"bullet_points": {bullet_range} findings'),
    (re.compile(r'"thorough_summary":\s*15\s*-\s*25\s+findings'),
     '"thorough_summary": {bullet_range} findings'),
]


def apply_backstop(rendered: str, source_words: int) -> str:
    """Replace legacy absolute length ranges with the scaled targets.

    Runs on every rendered prompt AFTER placeholder substitution. When a
    template already uses the {{...}} placeholders the patterns find nothing
    and the prompt is returned unchanged; a user-edited template carrying
    the old absolute numbers gets the source-scaled numbers instead.
    """
    if not rendered:
        return rendered
    subs = {
        "thorough_words": thorough_words_phrase(source_words),
        "exec_words": exec_words_phrase(source_words),
        "bullet_range": bullet_range_phrase(source_words),
    }
    out = rendered
    for pattern, replacement in _BACKSTOP_RULES:
        out = pattern.sub(replacement.format(**subs), out)
    return out
