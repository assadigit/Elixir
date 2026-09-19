"""Phase 0 (item 0.5) — Characterization tests for the consolidation leak guard.

V18.2.38: ``BulletPipeline.detect_leaked_consolidation_metadata`` detects
when the consolidation LLM leaked its dedup-reasoning into the bullet
content instead of producing clean consolidated bullets. Patterns caught:

  - "Bullet 11:", "Bullet 27 says"
  - "KEEP BOTH", "KEEP ALL"
  - "This is similar to bullet 27 but..."
  - "These are related but different facts/claims"
  - "Bullet N (Author YYYY) and bullet M (Author YYYY)" comparison headers

When detected, ``_consolidate_bullets`` rejects the LLM output and falls
back to deterministic rapidfuzz dedup.

**Phase 0 status:** these tests PASS immediately — they characterize the
EXISTING leak-guard behavior.  They serve as the regression gate for
Phase 3 (prompt redesign) and Phase 1.1 (model_taxonomy wiring).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.bullet_pipeline import BulletPipeline


class TestLeakDetection:
    """detect_leaked_consolidation_metadata catches leaked dedup-reasoning."""

    def _detect(self, bullets):
        return BulletPipeline.detect_leaked_consolidation_metadata(bullets)

    # ── Clean bullets (no leak) ────────────────────────────────────────────

    @pytest.mark.parametrize(
        "bullet",
        [
            "The author defines identity as an internal psychic structure.",
            "Erikson described identity formation as a lifelong process.",
            "Lichtenstein (1961) distinguished identity from identification.",
            "Kernberg's model includes three structural components: splitting, idealization, and devaluation.",
            "The chapter notes three clinical implications of this model.",
        ],
    )
    def test_clean_bullet_not_flagged(self, bullet):
        """Legitimate summary bullets must NOT be flagged as leaks."""
        leaked, samples = self._detect([bullet])
        assert leaked == 0, f"Clean bullet falsely flagged: {bullet!r}"
        assert samples == []

    def test_all_clean_bullets(self):
        """A list of 5 clean bullets → 0 leaked."""
        bullets = [
            "The author defines identity as an internal psychic structure.",
            "Erikson described identity formation as a lifelong process.",
            "The chapter traces identity from early origins to middle age.",
            "Three clinical frameworks are compared: Erikson, Kernberg, and Lichtenstein.",
            "Identity consolidation occurs during adolescence.",
        ]
        leaked, samples = self._detect(bullets)
        assert leaked == 0

    # ── Leaked patterns ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "bullet,pattern_desc",
        [
            # "Bullet N:" prefix
            (
                "Bullet 11: Lichtenstein (1961) distinguished identity from identification.",
                "Bullet N:",
            ),
            ("Bullet 27 says that identity formation is lifelong.", "Bullet N says"),
            (
                "Bullet 8 (Kernberg 1967) describes three structural components.",
                "Bullet N (Author)",
            ),
            # "KEEP BOTH" / "KEEP ALL"
            ("These are related but different claims. KEEP BOTH.", "KEEP BOTH"),
            ("Similar but distinct. KEEP ALL.", "KEEP ALL"),
            # "This is similar to bullet N"
            (
                "This is similar to bullet 27 but attributes the claim to a different author.",
                "similar to bullet",
            ),
            # "These are related but different"
            ("These are related but different facts/claims.", "related but different"),
            # "different facts/claims" phrasing
            ("These bullets discuss different facts/claims about identity.", "different facts/"),
            # "but different years"
            (
                "Both mention Kernberg but different years and slightly different claims.",
                "different years",
            ),
            # Comparison header: "Bullet N (Author) and bullet M (Author)"
            (
                "Bullet 8 (Kernberg 1967) and bullet 9 (Kernberg 1980): Both discuss identity.",
                "Bullet N and bullet M",
            ),
        ],
    )
    def test_leaked_bullet_detected(self, bullet, pattern_desc):
        """Each known leak pattern must be detected."""
        leaked, samples = self._detect([bullet])
        assert leaked == 1, f"Leak pattern not detected ({pattern_desc}): {bullet!r}"
        assert len(samples) == 1
        idx, matched, preview = samples[0]
        assert idx == 0  # first (and only) bullet

    def test_multiple_leaked_bullets(self):
        """Multiple leaked bullets in one list → all detected."""
        bullets = [
            "Bullet 11: first leaked bullet",
            "A clean bullet about identity formation.",
            "KEEP BOTH — these are different facts.",
            "Another clean bullet about the chapter.",
            "This is similar to bullet 27 but different.",
        ]
        leaked, samples = self._detect(bullets)
        assert leaked == 3, f"Expected 3 leaked, got {leaked}"
        assert len(samples) == 3
        # Indices should be 0, 2, 4
        indices = [s[0] for s in samples]
        assert indices == [0, 2, 4], f"Wrong indices: {indices}"

    def test_only_first_pattern_per_bullet(self):
        """A bullet matching multiple patterns counts as 1 (break after first match)."""
        bullet = "Bullet 11: This is similar to bullet 27. KEEP BOTH."
        leaked, samples = self._detect([bullet])
        assert leaked == 1, "One bullet = one leak (break after first match)"

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_empty_list(self):
        """Empty bullet list → 0 leaked."""
        leaked, samples = self._detect([])
        assert leaked == 0
        assert samples == []

    def test_all_leaked(self):
        """All bullets leaked → all detected."""
        bullets = ["Bullet 1: first", "Bullet 2: second", "Bullet 3: third"]
        leaked, _ = self._detect(bullets)
        assert leaked == 3

    def test_mixed_clean_and_leaked(self):
        """A mix of clean + leaked bullets → only leaked ones counted."""
        bullets = [
            "Erikson described identity formation as a lifelong process.",  # clean
            "Bullet 5: This is a leaked bullet.",  # leaked
            "The author defines identity as an internal structure.",  # clean
            "KEEP BOTH.",  # leaked
        ]
        leaked, samples = self._detect(bullets)
        assert leaked == 2
        leaked_indices = [s[0] for s in samples]
        assert leaked_indices == [1, 3]

    def test_sample_preview_truncated(self):
        """The sample preview is truncated to 80 chars + ellipsis."""
        long_leaked = "Bullet 11: " + "A" * 200
        _, samples = self._detect([long_leaked])
        idx, matched, preview = samples[0]
        assert preview.endswith("…"), f"Preview should end with ellipsis: {preview!r}"
        assert len(preview) <= 81 + len("…"), f"Preview too long: {len(preview)}"

    def test_case_insensitive(self):
        """Leak patterns are case-insensitive."""
        bullets = [
            "bullet 11: lowercase prefix",
            "keep both: lowercase verdict",
            "BULLET 27: uppercase prefix",
        ]
        leaked, _ = self._detect(bullets)
        assert leaked == 3, f"Case-insensitive detection failed: {leaked}"


class TestLeakGuardFallbackContract:
    """The leak guard's return value contract for _consolidate_bullets.

    _consolidate_bullets (summarizer.py) calls detect_leaked_consolidation_metadata
    and, if leaked_count > 0, falls back to _consolidate_duplicate_claims
    (deterministic rapidfuzz dedup).  This test verifies the RETURN VALUE
    CONTRACT that _consolidate_bullets relies on.
    """

    def test_clean_bullets_return_zero(self):
        """Clean bullets → (0, []) → _consolidate_bullets uses LLM output."""
        leaked, samples = BulletPipeline.detect_leaked_consolidation_metadata(
            [
                "Clean bullet one.",
                "Clean bullet two.",
            ]
        )
        assert leaked == 0
        assert samples == []
        # _consolidate_bullets checks: if leaked_count > 0 → fallback.
        # leaked=0 means the LLM output is accepted.

    def test_leaked_bullets_return_nonzero(self):
        """Leaked bullets → (N>0, [...]) → _consolidate_bullets falls back."""
        leaked, samples = BulletPipeline.detect_leaked_consolidation_metadata(
            [
                "Bullet 1: leaked",
            ]
        )
        assert leaked > 0
        assert len(samples) > 0
        # Each sample is a (index, matched_pattern, preview) tuple.
        for sample in samples:
            assert len(sample) == 3
            idx, matched, preview = sample
            assert isinstance(idx, int)
            assert isinstance(matched, str)
            assert isinstance(preview, str)
