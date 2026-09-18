"""V18.6 (Phase 4, Task 4.3): Post-processing pure functions.

Extracted verbatim from ``Summarizer`` (god-class decomposition Stage 1).
These are pure string/bullet transforms — NO ``self``, NO LLM calls, NO
side effects. The ``Summarizer`` methods of the same name now delegate here.

**Extraction map** (what moved where):

| Summarizer method (old)        | post_processing function (new)        | Origin                        |
|--------------------------------|---------------------------------------|-------------------------------|
| ``_strip_thinking``            | ``strip_thinking``                    | response_parser (already pure)|
| ``_strip_markup_tags``         | ``strip_markup_tags``                 | response_parser (already pure)|
| ``_strip_narrative_from_thorough`` | ``strip_narrative_from_thorough`` | response_parser (already pure)|
| ``_truncate_to_sentences``     | ``truncate_to_sentences``             | response_parser (already pure)|
| ``_normalize_bullets``         | ``normalize_bullets``                 | Summarizer (was pure, no self)|
| ``_filter_thinking_bullets``   | ``classify_bullets``                  | Summarizer (core logic pure)  |

The first 4 were ALREADY thin delegates to ``response_parser`` — this module
just re-exports them under one roof for discoverability.

``normalize_bullets`` is extracted VERBATIM from ``Summarizer._normalize_bullets``
(V16.0.2 + V18.2.7/V18.2.9). It was already a pure function (operated only
on the ``bullets`` parameter, no ``self`` usage).

``classify_bullets`` is the CORE of ``Summarizer._filter_thinking_bullets`` —
the pattern-matching + classification logic. It returns
``(kept_bullets, drop_records)`` where ``drop_records`` is a list of
``(bullet, stage, reason, always_drop)`` tuples. The ``Summarizer`` method
keeps the quarantine-logging side-effect (it calls ``self.quarantine.add()``
for each drop record) but delegates the classification to this pure function.
This cleanly separates the pure decision logic from the I/O side-effect.

Characterization tests: ``tests/test_post_processing.py`` captures canned
inputs → golden outputs for every function. Byte-for-byte stability gate.
"""
from __future__ import annotations

import re

# Re-export the 4 functions that already live in response_parser.
# (They're imported here so callers have ONE import surface for all
# post-processing; the underlying implementation hasn't moved.)
from core.summarisation.response_parser import (
    strip_markup_tags,
    strip_narrative_from_thorough,
    strip_thinking,
    truncate_to_sentences,
)

# Type alias for the drop-record tuple returned by classify_bullets.
# (bullet_text, stage, reason, always_drop)
DropRecord = tuple[str, str, str, bool]


# ── normalize_bullets (extracted verbatim from Summarizer V16.0.2/V18.2.7) ──


def normalize_bullets(bullets: list[str]) -> list[str]:
    """V16.0.2: Universal bullet normalization pass. Strips inconsistent prefixes.

    V18.2.7: Improved to handle:
    - Gap-fill bullets that arrive as "**Author**: text" (strip the bold,
      keep the author name plain)
    - Remove "…" truncation artifacts (incomplete bullets)
    - Format academic years as italic + smaller: "Author (1980)" →
      "Author (<em style='font-size:0.9em'>1980</em>)" — but ONLY in the
      markdown output, not the raw bullets (the markdown formatter handles
      the <em> tag; here we just ensure the year is in parentheses)

    Extracted verbatim from ``Summarizer._normalize_bullets`` in V18.6
    (Phase 4, Task 4.3). The method was already pure (no ``self`` usage) —
    this is a mechanical move, not a logic change.
    """
    import re as _re
    normalized = []
    for bp in bullets:
        if not bp:
            continue
        bp_str = str(bp).strip()
        # Strip leading bullet markers: -, –, •, *, and numbered prefixes
        # V18.15.3.1: Loop to handle gap-fill bullets that arrive as
        # "- - Name: text" (double-dash — the prompt says "prefixed with '- '"
        # AND the model adds its own "- " prefix). The old single-pass regex
        # only stripped one dash, leaving "- Name: text" which rendered as a
        # double-dash bullet in the markdown output. Now we loop until no more
        # leading markers are found (max 3 passes — handles up to "- - - text").
        for _ in range(3):
            _prev = bp_str
            bp_str = _re.sub(r'^[-–•*]\s+', '', bp_str)
            bp_str = _re.sub(r'^\d+[.)]\s+', '', bp_str)
            if bp_str == _prev:
                break  # no change → all leading markers stripped
        # V18.2.7: Strip "KEY QUOTE:" prefix
        bp_str = _re.sub(r'^-?\s*KEY QUOTE:\s*', '', bp_str, flags=_re.IGNORECASE)
        # V18.2.9: Strip section-heading artifacts that leak into bullets:
        # "*Analysis:**", "*Conclusion:**", "## Analysis", etc.
        bp_str = _re.sub(r'^\*+(Analysis|Conclusion|Summary|Key Points?)\*+:?\s*$', '', bp_str, flags=_re.IGNORECASE)
        bp_str = _re.sub(r'^#+\s*(Analysis|Conclusion|Summary|Key Points?)\s*$', '', bp_str, flags=_re.IGNORECASE)
        # V18.2.9: Drop bullets that are just "con" or fragments < 15 chars
        # (these are truncation artifacts, not real bullets)
        if len(bp_str) < 15:
            continue
        # V18.2.7: If bullet starts with "**Author**:" (gap-fill format),
        # strip the bold markers but keep the author name
        bp_str = _re.sub(r'^\*\*([A-Z][^*]{2,60})\*\*:\s*', r'\1: ', bp_str)
        # V18.2.7: Remove trailing "…" or "...." (truncation artifacts)
        # These indicate an incomplete bullet — but rather than dropping,
        # we clean them. The content is still valuable.
        bp_str = _re.sub(r'\s*\.{2,}$', '.', bp_str)  # "…." → "."
        bp_str = _re.sub(r'\s*…$', '.', bp_str)  # "…" → "."
        # V18.2.9: Drop bullets that end mid-sentence (no terminal punctuation)
        # and are clearly truncated. A complete bullet must end with . ! ? or :
        # If it ends with a word + "were"/"and"/"the"/"of"/"to"/"in" etc., it's
        # truncated mid-sentence — drop it (better to omit than ship incomplete).
        _trailing_words = ('were', 'and', 'the', 'of', 'to', 'in', 'for', 'with',
                           'from', 'by', 'as', 'is', 'are', 'was', 'be', 'that',
                           'this', 'which', 'who', 'whose', 'its', 'their', 'his',
                           'her', 'our', 'your', 'an', 'a', 'or', 'but', 'not',
                           'have', 'has', 'had', 'will', 'would', 'could', 'should',
                           'may', 'might', 'can', 'shall', 'must', 'do', 'does', 'did')
        _words = bp_str.split()
        if _words and _words[-1].lower().rstrip('.,;:') in _trailing_words:
            # Truncated mid-sentence — skip this bullet
            continue
        bp_str = bp_str.strip()
        # Capitalize first letter
        if bp_str and bp_str[0].islower():
            bp_str = bp_str[0].upper() + bp_str[1:]
        if bp_str:
            normalized.append(bp_str)
    return normalized


# ── classify_bullets (core of Summarizer._filter_thinking_bullets) ──────────
#
# The patterns below are extracted VERBATIM from Summarizer._filter_thinking_bullets
# (V10.12.9 + V10.28.0 + V18.2.7). The Summarizer method keeps the
# quarantine-logging side-effect; this function does the pure classification.

