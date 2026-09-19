"""V18.2.21 (Phase 1.4): Tests for the consolidated retry module.

Covers:
  1. Retryable error (requests.ConnectionError) retries then succeeds.
  2. Non-retryable ModelNotFound404Error raises immediately without retry.
  3. Non-retryable OllamaTimeoutError raises immediately without retry.
  4. max_attempts exhaustion raises the last exception.
  5. Jitter produces varying wait times (statistical — not always identical).
  6. Graceful degradation when tenacity is not installed (mock the import).
"""

from __future__ import annotations

import importlib
import logging
import sys
import time
from typing import Any

import pytest
import requests

# IMPORTANT: import the retry module via the package path so reload + reload
# back works cleanly across tests.
import core.llm.retry as retry_mod

# V18.20.3.12 (O8 xfail normalization, user-approved): the tests below
# characterize REAL tenacity behaviors (jitter, exhaustion semantics,
# per-callback retry hooks) that the linear 2-attempt fallback cannot
# reproduce. They fail in every environment without the optional
# `tenacity` dependency (this sandbox since V18.20.3.7). Mark them
# xfail-when-tenacity-is-absent so the baseline is honest in BOTH envs:
# with tenacity they run as normal passing tests; without it they report
# xfail instead of failure. Non-strict: an XPASS (tenacity present, or a
# fallback improvement) never fails the suite.
try:
    import tenacity  # noqa: F401

    _TENACITY_ABSENT = False
except ImportError:
    _TENACITY_ABSENT = True

_TENACITY_XFAIL = pytest.mark.xfail(
    _TENACITY_ABSENT,
    reason=(
        "tenacity not installed — core.llm.retry falls back to the linear "
        "2-attempt retry; this tenacity-specific behavior cannot be "
        "reproduced (V18.20.3.12 / O8 normalization)"
    ),
    strict=False,
)


# ── Shared helpers ──────────────────────────────────────────────────────────


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Patch ``time.sleep`` to a no-op so retry tests run instantly.

    Tenacity looks up ``time.sleep`` at call time via its ``nap`` module,
    so patching the global ``time.sleep`` is the simplest way to bypass waits.
    """
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    yield


@pytest.fixture
def captured_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch ``time.sleep`` to RECORD the wait durations without sleeping."""
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    yield sleeps


# ── 1. Retryable error retries then succeeds ────────────────────────────────


class TestRetryThenSucceed:
    """A retryable exception (ConnectionError) should retry and eventually succeed."""

    @_TENACITY_XFAIL
    def test_connection_error_retries_then_succeeds(self, no_sleep: Any) -> None:
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=lambda _m, _l: None)
        def f() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise requests.exceptions.ConnectionError("transient")
            return "ok"

        result = f()
        assert result == "ok"
        assert calls["n"] == 3, f"Expected 3 attempts, got {calls['n']}"

    def test_first_attempt_succeeds_no_retry(self, no_sleep: Any) -> None:
        """If the call succeeds on attempt 1, no retry should happen."""
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3)
        def f() -> str:
            calls["n"] += 1
            return "immediate"

        assert f() == "immediate"
        assert calls["n"] == 1

    def test_429_rate_limit_retries(self, no_sleep: Any) -> None:
        """HTTP 429 (rate limit) is retryable."""

        class _FakeResp:
            status_code = 429

        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=lambda _m, _l: None)
        def f() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise requests.exceptions.HTTPError("429 Too Many Requests", response=_FakeResp())
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 2

    def test_5xx_server_error_retries(self, no_sleep: Any) -> None:
        """HTTP 5xx (server-side) is retryable."""

        class _FakeResp:
            status_code = 503

        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=lambda _m, _l: None)
        def f() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise requests.exceptions.HTTPError("503 Service Unavailable", response=_FakeResp())
            return "ok"

        assert f() == "ok"
        assert calls["n"] == 2


# ── 2. ModelNotFound404Error raises immediately without retry ───────────────


