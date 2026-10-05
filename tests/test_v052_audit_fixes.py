"""V0.5.2 (FIX-P0-1) — regression tests for the re-implemented
Pattern C compound-word guard in ``detect_sentence_fusion``.

The original V0.5.2 "Fix 5 — Pattern C lexicon check" (commit 1cf0dcb)
was BROKEN (severity 1, found by AUDIT-V0.5.2):

  1. PLACED IN PATTERN A, not Pattern C. The 7-line block at
     ``core/summarisation/postchecks/garble/fusion.py:268-274`` lived
     inside Pattern A's ``for s in starts`` loop — Pattern C is the
     dropped-prefix detector at L344+.
  2. REDUNDANT (provably dead code). The added check
     ``if word in lexicon: continue`` is unreachable: the early
     lexicon check at L218 (``if lexicon and word in lexicon: continue``)
     already short-circuits any word that is in the lexicon, so by the
     time execution reaches L273 ``word in lexicon`` is GUARANTEED
     False. Empirically verified: running ``detect_sentence_fusion``
     on the documented FP with vs. without the L268-274 block yields
     IDENTICAL output (1 issue).
  3. WOULD NOT SUPPRESS THE FP ANYWAY. The documented FP word
     "underrepresentation" is NOT in the 126,761-word lexicon
     (``zgrep -c '^underrepresentation$' core/summarisation/postchecks/
     data/english_lexicon.txt.gz`` → 0). So even if correctly placed
     in Pattern C, the full-word lexicon check could never suppress it.
  4. CHANGELOG FALSE. The CHANGELOG.md V0.5.2 entry claims "Pattern C
     now checks if the full word is in the lexicon BEFORE flagging" —
     the check was actually in Pattern A, and the FP word is not in
     the lexicon.

The principled re-implementation (per AUDIT-V0.5.2 recommendation):
before Pattern C flags a candidate, verify the word isn't a legitimate
English compound. A real compound word is EITHER (i) itself in the
lexicon (already covered by the early lexicon check at L218, but
re-checked against the un-hyphenated ``clean`` form for hyphenated
compounds like "under-representation") OR (ii) composed of two lexicon
words (prefix + suffix both real English). If either holds, the
candidate is a legitimate English compound, not a dropped-prefix fusion
— skip Pattern C.

Content-agnostic (Rule 1): the guard uses lexicon membership ONLY;
no hardcoded words. The test below asserts BOTH the FP suppression
("underrepresentation" → 0 issues) AND the positive-case preservation
("persecutionensate" → still flagged). The "underrepresentation"
string appears in the test ONLY as the FP-under-test — never in the
production code.
"""

from __future__ import annotations

from core.summarisation.postchecks.garble.fusion import detect_sentence_fusion

# ═══════════════════════════════════════════════════════════════════════════
# FIX-P0-1 — Pattern C compound-word guard (re-implemented V0.5.2 Fix 5)
# ═══════════════════════════════════════════════════════════════════════════


