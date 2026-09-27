# AUDIT V0.5.8 — ch.6 summary vs. source (the glossary call STILL failed — max_output_tokens override)

**Run:** `20260927-030000-012fba8a` (V0.5.8)
**Candidate:** 3,152 words, 65 bullets (REGRESSED from V0.5.6's 6,710/83; slightly up from V0.5.7's 3,273/60)

## Four-pillar scorecard (V0.5.8 vs V0.5.7 vs V0.5.6)

| Pillar | V0.5.6 | V0.5.7 | V0.5.8 | Trend |
|---|---|---|---|---|
| Factual Consistency | 9 | 9 | 9 | flat (0 hallucinations) |
| Informational Coverage | 8 | 6 | 5-6 | **REGRESSION** (42/74=57%) |
| Cohesion & Clarity | 7-8 | 7 | 7 | flat |
| Conciseness | 7 | 8 | 8 | flat |
| **Overall** | **~8.0** | **~7.25** | **~7.0** | **REGRESSION** |

## What WORKED in V0.5.8

1. **The V0.5.6 leftover noise is GONE** ✓ — 0 matches for "V0.5.6: no <name_glossary> block parsed from master summary" (Fix 4 worked — the fused-path parser was removed).

2. **The master-summary succeeded** ✓ — no empty returns (the V0.5.7 simpler-prompt fix holds).

## What FAILED in V0.5.8

1. **The glossary call STILL produced NO `<name_glossary>` block** ✗ — the log shows `ℹ️ V0.5.7: no <name_glossary> block parsed from the separate call`. **ROOT CAUSE FOUND**: the conv log shows `🦙 llama.cpp t=0.30 max=4096 streaming…` — the V0.5.8 fix raised the DEFAULT to 8192, BUT the caller in `primary_call.py` passed `max_output_tokens=4096` explicitly, OVERRIDING the default. The LLM still hit the 4096 limit before finishing the glossary.

2. **Coverage REGRESSED further** ✗ — 42/74 authors (57%) vs V0.5.7's 48/74 (65%) vs V0.5.6's 69/75 (92%). The gap-fill rounds 1-4 added 6/8 bullets in round 4, but 30 theorists are still missing (Byrne, Akhtar and Byrne, Winokur, Kohut, Fenichel, Bergman, Allodi, Jack, Ndtei, Bursten, Green...). The loosened quote-guard + final-check didn't fire (no glossary).

3. **The 5 missing authors are STILL missing** ✗ — Jack (0), Allodi (0), Morey (0), Ndtei (0), Rettersol (0), Lowenthal (0). Only Bak (1) is present.

## Root cause analysis

The V0.5.8 fix was **INCOMPLETE**: the `extract_glossary_via_llm` default was raised to 8192, but the CALLER in `primary_call.py:172` passed `max_output_tokens=4096` explicitly, overriding the default. The conv log confirms `max=4096` (not 8192). The LLM still hit the 4096 limit before finishing the `<name_glossary>` block.

**The V0.5.9 fix**: change `primary_call.py:172` from `max_output_tokens=4096` to `max_output_tokens=8192`. This is a 1-line fix that makes the V0.5.8 changes actually take effect.

## V0.5.8 vs V0.5.7 vs V0.5.6 metric delta

| Metric | V0.5.6 | V0.5.7 | V0.5.8 |
|---|---|---|---|
| keypoints | 83 | 60 | 65 |
| words | 6,710 | 3,273 | 3,152 |
| Author coverage (deterministic floor) | 69/75 (92%) | 48/74 (65%) | 42/74 (57%) |
| Glossary call max_tokens | (n/a — fused) | 4096 | 4096 (should be 8192 — the override bug) |
| Glossary extracted | 0 | 0 | 0 (STILL failed) |
| V0.5.6 leftover noise | present | present | GONE ✓ |

## Verdict

**REGRESSION (V0.5.8 ~7.0 vs V0.5.7 ~7.25 vs V0.5.6 ~8.0)** — the V0.5.6 leftover removal worked (Fix 4), BUT the glossary call STILL failed because the caller overrides max_output_tokens to 4096 (the V0.5.8 default change to 8192 didn't take effect). Coverage regressed further to 42/74 (57%). The V0.5.9 fix (1-line: change the caller to 8192) should make the glossary actually extract.

## The V0.5.9 fix (released alongside this audit)

The V0.5.9 fix: `primary_call.py:172` — `max_output_tokens=4096` → `max_output_tokens=8192`. This makes the V0.5.8 changes (the default raise + strip_thinking + the explicit prompt) actually take effect. Expected: the glossary will finally be extracted (8192 tokens is enough for a 74-author glossary) → the loosened quote-guard + final-check will fire → the 5-author gap will close.
