# Project History — Elixir (the lean summary)

> A condensed history of the Elixir project's evolution, covering the V18.x era (the "MarkItDown Pro" → "Elixir" transition) + the V0.4.x → V0.5.x era (the verification LAYER + glossary architecture). The full 7,347-line changelog is in git history (commit `bf7495e~1`).

---

## The V18.x era (MarkItDown Pro → Elixir)

The V18.x era built the foundational pipeline: PDF → OCR → chapter segmentation → summarization (master-summary + bullets + thorough + key-distinctions + theoretical-tensions) → post-checks → output.

### Key challenges + what worked / didn't

| Challenge | What happened | Fix | Worked? |
|---|---|---|---|
| **Gap-fill coverage (26%)** | V18.14.0: bullets covered only 26% of source theorists — the gap-fill had a 20-author cap + didn't loop | V18.14.1: removed the cap + looped the batch gap-fill (8 at a time until all covered) | ✓ — reached 100% bullets-only coverage |
| **Prompt leakage** | V18.14.2: the LLM's internal monologue (~5000 chars) leaked into the Key Takeaways — the 4th bullet-generation path wasn't filtering | V18.14.3: filtered ALL 4 bullet paths through `_filter_thinking_bullets` + 7 new leakage patterns | ✓ — all 4 paths now filtered |
| **Ollama 500 (transient LLM failure)** | V18.12.0: the dedicated thorough call crashed on a transient Ollama 500 Server Error | V18.12.1: 3-attempt retry (catches transient 500s) | ✓ — the crash became a retry |
| **IQ2_XXS empty responses** | V18.2.5: low-bit quants (IQ2_XXS) returned empty — Academic Rigor was too demanding for the quant | V18.2.5: disabled Academic Rigor for <13B models + raised temperature | ✓ — the empty-response rate dropped |
| **`_format_years` crash** | V18.2.8: TypeError: `sub() missing argument` — a regex group was optional but the format string expected it | V18.2.8: guarded the regex group access | ✓ |
| **`presence_penalty` / thinking-mode** | V18.2.41: `/no_think` on first attempt FAILED — the model still thought. V18.2.42: `presence_penalty=1.5` Instruct mode | V18.2.42: the `presence_penalty` fix replaced the failed `/no_think` | ✓ — `presence_penalty` is the proven approach |
| **VRAM truncation** | V18.3.3: 27B models on 12GB cards hit the output cap → truncated summaries | V18.3.4: VRAM-aware output expansion + chunked output | ✓ — no more truncation |
| **Chapter matching** | V18.3.2: renamed chapters didn't match the TOC | V18.3.2: page-based chapter-matching fallback | ✓ |
| **Garbled-token sweep** | V18.2.13: fused words (e.g., "persecutionensate") shipped undetected | V18.2.13: deterministic post-checks (the garble detector — later evolved into Pattern A/B/C/D in V0.5.x) | ✓ |

### The gold standards

- **V18.6.4**: the first gold standard — 9/10 score, 17.6 min, coverage 10/10. This was the ROLLBACK point after the V18.6.3 `_build_prompt` extraction failed.
- **V18.2.43**: IQ2_S context raised to 26758 — the second gold standard.
- **V18.2.12**: "Stable pipeline, best version to date" — the V18.x era's stable release.

### The god-class extraction (V18.6.0 → V18.12.0)

The biggest refactor of the V18.x era: extracting the `Summarizer` god-class (~3000 LOC) into:
- `prompt_assembly.py` (V18.6.1)
- `post_processing.py` (V18.6.0)
- `summary_validator.py` (V18.7.0)
- `llm_dispatcher.py` (V18.8.0)
- `_summarize_inner` decision (V18.12.0)
- 15 delegate methods (V18.11.0 + V18.13.0)

**What worked**: the extraction was characterization-test-driven (every extracted method got a characterization test pinning its behavior byte-for-byte). Zero regressions across 462 → 496 tests.
**What didn't**: the V18.6.3 `_build_prompt` extraction FAILED (introduced a regression) → rolled back to V18.6.4 (the gold standard).

