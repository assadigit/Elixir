# New Session Prompt — Elixir V0.5.17+ (the post-repeatability session)

## Context

You are continuing work on **Elixir** — a PySide6 desktop app + local LLM (llama.cpp) that summarizes books. The project is at `https://github.com/assadigit/elixir` on branch `refactor/audit-session` (tag `V0.5.17`).

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

## Key files (current)

- `scripts/repeatability_run.py` — the headless end-to-end chapter run
  (rig-parity settings, real LlamaCppProvider streaming path, the
  conversion-level pre-steps: segments + deterministic analysis + concepts,
  the save path: render + verification LAYER + provenance + run-stamped name)
- `scripts/repeatability_audit.py` — the deterministic author-coverage audit
- `core/summarisation/bullet_pipeline.py` — `_validate_gap_fill_bullets`
  (the V0.5.16 degenerate-signal guard)
- `core/summarisation/postchecks/orchestrator.py` — the V0.5.17 near-dup
  author-coverage veto
- `core/summarisation/glossary_parser.py` — glossary extraction + parser + persistence
- `core/summarisation/primary_call.py` — the `_extract_glossary_for_call` wiring
- `core/summarisation/verification_phase.py` — the glossary-grounded coverage check + side-channel
- `core/summarisation/gap_fill_batch.py` — the loosened quote-guard + final-check round 4
- `core/pipeline/converter_impl.py` — the non-blocking VRAM check (V0.5.14)
- `prompts/summarisation/glossary_extraction.md` — the markdown-header glossary prompt

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
3. **The V0.5.18 backlog (small, evidenced)**:
   - **NEW (ch.9 operator audit, HIGH): the verification LAYER's "et al."
     false positive** — the coverage check's word-boundary pattern
     (`verification_phase.py` ~L790: `r"\b" + re.escape(name) + r"\b"`) can
     NEVER match a glossary name ending in "et al." (the terminal `\b` after
     the escaped period requires a following word character; prose always has
     "et al. " + space/paren). The ch.9 run flagged 8 missing authors — 6 were
     present (Kety et al., Lilienfeld et al., Robins et al., Rosenthal et al.,
     Snyder et al., Spitzer et al.). Fix: strip the "et al." suffix for the
     presence check or relax the terminal `\b` for names ending in a non-word
     char. BENIGN now (flag-only) but HARMFUL once append-mode corrections
     land (duplicate-bullet injection).
   - **NEW (ch.9 operator audit, HIGH): the semantic-dedup path lacks the
     V0.5.17 author-coverage veto** — the post-gap-fill semantic dedup
     (V18.20.3.2, 95→87 bullets) dropped the round-4 bullets that uniquely
     named Wender et al. + Widiger et al. (the Eissler pattern, one removal
     layer over — the veto exists in the near-dup path only). Extend the veto
     to the semantic-dedup removal path.
   - **NEW (ch.9 operator audit, MEDIUM): `extract_citations` citation-run
     gap** — "Kety et al. 1968, 1975, Rosenthal et al. 1968, 1971, Wender et
     al. 1974" captures only Kety; possessive/line-broken citations
     ("Abraham's (1921,\n1924a,b)") are missed too. The glossary compensates
     (llm_only bucket) but the deterministic floor undercounts the universe.
   - cross-field year-consistency check (the ch.1 thorough shipped "Eissler
     (*1955*)" + "Kris (*1956*)" while the bullets had the correct 1958/1946 —
     a per-field validator that flags when bullet + thorough disagree on an
     author's year for the same event. The ch.9 run adds a 2nd instance: the
     women-citation bullet shipped "Akhtar et al., (*1984*)" where the source
     says "Akhtar et al. 1986" — the 1984 belongs to the ADJACENT men-citation
     "Robins et al. 1984")
   - the verification LAYER's additions are brittle (exact-substring
     corrections; 5 of 6 proposed corrections were skipped in the ch.1 run) —
     consider an append-mode correction type
   - the scholar-reflection quote guard (scholar_reflection.py:594 "Dropped
     gap-fill without quote") could take the V0.5.6 loosened quote-guard for
     glossary-backed authors (same pattern as V0.5.15/V0.5.17)
4. **The Searles caveat**: the loosened quote-guard accepted "Searles (1960)
   discussed the longing to abandon the human quality of identity" on a
   see-also-only citation — verify whether the glossary context should bound
   the bullet's claim more tightly (the audit flagged slight content
   inflation). The ch.9 run adds a 2nd instance: the Simic bullet shipped
   "Simic (*1980*)" — the epigraph attribution is true but the YEAR appears
   nowhere in the source (glossary-borne external knowledge).

## Token + repo

- GitHub token: `[REDACTED:github_token]` (one-off URL, scrub after use per Rule 4)
- Repo: `https://github.com/assadigit/elixir` (branch `refactor/audit-session`)
- Zips: `/home/z/my-project/download/Elixir-V0.5.16.zip` + `Elixir-V0.5.17.zip`

## Session workflow

1. Clone the repo (if not already): `git clone https://ghp_...@github.com/assadigit/elixir.git elixir`
2. Checkout `refactor/audit-session` (the V0.5.x lineage)
3. Read this file + CHANGELOG.md (the V0.5.x entries at the top)
4. For headless runs: `python scripts/repeatability_run.py --chapter <path> --out runs/<name> --llamacpp-url <endpoint> --llamacpp-model <model>` then `python scripts/repeatability_audit.py --run runs/<name>` (see the scripts' docstrings for the llama.cpp-emulator shim setup)
5. Audit any rig upload (move files to `audit/results/bench_v0XXX/` + create the audit md)
6. If coverage <90% on a new chapter/book, investigate + fix (content-agnostic — Rule 1)
7. Commit + push + zip per release (Rule 5)
