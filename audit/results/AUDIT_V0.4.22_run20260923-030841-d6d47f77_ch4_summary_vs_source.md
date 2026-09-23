# AUDIT — Summary vs Source — version V0.4.22 (run 20260923-030841-d6d47f77) — ch.4

> **Audit version:** `V0.4.22 / run 20260923-030841-d6d47f77 / app 0.4.22 / 2026-09-23T03:08:41 / 40 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 4 "BORDERLINE PERSONALITY DISORDER" (PDF pp. 77–112, 36 pages, 12,073 words)
> **Audit framework:** the standing four-pillar expert fact-checker (`prompts/evaluation/expert_fact_checker.md`).
> **Ground truth:** `docs/ground_truth/001_4 - BORDERLINE PERSONALITY DISORDER.md` — **saved to the repo this session**. Per the owner's instruction, future audits of ch.4 summaries run against this file directly; only the summary will be sent.

---

## Provenance cross-check & uploaded-artifact triage (5 files)

| Field | Value | Match |
|---|---|---|
| `run_id` (summary) | `20260923-030841-d6d47f77` | ✓ new |
| `app_version` | `0.4.22` | ✓ |
| `bullets` | `40` | ✓ (log: `ELIXIR_PROGRESS … "bullets":40`) |
| Conversion log | `v0.4.22 \| run_id=20260923-030537-92b3c349`, Windows/Py3.12.9, llama.cpp, Ternary-Bonsai-2-27B-Instruct-Vision, t=0.7, workers=1, RTX 3060 12 GB | ✓ same run (log line 957 pins the summary file to `run_id=20260923-030841-d6d47f77`, bullets=40) |

Triage of the five uploaded files:

1. `001_4 - BORDERLINE PERSONALITY DISORDER.md` → the source chapter. **Saved as the second standing ground truth** (`docs/ground_truth/`, alongside ch.1).
2. `001_4_-_BORDERLINE_PERSONALITY_DISORDER_summary.md` → the V0.4.22 chapter summary. **Audited below.**
3. `001_4 - BORDERLINE PERSONALITY DISORDER_analysis.md` → deterministic analysis of the same run; used below as a coverage cross-check (and as evidence for the fake-author root cause).
4. `Broken Structures Salman Akhtar.conversion.log.md` → the V0.4.22 conversion log. **Log-audit section below.**
5. `Broken Structures Salman Akhtar.summary.md` → **NOT a V0.4.22 artifact.** Its stamp reads `generated-by: Elixir v0.3 | run_id=20260921-050415-c9511a74 | 2026-09-21 | Provider: ollama | Chapters: 1` and its content summarizes chapter **2** ("THE SYNDROME OF IDENTITY DIFFUSION"), not chapter 4. This exact file was already audited on 2026-09-21: `AUDIT_V0.3_run20260921-050415-c9511a74_ch2_summary_vs_source.md` → **9/9/9/9 PASS**. No re-audit performed (no new information in it). If the intent was to audit the book summary that THIS run wrote, that file needs to be re-uploaded from `G:\4.22\Broken Structures Salman Akhtar\summaries\` (the v0.4.22 run wrote it at 03:22:41 — the uploaded copy is the stale Sept-21 file the run left in place).

---

## Part 1 — Detailed Report

### Fact-Check Log

**Method.** Extracted **102 discrete claims** across the five summary sections (Executive Summary 12; Key Takeaways 40 bullets ≈ 58; Thorough Summary 28; Key Distinctions 4; Theoretical Tensions 4 — many shared between exec/thorough and bullets). Each was verified against the ground-truth chapter.

**Result: 92 verified clean, 6 flagged as hallucination incidents/garbles, 4 minor defects.** All dates, numbers, criteria lists, proper names, and quotes sampled from the summary verify — the core narrative is faithful. The flagged items below are localized, and four of them trace to identifiable pipeline mechanisms (not model whimsy).

**Verified clean — representative high-stakes claims (selection of 30):**

| # | Claim in summary | Evidence in source (quote) |
|---|---|---|
| 1 | Prichard's 1835 "moral insanity" as origin | "In 1835, Prichard expanded the horizons… Prichard called this disorder 'moral insanity'" |
| 2 | Kraepelin (1905) "morbid personalities" as "borderline states"; instability of will / morbid liars / pseudoquerulous | "Kraepelin (1905) revived interest… 'borderline states' between insanity and day-to-day eccentricities… (1) those with an instability of will, (2) morbid liars and swindlers, and (3) pseudoquerulous individuals" |
| 3 | Bleuler's nonpsychotic forms; Kretschmer's temperaments | "Bleuler… described two nonpsychotic forms… simple and latent schizophrenias"; "Kretschmer's (1925) detailed descriptions of the 'cycloid' and 'schizoid' temperaments" |
| 4 | Zilboorg "ambulatory schizophrenia"; Hoch & Polatin "pseudoneurotic schizophrenia" | verbatim in source |
| 5 | Grinker et al. (1968): 4 fundamental characteristics (chronic anger, defective interpersonal relationships, identity disturbance, depression based on loneliness) + 4 subcategories (psychotic border, core borderline, as-if, near-neurotic) | "four fundamental characteristics of what they termed the 'borderline syndrome'… Cluster analysis of their data yielded four subcategories" |
| 6 | Gunderson & Singer (1975) six criteria — all six items match | "six criteria… (1) intense affect… (2) impulsive behavior… (3) social adaptiveness, which masks a disturbed identity… (4) brief psychotic experiences… (5) bizarre and primitive responses to projective psychological tests; and (6) disturbed interpersonal relationships" |
| 7 | Perry & Klerman (1978) challenged consensus; Liebowitz (1979) questioned independent status | "Perry and Klerman (1978) conducted a comparative analysis of four sets of diagnostic criteria"; "Liebowitz felt that the 'available data do not weigh conclusively for or against borderline's status as an independent entity'" |
| 8 | Spitzer et al.: 88% discriminatory accuracy, APA-member survey | "sent the list to 4,000 members of the American Psychiatric Association… The 808 members who responded indicated… 88 percent of the time" |
| 9 | DSM-III (1980) listed eight criteria; omitted psychotic-like episodes and cognitive peculiarities | "It listed eight criteria"; "the 'noteworthy omission' (Leichtman 1989, p. 239) of items related to psychoticlike episodes or disturbed thinking and communication… cognitive peculiarities… are omitted" |
| 10 | DSM-III-R changed "intolerance of being alone" → "frantic efforts to avoid real or imagined abandonment" | "In a largely semantic move, the criterion of 'intolerance of being alone' was changed to 'frantic efforts to avoid real or imagined abandonment'" |
| 11 | Reich (1925) early description of "borderline cases," ambivalence + primitive narcissism | "Wilhelm Reich. In a 1925 paper… intense ambivalence… primitive narcissism… they constituted 'borderline cases' between psychosis and health" |
| 12 | Stern (1938) formalized "borderline," ten criteria incl. narcissism, hypersensitivity, projective mechanisms | "The term borderline was subsequently given a formal status by Stern (1938)… His list of ten criteria… (1) narcissism… (3) inordinate hypersensitivity… (9) preponderance of projective mechanisms" |
| 13 | Kernberg (1967): descriptive/structural/genetic-dynamic criteria; identity diffusion, primitive defenses, intact reality testing | "Kernberg proposed its diagnosis to be based on three sets of criteria: descriptive, structural, and genetic-dynamic"; "tightened the criteria… into identity diffusion, primitive defenses, and intact reality testing" |
| 14 | Schmideberg 1947 "stable in their instability," chaotic lives, poor therapy motivation | "In 1947, Schmideberg described… 'stable in their instability'… led chaotic lives… poor motivation" |
| 15 | Modell (1963): transitional relatedness, magical omnipotence, divided self-image, chronic struggle with distance | all four in source's Modell passage |
| 16 | Abend/Porder/Willick: four analyzed patients, Kris Study Group, NY Psychoanalytic Institute | "Abend, Porder, and Willick (1983) based their findings on four analyzed 'borderline' patients… Kris Study Group of the New York Psychoanalytic Institute" |
| 17 | Adler: failure of evocative memory in object relations | "not having achieved a solid evocative memory in the realm of object relations" |
| 18 | Erikson (1956, 1959) epigenetic sequence + identity diffusion | verbatim |
| 19 | Jacobson: psychostructural correlates of early introjections; pathological internalized object relations | verbatim |
| 20 | Mahler: rapprochement vulnerability, maternal unavailability, failure of object constancy / optimal distance | "narcissism to be most vulnerable during the rapprochement subphase"; "lack of optimal emotional availability on the part of the mother"; "Object constancy is not achieved" |
| 21 | Balint (1968) "basic fault": two-person level, overcathexis, intense symptoms on separation | verbatim |
| 22 | Kolb & Gunderson (1978): seven distinguishing characteristics incl. low achievement, impulsivity, manipulative suicidal gestures, heightened affectivity | "Gunderson and Kolb (1978) isolated seven distinguishing characteristics…: (1) low school and work achievement; (2) impulsivity…; (3) manipulative suicidal gestures; (4) heightened affectivity…" |
| 23 | Sheehy: triad (impulsivity, intense affects, interpersonal difficulties) | "Sheehy and colleagues found that impulsivity, intense affects, and interpersonal difficulties constituted the triad" |
| 24 | Widiger co-developed PIQ-II (1986) | "Personality Interview Question-II (PIQ-II; Widiger et al. 1986)" |
| 25 | Stone: favorable vs poor outcome factors (both lists match) | "self-discipline, talent, likableness, attractiveness, and high IQ contribute to a favorable outcome, while substance abuse, aggressivity, parental victimization… and antisocial tendencies… poor outcome" |
| 26 | McGlashan: affective disorders independent, often coexist | "(3) affective disorders are independent conditions that often coexist with severe personality disorders (McGlashan 1983)" |
| 27 | Werble (with Grinker) added fourteen new patients, 1977 | "In 1977, Grinker and Werble added fourteen new borderline patients… and reaffirmed their findings" |
| 28 | Kendler: genetic linkage to schizophrenia, more evident in schizotypal; Torgersen: schizotypal socially isolated, lacks heightened emotionality | "The main areas of their distinction are genetic linkage to schizophrenia, more evident in the schizotypal patients (Kendler et al. 1981, Torgersen 1985)"; "The schizotypal patient is socially isolated and lacks the heightened emotionality… (Gunderson and Siever 1983, Kendler 1984, Torgersen 1984)" |
| 29 | Akhtar & Byrne: incapacity for ambivalence, moral/ethnic relativism, body-image disturbances, hypomanic exhilaration | "Incapacity for ambivalence, inordinate moral and ethnic relativism, subtle body-image disturbances, and a tendency toward hypomanic exhilaration… (Akhtar 1984, Akhtar and Byrne 1983)" |
| 30 | Six-area composite profile; overt vs covert features; differential vs narcissistic/histrionic/antisocial/schizotypal; BPD-vs-BPO two-level distinction; all **five** "borderline is apt" ways; "poorly defined, idiosyncratically employed catchall term" quote | all verbatim-matched: six areas "(1) self-concept; (2) interpersonal relations; (3) social adaptation; (4) ethics, standards, and ideals; (5) love and sexuality; and (6) cognitive style"; overt "view themselves as victims… chronically enraged… impulsive"; covert "feel inherently defective, are frequently suicidal… vulnerable to magical thinking"; "borderline in five different ways" (all five match); "'poorly defined, idiosyncratically employed catchall term for difficult patients' (Gunderson 1989, p. 123)" |

**Flagged — 4 hallucination incidents:**

**H1 (severe — fabricated author).** Bullet: *"May: The text notes that her postulated move from the paranoid to the depressive position may have resonance with other theoretical models, and describes patients as often feeling empty and enraged while appearing relatively normal under conditions of security."*
- **No author "May" exists in the source.** The word "May" appears exactly once — as a panel **date**: "two all-day panel discussions in **May 1954** and December 1955." The deterministic analysis regex parsed the month names as cited authors ("May (11 mentions): 1954", "December (1 mentions): 1955"), the V18.14.1 gap-fill then hunted "May" as a missing theorist (log 03:20:38, round 1 list), and the model satisfied the quota by stitching two claims from *other* authors:
  - "her postulated move from the paranoid to the depressive position" = **Klein**: "Even **her** postulated move from the paranoid to the depressive position may have resonance with other theoretical models (Kernberg 1975a, Mahler et al. 1975)";
  - "patients… feeling empty and enraged while appearing relatively normal under conditions of security" = **Fenichel**: "They often feel empty and enraged but may appear relatively normal as long as certain conditions of security are fulfilled."
- Root cause: month-date regex artifacts (+ mirrored-table tokens BIOA/Tey/JOQuUI) feeding the author-coverage machinery. Exactly the failure mode the framework's calibration note warns about ("fabricates an author not in the source").

**H2 (moderate — misattributed figure).** Bullet: *"Knight: He contributed to clarifying the nosological status of borderline patients and is noted for identifying 104 diagnostic criteria associated with the psychosocial functioning of the borderline patient."*
- The 104 figure belongs to **Perry and Klerman (1978)**: "Perry and Klerman (1978) conducted a comparative analysis of four sets of diagnostic criteria (Grinker et al. 1968, Gunderson and Singer 1975, Kernberg 1967, Knight 1953) and found that a total of **104 diagnostic criteria** had been mentioned…" Knight 1953 is merely one of the four sets analyzed. (Knight's own verified contribution — ego-function impairment incl. "integration, concept formation," "schizophrenic tendencies" — survives in the bullet's first half.)

**H3 (moderate — guard-introduced misattribution).** Bullet + thorough: *"Meissner and Rinsley both proposed a hierarchical continuum of borderline conditionsss."*
- The source attributes the hierarchical continuum to **Meissner alone**: "Meissner (1978a,b, 1982, 1984) attempted to arrange various 'borderline conditions' on a hierarchical continuum." Rinsley's actual contribution is the "split object relations unit." Ironically, this half-fabrication was **introduced by the V18.20.3.2 anti-false-precision guard itself** (log 03:20:38: "rewrote 'Meissner proposed a hierarchical continuum…' → 'Meissner and Rinsley both proposed…' (source groups Meissner + Rinsley)") — the "grouping" it detected is paragraph adjacency, not a source statement. Also carries the `conditionsss` garble (see Minor defects).

**H4 (moderate — fabricated citation precision).** Key Distinctions & Theoretical Tensions ship eight bullets with page refs "(p. 77)", "(p. 85)", "(p. 94)", "(p. 103)".
- The log admits these are **estimates**: "page_ref_injector/fix: … added (p. X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; **pages estimated from start_page=77, end_page=112**)." The four values are linearly spaced guesses. At least one is demonstrably wrong: the BPD-vs-BPO distinction is stated in the COMMENT section (source lines 911–924 of 936 ≈ p. 111–112, **not** p. 77). Eight shipped bullets carry citations that look authoritative but are machine-estimated.

**Minor defects (not counted as hallucinations):**

- **`conditionsss`** — fragment-merge garble; not in the source; shipped **twice** (bullet + thorough). The post-check flagged it (fragment_merge) but did not repair it.
- **`victimhood`** — morphological coinage; source says "view themselves as victims." Semantically faithful, lexically invented (post-check's sentence_fusion flag is a false alarm in spirit, true in letter).
- **Exec triple-attribution**: "Additional contributors such as Masterson, Meissner, and Volkan synthesized attachment theory and hierarchical continuums" — distributes two achievements across three names; Volkan did neither (his contributions: introjective-projective relatedness, emotional flooding).
- **Robbins bullet temporal compression**: "…following official recognition of the issue by the American Psychoanalytic Association" welds Robbins's **1983** observation to the **1954/55** panels (cited to Robbins 1956) into a misleading sequence. Both facts verify individually.

### Missing Information (top 3)

1. **The psychoanalytic summary's first shared characteristic — "a substrate of excessive aggression originating from constitutional factors and from severe, sustained preoedipal trauma."** Nowhere in the summary. This is the tool's own recall-floor miss (log 03:22:41: "conclusion items 6/7 (missing: ['a substrate of excessive aggression originating fr'])"). The consolidated Characteristics bullet that carried all 7 items (V18.15.9.1) was generated verbatim from source — then displaced by the 40-bullet hard cap.
2. **Singer's individual contributions** (3rd most-cited author, 17 mentions, a full source passage): the fear that the inner world becomes "devoid of objects… devoid of themselves," the emptiness experience distinguished from loneliness and depersonalization, dehumanization as a defensive maneuver. The summary covers Singer only as half of "Gunderson and Singer."
3. **The Masterson–Rinsley etiological core**: Masterson's pre-borderline mother ("withdrew her love when the child displayed strivings toward independence" → the abandonment dilemma) and Rinsley's "split object relations unit" (withdrawing/rewarding units + eight consequences). The summary reduces Masterson to "synthesizing attachment theory with separation-individuation processes" and Rinsley to the garbled continuum bullet.

*(Honorable mentions: the nine-feature descriptive conspectus is never assembled as such; the DSM-III division of the old heterogeneous borderline group into schizotypal + "unstable" is absent; Volkan's actual content — emotional flooding, the three early environments — is absent because his bullet is pure filler.)*

### Quality Notes

- **Executive Summary (Good).** 225 words, two paragraphs, distinct from the thorough — the master-summary architecture held. One loose triple-attribution (Volkan).
- **Key Takeaways (Mixed — the weakest section).** 40 bullets, but **7 of 40 are meta-filler** that assert citation adjacency instead of content: *"Volkan: He is recognized for his important contributions to the field, with specific citations provided for his works in 1976, 1980b, 1981, and 1987"* (says nothing), *"Hartocollis is cited in a list of sources alongside other investigators,"* *"Chatham is listed among specific authors… within the chapter's references,"* *"Mack: Cited as one of the primary sources…"* The May/Mahler/Volkan/Knight run (4 consecutive bullets) uses a "Name: The text notes…" label voice that breaks the declarative style of the other 36. This is the V0.20.5-era "author coverage at the cost of substance" failure mode returning **through gap-fill** — the deadline-skipped bullet consolidation would have merged these.
- **Thorough Summary (Good).** Five paragraphs, chronological → thematic, 788 words (the log shows 3 expansion attempts, best 788 < 800 threshold, kept best-effort). Carries the `conditionsss` garble and repeats the Meissner+Rinsley misattribution.
- **Key Distinctions / Theoretical Tensions (Good content, poisoned citations).** All 8 items are genuinely useful, source-grounded syntheses (the Kernberg-vs-Abend formulation and the checklist-vs-profile tensions are excellent) — but every one carries an estimated page ref (H4).
- **0 CoT leaks, 0 stray quotes, exec ≠ thorough, 0 name garbles that shipped** (the one true garble, McElroy→"Elroy", was displaced by the cap before shipping).

---

## Conversion-log audit (uploaded log, run 20260923-030537-92b3c349)

Pipeline observations, cross-checked against the shipped summary:

1. **VRAM overbudget**: peak 12.9 GB model on a 12.0 GB RTX 3060 — the run proceeded anyway. No corruption observed, but this is a stability risk worth heeding (smaller summarization model or workers=1 confirmed).
2. **Deadline cascade**: 480 s budget exceeded at 717 s → scholar reflection, semantic dedup, bullet consolidation **skipped**; 795 s → thorough theorist floor gap-fill forced (non-skippable); chapter total 840 s. The skipped phases are visible in the output (filler bullets that consolidation would have merged; only the post-gap-fill dedup ran).
3. **The judge's 100 % coverage is auto-passed on suspicion of false positive** (log 03:20:38: "likely a false positive for this source length. Auto-passing to preserve content"). The honest number is the deterministic recall floor: **theorists 68/86 (79 %), conclusion items 6/7 (86 %)** — the log itself says so, and the diagnostic summary reports the floor, not the judge number. Good honesty design; the 100 % claim should not be quoted as coverage.
4. **Post-check scoreboard: 14 flagged / 5 auto-fixed.** Audit verdicts on the notable flags:
   - `'Prichard' (1835) not found in source's 77 citations — possible name corruption` → **false positive** (Prichard is in the source text, quoted via Mack 1975; the citation regex misses text-quoted names).
   - `'DSM-III' (cited with 1980) not found… possible name corruption` → **false positive** (DSM-III is not an author — needs a stop-list).
   - Two `false 'missing' claim` flags on "omitted psychotic-like episodes…" → **false positives** (the source itself asserts the omission — "the 'noteworthy omission' (Leichtman 1989, p. 239)…"; the heuristic "concept words present in source → can't be missing" misfires on statements-about-omissions).
   - `conditionsss` fragment-merge → **true garble, shipped unrepaired** (twice).
   - `victimhood` sentence-fusion → **coinage, semantically faithful**, shipped.
   - `'Blashfield'/'Elroy'` → **true name corruption** (source: Blashfield **and McElroy** 1987) — but that bullet was displaced by the 40-bullet cap, so it never shipped. Contained by luck, not by design.
   - `quote_verification` on key_distinctions → **good catch** (a non-verbatim "quote" was downgraded to paraphrase before shipping).
   - `page_ref_injector` → **the H4 fabrication source** (shipped).
