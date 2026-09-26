# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T06:53:12.211511

<!-- generated-by: Elixir v0.4.39 | run_id=20260926-065312-42c42ba4 -->

---

[06:53:12] [SUCCESS] 🚀 Starting conversion…

[06:53:12] [DEBUG]   🔍 importing 'pypdf'…

[06:53:12] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[06:53:12] [DEBUG]   🔍 importing 'pdf2image'…

[06:53:12] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[06:53:12] [DEBUG]   🔍 importing 'tiktoken'…

[06:53:12] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[06:53:12] [DEBUG]   🔍 importing 'markitdown'…

[06:53:14] [DEBUG]   ✅ 'markitdown' ok (2.2s)

[06:53:14] [DEBUG]   🔍 importing 'rapidfuzz'…

[06:53:14] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[06:53:14] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[06:53:14] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[06:53:14] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[06:53:14] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[06:53:14] [DEBUG]   🔍 importing 'torch'…

[06:53:14] [DEBUG]   ✅ 'torch' ok (0.0s)

[06:53:14] [DEBUG]   🔍 importing 'transformers'…

[06:53:27] [DEBUG]   ✅ 'transformers' ok (13.0s)

[06:53:27] [DEBUG]   🔍 importing 'langextract'…

[06:53:27] [DEBUG]   ✅ 'langextract' ok (0.1s)

[06:53:27] [DEBUG]   ✅ Pre-flight dependency check passed

[06:53:27] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[06:53:27] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[06:53:27] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar.pdf

[06:53:27] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar

[06:53:27] [INFO]   Source type: normal_book

[06:53:27] [INFO]   App version: 0.4.39

[06:53:27] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[06:53:27] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[06:53:27] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[06:53:27] [INFO]   Ollama reachable (localhost:11434): True

[06:53:27] [INFO]   Provider: llamacpp

[06:53:27] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[06:53:27] [INFO]   [Phase 1 (Extraction)]

[06:53:27] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[06:53:27] [INFO]   [Phase 2 (Summarization)]

[06:53:27] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[06:53:27] [INFO]   ────────────────────────────────────────

[06:53:27] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[06:53:27] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[06:53:27] [INFO] ━━━━━━━━━━━━━━━━━━━━

[06:53:27] [INFO]   LLM OCR: True, Force OCR all: False

[06:53:27] [INFO]   Auto-detect scanned: True

[06:53:27] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[06:53:27] [INFO]   OCR retries: 2, Image max size: 1200

[06:53:27] [INFO]   Page range: all

[06:53:27] [INFO]   Selected chapters: 1 chapter(s)

[06:53:27] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[06:53:27] [INFO]   Segmentation: auto, Token limit: 2000

[06:53:27] [INFO]   Semantic: True, Page group: 10

[06:53:27] [INFO]   Generate summaries: True

[06:53:27] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[06:53:27] [INFO]   Fast model: , Heavy model: (disabled)

[06:53:27] [INFO]   Workers (requested): 1, Temperature: 0.7

[06:53:27] [INFO]   Self-consistency: False, Coverage threshold: 85%

[06:53:27] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[06:53:27] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[06:53:27] [INFO]   Academic rigor: False

[06:53:27] [INFO]   Max context tokens: 128000

[06:53:27] [INFO]   Max output tokens: 32768

[06:53:27] [INFO]   Keep-alive: 30m

[06:53:27] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[06:53:27] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[06:53:27] [INFO]   Translation: disabled

[06:53:27] [INFO]   Clean markdown: True, Token saver: True

[06:53:27] [INFO]   Content filter: True

[06:53:27] [INFO]   Extract tables: False, Math: False, Figures: False

[06:53:27] [INFO]   Visual-region crops: True

[06:53:27] [INFO]   Layout analysis: False

[06:53:27] [INFO]   DOCX author: Elixir, TOC: True

[06:53:27] [INFO]   Output paths (V7.5 subfolders):

[06:53:27] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[06:53:27] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[06:53:27] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[06:53:27] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\packets

[06:53:27] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\podcast

[06:53:27] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\logs\quality_report.json

[06:53:27] [INFO]   Resume mode: enabled — will skip done chapters

[06:53:27] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[06:53:27] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[06:53:27] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[06:53:27] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[06:53:27] [DEBUG]   💾 Disk space: 24.7 GB free

[06:53:27] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\.checkpoint.json

[06:54:35] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[06:54:35] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[06:54:35] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[06:54:35] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[06:54:35] [INFO] [TOC] Using PDF outlines: 22 entries.

