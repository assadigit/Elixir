# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-25T20:36:38.397204

<!-- generated-by: Elixir v0.4.31 | run_id=20260925-203638-b1687582 -->

---

[20:36:38] [SUCCESS] 🚀 Starting conversion…

[20:36:38] [DEBUG]   🔍 importing 'pypdf'…

[20:36:38] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[20:36:38] [DEBUG]   🔍 importing 'pdf2image'…

[20:36:38] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[20:36:38] [DEBUG]   🔍 importing 'tiktoken'…

[20:36:38] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[20:36:38] [DEBUG]   🔍 importing 'markitdown'…

[20:36:40] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[20:36:40] [DEBUG]   🔍 importing 'rapidfuzz'…

[20:36:40] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[20:36:40] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[20:36:40] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[20:36:40] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[20:36:40] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[20:36:40] [DEBUG]   🔍 importing 'torch'…

[20:36:40] [DEBUG]   ✅ 'torch' ok (0.0s)

[20:36:40] [DEBUG]   🔍 importing 'transformers'…

[20:36:51] [DEBUG]   ✅ 'transformers' ok (11.6s)

[20:36:51] [DEBUG]   🔍 importing 'langextract'…

[20:36:52] [DEBUG]   ✅ 'langextract' ok (0.1s)

[20:36:52] [DEBUG]   ✅ Pre-flight dependency check passed

[20:36:52] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[20:36:52] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[20:36:52] [INFO]   Input path (full): G:\431\Broken Structures Salman Akhtar.pdf

[20:36:52] [INFO]   Output dir: G:\431\Broken Structures Salman Akhtar

[20:36:52] [INFO]   Source type: normal_book

[20:36:52] [INFO]   App version: 0.4.31

[20:36:52] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[20:36:52] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[20:36:52] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[20:36:52] [INFO]   Ollama reachable (localhost:11434): True

[20:36:52] [INFO]   Provider: llamacpp

[20:36:52] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[20:36:52] [INFO]   [Phase 1 (Extraction)]

[20:36:52] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[20:36:52] [INFO]   [Phase 2 (Summarization)]

[20:36:52] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[20:36:52] [INFO]   ────────────────────────────────────────

[20:36:52] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[20:36:52] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[20:36:52] [INFO] ━━━━━━━━━━━━━━━━━━━━

[20:36:52] [INFO]   LLM OCR: True, Force OCR all: False

[20:36:52] [INFO]   Auto-detect scanned: True

[20:36:52] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[20:36:52] [INFO]   OCR retries: 2, Image max size: 1200

[20:36:52] [INFO]   Page range: all

[20:36:52] [INFO]   Selected chapters: 1 chapter(s)

[20:36:52] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[20:36:52] [INFO]   Segmentation: auto, Token limit: 2000

[20:36:52] [INFO]   Semantic: True, Page group: 10

[20:36:52] [INFO]   Generate summaries: True

[20:36:52] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[20:36:52] [INFO]   Fast model: , Heavy model: (disabled)

[20:36:52] [INFO]   Workers (requested): 1, Temperature: 0.7

[20:36:52] [INFO]   Self-consistency: False, Coverage threshold: 85%

[20:36:52] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[20:36:52] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[20:36:52] [INFO]   Academic rigor: False

[20:36:52] [INFO]   Max context tokens: 128000

[20:36:52] [INFO]   Max output tokens: 32768

[20:36:52] [INFO]   Keep-alive: 30m

[20:36:52] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[20:36:52] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[20:36:52] [INFO]   Translation: disabled

[20:36:52] [INFO]   Clean markdown: True, Token saver: True

[20:36:52] [INFO]   Content filter: True

[20:36:52] [INFO]   Extract tables: False, Math: False, Figures: False

[20:36:52] [INFO]   Visual-region crops: True

[20:36:52] [INFO]   Layout analysis: False

[20:36:52] [INFO]   DOCX author: Elixir, TOC: True

[20:36:52] [INFO]   Output paths (V7.5 subfolders):

[20:36:52] [DEBUG]     markdown: G:\431\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[20:36:52] [DEBUG]     summaries: G:\431\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[20:36:52] [DEBUG]     keypoints: G:\431\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[20:36:52] [DEBUG]     packets: G:\431\Broken Structures Salman Akhtar\packets

[20:36:52] [DEBUG]     podcast: G:\431\Broken Structures Salman Akhtar\podcast

