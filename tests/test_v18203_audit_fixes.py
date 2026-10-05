"""V18.20.3.0 characterization tests — audit follow-up fixes.

Covers the two defect classes found by the first V18.20.2.0 real-rig
output audit (``audit/results/AUDIT_V18.20.2.0_001_1_identity.md``):

1. FLAG-02 — UNFLAGGED BULLET TRUNCATION: a Key-Takeaways bullet ended
   "…(4) role of aggression in self-delineation, and." with NO
   truncation_detected warning (A20 only fires on provider
   done_reason=length; the terminal period let it past every existing
   is_truncated signal). Fix: ``ends_on_dangling_word`` + the
   ``is_truncated`` extension (applies at classify_bullets pre-drop AND
   the post-consolidation flag in run_post_checks).

2. FLAG-01 — KHAN/WINNICOTT SUBJECT-SWAP MISATTRIBUTION: the bullet
   credited Khan with the developmental basis that the source credits to
   Winnicott (Khan cited only parenthetically as the coiner of
   "corporeality"). Invisible to F4 source-overlap + embedding judges by
   construction. Fix: ``detect_attribution_subject_swap``.

3. Coverage follow-up — QUOTE-ANCHOR PROMPT LINES (all three critical
   omissions were block quotes / enumerative conclusions).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager postchecks→…→core.pdf import chain loadable).
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════
# 1) Dangling-tail truncation guard (FLAG-02)
# ═══════════════════════════════════════════════════════════════════════════


class TestEndsOnDanglingWord:
    """V18.20.3.0: the final-word truncation signal."""

    def test_audit_flag02_bullet_is_truncated(self):
        """The EXACT Jacobson five-categories bullet from the real-rig audit."""
        from core.summarisation.post_processing import is_truncated

        bullet = (
            "Jacobson's schema spans five categories: (1) self and object "
            "representations, (2) affects, (3) early identifications, "
            "(4) role of aggression in self-delineation, and."
        )
        assert is_truncated(bullet) is True

    def test_common_dangling_tails(self):
        from core.summarisation.post_processing import is_truncated

        for tail in (
            "and.",
            "or.",
            "of.",
            "in.",
            "to.",
            "with.",
            "for.",
            "by.",
            "from.",
            "the.",
            "a.",
            "that.",
            "which.",
            "including.",
            "is.",
            "between.",
            "as.",
        ):
            bullet = f"The chapter situates the concept within a broader framework {tail}"
            assert is_truncated(bullet) is True, f"tail {tail!r} must be flagged"

    def test_short_dangling_tail_any_length(self):
        """Signal applies BELOW the 40-char gate — 'X and.' is never complete."""
        from core.summarisation.post_processing import is_truncated

        assert is_truncated("Erikson and.") is True
        assert is_truncated("the theory of.") is True

    def test_dangling_tail_behind_closing_quote_or_paren(self):
        from core.summarisation.post_processing import ends_on_dangling_word

        assert ends_on_dangling_word('…self-delineation, and)."') is True
        assert ends_on_dangling_word("…self-delineation, and.\u201d") is True

    @pytest.mark.parametrize(
        "bullet",
        [
            "Erikson defined ego identity as selfsameness and sharing of essential character with others.",
            "Freud (1926a)",
            "See above.",
            "The chapter concludes with seven characteristics of identity.",
            "Erikson dropped the ego prefix in part to accommodate Hartmann's differentiation.",
            "Kernberg wrote 'it is the presence or absence of identity diffusion' (p. 14).",
            # Elliptical-but-complete endings deliberately NOT flagged:
            "The evidence suggests so.",
            "He decided it did not.",
            "Kahn replied no.",
        ],
    )
    def test_complete_bullets_not_flagged(self, bullet):
        from core.summarisation.post_processing import is_truncated

        assert is_truncated(bullet) is False, f"false positive: {bullet!r}"

    def test_empty_and_whitespace(self):
        from core.summarisation.post_processing import ends_on_dangling_word

        assert ends_on_dangling_word("") is False
        assert ends_on_dangling_word("   ") is False
        assert ends_on_dangling_word("...") is False


class TestClassifyBulletsDropsDanglingTail:
    """The pre-consolidation drop path: classify_bullets → gap-fill re-adds."""

    def test_dangling_bullet_is_dropped_conservative_gated(self):
        from core.summarisation.post_processing import classify_bullets

        bullets = [
            "Erikson (1968) defined ego identity as selfsameness and shared essential character.",
            "Jacobson's schema spans five categories: (1) self representations, "
            "(2) affects, (3) identifications, (4) aggression in self-delineation, and.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert len(drops) == 1
        assert drops[0][2] and "truncat" in drops[0][2].lower()
        assert drops[0][3] is False  # conservative-gated (kept in conservative mode)


class TestPostConsolidationTruncationFlag:
    """run_post_checks flags the dangling tail post-consolidation (DEBT-07 path)."""

    def test_run_post_checks_flags_dangling_tail(self):
        from core.summarisation.postchecks import run_post_checks

        bullet = (
            "Jacobson's schema spans five categories: (1) self and object "
            "representations, (2) affects, (3) early identifications, "
            "(4) role of aggression in self-delineation, and."
        )
        report = run_post_checks([bullet], "Exec summary.", "Thorough summary.")
        trunc = [i for i in report.issues if i.detector == "truncated"]
        assert trunc, "dangling-tail bullet must be flagged post-consolidation"


# ═══════════════════════════════════════════════════════════════════════════
# 2) Attribution subject-swap detector (FLAG-01)
# ═══════════════════════════════════════════════════════════════════════════

_KHAN_BULLET = (
    "Khan's work provides the developmental basis for authenticity, "
    "'corporeality' as a deeply assimilated and personalized bodily "
    "foundation for self-experience, and the experience of temporal "
    "continuity in the self."
)
_WINNICOTT_SOURCE = (
    "Winnicott did not use the term identity but his views are of great "
    "significance. His work provides the developmental basis for "
    "(1) authenticity; (2) 'corporeality' (Khan 1983), or a deeply "
    "assimilated and personalized bodily foundation for one's "
    "self-experience; and (3) the experience of temporal continuity "
    "in the self."
)


class TestDetectAttributionSubjectSwap:
    def test_khan_winnicott_audit_case_flagged(self):
        """The EXACT FLAG-01 bullet + source from the real-rig audit."""
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        text, issues = detect_attribution_subject_swap(
            _KHAN_BULLET,
            _WINNICOTT_SOURCE,
            "bullet[0]",
            source_authors=["Winnicott", "Khan", "Erikson", "Jacobson"],
        )
        assert text == _KHAN_BULLET  # flag-only — text never modified
        assert len(issues) == 1
        assert issues[0].detector == "attribution_swap"
        assert issues[0].severity == "flag"
        assert "Khan" in issues[0].detail and "Winnicott" in issues[0].detail

    def test_correct_winnicott_attribution_not_flagged(self):
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        ok = (
            "Winnicott's work provides the developmental basis for "
            "authenticity and temporal continuity in the self."
        )
        _, issues = detect_attribution_subject_swap(
            ok,
            _WINNICOTT_SOURCE,
            "bullet[0]",
            source_authors=["Winnicott", "Khan"],
        )
        assert not issues

    def test_named_possessive_source_subject_flagged(self):
        """Source with EXPLICIT different-name subject: 'Blos's work provides…'"""
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        bullet = (
            "Khan's work provides the framework for understanding "
            "the false self and its defensive organisation."
        )
        source = (
            "Blos's work provides the framework for understanding "
            "the false self and its defensive organisation, a theme "
            "later extended (Khan 1983)."
        )
        _, issues = detect_attribution_subject_swap(
            bullet,
            source,
            "bullet[0]",
            source_authors=["Blos", "Khan"],
        )
        assert len(issues) == 1
        assert "Blos" in issues[0].detail

    def test_genuine_subject_outside_parens_not_flagged(self):
        """'Freud's (1923) work provides…' — Freud IS the subject (name
        outside the parenthetical year) → never flagged."""
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        source = (
            "Freud's (1923) work provides the structural model of "
            "the psyche for all later theorising about identity."
        )
        bullet = (
            "Freud's work provides the structural model of the "
            "psyche for all later theorising about identity."
        )
        _, issues = detect_attribution_subject_swap(
            bullet,
            source,
            "bullet[0]",
            source_authors=["Freud"],
        )
        assert not issues

    def test_genuine_subject_elsewhere_blocks_flag(self):
        """If ANY source region genuinely names the claimed author as an
        attributive subject, the flag is suppressed (escape hatch)."""
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        bullet = (
            "Khan's work provides the developmental basis for authenticity and temporal continuity."
        )
        source = (
            "Winnicott did not use the term. His work provides the "
            "developmental basis for authenticity and temporal continuity "
            "in the self (Khan 1983). "
            "Later, Khan's work provides an expanded account of the "
            "facilitating environment and its failures."
        )
        _, issues = detect_attribution_subject_swap(
            bullet,
            source,
            "bullet[0]",
            source_authors=["Winnicott", "Khan"],
        )
        assert not issues, f"escape hatch failed: {issues}"

    def test_no_pattern_no_flag(self):
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        plain = "The chapter surveys six sociocultural writers on identity."
        _, issues = detect_attribution_subject_swap(
            plain,
            _WINNICOTT_SOURCE,
            "exec",
            source_authors=["Khan"],
        )
        assert not issues

    def test_empty_inputs(self):
        from core.summarisation.postcheck_detectors import (
            detect_attribution_subject_swap,
        )

        assert detect_attribution_subject_swap("", "src", "x")[1] == []
        assert detect_attribution_subject_swap("text", "", "x")[1] == []

    def test_no_source_text_graceful(self):
        from core.summarisation.postchecks import run_post_checks

        # run_post_checks with source_text=None must not crash on the new detector
        report = run_post_checks([_KHAN_BULLET], "Exec.", "Thorough.")
        assert isinstance(report.issues, list)


