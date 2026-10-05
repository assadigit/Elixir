"""V18.20.3.2 characterization tests — third real-rig audit fixes.

Covers the defect classes found by the V18.20.3.1 "Broken Structures"
real-rig run audit (audit/results/AUDIT_V18.20.3.1_realrig.md; log: 725
lines; output: 39 bullets, scorecard 6.5/10 REGRESSION):

P0-1 — LATE CoT NUKE INVALIDATED EVERY THOROUGH GATE: the primary call
   returned exec=0 + a 34,794-char thorough that was 100% CoT; the
   V18.19.2.2 nuke fired 26 MINUTES later in postchecks — by then the
   V18.14 thorough-judge had validated the CoT text (29/34 authors) and
   the shipped "Thorough Summary" was a verbatim copy of the 191-word
   exec (real coverage ~19/34). Fix: PARSE-TIME CoT gate + final
   re-derivation from exec + FINAL bullets + thorough-judge re-run.

P0-2 — MODEL SELF-TALK SHIPPED AS KEY TAKEAWAYS: "Stoller (1968) -
   include this! Let me add it." + "Erikson (1958) - be more specific.
   The source says …" — the expansion-path filter logged "kept 0" while
   37 candidates merged; the judge flagged them ungrounded but the
   appeal auto-KEPT on 100% source overlap (self-talk quoting the source
   defeats the overlap rescue). Fix: batch expansion filter + mid-bullet
   SELF_TALK_PATTERNS (always-drop) + judge-appeal carve-out.

P1-a — PARENTHETICAL-PROMOTION MISATTRIBUTIONS ×3 (Khan→Winnicott,
   Klein→Kernberg, Searles→Lichtenstein — the class widened 1→2→3 across
   .2.0/.3.0/.3.1). Fix: generation-time active-subject veto
   (detect_parenthetical_promotion) in the V18.14.1 batch gap-fill +
   pre-ship DROP in run_post_checks.

P1-b — GAP-FILL BULLETS BYPASSED SEMANTIC DEDUP (near-verbatim duplicate
   pair shipped). Fix: second dedup pass after all bullet-generation
   stages.

P1-c — BROKEN LEAD BULLETS SHIPPED (citation dump + no-predicate
   fragment as Key-Takeaways #1-2). Fix: citation-only fragment drop at
   generation + ship time.

P1-d — CONSOLIDATION + SCHOLAR STILL HIT THE 4096 CAP; scholar's "no
   significant gaps found" was parsed from a TRUNCATED response.
   Fix: 6144 + "VERDICT UNRELIABLE (truncated)" qualifier.

P1-e — ADDITIVE YIELD REGRESSION (5/9 items dropped as truncated).
   Fix: retry-on-mass-drop (>50%).

P2-a — DROPPED_LETTER FPs ×8 on ordinary words (moving/seven/stages/
   clarify/fusing/raising/identifies). Fix: common-word stoplist +
   suffix-stem lookup.

P2-b — YEAR STYLING INCONSISTENT ("(1956)" styled, "(1961, 1963)" plain)
   + 'ego ideal' → 'egoideal' join corruption. Fix: every-parenthesized-
   year styling + GLOBAL split-form veto.

P2-c — presence_penalty/keep_alive invisible in the settings banner.

P2-d — THERMAL REPORT CUT OFF after "Session duration": ROOT CAUSE was a
   DEADLOCK — ThermalBudget.format_report() acquires self._lock then
   calls the minutes_above_threshold property which acquires the SAME
   non-reentrant Lock. Fix: RLock + per-line guards in log_report.
"""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════
# Real regression vectors from the V18.20.3.1 Broken Structures run
# ═══════════════════════════════════════════════════════════════════════════

# Source excerpts (gold standard, verbatim)
SRC_KHAN = (
    "Winnicott Although Winnicott did not use the term identity specifically, "
    "his views on early development are of great significance to the formation "
    "of identity. His work provides the developmental basis for (1) "
    "authenticity; (2) \u201ccorporeality\u201d (Khan 1983), or a deeply "
    "assimilated and personalized bodily foundation for one's selfexperience; "
    "and (3) the experience of temporal continuity in the self."
)
SRC_KLEIN = (
    "By integrating the works of Klein (1948), Erikson (1950a,b, 1958, 1962), "
    "Jacobson (1964), and Mahler (1968, 1971, 1975) with his own views, "
    "Kernberg formulated a three-step process of identity formation. The "
    "first step in the process is introjection, whereby certain affectively "
    "charged, specific attributes of others are internalized without being "
    "fully assimilated into the self-image."
)
SRC_SEARLES = (
    "Juxtaposed to the driving pressure of this \u201cidentity theme\u201d is "
    "a second force, which, according to Lichtenstein, is the longing to "
    "abandon the human quality of identity (see also Searles 1960 in this "
    "connection). Lichtenstein recognizes that the abandonment of identity "
    "produces confusion and anguish, but he also indicates that this loss "
    "can be experienced as liberation and ecstasy."
)

# The 3 shipped misattribution bullets (verbatim from the V18.20.3.1 output)
BULLET_KHAN = (
    "Khan: Provided the developmental basis for authenticity, 'corporeality' "
    "(a deeply assimilated and personalized bodily foundation for "
    "self-experience), and the experience of temporal continuity in the self."
)
BULLET_KLEIN = (
    "Klein: Contributed to the formulation of a three-step process of "
    "identity formation by integrating his 1948 work with those of Erikson, "
    "Jacobson, and Mahler within Kernberg's theoretical framework."
)
BULLET_SEARLES = (
    "Searles: Identified a force juxtaposed to the driving pressure of the "
    "'identity theme,' specifically the longing to abandon the human quality "
    "of identity, in connection with Lichtenstein's views."
)

