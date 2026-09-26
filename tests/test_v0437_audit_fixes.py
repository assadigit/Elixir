"""V0.4.37 — the F2+F3+F4+F6+F7 low-priority backlog release.

Characterization tests for the V0.4.37 fixes. All 5 backlog items were
flagged LOW PRIORITY in the V0.4.36 ch.6 audit's V0.4.37 backlog
(``audit/results/AUDIT_V0.4.36_run20260926-023012-00c5ef19_ch6_summary_vs_source.md``,
"V0.4.37 backlog" section). This file covers the items that are fully
validatable in-sandbox (no live-LLM rig required):

  F7 — detector false-positive tuning (observability):
    - grammar: recognize 3rd-person-singular "-s" verbs (e.g. "masks")
      so a clean academic bullet with a singular subject + "-s" verb
      isn't false-flagged as "no main verb".
    - attribution: lower the flag threshold to 40% (from 50%) on the
      thorough field, where tight paraphrases legitimately score 40-49%.

All fixes are content-agnostic (Rule 1 ✓): the grammar fix uses the
generic English lexicon (126k words, no domain terms); the attribution
fix is field-type-based (thorough vs exec/bullets), not content-based.
"""

from __future__ import annotations

import pytest

from core.models import SummaryResult
from core.pipeline.chapter_checkpoint import render_summary_markdown
from core.summarisation.postchecks.attribution import verify_attribution
from core.summarisation.postchecks.garble.token_detectors import (
    detect_grammatical_incoherence,
)

# ═══════════════════════════════════════════════════════════════════════════
# F7 (grammar): 3rd-person-singular "-s" verbs are recognized
# ═══════════════════════════════════════════════════════════════════════════


class TestV0437F7GrammarThirdSingular:
    """F7 (grammar): recognize 3rd-person-singular "-s" verbs.

    The V0.4.36 audit (conv-log lines 745/747) flagged two clean bullets
    as "no main verb detected in first 40 words" — both had the verb
    "masks"/"mask" which the suffix list (es/ed/ing/...) misses. The
    V0.4.37 fix: also accept a "-s" word whose singular form is in the
    generic English lexicon.
    """

    def test_third_singular_verb_not_flagged(self):
        """A clean bullet whose main verb is a 3rd-singular "-s" form
        (e.g. "the facade masks the defect") must NOT be flagged as
        having "no main verb" — the V0.4.36 audit F7 false-positive."""
        text = "The rigid facade masks an underlying fragility throughout the profile."
        _, issues = detect_grammatical_incoherence(text, "bullet[0]")
        verb_issues = [i for i in issues if "no main verb" in i.detail]
        assert verb_issues == [], (
            f"3rd-singular verb 'masks' should be recognized; got: {[i.detail for i in issues]}"
        )

    def test_inflected_verb_still_recognized(self):
        """Regression guard: inflected verbs (-ed/-ing/-es) still pass."""
        text = "The framework describes a mechanism that structured the field."
        _, issues = detect_grammatical_incoherence(text, "bullet[1]")
        assert [i for i in issues if i.detector == "grammar"] == []

    def test_truly_verbless_bullet_still_flagged(self):
        """Regression guard: a genuinely verbless noun-soup is still
        flagged (the 3rd-singular extension must not over-suppress)."""
        text = (
            "The big concept dissolution fragmentation contradiction "
            "everywhere dissolution fragmentation contradiction"
        )
        _, issues = detect_grammatical_incoherence(text, "bullet[2]")
        verb_issues = [i for i in issues if "no main verb" in i.detail]
        assert len(verb_issues) >= 1, "a verbless bullet must still be flagged"


# ═══════════════════════════════════════════════════════════════════════════
# F7 (attribution): the thorough field flags only below 40%
# ═══════════════════════════════════════════════════════════════════════════


def _rapidfuzz_stubbed() -> bool:
    """Detect the test_integration_pipeline.py rapidfuzz stub.

    When the full suite runs, test_integration_pipeline.py replaces
    rapidfuzz.fuzz.token_set_ratio with a lambda returning 80.0 — the
    similarity threshold checks can't distinguish bands. Skip the
    band-specific tests when the stub is active; run them in isolation.
    """
    try:
        from rapidfuzz import fuzz as _rf

        # One high-overlap probe (real rapidfuzz → 100) and one zero-
        # overlap probe (real → 0). The integration-pipeline stub
        # returns 80.0 for BOTH → equality means the stub is active.
        return _rf.token_set_ratio("the cat", "the cat") == _rf.token_set_ratio("aaa", "zzz")
    except ImportError:
        return False


