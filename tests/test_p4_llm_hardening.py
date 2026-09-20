"""Phase 4.4 (LLM-call hardening audit) — evidence tests for the hardened paths.

Companion to ``docs/LLM_HARDENING.md`` (the audit matrix). Every test here
proves one cell of the provider × guarantee matrix at the REAL production
seam — the HTTP boundary — following the conventions of
``tests/test_p2_llm_llamacpp.py`` / ``tests/test_p2_llm_openai_compat.py``:

Per provider (ollama / llamacpp / openai-compat [openrouter, openai,
openai_compatible, freellmapi] / claude / freellmapi-inline-dispatcher):

  * **timeout is actually passed to the HTTP layer** — the fake session /
    request function records the ``timeout`` kwarg and we assert it equals
    the provider's configured timeout (a timeout that never reaches the
    socket is a docstring, not a guarantee).
  * **classified retry** — ``requests.ConnectionError`` is retried with a
    recorded backoff sleep, while HTTP 404 (model not found) is NOT
    retried (exactly one HTTP call).
  * **non-retryable handling** — Ollama OOM halves ``num_ctx`` and retries
    once; timeout returns None immediately (the V18.2.19 stall rule).

For ``core/llm/structured_io.py``: the Phase-4.4 lenient-repair pass —
trailing commas, fenced ``\\`\\`\\`json`` blocks, Python-style ``\\'``
escapes and smart quotes are repaired and validated; truncated JSON
returns None safely (never raises). Plus the V0.11 repair ladder through
``response_parser.parse_response`` (the production XML-path integration).

Hermeticity: no socket is ever opened. Every HTTP boundary is monkey-
patched (``core.llm.ollama_provider.safe_ollama_request``,
``core.llm.llamacpp_provider._no_proxy_session``, ``requests.post``,
``core.summarisation.llm_dispatcher.session_for_url``). The suite's
autouse raising-keyring stub (conftest.py) keeps the factory tests off
the real OS keychain.

Retry determinism: the classified-retry tests force
``core.llm.retry._HAS_TENACITY = False`` and stub ``time.sleep`` so the
deterministic 2-attempt LINEAR fallback runs in every environment (with
or without tenacity installed). The attempt cap (2), the classification
(retryable vs non-retryable) and the backoff-sleep recording are
identical on both implementations; the tenacity-specific wait curve is
covered by ``tests/test_retry.py``.

Run: ``python3 -m pytest tests/test_p4_llm_hardening.py -q --no-cov -p no:cacheprovider``
"""

from __future__ import annotations

import json
import math
import sys
import time
import types
from pathlib import Path

import pytest
import requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.llm.llamacpp_provider as lp  # noqa: E402
import core.llm.retry as retry_mod  # noqa: E402
import core.llm.structured_io as sio  # noqa: E402
import core.summarisation.llm_dispatcher as ld  # noqa: E402
import core.summarisation.response_parser as rp  # noqa: E402
from core.llm.claude_provider import ClaudeProvider  # noqa: E402
from core.llm.llamacpp_provider import LlamaCppProvider  # noqa: E402
from core.llm.ollama_provider import OllamaProvider  # noqa: E402
from core.llm.openai_compat_provider import OpenAICompatProvider  # noqa: E402

# ── Shared fakes (requests-shape objects; no sockets) ───────────────────────


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> requests.Response:
    """A real ``requests.Response`` hand-built from a payload (the
    test_p2_llm_llamacpp.py pattern — real ``.json()`` / ``.raise_for_status``
    / context-manager semantics, zero network)."""
    r = requests.Response()
    r.status_code = status
    if payload is not None:
        r._content = json.dumps(payload).encode()
        r.headers["Content-Type"] = "application/json"
    else:
        r._content = text.encode()
    r.encoding = "utf-8"
    r.raw = types.SimpleNamespace(close=lambda: None)  # `with resp:` needs raw.close()
    r._content_consumed = True
    return r


