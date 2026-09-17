"""Phase 0 (item 0.2) — Tests for the model_taxonomy module.

This module is the single source of truth for model classification
(low-bit quant, small model, parameter count, context cap).

**Phase 0 status:** model_taxonomy.py is created but NOT YET WIRED into any
call site.  These tests verify its own logic.  Phase 1 will wire it into
the 5 inline-regex sites — at that point, cross-site parity tests (in
test_small_model_detection.py and test_ctx_cap_branching.py) confirm the
taxonomy produces the same classifications as the old inline regexes.

Test categories:
  - Parametric: every known model variant (IQ2_S, Q2_K_XL, 9B, etc.)
  - Edge cases: None, empty, no param count, ambiguous names
  - Cross-check: is_iq2_s vs is_low_bit_quant (IQ2_S is low-bit but Q2_K_S is NOT iq2_s)
  - Context cap: the full recommended_ctx_cap decision matrix
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.model_taxonomy import (
    LOW_BIT_TOKENS,
    is_27b_plus,
    is_iq2_s,
    is_low_bit_quant,
    is_small_model,
    param_count_b,
    recommended_ctx_cap,
)

# ── is_low_bit_quant ────────────────────────────────────────────────────────

class TestIsLowBitQuant:
    """Every known low-bit quant variant must be detected."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest",
        "Qwen3.8-27B-UD-IQ2_S:latest",
        "Qwen3.8-27B-UD-IQ2_XXS:latest",
        "Qwen3.8-27B-UD-IQ2_XS:latest",
        "Qwen3.8-27B-UD-Q2_K_XL:latest",
        "Qwen3.8-27B-UD-Q2_K:latest",
        "Qwen3.8-27B-UD-Q2_K_S:latest",
        "Qwen3.8-27B-UD-IQ1_S:latest",
        "Qwen3.8-27B-UD-IQ1_M:latest",
        "Qwen3.8-27B-Q1_0:latest",
        "qwen3.8-27b-ud-iq2_s:latest",  # case-insensitive
        "QWEN3.8-27B-IQ2_S",            # all-caps
    ])
    def test_detects_low_bit_quants(self, model):
        assert is_low_bit_quant(model) is True

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-Q8_0:latest",       # Q8 is NOT low-bit
        "Qwen3.8-27B-F16:latest",         # FP16 is NOT low-bit
        "Qwen3.8-9B-Q8:latest",           # small model, not low-bit
        "llama3:8b",                       # different family
        "gpt-4",                           # no quant token
    ])
    def test_rejects_full_precision(self, model):
        assert is_low_bit_quant(model) is False

    @pytest.mark.parametrize("model", [None, "", "   "])
    def test_rejects_empty(self, model):
        assert is_low_bit_quant(model) is False

    def test_low_bit_tokens_not_empty(self):
        """The canonical token list must not be empty."""
        assert len(LOW_BIT_TOKENS) >= 5
        assert "iq2_s" in LOW_BIT_TOKENS
        assert "q2_k" in LOW_BIT_TOKENS


# ── is_iq2_s ────────────────────────────────────────────────────────────────

