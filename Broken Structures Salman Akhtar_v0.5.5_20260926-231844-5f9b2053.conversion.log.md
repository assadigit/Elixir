# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T23:18:44.819493

<!-- generated-by: Elixir v0.5.5 | run_id=20260926-231844-5f9b2053 -->

---

[23:18:44] [SUCCESS] 🚀 Starting conversion…

[23:18:44] [DEBUG]   🔍 importing 'pypdf'…

[23:18:44] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[23:18:44] [DEBUG]   🔍 importing 'pdf2image'…

[23:18:44] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[23:18:44] [DEBUG]   🔍 importing 'tiktoken'…

[23:18:44] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[23:18:44] [DEBUG]   🔍 importing 'markitdown'…

[23:18:46] [DEBUG]   ✅ 'markitdown' ok (1.5s)

[23:18:46] [DEBUG]   🔍 importing 'rapidfuzz'…

[23:18:46] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[23:18:46] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[23:18:46] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[23:18:46] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[23:18:46] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[23:18:46] [DEBUG]   ✅ 'torch' installed

[23:18:46] [DEBUG]   ✅ 'transformers' installed

[23:18:46] [DEBUG]   ✅ 'langextract' installed

[23:18:46] [DEBUG]   ✅ Pre-flight dependency check passed

[23:18:46] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[23:18:46] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[23:18:46] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar.pdf

[23:18:46] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar

[23:18:46] [INFO]   Source type: normal_book

[23:18:46] [INFO]   App version: 0.5.5

[23:18:46] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[23:18:46] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[23:18:46] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[23:18:46] [INFO]   Ollama reachable (localhost:11434): True

[23:18:46] [INFO]   Provider: llamacpp

[23:18:46] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[23:18:46] [INFO]   [Phase 1 (Extraction)]

[23:18:46] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[23:18:46] [INFO]   [Phase 2 (Summarization)]

[23:18:46] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[23:18:46] [INFO]   ────────────────────────────────────────

[23:18:46] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[23:18:46] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[23:18:46] [INFO] ━━━━━━━━━━━━━━━━━━━━

[23:18:46] [INFO]   LLM OCR: True, Force OCR all: False

[23:18:46] [INFO]   Auto-detect scanned: True

[23:18:46] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:18:46] [INFO]   OCR retries: 2, Image max size: 1200

[23:18:46] [INFO]   Page range: all

[23:18:46] [INFO]   Selected chapters: 1 chapter(s)

[23:18:46] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[23:18:46] [INFO]   Segmentation: auto, Token limit: 2000

[23:18:46] [INFO]   Semantic: True, Page group: 10

[23:18:46] [INFO]   Generate summaries: True

[23:18:46] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:18:46] [INFO]   Fast model: , Heavy model: (disabled)

[23:18:46] [INFO]   Workers (requested): 1, Temperature: 0.7

[23:18:46] [INFO]   Self-consistency: False, Coverage threshold: 85%

[23:18:46] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[23:18:46] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[23:18:46] [INFO]   Academic rigor: False

[23:18:46] [INFO]   Max context tokens: 128000

[23:18:46] [INFO]   Max output tokens: 32768

[23:18:46] [INFO]   Keep-alive: 30m

[23:18:46] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[23:18:46] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[23:18:46] [INFO]   Translation: disabled

[23:18:46] [INFO]   Clean markdown: True, Token saver: True

[23:18:46] [INFO]   Content filter: True

[23:18:46] [INFO]   Extract tables: False, Math: False, Figures: False

[23:18:46] [INFO]   Visual-region crops: True

[23:18:46] [INFO]   Layout analysis: False

[23:18:46] [INFO]   DOCX author: Elixir, TOC: True

[23:18:46] [INFO]   Output paths (V7.5 subfolders):

[23:18:46] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[23:18:46] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[23:18:46] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[23:18:46] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\packets

[23:18:46] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\podcast

[23:18:46] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\logs\quality_report.json

[23:18:46] [INFO]   Resume mode: enabled — will skip done chapters

[23:18:46] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[23:18:46] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:18:46] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[23:18:46] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[23:18:46] [DEBUG]   💾 Disk space: 22.9 GB free

[23:18:46] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\.checkpoint.json

[23:19:43] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[23:19:43] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[23:19:43] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[23:19:43] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[23:19:43] [INFO] [TOC] Using PDF outlines: 22 entries.

