"""V13.40.2: Tests for the phase-based VRAM budget calculation.

Tests verify:
1. OCR + Summarization (sequential phases) → peak is MAX, not SUM
2. Summarization + Fast model (same phase) → peak is SUM of both
3. Translation (separate phase) doesn't add to summarization peak
4. The user's exact scenario (OlmOCR 6.4 + Gemma4-12B 9.3 = 9.3 peak, not 15.7)
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

    def test_summarization_plus_fast_model_sums(self):
        """Summarization + Fast model (same Phase 2) → peak should include both."""
        estimates, peak, total, rec = calculate_vram_budget(
            ocr_model="",
            summarization_model="gemma4-12b:latest",  # ~9.3 GB
            fast_model="qwen2.5:7b",  # ~5 GB — different model, same phase
            max_workers=1,
        )
        # Peak should be at least 9.3 (summarization alone)
        assert peak >= 9.0, f"Peak {peak:.1f} should include summarization model"
        # Fast model is in the same phase, so it adds to the peak
        # (model swap: both may be loaded briefly during the swap)
        assert peak > 9.3, f"Peak {peak:.1f} should include fast model (same phase)"

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
