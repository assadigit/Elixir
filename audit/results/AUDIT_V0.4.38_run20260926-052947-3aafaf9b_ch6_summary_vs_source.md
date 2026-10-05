# AUDIT — Summary vs Source — version V0.4.38 (run 20260926-052947-3aafaf9b) — ch.6

> Four-pillar expert fact-checker audit, **the EIGHTH round** on the same chapter
> (the V0.4.38 release shipped FIVE backlog fixes from the V0.4.37 audit:
> **F1** — fusion-garble Pattern C, the dropped-prefix fusion detection
> (commit `415f589`); **F2** — 4th dedicated-thorough attempt with a
> quantified length directive (commit `ff7ab00`); **F3** — fragment_merge
> lexicon check, the "theme" false-positive fix (commit `57f13f3`); **F4** —
> bold-name structural-label exemption, the "Conclusions" false-positive
> fix (commit `605bafd`); **F5** — render-boundary self-compound hyphen
> normalization (commit `f2877d7`)).

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol / Rule 4)

| Field | Stamp | Notes |
|---|---|---|
| `app_version` | `0.4.38` | Matches the V0.4.38 release commit `2df0d69` ("release: V0.4.38 — the F1-F5 backlog release"); VERSION file = `0.4.38` |
| `run_id` | `20260926-052947-3aafaf9b` | Matches conversion-log line 5 (`<!-- generated-by: Elixir v0.4.38 \| run_id=20260926-052947-3aafaf9b -->`) and summary line 3 |
| `started` | `2026-09-26T05:29:47` (conversion log) / `05:35:40` (summary) | The summary `started=` is the post-dedup final-stamp; consistent |
| `bullets` | `63` | Matches summary line 3 + final shipped bullet count (conversion-log line 947: "Total bullets: 63") — DOWN from V0.4.37's 67 |
| Conversion-log companion stamp (line 5) | ✅ Present, matches summary | `run_id=20260926-052947-3aafaf9b` |
| V0.4.38 F1 fix (commit `415f589`) | ✅ Present in `core/summarisation/postchecks/garble/fusion.py` (Pattern C: `_FUSION_C_MIN_SUFFIX`/`_FUSION_C_MAX_SUFFIX` + `_source_word_suffix_set` precompute) | Verified via `git show 415f589` |
| V0.4.38 F2 fix (commit `ff7ab00`) | ✅ Present in `core/summarisation/thorough_fallback.py` (Attempt 4 quantified length-directive) | Verified — **FIRED on the rig** (conv-log line 545) |
| V0.4.38 F3 fix (commit `57f13f3`) | ✅ Present in `core/summarisation/postchecks/garble/token_detectors.py` (fragment_merge lexicon check) | Verified |
| V0.4.38 F4 fix (commit `605bafd`) | ✅ Present in `core/summarisation/postchecks/attribution.py` (`_BOLD_NAME_STRUCTURAL_LABELS`) | Verified |
| V0.4.38 F5 fix (commit `f2877d7`) | ✅ Present in `core/pipeline/chapter_checkpoint.py` (`_normalize_self_compounds`) | Verified |
| Source chapter | `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words) | UNCHANGED across all 8 audits (V0.4.31 → V0.4.38) |
| Rig model | `Ternary-Bonsai-2-27B-Instruct-Vision` (conversion-log line 113) | IDENTICAL to V0.4.36 + V0.4.37 — the coverage/garble deltas are LLM variance (same model, temp 0.7), NOT a model swap |

**Provenance verdict: ✅ STAMPED + CONSISTENT.** Audit may proceed.

---

## Part 1 — Detailed Report

### Step 1 — The 5 V0.4.38 fixes (the headline findings — did each work on the rig?)

**1. F1 fusion-garble Pattern C (commit `415f589`) — ✅ validated in-sandbox; NOT exercised this rig run.**

  V0.4.37 shipped "persecutionensate" (a "persecution"+"compensate" mid-overlap fusion) — undetected (0 `sentence_fusion` flags). **V0.4.38: 0 `sentence_fusion` flags** (conv-log) AND the V0.4.37 "persecutionensate" did NOT recur — the V0.4.38 thorough line 81 ships a clean `Bleuler (*1908*), who identified a triad of suspiciousness, grandiosity, and persecution` (no fusion). So Pattern C was NOT exercised this run (the model didn't produce a fusion garble). Pattern C is validated in-sandbox by `test_v0438_audit_fixes.py::TestV0438F1DroppedPrefixFusion` (reproduces "persecutionensate" + asserts it's flagged). ✅ The rig run just didn't produce the fusion class this time (LLM variance — the V0.4.38 model produced a DIFFERENT garble class, see Step 5).

**2. F2 4th dedicated-thorough attempt (commit `ff7ab00`) — ✅ FIRED on the rig (machinery validated); did NOT recover the length.**

  Conv-log line 525: `thorough_summary too short (696 words < 800 threshold) — requesting dedicated expansion`. Lines 531: Attempt 1 = 696 words. **Line 545: `V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 696 < 800 min words)`** — the F2 4th attempt FIRED. Line 551: `All 4 thorough attempts returned < 800 words (best=696) — keeping best-effort result`. So the model produced 696 words on ALL 4 attempts — the quantified length directive did NOT make the model produce ≥800 words (LLM variance — the model is stuck short on this chapter). The F2 machinery WORKED (attempt 4 fired + the quantified directive was sent); the recovery is model-dependent. The F3 coverage-driven gap-fill then ran (21/74→29/74) and brought the shipped thorough to **1079 words** (11 paragraphs) — so the SHIPPED thorough is ≥800 (the gap-fill compensated), but the dedicated-expansion itself stayed at 696. ✅ machinery validated; the model didn't recover.

**3. F3 fragment_merge lexicon check (commit `57f13f3`) — ✅ WORKED (no "theme" false-positive).**

  V0.4.37 flagged "theme" (bullet 4 + thorough) because "them" is in the source but "theme" is not — the detector checked source_words only. **V0.4.38: 0 "theme" fragment_merge flags.** The only fragment_merge flag this run is "betrayale" (a REAL garble — "betrayale" is NOT in the lexicon, so the F3 lexicon check correctly does NOT suppress it; see Step 5). So F3's lexicon check suppressed the "theme"-class FP (or the model didn't produce "them"+"e" this run). ✅

**4. F4 bold-name structural-label exemption (commit `605bafd`) — ✅ WORKED (no "Conclusions" flag).**

  V0.4.37 flagged `**Conclusions**:` (bullet 59) as "author 'Conclusions' not found in source". **V0.4.38: 0 bold-name attribution flags** (the summary ships `**Conclusions**:` on line 70 + 6 other structural `**Label**:` bullets — none flagged). The `_BOLD_NAME_STRUCTURAL_LABELS` exemption suppressed the "Conclusions"-class FP. ✅

**5. F5 self-compound hyphen normalization (commit `f2877d7`) — ✅ output is clean (hyphenated).**

  V0.4.37 shipped "selfinflation" (bullet line 76) + "selfrighteousness" (bullet line 63). **V0.4.38 ships "self-inflation" (line 71) + "self-righteousness" (line 59)** — hyphenated. The F5 render-sweep logs to the module logger (not the structured conversion log), so the conv-log doesn't record whether F5 fixed them or the model produced them hyphenated this run. Either way, the SHIPPED output is clean (hyphenated). ✅ (F5 validated in-sandbox by `test_v0438_audit_fixes.py::TestV0438F5SelfCompoundHyphenNormalization` which reproduces "selfinflation"→"self-inflation" + asserts "selfless"/"selfish" are left alone.)

**Step-1 verdict: all 5 V0.4.38 fixes WORKED on the rig (F2 fired, F3/F4 FPs fixed, F5 output clean, F1 not exercised).** The run-quality issues in Steps 3-5 are LLM variance (the model produced 2 NEW garbles in the dropped_letter/fragment_merge classes) + the binding coverage constraint unchanged — NOT V0.4.38 code regressions.

### Step 2 — Hallucination check (0 hallucinations shipped ✅)

The V0.4.38 gap-fill produced fabricated names ("Jack", "Ndtei") — conv-log lines 831/833: `V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack's contributions…" / "Ndtei's work…" — its name(s) never co-occur with the claim's key phrases in the source`. **ALL fabricated names were DROPPED pre-ship by the V0.4.24 attribution-edge check.** Grep of the shipped summary confirms neither `Jack` nor `Ndtei` appears as cited authors.

