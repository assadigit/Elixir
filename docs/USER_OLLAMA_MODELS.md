# User Ollama Models Reference

This document lists the Ollama models referenced by Elixir's default
settings. It exists so users (and the V13.45.4 regression test) can verify the
exact model-name strings the app expects.

All four models below are pulled from `utils/settings.py` defaults. They are
**defaults only** — every one can be overridden in `~/.elixir/settings.json`
or via the UI's model-selection fields. The app is model-agnostic: any Ollama-
served model with a matching name will be used.

> **Note on quantization / naming.** Ollama model tags encode author + quant
> (e.g. `…-Q4_K_L-bartowski-allenai:latest`). These exact strings must match
> what `ollama list` shows on your machine. If you pull a different quant,
> update the setting to the new tag.

---

## 1. Summarization model — `gemma4-12b:latest`

- **Setting key:** `summarisation.model`
- **Default since:** V13.45.4 (replaced an incorrect Qwythos variant)
- **Role:** Primary chapter-summarization model. Produces the five XML sections
  (`executive_summary`, `bullet_points`, `thorough_summary`, `key_distinctions`,
  `theoretical_tensions`).
- **Sampling profile (auto-applied):** `temperature: 1.0`, `top_p: 0.95`,
  `top_k: 64` — Gemma's recommended creative-sampling range.
- **Context:** 32 768 tokens (`summarisation.max_context_tokens`); adaptive
  reduction available for short chapters on 12 GB cards.
- **Output cap:** 16 000 tokens (`summarisation.max_output_tokens`, V13.45.4).

## 2. Alternative summarization model — `Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest`

- **Setting key:** appears in `summarisation.model_profiles` (temperature override)
- **Role:** A 9 B-parameter Qwen3-derived instruct model (empero-v3 tune) used
  as an alternative summarization backend. Lower temperature than Gemma.
- **Sampling profile (auto-applied):** `temperature: 0.6`.
- **Related:** the *fast* path (`summarisation.fast_model`) defaults to the
  non-`-empero-v3` tag `Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M:latest`.

## 3. Translation model — `translategemma-12b-it.Q4_K_M_mradermacher:latest`

- **Setting key:** `translation.model`
- **Role:** TranslateGemma 12B (instruction-tuned, Q4_K_M, mradermacher quant)
  for chapter translation. Used by `core/translation/` when `translation.enabled`
  is true and `provider == "ollama"`.
- **Default since:** the translation backend was migrated from NLLB to
  TranslateGemma (Ollama) — see the deprecation notice on
  `core/translation/nllb_translator.py`.

## 4. OCR model — `OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest`

- **Setting keys:** `ocr.primary_model` and `ocr.fallback_model`
- **Role:** AllenAI's OlmOCR-2-7B (1025 checkpoint, Q4_K_L, bartowski quant)
  for page-level OCR of scanned PDFs and figure text extraction.
- **Fallback chain:** `primary_model` → `fallback_model` → (if set)
  `ocr.vlm_fallback_model` (a local VLM such as `llava:13b`).
- **Related:** `advanced.vision_model_for_figures` defaults to the short tag
  `OlmOCR-2-7B:latest` for figure-captioning (a lighter alias users may pull).

---

## Installing the models

```bash
ollama pull gemma4-12b:latest
ollama pull Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M-empero-v3:latest
ollama pull translategemma-12b-it.Q4_K_M_mradermacher:latest
ollama pull OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest
```

If a tag is unavailable, pull the closest available quant and update the
matching key in `~/.elixir/settings.json` (or the UI). The app reads
model names verbatim — no normalization is performed.

## Why these defaults?

The defaults reflect Key Decisions recorded in the audit handout:
- **IQ2_XXS for speed (≈19 min) vs IQ2_M for stability (≈79 min)** — the
  default tags above are the stable Q4 family; switch to an `IQ2_XXS` Qwen3
  tag for fast batch runs.
- **Temperature 0.7 for Qwen3 Instruct** (auto-applied via `model_profiles`
  for Qwen3-family tags; Gemma keeps 1.0).
- **`presence_penalty` must be 0** — never override this for summarization.
- **`keep_alive: "30m"`** — models stay resident 30 min after the last request
  to avoid cold reloads between chapters.
