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
2. **The rig re-verification**: re-run ch.1 or ch.6 ON THE RIG with V0.5.17 to
   confirm the two new guards behave identically with a REAL embedder present
   (the guards are no-ops when the embedder is healthy — but verify).
3. **The V0.5.18 backlog (small, evidenced)**:
   - cross-field year-consistency check (the ch.1 thorough shipped "Eissler
     (*1955*)" + "Kris (*1956*)" while the bullets had the correct 1958/1946 —
     a per-field validator that flags when bullet + thorough disagree on an
     author's year for the same event)
   - the verification LAYER's additions are brittle (exact-substring
     corrections; 5 of 6 proposed corrections were skipped in the ch.1 run) —
     consider an append-mode correction type
   - the scholar-reflection quote guard (scholar_reflection.py:594 "Dropped
     gap-fill without quote") could take the V0.5.6 loosened quote-guard for
     glossary-backed authors (same pattern as V0.5.15/V0.5.17)
4. **The Searles caveat**: the loosened quote-guard accepted "Searles (1960)
   discussed the longing to abandon the human quality of identity" on a
   see-also-only citation — verify whether the glossary context should bound
   the bullet's claim more tightly (the audit flagged slight content inflation).

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
