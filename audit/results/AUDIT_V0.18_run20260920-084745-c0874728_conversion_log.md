# AUDIT #2 — Conversion Log — version V0.18 (run 20260920-084745-c0874728)

> **Audit version:** `V0.18 / run 20260920-084745-c0874728 / app 0.18 / 2026-09-20T08:47:45 / 40 bullets`
> **Log file:** `Broken Structures Salman Akhtar.conversion.log.md` (899 lines)
> **Scope:** per the campaign owner's instruction — *"audit the conversion log, and see what went wrong and could be fixed/improved. For example, I've noticed that output truncates itself, which might cause coverage and accuracy issues, so it seems we need to chunk outputs, so it doesn't go beyond modelfile max output size."*
> **Comparison anchor:** this is the **V0.18 baseline log audit**. The next log audit (after a re-run with tag `V0.20.1`) will be filed as `AUDIT_V0.20.1_<new_run_id>_log.md` and compared against the call-by-call table below.

---

## 1. The 11-call timeline — what the model did, what truncated, what was lost

The run made **11 LLM calls, 1392s total (80% of the 1735s wall-time)**. **5 of 11 calls truncated** (`done_reason=length`), and 3 of those 5 produced content that was **discarded** by downstream gates. The call-by-call map:

| # | Time (s) | Phase | Prompt tok | Output tok | done_reason | Truncated? | What survived | What was lost/wasted |
|---|---|---|---|---|---|---|---|---|
| 1 | 286 | **Primary summarize** (5-section XML: exec+bullets+thorough+distinctions+tensions) | 12388 | 3740 | length | **YES** | 30 bullets (from 134 in a CoT thinking block; thinking filter kept 30) | **exec = CoT → discarded; thorough = CoT → discarded** (log L465: "primary-call thorough is CoT narrative — DISCARDED AT PARSE TIME"). The entire 5-section XML was inside the thinking block. 286s produced only 30 bullets. |
| 2 | 139 | Additive sections (key_distinctions + theoretical_tensions) | 9893 | 1921 | stop | no | both sections (1464 + 1114 chars) | — |
| 3 | 134 | Dedicated thorough (t=0.35, regenerates the CoT-discarded thorough) | 9961 | 1896 | stop | no | thorough = 823 words | — (this call exists ONLY because call 1's thorough was CoT-discarded) |
| 4 | 115 | Exec-from-thorough derivation | 1129 | 2048 | length | **YES** | nothing | **output = CoT → discarded** (log L513: "Exec-from-thorough output is CoT narrative — discarding, falling back"). Exec fell back to = thorough (the V0.18 Defect D: exec = thorough, byte-identical). 115s wasted. |
| 5 | 200 | **Scholar reflection** (gap analysis + gap-fill for ALL ~24 missing theorists in one call) | 13418 | 2710 | length | **YES** | nothing | **gap-fill bullets dropped — no quotes** (log L571-573: "Dropped gap-fill without quote: Max 8 reflection bullets… Max 12 gap-fill bullets…"). "Scholar reflection: identified gaps but could not fill them" (log L575). 200s wasted. |
| 6 | 133 | **Scholar continuation** (O-a4 retry — additive continuation of call 5) | 14003 | 2125 | length | **YES** | nothing | **retry ALSO truncated** (prompt 14003 + output 2125 = 16128 > 16000 num_ctx → hit the CONTEXT window, not the output cap). Output ALSO dropped — no quotes. 133s wasted. |
| 7 | 77 | V18.14.1 batch gap-fill round 1 (Jacobson, Kernberg, Blos, Mahler, Winnicott) | 1022 | 1335 | stop | no | 8 bullets | — |
| 8 | 70 | V18.14.1 batch gap-fill round 2 (Fenichel, Hartmann, Tausk, Wheelis, Lynd) | 1020 | 1191 | stop | no | 8 bullets | — |
| 9 | 116 | V18.14.1 batch gap-fill round 3 (Federn, Glover, Spiegel, Stoller, Galenson and Roiphe) | 910 | 2000 | length | **YES** | 7 bullets | 1 bullet dropped — prompt-leakage/thinking (log L639: "Dropped gap-fill bullet: Spitz's (1957) developmental hypothesis…" — the model confused the rounds). The truncation cut the output but the 7 kept bullets are valid. |
| 10 | 94 | V18.14.1 batch gap-fill round 4 (Spitz, Klein, Loewald, Searles, Khan) | 758 | 1575 | stop | no | 4 bullets (1 vetoed: "Khan's work supplies… source attributes this claim to Winnicott, not Khan") | — |
| 11 | 26 | V18.14.1 batch gap-fill round 5 (Khan) | 382 | 433 | stop | no | 0 bullets (vetoed again) | — |
| | **1392** | | | | | **5 truncated** | | **~834s wasted (60% of LLM time)** |

**The 5 truncated calls (1, 4, 5, 6, 9) consumed 850s (61% of LLM time) and produced 37 surviving bullets between them — all 37 from call 1's thinking block.** The other 6 non-truncated calls (2, 3, 7, 8, 10, 11) consumed 542s and produced 19 surviving bullets + the additive sections + the thorough.

## 2. The truncation root cause — two caps, both rig-imposed

The model is `Qwen3.8-27B-Q2_K_XL-Instruct-NoVision-Unsloth-DynamicV3Quant:latest` on a 12 GB card. Two caps bind it (both set by V18.2.43 / V18.2.37d, both rig constraints, not bugs):

### Cap A — `num_predict` (output cap) = 8192 tokens
- Set at log L393-395: *"max_output_tokens was 12000 — capping to 8192 for low-bit quant (26758 context cap)."*
- Code: `core/summarisation/summarizer_init.py` L644-666. The low-bit-quant branch caps `summarisation_max_output_tokens` to `IQ2_S_PROFILE.LOW_BIT_MAX_OUTPUT` (8192).
- The comment at L652 states the design intent: *"Truncation on large chapters is handled by E3 (chunked output), NOT by raising the per-call output cap."* **The chunked-output machinery exists (the V18.14.1 batch gap-fill uses it) — but the scholar reflection and the primary call do NOT use it.**

### Cap B — `num_ctx` (context window) = 16000 tokens
- Set at log L451: *"27B Q2_K model on 12GB card — capping context 23209→16000 (IQ2_S has more headroom than Q2_K_XL: 1.59GB vs 0.82GB free)."*
- The Q2_K_XL quant on 12 GB leaves only 0.82 GB free after model load → the context window is capped at 16000 to avoid OOM.
- This cap is the BINDING constraint for the O-a4 retry (call 6): prompt 14003 + output 2125 = 16128 > 16000. The retry hit the CONTEXT window, not the output cap.

**The two caps interact:** for any call, `prompt_tokens + output_tokens ≤ 16000` (the context window) AND `output_tokens ≤ 8192` (the output cap). When the prompt is large (scholar reflection: 13418 tok), the output room is `16000 − 13418 = 2582 tok` — far less than the 8192 output cap. So a large-prompt call is context-bound, not output-bound.

## 3. The double-failure: scholar reflection (calls 5 + 6) — 333s, zero gap-fill

This is the most expensive defect in the run. The scholar reflection phase took **333s (24% of all LLM time) and produced ZERO gap-fill bullets.** The failure has two layers:

### Layer 1 — truncation (both calls)
- Call 5: prompt 13418 tok, output 2710 tok, done_reason=length. The output (9707 chars) hit the 8192 output cap mid-gap-fill.
- Call 6 (O-a4 retry): prompt 14003 tok, output 2125 tok, done_reason=length. The prompt GREW (13418 → 14003) because the retry appends the continuation suffix + the last 2000 chars of the first response. So `prompt + output = 16128 > 16000` → the retry hit the CONTEXT window. **The retry is counterproductive when the prompt is near the context cap:** it makes the prompt bigger, which leaves less output room.

### Layer 2 — no-quotes drop (both calls)
Even if the calls hadn't truncated, the gap-fill bullets would have been dropped (log L571-573): *"Dropped gap-fill without quote: Max 8 reflection bullets (≤30 words each)… Max 12 gap-fill bullets (≤45 words each)…"*. The scholar reflection's gap-fill format requires each bullet to carry a source quote; the model's output (in the surviving prefix) didn't include them (or they were in the truncated tail).

### The chunked fallback that already works (calls 7–11)
The V18.14.1 batch gap-fill path — which ran AFTER the scholar reflection failed — is **already chunked**: 8 missing theorists per round, 5 rounds, each call with a small prompt (910–1022 tok) and a small output (1191–2000 tok). It produced 27 gap-fill bullets across 5 rounds (384s). The batch path's prompts are small enough that the context window never binds, and its output is small enough that the 8192 cap never binds (except round 3, which truncated at 2000 tok but kept 7/8 bullets).

**The scholar reflection is REDUNDANT when it truncates** — the V18.14.1 batch path does the same job, chunked, and succeeds. The 333s spent on the scholar reflection (calls 5+6) was entirely wasted.

## 4. The primary call (call 1) — 286s, CoT, only 30 bullets survived

The primary call asked for all 5 sections (exec + bullets + thorough + distinctions + tensions) in one 8192-output call. The model produced a **17,313-char response that was entirely inside a `<thinking>` block** — the 5-section XML was never opened. The thinking filter (log L471-473) kept 30 of 134 bullets. The thorough was CoT narrative → discarded (log L465). The dedicated thorough (call 3, 134s) had to regenerate the thorough from scratch.

So the primary's 286s produced only 30 bullets. The 5-section XML the prompt asked for was never produced — the model spent its output budget on thinking. This is the known V18.20.3.2 CoT-inundation pattern, and the existing fallback (dedicated thorough) handles the thorough. But the exec, the distinctions, and the tensions were ALSO lost (the additive sections call 2 and the exec-from-thorough call 4 had to regenerate them).

**The user's "chunk outputs" suggestion applies directly here:** instead of asking for all 5 sections in one 8192-output call (which the model fills with thinking), split into 2 calls:
- Call 1a: exec + bullets (the dense, claim-heavy sections)
- Call 1b: thorough + distinctions + tensions (the prose sections)

Each call's output target is smaller, the model spends less output on thinking per call, and the truncation risk drops. This is the map-reduce pattern already used for long chapters (`core/summarisation/map_reduce.py`) — applied to the OUTPUT side, not the input side.

## 5. What went wrong — the defect inventory

| Defect | Layer | Evidence (log lines) | Impact | Fixable in code? |
|---|---|---|---|---|
| **L1 — Scholar reflection truncates (output cap)** | scholar_reflection.py | L557-559, L567-569 | 333s wasted; 0 gap-fill bullets from scholar | YES — chunk the scholar reflection (the user's suggestion) |
| **L2 — O-a4 retry counterproductive (context cap collision)** | scholar_reflection.py L296-366 | L567: prompt 14003 + output 2125 = 16128 > 16000 | retry ALSO truncated; 133s wasted | YES — skip the retry when prompt is near the context cap |
| **L3 — Scholar gap-fill bullets dropped (no quotes)** | scholar_reflection.py | L571-575 | even un-truncated output would have been dropped | YES — the V18.14.1 batch path produces quotes and succeeds |
| **L4 — Primary call produces CoT, 5-section XML lost** | primary_call.py | L459-465 | 286s → only 30 bullets; exec/thorough/distinctions/tensions all regenerated by later calls | YES — chunk the primary call (the user's suggestion) OR strengthen the no-thinking prompt constraint |
| **L5 — Exec-from-thorough produces CoT, discarded** | chapter_phases.py (V18.15.8.0) | L509-513, L697 | 115s wasted; exec = thorough (Defect D) | YES — the V0.18 Defect D (deferred) |
| **L6 — Gap-fill round 3 truncates, 1 bullet lost (Spitz)** | gap_fill_batch.py | L631-639 | 1 bullet dropped (prompt-leakage/thinking, not a missing theorist) | minor — the 7/8 kept bullets are valid |
| **L7 — 5/11 calls truncated (60% waste)** | the whole 5-call chain | L873 | 834s of 1392s LLM time produced no net content | the sum of L1-L5 |

## 6. The smallest fix the evidence supports (one conventional commit)

**Fix — skip the O-a4 retry when the scholar reflection's prompt is near the context cap.** The retry is counterproductive when `prompt_tokens + continuation_overhead > num_ctx − min_output_room`: the retry makes the prompt BIGGER, so it hits the context window and produces even less output. The V18.14.1 batch gap-fill (which uses small prompts and already chunks) is the working fallback — it runs immediately after the scholar reflection and produces 27 gap-fill bullets.

The change is ~5 lines in `core/summarisation/scholar_reflection.py` at the O-a4 retry site (L314): before issuing the continuation call, check whether `len(prompt_tokens) + continuation_suffix_overhead > num_ctx − min_output_room`; if so, skip the retry, log a WARNING ("scholar prompt near context cap — O-a4 retry skipped, V18.14.1 batch gap-fill will handle"), and let the existing batch path run. This saves 133s (the doomed retry) on this rig run and avoids the counterproductive double-truncation.

**Evidence cited:** log L567 (retry prompt 14003 tok + output 2125 tok = 16128 > 16000 num_ctx → done_reason=length), log L571-575 (retry output dropped — no quotes), log L603-675 (V18.14.1 batch path succeeds, 27 bullets, 384s).

## 7. The bigger fix — the user's "chunk outputs" suggestion (design-aligned)

The codebase's own design intent (the comment at `summarizer_init.py` L652) states: *"Truncation on large chapters is handled by E3 (chunked output), NOT by raising the per-call output cap."* The V18.14.1 batch gap-fill already implements E3 chunking for the gap-fill phase. The user's suggestion — *"chunk outputs, so it doesn't go beyond modelfile max output size"* — extends E3 to the two phases that don't chunk:

### 7a. Chunk the scholar reflection's gap-fill (medium change)
Instead of one call asking for ALL ~24 missing theorists' gap analysis + gap-fill, split into rounds of ~8 theorists (the same chunk size the V18.14.1 batch path uses). Each round's prompt is smaller (~2000 tok instead of 13418 tok), each round's output is smaller (well under the 8192 cap), and each round's gap-fill bullets carry quotes (the batch path's prompt format enforces this). This is essentially: **make the scholar reflection USE the V18.14.1 batch path's chunking + quote format, instead of the single-big-call format.** The single-big-call scholar reflection becomes the "gap analysis" step (identify the missing theorists), and the V18.14.1 batch path becomes the "gap-fill" step (produce the chunked, quoted bullets) — which is exactly how the pipeline already runs when the scholar reflection fails. The fix is to make this the DEFAULT path, not just the fallback.

### 7b. Chunk the primary call (larger change)
Instead of one call asking for all 5 sections (exec + bullets + thorough + distinctions + tensions) in one 8192-output call, split into 2 calls:
- Call 1a: exec + bullets (the dense, claim-heavy sections — the model's deliberate selection)
- Call 1b: thorough + distinctions + tensions (the prose sections)

Each call's output target is ~4096 tok (well under the 8192 cap), the model spends less output on thinking per call, and the CoT-inundation pattern (L4) drops. The additive-sections call (call 2) already produces distinctions + tensions separately — so half of this chunking already exists. The remaining step is to split the primary's exec+bullets+thorough into two calls (exec+bullets, then thorough). This is a larger change to the primary call prompt and the parse logic, and should be a separate commit with its own audit.

## 8. What did NOT go wrong (the good news)

- **Zero hallucinations** (Audit #1): every shipped claim is source-grounded. The 5-call dependency chain's grounding check + judge + postchecks caught every paraphrase-hygiene issue (log L719-753).
- **The deterministic recall floor is honest** (log L765): "theorists 20/37, conclusion items 5/7" — the regex-measured floor, not the LLM judge's overstated 100%.
- **The V18.14.1 batch gap-fill is robust** (calls 7-11): 27 bullets across 5 rounds, small prompts, no context-window collisions, quote-enforced format. This is the chunked-output pattern the user is asking for — it already exists for the gap-fill phase.
- **The incremental checkpointing worked** (log L429, L777): each chapter is saved the moment it completes; a crash never loses finished chapters.
- **The thermal safety system held** (log L827-837): 0.0/120 min above 70°C, 0 cool-downs — the GPU never thermal-throttled.

## 9. Comparison anchor — for the next log audit

This is the **V0.18 baseline log**. When the owner re-runs with tag `V0.20.1`, the new log audit will be compared against:

| Metric | V0.18 baseline | V0.20.1 target |
|---|---|---|
| LLM calls | 11 | 11 (or fewer if the O-a4 retry is skipped) |
| Truncated calls | 5 | ≤3 (the primary + scholar are rig-bound; the O-a4 retry skip removes 1) |
| LLM time wasted on discarded/retried calls | ~834s (60%) | ≤500s (the V0.20.1 fixes don't touch truncation; they fix coverage + clarity) |
| Scholar reflection gap-fill bullets | 0 (all dropped — no quotes) | 0 (unchanged — the scholar reflection prompt is not changed in V0.20.1) |
| V18.14.1 batch gap-fill bullets | 27 | ≥27 (the V0.06 cap now rescues sole-cover gap-fill bullets — Defects A+B fix) |
| Recall floor (theorists) | 20/37 (54%) | ≥25/37 (the V0.06 cap rescue) |
| Recall floor (conclusion items) | 5/7 (71%) | 7/7 (the V0.06 cap rescue) |
| Thorough theorists | 13/37 (35%) | ≥18/37 (the non-skippable thorough floor — Defect C fix) |

> **The V0.20.1 fixes (already on `main`, tag `V0.20.1`) do NOT address truncation** — they address the V0.06 cap coverage (Defects A+B), the thorough floor deadline-skip (Defect C), and the colon-ending label-stub detector (Defect E). The truncation fixes (this audit's §6 and §7) are the NEXT commit family, after the V0.20.1 re-run confirms the coverage/clarity scorecard moved toward 9–10.
