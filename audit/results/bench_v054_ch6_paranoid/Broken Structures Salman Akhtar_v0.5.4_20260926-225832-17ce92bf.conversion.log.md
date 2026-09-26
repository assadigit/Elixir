# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T22:58:32.148260

<!-- generated-by: Elixir v0.5.4 | run_id=20260926-225832-17ce92bf -->

---

[22:58:32] [SUCCESS] 🚀 Starting conversion…

[22:58:32] [DEBUG]   🔍 importing 'pypdf'…

[22:58:32] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[22:58:32] [DEBUG]   🔍 importing 'pdf2image'…

[22:58:32] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[22:58:32] [DEBUG]   🔍 importing 'tiktoken'…

[22:58:32] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[22:58:32] [DEBUG]   🔍 importing 'markitdown'…

[22:58:34] [DEBUG]   ✅ 'markitdown' ok (2.3s)

[22:58:34] [DEBUG]   🔍 importing 'rapidfuzz'…

[22:58:34] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[22:58:34] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[22:58:34] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[22:58:34] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[22:58:34] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[22:58:34] [DEBUG]   ✅ 'torch' installed

[22:58:34] [DEBUG]   ✅ 'transformers' installed

[22:58:34] [DEBUG]   ✅ 'langextract' installed

[22:58:34] [DEBUG]   ✅ Pre-flight dependency check passed

[22:58:34] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[22:58:34] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[22:58:34] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar.pdf

[22:58:34] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar

[22:58:34] [INFO]   Source type: normal_book

[22:58:34] [INFO]   App version: 0.5.4

[22:58:34] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[22:58:34] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[22:58:34] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[22:58:34] [INFO]   Ollama reachable (localhost:11434): True

[22:58:34] [INFO]   Provider: llamacpp

[22:58:34] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[22:58:34] [INFO]   [Phase 1 (Extraction)]

[22:58:34] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:58:34] [INFO]   [Phase 2 (Summarization)]

[22:58:34] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:58:34] [INFO]   ────────────────────────────────────────

[22:58:34] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[22:58:34] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[22:58:34] [INFO] ━━━━━━━━━━━━━━━━━━━━

[22:58:34] [INFO]   LLM OCR: True, Force OCR all: False

[22:58:34] [INFO]   Auto-detect scanned: True

[22:58:34] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:58:34] [INFO]   OCR retries: 2, Image max size: 1200

[22:58:34] [INFO]   Page range: all

[22:58:34] [INFO]   Selected chapters: 1 chapter(s)

[22:58:34] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[22:58:34] [INFO]   Segmentation: auto, Token limit: 2000

[22:58:34] [INFO]   Semantic: True, Page group: 10

[22:58:34] [INFO]   Generate summaries: True

[22:58:34] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:58:34] [INFO]   Fast model: , Heavy model: (disabled)

[22:58:34] [INFO]   Workers (requested): 1, Temperature: 0.7

[22:58:34] [INFO]   Self-consistency: False, Coverage threshold: 98%

[22:58:34] [INFO]   📈 Over-delivery: ENABLED (floor 98% → target 100%)

[22:58:34] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[22:58:34] [INFO]   Academic rigor: False

[22:58:34] [INFO]   Max context tokens: 128000

[22:58:34] [INFO]   Max output tokens: 32768

[22:58:34] [INFO]   Keep-alive: 30m

[22:58:34] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[22:58:34] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[22:58:34] [INFO]   Translation: disabled

[22:58:34] [INFO]   Clean markdown: True, Token saver: True

[22:58:34] [INFO]   Content filter: True

[22:58:34] [INFO]   Extract tables: False, Math: False, Figures: False

[22:58:34] [INFO]   Visual-region crops: True

[22:58:34] [INFO]   Layout analysis: False

[22:58:34] [INFO]   DOCX author: Elixir, TOC: True

[22:58:34] [INFO]   Output paths (V7.5 subfolders):

[22:58:34] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[22:58:34] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:58:34] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[22:58:34] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\packets

[22:58:34] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\podcast

[22:58:34] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\logs\quality_report.json

[22:58:34] [INFO]   Resume mode: enabled — will skip done chapters

[22:58:34] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[22:58:34] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:58:34] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[22:58:34] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[22:58:34] [DEBUG]   💾 Disk space: 23.0 GB free

[22:58:34] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\.checkpoint.json

[22:59:39] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[22:59:39] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:59:39] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:59:39] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[22:59:39] [INFO] [TOC] Using PDF outlines: 22 entries.

[22:59:39] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[22:59:39] [DEBUG]   [TOC] Entries passed to segmenter: 22

