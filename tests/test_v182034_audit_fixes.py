"""V18.20.3.4 (audit v182033) — characterization tests for the fix bundle.

Every fixture in this file is a REAL bullet or defect from the V18.20.3.3
golden-master run (audit/results/v182033_scorecard.md, section B2, F1-F8,
plus the post-check false positives from section B3). The tests pin the
exact behaviour the fix bundle was designed to produce:

  RC-1  process-scar quarantine (generation-time + ship-time)
  RC-2  post-gap-fill semantic dedup is no longer deadline-skippable
  RC-3  enforced truncation drop + unambiguous dropped-letter auto-repair
  RC-5a common-word whitelist suppresses the run's real FPs
  RC-5b multi-author citation extraction ("Hartmann, Kris, and Loewenstein
        (1946)" grounds Kris + Hartmann, not just Loewenstein)
  RC-5c borderline attribution band verifies named entities before flagging
"""

import pytest

from core.preprocessing.deterministic_analyzer import extract_citations
from core.summarisation.post_processing import (
    classify_bullets,
    classify_scar,
    ends_in_bare_ellipsis,
    has_truncation_marker,
    is_checklist_stub,
    is_label_stub,
    is_summary_self_assessment,
)
from core.summarisation.postcheck_detectors import (
    detect_dropped_letter_garble,
    verify_attribution,
)
from core.summarisation.postchecks import run_post_checks

# ═══════════════════════════════════════════════════════════════════════════
# Real fixtures — the 8 defective bullets of the V18.20.3.3 run (F1-F8)
# ═══════════════════════════════════════════════════════════════════════════

F1_SELF_REFERENTIAL = (
    "Roiphe (1971), Meyer (1980), and Stoller (1968, 1972) are identified in "
    "the source as significant contributors to gender identity "
    "consolidation, a topic the summary omits entirely: 'This specific "
    "area\u2026 Galenson and Ro."
)
F2_TRUNCATION_MARKER = (
    "For girl: final giving up of illusory penis, abandonment of "
    "narcissistic p\u2026 (text cuts off)"
)
F3_CHECKLIST = "Two directions - covered"
F4_CHECKLIST = "Federn, Glover, Spiegel - covered"
F5_LABEL = "Jacobson five categories"
F6_LABEL = 'Walt Whitman "Song of Myself" epigraph'
F7_TYPO_BULLET = (
    "Greenacre (1958) conceptualized the child as beginning to have a "
    "preliminary sense of identity in the phallic/edipal phase."
)
F7_TYPO_THOROUGH = (
    "The phallic/edipal phase saw the beginnings of a preliminary identity, "
    "and consolidation remained incomplete until adolescence resolution."
)
# F8 duplicates (dedup fixture): a gap-fill near-duplicate pair from that run
F8_DUP_A = (
    "Galenson and Roiphe: Made significant contributions to the specific "
    "area of gender identity consolidation."
)
F8_DUP_B = (
    "Meyer: Provided significant contributions to the specific area of "
    "gender identity consolidation."
)

GOOD_BULLETS = [
    "Tausk (1919) introduced the term identity into the psychoanalytic "
    "literature and asserted that man must, throughout life, constantly "
    "find and experience himself anew.",
    "Erikson defined ego identity as a persistent sameness within oneself "
    "and a persistent sharing of some kind of essential character with "
    "others.",
    "Mahler (1968) distinguished psychological birth from biological birth "
    "and described the separation-individuation process across five phases.",
]

# A source excerpt containing the exact vocabulary the fixes resolve against.
SOURCE_EXCERPT = (
    "It is in the phallic/oedipal phase that Greenacre conceptualized the "
    "child as beginning to have a preliminary sense of identity. The "
    "ego-psychology framework was consolidated by Hartmann, Kris, and "
    "Loewenstein (1946). Mahler described object constancy and the "
    "separation-individuation process. Galenson and Roiphe (1971) studied "
    "gender identity consolidation in early childhood. Jacobson and "
    "Kernberg (1967) later recognized these limitations."
)


