# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-25T22:25:23.369461

<!-- generated-by: Elixir v0.4.32 | run_id=20260925-222523-2378ac93 -->

---

[22:25:23] [SUCCESS] 🚀 Starting conversion…

[22:25:23] [DEBUG]   🔍 importing 'pypdf'…

[22:25:23] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[22:25:23] [DEBUG]   🔍 importing 'pdf2image'…

[22:25:23] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[22:25:23] [DEBUG]   🔍 importing 'tiktoken'…

[22:25:23] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[22:25:23] [DEBUG]   🔍 importing 'markitdown'…

[22:25:25] [DEBUG]   ✅ 'markitdown' ok (2.0s)

[22:25:25] [DEBUG]   🔍 importing 'rapidfuzz'…

[22:25:25] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[22:25:25] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[22:25:25] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[22:25:25] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[22:25:25] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[22:25:25] [DEBUG]   🔍 importing 'torch'…

[22:25:25] [DEBUG]   ✅ 'torch' ok (0.0s)

[22:25:25] [DEBUG]   🔍 importing 'transformers'…

[22:25:39] [DEBUG]   ✅ 'transformers' ok (13.9s)

[22:25:39] [DEBUG]   🔍 importing 'langextract'…

[22:25:39] [DEBUG]   ✅ 'langextract' ok (0.1s)

[22:25:39] [DEBUG]   ✅ Pre-flight dependency check passed

[22:25:39] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[22:25:39] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[22:25:39] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar.pdf

[22:25:39] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar

[22:25:39] [INFO]   Source type: normal_book

[22:25:39] [INFO]   App version: 0.4.32

[22:25:39] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[22:25:39] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[22:25:39] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[22:25:39] [INFO]   Ollama reachable (localhost:11434): True

[22:25:39] [INFO]   Provider: llamacpp

[22:25:39] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[22:25:39] [INFO]   [Phase 1 (Extraction)]

[22:25:39] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:25:39] [INFO]   [Phase 2 (Summarization)]

[22:25:39] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:25:39] [INFO]   ────────────────────────────────────────

[22:25:39] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[22:25:39] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[22:25:39] [INFO] ━━━━━━━━━━━━━━━━━━━━

[22:25:39] [INFO]   LLM OCR: True, Force OCR all: False

[22:25:39] [INFO]   Auto-detect scanned: True

[22:25:39] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:25:39] [INFO]   OCR retries: 2, Image max size: 1200

[22:25:39] [INFO]   Page range: all

[22:25:39] [INFO]   Selected chapters: 1 chapter(s)

[22:25:39] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[22:25:39] [INFO]   Segmentation: auto, Token limit: 2000

[22:25:39] [INFO]   Semantic: True, Page group: 10

[22:25:39] [INFO]   Generate summaries: True

[22:25:39] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:25:39] [INFO]   Fast model: , Heavy model: (disabled)

[22:25:39] [INFO]   Workers (requested): 1, Temperature: 0.7

[22:25:39] [INFO]   Self-consistency: False, Coverage threshold: 85%

[22:25:39] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[22:25:39] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[22:25:39] [INFO]   Academic rigor: False

[22:25:39] [INFO]   Max context tokens: 128000

[22:25:39] [INFO]   Max output tokens: 32768

[22:25:39] [INFO]   Keep-alive: 30m

[22:25:39] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[22:25:39] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[22:25:39] [INFO]   Translation: disabled

[22:25:39] [INFO]   Clean markdown: True, Token saver: True

[22:25:39] [INFO]   Content filter: True

[22:25:39] [INFO]   Extract tables: False, Math: False, Figures: False

[22:25:39] [INFO]   Visual-region crops: True

[22:25:39] [INFO]   Layout analysis: False

[22:25:39] [INFO]   DOCX author: Elixir, TOC: True

[22:25:39] [INFO]   Output paths (V7.5 subfolders):

[22:25:39] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[22:25:39] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:25:39] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[22:25:39] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\packets

[22:25:39] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\podcast

[22:25:39] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\logs\quality_report.json

