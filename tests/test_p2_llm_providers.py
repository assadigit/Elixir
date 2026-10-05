"""Phase 2 (Test-Net Deepening) — providers & preflight: ``cloud_client``,
``claude_provider``, and the ``llm_provider_impl`` factory.

Baselines: cloud_client.py 45/45 missed (0%), claude_provider.py 38/48 (21%),
llm_provider_impl.py 17/62 (73%).

Hermetic: ``requests`` and ``utils.network.session_for_url`` /
``extract_openai_content`` are patched at the SOURCE module (cloud_client
imports them lazily inside the function, so the source-module attributes are
what the function sees); the Claude provider transport is patched at the
provider module's ``session_for_url`` seam (V0.6.7 review-loop A5: top-level
import there). No HTTP leaves the process.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import core.llm.cloud_client as cloud_client_module  # noqa: E402
from core.llm.claude_provider import ClaudeProvider  # noqa: E402
from core.llm.cloud_client import CLOUD_PRESETS  # noqa: E402

# NOTE: cloud_client's pre-flight helper is itself named ``test_cloud_connection``
# (production API, not a test). Importing it bare would make pytest collect it,
# so it is accessed via the module attribute below.


# ════════════════════════════════════════════════════════════════════════════
# cloud_client
# ════════════════════════════════════════════════════════════════════════════


class _FakeSession:
    def __init__(self, response=None, exc=None) -> None:
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._response


def _http(status: int, payload: dict | None = None, text: str = "") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(payload).encode() if payload is not None else text.encode()
    return r


def _with_session(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    import utils.network as net

    monkeypatch.setattr(net, "session_for_url", lambda url: session)
    # Real extraction (shape-safe) — we feed it well-formed payloads.


class TestCloudPresets:
    def test_presets_shape(self):
        assert len(CLOUD_PRESETS) == 4
        for preset in CLOUD_PRESETS:
            assert {"label", "base_url", "model", "hint"} <= set(preset)

    def test_nine_router_first_and_custom_last(self):
        assert "9Router" in CLOUD_PRESETS[0]["label"]
        assert CLOUD_PRESETS[-1]["base_url"] == ""


# The production pre-flight probe (named ``test_*`` but NOT a pytest test).
probe = cloud_client_module.test_cloud_connection


class TestTestCloudConnectionValidation:
    def test_empty_base_url(self):
        assert probe("", "key", "model") == (False, "No base URL set.")

    def test_none_base_url(self):
        assert probe(None, "key", "model") == (False, "No base URL set.")

    def test_whitespace_base_url(self):
        assert probe("   ", "key", "model") == (False, "No base URL set.")

    def test_empty_model(self):
        assert probe("https://x/v1", "key", "") == (False, "No model name set.")

    def test_empty_api_key(self):
        assert probe("https://x/v1", "", "m") == (False, "No API key set.")


class TestTestCloudConnectionNetwork:
    def test_connection_error(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(exc=requests.exceptions.ConnectionError("refused")))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False
        assert msg.startswith("Connection failed")

    def test_timeout(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(exc=requests.exceptions.Timeout("t")))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False
        assert "Timed out" in msg

    def test_other_request_exception(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(exc=RuntimeError("weird")))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False
        assert msg.startswith("Request error")

    def test_unauthorized_401(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(_http(401, {"error": "nope"})))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "Unauthorized (401)" in msg

    def test_not_found_404(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(_http(404, {})))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "Not found (404)" in msg

    def test_bad_request_400_with_json_detail(self, monkeypatch):
        _with_session(
            monkeypatch,
            _FakeSession(_http(400, {"error": {"message": "model unknown"}})),
        )
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "Bad request (400): model unknown" in msg

    def test_bad_request_400_text_fallback(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(_http(400, text="plain failure")))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "Bad request (400)" in msg and "plain failure" in msg

    def test_other_http_error(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(_http(503, text="down")))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "HTTP 503" in msg

    def test_unexpected_response_shape(self, monkeypatch):
        _with_session(monkeypatch, _FakeSession(_http(200, {"choices": []})))
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is False and "Unexpected response shape" in msg

    def test_success_message(self, monkeypatch):
        session = _FakeSession(_http(200, {"choices": [{"message": {"content": "OK"}}]}))
        _with_session(monkeypatch, session)
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is True and "Connected" in msg and "OK" in msg
        (call,) = session.calls
        assert call["url"] == "https://api.example.com/v1/chat/completions"
        assert call["headers"]["Authorization"] == "Bearer k"
        assert call["json"]["max_tokens"] == 10
        assert call["json"]["temperature"] == 0.0

    def test_success_long_preview_truncated(self, monkeypatch):
        long_reply = "x" * 100
        _with_session(
            monkeypatch,
            _FakeSession(_http(200, {"choices": [{"message": {"content": long_reply}}]})),
        )
        ok, msg = probe("https://api.example.com/v1", "k", "m")
        assert ok is True
        assert "…" in msg  # the >60 char preview ellipsis

    def test_openrouter_gets_referer_headers(self, monkeypatch):
        session = _FakeSession(_http(200, {"choices": [{"message": {"content": "OK"}}]}))
        _with_session(monkeypatch, session)
        probe("https://openrouter.ai/api/v1", "k", "m")
        (call,) = session.calls
        assert call["headers"]["HTTP-Referer"] == "https://elixir.local"
        assert call["headers"]["X-Title"] == "Elixir"

    def test_custom_timeout_forwarded(self, monkeypatch):
        session = _FakeSession(_http(200, {"choices": [{"message": {"content": "OK"}}]}))
        _with_session(monkeypatch, session)
        probe("https://api.example.com/v1", "k", "m", timeout=7)
        assert session.calls[0]["timeout"] == 7

    def test_trailing_slash_base_url_normalized(self, monkeypatch):
        session = _FakeSession(_http(200, {"choices": [{"message": {"content": "OK"}}]}))
        _with_session(monkeypatch, session)
        probe("https://api.example.com/v1/", "k", "m")
        assert session.calls[0]["url"] == "https://api.example.com/v1/chat/completions"


# ════════════════════════════════════════════════════════════════════════════
# claude_provider
# ════════════════════════════════════════════════════════════════════════════


def _claude_response(content) -> requests.Response:
    return _http(200, {"content": content})


def _claude_sess_patch(**post_kwargs):
    """Patch the Claude transport seam (the top-level session_for_url import
    in core.llm.claude_provider — V0.6.7 review-loop A5) with a mock pooled
    session; same assertions as the old requests.post patches, redirected to
    the session's ``.post``."""
    sess = MagicMock()
    sess.post = MagicMock(**post_kwargs)
    return patch("core.llm.claude_provider.session_for_url", return_value=sess), sess