# ═══════════════════════════════════════════════════════════════════════════
# RC-1 — classify_scar / scar predicates
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyScar:
    @pytest.mark.parametrize(
        "bullet,expected",
        [
            (F1_SELF_REFERENTIAL, "summary_self_assessment"),
            (F2_TRUNCATION_MARKER, "truncation_marker"),
            (F3_CHECKLIST, "checklist_stub"),
            (F4_CHECKLIST, "checklist_stub"),
            # En-dash / em-dash variants of the checklist idiom.
            ("Two directions \u2013 covered", "checklist_stub"),
            ("Two directions \u2014 covered", "checklist_stub"),
            (F5_LABEL, "label_stub"),
            (F6_LABEL, "label_stub"),
            ("The model was cut off mid-word here\u2026", "bare_ellipsis"),
            ("Some bullet ends abruptly...", "bare_ellipsis"),
        ],
    )
    def test_scar_classes_detected(self, bullet, expected):
        assert classify_scar(bullet) == expected

    @pytest.mark.parametrize(
        "bullet",
        GOOD_BULLETS
        + [
            # "covered" mid-sentence is fine — only the terminal idiom is a stub.
            "Erikson covered four connotations of ego identity in depth.",
            # A completed trailing quote is not a bare ellipsis.
            "Lichtenstein called it a \u2018destiny neurosis\u2019 capable of variation.",
        ],
    )
    def test_good_bullets_pass(self, bullet):
        assert classify_scar(bullet) is None

    def test_predicates_direct(self):
        assert is_checklist_stub("Tausk (1919) - covered")
        assert is_checklist_stub("Federn, Glover, Spiegel - covered")
        assert not is_checklist_stub("Federn, Glover, Spiegel covered ego nuclei.")
        assert is_summary_self_assessment("a topic the summary omits entirely")
        assert is_summary_self_assessment("the summary does not cover this")
        assert not is_summary_self_assessment("the summary covers Freud extensively.")
        assert has_truncation_marker("ends here (text cuts off)")
        assert not has_truncation_marker("a clean bullet about text.")
        assert ends_in_bare_ellipsis("cut off\u2026")
        assert not ends_in_bare_ellipsis("complete sentence.")
        assert is_label_stub(F5_LABEL)
        assert is_label_stub(F6_LABEL)
        # 9+ words without a verb is NOT a stub (rich enough to carry a topic)
        assert not is_label_stub(
            "ego identity versus existential identity and the identity principle"
        )

    def test_colon_ending_label_stub_v020(self):
        """V0.20 (Quality Campaign, audit V0.18 on the standing test
        chapter, Defect E): the <8-word filter let through label stubs
        that END WITH A COLON — they introduce sub-content (a list,
        sub-bullets) absent from the shipped set. Zero legitimate
        colon-ending bullets exist across all 6 golden fixtures (verified),
        so a shipped bullet ending with ':' is a label stub regardless of
        word count or verb presence."""
        # The V0.18 rig-run shapes (verbatim from the shipped summary):
        assert is_label_stub("Two conditions for ego organization and drive neutralization:")
        assert is_label_stub("Oedipal child has two routes:")
        # A verb-bearing colon-ender is still a label (the claim it
        # introduces — "the two routes are A and B" — is absent).
        assert is_label_stub("The author identified two main routes:")
        # A short colon-ender (above the 10-char floor) is a label.
        assert is_label_stub("Two routes:")
        # A completed sentence ending with a period is NOT a stub.
        assert not is_label_stub("The author identified two main routes clearly.")
        # A mid-colon bullet that does NOT end with a colon is not caught
        # by this detector (it's a different defect shape — out of scope
        # for this fix; the mid-colon + no-verb case is handled by the
        # <8-word + no-verb path when it's short enough).
        assert not is_label_stub(
            "Mahler (1968) distinguished psychological birth from biological birth."
        )


# ═══════════════════════════════════════════════════════════════════════════
# RC-1 layer 2 — classify_bullets drops the scar classes at generation time
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyBulletsScars:
    def test_generation_time_scar_drops(self):
        # Checklist stubs, self-assessment and truncation markers are
        # dropped at GENERATION time (they are structural self-reference,
        # never summary content).
        bullets = [
            F1_SELF_REFERENTIAL,
            F2_TRUNCATION_MARKER,
            F3_CHECKLIST,
            F4_CHECKLIST,
        ] + GOOD_BULLETS
        kept, drops = classify_bullets(bullets)
        kept_set = set(kept)
        for bad in (F1_SELF_REFERENTIAL, F2_TRUNCATION_MARKER, F3_CHECKLIST, F4_CHECKLIST):
            assert bad not in kept_set
        for good in GOOD_BULLETS:
            assert good in kept_set

    def test_label_stubs_are_ship_time_only(self):
        # By design (audit v182033 RC-1): the verbless-label class is
        # enforced at FINAL assembly (run_post_checks), not at generation
        # time — a short label in the generation stream is allowed to
        # exist until the quarantine removes it from the shipped set.
        kept, _ = classify_bullets([F5_LABEL, F6_LABEL])
        assert F5_LABEL in kept
        assert F6_LABEL in kept

    def test_scar_drops_are_always_drop(self):
        _, drops = classify_bullets([F3_CHECKLIST, F1_SELF_REFERENTIAL])
        stages = {d[1] for d in drops}
        assert "thinking_filter.checklist_stub" in stages
        assert "thinking_filter.summary_self_assessment" in stages
        assert all(d[3] is True for d in drops)  # always_drop=True


