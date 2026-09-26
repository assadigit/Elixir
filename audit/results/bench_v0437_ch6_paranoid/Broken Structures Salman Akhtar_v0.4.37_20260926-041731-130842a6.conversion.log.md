# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T04:17:31.240879

<!-- generated-by: Elixir v0.4.37 | run_id=20260926-041731-130842a6 -->

---

[04:17:31] [SUCCESS] 🚀 Starting conversion…

[04:17:31] [DEBUG]   🔍 importing 'pypdf'…

[04:17:31] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[04:17:31] [DEBUG]   🔍 importing 'pdf2image'…

[04:17:31] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[04:17:31] [DEBUG]   🔍 importing 'tiktoken'…

[04:17:31] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[04:17:31] [DEBUG]   🔍 importing 'markitdown'…

[04:17:33] [DEBUG]   ✅ 'markitdown' ok (2.1s)

[04:17:33] [DEBUG]   🔍 importing 'rapidfuzz'…

[04:17:33] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[04:17:33] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[04:17:33] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[04:17:33] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[04:17:33] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[04:17:33] [DEBUG]   🔍 importing 'torch'…

[04:17:33] [DEBUG]   ✅ 'torch' ok (0.0s)

[04:17:33] [DEBUG]   🔍 importing 'transformers'…

[04:17:47] [DEBUG]   ✅ 'transformers' ok (14.1s)

[04:17:47] [DEBUG]   🔍 importing 'langextract'…

[04:17:47] [DEBUG]   ✅ 'langextract' ok (0.1s)

[04:17:47] [DEBUG]   ✅ Pre-flight dependency check passed

[04:17:47] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[04:17:47] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[04:17:47] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar.pdf

[04:17:47] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar

[04:17:47] [INFO]   Source type: normal_book

[04:17:47] [INFO]   App version: 0.4.37

[04:17:47] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[04:17:47] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[04:17:47] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[04:17:47] [INFO]   Ollama reachable (localhost:11434): True

[04:17:47] [INFO]   Provider: llamacpp

[04:17:47] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[04:17:47] [INFO]   [Phase 1 (Extraction)]

[04:17:47] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[04:17:47] [INFO]   [Phase 2 (Summarization)]

[04:17:47] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[04:17:47] [INFO]   ────────────────────────────────────────

[04:17:47] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[04:17:47] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[04:17:47] [INFO] ━━━━━━━━━━━━━━━━━━━━

[04:17:47] [INFO]   LLM OCR: True, Force OCR all: False

[04:17:47] [INFO]   Auto-detect scanned: True

[04:17:47] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[04:17:47] [INFO]   OCR retries: 2, Image max size: 1200

[04:17:47] [INFO]   Page range: all

[04:17:47] [INFO]   Selected chapters: 1 chapter(s)

[04:17:47] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[04:17:47] [INFO]   Segmentation: auto, Token limit: 2000

[04:17:47] [INFO]   Semantic: True, Page group: 10

[04:17:47] [INFO]   Generate summaries: True

[04:17:47] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[04:17:47] [INFO]   Fast model: , Heavy model: (disabled)

[04:17:47] [INFO]   Workers (requested): 1, Temperature: 0.7

[04:17:47] [INFO]   Self-consistency: False, Coverage threshold: 85%

[04:17:47] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[04:17:47] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[04:17:47] [INFO]   Academic rigor: False

[04:17:47] [INFO]   Max context tokens: 128000

[04:17:47] [INFO]   Max output tokens: 32768

[04:17:47] [INFO]   Keep-alive: 30m

[04:17:47] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[04:17:47] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[04:17:47] [INFO]   Translation: disabled

[04:17:47] [INFO]   Clean markdown: True, Token saver: True

[04:17:47] [INFO]   Content filter: True

[04:17:47] [INFO]   Extract tables: False, Math: False, Figures: False

[04:17:47] [INFO]   Visual-region crops: True

[04:17:47] [INFO]   Layout analysis: False

[04:17:47] [INFO]   DOCX author: Elixir, TOC: True

