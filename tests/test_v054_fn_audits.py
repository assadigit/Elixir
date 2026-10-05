r"""V0.5.4 (Track E + B5) — FN-side audit remediation tests.

This file audits + fixes the FALSE-NEGATIVE side of the verification
LAYER (the V0.5.3 audit found the LAYER's signal is 80% false-positive
— those 3 FP classes are handled by Track A; this track addresses the
genuine FN risks the LAYER should flag but doesn't).

  E2 — Date-format coverage audit + letter-suffix year pattern
       (``\d{4}[a-z]`` academic-citation convention).
  E3 — Pattern C pattern-coverage audit + Pattern D (source-propagated
       self-X fusion garble) for "selfinflation" / "selfrighteousness"
       type source-garbles transmitted verbatim.
  E4 — LLM verification prompt devil's-advocate instruction (reduce the
       rubber-stamp tendency where the LLM returns [] without scrutiny).
  B5 — Affected-populations prompt instruction (generic, content-
       agnostic — instructs the LLM to include source-listed
       populations for any condition; no hardcoded "immigrants /
       refugees" — that would violate Rule 1).

All fixes are content-agnostic (Rule 1 ✓): the date regex uses generic
``\d{4}[a-z]``; Pattern D uses "self" (a generic English morpheme —
precedent: ``_FUSION_LEGIT_SUFFIXES`` in fusion.py already uses "self");
the devil's-advocate prompt is generic ("find the weakest claim"); the
B5 prompt instruction is generic ("include the source's specific
populations"). No hardcoded book/author/chapter content.

The V0.5.3 chapter 6 summary + source are referenced BY FILE PATH
(not embedded inline) — the audit-grounded real garbles appear in
this test file ONLY as the test-under-test, never in production code.
"""

from __future__ import annotations

from pathlib import Path

from core.preprocessing.date_extractor import extract_dates
from core.summarisation.postchecks.garble.fusion import detect_sentence_fusion

# ═══════════════════════════════════════════════════════════════════════════
# E2 — Letter-suffix academic-citation year pattern
# ═══════════════════════════════════════════════════════════════════════════