# The 2 shipped self-talk bullets (verbatim)
SELF_TALK_1 = "Stoller (1968) - include this! Let me add it."
SELF_TALK_2 = (
    'Erikson (1958) - be more specific. The source says "Erikson (1958)" '
    "in the context of the term being introduced. Actually, looking at the "
    'text: "In the 1950s Erikson (1950a, 1956, 1958, 1959) resurrected the '
    'term."'
)

# The 2 shipped broken lead bullets (verbatim)
FRAGMENT_FREUD = "Freud's contributions (das Ich, ego)"
FRAGMENT_CITATIONS = "Federn (1952), Glover (1950), Spiegel (1959)"

# The V18.20.3.1 primary-call raw response opening (100% CoT — log :373)
COT_PRIMARY_OPENING = (
    "The user wants a comprehensive, faithful summary of Chapter 1 "
    "\u201cIDENTITY AND ITS ORIGINS\u201d from what appears to be Kernberg's "
    "book on borderline and narcissistic disorders. Let me carefully extract "
    "all key concepts, arguments, frameworks, named contributors, and "
    "examples.\n\nLet me organize my thoughts:\n\n**Named contributors in "
    "order:**\nTausk (1919), Erikson (1958), Erikson (1950), Jacobson (1964), "
    "Mahler (1958), Erikson (1956), Eissler (1958), Kernberg (1967), Fromm "
    "(1955), Wheelis (1958), Lynd (19"
)


# ═══════════════════════════════════════════════════════════════════════════
# 1) P0-1 — parse-time CoT gate (detect_cot_narrative on the real vector)
# ═══════════════════════════════════════════════════════════════════════════


class TestParseTimeCoTGate:
    """The primary-call CoT that shipped in V18.20.3.1 must be caught by
    detect_cot_narrative — the function the new parse-time gate calls at
    00:04:26 instead of 00:30:30."""

    def test_real_primary_cot_detected(self):
        from core.summarisation.postchecks import detect_cot_narrative

        # The full thorough was 34,794 chars; the opening already carries
        # 4+ distinct CoT markers.
        text = COT_PRIMARY_OPENING * 3  # >= 50 chars, sustained pattern
        cleaned, issues = detect_cot_narrative(text, "thorough")
        assert issues, "the V18.20.3.1 primary CoT must be detected"
        assert cleaned == "", "CoT thorough must be truncated to empty"
        assert issues[0].detector == "cot_narrative"

    def test_legitimate_thorough_passes(self):
        from core.summarisation.postchecks import detect_cot_narrative

        text = (
            "This chapter traces the theoretical evolution of identity from "
            "Tausk's initial use of the term through Erikson's revival of ego "
            "identity. The developmental arc spans infant-mother interactions, "
            "primitive introjections, differentiation, Oedipal resolution, and "
            "adolescent consolidation. The chapter concludes by defining seven "
            "cross-sectional characteristics of a solid identity: selfsameness, "
            "temporal continuity, authenticity, realistic body image, inner "
            "solidity, gender clarity, and ethnic solidarity with an "
            "internalized conscience."
        )
        cleaned, issues = detect_cot_narrative(text, "thorough")
        assert not issues
        assert cleaned == text

    def test_v0203_thorough_floor_cot_leak_detected(self):
        """V0.20.3 (Quality Campaign, audit V0.20.2 ch.2): the thorough-
        theorist-floor gap-fill call produced a ~52-line CoT thinking block
        that leaked into the shipped thorough summary. The existing 25
        markers matched only 1 (the threshold is 3), so detect_cot_narrative
        did NOT fire and the raw thinking shipped. The V0.20.3 fix added 12
        new markers for the thorough-floor gap-fill's CoT shape: 'Let me
        identify', 'Let me re-read', 'Let me compile', 'Hmm, could', 'The
        user wants me to', 'I will skip/treat', etc. This test proves the
        fix catches the actual V0.20.2 ch.2 leak."""
        from core.summarisation.postchecks import detect_cot_narrative

        # Verbatim excerpt from the V0.20.2 ch.2 thorough-floor gap-fill CoT
        # leak (audit/results/AUDIT_V0.20.2_run20260921-003234-00d02c99_ch2_summary_vs_source.md)
        text = (
            "The user wants me to write 1-2 paragraphs (150-300 words) that "
            "weave in specific contributors from the chapter, each with their "
            "specific contribution as described in the source text. Let me "
            "identify each contributor and their specific contribution:\n"
            "1. Chasseguet-Smirgel - mentioned multiple times\n"
            "2. Levy - eternal dilettante\n"
            'Wait - "Erikson in" - this is odd. Looking at the text, I see '
            '"Eisner" is not mentioned. Let me re-read: "Erikson in" - '
            "could this be a typo?\n"
            'Hmm, "Erikson in" - I think this might be a formatting error. '
            "Let me just treat it as Erikson and move on.\n"
            'Let me also check: "Klass and Offenkrantz" - this appears at '
            "the end of the list.\n"
            "Let me compile each contributor's specific contribution.\n"
            "I will skip it since Erikson is already covered."
        )
        cleaned, issues = detect_cot_narrative(text, "thorough")
        assert issues, (
            "the V0.20.2 ch.2 thorough-floor CoT leak must be detected "
            "(V0.20.3: the new markers catch 'Let me identify', 'Let me "
            "re-read', 'Hmm, could', 'The user wants me to', 'I will skip')"
        )
        assert cleaned == "", "CoT thorough must be truncated to empty"
        assert issues[0].detector == "cot_narrative"

    def test_summarizer_flags_reset_per_chapter(self):
        """The new per-chapter flags must be initialized to False at the
        top of _summarize_inner — verified by source inspection of the
        reset block (attribute existence on a bare instance)."""
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        # The reset block runs inside _summarize_inner; the flags are plain
        # instance attrs. Assert the defaults used by getattr() hold on a
        # bare instance (getattr default False == the reset value).
        assert getattr(s, "_primary_thorough_cot_nuked", False) is False
        assert getattr(s, "_primary_exec_cot_nuked", False) is False
        assert getattr(s, "_thorough_is_synthetic", False) is False
        # And the source contains the reset block (regression pin).
        import inspect

        # V0.18 (Phase 5.1, steps 2-4): the per-chapter reset block moved
        # VERBATIM to the setup phase; the CoT gate to the single-pass phase.
        src = inspect.getsource(Summarizer._phase_setup_and_gate)
        assert "_primary_thorough_cot_nuked = False" in src
        assert "_thorough_is_synthetic = False" in src
        src = inspect.getsource(Summarizer._phase_single_pass_primary)
        assert "PARSE-TIME CoT gate" in src

    def test_parse_gate_and_rederivation_source_pins(self):
        """Regression pins: the parse-time gate, the final re-derivation,
        and the thorough-judge re-run must all exist in _summarize_inner."""
        import inspect

        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        # V0.18 (Phase 5.1, steps 2-4): the parse-time CoT gate moved
        # VERBATIM to the single-pass phase method.
        src = inspect.getsource(Summarizer._phase_single_pass_primary)
        assert "DISCARDED AT PARSE TIME" in src
        # V0.18 (Phase 5.1, step 1): the re-derivation/re-run block moved
        # VERBATIM to the postchecks phase method.
        src = inspect.getsource(Summarizer._phase_postchecks_and_floors)
        assert "Thorough re-derived from exec + FINAL" in src
        assert "Thorough-judge RE-RUN" in src

    def test_expansion_batch_filter_source_pin(self):
        """P0-2: the expansion path must batch-filter candidates (no more
        per-bullet filter calls with the confusing 'kept 0' aggregate)."""
        import inspect

        from core.summarisation.summarizer import Summarizer

        src = inspect.getsource(Summarizer._summarize_inner)
        # V0.18 (Phase 5.1, steps 2-4): the expansion filter moved VERBATIM
        # to the thorough-and-coverage phase method.
        src = inspect.getsource(Summarizer._phase_thorough_and_coverage)
        assert "BATCH-filter the expansion" in src
        assert "Expansion filter dropped" in src


