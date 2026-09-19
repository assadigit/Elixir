"""V18.8 (Phase 5.1, Batch B): LLM dispatcher leaf functions.

Extracted from ``Summarizer`` (god-class decomposition Stage 2). These are
the 6 LEAF HTTP-call methods — the actual provider interactions. The
dispatcher methods (``_call_llm``, ``_call_llm_with_empty_retry``,
``_call_cloud``) STAY in Summarizer because they have 10+ self-deps and
form the call-chain control flow.

**Extraction map** (what moved where):

| Summarizer method (old)              | llm_dispatcher function (new)     | self deps                            |
|--------------------------------------|------------------------------------|--------------------------------------|
| ``_call_ollama``                     | ``call_ollama``                    | streaming, base_url, timeout, retries, ctx_tokens, supervisor, log |
| ``_call_ollama_streaming``           | ``_call_ollama_streaming``         | base_url, timeout, retries, ctx_tokens, supervisor, log |
| ``_call_ollama_nonstreaming``        | ``_call_ollama_nonstreaming``      | ctx_tokens, timeout, retries, base_url, supervisor, log |
| ``_call_openai_compat``              | ``call_openai_compat``             | timeout, retries, provider, log |
| ``_call_claude``                     | ``call_claude``                    | claude_api_key, claude_model, claude_base_url, retries, log |
| ``_call_via_llm_provider``           | ``call_via_llm_provider``          | timeout, supervisor, log + fallback callbacks |

Each function is extracted VERBATIM — the only change is ``self.X`` becomes
a parameter. The Summarizer methods now delegate to these functions.

**NOT extracted** (stay in Summarizer — too many self-deps for the dispatch
control flow):
- ``_call_llm`` — dispatcher with response cache (reads provider, primary_model,
  temperature, academic_rigor, cache_enabled, + all cloud provider config)
- ``_call_llm_with_empty_retry`` — Qwen3 ``/no_think`` injection + retry
  (reads primary_model, calls _call_llm)
- ``_call_cloud`` — fusion dispatcher (reads 7+ fusion_* attrs)

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object
like the failed ``PromptContext``). This matches the proven Phase 4 + Batch A
pattern.

**Phase 5.3**: ``call_fast_ollama`` is also extracted here, migrated from
inline ``for attempt in range(2)`` to ``@retry_llm_call`` decorator.

Characterization tests: ``tests/test_llm_dispatcher.py`` verifies the
delegate wiring and that the functions accept the expected params.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import requests as _requests

from core.llm.retry import retry_llm_call
from utils.network import extract_openai_content, safe_ollama_request, session_for_url

logger = logging.getLogger(__name__)

# Type aliases (duck-typed).
SupervisorLike = Any
LogCallback = Callable[[str, str], None]


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── call_ollama (extracted verbatim from Summarizer._call_ollama) ──────────


def call_ollama(
    prompt: str,
    model: str,
    temp: float,
    max_tokens: int,
    *,
    streaming_enabled: bool,
    ollama_base_url: str,
    timeout: int,
    retries: int,
    context_tokens: int,
    supervisor: SupervisorLike,
    log: LogCallback | None = None,
    error_tracker: list | None = None,  # V18.15.6.0 (Fix B)
) -> str | None:
    """V10.32.0 (Sprint 4 s2): Delegates to OllamaProvider.complete().

    The inline HTTP + retry + supervisor logic is now in
    ``core.llm.llm_provider.OllamaProvider`` (which already had the
    same supervisor integration).  This unifies the Ollama call path
    with the cloud providers that were migrated in V10.31.0 Sprint 4.3.

    Streaming is still handled by ``_call_ollama_streaming`` (which
    already delegates to ``OllamaProvider.complete_streaming``).

    V18.2.14 (M5): Removed the ``_call_ollama_inline`` defensive
    fallback. The inline implementation was a 50-line duplicate of
    ``OllamaProvider.complete()`` kept "in case the provider has a bug"
    — but the provider is pure Python and has been stable since V13.
    When delegation fails, we now log a full traceable WARNING (type +
    message + traceback) and return ``None`` so the caller's existing
    retry/empty-response handling takes over, rather than silently
    running a second, divergent code path.

    Extracted verbatim from ``Summarizer._call_ollama`` in V18.8
    (Phase 5.1, Batch B). The only change: ``self.X`` → explicit params.
    """
    _log = log or _noop_log

    # V10.22.0: Streaming support — when enabled, use OllamaProvider's
    # complete_streaming() to show partial output in the UI log viewer.
    if streaming_enabled:
        return _call_ollama_streaming(
            prompt,
            model,
            temp,
            max_tokens,
            ollama_base_url=ollama_base_url,
            timeout=timeout,
            retries=retries,
            context_tokens=context_tokens,
            supervisor=supervisor,
            log=_log,
            error_tracker=error_tracker,  # V18.15.6.0 (Fix B)
        )

    # V10.32.0: delegate to OllamaProvider (non-streaming)
    try:
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings

        # V13.6.0: create_provider() only accepts (provider, settings,
        # log_callback, supervisor). Other kwargs passed to complete().
        provider = create_provider(
            provider="ollama",
            settings=Settings(),
            log_callback=_log,
            supervisor=supervisor,
        )
        # Override the model (create_provider uses settings default)
        if hasattr(provider, "_model"):
            provider._model = model
        # V13.44.3: Override the timeout — create_provider hardcodes 300s,
        # but we need 600s for Gemma 4 12B (takes 5+ min per call)
        if hasattr(provider, "timeout"):
            provider.timeout = timeout
        result = provider.complete(
            prompt=prompt,
            temperature=temp,
            max_tokens=max_tokens,
            model=model,
        )
        return result
    except Exception as _e:
        # V18.2.14 (M5): No more silent inline fallback. Log a full
        # traceable record so the failure is diagnosable: the exception
        # type + message at WARNING (visible in conversion log + GUI),
        # and the full traceback at DEBUG (for the structured log).
        _log(
            f"    ⚠️ OllamaProvider delegation failed: "
            f"{type(_e).__name__}: {_e} — returning None (caller handles)",
            "WARNING",
        )
        logger.warning(
            "OllamaProvider.complete() delegation failed for model=%s (prompt len=%d): %s: %s",
            model,
            len(prompt),
            type(_e).__name__,
            _e,
            exc_info=True,
        )
        # V18.15.6.0 (Fix B): classify the error type so the caller can
        # distinguish "timed out" from "not installed" (404) etc.
        if error_tracker is not None:
            error_tracker.clear()
            from core.llm.retry import OllamaTimeoutError as _OllamaTimeoutError

            if isinstance(_e, _OllamaTimeoutError):
                error_tracker.append("timeout")
            else:
                _err_msg = str(_e).lower()
                if "404" in _err_msg or "not found" in _err_msg:
                    error_tracker.append("not_found")
                elif "oom" in _err_msg or "out of memory" in _err_msg or "cuda" in _err_msg:
                    error_tracker.append("oom")
                elif "timeout" in _err_msg or "timed out" in _err_msg:
                    error_tracker.append("timeout")
                else:
                    error_tracker.append("other")
        return None


# ── _call_ollama_streaming (extracted verbatim, internal helper) ───────────


def _call_ollama_streaming(
    prompt: str,
    model: str,
    temp: float,
    max_tokens: int,
    *,
    ollama_base_url: str,
    timeout: int,
    retries: int,
    context_tokens: int,
    supervisor: SupervisorLike,
    log: LogCallback,
    error_tracker: list | None = None,  # V18.15.6.0 (Fix B)
) -> str | None:
    """V10.22.0: Streaming Ollama call — shows partial output in UI log.

    Uses OllamaProvider.complete_streaming() with an on_chunk callback
    that logs the first 200 chars of the growing response at intervals.
    Falls back to non-streaming if streaming fails.

    Extracted verbatim from ``Summarizer._call_ollama_streaming``.
    """
    try:
        from core.llm.llm_provider import OllamaProvider

        provider = OllamaProvider(
            model=model,
            base_url=ollama_base_url,
            temperature=temp,
            max_tokens=max_tokens,
            context_tokens=context_tokens,
            timeout=timeout,
            retries=retries,
            log_callback=log,
            supervisor=supervisor,
        )
        log(f"    🤖 {model} (t={temp:.2f}) streaming…", "INFO")

        _last_logged_len = 0

        def _on_chunk(accumulated_text: str) -> None:
            nonlocal _last_logged_len
            # Log every ~500 chars of new content (not every token — too noisy)
            if len(accumulated_text) - _last_logged_len > 500:
                _last_logged_len = len(accumulated_text)
                # Show last 200 chars as a preview
                preview = accumulated_text[-200:].replace("\n", " ")
                log(f"    📝 Streaming: {len(accumulated_text)} chars… ({preview[:80]}…)", "DEBUG")

        result = provider.complete_streaming(
            prompt=prompt,
            temperature=temp,
            max_tokens=max_tokens,
            model=model,
            on_chunk=_on_chunk,
        )
        if result:
            log(f"    ✅ Streaming complete: {len(result)} chars", "DEBUG")
            return result
        log("    ⚠️ Streaming returned empty — falling back to non-streaming", "WARNING")
    except Exception as _e:
        log(f"    ⚠️ Streaming failed ({_e}) — falling back to non-streaming", "WARNING")

    # Fallback to non-streaming
    return _call_ollama_nonstreaming(
        prompt,
        model,
        temp,
        max_tokens,
        context_tokens=context_tokens,
        timeout=timeout,
        retries=retries,
        ollama_base_url=ollama_base_url,
        supervisor=supervisor,
        log=log,
        error_tracker=error_tracker,  # V18.15.6.0 (Fix B): propagate tracker
    )


# ── _call_ollama_nonstreaming (extracted verbatim, internal helper) ───────


def _call_ollama_nonstreaming(
    prompt: str,
    model: str,
    temp: float,
    max_tokens: int,
    *,
    context_tokens: int,
    timeout: int,
    retries: int,
    ollama_base_url: str,
    supervisor: SupervisorLike,
    log: LogCallback,
    error_tracker: list | None = None,  # V18.15.6.0 (Fix B)
) -> str | None:
    """Non-streaming Ollama call (the original _call_ollama logic).

    Extracted verbatim from ``Summarizer._call_ollama_nonstreaming``.
    Preserves:
    - V18.2.19: Timeout → break (non-retryable via OllamaTimeoutError)
    - V10.4.0: supervisor.record_success / record_failure integration
    - Empty-response retry (ConnectionError → retryable)

    V18.15.6.0 (Fix B): ``error_tracker`` is an optional 1-element list
    the caller can pass to receive the error TYPE ("timeout" / "not_found" /
    "oom" / "empty") when the call returns None. This lets the Summarizer
    distinguish "model not installed" (404) from "model timed out during
    generation" (timeout) and surface a correct hint instead of the
    misleading "not installed" message. The tracker is a list (not a
    scalar) because Python closures capture by reference, not by value —
    a mutable container is the standard pattern for out-params.
    """
    # V18.20.2.0 (SWOT A3): route the fallback's num_ctx through the SAME
    # clamp the provider's adaptive path uses (core/llm/ctx_clamp.py). The
    # old raw `ctx = max(context_tokens, 16000)` had NO 26758 IQ2_S cap and
    # NO VRAM guard — a user-set 65536 + a streaming failure would send an
    # uncapped num_ctx to Ollama and OOM-loop the 12 GB card. The clamp is
    # a no-op when the GPU size can't be detected (headless/test sandbox).
    from core.llm.ctx_clamp import clamp_num_ctx
    from core.llm.retry import OllamaTimeoutError

    ctx = clamp_num_ctx(model, max(context_tokens, 16000))
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # V18.2.37e: override the Modelfile's system prompt
        "system": "",
        "options": {
            "temperature": temp,
            "num_predict": max_tokens,
            "num_ctx": ctx,
            # V18.2.20 (P7 follow-up): -1 = "all available GPU layers".
            "num_gpu": -1,
            # V18.2.42: presence_penalty removed — let Modelfile decide.
            # Forcing 0 puts Qwen3 in thinking mode. See llm_provider.py
            # for the full explanation.
        },
    }
    url = f"{ollama_base_url}/api/generate"

    # V18.2.21 (Phase 2.4-retry): Migrated from inline
    # `for attempt in range(self.retries + 1)` loop with linear
    # `time.sleep(3 * (attempt + 1))` to the consolidated @retry_llm_call
    # decorator. Preserves:
    #   - V18.2.19: Timeout → break (non-retryable). The break is now
    #     expressed as raising OllamaTimeoutError, which the decorator
    #     classifies as non-retryable (no retry, propagates immediately).
    #     The outer try/except converts it to None (matches old "break
    #     then return None" semantics).
    #   - V10.4.0: supervisor.record_success / record_failure integration.
    #     On Timeout and ConnectionError, record_failure is called inside
    #     _do_one_call before the exception propagates (so the supervisor
    #     still counts toward its 3-strike Ollama-restart threshold).
    #   - Empty-response retry (preserved as a ConnectionError → retryable).
    # NOTE: Unlike OllamaProvider.complete (which has the V10.18.0 A4 OOM
    # ctx-halving), this site did NOT have OOM-halving in the original —
    # the migration keeps that contract (OOM is treated as a generic 5xx
    # by the decorator, retried with backoff, eventually returns None).
    @retry_llm_call(max_attempts=retries + 1, log_callback=log)
    def _do_one_call() -> str:
        log(
            f"    🤖 {model} (t={temp:.2f}) num_ctx={ctx} attempt…",
            "INFO",
        )
        try:
            resp = safe_ollama_request("POST", url, json=payload, timeout=timeout)
        except _requests.exceptions.Timeout as e:
            # V18.2.19: Timeouts on IQ2_XXS (2.1 bits/param) indicate the
            # model is genuinely stuck (not a transient network issue).
            # Retrying just wastes another 600s. Log the timeout and break
            # immediately — the caller's empty-response handling takes over.
            log(
                f"    ⚠️ {model} timeout: {e} — "
                f"NOT retrying (timeout = model stuck, not transient). "
                f"Returning None; caller handles empty response.",
                "WARNING",
            )
            logger.warning(
                "Ollama timeout (model=%s, timeout=%ss) — not retrying "
                "(IQ2_XXS timeouts indicate model stall, not network issue)",
                model,
                timeout,
            )
            supervisor.record_failure()
            raise OllamaTimeoutError(model=model, timeout=timeout, original=e) from e
        except _requests.exceptions.ConnectionError as e:
            log(
                f"    ⚠️ {model} connection error: {e}",
                "WARNING",
            )
            supervisor.record_failure()
            raise  # ConnectionError → retryable per classifier
        # HTTP OK — parse the response JSON.
        text = resp.json().get("response", "").strip()
        if not text:
            # Empty response — raise ConnectionError so the decorator
            # retries (preserves old "log empty + sleep + retry" behavior).
            raise _requests.exceptions.ConnectionError("empty response from model")
        supervisor.record_success()
        return text

    try:
        return _do_one_call()
    except OllamaTimeoutError:
        # V18.2.19: model stall — return None, caller handles empty response.
        # (Logging already done inside _do_one_call to preserve the exact
        # log message from the original inline implementation.)
        # V18.15.6.0 (Fix B): record the error type so the caller can
        # distinguish "timed out" from "not installed" (404).
        if error_tracker is not None:
            error_tracker.clear()
            error_tracker.append("timeout")
        return None
    except Exception as e:
        # V18.2.21: retries exhausted OR a non-retryable error raised
        # (e.g. HTTP 404 model-not-found, or programming error).
        log(f"    ⚠️ {model} call failed: {e}", "WARNING")
        # V18.15.6.0 (Fix B): classify the error type for the caller.
        if error_tracker is not None:
            error_tracker.clear()
            _err_msg = str(e).lower()
            if (
                "404" in _err_msg
                or "not found" in _err_msg
                or "model" in _err_msg
                and "not" in _err_msg
            ):
                error_tracker.append("not_found")
            elif "oom" in _err_msg or "out of memory" in _err_msg or "cuda" in _err_msg:
                error_tracker.append("oom")
            elif "timeout" in _err_msg or "timed out" in _err_msg:
                error_tracker.append("timeout")
            else:
                error_tracker.append("other")
        return None


# ── call_openai_compat (extracted verbatim from Summarizer._call_openai_compat) ──


def call_openai_compat(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    label: str,
    temp: float,
    max_tokens: int,
    *,
    timeout: int,
    retries: int,
    provider: str,
    log: LogCallback | None = None,
) -> str | None:
    """Call an OpenAI-compatible API (OpenAI, OpenRouter, etc.).

    Extracted verbatim from ``Summarizer._call_openai_compat``. The only
    change: ``self.timeout``, ``self.retries``, ``self.provider``,
    ``self.log`` → explicit params.
    """
    _log = log or _noop_log

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if "openrouter" in base_url:
        headers["HTTP-Referer"] = "https://elixir.local"
        headers["X-Title"] = "Elixir"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temp,
    }
    url = f"{base_url.rstrip('/')}/chat/completions"

    # V18.2.21 (Phase 2.4-retry): Migrated from inline
    # `for attempt in range(self.retries + 1)` loop with linear
    # `time.sleep(2 * (attempt + 1))` to the consolidated @retry_llm_call
    # decorator. Same pattern as OpenAICompatProvider.complete — the
    # decorator classifies retryable (429 / 5xx / ConnectionError) vs
    # non-retryable (401 / 403 / 404 / programming) errors.
    icon = "☁️" if provider != "freellmapi" else "🔌"

    @retry_llm_call(max_attempts=retries + 1, log_callback=_log)
    def _do_one_call() -> str:
        _log(
            f"    {icon} {label} ({model}) t={temp:.2f} attempt…",
            "INFO",
        )
        # V18.20.4.11 (P3 / O-c5): pooled cloud session (proxy-trusting for
        # cloud endpoints, no-proxy for localhost /v1 endpoints) replaces the
        # bare per-call ``_requests.post`` — same timeout, same retries, plus
        # connection reuse. The deep-index choices[0] parse is replaced by
        # the shared shape-safe extract_openai_content: a malformed/error
        # payload now flows into the SAME empty-response retry path as an
        # empty-but-valid response (previously it raised straight to the
        # outer except → None, skipping the retry).
        resp = session_for_url(url).post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        text = extract_openai_content(resp.json())
        if not text:
            # Empty response — raise ConnectionError so the decorator retries
            # (preserves old "log empty + sleep + retry" behavior).
            raise _requests.exceptions.ConnectionError("empty response from cloud model")
        return text

    try:
        return _do_one_call()
    except Exception as e:
        # V18.2.21: retries exhausted OR a non-retryable error raised.
        _log(f"    ⚠️ {label} call failed: {e}", "WARNING")
        return None


# ── call_claude (extracted verbatim from Summarizer._call_claude) ──────────


def call_claude(
    prompt: str,
    max_tokens: int,
    temperature: float,
    *,
    claude_api_key: str,
    claude_model: str,
    claude_base_url: str,
    retries: int,
    log: LogCallback | None = None,
) -> str | None:
    """Call the Anthropic Claude API directly.

    Extracted verbatim from ``Summarizer._call_claude``. The only change:
    ``self.claude_*``, ``self.retries``, ``self.log`` → explicit params.
    """
    _log = log or _noop_log

    if not claude_api_key:
        _log("  ❌ Claude API key not set. Please add it in settings.", "ERROR")
        return None

    headers = {
        "Content-Type": "application/json",
        "x-api-key": claude_api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": claude_model,
        "max_tokens": min(max_tokens, 8192),  # Claude max is 8192 for most models
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    url = f"{claude_base_url.rstrip('/')}/messages"

    # V18.2.21 (Phase 2.4-retry): Migrated from inline
    # `for attempt in range(self.retries + 1)` loop with linear
    # `time.sleep(2 * (attempt + 1))` (and a 429-specific
    # `time.sleep(5 * (attempt + 1))`) to the consolidated @retry_llm_call
    # decorator. The 429 case previously had a double-sleep (5s + 2s = 7s)
    # before retry — collapsed into a single exponential backoff wait.
    # The 401 case ("invalid key") now propagates immediately instead of
    # being retried (retrying a bad API key is pointless).
    @retry_llm_call(max_attempts=retries + 1, log_callback=_log)
    def _do_one_call() -> str:
        _log(
            f"    🧠 Claude ({claude_model}) t={temperature:.2f} attempt…",
            "INFO",
        )
        # V18.20.4.11 (P3 / O-c5): pooled session (see call_openai_compat).
        resp = session_for_url(url).post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()  # → HTTPError for 401/429/5xx
        data = resp.json()
        # Claude returns content as a list of text blocks
        content = data.get("content", [])
        if content and isinstance(content, list):
            text_parts = [block.get("text", "") for block in content if block.get("type") == "text"]
            text = "".join(text_parts).strip()
            if text:
                _log(f"    ✅ Claude response: {len(text)} chars", "INFO")
                return text
        # Empty response — raise ConnectionError so the decorator retries
        # (preserves old "log empty + sleep + retry" behavior).
        raise _requests.exceptions.ConnectionError("empty response from Claude")

    try:
        return _do_one_call()
    except _requests.exceptions.HTTPError as e:
        # V18.2.21: Surface the actionable 401 message; other 4xx/5xx are
        # logged via the decorator's before_sleep hook (if retried) or here.
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status == 401:
            _log("  ❌ Claude API key invalid or expired.", "ERROR")
        elif status == 429:
            _log("  ⚠️ Claude rate limited — retries exhausted.", "WARNING")
        else:
            _body = ""
            try:
                _body = e.response.text[:200] if e.response is not None else ""
            except Exception:
                _body = ""
            _log(
                f"    ⚠️ Claude HTTP {status} call failed: {_body}",
                "WARNING",
            )
        return None
    except Exception as e:
        _log(f"    ⚠️ Claude call failed: {e}", "WARNING")
        return None


# ── call_via_llm_provider (extracted verbatim from Summarizer._call_via_llm_provider) ──


def call_via_llm_provider(
    provider_type: str,
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    temp: float,
    max_tokens: int,
    *,
    timeout: int,
    supervisor: SupervisorLike,
    log: LogCallback | None = None,
    # Fallback functions (for the inline fallback path):
    call_claude_fn: Callable = None,
    call_openai_compat_fn: Callable = None,
) -> str | None:
    """V10.31.0 (Sprint 4.3): Delegate to core.llm.llm_provider.

    Creates a provider via ``create_provider`` and calls
    ``provider.complete()``.  Falls back to the inline ``call_claude``
    / ``call_openai_compat`` if the provider abstraction is unavailable
    (shouldn't happen — it's pure Python — but defensive).

    Extracted verbatim from ``Summarizer._call_via_llm_provider``. The
    only change: ``self.*`` → explicit params. The fallback functions
    are passed as callbacks (``call_claude_fn``, ``call_openai_compat_fn``)
    to avoid circular imports within the module.
    """
    _log = log or _noop_log

    try:
        from core.llm.llm_provider import create_provider
        from utils.settings import Settings

        # V13.6.0: create_provider() only accepts (provider, settings,
        # log_callback, supervisor). Other kwargs (model, temperature,
        # etc.) are passed to provider.complete() below. Previously
        # passing them to create_provider() caused TypeError.
        provider = create_provider(
            provider=provider_type,
            settings=Settings(),
            log_callback=_log,
            supervisor=supervisor,
        )
        # Override the model (create_provider uses settings default)
        if hasattr(provider, "_model"):
            provider._model = model
        # V13.44.3: Override the timeout — create_provider hardcodes 300s
        if hasattr(provider, "timeout"):
            provider.timeout = timeout
        # Apply cloud-specific settings (base_url, api_key) for openai_compat
        if provider_type == "openai_compat" and base_url:
            provider._base_url = base_url
        if provider_type == "openai_compat" and api_key:
            provider._api_key = api_key
        # V0.04: llama.cpp — apply the endpoint overrides through the REAL
        # attribute names (LlamaCppProvider exposes base_url/api_key, not
        # the underscore-prefixed names the openai_compat branch targets —
        # that legacy branch is inert dead code and is left untouched; see
        # the known-follow-ups note in CHANGELOG V0.04). The Summarizer
        # passes the same values create_provider already read from the
        # llamacpp_* settings, so this is a no-op in practice — it exists
        # so an explicit per-call endpoint override can never be silently
        # dropped for the new backend.
        if provider_type == "llamacpp":
            if base_url and hasattr(provider, "base_url"):
                provider.base_url = base_url.rstrip("/")
            if api_key and hasattr(provider, "api_key"):
                provider.api_key = api_key
        _log(f"    🤖 {model} (t={temp:.2f}) via llm_provider.{provider_type}…", "INFO")
        result = provider.complete(
            prompt=prompt,
            temperature=temp,
            max_tokens=max_tokens,
            model=model,
        )
        if result and result.strip():
            return result.strip()
        _log("    ⚠️ llm_provider returned empty — falling back to inline call", "WARNING")
    except Exception as _e:
        _log(
            f"    ⚠️ llm_provider.{provider_type} failed ({_e}) — falling back to inline", "WARNING"
        )
        logger.debug("llm_provider delegation failed: %s: %s", type(_e).__name__, _e)
    # Fallback to the inline implementations
    if provider_type == "claude":
        if call_claude_fn:
            return call_claude_fn(prompt, max_tokens=max_tokens, temperature=temp)
        return None
    if call_openai_compat_fn:
        return call_openai_compat_fn(
            prompt,
            base_url=base_url,
            api_key=api_key,
            model=model,
            label=provider_type,
            temp=temp,
            max_tokens=max_tokens,
        )
    return None


# ── call_fast_ollama (Phase 5.3: migrated from inline for-loop to @retry_llm_call) ──


def call_fast_ollama(
    prompt: str,
    model: str,
    temp: float,
    max_tokens: int,
    *,
    ollama_base_url: str,
    fast_model_context: int,
    log: LogCallback | None = None,
) -> str | None:
    """V17.0.0: Call fast model via Ollama with configurable 128K context.

    V18.8 (Phase 5.3): Migrated from inline ``for attempt in range(2)``
    loop with ``time.sleep(2)`` to the consolidated ``@retry_llm_call``
    decorator. This was the LAST holdout — all other call sites were
    migrated in V18.2.21.

    The migration preserves:
    - 2 attempts (max_attempts=retries+1=2 with retries=1)
    - Empty-response → retryable (ConnectionError)
    - Timeout → retryable (was retried in the old inline loop; now
      the decorator classifies it as retryable too)
    - 120s timeout (was hardcoded in the inline loop; preserved here)
    """
    _log = log or _noop_log

    ctx = fast_model_context or 131072
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # V18.2.37e: override the Modelfile's system prompt
        "system": "",
        # V18.2.20 (P7 follow-up): -1 = "all available GPU layers"
        # (was 99 — see _call_ollama_nonstreaming above for rationale).
        # V18.2.42: presence_penalty removed — let Modelfile decide.
        "options": {
            "temperature": temp,
            "num_predict": max_tokens,
            "num_ctx": ctx,
            "num_gpu": -1,
        },
    }
    url = f"{ollama_base_url}/api/generate"

    @retry_llm_call(max_attempts=2, log_callback=_log)
    def _do_one_call() -> str:
        _log(f"    🤖 {model} (t={temp:.2f}, ctx={ctx // 1024}K) attempt…", "INFO")
        resp = safe_ollama_request("POST", url, json=payload, timeout=120)
        text = resp.json().get("response", "").strip()
        if not text:
            raise _requests.exceptions.ConnectionError("empty response from fast model")
        return text

    try:
        return _do_one_call()
    except Exception as e:
        _log(f"    ⚠️ Fast model call failed: {e}", "WARNING")
        return None


__all__ = [
    "call_ollama",
    "call_openai_compat",
    "call_claude",
    "call_via_llm_provider",
    "call_fast_ollama",
]
