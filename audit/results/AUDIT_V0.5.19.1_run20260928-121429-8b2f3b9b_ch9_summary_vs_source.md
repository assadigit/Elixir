# AUDIT V0.5.19.1 — ch.9 same-chapter re-benchmark (the V0.5.19 backlog fixes vs the V0.5.18 baseline)

**Run:** `20260928-121429-8b2f3b9b` (V0.5.19.1, **sandbox shim** — glm-4-plus @ t=0.70 via the zai-llamacpp-shim llama.cpp emulator, port 3031; embedder-less sandbox; 254.2s chapter, 116 bullets; run via the bench-spawner mini-service)
**Source:** `001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md` (7,089 words, 564 lines — the same chapter as the operator's V0.5.17 rig run and the V0.5.18 sandbox re-run)
**Candidate:** `001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.19.1_20260928-121429-8b2f3b9b_summary.md` (116 bullets, exec 1,395 chars, thorough 11,297 chars; provenance stamp v0.5.19.1 ✓ + COMPLETE sentinel ✓)
**Method:** the standing four-pillar framework (EVALUATION_FRAMEWORK.md) + the deterministic author-roster cross-reference (the V0.5.18 anchor rule + the V0.5.19 structural-name filter) + conversion-log cross-check (stage-fire evidence incl. the new append-mode + thin-bullet detectors).
**Benchmark:** the V0.5.18 sandbox re-run on this exact chapter (73/73 = 100%, flag 3/0, 107 bullets) — the V0.5.19/.1 run answers: what do the six backlog fixes change on the same input?

## Headline: 100% coverage holds, and every V0.5.19 fix has live evidence on this run

| Metric | ch.9 SANDBOX V0.5.18 | **ch.9 SANDBOX V0.5.19.1** | Δ |
|---|---|---|---|
| Deterministic roster / covered | 73/73 = 100% | **73/73 = 100%** | holds |
| Verification-LAYER missing-author flag | 3 flagged / 0 false (DSM-II†, Kohut and Wolf, Simic) | **2 flagged / 0 false** (Siever and Gunderson‡, Simic — both genuinely absent pre-correction) | DSM-II gone (the structural filter), Kohut and Wolf covered this run |
| **Append-mode corrections (V0.5.19 flagship)** | — (didn't exist; anchor-insert corrections never landed) | **FIRED LIVE**: the Simic append landed as `verification_append/fix` — "Simic: Author of the poem 'The Roach,' which opens the chapter…" (verbatim-faithful vs source L40) | **the brittle-additions fix works end-to-end** |
| Kernberg's six-grounds list (the guarantee bullet) | **"5 items"** — item (5) truncated at the paragraph break, item (6) lost | **"6 items"** — item (5) completed ("…oedipal rivals, while infantile personalities show less chronic competitiveness…") + item (6) carried ("masochistic tendencies…") | **the V0.5.19.1 wrapped-continuation join works** |
| Reproduced Diagnostic Criteria section | garbled (discussion-prose glued into item b; sub-item (i) truncated; mid-line (ii) unrecognized; follow-on paragraph attached) | **CLEAN** — every sub-item completes; the mid-line (ii) split; the discussion paragraph closes the cluster (no glue) | **the V0.5.19 criteria continuation rules work** |
| Thin roster-gap-fill bullets | 2 shipped unflagged (Wolf's cross-wired cites, Widiger's prose-form "a work from 1980") | 4 shipped — **all 4 FLAGGED by the new thin-bullet detector** (Robins/Frances/Wolf/Chick one-liners); no year slip this run (the Widiger bullet cites no year) | the quality signal is now visible to the audit |
| Glossary structural-label noise | DSM-II/DSM-III/DSM-III-R listed as "names" (llm_only noise + a false coverage demand in V0.5.17) | **0 structural labels** — the xref llm_only bucket holds only real authors | **the structural-name filter works** |
| Fabricated names/claims | 0 | **0** | holds |
| Bullets | 107 | 116 | +9 (12 scholar gap-fill − dedup/merges) |

† the garbage-glossary family, filtered at ingestion in V0.5.19. ‡ the glossary's duplicate pair-form (both "Gunderson and Siever" and "Siever and Gunderson" listed); the individuals ARE covered (Siever appears 3×, Gunderson throughout) — a benign pair-form artifact of the LLM glossary ground truth, noted for the backlog (dedupe pair-forms at ingestion).

**The V0.5.19 system answer on the same chapter:** coverage stays at the 100% ceiling while every removal-layer and post-check defect the audits filed is either fixed with live evidence (the append-mode, the 6-grounds join, the criteria continuation, the structural filter, the thin-bullet signal) or armed and unit-pinned (the prose-form year check — no prose-year slip occurred this run; the loosened scholar quote-guard — the 12 gap-fill bullets all carried verbatim quotes, so the fallback path wasn't needed).

## Part 1: Detailed Report

### Fact-Check Log (verified claims vs. flagged errors — every named bullet checked against the source)

**Verified verbatim-faithful (sample of ~50 checked; the factual spine is sound):**

| # | Bullet claim (summary) | Source evidence | Verdict |
|---|---|---|---|
| 1 | **The appended Simic bullet** — "Simic: Author of the poem 'The Roach,' which opens the chapter and sets a thematic tone" | L40 — '"The Roach," Charles Simic I have chosen to discuss…' | **VERIFIED** (the append-mode's first live landing is grounded) |
| 2 | **The 6-grounds Kernberg bullet** — all six grounds carried verbatim, item (5) complete through "…differentiation in their behavior toward the two sexes", item (6) "masochistic tendencies are more restricted…" | L130-141 — the paragraph break inside item (5) no longer truncates the capture (the V0.5.19.1 join) | **VERIFIED** (was 5/6 in every prior run) |
| 3 | The reproduced criteria blocks (a/b + Roman sub-items, both criteria sets) | L199-219, L400-443 — every sub-item completes; the mid-line (ii) splits correctly; no discussion-prose glue | **VERIFIED** (the V0.5.19 continuation rules — both ch.9 criteria blocks render clean) |
| 4 | Zilboorg's eight criteria ("Basically, symptoms — 6 items…") + the "This consisted of" 5-item list + the "Indicated by at least three of" 5-item list | L363-365, L191, L201-207 — counts and items match | **VERIFIED** |
| 5 | Kety et al. (*1968*, *1975*) adoptive studies; Spitzer et al. (*1979*) survey; Gunderson and Siever (*1983*) + McGlashan (*1987*) discriminative findings | L356, L390-399, L430-436 | **VERIFIED** |
| 6 | Bleuler (*1908*, *1911*) observations; Zilboorg (*1941*) ambulatory schizophrenia; Hoch and Polatin (*1949*) pseudoneurotic schizophrenia; Rado (*1953*) / Meehl (*1962*) theoretical underpinnings | L344-372 | **VERIFIED** |
| 7 | Erikson (*1959*, Kernberg *1980*b) middle-age developmental tasks | L538 | **VERIFIED** (held from V0.5.18) |
| 8 | Abraham's (*1921*, *1924*a,b) early papers; Easser and Lesser (*1965*) true-hysteric vs hysteroid; Akhtar citation years (*1990*a, *1989*, *1988*, Thomson *1982*a) | L65-66, L108-121, L56, L525 — no year slips (the operator run's Akhtar 1984 slip family stays dead) | **VERIFIED** |
| 9 | The five extrinsic influences (mixed forms, social functioning, sex differences, lifespan, culture) + the affective-spectrum exclusion critique (Kraepelin *1921*b) | L495-557 | **VERIFIED** |

**Flagged errors (4 minor, all one family — thin roster-gap-fill one-liners, ALL caught by the new V0.5.19 thin-bullet detector):**

| # | Summary claim | Source | Verdict |
|---|---|---|---|
| E1 | "Wolf: Cited in studies examining the overlap of narcissistic and paranoid, … (Akhtar *1990*a, Bursten *1973*a, Bursten *1989*, Kernberg *1989*, Wolman *1987*, Reid *1981*, Akhtar *1987*, Kohut and Wolf *1978*)" | L503-505 — the overlap-literature cites are attached to the adjacent name again (Wolf's own co-cite is Kohut and Wolf 1978); the V0.5.18 E1 cross-wiring family, THIN-BULLET form | **CROSS-WIRED SUBJECT** — now FLAGGED live by the thin-bullet detector (bullet[95]) |
| E2 | "Chick: Cited in Wolff and Chick 1980 in relation to literature…" | L135 — the pair co-cite is correct but the bullet is citation-registry only | **THIN** — flagged (bullet[97]) |
| E3 | "Robins: Contributed to literature on early antisocial personality…" | L408-412 — true but contribution-free | **THIN** — flagged (bullet[79]) |
| E4 | "Frances: contributed to the controversy about whether the histrionic category should be broadened…" | L56-60 — true but thin | **THIN** — flagged (bullet[88]) |

**Hallucination verdict: 0 fabricated entities/claims.** The deterministic roster diff found 0 candidate names absent from the source (the appended Simic bullet included — Simic is glossary-rostered and verbatim-grounded).

### Missing Information (minor)

1. **The "third factor" borderline-concept narrative** (the late-1960s momentum — Kety vs Kernberg vs Gunderson and Singer) — still not carried (unchanged across all four runs; a model-choice, not a pipeline defect).
2. **The black/borderline subcultural finding** — still omitted (unchanged).

### Clarity / Conciseness

- The takeaways are grouped under the source's ALL-CAPS sections (the C1 structure); the 116-bullet density is +9 over V0.5.18 (the scholar-reflection gap-fill added 12, dedup/merges netted −3). The thin one-liners (E1-E4) slightly dilute the takeaways but are now AUDIT-VISIBLE.
- The reproduced-criteria section is CLEAN for the first time on this chapter — previously the worst-looking part of the output.

### Conversion-Log Cross-Check (stage-fire evidence)

- `verification_append/fix` — **the append-mode's first live landing** (Simic; the guards passed: roster-author, bullet-names-author, shape caps, clean).
- 4 × `attribution/flag` thin-bullet detections — the new quality signal, all true positives.
- The verification coverage flag: 2 missing pre-correction (Siever and Gunderson [the pair-form artifact], Simic) — 0 false; 1 of the 2 closed by the append; the pair-form noted for the backlog.
- 12 scholar-reflection gap-fill bullets added (all quote-grounded — the V0.5.19 loosened fallback wasn't needed this run; it stays unit-pinned).
- No near-dup veto fires (vetoed=0 all rounds — nothing roster-grounded was dedup-dropped this run; the V0.5.17/V0.5.18 vetoes stand guard).
- The V0.5.18 layers held: Pattern-6 roster (73), the anchor check (0 false flags), check 3 (no citation-shaped year slips).

## Part 2: Structured JSON Scorecard

```json
{
  "summary_id": "V0.5.19.1_run20260928-121429-8b2f3b9b_ch9",
  "overall_score": 8,
  "factual_consistency_score": 9,
  "coverage_score": 9,
  "clarity_score": 7,
  "conciseness_score": 7,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 0,
  "verdict": "PASS",
  "justification": "Same-chapter re-benchmark after V0.5.19/.1: 73/73 = 100% deterministic coverage holds with 0 fabricated claims; every backlog fix has live evidence — the append-mode landed the flagged-missing Simic bullet (verbatim-grounded), the Kernberg six-grounds list ships 6/6 complete (was 5/6 in every prior run), the reproduced-criteria section is clean (was garbled), the glossary carries 0 structural labels, and the 4 thin one-liners are all caught by the new quality flag. Remaining: the thin-bullet cross-wiring family (model variance, now audit-visible) + the glossary pair-form dedup (backlog)."
}
```
