# New Session Prompt — Elixir V0.5.15+ (the repeatability session)

## Context

You are continuing work on **Elixir** — a PySide6 desktop app + local LLM (llama.cpp) that summarizes books. The project is at `https://github.com/assadigit/Elixir` on branch `refactor/audit-session` @ commit `68946df` (tag `V0.5.15`).

**STANDING RULE**: the elixir project is PURELY PYTHON (PySide6 desktop app + local LLM). The Next.js sandbox at /home/z/my-project is disposable tooling only — NOT part of the elixir project. Never describe elixir with web-framework framing.

## AGENTS.md rules (NON-NEGOTIABLE)

1. **Rule 1 (content-agnostic)**: NO hardcoded book/author/chapter/domain strings. The system must find authors itself via the runtime `extract_citations` (the deterministic regex) + the runtime glossary (the LLM-extracted source roster). Never hardcode or cheat by adding missing author names to the LLM or prompt.
2. **Rule 2 (evidence-first)**: every claim cites file:line.
3. **Rule 3 (net-green)**: ruff clean + eval gate OK + pytest suite passing.
4. **Rule 4 (provenance)**: changes traceable in CHANGELOG + commits.
5. **Rule 5 (zip-per-release)**: zip per release in `/home/z/my-project/download/`.

## The V0.5.x campaign summary (V0.5.0 → V0.5.15)

The V0.5.x campaign introduced the **source-glossary architecture** — the user's idea: an LLM-generated glossary (names + dates + terms) fused into a separate LLM call, persisted as a `.md` file, used as the coverage ground truth for the gap-fill + final-check + loosened quote-guard.

**The architecture (now working end-to-end):**
```
source text → extract_glossary_via_llm (separate call, 8192 tokens, markdown headers)
           → parse_name_glossary (3-tier: XML compat, markdown headers, lenient bare-bullets)
           → persist_glossary (.glossary.md)
           → set_chapter_glossary (side-channel)
           → batch_gap_fill (source_glossary passed → V0.5.12 wiring)
              ↳ V0.5.6 glossary-grounded loosened quote-guard ✓
              ↳ V0.5.10 regex fallback ✓
           → V0.5.6 final-check round 4 (glossary-grounded targeted gap-fill) ✓
           → post-checks (V0.5.15 safety net: parenthetical_promotion + attribution-edge keep regex-grounded bullets) ✓
           → verification LAYER (glossary-grounded coverage check + cross-reference) ✓
```

**V0.5.15 results (the best in the lineage):**
- 70/74 = 95% author coverage (UP from V0.5.5's 93%)
- 82 keypoints, 39 bullets grounded (0 hallucinations)
- ALL 5 V0.5.5 missing authors covered (Jack, Morey, Ndtei, Rettersol, Bak)
- ALL 5 V0.5.14 missing authors closed (Kernberg, Socarides, Siever+Kendler, Varghesi, Pao)
- The glossary + final-check + loosened quote-guard + post-check safety net all fire correctly

**Key files:**
- `core/summarisation/glossary_parser.py` — the glossary extraction + parser + persistence
- `core/summarisation/primary_call.py` — the `_extract_glossary_for_call` wiring (3 return paths)
- `core/summarisation/verification_phase.py` — the glossary-grounded coverage check + side-channel
- `core/summarisation/gap_fill_batch.py` — the loosened quote-guard + final-check round 4
- `core/summarisation/postchecks/field_phases.py` — the V0.5.15 post-check safety net
- `core/summarisation/thorough_theorist_floor.py` — the V0.5.15 attribution-edge recovery
- `core/pipeline/converter_impl.py` — the V0.5.14 non-blocking VRAM overbudget check
- `prompts/summarisation/glossary_extraction.md` — the markdown-header glossary prompt

## The next session goal: REPEATABILITY

**The V0.5.15 results (95% coverage, 0 hallucinations) were achieved on chapter 6 of "Broken Structures Salman Akhtar". The goal now is to verify these results are REPEATABLE on:**

1. **Another chapter of the same book** (e.g., chapter 1, 2, 3... — does the glossary + final-check + loosened quote-guard deliver the same 95%+ coverage on a different chapter?)
2. **A different book entirely** (does the content-agnostic architecture work on a physics textbook, a novel, a cooking manual? — Rule 1 compliance test)
3. **The SAME chapter re-run** (is the 70/74 coverage stable, or does it vary run-to-run due to LLM variance? The V0.5.14 had Jack but missed Kernberg; V0.5.15 had Kernberg but missed Jack — this LLM variance needs to be characterized + potentially mitigated)

**Specific tasks for the next session:**
- Run V0.5.15 on a DIFFERENT chapter of "Broken Structures Salman Akhtar" (or a different book) + audit the results
- If the coverage is <90% on a new chapter, investigate why (the glossary might not extract as well, or the gap-fill might not target the right authors)
- Characterize the LLM variance (run the same chapter 3× + measure the coverage variance — is it ±2pp or ±10pp?)
- If the variance is high, consider: (a) increasing the final-check rounds (from 1 to 2-3), (b) lowering the temperature further, (c) adding a 2nd glossary extraction pass
- The VRAM overbudget check is now non-blocking (V0.5.14) — verify it doesn't cause issues on a different rig/config
- The `model_vram_override_gb` setting is available — document it in the README for users with special-quant models

## Token + repo

- GitHub token: `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` (one-off URL, scrub after use per Rule 4)
- Repo: `https://github.com/assadigit/Elixir` (branch `refactor/audit-session`)
- Zip: `/home/z/my-project/download/Elixir-V0.5.15.zip`

## Session workflow

1. Clone the repo (if not already): `git clone https://ghp_...@github.com/assadigit/Elixir.git elixir`
2. Checkout `refactor/audit-session` (the V0.5.x lineage)
3. Read this file + CHANGELOG.md (the V0.5.x entries at the top)
4. The user will upload a new conversion output (from a different chapter/book)
5. Audit it (move files to `audit/results/bench_v0XXX/` + create the audit md)
6. If coverage <90% on a new chapter, investigate + fix (content-agnostic — Rule 1)
7. Commit + push + zip per release (Rule 5)
