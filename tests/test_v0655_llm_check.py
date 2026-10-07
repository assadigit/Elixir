"""V0.6.55 (P1c) — the one-click LLM health check pins.

THE FEATURE (the operator's redesign item): a 🔌 Test button that
answers "will the summarize step work, and how FAST?" before a
30-minute run discovers it won't. ``check_llm_for_transcribe``
(core/transcribe/llm_check.py) resolves the backend via
``decide_llamacpp_first`` (which since P1a auto-detects llama.cpp's
shifting ports 8080 → 8000 → 9931), probes a REAL tiny generation on
the llama.cpp path (the P1b speed measurement — the n_gpu_layers
CPU-fallback surfaces with its fix), lists models on the Ollama path,
and honestly reports cloud selections as "not probed locally".

The dict contract: ``ok`` (responded), ``level`` (healthy /
slow-cpu-fallback-suspected / unreachable / info), ``message`` (the
full user-facing text), ``save_url`` (the auto-detected port to
persist — ONLY when the setting still holds the stale default; an
explicit operator URL is never second-guessed).

Hermetic: decide_llamacpp_first, probe_llamacpp_generation and
list_ollama_models are monkeypatched at their module homes (the
V0.6.13 pattern).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class _Settings:
    def __init__(self, values: dict | None = None) -> None:
        self._v = dict(values or {})

    def get(self, key, default=None):
        return self._v.get(key, default)

    def set(self, key, value):
        self._v[key] = value
        return True


class _Decision:  # mirrors LlamacppFirstDecision (a frozen dataclass)
    def __init__(self, use_llamacpp, base_url, model, api_key, note):
        self.use_llamacpp = use_llamacpp
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.note = note


class _ProbeResult:  # mirrors GenerationProbeResult
    def __init__(self, ok, model, base_url, tokens, elapsed_s, tps, verdict, message):
        self.ok = ok
        self.model = model
        self.base_url = base_url
        self.tokens = tokens
        self.elapsed_s = elapsed_s
        self.tps = tps
        self.verdict = verdict
        self.message = message


@pytest.fixture()
def _env(monkeypatch):
    """Patch the three seams llm_check consults; capture the inputs."""
    from core.llm import local_fallback
    import core.llm.llamacpp_provider as lp

    state = {
        "decision": _Decision(False, "", "", "", ""),
        "probe_calls": [],
        "probe_result": _ProbeResult(True, "m", "u", 16, 1.0, 30.0, "healthy", "llama.cpp OK — fast"),
        "ollama_calls": [],
        "ollama_models": ["ollama-model-a", "ollama-model-b"],
    }

    monkeypatch.setattr(
        local_fallback, "decide_llamacpp_first", lambda s, p: state["decision"]
    )
    monkeypatch.setattr(
        lp,
        "probe_llamacpp_generation",
        lambda base, key, model, log_callback=None, **kw: (
            state["probe_calls"].append((base, key, model)) or state["probe_result"]
        ),
    )

    def _fake_list(url, timeout=5):
        state["ollama_calls"].append((url, timeout))
        return list(state["ollama_models"])

    # utils.network.list_ollama_models is imported inside the function —
    # patch at its module home so the deferred import picks the fake.
    import utils.network as un

    monkeypatch.setattr(un, "list_ollama_models", _fake_list)
    return state


from core.transcribe.llm_check import check_llm_for_transcribe  # noqa: E402


class TestV0655LlmCheckLlamacppPath:
    def test_healthy_gpu_backend_reports_ok(self, _env):
        _env["decision"] = _Decision(
            True, "http://127.0.0.1:8000/v1", "Ternary-Bonsai-2-27B", "local",
            "llama.cpp detected at http://127.0.0.1:8000/v1 — routing to it",
        )
        out = check_llm_for_transcribe(_Settings())
        assert out["ok"] is True
        assert out["level"] == "healthy"
        assert out["backend"] == "llama.cpp"
        assert out["base_url"] == "http://127.0.0.1:8000/v1"
        assert out["model"] == "Ternary-Bonsai-2-27B"
        assert out["tps"] == 30.0
        # the decision note rides along (the operator sees WHY it routed)
        assert "8000" in out["message"]
        # the probe was pointed at the DETECTED url + model
        assert _env["probe_calls"] == [("http://127.0.0.1:8000/v1", "local", "Ternary-Bonsai-2-27B")]

    def test_slow_cpu_fallback_carries_the_n_gpu_layers_guidance(self, _env):
        """THE P1 REQUIREMENT: the GPU-fit failure (server fell back to
        CPU, still answers) surfaces as a WARNING-level result whose
        message names VRAM / n_gpu_layers / the restart fix."""
        _env["decision"] = _Decision(
            True, "http://127.0.0.1:8000/v1", "Ternary-Bonsai-2-27B", "local", "note"
        )
        _env["probe_result"] = _ProbeResult(
            True, "Ternary-Bonsai-2-27B", "u", 16, 10.0, 1.5,
            "slow-cpu-fallback-suspected",
            "llama.cpp responded but generated only ~1.5 tokens/s ... "
            "restart llama-server with a lower --n-gpu-layers value",
        )
        out = check_llm_for_transcribe(_Settings())
        assert out["ok"] is True  # responded — the SPEED is the finding
        assert out["level"] == "slow-cpu-fallback-suspected"
        low = out["message"].lower()
        assert "n-gpu-layers" in low or "n_gpu_layers" in low
        assert "restart" in low

    def test_unreachable_llamacpp_is_ok_false_with_reason(self, _env):
        _env["decision"] = _Decision(True, "http://127.0.0.1:8000/v1", "m", "local", "note")
        _env["probe_result"] = _ProbeResult(
            False, "m", "u", 0, 0.0, 0.0, "unreachable",
            "llama.cpp at http://127.0.0.1:8000/v1 could not be probed: ConnectionError",
        )
        out = check_llm_for_transcribe(_Settings())
        assert out["ok"] is False
        assert out["level"] == "unreachable"

    def test_auto_detected_port_offers_save_url_only_on_default_setting(self, _env):
        """THE P1a INTERPLAY: llama.cpp auto-detected on :8000 while the
        setting still holds the stale 8080 default → save_url is the
        detected URL (the dialog persists it after telling the
        operator). An EXPLICIT operator URL is never offered for
        overwrite."""
        _env["decision"] = _Decision(
            True, "http://127.0.0.1:8000/v1", "m", "local", "auto-detected"
        )
        # stale default setting → save offered
        out = check_llm_for_transcribe(_Settings({}))
        assert out["save_url"] == "http://127.0.0.1:8000/v1"
        assert "saves http://127.0.0.1:8000/v1" in out["message"]
        # explicit operator URL (8500) → never second-guessed
        out2 = check_llm_for_transcribe(
            _Settings({"summarisation.llamacpp_base_url": "http://127.0.0.1:8500/v1"})
        )
        assert out2["save_url"] is None

    def test_default_port_live_never_offers_save(self, _env):
        _env["decision"] = _Decision(
            True, "http://127.0.0.1:8080/v1", "m", "local", "note"
        )
        out = check_llm_for_transcribe(_Settings({}))
        assert out["save_url"] is None


class TestV0655LlmCheckOllamaPath:
    def test_no_llamacpp_ollama_alive_reports_models(self, _env):
        _env["decision"] = _Decision(
            False, "", "", "", "llama.cpp not reachable — using the configured backend"
        )
        out = check_llm_for_transcribe(
            _Settings({}), ollama_url="http://localhost:11434"
        )
        assert out["ok"] is True
        assert out["backend"] == "ollama"
        assert out["model"] == "ollama-model-a"
        assert "2 model(s)" in out["message"]
        assert _env["ollama_calls"] == [("http://localhost:11434", 5)]

    def test_no_llamacpp_ollama_dead_is_unreachable_with_fix(self, _env):
        _env["decision"] = _Decision(False, "", "", "", "note")
        _env["ollama_models"] = []
        out = check_llm_for_transcribe(_Settings({}))
        assert out["ok"] is False
        assert out["level"] == "unreachable"
        assert "ollama serve" in out["message"].lower()
        # the auto-probed ports are advertised in the fix line
        assert "8080/8000/9931" in out["message"]

    def test_ollama_probe_exception_is_data_not_crash(self, _env):
        import utils.network as un

        def _boom(url, timeout=5):
            raise RuntimeError("proxy garbage")

        monkeypatch_holder = pytest.MonkeyPatch()
        monkeypatch_holder.setattr(un, "list_ollama_models", _boom)
        try:
            _env["decision"] = _Decision(False, "", "", "", "note")
            out = check_llm_for_transcribe(_Settings({}))
            assert out["ok"] is False
            assert out["level"] == "unreachable"
        finally:
            monkeypatch_holder.undo()


class TestV0655LlmCheckCloudPath:
    def test_cloud_selection_is_honestly_not_probed(self, _env):
        _env["decision"] = _Decision(False, "", "", "", "")
        out = check_llm_for_transcribe(
            _Settings({"summarisation.provider": "openrouter"})
        )
        assert out["ok"] is True
        assert out["level"] == "info"
        assert out["backend"] == "openrouter"
        assert "no local probe" in out["message"].lower()
        # and NOTHING was probed
        assert _env["probe_calls"] == []
        assert _env["ollama_calls"] == []


def test_module_is_importable_without_qt():
    """core/transcribe/llm_check.py is pure Python at import time (the
    deferred heavy imports live inside the function bodies) — the
    hermetic-test gate."""
    import core.transcribe.llm_check as m

    assert isinstance(m, types.ModuleType)