[22:25:39] [INFO]   Resume mode: enabled — will skip done chapters

[22:25:39] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[22:25:39] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:25:39] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[22:25:39] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[22:25:39] [DEBUG]   💾 Disk space: 16.2 GB free

[22:25:39] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\.checkpoint.json

[22:26:42] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[22:26:42] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:26:42] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:26:42] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[22:26:42] [INFO] [TOC] Using PDF outlines: 22 entries.

[22:26:42] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[22:26:42] [DEBUG]   [TOC] Entries passed to segmenter: 22

[22:26:42] [DEBUG]   [TOC] - p.7: Table of Contents

[22:26:42] [DEBUG]   [TOC] - p.9: FOREWORD

[22:26:42] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[22:26:42] [DEBUG]   [TOC] … and 19 more

[22:26:42] [INFO]   🎯 User selected 1 chapter(s):

[22:26:42] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[22:26:43] [INFO]   📸 front_cover → front_cover.jpg

[22:26:43] [INFO]   📸 back_cover → back_cover.jpg

[22:26:43] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:26:43] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[22:26:43] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[22:26:43] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[22:26:43] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[22:26:44] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[22:26:44] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[22:26:44] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[22:26:44] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[22:26:44] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[22:26:44] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[22:26:45] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[22:26:45] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[22:26:45] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[22:26:45] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[22:26:45] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[22:26:45] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[22:26:46] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[22:26:46] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[22:26:46] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[22:26:46] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[22:26:46] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[22:26:47] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[22:26:47] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[22:26:47] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[22:26:47] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[22:26:47] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:26:47] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[22:26:47] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[22:26:47] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[22:26:47] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[22:26:47] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[22:26:47] [INFO]   ✅ markitdown ready for digital-page extraction

[22:26:47] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[22:26:47] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[22:26:47] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[22:26:47] [INFO]      Pages needing OCR: [152, 153, 154]

[22:26:47] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[22:26:47] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[22:26:47] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[22:26:49] [INFO]   📄 140/397 pages processed (35%)

[22:26:55] [INFO]   🔍 OCR  page 152/397 (scanned)…

[22:26:57] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[22:28:26] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[22:28:26] [INFO]   🔍 OCR  page 153/397 (scanned)…

[22:30:04] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[22:30:04] [INFO]   🔍 OCR  page 154/397 (scanned)…

[22:32:06] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[22:32:10] [INFO]   📄 160/397 pages processed (40%)

[22:32:10] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[22:32:10] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[22:32:10] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[22:32:10] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[22:32:10] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[22:32:10] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[22:32:10] [INFO] 📝 Raw markdown: 53,157 chars | [406.9s]

[22:32:10] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[22:32:10] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[22:32:10] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[22:32:10] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[22:32:10] [INFO] [Segmenter] Attempting chapter-level segmentation…

[22:32:10] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:32:10] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[22:32:10] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[22:32:10] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[22:32:10] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[22:32:10] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[22:32:10] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[22:32:10] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[22:32:10] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[22:32:10] [INFO]   📑 Filtered segments: kept 1 of 17

[22:32:10] [INFO] 📚 1 segment(s) detected | [407.1s]

[22:32:10] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[22:32:10] [INFO] 🌐 Detected language: en

[22:32:10] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[22:32:10] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[22:32:10] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\markdown\chapters

[22:32:10] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[22:32:10] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\markdown\chapters

[22:32:10] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[22:32:10] [INFO]   ⏱️ Summary phase starting | [407.4s]

[22:32:12] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[22:32:12] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[22:32:12] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[22:32:12] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[22:32:12] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[22:32:12] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[22:32:12] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[22:32:13] [INFO]   🌡️ Pre-flight: idle GPU temp = 59°C

[22:32:13] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 59°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[22:32:13] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[22:32:13] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[22:32:13] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[22:32:13] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[22:32:13] [DEBUG]   🎛️ Model profile: Default