5. **Gap-fill author hunting polluted by analysis artifacts.** Month names (May, December) and mirrored-table tokens (BIOA, Tey, JOQuUI) were treated as missing "theorists"; "May" got a bullet (H1). Meanwhile **real** authors Bowlby, Fraiberg, Kroll, Frances never made the final set — and Bowlby's *correct* bullet ("Bowlby provided the attachment theory (1969, 1973) that Masterson…") was **killed by an active-subject veto misfire** (log 03:21:52: "source attributes this claim to 'Mahler's', not 'Bowlby'" — the veto matched the wrong source sentence; the source does attribute attachment theory to Bowlby in the Masterson passage). The same veto family misfired on a TRUE Grinker bullet ("four subcategories" — the source attributes these to Grinker et al.'s cluster analysis; the information survived only via the thorough).
6. **Ground-truth file caveat for future audits**: TABLE 4-1 in the ground-truth chapter is OCR-mirrored garbage (source lines 785–860). Do not treat its tokens as text; it is the origin of the BIOA/Tey/JOQuUI artifacts.

---

## Part 2 — Structured JSON Scorecard

```json
{
  "summary_id": "001_4_-_BORDERLINE_PERSONALITY_DISORDER__run20260923-030841-d6d47f77_v0.4.22",
  "overall_score": 7,
  "factual_consistency_score": 8,
  "coverage_score": 7,
  "clarity_score": 7,
  "hallucinations_detected": 4,
  "critical_omissions_detected": 3,
  "verdict": "PASS",
  "justification": "PASS with caveats: the chapter's architecture (historical → psychoanalytic → DSM critique → synthesis → differential → comment) is accurately and readably represented — every date, criteria list, and quote sampled verifies against the source — but 4 hallucination incidents (a fabricated 'May' author stitched from Klein's and Fenichel's claims by gap-fill, the 104-criteria figure misattributed to Knight instead of Perry & Klerman, the guard-introduced 'Meissner and Rinsley' continuum, and 8 bullets carrying machine-estimated page refs presented as citations), 3 critical omissions (the aggression substrate, Singer's emptiness contributions, the Masterson–Rinsley etiological core), and 7 content-free filler bullets leave it at 7 — a regression from the V0.4 ch.3 bar of 9, driven by deadline-skipped consolidation, a VRAM-overbudget 27B model, and regex artifacts (month names, mirrored-table tokens) polluting the author-coverage machinery."
}
```