class TestRunPostChecksIntegration:
    def test_khan_bullet_flagged_in_full_pipeline(self):
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            [_KHAN_BULLET],
            "Executive summary text.",
            "Thorough summary text.",
            source_text=_WINNICOTT_SOURCE,
        )
        swaps = [i for i in report.issues if i.detector == "attribution_swap"]
        assert len(swaps) == 1
        assert swaps[0].field == "bullet[0]"

    def test_thorough_summary_swap_flagged(self):
        from core.summarisation.postchecks import run_post_checks

        thorough = (
            "In the British tradition, the picture is different. "
            + _KHAN_BULLET
            + " This contrasts with the ego-psychological account."
        )
        report = run_post_checks(
            ["A correct bullet about Erikson (1950)."],
            "Executive summary.",
            thorough,
            source_text=_WINNICOTT_SOURCE,
        )
        swaps = [i for i in report.issues if i.detector == "attribution_swap"]
        assert any(i.field == "thorough" for i in swaps)


# ═══════════════════════════════════════════════════════════════════════════
# 3) Quote-anchor prompt lines (coverage follow-up)
# ═══════════════════════════════════════════════════════════════════════════


class TestQuoteAnchorPrompts:
    """All summary prompts carry the V18.20.3.0 quote-anchor instruction."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "prompts/default.md",
            "prompts/default_lowbit.md",
            "prompts/academic.md",
            "prompts/technical.md",
            "prompts/creative.md",
            "prompts/summarisation/thematic_synthesis.md",
            "prompts/summarisation/thematic_synthesis_lowbit.md",
        ],
    )
    def test_prompt_has_quote_anchor(self, relpath):
        p = PROJECT_ROOT / relpath
        assert p.exists(), f"missing prompt: {relpath}"
        text = p.read_text(encoding="utf-8")
        low = text.lower()
        assert "quote anchor" in low, f"{relpath} lacks the quote-anchor instruction"
        assert "block quot" in low, f"{relpath} must reference block quotations"
        assert "concluding" in low, f"{relpath} must reference concluding syntheses"

    def test_quote_anchor_is_genre_agnostic(self):
        """No book-specific fingerprint in the new instruction (A4 lesson)."""
        for relpath in ("prompts/default.md", "prompts/academic.md"):
            text = (PROJECT_ROOT / relpath).read_text(encoding="utf-8")
            anchor_block = text[text.lower().find("quote anchor") :]
            anchor_block = (
                anchor_block[: anchor_block.lower().find("**context")]
                if "**context" in anchor_block.lower()
                else anchor_block[:2000]
            )
            for banned in ("identity", "erikson", "ego", "adolescence", "winnicott"):
                assert banned not in anchor_block.lower(), (
                    f"{relpath}: quote-anchor block has book fingerprint {banned!r}"
                )