class TestNonRetryable404:
    """ModelNotFound404Error is non-retryable (pulling is a user action)."""

    def test_model_not_found_raises_immediately(self, no_sleep: Any) -> None:
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3)
        def f() -> str:
            calls["n"] += 1
            raise retry_mod.ModelNotFound404Error("qwen2.5:latest", "model not found")

        with pytest.raises(retry_mod.ModelNotFound404Error) as excinfo:
            f()
        assert calls["n"] == 1, "404 must NOT be retried"
        assert "qwen2.5:latest" in str(excinfo.value)
        assert "ollama pull" in str(excinfo.value)

    def test_http_404_classified_non_retryable(self) -> None:
        """A raw requests.HTTPError with status 404 is also non-retryable."""

        class _FakeResp:
            status_code = 404

        err = requests.exceptions.HTTPError("404 Not Found", response=_FakeResp())
        assert retry_mod.classify_ollama_exception(err) is False

    def test_http_401_classified_non_retryable(self) -> None:
        """HTTP 401 (bad API key) is non-retryable."""

        class _FakeResp:
            status_code = 401

        err = requests.exceptions.HTTPError("401 Unauthorized", response=_FakeResp())
        assert retry_mod.classify_ollama_exception(err) is False


# ── 3. OllamaTimeoutError raises immediately without retry ──────────────────


class TestNonRetryableTimeout:
    """OllamaTimeoutError is non-retryable (V18.2.19: IQ2_XXS stall)."""

    def test_timeout_raises_immediately(self, no_sleep: Any) -> None:
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3)
        def f() -> str:
            calls["n"] += 1
            raise retry_mod.OllamaTimeoutError("qwen2.5-iq2_xxs", 300)

        with pytest.raises(retry_mod.OllamaTimeoutError) as excinfo:
            f()
        assert calls["n"] == 1, "Timeout must NOT be retried"
        assert "model stall" in str(excinfo.value) or "IQ2_XXS" in str(excinfo.value)

    def test_raw_requests_timeout_classified_non_retryable(self) -> None:
        """A raw requests.exceptions.Timeout is also non-retryable."""
        err = requests.exceptions.Timeout("read timed out")
        assert retry_mod.classify_ollama_exception(err) is False


# ── 4. max_attempts exhaustion raises the last exception ────────────────────


class TestExhaustion:
    """All retries exhausted → last exception is reraised."""

    @_TENACITY_XFAIL
    def test_exhaustion_raises_last_exception(self, no_sleep: Any) -> None:
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=lambda _m, _l: None)
        def f() -> str:
            calls["n"] += 1
            raise requests.exceptions.ConnectionError(f"fail #{calls['n']}")

        with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
            f()
        assert calls["n"] == 3, f"Expected 3 attempts, got {calls['n']}"
        # Should be the LAST exception, with the last call's message.
        assert "fail #3" in str(excinfo.value)

    def test_max_attempts_1_disables_retry(self, no_sleep: Any) -> None:
        """max_attempts=1 means no retries at all."""
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=1)
        def f() -> str:
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("nope")

        with pytest.raises(requests.exceptions.ConnectionError):
            f()
        assert calls["n"] == 1


# ── 5. Jitter produces varying wait times ───────────────────────────────────


class TestJitter:
    """wait_exponential_jitter should NOT produce identical wait times across calls."""

    @_TENACITY_XFAIL
    def test_jitter_produces_varying_waits(self) -> None:
        """20 calls to wait_exponential_jitter on the same attempt should yield >5 distinct values."""
        from tenacity import RetryCallState, wait_exponential_jitter

        w = wait_exponential_jitter(initial=2, max=30, jitter=2)
        state = RetryCallState(None, None, (), {})
        state.attempt_number = 1
        vals = [w(state) for _ in range(20)]
        distinct = set(vals)
        assert len(distinct) >= 5, (
            f"Jitter should produce ≥5 distinct values across 20 calls, got {len(distinct)}"
        )
        # All values should be within [initial - jitter, initial + jitter]
        # i.e. [0, 4] (tenacity clamps at 0).
        assert min(vals) >= 0
        assert max(vals) <= 2 + 2 + 0.01  # initial + jitter + tiny epsilon

    @_TENACITY_XFAIL
    def test_jitter_in_decorator_varies_sleeps(self, captured_sleeps: list[float]) -> None:
        """Across multiple decorator invocations, captured sleep durations should vary.

        Each invocation triggers 2 sleeps (attempt 1 → 2, attempt 2 → 3). Across
        10 invocations = 20 sleeps. With ±2s jitter, we expect significant variation.
        """

        @retry_mod.retry_llm_call(max_attempts=3, initial_wait=2.0, max_wait=30.0, jitter=2.0)
        def f() -> str:
            raise requests.exceptions.ConnectionError("always fails")

        for _ in range(10):
            with pytest.raises(requests.exceptions.ConnectionError):
                f()

        assert len(captured_sleeps) == 20, (
            f"Expected 20 sleeps (10 runs × 2 retries), got {len(captured_sleeps)}"
        )
        distinct = set(captured_sleeps)
        assert len(distinct) >= 5, (
            f"Jitter should produce ≥5 distinct sleep durations, got {len(distinct)}: "
            f"{sorted(distinct)[:5]}"
        )

    @_TENACITY_XFAIL
    def test_exponential_growth_across_attempts(self) -> None:
        """Without jitter, the base wait should grow exponentially (2, 4, 8, 16, 30)."""
        from tenacity import RetryCallState, wait_exponential_jitter

        # Use jitter=0 to isolate the exponential base.
        w = wait_exponential_jitter(initial=2, max=30, jitter=0)
        base_waits = []
        for attempt in range(1, 6):
            state = RetryCallState(None, None, (), {})
            state.attempt_number = attempt
            base_waits.append(w(state))
        # 2, 4, 8, 16, 30 (capped)
        assert base_waits[0] == pytest.approx(2.0)
        assert base_waits[1] == pytest.approx(4.0)
        assert base_waits[2] == pytest.approx(8.0)
        assert base_waits[3] == pytest.approx(16.0)
        assert base_waits[4] == pytest.approx(30.0)  # capped at max


