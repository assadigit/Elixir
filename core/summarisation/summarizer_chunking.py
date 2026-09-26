"""V0.4.19 — moved VERBATIM from summarizer.py (de-monolithization step 9/10)
following the house mixin pattern.

The chunked-output + map-reduce machinery moved out of the ~2.7k-line
``summarizer.py`` monolith into this module, re-homed via the mixin
pattern — ``Summarizer`` inherits ``SummarizerChunkingMixin`` at the END
of its bases list, so every ``self.<attr>`` / ``self.<method>`` reference
resolves exactly as before through the MRO and external importers of
``Summarizer`` are unaffected (same module, same name).

VERBATIM CONTRACT (the house decomposition pattern): every method body is
byte-identical to summarizer.py immediately before this move — only this
module's imports (the re-homed module-level dependencies) and docstring
are new.

What lives here (moved VERBATIM, in the original relative order):

  - ``_chunked_summarize``    — V0.3 (master-summary architecture): the
    3-call sequential pipeline (master summary -> derive bullets -> derive
    exec).
  - ``_build_chunked_prompt`` — V18.3.4 (E3) chunked prompt builder
    (delegates to ``prompt_assembly.build_chunked_prompt``; the caller
    builds the full prompt via ``self._build_prompt``).
  - ``_merge_summaries``      — multi-sample merge (M21 fix: source_text
    as a parameter; rapidfuzz fuzzy dedup with exact-match fallback).
  - ``_section_map_reduce``   — V3.3.0 B4 delegate to
    ``map_reduce.section_map_reduce`` (~15 self-deps as explicit kwargs).
  - ``_map_reduce_summarize`` — V18.11 delegate to
    ``map_reduce.map_reduce_summarize`` (V0.10 P6 decision-driven chunk
    geometry + V18.20.4.10 P0-d map-phase wall-clock budget).

NOT moved (stays in summarizer.py): ``_summarize_inner`` (the strategy
dispatch + the V0.3.1 map-reduce master-summary derivation stay with the
orchestrator — pinned by ``_NOT_MOVED_NEIGHBOURS``), ``_prepare_text`` /
``_smart_truncate`` and the B3 multi-sample delegates.
"""

from __future__ import annotations

import logging
import re
import time

# V18.11 (Phase 5 Stage 3, Batch 2.1 + 2.5): map-reduce summarization.
from core.summarisation.map_reduce import (
    map_reduce_summarize as mr_map_reduce_summarize,
)
from core.summarisation.map_reduce import (
    section_map_reduce as mr_section_map_reduce,
)

logger = logging.getLogger(__name__)


