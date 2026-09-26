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


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
