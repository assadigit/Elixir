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
from typing import Any, Optional

# V18.20.4.12 (W-b15): structured progress line — the wizard's live quality
# dashboard parses this JSON line (JSON-first) instead of regex-matching
# the human "📊 Progress:" wording; the human line stays byte-identical.
from core.common.progress_events import progress_json_line

# V18.20.4.11 (P2 / W-a7 partial): single source of truth for the legacy
# default-model literal (de-duplication only — value byte-identical).
# V18.2.21 (Phase 2.4-retry): consolidated retry decorator + typed exceptions.
# Replaces the 4 duplicated `for attempt in range(self.retries + 1)` loops
# in this module (_call_ollama_nonstreaming, _call_openai_compat, _call_claude,
# and the two sleeps inside _call_claude's 429 branch).
from core.models import ConversionRequest, SummaryResult
from core.summarisation import llm_dispatcher as _ld
from core.summarisation.additive_sections import SummarizerAdditiveMixin

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

# V18.20.4.7 (P5 / O-a2): additive-sections machinery mixin — the 5
# methods moved VERBATIM (byte-identical bodies) to
# core.summarisation.additive_sections.
# V0.18 (Phase 5.1, step 1): chapter-phase methods mixin — the recovery /
# deterministic-judge / postchecks / finalize phases of _summarize_inner moved
# VERBATIM here (byte-identical bodies; state threaded via explicit params).
from core.summarisation.chapter_phases import SummarizerChapterPhasesMixin

# V18.15.3 (Phase 5 Stage 3, Batch 4.5): 3-Tier coverage guarantee.
from core.summarisation.coverage_guarantee import apply_3tier_coverage as cg_apply_3tier_coverage

# V0.06 (rig audit F4-b): the source-scaled bullet budget (single source of
# truth: length_policy.bullet_target) as a hard-cap helper for the delegates.
from core.summarisation.length_policy import (
    bullet_cap as _lp_bullet_cap_mod,
)
from core.summarisation.length_policy import (
    count_source_words as _lp_count_source_words_mod,
)
from core.summarisation.prompt_builders import SummarizerPromptMixin
from core.summarisation.summarizer_init import SummarizerInitMixin


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

# V18.20.4.8 (P6 / O-a5): the single canonical structural-stopwords module
# (fixes W-a5's 3 drifting hand-curated copies; the class-level literal
# below is now an alias of this import — membership byte-identical).
from core.summarisation.structural_stopwords import STRUCTURAL_FUNCTION_WORDS

# V18.15.3 (Phase 5 Stage 3, Batch 4.1): structured (JSON) LLM output.
from core.summarisation.structured_llm import call_llm_structured as sl_call_llm_structured
from core.summarisation.summary_validator import (
    anti_false_precision_check as sv_anti_false_precision_check,
)
from core.summarisation.summary_validator import (
    compute_coverage as sv_compute_coverage,
)
from core.summarisation.summary_validator import (
    semantic_dedup_bullets as sv_semantic_dedup_bullets,
)
from core.summarisation.summary_validator import (
    verify_bullets as sv_verify_bullets,
)

# V18.11 (Phase 5 Stage 3, Batch 1.1): smart-truncation text utility.
from core.summarisation.text_utils_ext import smart_truncate as tue_smart_truncate

# V18.11 (Phase 5 Stage 3, Batch 2.3): dedicated thorough call + 3-attempt fallback.
# V18.20.4.7 (P5 / O-a2): thorough-theorist floor mixin (V18.20.3.13)
# — _thorough_theorist_floor moved VERBATIM to
# core.summarisation.thorough_theorist_floor.
from core.summarisation.thorough_theorist_floor import (
    SummarizerThoroughFloorMixin,
)

# V18.2.14 (B4): traceable error-handling helpers — replace silent
# ``except Exception: pass`` with ``log_swallow()`` so failures leave a
# permanent, searchable log trace (operation name + exc type + traceback).
from utils.error_trace import log_swallow
from utils.logging import get_main_logger
from utils.settings import Settings
from utils.token_counter import count_tokens

logger = get_main_logger()