### The V18.20.4.x final state

By V18.20.4.x, the pipeline was stable: 5,889 tests, 66% coverage, ruff clean, eval gate OK. The V18.x era ended with the versioning reset to V0.01 (V0.01 = V18.20.4.12).

---

## The V0.4.x era (the verification LAYER + the audit campaign)

The V0.4.x era (V0.01 → V0.4.40) introduced the post-conversion verification LAYER — an LLM pass that verifies the summary against the source for Dates/Names/Omissions/Hallucinations.

### Key milestones

| Version | Milestone | What worked | What didn't |
|---|---|---|---|
| V0.4.22 | The 5-section output format (exec + bullets + thorough + key-distinctions + tensions) | the structured output | — |
| V0.4.23 | The V18.20.3.2 parenthetical-promotion veto (the "quote-guard") | caught misattributed bullets | too strict — dropped bullets for "see also" authors |
| V0.4.26-V0.4.28 | The SWOT + 3-track audit remediation (Pattern C + date-check FPs + coverage + LAYER auto-apply) | the 6-track approach | — |
| V0.4.37-V0.4.39 | The detector false-positive fixes (grammar, attribution, fragment-merge, bold-name) | the D3 LLM-repair pattern | — |
| V0.4.40 | The post-conversion verification LAYER (Dates/Names/Omissions/Hallucinations) | the LAYER concept | the LAYER was dead code on the normal path (the file-existence short-circuit bypassed it) |

### The V0.4.40 LAYER wiring bug

The V0.4.40 verification LAYER ran but its output (`_v_issues`) was **silently dropped** — the `summarization.py` bound the variable but never read it. Fixed in V0.5.1 (the wiring fix).

---

## The V0.5.x era (the glossary architecture)

The V0.5.x era (V0.5.0 → V0.5.15) introduced the **source-glossary architecture** — the user's idea: an LLM-generated glossary (names + dates + terms) used as the coverage ground truth.

### The V0.5.x trajectory

| Version | Coverage | keypoints | Key milestone | What worked | What didn't |
|---|---|---|---|---|---|
| V0.5.0 | — | — | The deterministic date-extraction module (8 format classes) | the date-check | — |
| V0.5.3 | — | — | The verification LAYER re-wired (P0-2 — ran before checkpoint save) | the LAYER finally ran | the LAYER was dead code on checkpointed chapters |
| V0.5.4 | — | — | The 6-track audit remediation (A-F) | Pattern C + date-check FP elimination | the Pattern C lexicon check was BROKEN (placed in Pattern A) |
| V0.5.5 | 69/74 (93%) | 81 | The baseline audit (5 authors missing: Jack, Morey, Ndtei, Rettersol, Bak) | the baseline | the 5-author gap |
| V0.5.6 | 69/75 (92%) | 83 | The glossary architecture (fused into master-summary) | the concept | the fused prompt overwhelmed the model → 3 empty returns |
| V0.5.7 | 48/74 (65%) | 60 | The separate glossary call (V0.5.7) | the separation | the LLM didn't output `<name_glossary>` XML block |
| V0.5.8 | 42/74 (57%) | 65 | max_tokens 4096→8192 + strip_thinking | — | the caller passed max=4096 (overriding the default) |
| V0.5.9 | 53/74 (72%) | 72 | The 8192 fix (the caller override fixed) | — | the LLM STILL didn't output XML (the format was the issue) |
| V0.5.10 | HANG | — | XML→markdown headers + field_phases fix + regex fallback + markitdown thread | the markdown format + 3-tier parser | the markitdown background-thread DEADLOCKED (30-min hang) |
| V0.5.11 | 62/74 (84%) | 69 | The glossary FINALLY extracted (markdown headers worked!) | the 📖 glossary line fired | the glossary not wired to the gap-fill |
| V0.5.12 | — | — | The gap-fill wiring (source_glossary → batch_gap_fill) | — | the VRAM overbudget block (hardcoded 12.9 GB) |
| V0.5.13 | — | — | torch.cuda.mem_get_info() VRAM fix | — | didn't work on Windows (per-process VRAM) |
| V0.5.14 | 68/74 (92%) | 84 | Non-blocking VRAM + glossary + final-check FIRED | ALL 5 V0.5.5 missing covered, final-check added 19/20 | 5 authors dropped by post-checks (parenthetical_promotion + attribution-edge) |
| V0.5.15 | 70/74 (95%) | 82 | Post-check safety net (keep regex-grounded bullets) | ALL 5 V0.5.14 missing closed, 95% coverage (BEST) | 4 LLM-variance missing (Jack, Ndtei, Pao, Grunberger) |

