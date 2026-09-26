# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T05:29:47.622442

<!-- generated-by: Elixir v0.4.38 | run_id=20260926-052947-3aafaf9b -->

---

[05:29:47] [SUCCESS] 🚀 Starting conversion…

[05:29:47] [DEBUG]   🔍 importing 'pypdf'…

[05:29:47] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[05:29:47] [DEBUG]   🔍 importing 'pdf2image'…

[05:29:47] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[05:29:47] [DEBUG]   🔍 importing 'tiktoken'…

[05:29:47] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[05:29:47] [DEBUG]   🔍 importing 'markitdown'…

[05:29:49] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[05:29:49] [DEBUG]   🔍 importing 'rapidfuzz'…

[05:29:49] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[05:29:49] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[05:29:49] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[05:29:49] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[05:29:49] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[05:29:49] [DEBUG]   🔍 importing 'torch'…

[05:29:49] [DEBUG]   ✅ 'torch' ok (0.0s)

[05:29:49] [DEBUG]   🔍 importing 'transformers'…

[05:30:03] [DEBUG]   ✅ 'transformers' ok (13.7s)

[05:30:03] [DEBUG]   🔍 importing 'langextract'…

[05:30:03] [DEBUG]   ✅ 'langextract' ok (0.1s)

[05:30:03] [DEBUG]   ✅ Pre-flight dependency check passed

[05:30:03] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[05:30:03] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[05:30:03] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar.pdf

[05:30:03] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar

[05:30:03] [INFO]   Source type: normal_book

[05:30:03] [INFO]   App version: 0.4.38

[05:30:03] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[05:30:03] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[05:30:03] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[05:30:03] [INFO]   Ollama reachable (localhost:11434): True

[05:30:03] [INFO]   Provider: llamacpp

[05:30:03] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[05:30:03] [INFO]   [Phase 1 (Extraction)]

[05:30:03] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[05:30:03] [INFO]   [Phase 2 (Summarization)]

[05:30:03] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[05:30:03] [INFO]   ────────────────────────────────────────

[05:30:03] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[05:30:03] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[05:30:03] [INFO] ━━━━━━━━━━━━━━━━━━━━

[05:30:03] [INFO]   LLM OCR: True, Force OCR all: False

[05:30:03] [INFO]   Auto-detect scanned: True

[05:30:03] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[05:30:03] [INFO]   OCR retries: 2, Image max size: 1200

[05:30:03] [INFO]   Page range: all

[05:30:03] [INFO]   Selected chapters: 1 chapter(s)

[05:30:03] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[05:30:03] [INFO]   Segmentation: auto, Token limit: 2000

[05:30:03] [INFO]   Semantic: True, Page group: 10

[05:30:03] [INFO]   Generate summaries: True

[05:30:03] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[05:30:03] [INFO]   Fast model: , Heavy model: (disabled)

[05:30:03] [INFO]   Workers (requested): 1, Temperature: 0.7

[05:30:03] [INFO]   Self-consistency: False, Coverage threshold: 85%

[05:30:03] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[05:30:03] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[05:30:03] [INFO]   Academic rigor: False

[05:30:03] [INFO]   Max context tokens: 128000

[05:30:03] [INFO]   Max output tokens: 32768

[05:30:03] [INFO]   Keep-alive: 30m

[05:30:03] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[05:30:03] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[05:30:03] [INFO]   Translation: disabled

[05:30:03] [INFO]   Clean markdown: True, Token saver: True

[05:30:03] [INFO]   Content filter: True

[05:30:03] [INFO]   Extract tables: False, Math: False, Figures: False

[05:30:03] [INFO]   Visual-region crops: True

[05:30:03] [INFO]   Layout analysis: False

[05:30:03] [INFO]   DOCX author: Elixir, TOC: True

[05:30:03] [INFO]   Output paths (V7.5 subfolders):

[05:30:03] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[05:30:03] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[05:30:03] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[05:30:03] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\packets

[05:30:03] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\podcast

[05:30:03] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\logs\quality_report.json

[05:30:03] [INFO]   Resume mode: enabled — will skip done chapters

