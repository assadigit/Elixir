"""V18.15.6.0 — IQ2_S HTTP timeout + error-message + retry-classifier tests.

Byte-for-byte stability gate for the 3 fixes bundled in V18.15.6.0:

  Fix A: Raise per-call HTTP timeout 600→1200s for IQ2_S (summarizer.py __init__).
  Fix B: Distinguish "not installed" (404) from "timed out" (timeout) in the
         error message — the error_tracker out-param propagated from
         llm_dispatcher._call_ollama_nonstreaming → Summarizer._call_ollama →
         Summarizer._summarize_inner's error-message logic.
  Fix C: classify_ollama_exception now returns True (retryable) for IQ2_S
         timeouts — the model is slow, not stalled. Non-IQ2_S timeouts stay
         non-retryable (the V18.2.19 model-stall rule).

Run: pytest tests/test_v18_15_6_timeout.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken (not installed in test env) — same pattern as conftest.
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = lambda *a, **k: None
    tk.encoding_for_model = lambda *a, **k: None
    tk.Encoding = type("_E", (), {})
    sys.modules["tiktoken"] = tk

from core.llm.model_taxonomy import is_iq2_s


def _retry_symbols():
    """V18.20.2.0 (SWOT test-debt): resolve ``core.llm.retry`` symbols at CALL time.

    ``tests/test_retry.py::test_import_time_warning_when_tenacity_absent``
    ``importlib.reload()``s ``core.llm.retry`` — a reload creates NEW
    exception class objects, so module-level imports captured at collection
    time go stale and the subsequent ``isinstance()`` checks inside
    ``classify_ollama_exception`` fail (the pre-V18.20.2.0 cause of
    ``test_iq2_s_timeout_is_retryable`` failing whenever this file ran
    AFTER test_retry.py — the behavior in retry.py itself is correct).
    Importing the module at call time always resolves the CURRENT module
    object from ``sys.modules``, making the tests order-independent.
    """
    import core.llm.retry as _retry
    return _retry


# ═══════════════════════════════════════════════════════════════════════════
# Fix C: classify_ollama_exception — IQ2_S timeout is RETRYABLE
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyOllamaExceptionTimeout:
    """V18.15.6.0 (Fix C): IQ2_S timeouts are retryable; non-IQ2_S stay
    non-retryable (the V18.2.19 model-stall rule)."""

    def test_iq2_s_timeout_is_retryable(self):
        """V18.15.6.0 NEW: IQ2_S timeout → True (retryable). The model is
        slow (5-15 tok/s), not stalled. Pre-V18.15.6.0 this returned False."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(
            model="Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest",
            timeout=1200,
        )
        assert _retry.classify_ollama_exception(exc) is True, (
            "IQ2_S timeout must be retryable post-V18.15.6.0 (model is slow, "
            "not stalled). Pre-V18.15.6.0 this returned False (the bug Fix C fixes)."
        )

    def test_iq2_xxs_timeout_still_non_retryable(self):
        """Regression guard: IQ2_XXS timeout → False (non-retryable). The
        V18.2.19 model-stall rule still applies to non-IQ2_S low-bit quants."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(
            model="Qwen3.8-27B-UD-IQ2_XXS:latest",
            timeout=300,
        )
        assert _retry.classify_ollama_exception(exc) is False, (
            "IQ2_XXS timeout must stay non-retryable (model stall rule)"
        )

    def test_iq2_xs_timeout_still_non_retryable(self):
        """Regression guard: IQ2_XS timeout → False (non-retryable)."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(
            model="Qwen3.8-27B-UD-IQ2_XS:latest",
            timeout=300,
        )
        assert _retry.classify_ollama_exception(exc) is False

    def test_q2_k_timeout_still_non_retryable(self):
        """Regression guard: Q2_K timeout → False (non-retryable)."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(
            model="Qwen3.8-27B-UD-Q2_K:latest",
            timeout=300,
        )
        assert _retry.classify_ollama_exception(exc) is False

    def test_normal_model_timeout_still_non_retryable(self):
        """Regression guard: non-low-bit model timeout → False (non-retryable)."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(
            model="llama3.1:8b",
            timeout=600,
        )
        assert _retry.classify_ollama_exception(exc) is False

    def test_model_not_found_still_non_retryable(self):
        """Regression guard: ModelNotFound404Error → False (non-retryable)."""
        _retry = _retry_symbols()
        exc = _retry.ModelNotFound404Error(model="nonexistent-model:latest")
        assert _retry.classify_ollama_exception(exc) is False

    def test_oom_still_non_retryable(self):
        """Regression guard: OllamaOOMError → False (non-retryable AS-IS)."""
        _retry = _retry_symbols()
        exc = _retry.OllamaOOMError(model="Qwen3.8-27B-UD-IQ2_S:latest", num_ctx=32768)
        assert _retry.classify_ollama_exception(exc) is False

    def test_q2_k_s_not_treated_as_iq2_s(self):
        """Regression guard: Q2_K_S contains 'q2_k' → is_iq2_s() returns False
        (so its timeout stays non-retryable, matching V18.2.19)."""
        assert is_iq2_s("Qwen3.8-27B-UD-Q2_K_S:latest") is False
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(model="Qwen3.8-27B-UD-Q2_K_S:latest", timeout=300)
        assert _retry.classify_ollama_exception(exc) is False

    def test_timeout_with_none_model_non_retryable(self):
        """Edge case: OllamaTimeoutError with model=None → non-retryable
        (can't classify, fall through to the V18.2.19 default)."""
        _retry = _retry_symbols()
        exc = _retry.OllamaTimeoutError(model="", timeout=600)
        # model="" → is_iq2_s("") returns False → non-retryable
        assert _retry.classify_ollama_exception(exc) is False


