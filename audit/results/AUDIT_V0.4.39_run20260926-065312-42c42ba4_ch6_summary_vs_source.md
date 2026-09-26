# AUDIT — Summary vs Source — version V0.4.39 (run 20260926-065312-42c42ba4) — ch.6

> Four-pillar expert fact-checker audit, **the NINTH round** on the same chapter
> (the V0.4.39 release shipped TWO general improvements per the user's
> "do only general improvements" direction: **Option A** — generalize the
> D3 LLM-repair pattern to garbles, `repair_garbles_via_llm` wired into all
> three postcheck fields (commits `324928b` + `31c3997`); **Option B** —
> general detector edge-case characterization on non-ch.6 fixtures). The
> V0.4.38 audit's ch.6-specific F1 (source-grounded auto-repair for
> "betrayale"/"paranoias") was DROPPED as overfitting.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol / Rule 4)

| Field | Stamp | Notes |
|---|---|---|
| `app_version` | `0.4.39` | Matches the V0.4.39 release (tag `V0.4.39` @ `9ec034b`, force-pushed to the finalized state); VERSION file = `0.4.39` |
| `run_id` | `20260926-065312-42c42ba4` | Matches conversion-log line 5 + summary line 3 |
| `started` | `2026-09-26T06:53:12` (conversion log) / `06:56:27` (summary) | Consistent (summary stamp = post-dedup final write) |
| `bullets` | `73` | Matches summary line 3 + conv-log line 983 ("Total bullets: 73") — UP from V0.4.38's 63 |
| Conversion-log companion stamp (line 5) | ✅ Present, matches summary | `run_id=20260926-065312-42c42ba4` |
| V0.4.39 Option A (commit `324928b` + finalization `31c3997`) | ✅ Present: `core/summarisation/postchecks/garble/garble_repair.py` + wired into all 3 postcheck fields (field_phases.py — `repair_garbles_via_llm` appears 3×) | Verified — NOT exercised this run (0 garble flags; the model produced clean output) |
| Source chapter | `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words) | UNCHANGED across all 9 audits |
| Rig model | `Ternary-Bonsai-2-27B-Instruct-Vision` (conv-log line 113) | IDENTICAL to V0.4.36/V0.4.37/V0.4.38 — the quality delta is LLM variance (same model, temp 0.7) |

**Provenance verdict: ✅ STAMPED + CONSISTENT.** Audit may proceed.

---

## Part 1 — Detailed Report

### Step 1 — The V0.4.39 fixes (did they fire on the rig?)

**1. Option A — garble LLM-repair (all three fields): NOT exercised (0 garbles this run).**

  V0.4.38 shipped 2 detected+flagged garbles ("betrayale" thorough + "paranoias" bullet). **V0.4.39: 0 `fragment_merge` + 0 `dropped_letter` + 0 `sentence_fusion` flags** (conv-log) — the model produced CLEAN output this run (LLM variance). Grep of the shipped summary confirms NONE of "betrayale"/"paranoias"/"selfinflation"/"selfrighteousness" appear. So `repair_garbles_via_llm` did NOT fire (no garble flags → the `_garble_flags` guard short-circuits). Option A is validated in-sandbox (`test_v0438_audit_fixes.py::TestV0439OptionAGarbleLLMRepair`, 5 mock-LLM tests) + the wiring is present (source-pin: `repair_garbles_via_llm` appears 3× in field_phases — bullets + exec + thorough). ✅ available + validated; not exercised this run.

**2. F2 — 4th dedicated-thorough attempt: NOT triggered (the model produced a long-enough thorough).**

  V0.4.38's dedicated-expansion returned 696 words on all 4 attempts (F2 fired but didn't recover). **V0.4.39: the primary-call thorough was 6807 chars / 1180 words** (conv-log line 505) — ≥ the 800-word dedicated-expansion threshold → the dedicated-expansion was NOT triggered → F2's 4th attempt didn't fire. The model produced a long-enough thorough this run (LLM variance). ✅ available; not triggered this run.

**3. F3/F4/F5 (V0.4.38 fixes): still in effect, no false-positives.**

  - F3 (fragment_merge lexicon): 0 fragment_merge flags (no "theme"-class FP).
  - F4 (bold-name structural-label): 0 bold-name attribution flags (the summary ships `**Conclusions**:` + structural labels — none flagged).
  - F5 (self-compound hyphen): 0 hyphen defects shipped (no "selfinflation"/"selfrighteousness").
  - F6 (V0.4.37 render-boundary stray-quote sweep): 0 odd-count quote lines shipped (verified per-line).
  - F7 (V0.4.37 grammar 3rd-singular + attribution thorough threshold): 0 grammar "no main verb" flags; 0 thorough attribution flags (the V0.4.38 had 2: Jaspers 38% + Bursten 39% — both below the 40% thorough threshold. V0.4.39 has 0 thorough attribution flags → the model's thorough claims were above 40% this run).

**Step-1 verdict: the V0.4.39 code is VALIDATED (it didn't break anything; the run is clean) but the V0.4.39-specific fixes (Option A, F2) were NOT exercised this run — the model produced clean, long output (LLM variance). The fixes are available + in-sandbox-validated for when the model produces garbles/short output.**

### Step 2 — Hallucination check (0 hallucinations shipped ✅)

Grep of the shipped summary: NONE of "Jack"/"Ndtei"/"Green" appear as cited authors. The recall floor (conv-log line 889) lists "Jack" as missing (fabricated, dropped pre-ship by the attribution-edge check). The "Missing X. [quote]" bullets (lines 52-54) quote REAL source text — verified against source:
- line 52 "grandiosity (Heimann 1952...)" → source line 344 ✓
- line 53 "the compulsive knows that the pressure to conform emanates from within himself" → source line 530 ✓
- line 54 "The silently resentful outcome may be more frequent among women" → source line 597 ✓

So the "Missing" bullets quote accurate source text (not fabricated). **0 hallucinations shipped** ✅.

### Step 3 — Factual Consistency (Score: 9, flat vs V0.4.38's 9)

- 0 fabricated claims; 0 fabricated years; 0 fabricated author attributions.
- The 3 "Missing X. [quote]" bullets (lines 52-54) are a factual-PRESENTATION issue: the bullet says "Missing X" then quotes a source excerpt that CONTAINS X. The consistency detector correctly flags the false "missing" claim (conv-log lines 775/777/779: "false 'missing' claim — 4/5 or 5/6 of the concept's words DO appear in the source"). The "Missing" claim is misleading (X is in the source), but the quoted text is accurate. One class of mild factual-presentation defect.
- 1 attribution-mismatch flag: bullet[28] Magnan (1893) 44% (below the 50% bullet threshold → correctly flagged; a genuine borderline paraphrase).
- Spot-checks: Magnan 1893 "bouffee delirante des degeneres" (source ✓), Kraepelin 1921a "great sexual excitability" (source ✓), Bleuler 1908 "geographical moves" (source ✓), Blum 1981 "inconstant object" (source ✓), Bergman 1971/1978 "better adjustments to aging" (source ✓).

Score 9 (flat — 0 hallucinations; one mild "false missing claim" class + 1 attribution borderline).

### Step 4 — Informational Coverage (Score: 7, ↑ from V0.4.38's 6 — the "4 pillars all ≥7" target RE-MET)

- **Bullets recall floor: 53/74 = 72%** (conv-log line 987). Roughly flat vs V0.4.38's 74% (−2pp); up from V0.4.37's 70%.
- **Thorough coverage: 30/74 → 40/74 = 54%** (post-gap-fill; conv-log line 887). ↑ from V0.4.38's 39% (**+15pp**). The thorough STARTED at 30/74 (higher than V0.4.38's 21/74 — the model produced a longer, better-coverage thorough); the F3 coverage-driven gap-fill gained +10 (30→40) vs V0.4.38's +8 (21→29).
- **Bullets shipped: 73** (↑ from V0.4.38's 63).
- **Thorough words: 1180** (8 paragraphs) — the primary call produced a long-enough thorough (no dedicated-expansion needed).
- **Root cause: LLM variance** (same model). The model produced a 1180-word thorough covering 30/74 (vs V0.4.38's 696-word / 21/74). NOT a V0.4.39 code change (Option A + F2 weren't exercised); the model's output is the driver.

The campaign's "4 pillars all ≥7" target is **RE-MET** — coverage 7 ✓ (for the first time since V0.4.36's 8). The binding constraint: NONE (all 4 pillars ≥7). Score 7.

### Step 5 — Cohesion & Clarity (Score: 7, ↑ from V0.4.38's 6)

- The thorough ships as **8 paragraphs** (the V0.4.36 F3 paragraph-breaking continues to work). ✅
- **0 garbles shipped** (0 fragment_merge/dropped_letter/sentence_fusion flags; 0 known garbles). ✅ — a clean run (vs V0.4.38's 2 shipped garbles).
- **3 "Missing X. [quote]" bullets** (lines 52-54) — a model-output quirk: the bullet says "Missing X" then quotes a source excerpt containing X. These read oddly (a "missing" claim immediately followed by the quoted content that IS present). The consistency detector flags them (advisory). This is a clarity defect (the bullets are confusing) but not a garble/hallucination.
- **~15 `quote_verification` fixes** stripped non-verbatim quote spans (conv-log lines 789-819) — correct behavior; 0 odd-count quote lines shipped (F6 clean).
- The exec is 3 paragraphs, well-structured. Key Distinctions + Theoretical Tensions are well-formed.

Score 7 (↑ from V0.4.38's 6 — the 2 garbles are gone; the 3 "Missing" bullets keep it from 8).

### Step 6 — Conciseness vs Vagueness (Score: 8, flat vs V0.4.38's 8)

- The thorough is **1180 words** (8 paragraphs) — reasonable length (vs V0.4.38's 1079; vs V0.4.36's ~2000).
- Bullets: 73 (vs V0.4.38's 63) — more, no vagueness regression.
- The bullets remain specific (e.g. line 41 Magnan's "bouffee delirante des degeneres" verbatim; lines 80-82 the enumerated-list bullets verbatim from source).
- Score 8 (flat — concise, no vagueness).

---

## Part 2 — JSON Scorecard

```json
{
  "version": "0.4.39",
  "run_id": "20260926-065312-42c42ba4",
  "chapter": "6 - PARANOID PERSONALITY DISORDER",
  "scorecard": {
    "factual_consistency": 9,
    "informational_coverage": 7,
    "cohesion_clarity": 7,
    "conciseness_vs_vagueness": 8
  },
  "hallucinations_shipped": 0,
  "garbles_shipped": 0,
  "bullets_shipped": 73,
  "bullets_recall_floor": "53/74 (72%)",
  "thorough_coverage_post_gapfill": "40/74 (54%)",
  "thorough_words_shipped": 1180,
  "fixes_exercised_on_rig": [],
  "fixes_available_not_exercised": ["Option A garble LLM-repair (0 garbles this run)", "F2 4th dedicated-thorough attempt (thorough 1180w >= 800, not triggered)"],
  "false_missing_claim_bullets": 3,
  "verdict": "PASS (re-met the '4 pillars all >=7' target for the first time since V0.4.36). The V0.4.39 run is CLEAN (0 garbles, 0 hallucinations, coverage improved to thorough 54%). The V0.4.39 code fixes (Option A, F2) were NOT exercised — the model produced clean, long output (LLM variance); they're validated in-sandbox + available when needed."
}
```

---

## Conversion-log review (the four-pillar + provenance cross-check)

### A. Provenance stamp
✅ Conversion-log line 5: `<!-- generated-by: Elixir v0.4.39 | run_id=20260926-065312-42c42ba4 -->` — matches summary line 3. Rule 4 satisfied.

### B. Deadline + runtime
- Conversion started 06:53:12, finished 07:10:31 (~17 min / 1,039s). Deadline NOT exceeded (the V0.4.38 had no overrun either; V0.4.37 did).

### C. The Option A garble LLM-repair (NOT exercised)
Conv-log: 0 `garble_llm_repair` issues (the `_garble_flags` guard short-circuits when no fragment_merge/dropped_letter flags). 0 garble flags this run → Option A didn't fire. The wiring is present (source-pin: `repair_garbles_via_llm` appears 3× in field_phases). Validated in-sandbox. ✅ available; not exercised.

### D. The F2 4th dedicated-thorough attempt (NOT triggered)
Conv-log: the primary-call thorough was 6807 chars / 1180 words (line 505) — ≥ the 800-word dedicated-expansion threshold → the dedicated-expansion block didn't fire → F2's 4th attempt didn't fire. The V0.4.38 case (best=696<800) didn't recur. ✅ available; not triggered.

### E. The shipped output (clean)
- 0 garbles (0 fragment_merge/dropped_letter/sentence_fusion flags).
- 0 hallucinations (Jack fabricated, dropped pre-ship; the "Missing" bullets quote real source text).
- 0 odd-count quote lines (F6 clean).
- 1 attribution flag (bullet 28 Magnan 44% — genuine borderline).
- 3 consistency flags (the "Missing X. [quote]" false-missing-claim class — advisory).
- 2 truncated enumeration-guarantee EXEMPT flags (correct).
- ~15 quote_verification fixes (stripped non-verbatim spans — correct).

### F. Coverage floor
- Bullets recall: 53/74 = 72% (line 987).
- Thorough: 30/74 → 40/74 = 54% post-gap-fill (line 887). The thorough STARTED at 30/74 (higher than V0.4.38's 21/74).
- Missing from bullets (recall floor): ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Jack'] — 'Jack' fabricated (dropped pre-ship); the others are real source authors not in the bullets.

### G. The V0.4.39+ commit lineage
- `324928b` Option A + B (garble LLM-repair + general edge-case tests) · `3ea5790` release V0.4.39 · `31c3997` finalization (extend garble repair to bullets + exec) · `9ec034b` docs · Tag `V0.4.39` force-pushed to `9ec034b` (the finalized state).

---

## Nine-audit delta table (V0.4.31 → … → V0.4.39)

| Pillar / metric | V0.4.31 | … | V0.4.36 | V0.4.37 | V0.4.38 | **V0.4.39** | Δ vs V0.4.38 |
|---|---|---|---|---|---|---|---|
| Factual consistency | 8 | … | 10 | 9 | 9 | **9** | flat (0 halluc; 3 "false missing" bullets) |
| Informational coverage | 6 | … | 8 | 6 | 6 | **7** | **+1 (thorough 39%→54%; target re-met)** |
| Cohesion & clarity | 7 | … | 8 | 7 | 6 | **7** | +1 (0 garbles shipped) |
| Conciseness vs vagueness | 6 | … | 7 | 8 | 8 | **8** | flat |
| Hallucinations shipped | 0 | … | 0 | 0 | 0 | **0** | flat ✅ |
| Garbles shipped | — | … | 0 | 1 (undetected) | 2 (detected, unrepaired) | **0** | **−2 (clean run; Option A not exercised)** |
| Bullets shipped | — | … | 79 | 67 | 63 | **73** | +10 |
| Bullets recall floor | — | … | 59/74 (80%) | 52/74 (70%) | 55/74 (74%) | **53/74 (72%)** | −2pp |
| Thorough coverage (post-gap-fill) | — | … | 48/74 (65%) | 31/74 (42%) | 29/74 (39%) | **40/74 (54%)** | **+15pp** |
| Dedicated-expansion best | — | … | — | 793w (3 att) | 696w (4 att, F2 fired) | **1180w (primary; no dedicated call)** | F2 not triggered |
| Verdict | borderline | … | **PASS (solid)** | REGRESSION | REGRESSION | **PASS (re-met target)** | — |

---

## Verdict + recommended V0.4.40 backlog

> **Verdict: PASS — the "4 pillars all ≥7" target is RE-MET (for the first time since V0.4.36's 10/8/8/7).**

The V0.4.39 run is CLEAN: 0 garbles shipped (vs V0.4.38's 2), 0 hallucinations, coverage improved (thorough 39%→54%, +15pp; bullets 72% roughly flat). **All 4 pillars ≥7** (9/7/7/8) — the binding constraint is NONE.

**Important caveat: this is LLM VARIANCE, not a V0.4.39 code win.** The V0.4.39-specific fixes (Option A garble LLM-repair, F2 4th dedicated-thorough attempt) were NOT exercised this run — the model produced clean, long output (the same Ternary-Bonsai-2-27B model that produced garbles + a 696-word thorough in V0.4.38 produced a clean 1180-word thorough covering 40/74 in V0.4.39). The V0.4.39 code is VALIDATED (it didn't break anything; the run is clean) + the fixes are in-sandbox-validated + available for when the model produces garbles/short output. But the V0.4.39→V0.4.38 quality jump is LLM-driven, not code-driven.

### V0.4.40 backlog (thin — the run is clean)

1. **(LOW — observability) The "Missing X. [quote]" bullet class:** the V0.4.39 model produced 3 bullets that say "Missing X" then quote a source excerpt containing X (lines 52-54; consistency flags). The "missing" claim is false (X is in the source, in the quote) but the quoted text is accurate — a clarity/factual-presentation quirk, not a hallucination. The consistency detector already flags these (advisory). A future general improvement could DROp this class (like the truncated-bullet drop) since the "Missing X. [quote]" shape is confusing + the claim is false — but dropping reduces coverage, so it's a trade-off. General (any chapter where the model produces "Missing X" bullets), not ch.6-tuned.
2. **(NONE — code) Coverage:** still below V0.4.36's level (thorough 54% vs 65%; bullets 72% vs 80%) but LLM variance — no code fix needed (F3 coverage-driven gate + F2 4th attempt are available).

---

## Artifacts

- Summary: `audit/results/bench_v0439_ch6_paranoid/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.39_20260926-065312-42c42ba4_summary.md` (125 lines, 73 bullets)
- Conversion log: `audit/results/bench_v0439_ch6_paranoid/Broken Structures Salman Akhtar_v0.4.39_20260926-065312-42c42ba4.conversion.log.md` (1039 lines)
- Source: `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words — unchanged across all 9 audits)
- Release: tag `V0.4.39` @ `9ec034b` (force-pushed to the finalized state); release zip `/home/z/my-project/download/Elixir-V0.4.39.zip` (4.75 MB, 865 entries)
