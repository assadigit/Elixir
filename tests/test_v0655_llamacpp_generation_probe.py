"""V0.6.55 (P1b) — llama.cpp generation-speed probe / CPU-fallback pins.

THE PROBLEM (the operator's rig, V0.6.54 CHANGELOG note #3): the rig's
``llama-server`` console shows the GPU-fit failure — ``n_gpu_layers=99``
layers of a 27B model do not fit in the card's VRAM — and llama-server
falls back to CPU while STILL listening. The app cannot read the
server's console, so today this failure is invisible: every request
succeeds, just 10-30x slower (a 27B on CPU generates ~1-2 tok/s). The
transcribe summary then takes 10+ minutes with a frozen status label
and the operator has no idea WHY.

THE FIX (this session, core/llm/llamacpp_provider.py): a MEASUREMENT
the app CAN take — generation speed. ``probe_llamacpp_generation()``
runs a tiny timed generation through the REAL streaming path (the same
``_chat_streaming`` the summary uses) and measures tokens/second
between stream chunks. ``classify_generation_speed()`` maps the number
to a verdict; below ``LLAMACPP_SLOW_TOKS_PER_SEC`` (5.0) the verdict is
"slow-cpu-fallback-suspected" and the message says exactly what the
operator should do: restart llama-server with a lower ``-ngl`` /
``--n-gpu-layers`` value or a smaller quant — the actionable version of
the console warning the app can never see.

Layers:
1. classify_generation_speed — pure.
2. compute_generation_tps — pure (sample-span vs whole-call fallback).
3. build_generation_probe_message — pure (the wording the dialog shows).
4. probe_llamacpp_generation — the integration probe (hermetic: the
   SSE transport is monkeypatched; the clock is the module's
   ``_monotonic`` indirection, also monkeypatched).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm import llamacpp_provider as _lp  # noqa: E402 — path bootstrap above


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — classification (pure)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655ClassifySpeed:
    def test_slow_threshold_is_five_toks_per_sec(self):
        """The threshold is pinned: dense 27B quants on a 12 GB GPU
        generate 20-100+ tok/s; on CPU ~1-2 tok/s (the provider's own
        LLAMACPP_MIN_TOKENS_PER_SEC floor of 2.0 documents the CPU
        floor). 5.0 sits clearly between the two regimes."""
        assert _lp.LLAMACPP_SLOW_TOKS_PER_SEC == 5.0

    def test_below_threshold_is_cpu_fallback_suspected(self):
        assert (
            _lp.classify_generation_speed(1.5)
            == "slow-cpu-fallback-suspected"
        )
        assert _lp.classify_generation_speed(4.9) == "slow-cpu-fallback-suspected"

    def test_at_and_above_threshold_is_healthy(self):
        assert _lp.classify_generation_speed(5.0) == "healthy"
        assert _lp.classify_generation_speed(47.3) == "healthy"

    def test_zero_or_negative_is_unknown(self):
        assert _lp.classify_generation_speed(0.0) == "unknown"
        assert _lp.classify_generation_speed(-1.0) == "unknown"


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — tokens/second math (pure)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655ComputeTps:
    def test_uses_the_sample_span_when_two_or_more_samples(self):
        """With >= 2 chunk samples the measurement window is FIRST →
        LAST sample (excludes connection + prompt-eval latency, so a
        cold first token does not poison the rate)."""
        # 4 chunks: cumulative chars 0 / 100 / 200 / 400 over 8 s span
        # (first→last sample) → 400 chars ≈ 100 tokens in 8 s = 12.5 tok/s.
        samples = [(0.0, 0), (0.0, 100), (4.0, 200), (8.0, 400)]
        tps = _lp.compute_generation_tps(samples, final_chars=400, elapsed_s=60.0)
        assert tps == pytest.approx(400 / 4 / 8.0)

    def test_falls_back_to_whole_call_when_no_samples(self):
        """A generation fast enough to fit inside the 0.5 s chunk-throttle
        yields ZERO on_chunk samples — the whole-call elapsed (which
        includes prompt eval) is the conservative fallback."""
        tps = _lp.compute_generation_tps([], final_chars=64, elapsed_s=2.0)
        assert tps == pytest.approx(64 / 4 / 2.0)

    def test_falls_back_to_whole_call_with_one_sample(self):
        tps = _lp.compute_generation_tps([(1.0, 64)], final_chars=64, elapsed_s=4.0)
        assert tps == pytest.approx(64 / 4 / 4.0)

    def test_zero_elapsed_is_unknown_not_division_error(self):
        assert _lp.compute_generation_tps([], final_chars=64, elapsed_s=0.0) == 0.0
        assert _lp.compute_generation_tps([(0.0, 0), (0.0, 64)], 64, 0.0) == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — the message (pure; the wording the operator reads)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655ProbeMessage:
    def test_slow_message_names_vram_ngl_and_cpu(self):
        """The actionable CPU-fallback message must contain: the measured
        rate, VRAM, n_gpu_layers, the CPU fallback explanation, and the
        restart fix (-ngl / --n-gpu-layers)."""
        msg = _lp.build_generation_probe_message(
            verdict="slow-cpu-fallback-suspected",
            tps=1.8,
            model="Ternary-Bonsai-2-27B-Instruct-Vision",
            base_url="http://127.0.0.1:8000/v1",
            detail="",
        )
        low = msg.lower()
        assert "1.8" in msg
        assert "ternary-bonsai-2-27b-instruct-vision" in low
        assert "vram" in low
        assert "n_gpu_layers" in low
        assert "cpu" in low
        assert "--n-gpu-layers" in low or "-ngl" in low
        assert "restart" in low

    def test_healthy_message_reports_the_rate(self):
        msg = _lp.build_generation_probe_message(
            verdict="healthy",
            tps=42.0,
            model="m",
            base_url="http://127.0.0.1:8000/v1",
            detail="",
        )
        low = msg.lower()
        assert "42" in msg
        assert "llama.cpp" in low
        assert len(low) > 20  # a real message, not the empty-string pass-through

    def test_unreachable_message_carries_the_detail(self):
        msg = _lp.build_generation_probe_message(
            verdict="unreachable",
            tps=0.0,
            model="m",
            base_url="http://127.0.0.1:8000/v1",
            detail="connection refused",
        )
        assert "connection refused" in msg


# ═════════════════════════════════════════════════════════════════════════════
# Layer 4 — the probe itself (hermetic: fake SSE transport + fake clock)
# ═════════════════════════════════════════════════════════════════════════════


class _FakeClock:
    """Deterministic monotonic clock for the probe tests."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _FakeStreaming:
    """Monkeypatch stand-in for LlamaCppProvider._chat_streaming that
    records the payload and drives on_chunk with a scripted timeline."""

    def __init__(self, script: list[tuple[float, int]], text: str, clock: _FakeClock):
        self.script = list(script)  # (advance_seconds, cumulative_chars)
        self.text = text
        self.clock = clock
        self.payloads: list[dict] = []
        self.timeouts: list[int | None] = []
        self.calls = 0

    def __call__(self, payload: dict, on_chunk, timeout=None):
        self.calls += 1
        self.payloads.append(dict(payload))
        self.timeouts.append(timeout)
        for advance, cum_chars in self.script:
            self.clock.advance(advance)
            if on_chunk is not None:
                on_chunk(self.text[:cum_chars])
        return self.text