class TestE2LetterSuffixYearPattern:
    """E2: extract_dates now captures the letter-suffix academic-citation
    format (e.g. "1921a", "1908b", "1978b" — used to disambiguate multiple
    publications by the same author in the same year).

    Pre-V0.5.4 the bare-year ``_PLAIN_YEAR`` pattern matched only "1921"
    from "1921a", silently dropping the disambiguating letter — a FN for
    the letter-suffix format (distinct papers became indistinguishable
    in the audit log). The V0.5.4 fix adds a ``_LETTER_SUFFIX_YEAR``
    pattern BEFORE ``_PLAIN_YEAR`` in the ``_PATTERNS`` registry; the
    full text (with letter) is preserved in ``DateMatch.text`` while
    the normalized form is the bare year (ce:1921) so summary-vs-source
    matching still treats a bare "1921" as a match for a suffixed
    "1921a"/"1921b" (avoids introducing false-positive hallucination
    flags when the summary is less precise than the source).
    """

    def test_letter_suffix_year_captured(self):
        """The documented scenario from the task: "Kraepelin (1921a)
        renamed..." → extract_dates captures "1921a" (full text, with
        the disambiguating letter)."""
        dms = extract_dates("Kraepelin (1921a) renamed the condition.")
        # At least one DateMatch captures the FULL "1921a" text
        full_text_matches = [m for m in dms if m.text == "1921a"]
        assert full_text_matches, (
            "E2: extract_dates must capture the FULL '1921a' text (with "
            f"the disambiguating letter); got: {[(m.text, m.format_type) for m in dms]}"
        )
        dm = full_text_matches[0]
        assert dm.format_type == "letter_suffix", (
            f"format_type must be 'letter_suffix'; got: {dm.format_type}"
        )
        assert dm.year == 1921
        assert dm.normalized == "ce:1921", (
            "normalised form must be the bare year (ce:1921) so summary-vs-"
            f"source matching still works; got: {dm.normalized}"
        )

    def test_letter_suffix_year_distinct_from_plain_year(self):
        """A bare "1921" is captured by the plain_year pattern; a
        suffixed "1921a" is captured by the letter_suffix pattern —
        distinct format_types so the audit log can distinguish them."""
        dms = extract_dates("Smith (1921) wrote paper 1. Smith (1921a) wrote paper 2.")
        plain = [m for m in dms if m.format_type == "plain_year" and m.text == "1921"]
        suffixed = [m for m in dms if m.format_type == "letter_suffix" and m.text == "1921a"]
        assert plain and suffixed, (
            "plain_year (1921) and letter_suffix (1921a) must both be "
            f"captured distinctly; got: {[(m.text, m.format_type) for m in dms]}"
        )

    def test_letter_suffix_no_false_positive_on_word_chars(self):
        r"""The ``(?<!\w)`` lookbehind prevents matching "1921a" inside
        a longer alphanumeric token (e.g. serial numbers like
        "author1921a"). Only standalone academic-citation years are
        captured."""
        dms = extract_dates("The reference author1921a was malformed.")
        suffixed = [m for m in dms if m.format_type == "letter_suffix"]
        assert suffixed == [], (
            "E2: letter_suffix must NOT match '1921a' inside 'author1921a' "
            f"(word-char lookbehind); got: {[m.text for m in suffixed]}"
        )

    def test_letter_suffix_year_bare_summary_matches_suffixed_source(self):
        """A summary that cites just "1921" (no letter) must still
        match a source that cites "1921a"/"1921b" — the bare-year
        normalisation avoids introducing false-positive hallucination
        flags when the summary is less precise than the source."""
        from core.preprocessing.date_extractor import compare_dates

        summary = extract_dates("Kraepelin (1921) wrote the foundational paper.")
        source = extract_dates("Kraepelin (1921a) wrote paper 1. Kraepelin (1921b) wrote paper 2.")
        result = compare_dates(summary, source)
        assert result["hallucinated_count"] == 0, (
            "E2: a bare '1921' summary must match suffixed '1921a'/'1921b' "
            "source (no false-positive hallucination flag); got "
            f"hallucinated_count={result['hallucinated_count']}"
        )