> **Mechanical verdict:** factual 8 ≥ 6, coverage 7 ≥ 5 → **PASS** — but **below the 9–10 campaign bar** for the first time since V0.3.

---

## Comparison to ALL previous versions

| Version | overall | factual | coverage | clarity | Key change |
|---|---|---|---|---|---|
| V0.18 ch.1 | 7 | 9 | 6 | 8 | (baseline) |
| V0.20.2 ch.2 | 6 | 9 | 8 | **5** | CoT leak dropped clarity |
| V0.20.3 ch.2 | 8 | 9 | 8 | 8 | CoT leak fixed |
| V0.20.4 ch.2 | 8 | 9 | 8 | 8 | stable |
| V0.20.5 ch.2 | **4** | 8 | 6 | **3** | D3 backfired (numbered outline regression) |
| V0.3 ch.2 | **9** | 9 | 9 | 9 | 🚀 master-summary architecture |
| V0.3 ch.3 | 8 | 8 | 9 | 8 | 'Ayyedura jo' name garble |
| V0.4 ch.3 | **9** | 9 | 9 | 9 | garble repair + master default |
| **V0.4.22 ch.4** | **7** | **8** | **7** | **7** | first 27B / 12 GB-VRAM run; filler gap-fill + fake-author pollution |

**What held vs the V0.4 ch.3 bar:** the 3-call master-summary architecture (exec ≠ thorough, no CoT, no stray quotes), the additive Distinctions/Tensions sections, the anti-false-precision intent, the honest recall floor.

