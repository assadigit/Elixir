"""V18.20.1.0 (D7): OpenAICompatProvider extracted from llm_provider_impl.py.

OpenAI-compatible provider (OpenRouter, OpenAI, FreeLLMAPI). Extracted verbatim
from llm_provider_impl.py (lines 769-1043 of the pre-V18.20.1.0 file).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import requests as _requests

from core.llm.llm_provider_impl import LLMProvider
from core.llm.retry import (
    retry_llm_call,
)
from utils.network import extract_openai_content, session_for_url

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    """OpenAI-compatible provider (OpenRouter, OpenAI, FreeLLMAPI)."""

    def __init__(
        self,
        model: str = "",
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        timeout: int = 300,
        retries: int = 1,
        log_callback: Callable[[str, str], None] | None = None,
        label: str = "Cloud",
    ):
        super().__init__(model, temperature, max_tokens, 65536, timeout, retries, log_callback)
        self.base_url = base_url
        self.api_key = api_key
        self.label = label

    def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,  # V18.2.21: accepted for API parity; OpenAI-compat JSON mode wired below
    ) -> str | None:
        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or self.max_tokens

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "openrouter" in self.base_url:
            headers["HTTP-Referer"] = "https://elixir.local"
            headers["X-Title"] = "Elixir"

        payload = {
            "model": _model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _max_tok,
            "temperature": _temp,
        }
        # V18.2.21 (Phase 1.2): OpenAI-compatible JSON mode. Most OpenAI-
        # compat endpoints (OpenAI, OpenRouter, FreeLLMAPI) support
        # response_format={"type": "json_object"}. The prompt must contain
        # the word "json" for OpenAI to accept it (structured_io appends a
        # JSON instruction that does).
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = f"{self.base_url.rstrip('/')}/chat/completions"

        # V18.2.21 (Phase 2.4-retry): Migrated from inline
        # `for attempt in range(self.retries + 1)` loop with linear
        # `time.sleep(2 * (attempt + 1))` to the consolidated @retry_llm_call
        # decorator (exponential backoff + jitter). The decorator classifies
        # retryable errors (429 / 5xx / ConnectionError) and retries them;
        # non-retryable errors (401 / 403 / 404 / programming errors) propagate
        # immediately and the outer try/except converts them to None (preserving
        # the old "exhaust loop → return None" contract). An empty response is
        # wrapped into a ConnectionError so the decorator retries it (matches
        # the old "log empty + sleep + retry" behavior).
        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call() -> str:
            self.log(
                f"    ☁️ {self.label} ({_model}) t={_temp:.2f} attempt…",
                "INFO",
            )
            # V0.6.7 (review-loop A5): pooled transport via session_for_url —
            # the ONE routing rule (cloud endpoints trust env proxies, localhost
            # /v1 endpoints like FreeLLMAPI get the proxy-immune session) —
            # replaces the bare per-call ``_requests.post``: same timeout, same
            # retries, plus connection reuse. The deep-index choices[0] parse
            # becomes the shared shape-safe extract_openai_content (same
            # migration as llm_dispatcher.call_openai_compat in V18.20.4.11):
            # a malformed/error payload now flows into the SAME empty-response
            # retry path as an empty-but-valid response (previously it raised
            # KeyError straight to the outer except → None, skipping retry).
            resp = session_for_url(url).post(
                url, headers=headers, json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
            text = extract_openai_content(resp.json())
            if not text:
                # Empty response — raise ConnectionError so the decorator
                # retries (preserves old "log empty + sleep + retry" behavior).
                raise _requests.exceptions.ConnectionError("empty response from cloud model")
            return text

        try:
            return _do_one_call()
        except Exception as e:
            # V18.2.21: retries exhausted OR a non-retryable error raised
            # (e.g. HTTP 401/403/404). The old code returned None at end of
            # the loop — we preserve that contract here.
            self.log(f"    ⚠️ {self.label} call failed: {e}", "WARNING")
            return None

    def batch_complete(
        self,
        prompts: list[
            str
        ],  # V18.20.3.12 (F821): List was undefined — modernized like the rest of the tree
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_batch_api: bool = False,
    ) -> list[str | None]:
        """V10.36.0: Real batch completion with parallel requests.

        V10.18.0 (C3) was a fake batch (sequential loop). V10.36.0 adds
        two real modes:

        1. **Parallel** (default): sends all prompts concurrently using
           ``concurrent.futures.ThreadPoolExecutor``. Same cost as
           sequential, but ~3× faster (APIs handle concurrent requests
           well).  No API support needed — works with any OpenAI-compat
           endpoint.

        2. **Batch API** (``use_batch_api=True``): uses the OpenAI Batch
           API for 50% cost reduction. Requires OpenAI (not OpenRouter)
           and takes up to 24h for completion. Only suitable for
           overnight runs. Falls back to parallel if the Batch API is
           unavailable.

        Args:
            prompts: List of prompt strings.
            temperature: Temperature for all prompts.
            max_tokens: Max tokens for all prompts.
            use_batch_api: If True, try the OpenAI Batch API (50% discount).
                Falls back to parallel if unavailable.
        """
        if not prompts:
            return []

        if use_batch_api:
            result = self._batch_api_complete(prompts, temperature, max_tokens)
            if result is not None:
                return result
            self.log("  ℹ️ Batch API unavailable — falling back to parallel", "DEBUG")

        # V10.36.0: Parallel execution (3-5× faster than sequential)
        import concurrent.futures

        max_workers = min(len(prompts), 5)  # cap at 5 concurrent requests
        results: list[str | None] = [None] * len(prompts)  # V18.20.3.12 (F821): List was undefined

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.complete, prompt, temperature, max_tokens): idx
                for idx, prompt in enumerate(prompts)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    self.log(f"  ⚠️ Batch item {idx} failed: {e}", "WARNING")
                    results[idx] = None

        return results

    def _batch_api_complete(
        self,
        prompts: list[str],  # V18.20.3.12 (F821): List was undefined — modernized
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[str | None] | None:
        """V10.36.0: Use the OpenAI Batch API for 50% cost reduction.

        Creates a batch job, polls until complete, and returns results.
        Returns None if the Batch API is unavailable (non-OpenAI endpoint,
        missing API key, or timeout). The caller falls back to parallel.

        Note: Batch jobs can take up to 24h. Only suitable for overnight runs.
        """
        try:
            # Only attempt if this looks like an OpenAI endpoint
            if "openai.com" not in self.base_url:
                return None
            if not self.api_key:
                return None

            _temp = temperature if temperature is not None else self.temperature
            _max_tok = max_tokens or self.max_tokens

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            # 1. Build the batch input file (JSONL)
            import json

            batch_lines = []
            for idx, prompt in enumerate(prompts):
                batch_lines.append(
                    json.dumps(
                        {
                            "custom_id": f"request-{idx}",
                            "method": "POST",
                            "url": "/v1/chat/completions",
                            "body": {
                                "model": self.model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": _max_tok,
                                "temperature": _temp,
                            },
                        }
                    )
                )
            batch_content = "\n".join(batch_lines)

            # 2. Upload the file
            upload_url = f"{self.base_url.rstrip('/')}/files"
            files = {
                "file": ("batch.jsonl", batch_content, "application/json"),
                "purpose": (None, "batch"),
            }
            upload_resp = _requests.post(
                upload_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                files=files,
                timeout=30,
            )
            if upload_resp.status_code != 200:
                self.log(f"  ⚠️ Batch API: file upload failed ({upload_resp.status_code})", "DEBUG")
                return None
            file_id = upload_resp.json().get("id")
            if not file_id:
                return None

            # 3. Create the batch
            batch_url = f"{self.base_url.rstrip('/')}/batches"
            batch_payload = {
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
            }
            batch_resp = _requests.post(batch_url, headers=headers, json=batch_payload, timeout=30)
            if batch_resp.status_code != 200:
                self.log(
                    f"  ⚠️ Batch API: batch creation failed ({batch_resp.status_code})", "DEBUG"
                )
                return None
            batch_id = batch_resp.json().get("id")
            self.log(f"  📦 Batch API: job created ({batch_id}), polling…", "INFO")

            # 4. Poll until complete (max 10 minutes)
            import time as _time

            for _poll in range(60):  # 60 × 10s = 10 min max
                # V0.4.28 (E6 sync-only guard): this blocks the QThread worker
                # for 10s per poll (up to 10 min on a live Batch-API). Fine for
                # the sync model. If async_provider is ever wired (see
                # docs/ASYNC_PROVIDER_DECISION.md), replace with asyncio.sleep
                # — under run_async this would block the event loop for the
                # full 10-min poll (the highest-severity E6 hazard).
                _time.sleep(10)
                poll_resp = _requests.get(
                    f"{batch_url}/{batch_id}",
                    headers=headers,
                    timeout=30,
                )
                if poll_resp.status_code != 200:
                    continue
                status = poll_resp.json().get("status", "")
                if status == "completed":
                    output_file_id = poll_resp.json().get("output_file_id")
                    break
                elif status in ("failed", "expired", "cancelled"):
                    self.log(f"  ⚠️ Batch API: job {status}", "WARNING")
                    return None
            else:
                self.log("  ⚠️ Batch API: timed out after 10 minutes", "WARNING")
                return None

            # 5. Download the results
            dl_url = f"{self.base_url.rstrip('/')}/files/{output_file_id}/content"
            dl_resp = _requests.get(dl_url, headers=headers, timeout=60)
            if dl_resp.status_code != 200:
                return None

            # 6. Parse results (JSONL with custom_id → response)
            results: list[str | None] = [None] * len(
                prompts
            )  # V18.20.3.12 (F821): List was undefined
            for line in dl_resp.text.strip().splitlines():
                try:
                    entry = json.loads(line)
                    custom_id = entry.get("custom_id", "")
                    idx = int(custom_id.split("-")[-1])
                    if entry.get("response", {}).get("status_code") == 200:
                        body = entry["response"]["body"]
                        content = body["choices"][0]["message"]["content"].strip()
                        results[idx] = content if content else None
                except (json.JSONDecodeError, KeyError, ValueError, IndexError):
                    continue

            self.log(
                f"  ✅ Batch API: {sum(1 for r in results if r)}/{len(results)} completed", "INFO"
            )
            return results

        except Exception as e:
            self.log(f"  ⚠️ Batch API failed: {e}", "DEBUG")
            return None
