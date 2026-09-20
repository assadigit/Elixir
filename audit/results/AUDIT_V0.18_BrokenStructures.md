# AUDIT V0.18 — Broken Structures (Salman Akhtar), ch.1 "IDENTITY AND ITS ORIGINS"

> Four-pillar expert fact-checker audit, per `docs/EVALUATION_FRAMEWORK.md`.
> Operating mode: USER-RIG (owner ran the V0.18 pipeline on the real rig and
> provided the outputs + conversion log; session audits, cross-checks
> provenance, diagnoses, and lands fixes).
>
- **Source Text (Gold Standard):** `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md` (6,425 words, 9,120 tokens, PDF pp.15–32). Uploaded copy byte-identical to ground truth.
- **Candidate Summary:** `001_1_-_IDENTITY_AND_ITS_ORIGINS_summary.md` — 40 bullets, exec + thorough + key distinctions + theoretical tensions.
- **Conversion log:** `Broken Structures Salman Akhtar.conversion.log.md` (899 lines).
- **Provenance:** `run_id=20260920-084745-c0874728`, app v0.18, started 2026-09-20T08:47:45, 40 bullets — **matches log line 869**. PASS.
- **Honest coverage (deterministic recall floor, log line 765):** theorists 20/37 (54%) in final bullets; conclusion items 5/7 (71%); thorough 13/37 (35%). The LLM judge's 100% claim-recall (log line 541) overstates content recall, per the EVALUATION_FRAMEWORK house note.

---

## Part 1 — Detailed Report (Human-Readable)

### Fact-Check Log

I extracted every factual claim from the Candidate Summary and traced it to the Source Text. **No hard hallucinations were found.** Every named theorist, date, quoted phrase, and causal claim I checked is directly supported by the source. The conversion-log postcheck "quote-verification/fix" entries (log lines 719–753) are paraphrase hygiene (quotation marks stripped from near-verbatim-but-not-exact quotes), not hallucination corrections — the underlying claims are all source-grounded.

Verified claims (representative sample, 25 of ~60 checked):

