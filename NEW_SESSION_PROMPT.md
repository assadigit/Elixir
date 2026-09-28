# New Session Prompt — Elixir V0.5.18+ (the post-repeatability session)

## Context

You are continuing work on **Elixir** — a PySide6 desktop app + local LLM (llama.cpp) that summarizes books. The project is at `https://github.com/assadigit/elixir` on branch `refactor/audit-session` (tag `V0.5.20`).

**STANDING RULE**: the elixir project is PURELY PYTHON (PySide6 desktop app + local LLM). Any Next.js sandbox at `/home/z/my-project` is disposable tooling only — NOT part of the elixir project. Never describe elixir with web-framework framing.

## AGENTS.md rules (NON-NEGOTIABLE)

1. **Rule 1 (content-agnostic)**: NO hardcoded book/author/chapter/domain strings. The system must find authors itself via the runtime `extract_citations` (the deterministic regex) + the runtime glossary (the LLM-extracted source roster). Never hardcode or cheat by adding missing author names to the LLM or prompt.
2. **Rule 2 (evidence-first)**: every claim cites file:line.
3. **Rule 3 (net-green)**: ruff clean + eval gate OK + pytest suite passing.
4. **Rule 4 (provenance)**: changes traceable in CHANGELOG + commits.
5. **Rule 5 (zip-per-release)**: zip per release in `/home/z/my-project/download/`.

## The V0.5.x campaign summary (V0.5.0 → V0.5.17)

The V0.5.x lineage built the **source-glossary architecture** (an LLM-generated
glossary fused into a separate LLM call, persisted as `.glossary.md`, used as
the coverage ground truth for gap-fill + final-check + loosened quote-guard)
and then — in the repeatability session — PROVED it repeatable:

- **V0.5.15 (rig, ch.6):** 70/74 = 95% author coverage, 0 hallucinations.
- **V0.5.16 (sandbox, ch.1):** found + fixed the gap-fill Phase 2.2
  degenerate-signal guard — an embedder-less rig rejected EVERY gap-fill
  bullet at "sim 0.00" (`semantic_fact_check` fails closed when the embed
  model is absent; the gap-fill validation call site lacked the V18.2.30
  health guard the main Phase 2.2 stage has). ch.1 coverage 56.8% → 89.2%.
- **V0.5.17 (sandbox, ch.1):** found + fixed the near-duplicate
  author-coverage veto — the ship-time near-dup removal dropped a gap-fill
  bullet that uniquely named a regex-confirmed author (Eissler). ch.1
  coverage → **37/37 = 100%, 0 hallucinations**, and a same-chapter re-run
  reproduced it EXACTLY (37/37 again, ±0pp variance — the V0.5.14-era
  "Jack vs Kernberg" run-to-run variance is structurally resolved by the
  deterministic floors).

**The repeatability verdict (audit/results/AUDIT_V0.5.17_..._ch1_summary_vs_source.md):**
the 95%+ coverage is repeatable on a different chapter of the same book, on a
different model (glm-4-plus cloud vs Ternary-Bonsai-2-27B local), on a
different machine — via the headless harness (`scripts/repeatability_run.py` +
`scripts/repeatability_audit.py`, one command each).

