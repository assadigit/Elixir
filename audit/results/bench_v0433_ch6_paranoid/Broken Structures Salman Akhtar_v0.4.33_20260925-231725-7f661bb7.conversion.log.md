# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-25T23:17:25.755693

<!-- generated-by: Elixir v0.4.33 | run_id=20260925-231725-7f661bb7 -->

---

[23:17:25] [SUCCESS] 🚀 Starting conversion…

[23:17:25] [DEBUG]   🔍 importing 'pypdf'…

[23:17:25] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[23:17:25] [DEBUG]   🔍 importing 'pdf2image'…

[23:17:25] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[23:17:25] [DEBUG]   🔍 importing 'tiktoken'…

[23:17:25] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[23:17:25] [DEBUG]   🔍 importing 'markitdown'…

[23:17:27] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[23:17:27] [DEBUG]   🔍 importing 'rapidfuzz'…

[23:17:27] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[23:17:27] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[23:17:27] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[23:17:27] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[23:17:27] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[23:17:27] [DEBUG]   🔍 importing 'torch'…

[23:17:27] [DEBUG]   ✅ 'torch' ok (0.0s)

[23:17:27] [DEBUG]   🔍 importing 'transformers'…

[23:17:42] [DEBUG]   ✅ 'transformers' ok (14.5s)

[23:17:42] [DEBUG]   🔍 importing 'langextract'…

[23:17:42] [DEBUG]   ✅ 'langextract' ok (0.1s)

[23:17:42] [DEBUG]   ✅ Pre-flight dependency check passed

[23:17:42] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[23:17:42] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[23:17:42] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar.pdf

[23:17:42] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar

[23:17:42] [INFO]   Source type: normal_book

[23:17:42] [INFO]   App version: 0.4.33

[23:17:42] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[23:17:42] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[23:17:42] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[23:17:42] [INFO]   Ollama reachable (localhost:11434): True

[23:17:42] [INFO]   Provider: llamacpp

[23:17:42] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[23:17:42] [INFO]   [Phase 1 (Extraction)]

[23:17:42] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[23:17:42] [INFO]   [Phase 2 (Summarization)]

[23:17:42] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[23:17:42] [INFO]   ────────────────────────────────────────

[23:17:42] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[23:17:42] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[23:17:42] [INFO] ━━━━━━━━━━━━━━━━━━━━

[23:17:42] [INFO]   LLM OCR: True, Force OCR all: False

[23:17:42] [INFO]   Auto-detect scanned: True

[23:17:42] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:17:42] [INFO]   OCR retries: 2, Image max size: 1200

[23:17:42] [INFO]   Page range: all

[23:17:42] [INFO]   Selected chapters: 1 chapter(s)

[23:17:42] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[23:17:42] [INFO]   Segmentation: auto, Token limit: 2000

[23:17:42] [INFO]   Semantic: True, Page group: 10

[23:17:42] [INFO]   Generate summaries: True

[23:17:42] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:17:42] [INFO]   Fast model: , Heavy model: (disabled)

[23:17:42] [INFO]   Workers (requested): 1, Temperature: 0.7

[23:17:42] [INFO]   Self-consistency: False, Coverage threshold: 85%

[23:17:42] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[23:17:42] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[23:17:42] [INFO]   Academic rigor: False

[23:17:42] [INFO]   Max context tokens: 128000

[23:17:42] [INFO]   Max output tokens: 32768

[23:17:42] [INFO]   Keep-alive: 30m

[23:17:42] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[23:17:42] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[23:17:42] [INFO]   Translation: disabled

[23:17:42] [INFO]   Clean markdown: True, Token saver: True

[23:17:42] [INFO]   Content filter: True

[23:17:42] [INFO]   Extract tables: False, Math: False, Figures: False

[23:17:42] [INFO]   Visual-region crops: True

[23:17:42] [INFO]   Layout analysis: False

[23:17:42] [INFO]   DOCX author: Elixir, TOC: True

[23:17:42] [INFO]   Output paths (V7.5 subfolders):

[23:17:42] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[23:17:42] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[23:17:42] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[23:17:42] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\packets

