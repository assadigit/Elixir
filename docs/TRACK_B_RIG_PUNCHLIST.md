# Track B — rig punch-list (the rig-required SWOT top-5 queue)

> **Status:** OPEN — the sandbox-doable prep is done (B2 runbook, B3 E6 guards,
> B4 characterization net); the items below need the owner's Windows rig to
> validate. Per AGENTS.md Rule 2 (evidence-first), the sandbox cannot generate
> validating evidence for these (no local LLM, no sentence-transformers, no
> real Qt GUI). This document is the executable plan for each.
>
> **Opened:** V0.4.28 (Phase-7 SWOT top-5 Track B). **Supersedes:** the
> V0.4.26 backlog triage in `CHANGELOG.md` V0.4.26 + the Track-B note in
> `SESSION_REPORT.md` §Phase 9.

## B1 — the V0.4.26 clarity backlog (items 1-4)

The five ch.1-clarity fixes from the V0.4.25 benchmark audit
(`audit/results/AUDIT_V0.4.25_run20260924-151700-2bd82b60_ch1_summary_vs_source.md`
§"Backlog for V0.4.26"). Item 5 (markdown year formatting) shipped in V0.4.26;
items 1-4 are below.

### B1.1 — Theoretical-tensions additive robustness (`core/summarisation/additive_sections.py`)

**The defect (V0.4.25 ch.1):** the additive followup produced 9 tension lines;
4 were dropped at intake as truncated (unmatched quote/paren, dangling tail);
the postcheck then dropped the remaining 5 as truncated. A five-section output
shipped as four sections — the Theoretical Tensions section died honestly.

**The fix (the backlog spec):** apply the V18.20.3.2 mass-truncation retry
PER-SECTION (not the whole additive call, which already retries) with a
structural prompt for tension lines ("X vs. Y — one line, balanced quotes"),
and never let a 4-line drop take the section below 2 lines without one retry.

