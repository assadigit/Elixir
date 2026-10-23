# 📚 Elixir

> 🚀 **Turn any book into a full learning kit — locally, privately, and with an 8-layer anti-hallucination engine.**

A PySide6 desktop application that converts **PDF / EPUB / DOCX / TXT / HTML** into **19 output types** — Markdown, per-chapter summaries, keypoints, flashcards, podcast scripts **+ audio**, Obsidian knowledge bases, study guides, mind maps, Q&A, glossaries, cheatsheets, agent skills, and more — with AI summarisation and **EN ↔ FA translation**.

Runs locally on Windows 10/11 with **Python 3.12 + PySide6 6.11**. Supports local LLMs (**Ollama**) *and* cloud APIs (**OpenRouter, OpenAI-compatible, Claude, FreeLLMAPI**).

> 🧪 **Previously "MarkItDown Pro"?** You're in the right place — the app was **rebranded to Elixir** in legacy V18.20.4.11. On first launch your `~/.markitdown_pro` directory (settings, cached models, prompts, keychain secrets) is **migrated automatically** to `~/.elixir`. Nothing to do, nothing lost.
>
> 🔢 **Versioning reset:** with the rebrand complete, Elixir **dropped the legacy `V18.x` line** and versions on its own: **V0.01 = the final legacy release (V18.20.4.12) repackaged**, then V0.02, V0.03, … See the V0.01 entry in [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md) for the mapping.
>
> ℹ️ The [`markitdown`](https://github.com/microsoft/markitdown) *Python library* (Microsoft's PDF-extraction engine, used internally) keeps its name — it's a dependency, not the app.

![Version](https://img.shields.io/badge/version-0.6.64-green) ![Python](https://img.shields.io/badge/python-3.12-blue) ![Qt](https://img.shields.io/badge/GUI-PySide6%206.11-green) ![Tests](https://img.shields.io/badge/tests-8584%20passed%20%2F%2016%20failed-yellow) ![Privacy](https://img.shields.io/badge/privacy-local--first-orange)

---

## 🌟 Why Elixir?

- 🔒 **Local-first & private** — runs 100% offline with Ollama. Your books never leave your machine unless *you* choose a cloud provider.
- 🛡️ **Anti-hallucination engine** — 8 defensive layers (deterministic + LLM-based) verify every bullet against the source before it ships.
- 📦 **19 output types** from one conversion — from a one-page executive briefing to a full Obsidian knowledge base.
- 🎙️ **Podcast-ready** — 2-host podcast scripts *and* TTS audio (NeuTTS/Kokoro for English, Coqui XTTS v2 for Farsi; V0.6.64: Piper removed).
- 🌐 **Bilingual** — full English ↔ Farsi translation pipeline (NLLB-200 or TranslateGemma).
- 🖥️ **VRAM-aware** — estimates context windows and VRAM budgets from your actual GPU, and (as of V18.20.4.10) **fails fast** instead of warn-and-continue when a model won't fit.
- 🧪 **5,400+ passing tests** — a characterization-test safety net pins every behavior before refactors touch it, including 124 Hypothesis property tests.

---

## 🚀 Quick Start

### 1️⃣ Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2️⃣ System dependencies (Windows)

| Tool | Purpose | Link |
|---|---|---|
| 🔍 **Tesseract OCR** | Fallback OCR (+ Persian `fas` pack) | [UB-Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki) → install to `C:\Program Files\Tesseract-OCR` |
| 📄 **Poppler** | PDF page rendering | [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) |
| 🦙 **Ollama** | Local LLM server | [ollama.com](https://ollama.com) |
| 🗣️ **NeuTTS-Air GGUF** *(optional)* | English TTS | place `.gguf` in `G:\Program Files\neutts-air\models\` |
| 🧪 **langextract** *(optional)* | Scientific Evidence Map output | `pip install langextract` |

### 3️⃣ Pull Ollama models

```bash
ollama pull qwen3-vl:8b                              # 🖼️ OCR (or use OlmOCR-2-7B)
ollama pull Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M    # 🧠 Summarisation (primary)
ollama pull translategemma-4b-it:q5_k_m              # 🌐 Translation backup (optional)
```

### 4️⃣ Configure paths (first run)

After first launch, open `~/.elixir/settings.json`:

```json
{
  "paths": {
    "tesseract": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    "poppler":   "C:\\poppler-24.08.0\\Library\\bin",
    "neutts_gguf": "G:\\Program Files\\neutts-air\\models\\neutts-air-Q8_0.gguf"
  }
}
```

> 💡 Leave `poppler` as `""` if it's already in your system PATH.

### 5️⃣ Run it! 🎉

```bash
python main.py
```

> ℹ️ Optional feature groups (TTS audio, EPUB/Anki formats, RAG, grounding)
> are opt-in extras since V0.13 — see the header of `requirements.txt`.

### 📦 Building the Windows installer (one command)

On a Windows 10/11 machine with Python 3.12 and the repo checked out:

```bash
python build_installer.py
```

That single command packs the app with PyInstaller (onedir, for fast startup),
verifies it (self-test → launch test → silent install test), and produces
**`dist_installer\Elixir-Setup-<version>.exe`** — a double-click installer
(Inno Setup, auto-installed via winget if missing). The builder also bundles
the small external tools whose licences allow it (ffmpeg, poppler); model
weights, Ollama and API keys are never bundled. If the packed app closes
right after starting, run `python build_installer.py --debug` to see the
crash text. Everything is logged to `build_installer.log`.

The installed app keeps its settings in `%LOCALAPPDATA%\Elixir` (never writes
inside the install folder); running `python main.py` from source keeps using
`~/.elixir` exactly as before, and an existing `~/.elixir` is copied over
automatically on the installed app's first launch. The installer bundles
ffmpeg + Poppler (licence-permitted); Ollama, Tesseract and model weights
stay external. The VibeVoice / Qwen3-TTS engines need the Python source
install — the installed app says so clearly if you try them (Kokoro
TTS works normally). A CI workflow
(`.github/workflows/windows-installer.yml`) builds the same installer on
GitHub's Windows runners.

---

## 🧠 How It Works

```
PDF / EPUB / DOCX / TXT / HTML
  │
  ├─ 💻 Digital pages  →  markitdown extraction  →  clean Markdown
  └─ 📷 Scanned pages  →  OCR cascade            →  clean Markdown
       (markitdown → OlmOCR-2-7B / Qwen3-VL → PaddleOCR → Tesseract)
          │
          ▼
   🔧 Hyphenation repair + paragraph joining + header/footer removal
          │
          ▼
   📑 TOC segmentation  (heading patterns + LLM fallback + token fallback)
          │   └─ V18.20.4.10: metadata-children exclusion, bounded merge,
          │      nearest-following page markers, monster-segment gate
          ▼
   ✅ Chapter selection (optional)
          │
          ▼
   🔍 Concept extraction (deterministic — guides the LLM, no hallucination)
          │
          ▼
   🤖 LLM summarisation (Ollama 9B or cloud)
       │  ├─ 🧹 Thinking-strip + narrative filter
       │  ├─ 🗳️ B3 multi-sample dedup (3 temperatures, voting)
       │  ├─ 📊 Quality scorer (0–100)
       │  ├─ 🔢 Numeric verification
       │  ├─ ⚖️ Content Judge grounding (langextract + LLM-as-judge)
       │  ├─ ♻️ Recovery pass (resurrects high-overlap bullets)
       │  └─ 🗺️ Map-Reduce for oversized chapters
       │      └─ V18.20.4.10: wall-clock budget + loud abort — never a silent stall
          │
          ▼
   📌 Keypoints + Simplified keypoints
          │
          ▼
   📦 15 Output Studio generators
          │
          ▼
   🌐 Translation (EN ↔ FA, NLLB-200 or TranslateGemma)  [optional]
          │
          ▼
   🔊 TTS audio (NeuTTS / Kokoro)  [optional]
```

---

## 📦 The 19 Output Types

### 🎯 4 Core outputs (always available)

| Output | Description |
|---|---|
| 📝 **Per-chapter Summaries** | Executive (150–200 words) + thorough (800–1200 words) per chapter |
| 🔑 **Keypoints** | Bullet points extracted from each chapter |
| ✨ **Simplified Keypoints** | Jargon-free version (simplification pass) |
| 📄 **DOCX Report** | Formatted Word document with TOC |

### 🎨 15 Output Studio extras (opt-in)

| Output | Description | Default |
|---|---|:---:|
| 📊 Executive Briefing | One-page synthesis of the whole book | ✅ on |
| 🎙️ Podcast Script | 2-host conversational script (text only) | ✅ on |
| 🃏 Flashcards | Anki-compatible TSV + readable MD | ✅ on |
| 🧩 Packets of Knowledge | Clustered keypoints synthesised into cohesive paragraphs | ⬜ off |
| 🗂️ Obsidian Knowledge Base | Linked notes with YAML frontmatter + wikilinks | ⬜ off |
| 📖 Study Guide | Objectives, glossary, Q&A, self-check | ⬜ off |
| 📱 Social Media Pack | X thread + LinkedIn + hashtags | ⬜ off |
| 🕸️ Mind Map | Mermaid mindmap + outline (deterministic, no LLM) | ⬜ off |
| 🎧 Podcast Audio | TTS audio (EN → NeuTTS/Kokoro, FA → Coqui XTTS v2) | ⬜ off |
| 🧪 Scientific Evidence Map | Interactive HTML with langextract verbatim grounding | ⬜ off |
| ❓ Q&A Study Questions | Self-test questions + answers per chapter | ⬜ off |
| 📚 Glossary | All terms + definitions extracted from the book | ⬜ off |
| 🧠 Patterns / Techniques | Recurring methods + frameworks across chapters | ⬜ off |
| 📋 Cheatsheet | One-page quick-reference of key facts | ⬜ off |
| 🤖 Agent Skill | Package the book as a ClawHub-style installable `SKILL.md` | ⬜ off |

> 🗄️ The output list is driven by `core/outputs/registry.py` — the single source of truth shared by the wizard, output-types dialog, settings dialog, and controller.

---

## 📁 Output Structure

```
output/
└── MyBook/
    ├── markdown/            ← 📝 full book + per-chapter MD (RAG-friendly)
    ├── summaries/           ← 📃 aggregated + per-chapter summaries
    ├── keypoints/           ← 🔑 keypoints + simplified keypoints
    ├── briefing/            ← 📊 Executive Briefing      (if enabled)
    ├── podcast/             ← 🎙️ script + audio          (if enabled)
    ├── flashcards/          ← 🃏 .md + .tsv             (if enabled)
    ├── packets/             ← 🧩 Packets of Knowledge    (if enabled)
    ├── obsidian/            ← 🗂️ Obsidian KB             (if enabled)
    ├── study_guide/         ← 📖 Study Guide             (if enabled)
    ├── social/              ← 📱 Social Media Pack       (if enabled)
    ├── mindmap/             ← 🕸️ Mind Map                (if enabled)
    ├── evidence/            ← 🧪 Evidence Map            (if enabled)
    ├── qa/  glossary/  patterns/  cheatsheet/  skill/    (if enabled)
    ├── fa/                  ← 🌐 Farsi translations      (if enabled)
    ├── logs/
    │   ├── conversion.log.md
    │   ├── quality_report.json
    │   └── drops.jsonl      ← 🧾 full quarantine audit trail
    └── .checkpoint.json     ← ⏯️ crash-safe resume state
```

---

## 🤖 LLM Providers

| Provider | Setting | Notes |
|---|---|---|
| 🦙 **Ollama** *(default)* | `summarisation.provider = "ollama"` | Local, free, offline. RTX 3060 12GB handles 9B Q4 models at 128k context. |
| ☁️ **OpenRouter** | `"openai_compat"` | Cloud, pay-per-token. Default model: `google/gemini-2.5-flash-preview:free` |
| 🔌 **OpenAI-compatible** | `"openai_compat"` | Any OpenAI-API-compatible endpoint (LM Studio, vLLM, …) |
| 🟣 **Claude (Anthropic)** | `"claude"` | Direct Anthropic API. Model: `claude-3-5-sonnet-20241022` |
| 🆓 **FreeLLMAPI** | `"freellmapi"` | Local proxy at `localhost:3001` |

> 🔐 **Cloud API keys are stored in the OS keychain** (Windows Credential Manager via the `keyring` dependency — V0.16). On first use, any legacy plaintext key in `~/.elixir/settings.json` is **migrated automatically** (the plaintext copy is removed only after the keychain write succeeds — no data loss possible), with a one-time WARNING in the log and a "🔐 Stored in the OS keychain" hint next to every API-key field in Settings. On backend-less systems (headless Linux), keys degrade to plaintext settings.json with a per-store WARNING — the app works everywhere.

## 🌐 Translation (EN ↔ FA)

- **TranslateGemma-12B** *(default — Ollama)* — context-aware, professional-grade Farsi (default model per [`docs/USER_OLLAMA_MODELS.md`](docs/USER_OLLAMA_MODELS.md))
- **NLLB-200-600M** *(retired V18.20.4.6+)* — the legacy HuggingFace backend; existing `translation.backend = "nllb"` settings migrate to Ollama automatically on load

Per-output translation selection: choose which outputs (chapter summaries, keypoints, podcast, …) to translate after conversion.

---

## 🛡️ Anti-Hallucination Defense (8 Layers)

Every summary bullet must survive all eight gates:

1. 🧷 **Concept injection** — deterministic keyword extraction guides the LLM
2. 🔢 **Numeric verification** — fabricated numbers/misquotes are dropped
3. 🧹 **Thinking-strip** — `<think…` leakage + reasoning-process bullets removed
4. 📖 **Narrative filter** — story bullets with no concept indicator dropped
5. 📏 **F4 source-overlap** — <25% content-word overlap → drop
6. 🧮 **Phase 2.2 semantic fact-check** — embedding similarity <0.5 → drop
7. ⚖️ **Content Judge** — LLM-as-judge grounding
8. 🔬 **langextract verbatim grounding** — deterministic claim extraction

### ♻️ Bullet Preservation & Quarantine

Every drop is logged to `logs/drops.jsonl` with the bullet text, the pipeline stage that dropped it, the threshold applied, and the measured source-overlap. A **recovery pass** resurrects any quarantined bullet with >30% source overlap.

- 🐢 **Conservative mode** (Wizard → Advanced) disables all drops except thinking/prompt-leakage — all would-be drops still logged for audit.
- 🔍 The **Quarantine tab** in the UI shows every dropped bullet with a **Restore** button.

### 🧮 Embedder (Phase 2.2 back-end)

| Model | Format | Size | Setting |
|-------|--------|------|---------|
| `BAAI/bge-small-en-v1.5` *(default)* | HF safetensors | ~130 MB | `embedding.model` |
| `qwen3-embed` | Ollama GGUF (0.6B) | ~600 MB | `embedding.model` |

V18.2.44-hardened: a silently-broken backend (zero/NaN vectors) is caught at load time and degrades to Jaccard word-overlap with one loud WARNING — never a silent false 0% coverage. Full details: [`docs/EMBEDDERS.md`](docs/EMBEDDERS.md).

Optional-mode knobs:

```json
{
  "embedding": {
    "enabled": false,     // true = gold-standard semantic path (default)
    "fallback": "skip",   // "jaccard" = lexical fallback, "skip" = omit Phase 2.2
    "model": "BAAI/bge-small-en-v1.5"
  }
}
```

---

## 🔥 VRAM Guardian (new in V18.20.4.10)

A real-world incident (a 257-page book on a 12GB GPU with a 20.2GB model) produced a **4-root-cause hotfix**:

| Fix | What changed |
|---|---|
| 📊 **Honest token estimates** | Chapter count now comes from the PDF outline first (was: a regex that counted *any* short numbered line → ~5M-token estimates, ~7× inflated) |
| 📑 **Metadata-children exclusion** | Outline levels that only repeat author names on the same page as real chapters are no longer treated as chapters (the "97 essays became 97 *author* segments" bug) |
| 🧱 **Bounded short-segment merge** | Short chapters merge up to `2 × min_pages`, then a new group starts — the whole-book "monster segment" cascade is structurally impossible now |
| 🗺️ **Map-Reduce rails** | Wall-clock budget for the whole map phase (`local.map_phase_max_seconds`, default 1800s) → a chapter **fails loudly** instead of silently grinding for days |
| ⚡ **VRAM fail-fast** | `local.vram_overbudget_policy` ∈ `ask` *(default — wizard asks with **Abort preselected**)* / `abort` / `proceed`. Queue & service starts (no UI to ask) always abort with guidance. No more warn-and-continue. |

---

## ⚡ Performance Levers (new in V0.19, Phase 6)

LLM time is **98.5% of chapter wall-clock** (Phase-1 baseline), so Phase 6
targets the *sequencing* of the intra-chapter LLM calls. Three overlap
levers + cloud queue concurrency, all measured on the deterministic
mock-latency bench ([`docs/baseline/timings_V0.19.md`](docs/baseline/timings_V0.19.md)):

| Lever | Path | Measured |
|---|---|---|
| 🗺️ **Map waves** | Map-reduce chunks run in bounded concurrent waves (independent by design; the wall-clock budget is enforced per wave) | **−57.0%** (315.8s → 135.8s, 13 chunks) |
| 🗳️ **B3 overlap** | The 3 multi-sample voting calls run concurrently; the 2×120s inter-sample VRAM sleeps are skipped on this path | **−44.2%** (115.4s → 64.4s) |
| 🎓 **Speculative scholar** | The scholar reflection launches while the judge tail runs, and is **merged** when the judge left the summary unchanged (the common case) or discarded + re-run sequentially when it did not — drop paths are byte-for-byte the old behavior | **−23.3%** on the golden chapter (its 5 calls form a strict chain — 23.3% is the mathematical cap for any behavior-preserving overlap; the proof is in the report) |
| ☁️ **Cloud queue** | Up to `queue.max_parallel_books` books convert concurrently in the Queue view — **cloud providers only** (local VRAM is never contested) | bounded, opt-in |

**Safety contract:** every lever is OFF by default
(`summarisation.parallel_stages`), each independently disableable, and the
outputs are **byte-identical with the levers ON vs OFF** on all 6 golden
chapters (pinned by test + the Phase-4 eval gate). Local 12GB-rig behavior
is unchanged by default — enable on the rig and soak-test before making it
your daily configuration. Reproduce any number:
`python scripts/bench_chapter.py --latency-scale 1.0 --parallel-stages`.

Cache instrumentation (Phase 6.4) landed alongside: response-cache and
embedding-cache hit-rate summaries at the end of every run (plus a
mid-run periodic line and the eviction counter — the budget-tuning
signal).

---

## ⚙️ Key Settings

Settings file: `~/.elixir/settings.json`

| Key | Default | Description |
|---|---|---|
| `ocr.primary_model` | `qwen3-vl:8b` | Ollama model for OCR |
| `summarisation.provider` | `ollama` | `ollama` / `openai_compat` / `claude` / `freellmapi` |
| `summarisation.model` | `Qwythos-9B-…` | Ollama model for summaries |
| `summarisation.max_context_tokens` | `131072` | Context window (auto-detected from VRAM) |
| `summarisation.coverage_threshold` | `0.70` | Min keyword coverage (auto-lowered to 0.60 after 3 retries) |
| `grounding.enabled` | `true` | langextract verbatim grounding |
| `embedding.enabled` | `true` | Gate the semantic fact-check path |
| `embedding.fallback` | `"jaccard"` | `"jaccard"` (lexical) or `"skip"` (omit Phase 2.2) |
| `local.vram_overbudget_policy` | `"ask"` | `ask` / `abort` / `proceed` — enforced before extraction |
| `local.map_phase_max_seconds` | `1800` | Wall-clock budget for a map-reduce map phase |
| `summarisation.parallel_stages` | `false` | **V0.19 (Phase 6)** — master switch for the intra-chapter LLM-call overlap levers (see ⚡ Performance Levers) |
| `summarisation.parallel_stages_map` | `true` | Map-reduce chunk overlap (when master ON) |
| `summarisation.parallel_stages_b3` | `true` | Multi-sample voting overlap (when master ON) |
| `summarisation.parallel_stages_judge_scholar` | `true` | Speculative scholar ∥ judge tail (when master ON) |
| `summarisation.parallel_stages_max_workers` | `4` | Concurrency bound for every lever (clamp 1–8) |
| `queue.max_parallel_books` | `2` | **V0.19 (Phase 6.3)** — cross-book queue workers, CLOUD providers only (clamp 1–4; local always sequential) |
| `translation.backend` | `nllb` | `nllb` / `translategemma` |
| `paths.*` | *(system paths)* | tesseract, poppler, neutts_gguf |
| `outputs.*` (15 keys) | varies | Output Studio toggles |

---

## 🧰 Technology

| Component | Technology |
|---|---|
| 🖥️ GUI | PySide6 6.11 (Qt for Python) |
| 📄 PDF extraction | markitdown (primary), pypdf (fallback) |
| 📷 OCR | OlmOCR-2-7B / Qwen3-VL via Ollama, PaddleOCR, Tesseract |
| 🧠 Summarisation | Ollama 9B (Qwythos-9B) or cloud APIs |
| 🌐 Translation | NLLB-200-600M (HuggingFace), TranslateGemma-4B (Ollama) |
| 🔊 TTS | NeuTTS-Air (Ollama GGUF), Coqui XTTS v2 |
| 📝 DOCX | python-docx |
| 🔢 Tokens | tiktoken |
| 🌍 HTTP | requests (proxy-proof) |
| 🔬 Grounding | langextract (Google) |

---

## 🧪 Development & Testing

```bash
# ▶️ Run the app
python main.py

# 🧪 Full test suite (5,500+ tests, ~160s headless)
python -m pytest tests/ --no-cov -q

# ⚡ Fast iteration — skip the slow/integration tests (~68s, 2.3× faster)
python -m pytest tests/ --no-cov -q -m "not slow"

# 🎲 Random-order determinism smoke (3 seeds, all must pass identically)
python -m pytest tests/ --no-cov -q -p randomly --randomly-dont-reset-seed --randomly-seed=101

# 📊 Summary-quality scorecards over the 6 golden chapters (ROUGE-L, faithfulness,
#    hallucination-rate, coverage, length policy — deterministic, mock LLM)
make eval

# 🚦 Accuracy regression gate — fails on quality regressions vs the committed
#    baseline (tests/golden/eval_baseline.json); CI runs this on every push
make eval-check

# 🧹 Lint
ruff check .

# 🏆 Golden-master audit (requires bun + z-ai-web-dev-sdk)
pytest --audit --audit-summary=path/to/summary.md --audit-source=path/to/source.md
```

**Current gate (Elixir V0.6.64, measured 2026-10-23 post-Piper-removal):** `8584 passed / 16 failed / 25 skipped in ~273s headless` *(Linux sandbox, offscreen Qt, requirements.lock-aligned environment; -14 vs V0.6.63 = the Piper engine's own tests removed with the engine — V0.6.64, user decision; the 16 failures are the SAME documented pre-existing families — TTS/ffmpeg/vibevoice environment-dependent e2e ×12, eval gate ×2, prompt-manifest drift ×1, source pin ×1 — all reproducible solo; any NEW failure is a regression)*

**Test markers** (registered, `--strict-markers`-enforced):

| Marker | Meaning | Use |
|---|---|---|
| `slow` | Tests that take >2s on a warm machine (retry-ladder sleeps, end-to-end flows, heavy AST sweeps) | `pytest -m "not slow"` for fast iteration |
| `integration` | Multi-module flow tests (may touch the filesystem) | `pytest -m integration` to run just the flows |
| `regression` | Version-anchored regression tests (`test_v18_*` files) | — |
| `characterization` | Byte-for-byte stability gates for extracted modules | — |
| `gpu` | Tests requiring a real GPU (currently none — all mocked) | — |

**Accuracy & reliability harness (V0.17, Phase 4):** summary-quality
regressions are mechanically detectable *before* any prompt or pipeline
change ships —

- **6 golden chapters** under `tests/golden/` (academic, nonfiction,
  academic_tables, scanned_ocr, multicolumn, farsi) each carry a source,
  a curated reference summary, and a byte-frozen pipeline output
  (`tests/test_golden_freeze.py`, 14 tests — the Phase-5 pre-net).
- **`scripts/eval_summary.py`** scores every chapter deterministically
  (ROUGE-L vs the reference, char-gram faithfulness + hallucination-rate
  vs the source, keyword coverage, REAL length-policy targets, the REAL
  F4 overlap) into scorecards matching `docs/EVALUATION_FRAMEWORK.md`
  Part 2 — the LLM judge stays the real-rig audit; this is the CI proxy.
- **The gate** (`make eval-check`) fails on regressions vs the committed
  baseline and is mutation-validated (`tests/test_p4_eval_gate.py`:
  fabricated bullets and prompt-bank changes are both caught, improvements
  never trip it). CI uploads per-chapter scorecards on every run.
- **LLM-call hardening** audited end-to-end — every provider path carries
  timeout, classified retry with backoff, non-retryable handling, response
  validation, and the lenient-JSON repair; the evidence matrix lives in
  `docs/LLM_HARDENING.md` (36 evidence tests).

**Coverage gates (V0.15, Phase 2):** global ≥64% on `core`+`utils`, plus per-package ≥80% on `core/llm` (currently 96%), `core/pdf` (98%), and `core/summarisation` (91%) — the safety net under the Phase 5 de-monolithization of `summarizer.py`.

### 🏗️ Project Layout

```
Elixir/
├── main.py                  ← 🚪 entry point + crash reporting
├── controller.py            ← 🎛️ orchestration bridge (UI ⇄ core)
├── core/
│   ├── pdf/                 ← 📄 extraction, TOC, layout, footnotes, math
│   ├── segmentation/        ← 📑 TOC / heading / semantic / token segmenters
│   ├── summarisation/       ← 🧠 the 8-layer pipeline + map-reduce
│   ├── llm/                 ← 🤖 providers, dispatcher, cache, retry, taxonomy
│   ├── translation/         ← 🌐 EN↔FA engines + glossary + validator
│   ├── tts/                 ← 🔊 NeuTTS / Kokoro / Coqui / Qwen / VibeVoice engines
│   ├── ocr/                 ← 📷 OCR cascade + prescan
│   ├── outputs/             ← 📦 all 19 output generators + registry
│   ├── pipeline/            ← ⚙️ converter, checkpoints, token estimator
│   ├── obs/                 ← 👁️ manifest, tracing, progress, remediation
│   └── system/              ← 🛡️ preflight, supervisor, thermal, hardware
├── ui_qt/                   🖥️  PySide6 views, wizard steps, components
├── prompts/                 ← ✍️ all LLM prompt templates (versioned)
├── tests/                   ← 🧪 5,800+-test characterization suite
├── docs/                    ← 📚 EMBEDDERS, models, evaluation framework
├── installer/               ← 📦 Inno Setup script
└── utils/                   ← 🔧 settings, logging, atomic IO, text quality
```

---

## 📊 Project Status

**Current version: Elixir V0.4.25.** Release history lives in [`CHANGELOG.md`](CHANGELOG.md) (V0.4.x line, detailed); everything older — the V0.20.x audit campaigns, V0.13–V0.19, V0.01–V0.12, and the legacy `V18.x` era — is archived verbatim in [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md), with an era summary in [`Project-History.md`](Project-History.md).

### ✅ Independent SWOT Audit (V18.20.4.9 baseline)

A full verification pass against the V18.20.4.0 SWOT analysis (99 findings + 22 strengths, every claim checked at file:line level):

| Category | ✅ Fixed | 🟡 Partial | ❌ Open | 🔴 Regressed |
|---|:---:|:---:|:---:|:---:|
| **Overall (99 findings)** | **55** | **15** | **29** | **0** |
| Strengths (S1–S22) hold | **22 / 22** ✅ | — | — | — |

- 🧪 Test gate independently reproduced: `2947 passed / 0 failed` at V18.20.4.9 (env-accounted exact match), now `2973` after the V18.20.4.10 hotfix (+26 regression pins).
- 🏆 All 10 self-identified top-priority SWOT items: **fixed and verified**.
- 📈 56% of all findings fully fixed; 71% counting partials — with **zero regressions** across the decompositions of V18.20.4.1–.4.9.

### 🗺️ Roadmap (prioritized from the audit's open items)

1. ✅ ~~`find_analysis_for_heading` heading-ignored bug~~ — **fixed in V18.20.4.11** (per-heading matching ladder, fail-closed)
2. ✅ ~~Unify ~10 hand-rolled LLM call stacks~~ — **fixed in V18.20.4.11** (pooled sessions tree-wide, shape-safe parsing; per-site retry folding remains future work)
3. ✅ ~~Close parallel-stage shared-state races~~ — **fixed in V18.20.4.11** (thread-local chapter context, all 7 attributes)
4. ✅ ~~Raise buried logs~~ — **fixed in V18.20.4.11** (4 sites now WARNING)
5. ✅ ~~Model-literal cleanup~~ — **fixed in V18.20.4.11** (model_taxonomy single source)
6. ✅ ~~response_parser silent fallbacks~~ — **fixed in V18.20.4.11** (full ladder logging)
7. ✅ ~~Blind post-completion shutdown/sleep~~ — **fixed in V18.20.4.12** (rc/stderr verified, loud WARNING + platform hint)
8. ✅ ~~Scholar gap-fill parse-once/drop-tail~~ — **fixed in V18.20.4.12** (one additive continuation retry)
9. ✅ ~~404 handled three ways~~ — **fixed in V18.20.4.12** (shared `model_errors` module, canonical pull hint)
10. ✅ ~~Hygiene nine-pack~~ — **fixed in V18.20.4.12** (/no_think Qwen-gated, log rotation, Settings.batch(), progress JSON, HF offline scoped, qwythos de-magic + two 404-default bug fixes, engine_cache shutdown hook, atomic output writes, comment de-jargon)
11. ✅ ~~Migrate cloud API keys to the OS keyring~~ — **fixed in V0.16 (Phase 3)**: `keyring` ships as a core dependency, every credential path (all 11, incl. dual-api fast key, llamacpp token, TTS normalizer, translation, grounding, and the named-provider catalog) routes through `get_secret`/`set_secret`, the `translation.api_key` path-mismatch is reconciled, and CI runs a gated pip-audit over the locked dependency closure
12. ✅ ~~Orchestrator decomposition round 3~~ — **done in the V0.4.25 audit session**: `convert()` decomposed 1,054 → 601 lines (−43%) and `core/pipeline/converter_impl.py` 2,175 → 1,577 via three verbatim extractions — `conversion/reporting.py`, `conversion/summary_outputs.py`, `conversion/finalization.py` (commits `e3e7e7f`/`50d9a63`/`7a8e451`, behind the `29b6c58` characterization net). The remaining hot spot is `_summarize_inner` (349 lines in `summarizer.py`).
13. 🧪 **Real-rig 97-Things re-run** — validate the V18.20.4.10 segmentation fixes end-to-end
14. ✅ ~~Green CI / fresh installs~~ — **fixed in V0.13 (Phase 0)**: see [`docs/AUDIT_SWOT_V0.11.md`](docs/AUDIT_SWOT_V0.11.md) and the V0.13 changelog entry

### ⚠️ Known Issues

1. `summarizer.py` remains the pipeline's orchestrator hub (1,990 lines as of V0.4.25, down from 5,803 through the V18.x/V0.x extraction campaigns; fan-out 38, fan-in 26 — measured in the V0.4.25 audit session) — further decomposition is roadmap item 12.
2. `[space/fix]` post-check occasionally splits correct compound words ("thereby" → "the reby"); auto-corrected by `[extra_space/fix]`.
3. The V18.20.4.9 user-machine pre-chunk stall was environmental (not reproduced in-sandbox); V18.20.4.10 bounds and surfaces it if it recurs.
4. `PromptContext` + `build_primary_prompt` remain in `prompt_assembly.py` unused (V18.6.3 crash pattern — kept frozen deliberately).

---

## 📜 History & Changelog

- 📋 [`CHANGELOG.md`](CHANGELOG.md) — every release, incident, and fix with full evidence
- 🗄️ [`CHANGELOG_ARCHIVE.md`](CHANGELOG_ARCHIVE.md) — every pre-V0.4.x entry, verbatim
- 📖 [`Project-History.md`](Project-History.md) — era summary + pointer; long-form story archived
- 🧭 [`NEW_SESSION_PROMPT.md`](NEW_SESSION_PROMPT.md) — working agreements for AI-assisted sessions

---

## 📄 License

Personal use. See project files for details.
