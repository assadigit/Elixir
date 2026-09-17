"""Phase 0 (item 0.4) — Characterization tests for the num_ctx cap branching.

V18.2.40/43: ``OllamaProvider._adaptive_context`` caps ``num_ctx`` for 27B
low-bit quant models on ≤ 12 GB cards:

  - IQ2_S 27B on ≤ 12 GB  →  26758  (1.59 GB VRAM headroom)
  - Q2_K_XL 27B on ≤ 12 GB →  16000  (0.82 GB headroom — 26758 too tight)
  - IQ2_XXS/XS 27B ≤ 12 GB →  16000  (conservative default)
  - Small models / big GPUs →  no cap (full context_tokens)

**Phase 0 status:** these tests PASS immediately — they characterize the
EXISTING behavior.  They serve as the regression gate for Phase 1.1 (wiring
model_taxonomy into _adaptive_context).  If Phase 1.1 changes the cap
values, these tests will catch it.

Challenge: ``_adaptive_context`` uses ``torch.cuda`` to check VRAM, but
torch is NOT installed in this sandbox.  We mock ``torch`` via
``sys.modules`` injection — a ``FakeTorch`` module that reports a 12 GB
card with low allocated memory.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Fake torch module ──────────────────────────────────────────────────────

class _FakeCudaProperties:
    """Simulates torch.cuda.get_device_properties(0).total_memory."""
    def __init__(self, total_memory_bytes: int):
        self.total_memory = total_memory_bytes


class _FakeTorch:
    """Minimal torch mock: cuda.is_available() + get_device_properties + memory_allocated.

    The real _adaptive_context does:
        import torch
        if torch.cuda.is_available():
            total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)
    """

    def __init__(self, gpu_gb: float = 12.0, allocated_gb: float = 0.0):
        self.cuda = MagicMock()
        self.cuda.is_available.return_value = True
        self.cuda.get_device_properties.return_value = _FakeCudaProperties(
            int(gpu_gb * 1024**3)
        )
        self.cuda.memory_allocated.return_value = int(allocated_gb * 1024**3)


@pytest.fixture
def mock_torch_12gb():
    """Inject a fake torch reporting a 12 GB card with ~0.5 GB allocated."""
    fake = _FakeTorch(gpu_gb=12.0, allocated_gb=0.5)
    original = sys.modules.get("torch")
    sys.modules["torch"] = fake
    yield fake
    if original is not None:
        sys.modules["torch"] = original
    else:
        sys.modules.pop("torch", None)


@pytest.fixture
def mock_torch_24gb():
    """Inject a fake torch reporting a 24 GB card (no cap needed)."""
    fake = _FakeTorch(gpu_gb=24.0, allocated_gb=0.5)
    original = sys.modules.get("torch")
    sys.modules["torch"] = fake
    yield fake
    if original is not None:
        sys.modules["torch"] = original
    else:
        sys.modules.pop("torch", None)


# ── Provider construction helper ────────────────────────────────────────────

def _make_provider(model: str, context_tokens: int = 32768):
    """Create an OllamaProvider with a specific model + context setting.

    OllamaProvider.__init__ creates an OllamaSupervisor internally — this
    is just an object, no network connection.  Safe to construct.
    """
    from core.llm.llm_provider import OllamaProvider
    return OllamaProvider(
        model=model,
        context_tokens=context_tokens,
    )


# ── Tests: the cap branching matrix ─────────────────────────────────────────

class TestCtxCapOn12GB:
    """On a 12 GB card, 27B low-bit quants get a context cap.

    V18.20.2.0 (SWOT A1): the IQ2_S expectation CHANGED. The VRAM-aware
    26758→32768 raise now requires a REAL external VRAM reading (Ollama
    /api/ps); with no external reading available (this test's FakeTorch
    measures the APP process, which the raise must ignore) the safe 26758
    cap stays in force.
    """

    @pytest.mark.parametrize("model,expected_cap", [
        # The gold-standard model: IQ2_S → 26758 (V18.20.2.0 SWOT A1: the
        # VRAM-aware raise to 32768 needs an external /api/ps reading
        # showing ≥1.2 GB free — unavailable here, so the SAFE cap applies.
        # Pre-V18.20.2.0 the app-process torch metric made the raise fire
        # unconditionally — the VRAM illusion this fix removes.)
        ("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest", 26758),
        ("Qwen3.8-27B-UD-IQ2_S:latest", 26758),
        # Q2_K_XL → 16000 (VRAM-aware raise only fires for IQ2_S, not Q2_K)
        ("Qwen3.8-27B-UD-Q2_K_XL:latest", 16000),
        ("Qwen3.8-27B-UD-Q2_K:latest", 16000),
        # IQ2_XXS → 16000 (VRAM-aware raise only fires for IQ2_S specifically)
        ("Qwen3.8-27B-UD-IQ2_XXS:latest", 16000),
        # IQ2_XS → 16000
        ("Qwen3.8-27B-UD-IQ2_XS:latest", 16000),
    ])
    def test_27b_low_bit_capped(self, mock_torch_12gb, model, expected_cap):
        """27B low-bit quants on 12 GB get the model-specific cap."""
        provider = _make_provider(model)
        # Use a prompt long enough that the uncapped ctx EXCEEDS 26758.
        # needed = prompt_tokens + max_tokens + 4096 = 15000 + 8192 + 4096 = 27288
        # uncapped ctx = min(32768, max(16000, 27288)) = 27288 > 26758 → cap fires.
        long_prompt = "x " * 30000  # ~15000 tokens → needed > 26758
        ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == expected_cap, (
            f"{model} on 12 GB should cap at {expected_cap}, got {ctx}"
        )

    def test_iq2_s_capped_to_26758_without_external_reading(self, mock_torch_12gb):
        """V18.20.2.0 (SWOT A1): IQ2_S WITHOUT an external /api/ps reading is
        capped at the safe 26758 — even though the app-process torch metric
        (FakeTorch: 12 GB total, 0.5 GB allocated → 11.5 GB "free") would
        have raised it to 32768 pre-fix. The app-process metric must NOT
        drive the raise (it cannot see Ollama's actual VRAM usage).
        """
        provider = _make_provider("Qwen3.8-27B-UD-IQ2_S:latest")
        long_prompt = "x " * 30000  # needed ~27288 > 26758
        ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == 26758, (
            f"IQ2_S without an external VRAM reading must stay at the safe "
            f"26758 cap, got {ctx}"
        )

    def test_iq2_s_not_capped_to_26758_with_real_external_reading(self, mock_torch_12gb):
        """V18.20.2.0 (SWOT A1): with a REAL external reading (Ollama /api/ps)
        showing ≥1.2 GB free, the raise fires and the ceiling becomes 32768.
        The adaptive ctx for this prompt is ~27288 — under the raised
        ceiling, so no cap fires and ctx stays above 26758.
        """
        from unittest.mock import MagicMock
        provider = _make_provider("Qwen3.8-27B-UD-IQ2_S:latest")
        long_prompt = "x " * 30000  # needed ~27288

        _resp = MagicMock()
        _resp.json.return_value = {
            # one loaded model using 10.5 GB → 12.0 − 10.5 = 1.5 GB free ≥ 1.2
            "models": [{"name": "m", "size_vram": int(10.5 * 1024**3)}]
        }
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("utils.network.safe_ollama_request", lambda *a, **k: _resp)
            ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx > 26758, f"IQ2_S with verified ≥1.2 GB free should NOT be capped to 26758, got {ctx}"
        assert ctx <= 32768, f"Should not exceed 32768, got {ctx}"

    def test_q2_k_xl_cap_is_16000_not_32768(self, mock_torch_12gb):
        """Q2_K_XL must stay at 16000 (VRAM-aware raise only fires for IQ2_S)."""
        provider = _make_provider("Qwen3.8-27B-UD-Q2_K_XL:latest")
        long_prompt = "x " * 30000  # needed > 26758
        ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == 16000, (
            f"Q2_K_XL context cap regressed to {ctx} — must stay 16000 "
            f"(VRAM-aware raise only fires for IQ2_S, not Q2_K)"
        )


class TestNoCapOn24GB:
    """On a 24 GB card, no cap is needed — the model fits with headroom."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-27B-UD-IQ2_S:latest",
        "Qwen3.8-27B-UD-Q2_K_XL:latest",
        "Qwen3.8-27B-UD-IQ2_XXS:latest",
    ])
    def test_no_cap_on_24gb(self, mock_torch_24gb, model):
        """24 GB cards have enough VRAM — no cap, full context_tokens used."""
        provider = _make_provider(model, context_tokens=32768)
        long_prompt = "x " * 30000  # needed > 26758 — cap would fire on 12 GB but not 24 GB
        ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        # Should be the full calculated ctx (not capped to 26758 or 16000).
        # The uncapped value is min(32768, max(16000, needed)) where
        # needed = 10000 + 8192 + 4096 = 22288 → ctx = 22288.
        assert ctx >= 20000, (
            f"24 GB card should NOT cap {model} — got {ctx}"
        )
        assert ctx != 26758, "24 GB should not apply the 12 GB cap"
        assert ctx != 16000, "24 GB should not apply the 12 GB cap"


