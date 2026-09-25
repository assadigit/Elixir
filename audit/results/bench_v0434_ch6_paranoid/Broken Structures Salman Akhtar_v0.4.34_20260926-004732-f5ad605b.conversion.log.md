# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T00:47:32.649447

<!-- generated-by: Elixir v0.4.34 | run_id=20260926-004732-f5ad605b -->

---

[00:47:32] [SUCCESS] 🚀 Starting conversion…

[00:47:32] [DEBUG]   🔍 importing 'pypdf'…

[00:47:32] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[00:47:32] [DEBUG]   🔍 importing 'pdf2image'…

[00:47:32] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[00:47:32] [DEBUG]   🔍 importing 'tiktoken'…

[00:47:32] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[00:47:32] [DEBUG]   🔍 importing 'markitdown'…

[00:47:34] [DEBUG]   ✅ 'markitdown' ok (2.1s)

[00:47:34] [DEBUG]   🔍 importing 'rapidfuzz'…

[00:47:34] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[00:47:34] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[00:47:34] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[00:47:34] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[00:47:34] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[00:47:34] [DEBUG]   🔍 importing 'torch'…

[00:47:34] [DEBUG]   ✅ 'torch' ok (0.0s)

[00:47:34] [DEBUG]   🔍 importing 'transformers'…

[00:47:46] [DEBUG]   ✅ 'transformers' ok (12.1s)

[00:47:46] [DEBUG]   🔍 importing 'langextract'…

[00:47:47] [DEBUG]   ✅ 'langextract' ok (0.1s)

[00:47:47] [DEBUG]   ✅ Pre-flight dependency check passed

[00:47:47] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[00:47:47] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[00:47:47] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar.pdf

[00:47:47] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar

[00:47:47] [INFO]   Source type: normal_book

[00:47:47] [INFO]   App version: 0.4.34

[00:47:47] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[00:47:47] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[00:47:47] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[00:47:47] [INFO]   Ollama reachable (localhost:11434): True

[00:47:47] [INFO]   Provider: llamacpp

[00:47:47] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[00:47:47] [INFO]   [Phase 1 (Extraction)]

[00:47:47] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[00:47:47] [INFO]   [Phase 2 (Summarization)]

[00:47:47] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[00:47:47] [INFO]   ────────────────────────────────────────

[00:47:47] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[00:47:47] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[00:47:47] [INFO] ━━━━━━━━━━━━━━━━━━━━

[00:47:47] [INFO]   LLM OCR: True, Force OCR all: False

[00:47:47] [INFO]   Auto-detect scanned: True

[00:47:47] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:47:47] [INFO]   OCR retries: 2, Image max size: 1200

[00:47:47] [INFO]   Page range: all

[00:47:47] [INFO]   Selected chapters: 1 chapter(s)

[00:47:47] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[00:47:47] [INFO]   Segmentation: auto, Token limit: 2000

[00:47:47] [INFO]   Semantic: True, Page group: 10

[00:47:47] [INFO]   Generate summaries: True

[00:47:47] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:47:47] [INFO]   Fast model: , Heavy model: (disabled)

[00:47:47] [INFO]   Workers (requested): 1, Temperature: 0.7

[00:47:47] [INFO]   Self-consistency: False, Coverage threshold: 85%

[00:47:47] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[00:47:47] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[00:47:47] [INFO]   Academic rigor: False

[00:47:47] [INFO]   Max context tokens: 128000

[00:47:47] [INFO]   Max output tokens: 32768

[00:47:47] [INFO]   Keep-alive: 30m

[00:47:47] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[00:47:47] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[00:47:47] [INFO]   Translation: disabled

[00:47:47] [INFO]   Clean markdown: True, Token saver: True

[00:47:47] [INFO]   Content filter: True

[00:47:47] [INFO]   Extract tables: False, Math: False, Figures: False

[00:47:47] [INFO]   Visual-region crops: True

[00:47:47] [INFO]   Layout analysis: False

[00:47:47] [INFO]   DOCX author: Elixir, TOC: True

[00:47:47] [INFO]   Output paths (V7.5 subfolders):

[00:47:47] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[00:47:47] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[00:47:47] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[00:47:47] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\packets

[00:47:47] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\podcast

[00:47:47] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\logs\quality_report.json

[00:47:47] [INFO]   Resume mode: enabled — will skip done chapters

[00:47:47] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[00:47:47] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[00:47:47] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[00:47:47] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[00:47:47] [DEBUG]   💾 Disk space: 25.5 GB free

[00:47:47] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\.checkpoint.json

