# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T01:30:38.425323

<!-- generated-by: Elixir v0.4.35 | run_id=20260926-013038-18eb612a -->

---

[01:30:38] [SUCCESS] 🚀 Starting conversion…

[01:30:38] [DEBUG]   🔍 importing 'pypdf'…

[01:30:38] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[01:30:38] [DEBUG]   🔍 importing 'pdf2image'…

[01:30:38] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[01:30:38] [DEBUG]   🔍 importing 'tiktoken'…

[01:30:38] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[01:30:38] [DEBUG]   🔍 importing 'markitdown'…

[01:30:40] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[01:30:40] [DEBUG]   🔍 importing 'rapidfuzz'…

[01:30:40] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[01:30:40] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[01:30:40] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[01:30:40] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[01:30:40] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[01:30:40] [DEBUG]   🔍 importing 'torch'…

[01:30:40] [DEBUG]   ✅ 'torch' ok (0.0s)

[01:30:40] [DEBUG]   🔍 importing 'transformers'…

[01:30:57] [DEBUG]   ✅ 'transformers' ok (17.5s)

[01:30:57] [DEBUG]   🔍 importing 'langextract'…

[01:30:58] [DEBUG]   ✅ 'langextract' ok (0.1s)

[01:30:58] [DEBUG]   ✅ Pre-flight dependency check passed

[01:30:58] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[01:30:58] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[01:30:58] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar.pdf

[01:30:58] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar

[01:30:58] [INFO]   Source type: normal_book

[01:30:58] [INFO]   App version: 0.4.35

[01:30:58] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[01:30:58] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[01:30:58] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[01:30:58] [INFO]   Ollama reachable (localhost:11434): True

[01:30:58] [INFO]   Provider: llamacpp

[01:30:58] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[01:30:58] [INFO]   [Phase 1 (Extraction)]

[01:30:58] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[01:30:58] [INFO]   [Phase 2 (Summarization)]

[01:30:58] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[01:30:58] [INFO]   ────────────────────────────────────────

[01:30:58] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[01:30:58] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[01:30:58] [INFO] ━━━━━━━━━━━━━━━━━━━━

[01:30:58] [INFO]   LLM OCR: True, Force OCR all: False

[01:30:58] [INFO]   Auto-detect scanned: True

[01:30:58] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[01:30:58] [INFO]   OCR retries: 2, Image max size: 1200

[01:30:58] [INFO]   Page range: all

[01:30:58] [INFO]   Selected chapters: 1 chapter(s)

[01:30:58] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[01:30:58] [INFO]   Segmentation: auto, Token limit: 2000

[01:30:58] [INFO]   Semantic: True, Page group: 10

[01:30:58] [INFO]   Generate summaries: True

[01:30:58] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[01:30:58] [INFO]   Fast model: , Heavy model: (disabled)

[01:30:58] [INFO]   Workers (requested): 1, Temperature: 0.7

[01:30:58] [INFO]   Self-consistency: False, Coverage threshold: 85%

[01:30:58] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[01:30:58] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[01:30:58] [INFO]   Academic rigor: False

[01:30:58] [INFO]   Max context tokens: 128000

[01:30:58] [INFO]   Max output tokens: 32768

[01:30:58] [INFO]   Keep-alive: 30m

[01:30:58] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[01:30:58] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[01:30:58] [INFO]   Translation: disabled

[01:30:58] [INFO]   Clean markdown: True, Token saver: True

[01:30:58] [INFO]   Content filter: True

[01:30:58] [INFO]   Extract tables: False, Math: False, Figures: False

[01:30:58] [INFO]   Visual-region crops: True

[01:30:58] [INFO]   Layout analysis: False

[01:30:58] [INFO]   DOCX author: Elixir, TOC: True

[01:30:58] [INFO]   Output paths (V7.5 subfolders):

[01:30:58] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[01:30:58] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[01:30:58] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[01:30:58] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\packets

[01:30:58] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\podcast

[01:30:58] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\logs\quality_report.json

[01:30:58] [INFO]   Resume mode: enabled — will skip done chapters

[01:30:58] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[01:30:58] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[01:30:58] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[01:30:58] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[01:30:58] [DEBUG]   💾 Disk space: 25.1 GB free

[01:30:58] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\.checkpoint.json

[01:32:13] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[01:32:13] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[01:32:13] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[01:32:13] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[01:32:14] [INFO] [TOC] Using PDF outlines: 22 entries.

[01:32:14] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[01:32:14] [DEBUG]   [TOC] Entries passed to segmenter: 22