@pytest.fixture
def claude_logs() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def claude(claude_logs) -> ClaudeProvider:
    return ClaudeProvider(
        model="claude-3-5-sonnet-20241022",
        api_key="sk-ant",
        timeout=30,
        retries=0,
        log_callback=lambda msg, level="INFO": claude_logs.append((level, msg)),
    )


class TestClaudeComplete:
    def test_missing_api_key_returns_none(self, claude_logs):
        p = ClaudeProvider(
            api_key="",
            retries=0,
            log_callback=lambda msg, level="INFO": claude_logs.append((level, msg)),
        )
        assert p.complete("p") is None
        assert any("API key not set" in m for (_, m) in claude_logs)

    def test_success_single_text_block(self, claude, monkeypatch):
        patcher, sess = _claude_sess_patch(
            return_value=_claude_response([{"type": "text", "text": "  ans  "}])
        )
        with patcher:
            assert claude.complete("p") == "ans"
        kwargs = sess.post.call_args.kwargs
        assert kwargs["headers"]["x-api-key"] == "sk-ant"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        assert kwargs["json"]["model"] == "claude-3-5-sonnet-20241022"
        assert kwargs["json"]["max_tokens"] == 4096
        assert sess.post.call_args.args[0].endswith("/messages")

    def test_success_multiple_blocks_joined(self, claude):
        patcher, _sess = _claude_sess_patch(
            return_value=_claude_response(
                [
                    {"type": "text", "text": "part1"},
                    {"type": "other"},
                    {"type": "text", "text": " part2"},
                ]
            )
        )
        with patcher:
            assert claude.complete("p") == "part1 part2"

    def test_max_tokens_capped_at_8192(self, claude):
        patcher, sess = _claude_sess_patch(
            return_value=_claude_response([{"type": "text", "text": "x"}])
        )
        with patcher:
            claude.complete("p", max_tokens=16000)
        assert sess.post.call_args.kwargs["json"]["max_tokens"] == 8192

    def test_overrides_forwarded(self, claude):
        patcher, sess = _claude_sess_patch(
            return_value=_claude_response([{"type": "text", "text": "x"}])
        )
        with patcher:
            claude.complete("p", temperature=0.2, max_tokens=100, model="other")
        payload = sess.post.call_args.kwargs["json"]
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 100
        assert payload["model"] == "other"

    def test_empty_content_retries_then_none(self, claude, claude_logs):
        patcher, _sess = _claude_sess_patch(return_value=_claude_response([]))
        with patcher:
            assert claude.complete("p") is None

    def test_content_not_list_returns_none(self, claude):
        patcher, _sess = _claude_sess_patch(return_value=_http(200, {"content": "just a string"}))
        with patcher:
            assert claude.complete("p") is None

    def test_http_401_actionable_log(self, claude, claude_logs):
        patcher, _sess = _claude_sess_patch(return_value=_http(401, {}))
        with patcher:
            assert claude.complete("p") is None
        assert any("API key invalid or expired" in m for (_, m) in claude_logs)

    def test_http_429_rate_limited_log(self, claude, claude_logs):
        patcher, _sess = _claude_sess_patch(return_value=_http(429, {}))
        with patcher:
            assert claude.complete("p") is None
        assert any("rate limited" in m for (_, m) in claude_logs)

    def test_http_other_status_log(self, claude, claude_logs):
        patcher, _sess = _claude_sess_patch(return_value=_http(500, {}))
        with patcher:
            assert claude.complete("p") is None
        assert any("HTTP 500" in m for (_, m) in claude_logs)

    def test_connection_error_returns_none(self, claude, claude_logs):
        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("refused")

        patcher, _sess = _claude_sess_patch(side_effect=boom)
        with patcher:
            assert claude.complete("p") is None
        assert any("call failed" in m for (_, m) in claude_logs)

    def test_retryable_500_retried_then_success(self, claude_logs):
        p = ClaudeProvider(
            api_key="k",
            retries=1,
            log_callback=lambda msg, level="INFO": claude_logs.append((level, msg)),
        )
        responses = [_http(500, {}), _claude_response([{"type": "text", "text": "ok"}])]
        patcher, _sess = _claude_sess_patch(side_effect=responses)
        with (
            patcher,
            patch("core.llm.retry._HAS_TENACITY", False),
            patch("core.llm.retry.time.sleep"),
        ):
            assert p.complete("p") == "ok"


