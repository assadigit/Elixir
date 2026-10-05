"""V18.20.2.0 (SWOT A1/A2/A3/A13/A16/A20/A21/A22) — LLM-layer fix gates.

Characterization + regression tests for the 8 LLM-layer fixes implemented
in the V18.20.2.0 session (agent IMPL-A, action plan items A1-A3, A13,
A16, A20-A22 — see audit/results/SWOT_V18.20.1.3_system_wide.md):

  A1  VRAM illusion: IQ2_S ctx raise 26758→32768 now requires a REAL
      external VRAM reading (Ollama /api/ps); unavailable → safe 26758.
      (Behavioral matrix also in test_vram_aware_output.py +
      test_ctx_cap_branching.py.)
  A2  Streaming payload divergence: complete_streaming now mirrors
      complete()'s payload semantics (system:"" + keep_alive).
  A3  Streaming-fallback nonstreaming ctx is clamped through the shared
      core/llm/ctx_clamp.py helper (IQ2_S 26758 ceiling on ≤12 GB cards).
  A13 Supervisor: process-wide shared restart rate limit + cumulative
      restart budget + 30s readiness polling (was: fixed 5s sleep).
  A16 structured_llm: provider construction corrected (no more swallowed
      TypeError) but the structured/JSON path stays intentionally OFF
      (behavior preservation — golden cliff avoided); one-time INFO notice.
  A20 Truncation observability: done_reason=="length" → WARNING, text
      unchanged.
  A21 Connection pooling: shared no-proxy session; no os.environ
      proxy pop/restore (thread-unsafe + redundant with trust_env=False).
  A22 Embed batching + keep_alive: one /api/embed call for the whole
      miss-list with per-item fallback; keep_alive in every embed payload.

All tests mock the HTTP layer — no real Ollama required.
Run: pytest tests/test_v18202_llm_fixes.py -v
"""

from __future__ import annotations

import json as _json
import logging
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

_IQ2_S = "Qwen3.8-27B-UD-IQ2_S:latest"
_Q2_K_XL = "Qwen3.8-27B-UD-Q2_K_XL:latest"


class _FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self) -> dict:
        return self._payload


