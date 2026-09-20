"""V0.18 (Phase 5.1, step 7) — Summarizer LLM transport layer.

The _call_* family (llm dispatch + empty-retry, cloud path, provider
router, the ollama streaming/nonstreaming/openai-compat/claude calls, the
structured-JSON call, and the fast-model calls) moved out of
summarizer.py. The llm_dispatcher aliases (ld_call_*) move WITH the bodies
— module-attribute patches must target this module (the 17 seams in
test_p2_summarizer_llm_transport.py were re-pointed in the same commit).

Moved VERBATIM (byte-identical bodies) from ``summarizer.py`` during the
V0.18 Phase 5.1 de-monolithization, re-homed via the house mixin pattern
(cf. additive_sections / chapter_phases). ``SummarizerTransportMixin`` joined the
Summarizer bases; every ``self.<attr>`` / ``self.<method>`` reference
resolves exactly as before.
"""

from __future__ import annotations

from typing import Any

from core.summarisation import llm_dispatcher as _ld
from core.summarisation.fast_llm import call_fast_llm as fl_call_fast_llm
from core.summarisation.llm_dispatcher import call_claude as ld_call_claude
from core.summarisation.llm_dispatcher import call_fast_ollama as ld_call_fast_ollama
from core.summarisation.llm_dispatcher import call_ollama as ld_call_ollama
from core.summarisation.llm_dispatcher import call_openai_compat as ld_call_openai_compat
from core.summarisation.llm_dispatcher import call_via_llm_provider as ld_call_via_llm_provider
from core.summarisation.structured_llm import call_llm_structured as sl_call_llm_structured
from utils.error_trace import log_swallow
from utils.logging import get_main_logger

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()


