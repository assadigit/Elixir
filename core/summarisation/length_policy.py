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

Every length target in this app therefore SCALES to the source — but the
V0.07 output-regression fix restores V18's richness contract for NORMAL
chapters (the V0.05 scaling over-corrected: a 1000-word chapter was told to
write a 270-450-word thorough and 13-20 bullets where MarkItDown V18
delivered 800-1200 words and 30-40 bullets — the user-reported "thin
summary / 3 bullets" regressions):

  * thorough summary: for sources < 800 words, at most ~45% of the source
    (the 97-Things anti-padding fix); for sources >= 800 words, at least
    V18's 800-word contract, growing with 0.45x the source — V0.4.23:
    NO absolute ceiling (the historical 1200-word cap is REMOVED by user
    directive: a thorough summary may be "as long as necessary for full
    coverage"; the never-exceed-the-source and never-pad rules remain).
    V0.6.2: for THIN sources (< 800) the 45% fraction is the TRUE cap —
    the small-source floor may never push the target past it;
  * executive summary: at most ~20% of the source (ceiling stays 250).
    V0.6.2: thin sources obey the 20% cap exactly (the 60-word floor is
    capped by the fraction);
  * bullet points: one distinct takeaway per ~25 source words as the
    COVERAGE FLOOR GUIDANCE (4-40) — V0.4.23: there is NO maximum and NO
    ship-time cap for NORMAL chapters (user directive: bullets "can be
    as long as necessary for full coverage"). The count reducers are the
    semantic dedup, consolidation, and the filler floor — never a
    numeric cap. V0.6.2: THIN sources (< 800) get a bounded prompt
    range ("N-M") + the source-scaled ADDITIVE budget via
    ``bullet_cap`` (gap-fill/resurrection additions only — never
    primary bullets) + the combined budget below;
  * V0.6.2 (the thin-book fix): THIN chapters (< 800 words — the
    user-reported book with 1-2 page chapters) additionally get a
    COMBINED BUDGET: exec + bullets + thorough together are prompted
    under ~75% of the source and MEASURED at ship time
    (``expansion_audit`` flags a combined ratio >= 1.0x — the
    user-reported "summaries risen above the original source word
    count").

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
# V0.4.23 (user directive — "no limit for bullet point quantity or thorough
# summary; they can be as long as necessary for full coverage"):
#   * THOROUGH_ABS_MAX (the historical 1200-word ceiling) is REMOVED — the
#     thorough target grows with the source (0.45x), bounded only by the
#     never-exceed-the-source and never-pad rules;
#   * BULLET_ABS_MAX is now a GUIDANCE clamp for the floor phrase only —
#     bullet_cap() returns 0 ("no cap") and NO ship-time/insertion cap
#     exists anywhere; dedup + consolidation + the filler floor are the
#     only reducers.
EXEC_ABS_MAX = 250
# V0.07 (output-regression fix): V18's thorough contract — a chapter of at
# least this many words is asked for at least 800 words of thorough summary
# (MarkItDown V18 demanded "800-1200" unconditionally; sources below this
# keep the V0.05 45%-of-source anti-padding rule instead).
THOROUGH_V18_FLOOR = 800
# Small-source floors: for a source smaller than this, the target scales
# down with the source (never instructing MORE than the source itself).
# V0.6.2 (thin-content fix): these floors are now SOFT anchors — a floor
# may never push a target past its source fraction (the fraction is the
# TRUE cap; see thorough_target/executive_target). Kept as the documented
# historical values for the 300-800-word band where they are inert.
THOROUGH_SMALL_SOURCE = 120
EXEC_SMALL_SOURCE = 60
# Ratio between the target's low and high bound.
THOROUGH_LO_FRACTION = 0.6
EXEC_LO_FRACTION = 0.6
# Bullets: one takeaway per this many source words, clamped to the historic
# 4..40 window (the old prompt demanded "20-40" unconditionally).
# V0.07 (output-regression fix): 50 -> 25. At 50, a 1000-word chapter was
# told "13-20 bullets" (ship cap 20) where V18 delivered 30-40 — the
# user-reported bullet collapse. At 25: W=1000 -> (27, 40), W>=1250 -> 40;
# tiny rig chapters (344-445 words) still scale down to 14-18.
BULLET_WORDS_PER_TAKEAWAY = 25
BULLET_ABS_MIN = 4
BULLET_ABS_MAX = 40
BULLET_LO_FRACTION = 0.67
# A ship-time section that exceeds this multiple of its scaled target (AND
# this much of its source) is logged as an expansion-ratio warning.
EXPANSION_WARN_TARGET_MULTIPLE = 1.5
EXPANSION_WARN_SOURCE_FRACTION = 0.60
# V0.6.2 (user-reported thin-book bug): the thin-chapter boundary and the
# combined budget. THIN_SOURCE_WORDS is deliberately the SAME boundary as
# THOROUGH_V18_FLOOR (the V0.05 small-source regime) — no new magic number;
# the thin regime is where the section targets are small enough that their
# SUM can reach (and, pre-fix, exceed) the source's own word count (the
# user's book with 1-2 page chapters shipped exec + bullets + thorough
# ABOVE the source, padded with rephrased near-duplicate bullets).
THIN_SOURCE_WORDS = THOROUGH_V18_FLOOR
# The thin-chapter COMBINED budget: exec + bullets + thorough together are
# prompted to stay under ~this fraction of the source (75% leaves real
# compression; the honest measurement flags >= 100%).
THIN_COMBINED_FRACTION = 0.75


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

    V0.07 (output-regression fix) — two regimes:

    * W >= THOROUGH_V18_FLOOR (800): V18's contract — at least 800 words,
      growing with 0.45 x W. V0.4.23: NO absolute ceiling (the 1200-word
      cap is removed — full coverage outranks brevity; the compression
      contract still forbids padding and exceeding the source).
    * W < 800: the V0.05 anti-padding regime — at most ~45% of the source
      (the 97-Things rig fix: a 321-441-word chapter must not be told to
      write 800-1200 words = 2.7x its source).

    V0.6.2 (user-reported thin-book bug): the 120-word small-source floor
    may never push the target PAST the 45% fraction. Pre-fix the floor was
    taken inside the max uncapped — a 150-word chapter was told to write a
    120-word thorough (80% of its source) and a 100-word chapter a
    100-word thorough (100%!) — instruction-driven padding on thin
    chapters (the module docstring's own "hallucination-by-instruction"
    failure mode). The fraction is now the TRUE cap: hi = min(W,
    round(0.45 x W)). The 80-word lo floor applies only when the hi can
    support it (no more point targets like "68-68 word" that force a
    minimum a thin source cannot honestly fill).

    lo = max(80, round(hi * 0.6)) when hi >= 80, else round(hi * 0.6).
    """
    w = max(0, int(source_words))
    if w >= THOROUGH_V18_FLOOR:
        hi = max(round(THOROUGH_SOURCE_FRACTION * w), THOROUGH_V18_FLOOR)
    else:
        # V0.6.2: the fraction is the cap — the small-source floor is
        # inert for thin sources (it existed for the 300-800-word band,
        # where 0.45xW >= 120 anyway and this branch is byte-identical).
        hi = min(w, round(THOROUGH_SOURCE_FRACTION * w))
    lo = round(hi * THOROUGH_LO_FRACTION)
    if hi >= 80:
        lo = max(lo, 80)
    if lo > hi:
        lo = hi
    return lo, hi


def executive_target(source_words: int) -> tuple[int, int]:
    """(lo, hi) word target for the executive summary, scaled to the source.

    V0.6.2 (user-reported thin-book bug): the 60-word small-source floor
    may never push the target past the 20% fraction (pre-fix a 100-word
    chapter was told to write a 60-word exec = 60% of its source). The
    40-word lo floor applies only when the hi can support it.
    """
    w = max(0, int(source_words))
    hi = min(EXEC_ABS_MAX, round(EXEC_SOURCE_FRACTION * w))
    lo = round(hi * EXEC_LO_FRACTION)
    if hi >= 40:
        lo = max(lo, 40)
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
    """V0.6.2 (user-reported thin-book bug): TWO REGIMES.

    * THIN sources (W < THIN_SOURCE_WORDS = 800): the source-scaled
      bullet_target hi — the V0.06 rig-audit F4-b ADDITIVE budget. The cap
      ONLY ever bounds the ADDITIVE machinery (Tier-2 gap-fill, scholar
      gap-fill, quarantine resurrection) — never primary bullets — so
      this bounds exactly the machinery that padded the user's thin book
      (gap-fill kept inserting rephrased bullets with no room limit:
      "repetitive bullets which rephrased the same concepts").
    * NORMAL sources: 0 — the V0.4.23 no-cap user directive stands
      unchanged (bullets "can be as long as necessary for full coverage";
      the V0.4.22 ch.4 displacement failure that removed the cap was a
      content-rich chapter, not a thin one).

    Consumers treat a result ``<= 0`` as "no cap" (fail-open).
    """
    w = max(0, int(source_words))
    if w >= THIN_SOURCE_WORDS:
        return 0
    _lo, hi = bullet_target(w)
    return hi


# ── Prompt-facing strings (one phrasing, every consumer) ────────────────────


def thorough_words_phrase(source_words: int) -> str:
    lo, hi = thorough_target(source_words)
    return f"{lo}-{hi} word"


def exec_words_phrase(source_words: int) -> str:
    lo, hi = executive_target(source_words)
    return f"{lo}-{hi} word"


def bullet_range_phrase(source_words: int) -> str:
    """V0.4.23: the prompt phrase for the bullet count — a coverage FLOOR
    with NO maximum ("at least N"), per the user's no-limit directive.
    Legacy callers that interpolated a range now read "at least N",
    which is the intended contract: as many bullets as full coverage
    requires, never fewer than the scaled floor, never padded.

    V0.6.2 (user-reported thin-book bug): THIN sources (W < 800) get a
    BOUNDED range ("N-M") instead — "at least N ... NO MAXIMUM" on a
    340-word chapter is an explicit invitation to rephrase the same
    concepts into more bullets when the chapter has fewer distinct
    ideas than N (the user's repetitive-bullet report). The hi is the
    same source-scaled bullet_target every coverage floor uses.
    """
    w = max(0, int(source_words))
    lo, hi = bullet_target(w)
    if w >= THIN_SOURCE_WORDS:
        return f"at least {lo}"
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
    # V0.6.2 (user-reported thin-book bug): the THIN-chapter variant —
    # bounded bullet count + the combined budget + the anti-repetition
    # contract. Normal chapters keep the V0.4.23 no-maximum wording
    # unchanged (their sections cannot sum past the source).
    _thin = 0 < source_words < THIN_SOURCE_WORDS
    if include_executive:
        elo, ehi = executive_target(source_words)
        lines.append(f"- executive_summary: {elo}-{ehi} words.")
    if include_keypoints:
        blo, bhi = bullet_target(source_words)
        if _thin:
            lines.append(
                f"- bullet_points: {blo}-{bhi} bullets. This is a THIN"
                " chapter: emit ONE bullet per DISTINCT fact, claim, or"
                " concept the chapter actually states. NEVER rephrase an"
                " already-stated idea as an additional bullet — a"
                " rephrased bullet is a defect, not coverage. If the"
                " chapter has fewer distinct ideas than the floor, emit"
                " fewer bullets; never fragment or pad to inflate the"
                " count."
            )
        else:
            lines.append(
                f"- bullet_points: at least {blo} bullets — there is NO"
                " MAXIMUM: add as many distinct takeaways as the chapter's"
                " content requires for FULL coverage (every enumerated list"
                " item, every named contributor, every distinct finding)."
                " Never fragment or pad to inflate the count; a bullet must"
                " carry content."
            )
    if include_thorough:
        tlo, thi = thorough_target(source_words)
        lines.append(
            f"- thorough_summary: {tlo}-{thi} words (the target scales with"
            " the chapter; no absolute ceiling — write as much as full"
            " coverage requires)."
        )
    if _thin:
        _combined_aim = max(30, round(THIN_COMBINED_FRACTION * source_words))
        lines.append(
            f"- COMBINED BUDGET: the sections above TOGETHER (executive +"
            f" bullet points + thorough) must stay WELL UNDER this chapter's"
            f" own {source_words} words — aim for ~{_combined_aim} words"
            " total. The three sections are one summary of one thin"
            " chapter, not three parallel expansions of it: do not restate"
            " a bullet's content in the prose sections or vice versa. If a"
            " section target cannot be filled with content the source"
            " actually states, write less."
        )
    lines.append(
        "COMPRESSION CONTRACT: this is a SUMMARY — every section must be"
        " SHORTER than the chapter itself. If you cannot fill a section's"
        " target with content the source actually states, write less; NEVER"
        " pad, elaborate, generalize, or invent examples to reach a length."
        " A shorter, faithful summary is correct; a longer, padded one is a"
        " defect. Coverage is bounded by the SOURCE's content, never by a"
        " numeric cap."
    )
    return "\n".join(lines)


# ── Ship-time honest measurement ────────────────────────────────────────────


def expansion_audit(
    source_words: int,
    exec_words: int,
    thorough_words: int,
    bullet_words: int = 0,
) -> list[str]:
    """Honest per-section compression-ratio findings (for the log line).

    Returns human-readable findings; empty when every section is within
    policy. A section flags when it exceeds 1.5x its scaled target AND
    60% of its source — i.e. it is in expansion territory, not summary
    territory. Measurement only — truncation is NOT done here (prose must
    never be cut by a ratio heuristic; the F1 caps and the prompt-side
    scaling are the enforcement).

    V0.6.2 (user-reported thin-book bug): the COMBINED finding — for thin
    sources (W < 800) the three sections together (exec + bullet words +
    thorough) at or above the source's own word count is exactly the
    user-reported defect ("the exec summary + bullet point + thorough
    summary risen above the original source word count"). Thin-scoped:
    normal chapters keep the V18 richness contract where the combined
    sections may legitimately reach the source's scale.
    """
    findings: list[str] = []
    if source_words > 0 and thorough_words > 0:
        _tlo, thi = thorough_target(source_words)
        if (
            thorough_words >= thi * EXPANSION_WARN_TARGET_MULTIPLE
            and thorough_words >= source_words * EXPANSION_WARN_SOURCE_FRACTION
        ):
            findings.append(
                f"thorough {thorough_words}w = {thorough_words / source_words:.1f}x "
                f"its {source_words}w source (target {thi}w) — expansion, not summary"
            )
    if source_words > 0 and exec_words > 0:
        _elo, ehi = executive_target(source_words)
        if (
            exec_words >= ehi * EXPANSION_WARN_TARGET_MULTIPLE
            and exec_words >= source_words * EXPANSION_WARN_SOURCE_FRACTION
        ):
            findings.append(
                f"exec {exec_words}w = {exec_words / source_words:.1f}x "
                f"its {source_words}w source (target {ehi}w) — expansion, not summary"
            )
    if 0 < source_words < THIN_SOURCE_WORDS:
        _combined = max(0, exec_words) + max(0, bullet_words) + max(0, thorough_words)
        if _combined >= source_words:
            findings.append(
                f"combined sections {_combined}w = {_combined / source_words:.1f}x "
                f"the {source_words}w source — over-generation, not summary "
                f"(thin chapter: the sections must sum to LESS than the source)"
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
    (
        re.compile(r'"bullet_points":\s*15\s*-\s*25\s+findings'),
        '"bullet_points": {bullet_range} findings',
    ),
    (
        re.compile(r'"thorough_summary":\s*15\s*-\s*25\s+findings'),
        '"thorough_summary": {bullet_range} findings',
    ),
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
