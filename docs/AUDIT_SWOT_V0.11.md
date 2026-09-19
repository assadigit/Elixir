# Elixir — SWOT Audit (Stage 1)

> **Audit scope:** full repository at commit `71bbfc2` (V0.11). All findings verified by direct inspection, tool runs, or API queries on 2026-09-19. No speculative findings.
>
> **Verification environment:** Python 3.12.14 (Linux sandbox), ruff 0.16.8, mypy (latest), vulture, pytest 9.0.2. Target runtime: Windows 10/11 + Python 3.12 + PySide6 6.11 (per README).
>
> **Scale snapshot:** 590 tracked files · 180,621 Python LOC (core 88,865 / ui_qt 27,784 / utils 3,369 / tests 59,377) · 61 prompt templates · 19 output generators.
>
> **Priority keys:** P1 Performance & speed · P2 Dead code removal · P3 Testing & debugging · P4 Engineering best practices · P5 Accuracy & reliability of AI summaries · P6 Project organization · P7 De-monolithization.

---

## Measured Baselines (captured before any change — the "before" for every later "after")

| Metric | Measured value | Method |
|---|---|---|
| Test suite | **3,668 passed / 35 skipped / 1 xpassed in 126 s** (`--no-cov`) | `python -m pytest tests/ --no-cov -q` (Linux) |
| Test suite + coverage | 3,668 passed in 147 s | `--cov=core --cov=utils` |
| Coverage (core+utils) | **51%** (17,478 of 35,494 statements missed) | pytest-cov, same run |
| Lint (ruff 0.16.8) | **1,059 errors** (121 auto-fixable) | `ruff check .` |
| Type check (mypy) | **906 errors in 160 files** (warn-only in CI) | `mypy core/ utils/ --ignore-missing-imports` |
| Dead-code candidates | 501 @ 60% confidence; 7 @ 100% | `vulture core/ utils/ ui_qt/ controller.py main.py` |
| CI (GitHub Actions) | **RED on last 3 commits** (lint job: ruff fail; test job: fails at *Install dependencies*) | GitHub API, runs 35399115183 et al. |
| Fresh install | **BROKEN** — `pip install -r requirements.txt` cannot resolve | PyPI: `anydoc` nonexistent; `kokoro>=0.9.0`/`misaki[en]>=0.9.0` unsatisfiable (max 0.7.16 / 0.7.4) |
| Largest files | summarizer.py 5,566 · postcheck_detectors.py 3,873 · text_preprocessor_impl.py 2,449 · converter_impl.py 2,278 · sections.py 2,152 | `wc -l` |

---

## ✅ Strengths (verified, keep and build on)

### S1. A real, green, fast characterization-test safety net — **P3/P7**
- 3,668 tests pass in ~2 minutes on a clean Linux checkout (verified locally, 2026-09-19). 35 skips are honest (headless Qt, absent reference zips, absent golden source), 1 documented order-fragile xpass (`tests/test_v18202_summarisation_fixes.py::TestA26GpuTempCache`, user-approved).
- Regression-pinning culture: `tests/test_v0*_*.py`, `test_v18*_*.py` anchor every shipped fix; de-monolithization work (V18.20.4.1–.4.9, P2/P5/P6 commits) reports **zero regressions** across 19 commits of history.
- Effort already sunk here is the single biggest reason incremental refactoring is viable at all.

### S2. Clean domain-package architecture under `core/` — **P6/P7**
- 15 bounded sub-packages by responsibility (`core/pdf`, `segmentation`, `summarisation`, `llm`, `translation`, `tts`, `ocr`, `outputs`, `pipeline`, `obs`, `system`, `preprocessing`, `postprocess`, `docx`, `grounding`) + `ui_qt/` (views / components / settings split) + `utils/`. This is already a proper src-style layout in all but name.
- Facade pattern (`core/pipeline/conversion/` splits `convert()` into extraction → segmentation → summarization → postprocess → output phases; `core/outputs/registry.py` is the single source of truth for the 19 output types, shared by wizard/dialog/settings/controller).

### S3. Best-in-class anti-hallucination engineering — **P5**
- 8 defensive layers (concept injection → numeric verification → thinking-strip → narrative filter → F4 source-overlap ≥25% → semantic fact-check ≥0.5 → LLM-as-judge → langextract verbatim grounding), every drop logged to `logs/drops.jsonl` with stage/threshold/measured-overlap, plus a recovery pass (≥30% overlap resurrect) and a Conservative mode. The V0.11 changelog documents this engine catching a real failure chain (25k-char claims-JSON → one-sentence Thorough) and hardening every layer involved.

