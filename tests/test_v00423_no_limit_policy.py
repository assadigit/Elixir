"""V0.4.23 (user directive — "no limit for bullet point quantity or
thorough summary; they can be as long as necessary for full coverage").

The policy-level pins: bullet_cap()==0 everywhere, thorough_target
uncapped, the prompt phrasing ("at least N" / NO MAXIMUM), and the
insertion-site caps' fail-open behavior at 0.
"""

from __future__ import annotations


class TestNoBulletCap:
    def test_bullet_cap_is_two_regime(self):
        """V0.6.2 (user-reported thin-book bug): ``bullet_cap`` is
        TWO-REGIME. NORMAL chapters (>= 800 words): 0 — the V0.4.23
        no-cap user directive stands. THIN chapters (< 800 words): the
        source-scaled ADDITIVE budget (bullet_target hi) — the cap only
        ever bounds gap-fill/resurrection ADDITIONS, never primary
        bullets; it bounds exactly the machinery that padded the user's
        thin book (1-2 page chapters) past its own source word count.
        The historical V0.4.22 displacement failure (the reason the cap
        was removed) was a content-rich chapter — those keep 0."""
        from core.summarisation.length_policy import bullet_cap, bullet_target

        for w in (800, 1000, 3000, 12000, 100000):
            assert bullet_cap(w) == 0, w
        for w in (50, 150, 340, 441):
            assert bullet_cap(w) == bullet_target(w)[1] > 0, w

    def test_bullet_range_phrase_is_a_floor_for_normal_chapters(self):
        from core.summarisation.length_policy import bullet_range_phrase

        assert bullet_range_phrase(1000) == "at least 27"  # lo of the 27-40 guidance range
        # V0.6.2: thin chapters get a BOUNDED range instead (the
        # "at least N ... NO MAXIMUM" phrasing invited rephrase-padding
        # on chapters with fewer distinct ideas than N)
        assert bullet_range_phrase(340) == "9-14"

    def test_budget_block_no_maximum_wording(self):
        from core.summarisation.length_policy import length_budget_block

        block = length_budget_block(12000)
        assert "NO MAXIMUM" in block
        assert "at least" in block
        assert "no absolute ceiling" in block
        # the compression contract survives (never pad / never exceed source)
        assert "COMPRESSION CONTRACT" in block


class TestThoroughUnbounded:
    def test_thorough_target_scales_past_1200(self):
        from core.summarisation.length_policy import thorough_target

        assert thorough_target(12000)[1] == 5400  # 0.45 x, uncapped
        assert thorough_target(3000)[1] == 1350
        assert thorough_target(1000)[1] == 800  # the floor still applies

    def test_thorough_words_phrase_grows(self):
        from core.summarisation.length_policy import thorough_words_phrase

        assert thorough_words_phrase(12000) == "3240-5400 word"


class TestInsertionSitesFailOpenAtZero:
    def test_tier2_cap_noop_at_zero(self):
        """coverage_guarantee treats bullet_cap<=0 as no cap — Tier-2 gap-fill
        is never trimmed when the budget is 0 (the V0.4.23 default)."""
        from core.summarisation.coverage_guarantee import apply_3tier_coverage

        result = {
            "executive_summary": "E",
            "bullet_points": ["B1 about concept alpha"],
            "thorough_summary": "T",
        }
        logs: list[str] = []

        def gap_fill(heading, text, missing):
            return [f"New bullet about {m}" for m in missing]

        apply_3tier_coverage(
            "H",
            "text " * 100,
            "concept alpha concept beta concept gamma " * 5,
            result,
            coverage=0.10,
            coverage_threshold=0.99,
            extract_keywords=lambda text, n: ["alpha", "beta", "gamma"],
            log=lambda msg, level="INFO": logs.append(msg),
            targeted_gap_fill=gap_fill,
            filter_thinking_bullets=lambda bl: list(bl),
            max_bullets_per_chapter=99999,
            compute_coverage=lambda c, s: 0.2,
            force_insert_missing=lambda t, sm, r: None,
            bullet_cap=0,
        )
        joined = " ".join(logs)
        assert "bullet budget reached" not in joined
        assert "bullet budget leaves room" not in joined
        # gap-fill bullets were NOT trimmed by a cap
        assert any("beta" in str(b) for b in result["bullet_points"])