class TestV052FixP01PatternCCompoundWordGuard:
    """FIX-P0-1: ``detect_sentence_fusion`` Pattern C now correctly
    suppresses the "underrepresentation" false-positive (and any other
    real English compound word composed of two lexicon words) WITHOUT
    suppressing real dropped-prefix fusions like "persecutionensate".

    The original V0.5.2 "Fix 5" lexicon check (commit 1cf0dcb) was
    broken (placed in Pattern A, redundant with the early lexicon
    check, and the FP word isn't in the lexicon). Re-implemented as
    a compound-word guard inside Pattern C's block.

    Content-agnostic (Rule 1): the guard uses lexicon membership only;
    no hardcoded words. The FP-under-test word appears in THIS test
    file only — never in the production code.
    """

    def test_underrepresentation_compound_not_flagged(self):
        """FP-suppression: 'underrepresentation' (= 'under' +
        'representation', both real English words in the lexicon) is
        NOT flagged as a dropped-prefix fusion.

        Pre-FIX-P0-1 this flagged as 1 issue (Pattern C: 'represent'
        + 5-char suffix 'ation' that is itself a suffix of 'presentation').
        Post-FIX-P0-1 the compound-word guard recognises 'under' +
        'representation' (both lexicon words) → 0 issues.
        """
        src = "The author present and represent the data. The presentation was clear."
        text = "This addresses the historical underrepresentation of cases."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert fusion == [], (
            "FIX-P0-1: 'underrepresentation' is a real English compound "
            "(under + representation, both lexicon words) and must NOT "
            f"be flagged; got: {[i.detail for i in fusion]}"
        )

    def test_persecutionensate_real_fusion_still_flagged(self):
        """Positive case: the genuine dropped-prefix fusion
        'persecutionensate' (= 'persecution' + 'ensate', where 'ensate'
        is a suffix of source word 'compensate' and 'ensate' is NOT a
        lexicon word) is STILL flagged.

        This is the regression guard: the compound-word guard must not
        over-suppress and break the original V0.4.38 F1 Pattern C
        detection that this whole subsystem was built to catch. The
        guard correctly rejects this candidate because no split of
        'persecutionensate' yields two lexicon words ('ensate' is not
        in the lexicon; the only lexicon-word prefix 'persecution'
        pairs with non-lexicon 'ensate').
        """
        src = "persecution is wrong. compensate for the losses incurred."
        text = "A persecutionensate problem here."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "FIX-P0-1: 'persecutionensate' is a genuine dropped-prefix "
            "fusion (persecution + ensate, where 'ensate' is NOT a "
            "lexicon word) and MUST still be flagged"
        )
        assert "persecutionensate" in fusion[0].detail
        assert "dropped-prefix fusion" in fusion[0].detail

    def test_hyphenated_compound_under_representation_not_flagged(self):
        """Hyphenated compound: 'under-representation' (hyphen-normalised
        to 'underrepresentation' for the substring analysis) is the same
        legitimate English compound — must NOT be flagged.

        Guards the ``clean in lexicon`` branch of the compound-word
        guard (the early lexicon check at L218 uses the un-normalised
        ``word`` with hyphens, which would miss 'under-representation'
        because the lexicon stores the un-hyphenated form). The
        re-implementation re-checks ``clean`` (hyphen-stripped) so
        hyphenated compounds are also covered.
        """
        src = "The author present and represent the data. The presentation was clear."
        text = "This addresses the historical under-representation of cases."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert fusion == [], (
            "FIX-P0-1: 'under-representation' (hyphen-normalised to "
            "'underrepresentation' = 'under' + 'representation', both "
            "lexicon words) must NOT be flagged"
            f"; got: {[i.detail for i in fusion]}"
        )

    def test_pattern_a_praiseity_still_flagged(self):
        """Regression guard: the original V0.4.3 Pattern A case
        ('praiseity' = 'praise' + 3-char suffix 'ity') is still
        flagged. The compound-word guard is INSIDE Pattern C only
        (does not affect Pattern A's per-s loop).
        """
        src = "praise. Waelder noted that the theory is governed by the prompt."
        text = "The model produced praiseity governed by the prompt."
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "Pattern A (3-4 char suffix fusion) must still work — the "
            "compound-word guard lives INSIDE Pattern C only"
        )

    def test_pattern_b_two_word_gap_still_flagged(self):
        """Regression guard: the V0.4.3 Pattern B case (two source
        words separated by a 3-8 char non-source gap) is still
        flagged. The compound-word guard is INSIDE Pattern C only.
        """
        src = "development. narcissistic masochistic character."
        text = "the self-developmentstic-masochistic character was noted."
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "Pattern B (2 source words + gap) must still work — the "
            "compound-word guard lives INSIDE Pattern C only"
        )