### S4. Operational resilience engineering — **P4**
- Crash visibility: `core/system/crash_visibility.py` (faulthandler + threading.excepthook, armed before torch import in `main.py:61-65`), crash-report zip with redacted settings (`core/system/crash_report.py`), global excepthook with friendly dialog (`main.py:168-237`).
- Atomic writes (`utils/atomic_io.py`), per-chapter checkpoint/resume (`.checkpoint.json`, `core/pipeline/chapter_checkpoint.py`), map-phase wall-clock budget (`local.map_phase_max_seconds`, default 1800 s), VRAM fail-fast policy (`ask`/`abort`/`proceed`), per-chapter deadline warnings, thermal safety controller.

### S5. Modern tooling configuration exists and is coherent — **P4**
- `pyproject.toml`: ruff (py312 target, E/W/F/I/UP/B/C4/SIM), mypy (3.12, `disallow_any_generics`, `warn_unreachable`), pytest markers, coverage config; `.pre-commit-config.yaml` with 10 hooks (ruff, mypy, whitespace, EOF, YAML, large-file, merge-conflict, debug-statements); `Makefile`; GitHub Actions CI with 3 jobs; `VERSION` file as single source (`dynamic = ["version"]`).

### S6. Windows-disciplined codebase — **P4/Windows**
- `pathlib` throughout: only 3 hardcoded Windows paths in production code, all in user-facing example strings (`ui_qt/settings/tts_page.py:placeholder`, `core/ocr/service.py` guidance text, `core/pipeline/checkpoint.py` docstring example). Zero `os.sep` concatenation. Explicit `encoding="utf-8"` on text I/O (spot-checked `main.py:98`, `utils/atomic_io.py`, `utils/logging.py`).
- Hard-won Windows fixes documented in place: torch-before-Qt DLL-shadowing (`main.py:67-110`), stale-`.pyc` strategy (`main.py:21-51`), locked-file tolerance (`ignore_errors=True`), high-DPI env, keychain service rename with read-fallback (`core/system/secrets.py:33-38`).

### S7. LLM provider abstraction with shared retry/error taxonomy — **P1/P4/P5**
- 5 providers behind one interface (Ollama / OpenAI-compat / Claude / FreeLLMAPI / llama.cpp); `core/llm/model_taxonomy.py` single source for model literals; `core/llm/retry.py` exception classification (404 → pull-hint, OOM, timeout vs retryable) with tenacity-or-linear fallback; response cache + embedding cache; `structured_io.py` shape-safe parsing; recent P5/P6 work added `ModelRegistry`/`ContextBudget` and an adaptive strategy engine (`core/summarisation/strategy.py`, 39 tests) wired into all 4 dispatch sites.

### S8. Versioned prompt management — **P5**
- YAML front-matter versioning on prompt templates (`core/summarisation/prompt_manager.py:29-43, 274-310`), user-override directory, lowbit variants, prompts split by domain (`prompts/summarisation|outputs|pdf|tts|transcribe`).

### S9. Documentation culture — **P6**
- README (412 lines, architecture diagram, settings reference), CHANGELOG (203 KB, every release evidence-linked), `Project-History.md`, `docs/EVALUATION_FRAMEWORK.md` (standing four-pillar judge prompt), `docs/EMBEDDERS.md`, `docs/USER_OLLAMA_MODELS.md`, `NEW_SESSION_PROMPT.md` working agreements.

### S10. Honest self-reporting — **P4**
- README "Known Issues" and roadmap sections admit the open debt (keyring wiring, orchestrator decomposition, real-rig re-run) instead of hiding it. Prior independent SWOT (V18.20.4.9) with per-finding verification table (55/99 fixed, 0 regressions) is preserved in-repo.

---

## ❌ Weaknesses (all evidence-linked)

> Severity 1–5 (5 = critical). Effort: S (<½ day) / M (½–2 days) / L (3–5 days) / XL (>5 days).

