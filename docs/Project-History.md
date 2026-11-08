# Project-History — Era Summary (long-form story archived)

> **Status:** this file is now a compact era index. The full verbatim
> long-form development story — all 132 original entries, 7,347 lines — now
> lives in [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md) **Part 2**, moved
> verbatim in the Phase-2 token-efficiency pass (branch
> `refactor/audit-session`). Nothing was deleted.
>
> Reading tip: some archived changelog entries cite "Project-History.md line
> NNNN" — those line numbers refer to the original 7,347-line file (now
> archive Part 2), not to this summary.

### Era table

Generated mechanically from the archived `## ` headings (132 total: 128
versioned entries + 4 headings inside one pasted converter-output block in the
V17.2 entry). Counts sum to 132.

| Era | Entries | Themes (from the entry titles) |
|---|---|---|
| V13.x | 52 | 3-Layer chapter-level segmentation; 3-Tier coverage guarantee; additive sections (Key Distinctions, Theoretical Tensions); scholar-reflection layer; VRAM recovery + B4 threshold fixes |
| V15.x | 3 | Enhanced concept extraction; over-delivery caps; judge-appeal visibility |
| V16.x | 1 | Complete prompt overhaul; professional template; hardcoded prompts migrated |
| V17.x | 6 (+4 pasted) | Deterministic preprocessing layer; deterministic judge layer (closed-loop verification); bullet consolidation on heavy model; skip-logic fix |
| V18.1 | 1 | Senior-engineer audit; VRAM fix; no-hardcode rule; security hardening |
| V18.2.x | 36 | Chain-of-thought leakage fix; deterministic post-checks; async LLM client; IQ2_S gold standard; embedder upgrades |
| V18.3.x | 5 | Gold-standard invariant guards; robust segmenter + TOC system; page-based chapter matching; VRAM-aware chunked output |
| V18.4.x | 2 | Embedder hardening + optional mode; phase exit-gate closure; skip-guards |
| V18.5.x | 2 | Lowbit prompt variants; leak-guard counter; front-matter versioning |
| V18.6.x | 5 | post_processing + prompt_assembly extractions; the rolled-back `_build_prompt` extraction (PromptContext crash); gold-standard recovery |
| V18.7–V18.9 | 3 | SummaryValidator extraction; LLMDispatcher leaf extraction; fragment-merge false-positive fixes |
| V18.10–V18.11 | 3 | Ops & reproducibility polish; god-class extraction batches; deadline raise + grammar guard |
| V18.12.x | 4 | Gap-fill prompt-leakage filters; thorough-call Ollama-500 handling; god-class extraction batches 2.6–2.7 |
| V18.13–V18.14 | 5 | Layout-reorder sampling; independent-unit coverage guarantee; looped batch gap-fill; pre-consolidation cap |
| *CHANGELOG.md eras (context)* | — | V18.20.4.x pre-rebrand era → V0.01 versioning reset → V0.4.x current line (24 V0.4.x entries kept in CHANGELOG.md; everything older is archive Part 1) |

### Reading order for a new session

1. `AGENTS.md` — the standing rules (content-agnostic fixes, evidence-first,
   net-green at every commit).
2. `README.md` — what the app is and how to run it.
3. `CHANGELOG.md` — recent releases (the V0.4.x line) plus the evergreen
   "Key design decisions" section.
4. `CHANGELOG_ARCHIVE.md` — **only** when you need pre-V0.4.2 history
   (Part 1 = legacy changelog entries; Part 2 = the long-form story that used
   to be this file).
