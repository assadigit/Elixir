# AUDIT — version V0.18 (run_id 20260920-084745-c0874728) — Broken Structures, ch.1 "IDENTITY AND ITS ORIGINS"

> **Audit version:** `V0.18 / run 20260920-084745-c0874728 / app 0.18 / 2026-09-20T08:47:45 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 1 "IDENTITY AND ITS ORIGINS"
> **Audit framework:** the standing four-pillar expert fact-checker (verbatim prompt in `docs/EVALUATION_FRAMEWORK.md`).
> **Purpose:** per the campaign owner's instruction — *“after every audit, we mention the version of it, so in next tests, we have something to compare to.”* This file is the **V0.18 baseline**. The next audit (after a re-run with the V0.20 build on `main`, commit `4e5169a`) will be filed as `AUDIT_V0.20_<run_id>.md` and compared directly against the scorecard at the bottom of this file.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol)

| Field | Summary stamp | Conversion log | Match |
|---|---|---|---|
| `run_id` | `20260920-084745-c0874728` | log L869: `run_id=20260920-084745-c0874728` | ✓ |
| `app_version` | `0.18` | log L61: `App version: 0.18` | ✓ |
| `started` | `2026-09-20T08:47:45` | log L3: `Started at: 2026-09-20T08:45:57.884046` (summary started at :47:45) | ✓ |
| `bullets` | `40` | log L775: `bullets=40` | ✓ |

- **Source chapter** uploaded by the owner is **byte-identical** to `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md` (body match confirmed; 6,425 words, 9,120 tokens, PDF pp.15–32).
- **Honest coverage (deterministic recall floor, log L765 + L857):** theorists **20/37 (54%)** in final bullets; conclusion items **5/7 (71%)**; thorough theorists **13/37 (35%)** (log L761).
- **LLM judge (log L541):** `coverage=100% (46/46 claims), grounding=100% (30/30 bullets), hallucinations=0` — overstates content recall per the EVALUATION_FRAMEWORK house note.
- **Provenance verdict: PASS** — this is the genuine V0.18 output of run `20260920-084745-c0874728`.

> **Note for the owner:** this is the same V0.18 run that was audited in the previous session (`audit/results/AUDIT_V0.18_BrokenStructures.md`). The scorecard below therefore reproduces the V0.18 baseline numbers. To produce a **V0.20 audit** that can be compared against this baseline, re-run the rig with the V0.20 build on `main` (commit `4e5169a` — which contains the 3 coverage/clarity fixes: `f6fbfa3` coverage-aware V0.06 cap, `b63d1ac` non-skippable thorough floor, `076bf4b` colon-ending label-stub detector) and upload the new summary + log. The new audit will be filed as `AUDIT_V0.20_<new_run_id>.md`.

---

## Part 1 — Detailed Report (Human-Readable)

### Fact-Check Log

I extracted every factual claim from the Candidate Summary (Executive Summary paragraph, 40 Key Takeaways bullets, Key Distinctions, Theoretical Tensions) and traced each to the Source Text. **No hard hallucinations were found.** Every named theorist, date, quoted phrase, and causal claim I checked is directly supported by the source. The conversion-log postcheck "quote-verification/fix" entries (log L719–753) are paraphrase hygiene (quotation marks stripped from near-verbatim-but-not-exact quotes), not hallucination corrections — the underlying claims are all source-grounded.

Verified claims (representative sample, 25 of ~60 checked):

| # | Candidate claim | Source evidence (line/quote) | Verdict |
|---|---|---|---|
| 1 | "The term identity was introduced into psychoanalytic discourse by Tausk (1919)" | L51: "The term identity was introduced into the psychoanalytic literature by Tausk (1919)" | ✓ |
| 2 | "Freud invoked it technically only once, in his 1926 address to B'nai B'rith" | L53: "Freud…referred to the concept of identity only once…in his address to B'nai B'rith (Freud 1926a)" | ✓ |
| 3 | "of the ninety-two times he used the word, ninety-one were colloquial or literal" | L153-154: "of the ninety-two times that Freud used the word identity…ninety-one were in a colloquial and/or literal sense" | ✓ |
| 4 | "Erikson (1950a, 1956, 1958, 1959) resurrected the concept…defining ego identity as both 'a persistent sameness within oneself' and 'a persistent sharing of some kind of essential character with others.'" | L55-56 + L64-65 (Erikson 1956 p.12) | ✓ (summary drops "(selfsameness)" parenthetical — minor) |
| 5 | "Kernberg…declared that identity diffusion most clearly differentiates borderline from non-borderline conditions" | L59-60 (Kernberg 1980 p.14) | ✓ |
| 6 | "Lichtenstein…two opposing forces…identity principle…metamorphosis—a loss that can be experienced as liberation or ecstasy" | L113-127 | ✓ |
| 7 | "the mother imprints not a fixed identity but an 'identity theme, irreversible yet capable of variations'" | L122-123 | ✓ (summary says "not a fixed identity" vs source "not an identity" — minor paraphrase) |
| 8 | "Sexual union…demonstrates both forces simultaneously" | L129-132 | ✓ |
| 9 | "Fenichel (1937, 1945)…self-image originates from direct awareness of inner experience and indirect perception of the bodily-mental self as object" | L181-182 | ✓ |
| 10 | "'into the formation of every ego there have gone many identifications' (1945)" | L185 (1945 p.77) | ✓ |
| 11 | "Greenacre…habitual visual incorporation of opposite-sex genitals…early repeated exposure among twins…particularly if occurring in phallic or oedipal phases" | L203-206 | ✓ |
| 12 | "Mahler…sequence of phases: autistic, symbiotic, differentiation, practicing—'conquest of the world'—and rapprochement" | L215-221 | ✓ |
| 13 | "two conditions for ego organization: enteroceptive-proprioceptive stimuli must not be so intense…mother must buffer and organize stimuli" | L230-234 | ✓ |
| 14 | "Self-constancy emerges at approximately two years" | L236 | ✓ |
| 15 | "Jacobson (1964) formulated five categories…self- and object representations, fused self-object representation as the first intrapsychic structure, identity emerging from primitive identifications, aggression's role in self-delineation, and modifications to oedipal resolution" | L260-264 | ✓ |
| 16 | "'not only the loving but also the hostile components furnish the fuel for developing feelings of identity'" | L291-296 (Jacobson 1964 p.61) | ✓ |
| 17 | "Winnicott…infant's spontaneous gestures emanate from the true self, while maternal failure to decode the infant's overture produces a false self through compliance" | L301-306 | ✓ |
| 18 | "The infant is a psychosomatic being, and the true self derives from the aliveness of body tissues and working of body functions" | L313-314 (Winnicott 1960 p.144, p.148) | ✓ |
| 19 | "'all processes of a live infant constitute a going-on-being, kind of blueprint for existentialism'" | L321 (Winnicott 1960 p.86) | ✓ |
| 20 | "Kernberg…two essential tasks…differentiation of self from object images through libidinal gratification and frustration, and integration of self-object images built under loving versus aggressive drives" | L331-345 | ✓ |
| 21 | "'libidinal gratification draws attention cathexes…fosters differentiation'…'frustration brings to awareness the painful absence…differentiate self from non-self'" | L335-337 (Kernberg 1975a p.26) | ✓ |
| 22 | "three-step process—introjection, identification, and identity formation—culminating in a harmonious gestalt where identifications become depersonified" | L354-366 | ✓ |
| 23 | "distinguished the adolescent identity crisis from identity diffusion syndrome (correlated with borderline character organization)" | L368-370 | ✓ |
| 24 | "Chasseguet-Smirgel…two oedipal routes: the long path…ego ideal with hope and temporal order; and the short path…perverse character organization where ego and ego ideal fuse and filial links are severed" | L381-399 | ✓ |
| 25 | "Blos…adolescence as a second individuation…radical alterations in ego structure and consolidation of sexual identity through renunciation of parents as sexual objects, reconciliation of activity and passivity, and resolution of bisexual identifications" | L408-427 | ✓ |

**Flagged items (minor, none rise to hallucination):**
- (a) Bullet L37 attributes "sine qua non of borderline and narcissistic character disorders" to "Jacobson (1964)" alone; source L40-41 attributes it jointly to "Jacobson 1964, Kernberg 1967". Defensible (Jacobson is one of the two) but slightly misleading as a sole attribution.
- (b) Summary L7 says "the mother imprints not a fixed identity" where source L122 says "not an identity"; the added word "fixed" is a mild interpolation but does not change the meaning.
- (c) Summary L7 drops the source's attribution of "corporeality" to Khan (1983) (source L300); minor attribution loss.
- (d) Two stray double-quote artifacts: `"short path"` (summary L61) and `"and the short path"` (L61) — formatting, not factual.

**Hallucinations detected: 0.** The summary is meticulously faithful. The log's postcheck "fixes" are paraphrase hygiene, not corrections of fabricated content.

### Missing Information (critical omissions from the source absent in the summary)

1. **The CONCLUSION section's seven-point characteristics list of a solid identity (source L449-451) is not rendered as a coherent list anywhere in the summary.** This is the chapter's capstone — the cross-sectional definition of "solid identity" and, by inversion, of "identity diffusion." The log shows V18.15.9.1 added a consolidated Characteristics bullet (log L681), but the ship-time bullet budget cut 53→40 (log L687, "remediation bullets trimmed") dropped it. Two of the seven items are entirely absent from the summary:
   - "(1) a sustained feeling of selfsameness displaying roughly similar character traits to varied others"
   - "(5) a sense of inner solidity and the associated capacity for peaceful solitude"
   The other five are present only as scattered fragments across the thorough/bullets (temporal continuity, authenticity, body image, gender clarity, ethnic solidarity), never assembled as the author's concluding list.

2. **Five named theorists present in the source are entirely absent from the shipped summary:** Lasch (1978), Kovel (1981), Federn (1952), Glover (1950), Spiegel (1959) — all cited in source L90-91 and L187-191. The log's V18.14.1 batch gap-fill added coverage for them (log L613-675), but the ship-time bullet budget (log L687) trimmed those gap-fill bullets. The recall floor (log L765) honestly reports: "theorists 20/37 in final bullets (missing: ['Lasch', 'Kovel', 'Federn', 'Glover', 'Spiegel'])."

3. **The thorough summary covers only 13/37 named theorists (35%).** Five theorists present in the source's developmental section — Hartmann, Eissler, Wheelis, Lynd, Lifton — appear only in the bullets (added by gap-fill rounds 1-2), never in the thorough paragraph. The thorough theorist floor gap-fill (V18.20.3.13) identified this gap (log L761) but was **skipped because the chapter exceeded the 1200s deadline** (1551s actual; log L763).

### Quality Notes

- **Structure (Good):** The thorough summary follows the chapter's developmental sequence faithfully (Concept → Lichtenstein → Freud → Fenichel → Greenacre → Mahler → Jacobson → Winnicott → Kernberg → Chasseguet-Smirgel → Blos). Temporal/causal flow is preserved. The Key Distinctions and Theoretical Tensions sections are excellent — they capture the long/short oedipal path, true/false self, identity principle/metamorphosis, and the intrapsychic-vs-sociocultural tension with high fidelity.
- **Executive Summary = Thorough Summary (defect):** The Executive Summary and the Thorough Summary are byte-identical (the same ~800-word paragraph). The log explains: the exec-from-thorough derivation produced CoT narrative and was discarded (log L697, "V18.19.2.2: Exec truncated to empty by CoT detection — falling back to thorough summary"). The F1 target (log L519) is exec ≤250 words; both shipped at ~800. This wastes the executive slot and produces a redundant section.
- **Verbless label-stub bullets (defect):** Several bullets survive as topic labels with no predicate: "Emphasize social aspect" (L13), "Two difficulties: term 'das Ich (ego) and usage of identity'" (L21), "Two conditions for ego organization and drive neutralization:" (L26), "Oedipal child has two routes:" (L36). The log's scar_label_stub detector dropped stubs <8 words (log L707-718), but these are ≥8 words and escaped the filter; the grammar/flag detector noted them (log L701-715) but does not drop. They ship as low-information-density bullets.
- **Density (Good overall, with thin spots):** The thorough summary is informationally dense (many named theorists, dates, concepts). The Key Takeaways bullets are mostly specific, but a few are thin ("Lynd appears in the same grouping of scholars…", "Lifton is listed among the prominent contributors…") — these name a scholar without stating their claim.
- **Minor formatting artifacts:** Stray double-quote in `"the short path"` (L61); minor, cosmetic.

---

## Part 2 — Structured JSON Scorecard (Machine-Parsable)

```json
{
  "summary_id": "001_1_-_IDENTITY_AND_ITS_ORIGINS__run20260920-084745-c0874728_v0.18",
  "overall_score": 7,
  "factual_consistency_score": 9,
  "coverage_score": 6,
  "clarity_score": 8,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 3,
  "verdict": "PASS",
  "justification": "Factually flawless (0 hallucinations, every claim source-grounded) but coverage falls below the 9-10 bar: the chapter's seven-point conclusion list is missing as a coherent list (2/7 items entirely absent), five named theorists (Lasch, Kovel, Federn, Glover, Spiegel) are absent, and the thorough summary covers only 13/37 theorists (35%) because the thorough floor gap-fill was skipped on a deadline overrun."
}
```

> **Mechanical verdict rule:** FAIL if `factual_consistency_score < 6` OR `coverage_score < 5`. This run: factual 9 ≥ 6, coverage 6 ≥ 5 → **PASS**, but **below the V0.20 campaign bar of 9–10/10**.
>
> **Coverage score (6) matches the deterministic recall floor** (theorists 54%, conclusion items 71%, thorough 35%) — the honest number, not the LLM judge's 100% claim-recall.

---

## Comparison anchor — for the next audit

This is the **V0.18 baseline**. When the owner re-runs the same chapter with the V0.20 build (`main`, commit `4e5169a`), the new audit will be filed as `AUDIT_V0.20_<new_run_id>.md` and compared directly against this scorecard. Expected movement (projected from the 3 V0.20 fixes already on `main`):

| Pillar | V0.18 baseline | V0.20 projected | Driver |
|---|---|---|---|
| factual_consistency | 9 | 9 (unchanged) | no fix touches facts |
| coverage | 6 | 7–8 | `f6fbfa3` rescues 5 theorists + 2 conclusion items at the V0.06 cap; `b63d1ac` weaves ~5 theorists into the thorough |
| clarity | 8 | 8.5–9 | `076bf4b` drops the 2 colon-ending label stubs |
| overall | 7 | ~8–8.5 | approaching the 9-10 bar |

The honest recall-floor lines to compare in the next log:
- V0.18: `theorists 20/37 (54%), conclusion items 5/7 (71%)`, thorough `13/37 (35%)`
- V0.20 target: `theorists ≥25/37`, `conclusion items 7/7`, thorough `≥18/37`