[05:30:03] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[05:30:03] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[05:30:03] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[05:30:03] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[05:30:03] [DEBUG]   💾 Disk space: 21.5 GB free

[05:30:03] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\.checkpoint.json

[05:31:02] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[05:31:02] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[05:31:02] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[05:31:03] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[05:31:03] [INFO] [TOC] Using PDF outlines: 22 entries.

[05:31:03] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[05:31:03] [DEBUG]   [TOC] Entries passed to segmenter: 22

[05:31:03] [DEBUG]   [TOC] - p.7: Table of Contents

[05:31:03] [DEBUG]   [TOC] - p.9: FOREWORD

[05:31:03] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[05:31:03] [DEBUG]   [TOC] … and 19 more

[05:31:03] [INFO]   🎯 User selected 1 chapter(s):

[05:31:03] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[05:31:03] [INFO]   📸 front_cover → front_cover.jpg

[05:31:03] [INFO]   📸 back_cover → back_cover.jpg

[05:31:03] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[05:31:03] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[05:31:03] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[05:31:03] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[05:31:03] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[05:31:04] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[05:31:04] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[05:31:04] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[05:31:04] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[05:31:04] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[05:31:05] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[05:31:05] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[05:31:05] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[05:31:05] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[05:31:05] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[05:31:06] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[05:31:06] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[05:31:06] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[05:31:06] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[05:31:06] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[05:31:07] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[05:31:07] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[05:31:07] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[05:31:07] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[05:31:07] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[05:31:08] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[05:31:08] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[05:31:08] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[05:31:08] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[05:31:08] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[05:31:08] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[05:31:08] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[05:31:08] [INFO]   ✅ markitdown ready for digital-page extraction

[05:31:08] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[05:31:08] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[05:31:08] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[05:31:08] [INFO]      Pages needing OCR: [152, 153, 154]

[05:31:08] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[05:31:08] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[05:31:08] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[05:31:10] [INFO]   📄 140/397 pages processed (35%)

[05:31:17] [INFO]   🔍 OCR  page 152/397 (scanned)…

[05:31:19] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[05:32:45] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[05:32:45] [INFO]   🔍 OCR  page 153/397 (scanned)…

[05:34:09] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[05:34:09] [INFO]   🔍 OCR  page 154/397 (scanned)…

[05:35:35] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[05:35:38] [INFO]   📄 160/397 pages processed (40%)

[05:35:38] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[05:35:38] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[05:35:38] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[05:35:38] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[05:35:38] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[05:35:38] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[05:35:38] [INFO] 📝 Raw markdown: 53,157 chars | [350.5s]

[05:35:38] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[05:35:38] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[05:35:38] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[05:35:38] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[05:35:38] [INFO] [Segmenter] Attempting chapter-level segmentation…

[05:35:38] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[05:35:38] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[05:35:38] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[05:35:38] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[05:35:38] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[05:35:38] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[05:35:38] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[05:35:38] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[05:35:38] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[05:35:38] [INFO]   📑 Filtered segments: kept 1 of 17

[05:35:38] [INFO] 📚 1 segment(s) detected | [350.6s]

[05:35:38] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[05:35:38] [INFO] 🌐 Detected language: en

[05:35:38] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[05:35:38] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[05:35:38] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\markdown\chapters

[05:35:38] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[05:35:38] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\markdown\chapters

[05:35:38] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[05:35:38] [INFO]   ⏱️ Summary phase starting | [350.9s]

[05:35:40] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[05:35:40] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[05:35:40] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[05:35:40] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[05:35:40] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[05:35:40] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[05:35:40] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[05:35:40] [INFO]   🌡️ Pre-flight: idle GPU temp = 58°C

[05:35:40] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 58°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[05:35:40] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[05:35:40] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[05:35:40] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[05:35:40] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[05:35:40] [DEBUG]   🎛️ Model profile: Default

[05:35:40] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[05:35:40] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[05:35:40] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[05:35:40] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[05:35:40] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[05:35:40] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[05:35:40] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[05:35:40] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[05:35:40] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[05:35:40] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[05:35:40] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[05:35:40] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[05:35:40] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[05:35:40] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[05:35:40] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[05:35:40] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[05:35:40] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[05:35:40] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[05:35:40] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[05:35:40] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[05:35:40] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[05:35:41] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\438

