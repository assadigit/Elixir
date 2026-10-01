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