**V0.5.17 (operator rig, ch.9 — 2026-09-28, the THIRD confirmation):** the
operator ran the released V0.5.17 zip on ch.9 ("HISTRIONIC AND SCHIZOTYPAL
PERSONALITY DISORDERS", 7,089 words, 69-author roster) on their own rig
(Ternary-Bonsai-2-27B, RTX 3060, REAL embedder via OllamaEmbedBackend):
**66/69 = 95.65% deterministic recall floor, 0 fabricated claims, 87 bullets**
(68/69 = 98.6% full-text; only Erikson absent everywhere). The V0.5.17
near-dup veto fired unprompted in the wild (Kretschmer + Nanarello rescued),
final-check round 4 added 19/19 glossary-grounded, the thorough-floor
deadline override worked as designed. Three confirmations now — ch.6 rig
94.6%, ch.1 sandbox 100%, ch.9 operator 95.65% — the ~95% band is a property
of the ARCHITECTURE. Audit: `audit/results/AUDIT_V0.5.17_run20260928-022401-45d5434e_ch9_summary_vs_source.md`
(on main) + `audit/results/bench_v0517_ch9_histrionic_schizotypal/`.

**V0.5.18 (2026-09-28, same-chapter re-benchmark — the ceiling lift):** the
ch.9 operator audit's 2 HIGH bugs + 1 MEDIUM fixed and the SAME chapter re-run
end-to-end (sandbox shim, glm-4-plus): **73/73 = 100% deterministic coverage
floor AND full-text** — on a 4-name-LARGER roster (the citation-run fix put
Rosenthal/Wender/Widiger/Abraham inside the deterministic universe) — vs the
operator's 66/69 = 95.65%. The verification flag went from 8-flagged/6-false
to 3-flagged/0-false (the et-al anchor fix, live), Wender + Widiger + Erikson
all covered (Erikson verbatim-faithful), the V0.5.17 near-dup veto rescued 8
roster-grounded bullets incl. Wender (up from 2 — the fixes compound), 0
fabricated claims, 2 minor thin-bullet cross-wirings. The semantic-dedup
veto (Bug #2's fix) is unit-pinned but was INERT in this embedder-less
sandbox (both semantic-dedup passes skip without sentence-transformers) —
it will fire live on the operator's real-embedder rig. Audit:
`audit/results/AUDIT_V0.5.18_run20260928-010037-71084cb1_ch9_summary_vs_source.md`
(on main) + `audit/results/bench_v0518_ch9_histrionic_schizotypal/`.

**V0.5.19.1 rig run #2 (2026-09-28, the FULL-BOOK ingestion path — run
`20260928-155851-011587f0`):** the operator ran the whole 397-page
"Broken Structures" PDF with ch.9 TOC-selected (p.222-242) on their
real-embedder rig — the first end-to-end full-book → chapter-selected run
and the first live fire of the V0.5.18 semantic-dedup veto (Kallman +
Widiger rescued; the sandbox runs were inert). **69/73 = 94.5%
individual-level coverage (67/73 strict-string), 0 fabricated claims,
verification flag 2/0 honest** — the ~95% band holds on a fourth
configuration (ch.6 rig 94.6%, ch.1 sandbox 100%, ch.9 rig 95.65%, ch.9
rig full-book 94.5%). The run's cost: the V0.5.19/.1 continuation joins
regressed on the full-book extraction's layout (all four filed defects
are now FIXED — see the V0.5.20 paragraph below). Audit:
`audit/results/AUDIT_V0.5.19.1_run20260928-155851-011587f0_ch9_summary_vs_source.md`
(on main) + `audit/results/bench_v0519_1_ch9_histrionic_schizotypal_rig2/`.

**V0.5.20 (2026-09-28, the four rig-run-2 backlog items — ALL SHIPPED,
tag `V0.5.20`, 37 new tests, zero new suite failures):**

- **The layout-independent (marker-sequence-driven) continuation join +
  the terminal-shape lint.** The run-in marker patterns now accept a
  marker at a paragraph tail (`…, and (4).` matched, punct consumed);
  the open-tail predicate treats empty/punctuation-only marker tails as
  OPEN; the final-item continuation rule joins an open list to a
  LOWERCASE successor paragraph carrying no same-style marker (the
  "embraces casual | acquaintances…" family — the histrionic criteria
  roman list now carries item (iv) COMPLETE with (v) attached on the
  real ch.9 source, a 4-item truncated capture in every prior run); up
  to 2 PAGE-FURNITURE paragraphs (bare page numbers / ALL-CAPS running
  headers — the new shared `core/common/layout_furniture.py`) between a
  list and its continuation are looked past; `extract_structured_criteria`
  skips furniture LINES without closing the cluster (the 5/8 + 3/9
  schizotypal prefix-truncations → 8/8). The lint
  (`ends_in_dangling_enum_marker`, advisory `enumeration/flag` in
  `postcheck_bullets`) makes the "enumerated items N/N" floor's blind
  spot audit-visible: no shipped bullet may end in a bare `and (N).`.
- **The keypoints-layer author-coverage veto.** The keypoints dedup
  (embedding + rapidfuzz paths) no longer removes a bullet that uniquely
  names a roster author absent from the rest of the keypoints (the same
  roster/anchor/deferred-judgment/promotion-guard semantics as the
  V0.5.18 summary-layer veto, order-preserved, fail-open).
- **The glossary handoff path.** The `.glossary.md` persists INSIDE the
  run's per-book output folder (`request._run_output_dir`, attached by
  `run_summarization`; falls back to `request.output_dir` on the harness
  path) and the glossary dict carries `path` — the "Glossary: (none)"
  audit-trail family is dead.