class TestNoCapForSmallOrFullPrecision:
    """Small models (< 27B) and full-precision models don't get a cap."""

    @pytest.mark.parametrize("model", [
        "Qwen3.8-9B-Q8:latest",       # 9B — small, no cap
        "Qwen3.8-27B-Q8:latest",       # 27B but Q8 (not low-bit), no cap
        "Qwen3.8-27B-F16:latest",       # 27B FP16, no cap
    ])
    def test_no_cap(self, mock_torch_12gb, model):
        """Non-low-bit or small models on 12 GB → no cap."""
        provider = _make_provider(model, context_tokens=32768)
        long_prompt = "x " * 30000  # needed > 26758 — but no cap for non-low-bit models
        ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx >= 20000, f"{model} should not be capped — got {ctx}"
        assert ctx != 26758 and ctx != 16000, (
            f"{model} should not get the low-bit cap — got {ctx}"
        )


class TestAdaptiveContextFloor:
    """The adaptive context never goes below 16000 (Ollama minimum)."""

    def test_short_prompt_still_16000_minimum(self, mock_torch_12gb):
        """Even a 1-token prompt gets at least 16000 context."""
        provider = _make_provider("Qwen3.8-27B-Q8:latest", context_tokens=32768)
        ctx = provider._adaptive_context("hi", max_tokens=4096)
        assert ctx >= 16000, f"Context floor violated: {ctx} < 16000"
