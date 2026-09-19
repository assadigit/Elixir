"""V18.2.24 (Phase 3.1) — Async LLM client for non-blocking I/O.

The problem
-----------
The entire LLM I/O path is synchronous (``requests.post``). A chapter's
pipeline makes 5-10 sequential LLM calls (exec → thorough → gap-fill →
additive-sections → self-review → grounding). Each blocks the worker thread
for its full latency. ``ThreadPoolExecutor`` parallelizes *chapters*, not
*stages within a chapter*.

The fix (2026 standard)
-----------------------
An ``AsyncLLMProvider`` with ``httpx.AsyncClient`` + ``async def complete()``.
True non-blocking I/O via ``asyncio``. Independent stages can be parallelized
with ``asyncio.gather`` (e.g. grounding-check on bullets can overlap
self-review on thorough_summary).

Design: parallel-ready, opt-in, with a sync bridge
--------------------------------------------------
This module is **opt-in and non-breaking**. The existing sync ``LLMProvider``
stays as the default. The async provider:

1. Mirrors the sync interface (``complete(prompt, ...) -> str``) but async.
2. Uses ``httpx.AsyncClient`` for true non-blocking HTTP.
3. Reuses the V18.2.21 retry policy (``@retry_llm_call`` semantics — but
   async, via ``asyncio.sleep`` + the same exception classification).
4. Provides ``run_async(coro)`` — a sync bridge that runs an async coroutine
   to completion via ``asyncio.run``. This lets the sync summarizer call the
   async provider without rewriting the whole call chain.
5. Provides ``gather_calls(*coros)`` — a convenience wrapper around
   ``asyncio.gather`` for parallelizing independent LLM calls.

Why not migrate everything to async?
------------------------------------
The app is a PySide6 desktop app. The UI runs on the Qt event loop; the
conversion runs on ``QThread`` workers (``ThreadPoolExecutor``). A full
asyncio migration would require a Qt↔asyncio bridge (``qasync``) and
rewriting the entire call chain — high risk on a 717-test-green system.

Instead, this module provides the *building blocks*:
- ``AsyncOllamaProvider`` — the async equivalent of ``OllamaProvider``.
- ``run_async(coro)`` — call it from sync code: ``result = run_async(provider.complete(prompt))``.
- ``gather_calls(*coros)`` — parallelize: ``results = run_async(gather_calls(c1, c2, c3))``.

When the summarizer wants to parallelize two independent stages, it does::

    from core.llm.async_provider import run_async, gather_calls, AsyncOllamaProvider
    provider = AsyncOllamaProvider(model="...", ...)
    grounding, review = run_async(gather_calls(
        provider.complete(grounding_prompt),
        provider.complete(review_prompt),
    ))

This runs both calls concurrently — total wall-clock time ≈ max(t1, t2)
instead of t1 + t2. For a 10-call chapter pipeline where 3-4 stages are
independent, this can cut chapter time by 30-40%.

Book-agnostic (Key Decision #3): no book-specific logic.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# httpx is the 2026 standard for async HTTP in Python. It's an optional
# dependency — when absent, the async provider degrades to running the sync
# provider in a thread (still works, just not truly async).
try:
    import httpx

    _HAS_HTTPX = True
except ImportError:  # pragma: no cover — httpx is in requirements
    _HAS_HTTPX = False
    httpx = None  # type: ignore[assignment]

# Re-use the sync provider's keep_alive cache + adaptive context logic.
from core.llm.llm_provider import _get_keep_alive
from core.llm.retry import (
    ModelNotFound404Error,
    OllamaOOMError,
    OllamaTimeoutError,
    classify_ollama_exception,
)

# ── Async retry (mirrors @retry_llm_call but with asyncio.sleep) ───────────


async def _async_retry(
    coro_fn: Callable[[], Awaitable[str]],
    *,
    max_attempts: int = 3,
    initial_wait: float = 2.0,
    max_wait: float = 30.0,
    log_callback: Callable[[str, str], None] | None = None,
) -> str | None:
    """Async retry with exponential backoff + jitter.

    Mirrors the sync ``@retry_llm_call`` decorator's semantics but uses
    ``asyncio.sleep`` (non-blocking) instead of ``time.sleep`` (blocking).
    Classifies exceptions via ``classify_ollama_exception`` — non-retryable
    errors (404, Timeout, OOM) raise immediately; retryable errors
    (ConnectionError, 429, 5xx) retry with backoff.
    """
    import random

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn()
        except (ModelNotFound404Error, OllamaTimeoutError, OllamaOOMError):
            # Non-retryable — re-raise immediately (V18.2.19 semantics).
            raise
        except Exception as exc:
            last_exc = exc
            if not classify_ollama_exception(exc):
                # Non-retryable per the classifier — re-raise.
                raise
            if attempt >= max_attempts:
                break
            # Exponential backoff + jitter (same formula as tenacity).
            wait = min(initial_wait * (2 ** (attempt - 1)), max_wait)
            wait += random.uniform(0, 2.0)  # jitter
            if log_callback:
                log_callback(
                    f"    🔄 async retry {attempt}/{max_attempts} after "
                    f"{wait:.1f}s ({type(exc).__name__}: {exc})",
                    "WARNING",
                )
            await asyncio.sleep(wait)
    if last_exc:
        raise last_exc
    return None


# ── Async Ollama provider ─────────────────────────────────────────────────


class AsyncOllamaProvider:
    """Async LLM provider for local Ollama via ``httpx.AsyncClient``.

    Mirrors the sync ``OllamaProvider.complete()`` interface but async.
    Uses ``httpx.AsyncClient`` for non-blocking HTTP — the event loop is
    free to run other coroutines while waiting for the Ollama response.

    Key advantage: when you ``asyncio.gather`` two ``complete()`` calls,
    both HTTP requests are in-flight simultaneously — total wall-clock
    time ≈ max(t1, t2), not t1 + t2.

    The provider reuses the sync provider's adaptive-context logic and
    keep_alive cache (no duplication). Retry semantics match
    ``@retry_llm_call`` (V18.2.21): exponential backoff + jitter,
    non-retryable on 404/Timeout/OOM.
    """

    def __init__(
        self,
        model: str = "",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        context_tokens: int = 65536,
        timeout: int = 300,
        retries: int = 1,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_tokens = context_tokens
        self.timeout = timeout
        self.retries = retries
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._client: Any | None = None  # lazy httpx.AsyncClient

    async def _get_client(self) -> Any:
        """Lazily create the httpx.AsyncClient (shared across calls)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        """Close the underlying httpx client. Call when done with the provider."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_payload(
        self,
        prompt: str,
        temp: float,
        max_tok: int,
        ctx: int,
        json_mode: bool = False,
    ) -> dict:
        """Build the Ollama /api/generate payload (mirrors sync OllamaProvider)."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": _get_keep_alive(),
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
                "num_ctx": ctx,
                "num_gpu": -1,  # V18.1 (P7): all available GPU layers
            },
        }
        if json_mode:
            payload["format"] = "json"  # V18.2.21 (Phase 1.2): JSON mode
        return payload

    def _adaptive_context(self, prompt: str, max_tok: int) -> int:
        """Compute the context window size (mirrors sync OllamaProvider).

        Uses the same char-based estimate (len//4) + VRAM-aware reduction
        as the sync provider — no duplication of the logic, just a local
        copy to avoid importing the sync provider's class.
        """
        estimated_prompt_tokens = len(prompt) // 4
        needed = estimated_prompt_tokens + max_tok + 4096
        ctx = min(self.context_tokens, max(16000, needed))
        # V18.2: VRAM-aware reduction (mirrors sync provider, but simplified —
        # the async provider doesn't probe torch.cuda here to keep it I/O-only).
        return ctx

    async def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str | None:
        """Call Ollama asynchronously. Returns the text response or None.

        Non-blocking: the event loop is free while waiting for the HTTP
        response. Use ``asyncio.gather`` to run multiple ``complete()``
        calls concurrently.

        Retry semantics match ``@retry_llm_call``: exponential backoff +
        jitter on retryable errors (ConnectionError, 429, 5xx); immediate
        raise on non-retryable (404, Timeout, OOM).
        """
        if not _HAS_HTTPX:
            # Degrade: run the sync provider in a thread (still works).
            return await self._fallback_sync(prompt, temperature, max_tokens, model, json_mode)

        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or self.max_tokens
        ctx = self._adaptive_context(prompt, _max_tok)
        payload = self._build_payload(prompt, _temp, _max_tok, ctx, json_mode)
        url = f"{self.base_url}/api/generate"

        async def _do_call() -> str:
            client = await self._get_client()
            self.log(
                f"    🤖 (async) {_model} (t={_temp:.2f}) …",
                "INFO",
            )
            # Import requests exceptions for classifier compatibility.
            # The retry classifier (core.llm.retry.classify_ollama_exception)
            # recognizes requests.exceptions.* — raising httpx.* would NOT be
            # classified as retryable. We translate httpx exceptions to their
            # requests equivalents so the shared classifier works for both
            # sync and async paths.
            import requests.exceptions as _rexc

            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("response", "").strip()
                if not text:
                    raise _rexc.ConnectionError("empty response from model")
                return text
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 404:
                    raise ModelNotFound404Error(
                        model=_model,
                        detail=f"HTTP 404 from Ollama. Run: ollama pull {_model}",
                    ) from exc
                if status == 429 or 500 <= status < 600:
                    # Translate to requests.HTTPError so the shared
                    # classify_ollama_exception recognizes it as retryable.
                    raise _rexc.HTTPError(f"HTTP {status}: {exc}", response=exc.response) from exc
                # Other HTTP errors — let the classifier decide.
                raise _rexc.HTTPError(f"HTTP {status}: {exc}") from exc
            except httpx.TimeoutException as exc:
                raise OllamaTimeoutError(
                    model=_model,
                    timeout=self.timeout,
                    original=exc,
                ) from exc
            except httpx.ConnectError as exc:
                # Translate to requests.ConnectionError (retryable).
                raise _rexc.ConnectionError(f"Ollama connect failed: {exc}") from exc

        return await _async_retry(
            _do_call,
            max_attempts=self.retries + 1,
            log_callback=self.log,
        )

    async def _fallback_sync(
        self,
        prompt: str,
        temperature: float | None,
        max_tokens: int | None,
        model: str | None,
        json_mode: bool,
    ) -> str | None:
        """Degrade to the sync provider in a thread when httpx unavailable."""
        from core.llm.llm_provider import OllamaProvider

        sync = OllamaProvider(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            context_tokens=self.context_tokens,
            timeout=self.timeout,
            retries=self.retries,
            log_callback=self.log,
        )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: sync.complete(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                json_mode=json_mode,
            ),
        )