**Why rig-blocked:** the "structural prompt" is a PROMPT change — a new
instruction to the LLM. Per Rule 3, a prompt change shifts the
`prompt_manifest_hash` → the eval gate FAILS until re-baselined, and
re-baselining requires the owner's judgment (is the new prompt better on the
real LLM?). The sandbox's z-ai proxy cannot validate that the structural
prompt actually produces balanced tension lines (the V0.4.25 benchmark used a
cloud model; the rig's 27B quantized model behaves differently).

**Rig data needed:**
1. Run the V0.4.25 ch.1 benchmark with the new per-section retry + structural
   prompt on the rig's 27B model.
2. Confirm the Theoretical Tensions section ships ≥2 balanced lines (the
   "never below 2 lines" floor).
3. Re-baseline the eval gate (`scripts/eval_summary.py --save-baseline`) in
   the same commit if the output improved (Rule 3).
4. Confirm `prompt_manifest_hash` change is intended + the 6 golden chapters
   don't regress.

**Implementation sketch (for the owner):** in `_ensure_additive_sections`, after
the existing whole-call retry, add a per-section retry for `theoretical_tensions`
only: parse the tt text, count non-truncated lines, if < 2, fire ONE more
targeted call with the structural prompt ("For each tension, write one line:
'X vs. Y — <one-sentence contrast>'. Balanced double-quotes. No trailing
punctuation."). Keep the better attempt (same criterion as the whole-call retry).

### B1.2 — Enumeration-stem self-containment (`core/summarisation/enumeration.py`)

**The defect (V0.4.25 ch.1):** 3 enumeration-bullet stems were context-free
slices — "His work provides developmental basis for —", "This he sees being
accomplished by —", "Can divided into five categories —". The V0.4.24
sentence/word alignment (`_aligned_stem` at `enumeration.py:528`) fixed the
mid-token slicing but NOT the self-containment (the stem doesn't name its
author).

**The fix (the backlog spec):** stems must be self-contained — the label must
name its author ("Jacobson's contributions divide into five categories:"),
never "His work…" / "This he sees…" / "Can divided…".

**Why rig-blocked:** making the stem name the author requires threading the
runtime-analysis author list into `_find_block_stem` (the stem-builder) +
a pronoun-replacement heuristic (replace "His work"/"This he"/"Can divided"
with "<Author>'s work"/etc.). The author name MUST come from `extract_citations`
(Rule 1 — no hardcoding). The heuristic's quality (does "Jacobson's
contributions divide into five categories:" read well?) depends on the source
text structure, which varies per chapter — the sandbox can't validate the
replacement reads well without the real LLM output pairing. A flag-only
detector (log context-free pronoun stems) is sandbox-safe but its value is
unvalidated (might log false positives the rig would tune out).

**Rig data needed:**
1. Run the V0.4.25 ch.1 benchmark; capture the consolidated bullets' stems.
2. Identify which stems are context-free (start with "His"/"This he"/"Can
   divided"/etc.).
3. For each, confirm the runtime analysis (`extract_citations` output) has
   the author name available at the stem-builder's call site.
4. Implement the pronoun-replacement (thread `analysis` into `_find_block_stem`;
   replace the context-free pronoun with `<Author>'s …`); confirm the resulting
   stems read well on ≥3 chapters (not just ch.1).

**Rule-1 compliance:** the author list comes from `extract_citations` (the
runtime deterministic analysis), NEVER hardcoded. The replacement is a generic
pronoun→author-name substitution (content-agnostic).

### B1.3 — Quote-pair balancer extension (`core/summarisation/postchecks/garble/quote_repair.py`)

**The defect (V0.4.25 ch.1):** ~9 unbalanced quote marks in the thorough/exec
text (e.g. `ego feeling" and "ego nuclei` — a swapped close-then-open pair;
`"good enough mother` — no closer; `concepts of ego feeling" and "ego nuclei` —
swapped pair).

**Existing coverage:** `repair_stray_quotes` (V0.20.5) +
`repair_stray_quotes_v2` (V0.20.6, three D1/D2/D3 detectors) +
`repair_d3_quotes_via_llm` (V0.4.11/V0.4.13, content-agnostic LLM repair)
ALREADY run on bullets/exec/thorough (`postchecks/field_phases.py:215,219,587,
589,741,747`). The ch.1 still had ~9 unbalanced quotes despite v2 → v2 doesn't
fully catch the close-then-open-then-and subtype.

**The fix (the backlog spec):** add a quote-balance pass (swap/reopen misplaced
pairs like `ego feeling" and "ego nuclei`, drop orphaned quote chars).

**Why rig-blocked:** a deterministic close-then-open swap detector risks shipping
WRONG fixes (v2's D3 is flag-only precisely because auto-repair is risky — a
deterministic rule can't tell WHERE to insert the missing pair without sentence
context). The sandbox can implement the LOGIC net-green, but validating it
doesn't ship wrong fixes needs the real LLM's quote patterns (which I can't see
here). A flag-only detector (mirroring D3) is sandbox-safe but may overlap with
existing D2/D3 flagging — the owner must verify on the rig that it adds value
(not noise).

**Rig data needed:**
1. Run the V0.4.25 ch.1 benchmark; capture ALL lines with unbalanced quotes
   (the ~9 + any others).
2. Classify each: (a) orphan closer, (b) orphan opener, (c) swapped
   close-then-open-then-and, (d) long-span (D3 already flags).
3. For class (c) only: implement a conservative auto-swap (the
   `word" conj "word` → `"word" conj "word"` pattern, where conj ∈ {and, or, ,}).
   Flag + log every swap; the owner audits the log for false positives before
   enabling auto-repair.
4. For classes (a)/(b): leave to `repair_d3_quotes_via_llm` (the LLM semantic
   repair is the right tool for context-dependent fixes).

**Precedent:** the V0.4.24 dropped-digit year auto-repair proved this class of
deterministic fix ships safely — but year digits are far more constrained than
quote chars. Be more conservative: flag-only first, auto-swap only after rig
validation.

### B1.4 — Sociocultural name floor (`core/summarisation/thorough_theorist_floor.py`)

**The defect (V0.4.25 ch.1):** the sociocultural extension's author list
shipped 3/6 names (Fromm, Wheelis, Lynd, Lifton, Lasch, Kovel — Lasch/Kovel
absent); Spiegel's "pooling" absent; Marx/Durkheim (alienation/anomie
foundations) absent.

**Existing coverage (verified this session):** the deterministic analyzer's
`extract_citations` (`core/preprocessing/deterministic_analyzer.py:293`) is
**category-agnostic** — it extracts ALL author-year citations via regex (Author
(Year), Author and Author (Year), Author et al. (Year)). The theorist floor
(`thorough_theorist_floor.py:121`) checks `check_coverage(analysis, thorough)`
against whatever authors the analyzer found — so the floor ALREADY covers
sociocultural authors IF they're cited with year parentheticals. The gap is the
quote-guard (the audit noted Spitz/Loewenstein gap-fill bullets were generated
then DROPPED for lacking a verbatim quote).

**The fix (the backlog spec):** the sociocultural roster needs the same
quote-guarded gap-fill treatment as the psychoanalytic authors.

**Why rig-blocked (HIGHEST risk — anti-hallucination threat):** the gap is the
quote-guard, NOT the floor. Loosening the quote-guard (accepting gap-fill
bullets without a verbatim quote) would directly threaten the anti-hallucination
guarantee (the F4 ≥25% source-overlap filter + the verbatim-quote requirement
are the core defense against fabricated claims). This MUST NOT be loosened
without rig validation that the loosened guard doesn't ship fabricated quotes.
The sandbox cannot generate that evidence (no embedder for the semantic
fact-check, no real LLM for the gap-fill).

**Rig data needed:**
1. Run the V0.4.25 ch.1 benchmark; capture the gap-fill bullets that were
   DROPPED for lacking a verbatim quote (Spitz, Loewenstein, + the sociocultural
   authors).
2. For each dropped bullet: is the claim FACTUAL (the author is in the source
   but the quote wasn't extractable) or FABRICATED (the LLM invented it)?
3. ONLY if factual: design a STRICTER sociocultural-floor pass (require BOTH the
   author name in the source AND a verbatim quote, but lower the F4 overlap
   threshold for sociocultural-context authors only — a category the runtime
   analysis can derive from the chapter's structure, NOT a hardcoded list).
4. Confirm zero fabricated quotes ship on ≥3 chapters before enabling.

**Rule-1 compliance (critical):** the sociocultural author list MUST come from
`extract_citations` (runtime), NEVER hardcoded (Rule 1 forbids "a list of
theorists to always cover"). The V0.4.26 backlog item 4 named Fromm/Wheelis/
Lynd/Lifton/Lasch/Kovel as EXAMPLES from ch.1; the FIX must derive the list
generically from the runtime analysis of WHATEVER book is being converted.

---

## B2 — T1 rig-test checklist

**Status:** runbook written — see `docs/RIG_TEST_CHECKLIST.md`. The sandbox
cannot execute it (no Windows, no real Qt GUI, the 36 skips are absent
deps/fixtures). The owner runs it on the Windows 10/11 rig.

## B3 — `async_provider.py` + E6 wire/delete

**Status:** the ADR is `docs/ASYNC_PROVIDER_DECISION.md` (committed V0.4.27,
`3ac5979`). The DECISION is the owner's, pending the rig data:
1. The rig's per-chapter wall-clock breakdown (is LLM time still 98.5% on the
   27B quantized model? if single-GPU-VRAM-bound, the async lever won't
   materialize → DELETE).
2. The independent-stage overlap opportunity (does `stage_overlap.py` already
   cover the grounding-check ∥ self-review case? if yes → DELETE).
3. The E6 sleep-refactor cost (replacing `_time.sleep`/`time.sleep` with
   `asyncio.sleep` at the 3 sites — mechanical, but `openai_compat_provider.py:265`
   is a live Batch-API poll).

**Sandbox-doable follow-up (done V0.4.28):** the E6 "sync-only" guard comments
at the 3 sleep sites (so a future async-wiring attempt doesn't miss them).

**Provisional recommendation (from the ADR):** DELETE if the rig is
single-GPU-VRAM-bound (likely — 12 GB RTX 3060 + 9.3 GB IQ2_S leaves ~1.5 GB
headroom); WIRE if there's GPU headroom or the cloud path is primary (ship as
V0.4.29 with byte-identical output proof per the V0.19 levers' pattern).

## B4 — `summarizer._summarize_inner` de-monolith round

**Status:** the SWOT-recommended first step — the **characterization net** —
is done V0.4.28 (test-only, like A2; see the B4 commit). The EXTRACTION itself
stays queued:

**Why rig-blocked:** `_summarize_inner` (349 ln, `summarizer.py:1429-1777`) is
the V0.11 W1 god-class residue, with 20+ self-deps. The NEW_SESSION_PROMPT
flags it as "too risky to extract — V18.6.3 crash mitigation" (the V18.6.3
crash on `_build_prompt` extraction was undiagnosed). With the characterization
net pinning behavior, the extraction becomes testable (net-green-checkable),
but VALIDATING the moved code's output equivalence needs the real LLM (the eval
gate uses stored fixtures; it won't catch a behavior drift in the moved code on
fresh inputs).

**Rig data needed:**
1. The characterization net (done V0.4.28) pins `_summarize_inner`'s behavior.
2. On the rig: extract one cohesive concern from `_summarize_inner` (e.g., the
   gap-fill orchestration, or the self-review dispatch) behind the facade
   re-export pattern (S4), one commit per extraction (Rule 2).
3. Re-run the V0.4.25 ch.1 benchmark after EACH extraction; confirm byte-
   identical output (the V0.19 levers' proof pattern) — the eval gate's stored
   fixtures won't catch drift; the real benchmark will.
4. The 5,853-test net + the new characterization net catch control-flow
   breakage; the rig benchmark catches output drift.

**Precedent:** the Phase-3 converter extraction (2,175→1,577, `convert()`
1,054→601) used exactly this pattern (characterization-first, byte-verbatim
move, facade re-export, one commit per extraction) + stayed net-green. The
V18.6.3 crash was on `_build_prompt` (a DIFFERENT method, frozen by design —
T5); `_summarize_inner` is the next target, not the frozen one.

---

## Summary: what the sandbox did vs what the rig must

| Item | Sandbox-done (V0.4.28) | Rig-required |
|---|---|---|
| B1.1 tensions retry | this punch-list (design + validation plan) | implement the per-section retry + structural prompt; re-baseline eval gate; validate on ch.1 |
| B1.2 stem self-containment | this punch-list (design + Rule-1 compliance) | thread `analysis` into `_find_block_stem`; pronoun-replacement; validate stems read well on ≥3 chapters |
| B1.3 quote-pair balancer | this punch-list (precedent + risk) | classify the ~9 unbalanced quotes; flag-only detector first; conservative auto-swap after rig validation |
| B1.4 sociocultural floor | this punch-list (anti-hallucination constraint) | DO NOT loosen the quote-guard blind; stricter per-category pass only after confirming dropped bullets are factual |
| B2 rig-test checklist | `docs/RIG_TEST_CHECKLIST.md` runbook | execute on Windows 10/11 rig |
| B3 async_provider | `docs/ASYNC_PROVIDER_DECISION.md` ADR + E6 guard comments | the wire/delete decision (pending the 3 rig-data items) |
| B4 _summarize_inner | the characterization net (test-only) | the extraction (one concern per commit, byte-identical-output validation per extraction) |
