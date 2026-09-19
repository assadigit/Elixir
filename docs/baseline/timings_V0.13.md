# Pipeline Timing Baseline — V0.13 codebase (Phase 1.3, V0.14 release)

> The "before" numbers for every later "after". Measured with
> `scripts/bench_chapter.py` (Phase 1.2 harness): the golden nonfiction
> chapter through the REAL `Summarizer` — real `__init__`, real
> `_summarize_inner` 16-stage pipeline — with a deterministic latency-bucketed
> mock LLM (heavy 20 s / medium 8 s / light 3 s, scaled). No network, no GPU:
> the numbers measure the pipeline's *structure* (call counts, stage costs,
> parallel overlap), which is stable across machines; absolute wall-clock on
> the real rig is dominated by actual model inference (see §4).
>
> Regenerate: `python scripts/bench_chapter.py [--parallel --workers N --chapters M] --json out.json`
> The roadmap (Phase 1.3) named this file `timings_V0.12.md`; it is committed
> as `timings_V0.13.md` to match the codebase version actually measured.

## 1. Chapter shape (the unit of work)

| Metric | Value |
|---|---|
| Golden chapter | `tests/golden/nonfiction/source_chapter.md` |
| Source tokens (tiktoken) | 292 in |
| Summary tokens out | 410 |
| LLM calls per chapter | **5** (1 heavy + 3 medium + 1 light) |
| Simulated LLM time per chapter | 47.0 s at full scale (20 + 8 + 8 + 8 + 3) |
| Python-side pipeline cost | **< 1.8 s** (all 16 stages combined, no LLM) |

Call classes observed (scale 0.05, 1 chapter): primary summarize = 1× heavy;
self-review + content-judge + consolidation = 3× medium; preflight/aux = 1× light.

## 2. Per-stage wall-clock (sequential, 1 chapter, scale 0.05 — LLM sleeps included)

| Stage | Calls | Total (s) | Notes |
|---|---:|---:|---|
| `_summarize_with_model` | 1 | 1.022 | includes the 20 s×0.05 heavy call |
| `pipeline.run_content_judge` | 1 | 0.734 | includes 2 medium aux calls |
| `_compute_coverage` | 2 | 0.004 | keyword+ngram, no LLM |
| `_parse_response` | 1 | 0.004 | XML parse |
| `_filter_thinking_bullets` | 1 | 0.003 | regex filters |
| `_verify_bullets` | 1 | 0.001 | fuzzy windows |
| `_anti_false_precision_check` | 1 | 0.001 | |
| `run_informational_checks` | 1 | 0.001 | |
| `_normalize_bullets` | 1 | 0.001 | |
| `apply_f3_reading_level` | 1 | 0.001 | |
| `_consolidate_bullets` | 1 | 0.001 | |
| `apply_f4_source_overlap` | 1 | 0.000 | |
| `_recover_quarantined` | 1 | 0.000 | |
| `apply_f1_length_validation` | 1 | 0.000 | |
| `_semantic_dedup_bullets` | 2 | 0.000 | |
| `_prepare_text` | 1 | 0.000 | |
| `apply_phase22_semantic_fact_check` | 1 | 0.000 | embedder absent → fail-closed |
| `run_self_consistency_and_review` | 1 | 0.000 | |
| `apply_academic_factual_verification` | 1 | 0.000 | |
| `_ensure_additive_sections` | 1 | 0.000 | |
| `salvage_empty_output` | 1 | 0.000 | |

**Reading:** with the LLM mocked to zero latency the entire Python-side
pipeline costs ~1.8 s/chapter (mostly interpreter warm-up; steady-state is
lower). The 16 stages are individually cheap — the pipeline's cost is the
**5 LLM round-trips**, and their *sequentiality* is the optimization target
(Phase 6.2).

## 3. Sequential vs parallel (scale 0.05)

| Mode | Chapters | Wall (s) | LLM calls | Simulated LLM (s) | Overlap |
|---|---:|---:|---|---:|---|
| Sequential (1 worker) | 4 | ~11.5 (extrapolated from 4×2.9) | 20 | 9.40 | ≈ 82% (serialized + overhead) |
| Parallel, 2 workers | 4 | **5.50** | 20 | 9.40 | **171% — overlap working** |
| Parallel, 4 workers | 8 | **5.72** | 40 | 18.80 | **329% — near-linear (8 ch ≈ 2 ch time)** |

Per-stage totals scale linearly with chapter count (`_summarize_with_model`
4.07 s @ 4 ch → 8.17 s @ 8 ch); no stage super-linear, no lock contention
visible at 4 workers on this fixture.

**Phase 6 leverage implied by these numbers:** chapter-level parallelism is
already near-linear in the mock. The remaining serialization is *within* a
chapter: the 5 calls per chapter run strictly in sequence (sequential mode
simulated-time/wall ≈ 100% at full scale). Phase 6.2 (overlap
grounding-check ∥ self-review ∥ additive sections via `async_provider`)
targets exactly that intra-chapter sequence.

## 4. Full-latency reference (scale 1.0, 1 chapter, sequential)

| Metric | Value |
|---|---|
| Wall-clock | 47.71 s |
| Simulated LLM time | 47.00 s |
| **LLM share of wall** | **98.5%** |

On the real rig the mix differs (real inference ≈ heavy calls dominate even
more; thermal guard sleeps disabled here), but the conclusion for Phase 6
prioritization is unchanged: **any optimization that does not reduce LLM
round-trips or overlap them is rearranging the <2%**.

## 5. Environment & reproducibility

- Measured on: Linux sandbox, Python 3.12.14, repo @ V0.13 + Phase-1 changes
  (pre-V0.14-release commit).
- Harness: `scripts/bench_chapter.py` @ Phase 1.2 — hermetic
  (`Settings._test_override`), embedder/spacy on their documented
  absent-machine fallbacks, response cache off, deterministic canned
  responses (frozen in `tests/golden/*/pipeline_output.json`).
- Expected variance: stage timings ±10% (CI machine noise); call counts and
  overlap ratios are deterministic (same fixtures, same code).
- cProfile: `python scripts/bench_chapter.py --profile --profile-out bench.prof`
  (top entries: `_summarize_inner` → `_mock_call_llm` sleeps → stage wrappers).

## 6. How this file is used

- **Phase 5 (de-monolithization):** every extraction PR re-runs the bench;
  call counts per chapter (5) and the frozen outputs must be *identical*;
  stage totals within noise.
- **Phase 6 (performance):** acceptance is ≥25% chapter wall-clock reduction
  on this harness (deterministic) — measured as simulated-LLM-time/wall
  improvement in parallel-within-chapter modes — plus no regression in the
  Phase-4 quality scorecards.
