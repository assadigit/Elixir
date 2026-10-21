"""V0.4.19 — shared lexicon constants and helpers for the garble family.

Moved VERBATIM from ``garble.py`` during the V0.4.19 de-monolithization:
the module-level regex/lexicon constants and the morphology/lexicon helpers
shared across detector groups, kept in their original definition order.
``_ENGLISH_LEXICON`` remains a lazily-loaded module global owned by
``_load_english_lexicon`` (once-per-process caching, fail-open to the empty
set) — exactly the pre-split semantics.

One deliberate path adaptation: this module lives one directory deeper
(``postchecks/garble/``) than the old flat ``garble.py``, so the vendored
lexicon is anchored one parent higher. The data file itself did not move.
"""

from __future__ import annotations

import re

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

            # V0.4.19 (de-monolithization): this module moved one level
            # deeper (postchecks/garble/lexicon.py), so the vendored
            # lexicon is anchored one parent higher — the data file
            # itself did not move (postchecks/data/english_lexicon.txt.gz).
            # V0.6.63: app_paths keeps that working in the PyInstaller bundle.
            from app_paths import resource_path

            _p = resource_path(
                "core", "summarisation", "postchecks", "data", "english_lexicon.txt.gz"
            )
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