# ── 6. Graceful degradation when tenacity not installed ──────────────────────


class TestGracefulDegradation:
    """When tenacity isn't installed, retry_llm_call falls back to 2-attempt linear."""

    def test_fallback_retries_at_most_twice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """In fallback mode, max_attempts is capped at 2 even if 5 is requested."""
        # Patch _HAS_TENACITY to route to the fallback path. This is the
        # simplest equivalent of "tenacity is not importable" — the public
        # decorator branches on this flag.
        monkeypatch.setattr(retry_mod, "_HAS_TENACITY", False)
        # No-op the linear retry's sleep so the test runs fast.
        monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)

        calls = {"n": 0}

        @retry_mod.retry_llm_call(
            max_attempts=5,  # will be capped to 2 in fallback
            log_callback=lambda _m, _l: None,
        )
        def f() -> str:
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("boom")

        with pytest.raises(requests.exceptions.ConnectionError):
            f()
        assert calls["n"] == 2, (
            f"Fallback should retry exactly once (2 total attempts), got {calls['n']}"
        )

    def test_fallback_still_respects_non_retryable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """In fallback mode, non-retryable exceptions still raise immediately."""
        monkeypatch.setattr(retry_mod, "_HAS_TENACITY", False)
        monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)

        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=5)
        def f() -> str:
            calls["n"] += 1
            raise retry_mod.ModelNotFound404Error("m1", "not found")

        with pytest.raises(retry_mod.ModelNotFound404Error):
            f()
        assert calls["n"] == 1, "Non-retryable must NOT be retried even in fallback"

    def test_fallback_uses_linear_backoff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback sleep durations should be linear (initial_wait × attempt)."""
        monkeypatch.setattr(retry_mod, "_HAS_TENACITY", False)
        sleeps: list[float] = []
        monkeypatch.setattr(retry_mod.time, "sleep", lambda s: sleeps.append(s))

        @retry_mod.retry_llm_call(
            max_attempts=5, initial_wait=3.0, log_callback=lambda _m, _l: None
        )
        def f() -> str:
            raise requests.exceptions.ConnectionError("boom")

        with pytest.raises(requests.exceptions.ConnectionError):
            f()
        # 2 attempts → 1 sleep. Linear: initial_wait * attempt_1 = 3.0 * 1 = 3.0
        assert sleeps == [3.0], f"Expected [3.0], got {sleeps}"

    @_TENACITY_XFAIL
    def test_import_time_warning_when_tenacity_absent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When the module is reloaded with tenacity blocked, a WARNING is logged."""
        # Block tenacity import — Python raises ImportError on `import tenacity`
        # when sys.modules['tenacity'] is None.
        monkeypatch.setitem(sys.modules, "tenacity", None)

        # Phase 2 (task 2.3, random-order determinism): a bare second
        # ``importlib.reload`` in the finally-block RESTORES functionality but
        # re-executes the module — every exception class gets rebound to a
        # NEW class object. Modules that imported ``core.llm.retry`` earlier
        # (e.g. ``core.llm.async_provider``, bound at session import) keep
        # raising the OLD classes while any test importing
        # ``from core.llm.retry import OllamaTimeoutError`` AFTER this test
        # compares against the NEW ones — identity mismatch, order-dependent
        # failure (caught by the ``-p randomly`` smoke). Fix: snapshot the
        # original module namespace and restore it WHOLESALE (exact class
        # identity preserved for every consumer, before or after this test).
        _original_namespace = dict(retry_mod.__dict__)

        # Reload the retry module so it re-evaluates the try/except import.
        with caplog.at_level(logging.WARNING, logger="core.llm.retry"):
            importlib.reload(retry_mod)

        try:
            assert retry_mod._HAS_TENACITY is False, "Reload should detect no tenacity"
            warning_msgs = [r.message for r in caplog.records]
            assert any("tenacity is not installed" in m for m in warning_msgs), (
                f"Expected WARNING about tenacity being absent, got: {warning_msgs}"
            )
        finally:
            # Restore: undo the sys.modules block + put the ORIGINAL module
            # namespace back (same class objects, same functions — identity
            # intact). This MUST run so subsequent tests see the
            # tenacity-enabled version AND the pre-reload class identities.
            monkeypatch.undo()
            retry_mod.__dict__.clear()
            retry_mod.__dict__.update(_original_namespace)
            assert retry_mod._HAS_TENACITY is True, "Restore failed"


