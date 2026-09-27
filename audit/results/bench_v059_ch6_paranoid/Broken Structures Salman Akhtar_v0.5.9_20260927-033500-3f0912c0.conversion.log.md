# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T03:35:00.535944

<!-- generated-by: Elixir v0.5.9 | run_id=20260927-033500-3f0912c0 -->

---

[03:35:00] [SUCCESS] 🚀 Starting conversion…

[03:35:00] [DEBUG]   🔍 importing 'pypdf'…

[03:35:00] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[03:35:00] [DEBUG]   🔍 importing 'pdf2image'…

[03:35:00] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[03:35:00] [DEBUG]   🔍 importing 'tiktoken'…

[03:35:00] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[03:35:00] [DEBUG]   🔍 importing 'markitdown'…

[03:35:03] [DEBUG]   ✅ 'markitdown' ok (2.7s)

[03:35:03] [DEBUG]   🔍 importing 'rapidfuzz'…

[03:35:03] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[03:35:03] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[03:35:03] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[03:35:03] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[03:35:03] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[03:35:03] [DEBUG]   ✅ 'torch' installed

[03:35:03] [DEBUG]   ✅ 'transformers' installed

[03:35:03] [DEBUG]   ✅ 'langextract' installed

[03:35:03] [DEBUG]   ✅ Pre-flight dependency check passed

[03:35:03] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[03:35:03] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[03:35:03] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar.pdf

[03:35:03] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar

[03:35:03] [INFO]   Source type: normal_book

[03:35:03] [INFO]   App version: 0.5.9

[03:35:03] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[03:35:03] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[03:35:03] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[03:35:03] [INFO]   Ollama reachable (localhost:11434): True

[03:35:03] [INFO]   Provider: llamacpp

[03:35:03] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[03:35:03] [INFO]   [Phase 1 (Extraction)]

[03:35:03] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[03:35:03] [INFO]   [Phase 2 (Summarization)]

[03:35:03] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[03:35:03] [INFO]   ────────────────────────────────────────

[03:35:03] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[03:35:03] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[03:35:03] [INFO] ━━━━━━━━━━━━━━━━━━━━

[03:35:03] [INFO]   LLM OCR: True, Force OCR all: False

[03:35:03] [INFO]   Auto-detect scanned: True

[03:35:03] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[03:35:03] [INFO]   OCR retries: 2, Image max size: 1200

[03:35:03] [INFO]   Page range: all

[03:35:03] [INFO]   Selected chapters: 1 chapter(s)

[03:35:03] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[03:35:03] [INFO]   Segmentation: auto, Token limit: 2000

[03:35:03] [INFO]   Semantic: True, Page group: 10

[03:35:03] [INFO]   Generate summaries: True

[03:35:03] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[03:35:03] [INFO]   Fast model: , Heavy model: (disabled)

[03:35:03] [INFO]   Workers (requested): 1, Temperature: 0.7

[03:35:03] [INFO]   Self-consistency: False, Coverage threshold: 95%

[03:35:03] [INFO]   📈 Over-delivery: ENABLED (floor 95% → target 100%)

[03:35:03] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[03:35:03] [INFO]   Academic rigor: False

[03:35:03] [INFO]   Max context tokens: 128000

[03:35:03] [INFO]   Max output tokens: 32768

[03:35:03] [INFO]   Keep-alive: 30m

[03:35:03] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[03:35:03] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[03:35:03] [INFO]   Translation: disabled

[03:35:03] [INFO]   Clean markdown: True, Token saver: True

[03:35:03] [INFO]   Content filter: True

[03:35:03] [INFO]   Extract tables: False, Math: False, Figures: False

[03:35:03] [INFO]   Visual-region crops: True

[03:35:03] [INFO]   Layout analysis: False

[03:35:03] [INFO]   DOCX author: Elixir, TOC: True

[03:35:03] [INFO]   Output paths (V7.5 subfolders):

[03:35:03] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[03:35:03] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[03:35:03] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[03:35:03] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\packets

[03:35:03] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\podcast