# ═══════════════════════════════════════════════════════════════════════════
# 2) P0-2 — self-talk patterns + classify_bullets + judge-appeal carve-out
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfTalkPatterns:
    def test_real_self_talk_bullets_caught(self):
        from core.summarisation.post_processing import SELF_TALK_PATTERNS

        assert SELF_TALK_PATTERNS.search(SELF_TALK_1)
        assert SELF_TALK_PATTERNS.search(SELF_TALK_2)

    def test_legitimate_bullets_pass(self):
        from core.summarisation.post_processing import SELF_TALK_PATTERNS

        ok_bullets = [
            "Erikson (1956) defined ego identity as a persistent sameness within oneself.",
            "The chapter distinguishes sociocultural determinants from the "
            "personal origins of identity.",
            "Kernberg formulated a three-step process: introjection, "
            "identification, and identity formation.",
        ]
        for b in ok_bullets:
            assert not SELF_TALK_PATTERNS.search(b), b

    def test_classify_bullets_drops_self_talk_always(self):
        """Self-talk is structural contamination: always_drop=True even in
        conservative mode."""
        from core.summarisation.post_processing import classify_bullets

        kept, drops = classify_bullets([SELF_TALK_1, SELF_TALK_2])
        assert kept == []
        stages = {d[1] for d in drops}
        assert "thinking_filter.self_talk" in stages
        assert all(d[3] is True for d in drops if d[1] == "thinking_filter.self_talk")

    def test_run_post_checks_drops_self_talk_bullet(self):
        """Ship-time defense: a self-talk bullet that survived to
        postchecks is dropped (severity=fix records it)."""
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            bullets=[SELF_TALK_1, "Erikson (1956) defined ego identity."],
            executive_summary="A summary.",
            thorough_summary="A thorough summary of the chapter.",
            source_text=SRC_KHAN,
        )
        assert "Erikson (1956) defined ego identity." in report.bullets
        assert all("Stoller" not in b for b in report.bullets)
        assert any(i.detector == "self_talk" and i.severity == "fix" for i in report.issues)


