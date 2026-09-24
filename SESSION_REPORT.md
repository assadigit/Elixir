# Elixir — Audit, Refactor & Benchmark Session Report

- **Repo:** https://github.com/assadigit/elixir @ main e6032ee (V0.4.25)
- **Branch:** `refactor/audit-session`
- **Baseline captured BEFORE any change** (Phase 0) — see §6 Metrics.
- **Method:** AGENTS.md standing rules honored (content-agnostic fixes, evidence-first, net-green at every commit, no history rewrite, one logical change per commit).

---

## Phase 1 — SWOT Analysis of the Codebase (baseline: V0.4.25, 5812 tests green)

Severity: 1 (minor) – 5 (critical). All counts verified on the baseline commit; evidence is file/line-anchored.

### Strengths

| # | Item | Sev | Evidence | Action this session |
|---|---|---|---|---|
| S1 | Exceptional test safety net: 5,812 passing characterization/property/golden tests; 65% global coverage with ≥80% per-package gates (llm 95% / pdf 81% / summarisation 91%) | 5 | baseline run `/home/z/audit-tools/baseline_pytest_nocov.txt`; pyproject `addopts`; CI gates | Treat as the contract: every refactor commit must keep the net green (Rule 3) |
| S2 | Deterministic accuracy harness: 6 golden chapters + `scripts/eval_summary.py` scorecards + `make eval-check` regression gate, mutation-validated | 5 | `scripts/eval_summary.py`, `tests/test_p4_eval_gate.py`, CI "Accuracy eval gate" step | Use as the quality-benchmark instrument for Phase 6 and as regression detector for Phase 3 refactors |
| S3 | Disciplined engineering hygiene: pinned ruff (0.16.8), fresh complete lockfile, gated pip-audit with waiver policy, zero secrets / zero bare-excepts / zero mutable-default-args / zero open TODOs, keychain-routed credentials (11 paths) | 4 | census items 2/8/14; `core/system/secrets.py`; `requirements.lock` | Keep gates green at every commit; reuse waiver discipline for any new findings |
| S4 | Proven de-monolithization pattern: facade re-export + byte-for-byte characterization tests; summarizer.py already reduced 5,803 → 1,990 LOC through 15+ extractions with stable public API | 4 | dep graph; V0.4.19 changelog (`aeac74b`); `core/summarisation/` module zoo | Reuse exactly this pattern in Phase 3 (extractions keep old import paths stable) |
| S5 | Content-agnostic enforcement (anti-benchmax): mechanical tests scan runtime code for book-derived names/concepts | 3 | AGENTS.md Rule 1; `tests/test_v182039_audit_fixes.py` | Guarantees Phase 3–4 refactors stay generic; never special-case the test book |
| S6 | Strong observability: conversion manifest, provenance stamps, `drops.jsonl` quarantine audit trail, structured logging, crash-report zips, cache hit-rate summaries | 3 | `core/obs/*`, `core/system/crash_report.py`, `core/system/provenance.py` | Use logs as design-review evidence in Phase 5 |

### Weaknesses