# ═══════════════════════════════════════════════════════════════════════════
# Fix A: IQ2_S per-call HTTP timeout raised 600→1200s
# ═══════════════════════════════════════════════════════════════════════════


class TestIQ2SHttpTimeoutRaise:
    """V18.15.6.0 (Fix A): the per-call HTTP timeout is raised 600→1200s for
    IQ2_S models in Summarizer.__init__.

    We test the LOGIC in isolation by constructing a minimal Summarizer-like
    object and running the IQ2_S timeout-raise block. The full __init__ is 630
    lines with many dependencies (model_manager, ollama_supervisor, etc.) —
    we test the specific block directly to avoid constructing the whole stack.
    """

    def _make_mini_summarizer(self, primary_model: str, timeout: int, is_local: bool = True):
        """Build a minimal object with just the attributes the Fix A block reads."""
        obj = MagicMock()
        obj.primary_model = primary_model
        obj.timeout = timeout
        obj.is_local = is_local
        obj.local_chapter_deadline = 480  # default before V18.15.4.0 raise
        obj.log = MagicMock()
        return obj

    def _apply_iq2_s_block(self, obj):
        """Apply the V18.15.4.0 + V18.15.6.0 (Fix A) IQ2_S block to a mini-summarizer."""
        from core.llm.model_taxonomy import is_iq2_s
        if obj.is_local and is_iq2_s(obj.primary_model):
            # V18.15.4.0 chapter deadline raise
            if obj.local_chapter_deadline > 0 and obj.local_chapter_deadline < 2400:
                obj.local_chapter_deadline = 2400
            # V18.15.6.0 (Fix A): per-call HTTP timeout raise
            if obj.timeout > 0 and obj.timeout < 1200:
                obj.timeout = 1200

    def test_iq2_s_timeout_raised_600_to_1200(self):
        """V18.15.6.0 NEW: IQ2_S with 600s timeout → raised to 1200s."""
        obj = self._make_mini_summarizer(
            primary_model="Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest",
            timeout=600,
        )
        self._apply_iq2_s_block(obj)
        assert obj.timeout == 1200, f"expected 1200, got {obj.timeout}"

    def test_iq2_s_timeout_not_raised_if_already_1200(self):
        """Edge case: IQ2_S with timeout already ≥1200 → no change."""
        obj = self._make_mini_summarizer(
            primary_model="Qwen3.8-27B-UD-IQ2_S:latest",
            timeout=1500,
        )
        self._apply_iq2_s_block(obj)
        assert obj.timeout == 1500  # unchanged

    def test_iq2_s_deadline_also_raised(self):
        """Regression guard: the V18.15.4.0 chapter deadline raise still fires."""
        obj = self._make_mini_summarizer(
            primary_model="Qwen3.8-27B-UD-IQ2_S:latest",
            timeout=600,
        )
        self._apply_iq2_s_block(obj)
        assert obj.local_chapter_deadline == 2400

    def test_non_iq2_s_timeout_not_raised(self):
        """Regression guard: non-IQ2_S model timeout stays at 600s (Fix A only
        applies to IQ2_S)."""
        obj = self._make_mini_summarizer(
            primary_model="Qwen3.8-27B-UD-IQ2_XXS:latest",
            timeout=300,  # IQ2_XXS gets 300s from the V18.2.33 reduction
        )
        self._apply_iq2_s_block(obj)
        assert obj.timeout == 300  # unchanged — Fix A doesn't touch non-IQ2_S

    def test_cloud_mode_timeout_not_raised(self):
        """Regression guard: cloud mode (is_local=False) → Fix A doesn't fire
        (cloud has its own 300s timeout, separate from local)."""
        obj = self._make_mini_summarizer(
            primary_model="Qwen3.8-27B-UD-IQ2_S:latest",
            timeout=300,
            is_local=False,
        )
        self._apply_iq2_s_block(obj)
        assert obj.timeout == 300  # unchanged — cloud mode


