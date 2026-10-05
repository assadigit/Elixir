"""V13.40.2: Tests for the phase-based VRAM budget calculation.

Tests verify:
1. OCR + Summarization (sequential phases) → peak is MAX, not SUM
2. Translation (separate phase) doesn't add to summarization peak
3. The user's exact scenario (OlmOCR 6.4 + Gemma4-12B 9.3 = 9.3 peak, not 15.7)

V0.6.14 (single-model order): the "Summarization + Fast model (same
Phase 2) → peak is SUM of both" scenario is RETIRED —
calculate_vram_budget no longer takes fast_model/heavy_model params and
emits no Fast/Simplification or Heavy estimates (ONE model,
summarisation_model, does every LLM task; nothing else shares its phase).
"""

from __future__ import annotations

import pytest

from core.vram_calculator import calculate_vram_budget


class TestPhaseBasedVRAM:
    """V13.40.2: Verify peak VRAM is the MAX across phases, not the SUM."""

    def test_ocr_plus_summarization_uses_max_not_sum(self):
        """OCR (Phase 1) + Summarization (Phase 2) → peak should be max(OCR, Summ), not sum."""
        estimates, peak, total, rec = calculate_vram_budget(
            ocr_model="olmocr-7b-q4",  # ~6.4 GB
            summarization_model="gemma4-12b:latest",  # ~9.3 GB
            max_workers=1,
        )
        # Peak should be ~9.3 (the max), NOT ~15.7 (the sum)
        assert peak < 11.0, f"Peak {peak:.1f} should be ~9.3 (max), not ~15.7 (sum)"
        assert peak > 8.0, f"Peak {peak:.1f} should be ~9.3 (the larger model)"

    def test_user_exact_scenario(self):
        """The user's exact scenario: OlmOCR + gemma4-12b on 12GB VRAM."""
        estimates, peak, total, rec = calculate_vram_budget(
            ocr_model="OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest",
            summarization_model="gemma4-12b:latest",
            max_workers=1,
        )
        # Peak should be ~9.3 GB (fits in 12 GB), NOT 15.7 GB (overbudget)
        assert peak < 12.0, f"Peak {peak:.1f} should fit in 12 GB (was 15.7 before fix)"
        # Should NOT be overbudget
        assert "OVERBUDGET" not in rec, f"Should not be overbudget: {rec}"

    # V0.6.14 (single-model order): 1 test REMOVED —
    # test_summarization_plus_fast_model_sums pinned the fast_model param
    # of calculate_vram_budget (a second model summed into the Phase-2
    # peak during the model swap). The dual-model concept is retired:
    # there is no fast_model param and no same-phase second model to sum,
    # so the scenario it pinned cannot exist anymore.

    def test_translation_separate_phase(self):
        """Translation (Phase 3) doesn't add to summarization (Phase 2) peak."""
        estimates, peak, total, rec = calculate_vram_budget(
            summarization_model="gemma4-12b:latest",  # ~9.3 GB (Phase 2)
            translation_backend="ollama",
            translation_model="translategemma:4b",  # ~2.8 GB (Phase 3)
            max_workers=1,
        )
        # Peak should be max(9.3, 2.8) = 9.3, NOT 9.3 + 2.8 = 12.1
        assert peak < 11.0, f"Peak {peak:.1f} should be ~9.3 (max), not ~12.1 (sum)"

    def test_no_false_overbudget_for_sequential_phases(self):
        """Two large models in different phases should NOT trigger overbudget."""
        # OCR 6.4 GB + Summarization 9.3 GB = 15.7 GB if summed (wrong)
        # But max(6.4, 9.3) = 9.3 GB (correct — fits in 12 GB)
        estimates, peak, total, rec = calculate_vram_budget(
            ocr_model="olmocr-7b-q4",
            summarization_model="gemma4-12b:latest",
            max_workers=1,
        )
        # The old code would have produced "❌ OVERBUDGET: 15.7 GB"
        # The new code should produce "✅ Comfortable: 9.3 GB" or similar
        assert "OVERBUDGET" not in rec, f"False overbudget: {rec}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