[23:17:42] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\podcast

[23:17:42] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\logs\quality_report.json

[23:17:42] [INFO]   Resume mode: enabled — will skip done chapters

[23:17:42] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[23:17:42] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:17:42] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[23:17:42] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[23:17:42] [DEBUG]   💾 Disk space: 16.1 GB free

[23:17:42] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\.checkpoint.json

[23:18:47] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[23:18:47] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[23:18:47] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[23:18:47] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[23:18:47] [INFO] [TOC] Using PDF outlines: 22 entries.

[23:18:47] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[23:18:47] [DEBUG]   [TOC] Entries passed to segmenter: 22

[23:18:47] [DEBUG]   [TOC] - p.7: Table of Contents

[23:18:47] [DEBUG]   [TOC] - p.9: FOREWORD

[23:18:47] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[23:18:47] [DEBUG]   [TOC] … and 19 more

[23:18:47] [INFO]   🎯 User selected 1 chapter(s):

[23:18:47] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[23:18:47] [INFO]   📸 front_cover → front_cover.jpg

[23:18:47] [INFO]   📸 back_cover → back_cover.jpg

[23:18:47] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:18:47] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[23:18:47] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[23:18:48] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[23:18:48] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[23:18:48] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[23:18:48] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[23:18:48] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[23:18:49] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[23:18:49] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[23:18:49] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[23:18:49] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[23:18:49] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[23:18:50] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[23:18:50] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[23:18:50] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[23:18:50] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[23:18:50] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[23:18:50] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[23:18:51] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[23:18:51] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[23:18:51] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[23:18:51] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[23:18:52] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[23:18:52] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[23:18:52] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[23:18:52] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:18:52] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[23:18:52] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[23:18:52] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[23:18:52] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[23:18:52] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[23:18:52] [INFO]   ✅ markitdown ready for digital-page extraction

[23:18:52] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[23:18:52] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[23:18:52] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[23:18:52] [INFO]      Pages needing OCR: [152, 153, 154]

[23:18:52] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[23:18:52] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[23:18:52] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[23:18:54] [INFO]   📄 140/397 pages processed (35%)

[23:19:00] [INFO]   🔍 OCR  page 152/397 (scanned)…

[23:19:02] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[23:20:28] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[23:20:28] [INFO]   🔍 OCR  page 153/397 (scanned)…

[23:21:50] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[23:21:50] [INFO]   🔍 OCR  page 154/397 (scanned)…

[23:23:25] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[23:23:28] [INFO]   📄 160/397 pages processed (40%)

[23:23:28] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[23:23:29] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[23:23:29] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[23:23:29] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[23:23:29] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[23:23:29] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[23:23:29] [INFO] 📝 Raw markdown: 53,157 chars | [363.3s]

[23:23:29] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[23:23:29] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[23:23:29] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[23:23:29] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[23:23:29] [INFO] [Segmenter] Attempting chapter-level segmentation…

[23:23:29] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:23:29] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[23:23:29] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[23:23:29] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[23:23:29] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[23:23:29] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[23:23:29] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[23:23:29] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[23:23:29] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:23:29] [INFO]   📑 Filtered segments: kept 1 of 17

[23:23:29] [INFO] 📚 1 segment(s) detected | [363.4s]

[23:23:29] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[23:23:29] [INFO] 🌐 Detected language: en

[23:23:29] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[23:23:29] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[23:23:29] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\markdown\chapters

[23:23:29] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[23:23:29] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\markdown\chapters

[23:23:29] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[23:23:29] [INFO]   ⏱️ Summary phase starting | [363.8s]

[23:23:31] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[23:23:31] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[23:23:31] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[23:23:31] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[23:23:31] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[23:23:31] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[23:23:31] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[23:23:31] [INFO]   🌡️ Pre-flight: idle GPU temp = 60°C

[23:23:31] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 60°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[23:23:31] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:23:31] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[23:23:31] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[23:23:31] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[23:23:31] [DEBUG]   🎛️ Model profile: Default

