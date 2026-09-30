"""Phase 2 (Test-Net Deepening) — long-tail coverage for llm_dispatcher.py.

The existing ``tests/test_llm_dispatcher.py`` covers the happy paths and
delegate wiring; this file targets the UNCOVERED branches (59 missed lines):

  * ``call_ollama`` — the V18.15.6.0 (Fix B) ``error_tracker`` error-type
    classification ladder (timeout / not_found / oom / other)
  * ``_call_ollama_streaming`` — success, the >500-char on_chunk preview
    log, empty-stream fallback, exception fallback
  * ``_call_ollama_nonstreaming`` — requests Timeout (non-retryable,
    V18.2.19), ConnectionError + supervisor.record_failure, empty-response
    retryable raise, and the error_tracker classification ladder
  * ``call_claude`` — the HTTPError handler's 401 / 429 / other-status
    branches (V18.2.21 actionable messages)
  * ``call_via_llm_provider`` — the openai_compat base_url/api_key
    overrides, the llamacpp endpoint overrides, empty-result fallback,
    and the no-inline-fallback None returns
  * ``call_fast_ollama`` — the final failure log + None return

Hermetic: no HTTP — ``safe_ollama_request`` / ``session_for_url`` /
``create_provider`` / ``OllamaProvider`` are patched; ``retries=0`` keeps
the @retry_llm_call decorator at max_attempts=1 (no backoff sleeps).

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_llm_dispatcher.py -q --no-cov``
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests as _requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.retry import OllamaTimeoutError
from core.summarisation import llm_dispatcher
from core.summarisation.llm_dispatcher import (
    _call_ollama_nonstreaming,
    _call_ollama_streaming,
    call_claude,
    call_fast_ollama,
    call_ollama,
    call_via_llm_provider,
)


def _collecting_log():
    calls = []

    def log(msg, level="INFO"):
        calls.append((msg, level))

    return log, calls


def _supervisor():
    sup = MagicMock()
    sup.record_success = MagicMock()
    sup.record_failure = MagicMock()
    return sup


# ── 1. call_ollama: error_tracker classification (V18.15.6.0 Fix B) ────────


class TestCallOllamaErrorTracker:
    def _run(self, exc):
        tracker = []
        log, logs = _collecting_log()
        with (
            patch("core.llm.llm_provider.create_provider", side_effect=exc),
            patch("utils.settings.Settings"),
        ):
            result = call_ollama(
                prompt="p",
                model="test-model",
                temp=0.7,
                max_tokens=64,
                streaming_enabled=False,
                ollama_base_url="http://localhost:11434",
                timeout=60,
                retries=0,
                context_tokens=4096,
                supervisor=_supervisor(),
                log=log,
                error_tracker=tracker,
            )
        assert result is None
        assert len(tracker) == 1
        return tracker[0], logs

    def test_ollama_timeout_error_classified_timeout(self):
        kind, _ = self._run(OllamaTimeoutError(model="test-model", timeout=60))
        assert kind == "timeout"

    def test_404_message_classified_not_found(self):
        kind, _ = self._run(RuntimeError("server returned 404 model not found"))
        assert kind == "not_found"

    def test_oom_message_classified_oom(self):
        kind, _ = self._run(RuntimeError("CUDA out of memory during generation"))
        assert kind == "oom"

    def test_timeout_message_classified_timeout(self):
        kind, _ = self._run(RuntimeError("request timed out after 60s"))
        assert kind == "timeout"

    def test_unknown_error_classified_other(self):
        kind, logs = self._run(RuntimeError("a totally mysterious failure"))
        assert kind == "other"
        assert any("delegation failed" in m for m, _ in logs)


# ── 2. _call_ollama_streaming ──────────────────────────────────────────────


class TestCallOllamaStreaming:
    def _kwargs(self, log, error_tracker=None):
        return dict(
            ollama_base_url="http://localhost:11434",
            timeout=60,
            retries=0,
            context_tokens=4096,
            supervisor=_supervisor(),
            log=log,
            error_tracker=error_tracker,
        )

    def test_streaming_success_returns_result(self):
        log, logs = _collecting_log()

        def _fake_complete_streaming(
            prompt="", temperature=0, max_tokens=0, model="", on_chunk=None
        ):
            if on_chunk:
                # Trigger the >500-char growth preview log (V10.22.0)
                on_chunk("x" * 300)
                on_chunk("x" * 300 + "y" * 300)
            return "streamed summary text"

        with patch("core.llm.llm_provider.OllamaProvider") as provider_cls:
            provider_cls.return_value.complete_streaming.side_effect = _fake_complete_streaming
            result = _call_ollama_streaming("p", "m", 0.7, 64, **self._kwargs(log))
        assert result == "streamed summary text"
        assert any("Streaming complete: 21 chars" in m for m, _ in logs)
        assert any("Streaming: 600 chars" in m for m, lvl in logs if lvl == "DEBUG")

    def test_streaming_empty_result_falls_back_to_nonstreaming(self):
        log, logs = _collecting_log()
        with (
            patch("core.llm.llm_provider.OllamaProvider") as provider_cls,
            patch(
                "core.summarisation.llm_dispatcher._call_ollama_nonstreaming",
                return_value="fallback result",
            ) as fallback,
        ):
            provider_cls.return_value.complete_streaming.return_value = ""
            result = _call_ollama_streaming("p", "m", 0.7, 64, **self._kwargs(log))
        assert result == "fallback result"
        fallback.assert_called_once()
        assert any("Streaming returned empty" in m for m, _ in logs)

    def test_streaming_exception_falls_back_to_nonstreaming(self):
        log, logs = _collecting_log()
        with (
            patch("core.llm.llm_provider.OllamaProvider") as provider_cls,
            patch(
                "core.summarisation.llm_dispatcher._call_ollama_nonstreaming",
                return_value="fallback result",
            ),
        ):
            provider_cls.return_value.complete_streaming.side_effect = RuntimeError("stream broke")
            result = _call_ollama_streaming("p", "m", 0.7, 64, **self._kwargs(log))
        assert result == "fallback result"
        assert any("Streaming failed (stream broke)" in m for m, _ in logs)

    def test_streaming_success_short_result_no_chunk_log(self):
        """A result below the 500-char growth threshold logs no streaming preview."""
        log, logs = _collecting_log()

        def _fake_complete_streaming(
            prompt="", temperature=0, max_tokens=0, model="", on_chunk=None
        ):
            if on_chunk:
                on_chunk("short")  # < 500 chars growth → no preview log
            return "ok"

        with patch("core.llm.llm_provider.OllamaProvider") as provider_cls:
            provider_cls.return_value.complete_streaming.side_effect = _fake_complete_streaming
            result = _call_ollama_streaming("p", "m", 0.7, 64, **self._kwargs(log))
        assert result == "ok"
        assert not any("Streaming:" in m for m, lvl in logs if lvl == "DEBUG")


# ── 3. _call_ollama_nonstreaming (Timeout / ConnectionError / classification) ─


class TestCallOllamaNonstreaming:
    def _kwargs(self, log, error_tracker=None):
        return dict(
            context_tokens=4096,
            timeout=60,
            retries=0,
            ollama_base_url="http://localhost:11434",
            supervisor=_supervisor(),
            log=log,
            error_tracker=error_tracker,
        )

    def test_success_returns_text_and_records_success(self):
        log, _ = _collecting_log()
        sup = _supervisor()
        resp = MagicMock()
        resp.json.return_value = {"response": "  hello world  "}
        with patch.object(llm_dispatcher, "safe_ollama_request", return_value=resp):
            result = _call_ollama_nonstreaming(
                "p", "m", 0.7, 64, **{**self._kwargs(log), "supervisor": sup}
            )
        assert result == "hello world"
        sup.record_success.assert_called_once()
        sup.record_failure.assert_not_called()

    def test_timeout_not_retried_and_tracker_says_timeout(self):
        """V18.2.19: requests.Timeout → OllamaTimeoutError → non-retryable → None."""
        log, logs = _collecting_log()
        tracker = []
        sup = _supervisor()
        with patch.object(
            llm_dispatcher,
            "safe_ollama_request",
            side_effect=_requests.exceptions.Timeout("read timed out"),
        ):
            result = _call_ollama_nonstreaming(
                "p", "test-model", 0.7, 64, **{**self._kwargs(log, tracker), "supervisor": sup}
            )
        assert result is None
        assert tracker == ["timeout"]
        sup.record_failure.assert_called_once()
        assert any("NOT retrying" in m for m, _ in logs)

    def test_connection_error_records_failure_and_classifies(self):
        """ConnectionError → supervisor.record_failure + retryable raise → None."""
        log, logs = _collecting_log()
        tracker = []
        sup = _supervisor()
        with patch.object(
            llm_dispatcher,
            "safe_ollama_request",
            side_effect=_requests.exceptions.ConnectionError("connection refused"),
        ):
            result = _call_ollama_nonstreaming(
                "p", "m", 0.7, 64, **{**self._kwargs(log, tracker), "supervisor": sup}
            )
        assert result is None
        sup.record_failure.assert_called_once()
        assert any("connection error" in m for m, _ in logs)
        # "connection refused" matches no keyword → "other"
        assert tracker == ["other"]

    def test_connection_error_not_found_classification(self):
        log, _ = _collecting_log()
        tracker = []
        with patch.object(
            llm_dispatcher,
            "safe_ollama_request",
            side_effect=_requests.exceptions.ConnectionError("model 'm' not found on server"),
        ):
            result = _call_ollama_nonstreaming("p", "m", 0.7, 64, **self._kwargs(log, tracker))
        assert result is None
        assert tracker == ["not_found"]

    def test_connection_error_oom_classification(self):
        log, _ = _collecting_log()
        tracker = []
        with patch.object(
            llm_dispatcher,
            "safe_ollama_request",
            side_effect=_requests.exceptions.ConnectionError("server reported OOM state"),
        ):
            result = _call_ollama_nonstreaming("p", "m", 0.7, 64, **self._kwargs(log, tracker))
        assert result is None
        assert tracker == ["oom"]

    def test_connection_error_timeout_message_classification(self):
        log, _ = _collecting_log()
        tracker = []
        with patch.object(
            llm_dispatcher,
            "safe_ollama_request",
            side_effect=_requests.exceptions.ConnectionError("worker timed out mid-request"),
        ):
            result = _call_ollama_nonstreaming("p", "m", 0.7, 64, **self._kwargs(log, tracker))
        assert result is None
        assert tracker == ["timeout"]

    def test_empty_response_raises_retryable_connection_error(self):
        """An empty 'response' field → ConnectionError('empty response…') → None."""
        log, _ = _collecting_log()
        tracker = []
        resp = MagicMock()
        resp.json.return_value = {"response": "   "}
        with patch.object(llm_dispatcher, "safe_ollama_request", return_value=resp):
            result = _call_ollama_nonstreaming("p", "m", 0.7, 64, **self._kwargs(log, tracker))
        assert result is None
        assert tracker == ["other"]


# ── 4. call_claude: HTTPError handler (V18.2.21) ──────────────────────────


class TestCallClaudeHTTPError:
    def _run(self, status_code, body=""):
        log, logs = _collecting_log()
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = body

        def _raise_for_status():
            raise _requests.exceptions.HTTPError(f"{status_code} error", response=resp)

        resp.raise_for_status = _raise_for_status
        resp.json.return_value = {"content": []}
        with patch.object(llm_dispatcher, "session_for_url") as sfu:
            sfu.return_value.post.return_value = resp
            result = call_claude(
                prompt="p",
                max_tokens=64,
                temperature=0.7,
                claude_api_key="sk-ant-test",
                claude_model="claude-3-sonnet",
                claude_base_url="https://api.anthropic.com/v1",
                retries=0,
                log=log,
            )
        assert result is None
        return logs

    def test_401_invalid_api_key_message(self):
        logs = self._run(401)
        assert any("API key invalid or expired" in m for m, lvl in logs if lvl == "ERROR")

    def test_429_rate_limited_message(self):
        logs = self._run(429)
        assert any("rate limited" in m for m, lvl in logs if lvl == "WARNING")

    def test_other_status_logs_body(self):
        logs = self._run(500, body="internal server error")
        assert any("Claude HTTP 500" in m and "internal server error" in m for m, _ in logs)

    def test_other_status_body_read_failure_uses_empty_body(self):
        """A response whose .text raises → the except falls back to an empty body."""
        log, logs = _collecting_log()

        class _TextRaises:
            status_code = 502

            @property
            def text(self):
                raise RuntimeError("stream closed")

        resp = _TextRaises()

        def _raise_for_status():
            raise _requests.exceptions.HTTPError("502 error", response=resp)

        resp.raise_for_status = _raise_for_status  # type: ignore[method-assign]
        with patch.object(llm_dispatcher, "session_for_url") as sfu:
            sfu.return_value.post.return_value = resp
            result = call_claude(
                prompt="p",
                max_tokens=64,
                temperature=0.7,
                claude_api_key="sk-ant-test",
                claude_model="claude-3-sonnet",
                claude_base_url="https://api.anthropic.com/v1",
                retries=0,
                log=log,
            )
        assert result is None
        # The WARNING still fires, with an empty body (no crash)
        assert any("Claude HTTP 502" in m for m, lvl in logs if lvl == "WARNING")


# ── 5. call_via_llm_provider: overrides + fallbacks ────────────────────────


class TestCallViaLlmProviderOverrides:
    def _base_kwargs(self, log):
        return dict(
            timeout=600,
            supervisor=_supervisor(),
            log=log,
        )

    def test_openai_compat_base_url_and_api_key_overrides(self):
        log, logs = _collecting_log()
        provider = MagicMock()
        provider.complete.return_value = "compat response"
        with (
            patch("core.llm.llm_provider.create_provider", return_value=provider),
            patch("utils.settings.Settings"),
        ):
            result = call_via_llm_provider(
                provider_type="openai_compat",
                prompt="p",
                model="gpt-x",
                base_url="http://localhost:8000/v1",
                api_key="sk-test-123",
                temp=0.7,
                max_tokens=64,
                **self._base_kwargs(log),
            )
        assert result == "compat response"
        # V0.6.8 (review-loop follow-up, contract evolution): the overrides
        # target the PUBLIC attrs now — the old _base_url/_api_key spellings
        # were no-ops on the REAL OpenAICompatProvider (MagicMock made the
        # dead assignment look alive here); see tests/test_v068_review_loop_fixes.py
        # TestLoop3LlmDispatcherSweep.
        assert provider.base_url == "http://localhost:8000/v1"
        assert provider.api_key == "sk-test-123"
        assert any("via llm_provider.openai_compat" in m for m, _ in logs)

    def test_llamacpp_endpoint_overrides(self):
        log, _ = _collecting_log()
        provider = MagicMock()
        provider.complete.return_value = "llamacpp response"
        with (
            patch("core.llm.llm_provider.create_provider", return_value=provider),
            patch("utils.settings.Settings"),
        ):
            result = call_via_llm_provider(
                provider_type="llamacpp",
                prompt="p",
                model="local-model",
                base_url="http://localhost:8080/",
                api_key="llamacpp-key",
                temp=0.7,
                max_tokens=64,
                **self._base_kwargs(log),
            )
        assert result == "llamacpp response"
        # V0.04: the trailing slash is stripped for llamacpp; the api_key
        # override goes through the REAL attribute name (base_url/api_key).
        assert provider.base_url == "http://localhost:8080"
        assert provider.api_key == "llamacpp-key"

    def test_whitespace_result_falls_back_to_inline(self):
        """A whitespace-only provider result → WARNING + inline fallback call."""
        log, logs = _collecting_log()
        provider = MagicMock()
        provider.complete.return_value = "   "
        fallback_calls = []

        def _compat_fallback(prompt, **kw):
            fallback_calls.append(prompt)
            return "inline fallback result"

        with (
            patch("core.llm.llm_provider.create_provider", return_value=provider),
            patch("utils.settings.Settings"),
        ):
            result = call_via_llm_provider(
                provider_type="openai_compat",
                prompt="p",
                model="m",
                base_url="http://x/v1",
                api_key="k",
                temp=0.7,
                max_tokens=64,
                call_openai_compat_fn=_compat_fallback,
                **self._base_kwargs(log),
            )
        assert result == "inline fallback result"
        assert fallback_calls == ["p"]
        assert any("returned empty" in m for m, _ in logs)

    def test_claude_provider_failure_without_fallback_returns_none(self):
        log, logs = _collecting_log()
        with (
            patch("core.llm.llm_provider.create_provider", side_effect=RuntimeError("fail")),
            patch("utils.settings.Settings"),
        ):
            result = call_via_llm_provider(
                provider_type="claude",
                prompt="p",
                model="claude-3",
                base_url="",
                api_key="",
                temp=0.7,
                max_tokens=64,
                call_claude_fn=None,
                **self._base_kwargs(log),
            )
        assert result is None
        assert any("falling back to inline" in m for m, _ in logs)

    def test_openai_compat_provider_failure_without_fallback_returns_none(self):
        log, _ = _collecting_log()
        with (
            patch("core.llm.llm_provider.create_provider", side_effect=RuntimeError("fail")),
            patch("utils.settings.Settings"),
        ):
            result = call_via_llm_provider(
                provider_type="openai_compat",
                prompt="p",
                model="m",
                base_url="http://x/v1",
                api_key="k",
                temp=0.7,
                max_tokens=64,
                call_openai_compat_fn=None,
                **self._base_kwargs(log),
            )
        assert result is None


# ── 6. call_fast_ollama: failure path ─────────────────────────────────────


class TestCallFastOllamaFailure:
    def test_exception_logs_and_returns_none(self):
        log, logs = _collecting_log()
        with patch.object(
            llm_dispatcher, "safe_ollama_request", side_effect=ValueError("bad payload")
        ):
            result = call_fast_ollama(
                prompt="p",
                model="fast-model",
                temp=0.7,
                max_tokens=64,
                ollama_base_url="http://localhost:11434",
                fast_model_context=8192,
                log=log,
            )
        assert result is None
        assert any("Fast model call failed: bad payload" in m for m, _ in logs)

    def test_success_returns_text(self):
        log, _ = _collecting_log()
        resp = MagicMock()
        resp.json.return_value = {"response": "quick summary"}
        with patch.object(llm_dispatcher, "safe_ollama_request", return_value=resp):
            result = call_fast_ollama(
                prompt="p",
                model="fast-model",
                temp=0.7,
                max_tokens=64,
                ollama_base_url="http://localhost:11434",
                fast_model_context=8192,
                log=log,
            )
        assert result == "quick summary"


# ── 7. Streaming call routes through call_ollama with error tracker ────────


class TestNoopLog:
    def test_default_noop_log_is_callable(self):
        """The module default log callback (used when log=None) is inert."""
        assert llm_dispatcher._noop_log("anything", "WARNING") is None


class TestStreamingRoute:
    def test_call_ollama_streaming_passes_error_tracker(self):
        """call_ollama(streaming_enabled=True) forwards the error_tracker."""
        tracker = []
        log, _ = _collecting_log()
        with patch(
            "core.summarisation.llm_dispatcher._call_ollama_streaming", return_value="ok"
        ) as streaming:
            result = call_ollama(
                prompt="p",
                model="m",
                temp=0.7,
                max_tokens=64,
                streaming_enabled=True,
                ollama_base_url="http://localhost:11434",
                timeout=60,
                retries=0,
                context_tokens=4096,
                supervisor=_supervisor(),
                log=log,
                error_tracker=tracker,
            )
        assert result == "ok"
        # The tracker is forwarded as a keyword argument
        assert streaming.call_args.kwargs.get("error_tracker") is tracker
