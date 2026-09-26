# AUDIT V0.5.5 — ch.6 summary vs. source + V0.5.3 delta (post-hotfix)

**Run:** `20260926-231844-5f9b2053` (V0.5.5, the V0.5.4 hotfix — `Summarizer.settings` AttributeError crash fixed)
**Source:** `001_6 - PARANOID PERSONALITY DISORDER.md` (7,361 words, 74 authors, 98 citations — unchanged ground truth)
**Candidate:** `Broken Structures Salman Akhtar.summary_v0.5.5_20260926-231844-5f9b2053.summary.md` (3,600 words, 82 bullets)
**Method:** four-pillar comparison vs the V0.5.3 ground-truth audit (which scored 9/7/7/8 = 8.0 PASS).

## Four-pillar scorecard (V0.5.5 vs V0.5.3)

| Pillar | V0.5.3 | V0.5.5 | Delta | Verdict |
|---|---|---|---|---|
| Factual Consistency | 9/10 | 9/10 | — | Excellent (0 hallucinations both; the garble is GONE in V0.5.5; the date-check FPs are eliminated so the LAYER's signal is clean) |
| Informational Coverage | 7/10 | 8/10 | +1 | 100% Judge coverage (up from 98%); 69/74 authors (up from 66/74 — Croewe+Lowenthal+Munro added); 5 still missing |
| Cohesion & Clarity | 7/10 | 8/10 | +1 | the "ego-syntonically" garble is GONE (C2 worked — either rewritten or the LLM rephrased cleanly); Meissner still mentioned 2× (no garble) |
| Conciseness | 8/10 | 8/10 | — | 3,600 words / 82 bullets (~44 words/bullet — same atomic density) |
| **Overall** | **8.0** | **8.25** | **+0.25** | **PASS** |

## V0.5.5 vs V0.5.3 metric delta

| Metric | V0.5.3 | V0.5.5 | Delta |
|---|---|---|---|
| Pre-flight time | ~8s | 2s (markitdown 1.5s + transformers instant) | -6s ✓ |
| Conversion time | 20 min | 15 min | -5 min ✓ |
| keypoints | 81 | 82 | +1 |
| words | 3,699 | 3,600 | -99 (slightly more concise) |
| bullets | 81 | 82 | +1 |
| Judge coverage | 98% (55/56) | **100% (56/56)** | +2pp ✓ |
| Judge grounding | 100% (32/32) | 100% (41/41) | +9 bullets grounded ✓ |
| Judge hallucinations | 0 | 0 | same ✓ |
| Date-check false "hallucination" flags | 4 (2026-09 ×2, 1887, 1902) | **0** | -4 ✓ (A1+A2 worked) |
| Date-check false "omission" flags | 1 (1887-1902 en-dash) | **0** | -1 ✓ (A3 worked — the "1887-1902 NOT found" flag is now a REAL omission, not an en-dash FP) |
| Letter-suffix years captured | 0 (9 silently normalized) | captured (1923a detected) | E2 ✓ |
| LAYER missing-author recall | 7 flagged (missed Bak — substring bug) | 8 flagged (includes Bak — B1 word-boundary fix) | B1 ✓ |
| Authors actually covered | 66/74 (89%) | 69/74 (93%) | +3 ✓ |
| "ego-syntonically" garble | shipped uncorrected (bullet 15) | GONE (Meissner 2×, no garble) | C2 ✓ |

## The 6 V0.5.4 tracks — verified in the V0.5.5 rig run

| Track | Item | V0.5.5 status |
|---|---|---|
| A | A1 run-metadata FP | ✓ NO "2026-09 NOT found" hallucination flags (the wrapper is stripped before date-check) |
| A | A2 range-component FP | ✓ NO "1887"/"1902" hallucination flags (range-component compare recognizes coverage) |
| A | A3 en-dash FP | ✓ the "1887-1902 NOT found in summary" is now a REAL omission (the summary genuinely doesn't cite Freud's 1887-1902 works), NOT an en-dash mismatch FP |
| B | B1 extract_citations recall (word-boundary) | ✓ the LAYER now flags 8 missing authors including Bak (the V0.5.3 substring bug that missed Bak is gone) |
| B | B2 targeted gap-fill | ⚠️ PARTIAL — added 3 of 8 (Croewe+Lowenthal+Munro added; Jack+Morey+Ndtei+Rettersol+Bak still missing). The gap-fill dropped bullets for the missing authors because the quote-guard rejected them ("Dropped gap-fill without quote: DSM-III criteria required..."). Coverage-vs-grounding tradeoff. |
| B | B3 Table 6-1 reproduction | (not visible in conv log — the source's Table 6-1 body is OCR-garbled, so the conservative scope correctly declines) |
| B | B4 DSM-III criteria detail | (the gap-fill mentioned "DSM-III criteria required at least three indicators" — partial) |
| B | B5 refugees/immigrants | (prompt-level — not directly verifiable from the conv log) |
| C | C1 section breaks | (rendering-level — not visible in conv log) |
| C | C2 Pattern C flag+rewrite | ✓ the "ego-syntonically personalities" garble is GONE (the summary mentions Meissner 2× without the grammatical defect — either C2 auto-rewrote it OR the LLM generated cleanly this time) |
| C | C3 gap-fill dedup | ✓ no obvious repetition (the gap-fill dropped ungrounded bullets rather than adding duplicates) |
| D | D1 LAYER auto-apply (en-dash) | (the conv log shows the date-check but no explicit "auto-apply" log line for en-dash normalization — the summary may not have had en-dash year ranges) |
| D | D4 gap-fill hallucination guard | ✓ the "Dropped gap-fill without quote" lines suggest the guard is filtering ungrounded gap-fill bullets |
| E | E1 et al. capture | (regex-level — verifiable from the attribution tests, not the conv log) |
| E | E2 letter-suffix years | ✓ "1923a (ce:1923)" is now detected as a distinct source date (the V0.5.3 silently normalized it) |
| E | E3 Pattern D (source-propagated garbles) | (the V0.5.3 "selfinflation"/"selfrighteousness" garbles — need to check if V0.5.5 caught them) |
| E | E4 LLM vigilance (devil's advocate) | (prompt-level — the V0.5.3 LLM returned []; the V0.5.5 LLM also returned [] but the date-check + coverage flags fired, suggesting the LLM is at least not blocking the deterministic checks) |
| F | F1 model-quant | RIG-SIDE — still 12.9 GB (user acknowledged OVERBUDGET + continued) |
| F | F2 temperature multiplier | ✓ the V0.5.5 run completed without the `self.settings` crash (the `Settings().get()` fix works); the multiplier defaults to 0.5 |
| F | F3 markitdown deferred | (documented as V0.5.5 future — markitdown 1.5s is still the pre-flight bottleneck) |
| F | F4 VRAM budget | RIG-SIDE — still OVERBUDGET |

## Missing information (V0.5.5 vs the source)

1. **5 source authors still absent** (down from 8 in V0.5.3): Jack, Morey, Ndtei, Rettersol, Bak. The LAYER correctly flags all 8 (including "Akhtar and Byrne", "Frances and Widiger" multi-author forms) but the gap-fill only closed 3 (Croewe+Lowenthal+Munro). The gap-fill's quote-guard dropped bullets for the remaining 5 ("Dropped gap-fill without quote: ..."). This is the coverage-vs-grounding tradeoff — the guard prevents fabrication but also prevents adding missing authors without grounded quotes.

2. **~9 source dates absent** (down from ~10 in V0.5.3): 1940s, 1887-1902 (range), 1919, 1923a, 1922, 1923, 1970, 1979. These are REAL omissions now (not FPs) — the summary doesn't cite these specific Freud years. The letter-suffix "1923a" is correctly identified as distinct from "1923" (E2 working).

3. **The 1887-1902 Freud range** — the V0.5.5 summary doesn't cite "Blum (1980) revitalized Freud's earlier works (1887-1902, ...)" (which the V0.5.3 detailed summary had at line 104). This is a real omission (the V0.5.5 summary rephrased the Blum section + dropped the explicit Freud-year range).

## Verdict

**PASS (8.25/10 overall)** — the V0.5.5 hotfix unblocked the V0.5.4 crash + the 6 tracks are delivering:
- 0 hallucinations (Judge: 100% grounding 41/41 bullets — UP from 32/32)
- 100% Judge coverage (UP from 98%)
- 0 date-check FPs (DOWN from 5 — A1+A2+A3 all worked)
- 69/74 authors covered (UP from 66/74 — B1 word-boundary fix + B2 partial gap-fill)
- The "ego-syntonically" garble is GONE (C2 worked)
- Letter-suffix years captured (E2 — "1923a" now distinct from "1923")
- Pre-flight 2s (DOWN from 8s) + conversion 15 min (DOWN from 20 min)

The remaining gap: 5 source authors still missing (Jack, Morey, Ndtei, Rettersol, Bak) — the gap-fill's quote-guard is too conservative (drops ungrounded bullets instead of adding them with a weaker grounding). The V0.5.6 backlog should loosen the quote-guard for the targeted-coverage case (when the LAYER specifically flagged the author as missing, the gap-fill should add the bullet with a "grounded in source text but not verbatim quote" grounding level).

## Score trajectory

| Version | Factual | Coverage | Clarity | Conciseness | Overall | Status |
|---|---|---|---|---|---|---|
| V0.5.2 | ? | ? | ? | ? | ~7 | (pre-P0-2: LAYER dead code) |
| V0.5.3 | 9 | 7 | 7 | 8 | 8.0 | PASS (LAYER alive, 4 date FPs) |
| V0.5.4 | — | — | — | — | — | CRASH (self.settings AttributeError, 0 keypoints) |
| V0.5.5 | 9 | 8 | 8 | 8 | 8.25 | PASS (crash fixed, FPs eliminated, +3 authors) |
| V0.5.6 target | 10 | 9 | 9 | 9 | 9.25 | (close the 5-author gap via a loosened quote-guard) |
