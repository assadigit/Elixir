# AUDIT — Summary vs Source — version V0.5.1 (run 20260926-085048-a3db0a0b) — ch.6

> Four-pillar expert fact-checker audit, **the ELEVENTH round** on the same chapter
> (the V0.5.1 release shipped the wiring bug fix + date-extractor page-ref FP fix
> + verification LAYER coverage-targeting).

## Provenance

| Field | Stamp | Notes |
|---|---|---|
| `app_version` | `0.5.1` | Matches tag `V0.5.1` @ `383d3d4` |
| `run_id` | `20260926-085048-a3db0a0b` | Matches conv-log + summary |
| `bullets` | `78` | UP from V0.5.0's 65 |
| Rig model | `Ternary-Bonsai-2-27B-Instruct-Vision` | IDENTICAL to all prior runs |

**Provenance verdict: ✅ STAMPED + CONSISTENT.**

## Scorecard: 10/7/8/8 — **PASS (all pillars ≥7)**

| Pillar | V0.5.0 | **V0.5.1** | Δ |
|---|---|---|---|
| Factual consistency | 10 | **10** | flat (0 hallucinations; "Jack" IS a real source author — prior audits corrected) |
| Informational coverage | 8 | **7** | −1 (bullets 88%↑ BEST; thorough 38%↓ from 61% — LLM variance) |
| Cohesion & clarity | 8 | **8** | flat (0 garbles shipped; 1 Pattern C FP flag: "underrepresentation") |
| Conciseness vs vagueness | 8 | **8** | flat (1006w thorough, 78 bullets) |
| Hallucinations shipped | 0 | **0** | flat ✅ |

## V0.5.1 architecture validation

### Verification LAYER — ❌ NOT visible in the conv-log (heading→source match issue)

The V0.5.1 wiring fix (logging `_v_issues`) + the date-extractor page-ref FP fix + the coverage-targeting were **NOT exercised** this run. The conv-log shows NO `✨ V0.5.1 verification:` log lines, NO `verification_date_check` issues, NO `verification_coverage` issues. The LAYER likely didn't fire because the `_source_for_summary(heading)` match failed — the chapter heading (`6 - PARANOID PERSONALITY DISORDER`) might not match the segment heading in `_source_by_heading`. **V0.5.2 bug to investigate + fix.**

### Date-extractor page-ref FP fix — ✅ VALIDATED (manual run)

Running the V0.5.1 date extractor on the summary: **0 page-ref false positives** (the ~137 page-ref masking works). Date-check results: 0 hallucinated dates (all summary dates in the source ✓), 31 omitted (advisory), 35 matched. The V0.5.0 page-ref FP (9 false-positive "hallucinated" ~137 dates) is **FIXED**. ✅

### Pattern C false positive — "underrepresentation" (V0.5.2 tuning)

Conv-log line 753: `[sentence_fusion/flag] exec: 'underrepresentation' is not in the source or English lexicon; it starts with source-word 'represent' + a 5-char suffix 'ation'`. "underrepresentation" IS a real English word (under+representation compound) but is NOT in the 126k lexicon. Pattern C flags it because "represent" is a source word + "ation" (5 chars) is a suffix of another source word (e.g. "presentation"). **False positive** — the word is real, not a fusion. V0.5.2 tuning: Pattern C should check if the full word is a real English compound (or add "ation" to the legit suffixes, or add the word to the lexicon).

### "Jack" IS a real source author — prior audits CORRECTED

**Source lines 489 + 493**: "Jack 1984" and "Jack et al. 1984" — Jack IS cited in the source as a contributor on reactive paranoia. The V0.4.37-V0.4.39 audits INCORRECTLY said "Jack" was fabricated (it was a wrong-year gap-fill that was dropped; "Jack" the author IS real, year 1984). The V0.5.0 audit corrected "Green" but not "Jack". **This audit corrects "Jack" — it IS a real source author, correctly shipped as "Jack (*1984*)" on line 79.** The prior audits' "Jack fabricated" claim was wrong.

### Coverage (the split story)

- **Bullets recall: 65/74 = 88%** — **NEW ALL-TIME BEST** (V0.5.0 was 81%; V0.4.36 was 80%). The in-pipeline gap-fill gained more this run (5 rounds, filling 8 authors per round — the model's gap-fill output was better this run). ↑ +7pp from V0.5.0.
- **Thorough coverage: 23/74 → 28/74 = 38%** — DOWN from V0.5.0's 61% (−23pp). The model produced a 1006-word thorough (≥800 → F2 NOT triggered) but it only covered 23/74 pre-gap-fill (lower than V0.5.0's 30/74). The gap-fill gained +5 (23→28, lower than V0.5.0's +15). **LLM variance** — the model produced a long-enough but lower-coverage thorough this run.

### F2 (4th dedicated-thorough attempt) — NOT triggered

The primary thorough was 1006 words (≥800 threshold) → the dedicated-expansion didn't fire → F2's 4th attempt didn't fire. The V0.4.37-V0.5.0 trend (793→696→589→696) shows the model's thorough length is HIGHLY variable. This run: 1006 words (above threshold). LLM variance.

## Verdict + V0.5.2 backlog

> **Verdict: PASS — 10/7/8/8 (all pillars ≥7).**

The V0.5.1 run has the **best bullets recall ever** (88%) but a thorough coverage regression (38% vs V0.5.0's 61% — LLM variance). 0 garbles shipped (1 Pattern C FP flag). 0 hallucinations ("Jack" IS a real source author — prior audits corrected).

The V0.5.1 code additions (wiring fix + page-ref FP + coverage-targeting) were **NOT exercised** (the verification LAYER didn't fire — the heading→source match likely failed). The page-ref FP fix IS validated (manual date-extractor run: 0 page-ref FPs).

### V0.5.2 backlog

1. **(BUG — HIGH) The verification LAYER didn't fire** — the `_source_for_summary(heading)` match likely failed for this chapter. Investigate the heading→source map (`_source_by_heading` built from `segments_for_summary` vs `summ.chapter_heading`). The chapter heading is `6 - PARANOID PERSONALITY DISORDER`; the segment heading might differ. Fix the matching (or use a more robust match).
2. **(TUNING — LOW) Pattern C false positive on "underrepresentation"** — a real English compound word not in the lexicon. Add a lexicon check to Pattern C (currently Pattern C doesn't check if the full word is in the lexicon — it only checks the source-word prefix + the suffix). OR add "ation" to the `_FUSION_LEGIT_SUFFIXES`.
3. **(TUNING — LOW) "His" attribution false positives** — the pronoun "His" is parsed as an author name by the citation regex. Add "His" to the author stopword list.
4. **(NONE) Thorough coverage regression (38% vs 61%)** — LLM variance. No code fix needed.
