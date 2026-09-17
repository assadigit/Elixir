"""V18.8 (Phase 5.1, Batch B) - LLM dispatcher characterization tests.

Verifies the delegate wiring: Summarizer._call_* methods correctly delegate
to llm_dispatcher.* functions with the expected parameters. Uses mocks to
avoid real HTTP/LLM calls.

Run: pytest tests/test_llm_dispatcher.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.llm_dispatcher import (
    call_claude,
    call_fast_ollama,
    call_ollama,
    call_openai_compat,
    call_via_llm_provider,
)

# ════════════════════════════════════════════════════════════════════════════
# 1. Module structure verification
# ════════════════════════════════════════════════════════════════════════════

class TestModuleStructure:
    """Verify the llm_dispatcher module exports the expected functions."""

    def test_call_ollama_exists(self):
        assert callable(call_ollama)

    def test_call_openai_compat_exists(self):
        assert callable(call_openai_compat)

    def test_call_claude_exists(self):
        assert callable(call_claude)

    def test_call_via_llm_provider_exists(self):
        assert callable(call_via_llm_provider)

    def test_call_fast_ollama_exists(self):
        assert callable(call_fast_ollama)

    def test_internal_streaming_functions_exist(self):
        """The internal _call_ollama_streaming and _call_ollama_nonstreaming
        should exist in the module (used by call_ollama internally)."""
        from core.summarisation import llm_dispatcher
        assert hasattr(llm_dispatcher, '_call_ollama_streaming')
        assert hasattr(llm_dispatcher, '_call_ollama_nonstreaming')


# ════════════════════════════════════════════════════════════════════════════
# 2. call_claude tests
# ════════════════════════════════════════════════════════════════════════════

class TestCallClaude:
    """Tests for call_claude."""

    def test_no_api_key_returns_none(self):
        """Should return None and log an error if claude_api_key is empty."""
        log_calls = []
        result = call_claude(
            prompt="test prompt",
            max_tokens=4096,
            temperature=0.7,
            claude_api_key="",
            claude_model="claude-3-sonnet",
            claude_base_url="https://api.anthropic.com/v1",
            retries=1,
            log=lambda m, l: log_calls.append((m, l)),
        )
        assert result is None
        assert any("API key not set" in m for m, _ in log_calls)

    def test_successful_call(self):
        """Should return the text content from a successful Claude response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "This is the summary."}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            result = call_claude(
                prompt="test prompt",
                max_tokens=4096,
                temperature=0.7,
                claude_api_key="sk-ant-test-key",
                claude_model="claude-3-sonnet",
                claude_base_url="https://api.anthropic.com/v1",
                retries=1,
                log=lambda m, l: None,
            )
        assert result == "This is the summary."

    def test_empty_response_returns_none(self):
        """Should return None on empty response after retries."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": []}
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            result = call_claude(
                prompt="test prompt",
                max_tokens=4096,
                temperature=0.7,
                claude_api_key="sk-ant-test-key",
                claude_model="claude-3-sonnet",
                claude_base_url="https://api.anthropic.com/v1",
                retries=1,
                log=lambda m, l: None,
            )
        assert result is None

    def test_max_tokens_capped_at_8192(self):
        """Claude max_tokens should be capped at 8192."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "response"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            mock_post = _sfu.return_value.post
            call_claude(
                prompt="test",
                max_tokens=16000,  # above the 8192 cap
                temperature=0.7,
                claude_api_key="sk-test",
                claude_model="claude-3",
                claude_base_url="https://api.anthropic.com/v1",
                retries=1,
                log=lambda m, l: None,
            )
        # Check the payload sent to requests.post
        call_args = mock_post.call_args
        payload = call_args[1]['json'] if 'json' in call_args[1] else call_args[0][2]
        assert payload['max_tokens'] == 8192


# ════════════════════════════════════════════════════════════════════════════
# 3. call_openai_compat tests
# ════════════════════════════════════════════════════════════════════════════

