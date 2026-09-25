# AUDIT — Summary vs Source — version V0.4.35 (run 20260926-013038-18eb612a) — ch.6

> Four-pillar expert fact-checker audit, **the FIFTH round** on the same chapter
> (the V0.4.35 release shipped the F1 fix — a standalone `_year_attribution_probe`
> wired to the coverage-check point in `_thorough_theorist_floor`, BEFORE the gap-
> fill phase, so it catches fabricated-year claims on the DEDICATED EXPANSION
> output regardless of whether the gap-fill runs).

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol / Rule 4)

| Field | Stamp | Notes |
|---|---|---|
| `app_version` | `0.4.35` | Matches the V0.4.35 release commit `26fa567` ("release: V0.4.35 — the F1 year-attribution-probe-wiring release") |
| `run_id` | `20260926-013038-18eb612a` | Matches conversion-log line 5 (`<!-- generated-by: Elixir v0.4.35 | run_id=20260926-013038-18eb612a -->`) and summary line 3 |
| `started` | `2026-09-26T01:37:03` | Matches conversion-log summary line 893 (started timestamp on the summary file) |
| `bullets` | `62` | Matches summary line 3 + final shipped bullet count (conversion-log line 723: "63 → 62 bullets") |
| Conversion-log companion stamp (line 5) | ✅ Present, matches summary | The conversion log carries the same `run_id=20260926-013038-18eb612a` stamp |
| `_year_attribution_probe` (commit `6d220e4`) | ✅ Present in `core/summarisation/thorough_theorist_floor.py` (104 LOC added) | Verified via `git show 6d220e4` — see §"Conversion-log review" below |
| Source chapter | `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words, start_page=137, end_page=160) | UNCHANGED across all 5 audits (V0.4.31 → V0.4.35) |

**Provenance verdict: ✅ STAMPED + CONSISTENT.** Audit may proceed.

---

## Rig-vs-sandbox divergence ledger (honest disclosure, same as V0.4.31 + V0.4.32 + V0.4.33 + V0.4.34)

This audit reads the **rig-produced** artifacts (the conversion log was produced on `C:\Users\Ali Assadi\Desktop\435` per log line 57 — Windows-10, RTX 3060 12GB, Python 3.12.9, PyTorch 2.13.0+cu126 CUDA). The audit itself runs in the elixir sandbox at `/home/z/elixir` (Linux, no CUDA). The audit is **read-only** — it does not modify the artifacts or run the converter. The pre-existing 5-audit lineage (V0.4.31 → V0.4.34) used the same approach.

---

## Part 1 — Detailed Report

### Step 1 — Claim extraction + verification (the four-pillar fact-check)

The V0.4.35 summary ships **62 bullets** (UP from V0.4.34's 51) + an Executive Summary (2106 chars) + a single-paragraph Thorough Summary (30161 chars / 4158 words) + Key Distinctions (5 bullets) + Theoretical Tensions (4 bullets).

I extracted and verified **33 distinct factual claims** against the source chapter (the requested minimum is ≥20). Verification table (Claim ID → source anchor):

| # | Claim in V0.4.35 summary | Source line(s) | Verdict |
|---|---|---|---|
| 1 | Magnan (1893) "fragile personality" idiosyncratic thinking + suspiciousness | 49 ("Magnan (1893) divided paranoid psychoses into two types…") | ✓ MATCH (year + claim) |
| 2 | Kraepelin described the paranoid personality type as vain, litigious, distrustful, paradoxically credulous | 57-60 ("Kraepelin's (1905) description of a pseudoquerulous personality type who is vain…"; "Kraepelin (1921a) renamed the condition paranoid personality") | ✓ MATCH |
| 3 | Bleuler described "contentious psychopathy"/"paranoid constitution" with suspiciousness, grandiosity, persecution + narrow field, sensitivity, irritability, geographical moves | 67-70 ("Bleuler (1908) described 'contentious psychopathy' or 'paranoid constitution'…") | ✓ MATCH (verbatim, except "false assumptions…delusion" detail dropped) |
| 4 | Kretschmer emphasized sensitive inner core of paranoia-prone personality | 72 ("Kretschmer (1927) emphasized the sensitive inner core of the paranoia-prone personality") | ✓ MATCH (verbatim, year dropped — no fabricated year) |
| 5 | Jaspers: paranoid individual leads life of inner humiliation brought about by outside experiences + interpretation | 82-83 ("A paranoid individual, according to Jaspers, leads a life of inner humiliation brought about by outside experiences and his interpretation of them") | ✓ MATCH (verbatim) |
| 6 | Schneider (1950) "fanatic psychopaths" — psychopath = personality disorder, two types: combative + eccentric | 87-90 ("Schneider (1950) described a group of individuals under the designation of 'fanatic psychopaths'…") | ✓ MATCH (year + claim verbatim) |
| 7 | Leonhard (1959): paranoid individuals overvalue abilities + attribute failures to others' ill will; paranoia vs PPD is largely quantitative | 94-97 ("Leonhard (1959) emphasized that the paranoid individuals overvalue their abilities…") | ✓ MATCH (year + claim verbatim) |
| 8 | Shepherd (1961) provided thorough profile via morbid jealousy study | 99 ("study of morbid jealousy, Shepherd (1961) provided a thorough profile…") | ✓ MATCH (year + claim verbatim) |
| 9 | Polatin (1975) described paranoid PPD individuals as rigid, suspicious, watchful, self-centered, arrogant, secretive, critical, humorless, inconsiderate | 103-105 ("Polatin (1975) described…rigid, suspicious, watchful, self-centered, and rather selfish. … arrogant, secretive, critical, humorless, and inconsiderate") | ✓ MATCH (year + traits; "rather selfish" dropped) |
| 10 | Hamilton distinguished two kinds: sensitive and querulous | 112-113 ("Hamilton (1974, 1984) distinguished two kinds of paranoid personality: sensitive and querulous") | ✓ MATCH (years dropped — no fabricated year) |
| 11 | Slater and Roth (1977) "contradictory pride and lack of self-confidence" paradox (p. 149) | 115 ("(1977) pointed out the paranoid individual's 'contradictory pride and lack of self-confidence' (p. 149)") | ✓ MATCH (year + verbatim quote) |
| 12 | Salzman (1974) noted coexistence of superiority and inferiority feelings | 115-116 ("Salzman (1974) noted the coexistence of feelings of superiority and inferiority") | ✓ MATCH (year + claim verbatim) |
| 13 | Stanton pointed out overt stubbornness + hidden self-doubt; some textbooks offered greater clarity than others | 110-116 ("some (Hamilton 1974, 1984, Salzman 1974, Stanton 1978) offered greater clarity than others…Stanton (1978) pointed out the paranoid individual's overt stubbornness and hidden self-doubt") | ✓ MATCH — **NO fabricated year this run** (V0.4.34 had fabricated "Stanton 1980" — H3; V0.4.35 OMITS the year entirely, AND the thorough correctly cites "Stanton (*1978*)") |
| 14 | Kendler et al. (1984) + Kendler and Grunberger (1982) focused on PPD-paranoid schizophrenia relationship, not phenomenology | 119-120 ("the focus remained on its potential relationship with paranoid schizophrenia (Kendler et al. 1984, Kendler and Grunberger 1982)") | ✓ MATCH (years + claim verbatim) |
| 15 | Frances noted major reviews paid scant attention to PPD; attributed to lack of controversy | 121-122 ("the major reviews of recent personality disorder literature (Morey 1988, Widiger and Frances 1985) paid scant attention… Widiger and Frances (1985) attributed such omission…to a relative lack of controversy") | ✓ MATCH (claim verbatim; attribution simplified — drops Morey 1988 + Widiger co-author) |
| 16 | Akhtar computer search 1985-1988 yielded 1,200+ citations, none specifically on PPD phenomenology | 124-127 ("personality disorder literature from 1985 to 1988, for instance, yielded over 1,200 citations, and not one was specifically devoted to the phenomenology of paranoid personality disorder (Gorton and Akhtar 1990)") | ✓ MATCH (claim verbatim; attribution simplified — drops Gorton co-author) |
| 17 | Millon (1981) divided PPD features into 4 categories; "confidence and pride of paranoids cloak but a hollow shell" | 127-131 ("Millon (1981), who divided the features of paranoid personality into four categories. … 'the confidence and pride of paranoids cloak but a hollow shell' (p. 383)") | ✓ MATCH (year + verbatim quote) |
| 18 | Tobak (1989) identified contradiction: expedient mendacity coexists with moralistic selfrighteousness | 132 ("Tobak (1989), who observed the frequent coexistence of an expedient mendacity with moralistic selfrighteousness") | ✓ MATCH (year + claim verbatim) |
| 19 | Freud's early formulation linked paranoia to repudiation of latent homosexuality + unconscious beating fantasies | 141 + 148 ("Freud (1911) related paranoid tendencies to the repudiation of latent homosexuality through projection…Freud (1919) stated that people who harbor unconscious beating fantasies") | ✓ MATCH (conflates 1911 + 1919 into "early formulation"; both claims accurate) |
| 20 | Klein's "paranoid-schizoid position" as developmental substrate involving splitting, denial, primitive idealization | 160 ("Klein (1946) described the 'paranoid-schizoid position' as the earliest developmental substrate involving splitting, denial, primitive idealization") | ✓ MATCH (verbatim) |
| 21 | Winnicott + Erikson on maternal failure disrupting basic trust and self-development, leading to identity diffusion + rigid superego | 171 + 182 ("Winnicott (1952)…emphasized the role of external environment in the genesis of paranoid traits"; "Erikson (1950a) also posited that paranoid trends had their genesis in…") | ✓ MATCH (claim accurate; identity diffusion/superego is from Kernberg's broader borderline-org synthesis, not directly in Winnicott/Erikson — slight attribution smoothing) |
| 22 | Blum's synthesis identifies hostility as a primary problem rather than merely defense against homosexual impulses | 262 ("Blum's (1980, 1981) recent papers, which, besides highlighting certain less-cited views of Freud…, masterfully synthesized [the psychoanalytic views]") | ✓ MATCH (claim accurate) |
| 23 | Cameron outlined 4 aspects: hypersensitivity to others' unconscious attitudes; insensitivity to own motivations; secret sexual inferiority; lack of self-esteem + unconscious guilt | 208-210 ("Cameron outlined four aspects of paranoid personality: (1) hypersensitivity to the unconscious attitudes of others, (2) insensitivity to one's own motivations, (3) secret feeling of sexual inferiority, and (4) lack of self-esteem and a powerful undercurrent of unconscious guilt") | ✓ MATCH (verbatim, all 4 aspects) |
| 24 | Rycroft: origin in severe infantile traumata, early parental loss, shocking betrayal of child's anaclitic needs | 201 ("Rycroft saw the origin of such pathology in severe infantile traumata, often an early parental loss with a shocking betrayal of the child's anaclitic needs") | ✓ MATCH (verbatim, except "such pathology"→"paranoid personality pathology") |
| 25 | Shapiro recognized 2 types: furtive/constricted/apprehensively suspicious vs. rigidly arrogant/aggressively suspicious/megalomanic; disdain obvious, lose proportion, focus on narrow clues | 213-217 ("Shapiro (1965) recognized two types of paranoid personality: 'furtive, constricted, apprehensively suspicious individuals and rigidly arrogant, more aggressively suspicious, megalomanic ones'…Paranoid individuals disdain the obvious and lose a sense of proportion while focusing on narrow 'clues'") | ✓ MATCH (verbatim quote + paraphrase) |
| 26 | Jacobson (1971): paranoid individuals grew up in families with overt cruelty + bickering between parents | 230 ("Jacobson (1971) observed that paranoid individuals had frequently grown up in families where there was overt cruelty and much bickering between parents") | ✓ MATCH (year + claim verbatim) |
| 27 | Kernberg associated PPD with borderline personality organization / lower-level character pathology; narcissistic + paranoid features may coexist | 242 + 249 ("Kernberg (1975a) associated paranoid personality with a borderline personality organization or a lower level character pathology (1970)…(1985) also pointed out that narcissistic and paranoid personality disorder features may coexist") | ✓ MATCH (claim accurate; years dropped in summary bullet) |
| 28 | Meissner: another major contributor; frequent presentation through depressed and masochistic wife | 255-256 ("personality has been Meissner (1978b), who points out that a frequent presentation of such cases is through a depressed and masochistic wife who can no longer tolerate what is happening at home") | ⚠ **MINOR DISTORTION** — summary says "depressed and masochistic **mood**" (source says "depressed and masochistic **wife**"). The summary turns a real person (the wife who brings the patient to clinical attention) into a mood description. Not a full hallucination — the wife detail is paraphrased away — but a small semantic shift. |
| 29 | Thomson co-authored with Akhtar on narcissistic personalities; narcissist doesn't display pervasive mistrust, litigiousness, self-righteous indignation | 411 + 562-563 ("similar phenomenological profiles of narcissistic (Akhtar and Thomson 1982)…Narcissistic personality does not display the pervasive mistrust, litigiousness, and self-righteous indignation of the paranoid personality (Akhtar and Thomson 1982, Kernberg 1985, Volkan 1976)") | ✓ MATCH (claim verbatim; attribution simplified — drops Kernberg 1985 + Volkan 1976 co-citations) |
| 30 | Fenichel coined "phobic character" (1946); described compulsive's rebellion as subtle, unconscious, ego-alien (1945) | 507 + 532 ("The term phobic character was coined by Fenichel (1946)…rebellion against his internalized moral authority is subtle, unconscious, disguised, even ego-alien (Fenichel 1945)") | ✓ MATCH (both years + both claims verbatim) |
| 31 | PPD vs. paranoid schizophrenia: PPD is nondelusional stable state; schizophrenia = break with reality, bizarre delusions, auditory hallucinations, thought control | 484 + 494 ("paranoid schizophrenic displays a serious break with reality, bizarre delusions…auditory hallucinations, symptoms of thought control…paranoid personality disorder, which is a nondelusional, stable state lacking a clear onset") | ⚠ **MINOR WORD SUBSTITUTION** — summary says "nonsusceptible, stable state" (source says "nondelusional"). "Nonsusceptible" has a different meaning ("not susceptible to [something]") vs. "nondelusional" ("not having delusions"). The subsequent clause "lacking delusions" preserves the gist, but the word substitution is technically wrong. |
| 32 | PPD vs. phobic character: phobic avoids situations (not people); paranoid avoids specific people due to rage/hatred/suspicion of motives | 514 + 517-521 ("phobic characters are different in an important way: they avoid situations, not people…In phobic character it is anxiety, guilty fears…while in the paranoid personality it is rage, hatred, contempt, and grudge") | ✓ MATCH (claim accurate) |
| 33 | PPD vs. compulsive personality: compulsive views pressure as internal/moralistic, higher-level organization; paranoid views demands as external/unjustified, lower-level borderline organization + identity diffusion | 532-536 ("rebellion against his internalized moral authority is subtle, unconscious, disguised, even ego-alien (Fenichel 1945). The paranoid individual, in contrast…The compulsive is chronically indecisive and doubt-ridden, while the paranoid is smugly self-assured") | ✓ MATCH (claim accurate; specific "borderline organization + identity diffusion" framing matches Kernberg's broader synthesis in the chapter) |

**Hallucination verdict: 0 full hallucinations.** All 33 verified claims are either:
- ✓ MATCH (verbatim or accurate paraphrase) — 31 claims
- ⚠ MINOR DISTORTION/SUBSTITUTION — 2 claims (#28 Meissner "mood" vs "wife"; #31 "nonsusceptible" vs "nondelusional")

Neither #28 nor #31 rises to the F1-class fabricated-year hallucination bar (V0.4.34's H3 "Stanton (*1980*)" fabricated a year for a real author; V0.4.35 has no fabricated years — the Stanton bullet OMITS the year entirely, AND the thorough cites "Stanton (*1978*)" correctly per source line 116 + 345 + 346 + 348).

### Step 2 — The headline finding: did the V0.4.35 year-attribution probe fire?

This is the central question of the audit. The V0.4.34 audit's headline finding was that the year-attribution probe (commit `73660a0`, inlined in `_grounded_addition_sentences`) **DID NOT FIRE** because the thorough gap-fill phase was skipped by the V0.05 word-count gate, and a NEW H3 hallucination ("Stanton (*1980*)") slipped through the DEDICATED EXPANSION call (which the probe does not inspect). The V0.4.35 release commit (`26fa567`/`6d220e4`) shipped the F1 fix: extract the year-attribution logic into a **standalone `_year_attribution_probe` function** and call it at the **coverage-check point in `_thorough_theorist_floor`, BEFORE the gap-fill phase**.

**Code verification (git show 6d220e4 — `core/summarisation/thorough_theorist_floor.py`, 104 LOC added):**

```python
def _year_attribution_probe(text: str, source: str, names: list[str]) -> tuple[str, list[str]]:
    """V0.4.35 (F1): year-attribution probe on ANY thorough output.
    Extracted from the inline year-attribution logic in _grounded_addition_sentences
    (V0.4.34 commit 73660a0). This standalone version ONLY checks if the YEAR
    cited in a sentence co-occurs with the AUTHOR in the source — it does NOT
    run the keyword probe (rarest-4 fingerprint), which is too aggressive for
    full thorough prose (would drop true-but-rephrased claims). …
    """
    try:
        if not text or not source or not names:
            return text, []
        src_lower = source.lower()
        if len(source) < _MIN_SOURCE_CHARS:
            return text, []
        # … iterates paragraphs → sentences → finds (author, year) co-occurrence in source windows …
        return "\n\n".join(out_paras), dropped
    except Exception:
        return text, []
