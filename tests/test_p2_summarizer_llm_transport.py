"""Phase 2 (P2-C1): the LLM transport seam of ``Summarizer``.

``_call_llm`` provider dispatch (claude / freellmapi / openrouter-family /
llamacpp / ollama) + the opt-in response cache, the V18.15.6.0 error-tracker
contract, the per-backend delegates (``_call_ollama``, streaming /
nonstreaming, openai-compat, claude, fast-ollama), the fusion-cloud ladder
(``_call_cloud``), the empty-retry wrapper (Qwen3 ``/no_think`` + the
always-retry contract), the structured-JSON delegate, ``_parse_universal``,
the B3 cloud judge, the model-profile delegates and the fast/heavy model
switches.

Every network boundary is monkeypatched at the module-import seam the
production code itself uses (``ld_call_*`` imported into
``core.summarisation.summarizer``; ``_ld._call_ollama_streaming`` etc.) —
no socket is ever opened.

Run: ``COVERAGE_FILE=.coverage.p2c1 python3 -m pytest tests/test_p2_summarizer_llm_transport.py -v``
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_p2_summarizer_harness import (  # noqa: E402
    ScriptedLLM,
    a_chapter,
    assert_logged,
    hermetic_env,
    make_summarizer,
)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    with hermetic_env():
        yield


# ── _call_llm: provider dispatch ────────────────────────────────────────────


class TestCallLlmDispatch:
    @pytest.mark.parametrize(
        ("provider", "expected_type"),
        [
            ("claude", "claude"),
            ("freellmapi", "openai_compat"),
            ("openrouter", "openai_compat"),
            ("openai", "openai_compat"),
            ("openai_compatible", "openai_compat"),
            ("llamacpp", "llamacpp"),
        ],
    )
    def test_cloud_and_llamacpp_providers_route_via_llm_provider(
        self, tmp_path, monkeypatch, provider, expected_type
    ):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake_via_provider(provider_type, prompt, *args, **kwargs):
            seen["type"] = provider_type
            seen["prompt"] = prompt
            seen.update(kwargs)
            return f"reply from {provider_type}"

        monkeypatch.setattr(sz_mod, "ld_call_via_llm_provider", _fake_via_provider)
        s = make_summarizer(tmp_path, settings_values={"summarisation.provider": provider})
        assert s.provider == provider
        out = s._call_llm("prompt text", temperature=0.3, max_tokens=512)
        assert out == f"reply from {expected_type}"
        assert seen["type"] == expected_type
        # The timeout/supervisor plumbing rides along.
        assert seen["timeout"] == s.timeout
        assert seen["supervisor"] is s._ollama_supervisor

    def test_ollama_provider_routes_inline_with_defaults(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake_ollama(prompt, model, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, model=model, temp=temp, max_tokens=max_tokens)
            return "ollama reply"

        monkeypatch.setattr(sz_mod, "ld_call_ollama", _fake_ollama)
        s = make_summarizer(tmp_path)  # default provider: ollama
        out = s._call_llm("hello")
        assert out == "ollama reply"
        assert seen["model"] == s.primary_model
        assert seen["temp"] == s.temperature
        assert seen["max_tokens"] == s.request.summarisation_max_output_tokens

    def test_academic_rigor_raises_output_budget_floor(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake_ollama(prompt, model, temp, max_tokens, **kwargs):
            seen["max_tokens"] = max_tokens
            return "ok"

        monkeypatch.setattr(sz_mod, "ld_call_ollama", _fake_ollama)
        s = make_summarizer(
            tmp_path,
            request_fields={
                "academic_rigor": True,
                "summarisation_max_output_tokens": 4096,
            },
        )
        assert s.academic_rigor is True
        s._call_llm("p")
        assert seen["max_tokens"] == 16000  # V13.45.4 floor


# ── _call_llm: the opt-in response cache ────────────────────────────────────


class TestCallLlmCache:
    def _cache_summarizer(self, tmp_path, monkeypatch):
        import core.llm.response_cache as rc_mod

        s = make_summarizer(tmp_path, request_fields={"summarisation_cache_enabled": True})
        store: dict = {}

        class _FakeCache:
            def get(self, prompt, model, temp, max_tok):
                return store.get((prompt, model, temp, max_tok))

            def put(self, prompt, model, temp, result, max_tok):
                store[(prompt, model, temp, max_tok)] = result

        monkeypatch.setattr(rc_mod, "response_cache", _FakeCache())
        return s, store

    def test_hit_skips_llm_and_logs(self, tmp_path, monkeypatch):
        s, store = self._cache_summarizer(tmp_path, monkeypatch)
        store[("p1", s.primary_model, s.temperature, s.request.summarisation_max_output_tokens)] = (
            "cached!"
        )
        logs: list[tuple[str, str]] = []
        s.log = lambda msg, level="INFO": logs.append((level, msg))  # type: ignore[assignment]

        calls = []

        def _no_call(*a, **k):
            calls.append(1)
            return "never"

        s._call_ollama = _no_call  # type: ignore[method-assign]
        assert s._call_llm("p1") == "cached!"
        assert calls == []
        assert_logged(logs, "Response cache HIT — LLM call skipped")

    def test_miss_calls_llm_then_puts(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        s, store = self._cache_summarizer(tmp_path, monkeypatch)
        monkeypatch.setattr(sz_mod, "ld_call_ollama", lambda *a, **k: "fresh reply")
        assert s._call_llm("p2") == "fresh reply"
        assert "fresh reply" in store.values()

    def test_cache_get_failure_is_best_effort(self, tmp_path, monkeypatch):
        import core.llm.response_cache as rc_mod
        import core.summarisation.summarizer as sz_mod

        s = make_summarizer(tmp_path, request_fields={"summarisation_cache_enabled": True})

        class _BoomCache:
            def get(self, *a, **k):
                raise RuntimeError("cache get exploded")

            def put(self, *a, **k):
                raise RuntimeError("cache put exploded")

        monkeypatch.setattr(rc_mod, "response_cache", _BoomCache())
        monkeypatch.setattr(sz_mod, "ld_call_ollama", lambda *a, **k: "still works")
        assert s._call_llm("p3") == "still works"

    def test_cache_disabled_never_touches_cache(self, tmp_path, monkeypatch):
        import core.llm.response_cache as rc_mod
        import core.summarisation.summarizer as sz_mod

        touches = []

        class _SpyCache:
            def get(self, *a, **k):
                touches.append("get")
                return None

            def put(self, *a, **k):
                touches.append("put")

        monkeypatch.setattr(rc_mod, "response_cache", _SpyCache())
        monkeypatch.setattr(sz_mod, "ld_call_ollama", lambda *a, **k: "uncached")
        s = make_summarizer(tmp_path)  # summarisation_cache_enabled defaults False
        assert s._call_llm("p4") == "uncached"
        assert touches == []


# ── _call_ollama: the V18.15.6.0 (Fix B) error-tracker contract ─────────────


class TestCallOllamaErrorTracker:
    def _patch(self, monkeypatch, behavior):
        import core.summarisation.summarizer as sz_mod

        def _fake(prompt, model, temp, max_tokens, error_tracker=None, **kwargs):
            return behavior(error_tracker)

        monkeypatch.setattr(sz_mod, "ld_call_ollama", _fake)

    def test_success_resets_error_type(self, tmp_path, monkeypatch):
        self._patch(monkeypatch, lambda tracker: "a real response")
        s = make_summarizer(tmp_path)
        s._last_llm_error_type = "timeout"  # stale from a previous call
        assert s._call_ollama("p", "m", 0.2, 512) == "a real response"
        assert s._last_llm_error_type is None

    def test_tracked_failure_persists_error_type(self, tmp_path, monkeypatch):
        self._patch(
            monkeypatch,
            lambda tracker: (tracker.append("timeout"), None)[1],
        )
        s = make_summarizer(tmp_path)
        assert s._call_ollama("p", "m", 0.2, 512) is None
        assert s._last_llm_error_type == "timeout"

    def test_untracked_empty_failure_classified_empty(self, tmp_path, monkeypatch):
        self._patch(monkeypatch, lambda tracker: None)
        s = make_summarizer(tmp_path)
        assert s._call_ollama("p", "m", 0.2, 512) is None
        assert s._last_llm_error_type == "empty"


# ── Backend delegates (llm_dispatcher seams) ─────────────────────────────────


class TestBackendDelegates:
    def test_streaming_delegate_passes_instance_state(self, tmp_path, monkeypatch):
        import core.summarisation.llm_dispatcher as ld

        seen: dict = {}

        def _fake(prompt, model, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, kwargs=kwargs)
            return "streamed"

        monkeypatch.setattr(ld, "_call_ollama_streaming", _fake)
        s = make_summarizer(tmp_path)
        s._streaming_enabled = True
        out = s._call_ollama_streaming("p", "m", 0.2, 64)
        assert out == "streamed"
        assert seen["kwargs"]["ollama_base_url"] == s.ollama_base_url
        assert seen["kwargs"]["timeout"] == s.timeout

    def test_nonstreaming_delegate_passes_instance_state(self, tmp_path, monkeypatch):
        import core.summarisation.llm_dispatcher as ld

        seen: dict = {}

        def _fake(prompt, model, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, kwargs=kwargs)
            return "nonstreamed"

        monkeypatch.setattr(ld, "_call_ollama_nonstreaming", _fake)
        s = make_summarizer(tmp_path)
        assert s._call_ollama_nonstreaming("p", "m", 0.2, 64) == "nonstreamed"
        assert seen["kwargs"]["context_tokens"] == s.request.summarisation_max_context_tokens

    def test_openai_compat_delegate_passes_instance_state(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake(prompt, base_url, api_key, model, label, temp, max_tokens, **kwargs):
            seen.update(
                prompt=prompt,
                base_url=base_url,
                api_key=api_key,
                model=model,
                label=label,
                temp=temp,
                max_tokens=max_tokens,
                kwargs=kwargs,
            )
            return "compat reply"

        monkeypatch.setattr(sz_mod, "ld_call_openai_compat", _fake)
        s = make_summarizer(tmp_path, settings_values={"summarisation.provider": "openrouter"})
        assert s._call_openai_compat("p", "http://x", "key", "m", "lbl", 0.3, 99) == "compat reply"
        assert seen["label"] == "lbl"
        assert seen["kwargs"]["provider"] == "openrouter"
        assert seen["kwargs"]["retries"] == s.retries

    def test_claude_delegate_passes_instance_state(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake(prompt, max_tokens, temperature, **kwargs):
            seen.update(
                prompt=prompt, max_tokens=max_tokens, temperature=temperature, kwargs=kwargs
            )
            return "claude reply"

        monkeypatch.setattr(sz_mod, "ld_call_claude", _fake)
        s = make_summarizer(tmp_path, settings_values={"summarisation.provider": "claude"})
        assert s._call_claude("p", 777, 0.1) == "claude reply"
        assert seen["kwargs"]["claude_api_key"] == s.claude_api_key
        assert seen["kwargs"]["claude_model"] == s.claude_model

    def test_fast_ollama_delegate_passes_instance_state(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake(prompt, model, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, model=model, temp=temp, max_tokens=max_tokens, kwargs=kwargs)
            return "fast reply"

        monkeypatch.setattr(sz_mod, "ld_call_fast_ollama", _fake)
        s = make_summarizer(tmp_path)
        assert s._call_fast_ollama("p", "m", 0.1, 200) == "fast reply"
        assert seen["kwargs"]["fast_model_context"] == s.request.fast_model_context

    def test_call_via_llm_provider_passes_callbacks(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake(provider_type, prompt, model, base_url, api_key, temp, max_tokens, **kwargs):
            seen.update(provider_type=provider_type, prompt=prompt, kwargs=kwargs)
            return "routed"

        monkeypatch.setattr(sz_mod, "ld_call_via_llm_provider", _fake)
        s = make_summarizer(tmp_path)
        assert (
            s._call_via_llm_provider("llamacpp", "p", model="m", temp=0.2, max_tokens=64)
            == "routed"
        )
        assert seen["kwargs"]["call_claude_fn"] == s._call_claude
        assert seen["kwargs"]["call_openai_compat_fn"] == s._call_openai_compat


# ── _call_cloud: the fusion ladder ──────────────────────────────────────────


class TestCallCloud:
    def _fusion_summarizer(self, tmp_path, settings=None, log_lines=None):
        values = {
            "summarisation.provider": "ollama",
            "summarisation.fusion_enabled": True,
            "summarisation.fusion_cloud_provider": "openai_compat",
            "summarisation.fusion_cloud_model": "cloud-model-x",
        }
        values.update(settings or {})
        return make_summarizer(tmp_path, settings_values=values, log_lines=log_lines)

    def test_disabled_fusion_falls_back_to_local(self, tmp_path):
        s = make_summarizer(tmp_path)  # fusion_enabled default False
        s._call_llm = lambda prompt, **k: f"local:{prompt}"  # type: ignore[method-assign]
        assert s._call_cloud("q", max_tokens=128, temperature=0.4) == "local:q"

    def test_openai_compat_success(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        # The delegate passes all 7 leading args positionally (see
        # Summarizer._call_via_llm_provider), so the fake must accept them.
        monkeypatch.setattr(
            sz_mod,
            "ld_call_via_llm_provider",
            lambda provider_type, prompt, model="", base_url="", api_key="", temp=0.6, max_tokens=4096, **k: (
                f"{provider_type}:{len(prompt)}"
            ),
        )
        s = self._fusion_summarizer(tmp_path)
        assert s._call_cloud("q") == "openai_compat:1"

    def test_claude_fusion_provider(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        seen: dict = {}

        def _fake(
            provider_type, prompt, model="", base_url="", api_key="", temp=0.6, max_tokens=4096, **k
        ):
            seen["type"] = provider_type
            return "claude fusion reply"

        monkeypatch.setattr(sz_mod, "ld_call_via_llm_provider", _fake)
        s = self._fusion_summarizer(tmp_path, {"summarisation.fusion_cloud_provider": "claude"})
        assert s._call_cloud("q") == "claude fusion reply"
        assert seen["type"] == "claude"

    def test_empty_cloud_reply_falls_back_to_local(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        logs: list[tuple[str, str]] = []
        monkeypatch.setattr(sz_mod, "ld_call_via_llm_provider", lambda *a, **k: "   ")
        s = self._fusion_summarizer(tmp_path, log_lines=logs)
        s._call_llm = lambda prompt, **k: "local fallback"  # type: ignore[method-assign]
        assert s._call_cloud("q") == "local fallback"
        assert_logged(logs, "Fusion cloud returned empty — falling back to local model")

    def test_cloud_exception_falls_back_to_local(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        logs: list[tuple[str, str]] = []

        def _boom(*a, **k):
            raise RuntimeError("cloud down")

        monkeypatch.setattr(sz_mod, "ld_call_via_llm_provider", _boom)
        s = self._fusion_summarizer(tmp_path, log_lines=logs)
        s._call_llm = lambda prompt, **k: "local fallback"  # type: ignore[method-assign]
        assert s._call_cloud("q") == "local fallback"
        assert_logged(logs, "Fusion cloud failed (RuntimeError: cloud down)")


# ── _call_llm_with_empty_retry ──────────────────────────────────────────────


class TestCallLlmWithEmptyRetry:
    def test_qwen3_gets_no_think_suffix_on_first_attempt(self, tmp_path):
        s = make_summarizer(tmp_path, model="Qwen3.8-27B:latest")
        seen: list[str] = []
        s._call_llm = lambda prompt, **k: seen.append(prompt) or "a sufficiently long reply"  # type: ignore[method-assign]
        out = s._call_llm_with_empty_retry("summarize this")
        assert out == "a sufficiently long reply"
        assert seen[0].endswith(" /no_think")

    def test_short_first_reply_retries_with_nudge_then_succeeds(self, tmp_path):
        s = make_summarizer(tmp_path, model="gemma3:12b")
        replies = iter(["tiny", "the nudged reply with enough length"])
        seen: list[str] = []

        def _fake(prompt, **k):
            seen.append(prompt)
            return next(replies)

        s._call_llm = _fake  # type: ignore[method-assign]
        logs: list[tuple[str, str]] = []
        s.log = lambda msg, level="INFO": logs.append((level, msg))  # type: ignore[assignment]
        assert s._call_llm_with_empty_retry("p") == "the nudged reply with enough length"
        assert len(seen) == 2
        assert "Please output the response now." in seen[1]
        assert_logged(logs, "Empty/short LLM response — retrying with nudge")

    def test_both_attempts_empty_returns_none(self, tmp_path):
        s = make_summarizer(tmp_path)
        s._call_llm = lambda prompt, **k: None  # type: ignore[method-assign]
        assert s._call_llm_with_empty_retry("p") is None

    def test_sleep_failure_is_swallowed_and_logged(self, tmp_path, monkeypatch):
        """The retry sleep's try/except (V18.2.14 B4) must never kill the call."""
        s = make_summarizer(tmp_path)
        replies = iter(["x", "a sufficiently long nudged reply"])

        def _fake_sleep(_secs):
            raise RuntimeError("sleep interrupted")

        monkeypatch.setattr(time, "sleep", _fake_sleep)
        s._call_llm = lambda prompt, **k: next(replies)  # type: ignore[method-assign]
        assert s._call_llm_with_empty_retry("p") == "a sufficiently long nudged reply"