# ── 7. OOM context-halving helper ──────────────────────────────────────────


class TestOOMContextHalving:
    """retry_with_oom_context_halving halves num_ctx on OllamaOOMError and retries once."""

    def test_halving_succeeds_on_second_attempt(self) -> None:
        """The helper retries ONCE at halved ctx — the second call must succeed."""
        tried_ctxs: list[int] = []

        def call_fn(ctx: int) -> str:
            tried_ctxs.append(ctx)
            if ctx > 32768:  # only fails at the initial ctx (65536)
                raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")
            return f"ok_at_{ctx}"

        result = retry_mod.retry_with_oom_context_halving(
            call_fn, initial_ctx=65536, log_callback=lambda _m, _l: None
        )
        assert result == "ok_at_32768"
        # Tried 65536 (failed OOM) → halved to 32768 → succeeded.
        assert tried_ctxs == [65536, 32768]

    def test_halving_only_once(self) -> None:
        """The helper retries ONLY ONCE — a second OOM propagates."""
        tried_ctxs: list[int] = []

        def call_fn(ctx: int) -> str:
            tried_ctxs.append(ctx)
            raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")

        with pytest.raises(retry_mod.OllamaOOMError) as excinfo:
            retry_mod.retry_with_oom_context_halving(
                call_fn, initial_ctx=65536, log_callback=lambda _m, _l: None
            )
        # Initial call (65536) failed → halved to 32768 → second call also failed.
        assert tried_ctxs == [65536, 32768]
        # The re-raised exception should be the SECOND one (at ctx=32768).
        assert excinfo.value.num_ctx == 32768

    def test_no_halving_needed_succeeds_first_try(self) -> None:
        calls = {"n": 0}

        def call_fn(ctx: int) -> str:
            calls["n"] += 1
            return f"ok_at_{ctx}"

        result = retry_mod.retry_with_oom_context_halving(
            call_fn, initial_ctx=65536, log_callback=lambda _m, _l: None
        )
        assert result == "ok_at_65536"
        assert calls["n"] == 1

    def test_oom_at_min_ctx_reraises_without_halving(self) -> None:
        """If initial_ctx is already at min_ctx, OOM propagates without halving."""
        calls = {"n": 0}

        def call_fn(ctx: int) -> str:
            calls["n"] += 1
            raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")

        with pytest.raises(retry_mod.OllamaOOMError):
            retry_mod.retry_with_oom_context_halving(
                call_fn,
                initial_ctx=8192,
                min_ctx=8192,
                log_callback=lambda _m, _l: None,
            )
        # Should only have called once (no halving possible).
        assert calls["n"] == 1

    def test_non_oom_exception_propagates_without_halving(self) -> None:
        """Non-OOM exceptions propagate unchanged (no halving)."""
        calls = {"n": 0}

        def call_fn(ctx: int) -> str:
            calls["n"] += 1
            raise ValueError("programming error")

        with pytest.raises(ValueError):
            retry_mod.retry_with_oom_context_halving(
                call_fn, initial_ctx=65536, log_callback=lambda _m, _l: None
            )
        assert calls["n"] == 1

    def test_oom_halving_swallows_log_callback_exception(self) -> None:
        """A buggy log_callback in the OOM-halving wrapper must not break the retry."""
        calls = {"n": 0}

        def call_fn(ctx: int) -> str:
            calls["n"] += 1
            if ctx > 32768:
                raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")
            return f"ok_at_{ctx}"

        def bad_cb(_msg: str, _level: str) -> None:
            raise RuntimeError("log callback crashed")

        # Should succeed despite the log_callback crashing.
        result = retry_mod.retry_with_oom_context_halving(
            call_fn, initial_ctx=65536, log_callback=bad_cb
        )
        assert result == "ok_at_32768"
        assert calls["n"] == 2

    def test_oom_at_min_ctx_swallows_log_callback_exception(self) -> None:
        """Defensive log_callback swallow on the at-min_ctx ERROR path too."""

        def call_fn(ctx: int) -> str:
            raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")

        def bad_cb(_msg: str, _level: str) -> None:
            raise RuntimeError("log callback crashed")

        # The OOM should propagate (not the log callback's RuntimeError).
        with pytest.raises(retry_mod.OllamaOOMError):
            retry_mod.retry_with_oom_context_halving(
                call_fn,
                initial_ctx=8192,
                min_ctx=8192,
                log_callback=bad_cb,
            )

    def test_composes_with_retry_decorator(self, no_sleep: Any) -> None:
        """OOM-halving wrapper composes cleanly with @retry_llm_call.

        The inner function uses @retry_llm_call to handle transient errors;
        the outer wrapper handles OOM by halving ctx. This is the production
        pattern documented in the module migration guide.
        """
        calls = {"n": 0}

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=lambda _m, _l: None)
        def inner_call(ctx: int) -> str:
            calls["n"] += 1
            # First call (ctx=65536): raise OOM (non-retryable for @retry_llm_call)
            # so the OOM-halving wrapper catches it and retries with ctx=32768.
            # Inner call at ctx=32768: transient ConnectionError on attempt 1,
            # then success on attempt 2.
            if ctx == 65536:
                raise retry_mod.OllamaOOMError("m1", ctx, "cuda OOM")
            if ctx == 32768 and calls["n"] <= 2:
                # First attempt at this ctx: fail transiently (retryable).
                raise requests.exceptions.ConnectionError("transient")
            return f"ok_at_{ctx}"

        result = retry_mod.retry_with_oom_context_halving(
            inner_call, initial_ctx=65536, log_callback=lambda _m, _l: None
        )
        assert result == "ok_at_32768"
        # Inner call sequence: 65536 (OOM, 1 attempt), 32768 (ConnectionError x1,
        # then success x1). Total inner calls: 3.
        assert calls["n"] == 3