# ═══════════════════════════════════════════════════════════════════════════
# RC-1 layer 1 + RC-3 — ship-time quarantine in run_post_checks
# ═══════════════════════════════════════════════════════════════════════════


class TestShipTimeQuarantine:
    def test_scarred_bullets_dropped_at_ship_time(self):
        bullets = [
            F1_SELF_REFERENTIAL,
            F2_TRUNCATION_MARKER,
            F3_CHECKLIST,
            F4_CHECKLIST,
            F5_LABEL,
            F6_LABEL,
        ] + GOOD_BULLETS
        report = run_post_checks(
            bullets=bullets,
            executive_summary="A faithful executive summary.",
            thorough_summary="A faithful thorough summary with real content.",
            source_text=SOURCE_EXCERPT,
        )
        shipped = set(report.bullets)
        for bad in (
            F1_SELF_REFERENTIAL,
            F2_TRUNCATION_MARKER,
            F3_CHECKLIST,
            F4_CHECKLIST,
            F5_LABEL,
            F6_LABEL,
        ):
            assert bad not in shipped
        for good in GOOD_BULLETS:
            assert good in shipped
        detectors = {i.detector for i in report.issues}
        assert "scar_checklist_stub" in detectors
        assert "scar_summary_self_assessment" in detectors
        assert "scar_truncation_marker" in detectors
        assert "scar_label_stub" in detectors

    def test_truncated_bullet_enforced_drop(self):
        # F1's tail form: unmatched quote, no terminal punctuation.
        truncated = (
            "Roiphe (1971) are identified as significant "
            "contributors to gender identity: 'This specific area"
        )
        report = run_post_checks(
            bullets=[truncated] + GOOD_BULLETS,
            executive_summary="Exec.",
            thorough_summary="Thorough.",
            source_text=SOURCE_EXCERPT,
        )
        assert truncated not in set(report.bullets)
        trunc = [i for i in report.issues if i.detector == "truncated"]
        assert trunc and trunc[0].severity == "fix"

    def test_edipal_autorepaired_in_bullets_and_thorough(self):
        import re as _re

        report = run_post_checks(
            bullets=[F7_TYPO_BULLET] + GOOD_BULLETS,
            executive_summary="Exec.",
            thorough_summary=F7_TYPO_THOROUGH,
            source_text=SOURCE_EXCERPT,
            auto_repair_garble=True,  # V0.03 (P0-1): repair is opt-in now
        )
        joined = " ".join(report.bullets) + " " + report.thorough_summary
        assert "oedipal" in joined
        # The standalone "edipal" token is gone everywhere (word-boundary
        # check — "oedipal" contains the substring "edipal").
        assert not _re.search(r"(?<!\w)edipal(?!\w)", joined)
        fixes = [i for i in report.issues if i.detector == "dropped_letter" and i.severity == "fix"]
        assert fixes  # the repair is recorded


# ═══════════════════════════════════════════════════════════════════════════
# RC-3 — dropped-letter auto-repair unit behaviour
# ═══════════════════════════════════════════════════════════════════════════