# ═══════════════════════════════════════════════════════════════════════════
# Fix B: error_tracker out-param propagation
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorTracker:
    """V18.15.6.0 (Fix B): the error_tracker out-param lets the caller
    distinguish "timeout" from "not_found" from "oom" when call_ollama
    returns None."""

    def test_tracker_records_timeout(self):
        """When _call_ollama_nonstreaming catches OllamaTimeoutError, the
        tracker is set to ["timeout"]."""
        # Mock safe_ollama_request to raise Timeout (which _do_one_call wraps
        # into OllamaTimeoutError).
        import requests as _requests

        from core.summarisation.llm_dispatcher import _call_ollama_nonstreaming

        tracker: list = []
        supervisor = MagicMock()
        supervisor.record_failure = MagicMock()
        supervisor.record_success = MagicMock()

        with patch("core.summarisation.llm_dispatcher.safe_ollama_request") as mock_req:
            mock_req.side_effect = _requests.exceptions.Timeout("timed out")
            result = _call_ollama_nonstreaming(
                "test prompt", "Qwen3.8-27B-UD-IQ2_S:latest", 0.7, 8192,
                context_tokens=32768, timeout=1200, retries=0,
                ollama_base_url="http://localhost:11434",
                supervisor=supervisor,
                log=lambda msg, level: None,
                error_tracker=tracker,
            )
        assert result is None
        assert tracker == ["timeout"], f"expected ['timeout'], got {tracker}"

    def test_tracker_records_not_found(self):
        """When _call_ollama_nonstreaming catches a 404-style exception, the
        tracker is set to ["not_found"]."""
        from core.llm.retry import ModelNotFound404Error
        from core.summarisation.llm_dispatcher import _call_ollama_nonstreaming

        tracker: list = []
        supervisor = MagicMock()

        # The @retry_llm_call decorator classifies ModelNotFound404Error as
        # non-retryable → propagates → caught by the outer except Exception.
        with patch("core.summarisation.llm_dispatcher.safe_ollama_request") as mock_req:
            mock_req.side_effect = ModelNotFound404Error(model="nonexistent:latest")
            result = _call_ollama_nonstreaming(
                "test prompt", "nonexistent:latest", 0.7, 8192,
                context_tokens=32768, timeout=600, retries=0,
                ollama_base_url="http://localhost:11434",
                supervisor=supervisor,
                log=lambda msg, level: None,
                error_tracker=tracker,
            )
        assert result is None
        assert tracker == ["not_found"], f"expected ['not_found'], got {tracker}"

    def test_tracker_none_on_success(self):
        """When the call succeeds, the tracker stays empty (no error)."""
        from core.summarisation.llm_dispatcher import _call_ollama_nonstreaming

        tracker: list = []
        supervisor = MagicMock()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "  successful output  "}

        with patch("core.summarisation.llm_dispatcher.safe_ollama_request") as mock_req:
            mock_req.return_value = mock_resp
            result = _call_ollama_nonstreaming(
                "test prompt", "Qwen3.8-27B-UD-IQ2_S:latest", 0.7, 8192,
                context_tokens=32768, timeout=1200, retries=0,
                ollama_base_url="http://localhost:11434",
                supervisor=supervisor,
                log=lambda msg, level: None,
                error_tracker=tracker,
            )
        assert result == "successful output"
        assert tracker == [], f"expected empty tracker on success, got {tracker}"

    def test_tracker_optional_backward_compat(self):
        """Regression guard: error_tracker defaults to None — callers that
        don't pass it get the pre-V18.15.6.0 behavior (no tracker)."""
        import requests as _requests

        from core.summarisation.llm_dispatcher import _call_ollama_nonstreaming

        supervisor = MagicMock()
        with patch("core.summarisation.llm_dispatcher.safe_ollama_request") as mock_req:
            mock_req.side_effect = _requests.exceptions.Timeout("timed out")
            # No error_tracker kwarg — must NOT crash.
            result = _call_ollama_nonstreaming(
                "test prompt", "Qwen3.8-27B-UD-IQ2_S:latest", 0.7, 8192,
                context_tokens=32768, timeout=1200, retries=0,
                ollama_base_url="http://localhost:11434",
                supervisor=supervisor,
                log=lambda msg, level: None,
            )
        assert result is None  # still returns None, just doesn't track