# ── 8. classify_ollama_exception unit tests ─────────────────────────────────


class TestClassifier:
    """Unit tests for classify_ollama_exception."""

    def test_requests_connection_error_retryable(self) -> None:
        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.ConnectionError("boom")) is True
        )

    def test_requests_timeout_non_retryable(self) -> None:
        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.Timeout("read timed out"))
            is False
        )

    def test_model_not_found_404_non_retryable(self) -> None:
        assert (
            retry_mod.classify_ollama_exception(retry_mod.ModelNotFound404Error("m1", "not found"))
            is False
        )

    def test_ollama_timeout_non_retryable(self) -> None:
        assert retry_mod.classify_ollama_exception(retry_mod.OllamaTimeoutError("m1", 300)) is False

    def test_ollama_oom_non_retryable(self) -> None:
        assert (
            retry_mod.classify_ollama_exception(retry_mod.OllamaOOMError("m1", 65536, "cuda OOM"))
            is False
        )

    def test_http_404_non_retryable(self) -> None:
        class _R:
            status_code = 404

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("404", response=_R()))
            is False
        )

    def test_http_429_retryable(self) -> None:
        class _R:
            status_code = 429

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("429", response=_R()))
            is True
        )

    def test_http_500_retryable(self) -> None:
        class _R:
            status_code = 500

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("500", response=_R()))
            is True
        )

    def test_http_503_retryable(self) -> None:
        class _R:
            status_code = 503

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("503", response=_R()))
            is True
        )

    def test_http_401_non_retryable(self) -> None:
        class _R:
            status_code = 401

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("401", response=_R()))
            is False
        )

    def test_http_400_non_retryable(self) -> None:
        class _R:
            status_code = 400

        assert (
            retry_mod.classify_ollama_exception(requests.exceptions.HTTPError("400", response=_R()))
            is False
        )

    def test_value_error_non_retryable(self) -> None:
        assert retry_mod.classify_ollama_exception(ValueError("bad arg")) is False

    def test_type_error_non_retryable(self) -> None:
        assert retry_mod.classify_ollama_exception(TypeError("bad type")) is False

    def test_keyboard_interrupt_non_retryable(self) -> None:
        assert retry_mod.classify_ollama_exception(KeyboardInterrupt()) is False

    def test_generic_request_exception_retryable(self) -> None:
        """Other requests.RequestException subclasses (ChunkedEncodingError, etc.) are retryable."""
        err = requests.exceptions.ChunkedEncodingError("partial read")
        assert retry_mod.classify_ollama_exception(err) is True

    def test_oom_in_message_non_retryable(self) -> None:
        """A plain RuntimeError mentioning OOM is treated as non-retryable (defensive)."""
        assert retry_mod.classify_ollama_exception(RuntimeError("CUDA out of memory")) is False
        assert (
            retry_mod.classify_ollama_exception(RuntimeError("GPU OOM: allocation failed")) is False
        )

    def test_plain_runtime_error_non_retryable(self) -> None:
        """A plain RuntimeError without OOM signal is non-retryable."""
        assert retry_mod.classify_ollama_exception(RuntimeError("something else")) is False