[03:35:03] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\logs\quality_report.json

[03:35:03] [INFO]   Resume mode: enabled — will skip done chapters

[03:35:03] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[03:35:03] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[03:35:03] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[03:35:03] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[03:35:03] [DEBUG]   💾 Disk space: 20.9 GB free

[03:35:03] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\.checkpoint.json

[03:36:36] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[03:36:36] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[03:36:36] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[03:36:36] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[03:36:36] [INFO] [TOC] Using PDF outlines: 22 entries.

[03:36:36] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[03:36:36] [DEBUG]   [TOC] Entries passed to segmenter: 22

[03:36:36] [DEBUG]   [TOC] - p.7: Table of Contents

[03:36:36] [DEBUG]   [TOC] - p.9: FOREWORD

[03:36:36] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[03:36:36] [DEBUG]   [TOC] … and 19 more

[03:36:36] [INFO]   🎯 User selected 1 chapter(s):

[03:36:36] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[03:36:36] [INFO]   📸 front_cover → front_cover.jpg

[03:36:36] [INFO]   📸 back_cover → back_cover.jpg

[03:36:36] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[03:36:36] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[03:36:37] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[03:36:37] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[03:36:37] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[03:36:37] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[03:36:37] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[03:36:38] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[03:36:38] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[03:36:38] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[03:36:38] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[03:36:38] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[03:36:39] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[03:36:39] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[03:36:39] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[03:36:39] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[03:36:39] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[03:36:40] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[03:36:40] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[03:36:40] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[03:36:40] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[03:36:40] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[03:36:40] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[03:36:41] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[03:36:41] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[03:36:41] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[03:36:41] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[03:36:41] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[03:36:41] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[03:36:41] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[03:36:41] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[03:36:41] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[03:36:41] [INFO]   ✅ markitdown ready for digital-page extraction

[03:36:41] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[03:36:41] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[03:36:41] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[03:36:41] [INFO]      Pages needing OCR: [152, 153, 154]

[03:36:41] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[03:36:41] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[03:36:41] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[03:36:43] [INFO]   📄 140/397 pages processed (35%)

[03:36:49] [INFO]   🔍 OCR  page 152/397 (scanned)…

[03:36:52] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[03:38:59] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[03:38:59] [INFO]   🔍 OCR  page 153/397 (scanned)…

[03:41:04] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[03:41:04] [INFO]   🔍 OCR  page 154/397 (scanned)…

[03:43:01] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[03:43:04] [INFO]   📄 160/397 pages processed (40%)

[03:43:04] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[03:43:05] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[03:43:05] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[03:43:05] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[03:43:05] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[03:43:05] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[03:43:05] [INFO] 📝 Raw markdown: 53,157 chars | [484.5s]

[03:43:05] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[03:43:05] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[03:43:05] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[03:43:05] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[03:43:05] [INFO] [Segmenter] Attempting chapter-level segmentation…

[03:43:05] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[03:43:05] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[03:43:05] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[03:43:05] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[03:43:05] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[03:43:05] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[03:43:05] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[03:43:05] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[03:43:05] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[03:43:05] [INFO]   📑 Filtered segments: kept 1 of 17

[03:43:05] [INFO] 📚 1 segment(s) detected | [484.6s]

[03:43:05] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[03:43:05] [INFO] 🌐 Detected language: en

[03:43:05] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[03:43:05] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[03:43:05] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\markdown\chapters

[03:43:05] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[03:43:05] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\markdown\chapters

[03:43:05] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3938 bytes)

[03:43:05] [INFO]   ⏱️ Summary phase starting | [484.9s]

[03:43:07] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[03:43:07] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[03:43:07] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[03:43:07] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[03:43:07] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[03:43:07] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[03:43:07] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[03:43:07] [INFO]   🌡️ Pre-flight: idle GPU temp = 58°C

[03:43:07] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 58°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[03:43:07] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[03:43:07] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[03:43:07] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[03:43:07] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[03:43:07] [DEBUG]   🎛️ Model profile: Default

