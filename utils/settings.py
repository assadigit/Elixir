"""
Settings management with JSON persistence, nested dot-notation access, and defaults.

NEW in this version (Sprint 3):
  - Added extract_figure_text: bool = False under advanced.
  - Added vision_model_for_figures: str = "OlmOCR-2-7B:latest" under advanced.
  - Added max_workers: int = 2 under summarisation (for parallel processing).
  - VRAM-aware defaults: if heavy_model is set, max_workers will be capped at 1
    (enforced in summarizer, but setting stored here).
"""

import copy
import json
import logging
import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from utils.atomic_io import atomic_write_json
from utils.settings_schema import (
    resolve_env_vars_with_warnings,
    validate_setting_path,
    validate_settings,
    validate_types,
)

logger = logging.getLogger(__name__)


# ── V18.20.4.11 (rebrand): user-data directory + one-time migration ─────────
# The app was renamed Elixir → Elixir; the user-data directory moved
# ~/.elixir → ~/.elixir. user_data_dir() is the SINGLE choke point:
# on first call it migrates the legacy directory (shutil.move — instant on
# the same filesystem) so settings, cached models, prompts, and secrets all
# survive the rebrand. Idempotent, thread-safe, and NEVER raises (a failed
# migration logs a WARNING and the app starts with fresh settings — the
# legacy directory is left untouched, so nothing is lost).
_USER_DIR_NAME = ".elixir"
_LEGACY_USER_DIR_NAME = ".markitdown_pro"  # pre-rebrand name — migration source (do NOT rename)
_user_dir_lock = threading.Lock()
_user_dir_resolved = False


def user_data_dir() -> Path:
    """Return the app's user-data directory (~/.elixir), migrating the
    legacy ~/.elixir on first call (V18.20.4.11 rebrand)."""
    global _user_dir_resolved
    new_dir = Path.home() / _USER_DIR_NAME
    if _user_dir_resolved:
        return new_dir
    with _user_dir_lock:
        if _user_dir_resolved:
            return new_dir
        legacy = Path.home() / _LEGACY_USER_DIR_NAME
        try:
            if not new_dir.exists() and legacy.exists():
                shutil.move(str(legacy), str(new_dir))
                logger.info(
                    "Elixir rebrand: migrated user data %s → %s (settings, "
                    "models, caches, prompts preserved)",
                    legacy,
                    new_dir,
                )
        except Exception:
            logger.warning(
                "Elixir rebrand: user-data migration %s → %s failed — "
                "starting fresh (legacy directory left untouched)",
                legacy,
                new_dir,
                exc_info=True,
            )
        _user_dir_resolved = True
    return new_dir