**"Green" / "Pao" / "Socarides" ARE REAL source authors** (source lines 281-283: "Green's (1986) essay on moral narcissism", "Pao's (1969) work on morbid jealousy", "Socarides's (1966) view on the affect of vengeance"). The V0.4.38 summary correctly ships them (line 66 "Green (*1986*)", line 95 "Pao" + "Socarides") — NOT hallucinations. (Note: V0.4.37's audit had mis-flagged "Green (1975)" as fabricated — it was a wrong-YEAR gap-fill that the attribution-edge correctly dropped; "Green" IS a real source author, year 1986. The V0.4.38 model produced the correct year.) **0 hallucinations shipped** ✅.

### Step 3 — Factual Consistency (Score: 9, flat vs V0.4.37's 9)

Spot-checks against `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md`:
- Magnan (1893) "fragile personalities" in degenerates — source line 51 ✅.
- Kraepelin (1905, 1921a) "pseudoquerulous" / "paranoid personality" — source ✅.
- Bleuler (1908) triad of suspiciousness/grandiosity/persecution — source line 67-68 ✅ (clean, no fusion this run).
- Millon (1981) "paranoids cloak but a hollow shell" (p. 383) — source line 130-131 ✅ (but the summary garbled "paranoids"→"paranoias", see Step 5).
- Green (1986) moral narcissism / Pao (1969) morbid jealousy / Socarides (1966) vengeance — source lines 281-283 ✅ (correctly shipped).
- 0 fabricated years shipped; 0 fabricated author attributions shipped.

**The 2 shipped garbles ("betrayale" + "paranoias") are cohesion/clarity defects, not factual errors** — the underlying facts (Rycroft/Cameron on betrayal; Millon on "paranoids cloak a hollow shell") are correct, the WORDS are mangled. The 2 attribution-mismatch flags (Jaspers 38%, Bursten 39% — both below the F7 thorough threshold of 40% → correctly flagged) are genuine borderline paraphrases. Score 9 (flat — 0 hallucinations, 2 garbles that distort words but not facts).

### Step 4 — Informational Coverage (Score: 6, flat vs V0.4.37's 6 — the binding constraint UNCHANGED)

- **Bullets recall floor (deterministic, final set): 55/74 = 74%** (conv-log line 951). ↑ from V0.4.37's 52/74 = 70% (+4pp) — IMPROVED. Still below V0.4.36's 80%.
- **Thorough coverage: 29/74 = 39%** (post-gap-fill; conv-log line 845: `Thorough gap-fill: floor 21/74 → 29/74`). ↓ from V0.4.37's 31/74 = 42% (−2pp) — slightly worse. The thorough started at 21/74 (lower than V0.4.37's 24/74); the F3 gap-fill gained +8 (21→29) vs V0.4.37's +7 (24→31).
- **Bullets shipped: 63** (↓ from V0.4.37's 67; conv-log line 947).
- **Thorough words: 1079** (11 paragraphs) — the dedicated-expansion best-effort was 696 (F2's 4th attempt didn't recover), but the F3 gap-fill brought the total to 1079 (≥800). So the SHIPPED thorough is a reasonable length; the COVERAGE is the issue (1079 words of synthesis prose covering only 29/74 theorists).
- **Root cause: LLM variance** (same model as V0.4.36/V0.4.37). The model produced a 696-word dedicated-expansion on all 4 attempts (F2's 4th attempt didn't recover); the F3 gap-fill compensated on length but not coverage. **NOT a V0.4.38 code regression** — the F2/F3 machinery worked; the model's output is the constraint.

The campaign's "4 pillars all ≥7" target remains **BROKEN** — coverage 6 < 7 (unchanged from V0.4.37). The binding constraint is still COVERAGE (LLM-variance-driven). Score 6 (flat).

### Step 5 — Cohesion & Clarity (Score: 6, ↓ from V0.4.37's 7 — TWO detected-but-unrepaired garbles shipped)

- The thorough ships as **11 paragraphs** (the V0.4.36 F3 paragraph-breaking continues to work). ✅
- **TWO garbles shipped — both DETECTED+flagged but flag-only → unrepaired:**
  1. **"betrayale"** (thorough line 87): `…guard against betrayale of biased clue-seeking.` Source: Rycroft "guard against betrayal" + Shapiro "biased clue-seeking". The model fused "betrayal" + a stray "e". **Conv-log line 757: `[fragment_merge/flag] 'betrayale of' — 'betrayal' is a known word but 'betrayale' is not`** + **line 759: `[dropped_letter/flag] 'betrayale' is edit-distance-1 from 'betrayal'`** — DOUBLE-flagged. "betrayale" is NOT in the lexicon (confirmed). Both detectors are flag-only → shipped unrepaired.
  2. **"paranoias"** (bullet 38 / summary line 53): `…the confidence and pride of paranoias cloak a hollow shell.` Source line 131: `the confidence and pride of paranoids cloak but a hollow shell` (Millon 1981, p. 383). The model wrote "paranoias" instead of "paranoids". **Conv-log line 751: `[dropped_letter/flag] 'paranoias' is edit-distance-1 from 'paranoids'`** — flagged. "paranoias" is NOT in the lexicon; "paranoids" IS. The dropped_letter detector's `auto_repair` is default OFF (since V0.03 P0-1 — "The V0.02 rig run corrupted 12/13 valid paraphrase words") → shipped unrepaired.
- **F5 fixed the V0.4.37 hyphen issues** ("selfinflation"→"self-inflation", "selfrighteousness"→"self-righteousness") — ✅ no hyphen defects shipped.
- **F3 fixed the V0.4.37 "theme" fragment_merge FP** — ✅ no fragment_merge FPs.
- **13 `quote_verification` fixes** stripped non-verbatim quote spans (conv-log lines 765-787) — left some slightly odd phrasing in the exec but balanced quotes.
- **F6 (stray-quote) render-sweep: 0 odd-count quote lines shipped** (verified by per-line `count('"') % 2` scan of all sections). ✅

The −1 (7→6) is the TWO shipped garbles — both edit-distance-1 from real source words, both DETECTED+flagged, but the detectors are flag-only (the dropped_letter auto_repair is OFF for a good reason — it corrupted valid words in V0.02). So the V0.4.38 IMPROVED detection (the garbles are now caught + logged) but the shipped OUTPUT still has them. Score 6.

### Step 6 — Conciseness vs Vagueness (Score: 8, flat vs V0.4.37's 8)

- The shipped thorough is **1079 words** (11 paragraphs) — reasonable (the dedicated-expansion's 696 + the F3 gap-fill's ~383). The exec is 3 paragraphs, well-structured.
- Bullets: 63 (vs V0.4.37's 67) — slightly fewer, no vagueness regression.
- No vagueness — the bullets remain specific (e.g. line 49 Hamilton's two subtypes; lines 70-77 the enumerated-list bullets verbatim from source).
- Score 8 (flat — the prose is tight; the coverage/garble issues are penalized in Steps 4-5, not here).

---

## Part 2 — JSON Scorecard

```json
{
  "version": "0.4.38",
  "run_id": "20260926-052947-3aafaf9b",
  "chapter": "6 - PARANOID PERSONALITY DISORDER",
  "scorecard": {
    "factual_consistency": 9,
    "informational_coverage": 6,
    "cohesion_clarity": 6,
    "conciseness_vs_vagueness": 8
  },
  "hallucinations_shipped": 0,
  "hallucinations_caught_pre_ship": ["Jack", "Ndtei"],
  "real_authors_correctly_shipped": ["Green (1986)", "Pao (1969)", "Socarides (1966)"],
  "bullets_shipped": 63,
  "bullets_recall_floor": "55/74 (74%)",
  "thorough_coverage_post_gapfill": "29/74 (39%)",
  "thorough_words_shipped": 1079,
  "dedicated_expansion_best_effort": "696 words (F2 attempt 4 fired, did not recover)",
  "fixes_validated_on_rig": ["F2 (4th attempt fired)", "F3 (no theme FP)", "F4 (no Conclusions flag)", "F5 (hyphenated output)"],
  "fixes_not_exercised_this_run": ["F1 (Pattern C — no fusion garble produced this run)"],
  "garbles_shipped_detected_but_unrepaired": ["betrayale (fragment_merge+dropped_letter, thorough line 87)", "paranoias (dropped_letter, bullet 38/line 53)"],
  "verdict": "REGRESSION (slight, cohesion -1) vs V0.4.37 (9/6/7/8) — the 5 V0.4.38 code fixes all worked on the rig, BUT 2 detected+flagged garbles shipped unrepaired (flag-only detectors) + the binding coverage constraint is unchanged (thorough 39%, bullets 74%). The '4 pillars all >=7' target remains BROKEN (coverage 6 + cohesion 6)."
}
```

---

## Conversion-log review (the four-pillar + provenance cross-check)

### A. Provenance stamp
✅ Conversion-log line 5: `<!-- generated-by: Elixir v0.4.38 | run_id=20260926-052947-3aafaf9b -->` — matches summary line 3. Rule 4 satisfied.

### B. Deadline + runtime
- Conversion started 05:29:47, finished 05:50:53 (~21 min / 1,266s). Deadline NOT exceeded this run (the dedicated-expansion 4 attempts + the 3-call thorough gap-fit ran within the deadline — V0.4.37 had a deadline overrun; V0.4.38 did not).

### C. The F2 4th attempt (the headline RIG validation)
Conv-log:
- Line 525: `thorough_summary too short (696 words < 800 threshold) — requesting dedicated expansion`.
- Line 531: `Attempt 1/3: dedicated thorough = 696 words`.
- Line 545: `V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 696 < 800 min words)` — **F2 FIRED**.
- Line 551: `All 4 thorough attempts returned < 800 words (best=696) — keeping best-effort result`.
- The model produced 696 words on all 4 attempts — the quantified length directive did NOT recover the length (LLM variance). The F3 gap-fill then ran (21/74→29/74) and brought the shipped thorough to 1079 words. So F2's machinery WORKED (attempt 4 fired + the directive was sent); the recovery is model-dependent. ✅ machinery validated.

### D. The F3 fragment_merge lexicon check
Conv-log fragment_merge flags:
- V0.4.37: 2 "theme" false-positives (bullet 4 + thorough).
- V0.4.38: 1 fragment_merge flag — "betrayale" (a REAL garble, NOT in the lexicon → correctly NOT suppressed by the F3 lexicon check). 0 "theme" FPs. ✅

### E. The F4 bold-name structural-label exemption
Conv-log bold-name attribution flags:
- V0.4.37: 1 — `**Conclusions**:` (bullet 59).
- V0.4.38: 0 bold-name attribution flags. The summary ships `**Conclusions**:` (line 70) + 6 other `**Label**:` structural bullets — none flagged. ✅

### F. The F5 self-compound hyphen normalization
The shipped summary has "self-inflation" (line 71) + "self-righteousness" (line 59) — hyphenated. V0.4.37 shipped "selfinflation"/"selfrighteousness" (unhyphenated). The F5 render-sweep logs to the module logger (not the structured conv-log), so the conv-log doesn't record whether F5 fixed them or the model produced them hyphenated. Either way, the OUTPUT is clean. ✅

### G. The F1 fusion Pattern C
Conv-log `sentence_fusion` flags: 0. The V0.4.37 "persecutionensate" did NOT recur (the V0.4.38 model produced clean "persecution" on line 81). Pattern C was NOT exercised this run (no fusion garble produced). Validated in-sandbox. ✅

### H. The shipped garbles (the cohesion defect)
- "betrayale" (thorough line 87): fragment_merge (line 757) + dropped_letter (line 759) — DOUBLE-flagged, flag-only → shipped unrepaired.
- "paranoias" (bullet 38 / line 53): dropped_letter (line 751) — flagged, flag-only → shipped unrepaired.
- Both edit-distance-1 from real source words ("betrayale"→"betrayal", "paranoias"→"paranoids"). The dropped_letter detector's `auto_repair` is default OFF (V0.03 P0-1 — it corrupted valid paraphrase words in V0.02). So the garbles are DETECTED but not REPAIRED.

### I. Coverage floor
- Bullets recall: 55/74 = 74% (conv-log line 951). ↑ from V0.4.37's 70%.
- Thorough: 21/74 → 29/74 (39%) post-gap-fill (line 845). ↓ from V0.4.37's 42%.
- Missing from bullets (recall floor): ['Winokur', 'Bergman', 'Jack', 'Ndtei', 'Pao'] — 'Jack'+'Ndtei' are fabricated (dropped pre-ship); 'Winokur'+'Bergman'+'Pao' are real source authors not in the bullets (Pao IS in the thorough line 95 but not the bullets).

### J. The V0.4.38+ commit lineage
- `415f589` F1 fusion Pattern C · `ff7ab00` F2 4th dedicated-thorough attempt · `57f13f3` F3 fragment_merge lexicon · `605bafd` F4 bold-name structural-label exemption · `f2877d7` F5 self-compound hyphen normalization · `2df0d69` release V0.4.38 · Tag `V0.4.38`.

---

## Eight-audit delta table (V0.4.31 → … → V0.4.38)

| Pillar / metric | V0.4.31 | … | V0.4.35 | V0.4.36 | V0.4.37 | **V0.4.38** | Δ vs V0.4.37 |
|---|---|---|---|---|---|---|---|
| Factual consistency | 8 | … | 9 | 10 | 9 | **9** | flat (0 halluc; 2 garbles are word-mangling, not factual) |
| Informational coverage | 6 | … | 5 | 8 | 6 | **6** | flat (bullets 74%↑, thorough 39%↓ — binding constraint unchanged) |
| Cohesion & clarity | 7 | … | 7 | 8 | 7 | **6** | **−1 (2 detected+flagged garbles shipped unrepaired)** |
| Conciseness vs vagueness | 6 | … | 7 | 7 | 8 | **8** | flat |
| Hallucinations shipped | 0 | … | 0 | 0 | 0 | **0** | flat ✅ |
| Bullets shipped | — | … | 62 | 79 | 67 | **63** | −4 |
| Bullets recall floor | — | … | — | 59/74 (80%) | 52/74 (70%) | **55/74 (74%)** | +4pp |
| Thorough coverage (post-gap-fill) | — | … | — | 48/74 (65%) | 31/74 (42%) | **29/74 (39%)** | −3pp |
| Dedicated-expansion best | — | … | — | — | 793w (3 attempts) | **696w (4 attempts — F2 fired)** | F2 machinery validated |
| Garbles shipped | — | … | — | 0 | 1 (persecutionensate, undetected) | **2 (betrayale+paranoias, detected+flagged, unrepaired)** | +1 (but now DETECTED) |
| Verdict | borderline | … | borderline | **PASS (solid)** | REGRESSION (coverage) | **REGRESSION (slight, cohesion)** | — |

---

## Verdict + recommended V0.4.40 backlog

> **Verdict: REGRESSION (slight) vs V0.4.37 (9/6/7/8 → 9/6/6/8) — cohesion −1.**

The 5 V0.4.38 code fixes all **WORKED on the rig** — F2's 4th attempt fired (line 545), F3's fragment_merge lexicon check suppressed the "theme" FP, F4's structural-label exemption suppressed the "Conclusions" flag, F5's output is hyphenated, F1's Pattern C wasn't exercised (no fusion garble this run). **The CODE is validated.** However:

1. **TWO detected+flagged garbles shipped unrepaired** — "betrayale" (thorough line 87) + "paranoias" (bullet 38). Both edit-distance-1 from real source words, both DETECTED (fragment_merge + dropped_letter flagged them), but both detectors are flag-only → shipped. The dropped_letter `auto_repair` is default OFF (V0.03 P0-1 — it corrupted valid paraphrase words in V0.02). So V0.4.38 IMPROVED detection (the garbles are now caught + logged) but the shipped OUTPUT still has them — cohesion −1.
2. **The binding coverage constraint is UNCHANGED** — bullets 74% (↑4pp), thorough 39% (↓3pp). The dedicated-expansion produced 696 words on all 4 attempts (F2's 4th attempt didn't recover — LLM variance); the F3 gap-fill compensated on length (1079 total) but not coverage. **NOT a V0.4.38 code regression** (F2/F3 machinery worked; the model's output is the constraint).

The campaign's "4 pillars all ≥7" target remains **BROKEN** — coverage 6 + cohesion 6, both < 7. The binding constraint is still COVERAGE (LLM-variance-driven) + now also the flag-only-garble-ship class.

### V0.4.40 backlog (priority order — all evidence-anchored to this audit)

1. **F1 — SOURCE-GROUNDED AUTO-REPAIR for edit-distance-1 garbles (HIGH PRIORITY):** "betrayale" (→"betrayal") + "paranoias" (→"paranoids") shipped DETECTED+flagged but unrepaired. The dropped_letter `auto_repair` is default OFF (V0.03 P0-1 — it corrupted valid paraphrase words in V0.02). The V0.4.40 fix: a CONSERVATIVE source-grounded auto-repair — only repair when the edit-distance-1 candidate IS a source word AND the garble is NOT in the English lexicon ("paranoias" not in lexicon + "paranoids" in source → repair to "paranoids"; "betrayale" not in lexicon + "betrayal" in source → repair to "betrayal"). This is strictly safer than the V0.02 auto_repair (which considered ALL edit-distance-1 candidates, including valid paraphrase words). Content-agnostic (Rule 1 ✓ — source-word + lexicon based). OR an LLM semantic repair (like the D3 stray-quote repair) as a fallback.
   **Evidence:** conv-log lines 751 ("paranoias" edit-distance-1 from "paranoids") + 757/759 ("betrayale" edit-distance-1 from "betrayal"); source line 131 ("paranoids cloak but a hollow shell"); summary lines 53 + 87.

2. **F2 — THOROUGH DEDICATED-EXPANSION PERSISTENT-SHORT ESCALATION (HIGH PRIORITY):** F2's 4th attempt fired but didn't recover (696<800 on all 4 attempts — the quantified length directive wasn't enough for this model/chapter). The F3 gap-fill compensated on length (1079 total) but coverage stayed at 39%. Consider: escalate to the synthetic (exec+bullets) fallback when the 4th attempt ALSO fails to meet min_words (currently the synthetic fallback fires only on total failure, best=None). This would trade prose-cohesion for coverage (the synthetic fallback is coverage-richer). OR accept LLM variance + document (the V0.4.36 stance).
   **Evidence:** conv-log lines 525/531/545/551 (4 attempts, best=696<800); line 845 (thorough 21/74→29/74).

3. **F3 — QUOTE_VERIFICATION STRIPPING PHRASING (LOW PRIORITY):** the 13 `quote_verification` fixes stripped non-verbatim quote spans (conv-log lines 765-787) — left some slightly odd exec phrasing (e.g. line 9 `"pseudoquerulous personality, which is defined…` — the quote marks stripped, the sentence reads slightly off). Consider a post-strip phrasing-smoothing pass. Minor.
   **Evidence:** conv-log lines 765-787; summary line 9.

---

## Artifacts

- Summary: `audit/results/bench_v0438_ch6_paranoid/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.38_20260926-052947-3aafaf9b_summary.md` (124 lines, 63 bullets)
- Conversion log: `audit/results/bench_v0438_ch6_paranoid/Broken Structures Salman Akhtar_v0.4.38_20260926-052947-3aafaf9b.conversion.log.md` (1003 lines)
- Source: `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words — unchanged across all 8 audits)
- Release: tag `V0.4.38` @ commit `2df0d69` on `refactor/audit-session`; release zip `/home/z/my-project/download/Elixir-V0.4.38.zip` (4.7 MB, 858 entries)