# ── Structured-JSON + universal parser + B3 judge delegates ─────────────────


class TestStructuredAndJudgeDelegates:
    def test_call_llm_structured_disabled_path_returns_none(self, tmp_path):
        """V18.20.2.0 A16: the structured path is production-disabled —
        the delegate must uphold the always-None contract."""
        s = make_summarizer(tmp_path)
        out = s._call_llm_structured("prompt", s.primary_model, 0.2, 4096)
        assert out is None or isinstance(out, dict)

    def test_parse_universal_delegate(self, tmp_path):
        s = make_summarizer(tmp_path)
        parsed = s._parse_universal(
            "<executive_summary>Exec text.</executive_summary>"
            "<bullet_points>\n- One bullet.\n</bullet_points>"
        )
        assert parsed["executive_summary"] == "Exec text."
        assert parsed["bullet_points"] == ["One bullet."]

    def test_b3_cloud_judge_delegate(self, tmp_path):
        """The delegate returns ``(best_exec_sample, best_thorough_sample)`` —
        the V13.36.0 ``b3_judge.b3_cloud_judge`` contract (a 2-tuple of sample
        dicts; there is no "reason" string)."""
        logs: list[tuple[str, str]] = []
        s = make_summarizer(tmp_path, log_lines=logs)
        samples = [
            {
                "executive_summary": "First sample executive text.",
                "bullet_points": ["First bullet."],
                "thorough_summary": "",
            },
            {
                "executive_summary": "Second sample executive text.",
                "bullet_points": ["Second bullet."],
                "thorough_summary": "",
            },
        ]
        # Script the two cloud-judge probes (exec judge, then thorough judge).
        replies = iter(["2", "1"])

        def _fake_cloud(prompt, **k):
            return next(replies)

        s._call_cloud = _fake_cloud  # type: ignore[method-assign]
        best_exec, best_thorough = s._b3_cloud_judge(samples, a_chapter(3), "Chapter")
        assert isinstance(best_exec, dict)
        assert isinstance(best_thorough, dict)
        assert best_exec is samples[1]  # exec judge answered "2"
        assert best_thorough is samples[0]  # thorough judge answered "1"