[06:54:35] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[06:54:35] [DEBUG]   [TOC] Entries passed to segmenter: 22

[06:54:35] [DEBUG]   [TOC] - p.7: Table of Contents

[06:54:35] [DEBUG]   [TOC] - p.9: FOREWORD

[06:54:35] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[06:54:35] [DEBUG]   [TOC] … and 19 more

[06:54:35] [INFO]   🎯 User selected 1 chapter(s):

[06:54:35] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[06:54:35] [INFO]   📸 front_cover → front_cover.jpg

[06:54:36] [INFO]   📸 back_cover → back_cover.jpg

[06:54:36] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[06:54:36] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[06:54:36] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[06:54:36] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[06:54:36] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[06:54:37] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[06:54:37] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[06:54:37] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[06:54:38] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[06:54:38] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[06:54:38] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[06:54:38] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[06:54:39] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[06:54:39] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[06:54:39] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[06:54:39] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[06:54:40] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[06:54:40] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[06:54:40] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[06:54:40] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[06:54:40] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[06:54:41] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[06:54:41] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[06:54:41] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[06:54:41] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[06:54:41] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[06:54:41] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[06:54:41] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[06:54:41] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[06:54:41] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[06:54:41] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[06:54:41] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[06:54:41] [INFO]   ✅ markitdown ready for digital-page extraction

[06:54:41] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[06:54:42] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[06:54:42] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[06:54:42] [INFO]      Pages needing OCR: [152, 153, 154]

[06:54:42] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[06:54:42] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[06:54:42] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[06:54:44] [INFO]   📄 140/397 pages processed (35%)

[06:54:50] [INFO]   🔍 OCR  page 152/397 (scanned)…

[06:54:53] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[06:55:24] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[06:55:24] [INFO]   🔍 OCR  page 153/397 (scanned)…

[06:55:48] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[06:55:48] [INFO]   🔍 OCR  page 154/397 (scanned)…

[06:56:21] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[06:56:25] [INFO]   📄 160/397 pages processed (40%)

[06:56:25] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[06:56:25] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[06:56:25] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[06:56:25] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[06:56:25] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[06:56:25] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[06:56:25] [INFO] 📝 Raw markdown: 53,157 chars | [193.0s]

[06:56:25] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[06:56:25] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[06:56:25] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[06:56:25] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[06:56:25] [INFO] [Segmenter] Attempting chapter-level segmentation…

[06:56:25] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[06:56:25] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[06:56:25] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[06:56:25] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[06:56:25] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[06:56:25] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[06:56:25] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[06:56:25] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[06:56:25] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[06:56:25] [INFO]   📑 Filtered segments: kept 1 of 17

[06:56:25] [INFO] 📚 1 segment(s) detected | [193.1s]

[06:56:25] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[06:56:25] [INFO] 🌐 Detected language: en

[06:56:25] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[06:56:25] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[06:56:25] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\markdown\chapters

[06:56:25] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[06:56:25] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\markdown\chapters

[06:56:25] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[06:56:25] [INFO]   ⏱️ Summary phase starting | [193.5s]

[06:56:27] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[06:56:27] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[06:56:27] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[06:56:27] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[06:56:27] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[06:56:27] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[06:56:27] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[06:56:27] [INFO]   🌡️ Pre-flight: idle GPU temp = 65°C

[06:56:27] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 65°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[06:56:27] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[06:56:27] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[06:56:27] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[06:56:27] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[06:56:27] [DEBUG]   🎛️ Model profile: Default

[06:56:27] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[06:56:28] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[06:56:28] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[06:56:28] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[06:56:28] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[06:56:28] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[06:56:28] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[06:56:28] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[06:56:28] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[06:56:28] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[06:56:28] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[06:56:28] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[06:56:28] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[06:56:28] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[06:56:28] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[06:56:28] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[06:56:28] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[06:56:28] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[06:56:28] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[06:56:28] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[06:56:28] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[06:56:28] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\439

[06:56:28] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[06:56:28] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[06:56:28] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[06:56:28] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[06:56:28] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[06:56:28] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[06:56:28] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[06:56:28] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[06:56:28] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[06:56:28] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[06:57:58] [INFO]     ✅ V0.3 Call 1/3: master summary = 872 words, 6807 chars