def _iter_lines(self, decode_unicode=False, **kwargs):
    # SSE lines from the pre-consumed body — same contract as the llamacpp
    # suite's fixture (kept as a local fixture here; conftest.py is frozen).
    yield from self._content.decode("utf-8").splitlines()


@pytest.fixture(autouse=True)
def _patched_iter_lines(monkeypatch):
    """Patch ``requests.Response.iter_lines`` for THIS module only.

    The llamacpp SSE path decodes pre-consumed bodies; a raw class patch
    would poison later modules that drive the real requests stack (the
    Phase-2 interference lesson recorded in the worklog).
    """
    monkeypatch.setattr(requests.Response, "iter_lines", _iter_lines)


class _FakeSession:
    """A ``requests.Session`` stand-in that RECORDS the timeout kwarg.

    (The Phase-2 fakes recorded method/url/json but not ``timeout`` — these
    tests exist to prove the timeout reaches the transport, so the kwarg is
    the primary assertion target.)
    """

    def __init__(self, responses=None, exc=None) -> None:
        self._responses = list(responses or [])
        self._exc = exc
        self.requests: list[dict] = []
        self.closed = False

    def _next(self):
        if self._exc is not None:
            raise self._exc
        if not self._responses:
            raise AssertionError("unexpected extra HTTP call (script exhausted)")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, headers=None, json=None, timeout=None, stream=False):
        self.requests.append(
            {"method": "POST", "url": url, "json": json, "timeout": timeout, "stream": stream}
        )
        return self._next()

    def get(self, url, headers=None, timeout=None):
        self.requests.append({"method": "GET", "url": url, "timeout": timeout})
        return self._next()

    def close(self):
        self.closed = True


def _use_session(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> _FakeSession:
    monkeypatch.setattr(lp, "_no_proxy_session", lambda: session)
    return session


def _sse(*chunks: str, done: bool = True) -> requests.Response:
    lines = []
    for c in chunks:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": c}}]}))
        lines.append("")  # SSE event separator — the provider must skip it
    if done:
        lines.append("data: [DONE]")
    return _resp(200, text="\n".join(lines))


@pytest.fixture
def deterministic_retry(monkeypatch) -> list[float]:
    """Force the no-tenacity LINEAR fallback + record (not perform) sleeps.

    ``retry_llm_call`` reads ``_HAS_TENACITY`` at decoration time — inside
    ``complete()`` — so patching it here switches every provider in scope to
    the deterministic 2-attempt fallback whose waits go through
    ``time.sleep`` (stubbed). The recorded sleeps prove the backoff actually
    happens; the identical classifier drives both implementations.
    """
    monkeypatch.setattr(retry_mod, "_HAS_TENACITY", False)
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    return sleeps


# ── ollama — core/llm/ollama_provider.py ────────────────────────────────────


def _stub_supervisor() -> tuple[types.SimpleNamespace, dict]:
    rec = {"fail": 0, "ok": 0}

    def _fail() -> bool:
        rec["fail"] += 1
        return False

    def _ok() -> None:
        rec["ok"] += 1

    return types.SimpleNamespace(record_failure=_fail, record_success=_ok), rec


def _ollama_provider(**overrides) -> tuple[OllamaProvider, list[tuple[str, str]]]:
    logs: list[tuple[str, str]] = []
    supervisor, _ = _stub_supervisor()
    kwargs: dict = dict(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=42,
        retries=1,
        log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        supervisor=supervisor,
    )
    kwargs.update(overrides)
    return OllamaProvider(**kwargs), logs


def _patch_ollama_transport(
    monkeypatch: pytest.MonkeyPatch, script: list
) -> tuple[list[dict], list[dict]]:
    """Patch ``safe_ollama_request`` + token counter + model list at the
    ollama_provider module seam. Returns (recorded calls, recorded payloads)."""
    calls: list[dict] = []

    def _fake_safe_request(method, url, timeout=None, **kwargs):
        # Deep-copy the payload at call time — _do_one_call MUTATES
        # options.num_ctx in place between attempts (the OOM halving), and a
        # shared reference would erase the per-attempt history.
        import copy

        calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                "json": copy.deepcopy(kwargs.get("json")),
            }
        )
        if not script:
            raise AssertionError("unexpected extra ollama HTTP call")
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr("core.llm.ollama_provider.safe_ollama_request", _fake_safe_request)
    # Deterministic adaptive-context math: 100 prompt tokens → ctx 16000
    # (100 + max_tokens + 4096 margin, floored at Ollama's 16000 minimum).
    monkeypatch.setattr("core.llm.ollama_provider._count_tokens", lambda p: 100)
    # The 404 handler lists installed models — must never touch the network.
    monkeypatch.setattr("utils.network.list_ollama_models", lambda base_url: ["other:latest"])
    return calls, []