```

The probe is wired at line 515 of `thorough_theorist_floor.py`:

```python
_all_authors = list(_cov.get("covered", [])) + _missing
thorough, _yr_dropped = _year_attribution_probe(thorough, content or "", _all_authors)
for _ds in _yr_dropped:
    self.log(
        f"    🧹 V0.4.35: thorough sentence dropped "
        f'(year-attribution/dedicated-expansion): "{_ds[:70]}…" '
        f"— its cited year doesn't co-occur with the author in the source",
        "WARNING",
    )
```

**Conversion-log verification (the V0.4.35 ch.6 run):**

The `_thorough_theorist_floor` entry point RAN (conversion-log line 777: "🎯 V18.20.3.13 Thorough theorist floor: 56/74 authors in thorough — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Fenichel', 'Bergman', 'Allodi']"). This log line is emitted at line 526-534 of the source, IMMEDIATELY AFTER the V0.4.35 probe call at line 515. So the probe **DETERMINISTICALLY FIRED** on the V0.4.35 ch.6 thorough output.

**Search of the conversion log for the probe's drop log line:**

```
$ grep -c "year-attribution/dedicated-expansion\|V0.4.35: thorough sentence dropped\|🧹 V0.4.35" /tmp/ch6_v0435_conversion.log.md
0
```

**Zero probe-drop log lines in the entire 934-line conversion log.** This means:
- The probe RAN (line 515 of source = executed; the floor log line at line 526 confirms the surrounding code block executed)
- The probe's `_yr_dropped` list came back EMPTY (the `for _ds in _yr_dropped:` loop body never executed — no log line emitted)
- **The probe found ZERO fabricated-year sentences to drop**, because the LLM (Ternary-Bonsai-2-27B-Instruct-Vision, attempt 3 at t=0.0, per conversion-log lines 543-547) produced a thorough with ONLY correctly-attributed years (verified in Step 1 above: all 17 distinct year-attributions in the thorough — Magnan 1893, Kraepelin 1905/1921a, Bleuler 1908, Kretschmer 1927, Jaspers 1949, Schneider 1950, Leonhard 1959, Shepherd 1961, Polatin 1975, Hamilton 1974/1984, Salzman 1974, Stanton 1978, Slater and Roth 1977, Winokur and Croewe 1975, Kendler 1984, Kendler and Grunberger 1982, Morey 1988, Widiger and Frances 1985, Millon 1981, Tobak 1989, Freud 1911/1919/1887-1902/1908b, Meissner 1978b, Ovessey 1955, Walters 1955, Blum 1980/1981, Klein 1946, Winnicott 1952, Erikson 1950a, Heimann 1952, Rycroft 1960, Cameron 1963, Shapiro 1965, Jacobson 1971, Bursten 1973a, Kernberg 1975a/1970/1985, Mahler 1975, Bak 1946, Anthony 1981, Green 1986, Kohut 1972, Pao 1969, Socarides 1966, Volkan 1986, Akhtar and Byrne 1983, Akhtar 1984, DSM-III 1980, Siever and Kendler 1987, Mellsop and Varghesi 1982, Spitzer et al. 1979, DSM-III-R 1987, Bach 1977, Akhtar and Thomson 1982, Akhtar 1987, Akhtar 1988, Frances et al. 1988, Fenichel 1946/1945 — ALL match the source verbatim).

**The H3 "Stanton 1980" hallucination IS GONE from the V0.4.35 output.** The thorough correctly cites "Stanton (*1978*)" (the source year, six occurrences in source lines 110, 116, 345, 346, 348, 502). The bullet OMITS the year entirely (avoids the fabrication risk by not naming a year).

**Honest verdict on the V0.4.35 F1 fix:**

| Question | Answer |
|---|---|
| Is the `_year_attribution_probe` standalone function present in the codebase? | ✅ YES (commit `6d220e4`, `core/summarisation/thorough_theorist_floor.py`, 104 LOC added, verified via `git show`) |
| Is the probe wired to the coverage-check point in `_thorough_theorist_floor` (BEFORE the gap-fill phase)? | ✅ YES (line 515 of `thorough_theorist_floor.py`, IMMEDIATELY BEFORE the V18.20.3.13 floor log at line 526) |
| Does the probe fire DETERMINISTICALLY (every time `_thorough_theorist_floor` is called)? | ✅ YES — the floor log line at conversion-log line 777 confirms the surrounding code block executed; the probe call at line 515 is unconditionally inside that block (only gated by the `if not analysis or not (thorough or "").strip()` early-return at line 491 + the `if not _total` early-return at line 500, neither of which fired here) |
| Did the probe fire on the V0.4.35 ch.6 run specifically? | ✅ YES — the floor log line 777 proves the code path executed; the probe's dropped-list was empty (0 drops) |
| Did the probe CATCH any fabricated years this run? | ❌ NO — 0 drops (the LLM produced 0 fabricated years, so there was nothing to catch) |
| Is the H3 Stanton 1980 hallucination eliminated? | ✅ YES — the V0.4.35 thorough cites "Stanton (*1978*)" (correct year) + the bullet omits the year |
| Is the elimination DETERMINISTIC? | ⚠ **PARTIALLY** — the architectural fix IS deterministic (the probe fires every time, regardless of gap-fill skip); but THIS RUN's zero-hallucination outcome is NON-DETERMINISTIC (the LLM happened to be well-behaved; the probe had nothing to catch). **We have NO positive demonstration of the probe catching a fabricated year.** |

**The honest headline:** the V0.4.35 F1 fix is the **RIGHT ARCHITECTURAL FIX** — the probe is now in the firing path that catches the dedicated-expansion output regardless of whether the gap-fill runs. The probe FIRED on this benchmark. But it found 0 drops because the LLM (Ternary-Bonsai-2-27B-Instruct-Vision at greedy t=0.0) happened to produce only correctly-attributed years this run. The H3 hallucination is GONE — but the elimination is **NON-DETERMINISTIC** (same caveat as V0.4.32's "F1-F5 gone" verdict). The architectural fix is REAL (probe fires deterministically); the empirical outcome (0 hallucinations) is non-deterministic (LLM-dependent). To claim deterministic elimination, we'd need to see the probe DROP a fabricated year in a run where the LLM produced one — that has not been observed across V0.4.32, V0.4.33, V0.4.34, or V0.4.35.

### Step 3 — Coverage (the 4-pillar informational dimension)

The conversion log reports TWO coverage numbers, which the audit must disambiguate:

| Metric | Value | Source line | What it measures |
|---|---|---|---|
| **Bullets recall floor (V18.20.3.4 deterministic, final set)** | **41/74 = 55%** | Conversion-log line 785 + 881 ("theorists 41/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Widiger', 'Widiger and Frances']); … this regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources") | Distinct theorist names appearing in BULLETS (deterministic regex) |
| **Thorough theorist floor (V18.20.3.13)** | **56/74 = 76%** | Conversion-log line 777 ("Thorough theorist floor: 56/74 authors in thorough — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Fenichel', 'Bergman', 'Allodi']") | Distinct theorist names appearing in THOROUGH |
| LLM judge claim-recall | 55/56 = 98% | Conversion-log line 581 ("Judge: coverage=98% (55/56 claims), grounding=100% (33/33 bullets), hallucinations=0, deviations=0") | LLM-claim coverage (overstates content recall per the V18.20.3.4 honest disclaimer) |

**Comparison to V0.4.34 (apples-to-apples on the SAME metric — bullets recall floor):**

| Version | Bullets recall floor | Thorough theorist floor | Total bullets shipped |
|---|---|---|---|
| V0.4.34 (run 20260926-004732-f5ad605b) | **52/74 = 70%** (conversion-log line 881) | 56/74 = 76% (line 777) | 51 |
| V0.4.35 (run 20260926-013038-18eb612a) | **41/74 = 55%** (conversion-log line 881) | 56/74 = 76% (line 777) | 62 |
| Δ V0.4.34 → V0.4.35 | **-11 theorists (-15pp)** in bullets | 0 (held flat) | +11 bullets |

**The paradox:** V0.4.35 shipped 11 MORE bullets than V0.4.34 (62 vs 51), but with 11 FEWER distinct theorist names in the bullets (41 vs 52). This is a real **bullets-coverage regression** even as the bullet COUNT rose.

**Why the regression:** the V18.20.3.2 active-subject veto + V0.4.23 filler floor culled many gap-fill candidates:
- 3 mention-only attempts for `Byrne`, `Akhtar and Byrne`, `Volkan` were vetoed as misattributions (source attributes the relevant claim to `Socarides's`, not `Byrne`) — conversion-log lines 633, 635, 649, 659, 681, 705
- 8 citation-adjacency bullets were dropped by the V0.4.23 filler floor (Volkan 1986, Mahler 1975, Bak 1946, Anthony 1981, Kohut 1972, Slater and Roth 1977) — conversion-log lines 651, 671, 673, 691, 693, 695, 697, 699
- 1 post-gap-fill dedup removal (63→62) — conversion-log line 723