class Summarizer(    SummarizerPromptMixin,
    SummarizerInitMixin,

    SummarizerChapterPhasesMixin,
    SummarizerAdditiveMixin,
    SummarizerThoroughFloorMixin,
):







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
                keywords = [
                    k
                    for k in keywords
                    if not any(entity.lower() in k.lower() for entity in ner_entities)
                ]
            return keywords
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # Fallback: old single-word method, V18.20.1.0 (D5) source-grounded.
        # Derive stopwords from the text's OWN frequency distribution: words
        # appearing >= 5% of the total word count are too common to be content
        # keywords (they're structural glue). Plus the tiny
        # _STRUCTURAL_FUNCTION_WORDS set (the/a/and/of... — grammatical, not
        # content). No hand-curated content word list.
        words = re.findall(r"\b[a-z]{6,}\b", text.lower())
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
            w
            for w, c in counts.items()
            if w not in self._STRUCTURAL_FUNCTION_WORDS and w not in _source_stopwords
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


    # V0.08 (P2 dead-code removal): the _build_thorough_followup delegate
    # (zero callers since the thorough followup call was replaced by the
    # dedicated thorough expansion) was deleted. The underlying
    # prompt_assembly.build_thorough_followup stays — it is a pinned live
    # export with its own characterization tests.



    # V18.20.4.7 (P5 / O-a2): _thorough_theorist_floor moved
    # VERBATIM to core/summarisation/thorough_theorist_floor.py
    # (SummarizerThoroughFloorMixin) — its call site below in
    # _summarize_inner is unchanged.


    # V0.08 (P2 dead-code removal): the _build_missing_keywords_reprompt
    # delegate was deleted — its only call site was the V18.6-era `if False`
    # academic-rigor gap-fill block removed above. The underlying
    # prompt_assembly.build_missing_keywords_reprompt stays (pinned live
    # export with characterization tests in test_prompt_assembly.py).


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
            _safe_h = re.sub(r"[^A-Za-z0-9_\-]+", "_", heading)[:60].strip("_")
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
                f"    ⚠️ V18.20.1.2: {label} checkpoint save failed (non-fatal): {_ckpt_e}",
                "WARNING",
            )
            logger.debug("%s checkpoint failed: %s: %s", label, type(_ckpt_e).__name__, _ckpt_e)

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
            self.log(
                "    ⚠️ V18.15.8.0: Cannot derive exec from thorough — thorough too short", "WARNING"
            )
            return ""
        self.log(
            "    📝 V18.15.8.0: Executive summary empty — deriving from thorough summary (dedicated system, 100% coverage)…",
            "INFO",
        )
        _prompt = self._build_exec_from_thorough_prompt(heading, thorough)
        _raw = self._call_llm_with_empty_retry(
            _prompt, model=self.primary_model, temperature=self.temperature, max_tokens=2048
        )
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
        m = re.search(r"<executive_summary>(.*?)</executive_summary>", _raw, re.DOTALL)
        if m:
            _exec = m.group(1).strip()
        else:
            # V18.16.0.1 (Fix 1): If no XML tag AND the output starts with CoT-like
            # phrases ("me to write", "synthesize", "Draft:", "Key elements"),
            # reject it — it's the model's reasoning, not a summary.
            _lower = _raw[:200].lower().strip()
            if any(
                _phrase in _lower
                for _phrase in (
                    "me to write",
                    "synthesize the key",
                    "draft:",
                    "key elements to capture",
                    "this in flowing prose",
                    "carefully. draft",
                )
            ):
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
            self.log(
                f"    ⚠️ V18.15.8.0: Exec-from-thorough too short ({_words} words < 50) — discarding",
                "WARNING",
            )
            return ""
        self.log(
            f"    ✅ V18.15.8.0: Executive summary derived from thorough ({_words} words)", "INFO"
        )
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
            if not sl or len(sl) < 20:
                continue
            if " " in kl:
                parts = [p for p in kl.split() if len(p) > 2]
                if parts and all(p in sl for p in parts):
                    return sent.strip()
            elif kl in sl:
                return sent.strip()
        return None

    def _targeted_gap_fill(self, heading, text, missing_keywords):
        if not missing_keywords:
            return []
        gap_pairs = []
        for kw in missing_keywords[:12]:
            sent = self._find_source_sentence(kw, text)
            if sent:
                gap_pairs.append((kw, sent))
        if not gap_pairs:
            return []
        self.log(
            f"    \U0001f50d Tier 2: targeted gap-fill for {len(gap_pairs)} missing concepts (parallel, focused calls)\u2026",
            "INFO",
        )
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
                    raw = self._call_cloud(
                        prompt, max_tokens=200, temperature=self.fusion_cloud_temperature
                    )
                else:
                    raw = self._call_fast_llm(prompt, max_tokens=200)
                if not raw:
                    return None
                raw = self._strip_thinking(raw).strip()
                if raw and not raw.startswith("- "):
                    raw = "- " + raw.lstrip("*-\u2022 ")
                if raw and len(raw) > 10 and "cannot" not in raw.lower()[:30]:
                    return raw
                return None
            except Exception:
                return None

        new_bullets = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_fill_one, pair): pair for pair in gap_pairs}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bp = future.result(timeout=120)
                        if bp:
                            new_bullets.append(bp)
                    except Exception as _e:
                        # V18.2.14 (B4): was silent ``pass`` — now traceable.
                        # WARNING level because a failed future means a lost
                        # gap-fill bullet — worth surfacing.
                        log_swallow("gap_fill_future_result", _e, level=logging.WARNING)
        except Exception:
            for pair in gap_pairs:
                bp = _fill_one(pair)
                if bp:
                    new_bullets.append(bp)
        if new_bullets:
            self.log(
                f"    \u2705 Tier 2: gap-filled {len(new_bullets)}/{len(gap_pairs)} concepts via focused LLM calls",
                "INFO",
            )
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
            for w in re.findall(r"[a-z0-9]+", (s or "").lower()):
                if len(w) <= 2:
                    continue
                if len(w) > 3 and w.endswith("s"):
                    out.add(w[:-1])
                out.add(w)
            return out

        combined_words = _tokens(
            " ".join(
                [
                    str(exec_sum or ""),
                    " ".join(str(b) for b in (bullets or [])),
                    str(thorough or ""),
                ]
            )
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
            for b in bullets or []:
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
        if not still_missing:
            return 0
        inserted = 0
        # V0.05 (rig audit F3-b — P1): the dedupe key is the NORMALIZED
        # SOURCE SENTENCE, not the framed excerpt string. The old key
        # (excerpt.lower()[:80]) was keyword-dominated — the frame
        # 'On "kw" — verbatim…' STARTS with the keyword, so different
        # keywords pointing at the SAME sentence each inserted their own
        # copy (the V0.04 rig shipped 9 excerpts for 4 unique sentences in
        # one chapter). The key extracts the quoted sentence tail instead.
        _norm_ws = re.compile(r"\s+")
        existing = set()
        for x in result.get("source_excerpts", []) or []:
            _body = str(x)
            _qm = re.search(r':\s*"(.*)"\s*$', _body, re.DOTALL)
            if _qm:
                _body = _qm.group(1)
            existing.add(_norm_ws.sub(" ", _body.lower().strip()))
        # V0.05 (F3-c): remediation unit = SENTENCE, not keyword. Keywords
        # resolving to the same source sentence are consolidated into ONE
        # excerpt (the frame lists them together) — overlapping
        # bigram/trigram keywords from one sentence must not each spawn
        # their own remediation.
        _by_sentence: dict[str, list[str]] = {}
        _sent_cache: dict[str, str] = {}
        for kw in still_missing:
            sent = self._find_source_sentence(kw, text)
            if not sent:
                continue
            _skey = _norm_ws.sub(" ", sent.lower().strip())
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
            sent = _norm_ws.sub(" ", sent).strip()
            if heading:
                _head = _norm_ws.sub(" ", str(heading).strip())
                _head_nn = re.sub(r"^\d+[.)]?\s*", "", _head).strip().lower()
                _sent_lc = sent.lower()
                if _head_nn and len(_head_nn) >= 12 and _sent_lc.startswith(_head_nn):
                    sent = sent[len(_head_nn) :].lstrip(" —–-:,.").strip()
                    _skey = _norm_ws.sub(" ", sent.lower().strip())
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
            if _skey in existing:
                continue
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
        )
        from core.summarisation.length_policy import (
            count_source_words as _lp_csw,
        )

        return cg_apply_3tier_coverage(
            heading,
            text,
            content,
            result,
            coverage,
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
            heading,
            text,
            result,
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
            heading,
            text,
            result,
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
            self.log(
                "    ℹ️ Self‑review using same model (no independent reviewer available).", "DEBUG"
            )

        # C8: send full source, truncated to fit the context window
        # Reserve 2000 tokens for the summary + prompt overhead
        max_src = max(self.request.summarisation_max_context_tokens - 2000, 8000)
        src_text = text[: max_src * 4]  # rough chars-per-token estimate

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
            model=review_model,
            temperature=self.temperature,
        )

    def _self_review_batched(
        self, heading: str, text: str, bullets: list, thorough: str
    ) -> str | None:
        """V13.45.4: Batched self-review — reviews bullets in chunks of 10.

        V18.11 (Phase 5 Stage 3, Batch 2.4): logic extracted verbatim to
        ``self_review.self_review_batched``. The ``request`` read
        (``summarisation_max_context_tokens``) is passed as an explicit
        primitive. Byte-for-byte identical behaviour (characterization
        tests in ``tests/test_self_review.py``). The ``thorough`` param is
        unused in the body but kept in the signature for call-site compat.
        """
        return sr_self_review_batched(
            heading,
            text,
            bullets,
            thorough,
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

    # ── Claude (Anthropic) API call ──────────────────────────────────

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

    def _score_bullet(
        self, bullet: str, concepts: list[str] | None = None, source_text: str = ""
    ) -> int:
        """V3.2.4 C1 / V10.14.0 (D3): Score a bullet 0-100 for quality.

        V18.11 (Phase 5 Stage 3, Batch 1.2): logic extracted verbatim to
        ``bullet_scorer.score_bullet`` (pure function — ZERO ``self`` deps in
        the original). This method is a one-line delegate. Byte-for-byte
        identical scoring (characterization tests in
        ``tests/test_bullet_scorer.py``; existing ``TestScoreBullet`` in
        ``tests/test_summarizer.py`` exercises the delegate).
        """
        return bs_score_bullet(bullet, concepts=concepts, source_text=source_text)

    def _filter_thinking_bullets(
        self, bullets: list, concepts: list[str] | None = None, source_text: str = ""
    ) -> list[str]:
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
            bullets,
            concepts=concepts,
            source_text=source_text,
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
            bullets,
            source_text,
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
            quarantine=getattr(self, "quarantine", None),
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
            prompt,
            model,
            temperature,
            max_tokens,
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
            heading,
            text,
            model,
            temp,
            with_cot=with_cot,
            max_tokens=max_tokens,
            concepts=concepts,
            callouts=callouts,
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
        prompt1 = self._build_chunked_prompt(
            heading, text, with_cot=with_cot, concepts=concepts, callouts=callouts, chunk=1
        )
        prompt2 = self._build_chunked_prompt(
            heading, text, with_cot=with_cot, concepts=concepts, callouts=callouts, chunk=2
        )

        # Call 1: exec + bullets + thorough
        self.log("    📦 Chunk 1/2: executive_summary + bullet_points + thorough_summary", "INFO")
        raw1 = self._call_llm_with_empty_retry(
            prompt1, model=model, temperature=temp, max_tokens=max_tokens
        )
        if not raw1:
            return None
        raw1 = self._strip_thinking(raw1)
        parsed1 = self._parse_response(raw1)
        self.log(
            f"    ✅ Chunk 1/2: exec={len(parsed1.get('executive_summary', ''))} chars, "
            f"bullets={len(parsed1.get('bullet_points', []))}, "
            f"thorough={len(parsed1.get('thorough_summary', ''))} chars",
            "INFO",
        )

        # Call 2: key_distinctions + theoretical_tensions
        self.log("    📦 Chunk 2/2: key_distinctions + theoretical_tensions", "INFO")
        raw2 = self._call_llm_with_empty_retry(
            prompt2, model=model, temperature=temp, max_tokens=max_tokens
        )
        if not raw2:
            # Chunk 2 failed — return chunk 1 with empty sections 4-5
            self.log(
                "    ⚠️ Chunk 2/2 failed — returning chunk 1 with empty distinctions/tensions",
                "WARNING",
            )
            parsed1["raw"] = raw1
            parsed1["model"] = model
            parsed1["temperature"] = temp
            return parsed1
        raw2 = self._strip_thinking(raw2)
        parsed2 = self._parse_response(raw2)
        self.log(
            f"    ✅ Chunk 2/2: distinctions={len(parsed2.get('key_distinctions', ''))} chars, "
            f"tensions={len(parsed2.get('theoretical_tensions', ''))} chars",
            "INFO",
        )

        # Merge: take sections 1-3 from chunk 1, sections 4-5 from chunk 2
        merged = parsed1.copy()
        merged["key_distinctions"] = parsed2.get("key_distinctions", "")
        merged["theoretical_tensions"] = parsed2.get("theoretical_tensions", "")
        merged["raw"] = (raw1 or "") + "\n\n---CHUNK---\n\n" + (raw2 or "")
        merged["model"] = model
        merged["temperature"] = temp
        return merged

    def _build_chunked_prompt(
        self,
        heading: str,
        text: str,
        with_cot: bool = True,
        concepts=None,
        callouts=None,
        chunk: int = 1,
    ) -> str:
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
        full_prompt = self._build_prompt(
            heading, text, with_cot=with_cot, concepts=concepts, callouts=callouts
        )
        # V0.05 (F9a): the chunk override carries the same output-selection
        # flags as the primary prompt — an unrequested section must not be
        # demanded back in through the chunking layer.
        return _pa_chunked(
            heading,
            text,
            full_prompt,
            with_cot=with_cot,
            chunk=chunk,
            include_executive=bool(getattr(self.request, "include_executive_summary", True)),
            include_thorough=bool(getattr(self.request, "include_thorough_summary", True)),
            include_keypoints=bool(getattr(self.request, "include_keypoints", True)),
        )

    def _merge_summaries(self, summaries: list[dict], source_text: str = "") -> dict:
        """Merge multiple summaries. M21 fix: take source_text as parameter
        instead of reading self._source_text (thread-safety)."""
        if not source_text:
            source_text = getattr(self, "_source_text", "")
        if not summaries:
            return {}
        bullet_counts: dict[str, int] = {}
        for s in summaries:
            for bp in s.get("bullet_points", []):
                norm = re.sub(r"[^\w\s]", "", bp.lower()).strip()
                bullet_counts[norm] = bullet_counts.get(norm, 0) + 1
        best_exec = max(
            summaries,
            key=lambda s: self._compute_coverage(source_text, s.get("executive_summary", "")),
        )
        best_thorough = max(
            summaries,
            key=lambda s: self._compute_coverage(source_text, s.get("thorough_summary", "")),
        )
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
                norm = re.sub(r"[^\w\s]", "", bp.lower()).strip()
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
            "bullet_points": all_bullets[: self.max_bullets_per_chapter],
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
            samples,
            source,
            heading,
            prompt_manager=self.prompt_manager,
            call_cloud=self._call_cloud,
            fusion_cloud_temperature=self.fusion_cloud_temperature,
            log=self.log,
            compute_coverage=self._compute_coverage,
        )

    def _multi_sample_summarize(
        self,
        heading: str,
        text: str,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
        n_samples: int = 3,
    ) -> dict | None:
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
            heading,
            text,
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
            self.log(
                f"    🎯 Pre-flight: identified {len(items)} must-have items: {items[:3]}…", "INFO"
            )
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
                        self.request.output_dir,
                        heading,
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

    def _thematic_synthesis(
        self, heading: str, merged_thorough: str, source_text: str
    ) -> str | None:
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
            raw = self._call_llm_with_empty_retry(
                prompt, temperature=self.temperature, max_tokens=2048
            )
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

    def _section_map_reduce(
        self,
        heading: str,
        text: str,
        concepts: list[str] | None = None,
        callouts: list[str] | None = None,
    ) -> dict | None:
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
            heading,
            text,
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
        # V0.18 (Phase 5.1, steps 2-4): the setup gate, the single-pass
        # primary acquisition, the thorough/bullet-expansion/coverage
        # phases, and the validation + content-judge phases moved VERBATIM
        # to chapter_phases (SummarizerChapterPhasesMixin). The strategy
        # decision and the map-reduce dispatch stay HERE (the P6 pins).
        _pr = self._phase_setup_and_gate(heading, content, book_context)
        if isinstance(_pr, SummaryResult):
            return _pr
        src_tokens, text, tok_in = _pr

        # ── V0.10 (P6): adaptive strategy decision ──────────────────────
        # ONE pure decision per chapter. decide_strategy never does I/O —
        # the LIVE window (request.summarisation_max_context_tokens, AFTER
        # the P5 registry raise), the output target, and the settings-
        # driven b4 threshold are read HERE and passed in. At window <=
        # 32768 this reproduces the legacy thresholds EXACTLY (map_reduce
        # iff src_tokens > MAP_REDUCE_THRESHOLD — byte-identical dispatch
        # for every <= 32k model); above it, a chapter that FITS (src <=
        # window - output - 700 - 512) goes single-pass — the 220k rig's
        # 40k-token chapters stop being shredded into 4k map-reduce
        # chunks (10+ LLM calls each).
        from core.summarisation.strategy import decide_strategy as _p6_decide_strategy
        from utils.settings import Settings as _P6Settings

        _p6_window = int(getattr(self.request, "summarisation_max_context_tokens", 32768) or 32768)
        _p6_output = int(getattr(self.request, "summarisation_max_output_tokens", 8192) or 8192)
        _p6_b4_threshold = int(_P6Settings().get("summarisation.b4_threshold_tokens", 12000))
        _p6_decision = _p6_decide_strategy(
            src_tokens,
            _p6_window,
            _p6_output,
            b4_threshold=_p6_b4_threshold,
            map_reduce_threshold=self.MAP_REDUCE_THRESHOLD,
        )
        self.log(
            f"    🧭 V0.10 (P6): strategy={_p6_decision.strategy} "
            f"(src={src_tokens:,} tok / window={_p6_window:,} / output={_p6_output:,})"
            f" — {_p6_decision.reason}",
            "INFO",
        )

        if _p6_decision.strategy == "map_reduce":
            self.log(
                f"    🗺️ Chapter too large for single call ({src_tokens:,} tokens) — "
                f"switching to Map-Reduce ({_p6_decision.map_chunk_tokens:,}-token chunks, "
                f"{int(_p6_decision.overlap * 100)}% overlap)",
                "INFO",
            )
            raw, combined_tokens = self._map_reduce_summarize(
                heading,
                content,
                map_chunk_tokens=_p6_decision.map_chunk_tokens,
                map_chunk_overlap=_p6_decision.overlap,
            )
            tok_in = combined_tokens
            if not raw:
                return SummaryResult(
                    chapter_heading=heading,
                    executive_summary="[Error: Map-Reduce failed]",
                    bullet_points=[],
                    thorough_summary="",
                    success=False,
                    error_msg="Map-Reduce returned no response",
                    input_tokens=tok_in,
                    output_tokens=0,
                )
            parsed = self._parse_response(raw)
        else:
            _pr = self._phase_single_pass_primary(
                heading,
                content,
                concepts,
                callouts,
                _p6_b4_threshold,
                _p6_decide_strategy,
                _p6_output,
                _p6_window,
            )

            if isinstance(_pr, SummaryResult):
                return _pr

            _pipeline, _pstate, coverage, parsed, text, tok_in = _pr

        (
            _bp_hi_lp,
            _bp_lo_lp,
            _inc_exec_lp,
            _inc_kp_lp,
            _inc_thorough_lp,
            _src_words_lp,
            _th_hi_lp,
            bullets,
            coverage,
            exec_sum,
            final_summary,
            thorough,
        ) = self._phase_thorough_and_coverage(heading, content, text, parsed)

        _pr = self._phase_validation_and_judge(
            heading,
            content,
            concepts,
            tok_in,
            coverage,
            exec_sum,
            bullets,
            thorough,
            final_summary,
            _pipeline,
            _pstate,
        )
        if isinstance(_pr, SummaryResult):
            return _pr
        bullets, exec_sum, thorough = _pr

        # V0.18 (Phase 5.1, step 1): the recovery / deterministic-judge /
        # postchecks / finalize phases moved VERBATIM to
        # core.summarisation.chapter_phases (SummarizerChapterPhasesMixin).
        bullets, exec_sum, thorough = self._phase_recovery_pass(
            heading, content, parsed, exec_sum, bullets, thorough
        )
        thorough = self._phase_deterministic_judge(heading, content, exec_sum, bullets, thorough)
        bullets, exec_sum, thorough = self._phase_postchecks_and_floors(
            heading,
            content,
            parsed,
            exec_sum,
            bullets,
            thorough,
            _inc_thorough_lp,
            _inc_kp_lp,
            _src_words_lp,
            _th_hi_lp,
            _bp_lo_lp,
            _bp_hi_lp,
        )
        return self._phase_finalize(
            heading,
            parsed,
            exec_sum,
            bullets,
            thorough,
            final_summary,
            tok_in,
            _inc_exec_lp,
            _inc_thorough_lp,
            _inc_kp_lp,
        )

    # ─────────────────────────────────────────────────────────────────────────

    def _recover_quarantined(self, bullets: list[str], source_text: str) -> list[str]:
        """Re-scan the quarantine and resurrect high-overlap bullets.

        V18.15 (Phase 5 Stage 3, Batch 3.1): logic extracted verbatim to
        ``quarantine_recovery.recover_quarantined``. This method is a thin
        delegate. Byte-for-byte identical behaviour (characterization tests
        in ``tests/test_quarantine_recovery.py``).
        """
        return qr_recover_quarantined(
            bullets,
            source_text,
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
            heading,
            content,
            bullets,
            concepts,
            exec_summary,
            thorough_summary,
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

    def _map_reduce_summarize(
        self,
        heading: str,
        content: str,
        *,
        map_chunk_tokens: int | None = None,
        map_chunk_overlap: float | None = None,
    ) -> tuple[str | None, int]:
        """Map-Reduce summarization for very large chapters (40k+ tokens).

        V18.11 (Phase 5 Stage 3, Batch 2.1): logic extracted verbatim to
        ``map_reduce.map_reduce_summarize``. The two ``request`` reads
        (``input_path.stem`` for cache-key uniqueness,
        ``summarisation_cache_enabled`` for the V10.33.0 cache toggle)
        are passed as explicit primitives. The MAP_CHUNK_* / MAP_MINI_WORDS
        instance attrs are passed as params. Byte-for-byte identical output
        (characterization tests in ``tests/test_map_reduce.py``).

        V0.10 (P6): the chunk geometry now flows from the strategy
        decision — at legacy windows the caller passes decide_strategy's
        values, which are EXACTLY the instance constants (4000 / 0.10),
        so behavior is byte-identical to pre-P6. At windows > 32768 the
        chunk scales (clamp(window // 8, 4000, 32000)) — the 220k rig
        maps 27,500-token chunks instead of 4k ones (7x fewer map calls).
        The instance constants remain the fallback (and the parity pin).

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
            _budget = (
                max(300, int(_remaining))
                if _budget <= 0
                else min(_budget, max(300, int(_remaining)))
            )
        return mr_map_reduce_summarize(
            heading,
            content,
            primary_model=self.primary_model,
            cache_dir=self.cache_dir,
            input_path_stem=self.request.input_path.stem,
            cache_enabled=bool(getattr(self.request, "summarisation_cache_enabled", False)),
            temperature=self.temperature,
            map_chunk_tokens=map_chunk_tokens
            if map_chunk_tokens is not None
            else self.MAP_CHUNK_TOKENS,
            map_chunk_overlap=map_chunk_overlap
            if map_chunk_overlap is not None
            else self.MAP_CHUNK_OVERLAP,
            map_mini_words=self.MAP_MINI_WORDS,
            build_prompt=self._build_prompt,
            call_llm=self._call_llm,
            log=self.log,
            map_phase_budget_sec=_budget,
        )

    def _prepare_text(self, text: str) -> str:
        if self.provider == "freellmapi":
            max_tok = (
                self.request.summarisation_max_context_tokens
                - self.request.summarisation_max_output_tokens
                - 700
            )
        elif self.provider == "claude":
            max_tok = (
                min(self.request.summarisation_max_context_tokens, 200000) - 2000
            )  # Claude has 200k context
        elif self.provider in ("openrouter", "openai", "openai_compatible"):
            max_tok = self.cloud_max_tokens - 2000
        else:
            max_tok = (
                self.request.summarisation_max_context_tokens
                - self.request.summarisation_max_output_tokens
                - 700
            )
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
                            chap["heading"],
                            chap["content"],
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
                            idx,
                            total,
                            chap["heading"][:60],
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
                if (
                    self.is_local
                    and self.local_chapter_deadline > 0
                    and _chap_elapsed > self.local_chapter_deadline
                ):
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
                        idx,
                        total,
                        _chap_elapsed,
                        self.local_chapter_deadline,
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
                    self.log(
                        f"❌ Chapter {idx}/{total}: {chap['heading'][:40]}… FAILED: {_result.error_msg}",
                        "ERROR",
                    )
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
                    chap["heading"],
                    chap["content"],
                    concepts=chap.get("concepts"),
                    callouts=chap.get("callouts"),
                )
                return idx, result
            except Exception as e:
                self.log(f"  ❌ Chapter {idx + 1} failed: {e}", "ERROR")
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
                    progress_callback(completed / total, f"Chapter {idx + 1}/{total} – complete")
                # log FAILED vs SUCCESS correctly — was always
                # logging "✅ complete" even when the chapter failed, which
                # was misleading (the user saw green checkmarks for failed chapters).
                if result.success:
                    self.log(
                        f"✅ Chapter {idx + 1}/{total}: {result.chapter_heading[:40]}… complete",
                        "INFO",
                    )
                else:
                    self.log(
                        f"❌ Chapter {idx + 1}/{total}: {result.chapter_heading[:40]}… FAILED: {result.error_msg}",
                        "ERROR",
                    )
                # V18.20.3.0: incremental checkpoint — fire as each parallel
                # future completes (chapters[idx] carries the chapter dict).
                if chapter_done_callback is not None:
                    try:
                        chapter_done_callback(idx + 1, result, chapters[idx])
                    except Exception as _cb_e:
                        self.log(
                            f"  ⚠️ V18.20.3.0 chapter checkpoint callback "
                            f"failed (chapter {idx + 1}): {_cb_e!r} — continuing.",
                            "WARNING",
                        )
                # check cancel — cancel remaining futures
                if cancel_event and cancel_event.is_set():
                    self.log(
                        "  ⏹️ Summarisation cancelled by user — stopping pending chapters.",
                        "WARNING",
                    )
                    for f in futures:
                        f.cancel()
                    break

        # Ensure all results are SummaryResult (not None)
        final_results = []
        for i, r in enumerate(results):
            if r is None:
                # Fallback for any missing results
                self.log(
                    f"  ⚠️ Chapter {i + 1} returned None – creating error placeholder.", "WARNING"
                )
                final_results.append(
                    SummaryResult(
                        chapter_heading=chapters[i]["heading"],
                        executive_summary="[Error: No result]",
                        bullet_points=[],
                        thorough_summary="",
                        success=False,
                        error_msg="No result returned from summarisation",
                    )
                )
            else:
                final_results.append(r)

        return final_results

    def build_book_summary(
        self, summaries: list[SummaryResult], book_title: str, stats: dict | None = None
    ) -> str:
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
        lines = [
            f"# Book Summary: {book_title}",
            "",
            f"> Provider: {self.provider} | Language: {self.language} | Chapters: {len(summaries)} | {time.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
        ]
        seen = set()
        all_bullets = []
        for s in summaries:
            for bp in s.bullet_points:
                norm = re.sub(r"[^\w\s]", "", bp.lower()).strip()
                if norm and norm not in seen and len(bp) > 10:
                    seen.add(norm)
                    all_bullets.append(bp)
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
                lines += [
                    f"### {idx}. {s.chapter_heading}",
                    "",
                    f"⚠️ Summary failed: {s.error_msg or 'unknown error'}",
                    "",
                ]
                continue
            _inc_exec_s = getattr(s, "include_executive_summary", True)
            _inc_kp_s = getattr(s, "include_keypoints", True)
            _inc_th_s = getattr(s, "include_thorough_summary", True)
            if _inc_exec_s and (s.executive_summary or "").strip():
                lines += [f"### {idx}. {s.chapter_heading}", "", s.executive_summary.strip(), ""]
            else:
                lines += [f"### {idx}. {s.chapter_heading}", ""]
            if _inc_kp_s and s.bullet_points:
                lines.append("**Key takeaways:**")
                for bp in s.bullet_points:
                    bp_str = str(bp) if not isinstance(bp, str) else bp
                    lines.append(f"- {bp_str}")
                lines.append("")
            if _inc_th_s and s.thorough_summary and s.thorough_summary.strip():
                lines += [
                    "<details><summary>Detailed summary</summary>",
                    "",
                    s.thorough_summary,
                    "",
                    "</details>",
                    "",
                ]
        return "\n".join(lines)