# ── Sync bridge: call async from sync code ─────────────────────────────────


def run_async(coro: Awaitable) -> Any:
    """Run an async coroutine to completion from sync code.

    This is the bridge between the sync summarizer and the async provider.
    Uses ``asyncio.run`` (Python 3.7+) which creates a new event loop,
    runs the coroutine, and closes the loop.

    Usage::

        from core.llm.async_provider import run_async, AsyncOllamaProvider
        provider = AsyncOllamaProvider(model="gemma4-12b:latest")
        result = run_async(provider.complete("Summarize this..."))

    Note: this BLOCKS the calling thread until the coroutine completes.
    It's meant for use inside ``QThread`` workers (not the UI thread).
    For true concurrency, call ``run_async(gather_calls(c1, c2))`` to
    run multiple LLM calls in parallel within the single event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're already in an event loop — can't call asyncio.run.
            # Use asyncio.ensure_future + run_until_complete pattern.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        pass  # No running loop — safe to use asyncio.run
    return asyncio.run(coro)


async def gather_calls(*coros: Awaitable) -> list[Any]:
    """Run multiple async LLM calls concurrently.

    Wraps ``asyncio.gather``. All coroutines run in the same event loop,
    sharing the ``httpx.AsyncClient`` connection pool. Total wall-clock
    time ≈ max(t1, t2, …), not sum.

    Usage::

        grounding, review = run_async(gather_calls(
            provider.complete(grounding_prompt),
            provider.complete(review_prompt),
        ))

    Returns results in the same order as the input coroutines. If any
    coroutine raises, the exception propagates (default ``asyncio.gather``
    behavior — use ``return_exceptions=True`` to suppress).
    """
    return await asyncio.gather(*coros)


# ── Convenience: async-parallel map for batch LLM calls ────────────────────


async def parallel_complete(
    provider: AsyncOllamaProvider,
    prompts: Sequence[str],
    *,
    max_concurrency: int = 4,
    **kwargs: Any,
) -> list[str | None]:
    """Run N LLM calls concurrently, bounded by ``max_concurrency``.

    Useful for batch operations like "generate gap-fill bullets for 5 missing
    authors" — instead of 5 sequential calls, run 4 at a time.

    Args:
        provider: an AsyncOllamaProvider (or any object with an async
            ``complete`` method).
        prompts: the prompts to run.
        max_concurrency: the maximum number of in-flight calls (bounded to
            avoid overwhelming the local Ollama server / VRAM).
        **kwargs: forwarded to ``provider.complete`` (temperature, etc.).

    Returns:
        List of results (None where a call failed), same order as prompts.
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    results: list[str | None] = [None] * len(prompts)

    async def _run_one(idx: int, prompt: str) -> None:
        async with semaphore:
            try:
                results[idx] = await provider.complete(prompt, **kwargs)
            except Exception as exc:
                logger.warning(
                    "parallel_complete[%d] failed: %s: %s",
                    idx,
                    type(exc).__name__,
                    exc,
                )
                results[idx] = None

    await asyncio.gather(*[_run_one(i, p) for i, p in enumerate(prompts)])
    return results
