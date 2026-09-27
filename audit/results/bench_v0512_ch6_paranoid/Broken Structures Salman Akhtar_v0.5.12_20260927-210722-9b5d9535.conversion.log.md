# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T21:07:22.696357

<!-- generated-by: Elixir v0.5.12 | run_id=20260927-210722-9b5d9535 -->

---

[21:07:22] [SUCCESS] 🚀 Starting conversion…

[21:07:22] [DEBUG]   🔍 importing 'pypdf'…

[21:07:22] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[21:07:22] [DEBUG]   🔍 importing 'pdf2image'…

[21:07:22] [DEBUG]   ✅ 'pdf2image' ok (0.1s)

[21:07:22] [DEBUG]   🔍 importing 'tiktoken'…

[21:07:22] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[21:07:22] [DEBUG]   🔍 importing 'markitdown'…

[21:07:29] [DEBUG]   ✅ 'markitdown' ok (6.7s)

[21:07:29] [DEBUG]   🔍 importing 'rapidfuzz'…

[21:07:29] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[21:07:29] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[21:07:29] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[21:07:29] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[21:07:29] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[21:07:29] [DEBUG]   ✅ 'torch' installed

[21:07:29] [DEBUG]   ✅ 'transformers' installed

[21:07:29] [DEBUG]   ✅ 'langextract' installed

[21:07:29] [DEBUG]   ✅ Pre-flight dependency check passed

[21:07:29] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[21:07:29] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[21:07:29] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.12\Broken Structures Salman Akhtar.pdf

[21:07:29] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.12\Broken Structures Salman Akhtar

[21:07:29] [INFO]   Source type: normal_book

[21:07:29] [INFO]   App version: 0.5.12

[21:07:29] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[21:07:29] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[21:07:29] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[21:07:33] [INFO]   Ollama reachable (localhost:11434): False

[21:07:33] [INFO]   Provider: llamacpp

[21:07:33] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[21:07:33] [INFO]   [Phase 1 (Extraction)]

[21:07:33] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:07:33] [INFO]   [Phase 2 (Summarization)]

[21:07:33] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:07:33] [INFO]   ────────────────────────────────────────

[21:07:33] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[21:07:33] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[21:07:33] [INFO] ━━━━━━━━━━━━━━━━━━━━

[21:07:33] [INFO]   LLM OCR: True, Force OCR all: False

[21:07:33] [INFO]   Auto-detect scanned: True

[21:07:33] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:07:33] [INFO]   OCR retries: 2, Image max size: 1200

[21:07:33] [INFO]   Page range: all

[21:07:33] [INFO]   Selected chapters: 1 chapter(s)

[21:07:33] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[21:07:33] [INFO]   Segmentation: auto, Token limit: 2000

[21:07:33] [INFO]   Semantic: True, Page group: 10

[21:07:33] [INFO]   Generate summaries: True

[21:07:33] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:07:33] [INFO]   Fast model: , Heavy model: (disabled)

[21:07:33] [INFO]   Workers (requested): 1, Temperature: 0.7

[21:07:33] [INFO]   Self-consistency: False, Coverage threshold: 95%

[21:07:33] [INFO]   📈 Over-delivery: ENABLED (floor 95% → target 100%)

[21:07:33] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[21:07:33] [INFO]   Academic rigor: False

[21:07:33] [INFO]   Max context tokens: 128000

[21:07:33] [INFO]   Max output tokens: 32768

[21:07:33] [INFO]   Keep-alive: 30m