# ═══════════════════════════════════════════════════════════════════════════
# FIX-P1-4 — V0.5.2 Fix 6 (pronoun stopword) regression tests
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.postchecks.attribution import validate_years  # noqa: E402


class TestV052PronounStopword:
    """FIX-P1-4: V0.5.2 Fix 6 added pronouns ("his", "her", "their",
    "its", "he", "she", "they") to the ``_SUMMARY_CITATION_RE``
    author-name stopword set in ``core/summarisation/postchecks/attribution.py``.

    The FP: a sentence like "Volkan: His (1986) insights were formative."
    is matched by the citation regex ``([A-Z][a-z]+)\\s*\\((\\d{4})\\)``
    with ``author="His"`` and ``year="1986"``. Without the pronoun
    stopword, "His" (≥3 chars, not in the source's author list) would
    be flagged as an UNGROUNDED author — a false positive, because
    "His" is a possessive pronoun referring to Volkan, not a citation.

    The V0.5.2 fix adds the pronouns to the stopword set so the
    author-name grounding check skips them.

    Content-agnostic (Rule 1): the pronouns are general English words,
    not domain-specific. The test uses generic author names ("Volkan",
    "AuthorY") — no book/author content.
    """

    def test_his_pronoun_not_flagged_as_author(self):
        """The documented FP: "His (1986)" is NOT flagged as an
        ungrounded author. The pronoun "His" is in the stopword set.
        """
        text = "Volkan: His (1986) insights were formative."
        src = "Volkan wrote in 1986."
        _, issues = validate_years(text, "exec", source_authors=["Volkan"], source_text=src)
        # The author-grounding check emits issues with detector="year" and
        # detail prefix "author '...' ... not found in source's N citations".
        ungrounded = [
            i for i in issues if i.detector == "year" and "not found in source" in (i.detail or "")
        ]
        assert ungrounded == [], (
            "FIX-P1-4: 'His' is a possessive pronoun referring to Volkan, "
            "not a citation — must NOT be flagged as an ungrounded author; "
            f"got: {[i.detail for i in ungrounded]}"
        )

    def test_her_pronoun_not_flagged_as_author(self):
        """Same FP class for "Her": "Her (1975) framework..." must not
        be flagged.
        """
        text = "Kernberg: Her (1975) framework extended the earlier work."
        src = "Kernberg wrote in 1975."
        _, issues = validate_years(text, "exec", source_authors=["Kernberg"], source_text=src)
        ungrounded = [
            i for i in issues if i.detector == "year" and "not found in source" in (i.detail or "")
        ]
        assert ungrounded == [], (
            "FIX-P1-4: 'Her' is a possessive pronoun, not a citation — "
            f"must NOT be flagged; got: {[i.detail for i in ungrounded]}"
        )

    def test_real_ungrounded_author_still_flagged(self):
        """Positive case: a genuinely ungrounded author name is STILL
        flagged. "Dukhaim (1951)" with source author "AuthorY" — the
        names don't match, "Dukhaim" is not a pronoun, not a month, not
        in the source text → must be flagged.
        """
        text = "Dukhaim (1951) noted the pattern."
        src = "AuthorY wrote in 1951."
        _, issues = validate_years(text, "exec", source_authors=["AuthorY"], source_text=src)
        ungrounded = [
            i for i in issues if i.detector == "year" and "not found in source" in (i.detail or "")
        ]
        assert len(ungrounded) >= 1, (
            "FIX-P1-4: 'Dukhaim' is a genuinely ungrounded author name "
            "(not a pronoun, not in source) — MUST still be flagged; "
            "the pronoun stopword must not over-suppress"
        )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.4 (Track C2) — Pattern A/C adverb-as-adjective auto-rewrite
# ═══════════════════════════════════════════════════════════════════════════