class TestIsIq2S:
    """IQ2_S is a special case: it gets the 26758 ctx cap, not 16000."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S:latest",
        "Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest",
        "qwen3.8-27b-ud-iq2_s:latest",
    ])
    def test_iq2_s_detected(self, model):
        assert is_iq2_s(model) is True

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-Q2_K_XL:latest",   # Q2_K, not IQ2_S
        "Qwen3.8-27B-UD-Q2_K_S:latest",    # Q2_K_S contains q2_k → not iq2_s
        "Qwen3.8-27B-UD-IQ2_XXS:latest",   # XXS, not S
        "Qwen3.8-27B-UD-IQ2_XS:latest",    # XS, not S
        "Qwen3.8-27B-Q8:latest",           # not low-bit at all
    ])
    def test_non_iq2_s_rejected(self, model):
        assert is_iq2_s(model) is False

    def test_iq2_s_is_also_low_bit(self):
        """IQ2_S must also be classified as low-bit (subset relationship)."""
        model = "Qwen3.8-27B-UD-IQ2_S:latest"
        assert is_iq2_s(model) is True
        assert is_low_bit_quant(model) is True


# ── param_count_b ───────────────────────────────────────────────────────────

class TestParamCountB:
    """Extract the parameter count in billions from the model name."""

    @pytest.mark.parametrize("model,expected", [
        ("Qwen3.8-27B-UD-IQ2_S:latest", 27.0),
        ("Qwen3.8-9B-Q8:latest", 9.0),
        ("llama3:8b", 8.0),
        ("Qwen3.8-32B:latest", 32.0),
        ("Qwen3.8-70B:latest", 70.0),
        ("Qwen3.8-14.5B:latest", 14.5),    # decimal param count
        ("phi-3.5-mini", 0.0),              # no param count in name
        ("gpt-4", 0.0),
        ("", 0.0),
        (None, 0.0),
    ])
    def test_param_count(self, model, expected):
        assert param_count_b(model) == expected


# ── is_small_model ──────────────────────────────────────────────────────────

class TestIsSmallModel:
    """V18.2.39: < 13B params → small model (max_output=8192, rigor off)."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-9B-Q8:latest",
        "llama3:8b",
        "Qwen3.8-12B:latest",
        "Qwen3.8-3B:latest",
    ])
    def test_small_models_detected(self, model):
        assert is_small_model(model) is True

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S:latest",   # 27B, not small
        "Qwen3.8-14B:latest",             # 14B > 13B threshold
        "Qwen3.8-32B:latest",             # 32B
        "Qwen3.8-13B:latest",             # exactly 13B → NOT small (boundary)
    ])
    def test_large_models_rejected(self, model):
        assert is_small_model(model) is False

    def test_boundary_at_threshold(self):
        """13B is the boundary — 13B is NOT small (>= threshold)."""
        assert is_small_model("Qwen3.8-13B:latest") is False
        assert is_small_model("Qwen3.8-12.9B:latest") is True

    def test_unknown_size_not_small(self):
        """Models with no param count in the name → NOT small (conservative)."""
        assert is_small_model("unknown-model") is False
        assert is_small_model("") is False
        assert is_small_model(None) is False

    def test_custom_threshold(self):
        """The threshold is configurable (V18.2.39 uses 13.0 default)."""
        # With threshold=20, 14B is small; with default 13, it's not.
        assert is_small_model("Qwen3.8-14B:latest", threshold=20.0) is True
        assert is_small_model("Qwen3.8-14B:latest", threshold=13.0) is False


# ── is_27b_plus ──────────────────────────────────────────────────────────────

