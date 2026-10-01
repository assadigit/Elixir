"""V0.6.12 — the llama.cpp-first local-LLM fallback policy.

THE USER REPORT (the Packets of Knowledge session): the tool called
``http://localhost:11434/api/generate`` while llama-server was the
backend actually running — the raw-request call sites read only
``summarisation.endpoint`` (default :11434) and never consult the
``summarisation.llamacpp_*`` block — and the failure surfaced as a raw
urllib3 HTTPConnectionPool blob (WinError 10061, connection actively
refused). THE POLICY the operator set: Ollama is the always-on default
(auto-start); llama-server is started deliberately, only when needed —
so "llama.cpp is up" MEANS "route to it and the model it serves";
otherwise fall back to the configured backend.

Layers:
1. The decision module itself (core/llm/local_fallback.py) — hermetic:
   the /v1/models probe is monkeypatched at the module name, the probe
   cache cleared per test.
2. PacketGenerator._call_llm routing (the reported call site) — the
   shared session is faked, the probe monkeypatched, Settings through
   the ``Settings._test_override`` DI hook.
3. The new-output riders' OutputGeneratorBase._call_llm_once — the
   same disease found by inspection while wiring the policy: provider
   "llamacpp" (the fresh-install DEFAULT) matched NO branch and
   silently returned None — the briefing/podcast/flashcards riders
   quietly produced nothing on a llama.cpp rig.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── shared hermetic helpers ─────────────────────────────────────────────────


class _SettingsStub:
    """The duck-type the decision module + call sites need (``get``/``set``).

    Absent keys fall through to the CALLER's default (the same
    semantics the real Settings has for these reads), so tests exercise
    the production defaults by omission.
    """

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)

    def set(self, key: str, value) -> bool:
        self._v[key] = value
        return True


class _ProbeSpy:
    """Monkeypatch stand-in for list_llamacpp_models that records calls."""

    def __init__(self, models: list[str] | None = None, raise_on_call: bool = False) -> None:
        self.models = list(models or [])
        self.raise_on_call = raise_on_call
        self.calls: list[tuple[str, str, int]] = []

    def __call__(self, base_url: str, api_key: str, timeout: int = 10) -> list[str]:
        self.calls.append((base_url, api_key, timeout))
        if self.raise_on_call:
            raise RuntimeError("probe exploded")
        return list(self.models)


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    """Every test starts with an empty probe cache (and leaves it empty)."""
    from core.llm import local_fallback

    local_fallback.clear_llamacpp_probe_cache()
    yield
    local_fallback.clear_llamacpp_probe_cache()


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — the decision module (core/llm/local_fallback.py)
# ═════════════════════════════════════════════════════════════════════════════


class TestDecideLlamacppFirst:
    def _decide(
        self, monkeypatch, provider: str, values: dict | None = None, spy: _ProbeSpy | None = None
    ):
        from core.llm import local_fallback

        spy = spy or _ProbeSpy()
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", spy)
        return local_fallback.decide_llamacpp_first(_SettingsStub(values), provider), spy

    def test_cloud_providers_are_never_probed(self, monkeypatch):
        """A cloud selection is a deliberate non-local choice — the policy
        must not fire (and must not even PROBE) for any of them."""
        for provider in (
            "cloud",
            "openrouter",
            "openai",
            "openai_compatible",
            "freellmapi",
            "claude",
        ):
            decision, spy = self._decide(
                monkeypatch,
                provider,
                values={
                    "summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1",
                },
            )
            assert decision.use_llamacpp is False, provider
            assert decision.note == "", provider
            assert spy.calls == [], provider

    def test_policy_off_never_probes(self, monkeypatch):
        """local.llamacpp_first=false is the kill switch — straight
        passthrough, zero probes (the pre-V0.6.12 behavior)."""
        decision, spy = self._decide(monkeypatch, "ollama", values={"local.llamacpp_first": False})
        assert decision.use_llamacpp is False
        assert decision.note == ""
        assert spy.calls == []

    def test_ollama_plus_live_llamacpp_takes_over(self, monkeypatch):
        """THE POLICY: the configured provider is Ollama but a llama.cpp
        server is up → the call routes to it with its served model and
        API key (the operator's 'llama.cpp on = I want that model')."""
        spy = _ProbeSpy(models=["served-model"])
        decision, _ = self._decide(
            monkeypatch,
            "ollama",
            values={
                "summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1",
                "summarisation.llamacpp_model": "served-model",
                "summarisation.llamacpp_api_key": "sekrit",
            },
            spy=spy,
        )
        assert decision.use_llamacpp is True
        assert decision.base_url == "http://127.0.0.1:8080/v1"
        assert decision.model == "served-model"
        assert decision.api_key == "sekrit"
        assert "routing to it" in decision.note
        assert spy.calls == [("http://127.0.0.1:8080/v1", "sekrit", 5)]  # UI-probe budget

    def test_detected_model_wins_over_configured(self, monkeypatch):
        """The V0.4.30 factory precedent, kept identical: a llama-server
        serving a DIFFERENT model than the configured name is addressed
        by what it actually serves (and the note says so)."""
        spy = _ProbeSpy(models=["actually-served"])
        decision, _ = self._decide(
            monkeypatch,
            "ollama",
            values={
                "summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1",
                "summarisation.llamacpp_model": "stale-configured-name",
            },
            spy=spy,
        )
        assert decision.use_llamacpp is True
        assert decision.model == "actually-served"
        assert "configured 'stale-configured-name' overridden" in decision.note

    def test_llamacpp_provider_plus_live_llamacpp(self, monkeypatch):
        """provider=llamacpp + the server actually up → takeover with the
        llamacpp URL (pre-V0.6.12 the raw-request sites never read the
        llamacpp_* block at all — the 'not connected to llama.cpp' bug)."""
        spy = _ProbeSpy(models=["bonsai"])
        decision, _ = self._decide(
            monkeypatch,
            "llamacpp",
            values={"summarisation.llamacpp_base_url": "http://127.0.0.1:8081/v1"},
            spy=spy,
        )
        assert decision.use_llamacpp is True
        assert decision.base_url == "http://127.0.0.1:8081/v1"
        assert decision.model == "bonsai"

    def test_llamacpp_down_falls_back_to_configured(self, monkeypatch):
        """llama.cpp off → NO takeover, empty routing fields, and the note
        names the dead URL (the call site keeps its configured backend —
        Ollama, the always-on default)."""
        spy = _ProbeSpy(models=[])
        decision, _ = self._decide(
            monkeypatch,
            "ollama",
            values={"summarisation.llamacpp_base_url": "http://127.0.0.1:8080/v1"},
            spy=spy,
        )
        assert decision.use_llamacpp is False
        assert decision.base_url == "" and decision.model == "" and decision.api_key == ""
        assert "not reachable at http://127.0.0.1:8080/v1" in decision.note

    def test_probe_result_cached_within_ttl(self, monkeypatch):
        """Two decisions inside the TTL window share ONE probe (the
        packets generator resolves once per packet — 5+ times a run)."""
        spy = _ProbeSpy(models=["m"])
        for _ in range(3):
            self._decide(monkeypatch, "ollama", spy=spy)
        assert len(spy.calls) == 1

    def test_cache_clear_forces_reprobe(self, monkeypatch):
        from core.llm import local_fallback

        spy = _ProbeSpy(models=["m"])
        self._decide(monkeypatch, "ollama", spy=spy)
        local_fallback.clear_llamacpp_probe_cache()
        self._decide(monkeypatch, "ollama", spy=spy)
        assert len(spy.calls) == 2

    def test_stale_cache_entry_reprobes(self, monkeypatch):
        """A cache entry older than the TTL does not satisfy the probe —
        a llama-server started mid-session is picked up on the next
        resolution after expiry."""
        import time as _time

        from core.llm import local_fallback

        spy = _ProbeSpy(models=["m"])
        self._decide(monkeypatch, "ollama", spy=spy)
        # Age the cached entry past the TTL (direct injection — the same
        # shape _probe_llamacpp writes).
        with local_fallback._PROBE_LOCK:
            key = ("http://127.0.0.1:8080/v1", "local")
            local_fallback._PROBE_CACHE[key] = (
                _time.monotonic() - local_fallback._PROBE_CACHE_TTL_S - 1,
                ["m"],
            )
        self._decide(monkeypatch, "ollama", spy=spy)
        assert len(spy.calls) == 2

    def test_probe_exception_means_dead(self, monkeypatch):
        """A raising probe never escapes the decision — 'dead' is the
        answer (fail-safe to the configured backend)."""
        spy = _ProbeSpy(raise_on_call=True)
        decision, _ = self._decide(monkeypatch, "ollama", spy=spy)
        assert decision.use_llamacpp is False
        assert "not reachable" in decision.note

    def test_unknown_and_blank_providers_are_local(self, monkeypatch):
        """Garbage/blank provider names get the LOCAL treatment (probe,
        fallback) — matching create_provider's default-to-ollama."""
        from core.llm import local_fallback

        for provider in ("banana", "", "  ", "LMSTUDIO"):
            local_fallback.clear_llamacpp_probe_cache()  # per-provider probe count
            spy = _ProbeSpy(models=[])
            decision, _ = self._decide(monkeypatch, provider, spy=spy)
            assert decision.use_llamacpp is False, provider
            assert len(spy.calls) == 1, provider

    def test_defaults_when_no_llamacpp_settings(self, monkeypatch):
        """Absent llamacpp_* keys → the production defaults: the 8080 URL,
        the 'local' key, the 5 s UI-probe budget."""
        spy = _ProbeSpy(models=[])
        self._decide(monkeypatch, "ollama", spy=spy)
        assert spy.calls == [("http://127.0.0.1:8080/v1", "local", 5)]


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — PacketGenerator._call_llm routing (the reported call site)
# ═════════════════════════════════════════════════════════════════════════════


class _FakeStreamedResponse:
    """The iter_lines/raise_for_status/close contract _call_llm needs."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self.closed = False

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def close(self) -> None:
        self.closed = True


def _sse_lines(text: str = "hello world") -> list[str]:
    """OpenAI-compatible SSE chunks carrying ``text`` then [DONE]."""
    mid = len(text) // 2
    parts = [text[:mid], text[mid:]]
    return [f'data: {{"choices": [{{"delta": {{"content": "{p}"}}}}]}}' for p in parts if p] + [
        "data: [DONE]"
    ]


_NDJSON_LINES = ['{"response": "hi ", "done": false}', '{"response": "there", "done": true}']


class _FakeSession:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


class _PacketsHarness:
    """A PacketGenerator + faked transport + faked probe + Settings override."""

    def __init__(self, monkeypatch, values: dict, probe_models: list[str]) -> None:
        import utils.network as net_mod
        from utils.settings import Settings

        # Settings._test_override DI hook (the repeatability_run pattern;
        # _call_llm constructs Settings() internally). monkeypatch sets it
        # now and restores the PRE-test value at teardown.
        self.settings = _SettingsStub(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        self.spy = _ProbeSpy(models=probe_models)
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)

        self.session = _FakeSession(response=_FakeStreamedResponse(_sse_lines()))
        monkeypatch.setattr(net_mod, "session_for_url", lambda url: self.session)

        from core.outputs.packets.generator import PacketGenerator

        self.logs: list[tuple[str, str]] = []
        self.gen = PacketGenerator(
            request=None, log_callback=lambda m, level="INFO": self.logs.append((level, m))
        )

    def call(self, prompt: str = "hi", model: str = "req-model", provider: str = "") -> str | None:
        _provider = provider or str(self.settings.get("summarisation.provider", "ollama"))
        return self.gen._call_llm(prompt, model, _provider, 0.1)

    def info_logs(self) -> list[str]:
        return [m for _lvl, m in self.logs]


_LLAMACPP_URL = "http://127.0.0.1:8080/v1"
_OLLAMA_ENDPOINT = "http://localhost:11434/v1"


class TestPacketsCallLlmRouting:
    def test_provider_llamacpp_with_live_server_routes_to_llamacpp_url(self, monkeypatch):
        """THE REPORT ('Packets of Knowledge is not connected to llama.cpp'):
        provider=llamacpp used to call the :11434 endpoint regardless —
        now a live llama-server gets the call, with its DETECTED model
        and the bearer key."""
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "llamacpp",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,  # the stale pre-V0.6.12 default
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
                "summarisation.llamacpp_model": "configured-name",
                "summarisation.llamacpp_api_key": "sekrit",
            },
            probe_models=["detected-x"],
        )
        assert h.call() == "hello world"
        url, kwargs = h.session.calls[0]
        assert url == f"{_LLAMACPP_URL}/chat/completions"
        assert kwargs["json"]["model"] == "detected-x"  # detected wins (V0.4.30)
        assert kwargs["headers"] == {"Authorization": "Bearer sekrit"}

    def test_provider_ollama_with_live_llamacpp_takes_over(self, monkeypatch):
        """THE POLICY: the saved provider is Ollama but llama-server is up
        (the operator started it deliberately) → the packets calls route
        to llama.cpp with its served model."""
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-27b"],
        )
        assert h.call() == "hello world"
        url, kwargs = h.session.calls[0]
        assert url == f"{_LLAMACPP_URL}/chat/completions"
        assert kwargs["json"]["model"] == "served-27b"
        assert kwargs["headers"]["Authorization"] == "Bearer local"

    def test_llamacpp_down_uses_configured_ollama_endpoint(self, monkeypatch):
        """llama.cpp off → the configured backend runs, byte-identical to
        V0.6.11 (the native :11434 /api/generate branch, no auth header)."""
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,
            },
            probe_models=[],
        )
        h.session.response = _FakeStreamedResponse(_NDJSON_LINES)
        assert h.call() == "hi there"
        url, kwargs = h.session.calls[0]
        assert url == "http://localhost:11434/api/generate"
        assert "headers" not in kwargs
        assert kwargs["json"]["model"] == "req-model"

    def test_custom_endpoint_openai_compat_branch_unchanged(self, monkeypatch):
        """A non-11434 endpoint with llama.cpp down keeps the exact
        pre-V0.6.12 openai-compat POST (no explicit headers)."""
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "llamacpp",
                "summarisation.endpoint": "http://localhost:3031/v1",
            },
            probe_models=[],
        )
        assert h.call() == "hello world"
        url, kwargs = h.session.calls[0]
        assert url == "http://localhost:3031/v1/chat/completions"
        assert "headers" not in kwargs

    def test_cloud_provider_never_probes(self, monkeypatch):
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "cloud",
                "summarisation.api_base_url": "https://api.example.com/v1",
                "summarisation.api_key": "sk-1",
                "summarisation.cloud_model": "cloud-m",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["live-would-take-over"],
        )
        assert h.call() == "hello world"
        assert h.spy.calls == []  # never probed
        url, kwargs = h.session.calls[0]
        assert url == "https://api.example.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-1"
        assert kwargs["json"]["model"] == "cloud-m"

    def test_connection_error_names_the_backend(self, monkeypatch):
        """The user report's raw urllib3 HTTPConnectionPool blob
        (WinError 10061) is replaced by a line naming the target and the
        likely cause. Control flow unchanged: first failure returns None."""
        import requests

        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,
            },
            probe_models=[],
        )
        h.session.error = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='localhost', port=11434): "
            "Max retries exceeded (WinError 10061)"
        )
        assert h.call() is None
        errs = [m for lvl, m in h.logs if lvl == "WARNING" and "Cannot reach" in m]
        assert len(errs) == 1, h.logs
        assert "is Ollama running?" in errs[0]
        assert "HTTPConnectionPool" not in errs[0]
        assert len(h.session.calls) == 1  # no retry on connection errors (unchanged)

    def test_takeover_note_logged_once_per_generator(self, monkeypatch):
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-27b"],
        )
        assert h.call() is not None
        assert h.call() is not None
        notes = [m for m in h.info_logs() if "llama.cpp detected" in m]
        assert len(notes) == 1, h.info_logs()
        assert len(h.spy.calls) == 1  # the probe cache held across calls
        assert len(h.session.calls) == 2

    def test_llamacpp_down_note_logged_once(self, monkeypatch):
        h = _PacketsHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "summarisation.endpoint": _OLLAMA_ENDPOINT,
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=[],
        )
        h.session.response = _FakeStreamedResponse(_NDJSON_LINES)
        assert h.call() is not None
        assert h.call() is not None
        notes = [m for m in h.info_logs() if "not reachable" in m]
        assert len(notes) == 1, h.info_logs()


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — the new-output riders (OutputGeneratorBase._call_llm_once)
# ═════════════════════════════════════════════════════════════════════════════


class _OllamaUrlSettingsStub(_SettingsStub):
    """Adds the get_ollama_url() surface OutputGeneratorBase.__init__ reads
    (the real resolution order, utils/settings.py:1449, minimal honest
    mirror: canonical key → legacy keys → default, /v1 stripped)."""

    def get_ollama_url(self) -> str:
        url = str(self.get("llm.ollama_url", "") or "")
        if not url:
            for legacy in (
                "summarisation.endpoint",
                "summarisation.ollama_url",
                "ocr.ollama_url",
                "translation.endpoint",
            ):
                url = str(self.get(legacy, "") or "")
                if url:
                    break
        if not url:
            url = "http://localhost:11434"
        if url.endswith("/v1"):
            url = url[:-3]
        return url.rstrip("/")


class _FakeJsonResponse:
    """The raise_for_status/json contract _call_openai_compat needs."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def _openai_payload(text: str = "rider synthesis text") -> dict:
    return {"choices": [{"message": {"content": text}}]}


class _RidersHarness:
    """An ExecutiveBriefingGenerator + faked transport + faked probe."""

    def __init__(self, monkeypatch, values: dict, probe_models: list[str]) -> None:
        import utils.network as net_mod
        from utils.settings import Settings

        self.settings = _OllamaUrlSettingsStub(values)
        monkeypatch.setattr(Settings, "_test_override", self.settings, raising=False)

        from core.llm import local_fallback

        self.spy = _ProbeSpy(models=probe_models)
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", self.spy)

        self.session = _FakeSession(response=_FakeJsonResponse(_openai_payload()))
        monkeypatch.setattr(net_mod, "session_for_url", lambda url: self.session)

        from core.outputs.new_outputs import ExecutiveBriefingGenerator
        from tests.fixtures import make_minimal_request

        self.logs: list[tuple[str, str]] = []
        self.gen = ExecutiveBriefingGenerator(
            make_minimal_request(),
            log_callback=lambda m, level="INFO": self.logs.append((level, m)),
        )

    def call_once(self, prompt: str = "hi") -> str | None:
        return self.gen._call_llm_once(prompt, 0.2, 512)


class TestNewOutputsRidersRouting:
    def test_provider_llamacpp_dead_calls_configured_llamacpp_url(self, monkeypatch):
        """CHARACTERIZATION (the adjacent defect found while wiring the
        policy): provider="llamacpp" — the fresh-install DEFAULT — matched
        NO branch in _call_llm_once and silently returned None (riders
        produced nothing on a llama.cpp rig). Now: the configured llamacpp
        URL gets the OpenAI-compatible call with the configured model."""
        h = _RidersHarness(
            monkeypatch,
            values={
                "summarisation.provider": "llamacpp",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
                "summarisation.llamacpp_model": "configured-lc",
                "summarisation.llamacpp_api_key": "sekrit",
            },
            probe_models=[],  # server currently down → no takeover
        )
        assert h.call_once() == "rider synthesis text"
        url, kwargs = h.session.calls[0]
        assert url == f"{_LLAMACPP_URL}/chat/completions"
        assert kwargs["json"]["model"] == "configured-lc"
        assert kwargs["headers"]["Authorization"] == "Bearer sekrit"
        assert any("not reachable" in m for _lvl, m in h.logs)

    def test_provider_ollama_live_llamacpp_takes_over(self, monkeypatch):
        """Same policy as Packets: saved provider Ollama + live llama-server
        → the rider's call routes to llama.cpp with the served model."""
        h = _RidersHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "llm.ollama_url": "http://localhost:11434",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["served-27b"],
        )
        assert h.call_once() == "rider synthesis text"
        url, kwargs = h.session.calls[0]
        assert url == f"{_LLAMACPP_URL}/chat/completions"
        assert kwargs["json"]["model"] == "served-27b"
        assert kwargs["headers"]["Authorization"] == "Bearer local"

    def test_provider_ollama_llamacpp_down_calls_ollama(self, monkeypatch):
        """Pin: llama.cpp off → the configured Ollama path runs unchanged
        (safe_ollama_request → /api/generate with the request's model)."""
        import utils.network as net_mod

        h = _RidersHarness(
            monkeypatch,
            values={
                "summarisation.provider": "ollama",
                "llm.ollama_url": "http://localhost:11434",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=[],
        )
        calls: list[tuple[str, str, dict]] = []

        def fake_safe_request(method, url, timeout=300, retries=0, **kwargs):
            calls.append((method, url, kwargs))
            return _FakeJsonResponse({"response": "ollama says"})

        monkeypatch.setattr(net_mod, "safe_ollama_request", fake_safe_request)
        assert h.call_once() == "ollama says"
        # the POST went to the Ollama native endpoint with the request model
        assert len(calls) == 1
        method, url, kwargs = calls[0]
        assert method == "POST"
        assert url == "http://localhost:11434/api/generate"
        assert kwargs["json"]["model"] == "test-model:latest"

    def test_cloud_provider_untouched(self, monkeypatch):
        h = _RidersHarness(
            monkeypatch,
            values={
                "summarisation.provider": "openrouter",
                "summarisation.api_base_url": "https://openrouter.ai/api/v1",
                "summarisation.api_key": "sk-1",
                "summarisation.cloud_model": "cloud-m",
                "summarisation.llamacpp_base_url": _LLAMACPP_URL,
            },
            probe_models=["live-would-take-over"],
        )
        assert h.call_once() == "rider synthesis text"
        assert h.spy.calls == []
        url, kwargs = h.session.calls[0]
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        assert kwargs["json"]["model"] == "cloud-m"