class TestDroppedLetterAutoRepair:
    def test_edipal_repaired(self):
        import re as _re

        text = "The phallic/edipal phase is when the preliminary identity forms."
        # V0.03 (P0-1): auto_repair must be EXPLICITLY enabled (default off).
        fixed, issues = detect_dropped_letter_garble(
            text, "bullet[0]", SOURCE_EXCERPT, auto_repair=True
        )
        assert "oedipal" in fixed
        # Word-boundary check: "oedipal" contains the substring "edipal",
        # so assert the STANDALONE token is gone.
        assert not _re.search(r"(?<!\w)edipal(?!\w)", fixed)
        assert any(i.severity == "fix" and "oedipal" in i.detail for i in issues)

    def test_capitalized_garble_preserves_case(self):
        import re as _re

        text = "Edipal resolution begins in the phallic phase."
        # V0.03 (P0-1): auto_repair must be EXPLICITLY enabled (default off).
        fixed, issues = detect_dropped_letter_garble(
            text, "bullet[1]", SOURCE_EXCERPT, auto_repair=True
        )
        assert "Oedipal" in fixed
        assert not _re.search(r"(?<!\w)Edipal(?!\w)", fixed)

    def test_ambiguous_garble_stays_flag_only(self):
        # Both "emergs"-like candidates: build a source where two words are
        # each edit-distance-1 from the same non-word.
        src = "The process of emergence and emergence-like emergo traces."
        text = "The model described the emergx of identity."
        fixed, issues = detect_dropped_letter_garble(text, "bullet[2]", src)
        # Either repaired to a unique candidate or flagged — the contract is
        # that a unique candidate REPAIRS and multiple candidates FLAG.
        if fixed != text:
            assert any(i.severity == "fix" for i in issues)
        else:
            assert any(i.severity == "flag" for i in issues)

    @pytest.mark.parametrize(
        "word",
        [
            "psychoanalysis",
            "bases",
            "meant",
            "elated",
        ],
    )
    def test_audit_false_positives_suppressed(self, word):
        # RC-5a (V18.20.3.4) → V18.20.3.5: these words were suppressed by
        # HAND-ADDED STOPWORD ENTRIES in .3.4 — the exact chapter-derived
        # word-list tuning the user banned. The entries are REMOVED; the
        # suppression now comes from GENERAL MORPHOLOGY RULES
        # (_is_legitimate_inflection_pair rule 8: Greek -is/-es plurals;
        # rule 9: final-char inflection swap; position-0 inflected-form
        # guard for "elated"), so the same outcome holds with no
        # chapter-specific lexicon.
        src = (
            "The psychoanalysts worked on many bases of the mind and "
            "meant every word, speaking elatedly about means."
        )
        text = f"The summary mentions {word} in a sentence."
        fixed, issues = detect_dropped_letter_garble(text, "bullet[3]", src)
        assert fixed == text
        assert not [i for i in issues if i.detector == "dropped_letter"]

    def test_no_chapter_derived_stoplist_entries(self):
        # V18.20.3.5 POLICY (user rule): the .3.4 chapter-derived entries
        # must be GONE from the common-word stoplist. Domain words learned
        # from one book's audit ("psychoanalysis", "elated") and bare
        # inflections redundant with the stem lookup ("argues", "asserts",
        # "noted", "means") are forbidden; suppression must come from
        # morphology rules instead.
        from core.summarisation.postcheck_detectors import (
            _COMMON_ENGLISH_WORDS,
        )

        for banned in ("psychoanalysis", "elate", "elated", "argues", "asserts", "noted", "means"):
            assert banned not in _COMMON_ENGLISH_WORDS, (
                f"{banned!r} is a chapter-derived/redundant stoplist entry — "
                f"replace it with a morphology rule (user rule V18.20.3.5)"
            )

    def test_greek_plural_rule_generalizes(self):
        # The -is/-es rule is content-agnostic: it must suppress ANY
        # Greek-plural pair, including words never seen in any audit
        # (novel fixture — proves the rule is not a word list).
        from core.summarisation.postcheck_detectors import (
            _is_legitimate_inflection_pair as pair,
        )

        assert pair("diagnoses", "diagnosis")
        assert pair("crises", "crisis")
        assert pair("theses", "thesis")
        # and must NOT bless garbles of unrelated words
        assert not pair("Roippe", "Roiphe")
        assert not pair("edipal", "oedipal")
        assert not pair("emergs", "emerges")
        assert not pair("emergs", "emerge")  # 'e' excluded from rule 9


# ═══════════════════════════════════════════════════════════════════════════
# RC-5b — multi-author citation extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiAuthorCitations:
    def test_kris_grounded_via_three_author_form(self):
        # The audit's exact false positive: "Kris (1946) not found in
        # source's 34 citations" although the source cites
        # "Hartmann, Kris, and Loewenstein (1946)".
        names = {
            c["author"]
            for c in extract_citations(
                "The framework was consolidated by Hartmann, Kris, and "
                "Loewenstein (1946) and extended."
            )
        }
        assert {"Hartmann", "Kris", "Loewenstein"} <= names

    def test_and_pair_form(self):
        names = {
            c["author"]
            for c in extract_citations("Jacobson and Kernberg (1967) described the distinction.")
        }
        assert {"Jacobson", "Kernberg"} <= names

    def test_comma_list_without_and(self):
        names = {
            c["author"]
            for c in extract_citations(
                "Fromm, Wheelis, Lynd (1958) contributed to the sociocultural strand."
            )
        }
        assert {"Fromm", "Wheelis", "Lynd"} <= names

    def test_no_year_no_match(self):
        names = {
            c["author"]
            for c in extract_citations(
                "Freud, Abraham, and Jones wrote extensively without a year here."
            )
        }
        assert "Freud" not in names

    def test_single_author_forms_unchanged(self):
        names = {
            c["author"]
            for c in extract_citations(
                "Erikson (1956) wrote. Federn\u2019s (1952) concept. Freud 1926a. "
                "Chasseguet-Smirgel (1984) analyzed the ego ideal."
            )
        }
        assert {"Erikson", "Federn", "Freud", "Chasseguet-Smirgel"} <= names