class TestJudgeAppealCarveOut:
    """P0-2: self-talk bullets flagged ungrounded by the LLM judge must be
    DROPPED even at 100% source overlap (the .3.1 rescue path)."""

    def _run_content_judge_segment(self, monkeypatch):
        """Drive BulletPipeline.run_content_judge with a fake judge that
        flags one self-talk bullet + one legit bullet, both at high
        source overlap (the rescue path)."""
        from core.summarisation.bullet_pipeline import BulletPipeline

        logs = []

        class _Q:
            entries = []

            def add(self, *a, **k):
                self.entries.append(k)

            def summary(self):
                return {}

        s = types.SimpleNamespace(
            log=lambda msg, level="INFO": logs.append((level, msg)),
            quarantine=_Q(),
            coverage_threshold=0.85,
            conservative_drops=False,
            _claim_extractor=None,
            _last_judge_result=None,
            judge_results=[],
            request=types.SimpleNamespace(source_type="normal_book"),
            _current_heading="Ch1",
        )

        # Fake ContentJudge: both bullets "ungrounded" per the LLM judge.
        class _FakeJudgeResult:
            summary = "fake"
            # One self-talk bullet (must be dropped by the carve-out) + one
            # high-overlap legit bullet (must be rescued by the appeal).
            ungrounded_bullets = [
                SELF_TALK_1,
                "Winnicott did not use the term identity specifically, but "
                "his views on early development are of great significance to "
                "the formation of identity.",
            ]
            grounding_layer8_available = False
            grounding_alarm = None
            hallucination_count = 0
            grounding_pct = 1.0
            grounded_bullets = 2
            total_bullets = 2
            needs_gap_fill = False
            uncovered_claims = []
            coverage_pct = 1.0
            deviation_count = 0
            deviation_details = []

        class _FakeJudge:
            def __init__(self, **kw):
                pass

            def judge(self, result, content):
                return _FakeJudgeResult()

        # Patch via sys.modules (NOT the string form — test_content_judge.py
        # replaces sys.modules["core.summarisation.content_judge"] with a
        # directly-loaded module, which breaks monkeypatch's string-path
        # resolution in full-suite runs). The lazy import inside
        # run_content_judge consults sys.modules first.
        monkeypatch.setitem(
            sys.modules,
            "core.summarisation.content_judge",
            types.SimpleNamespace(ContentJudge=_FakeJudge),
        )
        # _llm_grounding_check returns the same list (LLM-as-judge path)
        s._llm_grounding_check = lambda bullets, content: list(_FakeJudgeResult.ungrounded_bullets)

        pipeline = BulletPipeline.__new__(BulletPipeline)
        pipeline.s = s
        from core.summarisation.bullet_pipeline import PipelineState

        state = PipelineState(
            heading="Ch1",
            content=SRC_KHAN,
            bullets=[
                SELF_TALK_1,
                "Winnicott did not use the term identity specifically, but "
                "his views on early development are of great significance to "
                "the formation of identity.",
            ],
            exec_sum="A summary.",
            thorough="A thorough.",
        )
        reject = pipeline.run_content_judge(state, 0.9, 100, "combined")
        assert reject is None
        return s, state, logs

    def test_self_talk_dropped_despite_overlap(self, monkeypatch):
        s, state, logs = self._run_content_judge_segment(monkeypatch)
        # The self-talk bullet must be GONE from state.bullets…
        assert all("Stoller" not in b for b in state.bullets)
        # …while the legit high-overlap bullet was rescued (kept).
        assert any("Winnicott did not use the term" in b for b in state.bullets)
        # …and the carve-out log fired.
        assert any("judge-appeal carve-out" in m for _, m in logs)


# ═══════════════════════════════════════════════════════════════════════════
# 3) P1-a — parenthetical-promotion veto (the Khan/Klein/Searles class)
# ═══════════════════════════════════════════════════════════════════════════


class TestParentheticalPromotion:
    def test_khan_vector(self):
        """Khan credited with Winnicott's developmental-basis claim."""
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        result = detect_parenthetical_promotion(BULLET_KHAN, SRC_KHAN)
        assert result == ("Khan", "Winnicott")

    def test_klein_vector(self):
        """Klein credited with Kernberg's three-step process (the paraphrase
        variant that evaded the V18.20.3.1 colon-verb regex)."""
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        result = detect_parenthetical_promotion(BULLET_KLEIN, SRC_KLEIN)
        assert result == ("Klein", "Kernberg")

    def test_searles_vector(self):
        """Searles credited with Lichtenstein's force (the 'according to'
        holder — no attribution verb in the span at all)."""
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        result = detect_parenthetical_promotion(BULLET_SEARLES, SRC_SEARLES)
        assert result == ("Searles", "Lichtenstein")

    def test_correctly_attributed_bullet_not_vetoed(self):
        """A bullet for an author who IS the source's active subject stays."""
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        src = (
            "Mahler formulated the separation-individuation theory. "
            "Mahler's work provides the developmental framework for "
            "psychological birth. Mahler (1968, 1971, 1975) contributed to "
            "object relations theory."
        )
        b = "Mahler: Contributed to object relations theory and developmental models."
        assert detect_parenthetical_promotion(b, src) is None

    def test_non_name_bullet_ignored(self):
        from core.summarisation.postcheck_detectors import (
            detect_parenthetical_promotion,
        )

        b = "The chapter covers identity diffusion in borderline patients."
        assert detect_parenthetical_promotion(b, SRC_KHAN) is None

    def test_run_post_checks_drops_confirmed_promotion(self):
        """Pre-ship veto: a confirmed promotion bullet is dropped with a
        parenthetical_promotion fix issue."""
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            bullets=[BULLET_KHAN, "Erikson (1956) defined ego identity."],
            executive_summary="A summary.",
            thorough_summary="A thorough summary of the chapter.",
            source_text=SRC_KHAN,
        )
        assert all("Khan:" not in b for b in report.bullets)
        promos = [i for i in report.issues if i.detector == "parenthetical_promotion"]
        assert len(promos) == 1
        assert promos[0].severity == "fix"
        assert "Winnicott" in promos[0].detail

    def test_gap_fill_veto_wired_in_summarizer(self):
        """Regression pin: the V18.14.1 batch gap-fill must call the veto
        before appending (generation-time, not post-hoc).

        V18.20.3.12 (Phase 4 / W6-O5): the gap-fill loop moved VERBATIM from
        ``Summarizer._summarize_inner`` to ``gap_fill_batch.batch_gap_fill``
        — re-pointed at the new module; the pinned wiring is unchanged."""
        from pathlib import Path

        from core.summarisation import gap_fill_batch as gfb

        # V0.6.11 (B14-b) pin evolution: the pinned block moved VERBATIM into
        # the _gff_* phase helpers (called by batch_gap_fill — the B12
        # call-site-following precedent); anchoring on the whole module.
        src = Path(gfb.__file__).read_text(encoding="utf-8")
        assert "detect_parenthetical_promotion(" in src
        assert "GENERATION-TIME active-subject" in src

    def test_expanded_verb_list_catches_colon_forms(self):
        """The expanded _ATTRIB_VERBS list now catches the .3.1 gap-fill
        verbs ('Contributed', 'Identified', 'Made', …) in the STRICT
        same-verb flag detector when the source uses the same verb — the
        Klein paraphrase variant (bullet 'Contributed' vs source
        'formulated') is the RELAXED promotion detector's job (covered by
        test_klein_vector + the run_post_checks drop test)."""
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        # Same-verb colon form: bullet + source both use 'contributed'.
        src = (
            "By integrating the works of Klein (1948), Erikson (1950a,b), "
            "Jacobson (1964), and Mahler (1968, 1971, 1975) with his own "
            "views, Kernberg contributed the three-step formulation of "
            "identity formation."
        )
        bullet = (
            "Klein: Contributed the three-step formulation of identity "
            "formation by integrating his 1948 work into Kernberg's framework."
        )
        _, issues = detect_attribution_subject_swap(bullet, src, "bullet[0]")
        assert any("attribution_swap" in i.detector for i in issues), (
            "the 'Contributed' colon form must now be flagged (same-verb)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4) P1-b — post-gap-fill semantic dedup (source pin) + P1-c citation-only
# ═══════════════════════════════════════════════════════════════════════════


class TestPostGapFillDedup:
    def test_second_dedup_pass_wired(self):
        import inspect

        from core.summarisation.summarizer import Summarizer

        # V0.18 (Phase 5.1, step 1): the dedup pass moved VERBATIM to the
        # postchecks phase method.
        src = inspect.getsource(Summarizer._phase_postchecks_and_floors)
        assert "Post-gap-fill semantic dedup" in src
        assert "V18.20.3.2: Post-gap-fill semantic dedup" in src


class TestCitationOnlyFragment:
    def test_real_fragments_detected(self):
        from core.summarisation.post_processing import is_citation_only_fragment

        assert is_citation_only_fragment(FRAGMENT_FREUD)
        assert is_citation_only_fragment(FRAGMENT_CITATIONS)

    def test_real_claims_pass(self):
        from core.summarisation.post_processing import is_citation_only_fragment

        ok = [
            "Winnicott (1960) described the infant's spontaneous gestures as "
            "emanating from the true self.",
            "Kernberg (1967, 1976, 1980b) formulated a three-step process: "
            "introjection, identification, and identity formation.",
            "The chapter concludes by defining seven cross-sectional "
            "characteristics of a solid identity.",
        ]
        for b in ok:
            assert not is_citation_only_fragment(b), b

    def test_label_style_bullet_without_scaffolding_kept(self):
        """Calibration: a short no-predicate bullet WITHOUT citation or
        parenthetical scaffolding is a legitimate label bullet — kept (the
        drop targets citation-DOMINATED fragments only)."""
        from core.summarisation.post_processing import is_citation_only_fragment

        labels = [
            "A real bullet about identity formation.",
            "Erikson's stages of psychosocial development.",
            "Seven characteristics of solid identity.",
        ]
        for b in labels:
            assert not is_citation_only_fragment(b), b

    def test_classify_bullets_drops_fragments(self):
        from core.summarisation.post_processing import classify_bullets

        kept, drops = classify_bullets([FRAGMENT_FREUD, FRAGMENT_CITATIONS])
        assert kept == []
        stages = {d[1] for d in drops}
        assert "thinking_filter.citation_only" in stages

    def test_run_post_checks_drops_fragments(self):
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            bullets=[FRAGMENT_CITATIONS, "Erikson (1956) defined ego identity."],
            executive_summary="A summary.",
            thorough_summary="A thorough summary of the chapter.",
            source_text=SRC_KHAN,
        )
        assert all("Federn" not in b for b in report.bullets)
        assert any(i.detector == "citation_only" and i.severity == "fix" for i in report.issues)


