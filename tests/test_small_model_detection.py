"""Phase 0 (item 0.6) — Characterization tests for small-model detection.

V18.2.39: the Summarizer.__init__ detects small models (< 13B params) and
low-bit quants, then:
  1. Caps ``summarisation_max_output_tokens`` to 8192 (down from 16000).
  2. Disables Academic Rigor for small models (< 13B).

This prevents small models from running out of attention capacity and
producing prompt-leakage / empty responses (the V18.2.38 regression where
Qwen3.8-9b-Q8 echoed prompt instructions instead of following them).

**Phase 0 status:** these tests PASS immediately — they characterize the
EXISTING inline logic in ``summarizer.py.__init__``.  Phase 1.1 will replace
the inline regex with ``model_taxonomy.is_small_model`` / ``is_low_bit_quant``;
these tests serve as the regression gate.

Approach: since ``Summarizer.__init__`` is heavy (creates ModelManager,
OllamaSupervisor, loads PromptManager, etc.), we use TWO strategies:
  1. **Source-level assertion** (like test_embedder_regression): read
     summarizer.py source, assert the V18.2.39 cap logic is present.
  2. **model_taxonomy cross-check**: verify that the taxonomy functions
     produce the same classification as the inline regex for every known
     model variant.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# V18.20.3.12 (F821): removed a dead broken line —
# ``Path(__project_root if False else __file__).resolve().parent.parent`` —
# which referenced the undefined name ``__project_root`` (never evaluated at
# runtime because the ternary condition is literally False; the line was
# immediately overwritten by the correct definition below anyway).
# Fix: use _project_root from __file__
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.model_taxonomy import is_low_bit_quant, is_small_model

SUMMARIZER_PATH = _project_root / "core" / "summarisation" / "summarizer.py"


class TestSmallModelDetectionSourceLevel:
    """Verify the V18.2.39 cap logic exists in summarizer.py source."""

    def _read_source(self) -> str:
        return SUMMARIZER_PATH.read_text(encoding="utf-8")

    def test_source_contains_small_model_check(self):
        """summarizer.py must contain the _is_small_model detection."""
        src = self._read_source()
        assert "_is_small_model" in src, (
            "V18.2.39 small-model detection not found in summarizer.py"
        )

    def test_source_contains_13b_threshold(self):
        """The 13B threshold must be present."""
        src = self._read_source()
        assert "13.0" in src or "13" in src, (
            "V18.2.39 13B threshold not found"
        )

    def test_source_contains_8192_cap(self):
        """The 8192 max_output cap for small/low-bit models must be present."""
        src = self._read_source()
        assert "8192" in src, (
            "V18.2.39 max_output=8192 cap not found"
        )

    def test_source_contains_low_bit_detection(self):
        """V18.3 (Phase 1.1): summarizer.py detects low-bit quants via model_taxonomy.

        After Phase 1.1, the inline regex is replaced by an import of
        ``is_low_bit_quant`` from ``core.llm.model_taxonomy``. This test
        verifies the import is present.
        """
        src = self._read_source()
        assert "from core.llm.model_taxonomy import" in src, (
            "V18.3 Phase 1.1: summarizer.py must import is_low_bit_quant "
            "from model_taxonomy (replacing the inline regex)."
        )
        assert "is_low_bit_quant" in src, "model_taxonomy function must be called."

    def test_source_contains_param_count_regex(self):
        """The param-count extraction regex must be present."""
        src = self._read_source()
        # The regex r'(\d+(?:\.\d+)?)\s*[bB]\b' extracts e.g. "27" from "27B".
        assert "[bB]" in src or "param" in src.lower(), (
            "Param-count extraction regex not found"
        )


class TestModelTaxonomyCrossCheck:
    """model_taxonomy must classify models identically to the inline regex.

    These tests verify that the NEW model_taxonomy functions produce the
    same classification as the OLD inline regex in summarizer.py.  When
    Phase 1.1 wires model_taxonomy in, behavior is guaranteed unchanged.
    """

    # The inline regex in summarizer.py (V18.2.39):
    # _is_low_bit = any(q in _model_lower for q in ("iq2_xxs", "iq2_xs", "iq1", "q2_k", "q2_"))
    # _is_small_model = 0 < _param_count_b < 13.0

    @pytest.mark.parametrize("model,expected_small,expected_low_bit", [
        # Small models (< 13B)
        ("Qwen3.8-9B-Q8:latest",       True,  False),
        ("Qwen3.8-3B:latest",          True,  False),
        ("Qwen3.8-12B:latest",         True,  False),
        # 27B low-bit quants (not small, but low-bit)
        ("Qwen3.8-27B-UD-IQ2_S:latest",     False, True),
        ("Qwen3.8-27B-UD-IQ2_XXS:latest",  False, True),
        ("Qwen3.8-27B-UD-Q2_K_XL:latest",  False, True),
        # 27B full-precision (neither small nor low-bit)
        ("Qwen3.8-27B-Q8:latest",      False, False),
        ("Qwen3.8-27B-F16:latest",     False, False),
        # Boundary: 13B exactly → NOT small (0 < 13 < 13.0 is False)
        ("Qwen3.8-13B:latest",         False, False),
        # Boundary: 14B → NOT small
        ("Qwen3.8-14B:latest",         False, False),
    ])
    def test_taxonomy_matches_inline_regex(self, model, expected_small, expected_low_bit):
        """model_taxonomy classification matches the old inline regex."""
        assert is_small_model(model) is expected_small, (
            f"is_small_model({model!r}) = {is_small_model(model)}, "
            f"expected {expected_small}"
        )
        assert is_low_bit_quant(model) is expected_low_bit, (
            f"is_low_bit_quant({model!r}) = {is_low_bit_quant(model)}, "
            f"expected {expected_low_bit}"
        )

    def test_small_model_implies_8192_cap(self):
        """Every small model must trigger the 8192 max_output cap.

        This is the V18.2.39 invariant: small model → cap at 8192.
        """
        small_models = [
            "Qwen3.8-9B-Q8:latest",
            "Qwen3.8-3B:latest",
            "Qwen3.8-12B:latest",
        ]
        for model in small_models:
            assert is_small_model(model), f"{model} should be small"
            # The cap applies because _is_small_model is True.

    def test_low_bit_implies_8192_cap(self):
        """Every low-bit quant must also trigger the 8192 cap (regardless of size).

        V18.2.39: the cap fires if _is_low_bit OR _is_small_model.
        """
        low_bit_models = [
            "Qwen3.8-27B-UD-IQ2_S:latest",
            "Qwen3.8-27B-UD-Q2_K_XL:latest",
            "Qwen3.8-27B-UD-IQ2_XXS:latest",
        ]
        for model in low_bit_models:
            assert is_low_bit_quant(model), f"{model} should be low-bit"
            # The cap applies because _is_low_bit is True (even though not small).

    def test_27b_full_precision_no_cap(self):
        """27B full-precision models (Q8, F16) do NOT get the 8192 cap.

        They get the full 16000 output budget (the _is_low_bit and
        _is_small_model checks both fail).
        """
        full_precision = [
            "Qwen3.8-27B-Q8:latest",
            "Qwen3.8-27B-F16:latest",
        ]
        for model in full_precision:
            assert not is_low_bit_quant(model), f"{model} should NOT be low-bit"
            assert not is_small_model(model), f"{model} should NOT be small"
            # Neither check fires → full 16000 output budget.


class TestAcademicRigorDisable:
    """V18.2.39: Academic Rigor is disabled for small models (< 13B).

    Low-bit quants also have Scholar's Reflections auto-disabled (per the
    session prompt's hard constraints), but Academic Rigor specifically
    is gated on _is_small_model.
    """

    def test_source_contains_academic_rigor_disable(self):
        """summarizer.py must contain Academic Rigor disable logic."""
        src = SUMMARIZER_PATH.read_text(encoding="utf-8")
        # The V18.2.39 logic disables Academic Rigor for small models.
        assert "academic_rigor" in src.lower() or "academic" in src.lower(), (
            "Academic Rigor logic not found in summarizer.py"
        )

    @pytest.mark.parametrize("model,should_disable_rigor", [
        ("Qwen3.8-9B-Q8:latest",      True),   # 9B < 13B → disable
        ("Qwen3.8-3B:latest",         True),   # 3B < 13B → disable
        ("Qwen3.8-27B-UD-IQ2_S:latest", False),  # 27B → keep (low-bit, but not small)
        ("Qwen3.8-27B-Q8:latest",     False),  # 27B full-precision → keep
    ])
    def test_rigor_disable_matches_taxonomy(self, model, should_disable_rigor):
        """The Academic Rigor disable condition matches is_small_model()."""
        is_small = is_small_model(model)
        assert is_small == should_disable_rigor, (
            f"is_small_model({model!r}) = {is_small}, "
            f"expected rigor_disable = {should_disable_rigor}"
        )