- **The thin-bullet colon-less variant.** `Name made significant
  contributions to…` / `Name (*1980*) contributed to…` one-liners (≤280
  chars) are now flagged alongside the colon form; real claims
  (`contributed the X` — no "to") and substantive thorough prose stay
  unflagged; the colon form's pinned behavior is unchanged.

NOT yet verified on the operator rig: the four fixes are pinned by 37
unit tests incl. REAL-source checks (the six-grounds 6/6, the Reveals
4/4 with item (4) complete, the criteria 8/8 across furniture) — the
next full-book rig run should confirm them LIVE (the joins now read the
marker sequence instead of the paragraph structure, so the p.222-242
pagination artifacts the run exposed are all handled).

## Key files (current)

- `scripts/repeatability_run.py` — the headless end-to-end chapter run
  (rig-parity settings, real LlamaCppProvider streaming path, the
  conversion-level pre-steps: segments + deterministic analysis + concepts,
  the save path: render + verification LAYER + provenance + run-stamped name)
- `scripts/repeatability_audit.py` — the deterministic author-coverage audit
- `core/summarisation/author_anchor.py` — **V0.5.18**: the shared boundary-safe
  author anchoring (et-al strip + `(?<!\w)name(?!\w)` lookarounds + the
  runtime roster helper) used by EVERY author-coverage veto + the
  verification coverage check + the audit scorecard
- `core/summarisation/summary_validator.py` — **V0.5.18**:
  `semantic_dedup_bullets(source_authors=, context_text=, source_text=)` —
  the deferred author-coverage veto on the semantic-dedup removal path
  (both `chapter_phases.py` call sites wired with the roster + exec/thorough
  context + source text)
- `core/summarisation/bullet_pipeline.py` — `_validate_gap_fill_bullets`
  (the V0.5.16 degenerate-signal guard)
- `core/summarisation/postchecks/orchestrator.py` — the V0.5.17 near-dup
  author-coverage veto (V0.5.18: routed through `author_anchor`)
- `core/summarisation/postchecks/attribution.py` — **V0.5.18**:
  `validate_years` check 3 (author-year consistency vs the roster years map,
  `Name[^\d]{0,48}?year` prose-adjacency exemption) + the markdown/comma-
  tolerant citation-regex join
- `core/preprocessing/deterministic_analyzer.py` — **V0.5.18**: `extract_citations`
  Pattern 6 (parenthetical citation runs) + the Pattern-1 letter-suffix years
  group ("1921,\n1924a,b")
- `core/summarisation/glossary_parser.py` — glossary extraction + parser + persistence
  (V0.5.18: `cross_reference_glossary` anchor-normalized)
- `core/summarisation/primary_call.py` — the `_extract_glossary_for_call` wiring
- `core/summarisation/verification_phase.py` — the glossary-grounded coverage check + side-channel
  (V0.5.18: the anchor-based presence check — the et-al false positive dead)
- `core/summarisation/gap_fill_batch.py` — the loosened quote-guard + final-check round 4
- `core/pipeline/converter_impl.py` — the non-blocking VRAM check (V0.5.14)
- `prompts/summarisation/glossary_extraction.md` — the markdown-header glossary prompt
- `tests/test_v0518_*.py` — the 28 V0.5.18 characterization tests (anchor
  matrix / dedup-veto matrix via the fake-embedder twin groups / citation-run
  + year-consistency matrix)
- `core/common/layout_furniture.py` — **V0.5.20**: the shared page-furniture
  shapes (bare page numbers + multi-token ALL-CAPS running headers), used by
  BOTH layout-join sites (the enumeration paragraph join + the criteria
  cluster collector)
- `core/summarisation/enumeration.py` — **V0.5.20**: the marker-sequence
  join (tail-marker patterns / `_runin_tail_open` / the final-item
  continuation rule / the furniture look-past)
- `core/summarisation/keypoints_builder.py` — **V0.5.20**: the
  keypoints-layer author-coverage veto (both dedup paths)
- `tests/test_v0520_layout_vetoes.py` — the 37 V0.5.20 characterization
  tests

## The next session goals

1. **A different BOOK entirely** (the remaining Rule 1 compliance test): the
   repeatability proof covered a different chapter of the SAME book. Run the
   harness on a physics textbook / novel / cooking manual — the content-agnostic
   claim needs one non-psychoanalysis domain verified end-to-end.