[23:19:43] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[23:19:43] [DEBUG]   [TOC] Entries passed to segmenter: 22

[23:19:43] [DEBUG]   [TOC] - p.7: Table of Contents

[23:19:43] [DEBUG]   [TOC] - p.9: FOREWORD

[23:19:43] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[23:19:43] [DEBUG]   [TOC] … and 19 more

[23:19:43] [INFO]   🎯 User selected 1 chapter(s):

[23:19:43] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[23:19:43] [INFO]   📸 front_cover → front_cover.jpg

[23:19:43] [INFO]   📸 back_cover → back_cover.jpg

[23:19:43] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:19:43] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[23:19:44] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[23:19:44] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[23:19:44] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[23:19:44] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[23:19:45] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[23:19:45] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[23:19:45] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[23:19:45] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[23:19:45] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[23:19:45] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[23:19:45] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[23:19:46] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[23:19:46] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[23:19:46] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[23:19:46] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[23:19:46] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[23:19:46] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[23:19:47] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[23:19:47] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[23:19:47] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[23:19:47] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[23:19:47] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[23:19:48] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[23:19:48] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[23:19:48] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:19:48] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[23:19:48] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[23:19:48] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[23:19:48] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[23:19:48] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[23:19:48] [INFO]   ✅ markitdown ready for digital-page extraction

[23:19:48] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[23:19:48] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[23:19:48] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[23:19:48] [INFO]      Pages needing OCR: [152, 153, 154]

[23:19:48] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[23:19:48] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[23:19:48] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[23:19:50] [INFO]   📄 140/397 pages processed (35%)

[23:19:55] [INFO]   🔍 OCR  page 152/397 (scanned)…

[23:19:57] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[23:20:05] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[23:20:05] [INFO]   🔍 OCR  page 153/397 (scanned)…

[23:20:07] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[23:20:07] [INFO]   🔍 OCR  page 154/397 (scanned)…

[23:20:16] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[23:20:19] [INFO]   📄 160/397 pages processed (40%)

[23:20:19] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[23:20:19] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[23:20:19] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[23:20:19] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[23:20:19] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[23:20:19] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[23:20:19] [INFO] 📝 Raw markdown: 53,157 chars | [94.4s]

[23:20:19] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[23:20:19] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[23:20:19] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[23:20:19] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[23:20:19] [INFO] [Segmenter] Attempting chapter-level segmentation…

[23:20:19] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[23:20:19] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[23:20:19] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[23:20:19] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[23:20:19] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[23:20:19] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[23:20:19] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[23:20:19] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[23:20:19] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:20:19] [INFO]   📑 Filtered segments: kept 1 of 17

[23:20:19] [INFO] 📚 1 segment(s) detected | [94.5s]

[23:20:19] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[23:20:19] [INFO] 🌐 Detected language: en

[23:20:19] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[23:20:19] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[23:20:19] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\markdown\chapters

[23:20:19] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[23:20:19] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\markdown\chapters

[23:20:19] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[23:20:19] [INFO]   ⏱️ Summary phase starting | [94.8s]

[23:20:21] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[23:20:21] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[23:20:21] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[23:20:21] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[23:20:21] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[23:20:21] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[23:20:21] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[23:20:21] [INFO]   🌡️ Pre-flight: idle GPU temp = 61°C

[23:20:21] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 61°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[23:20:21] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:20:21] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[23:20:21] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[23:20:21] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[23:20:21] [DEBUG]   🎛️ Model profile: Default

[23:20:21] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[23:20:21] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[23:20:21] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[23:20:21] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[23:20:21] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[23:20:21] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[23:20:21] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[23:20:21] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[23:20:21] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[23:20:21] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[23:20:21] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[23:20:21] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[23:20:21] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[23:20:21] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[23:20:21] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[23:20:21] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[23:20:21] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[23:20:21] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[23:20:21] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[23:20:21] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[23:20:22] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[23:20:22] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.5

[23:20:22] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:20:22] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:20:22] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[23:20:22] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[23:20:22] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[23:20:22] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[23:20:22] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[23:20:22] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[23:20:22] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:20:22] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[23:21:24] [INFO]     ✅ V0.3 Call 1/3: master summary = 976 words, 7971 chars

