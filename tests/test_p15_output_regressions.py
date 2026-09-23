"""P1.5-b (V0.07) — Output-quality regression fixes: MarkItDown V18 -> Elixir V0.06.

Pins the RESTORED V18 behavior for the three user-reported regressions:

(a) BULLET COLLAPSE — the same chapter that generated 30-40+ bullets in
    MarkItDown V18 produced ~3 in V0.06. Root cause: length_policy's
    ``W/50`` bullet density (V0.05, commit 0bb605a) plus the ship-time hard
    cap. Fix: ``BULLET_WORDS_PER_TAKEAWAY`` 50 -> 25 (a 1000-word chapter
    targets 27-40 again; tiny rig chapters still scale down).

(b) THIN THOROUGH SUMMARY — V18's "800-1200 word" contract became
    ``0.45 x W`` (a 1000-word chapter: "270-450 words"), the expansion floor
    followed the scaled lo, and F1 TRUNCATED a well-written 800-word
    thorough to 563. Fix: two regimes — sources >= 800 words get V18's
    800-word floor (growing to 1200); smaller sources keep the 97-Things
    anti-padding rule. F1 caps return to the historical 1500/400 for normal
    chapters. The dedicated-expansion trigger is 800 words again.

(c) PARAGRAPH-AS-CHAPTER-HEADLINE — a PDF-glued
    "Chapter 1 Identity Diffusion <first paragraph…>" line became the
    chapter headline. Root cause: V0.02's selection TOC filter could shrink
    the TOC to 1 entry, which disabled ALL THREE TOC segmentation
    strategies (each requires >= 2 entries) and cascaded to heading-based
    segmentation, whose uncapped "Chapter N <Title>" pattern matched the
    glued line. Fixes: < 2 surviving TOC entries -> return the FULL TOC;
    > 120-char lines are never chapter boundaries; normalized headings cap
    at the first sentence / 80 chars; the chapter-keyword heading test is
    start-anchored.

Run: pytest tests/test_p15_output_regressions.py -v
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# markitdown is not installed in this sandbox; the core.segmentation import
# chain (package __init__ -> segmenter -> core.pdf.adaptive_toc) needs it.
# Same stub pattern as tests/test_v003_rig_audit_fixes.py.
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = type("MarkItDown", (), {})
    sys.modules["markitdown"] = _md


# ════════════════════════════════════════════════════════════════════════════
# (a) Bullet collapse — V18 richness restored for normal chapters
# ════════════════════════════════════════════════════════════════════════════


class TestBulletCollapseFix:
    def test_normal_chapter_targets_v18_range(self):
        """A 1000-word chapter must target 27-40 bullets (V18 delivered
        30-40; V0.05's W/50 capped it at 20 — the user-reported collapse)."""
        from core.summarisation.length_policy import bullet_target

        for w in (1000, 1500, 2000, 3000, 20000):
            lo, hi = bullet_target(w)
            assert hi == 40, f"W={w}: hi must be 40, got {hi}"
            assert lo >= 27, f"W={w}: lo must be >= 27 (V18 parity), got {lo}"

    def test_mid_chapter_not_collapsed(self):
        """A 600-word chapter targets 16-24 — dense, not the V0.05 8-12."""
        from core.summarisation.length_policy import bullet_target

        lo, hi = bullet_target(600)
        assert (lo, hi) == (16, 24), f"600-word chapter: got {lo}-{hi}"

    def test_tiny_fragment_still_scales_down(self):
        """The 97-Things anti-padding intent survives: a 150-word fragment
        targets 4-6, never V18's unconditional 20-40."""
        from core.summarisation.length_policy import bullet_target

        lo, hi = bullet_target(150)
        assert lo >= 4 and hi <= 6, f"150-word fragment: got {lo}-{hi}"

    def test_ship_cap_removed_for_all_chapters(self):
        """V0.4.23 (user directive — bullets "can be as long as necessary
        for full coverage"): there is NO bullet cap. The historical V0.06
        source-scaled cap displaced coverage-critical bullets in the
        V0.4.22 ch.4 run; dedup/consolidation/filler-floor are the only
        reducers now."""
        from core.summarisation.length_policy import bullet_cap

        assert bullet_cap(1000) == 0, "no cap for normal chapters"
        assert bullet_cap(441) == 0, "no cap for rig-sized chapters"
        assert bullet_cap(20000) == 0, "no cap for huge chapters"

    def test_length_budget_block_states_no_maximum(self):
        """V0.4.23: the prompt block states the coverage FLOOR with NO
        MAXIMUM and the no-fragment/no-pad rule."""
        import re

        from core.summarisation import length_policy as lp

        block = lp.length_budget_block(1000, include_executive=False, include_thorough=False)
        assert "NO MAXIMUM" in block, f"no-maximum phrase missing:\n{block}"
        assert re.search(r"at least \d+ bullets", block), block
        assert "Never fragment or" in block


# ════════════════════════════════════════════════════════════════════════════
# (b) Thin thorough summary — V18's 800-word contract restored
# ════════════════════════════════════════════════════════════════════════════


class TestThinThoroughFix:
    def test_normal_chapters_get_v18_contract(self):
        """W >= 800: the thorough target must be at least 800 words (V18
        demanded "800-1200"; V0.05 told a 1000-word chapter "270-450").
        V0.4.23: the 1200 ceiling is REMOVED — the target scales with the
        source (0.45x, floored at 800)."""
        from core.summarisation.length_policy import thorough_target

        cases = {
            800: (480, 800),
            1000: (480, 800),
            1780: (481, 801),
            3000: (810, 1350),
            10000: (2700, 4500),
        }
        for w, (lo_exp, hi_exp) in cases.items():
            lo, hi = thorough_target(w)
            assert (lo, hi) == (lo_exp, hi_exp), (
                f"W={w}: expected ({lo_exp}, {hi_exp}), got ({lo}, {hi})"
            )

    def test_small_sources_keep_antipadding(self):
        """The 97-Things rig fix survives: 321-441-word chapters are targeted
        at ~45% of their length, never 800-1200."""
        from core.summarisation.length_policy import thorough_target

        for w in (321, 340, 430, 441):
            _lo, hi = thorough_target(w)
            assert hi <= 220, f"W={w}: rig regime must stay <= 220, got {hi}"
            assert hi <= w, f"W={w}: never above the source"

    def test_f1_thorough_cap_scales_uncapped(self):
        """V0.4.23 (user directive): F1's thorough truncation backstop
        scales with the source (1.25x the scaled target) — the absolute
        1500-word pass-line is REMOVED (a thorough summary may be as long
        as full coverage requires). The exec keeps its 400 pass-line (the
        executive is a compression artifact by design)."""
        src = (_project_root / "core" / "summarisation" / "bullet_pipeline.py").read_text(
            encoding="utf-8"
        )
        assert "_thorough_cap = int(_thi * 1.25) + 1" in src, (
            "F1 thorough cap must scale with the target (no absolute 1500)"
        )
        assert "_thorough_cap = 1500" not in src, "the 1500 pass-line is removed"
        assert "if _ehi >= 200:" in src, "F1 exec cap must be regime-split"
        assert "_exec_cap = 400" in src, "V18 exec pass-line restored"

    def test_expansion_threshold_restored(self):
        """The dedicated thorough expansion must fire below 800 words for
        normal chapters (V18's contract), not below the scaled lo (270)."""
        # V0.18 (Phase 5.1): moved VERBATIM to chapter_phases.py — pin follows.
        src = (_project_root / "core" / "summarisation" / "chapter_phases.py").read_text(
            encoding="utf-8"
        )
        assert "(800 if _th_hi_lp >= 800 else _th_lo_lp)" in src, (
            "the expansion threshold must be regime-split (V18: 800)"
        )


# ════════════════════════════════════════════════════════════════════════════
# (c) Paragraph-as-chapter-headline — segmentation guards
# ════════════════════════════════════════════════════════════════════════════


def _make_segmenter():
    from core.segmentation.heading_segmenter import HeadingSegmenter

    class _Req:
        custom_regex_patterns: list = []
        custom_keywords: list = []
        language = "en"

    return HeadingSegmenter(_Req(), log_callback=lambda m, l="INFO": None)


class TestParagraphHeadlineFix:
    def test_glued_paragraph_is_not_a_chapter_boundary(self):
        """A PDF-glued title+body line (> 120 chars) must NOT be treated as
        a chapter boundary — accepting it made the whole paragraph the
        chapter headline (the user-reported regression)."""
        seg = _make_segmenter()
        glued = (
            "Chapter 1 Identity Diffusion The term describes a specific stage "
            "of adolescent development in which the young person has not yet "
            "committed to an identity and struggles to integrate the various "
            "aspects of self into a coherent whole."
        )
        assert len(glued) > 120
        assert not seg._is_chapter_boundary(glued), (
            "a >120-char glued title+body line must not be a chapter boundary"
        )

    def test_short_glued_line_gets_capped_heading(self):
        """A glued line that slips under the 120-char boundary check still
        gets its heading capped at the first sentence / 80 chars."""
        seg = _make_segmenter()
        # ~105 chars — passes the <=120 boundary check, exceeds the 80-char
        # heading cap, ends mid-body with no sentence punctuation
        glued = (
            "Chapter 1 Identity Diffusion The term describes a specific stage "
            "of adolescent development in which the young person"
        )
        assert 80 < len(glued) <= 120, f"test fixture length: {len(glued)}"
        assert seg._is_chapter_boundary(glued)
        heading = seg._normalise_heading(glued)
        assert len(heading) <= 80, f"heading must be capped, got {len(heading)} chars"
        assert heading.startswith("Chapter 1 Identity Diffusion"), (
            f"the title part must survive, got {heading!r}"
        )

    def test_normalise_caps_at_80_chars(self):
        seg = _make_segmenter()
        long_no_sentence = "Chapter 2 " + "Formation Processes " * 10  # 200 chars, no punctuation
        heading = seg._normalise_heading(long_no_sentence)
        assert len(heading) <= 80

    def test_selection_toc_filter_returns_full_toc_below_two(self):
        """A 1-entry TOC disables all three TOC segmentation strategies —
        the filter must return the FULL TOC instead (the fix for the
        paragraph-as-headline cascade)."""
        from core.segmentation.chapter_matcher import filter_toc_entries_for_selection

        toc = [(f"Chapter {i}: Topic {i}", i * 10) for i in range(1, 31)]
        # Selection matches exactly ONE entry (Chapter 1)
        filtered, dropped = filter_toc_entries_for_selection(toc, ["Chapter 1: Topic 1"], log=None)
        assert filtered is toc or filtered == toc, (
            "a single match must return the FULL TOC (1-entry TOC disables TOC segmentation)"
        )
        assert dropped == 0

    def test_selection_toc_filter_still_restricts_multi_matches(self):
        """The V0.02 false-success fix survives: selections matching >= 2
        entries still get a restricted TOC."""
        from core.segmentation.chapter_matcher import filter_toc_entries_for_selection

        toc = [(f"Chapter {i}: Topic {i}", i * 10) for i in range(1, 31)]
        filtered, dropped = filter_toc_entries_for_selection(
            toc, ["Chapter 1: Topic 1", "Chapter 2: Topic 2"], log=None
        )
        assert len(filtered) == 2
        assert dropped == 28

    def test_likely_heading_rejects_mid_sentence_chapter(self):
        """A body sentence with 'Chapter' mid-string is not a heading
        candidate (the old substring test matched it; now start-anchored).
        The discriminator starts lowercase so rule 4 (title-case heuristic)
        cannot mask the rule-3 change."""
        from core.common.heading_utils import is_likely_heading

        assert not is_likely_heading("as noted in Chapter 3 the theory holds for all adolescents")
        assert is_likely_heading("Chapter 5: Conclusion")
        assert is_likely_heading("## Chapter 3 — Methods")
        assert is_likely_heading("PART TWO")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