[00:48:54] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[00:48:54] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[00:48:54] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[00:48:54] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[00:48:54] [INFO] [TOC] Using PDF outlines: 22 entries.

[00:48:54] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[00:48:54] [DEBUG]   [TOC] Entries passed to segmenter: 22

[00:48:54] [DEBUG]   [TOC] - p.7: Table of Contents

[00:48:54] [DEBUG]   [TOC] - p.9: FOREWORD

[00:48:54] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[00:48:54] [DEBUG]   [TOC] … and 19 more

[00:48:54] [INFO]   🎯 User selected 1 chapter(s):

[00:48:54] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[00:48:54] [INFO]   📸 front_cover → front_cover.jpg

[00:48:55] [INFO]   📸 back_cover → back_cover.jpg

[00:48:55] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[00:48:55] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[00:48:55] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[00:48:55] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[00:48:55] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[00:48:56] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[00:48:56] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[00:48:56] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[00:48:56] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[00:48:56] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[00:48:56] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[00:48:57] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[00:48:57] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[00:48:57] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[00:48:57] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[00:48:58] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[00:48:58] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[00:48:58] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[00:48:58] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[00:48:58] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[00:48:59] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[00:48:59] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[00:48:59] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[00:48:59] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[00:48:59] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[00:48:59] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[00:48:59] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[00:48:59] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[00:48:59] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[00:48:59] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[00:48:59] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[00:48:59] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[00:49:00] [INFO]   ✅ markitdown ready for digital-page extraction

[00:49:00] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[00:49:00] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[00:49:00] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[00:49:00] [INFO]      Pages needing OCR: [152, 153, 154]

[00:49:00] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[00:49:00] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[00:49:00] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[00:49:02] [INFO]   📄 140/397 pages processed (35%)

[00:49:08] [INFO]   🔍 OCR  page 152/397 (scanned)…

[00:49:11] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[00:49:42] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[00:49:42] [INFO]   🔍 OCR  page 153/397 (scanned)…

[00:50:05] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[00:50:05] [INFO]   🔍 OCR  page 154/397 (scanned)…

[00:50:38] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[00:50:42] [INFO]   📄 160/397 pages processed (40%)

[00:50:42] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[00:50:42] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[00:50:42] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[00:50:42] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[00:50:42] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[00:50:42] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[00:50:42] [INFO] 📝 Raw markdown: 53,157 chars | [190.2s]

[00:50:42] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[00:50:42] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[00:50:42] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[00:50:42] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[00:50:42] [INFO] [Segmenter] Attempting chapter-level segmentation…

[00:50:42] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:50:42] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[00:50:42] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[00:50:42] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[00:50:42] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[00:50:42] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[00:50:42] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[00:50:42] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[00:50:42] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[00:50:42] [INFO]   📑 Filtered segments: kept 1 of 17

[00:50:42] [INFO] 📚 1 segment(s) detected | [190.3s]

[00:50:42] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[00:50:43] [INFO] 🌐 Detected language: en

[00:50:43] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[00:50:43] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[00:50:43] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\markdown\chapters

[00:50:43] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[00:50:43] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\markdown\chapters

[00:50:43] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[00:50:43] [INFO]   ⏱️ Summary phase starting | [190.6s]

[00:50:45] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[00:50:45] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[00:50:45] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[00:50:45] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[00:50:45] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[00:50:45] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[00:50:45] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[00:50:45] [INFO]   🌡️ Pre-flight: idle GPU temp = 64°C

[00:50:45] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 64°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[00:50:45] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[00:50:45] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[00:50:45] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[00:50:45] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[00:50:45] [DEBUG]   🎛️ Model profile: Default

[00:50:45] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[00:50:45] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[00:50:45] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[00:50:45] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[00:50:45] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[00:50:45] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[00:50:45] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[00:50:45] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[00:50:45] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[00:50:45] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[00:50:45] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[00:50:45] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[00:50:45] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[00:50:45] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[00:50:45] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[00:50:45] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[00:50:45] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[00:50:45] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[00:50:45] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[00:50:45] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[00:50:45] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[00:50:45] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\434

[00:50:45] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[00:50:45] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[00:50:45] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[00:50:45] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[00:50:45] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:50:45] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[00:50:45] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[00:50:45] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[00:50:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:50:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:51:49] [INFO]     ✅ V0.3 Call 1/3: master summary = 533 words, 4143 chars

[00:51:49] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[00:51:49] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:51:49] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[00:52:23] [INFO]     ✅ V0.3 Call 2/3: 22 bullets derived from master summary