[23:21:24] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[23:21:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:21:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[23:22:11] [INFO]     ✅ V0.3 Call 2/3: 41 bullets derived from master summary

[23:22:11] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[23:22:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:22:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[23:22:28] [INFO]     ✅ V0.3 Call 3/3: exec summary = 209 words

[23:22:28] [DEBUG]     📝 Parsed: exec=1875 chars, bullets=41, thorough=7971 chars

[23:22:55] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[23:22:57] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[23:22:57] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (41 bullets, 209 exec words, 976 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:22:58] [DEBUG]     🔍 Fact-check: all 41 bullets verified ✓

[23:22:58] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[23:22:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:22:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[23:23:29] [INFO]     ✅ Additive sections via followup call: key_distinctions=2124 chars, theoretical_tensions=1732 chars

[23:23:29] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (41 bullets, 209 exec words, 976 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[23:23:29] [INFO]     ⚠️ 41 bullets — requesting dedicated bullet expansion (full output budget)…

[23:23:29] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:23:29] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=8192 streaming…

[23:24:10] [INFO]     ✅ Final coverage 100%

[23:24:10] [DEBUG]     📏 F1: exec=209w, thorough=976w (source=7405w; targets exec<=250w, thorough<=3332w)

[23:26:13] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[23:26:13] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 21.5 (diff: -5.2)

[23:26:13] [WARNING]     ⚠️ F3: Summary is 5.2 grade levels HARDER to read than source — extreme density (informational only; simplification LLM call removed in V18.2.38).

[23:26:14] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[23:26:14] [DEBUG]     🔄 J2: 27 cross-section redundancy(ies) found (exec↔bullets: 3, bullets↔thorough: 24)

[23:26:14] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[23:26:14] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[23:26:14] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[23:26:14] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[23:26:27] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 4816 per-pair calls)

[23:26:27] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[23:26:31] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (41/41 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[23:26:31] [INFO]   ℹ️ Summary has substantial content (exec=1875 chars, thorough=7966 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[23:26:31] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[23:26:31] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[23:26:31] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[23:26:31] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[23:26:31] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:26:31] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[23:27:41] [INFO]     📜 Scholar response truncated — one additive continuation retry (V18.20.4.12 / O-a4)

[23:27:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:27:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: DSM-III criteria required at least three indicators of perva…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Shapiro (1965) two paranoid types and cognitive details: onl…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: DSM-III-R specific seven items not enumerated in summary…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Table 6-1 self-concept and ethics domains under-specified…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Conlon (1984) mnemonic absent from summary…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Frances et al. (1988) utilizable-by caveat absent…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Bach (1977) mirror complementarity absent…

[23:28:07] [DEBUG]     🎓 Dropped gap-fill without quote: Lowenthal/Bergman aging adjustment absent…

[23:28:07] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 20)

[23:28:07] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}

[23:28:07] [INFO]     🧩 V18.20.3.4: Filtered 1 thinking/scar bullet(s) from scholar gap-fill before merge

[23:28:07] [INFO]     🎓 Gap-fill: added 20 new bullet(s) from scholar reflection (source-grounded)

[23:28:07] [INFO]     🎓 Scholar reflection: identified 8 gap(s), filled 20 with new bullets

[23:28:07] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[23:28:07] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 11 (sim=0.86 with bullet 1)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 33 (sim=0.85 with bullet 1)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 35 (sim=0.86 with bullet 1)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 38 (sim=0.85 with bullet 30)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 55 (sim=0.89 with bullet 45)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.98 with bullet 48)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 59 (sim=0.91 with bullet 50)

[23:28:08] [DEBUG]     🧹 Semantic dedup: removing bullet 60 (sim=0.91 with bullet 46)

[23:28:08] [INFO]     🧹 Semantic dedup: 61 → 53 bullets (removed 8 semantic duplicates)

[23:28:08] [DEBUG]     🧹 V16.0.2 Bullet normalization: 53 bullets normalized

[23:28:08] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[23:28:08] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.5

[23:28:08] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:28:08] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:28:08] [INFO]     🔧 Bullet consolidation SKIPPED — deterministic probe found 0 mergeable pairs (53 bullets, LLM call not needed; rig .3.7-.3.9: the LLM merged 0 on the same input shape)

[23:28:08] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.5