[05:35:41] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[05:35:41] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[05:35:41] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[05:35:41] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[05:35:41] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[05:35:41] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[05:35:41] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[05:35:41] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[05:35:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:35:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[05:36:57] [INFO]     ✅ V0.3 Call 1/3: master summary = 696 words, 5465 chars

[05:36:57] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[05:36:57] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:36:57] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[05:37:36] [INFO]     ✅ V0.3 Call 2/3: 31 bullets derived from master summary

[05:37:36] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[05:37:36] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:37:36] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[05:38:01] [INFO]     ✅ V0.3 Call 3/3: exec summary = 325 words

[05:38:01] [DEBUG]     📝 Parsed: exec=2659 chars, bullets=31, thorough=5465 chars

[05:38:21] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[05:38:22] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[05:38:22] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (31 bullets, 325 exec words, 696 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[05:38:23] [DEBUG]     🔍 Fact-check: all 31 bullets verified ✓

[05:38:23] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[05:38:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:38:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[05:39:12] [INFO]     ✅ Additive sections via followup call: key_distinctions=1608 chars, theoretical_tensions=1298 chars

[05:39:12] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (31 bullets, 325 exec words, 696 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[05:39:12] [WARNING]     ⚠️ thorough_summary too short (696 words < 800 threshold) — requesting dedicated expansion…

[05:39:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[05:39:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[05:40:18] [INFO]     📖 Attempt 1/3: dedicated thorough = 696 words

[05:40:18] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[05:40:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[05:40:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[05:41:06] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying at temperature 0.0 (greedy)

[05:41:06] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.00) via llm_provider.llamacpp…

[05:41:06] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.00 max=8192 streaming…

[05:41:51] [DEBUG]     📏 V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 696 < 800 min words)

[05:41:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[05:41:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[05:42:36] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=696) — keeping best-effort result

[05:42:36] [DEBUG]     ℹ️ Dedicated thorough call returned 696 words (not longer than original 696) — keeping original

[05:42:36] [INFO]     V0.05: Skipping bullet expansion — 31 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[05:42:36] [INFO]     ✅ Final coverage 100%

[05:42:36] [DEBUG]     📏 F1: exec=325w, thorough=696w (source=7405w; targets exec<=250w, thorough<=3332w)

[05:44:22] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[05:44:22] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.3 (diff: -4.0)

[05:44:22] [INFO]     ℹ️ F3: Summary is 4.0 grade levels denser than source — expected for a compressed academic summary.

[05:44:24] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[05:44:24] [DEBUG]     🔄 J2: 23 cross-section redundancy(ies) found (exec↔bullets: 7, bullets↔thorough: 16)

[05:44:24] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 7 markers)

[05:44:24] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[05:44:24] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[05:44:24] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[05:44:42] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 3696 per-pair calls)

[05:44:42] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[05:44:43] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (31/31 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[05:44:43] [INFO]   ℹ️ Summary has substantial content (exec=2659 chars, thorough=5461 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[05:44:43] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[05:44:43] [WARNING]   ⏱️⚠️ Deadline exceeded (543s > 480s) — skipping optional phase: scholar reflection

[05:44:43] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[05:44:43] [INFO]     🛡️ Anti-false-precision: rewrote 'Rycroft (1960) proposed that paranoid rage serves to recreat…' → 'Rycroft and Cameron both proposed that paranoid rage serves …' (source groups Rycroft + Cameron)

[05:44:43] [INFO]     🛡️ Anti-false-precision: rewrote 1 claim(s) that invented distinctions between authors the source groups together

[05:44:43] [WARNING]   ⏱️⚠️ Deadline exceeded (543s > 480s) — skipping optional phase: semantic dedup

[05:44:43] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[05:44:43] [DEBUG]     🧹 V16.0.2 Bullet normalization: 31 bullets normalized

[05:44:43] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[05:44:43] [WARNING]   ⏱️⚠️ Deadline exceeded (543s > 480s) — skipping optional phase: bullet consolidation

[05:44:43] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[05:44:43] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\438

[05:44:43] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[05:44:43] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[05:44:43] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Leonhard', 'Shepherd', 'Klein', 'Winnicott', 'Erikson', 'Bursten']/74 authors in bullets (27%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[05:44:43] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Leonhard', 'Shepherd', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Gorton and Akhtar']/74 authors in thorough (28%) — MISSING from thorough: ['Shapiro', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[05:44:43] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']…

[05:44:43] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:44:43] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[05:45:00] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne: Co-described the behavioral correlates of splitting (…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[05:45:00] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[05:45:00] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (16.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[05:45:00] [DEBUG]     📊 V18.14.1: After round 1, 42 still missing from bullets: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[05:45:00] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[05:45:00] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:45:00] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[05:45:12] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) offered a textbook description of paranoid p…

[05:45:12] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[05:45:12] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (12.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[05:45:12] [DEBUG]     📊 V18.14.1: After round 2, 33 still missing from bullets: ['Winokur', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[05:45:12] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Winokur', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[05:45:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:45:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[05:45:30] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1975) is cited alongside Croewe in the source as an example o…

[05:45:30] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is listed amon…

[05:45:30] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is included in a list …

[05:45:30] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 5/8 bullets

[05:45:30] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (17.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[05:45:30] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[05:45:30] [DEBUG]     📊 V18.14.1: After round 3, 28 still missing from bullets: ['Winokur', 'Anthony', 'Kohut', 'Bergman', 'Allodi']…

[05:45:30] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Winokur', 'Anthony', 'Kohut', 'Bergman', 'Allodi']… (mention-only: ['Winokur'])

[05:45:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:45:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[05:45:44] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) are cited in the source as an example of a t…

[05:45:44] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Allodi (1982) is cited regarding the reactive or acute development of …

[05:45:44] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited regarding the differentiation between the reactiv…

[05:45:44] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is cited regarding the observation that reactive or acute…

[05:45:44] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets

[05:45:44] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (13.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[05:45:44] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Winokur' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[05:45:44] [DEBUG]     📊 V18.14.1: After round 4, 24 still missing from bullets: ['Winokur', 'Allodi', 'Jack', 'Ndtei', 'Pao']…

[05:45:44] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Allodi', 'Jack', 'Ndtei', 'Pao', 'Socarides']…

[05:45:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:45:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[05:45:54] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work is cited regarding morbid jealousy.…

[05:45:54] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view is cited on the affect of vengeance.…

[05:45:54] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[05:45:54] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (10.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[05:45:54] [DEBUG]     📊 V18.14.1: After round 5, 15 still missing from bullets: ['Winokur', 'Pao', 'Socarides', 'Wurmser', 'Conlon']…

[05:45:54] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 29 bullets across 5 round(s)

[05:45:54] [WARNING]     ⚠️ V18.14.1: 15 theorists still missing from bullets after gap-fill: ['Winokur', 'Pao', 'Socarides', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Croewe'] — of these, 1 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Winokur'] — 14 never covered (round cap/deadline): ['Pao', 'Socarides', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Croewe', 'Grunberger']

[05:45:54] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[05:45:54] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (4 item(s) were uncovered; all 9 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[05:45:54] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[05:45:54] [DEBUG]     🧹 Semantic dedup: removing bullet 38 (sim=0.95 with bullet 34)

[05:45:54] [DEBUG]     🧹 Semantic dedup: removing bullet 53 (sim=0.89 with bullet 30)

[05:45:54] [DEBUG]     🧹 Semantic dedup: removing bullet 57 (sim=0.88 with bullet 55)

[05:45:54] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.85 with bullet 43)

[05:45:54] [DEBUG]     🧹 Semantic dedup: removing bullet 68 (sim=0.87 with bullet 21)

[05:45:54] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 68 → 63 bullets (removed 5 gap-fill/conclusion duplicates; 0.7s, non-skippable per V18.20.3.4)

[05:45:54] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\438

[05:45:54] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[05:45:54] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[05:45:57] [INFO]     ℹ️ V0.4.23: 62 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[05:45:57] [INFO]     🛡️ V18.2.13 Post-checks: 14 fixed, 7 flagged (of 62 bullets + exec + thorough)

[05:45:57] [DEBUG]       [space/fix] bullet[35]: split 'review' -> 're view' (source-validated)  |  Frances: Co-authored a 1985 review with Widiger that paid …

[05:45:57] [DEBUG]       [dropped_letter/flag] bullet[38]: likely garbled token: 'paranoias' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …t the confidence and pride of paranoias cloak a hollow shell…

[05:45:57] [DEBUG]       [truncated/flag] bullet[60]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[05:45:57] [DEBUG]       [truncated/flag] bullet[62]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[05:45:57] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'betrayale of' — 'betrayal' is a known word but 'betrayale' is not. The 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …arly trauma and guard against betrayale of biased clue-seeki…

[05:45:57] [DEBUG]       [dropped_letter/flag] thorough: likely garbled token: 'betrayale' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'betrayal' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …arly trauma and guard against betrayale of biased clue-seeki…

[05:45:57] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 38% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …f inadequacy and entitlement; Jaspers (1949), whose descript…

[05:45:57] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bursten (1973a)' has 39% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ontemporary contributors like Bursten (1973a), Kernberg (197…

[05:45:57] [DEBUG]       [quote_verification/fix] bullet[21]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (arrogance, hypervigilance, moralistic indi

[05:45:57] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality, which is defined by a paradoxical coexistence 

[05:45:57] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Blum’s concept of the 

[05:45:57] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., arrogance) and 

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality as an individual who is always on the alert for

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   highlighted overcompensation through formality; Schneider (

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ; and Leonhard (1959) and Shepherd (1961), who detailed the 

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a developmental substrate involving projection of aggres

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to explain the paranoid individual’s desperate attempt to p

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics—such as arrogance, hypervigilance, and mora

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   ones—such as timidity, gullibility, and vulnerability to er

[05:45:57] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   or paranoia (which involves encapsulated delusions). The au

[05:45:57] [DEBUG]       [near_duplicate/fix] bullet[53]: near-duplicate of bullet[52] (token-set containment >= 0.8) — kept the first, dropped this one  |  Jack (1984) contributed to the literature on the reactive or

[05:45:57] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 21/74 authors in thorough — MISSING from thorough: ['Shapiro', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[05:45:57] [WARNING]   ⏱️⚠️ Deadline exceeded (616s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[05:45:57] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 53 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[05:45:57] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:45:57] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jacobson (1971) traced the disorder to family environments marked by o…" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Volkan (1986) offered insights into man’s need for enemies and allies,…" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Akhtar and Thomson (1982) provided a parallel phenomenol…" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the section addressing DSM criteria and diagnostic limitations, the…" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In discussing the potential relationship between paranoid personality …" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:40] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, the chapter acknowledges that while major reviews by Widiger …" — its name(s) never co-occur with the claim's key phrases in the source

[05:46:53] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:46:53] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[05:47:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the paranoid adolescent, highlighting early …" — its name(s) never co-occur with the claim's key phrases in the source

[05:47:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, the chapter references the work of Mahler (1975) on sepa…" — its name(s) never co-occur with the claim's key phrases in the source

[05:47:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Bak (1946) is cited in agreement with Freud regarding the gra…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[05:48:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Fenichel and Bergman are cited in the context of early psychoanalytic …" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi’s work is referenced in relation to the clinical observation of…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack’s contributions are noted in connection with the study of defensi…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei’s work addresses the developmental and relational dimensions of …" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater’s observations on the contradictory nature of paranoid pride an…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green’s essay on moral narcissism is referenced as indirectly bearing …" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao’s 1969 work on morbid jealousy further elaborates on the sexual vu…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler (1987) critically evaluated the DSM-III criteria, p…" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Frances and Widiger are mentioned in two contexts: first, as …" — its name(s) never co-occur with the claim's key phrases in the source

[05:48:57] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 21/74 → 29/74 (3 chunked call(s), ≤12 names each; 17 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[05:48:57] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[05:48:57] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 1 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[05:48:57] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 55/74 in final bullets (missing: ['Winokur', 'Bergman', 'Jack', 'Ndtei', 'Pao']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[05:48:57] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 797s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 797s of the budget.

[05:48:57] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[05:48:57] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":63,"exec_chars":2653,"chapter_done":true}

[05:48:57] [DEBUG]   📊 Progress: 1/1 done | 63 bullets | 2,653 chars exec summary

[05:48:57] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\checkpoints

[05:48:57] [INFO] 📄 Building DOCX report…

[05:48:57] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[05:48:57] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[05:48:57] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.38_20260926-052947-3aafaf9b_summary.md + DOCX

[05:48:57] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[05:48:57] [INFO]   🧮 Embedding cache: 64 hits / 32 misses (67% hit-rate), 5000 entries

[05:48:57] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.38_20260926-052947-3aafaf9b_summary.md

[05:48:57] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries

[05:48:57] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[05:48:57] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.38_20260926-052947-3aafaf9b.summary.md

[05:48:57] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[05:48:57] [INFO]   ⏱️ DOCX phase starting | [1150.3s]

[05:48:57] [INFO] 📄 Building DOCX report…

[05:48:57] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[05:48:58] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[05:49:00] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[05:49:01] [INFO]   🧹 Keypoints dedup: removed 1 duplicate(s) (63 → 62 keypoints)

[05:49:01] [DEBUG]   🗑️ '**To this composite profile (Table 6-1),** — 6 items from th...' (embedding sim > 0.85)

[05:49:01] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[05:50:35] [INFO]   🎯 K1+Classification: 62 bullets — 16 core, 28 supporting, 18 additional

[05:50:35] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[05:50:35] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[05:50:35] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[05:50:35] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[05:50:35] [INFO]   📊 Citation graph: no citations found in the text.

[05:50:35] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[05:50:35] [SUCCESS] ✅ Conversion complete.

[05:50:53] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\logs\quality_report.json

[05:50:53] [INFO] 

[05:50:53] [INFO] ━━━ Thermal Safety Report ━━━

[05:50:53] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[05:50:53] [INFO]   Session duration: 15.2 min

[05:50:53] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[05:50:53] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[05:50:53] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[05:50:53] [INFO] 

[05:50:53] [INFO] ━━━ Elixir v0.4.38 Conversion Diagnostic Summary ━━━

[05:50:53] [INFO]   Book: Broken Structures Salman Akhtar

[05:50:53] [INFO]   Total pages: 397

[05:50:53] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[05:50:53] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[05:50:53] [INFO]   Summaries generated: 1

[05:50:53] [INFO]     Success: 1, Failed: 0, Total bullets: 63

[05:50:53] [INFO]     Coverage: 94%

[05:50:53] [INFO]     Recall floor (deterministic, final set): theorists 55/74 (74%), conclusion items 3/3 (100%)

[05:50:53] [INFO]   Warnings: 0

[05:50:53] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar

[05:50:53] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.38_20260926-052947-3aafaf9b.conversion.log.md

[05:50:53] [INFO]   Diagnostic JSONL: None

[05:50:53] [INFO]   Summary files (3):

[05:50:53] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.38_20260926-052947-3aafaf9b_summary.md — generated-by v0.4.38 | run_id=20260926-052947-3aafaf9b | started=2026-09-26T05:35:40 | bullets=63

[05:50:53] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.38 | run_id=20260926-052947-3aafaf9b | started=2026-09-26T05:35:40 | bullets=63

[05:50:53] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.38_20260926-052947-3aafaf9b.summary.md — generated-by v0.4.38 | run_id=20260926-052947-3aafaf9b | started=2026-09-26T05:35:40 | bullets=63

[05:50:53] [INFO]   Models loaded at exit: (none — all unloaded)

[05:50:53] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[05:50:53] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[05:50:53] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[05:50:53] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[05:50:53] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[05:50:54] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[05:50:54] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[05:50:54] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\images

[05:50:54] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[05:51:01] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\images

[05:51:08] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[05:51:08] [INFO]   [pipeline] after de-dup: 2 regions

[05:51:09] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\438\Broken Structures Salman Akhtar\regions

[05:51:09] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[05:51:09] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 62 keypoints)


---
Finished at: 2026-09-26T05:51:09.260990