_THINKING_STARTS = re.compile(
    r'^(?:\*?\*?)?(?:Analyze|Process|Draft|Check|Review|Refine|Identify|'
    r'Extract|Read|Understand|Consider|Note|Step|Plan|Determine|Evaluate|'
    r'Scan|Simplification|Translation|Final|Refinement|Polish|'
    r'I\s+will|I\'ll|Let\'s|Let me|Looks good|Wait|Ready|Okay|'
    r'One more|Now|First|Next|Then|After that|Moving on|'
    r'Input|Output|Rules?|Instructions?|Task|Format|Language|Condition|'
    r'Source Text|Target Concepts|Claims to verify|Summary to verify)\b',
    re.IGNORECASE
)
_BACKTICK_WORDS = re.compile(r'`[a-z_]+`')
_INTERNAL_MARKERS = re.compile(
    r'\*?\*?(?:Jargon|Context|Draft|Simplification|Translation|Refinement|Check|Original|Point)\s*[:\d]',
    re.IGNORECASE
)
_PROMPT_LEAKAGE = re.compile(
    r'(?:Source Text|Target Concepts|Task|Format|Language|Condition|Rules|Instructions|Output|Input)\s*:',
    re.IGNORECASE
)
# V18.12.2: Gap-fill prompt-leakage patterns. The V18.12.1 golden-master audit
# found that the V17.8 batch gap-fill sometimes leaked the prompt template
# into the bullets (e.g. "a single bullet point summarizing what the source
# sentence says about 'infant'", "the source sentence:", "What does this say
# about"). These are the LLM's instructions to itself, not summary content.
# The structural fix (re-filtering batch gap-fill bullets via
# _filter_thinking_bullets) is in summarizer.py; this regex is defense-in-depth
# so classify_bullets catches the phrases if they slip through elsewhere.
# V18.12.3: Added the Tier 2 _targeted_gap_fill prompt patterns discovered in
# the V18.12.2 audit ("me to write one bullet point", "Wait - the user asks",
# "Let me analyze", "The user wants me to"). The Tier 2 path now also filters
# structurally, but these patterns catch any other gap-fill that leaks them.
_GAP_FILL_PROMPT_LEAKAGE = re.compile(
    r'(?:a single bullet point summarizing what the source sentence says about|'
    r'the source sentence\s*:|'
    r'What does this say about|'
    r'summarizing what the source|'
    r'what the source sentence says|'
    r'me to write one bullet point|'
    r'Wait\s*[-–]\s*the user asks|'
    r'Let me analyze|'
    r'The user wants me to|'
    r'Write ONE bullet point|'
    r'prefixed with ["\']- ["\']|'
    # V18.14.3: bullet expansion prompt-leakage patterns
    r'extract all key concepts|'
    r'through the source systematically|'
    r'Wait,? let me re.?read|'
    r'So make sure ALL of|'
    r'Now let me organize|'
    r'Named contributors in order|'
    r'from what appears to be a|'
    r'likely by \w+,? given the)',
    re.IGNORECASE
)
_META_COMMENTARY = re.compile(
    r'(?:This captures|This is a complete sentence|not identical to any existing|'
    r'covers point \d+|This bullet|This keypoint|This item|This statement|'
    r'It is a complete sentence|This refers to the|This describes the|'
    r'This captures the|not identical to any|This entry)',
    re.IGNORECASE
)

# V18.19.2.1 (Audit Fix 1): Word-count chain-of-thought leakage.
# The V18.19.2.0 audit (audit/results/audit_V18.19.2.0_2026-08-28.md) found that
# 45% of the delivered Key Takeaways bullets were the model's INTERNAL reasoning
# in a surface form the existing thinking_filter did NOT catch:
#   - '"..." = 23 words - TOO LONG. Need to split.'
#   - '"..." = 20 - borderline. Let me split:'
#   - '"..." = 17 ✓ (Wait, use "emerges" not "emergs")'
# These are word-count annotations the model makes to itself while deciding
# whether to split a long bullet. They are NOT summary content. Categorized as
# structural contamination (always_drop=True) — same severity as thinking_process.
# Patterns (tested in tests/test_filter_thinking_wordcount_cot.py):
#   1. Trailing "= N [words/w/chars]? [-–—] (TOO LONG|borderline|long|short)" annotation
#   2. Trailing "= N ✓" word-count-with-checkmark annotation (the no-dash variant
#      the model uses for short bullets it's validating)
#   3. Trailing "Let me split:" continuation marker
#   4. Self-correction in parens: "(Wait, ...)" or "(use X not Y)"
_WORD_COUNT_COT = re.compile(
    r'=\s*\d+\s*(?:words?|w|chars?)?\s*[-–—]\s*'
    r'(?:TOO\s+LONG|borderline|too\s+long|too\s+short|long|short)\b',
    re.IGNORECASE
)
_WORD_COUNT_CHECKMARK = re.compile(
    r'=\s*\d+\s*✓',
    re.IGNORECASE
)
_LET_ME_SPLIT = re.compile(
    r'\bLet\s+me\s+split\b',
    re.IGNORECASE
)
_SELF_CORRECTION_PAREN = re.compile(
    r'\(\s*Wait\b',
    re.IGNORECASE
)
# V18.19.2.1 (Audit Fix 1b): Self-instruction leakage.
# Lines like "Using the chapter's own terminology", "Preserving all named
# contributors", "Preserve technical terminology" — the model instructing
# itself on strategy, not summary content. These appeared as standalone bullets
# in the V18.19.2.0 output.
_SELF_INSTRUCTION = re.compile(
    r'^(?:Using\s+the\s+\S+\s+(?:own\s+)?terminology|'
    r'Preserving\s+all\s+(?:named\s+)?(?:contributors|authors|terms)|'
    r'Preserve\s+(?:technical|all)\s+terminology|'
    r'Using\s+(?:the\s+)?(?:source|chapter)\'?s?\s+(?:own\s+)?(?:terminology|words|vocabulary))\b',
    re.IGNORECASE
)
# V18.19.2.1 (Audit Fix 1c): Bare validation checkmark lines.
# Lines like "AuthorI (1950) ✓" or "AuthorO (1958a) ✓" — the model's validation
# checklist, not summary content. A content bullet never ends in a bare ✓; the
# checkmark is the model marking "I included this author". Pattern: a line ending
# in an isolated ✓ (possibly with a trailing parenthetical like "(mentioned in
# context of resurrecting the term)"). NOTE: no \b before ✓ — ✓ (U+2713) is not a
# word character so \b won't match before it; use (?:^|\s) lookahead instead.
_BARE_CHECKMARK = re.compile(
    r'✓\s*(?:\([^)]*\))?\s*$'
)

# V18.20.3.2 (audit N1 / P0-2): model SELF-TALK patterns (mid-bullet,
# unanchored). The V18.20.3.1 real-rig run shipped two CoT planning lines as
# Key-Takeaways bullets:
#   "AuthorW (1968) - include this! Let me add it."
#   "AuthorI (1958) - be more specific. The source says \"AuthorI (1958)\" in
#    the context of the term being introduced. Actually, looking at the text: …"
# These are the model's note-to-self annotations about ITS OWN output. They
# pass every existing filter because they don't START with a thinking verb
# ("AuthorW (1968) - …") — the existing _THINKING_STARTS is start-anchored.
# Self-talk is structural contamination (always_drop=True): a bullet that
# discusses the summary-writing process is never summary content.
# NOTE: these patterns are also the judge-appeal carve-out (bullet_pipeline)
# — self-talk quoting the source defeats the source-overlap rescue, so the
# SAME regex list is exposed as SELF_TALK_PATTERNS for reuse.
SELF_TALK_PATTERNS = re.compile(
    r'(?:'
    r'\binclude this\b|'
    r'\bincluded this\b|'
    r'\blet\s+me\s+add\b|'
    r'\blet\s+me\s+include\b|'
    r'\blet\s+me\s+check\b|'
    r'\blet\s+me\s+verify\b|'
    r'\blet\s+me\s+make\s+sure\b|'
    r'\bbe\s+more\s+specific\b|'
    r'\bthe\s+source\s+says\b|'
    r'\bthe\s+text\s+says\b|'
    r'\bthe\s+prompt\s+says\b|'
    r'\blooking\s+at\s+the\s+text\b|'
    r'\blooking\s+at\s+the\s+source\b|'
    r'\bI\s+need\s+to\s+include\b|'
    r'\bI\s+should\s+include\b|'
    r'\bI\s+should\s+add\b|'
    r'\bnote\s+to\s+self\b|'
    r'\bWait,?\s+use\b|'
    r'\bActually,?\s+looking\s+at\b'
    r')',
    re.IGNORECASE,
)