[00:52:23] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[00:52:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:52:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[00:52:41] [INFO]     ✅ V0.3 Call 3/3: exec summary = 240 words

[00:52:41] [DEBUG]     📝 Parsed: exec=1895 chars, bullets=22, thorough=4143 chars

[00:53:05] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[00:53:07] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[00:53:07] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee

[00:53:07] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (22 bullets, 240 exec words, 533 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[00:53:08] [DEBUG]     🔍 Fact-check: all 22 bullets verified ✓

[00:53:08] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[00:53:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:53:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[00:54:11] [INFO]     ✅ Additive sections via followup call: key_distinctions=1721 chars, theoretical_tensions=1836 chars

[00:54:11] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (22 bullets, 240 exec words, 533 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[00:54:11] [WARNING]     ⚠️ thorough_summary too short (533 words < 800 threshold) — requesting dedicated expansion…

[00:54:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[00:54:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[00:55:14] [INFO]     📖 Attempt 1/3: dedicated thorough = 533 words

[00:55:14] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[00:55:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[00:55:17] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[01:00:04] [INFO]     📖 Attempt 2/3: dedicated thorough = 3945 words

[01:00:04] [INFO]     ✅ thorough_summary expanded via dedicated call: 533 → 3945 words

[01:00:04] [WARNING]   ⏱️⚠️ Deadline exceeded (558s > 480s) — skipping optional phase: dedicated bullet expansion

[01:00:04] [INFO]     ✅ Final coverage 100%

[01:00:04] [DEBUG]     📏 F1: exec=240w, thorough=3945w (source=7405w; targets exec<=250w, thorough<=3332w)

[01:01:37] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[01:01:37] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.6 (diff: -4.3)

[01:01:37] [INFO]     ℹ️ F3: Summary is 4.3 grade levels denser than source — expected for a compressed academic summary.

[01:01:39] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[01:01:39] [DEBUG]     🔄 J2: 16 cross-section redundancy(ies) found (exec↔bullets: 3, bullets↔thorough: 12)

[01:01:39] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[01:01:39] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[01:01:39] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[01:01:39] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[01:01:56] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 2688 per-pair calls)

[01:01:56] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[01:01:59] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (22/22 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[01:01:59] [INFO]   ℹ️ Summary has substantial content (exec=1895 chars, thorough=29757 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[01:01:59] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[01:01:59] [WARNING]   ⏱️⚠️ Deadline exceeded (673s > 480s) — skipping optional phase: scholar reflection

[01:01:59] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[01:01:59] [DEBUG]     🛡️ Anti-false-precision: SKIPPED rewrite of 'Slater and Roth (1977) pointed out the "contradictory pride …' — claim1 is a fragment starting with 'and' (merge would produce broken grammar)

[01:01:59] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[01:01:59] [WARNING]   ⏱️⚠️ Deadline exceeded (673s > 480s) — skipping optional phase: semantic dedup

[01:01:59] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[01:01:59] [DEBUG]     🧹 V16.0.2 Bullet normalization: 22 bullets normalized

[01:01:59] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[01:01:59] [WARNING]   ⏱️⚠️ Deadline exceeded (673s > 480s) — skipping optional phase: bullet consolidation

[01:01:59] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[01:01:59] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\434

[01:01:59] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[01:01:59] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[01:01:59] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Bleuler', 'Freud', 'Kretschmer', 'Magnan', 'Jaspers', 'Schneider', 'Leonhard', 'Polatin', 'Klein', 'Winnicott']/74 authors in bullets (16%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Stanton', 'Heimann']

[01:01:59] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Thomson', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne', 'Akhtar and Thomson', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Widiger', 'Kendler', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Widiger and Frances', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Anthony', 'Kohut', 'Bach', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Frances and Widiger', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Gorton and Akhtar', 'Siever']/74 authors in thorough (76%) — MISSING from thorough: ['Winokur', 'Fenichel', 'Bergman', 'Allodi', 'Jack']

[01:01:59] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Stanton', 'Heimann']…

[01:01:59] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:01:59] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:02:18] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[01:02:18] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (19.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[01:02:18] [DEBUG]     📊 V18.14.1: After round 1, 52 still missing from bullets: ['Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[01:02:18] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[01:02:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:02:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:02:34] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne co-authored descriptions (with Akhtar) of the behavioral correla…

[01:02:34] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[01:02:34] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 6/8 bullets

[01:02:34] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (16.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=6

[01:02:34] [DEBUG]     📊 V18.14.1: After round 2, 43 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Kendler']…

[01:02:34] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Kendler']…

[01:02:34] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:02:34] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:02:52] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne: They provided descriptions of the behavioral correla…

[01:02:52] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur: His 1975 work with Croewe was noted as an example of textbook…

[01:02:52] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets

[01:02:52] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (18.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[01:02:52] [DEBUG]     📊 V18.14.1: After round 3, 32 still missing from bullets: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Bach']…

[01:02:52] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Winokur', 'Mahler', 'Anthony', 'Kohut', 'Bach']…

[01:02:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:02:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:03:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur’s (1985) work on paranoid disorders is cited alongside other s…

[01:03:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is referenced …

[01:03:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited alongside oth…

[01:03:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bach’s (1977) observation on the “mirror complementarity of the self” …

[01:03:14] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets

[01:03:14] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (21.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[01:03:14] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[01:03:14] [DEBUG]     📊 V18.14.1: After round 4, 28 still missing from bullets: ['Winokur', 'Anthony', 'Kohut', 'Bach', 'Jack']…

[01:03:14] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Winokur', 'Anthony', 'Kohut', 'Bach', 'Jack']… (mention-only: ['Winokur'])

[01:03:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:03:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:03:28] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut (1972) provided a description of narcissistic rage that is cited…

[01:03:28] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited as part of a list of sources for differentiating …

[01:03:28] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is included in the citation list supporting the distincti…

[01:03:28] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 5/8 bullets

[01:03:28] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (14.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[01:03:28] [INFO]     🔁 V18.20.3.7: 'Kohut' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[01:03:28] [DEBUG]     📊 V18.14.1: After round 5, 22 still missing from bullets: ['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao']…

[01:03:28] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 29 bullets across 5 round(s)

[01:03:28] [WARNING]     ⚠️ V18.14.1: 22 theorists still missing from bullets after gap-fill: ['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels'] — 22 never covered (round cap/deadline): ['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels']

[01:03:28] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[01:03:28] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[01:03:28] [DEBUG]     ✅ V0.4.23: enumeration guarantee — all 43 item(s) across 9 detected list(s) already covered (no bullets added)

[01:03:29] [DEBUG]     🧹 Semantic dedup: removing bullet 19 (sim=0.87 with bullet 1)

[01:03:29] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 52 → 51 bullets (removed 1 gap-fill/conclusion duplicates; 0.8s, non-skippable per V18.20.3.4)

[01:03:29] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\434

[01:03:29] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[01:03:29] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[01:03:32] [INFO]     ℹ️ V0.4.23: 51 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[01:03:32] [INFO]     🛡️ V18.2.13 Post-checks: 22 fixed, 7 flagged (of 51 bullets + exec + thorough)

[01:03:32] [DEBUG]       [fragment_merge/flag] bullet[5]: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  A consistent theme in descriptive literatur…

[01:03:32] [DEBUG]       [space/fix] bullet[31]: split 'review' -> 're view' (source-validated)  |  Frances, in a 1985 review with Widiger, attribute…

[01:03:32] [DEBUG]       [dropped_letter/flag] bullet[33]: likely garbled token: 'paranoics' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …t the confidence and pride of paranoics cloak a hollow shell…

[01:03:32] [DEBUG]       [sentence_fusion/flag] bullet[40]: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  endacity with moralistic self-righteousness in the paranoid characte

[01:03:32] [DEBUG]       [attribution/flag] bullet[45]: attribution mismatch: summary's claim about 'Anthony (1981)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Anthony (1981) delineated the …

[01:03:32] [DEBUG]       [attribution/flag] bullet[50]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[01:03:32] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  ighly structuralized and ego-syntonically embedded in personality 

[01:03:32] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'DSM-III (1980)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ia, noting their limitations. DSM-III (1980) listed PPD as a…

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   in two types: combative (unpleasantly insistent, actively q

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   while Salzman (1974) noted the coexistence of feelings of s

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the earliest developmental constellation of infantile ob

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a menace. The end of intrauterine bliss at birth provide

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects to project split-off attributes onto, with

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who remains benevolent despite attacks might turn out to be

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Shapiro regarded the paranoid person’s construction of a su

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   clues from context, and loss of appreciation of that contex

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   unconscious desires are disavowed by projection and further

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   involves preoedipal problems. Interweaving his propositions

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   the ambivalently loved object felt to be both persecutory a

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and unemotional; pride taken in always being objective, rat

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   is an improvement. However, DSM-III-R does not include supe

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   noted by Bach (1977). Patients may initially display some u

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   people, terrified of loving and being loved, detests depend

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   data offered by mechanical, electronic, or even legal profe

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   lines of work). IV. Love and Sexuality (Overt: seemingly de

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   that fit preexisting bias, rich vocabulary, ability for hai

[01:03:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   loses proportion and context, readily dismisses the obvious

[01:03:32] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[01:03:32] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Libidinal vs. Aggressive/Ethical origins of paranoia: Freu

[01:03:32] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 56/74 authors in thorough — MISSING from thorough: ['Winokur', 'Fenichel', 'Bergman', 'Allodi', 'Jack']

[01:03:32] [WARNING]   ⏱️⚠️ Deadline exceeded (766s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[01:03:32] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 18 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[01:03:32] [INFO]     ⏭️  V0.05: Thorough gap-fill skipped — thorough (3945 words) already meets its source-scaled target (3332 words); the missing contributor(s) are covered by the bullets/recall floor

[01:03:32] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 52/74 in final bullets (missing: ['Kohut', 'Jack', 'Ndtei', 'Green', 'Pao']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[01:03:32] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 767s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 767s of the budget.

[01:03:32] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[01:03:32] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":51,"exec_chars":1895,"chapter_done":true}

[01:03:32] [DEBUG]   📊 Progress: 1/1 done | 51 bullets | 1,895 chars exec summary

[01:03:32] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\checkpoints

[01:03:32] [INFO] 📄 Building DOCX report…

[01:03:32] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[01:03:32] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[01:03:32] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.34_20260926-004732-f5ad605b_summary.md + DOCX

[01:03:32] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[01:03:32] [INFO]   🧮 Embedding cache: 63 hits / 24 misses (72% hit-rate), 5000 entries

[01:03:32] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.34_20260926-004732-f5ad605b_summary.md

[01:03:32] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries

[01:03:32] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[01:03:32] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.34_20260926-004732-f5ad605b.summary.md

[01:03:32] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[01:03:32] [INFO]   ⏱️ DOCX phase starting | [960.1s]

[01:03:32] [INFO] 📄 Building DOCX report…

[01:03:32] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[01:03:33] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[01:03:34] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[01:03:36] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[01:04:54] [INFO]   🎯 K1+Classification: 51 bullets — 13 core, 28 supporting, 10 additional

[01:04:54] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[01:04:54] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[01:04:54] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[01:04:54] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[01:04:54] [INFO]   📊 Citation graph: no citations found in the text.

[01:04:54] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[01:04:54] [SUCCESS] ✅ Conversion complete.

[01:05:11] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\logs\quality_report.json

[01:05:11] [INFO] 

[01:05:11] [INFO] ━━━ Thermal Safety Report ━━━

[01:05:11] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[01:05:11] [INFO]   Session duration: 14.4 min

[01:05:11] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[01:05:11] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[01:05:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[01:05:11] [INFO] 

[01:05:11] [INFO] ━━━ Elixir v0.4.34 Conversion Diagnostic Summary ━━━

[01:05:11] [INFO]   Book: Broken Structures Salman Akhtar

[01:05:11] [INFO]   Total pages: 397

[01:05:11] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[01:05:11] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[01:05:11] [INFO]   Summaries generated: 1

[01:05:11] [INFO]     Success: 1, Failed: 0, Total bullets: 51

[01:05:11] [INFO]     Coverage: 100%

[01:05:11] [INFO]     Recall floor (deterministic, final set): theorists 52/74 (70%), conclusion items 3/3 (100%)

[01:05:11] [INFO]   Warnings: 0

[01:05:11] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar

[01:05:11] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.34_20260926-004732-f5ad605b.conversion.log.md

[01:05:11] [INFO]   Diagnostic JSONL: None

[01:05:11] [INFO]   Summary files (3):

[01:05:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.34_20260926-004732-f5ad605b_summary.md — generated-by v0.4.34 | run_id=20260926-004732-f5ad605b | started=2026-09-26T00:50:45 | bullets=51

[01:05:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.34 | run_id=20260926-004732-f5ad605b | started=2026-09-26T00:50:45 | bullets=51

[01:05:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.34_20260926-004732-f5ad605b.summary.md — generated-by v0.4.34 | run_id=20260926-004732-f5ad605b | started=2026-09-26T00:50:45 | bullets=51

[01:05:11] [INFO]   Models loaded at exit: (none — all unloaded)

[01:05:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[01:05:11] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[01:05:11] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[01:05:11] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[01:05:11] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[01:05:11] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[01:05:11] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[01:05:11] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\images

[01:05:11] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[01:05:16] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\images

[01:05:23] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[01:05:23] [INFO]   [pipeline] after de-dup: 2 regions

[01:05:23] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\434\Broken Structures Salman Akhtar\regions

[01:05:23] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[01:05:23] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 51 keypoints)


---
Finished at: 2026-09-26T01:05:23.849703