class TestIs27BPlus:
    """27B+ models need the num_ctx cap on ≤ 12 GB cards."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S:latest",
        "Qwen3.8-32B:latest",
        "Qwen3.8-70B:latest",
    ])
    def test_large_models(self, model):
        assert is_27b_plus(model) is True

    @pytest.mark.parametrize("model", [
        "Qwen3.8-9B-Q8:latest",
        "Qwen3.8-14B:latest",
        "Qwen3.8-19B:latest",   # 19B < 20B threshold
    ])
    def test_small_models(self, model):
        assert is_27b_plus(model) is False

    def test_boundary_at_20b(self):
        """20B is the threshold — 20B IS 27b_plus (>= 20)."""
        assert is_27b_plus("Qwen3.8-20B:latest") is True
        assert is_27b_plus("Qwen3.8-19.9B:latest") is False


# ── recommended_ctx_cap ─────────────────────────────────────────────────────

class TestRecommendedCtxCap:
    """The full VRAM-driven context-cap decision matrix.

    Replicates the logic in llm_provider._adaptive_context (V18.2.43):
      - IQ2_S 27B on ≤ 12 GB  →  26758
      - Q2_K*  27B on ≤ 12 GB  →  16000
      - IQ2_XXS/XS 27B ≤ 12 GB →  16000
      - Small models / big GPUs   →  None (no cap)
    """

    @pytest.mark.parametrize("model,gpu_gb,expected", [
        # IQ2_S on 12 GB → 26758 (the gold-standard cap)
        ("Qwen3.8-27B-UD-IQ2_S:latest", 12.0, 26758),
        # Q2_K_XL on 12 GB → 16000 (tighter, 0.82 GB headroom)
        ("Qwen3.8-27B-UD-Q2_K_XL:latest", 12.0, 16000),
        # Q2_K on 12 GB → 16000
        ("Qwen3.8-27B-UD-Q2_K:latest", 12.0, 16000),
        # IQ2_XXS on 12 GB → 16000 (conservative)
        ("Qwen3.8-27B-UD-IQ2_XXS:latest", 12.0, 16000),
        # IQ2_XS on 12 GB → 16000
        ("Qwen3.8-27B-UD-IQ2_XS:latest", 12.0, 16000),
    ])
    def test_caps_on_12gb(self, model, gpu_gb, expected):
        assert recommended_ctx_cap(model, gpu_gb) == expected

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S:latest",
        "Qwen3.8-27B-UD-Q2_K_XL:latest",
        "Qwen3.8-27B-UD-IQ2_XXS:latest",
    ])
    def test_no_cap_on_24gb(self, model):
        """24 GB cards have enough VRAM — no cap needed."""
        assert recommended_ctx_cap(model, 24.0) is None

    @pytest.mark.parametrize("model", [
        "Qwen3.8-9B-Q8:latest",       # small model, no cap
        "Qwen3.8-27B-Q8:latest",       # full-precision, no cap
        "Qwen3.8-27B-F16:latest",      # FP16, no cap
    ])
    def test_no_cap_for_non_low_bit(self, model):
        assert recommended_ctx_cap(model, 12.0) is None

    def test_iq2_s_cap_higher_than_q2_k(self):
        """IQ2_S gets a HIGHER cap than Q2_K_XL (more VRAM headroom)."""
        iq2s_cap = recommended_ctx_cap("Qwen3.8-27B-UD-IQ2_S:latest", 12.0)
        q2k_cap = recommended_ctx_cap("Qwen3.8-27B-UD-Q2_K_XL:latest", 12.0)
        assert iq2s_cap is not None
        assert q2k_cap is not None
        assert iq2s_cap > q2k_cap, (
            f"IQ2_S cap ({iq2s_cap}) should be > Q2_K cap ({q2k_cap}) — "
            f"IQ2_S has 1.59 GB headroom vs Q2_K_XL's 0.82 GB"
        )


# ── Cross-consistency ───────────────────────────────────────────────────────

class TestCrossConsistency:
    """The predicates must be internally consistent."""

    def test_all_iq2_s_are_low_bit(self):
        """is_iq2_s → is_low_bit_quant (subset relationship)."""
        model = "Qwen3.8-27B-UD-IQ2_S:latest"
        assert is_iq2_s(model)
        assert is_low_bit_quant(model)

    def test_27b_low_bit_on_12gb_has_cap(self):
        """Every 27B low-bit quant on 12 GB gets a non-None cap."""
        for model in [
            "Qwen3.8-27B-UD-IQ2_S:latest",
            "Qwen3.8-27B-UD-Q2_K_XL:latest",
            "Qwen3.8-27B-UD-IQ2_XXS:latest",
        ]:
            assert is_27b_plus(model)
            assert is_low_bit_quant(model)
            assert recommended_ctx_cap(model, 12.0) is not None

    def test_small_model_not_necessarily_low_bit(self):
        """A 9B-Q8 is small but NOT low-bit (independent dimensions)."""
        model = "Qwen3.8-9B-Q8:latest"
        assert is_small_model(model)
        assert not is_low_bit_quant(model)
