# AUDIT — Summary vs Source — version V0.20.2 (run 20260921-003234-00d02c99) — ch.2

> **Audit version:** `V0.20.2 / run 20260921-003234-00d02c99 / app 0.20.2 / 2026-09-21T00:32:34 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 2 "THE SYNDROME OF IDENTITY DIFFUSION" (pp.33–46, 4,625 words, 6,166 tokens)
> **Audit framework:** the standing four-pillar expert fact-checker (verbatim prompt in `docs/EVALUATION_FRAMEWORK.md`).
> **Comparison anchor:** this is the **first V0.20.2 audit** — a different chapter from the V0.18 baseline (ch.1). The V0.18 baseline scorecard (ch.1) is in `AUDIT_V0.18_run20260920-084745-c0874728_summary_vs_source.md`. This audit establishes the V0.20.2 baseline for ch.2; future re-runs of ch.2 will be compared against this scorecard.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol)

| Field | Summary stamp | Evidence | Match |
|---|---|---|---|
| `run_id` | `20260921-003234-00d02c99` | summary line 3 + line 128 (footer) | ✓ NEW (not the old `20260920-084745-c0874728`) |
| `app_version` | `0.20.2` | summary line 3: `generated-by: Elixir v0.20.2` | ✓ **V0.20.2 confirmed** |
| `started` | `2026-09-21T00:32:34` | summary line 3 | ✓ (the day after the V0.18 run — a fresh run) |
| `bullets` | `40` | summary line 3 | ✓ |
| Source frontmatter `date_processed` | `2026-09-21T00:32:31` | source line 23 | ✓ (3 seconds before the summary started — matches) |

- **Source chapter** uploaded by the owner (`001_2 - THE SYNDROME OF IDENTITY DIFFUSION.md`, 348 lines) is the full chapter text, pp.33–46, 4,625 words, 6,166 tokens. The frontmatter `date_processed: 2026-09-21T00:32:31` matches the run.
- **Conversion log:** the uploaded `Broken Structures Salman Akhtar.conversion.log.md` is the **old V0.18 log** (899 lines, `Started at: 2026-09-20T08:45:57`, `App version: 0.18`, `run_id=20260920-084745-c0874728`, SHA-256 `3a443ff98cea42b5` — identical to all prior uploads). It does **not** cover the ch.2 run. The user likely uploaded the wrong log file alongside the new ch.2 summary. **This audit is based on the summary + source alone; the conversion-log cross-check is deferred until the correct V0.20.2 log is uploaded.**
- **Provenance verdict: PASS** — the chapter 2 summary is the genuine V0.20.2 output of run `20260921-003234-00d02c99`. The user forced a fresh run by selecting a different chapter (resume mode can't skip a chapter that was never processed).

---

## Part 1 — Detailed Report (Human-Readable)

### Fact-Check Log

I extracted every factual claim from the Candidate Summary (Executive Summary paragraph, 40 Key Takeaways bullets, Thorough Summary, Key Distinctions, Theoretical Tensions) and traced each to the Source Text. **No hard hallucinations were found.** Every named theorist, date, quoted phrase, and causal claim I checked is directly supported by the source. I verified 20 representative claims against the source (Erikson 1950/1956, Mahler 1968, Chasseguet-Smirgel 1983, Reich 1954, Freud 1923a, Deutsch 1942, Goldberg 1983, Ferenczi 1926a, Waelder 1930, Adler 1981, Galenson and Roiphe 1971, Meyer 1982, Bach 1977, Kretschmer 1925, Stern 1938, Pfeiffer 1974, and more) — all 20 are source-grounded.

Verified claims (representative sample, 20 of ~70 checked):

| # | Candidate claim | Source evidence (line) | Verdict |
|---|---|---|---|
| 1 | "Erikson (1950) first used the term 'identity diffusion'" | L39: "The term identity diffusion was first used by Erikson in 1950" | ✓ |
| 2 | "Erikson (1956) described associated clinical phenomena: impaired intimacy, diffusion of time perspective, diminished sense of workmanship, hostility toward family-offered roles, and conflicts about ethnic origins" | L40-41 | ✓ |
| 3 | "adolescents...raised by intrusive, appearance-conscious mothers and weak, insecure fathers" | L42 | ✓ |
| 4 | "developmental...arrested at the rapprochement subphase (Mahler 1968)" | L51-52 | ✓ |
| 5 | "Chasseguet-Smirgel (1983)...regressive attachment to an 'anal universe'" | L52-53 | ✓ |
| 6 | "dynamic...continued active presence of magic identifications (Reich 1954), unmetabolized introjects (Kernberg 1967)...splitting over repression" | L54-56 | ✓ |
| 7 | "contradictory character traits include coexisting tenderness and indifference, naivete and suspiciousness, shyness and exhibitionism, greed and self-denial, and arrogance and timidity" | L61-63 | ✓ |
| 8 | "necklace versus loose beads not connected by a meaningful thread" | L79-80 | ✓ |
| 9 | "Freud (1923a) stated that if the ego's object identifications become too numerous, unduly powerful, and incompatible...different identifications may seize hold of consciousness in turn" | L86-93 | ✓ |
| 10 | "Fast (1974), Abse (1983), Buck (1983), and Benner and Joscelyne (1984)...similarities and differences between identity diffusion and multiple personality" | L95-96 | ✓ |
| 11 | "Deutsch's (1942) as-if personality...four characteristics: passive plasticity, shallow morality, automatonlike suggestibility, and splitting off of aggression" | L132-134 | ✓ |
| 12 | "Freud (1923a) stated that the ego is first and foremost a bodily ego" | L152 | ✓ |
| 13 | "body image disturbances...feeling they exist only from the neck up, erroneous assessments of weight or height, and feeling genitals are inadequate" | L160-162 | ✓ |
| 14 | "Kernberg (1975a) and Singer (1977a,b)...feelings of emptiness, distinct from loneliness" | L170-174, L186-190 | ✓ |
| 15 | "Khan (1983) felt such outrageousness is a frequent flamboyant persona for a missing inner solidity" | L182 | ✓ |
| 16 | "core gender identity (Stoller 1968), gender role (Tyson 1982), and sexual partner orientation (Green 1975)" | L198-200 | ✓ |
| 17 | "sphincter morality (Ferenczi 1926a), where governance comes from external reward and punishment rather than from inner standards" | L236 | ✓ |
| 18 | "principle of multiple function (Waelder 1930) and means many things simultaneously" | L345-346 | ✓ |
| 19 | "Meyer (1982)...many transsexuals seeking sex-reassignment surgery display borderline personality organization" | L213-214 | ✓ |
| 20 | "Adler (1981)...individuals without serious identity disturbances develop firmer therapeutic alliances" | L325-326 | ✓ |

**Hallucinations detected: 0.** The summary is factually faithful. Every named theorist, date, and quoted phrase traces to the source.

### 🚨 Critical defect found — CoT thinking block leaked into the Thorough Summary

The Thorough Summary section (line 54) contains the actual thorough paragraph, which is excellent. But immediately after it (lines 56–107), a **large chain-of-thought (CoT) thinking block is leaked verbatim into the shipped summary**. The leaked text begins:

> "The user wants me to write 1-2 paragraphs (150-300 words) that weave in specific contributors from the chapter, each with their specific contribution as described in the source text. Let me identify each contributor and their specific contribution:
> 1. Chasseguet-Smirgel - mentioned multiple times: regressive attachment to an "anal universe" (1983); successful resolution of Oedipus complex adds entry into father's universe (1984); commentary on superego defects (1984); writing about individuals who use aliases/erase identities (1984)
> 2. Levy - "eternal dilettante" (1949)...
> ..."

and continues for ~52 lines of raw model reasoning (numbered lists, "Wait, this is...", "Hmm, could 'Erikson in' be a misread...", "Let me re-read the list...", etc.), ending mid-item at "17. **Goldberg** (1983): experience of oneself as a 'chronic misfit' associated with subjective". The "Key Distinctions" section then resumes normally at line 109.

**This is the thorough-theorist-floor gap-fill call's raw thinking output, leaked into the shipped thorough summary.** The CoT stripping (`detect_cot_narrative` + `_strip_thinking`) did not catch this shape — the thinking is in a numbered-list format (not the `<thinking>...</thinking>` tag format the strip functions look for), and it wasn't wrapped in `<thorough_addition>...</thorough_addition>` tags (the format the thorough-floor gap-fill requests), so the tag-based extraction fell through to the raw cleaned text, which included the thinking.

**Impact:** This is a **clarity/cleanliness regression introduced by V0.20.2**. The V0.20.1 Fix 2 made the thorough-theorist floor NON-SKIPPABLE on deadline (so the gap-fill call now always fires). On this chapter, the call produced a CoT-inundated response that wasn't stripped, and the raw thinking shipped into the delivered summary. The V0.18 ch.1 run didn't hit this because the thorough floor was skipped on the deadline overrun (the V0.18 Defect C). **Making the floor non-skippable exposed a CoT-leak path that was previously dormant.**

**Root cause (preliminary, pending the V0.20.2 conversion log):** `core/summarisation/thorough_theorist_floor.py` L198-225 has a CoT guard (`detect_cot_narrative`) and a `<thorough_addition>` tag extraction. The guard looks for CoT *markers* (phrases like "Let me", "Wait", "Hmm"). The leaked block contains all of these markers ("Let me identify", "Wait, this is", "Hmm, could 'Erikson in' be a misread", "Let me re-read"), so `detect_cot_narrative` should have caught it — unless the detection threshold (number of markers) wasn't met, or the function was looking at a different slice of the response. This needs a fix in the thorough-floor's CoT handling.

### Missing Information (critical omissions from the source absent in the summary)

1. **The chapter's opening epigraph** (Yevgeny Yevtushenko, "The Face Behind Face" — L29-37) is not mentioned. Minor — epigraphs are often omitted, but it sets the tonal frame for the chapter.

2. **The "eternal dilettante" clinical example** (L70-73 — "the persistence into adulthood of equally strong desires to become a physician and a movie star represents an ill-organized ego identity") is referenced by name in the bullets but the *specific* physician/movie-star example (which is the illustrative core of the concept) is absent from the thorough.

3. **The detailed four-item list of Deutsch's "as-if" personality characteristics** is in the summary, but the *quote* explaining why it differs from repression ("it is no longer an act of repression but a real loss of object cathexis", L139-143) is absent — this is the theoretically load-bearing distinction Deutsch drew, and it's what separates "as-if" pathology from ordinary neurotic coldness.

### Quality Notes

- **Executive Summary (Excellent):** A clean, dense, ~190-word paragraph that captures the chapter's structure (origin → three perspectives → seven features → differential diagnosis → conclusion → three clinical advantages → principle of multiple function). This is a **major improvement over V0.18** — the V0.18 ch.1 exec was byte-identical to the thorough (the V0.18 Defect D). The V0.20.2 exec is a genuine, distinct, concise executive summary. **The V0.20.2 chunking fix (Fix C) worked** — the primary call produced a real exec instead of CoT-inundating it.
- **Key Takeaways (Good):** 40 bullets, mostly specific and source-grounded. A few late bullets are thin ("Bach: The source describes Bach's (1977) work as pointing out peculiar thermal sensitivity and skin mascomism..." — "skin mascomism" is a typo for "skin masochism"; the bullet phrases it as "The source describes..." which is a meta-narrative voice, not a direct claim). The "Abraham, Greenacre, Deutsch, Gediman wrote on alias/name-changers..." bullet ends with a stray "..." that suggests truncation.
- **Thorough Summary (Good content, CRITICAL formatting defect):** The thorough paragraph itself (line 54) is excellent — it follows the chapter's structure faithfully (origin → three perspectives → seven features → differential diagnosis → conclusion → clinical advantages → principle of multiple function) with high density and accurate attributions. **But the CoT leak (lines 56-107) destroys the section's readability** — a reader sees the thorough paragraph end, then 52 lines of raw model thinking, then the Key Distinctions. This is the single most damaging defect in the summary.
- **Key Distinctions (Excellent):** 4 distinctions, all accurate and well-formulated (identity diffusion vs multiple personality, vs adolescent identity crisis, vs psychotic disturbances; cohesive self vs poorly integrated identity via the necklace metaphor).
- **Theoretical Tensions (Excellent):** 4 tensions, all accurate (object-relations vs oedipal/structural; spectrum view; principle of multiple function; degree of manifestation across personality disorders).
- **Minor formatting artifacts:** Stray double-quotes in `"false self,` and `"divided self,` (L54) — missing closing quote; `"short path"` artifacts. The word "skin mascomism" (bullet, typo for "masochism") — a model garble not caught by postchecks.

---

## Part 2 — Structured JSON Scorecard (Machine-Parsable)

```json
{
  "summary_id": "001_2_-_THE_SYNDROME_OF_IDENTITY_DIFFUSION__run20260921-003234-00d02c99_v0.20.2",
  "overall_score": 6,
  "factual_consistency_score": 9,
  "coverage_score": 8,
  "clarity_score": 5,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 3,
  "verdict": "PASS",
  "justification": "Factually flawless (0 hallucinations, all 20 sampled claims source-grounded) and coverage is strong (8 — the V0.20.2 chunking fix produced a genuine exec + a dense thorough), BUT a ~52-line chain-of-thought thinking block leaked into the Thorough Summary section (the thorough-theorist-floor gap-fill call's raw reasoning shipped unstripped), which is a V0.20.2-introduced clarity regression that drops the clarity score to 5 and the overall to 6."
}
```

> **Mechanical verdict rule:** FAIL if `factual_consistency_score < 6` OR `coverage_score < 5`. This run: factual 9 ≥ 6, coverage 8 ≥ 5 → **PASS**. But **below the V0.20 campaign bar of 9–10/10**, and **below the V0.18 baseline's clarity (8)** because of the CoT leak.
>
> **Comparison to V0.18 baseline (ch.1):**
> | Pillar | V0.18 ch.1 | V0.20.2 ch.2 | Movement |
> |---|---|---|---|
> | factual_consistency | 9 | 9 | unchanged (no hallucinations in either) |
> | coverage | 6 | **8** ↑ | the V0.20.2 chunking fix (Fix C) produced a genuine exec + dense thorough; the V0.06 cap rescue + non-skippable thorough floor are working |
> | clarity | 8 | **5** ↓ | the CoT leak in the thorough is a V0.20.2-introduced regression |
> | overall | 7 | 6 | dropped because of the CoT leak |
>
> **The V0.20.2 coverage fixes WORKED** (coverage 6→8): the exec is no longer a byte-identical copy of the thorough, and the thorough is dense with named theorists. **But V0.20.2 introduced a new clarity defect** (the CoT leak) that needs a fix in the thorough-theorist-floor's CoT handling.

---

## Diagnosis — the CoT leak's owning pipeline stage

| Defect | Owning stage | Evidence |
|---|---|---|
| **CoT thinking block leaked into Thorough Summary (lines 56-107)** | `core/summarisation/thorough_theorist_floor.py` — the thorough-theorist-floor gap-fill call's output handling (L198-225: `detect_cot_narrative` + `<thorough_addition>` tag extraction) | The leaked text is the raw reasoning output of the thorough-floor gap-fill call (the "write 1-2 paragraphs weaving in ONLY the contributors listed below" prompt at L166). The response was CoT-inundated (numbered list of "Let me identify each contributor", "Wait, this is", "Hmm, could 'Erikson in' be a misread"), wasn't wrapped in `<thorough_addition>` tags, and the tag-extraction fell through to the raw cleaned text — which included the thinking. The CoT guard (`detect_cot_narrative`) should have caught it (the markers are all present) but didn't — either the marker threshold wasn't met or the function examined a different slice. |

**Why V0.18 didn't hit this but V0.20.2 did:** the V0.18 thorough floor was SKIPPED on the 1551s > 1200s deadline overrun (the V0.18 Defect C). V0.20.1 Fix 2 made the floor NON-SKIPPABLE — so the gap-fill call now always fires. On this ch.2 run, the call produced a CoT-inundated response that the existing CoT guard didn't catch, and the raw thinking shipped. **Making the floor non-skippable exposed a CoT-leak path that was previously dormant.** This is the tradeoff the V0.20.1 Fix 2 made: coverage (the thorough got more theorists) at the risk of clarity (the gap-fill call's CoT can leak if the guard misses it).

**Smallest fix the evidence supports:** strengthen the thorough-floor's CoT guard to catch the numbered-list thinking shape (the leaked block has 17 numbered items + repeated "Let me"/"Wait"/"Hmm" markers — a pattern `detect_cot_narrative` should catch but currently doesn't). This is a **V0.20.3 fix candidate** — one audit-finding family, one conventional commit, with the V0.20.2 ch.2 audit cited as evidence.

---

## ⚠️ To complete the V0.20.2 audit, please upload the correct conversion log

The uploaded `Broken Structures Salman Akhtar.conversion.log.md` is the old V0.18 log (899 lines, `App version: 0.18`, `run_id=20260920-084745-c0874728`). It does not cover the ch.2 V0.20.2 run. Please upload the **new** conversion log from the ch.2 run (it should be at `G:\DL\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar.conversion.log.md` with a 2026-09-21 timestamp, `App version: 0.20.2`, `run_id=20260921-003234-00d02c99`). That log will show whether the truncation fixes (Fix A/B/C) fired on this run and whether the thorough-floor gap-fill call truncated — which will confirm the CoT-leak root cause.