# ═══════════════════════════════════════════════════════════════════════════
# RC-5c — borderline attribution band
# ═══════════════════════════════════════════════════════════════════════════


class TestBorderlineAttribution:
    def _make_source(self):
        return (
            "Mahler (1968) distinguished psychological birth from biological "
            "birth, describing the infant's gradual separation from the "
            "mother through the phases of separation-individuation, with "
            "object constancy as the culmination of the developmental "
            "sequence."
        )

    def test_entity_aligned_paraphrase_suppressed(self):
        # Same theorist + year, tight paraphrase: entities all present.
        source = self._make_source()
        text = (
            "Mahler (1968) separated psychological birth from the biological "
            "one, charting the infant's gradual detachment and the final "
            "attainment of object constancy across development."
        )
        _, issues = verify_attribution(text, source, "bullet[4]")
        attrib = [i for i in issues if i.detector == "attribution"]
        assert not attrib

    def test_wrong_author_claim_still_flagged(self):
        source = self._make_source()
        # Lexically distant from the source sentence, same author-year —
        # a fabricated claim that no paraphrase band can rescue.
        text = (
            "Mahler (1968) invented the primal cavity concept and argued "
            "that infants are born with a fully organized ego structure.",
        )
        text = text[0]
        _, issues = verify_attribution(text, source, "bullet[5]")
        attrib = [i for i in issues if i.detector == "attribution"]
        assert attrib


# ═══════════════════════════════════════════════════════════════════════════
# RC-2 — post-gap-fill dedup no longer deadline-gated (source-level pins)
# ═══════════════════════════════════════════════════════════════════════════


class TestDedupNotSkippable:
    def test_deadline_gate_removed_from_source(self):
        # The old code skipped the post-gap-fill dedup when the chapter
        # deadline was exceeded. V18.20.3.4 (RC-2) removed that gate: the
        # pass costs ~1-2s with batch encode and is the ONLY dedup that
        # runs after the gap-fill rounds. Pin the source-level contract.
        import inspect

        from core.summarisation import summarizer as sm

        # V0.18 (Phase 5.1, step 1): the dedup pass moved VERBATIM to the
        # postchecks phase method (chapter_phases mixin).
        src = inspect.getsource(sm.Summarizer._phase_postchecks_and_floors)
        assert "skipping optional phase: post-gap-fill semantic dedup" not in src
        assert src.count("Post-gap-fill semantic dedup crashed") == 1
        # the call itself remains, inside a non-gated try/except
        # (V0.5.18: the call now also passes the author-coverage veto's
        # kwargs — source roster + context + source text)
        assert "_semantic_dedup_bullets(" in src
        assert "source_author_surnames(content)" in src

    def test_gap_fill_loop_has_veto_accounting(self):
        # RC-4: the loop must track per-author vetoes, switch to
        # mention-only after two vetoes, and give up when that fails.
        # V18.20.3.12 (Phase 4 / W6-O5): the loop moved VERBATIM from
        # Summarizer._summarize_inner to gap_fill_batch.batch_gap_fill —
        # re-pointed at the new module (Summarizer passes its judge locals
        # _analysis/_det_authors/_missing in as explicit parameters).
        import inspect

        from core.summarisation import gap_fill_batch as gfb

        src = inspect.getsource(gfb.batch_gap_fill)
        assert "_veto_counts" in src
        assert "_mention_only" in src
        assert "_given_up" in src
        assert "MENTION-ONLY authors" in src
        assert "No actionable authors left" in src

    def test_recall_floor_probe_present(self):
        # RC-6 (V18.20.3.4) → V18.20.3.5: the probe moved from inline code
        # (which crashed invisibly on the rig — tuple .lower()
        # AttributeError swallowed by logger.debug) to a dedicated,
        # unit-tested module with a visible-failure contract.
        import inspect

        from core.summarisation import summarizer as sm
        from core.summarisation.recall_floor import (
            deterministic_recall_floor,
        )

        # V0.18 (Phase 5.1, step 1): the probe call moved VERBATIM to the
        # postchecks phase method (chapter_phases mixin).
        src = inspect.getsource(sm.Summarizer._phase_postchecks_and_floors)
        assert "Deterministic recall floor" in src
        assert "deterministic_recall_floor" in src
        # The dedicated module exists and handles the (number, text) tuples
        # that killed the inline version. (Source must be >= 200 chars —
        # detect_enumerated_conclusions short-circuits on shorter text, and
        # it focuses on the last 30% where conclusions live.)
        _src = (
            "Background paragraph with enough ordinary prose to pass the "
            "two-hundred character minimum of the conclusion detector. "
            "It mentions nothing numbered at all, just filler text. "
            "Now the conclusion: (1) first item here (2) second item "
            "follows (3) third item ends."
        )
        rf = deterministic_recall_floor(
            "",
            ["bullet one"],
            "thorough text",
            _src,
        )
        assert rf["conclusion_items_total"] == 3
        assert isinstance(rf["log_parts"], list)