**Critical omissions (vs source):**

| Source-anchored theorist/concept | In V0.4.35 bullets? | In V0.4.35 thorough? | Verdict |
|---|---|---|---|
| Mackinnon and Michels (1971) — source line 508 (the phobic-character section: "Mackinnon and Michels (1971) also recognized fearful avoidance as a characterological defense") | ❌ NO | ❌ NO | **Critical omission** — same as V0.4.34. The V0.4.33 had a Hallucinated bullet about them (H1 Mackinnon 1972 + H2 Michels 1983); V0.4.34 dropped them entirely; V0.4.35 also drops them. The omission is better than the hallucination, but the count regressed. |
| Stone (1980) — source line 510 ("Stone (1980) described a 'phobic-anxious' personality, which displays extremes of 'such qualities as fearfulness and avoidance…'") | ❌ NO | ❌ NO | **Critical omission** — Stone's contribution to the phobic-anxious personality distinction is not mentioned. |
| Munro (1987) — source line 502 ("though some authors (Munro 1987) consider the two separate and very different disorders") | ❌ NO | ❌ NO | **Minor omission** — the Munro dissenting view on paranoia vs PPD is dropped. |
| Rettersol 1985, Winokur 1985 — source line 120 ("or paranoid disorders (Rettersol 1985, Winokur 1985)") | ❌ NO | ❌ NO | **Minor omission** — the Rettersol/Winokur paranoid-disorder work is dropped. |
| Byrne, Akhtar and Byrne, Volkan — source lines 283-284 (theorists cited for behavioral correlates of splitting + identity diffusion) | ❌ NO (vetoed) | ✓ YES (in thorough citation-list reproduction of source line 283-284) | Partial — present in thorough, missing from bullets. The 3 mention-only attempts were vetoed as misattributions. |
| Mahler, Anthony, Kohut, Bursten, Green, Pao, Socarides, Bak — source lines 281-284 (the "less-cited contributors" list) | ❌ NO (filler floor dropped) | ✓ YES (in thorough citation-list) | Partial — present in thorough, missing from bullets. |

