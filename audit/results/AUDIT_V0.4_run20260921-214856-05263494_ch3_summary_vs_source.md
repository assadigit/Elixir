# AUDIT — Summary vs Source — version V0.4 (run 20260921-214856-05263494) — ch.3

> **Audit version:** `V0.4 / run 20260921-214856-05263494 / app 0.4 / 2026-09-21T21:48:56 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 3 "NARCISSISTIC PERSONALITY DISORDER"
> **Model:** ternary 27b bonsai, 100k context, 32768 max output (llama.cpp provider)
> **Chapter size:** 15,182 tokens / 9,407 words

---

## Provenance cross-check

| Field | Value | Match |
|---|---|---|
| `run_id` | `20260921-214856-05263494` | ✓ NEW (different from V0.3's `20260921-202342-dabcb4c3`) |
| `app_version` | `0.4` | ✓ **V0.4 confirmed** |
| `bullets` | `40` | ✓ |
| Conversion log | Old V0.18 log (SHA `3a443ff98cea42b5`) | 8th consecutive stale log |

---

## Part 1 — Detailed Report

### Fact-Check Log

I verified 31 of 33 sampled claims against the source — **all 31 found** (2 misses were regex variants, not factual errors). **0 hallucinations. 0 name garbles. 0 "Ayyedura jo".**

### 🚀 V0.4 improvements confirmed vs V0.3

| Metric | V0.3 ch.3 | V0.4 ch.3 | Change |
|---|---|---|---|
| "Ayyedura jo" garble | **1** (severe garble) | **0** | ✅ **GONE** — fuzzy garble repair OR the model produced it correctly this time |
| CoT markers | 0 | 0 | ✅ stable |
| Exec ≠ Thorough | 124w vs 1175w | **241w vs 1240w** | ✅ Defect D GONE (exec is a genuine concise summary) |
| Odd quote lines | 0 | 0 | ✅ stable |
| Unique theorists | 34 | **44** | ✅ **+10 theorists** (Adler, Akhtar, Fairbairn, Gediman, Guntrip, Khan, Kaplan, and more) |
| Thorough paragraphs | 3 | 3 | ✅ stable (natural paragraphs, no MANDATORY instruction) |
| Summary words | 2,621 | **2,738** | +117 words (more comprehensive) |
| Key Distinctions | 7 | 5 | -2 (slightly fewer, but all accurate) |
| Theoretical Tensions | 2 | **4** | ✅ +2 (better tension coverage) |

### Missing Information

1. **The chapter's opening epigraph** — not mentioned. Minor.
2. **The "clever baby" dream (Ferenczi 1923)** — present in V0.3 but absent from V0.4 (the V0.4 thorough covers different contributors).
3. **Nemiah's parental demands → harsh self-criticism** — present in the thorough but not as a distinct Key Takeaway.

### Quality Notes

- **Executive Summary (Excellent):** A clean, **241-word, 3-paragraph** executive summary. Distinct from the thorough (1240 words). Covers: (1) historical evolution from Freud → early analysts, (2) contemporary contributions from Kernberg/Kohut/Mahler, (3) clinical themes (overt/covert dichotomy, DSM critique, differential diagnosis, sociocultural debate). **The best exec summary the campaign has produced.**
- **Key Takeaways (Excellent):** 40 bullets, all specific and source-grounded. Each names the theorist AND states their specific contribution. No meta-narrative voice. No leaked instructions.
- **Thorough Summary (Excellent):** A **1240-word, 3-paragraph** flowing prose summary covering the full chapter from Freud through contemporary analysts, including the six-area clinical profile, DSM critique, differential diagnosis, and demographic/sociocultural conclusion. **No CoT, no garbles, no stray quotes.** The thorough is comprehensive and well-structured.
- **Key Distinctions (Good):** 5 distinctions, all accurate (normal vs pathological narcissism; NPD vs borderline; behavior vs personality disorders; NPD vs obsessional/hysterical; pseudosublimation vs mature sublimation).
- **Theoretical Tensions (Excellent):** 4 tensions (Kernberg vs Kohut; intrapsychic vs sociocultural; Kohut's five-type inconsistency; gender prevalence). **Best tension coverage so far.**

---

## Part 2 — Structured JSON Scorecard

```json
{
  "summary_id": "001_3_-_NARCISSISTIC_PERSONALITY_DISORDER__run20260921-214856-05263494_v0.4",
  "overall_score": 9,
  "factual_consistency_score": 9,
  "coverage_score": 9,
  "clarity_score": 9,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 3,
  "verdict": "PASS",
  "justification": "Factually flawless (0 hallucinations, 0 garbles, 0 'Ayyedura jo') with comprehensive coverage (9 — 44 theorists, six-area clinical profile, full differential diagnosis, DSM critique, demographic conclusion, 4 theoretical tensions) and excellent clarity (9 — 3-paragraph 1240-word thorough, 241-word 3-paragraph exec distinct from thorough, no CoT, no stray quotes). The V0.4 master-summary default + fuzzy garble repair delivered 9/10 on a 15k-token chapter via llama.cpp provider."
}
```

> **Mechanical verdict:** factual 9 ≥ 6, coverage 9 ≥ 5 → **PASS**. **At the 9/10 campaign bar!**

---

## Comparison across ALL versions and chapters

| Version | Chapter | overall | factual | coverage | clarity | Size | Provider | Key change |
|---|---|---|---|---|---|---|---|---|
| V0.18 | ch.1 | 7 | 9 | 6 | 8 | 8.5k | Ollama | (baseline) |
| V0.3 | ch.2 | **9** | 9 | 9 | 9 | 6k | Ollama | master-summary |
| V0.3 | ch.3 | 8 | 8 | 9 | 8 | 15k | llama.cpp | "Ayyedura jo" garble |
| **V0.4** | **ch.3** | **9** | **9** | **9** | **9** | **15k** | **llama.cpp** | **master-summary default + fuzzy garble repair** |

**V0.4 ch.3 reaches 9/10.** The "Ayyedura jo" garble is GONE (either the fuzzy repair caught it, or the model produced it correctly — either way, 0 garbles). The 44 theorists (up from 34) and 4 theoretical tensions (up from 2) show the V0.4 master-summary default is producing more comprehensive output. The exec is a genuine 241-word 3-paragraph summary (not a copy of the thorough). This is the campaign's best ch.3 scorecard.

### The full campaign progress

| Milestone | Score | Date |
|---|---|---|
| V0.18 baseline (ch.1) | 7/10 | 2026-09-20 |
| V0.20.2 CoT leak (ch.2) | 6/10 | 2026-09-21 |
| V0.20.3 CoT fixed (ch.2) | 8/10 | 2026-09-21 |
| V0.20.5 D3 backfired (ch.2) | 4/10 | 2026-09-21 |
| V0.3 master-summary (ch.2) | **9/10** | 2026-09-21 |
| V0.3 garble (ch.3) | 8/10 | 2026-09-21 |
| **V0.4 master-summary default + fuzzy garble (ch.3)** | **9/10** | **2026-09-21** |

**The campaign's objective — 9-10/10 on every audited book — is now achieved on ch.2 and ch.3.**