# ═══════════════════════════════════════════════════════════════════════════
# 5) P1-d — 6144 caps + scholar truncated-verdict warning
# ═══════════════════════════════════════════════════════════════════════════


class TestTokenCaps:
    def test_consolidation_cap_6144(self):
        """The consolidation LLM call must use max_tokens=6144."""
        import inspect

        from core.summarisation.bullet_consolidation import consolidate_bullets

        src = inspect.getsource(consolidate_bullets)
        assert "max_tokens=6144" in src

    def test_scholar_cap_6144(self):
        import inspect

        from core.summarisation import scholar_reflection as sr

        # V0.6.10 (B12) pin evolution: the scholar LLM call site moved from
        # ``scholar_reflection``'s body into the ``_sr_call_llm`` phase
        # helper (god-function decomposition, AST-identity verified); the
        # 6144 contract itself is unchanged. Both the helper AND the
        # orchestrator's delegating body are pinned.
        src = inspect.getsource(sr._sr_call_llm)
        assert "max_tokens=6144" in src
        orch = inspect.getsource(sr.scholar_reflection)
        assert "_sr_call_llm(ctx)" in orch


class TestScholarTruncatedVerdict:
    def _run_scholar(self, raw_response, monkeypatch):
        logs = []

        captured = {}

        def fake_call_llm(prompt, temperature=0.7, max_tokens=4096, **kw):
            captured["max_tokens"] = max_tokens
            return raw_response

        def fake_strip_thinking(t):
            return t

        def fake_recover_vram(context="", delay_sec=0.0, **kw):
            pass

        class _PM:
            def render_template(self, *a, **k):
                return "PROMPT"

        from core.summarisation.scholar_reflection import scholar_reflection

        monkeypatch.setattr(
            "core.summarisation.scholar_reflection.scr_scholar_reflection", None, raising=False
        )
        result = {}
        # Call the module-level function directly with the fake deps.
        result["out"] = scholar_reflection(
            "Ch1",
            "Chapter text about identity. " * 40,
            {"bullet_points": ["a"], "executive_summary": "b", "thorough_summary": "c"},
            max_context_tokens=32768,
            language="en",
            temperature=0.7,
            prompt_manager=_PM(),
            recover_vram=fake_recover_vram,
            call_llm=fake_call_llm,
            strip_thinking=fake_strip_thinking,
            log=lambda msg, level="INFO": logs.append((level, msg)),
        )
        return logs, captured

    def test_truncated_no_gaps_verdict_qualified(self, monkeypatch):
        """A 'no significant gaps found' verdict from a response whose
        <gap_fill_bullets> section never closed must carry the VERDICT
        UNRELIABLE warning (the .3.1 failure mode)."""
        raw = "<scholar_reflections>\nnone\n<gap_fill_bullets>\n- a partial bullet that was cut mid"
        logs, captured = self._run_scholar(raw, monkeypatch)
        assert captured["max_tokens"] == 6144
        verdict_logs = [m for _, m in logs if "no significant gaps" in m]
        assert verdict_logs, "the verdict log must fire"
        assert any("VERDICT UNRELIABLE" in m for m in verdict_logs)
        assert any(level == "WARNING" for level, m in logs if "VERDICT UNRELIABLE" in m)

    def test_complete_no_gaps_verdict_clean(self, monkeypatch):
        """A well-formed complete response logs the plain verdict."""
        raw = (
            "<scholar_reflections>\nnone\n</scholar_reflections>\n"
            "<gap_fill_bullets>\nnone\n</gap_fill_bullets>"
        )
        logs, _ = self._run_scholar(raw, monkeypatch)
        verdict_logs = [m for _, m in logs if "no significant gaps" in m]
        assert verdict_logs
        assert not any("VERDICT UNRELIABLE" in m for m in verdict_logs)