[01:32:14] [DEBUG]   [TOC] - p.7: Table of Contents

[01:32:14] [DEBUG]   [TOC] - p.9: FOREWORD

[01:32:14] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[01:32:14] [DEBUG]   [TOC] … and 19 more

[01:32:14] [INFO]   🎯 User selected 1 chapter(s):

[01:32:14] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[01:32:14] [INFO]   📸 front_cover → front_cover.jpg

[01:32:14] [INFO]   📸 back_cover → back_cover.jpg

[01:32:14] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[01:32:14] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[01:32:14] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[01:32:14] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[01:32:15] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[01:32:15] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[01:32:15] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[01:32:15] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[01:32:15] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[01:32:16] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[01:32:16] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[01:32:16] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[01:32:16] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[01:32:16] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[01:32:17] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[01:32:17] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[01:32:17] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[01:32:17] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[01:32:17] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[01:32:18] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[01:32:18] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[01:32:18] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[01:32:18] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[01:32:18] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[01:32:19] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[01:32:19] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[01:32:19] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[01:32:19] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[01:32:19] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[01:32:19] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[01:32:19] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[01:32:19] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[01:32:19] [INFO]   ✅ markitdown ready for digital-page extraction

[01:32:19] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[01:32:19] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[01:32:19] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[01:32:19] [INFO]      Pages needing OCR: [152, 153, 154]

[01:32:19] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[01:32:19] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[01:32:19] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[01:32:22] [INFO]   📄 140/397 pages processed (35%)

[01:32:29] [INFO]   🔍 OCR  page 152/397 (scanned)…

[01:32:31] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[01:33:56] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[01:33:56] [INFO]   🔍 OCR  page 153/397 (scanned)…

[01:35:28] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[01:35:28] [INFO]   🔍 OCR  page 154/397 (scanned)…

[01:36:56] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[01:37:00] [INFO]   📄 160/397 pages processed (40%)

[01:37:00] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[01:37:00] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[01:37:00] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[01:37:00] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[01:37:00] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[01:37:00] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[01:37:00] [INFO] 📝 Raw markdown: 53,157 chars | [382.3s]

[01:37:00] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[01:37:00] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[01:37:00] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[01:37:00] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[01:37:00] [INFO] [Segmenter] Attempting chapter-level segmentation…

[01:37:00] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[01:37:00] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[01:37:00] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[01:37:00] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[01:37:00] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[01:37:00] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[01:37:00] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[01:37:00] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[01:37:00] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[01:37:00] [INFO]   📑 Filtered segments: kept 1 of 17

[01:37:00] [INFO] 📚 1 segment(s) detected | [382.5s]

[01:37:00] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[01:37:00] [INFO] 🌐 Detected language: en

[01:37:00] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[01:37:00] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[01:37:01] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\markdown\chapters

[01:37:01] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[01:37:01] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\markdown\chapters

[01:37:01] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[01:37:01] [INFO]   ⏱️ Summary phase starting | [382.9s]

[01:37:03] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[01:37:03] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[01:37:03] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[01:37:03] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[01:37:03] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[01:37:03] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[01:37:03] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[01:37:03] [INFO]   🌡️ Pre-flight: idle GPU temp = 59°C

[01:37:03] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 59°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[01:37:03] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[01:37:03] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[01:37:03] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[01:37:03] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[01:37:03] [DEBUG]   🎛️ Model profile: Default

[01:37:03] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[01:37:03] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[01:37:03] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[01:37:03] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[01:37:03] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[01:37:03] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[01:37:03] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[01:37:03] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[01:37:03] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[01:37:03] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[01:37:03] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[01:37:03] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[01:37:03] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[01:37:03] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[01:37:03] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[01:37:03] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[01:37:03] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[01:37:03] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[01:37:03] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[01:37:03] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[01:37:03] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[01:37:03] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\435

[01:37:03] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[01:37:03] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[01:37:03] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[01:37:03] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[01:37:03] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[01:37:03] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[01:37:04] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[01:37:04] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[01:37:04] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:37:04] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[01:38:14] [INFO]     ✅ V0.3 Call 1/3: master summary = 721 words, 5591 chars

[01:38:14] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[01:38:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:38:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[01:38:48] [INFO]     ✅ V0.3 Call 2/3: 33 bullets derived from master summary

[01:38:48] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[01:38:48] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:38:48] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[01:39:06] [INFO]     ✅ V0.3 Call 3/3: exec summary = 258 words

[01:39:06] [DEBUG]     📝 Parsed: exec=2097 chars, bullets=33, thorough=5591 chars

