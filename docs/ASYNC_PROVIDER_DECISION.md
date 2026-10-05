# ADR: wire or delete `core/llm/async_provider.py` (+ the E6 blocking-sleep pair)

> **Status:** PROPOSED — decision deferred to the owner. This document lays
> out the evidence on both sides and the data needed to decide. Per
> AGENTS.md Rule 2 (evidence-first; the fix is the smallest change the
> evidence supports), neither option is taken blind.
>
> **Opened:** V0.4.27 (Phase-5 P3 / SWOT W13). **Supersedes:** the
> `W8/E6 pair` note in `SESSION_REPORT.md` §Phase 7 W13 + the V0.11 SWOT W8.

## The artifact

`core/llm/async_provider.py` (445 ln) — an `AsyncLLMProvider` with
`httpx.AsyncClient` + `async def complete()`, plus two sync-bridge helpers:
`run_async(coro)` (runs an async coroutine to completion via `asyncio.run`)
and `gather_calls(*coros)` (a wrapper around `asyncio.gather` for
parallelizing independent LLM calls). Its own docstring (L1-45) declares it
**"opt-in and non-breaking"** and **"deliberately unwired"** per
`ROADMAP_V0.12 §6.2` — a full asyncio migration was explicitly rejected
("the app is a PySide6 desktop app; the UI runs on the Qt event loop; the
conversion runs on QThread workers; a full asyncio migration would require
a Qt↔asyncio bridge (`qasync`) and rewriting the entire call chain — high
risk").

**Runtime-dead status (re-verified this session):** the module's public API
has zero runtime call sites. The only repo references are docstrings/comments
(`core/summarisation/stage_overlap.py:12-25` explains why it chose threads
over `async_provider.gather_calls`; `core/llm/retry.py:123` notes the retry
policy keeps working with zero changes if async is ever wired). It has been
runtime-dead since V18.2.24 — seven versions and two SWOTs ago (the V0.11
SWOT W8 flagged it at 432 ln; it has since grown to 445 ln).

## The lever (the case for WIRING)

A chapter's pipeline makes 5–10 sequential blocking LLM calls (exec →
thorough → gap-fill → additive-sections → self-review → grounding). Each
blocks the worker thread for its full latency. The module's own estimate
(docstring): wiring it would parallelize independent in-chapter stages
(grounding-check on bullets ∥ self-review on thorough_summary) for a
documented **30–40 % chapter wall-clock cut**. LLM time is 98.5 % of
chapter wall-clock (README Phase-1 baseline), so this is the only latency
lever that matters.

The parallel-stages levers V0.19 (map waves −57 %, B3 overlap −44.2 %,
speculative scholar −23.3 %) are already wired and ON-by-default-OFF —
they overlap CHAPTERS and MAP WAVES, not the independent STAGES WITHIN a
single chapter that the async provider targets. So the async lever is
orthogonal to the existing V0.19 levers.

## The hazard (the case for NOT wiring / the E6 pair)

Wiring `async_provider` would also activate the **E6 blocking-sleep
hazard** (Phase-4 E6 / Phase-5 §2), because the sync-bridge `run_async` runs
the async event loop on the QThread, and these sleep sites become blocking
under the async loop:

- `core/llm/openai_compat_provider.py:265` — `_time.sleep(10)` in the Batch-API
  poll loop (60 × 10 s = up to 10 min blocking; a live provider). On a sync
  QThread this blocks one worker; under `run_async` it blocks the event loop
  (no other coro progresses during the sleep).
- `core/pdf/vision_figure_extractor.py:267,295` — `time.sleep(2 * (attempt +
  1))` retries (fine on sync QThreads; under async, same event-loop block).

