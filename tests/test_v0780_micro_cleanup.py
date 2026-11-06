"""V0.7.8 — the micro-cleanup batch pin file (the audit's three observations).

The V0.7.5-campaign audit (docs/AUDIT_CAMPAIGN_V0.7.5.md §8) recorded
three observations — "candidates for a future micro-cleanup, not
defects".  The owner approved the batch in the post-V0.7.7 session:

1. The Settings "Maximum" quality preset flips the truthfully-labelled
   Ollama-only self-consistency checkbox ON under a generic name — the
   effect is now spelled out in the PRESET tooltip too (visible before
   the pick, not only after it).
2. ``gap_fill_concepts`` accepted two ``overdeliver_*`` params it never
   read (signature-only legacy) — dropped (2e9b61d).
3. The close-out's B3 phrasing ("whether any UI ever exposes it") was
   imprecise — the Settings page has carried the checkbox since
   V0.4.19; the harmonized phrasing names the real open decision
   (NEW surfaces, the wizard).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_AIQ = _project_root / "ui_qt" / "settings" / "sections" / "ai_prompt_quality.py"
_CLOSEOUT = _project_root / "docs" / "CAMPAIGN_CLOSEOUT_V0.7.5.md"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the Maximum preset's effect is visible at the preset itself
# ═══════════════════════════════════════════════════════════════════════════


class TestMaximumPresetTooltip:
    """The audit's observation 1: the preset name over-promised — the
    Ollama-only caveat lived only on the checkbox the preset flips, so a
    non-Ollama user learned it AFTER picking Maximum.  The preset combo
    now carries the same truth."""

    def test_preset_tooltip_names_each_preset_effect(self):
        src = _src(_AIQ)
        for phrase in (
            "• Fast — temperature 0.3, self-consistency OFF.",
            "• Balanced — temperature 0.2, self-consistency OFF.",
            "• Maximum — temperature 0.1 AND self-consistency ON.",
        ):
            assert phrase in src, f"the preset tooltip must carry {phrase!r}"

    def test_preset_tooltip_carries_the_ollama_only_truth(self):
        """Same three facts as the checkbox copy (audit §W12): Ollama-only,
        ~3-4× cost, skipped elsewhere with a logged warning."""
        src = _src(_AIQ)
        for phrase in (
            "only runs when the provider is",
            "Ollama",
            "~3-4×",
            "skipped with a",
            "logged warning",
        ):
            assert phrase in src, f"the preset tooltip must carry {phrase!r}"

    def test_the_checkbox_copy_is_unchanged(self):
        """The V0.7.5 truthful checkbox copy stays exactly as pinned by
        test_v0750_steps7_7b (Ollama-only; ~3-4× cost; union, not majority
        vote) — this cleanup only ADDS the preset tooltip."""
        src = _src(_AIQ)
        for phrase in (
            "Ollama-only",
            "~3-4× cost",
            "union, not majority vote",
        ):
            assert phrase in src, f"the checkbox copy must still carry {phrase!r}"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the gap-filler signature drop (2e9b61d)
# ═══════════════════════════════════════════════════════════════════════════


class TestGapFillerSignatureDrop:
    """The audit's observation 3: the two ``overdeliver_*`` params were
    signature-only legacy — accepted, never read in the body.  Dropped;
    the request fields stay (read into Summarizer attributes, set by
    external rig scripts)."""

    def test_signature_has_no_overdeliver_params(self):
        from core.summarisation.gap_filler import gap_fill_concepts

        params = inspect.signature(gap_fill_concepts).parameters
        assert "overdeliver_enabled" not in params
        assert "overdeliver_target" not in params
        # the params that ARE read survive the drop
        for still_there in (
            "effective_target",
            "coverage_threshold",
            "temperature",
        ):
            assert still_there in params, f"{still_there} must survive the drop"

    def test_the_wrapper_no_longer_passes_them(self):
        wrapper = _src(_project_root / "core" / "summarisation" / "summarizer_coverage.py")
        assert "overdeliver_enabled=self.overdeliver_enabled" not in wrapper
        assert "overdeliver_target=self.overdeliver_target" not in wrapper


# ═══════════════════════════════════════════════════════════════════════════
# 3 — the close-out's B3 phrasing names the real open decision
# ═══════════════════════════════════════════════════════════════════════════


class TestCloseoutB3Phrasing:
    """The audit's observation 2: "whether any UI ever exposes it" was
    imprecise — the Settings AI-quality page has carried the default-off
    b3-voting checkbox since V0.4.19.  The open decision is about NEW
    surfaces (the wizard)."""

    def test_the_imprecise_phrase_is_gone(self):
        src = _src(_CLOSEOUT)
        assert "whether any UI ever exposes it" not in src

    def test_the_harmonized_phrasing_names_the_real_decision(self):
        src = _src(_CLOSEOUT)
        assert "since V0.4.19" in src
        assert "NEW surface" in src
