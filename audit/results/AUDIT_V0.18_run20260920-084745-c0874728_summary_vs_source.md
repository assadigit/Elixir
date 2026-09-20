# AUDIT #1 — Summary vs Source — version V0.18 (run 20260920-084745-c0874728)

> **Audit version:** `V0.18 / run 20260920-084745-c0874728 / app 0.18 / 2026-09-20T08:47:45 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 1 "IDENTITY AND ITS ORIGINS"
> **Audit framework:** the standing four-pillar expert fact-checker (verbatim prompt in `docs/EVALUATION_FRAMEWORK.md`).
> **Comparison anchor:** this is the **V0.18 baseline** — the same run audited in `AUDIT_V0.18_run20260920-084745-c0874728.md` (the versioned baseline file). The scorecard below is reproduced from that file for this audit cycle. The next audit (after a re-run with the V0.20.1 build on `main`, tag `V0.20.1`) will be filed as `AUDIT_V0.20.1_<new_run_id>.md` and compared directly against this scorecard.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol)

| Field | Summary stamp | Conversion log | Match |
|---|---|---|---|
| `run_id` | `20260920-084745-c0874728` | log L869: `run_id=20260920-084745-c0874728` | ✓ |
| `app_version` | `0.18` | log L61: `App version: 0.18` | ✓ |
| `started` | `2026-09-20T08:47:45` | log L3 + L869 | ✓ |
| `bullets` | `40` | log L775: `bullets=40` | ✓ |

- **Source chapter** uploaded by the owner is **byte-identical** to `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md` (body match confirmed; 6,425 words, 9,120 tokens, PDF pp.15–32).
- **Provenance verdict: PASS** — this is the genuine V0.18 output of run `20260920-084745-c0874728`.

> ⚠️ **This is the SAME V0.18 run as the previous two uploads** (run_id `20260920-084745-c0874728`, app v0.18, same 899-line log, same 76-line summary — the summary SHA-256 prefix `be5ca90ecbfed4ac` matches the prior upload). The `app_version` stamp reads `0.18`; a V0.20.1 run would stamp `v0.20.1`. **To verify the 3 V0.20.1 fixes (coverage-aware V0.06 cap, non-skippable thorough floor, colon-ending label-stub detector), pull tag `V0.20.1` from GitHub and re-run the same chapter.** The V0.18 scorecard below is the baseline the V0.20.1 audit will be compared against.

---

## Part 1 — Detailed Report (Human-Readable)

### Fact-Check Log

I extracted every factual claim from the Candidate Summary (Executive Summary paragraph, 40 Key Takeaways bullets, Key Distinctions, Theoretical Tensions) and traced each to the Source Text. **No hard hallucinations were found.** Every named theorist, date, quoted phrase, and causal claim I checked is directly supported by the source. The conversion-log postcheck "quote-verification/fix" entries (log L719–753) are paraphrase hygiene (quotation marks stripped from near-verbatim-but-not-exact quotes), not hallucination corrections.

Verified claims (representative sample, 25 of ~60 checked):

| # | Candidate claim | Source evidence | Verdict |
|---|---|---|---|
| 1 | "The term identity was introduced into psychoanalytic discourse by Tausk (1919)" | L51: "The term identity was introduced into the psychoanalytic literature by Tausk (1919)" | ✓ |
| 2 | "Freud invoked it technically only once, in his 1926 address to B'nai B'rith" | L53 | ✓ |
| 3 | "of the ninety-two times he used the word, ninety-one were colloquial or literal" | L153-154 | ✓ |
| 4 | "Erikson (1950a, 1956, 1958, 1959) resurrected the concept…'a persistent sameness within oneself' and 'a persistent sharing of some kind of essential character with others.'" | L55-56 + L64-65 | ✓ |
| 5 | "Kernberg…declared that identity diffusion most clearly differentiates borderline from non-borderline conditions" | L59-60 (Kernberg 1980 p.14) | ✓ |
| 6 | "Lichtenstein…identity principle…metamorphosis—a loss that can be experienced as liberation or ecstasy" | L113-127 | ✓ |
| 7 | "the mother imprints not a fixed identity but an 'identity theme, irreversible yet capable of variations'" | L122-123 | ✓ |
| 8 | "Sexual union…demonstrates both forces simultaneously" | L129-132 | ✓ |
| 9 | "Fenichel (1937, 1945)…self-image originates from direct awareness of inner experience and indirect perception of the bodily-mental self as object" | L181-182 | ✓ |
| 10 | "'into the formation of every ego there have gone many identifications' (1945)" | L185 (1945 p.77) | ✓ |
| 11 | "Greenacre…habitual visual incorporation of opposite-sex genitals…early repeated exposure among twins…particularly if occurring in phallic or oedipal phases" | L203-206 | ✓ |
| 12 | "Mahler…sequence of phases: autistic, symbiotic, differentiation, practicing—'conquest of the world'—and rapprochement" | L215-221 | ✓ |
| 13 | "two conditions for ego organization: enteroceptive-proprioceptive stimuli…mother must buffer and organize stimuli" | L230-234 | ✓ |
| 14 | "Self-constancy emerges at approximately two years" | L236 | ✓ |
| 15 | "Jacobson (1964) formulated five categories" | L260-264 | ✓ |
| 16 | "'not only the loving but also the hostile components furnish the fuel for developing feelings of identity'" | L291-296 (Jacobson 1964 p.61) | ✓ |
| 17 | "Winnicott…infant's spontaneous gestures emanate from the true self, while maternal failure to decode…produces a false self through compliance" | L301-306 | ✓ |
| 18 | "The infant is a psychosomatic being, and the true self derives from the aliveness of body tissues and working of body functions" | L313-314 (Winnicott 1960 p.144, p.148) | ✓ |
| 19 | "'all processes of a live infant constitute a going-on-being, kind of blueprint for existentialism'" | L321 (Winnicott 1960 p.86) | ✓ |
| 20 | "Kernberg…two essential tasks…differentiation of self from object images through libidinal gratification and frustration, and integration of self-object images" | L331-345 | ✓ |
| 21 | "'libidinal gratification draws attention cathexes…fosters differentiation'…'frustration brings to awareness the painful absence…differentiate self from non-self'" | L335-337 (Kernberg 1975a p.26) | ✓ |
| 22 | "three-step process—introjection, identification, and identity formation—culminating in a harmonious gestalt where identifications become depersonified" | L354-366 | ✓ |
| 23 | "distinguished the adolescent identity crisis from identity diffusion syndrome (correlated with borderline character organization)" | L368-370 | ✓ |
| 24 | "Chasseguet-Smirgel…two oedipal routes: the long path…ego ideal with hope and temporal order; and the short path…perverse character organization where ego and ego ideal fuse and filial links are severed" | L381-399 | ✓ |
| 25 | "Blos…adolescence as a second individuation…radical alterations in ego structure and consolidation of sexual identity through renunciation of parents as sexual objects, reconciliation of activity and passivity, and resolution of bisexual identifications" | L408-427 | ✓ |

**Flagged items (minor, none rise to hallucination):**
- (a) Bullet L37 attributes "sine qua non" to "Jacobson (1964)" alone; source L40-41 attributes it jointly to "Jacobson 1964, Kernberg 1967".
- (b) Summary L7 says "the mother imprints not a fixed identity" where source L122 says "not an identity" — mild interpolation, meaning unchanged.
- (c) Summary L7 drops the source's attribution of "corporeality" to Khan (1983) (source L300).
- (d) Stray double-quote artifacts in `"short path"` (L61) — formatting, not factual.

**Hallucinations detected: 0.**

### Missing Information (critical omissions from the source absent in the summary)

1. **The CONCLUSION section's seven-point characteristics list of a solid identity (source L449-451) is not rendered as a coherent list anywhere in the summary.** Two of the seven items are entirely absent:
   - "(1) a sustained feeling of selfsameness displaying roughly similar character traits to varied others"
   - "(5) a sense of inner solidity and the associated capacity for peaceful solitude"

2. **Five named theorists are entirely absent from the shipped summary:** Lasch (1978), Kovel (1981), Federn (1952), Glover (1950), Spiegel (1959). The deterministic recall floor (log L765) honestly reports: "theorists 20/37 in final bullets (missing: ['Lasch', 'Kovel', 'Federn', 'Glover', 'Spiegel'])."

3. **The thorough summary covers only 13/37 named theorists (35%).** Five theorists (Hartmann, Eissler, Wheelis, Lynd, Lifton) appear only in the bullets, never in the thorough paragraph. The thorough theorist floor gap-fill (V18.20.3.13) identified this gap (log L761) but was **skipped because the chapter exceeded the 1200s deadline** (1551s actual; log L763).

### Quality Notes

- **Structure (Good):** The thorough summary follows the chapter's developmental sequence faithfully. The Key Distinctions and Theoretical Tensions sections are excellent.
- **Executive Summary = Thorough Summary (defect):** byte-identical ~800-word paragraph. The exec-from-thorough derivation produced CoT and fell back (log L697). F1 target is exec ≤250 words; both shipped at ~800.
- **Verbless label-stub bullets (defect):** "Two conditions for ego organization and drive neutralization:" (L26), "Oedipal child has two routes:" (L36) — colon-ending labels whose sub-content is absent.
- **Density (Good overall, with thin spots):** A few bullets name a scholar without stating their claim ("Lynd appears in the same grouping…", "Lifton is listed among the prominent contributors…").

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
> **This scorecard is the V0.18 baseline.** The next audit (V0.20.1, after a re-run with tag `V0.20.1`) will be compared against these numbers. Projected V0.20.1: factual 9, coverage 7–8, clarity 8.5–9, overall ~8–8.5.
