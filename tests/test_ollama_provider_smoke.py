"""V18.4 (Phase 2) — OllamaProvider.smoke_test() tests.

Tests the LLM-side twin of the embedder smoke-test (item 2.3 of the Phase 2
plan). ``OllamaProvider.smoke_test()`` probes ``/api/generate`` with a
1-token ``"hello"`` request and returns ``bool`` — never raises.

Coverage:
  - Returns True on a valid (non-empty) response.
  - Returns False on an empty response (broken quant / Modelfile).
  - Returns False on HTTP 404 (model not pulled).
  - Returns False on Timeout (server stalled / cold load).
  - Returns False on ConnectionError (Ollama not running).
  - Returns False on any other unexpected exception.
  - The probe payload does NOT set ``presence_penalty`` (V18.2.42 hard
    constraint — setting it to 0.0 would activate thinking mode).
  - The probe uses ``num_predict=1`` and a tiny ``num_ctx=4096`` (fast).
  - The timeout is capped at ``min(self.timeout, 60)`` (cold-load safety).

Uses ``unittest.mock.patch`` on ``safe_ollama_request`` so no real Ollama
is needed.

Run: ``pytest tests/test_ollama_provider_smoke.py -v``
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.llm.llm_provider import OllamaProvider


@pytest.fixture
def provider():
    """An OllamaProvider with a no-op log callback (no supervisor side-effects)."""
    return OllamaProvider(
        model="test-model:latest",
        base_url="http://localhost:11434",
        timeout=300,
        log_callback=lambda msg, level="INFO": None,
    )


# ── 1. Happy path ───────────────────────────────────────────────────────────


class TestSmokeTestHappyPath:
    def test_returns_true_on_valid_response(self, provider):
        """A non-empty response → True."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            ok = provider.smoke_test()
        assert ok is True
        mock_req.assert_called_once()

    def test_returns_true_on_longer_response(self, provider):
        """A multi-char response → True."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "Hello world", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp):
            ok = provider.smoke_test()
        assert ok is True


# ── 2. Failure paths (each returns False, never raises) ────────────────────


class TestSmokeTestFailurePaths:
    def test_returns_false_on_empty_response(self, provider):
        """Empty/whitespace response → False (broken quant / Modelfile)."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "   ", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp):
            ok = provider.smoke_test()
        assert ok is False

    def test_returns_false_on_missing_response_key(self, provider):
        """Response JSON without 'response' key → False."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"done": True}  # no "response" field
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp):
            ok = provider.smoke_test()
        assert ok is False

    def test_returns_false_on_404(self, provider):
        """HTTP 404 (model not pulled) → False, with actionable log."""
        resp_404 = MagicMock()
        resp_404.status_code = 404
        http_err = requests.exceptions.HTTPError(response=resp_404)
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   side_effect=http_err):
            ok = provider.smoke_test()
        assert ok is False

    def test_returns_false_on_timeout(self, provider):
        """Timeout → False (server stalled / cold load)."""
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   side_effect=requests.exceptions.Timeout("60s")):
            ok = provider.smoke_test()
        assert ok is False

    def test_returns_false_on_connection_error(self, provider):
        """ConnectionError (Ollama not running) → False."""
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   side_effect=requests.exceptions.ConnectionError("refused")):
            ok = provider.smoke_test()
        assert ok is False

    def test_returns_false_on_unexpected_exception(self, provider):
        """Any other exception → False (defensive catch-all)."""
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   side_effect=ValueError("unexpected")):
            ok = provider.smoke_test()
        assert ok is False

    def test_never_raises_on_any_failure(self, provider):
        """smoke_test must NEVER raise — callers use it in a boolean context."""
        for exc in [
            requests.exceptions.Timeout("t"),
            requests.exceptions.ConnectionError("c"),
            ValueError("v"),
            RuntimeError("r"),
        ]:
            with patch("core.llm.ollama_provider.safe_ollama_request",
                       side_effect=exc):
                # Must not raise
                result = provider.smoke_test()
                assert isinstance(result, bool)


# ── 3. Payload constraints (hard constraints preserved) ────────────────────


class TestSmokeTestPayloadConstraints:
    """The probe payload must respect the V18.2.42+ hard constraints."""

    def test_does_not_set_presence_penalty(self, provider):
        """CRITICAL: presence_penalty must NOT be in the payload options.

        Setting presence_penalty=0.0 would activate Qwen3 thinking mode
        (the V18.2.41 2/10 regression) AND trip the ThinkingModeViolation
        guard. The smoke-test lets the Modelfile decide (1.5 = Instruct).
        """
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert "presence_penalty" not in payload.get("options", {}), (
            "smoke_test must not set presence_penalty (V18.2.42 hard constraint)"
        )

    def test_uses_num_predict_one(self, provider):
        """num_predict=1 — minimal token cost for the probe."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert payload["options"]["num_predict"] == 1

    def test_uses_tiny_context(self, provider):
        """num_ctx=4096 — fast KV cache allocation for the probe."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert payload["options"]["num_ctx"] == 4096

    def test_uses_greedy_temperature(self, provider):
        """temperature=0.0 — most deterministic probe."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert payload["options"]["temperature"] == 0.0

    def test_sends_empty_system_prompt(self, provider):
        """system='' — override the Modelfile's system prompt (V18.2.37e fix)."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert payload.get("system") == ""

    def test_uses_keep_alive(self, provider):
        """keep_alive is set (models stay resident — V18.1)."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert "keep_alive" in payload

    def test_targets_correct_endpoint(self, provider):
        """The probe hits /api/generate (not /api/embeddings)."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        call_args = mock_req.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/api/generate" in url


# ── 4. Timeout cap (cold-load safety) ──────────────────────────────────────


class TestSmokeTestTimeoutCap:
    """The probe timeout is capped so a cold model load can't stall preflight."""

    def test_timeout_capped_at_60_when_provider_timeout_higher(self, provider):
        """Provider timeout=300 → probe uses min(300, 60) = 60."""
        assert provider.timeout == 300
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        used_timeout = mock_req.call_args.kwargs["timeout"]
        assert used_timeout == 60

    def test_timeout_uses_provider_value_when_lower(self):
        """Provider timeout=30 → probe uses min(30, 60) = 30."""
        p = OllamaProvider(
            model="m:latest", base_url="http://localhost:11434",
            timeout=30, log_callback=lambda msg, level="INFO": None,
        )
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            p.smoke_test()
        used_timeout = mock_req.call_args.kwargs["timeout"]
        assert used_timeout == 30

    def test_explicit_timeout_override(self, provider):
        """An explicit timeout= arg to smoke_test overrides the cap."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test(timeout=15)
        used_timeout = mock_req.call_args.kwargs["timeout"]
        assert used_timeout == 15

    def test_iq2_s_timeout_exclusion_preserved(self):
        """The IQ2_S 300s-exclusion hard constraint is NOT violated by smoke_test.

        smoke_test caps at min(self.timeout, 60) — it never uses the full
        300s IQ2_S timeout. This is intentional: a cold IQ2_S load (~30s)
        fits within 60s, but preflight should never stall for 5+ minutes.
        """
        p = OllamaProvider(
            model="Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest",
            base_url="http://localhost:11434",
            timeout=300,  # IQ2_S uses the 300s timeout for real calls
            log_callback=lambda msg, level="INFO": None,
        )
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "hi", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            p.smoke_test()
        used_timeout = mock_req.call_args.kwargs["timeout"]
        # smoke_test caps at 60, NOT 300 — preflight stays fast.
        assert used_timeout == 60
        assert used_timeout < 300


# ── 5. Custom prompt ────────────────────────────────────────────────────────


class TestSmokeTestCustomPrompt:
    def test_custom_prompt_is_sent(self, provider):
        """A custom probe prompt is passed through to the payload."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "x", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test(prompt="Say OK")
        payload = mock_req.call_args.kwargs["json"]
        assert payload["prompt"] == "Say OK"

    def test_default_prompt_is_hello(self, provider):
        """The default probe prompt is 'hello' (tiny, universally answerable)."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"response": "x", "done": True}
        with patch("core.llm.ollama_provider.safe_ollama_request",
                   return_value=fake_resp) as mock_req:
            provider.smoke_test()
        payload = mock_req.call_args.kwargs["json"]
        assert payload["prompt"] == "hello"