class SummarizerTransportMixin:
    """See the module docstring."""

    def _call_llm(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        if model is None:
            model = self.primary_model
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens or self.request.summarisation_max_output_tokens
        # V13.45.4: Academic-rigor JSON mode needs more tokens — the JSON format
        # with claim+supporting_text+source_reference is ~3x more token-heavy
        # than XML. V13.40.5 set the floor to 12288; V13.45.4 raises to 16000
        # (matching the user's max_output_tokens setting). With 32K context,
        # 16K output is safe and prevents thorough_summary truncation.
        if self.academic_rigor and max_tok < 16000:
            max_tok = 16000

        # V10.33.0 (Sprint 5.3): Check the in-memory response cache first.
        # This skips the LLM entirely for repeated prompts (re-summarization,
        # gap-fill reprompts, conservative-mode A/B testing).  The cache is
        # always active (no setting) — it's free (in-memory, no disk I/O).
        # V18.20.4.8 (P6 / O-a8, fixes W-a9): max_tokens IS part of the cache
        # key now (passed as the 4th arg below). The old key
        # (prompt+model+temperature) let a call with a larger max_tokens
        # return a truncated cached response — call sites vary max_tokens
        # 2048/4096/6144/16000 (academic-rigor floor, scholar reflection).
        # Old cache entries simply miss under the new key — safe.
        # V13.35.0: Cache gated by summarisation_cache_enabled ONLY.
        # The old `cache_enabled` OR-branch was dead code (the attribute
        # doesn't exist on ConversionRequest — only `summarisation_cache_enabled`
        # does) and a latent foot-gun: if anyone ever set request.cache_enabled
        # directly, the cache would hit even when Cache: False. The PUT path
        # is now also gated (see below) — previously it wrote to disk even
        # when Cache: False, polluting response_cache.jsonl with entries that
        # became HITs the moment the user toggled Cache back to True.
        _cache_enabled = bool(getattr(self.request, "summarisation_cache_enabled", False))
        if _cache_enabled:
            try:
                from core.llm.response_cache import response_cache

                cached = response_cache.get(prompt, model or "", temp, max_tok)
                if cached is not None:
                    # V18.20.3.10 (O7): HIT promoted DEBUG→INFO — the cache
                    # is opt-in, so a hit is exactly what the audit-iteration
                    # user wants to SEE (why this run is fast / what it
                    # skipped paying for).
                    self.log(
                        f"    💾 Response cache HIT — LLM call skipped "
                        f"({model or 'primary model'})",
                        "INFO",
                    )
                    return cached
            except Exception as _e:
                logger.debug(
                    "ignored %s: %s", type(_e).__name__, _e
                )  # cache is best-effort — never block on it

        # V10.31.0 (Sprint 4.3): Cloud providers now delegate to the
        # llm_provider abstraction (create_provider).  The Ollama path
        # stays inline because it has OllamaSupervisor crash-recovery
        # integration that the provider abstraction doesn't (yet).
        # This achieves the Sprint 4 exit criterion: "grep confirms
        # Summarizer delegates to llm_provider" for the cloud path.
        # Session 2 will migrate the Ollama path too (requires adding
        # supervisor support to OllamaProvider).
        if self.provider == "claude":
            _result = self._call_via_llm_provider(
                "claude",
                prompt,
                model=model or self.claude_model,
                temp=temp,
                max_tokens=max_tok,
            )
        elif self.provider == "freellmapi":
            _result = self._call_via_llm_provider(
                "openai_compat",
                prompt,
                base_url=self.freellmapi_url,
                api_key=self.freellmapi_key,
                model=model or self.freellmapi_model,
                temp=temp,
                max_tokens=max_tok,
            )
        elif self.provider in ("openrouter", "openai", "openai_compatible"):
            _result = self._call_via_llm_provider(
                "openai_compat",
                prompt,
                base_url=self.api_base_url,
                api_key=self.api_key,
                model=model or self.cloud_model,
                temp=temp,
                max_tokens=max_tok,
            )
        elif self.provider == "llamacpp":
            # V0.04: llama.cpp server. GENERAL RULE: the backend's own
            # configured model is the source of truth — a stale Ollama tag
            # in the request (saved wizard profile, old checkpoint) never
            # reaches llama-server. The provider clamps max_tok to the
            # model's 12288 output cap and fits it into the 65536 window
            # (academic-rigor's 16000 floor cannot 400 the request).
            _result = self._call_via_llm_provider(
                "llamacpp",
                prompt,
                base_url=self.llamacpp_base_url,
                api_key=self.llamacpp_api_key,
                model=self.llamacpp_model or model,
                temp=temp,
                max_tokens=max_tok,
            )
        else:
            _result = self._call_ollama(prompt, model=model, temp=temp, max_tokens=max_tok)

        # V13.35.0: Gate the PUT with _cache_enabled (was unguarded — wrote
        # to disk even when Cache: False, polluting response_cache.jsonl).
        if _result and _cache_enabled:
            try:
                from core.llm.response_cache import response_cache

                response_cache.put(prompt, model or "", temp, _result, max_tok)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)  # cache is best-effort
        return _result

    def _call_llm_with_empty_retry(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        min_length: int = 10,
    ) -> str | None:
        """Call _call_llm and retry once if the response is empty/too short.

        V13.35.0: Addresses 'empty responses on some B3/section calls'. The
        inline HTTP functions already retry on empty (2 attempts), but
        transient VRAM eviction on the RTX 3060 12GB (Gemma 4 ~10.9 GB) can
        cause both to fail when the model is reloading. This wrapper adds one
        higher-level retry with a 2-second delay (gives the model time to
        reload into VRAM) and a nudge suffix ("Please output the response
        now.") that helps when the model is confused by a complex prompt.

        Used by: _summarize_with_model, B3 samples, B4 sections, Tier-2
        gap-fill, two-pass.
        (V18.7.0: _simplify_for_reading_level was deleted as dead code —
        it no longer needs its own retry note.)

        V18.2.31 (reverted V18.2.28): the deadline-aware retry skip was WRONG.
        It caused the V18.2.30 complete crash — the retry is what produces
        the summary. A delayed summary with skipped enrichment is better
        than no summary. ALWAYS retry once after empty/timeout.

        V18.2.41 (CRITICAL fix): Add /no_think to the FIRST prompt for
        Qwen3 models. The V18.2.40 conversion log (IQ2_S model) showed
        thinking-mode content leaking into the output — the model produced
        9344 chars of internal reasoning ("The user wants...", "Let me
        analyze...") instead of an actual summary. The parser treated this
        thinking content as the "thorough summary", producing a catastrophic
        1/10 failure. Previously /no_think was only added on RETRY, but the
        first attempt "succeeded" (returned 9344 chars), so no retry fired.
        Now /no_think is prepended to every Qwen3 call from the start.
        This matches Key Decision #2: "Thinking mode is WORSE for
        summarization."
        """
        # V18.2.41: Prepend /no_think for Qwen3 thinking-capable models.
        # This disables the thinking phase that produces internal reasoning
        # instead of the actual summary. Must be on the FIRST attempt, not
        # just retries — otherwise the thinking content is treated as a
        # "successful" response and no retry fires.
        _model_lower = (model or self.primary_model or "").lower()
        _is_qwen3 = "qwen" in _model_lower or "qwythos" in _model_lower
        if _is_qwen3:
            prompt = prompt + " /no_think"

        raw = self._call_llm(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
        if raw and len(raw.strip()) >= min_length:
            return raw
        # V18.2.31: ALWAYS retry. A summary (even delayed) > no summary.
        # Empty or too short — retry with a nudge suffix after a brief delay
        # (the delay gives the model time to reload into VRAM if it was evicted).
        # V18.20.3.10 (F5, .3.8 rig audit): promoted DEBUG→WARNING — the
        # .3.7 rig log had a 1.9s empty round-1 response that was INVISIBLE
        # at DEBUG; it recovered via this retry, but the operator should
        # see the anomaly when it happens, not only when it fails twice.
        self.log("    ⚠️ Empty/short LLM response — retrying with nudge after 2s delay", "WARNING")
        try:
            import time as _time

            _time.sleep(2)
        except Exception as _e:
            # V18.2.14 (B4): was silent ``pass`` — now traceable.
            log_swallow("empty_response_retry_sleep", _e)
        nudge = "\n\nPlease output the response now."
        # For Qwen-family models, /no_think is already in the prompt (V18.2.41),
        # but we keep it in the nudge too for belt-and-suspenders safety.
        if _is_qwen3:
            nudge = " /no_think\n\nPlease output the response now."
        raw2 = self._call_llm(
            prompt + nudge, model=model, temperature=temperature, max_tokens=max_tokens
        )
        if raw2 and len(raw2.strip()) >= min_length:
            return raw2
        return None

    def _call_cloud(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str | None:
        """V13.36.0: Call the FUSION cloud model for strategic decisions.

        Used ONLY when ``self.fusion_enabled`` is True. Routes to the cloud
        provider configured under ``summarisation.fusion_*`` settings. On
        failure (timeout, 401, network), falls back to the local model via
        ``_call_llm`` — the pipeline NEVER blocks on a cloud failure.

        This is the surgical injection point for the Hybrid Fusion feature.
        Called by:
          - ``_self_review`` (site A: independent fact-checker)
          - ``_llm_grounding_check`` (site B: bullet verification)
          - ``_multi_sample_summarize`` (site D: pick best summary)
          - ``_targeted_gap_fill`` (site E: higher-quality paraphrases, opt-in)

        NOT called by the primary summarization path — that always uses the
        local model (the whole point of fusion: local does the heavy lifting,
        cloud does the surgical aids).
        """
        if not self.fusion_enabled:
            # Fusion not enabled — fall back to local
            return self._call_llm(
                prompt,
                temperature=temperature or self.fusion_cloud_temperature,
                max_tokens=max_tokens or self.fusion_cloud_max_tokens,
            )

        _temp = temperature if temperature is not None else self.fusion_cloud_temperature
        _max_tok = max_tokens or self.fusion_cloud_max_tokens
        _model = self.fusion_cloud_model
        _provider = self.fusion_cloud_provider

        try:
            if _provider == "claude":
                result = self._call_via_llm_provider(
                    "claude",
                    prompt,
                    model=_model or self.claude_model,
                    temp=_temp,
                    max_tokens=_max_tok,
                )
            else:
                # openai_compat (OpenRouter, OpenAI, 9Router, etc.)
                result = self._call_via_llm_provider(
                    "openai_compat",
                    prompt,
                    base_url=self.fusion_cloud_base_url,
                    api_key=self.fusion_cloud_api_key,
                    model=_model,
                    temp=_temp,
                    max_tokens=_max_tok,
                )
            if result and result.strip():
                self.log(f"    🔀 Fusion cloud ({_model}) responded: {len(result)} chars", "DEBUG")
                return result.strip()
            # Cloud returned empty — fall back to local
            self.log("    🔀 Fusion cloud returned empty — falling back to local model", "WARNING")
        except Exception as e:
            self.log(
                f"    🔀 Fusion cloud failed ({type(e).__name__}: {e}) — falling back to local",
                "WARNING",
            )
            logger.debug("fusion cloud call failed: %s: %s", type(e).__name__, e)

        # Graceful fallback: use the local model for the same prompt
        return self._call_llm(prompt, temperature=_temp, max_tokens=_max_tok)

    def _call_via_llm_provider(
        self,
        provider_type: str,
        prompt: str,
        model: str = "",
        base_url: str = "",
        api_key: str = "",
        temp: float = 0.6,
        max_tokens: int = 4096,
    ) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher.call_via_llm_provider."""
        return ld_call_via_llm_provider(
            provider_type,
            prompt,
            model,
            base_url,
            api_key,
            temp,
            max_tokens,
            timeout=self.timeout,
            supervisor=self._ollama_supervisor,
            log=self.log,
            call_claude_fn=self._call_claude,
            call_openai_compat_fn=self._call_openai_compat,
        )

    def _call_ollama(self, prompt: str, model: str, temp: float, max_tokens: int) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher.call_ollama.

        V18.15.6.0 (Fix B): passes an error_tracker list so the caller can
        distinguish "model not installed" (404) from "model timed out" (timeout)
        when the call returns None. The tracker is stored on self._last_llm_error
        for inspection by _summarize_inner's error-message logic.
        """
        # V18.15.6.0 (Fix B): reset the error tracker before each call.
        # A 1-element list is the standard out-param pattern (mutable container
        # captured by reference inside the dispatcher's closure).
        _tracker: list = []
        result = ld_call_ollama(
            prompt,
            model,
            temp,
            max_tokens,
            streaming_enabled=self._streaming_enabled,
            ollama_base_url=self.ollama_base_url,
            timeout=self.timeout,
            retries=self.retries,
            context_tokens=self.request.summarisation_max_context_tokens,
            supervisor=self._ollama_supervisor,
            log=self.log,
            error_tracker=_tracker,
        )
        # V18.15.6.0 (Fix B): persist the error type (or None on success).
        if result:
            self._last_llm_error_type = None
        elif _tracker:
            self._last_llm_error_type = _tracker[0]
        else:
            # Empty response with no tracked error — treat as "empty".
            self._last_llm_error_type = "empty"
        return result

    def _call_ollama_streaming(
        self, prompt: str, model: str, temp: float, max_tokens: int
    ) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher._call_ollama_streaming."""
        return _ld._call_ollama_streaming(
            prompt,
            model,
            temp,
            max_tokens,
            ollama_base_url=self.ollama_base_url,
            timeout=self.timeout,
            retries=self.retries,
            context_tokens=self.request.summarisation_max_context_tokens,
            supervisor=self._ollama_supervisor,
            log=self.log,
        )

    def _call_ollama_nonstreaming(
        self, prompt: str, model: str, temp: float, max_tokens: int
    ) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher._call_ollama_nonstreaming."""
        return _ld._call_ollama_nonstreaming(
            prompt,
            model,
            temp,
            max_tokens,
            context_tokens=self.request.summarisation_max_context_tokens,
            timeout=self.timeout,
            retries=self.retries,
            ollama_base_url=self.ollama_base_url,
            supervisor=self._ollama_supervisor,
            log=self.log,
        )

    def _call_openai_compat(
        self,
        prompt: str,
        base_url: str,
        api_key: str,
        model: str,
        label: str,
        temp: float,
        max_tokens: int,
    ) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher.call_openai_compat."""
        return ld_call_openai_compat(
            prompt,
            base_url,
            api_key,
            model,
            label,
            temp,
            max_tokens,
            timeout=self.timeout,
            retries=self.retries,
            provider=self.provider,
            log=self.log,
        )

    def _call_claude(self, prompt: str, max_tokens: int, temperature: float) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher.call_claude."""
        return ld_call_claude(
            prompt,
            max_tokens,
            temperature,
            claude_api_key=self.claude_api_key,
            claude_model=self.claude_model,
            claude_base_url=self.claude_base_url,
            retries=self.retries,
            log=self.log,
        )

    def _call_llm_structured(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any] | None:
        """V18.2.22 (Phase 2.2 PoC): Call the LLM requesting JSON, validate.

        V18.15.3 (Phase 5 Stage 3, Batch 4.1): logic extracted verbatim to
        ``structured_llm.call_llm_structured``. The 3 ``self`` deps
        (``provider``, ``_parse_response``, ``log``) are passed as explicit
        kwargs (the proven-safe pattern — NOT a context object).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_structured_llm.py``).
        """
        return sl_call_llm_structured(
            prompt,
            model,
            temperature,
            max_tokens,
            provider=getattr(self, "provider", "ollama"),
            parse_response=self._parse_response,
            log=self.log,
        )

    def _call_fast_llm(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 1.0,
    ) -> str | None:
        """V16.0.9: Call the fast/small model for simple tasks.

        V18.15.3 (Phase 5 Stage 3, Batch 4.4): logic extracted verbatim to
        ``fast_llm.call_fast_llm``. The 7 ``self`` deps (``request``,
        ``_call_llm_with_empty_retry``, ``_switch_to_fast_model``,
        ``_call_fast_ollama``, ``_switch_to_heavy_model``,
        ``_call_openai_compat``, ``log``) are passed as explicit kwargs (the
        proven-safe pattern — NOT a context object). ``request`` is the
        read-only ConversionRequest data object (accessed only via getattr).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_fast_llm.py``).
        """
        return fl_call_fast_llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            request=self.request,
            call_llm_with_empty_retry=self._call_llm_with_empty_retry,
            switch_to_fast_model=self._switch_to_fast_model,
            call_fast_ollama=self._call_fast_ollama,
            switch_to_heavy_model=self._switch_to_heavy_model,
            call_openai_compat=self._call_openai_compat,
            log=self.log,
        )

    def _call_fast_ollama(
        self, prompt: str, model: str, temp: float, max_tokens: int
    ) -> str | None:
        """V18.8 (Phase 5.3): delegates to llm_dispatcher.call_fast_ollama.

        Migrated from inline ``for attempt in range(2)`` loop to
        ``@retry_llm_call`` decorator (the last holdout).
        """
        return ld_call_fast_ollama(
            prompt,
            model,
            temp,
            max_tokens,
            ollama_base_url=self.ollama_base_url,
            fast_model_context=getattr(self.request, "fast_model_context", 131072),
            log=self.log,
        )
