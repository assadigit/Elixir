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


# ═══════════════════════════════════════════════════════════════════════════
# F5: missing-hyphen normalization (selfinflation → self-inflation)
# ═══════════════════════════════════════════════════════════════════════════

from core.pipeline.chapter_checkpoint import _normalize_self_compounds


class TestV0438F5SelfCompoundHyphenNormalization:
    """F5: a render-boundary pass inserts missing hyphens in 'self' + word
    fusions.

    The V0.4.37 summary shipped 'selfinflation' (bullet line 76) and
    'selfrighteousness' (bullet line 63). The V0.4.38 fix: a
    lexicon-based pass that hyphenates 'self' + a trailing word ONLY
    when the fused word is NOT a real English word but the trailing
    part IS (so 'selfless'/'selfish' — real words — are left alone).
    Content-agnostic (Rule 1): the lexicon is a generic English
    wordlist; the 'self-' prefix is generic English morphology.
    """

    def test_selfinflation_selfrighteousness_hyphenated(self):
        """The V0.4.37 defects are fixed: selfinflation → self-inflation,
        selfrighteousness → self-righteousness."""
        t = "The profile shows selfinflation and selfrighteousness."
        out = _normalize_self_compounds(t, "bullet[0]")
        assert "self-inflation" in out
        assert "self-righteousness" in out
        assert "selfinflation" not in out
        assert "selfrighteousness" not in out

    def test_real_self_words_left_alone(self):
        """Real English self- words (selfless, selfish) and already-
        hyphenated forms (self-esteem) are NOT touched."""
        t = "He was selfless and selfish and had high self-esteem."
        out = _normalize_self_compounds(t, "exec")
        assert out == t, f"real self- words must be left alone; got: {out!r}"

    def test_noop_when_no_self(self):
        """Text without 'self' is unchanged (fast-path)."""
        t = "A plain sentence about the chapter."
        assert _normalize_self_compounds(t, "thorough") == t


# ═══════════════════════════════════════════════════════════════════════════
# V0.4.39 (Option A): LLM semantic repair for flagged garbles
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.postchecks.garble.garble_repair import repair_garbles_via_llm


class _MockSettings:
    """Minimal Settings stub returning a configured model + ollama arch."""

    def __init__(self, *, model="mock-model", arch="single_local"):
        self._model = model
        self._arch = arch

    def get(self, key, default=None):
        if key == "summarisation.model":
            return self._model
        if key == "summarisation.model_architecture":
            return self._arch
        return default


class _MockProvider:
    """A mock LLM provider that applies a caller-supplied repair function."""

    def __init__(self, repair_fn):
        self._repair_fn = repair_fn
        self.calls = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt, "temperature": temperature})
        # The prompt ends with the text to fix (after "TEXT TO FIX:\n").
        text = prompt.split("TEXT TO FIX:\n", 1)[1] if "TEXT TO FIX:\n" in prompt else prompt
        return self._repair_fn(text)


class TestV0439OptionAGarbleLLMRepair:
    """V0.4.39 (Option A): extend the D3 LLM-repair pattern to garbles.

    A general, content-agnostic LLM semantic repair for fragment_merge +
    dropped_letter garbles. Mirrors repair_d3_quotes_via_llm (V0.4.11/V0.4.13):
    fail-open; D3-style guard (keep the original if the repair doesn't reduce
    the garble flag count). Works on any chapter (Rule 1).
    """

    def test_garble_repaired_when_llm_fixes_the_token(self, monkeypatch):
        """When the LLM returns the fixed text (fewer garble flags), it's
        kept + a 'fix' issue is recorded."""
        source = "the confidence and pride of paranoids cloak but a hollow shell."
        text = "the confidence and pride of paranoias cloak a hollow shell."
        # mock provider that fixes 'paranoias' -> 'paranoids'
        provider = _MockProvider(lambda t: t.replace("paranoias", "paranoids"))
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = repair_garbles_via_llm(text, "bullet[0]", source, settings=_MockSettings())
        assert "paranoids" in out and "paranoias" not in out
        assert any(i.detector == "garble_llm_repair" and i.severity == "fix" for i in issues)

    def test_original_kept_when_llm_doesnt_reduce_flags(self, monkeypatch):
        """D3-style guard: if the LLM's output doesn't reduce the garble
        flag count, the original is kept + a 'flag' issue is recorded."""
        source = "the confidence and pride of paranoids cloak but a hollow shell."
        text = "the confidence and pride of paranoias cloak a hollow shell."
        # mock provider that returns the SAME garbled text (no fix)
        provider = _MockProvider(lambda t: t)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = repair_garbles_via_llm(text, "bullet[0]", source, settings=_MockSettings())
        assert out == text  # original kept
        assert any(i.detector == "garble_llm_repair" and i.severity == "flag" for i in issues)

    def test_no_op_when_no_garble_flags(self):
        """When the text has no garble flags, no LLM call is made (bounded)."""
        source = "a clean sentence about the topic."
        text = "a clean sentence about the topic."
        out, issues = repair_garbles_via_llm(text, "exec", source, settings=_MockSettings())
        assert out == text
        assert issues == []

    def test_fail_open_when_no_model_configured(self):
        """No model configured → no-op (fail-open, like the D3 repair)."""
        source = "the pride of paranoids cloak a shell."
        text = "the pride of paranoias cloak a shell."
        out, issues = repair_garbles_via_llm(
            text, "thorough", source, settings=_MockSettings(model="")
        )
        assert out == text  # original kept
        assert issues == []

    def test_fail_open_on_provider_exception(self, monkeypatch):
        """Provider creation raises → fail-open (original kept)."""
        source = "the pride of paranoids cloak a shell."
        text = "the pride of paranoias cloak a shell."

        def _raise(name, settings):
            raise RuntimeError("provider boom")

        monkeypatch.setattr("core.llm.llm_provider_impl.create_provider", _raise)
        out, issues = repair_garbles_via_llm(text, "thorough", source, settings=_MockSettings())
        assert out == text  # original kept
        assert any("failed" in i.detail for i in issues)