class TestOllamaProviderHardening:
    def test_timeout_reaches_http_layer(self, monkeypatch):
        calls, _ = _patch_ollama_transport(monkeypatch, [_resp(200, {"response": "text"})])
        p, _logs = _ollama_provider()
        assert p.complete("prompt") == "text"
        assert len(calls) == 1
        assert calls[0]["timeout"] == 42  # the configured timeout, verbatim
        assert calls[0]["method"] == "POST"
        assert calls[0]["url"].endswith("/api/generate")

    def test_connection_error_retried_with_backoff_then_succeeds(
        self, monkeypatch, deterministic_retry
    ):
        _patch_ollama_transport(
            monkeypatch,
            [
                requests.exceptions.ConnectionError("refused"),
                _resp(200, {"response": "recovered"}),
            ],
        )
        p, _logs = _ollama_provider(retries=1)
        assert p.complete("prompt") == "recovered"
        assert len(deterministic_retry) == 1  # one backoff sleep before attempt 2
        assert deterministic_retry[0] > 0

    def test_http_404_model_not_found_not_retried(self, monkeypatch, deterministic_retry):
        err = requests.exceptions.HTTPError(
            "404 Client Error", response=_resp(404, {"error": "model not found"})
        )
        calls, _ = _patch_ollama_transport(monkeypatch, [err])
        p, logs = _ollama_provider(retries=1)
        assert p.complete("prompt") is None
        assert len(calls) == 1  # exactly ONE call — 404 never retried
        assert deterministic_retry == []  # no backoff sleep either
        assert any("ollama pull test-model" in m for (_, m) in logs)

    def test_empty_response_is_retryable(self, monkeypatch, deterministic_retry):
        _patch_ollama_transport(
            monkeypatch,
            [
                _resp(200, {"response": "   "}),
                _resp(200, {"response": "got it"}),
            ],
        )
        p, _logs = _ollama_provider(retries=1)
        assert p.complete("prompt") == "got it"

    def test_oom_halves_num_ctx_and_retries_once(self, monkeypatch, deterministic_retry):
        oom = requests.exceptions.HTTPError(
            "500 Server Error: cuda out of memory for url http://localhost:11434/api/generate"
        )
        calls, _ = _patch_ollama_transport(monkeypatch, [oom, _resp(200, {"response": "ok"})])
        p, logs = _ollama_provider(retries=1)
        assert p.complete("prompt") == "ok"
        # V10.18.0 (A4): the second call must run at the HALVED context.
        ctx_sequence = [c["json"]["options"]["num_ctx"] for c in calls]
        assert ctx_sequence == [16000, 8192]
        assert any("VRAM OOM" in m for (_, m) in logs)
        assert deterministic_retry == []  # OOM is not a backoff-retryable error

    def test_timeout_returns_none_without_retry(self, monkeypatch, deterministic_retry):
        calls, _ = _patch_ollama_transport(monkeypatch, [requests.exceptions.Timeout("stalled")])
        p, logs = _ollama_provider(retries=1)
        assert p.complete("prompt") is None
        assert len(calls) == 1  # V18.2.19: timeout = model stall, not transient
        assert deterministic_retry == []
        assert any("NOT retrying" in m for (_, m) in logs)


