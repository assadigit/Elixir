"""V18.3.4 (E1+E2+E3) — Tests for VRAM-aware output expansion + chunked output.

E1: VRAM-aware num_ctx cap (raise 26758 → 32768 when ≥1.2 GB free)
E2: VRAM-aware max_output expansion (8192 → 12000 when VRAM allows)
E3: Chunked output (split 5-section primary call into 2 sequential calls)

V18.20.2.0 (SWOT A1): E1's contract CHANGED. The old raise condition used
``torch.cuda.memory_allocated()`` — which measures the APP process, not the
separate Ollama server process — so "free VRAM" was ≈12 GB on every call and
the raise fired unconditionally (IQ2_S safe_ctx silently 26758→32768, a
hard-constraint violation). The raise now requires a REAL external VRAM
reading (Ollama ``/api/ps`` → Σ size_vram of loaded models):

  - external reading ≥1.2 GB free  → raise fires (26758 → 32768)
  - external reading <1.2 GB free  → stays at 26758
  - external reading UNAVAILABLE   → stays at 26758 (quality > speed)

The tests also scan ``core/llm/ollama_provider.py`` — since the V18.20.1.0
(D7) extraction the provider code lives there (llm_provider.py is a re-export
shim; pre-V18.20.2.0 these tests scanned the shim and failed).
E3's chunking markers moved to ``core/summarisation/primary_call.py`` in the
V18.15.3 extraction — the scans follow the code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

OLLAMA_PROVIDER_PATH = _project_root / "core" / "llm" / "ollama_provider.py"
SUMMARIZER_PATH = _project_root / "core" / "summarisation" / "summarizer.py"
# V0.4.19 (de-monolithization step 9/10): the E3 master-summary machinery
# (_chunked_summarize + _build_chunked_prompt + the V0.3 3-call pipeline)
# moved VERBATIM to summarizer_chunking.py — the E3 source pins follow the
# code (the same re-pointing discipline as the V18.15.3 primary_call move).
SUMMARIZER_CHUNKING_PATH = _project_root / "core" / "summarisation" / "summarizer_chunking.py"
# V0.18 (Phase 5.1): the low-bit max_output cap moved VERBATIM to
# summarizer_init.py — the E2-revert pin follows it there.
SUMMARIZER_INIT_PATH = _project_root / "core" / "summarisation" / "summarizer_init.py"
PRIMARY_CALL_PATH = _project_root / "core" / "summarisation" / "primary_call.py"
PROMPT_ASSEMBLY_PATH = _project_root / "core" / "summarisation" / "prompt_assembly.py"


# ── Fake torch module (same pattern as tests/test_ctx_cap_branching.py) ─────


class _FakeCudaProperties:
    """Simulates torch.cuda.get_device_properties(0).total_memory."""

    def __init__(self, total_memory_bytes: int):
        self.total_memory = total_memory_bytes


class _FakeTorch:
    """Minimal torch mock: cuda.is_available() + get_device_properties + memory_allocated.

    V18.20.2.0 (SWOT A1): the app-process ``memory_allocated`` value is
    deliberately IRRELEVANT now — the raise must NOT fire based on it. The
    fake reports a (fictional, per the SWOT finding) ~0 GB app-process
    allocation to prove the raise ignores it.
    """

    def __init__(self, gpu_gb: float = 12.0, allocated_gb: float = 0.0):
        self.cuda = MagicMock()
        self.cuda.is_available.return_value = True
        self.cuda.get_device_properties.return_value = _FakeCudaProperties(int(gpu_gb * 1024**3))
        self.cuda.memory_allocated.return_value = int(allocated_gb * 1024**3)


@pytest.fixture
def mock_torch_12gb():
    """Inject a fake torch reporting a 12 GB card, ~0 GB allocated (the app process)."""
    fake = _FakeTorch(gpu_gb=12.0, allocated_gb=0.0)
    original = sys.modules.get("torch")
    sys.modules["torch"] = fake
    yield fake
    if original is not None:
        sys.modules["torch"] = original
    else:
        sys.modules.pop("torch", None)


def _make_provider(model: str, context_tokens: int = 32768):
    """Create an OllamaProvider with a specific model + context setting."""
    from core.llm.ollama_provider import OllamaProvider

    return OllamaProvider(model=model, context_tokens=context_tokens)


def _ps_response(size_vram_gb: float):
    """A mocked /api/ps HTTP response listing one loaded model."""
    resp = MagicMock()
    resp.json.return_value = {
        "models": [{"name": "some-model", "size_vram": int(size_vram_gb * 1024**3)}]
    }
    return resp


# ── E1: VRAM-aware num_ctx cap ──────────────────────────────────────────────


class TestVRAMAwareCtxCap:
    """V18.20.2.0 (SWOT A1): the 26758→32768 raise fires ONLY when a REAL
    external VRAM reading (Ollama /api/ps) confirms ≥1.2 GB free."""

    def test_source_contains_vram_aware_raise(self):
        """ollama_provider.py contains the VRAM-aware raise logic."""
        src = OLLAMA_PROVIDER_PATH.read_text(encoding="utf-8")
        assert "V18.20.2.0" in src, "V18.20.2.0 (SWOT A1) marker missing"
        assert "VRAM-aware" in src, "the VRAM-aware raise logic must be present"
        assert "32768" in src, "The raised cap value 32768 must be present"
        assert "_free_gb >= 1.2" in src or "free_gb >= 1.2" in src, (
            "The ≥1.2 GB free-VRAM threshold must be present"
        )

    def test_raise_only_fires_for_iq2_s(self):
        """The VRAM-aware raise only fires for IQ2_S (not Q2_K_XL)."""
        src = OLLAMA_PROVIDER_PATH.read_text(encoding="utf-8")
        assert "if _is_iq2_s_model:" in src, "The raise must be gated on IQ2_S detection"

    def test_raise_requires_external_reading(self):
        """V18.20.2.0 (SWOT A1): the raise is gated on the EXTERNAL reading
        (_external_gpu_free_gb), NOT torch's app-process allocated bytes."""
        src = OLLAMA_PROVIDER_PATH.read_text(encoding="utf-8")
        assert "_external_gpu_free_gb" in src, (
            "The raise must call the external /api/ps reading helper"
        )
        assert "_free_gb is not None and _free_gb >= 1.2" in src, (
            "The raise must check the external reading is available AND ≥1.2 GB"
        )
        # The OLD fictional metric (app-process torch allocation) must NOT
        # drive the raise anymore.
        assert "_free_gb = total_gb - allocated_gb" not in src, (
            "The app-process torch metric must no longer compute free VRAM "
            "for the raise (SWOT A1 root cause)"
        )

    def test_raise_fires_with_real_external_reading(self, mock_torch_12gb):
        """External /api/ps reading shows ≥1.2 GB free → raise 26758→32768."""
        provider = _make_provider("Qwen3.8-27B-UD-IQ2_S:latest")
        long_prompt = "x " * 30000  # needed ~27288 > 26758 → cap would fire
        # /api/ps: one model loaded using 10.5 GB → 12.0 − 10.5 = 1.5 GB free ≥ 1.2
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "utils.network.safe_ollama_request",
                lambda *a, **k: _ps_response(10.5),
            )
            ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert 26758 < ctx <= 32768, (
            f"With a real external reading ≥1.2 GB free the raise must fire "
            f"(ctx > 26758, ≤32768); got {ctx}"
        )

    def test_no_raise_when_external_reading_below_threshold(self, mock_torch_12gb):
        """External reading shows <1.2 GB free → stays at the safe 26758 cap."""
        provider = _make_provider("Qwen3.8-27B-UD-IQ2_S:latest")
        long_prompt = "x " * 30000
        # /api/ps: 11.2 GB used → 0.8 GB free < 1.2 → NO raise
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "utils.network.safe_ollama_request",
                lambda *a, **k: _ps_response(11.2),
            )
            ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == 26758, (
            f"External reading <1.2 GB free must keep the safe 26758 cap; got {ctx}"
        )

    def test_no_raise_when_external_reading_unavailable(self, mock_torch_12gb):
        """V18.20.2.0 (SWOT A1) — THE core regression: when the external
        reading is unavailable (Ollama offline / API error), the raise does
        NOT fire — even though the (fictional) app-process torch metric
        reports ~12 GB free. The safe 26758 cap stays in force."""
        provider = _make_provider("Qwen3.8-27B-UD-IQ2_S:latest")
        long_prompt = "x " * 30000

        def _unreachable(*a, **k):
            raise ConnectionError("Ollama /api/ps unreachable (simulated)")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("utils.network.safe_ollama_request", _unreachable)
            ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == 26758, (
            f"Unavailable external reading must keep the safe 26758 cap "
            f"(the OLD code raised to 32768 here on every call); got {ctx}"
        )

    def test_q2_k_xl_never_raises_even_with_external_headroom(self, mock_torch_12gb):
        """The raise is IQ2_S-only: Q2_K_XL stays at 16000 regardless."""
        provider = _make_provider("Qwen3.8-27B-UD-Q2_K_XL:latest")
        long_prompt = "x " * 30000
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "utils.network.safe_ollama_request",
                lambda *a, **k: _ps_response(10.5),
            )
            ctx = provider._adaptive_context(long_prompt, max_tokens=8192)
        assert ctx == 16000, f"Q2_K_XL must stay at 16000 (raise is IQ2_S-only); got {ctx}"

    def test_logs_the_raise(self):
        """The raise logs a structured "ctx_raise" line so ops can see it fire."""
        src = OLLAMA_PROVIDER_PATH.read_text(encoding="utf-8")
        assert "ctx_raise:" in src, "Must log a ctx_raise line (kept for ops continuity)"

    def test_safe_ctx_default_is_26758_via_shared_clamp(self):
        """The 26758 safe default is the shared clamp's IQ2_S value."""
        from core.llm.ctx_clamp import low_bit_ctx_cap

        assert low_bit_ctx_cap("Qwen3.8-27B-UD-IQ2_S:latest", 12.0) == 26758
        assert low_bit_ctx_cap("Qwen3.8-27B-UD-Q2_K_XL:latest", 12.0) == 16000