[22:32:13] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[22:32:13] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[22:32:13] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[22:32:13] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[22:32:13] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[22:32:13] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[22:32:13] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[22:32:13] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[22:32:13] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[22:32:13] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[22:32:13] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[22:32:13] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[22:32:13] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[22:32:13] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[22:32:13] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[22:32:13] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[22:32:13] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[22:32:13] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[22:32:13] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[22:32:13] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[22:32:13] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[22:32:13] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433

[22:32:13] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:32:13] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:32:13] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[22:32:13] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[22:32:13] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:32:13] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[22:32:13] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[22:32:13] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[22:32:13] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:32:13] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[22:33:56] [INFO]     ✅ V0.3 Call 1/3: master summary = 616 words, 4871 chars

[22:33:56] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[22:33:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:33:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[22:34:50] [INFO]     ✅ V0.3 Call 2/3: 32 bullets derived from master summary

[22:34:50] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[22:34:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:34:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[22:35:17] [INFO]     ✅ V0.3 Call 3/3: exec summary = 251 words

[22:35:17] [DEBUG]     📝 Parsed: exec=1961 chars, bullets=32, thorough=4871 chars

[22:35:38] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[22:35:40] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[22:35:40] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee

[22:35:40] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (32 bullets, 251 exec words, 616 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[22:35:41] [DEBUG]     🔍 Fact-check: all 32 bullets verified ✓

[22:35:41] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[22:35:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:35:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[22:36:48] [INFO]     ✅ Additive sections via followup call: key_distinctions=1411 chars, theoretical_tensions=1296 chars

[22:36:48] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (32 bullets, 251 exec words, 616 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[22:36:48] [WARNING]     ⚠️ thorough_summary too short (616 words < 800 threshold) — requesting dedicated expansion…

[22:36:48] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[22:36:48] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[22:38:49] [INFO]     📖 Attempt 1/3: dedicated thorough = 904 words

[22:38:49] [INFO]     ✅ thorough_summary expanded via dedicated call: 616 → 904 words

[22:38:49] [INFO]     V0.05: Skipping bullet expansion — 32 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[22:38:49] [INFO]     ✅ Final coverage 92%

[22:38:49] [DEBUG]     📏 F1: exec=251w, thorough=904w (source=7405w; targets exec<=250w, thorough<=3332w)

[22:40:47] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[22:40:47] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 19.6 (diff: -3.4)

[22:40:47] [INFO]     ℹ️ F3: Summary is 3.3 grade levels denser than source — expected for a compressed academic summary.

[22:40:49] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[22:40:49] [DEBUG]     🔄 J2: 17 cross-section redundancy(ies) found (exec↔bullets: 7, bullets↔thorough: 10)

[22:40:49] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 3 markers)

[22:40:49] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[22:40:49] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[22:40:49] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[22:41:04] [DEBUG]     📊 Batch coverage: 54/56 claims (2 batch encode calls via EmbeddingCache, was 3808 per-pair calls)

[22:41:04] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[22:41:07] [INFO]     📊 Judge: coverage=96% (54/56 claims), grounding=100% (32/32 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[22:41:07] [INFO]   ℹ️ Summary has substantial content (exec=1961 chars, thorough=6953 chars) — Judge coverage check at 96% is likely a false positive for this source length. Auto-passing to preserve content.

[22:41:07] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[22:41:07] [WARNING]   ⏱️⚠️ Deadline exceeded (534s > 480s) — skipping optional phase: scholar reflection

[22:41:07] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[22:41:07] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[22:41:07] [WARNING]   ⏱️⚠️ Deadline exceeded (534s > 480s) — skipping optional phase: semantic dedup

[22:41:07] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[22:41:07] [DEBUG]     🧹 V16.0.2 Bullet normalization: 32 bullets normalized

[22:41:07] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[22:41:07] [WARNING]   ⏱️⚠️ Deadline exceeded (534s > 480s) — skipping optional phase: bullet consolidation

[22:41:07] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[22:41:07] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433

[22:41:07] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:41:07] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:41:07] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Bleuler', 'Freud', 'Heimann', 'Kretschmer', 'Magnan', 'Jaspers', 'Schneider', 'Leonhard', 'Klein', 'Winnicott', 'Erikson']/74 authors in bullets (18%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Stanton', 'Meissner']

[22:41:07] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Frances', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Jacobson', 'Widiger', 'Leonhard', 'Polatin', 'Widiger and Frances', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Frances and Widiger', 'Morey', 'Ovessey', 'Walters']/74 authors in thorough (39%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Byrne']

[22:41:07] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Stanton', 'Meissner']…

[22:41:07] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:41:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:41:26] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[22:41:26] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[22:41:26] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (19.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[22:41:26] [DEBUG]     📊 V18.14.1: After round 1, 52 still missing from bullets: ['Kernberg', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[22:41:26] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[22:41:26] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:41:26] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:41:44] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne described the behavioral correlates of splitting (Akht…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[22:41:44] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[22:41:44] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 6/8 bullets

[22:41:44] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (17.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[22:41:44] [DEBUG]     📊 V18.14.1: After round 2, 46 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Widiger']…

[22:41:44] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Widiger']… (mention-only: ['Byrne'])

[22:41:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:41:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:42:00] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar (1984) described identity diffusion, while Akhtar and…' (source attributes this claim to 'Socarides’s', not 'Akhtar')

[22:42:00] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1975) co-authored a description with Croewe that was noted to…

[22:42:00] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets

[22:42:00] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (16.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=6

[22:42:00] [INFO]     🔁 V18.20.3.7: 'Akhtar and Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:42:01] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[22:42:01] [DEBUG]     📊 V18.14.1: After round 3, 40 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Widiger', 'Kendler']…

[22:42:01] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Akhtar and Byrne', 'Winokur', 'Widiger', 'Kendler', 'Shepherd']… (mention-only: ['Akhtar and Byrne'])

[22:42:01] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:42:01] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:42:18] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne (1983) are cited by the chapter author as providing d…