# ── llamacpp — core/llm/llamacpp_provider.py ────────────────────────────────


def _llamacpp_provider(**overrides) -> tuple[LlamaCppProvider, list[tuple[str, str]]]:
    logs: list[tuple[str, str]] = []
    kwargs: dict = dict(
        model="test-model",
        base_url="http://127.0.0.1:8080/v1",
        api_key="local",
        max_tokens=12288,
        context_tokens=65536,
        timeout=30,
        retries=1,
        log_callback=lambda msg, level="INFO": logs.append((level, msg)),
    )
    kwargs.update(overrides)
    return LlamaCppProvider(**kwargs), logs


@pytest.fixture
def stub_llamacpp_tokens(monkeypatch):
    """Deterministic fit_max_tokens math (prompt ≈ 10 tokens)."""
    monkeypatch.setattr(lp, "_count_tokens", lambda p: 10)


class TestLlamaCppProviderHardening:
    def test_streaming_timeout_reaches_http_layer(self, monkeypatch, stub_llamacpp_tokens):
        sess = _use_session(monkeypatch, _FakeSession([_sse("chunked")]))
        p, _logs = _llamacpp_provider()
        assert p.complete("prompt") == "chunked"
        assert len(sess.requests) == 1
        assert sess.requests[0]["timeout"] == 30  # per-chunk read timeout
        assert sess.requests[0]["stream"] is True

    def test_nonstreaming_fallback_timeout_is_budget_derived(
        self, monkeypatch, stub_llamacpp_tokens
    ):
        # Streaming transport dies → the non-streaming fallback derives its
        # timeout from the output budget at the pessimistic 2 tok/s floor:
        # max(30, ceil(12288 / 2) + 60) = 6204s.
        sess = _use_session(
            monkeypatch,
            _FakeSession(
                [
                    requests.exceptions.ConnectionError("proxy mangled SSE"),
                    _resp(200, {"choices": [{"message": {"content": "ns-ok"}}]}),
                ]
            ),
        )
        p, _logs = _llamacpp_provider(retries=0)
        assert p.complete("prompt") == "ns-ok"
        expected = max(30, math.ceil(12288 / lp.LLAMACPP_MIN_TOKENS_PER_SEC) + 60)
        assert sess.requests[1]["timeout"] == expected
        assert sess.requests[1]["stream"] is False

    def test_smoke_test_timeout_cap_reaches_http_layer(self, monkeypatch):
        # Phase 4.4 fix: smoke_test's min(self.timeout, 60) probe cap was
        # computed but never forwarded — the probe always used the FULL
        # provider timeout (600s stall risk during preflight).
        sess = _use_session(monkeypatch, _FakeSession([_sse("hi"), _sse("hi")]))
        p, _logs = _llamacpp_provider(timeout=600)
        assert p.smoke_test() is True
        assert sess.requests[0]["timeout"] == 60  # min(600, 60) — now honored
        assert p.smoke_test(timeout=9) is True
        assert sess.requests[1]["timeout"] == 9  # explicit override honored too

    def test_connection_error_retried_with_backoff_then_succeeds(
        self, monkeypatch, stub_llamacpp_tokens, deterministic_retry
    ):
        # attempt 1: streaming ConnError → non-streaming fallback ConnError
        # → retryable → backoff; attempt 2: streaming succeeds.
        sess = _use_session(
            monkeypatch,
            _FakeSession(
                [
                    requests.exceptions.ConnectionError("reset"),
                    requests.exceptions.ConnectionError("reset again"),
                    _sse("recovered"),
                ]
            ),
        )
        p, _logs = _llamacpp_provider(retries=1)
        assert p.complete("prompt") == "recovered"
        assert len(sess.requests) == 3
        assert len(deterministic_retry) == 1
        assert deterministic_retry[0] > 0

    def test_http_404_not_retried(self, monkeypatch, stub_llamacpp_tokens, deterministic_retry):
        sess = _use_session(
            monkeypatch,
            _FakeSession([_resp(404, {"error": {"code": 404, "message": "not served"}})]),
        )
        p, logs = _llamacpp_provider(retries=1)
        assert p.complete("prompt") is None
        assert len(sess.requests) == 1  # one call only — 404 is non-retryable
        assert deterministic_retry == []
        assert any("call failed" in m for (_, m) in logs)

    def test_context_400_actionable_message_no_retry(
        self, monkeypatch, stub_llamacpp_tokens, deterministic_retry
    ):
        _use_session(
            monkeypatch,
            _FakeSession(
                [_resp(400, {"error": {"code": 400, "message": "exceeds the context size"}})] * 2
            ),
        )
        p, logs = _llamacpp_provider(retries=1)
        assert p.complete("prompt") is None
        assert any("exceeds the server's context" in m for (_, m) in logs)
        assert deterministic_retry == []  # 400 = caller error, never retried

    def test_complete_streaming_connection_error_retried_after_hardening(
        self, monkeypatch, stub_llamacpp_tokens, deterministic_retry
    ):
        # Phase 4.4 fix: the streaming-with-callback path now shares
        # complete()'s classified retry. Combined attempt 1 fails at the
        # transport level (streaming + non-streaming fallback); attempt 2
        # succeeds. Pre-fix this returned None after 2 HTTP calls.
        sess = _use_session(
            monkeypatch,
            _FakeSession(
                [
                    requests.exceptions.ConnectionError("reset"),
                    requests.exceptions.ConnectionError("reset again"),
                    _sse("streamed-recovered"),
                ]
            ),
        )
        p, _logs = _llamacpp_provider(retries=1)
        seen: list[str] = []
        assert p.complete_streaming("prompt", on_chunk=seen.append) == "streamed-recovered"
        assert len(sess.requests) == 3
        assert len(deterministic_retry) == 1

    def test_complete_streaming_404_not_retried(
        self, monkeypatch, stub_llamacpp_tokens, deterministic_retry
    ):
        sess = _use_session(
            monkeypatch,
            _FakeSession(
                [
                    _resp(404, {"error": {"code": 404, "message": "not served"}}),
                    _resp(404, {"error": {"code": 404, "message": "not served"}}),
                ]
            ),
        )
        p, _logs = _llamacpp_provider(retries=1)
        assert p.complete_streaming("prompt") is None
        # 2 calls = the single combined attempt (streaming + its non-streaming
        # fallback). The 404 is non-retryable → NO second attempt.
        assert len(sess.requests) == 2
        assert deterministic_retry == []