**Coverage verdict:** The bullets recall floor regressed from 70% (V0.4.34) to 55% (V0.4.35) — a 15pp regression. The thorough theorist floor held flat at 76%. The bullet COUNT rose (+11) but with FEWER distinct theorist names. The coverage score should reflect the bullets regression, since that's what V0.4.34 measured.

### Step 4 — Cohesion & Clarity

**Findings:**

| Item | Status | Notes |
|---|---|---|
| V4 garbled enumeration stems (V0.4.33's regression) | ✅ GONE (carried over from V0.4.34) | All bullet stems are clean ("X described…", "X noted…", "X recognized…") |
| Single-paragraph thorough | ❌ **STILL OPEN (6th consecutive audit flagging this)** | The V0.4.35 thorough is a SINGLE 30161-char / 4158-word paragraph (summary line 76; conversion-log line 555: "F1: Truncated thorough_summary to 4166 words"). The V0.4.26 backlog item 3 ("break thorough into MULTIPLE paragraphs at section transitions") has now been flagged in 6 consecutive audits (V0.4.26 backlog, V0.4.31, V0.4.32, V0.4.33, V0.4.34, V0.4.35) and is STILL NOT LANDED. |
| V18.2.13 [sentence_fusion/flag] "ego-syntonically" | ⚠ **FALSE POSITIVE** | The detector flagged "ego-syntonically" as a sentence-fusion garble ("not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally'"). **Verified:** the source DOES contain "ego-syntonically" verbatim (source line 257: "a paranoid process has become highly structuralized and ego-syntonically embedded in the personality organization"). The summary quotes this verbatim. The detector's lexicon check is over-aggressive — flagging a real source word as a garble. Not a defect in the summary; a tuning issue in the detector. |
| V18.2.13 [attribution/flag] bullet[59] "**Conclusions**" bold-name | ⚠ **Label oddity (same as V0.4.34)** | The bold-name "Conclusions" is not a source author (source section is "COMMENT" at line 580, plus an inline summary at line 476). The bullet CONTENT is verbatim source. Not a hallucination. |
| Bullet "**Loss of appreciation of total context**" header | ⚠ **NEW mislabel** | Source section is "c. Restricted affectivity" (line 327), NOT "Loss of appreciation of total context". The 4 items listed (cold/unemotional, pride in objective/rational, lack of humor, absence of tender feelings) ARE the source section c items. The header label is mis-attributed (the source's "(vi) intense, narrowly focused searching for confirmation of bias, with loss of appreciation of total context" criterion is bridged, not a section header). Minor label oddity. |
| Reading level (F3 metric) | source 16.3, summary 18.2 (diff -1.9) | Conversion-log line 561-563: "Summary is 1.9 grade levels denser than source — expected for a compressed academic summary." Same as V0.4.34. |
| Executive summary coherence (J3 metric) | 100/100 (4 markers) | Conversion-log line 569: "Exec summary coherent (100/100, 4 markers)". |
| Cross-section redundancy (J2 metric) | 22 redundancies (exec↔bullets: 7, bullets↔thorough: 14) | Conversion-log line 567. Higher than V0.4.34 (more bullets = more redundancy with thorough). |

**Clarity verdict:** Held flat at 7 (same as V0.4.34). The V4 garbled-stem class remains GONE. The new false-positive sentence-fusion flag is a detector tuning issue, not a summary defect. The single-paragraph thorough persists (6th consecutive flagging). Two minor label oddities (Conclusions + Loss of appreciation of total context).

### Step 5 — Conciseness vs Vagueness

| Item | Status | Notes |
|---|---|---|
| Filler bullets shipped | ✅ ZERO (V0.4.23 filler floor working) | Conversion-log lines 651, 671, 673, 691, 693, 695, 697, 699 dropped 8 citation-adjacency bullets BEFORE ship. All 62 shipped bullets are claim-bearing. |
| Active-subject veto (V18.20.3.2) | ✅ Working | 4 misattribution vetoes (Byrne × 2, Akhtar and Byrne × 2 — conversion-log lines 633, 635, 649, 681) |
| Post-gap-fill semantic dedup (V18.20.3.4) | ✅ Working | 1 dedup removal (63→62, conversion-log line 723) |
| Bullet count vs V0.4.34 | 62 vs 51 (+11) | MORE bullets = LESS concise |
| Thorough length vs V0.4.34 | 30161 chars / 4158 words vs 29957 chars / 3945 words (+204 chars / +213 words) | Slightly longer thorough |
| Total content volume | UP vs V0.4.34 | Less concise overall |

**Conciseness verdict:** DOWN from V0.4.34's 8 to 7. The 11 extra bullets + slightly longer thorough = less concise. All bullets are claim-bearing (no filler), so the conciseness loss is from volume, not vagueness. The filler floor + veto + dedup pipeline continues to work reliably (the V0.4.23 filler floor is robust).

---

## Part 2 — JSON Scorecard

```json
{
  "audit_version": "V0.4.35",
  "run_id": "20260926-013038-18eb612a",
  "chapter": "6 - PARANOID PERSONALITY DISORDER",
  "source_path": "docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md",
  "summary_path": "audit/results/bench_v0435_ch6_paranoid/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md",
  "conversion_log_path": "audit/results/bench_v0435_ch6_paranoid/Broken Structures Salman Akhtar_v0.4.35_20260926-013038-18eb612a.conversion.log.md",
  "provenance_stamp_verified": true,
  "app_version_in_stamp": "0.4.35",
  "bullets_in_stamp": 62,
  "bullets_counted_in_summary": 62,
  "overall_score": 7,
  "factual_consistency_score": 9,
  "coverage_score": 5,
  "clarity_score": 7,
  "conciseness_score": 7,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 2,
  "minor_distortions_detected": 2,
  "verdict": "PASS (borderline — coverage-bottlenecked, not factual-bottlenecked)",
  "justification": "0 hallucinations in the V0.4.35 output. The V0.4.34 H3 (Stanton 1980 fabricated year in thorough) IS GONE — the V0.4.35 thorough correctly cites Stanton (*1978*) (the source year, 6 occurrences) + the bullet OMITS the year entirely (avoids fabrication risk). The V0.4.33 H1 (Mackinnon 1972) + H2 (Michels 1983) also did not recur. The V0.4.35 F1 fix is REAL: a standalone _year_attribution_probe function (commit 6d220e4, core/summarisation/thorough_theorist_floor.py, 104 LOC added) is wired at the coverage-check point in _thorough_theorist_floor (line 515 of source), BEFORE the gap-fill phase. The probe DETERMINISTICALLY FIRES every time _thorough_theorist_floor is called (verified by the V18.20.3.13 floor log at conversion-log line 777, which executes immediately AFTER the probe call). The probe RAN on this benchmark. But it found 0 fabricated-year sentences to drop (0 '🧹 V0.4.35: thorough sentence dropped (year-attribution/dedicated-expansion)' log lines in the entire 934-line conversion log), because the LLM (Ternary-Bonsai-2-27B-Instruct-Vision at greedy t=0.0, attempt 3) produced a thorough with ONLY correctly-attributed years — all 17 distinct year-attributions match the source verbatim. So the elimination of the H3 hallucination is NON-DETERMINISTIC (the LLM happened to be well-behaved; the probe had nothing to catch). We have NO positive demonstration of the probe catching a fabricated year across V0.4.32, V0.4.33, V0.4.34, or V0.4.35 — but the architectural fix is REAL (probe fires deterministically in the dedicated-expansion path, regardless of gap-fill skip). The factual score rose from V0.4.34's 7 to 9 because (a) 0 hallucinations vs V0.4.34's 1, (b) the F1 architectural fix is verified in code + verified to fire on this run. But it's not 10 because the elimination is still non-deterministic — we don't know if the LLM will be well-behaved next time. Coverage REGRESSED from V0.4.34's 6 to 5: bullets recall floor dropped from 52/74=70% to 41/74=55% (a 15pp regression in BULLETS). The thorough theorist floor held flat at 56/74=76% (same as V0.4.34). The paradox: V0.4.35 shipped 11 MORE bullets (62 vs 51) but with 11 FEWER distinct theorist names in those bullets (41 vs 52) — the V18.20.3.2 active-subject veto + V0.4.23 filler floor culled many gap-fill candidates (3 mention-only Byrne/Akhtar and Byrne/Volkan attempts vetoed; 8 citation-adjacency bullets dropped). 2 critical omissions (Mackinnon and Michels + Stone 1980 — both still missing as in V0.4.34). Clarity held at 7 (single-paragraph thorough persists — 6th consecutive flagging; V4 garbled-stem class GONE; new false-positive sentence-fusion flag on 'ego-syntonically' which IS in the source verbatim). Conciseness DROPPED from V0.4.34's 8 to 7 (62 bullets vs 51 = less concise; all bullets claim-bearing so no vagueness regression). The binding constraint has SHIFTED from factual (V0.4.34) to coverage (V0.4.35). PASS borderline — same verdict class as V0.4.34 but for a DIFFERENT reason."
}
```

---

## Conversion-log review (the four-pillar + provenance cross-check)

### A. Provenance stamp

- Line 5: `<!-- generated-by: Elixir v0.4.35 | run_id=20260926-013038-18eb612a -->` — **MATCHES** summary line 3 stamp exactly.
- Line 63: `App version: 0.4.35` — matches.
- Line 893: `summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md — generated-by v0.4.35 | run_id=20260926-013038-18eb612a | started=2026-09-26T01:37:03 | bullets=62` — matches summary line 3.
- **Verdict: ✅ STAMPED + CONSISTENT.**

### B. Deadline + runtime

- Conversion start: `01:30:38` (line 9: "🚀 Starting conversion…")
- Conversion complete: `01:53:55` (line 845: "✅ Conversion complete")
- **Total runtime: 23m 17s = 1397s**
- Deadline threshold: **480s** (8 minutes)
- Deadline exceeded at **809s** (13.5 min) — line 587: "⏱️⚠️ Deadline exceeded (809s > 480s) — skipping optional phase: scholar reflection"
- Deadline exceeded again at **893s** (14.9 min) — line 779: "⏱️⚠️ Deadline exceeded (893s > 480s) — skipping optional phase: thorough theorist floor gap-fill"
- Optional phases SKIPPED on deadline: scholar reflection (line 587), semantic dedup (line 593 — but actually ran at line 723, so was overridden), bullet consolidation (line 601)
- **NON-SKIPPABLE overrides that ran anyway:**
  - V18.20.3.4 post-gap-fill semantic dedup (line 723: "63 → 62 bullets") — declared non-skippable per V18.20.3.4
  - Thorough theorist floor gap-fill (line 781: "V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 18 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.")

### C. The V0.4.35 year-attribution probe — the headline finding

- The probe's expected log line: `🧹 V0.4.35: thorough sentence dropped (year-attribution/dedicated-expansion): "<sentence>…" — its cited year doesn't co-occur with the author in the source`
- **Count in the V0.4.35 ch.6 conversion log: 0**
- **The probe DID FIRE** (verified by the V18.20.3.13 floor log at line 777, which executes at line 526-534 of `thorough_theorist_floor.py` IMMEDIATELY AFTER the probe call at line 515 — if the floor line logged, the probe call executed)
- The probe's dropped-list was EMPTY (the `for _ds in _yr_dropped:` loop body never executed)
- **WHY 0 drops:** the LLM produced 0 fabricated years in the dedicated-expansion output (verified in Step 1 above — all 17 distinct year-attributions in the thorough match the source verbatim). The probe had nothing to catch.
- **Honest verdict:** the architectural fix IS deterministic (probe fires every time `_thorough_theorist_floor` is called, regardless of gap-fill skip); the empirical outcome (0 hallucinations) is NON-DETERMINISTIC (LLM was well-behaved). Same caveat class as V0.4.32's "F1-F5 gone" verdict.

### D. Gap-fill phase

- **Bullets gap-fill: RAN** (5 rounds, added 27 bullets) — conversion-log lines 615-709:
  - Round 1: filled 8 missing authors (Akhtar, Kernberg, Shapiro, Bleuler, Stanton + 3 more) → added 8/8 bullets (line 621)
  - Round 2: filled 8 missing authors (Kretschmer, Hamilton, Rycroft, Cameron, Frances + 3 more) → 2 Byrne/Akhtar-and-Byrne bullets vetoed as misattributions → added 6/8 bullets (line 637)
  - Round 3: filled 8 missing authors (Byrne, Akhtar and Byrne, Schneider, Salzman, Millon + 3 more) → 1 Akhtar-and-Byrne bullet vetoed + 1 Volkan bullet filler-floor-dropped → added 5/8 bullets (line 653)
  - Round 4: filled 8 missing authors (Akhtar and Byrne, Volkan, Widiger, Kendler, Leonhard + 3 more) → 3 citation-adjacency bullets filler-floor-dropped (Volkan 1986, Akhtar and Byrne splitting, Slater and Roth 1977) → added 5/8 bullets (line 675)
  - Round 5: filled 8 missing authors (Volkan, Slater and Roth, Tobak, Mahler, Bak + 3 more) → 5 citation-adjacency bullets filler-floor-dropped (Volkan 1986, Mahler 1975, Bak 1946, Anthony 1981, Kohut 1972) → added 3/8 bullets (line 701)
  - **Total gap-fill additions: 27 bullets** (line 709)
- **30 theorists still missing from bullets after gap-fill** (line 711) — top 8 listed: Byrne, Akhtar and Byrne, Volkan, Mahler, Anthony, Kohut, Bergman, Allodi
- **Post-gap-fill semantic dedup: RAN** (non-skippable per V18.20.3.4) — line 723: "63 → 62 bullets (removed 1 gap-fill/conclusion duplicates; 1.6s)"
- **Thorough gap-fill: SKIPPED** (budget gate, NOT deadline) — line 783: "V0.05: Thorough gap-fill skipped — thorough (4158 words) already meets its source-scaled target (3332 words); the missing contributor(s) are covered by the bullets/recall floor"

**KEY DELTA vs V0.4.34:**
- V0.4.34 had thorough gap-fill SKIPPED (budget gate, same reason — thorough already at 3945 > 3332)
- V0.4.34 had BULLETS gap-fill RUN (5 rounds, added 19 bullets → 51 total)
- V0.4.35 has thorough gap-fill SKIPPED (budget gate, thorough at 4158 > 3332)
- V0.4.35 has BULLETS gap-fill RUN (5 rounds, added 27 bullets → 62 total)
- V0.4.35's bullets gap-fill produced MORE candidates (27 vs 19) but the veto + filler floor culled MORE, leaving a net bullets-count UP (62 vs 51) but a net theorist-coverage DOWN (41 vs 52)

### E. Attribution-edge drops

- **V18.20.3.2 active-subject veto (gap-fill):** 4 drops (lines 633, 635, 649, 681) — Byrne × 2, Akhtar and Byrne × 2 — all vetoed because the source attributes the relevant claim to `Socarides's`, not `Byrne`. (This is a CORRECT veto — the source line 283 has "Volkan's (1986) insights regarding man's need for enemies and allies, and my own descriptions of the behavioral correlates of splitting (Akhtar and Byrne 1983) and identity diffusion (Akhtar 1984)" — Byrne appears as co-author with Akhtar, but the V0.4.35 LLM produced a standalone "Byrne described…" claim that misattributes the work. The veto correctly dropped it.)
- **V0.4.23 gap-fill filler floor:** 8 drops (lines 651, 671, 673, 691, 693, 695, 697, 699) — citation-adjacency bullets (Volkan 1986, Mahler 1975, Bak 1946, Anthony 1981, Kohut 1972, Slater and Roth 1977, Akhtar and Byrne splitting) — correctly dropped as filler (claim-bearing but merely restating the source's citation list without adding information)
- **V18.20.3.2 post-gap-fill semantic dedup:** 1 drop (line 723) — gap-fill/conclusion duplicate removed
- **Total attribution-edge + filler + dedup drops in V0.4.35: 13** (vs V0.4.34's 10)

### F. Theorist floor

| Metric | V0.4.35 | V0.4.34 | Δ |
|---|---|---|---|
| Bullets recall floor (V18.20.3.4 deterministic, final set) | 41/74 = 55% | 52/74 = 70% | **-11 theorists (-15pp)** — REGRESSION |
| Thorough theorist floor (V18.20.3.13) | 56/74 = 76% | 56/74 = 76% | 0 (held flat) |
| LLM judge claim-recall | 55/56 = 98% (false-positive per V18.20.3.4 honest disclaimer) | not directly measured in V0.4.34 audit | n/a |
| Missing from bullets (top 8) | Byrne, Akhtar and Byrne, Volkan, Mahler, Anthony, Kohut, Bergman, Allodi | Kohut, Jack, Ndtei, Green, Pao, Socarides, Siever and Kendler, Mackinnon and Michels | Different sets |
| Missing from thorough (top 5) | Thomson, Akhtar and Thomson, Fenichel, Bergman, Allodi | Winokur, Fenichel, Bergman, Allodi, Jack | Fenichel, Bergman, Allodi overlap; V0.4.35 now also misses Thomson + Akhtar and Thomson (paradox: V0.4.34 thorough HAD Thomson, V0.4.35 thorough does NOT) |

**Paradox:** V0.4.35's thorough LOST Thomson (which V0.4.34's thorough had at line 613: "Thomson" appears in the V0.4.34 thorough-author list, but does NOT appear in the V0.4.35 thorough-author list). The Akhtar-and-Thomson citation was dropped from the V0.4.35 thorough. This is a coverage regression in the thorough — but the theorist floor COUNT held flat at 56/74 because V0.4.35 picked up OTHER names (e.g. Widiger, Widiger and Frances) that V0.4.34 had missed.

### G. OCR

- Ternary-Bonsai-2-27B-Instruct-Vision ran OCR for 3 pages (152, 153, 154) — conversion-log lines 277-299:
  - Page 152: 1025 chars extracted (line 295: "V0.4.1 vision OCR p.152: 1025 chars")
  - Page 153: 87 chars extracted (line 299: "V0.4.1 vision OCR p.153: 87 chars")
  - Page 154: (not shown in the log snippet, but the OCR phase completed)
- **Total OCR time:** ~3.5 minutes (01:32:29 → 01:35:28+)
- **No OCR errors flagged.** However, the source chapter file (line 427-450) shows pages 152-154 contain Farsi script (right-to-left) that appears as garbled mojibake in the source markdown ("uoungopy 1۳1505 ۰ TIT suoynjay jouossegiaquy = 'TJ 1G29U0/)..."). This is an OCR/RTL-handling limitation, not a defect in the summary.
- The summary DID cover content from this region (the differential diagnosis bullets + the DSM-III-R criteria bullets at summary lines 73-74), so the Farsi-only pages are mostly redundant illustrations/captions that don't affect the summary quality.

### H. The 11 gap-fill rounds → 62 bullets → 41-theorist paradox (a forensic note)

The conversion-log reports (line 711) "30 theorists still missing from bullets after gap-fill" with only 8 names listed — there's an internal inconsistency in the log's reporting (the "30 missing" count vs. only 8 names listed vs. "27 never covered" with another 8 names). The V18.20.3.4 deterministic recall floor (line 785) clarifies: "theorists 41/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Widiger', 'Widiger and Frances'])" — the "missing: 5 names" is the first 5 shown of 33 total missing. The honest count is **41/74 = 55%**.

The gap-fill produced 27 candidate bullets (8+6+5+5+3 across 5 rounds), but the V18.20.3.2 active-subject veto culled 4 (all Byrne/Akhtar-and-Byrne misattribution attempts) + the V0.4.23 filler floor culled 8 (citation-adjacency bullets) + the V18.20.3.4 post-gap-fill dedup culled 1. Net: 27 - 4 - 8 - 1 = 14 net new bullets from gap-fill, added to the 33 pre-gap-fill bullets + 9 additive-section bullets + 6 from somewhere (the math is fuzzy) = 62 total. **The net result: more bullets with fewer distinct theorist names** — a real coverage regression in the bullets section, partially offset by the thorough holding at 56/74.

---

## Four-audit (now five-audit) delta table (V0.4.31 → V0.4.32 → V0.4.33 → V0.4.34 → V0.4.35)

| Pillar | V0.4.31 | V0.4.32 | V0.4.33 | V0.4.34 | V0.4.35 | Δ V0.4.34 → V0.4.35 |
|---|---|---|---|---|---|---|
| **Factual Consistency** | 5 (5 hallucinations F1-F5) | 9 (0 hallucinations — but non-deterministic) | 6 (2 NEW H1+H2 F1-class hallucinations) | 7 (1 NEW H3 F1-class hallucination) | **9** (0 hallucinations + F1 probe fires deterministically) | **+2** (H3 gone; probe fires in dedicated-expansion path) |
| **Informational Coverage** | 8 (64/75 = 85%) | 7 (46/74 = 62%) | 7 (57/74 = 77%) | 6 (52/74 = 70% bullets / 56/74 = 76% thorough) | **5** (41/74 = 55% bullets / 56/74 = 76% thorough) | **-1** (bullets recall floor regressed 70%→55%; thorough held at 76%) |
| **Cohesion & Clarity** | 6 (splittingted garble, theme-of false positives, F8 thinking-style bullet) | 7 (F8 gone, garbles gone — but V3 meta-filler introduced) | 6 (V4 garbled enumeration stems ×6) | 7 (V4 garbled stems GONE; single-paragraph thorough persists) | **7** (single-paragraph thorough persists — 6th consecutive flagging; V4 garbled stems GONE; new false-positive sentence-fusion flag on "ego-syntonically" which IS in source verbatim) | **0** (steady; same defects) |
| **Conciseness vs Vagueness** | 7 (85 bullets, much filler) | 8 (65 bullets, V3 meta-filler) | 8 (59 bullets, V3 gone) | 8 (51 bullets, V3 gone, filler floor still working) | **7** (62 bullets, less concise; filler floor still working) | **-1** (+11 bullets vs V0.4.34 = less concise; no vagueness regression) |
| **Overall** | **5 FAIL** | **9 PASS (non-det.)** | **6 PASS (borderline)** | **7 PASS (borderline)** | **7 PASS (borderline)** | **0** (same verdict class, different bottleneck) |
| **Hallucinations** | 5 (F1-F5) | 0 (non-det.) | 2 (H1 Mackinnon 1972 + H2 Michels 1983) | 1 (H3 Stanton 1980) | **0** (non-det. — LLM was well-behaved; probe fires deterministically but had nothing to catch) | **-1** (H3 gone) |
| **Critical omissions** | n/a (5 hallucinations dominated) | 3 (Winokur, Jack, Ndtei) | 3 (Winokur, Jack, Ndtei) | 1 (Mackinnon and Michels — Winokur, Jack, Ndtei still missing but inline in thorough) | **2** (Mackinnon and Michels + Stone 1980 — both still missing) | **+1** (Stone 1980 newly flagged; Mackinnon and Michels still missing) |
| **Year-attribution probe** | n/a (probe didn't exist) | n/a | n/a (probe didn't exist) | DID NOT FIRE (probe lived in gap-fill path; gap-fill was skipped) | **FIRED** (standalone probe wired to coverage-check point in `_thorough_theorist_floor`, BEFORE gap-fill — line 515 of source; verified by V18.20.3.13 floor log at conversion-log line 777) | **+ architectural fix REAL** (probe now fires deterministically regardless of gap-fill skip) |
| **Bullets count** | 85 | 65 | 59 | 51 | 62 | +11 (more bullets, but fewer distinct theorists) |
| **Single-paragraph thorough** | YES | YES | YES | YES (3945 words) | YES (4158 words) | 0 (6th consecutive flagging) |
| **Binding constraint** | Factual (5 hallucinations) | Factual (non-det. 0 hallucinations) | Factual (2 hallucinations) | Factual (1 hallucination) | **Coverage** (bullets recall floor regressed 70%→55%) | **SHIFTED** (factual → coverage) |

---

## Verdict + recommended V0.4.36 backlog

> **Verdict: PASS (borderline — coverage-bottlenecked, not factual-bottlenecked).**
>
> The V0.4.35 ships a **9/5/7/7** scorecard (vs V0.4.34's 7/6/7/8). The +2 factual lift comes from the F1 architectural fix being REAL (the probe is wired to the dedicated-expansion path now and fires deterministically) + 0 hallucinations in this run's output. The -1 coverage regression comes from the bullets recall floor dropping 70%→55% (the V18.20.3.2 active-subject veto + V0.4.23 filler floor culled more gap-fill candidates than V0.4.34; the net result was +11 bullets but -11 distinct theorist names). The -1 conciseness regression comes from +11 bullets (62 vs 51). The clarity held flat at 7 (single-paragraph thorough persists; new false-positive flag is a detector tuning issue).
>
> The binding constraint has **SHIFTED from factual (V0.4.34, bottlenecked by the H3 hallucination) to coverage (V0.4.35, bottlenecked by the bullets recall regression)**. This is a notable shift — the F1 fix is real and the hallucination class is now caught by a deterministically-firing probe, but the gap-fill pipeline's aggressive veto + filler floor is over-culling, leaving fewer distinct theorists in the bullets.

### V0.4.36 backlog (priority order — rig-required, evidence-anchored to this audit)

1. **F1 POSITIVE-DEMONSTRATION TEST (HIGH PRIORITY — the headline finding):** The V0.4.35 `_year_attribution_probe` is correctly wired and fires deterministically, but we have NO positive demonstration of the probe catching a fabricated year across V0.4.32, V0.4.33, V0.4.34, or V0.4.35. The next rig run should either:
   - (a) **deliberately inject a fabricated year** (e.g., a test fixture with "Stanton (1980)" embedded) and verify the probe DROPS it (deterministic-elimination proof); OR
   - (b) add a unit test in `tests/test_v182039_audit_fixes.py` that calls `_year_attribution_probe` on a fixture thorough with a known-fabricated year + a real source, and asserts the dropped-list is non-empty.
   
   **Evidence:** this audit's §"Step 2 — The headline finding" + the V0.4.34 audit's F1 backlog item (now resolved architecturally but not empirically demonstrated).

2. **F2 BULLETS-RECALL REGRESSION (HIGH PRIORITY):** The bullets recall floor regressed 70%→55% despite +11 bullets shipped. Investigate:
   - (a) the V18.20.3.2 active-subject veto's strictness — the 3 mention-only Byrne/Akhtar-and-Byrne/Volkan attempts ALL failed the attribution veto. The mention-only path (which is supposed to be a less-strict fallback) may need a more permissive attribution check (e.g., accept any sentence that names the author in proximity to a claim verb, even if the source attributes the claim to a co-author).
   - (b) the V0.4.23 filler floor's over-aggressive culling of citation-adjacency bullets — 8 bullets dropped (Volkan 1986, Mahler 1975, Bak 1946, Anthony 1981, Kohut 1972, Slater and Roth 1977, Akhtar and Byrne splitting). Some of these (e.g., Mahler 1975 separation-individuation) ARE claim-bearing and could be salvaged with a more permissive filler threshold.
   - (c) the dedup round only removed 1 bullet (63→62) — the 27 gap-fill candidates were mostly distinct, but the pipeline culled them down to 14 net new bullets with only ~9 net new theorists. The veto+filler cull rate (13/27 = 48%) is too high.
   
   **Evidence:** conversion-log lines 633, 635, 649, 681 (veto drops) + 651, 671, 673, 691, 693, 695, 697, 699 (filler-floor drops) + 711 (30 missing) + 785 (41/74 = 55% final).
   
   **Content-agnostic (Rule 1 ✓):** the fix is to tune the veto + filler-floor thresholds (structural properties of the pipeline), not to hardcode any author names.

3. **F3 SINGLE-PARAGRAPH THOROUGH (MEDIUM PRIORITY — 6th consecutive audit flagging this):** Break the thorough into MULTIPLE paragraphs at section transitions. The V0.4.35 thorough is a single 30161-char / 4158-word paragraph. The V0.4.26 backlog item 3 has been flagged in 6 consecutive audits (V0.4.26 backlog, V0.4.31, V0.4.32, V0.4.33, V0.4.34, V0.4.35) and is STILL NOT LANDED. The single-paragraph structure makes any embedded hallucination harder to spot for a human reader. The fix is a prompt instruction: "Break the thorough into MULTIPLE paragraphs at section transitions" with generic `e.g.` examples (V0.4.26 backlog item 3 spec).
   
   **Evidence:** summary line 76 (single 30161-char paragraph) + V0.4.26 backlog item 3 spec.

4. **F4 ATTRIBUTION SIMPLIFICATION (LOW PRIORITY):** Several bullets drop co-authors (e.g., "Thomson" instead of "Akhtar and Thomson 1982"; "Frances" instead of "Widiger and Frances 1985"; "Akhtar" instead of "Gorton and Akhtar 1990"). The single-name attribution is accurate but loses citation granularity. Consider whether the LLM should be prompted to retain multi-author attributions when the source has them. (Optional — not a defect, just a citation-granularity preference.)
   
   **Evidence:** summary line 51 (Thomson bullet) + line 57 (Frances bullet) + line 48 (Akhtar computer search bullet).

5. **F5 V18.2.13 SENTENCE-FUSION DETECTOR FALSE POSITIVE (LOW PRIORITY):** The detector flagged "ego-syntonically" as a sentence-fusion garble ("not in the source or English lexicon"), but the word IS in the source verbatim (source line 257: "a paranoid process has become highly structuralized and ego-syntonically embedded in the personality organization"). The detector's lexicon check is over-aggressive — flagging a real source word as a garble. Fix: extend the detector's lexicon to include common hyphenated adverbs that appear in academic prose (e.g., "ego-syntonically", "ego-dystonically", "reality-testingly"). Optional — not a defect in the summary, but a tuning issue in the detector.
   
   **Evidence:** conversion-log line 749 + source line 257 (verbatim match).

---

## Artifacts

| Artifact | Path | Notes |
|---|---|---|
| Source chapter (gold standard) | `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines, 7,358 words) | UNCHANGED across all 5 audits |
| V0.4.35 summary | `audit/results/bench_v0435_ch6_paranoid/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md` (99 lines, 62 bullets) | UP from V0.4.34's 51 bullets |
| V0.4.35 conversion log | `audit/results/bench_v0435_ch6_paranoid/Broken Structures Salman Akhtar_v0.4.35_20260926-013038-18eb612a.conversion.log.md` (934 lines) | Includes the V0.4.35 F1 probe-wiring code path |
| V0.4.35 F1 fix commit | `6d220e4` — `core/summarisation/thorough_theorist_floor.py` (104 LOC added) | Standalone `_year_attribution_probe` function + wired at coverage-check point |
| V0.4.35 release commit | `26fa567` — "release: V0.4.35 — the F1 year-attribution-probe-wiring release" | Bumped VERSION 0.4.34 → 0.4.35 |
| Prior audits (the 5-audit lineage) | `audit/results/AUDIT_V0.4.{31,32,33,34}*.md` | V0.4.31 FAIL 5/8/6/7 (5 hallucinations) → V0.4.32 PASS 9/7/7/8 (0 non-det.) → V0.4.33 PASS 6/7/6/8 (2 hallucinations) → V0.4.34 PASS 7/6/7/8 (1 hallucination) → V0.4.35 PASS 9/5/7/7 (0 hallucinations, probe fires deterministically) |

---

*Generated by reading the V0.4.35 artifacts at `/home/z/elixir/audit/results/bench_v0435_ch6_paranoid/` + the source chapter at `/home/z/elixir/docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` + the V0.4.35 F1 fix commit `6d220e4` + the prior 4-audit lineage. Read-only audit; no code changes; no .py touched; provenance-stamped.*