[22:59:39] [DEBUG]   [TOC] - p.7: Table of Contents

[22:59:39] [DEBUG]   [TOC] - p.9: FOREWORD

[22:59:39] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[22:59:39] [DEBUG]   [TOC] … and 19 more

[22:59:39] [INFO]   🎯 User selected 1 chapter(s):

[22:59:39] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[22:59:40] [INFO]   📸 front_cover → front_cover.jpg

[22:59:40] [INFO]   📸 back_cover → back_cover.jpg

[22:59:40] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:59:40] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[22:59:40] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[22:59:40] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[22:59:41] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[22:59:41] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[22:59:41] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[22:59:41] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[22:59:41] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[22:59:42] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[22:59:42] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[22:59:42] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[22:59:42] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[22:59:42] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[22:59:42] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[22:59:42] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[22:59:43] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[22:59:43] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[22:59:43] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[22:59:43] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[22:59:44] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[22:59:44] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[22:59:44] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[22:59:44] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[22:59:44] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[22:59:44] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[22:59:44] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:59:44] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[22:59:44] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[22:59:44] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[22:59:44] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[22:59:44] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[22:59:45] [INFO]   ✅ markitdown ready for digital-page extraction

[22:59:45] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[22:59:45] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[22:59:45] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[22:59:45] [INFO]      Pages needing OCR: [152, 153, 154]

[22:59:45] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[22:59:45] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[22:59:45] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[22:59:47] [INFO]   📄 140/397 pages processed (35%)

[22:59:52] [INFO]   🔍 OCR  page 152/397 (scanned)…

[22:59:54] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[23:00:26] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[23:00:26] [INFO]   🔍 OCR  page 153/397 (scanned)…

[23:00:52] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[23:00:52] [INFO]   🔍 OCR  page 154/397 (scanned)…

[23:01:26] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[23:01:29] [INFO]   📄 160/397 pages processed (40%)

[23:01:29] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[23:01:29] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[23:01:29] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[23:01:29] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[23:01:29] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[23:01:29] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[23:01:29] [INFO] 📝 Raw markdown: 53,157 chars | [177.4s]

[23:01:29] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[23:01:29] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[23:01:29] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[23:01:29] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[23:01:29] [INFO] [Segmenter] Attempting chapter-level segmentation…

[23:01:29] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:01:29] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[23:01:29] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[23:01:29] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[23:01:29] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[23:01:29] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[23:01:29] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[23:01:29] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[23:01:29] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:01:29] [INFO]   📑 Filtered segments: kept 1 of 17

[23:01:29] [INFO] 📚 1 segment(s) detected | [177.5s]

[23:01:29] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[23:01:29] [INFO] 🌐 Detected language: en

[23:01:29] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[23:01:29] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[23:01:29] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\markdown\chapters

[23:01:29] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[23:01:29] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\markdown\chapters

[23:01:29] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[23:01:29] [INFO]   ⏱️ Summary phase starting | [177.8s]

[23:01:31] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[23:01:31] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[23:01:31] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[23:01:32] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[23:01:32] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[23:01:32] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[23:01:32] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[23:01:32] [INFO]   🌡️ Pre-flight: idle GPU temp = 63°C

[23:01:32] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 63°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[23:01:32] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:01:32] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[23:01:32] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[23:01:32] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[23:01:32] [DEBUG]   🎛️ Model profile: Default

[23:01:32] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[23:01:32] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[23:01:32] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[23:01:32] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[23:01:32] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[23:01:32] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[23:01:32] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[23:01:32] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[23:01:32] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[23:01:32] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[23:01:32] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[23:01:32] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[23:01:32] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[23:01:32] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[23:01:32] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[23:01:32] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[23:01:32] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[23:01:32] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:01:32] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[23:01:32] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[23:01:32] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[23:01:32] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.4