# ── openai-compat — core/llm/openai_compat_provider.py ─────────────────────
# (serves openrouter / openai / openai_compatible / freellmapi)


def _openai_provider(**overrides) -> tuple[OpenAICompatProvider, list[tuple[str, str]]]:
    logs: list[tuple[str, str]] = []
    kwargs: dict = dict(
        model="m",
        base_url="http://localhost:3001/v1",
        api_key="k",
        timeout=77,
        retries=1,
        label="FreeLLMAPI",
        log_callback=lambda msg, level="INFO": logs.append((level, msg)),
    )
    kwargs.update(overrides)
    return OpenAICompatProvider(**kwargs), logs


def _cloud_ok(text: str = "ok") -> requests.Response:
    return _resp(200, {"choices": [{"message": {"content": text}}]})


class TestOpenAICompatHardening:
    def test_timeout_reaches_http_layer(self, monkeypatch):
        calls: list[dict] = []

        def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            calls.append({"url": url, "timeout": timeout})
            return _cloud_ok("text")

        monkeypatch.setattr(requests, "post", _fake_post)
        p, _logs = _openai_provider()
        assert p.complete("prompt") == "text"
        assert calls[0]["timeout"] == 77
        assert calls[0]["url"].endswith("/chat/completions")

    def test_connection_error_retried_with_backoff_then_succeeds(
        self, monkeypatch, deterministic_retry
    ):
        script = [requests.exceptions.ConnectionError("refused"), _cloud_ok("second try")]

        def _fake_post(url, **kwargs):
            item = script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(requests, "post", _fake_post)
        p, _logs = _openai_provider(retries=1)
        assert p.complete("prompt") == "second try"
        assert len(deterministic_retry) == 1
        assert deterministic_retry[0] > 0

    def test_http_404_not_retried(self, monkeypatch, deterministic_retry):
        calls: list[int] = []

        def _fake_post(url, **kwargs):
            calls.append(1)
            return _resp(404, {"error": {"message": "model m not found"}})

        monkeypatch.setattr(requests, "post", _fake_post)
        p, logs = _openai_provider(retries=1)
        assert p.complete("prompt") is None
        assert len(calls) == 1  # raise_for_status → HTTPError 404 → non-retryable
        assert deterministic_retry == []
        assert any("call failed" in m for (_, m) in logs)

    def test_freellmapi_factory_wires_class_timeout_and_label(self):
        from core.llm.llm_provider_impl import create_provider

        class _Settings:
            def get(self, key, default=None):
                return {
                    "summarisation.freellmapi_model": "auto",
                    "summarisation.freellmapi_url": "http://localhost:3001/v1",
                    "summarisation.temperature": 0.6,
                    "summarisation.max_output_tokens": 4096,
                }.get(key, default)

        p = create_provider("freellmapi", _Settings())
        assert isinstance(p, OpenAICompatProvider)
        assert p.timeout == 300  # explicit factory-wired timeout
        assert p.label == "FreeLLMAPI"
        assert p.base_url == "http://localhost:3001/v1"

    def test_empty_response_is_retryable(self, monkeypatch, deterministic_retry):
        script = [_resp(200, {"choices": [{"message": {"content": "  "}}]}), _cloud_ok("filled")]

        def _fake_post(url, **kwargs):
            item = script.pop(0)
            return item

        monkeypatch.setattr(requests, "post", _fake_post)
        p, _logs = _openai_provider(retries=1)
        assert p.complete("prompt") == "filled"


