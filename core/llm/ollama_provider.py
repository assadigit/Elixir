"""V18.20.1.0 (D7): OllamaProvider extracted from llm_provider_impl.py.

Local Ollama provider (http://localhost:11434). V10.4.0: includes
OllamaSupervisor integration — records failures and auto-restarts Ollama after
3 consecutive connection errors.

Extracted verbatim from llm_provider_impl.py (lines 159-767 of the pre-V18.20.1.0
file). The llm_provider_impl.py module re-exports this class for backward compat.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import requests as _requests

from core.llm.context_budget import count_tokens as _count_tokens
from core.llm.llm_provider_impl import LLMProvider, _get_keep_alive

# V18.20.4.12 (T-c7): ModelNotFound404Error moved to the shared
# core/llm/model_errors.py module — imported here (and re-exported for
# compat, matching the historical ``from core.llm.ollama_provider import
# ModelNotFound404Error`` pattern) so the raise site below, the outer
# handler, and every external importer share ONE class + ONE canonical
# ``ollama pull`` message.
from core.llm.model_errors import ModelNotFound404Error  # noqa: F401 — re-export for compat
from core.llm.retry import (
    OllamaOOMError,
    OllamaTimeoutError,
    ThinkingModeViolation,
    retry_llm_call,
    retry_with_oom_context_halving,
)
from core.system.ollama_supervisor import OllamaSupervisor
from utils.network import safe_ollama_request, session_for_url

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Local Ollama provider (http://localhost:11434).

    V10.4.0: includes OllamaSupervisor integration — records failures
    and auto-restarts Ollama after 3 consecutive connection errors.
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
        supervisor: OllamaSupervisor | None = None,
    ):
        super().__init__(
            model, temperature, max_tokens, context_tokens, timeout, retries, log_callback
        )
        self.base_url = base_url
        self._supervisor = supervisor or OllamaSupervisor(
            url=base_url,
            max_consecutive_failures=3,
            log_callback=lambda msg, level="INFO": self.log(msg, level),
        )

    def smoke_test(self, prompt: str = "hello", timeout: int | None = None) -> bool:
        """V18.4 (Phase 2): probe the Ollama server + model with a tiny request.

        Mirrors ``OllamaEmbedBackend.smoke_test`` / the embedder smoke-test
        pattern: send a minimal ``/api/generate`` call (1 token, no thinking,
        no JSON) and assert a non-empty response. Use this at startup /
        preflight to catch:

          - Ollama not running (ConnectionError).
          - Model not pulled (HTTP 404).
          - Model loads but returns empty (broken quant / Modelfile).
          - Server too slow (Timeout — distinct from a hang).

        This is the LLM-side twin of the embedder smoke-test: the embedder
        test verifies ``/api/embed`` works; this verifies ``/api/generate``
        works. Both are needed — a working embed endpoint does NOT imply a
        working generate endpoint (different code paths, different models).

        Args:
            prompt: the probe prompt (default ``"hello"``). Kept tiny so the
                call costs <1s on a warm model and ~5s on a cold load.
            timeout: override the provider's default timeout for this one
                probe (seconds). Defaults to ``min(self.timeout, 60)`` so a
                cold model load can't stall preflight for 5+ minutes.

        Returns:
            True if Ollama returned a non-empty response for ``self.model``;
            False otherwise (with a loud ERROR log explaining the likely
            cause). Never raises — callers can use this in a boolean context
            without try/except.
        """
        # A cold model load (first call after Ollama start) can take ~30s on
        # the IQ2_S 27B. Cap the smoke-test at 60s so preflight never stalls.
        _to = timeout if timeout is not None else min(self.timeout, 60)
        _payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "system": "",
            "keep_alive": _get_keep_alive(),
            "options": {
                # V18.2.42: do NOT set presence_penalty — let the Modelfile
                # decide (1.5 = Instruct mode). Setting 0.0 would activate
                # thinking mode AND trip the ThinkingModeViolation guard.
                "temperature": 0.0,  # greedy — most deterministic probe
                "num_predict": 1,  # 1 token is enough to prove the model runs
                "num_ctx": 4096,  # tiny ctx → fast KV cache allocation
                "num_gpu": -1,
            },
        }
        url = f"{self.base_url}/api/generate"
        try:
            resp = safe_ollama_request("POST", url, json=_payload, timeout=_to)
            data = resp.json()
        except _requests.exceptions.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404:
                self.log(
                    f"    🚫 OllamaProvider smoke-test FAILED: model '{self.model}' "
                    f"not found (HTTP 404). Run: ollama pull {self.model}",
                    "ERROR",
                )
            else:
                self.log(
                    f"    🚫 OllamaProvider smoke-test FAILED: HTTP {status} — {e}",
                    "ERROR",
                )
            return False
        except _requests.exceptions.Timeout:
            self.log(
                f"    🚫 OllamaProvider smoke-test FAILED: timeout after {_to}s "
                f"(model '{self.model}' may be loading or Ollama is stalled). "
                f"If this persists, check Ollama is running and the model is pulled.",
                "ERROR",
            )
            return False
        except _requests.exceptions.ConnectionError as e:
            self.log(
                f"    🚫 OllamaProvider smoke-test FAILED: cannot reach Ollama at "
                f"{self.base_url} ({e}). Is `ollama serve` running?",
                "ERROR",
            )
            return False
        except Exception as e:
            self.log(
                f"    🚫 OllamaProvider smoke-test FAILED: {type(e).__name__}: {e}",
                "ERROR",
            )
            return False

        # Ollama /api/generate returns {"response": "...", "done": true, ...}.
        # An empty/whitespace response means the model loaded but produced
        # nothing (broken quant, empty Modelfile template, or the IQ2_S
        # "empty generation" failure mode documented in V18.2.43).
        _resp = (data.get("response") or "").strip()
        if not _resp:
            _err = data.get("error", "")
            self.log(
                f"    🚫 OllamaProvider smoke-test FAILED: empty response from "
                f"'{self.model}' (model loaded but generated nothing"
                + (f"; server error: {_err}" if _err else "")
                + "). This is the V18.2.43 empty-generation failure mode — "
                "check the Modelfile template / try a different quant.",
                "ERROR",
            )
            return False

        self.log(
            f"    ✅ OllamaProvider smoke-test OK: '{self.model}' responded "
            f"({len(_resp)} chars, prompt={prompt!r})",
            "DEBUG",
        )
        return True

    def _adaptive_context(self, prompt: str, max_tokens: int) -> int:
        """V13.29.0 (P3.1): Calculate the optimal context window size.

        Instead of always using the full configured context (default 65536),
        this method estimates the actual needed context based on the prompt
        length. This saves VRAM on short prompts — a 500-token prompt doesn't
        need 65k of KV cache.

        Formula:
            V0.09 (P5): estimated_prompt_tokens = count_tokens(prompt)
            (tiktoken cl100k_base via core.llm.context_budget — replaced the
            old len(prompt)//4 heuristic, which over-counted repetitive text
            ~2x and under-counted CJK)
            needed = estimated_prompt_tokens + max_tokens + 4096 (safety margin)
            ctx = min(self.context_tokens, max(16000, needed))

        The 16000 minimum is Ollama's default for most models — going below
        it can cause "context too small" errors for some models.

        The safety margin (4096) covers system prompts, thinking blocks,
        and response overhead.

        For a 2000-token chapter (8000 chars):
            needed = 2000 + 4096 + 4096 = 10192
            ctx = min(65536, max(16000, 10192)) = 16000

        For a 8000-token chapter (32000 chars):
            needed = 8000 + 4096 + 4096 = 16192
            ctx = min(65536, max(16000, 16192)) = 16192

        For a 30000-token chapter (120000 chars):
            needed = 30000 + 4096 + 4096 = 38192
            ctx = min(65536, max(16000, 38192)) = 38192
        """
        # V0.09 (P5): tokenizer-aware estimate (see formula note above). The
        # import is bound at module level (the summarizer.py:228 convention);
        # tests that need to control it patch core.llm.ollama_provider's
        # binding (the established consumer-binding patch pattern).
        estimated_prompt_tokens = _count_tokens(prompt)
        needed = estimated_prompt_tokens + max_tokens + 4096
        ctx = min(self.context_tokens, max(16000, needed))

        # V18.2 (audit): Adaptive context reduction for VRAM-constrained cards.
        # If the GPU has <2 GB VRAM free, reduce ctx to 16384 (saves ~1 GB KV cache).
        # This prevents CPU offloading on 12 GB cards running a 27B model.
        # The chapter is 9127 tokens — 16k context is plenty (9127 + 4096 margin = 13223 < 16384).
        try:
            from utils.settings import Settings

            _adaptive = Settings().get("summarisation.adaptive_context_enabled", True)
        except Exception:
            _adaptive = True
        if _adaptive:
            try:
                import torch

                if torch.cuda.is_available():
                    total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)
                    free_gb = total_gb - allocated_gb
                    # If <2 GB free, reduce to 16k to save ~1 GB KV cache
                    if free_gb < 2.0 and ctx > 16384:
                        _orig_ctx = ctx
                        ctx = 16384
                        logger.info(
                            "V18.2: adaptive context %d→16384 (only %.1f GB VRAM free — "
                            "reducing KV cache to prevent CPU offloading)",
                            _orig_ctx,
                            free_gb,
                        )
                    # V18.2.31: IQ2_XXS on 12 GB cards stalls when context
                    # exceeds 26758 tokens (the KV cache size + the 12B IQ2_XXS
                    # weights pushes past 12 GB and triggers CPU offloading
                    # mid-generation). Cap the context at 26758 (which still
                    # fits a full chapter + 4096 margin) ONLY on cards with
                    # ≤12 GB total VRAM. Larger cards (16+ GB) are unaffected.
                    #
                    # V18.2.40 (CRITICAL fix): The 26758 cap was designed for
                    # the 9.5 GB IQ2_XXS model. The 9.8 GB Q2_K_XL model needs
                    # a LOWER cap because it has 64 layers (vs IQ2_XXS's 64
                    # layers, but the Q2_K_XL file is 0.3 GB larger, leaving
                    # only 0.05 GB headroom at 26758 context — way too tight).
                    #
                    # KV cache math for 27B model (64 layers, 8 KV heads, 128 head_dim):
                    #   At 26758 ctx: 64 × 26758 × 1024 bytes = 1.75 GB
                    #   At 16000 ctx: 64 × 16000 × 1024 bytes = 1.05 GB  (saves 0.7 GB)
                    #
                    # VRAM budget for Q2_K_XL on 12GB card:
                    #   Model: 9.8 GB + CUDA: 0.4 GB = 10.2 GB used
                    #   At 26758 ctx: 10.2 + 1.75 = 11.95 GB → 99.6% VRAM (FAILS)
                    #   At 16000 ctx: 10.2 + 1.05 = 11.25 GB → 93.8% VRAM (FITS)
                    #
                    # The chapter is ~11000 tokens (9139 text + 2000 prompt),
                    # so 16000 context has 5000 tokens of headroom — comfortable.
                    _model_lower = (self.model or "").lower()
                    # V18.3 (Phase 1.1): replaced 4 inline heuristics with the
                    # canonical model_taxonomy functions — single source of truth.
                    # Behavior is IDENTICAL for all tested models (IQ2_S, IQ2_XXS,
                    # Q2_K_XL, 9B-Q8, 27B-Q8) because "q2_" is a substring of "iq2_s"
                    # etc. See tests/test_model_taxonomy.py + test_ctx_cap_branching.py.
                    from core.llm.model_taxonomy import (
                        is_27b_plus,
                        is_iq2_s,
                        is_low_bit_quant,
                        param_count_b,
                    )

                    _is_low_bit = is_low_bit_quant(self.model)
                    _param_b = param_count_b(self.model)
                    _is_27b_plus = is_27b_plus(self.model)
                    # V18.2.43: IQ2_S models have more VRAM headroom than Q2_K_XL.
                    # The V18.2.40 cap of 16000 was designed for Q2_K_XL (9.8GB, 0.8GB headroom).
                    # IQ2_S is only 8.37GB — it has 1.5GB headroom at 16000 context,
                    # enough to safely raise the cap to 26758 (matching V18.2.21 gold standard).
                    #
                    # VRAM math (IQ2_S 27B on 12GB card):
                    #   Model: 8.37 GB + CUDA: 0.4 GB = 8.77 GB used
                    #   At 26758 ctx: KV = 1.64 GB → total 10.41 GB → 1.59 GB headroom ✅
                    #   At 16000 ctx: KV = 0.98 GB → total 9.75 GB → 2.25 GB headroom (wasteful)
                    #
                    # VRAM math (Q2_K_XL 27B on 12GB card — STAYS at 16000):
                    #   Model: 9.8 GB + CUDA: 0.4 GB = 10.2 GB used
                    #   At 16000 ctx: KV = 0.98 GB → total 11.18 GB → 0.82 GB headroom ✅
                    #   At 26758 ctx: KV = 1.64 GB → total 11.84 GB → 0.16 GB headroom ❌ (too tight)
                    if _is_low_bit and total_gb <= 12.0 and _is_27b_plus:
                        _is_iq2_s_model = is_iq2_s(self.model)
                        # V18.20.2.0 (SWOT A3): the cap VALUE now comes from the
                        # shared clamp helper (core/llm/ctx_clamp.py) — the same
                        # single source the llm_dispatcher streaming-fallback path
                        # uses. Identical values (IQ2_S→26758, other low-bit→16000);
                        # the constants are no longer duplicated inline.
                        from core.llm.ctx_clamp import low_bit_ctx_cap

                        _safe_ctx = low_bit_ctx_cap(self.model, total_gb)
                        # V18.3.5 (F2): VRAM-AWARE RAISE — FIXED.
                        # V18.3.4 had 2 bugs: (1) the condition "if ctx > _raised_ctx"
                        # was INVERTED (it capped DOWN, never raised UP), and (2) the
                        # standard cap below ("if ctx > _safe_ctx → ctx = _safe_ctx")
                        # immediately overrode the raise.
                        # FIX: when VRAM allows (≥1.2 GB free), raise _safe_ctx itself
                        # from 26758 → 32768. This way the standard cap respects the raise.
                        #
                        # V18.20.2.0 (SWOT A1): the raise now requires a REAL external
                        # VRAM reading (Ollama /api/ps). The old condition used
                        # torch.cuda.memory_allocated() — which measures THIS app
                        # process, not the separate Ollama process — so _free_gb was
                        # ≈12 GB on every call and IQ2_S safe_ctx was silently raised
                        # 26758→32768 unconditionally (violating the hard constraint
                        # "app caps to 26758 for IQ2_S" and eroding the headroom whose
                        # loss caused the V18.19/V18.20 GPU OOM hard-kills). When the
                        # external reading is unavailable (offline/API error) the
                        # raise does NOT fire — the safe 26758 cap stays in force.
                        if _is_iq2_s_model:
                            _free_gb = self._external_gpu_free_gb(total_gb)
                            if _free_gb is not None and _free_gb >= 1.2:
                                _orig_safe = _safe_ctx
                                _safe_ctx = 32768
                                logger.info(
                                    "ctx_raise: model=%s safe_ctx %d→%d reason=VRAM-aware "
                                    "(%.2f GB free → KV=2.01GB, headroom=1.22GB)",
                                    self.model,
                                    _orig_safe,
                                    _safe_ctx,
                                    _free_gb,
                                )
                                self.log(
                                    f"    📈 V18.3.5: IQ2_S VRAM-aware raise — safe_ctx {_orig_safe}→{_safe_ctx} "
                                    f"({_free_gb:.2f} GB VRAM free, KV=2.01GB, headroom=1.22GB)",
                                    "INFO",
                                )
                        # Standard cap — now respects the VRAM-aware raise
                        if ctx > _safe_ctx:
                            _orig_ctx = ctx
                            ctx = _safe_ctx
                            logger.info(
                                "ctx_capped: model=%s from=%d to=%d reason=VRAM "
                                "(%sB %s on %.0fGB card — IQ2_S headroom 1.59GB vs Q2_K 0.82GB)",
                                self.model,
                                _orig_ctx,
                                ctx,
                                _param_b if _param_b > 0 else "?",
                                "IQ2_S" if _is_iq2_s_model else "Q2_K",
                                total_gb,
                            )
                            self.log(
                                f"    🔧 V18.2.43: {_param_b:g}B {'IQ2_S' if _is_iq2_s_model else 'Q2_K'} "
                                f"model on {total_gb:.0f}GB card — capping context {_orig_ctx}→{ctx} "
                                f"(IQ2_S has more headroom than Q2_K_XL: 1.59GB vs 0.82GB free)",
                                "INFO",
                            )
            except Exception:
                pass

        return ctx

    def _external_gpu_free_gb(self, total_gb: float | None) -> float | None:
        """V18.20.2.0 (SWOT A1): real GPU headroom from Ollama ``/api/ps``.

        The pre-V18.20.2.0 raise condition used ``torch.cuda.memory_allocated()``
        — which measures THIS app process, not the separate Ollama process — so
        ``free_gb`` was ≈ the full 12 GB on every call and the IQ2_S safe_ctx was
        silently raised 26758→32768 unconditionally (eroding the exact VRAM
        headroom whose loss caused the V18.19/V18.20 GPU OOM hard-kills).

        This method queries Ollama's ``/api/ps`` (which reports ``size_vram``
        for every loaded model — the REAL VRAM footprint including KV cache)
        and returns ``total_gb − Σ size_vram``.

        Returns:
            Free VRAM in GB, or ``None`` when the external reading is
            unavailable (Ollama offline, API error, malformed response).
            Callers MUST treat ``None`` as "do NOT raise" — the safe 26758
            cap stays in force (quality > speed).
        """
        if total_gb is None or total_gb <= 0:
            return None
        try:
            from utils.network import safe_ollama_request

            resp = safe_ollama_request("GET", f"{self.base_url}/api/ps", timeout=5)
            data = resp.json()
            used_bytes = 0
            for _entry in data.get("models", []) or []:
                try:
                    used_bytes += int(_entry.get("size_vram") or 0)
                except (TypeError, ValueError):
                    continue
            return total_gb - (used_bytes / (1024**3))
        except Exception as exc:
            logger.debug(
                "ctx_raise: external VRAM reading unavailable for model=%s "
                "(%s: %s) — keeping safe cap",
                self.model,
                type(exc).__name__,
                exc,
            )
            return None

    def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str | None:
        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or self.max_tokens
        # V13.29.0 (P3.1): Adaptive context window — use a smaller ctx for
        # short prompts to save VRAM. The old code always used the full
        # context_tokens (default 65536) even for a 500-token prompt.
        # Now: ctx = min(configured_max, prompt_tokens * 2 + max_tokens + 4096)
        # but never below 16000 (Ollama minimum for most models).
        ctx = self._adaptive_context(prompt, _max_tok)

        payload = {
            "model": _model,
            "prompt": prompt,
            "stream": False,
            # V18.2.37e (CRITICAL fix): override the Modelfile's SYSTEM prompt.
            # The user's Q2_K_XL model has a complex system prompt in its
            # Modelfile ("You are an expert academic summariser... output
            # <finding /> XML format..."). This CONFLICTS with our app's
            # prompt, causing the model to return empty. By sending an empty
            # system prompt, we tell Ollama to IGNORE the Modelfile's system
            # prompt and use only our prompt.
            "system": "",
            # V18.1 (audit): Add keep_alive so models stay resident in VRAM
            # between calls. The old code had no keep_alive, so Ollama used
            # its default 5-minute timeout — models cold-reloaded between
            # chapters if the user waited >5 min. User explicitly requested
            # "keep the model in the vram" — 30m is a good balance (long
            # enough for inter-chapter gaps, short enough to free VRAM if
            # the user walks away). Configurable via settings.llm.keep_alive.
            "keep_alive": _get_keep_alive(),
            "options": {
                "temperature": _temp,
                "num_predict": _max_tok,
                "num_ctx": ctx,
                # V18.1 (P7): -1 means "use all available GPU layers" in
                # Ollama — handles small-VRAM cards gracefully (the old
                # hardcoded 99 forced 99 layers offload even on cards that
                # couldn't hold the whole model, causing OOM/spillover).
                "num_gpu": -1,
                # V18.2.42 (CRITICAL fix): DO NOT force presence_penalty=0.
                # Key Decision #7 was WRONG — it was based on the V18.2.37
                # Q2_K_XL failure, which was actually a VRAM overflow issue
                # (not a presence_penalty issue). Forcing presence_penalty=0
                # puts Qwen3 models in THINKING MODE, causing them to produce
                # internal reasoning ("The user wants...", "Let me analyze...")
                # instead of actual summaries.
                #
                # Per Unsloth's official documentation:
                #   Thinking Mode:       presence_penalty=0.0
                #   Instruct (no-think):  presence_penalty=1.5
                #
                # By NOT overriding presence_penalty here, the Modelfile's
                # value (1.5 for Instruct mode) is used. This keeps the model
                # in Instruct mode and prevents thinking-mode content leaks.
                # (presence_penalty removed — let Modelfile decide)
            },
        }

        # V18.3 (Phase 1.2): ThinkingModeViolation guard.
        # If the model is a Qwen3 variant AND the payload explicitly sets
        # presence_penalty=0.0, REFUSE the call — that activates thinking
        # mode (the V18.2.41 2/10 regression). This is fail-closed: it can
        # only PREVENT a known-bad config, never cause one. If
        # presence_penalty is absent (Modelfile decides) or is 1.5 (Instruct
        # mode), the guard does NOT fire. Non-Qwen3 models are unaffected.
        _model_lower = (_model or "").lower()
        _is_qwen3 = "qwen" in _model_lower or "qwythos" in _model_lower
        if _is_qwen3:
            _pp = payload.get("options", {}).get("presence_penalty")
            if _pp is not None and float(_pp) == 0.0:
                self.log(
                    f"    🚫 ThinkingModeViolation: Qwen3 model '{_model}' called with "
                    f"presence_penalty=0.0 — REFUSING (this activates thinking mode, "
                    f"the V18.2.41 2/10 regression). Fix: set presence_penalty=1.5.",
                    "ERROR",
                )
                raise ThinkingModeViolation(model=_model)

        # V18.2.21 (Phase 1.2): JSON mode — request structured JSON output
        # from Ollama. The caller validates via structured_io.validate_*.
        # Low-bit quants (IQ2_XXS) can't follow complex JSON reliably
        # (Key Decision #5) — callers should check supports_json_mode()
        # before setting json_mode=True. The flag is a no-op for providers
        # that don't support it.
        if json_mode:
            payload["format"] = "json"
        url = f"{self.base_url}/api/generate"

        # V18.2.21 (Phase 2.4-retry): Migrated from inline
        # `for attempt in range(self.retries + 1)` loop with linear
        # `time.sleep(3 * (attempt + 1))` to the consolidated @retry_llm_call
        # decorator + retry_with_oom_context_halving helper. The migration
        # preserves ALL prior business logic:
        #   - V11.17: HTTP 404 (model not pulled) → return None immediately.
        #   - V18.2.19: Timeout → return None (non-retryable; aligns with
        #     the same fix already applied to summarizer._call_ollama_nonstreaming).
        #     [NOTE: prior to this migration, OllamaProvider.complete did NOT
        #     honor the V18.2.19 fix — it retried on Timeout. This migration
        #     aligns the two paths.]
        #   - V10.18.0 (A4): OOM → halve num_ctx and retry ONCE (min 8192).
        #   - V10.4.0: supervisor.record_success/record_failure integration.
        #   - Empty-response retry (preserved as a ConnectionError → retryable).
        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call(num_ctx: int) -> str:
            payload["options"]["num_ctx"] = num_ctx
            self.log(
                f"    🤖 {_model} (t={_temp:.2f}) num_ctx={num_ctx} attempt…",
                "INFO",
            )
            # V18.20.3.9 (Phase 3.a / C1): wall-clock for THIS attempt —
            # feeds the per-call telemetry line + the process-wide registry
            # that the end-of-run diagnostic summarizes.
            _t0 = time.monotonic()
            try:
                resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
            except _requests.exceptions.HTTPError as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 404:
                    # V11.17: Ollama returns 404 when the model is not installed.
                    # Pulling is a user action, not transient — surface as a
                    # typed non-retryable so the outer handler logs the
                    # actionable `ollama pull` message.
                    err_detail = ""
                    try:
                        err_detail = e.response.json().get("error", "")
                    except Exception:
                        err_detail = e.response.text[:200] if e.response is not None else ""
                    raise ModelNotFound404Error(model=_model, detail=err_detail) from e
                # V10.18.0 (A4): detect OOM in the HTTP error message —
                # Ollama returns 500 with "out of memory" / "oom" /
                # "cuda out of memory" in the body. Raise as a typed
                # non-retryable so retry_with_oom_context_halving handles it.
                _err_str = str(e).lower()
                if (
                    "out of memory" in _err_str
                    or "oom" in _err_str
                    or "cuda out of memory" in _err_str
                ):
                    raise OllamaOOMError(model=_model, num_ctx=num_ctx, detail=str(e)) from e
                raise  # let decorator classify (429 → retry, 5xx → retry, 4xx → non-retryable)
            except _requests.exceptions.Timeout as e:
                # V18.2.19: timeouts on IQ2_XXS indicate model stall — non-retryable.
                # (Previously this provider retried on Timeout; summarizer's path
                # already honored V18.2.19. This migration aligns both paths.)
                self._supervisor.record_failure()
                raise OllamaTimeoutError(model=_model, timeout=self.timeout, original=e) from e
            except _requests.exceptions.ConnectionError:
                # V10.4.0: network blip / Ollama down — supervisor records
                # (may auto-restart Ollama). Decorator retries the ConnectionError.
                self._supervisor.record_failure()
                raise
            # HTTP OK — parse the response JSON.
            _data = resp.json()
            text = (_data.get("response") or "").strip()
            # V18.20.3.9 (Phase 3.a / C1): per-call telemetry — one INFO
            # line per completed call (duration, prompt/eval tokens,
            # done_reason) + one registry entry for the end-of-run
            # aggregate. The .3.7/.3.8 rig audits had to reconstruct these
            # numbers by hand from log-timestamp subtraction; every later
            # perf decision (Phase 3.b cap right-sizing) reads them
            # directly now.
            try:
                _dur = time.monotonic() - _t0
                self.log(
                    f"    ⏱️ {_model} done in {_dur:.1f}s — "
                    f"prompt {_data.get('prompt_eval_count', '?')} tok, "
                    f"output {_data.get('eval_count', '?')} tok, "
                    f"done_reason={_data.get('done_reason', '?')}",
                    "INFO",
                )
                from core.llm.call_meta import record_call_telemetry

                record_call_telemetry(
                    model=_model,
                    duration_s=_dur,
                    prompt_tokens=_data.get("prompt_eval_count"),
                    output_tokens=_data.get("eval_count"),
                    done_reason=_data.get("done_reason"),
                )
            except Exception:
                pass  # best-effort — telemetry must never fail a call
            # V18.20.2.0 (SWOT A20): truncation observability. Ollama sets
            # done_reason="length" when generation stopped at the num_predict
            # cap — the output was silently truncated. Downstream postchecks
            # handle truncation CONTENT; this WARNING only makes the fact
            # visible (model + prompt tokens + truncated-output length) so
            # operators can distinguish "model finished" from "output cap
            # hit". The returned text is intentionally NOT modified.
            _truncated = _data.get("done_reason") == "length"
            # V18.20.3.5 (audit v182034): also PROPAGATE the truncation flag
            # (ContextVar, set on every response) so verdict-critical
            # callers (scholar reflection's gap analysis) can refuse to
            # trust a clean verdict parsed from a cut response. Logging
            # alone left the .3.4 run's truncated scholar call emitting
            # "no significant gaps found".
            try:
                from core.llm.call_meta import mark_call_truncated

                mark_call_truncated(_truncated)
            except Exception:  # pragma: no cover — never fail a call over a flag
                pass
            if _truncated:
                logger.warning(
                    "truncation_detected: model=%s done_reason=length "
                    "(num_predict cap hit mid-generation) prompt_eval_count=%s "
                    "eval_count=%s truncated_output_len=%d num_ctx=%d",
                    _model,
                    _data.get("prompt_eval_count"),
                    _data.get("eval_count"),
                    len(text),
                    num_ctx,
                )
                self.log(
                    f"    ✂️ Output truncated (done_reason=length): '{_model}' hit "
                    f"the num_predict cap mid-generation — prompt "
                    f"{_data.get('prompt_eval_count')} tok, output {len(text)} chars. "
                    f"Downstream postchecks will assess truncation content.",
                    "WARNING",
                )
            if not text:
                # Empty response — raise ConnectionError so the decorator
                # retries (preserves old "log empty + sleep + retry" behavior).
                raise _requests.exceptions.ConnectionError("empty response from model")
            self._supervisor.record_success()
            return text

        try:
            # retry_with_oom_context_halving handles V10.18.0 (A4): on OOM,
            # halve num_ctx and retry ONCE (min_ctx=8192 — Ollama's practical
            # minimum). The @retry_llm_call decorator on _do_one_call handles
            # transient ConnectionError / 429 / 5xx with exponential backoff.
            return retry_with_oom_context_halving(
                call_fn=_do_one_call,
                initial_ctx=ctx,
                min_ctx=8192,
                log_callback=self.log,
            )
        except ModelNotFound404Error:
            # V11.17: surface an actionable error — fetching the list of
            # installed models so the user can pick an alternative.
            try:
                from utils.network import list_ollama_models

                installed = list_ollama_models(self.base_url)
            except Exception:
                installed = []
            avail = ", ".join(installed) if installed else "(no models installed)"
            self.log(
                f"    ❌ Model '{_model}' is NOT installed in Ollama (HTTP 404).",
                "ERROR",
            )
            # Re-raise the underlying detail if available (ModelNotFound404Error.detail).
            self.log(
                f"       👉 Fix: `ollama pull {_model}` (or pick: {avail})",
                "ERROR",
            )
            return None  # do NOT retry — pulling is a user action
        except OllamaTimeoutError:
            # V18.2.19: model stall — return None, caller handles empty response.
            self.log(
                f"    ⚠️ {_model} timeout — NOT retrying (model stall, not transient).",
                "WARNING",
            )
            return None
        except OllamaOOMError:
            # V10.18.0 (A4): OOM persisted even after ctx halving — return None.
            self.log(
                f"    🚨 {_model} OOM even at reduced num_ctx — returning None.",
                "ERROR",
            )
            return None
        except Exception as e:
            # Retries exhausted OR a non-retryable error raised.
            self.log(f"    ⚠️ {_model} call failed: {e}", "WARNING")
            return None

    # V0.4.1: vision capability for OCR — provider-agnostic, no hardcoded
    # model names. The probe calls Ollama's /api/show to check if the model
    # has an mmproj/adapter attached (the /api/show response includes
    # "model_info" with projector details for vision models).

    def supports_vision(self) -> bool:
        """Probe Ollama /api/show to check if the model has vision ability.

        Content-agnostic: checks the LIVE model info for an mmproj adapter,
        not a hardcoded model name list. If /api/show fails, returns False
        (fail-safe — don't attempt vision if we can't confirm it).
        """
        try:
            url = f"{self.base_url}/api/show"
            # V0.6.7 (review-loop A5): pooled transport via session_for_url —
            # localhost Ollama gets the proxy-immune session (a misconfigured
            # HTTP_PROXY must never break the /api/show probe); remote Ollama
            # hosts keep env-proxy behavior. Same timeout, plus connection reuse.
            resp = session_for_url(url).post(url, json={"name": self.model}, timeout=10)
            if resp.status_code != 200:
                return False
            info = resp.json()
            # Ollama's /api/show includes "model_info" with projector/adapter
            # details for vision models. Check for any key containing
            # "vision" or "adapter" or "mmproj" — these indicate a vision
            # projector is attached. Also check "projector_info" (newer
            # Ollama versions) and "adapter_info".
            model_info = info.get("model_info", {})
            # Check all values in model_info for vision/projector indicators
            for key, val in model_info.items():
                key_lower = key.lower()
                if (
                    "vision" in key_lower
                    or "projector" in key_lower
                    or "adapter" in key_lower
                    or "mmproj" in key_lower
                ):
                    return True
                # Some Ollama versions store the projector type as a
                # general.architecture value
                if isinstance(val, str) and ("vision" in val.lower() or "mmproj" in val.lower()):
                    return True
            # Also check "projector_info" and "adapter_info" (newer keys)
            return any(info.get(key) for key in ("projector_info", "adapter_info"))
        except Exception:
            return False

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str | None:
        """Send a prompt + image to Ollama and return the text response.

        Uses Ollama's /api/generate endpoint with the ``images`` field
        (base64-encoded image). Content-agnostic — works with any
        vision-capable model on Ollama.

        V0.4.12: added optional ``model`` parameter so cross-backend OCR
        can use a different model than the provider's default (e.g., when
        the main model is on llama.cpp but the OCR model is on Ollama).
        """
        import base64 as _b64

        b64_image = _b64.b64encode(image_bytes).decode("utf-8")
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or 4096
        _model = model or self.model  # V0.4.12: allow override
        payload = {
            "model": _model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {"temperature": _temp, "num_predict": _max_tok},
        }
        url = f"{self.base_url}/api/generate"
        try:
            # V0.6.7 (review-loop A5): pooled transport via session_for_url —
            # same routing rule as supports_vision (proxy-immune for localhost,
            # env-proxy for remote hosts), plus connection reuse.
            resp = session_for_url(url).post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip() or None
        except Exception as e:
            self.log(f"    ⚠️ Ollama vision call failed: {e}", "WARNING")
        return None

    def complete_streaming(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str | None:
        """V10.16.0 (C2): Streaming Ollama call.

        Uses Ollama's streaming API (``stream: True``) to receive tokens
        as they're generated.  Each chunk is a JSON object with a ``response``
        field containing the incremental text.  The ``on_chunk`` callback is
        called with the FULL accumulated text after each chunk (so the UI
        can show the growing summary).

        Falls back to non-streaming if the streaming call fails.
        """
        if not on_chunk:
            return self.complete(prompt, temperature, max_tokens, model)

        _model = model or self.model
        _temp = temperature if temperature is not None else self.temperature
        _max_tok = max_tokens or self.max_tokens
        # V13.29.0 (P3.1): Adaptive context window (same as complete())
        ctx = self._adaptive_context(prompt, _max_tok)

        payload = {
            "model": _model,
            "prompt": prompt,
            "stream": True,  # V10.16.0: streaming mode
            # V18.20.2.0 (SWOT A2): mirror complete()'s payload semantics.
            # The old streaming payload omitted BOTH of these, so streaming
            # mode silently diverged from non-streaming:
            #   - no "system": "" → the Modelfile's SYSTEM prompt returned
            #     (the V18.2.37e empty-response class resurfacing);
            #   - no "keep_alive" → Ollama's default 5m unload between
            #     chapters instead of the 30m policy.
            "system": "",
            "keep_alive": _get_keep_alive(),
            "options": {
                "temperature": _temp,
                "num_predict": _max_tok,
                "num_ctx": ctx,
                # V18.2.14 (P7): -1 means "use all available GPU layers" in
                # Ollama — matches the non-streaming path (line 259). The old
                # hardcoded 99 forced 99 layers offload even on cards that
                # couldn't hold the whole model, causing OOM/spillover. Now
                # both code paths agree on -1.
                "num_gpu": -1,
            },
        }
        url = f"{self.base_url}/api/generate"

        try:
            self.log(f"    🤖 {_model} (t={_temp:.2f}) streaming…", "INFO")
            # V18.20.2.0 (SWOT A21): use the shared no-proxy session from
            # utils.network instead of a per-call Session + os.environ proxy
            # pop/restore. The env mutation was thread-unsafe under the
            # ThreadPoolExecutor workers and redundant: trust_env=False plus
            # empty proxies already makes the session proxy-immune. The
            # shared session is NOT closed here (it is process-lifetime).
            from utils.network import get_shared_session

            session = get_shared_session()

            resp = session.post(url, json=payload, timeout=self.timeout, stream=True)
            resp.raise_for_status()

            full_text = ""
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    import json

                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        full_text += token
                        on_chunk(full_text)  # call with accumulated text
                    if chunk.get("done", False):
                        break
                except (json.JSONDecodeError, ValueError):
                    continue

            if full_text.strip():
                self._supervisor.record_success()
                return full_text.strip()
            self.log("    ⚠️ Streaming returned empty response", "WARNING")
        except _requests.exceptions.ConnectionError as e:
            self.log(f"    ⚠️ Streaming connection error: {e}", "WARNING")
            self._supervisor.record_failure()
        except Exception as e:
            self.log(f"    ⚠️ Streaming failed ({e}) — falling back to non-streaming", "WARNING")

        # Fallback to non-streaming
        return self.complete(prompt, temperature, max_tokens, model)
