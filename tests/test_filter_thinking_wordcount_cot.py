"""V18.19.2.1 (Audit Fix 1): characterization tests for the new CoT-leak surface
forms discovered in the V18.19.2.0 audit.

The V18.19.2.0 audit (audit/results/audit_V18.19.2.0_2026-08-28.md) found that
45% of the delivered Key Takeaways bullets were the model's INTERNAL reasoning
in surface forms the existing thinking_filter did NOT catch:

  1. Word-count annotations: ``"..." = 23 words - TOO LONG. Need to split.``
  2. Word-count + checkmark: ``"..." = 17 ✓ (Wait, use "emerges" not "emergs")``
  3. ``Let me split:`` continuation markers
  4. Self-instruction lines: ``Using the chapter's own terminology``,
     ``Preserving all named contributors``, ``Preserve technical terminology``
  5. Bare validation checkmarks: ``Erikson (1950) ✓``, ``Greenacre (1958a) ✓``
  6. Self-correction parentheticals: ``(Wait, ...)``

These tests lock the new patterns so a future refactor cannot regress them.
Each test feeds the EXACT leaked line from the audit through classify_bullets
and asserts it's dropped with the correct stage.

Run: ``pytest tests/test_filter_thinking_wordcount_cot.py -v``
"""

from __future__ import annotations

import sys
import types

import pytest

# Minimal heavy-dep stub (tiktoken only) — matches test_anti_hallucination.py
if "tiktoken" not in sys.modules:
    _tk = types.ModuleType("tiktoken")
    _tk.get_encoding = lambda *a, **k: None
    _tk.encoding_for_model = lambda *a, **k: None
    _tk.Encoding = type("Encoding", (), {})
    sys.modules["tiktoken"] = _tk

from core.summarisation.post_processing import classify_bullets

# ═══════════════════════════════════════════════════════════════════════════
# 1. Word-count CoT annotations (the "= N words - TOO LONG" surface form)
# ═══════════════════════════════════════════════════════════════════════════


class TestWordCountCotAnnotation:
    """Bullets ending in '= N words - TOO LONG' / '= N - borderline' are CoT."""

    def test_too_long_annotation_dropped(self):
        bp = (
            '"Erikson identified four connotations: conscious sense of '
            "individual identity, unconscious striving for continuity, "
            "criterion for ego synthesis, and inner solidarity with group "
            'ideals." = 23 words - TOO LONG. Need to split.'
        )
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        assert drops[0][1] == "thinking_filter.word_count_cot"
        assert drops[0][3] is True  # always_drop

    def test_borderline_no_unit_dropped(self):
        bp = (
            '"Winnicott did not use the term identity specifically, but his '
            "views provide developmental basis for authenticity, corporeality, "
            'and temporal continuity." = 20 - borderline. Let me split:'
        )
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        stages = {d[1] for d in drops}
        # Either word_count_cot or let_me_split catches it (both match).
        assert stages & {"thinking_filter.word_count_cot", "thinking_filter.let_me_split"}

    def test_word_count_with_chars_unit(self):
        bp = '"Some quote." = 200 chars - too long.'
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        assert drops[0][1] == "thinking_filter.word_count_cot"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Word-count + checkmark (the "= N ✓" surface form)
# ═══════════════════════════════════════════════════════════════════════════