# ── 9. Log callback invocation ──────────────────────────────────────────────


class TestLogCallback:
    """The log_callback (if provided) is invoked on each retry."""

    @_TENACITY_XFAIL
    def test_log_callback_invoked_on_retry(self, no_sleep: Any) -> None:
        logged: list[tuple[str, str]] = []

        def cb(msg: str, level: str) -> None:
            logged.append((msg, level))

        @retry_mod.retry_llm_call(max_attempts=3, log_callback=cb)
        def f() -> str:
            raise requests.exceptions.ConnectionError("transient")

        with pytest.raises(requests.exceptions.ConnectionError):
            f()
        # 3 attempts → 2 retries → 2 log_callback invocations.
        assert len(logged) == 2
        for msg, level in logged:
            assert level == "WARNING"
            assert "LLM call attempt" in msg
            assert "retrying" in msg

    def test_log_callback_exception_swallowed(self, no_sleep: Any) -> None:
        """A buggy log_callback must not break the retry."""

        def bad_cb(_msg: str, _level: str) -> None:
            raise RuntimeError("log callback crashed")

        @retry_mod.retry_llm_call(max_attempts=2, log_callback=bad_cb)
        def f() -> str:
            raise requests.exceptions.ConnectionError("transient")

        # The retry should still raise the ConnectionError, not the log callback's RuntimeError.
        with pytest.raises(requests.exceptions.ConnectionError):
            f()

    def test_fallback_log_callback_exception_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A buggy log_callback in FALLBACK mode must not break the retry."""
        monkeypatch.setattr(retry_mod, "_HAS_TENACITY", False)
        monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)

        def bad_cb(_msg: str, _level: str) -> None:
            raise RuntimeError("log callback crashed")

        @retry_mod.retry_llm_call(max_attempts=2, log_callback=bad_cb)
        def f() -> str:
            raise requests.exceptions.ConnectionError("transient")

        with pytest.raises(requests.exceptions.ConnectionError):
            f()


# ── 10. Exception class structure ──────────────────────────────────────────


class TestExceptionClasses:
    """The three exception classes carry useful diagnostic attributes."""

    def test_model_not_found_404_attributes(self) -> None:
        exc = retry_mod.ModelNotFound404Error("qwen2.5:latest", "model not found")
        assert exc.model == "qwen2.5:latest"
        assert exc.detail == "model not found"
        assert "qwen2.5:latest" in str(exc)
        assert "ollama pull qwen2.5:latest" in str(exc)
        assert isinstance(exc, RuntimeError)

    def test_ollama_timeout_attributes(self) -> None:
        original = requests.exceptions.Timeout("read timed out")
        exc = retry_mod.OllamaTimeoutError("m1", 300, original=original)
        assert exc.model == "m1"
        assert exc.timeout == 300
        assert exc.original is original
        assert "IQ2_XXS" in str(exc)
        assert isinstance(exc, RuntimeError)

    def test_ollama_oom_attributes(self) -> None:
        exc = retry_mod.OllamaOOMError("m1", 65536, "cuda OOM")
        assert exc.model == "m1"
        assert exc.num_ctx == 65536
        assert exc.detail == "cuda OOM"
        assert "65536" in str(exc)
        assert isinstance(exc, RuntimeError)
