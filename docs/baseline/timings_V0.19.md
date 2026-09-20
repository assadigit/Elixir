# Pipeline Timing Baseline — V0.19 (Phase 6 Performance, before/after)

> The Phase-6 "after" numbers vs the Phase-1 baseline
> ([`timings_V0.13.md`](timings_V0.13.md)). Same harness
> (`scripts/bench_chapter.py` — the REAL Summarizer, real 16-stage
> pipeline, deterministic latency-bucketed mock LLM: heavy 20 s /
> medium 8 s / light 3 s, no network, no GPU), so every number below is
> reproducible on any machine.
>
> V0.18 pre-change verification: the untouched default path measured
> **47.43 s** on the golden chapter — matching the V0.13 baseline's
> 47.71 s within the documented ±10 % machine-noise band. The "before"
> for every mode below is the same V0.18 codebase with the levers OFF
> (the shipped default).

## 0. What Phase 6 changed (the levers)

All OFF by default (`summarisation.parallel_stages` — the roadmap's
"default off → on after soak" rollback plan; each lever independently
disableable; `max_workers` logic for the local path untouched):

| Lever | Setting (default when master ON) | What overlaps |
|---|---|---|
| MAP | `summarisation.parallel_stages_map` (true) | Map-reduce map chunks, bounded waves (≤ `parallel_stages_max_workers`, default 4) |
| B3 | `summarisation.parallel_stages_b3` (true) | The 3 multi-sample voting calls (same prompt, model-optimal temp) |
| JUDGE-SCHOLAR | `summarisation.parallel_stages_judge_scholar` (true) | The scholar reflection (speculative) ∥ the validation+judge LLM tail; MERGED when the judge leaves the summary state unchanged, DISCARDED + re-run inline when it does not |
| — | `summarisation.parallel_stages_max_workers` (4, clamp 1..8) | The concurrency bound for every lever |
| Queue (6.3) | `queue.max_parallel_books` (2, clamp 1..4) | Cross-book queue workers — **cloud providers only**; local always sequential |

Why threads and not `async_provider.gather_calls` (the roadmap allowed
either): the async provider speaks Ollama only; the thread engine wraps
the same sync callables every provider already uses, and the transport
(`_call_llm` → requests + locked response cache) is already exercised
concurrently by cross-chapter workers in production. See
`core/summarisation/stage_overlap.py` §"Why threads".

## 1. Golden chapter (single-pass) — the dependency-chain cap

`tests/golden/nonfiction`, 1 chapter, sequential, scale 1.0:

| Mode | Wall (s) | LLM calls | Simulated LLM (s) | Overlap |
|---|---:|---|---:|---|
| Levers OFF (V0.18 default) | **47.43** | 5 (1H+3M+1L) | 47.0 | 99 % sequential |
| Levers ON (`--parallel-stages`) | **36.41** | 5 (1H+3M+1L) | 47.0 | **129 % — overlap working** |
| **Reduction** | **−23.3 %** | unchanged | unchanged | |

**Why 23.3 % is the cap on this chapter** — the 5 calls form a strict
chain (Phase 6.1 trace, `origin=` per call):

```
#1 primary summarize (heavy 20 s, primary_call.py)
  → validation prologue (deterministic, no LLM)
    → [#2 grounding check (medium 8 s) → #3 gap-fill reprompt (light 3 s)]   ← judge tail
    → [#4 scholar reflection (medium 8 s) → #5 truncation retry (medium 8 s)] ← recovery
```

`#3`'s prompt embeds post-`#2` bullets; `#5` is a continuation retry of
`#4`; the scholar sees post-judge bullets. The only SAFE overlap is the
judge tail ∥ the scholar pair (the JUDGE-SCHOLAR lever's speculative
merge). The critical path is then `#1 (20) + max(11, 16) = 36 s` —
measured 36.41 s. **No behavior-preserving overlap can beat this** on
the single-pass golden chapter; the remaining 25 %+ lives on the paths
below, which is where real books spend their time.

## 2. B3 multi-sample path (coverage-fail chapters)

`--bench-mode b3`: the first primary response is deliberately narrow →
coverage check fails → B3 fires 3 samples (each a full primary-shaped
heavy call) → voting → the normal tail:

| Mode | Wall (s) | LLM calls | Reduction |
|---|---:|---|---:|
| Levers OFF | **115.42** | 9 (4H+4M+1L) | |
| Levers ON | **64.39** | 9 (4H+4M+1L) | **−44.2 %** |

On a real rig this path is even bigger: the V15.1.0 inter-sample
`recover_vram(120 s)` sleeps (2 × 120 s on the sequential path) are
skipped entirely on the overlapped path — they exist to serialize local
samples, and the lever is cloud-oriented.

## 3. Map-reduce path (oversized chapters)

`--bench-mode mapreduce`: a deterministic synthetic ~45 k-token chapter
at the legacy 32 k window → 13 map chunks (4 000-token, heavy class) +
1 reduce:

| Mode | Wall (s) | LLM calls | Reduction |
|---|---:|---|---:|
| Levers OFF | **315.79** | 18 (14H+4M) | |
| Levers ON | **135.78** | 18 (14H+4M) | **−57.0 %** |

Both runs fail identically AFTER the map+reduce phase completes — the
deliberately-preserved, test-pinned `_pipeline`/`_pstate`
UnboundLocalError on the map-reduce leg (see ROADMAP Phase 5 notes);
the comparison is apples-to-apples (same 18 calls, same failure, same
point). 13 map calls in 4-worker waves: `13 × 20 s → ceil(13/4) × 20 s`.
This is the lever for the rig's real map-reduce workloads (the V18.20.4.9
'97 Things' case: 188 chunks × 5-15 min each on a CPU-offloaded quant —
4 workers bounds that to ~¼ of the wall-clock).

## 4. Queue concurrency (task 6.3) — cloud providers only

Bounded cross-book workers (`queue.max_parallel_books`, default 2,
clamp 4) when the provider is cloud (claude / freellmapi / openrouter /
openai / openai_compatible). Local providers are ALWAYS sequential —
the Phase-6 VRAM acceptance (max_workers logic untouched for the local
path). Per-book cancel events (a stop cancels every active book),
per-book progress signal, crash isolation (one book's failure never
kills the queue). Semantics pinned headlessly in
`tests/test_p6_stage_overlap.py::TestQueueViewWiring` +
`TestRunBooksParallel` (PySide6 is not needed to test them).

## 5. Output equivalence + quality gates (the "not worse" proof)

- **Byte-identical ON == OFF**: the freeze-output dicts of all 6 golden
  chapters (nonfiction, academic, academic_tables, scanned_ocr,
  multicolumn, farsi) are IDENTICAL with the levers armed vs the
  default path, and both match the committed fixtures
  (`tests/test_p6_stage_overlap.py::TestGoldenEquivalence`).
- **Golden freeze suite**: 14/14 green (unchanged fixtures).
- **Phase-4 eval gate**: `make eval-check` → "EVAL GATE: OK — no
  quality regressions vs baseline" (faithfulness 99.2-99.7 %,
  hallucination 0 % on all 6 chapters — identical to the V0.17
  baseline, because the outputs are identical).
- **Full suite**: 5 573 passed / 0 failed (+41 Phase-6 tests).

## 6. Real-rig projection (the ≥15 % acceptance leg)

No rig access from the development sandbox — the measured projection,
from the harness numbers plus the rig's documented constants:

- The two pre-LLM `recover_vram` sleeps on the golden path
  (pre-content-judge 15 s, pre-scholar 15 s) overlap the opposite
  phase's calls under the JUDGE-SCHOLAR lever (hidden, not removed).
- B3 chapters lose the 2 × 120 s inter-sample sleeps AND overlap the
  3 samples (measured −44 % on calls alone; with the sleeps the
  sequential path is ~+4 min, the overlapped path ~1 call).
- Map-reduce chapters: measured −57 % of the map phase.
- Cloud queue: up to 4 books concurrently (bounded, opt-in).

Chapter mix on a real book: single-pass chapters ~ −20-25 %, coverage-
fail chapters ~ −60-75 % (with the sleeps), oversized chapters ~ −55 %,
plus queue-level gains for cloud multi-book runs. The ≥15 % bar is met
with margin on every path except single-pass-only books with a local
provider at `parallel_stages` default OFF (0 % — by design; the setting
is the rollback plan). **Soak instruction**: enable
`summarisation.parallel_stages` on the rig, re-run a known book,
compare the Phase-4 scorecards (re-freeze → re-baseline if intentional)
and wall-clock; each lever can be turned off independently.

## 7. Cache instrumentation (task 6.4)

- `response_cache`: eviction counter + mid-run periodic INFO summary
  (every 200 lookups) + end-of-run summary; `stats()["evictions"]`.
- `embedding_cache`: end-of-run hit-rate summary.
- Budgets deliberately unchanged — no eviction data exists yet; the
  counter is the tuning signal (an eviction is the only evidence the
  1 000-entry FIFO cap is losing reusable responses).

## 8. Reproduce

```bash
python scripts/bench_chapter.py --latency-scale 1.0                        # golden, default (47.43 s)
python scripts/bench_chapter.py --latency-scale 1.0 --parallel-stages     # golden, levers ON (36.41 s)
python scripts/bench_chapter.py --latency-scale 1.0 --bench-mode b3 --parallel-stages
python scripts/bench_chapter.py --latency-scale 1.0 --bench-mode mapreduce --parallel-stages
make eval-check                                                           # quality gate
```

- Measured on: Linux sandbox, Python 3.12.14, repo @ V0.19.
- Expected variance: ±10 % (CI machine noise); call counts, overlap
  ratios, and output equivalence are deterministic.