# ═══════════════════════════════════════════════════════════════════════════
# 6) P1-e — additive retry-on-mass-drop
# ═══════════════════════════════════════════════════════════════════════════


class TestAdditiveRetryOnMassDrop:
    def _make_summarizer_stub(self, responses):
        from core.summarisation.summarizer import Summarizer

        s = Summarizer.__new__(Summarizer)
        logs = []
        s.log = lambda msg, level="INFO": logs.append((level, msg))
        s._logs = logs
        s.language = "en"
        s.temperature = 0.7
        s.primary_model = "test-model:latest"
        s.request = types.SimpleNamespace(
            summarisation_max_context_tokens=32768,
        )
        s._deadline_exceeded = lambda ctx: False

        class _PM:
            def render_template(self, *a, **k):
                return "ADDITIVE PROMPT"

            def load_prompt(self, name):
                return None

        s.prompt_manager = _PM()
        calls = {"n": 0}

        def fake_call(prompt, model=None, temperature=0.7, max_tokens=4096, **kw):
            i = min(calls["n"], len(responses) - 1)
            calls["n"] += 1
            return responses[i]

        s._call_llm_with_empty_retry = fake_call
        s._strip_thinking = lambda t: t
        return s, calls

    def test_mass_drop_triggers_retry_and_better_yield_wins(self):
        """First response: 5/6 lines truncated (>50%) → retry. The retry's
        complete output must replace the first attempt."""
        truncated_resp = (
            "<key_distinctions>\n"
            "- A complete distinction between introjection and identification that stands.\n"
            '- Truncated one that got cut (unmatched quote "\n'
            "- Another truncated line missing its contrast (unmatched\n"
            "- Third truncated line with no terminal punctuation at all here\n"
            "- Fourth truncated\n"
            "- Fifth (unclosed\n"
            "</key_distinctions>\n"
            "<theoretical_tensions>\n"
            "- A (cut\n"
            "</theoretical_tensions>"
        )
        good_resp = (
            "<key_distinctions>\n"
            "- Kernberg's distinction between introjection (affectively charged, "
            "unassimilated) and identification (role-oriented, deeper).\n"
            "- Chasseguet-Smirgel's distinction between the long path and the "
            "short path.\n"
            "</key_distinctions>\n"
            "<theoretical_tensions>\n"
            "- The tension between personal developmental origins and "
            "sociocultural determinants.\n"
            "- The tension between authenticity and the false self.\n"
            "</theoretical_tensions>"
        )
        s, calls = self._make_summarizer_stub([truncated_resp, good_resp])
        result = {}
        s._ensure_additive_sections("Ch1", "Chapter text. " * 50, result)
        assert calls["n"] == 2, "the mass-drop must trigger exactly one retry"
        assert "key_distinctions" in result and result["key_distinctions"]
        # The good attempt's complete line must be present.
        assert "Chasseguet-Smirgel" in result["key_distinctions"]
        assert any("mass-truncation" in m for _, m in s._logs)

    def test_no_retry_when_yield_healthy(self):
        """A healthy first response (no truncated lines) must not retry."""
        good_resp = (
            "<key_distinctions>\n"
            "- Kernberg's distinction between introjection and identification.\n"
            "</key_distinctions>\n"
            "<theoretical_tensions>\n"
            "- The tension between origins and determinants.\n"
            "</theoretical_tensions>"
        )
        s, calls = self._make_summarizer_stub([good_resp])
        result = {}
        s._ensure_additive_sections("Ch1", "Chapter text. " * 50, result)
        assert calls["n"] == 1, "no retry on healthy yield"
        assert "key_distinctions" in result


# ═══════════════════════════════════════════════════════════════════════════
# 7) P2-a — dropped-letter common-word stoplist
# ═══════════════════════════════════════════════════════════════════════════