# V18.20.3.4 (RC-1, audit v182033): process-scar patterns — the four defect
# classes that survived every existing filter in the V18.20.3.3 golden-master
# run (8 of 45 Key-Takeaways bullets carried visible machine scars):
#   F3/F4  "Two directions - covered" / "AuthorAC, AuthorAA, AuthorAD - covered"
#          → gap-fill CHECKLIST stubs (the model ticking off its own coverage
#            list, not summary content)
#   F1     "…a topic the summary omits entirely: 'This specific area…"
#          → gap-fill SELF-ASSESSMENT (the model commenting on the summary's
#            own coverage — incoherent once embedded in that summary)
#   F2     "…abandonment of narcissistic p… (text cuts off)"
#          → TRUNCATION MARKER (the model's own annotation of a cut)
#   F5/F6  "AuthorL five categories" / "Walt AuthorAB "a quoted epigraph" epigraph"
#          → verbless LABEL stubs (<8 words, no predicate — carry no claim)
# These run at TWO layers (per audit/results/v182033_pipeline_root_causes.md):
#   Layer 1 — ship-time quarantine in run_post_checks (final assembly,
#             applies to the final bullet set regardless of origin)
#   Layer 2 — generation-time drops in classify_bullets (so gap-fill /
#             expansion bullets never enter the list at all)
# The checklist + self-assessment + truncation-marker classes are
# always-drop (structural self-reference); the verbless-label class is
# enforced at ship time only (see is_label_stub).
_CHECKLIST_STUB_RE = re.compile(
    r'^\s*\S[^\n]{0,80}?\s[-\u2013\u2014]\s*covered\s*$',
    re.IGNORECASE,
)
_SUMMARY_SELF_ASSESSMENT_RE = re.compile(
    r'\bthe\s+summary\b[^\n]{0,80}?\b(?:omits|misses|omitted|missed|'
    r'does\s+not\s+cover|does\s+not\s+mention|fails\s+to\s+cover|'
    r'leaves\s+out)\b',
    re.IGNORECASE,
)
# V0.05 (rig audit F2 — P0): STRUCTURAL self-assessment detection. The
# phrase-enumeration regex above caught only "the summary <verb>" with 6
# verbs; the V0.04 rig leaked 11 critique bullets through it in 3/6 files
# ("Missing explicit mechanism…", "It omits…", "The summary flattens…",
# "The gap fails to capture…", "Author attribution: … does not appear in
# the summary text", "The summary must identify…"). The general rule: a
# bullet whose SUBJECT is the summary artifact (not the source content) is
# process commentary, not summary content — detected STRUCTURALLY, not by
# enumerating phrases:
#   (a) HEADLINE form — sentence-initial "Missing/Omitted/Absent/Uncovered
#       <noun-phrase>:" (no subject, pure critique-label);
#   (b) ARTIFACT-SUBJECT form — {the summary, this summary, the text above,
#       the gap, sentence-initial It, the thorough summary} × a
#       coverage-verb family (omits/misses/lacks/flattens/fails to
#       capture|mention|cover|include/does not appear/is not mentioned/
#       must identify/needs to/neglects/overlooks/does not appear).
_COVERAGE_VERB = (
    r'(?:omits|omitted|omitting|misses|missed|missing|lacks|lacked|'
    r'lacking|flattens|flattened|neglects|neglected|overlooks|overlooked|'
    r'fails\s+to\s+(?:capture|mention|cover|include|identify|reflect|'
    r'convey|note)|does\s+not\s+(?:appear|mention|cover|include|name|'
    r'identify|capture|convey|note)|is\s+not\s+(?:mentioned|covered|'
    r'included|named)|must\s+(?:identify|include|mention|name|capture)|'
    r'needs\s+to\s+(?:identify|include|mention|name|capture))'
)
_SELF_ASSESSMENT_HEADLINE_RE = re.compile(
    r'^\s*(?:missing|omitted|absent|uncovered|lacking)'
    r'(?:\s+(?:the|a|an|this|that|its|their|specific|explicit|distinct|'
    r'exact|any|several|certain)\b|[^.!?\n]{0,90}:)',
    re.IGNORECASE,
)
_SELF_ASSESSMENT_SUBJECT_RE = re.compile(
    r'(?:^|[.!?\n]\s*)'
    r'(?:it|the\s+(?:summary|thorough\s+summary|executive\s+summary|text\s+above|gap)|'
    r'this\s+summary)\s+'
    + _COVERAGE_VERB,
    re.IGNORECASE,
)
# "… does not appear in the summary text" — the verb targets the summary
# even when the subject is something else ("Author attribution: The chapter
# author is identified as 'By Neal Ford' but this name does not appear in
# the summary text").
_SELF_ASSESSMENT_IN_SUMMARY_RE = re.compile(
    r'(?:does\s+not\s+appear|is\s+not\s+mentioned|is\s+absent)\s+in\s+the\s+summary',
    re.IGNORECASE,
)
# "Author attribution:"-style critique labels — the scholar prompt's
# checklist vocabulary used as a bullet headline.
_SELF_ASSESSMENT_LABEL_RE = re.compile(
    r'^\s*(?:author\s+attribution|attribution)\s*[:—-]',
    re.IGNORECASE,
)
# V0.06 (rig audit F5 — P0): THREE more STRUCTURAL forms the V0.05 rig
# leaked through the detector above (all shipped in Key Takeaways):
#   (a) TRAILING critique-label — "<topic> omitted/missing/…: "<quote>""
#       ("Weather impact on schedules omitted: "a sever change in weather
#       throws the entire schedule out of whack."", "Framework origin
#       preference missing: "Prefer frameworks derived from working code…"").
#       The coverage-verb is NOT sentence-initial (the headline form) and
#       the subject is not the summary artifact (the subject form) — it is
#       a topic-label + past-participle + colon + evidence-quote. Requiring
#       the colon-then-quote shape keeps it clear of real content ("a
#       payroll system is missing a cost model: "quote"" is about the
#       SOURCE's subject matter only when no coverage-verb is involved).
#   (b) ADVICE form — "The summary should clarify/must identify/needs to
#       …" ("The summary should clarify that quality attributes are
#       explicitly defined in the text as "-ilities"…"). Any sentence whose
#       subject is the summary and whose verb is advisory is process
#       commentary by construction.
#   (c) NEGATED-ENUMERATION vs the artifact — "…are not fully enumerated
#       in the summary: "…"", "…are omitted from the detailed examples:
#       "…"". A coverage-verb (or negated completeness-verb) anchored to
#       "the summary"/"the detailed examples"/"the takeaways" is a claim
#       about the SUMMARY ARTIFACT, not about the source's content.
_SELF_ASSESSMENT_TRAILING_RE = re.compile(
    r'[^.!?\n]{0,120}?\b(?:omitted|missing|absent|uncovered|lacking|'
    r'not\s+fully\s+enumerated|not\s+enumerated|left\s+out|glossed\s+over|'
    r'flattened|reduced\s+to)\s*'
    r'(?:from\s+(?:the\s+)?(?:detailed\s+)?(?:summary|examples|takeaways|text)\s*)?'
    r':\s*["\u201c]',
    re.IGNORECASE,
)
_SELF_ASSESSMENT_ADVICE_RE = re.compile(
    r'\b(?:the|this)\s+summary\s+(?:should|must|needs\s+to|could|would)\b',
    re.IGNORECASE,
)
_SELF_ASSESSMENT_VS_ARTIFACT_RE = re.compile(
    r'\b(?:omitted|missing|absent|uncovered|not\s+fully\s+enumerated|'
    r'not\s+enumerated|not\s+fully\s+listed)\b[^.!?\n]{0,80}?'
    r'\b(?:in|from)\s+the\s+(?:summary|detailed\s+summary|detailed\s+examples|'
    r'takeaways|final\s+summary)\b',
    re.IGNORECASE,
)
_TRUNCATION_MARKER_RE = re.compile(
    r'\(\s*text\s+cuts\s+off\s*\)|\[\s*truncated\s*\]|\{\s*truncated\s*\}',
    re.IGNORECASE,
)