def _make_provider(model: str = _IQ2_S, **kwargs):
    from core.llm.ollama_provider import OllamaProvider

    return OllamaProvider(model=model, log_callback=lambda m, l="INFO": None, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# A1 — external VRAM reading helper
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestExternalGpuFreeGb:
    """OllamaProvider._external_gpu_free_gb: real headroom from /api/ps."""

    def test_sums_size_vram_of_all_loaded_models(self, monkeypatch):
        provider = _make_provider()
        resp = _FakeResponse(
            {
                "models": [
                    {"name": "main", "size_vram": int(9.0 * 1024**3)},
                    {"name": "embedder", "size_vram": int(0.5 * 1024**3)},
                ]
            }
        )
        monkeypatch.setattr("utils.network.safe_ollama_request", lambda *a, **k: resp)
        free = provider._external_gpu_free_gb(12.0)
        assert free is not None
        assert abs(free - 2.5) < 0.01, f"expected 12 − 9.5 = 2.5 GB free, got {free}"

    def test_unavailable_when_ollama_offline(self, monkeypatch):
        def _unreachable(*a, **k):
            raise ConnectionError("refused")

        monkeypatch.setattr("utils.network.safe_ollama_request", _unreachable)
        provider = _make_provider()
        assert provider._external_gpu_free_gb(12.0) is None

    def test_unavailable_on_malformed_response(self, monkeypatch):
        resp = _FakeResponse({"models": "not-a-list"})
        monkeypatch.setattr("utils.network.safe_ollama_request", lambda *a, **k: resp)
        provider = _make_provider()
        # models is not iterable-of-dicts → sum stays 0 → free = total − 0.
        # A malformed list must NOT crash the caller (it is embedded in the
        # hot path). Either a number or None is acceptable; no exception.
        free = provider._external_gpu_free_gb(12.0)
        assert free is None or isinstance(free, float)

    def test_unavailable_without_total_gb(self):
        provider = _make_provider()
        assert provider._external_gpu_free_gb(None) is None
        assert provider._external_gpu_free_gb(0.0) is None

    def test_ignores_missing_size_vram_entries(self, monkeypatch):
        resp = _FakeResponse({"models": [{"name": "loading"}, {"size_vram": 1024**3}]})
        monkeypatch.setattr("utils.network.safe_ollama_request", lambda *a, **k: resp)
        provider = _make_provider()
        free = provider._external_gpu_free_gb(12.0)
        assert free is not None and abs(free - 11.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# A2 — streaming payload mirrors complete()
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestStreamingPayloadParity:
    """complete_streaming() must send the same payload semantics as complete()."""

    def test_streaming_payload_has_system_and_keep_alive(self, monkeypatch):
        provider = _make_provider(model=_IQ2_S, context_tokens=32768)

        class _StreamResp:
            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                return iter(
                    [
                        _json.dumps({"response": "hello ", "done": False}),
                        _json.dumps({"response": "world", "done": True}),
                    ]
                )

        captured = {}

        class _FakeSession:
            def post(self, url, json=None, timeout=None, stream=None):
                captured["url"] = url
                captured["payload"] = json
                return _StreamResp()

        monkeypatch.setattr("utils.network.get_shared_session", lambda: _FakeSession())

        chunks = []
        result = provider.complete_streaming("test prompt", on_chunk=lambda t: chunks.append(t))
        assert result == "hello world"
        payload = captured["payload"]
        # V18.2.37e parity: the Modelfile's system prompt must be overridden.
        assert payload.get("system") == "", (
            "streaming payload must send system='' like complete() does"
        )
        # V18.1 parity: keep_alive must be present (30m policy, not 5m default).
        assert "keep_alive" in payload and payload["keep_alive"], (
            "streaming payload must send keep_alive like complete() does"
        )

    def test_streaming_and_complete_payloads_agree_on_shared_fields(self, monkeypatch):
        """Characterization: for the same inputs, the shared payload fields
        of complete() and complete_streaming() must MATCH (A2's contract)."""
        provider = _make_provider(model=_IQ2_S, context_tokens=32768)

        nonstream_payload = {}

        def _fake_safe(method, url, json=None, timeout=None, **k):
            nonstream_payload.update(json)
            return _FakeResponse({"response": "ok"})

        monkeypatch.setattr("core.llm.ollama_provider.safe_ollama_request", _fake_safe)
        assert provider.complete("same prompt", temperature=0.7, max_tokens=512) == "ok"

        stream_payload = {}

        class _StreamResp:
            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                return iter([_json.dumps({"response": "ok", "done": True})])

        class _FakeSession:
            def post(self, url, json=None, timeout=None, stream=None):
                stream_payload.update(json)
                return _StreamResp()

        monkeypatch.setattr("utils.network.get_shared_session", lambda: _FakeSession())
        assert (
            provider.complete_streaming(
                "same prompt", temperature=0.7, max_tokens=512, on_chunk=lambda t: None
            )
            == "ok"
        )

        # The shared semantic fields must be identical between both paths.
        for field in ("model", "prompt", "system", "keep_alive"):
            assert stream_payload[field] == nonstream_payload[field], (
                f"streaming payload field {field!r} diverges from complete(): "
                f"{stream_payload[field]!r} != {nonstream_payload[field]!r}"
            )
        for opt in ("temperature", "num_predict", "num_ctx", "num_gpu"):
            assert stream_payload["options"][opt] == nonstream_payload["options"][opt], (
                f"streaming options.{opt} diverges from complete()"
            )
        # Only the stream flag itself may differ.
        assert stream_payload["stream"] is True
        assert nonstream_payload["stream"] is False


# ═══════════════════════════════════════════════════════════════════════════
# A3 — streaming-fallback nonstreaming ctx clamp
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestFallbackCtxClamp:
    """_call_ollama_nonstreaming must clamp num_ctx through ctx_clamp."""

    def _capture_ctx(self, monkeypatch, model: str, context_tokens: int, total_gb=None):
        from core.summarisation import llm_dispatcher

        captured = {}

        def _fake_safe(method, url, json=None, timeout=None, **k):
            captured.update(json)
            return _FakeResponse({"response": "ok"})

        monkeypatch.setattr(llm_dispatcher, "safe_ollama_request", _fake_safe)
        if total_gb is not None:
            monkeypatch.setattr("core.llm.ctx_clamp.gpu_total_gb", lambda: total_gb)
        supervisor = MagicMock()
        result = llm_dispatcher._call_ollama_nonstreaming(
            "p",
            model,
            0.7,
            8192,
            context_tokens=context_tokens,
            timeout=60,
            retries=0,
            ollama_base_url="http://localhost:11434",
            supervisor=supervisor,
            log=lambda m, l: None,
        )
        assert result == "ok"
        return captured

    def test_user_set_65536_iq2_s_capped_to_26758_on_12gb(self, monkeypatch):
        """A2 action-plan contract: user-set 65536 + IQ2_S → fallback ctx
        never exceeds 26758."""
        captured = self._capture_ctx(monkeypatch, _IQ2_S, context_tokens=65536, total_gb=12.0)
        assert captured["options"]["num_ctx"] == 26758

    def test_user_set_65536_q2_k_xl_capped_to_16000_on_12gb(self, monkeypatch):
        captured = self._capture_ctx(monkeypatch, _Q2_K_XL, context_tokens=65536, total_gb=12.0)
        assert captured["options"]["num_ctx"] == 16000

    def test_non_low_bit_model_uncapped(self, monkeypatch):
        captured = self._capture_ctx(
            monkeypatch, "llama3.1:8b", context_tokens=65536, total_gb=12.0
        )
        assert captured["options"]["num_ctx"] == 65536

    def test_24gb_card_uncapped(self, monkeypatch):
        captured = self._capture_ctx(monkeypatch, _IQ2_S, context_tokens=65536, total_gb=24.0)
        assert captured["options"]["num_ctx"] == 65536

    def test_clamp_noop_when_gpu_unknown(self, monkeypatch):
        """Sandbox/no-torch: GPU size undetectable → ctx unchanged (documented
        no-op — the cap only applies when the card size is known)."""
        captured = self._capture_ctx(monkeypatch, _IQ2_S, context_tokens=65536, total_gb=None)
        assert captured["options"]["num_ctx"] == 65536

    def test_dispatcher_uses_shared_clamp_not_inline_constants(self):
        """The fallback must route through core.llm.ctx_clamp (no duplicated
        constants) — and the provider's adaptive path must use the same
        helper for the cap VALUE."""
        from core.summarisation import llm_dispatcher

        dispatcher_src = (Path(llm_dispatcher.__file__)).read_text(encoding="utf-8")
        assert "from core.llm.ctx_clamp import clamp_num_ctx" in dispatcher_src
        assert "ctx = clamp_num_ctx(model, max(context_tokens, 16000))" in dispatcher_src
        provider_src = (_project_root / "core" / "llm" / "ollama_provider.py").read_text(
            encoding="utf-8"
        )
        assert "from core.llm.ctx_clamp import low_bit_ctx_cap" in provider_src


# ═══════════════════════════════════════════════════════════════════════════
# A13 — supervisor shared rate limit + restart budget + readiness poll
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestSupervisorSharedRestartState:
    def setup_method(self):
        from core.system.ollama_supervisor import OllamaSupervisor

        OllamaSupervisor.reset_restart_state()

    def teardown_method(self):
        from core.system.ollama_supervisor import OllamaSupervisor

        OllamaSupervisor.reset_restart_state()

    def test_two_instances_share_the_rate_limit(self, monkeypatch):
        """A13 core contract: two coexisting supervisors → only ONE restart
        within the 60s window (the old per-instance limit double-spawned)."""
        from core.system.ollama_supervisor import OllamaSupervisor

        spawns = []
        monkeypatch.setattr(
            "core.system.ollama_supervisor.subprocess.Popen",
            lambda cmd, **k: spawns.append(cmd),
        )
        monkeypatch.setattr(OllamaSupervisor, "is_running", lambda self: True)
        s1 = OllamaSupervisor(restart_command=["ollama", "serve"])
        s2 = OllamaSupervisor(restart_command=["ollama", "serve"])

        assert s1.restart() is True
        assert len(spawns) == 1
        # The second instance within the window must NOT spawn another server.
        assert s2.restart() is False
        assert len(spawns) == 1, "double-spawn: two `ollama serve` within 60s"

    def test_restart_budget_exhaustion_stops_restarting(self, monkeypatch):
        """A13 crash-loop breaker: after MAX_RESTARTS_PER_PROCESS restarts,
        restart() logs CRITICAL and returns False without spawning."""
        from core.system.ollama_supervisor import OllamaSupervisor

        clock = {"t": 1000.0}
        fake_time = types.SimpleNamespace(
            time=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s)
        )
        monkeypatch.setattr("core.system.ollama_supervisor.time", fake_time)

        spawns = []
        monkeypatch.setattr(
            "core.system.ollama_supervisor.subprocess.Popen",
            lambda cmd, **k: spawns.append(cmd),
        )
        monkeypatch.setattr(OllamaSupervisor, "is_running", lambda self: True)
        sup = OllamaSupervisor(restart_command=["ollama", "serve"])

        budget = OllamaSupervisor.MAX_RESTARTS_PER_PROCESS
        results = []
        for _ in range(budget + 2):
            results.append(sup.restart())
            clock["t"] += 61.0  # move past the 60s rate-limit window

        assert results[:budget] == [True] * budget, (
            f"the first {budget} restarts (outside the rate window) must succeed"
        )
        assert results[budget:] == [False, False], "budget exhausted → no further restarts"
        assert len(spawns) == budget, f"exactly {budget} spawns expected, got {len(spawns)}"

    def test_budget_exhaustion_logs_critical(self, monkeypatch, caplog):
        from core.system.ollama_supervisor import OllamaSupervisor

        clock = {"t": 1000.0}
        fake_time = types.SimpleNamespace(time=lambda: clock["t"], sleep=lambda s: None)
        monkeypatch.setattr("core.system.ollama_supervisor.time", fake_time)
        monkeypatch.setattr("core.system.ollama_supervisor.subprocess.Popen", lambda cmd, **k: None)
        monkeypatch.setattr(OllamaSupervisor, "is_running", lambda self: True)
        sup = OllamaSupervisor(restart_command=["ollama", "serve"])
        for _ in range(OllamaSupervisor.MAX_RESTARTS_PER_PROCESS + 1):
            sup.restart()
            clock["t"] += 61.0
        with caplog.at_level(logging.CRITICAL, logger="core.system.ollama_supervisor"):
            assert sup.restart() is False
        assert any("budget exhausted" in r.message.lower() for r in caplog.records), (
            "the crash-loop breaker must log CRITICAL when it refuses to restart"
        )

    def test_post_restart_readiness_poll_instead_of_single_check(self, monkeypatch):
        """A13 readiness: after Popen, is_running() is POLLED (up to 30s)
        instead of a fixed 5s sleep + single check."""
        from core.system.ollama_supervisor import OllamaSupervisor

        sleeps = []
        fake_time = types.SimpleNamespace(time=lambda: 1000.0, sleep=sleeps.append)
        monkeypatch.setattr("core.system.ollama_supervisor.time", fake_time)
        monkeypatch.setattr("core.system.ollama_supervisor.subprocess.Popen", lambda cmd, **k: None)
        # is_running: False, False, then True (Ollama needs 3 polls to come up).
        monkeypatch.setattr(
            OllamaSupervisor, "is_running", MagicMock(side_effect=[False, False, True])
        )
        sup = OllamaSupervisor(restart_command=["ollama", "serve"])
        assert sup.restart() is True
        assert len(sleeps) == 2, "must poll is_running repeatedly (old code: one check after 5s)"

    def test_post_restart_readiness_times_out_at_30s(self, monkeypatch):
        from core.system.ollama_supervisor import OllamaSupervisor

        clock = {"t": 1000.0}

        def _sleep(s):
            clock["t"] += s

        fake_time = types.SimpleNamespace(time=lambda: clock["t"], sleep=_sleep)
        monkeypatch.setattr("core.system.ollama_supervisor.time", fake_time)
        monkeypatch.setattr("core.system.ollama_supervisor.subprocess.Popen", lambda cmd, **k: None)
        monkeypatch.setattr(OllamaSupervisor, "is_running", lambda self: False)
        sup = OllamaSupervisor(restart_command=["ollama", "serve"])
        start = clock["t"]
        assert sup.restart() is False
        polled_secs = clock["t"] - start
        assert polled_secs <= 31.0, f"readiness poll must stop at ~30s, polled {polled_secs}s"

    def test_no_restart_command_consumes_no_budget(self, monkeypatch):
        """Platforms without ollama/systemctl: restart() fails fast without
        consuming the shared rate-limit window or budget."""
        from core.system.ollama_supervisor import OllamaSupervisor

        spawns = []
        monkeypatch.setattr(
            "core.system.ollama_supervisor.subprocess.Popen",
            lambda cmd, **k: spawns.append(cmd),
        )
        # Force detection to find nothing (simulates a box without
        # systemctl AND without an ollama binary).
        monkeypatch.setattr(
            OllamaSupervisor,
            "_detect_restart_command",
            staticmethod(lambda: []),
        )
        sup = OllamaSupervisor()
        assert sup.restart() is False
        assert spawns == []
        assert OllamaSupervisor._SHARED_RESTART_COUNT == 0


# ═══════════════════════════════════════════════════════════════════════════
# A16 — structured path: correct construction, path stays OFF
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestStructuredPathInert:
    def setup_method(self):
        import core.summarisation.structured_llm as sl

        self._sl = sl
        self._orig_flag = sl._STRUCTURED_PATH_ENABLED
        self._orig_notice = sl._STRUCTURED_PATH_NOTICE_LOGGED

    def teardown_method(self):
        self._sl._STRUCTURED_PATH_ENABLED = self._orig_flag
        self._sl._STRUCTURED_PATH_NOTICE_LOGGED = self._orig_notice

    def test_production_flag_is_off(self):
        """The structured/JSON path must remain OFF in production (golden
        cliff avoidance — SWOT Threat T2)."""
        assert self._sl._STRUCTURED_PATH_ENABLED is False

    def test_json_mode_never_passed_in_structured_io_production_path(self):
        """Hard constraint: structured_io's production path must NOT pass
        json_mode=True (the provider JSON mode stays dead)."""
        src = (_project_root / "core" / "llm" / "structured_io.py").read_text(encoding="utf-8")
        assert "json_mode=True" not in src, (
            "structured_io must not activate provider JSON mode (A16 keeps the path inert)"
        )

    def test_returns_none_with_one_time_info_notice(self, caplog):
        """The disabled path returns None (the historical contract) and logs
        ONE INFO notice per process instead of swallowing a TypeError."""
        self._sl._STRUCTURED_PATH_NOTICE_LOGGED = False
        with caplog.at_level(logging.INFO, logger="core.summarisation.structured_llm"):
            result = self._sl.call_llm_structured("p", "m", 0.7, 4096, provider="ollama")
        assert result is None
        assert any("structured path unavailable" in r.message for r in caplog.records), (
            "the one-time INFO notice must be logged"
        )

    def test_notice_fires_exactly_once(self, caplog):
        self._sl._STRUCTURED_PATH_NOTICE_LOGGED = False
        with caplog.at_level(logging.INFO, logger="core.summarisation.structured_llm"):
            for _ in range(3):
                assert self._sl.call_llm_structured("p", "m", 0.7, 4096, provider="ollama") is None
        notices = [r for r in caplog.records if "structured path unavailable" in r.message]
        assert len(notices) == 1, (
            f"the fallback notice must fire once per process, got {len(notices)}"
        )

    def test_construction_uses_real_signature_no_typeerror(self, monkeypatch):
        """With the path ENABLED (test-only), the provider is built with the
        REAL create_provider signature — no model= kwarg → no TypeError —
        and the per-chapter model is set on the provider instance."""
        monkeypatch.setattr(self._sl, "_STRUCTURED_PATH_ENABLED", True)

        calls = {"create_provider": [], "complete_structured": []}

        fake_lp = types.ModuleType("core.llm.llm_provider")

        class _Prov:
            model = ""

        def _create_provider(provider, settings, log_callback=None, supervisor=None):
            calls["create_provider"].append({"provider": provider, "settings": settings})
            return _Prov()

        fake_lp.create_provider = _create_provider
        monkeypatch.setitem(sys.modules, "core.llm.llm_provider", fake_lp)

        fake_settings = types.ModuleType("utils.settings")

        class _Settings:
            def get(self, key, default=None):
                return default

        fake_settings.Settings = _Settings
        monkeypatch.setitem(sys.modules, "utils.settings", fake_settings)

        fake_sio = types.ModuleType("core.llm.structured_io")
        fake_sio.supports_json_mode = lambda provider, model: True

        def _complete_structured(prov, prompt, **k):
            calls["complete_structured"].append({"model_attr": prov.model})
            return {"bullet_points": ["x"]}

        fake_sio.complete_structured = _complete_structured
        monkeypatch.setitem(sys.modules, "core.llm.structured_io", fake_sio)

        result = self._sl.call_llm_structured(
            "prompt", "chapter-model:latest", 0.7, 4096, provider="ollama"
        )
        # The corrected construction succeeds (pre-V18.20.2.0 this raised a
        # TypeError that was silently swallowed → always None).
        assert result == {"bullet_points": ["x"]}
        assert calls["create_provider"] == [
            {"provider": "ollama", "settings": calls["create_provider"][0]["settings"]}
        ]
        assert calls["complete_structured"][0]["model_attr"] == "chapter-model:latest", (
            "the per-chapter model must be set on the provider instance"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A20 — truncation detection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestTruncationDetection:
    def test_done_reason_length_logs_warning_text_unchanged(self, monkeypatch, caplog):
        provider = _make_provider(model=_IQ2_S)
        resp = _FakeResponse(
            {
                "response": "  truncated output text  ",
                "done_reason": "length",
                "prompt_eval_count": 1234,
                "eval_count": 8192,
            }
        )
        monkeypatch.setattr("core.llm.ollama_provider.safe_ollama_request", lambda *a, **k: resp)
        with caplog.at_level(logging.WARNING, logger="core.llm.ollama_provider"):
            result = provider.complete("test prompt")
        # Observability ONLY: the returned text is byte-for-byte what Ollama sent.
        assert result == "truncated output text"
        warnings = [r for r in caplog.records if "truncation_detected" in r.message]
        assert len(warnings) == 1, (
            "done_reason=length must produce exactly one truncation_detected WARNING"
        )
        msg = warnings[0].getMessage()
        assert _IQ2_S in msg and "prompt_eval_count=1234" in msg

    def test_done_reason_stop_no_warning(self, monkeypatch, caplog):
        provider = _make_provider(model=_IQ2_S)
        resp = _FakeResponse({"response": "normal output", "done_reason": "stop"})
        monkeypatch.setattr("core.llm.ollama_provider.safe_ollama_request", lambda *a, **k: resp)
        with caplog.at_level(logging.WARNING, logger="core.llm.ollama_provider"):
            result = provider.complete("test prompt")
        assert result == "normal output"
        assert not [r for r in caplog.records if "truncation_detected" in r.message], (
            "no truncation warning when the model finished normally"
        )

    def test_empty_response_still_retried_even_if_done_reason_length(self, monkeypatch, caplog):
        """Truncation observability must NOT change the empty-response retry
        contract: an EMPTY response still raises the retryable
        ConnectionError, regardless of done_reason."""
        provider = _make_provider(model=_IQ2_S, retries=0)
        resp = _FakeResponse({"response": "", "done_reason": "length"})
        monkeypatch.setattr("core.llm.ollama_provider.safe_ollama_request", lambda *a, **k: resp)
        result = provider.complete("test prompt")
        assert result is None  # empty → retry exhausted → None (old contract)


# ═══════════════════════════════════════════════════════════════════════════
# A21 — connection pooling (shared session, no env mutation)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestConnectionPooling:
    def setup_method(self):
        import utils.network as nw

        self._nw = nw
        self._orig_shared = nw._SHARED_SESSION

    def teardown_method(self):
        self._nw._SHARED_SESSION = self._orig_shared

    def test_shared_session_reused_across_calls(self, monkeypatch):
        """Two safe_ollama_request calls reuse ONE session (the old code
        created AND closed a session per call — zero pooling)."""
        nw = self._nw
        fake_session = MagicMock()
        fake_session.request.return_value = _FakeResponse({})
        nw._SHARED_SESSION = fake_session
        # If the code tried to build a new session, this would raise.
        monkeypatch.setattr(
            nw,
            "create_no_proxy_session",
            lambda: pytest.fail("must reuse the shared session, not create one"),
        )
        nw.safe_ollama_request("GET", "http://localhost:11434/api/tags")
        nw.safe_ollama_request("GET", "http://localhost:11434/api/tags")
        assert fake_session.request.call_count == 2
        fake_session.close.assert_not_called(), "the shared session must never be closed"

    def test_shared_session_is_proxy_immune_and_env_untouched(self, monkeypatch):
        """trust_env=False + empty proxies make the session proxy-immune;
        the HTTP_PROXY env var is NOT popped/restored anymore (the old
        mutation was thread-unsafe under the worker pool)."""
        import os

        nw = self._nw
        monkeypatch.setenv("HTTP_PROXY", "http://evil-proxy:1234")
        monkeypatch.setenv("http_proxy", "http://evil-proxy:1234")
        nw._SHARED_SESSION = None
        try:
            session = nw.get_shared_session()
            assert session.trust_env is False
            assert session.proxies == {"http": "", "https": ""}
            # Route a call through it with request mocked (no real network).
            session.request = MagicMock(return_value=_FakeResponse({}))
            nw.safe_ollama_request("GET", "http://localhost:11434/api/tags")
            # The env mutation is GONE: proxy vars still present after the call.
            assert os.environ.get("HTTP_PROXY") == "http://evil-proxy:1234"
            assert os.environ.get("http_proxy") == "http://evil-proxy:1234"
        finally:
            # Don't leak the real session whose .request we mocked.
            nw._SHARED_SESSION = None

    def test_retries_path_keeps_its_own_session(self, monkeypatch):
        """retries>0 mounts a Retry adapter on a per-call session (mounting
        it on the shared session would mutate pooling for everyone)."""
        nw = self._nw
        fake_session = MagicMock()
        fake_session.request.return_value = _FakeResponse({})
        created = [fake_session]
        monkeypatch.setattr(nw, "create_no_proxy_session", lambda: created[0])
        monkeypatch.setattr(
            nw,
            "get_shared_session",
            lambda: pytest.fail("retries>0 must not use the shared session"),
        )
        resp = nw.safe_ollama_request("GET", "http://x/api/tags", timeout=5, retries=1)
        assert resp.status_code == 200
        fake_session.close.assert_called_once()

    def test_get_shared_session_is_singleton(self):
        nw = self._nw
        nw._SHARED_SESSION = None
        try:
            s1 = nw.get_shared_session()
            s2 = nw.get_shared_session()
            assert s1 is s2
        finally:
            nw._SHARED_SESSION = None


# ═══════════════════════════════════════════════════════════════════════════
# A22 — embed batching + keep_alive
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.characterization
class TestEmbedBatching:
    def _backend(self):
        from core.llm.embedder_backend import OllamaEmbedBackend

        return OllamaEmbedBackend("qwen3-embed:latest")

    def test_batched_call_for_n_texts(self, monkeypatch):
        """N texts on /api/embed → ONE HTTP call with input=[list]."""
        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append({"url": url, "json": json})
            return _FakeResponse({"embeddings": [[0.1] * 8, [0.2] * 8, [0.3] * 8]})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        out = backend.encode(["alpha", "beta", "gamma"])
        assert out.shape == (3, 8)
        assert len(calls) == 1, f"expected ONE batched call, got {len(calls)}"
        assert calls[0]["url"].endswith("/api/embed")
        assert calls[0]["json"]["input"] == ["alpha", "beta", "gamma"]
        assert calls[0]["json"]["model"] == "qwen3-embed:latest"

    def test_batch_payload_has_keep_alive(self, monkeypatch):
        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append(json)
            return _FakeResponse({"embeddings": [[0.1] * 4]})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        backend.encode(["only one"])
        assert "keep_alive" in calls[0] and calls[0]["keep_alive"], (
            "the embed payload must send keep_alive (30m policy) — stops the "
            "5m-default embedder eviction between phases"
        )

    def test_single_string_payload_has_keep_alive(self, monkeypatch):
        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append({"url": url, "json": json})
            return _FakeResponse({"embedding": [0.1] * 4})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        backend.encode("single text")
        assert len(calls) == 1
        assert calls[0]["json"].get("keep_alive"), "single embed needs keep_alive too"

    def test_batch_failure_falls_back_to_per_item(self, monkeypatch):
        """Batched call fails → the per-item loop still produces results
        (graceful degradation; zero-vector semantics unchanged)."""
        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append({"url": url, "json": json})
            if url.endswith("/api/embed") and isinstance(json.get("input"), list):
                raise ConnectionError("batch endpoint exploded")
            return _FakeResponse({"embeddings": [[0.5] * 6]})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        out = backend.encode(["a", "b"])
        assert out.shape == (2, 6)
        # 1 failed batch call + 2 per-item calls.
        assert len(calls) == 3

    def test_batch_count_mismatch_falls_back_to_per_item(self, monkeypatch):
        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append({"url": url, "json": json})
            if url.endswith("/api/embed") and isinstance(json.get("input"), list):
                # server returns fewer embeddings than texts (malformed)
                return _FakeResponse({"embeddings": [[0.5] * 6]})
            return _FakeResponse({"embeddings": [[0.7] * 6]})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        out = backend.encode(["a", "b", "c"])
        assert out.shape == (3, 6)
        assert len(calls) == 4  # 1 mismatched batch + 3 per-item
        assert backend.healthy is True  # graceful degradation, no unhealthy flip

    def test_legacy_embeddings_endpoint_still_per_item_with_keep_alive(self, monkeypatch):
        """Old Ollama (only /api/embeddings): batch 404s → per-item loop →
        each /api/embeddings payload uses the legacy 'prompt' key AND
        carries keep_alive."""
        import requests

        backend = self._backend()
        calls = []

        def _fake_safe(method, url, json=None, timeout=None, **k):
            calls.append({"url": url, "json": json})
            if url.endswith("/api/embed"):
                err = requests.exceptions.HTTPError("404 Client Error: Not Found")
                err.response = _FakeResponse({}, status_code=404)
                raise err
            assert "prompt" in json, "legacy endpoint uses the 'prompt' key"
            return _FakeResponse({"embedding": [0.2] * 5})

        monkeypatch.setattr("utils.network.safe_ollama_request", _fake_safe)
        out = backend.encode(["x", "y"])
        assert out.shape == (2, 5)
        legacy = [c for c in calls if c["url"].endswith("/api/embeddings")]
        assert len(legacy) == 2
        assert all(c["json"].get("keep_alive") for c in legacy)

    def test_empty_list_returns_empty_array(self, monkeypatch):
        backend = self._backend()

        def _fail(*a, **k):
            pytest.fail("no HTTP call expected for an empty list")

        monkeypatch.setattr("utils.network.safe_ollama_request", _fail)
        out = backend.encode([])
        assert out.shape == (0,)
