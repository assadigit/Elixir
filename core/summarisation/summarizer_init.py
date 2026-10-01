"""V0.18 (Phase 5.1, step 5) — Summarizer sub-constructors.

The eight ``_init_*`` sub-constructor methods (provider config, runtime
basics, coverage/counters, thermal guard, max-workers, quarantine,
map-reduce/prompts, quality params) moved out of summarizer.py.
``__init__`` itself and the TLS property block stay in summarizer.py
(``_chapter_tls_store`` hard-references ``Summarizer._TLS_CREATE_LOCK``).

Moved VERBATIM (byte-identical bodies) from ``summarizer.py`` during the
V0.18 Phase 5.1 de-monolithization, re-homed via the house mixin pattern
(cf. additive_sections / chapter_phases). ``SummarizerInitMixin`` joined the
Summarizer bases; every ``self.<attr>`` / ``self.<method>`` reference
resolves exactly as before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.llm import ModelManager
from core.llm.model_taxonomy import LEGACY_DEFAULT_MODEL
from core.system.ollama_supervisor import OllamaSupervisor
from core.system.timeouts import LONG_RUN_TIMEOUT_S
from utils.logging import get_main_logger
from utils.settings import Settings

# The SAME logger object summarizer.py's module-level ``logger`` holds.
logger = get_main_logger()


class SummarizerInitMixin:
    """See the module docstring."""

    # V18.20.4.7 (P5 / O-a2): the additive-sections machinery and the
    # thorough-theorist floor now live in their own modules, re-homed
    # via these mixins (method bodies byte-identical to the V18.20.4.6
    # zip). External importers of Summarizer are unaffected.
    # V18.16.0.0 (Phase 2b): Sub-constructor for LLM provider config.
    # Extracted from __init__ (was lines 237-284, ~50 lines, ~30 attrs).
    # This is the SAFE reduction path — internal method on `self`, NOT an
    # external module extraction (which caused the V18.6.3 crash via a
    # PromptContext context object). Sub-constructors use the SAME `self`
    # namespace — same attribute resolution, same dict mutation order.
    def _init_provider_config(self, settings) -> None:
        """V18.16.0.0: Initialize LLM provider config (cloud, Claude, FreeLLMAPI, fusion).

        Extracted verbatim from ``__init__`` (Phase 2b, DEBT-13). The 30 attrs
        set here are in the EXACT same order as the original __init__ code.
        The ``settings`` param is the ``Settings()`` instance created in __init__
        (line 236) — passed explicitly to avoid re-reading settings.json.

        Sets: provider, api_key, api_base_url, cloud_model, cloud_max_tokens,
        claude_*, freellmapi_*, fusion_* (11 attrs), + provider override.
        """
        self.provider = settings.get("summarisation.provider", "ollama")

        # V10.36.0: API keys now go through the keyring-backed secrets manager.
        try:
            from core.system.secrets import get_secret

            def _get(path: str, default: str = "") -> str:
                return get_secret(path, settings, default)
        except ImportError:

            def _get(path: str, default: str = "") -> str:  # noqa: F811
                return settings.get(path, default)

        # Cloud / OpenAI-compatible settings
        self.api_key = _get("summarisation.api_key", "")
        self.api_base_url = settings.get(
            "summarisation.api_base_url", "https://openrouter.ai/api/v1"
        )
        self.cloud_model = settings.get(
            "summarisation.cloud_model", "google/gemini-2.5-flash-preview:free"
        )
        self.cloud_max_tokens = settings.get("summarisation.cloud_max_tokens", 16000)

        # Claude (Anthropic) settings
        self.claude_api_key = _get("summarisation.claude_api_key", "")
        self.claude_model = settings.get("summarisation.claude_model", "claude-3-5-sonnet-20241022")
        self.claude_base_url = settings.get(
            "summarisation.claude_base_url", "https://api.anthropic.com/v1"
        )
        self.claude_max_tokens = settings.get("summarisation.claude_max_tokens", 4096)

        # FreeLLMAPI
        self.freellmapi_url = settings.get(
            "summarisation.freellmapi_url", "http://localhost:3001/v1"
        )
        self.freellmapi_key = _get("summarisation.freellmapi_key", "")
        self.freellmapi_model = settings.get("summarisation.freellmapi_model", "auto")

        # V0.04: llama.cpp server (llama-server) — the local backend that
        # replaces Ollama on the rig. Read once here; the _call_llm
        # dispatch routes "llamacpp" through _call_via_llm_provider, and
        # create_provider("llamacpp") re-reads the same keys (single source
        # of truth: the llamacpp_* settings block).
        self.llamacpp_base_url = settings.get(
            "summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1"
        )
        # V0.16 (Phase 3 / 3.2): llamacpp key now routes through the same
        # keyring-backed ``_get`` wrapper as the cloud keys above (was a
        # plaintext settings.get — the one key this __init__ missed).
        self.llamacpp_api_key = _get("summarisation.llamacpp_api_key", "local")
        self.llamacpp_model = settings.get(
            "summarisation.llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision"
        )
        self.llamacpp_context_tokens = int(
            settings.get("summarisation.llamacpp_context_tokens", 65536) or 65536
        )
        self.llamacpp_max_output = int(
            settings.get("summarisation.llamacpp_max_output_tokens", 12288) or 12288
        )

        # V13.36.0: Hybrid Fusion (Local + Cloud)
        self.fusion_enabled = self.provider == "fusion" or settings.get(
            "summarisation.fusion_enabled", False
        )
        self.fusion_cloud_provider = settings.get(
            "summarisation.fusion_cloud_provider", "openai_compat"
        )
        self.fusion_cloud_model = settings.get("summarisation.fusion_cloud_model", self.cloud_model)
        self.fusion_cloud_api_key = _get("summarisation.fusion_cloud_api_key", "") or self.api_key
        self.fusion_cloud_base_url = (
            settings.get("summarisation.fusion_cloud_base_url", "") or self.api_base_url
        )
        self.fusion_cloud_max_tokens = settings.get("summarisation.fusion_cloud_max_tokens", 4096)
        self.fusion_cloud_temperature = settings.get("summarisation.fusion_cloud_temperature", 0.2)
        self.fusion_use_for_self_review = settings.get(
            "summarisation.fusion_use_for_self_review", True
        )
        self.fusion_use_for_grounding = settings.get("summarisation.fusion_use_for_grounding", True)
        self.fusion_use_for_b3_judge = settings.get("summarisation.fusion_use_for_b3_judge", True)
        self.fusion_use_for_gap_fill = settings.get("summarisation.fusion_use_for_gap_fill", False)
        # When fusion is on, the primary provider is always Ollama (local)
        if self.fusion_enabled and self.provider == "fusion":
            self.provider = "ollama"  # primary calls go to local

    # V18.17.0.1 (Phase 2b): Sub-constructor for runtime basics (Group A).
    def _init_runtime_basics(self, request, log_callback, language, claim_extractor) -> None:
        """V18.17.0.1: Initialize runtime basics (request, log, model_manager, supervisor).

        Extracted verbatim from ``__init__`` (Phase 2b, DEBT-13). Sets 10 attrs.
        Has 2 external constructions: ModelManager() + OllamaSupervisor().
        The OllamaSupervisor lambda captures self.log (MUST be set before the supervisor).
        """
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.language = language
        self.model_manager = ModelManager()
        # V18.20.4.3 (P2 / W-c9, +1 same-class site found during the P2
        # sweep): canonical Ollama URL from settings — this value flows to
        # the LLM dispatcher, the OllamaSupervisor and the fast-LLM path;
        # the old hardcoded localhost silently split behavior on
        # remote-Ollama rigs. Fail-soft: Settings failure → localhost
        # (byte-identical behavior on local rigs).
        try:
            self.ollama_base_url = Settings().get_ollama_url()
        except Exception:
            self.ollama_base_url = "http://localhost:11434"
        self.timeout = LONG_RUN_TIMEOUT_S
        self.retries = 1
        self._streaming_enabled = bool(getattr(request, "_streaming_enabled", False))
        self._ollama_supervisor = OllamaSupervisor(
            url=self.ollama_base_url,
            max_consecutive_failures=3,
            log_callback=lambda msg, level="INFO": self.log(msg.strip(), level),
        )
        self._claim_extractor = claim_extractor
        # V18.20.3.7: per-conversion provenance identity. ONE run id per
        # Summarizer instance (= per conversion) is stamped onto every
        # SummaryResult and rendered into every output file (header comment
        # + COMPLETE sentinel) so any file on disk answers "which app
        # version and which run produced me?" — the V18.20.3.6 audit spent
        # two sessions proving file identity by cross-referencing log
        # internals; the files now say it themselves.
        try:
            from core.system.provenance import (
                get_app_version,
                make_run_id,
                run_started_iso,
            )

            self._run_id = make_run_id()
            self._app_version = get_app_version()
            self._run_started = run_started_iso()
        except Exception:
            self._run_id = ""
            self._app_version = ""
            self._run_started = ""

    # V18.17.0.1 (Phase 2b): Sub-constructor for coverage state + counters (Groups B1 + C).
    def _init_coverage_and_counters(self) -> None:
        """V18.17.0.1: Initialize coverage caches + mutable run-state counters.

        Extracted verbatim from ``__init__`` (Phase 2b, DEBT-13). Sets 5 attrs:
        judge_results, _coverage_cache, _verify_windows_cache,
        _synthetic_thorough_fallback_count, _leak_guard_fire_count.
        Pure literal assignments — no external calls, no branching.
        """
        self.judge_results: list[Any] = []
        self._coverage_cache: dict[str, tuple] = {}
        self._verify_windows_cache: dict[str, list] = {}
        self._synthetic_thorough_fallback_count: int = 0
        self._leak_guard_fire_count: int = 0

    # V18.17.0.1 (Phase 2b): Sub-constructor for thermal guard (Group F part 1).
    def _init_thermal_guard(self, settings) -> None:
        """V18.17.0.1: Initialize thermal guard settings (is_local, timeout, deadline).

        Extracted from Group F part 1. MUST be called BEFORE Group B (which
        reads self.is_local, self.timeout, self.local_chapter_deadline for the
        IQ2_S overrides). Does NOT read self.primary_model or self.heavy_model.
        """
        # V0.04: "llamacpp" is a LOCAL backend — VRAM recovery, thermal
        # guards, and local timeouts all apply to llama-server exactly as
        # they do to Ollama.
        self.is_local = self.provider in ("ollama", "lmstudio", "llamacpp", "fusion")
        self.local_vram_recovery_delay = settings.get("local.vram_recovery_delay_sec", 120)
        self.local_b4_section_cap = settings.get("local.b4_max_sections", 3)
        self.local_preflight_skip_temp = settings.get("local.preflight_skip_temp_c", 60)
        self.local_http_timeout = settings.get("local.http_timeout_sec", 600)
        self.local_chapter_deadline = settings.get("local.chapter_deadline_sec", 0)
        self._chapter_deadline_start: float | None = None
        if self.local_chapter_deadline > 0:
            self.log(
                f"    ⏱️ V18.2.15 Per-chapter deadline: {self.local_chapter_deadline}s "
                f"(chapters exceeding this will be logged + marked failed)",
                "INFO",
            )
        self.timeout = self.local_http_timeout if self.is_local else 300
        self.log(
            f"    🔧 HTTP timeout set to {self.timeout}s ({'local' if self.is_local else 'cloud'} mode)",
            "DEBUG",
        )

    # V18.17.0.1 (Phase 2b): Sub-constructor for max_workers + VRAM (Group F part 2).
    def _init_max_workers(self) -> None:
        """V18.17.0.1: Initialize max_workers + VRAM safeguards.

        Extracted from Group F part 2. MUST be called AFTER Group B (which
        sets self.primary_model and self.heavy_model). Reads both to determine
        safe worker count.
        """
        self.max_workers = getattr(self.request, "max_workers", 2)
        try:
            from core.vram_calculator import get_total_vram

            _total_vram_gb = get_total_vram()
            if _total_vram_gb and _total_vram_gb < 16 and self.max_workers > 1:
                self.log(
                    f"  ⚠️ max_workers capped to 1 (VRAM < 16 GB — parallel "
                    f"workers would OOM). Total VRAM: {_total_vram_gb:.1f} GB.",
                    "WARNING",
                )
                self.max_workers = 1
        except Exception as _e:
            self.log(
                f"  ℹ️ Could not query VRAM for max_workers cap ({type(_e).__name__}: {_e}).",
                "DEBUG",
            )
        if self.heavy_model and self.max_workers > 1:
            self.log(
                f"  ⚠️ Heavy model enabled – forcing max_workers from {self.max_workers} to 1 to prevent OOM.",
                "WARNING",
            )
            self.max_workers = 1
        model_lower = (self.primary_model or "").lower()
        # V18.20.4.12 (W-a10): dropped dead uppercase entries — model_lower is lowercased
        if any(k in model_lower for k in ("14b", "32b", "70b")):
            safe_max = 1
        elif any(k in model_lower for k in ("9b", "8b", "12b", "13b")):
            safe_max = 2
        else:
            safe_max = 4
        if self.max_workers > safe_max:
            self.log(
                f"  ⚠️ Model '{self.primary_model}' is large — reducing workers "
                f"from {self.max_workers} to {safe_max} to prevent VRAM OOM.",
                "WARNING",
            )
            self.max_workers = safe_max
        try:
            from core.vram_calculator import calculate_vram_budget, get_total_vram

            estimates, peak, total, _rec = calculate_vram_budget(
                summarization_model=self.primary_model or "",
                max_workers=self.max_workers,
            )
            if total:
                from core.vram_calculator import _estimate_model_vram

                per_worker = _estimate_model_vram(self.primary_model or "", "Summarization") * 0.6
                usable = total - 1.0
                base = peak - per_worker * (self.max_workers - 1) if self.max_workers > 1 else peak
                affordable = self.max_workers
                if per_worker > 0:
                    while affordable > 1 and base + per_worker * (affordable - 1) > usable:
                        affordable -= 1
                if affordable < self.max_workers:
                    self.log(
                        f"  💾 VRAM budget: {peak:.1f} GB peak / {total:.1f} GB total "
                        f"— silently reducing workers {self.max_workers} → {affordable} "
                        f"to stay within VRAM.",
                        "INFO",
                    )
                    self.max_workers = affordable
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # V18.17.0.0 (Phase 2b): Sub-constructor for quarantine state (Group D).
    # Extracted from __init__ (was lines 265-293, ~30 lines, 3 attrs).
    def _init_quarantine(self) -> None:
        """V18.17.0.0: Initialize quarantine state (conservative_drops, quarantine log).

        Extracted verbatim from ``__init__`` (Phase 2b, DEBT-13). The 3 attrs
        are in the EXACT same order as the original __init__ code. Reads
        ``self.request`` + ``self.log`` (both set in Group A / _init_runtime_basics).
        """
        from core.summarisation.quarantine import (
            DEFAULT_RECOVERY_THRESHOLD,
            QuarantineLog,
        )

        self.conservative_drops = bool(getattr(self.request, "conservative_drops", False))
        _out_dir = getattr(self.request, "output_dir", None)
        self.quarantine = QuarantineLog(
            output_dir=_out_dir,
            recovery_threshold=DEFAULT_RECOVERY_THRESHOLD,
            log_callback=self.log,
        )
        self._last_quarantined: list[tuple] = []
        if self.conservative_drops:
            self.log(
                "  🛡️ Conservative drop mode ENABLED — only thinking/prompt-leakage "
                "bullets will be removed. All other drops are logged to quarantine "
                "but kept in the output. Recovery pass will run after all drops.",
                "INFO",
            )

    # V18.17.0.0 (Phase 2b): Sub-constructor for map-reduce params + prompt bank (Group H).
    # Extracted from __init__ (was lines 707-715 + 790-796, ~15 lines, 6 attrs).
    def _init_map_reduce_and_prompts(self, settings) -> None:
        """V18.17.0.0: Initialize map-reduce params + cache dir + prompt bank.

        Extracted verbatim from ``__init__`` (Phase 2b, DEBT-13). The 6 attrs
        are in the EXACT same order as the original __init__ code. The
        ``settings`` param is the ``Settings()`` instance (same as _init_provider_config).
        Has filesystem side effects (mkdir for cache_dir + load_prompt for prompt bank).
        """
        # Cache for Map-Reduce mini-summaries (resumable)
        self.cache_dir = Path.home() / ".elixir" / "summary_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Map-Reduce parameters
        self.MAP_CHUNK_TOKENS = 4000
        self.MAP_CHUNK_OVERLAP = 0.10
        self.MAP_REDUCE_THRESHOLD = 40000
        self.MAP_MINI_WORDS = 300
        # Prompt Bank (A1: user-editable prompts)
        from core.summarisation.prompt_manager import PromptManager

        self.prompt_manager = PromptManager()
        self.active_prompt = settings.get("summarisation.prompt", "default")
        if not self.prompt_manager.load_prompt(self.active_prompt):
            self.active_prompt = "default"

    def _init_quality_params(self, settings) -> None:
        """V18.19.3.0 (Phase 2f): Initialize quality parameters + model profile.

        Extracted verbatim from ``__init__`` Group B (lines 408-596 of the
        pre-V18.19.3.0 code). The characterization tests in
        ``tests/test_group_b_characterization.py`` lock the 13 load-bearing
        decisions this method makes:

          1. IQ2_S overrides (V18.15.4.0 + V18.15.6.0): deadline 2400s, timeout 1200s
          2. IQ2_XXS overrides (V18.2.33): timeout 300s, deadline 1200s
          3. max_output_tokens cap (V18.2.37d / V18.3.6): 8192 for low-bit/small
          4. max_output_tokens force: 16000 for full-precision large models
          5. max_bullets_per_chapter = 99999 (V13.45.5 — no cap)
          6. primary_model default: "gemma3:12b" when empty
          7. academic_rigor auto-enable (academic_paper + large full-precision)
          8. academic_rigor NOT auto-enabled for low-bit/small
          9. compact_summaries cap (min(orig, 2048)) — LATENT BUG D10: defeated
             by the 16000-force for large models (locked as current behavior)
          10. overdeliver_target clamping ([coverage_threshold, 1.0])
          11. model profile assignment (Qwen → thinking_strip_aggressive)
          12. heavy_model fallback (heavy == primary → None)
          13. per-model temperature enforcement (model_temperatures setting)

        Ordering constraints (documented in __init__ comments):
          - MUST come AFTER _init_thermal_guard (reads self.is_local, self.timeout,
            self.local_chapter_deadline).
          - MUST come BEFORE _init_max_workers + _init_map_reduce_and_prompts
            (which read self.primary_model + self.heavy_model set here).

        Args:
            settings: the ``Settings()`` instance created in __init__ (passed
                explicitly to avoid re-reading settings.json).
        """
        # Quality parameters from request
        self.temperature = getattr(self.request, "temperature", 0.2)
        self.self_consistency = getattr(self.request, "self_consistency", False)
        self.fast_model = getattr(
            self.request, "fast_model", "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest"
        )
        self.heavy_model = getattr(self.request, "heavy_model", "")
        self.coverage_threshold = getattr(self.request, "coverage_threshold", 0.70)

        from core.llm.content_presets import get_content_preset

        _preset = get_content_preset(getattr(self.request, "source_type", "normal_book"))
        if self.coverage_threshold == 0.70:
            self.coverage_threshold = _preset.coverage_threshold
        self.overdeliver_enabled = bool(getattr(self.request, "overdeliver_enabled", True))
        _od_target = float(getattr(self.request, "overdeliver_target", 1.0))
        self.overdeliver_target = max(self.coverage_threshold, min(_od_target, 1.0))
        self.b3_voting_enabled = bool(getattr(self.request, "b3_voting_enabled", False))
        self._effective_target = (
            self.overdeliver_target if self.overdeliver_enabled else self.coverage_threshold
        )
        self.content_preset = _preset

        # Academic Rigor flag
        self.academic_rigor = getattr(self.request, "academic_rigor", False)
        if not self.academic_rigor and getattr(self.request, "source_type", "") == "academic_paper":
            pass  # deferred to after primary_model assignment

        # Per-model temperature enforcement
        try:
            from utils import settings as _settings_mod

            _s = _settings_mod.Settings()
            _model_temps = _s.get("model_temperatures", {})
            if _model_temps:
                _model_lower = (getattr(self.request, "summarisation_model", "") or "").lower()
                for _pattern, (_min_t, _rec_t) in _model_temps.items():
                    if _pattern.lower() in _model_lower:
                        if self.temperature < _min_t:
                            self.log(
                                f"  🌡️ Model temperature {self.temperature} < minimum {_min_t} for {_pattern} — raising to {_rec_t}",
                                "INFO",
                            )
                            self.temperature = _rec_t
                        break
        except Exception as _e:
            logger.debug("model temperature enforcement failed: %s", _e)

        # Auto-detect context limit
        auto_ctx = self._auto_detect_context_limit()
        if self.request.summarisation_max_context_tokens <= 16000:
            self.request.summarisation_max_context_tokens = auto_ctx

        # Primary model
        # V18.20.4.11 (P2): literal → core.llm.model_taxonomy constant
        # (value unchanged: the LEGACY sentinel default "gemma3:12b").
        self.primary_model = self.request.summarisation_model or LEGACY_DEFAULT_MODEL

        # IQ2_S/IQ2_XXS overrides
        # V18.20.1.0 (D9): constants centralized to core.llm.iq2_s_profile.
        from core.llm.iq2_s_profile import IQ2_S_PROFILE
        from core.llm.model_taxonomy import is_iq2_s, is_low_bit_quant

        _is_slow_low_bit = is_low_bit_quant(self.primary_model) and not is_iq2_s(self.primary_model)
        if self.is_local and _is_slow_low_bit:
            if self.timeout > IQ2_S_PROFILE.IQ2_XXS_TIMEOUT_SEC:
                self.log(
                    f"    🔧 V18.2.33: HTTP timeout reduced {self.timeout}s → {IQ2_S_PROFILE.IQ2_XXS_TIMEOUT_SEC}s for IQ2_XXS",
                    "INFO",
                )
                self.timeout = IQ2_S_PROFILE.IQ2_XXS_TIMEOUT_SEC
            if (
                self.local_chapter_deadline > 0
                and self.local_chapter_deadline < IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC
            ):
                self.local_chapter_deadline = IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC
                self.log(
                    f"    ⏱️ V18.2.33: Chapter deadline raised → {IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC}s for IQ2_XXS",
                    "INFO",
                )

        if self.is_local and is_iq2_s(self.primary_model):
            if (
                self.local_chapter_deadline > 0
                and self.local_chapter_deadline < IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC
            ):
                self.local_chapter_deadline = IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC
                self.log(
                    f"    ⏱️ V18.15.4.0: Chapter deadline raised → {IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC}s for IQ2_S 27B",
                    "INFO",
                )
            if self.timeout > 0 and self.timeout < IQ2_S_PROFILE.HTTP_TIMEOUT_SEC:
                self.timeout = IQ2_S_PROFILE.HTTP_TIMEOUT_SEC
                self.log(
                    f"    🔧 V18.15.6.0: HTTP timeout raised → {IQ2_S_PROFILE.HTTP_TIMEOUT_SEC}s for IQ2_S 27B",
                    "INFO",
                )

        self._last_llm_error_type: str | None = None

        # Academic Rigor post-primary_model
        if not self.academic_rigor and getattr(self.request, "source_type", "") == "academic_paper":
            from core.llm.model_taxonomy import is_low_bit_quant, is_small_model, param_count_b

            _is_low_bit = is_low_bit_quant(self.primary_model)
            _param_count_b = param_count_b(self.primary_model)
            _is_small_model = is_small_model(self.primary_model)
            if _is_low_bit or _is_small_model:
                _reason = (
                    "low-bit quant (IQ2_XXS/XS)"
                    if _is_low_bit
                    else f"small model ({_param_count_b:.0f}B < 13B threshold)"
                )
                self.log(f"  ⚠️ Academic Rigor NOT auto-enabled — model uses a {_reason}", "WARNING")
            else:
                self.academic_rigor = True
                self.log("  🔬 Academic Rigor auto-enabled (source_type=academic_paper).", "INFO")
        if self.academic_rigor:
            self.log(
                f"  🔬 Academic Rigor mode enabled (temperature stays at {self.temperature})",
                "INFO",
            )

        # Model profile
        try:
            from core.llm.model_profiles import get_model_profile

            self.profile = get_model_profile(self.primary_model)
            self.log(f"  🎛️ Model profile: {self.profile.name}", "DEBUG")
            if self.profile.thinking_strip_aggressive:
                self._aggressive_thinking_strip = True
        except Exception:
            self.profile = None

        # Heavy model fallback
        if not self.heavy_model or self.heavy_model == self.primary_model:
            self.heavy_model = None
            self.log("  ℹ️ Heavy model fallback disabled (same as primary or empty).", "INFO")
        else:
            self.log(f"  ℹ️ Heavy model fallback set to: {self.heavy_model}", "INFO")

        # V18.17.0.1 (Phase 2b): Max_workers + VRAM (Group F part 2) extracted to
        # sub-constructor. MUST come AFTER Group B (which sets self.primary_model
        # and self.heavy_model).
        self._init_max_workers()

        # V18.17.0.0 (Phase 2b): Map-reduce params + prompt bank extracted to
        # sub-constructor. See _init_map_reduce_and_prompts for the full rationale.
        self._init_map_reduce_and_prompts(settings)

        # Ensure context is at least 32k (hardware floor for modern GPUs)
        if self.request.summarisation_max_context_tokens < 32768:
            self.request.summarisation_max_context_tokens = max(auto_ctx, 32768)
            self.log(
                f"  🔧 Raised summarisation context to {self.request.summarisation_max_context_tokens} tokens",
                "INFO",
            )

        # V0.09 (P5): ModelRegistry — the context window as DATA. The value
        # computed above (settings → VRAM ladder → 32k floor) stays the
        # FLOOR; a KNOWN model capability (llm.context_window_overrides >
        # /api/show probe > Modelfile num_ctx > static table > name hints)
        # can only ever RAISE it — e.g. the rig's 220k Ternary-Bonsai
        # llama.cpp model — never lower it (that decision belongs to P6's
        # strategy engine). Discovered values on local backends stay
        # bounded by the 220,144 cap and the VRAM ladder above; explicit
        # user values keep the pre-P5 never-ladder-reduced semantics. The
        # ctx_clamp/IQ2_S caps are NOT touched here — they remain the
        # post-cap layer at request time. With no overrides, no probe
        # success, and a model absent from the table/hints, this is a
        # no-op (byte-identical at today's defaults).
        from core.llm.registry import backend_for_provider, get_registry

        _reg = get_registry()
        _reg_backend = backend_for_provider(self.provider)
        _reg_ctx = _reg.get_context_window(
            self.primary_model,
            _reg_backend,
            base=self.request.summarisation_max_context_tokens,
            vram_limit_fn=self._auto_detect_context_limit,
        )
        if _reg_ctx != self.request.summarisation_max_context_tokens:
            self.log(
                f"  🧠 V0.09 (P5): model registry context window "
                f"{self.request.summarisation_max_context_tokens} → {_reg_ctx} "
                f"for '{self.primary_model}' ({_reg_backend} backend)",
                "INFO",
            )
            self.request.summarisation_max_context_tokens = _reg_ctx

        # ── Max bullets per chapter ──────────────────────────────────────
        # V13.45.5: REMOVED the hard-coded cap. The user explicitly requested:
        # "There must be no max bullets per chapter — bullets can be as many
        # as required. Chapter length is variable, so a hard-coded number is
        # not viable." Set to 99999 (effectively unlimited). The slicing
        # operations throughout the pipeline become no-ops.
        # The "Aim for N bullets" in prompts is GUIDANCE (not a cap) — it
        # helps the model calibrate output length but doesn't truncate.
        self.max_bullets_per_chapter = 99999

        # V10.20.0: Density-over-completeness mode — produce compact ~1000-token
        # summaries instead of the default ~2000+ tokens.  Inspired by
        # book-to-skill's principle: "Density over completeness — a 1,000-token
        # summary beats a 10,000-token excerpt."
        # V18.20.1.0 (D10 fix): track the compact cap so the 16000-force below
        # does NOT override it. The pre-V18.20.1.0 code applied compact (2048)
        # first, then the 16000-force for full-precision large models raised it
        # back to 16000 — defeating compact mode entirely. Now _compact_cap
        # gates the 16000-force: if compact_summaries is on, the cap survives.
        _compact_cap: int | None = None
        if getattr(self.request, "compact_summaries", False):
            _compact_cap = IQ2_S_PROFILE.COMPACT_MAX_OUTPUT  # 2048
            self.request.summarisation_max_output_tokens = min(
                self.request.summarisation_max_output_tokens, _compact_cap
            )
            # V13.45.5: Even in compact mode, don't hard-cap bullets
            self.log(
                f"  📦 Compact summaries mode: max {_compact_cap} output tokens (no bullet cap)",
                "INFO",
            )

        # V18.2.37d (CRITICAL fix): Force max_output_tokens to 16000 ONLY if
        # the context window can fit it. For low-bit quants (IQ2_XXS, Q2_K)
        # with the 26758 context cap, 16000 output + ~11000 input = 27000
        # which OVERFLOWS the 26758 cap → the model returns empty.
        # For these models, cap output at 8192 (fits: 11000+8192=19192<26758).
        # The dedicated thorough call (V18.2.34) already uses min(16000, 8192).
        #
        # V18.2.39: Extended to also cap SMALL MODELS (<13B parameters).
        # Small models can't handle 16000-token output budgets — they run out
        # of attention capacity and produce prompt-leakage / empty responses.
        # The V18.2.38 conversion log showed Qwen3.8-9b-Q8 failing with
        # max_output_tokens=16000 (echoed prompt instructions instead of
        # following them). Cap at 8192 for small models regardless of quant.
        _current_max_tok = getattr(self.request, "summarisation_max_output_tokens", 16000)
        # V18.3 (Phase 1.1): replaced inline regex + param extraction with
        # model_taxonomy — single source of truth. Behavior identical for all
        # tested models (see tests/test_small_model_detection.py).
        from core.llm.model_taxonomy import is_low_bit_quant, is_small_model, param_count_b

        _model_name = getattr(self.request, "summarisation_model", "") or ""
        _is_low_bit = is_low_bit_quant(_model_name)
        _param_count_b2 = param_count_b(_model_name)
        _is_small_model = is_small_model(_model_name)
        if _is_low_bit or _is_small_model:
            # V18.3.6: REVERTED E2 (the VRAM-aware max_output raise).
            # The raise from 8192 → 12000 caused thermal-throttling timeouts on
            # the rig-test book (the gold-standard chapter that worked with 8192
            # in V18.2.44). 12000 output tokens = 47% more generation time → GPU
            # hit 80°C → thermal throttle → 300s timeout → model stall → FAILED.
            # The extra VRAM headroom is for CONTEXT (E1), not OUTPUT — more
            # output tokens = more generation time = more heat. Keep 8192.
            # Truncation on large chapters is handled by E3 (chunked output),
            # NOT by raising the per-call output cap.
            _safe_max = IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT  # 8192
            _reason2 = (
                "low-bit quant (26758 context cap)"
                if _is_low_bit
                else f"small model ({_param_count_b2:.0f}B < 13B threshold)"
            )
            if _current_max_tok > _safe_max:
                self.log(
                    f"  ⚠️ max_output_tokens was {_current_max_tok} — capping to {_safe_max} for {_reason2}",
                    "WARNING",
                )
                self.request.summarisation_max_output_tokens = _safe_max
                _current_max_tok = _safe_max
        else:
            # For full-precision large models: force to at least 16000 — UNLESS
            # compact_summaries is on (V18.20.1.0 D10 fix). The pre-V18.20.1.0
            # code unconditionally forced to 16000, which defeated compact mode
            # (compact set 2048, then this block raised it to 16000). Now the
            # compact cap survives — the user's explicit compact_summaries=True
            # request is respected for ALL model classes.
            if _current_max_tok < IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT and not _compact_cap:
                self.log(
                    f"  ⚠️ max_output_tokens was {_current_max_tok} (stale setting) — forcing to {IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT}",
                    "WARNING",
                )
                self.request.summarisation_max_output_tokens = IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT
                _current_max_tok = IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT
            elif _compact_cap and _current_max_tok > _compact_cap:
                # V18.20.1.0 (D10): compact mode active — don't force up to 16000.
                # The compact cap (2048) is the user's explicit choice; respect it.
                self.log(
                    f"  📦 Compact mode: keeping max_output at {_compact_cap} (not forcing to {IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT} for full-precision large model)",
                    "INFO",
                )
        self.log(
            f"  📝 Max output tokens: {_current_max_tok} (context: {getattr(self.request, 'summarisation_max_context_tokens', 32768)})",
            "INFO",
        )