# ════════════════════════════════════════════════════════════════════════════
# llm_provider_impl — factory + base class + keep_alive
# ════════════════════════════════════════════════════════════════════════════


class _DictSettings:
    """The minimal ``settings.get(path, default)`` surface create_provider uses."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = data or {}

    def get(self, path: str, default=None):
        return self._data.get(path, default)


class TestCreateProviderFactory:
    def test_openrouter_provider(self):
        from core.llm.llm_provider_impl import create_provider

        s = _DictSettings(
            {
                "summarisation.cloud_model": "m",
                "summarisation.api_base_url": "https://openrouter.ai/api/v1",
                "summarisation.api_key": "sk",
            }
        )
        from core.llm.openai_compat_provider import OpenAICompatProvider

        p = create_provider("openrouter", s)
        assert isinstance(p, OpenAICompatProvider)
        assert p.model == "m"
        assert p.api_key == "sk"
        assert p.label == "Openrouter"

    def test_openai_compatible_provider(self):
        from core.llm.llm_provider_impl import create_provider
        from core.llm.openai_compat_provider import OpenAICompatProvider

        s = _DictSettings({"summarisation.cloud_model": "gpt-x"})
        p = create_provider("openai_compatible", s)
        assert isinstance(p, OpenAICompatProvider)
        assert p.label == "Openai_compatible"

    def test_openai_provider(self):
        from core.llm.llm_provider_impl import create_provider
        from core.llm.openai_compat_provider import OpenAICompatProvider

        p = create_provider("openai", _DictSettings({}))
        assert isinstance(p, OpenAICompatProvider)
        assert p.base_url == "https://openrouter.ai/api/v1"  # default

    def test_freellmapi_provider(self):
        from core.llm.llm_provider_impl import create_provider
        from core.llm.openai_compat_provider import OpenAICompatProvider

        s = _DictSettings(
            {
                "summarisation.freellmapi_model": "auto",
                "summarisation.freellmapi_url": "http://localhost:3001/v1",
                "summarisation.freellmapi_key": "fk",
            }
        )
        p = create_provider("freellmapi", s)
        assert isinstance(p, OpenAICompatProvider)
        assert p.model == "auto"
        assert p.api_key == "fk"
        assert p.label == "FreeLLMAPI"

    def test_claude_provider(self):
        from core.llm.claude_provider import ClaudeProvider
        from core.llm.llm_provider_impl import create_provider

        s = _DictSettings(
            {
                "summarisation.claude_model": "claude-x",
                "summarisation.claude_api_key": "ck",
            }
        )
        p = create_provider("claude", s)
        assert isinstance(p, ClaudeProvider)
        assert p.model == "claude-x"
        assert p.api_key == "ck"

    def test_unknown_provider_defaults_to_ollama(self):
        from core.llm.llm_provider_impl import create_provider
        from core.llm.ollama_provider import OllamaProvider

        p = create_provider("nonsense", _DictSettings({"summarisation.model": "mm"}))
        assert isinstance(p, OllamaProvider)
        assert p.model == "mm"

    def test_ollama_provider(self):
        from core.llm.llm_provider_impl import create_provider
        from core.llm.ollama_provider import OllamaProvider

        p = create_provider("ollama", _DictSettings({"summarisation.model": "mm"}))
        assert isinstance(p, OllamaProvider)

    def test_llamacpp_provider(self):
        from core.llm.llamacpp_provider import LlamaCppProvider
        from core.llm.llm_provider_impl import create_provider

        s = _DictSettings(
            {
                "summarisation.llamacpp_model": "ternary",
                "summarisation.llamacpp_base_url": "http://127.0.0.1:9000/v1",
                "local.http_timeout_sec": 123,
            }
        )
        p = create_provider("llamacpp", s)
        assert isinstance(p, LlamaCppProvider)
        assert p.base_url == "http://127.0.0.1:9000/v1"
        assert p.timeout == 123


class TestLLMProviderBase:
    def test_complete_raises_not_implemented(self):
        from core.llm.llm_provider_impl import LLMProvider

        with pytest.raises(NotImplementedError):
            LLMProvider().complete("p")

    def test_complete_streaming_default_fallback(self):
        from core.llm.llm_provider_impl import LLMProvider

        chunks: list[str] = []

        class _Sub(LLMProvider):
            def complete(
                self, prompt, temperature=None, max_tokens=None, model=None, json_mode=False
            ):
                return "streamed text"

        p = _Sub()
        assert p.complete_streaming("p", on_chunk=chunks.append) == "streamed text"
        assert chunks == ["streamed text"]

    def test_complete_streaming_no_callback(self):
        from core.llm.llm_provider_impl import LLMProvider

        class _Sub(LLMProvider):
            def complete(
                self, prompt, temperature=None, max_tokens=None, model=None, json_mode=False
            ):
                return "x"

        assert _Sub().complete_streaming("p") == "x"

    def test_complete_streaming_none_result_no_chunk(self):
        from core.llm.llm_provider_impl import LLMProvider

        chunks: list[str] = []

        class _Sub(LLMProvider):
            def complete(
                self, prompt, temperature=None, max_tokens=None, model=None, json_mode=False
            ):
                return None

        assert _Sub().complete_streaming("p", on_chunk=chunks.append) is None
        assert chunks == []


class TestGetKeepAlive:
    def test_reads_settings_and_caches(self, monkeypatch):
        from core.llm import llm_provider_impl as impl

        monkeypatch.setattr(impl._runtime_state, "keep_alive_cache", None)
        monkeypatch.setattr(
            "utils.settings.Settings",
            lambda: SimpleNamespace(get=lambda path, default=None: "45m"),
        )
        assert impl._get_keep_alive() == "45m"
        assert impl._runtime_state.keep_alive_cache == "45m"

    def test_settings_failure_falls_back_to_30m(self, monkeypatch):
        from core.llm import llm_provider_impl as impl

        monkeypatch.setattr(impl._runtime_state, "keep_alive_cache", None)

        def broken_settings():
            raise RuntimeError("no settings for you")

        monkeypatch.setattr("utils.settings.Settings", broken_settings)
        assert impl._get_keep_alive() == "30m"

    def test_cached_value_short_circuits(self, monkeypatch):
        from core.llm import llm_provider_impl as impl

        monkeypatch.setattr(impl._runtime_state, "keep_alive_cache", "9m")
        assert impl._get_keep_alive() == "9m"


class TestLazyProviderAttr:
    def test_getattr_loads_provider_modules(self):
        import core.llm.llm_provider_impl as impl

        assert impl.OllamaProvider.__name__ == "OllamaProvider"
        assert impl.LlamaCppProvider.__name__ == "LlamaCppProvider"
        assert impl.OpenAICompatProvider.__name__ == "OpenAICompatProvider"
        assert impl.ClaudeProvider.__name__ == "ClaudeProvider"

    def test_unknown_attribute_raises(self):
        import core.llm.llm_provider_impl as impl

        with pytest.raises(AttributeError, match="has no attribute"):
            impl.NotAProvider  # noqa: B018