| # | Item | Sev | Evidence | Action this session |
|---|---|---|---|---|
| W1 | Massive AI-context doc load: CHANGELOG.md ≈132.9K tokens + Project-History.md ≈103K + README ≈7.5K + docs/ ≈33.3K ≈ **174K tokens** per AI session | 5 | `wc -c` on baseline; changelog scan (7,911 + 7,347 lines; internal + cross-file duplication found) | Phase 2: compact to recent + archive; target ≥80% reduction with zero information loss |
| W2 | Remaining monoliths: text_preprocessor_concepts 2,444 · converter_impl 2,175 (fan-out 31) · segmenter 2,084 · summarizer 1,990 (fan-out 38/fan-in 26) · chapter_phases 1,965 · text_preprocessor_impl 1,929 | 4 | dep graph (`/home/z/audit-tools/dep_graph.py`); README roadmap item 12 ("decomposition round 3") | Phase 3: propose extraction plan, then incremental one-commit-per-extraction with tests |
| W3 | 140 hard exception swallows (`except …: pass`), 84 of them `except Exception` + pass — silent failure modes | 4 | census item 1; e.g. `core/docx/builder.py:117`, `controller.py:946`, `main.py:51` | Phase 4/5: catalogue + flag; fix only highest-risk core paths; no mass rewrite |
| W4 | Stale/contradictory docs: README "Project Status" says V0.13 (actual V0.4.25); "Known Issues" claims summarizer ≈5,600 lines (measured 1,990); translation-default claim contradicts `docs/USER_OLLAMA_MODELS.md` | 3 | README.md:445, :481, :211 vs `docs/USER_OLLAMA_MODELS.md:47` | Phase 2: correct the stale claims |
| W5 | 55 hardcoded Windows path literals in runtime code incl. machine-specific `G:\` defaults | 3 | census item 4; `utils/settings.py:782-794`, `core/pipeline/checkpoint.py:11` | Phase 5: recommend centralizing into settings defaults (flag — behavior-adjacent) |
| W6 | Timeout scatter: 65 call sites, 11 distinct magic values (2…600s), no central policy | 3 | census item 6; `core/pipeline/conversion/summarization.py:524-651` | Phase 5: recommend a timeout policy table (fix-later; churn risk) |
| W7 | Hygiene gaps: `.venv/` missing from .gitignore; two AST-sweep tests parse the entire venv (12 warnings + CI time) | 2 | census item 13; `tests/test_v182046_p5_dialog_split.py:179`, `tests/test_v182047_p5_services_decomp.py:440` | Phase 2 (.gitignore) + Phase 4 (test skip, test-only change) |
| W8 | Coverage deserts: core/extract 0%, core/ocr/unlimited_ocr 0%, core/models/config_views 0%, outputs service formatters 8–52% | 2 | baseline coverage table | Phase 3: characterization tests FIRST for any touched low-coverage module |
| W9 | `utils/settings.py` is a 1,608-LOC hub with fan-in 83 (every module imports it); schema split across two files | 2 | dep graph | Phase 5: recommend later split (store vs schema vs defaults) |
| W10 | Book-derived ground-truth/audit content committed in-repo (≈132KB) — copyright exposure + token weight | 2 | `docs/ground_truth/`, `audit/results/` | Flag to owner (T6); keep — deliberate evidence per AGENTS.md |

### Opportunities

| # | Item | Sev | Evidence | Action this session |
|---|---|---|---|---|
| O1 | Token-cost reduction ≥150K tokens/session via changelog compaction + history archival | 5 | changelog scan: keep-portion is 1,415/7,911 lines (18%) | Phase 2 (execute now) |
| O2 | De-monolithization round 3 on converter_impl / segmenter / text_preprocessor_concepts following the S4 pattern | 4 | dep graph; precedent: 15+ safe extractions | Phase 3 (execute now, bounded scope) |
| O3 | Dead-code sweep: vulture + import tracing; known frozen candidate (`prompt_assembly.PromptContext` unused by design) | 3 | README Known Issues #4; NEW_SESSION_PROMPT | Phase 4: table + high-confidence deletions only, whitelist the frozen code |
| O4 | Test-suite speedup: skip `.venv` in AST sweeps; the legacy `tests/test_ground/*.ts` bun scripts are superseded by the Python plugin | 3 | census item 13; `tests/plugins/golden_master_audit.py` port | Phase 4: test-only changes (flag .ts deletion for owner) |
| O5 | Lint ratchets: re-enable deferred rules (E701/E702 ≈150 sites, SIM105 ≈50) per-file during extractions | 2 | pyproject ignore list with rationale | Flag for later (mechanical churn, no behavior value) |
| O6 | mypy is warn-only in CI — gradual tightening possible | 2 | ci.yml typecheck job (`continue-on-error: true`) | Phase 5 recommendation only |
| O7 | requirements.txt duplicates pyproject `[project.dependencies]` (drift risk) | 2 | diff of both files | Phase 2: keep as-is (install docs reference it); flag for later single-sourcing |

### Threats

| # | Item | Sev | Evidence | Action this session |
|---|---|---|---|---|
| T1 | Headless test environment: 55 skips (Qt GUI tests) mean UI regressions are invisible in CI/this sandbox; app targets Windows 10/11 | 4 | baseline skip reasons | Keep UI-layer changes at zero; list rig-test items for owner |
| T2 | Single-maintainer, ~22 commits/day AI-driven cadence — bus factor + drift risk | 3 | git log 2026-09-17→09-23, 147 commits, 4 authors | SESSION_REPORT backlog + worklog for continuity |
| T3 | `markitdown[all]` pulls a very wide transitive closure (azure SDK, youtube-transcript-api, …) — attack surface + install weight | 3 | requirements.lock (105+ pins) | Phase 5: recommend slimming to used extras |
| T4 | Windows-first literals (`G:\`, `C:\`) break portability | 2 | census item 4 | Phase 5 recommendation (settings-default centralization) |
| T5 | Frozen-by-design dead code (`PromptContext`/`build_primary_prompt`) risks accidental deletion by future dead-code passes | 2 | README Known Issues #4 | Phase 4: explicit whitelist entry |
| T6 | Book-derived ground-truth files in a public repo — copyright gray zone | 2 | `docs/ground_truth/` | Flag to owner now |

### Session Strategy (explicit)

- **Leverage S1+S2 as the safety contract.** Every commit in Phases 2–4 runs the full suite + ruff; any extraction that cannot stay green is reverted. The eval gate (`make eval-check`) guards output quality, not just code paths.
- **Leverage S4's extraction pattern for Phase 3** (facade re-export keeps `from core.x.y import z` stable; characterization tests pin bytes BEFORE the extraction moves).
- **Mitigate W1 via Phase 2** (O1): compaction is docs-only; the net proves zero behavior change; the rebrand-sweep test allowlist is updated in the same logical change-set so the gate stays honest.
- **Mitigate W2 via Phase 3** (O2): one monolith, one extraction, one commit; characterization tests FIRST where coverage is thin (W8).
- **Mitigate W3/W5/W6 by cataloguing and flagging** (evidence-first; Rule 2 — smallest change the evidence supports), not mass-fixing.
- **Mitigate W7 immediately** — trivial, zero-risk.
- **Guard T1** — no UI-layer edits this session; rig-test checklist in the backlog.
- **Guard T5** — the frozen V18.6.3 pattern is whitelisted in the Phase 4 dead-code report.
- **T2/T6** — surfaced to the owner in the final report; not actionable in-repo beyond documentation.

---

## Phase 3 — Split Monolithic Modules

**Scope:** one monolith (chosen by pain score), decomposed through characterization-first, byte-verbatim extractions — one commit per extraction, net green at every commit. No UI-layer edits; no import-surface changes; `PromptContext` untouched.

### Monolith ranking (Task 3-plan)

Weights: LOC / fan-out / fan-in / churn / un-coverage / responsibilities = 0.20/0.15/0.15/0.15/0.20/0.15, each normalized to the cohort max. Churn = touches within a fixed last-40-commit window.

| Rank | Module | LOC | Fan-out / fan-in | Churn | Coverage | Pain | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `core/pipeline/converter_impl.py` | 2,175 | 31 / 6 | 4 (most-touched) | 72% | **0.69** | **CHOSEN** (also README roadmap item 12's own target) |
| 2 | `core/summarisation/summarizer.py` | 1,990 | 38 / 26 | 3 | 84% | 0.66 | next round (`_summarize_inner`) |
| 3 | `core/preprocessing/deterministic_analyzer.py` | 1,810 | 3 / 21 | 1 | 70% | 0.41 | not this round |
| 4 | `core/segmentation/segmenter.py` | 2,084 | 10 / 5 | 0 | 59% | 0.35 | not this round (0 churn, cohesive) |
| 5 | `core/outputs/packets/generator.py` | 1,829 | 10 / 2 | 0 | 52% | 0.34 | needs characterization first |
| 6 | `core/summarisation/chapter_phases.py` | 1,965 | 10 / 2 | 2 | 98% | 0.30 | not this round |
| 7 | `core/summarisation/text_preprocessor_concepts.py` | 2,444 | 4 / 3 | 0 | 99% | 0.26 | frozen, pure-function, cohesive |
| 8 | `core/summarisation/text_preprocessor_impl.py` | 1,929 | 6 / 8 | 0 | 99% | 0.24 | not this round |

`converter_impl` won on churn + un-coverage + responsibilities (11+ in one `convert()` body); `summarizer` was deferred because its hot spot (`_summarize_inner`, 349 lines) is a single method, not a scattered monolith.

### Extraction summary — 4 commits

| Commit | What moved | Where | Discipline |
|---|---|---|---|
| `29b6c58` | **Test-only:** 91 hermetic characterization tests pinning the `_match_chapter` ladder (4 rungs), terminal status strings, diagnostic-summary line formats, quality-report JSON shape, `_cross_chapter_dedup`, `_enforce_vram_budget` policies, screenshots precedence + TOC ranges, simplified-keypoints messages, callback plumbing. Every expected value verified empirically against the live code before being written down. | `tests/test_converter_phase3_characterization.py` | characterization FIRST (W8 rule: no extraction into thin coverage) |
| `e3e7e7f` | `ConverterReportingMixin._generate_quality_report` (160 ln) + `convert()`'s diagnostics block (208 ln → `run_diagnostic_summary`) | `core/pipeline/conversion/reporting.py` (447 ln) | mixin move VERBATIM (zero-diff verified vs pre-move blob); runner per the `run_<phase>` house pattern |
| `50d9a63` | `run_summary_outputs`: DOCX (13) + keypoints (41) + simplified digest (58) + citation graph (17) = 129 ln of `convert()` | `core/pipeline/conversion/summary_outputs.py` (254 ln) | script-generated byte-exact move (`/home/z/audit-tools/gen_summary_outputs.py`), difflib-verified vs the pre-move blob |
| `7a8e451` | `assess_completion` pure fn (88 ln: all-failed/cancel/zero-summaries/partial-failure guards + terminal expressions) + `run_screenshots_and_graphs` (51) + `run_library_tracking` (56) | `core/pipeline/conversion/finalization.py` (383 ln) | pure-function conversion; emissions became return values, replayed byte-identically at the exact inline position |

Common invariants across all three extractions: facade + import surfaces unchanged (`conversion/__init__.py` registry updated per commit); anchor tests repointed, never weakened (one weakened pin found and restored during commit 3's audit); Rule-1 deny-list pins added for each new module; the only sanctioned textual differences are the documented mechanical edits (dedent 12→4, `self.`→`converter.`, parameter threading) plus one AST-identical ruff-format reflow per commit.

### Measured LOC (wc -l / AST spans)

| Metric | Before | After | Δ |
|---|---|---|---|
| `converter_impl.py` | 2,175 | 1,577 | −598 (−27%) |
| `convert()` | 1,054 (L1121–2175) | 601 (L977–1577) | −453 (−43%) |
| `conversion/reporting.py` | — | 447 | new |
| `conversion/summary_outputs.py` | — | 254 | new |
| `conversion/finalization.py` | — | 383 | new |
| characterization net | 0 | 131 tests (91 + 11 + 13 + 16) | +131 |
| full suite | 5,812 P / 0 F / 55 S | 5,943 P / 0 F / 55 S | green at every commit |

### Deviations from pure verbatim moves (all documented at the move site)

1. **Commit 2 — citation-graph log order.** The block previously ran *after* `progress(0.96)` + output-studio; inside the runner it follows the simplified digest directly. Log interleaving only — no data dependency either way (graph reads `summaries`/`segments`/`temp_markdown`; studio reads `summaries`/`segments`/`paths`); full suite green. Documented in the module docstring + an ORDER NOTE comment in `convert()`.
2. **Commit 3 — emission → return conversion in `assess_completion`.** `self._update_status(MSG)` → `status_message = MSG`; `self._log(MSG, LEVEL)` → `log_lines.append((LEVEL, MSG))` — message/level text byte-identical, and `convert()`'s replay (status first, then log lines in order) emits byte-identically at the exact inline position (pinned by an end-to-end fake-sink test).

### Not this round (recorded for later)

- `summarizer._summarize_inner` (349 lines, L1429–1777) — the next round's target.
- Converter `preflight` block extraction; `_match_chapter` ↔ `core/segmentation/chapter_matcher.ChapterMatcher` consolidation; frontmatter family (~110 ln).
- `segmenter` (0 churn, cohesive), `text_preprocessor_concepts` (frozen, 99%, pure functions), `packets/generator` (52% — needs a characterization net first).

### Lesson: extracted ≠ tested

The conversion/* modules extracted in *earlier* campaigns are thin-covered — postprocess 22%, visual_features 25%, output_runner 38% — the coverage did not follow the moved code. Consequence adopted this phase: every new extraction ships its characterization net in the same commit series (the 131-test net above), and the net doubles as a byte-identical-move tripwire for every pinned literal.

---

*(Phases 2–6 sections appended below as work completes.)*