[23:23:31] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[23:23:31] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[23:23:31] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[23:23:31] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[23:23:31] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[23:23:31] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[23:23:31] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[23:23:31] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[23:23:31] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[23:23:31] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[23:23:31] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[23:23:31] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[23:23:31] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[23:23:31] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[23:23:31] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[23:23:31] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[23:23:31] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[23:23:31] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:23:31] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[23:23:31] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[23:23:31] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[23:23:32] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433new

[23:23:32] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:23:32] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:23:32] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[23:23:32] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[23:23:32] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:23:32] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[23:23:32] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[23:23:32] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[23:23:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:23:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[23:25:23] [INFO]     ✅ V0.3 Call 1/3: master summary = 722 words, 5485 chars

[23:25:23] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[23:25:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:25:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[23:26:19] [INFO]     ✅ V0.3 Call 2/3: 31 bullets derived from master summary

[23:26:19] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[23:26:19] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:26:19] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[23:26:44] [INFO]     ✅ V0.3 Call 3/3: exec summary = 193 words

[23:26:44] [DEBUG]     📝 Parsed: exec=1545 chars, bullets=31, thorough=5485 chars

[23:27:10] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[23:27:12] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['disorders']

[23:27:12] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 30)

[23:27:12] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}

[23:27:12] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (30 bullets, 193 exec words, 722 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:27:15] [DEBUG]     🔍 Fact-check: all 30 bullets verified ✓

[23:27:15] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[23:27:15] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:27:15] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[23:28:24] [INFO]     ✅ Additive sections via followup call: key_distinctions=1667 chars, theoretical_tensions=1379 chars

[23:28:24] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (30 bullets, 193 exec words, 722 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:28:24] [WARNING]     ⚠️ thorough_summary too short (722 words < 800 threshold) — requesting dedicated expansion…

[23:28:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[23:28:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[23:30:11] [INFO]     📖 Attempt 1/3: dedicated thorough = 757 words

[23:30:11] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[23:30:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[23:30:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[23:31:08] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying at temperature 0.0 (greedy)

[23:31:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.00) via llm_provider.llamacpp…

[23:31:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.00 max=8192 streaming…

[23:31:56] [WARNING]     ℹ️ All 3 thorough attempts returned < 800 words (best=757) — keeping best-effort result

[23:31:56] [INFO]     ✅ thorough_summary expanded via dedicated call: 722 → 757 words

[23:31:56] [INFO]     V0.05: Skipping bullet expansion — 30 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[23:31:56] [INFO]     ✅ Final coverage 100%

[23:31:56] [DEBUG]     📏 F1: exec=193w, thorough=757w (source=7405w; targets exec<=250w, thorough<=3332w)

[23:33:34] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[23:33:34] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 19.0 (diff: -2.7)

[23:33:34] [INFO]     ℹ️ F3: Summary is 2.7 grade levels denser than source — expected for a compressed academic summary.

[23:33:35] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[23:33:35] [DEBUG]     🔄 J2: 21 cross-section redundancy(ies) found (exec↔bullets: 2, bullets↔thorough: 19)

[23:33:35] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 2 markers)

[23:33:35] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[23:33:35] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[23:33:35] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[23:33:49] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3584 per-pair calls)

[23:33:49] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[23:33:51] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (30/30 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[23:33:51] [INFO]   ℹ️ Summary has substantial content (exec=1545 chars, thorough=5753 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[23:33:51] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[23:33:51] [WARNING]   ⏱️⚠️ Deadline exceeded (619s > 480s) — skipping optional phase: scholar reflection

[23:33:51] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[23:33:51] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[23:33:51] [WARNING]   ⏱️⚠️ Deadline exceeded (620s > 480s) — skipping optional phase: semantic dedup

[23:33:51] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[23:33:51] [DEBUG]     🧹 V16.0.2 Bullet normalization: 30 bullets normalized

[23:33:51] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[23:33:51] [WARNING]   ⏱️⚠️ Deadline exceeded (620s > 480s) — skipping optional phase: bullet consolidation

[23:33:51] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[23:33:51] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433new

[23:33:51] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:33:51] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:33:51] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Polatin', 'Klein', 'Winnicott', 'Bach', 'Erikson', 'Bursten']/74 authors in bullets (30%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Thomson', 'Frances', 'Byrne']

[23:33:51] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Leonhard', 'Polatin', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Morey']/74 authors in thorough (31%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Frances', 'Byrne']

[23:33:51] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Thomson', 'Frances', 'Byrne']…

[23:33:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:33:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:34:06] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne: Provided descriptions of the behavioral correlates of…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[23:34:06] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne: Described the behavioral correlates of spl…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[23:34:06] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 6/8 bullets

[23:34:06] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[23:34:06] [DEBUG]     📊 V18.14.1: After round 1, 41 still missing from bullets: ['Jacobson', 'Volkan', 'Winokur', 'Kendler', 'Leonhard']…

[23:34:06] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Jacobson', 'Volkan', 'Winokur', 'Kendler', 'Leonhard']…

[23:34:06] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:34:06] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:34:17] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1985) contributed to the literature on paranoid disorders, th…