**What regressed:** (a) gap-fill bullets written to satisfy a *polluted* author list (fake May/December/BIOA/Tey/JOQuUI entries) instead of source content; (b) deadline-skipped consolidation left 7 filler bullets standing; (c) the anti-false-precision guard and the active-subject veto each misfired once and *created* errors; (d) page-ref injection shipped estimates as citations.

**Backlog (priority order) — candidate V0.4.23 code fixes:**

1. **Analysis-regex garbage filter**: drop month names, non-Latin-script tokens, and garbled-table strings before the author list feeds gap-fill (kills H1 at the root; also stops wasting 2 of 5 gap-fill rounds on BIOA/Tey/JOQuUI).
2. **page_ref_injector honesty**: never ship estimated pages as `(p. X)` — use `(p. ~X)` or omit.
3. **Active-subject veto precision**: require the matched source sentence to actually contain the competing attribution (fixes the Bowlby and Grinker misfires — both killed TRUE bullets).
4. **Filler-bullet floor**: reject gap-fill bullets whose main verb is "is cited / is listed / is recognized / The text notes" (7 of 40 shipped bullets).
5. **Statements-about-omissions exception** in the "false missing claim" heuristic (the source's own omission claims are not summary errors).
6. **Cap-exempt the consolidated Characteristics bullet** (sole cover of the psychoanalytic-summary conclusion items — its displacement is omission #1).
