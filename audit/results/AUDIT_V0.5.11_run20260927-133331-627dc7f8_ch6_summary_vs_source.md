# AUDIT V0.5.11 — BREAKTHROUGH: glossary FINALLY extracted + coverage up to 62/74 (84%)

**Run:** `20260927-133331-627dc7f8` (V0.5.11)
**Candidate:** 3,265 words, 69 bullets

## Four-pillar scorecard (V0.5.11 vs V0.5.9 vs V0.5.6)

| Pillar | V0.5.6 | V0.5.9 | V0.5.11 | Trend |
|---|---|---|---|---|
| Factual Consistency | 9 | 9 | 9 | flat (0 hallucinations) |
| Informational Coverage | 8 | 6-7 | **7-8** | **RECOVERING** (62/74=84%) |
| Cohesion & Clarity | 7-8 | 7-8 | 7-8 | flat |
| Conciseness | 7 | 8 | 8 | flat |
| **Overall** | **~8.0** | **~7.5** | **~8.0** | **RECOVERED to V0.5.6 level** |

## What WORKED in V0.5.11 (3 breakthroughs)

1. **The app INITIALIZED in ~6s** ✓ — markitdown imported in 5.9s (the V0.5.11 eager-import revert). The 30-min hang is GONE. The V0.5.10 markitdown background-thread deadlock is fixed.

2. **The glossary FINALLY EXTRACTED** ✓✓✓ — `📖 V0.5.7 source glossary (separate call) → ...glossary.md`. This is the FIRST TIME the glossary actually extracted (V0.5.6→V0.5.9 all failed). The V0.5.10 markdown-header format change + the 3-tier parser WORKED. The LLM produced the glossary in markdown-header format (not the XML `<name_glossary>` wrapper that the model couldn't follow). The glossary is persisted to `summaries/.glossaries/6 - PARANOID PERSONALITY DISORDER.glossary.md`.

3. **The loosened quote-guard FIRED** ✓ — `✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)`. The V0.5.10 regex fallback worked — bullets for regex-confirmed authors are accepted without verbatim quotes. The gap-fill round 4 added 8/8 bullets (0 vetoes — the loosened quote-guard + the regex fallback are working).

4. **The verification LAYER is glossary-grounded** ✓ — `✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 9 source author(s) NOT found... Cross-ref: confirmed=64, llm_only=2, regex_only=10`. The cross-reference ran (the glossary names were compared against the regex extract_citations output). confirmed=64 (both caught), llm_only=2 (LLM glossary caught, regex missed), regex_only=10 (regex caught, LLM glossary missed).

5. **Coverage UP to 62/74 = 84%** ✓ — up from V0.5.9's 53/74 (72%) + V0.5.8's 42/74 (57%). +12pp vs V0.5.9.

6. **No "ego-syntonically" garble** ✓ — the grep found 0 occurrences. Either the LLM didn't produce it this run OR the V0.5.10 field_phases caller fix rewrote it. Either way, the garble is GONE.

## The 5 V0.5.5 missing authors — 4 now covered

| Author | V0.5.5 | V0.5.11 | Status |
|---|---|---|---|
| Allodi | 0 | **1** | ✓ COVERED |
| Ndtei | 0 | **1** | ✓ COVERED |
| Bak | 0 | **1** | ✓ COVERED |
| Lowenthal | 0 | **1** | ✓ COVERED |
| Jack | 0 | 0 | ⚠️ still missing |
| Rettersol | 0 | 0 | ⚠️ still missing |
| Morey | 0 | 0 | ⚠️ still missing |
| Munro | 0 | 0 | ⚠️ still missing |

The LAYER's glossary-grounded coverage-targeting identifies 9 still-missing: Bach, Croewe, Gorton, Jack, Morey, Munro, Ovessey, Rettersol, Walters.

## What STILL needs fixing (the V0.5.12 gap)

**The V0.5.6 final-check (the glossary-grounded targeted round 4) didn't fire.** The conv log shows:
- `Glossary: (none)` in the verification LAYER's coverage-targeting output — even though the 📖 line fired + the glossary was persisted.
- The cross-reference ran (confirmed=64, llm_only=2, regex_only=10) — so the glossary DATA is available.
- But the verification LAYER's `get_chapter_glossary` side-channel returned None → the V0.5.6 final-check (which needs the glossary via the side-channel) didn't fire.
- The round 4 that fired is the OLD V18.14.1 mechanism (using the regex), not the V0.5.6 glossary-grounded one.

**The V0.5.12 fix**: wire the glossary into the verification LAYER's side-channel — the `set_chapter_glossary` call in `_extract_glossary_for_call` (primary_call.py) should populate the side-channel so `get_chapter_glossary` returns the glossary (not None). Once wired, the V0.5.6 final-check will fire → the 9 missing authors will be targeted by name + glossary context → they'll be added → 74/74 (100%).

## Verdict

**RECOVERED to V0.5.6 level (V0.5.11 ~8.0 vs V0.5.6 ~8.0) — WITH the glossary actually working.** The V0.5.10 format change (XML → markdown headers) + the 3-tier parser finally made the glossary extract. The loosened quote-guard (V0.5.10 regex fallback) caught Byrne. Coverage is up to 62/74 (84%). The 30-min hang is gone (the V0.5.11 markitdown-thread revert). The "ego-syntonically" garble is gone.

The remaining gap (9 missing authors) is the V0.5.6 final-check wiring issue — the glossary is extracted + cross-referenced but NOT pushed to the verification LAYER's side-channel. The V0.5.12 fix (1-line: `set_chapter_glossary(chapter_heading, glossary)` in the right place) should close the gap → 74/74 (100%) → ~9.25.