[04:17:47] [INFO]   Output paths (V7.5 subfolders):

[04:17:47] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[04:17:47] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[04:17:47] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[04:17:47] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\packets

[04:17:47] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\podcast

[04:17:47] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\logs\quality_report.json

[04:17:47] [INFO]   Resume mode: enabled — will skip done chapters

[04:17:47] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[04:17:47] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[04:17:47] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[04:17:47] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[04:17:47] [DEBUG]   💾 Disk space: 24.8 GB free

[04:17:47] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\.checkpoint.json

[04:19:03] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[04:19:03] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[04:19:03] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[04:19:03] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[04:19:03] [INFO] [TOC] Using PDF outlines: 22 entries.

[04:19:03] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[04:19:03] [DEBUG]   [TOC] Entries passed to segmenter: 22

[04:19:03] [DEBUG]   [TOC] - p.7: Table of Contents

[04:19:03] [DEBUG]   [TOC] - p.9: FOREWORD

[04:19:03] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[04:19:03] [DEBUG]   [TOC] … and 19 more

[04:19:03] [INFO]   🎯 User selected 1 chapter(s):

[04:19:03] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[04:19:04] [INFO]   📸 front_cover → front_cover.jpg

[04:19:04] [INFO]   📸 back_cover → back_cover.jpg

[04:19:04] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[04:19:04] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[04:19:04] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[04:19:04] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[04:19:04] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[04:19:05] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[04:19:05] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[04:19:05] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[04:19:05] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[04:19:05] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[04:19:06] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[04:19:06] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[04:19:06] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[04:19:06] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[04:19:06] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[04:19:06] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[04:19:07] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[04:19:07] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[04:19:07] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[04:19:07] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[04:19:08] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[04:19:08] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[04:19:08] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[04:19:08] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[04:19:08] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[04:19:09] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[04:19:09] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[04:19:09] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[04:19:09] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[04:19:09] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[04:19:09] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[04:19:09] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[04:19:09] [INFO]   ✅ markitdown ready for digital-page extraction

[04:19:09] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[04:19:09] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[04:19:09] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[04:19:09] [INFO]      Pages needing OCR: [152, 153, 154]

[04:19:09] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[04:19:09] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[04:19:09] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[04:19:12] [INFO]   📄 140/397 pages processed (35%)

[04:19:18] [INFO]   🔍 OCR  page 152/397 (scanned)…

[04:19:20] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[04:20:30] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[04:20:30] [INFO]   🔍 OCR  page 153/397 (scanned)…

[04:21:35] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[04:21:35] [INFO]   🔍 OCR  page 154/397 (scanned)…

[04:22:49] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[04:22:53] [INFO]   📄 160/397 pages processed (40%)

[04:22:53] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[04:22:53] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[04:22:53] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[04:22:53] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[04:22:53] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[04:22:53] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[04:22:53] [INFO] 📝 Raw markdown: 53,157 chars | [321.9s]

[04:22:53] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[04:22:53] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[04:22:53] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[04:22:53] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[04:22:53] [INFO] [Segmenter] Attempting chapter-level segmentation…

[04:22:53] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[04:22:53] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[04:22:53] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[04:22:53] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[04:22:53] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[04:22:53] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[04:22:53] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[04:22:53] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[04:22:53] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[04:22:53] [INFO]   📑 Filtered segments: kept 1 of 17

[04:22:53] [INFO] 📚 1 segment(s) detected | [322.0s]

[04:22:53] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[04:22:53] [INFO] 🌐 Detected language: en

[04:22:53] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[04:22:53] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[04:22:53] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\markdown\chapters

[04:22:53] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[04:22:53] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\markdown\chapters

[04:22:53] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[04:22:53] [INFO]   ⏱️ Summary phase starting | [322.5s]

[04:22:55] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[04:22:55] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[04:22:55] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[04:22:55] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[04:22:55] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[04:22:55] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[04:22:55] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[04:22:55] [INFO]   🌡️ Pre-flight: idle GPU temp = 60°C