[22:42:18] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur’s 1975 work with Croewe is noted in the source for offering le…

[22:42:18] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kendler’s 1982 work with Grunberger is referenced as focusing on the p…

[22:42:18] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets

[22:42:18] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (17.6s): response=7 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=4

[22:42:18] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:42:18] [INFO]     🔁 V18.20.3.7: 'Kendler' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:42:18] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Akhtar and Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[22:42:18] [DEBUG]     📊 V18.14.1: After round 4, 32 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Kendler', 'Tobak']…

[22:42:18] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Winokur', 'Kendler', 'Tobak', 'Mahler', 'Bak']… (mention-only: ['Winokur', 'Kendler'])

[22:42:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:42:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:42:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur is cited by the chapter as offering less clarity in textbook d…

[22:42:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kendler is referenced by the chapter regarding the focus on the relati…

[22:42:34] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[22:42:34] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (15.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[22:42:34] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Kendler' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[22:42:34] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Winokur' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[22:42:34] [DEBUG]     📊 V18.14.1: After round 5, 26 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Kendler', 'Allodi']…

[22:42:34] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 29 bullets across 5 round(s)

[22:42:34] [WARNING]     ⚠️ V18.14.1: 26 theorists still missing from bullets after gap-fill: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Kendler', 'Allodi', 'Jack', 'Ndtei', 'Bursten'] — of these, 4 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Kendler'] — 22 never covered (round cap/deadline): ['Allodi', 'Jack', 'Ndtei', 'Bursten', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser']

[22:42:34] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[22:42:34] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[22:42:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[22:42:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[22:42:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[22:42:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[22:42:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[22:42:34] [DEBUG]     🧹 Semantic dedup: removing bullet 10 (sim=0.87 with bullet 1)

[22:42:34] [DEBUG]     🧹 Semantic dedup: removing bullet 52 (sim=0.90 with bullet 42)

[22:42:34] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 67 → 65 bullets (removed 2 gap-fill/conclusion duplicates; 0.7s, non-skippable per V18.20.3.4)

[22:42:34] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\433

[22:42:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:42:34] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:42:37] [INFO]     ℹ️ V0.4.23: 65 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[22:42:37] [INFO]     🛡️ V18.2.13 Post-checks: 4 fixed, 13 flagged (of 65 bullets + exec + thorough)

[22:42:37] [DEBUG]       [grammar/flag] bullet[15]: no main verb detected in first 40 words of 'Psychoanalytic mechanisms in PPD include…' — the bullet may be grammatically broken (generation/formatting failure)  |  Psychoanalytic mechanisms in P…

[22:42:37] [DEBUG]       [consistency/flag] bullet[18]: false 'missing' claim: 'omitted' followed by 'key features of PPD such as grandiosity' — but 3/3 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  DSM-III omitted key features of PPD su…

[22:42:37] [DEBUG]       [grammar/flag] bullet[23]: no main verb detected in first 40 words of 'In self-concept, PPD presents an overtly…' — the bullet may be grammatically broken (generation/formatting failure)  |  In self-concept, PPD presents …

[22:42:37] [DEBUG]       [attribution/flag] bullet[59]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[22:42:37] [DEBUG]       [truncated/flag] bullet[62]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[22:42:37] [DEBUG]       [truncated/flag] bullet[64]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[22:42:37] [DEBUG]       [space/fix] exec: split 'review' -> 're view' (source-validated)  |  … the disorder. The historical review traces PPD from Magnan’…

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 36% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …n entitlement and inadequacy; Jaspers (1949), whose concept …

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Schneider (1950)' has 43% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ities” closely resembled PPD; Schneider (1950), who describe…

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Leonhard (1959)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ative or eccentric types; and Leonhard (1959), who highlight…

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Polatin (1975)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …re recent descriptive work by Polatin (1975) and Millon (198…

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Shapiro (1965)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …croft (1960), Cameron (1963), Shapiro (1965), Jacobson (1971…

[22:42:37] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bursten (1973a)' has 33% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …piro (1965), Jacobson (1971), Bursten (1973a), Kernberg (197…

[22:42:37] [DEBUG]       [consistency/flag] thorough: false 'missing' claim: 'omitted' followed by 'superego unevenness' — but 2/2 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …list of seven items but still omitted superego unevenness, s…

[22:42:37] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   features of paranoid personality (arrogance, suspicion, hyp

[22:42:37] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Descriptive psychiatry views paranoid personality disorder

[22:42:37] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freud's original formulation of paranoia as a defense agai

[22:42:37] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 29/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Byrne']

[22:42:37] [WARNING]   ⏱️⚠️ Deadline exceeded (624s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[22:42:37] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 45 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[22:42:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:42:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:43:27] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, the chapter references work by Thomson (1982), who colla…" — its name(s) never co-occur with the claim's key phrases in the source

[22:43:27] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Kendler (1982, 1984) contributed to understanding the potenti…" — its name(s) never co-occur with the claim's key phrases in the source

[22:43:27] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:43:27] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:44:17] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) specifically delineated the characteristics of the para…" — its name(s) never co-occur with the claim's key phrases in the source

[22:44:17] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Kohut’s (1972) work on narcissistic rage further illuminated the affec…" — its name(s) never co-occur with the claim's key phrases in the source

[22:44:17] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the descriptive literature, Slater and Roth (1977) emphasized the p…" — its name(s) never co-occur with the claim's key phrases in the source

[22:44:17] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Roth’s contributions, alongside those of Allodi and Jack, pro…" — its name(s) never co-occur with the claim's key phrases in the source

[22:44:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:44:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:45:15] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater and Roth (1977) highlighted the "contradictory pride and lack o…" — its name(s) never co-occur with the claim's key phrases in the source

[22:45:15] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Building on this descriptive foundation, Wurmser (1964) emphasized the…" — its name(s) never co-occur with the claim's key phrases in the source

[22:45:15] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1969) examined morbid jealousy as a central feature of the disord…" — its name(s) never co-occur with the claim's key phrases in the source

[22:45:15] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Reid (1987) contributed to the understanding of "paranoid personality"…" — its name(s) never co-occur with the claim's key phrases in the source

[22:45:15] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Lowenthal (1980) discussed the "paranoid personality" in the …" — its name(s) never co-occur with the claim's key phrases in the source

[22:45:15] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 29/74 → 42/74 (3 chunked call(s), ≤12 names each; 9 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[22:45:15] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 46/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Widiger', 'Kendler']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[22:45:15] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 782s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 782s of the budget.

[22:45:15] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[22:45:15] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":65,"exec_chars":1962,"chapter_done":true}

[22:45:15] [DEBUG]   📊 Progress: 1/1 done | 65 bullets | 1,962 chars exec summary

[22:45:15] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\checkpoints

[22:45:15] [INFO] 📄 Building DOCX report…

[22:45:15] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:45:15] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[22:45:15] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.32_20260925-222523-2378ac93_summary.md + DOCX

[22:45:15] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[22:45:15] [INFO]   🧮 Embedding cache: 53 hits / 44 misses (55% hit-rate), 5000 entries

[22:45:15] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.32_20260925-222523-2378ac93_summary.md

[22:45:15] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries

[22:45:15] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:45:15] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.32_20260925-222523-2378ac93.summary.md

[22:45:15] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[22:45:15] [INFO]   ⏱️ DOCX phase starting | [1192.5s]

[22:45:15] [INFO] 📄 Building DOCX report…

[22:45:15] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:45:16] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[22:45:18] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[22:45:20] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[22:47:02] [INFO]   🎯 K1+Classification: 65 bullets — 19 core, 17 supporting, 29 additional

[22:47:02] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:47:03] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:47:03] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:47:03] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:47:03] [INFO]   📊 Citation graph: no citations found in the text.

[22:47:03] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[22:47:03] [SUCCESS] ✅ Conversion complete.

[22:47:19] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\logs\quality_report.json

[22:47:19] [INFO] 

[22:47:19] [INFO] ━━━ Thermal Safety Report ━━━

[22:47:19] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[22:47:19] [INFO]   Session duration: 15.1 min

[22:47:19] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[22:47:19] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[22:47:19] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:47:19] [INFO] 