[20:36:52] [DEBUG]     logs: G:\431\Broken Structures Salman Akhtar\logs\quality_report.json

[20:36:52] [INFO]   Resume mode: enabled — will skip done chapters

[20:36:52] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[20:36:52] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[20:36:52] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[20:36:52] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[20:36:52] [DEBUG]   💾 Disk space: 89.6 GB free

[20:36:52] [DEBUG]   📋 Checkpoint system initialized → G:\431\Broken Structures Salman Akhtar\.checkpoint.json

[20:37:54] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[20:37:54] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[20:37:54] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[20:37:54] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[20:37:54] [INFO] [TOC] Using PDF outlines: 22 entries.

[20:37:54] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[20:37:54] [DEBUG]   [TOC] Entries passed to segmenter: 22

[20:37:54] [DEBUG]   [TOC] - p.7: Table of Contents

[20:37:54] [DEBUG]   [TOC] - p.9: FOREWORD

[20:37:54] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[20:37:54] [DEBUG]   [TOC] … and 19 more

[20:37:54] [INFO]   🎯 User selected 1 chapter(s):

[20:37:54] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[20:37:55] [INFO]   📸 front_cover → front_cover.jpg

[20:37:55] [INFO]   📸 back_cover → back_cover.jpg

[20:37:55] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[20:37:55] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[20:37:55] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[20:37:56] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[20:37:56] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[20:37:56] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[20:37:56] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[20:37:57] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[20:37:57] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[20:37:57] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[20:37:57] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[20:37:57] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[20:37:58] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[20:37:58] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[20:37:58] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[20:37:58] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[20:37:58] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[20:37:58] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[20:37:59] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[20:37:59] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[20:37:59] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[20:37:59] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[20:37:59] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[20:38:00] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[20:38:00] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[20:38:00] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[20:38:00] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[20:38:00] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[20:38:00] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[20:38:00] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[20:38:00] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[20:38:00] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[20:38:00] [INFO]   ✅ markitdown ready for digital-page extraction

[20:38:00] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[20:38:00] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[20:38:00] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.0s)

[20:38:00] [INFO]      Pages needing OCR: [152, 153, 154]

[20:38:00] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[20:38:00] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[20:38:00] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[20:38:02] [INFO]   📄 140/397 pages processed (35%)

[20:38:07] [INFO]   🔍 OCR  page 152/397 (scanned)…

[20:38:09] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[20:38:09] [WARNING]   ⚠️ V0.4.1 vision OCR p.152 failed: LlamaCppProvider.complete_with_image() got an unexpected keyword argument 'model'

[20:38:12] [INFO]     ✅ Tesseract p.152: 953 chars

[20:38:12] [INFO]   🔍 OCR  page 153/397 (scanned)…

[20:38:13] [WARNING]   ⚠️ V0.4.1 vision OCR p.153 failed: LlamaCppProvider.complete_with_image() got an unexpected keyword argument 'model'

[20:38:15] [INFO]   🔍 OCR  page 154/397 (scanned)…

[20:38:17] [WARNING]   ⚠️ V0.4.1 vision OCR p.154 failed: LlamaCppProvider.complete_with_image() got an unexpected keyword argument 'model'

[20:38:20] [INFO]     ✅ Tesseract p.154: 871 chars

[20:38:22] [INFO]   📄 160/397 pages processed (40%)

[20:38:22] [WARNING]   ⚠️ 1 page(s) failed to extract: [153]

[20:38:23] [SUCCESS] ✅ PDF processing done: 23/397 pages extracted

[20:38:23] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[20:38:23] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[20:38:23] [DEBUG]   🧹 Header/footer removal: 7 chars stripped

[20:38:23] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[20:38:23] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[20:38:23] [INFO] 📝 Raw markdown: 52,964 chars | [104.7s]

[20:38:23] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[20:38:23] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[20:38:23] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[20:38:23] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[20:38:23] [INFO] [Segmenter] Attempting chapter-level segmentation…

[20:38:23] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[20:38:23] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[20:38:23] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[20:38:23] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[20:38:23] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[20:38:23] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[20:38:23] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[20:38:23] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[20:38:23] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[20:38:23] [INFO]   📑 Filtered segments: kept 1 of 17

[20:38:23] [INFO] 📚 1 segment(s) detected | [104.8s]

[20:38:23] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,968 tokens | p.137–160