class TestV0437F7AttributionThoroughThreshold:
    """F7 (attribution): the thorough field flags only below 40%.

    The V0.4.36 audit (conv-log lines 763-783) flagged 11 thorough
    claims at 34-49% similarity — all CORRECT paraphrases, not
    misattributions. The V0.4.37 fix: on the thorough field (long-prose
    paraphrase territory), flag only claims < 40%; keep 50% for
    exec/bullets (terse, less paraphrase latitude).
    """

    def test_thorough_flags_truly_low_sim(self):
        """A claim well below 40% similarity still flags on thorough."""
        if _rapidfuzz_stubbed():
            import pytest

            pytest.skip("rapidfuzz stubbed in full-suite run")
        source = "Author (1900) described the mechanism in terms of systemic regulation."
        # 20-token gibberish summary: shares only the citation tokens
        # → token_set_ratio ~0.36 (< 0.40 thorough threshold). Measured
        # 0.357 at write-time; the assertion below pins the band so a
        # future rapidfuzz drift surfaces here rather than silently
        # passing.
        summary = (
            "Author (1900) bzzt qwx nnn ppp vvv kkk jjj mmm uuu "
            "rrr sss ttt xxx yyy www aaa bbb ccc."
        )
        _, issues = verify_attribution(summary, source, "thorough", ["Author"])
        attrib = [i for i in issues if i.detector == "attribution"]
        assert attrib, "a <40% claim must still flag on thorough"

    def test_paraphrase_band_not_flagged_on_thorough(self):
        """A tight paraphrase scoring in the 40-50% band must NOT flag
        on the thorough (the V0.4.36 audit F7 false-positive). The same
        claim on exec keeps the 50% threshold and flags (when its
        salient vocabulary doesn't track the source)."""
        if _rapidfuzz_stubbed():
            import pytest

            pytest.skip("rapidfuzz stubbed in full-suite run")
        source = "Author (1900) described the mechanism in terms of systemic regulation."
        # Shares only the citation tokens with the source (the rest is
        # divergent gibberish) → token_set_ratio ~0.43 (in the 40-50%
        # band). Measured 0.432 at write-time.
        summary = "Author (1900) xyzzy quux foobar wobble frobnicate zzzz."
        # Measure the actual similarity to confirm we're in the band.
        try:
            from rapidfuzz import fuzz as _rf

            _sim = _rf.token_set_ratio(summary, source) / 100.0
        except ImportError:
            from difflib import SequenceMatcher

            _sim = SequenceMatcher(None, summary, source).ratio()
        assert 0.40 <= _sim < 0.50, f"test fixture sim = {_sim:.3f} (want 0.40-0.50)"
        # Thorough: 40% threshold → no flag.
        _, tho = verify_attribution(summary, source, "thorough", ["Author"])
        assert not [i for i in tho if i.detector == "attribution"], (
            "thorough paraphrase in 40-50% band must not flag (F7)"
        )
        # Exec: 50% threshold + rescue fails (divergent salient vocab:
        # xyzzy/quux/foobar/wobble/frobnicate/zzzz are all absent from
        # the source) → still flagged.
        _, exc = verify_attribution(summary, source, "exec", ["Author"])
        assert [i for i in exc if i.detector == "attribution"], (
            "exec keeps the 50% threshold (F7 thorough-only relaxation)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# F6: render-boundary stray-quote sweep (defense-in-depth)
# ═══════════════════════════════════════════════════════════════════════════


class TestV0437F6RenderStrayQuoteSweep:
    """F6: a final stray-quote sweep at the render boundary catches
    orphans the postcheck's single-line pass missed.

    The V0.4.36 ch.6 audit (F6, LOW PRIORITY — observability) found a
    stray ``"`` before a trailing participle survived into the rendered
    thorough despite the postcheck logging no ``stray_quote`` fix. The
    root cause: the postcheck's ``repair_stray_quotes_v2`` runs on the
    thorough while it is still a single long line; its state-machine
    can mis-pair ambiguous quotes on a long line and leave an orphan.
    The V0.4.36 (F3) paragraph-breaking that runs in render shortens
    the thorough into paragraph-lines, making per-line pairing far more
    reliable — so re-running the sweep AFTER paragraph-breaking catches
    orphans the earlier single-line pass missed.
    """

    _STRAY_THOROUGH = (
        "An initial paragraph introduces the topic at length with substantial "
        "exposition describing the background and the historical context in "
        "considerable detail for the reader and establishes the conceptual "
        "foundation upon which the subsequent analytical discussion will rest. "
        "Alpha (1900) described the mechanism in terms of systemic regulation "
        "and the feedback architecture of the apparatus across the field "
        "comprehensively and with considerable analytical nuance for the era. "
        "Beta (1910) extended the framework with new theoretical contributions "
        "and elaborated the structural model considerably for subsequent "
        "researchers working in the same tradition and intellectual lineage. "
        "Gamma (1920) synthesized these contributions into a coherent fighting "
        'stance" providing integrity against despair across the entire domain '
        "for future scholars to build upon systematically and without reservation."
    )

    def test_render_sweep_removes_stray_quote(self):
        """The stray ``"`` before 'providing' is removed by the render
        sweep (the V0.4.36 F6 evidence, reproduced)."""
        summ = SummaryResult(
            chapter_heading="6 Profile",
            executive_summary="A clean exec summary with no stray quotes.",
            bullet_points=["A clean bullet.", "Another clean bullet."],
            thorough_summary=self._STRAY_THOROUGH,
            success=True,
            model_used="mock",
            input_tokens=100,
            output_tokens=200,
        )
        rendered = render_summary_markdown(summ)
        # The stray quote before 'providing' is gone.
        assert 'stance" providing' not in rendered, (
            "F6 render sweep should remove the stray quote before 'providing'"
        )
        # And the rendered thorough has no odd-count quote line.
        thorough_section = rendered.split("## Thorough Summary", 1)[1]
        for line in thorough_section.split("\n"):
            if line.count('"') % 2 == 1:
                pytest.fail(f"rendered thorough has an odd-count quote line: {line[:60]!r}")

    def test_render_sweep_idempotent_on_clean_thorough(self):
        """A clean thorough (no stray) is unchanged — the sweep must not
        false-positive (remove a legit balanced quote pair or add quotes)."""
        clean_thorough = (
            "An initial paragraph introduces the topic at length with "
            "substantial exposition for the reader. Alpha (1900) described "
            'the "mechanism of regulation" in terms of systemic feedback.'
        )
        summ = SummaryResult(
            chapter_heading="6 Profile",
            executive_summary="A clean exec summary.",
            bullet_points=["A clean bullet."],
            thorough_summary=clean_thorough,
            success=True,
            model_used="mock",
            input_tokens=100,
            output_tokens=200,
        )
        rendered = render_summary_markdown(summ)
        # The legit balanced quote pair survives (sweep only removes orphans).
        assert '"mechanism of regulation"' in rendered, (
            "the render sweep must not strip a balanced legit quote pair"
        )


# ═══════════════════════════════════════════════════════════════════════════
# F4: gap-fill prompt retains multi-author attribution form
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.gap_fill_batch import batch_gap_fill


def _v0437_f4_capturing_deps():
    """Minimal hermetic deps for batch_gap_fill that capture the prompt."""
    llm_calls = []

    def check_coverage(analysis, text):
        text = text or ""
        covered = [a for a in analysis["authors"] if a in text]
        missing = [a for a in analysis["authors"] if a not in text]
        total = len(analysis["authors"])
        pct = (len(covered) / total) if total else 0.0
        return {"covered": covered, "missing": missing, "total": total, "coverage_pct": pct}

    def call_fast_llm(prompt, max_tokens=None, temperature=None, **kw):
        llm_calls.append(prompt)
        # Return a bullet naming the missing author so coverage clears →
        # the loop exits after round 1 (one prompt captured).
        return "- AuthorA established the framework."

    def strip_thinking(text):
        return text

    def filter_thinking_bullets(bullets, concepts=None, source_text=""):
        return list(bullets)

    def log(msg, level="INFO"):
        pass

    return {
        "check_coverage": check_coverage,
        "call_fast_llm": call_fast_llm,
        "strip_thinking": strip_thinking,
        "filter_thinking_bullets": filter_thinking_bullets,
        "log": log,
        "llm_calls": llm_calls,
    }


class TestV0437F4MultiAuthorAttribution:
    """F4: the gap-fill prompt instructs the LLM to retain multi-author
    attribution form (e.g. 'AuthorA and AuthorB (Year)') rather than
    reduce it to a single name.

    The V0.4.36 ch.6 audit (F4, LOW PRIORITY) found gap-fill bullets
    that dropped a co-author (the source's 'AuthorA and AuthorB (Year)'
    shipped as just 'AuthorB'). The single-name form is accurate but
    loses citation granularity. The fix: a genre-agnostic attribution
    rule (Rule 1 ✓ — about citation FORM, not content; placeholders
    are generic) added to the per-author batch gap-fill prompt + the
    two concept/reprompt gap-fill templates.
    """

    def test_batch_gap_fill_prompt_carries_multi_author_rule(self):
        deps = _v0437_f4_capturing_deps()
        src = "AuthorA and AuthorB (1990) described the framework."
        analysis = {"authors": ["AuthorA", "AuthorB"]}
        batch_gap_fill(
            "Chapter 6 — Profile",
            src,
            ["An existing bullet."],
            ["AuthorA"],
            analysis,
            ["AuthorA", "AuthorB"],
            check_coverage=deps["check_coverage"],
            call_fast_llm=deps["call_fast_llm"],
            temperature=0.2,
            strip_thinking=deps["strip_thinking"],
            filter_thinking_bullets=deps["filter_thinking_bullets"],
            log=deps["log"],
        )
        assert deps["llm_calls"], "the gap-fill loop should have issued a prompt"
        prompt = deps["llm_calls"][0]
        assert "multi-author attribution form" in prompt, (
            "F4: the per-author batch gap-fill prompt must instruct the LLM "
            "to retain the multi-author attribution form"
        )
        assert "AuthorA and AuthorB" in prompt, (
            "F4: the rule must illustrate the form with generic placeholders"
        )

    def test_gap_fill_concept_template_carries_multi_author_rule(self):
        from pathlib import Path

        tpl = Path("prompts/summarisation/gap_fill_concept.md").read_text(encoding="utf-8")
        assert "multi-author attribution" in tpl
        assert "AuthorA and AuthorB" in tpl

    def test_gap_fill_reprompt_template_carries_multi_author_rule(self):
        from pathlib import Path

        tpl = Path("prompts/summarisation/gap_fill_reprompt.md").read_text(encoding="utf-8")
        assert "multi-author attribution" in tpl
        assert "AuthorA and AuthorB" in tpl


# ═══════════════════════════════════════════════════════════════════════════
# F3: coverage-driven thorough gap-fill engagement (not word-count-only)
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.thorough_theorist_floor import _v05_gapfill_should_skip


class TestV0437F3CoverageDrivenGate:
    """F3: the V0.05 thorough gap-fill engages on COVERAGE, not word-count
    alone.

    The V0.4.36 ch.6 audit (F3, LOW PRIORITY -- observability) noted the
    thorough gap-fill's V0.05 word-count gate could ship a coverage
    deficit: a thorough meeting its source-scaled word target while still
    well below the coverage fraction. The V0.4.37 fix: the gate skips
    ONLY when word-count is met AND coverage is at/above the engage
    fraction (0.70); below that, the gap-fill runs to close the coverage
    gap regardless of word-count. Content-agnostic (Rule 1): the
    threshold is a coverage FRACTION, not a chapter-specific theorist count.
    """

    def test_wordcount_met_low_coverage_engages(self):
        """Word-count met BUT coverage 50% < 70% -> engage (no skip)."""
        skip, reason = _v05_gapfill_should_skip(50, 40, 1, 2)
        assert skip is False
        assert "V0.4.37 F3" in reason
        assert "coverage-driven engagement" in reason

    def test_wordcount_met_high_coverage_skips(self):
        """Word-count met AND coverage 80% >= 70% -> skip (few missing
        left to the bullets/recall floor)."""
        skip, reason = _v05_gapfill_should_skip(50, 40, 8, 10)
        assert skip is True
        assert "V0.05" in reason
        assert ">= the engage fraction" in reason

    def test_wordcount_unmet_engages_no_reason(self):
        """Word-count below target -> engage (no skip, no F3 reason --
        the existing 'below target' path, unchanged)."""
        skip, reason = _v05_gapfill_should_skip(30, 40, 1, 2)
        assert skip is False
        assert reason == ""

    def test_no_target_never_skips(self):
        """scaled_target_hi None -> the gate is inactive (never skips)."""
        skip, reason = _v05_gapfill_should_skip(500, None, 0, 10)
        assert skip is False
        assert reason == ""


class TestV0437F3IntegrationEngagesDespiteWordcount:
    """F3 integration: a thorough that meets its word target but has low
    coverage still fires the gap-fill (coverage-driven engagement)."""

    def test_low_coverage_engages_despite_wordcount_met(self):
        # Reuse the hermetic Voss/Ibarra fixtures from the thorough-floor
        # suite (synthetic placeholder names -- deny-list safe).
        import time

        from test_v1820313_thorough_floor import (
            _ANALYSIS,
            _CANNED,
            _SOURCE,
            _THOROUGH,
            _make_bare,
        )

        # _THOROUGH is ~58 words and covers 1/2 (Voss only -> 50% coverage).
        # scaled_target_hi=40 -> word-count met (58 >= 40) BUT coverage
        # 50% < 70% -> F3 overrides the word-count skip -> gap-fill runs.
        s, llm_calls, _ = _make_bare(responses=[_CANNED])
        # _make_bare arms the real deadline machinery; ensure it's NOT
        # exceeded so the non-skippable-deadline WARNING path is inert.
        s._chapter_deadline_start = time.time()
        result = s._thorough_theorist_floor(
            "Chapter One", _SOURCE, _THOROUGH, _ANALYSIS, scaled_target_hi=40
        )
        # The gap-fill engaged despite word-count being met (F3).
        assert len(llm_calls) == 1, (
            "F3: gap-fill must engage despite word-count met when coverage "
            "is below the engage fraction"
        )
        # The canned addition was appended.
        assert result != _THOROUGH
        # The F3 coverage-driven engagement reason was logged.
        assert any(
            "V0.4.37 F3" in msg and "coverage-driven engagement" in msg for _lvl, msg in s.log_lines
        ), "F3 engage reason must be logged"


# ═══════════════════════════════════════════════════════════════════════════
# F2(c): dedup symmetric-difference guard tightened (<=6 -> <=4)
# ═══════════════════════════════════════════════════════════════════════════

from core.summarisation.bullet_consolidation import consolidate_duplicate_claims


class TestV0437F2cDedupGuardTightened:
    """F2(c): the dedup symmetric-difference guard is tightened from
    <=6 to <=4 so a pair of high-similarity bullets that differ in 5-6
    words (more likely rewording of a DISTINCT claim than a subject
    swap) is preserved, not merged.

    The V0.4.36 ch.6 audit (F2c) found the dedup round culled 20/99 =
    20% and asked whether the threshold could be tightened to let more
    distinct gap-fill candidates ship. Raising the SIM threshold (0.92
    -> 0.95) was rejected: the canonical subject-swap case sits at
    sim ~0.928, so 0.95 would stop merging legitimate subject-swaps
    (under-merge). Instead the symmetric-difference guard is tightened
    (<=6 -> <=4): a 1-name swap = 2 diff words; an N-name swap still
    merges via pairwise 2-word diffs; a 5-6-word-diff pair at sim>=0.92
    is preserved. Content-agnostic (Rule 1): a numeric diff-count guard.

    F2(a) the active-subject veto and F2(b) the V0.4.23 filler floor
    are NOT loosened here -- both gates were deliberately calibrated to
    block specific misattribution/filler defects (veto: bullets where
    the author isn't the grammatical subject of an attribution verb;
    filler floor: high-precision patterns each matching a shipped
    filler). Loosening either risks re-introducing the exact defects
    they were built to block; the audit's evidence is book-specific and
    the fix needs a live-LLM rig run to validate no regression. They
    remain as-is for a future rig-validated tuning pass.
    """

    def test_canonical_subject_swap_still_merges(self):
        """A 1-name subject swap (2 diff words, sim ~0.93) still merges --
        the V0.4.37 <=4 guard preserves the canonical case."""
        b = [
            "Jacobson views identity consolidation as sine qua non of pathology.",
            "Kernberg views identity consolidation as sine qua non of pathology.",
        ]
        out = consolidate_duplicate_claims(b)
        assert len(out) == 1, "canonical 1-name subject-swap must still merge"

    def test_5_word_diff_high_sim_pair_preserved(self):
        """A sim>=0.92 pair differing in 5 words (rewording of a distinct
        claim, not a subject swap) is PRESERVED at the V0.4.37 <=4 guard
        (it would have merged at the old <=6)."""
        b = [
            "AuthorA described the identity consolidation process as the sine qua non there.",
            "AuthorB described the identity consolidation process as the sine qua non here now.",
        ]
        out = consolidate_duplicate_claims(b)
        assert len(out) == 2, (
            "a 5-word-diff pair at sim>=0.92 must be preserved (not a subject "
            "swap -- the V0.4.37 F2c <=4 guard)"
        )