| # | Candidate claim | Source evidence (line/quote) | Verdict |
|---|---|---|---|
| 1 | "The term identity was introduced into psychoanalytic discourse by Tausk (1919)" | L51: "The term identity was introduced into the psychoanalytic literature by Tausk (1919)" | ✓ |
| 2 | "Freud invoked it technically only once, in his 1926 address to B'nai B'rith" | L53: "Freud…referred to the concept of identity only once…in his address to B'nai B'rith (Freud 1926a)" | ✓ |
| 3 | "of the ninety-two times he used the word, ninety-one were colloquial or literal" | L153-154: "of the ninety-two times that Freud used the word identity…ninety-one were in a colloquial and/or literal sense" | ✓ |
| 4 | "Erikson (1950a, 1956, 1958, 1959) resurrected the concept…defining ego identity as both 'a persistent sameness within oneself' and 'a persistent sharing of some kind of essential character with others.'" | L55-56 + L64-65: "Erikson (1950a, 1956, 1958, 1959) resurrected the term…'both a persistent sameness within oneself (selfsameness) and a persistent sharing of some kind of essential character with others' (p. 12)" | ✓ (summary drops "(selfsameness)" parenthetical — minor) |
| 5 | "Kernberg…declared that identity diffusion most clearly differentiates borderline from non-borderline conditions" | L59-60: "in 1980, he declared that 'it is the presence or absence of identity diffusion that most clearly differentiates borderline from non-borderline conditions' (p. 14)" | ✓ |
| 6 | "Lichtenstein…two opposing forces…identity principle…metamorphosis—a loss that can be experienced as liberation or ecstasy" | L113-127: "identity principle…perpetual drive of man to maintain his historical existence…longing to abandon the human quality of identity…metamorphosis…loss can be experienced as liberation and ecstasy" | ✓ |
| 7 | "the mother imprints not a fixed identity but an 'identity theme, irreversible yet capable of variations'" | L122-123: "The mother imprints upon the infant not an identity, but an 'identity theme.' This theme is irreversible, but it is capable of variations" | ✓ (summary says "not a fixed identity" vs source "not an identity" — minor paraphrase) |
| 8 | "Sexual union…demonstrates both forces simultaneously: the individual becomes an instrument fulfilling another's needs…while also surrendering identity altogether in metamorphosis" | L129-132: "Sexual union…an individual become 'an instrument for the fulfillment of another one's needs'…living out the symbiotic 'identity theme'…surrendering one's identity altogether and undergoing metamorphosis" | ✓ |
| 9 | "Fenichel (1937, 1945)…self-image originates from direct awareness of inner experience and indirect perception of the bodily-mental self as object" | L181-182: "Fenichel (1937) suggested that the image of our self originates from two sources: the direct awareness of our inner experience and the indirect perception of our bodily and mental self as an object" | ✓ |
| 10 | "'into the formation of every ego there have gone many identifications' (1945)" | L185: "into 'the formation of every ego there have gone many identifications' (1945, p. 77)" | ✓ |
| 11 | "Greenacre…habitual visual incorporation of opposite-sex genitals…early repeated exposure among twins may lead to marked primary incorporation…particularly if occurring in phallic or oedipal phases" | L203-206: "habitual taking in through vision of the opposite-sex genitals…early and repeated exposure to the genitals of the opposite sex among twins…marked primary incorporation…more marked if such exposure occurs largely in the phallic and oedipal phases" | ✓ |
| 12 | "Mahler…sequence of phases: the autistic phase, the symbiotic phase, the differentiation phase, the practicing phase—where the toddler elatedly enjoys psychic autonomy in a conquest of the world—and the rapprochement phase" | L215-221: all five phases verbatim; "the toddler elatedly enjoys his newfound psychic autonomy and motoric freedom and appears to be involved in the 'conquest of the world'" | ✓ |
| 13 | "two conditions for ego organization: enteroceptive-proprioceptive stimuli must not be so intense as to prevent structure formation, and the mother must buffer and organize stimuli" | L230-234: "(1) the enteroceptive-proprioceptive stimuli must not be so continual and so intense as to prevent structure formation…and (2) the mother must be able to buffer and organize inner and other stimuli for the infant" | ✓ |
| 14 | "Self-constancy emerges at approximately two years" | L236: "self constancy…comes into being…at approximately two years of age" | ✓ |
| 15 | "Jacobson (1964) formulated five categories…self- and object representations, fused self-object representation as the first intrapsychic structure, identity emerging from primitive identifications, aggression's role in self-delineation, and modifications to oedipal resolution" | L260-264: all five categories verbatim | ✓ |
| 16 | "'not only the loving but also the hostile components furnish the fuel for developing feelings of identity'" | L291-296: "not only the loving but also the hostile components of the infantile self and object directed strivings furnish the fuel that enables the child to develop his feelings of identity" | ✓ |
| 17 | "Winnicott…infant's spontaneous gestures emanate from the true self, while maternal failure to decode the infant's overture produces a false self through compliance" | L301-306 | ✓ |
| 18 | "The infant is a psychosomatic being, and the true self derives from the aliveness of body tissues and working of body functions" | L313-314: "'psychosomatic being' (1960, p. 144)…'the aliveness of body tissues and working of body functions' (1960, p. 148)" | ✓ |
| 19 | "'all processes of a live infant constitute a going-on-being, kind of blueprint for existentialism'" | L321 | ✓ |
| 20 | "Kernberg…two essential tasks…differentiation of self from object images through libidinal gratification and frustration, and integration of self-object images built under loving versus aggressive drives" | L331-345 | ✓ |
| 21 | "'libidinal gratification draws attention cathexes to the interaction between self and objects and fosters differentiation'…'frustration brings to awareness the painful absence of fulfilling objects and thus contributes to differentiate self from non-self'" | L335-337 (Kernberg 1975a p.26) | ✓ |
| 22 | "three-step process—introjection, identification, and identity formation—culminating in a harmonious gestalt where identifications become depersonified" | L354-366 | ✓ |
| 23 | "distinguished the adolescent identity crisis from identity diffusion syndrome (correlated with borderline character organization)" | L368-370 | ✓ |
| 24 | "Chasseguet-Smirgel…two oedipal routes: the long path…ego ideal with hope and temporal order; and the short path…perverse character organization where ego and ego ideal fuse and filial links are severed" | L381-399 | ✓ |
| 25 | "Blos…adolescence as a second individuation…radical alterations in ego structure and consolidation of sexual identity through renunciation of parents as sexual objects, reconciliation of activity and passivity, and resolution of bisexual identifications" | L408-427 | ✓ |

