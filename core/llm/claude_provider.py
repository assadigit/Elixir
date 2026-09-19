"""V18.20.1.0 (D7): ClaudeProvider extracted from llm_provider_impl.py.

Anthropic Claude API provider. Extracted verbatim from llm_provider_impl.py
(lines 1045-1138 of the pre-V18.20.1.0 file).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import requests as _requests

from core.llm.llm_provider_impl import LLMProvider
from core.llm.retry import retry_llm_call

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        timeout: int = 180,
        retries: int = 1,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        super().__init__(model, temperature, max_tokens, 65536, timeout, retries, log_callback)
        self.api_key = api_key
        self.base_url = base_url

    def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,  # V18.2.21: accepted for API parity; OpenAI-compat JSON mode wired below
    ) -> str | None:
        if not self.api_key:
            self.log("  ❌ Claude API key not set.", "ERROR")
            return None

        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = min(max_tokens or self.max_tokens, 8192)

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": _model,
            "max_tokens": _max_tok,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": _temp,
        }
        url = f"{self.base_url.rstrip('/')}/messages"

        # V18.2.21 (Phase 2.4-retry): Migrated from inline
        # `for attempt in range(self.retries + 1)` loop with linear
        # `time.sleep(2 * (attempt + 1))` (and a 429-specific
        # `time.sleep(5 * (attempt + 1))`) to the consolidated @retry_llm_call
        # decorator. The decorator classifies 429 as retryable (rate-limit) and
        # 4xx (401/403/404) as non-retryable; the 429 case previously had a
        # double-sleep (5s + 2s = 7s) before retry — that's collapsed into a
        # single exponential backoff wait, which is strictly better. The 401
        # case ("invalid key") now propagates immediately instead of being
        # retried (retrying a bad API key is pointless).
        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call() -> str:
            self.log(
                f"    🧠 Claude ({_model}) t={_temp:.2f} attempt…",
                "INFO",
            )
            resp = _requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()  # → HTTPError for 401/429/5xx
            data = resp.json()
            content = data.get("content", [])
            if content and isinstance(content, list):
                text_parts = [
                    block.get("text", "") for block in content if block.get("type") == "text"
                ]
                text = "".join(text_parts).strip()
                if text:
                    return text
            # Empty response — raise ConnectionError so the decorator retries
            # (preserves old "log empty + sleep + retry" behavior).
            raise _requests.exceptions.ConnectionError("empty response from Claude")

        try:
            return _do_one_call()
        except _requests.exceptions.HTTPError as e:
            # V18.2.21: Surface the actionable 401 message; other 4xx/5xx
            # are logged via the decorator's before_sleep hook (if retried)
            # or here (if non-retryable).
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 401:
                self.log("  ❌ Claude API key invalid or expired.", "ERROR")
            elif status == 429:
                self.log("  ⚠️ Claude rate limited — retries exhausted.", "WARNING")
            else:
                self.log(f"    ⚠️ Claude HTTP {status} call failed: {e}", "WARNING")
            return None
        except Exception as e:
            self.log(f"    ⚠️ Claude call failed: {e}", "WARNING")
            return None