def is_checklist_stub(bullet: str) -> bool:
    """V18.20.3.4 (RC-1): True for gap-fill checklist stubs ("X - covered")."""
    if not bullet:
        return False
    return bool(_CHECKLIST_STUB_RE.match(bullet.strip()))


def is_summary_self_assessment(bullet: str) -> bool:
    """V18.20.3.4 (RC-1): True when the bullet comments on the summary's own
    coverage ("a topic the summary omits entirely") — incoherent inside the
    summary it describes.

    V0.05 (rig audit F2 — P0, STRUCTURAL): the detection is now structural
    (headline form + artifact-subject × coverage-verb family + "in the
    summary" verbs + attribution-critique labels), not the original 6-verb
    phrase enumeration. All 11 leaked rig bullets match one of the
    structural forms; the 3 sibling shapes the old regex caught remain
    caught (it is a subset). False-positive guard: bullets that REPORT the
    source's own claims about coverage are still content — but a bullet
    whose subject is the SUMMARY ARTIFACT ("the summary", "the gap", "It"
    at sentence start, "Missing …:") is process commentary by
    construction, whatever the verb.
    """
    if not bullet:
        return False
    t = bullet.strip()
    if _SUMMARY_SELF_ASSESSMENT_RE.search(t):
        return True
    if _SELF_ASSESSMENT_HEADLINE_RE.match(t):
        return True
    if _SELF_ASSESSMENT_SUBJECT_RE.search(t):
        return True
    if _SELF_ASSESSMENT_IN_SUMMARY_RE.search(t):
        return True
    if _SELF_ASSESSMENT_LABEL_RE.match(t):
        return True
    # V0.06 (rig audit F5): the three new structural forms — trailing
    # critique-label (…omitted/missing/…: "quote"), advice form (the
    # summary should…), negated-enumeration vs the artifact (not fully
    # enumerated in the summary…). All three leaked into the V0.05 rig's
    # Key Takeaways despite the ship-time scar filter because the shapes
    # above did not cover them.
    if _SELF_ASSESSMENT_TRAILING_RE.search(t):
        return True
    if _SELF_ASSESSMENT_ADVICE_RE.search(t):
        return True
    if _SELF_ASSESSMENT_VS_ARTIFACT_RE.search(t):
        return True
    return False


def has_truncation_marker(bullet: str) -> bool:
    """V18.20.3.4 (RC-1): True when the bullet carries an explicit truncation
    marker ("(text cuts off)" / "[truncated]") — the model's own annotation of
    a cut, never summary content."""
    if not bullet:
        return False
    return bool(_TRUNCATION_MARKER_RE.search(bullet))


def ends_in_bare_ellipsis(bullet: str) -> bool:
    """V18.20.3.4 (RC-1): True when the bullet's last non-space char is an
    ellipsis (… or ...) with nothing after it — the mid-generation cut form
    ("…abandonment of narcissistic p…"). A bullet that ends in a completed
    quote or sentence never ends this way."""
    if not bullet:
        return False
    t = bullet.rstrip()
    return t.endswith("\u2026") or t.endswith("...")


def is_label_stub(bullet: str) -> bool:
    """V18.20.3.4 (RC-1): True for verbless label stubs — fewer than 8 words
    AND no verb anywhere ("AuthorL five categories", "Walt AuthorAB
    quoted-epigraph label). Carries no claim: conveys that a topic
    exists but says nothing about it. Ship-time only (a legitimate short
    label in the generation stream is allowed to exist until final
    assembly, where the audit defect class is removed)."""
    if not bullet:
        return False
    text = bullet.strip()
    if len(text) < 10:
        return False  # sub-10-char items are handled by the <15-char drop
    if len(text.split()) >= 8:
        return False
    if _LIGHT_VERB_RE.search(text):
        return False  # has a predicate — it's a claim, keep it
    return True


def classify_scar(bullet: str) -> str | None:
    """V18.20.3.4 (RC-1): Return the process-scar class of a bullet, or None.

    Pure function. Used by run_post_checks (ship-time quarantine, layer 1)
    and available to any caller that wants the scar taxonomy:
    "checklist_stub" | "summary_self_assessment" | "truncation_marker" |
    "bare_ellipsis" | "label_stub" | None.
    """
    if not bullet:
        return None
    if is_checklist_stub(bullet):
        return "checklist_stub"
    if is_summary_self_assessment(bullet):
        return "summary_self_assessment"
    if has_truncation_marker(bullet):
        return "truncation_marker"
    if ends_in_bare_ellipsis(bullet):
        return "bare_ellipsis"
    if is_label_stub(bullet):
        return "label_stub"
    return None


# V18.20.3.2 (audit N5 / P1-c): citation-only fragment detection. The
# V18.20.3.1 run opened its Key Takeaways with two non-bullets:
#   "AuthorZ's contributions (a foreign term, a translation)"       — no predicate, no claim
#   "AuthorAC (1952), AuthorAA (1950), AuthorAD (1959)" — author-year citation dump
# The grammar detector flags "no main verb" but is flag-only. These are
# dropped at generation time (classify_bullets) and at ship time
# (run_post_checks) — a bullet with no predicate and <8 content words
# carries no claim at all.
_CITATION_TOKEN_RE = re.compile(
    r'[A-Z][a-zA-Z\u2019\-]+\s*\((?:\d{4}[a-z]?(?:\s*[,;]\s*\d{4}[a-z]?)*)\)'
)
# Light verb heuristic (keeps post_processing dependency-free): a word that
# IS a common verb form or ends with a verb suffix. Anything richer belongs
# to postcheck_detectors.detect_grammatical_incoherence.
# V18.20.3.2 fix: the initial explicit list missed 'introduced'/'distinguished'
# (legacy tests pin "AuthorP (1919) introduced…" and "AuthorK (1958)
# distinguished…" as KEEPS) — the generic past-tense alternative
# \b[a-z]{5,}ed\b catches every attribution verb in past tense
# (introduced, formulated, distinguished, contributed, described, …) while
# the explicit list covers the irregulars and present-tense forms.
_LIGHT_VERB_RE = re.compile(
    r'\b(?:is|are|was|were|be|been|being|has|have|had|does|did|do|will|would|'
    r'can|could|should|must|may|might|makes?|made|gives?|gave|takes?|took|'
    r'provides?|provided|offers?|offered|forms?|formed|holds?|held|sees?|saw|'
    r'views?|viewed|argues?|argued|notes?|noted|adds?|added|describes?|'
    r'described|defines?|defined|proposes?|proposed|suggests?|suggested|'
    r'emphasizes?|emphasized|contributes?|contributed|identifies?|identified|'
    r'introduces?|introduced|distinguishes?|distinguished|develops?|developed|'
    r'examines?|examined|explores?|explored|traces?|traced|coined|termed|'
    r'observes?|observed|maintains?|maintained|asserts?|asserted|'
    r'advances?|advanced|highlights?|highlighted|clarifies?|clarified|'
    r'recognizes?|recognized|applies?|applied|extends?|extended|'
    r'considers?|considered|discusses?|discussed|demonstrates?|'
    r'demonstrated|establishes?|established|creates?|created|builds?|built|'
    r'lays?|laid|finds?|found|shows?|showed|shown|wrote|writes?|'
    # V18.20.3.4 (RC-1): common present-tense academic verbs — the
    # label-stub detector (<8 words AND no verb) was false-positiving on
    # legitimate short sentences whose verb is 3rd-person present
    # ("The process emerges from the analysis."). Base forms +
    # 3rd-person -s forms.
    r'emerges?|arises?|occurs?|reflects?|captures?|marks?|signals?|'
    r'undergoes?|entails?|constitutes?|represents?|remains?|becomes?|'
    r'involves?|includes?|encompasses?|concerns?|focus(?:es)?|centers?|'
    r'stems?|derives?|originates?|follows?|precedes?|accompanies?|'
    r'parallels?|contrasts?|differs?|resembles?|replaces?|produces?|'
    r'generates?|yields?|results?|leads?|implies?|indicates?|reveals?|'
    r'illustrates?|exemplifies?|embodies?|expresses?|articulates?|'
    r'frames?|positions?|casts?|treats?|regards?|conceives?|imagines?|'
    r'envisions?|characterizes?|conceptualizes?|postulates?|assumes?|'
    r'links?|connects?|relates?|associates?|underpins?|grounds?|'
    r'shapes?|molds?|drives?|fuels?|anchors?|consolidates?|integrates?|'
    r'[a-z]{5,}ed)\b',
    re.IGNORECASE,
)


