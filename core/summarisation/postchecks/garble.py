"""V0.18 (Phase 5.2) — garbled-token / spacing-artifact detectors (+ English-lexicon guards).

Moved VERBATIM (byte-identical bodies) from ``postcheck_detectors.py``
during the Phase 5.2 regroup into the ``postchecks/`` package.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.shared import (  # noqa: F401
    Issue,
    _snippet,
)

_LONG_CONSONANT_CLUSTER_RE = re.compile(r"\b\w*[bcdfghjklmnpqrstvwxz]{6,}\w*\b", re.IGNORECASE)

_IMPOSSIBLE_BIGRAMS = (
    "xz",
    "zx",
    "qq",
    "zz",
    "kx",
    "xk",
    "jx",
    "xj",
    "qx",
    "xq",
    "vc",
    "cv",
    "kz",
    "zk",
    "jz",
    "zj",
)

_IMPOSSIBLE_BIGRAM_RE = re.compile(
    r"\b\w*(?:" + "|".join(_IMPOSSIBLE_BIGRAMS) + r")\w*\b", re.IGNORECASE
)

_VOWEL = "aeiouy"

_VOWEL_LESS_LONG_RE = re.compile(
    r"\b[^aeiouy\W\d]{5,}\b",
    re.IGNORECASE,  # V18.2.19: exclude digits (1980b etc.)
)

_MISSING_SPACE_CAP_RE = re.compile(r"\b([a-z]{1,3})([A-Z][a-zA-Z]{2,})\b")

_MISSING_SPACE_LOWER_RE = re.compile(r"\b([a-z]{1,3})([a-z]{4,})\b", re.IGNORECASE)

_CAMELCASE_MERGE_RE = re.compile(r"\b([a-z]{3,})([A-Z][a-zA-Z]{2,})\b")


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


_MERGED_SENTENCE_RE = re.compile(r"\.([A-Z][a-z]+)")

_VERB_ENDINGS = (
    "es",
    "ed",
    "ing",
    "ies",
    "ied",
    "ays",
    "ows",
    "aps",
    "ops",
    "ups",
    "ans",
    "ens",
    "ins",
    "ars",
    "ers",
    "irs",
    "ors",
    "urs",
    "ate",
    "ite",
    "ose",
    "ise",
    "ize",
    "ect",
    "act",
    "ict",
    "upt",
    "apt",
    "opt",
    "ain",
    "oin",
    "urn",
    "awn",
    # V18.2.19: Irregular verb endings (past tense + participles).
    "ade",  # made, bade, waded
    "oke",  # broke, spoke, woke
    "elt",  # felt, dealt, knelt
    "ew",  # knew, threw, grew, blew
    "at",  # sat, pat, chat
    "it",  # hit, split, quit
    "ut",  # shut, cut, put
    "et",  # set, let, get, met
    "ound",  # found, bound, wound
    "old",  # sold, told, held
    "ung",  # hung, sung, rung
    "unk",  # sunk, drunk, shrunk
)

_VERB_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "but",
        "for",
        "with",
        "from",
        "this",
        "that",
        "these",
        "those",
        "which",
        "what",
        "when",
        "where",
        "while",
        "during",
        "before",
        "after",
        "between",
        "among",
        "through",
        "without",
        "within",
        "against",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "must",
    }
)


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
            # Check for any finite verb (word >3 chars ending in a verb suffix,
            # not a stopword).
            has_verb = any(
                len(w) > 3
                and w.lower() not in _VERB_STOPWORDS
                and any(w.lower().endswith(e) for e in _VERB_ENDINGS)
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


_FRAGMENT_MERGE_RE = re.compile(
    r"\b([a-z]{4,})([a-z]{1,2})\s+([a-z]{2,})\b",
    re.IGNORECASE,
)

_LEGIT_SUFFIXES = frozenset(
    {
        "s",  # plural: difference→differences, condition→conditions
        "es",  # plural: box→boxes, church→churches
        "ed",  # past tense: contribute→contributed, view→viewed
        "er",  # comparative/agent: view→viewer, think→thinker
        "ly",  # adverb: quick→quickly, clear→clearly
        "al",  # adjective: environment→environmental, condition→conditional
        "ing",  # participle: run→running, think→thinking
        "est",  # superlative: big→biggest, fast→fastest
        "d",  # past tense: use→used, move→moved
        "ers",  # plural agent: view→viewers, think→thinkers
        "ies",  # plural: city→cities, theory→theories
        "ied",  # past tense: city→citied (rare but valid)
        "ier",  # comparative: happy→happier
        "iest",  # superlative: happy→happiest
        # present participle (duplicate for safety)
        "ic",  # adjective: history→historic
        "ity",  # noun: active→activity
        "ment",  # noun: develop→development
        "ness",  # noun: dark→darkness
        "tion",  # noun: act→action
        "able",  # adjective: use→usable
        "ible",  # adjective: access→accessible
        "ous",  # adjective: danger→dangerous
        "ive",  # adjective: act→active
        "ful",  # adjective: use→useful
        "less",  # adjective: use→useless
    }
)


def _is_legitimate_inflection(word: str, stray: str) -> bool:
    """V18.9: Check if word+stray is a legitimate English inflection of word.

    Returns True if ``stray`` is a standard English suffix (plural, past
    tense, adjective, etc.) — meaning ``word+stray`` is a valid word form,
    NOT a fragment-merge artifact.

    This eliminates the false-positive class where "differences" (word=
    "difference", stray="s") was flagged as a fragment merge. "differences"
    is the standard plural of "difference" — not a dropped sentence boundary.
    """
    return stray.lower() in _LEGIT_SUFFIXES


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


_MIN_GARBLED_WORD_LEN = 5

_MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE = 20000  # cap; larger sources skip the check


def _edit_distance_one_neighbors(word: str) -> set:
    """Return the set of all words within edit distance 1 of ``word``.

    Includes insertions, deletions, and substitutions of a single character.
    Used to check if a summary word is a garbled form of a source word.
    """
    neighbors = set()
    # Deletions (remove 1 char): "emergs" → "emerg", "emegs", "emers", ...
    for i in range(len(word)):
        neighbors.add(word[:i] + word[i + 1 :])
    # Insertions (add 1 char): "emergs" → "aemergs", "bemergs", ...
    # Limited to common letters to bound the set size.
    for i in range(len(word) + 1):
        for c in "abcdefghijklmnopqrstuvwxyz":
            neighbors.add(word[:i] + c + word[i:])
    # Substitutions (replace 1 char): "emergs" → "amergs", "bmergs", ...
    for i in range(len(word)):
        for c in "abcdefghijklmnopqrstuvwxyz":
            if c != word[i]:
                neighbors.add(word[:i] + c + word[i + 1 :])
    return neighbors


def _is_legitimate_inflection_pair(summary_word: str, source_word: str) -> bool:
    """V18.19.2.5 (tune): Is ``summary_word`` a legitimate English form of ``source_word``?

    The V18.19.2.4 audit found 16 false positives from detect_dropped_letter_garble:
    the detector flagged words like "author" (matching source "authors"), "clarifies"
    (matching "clarified"), "surveys" (matching "survey"), "paths" (matching "path") —
    all legitimate English inflections, NOT garbled tokens.

    The original "emergs"→"emerges" true positive is a NON-word ("emergs" is not
    real English). The false positives are all REAL English words that happen to be
    edit-distance-1 from a different source word via standard morphology.

    This helper checks if the edit-distance-1 relationship is a legitimate English
    morphological transformation (the summary word is an inflection/derivation of
    the source word, or vice versa). Returns True if it is → the flag should be
    suppressed (it's a false positive).

    Checks (any True → legitimate):
      1. The summary word ends with a standard suffix that, when stripped, yields
         the source word (e.g. "authors" - "s" = "author"). Covers plurals,
         verb conjugations, adverbs, adjectives.
      2. The source word ends with a standard suffix that, when stripped, yields
         the summary word (e.g. "clarified" - "d" = "clarifie" ≈ "clarifies" via
         further 'e'→'es' morph). Covers the reverse direction.
      3. The two words differ only by a trailing 's'/'es' (plural/3rd-person).
      4. The two words differ only by a trailing 'd'/'ed' (past tense).

    This is source-grounded morphology (grammatical structure, not a content
    dictionary — same exemption as _STRUCTURAL_STOPWORDS under the V18.15.3.2
    "no hand-curated word lists" constraint, which targets CONTENT dictionaries).
    """
    sw = summary_word.lower()
    src = source_word.lower()
    if sw == src:
        return True  # identical (shouldn't happen — caller already checked)
    # 1. summary word = source word + suffix (e.g. "authors" = "author" + "s")
    for suffix in _LEGIT_SUFFIXES:
        if sw == src + suffix:
            return True
    # 2. source word = summary word + suffix (e.g. "clarified" = "clarifie" + "d"
    #    — but "clarifie" isn't "clarifies"; this catches "drawn" vs "draw" where
    #    "drawn" = "draw" + "n"... actually "n" isn't a suffix. Let me handle
    #    the specific past-participle/past-tense cases below.)
    for suffix in _LEGIT_SUFFIXES:
        if src == sw + suffix:
            return True
    # 3. Trailing-s difference (plural / 3rd person singular):
    #    author↔authors, path↔paths, open↔opens, turn↔turns, split↔splits,
    #    survey↔surveys, attempt↔attempts
    if len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == "s":
        return True
    if len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == "s":
        return True
    # 4. Trailing-d/ed difference (past tense):
    #    describe↔described, clarify↔clarified, consolidate↔consolidated,
    #    emerge↔emerged (note: "emergs"≠"emerged" — emergs is a non-word, caught below)
    #    BUT "emergs" → "emerges" is NOT past tense (no d/ed) → still flagged. ✓
    if len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == "d":
        return True
    if len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == "d":
        return True
    if len(sw) == len(src) + 2 and sw.startswith(src) and sw[-2:] == "ed":
        return True
    if len(src) == len(sw) + 2 and src.startswith(sw) and src[-2:] == "ed":
        return True
    # 5. Past participle -n (draw↔drawn, show↔shown). Rare but legitimate.
    if len(sw) == len(src) + 1 and sw.startswith(src) and sw[-1] == "n":
        return True
    if len(src) == len(sw) + 1 and src.startswith(sw) and src[-1] == "n":
        return True

    # 6. V18.19.2.5: -y / -ies / -ied verb-conjugation + noun-plural transformations.
    #    clarifY↔clarifieS, clarifY↔clarifieD, identitY↔identitIES.
    def _y_to_ies(w: str) -> str:
        if w.endswith("y") and len(w) >= 3:
            return w[:-1] + "ies"
        return w

    def _y_to_ied(w: str) -> str:
        if w.endswith("y") and len(w) >= 3:
            return w[:-1] + "ied"
        return w

    def _ies_to_y(w: str) -> str:
        if w.endswith("ies") and len(w) >= 4:
            return w[:-3] + "y"
        return w

    def _ied_to_y(w: str) -> str:
        if w.endswith("ied") and len(w) >= 4:
            return w[:-3] + "y"
        return w

    for transform in (_y_to_ies, _y_to_ied, _ies_to_y, _ied_to_y):
        if transform(sw) == src or transform(src) == sw:
            return True
    # 8. V18.20.3.5 (audit v182034, user rule: no chapter-derived word
    # lists): Greek/Latin -is <-> -es plural pair. "basis"->"bases",
    # "analysis"->"analyses", "crisis"->"crises", "thesis"->"theses",
    # "diagnosis"->"diagnoses" — the singular ends in "is", the plural in
    # "es", and the stems are IDENTICAL. This is a general morphological
    # rule of English (a closed grammatical system), not a content word
    # list: it covers EVERY -is noun in any chapter, which is what
    #    replaces the V18.20.3.4 hand-added entries (learned from ONE
    # "bases" were learned from ONE book's false positives — exactly the
    # chapter-specific tuning the user banned).
    if sw.endswith("is") and src.endswith("es") and sw[:-2] == src[:-2] and len(sw) - 2 >= 3:
        return True
    if src.endswith("is") and sw.endswith("es") and src[:-2] == sw[:-2] and len(src) - 2 >= 3:
        return True
    # 10. V18.20.3.5: -is discipline vs -ts agent-plural tail swap:
    # "analysis" <-> "analysts" (equal length, identical prefix, ONLY the
    # (equal length, identical prefix, ONLY the last two characters differ
    # as is<->ts). The Greek-derived agent-noun pattern. This is the pair
    # the V18.20.3.4 hand-added stoplist entry was hand-blocking —
    # without a rule here the unique-candidate auto-repair would CORRUPT
    # "the analysis of society" into "the analysts of
    # society". Structural: prefix identity + tail is<->ts, no word list;
    # requires length >= 8 so it covers analysis/analysts while keeping
    # shorter coincidental pairs flagged.
    if (
        len(sw) == len(src)
        and len(sw) >= 8
        and sw[:-2] == src[:-2]
        and {sw[-2:], src[-2:]} == {"is", "ts"}
    ):
        return True
    # 9. V18.20.3.5: final-character inflection swap. Two words of EQUAL
    # length that share everything except the LAST character, where both
    # final characters are standard inflection endings (s/d/t/n —
    # 3rd-person, past, participle; 'e' deliberately EXCLUDED: the s<->e
    # swap is the bogus 3rd-person class "emergs"<->"emerge", the
    # detector's original true positive, and no real inflection pair
    # needs it): "meant" <-> "means" (irregular mean paradigm),
    # "notes" <-> "noted", "states" <-> "stated". Garbles of the dropped-letter class are
    #    edits at ARBITRARY positions (a garbled name differs at one position
    # 4 of 6), so restricting this blessing to the FINAL position keeps
    # the true-positive garble class flagged while covering the irregular
    # verb pairs that forced the old hand-list entries.
    _FINAL_INFLECTION_CHARS = frozenset("sdtn")
    if (
        len(sw) == len(src)
        and len(sw) >= 5
        and sw[:-1] == src[:-1]
        and sw[-1] in _FINAL_INFLECTION_CHARS
        and src[-1] in _FINAL_INFLECTION_CHARS
        and sw[-1] != src[-1]
    ):
        return True
    # 7. V18.19.2.5: shared-stem inflections — TIGHTENED. Two words that share
    #    a common stem (>=4 chars) AND differ ONLY by swapping one standard
    #    inflectional suffix for ANOTHER standard inflectional suffix (both
    #    suffixes in the set, equal length) are legitimate conjugation pairs.
    #    Examples:
    #      clarifIES ↔ clarifIED (stem "clarif", swap "ies"↔"ied" — both 3 chars)
    #      consolidatES ↔ consolidatED (stem "consolidat", swap "es"↔"ed" — both 2)
    #    But NOT:
    #      emergS ↔ emergES (stem "emerg", "s"↔"es" — but "emergs" is a non-word;
    #        the "s" here is a dropped letter, not a plural suffix. The signal:
    #        "emergs" stripped of "s" = "emerg" (4 chars), "emerges" stripped of
    #        "es" = "emerg" (4 chars) — stems match. BUT "s" and "es" differ in
    #        length by 1, and the shorter word "emergs" is not a real inflection
    #        of "emerg" (the 3rd-person is "emerges", not "emergs"). So we require
    #        the suffixes to be EQUAL length — a true conjugation swap, not a
    #        dropped-letter case.)
    _INFLECTION_SUFFIXES_BY_LEN = {
        3: (
            "ies",
            "ied",
            "ing",
            "est",
            "ers",
            "ment",
            "tion",
            "ness",
            "able",
            "ible",
            "ous",
            "ive",
            "ful",
            "less",
        ),
        2: ("es", "ed", "er", "al", "ly", "ic", "ity"),
        1: ("s", "d"),
    }
    for suf_len in (3, 2, 1):
        suffixes = _INFLECTION_SUFFIXES_BY_LEN[suf_len]
        if sw.endswith(suffixes) and src.endswith(suffixes):
            sw_stem = sw[:-suf_len] if len(sw) > suf_len else sw
            src_stem = src[:-suf_len] if len(src) > suf_len else src
            if (
                sw_stem == src_stem
                and len(sw_stem) >= 4
                and len(sw) == len(src)  # equal length → true suffix swap
                and sw[-suf_len:] != src[-suf_len:]
            ):  # different suffixes
                return True
    return False


# ── V0.03 (P0-1, real-rig audit): English lexicon for the garble guard ─────
#
# The V0.02 rig run proved the dropped-letter auto-repair corrupts valid
# paraphrases: 12 of 13 "repairs" swapped a real English word for a different
# source word ('contrast'→'contract', 'teams'→'beams', 'causes'→'cases',
# 'skill'→'still', 'simply'→'simple' …). The structural proxies (stoplists,
# inflection pairs, suffix decomposition) cannot separate a real word from a
# garble — only a dictionary can. This vendored lexicon (126,761 lowercase
# alpha words ≥4 chars, derived from the pyspellchecker English frequency
# dictionary, frequency ≥ 50) provides exactly that. It is a GENERAL English
# word list — not chapter- or book-derived (the V18.15.3.2 constraint bans
# hand-curated CONTENT lists; a frequency lexicon of the whole language is
# the same class of resource as a spell-checker, which this rule always
# needed to be).
_ENGLISH_LEXICON: set | None = None


def _load_english_lexicon() -> set:
    """Lazily load the vendored English lexicon (fail-open to empty set).

    Empty set ⇒ the dictionary guard is inactive (degrades to the V0.02
    behavior minus auto-repair, which is disabled by default anyway).
    """
    global _ENGLISH_LEXICON
    if _ENGLISH_LEXICON is None:
        try:
            import gzip as _gzip
            from pathlib import Path as _Path

            _p = _Path(__file__).parent / "data" / "english_lexicon.txt.gz"
            _ENGLISH_LEXICON = set(_gzip.decompress(_p.read_bytes()).decode("ascii").split())
        except Exception:  # fail-open — a missing lexicon must not crash postchecks
            _ENGLISH_LEXICON = set()
    return _ENGLISH_LEXICON


def _paragraph_corroborated(
    candidate: str,
    garble_word: str,
    match_start: int,
    text: str,
    source_text: str,
) -> bool:
    """V0.03 (P0-1 guard b): the repair candidate must live in a source
    paragraph that is among the BEST topical matches for the summary
    sentence being repaired (nearest-paragraph rule).

    The rig audit showed every false repair attracted its candidate from a
    DIFFERENT essay/section than the one the summary sentence was about
    (e.g. 'contrast' in a deployment sentence "repaired" to 'contract' from
    an unrelated agile-manifesto quote). GENERAL rule: compute content-word
    overlap (words ≥4 chars) between the summary sentence and every source
    paragraph; the candidate is corroborated iff it appears in a paragraph
    achieving the MAXIMUM overlap (ties allowed — section boundaries are
    fuzzy). When no paragraph shares any vocabulary (a fully paraphrased
    sentence, or a single-paragraph source), every paragraph ties at zero
    and the rule degrades to a vacuous pass — the remaining guards
    (lexicon non-word, strict uniqueness, position-0) still apply.
    """
    try:
        _sent_start = (
            max(
                text.rfind(". ", 0, match_start),
                text.rfind("! ", 0, match_start),
                text.rfind("? ", 0, match_start),
                text.rfind("\n", 0, match_start),
            )
            + 1
        )
        _sent_end_candidates = [
            p
            for p in (
                text.find(". ", match_start),
                text.find("! ", match_start),
                text.find("? ", match_start),
                text.find("\n", match_start),
            )
            if p != -1
        ]
        _sent_end = min(_sent_end_candidates) if _sent_end_candidates else len(text)
        _sent_words = {
            w
            for w in re.findall(r"[a-z]{4,}", text[_sent_start:_sent_end].lower())
            if w != garble_word
        }
        _paras = [p for p in source_text.split("\n\n") if p.strip()]
        if not _paras:
            return False
        _best = -1
        _para_words_cache: list[set] = []
        for _para in _paras:
            _pw = set(re.findall(r"[a-z]{4,}", _para.lower()))
            _para_words_cache.append(_pw)
            _ov = len(_sent_words & _pw)
            if _ov > _best:
                _best = _ov
        # Corroborated iff the candidate lives in a max-overlap paragraph.
        for _pw in _para_words_cache:
            if candidate in _pw and len(_sent_words & _pw) == _best:
                return True
        return False
    except Exception:
        # Fail-open on structure problems: corroboration unavailable → the
        # caller keeps the flag-only path (never crashes a conversion).
        return False


def detect_dropped_letter_garble(
    text: str,
    field_label: str,
    source_text: str = "",
    source_words: set | None = None,
    auto_repair: bool = False,
) -> tuple[str, list[Issue]]:
    """V18.19.2.3 (Audit Fix 5): Detect single-character garbled tokens.
    V18.19.2.5 (tune): Suppress false positives on legitimate English inflections.

    Catches words like "emergs" (should be "emerges"), "identiy" (should be
    "identity"), "Dukhaim" (should be "AuthorY") — words that are NOT in the
    source but become a source word after a single-character edit (insert /
    delete / substitute).

    V18.19.2.5 tuning (per the V18.19.2.4 audit): the V18.19.2.3 detector produced
    16 false positives — flagging legitimate English words ("author", "clarifies",
    "surveys", "paths", "seven") that happen to be edit-distance-1 from a different
    source word. The fix: suppress the flag if the edit-distance-1 relationship is
    a legitimate English morphological transformation (the summary word is an
    inflection/derivation of the source word via a standard suffix). This keeps
    the true positive ("emergs"→"emerges" — "emergs" is a non-word) while dropping
    the 16 false positives (all real English words).

    Source-grounded: no hand-curated content word list (per the V18.15.3.2
    constraint). The morphological suffix set is grammatical structure, not a
    content dictionary — same exemption as _STRUCTURAL_STOPWORDS.

    A word is flagged only if:
      1. It's >= 5 chars (shorter words have too many false-positive neighbors).
      2. It's NOT in the source text (already-legitimate source words are exempt).
      3. A single-character edit makes it match a source word.
      4. The edit-distance-1 relationship is NOT a legitimate English inflection
         (V18.19.2.5: _is_legitimate_inflection_pair check).
      5. It's not in the _STRUCTURAL_STOPWORDS exempt set.
      6. V0.03 (P0-1 guard a): it is NOT a valid English word per the vendored
         lexicon — a real dictionary word is never a garble, regardless of its
         edit-distance-1 neighbors ('causes' exists even when the source only
         contains 'cases').
      7. V0.03 (P0-1 guard d): it does not appear more than once in the summary
         text — repeated vocabulary is deliberate authorial choice, not a typo.

    V18.20.3.4 (RC-3) originally auto-fixed unambiguous repairs. V0.03 (P0-1,
    real-rig audit) DISABLES auto-repair by default: the V0.02 rig run showed
    12 of 13 auto-repairs corrupted valid paraphrase words. When ``auto_repair``
    is explicitly enabled, a repair additionally requires ALL of:
      (a) the token is not a valid English dictionary word (guard a),
      (b) paragraph corroboration — the candidate appears in a source paragraph
          sharing content words with the summary sentence being repaired,
      (c) exactly ONE source word at edit distance 1 counting inflection
          partners too (the 'skill'→'still' corruption happened because
          'skills' was excluded as an "inflection", leaving 'still' spuriously
          "unique"),
      (d) the pre-existing position-0 inflected-form guard.
    Failed guards degrade to flag-only — the log stays honest, the text stays
    untouched. Flags are advisory; repairs rewrite user-facing text.

    Args:
        text: the summary text to scan.
        field_label: "exec" / "thorough" / "bullet[N]".
        source_text: the source chapter text.
        auto_repair: V0.03 — default False (disabled until re-validated on a
            real rig). When True, guarded auto-repair is allowed.

    Returns:
        ``(text, issues)``. Text carries only guarded auto-repairs (when
        enabled); everything else leaves it unchanged.
    """
    issues: list[Issue] = []
    # V18.20.3.4 (RC-3): queued (garble, repair) pairs — applied after
    # the scan loop. Initialized OUTSIDE the try so a crash anywhere in
    # the scan still leaves the post-loop application valid.
    _repairs: list = []
    if not text or not source_text:
        return text, issues
    # V0.03 (P0-1 guard a): load once per process (lazy singleton).
    _lexicon = _load_english_lexicon()
    try:
        # V18.20.2.0 (SWOT A24): accept the precomputed source word-set from
        # run_post_checks (was rebuilt per bullet/exec/thorough call);
        # lazy-build when omitted.
        if source_words is None:
            source_words = set(re.findall(r"\b[a-z]+\b", source_text.lower()))
        if len(source_words) > _MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE:
            # Skip for very large sources (perf guard — rare; the 9120-token
            # trust-ground produces ~2500 unique words, well under the cap).
            return text, issues
        # Pre-build a set of source words >= _MIN_GARBLED_WORD_LEN - 1 (so a
        # deletion could land in range). This bounds the neighbor-checking.
        candidate_sources = {w for w in source_words if len(w) >= _MIN_GARBLED_WORD_LEN - 1}
        if not candidate_sources:
            return text, issues
        seen: set = set()
        _word_pat = rf"\b[a-zA-Z]{{{_MIN_GARBLED_WORD_LEN},}}\b"
        for m in re.finditer(_word_pat, text):
            word = m.group(0).lower()
            if word in seen:
                continue
            seen.add(word)
            # Skip if the word IS in the source (legitimate).
            if word in source_words:
                continue
            if word in _STRUCTURAL_STOPWORDS:
                continue
            # V18.20.3.2 (audit N7 / P2-a): common-English-word stoplist. The
            # V18.20.3.1 run false-flagged 8 ordinary words ('moving', 'seven',
            # 'stages', 'clarify', 'fusing', 'raising', 'identifies') that are
            # real English merely absent from that source. A common word is
            # never a garble candidate regardless of its edit-distance-1
            # neighbors (latent-corruption guard: a future auto-fix would
            # otherwise turn 'moving through' into 'loving').
            if _common_word_stem_in_stoplist(word):
                continue
            # V0.03 (P0-1 guard a): dictionary guard — a valid English word is
            # never a garble, period. This is the general rule the stoplist/
            # inflection/suffix proxies were approximating; the V0.02 rig run
            # proved the proxies insufficient ('causes', 'teams', 'contrast',
            # 'simply', 'agility' … are all real words that got "repaired").
            if word in _lexicon:
                continue
            # V0.03 (P0-1 guard d): a token the model used more than once is
            # deliberate vocabulary, not a one-off typo.
            if len(re.findall(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE)) > 1:
                continue
            # Check if any edit-distance-1 neighbor is a source word.
            neighbors = _edit_distance_one_neighbors(word)
            matching_source = candidate_sources & neighbors
            if not matching_source:
                continue
            # V18.19.2.5 (tune): suppress false positives on legitimate English
            # inflections. If the edit-distance-1 relationship is a standard
            # morphological transformation (plural, verb conjugation, etc.),
            # the summary word is a real English word — NOT garbled. Only flag
            # if NONE of the matching source words are legitimate inflection
            # partners (i.e. the summary word is a true non-word like "emergs").
            non_inflection_matches = {
                src_w
                for src_w in matching_source
                if not _is_legitimate_inflection_pair(word, src_w)
            }
            if not non_inflection_matches:
                # All edit-distance-1 matches are legitimate inflections →
                # the summary word is a real English word. Suppress the flag.
                # (e.g. "author" matches "authors" via plural — suppress.)
                continue
            # V0.03 (P0-1): the RC-3 auto-repair is OFF unless explicitly
            # enabled (auto_repair=True), and even then must pass guard (c):
            # exactly ONE source word at edit distance 1 counting inflection
            # partners too. The V0.02 rig corruption 'skill'→'still' happened
            # precisely because 'skills' (the correct distance-1 partner) was
            # excluded as an "inflection", leaving 'still' spuriously unique.
            # Case is preserved: a capitalized garble gets a capitalized repair.
            _repair_allowed = (
                auto_repair and len(matching_source) == 1 and len(non_inflection_matches) == 1
            )
            if _repair_allowed and not _paragraph_corroborated(
                next(iter(matching_source)),
                word,
                m.start(),
                text,
                source_text,
            ):
                # V0.03 (P0-1 guard b): the only candidate lives in a source
                # paragraph that does not overlap this sentence's content —
                # not a credible reconstruction. Degrade to flag-only.
                _repair_allowed = False
            if _repair_allowed:
                _repair = next(iter(non_inflection_matches))
                _orig_tok = m.group(0)
                if _orig_tok[:1].isupper():
                    _repair_tok = _repair.capitalize()
                else:
                    _repair_tok = _repair
                # V18.20.3.5 (audit v182034, user rule: no chapter-derived
                # word lists): POSITION-0 INFLECTED-FORM GUARD on the
                # auto-repair. The residual false-repair class after the
                # rule-8/rule-9 morphology coverage: a real English word
                # that is edit-distance-1 from a DIFFERENT source word via
                # a LEADING-character edit — "elated" vs "related",
                # "review" vs "preview", "version" vs "aversion". These
                # pairs share no morphology, so only lexical knowledge
                # separates them; without a lexicon, the structural
                # proxy is: a token that DECOMPOSES as stem + standard
                # inflection suffix ("elat"+"ed", "review" has none) looks
                # like a real inflected English form and is NOT
                # auto-repaired (flag-only, human decides). Non-decomposing
                # tokens (the audit's true positive) still
                # auto-repair. Purely structural, no word list.
                _pos0_edit = word == _repair[1:] or _repair == word[1:]
                _looks_inflected = any(
                    word.endswith(_suf) and len(word) - len(_suf) >= 3 for _suf in _COMMON_SUFFIXES
                )
                if _pos0_edit and _looks_inflected:
                    issues.append(
                        Issue(
                            detector="dropped_letter",
                            severity="flag",
                            field=field_label,
                            snippet=_snippet(text, m.start()),
                            detail=(
                                f"possible garble: '{_orig_tok}' is edit-distance-1 "
                                f"(leading-character edit) from source word "
                                f"'{_repair}' — but '{_orig_tok}' decomposes as a "
                                f"stem + standard English suffix, so it may be a "
                                f"real word unrelated to '{_repair}' (the "
                                f"'elated'/'related' class). NOT auto-repaired; "
                                f"verify manually."
                            ),
                        )
                    )
                    continue
                issues.append(
                    Issue(
                        detector="dropped_letter",
                        severity="fix",
                        field=field_label,
                        snippet=_snippet(text, m.start()),
                        detail=(
                            f"guarded auto-repair of garbled token: '{_orig_tok}' → "
                            f"'{_repair_tok}' (non-word per English lexicon; the ONLY "
                            f"source word at edit distance 1; paragraph-corroborated — "
                            f"V0.03 P0-1, the 'emergs'→'emerges' class)"
                        ),
                    )
                )
                # Queue the repair (word-boundary-scoped so a substring
                # token can never be partially rewritten). Applied AFTER
                # the scan loop so the finditer match positions stay valid
                # for subsequent issues' snippets.
                _repairs.append((_orig_tok, _repair_tok))
                seen.add(_repair)
                continue
            _suggestion = sorted(non_inflection_matches)[0]
            issues.append(
                Issue(
                    detector="dropped_letter",
                    severity="flag",
                    field=field_label,
                    snippet=_snippet(text, m.start()),
                    detail=(
                        f"likely garbled token: '{m.group(0)}' is not in the source "
                        f"and is not a legitimate inflection of any source word, "
                        f"but is edit-distance-1 from '{_suggestion}' "
                        f"(single-char insert/delete/substitute). "
                        f"V18.19.2.5: caught 'emergs'→'emerges' (non-word) class."
                    ),
                )
            )
    except Exception as e:  # fail-open
        issues.append(
            Issue(
                detector="dropped_letter",
                severity="flag",
                field=field_label,
                snippet=text[:60],
                detail=f"dropped-letter check crashed: {e!r}",
            )
        )
    # V18.20.3.4 (RC-3): apply the queued unambiguous repairs now that the
    # scan is done (match positions are no longer needed). Word-boundary
    # scoping keeps a substring token from being partially rewritten.
    for _orig_tok, _repair_tok in _repairs:
        try:
            text = re.sub(
                r"(?<!\w)" + re.escape(_orig_tok) + r"(?!\w)",
                _repair_tok.replace("\\", "\\\\"),
                text,
            )
        except re.error:
            pass  # defensive — a repair regex failure must not lose the flag
    return text, issues


# Tiny structural-stopword set (function words only — NOT a content dictionary).
# Exempt from the "no hand-curated word lists" constraint (V18.15.3.2) because
# these are grammatical glue, not content claims. Keeps the detector from
# flagging "because"/"therefore"/"however" on chapters that don't happen to
# contain them verbatim.
_STRUCTURAL_STOPWORDS = frozenset(
    {
        "because",
        "therefore",
        "however",
        "moreover",
        "furthermore",
        "nevertheless",
        "thus",
        "hence",
        "although",
        "though",
        "whereas",
        "while",
        "unless",
        "between",
        "through",
        "during",
        "before",
        "after",
        "since",
        "until",
        "against",
        "without",
        "within",
        "among",
        "across",
        "behind",
        "beyond",
        "already",
        "always",
        "never",
        "often",
        "sometimes",
        "usually",
        # V18.20.3.4 (RC-3 hardening, found while verifying the auto-repair):
        # high-frequency function/frequency words that are edit-distance-1 from
        # a DIFFERENT common word ("thorough"≈"through", "from"≈"form",
        # "their"≈"there"). The V18.20.3.4 auto-repair makes the stoplist
        # safety-critical (a missed common word could be "repaired" into its
        # neighbor), so the preposition/determiner/adverb core of English is
        # exempted here — grammatical glue, not content claims.
        "from",
        "than",
        "then",
        "there",
        "their",
        "about",
        "into",
        "upon",
        "over",
        "under",
        "again",
        "almost",
        "perhaps",
        "quite",
        "rather",
        "still",
        "just",
        "even",
        "also",
        "both",
        "either",
        "neither",
        "instead",
        "indeed",
        "somewhat",
        "thorough",
    }
)

# V18.20.3.2 (audit N7 / P2-a): common-English-word stoplist for the
# dropped-letter detector. The V18.20.3.1 run false-flagged 8 ORDINARY words
# ('identifies', 'fusing', 'raising', 'clarify' ×2, 'moving', 'seven',
# 'stages') — legitimate English absent from that particular source but
# edit-distance-1 from a DIFFERENT source word ('seven'→'seen',
# 'stages'→'states', 'clarify'→'clarity', 'moving'→'loving', …). The
# V18.19.2.5 inflection check only suppresses morphological pairs
# (author→authors), not unrelated real words. This stoplist covers the
# high-frequency English lexicon (base forms; inflections are checked via
# suffix-stripping below). Same exemption class as _STRUCTURAL_STOPWORDS:
# grammatical/lexical structure, not content claims — and it only ever
# SUPPRESSES flags (latent-corruption risk: any future auto-fix built on
# this detector would otherwise turn "moving through" into "loving").
_COMMON_ENGLISH_WORDS = frozenset(
    {
        # high-frequency verbs (base forms; inflections stripped before lookup)
        "make",
        "take",
        "give",
        "get",
        "put",
        "keep",
        "find",
        "hold",
        "come",
        "go",
        "see",
        "look",
        "know",
        "think",
        "say",
        "tell",
        "use",
        "show",
        "move",
        "live",
        "work",
        "call",
        "try",
        "ask",
        "need",
        "feel",
        "become",
        "leave",
        "mean",
        "meet",
        "run",
        "help",
        "talk",
        "turn",
        "start",
        "bring",
        "lose",
        "pay",
        "sit",
        "stand",
        "hear",
        "play",
        "grow",
        "raise",
        "rise",
        "fall",
        "fell",
        "pass",
        "cross",
        "cut",
        "read",
        "write",
        "speak",
        "spoke",
        "learn",
        "teach",
        "taught",
        "buy",
        "sell",
        "send",
        "build",
        "break",
        "broke",
        "share",
        "carry",
        "catch",
        "caught",
        "choose",
        "chose",
        "deal",
        "draw",
        "drew",
        "drive",
        "drove",
        "eat",
        "feed",
        "fill",
        "fly",
        "flew",
        "follow",
        "forget",
        "hang",
        "happen",
        "hit",
        "hope",
        "join",
        "jump",
        "kill",
        "land",
        "laugh",
        "lead",
        "led",
        "let",
        "lie",
        "lay",
        "light",
        "love",
        "marry",
        "match",
        "miss",
        "mix",
        "open",
        "close",
        "order",
        "own",
        "pick",
        "plan",
        "point",
        "press",
        "prove",
        "pull",
        "push",
        "reach",
        "realize",
        "remain",
        "remember",
        "repeat",
        "reply",
        "report",
        "require",
        "rest",
        "return",
        "ride",
        "ring",
        "save",
        "seem",
        "serve",
        "set",
        "settle",
        "shake",
        "shine",
        "shoot",
        "shout",
        "sing",
        "sang",
        "sleep",
        "smell",
        "smile",
        "spend",
        "spread",
        "stay",
        "step",
        "stick",
        "stop",
        "study",
        "support",
        "survive",
        "swim",
        "swing",
        "taste",
        "tear",
        "thank",
        "throw",
        "threw",
        "touch",
        "train",
        "travel",
        "treat",
        "trust",
        "understand",
        "understood",
        "visit",
        "wait",
        "wake",
        "walk",
        "want",
        "warm",
        "wash",
        "watch",
        "wear",
        "wore",
        "win",
        "won",
        "wish",
        "wonder",
        "worry",
        # common verbs that appeared as real FPs in the V18.20.3.1 audit
        "clarify",
        "fuse",
        "identify",
        "argue",
        "assert",
        "note",
        "observe",
        "recognize",
        "suggest",
        "emphasize",
        "highlight",
        "distinguish",
        "examine",
        "explore",
        "trace",
        "define",
        "view",
        "consider",
        # numbers (edit-distance-1 traps: seven→seen, nine→none)
        "seven",
        "eight",
        "nine",
        "three",
        "four",
        "five",
        "six",
        "ten",
        "eleven",
        "twelve",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
        "none",
        "one",
        "two",
        # high-frequency nouns/adjectives/adverbs
        "stage",
        "state",
        "case",
        "place",
        "part",
        "fact",
        "force",
        "form",
        "kind",
        "type",
        "sort",
        "field",
        "group",
        "level",
        "sense",
        "side",
        "thing",
        "time",
        "value",
        "world",
        "area",
        "body",
        "book",
        "child",
        "city",
        "class",
        "color",
        "day",
        "door",
        "east",
        "end",
        "even",
        "example",
        "eye",
        "face",
        "family",
        "father",
        "feet",
        "figure",
        "girl",
        "hand",
        "head",
        "hour",
        "idea",
        "inch",
        "interest",
        "job",
        "king",
        "lady",
        "language",
        "law",
        "letter",
        "line",
        "list",
        "man",
        "matter",
        "may",
        "method",
        "mind",
        "minute",
        "moment",
        "money",
        "month",
        "mother",
        "mouth",
        "music",
        "name",
        "nation",
        "nature",
        "night",
        "north",
        "number",
        "object",
        "office",
        "page",
        "paper",
        "person",
        "picture",
        "piece",
        "plant",
        "power",
        "price",
        "problem",
        "question",
        "race",
        "rate",
        "reason",
        "record",
        "research",
        "result",
        "right",
        "river",
        "road",
        "rock",
        "room",
        "rule",
        "school",
        "science",
        "season",
        "second",
        "sentence",
        "series",
        "service",
        "shape",
        "ship",
        "short",
        "sound",
        "south",
        "space",
        "special",
        "story",
        "street",
        "student",
        "subject",
        "table",
        "teacher",
        "test",
        "theory",
        "thought",
        "title",
        "today",
        "topic",
        "town",
        "trade",
        "true",
        "unit",
        "voice",
        "war",
        "water",
        "way",
        "week",
        "west",
        "wheel",
        "woman",
        "word",
        "young",
        # V18.20.3.4 (RC-5a, audit v182033) → V18.20.3.5 POLICY CHANGE (user
        # rule: "never add a word list of this chapter — solve problems
        # fundamentally"): the .3.4 entries added after auditing ONE book's
        # false positives ("analysis", "elated", "argues", "asserts",
        # "noted", "means") are REMOVED. Their FP classes are now covered by
        # the general morphological rules added to
        # _is_legitimate_inflection_pair (rule 8: Greek -is/-es plurals covers
        # -is plurals, basis/bases, analysis/analyses in ANY
        # chapter; rule 9: final-char inflection swap covers meant/means); the
        # bare-inflection entries are redundant with the suffix-stripping
        # lookup below (argues→argue, asserts→assert, noted→note, means→mean
        # are all in the base list). Kept entries are top-3000 general English
        # (analysis, analyst, base, basis, mean, meant) that belong in ANY
        # English lexicon, independent of any book. POLICY: this set accepts
        # ONLY general-English core vocabulary and grammatical structure —
        # never words learned from a specific chapter's audit.
        "analysis",
        "analyst",
        "base",
        "basis",
        "meant",
    }
)

# Common English inflection suffixes — stripped before the stoplist lookup
# ("moving" → "move" ✓, "stages" → "stage" ✓, "identifies" → "identify" ✓).
# V18.20.3.2 fix: -ing strips also try stem+"e" (English drops the 'e'
# before -ing: move→moving, fuse→fusing) — the naive strip gave "mov"/"fus"
# and the FP suppression missed exactly the two audit words.
_COMMON_SUFFIXES = (
    "ies",
    "ied",
    "ing",
    "est",
    "ers",
    "es",
    "ed",
    "er",
    "ly",
    "s",
    "d",
)


def _common_word_stem_in_stoplist(word: str) -> bool:
    """V18.20.3.2 (P2-a): True when ``word`` (lowercase) is a common English
    word — either directly in ``_COMMON_ENGLISH_WORDS`` or its base form
    (after stripping one common inflection suffix) is."""
    if word in _COMMON_ENGLISH_WORDS:
        return True
    for suf in _COMMON_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            stem = word[: -len(suf)]
            if suf == "ies" or suf == "ied":
                stem = word[: -len(suf)] + "y"
            if stem in _COMMON_ENGLISH_WORDS:
                return True
            # -ing / -ed restore the dropped 'e' (move→moving, fuse→fusing,
            # raise→raised).
            if suf == "ing" or suf == "ed":
                if (stem + "e") in _COMMON_ENGLISH_WORDS:
                    return True
    return False


# ── V0.20.5 (Quality Campaign, brainstorm D1): surname-garble cross-check ──


# Pattern: "Surname (year)" or "Surname (<em>year</em>)" — the author-year
# citation form the summary uses. Strips <em> tags before matching so the
# year is a clean 4-digit string.
_AUTHOR_YEAR_RE = re.compile(
    r"\b([A-Z][a-z]{2,}(?:[-\s][A-Z][a-z]+)?)\s*\(\s*(?:<em[^>]*>)?\s*(\d{4})",
)


def detect_and_repair_author_garbles(
    text: str,
    field_label: str,
    source_authors: list[str] | None = None,
) -> tuple[str, list[Issue]]:
    """V0.20.5 (brainstorm D1): cross-check every "Surname (year)" pattern in
    the summary against the source's author list. If a surname is edit-
    distance-1 from a source author (e.g., a dropped-letter garble of a
    cited author's surname), auto-repair it.

    Content-agnostic: the source author list comes from the RUNTIME
    deterministic analysis (extract_citations on the source text), not a
    hardcoded list. No book-derived names are embedded in this code.

    Args:
        text: the summary field text (bullet, exec, or thorough).
        field_label: "bullet", "exec", or "thorough".
        source_authors: the surnames extracted from the source chapter
            (from extract_citations). When None or empty, the detector is
            a no-op (returns the text unchanged, no issues).

    Returns:
        ``(repaired_text, issues)``. Each issue is a ``name_garble`` fix
        with the repaired surname.
    """
    issues: list[Issue] = []
    if not text or not source_authors:
        return text, issues
    try:
        # Build a casefold set of source author surnames for fast lookup.
        source_set = {a.casefold(): a for a in source_authors if len(a) >= 4}
        if not source_set:
            return text, issues

        # Build edit-distance-1 neighbors for each source author. If a
        # summary surname matches a neighbor, it's a garble of that author.
        # (e.g., a source author's surname with one dropped letter.)
        author_neighbors: dict[str, str] = {}  # casefold garble → original source author
        for src_auth in source_authors:
            if len(src_auth) < 4:
                continue
            for neighbor in _edit_distance_one_neighbors(src_auth.casefold()):
                # Only register a neighbor if it's NOT itself a source author
                # (avoids "Gediman" matching itself as a garble of "Gediman").
                if neighbor not in source_set:
                    author_neighbors[neighbor] = src_auth

        # Find all "Surname (year)" patterns and check for garbles.
        # V0.4 (Quality Campaign, audit V0.3 ch.3): add a fuzzy-matching
        # fallback for SEVERE garbles (edit distance >>1) — a cited author's
        # name corrupted beyond one-letter drops. The edit-distance-1 check
        # above catches one-letter drops; the fuzzy check below catches
        # multi-character corruption using rapidfuzz similarity ratio.
        # Threshold: >=80% similarity to a source author (with length >= 4)
        # that is NOT an exact match. Content-agnostic (uses the runtime list).
        try:
            from rapidfuzz import fuzz as _rf_fuzz

            _has_fuzz = True
        except ImportError:
            _has_fuzz = False

        def _repair_match(m: re.Match) -> str:
            surname = m.group(1)
            surname_cf = surname.casefold()
            # If the surname is already an exact source author, no garble.
            if surname_cf in source_set:
                return m.group(0)
            # Check 1: edit-distance-1 (fast, catches one-letter drops).
            if surname_cf in author_neighbors:
                correct = author_neighbors[surname_cf]
                issues.append(
                    Issue(
                        detector="name_garble",
                        severity="fix",
                        field=field_label,
                        snippet=m.group(0)[:60],
                        detail=(
                            f"repaired author-name garble: {surname!r} → {correct!r} "
                            f"(edit-distance-1 from source author; cross-checked "
                            f"against the runtime analysis author list)"
                        ),
                    )
                )
                return m.group(0).replace(surname, correct, 1)
            # Check 2 (V0.4): fuzzy matching for severe garbles (>=80%
            # similarity to a source author). Catches a severely corrupted
            # cited author's name (the V0.3 ch.3 audit defect). Only fires
            # when rapidfuzz is available AND the surname is >= 4 chars AND
            # no exact/ed-1 match was found.
            if _has_fuzz and len(surname) >= 4:
                _best_ratio = 0.0
                _best_match: str | None = None
                for src_cf, src_orig in source_set.items():
                    if abs(len(surname) - len(src_cf)) > max(len(surname), len(src_cf)) // 2:
                        continue  # skip if length difference is too large
                    _ratio = _rf_fuzz.ratio(surname_cf, src_cf)
                    if _ratio > _best_ratio:
                        _best_ratio = _ratio
                        _best_match = src_orig
                if _best_match and _best_ratio >= 80.0:
                    issues.append(
                        Issue(
                            detector="name_garble",
                            severity="fix",
                            field=field_label,
                            snippet=m.group(0)[:60],
                            detail=(
                                f"repaired author-name garble (fuzzy): {surname!r} → "
                                f"{_best_match!r} ({_best_ratio:.0f}% similarity to "
                                f"source author; cross-checked against the runtime "
                                f"analysis author list)"
                            ),
                        )
                    )
                    return m.group(0).replace(surname, _best_match, 1)
            return m.group(0)

        repaired = _AUTHOR_YEAR_RE.sub(_repair_match, text)
        return repaired, issues
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("name-garble detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues


# ── V0.20.5 (Quality Campaign, brainstorm D2): stray-quote repair ──


def repair_stray_quotes(
    text: str,
    field_label: str,
) -> tuple[str, list[Issue]]:
    """V0.20.5 (brainstorm D2): repair stray/misplaced double-quotes.

    The V0.20.4 thorough summary had ~10 instances of misplaced closing
    quotes where the model opened a quote but misplaced the closing quote
    (e.g., a quoted phrase followed by a comma where the closing quote
    landed after the comma instead of after the phrase). The existing
    quote_verification postcheck strips mismatched quotes, but it doesn't
    catch all shapes.

    This detector finds lines with an ODD number of double-quote characters
    (a stray quote) and removes the orphan opening or closing quote. The
    heuristic: if a line has an odd quote count, the LAST quote is the
    orphan — remove it. This is conservative (removes one quote per odd-
    count line) and content-agnostic (no hardcoded quote patterns).

    Args:
        text: the summary field text.
        field_label: "bullet", "exec", or "thorough".

    Returns:
        ``(repaired_text, issues)``. Each issue is a ``stray_quote`` fix.
    """
    issues: list[Issue] = []
    if not text:
        return text, issues
    try:
        lines = text.split("\n")
        repaired_lines = []
        for line in lines:
            quote_count = line.count('"')
            if quote_count % 2 == 1 and quote_count >= 1:
                # Odd quote count → stray quote. Remove the LAST quote
                # (the most likely orphan — a misplaced closing quote).
                last_quote_idx = line.rfind('"')
                repaired_line = line[:last_quote_idx] + line[last_quote_idx + 1 :]
                issues.append(
                    Issue(
                        detector="stray_quote",
                        severity="fix",
                        field=field_label,
                        snippet=line[:60],
                        detail=(
                            f"removed a stray double-quote (line had {quote_count} "
                            f"quotes — odd count; removed the last quote)"
                        ),
                    )
                )
                repaired_lines.append(repaired_line)
            else:
                repaired_lines.append(line)
        return "\n".join(repaired_lines), issues
    except Exception as e:  # pragma: no cover — detector must never break the chapter
        from core.summarisation.postchecks.shared import logger

        logger.warning("stray-quote detector crashed (non-fatal): %s: %s", type(e).__name__, e)
        return text, issues
