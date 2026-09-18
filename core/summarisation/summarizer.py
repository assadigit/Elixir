"""
Two-level summarisation with quality enhancements:
  - Fast model as primary, heavy model as optional fallback.
  - Self‑consistency (optional, disabled by default).
  - Chain‑of‑thought prompting.
  - Coverage guard with auto‑reprompt (limited retries).
  - Map‑Reduce for very large chapters (40k+ tokens).
  - FIX: bullet point extraction fallback from thorough/executive summary.
  - FIX: Use fast_model as primary, reduce retries, lower timeout.
  - NEW: Academic Rigor mode – temperature=0, self‑review, structured JSON with evidence.
  - NEW: Prompt avoids specific numbers (percentages, dosages, counts) to reduce hallucination.
  - NEW: Smart auto‑context detection based on available VRAM (16k/32k/64k).
  - NEW: Claude (Anthropic) API support via direct API call.
  - NEW: Sprint 3 – Parallel summarisation with VRAM‑aware safeguards.
    * Uses ThreadPoolExecutor for concurrent chapter processing.
    * If heavy_model is set, max_workers is forced to 1 to prevent OOM.
    * Progress callback reports per‑chapter completion.
  - FIX: Academic Rigor prompt now explicitly instructs model to extract facts, not describe the schema.
  - FIX: `_strip_thinking()` is called unconditionally on all summary strings before saving.
"""

import concurrent.futures
import logging
import re
import threading  # V18.20.3.12 (F821): quoted "threading.Event" annotation in summarize_chapters
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

# V18.20.4.12 (W-b15): structured progress line — the wizard's live quality
# dashboard parses this JSON line (JSON-first) instead of regex-matching
# the human "📊 Progress:" wording; the human line stays byte-identical.
from core.common.progress_events import progress_json_line

from core.llm import ModelManager
# V18.20.4.11 (P2 / W-a7 partial): single source of truth for the legacy
# default-model literal (de-duplication only — value byte-identical).
from core.llm.model_taxonomy import LEGACY_DEFAULT_MODEL

# V18.2.21 (Phase 2.4-retry): consolidated retry decorator + typed exceptions.
# Replaces the 4 duplicated `for attempt in range(self.retries + 1)` loops
# in this module (_call_ollama_nonstreaming, _call_openai_compat, _call_claude,
# and the two sleeps inside _call_claude's 429 branch).
from core.models import ConversionRequest, SummaryResult

# V18.20.4.7 (P5 / O-a2): additive-sections machinery mixin — the 5
# methods moved VERBATIM (byte-identical bodies) to
# core.summarisation.additive_sections.
from core.summarisation.additive_sections import SummarizerAdditiveMixin

from core.summarisation import llm_dispatcher as _ld

# V18.15.3 (Phase 5 Stage 3, Batch 4.2): B3 cloud-judge sample selection.
from core.summarisation.b3_judge import b3_cloud_judge as bj_b3_cloud_judge
from core.summarisation.bullet_consolidation import (
    consolidate_bullets as bc_consolidate_bullets,
)

# V18.11 (Phase 5 Stage 3, Batch 1.3 + 1.4): bullet consolidation (dedup + LLM merge).
from core.summarisation.bullet_consolidation import (
    consolidate_duplicate_claims as bc_consolidate_duplicate_claims,
)

# V18.11 (Phase 5 Stage 3, Batch 1.2): bullet quality scorer (0-100).
from core.summarisation.bullet_scorer import score_bullet as bs_score_bullet

# V18.15.3 (Phase 5 Stage 3, Batch 4.5): 3-Tier coverage guarantee.
from core.summarisation.coverage_guarantee import apply_3tier_coverage as cg_apply_3tier_coverage

# V0.06 (rig audit F4-b): the source-scaled bullet budget (single source of
# truth: length_policy.bullet_target) as a hard-cap helper for the delegates.
from core.summarisation.length_policy import (
    bullet_cap as _lp_bullet_cap_mod,
    count_source_words as _lp_count_source_words_mod,
)


def _lp_bullet_cap_fn(source_text: str) -> int | None:
    """Hard bullet cap for a chapter of this size (length_policy.bullet_cap).

    ``None`` (never a number) on any failure — every consumer treats
    ``None``/``<= 0`` as "no cap" so a probe crash can never zero out a
    chapter's bullets (fail-open, same contract as the other budget probes).
    """
    try:
        return _lp_bullet_cap_mod(_lp_count_source_words_mod(source_text or ""))
    except Exception:
        return None

# V18.15.3 (Phase 5 Stage 3, Batch 4.4): fast/small-model LLM dispatch.
from core.summarisation.fast_llm import call_fast_llm as fl_call_fast_llm

# V18.15.3 (Phase 5 Stage 3, Batch 4.6): bullet thinking/narrative filter.
from core.summarisation.filter_thinking import filter_thinking_bullets as ft_filter_thinking_bullets

# V18.20.2.0 (SWOT A5): shared Qwen-family /no_think injection helper for
# the direct _call_llm sites (self-review, coverage reprompt) that bypass
# the V18.2.41 injection in _call_llm_with_empty_retry.
from core.summarisation.filter_thinking import qwen_no_think

# V18.20.3.12 (Phase 4 / W6-O5): batch gap-fill loop (V18.14.1 bullets-only
# coverage guarantee) — extracted from the _summarize_inner judge block.
from core.summarisation.gap_fill_batch import batch_gap_fill as gfb_batch_gap_fill

# V18.12 (Phase 5 Stage 3, Batch 2.7): concept gap-fill (targeted LLM calls for uncovered concepts).
from core.summarisation.gap_filler import gap_fill_concepts as gf_gap_fill_concepts

# V18.15.3 (Phase 5 Stage 3, Batch 4.3): LLM-as-judge grounding check.
from core.summarisation.grounding_check import llm_grounding_check as gc_llm_grounding_check
from core.summarisation.llm_dispatcher import (
    call_claude as ld_call_claude,
)
from core.summarisation.llm_dispatcher import (
    call_fast_ollama as ld_call_fast_ollama,
)
from core.summarisation.llm_dispatcher import (
    call_ollama as ld_call_ollama,
)
from core.summarisation.llm_dispatcher import (
    call_openai_compat as ld_call_openai_compat,
)
from core.summarisation.llm_dispatcher import (
    call_via_llm_provider as ld_call_via_llm_provider,
)

# V18.11 (Phase 5 Stage 3, Batch 2.1 + 2.5): map-reduce summarization.
from core.summarisation.map_reduce import (
    map_reduce_summarize as mr_map_reduce_summarize,
)
from core.summarisation.map_reduce import (
    section_map_reduce as mr_section_map_reduce,
)

# V18.11 (Phase 5 Stage 3, Batch 2.2): multi-sample (B3) summarization + voting.
from core.summarisation.multi_sample import multi_sample_summarize as ms_multi_sample_summarize

# V18.20.4.8 (P6 / O-a5): the single canonical structural-stopwords module
# (fixes W-a5's 3 drifting hand-curated copies; the class-level literal
# below is now an alias of this import — membership byte-identical).
from core.summarisation.structural_stopwords import STRUCTURAL_FUNCTION_WORDS

# V18.15.3 (Phase 5 Stage 3, Batch 4.7): primary summarization call.
from core.summarisation.primary_call import summarize_with_model as pc_summarize_with_model

# V18.15 (Phase 5 Stage 3, Batch 3.1): quarantine recovery pass.
from core.summarisation.quarantine_recovery import recover_quarantined as qr_recover_quarantined
from core.summarisation.response_parser import (
    extract_bullets_from_text as _rp_extract_bullets,
)
from core.summarisation.response_parser import (
    extract_sentences_as_bullets as _rp_extract_sentences_as_bullets,
)
from core.summarisation.response_parser import (
    parse_response as _rp_parse_response,
)
from core.summarisation.response_parser import (
    strip_markup_tags as _rp_strip_markup_tags,
)
from core.summarisation.response_parser import (
    strip_narrative_from_thorough as _rp_strip_narrative,
)
from core.summarisation.response_parser import (
    strip_thinking as _rp_strip_thinking,
)
from core.summarisation.response_parser import (
    truncate_to_sentences as _rp_truncate_to_sentences,
)

# V18.12 (Phase 5 Stage 3, Batch 2.6): scholar reflection (meta-cognitive gap analysis + gap-fill).
from core.summarisation.scholar_reflection import (
    scholar_reflection as scr_scholar_reflection,
)
from core.summarisation.scholar_reflection import (
    scholar_reflection_gapfill_only as scr_scholar_reflection_gapfill_only,
)

# V18.11 (Phase 5 Stage 3, Batch 2.4): batched self-review.
from core.summarisation.self_review import self_review_batched as sr_self_review_batched

# V18.15.3 (Phase 5 Stage 3, Batch 4.1): structured (JSON) LLM output.
from core.summarisation.structured_llm import call_llm_structured as sl_call_llm_structured
from core.summarisation.summary_validator import (
    anti_false_precision_check as sv_anti_false_precision_check,
)
from core.summarisation.summary_validator import (
    compute_coverage as sv_compute_coverage,
)
from core.summarisation.summary_validator import (
    normalize_empty_section as sv_normalize_empty_section,
)
from core.summarisation.summary_validator import (
    semantic_dedup_bullets as sv_semantic_dedup_bullets,
)
from core.summarisation.summary_validator import (
    verify_additive_section_item as sv_verify_additive_section_item,
)
from core.summarisation.summary_validator import (
    verify_additive_sections as sv_verify_additive_sections,
)
from core.summarisation.summary_validator import (
    verify_bullets as sv_verify_bullets,
)

# V18.11 (Phase 5 Stage 3, Batch 1.1): smart-truncation text utility.
from core.summarisation.text_utils_ext import smart_truncate as tue_smart_truncate

# V18.11 (Phase 5 Stage 3, Batch 2.3): dedicated thorough call + 3-attempt fallback.
from core.summarisation.thorough_fallback import (
    call_dedicated_thorough_with_fallback as tf_call_dedicated_thorough_with_fallback,
)

# V18.20.4.7 (P5 / O-a2): thorough-theorist floor mixin (V18.20.3.13)
# — _thorough_theorist_floor moved VERBATIM to
# core.summarisation.thorough_theorist_floor.
from core.summarisation.thorough_theorist_floor import (
    SummarizerThoroughFloorMixin,
)

from core.system.ollama_supervisor import OllamaSupervisor

# V18.2.14 (B4): traceable error-handling helpers — replace silent
# ``except Exception: pass`` with ``log_swallow()`` so failures leave a
# permanent, searchable log trace (operation name + exc type + traceback).
from utils.error_trace import log_swallow
from utils.logging import get_main_logger
from utils.settings import Settings
from utils.token_counter import count_tokens

logger = get_main_logger()


