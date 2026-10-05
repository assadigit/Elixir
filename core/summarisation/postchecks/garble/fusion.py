"""V0.4.19 — the sentence-boundary fusion detector.

``detect_sentence_fusion`` (and ``_is_legit_fusion_suffix`` + the
``_FUSION_*`` constants) moved VERBATIM from ``garble.py`` during the
V0.4.19 de-monolithization. ``_load_english_lexicon`` lives in
``garble.lexicon`` and is imported by name.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.garble.lexicon import _load_english_lexicon
from core.summarisation.postchecks.shared import Issue

# ─────────────────────────────────────────────────────────────────────────────
# V0.4.3 (audit D4): sentence-fusion detector.
#
# The V0.4.2 NPD thorough summary shipped two sentence-fusion garbles that
# the existing detectors missed:
#   - "praiseity governed by the prompt" — the LLM merged "praise." +
#     "Waelder noted that...governed by the prompt" into one word, dropping
#     the sentence boundary. The "ity" is a remnant of the dropped text.
#   - "self-developmentstic-masochistic character" — merged "self-
#     development." + "Cooper proposed a unified narcissistic-masochistic
#     character" — the "stic" is a remnant of "narcissistic".
#
# Pattern: a word that is NOT in the source AND has a long prefix (>=5
# chars) that IS in the source, with a short suffix (2-4 chars). The
# suffix is the remnant of the dropped sentence-boundary text.
#
# Content-agnostic: works on any source word-set. No hardcoded words.
# Flag-only (no auto-repair — the correct reconstruction is ambiguous:
# "praiseity" could be "praise. Waelder noted that..." or "praise. It is
# ...", etc.).
#
# Validation: catches both V0.4.2 fusions. False-positive risk: real
# words like "carefulness" (careful + ness) where the prefix is in the
# source — mitigated by requiring the suffix to be 2-4 chars AND the
# full word to not be in the source.
# ─────────────────────────────────────────────────────────────────────────────

_FUSION_MIN_PREFIX = 5  # prefix must be >= 5 chars (avoids matching short stems)
_FUSION_MIN_SUFFIX = 3  # suffix must be >= 3 chars (2-char suffixes are
# almost always legitimate inflections: -ed,
# -es, -ly, -al, -er, -or)
_FUSION_MAX_SUFFIX = 4  # suffix must be <= 4 chars (longer = likely a real word)
_FUSION_MIN_WORD_LEN = 9  # full word must be >= 9 chars (shorter = likely a
# real inflection like 'discussion', 'whereas')

# V0.4.38 (F1): Pattern C — the "dropped-prefix" fusion. Catches words
# like "persecutionensate" = source-word "persecution" + "ensate" where
# "ensate" (6 chars) is itself a SUFFIX of another source word
# "compensate" (the model fused the two but dropped "comp" from
# "compensate"). Pattern A caps suffixes at 4 chars (so a 5-6 char
# remnant escapes); Pattern B needs >=2 source-word substrings but the
# 2nd source word's prefix was dropped so it isn't a substring. Pattern
# C closes this gap: a source-word prefix + a 5-6 char suffix that is a
# suffix of some OTHER source word (not the prefix itself).
_FUSION_C_MIN_SUFFIX = 5  # the remnant is 5-6 chars (4-char remnants are
# already caught by Pattern A's <=4 range; 7+ = likely a real compound)
_FUSION_C_MAX_SUFFIX = 6

# V0.5.4 (Track E3 Pattern D): the "source-propagated self-X fusion
# garble" pattern. Catches the case where the source itself has a
# missing-hyphen "self-X" compound (e.g. "selfinflation" instead of
# "self-inflation") and the summary transmits it verbatim. Pattern
# A/B/C correctly skip source-words (the early
# ``if word in source_words: continue``), so this gap is unaddressed.
#
# Detection: word IS in source_words (source has the unhyphenated form)
# AND word NOT in lexicon AND word starts with the conventionally-
# always-hyphenated English morpheme "self" + a 5+ char lexicon word
# suffix.
#
# Why "self" specifically: per English style guides (Chicago, AP), the
# "self-X" compound convention is ALWAYS hyphenated (self-confidence,
# self-esteem, self-inflation). The unhyphenated form is conventionally
# a typo. Other prefixes (hyper-, hypo-, pseudo-, psycho-) are
# conventionally UNhyphenated (hypervigilance, hypomania) — flagging
# those would cause false positives. "self" is a generic English
# morpheme (precedent: _FUSION_LEGIT_SUFFIXES at L99 includes "self"
# for "X-self" hyphen-joins); not book content (Rule 1 ✓).
#
# The 5+ char suffix requirement avoids short inflections (-ing, -ed,
# -ness, -tion) that would create false positives on regular English
# words like "selfish" (in lexicon — already skipped by ``word not in
# lexicon``) or "selfhood" (5-char suffix "hood", in lexicon).
_FUSION_D_SELF_PREFIX = "self"
_FUSION_D_MIN_SUFFIX = 5

# Common English suffixes that produce real words when appended to a source
# word — these are NOT sentence-fusion remnants and must NOT be flagged.
# Content-agnostic (English morphology, not book-specific).
_FUSION_LEGIT_SUFFIXES = frozenset(
    {
        # 3-char legitimate
        "ity",
        "ion",
        "ing",
        "ies",
        "ers",
        "est",
        # 4-char legitimate
        "ions",
        "ness",
        "ment",
        "tion",
        "sion",
        "able",
        "ible",
        "ance",
        "ence",
        "ship",
        "hood",
        "ward",
        "ways",
        "side",
        "time",
        "wide",
        "long",
        "term",
        # hyphen-join suffixes (after hyphen normalization)
        "ego",
        "off",
        "love",
        "self",
        # V0.4.36 (F5): adverbial suffixes that produce real words —
        # "egosyntonic" + "ally" = "egosyntonically" (a valid English
        # adverb; the V0.4.34/V0.4.35 audit flagged this as a false
        # positive). Content-agnostic (English morphology).
        "ally",
    }
)

# Common English compound words (hyphen-joined) that should NOT be flagged.
_FUSION_LEGIT_COMPOUNDS = frozenset(
    {
        "alter-ego",
        "object-love",
        "split-off",
        "self-development",
        "pre-modern",
        "self-help",
        # V0.4.3 (audit D4 follow-up): common English hyphenated constructions
        # that contain a source-word substring but are NOT fusions.
        "generated-by",
        "well-consolidated",
        "well-integrated",
        "well-defined",
        "well-established",
        "well-known",
    }
)


def _is_legit_fusion_suffix(suffix: str) -> bool:
    """Return True if the suffix is a legitimate English inflection/
    derivation of the prefix (NOT a sentence-fusion remnant).

    Conservative: returns True for any suffix that commonly forms a real
    word when appended to an English stem. This is content-agnostic (the
    list is English morphology, not book-specific).
    """
    if suffix in _FUSION_LEGIT_SUFFIXES:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# V0.5.4 (Track C2): adverb-as-adjective grammatical-garble auto-rewrite.
#
# The V0.5.3 ground-truth audit (commit cfec6a9, file
# audit/results/AUDIT_V0.5.3_run20260926-211039-8b53ed76_ch6_summary_vs_source.md)
# found that bullet 15 of the V0.5.3 summary shipped a grammatical garble
# — "ego-syntonically personalities" (the adverb "ego-syntonically"
# misused as an adjective; should be "ego-syntonic personalities"). The
# sentence-fusion detector correctly flagged the word (Pattern A
# specifically, since "ally" is a 4-char suffix; the V0.5.3 release
# notes' "Pattern C" wording was loose shorthand for the whole sentence-
# fusion subsystem), but the summary shipped it uncorrected because the
# detector was flag-only.
#
# Track C2: upgrade the sentence-fusion detector from flag-only to
# flag+auto-rewrite for clear grammatical garbles where the correction
# is unambiguous. The rule is conservative + deterministic (NOT an LLM
# repair — it uses English morphology + lexicon membership only):
#
#   1. ``word`` ends in "-ically" (the adverb suffix formed from an
#      adjective ending in "-ic" + "ally"; e.g., "ego-syntonic" +
#      "ally" → "ego-syntonically"). The candidate rewrite is
#      ``word[:-len("ically")] + "ic"`` (e.g., "ego-syntonically" →
#      "ego-synton" + "ic" → "ego-syntonic").
#   2. The candidate adjective is recognised as a real English word:
#      EITHER directly in the lexicon, OR (for domain-specific
#      hyphenated adjectives like "ego-syntonic") a hyphenated
#      compound whose LAST hyphen-component is in the lexicon (covers
#      the case where the lexicon has the stem "syntonic" but not the
#      hyphenated compound form "ego-syntonic"; this is morphologically
#      principled — the head of a hyphenated English compound is its
#      last component).
#   3. The next word after ``word`` is a noun: it is in the lexicon
#      AND does NOT end in a common English past-tense / participle
#      ending (so "personalities" passes — clearly a noun; "embedded"
#      does NOT — it is the verb past participle, the source's CORRECT
#      adverb-modifying-verb usage on line 257 of the V0.5.3 source
#      chapter).
#
# If all checks pass → rewrite ``word`` to the candidate adjective in
# the returned ``text`` AND annotate the issue's ``detail`` with the
# rewrite note. If ANY check fails → fall back to flag-only (the
# V0.5.3 behavior). The rewrite is OPTIONAL + fail-open (an empty
# lexicon ⇒ no rewrite).
#
# Conservative scope (per the task spec): the rewrite is ONLY for the
# "-ically → -ic" adverb→adjective pattern. It does NOT apply to other
# garble types (e.g., dropped-prefix fusions like "persecutionensate"
# — those need LLM repair, not a deterministic rewrite, because the
# correct reconstruction is ambiguous).
#
# Content-agnostic (Rule 1): the rule uses English morphology + lexicon
# membership ONLY; no hardcoded words. The example "ego-syntonically"
# appears in TESTS only, never in the production code.
# ─────────────────────────────────────────────────────────────────────────────

# The adverb suffix (e.g., "ego-syntonically" ends in "ically").
_REWRITE_ADVERB_SUFFIX = "ically"
# The adjective suffix to rewrite to ("ego-syntonically" → "ego-syntonic").
_REWRITE_ADJECTIVE_SUFFIX = "ic"
# Common English past-tense / participle endings — if the next word ends
# in one of these, it is a verb (not a noun), so DON'T rewrite (the adverb
# is correctly modifying the verb). Conservative: the rule would rather
# MISS a rewrite than incorrectly rewrite a correct adverb-modifying-verb
# usage. The 3 entries are unambiguous English past-tense/participle
# endings: "ed" (past tense: "embedded"), "ing" (present participle:
# "running"), "en" (past participle: "broken").
_REWRITE_VERB_PAST_ENDINGS = ("ed", "ing", "en")


def _rewrite_grammatical_garble(word: str, next_word: str, lexicon: set) -> str | None:
    """V0.5.4 (Track C2): rule-based grammatical-garble auto-rewrite for
    the adverb-as-adjective pattern (see the module constants block above
    for the full rationale + conservative scope).

    Args:
        word: the flagged candidate word (lowercased).
        next_word: the next word in the summary text after ``word``
            (lowercased, or empty if ``word`` is at the end of text).
        lexicon: the loaded English lexicon (set of lowercased words;
            an empty set ⇒ fail-open: no rewrite is attempted).

    Returns:
        The rewritten adjective form (e.g., "ego-syntonic"), or ``None``
        if any check fails (falls back to flag-only — the V0.5.3
        behavior).
    """
    if not word or not word.endswith(_REWRITE_ADVERB_SUFFIX):
        return None
    candidate = word[: -len(_REWRITE_ADVERB_SUFFIX)] + _REWRITE_ADJECTIVE_SUFFIX
    # Check the candidate is a real English adjective: directly in the
    # lexicon, OR (for domain-specific hyphenated adjectives) a hyphenated
    # compound whose last hyphen-component is in the lexicon. The hyphen
    # fallback is morphologically principled — the head of an English
    # hyphenated compound is its last component ("ego-syntonic" → head
    # "syntonic", which IS in the lexicon even though "ego" alone is not
    # and the hyphenated compound form is not).
    candidate_real = bool(lexicon) and (
        candidate in lexicon or ("-" in candidate and candidate.rsplit("-", 1)[-1] in lexicon)
    )
    if not candidate_real:
        return None
    # Check the next word is a noun (in the lexicon AND not a verb past
    # participle). This is the conservative guard that distinguishes the
    # garble "ego-syntonically personalities" (rewrite) from the source's
    # correct usage "ego-syntonically embedded" (no rewrite — "embedded"
    # is a verb past participle).
    if not next_word or not next_word.islower():
        return None
    if not (lexicon and next_word in lexicon):
        return None
    if next_word.endswith(_REWRITE_VERB_PAST_ENDINGS):
        return None  # likely a verb past participle — not a noun
    return candidate


def _try_grammatical_rewrite_after_flag(
    word: str,
    text: str,
    word_start: int,
    word_end: int,
    lexicon: set,
    issues: list,
    pending_rewrites: list,
) -> None:
    """V0.5.4 (Track C2): after a Pattern A/B/C issue is appended (the
    LAST issue in ``issues``), check if the flagged word matches the
    adverb-as-adjective grammatical-rewrite pattern. If so, register the
    rewrite in ``pending_rewrites`` (applied to ``text`` AFTER the
    ``re.finditer`` loop completes — preserves character offsets by
    applying rewrites in REVERSE order, so earlier matches' positions
    don't shift) and annotate the issue's ``detail`` with the rewrite
    note (the issue's ``snippet`` remains the original garble for
    audit-trail purposes).

    The rewrite helper is fail-open: any internal exception is swallowed
    (the detector must never break the chapter — the outer ``try/except``
    in ``detect_sentence_fusion`` is the safety net, but this inner
    swallow lets the per-word loop continue to find OTHER garbles even if
    the rewrite logic crashes on one word).
    """
    try:
        if not issues:
            return
        # Find the next word in text after word_end (skip leading
        # whitespace + punctuation; match a single alphabetic/hyphen
        # token). The regex is anchored at the start of the slice.
        next_m = re.match(r"\s*([a-zA-Z][a-zA-Z\-]+)", text[word_end:])
        next_word = next_m.group(1).lower() if next_m else ""
        rewrite = _rewrite_grammatical_garble(word, next_word, lexicon)
        if rewrite is None:
            return
        pending_rewrites.append((word_start, word_end, rewrite))
        issues[-1].detail += (
            f" Auto-rewrite applied (V0.5.4 Track C2): '{word}' → "
            f"'{rewrite}' (adverb-as-adjective before noun "
            f"'{next_word}'; the adverb form is correct only when "
            f"modifying a verb)."
        )
    except Exception:  # pragma: no cover — rewrite must never break the chapter
        pass


def detect_sentence_fusion(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V0.4.3 (audit D4): detect sentence-boundary fusion garbles.

    Catches words like ``praiseity`` (praise + ity) or
    ``self-developmentstic`` (development + stic) where a sentence
    boundary was dropped and the next sentence's first chars got fused
    onto the previous word.

    Detection (book-agnostic): for each word in the summary that is NOT
    in the source word-set AND NOT in the English lexicon, scan ALL
    substrings (not just position-0 prefixes) for a source-word match +
    short non-inflectional suffix. The suffix must be 3-4 chars AND NOT
    a legitimate English inflection.

    Two refinements vs the first draft:
      1. English-lexicon check: skip words that are real English words
         (catches false positives like 'furthermore').
      2. Substring-prefix matching: allow the source-word prefix to
         start at ANY position in the cleaned word, not just position 0.
         This catches 'self-developmentstic' where 'development' starts
         at position 4 (after 'self').

    Flag-only (doesn't auto-fix — the correct reconstruction is ambiguous).
    Content-agnostic: the source word-set comes from the runtime analysis.
    The English lexicon is the vendored ``data/english_lexicon.txt.gz``
    (already used by ``detect_dropped_letter_garble``).

    V0.5.4 (Track C2): upgraded from flag-only to flag+auto-rewrite for
    the adverb-as-adjective grammatical garble (see
    ``_rewrite_grammatical_garble``). When a Pattern A or Pattern C flag
    matches the unambiguous rewrite pattern (word ends in ``-ically`` +
    next word is a noun + candidate adjective is a real English word),
    the returned ``text`` has the rewrite applied (preserving all other
    character offsets) and the flagged issue's ``detail`` notes the
    rewrite. Other garble types (dropped-prefix fusions like
    ``persecutionensate``) remain flag-only — the rewrite is
    conservative + scoped to the unambiguous ``-ically → -ic`` pattern.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the source chapter text (for building the word-set).
        source_words: precomputed source word-set (preferred over
            ``source_text`` for batch use).

    Returns:
        ``(text, issues)``. ``text`` is the input text unchanged, UNLESS
        a Pattern A or Pattern C flag triggered the V0.5.4 Track C2
        adverb-as-adjective rewrite (in which case the rewritten text is
        returned, with all other character offsets preserved).
    """
    issues: list[Issue] = []
    if source_words is None:
        source_words = set(re.findall(r"\b[a-z]+\b", source_text.lower())) if source_text else set()
    if not text or not source_words:
        return text, issues

    # Lazily load the English lexicon (fail-open to empty set).
    try:
        lexicon = _load_english_lexicon()
    except Exception:
        lexicon = set()

    # V0.5.4 (Track C2): per-word grammatical-garble rewrites to apply
    # AFTER the re.finditer loop completes. Applied in REVERSE order so
    # earlier matches' character offsets don't shift when later matches'
    # text replacements are applied first. Each entry is
    # (word_start, word_end, replacement_adjective_form).
    pending_rewrites: list[tuple[int, int, str]] = []

    # V0.4.38 (F1): Pattern C precompute — the set of 5-6 char suffixes
    # of all source words (the dropped-prefix fusion signature). O(1)
    # lookup per candidate. Content-agnostic: built from the runtime
    # source word-set, no hardcoded words.
    _source_word_suffix_set: set[str] = set()
    for _sw in source_words:
        _sw_len = len(_sw)
        for _sl in range(_FUSION_C_MIN_SUFFIX, min(_FUSION_C_MAX_SUFFIX, _sw_len - 1) + 1):
            _source_word_suffix_set.add(_sw[-_sl:])

    try:
        # Find all words in the summary (lowercase, alphabetic, with hyphens).
        # Hyphens are normalized to '' for the substring analysis (catches
        # "self-developmentstic-masochistic" → contains "development" +
        # "stic" (3-char gap) + "masochistic" — a 2-source-word fusion).
        for m in re.finditer(r"\b[a-zA-Z][a-zA-Z\-]{6,}\b", text):
            word = m.group(0).lower()
            # Skip legitimate compounds (alter-ego, object-love, etc.).
            if word in _FUSION_LEGIT_COMPOUNDS:
                continue

            # ── Pattern D (V0.5.4 Track E3): source-propagated self-X
            # fusion garble. Runs BEFORE the early source-words skip
            # (Pattern A/B/C correctly skip source-words — they only
            # catch LLM-introduced fusions; Pattern D catches the
            # source-itself-has-the-garble case where the summary
            # faithfully transmits a source-text typo). See
            # _FUSION_D_SELF_PREFIX docstring for the design rationale.
            if (
                lexicon
                and word in source_words
                and word not in lexicon
                and word.startswith(_FUSION_D_SELF_PREFIX)
            ):
                _d_suffix = word[len(_FUSION_D_SELF_PREFIX) :]
                if len(_d_suffix) >= _FUSION_D_MIN_SUFFIX and _d_suffix in lexicon:
                    _snippet_start = max(0, m.start() - 25)
                    _snippet_end = min(len(text), m.end() + 25)
                    issues.append(
                        Issue(
                            detector="sentence_fusion",
                            severity="flag",
                            field=field_label,
                            snippet=text[_snippet_start:_snippet_end],
                            detail=(
                                f"likely source-propagated fusion garble: '{word}' is in the "
                                f"source but is NOT a real English word; it starts with the "
                                f"conventionally-always-hyphenated English morpheme "
                                f"'{_FUSION_D_SELF_PREFIX}' + lexicon word '{_d_suffix}' (the "
                                f"source's own missing-hyphen typo was transmitted verbatim to "
                                f"the summary — the LLM faithfully reproduced the source's "
                                f"garble instead of normalising to "
                                f"'{_FUSION_D_SELF_PREFIX}-{_d_suffix}')."
                            ),
                        ),
                    )
                    continue  # Pattern D handled this word — don't run A/B/C

            if word in source_words:
                continue  # exact match with source — not a fusion
            if lexicon and word in lexicon:
                continue  # real English word — not a fusion (catches
                # 'furthermore', 'discussion', etc.)
            # Normalize hyphens for the substring analysis.
            clean = word.replace("-", "")
            if len(clean) < _FUSION_MIN_WORD_LEN:
                continue
            # Find all source-word substrings (length >= 5) in the cleaned
            # word. Keep only the longest match at each start position
            # (avoids treating 'develop' as a separate match from
            # 'development').
            longest_by_start: dict[int, tuple[int, str]] = {}
            for sub_start in range(len(clean)):
                for prefix_len in range(_FUSION_MIN_PREFIX, min(20, len(clean) - sub_start + 1)):
                    prefix = clean[sub_start : sub_start + prefix_len]
                    if prefix in source_words:
                        if (
                            sub_start not in longest_by_start
                            or prefix_len > longest_by_start[sub_start][0]
                        ):
                            longest_by_start[sub_start] = (prefix_len, prefix)
            if not longest_by_start:
                continue
            starts = sorted(longest_by_start.keys())
            snippet_start = max(0, m.start() - 25)
            snippet_end = min(len(text), m.end() + 25)

            # ── Pattern A: source-word prefix + short non-inflectional
            # suffix at the end. Catches "praiseity" = "praise" + "ity".
            # The source word must END at or near the end of the cleaned
            # word, with a 3-4 char suffix that's not a legit inflection.
            found_fusion = False
            for s in starts:
                if found_fusion:
                    break
                prefix_len, prefix = longest_by_start[s]
                suffix_start = s + prefix_len
                if suffix_start >= len(clean):
                    continue  # no suffix after the source word
                suffix = clean[suffix_start:]
                # The suffix must be short (3-4 chars) and at the end
                # of the cleaned word (no more source words after it).
                if not (_FUSION_MIN_SUFFIX <= len(suffix) <= _FUSION_MAX_SUFFIX):
                    continue
                # Skip legitimate English inflections ONLY when the
                # full word IS a real English word. If the full word is
                # not in the lexicon AND not in source, a "legit" suffix
                # is still suspicious (e.g., 'praiseity' = 'praise' +
                # 'ity'; 'ity' is a real suffix but 'praiseity' is not
                # a real word).
                # NOTE: the V0.5.2 "Pattern C lexicon check" block that
                # lived here (commit 1cf0dcb) was BROKEN — it was
                # redundant with the early lexicon check at L218 (which
                # already does `if lexicon and word in lexicon: continue`
                # upstream, so `word in lexicon` is always False here),
                # and the documented FP compound word is NOT in the
                # 126k-word lexicon, so the check could never suppress
                # it. Re-implemented correctly INSIDE Pattern C's block
                # (see compound-word guard below). See
                # tests/test_v052_audit_fixes.py for the regression.
                if _is_legit_fusion_suffix(suffix):
                    full_word_is_real = (lexicon and word in lexicon) or (word in source_words)
                    if full_word_is_real:
                        continue
                if suffix in source_words:
                    continue
                # Check no other source word starts after this suffix
                # (otherwise it's Pattern B).
                later_starts = [st for st in starts if st >= suffix_start]
                if later_starts:
                    continue
                issues.append(
                    Issue(
                        detector="sentence_fusion",
                        severity="flag",
                        field=field_label,
                        snippet=text[snippet_start:snippet_end],
                        detail=(
                            f"likely sentence-fusion garble: '{word}' is not in the source "
                            f"or English lexicon but ends with source-word '{prefix}' + "
                            f"suffix '{suffix}' ({len(suffix)} chars, not a legitimate "
                            f"English inflection). The suffix is likely a remnant of "
                            f"a dropped sentence boundary."
                        ),
                    ),
                )
                found_fusion = True
                # V0.5.4 (Track C2): after Pattern A flags the word, check
                # for the adverb-as-adjective grammatical rewrite (word
                # ends in "-ically" + next word is a noun + candidate
                # adjective is a real English word). If the rule fires,
                # register the rewrite in ``pending_rewrites`` (applied
                # after the finditer loop) and annotate this issue's
                # ``detail`` with the rewrite note. Fail-open: any
                # internal exception is swallowed (the detector must
                # never break the chapter).
                _try_grammatical_rewrite_after_flag(
                    word=word,
                    text=text,
                    word_start=m.start(),
                    word_end=m.end(),
                    lexicon=lexicon,
                    issues=issues,
                    pending_rewrites=pending_rewrites,
                )

            # ── Pattern B: 2 source-word substrings separated by a 3-8
            # char non-source gap. Catches "self-developmentstic-
            # masochistic" = "development" + "stic" (3-char gap) +
            # "masochistic". The gap is the remnant of the dropped
            # sentence boundary text.
            if not found_fusion and len(starts) >= 2:
                for i, s1 in enumerate(starts):
                    if found_fusion:
                        break
                    prefix_len1, prefix1 = longest_by_start[s1]
                    end1 = s1 + prefix_len1
                    for s2 in starts[i + 1 :]:
                        if s2 < end1:
                            continue  # overlap
                        gap = s2 - end1
                        if not (3 <= gap <= 8):
                            continue
                        prefix_len2, prefix2 = longest_by_start[s2]
                        gap_text = clean[end1:s2]
                        # Skip if the gap alone is a real source word or
                        # English word (not a remnant).
                        if gap_text in source_words or (lexicon and gap_text in lexicon):
                            continue
                        issues.append(
                            Issue(
                                detector="sentence_fusion",
                                severity="flag",
                                field=field_label,
                                snippet=text[snippet_start:snippet_end],
                                detail=(
                                    f"likely sentence-fusion garble: '{word}' contains two "
                                    f"source-words '{prefix1}' and '{prefix2}' separated by "
                                    f"a {gap}-char gap '{gap_text}' (not in source or English "
                                    f"lexicon). The gap is likely a remnant of a dropped "
                                    f"sentence boundary."
                                ),
                            ),
                        )
                        found_fusion = True
                        break

            # ── Pattern C (V0.4.38 F1): source-word prefix + a 5-6 char
            # suffix that is itself a SUFFIX of some other source word
            # (the "dropped-prefix" fusion). Catches "persecutionensate"
            # = "persecution" (source prefix) + "ensate" (a 6-char
            # suffix of the source word "compensate", whose "comp"
            # prefix was dropped in the fusion). Pattern A caps at 4
            # chars so the 5-6 char remnant escapes; Pattern B needs 2
            # source-word substrings but the 2nd source word's prefix
            # was dropped so it isn't a substring. Pattern C closes
            # the gap. Content-agnostic: the suffix-to-source-word-
            # suffix match is structural, no hardcoded words.
            #
            # V0.5.2 (FIX-P0-1 — RE-IMPLEMENTED): compound-word
            # guard. BEFORE Pattern C flags a candidate, verify the
            # word isn't a legitimate English compound. The original
            # V0.5.2 "Fix 5" placed a redundant `if word in lexicon:
            # continue` inside Pattern A (where the early lexicon
            # check at L218 already catches it), and the documented
            # FP compound word is NOT in the 126k-word lexicon
            # (zgrep -c '^<compound-word>$' -> 0), so the check was
            # provably dead code (see the NOTE comment in Pattern A
            # above). The principled fix (per the AUDIT-V0.5.2
            # recommendation): a real compound word is either
            # (i) itself in the lexicon (already covered by the early
            # lexicon check at L218, but re-checked here against the
            # un-hyphenated `clean` form for hyphenated compounds),
            # OR (ii) composed of two lexicon words (prefix + suffix
            # both real English). If either holds, the candidate is
            # a legitimate English compound, not a dropped-prefix
            # fusion — skip Pattern C. Content-agnostic (Rule 1):
            # lexicon membership only, no hardcoded words. See
            # tests/test_v052_audit_fixes.py for the regression.
            if not found_fusion:
                _is_compound_word = lexicon and (
                    clean in lexicon
                    or any(
                        clean[:_split] in lexicon and clean[_split:] in lexicon
                        for _split in range(_FUSION_MIN_PREFIX, len(clean) - _FUSION_MIN_PREFIX + 1)
                    )
                )
                if _is_compound_word:
                    # real English compound (prefix + suffix both
                    # in the lexicon) — not a dropped-prefix fusion.
                    continue
                for s in starts:
                    if found_fusion:
                        break
                    prefix_len, prefix = longest_by_start[s]
                    suffix_start = s + prefix_len
                    if suffix_start >= len(clean):
                        continue  # no suffix after the source word
                    suffix = clean[suffix_start:]
                    # The suffix must be 5-6 chars (the dropped-prefix
                    # remnant range — 3-4 is Pattern A's territory).
                    if not (_FUSION_C_MIN_SUFFIX <= len(suffix) <= _FUSION_C_MAX_SUFFIX):
                        continue
                    # The suffix itself must not be a source word
                    # (else Pattern A / a legit compound handles it).
                    if suffix in source_words:
                        continue
                    # Self-suffix guard: if the prefix (the source
                    # word) itself ends with this suffix, it's an
                    # inflection of the prefix, not a dropped-prefix
                    # fusion of a DIFFERENT source word.
                    if prefix.endswith(suffix):
                        continue
                    # The KEY Pattern-C check: the suffix is a suffix
                    # of some OTHER source word (the dropped-prefix
                    # fusion signature). O(1) lookup in the precomputed
                    # set.
                    if suffix not in _source_word_suffix_set:
                        continue
                    # No other source word starts after this suffix
                    # (otherwise Pattern B would have handled it).
                    later_starts = [st for st in starts if st >= suffix_start]
                    if later_starts:
                        continue
                    issues.append(
                        Issue(
                            detector="sentence_fusion",
                            severity="flag",
                            field=field_label,
                            snippet=text[snippet_start:snippet_end],
                            detail=(
                                f"likely sentence-fusion garble: '{word}' is not in the source "
                                f"or English lexicon; it starts with source-word '{prefix}' + "
                                f"a {len(suffix)}-char suffix '{suffix}' that is itself a "
                                f"suffix of another source word (a dropped-prefix fusion — "
                                f"the model fused '{prefix}' with a source word ending in "
                                f"'{suffix}' but dropped that word's prefix)."
                            ),
                        ),
                    )
                    found_fusion = True
                    # V0.5.4 (Track C2): after Pattern C flags the word,
                    # check for the adverb-as-adjective grammatical
                    # rewrite (same hook as Pattern A above — the
                    # rewrite rule is pattern-agnostic: any flagged word
                    # ending in "-ically" before a noun rewrites to the
                    # adjective form). Symmetric with the Pattern A hook
                    # so future Pattern-C-flagged "-ically" garbles also
                    # get the rewrite (the V0.5.3 rig's "ego-syntonically"
                    # garble was flagged by Pattern A — "ally" is 4 chars,
                    # Pattern A's range — but the rule is generic).
                    _try_grammatical_rewrite_after_flag(
                        word=word,
                        text=text,
                        word_start=m.start(),
                        word_end=m.end(),
                        lexicon=lexicon,
                        issues=issues,
                        pending_rewrites=pending_rewrites,
                    )
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("sentence-fusion detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues
    # V0.5.4 (Track C2): apply any pending grammatical-garble rewrites
    # (adverb-as-adjective: "-ically" → "-ic"). Applied in REVERSE order
    # so earlier matches' character offsets don't shift when later
    # matches' text replacements are applied first. Each rewrite replaces
    # text[start:end] with the candidate adjective form (e.g., replaces
    # "ego-syntonically" with "ego-syntonic"). Other character offsets in
    # the text are preserved — only the flagged words are replaced, and
    # only when the rewrite rule fires (otherwise flag-only).
    if pending_rewrites:
        for _rw_start, _rw_end, _rw_new in sorted(pending_rewrites, reverse=True):
            text = text[:_rw_start] + _rw_new + text[_rw_end:]
    return text, issues
