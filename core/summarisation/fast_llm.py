"""V18.15.3 (Phase 5 Stage 3, Batch 4.4): Fast/small-model LLM dispatch.

Extracted verbatim from ``Summarizer._call_fast_llm`` (god-class decomposition
Stage 4 — the 16th extraction). Routes fast/simple tasks across the 4-mode
model architecture (single_local / single_api / dual_local / dual_api),
falling back to the primary heavy model on any failure.

**Extraction map**:

| Summarizer method (old) | fast_llm function (new) | self deps |
|------------------------|------------------------|-----------|
| ``_call_fast_llm`` | ``call_fast_llm`` | ``request`` (read-only ConversionRequest data object), ``_call_llm_with_empty_retry``, ``_switch_to_fast_model``, ``_call_fast_ollama``, ``_switch_to_heavy_model``, ``_call_openai_compat``, ``log`` |

**Note on ``request``**: ``ConversionRequest`` is the primary read-only INPUT
data object passed to ``Summarizer.__init__`` (not a ``PromptContext``-style
context object). It is accessed here only via ``getattr`` (never mutated), so
passing it explicitly is consistent with the V18.6.3 crash mitigation
("explicit parameters, NOT context objects"). Every ``getattr(self.request,
X, default)`` is replicated verbatim as ``getattr(request, X, default)`` for
byte-for-byte fidelity.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Zero mutable state — the function is read-only w.r.t. the Summarizer instance.

Characterization tests: ``tests/test_fast_llm.py`` captures all 4 architecture
modes, the legacy ``single`` alias, the gemma3:12b short-circuit, the
dual_local failure-fallback, and the dual_api missing-config fallback.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
RequestLike = Any
CallLlmRetryFn = Callable[..., str | None]
SwitchModelFn = Callable[[], None]
CallFastOllamaFn = Callable[..., str | None]
CallOpenAiCompatFn = Callable[..., str | None]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


def _noop_llm(prompt, **kw):
    """Default no-op LLM call (returns None)."""
    return None


# ── call_fast_llm (extracted verbatim) ─────────────────────────────────────

def call_fast_llm(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 1.0,
    request: RequestLike = None,
    call_llm_with_empty_retry: CallLlmRetryFn | None = None,
    switch_to_fast_model: SwitchModelFn | None = None,
    call_fast_ollama: CallFastOllamaFn | None = None,
    switch_to_heavy_model: SwitchModelFn | None = None,
    call_openai_compat: CallOpenAiCompatFn | None = None,
    log: LogCallback | None = None,
) -> str | None:
    """Call the fast/small model for simple tasks.

    Routes to (4-mode architecture):
    - ``single_local`` / ``single_api``: fast tasks use the primary (heavy)
      model — local Ollama or cloud API, depending on provider. Legacy
      ``single`` is accepted and treated as ``single_local``.
    - ``dual_local``  mode: uses Ollama fast model with 128K context
    - ``dual_api``    mode: uses the fast cloud API (fast_api_*)

    Falls back to the primary heavy model if the fast model is not configured
    or the call fails.
    """
    if log is None:
        log = _noop_log
    if call_llm_with_empty_retry is None:
        call_llm_with_empty_retry = _noop_llm

    arch = getattr(request, "model_architecture", "single_local") or "single_local"
    # V16.0.9: backward-compat — legacy "single" → "single_local"
    if arch == "single":
        arch = "single_local"

    # V16.0.8: Use the fast model's own temperature (not the heavy model's)
    # LFM2.5-2.6B recommends 0.3; Gemma4-12b recommends 1.0
    fast_temp = getattr(request, "fast_model_temperature", 0.1)

    # single_local + single_api (+ legacy single): fast tasks reuse the
    # heavy model. ``_call_llm_with_empty_retry`` routes via self.provider,
    # so single_api (provider = cloud) hits the cloud API automatically.
    if arch in ("single_local", "single_api"):
        return call_llm_with_empty_retry(
            prompt, temperature=temperature, max_tokens=max_tokens,
        )

    if arch == "dual_local":
        fast_model = getattr(request, "fast_model", "") or ""
        if not fast_model or fast_model == "gemma3:12b":
            return call_llm_with_empty_retry(
                prompt, temperature=temperature, max_tokens=max_tokens,
            )
        switch_to_fast_model()
        try:
            result = call_fast_ollama(prompt, model=fast_model, temp=fast_temp, max_tokens=max_tokens)
            return result
        except Exception as _e:
            log(f"    ⚠️ Fast model failed ({_e}) — falling back to heavy", "WARNING")
            switch_to_heavy_model()
            return call_llm_with_empty_retry(
                prompt, temperature=temperature, max_tokens=max_tokens,
            )

    if arch == "dual_api":
        api_url = getattr(request, "fast_api_url", "") or ""
        api_key = getattr(request, "fast_api_key", "") or ""
        api_model = getattr(request, "fast_api_model", "") or ""
        if not api_url or not api_model:
            return call_llm_with_empty_retry(
                prompt, temperature=temperature, max_tokens=max_tokens,
            )
        try:
            return call_openai_compat(
                prompt, base_url=api_url, api_key=api_key,
                model=api_model, label="FastAPI",
                temp=fast_temp, max_tokens=max_tokens,
            )
        except Exception:
            return call_llm_with_empty_retry(
                prompt, temperature=temperature, max_tokens=max_tokens,
            )
    return None