[23:01:32] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:01:32] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:01:32] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[23:01:32] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[23:01:32] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:01:32] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[23:01:32] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[23:01:32] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[23:01:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:01:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[23:02:25] [INFO]     ✅ V0.3 Call 1/3: master summary = 483 words, 3788 chars

[23:02:25] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[23:02:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:02:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[23:02:56] [INFO]     ✅ V0.3 Call 2/3: 30 bullets derived from master summary

[23:02:56] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[23:02:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:02:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[23:03:22] [INFO]     ✅ V0.3 Call 3/3: exec summary = 446 words

[23:03:22] [DEBUG]     📝 Parsed: exec=3502 chars, bullets=30, thorough=3788 chars

[23:03:54] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[23:03:56] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[23:03:56] [INFO]     ℹ️ Coverage 92% < 98% — B3 voting disabled, will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward 100%

[23:03:56] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 98% → target 100%) — applying 3-Tier Guarantee

[23:03:57] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (30 bullets, 446 exec words, 483 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:03:58] [DEBUG]     🔍 Fact-check: all 30 bullets verified ✓

[23:03:58] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[23:03:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:03:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[23:04:44] [INFO]     ✅ Additive sections via followup call: key_distinctions=1342 chars, theoretical_tensions=1332 chars

[23:04:44] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (30 bullets, 446 exec words, 483 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:04:44] [WARNING]     ⚠️ thorough_summary too short (483 words < 800 threshold) — requesting dedicated expansion…

[23:04:44] [ERROR]   ❌ Chapter 1 failed: 'Summarizer' object has no attribute 'settings'

[23:04:44] [DEBUG]   ⏱️ Chapter 1/1 took 192s (deadline 480s)

[23:04:44] [ERROR] ❌ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… FAILED: 'Summarizer' object has no attribute 'settings'

[23:04:44] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\checkpoints

[23:04:44] [DEBUG]   ⏭️ Checkpoint skip: chapter 1 ('6 - PARANOID PERSONALITY DISORDER') failed/empty — it will be reprocessed on resume.

[23:04:44] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[23:04:48] [INFO]   🧮 Embedding cache: 0 hits / 0 misses (0% hit-rate), 5000 entries

[23:04:48] [WARNING]   ⚠️ Skipped saving FAILED summary 1/1: 6 - PARANOID PERSONALITY DISORDER… (no content — model returned empty)

[23:04:48] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\summaries

[23:04:48] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[23:04:48] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.4_20260926-230448-8f60d6d0.summary.md

[23:04:48] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[23:04:48] [INFO]   ⏱️ DOCX phase starting | [376.1s]

[23:04:48] [INFO] 📄 Building DOCX report…

[23:04:48] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[23:04:48] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[23:04:49] [INFO]   ℹ️ No keypoints found to build.

[23:04:49] [INFO]   📊 Citation graph: no citations found in the text.

[23:04:49] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[23:04:49] [ERROR] ❌ Conversion FAILED: all chapters returned empty responses.

[23:04:49] [ERROR]    1 chapter(s) failed — model produced no content. Likely causes: model not installed, VRAM insufficient, or quantization too aggressive for the prompt complexity. Try: ollama pull <model>, or switch to a less aggressive quant (IQ2_M instead of IQ2_XXS), or raise temperature to 1.0.

[23:05:04] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\logs\quality_report.json

[23:05:04] [INFO] 

[23:05:04] [INFO] ━━━ Thermal Safety Report ━━━

[23:05:04] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:05:04] [INFO]   Session duration: 3.5 min

[23:05:04] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[23:05:04] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[23:05:04] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:05:04] [INFO] 

[23:05:04] [INFO] ━━━ Elixir v0.5.4 Conversion Diagnostic Summary ━━━

[23:05:04] [INFO]   Book: Broken Structures Salman Akhtar

[23:05:04] [INFO]   Total pages: 397

[23:05:04] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[23:05:04] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[23:05:04] [INFO]   Summaries generated: 1

[23:05:04] [INFO]     Success: 0, Failed: 1, Total bullets: 0

[23:05:04] [INFO]     Coverage: 0%

[23:05:04] [INFO]   Warnings: 0

[23:05:04] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar

[23:05:04] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.4_20260926-225832-17ce92bf.conversion.log.md

[23:05:04] [INFO]   Diagnostic JSONL: None

[23:05:04] [INFO]   Summary files (2):

[23:05:04] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.4 | run_id=20260926-230448-8f60d6d0 | started=2026-09-26T23:04:48 | bullets=0

[23:05:04] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.4_20260926-230448-8f60d6d0.summary.md — generated-by v0.5.4 | run_id=20260926-230448-8f60d6d0 | started=2026-09-26T23:04:48 | bullets=0

[23:05:04] [INFO]   Models loaded at exit: (none — all unloaded)

[23:05:04] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:05:04] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[23:05:04] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[23:05:04] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:05:04] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[23:05:04] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[23:05:04] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[23:05:04] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\images

[23:05:04] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[23:05:09] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\images

[23:05:15] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[23:05:15] [INFO]   [pipeline] after de-dup: 2 regions

[23:05:15] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.4\Broken Structures Salman Akhtar\regions

[23:05:15] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[23:05:15] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 0 keypoints)


---
Finished at: 2026-09-26T23:05:15.769619