class TestWordCountCheckmark:
    """Bullets ending in '= N ✓ (Wait, ...)' are CoT self-verification."""

    def test_word_count_checkmark_dropped(self):
        bp = (
            '"Self-constancy—a stable sense of unique personhood—emergs at '
            'approximately two years, when the rapprochement subphase ends." '
            '= 17 ✓ (Wait, use "emerges" not "emergs")'
        )
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        stages = {d[1] for d in drops}
        assert stages & {"thinking_filter.word_count_checkmark", "thinking_filter.self_correction"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Self-instruction lines
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfInstruction:
    """Standalone self-instruction lines are model strategy notes, not content."""

    @pytest.mark.parametrize(
        "line",
        [
            "Using the chapter's own terminology",
            "Preserving all named contributors",
            "Preserve technical terminology",
            "Preserving all named authors",
            "Using the source's own vocabulary",
        ],
    )
    def test_self_instruction_dropped(self, line):
        kept, drops = classify_bullets([line], concepts=[], source_text="")
        assert len(kept) == 0, f"Should drop: {line!r}"
        assert drops[0][1] == "thinking_filter.self_instruction"
        assert drops[0][3] is True  # always_drop


# ═══════════════════════════════════════════════════════════════════════════
# 4. Bare validation checkmark lines
# ═══════════════════════════════════════════════════════════════════════════


class TestBareCheckmark:
    """Lines ending in an isolated ✓ are the model's validation checklist."""

    @pytest.mark.parametrize(
        "line",
        [
            "Erikson (1950) ✓",
            "Erikson (1958) ✓",
            "Jacobson (1964) ✓",
            "Greenacre (1958a) ✓",
            "Stoller (1968) ✓",
            "Erikson (1950) ✓ (mentioned in context of resurrecting the term)",
        ],
    )
    def test_bare_checkmark_dropped(self, line):
        kept, drops = classify_bullets([line], concepts=[], source_text="")
        assert len(kept) == 0, f"Should drop: {line!r}"
        assert drops[0][1] == "thinking_filter.bare_checkmark"
        assert drops[0][3] is True  # always_drop


# ═══════════════════════════════════════════════════════════════════════════
# 5. Let-me-split continuation markers
# ═══════════════════════════════════════════════════════════════════════════


class TestLetMeSplit:
    def test_let_me_split_dropped(self):
        # A bullet with "Let me split" but WITHOUT a word-count annotation
        # (so word_count_cot doesn't fire first) must be caught by let_me_split.
        bp = "Some bullet text. Let me split: part one, part two."
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        assert drops[0][1] == "thinking_filter.let_me_split"
        assert drops[0][3] is True  # always_drop

    def test_let_me_split_combined_with_word_count_also_dropped(self):
        # The combined form "= 20 - borderline. Let me split:" — word_count_cot
        # fires first (correctly) and the bullet is dropped. Either stage is fine.
        bp = (
            '"Blos outlined three areas: second individuation in adolescence, '
            "consolidation of sexual identity, and biphasic resolution of the "
            'Oedipus complex." = 20 - borderline. Let me split:'
        )
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        stages = {d[1] for d in drops}
        # Either pattern catches it — the requirement is that it's dropped.
        assert stages & {"thinking_filter.let_me_split", "thinking_filter.word_count_cot"}


# ═══════════════════════════════════════════════════════════════════════════
# 6. Self-correction parentheticals
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfCorrectionParen:
    def test_wait_paren_dropped(self):
        bp = 'Some text (Wait, use "emerges" not "emergs")'
        kept, drops = classify_bullets([bp], concepts=[], source_text="")
        assert len(kept) == 0
        assert drops[0][1] == "thinking_filter.self_correction"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Regression guard: real content bullets must NOT be dropped by the new patterns
# ═══════════════════════════════════════════════════════════════════════════


class TestRealContentNotDropped:
    """The new patterns must not false-positive on legitimate summary bullets."""

    @pytest.mark.parametrize(
        "bp",
        [
            "Tausk introduced the term identity into psychoanalytic literature.",
            "Erikson defined ego identity as persistent sameness within oneself.",
            "Winnicott distinguished the true self from the false self.",
            "Kernberg formulated a three-step process of identity formation.",
            "The chapter defines seven characteristics of solid identity.",
        ],
    )
    def test_real_content_kept(self, bp):
        # source_text contains the years so numeric_verify passes
        source = (
            "Tausk 1919 Erikson 1956 Winnicott Kernberg three-step "
            "seven characteristics solid identity"
        )
        kept, drops = classify_bullets(
            [bp], concepts=["identity", "ego", "self"], source_text=source
        )
        # The new word-count/self-instruction/checkmark patterns must NOT fire.
        new_stages = {
            "thinking_filter.word_count_cot",
            "thinking_filter.word_count_checkmark",
            "thinking_filter.let_me_split",
            "thinking_filter.self_correction",
            "thinking_filter.self_instruction",
            "thinking_filter.bare_checkmark",
        }
        fired = {d[1] for d in drops} & new_stages
        assert not fired, f"New pattern false-positive on real content: {fired}"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Full V18.19.2.0 audit regression: all 24 leaked lines caught
# ═══════════════════════════════════════════════════════════════════════════


class TestFullAuditLeakedSet:
    """The exact 24 leaked lines from the V18.19.2.0 audit must ALL be dropped."""

    LEAKED = [
        '"Erikson identified four connotations: conscious sense of individual identity, unconscious striving for continuity, criterion for ego synthesis, and inner solidarity with group ideals." = 23 words - TOO LONG. Need to split.',
        '"Self-constancy—a stable sense of unique personhood—emergs at approximately two years, when the rapprochement subphase ends." = 17 ✓ (Wait, use "emerges" not "emergs")',
        '"Winnicott did not use the term identity specifically, but his views provide developmental basis for authenticity, corporeality, and temporal continuity." = 20 - borderline. Let me split:',
        '"The second step involves less concrete, role-oriented internalization of significant others; identifications sit deeper in the self-system than introjects." = 20 - borderline. Let me split:',
        '"Sexual union demonstrates both forces at work, requiring one to become an instrument for another\'s needs while surrendering identity altogether." = 21 - borderline. Let me split:',
        '"He gave equal importance to somatic foundations and identifications in ego origin, calling the body image fundamental for ego development." = 20 - borderline. Let me split:',
        '"A good enough mother enables the infant\'s true self to have life; failure produces a compliant but inauthentic false self." = 20 - borderline. Let me split:',
        '"Blos outlined three areas: second individuation in adolescence, consolidation of sexual identity, and biphasic resolution of the Oedipus complex." = 20 - borderline. Let me split:',
        "Using the chapter's own terminology",
        "Preserving all named contributors",
        "Preserve technical terminology",
        "Erikson (1950) ✓",
        "Erikson (1958) ✓",
        "Jacobson (1964) ✓",
        "Mahler (1958) ✓",
        "Eissler (1958) ✓",
        "Kernberg (1967) ✓",
        "Wheelis (1958) ✓",
        "Lifton (1971) ✓",
        "Lichtenstein (1961) ✓",
        "Fenichel (1937) ✓",
        "Spiegel (1959) ✓",
        "Greenacre (1958a) ✓",
        "Stoller (1968) ✓",
    ]

    def test_all_24_leaked_lines_dropped(self):
        kept, drops = classify_bullets(self.LEAKED, concepts=[], source_text="")
        # Every leaked line must be dropped (kept must be empty).
        assert len(kept) == 0, f"{len(kept)} leaked lines survived filtering: {kept!r}"
        assert len(drops) == len(self.LEAKED), (
            f"Expected {len(self.LEAKED)} drops, got {len(drops)}"
        )
        # All drops must be always_drop=True (structural contamination).
        not_always = [d for d in drops if not d[3]]
        assert not not_always, f"These leaked lines were gated (not always_drop): {not_always!r}"