class TestDroppedLetterStoplist:
    """The 8 ordinary words false-flagged in the .3.1 run are suppressed;
    the true positive ('emergs') still fires."""

    _SRC = (
        "loving rises states clarity using seen emerges identities "
        "psychoanalytic literature philosophy existential"
    )

    @pytest.mark.parametrize(
        "word",
        [
            "moving",
            "seven",
            "stages",
            "clarify",
            "fusing",
            "raising",
            "identifies",
        ],
    )
    def test_common_word_not_flagged(self, word):
        from core.summarisation.postcheck_detectors import (
            detect_dropped_letter_garble,
        )

        _, issues = detect_dropped_letter_garble(
            f"the {word} process", "test", source_text=self._SRC
        )
        assert not any(i.detail.startswith("likely garbled") for i in issues), (
            f"'{word}' is ordinary English — must not be flagged"
        )

    def test_true_positive_still_caught(self):
        """V18.20.3.4 (RC-3) → V0.03 (P0-1): 'emergs' is still caught — as a
        guarded auto-repair (severity='fix') when auto_repair=True, because
        'emerges' is the unique edit-distance-1 source candidate. Default
        remains flag-only (repair disabled until rig-validated)."""
        from core.summarisation.postcheck_detectors import (
            detect_dropped_letter_garble,
        )

        # V0.03 default: flag-only, text untouched.
        fixed, issues = detect_dropped_letter_garble(
            "the emergs process", "test", source_text=self._SRC
        )
        assert any(i.severity == "flag" for i in issues)
        assert "emergs" in fixed
        # Explicitly enabled: the guarded repair fires.
        fixed, issues = detect_dropped_letter_garble(
            "the emergs process", "test", source_text=self._SRC, auto_repair=True
        )
        assert any(i.severity == "fix" and "auto-repair" in i.detail for i in issues), (
            "the 'emergs' true positive must be caught (now as a repair)"
        )
        assert "emerges" in fixed

    def test_stem_lookup_ing_restores_e(self):
        """move→moving / fuse→fusing: the -ing strip must try stem+e."""
        from core.summarisation.postcheck_detectors import (
            _common_word_stem_in_stoplist,
        )

        assert _common_word_stem_in_stoplist("moving")
        assert _common_word_stem_in_stoplist("fusing")
        assert _common_word_stem_in_stoplist("raised")
        assert _common_word_stem_in_stoplist("stages")
        assert _common_word_stem_in_stoplist("identifies")
        assert not _common_word_stem_in_stoplist("emergs")


# ═══════════════════════════════════════════════════════════════════════════
# 8) P2-b — ego-ideal join guard + year-styling consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestEgoIdealJoinGuard:
    _SRC = (
        "the ego ideal is the heir of the Oedipus complex. Forming "
        "ego-ideal, temporal order from accepting chronological lag. "
        "Ego and ego ideal are fused."
    )

    def test_split_form_in_source_never_joined(self):
        """The .3.1 corruption: 'ego ideal' → 'egoideal' via a hyphenated
        occurrence inside the ±300 window. The GLOBAL veto must block it
        (the source uses the split form)."""
        from core.summarisation.postcheck_detectors import detect_extra_spaces

        txt = "The long path means accepting chronological lag, forming ego ideal, temporal order."
        cleaned, issues = detect_extra_spaces(txt, "test", source_text=self._SRC)
        assert "egoideal" not in cleaned
        assert not issues

    def test_genuine_split_word_still_joined(self):
        """The guard must not break the real fix class: 'the reby' →
        'thereby' when the source has the joined form and NOT the split
        form."""
        from core.summarisation.postcheck_detectors import detect_extra_spaces

        src = "the thereby principle holds throughout"
        txt = "the reby principle holds"
        cleaned, issues = detect_extra_spaces(txt, "test", source_text=src)
        assert "thereby" in cleaned
        assert any(i.detector == "extra_space" for i in issues)


class TestYearStylingConsistency:
    def test_single_year_styled(self):
        from core.pipeline.chapter_checkpoint import format_years

        out = format_years("Erikson (1956) wrote")
        assert "*1956*" in out  # V0.4.26: markdown italic, not <em>

    def test_multi_year_citation_styled(self):
        """The .3.1 inconsistency: '(1961, 1963)' shipped plain next to
        styled '(1956)'."""
        from core.pipeline.chapter_checkpoint import format_years

        out = format_years("Lichtenstein (1961, 1963) identifies")
        assert "*1961*" in out  # V0.4.26: markdown italic
        assert "*1963*" in out

    def test_year_letter_suffix_styled(self):
        """'(1950a, 1956)' — the 1950a letter-suffix form the old \\b regex
        missed."""
        from core.pipeline.chapter_checkpoint import format_years

        out = format_years("Erikson (1950a, 1956, 1958, 1959) resurrected")
        assert "*1950*a" in out  # V0.4.26: markdown italic; letter suffix stays adjacent
        assert "*1959*" in out

    def test_non_year_parens_untouched(self):
        from core.pipeline.chapter_checkpoint import format_years

        out = format_years("das Ich (das Ich, ego) remains")
        assert out == "das Ich (das Ich, ego) remains"

    def test_five_digit_runs_untouched(self):
        from core.pipeline.chapter_checkpoint import format_years

        out = format_years("item (19840) stays")
        assert "19840" in out and "<em" not in out


# ═══════════════════════════════════════════════════════════════════════════
# 9) P2-c — settings banner: keep_alive + presence_penalty
# ═══════════════════════════════════════════════════════════════════════════