def is_citation_only_fragment(bullet: str) -> bool:
    """V18.20.3.2 (audit N5 / P1-c): True when a "bullet" is a citation dump
    or a no-predicate fragment — not a claim.

    Criteria (all must hold):
      1. No verb detected anywhere in the bullet (the light-verb heuristic
         above — "AuthorB (1960) described the the core construct." has "described"
         and is safe).
      2. Fewer than 8 content words remain after stripping author-year
         citation tokens and parentheticals ("AuthorAC (1952), AuthorAA (1950),
         AuthorAD (1959)" → ~0 content words; "AuthorZ's contributions (das
         Ich, ego)" → 2).
      3. The bullet actually CONTAINS a citation token or a parenthetical —
         the strip must have removed something. This keeps legitimate short
         label bullets ("AuthorI's stages of psychosocial development") that
         merely happen to lack a predicate: they carry no citation scaffolding
         and were not the defect class.

    Pure function — no side effects. Regression vectors from the V18.20.3.1
    the rig-test book run are pinned in tests/test_v182032_audit_fixes.py.
    """
    if not bullet:
        return False
    text = bullet.strip()
    if len(text) < 10:
        return False  # sub-10-char items are handled by the <15-char drop
    if _LIGHT_VERB_RE.search(text):
        return False  # has a predicate — it's a claim, keep it
    # Strip citation tokens, then count remaining content words.
    stripped = _CITATION_TOKEN_RE.sub(' ', text)
    # Also strip remaining bare parentheticals (e.g. "(a foreign term, a translation)").
    stripped = re.sub(r'\([^)]{0,60}\)', ' ', stripped)
    stripped = re.sub(r'[,;:.\-–—]', ' ', stripped)
    words = [w for w in stripped.split() if len(w) > 2]
    if len(words) >= 8:
        return False
    # V18.20.3.2 calibration: require citation/parenthetical scaffolding —
    # the fragment must be citation-DOMINATED, not merely short. Without
    # this, every legitimate label-style bullet ("AuthorI's stages of
    # psychosocial development") would drop.
    has_citation = bool(_CITATION_TOKEN_RE.search(text))
    has_parenthetical = bool(re.search(r'\([^)]{0,60}\)', text))
    return has_citation or has_parenthetical

_NARRATIVE_PATTERNS = [
    # V18.20.3.9 (Phase 2 / W3 / residuals sweep): structural replacement for
    # the book-keyed given-name alternation (17 first names harvested
    # from specific processed books — see git history for the list).
    # The name list made detection
    # book-KEYED: a narrative bullet whose character name wasn't listed (any
    # other book) shipped. New shape: ANY bare capitalized subject + a CLOSED
    # scene-narrative verb set + an article/possessive object — the "X went to
    # the/a party" scene shape, book-agnostic. Precision design:
    #   * the verb set deliberately EXCLUDES academic-attribution verbs
    #     ("observed", "established", "used", "said", "told"…): with a
    #     book-agnostic subject they would false-positive on every
    #     "Surname <verb> …" academic bullet ("AuthorI established…").
    #     Only scene-action verbs that essentially never open a nonfiction
    #     claim are kept.
    #   * the article/possessive object requirement keeps "X went on to
    #     argue" (no article after the preposition) and "X met <ProperName>"
    #     (biographical statements address proper nouns, not generic scene
    #     objects) OUT of the drop.
    #   * the lookahead excludes sentence-initial common words — "They went
    #     to great lengths to argue" is legitimate academic English.
    # The concept-indicator rescue below (is_narrative AND NOT has_concept)
    # still applies unchanged. Both-directions policy tests in
    # tests/test_v182039_audit_fixes.py.
    re.compile(
        r"^(?!(?:The|This|These|Those|They|It|He|She|We|You|There|One|Each|Both|"
        r"Some|Most|Many|All|Such|When|While|If|Because|Although)\s)"
        r"[A-Z][a-z']*\s+"
        r"(?:goes|went|arrives|arrived|meets|met|notices|noticed|figured|figures|"
        r"paid|pays|buying|bought)\s+"
        r"(?:to|at|in|into|onto)?\s*"
        r"(?:a|an|the|his|her|their|its|some)\b"
    ),
    re.compile(r"^For\s+[A-Z]\w+'s\s+(?:spy\s+)?(?:story|scenario|example|case|mission)", re.IGNORECASE),
    re.compile(r'^(?:A|An|The)\s+(?:case\s+study|real\s+example|story|anecdote)\s+(?:involving|about|where|demonstrates)', re.IGNORECASE),
    re.compile(r'^(?:In\s+a|In\s+the)\s+(?:licens|deal|scenario|situation|story|case|example|meeting)', re.IGNORECASE),
    re.compile(r'(?:as\s+seen\s+in\s+[A-Z]\w+|like\s+the\s+character\s+[A-Z]\w+|in\s+the\s+chapter\'s\s+narrative)', re.IGNORECASE),
    re.compile(r'(?:arrives at a party|goes to a|meets [A-Z]\w+ at|tells the story of|recounts how|describes how [A-Z]\w+ (?:went|arrived|met)|succeeded with|struggled with)', re.IGNORECASE),
    re.compile(r'\(and\s+by\s+extension', re.IGNORECASE),
    re.compile(r"in\s+the\s+chapter'?s\s+narrative", re.IGNORECASE),
]

# V18.20.3.9 (Phase 2 / W3 / residuals sweep): a domain-noun alternation
# (six occupation/cast nouns harvested from specific business/spy books —
# the literal list is in git history only) was REMOVED. The remaining
# indicators are structural: definitional frames,
# deontic markers, reportative frames, and second-person directives — they
# rescue narrative bullets in ANY book without keying on any book's cast.
_CONCEPT_INDICATORS = re.compile(
    r'(?:is defined as|refers to|means|involves|requires|'
    r'the concept of|the principle of|the technique of|the strategy of|'
    r'should|must|need to|important to|essential to|crucial to|'
    r'according to|research shows|statistics indicate|studies show|'
    r'the goal of|the purpose of|the key to|the difference between|'
    r'this (?:technique|method|approach|concept|principle|strategy)|'
    r'by (?:matching|mirroring|observing|asking|using|creating|establishing|developing)|'
    r'you (?:should|must|need to|can|could|should)|'
    r'(?:effective|powerful|essential|important) (?:way|method|technique|strategy|approach)|'
    r'(?:involves|requires|consists of|depends on|relies on)|'
    r'(?:the (?:first|second|third|key|main|primary|best) (?:step|way|method|approach|rule|principle)))',
    re.IGNORECASE
)


# ── is_truncated (V18.15.3.1: truncation detection) ────────────────────────
#
# Catches the V18.15.3.0 audit defect: a AuthorO bullet ended mid-quote
# at "I am different" (unmatched quote, no terminal punctuation). This
# happens when the primary call's 5-section output hits the max_tokens=8192
# ceiling mid-bullet-generation. The XML parser then extracts the incomplete
# bullet as-is.
#
# The fix: detect → drop (conservative-gated) → the V18.14.1 gap-fill loop
# sees the theorist "missing" from bullets and re-adds a COMPLETE single-bullet
# (single-bullet calls use ~200-400 output tokens, nowhere near the 8192
# ceiling, so truncation is virtually impossible on re-add).
#
# Signals (any one triggers):
# 1. Unmatched double quotes (odd count of ") — strong truncation signal
# 2. Unmatched parentheses (count of ( != count of ))
# 3. Long bullet (>= 40 chars) without terminal punctuation (. ! ? : ) " '])
# 4. V18.20.3.0: dangling function-word tail (any length) — the bullet
#    ENDS with terminal punctuation but its final word is a conjunction /
#    preposition / article / relativizer / copula ("…, and." / "… of." /
#    "… in."). A complete sentence never ends on a function word, so this
#    is truncation regardless of length or punctuation presence.
#
# Short bullets (< 40 chars) are exempt from signal 3 — they may be
# intentional label-style fragments (e.g. "AuthorZ (1926a)" or "See above.")
# that are complete. Signals 1, 2 and 4 apply to ALL lengths.

