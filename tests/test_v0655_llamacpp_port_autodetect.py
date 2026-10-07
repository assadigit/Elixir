"""V0.6.55 (P1a) — llama.cpp port auto-detection pins.

THE PROBLEM (the operator's rig, V0.6.54 CHANGELOG "configuration, not
code" note): ``llama-server`` on the rig listens on
``http://127.0.0.1:8000`` (llama.cpp's CURRENT default port — its
console even prints "server default port will be changed to :9931 in a
future release"), but the app's single hard default is
``LLAMACPP_DEFAULT_BASE_URL = http://127.0.0.1:8080/v1``
(core/llm/local_fallback.py). Every llama.cpp-first routing decision
therefore probes a DEAD port, concludes "llama.cpp not reachable", and
silently falls back to Ollama — which on this rig is not the backend the
operator started deliberately. The V0.6.54 CHANGELOG flagged exactly
this: "a port-auto-detection helper would make the tool robust to
llama.cpp's shifting default port".

THE FIX (this session): two pieces in core/llm/local_fallback.py —

  1. ``resolve_llamacpp_base_url(settings, api_key)`` — the single
     source for "which llama.cpp URL should we talk to": the operator's
     EXPLICIT setting when they set one; otherwise the first LIVE
     well-known port (8080 default first, then 8000, then 9931 — probe
     order pinned below).
  2. ``decide_llamacpp_first`` consults the same candidates: when the
     configured URL is the UNMODIFIED default and it is dead, the
     alternates are probed; the first live one takes over the routing
     (and the note says the port was AUTO-DETECTED so the log explains
     itself). An explicitly configured URL is never second-guessed —
     the V0.6.12 contract (deliberate operator choice wins).

Plus the factory wiring: ``create_provider``'s llamacpp branch
(core/llm/llm_provider_impl.py) must build the provider on
``resolve_llamacpp_base_url(...)`` so every factory-built provider
follows the detection, not just the routing decision.

THE PINS (all hermetic — the /v1/models probe is monkeypatched at the
module name exactly like test_v0612_llamacpp_first_fallback.py, the
probe cache cleared per test): configured-explicit passthrough, probe
ORDER, first-live wins, all-dead keeps the default, the decision note
mentions auto-detection, the probe cache bounds repeat cost, the
alternates list contents, and the factory source wiring.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# The URLs under test (single source with the module under test).
_DEFAULT_URL = "http://127.0.0.1:8080/v1"
_ALT_8000 = "http://127.0.0.1:8000/v1"
_ALT_9931 = "http://127.0.0.1:9931/v1"


class _SettingsStub:
    """The duck-type the decision module needs (get/set) — the same
    pattern test_v0612_llamacpp_first_fallback.py uses: absent keys fall
    through to the CALLER's default so tests exercise production
    defaults by omission."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)

    def set(self, key: str, value) -> bool:
        self._v[key] = value
        return True


class _ProbeSpy:
    """Monkeypatch stand-in for list_llamacpp_models that records calls
    and answers per-URL (dead URLs → [], live URLs → model lists)."""

    def __init__(self, live: dict[str, list[str]] | None = None) -> None:
        self.live = dict(live or {})
        self.calls: list[str] = []

    def __call__(self, base_url: str, api_key: str, timeout: int = 10) -> list[str]:
        self.calls.append(base_url)
        return list(self.live.get(base_url, []))


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    """Every test starts with an empty probe cache (and leaves it empty)."""
    from core.llm import local_fallback

    local_fallback.clear_llamacpp_probe_cache()
    yield
    local_fallback.clear_llamacpp_probe_cache()


def _install_spy(monkeypatch, live: dict[str, list[str]] | None = None) -> _ProbeSpy:
    from core.llm import local_fallback

    spy = _ProbeSpy(live)
    monkeypatch.setattr(local_fallback, "list_llamacpp_models", spy)
    return spy


# ═════════════════════════════════════════════════════════════════════════════
# Layer 1 — the candidate list itself (single source of truth)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655AlternatePortList:
    def test_alternates_are_exactly_8000_and_9931(self):
        """The alternates: llama.cpp's CURRENT default port (8000) first,
        the ANNOUNCED future default (9931) second. The legacy 8080 is
        NOT an alternate — it is LLAMACPP_DEFAULT_BASE_URL itself and is
        always probed first."""
        from core.llm.local_fallback import LLAMACPP_ALT_BASE_URLS

        assert LLAMACPP_ALT_BASE_URLS == (_ALT_8000, _ALT_9931)

    def test_default_url_is_unchanged_8080(self):
        """The legacy default stays 8080 — the auto-detection is additive,
        not a default change (byte-identical behavior when it IS live)."""
        from core.llm.local_fallback import LLAMACPP_DEFAULT_BASE_URL

        assert LLAMACPP_DEFAULT_BASE_URL == _DEFAULT_URL


