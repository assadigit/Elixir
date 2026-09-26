"""V0.4.38 — the F1-F5 backlog release (fusion-garble detection +
thorough short-output floor + fragment-merge lexicon + bold-name
structural-label exemption + self- hyphen normalization).

Characterization tests for the V0.4.38 fixes. All 5 items were
flagged in the V0.4.37 ch.6 audit (audit/results/
AUDIT_V0.4.37_run20260926-041731-130842a6_ch6_summary_vs_source.md,
"V0.4.38 backlog" section). This file covers the items that are fully
validatable in-sandbox (no live-LLM rig required):

  F1 — fusion-garble detection (HIGH): the V0.4.37 thorough shipped a
    "persecution"+"compensate" mid-overlap fusion ("persecutionensate")
    that detect_sentence_fusion missed. The V0.4.38 fix adds Pattern C
    (a source-word prefix + a 5-6 char suffix that is itself a suffix
    of another source word — the dropped-prefix fusion signature).
  F3 — "theme" fragment_merge false-positive (LOW): "theme" is a real
    English word but the garble lexicon lacked it; the V0.4.38 fix
    adds it.
  F4 — "Conclusions" bold-name false-positive (LOW): the bold-name
    detector flagged structural section labels (**Conclusions**:);
    the V0.4.38 fix exempts the known enumeration-guarantee labels.
  F5 — missing-hyphen normalization (LOW): "selfinflation" /
    "selfrighteousness" shipped without hyphens; the V0.4.38 fix adds
    a deterministic self- compound hyphen-normalization pass.

All fixes are content-agnostic (Rule 1).
"""

from __future__ import annotations

from core.summarisation.postchecks.garble.fusion import detect_sentence_fusion

# ═══════════════════════════════════════════════════════════════════════════
# F1: Pattern C — the dropped-prefix fusion (persecutionensate)
# ═══════════════════════════════════════════════════════════════════════════