2. **The rig re-verification** — LARGELY ANSWERED by the ch.9 operator run
   (2026-09-28): V0.5.17 on the operator's own rig with a REAL embedder
   (OllamaEmbedBackend): the V0.5.16 guard no-op'd as designed (Phase 2.2 all
   bullets ≥0.50), the V0.5.17 veto fired correctly, 95.65% floor. A
   controlled ch.1/ch.6 re-run remains optional for exact-parity comparison.
3. **The V0.5.21 backlog (small, evidenced)** — the V0.5.19 AND V0.5.20
   items are ALL SHIPPED (V0.5.19 + V0.5.19.1 + V0.5.20; see the
   CHANGELOG's three entries + the 96 new tests). What remains:
   - **the thin roster-gap-fill bullet quality** (the Wolf/Chick/Robins/
     Frances one-liners recurred in the V0.5.19.1 run — now ALL caught by
     the quality flag, but the MODEL still writes them; a gap-fill prompt
     tightening ("state the author's specific contribution") or a
     quality-gate at the gap-fill merge would reduce the family at the
     source)
   - **the glossary pair-form dedup** (the ch.9 V0.5.19.1 glossary lists
     both "Gunderson and Siever" AND "Siever and Gunderson" as separate
     names — the anchor-check pair-form made the verification flag name
     the reverse pair as missing while both individuals are covered; dedupe
     commuted pair-forms at glossary ingestion)
   - **the Searles-family see-also bound** (below, unchanged)
   - **the rig LIVE verification of the V0.5.20 fixes** — the four fixes
     are unit-pinned (37 tests incl. real-source checks: the six-grounds
     6/6, the Reveals 4/4 with item (4) complete, the criteria 8/8 across
     furniture) but the full-book rig run that exposed them has not been
     re-run; the next operator run should confirm the joins fire on the
     real full-book extraction layout (the lint + the empty-item skip
     guarantee the defects are at least audit-visible even if a new
     layout family escapes)
4. **The Searles caveat**: the loosened quote-guard accepted "Searles (1960)
   discussed the longing to abandon the human quality of identity" on a
   see-also-only citation — verify whether the glossary context should bound
   the bullet's claim more tightly (the audit flagged slight content
   inflation). The ch.9 operator run's Simic bullet shipped "Simic (*1980*)"
   (unsourced year — glossary-borne); NOTE the V0.5.18 re-run shipped NO
   Simic bullet at all (absent rather than unsourced — same family, cleaner
   failure mode).

## Token + repo

- GitHub token: `[REDACTED:github_token]` (one-off URL, scrub after use per Rule 4)
- Repo: `https://github.com/assadigit/elixir` (branch `refactor/audit-session`)
- Zips: `/home/z/my-project/download/` — `Elixir-V0.5.16.zip` … `Elixir-V0.5.20.zip`

## Sandbox benchmarking note (the reaper)

The z.ai sandbox reaps background processes spawned from tool-call shells
(setsid/nohup/disown strays die within ~a minute of the spawning call
ending). For headless benchmark runs use the **bench-spawner** mini-service
(`mini-services/bench-spawner/`, port 3032, launched with the subshell
pattern `(bun run dev > spawner.log 2>&1 &)` — services launched that way
persist):

```bash
curl -X POST "http://localhost:3032/run?out=<name>&chapter=<path>&label=<label>&model=glm-4-plus"
curl "http://localhost:3032/status?log=/home/z/elixir/runs/<name>_run.log"   # alive + log tail
```

The LLM endpoint is the zai-llamacpp-shim (port 3031) — do NOT restart it
(it persists from its original launch; a fresh stray would be reaped).

## Session workflow

1. Clone the repo (if not already): `git clone https://ghp_...@github.com/assadigit/elixir.git elixir`
2. Checkout `refactor/audit-session` (the V0.5.x lineage)
3. Read this file + CHANGELOG.md (the V0.5.x entries at the top)
4. For headless runs: `python scripts/repeatability_run.py --chapter <path> --out runs/<name> --llamacpp-url <endpoint> --llamacpp-model <model>` then `python scripts/repeatability_audit.py --run runs/<name>` (see the scripts' docstrings for the llama.cpp-emulator shim setup)
5. Audit any rig upload (move files to `audit/results/bench_v0XXX/` + create the audit md)
6. If coverage <90% on a new chapter/book, investigate + fix (content-agnostic — Rule 1)
7. Commit + push + zip per release (Rule 5)