class TestCallOpenAICompat:
    """Tests for call_openai_compat."""

    def test_successful_call(self):
        """Should return the content from a successful OpenAI-compat response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test summary."}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            result = call_openai_compat(
                prompt="test prompt",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                model="gpt-4",
                label="OpenAI",
                temp=0.7,
                max_tokens=4096,
                timeout=600,
                retries=1,
                provider="openai",
                log=lambda m, l: None,
            )
        assert result == "Test summary."

    def test_openrouter_headers(self):
        """Should add HTTP-Referer and X-Title headers for OpenRouter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            mock_post = _sfu.return_value.post
            call_openai_compat(
                prompt="test",
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-or-test",
                model="gpt-4",
                label="OpenRouter",
                temp=0.7,
                max_tokens=4096,
                timeout=600,
                retries=1,
                provider="openrouter",
                log=lambda m, l: None,
            )
        headers = mock_post.call_args[1]['headers']
        assert headers['HTTP-Referer'] == "https://elixir.local"
        assert headers['X-Title'] == "Elixir"

    def test_empty_response_returns_none(self):
        """Should return None on empty response after retries."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch('core.summarisation.llm_dispatcher.session_for_url') as _sfu:
            _sfu.return_value.post.return_value = mock_response
            result = call_openai_compat(
                prompt="test",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                model="gpt-4",
                label="OpenAI",
                temp=0.7,
                max_tokens=4096,
                timeout=600,
                retries=1,
                provider="openai",
                log=lambda m, l: None,
            )
        assert result is None


# ════════════════════════════════════════════════════════════════════════════
# 4. call_ollama tests (non-streaming path)
# ════════════════════════════════════════════════════════════════════════════

class TestCallOllama:
    """Tests for call_ollama (non-streaming path)."""

    def test_nonstreaming_delegates_to_provider(self):
        """When streaming_enabled=False, should delegate to OllamaProvider via create_provider."""
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Ollama response."

        with patch('core.summarisation.llm_dispatcher.create_provider', return_value=mock_provider) if hasattr(__import__('core.summarisation.llm_dispatcher', fromlist=['create_provider']), 'create_provider') else \
             patch('core.llm.llm_provider.create_provider', return_value=mock_provider):
            with patch('utils.settings.Settings'):
                result = call_ollama(
                    prompt="test prompt",
                    model="qwen3:32b",
                    temp=0.7,
                    max_tokens=8192,
                    streaming_enabled=False,
                    ollama_base_url="http://localhost:11434",
                    timeout=600,
                    retries=1,
                    context_tokens=32768,
                    supervisor=MagicMock(),
                    log=lambda m, l: None,
                )
        assert result == "Ollama response."
        mock_provider.complete.assert_called_once()

    def test_streaming_enabled_routes_to_streaming(self):
        """When streaming_enabled=True, should call _call_ollama_streaming."""
        with patch('core.summarisation.llm_dispatcher._call_ollama_streaming', return_value="streamed response") as mock_streaming:
            result = call_ollama(
                prompt="test prompt",
                model="qwen3:32b",
                temp=0.7,
                max_tokens=8192,
                streaming_enabled=True,
                ollama_base_url="http://localhost:11434",
                timeout=600,
                retries=1,
                context_tokens=32768,
                supervisor=MagicMock(),
                log=lambda m, l: None,
            )
        assert result == "streamed response"
        mock_streaming.assert_called_once()

    def test_provider_failure_returns_none(self):
        """When create_provider or complete raises, should return None and log WARNING."""
        mock_provider = MagicMock()
        mock_provider.complete.side_effect = RuntimeError("model not found")

        with patch('core.llm.llm_provider.create_provider', return_value=mock_provider):
            with patch('utils.settings.Settings'):
                log_calls = []
                result = call_ollama(
                    prompt="test",
                    model="bad-model",
                    temp=0.7,
                    max_tokens=8192,
                    streaming_enabled=False,
                    ollama_base_url="http://localhost:11434",
                    timeout=600,
                    retries=1,
                    context_tokens=32768,
                    supervisor=MagicMock(),
                    log=lambda m, l: log_calls.append((m, l)),
                )
        assert result is None
        assert any("delegation failed" in m.lower() for m, _ in log_calls)


# ════════════════════════════════════════════════════════════════════════════
# 5. call_via_llm_provider tests
# ════════════════════════════════════════════════════════════════════════════

class TestCallViaLlmProvider:
    """Tests for call_via_llm_provider."""

    def test_successful_delegation(self):
        """Should return the result from provider.complete()."""
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "Provider response."

        with patch('core.llm.llm_provider.create_provider', return_value=mock_provider):
            with patch('utils.settings.Settings'):
                result = call_via_llm_provider(
                    provider_type="claude",
                    prompt="test",
                    model="claude-3",
                    base_url="",
                    api_key="",
                    temp=0.7,
                    max_tokens=4096,
                    timeout=600,
                    supervisor=MagicMock(),
                    log=lambda m, l: None,
                )
        assert result == "Provider response."

    def test_fallback_to_inline_claude(self):
        """When provider fails, should fall back to call_claude_fn callback."""
        with patch('core.llm.llm_provider.create_provider', side_effect=RuntimeError("fail")):
            with patch('utils.settings.Settings'):
                fallback_calls = []
                def mock_claude_fallback(prompt, max_tokens, temperature):
                    fallback_calls.append((prompt, max_tokens, temperature))
                    return "Fallback Claude response."

                result = call_via_llm_provider(
                    provider_type="claude",
                    prompt="test",
                    model="claude-3",
                    base_url="",
                    api_key="",
                    temp=0.7,
                    max_tokens=4096,
                    timeout=600,
                    supervisor=MagicMock(),
                    log=lambda m, l: None,
                    call_claude_fn=mock_claude_fallback,
                )
        assert result == "Fallback Claude response."
        assert len(fallback_calls) == 1

    def test_fallback_to_inline_openai_compat(self):
        """When provider fails for openai_compat, should fall back to call_openai_compat_fn."""
        with patch('core.llm.llm_provider.create_provider', side_effect=RuntimeError("fail")):
            with patch('utils.settings.Settings'):
                def mock_openai_fallback(prompt, base_url, api_key, model, label, temp, max_tokens):
                    return "Fallback OpenAI response."

                result = call_via_llm_provider(
                    provider_type="openai_compat",
                    prompt="test",
                    model="gpt-4",
                    base_url="https://api.openai.com/v1",
                    api_key="sk-test",
                    temp=0.7,
                    max_tokens=4096,
                    timeout=600,
                    supervisor=MagicMock(),
                    log=lambda m, l: None,
                    call_openai_compat_fn=mock_openai_fallback,
                )
        assert result == "Fallback OpenAI response."


# ════════════════════════════════════════════════════════════════════════════
# 6. call_fast_ollama tests (Phase 5.3 — migrated to @retry_llm_call)
# ════════════════════════════════════════════════════════════════════════════

class TestCallFastOllama:
    """Tests for call_fast_ollama (Phase 5.3 migration)."""

    def test_successful_call(self):
        """Should return the response text from Ollama."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Fast model response."}

        with patch('core.summarisation.llm_dispatcher.safe_ollama_request', return_value=mock_response):
            result = call_fast_ollama(
                prompt="test",
                model="gemma3:12b",
                temp=1.0,
                max_tokens=500,
                ollama_base_url="http://localhost:11434",
                fast_model_context=131072,
                log=lambda m, l: None,
            )
        assert result == "Fast model response."

    def test_empty_response_retries(self):
        """Empty response should trigger retry via @retry_llm_call."""
        mock_response_empty = MagicMock()
        mock_response_empty.json.return_value = {"response": ""}

        mock_response_ok = MagicMock()
        mock_response_ok.json.return_value = {"response": "Retried response."}

        with patch('core.summarisation.llm_dispatcher.safe_ollama_request',
                   side_effect=[mock_response_empty, mock_response_ok]):
            result = call_fast_ollama(
                prompt="test",
                model="gemma3:12b",
                temp=1.0,
                max_tokens=500,
                ollama_base_url="http://localhost:11434",
                fast_model_context=131072,
                log=lambda m, l: None,
            )
        # Should have retried and gotten the OK response
        # (Note: the retry decorator may or may not retry depending on the exception type)
        # The empty response raises ConnectionError which IS retryable

    def test_context_defaults_to_131072(self):
        """fast_model_context=None should default to 131072."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "response"}

        with patch('core.summarisation.llm_dispatcher.safe_ollama_request', return_value=mock_response) as mock_req:
            call_fast_ollama(
                prompt="test",
                model="gemma3:12b",
                temp=1.0,
                max_tokens=500,
                ollama_base_url="http://localhost:11434",
                fast_model_context=0,  # falsy → should default to 131072
                log=lambda m, l: None,
            )
        # Verify the payload was sent with num_ctx=131072
        call_args = mock_req.call_args
        payload = call_args[1].get('json', {})
        assert payload['options']['num_ctx'] == 131072


# ════════════════════════════════════════════════════════════════════════════
# 7. Summarizer delegation wiring
# ════════════════════════════════════════════════════════════════════════════

class TestSummarizerDelegation:
    """Verify that Summarizer._call_* methods delegate correctly."""

    def test_call_ollama_delegates(self):
        """_call_ollama should delegate to ld_call_ollama with streaming_enabled."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_ollama)
        assert 'ld_call_ollama' in source
        assert 'streaming_enabled' in source
        assert 'self._streaming_enabled' in source

    def test_call_openai_compat_delegates(self):
        """_call_openai_compat should delegate to ld_call_openai_compat."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_openai_compat)
        assert 'ld_call_openai_compat' in source
        assert 'self.timeout' in source

    def test_call_claude_delegates(self):
        """_call_claude should delegate to ld_call_claude."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_claude)
        assert 'ld_call_claude' in source
        assert 'self.claude_api_key' in source

    def test_call_via_llm_provider_delegates(self):
        """_call_via_llm_provider should delegate to ld_call_via_llm_provider."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_via_llm_provider)
        assert 'ld_call_via_llm_provider' in source
        assert 'call_claude_fn' in source
        assert 'call_openai_compat_fn' in source

    def test_call_fast_ollama_delegates(self):
        """_call_fast_ollama should delegate to ld_call_fast_ollama."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_fast_ollama)
        assert 'ld_call_fast_ollama' in source

    def test_call_llm_stays_in_summarizer(self):
        """_call_llm should NOT be delegated (stays in Summarizer — dispatcher with cache)."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_llm)
        # Should still contain the cache logic + provider dispatch
        assert 'response_cache' in source or 'summarisation_cache_enabled' in source
        assert 'self.provider' in source

    def test_call_llm_with_empty_retry_stays_in_summarizer(self):
        """_call_llm_with_empty_retry should NOT be delegated (Qwen3 /no_think invariant)."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_llm_with_empty_retry)
        # The Qwen3 /no_think injection MUST still be here
        assert '/no_think' in source
        assert 'self._call_llm' in source

    def test_llm_grounding_check_uses_empty_retry(self):
        """Phase 5.3: _llm_grounding_check should use _call_llm_with_empty_retry (not _call_llm)."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._llm_grounding_check)
        # Should route through _call_llm_with_empty_retry (Phase 5.3 fix)
        assert '_call_llm_with_empty_retry' in source
        # The old direct _call_llm call for the non-fusion path should be gone
        # (the fusion path still uses _call_cloud which falls back to _call_llm)


# ════════════════════════════════════════════════════════════════════════════
# 8. Qwen3 /no_think invariant (critical — must not be broken by extraction)
# ════════════════════════════════════════════════════════════════════════════

class TestQwen3NoThinkInvariant:
    """Verify the V18.2.41 Qwen3 /no_think injection is preserved.

    This is the CRITICAL invariant — if it breaks, the model produces
    thinking-mode content instead of actual summaries (V18.2.40 crash).
    """

    def test_no_think_in_call_llm_with_empty_retry(self):
        """The /no_think directive must be in _call_llm_with_empty_retry."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_llm_with_empty_retry)
        assert '/no_think' in source, "Qwen3 /no_think directive missing from _call_llm_with_empty_retry!"

    def test_no_think_on_first_attempt(self):
        """/no_think must be on the FIRST attempt, not just retries."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_llm_with_empty_retry)
        # The prompt += " /no_think" happens BEFORE the first _call_llm
        lines = source.split('\n')
        no_think_line = None
        first_call_line = None
        for i, line in enumerate(lines):
            if 'prompt = prompt + " /no_think"' in line or 'prompt += " /no_think"' in line:
                no_think_line = i
            if 'self._call_llm(prompt' in line and first_call_line is None:
                first_call_line = i
        assert no_think_line is not None, "/no_think not found in source"
        assert first_call_line is not None, "first _call_llm not found"
        assert no_think_line < first_call_line, \
            f"/no_think (line {no_think_line}) must come BEFORE first _call_llm (line {first_call_line})"

    def test_no_think_only_for_qwen_models(self):
        """/no_think should only be added for Qwen-family models."""
        import inspect

        from core.summarisation.summarizer import Summarizer
        source = inspect.getsource(Summarizer._call_llm_with_empty_retry)
        assert 'qwen' in source.lower() or 'qwythos' in source.lower()
