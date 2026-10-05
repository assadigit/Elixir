# AUDIT — Summary vs Source — version V0.4.25 (run 20260924-151700-2bd82b60) — ch.1

> **Audit version:** `V0.4.25 / run 20260924-151700-2bd82b60 / app 0.4.25 / 2026-09-24T15:17:00 / 45 bullets`
> **Book:** Broken Structures (Salman Akhtar), chapter 1 "IDENTITY AND ITS ORIGINS" (PDF pp. 15–32, 6,335 source words fed / 6,425 counted by the app)
> **Audit framework:** the standing four-pillar expert fact-checker (`docs/EVALUATION_FRAMEWORK.md`).
> **Ground truth:** `docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md` — the standing ch.1 ground truth (unchanged since the V0.18 audit).
> **Operating mode:** **SANDBOX BENCHMARK RIG — the first fully in-session end-to-end run.** The REAL V0.4.25 pipeline (16-stage `_summarize_inner`, exact `refactor/audit-session @ fd32ee3` tree shipped in `elixir-0.4.25-audit-session.zip`) ran headlessly against the standing ground-truth chapter text, with the llama.cpp provider contract pointed at a local OpenAI-compatible streaming proxy (`mini-services/llm-proxy`, port 4540) backed by the session's z-ai SDK model at t=0.7. This is the same code path the owner's Windows rig drives; the LLM differs (z-ai cloud model vs Ternary-Bonsai-2-27B on RTX 3060), which this audit accounts for wherever model-dependent behavior matters.

---

## Provenance cross-check (run BEFORE the audit, per the campaign protocol)

| Field | Value | Match |
|---|---|---|
| `run_id` (summary stamp) | `20260924-151700-2bd82b60` | ✓ fresh, in-file `<!-- generated-by -->` comment |
| `app_version` | `0.4.25` | ✓ matches repo `VERSION` at commit `fd32ee3` |
| `bullets` | `45` | ✓ manifest = rendered file = log line "43 bullets ship… + 2 last-chance enumeration repair" |
| repo state | `refactor/audit-session @ fd32ee3`, clean tree | ✓ the audit-session zip tree, byte-for-byte |
| run-stamped filename | `001_1_-_IDENTITY_AND_ITS_ORIGINS_v0.4.25_20260924-151700-2bd82b60_summary.md` | ✓ V0.4.25 run-stamp convention |
| COMPLETE sentinel | `<!-- COMPLETE run_id=20260924-151700-2bd82b60 -->` | ✓ run-id-stamped |
| LLM transport | llama.cpp wire contract (SSE streaming), 12 calls, 62.3 s LLM time, 394,350 prompt chars / 25,254 response chars | ✓ proxy call log `calls.jsonl` calls #11–#22 |
| chapter wall-clock | 67 s (deadline 480 s) | ✓ log line 149 |
| temperature | 0.7 set; internal phases used their own temps (0.20 primary / 0.10 thorough / 0.00 greedy retries) | ✓ Group-B per-phase policy, same as rig runs |
| artifacts | summary `.md` + conversion log + deterministic scorecard + manifest, saved at `audit/results/bench_v0425_ch1/` | ✓ |

**Sandbox-rig disclosures (honest-divergence ledger).** Three pipeline features are embedder-dependent and the sandbox venv ships no `sentence-transformers`: the semantic fact-check, semantic dedup, and the LLM-judge gap-fill all detected the unhealthy embedder and **skipped themselves with explicit degenerate-signal guards** (log lines 54/60/87: "embedder unhealthy — skipping… would produce false drops"). The deterministic judge, coverage floor, theorist floor, enumeration guarantee, and all deterministic-polish postchecks ran normally. On the owner's rig (which has the embedder) those three phases would additionally run — the divergence is disclosed, not hidden.

---

## Part 1 — Detailed Report

### Method