# ── E2: VRAM-aware max_output expansion ──────────────────────────────────────


class TestVRAMAwareMaxOutput:
    """V18.3.6: E2 REVERTED — max_output stays at 8192 (the raise caused thermal throttling).

    The V18.3.4 raise from 8192 → 12000 caused 47% more generation time → GPU hit 80°C
    → thermal throttle → 300s timeout → model stall → FAILED. The extra VRAM headroom
    is for CONTEXT (E1), not OUTPUT — more output = more generation = more heat.
    Truncation on large chapters is handled by E3 (chunked output), not by raising
    the per-call output cap.

    V18.20.2.0: the cap value now lives in core/llm/iq2_s_profile.py
    (IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT) — the scan follows the constant.
    """

    def test_max_output_stays_at_8192(self):
        """V18.3.6: max_output is capped at 8192 (NOT raised to 12000)."""
        # V0.18 (Phase 5.1): the low-bit max_output cap moved VERBATIM to
        # summarizer_init.py — pin follows (the E3 chunking pins below stayed
        # in summarizer.py and are untouched).
        src = SUMMARIZER_INIT_PATH.read_text(encoding="utf-8")
        assert "REVERTED E2" in src, "V18.3.6 must document the E2 revert"
        assert "_safe_max = IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT" in src, (
            "Must cap at the profile's LOW_BIT_MAX_OUTPUT"
        )
        from core.llm.iq2_s_profile import IQ2_S_PROFILE

        assert IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT == 8192, (
            "The profile constant must stay 8192 (hard constraint: max_output=8192)"
        )
        # The 12000 raise must NOT be in the active code (only in comments)
        assert "_safe_max = 12000" not in src, (
            "V18.3.6: the 12000 raise must be removed (it caused thermal throttling)"
        )