class TestE2SourceChapterCoverage:
    """E2: extract_dates on the full source chapter captures ≥90% of the
    human-identified dates (ground truth from the V0.5.3 audit)."""

    # Path to the source chapter on origin/main (committed to docs/ground_truth/
    # for offline audit — the AUDIT-V0.5.3-ground-truth entry uses this same file).
    SOURCE_PATH = Path("docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md")

    # The V0.5.3 ground-truth audit identified these distinct years in the
    # source chapter (the per-author citation years across all 5 ALL-CAPS
    # sections). These are the audit's hand-verified ground truth (Rule 1
    # exception: the test references the audit ground-truth, not production
    # code). 46 distinct years; the decade references (1940s, 1980s) are
    # captured separately by the decade pattern.
    HUMAN_IDENTIFIED_YEARS = {
        1887,
        1893,
        1902,
        1905,
        1908,
        1911,
        1919,
        1921,
        1922,
        1923,
        1927,
        1945,
        1946,
        1949,
        1950,
        1952,
        1955,
        1958,
        1959,
        1960,
        1961,
        1963,
        1965,
        1966,
        1968,
        1969,
        1970,
        1971,
        1972,
        1973,
        1974,
        1975,
        1976,
        1977,
        1978,
        1979,
        1980,
        1981,
        1982,
        1983,
        1984,
        1985,
        1986,
        1987,
        1988,
        1990,
    }

    def test_all_source_dates_extracted(self):
        """extract_dates on the full source chapter captures ≥90% of the
        human-identified dates (the V0.5.3 audit's ground truth)."""
        if not self.SOURCE_PATH.exists():
            import pytest

            pytest.skip(
                f"source chapter not available: {self.SOURCE_PATH} "
                "(this test runs only with the full elixir repo checkout)"
            )
        text = self.SOURCE_PATH.read_text(encoding="utf-8")
        matches = extract_dates(text)
        # Aggregate all years (plain_year + letter_suffix + range components
        # + decade prefixes + year_end from ranges).
        extracted_years: set[int] = set()
        for m in matches:
            if m.year is not None:
                extracted_years.add(m.year)
            if m.year_end is not None:
                extracted_years.add(m.year_end)
        missing = self.HUMAN_IDENTIFIED_YEARS - extracted_years
        coverage = len(self.HUMAN_IDENTIFIED_YEARS & extracted_years) / len(
            self.HUMAN_IDENTIFIED_YEARS
        )
        assert coverage >= 0.90, (
            f"E2: extract_dates must capture ≥90% of human-identified dates; "
            f"got {coverage:.1%} ({len(self.HUMAN_IDENTIFIED_YEARS & extracted_years)}/"
            f"{len(self.HUMAN_IDENTIFIED_YEARS)}); missing: {sorted(missing)}"
        )

    def test_letter_suffix_years_in_source_all_captured(self):
        """The source chapter's letter-suffix citation years (1921a,
        1921b, 1908b, 1923a, 1950a, 1973a, 1975a, 1978b, 1982a) are all
        captured by the letter_suffix pattern (pre-V0.5.4 these were
        silently normalised to plain_year, dropping the disambiguating
        letter)."""
        if not self.SOURCE_PATH.exists():
            import pytest

            pytest.skip(
                f"source chapter not available: {self.SOURCE_PATH} "
                "(this test runs only with the full elixir repo checkout)"
            )
        text = self.SOURCE_PATH.read_text(encoding="utf-8")
        matches = extract_dates(text)
        captured = {m.text for m in matches if m.format_type == "letter_suffix"}
        # The expected letter-suffixed academic-citation years per the
        # V0.5.3 audit's source-text scan.
        expected = {"1921a", "1921b", "1908b", "1923a", "1950a", "1973a", "1975a", "1978b", "1982a"}
        missing = expected - captured
        assert not missing, (
            f"E2: letter-suffix pattern must capture all source chapter's "
            f"letter-suffixed citation years; missing: {sorted(missing)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# E3 — Pattern D: source-propagated self-X fusion garble
# ═══════════════════════════════════════════════════════════════════════════


class TestE3PatternDSourcePropagatedSelfXFusion:
    """E3: Pattern C (the existing fusion detector) correctly skipped
    source-words (its design is LLM-introduced fusions only), so when
    the SOURCE itself has a missing-hyphen "self-X" compound (e.g.
    "selfinflation" instead of "self-inflation") and the summary
    transmits it verbatim, no detector flagged the defect.

    Pattern D (V0.5.4) closes this gap: a source-word that starts with
    "self" + a 5+ char lexicon word, not in the lexicon itself → flag
    as a "source-propagated fusion garble" so the audit log shows the
    defect (the V0.4.38 F5 render-sweep normalises the OUTPUT text;
    Pattern D flags the underlying defect in the audit trail).
    """

    def test_pattern_c_catches_self_inflation(self):
        """The documented V0.5.3 garble: "selfinflation" is in the source
        (source line 129 has the garble verbatim) and transmitted to the
        summary. Pattern C correctly does NOT flag (its design skips
        source-words); Pattern D (V0.5.4) DOES flag the source-propagated
        garble.

        This test asserts the broader fusion detector family (which now
        includes Pattern D) catches the V0.5.3 summary's "selfinflation"
        garble — the audit-FN the V0.5.3 conv-log missed.
        """
        src = (
            "The author noted selfinflation through grandiose fantasies in the dynamics. "
            "The summary transmits the selfinflation as in the source."
        )
        text = "The summary transmits the selfinflation as in the source."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        self_inflation_issues = [i for i in fusion if "selfinflation" in (i.detail or "")]
        assert len(self_inflation_issues) >= 1, (
            "E3 Pattern D: 'selfinflation' IS in source_words (source itself "
            "has the missing-hyphen garble); Pattern A/B/C correctly skip "
            "(their design is LLM-introduced fusions only); Pattern D MUST "
            "flag the source-propagated garble so the audit log shows the "
            f"defect; got: {[i.detail for i in fusion]}"
        )
        assert "source-propagated" in self_inflation_issues[0].detail, (
            "Pattern D must use the 'source-propagated' marker so the audit "
            "log can distinguish it from LLM-introduced fusions"
        )

    def test_pattern_d_catches_self_righteousness(self):
        """The second documented V0.5.3 garble: "selfrighteousness"
        (source line 132 has the garble verbatim; summary line 59
        transmits it). Pattern D catches it."""
        src = "the expedient mendacity with moralistic selfrighteousness in the paranoid character."
        text = "the mendacity with moralistic selfrighteousness in the character."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        self_right_issues = [i for i in fusion if "selfrighteousness" in (i.detail or "")]
        assert len(self_right_issues) >= 1, (
            "E3 Pattern D: 'selfrighteousness' IS in source_words; Pattern D "
            f"must flag the source-propagated garble; got: {[i.detail for i in fusion]}"
        )

    def test_pattern_d_no_false_positive_on_real_self_word(self):
        """Pattern D must NOT flag real English words starting with
        "self" (e.g. "selfish", "selfless") — they're in the lexicon
        so the ``word not in lexicon`` check filters them out."""
        src = "the candidate was selfish in the negotiations."
        text = "the candidate was selfish in the negotiations."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        selfish_issues = [i for i in fusion if "selfish" in (i.detail or "")]
        assert selfish_issues == [], (
            "E3 Pattern D: 'selfish' is a real English word (in lexicon); "
            f"must NOT be flagged; got: {[i.detail for i in selfish_issues]}"
        )

    def test_pattern_d_no_false_positive_on_hyper_x_compounds(self):
        """Pattern D must NOT flag legitimate unhyphenated "hyper-X"
        compounds (e.g. "hypervigilance" — a real medical term where
        "hyper" is conventionally UNhyphenated). The "self"-only prefix
        constraint avoids this FP class (per the design rationale)."""
        src = "the patient exhibited hypervigilance and hyperalertness."
        text = "the patient exhibited hypervigilance and hyperalertness."
        _, issues = detect_sentence_fusion(text, "exec", source_text=src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        hyper_issues = [i for i in fusion if "hypervigilance" in (i.detail or "")]
        assert hyper_issues == [], (
            "E3 Pattern D: 'hypervigilance' is a legitimate unhyphenated "
            "compound ('hyper' is conventionally UNhyphenated, unlike 'self'); "
            f"must NOT be flagged; got: {[i.detail for i in hyper_issues]}"
        )

    def test_pattern_a_b_c_still_work(self):
        """Regression guard: the V0.5.4 Pattern D addition must NOT break
        the existing Pattern A/B/C detection. The V0.4.3 Pattern A case
        ('praiseity' = 'praise' + 3-char suffix 'ity') is still flagged.
        """
        src = "praise. Waelder noted that the theory is governed by the prompt."
        text = "The model produced praiseity governed by the prompt."
        _, issues = detect_sentence_fusion(text, "thorough", src)
        fusion = [i for i in issues if i.detector == "sentence_fusion"]
        assert len(fusion) >= 1, (
            "E3: Pattern D addition must not break Pattern A — 'praiseity' "
            "(praise + 3-char suffix 'ity') must still be flagged"
        )


# ═══════════════════════════════════════════════════════════════════════════
# E4 — LLM verification prompt: devil's-advocate instruction
# ═══════════════════════════════════════════════════════════════════════════


class TestE4DevilAdvocatePrompt:
    """E4: the V0.5.3 conv-log shows the LLM verification returned []
    (no corrections) — it rubber-stamped the summary. The fix adds a
    "devil's advocate" instruction to the verification prompt: argue
    AGAINST the summary, find the WEAKEST claim, default to scrutinizing
    not approving.
    """

    def test_llm_verification_prompt_includes_devil_advocate(self):
        """The _VERIFICATION_PROMPT in verification_phase.py contains
        the devil's-advocate instruction markers ("weakest", "scrutinize",
        "argue against" / "argue AGAINST")."""
        from core.summarisation.verification_phase import _VERIFICATION_PROMPT

        # The prompt must contain all 3 devil's-advocate markers
        # (any case — the prompt uses uppercase + lowercase).
        prompt_lower = _VERIFICATION_PROMPT.lower()
        assert "weakest" in prompt_lower, (
            "E4: prompt must mention 'weakest' (find the weakest claim — "
            "the one most likely to be a hallucination)"
        )
        assert "scrutiniz" in prompt_lower, (
            "E4: prompt must mention 'scrutinize' / 'scrutiny' "
            "(default to scrutinizing, not approving)"
        )
        assert "argue against" in prompt_lower, (
            "E4: prompt must contain 'argue against' (the devil's-advocate "
            "instruction — argue AGAINST the summary)"
        )

    def test_llm_verification_prompt_includes_rubber_stamp_warning(self):
        """The prompt explicitly warns that a rubber-stamp [] without
        scrutiny is a failure mode (the V0.5.3 audit's headline FN)."""
        from core.summarisation.verification_phase import _VERIFICATION_PROMPT

        prompt_lower = _VERIFICATION_PROMPT.lower()
        assert "rubber-stamp" in prompt_lower or "rubber stamp" in prompt_lower, (
            "E4: prompt must warn against rubber-stamp [] (the V0.5.3 audit "
            "found the LLM returned [] without scrutiny — a FN risk)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# B5 — Affected-populations prompt instruction (generic, content-agnostic)
# ═══════════════════════════════════════════════════════════════════════════


class TestB5AffectedPopulationsPrompt:
    """B5: the V0.5.3 ch.6 summary omitted the source's specific
    population list for acute/reactive paranoid disorders (source lines
    469-470: "immigrants, refugees, prisoners of war, inductees into
    military services, or people leaving home for the first time").

    The fix is a GENERIC instruction in the default summary prompt:
    "When the source describes a disorder/condition as affecting specific
    populations, include the SPECIFIC populations the source lists — do
    not generalise to 'vulnerable groups' or omit the list entirely."
    The instruction is content-agnostic (Rule 1): it tells the LLM to
    pull the population list from the runtime source — NO hardcoded
    "immigrants / refugees" (that would be the source's specific
    content, not a generic instruction).
    """

    def test_b5_affected_populations_prompt_instruction(self):
        """The default.md prompt contains the 'Affected Populations'
        instruction block (B5)."""
        prompt_text = Path("prompts/default.md").read_text(encoding="utf-8")
        assert "Affected Populations" in prompt_text, (
            "B5: prompts/default.md must contain the 'Affected Populations' "
            "section (V0.5.4 B5 fix — the instruction to include source-listed "
            "populations)"
        )
        assert "specific populations the source lists" in prompt_text.lower(), (
            "B5: the instruction must use the generic 'specific populations "
            "the source lists' phrasing (content-agnostic — lets the LLM "
            "pull from the runtime source, NOT hardcoded 'immigrants/refugees')"
        )

    def test_b5_no_hardcoded_specific_populations(self):
        """Rule 1 guard: the B5 instruction must NOT hardcode the
        source's specific populations ("immigrants", "refugees",
        "prisoners of war") — that would be book-specific content.
        The instruction must be GENERIC (the LLM pulls the list from
        the runtime source)."""
        prompt_text = Path("prompts/default.md").read_text(encoding="utf-8")
        # The specific populations named in the source chapter (lines
        # 469-470) MUST NOT appear in the prompt (they're book content).
        forbidden = ["immigrants", "refugees", "prisoners of war", "inductees"]
        violations = [w for w in forbidden if w.lower() in prompt_text.lower()]
        assert violations == [], (
            "B5 Rule 1 violation: the prompt must NOT hardcode the source's "
            f"specific populations ({violations} found in prompts/default.md) "
            "— the instruction must be generic ('pull the list from the "
            "runtime source'), not book-specific"
        )

    def test_b5_instruction_in_lowbit_prompt_too(self):
        """The lowbit variant (prompts/default_lowbit.md) also includes
        the B5 instruction (consistency with the full prompt)."""
        prompt_text = Path("prompts/default_lowbit.md").read_text(encoding="utf-8")
        assert "Affected Populations" in prompt_text, (
            "B5: prompts/default_lowbit.md must also contain the 'Affected "
            "Populations' instruction (consistency with the full prompt)"
        )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
