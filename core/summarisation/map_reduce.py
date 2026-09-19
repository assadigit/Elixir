"""V18.11 (Phase 5 Stage 3, Batch 2.1): Map-Reduce summarization.

Extracted verbatim from ``Summarizer._map_reduce_summarize`` (god-class
decomposition Stage 3). This handles very large chapters (40k+ tokens) by
splitting the content into overlapping chunks, summarising each ("map" phase),
then combining the mini-summaries into a final summary ("reduce" phase).

**Extraction map**:

| Summarizer method (old) | map_reduce function (new) | self deps                                 |
|------------------------|---------------------------|-------------------------------------------|
| ``_map_reduce_summarize`` | ``map_reduce_summarize`` | ``primary_model``, ``cache_dir``, ``request.input_path.stem``, ``request.summarisation_cache_enabled``, ``temperature``, ``MAP_CHUNK_TOKENS``, ``MAP_CHUNK_OVERLAP``, ``MAP_MINI_WORDS``, ``_build_prompt``, ``_call_llm``, ``log`` |

Each function is extracted VERBATIM — the only change is ``self.X`` → a named
parameter. The Summarizer method now delegates to this function.

The two ``request`` reads (``input_path.stem`` for the cache-key uniqueness,
``summarisation_cache_enabled`` for the V10.33.0 cache toggle) are passed as
explicit primitives (``input_path_stem: str``, ``cache_enabled: bool``) rather
than the whole ``request`` object — keeps the function testable without
constructing a full ``ConversionRequest``.

**V18.6.3 crash mitigation**: Uses EXPLICIT PARAMETERS (not a context object).
Matches the proven Phase 4 + Phase 5 + Batch 1 pattern.

Characterization tests: ``tests/test_map_reduce.py`` captures canned inputs →
golden outputs with mocked ``build_prompt`` / ``call_llm`` / cache filesystem.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path

# V18.20.2.0 (SWOT A5): shared Qwen-family /no_think injection for the
# direct call_llm sites below (they bypass _call_llm_with_empty_retry's
# V18.2.41 injection). Import is safe — filter_thinking has no dependency
# on this module (no import cycle).
from core.summarisation.filter_thinking import qwen_no_think
from utils.atomic_io import atomic_write_text
from utils.error_trace import log_swallow
from utils.token_counter import count_tokens

# Type aliases (duck-typed — matches the established convention).
LogCallback = Callable[[str, str], None]
BuildPromptFn = Callable[..., str]
CallLlmFn = Callable[..., str | None]
RecoverVramFn = Callable[..., None]
SummarizeWithModelFn = Callable[..., dict | None]

logger = logging.getLogger(__name__)


def _noop_log(msg: str, level: str = "INFO") -> None:
    """Default no-op log callback when none is provided."""
    pass


# ── V18.20.2.0 (SWOT A29): map-reduce cache management ─────────────────────

# Cap on cached mini-summary files per cache dir. The V18.20.1.3 cache grew
# forever (one file per chapter ever processed, never evicted).
_MAPREDUCE_CACHE_MAX_ENTRIES = 256


def _evict_mapreduce_cache(
    cache_dir: Path, max_entries: int = _MAPREDUCE_CACHE_MAX_ENTRIES
) -> None:
    """V18.20.2.0 (SWOT A29): keep at most ``max_entries`` mapreduce_* cache
    files in ``cache_dir``, evicting the oldest by mtime. Best-effort — any
    filesystem error is swallowed (the cache is an optimization, never a
    correctness dependency)."""
    try:
        entries = sorted(
            (p for p in cache_dir.glob("mapreduce_*.mini_summaries.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        for stale in entries[: max(0, len(entries) - max_entries)]:
            try:
                stale.unlink()
                logger.debug("evicted stale map-reduce cache entry %s", stale.name)
            except OSError:
                pass  # best-effort eviction — a locked file must never break summarisation
    except Exception as _e:
        logger.debug("map-reduce cache eviction skipped: %s: %s", type(_e).__name__, _e)


# ── map_reduce_summarize (extracted verbatim) ──────────────────────────────


def map_reduce_summarize(
    heading: str,
    content: str,
    *,
    primary_model: str,
    cache_dir: Path,
    input_path_stem: str,
    cache_enabled: bool,
    temperature: float,
    map_chunk_tokens: int,
    map_chunk_overlap: float,
    map_mini_words: int,
    build_prompt: BuildPromptFn,
    call_llm: CallLlmFn,
    log: LogCallback | None = None,
    map_phase_budget_sec: int = 0,
) -> tuple[str | None, int]:
    """Map-Reduce summarization for very large chapters.

    Extracted verbatim from ``Summarizer._map_reduce_summarize``. The only
    changes are ``self.X`` → named parameters. The chunk-overlap algorithm,
    the cache-key hash composition, the V10.33.0 cache-enabled toggle, and
    the map→reduce prompt composition are byte-for-byte identical.

    Returns ``(reduce_response, combined_tokens)`` where ``reduce_response``
    is the LLM's final reduced summary (or ``None`` if all map chunks failed)
    and ``combined_tokens`` is the token count of the combined mini-summaries
    fed to the reduce step.

    V18.20.4.10 (P0-d) adds two safety rails, both backward compatible:

    - ``map_phase_budget_sec`` — a hard wall-clock budget for the whole map
      phase (0 = disabled). When exceeded mid-loop the phase STOPS and the
      chapter fails LOUDLY (``None`` return + WARNING) instead of grinding
      for hours: on a CPU-offloaded 27B quant each 4k-token chunk can take
      5-15 min, so a whole-book segment (the V18.20.4.9 '97 Things' bug:
      675,817 tokens → 188 chunks) meant DAYS of silent map calls.
    - A liveness/timing log around the chunking pass, so any future
      pre-chunk stall is visible with timestamps in the conversion log.
    """
    log = log or _noop_log
    _phase_start = time.monotonic()
    # C5 fix: include a content hash in the cache key so changes to the
    # source (different edition, different OCR, different page range)
    # invalidate the cache.  Also include the model name + prompt version.
    # V18.20.2.0 (SWOT A29): the hash now covers the FULL content (sha256),
    # not just the first 500 chars — two chapters with the same heading and
    # a shared 500-char prefix (frontmatter / running header) collided and
    # restored the WRONG mini-summaries, and edits past char 500 never
    # invalidated the cache. The key-format change intentionally invalidates
    # existing on-disk entries (the cache is opt-in, default OFF — regenerating
    # is the correct behaviour after this fix).
    content_hash = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()[:16]
    model_tag = (primary_model or "unknown")[:20]
    cache_key = hashlib.md5(
        f"{heading}_{input_path_stem}_{content_hash}_{model_tag}".encode()
    ).hexdigest()
    cache_file = cache_dir / f"mapreduce_{cache_key}.mini_summaries.md"
    # V10.33.0 (Sprint 5.5): respect the summarisation_cache_enabled setting.
    # Before V10.33.0 this was a dead setting — the cache was always read
    # when the file existed, regardless of the user's preference.  Now
    # the cache is only used when the setting is True (default: False).
    if cache_enabled and cache_file.exists():
        try:
            combined = cache_file.read_text(encoding="utf-8")
            lines = combined.splitlines()
            start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("# Chapter:"):
                    start_idx = i + 1
                    break
            combined = "\n".join(lines[start_idx:]).strip()
            if combined:
                log(
                    "    \U0001f4be Found cached mini\u2011summaries \u2013 skipping Map phase",
                    "INFO",
                )
                combined_tokens = count_tokens(combined)
                reduce_prompt = build_prompt(
                    heading,
                    f"[Sequential summaries covering the complete chapter]\n\n{combined}",
                    with_cot=True,
                )
                # V18.20.2.0 (SWOT A5): direct call_llm site — inject /no_think
                # for Qwen-family models.
                response = call_llm(
                    qwen_no_think(reduce_prompt, primary_model),
                    model=primary_model,
                    temperature=temperature,
                )
                return response, combined_tokens
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    log(
        f"    \U0001f5fa\ufe0f Map phase chunking {count_tokens(content):,} tokens "
        f"into ~{map_chunk_tokens:,}-token chunks…",
        "DEBUG",
    )
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks = []
    overlap_tokens = int(map_chunk_tokens * map_chunk_overlap)
    current = []
    used = 0
    for para in paragraphs:
        pt = count_tokens(para)
        if used + pt > map_chunk_tokens and current:
            chunks.append("\n\n".join(current))
            overlap_paras = []
            overlap_used = 0
            for p in reversed(current):
                ot = count_tokens(p)
                if overlap_used + ot > overlap_tokens:
                    break
                overlap_paras.insert(0, p)
                overlap_used += ot
            current = overlap_paras
            used = overlap_used
        current.append(para)
        used += pt
    if current:
        chunks.append("\n\n".join(current))

    log(
        f"    \U0001f5fa\ufe0f Map\u2011Reduce: {len(chunks)} chunks (overlap ~{overlap_tokens} tokens)",
        "INFO",
    )

    # V18.20.4.10 (P0-d): chunk-count sanity. A chapter needing more than
    # ~50 map chunks is a SEGMENTATION failure (a whole-book segment), not
    # a summarization workload — at 5-15 min/chunk on a CPU-offloaded quant
    # that is 4-12 HOURS. Proceed (backward compatible) but say it loudly;
    # the wall-clock budget below is the hard stop.
    if len(chunks) > 50:
        log(
            f"    \u26a0\ufe0f Map\u2011Reduce needs {len(chunks)} chunks \u2014 this chapter is "
            f"OVERSIZED (segmentation should have split it). At 5-15 min/chunk "
            f"on a small-VRAM rig this phase can take {len(chunks) * 5}-{len(chunks) * 15} "
            f"minutes. The map-phase budget will stop it.",
            "WARNING",
        )

    mini_summaries = []
    for idx, chunk in enumerate(chunks, 1):
        # V18.20.4.10 (P0-d): wall-clock budget for the whole map phase.
        # Checked BEFORE each chunk so a stuck/slow phase is bounded by
        # budget + one HTTP timeout, never unbounded. Failing loudly beats
        # silently producing a partial summary (honesty machinery rule).
        if map_phase_budget_sec > 0 and (time.monotonic() - _phase_start) > map_phase_budget_sec:
            log(
                f"    \u26a0\ufe0f Map\u2011Reduce ABORTED: map phase exceeded its "
                f"{map_phase_budget_sec}s budget after {len(mini_summaries)}/{len(chunks)} "
                f"chunks \u2014 chapter '{heading[:40]}' will be marked FAILED instead "
                f"of silently grinding (raise local.map_phase_max_seconds to "
                f"allow longer map phases).",
                "WARNING",
            )
            return None, 0
        prompt = f'Summarize the following excerpt from chapter "{heading}" in exactly {map_mini_words} words. Focus on concrete facts, arguments, and named concepts. Output ONLY the summary text, no preamble.\n\n{chunk}'
        log(
            f"    \U0001f5fa\ufe0f Map chunk {idx}/{len(chunks)} ({count_tokens(chunk):,} tok)\u2026",
            "INFO",
        )
        # V18.20.2.0 (SWOT A5): direct call_llm site — inject /no_think for
        # Qwen-family models.
        response = call_llm(
            qwen_no_think(prompt, primary_model),
            model=primary_model,
            temperature=temperature * 0.7,
        )
        if response:
            mini_summaries.append(f"[Chunk {idx}/{len(chunks)}]\n{response.strip()}")
        else:
            log(f"    \u26a0\ufe0f Map chunk {idx} failed \u2013 skipped", "WARNING")

    if not mini_summaries:
        return None, 0

    combined = "\n\n".join(mini_summaries)
    combined_tokens = count_tokens(combined)

    try:
        # V10.33.0 (Sprint 5.5): only write cache when enabled
        # V18.20.2.0 (SWOT A29): atomic write (a crash mid-write must never
        # leave a truncated mini-summaries file that a later run would
        # restore) + size-capped eviction of the oldest entries.
        if cache_enabled:
            atomic_write_text(
                cache_file,
                f"# Map-Reduce Mini-Summaries\n# Chapter: {heading}\n# Chunks: {len(mini_summaries)}\n\n{combined}",
                encoding="utf-8",
            )
            _evict_mapreduce_cache(cache_dir)
            log(f"    \U0001f4be Mini-summaries cached \u2192 {cache_file.name}", "DEBUG")
    except Exception as e:
        log(f"    \u26a0\ufe0f Could not cache: {e}", "WARNING")

    log(
        f"    \U0001f504 Reduce phase: combining {len(mini_summaries)} mini\u2011summaries "
        f"({combined_tokens:,} tokens) into the final summary\u2026",
        "INFO",
    )
    reduce_prompt = build_prompt(
        heading,
        f"[Sequential summaries covering the complete chapter]\n\n{combined}",
        with_cot=True,
    )
    # V18.20.2.0 (SWOT A5): direct call_llm site — inject /no_think for
    # Qwen-family models.
    response = call_llm(
        qwen_no_think(reduce_prompt, primary_model),
        model=primary_model,
        temperature=temperature,
    )
    return response, combined_tokens


__all__ = [
    "map_reduce_summarize",
    "section_map_reduce",
    "_evict_mapreduce_cache",
    "LogCallback",
    "BuildPromptFn",
    "CallLlmFn",
]


# ── section_map_reduce (extracted verbatim) ────────────────────────────────


def section_map_reduce(
    heading: str,
    text: str,
    *,
    concepts: list[str] | None = None,
    callouts: list[str] | None = None,
    primary_model: str,
    temperature: float,
    is_local: bool,
    local_preflight_skip_temp: int,
    last_gpu_temp: int,
    local_b4_section_cap: int,
    local_vram_recovery_delay: float,
    max_bullets_per_chapter: int,
    extract_must_have_items: Callable[[str, str], list[str]],
    recover_vram: RecoverVramFn,
    summarize_with_model: SummarizeWithModelFn,
    consolidate_duplicate_claims: Callable[[list[str]], list[str]],
    thematic_synthesis: Callable[[str, str, str], str | None],
    log: LogCallback | None = None,
) -> dict | None:
    """V3.3.0 B4: Split chapter into sections, summarize each, merge.

    Extracted verbatim from ``Summarizer._section_map_reduce``. The only
    changes are ``self.X`` → named parameters. The section-detection split,
    the must-have pre-flight (with the local GPU-temp skip), the key-quote
    extraction, the progressive-context injection, the adaptive B4 section
    cap (V18.2.15 VRAM-aware), the per-section VRAM recovery, the dedup
    consolidation, and the thematic-synthesis pass are byte-for-byte identical.

    The 2 local imports (``detect_sections`` from text_preprocessor,
    ``get_total_vram`` from vram_calculator) stay as local imports inside the
    function (verbatim) — they're optional and degrade gracefully on ImportError.

    Uses A6 (detect_sections) to find sub-headings, splits the text at those
    headings, summarizes each section independently, then merges. This
    guarantees every section gets LLM attention — no section is "forgotten"
    because it was in the middle of a long chapter.

    V13.44.0 enhancements:
    - #1 Must-have pre-flight: 1 quick LLM call identifies 5-7 must-have items
      before B4 runs; these are injected into each section's prompt
    - #5 Dedup consolidation: deterministic rapidfuzz merge after B4
    - #7 Progressive summarization: each section gets previous section's
      summary as context (prevents redundancy, encourages new ground)
    - #3 Thematic synthesis: 1 LLM call reorganizes the merged thorough
      summary by theme (not section order)
    - #6 Key quote preservation: deterministic extraction of important
      quoted passages, preserved verbatim
    """
    log = log or _noop_log
    try:
        from core.summarisation.text_preprocessor import detect_sections
    except Exception as _e:
        return None

    sections = detect_sections(text)
    if len(sections) < 2:
        return None  # not enough sections to justify map-reduce

    log(f"    \U0001f4d1 B4: Section map-reduce \u2014 {len(sections)} sections detected", "DEBUG")

    # Split text at section headings
    section_chunks = []
    lines = text.splitlines()
    current_chunk = []
    current_heading = heading
    for line in lines:
        stripped = line.strip()
        # Check if this line is a section heading
        is_heading = False
        for s in sections:
            if stripped == s or stripped.startswith(s):
                if current_chunk:
                    section_chunks.append((current_heading, "\n".join(current_chunk)))
                current_chunk = []
                current_heading = f"{heading} \u2014 {s}"
                is_heading = True
                break
        if not is_heading:
            current_chunk.append(line)
    if current_chunk:
        section_chunks.append((current_heading, "\n".join(current_chunk)))

    if len(section_chunks) < 2:
        return None

    # ── V13.44.0 Idea #1: Must-Have Extraction Pre-Flight ──
    # V13.44.3: Pre-flight always runs for cloud APIs (no thermal concern).
    # For local models, skip if GPU is warm (configurable threshold).
    must_have_items = []
    try:
        _skip_preflight = False
        if is_local and local_preflight_skip_temp > 0:
            _gpu_temp = last_gpu_temp
            if _gpu_temp >= local_preflight_skip_temp:
                _skip_preflight = True
                log(
                    f"    \u23ed\ufe0f Pre-flight skipped (GPU temp {_gpu_temp}\u00b0C \u2265 {local_preflight_skip_temp}\u00b0C threshold)",
                    "INFO",
                )
        if not _skip_preflight:
            must_have_items = extract_must_have_items(heading, text)
    except Exception as _e:
        # V18.2.14 (B4): traceable — was silent except:pass
        log_swallow("preflight_must_have_extract", _e, detail=f"heading={heading[:60]}")
    # Inject must-have items as additional callouts
    if must_have_items:
        if callouts is None:
            callouts = []
        callouts = list(callouts) + [f"MUST COVER: {item}" for item in must_have_items]
        log(
            f"    \U0001f3af Pre-flight: {len(must_have_items)} must-have items injected into B4 prompts",
            "INFO",
        )

    # (V0.08 / P2: the V13.44.0 "Key Quote Preservation" stage was removed —
    # extract_key_quotes always returned [] since V16.0.2, so the call and
    # the injection site below were zero-effect dead plumbing.)

    # Summarize each section
    all_bullets = []
    all_execs = []
    all_thoroughs = []
    all_distinctions = []  # V13.38.0: new additive sections
    all_tensions = []
    # V13.44.0 Idea #7: Progressive summarization — each section gets
    # the previous section's summary as context (prevents redundancy)
    # V13.44.3: Section cap is now configurable (local.b4_max_sections).
    # For cloud APIs, no cap (process ALL sections — cloud is fast enough).
    # V18.1 (audit Q1): Removed the 200-char truncation on the progressive
    # context hint. The full executive summary (~300-400 words) is now
    # injected, giving the next section proper context of what was already
    # covered. This prevents redundancy without losing continuity.
    prev_section_summary = ""
    _max_sections = len(section_chunks)  # default: no cap
    if is_local and local_b4_section_cap > 0:
        _max_sections = min(len(section_chunks), local_b4_section_cap)
        # V18.2.15 (P5): Adaptive cap — if the chapter has MORE sections
        # than the static cap, check available VRAM and raise the cap
        # when there's headroom. This removes the "hidden quality cliff"
        # where sections 7+ were silently skipped on long chapters.
        _skipped_sections = len(section_chunks) - _max_sections
        if _skipped_sections > 0:
            try:
                from core.vram_calculator import get_total_vram

                _total_vram = get_total_vram()
                if _total_vram and _total_vram >= 12.0:
                    _new_cap = min(len(section_chunks), max(_max_sections, 8))
                    if _new_cap > _max_sections:
                        log(
                            f"    \U0001f4d1 V18.2.15 Adaptive B4 cap: {_max_sections} \u2192 {_new_cap} "
                            f"(chapter has {len(section_chunks)} sections, {_skipped_sections} "
                            f"would be skipped; VRAM {_total_vram:.0f} GB \u2265 12 GB allows more)",
                            "INFO",
                        )
                        _max_sections = _new_cap
                    else:
                        log(
                            f"    \U0001f4d1 B4 cap: {_max_sections}/{len(section_chunks)} sections "
                            f"(VRAM {_total_vram:.0f} GB)",
                            "DEBUG",
                        )
                elif _total_vram:
                    log(
                        f"    \U0001f4d1 B4 cap: {_max_sections}/{len(section_chunks)} sections "
                        f"(VRAM {_total_vram:.0f} GB < 12 GB \u2014 cap kept; {_skipped_sections} "
                        f"sections will be skipped \u2014 raise local.b4_max_sections to override)",
                        "DEBUG",
                    )
            except Exception as _e:
                log_swallow("adaptive_b4_cap_vram_check", _e)
    for sec_idx, (sec_heading, sec_text) in enumerate(section_chunks[:_max_sections]):
        if len(sec_text.strip()) < 200:
            continue
        # V13.42.2: VRAM recovery between B4 sections (thermal protection)
        # V18.1 (audit P3): delay is now configurable (local.vram_recovery_delay_sec).
        # Default changed from 120s to 0 (user undervolted GPU — no thermal pressure).
        if sec_idx > 0:
            recover_vram(
                context=f"B4-section-{sec_idx + 1}", delay_sec=float(local_vram_recovery_delay)
            )

        # V18.1 (audit Q1): Build progressive context — inject FULL executive summary
        progressive_context = ""
        if prev_section_summary and sec_idx > 0:
            progressive_context = f"\n\nPREVIOUS SECTION CONTEXT (already covered \u2014 focus on what's NEW):\n{prev_section_summary}"
            log(
                f"    \U0001f4d1 B4 section {sec_idx + 1}/{_max_sections}: progressive context injected ({len(prev_section_summary)} chars)",
                "DEBUG",
            )

        # Inject progressive context into the section text
        sec_text_with_context = sec_text
        if progressive_context:
            sec_text_with_context = f"{sec_text}\n{progressive_context}"

        try:
            result = summarize_with_model(
                sec_heading,
                sec_text_with_context,
                primary_model,
                temperature,
                with_cot=True,
                concepts=concepts,
                callouts=callouts,
            )
        except Exception as _e:
            log(f"    \u26a0\ufe0f B4 section {sec_idx + 1} crashed (non-fatal): {_e}", "WARNING")
            logger.debug("B4 section crash: %s: %s", type(_e).__name__, _e)
            result = None
        if result:
            all_bullets.extend(result.get("bullet_points", []))
            all_execs.append(result.get("executive_summary", ""))
            all_thoroughs.append(result.get("thorough_summary", ""))
            all_distinctions.append(result.get("key_distinctions", ""))
            all_tensions.append(result.get("theoretical_tensions", ""))
            # V13.44.0 Idea #7: Save this section's summary for the next section
            # V18.1 (audit Q1): No truncation — save full executive summary
            prev_section_summary = result.get("executive_summary", "")
            log(
                f"    \U0001f4d1 B4 section {sec_idx + 1}/{_max_sections}: completed, {len(result.get('bullet_points', []))} bullets, {len(result.get('thorough_summary', ''))} chars thorough",
                "DEBUG",
            )

    if not all_bullets:
        return None

    # ── V13.44.0 Idea #5: Dedup Consolidation Pass ──
    merged_bullets = consolidate_duplicate_claims(all_bullets)
    log(
        f"    \U0001f527 Dedup consolidation: {len(all_bullets)} \u2192 {len(merged_bullets)} bullets (merged {len(all_bullets) - len(merged_bullets)} duplicates)",
        "INFO",
    )

    # V0.06 (rig audit F1-e): the "None" placeholder is a FORMAT token — a
    # section that answered "None" contributes nothing to the merge (the
    # V0.05 rig shipped a literal "None" line inside a merged section).
    def _real(txt: str) -> bool:
        return bool(txt and txt.strip() and txt.strip().lower() not in ("none", "n/a", "null"))

    merged_exec = " ".join(e for e in all_execs if _real(e))[:2000]
    merged_thorough = "\n\n".join(t for t in all_thoroughs if _real(t))[:6000]

    # ── V13.44.0 Idea #3: Thematic Synthesis Pass ──
    # V13.44.3: Always run for cloud APIs (no thermal concern).
    # For local models, skip if B4 underperformed (saves GPU time).
    _run_synthesis = len(merged_thorough) > 500 and len(section_chunks) >= 2
    if is_local and len(all_bullets) < 15:
        _run_synthesis = False  # local + low output = skip synthesis
        log("    \u23ed\ufe0f Thematic synthesis skipped (local mode + low B4 output)", "INFO")
    if _run_synthesis:
        recover_vram(context="pre-thematic-synthesis", delay_sec=10.0)
        synthesized_thorough = thematic_synthesis(heading, merged_thorough, text)
        if synthesized_thorough:
            log(
                f"    \U0001f504 Thematic synthesis: reorganized {len(merged_thorough)} \u2192 {len(synthesized_thorough)} chars thorough",
                "INFO",
            )
            merged_thorough = synthesized_thorough

    # V13.38.0: Merge the new additive sections (concatenate non-empty)
    # V0.06 (F1-e): "None" placeholders excluded here too.
    merged_distinctions = "\n".join(d for d in all_distinctions if _real(d))[:3000]
    merged_tensions = "\n".join(t for t in all_tensions if _real(t))[:3000]

    return {
        "executive_summary": merged_exec,
        "bullet_points": merged_bullets[:max_bullets_per_chapter],
        "thorough_summary": merged_thorough,
        "key_distinctions": merged_distinctions,
        "theoretical_tensions": merged_tensions,
        "model": "section_map_reduce_v13.44",
        "temperature": temperature,
    }