# ── claude — core/llm/claude_provider.py ────────────────────────────────────


def _claude_ok(text: str = "ok") -> requests.Response:
    return _resp(200, {"content": [{"type": "text", "text": text}]})


class TestClaudeProviderHardening:
    def _provider(self, **overrides) -> tuple[ClaudeProvider, list[tuple[str, str]]]:
        logs: list[tuple[str, str]] = []
        kwargs: dict = dict(
            model="claude-3-5-sonnet-20241022",
            api_key="sk-ant",
            timeout=55,
            retries=1,
            log_callback=lambda msg, level="INFO": logs.append((level, msg)),
        )
        kwargs.update(overrides)
        return ClaudeProvider(**kwargs), logs

    def test_timeout_reaches_http_layer(self, monkeypatch):
        calls: list[dict] = []

        def _fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            calls.append({"url": url, "timeout": timeout, "headers": headers})
            return _claude_ok("ans")

        monkeypatch.setattr(requests, "post", _fake_post)
        p, _logs = self._provider()
        assert p.complete("prompt") == "ans"
        assert calls[0]["timeout"] == 55
        assert calls[0]["url"].endswith("/messages")
        assert calls[0]["headers"]["x-api-key"] == "sk-ant"

    def test_connection_error_retried_with_backoff_then_succeeds(
        self, monkeypatch, deterministic_retry
    ):
        script = [requests.exceptions.ConnectionError("refused"), _claude_ok("second")]

        def _fake_post(url, **kwargs):
            item = script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(requests, "post", _fake_post)
        p, _logs = self._provider(retries=1)
        assert p.complete("prompt") == "second"
        assert len(deterministic_retry) == 1

    def test_http_401_not_retried_actionable_log(self, monkeypatch, deterministic_retry):
        calls: list[int] = []

        def _fake_post(url, **kwargs):
            calls.append(1)
            return _resp(401, {})

        monkeypatch.setattr(requests, "post", _fake_post)
        p, logs = self._provider(retries=1)
        assert p.complete("prompt") is None
        assert len(calls) == 1  # bad API key — retrying is pointless
        assert deterministic_retry == []
        assert any("API key invalid or expired" in m for (_, m) in logs)