class Summarizer(SummarizerAdditiveMixin, SummarizerThoroughFloorMixin):
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
            _get = lambda path, default="": get_secret(path, settings, default)
        except ImportError:
            _get = lambda path, default="": settings.get(path, default)

        # Cloud / OpenAI-compatible settings
        self.api_key = _get("summarisation.api_key", "")
        self.api_base_url = settings.get("summarisation.api_base_url", "https://openrouter.ai/api/v1")
        self.cloud_model = settings.get("summarisation.cloud_model", "google/gemini-2.5-flash-preview:free")
        self.cloud_max_tokens = settings.get("summarisation.cloud_max_tokens", 16000)

        # Claude (Anthropic) settings
        self.claude_api_key = _get("summarisation.claude_api_key", "")
        self.claude_model = settings.get("summarisation.claude_model", "claude-3-5-sonnet-20241022")
        self.claude_base_url = settings.get("summarisation.claude_base_url", "https://api.anthropic.com/v1")
        self.claude_max_tokens = settings.get("summarisation.claude_max_tokens", 4096)

        # FreeLLMAPI
        self.freellmapi_url = settings.get("summarisation.freellmapi_url", "http://localhost:3001/v1")
        self.freellmapi_key = _get("summarisation.freellmapi_key", "")
        self.freellmapi_model = settings.get("summarisation.freellmapi_model", "auto")

        # V0.04: llama.cpp server (llama-server) — the local backend that
        # replaces Ollama on the rig. Read once here; the _call_llm
        # dispatch routes "llamacpp" through _call_via_llm_provider, and
        # create_provider("llamacpp") re-reads the same keys (single source
        # of truth: the llamacpp_* settings block).
        self.llamacpp_base_url = settings.get(
            "summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1")
        self.llamacpp_api_key = settings.get("summarisation.llamacpp_api_key", "local")
        self.llamacpp_model = settings.get(
            "summarisation.llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision")
        self.llamacpp_context_tokens = int(
            settings.get("summarisation.llamacpp_context_tokens", 65536) or 65536)
        self.llamacpp_max_output = int(
            settings.get("summarisation.llamacpp_max_output_tokens", 12288) or 12288)

        # V13.36.0: Hybrid Fusion (Local + Cloud)
        self.fusion_enabled = self.provider == "fusion" or settings.get("summarisation.fusion_enabled", False)
        self.fusion_cloud_provider = settings.get("summarisation.fusion_cloud_provider", "openai_compat")
        self.fusion_cloud_model = settings.get("summarisation.fusion_cloud_model", self.cloud_model)
        self.fusion_cloud_api_key = _get("summarisation.fusion_cloud_api_key", "") or self.api_key
        self.fusion_cloud_base_url = settings.get("summarisation.fusion_cloud_base_url", "") or self.api_base_url
        self.fusion_cloud_max_tokens = settings.get("summarisation.fusion_cloud_max_tokens", 4096)
        self.fusion_cloud_temperature = settings.get("summarisation.fusion_cloud_temperature", 0.2)
        self.fusion_use_for_self_review = settings.get("summarisation.fusion_use_for_self_review", True)
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
        self.request  = request
        self.log      = log_callback or (lambda msg, level="INFO": None)
        self.language = language
        self.model_manager   = ModelManager()
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
        self.timeout  = 600
        self.retries  = 1
        self._streaming_enabled = bool(
            getattr(request, "_streaming_enabled", False)
        )
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
        self.log(f"    🔧 HTTP timeout set to {self.timeout}s ({'local' if self.is_local else 'cloud'} mode)", "DEBUG")

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
            self.log(f"  ⚠️ Heavy model enabled – forcing max_workers from {self.max_workers} to 1 to prevent OOM.", "WARNING")
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
                per_worker = _estimate_model_vram(
                    self.primary_model or "", "Summarization"
                ) * 0.6
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
        self.conservative_drops = bool(
            getattr(self.request, "conservative_drops", False)
        )
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

    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
        language: str = "en",
        claim_extractor: Any | None = None,
    ):
        # V18.20.4.11 (P2 / W-a1, T-a3): per-worker chapter-context store —
        # see the property shims right after __init__. MUST be the FIRST
        # assignment: sub-constructors (notably _init_thermal_guard, which
        # writes self._chapter_deadline_start) already touch the
        # thread-local-backed attributes.
        self._chapter_tls = threading.local()
        # V18.17.0.1 (Phase 2b): Runtime basics extracted to sub-constructor.
        self._init_runtime_basics(request, log_callback, language, claim_extractor)

        # V18.17.0.1 (Phase 2b): Coverage state + counters extracted to sub-constructor.
        self._init_coverage_and_counters()

        # V18.17.0.0 (Phase 2b): Quarantine state extracted to sub-constructor.
        self._init_quarantine()


        settings = Settings()
        # V18.16.0.0 (Phase 2b): LLM provider config extracted to sub-constructor.
        # See _init_provider_config for the full rationale + the 30 attrs it sets.
        self._init_provider_config(settings)

        # V18.17.0.1 (Phase 2b): Thermal guard (Group F part 1) extracted to sub-constructor.
        # MUST come BEFORE Group B (which reads self.is_local, self.timeout, self.local_chapter_deadline).
        self._init_thermal_guard(settings)

        # V18.19.3.0 (Phase 2f): Group B extracted to _init_quality_params (the
        # 8th sub-constructor). Characterization tests in
        # tests/test_group_b_characterization.py lock the 13 load-bearing
        # decisions (IQ2_S/IQ2_XXS overrides, max_output capping, academic_rigor
        # auto-enable, compact_summaries, overdeliver clamping, model profile,
        # heavy_model fallback, per-model temperature enforcement, etc.).
        # MUST come AFTER _init_thermal_guard (which sets self.is_local, self.timeout,
        # self.local_chapter_deadline) and BEFORE _init_max_workers +
        # _init_map_reduce_and_prompts (which read self.primary_model +
        # self.heavy_model).
        self._init_quality_params(settings)

    # ─────────────────────────────────────────────────────────────────────────
    # V18.20.4.11 (P2 / W-a1, T-a3): per-worker chapter context (thread-local)
    # ─────────────────────────────────────────────────────────────────────────
    # ``summarize_chapters`` runs ``process_chapter`` → ``_summarize_inner``
    # on ThreadPoolExecutor WORKER threads while every chapter writes its
    # context onto the single shared Summarizer instance. With >1 workers
    # those attributes RACE (the SWOT-21 shared-state inventory, deferred
    # there as "a per-worker thread-local is the full fix"):
    #   - ``_current_heading`` is read 6× by bullet_pipeline.py for
    #     drops.jsonl chapter attribution → with >1 workers, drop records
    #     could carry the WRONG chapter name;
    #   - ``_primary_thorough_cot_nuked`` / ``_primary_exec_cot_nuked`` /
    #     ``_thorough_is_synthetic`` are per-chapter flags whose :2853-2858
    #     reset was designed to stop chapter N leaking into chapter N+1 —
    #     but the reset itself raced under concurrency;
    #   - ``_last_coverage`` cross-contaminated the self-review skip
    #     decision (bullet_pipeline reads it per chapter);
    #   - ``_chapter_deadline_start`` measured every chapter from the MOST
    #     RECENT submission (under-approximation, admitted in the old
    #     submission-loop comment).
    #
    # The 7 attributes below are converted to property shims backed by a
    # per-instance ``threading.local`` — NO call-site changes: every
    # existing read/write syntax (``self._current_heading = heading``,
    # ``getattr(s, "_current_heading", "")``) works unchanged, and the
    # getters NEVER raise AttributeError (they getattr-with-default inside,
    # matching each reader's previous fallback value).
    #
    # Thread-affinity audit (why each attribute is safe to localize):
    #   - ALL readers/writers run on the chapter-processing thread.
    #     ``_summarize_inner`` writes them at its top and reads them in the
    #     postchecks re-derivation block (same call frame);
    #     bullet_pipeline / filter_thinking / multi_sample / gap_filler read
    #     them from within that frame; ``_deadline_exceeded`` and
    #     ``_map_reduce_summarize`` are likewise called only from inside
    #     chapter processing. No post-futures MAIN-thread reader exists
    #     (verified tree-wide grep — ui_qt/, controller and
    #     conversion/summarization.py never touch these attrs).
    #   - The SEQUENTIAL path (max_workers == 1) is unchanged: the main
    #     thread both writes (summarize_chapters, pre-call) and reads
    #     (``_summarize_inner`` runs on the same thread) — TLS resolves to
    #     the same slot naturally.
    #   - ``_chapter_deadline_start``: the parallel-path stamp moved INTO
    #     ``process_chapter`` (each worker stamps at pickup — exact
    #     per-chapter elapsed time, strictly more correct than the old
    #     under-approximation). A main-thread-only pre-submit write would
    #     leave workers seeing the None default = deadline silently
    #     disabled (that would be a regression, not a fix).
    #   - bullet_pipeline.py needs NO changes: its ``getattr(s, ...)``
    #     reads resolve through these properties transparently.
    _TLS_CREATE_LOCK = threading.Lock()

    def _chapter_tls_store(self) -> threading.local:
        """This instance's thread-local chapter-context store (V18.20.4.11).

        Created eagerly in ``__init__``; the lazy double-checked path below
        only serves test harnesses that build the Summarizer via
        ``object.__new__`` (bypassing ``__init__``, the established
        characterization-test pattern) — where the first access can happen
        on a worker thread, hence the lock.
        """
        tls = getattr(self, "_chapter_tls", None)
        if tls is None:
            with Summarizer._TLS_CREATE_LOCK:
                tls = getattr(self, "_chapter_tls", None)
                if tls is None:
                    tls = threading.local()
                    self._chapter_tls = tls
        return tls

    @property
    def _source_text(self) -> str:
        return getattr(self._chapter_tls_store(), "source_text", "")

    @_source_text.setter
    def _source_text(self, value: str) -> None:
        self._chapter_tls_store().source_text = value

    @property
    def _current_heading(self) -> str:
        return getattr(self._chapter_tls_store(), "current_heading", "")

    @_current_heading.setter
    def _current_heading(self, value: str) -> None:
        self._chapter_tls_store().current_heading = value

    @property
    def _primary_thorough_cot_nuked(self) -> bool:
        return getattr(self._chapter_tls_store(), "primary_thorough_cot_nuked", False)

    @_primary_thorough_cot_nuked.setter
    def _primary_thorough_cot_nuked(self, value: bool) -> None:
        self._chapter_tls_store().primary_thorough_cot_nuked = value

    @property
    def _primary_exec_cot_nuked(self) -> bool:
        return getattr(self._chapter_tls_store(), "primary_exec_cot_nuked", False)

    @_primary_exec_cot_nuked.setter
    def _primary_exec_cot_nuked(self, value: bool) -> None:
        self._chapter_tls_store().primary_exec_cot_nuked = value

    @property
    def _thorough_is_synthetic(self) -> bool:
        return getattr(self._chapter_tls_store(), "thorough_is_synthetic", False)

    @_thorough_is_synthetic.setter
    def _thorough_is_synthetic(self, value: bool) -> None:
        self._chapter_tls_store().thorough_is_synthetic = value

    @property
    def _last_coverage(self) -> float:
        return getattr(self._chapter_tls_store(), "last_coverage", 0.0)

    @_last_coverage.setter
    def _last_coverage(self, value: float) -> None:
        self._chapter_tls_store().last_coverage = value

    @property
    def _chapter_deadline_start(self) -> float | None:
        return getattr(self._chapter_tls_store(), "chapter_deadline_start", None)

    @_chapter_deadline_start.setter
    def _chapter_deadline_start(self, value: float | None) -> None:
        self._chapter_tls_store().chapter_deadline_start = value


    # ─────────────────────────────────────────────────────────────────────────
    # V18.19.3.0 (Phase 2f): Group B — quality params, academic rigor, per-model
    # temp, primary_model, IQ2_S/IQ2_XXS overrides, model profile, heavy-model
    # fallback, max_output capping, compact_summaries. The most complex __init__
    # group; extracted last because it needed characterization tests first
    # (delivered in V18.19.1.4). See tests/test_group_b_characterization.py.
    # ─────────────────────────────────────────────────────────────────────────

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
        self.fast_model = getattr(self.request, "fast_model", "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest")
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
            self.overdeliver_target if self.overdeliver_enabled
            else self.coverage_threshold
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
                            self.log(f"  🌡️ Model temperature {self.temperature} < minimum {_min_t} for {_pattern} — raising to {_rec_t}", "INFO")
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
                self.log(f"    🔧 V18.2.33: HTTP timeout reduced {self.timeout}s → {IQ2_S_PROFILE.IQ2_XXS_TIMEOUT_SEC}s for IQ2_XXS", "INFO")
                self.timeout = IQ2_S_PROFILE.IQ2_XXS_TIMEOUT_SEC
            if self.local_chapter_deadline > 0 and self.local_chapter_deadline < IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC:
                self.local_chapter_deadline = IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC
                self.log(f"    ⏱️ V18.2.33: Chapter deadline raised → {IQ2_S_PROFILE.IQ2_XXS_DEADLINE_SEC}s for IQ2_XXS", "INFO")

        if self.is_local and is_iq2_s(self.primary_model):
            if self.local_chapter_deadline > 0 and self.local_chapter_deadline < IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC:
                self.local_chapter_deadline = IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC
                self.log(f"    ⏱️ V18.15.4.0: Chapter deadline raised → {IQ2_S_PROFILE.CHAPTER_DEADLINE_SEC}s for IQ2_S 27B", "INFO")
            if self.timeout > 0 and self.timeout < IQ2_S_PROFILE.HTTP_TIMEOUT_SEC:
                self.timeout = IQ2_S_PROFILE.HTTP_TIMEOUT_SEC
                self.log(f"    🔧 V18.15.6.0: HTTP timeout raised → {IQ2_S_PROFILE.HTTP_TIMEOUT_SEC}s for IQ2_S 27B", "INFO")

        self._last_llm_error_type: str | None = None

        # Academic Rigor post-primary_model
        if not self.academic_rigor and getattr(self.request, "source_type", "") == "academic_paper":
            from core.llm.model_taxonomy import is_low_bit_quant, is_small_model, param_count_b
            _is_low_bit = is_low_bit_quant(self.primary_model)
            _param_count_b = param_count_b(self.primary_model)
            _is_small_model = is_small_model(self.primary_model)
            if _is_low_bit or _is_small_model:
                _reason = ("low-bit quant (IQ2_XXS/XS)" if _is_low_bit
                           else f"small model ({_param_count_b:.0f}B < 13B threshold)")
                self.log(f"  ⚠️ Academic Rigor NOT auto-enabled — model uses a {_reason}", "WARNING")
            else:
                self.academic_rigor = True
                self.log("  🔬 Academic Rigor auto-enabled (source_type=academic_paper).", "INFO")
        if self.academic_rigor:
            self.log(f"  🔬 Academic Rigor mode enabled (temperature stays at {self.temperature})", "INFO")

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
            self.log(f"  🔧 Raised summarisation context to {self.request.summarisation_max_context_tokens} tokens", "INFO")

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
            self.log(f"  📦 Compact summaries mode: max {_compact_cap} output tokens (no bullet cap)", "INFO")

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
            _reason2 = ("low-bit quant (26758 context cap)" if _is_low_bit
                        else f"small model ({_param_count_b2:.0f}B < 13B threshold)")
            if _current_max_tok > _safe_max:
                self.log(f"  ⚠️ max_output_tokens was {_current_max_tok} — capping to {_safe_max} for {_reason2}", "WARNING")
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
                self.log(f"  ⚠️ max_output_tokens was {_current_max_tok} (stale setting) — forcing to {IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT}", "WARNING")
                self.request.summarisation_max_output_tokens = IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT
                _current_max_tok = IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT
            elif _compact_cap and _current_max_tok > _compact_cap:
                # V18.20.1.0 (D10): compact mode active — don't force up to 16000.
                # The compact cap (2048) is the user's explicit choice; respect it.
                self.log(f"  📦 Compact mode: keeping max_output at {_compact_cap} (not forcing to {IQ2_S_PROFILE.LARGE_FP_MIN_OUTPUT} for full-precision large model)", "INFO")
        self.log(f"  📝 Max output tokens: {_current_max_tok} (context: {getattr(self.request, 'summarisation_max_context_tokens', 32768)})", "INFO")

        # V18.17.0.0 (Phase 2b): Prompt bank initialization moved to
        # _init_map_reduce_and_prompts (called above). No inline code here.

    # ─────────────────────────────────────────────────────────────────────────
    # V18.2.22 (BUG-4): Mid-generation deadline watchdog
    # ─────────────────────────────────────────────────────────────────────────

    def _deadline_exceeded(self, phase_name: str) -> bool:
        """Check if the per-chapter deadline is exceeded at a phase boundary.

        Called by ``_summarize_inner`` before optional phases (scholar
        reflection, semantic dedup, consolidation). When the deadline is
        exceeded, the phase is SKIPPED with a traceable WARNING so the
        conversion doesn't waste further time on a chapter that's already
        over budget.

        The V18.2.20 conversion log showed a chapter taking 1271s vs a 480s
        deadline. The post-hoc V18.2.15 WARNING fired correctly, but the 4
        optional phases AFTER the deadline (scholar reflection ~2.5 min,
        consolidation ~2.3 min) ran anyway — wasting ~5 min. This helper
        short-circuits them.

        Returns True if the deadline is exceeded (skip the phase), False
        otherwise (proceed). When there's no deadline (0) or no start time,
        returns False (never skip).
        """
        if not self.is_local or self.local_chapter_deadline <= 0:
            return False
        if self._chapter_deadline_start is None:
            return False
        elapsed = time.time() - self._chapter_deadline_start
        if elapsed > self.local_chapter_deadline:
            self.log(
                f"  ⏱️⚠️ Deadline exceeded ({elapsed:.0f}s > "
                f"{self.local_chapter_deadline}s) — skipping optional phase: "
                f"{phase_name}",
                "WARNING",
            )
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Auto‑context detection
    # ─────────────────────────────────────────────────────────────────────────

    def _auto_detect_context_limit(self) -> int:
        """
        Returns recommended context size (tokens) based on available VRAM.

        V10.23.0: Aggressive VRAM utilization. The user's RTX 3060 12GB
        with a 9B Q4 model (6.5GB weights) was only using 7.6/12GB VRAM.
        The old limits (64k for 12GB) left ~4GB unused. Now we target
        90% VRAM utilization:

        - Model weights: ~6.5 GB (9B Q4)
        - System/OS reserve: ~1.0 GB
        - Available for KV cache: 12 - 6.5 - 1.0 = 4.5 GB
        - KV cache per 1k tokens (9B model): ~0.03 GB
        - Max context = 4.5 / 0.03 = 150k → cap at 131072 (128k)

        Hardware guidance (V10.23.0 — aggressive):
        - < 8 GB VRAM:   32768   (small GPUs — 8k KV cache after 5GB model)
        - < 12 GB VRAM:  65536   (RTX 3060 12GB — ~3GB KV cache)
        - < 16 GB VRAM:  131072  (RTX 3060 12GB, RTX 4070 12GB — ~4.5GB KV cache)
        - < 24 GB VRAM:  131072  (RTX 3090/4090 24GB — ~10GB KV cache)
        - >= 24 GB VRAM: 262144  (RTX 4090 24GB+ — huge context)
        - No torch/CUDA: 65536   (sensible default)

        The V10.18.0 C5 "smart context" feature was COUNTERPRODUCTIVE — it
        REDUCED context to 8k/32k for short chapters, which actually
        slowed inference (Ollama re-allocates KV cache on each call).
        V10.23.0 removes the down-scaling and instead UP-scales to fill VRAM.
        """
        try:
            import torch
            if torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb < 8:
                    return 32768
                elif vram_gb < 12:
                    return 65536
                elif vram_gb < 16:
                    return 131072  # V10.23.0: was 65536 → 131072 (aggressive)
                elif vram_gb < 24:
                    return 131072
                else:
                    return 262144  # V10.23.0: was 131072 → 262144
            else:
                return 65536
        except ImportError:
            return 65536
        except Exception as _e:
            return 65536

    # ─────────────────────────────────────────────────────────────────────────
    # Keyword coverage (deterministic)
    # ─────────────────────────────────────────────────────────────────────────

    # V18.20.1.0 (D5): _STOPWORDS + _EXTRA_STOP DELETED. Hand-curated word lists
    # violate the V18.15.3.2 "no hand-curated word lists" constraint (the source
    # text is the only dictionary). The fallback path now derives stopwords from
    # the SOURCE TEXT's own frequency distribution (bottom-quartile TF + the
    # small structural-function-word set below). The golden path
    # (extract_ngram_keywords) was already source-grounded; only the fallback
    # used the hand-curated lists.
    #
    # The tiny _STRUCTURAL_FUNCTION_WORDS set below is grammatical glue (the/
    # a/and/of/is/was...), NOT a content dictionary. Exempt under V18.15.3.2
    # (which targets CONTENT word-lists, not function-word stopwords). Same
    # exemption as _STRUCTURAL_STOPWORDS in postcheck_detectors.py.
    # V18.20.4.8 (P6 / O-a5): the literal now lives in the single canonical
    # structural-stopwords module (fixes W-a5's 3 drifting copies); this
    # class attribute aliases it so self._STRUCTURAL_FUNCTION_WORDS (and
    # monkeypatching on it) keeps working unchanged.
    _STRUCTURAL_FUNCTION_WORDS = STRUCTURAL_FUNCTION_WORDS

    def _extract_keywords(self, text: str, n: int = 18) -> list[str]:
        """Extract top-n content keywords from text for coverage checking.

        A7: Now uses n-gram extraction (bigrams + trigrams) from the
        DeterministicPreprocessor. This captures multi-word concepts like
        "focus base", "hourglass conversation" that single-word extraction
        misses entirely. Falls back to the old single-word method if the
        preprocessor is unavailable.

        V18.20.1.0 (D5): the fallback path no longer uses hand-curated
        ``_STOPWORDS`` / ``_EXTRA_STOP`` lists (V18.15.3.2 constraint). Instead
        it derives stopwords from the source text's own frequency distribution:
        the bottom-quartile TF terms are treated as noise (too common to be
        content keywords). This is source-grounded — the source text is the
        only dictionary.
        """
        try:
            from core.summarisation.text_preprocessor import (
                extract_ngram_keywords,
                get_all_ner_entities,
            )
            keywords = extract_ngram_keywords(text, n=n)
            # Exclude NER entities (proper nouns) — book-derived names
            # are never listed here: the entities come from the source
            # text at runtime (V18.20.3.9 residuals-sweep rule).
            # from coverage keywords. These inflate the "missing" count without
            # indicating actual concept gaps.
            ner_entities = get_all_ner_entities(text)
            if ner_entities:
                keywords = [k for k in keywords if not any(
                    entity.lower() in k.lower() for entity in ner_entities
                )]
            return keywords
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Fallback: old single-word method, V18.20.1.0 (D5) source-grounded.
        # Derive stopwords from the text's OWN frequency distribution: words
        # appearing >= 5% of the total word count are too common to be content
        # keywords (they're structural glue). Plus the tiny
        # _STRUCTURAL_FUNCTION_WORDS set (the/a/and/of... — grammatical, not
        # content). No hand-curated content word list.
        words = re.findall(r'\b[a-z]{6,}\b', text.lower())
        if not words:
            return []
        total = len(words)
        counts: dict = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1
        # V18.20.1.0 (D5): source-grounded stopword derivation. A word is a
        # "stopword" (too common to be a content keyword) if it appears in
        # >= 5% of the text. This adapts per-book: "identity" in a chapter
        # about identity would be a stopword here (appears 50+ times), but a
        # content keyword in a chapter that mentions it once. The 5% threshold
        # is empirically calibrated: below it, a word is specific enough to be
        # a content keyword; above it, it's background noise.
        _freq_threshold = max(3, int(total * 0.05))
        _source_stopwords = {w for w, c in counts.items() if c >= _freq_threshold}
        content_words = [
            w for w, c in counts.items()
            if w not in self._STRUCTURAL_FUNCTION_WORDS
            and w not in _source_stopwords
        ]
        content_words.sort(key=lambda w: counts[w], reverse=True)
        return content_words[:n]

    def _compute_coverage(self, source: str, summary: str) -> float:
        """Return fraction of source keywords + concepts present in summary.

        V18.7 (Phase 5.2): extracted verbatim to ``summary_validator.compute_coverage``.
        This method is a thin delegate. The ``coverage_cache`` dict and
        ``_extract_keywords`` callable are passed by reference/callback.
        """
        return sv_compute_coverage(
            source=source,
            summary=summary,
            coverage_cache=self._coverage_cache,
            extract_keywords=self._extract_keywords,
        )
    def _build_prompt(
        self,
        heading: str,
        text: str,
        with_cot: bool = True,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
    ) -> str:
        """V18.6.4 (ROLLBACK of V18.6.3): _build_prompt is INLINE again.

        V18.6.3 extracted this to prompt_assembly.build_primary_prompt, but
        it caused a crash on the user's machine after clicking Process in
        the wizard. Rolling back to the inline version (the V18.6.1 code)
        to restore stability. V18.20.4.7 (P5 / W-a3): the dead twin that
        stayed behind in prompt_assembly.py after this rollback was
        deleted there — this inline builder is the only one.

        The 5 low-risk _build_* methods (thorough_followup, dedicated_thorough,
        dedicated_bullet, missing_keywords, chunked) REMAIN extracted — only
        the high-risk _build_prompt is rolled back.
        """
        lang = "Write your entire response in Persian (Farsi)." if self.language == "fa" else "Write your entire response in English."

        # V0.05 (rig audit F9a/F9b — the user's "I didn't ask for a thorough
        # summary but it produced" + "thorough longer than the chapter"):
        # the request's output-selection flags are THE CONTRACT — they were
        # previously logged (settings_logger) but never enforced here, so an
        # unchecked Thorough Summary was still demanded, generated, expanded
        # (the 800-word floor), and rendered. And every length target now
        # SCALES to the source (a summary section may never be instructed to
        # exceed a fraction of its source — absolute word demands force the
        # model to pad/invent for short chapters: hallucination-by-instruction).
        from core.summarisation.length_policy import (
            bullet_range_phrase,
            count_source_words,
            exec_words_phrase,
            length_budget_block,
            thorough_words_phrase,
        )
        _source_words = count_source_words(text)
        _exec_words = exec_words_phrase(_source_words)
        _bullet_range = bullet_range_phrase(_source_words)
        _thorough_words = thorough_words_phrase(_source_words)
        _inc_exec = bool(getattr(self.request, "include_executive_summary", True))
        _inc_thorough = bool(getattr(self.request, "include_thorough_summary", True))
        _inc_keypoints = bool(getattr(self.request, "include_keypoints", True))

        callout_block = ""
        if callouts:
            callout_list = "\n".join(f"  - \"{c}\"" for c in callouts[:10])
            callout_block = f"""
HIGH-VALUE CALLOUTS from the author (these appear as highlighted tips in the chapter — your summary MUST capture the concept behind each):
{callout_list}
"""
        structural_block = ""
        try:
            import re as _re_so
            _so_matches = _re_so.findall(
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((\d{4})',
                text[:200000],
            )
            _so_stop = {"The", "This", "These", "Those", "A", "An", "In",
                        "While", "When", "If", "It", "He", "She", "They",
                        "We", "Page", "Chapter", "Figure", "Table", "Note",
                        "See", "As", "For", "Later", "Also", "Then",
                        "However", "Moreover", "First", "Second", "Third"}
            _so_seen = set()
            _so_sequence = []
            for _name, _year in _so_matches:
                if _name in _so_stop or len(_name) < 3:
                    continue
                _key = f"{_name} ({_year})"
                if _key not in _so_seen:
                    _so_seen.add(_key)
                    _so_sequence.append(_key)
            if len(_so_sequence) >= 3:
                structural_block = f"""
STRUCTURAL OUTLINE — The source mentions these named contributors in this order:
{', '.join(_so_sequence[:20])}

Your THOROUGH SUMMARY must cover the FULL sequence above. Do NOT stop early —
narrate through the complete progression, ending with the source's conclusion.
If the source ends with an enumerated list or summary framework, your thorough
summary must reach that conclusion.
"""
        except Exception as _e:
            log_swallow("structural_outline_build", _e,
                        detail=f"heading={heading[:60]}")

        # V0.03 (P1-5, real-rig audit): ANTHOLOGY ATTRIBUTION. The V0.02 rig
        # summarized an 8-author extract with ZERO author names — for an
        # anthology, bylines are core content. GENERAL rule: when the chapter
        # text carries standalone "By <Name>" bylines, require the summary
        # to attribute ideas to their authors.
        # V0.05 (rig audit F5 — P1): the block fires at >=1 byline. The old
        # >=2 threshold could never fire for a PER-CHAPTER segment of an
        # anthology (exactly one byline), leaving attribution to model whim
        # — the V0.04 rig's chapter-2 output named Neal Ford only inside a
        # critique bullet. A byline is attribution content, full stop; the
        # multi-author framing text remains for >=2.
        attribution_block = ""
        try:
            from core.preprocessing.deterministic_analyzer import extract_bylines
            _bylines = extract_bylines(text[:200000])
            if len(_bylines) >= 2:
                attribution_block = (
                    "\nANTHOLOGY ATTRIBUTION — This section collects work by "
                    f"multiple named authors ({', '.join(_bylines[:12])}). "
                    "Attribute each idea to the author the source credits "
                    "(e.g. \"Nygard argues…\", \"per Braithwaite…\"). Do NOT "
                    "collapse multi-author sections into anonymous prose.\n"
                )
            elif len(_bylines) == 1:
                attribution_block = (
                    f"\nATTRIBUTION — This chapter is by {_bylines[0]}. Name "
                    f"the author in the summary prose (e.g. \"{_bylines[0].split()[-1]} "
                    "argues…\"); a chapter summary that never names its author "
                    "is incomplete.\n"
                )
        except Exception as _e:
            log_swallow("byline_attribution_build", _e,
                        detail=f"heading={heading[:60]}")

        try:
            from core.summarisation.text_preprocessor import calculate_reading_level
            _source_grade = calculate_reading_level(text[:5000])
            if _source_grade > 14:
                reading_level_instruction = """- Write for a specialist audience. Use technical terminology appropriate to the field. Maintain the academic register of the source."""
            elif _source_grade > 10:
                reading_level_instruction = """- Write for an educated general audience. Define technical terms on first use. Use clear, professional language."""
            else:
                reading_level_instruction = """"""
        except Exception as _e:
            reading_level_instruction = """
READING LEVEL REQUIREMENT (MANDATORY): Write for a non-native English reader at IELTS Reading level 7-9.
- Keep sentences under 20 words each. If a sentence is longer, split it into two.
- Use ACTIVE voice, not passive. "The author argues" not "It is argued by the author".
- Use common words. If you use a technical term or jargon, define it in plain words the first time it appears.
- Do NOT use idioms, metaphors, or culturally specific expressions a non-native reader may not know.
- Do NOT use words like "comprehensive", "methodology", "facilitate", "leverage", "utilize" — use "full", "method", "help", "use" instead.
- The summary MUST be EASIER to read than the source text, not harder.
- Write clearly and directly. Avoid academic jargon unless the source requires it.
"""
        if self.provider not in ("ollama", "lmstudio", "llamacpp", ""):
            reading_level_instruction += """
QUALITY (cloud model): You are a high-capability model. Go beyond extraction:
- Synthesise across paragraphs; show how ideas connect.
- Preserve the author's nuance and conditional statements ("however", "except when").
- Never invent facts, quotes, or examples not present in the source.
- If the source is ambiguous, say so explicitly rather than guessing.
"""

        if not self.academic_rigor:
            _active_prompt = self._select_prompt(self.active_prompt)
            rendered = self.prompt_manager.render(_active_prompt, heading, text, lang)
            if rendered:
                if callout_block:
                    inject = f"\n{callout_block}\n"
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace("Chapter content:", inject + "Chapter content:")
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace("{{text}}", inject + "{{text}}")
                    else:
                        rendered += inject
                if structural_block:
                    inject_so = f"\n{structural_block}\n"
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace("Chapter content:", inject_so + "Chapter content:")
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace("{{text}}", inject_so + "{{text}}")
                    else:
                        rendered += inject_so
                # V0.03 (P1-5): the anthology attribution block rides the
                # same injection path as callouts/structural outline.
                if attribution_block:
                    if "Chapter content:" in rendered:
                        rendered = rendered.replace(
                            "Chapter content:", attribution_block + "Chapter content:")
                    elif "{{text}}" in rendered:
                        rendered = rendered.replace(
                            "{{text}}", attribution_block + "{{text}}")
                    else:
                        rendered += attribution_block
                rendered += "\n" + reading_level_instruction
                rendered += "\nIMPORTANT: Only include specific numbers (percentages, dosages, counts, dates) if they appear VERBATIM in the source text. Do NOT invent, approximate, or round any numbers. If you are unsure whether a number is in the source, omit it."
                rendered += "\nANTI-HALLUCINATION: Use ONLY information from the source text. Do NOT add external knowledge, invented facts, or personal opinions. If you are unsure whether a claim is supported by the source, OMIT it."
                from core.llm.content_presets import get_content_preset
                _preset = get_content_preset(getattr(self.request, "source_type", "normal_book"))
                if _preset.prompt_addendum:
                    rendered += "\n" + _preset.prompt_addendum
                if _preset.tone_instruction:
                    rendered += "\n" + _preset.tone_instruction
                if _preset.preserve_domain_terms:
                    rendered += "\nDOMAIN TERMS: Preserve all technical/domain terminology exactly as written. Do NOT simplify or replace with common words."
                # V0.05 (F9a): strip the spec blocks of every section the user
                # did NOT select — an unrequested <thorough_summary> spec in
                # the prompt is what generated unrequested thorough sections
                # on the rig (the flag was logged but never enforced).
                if not _inc_exec:
                    rendered = re.sub(
                        r'<executive_summary>.*?</executive_summary>\s*',
                        '', rendered, flags=re.DOTALL,
                    )
                if not _inc_keypoints:
                    rendered = re.sub(
                        r'<bullet_points>.*?</bullet_points>\s*',
                        '', rendered, flags=re.DOTALL,
                    )
                if not _inc_thorough:
                    rendered = re.sub(
                        r'<thorough_summary>.*?</thorough_summary>\s*',
                        '', rendered, flags=re.DOTALL,
                    )
                _wanted = [
                    _t for _t, _on in (
                        ("<executive_summary>", _inc_exec),
                        ("<bullet_points>", _inc_keypoints),
                        ("<thorough_summary>", _inc_thorough),
                        ("<key_distinctions>", True),
                        ("<theoretical_tensions>", True),
                    ) if _on
                ]
                if len(_wanted) < 5:
                    rendered += (
                        "\nOUTPUT SECTIONS (OVERRIDES any section list above): "
                        "output ONLY these sections, in this order: "
                        + ", ".join(_wanted) + ".\n"
                    )
                # V0.05 (F9b): the source-relative length budget — appended to
                # EVERY rendered template so the scaled targets override any
                # absolute numbers a user-edited template still carries.
                rendered += "\n" + length_budget_block(
                    _source_words,
                    include_executive=_inc_exec,
                    include_thorough=_inc_thorough,
                    include_keypoints=_inc_keypoints,
                )
                return rendered

        # V0.05 (F9a/F9b): the inline fallback formats build ONLY the
        # requested sections, with targets scaled to the source.
        _sections_json = []
        if _inc_exec:
            _sections_json.append('- "executive_summary": 3-5 findings.')
        if _inc_keypoints:
            _sections_json.append(
                f'- "bullet_points": {_bullet_range} findings. Include ALL '
                'items from any enumerated lists in the source.'
            )
        if _inc_thorough:
            _sections_json.append(
                f'- "thorough_summary": {_bullet_range} findings. CRITICAL: '
                'Cover ALL major topics and contributors in the chapter. Do '
                'NOT truncate — if running low on output space, make claims '
                'shorter rather than omitting topics. Preserve all '
                'enumerated lists and multi-step processes.'
            )
        _sections_json += [
            '- "key_distinctions": 2-5 distinctions (each: "claim" = the contrast + why it matters, "supporting_text" = verbatim quote). Prioritize technical-term contrasts, developmental phase distinctions, competing positions, normal-vs-pathological.',
            '- "theoretical_tensions": 2-4 tensions (each: "claim" = the tension + diverging positions, "supporting_text" = verbatim quote). Prioritize opposing-force dialectics, school-vs-school debates, unresolved ambiguities, clinical-vs-theoretical. Name BOTH poles.',
        ]
        _sections_xml = []
        if _inc_exec:
            _sections_xml.append(
                f'<executive_summary>\nA {_exec_words} word narrative overview '
                'of the chapter\'s main argument and conclusions.\n</executive_summary>'
            )
        if _inc_keypoints:
            _sections_xml.append(
                f'<bullet_points>\nA comprehensive list of {_bullet_range} '
                'distinct key takeaways. One bullet per line, each prefixed '
                'with "- ". Each bullet must be a complete, self-contained '
                'sentence expressing a single claim, finding, or concept. '
                'Cover every section of the chapter.\n</bullet_points>'
            )
        if _inc_thorough:
            _sections_xml.append(
                f'<thorough_summary>\nA {_thorough_words} word detailed '
                'narrative that walks through the chapter section by section, '
                'explaining the argument, evidence, and reasoning in depth. '
                'The target scales to this chapter\'s length — never pad or '
                'invent content to reach it.\n</thorough_summary>'
            )
        _sections_xml += [
            '<key_distinctions>\nList 2-5 important DISTINCTIONS the chapter explicitly draws between related concepts. ONLY include distinctions that the chapter ACTUALLY discusses — each must be traceable to a specific passage. If the chapter does not draw any explicit distinctions, output "None" (do NOT invent distinctions). Format: one distinction per line, prefixed with "- ". Prioritize: technical-term contrasts, developmental phase distinctions, competing positions, normal-vs-pathological.\n</key_distinctions>',
            '<theoretical_tensions>\nIdentify 2-4 theoretical TENSIONS, DEBATES, or AMBIGUITIES the author EXPLICITLY discusses. ONLY include tensions that are actually present in the text — each must be traceable to a specific passage. If the chapter does not discuss any tensions, output "None" (do NOT fabricate debates to fill space). Prioritize: opposing-force dialectics, school-vs-school debates, unresolved ambiguities, clinical-vs-theoretical tensions. Name BOTH poles for each.\n</theoretical_tensions>',
        ]

        output_format = ""
        if self.academic_rigor:
            output_format = f"""
You are a clinical summariser. Extract the key findings from the chapter titled "{heading}".

For each finding, provide:
- "claim": A short, PRECISE summary (one sentence). Do NOT oversimplify or reinterpret. If the source says "used the word identity 92 times, only once in a technical sense," write exactly that — do NOT write "mentioned identity only once."
- "supporting_text": A DIRECT QUOTE from the chapter (verbatim, in quotes).
- "source_reference": Page/line reference if available, or author+year.

LIST PRESERVATION: If the source contains enumerated or numbered lists, reproduce ALL items as separate findings.
DETAIL PRESERVATION: When the source describes a multi-step process or set of conditions, preserve ALL steps/components as separate findings.
ANTI-FALSE-PRECISION: Do NOT invent distinctions between authors the source groups together. PRESERVE the source's grouping.
THEORIST COVERAGE: Every named author in the source MUST appear, including minor/secondary contributors.
SUB-COMPONENT COMPLETENESS: When the source describes a model with numbered sub-components, reproduce EVERY sub-component.
ANTI-OVERSPECIFICATION: Do NOT add interpretive adjectives not in the source. Quote the source's exact characterization.
ANTI-CONTEXT-STRIPPING: PRESERVE context qualifiers. Do NOT generalize context-specific statements to universal ones.
DEPTH PRESERVATION: Preserve philosophical articulations verbatim. Do NOT reduce rich characterizations to generic phrases.

Output a JSON object with these sections:
{chr(10).join(_sections_json)}

PRECISION RULE: Every claim must be traceable to a specific passage. The supporting_text MUST be a verbatim quote from the source. Do NOT paraphrase loosely — if the source says "contains the history of object choices," write exactly that, not "holds history."

Do NOT describe the JSON structure. Only output the JSON object.
"""
        else:
            output_format = (
                "\nYou MUST output exactly these XML sections:\n\n"
                + "\n\n".join(_sections_xml)
            )
        # V0.05 (F9b): the length budget rides BOTH inline paths.
        output_format += "\n\n" + length_budget_block(
            _source_words,
            include_executive=_inc_exec,
            include_thorough=_inc_thorough,
            include_keypoints=_inc_keypoints,
        )

        cot_instruction = ""

        number_instruction = """
IMPORTANT: Focus on descriptive findings, mechanisms, relationships, and qualitative conclusions.
Only include specific numbers (percentages, dosages, counts, dates) if they appear VERBATIM in the source text. Do NOT invent, approximate, or round any numbers. If you are unsure whether a number is in the source, omit it.
"""

        model_specific = ""
        model_lower = (self.primary_model or "").lower()
        if "qwen" in model_lower:
            model_specific = "\nNOTE: You are a thinking model. Do NOT include your chain-of-thought reasoning in the output. Output ONLY the final summary.\n"
        elif "qwythos" in model_lower or "claude" in model_lower or "mythos" in model_lower:
            model_specific = "\nNOTE: Be concise — each bullet should be a single, distinct concept (one sentence, max ~25 words). Do not pad bullets with narrative filler.\n"

        from core.llm.content_presets import detect_source_type, get_content_preset
        source_type = getattr(self.request, "source_type", "normal_book")
        if source_type == "normal_book":
            detected = detect_source_type(text)
            if detected != "normal_book":
                source_type = detected
                self.log(f"    📋 Auto-detected source type: {source_type}", "DEBUG")
        preset = get_content_preset(source_type)
        tone_instruction = preset.tone_instruction
        content_addendum = preset.prompt_addendum

        if preset.bullet_style == "nuanced":
            model_specific += f"\nNOTE: Write longer, nuanced bullets (20-40 words each) that preserve philosophical arguments. Aim for {preset.max_bullets} bullets.\n"
        elif preset.bullet_style == "actionable":
            model_specific += f"\nNOTE: Frame bullets as actionable advice. Aim for {preset.max_bullets} bullets.\n"
        elif preset.bullet_style == "conceptual" and source_type == "academic_paper":
            model_specific += f"\nNOTE: Aim for {preset.max_bullets} bullets covering methodology, results, and conclusions separately.\n"

        return f"""You are an expert book summariser. {lang}

You are summarising a chapter titled: "{heading}".

GOAL: Produce a comprehensive, faithful summary that a reader could use to recall every key concept, argument, framework, and example from the chapter. Depth over brevity.

INSTRUCTIONS:
1. Read the entire chapter content carefully.
2. Identify every distinct claim, concept, definition, example, and recommendation.
3. If you are unsure whether a claim is supported by the source, OMIT it. Do not invent facts.
4. Use the chapter's own terminology; do not substitute synonyms for technical terms.
5. Paraphrase PRECISELY. Do not oversimplify or reinterpret the source. If the source says "contains the history of object choices," write exactly that — do NOT write "holds history" or other loose paraphrases. Preserve the author's exact meaning.
6. LIST PRESERVATION: If the source contains enumerated or numbered lists (e.g., "1. ... 2. ... 3. ...", bullet-pointed characteristics, numbered criteria, step-by-step processes), reproduce ALL items in your summary. Do NOT condense numbered lists to "among other things" or "including several factors." Each listed item is there for a reason — the reader needs all of them.
7. DETAIL PRESERVATION: When the source describes a multi-step process, a set of conditions, a causal mechanism, or a specific procedure, do NOT reduce it to a single sentence. Preserve the steps, conditions, or components. For example, if the source says "two conditions must be met: (1) ... and (2) ...", include BOTH conditions. If it describes a staged process, include every step with its specific name and what each step involves.
8. ANTI-FALSE-PRECISION: Do NOT invent scholarly distinctions between authors the source groups together. PRESERVE the source's grouping.
9. THEORIST COVERAGE: Every named author in the source MUST appear, including minor/secondary contributors.
10. SUB-COMPONENT COMPLETENESS: When the source describes a model with numbered sub-components, reproduce EVERY sub-component.
11. ANTI-OVERSPECIFICATION: Do NOT add interpretive adjectives not in the source. If source says "in passing", write "in passing" — not "non-technical" or "colloquial".
12. ANTI-CONTEXT-STRIPPING: PRESERVE context qualifiers. If source says "in the short path, X does not occur", do NOT write "X does not occur".
13. DEPTH PRESERVATION: Preserve philosophical articulations verbatim. Do NOT reduce "two limits of human experience incompatible but complementary" to "two opposing forces".
14. DO NOT output your thinking process, analysis steps, or reasoning. Output ONLY the final summary in the XML format below.
{model_specific}
{number_instruction}
{reading_level_instruction}
{tone_instruction}
{content_addendum}
{callout_block}
{attribution_block}
{output_format}

Chapter content:
{text}

Output ONLY the XML sections specified above. No preamble, no commentary, no thinking process, no markdown code fences.
"""

    # V0.08 (P2 dead-code removal): the _build_thorough_followup delegate
    # (zero callers since the thorough followup call was replaced by the
    # dedicated thorough expansion) was deleted. The underlying
    # prompt_assembly.build_thorough_followup stays — it is a pinned live
    # export with its own characterization tests.

    def _build_dedicated_thorough_prompt(self, heading: str, text: str, exec_sum: str, bullets: list[str], draft: str | None = None) -> str:
        """V18.2.34: Dedicated thorough-summary prompt.

        V18.6 (Phase 4, Task 4.2): delegates to
        ``prompt_assembly.build_dedicated_thorough_prompt``. Byte-for-byte
        identical output (characterization tests in ``test_prompt_assembly.py``).

        Unlike ``_build_thorough_followup`` (a small followup call appended to
        the primary LLM response that shares output budget with the other 4
        sections), this is a STANDALONE call that gets the full output budget
        for the thorough summary alone. Used when the primary-call thorough
        came back short (<800 words) and we want a deeper, more comprehensive
        expansion that doesn't compete with exec/bullets/key_distinctions/
        glossary for token budget.
        """
        from core.summarisation.prompt_assembly import (
            build_dedicated_thorough_prompt as _pa_ded_thorough,
        )
        # V18.20.3.11 (Phase 3.b): the primary's PARTIAL thorough (cut at the
        # 8192 output cap) travels as ``draft`` so the dedicated call is a
        # continuation, not a cold re-derivation.
        return _pa_ded_thorough(heading, text, exec_sum, bullets, self.language, draft=draft)

    def _call_dedicated_thorough_with_fallback(
        self,
        prompt: str,
        exec_sum: str,
        bullets: list[str],
        min_words: int = 800,
    ) -> str | None:
        """V18.2.44 (Next Step #6): Dedicated thorough call with 3 attempts + a
        deterministic non-empty fallback.

        V18.11 (Phase 5 Stage 3, Batch 2.3): logic extracted verbatim to
        ``thorough_fallback.call_dedicated_thorough_with_fallback``. The
        mutable ``self._synthetic_thorough_fallback_count`` is passed in
        as an int param and the (possibly incremented) new count is
        returned alongside the thorough text; this delegate unpacks and
        re-assigns it (kept as a plain int per the V18.4 contract).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_thorough_fallback.py``).
        """
        result, self._synthetic_thorough_fallback_count = (
            tf_call_dedicated_thorough_with_fallback(
                prompt, exec_sum, bullets,
                min_words=min_words,
                max_output_tokens=getattr(self.request, "summarisation_max_output_tokens", 8192) or 8192,
                primary_model=self.primary_model,
                temperature=self.temperature,
                strip_thinking=self._strip_thinking,
                call_llm=self._call_llm,
                deadline_exceeded=self._deadline_exceeded,
                synthetic_fallback_count=self._synthetic_thorough_fallback_count,
                log=self.log,
            )
        )
        return result

    # V18.20.4.7 (P5 / O-a2): _thorough_theorist_floor moved
    # VERBATIM to core/summarisation/thorough_theorist_floor.py
    # (SummarizerThoroughFloorMixin) — its call site below in
    # _summarize_inner is unchanged.

    def _build_dedicated_bullet_prompt(self, heading: str, text: str, exec_sum: str, existing_bullets: list[str]) -> str:
        """V18.2.34: Dedicated bullet-expansion prompt.

        V18.6 (Phase 4, Task 4.2): delegates to
        ``prompt_assembly.build_dedicated_bullet_prompt``. Byte-for-byte
        identical output (characterization tests in ``test_prompt_assembly.py``).

        Standalone call (full output budget) used when the primary-call
        bullet_points list came back short (<30 bullets). Asks for 30-50 NEW
        bullets that don't repeat the existing ones — gives the chapter full
        coverage of every named contributor, framework, and example.
        """
        from core.summarisation.prompt_assembly import (
            build_dedicated_bullet_prompt as _pa_ded_bullet,
        )
        return _pa_ded_bullet(heading, text, exec_sum, existing_bullets, self.language)

    # V0.08 (P2 dead-code removal): the _build_missing_keywords_reprompt
    # delegate was deleted — its only call site was the V18.6-era `if False`
    # academic-rigor gap-fill block removed above. The underlying
    # prompt_assembly.build_missing_keywords_reprompt stays (pinned live
    # export with characterization tests in test_prompt_assembly.py).

    def _build_exec_from_thorough_prompt(self, heading: str, thorough_summary: str) -> str:
        """V18.15.8.0 (Fix 1): Build the exec-from-thorough followup prompt.

        Delegates to ``prompt_assembly.build_exec_from_thorough_prompt``.
        See that function's docstring for the full rationale.
        """
        from core.summarisation.prompt_assembly import (
            build_exec_from_thorough_prompt as _pa_exec_from_thorough,
        )
        return _pa_exec_from_thorough(heading, thorough_summary, self.language)

    def _save_checkpoint(self, heading: str, result: dict, label: str = "primary") -> None:
        """V18.20.1.2 (crash mitigation): Save a checkpoint of the current result state.

        Writes exec + bullets + thorough + key_distinctions + theoretical_tensions
        to ``summaries/.checkpoints/<label>_<heading>_summary.md``. If the pipeline
        crashes in a LATER phase, the user recovers this checkpoint.

        Called at two points:
          1. ``label="primary"`` — after the primary call + thinking strip (V18.19.2.4).
          2. ``label="post-additive-sections"`` — after additive sections are populated
             (V18.20.1.2). This captures key_distinctions + theoretical_tensions,
             which the primary checkpoint doesn't have.

        Best-effort: if the write fails, logs + continues (never crashes the pipeline).
        The final save (conversion/summarization.py:770) overwrites this with the
        complete post-processed output if the pipeline succeeds.
        """
        try:
            from pathlib import Path as _P

            from utils.atomic_io import atomic_write_text
            _ckpt_dir = _P(self.request.output_dir) / "summaries" / ".checkpoints"
            _ckpt_dir.mkdir(parents=True, exist_ok=True)
            _safe_h = re.sub(r'[^A-Za-z0-9_\-]+', '_', heading)[:60].strip('_')
            _ckpt_path = _ckpt_dir / f"{label}_{_safe_h}_summary.md"
            _exec = result.get("executive_summary", "") or ""
            _thorough = result.get("thorough_summary", "") or ""
            _bullets = result.get("bullet_points", []) or []
            _bp_text = "\n".join(f"- {b}" for b in _bullets)
            _kd = result.get("key_distinctions", "") or ""
            _tt = result.get("theoretical_tensions", "") or ""
            # V0.03 (P0-2): Tier-3 excerpts in checkpoints too.
            _se = result.get("source_excerpts", []) or []
            _se_text = "\n".join(f"- {e}" for e in _se if str(e).strip())
            _ckpt_content = (
                f"# Summary ({label.upper()} CHECKPOINT — V18.20.1.2)\n\n"
                f"## Chapter: {heading}\n\n"
                f"> ⚠️ Checkpoint saved at phase: {label}. If the conversion\n"
                f"> completed successfully, this file was superseded by the\n"
                f"> final summary in the parent `summaries/` folder. If the\n"
                f"> conversion CRASHED after this checkpoint, this file contains\n"
                f"> the recovered output up to this phase.\n\n"
                f"## Executive Summary\n\n{_exec}\n\n"
                f"## Key Takeaways\n\n{_bp_text}\n\n"
                f"## Thorough Summary\n\n{_thorough}\n\n"
                + (f"## Key Distinctions\n\n{_kd}\n\n" if _kd.strip() else "")
                + (f"## Theoretical Tensions\n\n{_tt}\n\n" if _tt.strip() else "")
                + (f"## Source Excerpts (auto-inserted)\n\n{_se_text}\n\n" if _se_text else "")
                + f"<!-- {label.upper()} CHECKPOINT — {len(_bullets)} bullets, "
                f"{len(_exec.split()) if _exec else 0} exec words, "
                f"{len(_thorough.split()) if _thorough else 0} thorough words"
                + (", +key_distinctions" if _kd.strip() else "")
                + (", +theoretical_tensions" if _tt.strip() else "")
                + (", +source_excerpts" if _se_text else "")
                + " -->\n"
            )
            atomic_write_text(_ckpt_path, _ckpt_content, encoding="utf-8")
            self.log(
                f"    💾 V18.20.1.2: {label} checkpoint saved "
                f"({len(_bullets)} bullets, {len(_exec.split()) if _exec else 0} "
                f"exec words, {len(_thorough.split()) if _thorough else 0} thorough words"
                + (", +key_distinctions" if _kd.strip() else "")
                + (", +theoretical_tensions" if _tt.strip() else "")
                + f") → .checkpoints/{_ckpt_path.name}",
                "DEBUG",
            )
        except Exception as _ckpt_e:
            # V18.20.4.11 (P2 / W-a12): raised DEBUG → WARNING — a lost
            # checkpoint silently breaks crash-resume (the whole point of
            # the V18.20.1.2 checkpoint), and the user must know. The
            # logger.debug trace stays; only the self.log LEVEL changes.
            self.log(
                f"    ⚠️ V18.20.1.2: {label} checkpoint save failed "
                f"(non-fatal): {_ckpt_e}",
                "WARNING",
            )
            logger.debug("%s checkpoint failed: %s: %s",
                         label, type(_ckpt_e).__name__, _ckpt_e)

    def _ensure_exec_from_thorough(self, heading: str, thorough: str) -> str:
        """V18.15.8.0 (Fix 1): Derive executive summary FROM the thorough summary.

        The thorough summary has a dedicated system with 100% coverage (the
        dedicated thorough call at ``summarizer.py:3060`` ensures thorough is
        NEVER empty). When the primary call's ``executive_summary`` is empty,
        we derive it FROM the thorough summary via a followup LLM call — rather
        than the pre-V18.15.8.0 backwards fallback (``thorough = exec_sum``
        which copied an empty string when exec was also empty, causing the
        V18.15.7.0 cascade failure where BOTH exec + thorough were empty).

        Mirrors the ``_ensure_additive_sections`` followup-call pattern:
        1. Build the prompt (``_build_exec_from_thorough_prompt``).
        2. Fire the LLM call via ``_call_llm_with_empty_retry``.
        3. Strip thinking + parse the ``<executive_summary>`` XML tag.
        4. Return the derived exec summary (or empty string on failure).

        Args:
            heading: the chapter heading.
            thorough: the populated thorough summary (800-1200 words).

        Returns:
            The derived executive summary (150-250 words), or empty string
            if the call failed.
        """
        if not thorough or len(thorough.strip()) < 50:
            self.log("    ⚠️ V18.15.8.0: Cannot derive exec from thorough — thorough too short", "WARNING")
            return ""
        self.log("    📝 V18.15.8.0: Executive summary empty — deriving from thorough summary (dedicated system, 100% coverage)…", "INFO")
        _prompt = self._build_exec_from_thorough_prompt(heading, thorough)
        _raw = self._call_llm_with_empty_retry(_prompt, model=self.primary_model, temperature=self.temperature, max_tokens=2048)
        if not _raw:
            self.log("    ⚠️ V18.15.8.0: Exec-from-thorough call returned empty", "WARNING")
            return ""
        _raw = self._strip_thinking(_raw)
        # V18.16.0.1 (Fix 1): Check for CoT narrative BEFORE accepting the output.
        # The V18.16.0.0 regression: when the model produces CoT (no <executive_summary>
        # tag), the fallback `_exec = _raw.strip()` accepted the FULL CoT output
        # (972 words of "me to write a 150-250 word executive summary... Draft:...").
        # The word count check (≥50) passed because CoT is long. This caused the
        # catastrophic 2/10 regression. Fix: run detect_cot_narrative on the raw
        # output. If CoT is detected, return empty (trigger last-resort fallback).
        from core.summarisation.postchecks import detect_cot_narrative
        _raw_cleaned, _cot_issues = detect_cot_narrative(_raw, "exec")
        if _cot_issues:
            self.log(
                f"    ⚠️ V18.16.0.1: Exec-from-thorough output is CoT narrative "
                f"({_cot_issues[0].detail[:60]}) — discarding, falling back",
                "WARNING",
            )
            return ""
        # Parse <executive_summary>...</executive_summary> tag
        m = re.search(r'<executive_summary>(.*?)</executive_summary>', _raw, re.DOTALL)
        if m:
            _exec = m.group(1).strip()
        else:
            # V18.16.0.1 (Fix 1): If no XML tag AND the output starts with CoT-like
            # phrases ("me to write", "synthesize", "Draft:", "Key elements"),
            # reject it — it's the model's reasoning, not a summary.
            _lower = _raw[:200].lower().strip()
            if any(_phrase in _lower for _phrase in (
                "me to write", "synthesize the key", "draft:", "key elements to capture",
                "this in flowing prose", "carefully. draft",
            )):
                self.log(
                    "    ⚠️ V18.16.0.1: Exec-from-thorough output looks like CoT "
                    "(no XML tag + CoT preamble) — discarding",
                    "WARNING",
                )
                return ""
            _exec = _raw.strip()
        # Validate: must be substantive (≥50 words)
        _words = len(_exec.split()) if _exec else 0
        if _words < 50:
            self.log(f"    ⚠️ V18.15.8.0: Exec-from-thorough too short ({_words} words < 50) — discarding", "WARNING")
            return ""
        self.log(f"    ✅ V18.15.8.0: Executive summary derived from thorough ({_words} words)", "INFO")
        return _exec

    # ─────────────────────────────────────────────────────────────────────────
    # Self‑review step (for academic rigor)
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # V13.32.8: 3-Tier Coverage Guarantee System
    # ─────────────────────────────────────────────────────────────────────────

    # V18.20.4.7 (P5 / O-a2): the additive-sections machinery
    # (_ensure_conclusion_bullets, _normalize_empty_section,
    # _verify_additive_section_item, _verify_additive_sections,
    # _ensure_additive_sections) moved VERBATIM to
    # core/summarisation/additive_sections.py
    # (SummarizerAdditiveMixin).

    def _find_source_sentence(self, keyword, text):
        kl = keyword.lower()
        # V0.05 (rig audit F4 — P1): the boundary lookahead now accepts
        # DIGITS and typographic quotes too. The old ``(?=[A-Z"])`` never
        # split before a numbered-list continuation ("…on the attack.\n\n 3)
        # Use these…"), so excerpts glued two numbered items into one
        # "sentence" — a verbatim excerpt must be exactly one sentence.
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c])', text)
        for sent in sentences:
            sl = sent.lower().strip()
            if not sl or len(sl) < 20: continue
            if ' ' in kl:
                parts = [p for p in kl.split() if len(p) > 2]
                if parts and all(p in sl for p in parts): return sent.strip()
            elif kl in sl: return sent.strip()
        return None

    def _targeted_gap_fill(self, heading, text, missing_keywords):
        if not missing_keywords: return []
        gap_pairs = []
        for kw in missing_keywords[:12]:
            sent = self._find_source_sentence(kw, text)
            if sent: gap_pairs.append((kw, sent))
        if not gap_pairs: return []
        self.log(f"    \U0001f50d Tier 2: targeted gap-fill for {len(gap_pairs)} missing concepts (parallel, focused calls)\u2026", "INFO")
        import concurrent.futures
        def _fill_one(pair):
            kw, sent = pair
            lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
            prompt = f'Write ONE bullet point (prefixed with "- ") summarizing what this source sentence says about "{kw}".\n\nSource sentence: "{sent}"\n\nRules:\n- One bullet only, prefixed with "- ".\n- Grounded in the source sentence.\n- Concise (1-2 sentences max).\n{lang}\n\nBullet point:'
            try:
                # V13.36.0: When fusion gap-fill is enabled (site E, opt-in),
                # use the cloud model for higher-quality paraphrases.
                # Default is OFF — the local 9B model is fine for paraphrasing.
                if self.fusion_enabled and self.fusion_use_for_gap_fill:
                    raw = self._call_cloud(prompt, max_tokens=200,
                                           temperature=self.fusion_cloud_temperature)
                else:
                    raw = self._call_fast_llm(prompt, max_tokens=200)
                if not raw: return None
                raw = self._strip_thinking(raw).strip()
                if raw and not raw.startswith("- "): raw = "- " + raw.lstrip("*-\u2022 ")
                if raw and len(raw) > 10 and "cannot" not in raw.lower()[:30]: return raw
                return None
            except Exception: return None
        new_bullets = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_fill_one, pair): pair for pair in gap_pairs}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bp = future.result(timeout=120)
                        if bp: new_bullets.append(bp)
                    except Exception as _e:
                        # V18.2.14 (B4): was silent ``pass`` — now traceable.
                        # WARNING level because a failed future means a lost
                        # gap-fill bullet — worth surfacing.
                        log_swallow("gap_fill_future_result", _e,
                                    level=logging.WARNING)
        except Exception:
            for pair in gap_pairs:
                bp = _fill_one(pair)
                if bp: new_bullets.append(bp)
        if new_bullets:
            self.log(f"    \u2705 Tier 2: gap-filled {len(new_bullets)}/{len(gap_pairs)} concepts via focused LLM calls", "INFO")
        return new_bullets

    def _prune_covered_excerpts(
        self,
        bullets: list[str],
        exec_sum: str,
        thorough: str,
        excerpts: list[str],
    ) -> list[str]:
        """V0.06 (rig audit F7-a): drop excerpts the FINAL summary covers.

        GENERAL RULE: a Tier-3 excerpt exists to cover a concept the summary
        text did not cover AT INSERTION TIME. Later stages (scholar
        gap-fill, Tier-2) can add bullets covering the same source
        sentence; at ship time the excerpt list is re-validated so the
        delivered "Source Excerpts" section only contains material the
        final summary genuinely does not cover. Two honest coverage
        signals, either suffices:

          * per-bullet content-token containment >= 0.55 (a bullet
            paraphrasing the excerpt's sentence), or
          * >= 75% of the quote's content words present in the combined
            summary text (exec + bullets + thorough).
        """
        if not excerpts:
            return list(excerpts or [])

        def _tokens(s: str) -> set[str]:
            out = set()
            for w in re.findall(r'[a-z0-9]+', (s or "").lower()):
                if len(w) <= 2:
                    continue
                if len(w) > 3 and w.endswith("s"):
                    out.add(w[:-1])
                out.add(w)
            return out

        combined_words = _tokens(
            " ".join([str(exec_sum or ""), " ".join(str(b) for b in (bullets or [])),
                      str(thorough or "")])
        )
        kept: list[str] = []
        for ex in excerpts:
            ex_str = str(ex)
            m = re.search(r':\s*"(.*)"\s*$', ex_str, re.DOTALL)
            if not m:
                kept.append(ex_str)  # not a framed excerpt — leave untouched
                continue
            quote_toks = _tokens(m.group(1))
            if not quote_toks:
                kept.append(ex_str)
                continue
            covered = False
            # (a) per-bullet paraphrase containment
            for b in (bullets or []):
                b_toks = _tokens(str(b))
                if not b_toks:
                    continue
                inter = len(quote_toks & b_toks)
                if inter and inter / min(len(quote_toks), len(b_toks)) >= 0.55:
                    covered = True
                    break
            # (b) combined-text word coverage
            if not covered:
                hits = sum(1 for t in quote_toks if t in combined_words)
                if hits / len(quote_toks) >= 0.75:
                    covered = True
            if not covered:
                kept.append(ex_str)
        return kept

    def _force_insert_missing(self, text, still_missing, result, heading=""):
        """V16.0.3 Tier-3 → V0.03 (P0-2) REDESIGNED.

        The old implementation appended raw source slices as KEY TAKEAWAYS
        ("- **{kw}**: {sent}"). The V0.02 rig run showed the failure mode:
        a mid-quote fragment of the *anti-pattern answer* ("We do," we say
        something like, "Well, you could do without a second server…")
        shipped as the final takeaway of the book — advice-shaped garbage.

        New contract (GENERAL, not book-specific):
          - excerpts NEVER enter ``bullet_points`` (Key Takeaways) — they
            go to ``result["source_excerpts"]``, rendered as a separate,
            clearly-labelled section;
          - only COMPLETE sentences are eligible: capital-letter start,
            terminal punctuation, ≥40 chars, balanced double quotes;
          - each excerpt carries explicit framing so a skimming reader
            cannot mistake it for the model's advice.
        """
        if not still_missing: return 0
        inserted = 0
        # V0.05 (rig audit F3-b — P1): the dedupe key is the NORMALIZED
        # SOURCE SENTENCE, not the framed excerpt string. The old key
        # (excerpt.lower()[:80]) was keyword-dominated — the frame
        # 'On "kw" — verbatim…' STARTS with the keyword, so different
        # keywords pointing at the SAME sentence each inserted their own
        # copy (the V0.04 rig shipped 9 excerpts for 4 unique sentences in
        # one chapter). The key extracts the quoted sentence tail instead.
        _norm_ws = re.compile(r'\s+')
        existing = set()
        for x in result.get("source_excerpts", []) or []:
            _body = str(x)
            _qm = re.search(r':\s*"(.*)"\s*$', _body, re.DOTALL)
            if _qm:
                _body = _qm.group(1)
            existing.add(_norm_ws.sub(' ', _body.lower().strip()))
        # V0.05 (F3-c): remediation unit = SENTENCE, not keyword. Keywords
        # resolving to the same source sentence are consolidated into ONE
        # excerpt (the frame lists them together) — overlapping
        # bigram/trigram keywords from one sentence must not each spawn
        # their own remediation.
        _by_sentence: dict[str, list[str]] = {}
        _sent_cache: dict[str, str] = {}
        for kw in still_missing:
            sent = self._find_source_sentence(kw, text)
            if not sent: continue
            _skey = _norm_ws.sub(' ', sent.lower().strip())
            _sent_cache[_skey] = sent
            _by_sentence.setdefault(_skey, []).append(kw)
        for _skey, _kws in _by_sentence.items():
            sent = _sent_cache[_skey]
            # V0.06 (rig audit F7-b — GENERAL RULE: an excerpt never opens
            # with a duplicate of its own chapter heading). PDF extraction
            # frequently glues the chapter TITLE (or its numbered echo)
            # onto the first sentence of the body text — the V0.05 rig
            # shipped an excerpt reading "Don't put your resume ahead of
            # the\n\nrequirements As engineers we sometimes…" where the
            # heading echo runs straight into the real sentence. Collapse
            # internal whitespace and strip a leading heading-echo prefix
            # (whitespace-insensitive, optional leading number).
            sent = _norm_ws.sub(' ', sent).strip()
            if heading:
                _head = _norm_ws.sub(' ', str(heading).strip())
                _head_nn = re.sub(r'^\d+[.)]?\s*', '', _head).strip().lower()
                _sent_lc = sent.lower()
                if _head_nn and len(_head_nn) >= 12 and _sent_lc.startswith(_head_nn):
                    sent = sent[len(_head_nn):].lstrip(' —–-:,.').strip()
                    _skey = _norm_ws.sub(' ', sent.lower().strip())
            kw = " / ".join(_kws[:3]) + (" …" if len(_kws) > 3 else "")
            # V0.03 (P0-2): complete-sentence gate — reject fragments.
            _s = sent.strip().strip('"')
            _starts_ok = bool(_s) and (_s[0].isupper() or _s[0] in "“\"'")
            _ends_ok = bool(_s) and (_s[-1] in ".!?…" or _s[-1] in "”\"')")
            _len_ok = len(_s) >= 40
            _quotes_ok = sent.count('"') % 2 == 0
            if not (_starts_ok and _ends_ok and _len_ok and _quotes_ok):
                self.log(
                    f"    ⛔ Tier 3: skipped non-sentence excerpt for '{kw}' "
                    f"(fragment/quote-imbalanced source slice)",
                    "DEBUG",
                )
                continue
            if _skey in existing: continue
            excerpt = (
                f'On "{kw}" — verbatim from the source (auto-inserted for '
                f'coverage; not the summarizer\'s advice): "{sent}"'
            )
            result.setdefault("source_excerpts", []).append(excerpt)
            existing.add(_skey)
            inserted += 1
        if inserted > 0:
            self.log(
                f"    🔖 Tier 3: recorded {inserted} complete-sentence source "
                f"excerpt(s) into the 'Source Excerpts' section (framed, "
                f"EXCLUDED from Key Takeaways; sentence-deduped — "
                f"{len(_by_sentence)} unique source sentence(s) for "
                f"{len(still_missing)} keyword(s))",
                "INFO",
            )
        return inserted

    def _apply_3tier_coverage(self, heading, text, content, result, coverage):
        """V16.0.3 3-Tier coverage guarantee.

        V18.15.3 (Phase 5 Stage 3, Batch 4.5): logic extracted verbatim to
        ``coverage_guarantee.apply_3tier_coverage``. The 8 ``self`` deps
        (``coverage_threshold``, ``_extract_keywords``, ``log``,
        ``_targeted_gap_fill``, ``_filter_thinking_bullets``,
        ``max_bullets_per_chapter``, ``_compute_coverage``,
        ``_force_insert_missing``) are passed as explicit kwargs (the
        proven-safe pattern — NOT a context object). ``result`` is mutated
        in place exactly as the original. Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_coverage_guarantee.py``).
        """
        # V0.06 (rig audit F4-b): the source-scaled bullet budget (the SAME
        # length_policy.bullet_target every prompt uses) is passed as a HARD
        # CAP to the coverage engine — Tier-2 gap-fill stops adding bullets
        # at the cap (the V0.05 rig: 6 primary bullets + 4 Tier-2 + 9 scholar
        # = 19 shipped against a 5-7 target). F7-b: the chapter heading is
        # threaded to Tier-3 so excerpts never open with a heading echo.
        from core.summarisation.length_policy import (
            bullet_cap as _lp_bullet_cap,
            count_source_words as _lp_csw,
        )
        return cg_apply_3tier_coverage(
            heading, text, content, result, coverage,
            coverage_threshold=self.coverage_threshold,
            extract_keywords=self._extract_keywords,
            log=self.log,
            targeted_gap_fill=self._targeted_gap_fill,
            filter_thinking_bullets=self._filter_thinking_bullets,
            max_bullets_per_chapter=self.max_bullets_per_chapter,
            compute_coverage=self._compute_coverage,
            force_insert_missing=(
                lambda t, sm, r: self._force_insert_missing(t, sm, r, heading=heading)
            ),
            bullet_cap=_lp_bullet_cap(_lp_csw(text)),
        )

    def _recover_vram(self, context: str = "", delay_sec: float = 8.0) -> None:
        """V13.40.0: Recover VRAM between heavy LLM phases to prevent empty responses.

        V13.44.3: This is now a NO-OP when using cloud APIs (self.is_local == False).
        Cloud APIs don't have VRAM — the delay would just waste time. All delay
        durations are configurable via settings (local.vram_recovery_delay_sec).

        V18.2.19 (M1): Delegates to core.summarisation.vram.recover_vram.
        The logic is extracted for testability + reuse.
        """
        from core.summarisation.vram import recover_vram
        recover_vram(
            is_local=self.is_local,
            delay_sec=delay_sec,
            configured_delay=self.local_vram_recovery_delay,
            context=context,
            log_fn=self.log,
        )

    def _scholar_reflection(self, heading: str, text: str, result: dict) -> None:
        """V13.41.0: Meta-cognitive reflection — the LLM reviews its own summary for gaps.

        V18.12 (Phase 5 Stage 3, Batch 2.6): logic extracted verbatim to
        ``scholar_reflection.scholar_reflection``. The 7 self-deps are passed
        as explicit kwargs (the proven-safe pattern — NOT a context object).
        Mutates ``result`` in-place (extends ``bullet_points``, sets
        ``scholar_reflections``). Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_scholar_reflection.py``).
        """
        scr_scholar_reflection(
            heading, text, result,
            max_context_tokens=self.request.summarisation_max_context_tokens,
            language=self.language,
            temperature=self.temperature,
            prompt_manager=self.prompt_manager,
            recover_vram=self._recover_vram,
            call_fast_llm=self._call_fast_llm,
            strip_thinking=self._strip_thinking,
            # V18.20.3.4 (RC-1 layer 2, audit v182033): filter the gap-fill
            # bullets through the SAME thinking/self-talk/scar filter the
            # expansion path uses, BEFORE they merge into bullet_points.
            filter_thinking_bullets=self._filter_thinking_bullets,
            log=self.log,
            # V0.06 (rig audit F4-b): the source-scaled bullet budget is a
            # hard cap — the scholar gap-fill merges at most (cap - existing)
            # new bullets (the V0.05 rig added 13/22/8/10 bullets on top of
            # chapters already at their target).
            bullet_cap=_lp_bullet_cap_fn(text),
        )

    def _scholar_reflection_gapfill_only(self, heading: str, text: str, result: dict) -> None:
        """V18.2 (audit Fix 2): Run gap-fill ONLY, suppress the reflections text.

        V18.12 (Phase 5 Stage 3, Batch 2.6): logic extracted verbatim to
        ``scholar_reflection.scholar_reflection_gapfill_only``. Delegates to
        ``scr_scholar_reflection`` then clears ``result["scholar_reflections"]``.
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_scholar_reflection.py``). The call site
        ``self._scholar_reflection_gapfill_only(heading, content, parsed)`` in
        ``_summarize_inner`` is preserved (satisfies test_deadline_watchdog).
        """
        scr_scholar_reflection_gapfill_only(
            heading, text, result,
            max_context_tokens=self.request.summarisation_max_context_tokens,
            language=self.language,
            temperature=self.temperature,
            prompt_manager=self.prompt_manager,
            recover_vram=self._recover_vram,
            call_fast_llm=self._call_fast_llm,
            strip_thinking=self._strip_thinking,
            # V18.20.3.4 (RC-1 layer 2, audit v182033): same filter as the
            # full scholar-reflection path.
            filter_thinking_bullets=self._filter_thinking_bullets,
            log=self.log,
            # V0.06 (F4-b): same hard bullet cap as the full path.
            bullet_cap=_lp_bullet_cap_fn(text),
        )

    def _anti_false_precision_check(self, heading: str, text: str, result: dict) -> None:
        """V13.45.0: Anti-false-precision — delegates to summary_validator.anti_false_precision_check.

        V18.7 (Phase 5.2): extracted verbatim to
        ``summary_validator.anti_false_precision_check``. Pure regex, no LLM call.
        """
        sv_anti_false_precision_check(heading, text, result, log=self.log)
    def _semantic_dedup_bullets(self, bullets: list[str], threshold: float = 0.85) -> list[str]:
        """V13.45.5: Semantic dedup — delegates to summary_validator.semantic_dedup_bullets.

        V18.7 (Phase 5.2): extracted verbatim to ``summary_validator.semantic_dedup_bullets``.
        The embedder is a module singleton (no instance state).

        V18.20.3.11 (F2 — user-approved threshold alignment): the shipped-
        summary dedup default drops 0.92 → 0.85, ALIGNING with the keypoints
        builder's embedding-dedup threshold (keypoints_builder.py, cosine
        > 0.85). The two layers were disagreeing over the same list: the
        .3.8 four-pillar audit found ~4 near-duplicate bullet pairs in the
        0.85-0.92 band shipping in the chapter summary (capping its
        conciseness at 8/10) while the keypoints file dropped them. Both
        layers now apply the same bar. The validator function's own default
        is untouched (its other callers keep their behavior); the shipped
        path is this delegate.
        """
        return sv_semantic_dedup_bullets(bullets, threshold=threshold, log=self.log)
    def _self_review(self, heading: str, text: str, summary: str) -> str | None:
        """Ask a model to review the summary against the source and flag unsupported claims.

        C8 fix: send the FULL source (truncated to the model's context window
        minus the summary), not just text[:8000].
        C9 fix: use the heavy_model if available (independent review); if no
        second model is available, skip self-review entirely (same-model
        self-review has a strong self-consistency bias and rarely catches
        real hallucinations).
        """
        # self-review now runs even with a single model (same
        # model reviewing its own output).  While same-model review has a
        # self-consistency bias, it still catches gross hallucinations and
        # formatting issues.  The merge logic (P3-5) ensures the reviewer
        # can only REMOVE unsupported claims, not introduce new ones.
        review_model = self.heavy_model if self.heavy_model else self.primary_model
        if not review_model:
            self.log("    ⏭️ Self‑review skipped (no model available).", "INFO")
            return None
        if review_model == self.primary_model:
            self.log("    ℹ️ Self‑review using same model (no independent reviewer available).", "DEBUG")

        # C8: send full source, truncated to fit the context window
        # Reserve 2000 tokens for the summary + prompt overhead
        max_src = max(self.request.summarisation_max_context_tokens - 2000, 8000)
        src_text = text[:max_src * 4]  # rough chars-per-token estimate

        prompt = self.prompt_manager.render_template(
            "summarisation/self_review",
            heading=heading,
            src_text=src_text,
            summary=summary,
        )

        # V13.34.0: Use the model's temperature, not 0.0. Temperature=0 causes
        # empty responses on Gemma 4 and Qwythos. The self-review still works
        # at the model's recommended temperature — it just has natural variation.
        # V13.36.0: When fusion is enabled, use the cloud model for self-review
        # (site A — independent fact-checker). The cloud model is a stronger,
        # independent reviewer that doesn't share the local model's biases.
        if self.fusion_enabled and self.fusion_use_for_self_review:
            self.log(f"    🔀 Self-review via fusion cloud ({self.fusion_cloud_model})…", "DEBUG")
            return self._call_cloud(prompt, temperature=self.fusion_cloud_temperature)
        # V18.20.2.0 (SWOT A5): direct _call_llm site — inject /no_think for
        # Qwen-family models (bypasses _call_llm_with_empty_retry's V18.2.41
        # injection). Cloud path above intentionally NOT injected.
        return self._call_llm(
            qwen_no_think(prompt, review_model),
            model=review_model, temperature=self.temperature,
        )

    def _self_review_batched(self, heading: str, text: str, bullets: list, thorough: str) -> str | None:
        """V13.45.4: Batched self-review — reviews bullets in chunks of 10.

        V18.11 (Phase 5 Stage 3, Batch 2.4): logic extracted verbatim to
        ``self_review.self_review_batched``. The ``request`` read
        (``summarisation_max_context_tokens``) is passed as an explicit
        primitive. Byte-for-byte identical behaviour (characterization
        tests in ``tests/test_self_review.py``). The ``thorough`` param is
        unused in the body but kept in the signature for call-site compat.
        """
        return sr_self_review_batched(
            heading, text, bullets, thorough,
            heavy_model=self.heavy_model,
            primary_model=self.primary_model,
            max_context_tokens=self.request.summarisation_max_context_tokens,
            temperature=self.temperature,
            prompt_manager=self.prompt_manager,
            recover_vram=self._recover_vram,
            call_llm=self._call_llm,
            strip_thinking=self._strip_thinking,
            log=self.log,
        )

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
        _cache_enabled = bool(getattr(self.request, 'summarisation_cache_enabled', False))
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
                logger.debug("ignored %s: %s", type(_e).__name__, _e)  # cache is best-effort — never block on it

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
                "claude", prompt, model=model or self.claude_model,
                temp=temp, max_tokens=max_tok,
            )
        elif self.provider == "freellmapi":
            _result = self._call_via_llm_provider(
                "openai_compat", prompt,
                base_url=self.freellmapi_url, api_key=self.freellmapi_key,
                model=model or self.freellmapi_model,
                temp=temp, max_tokens=max_tok,
            )
        elif self.provider in ("openrouter", "openai", "openai_compatible"):
            _result = self._call_via_llm_provider(
                "openai_compat", prompt,
                base_url=self.api_base_url, api_key=self.api_key,
                model=model or self.cloud_model,
                temp=temp, max_tokens=max_tok,
            )
        elif self.provider == "llamacpp":
            # V0.04: llama.cpp server. GENERAL RULE: the backend's own
            # configured model is the source of truth — a stale Ollama tag
            # in the request (saved wizard profile, old checkpoint) never
            # reaches llama-server. The provider clamps max_tok to the
            # model's 12288 output cap and fits it into the 65536 window
            # (academic-rigor's 16000 floor cannot 400 the request).
            _result = self._call_via_llm_provider(
                "llamacpp", prompt,
                base_url=self.llamacpp_base_url, api_key=self.llamacpp_api_key,
                model=self.llamacpp_model or model,
                temp=temp, max_tokens=max_tok,
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
        raw2 = self._call_llm(prompt + nudge, model=model, temperature=temperature, max_tokens=max_tokens)
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
            return self._call_llm(prompt, temperature=temperature or self.fusion_cloud_temperature,
                                  max_tokens=max_tokens or self.fusion_cloud_max_tokens)

        _temp = temperature if temperature is not None else self.fusion_cloud_temperature
        _max_tok = max_tokens or self.fusion_cloud_max_tokens
        _model = self.fusion_cloud_model
        _provider = self.fusion_cloud_provider

        try:
            if _provider == "claude":
                result = self._call_via_llm_provider(
                    "claude", prompt,
                    model=_model or self.claude_model,
                    temp=_temp, max_tokens=_max_tok,
                )
            else:
                # openai_compat (OpenRouter, OpenAI, 9Router, etc.)
                result = self._call_via_llm_provider(
                    "openai_compat", prompt,
                    base_url=self.fusion_cloud_base_url,
                    api_key=self.fusion_cloud_api_key,
                    model=_model,
                    temp=_temp, max_tokens=_max_tok,
                )
            if result and result.strip():
                self.log(f"    🔀 Fusion cloud ({_model}) responded: {len(result)} chars", "DEBUG")
                return result.strip()
            # Cloud returned empty — fall back to local
            self.log("    🔀 Fusion cloud returned empty — falling back to local model", "WARNING")
        except Exception as e:
            self.log(f"    🔀 Fusion cloud failed ({type(e).__name__}: {e}) — falling back to local", "WARNING")
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
            provider_type, prompt, model, base_url, api_key, temp, max_tokens,
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
            prompt, model, temp, max_tokens,
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
    def _call_ollama_streaming(self, prompt: str, model: str, temp: float, max_tokens: int) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher._call_ollama_streaming."""
        return _ld._call_ollama_streaming(
            prompt, model, temp, max_tokens,
            ollama_base_url=self.ollama_base_url,
            timeout=self.timeout,
            retries=self.retries,
            context_tokens=self.request.summarisation_max_context_tokens,
            supervisor=self._ollama_supervisor,
            log=self.log,
        )
    def _call_ollama_nonstreaming(self, prompt: str, model: str, temp: float, max_tokens: int) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher._call_ollama_nonstreaming."""
        return _ld._call_ollama_nonstreaming(
            prompt, model, temp, max_tokens,
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
            prompt, base_url, api_key, model, label, temp, max_tokens,
            timeout=self.timeout,
            retries=self.retries,
            provider=self.provider,
            log=self.log,
        )
    # ── Claude (Anthropic) API call ──────────────────────────────────

    def _call_claude(self, prompt: str, max_tokens: int, temperature: float) -> str | None:
        """V18.8 (Phase 5.1): delegates to llm_dispatcher.call_claude."""
        return ld_call_claude(
            prompt, max_tokens, temperature,
            claude_api_key=self.claude_api_key,
            claude_model=self.claude_model,
            claude_base_url=self.claude_base_url,
            retries=self.retries,
            log=self.log,
        )
    # ─────────────────────────────────────────────────────────────────────────
    # Parsing (improved for academic rigor) – with unconditional thinking stripping
    # ─────────────────────────────────────────────────────────────────────────

    def _strip_thinking(self, text: str) -> str:
        """Delegate to response_parser.strip_thinking."""
        return _rp_strip_thinking(text)

    def _strip_markup_tags(self, text: str) -> str:
        """Delegate to response_parser.strip_markup_tags."""
        return _rp_strip_markup_tags(text)

    def _strip_narrative_from_thorough(self, text: str) -> str:
        """Delegate to response_parser.strip_narrative_from_thorough."""
        return _rp_strip_narrative(text)

    def _score_bullet(self, bullet: str, concepts: list[str] | None = None,
                      source_text: str = "") -> int:
        """V3.2.4 C1 / V10.14.0 (D3): Score a bullet 0-100 for quality.

        V18.11 (Phase 5 Stage 3, Batch 1.2): logic extracted verbatim to
        ``bullet_scorer.score_bullet`` (pure function — ZERO ``self`` deps in
        the original). This method is a one-line delegate. Byte-for-byte
        identical scoring (characterization tests in
        ``tests/test_bullet_scorer.py``; existing ``TestScoreBullet`` in
        ``tests/test_summarizer.py`` exercises the delegate).
        """
        return bs_score_bullet(bullet, concepts=concepts, source_text=source_text)

    def _filter_thinking_bullets(self, bullets: list, concepts: list[str] | None = None,
                                  source_text: str = "") -> list[str]:
        """Filter out bullets that are thinking-process contamination AND
        narrative/story bullets that describe plot rather than concepts.

        V18.15.3 (Phase 5 Stage 3, Batch 4.6): logic extracted verbatim to
        ``filter_thinking.filter_thinking_bullets``. The 6 ``self`` deps
        (``_current_heading``, ``conservative_drops``, ``quarantine``,
        ``_score_bullet``, ``max_bullets_per_chapter``, ``log``) are passed
        as explicit kwargs (the proven-safe pattern — NOT a context object).
        The ``self._last_quarantined`` mutation is preserved via a
        ``set_last_quarantined`` callback (matches the gap_filler
        ``set_last_coverage`` precedent). Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_filter_thinking.py``).
        """
        return ft_filter_thinking_bullets(
            bullets, concepts=concepts, source_text=source_text,
            current_heading=getattr(self, "_current_heading", "") or "",
            conservative_drops=self.conservative_drops,
            quarantine=self.quarantine,
            score_bullet=self._score_bullet,
            max_bullets_per_chapter=self.max_bullets_per_chapter,
            log=self.log,
            set_last_quarantined=lambda v: setattr(self, "_last_quarantined", v),
        )

    def _truncate_to_sentences(self, text: str, max_sentences: int = 2, max_words: int = 35) -> str:
        """Truncate text to at most max_sentences, capped at max_words.

        V13.31.1 (P2.13 step 1): logic moved to response_parser.truncate_to_sentences.
        """
        return _rp_truncate_to_sentences(text, max_sentences=max_sentences, max_words=max_words)

    def _llm_grounding_check(self, bullets: list[str], source_text: str) -> list[str]:
        """V10.14.0 (D6): LLM-as-judge grounding check (langextract fallback).

        V18.15.3 (Phase 5 Stage 3, Batch 4.3): logic extracted verbatim to
        ``grounding_check.llm_grounding_check``. The 8 ``self`` deps
        (``prompt_manager``, ``fusion_enabled``, ``fusion_use_for_grounding``,
        ``_call_cloud``, ``fusion_cloud_temperature``,
        ``_call_llm_with_empty_retry``, ``temperature``, ``log``) are passed
        as explicit kwargs (the proven-safe pattern — NOT a context object).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_grounding_check.py``).
        """
        return gc_llm_grounding_check(
            bullets, source_text,
            prompt_manager=self.prompt_manager,
            fusion_enabled=self.fusion_enabled,
            fusion_use_for_grounding=self.fusion_use_for_grounding,
            call_cloud=self._call_cloud,
            fusion_cloud_temperature=self.fusion_cloud_temperature,
            call_llm_with_empty_retry=self._call_llm_with_empty_retry,
            temperature=self.temperature,
            log=self.log,
        )

    def _verify_bullets(self, bullets: list, source_text: str) -> list[str]:
        """A3: Deterministic fact-check — delegates to summary_validator.verify_bullets.

        V18.7 (Phase 5.2): extracted verbatim to ``summary_validator.verify_bullets``.
        This method is a thin delegate. The ``_verify_windows_cache`` dict is
        now initialized in ``__init__`` (was lazy-init'd via ``hasattr``).
        V0.03 (P1-6): passes the current chapter heading so quarantine
        entries are attributed and the per-chapter appendix can render them.
        """
        return sv_verify_bullets(
            bullets=bullets,
            source_text=source_text,
            verify_windows_cache=self._verify_windows_cache,
            quarantine=getattr(self, 'quarantine', None),
            log=self.log,
            chapter=getattr(self, "_current_heading", "") or "",
        )
    def _extract_bullets_from_text(self, text: str) -> list[str]:
        """Delegate to response_parser.extract_bullets_from_text."""
        return _rp_extract_bullets(text)

    def _extract_sentences_as_bullets(self, text: str, max_bullets: int = 15) -> list[str]:
        """V10.1.7: Extract sentences from text as bullet points.

        V13.31.1 (P2.13 step 1): logic moved to response_parser.extract_sentences_as_bullets.
        """
        return _rp_extract_sentences_as_bullets(text, max_bullets=max_bullets)

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """Delegate to response_parser.parse_response."""
        return _rp_parse_response(raw, academic_rigor=self.academic_rigor)

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
            prompt, model, temperature, max_tokens,
            provider=getattr(self, "provider", "ollama"),
            parse_response=self._parse_response,
            log=self.log,
        )

    def _parse_universal(self, cleaned: str) -> dict[str, Any]:
        """Delegate to response_parser._parse_universal (backward compat)."""
        from core.summarisation.response_parser import _parse_universal as _rp_universal
        return _rp_universal(cleaned)

    def _summarize_with_model(
        self,
        heading: str,
        text: str,
        model: str,
        temp: float,
        with_cot: bool = True,
        max_tokens: int | None = None,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
    ) -> dict | None:
        """V18.15.3 (Phase 5 Stage 3, Batch 4.7): logic extracted verbatim to
        ``primary_call.summarize_with_model``. The 8 ``self`` deps
        (``request``, ``log``, ``_chunked_summarize``, ``_build_prompt``,
        ``_call_llm_structured``, ``_call_llm_with_empty_retry``,
        ``_strip_thinking``, ``_parse_response``) are passed as explicit
        kwargs (the proven-safe pattern — NOT a context object).
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_primary_call.py``). Hard constraints preserved:
        max_output=8192, chunking threshold 12000 + thermal guard <78°C,
        structured-JSON-first/XML-fallback, Qwen3 /no_think stays in
        ``_call_llm_with_empty_retry``.
        """
        return pc_summarize_with_model(
            heading, text, model, temp, with_cot=with_cot,
            max_tokens=max_tokens, concepts=concepts, callouts=callouts,
            request=self.request,
            log=self.log,
            chunked_summarize=self._chunked_summarize,
            build_prompt=self._build_prompt,
            call_llm_structured=self._call_llm_structured,
            call_llm_with_empty_retry=self._call_llm_with_empty_retry,
            strip_thinking=self._strip_thinking,
            parse_response=self._parse_response,
        )

    def _chunked_summarize(
        self,
        heading: str,
        text: str,
        model: str,
        temp: float,
        with_cot: bool,
        concepts: list[str] | None,
        callouts: list[str] | None,
        max_tokens: int,
    ) -> dict | None:
        """V18.3.4 (E3): Chunked output — 2 sequential calls, no truncation.

        Call 1: executive_summary + bullet_points + thorough_summary (the bulk)
        Call 2: key_distinctions + theoretical_tensions (the analysis)
        Each call gets the full output budget → no section is cut off mid-sentence.
        Returns a merged Dict with all 5 sections, or None if either call fails.
        """
        # Build TWO prompts: one for sections 1-3, one for sections 4-5.
        # We reuse _build_prompt but with a "chunk" parameter that limits the output_format.
        # This keeps the prompt-assembly logic in one place.
        prompt1 = self._build_chunked_prompt(heading, text, with_cot=with_cot,
                                             concepts=concepts, callouts=callouts, chunk=1)
        prompt2 = self._build_chunked_prompt(heading, text, with_cot=with_cot,
                                             concepts=concepts, callouts=callouts, chunk=2)

        # Call 1: exec + bullets + thorough
        self.log("    📦 Chunk 1/2: executive_summary + bullet_points + thorough_summary", "INFO")
        raw1 = self._call_llm_with_empty_retry(prompt1, model=model, temperature=temp, max_tokens=max_tokens)
        if not raw1:
            return None
        raw1 = self._strip_thinking(raw1)
        parsed1 = self._parse_response(raw1)
        self.log(f"    ✅ Chunk 1/2: exec={len(parsed1.get('executive_summary',''))} chars, "
                 f"bullets={len(parsed1.get('bullet_points',[]))}, "
                 f"thorough={len(parsed1.get('thorough_summary',''))} chars", "INFO")

        # Call 2: key_distinctions + theoretical_tensions
        self.log("    📦 Chunk 2/2: key_distinctions + theoretical_tensions", "INFO")
        raw2 = self._call_llm_with_empty_retry(prompt2, model=model, temperature=temp, max_tokens=max_tokens)
        if not raw2:
            # Chunk 2 failed — return chunk 1 with empty sections 4-5
            self.log("    ⚠️ Chunk 2/2 failed — returning chunk 1 with empty distinctions/tensions", "WARNING")
            parsed1["raw"] = raw1
            parsed1["model"] = model
            parsed1["temperature"] = temp
            return parsed1
        raw2 = self._strip_thinking(raw2)
        parsed2 = self._parse_response(raw2)
        self.log(f"    ✅ Chunk 2/2: distinctions={len(parsed2.get('key_distinctions',''))} chars, "
                 f"tensions={len(parsed2.get('theoretical_tensions',''))} chars", "INFO")

        # Merge: take sections 1-3 from chunk 1, sections 4-5 from chunk 2
        merged = parsed1.copy()
        merged["key_distinctions"] = parsed2.get("key_distinctions", "")
        merged["theoretical_tensions"] = parsed2.get("theoretical_tensions", "")
        merged["raw"] = (raw1 or "") + "\n\n---CHUNK---\n\n" + (raw2 or "")
        merged["model"] = model
        merged["temperature"] = temp
        return merged

    def _build_chunked_prompt(self, heading: str, text: str, with_cot: bool = True,
                               concepts=None, callouts=None, chunk: int = 1) -> str:
        """V18.3.4 (E3): Build a chunked prompt — only requests SOME sections.

        V18.6 (Phase 4, Task 4.2): delegates to
        ``prompt_assembly.build_chunked_prompt``. The caller builds the full
        prompt via ``self._build_prompt(...)`` (which is NOT extracted — too
        coupled) and passes it as ``full_prompt`` to the pure function.

        chunk=1: executive_summary + bullet_points + thorough_summary
        chunk=2: key_distinctions + theoretical_tensions
        """
        from core.summarisation.prompt_assembly import build_chunked_prompt as _pa_chunked
        # Build the full prompt first (still in Summarizer — 9 self deps)
        full_prompt = self._build_prompt(heading, text, with_cot=with_cot,
                                          concepts=concepts, callouts=callouts)
        # V0.05 (F9a): the chunk override carries the same output-selection
        # flags as the primary prompt — an unrequested section must not be
        # demanded back in through the chunking layer.
        return _pa_chunked(
            heading, text, full_prompt, with_cot=with_cot, chunk=chunk,
            include_executive=bool(getattr(self.request, "include_executive_summary", True)),
            include_thorough=bool(getattr(self.request, "include_thorough_summary", True)),
            include_keypoints=bool(getattr(self.request, "include_keypoints", True)),
        )

    def _merge_summaries(self, summaries: list[dict], source_text: str = "") -> dict:
        """Merge multiple summaries. M21 fix: take source_text as parameter
        instead of reading self._source_text (thread-safety)."""
        if not source_text:
            source_text = getattr(self, '_source_text', '')
        if not summaries:
            return {}
        bullet_counts: dict[str, int] = {}
        for s in summaries:
            for bp in s.get("bullet_points", []):
                norm = re.sub(r'[^\w\s]', '', bp.lower()).strip()
                bullet_counts[norm] = bullet_counts.get(norm, 0) + 1
        threshold = max(1, len(summaries) // 2)
        merged_bullets = [bp for bp, count in bullet_counts.items() if count >= threshold]
        best_exec = max(summaries, key=lambda s: self._compute_coverage(source_text, s.get("executive_summary", "")))
        best_thorough = max(summaries, key=lambda s: self._compute_coverage(source_text, s.get("thorough_summary", "")))
        all_bullets = []
        seen = set()
        # Fix 5: improved dedup — use fuzzy matching (not just exact
        # normalized match) to catch near-duplicates like the same finding
        # reworded across samples.  Falls back to exact match if rapidfuzz
        # is unavailable.
        try:
            from rapidfuzz import fuzz as rf_fuzz
            _has_fuzz = True
        except ImportError:
            _has_fuzz = False
        for s in summaries:
            for bp in s.get("bullet_points", []):
                norm = re.sub(r'[^\w\s]', '', bp.lower()).strip()
                if not norm or len(norm) < 10:
                    continue
                if _has_fuzz:
                    is_dup = any(rf_fuzz.token_set_ratio(norm, existing) >= 75 for existing in seen)
                else:
                    is_dup = norm in seen
                if not is_dup:
                    seen.add(norm)
                    all_bullets.append(bp)
        return {
            "executive_summary": best_exec.get("executive_summary", ""),
            "thorough_summary": best_thorough.get("thorough_summary", ""),
            "bullet_points": all_bullets[:self.max_bullets_per_chapter],
            "key_distinctions": best_exec.get("key_distinctions", ""),  # V13.38.0
            "theoretical_tensions": best_exec.get("theoretical_tensions", ""),  # V13.38.0
            "raw": "Merged from multiple summaries",
            "model": "merged",
            "temperature": "merged",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # B3: Multi-Sampling + Voting
    # ─────────────────────────────────────────────────────────────────────────

    def _b3_cloud_judge(self, samples: list[dict], source: str, heading: str) -> tuple:
        """V13.36.0: Use the fusion cloud model to pick the best B3 sample.

        V18.15.3 (Phase 5 Stage 3, Batch 4.2): logic extracted verbatim to
        ``b3_judge.b3_cloud_judge``. The 5 ``self`` deps (``prompt_manager``,
        ``_call_cloud``, ``fusion_cloud_temperature``, ``log``,
        ``_compute_coverage``) are passed as explicit kwargs (the proven-safe
        pattern — NOT a context object). Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_b3_judge.py``).
        """
        return bj_b3_cloud_judge(
            samples, source, heading,
            prompt_manager=self.prompt_manager,
            call_cloud=self._call_cloud,
            fusion_cloud_temperature=self.fusion_cloud_temperature,
            log=self.log,
            compute_coverage=self._compute_coverage,
        )

    def _multi_sample_summarize(self, heading: str, text: str,
                                 concepts: list[str] | None = None,
                                 callouts: list[str] | None = None,
                                 n_samples: int = 3) -> dict | None:
        """V3.3.0 B3: Generate N summaries and vote on the best.

        V18.11 (Phase 5 Stage 3, Batch 2.2): logic extracted verbatim to
        ``multi_sample.multi_sample_summarize``. The 12 self-deps are
        passed as explicit kwargs (the proven-safe pattern — NOT a
        context object). ``_compute_coverage`` is itself a delegate to
        ``summary_validator.compute_coverage`` (Phase 5 Batch A). 
        Byte-for-byte identical behaviour (characterization tests in
        ``tests/test_multi_sample.py``).
        """
        return ms_multi_sample_summarize(
            heading, text,
            concepts=concepts,
            callouts=callouts,
            n_samples=n_samples,
            primary_model=self.primary_model,
            temperature=self.temperature,
            recover_vram=self._recover_vram,
            summarize_with_model=self._summarize_with_model,
            b3_cloud_judge=self._b3_cloud_judge,
            compute_coverage=self._compute_coverage,
            conservative_drops=self.conservative_drops,
            quarantine=self.quarantine,
            current_heading=getattr(self, "_current_heading", "") or "",
            fusion_enabled=self.fusion_enabled,
            fusion_use_for_b3_judge=self.fusion_use_for_b3_judge,
            log=self.log,
        )

    def _extract_must_have_items(self, heading: str, text: str) -> list[str]:
        """V13.44.0 Idea #1: Pre-flight extraction of must-have items.

        Runs 1 quick LLM call to identify 5-7 things this summary MUST include.
        These are injected into each B4 section's prompt as explicit requirements.

        Universal: works for any book — discovers enumerated lists, key definitions,
        critical conclusions, important quotes, specific mechanisms by reading the source.
        """
        self.log("    🎯 Pre-flight: extracting must-have items…", "INFO")
        # Truncate source for the pre-flight call (don't need full text)
        max_src = 12000  # ~3000 tokens — enough to identify key items
        src_text = text[:max_src]
        lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
        text_excerpt = text[:200] if len(text) > 200 else text
        prompt = self.prompt_manager.render_template(
            "summarisation/preflight_must_have",
            heading=heading,
            text_excerpt=text_excerpt,
            src_text=src_text,
            language=lang,
        )

        try:
            raw = self._call_llm_with_empty_retry(prompt, temperature=0.3, max_tokens=300)
            if not raw:
                self.log("    ⚠️ Pre-flight: empty response, skipping", "WARNING")
                return []
            raw = self._strip_thinking(raw)
            items = []
            for line in raw.strip().split("\n"):
                line = line.strip().lstrip("- •\t").strip()
                if line and len(line) > 5 and len(line) < 100:
                    items.append(line)
            self.log(f"    🎯 Pre-flight: identified {len(items)} must-have items: {items[:3]}…", "INFO")
            return items[:7]  # cap at 7
        except Exception as e:
            self.log(f"    ⚠️ Pre-flight failed: {e}", "WARNING")
            return []

    # V0.08 (P2 dead-code removal): the _extract_key_quotes method (always
    # returned [] since V16.0.2) and its zero-effect plumbing through
    # map_reduce.section_map_reduce were deleted.

    def _normalize_bullets(self, bullets: list[str]) -> list[str]:
        """V16.0.2: Universal bullet normalization pass. Strips inconsistent prefixes.

        V18.2.7: Improved to handle:
        - Gap-fill bullets that arrive as "**Author**: text" (strip the bold,
          keep the author name plain)
        - Remove "…" truncation artifacts (incomplete bullets)
        - Format academic years as italic + smaller: "Author (1980)" →
          "Author (<em style='font-size:0.9em'>1980</em>)" — but ONLY in the
          markdown output, not the raw bullets (the markdown formatter handles
          the <em> tag; here we just ensure the year is in parentheses)

        V18.6 (Phase 4, Task 4.3): logic extracted to
        ``post_processing.normalize_bullets`` (pure function, no ``self``).
        This method is now a thin delegate. Byte-for-byte identical output
        (characterization tests in ``tests/test_post_processing.py``).
        """
        from core.summarisation.post_processing import normalize_bullets as _pp_normalize
        return _pp_normalize(bullets)

    def _select_prompt(self, base_name: str) -> str:
        """V18.5 (Phase 3, Task 3.3): Select the prompt variant for the active model.

        For low-bit quant models (IQ2_XXS/XS/S, Q2_K*), appends ``_lowbit``
        to the base name IF a ``_lowbit`` variant exists in the prompt bank.
        Returns the base name unchanged for full-precision models or when
        no ``_lowbit`` variant is available (graceful fallback).

        This is the single wiring point for the Phase 3 lowbit-prompt system.
        Every call site that renders a leak-prone prompt should call this
        instead of hardcoding the name:

            name = self._select_prompt("summarisation/default")
            prompt = self.prompt_manager.render_template(name, ...)

        The lowbit variants are short, imperative, few-shot prompts with an
        explicit ``### FORBIDDEN ###`` section — they prevent the low-bit
        quant from leaking its internal reasoning ("Bullet 1:", "KEEP BOTH")
        into the output. See ``bullet_consolidation_lowbit.md`` for the
        canonical pattern and ``default_lowbit.md`` / etc. for the Phase 3
        additions.

        The existing ``_consolidate_bullets`` method (V18.2.44) inlined this
        logic; this helper extracts it so every leak-prone call site shares
        one implementation.
        """
        from core.llm.model_taxonomy import is_low_bit_quant
        if not is_low_bit_quant(self.primary_model):
            return base_name
        _lowbit_name = f"{base_name}_lowbit"
        # Check if the _lowbit variant exists before using it (graceful
        # fallback — if the variant file is missing, use the base prompt).
        if self.prompt_manager.load_prompt(_lowbit_name) is not None:
            self.log(
                f"    \U0001f9ee V18.5: low-bit quant detected — using "
                f"'{_lowbit_name}' (short, imperative, few-shot)",
                "DEBUG",
            )
            return _lowbit_name
        return base_name

    def _consolidate_bullets(self, bullets: list[str], heading: str | None = None) -> list[str]:
        """V16.0.2: LLM-assisted bullet consolidation (merge near-duplicates).

        V18.11 (Phase 5 Stage 3, Batch 1.4): logic extracted verbatim to
        ``bullet_consolidation.consolidate_bullets``. The mutable
        ``self._leak_guard_fire_count`` is passed in as an int parameter and
        the (possibly incremented) new count is returned alongside the
        consolidated bullets; this delegate unpacks and re-assigns it to
        ``self._leak_guard_fire_count`` (kept as a plain int per
        ``test_leak_guard_counter.py``). Byte-for-byte identical behaviour
        (characterization tests in ``tests/test_bullet_consolidation.py``;
        the existing ``test_consolidation_leak_guard.py`` exercises the
        BulletPipeline guard, and ``test_deadline_watchdog.py`` asserts the
        call site ``self._consolidate_bullets(bullets)`` in ``_summarize_inner``
        is preserved).

        V18.20.3.7 (audit v182036 RC-A): when ``heading`` is given, the
        delegate builds the deterministic author-coverage closure (the SAME
        analysis + ``check_coverage`` the V18.14 judge uses) and passes it
        down, arming the consolidation coverage assertion + truncation-aware
        salvage inside ``consolidate_bullets``. Thread-safe by construction:
        the heading travels as a parameter, never as shared instance state.
        """
        _coverage_fn = None
        if heading:
            def _coverage_fn(bs: list[str]):
                try:
                    from core.preprocessing.deterministic_analyzer import (
                        check_coverage,
                        find_analysis_for_heading,
                    )
                    _seg_path_c, _analysis_c = find_analysis_for_heading(
                        self.request.output_dir, heading,
                        log_fn=lambda msg, level="DEBUG": self.log(msg, level),
                    )
                    if not _analysis_c:
                        return None
                    cov = check_coverage(_analysis_c, " ".join(str(b) for b in bs))
                    return set(cov.get("covered", [])) or None
                except Exception:
                    return None  # assertion disabled — never break the chapter
        result, self._leak_guard_fire_count = bc_consolidate_bullets(
            bullets,
            leak_guard_fire_count=self._leak_guard_fire_count,
            prompt_manager=self.prompt_manager,
            select_prompt=self._select_prompt,
            call_llm_with_empty_retry=self._call_llm_with_empty_retry,
            primary_model=self.primary_model,
            temperature=self.temperature,
            strip_thinking=self._strip_thinking,
            consolidate_duplicate_claims=self._consolidate_duplicate_claims,
            log=self.log,
            author_coverage_fn=_coverage_fn,
        )
        return result


    def _switch_to_fast_model(self):
        """V16.0.9: Unload the heavy model before loading the fast model.

        Only applies to ``dual_local`` mode — in single modes there's nothing
        to unload (same model), and in API modes the fast model runs in the
        cloud (no local VRAM contention).
        """
        arch = getattr(self.request, "model_architecture", "single_local") or "single_local"
        if arch == "dual_local":
            self._recover_vram(context="switch-to-fast", delay_sec=10.0)

    def _switch_to_heavy_model(self):
        """V16.0.9: Unload the fast model before loading the heavy model.

        Only applies to ``dual_local`` mode — the heavy model needs the full
        VRAM budget that the fast model is occupying. The longer 30s delay
        gives Ollama time to evict the fast model + the heavy model time to
        load before the next call.
        """
        arch = getattr(self.request, "model_architecture", "single_local") or "single_local"
        if arch == "dual_local":
            self._recover_vram(context="switch-to-heavy", delay_sec=30.0)

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
            prompt, max_tokens=max_tokens, temperature=temperature,
            request=self.request,
            call_llm_with_empty_retry=self._call_llm_with_empty_retry,
            switch_to_fast_model=self._switch_to_fast_model,
            call_fast_ollama=self._call_fast_ollama,
            switch_to_heavy_model=self._switch_to_heavy_model,
            call_openai_compat=self._call_openai_compat,
            log=self.log,
        )

    def _call_fast_ollama(self, prompt: str, model: str, temp: float, max_tokens: int) -> str | None:
        """V18.8 (Phase 5.3): delegates to llm_dispatcher.call_fast_ollama.

        Migrated from inline ``for attempt in range(2)`` loop to
        ``@retry_llm_call`` decorator (the last holdout).
        """
        return ld_call_fast_ollama(
            prompt, model, temp, max_tokens,
            ollama_base_url=self.ollama_base_url,
            fast_model_context=getattr(self.request, "fast_model_context", 131072),
            log=self.log,
        )
    def _consolidate_duplicate_claims(self, bullets: list[str]) -> list[str]:
        """V13.44.0 Idea #5: Dedup consolidation pass.

        V18.11 (Phase 5 Stage 3, Batch 1.3): logic extracted verbatim to
        ``bullet_consolidation.consolidate_duplicate_claims`` (deterministic
        rapidfuzz near-dup merge, no LLM; the only ``self`` dep was
        ``self.log``, now passed as the ``log`` callback). This method is a
        thin delegate. Byte-for-byte identical output (characterization tests
        in ``tests/test_bullet_consolidation.py``).
        """
        return bc_consolidate_duplicate_claims(bullets, log=self.log)

    def _thematic_synthesis(self, heading: str, merged_thorough: str, source_text: str) -> str | None:
        """V13.44.0 Idea #3: Thematic synthesis pass.

        Takes the merged B4 thorough summary (which is a concatenation of section
        summaries in section order) and reorganizes it by THEME with flowing
        paragraphs and cross-section connections.

        Universal: every book benefits from thematic organization. The model
        discovers the themes by reading the merged summary.
        """
        self.log("    🔄 Thematic synthesis: reorganizing thorough summary by theme…", "INFO")
        lang = "Write in Persian (Farsi)." if self.language == "fa" else "Write in English."
        prompt = self.prompt_manager.render_template(
            self._select_prompt("summarisation/thematic_synthesis"),
            heading=heading,
            merged_thorough=merged_thorough,
            language=lang,
        )

        try:
            raw = self._call_llm_with_empty_retry(prompt, temperature=self.temperature, max_tokens=2048)
            if not raw:
                self.log("    ⚠️ Thematic synthesis: empty response, keeping original", "WARNING")
                return None
            raw = self._strip_thinking(raw)
            if len(raw.strip()) > 200:
                return raw.strip()[:6000]
            return None
        except Exception as e:
            self.log(f"    ⚠️ Thematic synthesis failed: {e}", "WARNING")
            return None

    def _section_map_reduce(self, heading: str, text: str,
                            concepts: list[str] | None = None,
                            callouts: list[str] | None = None) -> dict | None:
        """V3.3.0 B4: Split chapter into sections, summarize each, merge.

        V18.11 (Phase 5 Stage 3, Batch 2.5): logic extracted verbatim to
        ``map_reduce.section_map_reduce``. The ~15 self-deps are passed as
        explicit kwargs (the proven-safe pattern — NOT a context object).
        The 2 local imports (detect_sections, get_total_vram) stay as local
        imports inside the extracted function (verbatim). Byte-for-byte
        identical behaviour (characterization tests in
        ``tests/test_map_reduce.py``).
        """
        return mr_section_map_reduce(
            heading, text,
            concepts=concepts,
            callouts=callouts,
            primary_model=self.primary_model,
            temperature=self.temperature,
            is_local=self.is_local,
            local_preflight_skip_temp=self.local_preflight_skip_temp,
            last_gpu_temp=getattr(self, "_last_gpu_temp", 50),
            local_b4_section_cap=self.local_b4_section_cap,
            local_vram_recovery_delay=self.local_vram_recovery_delay,
            max_bullets_per_chapter=self.max_bullets_per_chapter,
            extract_must_have_items=self._extract_must_have_items,
            recover_vram=self._recover_vram,
            summarize_with_model=self._summarize_with_model,
            consolidate_duplicate_claims=self._consolidate_duplicate_claims,
            thematic_synthesis=self._thematic_synthesis,
            log=self.log,
        )

    def _summarize_inner(
        self,
        heading: str,
        content: str,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
        book_context: str = "",
    ) -> SummaryResult:
        """Summarise one chapter — the full 15-stage bullet pipeline.

        V18.1 (audit Q2): Added ``book_context`` parameter — a 150-word rolling
        synthesis of chapters 1..N-1, injected before the chapter text to give
        the LLM cross-chapter continuity (prevents repeating content already
        covered, helps maintain narrative flow across the book).

        V10.29.0 (Sprint 2.6): This docstring documents every stage so the
        1,035-line method is navigable.  Sprint 4 will extract each stage
        into its own method on ``BulletPipeline``; until then, this is the
        map.

        Stages (in execution order):
            1.  **Empty-input gate** — <80 tokens → abort (prevents
                hallucination from empty prompts).
            2.  **Map-Reduce routing** — >40k tokens → B4 section map-reduce;
                >8k tokens → section map-reduce attempt; else primary call.
            3.  **Primary LLM call** — ``_summarize_with_model`` at the
                user's temperature (model-profile minimum enforced).
            4.  **Coverage check** — ``_compute_coverage`` (keyword overlap).
                <threshold → B3 multi-sample voting (3 temps: 0.2/0.4/0.6).
            5.  **B3 dedup** — rapidfuzz token_set_ratio ≥75% merge.
                *(V10.28.0: conservative mode skips this; logs to quarantine.)*
            6.  **Response parsing** — ``_parse_response`` extracts
                exec_summary / bullets / thorough_summary.
            7.  **Thinking-filter** — ``_filter_thinking_bullets`` drops
                thinking-process, prompt-leakage, meta-commentary, narrative,
                numeric-verify failures, and low-quality-score bullets.
                *(V10.28.0: 4 thinking/prompt checks ALWAYS active; the rest
                are conservative-gated. Every drop → quarantine.)*
            8.  **F1 length validation** — exec ≤400 words, thorough ≤1500.
            9.  **F4 source-overlap drop** — ``compute_source_overlap < 0.25``.
                *(V10.28.0: conservative-gated; logged to quarantine.)*
            10. **Phase 2.2 semantic fact-check** —
                ``semantic_fact_check`` embedding similarity < 0.5.
                *(V10.28.0: threshold drift fixed — code+log now agree at 0.5.
                Conservative-gated; logged to quarantine.)*
            11. **F3 reading-level** — auto-simplify if summary is harder
                than source (one retry, no loop).
            12. **I2 difficulty scoring** + **J2 cross-section redundancy**
                — informational only (no drops).
            13. **C2 gap-fill** — uncovered concepts → targeted LLM call
                (≤8 concepts, ≤7 new bullets).
            14. **Content Judge** — ``ContentJudge.judge()`` grounding +
                coverage check.  Drops ungrounded bullets (LLM-as-judge +
                F4 cross-check when langextract is off).
                *(V10.28.0: conservative-gated; logged to quarantine.)*
            15. **Hard rejection** — >30% ungrounded OR coverage <30% →
                SummaryResult(success=False).  Bypassed for garbled source /
                verbatim quotes / short source / substantial content.
            16. **Recovery pass** *(V10.28.0)* — ``_recover_quarantined``
                re-scans the quarantine and resurrects bullets with
                source_overlap > 0.30.

        Quarantine: every drop at stages 5, 7, 9, 10, 14 is logged to
        ``self.quarantine`` (writes ``output/<book>/logs/drops.jsonl``).
        The recovery pass (stage 16) uses the recorded source_overlap to
        decide what to resurrect.

        Args:
            heading: Chapter heading (used for quarantine context + logging).
            content: Chapter source text (markdown).
            concepts: Optional list of concept keywords to inject into the
                prompt + use for coverage scoring.
            callouts: Optional list of callout phrases to inject.

        Returns:
            SummaryResult with executive_summary, bullet_points,
            thorough_summary, and token counts.  ``success=False`` if the
            empty-input gate or hard rejection triggers.
        """
        self._source_text = content
        # V10.28.0 (Sprint 1): track the current chapter heading so every
        # quarantine entry records which chapter the dropped bullet came from.
        self._current_heading = heading
        # V18.20.3.2 (P0-1): per-chapter CoT/synthetic flags — RESET every
        # chapter so a CoT nuke in chapter N never leaks into chapter N+1's
        # re-derivation decisions.
        self._primary_thorough_cot_nuked = False
        self._primary_exec_cot_nuked = False
        self._thorough_is_synthetic = False
        src_tokens = count_tokens(content)
        text = content
        tok_in = 0

        # V17.2/V17.5: Prepend deterministic analysis to the text gemma sees.
        # V17.5 fix: uses find_analysis_for_heading() instead of fragile
        # heading-to-filename matching. Searches the ENTIRE output tree.
        try:
            from core.preprocessing.deterministic_analyzer import find_analysis_for_heading
            _seg_path, _analysis = find_analysis_for_heading(
                self.request.output_dir, heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
            if _analysis:
                # V18.1 (audit Q2): Inject cross-chapter running context BEFORE
                # the deterministic analysis and chapter text. This gives the LLM
                # awareness of what previous chapters already covered, preventing
                # repetition and improving cross-chapter synthesis.
                _book_ctx_block = ""
                if book_context:
                    _book_ctx_block = (
                        f"## PREVIOUS CHAPTERS SYNTHESIS (for continuity — "
                        f"do NOT repeat this content, focus on THIS chapter's NEW content):\n"
                        f"{book_context}\n\n---\n\n"
                    )
                text = _book_ctx_block + _analysis + "\n\n---\n\n## CHAPTER TEXT\n\n" + text
                self.log(f"    📊 V17.2: Prepended deterministic analysis ({len(_analysis)} chars) — citation recall 78%→100%", "INFO")
                if book_context:
                    self.log(f"    📚 V18.1: Cross-chapter context injected ({len(book_context)} chars from previous chapters)", "INFO")
            else:
                self.log("    ⚠️ V17.5: No deterministic analysis found — running without prepend (old behavior)", "DEBUG")
        except Exception as _e:
            self.log(f"    ⚠️ V17.5: Deterministic analysis load failed: {_e}", "WARNING")

        # Empty/near-empty input gate — if the segment
        # has almost no content (< 80 tokens), DO NOT call the LLM.  Sending
        # an empty prompt causes the model to fabricate an entire essay from
        # its training data (the karsan2022 Memantine hallucination).  Mark
        # as failed instead.
        if src_tokens < 80:
            msg = f"Segment too small ({src_tokens} tokens) — skipping to prevent hallucination"
            self.log(f"    🚫 {msg}", "WARNING")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary="",
                success=False,
                error_msg=msg,
                input_tokens=src_tokens,
                output_tokens=0,
            )

        # ── Map‑Reduce if needed ──────────────────────────────────────────
        if src_tokens > self.MAP_REDUCE_THRESHOLD:
            self.log(f"    🗺️ Chapter too large for single call ({src_tokens:,} tokens > {self.MAP_REDUCE_THRESHOLD:,}) — switching to Map-Reduce", "INFO")
            raw, combined_tokens = self._map_reduce_summarize(heading, content)
            tok_in = combined_tokens
            if not raw:
                return SummaryResult(chapter_heading=heading, executive_summary="[Error: Map-Reduce failed]", bullet_points=[], thorough_summary="", success=False, error_msg="Map-Reduce returned no response", input_tokens=tok_in, output_tokens=0)
            parsed = self._parse_response(raw)
        else:
            # ── Prepare text (truncate if needed) ──────────────────────────
            text = self._prepare_text(content)
            tok_in = count_tokens(text)

            # ── Primary model pass (V3.2.0 B1: pass concepts + callouts) ───
            # For long chapters (>8000 tokens), try section map-reduce
            # first — it guarantees every section gets LLM attention.
            model = self.primary_model
            self.log(f"    ⚡ Using primary model: {model}", "INFO")
            if concepts:
                self.log(f"    🎯 Injecting {len(concepts)} concepts + {len(callouts or [])} callouts into prompt", "DEBUG")

            result = None
            # B4: Section map-reduce for long chapters
            # V18.2 (audit): Threshold is now configurable via
            # settings.summarisation.b4_threshold_tokens (default 12000).
            # Was hardcoded 8000, which triggered B4 for a 9127-token chapter
            # = 3 LLM calls + must-have pre-flight + consolidation = 6 calls.
            # On a 27B/12GB card (spilling to CPU), each call takes 10+ min,
            # so 6 calls = 1 hour. Raising to 12000 lets most chapters
            # (under ~50 pages) do single-pass = 1 call = ~10 min.
            # The original V13.40.3 comment said B4 gave 85% coverage vs 62%
            # single-pass at 9k tokens — but that was with Gemma 12B.
            # For 27B models with larger context windows, single-pass at 9k
            # tokens should be fine. Users can lower to 8000 if coverage drops.
            from utils.settings import Settings as _B4Settings
            _b4_threshold = _B4Settings().get("summarisation.b4_threshold_tokens", 12000)
            if tok_in > _b4_threshold:
                self.log(f"    📑 Chapter is long ({tok_in:,} tokens > {_b4_threshold:,} threshold) — trying section map-reduce (B4)…", "INFO")
                result = self._section_map_reduce(heading, text, concepts, callouts)
                if result:
                    self.log("    ✅ Section map-reduce succeeded", "INFO")
                    # V13.40.0: Recover VRAM after B4 map-reduce. The 3+ sequential
                    # LLM calls (each ~4 min) leave the GPU stressed. Without
                    # recovery, subsequent self-review + gap-fill return empty.
                    self._recover_vram(context="post-B4-map-reduce", delay_sec=10.0)
                else:
                    self.log("    ℹ️ Section map-reduce not applicable — using single-pass", "DEBUG")

            # Standard single-pass if B4 didn't apply or failed
            if not result:
                result = self._summarize_with_model(
                    heading, text, model, self.temperature, with_cot=True,
                    concepts=concepts, callouts=callouts,
                )

            if not result:
                msg = f"Primary model {model} returned no response"
                self.log(f"    ❌ {msg}", "ERROR")
                # V18.15.6.0 (Fix B): distinguish "model not installed" (404)
                # from "model timed out during generation" (HTTP timeout). The
                # pre-V18.15.6.0 code always said "not installed" even when the
                # model WAS loaded (S19 pre-warm succeeded 20 min earlier) and
                # the real cause was a per-call HTTP timeout mid-generation.
                # The _last_llm_error_type is set by _call_ollama based on the
                # error_tracker out-param propagated from llm_dispatcher.
                _err_type = getattr(self, "_last_llm_error_type", None)
                if _err_type == "timeout":
                    hint = (
                        f"Likely cause: model '{model}' timed out after {self.timeout}s "
                        f"during generation (the model WAS loaded — S19 pre-warm succeeded; "
                        f"the per-call HTTP timeout fired mid-generation). "
                        f"Fix: raise `local.http_timeout_sec` in Settings (current: {self.timeout}s), "
                        f"or reduce input size, or switch to a faster quant."
                    )
                elif _err_type == "oom":
                    hint = (
                        f"Likely cause: model '{model}' ran out of VRAM (OOM). "
                        f"Fix: reduce `summarisation_max_context_tokens` in Settings, "
                        f"or switch to a smaller model."
                    )
                elif _err_type == "not_found":
                    hint = (
                        f"Likely cause: model '{model}' is not installed in Ollama. "
                        f"Fix: `ollama pull {model}`, or change the model in Settings → Summarisation."
                    )
                else:
                    # "empty" or unknown — keep the legacy hint (covers the
                    # short-response-after-retry case where no exception fired).
                    hint = (
                        f"Likely cause: model '{model}' returned an empty/short response after retry. "
                        f"If persistent: check Ollama is running (`ollama list` shows '{model}'), "
                        f"or raise `local.http_timeout_sec` in Settings, or switch to a faster quant."
                    )
                self.log(f"    💡 {hint}", "ERROR")
                return SummaryResult(
                    chapter_heading=heading,
                    executive_summary="",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg=f"{msg}. {hint}",
                    input_tokens=tok_in,
                    output_tokens=0,
                )

            # ── Verbose: log what the model returned ───────────────────────
            _bps_count = len([b for b in result.get('bullet_points', []) if b])
            _exec_len = len(result.get('executive_summary', ''))
            _thorough_len = len(result.get('thorough_summary', ''))
            self.log(f"    📝 Parsed: exec={_exec_len} chars, bullets={_bps_count}, thorough={_thorough_len} chars", "DEBUG")

            # V0.06 (rig audit F1-b — GENERAL RULE: the output selection is
            # the contract, enforced at PARSE time): when the user did not
            # request a thorough summary, ANY thorough content the model
            # produced anyway (the parser's leftover fallback can capture
            # unrequested additive-section output; a low-bit model may emit
            # the tag regardless) is discarded HERE, so every downstream
            # stage (coverage, judges, expansion gates, render) sees the
            # contract state: no thorough. The V0.05 rig shipped "Thorough
            # Summary" sections to a user who unchecked the output because
            # this gate did not exist.
            if not bool(getattr(self.request, "include_thorough_summary", True)):
                if (result.get("thorough_summary", "") or "").strip():
                    self.log(
                        f"    V0.06: thorough_summary not requested — discarding "
                        f"{_thorough_len} chars of unrequested thorough content "
                        f"(output-selection contract).",
                        "DEBUG",
                    )
                result["thorough_summary"] = ""
            if not bool(getattr(self.request, "include_keypoints", True)):
                if result.get("bullet_points", []):
                    self.log(
                        f"    V0.06: keypoints not requested — discarding "
                        f"{_bps_count} unrequested bullet(s) "
                        f"(output-selection contract).",
                        "DEBUG",
                    )
                result["bullet_points"] = []
            if not bool(getattr(self.request, "include_executive_summary", True)):
                if (result.get("executive_summary", "") or "").strip():
                    self.log(
                        f"    V0.06: executive_summary not requested — discarding "
                        f"{_exec_len} chars of unrequested exec content "
                        f"(output-selection contract).",
                        "DEBUG",
                    )
                result["executive_summary"] = ""

            # ── V18.20.3.2 (audit N2+N3 / P0-1a): PARSE-TIME CoT gate ──────
            # The V18.20.3.1 real-rig run's primary call returned exec=0 and
            # a 34,794-char thorough that was 100% chain-of-thought. Nothing
            # detected it until run_post_checks fired the V18.19.2.2 CoT-nuke
            # 26 MINUTES later — by then every thorough-section gate (the
            # V18.14 thorough-only judge, gap-fill decisions) had already
            # validated the CoT text, and the shipped "Thorough Summary" was
            # a verbatim copy of the 191-word exec. Nuking HERE means every
            # downstream stage sees the REAL state: the dedicated-thorough
            # path regenerates a real thorough, coverage is computed on real
            # text (CoT inflates it — the model's reasoning mentions
            # everything), and the V18.14 judges measure what ships.
            try:
                from core.summarisation.postchecks import detect_cot_narrative
                _p_tho = result.get("thorough_summary", "") or ""
                if _p_tho:
                    _p_tho_clean, _p_tho_cot = detect_cot_narrative(_p_tho, "thorough")
                    if _p_tho_cot:
                        self.log(
                            f"    🚨 V18.20.3.2: primary-call thorough is CoT "
                            f"narrative ({len(_p_tho)} chars, {_p_tho_cot[0].detail[:60]}…) "
                            f"— DISCARDED AT PARSE TIME. The dedicated-thorough "
                            f"call will regenerate a real one; all downstream "
                            f"gates will judge the REAL text.",
                            "WARNING",
                        )
                        result["thorough_summary"] = ""
                        self._primary_thorough_cot_nuked = True
                _p_exec = result.get("executive_summary", "") or ""
                if _p_exec:
                    _p_exec_clean, _p_exec_cot = detect_cot_narrative(_p_exec, "exec")
                    if _p_exec_cot:
                        self.log(
                            f"    🚨 V18.20.3.2: primary-call exec is CoT "
                            f"narrative ({len(_p_exec)} chars) — DISCARDED AT "
                            f"PARSE TIME (exec-from-thorough will re-derive).",
                            "WARNING",
                        )
                        result["executive_summary"] = ""
                        self._primary_exec_cot_nuked = True
            except Exception as _cot_e:
                logger.debug("parse-time CoT gate crashed (non-fatal): %s: %s",
                             type(_cot_e).__name__, _cot_e)
                # V18.20.4.11 (P2 / W-a12): the CoT gate is anti-hallucination
                # machinery — a crashed gate silently re-admits CoT narrative
                # as "summary" text. The DEBUG-only trace made that invisible
                # in every real-rig log. Keep the debug trace, ADD a visible
                # WARNING (honesty-machinery failures must be LOUD).
                self.log(
                    f"    ⚠️ V18.20.4.11: parse-time CoT gate crashed (non-fatal — "
                    f"gate skipped for this chapter): "
                    f"{type(_cot_e).__name__}: {_cot_e}",
                    "WARNING",
                )

            # ── Compute coverage ────────────────────────────────────────────
            _bps = [str(b) if not isinstance(b, str) else b for b in result.get('bullet_points', []) if b]
            combined_summary = f"{result.get('executive_summary', '')} {' '.join(_bps)} {result.get('thorough_summary', '')}"
            coverage = self._compute_coverage(content, combined_summary)
            self._last_coverage = coverage  # V13.40.4: for self-review skip decision
            self.log(f"    📊 Primary coverage: {coverage:.0%} | keywords: {self._extract_keywords(content, n=8)}", "INFO")

            # DEBUG — log which keywords are found vs missing for
            # diagnosing low-coverage chapters (e.g. Chapter 3 at 61%).
            _all_kw = self._extract_keywords(content, n=18)
            _sl = combined_summary.lower()
            _found = [k for k in _all_kw if k in _sl]
            _missing = [k for k in _all_kw if k not in _sl]
            self.log(
                f"    🔍 Coverage detail: {len(_found)}/{len(_all_kw)} keywords found | "
                f"missing: {_missing[:8]}{'…' if len(_missing) > 8 else ''}",
                "DEBUG",
            )

            # ── Heavy model fallback ──────────────────────────────────────────
            # Multi-sampling + voting fallback for low coverage
            _used_b3_voting = False
            # V15.1.1: B3 disabled by default — damages conceptual depth.
            # The consensus voting produces bland exec summaries (402 chars
            # vs V13.45.5's 974 chars) and loses specific theorist details.
            # When disabled, coverage falls through to 3-Tier + gap-fill +
            # over-delivery, which is deterministic and targeted.
            if (round(coverage, 2) < self.coverage_threshold and not self.heavy_model
                    and self.b3_voting_enabled):  # V15.1.1: gated
                self.log(f"    🔄 Coverage {coverage:.0%} < {self.coverage_threshold:.0%} – trying multi-sample voting (B3)…", "INFO")
                voted = self._multi_sample_summarize(heading, text, concepts, callouts, n_samples=3)
                if voted:
                    _vbps = [str(b) if not isinstance(b, str) else b for b in voted.get('bullet_points', []) if b]
                    voted_combined = f"{voted.get('executive_summary', '')} {' '.join(_vbps)} {voted.get('thorough_summary', '')}"
                    voted_coverage = self._compute_coverage(content, voted_combined)
                    self.log(f"    📊 Voted coverage: {voted_coverage:.0%}", "INFO")
                    if voted_coverage > coverage:
                        result = voted
                        coverage = voted_coverage
                        _used_b3_voting = True
                        self._last_coverage = coverage  # V13.40.5: update for self-review skip
                        self.log(f"    ✅ Multi-sample voting improved coverage to {coverage:.0%}", "INFO")
            elif round(coverage, 2) < self.coverage_threshold and not self.b3_voting_enabled:
                self.log(
                    f"    ℹ️ Coverage {coverage:.0%} < {self.coverage_threshold:.0%} — B3 voting disabled, "
                    f"will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward {self._effective_target:.0%}",
                    "INFO",
                )

            if coverage < self.coverage_threshold and self.heavy_model:
                self.log(f"    🔥 Coverage {coverage:.0%} < {self.coverage_threshold:.0%} – using heavy model: {self.heavy_model}", "INFO")
                heavy_result = self._summarize_with_model(heading, text, self.heavy_model, self.temperature * 0.5, with_cot=True)
                if heavy_result:
                    _hbps = [str(b) if not isinstance(b, str) else b for b in heavy_result.get('bullet_points', []) if b]
                    heavy_combined = f"{heavy_result.get('executive_summary', '')} {' '.join(_hbps)} {heavy_result.get('thorough_summary', '')}"
                    heavy_coverage = self._compute_coverage(content, heavy_combined)
                    self.log(f"    📊 Heavy coverage: {heavy_coverage:.0%}", "INFO")
                    if heavy_coverage > coverage:
                        merged_bullets = list(heavy_result.get("bullet_points", []))
                        for bp in result.get("bullet_points", []):
                            if bp not in merged_bullets:
                                merged_bullets.append(bp)
                        result["executive_summary"] = heavy_result.get("executive_summary", result.get("executive_summary", ""))
                        result["thorough_summary"] = heavy_result.get("thorough_summary", result.get("thorough_summary", ""))
                        result["bullet_points"] = merged_bullets[:self.max_bullets_per_chapter]
                        result["model"] = "primary+heavy"
                        self.log("    ✅ Merged primary + heavy summaries", "INFO")
                    else:
                        for bp in heavy_result.get("bullet_points", []):
                            if bp not in result.get("bullet_points", []):
                                result["bullet_points"].append(bp)
                        result["bullet_points"] = result["bullet_points"][:self.max_bullets_per_chapter]
                        result["model"] = "primary+heavy_bullets"
                        self.log("    ✅ Added unique heavy bullets to primary summary", "INFO")
                else:
                    self.log("    ⚠️ Heavy model returned no response, keeping primary", "WARNING")

            # ── V13.32.8: 3-Tier Coverage Guarantee System ──────────────────
            # V15.1.0: Use _effective_target (over-delivery target when enabled,
            # falls back to coverage_threshold). This is the "don't settle" logic:
            # if user set 85% but over-delivery target is 92%, we keep gap-filling
            # until 92% (or no more concepts to fill).
            if coverage < self._effective_target:
                _od_note = ""
                if self.overdeliver_enabled and self.overdeliver_target > self.coverage_threshold:
                    _od_note = f" (over-deliver: floor {self.coverage_threshold:.0%} → target {self.overdeliver_target:.0%})"
                self.log(
                    f"    📈 Coverage {coverage:.0%} < effective target {self._effective_target:.0%}"
                    f"{_od_note} — applying 3-Tier Guarantee",
                    "INFO",
                )
                coverage = self._apply_3tier_coverage(
                    heading, text, content, result, coverage,
                )

            # ── Old academic-rigor gap-fill: removed in V0.08 (P2) — it was an
            # `if False` dead block since V18.6, superseded by the 3-Tier
            # coverage guarantee above. ──

            # ── Post-filter: remove thinking-process bullets + quality scoring ─
            # Pass concepts + source_text for quality scoring
            # Skip aggressive C1/C4 filtering if B3 voting was used —
            # voted bullets are already consensus-validated across 3 samples.
            if _used_b3_voting:
                # Light filtering only: strip thinking + narrative, no quality scoring
                result["bullet_points"] = self._filter_thinking_bullets(
                    result.get("bullet_points", []),
                    concepts=None,  # None = skip C1 quality scoring
                    source_text="",  # empty = skip C4 numeric verification
                )
                self.log(f"    ℹ️ B3 voted bullets — skipping aggressive C1/C4 filtering (kept {len(result.get('bullet_points', []))})", "DEBUG")
            else:
                result["bullet_points"] = self._filter_thinking_bullets(
                    result.get("bullet_points", []),
                    concepts=concepts,
                    source_text=content,
                )
            result["executive_summary"] = self._strip_thinking(result.get("executive_summary", ""))
            result["thorough_summary"] = self._strip_thinking(result.get("thorough_summary", ""))

            # V18.19.2.4 (Crash Fix) / V18.20.1.2 (refactored to _save_checkpoint):
            # Emergency checkpoint save of the primary-call output BEFORE the
            # additive-sections / judge / postchecks phases. See _save_checkpoint
            # docstring for the full rationale. See audit/results/audit_V18.19.2.3_crash.md.
            self._save_checkpoint(heading, result, label="primary")

            # ── A3: Fact-Checking Pipeline (deterministic) ────────────────
            # For each bullet, fuzzy-match against the source text. If no
            # match > 60% similarity, mark as "⚠️ Unverified".
            result["bullet_points"] = self._verify_bullets(
                result.get("bullet_points", []), content
            )

            # V13.39.0: Anti-hallucination verification for additive sections.
            # V13.40.0: First, ensure the sections are populated — in academic-rigor
            # JSON mode, the model often omits key_distinctions/theoretical_tensions.
            # This followup call populates them if empty, then verification checks them.
            self._ensure_additive_sections(heading, content, result)
            self._verify_additive_sections(heading, content, result)

            # V18.20.1.2 (crash mitigation): SECOND checkpoint AFTER additive
            # sections + bullet verification. The V18.19.2.4 crash (process killed
            # during additive-sections) + the V18.20.1.1 crash (process killed
            # during thorough-expansion, which runs AFTER additive-sections)
            # showed that the primary-call checkpoint alone isn't enough — the
            # additive-sections call is expensive and can crash, losing its output.
            # This checkpoint captures the state AFTER additive sections are
            # populated, so if the thorough-expansion call (the next expensive
            # phase) crashes, the user still gets exec + bullets + key_distinctions
            # + theoretical_tensions. The thorough may be empty (if the primary
            # didn't produce it), but that's strictly better than losing everything.
            self._save_checkpoint(heading, result, label="post-additive-sections")

            # V13.6.0: Create BulletPipeline + PipelineState EARLY — needed
            # by self-consistency/review (line 2654) and academic factual
            # verification (line 2730), which both run BEFORE the F4/Phase2.2
            # pipeline stages. Previously _pipeline was created at line ~2772,
            # causing UnboundLocalError when academic_rigor triggered the
            # self-review path.
            from core.summarisation.bullet_pipeline import BulletPipeline, PipelineState
            _pipeline = BulletPipeline(self)
            _pstate = PipelineState(
                heading=heading, content=content,
                bullets=result.get("bullet_points", []),
                exec_sum=result.get("executive_summary", ""),
                thorough=result.get("thorough_summary", ""),
            )

            # V10.36.0: Self-consistency + self-review extracted to BulletPipeline.
            _pipeline.run_self_consistency_and_review(_pstate, result, heading, text)
            result = _pstate.__dict__.get('_result', result)  # get updated result if modified
            parsed = result

        # ── Ensure thorough is long enough ──────────────────────────────────
        exec_sum = parsed.get("executive_summary", "")
        bullets = parsed.get("bullet_points", [])
        thorough = parsed.get("thorough_summary", "")
        # V18.2.34: Replaced the old "len(thorough) < len(exec_sum) * 2" check
        # (a fragile character-length heuristic) with a strict 800-word floor.
        # V0.05 (rig audit F9b — GENERAL RULE REPLACEMENT): the floor is no
        # longer the absolute 800 — it SCALES to the source (length_policy:
        # thorough_target). The V0.04 rig proved the absolute floor's failure
        # mode end-to-end: 321-441-word chapters were force-EXPANDED to >=800
        # words (the delivered thorough sections measured 1.55-2.76x their
        # sources, padded with invented context — hallucination-by-
        # instruction). A short chapter's thorough summary is ALLOWED to be
        # short: ~90-150 words for a 340-word chapter is the correct
        # deliverable. The dedicated expansion call now only fires when the
        # thorough is short RELATIVE TO ITS SCALED TARGET — and never when
        # the user did not request a thorough summary at all (F9a).
        from core.summarisation.length_policy import (
            bullet_target as _bp_target_lp,
            count_source_words as _csw_lp,
            thorough_target as _th_target_lp,
        )
        _src_words_lp = _csw_lp(text)
        _th_lo_lp, _th_hi_lp = _th_target_lp(_src_words_lp)
        _bp_lo_lp, _bp_hi_lp = _bp_target_lp(_src_words_lp)
        _inc_thorough_lp = bool(getattr(self.request, "include_thorough_summary", True))
        _inc_exec_lp = bool(getattr(self.request, "include_executive_summary", True))
        _inc_kp_lp = bool(getattr(self.request, "include_keypoints", True))
        _thorough_words = len(thorough.split()) if thorough else 0
        # V0.07 (output-regression fix): normal chapters (scaled thorough
        # hi >= 800 — the V18 regime) expand below 800 words, restoring
        # MarkItDown V18's expansion contract; small sources (the 97-Things
        # rig regime, hi < 800) keep the source-scaled lo so tiny chapters
        # are never force-expanded to 800+ words.
        _new_threshold = (800 if _th_hi_lp >= 800 else _th_lo_lp) if _inc_thorough_lp else 0
        # V18.20.3.2 (P0-1b): snapshot the synthetic-fallback counter BEFORE
        # the dedicated call — if it increments, the returned thorough is the
        # deterministic exec+bullets synthesis built from the EARLY bullet
        # set (pre-expansion, pre-gap-fill). The final stage re-derives it
        # from the FINAL bullet set in that case (see the postchecks block).
        _syn_fb_before = getattr(self, "_synthetic_thorough_fallback_count", 0)
        if _inc_thorough_lp and (not thorough or _thorough_words < _new_threshold):
            self.log(f"    ⚠️ thorough_summary too short ({_thorough_words} words < {_new_threshold} threshold) — requesting dedicated expansion…", "WARNING")
            # V18.2.44 (Next Step #6): replaced the 2-attempt
            # ``_call_llm_with_empty_retry`` with the new 3-attempt +
            # synthetic-fallback helper. The V18.2.43 session noted the
            # dedicated expansion "sometimes fails (empty responses)" — this
            # makes the path robust: 3 attempts at varying temperature /
            # nudges, then a deterministic exec+bullets synthesis so the
            # thorough is NEVER empty (was silently degrading to a 1-para
            # ``thorough = exec_sum`` stub before).
            _dedicated_prompt = self._build_dedicated_thorough_prompt(
                heading, text, exec_sum, bullets,
                # V18.20.3.11 (Phase 3.b, .3.9 rig audit §2): pass the
                # primary's partial thorough as the continuation draft —
                # it was cut at the primary's output cap (423-763 words
                # across rig runs .3.7-.3.9) and previously discarded,
                # paying the truncation twice. Empty/CoT-nuked thorough
                # renders the block inert (draft=None path).
                draft=(thorough or None),
            )
            fu_raw = self._call_dedicated_thorough_with_fallback(
                _dedicated_prompt, exec_sum=exec_sum, bullets=bullets,
                min_words=_new_threshold,
            )
            if fu_raw:
                fu_raw = self._strip_thinking(fu_raw)
                m = re.search(r'<thorough_summary>(.*?)</thorough_summary>', fu_raw, re.DOTALL)
                if m:
                    _new_thorough = m.group(1).strip()
                else:
                    _new_thorough = fu_raw.strip()
                if _new_thorough and len(_new_thorough.split()) > _thorough_words:
                    thorough = _new_thorough
                    self.log(f"    ✅ thorough_summary expanded via dedicated call: {_thorough_words} → {len(thorough.split())} words", "INFO")
                elif _new_thorough:
                    self.log(f"    ℹ️ Dedicated thorough call returned {len(_new_thorough.split())} words (not longer than original {_thorough_words}) — keeping original", "DEBUG")
        # V18.20.3.2 (P0-1b): flag when the dedicated call fell back to the
        # deterministic synthesis (early bullets only) — the final stage
        # rebuilds it from the final bullet set.
        self._thorough_is_synthetic = (
            getattr(self, "_synthetic_thorough_fallback_count", 0) > _syn_fb_before
        )
        # V18.15.8.0 (Fix 1): Reorder — produce thorough first, then derive
        # exec FROM thorough. The thorough summary has a dedicated system with
        # 100% coverage (the dedicated thorough call at line 3060 ensures
        # thorough is NEVER empty). When exec_sum is empty, we derive it FROM
        # the thorough summary via a followup LLM call — NOT the pre-V18.15.8.0
        # backwards fallback (``thorough = exec_sum`` which copied an empty
        # string when exec was also empty, causing the V18.15.7.0 cascade
        # failure where BOTH exec + thorough were empty).
        # V0.05 (F9a): the exec-from-thorough derivation only fires when the
        # user actually requested an executive summary — the flags are the
        # contract.
        if _inc_exec_lp and not exec_sum and thorough and len(thorough.strip()) >= 50:
            exec_sum = self._ensure_exec_from_thorough(heading, thorough)
            if exec_sum:
                parsed["executive_summary"] = exec_sum
        # Last-resort fallback (rare now — only fires if BOTH the dedicated
        # thorough call AND the exec-from-thorough call failed).
        # V0.05 (F9a): never fabricate a thorough the user did not request.
        if not thorough and _inc_thorough_lp:
            thorough = exec_sum

        # V18.2.34: Dedicated bullet expansion. If the primary call returned
        # <30 bullets, fire a STANDALONE bullet-expansion LLM call (full
        # output budget) asking for 30-50 NEW bullets. The existing bullets
        # are kept; new bullets are de-duplicated against them before being
        # appended. This addresses the V18.2.28 regression where the
        # primary call was truncated by the 2048-token output cap and
        # returned only 4-7 bullets per chapter.
        bullets = parsed.get("bullet_points", bullets) or bullets
        # V18.15.4.0: Skip bullet expansion for short chapters (< 10000 tokens)
        # that already have >= 20 bullets. The expansion call adds ~7 minutes
        # and is unnecessary for short chapters with adequate coverage. The
        # gap-fill loop will still add any missing theorists. This prevents
        # the deadline from being consumed by expansion on chapters that
        # don't need it (the the rig-test chapter is 9120 tokens with 24
        # bullets — expansion to 71 was overkill and pushed past the deadline).
        _input_tok = count_tokens(text)
        # V18.15.4.3: Raised threshold 9000 -> 10000 tok (the V18.15.4.0 run hit
        # 9120 tok and the skip didn't fire, pushing past the 2400s deadline).
        # V0.05 (rig audit F9b — GENERAL RULE): the expansion floor/ceiling now
        # SCALE to the source (length_policy.bullet_target) instead of the
        # absolute "<30 → ask for 30-50". The V0.04 rig shipped 29-36 bullets
        # for 321-441-word chapters (one bullet per ~12 source words — the
        # chapter restated as bullets) because this machinery pushed every
        # chapter toward 30+. A 340-word chapter's target is ~5-7 bullets; the
        # expansion call does not fire at all when the primary already met the
        # SCALED target. Also gated on the user's keypoints selection (F9a).
        _skip_expansion = (
            not _inc_kp_lp
            or bool(bullets and len(bullets) >= _bp_lo_lp)
        )
        if _skip_expansion and _inc_kp_lp:
            self.log(
                f"    V0.05: Skipping bullet expansion — {len(bullets or [])} bullets "
                f"already meet the source-scaled target ({_bp_lo_lp}-{_bp_hi_lp} for "
                f"a {_src_words_lp}-word chapter; gap-fill will handle missing "
                f"concepts).",
                "INFO",
            )
        elif not _inc_kp_lp:
            self.log(
                "    V0.05 (F9a): Keypoints not requested — bullet expansion "
                "disabled for this chapter.",
                "DEBUG",
            )
        if (_inc_kp_lp and bullets and len(bullets) < _bp_lo_lp
                and not self._deadline_exceeded("dedicated bullet expansion")
                and not _skip_expansion):
            self.log(f"    ⚠️ Only {len(bullets)} bullets — requesting dedicated bullet expansion (full output budget)…", "INFO")
            _bp_raw = self._call_llm_with_empty_retry(
                self._build_dedicated_bullet_prompt(heading, text, exec_sum, bullets),
                model=self.primary_model, temperature=self.temperature,
                max_tokens=min(self.request.summarisation_max_output_tokens, 8192),
            )
            if _bp_raw:
                _bp_raw = self._strip_thinking(_bp_raw)
                _new_bullets = self._extract_bullets_from_text(_bp_raw)
                if _new_bullets and len(_new_bullets) > len(bullets):
                    _existing_lower = set(b.lower()[:60] for b in bullets)
                    # V18.20.3.2 (audit N1 / P0-2): BATCH-filter the expansion
                    # candidates in ONE call, then append the survivors. The
                    # V18.20.3.1 path filtered per-bullet (37 separate filter
                    # calls): the aggregate log line ("Filtered 1 thinking …
                    # kept 0") described only the LAST call, hiding that 36
                    # unfiltered candidates had sailed through — and two
                    # model SELF-TALK lines ("AuthorW (1968) - include this!
                    # Let me add it.") shipped to the final output because the
                    # start-anchored thinking patterns missed them (they start
                    # with an author-year token). One batch call = one honest
                    # aggregate log + the new mid-bullet self-talk patterns
                    # (SELF_TALK_PATTERNS) catch the planning-note class.
                    _candidates = [nb for nb in _new_bullets
                                   if nb.lower()[:60] not in _existing_lower]
                    _filtered = self._filter_thinking_bullets(
                        _candidates, concepts=None, source_text="",
                    )
                    _added = 0
                    for fb in _filtered:
                        if fb.lower()[:60] not in _existing_lower:
                            bullets.append(fb)
                            _existing_lower.add(fb.lower()[:60])
                            _added += 1
                    _dropped_exp = len(_candidates) - _added
                    if _dropped_exp > 0:
                        self.log(
                            f"    🎓 V18.20.3.2: Expansion filter dropped "
                            f"{_dropped_exp}/{len(_candidates)} candidate bullet(s) "
                            f"(thinking/prompt-leakage/self-talk) before merge",
                            "INFO",
                        )
                    if _added > 0:
                        self.log(f"    ✅ Bullet expansion: {len(bullets) - _added} → {len(bullets)} bullets (added {_added} new via dedicated call)", "INFO")
                        parsed["bullet_points"] = bullets

        # ── Final coverage check ─────────────────────────────────────────────
        # Sanitize bullets — ensure all items are strings (academic-rigor JSON
        # parsing can leave dicts in the list, which crashes str.join).
        bullets = [str(b) if not isinstance(b, str) else b for b in bullets if b]
        final_summary = f"{exec_sum} {' '.join(bullets)} {thorough}"
        coverage = self._compute_coverage(content, final_summary)

        # Adaptive coverage threshold — start at the
        # configured threshold (now 70%+ by default), but after 3 retries,
        # accept best-effort rather than looping forever.  change:
        # the floor is raised from 50% → 60%, and when best-effort is accepted
        # BELOW the 70% target, the warning explicitly says so (no silent
        # acceptance of low coverage).  This honours the "70% minimum" goal
        # while still terminating on hard books.
        if not hasattr(self, "_coverage_retry_counts"):
            self._coverage_retry_counts = {}
        chapter_retry_key = heading[:50]
        self._coverage_retry_counts[chapter_retry_key] = self._coverage_retry_counts.get(chapter_retry_key, 0) + 1
        retry_count = self._coverage_retry_counts[chapter_retry_key]

        effective_threshold = self.coverage_threshold
        if retry_count > 3:
            # floor at 60% (was 50%) — never silently accept below that.
            effective_threshold = max(0.60, self.coverage_threshold - 0.10)
            if coverage < 0.70:
                self.log(
                    f"    ⚠️ Coverage at {coverage:.0%} after {retry_count} retries — "
                    f"BELOW the 70% target. Accepting best-effort to avoid "
                    f"infinite retries, but this chapter needs manual review.",
                    "WARNING"
                )
            else:
                self.log(
                    f"    📉 Coverage at {coverage:.0%} after {retry_count} retries — "
                    f"accepting best effort (threshold {self.coverage_threshold:.0%})",
                    "WARNING"
                )

        if coverage < effective_threshold:
            self.log(f"    ⚠️ Final coverage {coverage:.0%} below {effective_threshold:.0%} threshold", "WARNING")
        else:
            self.log(f"    ✅ Final coverage {coverage:.0%}", "INFO")

        # ── Strip thinking from all final fields one more time ──────────────
        exec_sum = self._strip_thinking(exec_sum)
        bullets = [self._strip_thinking(bp) for bp in bullets]
        thorough = self._strip_thinking(thorough)
        thorough = self._strip_narrative_from_thorough(thorough)

        # V10.32.0 (Sprint 4 s2): Academic factual-claim verification
        # delegated to BulletPipeline. (extracted verbatim — see
        # BulletPipeline.apply_academic_factual_verification)
        _pstate.bullets = bullets
        _pstate.content = content
        _pipeline.apply_academic_factual_verification(_pstate)
        bullets = _pstate.bullets

        # V10.32.0 (Sprint 4 s2): Empty-output salvage delegated to BulletPipeline.
        # (extracted verbatim — see BulletPipeline.salvage_empty_output)
        # Returns True if the chapter should continue, False if it should fail.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        if not _pipeline.salvage_empty_output(_pstate):
            msg = "Summary is empty after all validation checks — marking as failed"
            self.log(f"    🚫 {msg}", "ERROR")
            return SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                bullet_points=[],
                thorough_summary=thorough,
                success=False,
                error_msg=msg,
                input_tokens=tok_in,
                output_tokens=count_tokens(final_summary),
            )
        bullets = _pstate.bullets
        exec_sum = _pstate.exec_sum
        thorough = _pstate.thorough

        # V10.32.0 (Sprint 4 s2): F1 length validation delegated to BulletPipeline.
        # (extracted verbatim — see BulletPipeline.apply_f1_length_validation)
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f1_length_validation(_pstate)
        exec_sum = _pstate.exec_sum
        thorough = _pstate.thorough

        # ── V10.31.0 (Sprint 4.1): F4 + Phase 2.2 stages delegated to
        # BulletPipeline.  The inline implementations were extracted verbatim
        # into ``core/summarisation/bullet_pipeline.py`` (BulletPipeline
        # .apply_f4_source_overlap + .apply_phase22_semantic_fact_check).
        # This is the first step of the Sprint 4 architecture refactor —
        # ``_summarize_inner`` will progressively delegate more stages until
        # it's a ≤100-line orchestrator (session 2 completes the extraction).
        # V13.6.0: _pipeline + _pstate already created above (before self-review).
        # Just refresh the state with current bullets/exec_sum/thorough.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f4_source_overlap(_pstate)
        _pipeline.apply_phase22_semantic_fact_check(_pstate)
        bullets = _pstate.bullets

        # ── V10.32.0 (Sprint 4 s2): F3 reading level + informational checks
        # extracted to BulletPipeline.  These are informational-only (log
        # but don't modify state, except F3 which may simplify thorough).
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.apply_f3_reading_level(_pstate)
        _pipeline.run_informational_checks(_pstate)
        thorough = _pstate.thorough

        # ── V10.32.0 (Sprint 4 s2): gap-fill extracted to BulletPipeline ─
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        _pipeline.gap_fill_concepts(_pstate, concepts)
        bullets = _pstate.bullets

        # V10.32.0 (Sprint 4 s2): F3 reading level, I2/J2/J3 informational
        # checks, and gap-fill are now delegated to BulletPipeline above.
        # The inline implementations were extracted verbatim — see
        # BulletPipeline.apply_f3_reading_level / .run_informational_checks
        # / .gap_fill_concepts.

        # V10.32.0 (Sprint 4 s2): Content Judge stage extracted to
        # BulletPipeline.run_content_judge().  This was the largest inline
        # block (~490 lines) — grounding checks, gap-fill reprompts, hard
        # rejection.  Returns None to continue, or a SummaryResult on hard reject.
        # V13.41.1: VRAM recovery + try/except wrapper. The content judge
        # runs langextract which loads a second model into VRAM — after B4 +
        # gap-fill, the GPU is exhausted and langextract can OOM-crash.
        _pstate.bullets = bullets
        _pstate.exec_sum = exec_sum
        _pstate.thorough = thorough
        self._recover_vram(context="pre-content-judge", delay_sec=15.0)
        try:
            _reject = _pipeline.run_content_judge(_pstate, coverage, tok_in, final_summary)
        except Exception as _e:
            self.log(f"    ⚠️ Content judge crashed (non-fatal): {_e}", "WARNING")
            logger.debug("content judge crashed: %s: %s", type(_e).__name__, _e)
            _reject = None  # skip the judge, continue with current bullets
        if _reject is not None:
            return _reject
        bullets = _pstate.bullets

        # ── V10.28.0 (Sprint 1.4): Recovery pass ──────────────────────────
        # After ALL drop sites have run, re-scan the quarantine and
        # resurrect any bullet whose source_overlap exceeds the recovery
        # threshold (default 0.30).  This catches bullets that were dropped
        # by a strict threshold (F4/Phase 2.2/Judge) but are actually
        # well-grounded paraphrases.  Resurrected bullets are re-inserted
        # into the live bullet list and marked ``recovered: true`` in
        # ``drops.jsonl``.
        #
        # In conservative mode this is a no-op: nothing was actually dropped
        # (only logged), so there is nothing to recover.  We still call it
        # for the audit log (it records "0 eligible" at DEBUG level).
        bullets = self._recover_quarantined(bullets, content)

        # V13.41.0: Scholar reflection — meta-cognitive gap analysis.
        # Runs AFTER all processing (B4, gap-fill, judge, recovery) when the
        # summary is in its final form. The LLM reviews its own output and
        # identifies chapter-specific gaps ("what did I miss?").
        # Update parsed with final values so the reflection sees the final summary.
        # V13.41.1: Wrapped in try/except to prevent ANY crash from killing
        # the conversion. The scholar reflection is optional — if it fails,
        # the summary is still complete without it.
        parsed["bullet_points"] = bullets
        parsed["executive_summary"] = exec_sum
        parsed["thorough_summary"] = thorough
        try:
            # V18.2 (audit Fix 2): Scholar's Reflections is now optional (default OFF).
            # The user's analysis showed this section was the #1 defect — it
            # contradicts itself by claiming content is "missing" that appears
            # elsewhere in the summary (caused by the truncation bug, now fixed).
            # The gap-fill mechanism still runs (it adds genuinely missing content
            # as new bullets), but the "what's missing" TEXT section is suppressed
            # by default. Enable via settings: summarisation.scholar_reflections_enabled
            from utils.settings import Settings as _Settings
            _scholar_enabled = _Settings().get("summarisation.scholar_reflections_enabled", False)
            # V18.2.22 (BUG-4): Skip scholar reflection if the chapter deadline
            # is already exceeded — it's optional and consumes an LLM call
            # (~2.5 min in the V18.2.20 conversion log).
            if not self._deadline_exceeded("scholar reflection"):
                if _scholar_enabled:
                    self._scholar_reflection(heading, content, parsed)
                else:
                    # Still run gap-fill (adds missing content), but skip the
                    # self-contradicting "reflections" text section.
                    self._scholar_reflection_gapfill_only(heading, content, parsed)
            else:
                self.log("    ⏭️  Scholar reflection skipped (deadline exceeded)", "INFO")
        except Exception as _e:
            self.log(f"    ⚠️ Scholar reflection crashed (non-fatal): {_e}", "WARNING")
            logger.debug("scholar reflection crashed: %s: %s", type(_e).__name__, _e)
            parsed["scholar_reflections"] = ""  # ensure empty, not None

        # V13.45.0: CRITICAL FIX — the scholar reflection's gap-fill bullets
        # were being LOST because SummaryResult used the local `bullets`
        # variable (the OLD list) instead of parsed["bullet_points"] (the NEW
        # list with gap-fill bullets appended). This bug has been present since
        # V13.42.0 and silently discarded every gap-fill bullet. Now we read
        # the updated bullets back from parsed.
        bullets = parsed.get("bullet_points", bullets) or bullets
        exec_sum = parsed.get("executive_summary", exec_sum) or exec_sum
        thorough = parsed.get("thorough_summary", thorough) or thorough

        # V13.45.0: Anti-false-precision post-check — scans the final summary
        # for "Author A views X while Author B views Y" patterns where the
        # source actually groups A and B together. Rewrites to preserve the
        # grouping. Deterministic, no LLM call.
        try:
            self._anti_false_precision_check(heading, content, parsed)
            # Re-read in case the check rewrote bullets/exec/thorough
            bullets = parsed.get("bullet_points", bullets) or bullets
            exec_sum = parsed.get("executive_summary", exec_sum) or exec_sum
            thorough = parsed.get("thorough_summary", thorough) or thorough
        except Exception as _e:
            self.log(f"    ⚠️ Anti-false-precision check crashed (non-fatal): {_e}", "WARNING")
            logger.debug("anti-false-precision crashed: %s: %s", type(_e).__name__, _e)

        # V18.2.22 (BUG-4): Skip semantic dedup if deadline exceeded — it's
        # optional and uses the embedder (which may be the broken one that
        # caused the 37-dropped-then-resurrected churn in V18.2.20).
        if self._deadline_exceeded("semantic dedup"):
            self.log("    ⏭️  Semantic dedup skipped (deadline exceeded)", "INFO")
        else:
            # V13.45.5: Semantic dedup pass — after scholar reflection adds gap-fill
            # bullets, there may be semantic duplicates (same concept, different
            # wording). Use embeddings to detect and remove them. This runs AFTER
            # all bullet-generation stages (B4, B3, gap-fill, scholar reflection)
            # to catch cross-stage redundancy that rapidfuzz missed.
            try:
                before_count = len(bullets)
                bullets = self._semantic_dedup_bullets(bullets)
                after_count = len(bullets)
                if before_count != after_count:
                    self.log(
                        f"    🧹 Semantic dedup: {before_count} → {after_count} bullets "
                        f"(removed {before_count - after_count} semantic duplicates)",
                        "INFO",
                    )
                    parsed["bullet_points"] = bullets
            except Exception as _e:
                self.log(f"    ⚠️ Semantic dedup crashed (non-fatal): {_e}", "WARNING")
                logger.debug("semantic dedup crashed: %s: %s", type(_e).__name__, _e)
        # V16.0.2: Normalization — its own try/except
        try:
            bullets = self._normalize_bullets(bullets)
            parsed["bullet_points"] = bullets
            self.log(f"    \U0001f9f9 V16.0.2 Bullet normalization: {len(bullets)} bullets normalized", "DEBUG")
        except Exception as _e:
            self.log(f"    \u26a0\ufe0f Bullet normalization crashed (non-fatal): {_e}", "WARNING")

        # V16.0.1: VRAM recovery BEFORE consolidation
        self._recover_vram(context="pre-bullet-consolidation", delay_sec=30.0)

        # V16.0.2: Bullet consolidation — its own try/except with timeout
        # V18.15: User rule: "Only consolidate bullets if you're 100% sure it
        # won't hurt coverage or accuracy. More bullets is better than lower
        # coverage/accuracy." Removed the min floor (10), the max cap (80),
        # and the post-consolidation warning — no min/max constraints on
        # bullet count. The LLM consolidation (merges 95%+ identical) is the
        # ONLY consolidation that runs. If it's skipped (deadline), ALL
        # bullets pass through unconsolidated — more bullets is better than
        # losing coverage.
        if self._deadline_exceeded("bullet consolidation"):
            self.log("    ⏭️  Bullet consolidation skipped (deadline exceeded)", "INFO")
        else:
            try:
                # V18.20.3.7 (RC-A): heading passed so the delegate can arm
                # the deterministic coverage assertion (reject any
                # consolidation that would lose a covered author; salvage
                # on truncated responses). See bullet_consolidation.py.
                bullets = self._consolidate_bullets(bullets, heading=heading)
                parsed["bullet_points"] = bullets
            except Exception as _e:
                self.log(f"    \u26a0\ufe0f Bullet consolidation crashed (non-fatal): {_e}", "WARNING")

        # V17.6: Deterministic judge — moved here from inside _gap_fill_concepts().
        # V17.5 had a bug: the V17.4 early-return from _gap_fill_concepts() skipped
        # PAST the judge block at the end of that method. Now the judge runs HERE,
        # AFTER all bullet-generation stages (B4, 3-Tier, self-review, content
        # judge, scholar reflection, consolidation) — the final coverage check.
        #
        # This is the BINDING check: if the deterministic analysis found 31 authors
        # and gemma only covered 28, the judge gap-fills the 3 missing ones.
        # Unlike the LLM content judge (which can be auto-passed), this check
        # is 100% reliable regex — it cannot be overridden.
        try:
            from core.preprocessing.deterministic_analyzer import (
                check_coverage,
                extract_authors_from_analysis,
                find_analysis_for_heading,
            )
            _seg_path, _analysis = find_analysis_for_heading(
                self.request.output_dir, heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
            if _analysis:
                _det_authors = extract_authors_from_analysis(_analysis)
                if _det_authors:
                    # V18.14: Check bullets ALONE and thorough ALONE as
                    # independent units. The old code checked the COMBINED
                    # exec+bullets+thorough text — so a theorist mentioned only
                    # in the thorough (but NOT in the bullets) was considered
                    # "covered." This is wrong: a user who only reads bullets
                    # must get 100% coverage. Compensating bullet gaps with the
                    # thorough summary is NOT accepted.
                    #
                    # Now we check:
                    # 1. Bullets-only coverage — if a theorist is missing from
                    #    the bullets, gap-fill them INTO the bullets.
                    # 2. Thorough-only coverage — if a theorist is missing from
                    #    the thorough, log a WARNING (the thorough is a
                    #    narrative, so we don't force gap-fill, but the user
                    #    is notified).
                    _bullets_only = ' '.join(bullets) if bullets else ''
                    _cov = check_coverage(_analysis, _bullets_only)
                    _missing = _cov["missing"]
                    _total = _cov["total"]
                    _pct = _cov["coverage_pct"]
                    self.log(
                        f"    📊 V18.14 Bullets-only judge: {_cov['covered']}/{_total} "
                        f"authors in bullets ({_pct:.0%})"
                        + (f" — MISSING from bullets: {_missing[:5]}" if _missing else " — ALL IN BULLETS ✅"),
                        "INFO"
                    )
                    # Also check thorough-only coverage (informational)
                    _thorough_only = thorough or exec_sum or ''
                    _cov_thorough = check_coverage(_analysis, _thorough_only)
                    _missing_thorough = _cov_thorough["missing"]
                    _pct_thorough = _cov_thorough["coverage_pct"]
                    self.log(
                        f"    📊 V18.14 Thorough-only judge: {_cov_thorough['covered']}/{_total} "
                        f"authors in thorough ({_pct_thorough:.0%})"
                        + (f" — MISSING from thorough: {_missing_thorough[:5]}" if _missing_thorough else " — ALL IN THOROUGH ✅"),
                        "INFO" if not _missing_thorough else "WARNING"
                    )
                    # If authors are missing from bullets, do targeted gap-fill.
                    # V18.14.1: Removed the len(_missing) <= 20 cap — the V18.14.0
                    # audit found that when 23 theorists were missing from bullets
                    # (23 > 20), the gap-fill SKIPPED entirely, leaving 74% of
                    # theorists missing from the bullets. Now the gap-fill runs
                    # regardless of how many are missing, processing 8 at a time
                    # in a loop until all are covered or the deadline is exceeded.
                    # V18.14.1: Added the loop — the old code processed only
                    # _missing[:8] in one LLM call, leaving 15+ theorists
                    # uncovered. Now it loops: 8 at a time, re-checking coverage
                    # after each batch, until all are covered or the deadline
                    # fires.
                    if _missing:
                        # V18.20.3.12 (Phase 4 / W6-O5 god-class decomposition):
                        # the ~478-line V18.14.1 batch gap-fill loop (rounds of
                        # 8 missing authors, re-checking coverage, the
                        # V18.20.3.4 veto/mention-only/give-up accounting, the
                        # V18.20.3.7 zero-yield escalation + telemetry) is
                        # extracted verbatim to
                        # ``gap_fill_batch.batch_gap_fill``. The loop's locals
                        # (``_total_added`` / ``_still_missing`` /
                        # ``_given_up`` / ``_gap_fill_round``) were never read
                        # after the block, so the outcome return value is
                        # ignored here (all reporting happens inside the loop,
                        # verbatim). The ``bullets`` list is mutated IN-PLACE
                        # (appended to) by the callee, exactly as the inline
                        # code did. The callables and the judge locals
                        # (``_analysis``, ``_det_authors``, ``check_coverage``)
                        # are passed as explicit parameters — the proven-safe
                        # pattern, NOT a context object. Byte-for-byte
                        # identical behaviour (characterization tests in
                        # ``tests/test_gap_fill_batch.py``).
                        gfb_batch_gap_fill(
                            heading, content, bullets, _missing, _analysis, _det_authors,
                            check_coverage=check_coverage,
                            call_fast_llm=self._call_fast_llm,
                            temperature=self.temperature,
                            strip_thinking=self._strip_thinking,
                            filter_thinking_bullets=self._filter_thinking_bullets,
                            log=self.log,
                        )

                    # V17.7: Inject ALL lists from the source as a dedicated
                    # "## Lists & Frameworks" section. V18.2.18 Improvement 3:
                    # This is now CONDITIONAL on a setting (default: off).
                    # The user's V18.2.15 analysis said "I'd remove this section
                    # entirely for a human-facing summary" because it duplicates
                    # info already in Key Takeaways. Power users who want the
                    # raw list extraction can enable it via
                    # `summarisation.inject_lists_section: true`.
                    try:
                        from utils.settings import Settings as _S
                        _inject_lists = _S().get("summarisation.inject_lists_section", False)
                    except Exception:
                        _inject_lists = False
                    if _inject_lists:
                        try:
                            from pathlib import Path as _P

                            from core.preprocessing.deterministic_analyzer import (
                                format_lists_section,
                            )
                            _seg_path_obj = _P(_seg_path) if _seg_path else None
                            if _seg_path_obj and _seg_path_obj.exists():
                                _seg_content = _seg_path_obj.read_text(encoding="utf-8")
                                _lists_section = format_lists_section(_seg_content)
                                if _lists_section:
                                    _list_count = _lists_section.count("### List ")
                                    thorough = (thorough or "") + "\n\n" + _lists_section
                                    self.log(f"    📝 V17.7: Injected Lists & Frameworks section ({_list_count} lists, all types) [inject_lists_section=true]", "INFO")
                        except Exception as _le:
                            self.log(f"    ⚠️ V17.7: Lists section injection failed: {_le}", "WARNING")
                    else:
                        self.log("    📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)", "DEBUG")
            else:
                self.log("    [V17.6] No analysis found for judge — skipping deterministic coverage check", "DEBUG")
        except Exception as _e:
            self.log(f"    ⚠️ V17.6: Deterministic judge failed: {_e}", "WARNING")

        # V18.15.9.0: Ensure the source's enumerated conclusions (e.g., the 7
        # characteristics of solid identity) appear as a DISTINCT bullet group.
        # The V18.15.8.0 audit found these were in the thorough summary but NOT
        # as distinct bullets (the gold standard V18.15.3.2 had them as distinct
        # bullets). This is a DETERMINISTIC guarantee (no LLM call) — runs AFTER
        # the deterministic judge + gap-fill (so gap-fill has a chance to add
        # them naturally first), but BEFORE postchecks (so the new bullets get
        # post-checked too).
        try:
            self._ensure_conclusion_bullets(heading, content, parsed)
            bullets = parsed.get("bullet_points", bullets) or bullets
        except Exception as _e:
            self.log(f"    ⚠️ V18.15.9.0: Conclusion-bullets check failed: {_e}", "WARNING")

        # V18.20.3.2 (audit N6 / P1-b): SECOND semantic-dedup pass AFTER all
        # bullet-generation stages. The first pass runs BEFORE the V17.6
        # deterministic judge + V18.14.1 batch gap-fill + conclusion bullets —
        # so bullets added by those stages were never deduped. The V18.20.3.1
        # run shipped a near-verbatim duplicate pair from gap-fill ("AuthorM
        # and AuthorN: Made significant contributions to the specific area of
        # gender identity consolidation" / "Meyer: Provided significant
        # contributions to the specific area of gender identity
        # consolidation"). The embedder is already loaded from the first pass
        # — this costs ~1s.
        # V18.20.3.4 (RC-2, audit v182033): this dedup is NO LONGER
        # deadline-skippable. The V18.20.3.3 run hit the chapter deadline
        # (2634s > 2400s) exactly here — "skipping optional phase:
        # post-gap-fill semantic dedup" — and shipped 6 duplicate bullets
        # (#17/#18/#26/#34/#35 + #25 duplicating #8/#15-16/#21/#23; audit
        # defect F8). The "optional" classification dates from when dedup
        # meant 4416 per-pair encode calls; since the EmbeddingCache batch
        # encode landed the whole pass costs ~1-2s ("46/46 claims… 2 batch
        # encode calls"), i.e. it is effectively free. It is also the ONLY
        # pass that runs AFTER the gap-fill rounds, so skipping it ships
        # every duplicate the gap-fill introduced. Keep the try/except
        # (an embedder OUTAGE must not kill the chapter) but never skip on
        # deadline.
        try:
            _before2 = len(bullets)
            _dedup_started = time.time()
            bullets = self._semantic_dedup_bullets(bullets)
            if len(bullets) != _before2:
                self.log(
                    f"    🧹 V18.20.3.2: Post-gap-fill semantic dedup: "
                    f"{_before2} → {len(bullets)} bullets (removed "
                    f"{_before2 - len(bullets)} gap-fill/conclusion duplicates; "
                    f"{time.time() - _dedup_started:.1f}s, non-skippable per "
                    f"V18.20.3.4)",
                    "INFO",
                )
                parsed["bullet_points"] = bullets
        except Exception as _e:
            self.log(f"    ⚠️ V18.20.3.2: Post-gap-fill semantic dedup crashed (non-fatal): {_e}", "WARNING")
            logger.debug("post-gap-fill dedup crashed: %s: %s", type(_e).__name__, _e)

        # V18.2.13: Deterministic post-checks — final sweep for the four
        # classes of garbled-token artifacts that low-bit quantization
        # (IQ2_XXS, 2.1 bits/param) introduces: name corruption ("Dukhaim"
        # vs "AuthorY"), missing spaces ("thesonic"→"the sonic"), prompt
        # leakage ("( provided in the input"), and implausible years.
        # Purely deterministic — zero LLM cost, ~1 ms/chapter. Runs AFTER
        # every bullet-generation stage (B4, B3, gap-fill, judge, lists) so
        # it catches artifacts introduced by ANY stage. See
        # core/summarisation/postchecks.py for the full design.
        try:
            from core.summarisation.postchecks import run_post_checks
            from utils.settings import Settings as _PcSettings
            _pc = run_post_checks(
                bullets=bullets,
                executive_summary=exec_sum,
                thorough_summary=thorough,
                source_text=content,
                key_distinctions=parsed.get("key_distinctions", "") or "",
                theoretical_tensions=parsed.get("theoretical_tensions", "") or "",
                # V0.03 (P0-1): dropped-letter auto-repair is OFF by default
                # (settings: summarisation.dropped_letter_auto_repair). The
                # V0.02 rig run corrupted 12/13 valid paraphrase words.
                auto_repair_garble=bool(
                    _PcSettings().get("summarisation.dropped_letter_auto_repair", False)
                ),
            )
            bullets = _pc.bullets
            exec_sum = _pc.executive_summary
            thorough = _pc.thorough_summary

            # ── V0.06 (rig audit F4-c — GENERAL RULE: the source-scaled
            # bullet budget is a HARD CAP, enforced at ship time) ─────────
            # The V0.05 length policy gated only the dedicated expansion
            # call; every other bullet-INSERTION engine (Tier-2 gap-fill,
            # Tier-3-adjacent scholar gap-fill, quarantine recovery) kept
            # appending freely — the rig shipped 19/18/15/14/12 bullets
            # against source-scaled targets of 5-7/5-7/6-9/6-9/5-8, with
            # the surplus being near-duplicate restatements of the same
            # claims. The cap is bullet_target(source).hi — the SAME single
            # source of truth every prompt uses. Primary-synthesis bullets
            # come first (they are the model's deliberate selection);
            # remediation bullets (appended later by gap-fill engines) are
            # the ones trimmed. Coverage shortfall below the cap is logged
            # honestly rather than padded away.
            if _inc_kp_lp and len(bullets) > _bp_hi_lp:
                self.log(
                    f"    ✂️ V0.06: bullet budget enforced at ship time — "
                    f"{len(bullets)} → {_bp_hi_lp} (target {_bp_lo_lp}-{_bp_hi_lp} "
                    f"for a {_src_words_lp}-word chapter; primary bullets kept, "
                    f"remediation bullets trimmed).",
                    "INFO",
                )
                bullets = list(bullets[:_bp_hi_lp])
                parsed["bullet_points"] = bullets

            # ── V0.06 (rig audit F7-a — GENERAL RULE: Tier-3 excerpts are
            # re-validated against the FINAL summary at ship time) ────────
            # Excerpts are recorded mid-pipeline for keywords the summary
            # "did not cover" — but later stages (scholar gap-fill, Tier-2)
            # can add bullets that cover the very same sentences, and
            # nothing re-checked the excerpt list. The rig shipped framed
            # excerpts duplicating bullets that paraphrased the identical
            # source sentence. An excerpt whose quoted sentence is already
            # covered by the final summary text is dropped; the excerpt
            # section keeps only genuinely-uncovered material.
            _se_pre = list(parsed.get("source_excerpts", []) or [])
            if _se_pre:
                _se_post = self._prune_covered_excerpts(
                    bullets=bullets,
                    exec_sum=exec_sum,
                    thorough=thorough,
                    excerpts=_se_pre,
                )
                if len(_se_post) != len(_se_pre):
                    self.log(
                        f"    🔖 V0.06: pruned {len(_se_pre) - len(_se_post)} "
                        f"source excerpt(s) whose sentence the FINAL summary "
                        f"already covers (kept {len(_se_post)}).",
                        "INFO",
                    )
                    parsed["source_excerpts"] = _se_post
            # V18.19.2.2 (Audit Fix 2): Re-populate thorough when run_post_checks
            # truncated it to empty (CoT narrative detected). The V18.19.2.0 audit
            # (audit/results/audit_V18.19.2.0_2026-08-28.md) found that the thorough
            # was 100% CoT, detect_cot_narrative correctly truncated it to empty
            # (postchecks.py:262), and the log said "caller falls back to exec_sum"
            # — but NOTHING actually repopulated thorough. The exec-from-thorough
            # fallback at line 3068 ran BEFORE run_post_checks, so it couldn't
            # catch this case. Result: the delivered summary had an EMPTY
            # "## Thorough Summary" section. This fix closes that gap: after
            # run_post_checks, if thorough is empty but exec is populated, copy
            # exec into thorough (the last-resort fallback the log message
            # promised). A short thorough (the exec) is strictly better than an
            # empty thorough — the reader gets at least the executive summary
            # content rather than a blank section.
            # V18.20.3.2 (audit N2+N3 / P0-1b): FINAL thorough re-derivation
            # from the FINAL bullet set — replaces the V18.19.2.2 exec-copy
            # fallback (which shipped a verbatim duplicate of the 191-word
            # exec as the "Thorough Summary", adding zero information). Now
            # the thorough is re-derived from exec + the FINAL bullets (all
            # generation stages complete: expansion, gap-fill, consolidation,
            # postcheck drops) — mirroring the V18.15.8.0 exec-derivation
            # pattern (derive the missing section from verified material the
            # model already produced). Fires when:
            #   (a) thorough is empty after postchecks (CoT-nuked or never
            #       produced), OR
            #   (b) the thorough came from the V18.2.44 SYNTHETIC fallback
            #       (exec + the EARLY bullet set only — the final set is
            #       strictly richer).
            # V0.05 (F9a): the re-derivation exists to repair a REQUESTED
            # thorough that was lost (CoT-nuked / synthetic). When the user
            # did not request a thorough summary, an empty one is CORRECT —
            # deriving one would fabricate the unrequested section again.
            _need_final_derive = _inc_thorough_lp and (
                (not thorough or not thorough.strip())
                or getattr(self, "_thorough_is_synthetic", False)
            )
            if _need_final_derive:
                _final_bullets_fd = [b for b in (parsed.get("bullet_points") or bullets or []) if b and b.strip()]
                _parts_fd = []
                if exec_sum and exec_sum.strip():
                    _parts_fd.append(exec_sum.strip())
                if _final_bullets_fd:
                    _parts_fd.append(" ".join(
                        f"\u2022 {b.strip()}." for b in _final_bullets_fd
                    ))
                if _parts_fd:
                    _derive_reason = (
                        "primary-call CoT was nuked at parse time"
                        if getattr(self, "_primary_thorough_cot_nuked", False)
                        else "dedicated thorough call fell back to the synthetic "
                             "synthesis (early bullets only)"
                    )
                    _derived_words = len(" ".join(_parts_fd).split())
                    thorough = "\n\n".join(_parts_fd)
                    self.log(
                        f"    📝 V18.20.3.2: Thorough re-derived from exec + FINAL "
                        f"bullet set ({_derived_words} words, "
                        f"{len(_final_bullets_fd)} bullets) — {_derive_reason}. "
                        f"This material is model-verified content, not a "
                        f"duplicated exec.",
                        "INFO",
                    )
            elif _inc_thorough_lp and not thorough and exec_sum and len(exec_sum.strip()) >= 50:
                # V18.19.2.2 legacy fallback — only when the CoT-nuke path
                # above did not apply (no primary CoT detected; e.g. a
                # postchecks CoT-nuke on a dedicated-call thorough).
                self.log(
                    f"    📝 V18.19.2.2: Thorough truncated to empty by CoT "
                    f"detection — falling back to exec summary ({len(exec_sum.split())} "
                    f"words) so the Thorough section is not blank.",
                    "INFO",
                )
                thorough = exec_sum
            # V18.20.3.2 (P0-1c): after any re-derivation, re-run the
            # V18.14 thorough-only coverage judge against the text that will
            # actually SHIP. The V18.20.3.1 run logged "29/34 authors in
            # thorough" — measured against 100% CoT that was nuked 33s later;
            # the shipped exec-copy covered ~19/34. The re-run makes the
            # logged verdict honest.
            try:
                if getattr(self, "_primary_thorough_cot_nuked", False) or getattr(
                    self, "_thorough_is_synthetic", False
                ):
                    from core.preprocessing.deterministic_analyzer import (
                        check_coverage,
                        extract_authors_from_analysis,
                        find_analysis_for_heading,
                    )
                    _seg_path_rr, _analysis_rr = find_analysis_for_heading(
                        self.request.output_dir, heading,
                        log_fn=lambda msg, level="DEBUG": self.log(msg, level),
                    )
                    if _analysis_rr:
                        _det_authors_rr = extract_authors_from_analysis(_analysis_rr)
                        if _det_authors_rr:
                            _cov_rr = check_coverage(
                                _analysis_rr, thorough or exec_sum or "",
                            )
                            self.log(
                                f"    📊 V18.20.3.2: Thorough-judge RE-RUN (post "
                                f"re-derivation): {_cov_rr['covered']}/{_cov_rr['total']} "
                                f"authors in the SHIPPED thorough "
                                f"({_cov_rr['coverage_pct']:.0%})"
                                + (f" — still missing: {_cov_rr['missing'][:5]}" if _cov_rr['missing'] else " ✅"),
                                "INFO" if not _cov_rr['missing'] else "WARNING",
                            )
            except Exception as _rr_e:
                logger.debug("thorough-judge re-run failed (non-fatal): %s: %s",
                             type(_rr_e).__name__, _rr_e)
                # V18.20.4.11 (P2 / W-a12): the re-run exists to make the
                # logged thorough-coverage verdict HONEST (V18.20.3.2 P0-1c);
                # a crashed re-run silently reverts to the dishonest verdict
                # the fix was built to remove. Keep the debug trace, ADD a
                # visible WARNING (honesty-machinery failures must be LOUD).
                self.log(
                    f"    ⚠️ V18.20.4.11: thorough-judge re-run failed (non-fatal — "
                    f"shipped-thorough coverage unverified for this chapter): "
                    f"{type(_rr_e).__name__}: {_rr_e}",
                    "WARNING",
                )
            # V18.19.2.2 (Audit Fix 2b): Same gap can hit exec — if run_post_checks
            # truncated exec to empty (CoT detected on exec, postchecks.py:208) but
            # thorough survived, fall back exec from thorough. Symmetric with the
            # above. (This case is rarer because the V18.15.8.0 exec-from-thorough
            # path + V18.16.0.1 CoT-check already guards exec before postchecks,
            # but run_post_checks can still truncate exec via detect_cot_narrative
            # if the CoT markers weren't caught by the pre-check. Defense-in-depth.)
            if not exec_sum and thorough and len(thorough.strip()) >= 50:
                self.log(
                    "    📝 V18.19.2.2: Exec truncated to empty by CoT "
                    "detection — falling back to thorough summary.",
                    "INFO",
                )
                exec_sum = thorough
            # V18.19.2.2 (Audit Fix 2c): If BOTH are empty after postchecks (the
            # catastrophic V18.15.7.0 cascade case), log at ERROR. The exec-from-
            # thorough + last-resort fallbacks above should prevent this, but if
            # both the primary AND dedicated calls produced CoT, we have nothing.
            # Surface it loudly rather than silently shipping empty sections.
            if not exec_sum and not thorough:
                self.log(
                    "    🚨 V18.19.2.2: BOTH exec and thorough are empty after "
                    "postchecks — the chapter will ship with blank summary sections. "
                    "This indicates the model produced CoT on every call (primary + "
                    "dedicated thorough + exec-from-thorough). Investigate the "
                    "model temperature / prompt / context window.",
                    "ERROR",
                )
            # V18.15.3.4: Use the cleaned additive sections too
            parsed["key_distinctions"] = _pc.key_distinctions
            parsed["theoretical_tensions"] = _pc.theoretical_tensions
            parsed["bullet_points"] = bullets
            parsed["executive_summary"] = exec_sum
            parsed["thorough_summary"] = thorough
            if _pc.total_findings:
                self.log(
                    f"    🛡️ V18.2.13 Post-checks: {_pc.fixed_count} fixed, "
                    f"{_pc.flagged_count} flagged "
                    f"(of {len(bullets)} bullets + exec + thorough)",
                    "INFO",
                )
                # Log each finding at DEBUG for the conversion log.
                for _iss in _pc.issues:
                    self.log(
                        f"      [{_iss.detector}/{_iss.severity}] {_iss.field}: "
                        f"{_iss.detail}  |  {_iss.snippet}",
                        "DEBUG",
                    )
            else:
                self.log("    ✅ V18.2.13 Post-checks: clean (no artifacts found)", "DEBUG")
        except Exception as _e:
            self.log(f"    ⚠️ V18.2.13 Post-checks crashed (non-fatal): {_e}", "WARNING")
            logger.debug("post-checks crashed: %s: %s", type(_e).__name__, _e)

        # V18.20.3.4 (RC-6, audit v182033): deterministic MUST-HAVE recall
        # floor, measured on the FINAL bullet set (post-quarantine,
        # post-dedup, post-postcheck drops). The V18.20.3.3 run's auto-judge
        # reported coverage=100% (46/46 claims) while the content audit
        # measured ~90% — claim-recall is not content-recall (the app itself
        # logged the caveat). This probe is the honest, hallucination-proof
        # complement: regex-measured (a) theorist recall from the
        # deterministic analysis (the V18.14 bullets-only judge pattern,
        # re-run on the final set) and (b) enumerated-conclusion item recall
        # (the V18.15.9.0 pattern). Zero LLM cost. Informational: prose-level
        # omissions (e.g. the AuthorJ ego-ideal gap in that audit) are invisible
        # to a deterministic probe — but the numbers it DOES print are real.
        #
        # V18.20.3.5 (audit v182034): the inline version of this probe NEVER
        # RAN on the rig — it iterated the conclusion tuples and called
        # .lower() on the TUPLE, raising AttributeError, which the except
        # clause swallowed via logger.debug (invisible in the conversion
        # log — the audit's "RC-6 not observable" finding). The logic now
        # lives in core/summarisation/recall_floor.py (unit-tested, stable
        # contract), failures log VISIBLY at WARNING, and the numbers are
        # stashed on the SummaryResult so the quality report and the
        # end-of-conversion diagnostic can print them instead of "?".
        # V18.20.3.8 (Phase 1 / W2): the 80-bullet cap now runs BEFORE the
        # recall-floor probe. Previously the probe measured the PRE-cap set
        # while the cap then deleted the list TAIL — exactly where gap-fill
        # and quarantine-recovery bullets are appended — so the logged
        # "honest number" could overstate the shipped set whenever the
        # count exceeded 80. The cap is also coverage-aware now: a tail
        # bullet that is the ONLY cover of an analysis author is rescued
        # into the capped set, displacing a redundant head bullet
        # ("more bullets is better than lower coverage" — the standing
        # rule, applied to the cap).
        _analysis_rf = ""
        try:
            from core.preprocessing.deterministic_analyzer import (
                find_analysis_for_heading,
            )
            _seg_path_rf, _analysis_rf = find_analysis_for_heading(
                self.request.output_dir, heading,
                log_fn=lambda msg, level="DEBUG": self.log(msg, level),
            )
        except Exception as _rf_e:
            # V18.20.3.5: a silent logger.debug here is how the .3.4 run
            # lost the probe entirely. Deterministic probes must fail
            # VISIBLY.
            self.log(
                f"    ⚠️ V18.20.3.5: Recall-floor analysis lookup failed: "
                f"{type(_rf_e).__name__}: {_rf_e}",
                "WARNING",
            )
            logger.debug("recall-floor analysis lookup failed: %s: %s",
                         type(_rf_e).__name__, _rf_e)

        # V18.15.7.0 (Fix 3): Hard-cap bullets at 80 (gold standard ≈ 46;
        # V18.15.6.0 shipped 212). Applied AFTER consolidation + gap-fill +
        # postchecks so consolidation can merge duplicates first, then the
        # cap catches overflow. The pre-V18.15.7.0 cap was 99999 (effectively
        # unlimited since V13.45.5) — this was a misinterpretation of the
        # "more bullets > lower coverage" rule (which was meant to prevent
        # MINIMUM caps, not MAXIMUM caps). A cap of 80 = 1.7× the gold
        # standard, allowing generous coverage while preventing the 212-bullet
        # explosion. The "more bullets > lower coverage" principle is preserved
        # — we never drop below the gold standard's 46; we only cap overflow.
        # V18.20.3.8: the cap delegates to coverage_aware_cap (same limit,
        # same head-cap behaviour when no analysis exists — plus the
        # sole-cover rescue).
        if bullets and len(bullets) > 80:
            try:
                from core.summarisation.recall_floor import coverage_aware_cap
                bullets = coverage_aware_cap(
                    bullets, _analysis_rf or "", limit=80,
                    log_fn=lambda msg, level="WARNING": self.log(msg, level),
                )
                parsed["bullet_points"] = bullets
            except Exception as _cap_e:
                # Never break the chapter over the cap: degrade to the
                # plain V18.15.7.0 head-cap, visibly.
                self.log(
                    f"    ⚠️ V18.20.3.8: coverage-aware cap failed "
                    f"({type(_cap_e).__name__}: {_cap_e}) — plain head-cap "
                    f"applied",
                    "WARNING",
                )
                logger.warning(
                    "coverage-aware cap failed — plain head-cap: %s: %s",
                    type(_cap_e).__name__, _cap_e,
                )
                bullets = bullets[:80]
                parsed["bullet_points"] = bullets

        # V18.20.3.13 (Phase 5 / W7+O3, .3.7 SWOT W7): thorough-theorist
        # FLOOR + one targeted gap-fill. Placement rationale: this is the
        # first point where the thorough is FINAL — every mutation is done
        # (dedicated expansion, postcheck repairs, the V18.20.3.2 re-derivation
        # from the final bullet set, the exec-copy fallbacks, Lists injection
        # which runs pre-postchecks) and the bullets are final too (cap
        # applied above) — so the floor measures the text that actually
        # ships. It runs BEFORE the recall-floor probe below so that probe's
        # conclusion-item measurement (bullets + thorough) sees the
        # post-gap-fill thorough. The theorist list comes from the SAME
        # runtime analysis lookup (``_analysis_rf``) the recall floor uses —
        # no second tree-walk, no hardcoded names (.3.9 rule). Fail-soft:
        # the method logs a WARNING and returns the thorough unchanged on
        # any internal crash.
        # V0.05 (F9a/F9b): skipped entirely when the user did not request a
        # thorough summary (nothing to measure/extend), and the gap-fill
        # append is budget-gated inside the mixin by the scaled target —
        # the 150-300-word append must never push a short chapter's thorough
        # past its source-scaled ceiling.
        if _inc_thorough_lp:
            thorough = self._thorough_theorist_floor(
                heading, content, thorough, _analysis_rf or "",
                scaled_target_hi=_th_hi_lp,
            )
        parsed["thorough_summary"] = thorough

        try:
            from core.summarisation.recall_floor import deterministic_recall_floor
            _rf = deterministic_recall_floor(
                _analysis_rf or "", bullets, thorough, content,
            )
            if _rf.get("log_parts"):
                self.log(
                    f"    📏 V18.20.3.4: Deterministic recall floor (final set): "
                    f"{'; '.join(_rf['log_parts'])}. This regex-measured floor is "
                    f"the honest coverage number — the LLM judge's claim-recall "
                    f"measures a different thing and overstates content recall "
                    f"for long sources.",
                    "INFO",
                )
            # V18.20.3.5: stash for the quality report / diagnostic summary.
            parsed["recall_floor"] = _rf
        except Exception as _rf_e:
            # V18.20.3.5: a silent logger.debug here is how the .3.4 run
            # lost the probe entirely. Deterministic probes must fail
            # VISIBLY.
            self.log(
                f"    ⚠️ V18.20.3.5: Deterministic recall-floor probe failed: "
                f"{type(_rf_e).__name__}: {_rf_e}",
                "WARNING",
            )
            logger.debug("recall-floor probe failed: %s: %s",
                         type(_rf_e).__name__, _rf_e)

        # ── V0.03 (P1-6): quarantine record for THIS chapter ───────────────
        # V0.06 (rig audit F2 — GENERAL RULE: pipeline bookkeeping never
        # ships in the deliverable): the per-drop record stays in the LOGS
        # (logs/drops.jsonl — the QuarantineLog has written every entry there
        # since V13.x) and the conversion log gets one honest count line.
        # The V0.05 rig rendered a "## Quarantine Log (quality-pipeline
        # drops)" section into every chapter's .md and DOCX — internal
        # quality-process metadata the user explicitly does not want in the
        # output ("keep it for your logs"). The appendix field is no longer
        # populated; the render sites were removed in the same release.
        try:
            _qa_entries = [
                e for e in (getattr(self.quarantine, "entries", None) or [])
                if getattr(e, "chapter", "") == heading and not getattr(e, "recovered", False)
            ]
            if _qa_entries:
                self.log(
                    f"    📋 Quarantine: {len(_qa_entries)} bullet drop(s) "
                    f"recorded for this chapter → logs/drops.jsonl "
                    f"(NOT rendered in the delivered files).",
                    "INFO",
                )
        except Exception as _qa_e:
            logger.debug("quarantine count log failed: %s: %s",
                         type(_qa_e).__name__, _qa_e)

        model_label = parsed.get("model", self.primary_model)
        return SummaryResult(
            chapter_heading=heading,
            executive_summary=exec_sum,
            bullet_points=bullets,
            # V0.06 (F1-b): the output-selection contract enforced at the
            # SOURCE — an unrequested section never enters the result, so
            # every renderer (markdown, DOCX, book summary) and every
            # consumer sees the contract state even before the render-side
            # flag gates (F1-c) run.
            thorough_summary=(thorough if _inc_thorough_lp else ""),
            success=True,
            model_used=model_label,
            input_tokens=tok_in,
            output_tokens=count_tokens(final_summary),
            # V13.40.1: Pass the additive sections through to SummaryResult
            # so they reach the DOCX + markdown output renderers.
            key_distinctions=parsed.get("key_distinctions", "") or "",
            theoretical_tensions=parsed.get("theoretical_tensions", "") or "",
            # V13.41.0: Scholar reflections — meta-cognitive gap analysis
            scholar_reflections=parsed.get("scholar_reflections", "") or "",
            # V0.03 (P0-2): Tier-3 framed source excerpts (separate section,
            # never Key Takeaways).
            source_excerpts=list(parsed.get("source_excerpts", []) or []),
            # V0.06 (F2): quarantine_appendix intentionally NOT set — the
            # drop record lives in logs/drops.jsonl only.
            # V18.20.3.5: deterministic recall-floor numbers for the
            # quality report + diagnostic summary (replaces the "?").
            recall_floor=parsed.get("recall_floor"),
            # V18.20.3.7: output provenance — which conversion produced
            # this summary (rendered into the summary files + sentinel).
            run_id=getattr(self, "_run_id", ""),
            app_version=getattr(self, "_app_version", ""),
            run_started=getattr(self, "_run_started", ""),
            # V0.06 (F1-c): stamp the output-selection flags onto the
            # result — renderers skip a section whose flag is False even if
            # content leaked into it (defense in depth behind the F1-b
            # parse gate).
            include_executive_summary=_inc_exec_lp,
            include_thorough_summary=_inc_thorough_lp,
            include_keypoints=_inc_kp_lp,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # V10.28.0 (Sprint 1.4): Quarantine recovery pass
    # ─────────────────────────────────────────────────────────────────────────

    def _recover_quarantined(
        self, bullets: list[str], source_text: str
    ) -> list[str]:
        """Re-scan the quarantine and resurrect high-overlap bullets.

        V18.15 (Phase 5 Stage 3, Batch 3.1): logic extracted verbatim to
        ``quarantine_recovery.recover_quarantined``. This method is a thin
        delegate. Byte-for-byte identical behaviour (characterization tests
        in ``tests/test_quarantine_recovery.py``).
        """
        return qr_recover_quarantined(
            bullets, source_text,
            quarantine=self.quarantine,
            log=self.log,
            # V0.06 (F4-b): the source-scaled bullet budget is a hard cap at
            # the recovery insertion site too.
            bullet_cap=_lp_bullet_cap_fn(source_text),
        )

    def _gap_fill_concepts(
        self,
        heading: str,
        content: str,
        bullets: list[str],
        concepts: list[str],
        exec_summary: str = "",
        thorough_summary: str = "",
    ) -> list[str]:
        """V3.2.0 C2: Detect uncovered concepts and make a targeted LLM call.

        V18.12 (Phase 5 Stage 3, Batch 2.7): logic extracted verbatim to
        ``gap_filler.gap_fill_concepts``. The 12 self-deps are passed as
        explicit kwargs (the proven-safe pattern — NOT a context object).
        The mutable ``self._last_coverage`` is set via a ``set_last_coverage``
        callback (preserves the original side-effect). Byte-for-byte identical
        behaviour (characterization tests in ``tests/test_gap_filler.py``).
        """
        return gf_gap_fill_concepts(
            heading, content, bullets, concepts, exec_summary, thorough_summary,
            output_dir=self.request.output_dir,
            temperature=self.temperature,
            effective_target=self._effective_target,
            overdeliver_enabled=self.overdeliver_enabled,
            overdeliver_target=self.overdeliver_target,
            coverage_threshold=self.coverage_threshold,
            prompt_manager=self.prompt_manager,
            recover_vram=self._recover_vram,
            call_fast_llm=self._call_fast_llm,
            strip_thinking=self._strip_thinking,
            switch_to_fast_model=self._switch_to_fast_model,
            set_last_coverage=lambda pct: setattr(self, "_last_coverage", pct),
            log=self.log,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Map‑Reduce with 4k chunks, 10% overlap, resumable from cache
    # ─────────────────────────────────────────────────────────────────────────

    def _map_reduce_summarize(self, heading: str, content: str) -> tuple[str | None, int]:
        """Map-Reduce summarization for very large chapters (40k+ tokens).

        V18.11 (Phase 5 Stage 3, Batch 2.1): logic extracted verbatim to
        ``map_reduce.map_reduce_summarize``. The two ``request`` reads
        (``input_path.stem`` for cache-key uniqueness,
        ``summarisation_cache_enabled`` for the V10.33.0 cache toggle)
        are passed as explicit primitives. The MAP_CHUNK_* / MAP_MINI_WORDS
        instance attrs are passed as params. Byte-for-byte identical output
        (characterization tests in ``tests/test_map_reduce.py``).

        V18.20.4.10 (P0-d): also passes a wall-clock budget for the map
        phase (``local.map_phase_max_seconds``, default 1800s). Derived
        from the per-chapter deadline when one is active, so the budget
        and the deadline agree: ``max(300, deadline - elapsed)``. 0
        disables the budget (old behaviour).
        """
        from utils.settings import Settings as _MrSettings
        _budget = int(_MrSettings().get("local.map_phase_max_seconds", 1800))
        if getattr(self, "local_chapter_deadline", 0) > 0:
            _remaining = self.local_chapter_deadline - (
                time.time() - getattr(self, "_chapter_deadline_start", time.time())
            )
            _budget = max(300, int(_remaining)) if _budget <= 0 else min(
                _budget, max(300, int(_remaining))
            )
        return mr_map_reduce_summarize(
            heading, content,
            primary_model=self.primary_model,
            cache_dir=self.cache_dir,
            input_path_stem=self.request.input_path.stem,
            cache_enabled=bool(getattr(self.request, "summarisation_cache_enabled", False)),
            temperature=self.temperature,
            map_chunk_tokens=self.MAP_CHUNK_TOKENS,
            map_chunk_overlap=self.MAP_CHUNK_OVERLAP,
            map_mini_words=self.MAP_MINI_WORDS,
            build_prompt=self._build_prompt,
            call_llm=self._call_llm,
            log=self.log,
            map_phase_budget_sec=_budget,
        )

    def _prepare_text(self, text: str) -> str:
        if self.provider == "freellmapi":
            max_tok = self.request.summarisation_max_context_tokens - self.request.summarisation_max_output_tokens - 700
        elif self.provider == "claude":
            max_tok = min(self.request.summarisation_max_context_tokens, 200000) - 2000  # Claude has 200k context
        elif self.provider in ("openrouter", "openai", "openai_compatible"):
            max_tok = self.cloud_max_tokens - 2000
        else:
            max_tok = self.request.summarisation_max_context_tokens - self.request.summarisation_max_output_tokens - 700
        if max_tok < 8000:
            max_tok = 8000
        if count_tokens(text) <= max_tok:
            return text
        return self._smart_truncate(text, max_tok)

    def _smart_truncate(self, text: str, max_tokens: int) -> str:
        """Paragraph-aware truncation: keep anchors + dense middle paragraphs.

        V18.11 (Phase 5 Stage 3, Batch 1.1): logic extracted verbatim to
        ``text_utils_ext.smart_truncate`` (pure function; the only ``self`` dep
        was a single ``self.log`` call, now passed as the ``log`` callback).
        This method is a thin delegate. Byte-for-byte identical output
        (characterization tests in ``tests/test_text_utils_ext.py``).
        """
        return tue_smart_truncate(text, max_tokens, log=self.log)

    # ── NEW: Parallel summarisation (Sprint 3) ──────────────────────────────

    def _distill_book_context(
        self,
        prev_context: str,
        chapter_exec_summary: str,
        chapter_heading: str,
    ) -> str:
        """V18.1 (audit Q2): Build a rolling cross-chapter context.

        After each chapter is summarized, this method distills the chapter's
        executive summary into a brief entry appended to the running context.
        The running context is capped at ~600 words (4 chapters × ~150 words)
        to keep the prompt size manageable. When the cap is exceeded, the
        oldest entries are truncated.

        This is a deterministic (non-LLM) distillation — we take the first
        ~150 words of the executive summary, prefixed with the chapter
        heading. This is fast (no extra LLM call) and sufficient for giving
        the next chapter's prompt awareness of what came before.

        For a more sophisticated synthesis (LLM-distilled), set
        ``summarisation.cross_chapter_context_mode = "llm"`` — this will
        make an extra LLM call to synthesize the context, at the cost of
        ~30s per chapter. Default is ``"deterministic"`` (fast, free).
        """
        if not chapter_exec_summary:
            return prev_context

        # Deterministic mode: take first ~150 words of the exec summary
        _words = chapter_exec_summary.split()
        _chapter_entry = f"[{chapter_heading}]: " + " ".join(_words[:150])
        if len(_words) > 150:
            _chapter_entry += "…"

        if prev_context:
            _new = prev_context + "\n\n" + _chapter_entry
        else:
            _new = _chapter_entry

        # Cap at ~600 words (trim oldest entries from the front)
        _all_words = _new.split()
        if len(_all_words) > 600:
            _new = "…[earlier context trimmed]… " + " ".join(_all_words[-600:])

        return _new

    def summarize_chapters(
        self,
        chapters: list[dict[str, str]],
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_event: Optional["threading.Event"] = None,
        thermal_pause_callback: Callable[[], None] | None = None,
        chapter_done_callback: Callable[..., None] | None = None,
    ) -> list[SummaryResult]:
        """
        Summarise multiple chapters in parallel using ThreadPoolExecutor.
        VRAM‑aware: if heavy_model is set, max_workers is forced to 1.

        P1-1: ``cancel_event`` is checked between chapters so cancel
        takes effect quickly, not after every chapter finishes.

        ``thermal_pause_callback`` is called between chapters.
        If the thermal safety controller has triggered a mandatory
        cool-down, this callback blocks until the cool-down is complete.
        Pass ``None`` to disable (no thermal pausing).

        V18.20.3.0: ``chapter_done_callback(idx, summary, chapter)`` is
        invoked IMMEDIATELY after each chapter's SummaryResult is
        produced (sequential and parallel paths). It is used by the
        incremental chapter-checkpoint saver to persist each chapter
        (summary .md + per-chapter .docx) the moment it completes, so a
        crash / power cut / user-cancel never loses completed chapters.
        Callback failures are logged at WARNING and NEVER propagate —
        checkpointing is strictly best-effort.
        """
        total = len(chapters)
        if total == 0:
            return []

        self.log(f"📚 Summarising {total} chapters with {self.max_workers} worker(s)...", "INFO")

        # If only one chapter or max_workers == 1, process sequentially
        if total == 1 or self.max_workers == 1:
            results = []
            # V18.1 (audit Q2): Cross-chapter running context.
            # After each chapter, distill its executive summary into a 150-word
            # rolling synthesis. Inject into the NEXT chapter's prompt for continuity.
            # Only applies in sequential mode (max_workers=1) — parallel mode
            # processes chapters out of order, so running context doesn't apply.
            _running_book_context = ""
            # V18.1 (audit Q2): Read cross-chapter context setting (Settings is a singleton)
            from utils.settings import Settings as _Settings
            _cross_chapter_enabled = _Settings().get("summarisation.cross_chapter_context", True)
            for idx, chap in enumerate(chapters, 1):
                # check cancel between chapters
                if cancel_event and cancel_event.is_set():
                    self.log("  ⏹️ Summarisation cancelled by user — stopping.", "WARNING")
                    break
                # check thermal pause — blocks if cool-down in progress
                if thermal_pause_callback:
                    thermal_pause_callback()
                if progress_callback:
                    progress_callback(idx / total, f"Chapter {idx}/{total} – processing")
                self.log(f"📚 Chapter {idx}/{total}: {chap['heading'][:55]}…", "INFO")
                # V18.2.15 (P4): Per-chapter wall-clock deadline. Record the
                # start time so we can detect a stuck generation AFTER the
                # call returns (the in-flight Ollama call has its own HTTP
                # timeout; this catches the case where the call technically
                # returned but took far too long, indicating a model stall).
                _chap_start = time.time()
                # V18.2.22 (BUG-4): also set the instance field so
                # _summarize_inner can check it at phase boundaries and
                # short-circuit optional phases (scholar reflection, dedup,
                # consolidation) when the deadline is already exceeded.
                self._chapter_deadline_start = _chap_start
                # V18.2.25 (Phase 4.1): tracing span for the chapter root.
                # No-op when tracing disabled (span() yields None internally).
                from core.obs.tracing import span as _otel_span
                with _otel_span(
                    "chapter.summarize",
                    chapter_idx=idx,
                    chapter_total=total,
                    chapter_heading=chap["heading"][:100],
                    model=getattr(self, "primary_model", ""),
                ):
                    try:
                        _result = self._summarize_inner(
                            chap["heading"], chap["content"],
                            concepts=chap.get("concepts"),
                            callouts=chap.get("callouts"),
                            book_context=_running_book_context,
                        )
                    except Exception as e:
                        # V18.20.2.0 (SWOT A7): mirror the parallel path's
                        # per-chapter handler (process_chapter below) exactly —
                        # log the crash at ERROR and record a failed
                        # SummaryResult instead of letting ONE chapter's
                        # unexpected crash kill the whole sequential run
                        # (the ONLY mode on the target machine, max_workers=1).
                        # The loop's existing FAILED branch below logs the
                        # final ❌ line, same as the as_completed loop does
                        # for the parallel path.
                        self.log(f"  ❌ Chapter {idx} failed: {e}", "ERROR")
                        logger.exception(
                            "Chapter %d/%d crashed in sequential loop (heading='%s')",
                            idx, total, chap["heading"][:60],
                        )
                        _result = SummaryResult(
                            chapter_heading=chap["heading"],
                            executive_summary="",
                            bullet_points=[],
                            thorough_summary="",
                            success=False,
                            error_msg=str(e),
                        )
                _chap_elapsed = time.time() - _chap_start
                # V18.2.15 (P4): Deadline check — log a traceable WARNING if
                # the chapter exceeded the budget. We DON'T hard-fail the
                # chapter (it may have produced a valid summary, just slowly),
                # but the WARNING leaves a permanent trace for diagnosis.
                # If the chapter also FAILED, the elapsed time helps explain
                # whether it was a stall (long) or a parse error (short).
                if self.is_local and self.local_chapter_deadline > 0 and _chap_elapsed > self.local_chapter_deadline:
                    self.log(
                        f"  ⏱️⚠️ V18.2.15 Chapter {idx}/{total} exceeded deadline: "
                        f"{_chap_elapsed:.0f}s > {self.local_chapter_deadline}s "
                        f"(heading='{chap['heading'][:40]}') — possible model stall. "
                        f"Summary {'kept' if _result.success else 'failed'}, but "
                        f"this chapter consumed {_chap_elapsed:.0f}s of the budget.",
                        "WARNING",
                    )
                    logger.warning(
                        "Chapter %d/%d exceeded deadline: %.0fs > %ds (heading='%s')",
                        idx, total, _chap_elapsed, self.local_chapter_deadline,
                        chap["heading"][:60],
                    )
                else:
                    # V18.2.15 (P4): Always log the per-chapter elapsed time
                    # at DEBUG so the conversion log has a full timing trace
                    # for post-mortem diagnosis (even when under budget).
                    self.log(
                        f"  ⏱️ Chapter {idx}/{total} took {_chap_elapsed:.0f}s "
                        f"(deadline {self.local_chapter_deadline}s)",
                        "DEBUG",
                    )
                if _result.success:
                    self.log(f"✅ Chapter {idx}/{total}: {chap['heading'][:40]}… complete", "INFO")
                    # V10.16.0 (C1): Progressive output preview — show partial
                    # summary stats as each chapter finishes, so the user sees
                    # progress during the long summarization phase.
                    _bp_count = len(_result.bullet_points) if _result.bullet_points else 0
                    _exec_len = len(_result.executive_summary) if _result.executive_summary else 0
                    # V18.20.4.12 (W-b15): structured progress line — the
                    # wizard's live quality dashboard parses this JSON-first
                    # (core/common/progress_events.py); the human line below
                    # stays byte-identical as the old-log fallback source.
                    self.log(
                        progress_json_line(idx, total, _bp_count, _exec_len),
                        "DEBUG",
                    )
                    self.log(
                        f"  📊 Progress: {idx}/{total} done | "
                        f"{_bp_count} bullets | {_exec_len:,} chars exec summary",
                        "DEBUG",
                    )
                    # V18.1 (audit Q2): Update running context for the next chapter.
                    # Distill this chapter's executive summary into ~150 words.
                    if _cross_chapter_enabled and _result.executive_summary:
                        _running_book_context = self._distill_book_context(
                            _running_book_context, _result.executive_summary, chap["heading"]
                        )
                else:
                    self.log(f"❌ Chapter {idx}/{total}: {chap['heading'][:40]}… FAILED: {_result.error_msg}", "ERROR")
                results.append(_result)
                # V18.20.3.0: incremental checkpoint — fire the moment the
                # chapter's result exists (BEFORE the next chapter starts),
                # so a crash never loses a completed chapter.
                if chapter_done_callback is not None:
                    try:
                        chapter_done_callback(idx, _result, chap)
                    except Exception as _cb_e:
                        self.log(
                            f"  ⚠️ V18.20.3.0 chapter checkpoint callback "
                            f"failed (chapter {idx}): {_cb_e!r} — continuing.",
                            "WARNING",
                        )
            return results

        # Parallel processing
        results: list[SummaryResult | None] = [None] * total
        completed = 0

        def process_chapter(idx: int, chap: dict[str, str]) -> tuple[int, SummaryResult]:
            """Wrapper to process a single chapter and return its index."""
            # V18.20.4.11 (P2 / W-a1): stamp the per-chapter deadline start ON
            # THE WORKER THREAD. The V18.20.2.0 (SWOT A8) fix set it on the
            # MAIN thread immediately before each executor.submit against a
            # SHARED attribute, so concurrent workers all measured from the
            # MOST RECENT submission (under-approximation — the old comment
            # there already deferred "a per-worker thread-local is the full
            # fix"). Now that _chapter_deadline_start is a thread-local
            # property shim, each worker stamps its own start at pickup:
            # EXACT per-chapter elapsed time, and the watchdog stays ENABLED
            # (a main-thread-only write would leave workers seeing the None
            # default = deadline silently disabled — a regression, not a fix).
            self._chapter_deadline_start = time.time()
            try:
                result = self._summarize_inner(
                    chap["heading"], chap["content"],
                    concepts=chap.get("concepts"),
                    callouts=chap.get("callouts"),
                )
                return idx, result
            except Exception as e:
                self.log(f"  ❌ Chapter {idx+1} failed: {e}", "ERROR")
                return idx, SummaryResult(
                    chapter_heading=chap["heading"],
                    executive_summary="",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg=str(e),
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, chap in enumerate(chapters):
                # V18.20.2.0 (SWOT A8): per-chapter deadline start — now
                # stamped INSIDE process_chapter on the worker thread itself
                # (V18.20.4.11 / W-a1 thread-local fix; see the comment
                # there for why a pre-submit main-thread write no longer
                # works now that the attribute is thread-local).
                futures[executor.submit(process_chapter, i, chap)] = i

            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed += 1
                if progress_callback:
                    progress_callback(completed / total, f"Chapter {idx+1}/{total} – complete")
                # log FAILED vs SUCCESS correctly — was always
                # logging "✅ complete" even when the chapter failed, which
                # was misleading (the user saw green checkmarks for failed chapters).
                if result.success:
                    self.log(f"✅ Chapter {idx+1}/{total}: {result.chapter_heading[:40]}… complete", "INFO")
                else:
                    self.log(f"❌ Chapter {idx+1}/{total}: {result.chapter_heading[:40]}… FAILED: {result.error_msg}", "ERROR")
                # V18.20.3.0: incremental checkpoint — fire as each parallel
                # future completes (chapters[idx] carries the chapter dict).
                if chapter_done_callback is not None:
                    try:
                        chapter_done_callback(idx + 1, result, chapters[idx])
                    except Exception as _cb_e:
                        self.log(
                            f"  ⚠️ V18.20.3.0 chapter checkpoint callback "
                            f"failed (chapter {idx+1}): {_cb_e!r} — continuing.",
                            "WARNING",
                        )
                # check cancel — cancel remaining futures
                if cancel_event and cancel_event.is_set():
                    self.log("  ⏹️ Summarisation cancelled by user — stopping pending chapters.", "WARNING")
                    for f in futures:
                        f.cancel()
                    break

        # Ensure all results are SummaryResult (not None)
        final_results = []
        for i, r in enumerate(results):
            if r is None:
                # Fallback for any missing results
                self.log(f"  ⚠️ Chapter {i+1} returned None – creating error placeholder.", "WARNING")
                final_results.append(SummaryResult(
                    chapter_heading=chapters[i]["heading"],
                    executive_summary="[Error: No result]",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg="No result returned from summarisation",
                ))
            else:
                final_results.append(r)

        return final_results

    def build_book_summary(self, summaries: list[SummaryResult], book_title: str,
                           stats: dict | None = None) -> str:
        """V0.03 (P1-6): optional ``stats`` out-param receives the ACTUAL
        aggregated numbers ("bullets" = the deduped cross-chapter count,
        "chapters" = chapter count) so the caller's provenance stamp stops
        labelling chapter count as bullet count (the V0.02 rig stamped
        ``bullets=2`` on a file containing 70).

        V0.06 (rig audit F3 — GENERAL RULE: a deliverable never lists the
        same content block twice): the V0.05 book file opened with
        "## 📌 All Key Takeaways" (a concatenation of EVERY chapter's
        bullets) followed by "## 📖 Chapter-by-Chapter …" which repeated
        each chapter's FULL bullet list again — every takeaway shipped
        twice in one file. The aggregate view already exists as its own
        deliverable (keypoints/*.Keypoints.md, classified core/supporting/
        additional), so the book summary keeps the structured per-chapter
        view ONLY. Section content additionally honors the per-chapter
        output-selection flags (F1-c).
        """
        lines = [f"# Book Summary: {book_title}", "", f"> Provider: {self.provider} | Language: {self.language} | Chapters: {len(summaries)} | {time.strftime('%Y-%m-%d')}", "", "---", ""]
        seen = set()
        all_bullets = []
        for s in summaries:
            for bp in s.bullet_points:
                norm = re.sub(r"[^\w\s]", "", bp.lower()).strip()
                if norm and norm not in seen and len(bp) > 10:
                    seen.add(norm); all_bullets.append(bp)
        if stats is not None:
            try:
                stats["bullets"] = len(all_bullets)
                stats["chapters"] = len(summaries)
            except Exception:
                pass  # stats must never break the book summary build
        # V0.06 (F3): the global "All Key Takeaways" concatenation is
        # DELIBERATELY ABSENT — each chapter's takeaways appear exactly
        # once, under their own chapter heading below. The aggregate
        # takeaway view is the keypoints deliverable.
        lines += ["## 📖 Chapter-by-Chapter Executive Summaries", ""]
        for idx, s in enumerate(summaries, 1):
            if not s.success:
                lines += [f"### {idx}. {s.chapter_heading}", "",
                          f"⚠️ Summary failed: {s.error_msg or 'unknown error'}", ""]
                continue
            _inc_exec_s = getattr(s, "include_executive_summary", True)
            _inc_kp_s = getattr(s, "include_keypoints", True)
            _inc_th_s = getattr(s, "include_thorough_summary", True)
            if _inc_exec_s and (s.executive_summary or "").strip():
                lines += [f"### {idx}. {s.chapter_heading}", "",
                          s.executive_summary.strip(), ""]
            else:
                lines += [f"### {idx}. {s.chapter_heading}", ""]
            if _inc_kp_s and s.bullet_points:
                lines.append("**Key takeaways:**")
                for bp in s.bullet_points:
                    bp_str = str(bp) if not isinstance(bp, str) else bp
                    lines.append(f"- {bp_str}")
                lines.append("")
            if _inc_th_s and s.thorough_summary and s.thorough_summary.strip():
                lines += ["<details><summary>Detailed summary</summary>", "", s.thorough_summary, "", "</details>", ""]
        return "\n".join(lines)