[23:28:08] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:28:08] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:28:08] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Frances', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Bach', 'Bergman', 'Erikson', 'Bursten', 'Conlon', 'Reid', 'Lowenthal', 'Morey']/74 authors in bullets (45%) — MISSING from bullets: ['Akhtar', 'Thomson', 'Hamilton', 'Byrne', 'Akhtar and Byrne']

[23:28:08] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Leonhard', 'Shepherd', 'Slater and Roth', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Bach', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Morey']/74 authors in thorough (43%) — MISSING from thorough: ['Akhtar', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[23:28:08] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Thomson', 'Hamilton', 'Byrne', 'Akhtar and Byrne']…

[23:28:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:28:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:28:23] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne: Co-described the behavioral correlates of splitting w…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[23:28:23] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne: Described the behavioral correlates of spl…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[23:28:23] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 6/8 bullets

[23:28:23] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[23:28:23] [DEBUG]     📊 V18.14.1: After round 1, 34 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Widiger', 'Kendler']…

[23:28:23] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Widiger', 'Kendler']… (mention-only: ['Byrne'])

[23:28:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:28:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:28:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne is mentioned as a co-author with Akhtar in descriptions of behav…

[23:28:33] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[23:28:33] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (10.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[23:28:33] [DEBUG]     📊 V18.14.1: After round 2, 21 still missing from bullets: ['Anthony', 'Kohut', 'Fenichel', 'Allodi', 'Jack']…

[23:28:33] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Anthony', 'Kohut', 'Fenichel', 'Allodi', 'Jack']…

[23:28:33] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:28:33] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:28:45] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[23:28:45] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (12.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[23:28:45] [DEBUG]     📊 V18.14.1: After round 3, 13 still missing from bullets: ['Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser']…

[23:28:45] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser']…

[23:28:45] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:28:45] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:28:58] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) is cited in the source regarding paranoid disorders, …

[23:28:58] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 7/8 bullets