# ═══════════════════════════════════════════════════════════════════════════
# RC-1 layer 2 — scholar-reflection gap-fill filter wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestScholarGapFillFilter:
    @staticmethod
    def _fake_prompt_manager():
        class _PM:
            def render_template(self, name, **kw):
                return "PROMPT BODY"

        return _PM()

    def test_filter_callback_wired(self):
        import inspect

        from core.summarisation import scholar_reflection as sr

        sig = inspect.signature(sr.scholar_reflection)
        assert "filter_thinking_bullets" in sig.parameters
        sig2 = inspect.signature(sr.scholar_reflection_gapfill_only)
        assert "filter_thinking_bullets" in sig2.parameters

    def test_gap_bullets_filtered_before_merge(self):
        from core.summarisation.scholar_reflection import scholar_reflection

        result = {"bullet_points": list(GOOD_BULLETS)}
        raw_llm = (
            "<scholar_reflections>\n- gap noted\n</scholar_reflections>\n"
            "<gap_fill_bullets>\n"
            f"- {F3_CHECKLIST}\n"
            f"- {GOOD_BULLETS[0]}\n"
            "</gap_fill_bullets>"
        )

        def fake_llm(prompt, **kw):
            return raw_llm

        logs = []
        scholar_reflection(
            "Chapter",
            SOURCE_EXCERPT,
            result,
            max_context_tokens=4096,
            language="English",
            temperature=0.7,
            prompt_manager=self._fake_prompt_manager(),
            recover_vram=lambda **kw: None,
            call_fast_llm=fake_llm,
            strip_thinking=lambda s: s,
            filter_thinking_bullets=lambda bs, **kw: [
                b for b in bs if classify_scar(b) is None and len(b.split()) >= 4
            ],
            log=lambda m, l="INFO": logs.append((m, l)),
        )
        # The checklist stub must NOT have merged; the good bullet may
        # (subject to the module's own grounding checks).
        merged = result.get("bullet_points", [])
        assert all(F3_CHECKLIST not in b for b in merged)

    def test_filter_optional_backward_compatible(self):
        # Omitting the callback keeps the pre-V18.20.3.4 behaviour.
        from core.summarisation.scholar_reflection import scholar_reflection

        result = {"bullet_points": []}
        raw_llm = (
            "<scholar_reflections>\nnone\n</scholar_reflections>\n"
            "<gap_fill_bullets>\nnone\n</gap_fill_bullets>"
        )
        scholar_reflection(
            "Chapter",
            "source text",
            result,
            max_context_tokens=4096,
            language="English",
            temperature=0.7,
            prompt_manager=self._fake_prompt_manager(),
            recover_vram=lambda **kw: None,
            call_fast_llm=lambda prompt, **kw: raw_llm,
            strip_thinking=lambda s: s,
            log=lambda m, l="INFO": None,
        )
        assert result["bullet_points"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Keypoints embedder log honesty (non-defect note from the audit)
# ═══════════════════════════════════════════════════════════════════════════


class TestKeypointsLogHonesty:
    def test_log_names_actual_backend(self):
        import inspect

        from core.summarisation import keypoints_builder as kb

        src = inspect.getsource(kb)
        assert "sentence-transformers loaded (shared singleton)" not in src
        assert "backend=" in src