def _install(monkeypatch, fake: _FakeStreaming, clock: _FakeClock):
    monkeypatch.setattr(_lp.LlamaCppProvider, "_chat_streaming", fake)
    monkeypatch.setattr(_lp, "_monotonic", clock)


class TestV0655ProbeGeneration:
    def test_gpu_class_speed_is_healthy(self, monkeypatch):
        """16 probe tokens (64 chars) streamed in ~1.6 s of chunk span →
        ~10 tok/s → healthy verdict, ok=True."""
        clock = _FakeClock()
        fake = _FakeStreaming(
            script=[(0.2, 16), (0.4, 32), (0.5, 48), (0.5, 64)],
            text="x" * 64,
            clock=clock,
        )
        _install(monkeypatch, fake, clock)
        result = _lp.probe_llamacpp_generation(
            "http://127.0.0.1:8000/v1", "local", "Ternary-Bonsai-2-27B"
        )
        assert result.ok is True
        assert result.verdict == "healthy"
        assert result.tps >= 5.0
        assert "8000" in result.message or "llama.cpp" in result.message.lower()

    def test_cpu_class_speed_is_cpu_fallback_suspected(self, monkeypatch):
        """THE OPERATOR'S RIG CASE: ~1.5 tok/s → the verdict is the CPU
        fallback suspicion and the message carries the n_gpu_layers fix."""
        clock = _FakeClock()
        # 60 chars ≈ 15 tokens over ~10 s span → 1.5 tok/s.
        fake = _FakeStreaming(
            script=[(2.0, 16), (2.0, 32), (2.0, 44), (2.0, 56), (2.0, 60)],
            text="y" * 60,
            clock=clock,
        )
        _install(monkeypatch, fake, clock)
        result = _lp.probe_llamacpp_generation(
            "http://127.0.0.1:8000/v1", "local", "Ternary-Bonsai-2-27B"
        )
        assert result.ok is True  # the server RESPONDED — speed is the finding
        assert result.verdict == "slow-cpu-fallback-suspected"
        assert "vram" in result.message.lower()
        assert "n_gpu_layers" in result.message.lower()

    def test_unreachable_transport_is_ok_false_with_reason(self, monkeypatch):
        clock = _FakeClock()

        def _boom(self, payload, on_chunk, timeout=None):
            raise _lp._requests.exceptions.ConnectionError("refused")

        monkeypatch.setattr(_lp.LlamaCppProvider, "_chat_streaming", _boom)
        monkeypatch.setattr(_lp, "_monotonic", clock)
        result = _lp.probe_llamacpp_generation(
            "http://127.0.0.1:8000/v1", "local", "m"
        )
        assert result.ok is False
        assert result.verdict == "unreachable"
        assert "refused" in result.message

    def test_probe_requests_the_pinned_token_budget_and_streams(self, monkeypatch):
        """The probe's payload: the pinned small token budget (a REAL
        generation, not a 1-token smoke ping — the rate needs tokens)
        with stream=True and the caller's model."""
        clock = _FakeClock()
        fake = _FakeStreaming(
            script=[(0.1, 32)], text="z" * 32, clock=clock
        )
        _install(monkeypatch, fake, clock)
        _lp.probe_llamacpp_generation("http://127.0.0.1:8000/v1", "local", "model-x")
        payload = fake.payloads[0]
        assert payload["model"] == "model-x"
        assert payload["max_tokens"] == _lp.LLAMACPP_PROBE_TOKENS
        assert payload["stream"] is True

    def test_probe_token_budget_is_small_but_real(self):
        """16 tokens: enough to measure a rate, cheap enough for a
        button click (~1-2 s on GPU, ~10 s on the CPU fallback — which
        is itself the diagnostic)."""
        assert _lp.LLAMACPP_PROBE_TOKENS == 16

    def test_result_is_immutable_dataclass(self, monkeypatch):
        clock = _FakeClock()
        fake = _FakeStreaming(script=[(0.1, 32)], text="z" * 32, clock=clock)
        _install(monkeypatch, fake, clock)
        result = _lp.probe_llamacpp_generation("http://u/v1", "local", "m")
        with pytest.raises(Exception):
            result.tps = 99.0  # frozen dataclass — no accidental mutation


# ═════════════════════════════════════════════════════════════════════════════
# Layer 5 — module importability without heavy deps (the conftest gate)
# ═════════════════════════════════════════════════════════════════════════════


def test_module_imports_without_tiktoken_runtime():
    """The provider module must stay importable in this sandbox (the
    conftest tiktoken stub + the requests package) — the V0.6.54 sweep
    precedent that keeps these pins runnable."""
    assert isinstance(_lp, types.ModuleType)
    assert hasattr(_lp, "probe_llamacpp_generation")
    assert hasattr(_lp, "classify_generation_speed")
    assert hasattr(_lp, "build_generation_probe_message")
    assert hasattr(_lp, "compute_generation_tps")