[22:47:19] [INFO] ━━━ Elixir v0.4.32 Conversion Diagnostic Summary ━━━

[22:47:19] [INFO]   Book: Broken Structures Salman Akhtar

[22:47:19] [INFO]   Total pages: 397

[22:47:19] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[22:47:19] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[22:47:19] [INFO]   Summaries generated: 1

[22:47:19] [INFO]     Success: 1, Failed: 0, Total bullets: 65

[22:47:19] [INFO]     Coverage: 94%

[22:47:19] [INFO]     Recall floor (deterministic, final set): theorists 46/74 (62%), conclusion items 3/3 (100%)

[22:47:19] [INFO]   Warnings: 0

[22:47:19] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar

[22:47:19] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.32_20260925-222523-2378ac93.conversion.log.md

[22:47:19] [INFO]   Diagnostic JSONL: None

[22:47:19] [INFO]   Summary files (3):

[22:47:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.32_20260925-222523-2378ac93_summary.md — generated-by v0.4.32 | run_id=20260925-222523-2378ac93 | started=2026-09-25T22:32:13 | bullets=65

[22:47:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.32 | run_id=20260925-222523-2378ac93 | started=2026-09-25T22:32:13 | bullets=65

[22:47:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.32_20260925-222523-2378ac93.summary.md — generated-by v0.4.32 | run_id=20260925-222523-2378ac93 | started=2026-09-25T22:32:13 | bullets=65

[22:47:19] [INFO]   Models loaded at exit: (none — all unloaded)

[22:47:19] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:47:19] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[22:47:19] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[22:47:19] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:47:19] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[22:47:19] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[22:47:19] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[22:47:19] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\images

[22:47:19] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[22:47:27] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\images

[22:47:35] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[22:47:35] [INFO]   [pipeline] after de-dup: 2 regions

[22:47:35] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\433\Broken Structures Salman Akhtar\regions

[22:47:35] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[22:47:35] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 65 keypoints)


---
Finished at: 2026-09-25T22:47:35.871605