# V18.20.3.0 (Audit FLAG-02): function words that never legitimately end a
# sentence. The V18.20.2.0 real-rig audit found a Key-Takeaways bullet
# ending "…(4) role of aggression in self-delineation, and." — the final
# item (5) of AuthorL's five categories was cut off (by generation or
# consolidation — NOT by provider done_reason=length, so A20 never fired
# and the period after "and" let it past the terminal-punctuation check).
# The final-WORD check closes that gap: only the word before the period
# reveals the truncation. Deliberately EXCLUDES words that can end
# elliptical-but-complete sentences ("so", "not", "no", "thus", "hence",
# "however") to avoid false positives.
_DANGLING_TAIL_WORDS = frozenset({
    # coordinating conjunctions
    "and", "or", "but", "nor", "yet",
    # relativizers / subordinators
    "that", "which", "who", "whom", "whose", "when", "where", "while",
    "because", "since", "although", "though", "if", "unless", "than",
    # prepositions
    "of", "in", "to", "with", "for", "as", "by", "from", "into", "onto",
    "at", "on", "upon", "about", "across", "against", "among", "between",
    "during", "through", "toward", "towards", "within", "without", "via",
    "per", "over", "under",
    # articles / determiners
    "the", "a", "an", "this", "these", "those", "such",
    # connectives that never end a sentence
    "also", "then", "both", "either", "neither", "including",
    "especially", "particularly",
    # copulas / auxiliaries
    "is", "are", "was", "were", "be", "been", "being", "has", "have",
    "had", "will", "would", "can", "could", "should", "must", "may",
    "might", "does", "did",
})

# Trailing characters stripped before reading the final word: terminal
# punctuation + closing quotes/brackets/ellipsis (both ASCII and curly).
_TAIL_STRIP_CHARS = ".,;:!?)'\"\u201d\u2019\u2026"


def ends_on_dangling_word(bullet: str) -> bool:
    """V18.20.3.0 (Audit FLAG-02): True if the bullet's final word (ignoring
    trailing punctuation and closing quotes/parens) is a function word that
    never ends a complete sentence.

    Pure function — no side effects. Characterization tests in
    ``tests/test_v18203_audit_fixes.py``.
    """
    if not bullet:
        return False
    core = bullet.rstrip(_TAIL_STRIP_CHARS)
    if not core:
        return False
    parts = core.split()
    if not parts:
        return False
    last_word = parts[-1].strip("'\"\u2018\u2019\u201c\u201d").lower()
    if not last_word:
        return False
    return last_word in _DANGLING_TAIL_WORDS


def is_truncated(bullet: str) -> bool:
    """V18.15.3.1: Detect if a bullet appears truncated (cut off mid-sentence).
    V18.19.3.1: catch unmatched parens/quotes in SHORT bullets too (the
    "AuthorD (198" case — a max_tokens cut mid-citation that the < 40-char
    exemption previously missed).
    V18.20.3.0: catch the dangling-tail class (Audit FLAG-02) — bullets that
    end "…, and." / "… of." pass every existing check (balanced quotes and
    parens, terminal punctuation present) but are cut off mid-list; only the
    final-word check reveals them.

    Returns True if the bullet shows structural signs of truncation:
    unmatched quotes/parens, a dangling function-word tail, or a long body
    without terminal punctuation.

    Pure function — no side effects, no I/O. Characterization tests in
    ``tests/test_truncation_detect.py`` + ``tests/test_truncation_short_bullet.py``.
    """
    if not bullet:
        return False
    stripped = bullet.rstrip()
    if not stripped:
        return False
    # V18.19.3.1 (audit fix): even short bullets can be truncated. The V18.15.3.1
    # code exempted all bullets < 40 chars, assuming they were intentional
    # label-style fragments (e.g. "AuthorZ (1926a)"). But the V18.19.3.0 audit
    # found "- AuthorD (198" — a 14-char bullet where the max_tokens ceiling
    # cut "1980b" to "198", leaving an UNMATCHED open paren. The < 40-char
    # exemption let it through. Fix: check unmatched quotes/parens REGARDLESS
    # of length. A label like "AuthorZ (1926a)" has matched parens; a truncated
    # "AuthorD (198" does not. The "no terminal punctuation" check still
    # only applies to long bullets (short labels legitimately lack terminal
    # punctuation).
    # Unmatched double quotes → strong truncation signal (any length).
    # V18.15.4.3: count ASCII " AND curly U+201C/U+201D (PDFs/typesetters
    # emit curly quotes; the pre-V18.15.4.3 code only counted ASCII " and
    # silently missed mid-curly-quote truncation).
    _quote_count = stripped.count('"') + stripped.count('\u201c') + stripped.count('\u201d')
    if _quote_count % 2 != 0:
        return True
    # Unmatched parentheses (any length — catches "AuthorD (198").
    if stripped.count('(') != stripped.count(')'):
        return True
    # V18.20.3.0 (Audit FLAG-02): dangling function-word tail — ANY length.
    # "…, and." has balanced quotes/parens AND terminal punctuation, so every
    # earlier check passes it; the cut-off is only visible in the final word.
    if ends_on_dangling_word(stripped):
        return True
    # Long bullet without terminal punctuation → likely truncated.
    # (This check stays gated on >= 40 chars — short labels like "See above."
    # legitimately lack terminal punctuation, but "See above." ends in '.' so
    # it passes; the issue is short fragments like "AuthorI (1950)" that
    # have NO terminal punctuation but ARE complete citations. Those are not
    # truncated — they're label-style. So the no-terminal-punctuation check
    # only fires for LONG bullets where missing punctuation is abnormal.)
    if len(stripped) < 40:
        return False  # short bullets with matched parens/quotes are intentional labels
    # V18.15.4.3: include curly closing quote U+201D as a valid terminal char
    # (a bullet ending in a closing curly quote is NOT truncated).
    last = stripped[-1]
    if last not in '.!?:)\'"\u201d\u2019':
        return True
    return False