[06:57:58] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[06:57:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[06:57:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[06:58:43] [INFO]     ✅ V0.3 Call 2/3: 29 bullets derived from master summary

[06:58:43] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[06:58:43] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[06:58:43] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[06:59:03] [INFO]     ✅ V0.3 Call 3/3: exec summary = 261 words

[06:59:03] [DEBUG]     📝 Parsed: exec=2160 chars, bullets=29, thorough=6807 chars

[06:59:24] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[06:59:26] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[06:59:26] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 28)

[06:59:26] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.numeric_verify': 1}

[06:59:26] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (28 bullets, 261 exec words, 872 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[06:59:28] [DEBUG]     🔍 Fact-check: all 28 bullets verified ✓

[06:59:28] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[06:59:28] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[06:59:28] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[07:00:19] [INFO]     ✅ Additive sections via followup call: key_distinctions=1654 chars, theoretical_tensions=1148 chars

[07:00:19] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (28 bullets, 261 exec words, 872 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[07:00:19] [INFO]     V0.05: Skipping bullet expansion — 28 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[07:00:19] [INFO]     ✅ Final coverage 100%

[07:00:19] [DEBUG]     📏 F1: exec=261w, thorough=872w (source=7405w; targets exec<=250w, thorough<=3332w)

[07:02:01] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[07:02:01] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 21.3 (diff: -5.1)

[07:02:01] [INFO]     ℹ️ F3: Summary is 5.0 grade levels denser than source — expected for a compressed academic summary.

[07:02:03] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[07:02:03] [DEBUG]     🔄 J2: 18 cross-section redundancy(ies) found (exec↔bullets: 8, bullets↔thorough: 9)

[07:02:03] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[07:02:03] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[07:02:03] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[07:02:03] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[07:02:16] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3360 per-pair calls)

[07:02:16] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[07:02:18] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (28/28 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[07:02:18] [INFO]   ℹ️ Summary has substantial content (exec=2160 chars, thorough=6803 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[07:02:18] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[07:02:18] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[07:02:18] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[07:02:18] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[07:02:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:02:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[07:03:38] [INFO]     📜 Scholar response truncated — one additive continuation retry (V18.20.4.12 / O-a4)

[07:03:38] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:03:38] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[07:04:11] [DEBUG]     🎓 Dropped ungrounded gap-fill: Missing secondary authors: Salzman, Stanton, Millon, Jacobso…

[07:04:11] [DEBUG]     🎓 Dropped gap-fill without quote: Millon (1981) categorized features into four areas: vigilanc…

[07:04:11] [DEBUG]     🎓 Dropped gap-fill without quote: Cameron (1963) outlined four aspects: hypersensitivity to ot…

[07:04:11] [DEBUG]     🧹 Filtered 5 thinking + 0 narrative bullets + 0 truncated (kept 24)

[07:04:11] [INFO]     📋 Quarantine: 6 bullet drop(s) recorded. Stages: {'thinking_filter.numeric_verify': 1, 'thinking_filter.truncated': 1, 'thinking_filter.summary_self_assessment': 4}

[07:04:11] [INFO]     🧩 V18.20.3.4: Filtered 5 thinking/scar bullet(s) from scholar gap-fill before merge

[07:04:11] [INFO]     🎓 Gap-fill: added 24 new bullet(s) from scholar reflection (source-grounded)

[07:04:11] [INFO]     🎓 Scholar reflection: identified 12 gap(s), filled 24 with new bullets

[07:04:11] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[07:04:11] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[07:04:12] [DEBUG]     🧹 Semantic dedup: removing bullet 48 (sim=0.92 with bullet 14)

[07:04:12] [DEBUG]     🧹 Semantic dedup: removing bullet 49 (sim=0.94 with bullet 38)

[07:04:12] [DEBUG]     🧹 Semantic dedup: removing bullet 51 (sim=0.97 with bullet 19)

[07:04:12] [INFO]     🧹 Semantic dedup: 52 → 49 bullets (removed 3 semantic duplicates)

[07:04:12] [DEBUG]     🧹 V16.0.2 Bullet normalization: 49 bullets normalized

[07:04:12] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[07:04:12] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\439

[07:04:12] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[07:04:12] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[07:04:12] [INFO]     🔧 Bullet consolidation SKIPPED — deterministic probe found 0 mergeable pairs (49 bullets, LLM call not needed; rig .3.7-.3.9: the LLM merged 0 on the same input shape)

[07:04:12] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\439

[07:04:12] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[07:04:12] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[07:04:12] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Jacobson', 'Polatin', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Bergman', 'Erikson', 'Bursten', 'Wurmser', 'Lowenthal', 'Morey']/74 authors in bullets (35%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Thomson', 'Cameron']

[07:04:12] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Bach', 'Roth', 'Slater', 'Erikson', 'Bursten']/74 authors in thorough (41%) — MISSING from thorough: ['Stanton', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[07:04:12] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Thomson', 'Cameron']…

[07:04:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:04:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[07:04:32] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[07:04:32] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne: Co-authored descriptions of the behavioral correlates of splitt…

[07:04:32] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 6/8 bullets

[07:04:32] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (19.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=1, added=6

[07:04:32] [DEBUG]     📊 V18.14.1: After round 1, 37 still missing from bullets: ['Kernberg', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[07:04:32] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[07:04:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:04:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[07:04:47] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[07:04:47] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur is mentioned alongside Croewe (1975) as an author whose textbo…

[07:04:47] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kendler et al. (1984) and Kendler and Grunberger (1982) are cited as f…

[07:04:47] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 5/8 bullets

[07:04:47] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (15.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[07:04:47] [DEBUG]     📊 V18.14.1: After round 2, 30 still missing from bullets: ['Volkan', 'Winokur', 'Kendler', 'Mahler', 'Anthony']…

[07:04:47] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Volkan', 'Winokur', 'Kendler', 'Mahler', 'Anthony']…

[07:04:47] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:04:47] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[07:05:02] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[07:05:02] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) are noted as offering less clarity in their …

[07:05:02] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is included am…

[07:05:02] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited as part of th…

[07:05:02] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 4/8 bullets

[07:05:02] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[07:05:02] [INFO]     🔁 V18.20.3.7: 'Volkan' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[07:05:02] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[07:05:02] [DEBUG]     📊 V18.14.1: After round 3, 25 still missing from bullets: ['Volkan', 'Winokur', 'Anthony', 'Kohut', 'Allodi']…

[07:05:02] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Volkan', 'Winokur', 'Anthony', 'Kohut', 'Allodi']… (mention-only: ['Volkan', 'Winokur'])

[07:05:02] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:05:02] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[07:05:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[07:05:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1975, with Croewe; 1985) is referenced among descriptions tha…

[07:05:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited in the context of differentiating reactive or acu…

[07:05:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is cited in the context of differentiating reactive or ac…

[07:05:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is cited as part of the broad…

[07:05:15] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 3/8 bullets

[07:05:15] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (13.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=5, added=3

[07:05:15] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Volkan' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[07:05:15] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Winokur' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[07:05:15] [DEBUG]     📊 V18.14.1: After round 4, 22 still missing from bullets: ['Volkan', 'Winokur', 'Jack', 'Ndtei', 'Green']…

[07:05:15] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[07:05:16] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:05:16] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited in the source text as part of a list of authoriti…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is referenced alongside other sources to support the diff…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is included in a list of work…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is cited as part of a collection …

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is mentioned in a l…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mackinnon and Michels (1971) are noted for recognizing fearful avoidan…

[07:05:33] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Stone (1980) is cited for describing a “phobic-anxious” personality ch…

[07:05:33] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 1/8 bullets

[07:05:33] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (17.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=7, added=1

[07:05:33] [INFO]     🔁 V18.20.3.7: 'Jack' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[07:05:33] [INFO]     🔁 V18.20.3.7: 'Ndtei' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[07:05:33] [INFO]     🔁 V18.20.3.7: 'Green' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[07:05:33] [DEBUG]     📊 V18.14.1: After round 5, 20 still missing from bullets: ['Volkan', 'Winokur', 'Jack', 'Ndtei', 'Green']…

[07:05:33] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 19 bullets across 5 round(s)

[07:05:33] [WARNING]     ⚠️ V18.14.1: 20 theorists still missing from bullets after gap-fill: ['Volkan', 'Winokur', 'Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Mackinnon and Michels'] — of these, 2 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Volkan', 'Winokur'] — 18 never covered (round cap/deadline): ['Jack', 'Ndtei', 'Green', 'Pao', 'Socarides', 'Mackinnon and Michels', 'Stone', 'Conlon']

[07:05:33] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[07:05:33] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[07:05:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[07:05:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[07:05:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[07:05:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[07:05:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[07:05:34] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\439

[07:05:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[07:05:34] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[07:05:37] [INFO]     ℹ️ V0.4.23: 73 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[07:05:37] [INFO]     🛡️ V18.2.13 Post-checks: 20 fixed, 6 flagged (of 73 bullets + exec + thorough)

[07:05:37] [DEBUG]       [attribution/flag] bullet[28]: attribution mismatch: summary's claim about 'Magnan (1893)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Magnan (1893) described a subt…

[07:05:37] [DEBUG]       [consistency/flag] bullet[39]: false 'missing' claim: 'Missing' followed by 'DSM sub-criteria details and specific om' — but 4/5 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  Missing DSM sub-criteria detai…

[07:05:37] [DEBUG]       [consistency/flag] bullet[40]: false 'missing' claim: 'Missing' followed by 'differential diagnosis specifics for pho' — but 5/6 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  Missing differential diagnosis…

[07:05:37] [DEBUG]       [consistency/flag] bullet[41]: false 'missing' claim: 'Missing' followed by 'developmental/lifespan details and sex-r' — but 5/6 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  Missing developmental/lifespan…

[07:05:37] [DEBUG]       [space/fix] bullet[54]: split 'review' -> 're view' (source-validated)  |  …that was part of a literature review finding no citations sp…

[07:05:37] [DEBUG]       [parenthetical_promotion/fix] bullet[54]: dropped misattributed bullet: 'Byrne' is credited with a claim the source attributes to 'Socarides’s' ('Byrne' appears there only as a citation/list item). Verified via the generation-time active-subject veto.  |  Akhtar and Byrne: Described the behavioral correlates of spl

[07:05:37] [DEBUG]       [truncated/flag] bullet[71]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[07:05:37] [DEBUG]       [truncated/flag] bullet[73]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[07:05:37] [DEBUG]       [quote_verification/fix] bullet[35]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  bear grudges or are unforgiving of insults or slights,

[07:05:37] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   These perspectives identify nine core features, including p

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   which metaphorically frames the paranoid individual’s exper

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by sudden onset and a 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to Kraepelin (1905, 1921a), who defined the 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   or paranoid personality as an individual who is 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Subsequent contributors such as Bleuler (1908), Kretschmer 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   types and the paranoid individual’s biased, autistic-like i

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and the lack of internalization of the comforting mother. T

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (e.g., arrogance, mistrust, industrial success) and 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (e.g., timidity, gullibility, vulnerability to erotomania) 

[07:05:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   The authors caution that this profile may be difficult for 

[07:05:37] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ): This distinction is described as largely quantitative, wh

[07:05:37] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   state characterized by diffuse suspicions that retain a 

[07:05:37] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   rooted in innate aggression and actual threats to survival,

[07:05:37] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  continued to exist independently,

[07:05:37] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[07:05:37] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 3 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian libidinal theory vs. object-relations/environment

[07:05:37] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 30/74 authors in thorough — MISSING from thorough: ['Stanton', 'Thomson', 'Frances', 'Byrne', 'Akhtar and Byrne']

[07:05:37] [WARNING]   ⏱️⚠️ Deadline exceeded (549s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[07:05:37] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 44 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[07:05:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:05:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[07:06:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stanton (1978) highlighted a critical paradox within the paranoid char…" — its name(s) never co-occur with the claim's key phrases in the source

[07:06:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Salzman (1974) similarly emphasized the internal conflict of this diso…" — its name(s) never co-occur with the claim's key phrases in the source

[07:06:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Volkan (1986) offered a broader existential perspective, providing ins…" — its name(s) never co-occur with the claim's key phrases in the source

[07:06:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Widiger and Frances (1985), in their major review of recent literature…" — its name(s) never co-occur with the claim's key phrases in the source

[07:06:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:06:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the paranoid adolescent, highlighting how ea…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1969) contributed to the understanding of morbid jealousy as a sp…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mahler’s (1975) theory of separation-individuation was woven into Blum…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bergman and Allodi offered additional descriptive and psychoanalytic p…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack (1978) examined the developmental origins of paranoid traits in c…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:21] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei’s observations further clarified the interpersonal dynamics char…" — its name(s) never co-occur with the claim's key phrases in the source

[07:07:31] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[07:07:31] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the contemporary diagnostic landscape, Siever and Kendler (1987) cr…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Similarly, Frances and Widiger (1985) acknowledged the relative unders…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In terms of psychoanalytic contributions, Mackinnon and Michels provid…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stone (1984) further refined the understanding of paranoid personality…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser (1980) explored the cognitive and affective dimensions of para…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Conlon (1979) contributed to the clinical description by highlighting …" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Reid (1980) examined the developmental precursors of paranoid traits, …" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Lowenthal (1984) integrated psychoanalytic theory with clinical observ…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Croewe (1975) emphasized the paradoxical nature of paranoid behavior, …" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Grunberger (1982) explored the relationship between paranoid personali…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Rettersol (1985) focused on the differential diagnosis between paranoi…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:18] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Morey (1988) synthesized contemporary literature on personality disord…" — its name(s) never co-occur with the claim's key phrases in the source

[07:08:22] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 30/74 → 40/74 (3 chunked call(s), ≤12 names each; 8 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[07:08:23] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 53/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Jack']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[07:08:23] [INFO]     📋 Quarantine: 6 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[07:08:23] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 715s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 715s of the budget.

[07:08:23] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[07:08:23] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":73,"exec_chars":2158,"chapter_done":true}

[07:08:23] [DEBUG]   📊 Progress: 1/1 done | 73 bullets | 2,158 chars exec summary

[07:08:23] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\checkpoints

[07:08:23] [INFO] 📄 Building DOCX report…

[07:08:23] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[07:08:23] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[07:08:23] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.39_20260926-065312-42c42ba4_summary.md + DOCX

[07:08:23] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[07:08:23] [INFO]   🧮 Embedding cache: 63 hits / 30 misses (68% hit-rate), 5000 entries

[07:08:23] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.39_20260926-065312-42c42ba4_summary.md

[07:08:23] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries

[07:08:23] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[07:08:23] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.39_20260926-065312-42c42ba4.summary.md

[07:08:23] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[07:08:23] [INFO]   ⏱️ DOCX phase starting | [911.2s]

[07:08:23] [INFO] 📄 Building DOCX report…

[07:08:23] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[07:08:23] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[07:08:26] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[07:08:28] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[07:10:15] [INFO]   🎯 K1+Classification: 73 bullets — 15 core, 42 supporting, 16 additional

[07:10:15] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[07:10:15] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[07:10:15] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[07:10:15] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[07:10:15] [INFO]   📊 Citation graph: no citations found in the text.

[07:10:15] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[07:10:15] [SUCCESS] ✅ Conversion complete.

[07:10:31] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\logs\quality_report.json

[07:10:31] [INFO] 

[07:10:31] [INFO] ━━━ Thermal Safety Report ━━━

[07:10:31] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[07:10:31] [INFO]   Session duration: 14.1 min

[07:10:31] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[07:10:31] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[07:10:31] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[07:10:31] [INFO] 

[07:10:31] [INFO] ━━━ Elixir v0.4.39 Conversion Diagnostic Summary ━━━

[07:10:31] [INFO]   Book: Broken Structures Salman Akhtar

[07:10:31] [INFO]   Total pages: 397

[07:10:31] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[07:10:31] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[07:10:31] [INFO]   Summaries generated: 1

[07:10:31] [INFO]     Success: 1, Failed: 0, Total bullets: 73

[07:10:31] [INFO]     Coverage: 94%

[07:10:31] [INFO]     Recall floor (deterministic, final set): theorists 53/74 (72%), conclusion items 3/3 (100%)

[07:10:31] [INFO]   Warnings: 0

[07:10:31] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar

[07:10:31] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.39_20260926-065312-42c42ba4.conversion.log.md

[07:10:31] [INFO]   Diagnostic JSONL: None

[07:10:31] [INFO]   Summary files (3):

[07:10:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.39_20260926-065312-42c42ba4_summary.md — generated-by v0.4.39 | run_id=20260926-065312-42c42ba4 | started=2026-09-26T06:56:27 | bullets=73

[07:10:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.39 | run_id=20260926-065312-42c42ba4 | started=2026-09-26T06:56:27 | bullets=73

[07:10:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.39_20260926-065312-42c42ba4.summary.md — generated-by v0.4.39 | run_id=20260926-065312-42c42ba4 | started=2026-09-26T06:56:27 | bullets=73

[07:10:31] [INFO]   Models loaded at exit: (none — all unloaded)

[07:10:31] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[07:10:31] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[07:10:31] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[07:10:31] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[07:10:31] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[07:10:31] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[07:10:31] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[07:10:31] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\images

[07:10:31] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[07:10:37] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\images

[07:10:42] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[07:10:42] [INFO]   [pipeline] after de-dup: 2 regions

[07:10:43] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\439\Broken Structures Salman Akhtar\regions

[07:10:43] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[07:10:43] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 73 keypoints)


---
Finished at: 2026-09-26T07:10:43.564554