# ── E3: Chunked output ──────────────────────────────────────────────────────


class TestChunkedOutput:
    """V0.3 (master-summary architecture): large chapters get 3 sequential
    calls (master summary → derive bullets → derive exec).

    V18.3.4 (E3) was a 2-call split by section TYPE. V0.3 restructured it to
    split by DEPTH: master summary first, then derive bullets and exec from
    it (the owner's study method). The tests check for the V0.3 architecture.
    """

    def test_source_contains_chunked_output(self):
        """summarizer_chunking.py contains the chunked-output logic (V0.4.19
        de-monolithization step 9/10: moved VERBATIM from summarizer.py —
        pin follows the code)."""
        src = SUMMARIZER_CHUNKING_PATH.read_text(encoding="utf-8")
        assert "_chunked_summarize" in src, "The _chunked_summarize method must exist"
        assert "_build_chunked_prompt" in src, "The _build_chunked_prompt method must exist"
        # The summarizer.py delegate wiring survived the move (MRO):
        sum_src = SUMMARIZER_PATH.read_text(encoding="utf-8")
        assert "chunked_summarize=self._chunked_summarize" in sum_src, (
            "The _summarize_with_model delegate must still wire _chunked_summarize"
        )

    def test_chunking_threshold(self):
        """V0.4: master-summary is the DEFAULT — no chunking threshold needed.
        The old V18.3.5 gate (input > 12000) is removed; chunked_summarize
        (the master-summary 3-call pipeline) runs for ALL chapters."""
        src = PRIMARY_CALL_PATH.read_text(encoding="utf-8")
        assert "count_tokens" in src, "Must use actual token count (not char estimate)"
        assert "V0.4: master-summary" in src, "V0.4: must log the master-summary default"

    def test_v03_master_summary_call(self):
        """V0.3 Call 1/3: master summary (comprehensive thorough) is the first call."""
        # V0.4.19 (de-monolithization step 9/10): the V0.3 call labels moved
        # with _chunked_summarize to summarizer_chunking.py — pin follows.
        src = SUMMARIZER_CHUNKING_PATH.read_text(encoding="utf-8")
        assert "master summary" in src.lower(), "V0.3: must have a master summary call"
        assert "Call 1/3" in src, "V0.3: must label the master summary as Call 1/3"

    def test_v03_bullets_derivation_call(self):
        """V0.3 Call 2/3: bullets derived FROM the master summary."""
        src = SUMMARIZER_CHUNKING_PATH.read_text(encoding="utf-8")
        assert "Call 2/3" in src, "V0.3: must label the bullets derivation as Call 2/3"
        assert "derive_bullets" in src or "derive bullet" in src.lower(), (
            "V0.3: must derive bullets from the master summary"
        )

    def test_v03_exec_derivation_call(self):
        """V0.3 Call 3/3: exec derived FROM the master summary + bullets."""
        src = SUMMARIZER_CHUNKING_PATH.read_text(encoding="utf-8")
        assert "Call 3/3" in src, "V0.3: must label the exec derivation as Call 3/3"
        assert "derive_exec" in src or "derive executive" in src.lower(), (
            "V0.3: must derive exec from the master summary + bullets"
        )

    def test_fallback_to_single_pass_on_chunk1_failure(self):
        """If the master summary call fails, fall back to single-pass."""
        src = PRIMARY_CALL_PATH.read_text(encoding="utf-8")
        assert "falling back" in src.lower(), "Must fall back to 5-in-1 if master-summary fails"


