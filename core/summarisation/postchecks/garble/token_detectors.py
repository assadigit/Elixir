"""V0.4.19 — the small token / spacing / grammar detectors.

Moved VERBATIM from ``garble.py`` during the V0.4.19 de-monolithization:
``detect_garbled_tokens``, ``detect_missing_spaces``,
``detect_grammatical_incoherence``, ``detect_extra_spaces``, and
``detect_word_fragment_merge``. The shared constants they reference live
in ``garble.lexicon`` and are imported by name.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.garble.lexicon import (
    _CAMELCASE_MERGE_RE,
    _FRAGMENT_MERGE_RE,
    _IMPOSSIBLE_BIGRAM_RE,
    _LONG_CONSONANT_CLUSTER_RE,
    _MERGED_SENTENCE_RE,
    _MISSING_SPACE_CAP_RE,
    _MISSING_SPACE_LOWER_RE,
    _VERB_ENDINGS,
    _VERB_STOPWORDS,
    _VOWEL_LESS_LONG_RE,
    _is_legitimate_inflection,
    _load_english_lexicon,
)
from core.summarisation.postchecks.shared import Issue, _snippet


def detect_garbled_tokens(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """Flag unusual character sequences that signal garbled tokens.

    Three signals:

    1. **Long consonant clusters** (6+ consonants in a row inside a word).
       English tops out around 5 ("lengths", "twelfths"); 6+ almost always
       indicates a token-merge artifact.
    2. **Impossible English bigrams** (``xz``, ``qq``, ``kx``, …). These
       never appear inside a real English word.
    3. **Long vowel-less words** (5+ chars, no a/e/i/o/u/y). Real English
       vowel-less words are extremely rare and none appear in academic prose.

    This detector FLAGS only — it does not rewrite. (A garbled token like
    "thesonic" is handled by :func:`detect_missing_spaces`; "Dukhaim" by
    :func:`validate_years`. Pure nonsense tokens have no safe deterministic
    correction, so we flag for review rather than guess.)

    The allowlist :data:`_GARBLED_ALLOWLIST` exempts common cluster-heavy
    words ("through", "strength", "rhythms", etc.) to avoid false positives.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is returned UNCHANGED.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    try:
        # V18.20.2.0 (SWOT A24): the source word-set was previously rebuilt
        # (a full-source regex scan) inside _flag for EVERY flagged match;
        # accept a precomputed set from run_post_checks and fall back to the
        # lazy per-call build for direct callers.
        if source_words is None:
            source_words = (
                set(re.findall(r"\b[a-z]+\b", source_text.lower())) if source_text else set()
            )
        flagged_words: set = set()

        def _flag(match: re.Match, signal: str) -> None:
            word = match.group(0)
            # Strip surrounding punctuation for allowlist lookup.
            bare = word.strip(".,;:!?\"'()[]{}")
            # V18.15.3.2: source-grounded — if the word is in the source, it's legitimate
            if source_words and bare.casefold() in source_words:
                return
            key = (bare.casefold(), signal)
            if key in flagged_words:
                return
            flagged_words.add(key)
            snippet = _snippet(text, match.start())
            issues.append(
                Issue(
                    detector="garbled",
                    severity="flag",
                    field=field_label,
                    snippet=snippet,
                    detail=f"{signal}: '{bare}'",
                )
            )

        for m in _LONG_CONSONANT_CLUSTER_RE.finditer(text):
            _flag(m, "long consonant cluster (6+)")
        for m in _IMPOSSIBLE_BIGRAM_RE.finditer(text):
            _flag(m, "impossible English bigram")
        for m in _VOWEL_LESS_LONG_RE.finditer(text):
            _flag(m, "long vowel-less word (5+)")
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="garbled",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"garbled-token check crashed: {e!r}",
            )
        )
    return text, issues