class Settings:
    _instance: Optional["Settings"] = None
    _settings_dir: Path = user_data_dir()
    _settings_file: Path = _settings_dir / "settings.json"
    # DI hook: tests can set this to a mock Settings instance.
    _test_override: Optional["Settings"] = None

    def __new__(cls) -> "Settings":
        if cls._test_override is not None:
            return cls._test_override
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # V9.0.0: thread-safe settings access
        self._data: dict[str, Any] = self._load()
        # V18.20.4.12 (W-c19): batch()-mode bookkeeping — nesting depth of
        # batch() contexts and whether any set() write is deferred. See
        # batch(). (batch()/set() also getattr-guard these defensively for
        # instances built without this __init__.)
        self._batch_depth: int = 0
        self._batch_dirty: bool = False

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "ocr": {
                "primary_model": "OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest",
                "fallback_model": "OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest",
                "vlm_fallback_model": "",  # V10.35.0: local VLM for OCR fallback (e.g. "llava:13b")
                "use_llm": True,
                "auto_detect_scanned": True,
                "force_ocr_all_pages": False,
                "image_max_size": 1200,
                "image_dpi": 300,
                "unlimited_ocr_path": "",
                "deepseek_ocr2_path": "",
                "timeout": 120,
                "retries": 2,
                "use_paddleocr": False,
            },
            "postprocess": {
                "clean_markdown": True,
                "fix_missing_spaces": False,
                "token_saver": True,
                "remove_page_number_headings": True,
                "convert_separators_to_comments": False,
            },
            "segmentation": {
                "strategy": "auto",
                "custom_keywords": ["فصل", "بخش", "قانون", "درس", "باب"],
                "custom_regex_patterns": [],
                "page_group_size": 10,
                "token_limit": 2000,
                "enable_semantic": True,
                "chunk_by_page_groups": True,
            },
            # ── V13.27.0 (P2.6): Canonical LLM settings ──────────────────────
            # The single source of truth for Ollama URL + provider. All modules
            # should read from ``llm.ollama_url`` (canonical) instead of the
            # legacy keys (ocr.ollama_url, summarisation.ollama_url,
            # summarisation.endpoint, translation.endpoint). The legacy keys
            # are kept for backward compat but resolve to this value.
            "llm": {
                "ollama_url": "http://localhost:11434",
                "provider": "ollama",  # "ollama" | "cloud"
                # V18.1 (audit): How long Ollama keeps a model resident in VRAM
                # after the last request. Default "30m" (30 minutes). The old
                # code had no keep_alive, so Ollama used its 5-minute default —
                # models cold-reloaded between chapters if the user waited >5 min.
                # Set to "0" to unload immediately, or "-1" to keep forever.
                "keep_alive": "30m",
                # V13.34.0: Per-model sampling profiles.
                "model_profiles": {
                    "gemma4-12b:latest": {
                        "temperature": 1.0,
                        "top_p": 0.95,
                        "top_k": 64,
                    },
                    "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest": {
                        "temperature": 0.6,
                    },
                    "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest": {
                        "temperature": 0.6,
                    },
                    # V18.2.2: Qwen3.8 Instruct profiles.
                    # Qwen3 Instruct models are optimized for temp 0.6-0.7 — the
                    # app's default of 1.0 (Gemma 4 legacy) causes hallucination
                    # and rambling on Qwen. These profiles override the default
                    # when the model name matches.
                    # V18.2.7: Reverted IQ2_XXS temp back to 0.7 — the user
                    # confirmed it works at 0.7 (the earlier empty responses
                    # were caused by Academic Rigor complex prompt + the
                    # use-before-assignment crash, NOT temperature).
                    "Qwen3.8-27B-UD-IQ2_XXS_Unsloth-instruct:latest": {
                        "temperature": 0.7,
                        "top_p": 0.80,
                        "top_k": 20,
                    },
                    "Qwen3.8-27B-UD-IQ2_XXS_Unsloth-instruct": {
                        "temperature": 0.7,
                        "top_p": 0.80,
                        "top_k": 20,
                    },
                    # V18.2.3: IQ2_M uses temp 0.7 (the standard Qwen instruct temp)
                    "Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest": {
                        "temperature": 0.7,
                        "top_p": 0.80,
                        "top_k": 20,
                    },
                    "Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct": {
                        "temperature": 0.7,
                        "top_p": 0.80,
                        "top_k": 20,
                    },
                },
            },
            "summarisation": {
                "enabled": False,
                "model": "gemma4-12b:latest",  # V13.45.4: primary summarization model (was wrong Qwythos variant)
                "language": "auto",
                "max_context_tokens": 32768,  # V13.34.0: 32k for local models (cloud uses 128k+)
                # V18.2 (audit): For 12 GB cards running a 27B model, the KV
                # cache at 32k context uses ~2 GB VRAM. If the model is CPU-
                # offloading (VRAM > 11 GB), reducing this to 16384 frees ~1 GB
                # and may eliminate CPU offloading entirely. Most chapters are
                # under 10k tokens, so 16k context is plenty. Set to 8192 for
                # extreme VRAM pressure (short chapters only).
                "adaptive_context_enabled": True,  # auto-reduce context for short chapters
                "max_output_tokens": 16000,  # V13.45.4: raised from 8192 (user has 32K context, 8K was too low for 100+ bullets)
                "cache_enabled": False,
                "include_book_summary": True,
                # V0.04: fresh installs default to the llama.cpp backend
                # (the rig's primary). Existing installs are migrated in
                # _load() — and only when still at the untouched "ollama"
                # default, so explicit choices survive.
                "provider": "llamacpp",
                "api_key": "",
                "api_base_url": "https://openrouter.ai/api/v1",
                "cloud_model": "google/gemini-2.5-flash-preview:free",
                "cloud_max_tokens": 16000,
                # ── Claude (Anthropic) settings ──────────────────────────
                "claude_api_key": "",
                "claude_model": "claude-3-5-sonnet-20241022",
                "claude_base_url": "https://api.anthropic.com/v1",
                "claude_max_tokens": 4096,
                # ── FreeLLMAPI ─────────────────────────────────────────────
                "freellmapi_url": "http://localhost:3001/v1",
                "freellmapi_key": "",
                "freellmapi_model": "auto",
                # ── llama.cpp server (llama-server) — V0.04 ────────────────
                # The first non-Ollama LOCAL backend, wired end-to-end
                # (provider + wizard + settings dialog). Defaults match the
                # rig: llama-server on 127.0.0.1:8080 with the
                # Ternary-Bonsai-2-27B-Instruct-Vision model, 65k context
                # (65536) and 12k output (12288). ``llamacpp_api_key`` is
                # sent as a Bearer token — llama.cpp only enforces it when
                # started with --api-key, otherwise the header is ignored.
                "llamacpp_base_url": "http://127.0.0.1:8080/v1",
                "llamacpp_api_key": "local",
                "llamacpp_model": "Ternary-Bonsai-2-27B-Instruct-Vision",
                "llamacpp_context_tokens": 65536,  # the 65k window
                "llamacpp_max_output_tokens": 12288,  # the 12k output cap
                # One-time activation flag for the V0.04 migration (see
                # _load). After the first run the flag stays True so a user
                # who later switches BACK to Ollama is never re-flipped.
                "llamacpp_activation_done": False,
                # ── Quality controls ──────────────────────────────────────
                # V10.1.7: default temperature raised 0.2 → 0.6 per user request.
                # 0.6 works better with Qwythos/Qwen models (0.2 produced empty output).
                "temperature": 1.0,  # V13.34.0: Gemma 4 recommended temp
                "self_consistency": False,
                "heavy_model": "",
                # V18.20.2.0 (SWOT A28): duplicate ``fast_model`` key removed.
                # The dict literal used to declare it twice — first
                # "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest", then "" —
                # and by dict-literal semantics the LAST occurrence silently
                # won, so the effective default has been "" all along.  The
                # single remaining declaration below preserves that behavior
                # (and removes the Qwythos name that 404s on other installs).
                # ── V16.0.9: 4-mode model architecture ──────────────────────
                # "single_local" — one LOCAL model does everything (default)
                # "dual_local"   — local heavy + local fast model (both Ollama)
                # "single_api"   — one CLOUD API model does everything
                # "dual_api"     — fast cheap cloud API + expensive accurate cloud API
                # Legacy "single" accepted (mapped → "single_local").
                "model_architecture": "single_local",
                "fast_model": "",  # V17.0.0: fast/small model for simple tasks
                "fast_model_temperature": 0.1,  # V17.0.0: LFM2.5 recommends 0.1
                "fast_model_context": 131072,  # V17.0.0: LFM2.5 max 128K context
                "fast_api_url": "",  # V17.0.0: API URL for dual_api mode
                "fast_api_key": "",  # V17.0.0: API key for dual_api mode
                "fast_api_model": "",  # V17.0.0: Model name for dual_api mode
                "coverage_threshold": 85,  # V13.34.0: raised from 50 to 85
                # V15.1.0: Over-delivery — keep improving coverage past the minimum
                # threshold toward the target. Default ON, target 92%.
                "overdeliver_enabled": True,
                "overdeliver_target": 100,  # V15.1.1: 100% (the more the better)
                "b3_voting_enabled": False,  # V15.1.1: disabled (damages depth); toggleable
                # V18.1 (audit Q2): Cross-chapter running context. When enabled,
                # each chapter's executive summary is distilled into a 150-word
                # entry and injected into the NEXT chapter's prompt. This gives
                # the LLM cross-chapter continuity (prevents repeating content,
                # improves narrative flow). Only applies in sequential mode
                # (max_workers=1). Default ON — no extra LLM cost (deterministic).
                "cross_chapter_context": True,
                # V18.2 (audit Fix 2): Scholar's Reflections section (the
                # "what's missing" self-audit). Default OFF — the user's
                # analysis showed this was the #1 defect, contradicting itself
                # by claiming content is missing that appears elsewhere.
                # The gap-fill mechanism (adds missing content as bullets)
                # still runs regardless; this only controls the TEXT section.
                # Set to True to restore the full reflections output (debugging).
                "scholar_reflections_enabled": False,
                # V18.2 (audit): B4 section map-reduce threshold. Chapters
                # above this token count are split into sections and summarized
                # via map-reduce (multiple LLM calls). Was hardcoded 8000.
                # Raised to 12000 — on a 27B/12GB card, B4's 6 LLM calls take
                # ~1 hour vs single-pass ~10 min. Most chapters under ~50 pages
                # fit in a single 32k context window. Lower to 8000 if you
                # notice coverage dropping on long chapters.
                "b4_threshold_tokens": 12000,
                # V0.03 (P0-1, real-rig audit): dropped-letter auto-repair.
                # DEFAULT OFF. The V0.02 rig run showed 12 of 13 auto-repairs
                # corrupted valid paraphrase words ('contrast'→'contract',
                # 'teams'→'beams', 'skill'→'still' …) — the rule assumed any
                # non-source word at edit-distance-1 from a source word is a
                # garble, which is false for real English words the model
                # legitimately coined. With this enabled, repairs require the
                # English-lexicon guard + paragraph corroboration + strict
                # single-candidate uniqueness. Flags (log-only) always run.
                "dropped_letter_auto_repair": False,
                # V7.7.0: Chapter-level resume — skip chapters with valid summaries on disk
                "resume_enabled": True,
                # V18.20.3.0: Incremental chapter checkpointing — save each
                # chapter's summary (.md) + per-chapter DOCX to
                # checkpoints/chapters/ the moment it completes (crash-safe:
                # power cut / crash / cancel never loses completed chapters;
                # resume then re-runs only the missing chapters). Default ON.
                "incremental_chapter_save": True,
                # ── Quick Mode flags ─────────────────────────────────────
                "include_executive_summary": True,
                "include_thorough_summary": True,
                "include_keypoints": True,
                # ── Academic Rigor ────────────────────────────────────────
                "academic_rigor": False,
                # ── Simplified Keypoints Digest ──────────────────────────
                "simplified_keypoints_enabled": True,  # V13.34.0: enabled by default
                # V10.1.7: default max_workers lowered 2 → 1 for VRAM safety.
                # LLM inference is memory-bandwidth-bound; 1 worker halves
                # VRAM heat.  Users with premium cards can manually raise to 2.
                "max_workers": 1,
                # V10.20.0: Density-over-completeness mode (compact summaries ~1000 tokens)
                "compact_summaries": False,
                # ── V13.36.0: Hybrid Fusion (Local + Cloud) ──────────────
                # When provider == "fusion", the local model (Ollama) does the
                # heavy lifting (primary summarization) and a cloud model is
                # used ONLY for strategic/surgical decisions: self-review,
                # grounding checks, B3 judging, gap-fill. This gives near-local
                # cost (~90% of calls are local/free) with cloud-quality judging.
                "fusion_enabled": False,
                "fusion_cloud_provider": "openai_compat",  # "openai_compat" | "claude"
                "fusion_cloud_model": "google/gemini-2.5-flash-preview:free",
                "fusion_cloud_api_key": "",  # "" = reuse summarisation.api_key
                "fusion_cloud_base_url": "",  # "" = reuse summarisation.api_base_url
                "fusion_cloud_max_tokens": 4096,
                "fusion_cloud_temperature": 0.2,  # low temp for judging/fact-checking
                "fusion_use_for_self_review": True,  # site A: independent fact-checker
                "fusion_use_for_grounding": True,  # site B+C: bullet verification
                "fusion_use_for_b3_judge": True,  # site D: pick best summary
                "fusion_use_for_gap_fill": False,  # site E: local is fine (default off)
            },
            # ── V13.44.3: Local mode settings ──────────────────────────────
            # These only apply when using a local model (Ollama/LM Studio).
            # Cloud APIs ignore all of these — they run at full quality.
            "local": {
                # V18.1 (audit P3): default changed 120 → 0. User undervolted GPU via
                # MSI Afterburner — no thermal pressure, so the 120s sleep between B4
                # sections was pure wasted time (6+ min per 4-section chapter).
                # Users with thermal issues can raise this back to 60-120.
                "vram_recovery_delay_sec": 0,  # 0 = disable VRAM recovery delays
                # V18.1 (audit P5): default raised 3 → 6. The old cap of 3 silently
                # skipped sections 4+ in long chapters — a hidden quality cliff.
                # 6 covers most academic chapters; 0 = unlimited (cloud-like).
                "b4_max_sections": 6,  # 0 = unlimited (process ALL sections)
                "preflight_skip_temp_c": 60,  # 0 = never skip pre-flight
                "http_timeout_sec": 600,  # HTTP read timeout for local Ollama
                # V18.2.15 (P4): Per-chapter wall-clock deadline (seconds).
                # If a single chapter exceeds this, the summarizer logs a
                # traceable WARNING + marks the chapter as failed (but does NOT
                # hard-kill the Ollama request — that has its own HTTP timeout).
                # The audit suggested 8 min (480s). 0 = no deadline.
                # The deadline is checked BETWEEN chapters (not mid-call), so
                # a stuck generation blocks at most one chapter's HTTP timeout
                # (~600s) before the deadline fires on the next check.
                "chapter_deadline_sec": 480,
                # V18.2.15 (P6): OCR page-processing parallelism. The OCR
                # model is loaded ONCE, scans all needed pages, then unloads
                # (see core/ocr/service.py). This setting controls how many
                # pages are processed concurrently DURING that loaded phase.
                # Default 1 (sequential) — safe for the 6 GB OCR model which
                # is single-instance on Ollama (parallel HTTP calls just queue).
                # Set to 2-4 only when using PaddleOCR/Tesseract (CPU-bound).
                "ocr_parallel_workers": 1,
                # V18.20.4.10 (P0-c): what to do when the pre-flight VRAM
                # budget check says the model does NOT fit on the GPU
                # (peak > total). The V18.20.4.9 behaviour was warn-and-
                # continue everywhere except one wizard dialog whose OK
                # button was the default — an accidental Enter started a
                # 20.2 GB model on a 12 GB card, which CPU-offloads at
                # ~0.2 tok/s and turns any map-reduce into a multi-day
                # stall (the 97-Things incident).
                #   "ask"     — the wizard asks (Abort is the DEFAULT button);
                #                non-interactive starts (queue / service
                #                dialogs) ABORT — they cannot ask.
                #   "abort"   — always abort with a clear error.
                #   "proceed" — always continue (the old behaviour, now an
                #                explicit user choice).
                "vram_overbudget_policy": "ask",
                # V18.20.4.10 (P0-d): hard wall-clock budget for the ENTIRE
                # map phase of a map-reduce chapter (all map chunks + the
                # reduce call). When exceeded, the chapter FAILS loudly
                # instead of silently grinding for hours. 0 = disabled.
                # Default 1800s (30 min): enough for ~9 chunks at the 300s
                # IQ2_XXS HTTP timeout; a legit larger chapter should be
                # segmented, not map-reduced (see the segmenter fixes).
                "map_phase_max_seconds": 1800,
            },
            "source_type": "normal_book",
            "is_academic": False,
            "generate_keypoints": True,
            "docx": {
                "enabled": True,  # V13.34.0: enabled by default
                "author": "Elixir",
                "include_toc": True,
                "font": "Helvetica",
                "theme": "apple",
            },
            "rag": {
                "enabled": True,
                "include_frontmatter": True,
                "clean_page_markers": True,
                "target_format": "chromadb",
            },
            "logging": {
                "verbose": True,
                "max_log_files": 5,
                # V13.28.0 (P2.11): Per-module log level overrides.
                # Dict of module_name → level_string.
                # Example: {"packets": "DEBUG", "ocr": "WARNING"}
                # See utils/logging.py _DEFAULT_MODULE_LEVELS for defaults.
                "module_levels": {},
            },
            "ui": {
                "theme": "dark",
                "auto_scroll_logs": True,
                # V8.0.0 #12: auto-open the output folder in the file explorer
                # when a conversion completes. Off by default (opt-in).
                "auto_open_output_folder": False,
                # V8.1.0: post-completion system action (none/quit/sleep/hibernate/shutdown)
                "post_completion_action": "none",
                # V9.0.0 E2: configurable shutdown countdown (seconds)
                "shutdown_countdown_sec": 60,
            },
            "output": {
                "last_input_dir": "",
                "last_output_dir": "",
                "per_book_folder": True,
            },
            "paths": {
                "poppler": "",
                "tesseract": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            },
            "advanced": {
                "extract_tables": False,
                "extract_math": False,
                "layout_analysis": False,
                "table_method": "camelot",
                "math_model": "pix2tex",
                "toc_vision_ocr": False,
                # ── NEW: Sprint 3 – Vision OCR for Figures ──────────────
                "extract_figure_text": False,
                "vision_model_for_figures": "OlmOCR-2-7B:latest",
            },
            # ── V4.7.25: Translation (EN ↔ FA) ───────────────────────────
            "translation": {
                "enabled": False,
                # V13.31.0 (#13): NLLB backend removed from the default UI.
                # Translation is now done exclusively by TranslateGemma
                # (Ollama). V18.20.4.6+ (P5-2b / O-c10): the NLLB fallback
                # module + the dead translation.nllb_model default were
                # retired — nothing reads the key anymore.
                # V11.22: Default changed to "ollama" per user request —
                # TranslateGemma produces more professional translations and
                # can do harakat in the same model.
                "backend": "ollama",
                # Ollama translator (used when backend="ollama")
                # V11.29.1: default = 12B for better quality.
                "model": "translategemma-12b-it.Q4_K_M_mradermacher:latest",
                # Harakat model (always Ollama)
                "harakat_model": "translategemma-12b-it.Q4_K_M_mradermacher:latest",
                "judge_model": "",  # empty = use summarisation.model
                "default_target_lang": "fa",  # "en" or "fa"
                "temperature": 0.1,
                "no_think": True,  # avoid <think> blocks
                "max_chunk_tokens": 2000,  # Ollama chunk size (NLLB uses 400)
                # Validation (zero hallucination tolerance)
                "validation_enabled": True,
                "back_translation_threshold": 0.6,  # semantic similarity
                "judge_threshold": 0.7,  # judge LLM faithfulness
                "max_retries": 1,  # retry failed chunks
                # Harakat (اعراب‌گذاری) for Farsi TTS output
                "harakat_enabled": True,
                "harakat_confident_only": True,
                # Glossary (terminology consistency)
                "glossary_enabled": True,
                # API (reuse Ollama endpoint)
                "endpoint": "http://localhost:11434/v1",
                "api_key": "",
                # Per-output selection (which outputs to translate)
                "outputs": {
                    "full_markdown": False,  # Book.md (huge — off by default)
                    "chapter_summaries": True,  # per-chapter + Book.summary.md
                    "keypoints": True,  # Book.keypoints.md
                    "simplified_keypoints": False,
                    "briefing": False,
                    "podcast": True,  # podcast script → harakat for TTS
                    "flashcards": False,
                    "packets": False,  # V7.3.0: Packets of Knowledge
                    "obsidian": False,
                    "study_guide": False,
                    "social": False,
                    "mindmap": False,
                },
            },
            # ── V7.0.0 S20: RAG indexing and screenshots are now opt-in ────
            "outputs_optin": {
                "rag_indexing": False,  # V7.0.0: Was auto-on, now opt-in
                "screenshots": False,  # V7.0.0: Was auto-on, now opt-in
            },
            # ── V10.1.0: Source Grounding (Google langextract) ──────────────
            # Layer 8 of the anti-hallucination defense.  When enabled, the
            # ContentJudge gets a deterministic verbatim-grounding signal
            # (char_interval) that complements the existing semantic checks.
            #
            # V10.28.0 (Sprint 1.8): Defaults to ON.  The strongest grounding
            # layer is now active by default — the LLM-as-judge fallback
            # (V10.14.0 D6) already covers the case where langextract is not
            # pip-installed, so flipping this ON is safe and gives the user
            # the best available anti-hallucination signal out of the box.
            # Backend defaults to "ollama" (local, free, matches the RTX 3060
            # overnight-run reliability goal).  Cloud backend is opt-in for
            # maximum-rigor scientific articles.
            "grounding": {
                "enabled": True,
                "backend": "ollama",  # "ollama" | "cloud"
                "ollama_model": "",  # "" = use summarisation.model
                "ollama_url": "http://localhost:11434",
                "cloud_model": "gpt-4o-mini",
                "cloud_base_url": "",  # "" = use summarisation.api_base_url
                "cloud_api_key": "",  # "" = use summarisation.api_key
                "extraction_passes": 1,  # 1-3 (recall vs cost)
                "max_workers": 1,  # V13.41.2: 1 worker (sequential, less VRAM pressure)
                "max_char_buffer": 8000,  # V13.41.2: 4000→8000 (halves chunk count)
                "timeout_sec": 600,  # V13.41.2: 120→600 (Gemma 4 12B needs ~35s/chunk × 6 chunks)
            },
            # ── V18.1 (audit O1/O3): Embedding model config ──────────────────
            # The embedder is used for semantic fact-checking (hallucination
            # detection), content judging, keypoints dedup, packets validation,
            # and translation back-translation checks.
            #
            # V18.2 (audit): Default is bge-base-en-v1.5 (MTEB 64.2, 440 MB) —
            # a strong embedder that fits on GPU alongside a 27B IQ2_XXS model
            # (9 GB + 2 GB KV + 0.5 GB compute = 11.5 GB, leaving ~0.5 GB for
            # the embedder on a 12 GB card).
            #
            # IMPORTANT: This requires using the IQ2_XXS quant (9.01 GB), NOT
            # IQ2_M (10.3 GB). With IQ2_M, VRAM overflows → CPU offloading →
            # the embedder competes with offloaded layers → CPU 100%.
            # With IQ2_XXS, the model fits entirely in VRAM, freeing ~0.5 GB
            # for the embedder on GPU.
            #
            # If you're using IQ2_M (or a model that fills VRAM), change this
            # to "all-MiniLM-L6-v2" (80 MB, fast on CPU, doesn't compete).
            #
            # For the 8B embedder (Qwen3-Embedding-8B), set load_mode="sequential"
            # — the LLM is unloaded, the embedder loads, computes all embeddings,
            # then unloads and the LLM reloads. Best quality but ~2 min/chapter
            # extra for model reloads.
            "embedding": {
                # V18.4 (Phase 2): embedder hardening & optional mode.
                # ``enabled`` gates the semantic-similarity path in
                # content_judge._semantic_similarity (Phase 2.2 fact-check).
                #   True  (default) — embedder used; falls back to Jaccard on
                #                     failure (existing gold-standard behaviour).
                #   False           — embedder NOT attempted. ``fallback``
                #                     decides what happens next:
                #                       "jaccard" (default) → lexical Jaccard
                #                          word-overlap similarity (weaker but
                #                          real signal; coverage % still runs).
                #                       "skip"              → Phase 2.2 skipped
                #                          ENTIRELY (explicit, one WARNING per
                #                          chapter). Use only when you trust
                #                          the LLM output or need max speed.
                "enabled": True,
                "fallback": "jaccard",  # "jaccard" | "skip"
                "model": "nomic-embed-text",  # V18.15.1: switched from BAAI/bge-small-en-v1.5 (HF, needs sentence_transformers) to nomic-embed-text (Ollama, just needs `ollama pull nomic-embed-text`). This fixes the "embedder unhealthy" issue — Ollama is already running, no extra Python packages needed.
                "device": "auto",  # "auto" = cuda if >0.6 GB free, else cpu
                "cache_enabled": True,  # on-disk embedding cache (~/.elixir/embed_cache/)
                "load_mode": "resident",  # "resident" | "sequential" (sequential for 8B embedders)
                # Threshold scale factor: multiplies all similarity thresholds
                # in core/summarisation/thresholds.py. 1.0 = use defaults.
                "threshold_scale": 1.0,
            },
            # ── Output Studio — all 17 output toggles ───────────────────────
            "outputs": {
                "briefing": True,  # V4.0.0
                "podcast": True,  # V4.0.0
                "flashcards": True,  # V4.0.0
                "packets": False,  # V7.3.0
                "obsidian": False,  # V4.1.0
                "study_guide": False,  # V4.1.0
                "social": False,  # V4.1.0
                "mindmap": False,  # V4.1.0
                "tts": False,  # V4.2.0
                "evidence_map": False,  # V10.1.0
                "qa": False,  # V10.17.0
                "glossary": False,  # V10.20.0
                "patterns": False,  # V10.20.0
                "cheatsheet": False,  # V10.20.0
                "skill": False,  # V10.21.0
                "epub": False,  # V10.35.0
                "quote_bank": False,  # V10.35.0
            },
            # ── V10.1.6: Manual GPU thermal profile override ─────────────────
            # For cards where nvidia-smi doesn't report the board partner name
            # (e.g. some Zotac cards report "NVIDIA GeForce RTX 3060" instead
            # of "ZOTAC GeForce RTX 3060 Twin Edge OC").  Set to "zotac_3060"
            # to force the emergency thermal profile.
            # Values: "auto" | "zotac_3060" | "zotac_3060_ti" | "zotac_3070" | "generic"
            # ── V10.1.6: Manual GPU thermal profile override ─────────────────
            # V10.1.7: default changed from "auto" to "zotac_3060" since
            # the user's card (Zotac RTX 3060 Twin Edge OC) doesn't report
            # its brand name to nvidia-smi, so auto-detection fails.
            "hardware": {
                "gpu_profile_override": "zotac_3060",
            },
            # ── V10.1.8: Per-model temperature profiles ─────────────────────
            # The user manually enters the fine-tuner's recommended temp
            # range for each model.  The app NEVER overrides this — not
            # Academic Rigor, not quality presets, nothing.
            # Pre-seeded with the user's known models:
            "model_temperatures": {
                "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest": {
                    "min": 0.6,
                    "max": 0.8,
                    "recommended": 0.7,
                },
                "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest": {
                    "min": 0.6,
                    "max": 0.8,
                    "recommended": 0.7,
                },
                "gemma2:7b": {
                    "min": 0.4,
                    "max": 0.9,
                    "recommended": 0.6,
                },
                "gemma2:9b": {
                    "min": 0.4,
                    "max": 0.9,
                    "recommended": 0.6,
                },
                # V13.34.0: Gemma 4 12B — official recommended settings
                "gemma4-12b:latest": {
                    "min": 0.8,
                    "max": 1.2,
                    "recommended": 1.0,
                },
                "qwen2.5:7b": {
                    "min": 0.3,
                    "max": 0.9,
                    "recommended": 0.6,
                },
                "mistral:7b": {
                    "min": 0.3,
                    "max": 0.9,
                    "recommended": 0.5,
                },
                # V10.2.1: Ornith-1.0-9B (coding model — tested at t=1.0)
                # Not recommended for summarization (it's a coding model), but
                # included so the app enforces its temperature range if used.
                "ornith-1.0-9b-Q5_K_M_deepreinforce_AI.gguf:latest": {
                    "min": 0.7,
                    "max": 1.2,
                    "recommended": 1.0,
                },
            },
            # ── V10.36.0: Content filter settings ───────────────────────────
            "content_filter": {
                "enabled": True,
                "min_content_chars": 60,
                "min_word_count": 2,
            },
            # ── V4.7.25: TTS settings ────────────────────────────────────────
            "tts": {
                "en_engine": "neutts",
                "en_voice": "af_heart",
                "fa_voice": "fa_IR-amir-medium",
                "host_a_voice": "",
                "host_b_voice": "",
                "speed": 1.0,
                "piper_binary": r"C:\piper_windows_amd64\piper\piper.exe",
                "neutts_gguf_path": r"G:\Program Files\neutts-air\models\neutts-air-Q8_0.gguf",
                "neutts_project_path": r"G:\Program Files\neutts-air",
                # V11.32.0: NeuTTS device configuration.
                "neutts_backbone_device": "cuda",
                "neutts_codec_device": "cuda",
                "neutts_use_subprocess": False,
                # V11.38.0: Qwen3-TTS (replaces NeuTTS as primary English engine)
                "qwen_model_path": r"C:\Qwen3-TTS-12Hz-1.7B-CustomVoice",
                "qwen_speaker": "Vivian",
                # V11.40.0: VibeVoice (high-quality English TTS)
                "vibevoice_model_path": r"C:\VibeVoice-Realtime-0.5B",
                "vibevoice_voices_dir": r"C:\VibeVoice\demo\voices\streaming_model",
                "vibevoice_default_voice": "en-Carter_man",
                "normalize_enabled": True,
                "australian_enabled": False,
                "australian_reference_wav": "",
                "australian_reference_text": "",
                # V10.36.0: Coqui XTTS v2
                "fa_engine": "piper",
                "coqui_model": "tts_models/multilingual/multi-dataset/xtts_v2",
                "coqui_speaker": "Ana",
                "coqui_voice_sample": "",
            },
            # ── V4.7.3: Podcast settings ─────────────────────────────────────
            "podcast": {
                "format": "conversational",
                "depth": "thorough",
                "style": "engaging",
                "tone": "informative",
                "human_fillers": True,
                "host_a_name": "Alex",
                "host_b_name": "Sam",
                "target_duration_min": 15,
            },
            # ── V13.23.0: Packets of Knowledge mode ──────────────────────────
            # "chapter" (default, new architecture): 1+ packets per chapter,
            #   using the author's own chapter boundaries. Split if >10 bullets,
            #   supplement with exec summary if <5 bullets.
            # "cross_chapter" (legacy): cross-chapter semantic clustering.
            #   May produce mismatched packets — use at own risk.
            "packets": {
                "mode": "chapter",
            },
            # ── V11: Quick service preferences ────────────────────────────────
            "quick_services": {
                "ocr": {
                    "engine": "auto",
                    "format": ".md",
                },
                # V11.21.1: per-service sub-dicts so the settings validator
                # recognises keys written by BaseServiceDialog._save_setting().
                # Without these, the validator logs "Unknown setting" warnings
                # on every write (non-fatal, but noisy).
                "summarization": {
                    "quality": "standard",
                    "format": ".md",
                    "obsidian": False,
                },
                "translation": {
                    "target_lang": "fa",
                    "backend": "__default__",
                    "format": "__default__",
                    "obsidian": False,
                    "save_to_folder": "",
                },
                "tts": {
                    "engine": "__default__",
                    "voice": "",
                    "speed": 1.0,
                    "language": "auto",
                    "format": ".wav",  # V11.36.2: .wav or .mp3
                    "style": "natural",  # V11.35.0: speaking style
                },
                # V11.19: Default engines/models/formats used by the standalone
                # service dialogs. Each tool's dialog shows a "Default (change
                # in Settings)" option that, when selected, reads from here.
                "defaults": {
                    # Summarization Service
                    "summarize_model": "",  # "" = use summarisation.model
                    "summarize_quality": "standard",  # fast | standard | thorough
                    "summarize_format": ".md",  # .md | .docx | .pdf
                    "summarize_obsidian": False,  # Obsidian-style markdown
                    # OCR Service
                    "ocr_engine": "auto",  # auto | pypdf | ollama | vlm | tesseract
                    "ocr_format": ".md",  # .md | .txt | .docx | .pdf
                    "ocr_model": "",  # "" = use ocr.primary_model
                    # PDF → Markdown
                    "pdf_format": ".md",  # .md | .docx | .pdf
                    # TTS Service
                    "tts_engine": "",  # "" = use tts.en_engine
                    # Translation Service
                    "translation_backend": "ollama",  # "ollama" only — NLLB removed from Translation Service (V11.31)
                    "translation_format": ".md",  # .md | .docx | .pdf
                    "translation_obsidian": False,  # Obsidian-style markdown
                },
            },
        }

    def _load(self) -> dict[str, Any]:
        defaults = self._defaults()
        if not self._settings_file.exists():
            self._data = defaults
            self.save()
            return defaults
        try:
            # V18.20.4.3 (P2 / W-c4 + T-c8): ``utf-8-sig`` — tolerates the
            # UTF-8 BOM Windows Notepad writes by default. The old plain
            # ``utf-8`` open left the BOM in front of ``{`` → json.load
            # threw → the corrupt-file reset path below (full silent
            # defaults, user loses API keys/models) fired on a hand-edit
            # that was actually fine.
            with open(self._settings_file, encoding="utf-8-sig") as f:
                user_data = json.load(f)
            merged = self._deep_merge(defaults, user_data)

            # Enforce minimum OCR timeout
            if merged.get("ocr", {}).get("timeout", 0) < 90:
                merged["ocr"]["timeout"] = 120
                logging.warning("[Settings] Overriding ocr.timeout to 120s (minimum required)")

            # ── Ensure quality defaults exist ──────────────────────────────
            summ = merged.setdefault("summarisation", {})
            for key, default_val in [
                ("temperature", 0.2),
                ("self_consistency", False),
                ("heavy_model", ""),
                # V18.20.2.0 (SWOT A28): duplicate ``fast_model`` entry
                # removed.  This list used to contain it twice — first
                # "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest", then "".
                # These entries are belt-and-braces only (the merged dict
                # ALWAYS has fast_model from ``_defaults()``, so neither
                # entry ever fired), but the effective default they back
                # up is "" — the single remaining entry matches it.
                # V16.0.9: 4-mode model architecture
                (
                    "model_architecture",
                    "single_local",
                ),  # single_local | dual_local | single_api | dual_api
                ("fast_model", ""),
                ("fast_model_temperature", 0.1),
                ("fast_model_context", 131072),
                ("fast_api_url", ""),
                ("fast_api_key", ""),
                ("fast_api_model", ""),
                ("coverage_threshold", 50),
                ("overdeliver_enabled", True),  # V15.1.0
                ("overdeliver_target", 100),  # V15.1.1: was 92, now 100
                ("b3_voting_enabled", False),  # V15.1.1: new
                ("resume_enabled", True),  # V7.7.0
                ("include_executive_summary", True),
                ("include_thorough_summary", True),
                ("include_keypoints", True),
                ("academic_rigor", False),
                # ── Claude defaults ──────────────────────────────────────────
                ("claude_api_key", ""),
                ("claude_model", "claude-3-5-sonnet-20241022"),
                ("claude_base_url", "https://api.anthropic.com/v1"),
                ("claude_max_tokens", 4096),
                # ── Simplified Keypoints ─────────────────────────────────────
                ("simplified_keypoints_enabled", False),
                # ── NEW: Sprint 3 – max_workers ─────────────────────────────
                ("max_workers", 2),
            ]:
                if key not in summ:
                    summ[key] = default_val

            # If heavy_model is None or empty, ensure it stays empty
            if summ.get("heavy_model") is None:
                summ["heavy_model"] = ""

            # Ensure PaddleOCR setting exists
            ocr = merged.setdefault("ocr", {})
            if "use_paddleocr" not in ocr:
                ocr["use_paddleocr"] = False

            # Ensure source_type and is_academic exist
            if "source_type" not in merged:
                merged["source_type"] = "normal_book"
            if "is_academic" not in merged:
                merged["is_academic"] = False

            # ── Ensure advanced settings exist ──────────────────────────────
            adv = merged.setdefault("advanced", {})
            for key, default_val in [
                ("extract_tables", False),
                ("extract_math", False),
                ("layout_analysis", False),
                ("table_method", "camelot"),
                ("math_model", "pix2tex"),
                ("toc_vision_ocr", False),
                # ── NEW: Sprint 3 – figure extraction ──────────────────────
                ("extract_figure_text", False),
                ("vision_model_for_figures", "OlmOCR-2-7B:latest"),
            ]:
                if key not in adv:
                    adv[key] = default_val

            # ── V4.7.25: Ensure translation settings exist ───────────────────
            tr = merged.setdefault("translation", {})
            for key, default_val in [
                ("enabled", False),
                # V13.31.0 (#13): default backend is now "ollama" (was "nllb")
                ("backend", "ollama"),
                # V18.20.4.6+ (P5-2b / O-c10): nllb_model removed — the
                # deprecated NLLB backend was retired; nothing reads it.
                ("model", "translategemma:4b"),
                ("harakat_model", "translategemma:4b"),
                ("judge_model", ""),
                ("default_target_lang", "fa"),
                ("temperature", 0.1),
                ("no_think", True),
                ("max_chunk_tokens", 2000),
                ("validation_enabled", True),
                ("back_translation_threshold", 0.6),
                ("judge_threshold", 0.7),
                ("max_retries", 1),
                ("harakat_enabled", True),
                ("harakat_confident_only", True),
                ("glossary_enabled", True),
                ("endpoint", "http://localhost:11434/v1"),
                ("api_key", ""),
            ]:
                if key not in tr:
                    tr[key] = default_val

            # V13.31.0 (#13): Auto-migrate any existing "nllb" backend to
            # "ollama" since the NLLB option has been removed from the UI.
            if tr.get("backend") == "nllb":
                logger.warning(
                    "[Settings] V13.31.0: migrating translation.backend "
                    "'nllb' -> 'ollama' (NLLB removed from UI)"
                )
                tr["backend"] = "ollama"
            # V18.20.4.6+ (P5-2b / O-c10): delete the dead translation.
            # nllb_model key (NLLB backend retired with core.translation.
            # nllb_translator). The key was previously persisted into every
            # settings.json by the DEFAULTS merge, so legacy files carry it;
            # deleting it here keeps the schema validator quiet (same house
            # pattern as the bootstrap b3_voting_enabled A14 deletion).
            if "nllb_model" in tr:
                del tr["nllb_model"]
                logger.info(
                    "[Settings] Removed deprecated translation.nllb_model "
                    "setting (NLLB backend retired)."
                )
            # Ensure the per-output sub-dict exists
            tr_out = tr.setdefault("outputs", {})
            for key, default_val in [
                ("full_markdown", False),
                ("chapter_summaries", True),
                ("keypoints", True),
                ("simplified_keypoints", False),
                ("briefing", False),
                ("podcast", True),
                ("flashcards", False),
                ("packets", False),  # V7.3.0
                ("obsidian", False),
                ("study_guide", False),
                ("social", False),
                ("mindmap", False),
            ]:
                if key not in tr_out:
                    tr_out[key] = default_val

            # ── V4.7.25: Ensure TTS Australian accent settings exist ────────
            tts = merged.setdefault("tts", {})
            for key, default_val in [
                ("australian_enabled", False),
                ("australian_reference_wav", ""),
                ("australian_reference_text", ""),
                # V10.36.0: Coqui XTTS v2 settings (Better Persian TTS)
                ("fa_engine", "piper"),  # "piper" or "coqui"
                ("coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2"),
                ("coqui_speaker", "Ana"),
                ("coqui_voice_sample", ""),
            ]:
                if key not in tts:
                    tts[key] = default_val

            # ── V11.32.2: NeuTTS device migration ──────────────────────────
            # If the user's settings.json has neutts_backbone_device = "cpu"
            # (saved from a previous version) but CUDA is available, upgrade
            # it to "cuda" automatically. This fixes the "still too slow"
            # problem without requiring the user to manually edit settings.
            # Also ensures the device keys exist (V11.32.0+ defaults).
            if "neutts_backbone_device" not in tts:
                tts["neutts_backbone_device"] = "cuda"
            if "neutts_codec_device" not in tts:
                tts["neutts_codec_device"] = "cuda"
            if "neutts_use_subprocess" not in tts:
                tts["neutts_use_subprocess"] = False
            # Auto-upgrade CPU → CUDA when a GPU is present.
            try:
                import torch as _torch

                if _torch.cuda.is_available() and _torch.cuda.device_count() > 0:
                    upgraded = []
                    if tts.get("neutts_backbone_device") == "cpu":
                        tts["neutts_backbone_device"] = "cuda"
                        upgraded.append("backbone")
                    if tts.get("neutts_codec_device") == "cpu":
                        tts["neutts_codec_device"] = "cuda"
                        upgraded.append("codec")
                    if upgraded:
                        logging.warning(
                            "[Settings] V11.32.2: auto-upgraded NeuTTS %s "
                            "device cpu→cuda (GPU detected)",
                            "+".join(upgraded),
                        )
            except Exception:
                pass  # torch not available — leave settings as-is

            # ── V18.15.1: Auto-migrate embedding model to nomic-embed-text ──
            # The old defaults (all-MiniLM-L6-v2, BAAI/bge-small-en-v1.5) require
            # the sentence_transformers Python package, which may not be installed.
            # nomic-embed-text uses Ollama's /api/embeddings endpoint — no extra
            # Python packages needed, just `ollama pull nomic-embed-text`.
            # Auto-migrate any old HF-based embedding model to nomic-embed-text.
            emb = merged.setdefault("embedding", {})
            _old_embed_models = {
                "all-MiniLM-L6-v2",
                "BAAI/bge-small-en-v1.5",
                "BAAI/bge-base-en-v1.5",
                "sentence-transformers/all-MiniLM-L6-v2",
            }
            if emb.get("model", "") in _old_embed_models:
                logger.warning(
                    "[Settings] V18.15.1: migrating embedding.model '%s' "
                    "-> 'nomic-embed-text' (Ollama-based, no sentence_transformers needed). "
                    "Run 'ollama pull nomic-embed-text' to download the model.",
                    emb.get("model"),
                )
                emb["model"] = "nomic-embed-text"

            # ── V10.1.0: Ensure grounding (langextract) settings exist ──────
            # V10.28.0 (Sprint 1.8): default changed False → True.
            gr = merged.setdefault("grounding", {})
            for key, default_val in [
                ("enabled", True),  # V10.28.0: was False — strongest grounding ON by default
                ("backend", "ollama"),
                ("ollama_model", ""),
                ("ollama_url", "http://localhost:11434"),
                ("cloud_model", "gpt-4o-mini"),
                ("cloud_base_url", ""),
                ("cloud_api_key", ""),
                ("extraction_passes", 1),
                ("max_workers", 1),  # V13.41.2: 2→1 (sequential, less VRAM pressure)
                ("max_char_buffer", 8000),  # V13.41.2: 4000→8000 (halves chunk count)
                ("timeout_sec", 600),  # V13.41.2: 120→600 (Gemma 4 12B needs ~35s/chunk × 6)
            ]:
                if key not in gr:
                    gr[key] = default_val

            # V13.42.3: Force-set grounding model to "" (use summarisation.model).
            # The user's settings had grounding.ollama_model set to a model name
            # that doesn't exist in Ollama (Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest
            # vs the actual Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest).
            # Setting it to "" makes langextract use the summarisation model
            # (gemma4-12b:latest), which is already loaded in VRAM.
            if gr.get("ollama_model", "") and gr["ollama_model"] != "":
                _installed_check = gr["ollama_model"]
                if "Qwythos" in _installed_check or "qwythos" in _installed_check.lower():
                    if "empero" not in _installed_check.lower():
                        logger.info(
                            "[Settings] V13.42.3: resetting grounding.ollama_model "
                            "'%s' -> '' (use summarisation model gemma4-12b).",
                            _installed_check,
                        )
                        gr["ollama_model"] = ""

            # V13.41.2: FORCE-UPDATE grounding settings that were changed.
            if gr.get("max_workers", 1) == 2:
                gr["max_workers"] = 1
                logger.info("[Settings] V13.41.2: migrating grounding.max_workers 2→1")
            if gr.get("max_char_buffer", 8000) == 4000:
                gr["max_char_buffer"] = 8000
                logger.info("[Settings] V13.41.2: migrating grounding.max_char_buffer 4000→8000")
            if gr.get("timeout_sec", 600) == 120:
                gr["timeout_sec"] = 600
                logger.info("[Settings] V13.41.2: migrating grounding.timeout_sec 120→600")

            # ── V10.1.0: Ensure outputs.evidence_map flag exists ───────────
            outs = merged.setdefault("outputs", {})
            if "evidence_map" not in outs:
                outs["evidence_map"] = False

            # ── V10.1.6: Ensure hardware.gpu_profile_override exists ───────
            hw = merged.setdefault("hardware", {})
            if "gpu_profile_override" not in hw:
                hw["gpu_profile_override"] = "zotac_3060"  # V10.1.7: was "auto"

            # ── V10.1.7: Enforce new defaults for existing settings ─────────
            # Force max_workers to 1 and temperature to 0.6 if the user hasn't
            # explicitly changed them (i.e., they're at the old defaults).
            summ = merged.setdefault("summarisation", {})
            if summ.get("max_workers") == 2:
                summ["max_workers"] = 1  # V10.1.7: VRAM safety
            if summ.get("temperature") == 0.2:
                summ["temperature"] = 0.6  # V10.1.7: 0.2 produced empty output

            # ── V10.1.8: Ensure model_temperatures exists ───────────────────
            mt = merged.setdefault("model_temperatures", {})
            # Merge in any new pre-seeded models from defaults that the user
            # doesn't have yet (without overwriting user-set values).
            _default_mts = defaults.get("model_temperatures", {})
            for _mk, _mv in _default_mts.items():
                if _mk not in mt:
                    mt[_mk] = _mv

            # ── V18.1/V18.2 (audit): Migrate old settings to new defaults ──
            # These FORCE-UPDATE old values that were saved by previous versions
            # and would otherwise override the new defaults (causing the 120s
            # VRAM sleep to still fire, max_output_tokens to stay at 8192, etc.)
            _local = merged.setdefault("local", {})
            # V18.1: vram_recovery_delay_sec 120→0 (user undervolted GPU)
            if _local.get("vram_recovery_delay_sec", 0) == 120:
                _local["vram_recovery_delay_sec"] = 0
                logger.info(
                    "[Settings] V18.1: migrating local.vram_recovery_delay_sec 120→0 (undervolted GPU)"
                )
            # V18.1: b4_max_sections 3→6 (was silently skipping sections 4+)
            if _local.get("b4_max_sections", 6) == 3:
                _local["b4_max_sections"] = 6
                logger.info(
                    "[Settings] V18.1: migrating local.b4_max_sections 3→6 (stop skipping sections)"
                )
            # V18.1: max_output_tokens <16000 → 16000 (was 8192 in old versions)
            # V0.04 GUARD: skip when the llama.cpp backend is active — its
            # 12288 output cap is a MODEL limit, and this legacy floor would
            # re-raise it to 16000 on every load (migrations must not fight
            # newer backend-specific caps).
            _summ_mig = merged.setdefault("summarisation", {})
            if (
                _summ_mig.get("max_output_tokens", 16000) < 16000
                and _summ_mig.get("provider", "ollama") != "llamacpp"
            ):
                _summ_mig["max_output_tokens"] = 16000
                logger.info(
                    "[Settings] V18.1: migrating summarisation.max_output_tokens %d→16000",
                    _summ_mig.get("max_output_tokens", 8192),
                )

            # ── V0.04 (llama.cpp backend): one-time activation ─────────────
            # The rig's primary LLM backend moves from Ollama to a local
            # llama.cpp server (llama-server, 127.0.0.1:8080). GENERAL RULE:
            # a backend switch migrates ONLY installations still sitting at
            # the untouched previous default — an explicit user choice
            # (lmstudio / cloud / anything else) is never overridden. The
            # llamacpp_* keys themselves are deep-merged from defaults for
            # every install (idempotent), so the backend is always
            # configurable regardless of the activation flip.
            _summ_lc = merged.setdefault("summarisation", {})
            _lc_defaults = defaults.get("summarisation", {})
            for _k in (
                "llamacpp_base_url",
                "llamacpp_api_key",
                "llamacpp_model",
                "llamacpp_context_tokens",
                "llamacpp_max_output_tokens",
            ):
                if _k in _lc_defaults and _k not in _summ_lc:
                    _summ_lc[_k] = _lc_defaults[_k]
            if not _summ_lc.get("llamacpp_activation_done", False):
                _summ_lc["llamacpp_activation_done"] = True
                if _summ_lc.get("provider", "ollama") == "ollama":
                    _summ_lc["provider"] = "llamacpp"
                    _summ_lc["model"] = _lc_defaults.get(
                        "llamacpp_model", "Ternary-Bonsai-2-27B-Instruct-Vision"
                    )
                    # 32k→65k only when still at the old default (a user's
                    # custom ctx survives untouched).
                    if _summ_lc.get("max_context_tokens", 32768) == 32768:
                        _summ_lc["max_context_tokens"] = _lc_defaults.get(
                            "llamacpp_context_tokens", 65536
                        )
                    # The old 16000 output default EXCEEDS the new model's
                    # 12288 output cap — clamp down (again: only at the old
                    # default; custom values survive).
                    if _summ_lc.get("max_output_tokens", 16000) == 16000:
                        _summ_lc["max_output_tokens"] = _lc_defaults.get(
                            "llamacpp_max_output_tokens", 12288
                        )
                    logger.info(
                        "[Settings] V0.04: activating llama.cpp backend "
                        "(provider ollama→llamacpp, ctx 65536, output 12288)"
                    )
                else:
                    logger.info(
                        "[Settings] V0.04: llama.cpp backend available (kept provider=%s)",
                        _summ_lc.get("provider", "?"),
                    )

            self._data = merged

            # V10.4.0 (Phase 6B-3): Schema validation — catch typos and
            # type errors at load time.  Unknown keys (e.g. "sumarisation"
            # instead of "summarisation") produce clear warnings with a
            # closest-match suggestion.  Type errors (e.g. max_workers="two")
            # produce a validation message.  These are WARNINGs, not fatal —
            # the app still loads (using defaults for unknown keys) so a
            # typo never bricks the app, but the user is told exactly what's
            # wrong instead of getting silent misbehaviour.
            try:
                key_errors = validate_settings(merged, defaults)
                for ke in key_errors:
                    logger.warning(f"[Settings] {ke}")
                type_errors = validate_types(merged)
                for te in type_errors:
                    logger.warning(f"[Settings] {te}")
            except Exception as _ve:
                logger.warning(f"[Settings] Schema validation skipped: {_ve}")

            return merged

        except Exception:
            # V18.20.4.3 (P2 / W-c4): a corrupt settings.json is now
            # BACKED UP before the reset (``settings.json.corrupt-<ts>``)
            # instead of being silently replaced — the user's models, API
            # keys and TTS paths stay recoverable, and the log names the
            # backup path. Best-effort: a failed copy never blocks the
            # defaults fallback.
            _backup = self._backup_corrupt_file()
            logger.error(
                "[Settings] Error loading: %s. Using defaults."
                + (f" Corrupt file backed up → {_backup}" if _backup else "")
            )
            self._data = defaults
            return defaults

    def _backup_corrupt_file(self) -> str | None:
        """V18.20.4.3 (W-c4): timestamped copy of the unreadable settings
        file, so the reset-to-defaults path never destroys user data.
        Returns the backup path, or None if the copy failed (best-effort).
        """
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self._settings_file.with_name(f"{self._settings_file.name}.corrupt-{ts}")
            shutil.copy2(self._settings_file, backup)
            return str(backup)
        except Exception as _be:
            logger.warning("[Settings] Could not back up corrupt settings file: %s", _be)
            return None

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self) -> bool:
        # V9.0.0: atomic write + thread lock — prevents corruption from
        # concurrent writes (UI thread + conversion worker can both call
        # update_setting simultaneously).
        # V18.20.4.3 (P2 / W-b6): returns success — callers (the settings
        # dialog) can now WARN instead of closing as-if-saved when the
        # disk write fails (disk-full / permission). Still never raises
        # (fail-soft contract unchanged).
        with self._lock:
            try:
                atomic_write_json(self._settings_file, self._data, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                logger.error(f"[Settings] Error saving: {e}")
                return False

    def get(self, path: str, default: Any = None) -> Any:
        with self._lock:
            keys = path.split(".")
            value = self._data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                    if value is None:
                        return default
                else:
                    return default
            # V10.4.0 (Phase 6B-4): Resolve ${env:VAR} / ${VAR} patterns in
            # string values at read time.  This lets API keys live in env
            # vars instead of settings.json.  Warnings for unset vars are
            # logged once (best-effort) so the user knows a secret is missing.
            if isinstance(value, str) and "${" in value:
                resolved, warnings = resolve_env_vars_with_warnings(value)
                for w in warnings:
                    logger.warning(f"[Settings] {w} (path: {path})")
                return resolved
            return value

    def get_ollama_url(self) -> str:
        """V13.27.0 (P2.6): Get the canonical Ollama URL.

        Resolves from any of these keys (in priority order):
        1. ``llm.ollama_url`` (canonical, V13.27.0+)
        2. ``summarisation.endpoint`` (legacy, used by Summarizer + packets)
        3. ``summarisation.ollama_url`` (legacy, used by some dialogs)
        4. ``ocr.ollama_url`` (legacy, used by OCR dialogs)
        5. ``translation.endpoint`` (legacy, used by translation)

        Falls back to ``http://localhost:11434`` if none are set.

        Returns the base URL WITHOUT ``/v1`` suffix (useful for /api/tags,
        /api/generate). Callers that need the OpenAI-compatible path should
        append ``/v1`` themselves.
        """
        # Try canonical key first
        url = self.get("llm.ollama_url", "")
        if not url:
            # Fall back to legacy keys
            for legacy in (
                "summarisation.endpoint",
                "summarisation.ollama_url",
                "ocr.ollama_url",
                "translation.endpoint",
            ):
                url = self.get(legacy, "")
                if url:
                    break
        if not url:
            url = "http://localhost:11434"
        # Strip /v1 suffix — callers that need it will add it back
        if url.endswith("/v1"):
            url = url[:-3]
        return url.rstrip("/")

    def set(self, path: str, value: Any) -> bool:
        # V18.20.4.3 (P2 / W-b6): returns the persistence result so
        # write-path callers can surface disk failures (the in-memory
        # mutation still always happens — unchanged fail-soft contract).
        with self._lock:
            # V10.4.0 (Phase 6B-3): Typo detection on write.
            # Validates the path against the known-keys schema derived from
            # ``_defaults()``.  When the path looks like a typo of a known
            # setting (close Levenshtein match), logs a WARNING with a
            # suggestion — but STILL writes the value.  This is non-breaking:
            # the defaults dict intentionally doesn't declare every UI-written
            # key (e.g. ``tts.*``, ``podcast.*``, ``output.custom_dir``,
            # ``summarisation.lmstudio_url``), so we cannot hard-reject
            # unknown paths.  The warning makes typos visible in the logs
            # without crashing the UI.
            try:
                err = validate_setting_path(path, self._defaults())
                if err is not None:
                    logger.warning(f"[Settings] {err} (writing anyway)")
            except Exception:
                pass  # validation must never block a write
            keys = path.split(".")
            target = self._data
            for key in keys[:-1]:
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                target = target[key]
            target[keys[-1]] = value
            # V18.20.4.12 (W-c19): inside an active batch() the disk write
            # is DEFERRED — the in-memory mutation above is already done
            # (get()/snapshot() see the new value immediately) and ONE
            # coalesced save() fires at the outermost batch() exit.
            # getattr-defensive: instances built without __init__ (the
            # object.__new__ harness pattern) must not crash here.
            if getattr(self, "_batch_depth", 0) > 0:
                self._batch_dirty = True
                return True
        return self.save()

    @contextmanager
    def batch(self) -> Iterator["Settings"]:
        """V18.20.4.12 (W-c19): defer disk writes — N set() calls coalesce
        into ONE save. Nested-safe (depth counter). Default set() behavior
        OUTSIDE a batch is UNCHANGED (immediate save). On exception the
        batch still saves what was set (matches set()'s per-write
        persistence semantics — partial progress survives), then re-raises.

        Each set() inside the block mutates in-memory only; the outermost
        exit performs ONE save() for the whole block, so writing N settings
        costs ONE atomic-write + fsync instead of N (save() rewrites the
        whole settings.json, so a loop of bare set() calls was N full-file
        writes). set() returns True inside a batch (the write is accepted;
        the eventual exit-save result is the batch's, and save() itself
        stays fail-soft/never-raises).

        Thread-safety: depth/dirty bookkeeping reuses the existing
        ``self._lock`` (RLock) — coherent with set()/get()/save(). A set()
        from another thread while a batch is active on this instance is
        ALSO deferred and flushed by the batch exit.

        Usage::

            with settings.batch():
                settings.set("a.b", 1)
                settings.set("c.d", 2)   # → exactly ONE save() at exit
        """
        # getattr-defensive: instances built without __init__ (the
        # object.__new__ harness pattern) must not crash here.
        with self._lock:
            self._batch_depth = getattr(self, "_batch_depth", 0) + 1
            if self._batch_depth == 1:
                # Fresh outermost batch — clear any stale dirty flag so an
                # empty batch performs no save. (A stale flag can only come
                # from a previous exit interrupted mid-reset, i.e. never in
                # practice — this is belt-and-braces, like set()'s guard.)
                self._batch_dirty = False
        try:
            yield self
        finally:
            # try/finally shape: BOTH the normal path and an in-block
            # exception run this block — the dirty flag is flushed (save)
            # and the exception then propagates naturally out of the
            # with-statement. save() never raises (fail-soft), so it can't
            # mask the in-block exception.
            flush = False
            with self._lock:
                self._batch_depth = max(0, getattr(self, "_batch_depth", 1) - 1)
                if self._batch_depth == 0 and getattr(self, "_batch_dirty", False):
                    self._batch_dirty = False
                    flush = True
            if flush:
                self.save()  # outside the lock — same shape as set()

    def snapshot(self) -> dict[str, Any]:
        """V18.20.4.3 (P2 / W-c3): locked deep-copy of the settings store.

        Safe to hand to callers that iterate while a conversion worker
        mutates nested dicts via ``set`` — the previous live-dict return
        raced ("dictionary changed size during iteration"). Mutating the
        returned dict never touches the store.
        """
        with self._lock:
            return copy.deepcopy(self._data)

    def reset_to_defaults(self) -> None:
        """Reset all settings to the factory defaults and persist."""
        self._data = self._defaults()
        self.save()


# ── DI helpers ────────────────────────────────────────────────────────────


def get_settings() -> Settings:
    """Get the Settings singleton (or test override if set).

    This is the preferred way to access Settings from business logic.
    Tests can call ``set_test_settings(mock_settings)`` to inject a mock.
    """
    return Settings()


def set_test_settings(settings: Settings | None) -> None:
    """Inject a test Settings instance (or None to clear the override).

    Usage in tests::

        mock = create_mock_settings()
        set_test_settings(mock)
        # ... code that calls Settings() now gets the mock ...
        set_test_settings(None)  # cleanup
    """
    Settings._test_override = settings
