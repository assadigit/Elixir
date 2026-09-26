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

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the source chapter text (for building the word-set).
        source_words: precomputed source word-set (preferred over
            ``source_text`` for batch use).

    Returns:
        ``(text, issues)``. Text is UNCHANGED.
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
            if not found_fusion:
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
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("sentence-fusion detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues
    return text, issues
