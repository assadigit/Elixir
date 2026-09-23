# AUDIT — Summary vs Source — version V0.4.23 (run 20260923-053014-491d1bf4) — ch.4

> **Audit version:** `V0.4.23 / run 20260923-053014-491d1bf4 / app 0.4.23 / 2026-09-23T05:30:14 / 74 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 4 "BORDERLINE PERSONALITY DISORDER" (PDF pp. 77–112, 36 pages, 12,073 words)
> **Audit framework:** the standing four-pillar expert fact-checker (`prompts/evaluation/expert_fact_checker.md`).
> **Ground truth:** `docs/ground_truth/001_4 - BORDERLINE PERSONALITY DISORDER.md` (byte-identical to this session's re-upload — md5 verified).
> **Audit instrument (new in V0.4.23):** the release's own universal enumeration detector was run against the summary as a machine coverage check — the first audit where per-list recall is **measured, not eyeballed**.

---

## Provenance cross-check & uploaded-artifact triage (2 files)

| Field | Value | Match |
|---|---|---|
| `run_id` (summary) | `20260923-053014-491d1bf4` | ✓ new run (V0.4.22 audit target was `030841-d6d47f77`) |
| `app_version` | `0.4.23` | ✓ first V0.4.23 output received |
| `bullets` | `74` | ✓ (header, footer, and count of Key-Takeaway lines all agree; +34 vs V0.4.22's 40 — the no-cap policy visibly in effect) |
| Conversion log | **not uploaded for this run** | — (log-level telemetry — enumeration-guarantee lines, filler counters, veto log — could not be cross-checked; see Backlog #3) |

Triage of the two uploaded files:

1. `001_4_-_BORDERLINE_PERSONALITY_DISORDER_summary.md` → the V0.4.23 chapter summary. **Audited below.**
2. `Broken Structures Salman Akhtar.summary.md` → **STALE ARTIFACT AGAIN (fourth occurrence of this trap).** Its stamp reads `generated-by: Elixir v0.3 | run_id=20260921-050415-c9511a74 | 2026-09-21 | bullets=39` and its content summarizes chapter 2 ("THE SYNDROME OF IDENTITY DIFFUSION"). That exact run was already audited 2026-09-21: `AUDIT_V0.3_run20260921-050415-c9511a74_ch2_summary_vs_source.md` → 9/9/9/9 PASS. It is not a V0.4.23 output — no re-audit performed. **If the intent was to audit the book-level summary THIS run wrote, re-export it from the V0.4.23 run's `summaries\` folder; its stamp must read `v0.4.23 | run_id=20260923-053014-491d1bf4`.**

---

## Part 1 — Detailed Report

### Method

Extracted ~140 discrete claims across the six summary sections (Executive Summary 14; Key Takeaways 74 bullets ≈ 90; Thorough Summary + thorough_addition ≈ 30; Key Distinctions 5; Theoretical Tensions 4 — many shared). Each was verified against the ground-truth chapter. Claims carried over unchanged from the V0.4.22 audit re-verified clean there (its 30-claim evidence table) were spot-checked, not re-derived. **Plus one machine pass:** `detect_enumerations(ground_truth)` → 21 lists, 117 items — per-item coverage measured against the final summary with the shipping heuristic (`enumeration_item_covered`).

### Machine coverage check (the repo's own detector as audit instrument)

```
DETECTED LISTS: 21        lists fully covered: 20 / 21
ENUMERATION ITEM RECALL: 113/117 (96.6%)
```

- **Fully captured (verbatim or ≥50%-word hit), the user's "seven means seven" contract honored:** the 7-item psychoanalytic Characteristics (7/7 — *the V0.4.22 omission #1, now shipped*); Gunderson–Kolb 7 distinguishing characteristics (7/7); G&S 1975 six criteria (6/6); DSM-III eight features (8/8); the nine-feature descriptive conspectus (9/9 — *never assembled in V0.4.22*); Kernberg descriptive 6/6, structural 4/4, oedipal 5/5, splitting-consequences 8/8, dependence 5/5; Modell 5/5; Klein's three problems 3/3; Volkan's three early environments 3/3 (*V0.4.22 honorable-mention miss, now shipped*); DSM-III-R (i)–(iv) 4/4; Table 4-1 six areas 6/6; comorbidity three explanations 3/3; and the 3-item referral-artifact / 4-item Grinker / 6-item and 3-item remaining runs.
- **The one partial list — Stern's ten criteria: 4/10 items captured.** The summary names narcissism, psychic bleeding, hypersensitivity, rigidity (bullet: "ten criteria, *including*…") — items (5)–(8) are absent everywhere: *(5) tendency to respond negatively to helpful and correct interpretations; (6) a deeply ingrained deficit of self-esteem and accompanying feelings of inferiority; (7) masochism and depressive mood swings; (8) organic insecurity or a constitutional incapacity to tolerate much stress.* The detector sees this list as an 8-item run (a PDF paragraph break inside item (8) splits it; items (9)–(10) fall below the 3-item minimum). **The ship-time guarantee should have forced a consolidated bullet for it — none shipped.** Without the conversion log the exact escape path can't be pinned; leading hypothesis: the guarantee's bullet contained the paragraph-break-truncated item "(8) organic insecurity or a" → the consolidated bullet itself looked truncated/garbled → a postcheck or dedup dropped it. (See Backlog #3.)

### Fact-Check Log

**Result: 139 of 140 verified clean; 1 hallucination incident; 3 minor defects; 1 residual filler.** Every date, number, proper name, quote, and criteria list sampled verifies. All four V0.4.22 hallucination incidents are confirmed FIXED (section below).

**Verified clean — the V0.4.23-new claims (gap-fill author bullets, consolidated lists, thorough_addition; all verified against source this session):**

| # | Claim in summary | Evidence in source |
|---|---|---|
| 1 | Grinker et al. (1968) studied **53 hospitalized patients** for **93 behavioral criteria** | "a study of fifty-three hospitalized patients… investigated these patients for ninety-three behavioral criteria" |
| 2 | Kraepelin bullet: morbid personalities as borderline states, instability of will / morbid liars / pseudoquerulous | verbatim (V0.4.22 audit #2) |
| 3 | Robbins: adjustment depends on "one or more obligatory relationships with persons who are quite inaccurately perceived" | "Robbins (1983) observed that the adjustment of borderline individuals depends on one or more obligatory relationships…" (no year welded — the V0.4.22 temporal compression is gone; the thorough_addition correctly places Robbins (1956) at the 1954/55 panels) |
| 4 | Abend: four analyzed patients, Kris Study Group, NY Psychoanalytic Institute | "Abend, Porder, and Willick (1983) based their findings on four analyzed 'borderline' patients… Kris Study Group" |
| 5 | Kolb: study comparing borderline, schizophrenic, neurotically depressed patients; seven distinguishing characteristics incl. low achievement, impulsivity, manipulative suicidal gestures, heightened affectivity | "…with schizophrenic and neurotically depressed patients, Gunderson and Kolb (1978) isolated seven distinguishing characteristics…" (attribution filed under Kolb alone drops Gunderson — loose, not false; Gunderson covered elsewhere) |
| 6 | Deutsch 1942: "as-if" patients "generally maintain a firm grip on reality and appear quite normal" | verbatim |
| 7 | Fairbairn: mapped the inner realm of severe character pathology; dealt more with withdrawn individuals | "This inner realm… mapped out by Klein… and Fairbairn (1944)… he seems to have been dealing with more withdrawn individuals than those generally considered borderline" |
| 8 | Erikson 1956/1959 epigenetic sequence + identity diffusion (self-sameness, continuity, affiliation) | "consists of a sustained sense of self-sameness… temporal continuity… feeling of affiliation"; "key anchoring symptom (Kernberg…)" — both verbatim |
| 9 | Balint: basic fault involves *exclusively* two-person relationships distinct from oedipal levels | "(a) all the events that happen in it belong to an exclusively twoperson relationship… (b) entirely different from… the oedipal level" (quoted pp. 16–17) |
| 10 | Kohut's self psychology a component of Adler's (1985) view; Adler: "primary inner emptiness" from absent positive introjects → "annihilatory panic" | "derived from a combination of Piaget's (1937) and Fraiberg's (1969) work on cognitive development, Mahler's… and Kohut's (1977) self psychology"; "primary inner emptiness based upon a relative absence of positive introjects"; "this 'annihilatory panic' in turn causes intense rage" |
| 11 | Mack 1975 review offering "a significantly unique synthesis of prior literature" | verbatim phrase in source |
| 12 | Gunderson and Siever (+ others): both types show perceptual/cognitive distortions incl. magical thinking, ideas of reference | "Both types of patients show perceptual and cognitive distortions, such as magical thinking, ideas of reference… (Gunderson 1984, Gunderson and Siever 1983, Rosenberger and Miller 1989)" |
| 13 | Instrument attributions: DIB (Gunderson 1982, 1984), SIDP (Pfohl et al. 1986), SIB (Baron et al. 1981), PIQ-II (Widiger et al. 1986), DIPD (Zanarini et al. 1987); reviews by Reich and Noyes (1987) and Widiger and Frances (1987) | all five verbatim in the instruments passage |
| 14 | Comorbidity three explanations: predisposes (Gunderson 1984), subaffective (Akiskal et al. 1983), independent-but-coexisting (McGlashan 1983); Barasch/Pope/Soloff: substantial proportion never develop major affective disorder, core symptoms unresponsive to antidepressants | three-explanation sentence verbatim; the studies passage follows |
| 15 | Demographics examined by Akhtar et al. (1986) and Widiger and Frances (1989) | verbatim |
| 16 | Fenichel 1945 "queer psychopaths," primitive narcissism, denial/defensive grandiosity under frustration | verbatim (the V0.4.22 H1 stitch-source now quoted to its RIGHTFUL author) |
| 17 | Frank suggested Winnicott's concepts fit borderline states better than classical approaches; developed later by Modell (1963) | "Frank suggested during the course of these discussions that borderline states might be better understood using the concepts of Winnicott… developed later by Modell (1963)" |
| 18 | Werble: 1977, Grinker and Werble added fourteen new patients, reaffirmed findings | verbatim (V0.4.22 audit #27) |
| 19 | Bouvet 1958: coercive clinging + negativistic withdrawal impede "optimal distance" | "Alternating behaviors of coercive clinging and negativistic withdrawal impede establishment of 'optimal distance' (Bouvet 1958)" |
| 20 | Piaget's cognitive-development work incorporated into Adler's view of borderline psychopathology | "derived from a combination of Piaget's (1937) and Fraiberg's (1969) work on cognitive development…" |
| 21 | Bowlby's attachment theory synthesized by Masterson (with Mahler) | "Masterson (1972, 1976) derived his ideas… by synthesizing Bowlby's (1969, 1973) attachment theory, Mahler's (1975, 1978)…" — *the exact bullet the V0.4.22 veto misfire killed; the precision fix restored it* |
| 22 | Abraham (and Jones) extended Freud's character investigation to other traits | "Abraham (1923, 1924b, 1926) and Jones (1913, 1918) became prominent in extending such investigation to other character traits" |
| 23 | Akhtar: recklessness in decision-making from underlying splitting, borderline cognition missing from DSM-III | "A certain recklessness in decision-making processes, resulting from the underlying splitting mechanisms (Akhtar and Byrne 1983), is also a characteristic of the borderline cognition missing from the DSM-III description" |
| 24 | Kernberg 1967: *stable* pathological state (not transitory), splitting central, buttressed by primitive idealization, projective identification, denial, omnipotence/devaluation | "Despite its chaotic appearance, this is a stable pathological state"; "buttressed by primitive idealization, projective identification, primitive denial, and omnipotence and devaluation" |
| 25 | All ten consolidated enumeration bullets' item lists (Characteristics 7; Knight 12; Klein 3; Modell 5 incl. the "(p. 285)/(p. 286)" quotes — which are the *book's own* cross-references, verbatim in source; Kernberg descriptive 6 / structural 4; oedipal 5; splitting-consequences 8; dependence 5; environments 3) | every item verbatim-matched in source |
| 26 | Knight (1953): severe ego weakness beneath neurotic symptoms; face-to-face interview over several sessions; impaired integration, judgment, defense | "underneath this picture lies severe ego weakness… 'integration, concept formation, judgment, realistic planning, and defending…'… only a face-to-face interview, often extending over several sessions" (3-of-5 selection from the quoted list — faithful) |
| 27 | Roster of 40 contributor names in the thorough_addition opening (Akhtar…Porder) | **every name grep-verified present in source — 0 fabricated authors** (V0.4.22 shipped one fabricated + 4 garbage tokens) |
| 28 | The thorough's DSM-omission list: psychoticlike episodes, disturbed thinking, hypomanic tendencies, centrality of splitting and identity diffusion | "noteworthy omission… psychoticlike episodes or disturbed thinking and communication"; "cognitive peculiarities, hypomanic end of mood swings… are omitted"; "does not underscore the centrality of splitting and identity diffusion" |

**V0.4.22 failure modes — regression check (all fixed):**

| V0.4.22 incident | V0.4.23 status |
|---|---|
| **H1** fabricated author "May" (month-date regex → gap-fill stitched Klein + Fenichel) | **FIXED** — no "May:" bullet; no BIOA/Tey/JOQuUI/aTQNJ anywhere; all 40 roster names real; Fenichel's claim now correctly attributed to Fenichel |
| **H2** 104-criteria figure misattributed to Knight | **FIXED** — the figure is gone; Knight's bullet and thorough entry carry only verified ego-weakness content |
| **H3** "Meissner and Rinsley both proposed a hierarchical continuum" (guard-introduced) | **FIXED** — continuum attributed to Meissner (1984) alone; Masterson & Rinsley carry the split object relations unit (correct) |
| **H4** eight estimated page refs shipped as `(p. 77)` citations | **FIXED** — all nine additive-section refs ship as `(p. ~77)` tilde format; the only bare refs `(p. 285)/(p. 286)` are verbatim book cross-references from the source itself |
| `conditionsss` ×2 | absent |
| `victimhood` coinage | absent (source's "parental victimization" now used) |
| `Elroy` (McElroy garble) | absent — "McElroy" spelled correctly (twice) |
| 7 of 40 filler bullets | 1 of 74 (Wolberg "appears in the same citation list" — see minor defects) |
| Omission #1 aggression substrate | **shipped** — Characteristics item (1), verbatim |
| Omission #2 Singer's individual contributions | **shipped** — bullet 38 + thorough ("dehumanized defenses against… dissolution" verified against the Singer passage) |
| Omission #3 Masterson–Rinsley etiological core | **shipped** — bullet 35 + thorough (pre-borderline mother, split object relations unit) |
| Exec Volkan triple-attribution | gone — exec now attributes splitting/separation-individuation to Stern/Klein/Mahler/Kernberg correctly |
| Robbins 1954/55-vs-1983 temporal compression | gone — the two Robbins facts are now correctly separated |

**Flagged — 1 hallucination incident:**

**H1 (minor — keyword-conflation misattribution).** thorough_addition: *"Piaget's cognitive development theories were referenced regarding Klein's questionable attribution of elaborate fantasy lives to young infants."*
- The source's Klein criticism cites "**current knowledge of neonatal cognitive development**" — **without naming Piaget** (Piaget appears exactly once in the chapter, in the *Adler* derivation: "a combination of Piaget's (1937) and Fraiberg's (1969) work on cognitive development"). The gap-fill welded the "cognitive development" keyword from the Klein passage onto the name from the Adler passage. Both facts exist individually; the claimed linkage does not. Same conflation class as V0.4.22's H3, but milder (no false content, only a false attribution edge).

**Minor defects (not counted as hallucinations):**

- **Fairbairn gloss:** thorough_addition says his internalization processes involve "bipolar units of ego fragments and internal objects, which he saw as always involving a two-person dynamic rather than intrapsychic conflict alone." Source: "a bipolar unit of an ego fragment and an internal object (self-and object representations, in current terminology)" — the bipolar-unit half is faithful; the "two-person dynamic *rather than intrapsychic conflict alone*" contrast clause is interpretive addition.
- **"cognitive recklessness"** (thorough) — source: "A certain recklessness in decision-making processes… characteristic of the borderline cognition." Semantically faithful lexical blend (the `victimhood` class: coinage, not invention).
- **Wolberg filler** — "His 1973 work appears in the same citation list as studies by Rinsley, Searles, Stone, and others." True but content-free citation adjacency; the filler floor's verb list caught "is cited/is listed/is recognized" but not "appears in the same citation list."
- **Kolb bullet** drops Gunderson from the jointly-isolated seven characteristics (loose attribution; Gunderson covered elsewhere).

### Missing Information

1. **Stern's ten criteria, items (5)–(8)** — the only enumeration-list escape (4/10 captured; details in the machine-check section). This is the single remaining instance of the exact failure mode the user's "if they are seven, seven must be captured" directive targets.
2. *(Minor)* The theorist roster names ~40 contributors in the thorough_addition opening, but ~a dozen of them (Chatham, Kroll, Hartocollis, Wolman, Thomson, Rangell, Jones…) never get content anywhere — name-only coverage. Honest (the recall floor now measures theorists by name), but a name is not a takeaway.
3. *(Minor)* Balint's overcathexis (ocnophilia/philobatism) and the "highly vehement and loud symptoms" on separation dropped from his bullet.

### Quality Notes

- **Executive Summary (Good).** Two clean paragraphs, distinct from the thorough, correct five-dimension "borderline is apt" framing, no attribution smears. The master-summary architecture holds.
- **Key Takeaways (Mixed — the no-cap trade-off made visible).** 74 bullets: ~46 solid content bullets (historical run, psychoanalytic run, DSM critique, differential — well-sequenced); 28 author-coverage gap-fill bullets, mostly genuine content this time (the V0.20.5 failure mode is largely cured); 10 machine-generated consolidated enumeration bullets carrying 58 verbatim items — **full-coverage gold, but 8 of 10 have garbled labels** (next item).
- **The garbled-stem defect (new, clarity-regressing).** The consolidated bullets' labels are mid-word-sliced source fragments: "**Rom others. unstable identity also found**" (source: "…f**rom** the others. An unstable identity was also found…"), "**Tive, structural, and genetic-dynamic. descriptive features,**" ("…descrip**tive, structural**…"), "**Character disorders, including 'infantile,' narcissistic, -if,**" ("…as**-if**…" cut mid-token), "**Ree types of early environment associated**" ("…th**ree** types…"), "**Of thinking to developed later by**," "**Of preoedipally distorted oedipal conflicts in**." Root cause: the run-in stem extraction takes a raw ~150-character window ending at the list start — character-sliced, not sentence- or word-aligned — and `stem_label` then capitalizes whatever fragment results. The *items* are pristine; the *labels* read like corruption.
- **Thorough Summary (Good body, defective tail).** The main thorough paragraph is a faithful, well-ordered 900-word synthesis — every list in it complete. But the additive `<thorough_addition>` ships **(a) its literal opening tag visible in the output, (b) no closing tag, and (c) a mid-sentence truncation** ("…parental victimization via incest or cruelty,‖"). Root cause found in code: the gap-fill call caps at `max_tokens=1024` (tuned for a 150–300-word ask); the 27B model ran long, the cut ate `</thorough_addition>`, the tag-regex then failed, and the fallback shipped the raw response *including* the opening tag and truncated tail — this path has none of the truncation guards the Key-Distinctions/Theoretical-Tensions additive path got in V18.20.3.2.
- **Key Distinctions / Theoretical Tensions (Good).** 9 items, all genuine source-grounded syntheses, all page refs honestly tilde-marked.
- **0 CoT leaks, 0 stray quotes, exec ≠ thorough, 0 name garbles, 0 fabricated authors.**

---

## Part 2 — Structured JSON Scorecard

```json
{
  "summary_id": "001_4_-_BORDERLINE_PERSONALITY_DISORDER__run20260923-053014-491d1bf4_v0.4.23",
  "overall_score": 8,
  "factual_consistency_score": 9,
  "coverage_score": 9,
  "clarity_score": 6,
  "hallucinations_detected": 1,
  "critical_omissions_detected": 1,
  "verdict": "PASS",
  "justification": "PASS, +1 over V0.4.22, and the audit backlog verifiably delivered: all four V0.4.22 hallucination incidents are fixed (no fabricated authors — all 40 roster names grep-verified; page refs honestly tilde-marked; Meissner/Knight/Fenichel attributions corrected), all three critical omissions recovered (aggression substrate, Singer, Masterson-Rinsley), machine-measured enumeration recall is 113/117 items across 21 lists (96.6%), and filler fell from 7/40 to 1/74. It stops at 8, not 9-10, because the new machinery shipped three visible defects: 8 of 10 consolidated enumeration bullets carry mid-word-sliced garbled labels ('Rom others. unstable identity also found'), the thorough_addition ships an unclosed visible tag and ends mid-sentence (1024-token cap ate the closing tag; the fallback path has no truncation guard), Stern's ten-criteria list escaped the ship-time guarantee (4/10 items), plus one minor keyword-conflation misattribution (Piaget welded to the Klein criticism he doesn't appear in) and a 40-name laundry-list paragraph. Every one of these is a mechanically fixable code bug — none is model whimsy."
}
```

> **Mechanical verdict:** factual 9 ≥ 6, coverage 9 ≥ 5 → **PASS** — still below the 9–10 campaign bar, but the blocker moved from *pipeline honesty* (V0.4.22) to *deterministic polish* (V0.4.23) — a much easier class of bug.

---

## Comparison to ALL previous versions

| Version | overall | factual | coverage | clarity | Key change |
|---|---|---|---|---|---|
| V0.3 ch.2 | 9 | 9 | 9 | 9 | 🚀 master-summary architecture |
| V0.3 ch.3 | 8 | 8 | 9 | 8 | name garble |
| V0.4 ch.3 | 9 | 9 | 9 | 9 | garble repair + master default |
| V0.4.22 ch.4 | 7 | 8 | 7 | 7 | filler gap-fill + fake-author pollution + estimated page refs |
| **V0.4.23 ch.4** | **8** | **9** | **9** | **6** | no-limits + enumeration capture: coverage/factual recovered; new deterministic-polish bugs (garbled stems, truncated addition, one guarantee escape) |

**What held:** the 3-call master-summary architecture; the additive sections (now with honest page refs); the author-garbage filter (zero fabricated names); the filler floor (7→1); the no-cap policy (74 bullets, nothing displaced — the Characteristics bullet that V0.4.22's 40-cap silently deleted now ships).

**What regressed:** clarity, specifically — the stem slicer, the thorough_addition truncation path, and the name-dump paragraph are all *new code* shipping first-draft labels and unguarded tails.

---

## Backlog for V0.4.24 (priority order)

1. **Run-in stem extraction must be sentence/word-aligned** (`core/summarisation/enumeration.py` — the stem window slicing and `stem_label`): search backwards from the list start to the nearest sentence boundary or line start; never slice mid-token ("f|rom", "th|ree", "as|-if"). Then `stem_label` should lead with the stem's *final* sentence's opening words, capped at a readable phrase. Kills the 8 garbled labels — the single biggest clarity win.
2. **Thorough_addition truncation guard** (`core/summarisation/thorough_theorist_floor.py`): when `</thorough_addition>` is absent, (a) strip the opening-tag line, (b) run `strip_truncated_section_tail`/`is_truncated` exactly like the KD/TT additive path (V18.20.3.2), (c) keep the clean prefix or retry; and revisit the 1024-token cap — under the no-limits policy it is the odd hardcoded limit (scale it with the thorough target, or at least check the finish reason).
3. **Guarantee-escape regression test** (Stern list): a test with the exact ch.4 Stern passage (paragraph break inside item (8)); the detector should join items across intra-list blank lines, and no postcheck may drop an enumeration-guarantee bullet without a log line. **Also: request the V0.4.23 conversion log from the owner** — its "enumeration guarantee — added N consolidated bullet(s)" lines and postcheck verdicts would pin the escape path exactly.
4. **Name-dump paragraph**: the theorist-floor thorough gap-fill should weave names into content sentences; a paragraph whose opening sentence is a 40-name list is citation adjacency in prose form.
5. **Filler floor verb list**: add "appears in the same citation list" (the Wolberg bullet).
6. **Attribution-edge check on gap-fill prose**: verify a name appears near the claim's key phrase in source before shipping "X's theories were referenced regarding Y" (would have caught the Piaget-Klein weld).