[20:38:23] [INFO] 🌐 Detected language: en

[20:38:23] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[20:38:23] [INFO] 💾 Full markdown → G:\431\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[20:38:23] [INFO] 📂 1 segment files → G:\431\Broken Structures Salman Akhtar\markdown\chapters

[20:38:23] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[20:38:23] [DEBUG]    [V17.5] Analysis files written to: G:\431\Broken Structures Salman Akhtar\markdown\chapters

[20:38:23] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (4032 bytes)

[20:38:23] [INFO]   ⏱️ Summary phase starting | [105.3s]

[20:38:25] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[20:38:25] [DEBUG]   ⏭️ Skipping page 152 in summarisation: High density of TOC‑like lines

[20:38:25] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[20:38:25] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[20:38:25] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[20:38:25] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[20:38:25] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[20:38:25] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[20:38:25] [INFO]   🌡️ Pre-flight: idle GPU temp = 55°C

[20:38:25] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 55°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[20:38:25] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[20:38:25] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[20:38:25] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[20:38:25] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[20:38:25] [DEBUG]   🎛️ Model profile: Default

[20:38:25] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[20:38:25] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[20:38:25] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[20:38:25] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[20:38:25] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[20:38:25] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[20:38:25] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[20:38:26] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[20:38:26] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[20:38:26] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[20:38:26] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[20:38:26] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[20:38:26] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[20:38:26] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[20:38:26] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[20:38:26] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[20:38:26] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (51893 chars)

[20:38:26] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[20:38:26] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[20:38:26] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[20:38:26] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[20:38:26] [DEBUG]     [V17.5] Searching for analysis files in: G:\431

[20:38:26] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[20:38:26] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[20:38:26] [INFO]     📊 V17.2: Prepended deterministic analysis (3901 chars) — citation recall 78%→100%

[20:38:26] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,276 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,276 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[20:38:26] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[20:38:26] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[20:38:26] [INFO]     📦 V0.4: master-summary architecture (default) — input 11276 tok, output cap 32768

[20:38:26] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[20:38:26] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:38:26] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[20:39:39] [INFO]     ✅ V0.3 Call 1/3: master summary = 759 words, 6018 chars

[20:39:39] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[20:39:39] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:39:39] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[20:40:12] [INFO]     ✅ V0.3 Call 2/3: 34 bullets derived from master summary