# ═══════════════════════════════════════════════════════════════════════════
# V0.4.39 (Option B): general detector edge-case characterization (non-ch.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestV0439OptionBGeneralDetectorEdgeCases:
    """V0.4.39 (Option B): general codebase hygiene — characterization tests
    for existing detectors on NON-ch.6 fixtures (generic English / biology /
    history). Confirms the detectors are book-agnostic (Rule 1)."""

    def test_fragment_merge_lexicon_check_on_generic_english(self):
        """The F3 lexicon check suppresses the 'word+trailing-char = a real
        English word' false-positive on any text (not just ch.6)."""
        # 'careful' + 'ly' = 'carefully' (real word, in lexicon) — must not flag
        src = "he was careful in his approach."
        text = "he was carefully in his approach."
        from core.summarisation.postchecks.garble.token_detectors import (
            detect_word_fragment_merge,
        )

        _, issues = detect_word_fragment_merge(text, "exec", src)
        flags = [i for i in issues if i.detector == "fragment_merge" and "carefully" in i.detail]
        assert flags == [], "'carefully' (real word) must not be flagged"

    def test_bold_name_structural_label_exemption_on_generic_text(self):
        """The F4 structural-label exemption works on any text — e.g. a
        biology chapter's '**Methods**:' / '**Results**:' labels."""
        from core.summarisation.postchecks.attribution import (
            verify_bold_name_attribution,
        )

        src = "The experiment measured photosynthesis rates under varying light."
        for label in ("Methods", "Results", "Discussion", "Abstract", "Background"):
            text = f"- **{label}**: the experiment used a controlled light source throughout."
            _, issues = verify_bold_name_attribution(text, src, "bullet[0]")
            flags = [i for i in issues if i.detector == "attribution"]
            assert flags == [], f"section label '{label}' must not be flagged"

    def test_self_compound_hyphen_normalization_on_generic_text(self):
        """The F5 self-compound hyphen normalization works on any text —
        e.g. a generic 'selfaware' → 'self-aware' (when 'aware' is in the
        lexicon but 'selfaware' is not)."""
        from core.pipeline.chapter_checkpoint import _normalize_self_compounds

        text = "the candidate was selfaware of the limitations."
        out = _normalize_self_compounds(text, "exec")
        assert "self-aware" in out
        assert "selfaware" not in out

    def test_fusion_pattern_c_no_false_positive_on_generic_clean_text(self):
        """The F1 fusion Pattern C does NOT false-positive on clean text
        using source words correctly (any chapter, not just ch.6). The
        Pattern C check is structural + targeted (a source-word prefix +
        a 5-6 char suffix that is itself a suffix of another source word)
        — clean text never matches."""
        from core.summarisation.postchecks.garble.fusion import detect_sentence_fusion

        src = "the water was apparently clean. the thesis was a defense."
        clean = "the water was apparently clean and the thesis was a defense."
        _, issues = detect_sentence_fusion(clean, "exec", src)
        assert [i for i in issues if i.detector == "sentence_fusion"] == []


# ═══════════════════════════════════════════════════════════════════════════
# V0.4.39 finalization: garble LLM-repair wired into ALL three fields
# (thorough + bullets + exec) — general coverage (any chapter, any field)
# ═══════════════════════════════════════════════════════════════════════════


class TestV0439FinalizationAllFieldsGarbleRepairWiring:
    """V0.4.39 finalization: the garble LLM-repair is wired into all three
    postcheck fields (thorough + bullets + exec), not just thorough. This
    confirms the wiring is present (source-pin) + that the repair is a
    bounded no-op when no model is configured (the common test path)."""

    def test_garble_repair_wired_into_all_three_fields(self):
        """Source-pin: the field_phases module references repair_garbles_via_llm
        in postcheck_bullets + postcheck_exec + postcheck_thorough (3 sites)."""
        from pathlib import Path

        src = Path("core/summarisation/postchecks/field_phases.py").read_text(encoding="utf-8")
        # The repair is invoked in 3 places (bullets loop, exec, thorough).
        assert src.count("repair_garbles_via_llm") >= 3, (
            "the garble LLM-repair must be wired into bullets + exec + thorough"
        )

    def test_garble_repair_is_noop_when_no_model_configured(self, monkeypatch):
        """When no model is configured, the repair is a no-op (the wiring's
        `_model` guard) — confirms the bounded-no-op behaviour on the
        common test path (no model in tests)."""
        source = "the pride of paranoids cloak a shell."
        text = "the pride of paranoias cloak a shell."
        out, issues = repair_garbles_via_llm(
            text, "bullet[0]", source, settings=_MockSettings(model="")
        )
        assert out == text  # original kept (no model → no-op)
        assert issues == []