def detect_missing_spaces(
    text: str,
    field_label: str,
    source_text: str = "",
    source_lower: str | None = None,
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """Fix missing spaces where a stopword merged with the following word.

    Catches the V18.2.12 artifacts ``"thesonic"`` (→ ``"the sonic"``) and
    ``"thefive-stage"`` (→ ``"the five-stage"``).

    Three patterns:

    1. **stopword + Capitalized** (``theAuthor`` → ``the AuthorZ``). The Capital
       is a strong signal that two tokens were joined. Always fixed.
    2. **stopword + lowercase (4+ chars)** (``thesonic`` → ``the sonic``).
       The 4-char minimum avoids catching ``thee``/``them``/``then``/``thea``.
       Fixed only if the *split* form is more plausible: we check that the
       stopword + suffix isn't itself a known word (via a small stoplist of
       real merged words like ``theory``, ``theme``, ``there``, ``these``).
    3. **camelCase merge** (``doingsIdentity`` → ``doings Identity``). Lowercase
       run of 3+ chars followed by a Capitalized run of 3+ chars. Fixed.

    Args:
        text: the summary text to clean.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(cleaned_text, issues)``.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    cleaned = text
    try:
        # Pattern 1: stopword + Capitalized → split (always safe).
        def _split_cap(m: re.Match) -> str:
            issues.append(
                Issue(
                    detector="space",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=f"split '{m.group(0)}' → '{m.group(1)} {m.group(2)}'",
                )
            )
            return f"{m.group(1)} {m.group(2)}"

        cleaned = _MISSING_SPACE_CAP_RE.sub(_split_cap, cleaned)

        # Pattern 3: camelCase merge → split (always safe).
        def _split_camel(m: re.Match) -> str:
            # Don't split if the lowercase part is a known stopword that
            # Pattern 1 already handled (avoid double-splitting "theFreud").
            # V18.15.3.2: skip if Pattern 1 already handled (short word + Capital)
            if len(m.group(1)) <= 3:
                return m.group(0)
            issues.append(
                Issue(
                    detector="space",
                    severity="fix",
                    field=field_label,
                    snippet=_snippet(cleaned, m.start()),
                    detail=f"split camelCase '{m.group(0)}' → '{m.group(1)} {m.group(2)}'",
                )
            )
            return f"{m.group(1)} {m.group(2)}"

        cleaned = _CAMELCASE_MERGE_RE.sub(_split_camel, cleaned)

        # Pattern 2: "the" + lowercase (4+) → split, but NOT if the merged
        # form is a real English word. Pattern 2 is restricted to "the" only
        # (see _LOWER_SPLIT_SAFE), so this allowlist only needs "the"-prefixed
        # real words whose suffix is 4+ chars: "theater", "theatre", "theirs",
        # "thence", "theorem", "theology", "theorist", "theoretical", etc.
        # Short suffixes (<=3 chars: "theory"="the"+"ory" where "ory" is 3)
        # never reach this code because of the {4,} minimum in the regex.
        # V18.15.3.2: _real_merged DELETED. Source-grounded validation replaces it.
        # V18.20.2.0 (SWOT A24): accept precomputed source_lower/source_words
        # from run_post_checks (was rebuilt per bullet); lazy-build when omitted.
        if source_lower is None:
            source_lower = source_text.lower() if source_text else ""
        if source_words is None:
            source_words = set(re.findall(r"\b[a-z]+\b", source_lower)) if source_text else set()

        def _split_lower(m: re.Match) -> str:
            merged = m.group(0)
            merged_lower = merged.casefold()
            split_form = f"{m.group(1)} {m.group(2)}"
            if not source_text:
                return merged  # no source -> can't validate -> don't split (safe)
            # If merged word is in source -> real word -> don't split
            if merged_lower in source_words:
                return merged
            # If split form appears in source -> confirmed merge -> split
            if split_form.lower() in source_lower:
                issues.append(
                    Issue(
                        detector="space",
                        severity="fix",
                        field=field_label,
                        snippet=_snippet(cleaned, m.start()),
                        detail=f"split '{merged}' -> '{split_form}' (source-validated)",
                    )
                )
                return split_form
            # Neither form in source -> conservative: don't split
            return merged

        cleaned = _MISSING_SPACE_LOWER_RE.sub(_split_lower, cleaned)

        # Final whitespace cleanup.
        cleaned = re.sub(r"  +", " ", cleaned).strip()
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="space",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"missing-space check crashed: {e!r}",
            )
        )
        return text, issues
    return cleaned, issues


def detect_grammatical_incoherence(
    text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V18.2.18 Improvement 2: Flag grammatically broken bullets.

    Catches the V18.2.15 broken Key Distinctions bullet pattern:
    "Identity and AuthorD both crisis of adolescence versus identity
    diffusion: AuthorI described..."

    Three signals (any one triggers a FLAG):
    1. **Merged sentences**: a period immediately followed by a Capital
       letter with no space (``.The`` → ``. The``).
    2. **No main verb**: the first 40 words contain no finite verb.
    3. **Disjoint subject-object**: "Noun1 and Noun2 both Noun3" with no
       verb between (e.g. "Identity and AuthorD both crisis").

    Book-agnostic: these are universal grammatical signals, not
    domain-specific. Works on any language that uses Latin script.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED (flag-only).
    """
    issues: list[Issue] = []
    if not text or len(text.strip()) < 20:
        return text, issues
    try:
        # Signal 1: Merged sentences (.Capital with no space)
        for m in list(_MERGED_SENTENCE_RE.finditer(text)):
            issues.append(
                Issue(
                    detector="grammar",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"merged sentences: '.{m.group(1)}' — a period is "
                        f"immediately followed by a Capital letter with no space. "
                        f"Likely a formatting/extraction failure."
                    ),
                )
            )

        # Signal 2 + 3: Check each bullet/line for missing verb
        lines = [
            line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 15
        ]
        for line in lines:
            words = re.findall(r"[A-Za-z]+", line)
            if len(words) < 5:
                continue
            first_40 = words[:40]
            # Check for any finite verb (word >3 chars ending in a verb
            # suffix, not a stopword). V0.4.37 (F7): also recognize
            # 3rd-person-singular "-s" verbs (e.g. "masks", "links",
            # "notes", "posits") — the suffix list above catches
            # "es"/"ed"/"ing"/... but misses the bare "-s" 3rd-singular
            # inflection, which false-positived clean academic bullets
            # where a singular subject takes a "-s" verb (e.g. "the
            # facade masks the defect"). Content-agnostic (Rule 1): the
            # lexicon is a generic English wordlist (126k words, no
            # domain terms); we only treat a "-s" word as a verb when
            # its singular form is a known English word and not a
            # function-word stopword. Base-form verbs (e.g. "mask" with
            # a plural subject) still escape — full recognition needs
            # POS tagging, deferred (observability-only per the V0.4.36
            # audit F7).
            _lex = _load_english_lexicon()
            has_verb = any(
                (
                    len(w) > 3
                    and w.lower() not in _VERB_STOPWORDS
                    and any(w.lower().endswith(e) for e in _VERB_ENDINGS)
                )
                or (
                    len(w) > 4
                    and w.lower().endswith("s")
                    and not w.lower().endswith("ss")
                    and w.lower()[:-1] in _lex
                    and w.lower()[:-1] not in _VERB_STOPWORDS
                )
                for w in first_40
            )
            if not has_verb:
                # Double-check: is there an auxiliary (is/are/was/were)?
                has_aux = any(
                    w.lower() in _VERB_STOPWORDS
                    for w in first_40
                    if w.lower() in ("is", "are", "was", "were", "have", "has", "had")
                )
                if not has_aux:
                    issues.append(
                        Issue(
                            detector="grammar",
                            severity="flag",
                            field=field_label,
                            snippet=_snippet(line, 0),
                            detail=(
                                f"no main verb detected in first 40 words of "
                                f"'{line[:40]}…' — the bullet may be grammatically "
                                f"broken (generation/formatting failure)"
                            ),
                        )
                    )

            # Signal 3: "Noun1 and Noun2 both Noun3" with no verb
            # Pattern: two proper nouns joined by "and", then "both", then
            # a lowercase noun (not a verb).
            _disjoint = re.search(
                r"([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+both\s+([a-z]+)",
                line,
            )
            if _disjoint:
                third = _disjoint.group(3).lower()
                # Is the third word a verb? If not, it's a disjoint pattern.
                _is_verb = any(third.endswith(e) for e in _VERB_ENDINGS) and len(third) > 3
                if not _is_verb:
                    issues.append(
                        Issue(
                            detector="grammar",
                            severity="flag",
                            field=field_label,
                            snippet=_snippet(line, 0),
                            detail=(
                                f"disjoint subject-object: '{_disjoint.group(0)}' "
                                f"— '{_disjoint.group(1)} and {_disjoint.group(2)} "
                                f"both {_disjoint.group(3)}' has no verb between "
                                f"the subject and object. Likely a broken bullet."
                            ),
                        )
                    )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="grammar",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"grammar check crashed: {e!r}",
            )
        )
    return text, issues