# ── freellmapi inline dispatcher — core/summarisation/llm_dispatcher.py ─────


class TestDispatcherOpenAICompatHardening:
    def test_timeout_reaches_pooled_session(self, monkeypatch):
        sess = _FakeSession([_cloud_ok("dispatched")])
        monkeypatch.setattr(ld, "session_for_url", lambda url: sess)
        out = ld.call_openai_compat(
            "prompt",
            "http://localhost:3001/v1",
            "k",
            "auto",
            "FreeLLMAPI",
            0.3,
            512,
            timeout=99,
            retries=1,
            provider="freellmapi",
        )
        assert out == "dispatched"
        assert sess.requests[0]["timeout"] == 99

    def test_connection_error_retried_404_not(self, monkeypatch, deterministic_retry):
        sess = _FakeSession(
            [requests.exceptions.ConnectionError("refused"), _cloud_ok("recovered")]
        )
        monkeypatch.setattr(ld, "session_for_url", lambda url: sess)
        out = ld.call_openai_compat(
            "p",
            "http://localhost:3001/v1",
            "k",
            "auto",
            "FreeLLMAPI",
            0.3,
            512,
            timeout=99,
            retries=1,
            provider="freellmapi",
        )
        assert out == "recovered"
        assert len(deterministic_retry) == 1

        sess2 = _FakeSession([_resp(404, {"error": {"message": "no model"}})])
        monkeypatch.setattr(ld, "session_for_url", lambda url: sess2)
        deterministic_retry.clear()
        out2 = ld.call_openai_compat(
            "p",
            "http://localhost:3001/v1",
            "k",
            "auto",
            "FreeLLMAPI",
            0.3,
            512,
            timeout=99,
            retries=1,
            provider="freellmapi",
        )
        assert out2 is None
        assert len(sess2.requests) == 1  # 404 → non-retryable, single call
        assert deterministic_retry == []


# ── structured_io — lenient JSON repair (Phase 4.4) ─────────────────────────

_VALID = (
    '{"executive_summary": "e", "bullet_points": ["a"], '
    '"thorough_summary": "t", "key_distinctions": null, "theoretical_tensions": null}'
)


