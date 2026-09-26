# AUDIT V0.5.7 — ch.6 summary vs. source (the Maj-sey fix worked; the separate glossary call FAILED; coverage regressed)

**Run:** `20260927-022039-13cee394` (V0.5.7)
**Candidate:** 3,273 words, 60 bullets (REGRESSED from V0.5.6's 6,710 words / 83 bullets)

## Four-pillar scorecard (V0.5.7 vs V0.5.6)

| Pillar | V0.5.6 | V0.5.7 | Delta |
|---|---|---|---|
| Factual Consistency | 9 | 9 | — (0 hallucinations both; Judge 100% grounding 27/27 — DOWN from 81/81 but still 100%) |
| Informational Coverage | 8 | 6 | **-2 REGRESSION** (48/74 authors = 65% — DOWN from 69/75 = 92%; 60 bullets — DOWN from 83) |
| Cohesion & Clarity | 7-8 | 7 | — (the run completed cleanly) |
| Conciseness | 7 | 8 | +1 (3,273 words is more concise than V0.5.6's 6,710 — but at the cost of coverage) |
| **Overall** | **~8.0** | **~7.25** | **-0.75 REGRESSION** |

## What WORKED in V0.5.7

1. **The "Maj sey" OCR-garble is GONE** ✓ — the regex fix worked. The source now produces 74 unique authors (was 75 in V0.5.6 — the +1 OCR-artifact is gone; back to V0.5.5's 74-author floor). No "Maj sey" anywhere in the conv log. The gap-fill no longer wastes rounds hunting the fake 14th-century theorist.

2. **The master-summary no longer returns empty** ✓ — the V0.5.6 bug (3 empty returns + 5-in-1 fallback) is FIXED. The master-summary succeeded with 783 words (the simpler 5-section prompt — the `<name_glossary>` revert worked). The normal master-summary path ran (not the 5-in-1 fallback).

3. **The separate glossary call FIRED** ✓ — the LLM was called at 02:26:38 (`🦙 llama.cpp t=0.30 max=4096 streaming…`) for the dedicated glossary extraction. The call ran for ~3.5 min.

## What FAILED in V0.5.7

1. **The separate glossary call produced NO `<name_glossary>` block** ✗ — the log shows `ℹ️ V0.5.7: no <name_glossary> block parsed from the separate call (skipping persistence — the verification LAYER will fall back to the regex extract_citations)`. The LLM was called but didn't output the `<name_glossary>` block. The glossary features (📖 persistence, loosened quote-guard, V0.5.6 final-check with glossary ground truth) are STILL DORMANT.

   **Hypothesis**: the Ternary-Bonsai-2-27B model likely output thinking/reasoning before the `<name_glossary>` block + hit the max_tokens=4096 limit before finishing. OR the model didn't follow the XML-tag format instruction. The glossary for a 74-author chapter needs >4096 tokens.

2. **Coverage REGRESSED** ✗ — 48/74 authors (65%) vs V0.5.6's 69/75 (92%). The master-summary produced only 783 words → the bullet derivation (Call 2/3) produced only 27 bullets → the gap-fill rounds 1-4 added 33 more (to 60 total) but couldn't reach V0.5.6's 83. The 5-in-1 fallback path (which V0.5.6 took) produces a longer summary with more bullets.

3. **The 5 missing authors are STILL missing** ✗ — Allodi (0), Jack (0), Siever and Kendler (0) are still absent. Varghesi is now 1 (partial). The loosened quote-guard + final-check didn't fire (no glossary).

4. **The V0.5.6 leftover fused-path parser still runs** ✗ — the log shows `ℹ️ V0.5.6: no <name_glossary> block parsed from master summary (skipping persistence + cross-reference)`. The OLD V0.5.6 code that tries to parse the `<name_glossary>` from the master-summary response is still running (it should have been removed when the prompt was reverted). It's harmless (fail-open) but noisy.

## Root cause analysis

The V0.5.7 regression has TWO root causes:

1. **The glossary call failed** (the LLM didn't output the `<name_glossary>` block). The fix:
   - Increase `max_output_tokens` from 4096 to 8192 (the glossary for 74 authors needs more space)
   - Apply `strip_thinking` / `qwen_no_think` to the glossary response (remove `<think>` tags before parsing)
   - OR make the prompt more explicit: "Start IMMEDIATELY with `<name_glossary>`. Do NOT output any thinking."

2. **The master-summary was short** (783 words → 27 bullets). This is LLM variance (the V0.5.6 run took the 5-in-1 fallback which produced 6,710 words / 83 bullets; the V0.5.7 run took the normal path which produced 783 words / 27 bullets). The normal master-summary path produces FEWER bullets than the 5-in-1 fallback. The fix:
   - Investigate why the master-summary is short (the model's output length varies)
   - OR ensure the gap-fill rounds close the gap (the loosened quote-guard + final-check would help — once the glossary works)

## Verdict

**REGRESSION (V0.5.7 ~7.25 vs V0.5.6 ~8.0)** — the Maj-sey fix worked (the regex garble is gone) + the master-summary no longer returns empty (the simpler prompt fixed the V0.5.6 bug), BUT the separate glossary call FAILED (the LLM didn't output the `<name_glossary>` block) + the coverage regressed (48/74 authors vs 69/75). The glossary features (loosened quote-guard, final-check) are still dormant.

## V0.5.8 backlog

1. **Fix the glossary call** — increase max_tokens to 8192 + apply strip_thinking + make the prompt more explicit ("Start IMMEDIATELY with `<name_glossary>`").
2. **Remove the V0.5.6 leftover fused-path parser** — the `ℹ️ V0.5.6: no <name_glossary> block parsed from master summary` log line should be removed (the master-summary prompt no longer asks for it).
3. **Investigate the short master-summary** — 783 words is short; the gap-fill should close the gap once the glossary works.