[04:22:55] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 60°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[04:22:55] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[04:22:55] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[04:22:55] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[04:22:55] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[04:22:55] [DEBUG]   🎛️ Model profile: Default

[04:22:55] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[04:22:56] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[04:22:56] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[04:22:56] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[04:22:56] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[04:22:56] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[04:22:56] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[04:22:56] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[04:22:56] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[04:22:56] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[04:22:56] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[04:22:56] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[04:22:56] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[04:22:56] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[04:22:56] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[04:22:56] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[04:22:56] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[04:22:56] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[04:22:56] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[04:22:56] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[04:22:56] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[04:22:56] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\437

[04:22:56] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[04:22:56] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[04:22:56] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[04:22:56] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[04:22:56] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[04:22:56] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[04:22:56] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[04:22:56] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[04:22:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:22:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[04:24:20] [INFO]     ✅ V0.3 Call 1/3: master summary = 793 words, 6050 chars

[04:24:20] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[04:24:20] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:24:20] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[04:24:58] [INFO]     ✅ V0.3 Call 2/3: 30 bullets derived from master summary

[04:24:58] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[04:24:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:24:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[04:25:17] [INFO]     ✅ V0.3 Call 3/3: exec summary = 241 words

[04:25:17] [DEBUG]     📝 Parsed: exec=1958 chars, bullets=30, thorough=6050 chars

[04:25:42] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[04:25:43] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[04:25:43] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee

[04:25:43] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (30 bullets, 241 exec words, 793 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[04:25:45] [DEBUG]     🔍 Fact-check: all 30 bullets verified ✓

[04:25:45] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[04:25:45] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:25:45] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[04:26:40] [INFO]     ✅ Additive sections via followup call: key_distinctions=2044 chars, theoretical_tensions=1429 chars

[04:26:40] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (30 bullets, 241 exec words, 793 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[04:26:40] [WARNING]     ⚠️ thorough_summary too short (793 words < 800 threshold) — requesting dedicated expansion…

[04:26:40] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[04:26:40] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[04:28:02] [INFO]     📖 Attempt 1/3: dedicated thorough = 789 words

[04:28:02] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[04:28:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[04:28:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[04:29:03] [INFO]     📖 Attempt 2/3: dedicated thorough = 793 words

[04:29:03] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying at temperature 0.0 (greedy)

[04:29:03] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.00) via llm_provider.llamacpp…

[04:29:03] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.00 max=8192 streaming…

[04:30:01] [WARNING]     ℹ️ All 3 thorough attempts returned < 800 words (best=793) — keeping best-effort result

[04:30:01] [DEBUG]     ℹ️ Dedicated thorough call returned 793 words (not longer than original 793) — keeping original

[04:30:01] [INFO]     V0.05: Skipping bullet expansion — 30 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[04:30:01] [INFO]     ✅ Final coverage 92%

[04:30:01] [DEBUG]     📏 F1: exec=241w, thorough=793w (source=7405w; targets exec<=250w, thorough<=3332w)

[04:31:52] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[04:31:52] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 19.1 (diff: -2.8)

[04:31:52] [INFO]     ℹ️ F3: Summary is 2.8 grade levels denser than source — expected for a compressed academic summary.

[04:31:54] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[04:31:54] [DEBUG]     🔄 J2: 20 cross-section redundancy(ies) found (exec↔bullets: 6, bullets↔thorough: 13)

[04:31:54] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 4 markers)

[04:31:54] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[04:31:54] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[04:31:54] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[04:32:09] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3584 per-pair calls)

[04:32:09] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[04:32:12] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (30/30 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[04:32:12] [INFO]   ℹ️ Summary has substantial content (exec=1958 chars, thorough=6045 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[04:32:12] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[04:32:12] [WARNING]   ⏱️⚠️ Deadline exceeded (556s > 480s) — skipping optional phase: scholar reflection

[04:32:12] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[04:32:12] [INFO]     🛡️ Anti-false-precision: rewrote 'Bleuler (1908) identified a triad of suspiciousness, grandio…' → 'Bleuler and Kretschmer both identified a triad of suspicious…' (source groups Bleuler + Kretschmer)

[04:32:12] [INFO]     🛡️ Anti-false-precision: rewrote 1 claim(s) that invented distinctions between authors the source groups together

[04:32:12] [WARNING]   ⏱️⚠️ Deadline exceeded (556s > 480s) — skipping optional phase: semantic dedup

[04:32:12] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[04:32:12] [DEBUG]     🧹 V16.0.2 Bullet normalization: 30 bullets normalized

[04:32:12] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[04:32:12] [WARNING]   ⏱️⚠️ Deadline exceeded (556s > 480s) — skipping optional phase: bullet consolidation

[04:32:12] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[04:32:12] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\437

[04:32:12] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[04:32:12] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[04:32:12] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Rycroft', 'Magnan', 'Jaspers', 'Schneider', 'Klein', 'Winnicott', 'Erikson', 'Morey']/74 authors in bullets (19%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Stanton', 'Meissner', 'Thomson']

[04:32:12] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Morey', 'Ovessey', 'Walters']/74 authors in thorough (32%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[04:32:12] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Stanton', 'Meissner', 'Thomson']…

[04:32:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:32:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:32:34] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[04:32:34] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kretschmer: Emphasized the sensitive inner core of the paranoia-prone …

[04:32:34] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 6/8 bullets

[04:32:34] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (21.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=6

[04:32:34] [DEBUG]     📊 V18.14.1: After round 1, 52 still missing from bullets: ['Kernberg', 'Kretschmer', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[04:32:34] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Kretschmer', 'Frances', 'Byrne', 'Akhtar and Byrne']…

[04:32:34] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:32:34] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:32:50] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kretschmer (1927) emphasized the sensitive inner core of the paranoia-…

[04:32:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne (1983) described the behavioral correlates of splitti…

[04:32:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jacobson (1971) observed that paranoid individuals had frequently grow…

[04:32:51] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 4/8 bullets

[04:32:51] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (16.8s): response=7 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=4

[04:32:51] [INFO]     🔁 V18.20.3.7: 'Kretschmer' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[04:32:51] [DEBUG]     📊 V18.14.1: After round 2, 45 still missing from bullets: ['Kretschmer', 'Byrne', 'Akhtar and Byrne', 'Jacobson', 'Volkan']…

[04:32:51] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Kretschmer', 'Byrne', 'Akhtar and Byrne', 'Jacobson', 'Volkan']… (mention-only: ['Kretschmer'])

[04:32:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:32:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:33:05] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[04:33:05] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar (1984) described identity diffusion in relation to pa…' (source attributes this claim to 'Socarides’s', not 'Akhtar')

[04:33:05] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets

[04:33:05] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (14.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[04:33:05] [INFO]     🔁 V18.20.3.7: 'Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[04:33:05] [INFO]     🔁 V18.20.3.7: 'Akhtar and Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[04:33:05] [DEBUG]     📊 V18.14.1: After round 3, 38 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Shepherd', 'Polatin', 'Slater and Roth']…

[04:33:05] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Shepherd', 'Polatin', 'Slater and Roth']… (mention-only: ['Byrne', 'Akhtar and Byrne'])

[04:33:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:33:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:33:23] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 8/8 bullets

[04:33:23] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (17.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[04:33:23] [DEBUG]     📊 V18.14.1: After round 4, 28 still missing from bullets: ['Anthony', 'Kohut', 'Bach', 'Fenichel', 'Bergman']…

[04:33:23] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Anthony', 'Kohut', 'Bach', 'Fenichel', 'Bergman']…

[04:33:23] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:33:23] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:33:41] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 8/8 bullets

[04:33:41] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (18.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[04:33:41] [DEBUG]     📊 V18.14.1: After round 5, 20 still missing from bullets: ['Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler']…

[04:33:41] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 32 bullets across 5 round(s)

[04:33:41] [WARNING]     ⚠️ V18.14.1: 20 theorists still missing from bullets after gap-fill: ['Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser'] — 20 never covered (round cap/deadline): ['Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser']

[04:33:41] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[04:33:41] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (2 item(s) were uncovered; all 6 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (1 item(s) were uncovered; all 4 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[04:33:41] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[04:33:42] [DEBUG]     🧹 Semantic dedup: removing bullet 27 (sim=0.86 with bullet 24)

[04:33:42] [DEBUG]     🧹 Semantic dedup: removing bullet 61 (sim=0.87 with bullet 60)

[04:33:42] [DEBUG]     🧹 Semantic dedup: removing bullet 62 (sim=0.91 with bullet 60)

[04:33:42] [DEBUG]     🧹 Semantic dedup: removing bullet 66 (sim=0.91 with bullet 36)

[04:33:42] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 70 → 66 bullets (removed 4 gap-fill/conclusion duplicates; 0.9s, non-skippable per V18.20.3.4)

[04:33:42] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\437

[04:33:42] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[04:33:42] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[04:33:44] [INFO]     ℹ️ V0.4.23: 66 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[04:33:44] [INFO]     🛡️ V18.2.13 Post-checks: 2 fixed, 6 flagged (of 66 bullets + exec + thorough)

[04:33:44] [DEBUG]       [fragment_merge/flag] bullet[4]: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  A recurring theme in descriptive literatur…

[04:33:44] [DEBUG]       [dropped_letter/flag] bullet[38]: likely garbled token: 'paranoias' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …t the confidence and pride of paranoias cloak but a hollow s…

[04:33:44] [DEBUG]       [attribution/flag] bullet[59]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[04:33:44] [DEBUG]       [truncated/flag] bullet[63]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[04:33:44] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …hapter highlights a recurring theme in descriptive literatur…

[04:33:44] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bursten (1973a)' has 35% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …piro (1965), Jacobson (1971), Bursten (1973a), Kernberg (197…

[04:33:44] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 6 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid Personality Disorder vs. Paranoid Schizophrenia/D

[04:33:44] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Descriptive vs. Psychoanalytic Literature: The chapter exp

[04:33:44] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 24/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[04:33:44] [WARNING]   ⏱️⚠️ Deadline exceeded (649s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[04:33:44] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 50 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[04:33:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:33:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:34:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:34:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:35:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This view was supported by Mahler’s (1975) theory of separation-indivi…" — its name(s) never co-occur with the claim's key phrases in the source

[04:35:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Further contributions to this understanding came from Anthony (1981), …" — its name(s) never co-occur with the claim's key phrases in the source

[04:35:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter also highlights Bak’s (1946) perspective on the nature of …" — its name(s) never co-occur with the claim's key phrases in the source

[04:35:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Bach’s (1977) observation regarding the “mirror compleme…" — its name(s) never co-occur with the claim's key phrases in the source

[04:35:43] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:35:43] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bergman (1980) provided a detailed analysis of morbid jealousy as a di…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi (1975) offered insights into the cognitive style of paranoid in…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack (1980) focused on the affective dimension of paranoia, describing…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In addition to these contributors, Ndtei (1974) explored the developme…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater (1980) examined the relationship between paranoid personality d…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green (1975) provided a psychoanalytic perspective on moral narcissism…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1980) investigated the role of erotomania in paranoid personality…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Socarides (1974) analyzed the affective experience of vengeance in par…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler (1987) critically evaluated the diagnostic reliabil…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Frances and Widiger (1986) proposed a prototypal model for classifying…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:31] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Mackinnon and Michels (1975) contributed to the understanding…" — its name(s) never co-occur with the claim's key phrases in the source

[04:36:34] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 24/74 → 31/74 (3 chunked call(s), ≤12 names each; 14 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[04:36:34] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (1 item(s) were uncovered; all 4 now carried verbatim)

[04:36:34] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 1 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[04:36:34] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 52/74 in final bullets (missing: ['Jack', 'Ndtei', 'Bursten', 'Green', 'Pao']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[04:36:34] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 819s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 819s of the budget.

[04:36:34] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[04:36:34] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":67,"exec_chars":1958,"chapter_done":true}

[04:36:34] [DEBUG]   📊 Progress: 1/1 done | 67 bullets | 1,958 chars exec summary

[04:36:34] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\checkpoints

[04:36:34] [INFO] 📄 Building DOCX report…

[04:36:34] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[04:36:35] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[04:36:35] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.37_20260926-041731-130842a6_summary.md + DOCX

[04:36:35] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[04:36:35] [INFO]   🧮 Embedding cache: 63 hits / 32 misses (66% hit-rate), 5000 entries

[04:36:35] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.37_20260926-041731-130842a6_summary.md

[04:36:35] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries

[04:36:35] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[04:36:35] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.37_20260926-041731-130842a6.summary.md

[04:36:35] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[04:36:35] [INFO]   ⏱️ DOCX phase starting | [1144.0s]

[04:36:35] [INFO] 📄 Building DOCX report…

[04:36:35] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[04:36:35] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[04:36:37] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[04:36:38] [INFO]   🧹 Keypoints dedup: removed 1 duplicate(s) (67 → 66 keypoints)

[04:36:38] [DEBUG]   🗑️ '**Cameron outlined four aspects of paranoid** — 4 items from...' (embedding sim > 0.85)

[04:36:38] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[04:38:22] [INFO]   🎯 K1+Classification: 66 bullets — 10 core, 36 supporting, 20 additional

[04:38:22] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[04:38:22] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[04:38:22] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[04:38:22] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[04:38:22] [INFO]   📊 Citation graph: no citations found in the text.

[04:38:22] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[04:38:22] [SUCCESS] ✅ Conversion complete.

[04:38:38] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\logs\quality_report.json

[04:38:38] [INFO] 

[04:38:38] [INFO] ━━━ Thermal Safety Report ━━━

[04:38:38] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[04:38:38] [INFO]   Session duration: 15.7 min

[04:38:38] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[04:38:38] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[04:38:38] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[04:38:38] [INFO] 

[04:38:38] [INFO] ━━━ Elixir v0.4.37 Conversion Diagnostic Summary ━━━

[04:38:38] [INFO]   Book: Broken Structures Salman Akhtar

[04:38:38] [INFO]   Total pages: 397

[04:38:38] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[04:38:38] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[04:38:38] [INFO]   Summaries generated: 1

[04:38:38] [INFO]     Success: 1, Failed: 0, Total bullets: 67

[04:38:38] [INFO]     Coverage: 94%

[04:38:38] [INFO]     Recall floor (deterministic, final set): theorists 52/74 (70%), conclusion items 3/3 (100%)

[04:38:38] [INFO]   Warnings: 0

[04:38:38] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar

[04:38:38] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.37_20260926-041731-130842a6.conversion.log.md

[04:38:38] [INFO]   Diagnostic JSONL: None

[04:38:38] [INFO]   Summary files (3):

[04:38:38] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.37_20260926-041731-130842a6_summary.md — generated-by v0.4.37 | run_id=20260926-041731-130842a6 | started=2026-09-26T04:22:55 | bullets=67

[04:38:38] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.37 | run_id=20260926-041731-130842a6 | started=2026-09-26T04:22:55 | bullets=67

[04:38:38] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.37_20260926-041731-130842a6.summary.md — generated-by v0.4.37 | run_id=20260926-041731-130842a6 | started=2026-09-26T04:22:55 | bullets=67

[04:38:38] [INFO]   Models loaded at exit: (none — all unloaded)

[04:38:38] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[04:38:38] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[04:38:38] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[04:38:38] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[04:38:38] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[04:38:38] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[04:38:38] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[04:38:38] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\images

[04:38:38] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[04:38:44] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\images

[04:38:49] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[04:38:49] [INFO]   [pipeline] after de-dup: 2 regions

[04:38:50] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\437\Broken Structures Salman Akhtar\regions

[04:38:50] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[04:38:50] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 66 keypoints)


---
Finished at: 2026-09-26T04:38:50.208810