class TestStructuredIoLenientRepair:
    def test_valid_json_validated_untouched(self):
        result = sio.validate_summary_json(_VALID)
        assert result is not None
        assert result["executive_summary"] == "e"
        assert result["bullet_points"] == ["a"]

    def test_trailing_commas_repaired(self):
        raw = '{"executive_summary": "e", "bullet_points": ["a",], "thorough_summary": "t",}'
        result = sio.validate_summary_json(raw)
        assert result is not None
        assert result["bullet_points"] == ["a"]

    def test_fenced_json_block_with_trailing_commas_repaired(self):
        raw = (
            "```json\n"
            + ('{"executive_summary": "e", "bullet_points": ["a",], "thorough_summary": "t",}')
            + "\n```"
        )
        result = sio.validate_summary_json(raw)
        assert result is not None
        assert result["executive_summary"] == "e"

    def test_python_style_single_quote_escape_repaired(self):
        # The V0.10 rig failure: the model escaped single quotes Python-style
        # (\' — invalid strict JSON) inside a string quoting source text.
        raw = (
            '{"executive_summary": "the model\'s claim about \'Identity\'", '
            '"bullet_points": ["a"], "thorough_summary": "t"}'
        )
        result = sio.validate_summary_json(raw)
        assert result is not None
        assert result["executive_summary"] == "the model's claim about 'Identity'"

    def test_smart_quote_delimiters_repaired(self):
        raw = (
            "{\u201cexecutive_summary\u201d: \u201ce\u201d, "
            '"bullet_points": ["a"], "thorough_summary": "t"}'
        )
        result = sio.validate_summary_json(raw)
        assert result is not None
        assert result["executive_summary"] == "e"

    def test_truncated_json_returns_none_never_raises(self):
        truncated = '{"executive_summary": "e", "bullet_points": ["a"'
        assert sio.validate_summary_json(truncated) is None
        # Truncated inside a fenced block (no closing fence, unbalanced braces)
        assert sio.validate_summary_json("```json\n" + truncated) is None
        # Unrepairable garbage also fails soft
        assert sio.validate_summary_json("{not json at all") is None
        assert sio.validate_summary_json("") is None

    def test_repair_never_corrupts_valid_json(self, monkeypatch):
        # The repair pass must only run AFTER a strict failure: a spy on
        # response_parser._repair_llm_json proves valid JSON skips it.
        calls: list[str] = []
        real_repair = rp._repair_llm_json

        def _spy(text):
            calls.append(text)
            return real_repair(text)

        import core.summarisation.response_parser as rp_mod

        monkeypatch.setattr(rp_mod, "_repair_llm_json", _spy)
        assert sio.validate_summary_json(_VALID) is not None
        assert calls == []  # valid JSON never enters the repair path

    def test_manual_validation_path_also_repaired(self, monkeypatch):
        # The pydantic-absent degrade path (dict-shape check) shares the
        # same lenient repair pass.
        monkeypatch.setattr(sio, "_HAS_PYDANTIC", False)
        raw = '{"executive_summary": "e", "bullet_points": ["a",], "thorough_summary": "t",}'
        result = sio.validate_summary_json(raw)
        assert result is not None
        assert result["thorough_summary"] == "t"

    def test_complete_structured_repairs_without_fallback(self):
        # End-to-end through the adapter: a repairable-but-malformed response
        # is validated in structured_io — the XML fallback parser is NOT
        # invoked (pre-Phase-4.4 this fell through to the fallback).
        class _Provider:
            def complete(self, prompt, **kwargs):
                return (
                    "```json\n"
                    + (
                        '{"executive_summary": "e", "bullet_points": ["a",], '
                        '"thorough_summary": "t",}'
                    )
                    + "\n```"
                )

        fallback = []
        result = sio.complete_structured(
            _Provider(), "prompt", fallback_parser=lambda raw: fallback.append(raw) or {}
        )
        assert result is not None
        assert result["executive_summary"] == "e"
        assert fallback == []


# ── response_parser — the V0.11 repair ladder (production XML path) ─────────


class TestResponseParserLenientRepair:
    def test_fenced_json_with_trailing_commas_parsed(self):
        raw = (
            "```json\n"
            + (
                '{"executive_summary": "exec text", "bullet_points": ["bullet-one", "bullet-two",], '
                '"thorough_summary": "thorough text",}'
            )
            + "\n```"
        )
        parsed = rp.parse_response(raw)
        assert parsed["executive_summary"] == "exec text"
        assert parsed["bullet_points"] == ["bullet-one", "bullet-two"]
        assert parsed["thorough_summary"] == "thorough text"

    def test_rig_shape_python_escape_blob_recovered(self):
        # The original V0.10 rig failure shape: a claims blob whose strings
        # carry Python-style \' escapes — strict parse fails, the V0.11
        # repair recovers every claim (NOT banked as leftover thorough).
        raw = (
            '{"executive_summary": [{"claim": "the brain\'s default mode '
            'network", "supporting_text": "x"}], '
            '"bullet_points": [], "thorough_summary": []}'
        )
        parsed = rp.parse_response(raw)
        assert "default mode network" in parsed["executive_summary"]

    def test_unrepairable_json_falls_back_never_raises(self):
        assert rp.parse_response("{ truncated beyond repair") is not None  # universal parser
        assert isinstance(rp.parse_response('{"only": "leftovers"'), dict)