| # | Finding | Evidence | Priority | Sev | Impact | Effort |
|---|---|---|---|---|---|---|
| **W1** | **`summarizer.py` is a 5,566-LOC god class and grew, not shrank.** `_summarize_inner` is a **single 1,712-line method** (lines 3329–5041); 97 methods on one class; `summarize_chapters` 278 lines. README's own target was ~3,000 LOC; the V0.06 note said "~4,700" — it has **grown ~860 lines since**. | `wc -l`; `rg -n "^    def "` on `core/summarisation/summarizer.py` | P7 | **5** | Unmaintainable core; every quality fix re-risks regressions in the highest-value path | L |
| **W2** | **Fresh installs are broken.** `anydoc>=0.1.0` **does not exist on PyPI**; `kokoro>=0.9.0` and `misaki[en]>=0.9.0` are unsatisfiable (PyPI max 0.7.16 / 0.7.4). `pip install -r requirements.txt` aborts on any clean machine. README Quick-Start step 1️⃣ fails. | `requirements.txt:138-139,168`; PyPI `pip index` verification; CI run logs | P4 | **5** | New users/new machines cannot install; user's rig only works because deps predate the breakage | S |
| **W3** | **CI is red on the last 3 commits — both gates dead.** Lint job fails `ruff check` (1,059 errors under ruff 0.16.8); Test job never reaches pytest (fails at *Install dependencies*, see W2). Only mypy "passes" because it's `continue-on-error: true`. | GitHub API: runs on `71bbfc2`, `f49e76f`, `c0a174b` all `failure`; jobs endpoint shows failing steps | P3/P4 | **5** | No automated gate on `main`; the 3,668-test net exists but is not enforced remotely | S |
| **W4** | **Dependency declarations have drifted three ways.** `pyproject.toml` lists 14 runtime deps; `requirements.txt` lists 30+ including heavy optionals (langchain, chromadb, spacy, sentence-transformers, kokoro, piper, docling, genanki, pikepdf) — and CI installs the whole set; `requirements.lock` is a **stale 31-line pre-rebrand artifact** ("MarkItDown Pro" header, legacy `PyPDF2==3.0.1`, `numpy-financial`, missing PySide6/markitdown/tiktoken entirely). | `requirements.txt` vs `pyproject.toml` vs `requirements.lock` | P4 | **4** | Unreproducible envs; slow/broken CI; no true lockfile despite one existing in name | M |
| **W5** | **Coverage is 51% with the bar set at 30%.** TTS engines 9–18%, `core/validation/validator.py` 0%, `utils/dependencies.py` 0%, `utils/file_utils.py` 39%. No property-based tests anywhere (hypothesis unused). Registered pytest markers (`slow`, `integration`, `gpu`) have **zero** uses. | coverage run 2026-09-19; `rg hypothesis tests/` → no matches; `rg pytest.mark.(slow\|integration\|gpu)` → 0 | P3 | **4** | Test count is high but breadth is uneven; parser/IO edges uncovered | L |
| **W6** | **API-key protection is dead-on-arrival for fresh installs.** `core/system/secrets.py` implements keyring + migration, but (a) `keyring` is **not in any requirements file**, so `_HAS_KEYRING` is always False on new installs (plaintext + one INFO log); (b) only 2 production call sites use `get_secret` (`core/system/bootstrap.py:283`, `core/summarisation/summarizer.py:259`); (c) `core/translation/service.py:205` reads `translation.api_key` directly — a path **not even in `_SECRET_PATHS`** (which lists `translation.cloud_api_key`) — so that key can never migrate. README admits plaintext storage. No `pip-audit` anywhere. | `rg get_secret` (3 hits incl. self); `requirements*.txt` grep for `keyring` → none; `secrets.py:53-60` | P4 | **4** | Cloud API keys stored in cleartext `settings.json` on any machine provisioned after the breakage | M |
| **W7** | **mypy: 906 errors in 160 of 241 files.** CI runs it warn-only (`continue-on-error: true`), so type coverage is nominal. | mypy run 2026-09-19; `.github/workflows/ci.yml` typecheck job | P4 | 3 | Type system provides little protection today | L |
| **W8** | **Performance work is unmeasured.** No cProfile/py-spy/line_profiler artifacts or timing harness in-repo; per-chapter pipeline makes 5–10 sequential blocking LLM calls (`async_provider.py:5-9` documents this); the purpose-built async path (`core/llm/async_provider.py`, 432 LOC, httpx + gather) is **never wired** — `run_async`/`gather_calls`/`parallel_complete` are unused in production (vulture 60%). Cross-chapter rolling context only functions in sequential mode (`summarizer.py:5264-5275`). Target rig runs `max_workers=1` (12 GB VRAM caps, `_init_max_workers` at `summarizer.py:409-476`), so wall-clock is dominated by serial LLM latency. | vulture output; `summarizer.py:5265`; README rig notes | P1 | **4** | No before/after numbers possible; a ready 30–40% chapter-latency lever (module's own estimate) sits unused | M |
| **W9** | **The accuracy evaluation harness is manual, single-sample, and not CI-able.** Golden dataset = 1 chapter (`docs/ground_truth/001_1 - IDENTITY AND ITS ORIGINS.md`); evaluation = paste-into-LLM four-pillar prompt with human-recorded scorecards; golden-master audit plugin (`tests/plugins/golden_master_audit.py`) requires bun + z-ai-web-dev-sdk (excluded from CI by design); no ROUGE/BERTScore/faithfulness metric computed automatically; prompt changes ship without a quantitative quality gate. The V0.11 changelog itself documents the failure class this enables (vacuous QA blessed a one-sentence Thorough). | `docs/EVALUATION_FRAMEWORK.md`; `tests/test_ground/` (historical scorecards only); CI comment in `ci.yml:9-11` | P5 | **4** | Highest-business-value area has the weakest automation | L |
| **W10** | **Version metadata drift.** `VERSION` = 0.11, but installer `AppVersion=0.06` (`installer/Elixir.iss`), README badge `version-0.06`, README test badge `3510 passed` (actual 3,668). | file inspection | P6 | 2 | User-facing artifacts disagree about what version ships | S |
| **W11** | **Confirmed dead/unused code remains.** Real F401/F841 in core (e.g. `core/docx/builder.py:19` unused `SummaryResult`; `core/extract/image_extractor.py:600` unused `col_has_content`); ruff counts 58×F841 + 38×F401 + 18×F811 repo-wide; vulture 501 candidates @60% (incl. whole `async_provider` public API — see W8; `content_presets.py` preset fields unread; `heading_utils.is_front_matter`/`is_chapter_like` unreferenced); README admits `PromptContext` + `build_primary_prompt` kept frozen deliberately (`prompt_assembly.py`). | ruff/vulture runs 2026-09-19; README Known Issues #4 | P2 | 2 | Noise, misdirection, larger surface for the 906 mypy errors | M |
| **W12** | **`controller.py` (968 LOC) mixes concerns**: thread orchestration + callback ownership + request assembly (`build_request_from_ui` giant field list) + per-book settings persistence. | `controller.py:1-28` (docstring lists accreted fields), `:536-710` | P7/P6 | 2 | Every UI change touches the same file | M |
| **W13** | **30 `print()` calls in production code.** Mostly legitimate (subprocess JSON protocol in `core/tts/_qwen_tts_subprocess.py`, CLI verify tools), but `core/system/dependency_checker.py:81`, `core/system/verify_environment.py:24-25` mix print with logging. | `rg '^\s*print\(' core/ utils/ ui_qt/` | P3 | 1 | Minor log-consistency debt | S |
| **W14** | **One known flaky test** (order-dependent module-state xpass), documented and user-approved but unfixed. | `tests/test_v18202_summarisation_fixes.py::TestA26GpuTempCache` xfail note | P3 | 1 | Erodes trust in the suite | S |

---

## 🌱 Opportunities

| # | Opportunity | Maps to | Value | Effort |
|---|---|---|---|---|
| O1 | **Make CI green in a day** (fix W2/W3/W4 trio: repair requirements, split optional deps into extras, pin ruff, auto-fix 121 lint errors, ratchet the rest). Everything else compounds from a green gate. | P4/P3 | Unblocks all remote verification | S |
| O2 | **Coverage ratchet with teeth**: gate at 55% now, ratchet to 80% on `core/summarisation`, `core/llm`, `core/pdf`; add hypothesis property tests for `segmentation/*`, `citations_regex`, `text_utils`, `postcheck_detectors` regexes. | P3 | Converts the test net from deep-but-narrow to broad | L |
| O3 | **Automated eval harness** (W9): expand golden set to 3–5 chapters incl. scanned/multi-column/table/non-Latin; compute ROUGE-L + faithfulness/hallucination-rate from the *existing* 8-layer signals (drops.jsonl, coverage floors already measure this); gate prompt merges on scorecard deltas. | P5 | Makes quality regressions mechanically detectable | L |
| O4 | **Wire the async provider** (or per-stage thread overlap) for independent in-chapter stages (grounding-check ∥ self-review); module's own estimate: 30–40% chapter wall-clock cut. Measure with the harness from O3/baseline timing. | P1 | Direct user-perceived speedup on the 12 GB rig | M |
| O5 | **Finish the keyring migration** (W6): add `keyring` to deps, route all 6+ key paths through `get_secret`, fix the `translation.api_key` path mismatch, add `pip-audit` to CI. | P4 | Closes the plaintext-secrets exposure | M |
| O6 | **De-monolithization round 3** (W1/W12): continue mixin extraction behind the characterization net — split `_summarize_inner` into staged phase modules, split `postcheck_detectors.py` by detector family, extract request-builder from `controller.py`. One PR per concern. | P7 | Restores maintainability of the core path | XL |
| O7 | **Packaging refresh**: sync installer version, automate `AppVersion` from `VERSION`, single-source badges, PyInstaller smoke test in CI. | P6 | Version hygiene; distributable builds | S |
| O8 | **Multi-document queue concurrency**: the Queue feature processes books sequentially; bounded cross-book concurrency for cloud providers (where VRAM is not the constraint) is low-hanging throughput. | P1 | Batch users convert N books in ≈ the time of the slowest | M |

---

## ⚠️ Threats

| # | Threat | Evidence / mechanism | Maps to | Likelihood | Sev |
|---|---|---|---|---|---|
| T1 | **Refactoring without a remote gate.** CI has been red across the last 3 pushes; any de-monolithization PR "passing locally" is unverifiable by collaborators and unaudited remotely — exactly the failure mode the stage-gates exist to prevent. | W3 | P3/P7 | Certain while red | 5 |
| T2 | **Environment rot breaks the user's own machine silently.** The requirements breakage (W2) means the *next* clean install — new PC, venv rebuild, CI — fails; current rig survives on pre-installed packages only. `markitdown[all]`, langchain, and Ollama API surfaces are fast-moving targets with no lockfile (W4). | W2/W4 | P4 | High | 5 |
| T3 | **Silent quality degradation of AI output.** Prompt templates change without quantitative gates (W9); the V0.11 post-mortem proves the class: a parser fallback + vacuous QA layers shipped a one-sentence "Thorough Summary" to a real user. Every future prompt/model tweak is a new roll of the same dice until O3 exists. | W9; V0.11 changelog | P5 | Medium-high | 5 |
| T4 | **Secrets exposure on any fresh provision.** New installs store cloud API keys in plaintext `settings.json` (W6) with only an INFO-level note; backups/sync of the home dir leak keys. | W6 | P4 | Medium | 4 |
| T5 | **God-class change amplification.** 40% of the summarisation pipeline's logic lives in one 1,712-line method (W1); quality fixes (the app's core value stream) each risk touching 20+ coupled self-deps — the V18.6.3 crash pattern that froze `_build_prompt` extraction was exactly this. | W1; NEW_SESSION_PROMPT.md hard constraints | P7/P5 | Medium | 4 |
| T6 | **Windows-specific fragility, mitigated but load-bearing.** The torch-before-Qt import order, stale-`.pyc` purge, and file-locking tolerances in `main.py` are all best-effort `try/except` paths; a future refactor that reorders imports or "cleans up" startup can reintroduce crashes the comments alone won't prevent (no test pins the import order). | `main.py:21-110` | P4/Windows | Low-medium | 3 |
| T7 | **Bus factor.** 180k LOC, one maintainer + AI sessions; institutional knowledge lives in CHANGELOG prose and inline version-tag comments rather than executable form. | repo structure | P6 | — | 3 |

---

## Cross-cutting observations (evidence-based, no action needed now)

1. **The repo's own roadmap and this audit agree** — README roadmap items #11 (keyring), #12 (orchestrator decomposition round 3), #13 (real-rig re-run) map to O5, O6, and O3 respectively. Nothing in this SWOT contradicts the project's self-assessment; this audit adds the *measured* severity (CI red, installs broken, coverage 51%) that the README could not state.
2. **Linux compatibility is a free win**: the entire suite passes headless on Linux (only Qt-widget tests skip). This makes CI cheap and fast — worth preserving as a hard constraint during refactors.
3. **The stale `requirements.lock` is dangerous precisely because it looks authoritative.** Recommend regenerating it from a real install (Phase 0) or deleting it in favor of extras + constraints.
4. **Prior SWOTs (V18.20.4.0/4.9, 99 findings) fixed 55 with 0 regressions** — the process works; this document is the next iteration of it, focused on the post-rebrand V0.x line.