[23:34:17] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[23:34:17] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (11.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[23:34:17] [DEBUG]     📊 V18.14.1: After round 2, 31 still missing from bullets: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Fenichel']…

[23:34:17] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Fenichel']…

[23:34:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:34:17] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:34:31] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur’s (1975) work with Croewe is cited as an example of textbook d…

[23:34:31] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler’s (1975) theory of separation-individuation is referenced to ex…

[23:34:31] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is listed amon…

[23:34:31] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited as part of th…

[23:34:31] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 4/8 bullets

[23:34:31] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (13.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[23:34:31] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[23:34:31] [DEBUG]     📊 V18.14.1: After round 3, 27 still missing from bullets: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Ndtei']…

[23:34:31] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Ndtei']… (mention-only: ['Winokur'])

[23:34:31] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:34:31] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1985) is cited as an example of literature that focused on pa…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited among other r…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is referenced alongside other sources to support the diff…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is cited as one of several re…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is mentioned as a relevant contri…

[23:34:46] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is included in a li…

[23:34:46] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 2/8 bullets

[23:34:46] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (15.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=6, added=2

[23:34:46] [INFO]     🔁 V18.20.3.7: 'Kohut' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[23:34:46] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Winokur' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[23:34:46] [DEBUG]     📊 V18.14.1: After round 4, 25 still missing from bullets: ['Winokur', 'Kohut', 'Ndtei', 'Green', 'Pao']…

[23:34:46] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Kohut', 'Ndtei', 'Green', 'Pao', 'Socarides']… (mention-only: ['Kohut'])

[23:34:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:34:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:35:03] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne (1983) described the behavioral correlates …' (source attributes this claim to 'Socarides’s', not 'Byrne')

[23:35:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green (1986) authored an essay on moral narcissism, which Akhtar and B…

[23:35:03] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[23:35:03] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (16.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=6

[23:35:03] [INFO]     🔁 V18.20.3.7: 'Green' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[23:35:03] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Kohut' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[23:35:03] [DEBUG]     📊 V18.14.1: After round 5, 16 still missing from bullets: ['Winokur', 'Kohut', 'Green', 'Wurmser', 'Conlon']…

[23:35:03] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 25 bullets across 5 round(s)

[23:35:03] [WARNING]     ⚠️ V18.14.1: 16 theorists still missing from bullets after gap-fill: ['Winokur', 'Kohut', 'Green', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Croewe'] — of these, 2 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Winokur', 'Kohut'] — 14 never covered (round cap/deadline): ['Green', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Croewe', 'Grunberger', 'Rettersol']

[23:35:03] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[23:35:03] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (3 item(s) were uncovered; all 9 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[23:35:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[23:35:03] [DEBUG]     🧹 Semantic dedup: removing bullet 24 (sim=0.89 with bullet 23)

[23:35:03] [DEBUG]     🧹 Semantic dedup: removing bullet 35 (sim=0.94 with bullet 33)

[23:35:03] [DEBUG]     🧹 Semantic dedup: removing bullet 47 (sim=0.87 with bullet 46)

[23:35:03] [DEBUG]     🧹 Semantic dedup: removing bullet 50 (sim=0.93 with bullet 46)

[23:35:03] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 63 → 59 bullets (removed 4 gap-fill/conclusion duplicates; 0.7s, non-skippable per V18.20.3.4)

[23:35:03] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433new

[23:35:03] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:35:03] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:35:06] [INFO]     ℹ️ V0.4.23: 59 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[23:35:06] [INFO]     🛡️ V18.2.13 Post-checks: 3 fixed, 15 flagged (of 59 bullets + exec + thorough)

[23:35:06] [DEBUG]       [fragment_merge/flag] bullet[6]: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  A central theme in PPD is the presence o…

[23:35:06] [DEBUG]       [space/fix] bullet[32]: split 'review' -> 're view' (source-validated)  |  Frances: Co-authored a 1985 review with Widiger that paid …

[23:35:06] [DEBUG]       [attribution/flag] bullet[47]: attribution mismatch: summary's claim about 'Akhtar (1984)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …h Akhtar and Byrne (1983) and Akhtar (1984) included in thei…

[23:35:06] [DEBUG]       [attribution/flag] bullet[51]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[23:35:06] [DEBUG]       [truncated/flag] bullet[55]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[23:35:06] [DEBUG]       [truncated/flag] bullet[57]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[23:35:06] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  … and coping styles. A central theme in the descriptive liter…

[23:35:06] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'models' — 'mode' is a known word but 'models' is not. The trailing 'ls' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …gh projection to more complex models. The author highlights …

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bleuler (1908)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ibutors refined this picture: Bleuler (1908) identified a tr…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …d an attitude of entitlement; Jaspers (1949) described “self…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Schneider (1950)' has 50% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …on to mask inner humiliation; Schneider (1950) differentiate…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Polatin (1975)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ll. The chapter further cites Polatin’s (1975) observation t…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Klein (1946)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …arly threats to survival, and Klein’s (1946) “paranoid-schiz…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Winnicott (1952)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …esponse to inborn aggression. Winnicott (1952) shifted focus…

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Shapiro (1965)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …tudes and sexual inferiority; Shapiro (1965), who described …

[23:35:06] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Hamilton (1974)' has 50% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …encing Schneider’s (1958) and Hamilton’s (1974) distinction …

[23:35:06] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[23:35:06] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Descriptive psychiatry vs. psychoanalytic literature: The 

[23:35:06] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 23/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Frances', 'Byrne']

[23:35:06] [WARNING]   ⏱️⚠️ Deadline exceeded (694s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[23:35:06] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 51 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[23:35:06] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:35:06] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Building upon the earlier psychoanalytic formulations, Volkan (1986) e…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This perspective complements the structural models discussed previousl…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jacobson noted that severe early frustrations prevented the building u…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "These developmental insights are further supported by Salzman (1974), …" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Similarly, Stanton (1978) pointed out the paranoid individual’s overt …" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The contemporary synthesis of these contributions is further refined b…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Furthermore, Akhtar (1984) contributed to the understanding of identit…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:46] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "More recently, Frances et al.…" — its name(s) never co-occur with the claim's key phrases in the source

[23:35:55] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:35:55] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:36:54] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:36:55] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi (1984) contributed to the discussion of paranoid personality by…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack (1975) highlighted the cognitive distortions inherent in the para…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei (1986) examined the developmental origins of paranoid tendencies…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater (1977), in collaboration with Roth, elaborated on the contradic…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Roth (1968) provided a foundational perspective on the defensive struc…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green (1983) explored the moral dimensions of paranoia, proposing that…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1969) focused on the role of jealousy in paranoid pathology, desc…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Socarides (1970) examined the emotional underpinnings of paranoid ange…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler (1987) critically evaluated the diagnostic criteria…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Frances and Widiger (1986) further refined these discussions by advoca…" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:38] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stone (1975) provided additional insights into the cognitive style of …" — its name(s) never co-occur with the claim's key phrases in the source