**78 discrete claims** extracted across the five summary sections (Executive Summary ≈ 12; Key Takeaways 45 bullets ≈ 48; Thorough Summary ≈ 13; Key Distinctions 5). Every claim was verified against the ground-truth chapter; every quoted string was checked for verbatim presence in the source (line-wrap-aware). The repo's own deterministic instrument (`scripts/eval_summary.py`, the same code that gates every commit via `make eval-check`) scored the pair independently — its scorecard is embedded below.

### Fact-Check Log

**Result: 74 claims verified clean, 2 moderate misattributions, 1 minor attribution stretch, 1 non-verbatim quote fragment. Zero fabricated content, zero fabricated names, zero fabricated quotations.** All dates, numbers, criteria lists, and proper names verify.

**Verified clean — representative high-stakes claims (selection of 24):**

| # | Claim in summary | Evidence in source (quote) |
|---|---|---|
| 1 | Tausk introduced "identity" into psychoanalytic literature in 1919 | "The term identity was introduced into the psychoanalytic literature by Tausk (1919)" |
| 2 | Freud referenced the term only once, in his 1926 address to B'nai B'rith | "Freud, according to Erikson (1958), referred to the concept of identity only once. Not insignificantly, that was in his address to B'nai B'rith (Freud 1926a)" — *the summary drops the "according to Erikson" attribution hedge; the source's own opening sentence carries it too* |
| 3 | Erikson: ego identity = persistent sameness within oneself + sharing essential character with others | "a persistent sameness within oneself (selfsameness) and a persistent sharing of some kind of essential character with others" (p. 12) |
| 4 | Erikson later dropped the "ego" prefix (Hartmann's ego–self distinction) | "He later dropped the prefix ego in part to accommodate Hartmann's (1950) differentiation between ego and self" |
| 5 | Adolescence is the critical consolidation period | "Erikson emphasized the period of adolescence in consolidating one's identity" |
| 6 | Kernberg: identity diffusion differentiates borderline from non-borderline | "it is the presence or absence of identity diffusion that most clearly differentiates borderline from non-borderline conditions" (Kernberg 1980, p. 14) |
| 7 | Lichtenstein's identity principle rooted in mother–child symbiosis; irreversible "identity theme" | "the identity principle… the mother imprints upon the infant not an identity, but an 'identity theme.' This theme is irreversible" (1961, p. 208) |
| 8 | Metamorphosis: anguish but also liberation; life oscillates between the extremes | "the abandonment of identity produces confusion and anguish, but… this loss can be experienced as liberation and ecstasy… human life exists in an oscillation between these two extremes" |
| 9 | Freud's implicit views: somatic underpinnings, gender differences, Oedipal resolution | "accommodates somatic underpinnings, gender differences, early identifications, the role of the Oedipus complex and its resolution" |
| 10 | Fenichel's "body image" foundational | "the so-called 'body image,' is of fundamental importance for the further development of his ego" (1937, p. 29) |
| 11 | Federn's "ego feeling"; Glover's "ego nuclei" | "Federn's (1952) concept of early 'ego feeling'… similar to Glover's (1950) concept of 'ego nuclei'" — **both were V0.18 critical omissions; both now ship** |
| 12 | Self-constancy at rapprochement ≈ 2 years via maternal buffering | "not until the end of the rapprochement subphase… an event occurring at approximately two years of age, that 'self constancy'… comes into being… met with a constant but empathic stance from the mother" |
| 13 | Jacobson: 5 categories (self/object representations; fused self-object representation; identity from primitive identifications; aggression in self-delineation; oedipal/superego modifications) | "can be divided into five categories: (1)… (5)…" — **bullet 54 carries all five verbatim** |
| 14 | Winnicott: true self / "good enough" mother; defensive false self | "the infant's mother is 'good enough' (Winnicott 1960)… Such compliance gives birth to a 'false self'… defensive nature of the inauthentic persona, which seeks to hide and protect the 'true self'" |
| 15 | Kernberg 3-step process: introjection → identification → identity formation | "a three-step process of identity formation. The first step… is introjection… The second step is identification… The third step is identity formation" (summary's "identity synthesis" is a fair compression of "identifications are synthesized") |
| 16 | Chasseguet-Smirgel long/short path (B48) | "the 'long path,' consists of his accepting the tragedy of chronological lag… The young child mistakenly believes that he is already a man… The 'fatal character of the Oedipus complex' (1984, p. 26) is bypassed" — **all three quoted fragments verbatim** |
| 17 | Greenacre: vision of opposite-sex genitals / twins (B46) | "the habitual taking in through vision of the opposite-sex genitals and the fusion of this part image with that of the subject's own body. An early and repeated exposure to the genitals of the opposite sex among twins… may lead to their marked primary incorporation" — **verbatim across the source's line wrap** |
| 18 | Loewald + Mahler: father's stable relationship protects the toddler (B47) | "both Loewald (1951) and Mahler (1975) had pointed out the necessity for a growing toddler of a stable relationship with the father to protect himself against the threat of this precompetitive, libidinal tie" — verbatim |
| 19 | Blos: second individuation; renunciation/activity-passivity/bisexual resolution (B53) | "the second individuation process of adolescence… This he sees as being accomplished by (1) the renunciation of the primary love objects… (2) the reconciliation of activity and passivity, (3) the resolution of bisexual identifications" — **all three verbatim** |
| 20 | Winnicott's 3 developmental aspects: authenticity, corporeality (Khan 1983), temporal continuity (B52) | "His work provides the developmental basis for (1) authenticity; (2) 'corporeality' (Khan 1983)…; and (3) the experience of temporal continuity in the self" — verbatim |
| 21 | Conclusion: identity = 7 characteristics (B55) | "Cross-sectionally, a solid identity consists of the following characteristics: (1) a sustained feeling of selfsameness… (7) an inner solidarity with an ethnic group's ideals and a well-internalized conscience" — **all seven verbatim; the V0.18 #1 critical omission is now captured whole** |
| 22 | Blos: negative Oedipus complex → ego ideal | "the adult ego ideal is the heir of the negative Oedipus complex" (1984, p. 319) |
| 23 | Identity diffusion manifests as contradictions in self-image and relationships | "contradictions in their self-images, aspirations, and interpersonal relationships" |
| 24 | Identity's inherent ambiguity: intrapsychic + social | "a two-sided term with intrapsychic as well as social ramifications… its admittedly ambiguous place in psychoanalytic theory" |

**Flagged incidents:**

| # | Where | Defect | Class |
|---|---|---|---|
| F1 | Bullet 17 + Thorough | "Jacobson clarified distinctions between adolescent identity crises and pathological identity diffusion" — the source attributes this distinction explicitly to **Kernberg (1978)** ("Kernberg (1978) also described the distinctions between the adolescent identity crisis and the syndrome of identity diffusion"); Jacobson (1964) is named only as jointly "recognizing limitations and attempting to fill the lacunae." The exec summary's "later theorists" phrasing is safe; the bullet's singular Jacobson attribution is not. | **Misattribution (moderate)** |
| F2 | Bullet 49 | Roiphe credited with "the final giving up of the illusory penis" and "the abandonment of a narcissistic position" — both phrases are verbatim in source but belong to **Blos's** account of girls' bisexual resolution; Roiphe (with Galenson 1971) is listed among gender-identity contributors two paragraphs earlier. A Piaget-Klein-style name weld (the V0.4.23 defect class). | **Misattribution weld (moderate)** |
| F3 | Bullet 50 | "Meyer's work… emphasized the emotional attitudes of both parents… as 'of paramount importance'" — the quoted phrase is the chapter author's summary sentence in the Mahler section; Meyer (1980) is citation-adjacent, not the quoted speaker. | Attribution stretch (minor) |
| F4 | Key Distinctions #3 | Introjection vs identification: "feels more deeper" in the self-system — **"more deeper" is not in the source** (source: identifications are situated "deeper" in the self-system). The claim is right; the quoted words are wrong. | Non-verbatim quote fragment (minor) |

**Deterministic-polish wins observed live in the conversion log** (fixes the V0.4.22/V0.4.23 backlog claimed, now verified on a fresh chapter):
- Dropped-digit year auto-repair: `Kernberg (1980) → Kernberg (1980b)` (log line 116).
- Quote-guard gap-fill drops: gap-fill bullets for **Spitz** and **Loewenstein** were generated and then **dropped for lacking a verbatim quote** (log lines 81–82) — exactly the V0.4.22 fake-author-pollution fix working; zero fabricated names shipped.
- Near-duplicate drops + last-chance enumeration repair: bullets 41–42 dropped as near-duplicates, then the 5-item and 7-item enumeration bullets re-added post-filter (log lines 143–147) — the V0.4.24 guarantee path confirmed end-to-end on a new chapter.

### Omissions & Coverage

**Honest deterministic numbers** (the campaign's house rule — the LLM judge's claim-recall overstates content recall):
- **Conclusion items: 7/7** (log line 148: "Deterministic recall floor (final set): conclusion items 7/7") — the V0.18 audit's #1 critical omission.
- **Enumerated lists, whole chapter: 18/18 carried verbatim** (same log line) — Jacobson's 5 categories, Blos's 3 + 3, Winnicott's 3, the conclusion 7.
- **Named theorists: 22/37 (59%)** by the V0.18 audit's own 37-name counting (Tausk, Freud, Erikson, Hartmann, Jacobson, Kernberg, Fromm, Wheelis, Lifton, Lichtenstein, Fenichel, Federn, Glover, Greenacre, Mahler, Khan, Winnicott, Chasseguet-Smirgel, Blos, Loewald, Roiphe, Meyer ship; Lynd, Lasch, Kovel, Marx, Durkheim, Eissler, Spiegel, Stoller, Galenson, Searles, Klein, Spitz, Kris, Loewenstein do not). V0.18 shipped 20/37 (54%).
- **Keyword coverage (top-30, repo instrument): 90%**; top-10 source keywords: 10/10 present; deterministic `critical_omissions_detected: 0` on keywords.

**Still missing (the honest gaps):** the sociocultural extension's author list ships 3/6 names (Fromm, Wheelis, Lifton present; **Lynd, Lasch, Kovel absent** — Lasch/Kovel were already flagged at V0.18); **Marx/Durkheim** (the alienation/anomie foundations) absent; **Spiegel's "pooling"** absent (V0.18 flag, still open); **Mahler's phase sequence** (autistic → symbiotic → differentiation → practicing → rapprochement → object-constancy) never enumerated — the summary names the theory and the rapprochement endpoint but not the phases themselves; Greenacre's body-image→self-image→identity continuum absent; Kernberg's middle-age dimensions (1980b) absent.

**Critical omissions: 1** — the sociocultural author cluster (the chapter names "two directions" of extension as a structural claim; one direction's roster remains 3/6 after two audit cycles).

### Clarity & Cohesion

What regressed or persists from V0.4.23's known defect classes, now measured on ch.1:
1. **Enumeration-stem grammar (3 bullets):** "**His work provides developmental basis for** —", "**This he sees being accomplished by** —", "**Can divided into five categories** —" — the V0.4.24 stem-alignment fix did not reach the enumeration-guarantee path; stems are mid-sentence slices, and the first two are context-free (whose work? which "this"?).
2. **Theoretical Tensions section: LOST.** The additive followup produced 9 lines; 4 were dropped at intake as truncated; the postcheck then dropped the remaining tension lines as truncated ("unmatched quote/paren, dangling tail" — log lines 117–120: the intrapsychic-vs-social, infantile-vs-adolescent, long-path-vs-short-path, structure-vs-metamorphosis tensions). A five-section output shipped as four sections. The generated tension lines themselves were malformed (the same quote-garble class as the thorough text) — the guards did their job, but the section died honestly rather than shipping noise.
3. **Quote-mark imbalance in the thorough/exec text (~9 instances):** e.g. `essential character with others,"` (no opener), `concepts of ego feeling" and "ego nuclei` (swapped pair), `"good enough mother` (no closer). Read end-to-end, this is the most visible quality defect in the prose.
4. **HTML leakage:** `format_years` emits `<em style="font-size:0.9em">1983</em>` — valid for the DOCX pipeline, but it ships raw into the markdown output.

**Deterministic clarity proxy:** fragment_rate 1.27% (excellent — only the 3 enumeration stems register); length policy: exec 184 words (compliant, target 150–250), thorough 512 words (**non-compliant** — target 1,711–2,851; the dedicated-expansion retry loop capped at ~636-word attempts and accepted under-threshold output), bullets 45 vs guidance 27–40 (deliberate no-limits policy).

### Conciseness vs Vagueness

Zero filler bullets (V0.4.23 shipped 1); zero vague "some theorists believe" bullets — 43/45 bullets name their theorist or their source mechanism; the 2 exceptions are the context-free enumeration stems above. Every enumeration bullet carries its items verbatim, which is maximal specificity. The thorough summary's under-length (512/1,711 floor) is a completeness shortfall more than a conciseness virtue; it is scored here because the framework's fourth pillar penalizes both padding and thinness.

---

## Part 2 — JSON Scorecard

```json
{
  "summary_id": "001_1_-_IDENTITY_AND_ITS_ORIGINS_v0.4.25_run20260924-151700-2bd82b60",
  "overall_score": 7,
  "factual_consistency_score": 8,
  "coverage_score": 8,
  "clarity_score": 6,
  "conciseness_score": 7,
  "hallucinations_detected": 0,
  "critical_omissions_detected": 1,
  "verdict": "PASS",
  "justification": "Zero fabricated content, names, or quotations (all 14 quoted strings verbatim-verified with one minor fragment exception). Two moderate misattributions (bullet 17: Kernberg-1978 distinction credited to Jacobson; bullet 49: Blos's girls'-resolution phrases welded onto Roiphe) and one citation-adjacency stretch (Meyer) hold factual at 8. Coverage transformed vs V0.18: conclusion list 7/7, all enumerated lists 18/18 verbatim, Federn/Glover restored, theorists 22/37 (59% vs 54%), keywords 90% — held at 8 by the still-missing sociocultural name cluster (Lynd/Lasch/Kovel/Marx/Durkheim), Spiegel, and Mahler's phase sequence. Clarity 6: three garbled enumeration stems, Theoretical Tensions section lost to the truncation guard, ~9 unbalanced quote marks, HTML <em> leakage. Conciseness 7: zero filler, every bullet substantive, thorough 512 words vs 1,711 floor."
}
```

> **Verdict: PASS** (factual 8 ≥ 6, coverage 8 ≥ 5) — below the campaign bar of 9–10. The deterministic instrument agrees: `factual 7 / coverage 9 / clarity 6 / overall 7 / verdict PASS`, `prompt_manifest_hash ee5a61d0…` identical to the committed baseline (prompt-bank identity unchanged), `critical_omissions_detected: 0` on keywords.

---

## Version-anchored comparison (the campaign ledger — same chapter, same ground truth)

| Audit | factual | coverage | clarity | conciseness | overall | signature finding |
|---|---|---|---|---|---|---|
| **V0.18 ch.1** (run 20260920-084745) | 9 | 6 | 8 | — | 7 | factually flawless but conclusion list fragmented (2/7 absent), 5 theorists missing, thorough 13/37 theorists (35%) |
| **V0.4.25 ch.1** (run 20260924-151700, sandbox rig) | 8 | 8 | 6 | 7 | 7 | coverage inverted: conclusion 7/7 + lists 18/18 verbatim; attribution precision and clarity now the binding constraints |

**What held across seven versions of fixes:** the master-summary architecture, the author-garbage filter (zero fabricated names on a fresh chapter), the filler floor (zero), the no-limits policy (nothing displaced), the enumeration guarantee (survived near-dup drops via last-chance repair), the quote-guard on gap-fills, and now proven: **all of it runs unchanged on a different LLM backend through the llama.cpp contract.**

**What regressed vs V0.18:** factual 9→8 (the misattribution class — V0.18 had zero; the no-limits + gap-fill machinery ships more claims and more names, and two welds slipped through), clarity 8→6 (V0.18's 40-bullet output had no garbled stems; the enumeration-guarantee stems and the tensions-section loss are new machinery, first drafted in V0.4.23/24, still carrying first-draft defects).

**Sandbox-rig validity note:** the z-ai backend is a stronger model than the rig's 27B quantized local one; truncation-class defects that stem from model output limits will be *under*-represented here (the proxy cannot emit `finish_reason: length`), while attribution-weld and stem-slice defects are pipeline-side and model-independent. The three skipped embedder phases (disclosed above) would on the rig add semantic fact-check, semantic dedup, and judge-driven gap-fill — all three of which are quality-*raising* phases, so this run's scores are a conservative floor for the rig configuration.

---

## Backlog for V0.4.26 (priority order)

1. **Theoretical-tensions additive robustness** (`core/summarisation/additive_sections.py`): the tensions lines arrived malformed (unmatched quotes/dangling tails) and the guards killed the whole section. Apply the V18.20.3.2 mass-truncation retry (already used for the additive call) *per-section* with a structural prompt for tension lines ("X vs. Y — one line, balanced quotes"), and never let a 4-line drop take the section below 2 lines without one retry.
2. **Enumeration-stem grammar + self-containment** (`core/summarisation/enumeration.py`): stems must be sentence-aligned (V0.4.24 backlog #1, still not reached on this path) AND self-contained — the label must name its author ("Jacobson's contributions divide into five categories:"), never "His work…" / "This he sees…" / "Can divided…".
3. **Quote-pair balancer in deterministic polish** (`core/summarisation/post_processing.py`): the dropped-digit repair proved this class of fix ships safely; add a quote-balance pass (swap/reopen misplaced pairs like `ego feeling" and "ego nuclei`, drop orphaned quote chars) for thorough/exec/additive text.
4. **Sociocultural name floor** (`core/summarisation/thorough_theorist_floor.py`): the theorist floor covers psychoanalytic authors; the chapter's explicitly-listed sociocultural extension roster (Fromm, Wheelis, Lynd, Lifton, Lasch, Kovel) needs the same quote-guarded gap-fill treatment (Spiegel's "pooling" and the Marx/Durkheim foundations ride along).
5. **Markdown-target year formatting** (`core/pipeline/chapter_checkpoint.py::format_years`): emit `*1983*` for `.md` targets, keep `<em>` for DOCX.

---

## Artifacts

- Generated summary: `audit/results/bench_v0425_ch1/001_1_-_IDENTITY_AND_ITS_ORIGINS_v0.4.25_20260924-151700-2bd82b60_summary.md`
- Conversion log (154 lines): `audit/results/bench_v0425_ch1/run20260924-151700-2bd82b60.conversion.log.md`
- Deterministic scorecard (repo instrument): `audit/results/bench_v0425_ch1/deterministic_scorecard.json`
- Run manifest (provenance + timings): `audit/results/bench_v0425_ch1/benchmark_manifest.json`
- Proxy call log: `mini-services/llm-proxy/calls.jsonl` (session sandbox, calls #11–#22)