### What worked (the V0.5.x wins)
1. **The markdown-header glossary format** (V0.5.10) — the Ternary-Bonsai-2-27B model produces markdown headers naturally (couldn't follow XML tags).
2. **The separate glossary call** (V0.5.7) — separating the glossary from the master-summary prevented the overwhelming that caused 3 empty returns.
3. **The 3-tier parser** (V0.5.10) — catches the model's actual output format regardless (XML backward compat, markdown headers, lenient bare-bullets).
4. **The side-channel wiring** (V0.5.12) — passing `source_glossary` to `batch_gap_fill` enabled the V0.5.6 final-check.
5. **The non-blocking VRAM check** (V0.5.14) — the param-count estimate was wrong for special-quants; making it non-blocking + querying nvidia-smi was the fix.
6. **The loosened quote-guard** (V0.5.6 + V0.5.10 + V0.5.15) — the glossary/regex IS the grounding; the author doesn't need to be an "active subject" or "co-occur with the claim's key phrases."

### What didn't work (the V0.5.x lessons)
1. **The fused glossary prompt** (V0.5.6) — overwhelming the model with dual-output (summary + glossary) caused empty returns.
2. **The XML `<name_glossary>` format** (V0.5.7-V0.5.9) — the model can't follow XML-tag format instructions, even with strip_thinking + explicit prompts.
3. **The markitdown background-thread import** (V0.5.10) — Python's global import lock deadlocks when a background thread imports while the main thread is also importing.
4. **The `torch.cuda.mem_get_info()` VRAM fix** (V0.5.13) — returns per-process VRAM on Windows, not GPU-wide (the llama-server process's VRAM isn't visible).
5. **The hardcoded 12.9 GB VRAM estimate** (V0.5.12-V0.5.14) — the param-count formula (27B × 0.31 ternary = 12.9 GB) is wrong for special-quant models (the user's 7.6 GB model was estimated at 12.9 GB → false overbudget → blocked the conversion).
6. **The post-checks dropping glossary-grounded bullets** (V0.5.14) — the loosened quote-guard only applied during the gap-fill, NOT during the post-checks that run after. Fixed in V0.5.15.

---

## The architecture (V0.5.15 final state)

```
source text → extract_glossary_via_llm (separate call, 8192 tokens, markdown headers)
           → parse_name_glossary (3-tier: XML compat, markdown headers, lenient bare-bullets)
           → persist_glossary (.glossary.md)
           → set_chapter_glossary (side-channel)
           → batch_gap_fill (source_glossary passed)
              ↳ V0.5.6 glossary-grounded loosened quote-guard ✓
              ↳ V0.5.10 regex fallback ✓
           → V0.5.6 final-check round 4 (glossary-grounded targeted gap-fill) ✓
           → post-checks (V0.5.15 safety net: keep regex-grounded bullets) ✓
           → verification LAYER (glossary-grounded coverage check + cross-reference) ✓
```

**V0.5.15 results**: 70/74 (95%) author coverage, 82 keypoints, 0 hallucinations, 39 bullets grounded. The glossary architecture delivers end-to-end.