def detect_extra_spaces(
    text: str,
    field_label: str,
    source_text: str = "",
    source_lower: str | None = None,
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V18.15.3.2: Detect words split by a spurious space — SOURCE-GROUNDED.

    NO external word lists. The source text is the only dictionary.

    Detection: any short word (1-3 chars) + space + fragment (3+ chars).
    The length filter is structural (not a curated stopword list).

    Validation (Phase 1 — direct): is the joined word a standalone word in
    the source? And is the fragment NOT in the source? If both → join.
    (If the fragment IS in the source, it's a real word, not a split fragment.)

    Validation (Phase 2 — adjacent-word guided): if Phase 1 fails, get
    adjacent words from the summary, find them in the source, search nearby
    for the joined word (allowing hyphens). If found → join.

    If neither phase validates → don't join (safe — no false positives).
    If source_text is empty/None → can't validate → return unchanged.
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues

    # V18.20.2.0 (SWOT A24): accept precomputed source_lower/source_words
    # from run_post_checks (was rebuilt per bullet); lazy-build when omitted.
    source_lower = source_lower if source_lower is not None else source_text.lower()
    # Build a set of standalone words in the source (for O(1) lookup)
    source_words = (
        source_words if source_words is not None else set(re.findall(r"\b[a-z]+\b", source_lower))
    )

    cleaned = text
    try:
        # Pattern: any short word (1-3 chars) + space + fragment (3+ chars)
        _SPLIT_RE = re.compile(r"\b([a-zA-Z]{1,3})\s+([a-z]{3,})\b")

        def _join_if_valid(m: re.Match) -> str:
            word1 = m.group(1).lower()
            fragment = m.group(2).lower()
            joined = word1 + fragment

            # V18.20.3.2 (audit N8 / P2-b): GLOBAL split-form veto. If the
            # split form ("ego ideal") appears ANYWHERE in the source as
            # standalone words, the two-word form is legitimate in this
            # source — never join. The V18.20.3.1 run joined 'ego ideal' →
            # 'egoideal' via Phase 2: a hyphenated 'ego-ideal' occurrence sat
            # inside the ±300-char window while the 8 spaced occurrences
            # elsewhere in the source went unseen (the old split-form guard
            # was window-local). The source is the dictionary — if it uses
            # the split form at all, we keep it.
            if re.search(
                r"\b" + re.escape(word1) + r"\s+" + re.escape(fragment) + r"\b",
                source_lower,
            ):
                return m.group(0)

            # Phase 1: Direct source lookup
            # Join only if: joined IS in source AND fragment is NOT in source.
            # This catches "the reby" → "thereby" (source has "thereby",
            # "reby" is not a standalone source word).
            if joined in source_words and fragment not in source_words:
                issues.append(
                    Issue(
                        detector="extra_space",
                        severity="fix",
                        field=field_label,
                        snippet=_snippet(cleaned, m.start()),
                        detail=f"joined split word: '{m.group(0)}' \u2192 '{joined}' (source-validated)",
                    )
                )
                return joined

            # Phase 2: Adjacent-word guided lookup
            # V18.15.3.2 bugfix: Phase 2 must search for the JOINED form
            # (or hyphenated variant), NOT the split form. The old regex
            # allowed an optional space between parts, which matched
            # "the core construct" in the source and falsely joined it to
            # "egoidentity". Now we search for the exact joined token or
            # the hyphenated variant only.
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            context = text[start:end].lower()
            context_words = [
                w for w in re.findall(r"\b[a-z]{4,}\b", context) if w != fragment and w != word1
            ]

            for adj_word in context_words[:4]:
                adj_pos = source_lower.find(adj_word)
                if adj_pos >= 0:
                    window_start = max(0, adj_pos - 300)
                    window_end = min(len(source_lower), adj_pos + 300)
                    window = source_lower[window_start:window_end]
                    # Search for the JOINED form as a standalone token,
                    # or the hyphenated variant (e.g., a compound term).
                    # Do NOT match the split form ("the core construct").
                    hyphenated = word1 + "-" + fragment
                    if re.search(r"\b" + re.escape(joined) + r"\b", window) or re.search(
                        r"\b" + re.escape(hyphenated) + r"\b", window
                    ):
                        # Extra safety: don't join if the split form (word1 + ' ' + fragment)
                        # also appears in the window as standalone words — that means
                        # the split form is legitimate in this source.
                        split_pattern = (
                            r"\b" + re.escape(word1) + r"\s+" + re.escape(fragment) + r"\b"
                        )
                        if re.search(split_pattern, window):
                            continue  # split form is in source → don't join
                        issues.append(
                            Issue(
                                detector="extra_space",
                                severity="fix",
                                field=field_label,
                                snippet=_snippet(cleaned, m.start()),
                                detail=f"joined split word: '{m.group(0)}' \u2192 '{joined}' (source-validated via adjacent '{adj_word}')",
                            )
                        )
                        return joined

            # Not found in source → don't join (safe)
            return m.group(0)

        cleaned = _SPLIT_RE.sub(_join_if_valid, cleaned)
    except Exception as e:
        issues.append(
            Issue(
                detector="extra_space",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"extra-space check crashed: {e!r}",
            )
        )
        return text, issues
    return cleaned, issues


def detect_word_fragment_merge(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
) -> tuple[str, list[Issue]]:
    """V18.2.19: Detect merged sentence-boundary fragments.

    Catches "adolescenceo fill" → "adolescence. To fill" where a period+T
    was dropped and "to" became "o". The result is a word + stray char(s)
    + space + another word.

    Detection (book-agnostic): finds ``(word)(1-2 stray chars) (word)``
    where the first part (word+stray) is NOT a known word, but the word
    alone IS known. This indicates the stray chars are a fragment of a
    dropped sentence boundary.

    Flag-only (doesn't auto-fix — the correct reconstruction is ambiguous:
    "adolescenceo" could be "adolescence. To" or "adolescence. O" etc.)

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".

    Returns:
        ``(text, issues)``. Text is UNCHANGED.
    """
    issues: list[Issue] = []

    # V18.20.2.0 (SWOT A24): accept the precomputed source word-set from
    # run_post_checks (was rebuilt per bullet); lazy-build when omitted.
    if source_words is None:
        source_words = set(re.findall(r"\b[a-z]+\b", source_text.lower())) if source_text else set()
    if not text:
        return text, issues
    try:
        for m in list(_FRAGMENT_MERGE_RE.finditer(text)):
            # V18.2.19: Check BOTH the left side (group1+group2) AND the
            # right side (group3) for word+stray patterns. The fragment
            # merge can appear on either side of the space.
            # Left: "emphasized" → group1="emphasize", group2="d" → "emphasized" IS a word (OK)
            # Right: "adolescenceo" → need to split group3 too.
            # Check the left side first:
            word = m.group(1).lower()
            stray = m.group(2).lower()
            full = (word + stray).lower()
            # V18.9 (Option B fix): Skip if stray is a legitimate English suffix
            # (plural 's', past tense 'ed', adjective 'al', etc.). This eliminates
            # the 5th-occurrence false-positive class where "differences", "conditions",
            # "contributions", etc. were flagged. These are valid inflections, NOT
            # dropped sentence boundaries.
            if word in source_words and full not in source_words and len(stray) <= 2:
                if _is_legitimate_inflection(word, stray):
                    continue  # valid plural/past-tense/adjective — not a fragment merge
                issues.append(
                    Issue(
                        detector="fragment_merge",
                        severity="flag",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"word-fragment merge: '{m.group(1)}{m.group(2)} {m.group(3)}' "
                            f"— '{word}' is a known word but '{full}' is not. "
                            f"The '{stray}' may be a remnant of a dropped "
                            f"sentence boundary (e.g. '. To')."
                        ),
                    )
                )
                continue
            # Check the right side (group3): is it a known word + stray chars?
            # E.g. "adolescenceo" → "adolescence" + "o"
            right = m.group(3).lower()
            # Try stripping 1-2 chars from the end and see if the base is known.
            for strip_len in (1, 2):
                if len(right) > strip_len + 3:
                    base = right[:-strip_len]
                    stray_right = right[-strip_len:]
                    if base in source_words and right not in source_words:
                        # V18.9 (Option B fix): Skip if the stripped suffix is a
                        # legitimate English inflection (plural, past tense, etc.)
                        if _is_legitimate_inflection(base, stray_right):
                            continue  # valid inflection — not a fragment merge
                        issues.append(
                            Issue(
                                detector="fragment_merge",
                                severity="flag",
                                field=field_label,
                                snippet=_snippet(text, m.start(3)),
                                detail=(
                                    f"word-fragment merge: '{m.group(3)}' "
                                    f"— '{base}' is a known word but '{right}' is not. "
                                    f"The trailing '{stray_right}' may be a remnant "
                                    f"of a dropped sentence boundary (e.g. '. To')."
                                ),
                            )
                        )
                        break
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="fragment_merge",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"fragment-merge check crashed: {e!r}",
            )
        )
    return text, issues