class TestV0438F1DroppedPrefixFusion:
    """F1: detect_sentence_fusion now catches the dropped-prefix fusion
    pattern (the V0.4.37 "persecutionensate" defect).

    The V0.4.37 thorough shipped "persecutionensate" = source-word
    "persecution" + "ensate" (a 6-char suffix of the source word
    "compensate", whose "comp" prefix was dropped in the fusion).
    Pattern A caps suffixes at 4 chars (so 6 escapes); Pattern B needs
    2 source-word substrings but "compensate" isn't a substring (its
    prefix was dropped). Pattern C closes the gap: a source-word
    prefix + a 5-6 char suffix that is itself a suffix of some OTHER
    source word. Content-agnostic (Rule 1): the suffix-to-source-word-
    suffix match is structural, no hardcoded words.
    """

    def test_persecutionensate_fusion_detected(self):
        """The V0.4.37 headline defect is now flagged."""
        src = (
            "Bleuler described the triad of suspiciousness, grandiosity, "
            "and feelings of persecution. Selfinsecurity leads to attempts "
            "to compensate for humiliation. Compulsive formality is a mask."
        )
        text = (
            "Bleuler and Kretschmer both identified a triad of suspiciousness, "
            "grandiosity, and persecutionensate for humiliation with formalism."
        )
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "F1: 'persecutionensate' (persecution + ensate, a suffix of "
            "compensate) must be flagged as a dropped-prefix fusion"
        )
        assert "persecutionensate" in fusion[0].detail
        assert "dropped-prefix fusion" in fusion[0].detail

    def test_pattern_c_no_false_positive_on_clean_text(self):
        """Clean text using 'persecution' and 'compensate' correctly →
        no fusion flag (the Pattern C check is structural + targeted)."""
        src = (
            "Bleuler described the triad of suspiciousness, grandiosity, "
            "and feelings of persecution. Selfinsecurity leads to attempts "
            "to compensate for humiliation."
        )
        clean = (
            "Bleuler described the triad of suspiciousness, grandiosity, "
            "and feelings of persecution. Patients compensate for humiliation."
        )
        _, issues = detect_sentence_fusion(clean, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert fusion == [], (
            "F1: clean text using 'persecution' + 'compensate' correctly "
            f"must not flag a fusion; got: {[i.detail for i in fusion]}"
        )

    def test_pattern_a_still_catches_short_suffix_fusion(self):
        """Regression guard: the original V0.4.3 Pattern A case
        ('praiseity' = 'praise' + 3-char suffix 'ity') is still flagged."""
        src = "praise. Waelder noted that the theory is governed by the prompt."
        text = "The model produced praiseity governed by the prompt."
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, "Pattern A (3-4 char suffix) must still work"

    def test_pattern_b_still_catches_two_word_gap_fusion(self):
        """Regression guard: the V0.4.3 Pattern B case (two source words
        separated by a 3-8 char non-source gap) is still flagged."""
        src = "development. narcissistic masochistic character."
        text = "the self-developmentstic-masochistic character was noted."
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, "Pattern B (2 source words + gap) must still work"


# ═══════════════════════════════════════════════════════════════════════════
# F3: "theme" fragment_merge false-positive (lexicon gap)
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.postchecks.garble.token_detectors import (
    detect_word_fragment_merge,
)


class TestV0438F3FragmentMergeLexiconCheck:
    """F3: detect_word_fragment_merge now consults the English lexicon so a
    source word + a trailing char that forms a DIFFERENT real English word
    (not in THIS source) is not flagged.

    The V0.4.37 thorough/bullet-4 flagged 'theme' = source-word 'them' +
    'e' (the source has 'them' but not 'theme'). 'theme' IS a real English
    word (in the vendored 126k-word lexicon). The V0.4.38 fix adds the
    lexicon check (mirrors detect_sentence_fusion). Content-agnostic
    (Rule 1): the lexicon is a generic English wordlist.
    """

    def test_theme_not_flagged(self):
        """'theme' (a real English word, in the lexicon but not in the
        source) is NOT flagged — the V0.4.37 false-positive."""
        src = "A recurring them in the literature. The chapter highlights them."
        text = "A recurring theme in the literature."
        _, issues = detect_word_fragment_merge(text, "bullet[4]", src)
        flags = [i for i in issues if i.detector == "fragment_merge"]
        assert flags == [], (
            "F3: 'theme' is a real English word (in the lexicon) and must not "
            f"be flagged; got: {[i.detail for i in flags]}"
        )

    def test_real_fragment_merge_still_flagged(self):
        """Regression guard: a genuine fragment-merge ('adolescenceo' =
        'adolescence' + 'o', where 'adolescenceo' is NOT a real word) is
        still flagged."""
        src = "adolescence. To fill the gap."
        text = "adolescenceo fill the gap."
        _, issues = detect_word_fragment_merge(text, "bullet[0]", src)
        flags = [i for i in issues if i.detector == "fragment_merge"]
        assert len(flags) >= 1, "a genuine fragment-merge must still be flagged"
        assert "adolescenceo" in flags[0].detail


# ═══════════════════════════════════════════════════════════════════════════
# F4: "Conclusions" bold-name false-positive (structural-label exemption)
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.postchecks.attribution import verify_bold_name_attribution


class TestV0438F4BoldNameStructuralLabelExemption:
    """F4: verify_bold_name_attribution no longer flags common English
    discourse/publishing section labels (e.g. '**Conclusions**:') as
    unknown authors.

    The V0.4.37 bullet[59] flagged '**Conclusions**: (1) includes...'
    (conv-log line 743) as "bold-name author 'Conclusions' not found in
    source" — it's a structural section label, not an author attribution.
    The V0.4.38 fix adds a genre-agnostic allowlist
    (_BOLD_NAME_STRUCTURAL_LABELS) of common English section labels.
    Rule 1: the list is generic English publishing/discourse labels,
    not book-specific.
    """

    def test_conclusions_label_not_flagged(self):
        """'**Conclusions**:' is a structural label, not an author — not
        flagged (the V0.4.37 false-positive)."""
        src = "Cameron (1963) outlined four aspects of paranoid personality."
        text = "- **Conclusions**: (1) includes both phenomenological observations thoroughly."
        _, issues = verify_bold_name_attribution(text, src, "bullet[59]")
        flags = [i for i in issues if i.detector == "attribution"]
        assert flags == [], (
            "F4: '**Conclusions**:' is a structural label, not an author; "
            f"got: {[i.detail for i in flags]}"
        )

    def test_summary_overview_introduction_labels_not_flagged(self):
        """Other common section labels (Summary, Overview, Introduction)
        are also exempt."""
        src = "Some source text about a topic."
        for label in ("Summary", "Overview", "Introduction", "Discussion", "References"):
            text = f"- **{label}**: this section recaps the key points made earlier."
            _, issues = verify_bold_name_attribution(text, src, "bullet[0]")
            flags = [i for i in issues if i.detector == "attribution"]
            assert flags == [], f"section label '{label}' must not be flagged"

    def test_real_bold_name_author_still_flagged(self):
        """Regression guard: a real '**AuthorName**:' bold whose author is
        NOT in the source is still flagged."""
        src = "Cameron (1963) outlined four aspects of paranoid personality."
        text = "- **Voss**: described the layered model of structure formation here."
        _, issues = verify_bold_name_attribution(text, src, "bullet[1]")
        flags = [i for i in issues if i.detector == "attribution"]
        assert len(flags) >= 1, "a real bold-name author not in source must still flag"
        assert "Voss" in flags[0].detail
