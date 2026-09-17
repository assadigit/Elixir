# New Session Prompt — MarkItDown Pro V18.15.2.1 (God-Class Extraction Continuation)

I'm continuing development of **MarkItDown Pro**, an LLM-based book summarization
desktop app (PySide6 + Ollama) running on Windows 10 with an RTX 3060 12GB GPU.
The current version is **V18.15.2.1** — this is the **gold standard** base version
for this session. The god-class extraction is the primary agenda.

## This session's focus: CONTINUE GOD-CLASS EXTRACTION

`core/summarisation/summarizer.py` is currently **4442 lines** (down from 5803 in
V18.10.1). **12 of 15 extraction targets** are done. The target is ~3000 lines.

## Environment
- **OS**: Windows 10 (10.0.19045)
- **GPU**: NVIDIA RTX 3060 12GB (Zotac Twin Edge OC — EMERGENCY thermal profile)
- **Python**: 3.12.9, PyTorch 2.13.0+cu126
- **Ollama**: 0.30.6
- **Model**: `Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest`
  (9.3 GB, VRAM ~10.5/12.0 GB, ctx cap 26758, deadline 1800s/30min)
- **Embedder**: `nomic-embed-text` via Ollama (WORKING since V18.15.2 — no sentence_transformers needed)
- **Test chapter**: "Broken Structures" Salman Akhtar, Ch.1 "IDENTITY AND ITS ORIGINS"
  (~6,425 words, 9,139 tokens) — trust-ground at `audit/trust-ground/001_1_..._source.md`
- **App source**: `/home/z/my-project/upload/extracted/MarkItDown-Pro-V18.3.6/`
  (folder name is V18.3.6 but `VERSION` file says `18.15.2.1` — known quirk)

## Current gold-standard metrics (V18.15.2.1)
- **Score**: 9/10 (0 hallucinations, 4 consecutive runs at 100% bullets-only coverage)
- **Bullets-only**: 100% (31/31 theorists) — gap-fill loop bypasses deadline
- **Thorough-only**: 94% (29/31)
- **Coverage**: 89-100% (model variance)
- **0 prompt-leakage** (all 4 bullet-gen paths filtered)
- **0 "the reby"** defects
- **7 characteristics** explicitly listed
- **Embedder**: WORKING (nomic-embed-text via Ollama — semantic dedup + Phase 2.2 fact-check run)
- **Layout reorder**: sampling-based (saves ~24s for 95% of books)
- **496 sandbox tests**, all passing

## Completed work (ALL DONE — DO NOT RE-EXTRACT)

### 12 extracted modules (V18.11.0 — V18.15.0):
1. `text_utils_ext.py` — `smart_truncate`
2. `bullet_scorer.py` — `score_bullet`
3. `bullet_consolidation.py` — `consolidate_duplicate_claims` + `consolidate_bullets`
4. `map_reduce.py` — `map_reduce_summarize` + `section_map_reduce`
5. `multi_sample.py` — `multi_sample_summarize`
6. `thorough_fallback.py` — `call_dedicated_thorough_with_fallback`
7. `self_review.py` — `self_review_batched`
8. `scholar_reflection.py` — `scholar_reflection` + `scholar_reflection_gapfill_only`
9. `gap_filler.py` — `gap_fill_concepts`
10. `quarantine_recovery.py` — `recover_quarantined`
11. `post_processing.py` — `normalize_bullets` + `classify_bullets` (V18.6)
12. `summary_validator.py` + `llm_dispatcher.py` + `prompt_assembly.py` (V18.7-V18.8)

### Key fixes (V18.12.1 — V18.15.2):
- V18.12.1: dedicated thorough try/except (Ollama 500 crash prevention)
- V18.12.2-3: prompt-leakage filter across ALL 3 gap-fill paths + 15 regex patterns
- V18.13.0: layout reorder sampling (1-2 pages, skip if single-column)
- V18.14.0: independent-unit coverage (bullets-only + thorough-only checked separately)
- V18.14.1-2: looped gap-fill (bypasses deadline, 5-round cap)
- V18.14.3: bullet expansion filter (4th path) + pre-consolidation cap (later removed)
- V18.15.0: no min/max on bullets (user rule: more bullets > lower coverage)
- V18.15.2: embedder switched to nomic-embed-text via Ollama