def classify_bullets(
    bullets: list[str],
    concepts: list[str] | None = None,
    source_text: str = "",
) -> tuple[list[str], list[DropRecord]]:
    """Classify bullets: keep the good ones, record drops with reasons.

    This is the PURE CORE of ``Summarizer._filter_thinking_bullets``. It
    applies the pattern-matching + classification logic and returns:

    - ``kept``: list of bullets that passed all checks (thinking/narrative/
      meta-commentary/numeric-verify). Each bullet has been cleaned
      (thinking stripped, markup stripped, orphaned bold-labels stripped).
    - ``drops``: list of ``DropRecord`` tuples ``(bullet, stage, reason,
      always_drop)``. ``always_drop=True`` means the drop is a structural
      contamination (thinking/prompt-leakage) that's dropped even in
      conservative mode; ``always_drop=False`` means it's a conservative-
      gated drop (narrative/meta-commentary/too-long/numeric-verify) that
      is LOGGED but KEPT in conservative mode.

    The ``Summarizer._filter_thinking_bullets`` method calls this function,
    then iterates ``drops`` to call ``self.quarantine.add(...)`` for each
    record (applying the conservative-mode decision). This cleanly separates
    the pure decision logic from the I/O side-effect.

    NOTE: The quality-scorer pass (``_score_bullet``) is NOT extracted here —
    it depends on ``self.max_bullets_per_chapter`` and the scoring function.
    That stays in Summarizer for now (Phase 4 Stage 2 candidate).
    """
    filtered = []
    drops: list[DropRecord] = []

    for bp in bullets:
        bp_str = str(bp).strip() if not isinstance(bp, str) else bp.strip()
        if not bp_str:
            continue

        # ── ALWAYS-ACTIVE thinking/prompt-leakage checks ─────────────
        if _THINKING_STARTS.match(bp_str):
            drops.append((bp_str, "thinking_filter.thinking_process",
                          "Bullet starts with a thinking-process verb "
                          "(Analyze/Process/Draft/Step/Now/…).", True))
            continue
        if _BACKTICK_WORDS.search(bp_str):
            drops.append((bp_str, "thinking_filter.backtick_words",
                          "Bullet contains backtick-quoted internal markers.", True))
            continue
        if _INTERNAL_MARKERS.search(bp_str):
            drops.append((bp_str, "thinking_filter.internal_markers",
                          "Bullet contains internal-section markers "
                          "(Jargon/Context/Draft/Refinement/…).", True))
            continue
        if _PROMPT_LEAKAGE.search(bp_str):
            drops.append((bp_str, "thinking_filter.prompt_leakage",
                          "Bullet leaks the prompt template.", True))
            continue
        # V18.12.2: Gap-fill prompt-leakage (defense-in-depth). Catches the
        # V17.8 batch gap-fill template phrases that slip past _PROMPT_LEAKAGE.
        if _GAP_FILL_PROMPT_LEAKAGE.search(bp_str):
            drops.append((bp_str, "thinking_filter.gap_fill_prompt_leakage",
                          "Bullet leaks the gap-fill prompt template "
                          "(source sentence / what does this say about).", True))
            continue

        # V18.19.2.1 (Audit Fix 1): Word-count CoT + self-instruction +
        # bare-checkmark leakage. The V18.19.2.0 audit found 45% of Key
        # Takeaways bullets were the model's internal reasoning in surface forms
        # the existing patterns missed. All three are structural contamination
        # (always_drop=True): they are never legitimate summary content.
        if _WORD_COUNT_COT.search(bp_str):
            drops.append((bp_str, "thinking_filter.word_count_cot",
                          "Bullet ends with a word-count annotation "
                          "(= N words - TOO LONG/borderline) — model's "
                          "internal split-decision reasoning.", True))
            continue
        if _WORD_COUNT_CHECKMARK.search(bp_str):
            drops.append((bp_str, "thinking_filter.word_count_checkmark",
                          "Bullet ends with '= N ✓' word-count + validation "
                          "annotation — model's internal verification reasoning.", True))
            continue
        if _LET_ME_SPLIT.search(bp_str):
            drops.append((bp_str, "thinking_filter.let_me_split",
                          "Bullet contains 'Let me split' — model's internal "
                          "continuation marker, not summary content.", True))
            continue
        if _SELF_CORRECTION_PAREN.search(bp_str):
            drops.append((bp_str, "thinking_filter.self_correction",
                          "Bullet contains a '(Wait, ...)' self-correction "
                          "parenthetical — model's internal editing reasoning.", True))
            continue
        if _SELF_INSTRUCTION.match(bp_str):
            drops.append((bp_str, "thinking_filter.self_instruction",
                          "Bullet is a self-instruction (Using the chapter's "
                          "terminology / Preserving all contributors / Preserve "
                          "technical terminology) — model's strategy notes, "
                          "not summary content.", True))
            continue
        if _BARE_CHECKMARK.search(bp_str):
            drops.append((bp_str, "thinking_filter.bare_checkmark",
                          "Bullet ends in an isolated ✓ validation checkmark "
                          "— model's author-inclusion checklist, not summary "
                          "content.", True))
            continue

        # V18.20.3.2 (audit N1 / P0-2): model SELF-TALK — mid-bullet CoT
        # planning notes ("include this!", "let me add it", "be more
        # specific", "the source says", "looking at the text"). The
        # V18.20.3.1 run shipped two of these as Key-Takeaways bullets; the
        # start-anchored _THINKING_STARTS missed them because they begin
        # with an author-year token. Always-drop: a bullet discussing the
        # summary-writing process is never summary content.
        if SELF_TALK_PATTERNS.search(bp_str):
            drops.append((bp_str, "thinking_filter.self_talk",
                          "Bullet contains model self-talk (include this! / "
                          "let me add / be more specific / the source says / "
                          "looking at the text) — CoT planning note, not "
                          "summary content.", True))
            continue

        # V18.20.3.4 (RC-1 layer 2, audit v182033): process-scar classes at
        # GENERATION time — the V18.20.3.3 run's gap-fill output leaked
        # checklist stubs ("Two directions - covered"), summary
        # self-assessment ("a topic the summary omits entirely") and
        # truncation markers ("(text cuts off)") past every existing pattern
        # because they don't start with a thinking verb and don't leak the
        # prompt template. Always-drop: a bullet about the summary-writing
        # process is never summary content. (The verbless-label class is
        # ship-time-only — see run_post_checks.)
        if is_checklist_stub(bp_str):
            drops.append((bp_str, "thinking_filter.checklist_stub",
                          "Gap-fill checklist stub ('X - covered') — the "
                          "model ticking off its own coverage list, not "
                          "summary content.", True))
            continue
        if is_summary_self_assessment(bp_str):
            drops.append((bp_str, "thinking_filter.summary_self_assessment",
                          "Bullet comments on the summary's own coverage "
                          "('a topic the summary omits') — self-assessment, "
                          "incoherent inside the summary it describes.", True))
            continue
        if has_truncation_marker(bp_str):
            drops.append((bp_str, "thinking_filter.truncation_marker",
                          "Bullet carries an explicit truncation marker "
                          "('(text cuts off)') — the model's annotation of a "
                          "cut, not summary content.", True))
            continue
        if ends_in_bare_ellipsis(bp_str):
            drops.append((bp_str, "thinking_filter.bare_ellipsis",
                          "Bullet ends in a bare ellipsis — mid-generation "
                          "cut; the claim is incomplete and unverifiable.",
                          True))
            continue

        # V18.20.3.2 (audit N5 / P1-c): citation-only fragment — no verb,
        # <8 content words after stripping citations ("AuthorAC (1952), AuthorAA
        # (1950), AuthorAD (1959)" / "AuthorZ's contributions (a foreign term, a translation)").
        # These carry no claim and previously shipped as the FIRST bullets
        # of the Key Takeaways. Always-drop.
        if is_citation_only_fragment(bp_str):
            drops.append((bp_str, "thinking_filter.citation_only",
                          "Citation-only fragment (no predicate, <8 content "
                          "words after citation strip) — carries no claim.",
                          True))
            continue

        # ── Conservative-gated checks (always_drop=False) ────────────
        if _META_COMMENTARY.search(bp_str):
            drops.append((bp_str, "thinking_filter.meta_commentary",
                          "Model commenting on the bullet itself.", False))
            continue
        if len(bp_str) > 500:
            drops.append((bp_str, "thinking_filter.too_long_500chars",
                          f"Bullet is {len(bp_str)} chars (>500).", False))
            continue

        is_narrative = any(p.search(bp_str) for p in _NARRATIVE_PATTERNS)
        has_concept = bool(_CONCEPT_INDICATORS.search(bp_str))
        if is_narrative and not has_concept:
            drops.append((bp_str, "thinking_filter.narrative_no_concept",
                          "Narrative/story bullet with no concept indicator.", False))
            continue

        # Strip thinking + markup from the bullet itself
        bp_str = strip_thinking(bp_str)
        bp_str = strip_markup_tags(bp_str)

        # Strip orphaned bold-label prefixes
        bp_str = re.sub(r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\*\*:\s*', '', bp_str)
        bp_str = re.sub(r'^[^.]*?\*\*:\s*', '', bp_str, count=1)
        bp_str = re.sub(r'^\*\*', '', bp_str)

        # V18.15.3.1: Strip leading bullet markers ("- ", "* ", "• ") that
        # survive from gap-fill output. Gap-fill bullets arrive as "- Name: text"
        # (the model follows the prompt's "- " prefix instruction). Without this
        # strip, the markdown formatter renders them as "- - Name: text".
        # normalize_bullets handles this in its own pass (with a loop for multi-
        # dash), but gap-fill bullets filtered through _filter_thinking_bullets
        # (V18.12.2) need the strip here too — belt-and-suspenders. Loop to
        # handle "- - Name" (double-dash from the prompt + model).
        for _ in range(3):
            _prev_marker = bp_str
            bp_str = re.sub(r'^[-–•*]\s+', '', bp_str)
            if bp_str == _prev_marker:
                break

        # V18.15.3.1: Truncation detection. Catches bullets cut off mid-sentence
        # when the primary call hits the max_tokens=8192 ceiling. Conservative-
        # gated (always_drop=False): in normal mode the bullet is dropped and the
        # V18.14.1 gap-fill loop re-adds a complete single-bullet; in conservative
        # mode the bullet is logged but kept (respects "more bullets > lower
        # coverage"). The AuthorO bullet from the V18.15.3.0 audit is the
        # regression case: ended mid-quote at "I am different" (unmatched ").
        if is_truncated(bp_str):
            drops.append((bp_str, "thinking_filter.truncated",
                          "Bullet appears truncated (unmatched quote/paren or "
                          "no terminal punctuation) — likely hit max_tokens "
                          "ceiling. Gap-fill will re-add a complete bullet.",
                          False))
            continue

        # Numeric/quote verification (optional — needs source_text)
        if source_text and bp_str:
            try:
                from core.summarisation.text_preprocessor import verify_numbers_and_quotes
                is_valid, _reasons = verify_numbers_and_quotes(bp_str, source_text)
                if not is_valid:
                    drops.append((bp_str, "thinking_filter.numeric_verify",
                                  f"Numeric/quote verification failed: "
                                  f"{', '.join(_reasons[:2]) if _reasons else 'unknown'}.",
                                  False))
                    continue
            except Exception as _e:  # V18.15.4.3: was silent `except Exception: pass`.
                # Keep fail-open (verification is optional — spaCy/NLTK may be
                # absent), but log at DEBUG so verify_numbers_and_quotes
                # regressions are discoverable instead of silently swallowed.
                import logging as _logging
                _logging.getLogger(__name__).debug(
                    "verify_numbers_and_quotes crashed (optional, fail-open): %r", _e
                )

        if bp_str and len(bp_str) > 2:
            filtered.append(bp_str)

    return filtered, drops


__all__ = [
    "strip_thinking",
    "strip_markup_tags",
    "strip_narrative_from_thorough",
    "truncate_to_sentences",
    "normalize_bullets",
    "is_truncated",
    "classify_bullets",
    "DropRecord",
    "detect_enumerated_conclusions",  # V18.15.9.0
    "SELF_TALK_PATTERNS",            # V18.20.3.2 (audit N1 / P0-2)
    "is_citation_only_fragment",     # V18.20.3.2 (audit N5 / P1-c)
    "classify_scar",                 # V18.20.3.4 (RC-1, audit v182033)
    "is_checklist_stub",             # V18.20.3.4 (RC-1)
    "is_summary_self_assessment",    # V18.20.3.4 (RC-1)
    "has_truncation_marker",         # V18.20.3.4 (RC-1)
    "ends_in_bare_ellipsis",         # V18.20.3.4 (RC-1)
    "is_label_stub",                 # V18.20.3.4 (RC-1)
]


# ── V18.15.9.0: Enumerated-conclusion detection ────────────────────────────


def detect_enumerated_conclusions(
    source_text: str,
    min_items: int = 3,
    max_items: int = 15,
) -> list:
    """V18.15.9.0: Detect enumerated conclusions in the source text.

    The V18.15.8.0 audit found the 7 characteristics of solid identity were
    present in the thorough summary but NOT as a distinct bullet group (the
    gold standard V18.15.3.2 had them as distinct bullets). This function
    detects enumerated conclusions like "(1) ... (2) ... (3) ..." in the
    source so they can be added as a distinct bullet group.

    Focuses on the LAST 30% of the source (conclusions are at the end).
    Supports both ``(N)`` and ``N.`` numbering styles.

    Args:
        source_text: the full source chapter text.
        min_items: minimum number of enumerated items to qualify as a
            "conclusion list" (default 3 — avoids false positives from
            casual inline numbering).
        max_items: cap on items returned (default 15 — avoids pathological
            cases where the source has 50+ numbered items).

    Returns:
        A list of ``(number, text)`` tuples, e.g. ``[(1, "selfsameness..."),
        (2, "temporal continuity..."), ...]``. Empty list if no enumerated
        conclusion is found, or if the numbers aren't sequential (1, 2, 3, ...).

    Examples:
        >>> source = "...characteristics: (1) selfsameness, (2) temporal
        ... continuity, (3) authenticity, (4) body image, (5) inner solidity,
        ... (6) gender clarity, (7) ethnic solidarity."
        >>> detect_enumerated_conclusions(source)
        [(1, 'selfsameness'), (2, 'temporal continuity'), ...]
    """
    if not source_text or len(source_text) < 200:
        return []
    import re as _re

    # Focus on the last 30% of the source (conclusions are at the end).
    _len = len(source_text)
    _focus = source_text[int(_len * 0.7):]

    # V18.15.9.0: Filter out 4-digit numbers (year-citations like (1978), (1951))
    # — they're NOT conclusion items. Conclusion items are 1-99 (single/double digit).
    # Pattern: (N) where N is 1-2 digits, NOT 4 digits (which are years).
    _paren_matches = list(_re.finditer(r'\(([1-9]\d{0,1})\)\s+', _focus))
    if len(_paren_matches) >= min_items:
        items = _extract_sequential_run(_paren_matches, min_items, max_items)
        if items:
            return items

    # Try N. style (e.g., "1. selfsameness 2. temporal continuity ...").
    # Same 1-2 digit filter (avoid matching "1978.").
    _dot_matches = list(_re.finditer(r'(?<!\d)([1-9]\d{0,1})\.\s+', _focus))
    if len(_dot_matches) >= min_items:
        items = _extract_sequential_run(_dot_matches, min_items, max_items)
        if items:
            return items

    return []


def _extract_sequential_run(matches, min_items, max_items):
    """Extract the LONGEST sequential run (1, 2, 3, ...) from the matches.

    A source may have multiple numbered groups (e.g., a (1)(2)(3) list in the
    middle + a (1)(2)(3)(4)(5)(6)(7) conclusion at the end). We find ALL
    sequential runs and return the LONGEST one (the conclusion is usually the
    longest). Validates that each run starts at 1 and is sequential.
    """
    # Group matches into sequential runs (each run starts at 1).
    _runs = []
    _current_run = []
    _expected = 1
    for m in matches:
        _num = int(m.group(1))
        if _num == _expected:
            _current_run.append(m)
            _expected += 1
        else:
            if len(_current_run) >= min_items:
                _runs.append(_current_run)
            _current_run = [m] if _num == 1 else []
            _expected = 2 if _num == 1 else 1
    if len(_current_run) >= min_items:
        _runs.append(_current_run)

    if not _runs:
        return []

    # Pick the LONGEST run (the conclusion is usually the longest enumerated list).
    _longest = max(_runs, key=len)
    if len(_longest) < min_items:
        return []

    # Extract items between consecutive markers.
    items = []
    for i, m in enumerate(_longest):
        _start = m.end()
        _end = _longest[i + 1].start() if i + 1 < len(_longest) else _find_sentence_end(m.string, _start)
        _text = m.string[_start:_end].strip().rstrip(',;.')
        # V18.15.9.1 (Fix 3): Collapse newlines to spaces (the source may have
        # line breaks mid-item like "(6) subjective clarity\nregarding one's
        # gender"). Also strip trailing "and" (from "(6) ..., and (7) ...").
        _text = _text.replace('\n', ' ').replace('\r', ' ')
        _text = re.sub(r'\s+', ' ', _text).strip()  # collapse multiple spaces
        _text = _text.rstrip(',;.')
        # Strip trailing "and" (e.g., "subjective clarity and" → "subjective clarity")
        _text = re.sub(r'\s+and\s*$', '', _text, flags=re.IGNORECASE).strip()
        _text = _text.rstrip(',;.')
        if _text:  # V18.15.9.0: accept any non-empty text (strip() handles whitespace)
            items.append((int(m.group(1)), _text))
    return items[:max_items]


def _find_sentence_end(text, start):
    """Find the end of the current sentence (period + space + Capital, or end)."""
    import re as _re
    _m = _re.search(r'[.!?]\s+(?=[A-Z])', text[start:])
    if _m:
        return start + _m.start() + 1  # include the period
    return len(text)