[23:28:58] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (12.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[23:28:58] [DEBUG]     📊 V18.14.1: After round 4, 3 still missing from bullets: ['Rettersol', 'Varghesi', 'Munro']

[23:28:58] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 3 missing authors: ['Rettersol', 'Varghesi', 'Munro']

[23:28:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:28:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[23:29:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) is cited in the source alongside Winokur (1985) as an…

[23:29:03] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 2/3 bullets

[23:29:03] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (5.9s): response=3 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=2

[23:29:03] [INFO]     🔁 V18.20.3.7: 'Rettersol' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[23:29:03] [DEBUG]     📊 V18.14.1: After round 5, 1 still missing from bullets: ['Rettersol']

[23:29:03] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 30 bullets across 5 round(s)

[23:29:03] [WARNING]     ⚠️ V18.14.1: 1 theorists still missing from bullets after gap-fill: ['Rettersol'] — 1 never covered (round cap/deadline): ['Rettersol']

[23:29:03] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[23:29:03] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[23:29:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[23:29:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (1 item(s) were uncovered; all 4 now carried verbatim)

[23:29:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[23:29:03] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[23:29:05] [DEBUG]     🧹 Semantic dedup: removing bullet 57 (sim=0.96 with bullet 55)

[23:29:05] [DEBUG]     🧹 Semantic dedup: removing bullet 65 (sim=0.93 with bullet 63)

[23:29:05] [DEBUG]     🧹 Semantic dedup: removing bullet 71 (sim=0.88 with bullet 70)

[23:29:05] [DEBUG]     🧹 Semantic dedup: removing bullet 72 (sim=0.90 with bullet 70)

[23:29:05] [DEBUG]     🧹 Semantic dedup: removing bullet 81 (sim=0.86 with bullet 80)

[23:29:05] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 88 → 83 bullets (removed 5 gap-fill/conclusion duplicates; 1.1s, non-skippable per V18.20.3.4)

[23:29:05] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.5

[23:29:05] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[23:29:05] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[23:29:08] [INFO]     🛡️ V18.2.13 Post-checks: 11 fixed, 10 flagged (of 82 bullets + exec + thorough)

[23:29:08] [DEBUG]       [sentence_fusion/flag] bullet[9]: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  endacity with moralistic self-righteousness in individuals with PPD.

[23:29:08] [DEBUG]       [consistency/flag] bullet[25]: false 'missing' claim: 'omitted' followed by 'superego unevenness' — but 2/2 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …eria to seven items but still omitted superego unevenness, s…

[23:29:08] [DEBUG]       [sentence_fusion/flag] bullet[33]: likely sentence-fusion garble: 'overinclusiveness' is not in the source or English lexicon but ends with source-word 'overinclusive' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  biased attention (versus overinclusiveness), and identity diffusion

[23:29:08] [DEBUG]       [grammar/flag] bullet[68]: no main verb detected in first 40 words of 'Green (1986) wrote an essay on moral nar…' — the bullet may be grammatically broken (generation/formatting failure)  |  Green (1986) wrote an essay on…

[23:29:08] [DEBUG]       [attribution/flag] bullet[70]: attribution mismatch: summary's claim about 'Socarides (1966)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Socarides (1966) contributed a…

[23:29:08] [DEBUG]       [sentence_fusion/flag] bullet[79]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[23:29:08] [DEBUG]       [truncated/flag] bullet[81]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[23:29:08] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  endacity with moralistic self-righteousness. The descriptive summary

[23:29:08] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'overinclusiveness' is not in the source or English lexicon but ends with source-word 'overinclusive' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |   versus the compulsive’s overinclusiveness, and possesses a lower-l

[23:29:08] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …h an attitude of entitlement; Jaspers (1949) described "self…

[23:29:08] [DEBUG]       [quote_verification/fix] bullet[48]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   in two types: combative, who are 

[23:29:08] [DEBUG]       [quote_verification/fix] bullet[48]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and eccentric, who are 

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by idiosyncratic thinking and suspiciousness.

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality as an individual who is always on alert to find

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who overcompensate for humiliation with formalism; Schneide

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ; and Leonhard (1959) and Shepherd (1961) highlighted the ac

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a developmental substrate involving projection of inborn

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   cognitive style that imposes a biased scheme on factual det

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   The psychoanalytic summary identifies nine core features: p

[23:29:08] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but still omitting superego unevenness, self-esteem defects

[23:29:08] [DEBUG]       [near_duplicate/fix] bullet[80]: near-duplicate of bullet[18] (token-set containment >= 0.8) — kept the first, dropped this one  |  **Cameron outlined four aspects of paranoid** — 4 items from

[23:29:08] [INFO]     ℹ️ V0.4.23: 82 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[23:29:08] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 32/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[23:29:08] [WARNING]   ⏱️⚠️ Deadline exceeded (526s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[23:29:08] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 42 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[23:29:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:29:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:29:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Widiger and Frances (1985) explicitly attributed their own omission of…" — its name(s) never co-occur with the claim's key phrases in the source

[23:29:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This gap in the descriptive literature is partially addressed by the w…" — its name(s) never co-occur with the claim's key phrases in the source

[23:29:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, the chapter highlights the indirect but significant bear…" — its name(s) never co-occur with the claim's key phrases in the source

[23:29:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "(1984) and Kendler and Grunberger (1982) contributed by focusing on th…" — its name(s) never co-occur with the claim's key phrases in the source

[23:29:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, to contextualize the synthesis of these descriptive and psych…" — its name(s) never co-occur with the claim's key phrases in the source

[23:29:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:29:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:30:29] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the developmental trajectory of the paranoid…" — its name(s) never co-occur with the claim's key phrases in the source

[23:30:29] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the descriptive and clinical domains, Pao (1969) provided foundatio…" — its name(s) never co-occur with the claim's key phrases in the source

[23:30:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[23:30:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[23:31:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser (1970) contributed a specific psychoanalytic formulation ident…" — its name(s) never co-occur with the claim's key phrases in the source

[23:31:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Conlon (1962) and Reid (1984) have examined the clinical…" — its name(s) never co-occur with the claim's key phrases in the source

[23:31:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Lowenthal (1970) described the "paranoid character" as possessing a ri…" — its name(s) never co-occur with the claim's key phrases in the source

[23:31:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Rettersol (1985) and Ovessey (1960) have further delineated the bounda…" — its name(s) never co-occur with the claim's key phrases in the source

[23:31:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Walters (1955) offered a structural perspective on paranoid t…" — its name(s) never co-occur with the claim's key phrases in the source

[23:31:45] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 32/74 → 37/74 (3 chunked call(s), ≤12 names each; 6 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[23:31:45] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 70/74 in final bullets (missing: ['Jack', 'Ndtei', 'Rettersol', 'Walters']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[23:31:45] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[23:31:45] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 684s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 684s of the budget.

[23:31:45] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[23:31:45] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":82,"exec_chars":1875,"chapter_done":true}

[23:31:45] [DEBUG]   📊 Progress: 1/1 done | 82 bullets | 1,875 chars exec summary

[23:31:45] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\checkpoints

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1919' (ce:1919) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923a' (ce:1923) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923' (ce:1923) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1919' (ce:1919) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1979' (ce:1979) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[23:31:46] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting: 8 source author(s) NOT found in the summary (Akhtar and Byrne, Bak, Frances and Widiger, Jack, Morey

[23:31:46] [INFO] 📄 Building DOCX report…

[23:31:46] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[23:31:46] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[23:31:46] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.5_20260926-231844-5f9b2053_summary.md + DOCX

[23:31:46] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[23:31:46] [INFO]   🧮 Embedding cache: 63 hits / 43 misses (59% hit-rate), 5000 entries

[23:31:46] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.5_20260926-231844-5f9b2053_summary.md

[23:31:46] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries

[23:31:46] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[23:31:46] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.5_20260926-231844-5f9b2053.summary.md

[23:31:46] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[23:31:46] [INFO]   ⏱️ DOCX phase starting | [781.8s]

[23:31:46] [INFO] 📄 Building DOCX report…

[23:31:46] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[23:31:46] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[23:31:48] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[23:31:50] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[23:33:38] [INFO]   🎯 K1+Classification: 82 bullets — 17 core, 35 supporting, 30 additional

[23:33:38] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[23:33:38] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[23:33:38] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[23:33:38] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[23:33:38] [INFO]   📊 Citation graph: no citations found in the text.

[23:33:38] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[23:33:38] [SUCCESS] ✅ Conversion complete.

[23:33:52] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\logs\quality_report.json

[23:33:52] [INFO] 

[23:33:52] [INFO] ━━━ Thermal Safety Report ━━━

[23:33:52] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[23:33:52] [INFO]   Session duration: 13.5 min

[23:33:52] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[23:33:52] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[23:33:52] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:33:52] [INFO] 

[23:33:52] [INFO] ━━━ Elixir v0.5.5 Conversion Diagnostic Summary ━━━

[23:33:52] [INFO]   Book: Broken Structures Salman Akhtar

[23:33:52] [INFO]   Total pages: 397

[23:33:52] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[23:33:52] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[23:33:52] [INFO]   Summaries generated: 1

[23:33:52] [INFO]     Success: 1, Failed: 0, Total bullets: 82

[23:33:52] [INFO]     Coverage: 94%

[23:33:52] [INFO]     Recall floor (deterministic, final set): theorists 70/74 (95%), conclusion items 3/3 (100%)

[23:33:52] [INFO]   Warnings: 0

[23:33:52] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar

[23:33:52] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.5_20260926-231844-5f9b2053.conversion.log.md

[23:33:52] [INFO]   Diagnostic JSONL: None

[23:33:52] [INFO]   Summary files (3):

[23:33:52] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.5_20260926-231844-5f9b2053_summary.md — generated-by v0.5.5 | run_id=20260926-231844-5f9b2053 | started=2026-09-26T23:20:21 | bullets=82

[23:33:52] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.5 | run_id=20260926-231844-5f9b2053 | started=2026-09-26T23:20:21 | bullets=82

[23:33:52] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.5_20260926-231844-5f9b2053.summary.md — generated-by v0.5.5 | run_id=20260926-231844-5f9b2053 | started=2026-09-26T23:20:21 | bullets=82

[23:33:52] [INFO]   Models loaded at exit: (none — all unloaded)

[23:33:52] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[23:33:52] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[23:33:52] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[23:33:52] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[23:33:52] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[23:33:52] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[23:33:52] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[23:33:52] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\images

[23:33:52] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[23:33:58] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\images

[23:34:03] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[23:34:03] [INFO]   [pipeline] after de-dup: 2 regions

[23:34:03] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\v5.5\Broken Structures Salman Akhtar\regions

[23:34:03] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[23:34:03] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 82 keypoints)


---
Finished at: 2026-09-26T23:34:03.920719
