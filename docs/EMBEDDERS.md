# Embedder Reference & Configuration (V18.4)

This document covers the **embedding models** used by MarkItDown Pro's
semantic-similarity path (Phase 2.2 — the content-judge coverage /
grounding / hallucination check) and the **optional-mode knobs** added in
V18.4 that let you disable or degrade that path explicitly.

> **What the embedder does.** After the LLM produces a chapter summary, the
> `ContentJudge` (`core/summarisation/content_judge.py`) splits the source
> text into ~2000-token chunks, extracts key claims deterministically, then
> embeds both the claims and the summary's bullets/thorough and computes
> cosine similarity. A claim with best-similarity ≥ 0.50 against any summary
> text is "covered"; a bullet with no source match is "ungrounded"
> (hallucination candidate). This is the **Phase 2.2 semantic fact-check**.
>
> When the embedder is unavailable, the judge falls back to Jaccard
> word-overlap (a real but weaker lexical signal). V18.4 makes the
> disable / fallback choice **explicit and user-configurable** rather than
> only triggered by a broken backend.

---

## 1. Recommended embedders

MarkItDown Pro's embedder backend (`core/llm/embedder_backend.py`) supports
two formats, auto-selected from the model name. Both are production-viable;
pick based on whether you already run Ollama.

### A. `BAAI/bge-small-en-v1.5` — HuggingFace safetensors (DEFAULT)

- **Setting key:** `embedding.model`
- **Default since:** V18.2.2 (switched from `bge-base` → `bge-small`)
- **Format:** HuggingFace safetensors, loaded via `sentence-transformers`
- **Size:** ~130 MB on disk (fits anywhere — even a 4 GB Pi)
- **Dimension:** 384
- **MTEB score:** ~62 (strong for the size; strictly better than
  `all-MiniLM-L6-v2` with zero recalibration risk)
- **Device:** `auto` → CUDA if >0.6 GB VRAM free, else CPU (~1–3 s/batch on
  CPU, <0.5 s on GPU)
- **Caching:** downloaded ONCE to `~/.markitdown_pro/models/BAAI--bge-small-en-v1.5/`
  then loaded 100 % offline on every subsequent launch. 60 s download
  timeout prevents hub-hang.

**Install (one-time, automatic):** just set the model name and run a
conversion — the first run downloads it. Or pre-seed:

```bash
pip install sentence-transformers>=2.7.0
python -c "from sentence_transformers import SentenceTransformer; \
           SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

**settings.json:**

```json
{
  "embedding": {
    "model": "BAAI/bge-small-en-v1.5",
    "device": "auto",
    "cache_enabled": true
  }
}
```

> **Why bge-small over MiniLM?** `all-MiniLM-L6-v2` (80 MB) is the
> sentence-transformers default, but on some RTX 3060 setups it loads yet
> silently produces zero vectors (a CUDA forward-pass OOM that
> SentenceTransformer swallows into a zero tensor instead of raising). The
> V18.2.44 `SentenceTransformerBackend.smoke_test()` now catches this at
> load time, but `bge-small` avoids the failure mode entirely and scores
> higher on MTEB. Use MiniLM only if you are VRAM-starved AND bge-small
> fails to load.

### B. `qwen3-embed` — Ollama GGUF

- **Setting key:** `embedding.model` (set to the Ollama model name, NOT the
  GGUF filename)
- **Format:** GGUF, served via Ollama's `/api/embed` endpoint
- **Recommended GGUF:** `Qwen3-Embedding-0.6B-Q8_0.gguf` (0.6 B params,
  ~600 MB, dimension 1024)
- **MTEB score:** ~70+ (Qwen3-Embedding family is currently the top open
  small embedder on the MTEB leaderboard)
- **When to use:** you already run Ollama for the summarization LLM and
  want one unified model server (no separate sentence-transformers +
  torch dependency). Also useful when GPU VRAM is fully consumed by the
  LLM — the embedder runs on Ollama's CPU thread pool without competing
  for CUDA.

**Install:**

```bash
# 1. Download the GGUF (example: Qwen3-Embedding-0.6B, Q8_0)
#    from https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF

# 2. Register it as an Ollama model. Create a Modelfile:
cat > /tmp/Modelfile.qwen3-embed <<'EOF'
FROM ./Qwen3-Embedding-0.6B-Q8_0.gguf
PARAMETER temperature 0
EOF

