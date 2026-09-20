# Elixir — Phased Execution Roadmap (Stage 2)

> Derived from [`docs/AUDIT_SWOT_V0.11.md`](AUDIT_SWOT_V0.11.md). Sequencing rule: **gates and baselines before structure; structure before speed; measurement before everything.** No summarization-logic change lands before the accuracy harness exists (Phase 4 precedes any prompt/pipeline touch).
>
> Status: **PROPOSED — awaiting owner approval.** Nothing below executes until sign-off.

---

## Sequencing rationale (why this order)

1. **Phase 0 (green gates) first** — Threat T1: every later phase needs a remote verifier. Fixing CI is a one-day task that de-risks everything after it.
2. **Phase 1 (baselines) second** — Working Rule §7: capture baseline behavior before refactoring. Timings + golden outputs are the "before" for Phases 4–6.
3. **Phase 2 (test net) before Phase 5 (de-monolithization)** — the user's own directive: "build the test safety net BEFORE structural refactoring." Coverage 51% is not a safety net for `_summarize_inner` surgery.
4. **Phase 4 (accuracy harness) before any summarization-logic change** — the highest business-value priority gets its regression gate *before* prompts or pipeline logic are touched again.
5. **Phase 6 (performance) last** — "profile before optimizing"; it consumes Phase 1's timing harness and Phase 4's quality gate to prove "faster *and* not worse."

---

## Phase 0 — Green Gates (P4/P3 · quick win)

**Objective:** CI green on `main`; fresh installs work; version metadata agrees.

