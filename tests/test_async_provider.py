"""V18.2.24 (Phase 3.1) — Tests for the async LLM client.

Covers:
1. AsyncOllamaProvider.complete returns text on success
2. complete raises ModelNotFound404Error on HTTP 404 (non-retryable)
3. complete raises OllamaTimeoutError on timeout (non-retryable)
4. complete retries on ConnectionError (retryable)
5. run_async bridge runs a coroutine from sync code
6. gather_calls runs coroutines concurrently (wall-clock < sum)
7. parallel_complete bounds concurrency
8. json_mode injects format=json into payload
9. _adaptive_context mirrors sync provider
10. graceful degradation when httpx absent
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

_project_root = Path(__file__).resolve().parent.parent
import sys

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _make_provider_with_mock_transport(handler):
    """Create an AsyncOllamaProvider with a mocked httpx transport.

    handler: a callable(request: httpx.Request) -> httpx.Response
    """
    import httpx

    from core.llm.async_provider import AsyncOllamaProvider

    provider = AsyncOllamaProvider(
        model="test-model:latest",
        base_url="http://localhost:11434",
        temperature=0.7,
        max_tokens=4096,
        timeout=30,
        retries=2,
    )
    transport = httpx.MockTransport(handler)
    provider._client = httpx.AsyncClient(transport=transport, timeout=30)
    return provider


class TestAsyncCompleteSuccess:
    def test_returns_text_on_success(self):
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"response": "  Hello world  "})

        provider = _make_provider_with_mock_transport(handler)
        result = asyncio.run(provider.complete("test prompt"))
        assert result == "Hello world"

    def test_returns_none_on_empty_response_retries(self):
        """Empty response triggers ConnectionError → retry → exhaust."""
        import httpx
        import requests.exceptions as _rexc

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, json={"response": ""})  # empty

        provider = _make_provider_with_mock_transport(handler)
        # After retries exhausted, raises the last requests.ConnectionError
        with patch("core.llm.async_provider.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(_rexc.ConnectionError):
                asyncio.run(provider.complete("test"))
        assert call_count["n"] == 3  # retried 3 times


class TestNonRetryableErrors:
    def test_404_raises_model_not_found(self):
        import httpx

        from core.llm.retry import ModelNotFound404Error

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model not found"})

        provider = _make_provider_with_mock_transport(handler)
        with pytest.raises(ModelNotFound404Error):
            asyncio.run(provider.complete("test"))

    def test_timeout_raises_ollama_timeout(self):
        import httpx

        from core.llm.retry import OllamaTimeoutError

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("read timeout")

        provider = _make_provider_with_mock_transport(handler)
        with pytest.raises(OllamaTimeoutError):
            asyncio.run(provider.complete("test"))


class TestRetryableErrors:
    def test_connection_error_retries_then_succeeds(self):
        import httpx

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"response": "success after retry"})

        provider = _make_provider_with_mock_transport(handler)
        # Patch the retry sleep to be instant (don't actually wait)
        with patch("core.llm.async_provider.asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(provider.complete("test"))
        assert result == "success after retry"
        assert call_count["n"] == 2  # failed once, succeeded on retry

    def test_429_retries(self):
        import httpx

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(200, json={"response": "ok"})

        provider = _make_provider_with_mock_transport(handler)
        with patch("core.llm.async_provider.asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(provider.complete("test"))
        assert result == "ok"

    def test_500_retries(self):
        import httpx

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(500, json={"error": "server error"})
            return httpx.Response(200, json={"response": "ok"})

        provider = _make_provider_with_mock_transport(handler)
        with patch("core.llm.async_provider.asyncio.sleep", new=AsyncMock()):
            result = asyncio.run(provider.complete("test"))
        assert result == "ok"


class TestRunAsyncBridge:
    def test_runs_coroutine_from_sync(self):
        from core.llm.async_provider import run_async

        async def coro():
            await asyncio.sleep(0.01)
            return 42

        result = run_async(coro())
        assert result == 42

    def test_returns_none_on_none_result(self):
        from core.llm.async_provider import run_async

        async def coro():
            return None

        assert run_async(coro()) is None


class TestGatherCalls:
    def test_runs_concurrently(self):
        """gather_calls should run coroutines concurrently — total time
        should be ~max(t1, t2), not t1 + t2."""
        from core.llm.async_provider import gather_calls, run_async

        async def slow():
            await asyncio.sleep(0.1)
            return "slow"

        async def fast():
            await asyncio.sleep(0.05)
            return "fast"

        start = time.time()
        results = run_async(gather_calls(slow(), fast()))
        elapsed = time.time() - start
        assert results == ["slow", "fast"]
        # If sequential, would be 0.15s. Concurrent should be ~0.1s.
        assert elapsed < 0.15, f"took {elapsed:.3f}s — not concurrent"

    def test_preserves_order(self):
        from core.llm.async_provider import gather_calls, run_async

        async def make(val, delay):
            await asyncio.sleep(delay)
            return val

        results = run_async(
            gather_calls(
                make("a", 0.02),
                make("b", 0.01),
                make("c", 0.03),
            )
        )
        assert results == ["a", "b", "c"]


class TestParallelComplete:
    def test_bounded_concurrency(self):
        """parallel_complete should bound concurrency to max_concurrency."""
        import json as _json

        import httpx

        from core.llm.async_provider import AsyncOllamaProvider, parallel_complete

        in_flight = {"max": 0, "current": 0}

        async def async_handler(request: httpx.Request) -> httpx.Response:
            in_flight["current"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["current"])
            # Small delay so coroutines overlap (observable concurrency)
            await asyncio.sleep(0.02)
            in_flight["current"] -= 1
            body = _json.loads(request.content)
            return httpx.Response(200, json={"response": f"resp to {body['prompt'][:10]}"})

        provider = AsyncOllamaProvider(model="test", timeout=30, retries=0)

        # httpx.MockTransport accepts a sync handler; for async we wrap it.
        # (V0.13: removed an unused placeholder MockTransport)
        class _AsyncTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                return await async_handler(request)

        provider._client = httpx.AsyncClient(transport=_AsyncTransport(), timeout=30)

        prompts = [f"prompt {i}" for i in range(8)]
        results = asyncio.run(parallel_complete(provider, prompts, max_concurrency=3))

        assert len(results) == 8
        assert all(r is not None for r in results)
        # With the 0.02s delay + cap=3, we should see 2-3 in-flight.
        assert in_flight["max"] >= 2, f"max in-flight was {in_flight['max']} (expected >=2)"
        assert in_flight["max"] <= 3, f"max in-flight was {in_flight['max']} (cap=3)"


class TestJsonMode:
    def test_json_mode_injects_format(self):
        import httpx

        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.content)
            captured["format"] = body.get("format")
            captured["model"] = body.get("model")
            return httpx.Response(200, json={"response": '{"key": "val"}'})

        provider = _make_provider_with_mock_transport(handler)
        asyncio.run(provider.complete("test", json_mode=True))
        assert captured["format"] == "json"

    def test_no_json_mode_no_format_key(self):
        import httpx

        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.content)
            captured["format"] = body.get("format")
            return httpx.Response(200, json={"response": "plain text"})

        provider = _make_provider_with_mock_transport(handler)
        asyncio.run(provider.complete("test", json_mode=False))
        assert "format" not in captured or captured["format"] is None


class TestAdaptiveContext:
    def test_short_prompt_uses_minimum(self):
        from core.llm.async_provider import AsyncOllamaProvider

        p = AsyncOllamaProvider(model="m", context_tokens=65536)
        ctx = p._adaptive_context("short", 4096)
        assert ctx == 16000  # minimum

    def test_long_prompt_uses_more(self):
        from core.llm.async_provider import AsyncOllamaProvider

        p = AsyncOllamaProvider(model="m", context_tokens=65536)
        long_prompt = "x" * 120000  # 30k tokens
        ctx = p._adaptive_context(long_prompt, 4096)
        assert ctx > 16000
        assert ctx <= 65536

    def test_capped_at_context_tokens(self):
        from core.llm.async_provider import AsyncOllamaProvider

        p = AsyncOllamaProvider(model="m", context_tokens=32768)
        very_long = "x" * 200000
        ctx = p._adaptive_context(very_long, 4096)
        assert ctx <= 32768


class TestGracefulDegradation:
    def test_fallback_sync_when_httpx_unavailable(self):
        """When httpx is absent, complete() falls back to sync provider in a thread."""

        from core.llm.async_provider import AsyncOllamaProvider

        provider = AsyncOllamaProvider(model="test-model", timeout=5, retries=0)
        # Mock httpx as absent
        with patch("core.llm.async_provider._HAS_HTTPX", False):
            # Mock the sync OllamaProvider.complete
            with patch("core.llm.llm_provider.OllamaProvider.complete", return_value="sync result"):
                result = asyncio.run(provider.complete("test"))
        assert result == "sync result"


# ── Helper: AsyncMock for patching asyncio.sleep ──────────────────────────


class AsyncMock:
    """A mock that returns an awaitable for asyncio.sleep patching."""

    def __call__(self, *args, **kwargs):
        fut = asyncio.Future()
        fut.set_result(None)
        return fut

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