[23:37:51] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 23/74 → 37/74 (3 chunked call(s), ≤12 names each; 15 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[23:37:51] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 57/74 in final bullets (missing: ['Winokur', 'Kohut', 'Jack', 'Ndtei', 'Green']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[23:37:51] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[23:37:51] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 860s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 860s of the budget.

[23:37:51] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[23:37:51] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":59,"exec_chars":1545,"chapter_done":true}

[23:37:51] [DEBUG]   📊 Progress: 1/1 done | 59 bullets | 1,545 chars exec summary

[23:37:51] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\checkpoints

[23:37:51] [INFO] 📄 Building DOCX report…

[23:37:51] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[23:37:51] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[23:37:51] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.33_20260925-231725-7f661bb7_summary.md + DOCX

[23:37:51] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[23:37:51] [INFO]   🧮 Embedding cache: 63 hits / 32 misses (66% hit-rate), 5000 entries

[23:37:51] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.33_20260925-231725-7f661bb7_summary.md

[23:37:51] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries

[23:37:51] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[23:37:51] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.33_20260925-231725-7f661bb7.summary.md

[23:37:51] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[23:37:51] [INFO]   ⏱️ DOCX phase starting | [1226.1s]

[23:37:51] [INFO] 📄 Building DOCX report…

[23:37:51] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[23:37:52] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[23:37:53] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[23:37:55] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[23:39:19] [INFO]   🎯 K1+Classification: 59 bullets — 10 core, 24 supporting, 25 additional

[23:39:19] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[23:39:19] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[23:39:19] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[23:39:19] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[23:39:19] [INFO]   📊 Citation graph: no citations found in the text.

[23:39:19] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[23:39:19] [SUCCESS] ✅ Conversion complete.

[23:39:35] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\logs\quality_report.json

[23:39:35] [INFO] 

[23:39:35] [INFO] ━━━ Thermal Safety Report ━━━

[23:39:35] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:39:35] [INFO]   Session duration: 16.1 min

[23:39:35] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[23:39:35] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[23:39:35] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:39:35] [INFO] 