class SummarizerChunkingMixin:
    """Chunked/map-reduce machinery for :class:`Summarizer` (see the module
    docstring). Method bodies are byte-identical to summarizer.py's."""

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
        """V0.3 (master-summary architecture): 3-call sequential pipeline.

        V18.3.4 (E3) was a 2-call split by section TYPE (exec+bullets+thorough /
        distinctions+tensions). V0.3 restructures this to split by DEPTH:
          Call 1 (Master Summary): produce the comprehensive thorough summary
          Call 2 (Bullets): derive bullet points FROM the master summary
          Call 3 (Exec): derive the executive summary FROM the master + bullets

        This is the owner's study method: read → summarize (master) → distill
        (bullets) → key takeaway (exec). Each call has a focused, smaller
        output → less truncation risk, less CoT risk. The bullets and exec
        are guaranteed consistent with the thorough (derived from it).

        Additive sections (key_distinctions + theoretical_tensions) stay as
        the existing followup call in _ensure_additive_sections.

        Returns a dict with thorough_summary, bullet_points, executive_summary
        (key_distinctions and theoretical_tensions are empty — filled later by
        _ensure_additive_sections).
        """
        from core.summarisation.prompt_manager import PromptManager

        _pm = PromptManager()

        # ── Call 1: Master Summary (the comprehensive thorough) ────────
        # This call asks for ONLY the thorough summary — the full output
        # budget for one section → no truncation from 5-section overload.
        self.log("    📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)", "INFO")
        from core.summarisation.length_policy import bullet_target as _bt

        _src_words = len(text.split())
        _bp_lo, _bp_hi = _bt(_src_words)
        _bullet_range = f"{_bp_lo}-{_bp_hi}"
        master_prompt = _pm.render_template(
            "summarisation/master_summary",
            heading=heading,
            # V0.3.1: use the ACTUAL available context space, not a hardcoded
            # 40000 chars. The available source space = (num_ctx - output_budget
            # - margin) * ~4 chars/token. For a 16000-tok ctx with 8192 output
            # and 700 margin: (16000 - 8192 - 700) * 4 = 28432 chars ≈ 7108 tok.
            # For a 32768-tok ctx: (32768 - 8192 - 700) * 4 = 95504 chars.
            text=text[
                : max(
                    (
                        getattr(self.request, "summarisation_max_context_tokens", 16000)
                        - max_tokens
                        - 700
                    )
                    * 4,
                    4000,
                )
            ],
        )
        raw1 = self._call_llm_with_empty_retry(
            master_prompt, model=model, temperature=temp, max_tokens=max_tokens
        )
        if not raw1:
            self.log(
                "    ⚠️ V0.3 Call 1/3 (master summary) returned empty — falling back", "WARNING"
            )
            return None
        raw1 = self._strip_thinking(raw1)
        # Extract the <thorough_summary> section
        import re as _re

        _m = _re.search(r"<thorough_summary>(.*?)</thorough_summary>", raw1, _re.DOTALL)
        master_summary = _m.group(1).strip() if _m else raw1.strip()
        if len(master_summary.split()) < 50:
            self.log(
                f"    ⚠️ V0.3 Call 1/3 (master summary) too short ({len(master_summary.split())} words) — falling back",
                "WARNING",
            )
            return None
        self.log(
            f"    ✅ V0.3 Call 1/3: master summary = {len(master_summary.split())} words, "
            f"{len(master_summary)} chars",
            "INFO",
        )

        # V0.5.8: the V0.5.6 fused-path glossary extraction was REMOVED.
        # The master-summary prompt no longer asks for <name_glossary> (the
        # V0.5.7 revert), so parsing raw1 for it always returned empty + logged
        # the noisy "no <name_glossary> block parsed from master summary".
        # The V0.5.7 separate call (extract_glossary_via_llm in primary_call.py)
        # now handles glossary extraction via a DEDICATED LLM call + the
        # set_chapter_glossary side-channel. This fused path is dead code.
        source_glossary: dict[str, list] = {"names": [], "dates": [], "terms": []}

        # ── Call 2: Bullet Points derivation FROM the master summary ──
        # The input is the master summary (much smaller than the full source)
        # → less context, less CoT risk, faster generation.
        self.log("    📦 V0.3 Call 2/3: Derive bullet points from master summary", "INFO")
        bullets_prompt = _pm.render_template(
            "summarisation/derive_bullets",
            heading=heading,
            master_summary=master_summary[:20000],
            bullet_range=_bullet_range,
        )
        raw2 = self._call_llm_with_empty_retry(
            bullets_prompt, model=model, temperature=temp, max_tokens=2048
        )
        bullets: list[str] = []
        if raw2:
            raw2 = self._strip_thinking(raw2)
            _bm = _re.search(r"<bullet_points>(.*?)</bullet_points>", raw2, _re.DOTALL)
            bullets_text = _bm.group(1).strip() if _bm else raw2.strip()
            bullets = [
                line.strip().lstrip("- ").strip()
                for line in bullets_text.split("\n")
                if line.strip().startswith("-")
            ]
        self.log(
            f"    ✅ V0.3 Call 2/3: {len(bullets)} bullets derived from master summary",
            "INFO",
        )

        # ── Call 3: Executive Summary derivation FROM master + bullets ─
        # The input is the master summary + bullets → small, focused.
        self.log("    📦 V0.3 Call 3/3: Derive executive summary from master + bullets", "INFO")
        _bullets_text = "\n".join(f"- {b}" for b in bullets) if bullets else "(no bullets)"
        exec_prompt = _pm.render_template(
            "summarisation/derive_exec",
            heading=heading,
            master_summary=master_summary[:12000],
            bullets=_bullets_text[:4000],
        )
        raw3 = self._call_llm_with_empty_retry(
            exec_prompt, model=model, temperature=temp, max_tokens=1024
        )
        exec_summary = ""
        if raw3:
            raw3 = self._strip_thinking(raw3)
            _em = _re.search(r"<executive_summary>(.*?)</executive_summary>", raw3, _re.DOTALL)
            exec_summary = _em.group(1).strip() if _em else raw3.strip()
        if not exec_summary:
            # Fallback: derive exec from the first paragraph of the master summary
            exec_summary = master_summary.split("\n")[0][:2000]
        self.log(
            f"    ✅ V0.3 Call 3/3: exec summary = {len(exec_summary.split())} words",
            "INFO",
        )

        # ── Merge: return all 3 sections (additive sections filled later) ─
        merged = {
            "executive_summary": exec_summary,
            "bullet_points": bullets,
            "thorough_summary": master_summary,
            "key_distinctions": "",  # filled by _ensure_additive_sections
            "theoretical_tensions": "",  # filled by _ensure_additive_sections
            # V0.5.6 Phase 0.5: the source glossary parsed from Call 1/3's
            # <name_glossary> block. Flows through to SummaryResult for the
            # verification LAYER (coverage ground truth). Empty dict = the
            # LLM didn't emit the block (fail-open — never blocks the
            # master-summary).
            "source_glossary": source_glossary,
            "raw": (raw1 or "")
            + "\n\n---V0.3-MASTER---\n\n"
            + (raw2 or "")
            + "\n\n---V0.3-BULLETS---\n\n"
            + (raw3 or ""),
            "model": model,
            "temperature": temp,
        }
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
        from core.summarisation.stage_overlap import lever_enabled as _p6_lever_enabled
        from core.summarisation.stage_overlap import lever_workers as _p6_lever_workers

        _p6_map_workers = _p6_lever_workers() if _p6_lever_enabled("map") else 1
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
            parallel_max_workers=_p6_map_workers,
        )
