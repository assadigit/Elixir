"""Phase 2 (Test-Net Deepening) — ``core/llm/llamacpp_provider.py`` push.

Baseline: 45/244 statements missed (82%).

Hermetic: the provider's HTTP goes through the module-local
``_no_proxy_session()`` helper — every test patches it to return a fake
session, so no socket is ever opened (unlike tests/test_v004_llamacpp.py,
which uses the localhost mock server; here we target the REMAINING error
branches the happy-path mock server can't reach).
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import core.llm.llamacpp_provider as lp  # noqa: E402
from core.llm.llamacpp_provider import LlamaCppProvider  # noqa: E402


def _resp(status: int = 200, payload: dict | None = None, text: str = "") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    if payload is not None:
        r._content = json.dumps(payload).encode()
        r.headers["Content-Type"] = "application/json"
    else:
        r._content = text.encode()
    r.encoding = "utf-8"
    # A hand-built Response has raw=None; the ``with resp:`` context manager
    # in _chat_streaming calls resp.close() → raw.close(). Give it a stub.
    r.raw = types.SimpleNamespace(close=lambda: None)  # type: ignore[assignment]
    r._content_consumed = True  # type: ignore[attr-defined]
    return r


def _iter_lines(self, decode_unicode=False, **kwargs):
    # NOTE: blank lines are deliberately KEPT — the provider's SSE loop must
    # skip them itself (line 311's ``if not raw_line: continue``).
    yield from self._content.decode("utf-8").splitlines()


@pytest.fixture(autouse=True)
def _patched_iter_lines(monkeypatch):
    """Patch ``requests.Response.iter_lines`` ONLY for the tests in this module.

    A raw module-level assignment (``requests.Response.iter_lines = _iter_lines``)
    leaked into every LATER test in the session: test_v004_llamacpp.py and
    test_v005_rig_audit_fixes.py drive the REAL requests stack against the
    localhost mock server, and for a genuinely streamed response
    ``Response._content`` is still the ``False`` sentinel (content is never
    consumed), so the fake crashed with ``'bool' object has no attribute
    'decode'`` / broke SSE parsing. The monkeypatch fixture restores the real
    method after every test (the conftest.py / test_group_b_characterization.py
    snapshot-restore discipline).
    """
    monkeypatch.setattr(requests.Response, "iter_lines", _iter_lines)


class _FakeSession:
    """A requests.Session stand-in with scripted responses / exceptions."""

    def __init__(self, responses=None, exc=None) -> None:
        self._responses = list(responses or [])
        self._exc = exc
        self.requests: list[dict] = []
        self.closed = False

    def _next(self):
        if self._exc is not None:
            raise self._exc
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]

    def post(self, url, headers=None, json=None, timeout=None, stream=False):
        self.requests.append({"method": "POST", "url": url, "json": json, "stream": stream})
        return self._next()

    def get(self, url, headers=None, timeout=None):
        self.requests.append({"method": "GET", "url": url})
        return self._next()

    def close(self):
        self.closed = True


def _use_session(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> _FakeSession:
    monkeypatch.setattr(lp, "_no_proxy_session", lambda: session)
    return session


def _sse(*chunks: str, done: bool = True) -> _FakeSession:
    # SSE events are separated by BLANK lines — the provider's loop must skip
    # them (the ``if not raw_line: continue`` branch).
    lines = []
    for c in chunks:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": c}}]}))
        lines.append("")  # SSE event separator
    if done:
        lines.append("data: [DONE]")
    return _FakeSession([_resp(200, text="\n".join(lines))])


def _provider(**overrides) -> LlamaCppProvider:
    kwargs = dict(
        model="test-model",
        base_url="http://127.0.0.1:8080/v1",
        api_key="local",
        timeout=30,
        retries=0,
        log_callback=lambda msg, level="INFO": None,
    )
    kwargs.update(overrides)
    return LlamaCppProvider(**kwargs)


# ── _pin_utf8 / _extract_error_message ──────────────────────────────────────


class TestHelpers:
    def test_pin_utf8_sets_encoding(self):
        r = _resp(200, {"a": 1})
        lp._pin_utf8(r)
        assert r.encoding == "utf-8"

    def test_pin_utf8_readonly_response_swallowed(self):
        class _ReadOnly:
            encoding = property(lambda self: "x")  # writing raises

            @encoding.setter
            def encoding(self, v):
                raise AttributeError("read-only")

        assert lp._pin_utf8(_ReadOnly()) is not None  # must not raise

    def test_extract_error_dict(self):
        r = _resp(
            400,
            {"error": {"code": 400, "message": "exceeds context", "type": "invalid_request_error"}},
        )
        msg = lp._extract_error_message(r)
        assert "HTTP 400" in msg
        assert "exceeds context" in msg
        assert "invalid_request_error" in msg

    def test_extract_error_dict_no_message(self):
        r = _resp(418, {"error": {"code": 418}})
        assert lp._extract_error_message(r) == "HTTP 418"

    def test_extract_error_string(self):
        r = _resp(401, {"error": "unauthorized"})
        assert lp._extract_error_message(r) == "HTTP 401: unauthorized"

    def test_extract_error_plain_text_body(self):
        r = _resp(500, text="internal panic")
        assert lp._extract_error_message(r) == "HTTP 500: internal panic"

    def test_extract_error_empty_body(self):
        r = _resp(502, text="")
        assert lp._extract_error_message(r) == "HTTP 502"

    def test_extract_error_garbage_json(self):
        r = _resp(200)
        r._content = b"{not json"
        assert lp._extract_error_message(r).startswith("HTTP 200")


# ── _parse_sse_line ─────────────────────────────────────────────────────────


class TestParseSseLine:
    def test_ignores_non_data_lines(self):
        assert _provider()._parse_sse_line(": keep-alive", []) is None

    def test_ignores_empty_data(self):
        assert _provider()._parse_sse_line("data:", []) is None
        assert _provider()._parse_sse_line("data:    ", []) is None

    def test_done_returns_accumulated(self):
        chunks = ["a", "b"]
        assert _provider()._parse_sse_line("data: [DONE]", chunks) == "ab"

    def test_content_delta_appended(self):
        chunks: list[str] = []
        line = "data: " + json.dumps({"choices": [{"delta": {"content": "hi"}}]})
        assert _provider()._parse_sse_line(line, chunks) is None
        assert chunks == ["hi"]

    def test_malformed_json_ignored(self):
        assert _provider()._parse_sse_line("data: {broken", []) is None

    def test_midstream_error_dict_raises(self):
        line = "data: " + json.dumps({"error": {"message": "ctx overflow"}})
        with pytest.raises(requests.exceptions.ConnectionError, match="ctx overflow"):
            _provider()._parse_sse_line(line, [])

    def test_midstream_error_string_raises(self):
        line = "data: " + json.dumps({"error": "server melting"})
        with pytest.raises(requests.exceptions.ConnectionError, match="server melting"):
            _provider()._parse_sse_line(line, [])

    def test_no_choices_key(self):
        assert _provider()._parse_sse_line('data: {"other": 1}', []) is None


# ── _chat_streaming edge branches ──────────────────────────────────────────


class TestChatStreamingEdges:
    def test_non_200_raises_http_error(self, monkeypatch):
        sess = _use_session(
            monkeypatch, _FakeSession([_resp(404, {"error": {"code": 404, "message": "no model"}})])
        )
        p = _provider()
        with pytest.raises(requests.exceptions.HTTPError):
            p._chat_streaming({"model": "m"}, None)
        assert sess.closed

    def test_stream_without_done_returns_accumulated(self, monkeypatch):
        _use_session(monkeypatch, _sse("partial", done=False))
        p = _provider()
        assert p._chat_streaming({"model": "m"}, None) == "partial"

    def test_stream_closed_without_content_raises(self, monkeypatch):
        sess = _use_session(monkeypatch, _FakeSession([_resp(200, text="data: \n")] * 2))
        p = _provider()
        with pytest.raises(requests.exceptions.ConnectionError, match="without content"):
            p._chat_streaming({"model": "m"}, None)
        assert sess.closed

    def test_on_chunk_callback_exception_swallowed(self, monkeypatch):
        # A chunk line + a [DONE] — with a raising on_chunk the call still
        # returns (the UI callback must never kill generation).
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "x"}}]}),
            "data: [DONE]",
        ]
        _use_session(monkeypatch, _FakeSession([_resp(200, text="\n".join(lines))]))

        def bad_cb(text):
            raise RuntimeError("UI exploded")

        p = _provider()
        assert p._chat_streaming({"model": "m"}, bad_cb) == "x"


# ── _chat_nonstreaming ──────────────────────────────────────────────────────


class TestChatNonStreaming:
    def test_success(self, monkeypatch):
        sess = _use_session(
            monkeypatch,
            _FakeSession([_resp(200, {"choices": [{"message": {"content": " full answer "}}]})]),
        )
        p = _provider()
        assert p._chat_nonstreaming({"model": "m", "max_tokens": 100}) == "full answer"
        (req,) = sess.requests
        assert req["json"]["stream"] is False

    def test_non_200_raises_http_error(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(500, {"error": {"message": "boom"}})]))
        p = _provider()
        with pytest.raises(requests.exceptions.HTTPError, match="boom"):
            p._chat_nonstreaming({"model": "m"})

    def test_empty_content_raises_connection_error(self, monkeypatch):
        _use_session(
            monkeypatch, _FakeSession([_resp(200, {"choices": [{"message": {"content": "  "}}]})])
        )
        p = _provider()
        with pytest.raises(requests.exceptions.ConnectionError, match="empty response"):
            p._chat_nonstreaming({"model": "m"})


# ── complete() error routing ────────────────────────────────────────────────


class TestCompleteErrorRouting:
    def test_streaming_transport_error_falls_back_nonstreaming(self, monkeypatch):
        # First POST (streaming) dies with ConnectionError; the fallback
        # non-streaming POST succeeds.
        sess = _FakeSession(
            [
                requests.exceptions.ConnectionError("proxy mangled SSE"),  # streaming
                _resp(200, {"choices": [{"message": {"content": "fallback ok"}}]}),  # non-stream
            ]
        )

        def post(url, headers=None, json=None, timeout=None, stream=False):
            sess.requests.append({"method": "POST", "url": url, "stream": stream})
            item = sess._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        sess.post = post  # type: ignore[method-assign]
        _use_session(monkeypatch, sess)
        p = _provider()
        assert p.complete("prompt") == "fallback ok"

    def test_context_400_logged_then_none(self, monkeypatch):
        sess = _FakeSession(
            [
                _resp(
                    400,
                    {
                        "error": {
                            "code": 400,
                            "message": "the request exceeds the available context size",
                        }
                    },
                )
            ]
            * 2
        )
        _use_session(monkeypatch, sess)
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.complete("prompt") is None
        assert any("exceeds the server's context" in m for (_, m) in logs)

    def test_all_attempts_fail_returns_none(self, monkeypatch):
        _use_session(
            monkeypatch,
            _FakeSession(exc=requests.exceptions.ConnectionError("down")),
        )
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.complete("prompt") is None
        assert any("call failed" in m for (_, m) in logs)


# ── complete_streaming ──────────────────────────────────────────────────────


class TestCompleteStreaming:
    def test_success_with_callback(self, monkeypatch):
        _use_session(monkeypatch, _sse("streamed "))
        seen: list[str] = []
        p = _provider()
        assert p.complete_streaming("prompt", on_chunk=seen.append) == "streamed "

    def test_streaming_failure_falls_back_to_nonstreaming(self, monkeypatch):
        sess = _FakeSession(
            [
                _resp(500, {"error": {"message": "SSE broken"}}),
                _resp(200, {"choices": [{"message": {"content": "ns-ok"}}]}),
            ]
        )
        _use_session(monkeypatch, sess)
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.complete_streaming("prompt") == "ns-ok"
        assert any("non-streaming retry" in m for (_, m) in logs)

    def test_both_paths_fail_returns_none(self, monkeypatch):
        sess = _FakeSession(
            [
                _resp(500, {"error": {"message": "SSE broken"}}),
                _resp(500, {"error": {"message": "still broken"}}),
            ]
        )
        _use_session(monkeypatch, sess)
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.complete_streaming("prompt") is None
        assert any("call failed" in m for (_, m) in logs)


# ── smoke_test ──────────────────────────────────────────────────────────────


class TestSmokeTest:
    def test_success(self, monkeypatch):
        _use_session(monkeypatch, _sse("hi"))
        p = _provider()
        assert p.smoke_test() is True

    def test_auth_rejected_401(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(401, {"error": {"message": "bad key"}})]))
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("auth rejected" in m for (_, m) in logs)

    def test_auth_rejected_403(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(403, {"error": {"message": "forbidden"}})]))
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("auth rejected" in m for (_, m) in logs)

    def test_model_mismatch_404(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(404, {"error": {"message": "not served"}})]))
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("not served by this server" in m for (_, m) in logs)

    def test_other_http_error(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(503, {"error": {"message": "overloaded"}})]))
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("smoke-test FAILED" in m for (_, m) in logs)

    def test_connection_error(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession(exc=requests.exceptions.ConnectionError("refused")))
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("cannot reach llama.cpp" in m for (_, m) in logs)

    def test_unexpected_exception(self, monkeypatch):
        sess = _FakeSession(exc=ValueError("surprise"))
        _use_session(monkeypatch, sess)
        logs: list[tuple[str, str]] = []
        p = _provider(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
        assert p.smoke_test() is False
        assert any("ValueError" in m for (_, m) in logs)

    def test_explicit_timeout_forwarded(self, monkeypatch):
        sess = _use_session(monkeypatch, _sse("hi"))
        p = _provider()
        p.smoke_test(timeout=9)
        assert sess.requests[0]["json"]["max_tokens"] == 1


# ── list_llamacpp_models / list_models ──────────────────────────────────────


class TestListModels:
    def test_success(self, monkeypatch):
        sess = _use_session(
            monkeypatch, _FakeSession([_resp(200, {"data": [{"id": "m1"}, {"id": ""}, {"x": 1}]})])
        )
        assert lp.list_llamacpp_models() == ["m1"]
        (req,) = sess.requests
        assert req["url"].endswith("/models")

    def test_non_200_returns_empty(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(401, {"error": "nope"})]))
        assert lp.list_llamacpp_models() == []

    def test_exception_returns_empty(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession(exc=requests.exceptions.ConnectionError("down")))
        assert lp.list_llamacpp_models() == []

    def test_provider_list_models(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession([_resp(200, {"data": [{"id": "served"}]})]))
        assert _provider().list_models() == ["served"]


# ── test_llamacpp_connection (wizard probe) ─────────────────────────────────


class TestTestLlamaCppConnection:
    def test_success_with_served_model(self, monkeypatch):
        sess = _FakeSession(
            [
                _resp(200, {"data": [{"id": "served-model"}]}),  # GET /models
                None,  # unused
            ]
        )
        # The stage-2 smoke test goes through _chat_streaming on the SAME
        # session: give it an SSE response next.
        sess._responses[1] = _resp(
            200,
            text="data: "
            + json.dumps({"choices": [{"delta": {"content": "x"}}]})
            + "\ndata: [DONE]",
        )
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection(model="served-model")
        assert ok is True
        assert "responded" in msg

    def test_auth_rejected(self, monkeypatch):
        sess = _FakeSession([_resp(401, {}), _resp(401, {})])
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection()
        assert ok is False
        assert "rejected the API key" in msg

    def test_models_endpoint_missing_404(self, monkeypatch):
        sess = _FakeSession([_resp(404, {}), _resp(404, {})])
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection()
        assert ok is False
        assert "is this llama-server" in msg

    def test_server_up_no_models(self, monkeypatch):
        sess = _FakeSession([_resp(200, {"data": []}), _resp(200, {"data": []})])
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection()
        assert ok is False
        assert "returned no models" in msg

    def test_server_down_connection_error(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession(exc=requests.exceptions.ConnectionError("refused")))
        ok, msg = lp.test_llamacpp_connection()
        assert ok is False
        assert "is llama-server running" in msg

    def test_server_down_other_error(self, monkeypatch):
        _use_session(monkeypatch, _FakeSession(exc=TimeoutError("t")))
        ok, msg = lp.test_llamacpp_connection()
        assert ok is False
        assert "connection failed" in msg

    def test_model_probe_failure_reports_detail(self, monkeypatch):
        # Stage 1 finds a model; stage 2's smoke test fails (404 model mismatch).
        sess = _FakeSession(
            [
                _resp(200, {"data": [{"id": "served-model"}]}),
                _resp(404, {"error": {"code": 404, "message": "model not found"}}),
            ]
        )
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection(model="other-model")
        assert ok is False
        assert "failed to respond" in msg

    def test_empty_base_url_uses_default(self, monkeypatch):
        sess = _FakeSession(
            [
                _resp(200, {"data": [{"id": "m"}]}),  # stage 1 model list
                _resp(
                    200,
                    text="data: "
                    + json.dumps({"choices": [{"delta": {"content": "x"}}]})
                    + "\ndata: [DONE]",
                ),
            ]
        )
        _use_session(monkeypatch, sess)
        ok, msg = lp.test_llamacpp_connection(base_url="")
        assert ok is True, msg


# ── fit_max_tokens (budget math, no HTTP) ───────────────────────────────────


class TestFitMaxTokens:
    def test_cap_applied_with_floor(self):
        """A cap of 100 with a 500-token request: the sanity floor (256)
        protects REDUCED requests, so the result is 256, not 100."""
        p = _provider(output_cap=100)
        assert p.fit_max_tokens(500, "short prompt") == 256

    def test_cap_reason_logged(self):
        """The 'model output cap' clamp reason is reported (cap above the
        256 floor so the floor doesn't mask it)."""
        p = _provider(output_cap=300)
        logs: list[tuple[str, str]] = []
        p.log = lambda msg, level="INFO": logs.append((level, msg))
        fitted = p.fit_max_tokens(500, "short prompt")
        assert fitted == 300
        assert any("model output cap 300" in m for (_, m) in logs)

    def test_context_fit_reason_logged(self):
        p = _provider(context_tokens=4096)
        logs: list[tuple[str, str]] = []
        p.log = lambda msg, level="INFO": logs.append((level, msg))
        fitted = p.fit_max_tokens(4000, "x" * 4000)
        assert fitted < 4000
        assert any("context fit" in m for (_, m) in logs)

    def test_cap_applied_below_floor_untouched(self):
        """A deliberately small request (100 < the 256 floor) is never
        inflated OR floored — the cap wins as-is."""
        p = _provider(output_cap=100)
        assert p.fit_max_tokens(100, "short prompt") == 100

    def test_context_fit_applied(self):
        p = _provider(context_tokens=4096)
        fitted = p.fit_max_tokens(4000, "x" * 4000)
        assert fitted < 4000

    def test_tiny_request_not_inflated(self):
        p = _provider(output_cap=12288)
        assert p.fit_max_tokens(3, "short") == 3

    def test_sanity_floor_for_huge_prompt(self):
        """A huge prompt squeezes the ctx budget below the usable floor —
        the 256 floor kicks in (tiktoken compresses the repeated x's, so the
        exact budget is BPE-dependent; assert the floor, not the raw budget)."""
        p = _provider(context_tokens=2048)
        fitted = p.fit_max_tokens(1000, "x" * 20000)
        assert fitted == 256  # LLAMACPP_MIN_OUTPUT_TOKENS floor


class TestNoProxySessionHelper:
    def test_no_proxy_session_config(self):
        s = lp._no_proxy_session()
        try:
            assert s.trust_env is False
            assert s.proxies == {"http": "", "https": ""}
        finally:
            s.close()


class TestJsonModePayload:
    def test_json_mode_sets_response_format(self, monkeypatch):
        captured: list[dict] = []

        class _CapSession(_FakeSession):
            def post(self, url, headers=None, json=None, timeout=None, stream=False):
                captured.append({"url": url, "json": json, "stream": stream})
                return _sse("json")._next()

        _use_session(monkeypatch, _CapSession())
        p = _provider()
        assert p.complete("prompt", json_mode=True) == "json"
        assert captured[0]["json"]["response_format"] == {"type": "json_object"}
