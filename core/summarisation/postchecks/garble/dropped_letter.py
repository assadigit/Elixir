"""V0.4.19 — the dropped-letter garble detector (the largest single detector).

``detect_dropped_letter_garble`` moved VERBATIM from ``garble.py`` during
the V0.4.19 de-monolithization. The lexicon/morphology helpers it uses
(``_load_english_lexicon``, ``_is_legitimate_inflection_pair``, the
stoplists, …) live in ``garble.lexicon`` and are imported by name.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.garble.lexicon import (
    _COMMON_SUFFIXES,
    _MAX_SOURCE_WORDS_FOR_EDIT_DISTANCE,
    _MIN_GARBLED_WORD_LEN,
    _STRUCTURAL_STOPWORDS,
    _common_word_stem_in_stoplist,
    _edit_distance_one_neighbors,
    _is_legitimate_inflection_pair,
    _load_english_lexicon,
    _paragraph_corroborated,
)
from core.summarisation.postchecks.shared import Issue, _snippet


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
            # V0.4.11 (audit item #3): auto-repair proper-noun garbles even
            # when auto_repair=False. Proper nouns (capitalized in BOTH the
            # text and the source) are almost never edit-distance-1 from each
            # other by accident — "Tyrson"→"Tyson", "Gedimen"→"Gediman" are
            # clear garbles, not real-word false positives. The guard:
            #   (1) the garbled token is capitalized in the text (proper noun)
            #   (2) the matching source word is also capitalized in the source
            #   (3) exactly ONE non-inflection match (no ambiguity)
            #   (4) the paragraph-corroboration check passes
            # This is safe because common English words (the V0.03 false-
            # repair class) are lowercase, so this path can't fire on them.
            if not _repair_allowed and len(non_inflection_matches) == 1:
                _orig_tok_check = m.group(0)
                _repair_check = next(iter(non_inflection_matches))
                # Check if the original token is capitalized (proper noun).
                _is_capitalized = _orig_tok_check[:1].isupper()
                # Check if the source word appears capitalized in the source.
                _source_capitalized = bool(
                    re.search(r"\b" + re.escape(_repair_check.capitalize()) + r"\b", source_text)
                )
                if _is_capitalized and _source_capitalized:
                    _repair_allowed = True
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