So the decision is **joint**: wire async_provider AND replace these sleeps
with `asyncio.sleep` (or move them off the event loop), OR delete
async_provider AND leave the sleeps as-is (they're fine for the sync model).

## The case for DELETING

1. **Seven versions of runtime-dead.** It has been unwired since V18.2.24.
   The V0.11 SWOT W8 (2026-09-19) flagged it; the Phase-7 SWOT W13 re-flagged
   it. Two SWOTs, no movement. The actual priority is evidently low.
2. **The sync model works.** The V0.19 parallel-stages levers already
   capture the chapter-level + map-wave parallelism; the V0.4.25 ch.1
   benchmark ran 12 LLM calls in 62.3 s LLM time / 67 s wall-clock (deadline
   480 s) on a CLOUD model — well under deadline. On the rig's local 27B
   quantized model the wall-clock is VRAM-bound (single-model serial), which
   async does NOT help (you can't run two inferences on one GPU
   simultaneously without VRAM contention — the VRAM guardian already
   enforces this). So the async lever's 30–40 % estimate may not materialize
   on the rig's single-GPU constraint.
3. **Carrying cost.** 445 ln of hardened-but-unwired code (per
   `LLM_HARDENING.md` §3, it's "fully hardened") + the vulture-flagged public
   API + the repeated SWOT re-discovery. Future dead-code passes must
   re-whitelist it (T5-style).
4. **The "frozen-by-design" precedent.** `prompt_assembly.py` (458 ln) is
   frozen-by-design + whitelisted (T5) for a documented reason (V18.6.3
   crash). `async_provider.py` is frozen-by-design for a different reason
   (architectural call deferred). Either pattern is legitimate, but two
   frozen modules is more carry-cost than one.

## The case for WIRING

1. **The 30–40 % lever is the only in-chapter latency lever left.** The V0.19
   levers are spent. If the owner wants further per-chapter speedup, this is
   the only documented option.
2. **It's already hardened.** `LLM_HARDENING.md` §3 documents the async
   provider's retry/error taxonomy (mirrors the sync `@retry_llm_call`).
   The wiring work is the sync-bridge + the E6 sleep replacement, not a
   from-scratch build.
3. **The Qt↔asyncio bridge concern is addressable.** The docstring's
   "high risk" is about a FULL migration. The module's `run_async` sync
   bridge is designed to be called from sync QThread code (no `qasync`
   needed) — it runs `asyncio.run(coro)` on the worker thread. The risk
   is contained to the call sites, not the whole call chain.

## Decision data needed (the owner must provide)

The sandbox cannot generate the validating evidence (no local LLM, no
sentence-transformers). To decide, the owner should measure on the rig:

1. **The rig's per-chapter wall-clock breakdown.** Is LLM time still 98.5 %
   of wall-clock on the rig's 27B quantized model? If the VRAM guardian
   serializes inferences (one at a time on one GPU), the async lever's
   30–40 % estimate won't materialize — **delete**. If the rig has
   headroom (e.g., a smaller embedder model runs alongside the main model,
   or the cloud-provider path is used), the lever is real — **wire**.
2. **The independent-stage overlap opportunity.** Which of the 5–10
   per-chapter calls are genuinely independent (grounding-check ∥
   self-review), and what fraction of chapter wall-clock do they represent?
   The `stage_overlap.py` module (which chose threads over async) already
   overlaps some stages — does it cover the independent ones? If yes, the
   async lever is redundant — **delete**. If no, **wire**.
3. **The E6 sleep-site refactor cost.** Replacing `_time.sleep` /
   `time.sleep` with `asyncio.sleep` at the 3 sites is mechanical, but the
   `openai_compat_provider.py:265` Batch-API poll loop is a live provider
   — the change needs a mocked-HTTP-boundary test (the 36 existing tests at
   the LLM boundary are the net).

## Recommendation (provisional, pending the rig data)

**If the rig's LLM is single-GPU-VRAM-bound (likely, given the 12 GB RTX
3060 + 9.3 GB IQ2_S model leaving ~1.5 GB headroom):** the async lever
won't materialize → **DELETE** `async_provider.py` (445 ln) + leave the E6
sleeps as-is (they're fine for sync). This closes W13, removes the carry
cost, and ends the two-SWOT re-discovery. The 30–40 % estimate was made
before the V0.19 parallel-stages levers shipped; those levers may have
already captured the available parallelism.

**If the rig has GPU headroom OR the cloud-provider path is the primary
target:** the lever is real → **WIRE** it: replace the 3 E6 sleeps with
`asyncio.sleep`, add the `run_async` calls at the independent-stage sites
(grounding-check ∥ self-review), measure with the benchmark harness (the
6 golden chapters + the ch.1 ground truth), confirm the 30–40 % cut +
byte-identical output (the V0.19 levers' proof pattern), ship as V0.4.28.

## Either way: the E6 sleeps

Independent of the wire/delete decision, the E6 sleep sites should be
**documented with a "sync-only" guard comment** so a future async-wiring
attempt doesn't miss them. (This is a docs-only follow-up; not blocking.)

## References

- `core/llm/async_provider.py` (445 ln, docstring L1-45)
- `docs/LLM_HARDENING.md` §3 (the async provider's hardening matrix)
- `ROADMAP_V0.12` §6.2 (the deliberate-non-wiring decision)
- `core/summarisation/stage_overlap.py:12-25` (why threads were chosen over
  async_provider.gather_calls for V0.19 stage overlap)
- `core/llm/openai_compat_provider.py:265` (E6 site 1: Batch-API 60×10 s poll)
- `core/pdf/vision_figure_extractor.py:267,295` (E6 sites 2-3: 2 s×(n+1) retries)
- `SESSION_REPORT.md` §Phase 7 W13 (the SWOT item that opened this ADR)
- `docs/AUDIT_SWOT_V0.11.md` W8 (the V0.11 historical flag at 432 ln)