[20:40:12] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[20:40:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:40:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[20:40:28] [INFO]     ✅ V0.3 Call 3/3: exec summary = 232 words

[20:40:28] [DEBUG]     📝 Parsed: exec=1875 chars, bullets=34, thorough=6018 chars

[20:40:51] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[20:40:52] [DEBUG]     🔍 Coverage detail: 6/8 keywords found | missing: ['others', 'object relations']

[20:40:52] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee

[20:40:53] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (34 bullets, 232 exec words, 759 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[20:40:54] [DEBUG]     🔍 Fact-check: all 34 bullets verified ✓

[20:40:54] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[20:40:54] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:40:54] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[20:41:45] [INFO]     ✅ Additive sections via followup call: key_distinctions=1770 chars, theoretical_tensions=1524 chars

[20:41:45] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (34 bullets, 232 exec words, 759 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[20:41:45] [WARNING]     ⚠️ thorough_summary too short (759 words < 800 threshold) — requesting dedicated expansion…

[20:41:45] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[20:41:45] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[20:43:05] [INFO]     📖 Attempt 1/3: dedicated thorough = 856 words

[20:43:05] [INFO]     ✅ thorough_summary expanded via dedicated call: 759 → 856 words

[20:43:05] [INFO]     V0.05: Skipping bullet expansion — 34 bullets already meet the source-scaled target (27-40 for a 7274-word chapter; gap-fill will handle missing concepts).

[20:43:05] [INFO]     ✅ Final coverage 92%

[20:43:05] [DEBUG]     📏 F1: exec=232w, thorough=856w (source=7274w; targets exec<=250w, thorough<=3273w)

[20:45:06] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[20:45:07] [DEBUG]     📖 F3: Reading level — source: 16.1, summary: 20.3 (diff: -4.2)

[20:45:07] [INFO]     ℹ️ F3: Summary is 4.2 grade levels denser than source — expected for a compressed academic summary.

[20:45:08] [DEBUG]     📊 I2: Chapter difficulty 0.58/1.0 (grade 16.1, strategy: multi_sample)

[20:45:08] [DEBUG]     🔄 J2: 25 cross-section redundancy(ies) found (exec↔bullets: 5, bullets↔thorough: 19)

[20:45:08] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[20:45:08] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[20:45:08] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[20:45:09] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[20:45:47] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 4032 per-pair calls)

[20:45:47] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[20:45:51] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (34/34 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[20:45:51] [INFO]   ℹ️ Summary has substantial content (exec=1875 chars, thorough=6768 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[20:45:51] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[20:45:51] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[20:45:51] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[20:45:51] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[20:45:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:45:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[20:47:24] [INFO]     📜 Scholar response truncated — one additive continuation retry (V18.20.4.12 / O-a4)

[20:47:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:47:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: Millon (1981) categorized paranoid personality features into…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: Author coverage check for Rycroft (1960) regarding the parad…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: Author coverage check for Cameron (1963) on four aspects inc…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: Author coverage check for Jacobson (1971) on family atmosphe…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: DSM-III criteria specifics: the exact count of items require…

[20:47:54] [DEBUG]     🎓 Dropped gap-fill without quote: Author coverage check for Conlon (1984) and his mnemonic des…

[20:47:54] [DEBUG]     🧹 Filtered 2 thinking + 0 narrative bullets + 0 truncated (kept 21)

[20:47:54] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 2}

[20:47:54] [INFO]     🧩 V18.20.3.4: Filtered 2 thinking/scar bullet(s) from scholar gap-fill before merge

[20:47:54] [INFO]     🧽 V0.4.23: Filler floor dropped 1 citation-adjacency bullet(s) from scholar gap-fill before merge

[20:47:54] [INFO]     🎓 Gap-fill: added 20 new bullet(s) from scholar reflection (source-grounded)

[20:47:54] [INFO]     🎓 Scholar reflection: identified 14 gap(s), filled 20 with new bullets

[20:47:54] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[20:47:54] [INFO]     🛡️ Anti-false-precision: rewrote 'Klein (1946) identified the "paranoid-schizoid position" as …' → 'Klein and Winnicott both identified the "paranoid-schizoid p…' (source groups Klein + Winnicott)

[20:47:54] [INFO]     🛡️ Anti-false-precision: rewrote 1 claim(s) that invented distinctions between authors the source groups together

[20:47:54] [WARNING]   ⏱️⚠️ Deadline exceeded (568s > 480s) — skipping optional phase: semantic dedup

[20:47:54] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[20:47:54] [DEBUG]     🧹 V16.0.2 Bullet normalization: 54 bullets normalized

[20:47:54] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[20:47:54] [WARNING]   ⏱️⚠️ Deadline exceeded (568s > 480s) — skipping optional phase: bullet consolidation

[20:47:54] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[20:47:54] [DEBUG]     [V17.5] Searching for analysis files in: G:\431

[20:47:54] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[20:47:54] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[20:47:54] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Erikson', 'Bursten', 'Wurmser', 'Conlon', 'Morey']/75 authors in bullets (36%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Stanton', 'Thomson', 'Hamilton']

[20:47:54] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Roth', 'Slater', 'Bursten', 'Morey', 'Ovessey', 'Walters']/75 authors in thorough (44%) — MISSING from thorough: ['Akhtar', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[20:47:54] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Stanton', 'Thomson', 'Hamilton']…

[20:47:54] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:47:54] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[20:48:11] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[20:48:11] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne: Co-authored descriptions of the behavioral correlates…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[20:48:11] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne: Described the behavioral correlates of spl…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[20:48:11] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 5/8 bullets

[20:48:11] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (16.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=3, filler=0, added=5

[20:48:11] [DEBUG]     📊 V18.14.1: After round 1, 38 still missing from bullets: ['Kernberg', 'Byrne', 'Akhtar and Byrne', 'Salzman', 'Millon']…

[20:48:11] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Byrne', 'Akhtar and Byrne', 'Salzman', 'Millon']… (mention-only: ['Byrne'])

[20:48:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:48:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[20:48:21] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[20:48:21] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[20:48:21] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (10.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[20:48:21] [DEBUG]     📊 V18.14.1: After round 2, 30 still missing from bullets: ['Slater and Roth', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[20:48:21] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Slater and Roth', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[20:48:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:48:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[20:48:37] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[20:48:37] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[20:48:37] [DEBUG]     📊 V18.14.1: After round 3, 21 still missing from bullets: ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[20:48:37] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[20:48:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:48:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[20:48:53] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited in the source as part of the literature supportin…

[20:48:53] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is referenced alongside other sources to support the dist…

[20:48:53] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is included in the source as …

[20:48:53] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is listed among the key studies c…

[20:48:53] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is mentioned as a r…

[20:48:53] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 3/8 bullets

[20:48:53] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (15.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=5, added=3

[20:48:53] [DEBUG]     📊 V18.14.1: After round 4, 15 still missing from bullets: ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[20:48:53] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[20:48:53] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:48:53] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[20:49:05] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Croewe (1975) is cited as one of the authors whose textbook descriptio…

[20:49:05] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 7/8 bullets

[20:49:05] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (12.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[20:49:05] [DEBUG]     📊 V18.14.1: After round 5, 8 still missing from bullets: ['Croewe', 'Grunberger', 'Rettersol', 'Ovessey', 'Walters']…

[20:49:05] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 30 bullets across 5 round(s)

[20:49:05] [WARNING]     ⚠️ V18.14.1: 8 theorists still missing from bullets after gap-fill: ['Croewe', 'Grunberger', 'Rettersol', 'Ovessey', 'Walters', 'Varghesi', 'Maj sey', 'Munro'] — 8 never covered (round cap/deadline): ['Croewe', 'Grunberger', 'Rettersol', 'Ovessey', 'Walters', 'Varghesi', 'Maj sey', 'Munro']

[20:49:05] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[20:49:05] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (2 item(s) were uncovered; all 6 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (2 item(s) were uncovered; all 9 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[20:49:05] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 27 (sim=0.88 with bullet 25)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 48 (sim=0.97 with bullet 37)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 53 (sim=0.95 with bullet 40)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 71 (sim=0.87 with bullet 28)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 72 (sim=0.85 with bullet 33)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 73 (sim=0.95 with bullet 67)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 78 (sim=0.87 with bullet 74)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 83 (sim=0.86 with bullet 31)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 88 (sim=0.94 with bullet 50)

[20:49:06] [DEBUG]     🧹 Semantic dedup: removing bullet 93 (sim=0.87 with bullet 22)

[20:49:06] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 93 → 83 bullets (removed 10 gap-fill/conclusion duplicates; 1.2s, non-skippable per V18.20.3.4)

[20:49:06] [DEBUG]     [V17.5] Searching for analysis files in: G:\431

[20:49:06] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[20:49:06] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[20:49:09] [INFO]     ℹ️ V0.4.23: 83 bullets ship (guidance floor was 27-40 for a 7274-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[20:49:09] [INFO]     🛡️ V18.2.13 Post-checks: 12 fixed, 26 flagged (of 83 bullets + exec + thorough)

[20:49:09] [DEBUG]       [fragment_merge/flag] bullet[8]: word-fragment merge: 'theme of' — 'them' is a known word but 'theme' is not. The 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …ive literature reinforced the theme of "contradictory pride …

[20:49:09] [DEBUG]       [attribution/flag] bullet[40]: attribution mismatch: summary's claim about 'Bursten (1973a)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Bursten (1973a) proposed that …

[20:49:09] [DEBUG]       [attribution/flag] bullet[65]: attribution mismatch: summary's claim about 'Kohut (1972)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kohut (1972) described narciss…

[20:49:09] [DEBUG]       [attribution/flag] bullet[73]: attribution mismatch: summary's claim about 'Pao (1969)' has 39% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Pao (1969) provided work on mo…

[20:49:09] [DEBUG]       [attribution/flag] bullet[74]: attribution mismatch: summary's claim about 'Socarides (1966)' has 42% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Socarides (1966) offered a vie…

[20:49:09] [DEBUG]       [attribution/flag] bullet[76]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[20:49:09] [DEBUG]       [truncated/flag] bullet[80]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[20:49:09] [DEBUG]       [truncated/flag] bullet[82]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[20:49:09] [DEBUG]       [fragment_merge/flag] exec: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …on, highlighting a consistent theme of contradictory pride a…

[20:49:09] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'theme of' — 'them' is a known word but 'theme' is not. The 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …d Tobak (1989) reinforced the theme of "contradictory pride …

[20:49:09] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'splittingted' is not in the source or English lexicon but ends with source-word 'splitting' + suffix 'ted' (3 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  involving projection and splittingted that early frustration i

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bleuler (1908)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …bsequent contributors include Bleuler (1908), who noted a tr…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …n entitlement and inadequacy; Jaspers (1949), whose "self-in…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Schneider (1950)' has 41% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ty and exaggerated assurance; Schneider (1950), who differen…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Leonhard (1959)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …tric fanatic psychopaths; and Leonhard (1959) and Shepherd (…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Shepherd (1961)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …aths; and Leonhard (1959) and Shepherd (1961), who emphasize…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Polatin (1975)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ial grievances. Later work by Polatin (1975), Hamilton (1974…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Roth (1977)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …lton (1974, 1984), Slater and Roth (1977), Salzman (1974), S…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Millon (1981)' has 40% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …lzman (1974), Stanton (1978), Millon (1981), and Tobak (1989…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Rycroft (1960)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …nd projective identification. Rycroft (1960), Cameron (1963)…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Cameron (1963)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …entification. Rycroft (1960), Cameron (1963), Shapiro (1965)…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Shapiro (1965)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …croft (1960), Cameron (1963), Shapiro (1965), Jacobson (1971…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jacobson (1971)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …meron (1963), Shapiro (1965), Jacobson (1971), Bursten (1973…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bursten (1973a)' has 39% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …piro (1965), Jacobson (1971), Bursten (1973a), Kernberg (197…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Kernberg (1975a)' has 50% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …bson (1971), Bursten (1973a), Kernberg (1975a), and Meissner…

[20:49:09] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Meissner (1978b)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …1973a), Kernberg (1975a), and Meissner (1978b) further elabo…

[20:49:09] [DEBUG]       [quote_verification/fix] bullet[22]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   framework highlights splitting mechanisms and prepares clin

[20:49:09] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   description, highlighting a consistent theme of contradicto

[20:49:09] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and Blum’s concept of the 

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by idiosyncratic thinking, undue sensitivity,

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   or paranoid personality as marked by distrust, irritability

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   described overcompensation for humiliation through masks of

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   noting the coexistence of arrogance with hollow insecurity,

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a developmental substrate involving projection and split

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —an ambivalently loved object whose perceived betrayal must 

[20:49:09] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   framework is presented as a nosologically forward step that

[20:49:09] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid Personality Disorder vs. Delusional Disorder (Par

[20:49:09] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian Homosexual Drive vs. Actual Early Trauma/Aggressi

[20:49:09] [INFO]     ℹ️ V0.4.23: 83 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[20:49:09] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 33/75 authors in thorough — MISSING from thorough: ['Akhtar', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[20:49:09] [WARNING]   ⏱️⚠️ Deadline exceeded (644s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[20:49:09] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 42 of 75 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[20:49:09] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:49:09] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[20:49:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:49:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[20:50:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[20:50:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[20:51:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon and Michels (1962) contributed to the understanding of the c…" — its name(s) never co-occur with the claim's key phrases in the source

[20:51:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Conlon (1973) provided a detailed analysis of the interpersonal dynami…" — its name(s) never co-occur with the claim's key phrases in the source

[20:51:13] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 33/75 → 59/75 (3 chunked call(s), ≤12 names each; 6 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[20:51:13] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[20:51:13] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[20:51:13] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 2 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[20:51:13] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 64/75 in final bullets (missing: ['Fenichel', 'Bergman', 'Jack', 'Reid', 'Croewe']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[20:51:13] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[20:51:13] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 767s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 767s of the budget.

[20:51:13] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[20:51:13] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":85,"exec_chars":1871,"chapter_done":true}

[20:51:13] [DEBUG]   📊 Progress: 1/1 done | 85 bullets | 1,871 chars exec summary

[20:51:13] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via G:\431\Broken Structures Salman Akhtar\checkpoints

[20:51:13] [INFO] 📄 Building DOCX report…

[20:51:13] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[20:51:13] [SUCCESS] ✅ DOCX saved to G:\431\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[20:51:14] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.31_20260925-203638-b1687582_summary.md + DOCX

[20:51:14] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[20:51:14] [INFO]   🧮 Embedding cache: 0 hits / 99 misses (0% hit-rate), 5000 entries

[20:51:14] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.31_20260925-203638-b1687582_summary.md

[20:51:14] [INFO] 📝 1 summaries → G:\431\Broken Structures Salman Akhtar\summaries

[20:51:14] [INFO] 📋 Book summary → G:\431\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[20:51:14] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.31_20260925-203638-b1687582.summary.md

[20:51:14] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[20:51:14] [INFO]   ⏱️ DOCX phase starting | [875.9s]

[20:51:14] [INFO] 📄 Building DOCX report…

[20:51:14] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[20:51:14] [SUCCESS] ✅ DOCX saved to G:\431\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[20:51:16] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[20:51:19] [INFO]   🧹 Keypoints dedup: removed 2 duplicate(s) (85 → 83 keypoints)

[20:51:19] [DEBUG]   🗑️ '**Cameron outlined four aspects of paranoid** — 4 items from...' (embedding sim > 0.85)

[20:51:19] [DEBUG]   🗑️ '**To this composite profile (Table 6-1),** — 6 items from th...' (embedding sim > 0.85)

[20:51:19] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[20:53:22] [INFO]   🎯 K1+Classification: 83 bullets — 13 core, 41 supporting, 29 additional

[20:53:22] [INFO]   📌 Keypoints MD → G:\431\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[20:53:22] [INFO]   📌 Keypoints DOCX → G:\431\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[20:53:22] [SUCCESS] 📌 Keypoints MD  → G:\431\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[20:53:22] [SUCCESS] 📌 Keypoints DOCX → G:\431\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[20:53:22] [INFO]   📊 Citation graph: no citations found in the text.

[20:53:22] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[20:53:22] [SUCCESS] ✅ Conversion complete.

[20:53:33] [INFO]   📊 Quality report → G:\431\Broken Structures Salman Akhtar\logs\quality_report.json

[20:53:33] [INFO] 

[20:53:33] [INFO] ━━━ Thermal Safety Report ━━━

[20:53:33] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[20:53:33] [INFO]   Session duration: 15.1 min

[20:53:33] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[20:53:33] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[20:53:33] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[20:53:33] [INFO] 

[20:53:33] [INFO] ━━━ Elixir v0.4.31 Conversion Diagnostic Summary ━━━

[20:53:33] [INFO]   Book: Broken Structures Salman Akhtar

[20:53:33] [INFO]   Total pages: 397

[20:53:33] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[20:53:33] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[20:53:33] [INFO]   Summaries generated: 1

[20:53:33] [INFO]     Success: 1, Failed: 0, Total bullets: 85

[20:53:33] [INFO]     Coverage: 94%

[20:53:33] [INFO]     Recall floor (deterministic, final set): theorists 64/75 (85%), conclusion items 3/3 (100%)

[20:53:33] [INFO]   Warnings: 0

[20:53:34] [INFO]   Output dir: G:\431\Broken Structures Salman Akhtar

[20:53:34] [INFO]   Log file: G:\431\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.31_20260925-203638-b1687582.conversion.log.md

[20:53:34] [INFO]   Diagnostic JSONL: None

[20:53:34] [INFO]   Summary files (3):

[20:53:34] [INFO]     ✓ G:\431\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.31_20260925-203638-b1687582_summary.md — generated-by v0.4.31 | run_id=20260925-203638-b1687582 | started=2026-09-25T20:38:25 | bullets=85

[20:53:34] [INFO]     ✓ G:\431\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.31 | run_id=20260925-203638-b1687582 | started=2026-09-25T20:38:25 | bullets=85

[20:53:34] [INFO]     ✓ G:\431\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.31_20260925-203638-b1687582.summary.md — generated-by v0.4.31 | run_id=20260925-203638-b1687582 | started=2026-09-25T20:38:25 | bullets=85

[20:53:34] [INFO]   Models loaded at exit: (none — all unloaded)

[20:53:34] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[20:53:34] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[20:53:34] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[20:53:34] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[20:53:34] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[20:53:34] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[20:53:34] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[20:53:34] [INFO]   ✅ Extracted 2 figure(s) → G:\431\Broken Structures Salman Akhtar\images

[20:53:34] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[20:53:39] [INFO]   ✅ Extracted 0 table(s) → G:\431\Broken Structures Salman Akhtar\images

[20:53:44] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[20:53:44] [INFO]   [pipeline] after de-dup: 2 regions

[20:53:45] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → G:\431\Broken Structures Salman Akhtar\regions

[20:53:45] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[20:53:45] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 83 keypoints)


---
Finished at: 2026-09-25T20:53:45.419298