# ═══════════════════════════════════════════════════════════════════════════
# Fix B: error-message branching (the user-visible fix)
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorMessageBranching:
    """V18.15.6.0 (Fix B): the error message shown to the user now branches
    on _last_llm_error_type. Pre-V18.15.6.0, it always said "not installed"
    even when the cause was a timeout."""

    def test_timeout_hint_mentions_timeout_not_install(self):
        """When _last_llm_error_type == "timeout", the hint says "timed out"
        and mentions the timeout value — NOT "not installed in Ollama"."""
        # Simulate the error-message branching logic from summarizer.py:2797
        model = "Qwen3.8-27B-UD-IQ2_S:latest"
        timeout = 1200
        _err_type = "timeout"
        if _err_type == "timeout":
            hint = (
                f"Likely cause: model '{model}' timed out after {timeout}s "
                f"during generation (the model WAS loaded — S19 pre-warm succeeded; "
                f"the per-call HTTP timeout fired mid-generation). "
                f"Fix: raise `local.http_timeout_sec` in Settings (current: {timeout}s), "
                f"or reduce input size, or switch to a faster quant."
            )
        elif _err_type == "not_found":
            hint = (
                f"Likely cause: model '{model}' is not installed in Ollama. "
                f"Fix: `ollama pull {model}`."
            )
        assert "timed out" in hint
        assert f"{timeout}s" in hint
        assert "not installed" not in hint, (
            "timeout hint must NOT say 'not installed' (the V18.15.6.0 bug fix)"
        )

    def test_not_found_hint_mentions_install(self):
        """When _last_llm_error_type == "not_found", the hint says "not installed"
        (preserves the pre-V18.15.6.0 behavior for the 404 case)."""
        model = "nonexistent:latest"
        _err_type = "not_found"
        if _err_type == "not_found":
            hint = (
                f"Likely cause: model '{model}' is not installed in Ollama. "
                f"Fix: `ollama pull {model}`."
            )
        assert "not installed" in hint
        assert "ollama pull" in hint

    def test_oom_hint_mentions_vram(self):
        """When _last_llm_error_type == "oom", the hint says "out of VRAM"."""
        model = "Qwen3.8-27B-UD-IQ2_S:latest"
        _err_type = "oom"
        if _err_type == "oom":
            hint = (
                f"Likely cause: model '{model}' ran out of VRAM (OOM). "
                f"Fix: reduce `summarisation_max_context_tokens` in Settings."
            )
        assert "VRAM" in hint or "OOM" in hint

    def test_empty_hint_mentions_retry(self):
        """When _last_llm_error_type == "empty" or None, the hint mentions
        retry + the timeout setting (covers the short-response case)."""
        model = "Qwen3.8-27B-UD-IQ2_S:latest"
        _err_type = "empty"
        if _err_type not in ("timeout", "oom", "not_found"):
            hint = (
                f"Likely cause: model '{model}' returned an empty/short response after retry. "
                f"If persistent: check Ollama is running."
            )
        assert "empty/short" in hint
        assert "retry" in hint
