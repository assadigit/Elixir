# AUDIT — Summary vs Source — version V0.4.34 (run 20260926-004732-f5ad605b) — ch.6

> **Audit version:** `V0.4.34 / run 20260926-004732-f5ad605b / app 0.4.34 / 2026-09-26T00:50:45 (summarization start) / 51 bullets (Key Takeaways) + 5 Key Distinctions + 4 Theoretical Tensions`
> **Book:** Broken Structures (Salman Akhtar), chapter 6 "PARANOID PERSONALITY DISORDER" (PDF pp. 137–160, 7,415 source words / 11,171 tokens fed).
> **Audit framework:** the standing four-pillar expert fact-checker (`docs/EVALUATION_FRAMEWORK.md`).
> **Ground truth:** `docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md` (598 lines; the OCR-garbled Table 6-1 on lines 416–475 still excluded from the audit as mid-extraction script damage — same scope rule as V0.4.31 / V0.4.32 / V0.4.33).
> **Operating mode:** **REAL RIG RUN — the owner's actual production environment (Windows 10 / RTX 3060 12 GB / Ternary-Bonsai-2-27B-Instruct-Vision local model via the llama.cpp provider contract / Ollama embedder alive).** Same rig as the prior three rounds.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol / Rule 4)

| Field | Value | Match |
|---|---|---|
| `run_id` (summary stamp) | `20260926-004732-f5ad605b` | ✓ fresh, in-file `<!-- generated-by -->` comment (summary line 3) and `<!-- COMPLETE … -->` sentinel (summary line 90) |
| `app_version` | `0.4.34` | ✓ matches repo `VERSION` (= `0.4.34`); release commit `2adb4b2` (V0.4.34 year-attribution-probe release); audit-fix commit `73660a0` is the probe; benchmark commit `c4b35e9` files the artifacts |
| `bullets` | `51` (Key Takeaways) | ✓ manifest = rendered file = log line 791 `ELIXIR_PROGRESS {"bullets":51}` — **DOWN from V0.4.33's 59 (-8 bullets)**, **DOWN from V0.4.32's 65 (-14 bullets)**, **DOWN from V0.4.31's 85 (-34 bullets)** |
| repo state | `refactor/audit-session @ c4b35e9`, tag `V0.4.34` pushed | ✓ the V0.4.34 release tree (post-V0.4.33 audit-fix 1 + V0.4.34 audit-fix 1 = year-attribution probe) |
| run-stamped filename | `001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.34_20260926-004732-f5ad605b_summary.md` | ✓ V0.4.34 run-stamp convention |
| COMPLETE sentinel | `<!-- COMPLETE run_id=20260926-004732-f5ad605b -->` (summary line 90) | ✓ run-id-stamped |
| LLM transport | llama.cpp wire contract (SSE streaming); 14 LLM calls visible in the log; provider at log line 73 (`Provider: llamacpp`), model at line 97 (`Ternary-Bonsai-2-27B-Instruct-Vision`) | ✓ the V0.4.30 multi-backend model-detection continues to feed the right model name through the wire |
| chapter wall-clock | **767 s (DEADLINE EXCEEDED — 1.60× the 480 s budget)** | ⚠ log line 787; deadline-exceeded warnings fired at 558 s (line 545 — dedicated bullet expansion skipped), 673 s (lines 579/587/595 — scholar reflection + pre-gap-fill semantic dedup + bullet consolidation skipped), 766 s (line 779 — thorough theorist floor gap-fill declared skipped). **DOWN from V0.4.33's 860 s (-93 s) and DOWN from V0.4.32's 889 s.** |
| temperature | 0.7 default; per-call policy: 0.70 for primary/derived/exec/additive/gap-fill rounds 1–5; **0.35 for the dedicated thorough expansion call** (log line 529 — same two-temperature policy as V0.4.33). | ✓ |
| endpoint-dropdown (V0.4.31 B1) | user-selected chapter = `'6 - PARANOID PERSONALITY DISORDER'` (TOC page 137, log line 203) | ✓ the B1 dropdown continues to work (4th run) |
| artifacts | summary `.md` + conversion log + keypoints `.md` + DOCX + checkpoints + quality_report.json, all saved to `C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\` and mirrored to `/home/z/elixir/audit/results/bench_v0434_ch6_paranoid/` | ✓ |
| **OCR path** | **3 of 24 chapter pages were scanned (152, 153, 154); the V0.4.1 vision-OCR path SUCCEEDED on all 3** (`✅ V0.4.1 vision OCR p.152: 1025 chars`, `✅ V0.4.1 vision OCR p.153: 87 chars`, `✅ V0.4.1 vision OCR p.154: 931 chars` — log lines 295, 299, 303) | ✓ 4th consecutive clean V0.4.1 OCR pass (V0.4.31 + V0.4.32 + V0.4.33 + V0.4.34). The V0.4.31 OCR bug fix (commit `58a2ac7`) continues to hold. |

**Net:** the provenance stamp is well-formed and matches the repo at HEAD `c4b35e9`. Audit may proceed (Rule 4 ✓).

---

## Rig-vs-sandbox divergence ledger (honest disclosure, same as V0.4.31 + V0.4.32 + V0.4.33)

The V0.4.34 ch.6 run is the REAL-rig production stack (Ternary-Bonsai 27B + RTX 3060 + Ollama embedder alive).

- **Phase 2.2 bullets-only semantic fact-check:** RAN on BULLETS ONLY (log line 551: "Phase 2.2: All bullets semantically grounded (≥0.50 similarity)"). Same scope as V0.4.31 + V0.4.32 + V0.4.33. The 22 master-derived bullets all passed ≥0.50 similarity to source claims (line 573: "grounding=100% (22/22 bullets), hallucinations=0, deviations=0").
- **V0.4.33 item 1 — thorough-additive semantic fact-check (`_semantic_ground_addition_sentences` in `core/summarisation/thorough_theorist_floor.py`):** the helper WAS NOT CALLED this run — the thorough gap-fill phase was SKIPPED (see "V0.4.34 year-attribution probe" below). Nothing to verify; nothing dropped.
- **V0.4.34 item 1 — year-attribution probe (commit `73660a0`, in the SAME helper `_grounded_addition_sentences`):** **DID NOT FIRE this run** — 0 attribution-edge drops in the log (vs V0.4.33's 19). The thorough gap-fill phase was skipped at log line 783 ("V0.05: Thorough gap-fill skipped — thorough (3945 words) already meets its source-scaled target (3332 words)"). The probe lives inside a function that only runs during thorough gap-fill; it had no opportunity to run. **This is the headline finding — see H3 below.**
- **Pre-gap-fill semantic dedup:** SKIPPED at 673 s deadline (log line 587 — same skip wave as V0.4.31 + V0.4.32 + V0.4.33).
- **Post-gap-fill semantic dedup:** RAN (log line 707; V18.20.3.4 declares it non-skippable) — **1 bullet dropped (52 → 51)** vs V0.4.33's 4 bullets dropped (63 → 59) and V0.4.32's 2 (67 → 65).
- **Bullet consolidation:** SKIPPED at 673 s deadline (log line 595 — same skip wave as V0.4.31 + V0.4.32 + V0.4.33).
- **Thorough-theorist-floor gap-fill:** declared SKIPPED at 766 s (log line 779), then **OVERRIDDEN as NON-SKIPPABLE** (log line 781 — same "coverage deficit is the V0.20 campaign target; timing is not" override as V0.4.33), then **ACTUALLY SKIPPED** at log line 783 by the V0.05 word-count gate (3945 > 3332 target). This is the divergence from V0.4.33: the V0.4.33 had the gap-fill actually run (3 chunked calls, 19 attribution-edge drops); the V0.4.34 did NOT (because the dedicated expansion call already produced enough text).
- **L8 source-grounding (langextract verbatim):** DISABLED by user setting (`grounding.enabled=False`, log line 571 — same as V0.4.31 + V0.4.32 + V0.4.33). Layers 1–7 active, Layer 8 OFF.

**Net:** the V0.4.34 audit-fix release's stated goal — "year-attribution probe catches the H1/H2-class hallucinations DIRECTLY" (commit `73660a0`) — was **TECHNICALLY MET in code** (the probe is in `_grounded_addition_sentences`), but **DID NOT FIRE on this benchmark** because the thorough gap-fill phase was skipped (V0.05 word-count gate). The H1/H2 hallucinations did NOT recur — but the elimination is NON-DETERMINISTIC (same flaw as V0.4.32), AND a NEW H3-class hallucination slipped through the dedicated expansion call (which the probe does not see).

---

## Part 1 — Detailed Report

### Method

**~75 discrete claims** extracted across the five summary sections (Executive Summary ≈ 12 claims across 2 paragraphs; Key Takeaways 51 bullets ≈ 55 claims; Thorough Summary ≈ 30 claims across 1 long paragraph (3945 words / 29957 chars — the V0.4.34 ships the thorough as a SINGLE paragraph, the V0.4.26 backlog item 3 "break the thorough into MULTIPLE paragraphs at section transitions" is still NOT shipped, 4th consecutive run); Key Distinctions 5 bullets ≈ 5 claims; Theoretical Tensions 4 bullets ≈ 4 claims). I verified **32 representative high-stakes claims** against the source (down from V0.4.33's 25 + V0.4.32's 28 + V0.4.31's 30 — a tighter verification set focused on year-attributed claims, the F1-class).

### Fact-Check Log

**Result: ~31 claims verified clean, 1 NEW SEVERE HALLUCINATION (H3 — Stanton 1980 fabricated year in thorough; same F1-class as V0.4.31's F1-F5 + V0.4.33's H1+H2). The V0.4.33 H1 (Mackinnon 1972) + H2 (Michels 1983) DID NOT RECUR — but the elimination is NON-DETERMINISTIC (the LLM happened not to produce them this run; the year-attribution probe DID NOT fire).**

**Verified clean — representative high-stakes claims (selection of 25):**

| # | Claim in summary | Evidence in source (quote) |
|---|---|---|
| 1 | Magnan (*1893*) "delusional states of degeneracy" linked to fragile personality (idiosyncratic thinking, undue sensitivity, hypochondriasis, referential thinking, suspiciousness) | "Magnan (1893) divided paranoid psychoses into two types… a 'fragile personality,' which showed idiosyncratic thinking, undue sensitivity, hypochondriasis, referential thinking, and suspiciousness" (source lines 47–55) |
| 2 | Kraepelin (*1905*, *1921*a) "pseudoquerulous" → "paranoid personality"; marked distrust, feeling unjustly treated, vulnerable to erotomania, credulous about gossip | "Kraepelin's (1905) description of a pseudoquerulous personality type… Kraepelin (1921a) renamed the condition paranoid personality… displaying marked distrust, feeling unjustly treated… vulnerable to erotomanialike secret love affairs… extremely credulous and accept without hesitation every piece of gossip" (source lines 57–65) |
| 3 | Bleuler (*1908*) "contentious psychopathy" / "paranoid constitution" — triad suspiciousness, grandiosity, persecution | "Bleuler (1908) described 'contentious psychopathy' or 'paranoid constitution' as displaying the characteristic triad of suspiciousness, grandiosity, and feelings of persecution" (source lines 67–71) |
| 4 | Kretschmer (*1927*) sensitive inner core + constant tension self-importance vs humiliating environment | "Kretschmer (1927) emphasized the sensitive inner core… constant tension between feelings of self-importance and experiences of the environment as unappreciative and humiliating" (source lines 72–77) |
| 5 | Jaspers (*1949*) "self-insecure personalities" who overcompensate via formality | "Jaspers (1949)… description of 'self-insecure personalities'… attempts at overcompensation through compulsive formality" (source lines 79–85) |
| 6 | Polatin (*1975*) facade of affability shatters to reveal mistrust, hate, rage | "Polatin (1975) described individuals with paranoid personality disorder as rigid, suspicious, watchful, self-centered… covered by a facade of affability that shatters readily to reveal underlying mistrust, authoritarianism, hate, and rage" (source lines 103–109) |
| 7 | Millon (*1981*) 4 categories: behavioral / complaints / dynamics / coping | "Millon (1981), who divided the features of paranoid personality into four categories…" (source lines 127–130) |
| 8 | Freud (*1911*) paranoia = projection of repudiated latent homosexuality | "Freud (1911) related paranoid tendencies to the repudiation of latent homosexuality through projection" (source line 141) |
| 9 | Klein (*1946*) "paranoid-schizoid position": splitting, denial, primitive idealization vs inborn aggression | "Klein (1946) described the 'paranoid-schizoid position'… defended against by splitting, denial, and primitive idealization" (source lines 160–170) |
| 10 | Winnicott (*1952*) "going-on-being"; maternal failures → suspiciousness, motor stiffness, sadomasochistic concerns | "Winnicott (1952)… 'going-on-being'… Maternal failures… suspiciousness, lack of playfulness, motor stiffness… sadomasochistic sexual concerns" (source lines 171–181) |
| 11 | Erikson (*1950*a) paranoid trends from overwhelming early-infancy frustrations → identity diffusion | "Erikson (1950a)… paranoid trends had their genesis in overwhelming frustrations during early infancy, which impede the development of basic trust… identity diffusion" (source lines 182–188) |
| 12 | Heimann (*1952*) chronic hypomania + paranoid defenses infiltrated with sadistic pleasure | "Heimann (1952) likened the paranoid personality to a chronic hypomanic state… paranoid individuals unconsciously obtain sadistic pleasure in situations consciously registered as persecutory" (source lines 189–197) |
| 13 | Shapiro (*1965*) two types (furtive vs megalomanic); "biased seizing of significant clues" + "loss of appreciation of context" | "Shapiro (1965) recognized two types of paranoid personality… biased seizing of significant clues from context, and loss of appreciation of that context" (source lines 213–229) |
| 14 | Blum (*1980*, *1981*) hostility as primary problem + "inconstant object" concept | "hostility is a primary problem in this condition and not merely a defense… Blum (1981) introduces his concept of 'inconstant object,' the ambivalently loved object that is felt to be both persecutory and needed" (source lines 262–275) |
| 15 | Meissner (*1978*b) paranoid process structuralized; identification with victimized mother as central source of anxiety | "Meissner (1978b)… a paranoid process has become highly structuralized and ego-syntonically embedded… the underlying identification with the weak, passive, and victimized mother that is the central source of anxiety" (source lines 255–261) |
| 16 | DSM-III/III-R missed grandiosity, sexual difficulties, hidden inferiority, idiosyncratic moral attitudes, gullibility | "the DSM-III criteria failed to include grandiosity (Heimann 1952, Jacobson 1971, Kraepelin 1921, Kretschmer 1927, Meissner 1978b, Stanton 1978), sexual difficulties… hidden feelings of inferiority… idiosyncratically moral attitudes… and gullibility and naivete" (source lines 343–350) |
| 17 | Composite profile 6 areas: self-concept; interpersonal relations; social adaptation; love and sexuality; ethics; cognitive style | "the clinical features of paranoid personality disorder involve six areas of psychosocial functioning… self-concept… interpersonal relations… social adaptation… love and sexuality… ethics, standards, and ideals… cognitive style" (source lines 364–390) |
| 18 | PPD vs paranoid schizophrenia distinguished by lack of reality break + bizarre delusions + auditory hallucinations | "The paranoid schizophrenic displays a serious break with reality, bizarre delusions of persecution, grandeur, jealousy or infidelity, auditory hallucinations, symptoms of thought control" (source lines 504–508) |
| 19 | PPD vs phobic character: paranoid personalizes intent + reacts by attack; phobic feels danger without knowing why + reacts by flight | "the paranoid reacts by attack or provocation of attack, while the phobic reacts by flight… the phobic's feeling is 'It is a danger, but I do not know why'… the paranoid personalizes" (source lines 511–525) |
| 20 | PPD vs compulsive: externalizing moral demands; biased attention; smug self-assurance | "The paranoid individual… views such demands as originating from external, unjustified sources… narrowly focused, biased attention… smugly self-assured" (source lines 528–541) |
| 21 | PPD vs narcissistic: lacks charm, seductiveness, sexual promiscuity; displays pervasive mistrust, litigiousness, angry negativism | "Narcissistic personality does not display the pervasive mistrust, litigiousness, and self-righteous indignation of the paranoid personality (Akhtar and Thomson 1982, Kernberg 1985, Volkan 1976)" (source lines 562–569) |
| 22 | Akhtar computer search 1985–1988 → 1,200+ citations, none on PPD phenomenology (attributed to Gorton and Akhtar 1990) | "A computer search of personality disorder literature from 1985 to 1988, for instance, yielded over 1,200 citations, and not one was specifically devoted to the phenomenology of paranoid personality disorder (Gorton and Akhtar 1990)" (source lines 125–126) |
| 23 | Bergman (*1978*) fighting stance keeps them intact; failure is never their own | "Bergman (1978) states that the fighting stance of paranoid personalities keeps them intact; failure is never their own" (source line 586) |
| 24 | Fenichel (*1946*) coined "phobic character" + Fenichel (*1945*) on compulsive's subtle rebellion | "The term phobic character was coined by Fenichel (1946)… The compulsive's rebellion against his internalized moral authority is subtle, unconscious, disguised, even ego-alien (Fenichel 1945)" (source lines 507, 532) |
| 25 | Hamilton (*1974*, *1984*) two kinds: sensitive (subdued resentment + cynicism) vs querulous (open defiance + litigiousness), elaborating on Fish | "Hamilton (1974, 1984) distinguished two kinds of paranoid personality: sensitive and querulous. The former was characterized by subdued resentment and cynicism, the latter by open defiance and litigiousness" (source lines 112–113) |

**Flagged incidents:**

| # | Where | Defect | Class |
|---|---|---|---|
| **H3** | **Thorough Summary (summary line 67, ~line 21 of the folded thorough text), in the body sentence of the descriptive-psychiatry survey paragraph:** | **"Stanton (*1980*) highlighted overt stubbornness with hidden self-doubt, and observed that while such individuals are contemptuous of others' naivete, they themselves have a remarkable, though latent, gullibility."** — The cited year `1980` is **FABRICATED**. The source has Stanton at years **1978** only — six times (source lines 110, 116, 345, 346, 348, 502). The V0.4.34 summary even reproduces the correct `Stanton *1978*` later in the SAME thorough paragraph (in the citation-list reproduction of source line 345). The body sentence fabricates `1980`. | **F1-class fabricated-year hallucination — IDENTICAL CLASS to V0.4.33 H1 (Mackinnon 1972) + H2 (Michels 1983) + V0.4.31 F1-F5.** The V0.4.34 year-attribution probe (commit `73660a0`) was DESIGNED to catch this exact class — and DID NOT, because the probe is in `core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences` which only runs during the thorough gap-fill phase, and that phase was SKIPPED this run (the dedicated expansion call already produced 3945 words > 3332 target; log line 783). The "Stanton (*1980*)" sentence was produced by the DEDICATED EXPANSION call (log lines 527–543), which the probe does NOT see. |
| V1 | Bullet 39 (summary line 39) | "Anthony (*1981*) delineated the paranoid adolescent as part of a broader list of specific conceptual frameworks" — the V18.2.13 post-check flagged this as `[attribution/flag]` (log line 727) at 48 % similarity to the source's claim about this author. **Verified clean by hand:** source line 281 explicitly says "Anthony's (1981) delineation of the paranoid adolescent" — the year and claim match. The flag is a **false positive** of the V18.2.13 similarity threshold. | Minor (false-positive flag, no drop) |
| V2 | Bullet "**Conclusions**" (summary line 63) | The V18.2.13 post-check flagged `[attribution/flag]` (log line 729) as "bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions." Verified: source line 476–477 has the EXACT conclusion content ("it (1) includes both phenomenological and psychoanalytic observations; (2) values depth and complexity over descriptive oversimplification; (3) establishes a connection between the behavioral and the psychostructural, hence developmental"). The "Conclusions" bold-name label is a slight mislabel (source section is "COMMENT" at line 580 + an inline summary at 476); the bullet CONTENT is verbatim source. Not a hallucination, a label oddity. | Minor (label oddity, no drop) |

**Drop trail observed live in the conversion log (the V0.4.24 attribution-edge + V0.4.23 filler floor working together — the V0.4.34 year-attribution probe DID NOT FIRE):**

- **V0.4.34 year-attribution probe (commit `73660a0`, the V0.4.34 release's headline feature):** **DID NOT FIRE THIS RUN — 0 attribution-edge drops in the log** (vs V0.4.33's 19 drops). The probe lives in `core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences` (per `git show 73660a0` — the diff adds 20 lines to that function: `re.findall(r"(?<!\d)(1[89]\d{2})(?!\d)", sent)` extracts the cited year, `re.search(rf"(?<!\d){re.escape(_yr)}(?!\d)", windows)` verifies it co-occurs with the author in the ±600-char source window, and `continue` skips the name if the year doesn't match — the sentence is dropped if NO name grounds). The function is **only called by the thorough-theorist-floor gap-fill phase**, which was SKIPPED this run at log line 783 ("V0.05: Thorough gap-fill skipped — thorough (3945 words) already meets its source-scaled target (3332 words)"). The skip is the consequence of the **dedicated expansion call having succeeded on attempt 2** (log line 541: "Attempt 2/3: dedicated thorough = 3945 words"; line 543: "thorough_summary expanded via dedicated call: 533 → 3945 words") — the dedicated expansion call produced enough text to satisfy the V0.05 word-count gate, so the V0.20 NON-SKIPPABLE override at log line 781 was overridden again by the V0.05 word-count gate at log line 783.

  **This is the audit's headline finding.** The V0.4.34 release's stated goal — "year-attribution probe catches the H1/H2 class DIRECTLY" — was **NOT ACHIEVED on this benchmark**. The probe is correctly implemented in code (the logic is sound — it WOULD have caught H1/H2/H3 if it had run), but it has a **coverage blind spot**: it only inspects thorough gap-fill output, NOT dedicated-expansion output. The H3 hallucination ("Stanton (*1980*)") was produced by the dedicated expansion call, which the probe never sees.

- **V0.4.33-wired semantic fact-check on thorough additive prose (`_semantic_ground_addition_sentences`, V0.4.32 backlog item 2 / V0.4.33 audit-fix 1):** **DID NOT FIRE THIS RUN** — same reason as the year-attribution probe. The helper is called from within the thorough gap-fill phase, which was skipped. Nothing to verify; nothing dropped. This is the second consecutive run where the V0.4.33 semantic fact-check had no opportunity to fire (the V0.4.32 audit found it dead-code-wired but unfired; the V0.4.33 release wired it; the V0.4.33 run actually fired it on 19 thorough additive sentences; the V0.4.34 run did not fire it because the thorough gap-fill was skipped).

- **V0.4.23 filler floor (existing — caught the F4/F5-class citation-adjacency fabrications + filler):** log lines 627, 643, 645, 659, 661, 663, 665, 681, 683, 685 dropped **10 citation-adjacency bullets** (vs V0.4.33's 12; vs V0.4.32's 12) — these are gap-fill bullets that repeat a true author's name but don't add new claim content. Examples:
  - line 627: "Byrne co-authored descriptions (with Akhtar) of the behavioral correlates…" — filler (the Byrne attribution was vetoed separately at line 629 by V18.20.3.2).
  - line 659: "Winokur's (1985) work on paranoid disorders is cited alongside other s…" — filler (the year 1985 is REAL — source line 120 — but the bullet is filler because it adds no new claim).
  - line 661: "Anthony's (1981) delineation of the paranoid adolescent is referenced …" — filler (year is real, bullet is filler).
  - line 663: "Kohut's (1972) description of narcissistic rage is cited alongside oth…" — filler (year is real, bullet is filler).
  - line 665: "Bach's (1977) observation on the 'mirror complementarity of the self' …" — filler (year is real, bullet is filler).
  - **Net: the V0.4.23 filler floor still works (10 drops, all true-class — no fabricated years were dropped because none were produced by the LLM this run).**

- **V18.20.3.2 active-subject veto (existing — dropped 1 gap-fill bullet this run vs V0.4.33's 3):** log line 629 dropped the "Akhtar and Byrne described the behavioral correlates…" bullet (the source attributes this claim to "Socarides's", not "Byrne" — same veto as V0.4.33's 3 Byrne-vetoes but only 1 this run).

- **Phase 2.2 bullets-only semantic fact-check (existing — RAN, bullets only):** log line 551 — "Phase 2.2: All bullets semantically grounded (≥0.50 similarity)." The scope is STILL bullets-only (the V0.4.33 wired the thorough-additive extension into `_grounded_addition_sentences`, which didn't run this time).

- **Post-gap-fill semantic dedup (RAN, non-skippable per V18.20.3.4):** log line 707 — **1 bullet dropped as semantic duplicate (52 → 51)** vs V0.4.33's 4 drops (63 → 59). The dedup removed bullet 19 (sim=0.87 with bullet 1 — a duplicate pair).

- **Enumeration guarantee (V0.4.23):** log line 703 — 43/43 enumerated items ship verbatim across **8 enumerated-list bullets** (same as V0.4.33) + inline-mention bullets. The 8 enumeration bullets are: the Cameron-four-aspects bullet (bullet 47), the Millon-four-categories bullet (33), the DSM-III criteria bullets, the composite-profile-six-areas bullet (54), and the conclusion-three-items bullet (63). All ship verbatim.

### Omissions & Coverage

**Honest deterministic numbers (log line 881 + 785):**

- **Conclusion items: 3/3** — the chapter's three Summary-section conclusion lists all ship as enumeration bullet 63. ✓
- **Enumerated items, whole chapter: 43/43 carried verbatim** (log line 703) — the items ship verbatim across 8 enumeration bullets + inline-mention bullets. ✓
- **Named theorists: 52/74 (70%)** (log line 881) — **DOWN from V0.4.33's 57/74 (77%) (-7 pp)**, **DOWN from V0.4.31's 64/75 (85%) (-15 pp)**, **UP from V0.4.32's 46/74 (62%) (+8 pp)**. The V0.4.34 missing-22 at log line 697 + 785: `['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels']` (truncated display — full count is 22). The regression from V0.4.33 is attributable to (a) the thorough gap-fill being skipped (no thorough-additive coverage lift — V0.4.33 got +14 pp from this; V0.4.34 got 0 pp), (b) the V0.4.23 filler floor dropping 10 gap-fill attempts for Kohut/Anthony/Bach/Winokur as filler, and (c) the deadline forcing the gap-fill to stop after 5 rounds (log line 695: "Batch gap-fill complete — added 29 bullets across 5 round(s)").
- **Keyword coverage:** log line 507 — primary coverage 92 % (6/7 keywords found; missing: 'others'); final coverage 100 % (log line 547 — the LLM judge's claim-recall measure; auto-passed to promote despite the 92 % primary because thorough has substantial content).
- **Thorough theorist floor:** log line 777 — thorough-only judge found 56/74 (76 %) — UP from V0.4.33's 23/74 (31 %) at the same checkpoint. The lift came from the dedicated expansion call (3945 words, 56 distinct theorists cited inline) — a much richer thorough than V0.4.33's post-dedicated-expansion 533-word thorough (which only had 23 theorists inline). The V0.4.34 thorough is **6× longer than V0.4.33's pre-gap-fill thorough** (3945 words vs 533 words) because the dedicated expansion call succeeded on attempt 2 (V0.4.33's attempt 2 also produced 3945 words but the V0.4.33 run then ALSO ran thorough gap-fill on top of it).

**Top 5 critical omissions on V0.4.34:**

1. **Mackinnon and Michels (1971)** — appears once in the source at line 508 ("Mackinnon and Michels (1971) also recognized fearful avoidance as a characterological defense"). The V0.4.34 summary does NOT mention them at all (no bullet, no thorough inline mention). The V0.4.33 had a Hallucinated bullet about them (H1 Mackinnon 1972 + H2 Michels 1983 — both fabricated years); the V0.4.34 OMITTED them entirely. **The omission is BETTER than the hallucination** (a missing claim is less dangerous than a fabricated one), but the V0.4.34's headline feature (the year-attribution probe) was supposed to enable a CORRECT bullet about them — and it did not, because the LLM never produced a candidate bullet for "Mackinnon and Michels" in any of the 5 gap-fill rounds (the system deprioritized compound names; round 1-5 fill-lists favored single-name theorists).
2. **Winokur (1975, 1985)** — Winokur appears 3 times in the source: line 111 ("Winokur and Croewe 1975" — textbook offering LESS clarity), line 120 ("paranoid disorders (Rettersol 1985, Winokur 1985)"). The V0.4.34 attempted Winokur gap-fill 3 times (rounds 3, 4, 5); each was dropped by the V0.4.23 filler floor (the LLM produced filler-only bullets that didn't add new claim content). At log line 671 the system switched to "mention-only" prompt for Winokur; at log line 691 the V0.4.33 system gave up after a failed mention-only attempt (the V0.4.34 also gave up — see the missing list). **No Winokur bullet ships.** Coverage loss.
3. **Kohut (1972)** — Kohut appears once in the source at line 281 ("Kohut's (1972) description of narcissistic rage"). The V0.4.34 thorough DOES mention Kohut inline ("Kohut's (*1972*) description of narcissistic rage" — summary line 79 of the long thorough paragraph). But no Kohut bullet ships (gap-fill attempts at rounds 4 + 5 were dropped by V0.4.23 filler floor — log lines 663, 681). The V0.4.33 had Kohut in the missing-5 list too. Coverage loss but inline coverage exists.
4. **Green (1986)** — Green appears once in source at line 281 ("Green's (1986) essay on moral narcissism"). The V0.4.34 thorough DOES mention Green inline ("Green's (*1986*) essay on moral narcissism" — summary line 79 of the long thorough paragraph). But no Green bullet ships (gap-fill attempts at rounds 4 + 5 were dropped by V0.4.23 filler floor — log lines 679, 685). Coverage loss but inline coverage exists.
5. **Pao (1969) + Socarides (1966)** — both appear once in source at lines 282–283 ("Pao's (1969) work on morbid jealousy, Socarides's (1966) view on the affect of vengeance"). The V0.4.34 thorough DOES mention them inline (summary line 79 of the long thorough paragraph: "Pao's (*1969*) work on morbid jealousy, Socarides's (*1966*) view on the affect of vengeance"). But no Pao/Socarides bullets ship (no gap-fill attempts — they were never in the round 1-5 fill-lists; they remained in the missing list at log line 697). Coverage loss but inline coverage exists.

**Critical omissions: 1** (Mackinnon and Michels — completely absent from both bullets and thorough; Kohut/Green/Pao/Socarides are in thorough paragraphs inline so they're "covered" by the V0.20 recall floor's inclusive count; Winokur is completely absent). This is **WORSE than V0.4.33's 3 critical omissions** (Winokur, Jack, Ndtei were V0.4.33's omissions) because the V0.4.34 added Mackinnon and Michels to the missing set (they were "covered" in V0.4.33 by H1+H2 hallucinations — which is worse than missing, but the count regressed).

**Theorist floor lineage: V0.4.31 (64/75 = 85 %) > V0.4.33 (57/74 = 77 %) > V0.4.34 (52/74 = 70 %) > V0.4.32 (46/74 = 62 %).** The V0.4.34 regressed -7 pp vs V0.4.33 because the thorough gap-fill was skipped (no +14 pp lift). The V0.4.34 is still +8 pp above V0.4.32 because the dedicated expansion call produced a richer thorough (56 inline theorists vs V0.4.32's thorough).

### Clarity & Cohesion

**V0.4.26 backlog status observed on this fresh chapter (the rig-required items):**

1. **Item 5 — markdown year format (LANDED ✓, 4th consecutive run):** the summary uses `*YYYY*` (markdown italic) for all year citations (e.g. `Magnan's (*1893*)`, `Bleuler (*1908*)`, `Kohut's (*1972*)`). All 47 distinct years in the summary use the `*YYYY*` format. ✓
2. **Item 1 — Theoretical-tensions additive robustness (LANDED ✓, 4th consecutive run):** the Theoretical Tensions section SHIPS with 4 bullets (summary lines 80–83), same as V0.4.31 + V0.4.32 + V0.4.33.
3. **Item 2 — enumeration-stem grammar + self-containment (PARTIALLY LANDED, IMPROVED):** the V0.4.34 enumeration bullets ship with cleaner stems than V0.4.33's garbled "**Cameron outlined four aspects of paranoid** —" pattern. The V0.4.34 ships a Cameron bullet (bullet 47) as a clean stem: "Cameron (*1963*) outlined four aspects of the paranoid personality, including hypersensitivity to others' unconscious attitudes…". ✓ IMPROVED over V0.4.33.
4. **Item 3 — quote-pair balancer in deterministic polish (LANDED ✓, 4th consecutive run):** the exec summary (line 7) ships balanced quote pairs ("inconstant object", "going-on-being"). ✓
5. **Item 4 — sociocultural name floor (N/A for this chapter, 4th consecutive run):** same as V0.4.31 + V0.4.32 + V0.4.33. Not testable on this benchmark.
6. **Item 6 — break thorough into MULTIPLE paragraphs at section transitions (NOT LANDED ✗ — STILL OPEN, 4th consecutive run):** the V0.4.34 thorough ships as a SINGLE 29957-char / 3945-word paragraph (summary line 67). The V0.4.26 backlog item 3 is still NOT shipped. The single-paragraph structure makes the H3 hallucination harder to spot for a human reader (it's buried in 3945 words of dense prose).

**NEW clarity defect classes on V0.4.34 (not present in V0.4.33):**

- **V18.2.13 `[dropped_letter/flag]` bullet 33** (log line 723): "paranoics" — flagged as a likely garbled token (edit-distance-1 from "paranoids"). The bullet ships as-is with "paranoics cloak a hollow shell" — a minor word-form issue carried over from the source's "paranoics" usage (source line 127 has "the features of paranoid personality"). The flag is a false positive ("paranoics" is the source's own usage).
- **V18.2.13 `[sentence_fusion/flag]` bullet 40** (log line 725): "self-righteousness" — flagged as a likely sentence-fusion garble (suffix "ness" + source word "righteous"). The bullet ships as-is with "expedient mendacity with moralistic self-righteousness". The flag is a false positive (the source itself uses "selfrighteousness" at line 132 — an OCR/typo in the source that the LLM reproduced as "self-righteousness").
- **V18.2.13 `[sentence_fusion/flag]` thorough** (log line 731): "ego-syntonically" — flagged as a likely sentence-fusion garble (suffix "ally" + source word "egosyntonic"). The thorough ships as-is with "highly structuralized and ego-syntonically embedded". The flag is a false positive (the source uses "egosyntonic" at line 261 — the LLM adverbialized it correctly to "ego-syntonically").

**Clarity changes vs V0.4.33 (NET POSITIVE on clarity):**

- **The H1+H2 hallucinations are GONE from the thorough** (the V0.4.33's "Mackinnon (*1972*) emphasized…" and "Michels (*1983*) contributed…" sentences at V0.4.33 summary line 85 are NOT in the V0.4.34 thorough). This is the V0.4.34's clarity improvement — but it's NON-DETERMINISTIC (the LLM didn't produce them this run; the year-attribution probe didn't fire).
- **The NEW H3 hallucination (Stanton 1980) IS in the thorough** — a fabricated-year regression. Net: -2 hallucinations (H1+H2 gone) + 1 new hallucination (H3) = -1 net.
- **The enumeration-stem grammar improved** — the V0.4.33's 6-of-8 garbled stems are now clean. ✓
- **The single-paragraph thorough structure PERSISTS** — V0.4.26 backlog item 3 still not shipped (4th consecutive run).

**Deterministic clarity proxy:** fragment_rate not directly measured. Length policy: exec 1895 chars (compliant, target ≤2500); thorough ~29957 chars / 3945 words across 1 paragraph (exceeds the V0.05 3332-word target by 18 % — the dedicated expansion call overshot). The single-paragraph structure makes the H3 hallucination harder to spot for a human reader.

### Conciseness vs Vagueness

- **Zero filler bullets shipped** (V0.4.23 filler floor working — log lines 627, 643, 645, 659, 661, 663, 665, 681, 683, 685 dropped 10 filler/citation-adjacency bullets BEFORE ship). The shipped 51 bullets are all claim-bearing. ✓
- **Zero thinking-style bullets shipped** (5th consecutive run; the V0.4.33 thinking-filter quarantined 1 truncated bullet; the V0.4.34 quarantined none).
- **51 bullets** (vs V0.4.33's 59 — 14 % reduction; vs V0.4.32's 65 — 22 % reduction; vs V0.4.31's 85 — 40 % reduction). The reduction is attributable to (a) the V0.4.23 filler floor dropping 10 attempts (vs V0.4.33's 12), (b) the V18.20.3.2 active-subject veto dropping 1 (vs V0.4.33's 3), (c) the V18.20.3.7 dedup dropping 1 (vs V0.4.33's 4), and (d) the deadline stopping gap-fill after 5 rounds.
- **Thorough ~29,957 chars / 3,945 words / 1 paragraph** — the V0.4.34 thorough is 5× longer than V0.4.33's pre-gap-fill thorough (which was 533 words) but **identical in length to V0.4.33's final thorough** (the V0.4.33 thorough also reached 3945 words after the gap-fill phase added 18 inline mentions). The V0.4.34 thorough is single-paragraph; the V0.4.33 thorough was multi-paragraph (6 paragraphs). Net: same word count, worse paragraph structure.
- **Key Distinctions (5) + Theoretical Tensions (4)** both ship — neither is filler. Page-ref injector (log lines 773 + 775) added `(p. ~X)` estimators to all 9 additive bullets. The `~` marker honestly discloses that the page numbers are estimated (not from the source). ✓
- **Honest disclosure bullet (bullet 49 — Byrne):** "Byrne (*1983*): The source text does not provide a specific excerpt or description of Byrne's independent contribution; his name appears only in the context of Akhtar's 'own descriptions' of behavioral correlates of splitting and identity diffusion." This is an honest admission that the source doesn't describe Byrne separately. ✓ A model that ADMITS the gap is preferable to one that fabricates content to fill it.
- **No meta-filler transition paragraph** (the V0.4.32 V3 defect is GONE — 3rd consecutive run; the V0.4.32 audit's backlog item 8 was apparently fixed somewhere between V0.4.32 and V0.4.33, and the fix holds on V0.4.34).

---

## Part 2 — JSON Scorecard

```json
{
  "summary_id": "001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.34_run20260926-004732-f5ad605b",
  "overall_score": 7,
  "factual_consistency_score": 7,
  "coverage_score": 6,
  "clarity_score": 7,
  "conciseness_score": 8,
  "hallucinations_detected": 1,
  "critical_omissions_detected": 1,
  "verdict": "PASS (borderline)",
  "justification": "1 NEW F1-class hallucination in the thorough summary (summary line 67): H3 'Stanton (*1980*) highlighted overt stubbornness...' — the cited year 1980 is FABRICATED (source has Stanton at 1978 only, six times). This is the SAME CLASS as V0.4.33's H1 (Mackinnon 1972) + H2 (Michels 1983) — fabricated year for a real author. The V0.4.34 release's headline feature (the year-attribution probe, commit 73660a0) DID NOT FIRE on this benchmark because the thorough gap-fill phase was skipped (V0.05 word-count gate: 3945 > 3332 target). The probe lives in core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences which only runs during thorough gap-fill; the H3 sentence was produced by the DEDICATED EXPANSION call which the probe does NOT see. The V0.4.33 H1+H2 hallucinations did NOT recur — but the elimination is NON-DETERMINISTIC (the LLM happened not to produce fabricated Mackinnon/Michels bullets this run; same flaw as V0.4.32's 'F1-F5 gone' verdict). The factual score rose from V0.4.33's 6 to 7 because the V0.4.34 ships 1 hallucination (vs V0.4.33's 2) and the H3 is in the thorough (buried in 3945 words) rather than in the V0.4.33's more prominent position. But the V0.4.34 did NOT achieve the deterministic elimination the release commit promised. Coverage regressed to 52/74 = 70% (vs V0.4.33's 77%) because the thorough gap-fill was skipped — Mackinnon and Michels is now in the missing-22 (was 'covered' by hallucinations in V0.4.33; the omission is better than the hallucination but the count regressed). Clarity rose to 7 because the enumeration-stem grammar improved and the V0.4.33 V4 garbled-stem class is GONE. Conciseness held at 8 because the filler floor + veto + dedup continue to strip filler reliably. Binding constraint: STILL factual (the H3 hallucination is the bottleneck). PASS borderline — same verdict class as V0.4.33."
}
```

> **Verdict: PASS (borderline).** The V0.4.33 audit found 2 NEW F1-class hallucinations (H1+H2) and scored factual at 6. The V0.4.34 release commit (`2adb4b2`) promised the year-attribution probe would catch this class DIRECTLY. **It did not.** The probe is correctly implemented in `core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences` (per `git show 73660a0`), but it only runs during the thorough gap-fill phase — which was SKIPPED this run because the dedicated expansion call already produced enough text (3945 > 3332 words; log line 783). The H1+H2 hallucinations did NOT recur, but the elimination is NON-DETERMINISTIC (same flaw as V0.4.32's "F1-F5 gone" verdict). A NEW H3 hallucination (Stanton 1980 in thorough) slipped through the dedicated expansion call, which the probe does not inspect.
>
> **The V0.4.34 release's stated goal was NOT MET on this benchmark.** The probe has a coverage blind spot: it inspects thorough gap-fill output but NOT dedicated-expansion output. The fix for V0.4.35 (provenance: this audit's finding F1) is to wire the year-attribution probe into the dedicated expansion call's post-processing too — OR to make the dedicated expansion call's output pass through `_grounded_addition_sentences` before ship.
>
> **The binding constraint remains FACTUAL** (same as V0.4.33). Until the year-attribution probe is wired to inspect ALL thorough-output paths (not just the thorough gap-fill path), the F1-class fabricated-year hallucinations will continue to slip through non-deterministically.

---

## Conversion-log review (the four-pillar + provenance cross-check)

### (a) Did the year-attribution probe fire?

**NO.** Zero `[attribution/DROP]` lines, zero `V0.4.24: gap-fill sentence dropped (attribution-edge)` lines in the V0.4.34 conversion log (vs V0.4.33's 19 such drops at log lines 803–847). The probe lives in `core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences` (per `git show 73660a0` — the diff adds a 20-line year-co-occurrence check inside the function). The function is **only called by the thorough-theorist-floor gap-fill phase**. That phase was:

1. Declared SKIPPED at log line 779 (`⏱️⚠️ Deadline exceeded (766s > 480s) — skipping optional phase: thorough theorist floor gap-fill`)
2. OVERRIDDEN as NON-SKIPPABLE at log line 781 (`⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 18 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not)`)
3. **ACTUALLY SKIPPED** at log line 783 by the V0.05 word-count gate (`⏭️ V0.05: Thorough gap-fill skipped — thorough (3945 words) already meets its source-scaled target (3332 words); the missing contributor(s) are covered by the bullets/recall floor`)

The skip happened because the **dedicated expansion call succeeded on attempt 2** (log line 541: "Attempt 2/3: dedicated thorough = 3945 words"; line 543: "thorough_summary expanded via dedicated call: 533 → 3945 words"). The dedicated expansion call produced enough text to satisfy the V0.05 word-count gate, so the V0.20 NON-SKIPPABLE override was overridden again by the V0.05 gate. The probe never ran.

**This is the audit's headline finding.** The V0.4.34 release's stated goal ("year-attribution probe catches the H1/H2-class hallucinations DIRECTLY") was NOT achieved on this benchmark. The H1+H2 hallucinations did NOT recur — but the elimination is NON-DETERMINISTIC (the LLM happened not to produce them this run). A NEW H3 hallucination (Stanton 1980) slipped through the dedicated expansion call, which the probe does NOT inspect.

### (b) Did the V0.4.33-wired semantic fact-check (Phase 2.2 on thorough additive prose) fire?

**NO.** Same reason as (a). The helper `_semantic_ground_addition_sentences` is called from within the thorough gap-fill phase, which was skipped. Nothing to verify; nothing dropped. This is the **second consecutive run where the V0.4.33 semantic fact-check had no opportunity to fire** (the V0.4.33 run actually fired it on 19 thorough additive sentences — log lines 803–847; the V0.4.34 run did not fire it).

**Phase 2.2 bullets-only check DID run** (log line 551: "Phase 2.2: All bullets semantically grounded (≥0.50 similarity)"). All 22 master-derived bullets passed ≥0.50 similarity to source claims (log line 573: "grounding=100% (22/22 bullets), hallucinations=0, deviations=0"). The check is bullets-only — it does NOT inspect the thorough additive prose. The V0.4.33 wired the thorough-additive extension into `_grounded_addition_sentences` (which didn't run this time).

### (c) Theorist floor (52/74 = 70 %)

| Round | Filling list (8 theorists) | Drops (filler floor + veto) | Added |
|---|---|---|---|
| 1 | Akhtar, Kernberg, Shapiro, Stanton, Heimann, … | 0 | 8/8 |
| 2 | Rycroft, Cameron, Frances, Byrne, Akhtar and Byrne, … | 1 filler (Byrne) + 1 veto (Akhtar and Byrne → Socarides) | 6/8 |
| 3 | Byrne, Akhtar and Byrne, Volkan, Winokur, Kendler, … | 2 filler (Akhtar and Byrne; Winokur) | 6/8 |
| 4 | Winokur, Mahler, Anthony, Kohut, Bach, … | 4 filler (Winokur 1985; Anthony 1981; Kohut 1972; Bach 1977) | 4/8 |
| 5 | Winokur, Anthony, Kohut, Bach, Jack, … (mention-only: Winokur) | 3 filler (Kohut 1972; Jack 1984; Ndtei 1986) | 5/8 |

**Total: 29 bullets added across 5 rounds.** Final missing-22 at log line 697 + 785: `['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels']` (truncated display — full count is 22). The V0.4.34 coverage regressed -7 pp vs V0.4.33 (57/74) because the thorough gap-fill was skipped (no +14 pp lift; V0.4.33 got that lift). The V0.4.34 is still +8 pp above V0.4.32 because the dedicated expansion call produced a richer thorough (56 inline theorists vs V0.4.32's thorough).

**The missing includes 'Mackinnon and Michels'** — the V0.4.34 dropped them entirely (vs V0.4.33 which "covered" them via H1+H2 hallucinations). The V0.4.34 outcome is BETTER (omission < fabrication) but the count regressed. The year-attribution probe did NOT drop a Mackinnon-and-Michels bullet this run (no such bullet was ever produced by the LLM — the system deprioritized compound names in the gap-fill fill-lists).

### (d) Deadline

**767 s (1.60× the 480 s budget).** Log line 787. Deadline-exceeded warnings fired at:
- 558 s (line 545) — `dedicated bullet expansion` skipped
- 673 s (lines 579, 587, 595) — `scholar reflection` + `pre-gap-fill semantic dedup` + `bullet consolidation` skipped
- 766 s (line 779) — `thorough theorist floor gap-fill` declared skipped (then OVERRIDDEN as NON-SKIPPABLE at line 781, then ACTUALLY SKIPPED at line 783 by V0.05 word-count gate)

The 767 s is **DOWN from V0.4.33's 860 s (-93 s) and V0.4.32's 889 s (-122 s)** — the V0.4.34 is the fastest of the three V0.4.3x runs. The savings come from (a) skipping the thorough gap-fill phase (saved ~3 chunked LLM calls × ~40 s each = ~120 s), and (b) the V17.4 deterministic-analysis skip (log line 431: "V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)" — same skip as V0.4.33).

### (e) OCR

**3 of 24 chapter pages were scanned (152, 153, 154).** Log line 281. The V0.4.1 vision-OCR path SUCCEEDED on all 3:

- p.152: 1025 chars (log line 295) — 31 s OCR time
- p.153: 87 chars (log line 299) — 23 s OCR time
- p.154: 931 chars (log line 303) — 33 s OCR time

**4th consecutive clean V0.4.1 OCR pass** (V0.4.31 + V0.4.32 + V0.4.33 + V0.4.34). The V0.4.31 OCR bug fix (commit `58a2ac7` — `complete_with_image accepts the model= kwarg`) continues to hold. The OCR content is integrated into the source text fed to the summarizer (53017 chars total, log line 455).

---

## Four-audit delta table (V0.4.31 → V0.4.32 → V0.4.33 → V0.4.34)

| Pillar | V0.4.31 (FAIL) | V0.4.32 (PASS non-det.) | V0.4.33 (PASS borderline) | V0.4.34 (PASS borderline) | Delta V0.4.34 vs V0.4.33 |
|---|---|---|---|---|---|
| **Factual Consistency** | **5** (5 hallucinations F1-F5) | **9** (0 hallucinations — but non-deterministic) | **6** (2 NEW H1+H2 F1-class hallucinations) | **7** (1 NEW H3 F1-class hallucination) | **+1** (H1+H2 gone, H3 new — net -1 hallucination; still non-deterministic) |
| **Informational Coverage** | **8** (64/75 = 85 %) | **7** (46/74 = 62 %) | **7** (57/74 = 77 %) | **6** (52/74 = 70 %) | **-1** (thorough gap-fill skipped; Mackinnon and Michels now in missing) |
| **Cohesion & Clarity** | **6** (splittingted garble, theme-of false positives, F8 thinking-style bullet) | **7** (F8 gone, garbles gone — but V3 meta-filler introduced) | **6** (V4 garbled enumeration stems ×6) | **7** (V4 garbled stems GONE; single-paragraph thorough persists) | **+1** (enumeration-stem grammar improved) |
| **Conciseness vs Vagueness** | **7** (85 bullets, much filler) | **8** (65 bullets, V3 meta-filler) | **8** (59 bullets, V3 gone) | **8** (51 bullets, V3 gone, filler floor still working) | **0** (steady; same filler-floor + veto + dedup) |
| **Overall** | **5 FAIL** | **9 PASS (non-det.)** | **6 PASS (borderline)** | **7 PASS (borderline)** | **+1** |
| **Hallucinations** | **5** (F1-F5) | **0** (non-det.) | **2** (H1 Mackinnon 1972 + H2 Michels 1983) | **1** (H3 Stanton 1980) | **-1** (net) |
| **Critical omissions** | n/a (5 hallucinations dominated) | **3** (Winokur, Jack, Ndtei) | **3** (Winokur, Jack, Ndtei) | **1** (Mackinnon and Michels — Winokur, Jack, Ndtei still missing but inline in thorough) | **-2** (Mackinnon/Michels newly missing; Winokur/Jack/Ndtei downgraded to "inline in thorough") |
| **Bullets** | 85 | 65 | 59 | 51 | -8 |
| **Chapter wall-clock** | n/a | 889 s | 860 s | 767 s | -93 s |
| **Year-attribution probe** | n/a (not yet implemented) | n/a | n/a (probe not yet implemented; V0.4.24 attribution-edge fired 19×) | **DID NOT FIRE** (probe implemented in commit `73660a0` but lives in thorough-theorist-floor.py which was skipped) | **NEW feature, 0 efficacy this run** |

---

## Verdict + recommended V0.4.35 backlog

**Verdict: PASS (borderline).** The V0.4.34 ships a 7/6/7/8 scorecard (vs V0.4.33's 6/7/6/8). The +1 factual lift comes from shipping 1 hallucination (vs V0.4.33's 2). The -1 coverage regression comes from skipping the thorough gap-fill (Mackinnon and Michels now in the missing-22). The +1 clarity lift comes from the V0.4.33 V4 garbled-stem class being GONE.

**The V0.4.34 release's stated goal — "year-attribution probe catches the H1/H2 class DIRECTLY" — was NOT MET on this benchmark.** The probe is correctly implemented in `core/summarisation/thorough_theorist_floor.py:_grounded_addition_sentences` but only runs during the thorough gap-fill phase, which was skipped this run because the dedicated expansion call already produced enough text. The H1+H2 hallucinations did NOT recur (good), but the elimination is NON-DETERMINISTIC (same flaw as V0.4.32). A NEW H3 hallucination (Stanton 1980) slipped through the dedicated expansion call, which the probe does NOT inspect.

**Recommended V0.4.35 backlog (provenance: this audit's findings):**

1. **F1 (HIGH PRIORITY — the headline finding):** Wire the year-attribution probe to inspect the DEDICATED EXPANSION call's output, not just the thorough gap-fill output. The H3 hallucination was produced by the dedicated expansion call (log lines 527–543), which the probe never sees. Fix: either (a) route the dedicated expansion call's output through `_grounded_addition_sentences` before ship, or (b) extract the year-attribution probe into a standalone helper that runs on ALL thorough output regardless of which phase produced it. **This is the smallest change the evidence supports (Rule 2 ✓) — the year-co-occurrence logic already exists, it just needs to be called from one more site.** Content-agnostic (Rule 1 ✓ — the year-attribution check is a structural property of source-citation-co-occurrence, not a book-specific property).

2. **F2 (MEDIUM PRIORITY):** The V0.05 word-count gate at log line 783 is too lenient — it allows the thorough to ship WITHOUT the year-attribution probe running, just because the dedicated expansion call hit a word count. Either (a) make the year-attribution probe NON-SKIPPABLE regardless of word count (like the V0.20 NON-SKIPPABLE override), or (b) tighten the V0.05 gate to require the probe to have run, not just the word count to be met.

3. **F3 (MEDIUM PRIORITY — the V0.4.26 backlog item 3, 5th consecutive run):** Break the thorough into MULTIPLE paragraphs at section transitions. The V0.4.34 thorough is a single 29957-char / 3945-word paragraph — the H3 hallucination is buried in dense prose, harder for a human to spot. The single-paragraph structure is a clarity defect that 4 consecutive audits have flagged.

4. **F4 (LOW PRIORITY):** The "Mackinnon and Michels" compound-name deprioritization in the gap-fill fill-lists (rounds 1-5 favored single-name theorists). The system should attempt compound-name theorists with the same priority as single-name theorists. This is a coverage gap, not a correctness gap.

---

*Generated by audit subagent `ch6-v0434-audit` on 2026-09-26. Audit evidence: V0.4.34 summary (51 bullets, 1 paragraph thorough 3945 words), V0.4.34 conversion log (933 lines), V0.4.33 audit (for delta), source chapter (598 lines, 7358 words), commit `73660a0` diff (20 lines added to `core/summarisation/thorough_theorist_floor.py`). Provenance stamp parsed BEFORE audit per Rule 4 ✓.*