**Flagged items (minor, none rise to hallucination):**
- (a) Bullet L37 attributes "sine qua non of borderline and narcissistic character disorders" to "Jacobson (1964)" alone; source L40-41 attributes it jointly to "Jacobson 1964, Kernberg 1967". Defensible (Jacobson is one of the two) but slightly misleading as a sole attribution.
- (b) Summary L7 says "the mother imprints not a fixed identity" where source L122 says "not an identity"; the added word "fixed" is a mild interpolation but does not change the meaning.
- (c) Summary L7 drops the source's attribution of "corporeality" to Khan (1983) (source L300); minor attribution loss.
- (d) Two stray double-quote artifacts: "short path"" (summary L61) and "and the short path"" (L61) — formatting, not factual.

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
- **Minor formatting artifacts:** Stray double-quote in "the short path"" (L61); minor, cosmetic.

---

## Part 2 — Structured JSON Scorecard

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

> Verdict is PASS by the mechanical rule (factual_consistency 9 ≥ 6, coverage 6 ≥ 5), but **below the campaign bar of 9-10/10**. The scorecard's coverage_score (6) matches the deterministic recall floor (theorists 54%, conclusion items 71%) — the honest number — not the LLM judge's 100% claim-recall.

---

## Diagnosis — map of defects to owning pipeline stages

| Defect | Owning stage (code location) | Evidence (log line / audit finding) |
|---|---|---|
| **A. Missing 7-point conclusion list (2/7 items absent)** | Ship-time bullet budget (V0.06) trims remediation bullets first → drops the V18.15.9.1 consolidated Characteristics bullet | Log L681 (added) → L687 (trimmed 53→40, "remediation bullets trimmed"). Recall floor L765: conclusion items 5/7. |
| **B. 5 named theorists absent (Lasch, Kovel, Federn, Glover, Spiegel)** | Ship-time bullet budget trims gap-fill bullets first → drops V18.14.1 gap-fill bullets | Log L675 (27 gap-fill bullets added) → L687 (trimmed 53→40). Recall floor L765: theorists 20/37, missing those 5. |
| **C. Thorough covers only 13/37 theorists (missing Hartmann, Eissler, Wheelis, Lynd, Lifton)** | Thorough theorist floor gap-fill (V18.20.3.13) skipped on deadline overrun (1551s > 1200s) | Log L761 (floor identified 13/37) → L763 (deadline exceeded → skipped). |
| **D. Executive Summary = Thorough Summary (redundant)** | Exec-from-thorough derivation (V18.15.8.0 / V18.19.2.2) produced CoT → discarded → fallback to thorough | Log L505-513 (CoT discarded) → L697 (fallback). |
| **E. Verbless label-stub bullets shipped** | scar_label_stub detector's <8-word filter misses ≥8-word stubs; grammar/flag notes but does not drop | Log L707-718 (stubs <8w dropped) vs L701-715 (≥8w flagged only). Summary L13/L21/L26/L36. |
| **F. 5/11 LLM calls truncated (output cap 8192)** | Low-bit quant + 12GB card caps output at 8192 tokens (V18.2.43) | Log L873 (truncated 5); L393-395 (cap). Rig constraint, not a code bug — but the scholar-reflection truncation (log L559-575, "identified gaps but could not fill them") shifts the entire gap-fill load onto the V18.14.1 batch path. |

**Highest-value, evidence-supported fix (single root cause for Defects A + B):**
The ship-time bullet budget (V0.06) trims "remediation bullets first" — but remediation bullets are exactly the ones that carry the recall floor (gap-fill theorists + consolidated conclusion). Trimming them first defeats the gap-fill and the conclusion consolidation that the pipeline just spent ~6 minutes (log L603-675) producing. The recall floor (log L765) honestly reports the damage: 5 theorists and 2 conclusion items lost.

The smallest change the evidence supports: **the ship-time bullet budget must not trim a remediation bullet that is the sole carrier of a recall-floor item** (a gap-fill theorist bullet for a theorist otherwise absent, or the consolidated conclusion bullet). Protect those bullets; trim other dedup candidates instead. One audit-finding family (coverage) → one conventional commit.