# ═════════════════════════════════════════════════════════════════════════════
# Layer 2 — resolve_llamacpp_base_url (the shared helper)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655ResolveBaseUrl:
    def test_explicit_configured_url_is_never_probed_or_overridden(self, monkeypatch):
        """An operator who typed a different URL made a DELIBERATE choice
        (the V0.6.12 contract) — returned as-is, zero probes."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {_ALT_8000: ["served-model"]})
        out = resolve_llamacpp_base_url(
            _SettingsStub({"summarisation.llamacpp_base_url": "http://10.0.0.5:9000/v1"})
        )
        assert out == "http://10.0.0.5:9000/v1"
        assert spy.calls == []

    def test_default_setting_probes_default_then_8000_then_9931_in_order(self, monkeypatch):
        """All-dead: the probe ORDER is pinned — the default 8080 first,
        then 8000, then 9931 (one pass, no retries)."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {})  # everything dead
        out = resolve_llamacpp_base_url(_SettingsStub())
        assert out == _DEFAULT_URL  # all dead → the default, unchanged
        assert spy.calls == [_DEFAULT_URL, _ALT_8000, _ALT_9931]

    def test_8000_live_wins_when_default_is_dead(self, monkeypatch):
        """THE OPERATOR'S RIG CASE: 8080 dead, 8000 live → 8000 is used
        and 9931 is never probed (first live wins, no over-probing)."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {_ALT_8000: ["Ternary-Bonsai-2-27B"]})
        out = resolve_llamacpp_base_url(_SettingsStub())
        assert out == _ALT_8000
        assert spy.calls == [_DEFAULT_URL, _ALT_8000]

    def test_9931_live_wins_when_only_future_port_alive(self, monkeypatch):
        """The announced future default alone: 8080 + 8000 dead, 9931
        live → 9931 is used."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {_ALT_9931: ["future-model"]})
        out = resolve_llamacpp_base_url(_SettingsStub())
        assert out == _ALT_9931
        assert spy.calls == [_DEFAULT_URL, _ALT_8000, _ALT_9931]

    def test_default_live_never_probes_alternates(self, monkeypatch):
        """Byte-identical V0.6.12 behavior when the default port IS the
        live one — zero extra probes."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {_DEFAULT_URL: ["served"]})
        out = resolve_llamacpp_base_url(_SettingsStub())
        assert out == _DEFAULT_URL
        assert spy.calls == [_DEFAULT_URL]

    def test_probe_cache_bounds_the_cost_on_repeat_calls(self, monkeypatch):
        """The 30s probe cache (V0.6.12) also covers the alternates: a
        second resolution within TTL does NOT re-probe (the packets
        generator resolves 5+ times per run)."""
        from core.llm import local_fallback
        from core.llm.local_fallback import resolve_llamacpp_base_url

        spy = _install_spy(monkeypatch, {_ALT_8000: ["m"]})
        first = resolve_llamacpp_base_url(_SettingsStub())
        second = resolve_llamacpp_base_url(_SettingsStub())
        assert first == second == _ALT_8000
        assert spy.calls == [_DEFAULT_URL, _ALT_8000]  # NOT doubled

    def test_probe_failure_counts_as_dead_not_error(self, monkeypatch):
        """A probe that RAISES is "dead", never an exception to the caller
        (the _probe_llamacpp contract)."""
        from core.llm.local_fallback import resolve_llamacpp_base_url

        class _ExplodingSpy(_ProbeSpy):
            def __call__(self, base_url, api_key, timeout=10):
                self.calls.append(base_url)
                raise RuntimeError("blackholed port")

        from core.llm import local_fallback

        spy = _ExplodingSpy()
        monkeypatch.setattr(local_fallback, "list_llamacpp_models", spy)
        out = resolve_llamacpp_base_url(_SettingsStub())
        assert out == _DEFAULT_URL
        assert spy.calls == [_DEFAULT_URL, _ALT_8000, _ALT_9931]


# ═════════════════════════════════════════════════════════════════════════════
# Layer 3 — decide_llamacpp_first consults the alternates (the routing)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655DecideAutoDetect:
    def test_rig_case_8000_takes_over_the_routing(self, monkeypatch):
        """8080 dead + 8000 serving Ternary-Bonsai → use_llamacpp=True on
        the 8000 URL with the detected model, and the NOTE says the port
        was auto-detected (the log must explain itself)."""
        from core.llm.local_fallback import decide_llamacpp_first

        _install_spy(monkeypatch, {_ALT_8000: ["Ternary-Bonsai-2-27B-Instruct-Vision"]})
        decision = decide_llamacpp_first(_SettingsStub(), "ollama")
        assert decision.use_llamacpp is True
        assert decision.base_url == _ALT_8000
        assert decision.model == "Ternary-Bonsai-2-27B-Instruct-Vision"
        assert "8000" in decision.note
        assert "auto" in decision.note.lower()

    def test_all_dead_note_lists_what_was_probed(self, monkeypatch):
        """All three dead → passthrough (use_llamacpp=False) and the note
        explains the candidates probed, so the operator can see why the
        fallback fired."""
        from core.llm.local_fallback import decide_llamacpp_first

        _install_spy(monkeypatch, {})
        decision = decide_llamacpp_first(_SettingsStub(), "ollama")
        assert decision.use_llamacpp is False
        assert decision.base_url == ""
        assert "8080" in decision.note and "8000" in decision.note and "9931" in decision.note

    def test_explicit_dead_url_keeps_old_single_probe_note(self, monkeypatch):
        """An EXPLICIT configured URL that is dead: unchanged V0.6.12
        behavior — only that URL probed, the note points at it alone."""
        from core.llm.local_fallback import decide_llamacpp_first

        spy = _install_spy(monkeypatch, {})
        decision = decide_llamacpp_first(
            _SettingsStub({"summarisation.llamacpp_base_url": "http://127.0.0.1:8500/v1"}), "ollama"
        )
        assert decision.use_llamacpp is False
        assert spy.calls == ["http://127.0.0.1:8500/v1"]
        assert "8500" in decision.note
        assert "9931" not in decision.note  # no alternate probing on explicit choice

    def test_default_live_routing_is_byte_identical_to_v0612(self, monkeypatch):
        """8080 live → the exact V0.6.12 decision shape (base, model,
        note wording unchanged in its 'detected' phrasing)."""
        from core.llm.local_fallback import decide_llamacpp_first

        _install_spy(monkeypatch, {_DEFAULT_URL: ["m1"]})
        decision = decide_llamacpp_first(_SettingsStub(), "ollama")
        assert decision.use_llamacpp is True
        assert decision.base_url == _DEFAULT_URL
        assert decision.model == "m1"
        assert "detected" in decision.note and "auto" not in decision.note.lower()

    def test_configured_model_override_note_survives_auto_detection(self, monkeypatch):
        """The V0.4.30 precedent (detected served model wins over the
        configured name) must keep working when the port was
        auto-detected too."""
        from core.llm.local_fallback import decide_llamacpp_first

        _install_spy(monkeypatch, {_ALT_9931: ["served-x"]})
        decision = decide_llamacpp_first(
            _SettingsStub({"summarisation.llamacpp_model": "configured-y"}), "ollama"
        )
        assert decision.use_llamacpp is True
        assert decision.model == "served-x"
        assert "configured-y" in decision.note  # the override is explained

    def test_cloud_provider_short_circuits_before_any_probe(self, monkeypatch):
        """Unchanged guard: a cloud selection is never probed, not even
        the default URL (byte-identical V0.6.12 behavior)."""
        from core.llm.local_fallback import decide_llamacpp_first

        spy = _install_spy(monkeypatch, {_ALT_8000: ["m"]})
        decision = decide_llamacpp_first(_SettingsStub(), "openrouter")
        assert decision.use_llamacpp is False
        assert spy.calls == []


# ═════════════════════════════════════════════════════════════════════════════
# Layer 4 — the factory wiring (create_provider's llamacpp branch)
# ═════════════════════════════════════════════════════════════════════════════


class TestV0655FactoryWiring:
    def test_factory_llamacpp_branch_uses_the_resolver(self):
        """SOURCE PIN (the factory needs the full provider stack to
        execute, so the wiring is pinned on source): create_provider's
        llamacpp branch must resolve the base URL through
        ``resolve_llamacpp_base_url`` — otherwise the routing decision
        detects :8000 while the PROVIDER still talks to the stale
        settings URL :8080 (the detection would be a no-op for every
        factory-built provider)."""
        factory_src = (
            _project_root / "core" / "llm" / "llm_provider_impl.py"
        ).read_text(encoding="utf-8")
        # The lazy-import + call must both be present in the llamacpp branch.
        assert "resolve_llamacpp_base_url" in factory_src, (
            "create_provider's llamacpp branch must call "
            "resolve_llamacpp_base_url(settings, ...) — otherwise "
            "auto-detected ports never reach the actual provider"
        )
        # And the OLD direct settings read must be gone from the branch
        # (the single-source rule: one resolver, not two competing reads).
        llamacpp_branch = factory_src.split('elif provider == "llamacpp":', 1)[1].split(
            'elif provider ==', 1
        )[0]
        assert 'settings.get("summarisation.llamacpp_base_url"' not in llamacpp_branch, (
            "the llamacpp branch must not keep a second, competing base-URL "
            "read next to the resolver"
        )
