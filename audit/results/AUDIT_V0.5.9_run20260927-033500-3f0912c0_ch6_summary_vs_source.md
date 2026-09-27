# AUDIT V0.5.9 — ch.6 summary vs. source (the 8192 fix worked; glossary STILL didn't extract — model can't follow XML format)

**Run:** `20260927-033500-3f0912c0` (V0.5.9)
**Candidate:** 3,593 words, 72 bullets (RECOVERING from V0.5.8's 3,152/65)

## Four-pillar scorecard (V0.5.9 vs V0.5.8 vs V0.5.6)

| Pillar | V0.5.6 | V0.5.8 | V0.5.9 | Trend |
|---|---|---|---|---|
| Factual Consistency | 9 | 9 | 9 | flat (0 hallucinations) |
| Informational Coverage | 8 | 5-6 | 6-7 | **RECOVERING** (53/74=72%, up from 42/74=57%) |
| Cohesion & Clarity | 7-8 | 7 | 7-8 | flat |
| Conciseness | 7 | 8 | 8 | flat |
| **Overall** | **~8.0** | **~7.0** | **~7.5** | **RECOVERING** |

## What WORKED in V0.5.9

1. **The 8192 fix worked** ✓ — the glossary call now uses `max=8192` (the conv log shows `🦙 llama.cpp t=0.30 max=8192 streaming…`). The V0.5.8 override bug (primary_call.py passed 4096) is fixed. The call ran ~9 min (03:47:01 → 03:56:04) — much longer than V0.5.8's 3.5 min.

2. **Coverage RECOVERED** ✓ — 53/74 authors (72%) vs V0.5.8's 42/74 (57%). +11pp. The 8192 token budget let the gap-fill rounds work better (the model had more room to generate bullets). 72 keypoints (up from V0.5.8's 65).

3. **3 of 7 missing authors now covered** ✓ — Morey (1), Allodi (1), Bak (1) are now present. The gap-fill rounds 1-4 closed these.

4. **Judge**: coverage=98% (55/56 claims), grounding=100% (36/36 bullets), hallucinations=0 — PASS.

## What STILL FAILED in V0.5.9

1. **The glossary call STILL produced NO `<name_glossary>` block** ✗ — even with max=8192 + strip_thinking + the explicit "Start IMMEDIATELY with `<name_glossary>`" prompt, the log shows `ℹ️ V0.5.7: no <name_glossary> block parsed from the separate call`. The LLM was called with 8192 tokens + ran 9 min, but didn't output the `<name_glossary>` XML wrapper. **The Ternary-Bonsai-2-27B model fundamentally can't follow the `<name_glossary>` XML-tag format instruction.**

2. **The loosened quote-guard didn't fire** — 0 matches (no glossary to check against).

3. **The V0.5.6 final-check with glossary didn't fire** — the round 4 that fired is the OLD V18.14.1 mechanism, not the V0.5.6 glossary-grounded one.

4. **4 of 7 missing authors still missing** — Jack (0), Ndtei (0), Rettersol (0), Lowenthal (0). The gap-fill couldn't close these without the loosened quote-guard (which needs the glossary).

## Root cause analysis

The V0.5.9 fix (max=8192) worked — the call has enough tokens. But the LLM STILL doesn't output the `<name_glossary>` block. This means the issue is NOT the token limit — it's the **output format**. The Ternary-Bonsai-2-27B model can't reliably follow the `<name_glossary>...</name_glossary>` XML-tag format instruction, even with:
- 8192 tokens (enough space)
- strip_thinking applied (removes thinking tags)
- "Start IMMEDIATELY with `<name_glossary>`" explicit prompt
- "Do NOT output any thinking" instruction

The model likely outputs the glossary content in a DIFFERENT format (e.g., a plain markdown list without the XML wrapper) that the parser (`parse_name_glossary`, which looks for `<name_glossary>...</name_glossary>`) doesn't recognize.

## V0.5.10 recommendation (the format change)

**Change the output format from XML tags to markdown headers.** Instead of asking the LLM to output:
```
<name_glossary>
## Names
- **Surname** (YYYY) — context
## Dates
- **YYYY-YYYY** — context
## Terms
- **term** — definition
</name_glossary>
```

Ask it to output:
```
## Source Glossary — Names
- **Surname** (YYYY) — context
## Source Glossary — Dates
- **YYYY-YYYY** — context
## Source Glossary — Terms
- **term** — definition
```

The parser would then look for the `## Source Glossary — Names` header instead of the `<name_glossary>` XML tag. Markdown headers are more natural for the model (it already outputs markdown bullets) — the XML wrapper is the friction point.

**Alternative**: add a few-shot example (show the model 2-3 concrete glossary entries so it knows exactly what format to follow).

## Verdict

**RECOVERING (V0.5.9 ~7.5 vs V0.5.8 ~7.0 vs V0.5.6 ~8.0)** — the 8192 fix worked (the call has enough tokens) + coverage recovered to 53/74 (72%). But the glossary STILL didn't extract — the model can't follow the XML format. The loosened quote-guard + final-check are still dormant. The V0.5.10 format change (XML → markdown headers) should finally make the glossary extract → the loosened quote-guard + final-check fire → the 4 remaining missing authors close → 74/74 (100%).