# 3. Create the Ollama model (name it "qwen3-embed")
ollama create qwen3-embed -f /tmp/Modelfile.qwen3-embed

# 4. Verify
ollama list | grep qwen3-embed
```

**settings.json:**

```json
{
  "embedding": {
    "model": "qwen3-embed",
    "cache_enabled": true
  }
}
```

> **Backend auto-detection.** `core/llm/embedder_backend.is_ollama_embed_model()`
> treats a model name as Ollama if it contains `:`, ends in `.gguf`, or is a
> bare single token without `/` or `.` (e.g. `qwen3-embed`). HF names
> (`org/model`) always use the sentence-transformers path. You can force the
> Ollama backend explicitly with `"embedding.backend": "ollama"`.

> **Smoke-test.** Both backends run a `smoke_test()` on first load
> (`encode("health check")`, assert non-zero / non-NaN / dim ≥ 32). A
> failure marks the backend `.healthy = False`, logs one ERROR, and the
> content-judge falls back to Jaccard (or skips — see §2). The smoke-test
> is the single most important defence against the V18.2.20
> "coverage = 0 % (0/46 claims)" regression caused by silent zero vectors.

---

## 2. Optional-mode knobs (V18.4 — Phase 2)

Two new settings give you explicit control over the semantic path. Both
live under the `embedding` section and are validated by the Pydantic
`_EmbeddingSchema` in `utils/settings_schema.py`.

| Key | Type | Default | Valid values |
|-----|------|---------|--------------|
| `embedding.enabled` | bool | `true` | `true` / `false` |
| `embedding.fallback` | string | `"jaccard"` | `"jaccard"` / `"skip"` |

### Behaviour matrix

| `enabled` | `fallback` | Phase 2.2 behaviour |
|-----------|-----------|---------------------|
| `true` | _(ignored)_ | **Embedder used.** On backend failure (smoke-test failed, zero vectors, model not pulled) → automatic Jaccard fallback with one WARNING. This is the gold-standard behaviour (9/10 audit, 0 hallucinations). |
| `false` | `"jaccard"` | **Embedder NOT attempted.** Coverage / grounding computed via Jaccard word-overlap only (weaker but real lexical signal; coverage % still runs, gap-fill still possible). One INFO log at first use. Use when the embedder is unreliable on your hardware but you still want a coverage measurement. |
| `false` | `"skip"` | **Phase 2.2 skipped ENTIRELY.** No similarity computation, no coverage %, no gap-fill. One WARNING per chapter. Coverage auto-passed (`coverage_skipped=True` on the `JudgeResult`). The deterministic judge + postchecks (`postchecks.py`) still run downstream. Use only when you trust the LLM output completely OR need maximum speed on a constrained device. |

### When to use which

- **Default (`enabled=true`)** — almost always. This is the audited
  gold-standard path. The smoke-test + degenerate-vector guard already
  handle a broken embedder gracefully (Jaccard fallback).
- **`enabled=false, fallback="jaccard"`** — your embedder is chronically
  unhealthy (e.g. `all-MiniLM-L6-v2` zero-vector OOM on your specific GPU
  driver) AND you don't want to spend VRAM/CPU on a retry loop. You keep a
  real coverage signal.
- **`enabled=false, fallback="skip"`** — speed-critical batch runs on a
  CPU-only laptop, or you are processing a trusted model's output and want
  to skip the ~5–10 s/chapter embedder cost entirely. **You lose the
  coverage / hallucination signal** — rely on the deterministic judge and
  postchecks instead.

### Example: fully disable Phase 2.2

```json
{
  "embedding": {
    "enabled": false,
    "fallback": "skip",
    "model": "BAAI/bge-small-en-v1.5"
  }
}
```

The `model` is kept so that re-enabling (`"enabled": true`) later is a
one-line change — no need to re-enter the model name.

### How the skip is implemented (non-silent)

The skip is **explicit and loud**, never silent:

1. `ContentJudge.judge()` reads `embedding.enabled` + `embedding.fallback`
   ONCE at the top of the Q1 (coverage) block.
2. If `enabled=false` + `fallback="skip"`, it short-circuits the whole
   coverage loop: sets `coverage_pct=1.0` (auto-pass), empties
   `uncovered_claims` (so nothing triggers gap-fill), sets
   `result.coverage_skipped=True`, and logs one WARNING.
3. `JudgeResult.format_report()` appends `coverage=SKIPPED(embedding off)`
   so the skip is visible in every chapter's judge line.
4. As **defense-in-depth**, `_semantic_similarity()` itself raises
   `EmbeddingDisabled` when called with `enabled=false`+`fallback="skip"`.
   This catches any direct caller that bypasses the judge pre-check
   (e.g. the per-bullet grounding loop). `EmbeddingDisabled` is distinct
   from `EmbedderUnavailable` (the latter = backend broken → Jaccard
   fallback; the former = user opted out → skip).

---

## 3. Troubleshooting

### "content_judge: embed backend unavailable … falling back to Jaccard"

The embedder smoke-test failed at load time. Common causes:

1. **Ollama model not pulled** → `ollama pull <model>` (for GGUF backends).
2. **HF model download timed out** → run the app once with internet to
   seed `~/.markitdown_pro/models/`; subsequent runs are offline.
3. **CUDA forward-pass OOM** (MiniLM on some drivers) → switch to
   `BAAI/bge-small-en-v1.5`, or set `"embedding.device": "cpu"`.
4. **sentence-transformers not installed** → `pip install sentence-transformers>=2.7.0`.

The fallback to Jaccard is a real (weaker) signal — coverage still runs.
To silence the recurring warning, either fix the embedder or set
`"embedding.enabled": false` + `"embedding.fallback": "jaccard"` (explicit
opt-out, one INFO log instead of per-call warnings).

### "Phase 2.2 semantic coverage check SKIPPED"

You have `enabled=false` + `fallback="skip"`. This is expected if you
configured it intentionally. The deterministic judge + postchecks still
verify the summary. To restore the semantic signal, set
`"embedding.enabled": true`.

### "OllamaProvider smoke-test FAILED" (V18.4)

The new `OllamaProvider.smoke_test()` (Phase 2, Task 3) probes
`/api/generate` with a 1-token `"hello"` request at startup / preflight.
If it fails:

- **HTTP 404** → `ollama pull <your-summarisation-model>`.
- **Timeout** → Ollama is loading the model (cold start) or stalled.
  Re-run; if persistent, check `ollama ps` and VRAM.
- **ConnectionError** → `ollama serve` is not running.
- **Empty response** → the model loaded but generated nothing (broken
  quant / Modelfile template). This is the V18.2.43 empty-generation
  failure mode — try a different quant.

The smoke-test never raises; it returns `bool` so preflight can branch
cleanly. It does NOT set `presence_penalty` (preserving the V18.2.42
Instruct-mode hard constraint).

---

## 4. Related files

| File | Role |
|------|------|
| `core/llm/embedder_backend.py` | `SentenceTransformerBackend`, `OllamaEmbedBackend`, `EmbedderUnavailable`, both `smoke_test()` implementations, `is_ollama_embed_model()`, `create_embedder()`. |
| `core/llm/model_singletons.py` | `get_embed_model()` lazy singleton (loads + smoke-tests the backend once), `is_embedder_healthy()`, `_resolve_embed_device()`. |
| `core/llm/embedding_cache.py` | On-disk embedding cache (`~/.markitdown_pro/embed_cache/`) — avoids re-embedding the same text across chapters. |
| `core/summarisation/content_judge.py` | `_semantic_similarity()`, `EmbeddingDisabled`, `_embedding_settings()`, `ContentJudge.judge()` Q1 coverage loop, `_check_coverage_batched()`. |
| `core/llm/llm_provider.py` | `OllamaProvider.smoke_test()` (V18.4) — the LLM-side twin of the embedder smoke-test. |
| `utils/settings.py` | `embedding.*` defaults (`enabled`, `fallback`, `model`, `device`, `cache_enabled`, `load_mode`, `threshold_scale`). |
| `utils/settings_schema.py` | `_EmbeddingSchema` Pydantic validator (validates `enabled` is bool, `fallback` ∈ {`jaccard`,`skip`}). |
| `tests/test_embedding_settings.py` | V18.4 tests for the optional-mode knobs + skip/jaccard paths. |
| `tests/test_ollama_provider_smoke.py` | V18.4 tests for `OllamaProvider.smoke_test()`. |
