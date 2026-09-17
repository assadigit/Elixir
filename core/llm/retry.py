"""V18.2.21 (Phase 1.4): Consolidated retry module for LLM calls.

Replaces the 8 duplicated ad-hoc retry loops scattered across
``core/llm/llm_provider.py`` and ``core/summarisation/summarizer.py`` with
one tenacity-based decorator that uses **exponential backoff + jitter** and
classifies errors as retryable vs non-retryable.

The 8 sites (do NOT migrate yet — this module is the migration target):

  - ``core/llm/llm_provider.py:336``  ``time.sleep(3 * (attempt + 1))``
  - ``core/llm/llm_provider.py:498``  ``time.sleep(2 * (attempt + 1))``
  - ``core/llm/llm_provider.py:642``  ``_time.sleep(10)``  (batch-API poll loop)
  - ``core/llm/llm_provider.py:757``  ``time.sleep(5 * (attempt + 1))``  (Claude 429)
  - ``core/llm/llm_provider.py:765``  ``time.sleep(2 * (attempt + 1))``
  - ``core/summarisation/summarizer.py:2467``  ``time.sleep(3 * (attempt + 1))``
  - ``core/summarisation/summarizer.py:2507``  ``time.sleep(2 * (attempt + 1))``
  - ``core/summarisation/summarizer.py:2555``  ``time.sleep(5 * (attempt + 1))``

== Migration guide (before / after) ==

The 8 sites above currently follow this pattern (showing
``OllamaProvider.complete``, ``core/llm/llm_provider.py:264-337``)::

    for attempt in range(self.retries + 1):
        try:
            resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
            text = resp.json().get("response", "").strip()
            if text:
                return text
        except _requests.exceptions.ConnectionError as e:
            self.log(f"    ⚠️ connection error: {e}", "WARNING")
            self._supervisor.record_failure()
        except _requests.exceptions.Timeout as e:
            self.log("    ⚠️ timeout — NOT retrying (V18.2.19)", "WARNING")
            return None
        except _requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None  # do NOT retry — pulling is a user action
        except Exception as e:
            if "oom" in str(e).lower():
                ctx //= 2  # V10.18.0 (A4): halve context, retry once
                continue
        if attempt < self.retries:
            time.sleep(3 * (attempt + 1))  # linear, no jitter
    return None

After migration::

    from core.llm.retry import (
        retry_llm_call,
        ModelNotFound404Error,
        OllamaTimeoutError,
        OllamaOOMError,
        retry_with_oom_context_halving,
    )

    @retry_llm_call(max_attempts=3, log_callback=self.log)
    def _do_one_call(num_ctx: int) -> str:
        payload["options"]["num_ctx"] = num_ctx
        resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
        if resp.status_code == 404:
            raise ModelNotFound404Error(model=_model, detail=resp.json().get("error", ""))
        try:
            text = resp.json().get("response", "").strip()
        except Exception as e:
            if "oom" in str(e).lower():
                raise OllamaOOMError(model=_model, num_ctx=num_ctx, detail=str(e))
            raise
        if not text:
            raise RuntimeError("empty response")
        return text

    try:
        # retry_with_oom_context_halving wraps _do_one_call with the V10.18.0
        # A4 OOM-halving semantics (one retry at halved num_ctx). The
        # @retry_llm_call decorator on _do_one_call handles transient
        # ConnectionError / 429 / 5xx with exponential backoff + jitter.
        return retry_with_oom_context_halving(
            call_fn=_do_one_call,
            initial_ctx=ctx,
            log_callback=self.log,
        )
    except ModelNotFound404Error:
        return None  # caller logs the actionable "ollama pull" message
    except OllamaTimeoutError:
        return None  # V18.2.19: model stall — caller handles empty response

The migration is mechanical: the inline `time.sleep(N*(attempt+1))` loop
collapses into a `@retry_llm_call()` decorator + (optionally) the
``retry_with_oom_context_halving`` wrapper for OOM handling.

== Why non-retryable for these cases (preserves V18.2.19 semantics) ==

  - ``ModelNotFound404Error``: pulling a model is a user action, not transient.
  - ``OllamaTimeoutError``: IQ2_XXS (2.1 bits/param) timeouts indicate the
    model is genuinely stuck (not a network blip) — retrying just wastes
    another full ``timeout`` window (V18.2.19).
  - ``OllamaOOMError``: a retry at the same ``num_ctx`` would just OOM again.
    The caller must halve ``num_ctx`` first (see
    ``retry_with_oom_context_halving``).

== Graceful degradation ==

If ``tenacity`` is not installed at import time, this module logs a single
WARNING and falls back to a 2-attempt LINEAR retry (no jitter, no exponential
backoff). The fallback preserves the retryable/non-retryable classification
via ``classify_ollama_exception`` — only the wait strategy degrades.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import requests as _requests

# V18.20.4.12 (T-c7): ModelNotFound404Error moved to the shared
# core/llm/model_errors.py module (detection + canonical message unified
# tree-wide). Re-exported here so every existing importer
# (async_provider, ollama_provider, tests) keeps working with ZERO
# changes — ``from core.llm.retry import ModelNotFound404Error`` still
# resolves, and ``classify_ollama_exception`` below isinstance-checks the
# same shared class.
from core.llm.model_errors import ModelNotFound404Error  # noqa: F401 — re-export (in __all__)

logger = logging.getLogger(__name__)

# V18.2.21 (Phase 1.4): tenacity is an optional dependency. The module-level
# try/except determines which implementation of `retry_llm_call` is used.
# When tenacity is absent, we fall back to a 2-attempt LINEAR retry (see
# `_make_retry_fallback`). The warning is logged ONCE at import time so we
# don't spam the log on every call.
try:
    import tenacity as _tenacity  # type: ignore[import-not-found]

    _HAS_TENACITY: bool = True
except ImportError:  # pragma: no cover — exercised only when tenacity is absent
    _tenacity = None  # type: ignore[assignment]
    _HAS_TENACITY = False
    logger.warning(
        "tenacity is not installed — core.llm.retry is falling back to a "
        "2-attempt LINEAR retry (no jitter, no exponential backoff). Install "
        "`tenacity>=8.2.0` (`pip install tenacity`) for production-grade retry."
    )

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "ModelNotFound404Error",
    "OllamaTimeoutError",
    "OllamaOOMError",
    "classify_ollama_exception",
    "retry_llm_call",
    "retry_with_oom_context_halving",
]


# ── Exception classes ───────────────────────────────────────────────────────

# NOTE (V18.20.4.12 / T-c7): ``ModelNotFound404Error`` is now defined in
# ``core/llm/model_errors.py`` (see the import + comment above). It was
# defined here from V18.2.21 until V18.20.4.12; the move is invisible to
# importers because this module re-exports the shared class and keeps it
# in ``__all__``.


class OllamaTimeoutError(RuntimeError):
    """Wrapper around ``requests.exceptions.Timeout``.

    V18.2.19: timeouts on IQ2_XXS (2.1 bits/param) indicate the model is
    genuinely stuck (not a transient network issue). Retrying just wastes
    another full ``timeout`` window — V18.2.19 explicitly disabled retry on
    Timeout in ``summarizer.py:2463``. This class makes that classification
    explicit so the decorator can route it correctly.

    V18.15.6.0 (Fix C): the non-retryable classification now ONLY applies
    to non-IQ2_S models. IQ2_S (27B, 5-15 tok/s) can legitimately need
    >600s for 8192 output tokens — a timeout there means "slow", not
    "stalled". ``classify_ollama_exception`` checks ``is_iq2_s(model)``
    and returns True (retryable) for IQ2_S timeouts.
    """

    def __init__(
        self,
        model: str,
        timeout: float,
        original: BaseException | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.original = original
        super().__init__(
            f"Ollama timeout (model={model}, timeout={timeout}s) — "
            f"non-retryable for non-IQ2_S models (IQ2_XXS stall); "
            f"retryable for IQ2_S (slow, not stalled)"
        )


class OllamaOOMError(RuntimeError):
    """Ollama returned an out-of-memory error. Non-retryable AS-IS.

    V10.18.0 (A4): the caller should halve ``num_ctx`` and retry ONCE via
    :func:`retry_with_oom_context_halving`. Retrying at the same ``num_ctx``
    would just OOM again — the KV cache size is the root cause.
    """

    def __init__(self, model: str, num_ctx: int, detail: str = "") -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.detail = detail
        msg = f"Ollama OOM (model={model}, num_ctx={num_ctx})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class ThinkingModeViolation(RuntimeError):
    """V18.3 (Phase 1.2): A Qwen3 model was called with presence_penalty=0.

    This is the V18.2.41 regression: ``presence_penalty=0`` activates Qwen3
    THINKING MODE, causing the model to emit internal reasoning
    ("The user wants…", "Let me analyze…") instead of the actual summary.
    The V18.2.41 conversion scored 2/10 — a catastrophic failure.

    V18.2.42 fixed this by removing the app's ``presence_penalty=0`` override
    (letting the Modelfile's ``presence_penalty=1.5`` decide). V18.3 adds
    this GUARD as a fail-closed safety net: if the payload's
    ``options.presence_penalty`` is explicitly ``0.0`` for a Qwen3 model,
    the provider REFUSES the call rather than silently producing thinking-mode
    garbage.

    Non-retryable — the user must fix the Modelfile (set ``presence_penalty 1.5``)
    or stop forcing it in the app payload.
    """

    def __init__(self, model: str, detail: str = "") -> None:
        self.model = model
        self.detail = detail
        msg = (
            f"ThinkingModeViolation: Qwen3 model '{model}' called with "
            f"presence_penalty=0.0 — this activates THINKING MODE (the "
            f"V18.2.41 2/10 regression). Fix: set presence_penalty=1.5 in "
            f"the Modelfile (Instruct mode) and ensure the app does NOT "
            f"override it to 0."
        )
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


# ── Classification ──────────────────────────────────────────────────────────


def classify_ollama_exception(exc: BaseException) -> bool:
    """Return ``True`` if ``exc`` is a transient / retryable error.

    **Retryable** (returns ``True``):

      - ``requests.ConnectionError`` — network blip, Ollama down, or
        supervisor-triggered restart (V10.4.0).
      - ``requests.HTTPError`` with status ``429`` (rate limit) or ``5xx``
        (server-side transient error).
      - Other ``requests.RequestException`` subtypes not matching above
        (e.g. ``ChunkedEncodingError``, ``ContentDecodingError``) — treat as
        transient network issues.

    **Non-retryable** (returns ``False``):

      - :class:`ModelNotFound404Error` — pulling is a user action.
      - :class:`OllamaTimeoutError` — V18.2.19: model stall, not transient.
      - :class:`OllamaOOMError` — caller must halve ``num_ctx`` first.
      - ``requests.Timeout`` — wrapped as ``OllamaTimeoutError`` by the
        caller, but also classified non-retryable here for safety.
      - ``requests.HTTPError`` with status ``404`` (model not found),
        ``401`` (bad API key), ``403`` (forbidden), ``400`` (bad request).
      - Any exception whose ``str()`` message contains ``"oom"`` /
        ``"out of memory"`` / ``"cuda out of memory"`` (defensive — in case
        the caller didn't wrap into :class:`OllamaOOMError`).
      - Programming errors (``ValueError``, ``TypeError``, ``KeyError``,
        ``AttributeError``, ``KeyboardInterrupt``) — non-retryable.

    Args:
        exc: the exception raised by the LLM call.

    Returns:
        ``True`` if the call should be retried, ``False`` if it should be
        re-raised immediately.
    """
    # V18.2.21: explicitly-typed non-retryable exceptions first.
    # V18.15.6.0 (Fix C): OllamaTimeoutError for IQ2_S is RETRYABLE — the
    # model isn't stalled, it's just slow (27B IQ2_S at 5-15 tok/s can
    # legitimately need >600s for 8192 output tokens). The user's hard
    # constraint says "IQ2_S excluded from 300s timeout" — the same logic
    # applies to retry classification. Pre-V18.15.6.0, ALL timeouts were
    # classified non-retryable (citing IQ2_XXS as the reason), which
    # caused the V18.15.5.1 golden-master failure: the retry-with-nudge
    # couldn't fire because the decorator swallowed the timeout. Now IQ2_S
    # timeouts are retryable (the @retry_llm_call decorator + the
    # _call_llm_with_empty_retry nudge both get a chance).
    if isinstance(exc, ModelNotFound404Error):
        return False
    if isinstance(exc, OllamaOOMError):
        return False
    if isinstance(exc, OllamaTimeoutError):
        # V18.15.6.0 (Fix C): IQ2_S timeout → retryable (model is slow,
        # not stalled). All other timeouts (IQ2_XXS/XS, Q2_K, normal
        # models) → non-retryable (the V18.2.19 model-stall rule).
        _model = getattr(exc, "model", None) or ""
        try:
            from core.llm.model_taxonomy import is_iq2_s
            if is_iq2_s(_model):
                return True  # IQ2_S — retryable
        except Exception:
            pass  # if taxonomy import fails, fall through to non-retryable
        return False  # non-IQ2_S timeout — non-retryable
    # KeyboardInterrupt must NEVER be retried.
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        return False
    # Programming errors — non-retryable.
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError, IndexError)):
        return False
    # requests.Timeout — V18.2.19: model stall, not transient.
    if isinstance(exc, _requests.exceptions.Timeout):
        return False
    # requests.ConnectionError — retryable (network blip / Ollama down).
    if isinstance(exc, _requests.exceptions.ConnectionError):
        return True
    # requests.HTTPError — depends on status code.
    if isinstance(exc, _requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 404:
            return False  # model not found — caller wraps into ModelNotFound404Error
        if status == 429:
            return True  # rate limit — retryable
        if status is not None and 500 <= status < 600:
            return True  # 5xx — server-side, retryable
        # 400 / 401 / 403 / 4xx — non-retryable (caller error).
        return False
    # Other requests errors (ChunkedEncodingError, etc.) — retryable.
    if isinstance(exc, _requests.exceptions.RequestException):
        return True
    # Defensive: detect OOM via message even if caller didn't wrap it.
    msg = str(exc).lower()
    if "out of memory" in msg or "cuda out of memory" in msg or "oom" in msg:
        return False
    # Default: non-retryable. Unknown exceptions are usually programming errors
    # or genuinely new failure modes that should be investigated, not retried.
    return False


# ── OOM context-halving helper ──────────────────────────────────────────────


def retry_with_oom_context_halving(
    call_fn: Callable[[int], Any],
    initial_ctx: int,
    min_ctx: int = 8192,
    log_callback: Callable[[str, str], None] | None = None,
) -> Any:
    """Call ``call_fn(num_ctx)``; on :class:`OllamaOOMError`, halve and retry ONCE.

    Preserves V10.18.0 (A4) semantics: instead of retrying at the same ctx
    (which would just OOM again), halve the KV cache size. The halving is
    capped at ``min_ctx`` (default ``8192`` — Ollama's practical minimum
    below which most models can't fit their system prompt).

    Args:
        call_fn: a function that takes ``num_ctx`` (int) and returns the LLM
            response. It may raise :class:`OllamaOOMError` (in which case the
            ctx is halved and the call is retried) or any other exception
            (propagated unchanged).
        initial_ctx: the starting context window (e.g. ``65536``).
        min_ctx: floor — if ``initial_ctx`` is already at or below ``min_ctx``
            when OOM occurs, the OOM is re-raised (no further halving possible).
        log_callback: optional ``fn(msg, level)`` for progress logging
            (mirrors the ``LLMProvider.log`` signature).

    Returns:
        Whatever ``call_fn`` returns on the successful attempt.

    Raises:
        OllamaOOMError: if ``call_fn`` raises OOM at or below ``min_ctx``
            (no further halving possible).
        Any other exception: propagated unchanged from ``call_fn``.

    Note:
        The inner ``call_fn`` itself can be decorated with
        :func:`retry_llm_call` — the OOM-halving wrapper composes cleanly
        with the transient-retry decorator (the decorator handles
        ConnectionError/429/5xx; this wrapper handles OOM).
    """
    ctx = initial_ctx
    try:
        return call_fn(ctx)
    except OllamaOOMError as exc:
        new_ctx = max(min_ctx, ctx // 2)
        if new_ctx == ctx:
            # Already at min — can't reduce further. Re-raise the OOM.
            if log_callback is not None:
                try:
                    log_callback(
                        f"🚨 VRAM OOM at num_ctx={ctx} (already at min {min_ctx}) — not retrying",
                        "ERROR",
                    )
                except Exception:
                    pass
            raise
        if log_callback is not None:
            try:
                log_callback(
                    f"🚨 VRAM OOM — retrying with {new_ctx} context tokens (halved from {ctx})",
                    "WARNING",
                )
            except Exception:
                pass
        logger.warning(
            "Ollama OOM (model=%s, num_ctx=%d → %d) — halving context and retrying once",
            exc.model,
            ctx,
            new_ctx,
        )
        return call_fn(new_ctx)


# ── Decorator (tenacity path) ──────────────────────────────────────────────


def _make_retry_with_tenacity(
    max_attempts: int,
    initial_wait: float,
    max_wait: float,
    jitter: float,
    log_callback: Callable[[str, str], None] | None,
) -> Callable[[F], F]:
    """Build a tenacity-based retry decorator. Only called when _HAS_TENACITY."""
    from tenacity import (  # type: ignore[import-not-found]
        RetryCallState,
        retry_if_exception,
        stop_after_attempt,
        wait_exponential_jitter,
    )
    from tenacity import (
        retry as _t_retry,
    )

    def _before_sleep(state: RetryCallState) -> None:
        # state.outcome.exception() is the exception that triggered the retry.
        exc = state.outcome.exception() if state.outcome is not None else None
        wait_s: float = state.next_action.sleep if state.next_action is not None else 0.0
        exc_type = type(exc).__name__ if exc is not None else "unknown"
        msg = (
            f"⚠️ LLM call attempt {state.attempt_number} failed "
            f"({exc_type}: {exc}) — retrying in {wait_s:.2f}s"
        )
        if log_callback is not None:
            try:
                log_callback(msg, "WARNING")
            except Exception:  # noqa: BLE001 — log must never crash the retry
                pass
        logger.warning(msg)

    decorator: Callable[[F], F] = _t_retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=initial_wait, max=max_wait, jitter=jitter),
        retry=retry_if_exception(classify_ollama_exception),
        reraise=True,
        before_sleep=_before_sleep,
    )
    return decorator


# ── Decorator (fallback path — no tenacity) ─────────────────────────────────


def _make_retry_fallback(
    max_attempts: int,
    initial_wait: float,
    log_callback: Callable[[str, str], None] | None,
) -> Callable[[F], F]:
    """Build a simple LINEAR-retry decorator used when tenacity is absent.

    Falls back to at most 2 attempts (initial + 1 retry) with LINEAR backoff
    ``initial_wait * attempt`` and NO jitter. Only retryable exceptions (per
    :func:`classify_ollama_exception`) are retried; non-retryable exceptions
    are re-raised immediately. This matches the spirit of the existing ad-hoc
    loops (which used ``time.sleep(N * (attempt + 1))``) so behavior degrades
    gracefully to "what we had before" rather than to "no retry at all".
    """

    # V18.2.21: cap at 2 attempts in fallback mode — the spec says "simple
    # 2-attempt linear retry". This also keeps the worst-case latency bounded
    # when tenacity isn't installed (no exponential blowup).
    effective_attempts = max(1, min(max_attempts, 2))

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, effective_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 — re-raised below
                    last_exc = exc
                    if not classify_ollama_exception(exc):
                        # Non-retryable — re-raise immediately.
                        raise
                    if attempt >= effective_attempts:
                        # Exhausted attempts — break and re-raise below.
                        break
                    sleep_s = initial_wait * attempt
                    msg = (
                        f"⚠️ LLM call attempt {attempt} failed "
                        f"({type(exc).__name__}: {exc}) — "
                        f"[FALLBACK no-tenacity] retrying in {sleep_s:.2f}s"
                    )
                    if log_callback is not None:
                        try:
                            log_callback(msg, "WARNING")
                        except Exception:  # noqa: BLE001
                            pass
                    logger.warning(msg)
                    time.sleep(sleep_s)
            assert last_exc is not None  # for the type checker — loop ran ≥1×
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


# ── Public decorator factory ───────────────────────────────────────────────


def retry_llm_call(
    *,
    max_attempts: int = 3,
    initial_wait: float = 2.0,
    max_wait: float = 30.0,
    jitter: float = 2.0,
    log_callback: Callable[[str, str], None] | None = None,
) -> Callable[[F], F]:
    """Decorator: retry an LLM call with exponential backoff + jitter.

    Uses tenacity's ``wait_exponential_jitter`` (``initial=2, max=30, jitter=2``
    by default → 2s, 4s, 8s, 16s, 30s, 30s, … with ±2s jitter on each). Only
    retryable exceptions (per :func:`classify_ollama_exception`) are retried;
    non-retryable exceptions (404, Timeout, OOM, programming errors) are
    raised immediately.

    Args:
        max_attempts: max number of attempts (default ``3`` = 1 initial + 2
            retries). Set to ``1`` to disable retry entirely.
        initial_wait: first backoff in seconds (default ``2.0``).
        max_wait: cap on backoff in seconds (default ``30.0``).
        jitter: ±seconds of jitter added to each wait (default ``2.0``).
        log_callback: optional ``fn(msg, level)`` — receives retry warnings
            (mirrors ``LLMProvider.log`` signature). Defaults to ``None``
            (only the module logger is used).

    Returns:
        A decorator that wraps the function with retry logic.

    Falls back to a 2-attempt LINEAR retry (no jitter, no exponential) if
    tenacity is not installed — a WARNING is logged once at module import
    time. ``max_attempts`` is capped at 2 in fallback mode (per the
    "simple 2-attempt linear retry" spec).

    Example::

        @retry_llm_call(max_attempts=3, log_callback=self.log)
        def _do_call(prompt: str) -> str:
            ...
    """
    if _HAS_TENACITY:
        return _make_retry_with_tenacity(max_attempts, initial_wait, max_wait, jitter, log_callback)
    return _make_retry_fallback(max_attempts, initial_wait, log_callback)