[03:43:07] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[03:43:07] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[03:43:07] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[03:43:07] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[03:43:07] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[03:43:07] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[03:43:07] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[03:43:07] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[03:43:07] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[03:43:07] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[03:43:07] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[03:43:07] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[03:43:07] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[03:43:08] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[03:43:08] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[03:43:08] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[03:43:08] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[03:43:08] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[03:43:08] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[03:43:08] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[03:43:08] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[03:43:08] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.9

[03:43:08] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[03:43:08] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[03:43:08] [INFO]     📊 V17.2: Prepended deterministic analysis (3823 chars) — citation recall 78%→100%

[03:43:08] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[03:43:08] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[03:43:08] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[03:43:08] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[03:43:08] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[03:43:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[03:43:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[03:45:39] [INFO]     ✅ V0.3 Call 1/3: master summary = 611 words, 4718 chars

[03:45:39] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[03:45:39] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[03:45:39] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[03:46:30] [INFO]     ✅ V0.3 Call 2/3: 36 bullets derived from master summary

[03:46:30] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[03:46:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[03:46:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[03:47:01] [INFO]     ✅ V0.3 Call 3/3: exec summary = 232 words

[03:47:01] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[03:47:01] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[03:56:04] [DEBUG]     ℹ️ V0.5.7: no <name_glossary> block parsed from the separate call (skipping persistence — the verification LAYER will fall back to the regex extract_citations)

[03:56:04] [DEBUG]     📝 Parsed: exec=1794 chars, bullets=36, thorough=4718 chars

[03:56:39] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[03:56:41] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[03:56:41] [INFO]     ℹ️ Coverage 92% < 95% — B3 voting disabled, will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward 100%

[03:56:41] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 95% → target 100%) — applying 3-Tier Guarantee

[03:56:42] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (36 bullets, 232 exec words, 611 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[03:56:44] [DEBUG]     🔍 Fact-check: all 36 bullets verified ✓

[03:56:44] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[03:56:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[03:56:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[03:59:35] [INFO]     ✅ Additive sections via followup call: key_distinctions=1933 chars, theoretical_tensions=1747 chars

[03:59:35] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (36 bullets, 232 exec words, 611 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[03:59:35] [WARNING]     ⚠️ thorough_summary too short (611 words < 800 threshold) — requesting dedicated expansion…

[03:59:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[03:59:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[04:03:06] [INFO]     📖 Attempt 1/3: dedicated thorough = 856 words

[04:03:06] [INFO]     ✅ thorough_summary expanded via dedicated call: 611 → 856 words

[04:03:06] [WARNING]   ⏱️⚠️ Deadline exceeded (1198s > 480s) — skipping optional phase: dedicated bullet expansion

[04:03:06] [WARNING]     ⚠️ Final coverage 92% below 95% threshold

[04:03:06] [DEBUG]     📏 F1: exec=232w, thorough=856w (source=7405w; targets exec<=250w, thorough<=3332w)

[04:05:23] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[04:05:23] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.4 (diff: -4.2)

[04:05:23] [INFO]     ℹ️ F3: Summary is 4.1 grade levels denser than source — expected for a compressed academic summary.

[04:05:24] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[04:05:24] [DEBUG]     🔄 J2: 6 cross-section redundancy(ies) found (exec↔bullets: 2, bullets↔thorough: 4)

[04:05:24] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 4 markers)

[04:05:24] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[04:05:24] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[04:05:24] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[04:05:43] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 4256 per-pair calls)

[04:05:43] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[04:05:46] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (36/36 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[04:05:46] [INFO]   ℹ️ Summary has substantial content (exec=1794 chars, thorough=6588 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[04:05:46] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[04:05:46] [WARNING]   ⏱️⚠️ Deadline exceeded (1358s > 480s) — skipping optional phase: scholar reflection

[04:05:46] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[04:05:46] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[04:05:46] [WARNING]   ⏱️⚠️ Deadline exceeded (1358s > 480s) — skipping optional phase: semantic dedup

[04:05:46] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[04:05:46] [DEBUG]     🧹 V16.0.2 Bullet normalization: 36 bullets normalized

[04:05:46] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[04:05:46] [WARNING]   ⏱️⚠️ Deadline exceeded (1358s > 480s) — skipping optional phase: bullet consolidation

[04:05:46] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[04:05:46] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.9

[04:05:46] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[04:05:46] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[04:05:46] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Freud', 'Heimann', 'Rycroft', 'Magnan', 'Slater and Roth', 'Klein', 'Winnicott', 'Roth', 'Slater', 'Erikson', 'Morey']/74 authors in bullets (18%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']

[04:05:46] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Widiger', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Widiger and Frances', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Anthony', 'Kohut', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Frances and Widiger', 'Morey', 'Ovessey', 'Walters']/74 authors in thorough (61%) — MISSING from thorough: ['Thomson', 'Byrne', 'Akhtar and Byrne', 'Akhtar and Thomson', 'Winokur']

[04:05:46] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']…

[04:05:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:05:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:06:07] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[04:06:07] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[04:06:07] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (21.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[04:06:07] [DEBUG]     📊 V18.14.1: After round 1, 53 still missing from bullets: ['Kernberg', 'Hamilton', 'Cameron', 'Frances', 'Byrne']…

[04:06:07] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Hamilton', 'Cameron', 'Frances', 'Byrne']…

[04:06:07] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:06:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:06:27] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne (1983) provided descriptions of the behavio…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[04:06:27] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[04:06:27] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (19.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[04:06:27] [DEBUG]     📊 V18.14.1: After round 2, 42 still missing from bullets: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[04:06:27] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[04:06:27] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:06:27] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:06:43] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[04:06:43] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[04:06:43] [DEBUG]     📊 V18.14.1: After round 3, 33 still missing from bullets: ['Polatin', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[04:06:43] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Polatin', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[04:06:43] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:06:43] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:07:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler’s (1975) theory of separation-individuation is cited to explain…

[04:07:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) work is noted for its description of narcissistic rage,…

[04:07:03] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 6/8 bullets

[04:07:03] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (20.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[04:07:03] [DEBUG]     📊 V18.14.1: After round 4, 27 still missing from bullets: ['Mahler', 'Kohut', 'Bergman', 'Allodi', 'Jack']…

[04:07:03] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Mahler', 'Kohut', 'Bergman', 'Allodi', 'Jack']…

[04:07:03] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:07:03] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[04:07:20] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 8/8 bullets

[04:07:20] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (17.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[04:07:20] [DEBUG]     📊 V18.14.1: After round 5, 19 still missing from bullets: ['Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone']…

[04:07:20] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 36 bullets across 5 round(s)

[04:07:20] [WARNING]     ⚠️ V18.14.1: 19 theorists still missing from bullets after gap-fill: ['Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser', 'Conlon', 'Reid'] — 19 never covered (round cap/deadline): ['Pao', 'Socarides', 'Siever and Kendler', 'Mackinnon and Michels', 'Stone', 'Wurmser', 'Conlon', 'Reid']

[04:07:20] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[04:07:20] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[04:07:21] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 28 (sim=0.94 with bullet 10)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 29 (sim=0.88 with bullet 16)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 31 (sim=0.86 with bullet 20)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 32 (sim=0.86 with bullet 1)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 34 (sim=0.91 with bullet 16)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 36 (sim=0.88 with bullet 23)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 69 (sim=0.87 with bullet 68)

[04:07:22] [DEBUG]     🧹 Semantic dedup: removing bullet 70 (sim=0.89 with bullet 68)

[04:07:22] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 80 → 72 bullets (removed 8 gap-fill/conclusion duplicates; 1.0s, non-skippable per V18.20.3.4)

[04:07:22] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.9

[04:07:22] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[04:07:22] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[04:07:25] [INFO]     🛡️ V18.2.13 Post-checks: 17 fixed, 6 flagged (of 72 bullets + exec + thorough)

[04:07:25] [DEBUG]       [consistency/flag] bullet[23]: false 'missing' claim: 'overlooked' followed by 'by standard diagnostic criteria but are ' — but 6/6 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …es of PPD that are frequently overlooked by standard diagnos…

[04:07:25] [DEBUG]       [sentence_fusion/flag] bullet[53]: likely source-propagated fusion garble: 'selfrighteousness' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'righteousness' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-righteousness').  |  mendacity and moralistic selfrighteousness.

[04:07:25] [DEBUG]       [sentence_fusion/flag] bullet[65]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[04:07:25] [DEBUG]       [truncated/flag] bullet[68]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[04:07:25] [DEBUG]       [truncated/flag] bullet[70]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[04:07:25] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Millon (1981)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …lzman (1974), Stanton (1978), Millon (1981), and Tobak (1989…

[04:07:25] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   structure to illustrate how external defensiveness masks in

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by idiosyncratic thinking and suspiciousness,

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   type who is vain, litigious, and distrustful yet paradoxica

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   noted by Slater and Roth (1977). The author highlights a co

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the developmental substrate, involving splitting, denial

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   leads to anxiety and suspiciousness. Erikson (1950a) linked

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a defense against betrayal, Cameron’s (1963) focus on ch

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   where the threat of betrayal is maintained to preserve an i

[04:07:25] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   framework highlights the central role of splitting and proj

[04:07:25] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  greater kernel of truth,

[04:07:25] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  It is a danger and I know why... his or her intention

[04:07:25] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and indecisive, while the paranoid attributes demands to ex

[04:07:25] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   dichotomy to capture the divided self of the paranoid indiv

[04:07:25] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   of such dynamic profiles by 

[04:07:25] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   with kinship to schizoid/narcissistic personalities, or var

[04:07:25] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[04:07:25] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian libidinal vs. psychoanalytic object-relations for

[04:07:25] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 45/74 authors in thorough — MISSING from thorough: ['Thomson', 'Byrne', 'Akhtar and Byrne', 'Akhtar and Thomson', 'Winokur']

[04:07:25] [WARNING]   ⏱️⚠️ Deadline exceeded (1457s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[04:07:25] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 29 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[04:07:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:07:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The descriptive literature is further enriched by the work of Thomson,…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Akhtar and Byrne extended this line of inquiry by identifying the beha…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Winokur contributed to the differential diagnosis debate by distinguis…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Kendler further advanced the genetic understanding of the disorder, su…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the psychoanalytic domain, Mahler’s theory of separation-individuat…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bach offered additional insight into the mirror complementarity of the…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Fenichel explored the structural dynamics of paranoia, emphasizing the…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bergman examined the cognitive distortions inherent in paranoid thinki…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi contributed to the understanding of moralistic self-righteousne…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Jack highlighted the sexual and erotomanic dimensions of para…" — its name(s) never co-occur with the claim's key phrases in the source

[04:08:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:08:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:09:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the domain of diagnostic validation and clinical assessment, Siever…" — its name(s) never co-occur with the claim's key phrases in the source

[04:09:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Similarly, Rettersol (1985) and Winokur (1985) directed attention to t…" — its name(s) never co-occur with the claim's key phrases in the source

[04:09:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[04:09:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler (1987) were among the first to critically examine t…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon's contributions to psychoanalytic theory provided an essenti…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon emphasized that paranoid personality represents a relatively…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Michels further refined the understanding of paranoid cognition by emp…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Michels demonstrated that paranoid individuals construct subjective wo…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:07] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Michels' work also highlighted the motor tension and hyperintentionali…" — its name(s) never co-occur with the claim's key phrases in the source

[04:10:21] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 45/74 → 51/74 (3 chunked call(s), ≤12 names each)

[04:10:21] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 53/74 in final bullets (missing: ['Jack', 'Ndtei', 'Pao', 'Socarides', 'Siever and Kendler']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[04:10:21] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 1633s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 1633s of the budget.

[04:10:21] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[04:10:21] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":72,"exec_chars":1792,"chapter_done":true}

[04:10:21] [DEBUG]   📊 Progress: 1/1 done | 72 bullets | 1,792 chars exec summary

[04:10:21] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\checkpoints

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923a' (ce:1923) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923' (ce:1923) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1945' (ce:1945) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1968' (ce:1968) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1958' (ce:1958) NOT found in summary — possible omission.

[04:10:21] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting: 16 source author(s) NOT found in the summary (Akhtar and Byrne, Akhtar and Thomson, Conlon, Jack, Lo

[04:10:21] [INFO] 📄 Building DOCX report…

[04:10:21] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[04:10:22] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[04:10:22] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.9_20260927-033500-3f0912c0_summary.md + DOCX

[04:10:22] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[04:10:22] [INFO]   🧮 Embedding cache: 63 hits / 38 misses (62% hit-rate), 5000 entries

[04:10:22] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.9_20260927-033500-3f0912c0_summary.md

[04:10:22] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries

[04:10:22] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[04:10:22] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.9_20260927-033500-3f0912c0.summary.md

[04:10:22] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[04:10:22] [INFO]   ⏱️ DOCX phase starting | [2121.8s]

[04:10:22] [INFO] 📄 Building DOCX report…

[04:10:22] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[04:10:22] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[04:10:24] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[04:10:26] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[04:12:23] [INFO]   🎯 K1+Classification: 72 bullets — 23 core, 32 supporting, 17 additional

[04:12:23] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[04:12:23] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[04:12:23] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[04:12:23] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[04:12:23] [INFO]   📊 Citation graph: no citations found in the text.

[04:12:23] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[04:12:23] [SUCCESS] ✅ Conversion complete.

[04:12:40] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\logs\quality_report.json

[04:12:40] [INFO] 

[04:12:40] [INFO] ━━━ Thermal Safety Report ━━━

[04:12:40] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[04:12:40] [INFO]   Session duration: 29.5 min

[04:12:40] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[04:12:40] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[04:12:40] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[04:12:40] [INFO] 

[04:12:40] [INFO] ━━━ Elixir v0.5.9 Conversion Diagnostic Summary ━━━

[04:12:40] [INFO]   Book: Broken Structures Salman Akhtar

[04:12:40] [INFO]   Total pages: 397

[04:12:40] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[04:12:40] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[04:12:40] [INFO]   Summaries generated: 1

[04:12:40] [INFO]     Success: 1, Failed: 0, Total bullets: 72

[04:12:40] [INFO]     Coverage: 94%

[04:12:40] [INFO]     Recall floor (deterministic, final set): theorists 53/74 (72%), conclusion items 3/3 (100%)

[04:12:40] [INFO]   Warnings: 0

[04:12:40] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar

[04:12:40] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.9_20260927-033500-3f0912c0.conversion.log.md

[04:12:40] [INFO]   Diagnostic JSONL: None

[04:12:40] [INFO]   Summary files (3):

[04:12:40] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.9_20260927-033500-3f0912c0_summary.md — generated-by v0.5.9 | run_id=20260927-033500-3f0912c0 | started=2026-09-27T03:43:07 | bullets=72

[04:12:40] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.9 | run_id=20260927-033500-3f0912c0 | started=2026-09-27T03:43:07 | bullets=72

[04:12:40] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.9_20260927-033500-3f0912c0.summary.md — generated-by v0.5.9 | run_id=20260927-033500-3f0912c0 | started=2026-09-27T03:43:07 | bullets=72

[04:12:40] [INFO]   Models loaded at exit: (none — all unloaded)

[04:12:40] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[04:12:40] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[04:12:40] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[04:12:40] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[04:12:40] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[04:12:40] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[04:12:40] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[04:12:40] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\images

[04:12:40] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[04:12:46] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\images

[04:12:52] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[04:12:52] [INFO]   [pipeline] after de-dup: 2 regions

[04:12:53] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.9\Broken Structures Salman Akhtar\regions

[04:12:53] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[04:12:54] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 72 keypoints)


---
Finished at: 2026-09-27T04:12:54.022017