[01:39:33] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[01:39:35] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[01:39:35] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (33 bullets, 258 exec words, 721 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[01:39:37] [DEBUG]     🔍 Fact-check: all 33 bullets verified ✓

[01:39:37] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[01:39:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:39:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[01:40:32] [INFO]     ✅ Additive sections via followup call: key_distinctions=1849 chars, theoretical_tensions=1590 chars

[01:40:32] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (33 bullets, 258 exec words, 721 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[01:40:32] [WARNING]     ⚠️ thorough_summary too short (721 words < 800 threshold) — requesting dedicated expansion…

[01:40:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[01:40:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[01:41:45] [INFO]     📖 Attempt 1/3: dedicated thorough = 790 words

[01:41:45] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[01:41:48] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[01:41:48] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[01:42:40] [INFO]     📖 Attempt 2/3: dedicated thorough = 793 words

[01:42:40] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying at temperature 0.0 (greedy)

[01:42:40] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.00) via llm_provider.llamacpp…

[01:42:40] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.00 max=8192 streaming…

[01:47:42] [INFO]     📖 Attempt 3/3: dedicated thorough = 4636 words

[01:47:42] [INFO]     ✅ thorough_summary expanded via dedicated call: 721 → 4636 words

[01:47:42] [INFO]     V0.05: Skipping bullet expansion — 33 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[01:47:42] [INFO]     ✅ Final coverage 100%

[01:47:42] [DEBUG]     ✂️ F1: Truncated thorough_summary to 4166 words (source-scaled cap)

[01:47:42] [DEBUG]     📏 F1: exec=258w, thorough=4636w (source=7405w; targets exec<=250w, thorough<=3332w)

[01:50:12] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[01:50:12] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 18.2 (diff: -1.9)

[01:50:12] [INFO]     ℹ️ F3: Summary is 1.9 grade levels denser than source — expected for a compressed academic summary.

[01:50:13] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[01:50:13] [DEBUG]     🔄 J2: 22 cross-section redundancy(ies) found (exec↔bullets: 7, bullets↔thorough: 14)

[01:50:13] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 4 markers)

[01:50:13] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[01:50:13] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[01:50:14] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[01:50:29] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3920 per-pair calls)

[01:50:29] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[01:50:32] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (33/33 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[01:50:32] [INFO]   ℹ️ Summary has substantial content (exec=2097 chars, thorough=29947 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[01:50:32] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[01:50:32] [WARNING]   ⏱️⚠️ Deadline exceeded (809s > 480s) — skipping optional phase: scholar reflection

[01:50:32] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[01:50:32] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[01:50:32] [WARNING]   ⏱️⚠️ Deadline exceeded (809s > 480s) — skipping optional phase: semantic dedup

[01:50:32] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[01:50:32] [DEBUG]     🧹 V16.0.2 Bullet normalization: 33 bullets normalized

[01:50:32] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[01:50:32] [WARNING]   ⏱️⚠️ Deadline exceeded (809s > 480s) — skipping optional phase: bullet consolidation

[01:50:32] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[01:50:32] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\435

[01:50:32] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[01:50:32] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[01:50:32] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Freud', 'Magnan', 'Klein', 'Winnicott', 'Bach', 'Erikson']/74 authors in bullets (11%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']

[01:50:32] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur', 'Widiger', 'Kendler', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Widiger and Frances', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Anthony', 'Kohut', 'Bach', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Frances and Widiger', 'Croewe', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Gorton and Akhtar', 'Siever']/74 authors in thorough (76%) — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Fenichel', 'Bergman', 'Allodi']

[01:50:33] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']…

[01:50:33] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:50:33] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:50:52] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[01:50:52] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (19.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[01:50:52] [DEBUG]     📊 V18.14.1: After round 1, 56 still missing from bullets: ['Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[01:50:52] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[01:50:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:50:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:51:03] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne described the behavioral correlates of splitting.…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[01:51:03] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[01:51:03] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 6/8 bullets

[01:51:03] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (11.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[01:51:03] [DEBUG]     📊 V18.14.1: After round 2, 50 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Schneider', 'Salzman', 'Millon']…

[01:51:03] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Schneider', 'Salzman', 'Millon']… (mention-only: ['Byrne'])

[01:51:03] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:51:03] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:51:19] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[01:51:19] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[01:51:19] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 5/8 bullets

[01:51:19] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.6s): response=7 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=5

[01:51:19] [INFO]     🔁 V18.20.3.7: 'Akhtar and Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[01:51:19] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[01:51:19] [DEBUG]     📊 V18.14.1: After round 3, 44 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Widiger', 'Kendler']…