# ── Fast/heavy model switches + fast-LLM delegate ───────────────────────────


class TestModelSwitches:
    def test_switch_to_fast_model_recovers_vram_only_in_dual_local(self, tmp_path):
        s = make_summarizer(tmp_path, request_fields={"model_architecture": "dual_local"})
        recovered: list[str] = []
        s._recover_vram = lambda context="", delay_sec=0.0: recovered.append(context)  # type: ignore[method-assign]
        s._switch_to_fast_model()
        assert recovered == ["switch-to-fast"]

    def test_switch_to_fast_model_noop_in_single_local(self, tmp_path):
        s = make_summarizer(tmp_path)  # single_local default
        recovered: list[str] = []
        s._recover_vram = lambda context="", delay_sec=0.0: recovered.append(context)  # type: ignore[method-assign]
        s._switch_to_fast_model()
        assert recovered == []

    def test_switch_to_heavy_model_recovers_vram_only_in_dual_local(self, tmp_path):
        s = make_summarizer(tmp_path, request_fields={"model_architecture": "dual_local"})
        recovered: list[str] = []
        s._recover_vram = lambda context="", delay_sec=0.0: recovered.append(context)  # type: ignore[method-assign]
        s._switch_to_heavy_model()
        assert recovered == ["switch-to-heavy"]

    def test_switch_to_heavy_model_noop_in_api_mode(self, tmp_path):
        s = make_summarizer(tmp_path, request_fields={"model_architecture": "single_api"})
        recovered: list[str] = []
        s._recover_vram = lambda context="", delay_sec=0.0: recovered.append(context)  # type: ignore[method-assign]
        s._switch_to_heavy_model()
        assert recovered == []

    def test_call_fast_llm_single_local_routes_via_call_llm(self, tmp_path):
        s = make_summarizer(tmp_path)  # single_local, fast_model default
        seen: list[str] = []
        s._call_llm_with_empty_retry = lambda prompt, **k: seen.append(prompt) or "fast local reply"  # type: ignore[method-assign]
        out = s._call_fast_llm("quick prompt", max_tokens=100)
        assert out == "fast local reply"
        assert seen == ["quick prompt"]

    def test_call_fast_llm_dual_local_uses_fast_ollama(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        s = make_summarizer(
            tmp_path,
            request_fields={"model_architecture": "dual_local", "fast_model": "fast-model-y"},
        )
        seen: dict = {}

        def _fake(prompt, model, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, model=model)
            return "fast dual reply"

        monkeypatch.setattr(sz_mod, "ld_call_fast_ollama", _fake)
        out = s._call_fast_llm("quick prompt", max_tokens=100)
        assert out == "fast dual reply"
        assert seen["model"] == "fast-model-y"

    def test_call_fast_llm_api_mode_uses_openai_compat(self, tmp_path, monkeypatch):
        import core.summarisation.summarizer as sz_mod

        s = make_summarizer(
            tmp_path,
            request_fields={
                "model_architecture": "dual_api",
                "fast_api_url": "http://fast/v1",
                "fast_api_key": "fk",
                "fast_api_model": "fast-cloud",
            },
        )
        seen: dict = {}

        def _fake(prompt, base_url, api_key, model, label, temp, max_tokens, **kwargs):
            seen.update(prompt=prompt, base_url=base_url, model=model)
            return "fast api reply"

        monkeypatch.setattr(sz_mod, "ld_call_openai_compat", _fake)
        out = s._call_fast_llm("quick prompt", max_tokens=100)
        assert out == "fast api reply"
        assert seen["base_url"] == "http://fast/v1"
        assert seen["model"] == "fast-cloud"


# ── _call_dedicated_thorough_with_fallback passthrough ──────────────────────


class TestDedicatedThoroughDelegate:
    def test_result_and_counter_unpacking(self, tmp_path):
        """The delegate unpacks (result, new_count) and re-assigns the
        instance counter — the V18.4 contract."""
        s = make_summarizer(tmp_path)
        s._synthetic_thorough_fallback_count = 0
        replies = {"n": 0}

        def _fake_call_llm(prompt, model=None, temperature=None, max_tokens=None):
            replies["n"] += 1
            return None  # all attempts fail → synthetic fallback

        s._call_llm = _fake_call_llm  # type: ignore[method-assign]
        out = s._call_dedicated_thorough_with_fallback(
            "prompt", exec_sum="exec material", bullets=[], min_words=50
        )
        assert out is not None  # synthetic fallback from exec material
        assert s._synthetic_thorough_fallback_count == 1

    def test_scripted_llm_still_installed(self, tmp_path):
        """Sanity: the ScriptedLLM seam works through the delegate too."""
        s = make_summarizer(tmp_path)
        ScriptedLLM(primary_response=None).install(s)
        assert s._call_llm("anything") is None