class TestSettingsBanner:
    def _run(self, monkeypatch, ollama_show_output="PARAMETER presence_penalty 1.5"):
        from core.pipeline.conversion import settings_logger

        logs = []

        class _S:
            def get(self, key, default=None):
                if key == "llm.keep_alive":
                    return "30m"
                return default

        r = types.SimpleNamespace(
            input_path=Path("book.pdf"),
            source_type="normal_book",
            use_llm_ocr=True,
            force_ocr_all_pages=False,
            auto_detect_scanned=True,
            primary_ocr_model="m",
            ocr_retries=2,
            image_max_size=1200,
            page_range_start=None,
            page_range_end=None,
            selected_chapters=[],
            segment_strategy="auto",
            token_limit_per_segment=2000,
            enable_semantic_segmentation=True,
            page_group_size=10,
            generate_summaries=True,
            summarisation_model="Qwen3.8-27B:latest",
            # V0.6.14 (single-model order): the fast_model/heavy_model
            # stub fields REMOVED — settings_logger no longer reads them
            # (the "Fast model: ... / Heavy model: ..." banner line is
            # retired; one model does every LLM task).
            max_workers=1,
            temperature=0.7,
            self_consistency=False,
            coverage_threshold=0.85,
            academic_rigor=False,
            summarisation_max_context_tokens=32768,
            summarisation_max_output_tokens=8192,
            include_executive_summary=True,
            include_thorough_summary=True,
            include_keypoints=True,
            simplified_keypoints_enabled=False,
            generate_docx=True,
            output_briefing=False,
            output_podcast=False,
            output_tts=False,
            output_flashcards=False,
            output_obsidian=False,
            output_study_guide=False,
            output_social=False,
            output_mindmap=False,
        )
        paths = types.SimpleNamespace()
        ctx = {
            "request": r,
            "settings": _S(),
            "paths": paths,
            "output_dir": Path("."),
            "app_version": "test",
        }

        import core.llm.modelfile_integrity as mi

        monkeypatch.setattr(mi, "_run_ollama_show", lambda model: ollama_show_output)
        monkeypatch.setattr(settings_logger, "_run_ollama_show", mi._run_ollama_show, raising=False)

        # Neutralize the VRAM calc + network probes (not under test).
        monkeypatch.setattr("utils.network.is_ollama_reachable", lambda: True, raising=False)
        try:
            settings_logger.log_conversion_settings(ctx, lambda msg, level="INFO": logs.append(msg))
        except Exception:
            # The full banner has many optional sections; only the new
            # lines matter here — retry with a minimal ctx if extras fail.
            pass
        return logs

    def test_keep_alive_and_presence_penalty_logged(self, monkeypatch):
        logs = self._run(monkeypatch)
        assert any("Keep-alive: 30m" in m for m in logs)
        assert any("Presence penalty (Modelfile): 1.5" in m for m in logs)

    def test_missing_presence_penalty_warns(self, monkeypatch):
        logs = self._run(monkeypatch, ollama_show_output="PARAMETER temperature 0.7")
        assert any("Presence penalty" in m and "not set" in m for m in logs)

    def test_unreadable_modelfile_degrades(self, monkeypatch):
        logs = self._run(monkeypatch, ollama_show_output=None)
        assert any("Keep-alive" in m for m in logs)


# ═══════════════════════════════════════════════════════════════════════════
# 10) P2-d — thermal deadlock fix
# ═══════════════════════════════════════════════════════════════════════════


class TestThermalDeadlockFix:
    def test_budget_format_report_does_not_deadlock(self):
        """The .3.1 killer: format_report() nested the non-reentrant lock
        via the minutes_above_threshold property. Must complete (the test
        itself would hang before the RLock fix)."""
        from core.system.thermal_safety import ThermalBudget

        b = ThermalBudget()
        b.update(75, 1000.0)
        b.update(75, 1060.0)
        result = b.format_report()
        assert "Thermal budget" in result
        assert "within budget" in result

    def test_budget_format_report_in_thread_completes(self):
        """Full regression vector: call format_report from a worker thread
        and join with a timeout — pre-fix this deadlocks forever."""
        from core.system.thermal_safety import ThermalBudget

        b = ThermalBudget()
        b.update(80, 1000.0)
        out = {}

        def _worker():
            out["report"] = b.format_report()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=5.0)
        assert not t.is_alive(), "format_report deadlocked (non-reentrant lock)"
        assert "Thermal budget" in out["report"]

    def test_locks_are_reentrant(self):
        from core.system.thermal_safety import CooldownScheduler, ThermalBudget

        assert isinstance(ThermalBudget()._lock, type(threading.RLock()))
        assert isinstance(CooldownScheduler()._lock, type(threading.RLock()))

    def test_log_report_line_guards(self):
        """A failing sub-report must not kill the remaining lines."""
        from core.system.thermal_safety import ThermalSafetyController

        logs = []
        ts = ThermalSafetyController(
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        ts._start_time = 1000.0

        def _boom():
            raise RuntimeError("boom")

        ts._budget.format_report = _boom
        ts.log_report()
        msgs = [m for _, m in logs]
        assert any("Session duration" in m for m in msgs)
        assert any("Thermal budget report failed" in m for m in msgs)
        assert any("Cool-downs triggered" in m for m in msgs), (
            "the scheduler line must still print after the budget line fails"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 11) Regression vector bundle — the full .3.1 Key-Takeaways garbage set
# ═══════════════════════════════════════════════════════════════════════════


class TestFullRegressionVectorBundle:
    """All 7 shipped defects from the .3.1 run in one run_post_checks
    sweep: 2 self-talk + 2 fragments + 1 promotion are dropped; the 2
    legitimate bullets survive."""

    def test_garbage_set_dropped_legit_kept(self):
        from core.summarisation.postchecks import run_post_checks

        bullets = [
            FRAGMENT_FREUD,  # N5: no-predicate fragment
            FRAGMENT_CITATIONS,  # N5: citation dump
            SELF_TALK_1,  # N1: self-talk
            SELF_TALK_2,  # N1: self-talk
            BULLET_KHAN,  # N4: misattribution
            "Erikson (1956) defined ego identity as a persistent sameness within oneself.",  # legit
            "Kernberg formulated a three-step process of identity formation "
            "beginning with introjection.",  # legit
        ]
        report = run_post_checks(
            bullets=bullets,
            executive_summary="A summary of identity origins.",
            thorough_summary="A thorough summary of the chapter on identity.",
            source_text=SRC_KHAN + " " + SRC_KLEIN,
        )
        assert len(report.bullets) == 2
        joined = " | ".join(report.bullets)
        assert "Erikson" in joined and "Kernberg formulated" in joined
        detectors = {i.detector for i in report.issues}
        assert "self_talk" in detectors
        assert "citation_only" in detectors
        assert "parenthetical_promotion" in detectors