## What STAYS in Summarizer (too risky to extract — per V18.6.3 crash mitigation)
- `_summarize_inner` (1013 lines, 20+ self-deps) — the orchestrator. DO NOT extract whole.
- `__init__` (623 lines) — the constructor
- `_build_prompt` (248 lines, 9 self-deps) — V18.6.3 crash undiagnosed
- `summarize_chapters` (197 lines) — entry point
- `_call_llm` / `_call_llm_with_empty_retry` / `_call_cloud` — the dispatch chain (10+ self-deps)

## The remaining extraction targets (this session's work)

| # | Method | Lines | Self-deps | Risk | Extract to |
|---|--------|-------|-----------|------|------------|
| 1 | `_b3_cloud_judge` | 65 | 5 | MED | `b3_judge.py` |
| 2 | `_apply_3tier_coverage` | 64 | 6 | MED | `coverage_guarantee.py` |
| 3 | `_llm_grounding_check` | 96 | 7 | MED | `grounding_check.py` |
| 4 | `_summarize_with_model` | 83 | 8 | MED | `primary_call.py` |
| 5 | `_filter_thinking_bullets` | 116 | 6 | LOW-MED | already delegates to `post_processing.classify_bullets` — thin wrapper |
| 6 | `_call_fast_llm` | 72 | 5 | MED | `fast_llm.py` |
| 7 | `_call_llm_structured` | 66 | 5 | MED | `structured_llm.py` |

**Estimated total extraction: ~562 lines** → summarizer.py drops from 4442 → ~3880 lines.

## Hard constraints (DO NOT VIOLATE)
- `presence_penalty=1.5`, `temperature=0.7`, `num_ctx` ceiling 32768 (app caps to 26758 for IQ2_S), `keep_alive=30m`
- IQ2_S excluded from 300s timeout; deadline 1800s (30 min)
- `max_output=8192` (do NOT raise)
- **Quality > speed** — prefer more coverage
- **Qwen3 `/no_think` injection** must stay in `_call_llm_with_empty_retry`
- **More bullets > lower coverage** — no min/max on bullet count. No deterministic consolidation.
- **Bullets are an independent unit** — checked separately from thorough. 100% bullets-only coverage required.
- **Gap-fill loop bypasses deadline** — it's a binding coverage guarantee.
- **All 4 bullet-generation paths** must filter through `_filter_thinking_bullets`.
- **Embedder**: nomic-embed-text via Ollama. Do NOT switch back to sentence_transformers.
- **Layout reorder**: sampling-based (1-2 pages). Do NOT revert to per-page.
- **Explicit parameters, NOT context objects** — the V18.6.3 crash mitigation.

## How to work (established pattern)
1. **Read the worklog first** — `/home/z/my-project/worklog.md` has the full history
2. **Do the lowest-risk extraction first** — test, then proceed
3. **Use `write_file` for new modules** — extract verbatim (`self.X` → parameter)
4. **Characterization tests** — write byte-for-byte stability tests for every extraction
5. **Package as a zip** for the user to golden-master test on their hardware
6. **Audit the result** — the trust-ground source + 4-pillar framework is at `/home/z/my-project/audit/`

## How to audit
When I provide a new summary + conversion log:
1. Load the source from `audit/trust-ground/001_1_IDENTITY_AND_ITS_ORIGINS_source.md`
2. Apply `audit/framework/AUDIT_PROMPT.md` verbatim (4 pillars, 1-10 scoring)
3. Write the report to `audit/results/` + append to `AUDIT_HISTORY.md`

## Known issues (context, not blockers)
1. **Deadline exceeded** (1800s) — consolidation + `_summarize_inner` semantic dedup often skipped. The post-processing semantic dedup (keypoints phase) runs and catches duplicates. The deadline is a performance issue, not a code defect.
2. **Thorough-only coverage 94%** — Loewenstein + Searles sometimes missing from thorough (but both in bullets via gap-fill). Not a blocker since bullets are 100%.
3. **V18.6.3 crash undiagnosed** — `PromptContext` + `build_primary_prompt` code is in `prompt_assembly.py` (unused). DO NOT use context objects for extraction.