class TestV054TrackC2PatternCRewrite:
    """V0.5.4 (Track C2): the sentence-fusion detector
    (``detect_sentence_fusion`` in ``core/summarisation/postchecks/garble/
    fusion.py``) is upgraded from **flag-only** to **flag+auto-rewrite**
    for clear grammatical garbles where the correction is unambiguous.

    The V0.5.3 ground-truth audit (commit ``cfec6a9``, file
    ``audit/results/AUDIT_V0.5.3_run20260926-211039-8b53ed76_ch6_summary_
    vs_source.md``) found that bullet 15 of the V0.5.3 summary shipped a
    grammatical garble — ``ego-syntonically personalities`` (the adverb
    ``ego-syntonically`` misused as an adjective; should be
    ``ego-syntonic personalities``). The sentence-fusion detector
    correctly flagged the word (Pattern A specifically, since ``ally``
    is a 4-char suffix; the V0.5.3 release notes' "Pattern C" wording
    was loose shorthand for the whole sentence-fusion subsystem), but
    the summary shipped it uncorrected because the detector was
    flag-only.

    Track C2 fixes this with a rule-based + deterministic (NOT LLM)
    rewrite for the adverb-as-adjective pattern. The rule fires only
    when ALL hold:

      1. The flagged word ends in ``-ically`` (the adverb suffix formed
         from an adjective ending in ``-ic`` + ``ally``; e.g.,
         ``ego-syntonic`` + ``ally`` → ``ego-syntonically``). The
         candidate rewrite is ``word[:-len("ically")] + "ic"`` (e.g.,
         ``ego-syntonically`` → ``ego-syntonic``).
      2. The candidate adjective is recognised as a real English word:
         EITHER directly in the lexicon, OR (for domain-specific
         hyphenated adjectives like ``ego-syntonic``) a hyphenated
         compound whose LAST hyphen-component is in the lexicon (covers
         the case where the lexicon has the stem ``syntonic`` but not
         the hyphenated compound form ``ego-syntonic`` — the head of an
         English hyphenated compound is its last component, so this is
         morphologically principled).
      3. The next word after the flagged word is a noun: in the lexicon
         AND does NOT end in a common English past-tense / participle
         ending (``ed``/``ing``/``en``). This distinguishes the garble
         ``ego-syntonically personalities`` (rewrite — ``personalities``
         is a noun) from the source's CORRECT usage
         ``ego-syntonically embedded`` (no rewrite — ``embedded`` is a
         verb past participle, the source's line 257).

    If all checks pass → the returned ``text`` has the rewrite applied
    (preserving all other character offsets) AND the flagged issue's
    ``detail`` notes the rewrite. If ANY check fails → fall back to
    flag-only (the V0.5.3 behavior). The rewrite is OPTIONAL + fail-open
    (an empty lexicon ⇒ no rewrite).

    Conservative scope (per the task spec): the rewrite is ONLY for the
    ``-ically → -ic`` adverb→adjective pattern. It does NOT apply to
    other garble types (dropped-prefix fusions like ``persecutionensate``
    — those need LLM repair, not a deterministic rewrite).

    Content-agnostic (Rule 1): the rule uses English morphology + lexicon
    membership ONLY; no hardcoded words. The example ``ego-syntonically``
    appears in TESTS only, never in the production code.
    """

    def test_ego_syntonically_rewrite_applied(self):
        """e2e: ``ego-syntonically personalities`` is rewritten to
        ``ego-syntonic personalities`` + the flagged issue's ``detail``
        notes the rewrite.

        The source has ``egosyntonic`` (the unhyphenated adjective form)
        + ``syntonically`` (so ``ally`` is in the source-word suffix
        set), which causes Pattern A to flag ``ego-syntonically`` (the
        adverb form, not in lexicon) as a ``egosyntonic`` + ``ally``
        fusion. The rewrite rule then fires:

        - word ends in ``-ically`` ✓
        - candidate ``ego-syntonic`` → last hyphen-component
          ``syntonic`` IS in the lexicon ✓
        - next word ``personalities`` IS in the lexicon AND does NOT
          end in a verb past-tense ending ✓

        → rewrite to ``ego-syntonic``.
        """
        src = "The patient showed egosyntonic traits. The behaviour was syntonically appropriate."
        text = "ego-syntonically personalities are noted."
        out, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "Track C2: Pattern A must flag 'ego-syntonically' as a "
            "sentence-fusion garble (the adverb form is not in lexicon)"
        )
        # The text was rewritten:
        assert "ego-syntonic personalities" in out, (
            "Track C2: 'ego-syntonically personalities' must be rewritten "
            f"to 'ego-syntonic personalities'; got: {out!r}"
        )
        assert "ego-syntonically personalities" not in out, (
            "Track C2: the original garble 'ego-syntonically "
            f"personalities' must NOT appear in the rewritten text; got: {out!r}"
        )
        # The issue detail must note the rewrite:
        assert any("Auto-rewrite" in i.detail and "ego-syntonic" in i.detail for i in fusion), (
            "Track C2: the issue detail must note the auto-rewrite "
            "(Auto-rewrite applied: 'ego-syntonically' → 'ego-syntonic'); "
            f"got: {[i.detail for i in fusion]}"
        )

    def test_real_fusion_not_rewritten(self):
        """e2e: ``persecutionensate`` (a real dropped-prefix fusion)
        is STILL flagged, NOT rewritten. The ``-ically`` rule doesn't
        apply (the word doesn't end in ``-ically``). This guards the
        conservative scope: the rewrite is ONLY for the adverb-as-
        adjective pattern, NOT for other garble types (dropped-prefix
        fusions need LLM repair, not a deterministic rewrite, because
        the correct reconstruction is ambiguous).
        """
        src = "persecution is wrong. compensate for the losses incurred."
        text = "A persecutionensate problem here."
        out, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "Track C2: 'persecutionensate' is a genuine dropped-prefix "
            "fusion (persecution + ensate, where 'ensate' is NOT a "
            "lexicon word) and MUST still be flagged"
        )
        # The text was NOT rewritten (the -ically rule doesn't apply):
        assert "persecutionensate" in out, (
            "Track C2: 'persecutionensate' must NOT be rewritten (the "
            "-ically rule doesn't apply — only adverb-as-adjective "
            f"rewrites); got: {out!r}"
        )
        # The issue detail must NOT mention an auto-rewrite:
        assert all("Auto-rewrite" not in i.detail for i in fusion), (
            "Track C2: the 'persecutionensate' issue must NOT include an "
            "auto-rewrite note (the rule didn't fire — the word doesn't "
            f"end in -ically); got: {[i.detail for i in fusion]}"
        )

    def test_adverb_before_verb_not_rewritten(self):
        """e2e: ``ego-syntonically embedded`` (the source's CORRECT
        adverb-modifying-verb usage on line 257 of the V0.5.3 source
        chapter) is NOT rewritten — the next word ``embedded`` ends in
        ``ed`` (verb past participle), so the rewrite rule returns None.

        Setup: the source has ``egosyntonic`` + ``syntonically`` so
        Pattern A fires on ``ego-syntonically`` (the adverb form is not
        in lexicon, fails the early-exit). The rewrite rule then runs
        but the next word ``embedded`` triggers the verb-ending
        exclusion → return None → flag-only (the V0.5.3 behavior).
        """
        src = "The egosyntonic traits were noted. The patient was syntonically appropriate."
        text = "The patient was ego-syntonically embedded here."
        out, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        # Pattern A should flag the word (since 'ally' is 4 chars and the
        # full word 'ego-syntonically' is not in lexicon/source):
        assert len(fusion) >= 1, (
            "Track C2 (e2e): Pattern A should flag 'ego-syntonically' as "
            "a sentence-fusion garble (the word is not in lexicon/source)"
        )
        # The text was NOT rewritten (the next word 'embedded' is a verb):
        assert "ego-syntonically embedded" in out, (
            "Track C2 (e2e): 'ego-syntonically embedded' (correct adverb-"
            "modifying-verb usage) must NOT be rewritten; got: "
            f"{out!r}"
        )
        # The issue detail must NOT mention an auto-rewrite:
        assert all("Auto-rewrite" not in i.detail for i in fusion), (
            "Track C2 (e2e): 'ego-syntonically embedded' issue must NOT "
            "include an auto-rewrite note (the rule didn't fire — next "
            "word 'embedded' is a verb past participle); got: "
            f"{[i.detail for i in fusion]}"
        )

    # ── Direct unit tests of the rewrite rule (no Pattern A/B/C needed) ──

    def test_rewrite_rule_ego_syntonically_personalities(self):
        """Direct unit test: ``_rewrite_grammatical_garble(
        'ego-syntonically', 'personalities', lexicon)`` returns
        ``'ego-syntonic'`` — the candidate is recognised as a real
        English adjective via the hyphenated-compound fallback (last
        hyphen-component ``syntonic`` IS in the lexicon).
        """
        from core.summarisation.postchecks.garble.fusion import _rewrite_grammatical_garble
        from core.summarisation.postchecks.garble.lexicon import _load_english_lexicon

        lex = _load_english_lexicon()
        out = _rewrite_grammatical_garble("ego-syntonically", "personalities", lex)
        assert out == "ego-syntonic", (
            "Track C2: rewrite rule must return 'ego-syntonic' for "
            f"'ego-syntonically' before noun 'personalities'; got: {out!r}"
        )

    def test_rewrite_rule_adverb_before_verb_returns_none(self):
        """Direct unit test: ``_rewrite_grammatical_garble(
        'ego-syntonically', 'embedded', lexicon)`` returns ``None`` —
        ``embedded`` ends in ``ed`` (verb past participle), so the
        rewrite is suppressed (the adverb is correctly modifying the
        verb — the source's line 257 usage).
        """
        from core.summarisation.postchecks.garble.fusion import _rewrite_grammatical_garble
        from core.summarisation.postchecks.garble.lexicon import _load_english_lexicon

        lex = _load_english_lexicon()
        out = _rewrite_grammatical_garble("ego-syntonically", "embedded", lex)
        assert out is None, (
            "Track C2: rewrite rule must return None for "
            "'ego-syntonically' before verb 'embedded' (correct usage — "
            f"adverb-modifying-verb); got: {out!r}"
        )

    def test_rewrite_rule_persecutionensate_returns_none(self):
        """Direct unit test: ``_rewrite_grammatical_garble(
        'persecutionensate', 'problem', lexicon)`` returns ``None`` —
        the word doesn't end in ``-ically``, so the rule doesn't apply
        (the dropped-prefix fusion needs LLM repair, not a deterministic
        rewrite).
        """
        from core.summarisation.postchecks.garble.fusion import _rewrite_grammatical_garble
        from core.summarisation.postchecks.garble.lexicon import _load_english_lexicon

        lex = _load_english_lexicon()
        out = _rewrite_grammatical_garble("persecutionensate", "problem", lex)
        assert out is None, (
            "Track C2: rewrite rule must return None for "
            "'persecutionensate' (doesn't end in -ically — only "
            f"adverb→adjective rewrites apply); got: {out!r}"
        )

    def test_rewrite_rule_failopen_on_empty_lexicon(self):
        """Direct unit test: an empty lexicon ⇒ no rewrite (fail-open).
        Guards the optional/fail-open contract: a missing or load-
        failure lexicon degrades gracefully to flag-only (the V0.5.3
        behavior). No exception is raised.
        """
        from core.summarisation.postchecks.garble.fusion import _rewrite_grammatical_garble

        out = _rewrite_grammatical_garble("ego-syntonically", "personalities", set())
        assert out is None, (
            "Track C2: an empty lexicon must short-circuit to None "
            f"(fail-open — no rewrite attempted); got: {out!r}"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