# ═══════════════════════════════════════════════════════════════════════════
# V0.4.40: the post-conversion verification + polish LAYER
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.verification_phase import (
    verify_and_polish_summary,
)


class _MockVerifyProvider:
    """A mock LLM provider that returns a caller-supplied raw response."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt, "temperature": temperature})
        return self._raw


class TestV0440VerificationLayer:
    """V0.4.40: the post-conversion verification + polish LAYER.

    A post-output LLM layer (runs after render_summary_markdown) that fills
    holes + fixes mistakes (Dates/Names/Omissions/Hallucinations) to make
    a 7/10 output 9/10-10/10. The LLM is in a VERIFICATION role (not
    generation). Targeted corrections (verbatim string replacements, NOT a
    full rewrite) + D3-style guard (reject if more deterministic flags OR
    >15% length diff) + fail-open. Non-skippable (catches LLM-variance
    defects every conversion). Content-agnostic (Rule 1 — checks against
    the runtime source for any book).
    """

    def test_targeted_correction_applied(self, monkeypatch):
        """A date correction (original is an exact substring) is applied."""
        source = "Smith (1971) described the mechanism."
        summary = "Smith (1979) described the mechanism."
        raw = '[{"original": "Smith (1979)", "corrected": "Smith (1971)", "reason": "date"}]'
        provider = _MockVerifyProvider(raw)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        assert "Smith (1971)" in out and "Smith (1979)" not in out
        assert any(
            i.detector == "verification" and i.severity == "fix" and "date" in i.detail
            for i in issues
        )

    def test_correction_skipped_when_original_not_a_substring(self, monkeypatch):
        """If the LLM's 'original' isn't an exact substring, it's skipped +
        the original is kept (fail-safe — the LLM can't locate a fix)."""
        source = "Smith (1971) described the mechanism."
        summary = "Smith (1971) described the mechanism."
        # "original" is a paraphrase, not an exact substring
        raw = '[{"original": "Smith (1979) described", "corrected": "Smith (1971) described", "reason": "date"}]'
        provider = _MockVerifyProvider(raw)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        assert out == summary  # unchanged
        assert any(
            i.detector == "verification" and i.severity == "flag" and "none matched" in i.detail
            for i in issues
        )

    def test_guard_rejects_too_long_polish(self, monkeypatch):
        """If the polished output is >15% longer than the original, the guard
        rejects it + the original is kept (no major rewrite)."""
        source = "A short source."
        summary = "A short summary."
        # correction that doubles the length (>15%)
        raw = '[{"original": "A short summary.", "corrected": "A short summary that is now very much longer than the original for no good reason and should be rejected by the guard.", "reason": "omission"}]'
        provider = _MockVerifyProvider(raw)
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        assert out == summary  # rejected (too long)
        assert any(i.detector == "verification" and "outside 85-115%" in i.detail for i in issues)

    def test_no_op_when_no_corrections(self, monkeypatch):
        """Empty corrections array → no-op."""
        source = "Smith (1971) described the mechanism."
        summary = "Smith (1971) described the mechanism."
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        assert out == summary
        assert issues == []

    def test_no_op_when_no_model_configured(self):
        """No model configured → no-op (fail-open, like the D3 repair)."""
        source = "Smith (1971) described the mechanism."
        summary = "Smith (1979) described the mechanism."
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings(model=""))
        assert out == summary
        assert issues == []

    def test_fail_open_on_provider_exception(self, monkeypatch):
        """Provider creation raises → fail-open (original kept)."""
        source = "Smith (1971) described the mechanism."
        summary = "Smith (1979) described the mechanism."

        def _raise(name, settings):
            raise RuntimeError("provider boom")

        monkeypatch.setattr("core.llm.llm_provider_impl.create_provider", _raise)
        out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        assert out == summary
        assert any("failed" in i.detail for i in issues)

    def test_json_extraction_handles_fenced_block(self):
        """The _extract_corrections helper handles ```json fences."""
        from core.summarisation.verification_phase import _extract_corrections

        raw = '```json\n[{"original": "x", "corrected": "y", "reason": "name"}]\n```'
        out = _extract_corrections(raw)
        assert len(out) == 1
        assert out[0]["reason"] == "name"
        # empty array
        assert _extract_corrections("[]") == []
        # no JSON
        assert _extract_corrections("no json here") == []