[23:39:35] [INFO] ━━━ Elixir v0.4.33 Conversion Diagnostic Summary ━━━

[23:39:35] [INFO]   Book: Broken Structures Salman Akhtar

[23:39:35] [INFO]   Total pages: 397

[23:39:35] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[23:39:35] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[23:39:35] [INFO]   Summaries generated: 1

[23:39:35] [INFO]     Success: 1, Failed: 0, Total bullets: 59

[23:39:35] [INFO]     Coverage: 100%

[23:39:35] [INFO]     Recall floor (deterministic, final set): theorists 57/74 (77%), conclusion items 3/3 (100%)

[23:39:35] [INFO]   Warnings: 0

[23:39:35] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar

[23:39:35] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.33_20260925-231725-7f661bb7.conversion.log.md

[23:39:35] [INFO]   Diagnostic JSONL: None

[23:39:35] [INFO]   Summary files (3):

[23:39:35] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.33_20260925-231725-7f661bb7_summary.md — generated-by v0.4.33 | run_id=20260925-231725-7f661bb7 | started=2026-09-25T23:23:31 | bullets=59

[23:39:35] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.33 | run_id=20260925-231725-7f661bb7 | started=2026-09-25T23:23:31 | bullets=59

[23:39:35] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.33_20260925-231725-7f661bb7.summary.md — generated-by v0.4.33 | run_id=20260925-231725-7f661bb7 | started=2026-09-25T23:23:31 | bullets=59

[23:39:35] [INFO]   Models loaded at exit: (none — all unloaded)

[23:39:35] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:39:35] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[23:39:35] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[23:39:35] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:39:35] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[23:39:35] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[23:39:35] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[23:39:35] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\images

[23:39:35] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[23:39:41] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\images

[23:39:47] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[23:39:47] [INFO]   [pipeline] after de-dup: 2 regions

[23:39:47] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\433new\Broken Structures Salman Akhtar\regions

[23:39:47] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[23:39:47] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 59 keypoints)


---
Finished at: 2026-09-25T23:39:47.926233
