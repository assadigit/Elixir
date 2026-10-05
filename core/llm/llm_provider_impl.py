"""V10.15.0 (B4): LLM abstraction layer.

Provides a unified ``LLMProvider`` interface that decouples the summarizer
and output generators from the Ollama/Cloud/Claude API details.  This
replaces the 102 scattered ``safe_ollama_request`` and ``_requests.post``
calls with a single ``provider.complete(prompt) -> str`` interface.

Implementations:
  - ``OllamaProvider`` — local Ollama (http://localhost:11434)
  - ``LlamaCppProvider`` — local llama.cpp server (http://127.0.0.1:8080/v1, V0.04)
  - ``OpenAICompatProvider`` — OpenRouter/OpenAI/FreeLLMAPI
  - ``ClaudeProvider`` — Anthropic Claude API

The Summarizer's ``_call_llm`` method (172 lines) will delegate to this
module.  The output generators' ``_call_llm`` (already has retry from V10.13.0)
will also delegate here in a future pass.

Usage::

    from core.llm.llm_provider import create_provider

    provider = create_provider(
        provider="ollama",
        model="qwythos:latest",
        settings=Settings(),
    )
    response = provider.complete(
        prompt="Summarize this chapter...",
        temperature=0.6,
        max_tokens=4096,
        log_callback=log,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# V18.2.21 (Phase 2.4-retry): consolidated retry decorator + typed exceptions.
# Replaces the 8 duplicated `for attempt in range(self.retries + 1)` loops
# (5 in this module + 3 in summarizer.py) with one tenacity-based policy.
from core.system.ollama_supervisor import OllamaSupervisor
from core.system.secrets import get_secret as _get_secret

logger = logging.getLogger(__name__)


# V18.1 (audit): Module-level cache for keep_alive setting (avoids Settings()
# lookup on every LLM call — this is a hot path).
# V18.20.1.0 (D3): centralized to _runtime_state.state.keep_alive_cache.
# Backward-compat proxy kept so existing ``monkeypatch.setattr`` calls don't
# break (but the impl reads/writes state.keep_alive_cache directly).
from core.summarisation._runtime_state import state as _runtime_state
from core.system.timeouts import (  # V0.6.10 (B15): the timeout policy leaf
    LLM_REQUEST_TIMEOUT_S,
    SLOW_LLM_TIMEOUT_S,
    UI_PROBE_TIMEOUT_S,
)

_keep_alive_cache: str | None = None  # backward-compat proxy (impl uses _runtime_state)


def _get_keep_alive() -> str:
    """Return the Ollama keep_alive duration from settings.

    Reads ``settings.llm.keep_alive`` (default ``"30m"``). This controls how
    long Ollama keeps a model resident in VRAM after the last request. The old
    code had no keep_alive in the payload, so Ollama used its default 5-minute
    timeout — models cold-reloaded between chapters if the user waited >5 min.
    """
    # V18.20.1.0 (D3): read/write the centralized state object directly.
    if _runtime_state.keep_alive_cache is not None:
        return _runtime_state.keep_alive_cache
    try:
        from utils.settings import Settings

        _runtime_state.keep_alive_cache = str(Settings().get("llm.keep_alive", "30m"))
    except Exception:
        _runtime_state.keep_alive_cache = "30m"
    return _runtime_state.keep_alive_cache


class LLMProvider:
    """Base class for LLM providers.

    Subclasses implement ``complete()`` which takes a prompt and returns
    the LLM's text response (or None on failure).
    """

    def __init__(
        self,
        model: str = "",
        temperature: float = 0.6,
        max_tokens: int = 4096,
        context_tokens: int = 65536,
        timeout: int = 300,
        retries: int = 1,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_tokens = context_tokens
        self.timeout = timeout
        self.retries = retries
        self.log = log_callback or (lambda msg, level="INFO": None)

    def complete(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str | None:
        """Call the LLM and return the text response (or None on failure).

        Args:
            prompt: the prompt text.
            temperature: optional override for the configured temperature.
            max_tokens: optional override for the configured max_tokens.
            model: optional override for the configured model.
            json_mode: V18.2.21 (Phase 1.2) — if True, request JSON-mode
                output from the provider (Ollama ``format: "json"``,
                OpenAI ``response_format``, etc.). The caller is responsible
                for validating the response (see
                ``core.llm.structured_io.validate_summary_json``). Providers
                that don't support JSON mode ignore this flag.
        """
        raise NotImplementedError("Subclasses must override complete()")

    def complete_streaming(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str | None:
        """Call the LLM with streaming — call ``on_chunk(text)`` for each token chunk.

        V10.16.0 (C2): Streaming support.  Returns the full text when done,
        but calls ``on_chunk(partial_text)`` as tokens arrive.  This lets the
        UI show partial summaries as they generate (better UX — user sees
        progress instead of waiting 2 min per chapter).

        Default implementation: fall back to non-streaming ``complete()``.
        Subclasses (OllamaProvider) override with real streaming.
        """
        result = self.complete(prompt, temperature, max_tokens, model)
        if result and on_chunk:
            on_chunk(result)
        return result

    # V0.4.1 (Quality Campaign, OCR/vision fix): provider-agnostic vision
    # capability. The OCR service uses these methods to detect whether the
    # model can process images and to send image+prompt to the model.
    # Content-agnostic (AGENTS.md Rule 1): no hardcoded model names — the
    # probe is a live API call to the provider, not a name-keyed check.

    def supports_vision(self) -> bool:
        """Check if this provider/model supports image input.

        Returns False by default — subclasses override with a real probe.
        The probe is a LIVE API call (e.g., Ollama /api/show, llama-server
        /v1/models), not a hardcoded name-keyed check. This ensures the
        detection works for ANY model, not just ones with known names.
        """
        return False

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        """Send a prompt + image to the model and return the text response.

        Returns None by default — subclasses override with the provider's
        multimodal API format (Ollama: images field, llama.cpp:
        OpenAI-compatible content array with image_url).
        """
        return None


# V18.20.1.0 (D7): the 3 provider classes extracted to their own modules.
# V18.20.1.1 (hotfix): the module-level re-export caused a circular import:
#   llm_provider_impl → ollama_provider → llm_provider_impl (deadlock).
# Fix: the re-exports are now LAZY (via __getattr__ at the bottom of this file
# + lazy imports inside create_provider). This breaks the cycle because the
# provider modules are only imported when actually needed (at call time, not
# at module-load time).


# ── Factory ────────────────────────────────────────────────────────────────


def create_provider(
    provider: str,
    settings: Any,
    log_callback: Callable[[str, str], None] | None = None,
    supervisor: OllamaSupervisor | None = None,
) -> LLMProvider:
    """Create an LLMProvider based on the provider name + settings.

    Args:
        provider: "ollama" | "llamacpp" | "openrouter" | "openai" |
                  "openai_compatible" | "claude" | "freellmapi"
        settings: the Settings singleton (for reading API keys, URLs, etc.)
        log_callback: fn(message, level) for progress logging
        supervisor: OllamaSupervisor instance (only used by OllamaProvider)
    """
    log = log_callback or (lambda msg, level="INFO": None)

    # V18.20.1.1 (hotfix): lazy imports inside create_provider to break the
    # circular import (llm_provider_impl → ollama_provider → llm_provider_impl).
    # The provider modules import LLMProvider + _get_keep_alive from THIS module;
    # if we imported them at module level, neither module could finish loading.
    if provider == "ollama":
        from core.llm.ollama_provider import OllamaProvider
        from core.llm.registry import get_registry

        # V0.09 (P5): context window resolved through the ModelRegistry.
        # The SETTINGS value (passed as the registry's ``configured``)
        # WINS over every discovery source, so factory behavior is
        # byte-identical at today's defaults. The registry adds, in order:
        # (a) the new ``llm.context_window_overrides`` per-model key
        # (absent by default — no behavior change until written), (b) the
        # 220,144 local-backend cap (Task 8 decision #2), and (c) fixes the
        # old fallback mismatch — the hardcoded 65536 default below used
        # to disagree with the settings.py default 32768 whenever the key
        # was absent (absent now → registry backend default 32768).
        return OllamaProvider(
            model=settings.get("summarisation.model", ""),
            base_url="http://localhost:11434",
            temperature=settings.get("summarisation.temperature", 0.6),
            max_tokens=settings.get("summarisation.max_output_tokens", 4096),
            context_tokens=get_registry().get_context_window(
                settings.get("summarisation.model", ""),
                "ollama",
                configured=settings.get("summarisation.max_context_tokens"),
            ),
            timeout=LLM_REQUEST_TIMEOUT_S,
            retries=1,
            log_callback=log,
            supervisor=supervisor,
        )
    elif provider == "llamacpp":
        # V0.04: llama.cpp server (llama-server) — the first non-Ollama
        # LOCAL backend. Reads the llamacpp_* settings block (defaults:
        # 127.0.0.1:8080/v1, api key "local", 65k context / 12k output).
        # The timeout honours local.http_timeout_sec (the app-wide local
        # backend timeout) instead of the cloud-style 300s.
        from core.llm.llamacpp_provider import LlamaCppProvider, list_llamacpp_models
        from core.llm.registry import get_registry

        _lc_base = settings.get("summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1")
        _lc_key = _get_secret("summarisation.llamacpp_api_key", settings, "local")
        _configured_model = settings.get("summarisation.llamacpp_model", "")

        # V0.4.30 (multi-backend): detect the ACTUAL served model via
        # GET /v1/models so a llama-server on a different port serving a
        # DIFFERENT model (e.g. 8080=Ternary-Bonsai, 8081=Qwen3.8) is
        # identified + addressed correctly — not by the hardcoded
        # llamacpp_model setting. Falls back to the configured model if
        # the server is unreachable or /v1/models is empty.
        _detected_model = _configured_model
        try:
            _served = list_llamacpp_models(_lc_base, _lc_key, timeout=UI_PROBE_TIMEOUT_S)
            if _served:
                _detected_model = _served[0]
                if _detected_model != _configured_model:
                    log(
                        f"    🦙 llama.cpp: detected model '{_detected_model}' on "
                        f"{_lc_base} (configured: '{_configured_model}') — "
                        f"using the detected.",
                        "INFO",
                    )
        except Exception:
            pass  # fall back to the configured model

        # V0.09 (P5): same registry routing as the ollama branch — the
        # settings value (65k window) stays the ``configured`` override so
        # nothing changes at today's defaults (pinned by
        # tests/test_v004_llamacpp.py::TestFactoryWiring), while the new
        # ``llm.context_window_overrides`` key and the 220,144 local cap
        # become available (Task 8 decisions #2/#4). V0.4.30: the registry
        # lookup now uses the DETECTED model (not the configured) so the
        # context window matches the actual served model.
        return LlamaCppProvider(
            model=_detected_model,
            base_url=_lc_base,
            api_key=_lc_key,
            temperature=settings.get("summarisation.temperature", 0.6),
            max_tokens=settings.get("summarisation.llamacpp_max_output_tokens", 12288),
            context_tokens=get_registry().get_context_window(
                _detected_model,
                "llamacpp",
                configured=settings.get("summarisation.llamacpp_context_tokens"),
            ),
            output_cap=settings.get("summarisation.llamacpp_max_output_tokens", 12288),
            timeout=int(settings.get("local.http_timeout_sec", 600) or 600),
            retries=1,
            log_callback=log,
        )
    elif provider in ("openrouter", "openai", "openai_compatible"):
        from core.llm.openai_compat_provider import OpenAICompatProvider

        return OpenAICompatProvider(
            model=settings.get("summarisation.cloud_model", ""),
            base_url=settings.get("summarisation.api_base_url", "https://openrouter.ai/api/v1"),
            api_key=_get_secret("summarisation.api_key", settings, ""),
            temperature=settings.get("summarisation.temperature", 0.6),
            max_tokens=settings.get("summarisation.max_output_tokens", 4096),
            timeout=LLM_REQUEST_TIMEOUT_S,
            retries=1,
            log_callback=log,
            label=provider.capitalize(),
        )
    elif provider == "freellmapi":
        from core.llm.openai_compat_provider import OpenAICompatProvider

        return OpenAICompatProvider(
            model=settings.get("summarisation.freellmapi_model", "auto"),
            base_url=settings.get("summarisation.freellmapi_url", "http://localhost:3001/v1"),
            api_key=_get_secret("summarisation.freellmapi_key", settings, ""),
            temperature=settings.get("summarisation.temperature", 0.6),
            max_tokens=settings.get("summarisation.max_output_tokens", 4096),
            timeout=LLM_REQUEST_TIMEOUT_S,
            retries=1,
            log_callback=log,
            label="FreeLLMAPI",
        )
    elif provider == "claude":
        from core.llm.claude_provider import ClaudeProvider

        return ClaudeProvider(
            model=settings.get("summarisation.claude_model", "claude-3-5-sonnet-20241022"),
            api_key=_get_secret("summarisation.claude_api_key", settings, ""),
            base_url=settings.get("summarisation.claude_base_url", "https://api.anthropic.com/v1"),
            temperature=settings.get("summarisation.temperature", 0.6),
            max_tokens=settings.get("summarisation.max_output_tokens", 4096),
            timeout=SLOW_LLM_TIMEOUT_S,
            retries=1,
            log_callback=log,
        )
    else:
        # Default to ollama
        return create_provider("ollama", settings, log_callback, supervisor)


# V18.20.1.1 (hotfix): lazy module-level __getattr__ for backward compat.
# ``from core.llm.llm_provider_impl import OllamaProvider`` triggers this
# __getattr__, which imports the provider module on demand — breaking the
# circular import. The provider modules are only loaded when someone actually
# accesses the name, not when llm_provider_impl itself loads.
_LAZY_PROVIDER_NAMES = {
    "OllamaProvider": "core.llm.ollama_provider",
    "LlamaCppProvider": "core.llm.llamacpp_provider",
    "OpenAICompatProvider": "core.llm.openai_compat_provider",
    "ClaudeProvider": "core.llm.claude_provider",
}


def __getattr__(name: str):
    """Lazy-load provider classes on first access (breaks circular import)."""
    if name in _LAZY_PROVIDER_NAMES:
        import importlib

        mod = importlib.import_module(_LAZY_PROVIDER_NAMES[name])
        cls = getattr(mod, name)
        # Cache on the module so subsequent accesses don't re-import
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
