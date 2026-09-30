# Elixir — SWOT Re-Audit (V0.6.7)

> **STATUS:** point-in-time SWOT at tag `V0.6.7` (`7cb180c`, branch `refactor/audit-session`).
> Supersedes the V0.4.25-era SWOT in `SESSION_REPORT.md` Phase 1 and the V0.11-era
> `docs/AUDIT_SWOT_V0.11.md` (both kept as historical evidence). All findings verified
> by direct inspection, tool runs, or executed tests in this session (2026-09-30).
> No speculative findings; every item carries file:line evidence and a confidence label.
>
> **Verification environment:** Python 3.12.14 (Linux sandbox), PySide6 6.11.2
> (Essentials+Addons, offscreen), pytest 9.0.2, ruff 0.16.8 (the CI pin), radon 6.0.1,
> vulture 2.16. One environment caveat: sandbox numpy is 2.1.3 (the project pins <2 for
> the Windows rig's compiled-deps ABI) — no test result in this audit depends on it.
>
> **Method:** scripted shape/complexity/MI/import-graph metrics (stdlib AST + radon),
> full-suite run, targeted failure diagnosis, two independent fresh-eyes review passes
> (code-quality; architecture/integration) with every top finding re-verified by the
> orchestrator before it appears below.

---

## 0. Executive Summary (12 lines)

Elixir at V0.6.7 is a **large, unusually well-defended single-user desktop pipeline**:
7,481 tests pass in ~4 minutes, layering is clean (zero core→UI imports), LLM operations
are hardened well above desktop-app norms, and the supply chain is locked and waivered
with zero known vulnerabilities. The audit's headline finding is a **BLOCKER that the
last two sessions misdiagnosed**: the VRAM-overbudget safety gate is unreachable dead
code (`converter_impl.py:502` returns unconditionally before the policy block), and the
**12 test failures it causes were pinned as "environment failures"** — the "14 pinned
families" baseline is a myth; only 2 of the 14 are real environment/contract questions.
A second confirmed defect: the `dual_api` fast-provider override silently never applies
(public vs underscore attribute names), so a supported architecture routes concept
extraction to the wrong endpoint. The structural debt (five god functions CC 105–136,
152 pass-only exception swallows, 60-site timeout scatter) is real but the repo owns a
**proven, mechanically-verified extraction pattern** to pay it down safely. Scores:
architecture 4/5, scalability 4/5, performance 3.5/5, integration 3.5/5,
modularization 3.5/5, maintainability 2.5/5, clean code 2.5/5.

## 1. Scorecard (1–5, evidence-anchored)

| Area | Score | One-line justification |
|---|---|---|
| A. Maintainability | **2.5** | 125 functions >150 LOC, 4 modules at MI 0.00, 2,312 V18.x comment tokens — but the characterization-test net makes refactoring unusually safe |
| B. Scalability (desktop) | **4** | Bounded caches/queues, checkpoints, map-reduce, streaming; whole-book-in-RAM residue documented, fine for one book |
| C. Performance | **3.5** | LRU/FIFO caches, pooled transports, probe caching; E6 blocking-sleep family and 60-site timeout scatter remain |
| D. System design & architecture | **4** | Zero core→UI violations, deliberate documented cycles, declarative registries; `utils.settings` hub (61 importers) and the 1,335-LOC conversion orchestrator are the soft spots |
| E. Clean code | **2.5** | 152 pass-only swallows (71 uncommented), lying docstrings on a safety gate, 91 stub-file duplication, VRAM dead code — against: zero bare `except:`, zero TODO debt, honest logging idioms |
| F. Modularization & findability | **3.5** | Bounded packages with intent-revealing names; timeouts have no home (the missing `core/system/timeouts.py`), `_vNNN_*` clones obscure intent |
| G. Dependency & integration reliability | **3.5** | Transport SSOT + supervisor + retry taxonomy + zero vulns; minus the dual_api no-op, RTL-dep drift across install surfaces, markitdown[all] closure |

**Overall: 3.4/5** — a mature codebase with excellent defenses whose honest-green
discipline slipped exactly once, at the worst possible place (a safety gate).

## 2. SWOT Quadrants

> Confidence labels: **MEASURED** (ran it, got the number) · **OBSERVED** (read the code,
> cited lines) · **INFERRED** (reasoned from evidence, marked as such).

### Strengths (by impact)

| ID | Item | Evidence | Conf. |
|---|---|---|---|
| S1 | **Test safety net of unusual depth**: 7,481 passing in 245.6 s; 260 test files / ~7,115 test functions; characterization-first culture; every shipped fix red-proofed | full-suite run this session; `tests/` census | MEASURED |
| S2 | **Clean layering — headless core is already real**: zero core→ui_qt imports (2 docstring-only refs), exactly 1 guarded PySide6 import in core (`numpy_abi_check.py:334`, console-fallback); composition root in `main.py:302` | AST import graph + grep | MEASURED |
| S3 | **LLM ops engineering**: `OllamaSupervisor` (restart budget, rate-limit, readiness poll), tenacity retry taxonomy (404 non-retryable, OOM context-halving), `session_for_url` transport SSOT (29 importing files) | `core/system/ollama_supervisor.py:151-211`, `core/llm/retry.py`, `utils/network.py:72-95` | OBSERVED |
| S4 | **Crash-safety architecture**: write-once `<!-- COMPLETE -->` checkpoints, occurrence-aware resume, atomic writes on all outputs, errno-28 actionable disk-full error | `core/pipeline/conversion/summarization.py:104-129`, `core/pipeline/chapter_resume.py`, `utils/atomic_io.py` | OBSERVED |
| S5 | **Supply-chain discipline**: complete lockfile (105+ pins), waiver policy requiring package+version+rationale+review-date, **zero active waivers / zero known vulns**, keychain/env-var secret resolution, 0 secrets/0 `verify=False`/0 `shell=True` in runtime code | `requirements.lock`, `requirements.audit-waivers`, greps this session | MEASURED |
| S6 | **Content-agnostic enforcement (anti-benchmax)**: mechanical tests scan runtime code for book-derived names/concepts — the repo polices its own Rule 1 | `AGENTS.md` Rule 1, `tests/test_v182039_audit_fixes.py` | OBSERVED |
| S7 | **A proven de-monolithization pattern**: verbatim extraction, AST-identity verification, purity-check guard, characterization tests first (the V0.6.7 save-block extraction is the reference) | CHANGELOG V0.6.7 §4; `tests/test_v067_review_loop_fixes.py` | OBSERVED |
| S8 | **Bounded by construction**: LRU 1,000 response cache, FIFO 2,000 translation cache, cloud-only queue cap 4, restart budgets, probe caches | `core/llm/response_cache.py:255`, `core/translation/cache.py:45`, `ui_qt/queue_parallel.py` | OBSERVED |

### Weaknesses (by impact)

| ID | Item | Evidence | Conf. |
|---|---|---|---|
| W1 | **The VRAM safety gate is dead code — and 12 red tests were mispinned as "environment"**: `converter_impl.py:502` `return None` (V0.5.14 hotfix) makes the entire proceed/ask/abort policy block at `:503-536` unreachable; the setting `local.vram_overbudget_policy` (registered `utils/settings.py:455`) is a placebo; the docstring `:411-429` still promises enforcement. 8 converter + 4 segmentation VRAM tests fail at HEAD; prior baselines listed them as "pinned environment families" | ran `tests/test_converter_phase3_characterization.py` (8 F/123 P) and the segmentation set (4 F); read the code | MEASURED |
| W2 | **God functions persist** (carried since V0.4.25, now measured precisely): `run_summarization` CC 136 / 1,020 LOC; `scholar_reflection` CC 118 / 13 params; `verify_and_polish_summary` CC 110 / 12 identical exit wrappers; `batch_gap_fill` CC 107 / 1,001 LOC / 14 params; `run_content_judge` CC 105. 125 functions >150 LOC; 37 signatures ≥10 params; 4 modules at MI 0.00 | radon 6.0.1 (CC + MI), AST param census | MEASURED |
| W3 | **Exception-swallow residue**: 152 pass-only handlers (101 `except Exception: pass`), 71 uncommented; highest-risk: checkpoint-manifest corruption silently → `{}` (`chapter_checkpoint.py:1045`), disk-cache `clear()` can silently fail (`response_cache.py:245`), embedder-health guard swallows its own import failure (`bullet_pipeline.py:221`) | AST census + targeted reads | MEASURED |
| W4 | **Duplication families**: timeout scatter 60 sites / 11 magic values (the planned `core/system/timeouts.py` still doesn't exist); 91 test files still carry copy-pasted tiktoken/markitdown stub blocks (conftest gates make them inert); 9 of 11 service dialogs not on `BaseServiceDialog`; `G:\` piper/neutts default literals duplicated in `utils/settings.py:791-793` and `core/outputs/podcast_audio.py:169-185`; 17 `_vNNN_*` function clones | greps + reads | MEASURED |
| W5 | **`dual_api` fast-provider override is a silent no-op**: `summarization.py:793-798` `hasattr(_provider, "_base_url"/"_api_key"/"_model")` — `OpenAICompatProvider` stores **public** `base_url`/`api_key` (`openai_compat_provider.py:39-40`), so url/key never override; concept extraction silently runs against the default cloud endpoint (errors swallowed at `:960-963` as "concept extraction unavailable") | read + attribute-name verification | MEASURED |
| W6 | **Dependency drift on the RTL line**: `arabic-reshaper` + `python-bidi` (V0.6.5 RTL outputs) exist only in `requirements.txt:48-49` — missing from `pyproject [project.dependencies]` AND from `requirements.lock` (not regenerated); 2 of 3 install surfaces silently lack them (degrade is WARNING-only) | file diffs | MEASURED |
| W7 | **Lying/stale docs in code**: the W1 docstring (safety gate!); `step4_outputs.py:29` claims 19 output types, registry holds 21; conftest comments say 51/36 stub files (actual 78/37); `main.py:54` prints a V18.2.37 tag at V0.6.7; 2,312 V18.x comment tokens reference an unmapped era | reads + greps | MEASURED |
| W8 | **`utils/settings.py` hub**: 1,617 LOC, 61 importers, `_load` CC 65 (4-line-in-one migration mass: every new key = defaults+migration+schema edits); the V0.4.25-era store/schema/defaults split recommendation stands | radon + import graph | MEASURED |

### Opportunities (by impact)

| ID | Item | Evidence | Conf. |
|---|---|---|---|
| O1 | **Retire the "14 pinned failures" myth → an honestly-green suite**: fix W1 (restore or delete-and-document the policy, one decision), resolve the 2 v182032 contract conflicts → the suite goes fully green and Rule 3 regains meaning | this audit's failure census | MEASURED |
| O2 | **Pay down the god functions with the proven pattern**: the V0.6.7 save-block extraction (verbatim move, AST-verified, 14 tests) is the template; `scholar_reflection` and `verify_and_polish_summary` are the next-best targets (their exits/phases are already separable) | CHANGELOG V0.6.7 §4 | OBSERVED |
| O3 | **Headless/server mode is one dialog away**: core is Qt-free (S2) — moving the numpy-ABI dialog to main.py unlocks a CLI/server entry point (new product surface, new users) | import graph | INFERRED |
| O4 | **Mechanical wins queue**: timeout policy table (60 sites), stub-block sweep (91 files, tests-only), dialog migration (9 files), `G:\` defaults single-sourcing, `_vNNN` renames — each one commit, each measurable | W4 evidence | MEASURED |
| O5 | **Dependency surface slimming**: markitdown[all] → used-extras (drops azure-SDK/youtube closure); single-source requirements.txt ↔ pyproject; regenerate the lock with the RTL deps | lock inspection | MEASURED |
| O6 | **mypy ratchet**: warn-only today; the E402/E701/E702 parking lot shrinks naturally during O2 extractions | pyproject lint ignores | OBSERVED |

### Threats (by impact)

| ID | Item | Evidence | Conf. |
|---|---|---|---|
| T1 | **Baseline-integrity process failure**: two consecutive sessions pinned 14 failures as "environment families" without root-cause; 12 were a code defect (W1), 2 a contract conflict (T5). A test net whose reds are myth-labeled stops protecting anything | V0.6.6/V0.6.7 baselines vs this census | MEASURED |
| T2 | **Bus factor 1 at AI cadence**: 244 of 312 commits from AI sessions; knowledge lives in CHANGELOG prose and session prompts, not in architecture docs a new hire could read | git shortlog | MEASURED |
| T3 | **Contract-conflict class (era drift)**: the V0.5.15 "regex-grounded exemption" (`field_phases.py:482-501`) keeps exactly the bullet class the V18.20.3.2 parenthetical-promotion veto exists to drop — Khan IS a parenthetical-only author, so the exemption defeats the veto; needs an owner decision (update tests to the V0.5.15 contract, or exempt only authors with non-parenthetical presence) | reproduced deterministically this session | MEASURED |
| T4 | **markitdown[all] transitive closure**: azure SDK + youtube-transcript-api etc. in the 105-pin lock — attack surface + install weight for a fraction of the features (carried T3 from V0.4.25, still current) | `requirements.lock:30-33,140` | MEASURED |
| T5 | **Rig-only verification surface**: live qwen/vibevoice/sherpa TTS, Persian tessdata OCR, full-book runs — only verifiable on the operator's Windows rig; this sandbox covers ~everything else | RIG_TEST_CHECKLIST.md | OBSERVED |
| T6 | **Windows-first literals + provenance compression**: `G:\`/`C:\` defaults in runtime code; V18.x comment archaeology (2,312 tokens, no tag mapping) makes future-agent archaeology expensive | W4/W7 | MEASURED |

## 3. Hotspot Map (top 10, risk × churn)

| # | Location | Why |
|---|---|---|
| 1 | `core/pipeline/converter_impl.py:502-536` | Dead safety gate + 12 red tests (W1) |
| 2 | `core/pipeline/conversion/summarization.py:316-1335` | `run_summarization` CC 136 / 1,020 LOC; 27-touch hotspot |
| 3 | `core/summarisation/postchecks/field_phases.py:482-518` | Veto-vs-exemption contract conflict (T3) |
| 4 | `core/summarisation/scholar_reflection.py:66-805` | CC 118, 13-param dependency bag |
| 5 | `core/summarisation/verification_phase.py:745-1504` | CC 110, 12 copy-pasted exits |
| 6 | `core/summarisation/gap_fill_batch.py:414-1414` | CC 107, veto state machine interleaved with retry loop |
| 7 | `core/summarisation/bullet_pipeline.py:1186-1683` | CC 105 + the `:221` embedder-guard swallow (W3) |
| 8 | `utils/settings.py:920-1387` | `_load` CC 65, migration mass (W8) |
| 9 | `core/pipeline/chapter_checkpoint.py:1045` | Silent manifest corruption → resume disabled (W3) |
| 10 | `core/llm/response_cache.py:245` + `embedding_cache.py:424` | Silent clear-failure family (W3) |

## 4. Key Metrics

| Metric | Value | Method |
|---|---|---|
| Runtime shape | 359 files · 152,749 LOC · 3,084 functions · avg 425 LOC/file | AST census |
| Test shape | 260 files · 129,531 LOC · ~7,115 test functions | AST census |
| Suite (this sandbox) | **7,481 P / 15 F / 43 S / 16 D in 245.6 s** | pytest 9.0.2, offscreen Qt |
| True failure census | 12 = W1 dead-code · 2 = T3 contract conflict · 1 = sandbox QtMultimedia (passes with full Qt) | per-test diagnosis |
| Ruff 0.16.8 | `ruff check .` **PASS**; 737 files format-clean; 1 invalid-`# noqa` warning (`response_cache.py:107`) | ruff run |
| Complexity | avg B (6.33) · 488 blocks ≥C · 152 blocks ≥21 · top CC 136 | radon cc |
| Maintainability | 4 modules MI 0.00; next-worst 1.25–3.98 | radon mi |
| Dead code | vulture ≥90%: 15 items (1 is the W1 BLOCKER: unreachable code) | vulture 2.16 |
| Import cycles | 3 clusters (llm providers / summarisation internals / tts) — deliberate, documented, runtime-safe (lazy imports + `__getattr__`), verified importable | AST Tarjan + import runs |
| Fan-in hubs | settings 61 · core.models 49 · logging 34 · network 29 | AST graph |
| Exceptions | 1,339 handlers; 0 bare `except:`; 152 pass-only (101 broad); 23 `log_swallow` adoptions | AST census |
| Security greps | 0 secrets · 0 `verify=False` · 0 `shell=True` · 0 unsafe deser. | greps |
| Git | 312 commits (all 2026-09); authors: AI sessions 244, operator 37, bots 22 | git log |
| Hot files (500-commits) | summarizer.py ×27 · converter_impl ×16 · thorough_theorist_floor ×14 · postchecks/orchestrator ×14 | git log --name-only |

## 5. Integration & Dependency Registry (reliability-rated)

| Integration | Where | Failure handling | Rating |
|---|---|---|---|
| Ollama (local) | `core/llm/ollama_provider.py` | pooled no-proxy transport, retry w/ backoff, OOM→context-halving, 404→pull-hint, supervisor auto-restart w/ budget | High |
| llama.cpp server | `core/llm/llamacpp_provider.py` | SSE streaming w/ per-chunk timeout, mid-stream errors surfaced, budget-derived wall-clock fallback | High |
| OpenRouter / OpenAI-compat | `core/llm/openai_compat_provider.py` | pooled, shape-safe parse, retry | High |
| Anthropic Claude | `core/llm/claude_provider.py` | pooled, missing-key→logged None, retry | High |
| OpenAI Batch API | `openai_compat_provider.py:243-305` | deliberate bare transport (documented); 60×10 s poll loop on sync threads (E6 family) | Medium |
| 9Router / LM Studio / FreeLLMAPI | probes + same transports | probe-only, actionable errors | Medium |
| TTS: VibeVoice / Piper / NeuTTS / Kokoro / Qwen / Sherpa / Persian VITS | `core/tts/*` | fail-fast no-restart (documented) / 120 s wedged-child kill / persistent-subprocess protocols w/ stderr drains / fail-soft base wrapper | Medium-High |
| TTS voice downloads | `core/tts/voices.py`, `sherpa_persian_engine.py` | raises w/ install instruction; optional-import guarded | Medium |
| OCR: tesseract / Qwen-via-Ollama / Paddle / Unlimited / poppler | `core/ocr/service.py` | PATH fallback, live vision probe + cross-backend fallback (cached/conversion), ImportError→disable w/ WARNING, poppler preflight | High |
| Translation (Ollama + active-LLM fallback) | `core/translation/translation_engine.py` | injectable transport, same retry machinery | High |
| OS keychain | `core/system/secrets.py` | typed errors, plaintext fallback w/ one-time WARNING, legacy migration | High |
| ffmpeg / nvidia-smi / ollama CLI | transcribe, hardware_monitor, supervisor | explicit timeouts (2–600 s), returncode surfaced, TimeoutExpired semantics documented | High |
| Python deps (105-pin lock) | `requirements.lock` | **zero active waivers, zero known vulns**; numpy<2 ABI rationale documented + startup guard | High |

Residual bare `requests` sites (all best-effort UI model pickers): `translation_service_dialog.py:579` (the recorded 5th), `podcast_maker_view.py:359`, `transcribe_service_dialog.py:237`, `summarization_service_dialog.py:386`, `dependency_checker.py:210`, `ai_model_section.py:380-392` — mechanical `list_ollama_models()`/`is_ollama_reachable()` swap.

## 6. Findability Spot-Test (10 questions)

| Question | Found in | Verdict |
|---|---|---|
| App entry point? | `main.py` → `ui_qt.app.run` (composition root `main.py:302`) | ✅ fast |
| LLM retry policy? | `core/llm/retry.py` (taxonomy in module docstring) | ✅ fast |
| Where are timeouts defined? | **Nowhere centrally** — 60 sites / 11 magic values (W4) | ❌ the honest gap |
| OCR engine chain order? | `core/ocr/service.py` (chain + preflight) | ✅ fast |
| Settings singleton & schema? | `utils/settings.py` + `utils/settings_schema.py` | ✅ fast |
| Output formats registry? | `core/outputs/registry.py` (21 OutputSpecs) | ✅ fast |
| Where do prompts live? | `prompts/` (61 templates) | ✅ fast |
| Which test covers fix V0.6.6? | `tests/test_v066_review_loop_fixes.py` (version-pinned naming) | ✅ fast |
| Coverage/gates config? | `pyproject.toml` addopts + CI | ✅ fast |
| Why is VRAM policy not firing? | `converter_impl.py:502` — but the docstring says otherwise (W7) | ⚠️ misleading docs |

## 7. Recommended Next-Session Directions (prioritized)

1. **Restore suite honesty** (O1/T1): decide the VRAM policy contract → restore-or-delete the W1 block + update the 12 tests + docstring + setting in ONE commit; resolve the 2 v182032 conflicts (T3) with an explicit operator decision; re-baseline to expected-zero-failures.
2. **Fix the silent-routing bugs** (W5): dual_api public-attr override + characterization test; the 6 bare-`requests` UI sites in one mechanical pass.
3. **Close the dependency drift** (W6/O5): RTL deps into pyproject + regenerate lock; markitdown extras slimming.
4. **Continue god-function decomposition** (O2) using the V0.6.7 verbatim-extraction pattern — `scholar_reflection` first (cleanest seams), then `verify_and_polish_summary` exits.
5. **Mechanical-wins queue** (O4): timeouts policy leaf, 91-file stub sweep, 9 dialog migrations, `G:\` single-sourcing.
6. **Then the bigger bets** (O3/O6): headless entry point; mypy ratchet.

## 8. Not Verified This Session (honest limits)

- Live-LLM behaviors (all `live_llm`-marked, deselected — no Ollama/llama-server in sandbox).
- Real OCR/TTS end-to-end on the rig (T5 surface): qwen OCR via real Ollama, Persian tessdata, vibevoice/sherpa audio, Unlimited-OCR torch paths.
- Coverage percentages (pyproject's `--cov` gates) — ran `--no-cov` for time; prior V0.6.7 session reported the shipped numbers.
- pip-audit re-run (offline sandbox cache); relied on the lock + waiver file state.
- The 2 v182032 failures' *intent* — mechanism is proven (T3), but which side is right is an owner decision, not an audit fact.