[01:51:19] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Akhtar and Byrne', 'Volkan', 'Widiger', 'Kendler', 'Leonhard']… (mention-only: ['Akhtar and Byrne'])

[01:51:19] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:51:19] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:51:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne’s descriptions of the behavioral correlates of splitt…

[01:51:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[01:51:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Slater and Roth (1977) pointed out the paradoxical "contradictory prid…

[01:51:35] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 5/8 bullets

[01:51:35] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (15.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[01:51:35] [INFO]     🔁 V18.20.3.7: 'Volkan' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[01:51:35] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Akhtar and Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[01:51:35] [DEBUG]     📊 V18.14.1: After round 4, 36 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Slater and Roth', 'Tobak']…

[01:51:35] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Volkan', 'Slater and Roth', 'Tobak', 'Mahler', 'Bak']… (mention-only: ['Volkan'])

[01:51:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[01:51:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[01:51:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan's (1986) insights regarding man’s need for enemies and allies a…

[01:51:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler’s (1975) theory of separation-individuation is referenced to ex…

[01:51:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bak (1946) is cited in support of the view that paranoid fantasies of …

[01:51:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is included am…

[01:51:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited as a signific…

[01:51:51] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 3/8 bullets

[01:51:51] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (16.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=5, added=3

[01:51:51] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Volkan' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[01:51:51] [DEBUG]     📊 V18.14.1: After round 5, 30 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Mahler', 'Anthony']…

[01:51:51] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 27 bullets across 5 round(s)

[01:51:51] [WARNING]     ⚠️ V18.14.1: 30 theorists still missing from bullets after gap-fill: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Mahler', 'Anthony', 'Kohut', 'Bergman', 'Allodi'] — of these, 3 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Byrne', 'Akhtar and Byrne', 'Volkan'] — 27 never covered (round cap/deadline): ['Mahler', 'Anthony', 'Kohut', 'Bergman', 'Allodi', 'Jack', 'Ndtei', 'Bursten']

[01:51:51] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[01:51:51] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[01:51:51] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (1 item(s) were uncovered; all 4 now carried verbatim)

[01:51:51] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[01:51:53] [DEBUG]     🧹 Semantic dedup: removing bullet 53 (sim=0.90 with bullet 46)

[01:51:53] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 63 → 62 bullets (removed 1 gap-fill/conclusion duplicates; 1.6s, non-skippable per V18.20.3.4)

[01:51:53] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\435

[01:51:53] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[01:51:53] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[01:51:56] [INFO]     ℹ️ V0.4.23: 62 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[01:51:56] [INFO]     🛡️ V18.2.13 Post-checks: 14 fixed, 7 flagged (of 62 bullets + exec + thorough)

[01:51:56] [DEBUG]       [grammar/flag] bullet[20]: no main verb detected in first 40 words of '"Overt" characteristics of the disorder …' — the bullet may be grammatically broken (generation/formatting failure)  |  "Overt" characteristics of the…

[01:51:56] [DEBUG]       [grammar/flag] bullet[21]: no main verb detected in first 40 words of '"Covert" characteristics include timidit…' — the bullet may be grammatically broken (generation/formatting failure)  |  "Covert" characteristics inclu…

[01:51:56] [DEBUG]       [dropped_letter/flag] bullet[49]: likely garbled token: 'paranooids' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  … "the confidence and pride of paranooids cloak but a hollow …

[01:51:56] [DEBUG]       [attribution/flag] bullet[59]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[01:51:56] [DEBUG]       [truncated/flag] bullet[60]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[01:51:56] [DEBUG]       [fragment_merge/flag] exec: word-fragment merge: 'theme' — 'them' is a known word but 'theme' is not. The trailing 'e' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …pe, highlighting a consistent theme of contradiction: the co…

[01:51:56] [DEBUG]       [interpretation/fix] thorough: stripped first-person interpretation: 'It should be noted that'  |  …iny and prevent misdiagnosis. It should be noted that the ov…

[01:51:56] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  ighly structuralized and ego-syntonically embedded in the personal

[01:51:56] [DEBUG]       [quote_verification/fix] bullet[49]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  the confidence and pride of paranooids cloak but a hollow sh

[01:51:56] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to Kraepelin’s description of a vain yet credulous type, hi

[01:51:56] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics like arrogance and hypervigilance, and 

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by idiosyncratic thinking, undue sensitivity,

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ) or paranoid schizophrenia. It characterizes the condition 

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the earliest developmental constellation of infantile ob

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a menace. The end of intrauterine bliss, with birth, pro

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects on whom they might plausibly project their

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Shapiro regarded the paranoid person’s construction of a su

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   clues form their context and, on the other hand, a loss of 

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   unconscious desires are disavowed by projection. Their furt

[01:51:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   the ambivalently loved object that is felt to be both perse

[01:51:56] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  continued to exist independently

[01:51:57] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 56/74 authors in thorough — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Fenichel', 'Bergman', 'Allodi']

[01:51:57] [WARNING]   ⏱️⚠️ Deadline exceeded (893s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[01:51:57] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 18 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[01:51:57] [INFO]     ⏭️  V0.05: Thorough gap-fill skipped — thorough (4158 words) already meets its source-scaled target (3332 words); the missing contributor(s) are covered by the bullets/recall floor

[01:51:57] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 41/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Widiger', 'Widiger and Frances']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[01:51:57] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 894s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 894s of the budget.

[01:51:57] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[01:51:57] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":62,"exec_chars":2093,"chapter_done":true}

[01:51:57] [DEBUG]   📊 Progress: 1/1 done | 62 bullets | 2,093 chars exec summary

[01:51:57] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\checkpoints

[01:51:57] [INFO] 📄 Building DOCX report…

[01:51:57] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[01:51:58] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[01:51:58] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md + DOCX

[01:51:58] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[01:51:58] [INFO]   🧮 Embedding cache: 63 hits / 35 misses (64% hit-rate), 5000 entries

[01:51:58] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md

[01:51:58] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries

[01:51:58] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[01:51:58] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.35_20260926-013038-18eb612a.summary.md

[01:51:58] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[01:51:58] [INFO]   ⏱️ DOCX phase starting | [1279.7s]

[01:51:58] [INFO] 📄 Building DOCX report…

[01:51:58] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[01:51:58] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[01:52:01] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[01:52:03] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[01:53:54] [INFO]   🎯 K1+Classification: 62 bullets — 19 core, 18 supporting, 25 additional

[01:53:54] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[01:53:55] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[01:53:55] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[01:53:55] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[01:53:55] [INFO]   📊 Citation graph: no citations found in the text.

[01:53:55] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[01:53:55] [SUCCESS] ✅ Conversion complete.

[01:54:11] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\logs\quality_report.json

[01:54:11] [INFO] 

[01:54:11] [INFO] ━━━ Thermal Safety Report ━━━

[01:54:11] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[01:54:11] [INFO]   Session duration: 17.1 min

[01:54:11] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[01:54:11] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[01:54:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[01:54:11] [INFO] 

[01:54:11] [INFO] ━━━ Elixir v0.4.35 Conversion Diagnostic Summary ━━━

[01:54:11] [INFO]   Book: Broken Structures Salman Akhtar

[01:54:11] [INFO]   Total pages: 397

[01:54:11] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[01:54:11] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[01:54:11] [INFO]   Summaries generated: 1

[01:54:11] [INFO]     Success: 1, Failed: 0, Total bullets: 62

[01:54:11] [INFO]     Coverage: 100%

[01:54:11] [INFO]     Recall floor (deterministic, final set): theorists 41/74 (55%), conclusion items 3/3 (100%)

[01:54:11] [INFO]   Warnings: 0

[01:54:11] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar

[01:54:11] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.35_20260926-013038-18eb612a.conversion.log.md

[01:54:11] [INFO]   Diagnostic JSONL: None

[01:54:11] [INFO]   Summary files (3):

[01:54:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.35_20260926-013038-18eb612a_summary.md — generated-by v0.4.35 | run_id=20260926-013038-18eb612a | started=2026-09-26T01:37:03 | bullets=62

[01:54:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.35 | run_id=20260926-013038-18eb612a | started=2026-09-26T01:37:03 | bullets=62

[01:54:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.35_20260926-013038-18eb612a.summary.md — generated-by v0.4.35 | run_id=20260926-013038-18eb612a | started=2026-09-26T01:37:03 | bullets=62

[01:54:11] [INFO]   Models loaded at exit: (none — all unloaded)

[01:54:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[01:54:11] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[01:54:11] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[01:54:12] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[01:54:12] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[01:54:12] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[01:54:12] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[01:54:12] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\images

[01:54:12] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[01:54:18] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\images

[01:54:29] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[01:54:29] [INFO]   [pipeline] after de-dup: 2 regions

[01:54:30] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\435\Broken Structures Salman Akhtar\regions

[01:54:30] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[01:54:30] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 62 keypoints)


---
Finished at: 2026-09-26T01:54:30.461344