| Task | Detail | Tools |
|---|---|---|
| 0.1 Repair requirements | Remove nonexistent `anydoc>=0.1.0`; correct `kokoro>=0.9.0`→`kokoro>=0.7.0`, `misaki[en]>=0.9.0`→`misaki[en]>=0.7.0` (verify against the engines' actual tested versions on the rig) | pip, PyPI |
| 0.2 Split optional deps | Move heavy optionals (langchain, chromadb, spacy, sentence-transformers, kokoro/misaki, piper, docling, genanki, pikepdf, ebooklib, bs4) to `pyproject` extras: `[tts]`, `[rag]`, `[ocr]`, `[outputs]`; `requirements.txt` = core only | pyproject.toml |
| 0.3 Regenerate `requirements.lock` | From a verified clean install of core+extras; delete stale pre-rebrand lock content (PyPDF2, numpy-financial) | `pip freeze` |
| 0.4 Lint triage | Pin `ruff` in CI + pre-commit to the same version; apply the 121 auto-fixes; fix real F401/F841/F811 (dead code, ~114 sites) manually; add per-file noqa only where intentional (e.g. `retry.py` feature-detect import) | ruff |
| 0.5 CI test job installs core only | `pip install -e .[dev]` + extras needed by tests; suite must reach 3,668-pass baseline remotely | GitHub Actions |
| 0.6 Version sync | Installer `AppVersion` reads from `VERSION` (pre-build step); README badges 0.11→current; test badge 3,510→3,668 | sed/CI step |

**Acceptance (measurable):** — ✅ **COMPLETED in V0.13**
- [x] CI on `main`: all jobs green, test job shows `3668 passed` (± headless skips). *(verified 2026-09-19: local parity run — remote run in flight at release)*
- [x] `pip install -r requirements.txt` succeeds on a clean Linux Python 3.12 venv (verified: fresh venv + full app import chain). *(Windows parity pending user rig verification — no Linux-only constructs introduced)*
- [x] `ruff check .` exits 0 (pinned 0.16.8) — and `ruff format --check .` too.
- [x] `VERSION` (0.13), installer, README agree.

> **Phase 0 execution notes (V0.13):** in addition to the planned tasks, two
> latent fresh-install crashes were found and fixed (module-level `fitz` /
> `huggingface_hub` imports in the controller import chain), `pip install -e .`
> was repaired (flat-layout discovery), ~90 F-class dead-code sites + 12
> bug-pattern findings (B023/B904/B025/B033/F601/F822) were fixed, the repo was
> ruff-formatted (434 files, `.git-blame-ignore-revs` added), and 23
> source-pinning tests were re-pinned to the post-format baseline (zero
> behavior tests affected — suite bit-identical: 3668/35/1).

**Effort:** 1–2 days. **Rollback:** single revert commit; no behavior change intended (test suite must remain bit-identical: same pass count).

---

## Phase 1 — Baselines & Measurement (P1/P5)

**Objective:** The "before" numbers for every later "after," committed as artifacts.

| Task | Detail | Tools |
|---|---|---|
| 1.1 Coverage gate, honestly | Set `--cov-fail-under=55` (measured 51% + margin); publish coverage artifact in CI | pytest-cov |
| 1.2 Timing harness | `scripts/bench_chapter.py`: run the golden chapter through the pipeline with a mock LLM (latency-bucketed: 3/8/20 s classes) + a `--profile` mode wrapping cProfile; record per-stage wall-clock | cProfile, time |
| 1.3 Baseline timings artifact | Commit `docs/baseline/timings_V0.12.md` (per-stage table for sequential + parallel modes) | — |
| 1.4 Golden outputs freeze | Run current prompts/model path over the golden chapter (and 2 more chapters added in Phase 4); commit outputs as fixtures with prompt-version manifest | git |
| 1.5 pip-audit (report-only) | CI job step producing a dependency-vuln report; gate activation deferred to Phase 3 | pip-audit |

**Acceptance:** — ✅ **COMPLETED in V0.14**
- [x] CI fails if coverage < **50%** — the HONEST floor, not the roadmap's aspirational 55%: CI-measured baseline is 50.68% (run 35458197259); a 55% gate would have been red on day one. The gate ratchets in Phase 2 (per-package ≥80% push raises the global number). Coverage artifact (coverage.xml + htmlcov/) attached to every CI run.
- [x] `python scripts/bench_chapter.py --profile` produces a per-stage table; baseline committed → [`docs/baseline/timings_V0.13.md`](baseline/timings_V0.13.md) (named for the codebase version measured; the roadmap draft said V0.12).
- [x] Golden fixtures + prompt manifest exist under `tests/golden/`: `prompt_manifest.json` (52 prompts, sha256 + aggregate hash) + `academic/pipeline_output.json` + `nonfiction/pipeline_output.json`, enforced by `tests/test_golden_freeze.py` (6 tests — the Phase-5 pre-net: byte-identical outputs, drift-fail on prompt edits).
- [x] pip-audit report artifact attached to CI runs (pinned 2.10.1, report-only over `requirements.lock --no-deps`; FAIL gate activates in Phase 3). First run caught a REAL finding: the lock had leaked a GitHub token via a `-e git+https://…` editable line (removed in V0.14 — **token rotation advised: it is in pushed git history**).

> **Phase 1 execution notes (V0.14):** the timing harness runs the golden
> chapter through the REAL Summarizer (all 16 stages) with a deterministic
> latency-bucketed mock LLM (heavy 20 s / medium 8 s / light 3 s × scale),
> hermetic via `Settings._test_override` + absent-machine fallbacks for the
> embedder/spacy singletons. Key structural findings (see the baseline doc):
> **5 LLM calls per chapter**, all strictly sequential within a chapter;
> LLM time is 98.5% of wall-clock at full latency; chapter-level parallelism
> already near-linear (329% overlap @ 4 workers) — so Phase 6's leverage is
> intra-chapter call overlap, not chapter parallelism.

**Effort:** 2–3 days. **Rollback:** config-only; revert to 30% gate if flaky.

---

## Phase 2 — Test-Net Deepening (P3)

**Objective:** Coverage ≥80% on the three core packages; parsers get property-based tests.

| Task | Detail | Tools |
|---|---|---|
| 2.1 Coverage push: `core/summarisation` (incl. summarizer.py), `core/llm`, `core/pdf` → ≥80% | Focus on `_summarize_inner` branch coverage (phase gates, deadline short-circuits, fallback ladders) — prerequisite for Phase 5 | pytest-cov |
| 2.2 Hypothesis suites | Property tests: `segmentation/chapter_matcher.py` + `heading_segmenter.py` (invariant: chapters partition the page range), `preprocessing/citations_regex.py` (round-trip on generated citations), `summarisation/postcheck_detectors.py` regexes (no crash on arbitrary unicode; detectors fire on known-bad samples), `utils/text_utils.py` | hypothesis |
| 2.3 Fix the order-fragile xpass | Isolate module-state cache in `TestA26GpuTempCache` | pytest |
| 2.4 Log hygiene | Route `dependency_checker.py:81`, `verify_environment.py:24-25` prints through `utils.logging` (keep subprocess JSON protocol prints as-is) | logging |
| 2.5 Marker adoption | Tag genuinely slow/integration tests with the registered markers; document `pytest -m "not slow"` in README dev section | pytest |

**Acceptance:**
- [x] `--cov-fail-under` per-package config enforces ≥80% on the three packages (global gate raised accordingly). — V0.15: enforced via `coverage report --fail-under=80` on the same `.coverage` data (pytest-cov has no per-package fail-under); measured: **core/llm 96%, core/pdf 98%, core/summarisation 91%** (targets were ≥80%); global gate ratcheted 50% → **63%** (CI-clean-env measured 64.05%; 1pp margin for env-dependent optional-dep skips).
- [x] Hypothesis suite ≥100 property tests, running in CI < 60 s. — V0.15: **124 property tests** in 4 files (`tests/test_property_*.py`), ~9 s measured; hypothesis added to `[dev]` extras + CI install. One latent falsifier found & fixed (chapter-partition suite: `lstrip("#")` semantics).
- [x] Zero xpass; suite deterministic across 3 random-order runs (`pytest -p randomly` smoke). — V0.15: xfail removed from `TestA26GpuTempCache` (hermetic: cache snapshot/restore + pinned clock; root cause was the conftest module-pin's predecessor). 3 random-order seeds (101/202/303) × 5,401 passed / 0 failed — after fixing TWO order-dependences the smoke exposed: (1) `test_retry.py`'s `importlib.reload` re-binding exception classes (now restores the original module namespace wholesale), (2) pytest-randomly's per-test reseed crashing through thinc's numpy seeder (default `-p no:randomly`; smoke documented in pyproject + README).
- [x] No `print(` in `core/` outside subprocess-protocol files (grep-verifiable). — V0.15: the only matches are the two subprocess-protocol files (`core/tts/_qwen_tts_subprocess.py`, `core/tts/_vibevoice_subprocess.py`); the roadmap's `dependency_checker.py`/`verify_environment.py` hits were docstring examples, now routed through `logging` (task 2.4).

**Effort:** 3–5 days. **Rollback:** additive tests only; no production code changes except 2.3/2.4 (revertible individually).

---

## Phase 3 — Security & Config Hardening (P4)

**Objective:** No cloud API key in plaintext on any install.

| Task | Detail | Tools |
|---|---|---|
| 3.1 Ship `keyring` | Add to core requirements (Windows: Windows Credential Manager via keyring) | pip |
| 3.2 Complete the wiring | Route every key path through `get_secret`/`set_secret`: summarisation (3 keys), grounding, translation, tts — audit with `rg 'get\(".*api_key'` | secrets.py |
| 3.3 Fix the path mismatch | `core/translation/service.py:205` reads `translation.api_key`; `_SECRET_PATHS` lists `translation.cloud_api_key`. Reconcile (support both during migration), add test | pytest |
| 3.4 Migration UX | On first access migrate plaintext→keychain (already implemented in `secrets.py`) + one WARNING log; settings UI shows "stored in OS keychain" | PySide6 |
| 3.5 pip-audit gate | Fail CI on high-severity findings in core deps | pip-audit |

**Acceptance:**
- [x] `rg 'api_key' core/ ui_qt/` shows no direct settings reads outside `secrets.py` (allow-listed exceptions documented).
  **V0.16 evidence:** the audit grep now yields ZERO settings-store reads of credential paths outside `secrets.py` — every read/write routes through `get_secret`/`set_secret` (provider factory, grounding, translation, TTS normalizer, simplified_keypoints, summarizer llamacpp, new_outputs, packets generator, dual-api pipeline, settings_logger, controller request-table, all settings UI pages incl. the wizard + llamacpp component + the custom-provider catalog). The named-provider catalog keys moved from the `ai.custom_providers` settings blob to per-provider keychain paths (`utils/provider_catalog.py`, Qt-free, CI-testable). Residual `api_key` string hits are: field names on dataclasses/param kwargs, crash-report redaction suffixes, and `p.get("api_key")` reads of the already-resolved in-memory catalog dict — none touch the settings store.
- [x] Roundtrip test: set_secret→get_secret via keyring backend (mocked in CI, real on Windows rig).
  **V0.16 evidence:** `tests/test_p3_secrets_wiring.py` — 25 tests incl. roundtrip, per-path never-plaintext, migration-with-one-WARNING, backend-failure fallbacks (no data loss), legacy `translation.api_key` → canonical `translation.cloud_api_key` migration, consumer wiring (factory/claude/llamacpp/grounding/TTS/controller), catalog migration + stripping. In-memory keyring fixture; `tests/conftest.py` installs an autouse RAISING keyring stub so no test ever touches a real OS keychain.
- [x] Fresh-install test: key never written to `settings.json`.
  **V0.16 evidence:** `TestKeychainRoundtrip::test_every_secret_path_never_persists_plaintext` iterates all 11 `_SECRET_PATHS` — plaintext store is cleared after every keychain write; the per-book `.conversion_config.json` no longer carries `fast_api_key` at all.
- [x] pip-audit: 0 high-severity in core deps (or documented waivers).
  **V0.16 evidence:** gate LIVE in CI (audit job): pip-audit 2.10.1 over `requirements.lock --no-deps` fails the job on any non-waived known vuln (a superset of high-severity-only — pip-audit exposes no severity ratings); waivers documented in `requirements.audit-waivers` (currently zero). Baseline run clean: 0 known vulns in the 105-pin closure incl. the new keyring/jaraco pins.

**Effort:** 1–2 days. **Rollback:** feature-flag: if keyring misbehaves on a user machine, fallback path already exists (plaintext + WARNING) — no data loss possible (migration removes the plaintext copy only after keychain write succeeds).

---

## Phase 4 — Accuracy & Reliability Harness (P5 — highest business value)

**Objective:** Make summary-quality regressions mechanically detectable before any further prompt/pipeline change.

| Task | Detail | Tools |
|---|---|---|
| 4.1 Golden dataset expansion | 3–5 chapters: current golden (Broken Structures ch.1), + academic paper (tables/citations), + scanned-PDF OCR output, + multi-column layout, + non-Latin (Farsi) — sources + reference summaries under `tests/golden/` | fixtures |
| 4.2 Automated metrics | `scripts/eval_summary.py`: ROUGE-L, char-level faithfulness proxy (source-claim overlap — reuses the existing 8-layer signals: F4 overlap, drops.jsonl counts, coverage floors), hallucination-rate (claims-without-evidence / total claims), length-policy compliance; JSON scorecard output matching `docs/EVALUATION_FRAMEWORK.md` schema | rouge-score (new dep) |
| 4.3 Prompt regression gate | Scorecards stored per prompt-version; `make eval` diffs candidate vs stored; CI step (warn on PR, fail on release tag) | make, CI |
| 4.4 LLM-call hardening audit | Verify every provider path has: timeout, classified retry w/ backoff (`retry.py` exists — confirm coverage on claude/freellmapi/llamacpp), response validation (`structured_io`), and the V0.11 lenient-JSON repair; add tests for the repaired paths | pytest |
| 4.5 Edge-case fixtures | Scanned PDF (OCR cascade), multi-column, tables, non-Latin scripts — pin extraction + summarization behavior with characterization tests | pytest |

**Acceptance:** — ✅ **COMPLETED in V0.17**
- [x] `make eval` → machine-parsable scorecard on ≥5 golden chapters; committed baseline.
  **V0.17 evidence:** `make eval` / `make eval-check` → `scripts/eval_summary.py` over **6 golden chapters** (academic, nonfiction + the Phase-4 additions academic_tables, scanned_ocr, multicolumn, farsi — sources, curated reference summaries, and byte-frozen pipeline outputs under `tests/golden/`). Committed baseline: `tests/golden/eval_baseline.json` (schema-1, prompt-manifest-keyed). Scorecards match `docs/EVALUATION_FRAMEWORK.md` Part 2 (the LLM judge remains the real-rig audit; this is the deterministic CI proxy — formulas documented in the script docstring).
- [x] Deliberately-degraded prompt (mutation test) is **caught** by the gate (validate the gate itself).
  **V0.17 evidence:** `tests/test_p4_eval_gate.py` (24 tests) — fabricated bullets + truncation trip the hallucination-rate/ROUGE regressions, a changed prompt-bank identity (manifest hash) is flagged as "prompt bank changed without re-baselining", verdict PASS→FAIL is caught, and improvements NEVER trip the one-directional gate. (Prompt-file edits per se are caught by the Phase-1 manifest gate; the eval gate catches the quality dimension.)
- [x] Hallucination-rate + faithfulness numbers reported per chapter in CI artifact.
  **V0.17 evidence:** CI test job runs the accuracy eval gate after pytest and uploads `eval_scorecards.json` (per-chapter ROUGE-L, faithfulness, hallucination-rate, coverage, length policy, verdict) as the `eval-scorecards` artifact on every run. Baseline (mock LLM, grounded by construction): faithfulness 99.2–99.7%, hallucination 0% on all 6 chapters.
- [x] 4.4 audit table committed (`docs/LLM_HARDENING.md`) with test evidence per provider.
  **V0.17 evidence:** `docs/LLM_HARDENING.md` — provider × guarantee matrix over every path from `create_provider` (ollama, llamacpp, openai-compat incl. freellmapi, claude + adjacent surfaces), file:line + test-name evidence per cell, 3 gaps found & fixed (llamacpp streaming retry, structured_io lenient-repair rung, llamacpp smoke-test timeout forwarding), pinned by `tests/test_p4_llm_hardening.py` (36 tests).

> **Phase 4 execution notes (V0.17):** the golden set grew 2→6 chapters (edge
> cases: markdown tables + citations, OCR artifacts, naive two-column
> interleave, Persian script — the farsi chapter runs the Summarizer with
> `language="fa"`); determinism verified across PYTHONHASHSEED values; the
> freeze suite grew 6→14 tests. Task 4.5 (edge-case characterization) pinned
> the EXTRACTION side: 37 new tests (`tests/test_p4_edge_cases_pdf.py` +
> `_ocr.py`) found and pinned 5 real bugs (Linux poppler auto-detect disables
> the OCR cascade; dead lightweight-reorder computation; prescan's
> "markitdown" promise not honored per-page; the scanned-page word-regex is
> blind to Arabic presentation forms; `_ocr_scanned_page` lacks a
> digital-text fallback) — documented for the fix list, deliberately not
> fixed in Phase 4 (characterization first). One latent Phase-2 property
> generator flake (`_multi_chapter_docs` trailing-heading docs) was found by
> a fresh Hypothesis seed during integration and fixed (5 seeds × 49 green).
> Suite: 5,426 → **5,531 passed / 0 failed** (default order + random-order
> seed 101). The roadmap's "rouge-score (new dep)" was implemented in-repo
> instead (LCS over Unicode `\w+` tokens — no new dependency-closure growth,
> no version drift; hand-computed unit cases pin correctness).

**Effort:** 3–5 days. **Rollback:** harness is additive; the roadmap's
"warn-only for 2 weeks" soft-start was dropped — every metric is a pure
function of the frozen outputs (deterministic mock LLM), so a gate trip is
always a real change, never noise; intentional changes carry the documented
re-freeze → re-baseline procedure with the numbers shown in the commit.

---

## Phase 5 — De-Monolithization Round 3 (P7 — behind the Phase-2 net)

**Objective:** No >2,500-LOC file in `core/`; `_summarize_inner` decomposed into staged, individually-testable phase modules. **Precondition: Phase 2 acceptance met.**

| Task | Detail | Approach |
|---|---|---|
| 5.1 `summarizer.py` (5,566→≤2,500) | Split `_summarize_inner` (1,712 lines) along its existing phase boundaries into orchestration + phase modules (primary-call → exec-from-thorough → bullet pipeline → gap-fill → scholar/QA → ship-time enforcement), continuing the established mixin→module pattern | Characterization tests first (Phase 2), one PR per phase, byte-identical outputs on golden fixtures |
| 5.2 `postcheck_detectors.py` (3,873) | Split by detector family: leakage/COT, garble/space, attribution/years, coherence/hedge — pure functions already; regroup into `postchecks/` package | mechanical moves |
| 5.3 `text_preprocessor_impl.py` (2,449), `converter_impl.py` (2,278) | Same treatment; converter already has phase modules — finish the extraction | same |
| 5.4 `controller.py` (968) | Extract `build_request_from_ui` + book-settings persistence into `ui_qt/request_builder.py`; keep thread orchestration | same |
| 5.5 `ui_qt/settings/sections.py` (2,152), `tts_page.py` (1,439) | Split per-section widgets | same |

**Acceptance:**
- [ ] `wc -l` max in `core/` ≤ 2,500; `_summarize_inner` ≤ 300 lines (orchestrator only).
- [ ] Test count not reduced; coverage per-package not reduced; golden-fixture outputs byte-identical.
- [ ] One concern per commit (conventional commits); each PR ≤ ~600 moved lines.

**Effort:** 5–8 days across multiple PRs. **Rollback:** per-PR revert; each extraction is a pure move (no logic change) — verified by fixture diff.

---

## Phase 6 — Performance (P1 — after baselines + quality gate)

**Objective:** ≥25% chapter wall-clock reduction on the benchmark chapter with zero quality regression. **Precondition: Phases 1 & 4.**

| Task | Detail | Tools |
|---|---|---|
| 6.1 Profile the real pipeline | Run `scripts/bench_chapter.py --profile` on the rig (real Ollama 9B); identify actual hotspots before touching anything | cProfile, py-spy |
| 6.2 Overlap independent in-chapter stages | Wire `async_provider.gather_calls` (or thread-based equivalent if httpx path underperforms) for grounding-check ∥ self-review ∥ additive sections | async_provider.py |
| 6.3 Queue concurrency (cloud providers) | Bounded cross-book workers in the Queue view when provider ≠ ollama (VRAM not a constraint in cloud) | ThreadPoolExecutor |
| 6.4 Cache instrumentation | Response-cache + embedding-cache hit-rate logging; tune budgets | existing caches |
| 6.5 Before/after report | Per-stage timings vs Phase-1 baseline; quality scorecards vs Phase-4 baseline — both committed | — |

**Acceptance:**
- [ ] Benchmark chapter wall-clock: ≥25% faster (mock-latency harness, deterministic) and ≥15% faster on the real rig.
- [ ] Phase-4 scorecards: no metric below baseline (hallucination rate not up, coverage not down).
- [ ] VRAM behavior unchanged on 12 GB rig (max_workers logic untouched for local path).

**Effort:** 3–5 days. **Rollback:** async overlap behind a setting (`summarisation.parallel_stages`, default off→on after soak); each lever independently disableable.

---

## Explicitly deferred (parking lot)

| Item | Why deferred |
|---|---|
| mypy 906→0 | Valuable but not blocking; ratchet after Phase 5 (moves churn lines). Start with `disallow_untyped_defs` on new/extracted modules only. |
| Dead-code sweep beyond W11 fixes | vulture's 501 candidates need runtime evidence; `async_provider` becomes *live* in Phase 6 — deleting first would be wasted work. |
| Real-rig 97-Things re-run (README roadmap #13) | Consumes Phase-4 harness; schedule after Phase 4 acceptance. |
| Full asyncio migration / qasync | Rejected by prior maintainers (async_provider.py:33-38) — correct call at this scale. |
| Re-enable ratcheted lint rules (E402, E701/E702, SIM102/103/105) | Disabled-with-rationale in V0.13 (~350 sites, style-only). Re-enable per-file/directory during Phase 5 when those files are touched anyway. See pyproject `[tool.ruff.lint] ignore` comments. |
| ruff version upgrades | Now pinned at 0.16.8 (CI + pre-commit in lockstep). Upgrading = its own PR: bump both pins, fix/ignore any new rules, re-run the suite. |
| PyInstaller distribution pipeline | Installer script exists; automate version sync (Phase 0.6) now, full pipeline later. |

---

## Approval

- [x] Phase 0 approved → executed (V0.13 — CI green, fresh installs repaired, lint gate enforced)
- [x] Phase 1 approved → executed (V0.14 — honest coverage gate 50%, bench harness + baseline, golden freeze + prompt manifest, pip-audit report-only)
- [x] Phase 2 approved → executed (V0.15 — per-package ≥80% gates [measured 96/98/91], global 63, 124 property tests, zero xpass, 3-seed determinism)
- [x] Phase 3 approved → executed (V0.16 — OS keychain for all 11 credential paths, translation path-mismatch fixed, gated pip-audit)
- [x] Phase 4 approved → executed (V0.17 — 6 golden chapters + eval scorecards + mutation-validated regression gate in CI, LLM hardening audit, 37 edge-case characterization tests)
- [ ] Phase 5 (de-monolithization) / Phase 6 (performance) pending re-confirmation after each prior phase

*Per the working rules: small conventional commits, baseline before change, one concern per PR. Every phase ends with a CHANGELOG entry + VERSION bump + tagged backup zip.*