# ── VRAM math verification ──────────────────────────────────────────────────


class TestVRAMMath:
    """Verify the VRAM math is correct (KV cache = ctx × 0.0000614 GB)."""

    def test_kv_at_26758_is_1_64_gb(self):
        """KV cache at 26758 ctx = 1.64 GB (the documented value)."""
        KV_PER_TOKEN_GB = 0.0000614
        kv = 26758 * KV_PER_TOKEN_GB
        assert abs(kv - 1.64) < 0.01, f"KV at 26758 should be ~1.64 GB, got {kv:.2f}"

    def test_kv_at_32768_is_2_01_gb(self):
        """KV cache at 32768 ctx = 2.01 GB (the raised value)."""
        KV_PER_TOKEN_GB = 0.0000614
        kv = 32768 * KV_PER_TOKEN_GB
        assert abs(kv - 2.01) < 0.01, f"KV at 32768 should be ~2.01 GB, got {kv:.2f}"

    def test_total_at_32768_leaves_1_22_gb_headroom(self):
        """IQ2_S 27B at 32768 ctx = 10.78 GB total → 1.22 GB headroom (safe)."""
        KV_PER_TOKEN_GB = 0.0000614
        CUDA_OVERHEAD_GB = 0.4
        IQ2_S_MODEL_GB = 8.37
        GPU_TOTAL_GB = 12.0
        kv = 32768 * KV_PER_TOKEN_GB
        total = IQ2_S_MODEL_GB + CUDA_OVERHEAD_GB + kv
        free = GPU_TOTAL_GB - total
        assert free >= 1.0, f"Headroom at 32768 should be ≥1.0 GB, got {free:.2f}"

    def test_max_output_for_16000_token_chapter_at_32768(self):
        """A 16000-token chapter at 32768 ctx allows ~15768 output tokens."""
        ctx = 32768
        input_tokens = 16000
        safety_margin = 1000
        max_output = ctx - input_tokens - safety_margin
        assert max_output >= 12000, (
            f"For a 16000-token chapter at 32768 ctx, max_output should be ≥12000, got {max_output}"
        )
