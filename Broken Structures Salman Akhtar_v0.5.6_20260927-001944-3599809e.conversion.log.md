# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T00:19:44.896267

<!-- generated-by: Elixir v0.5.6 | run_id=20260927-001944-3599809e -->

---

[00:19:44] [SUCCESS] 🚀 Starting conversion…

[00:19:44] [DEBUG]   🔍 importing 'pypdf'…

[00:19:44] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[00:19:44] [DEBUG]   🔍 importing 'pdf2image'…

[00:19:44] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[00:19:44] [DEBUG]   🔍 importing 'tiktoken'…

[00:19:44] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[00:19:44] [DEBUG]   🔍 importing 'markitdown'…

[00:19:46] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[00:19:46] [DEBUG]   🔍 importing 'rapidfuzz'…

[00:19:46] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[00:19:46] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[00:19:46] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[00:19:46] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[00:19:46] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[00:19:46] [DEBUG]   ✅ 'torch' installed

[00:19:46] [DEBUG]   ✅ 'transformers' installed

[00:19:46] [DEBUG]   ✅ 'langextract' installed

[00:19:46] [DEBUG]   ✅ Pre-flight dependency check passed

[00:19:46] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[00:19:46] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[00:19:46] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar.pdf

[00:19:46] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar

[00:19:46] [INFO]   Source type: normal_book

[00:19:46] [INFO]   App version: 0.5.6

[00:19:46] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[00:19:46] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[00:19:46] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[00:19:46] [INFO]   Ollama reachable (localhost:11434): True

[00:19:46] [INFO]   Provider: llamacpp

[00:19:46] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[00:19:46] [INFO]   [Phase 1 (Extraction)]

[00:19:46] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[00:19:46] [INFO]   [Phase 2 (Summarization)]

[00:19:46] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[00:19:46] [INFO]   ────────────────────────────────────────

[00:19:46] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[00:19:46] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[00:19:46] [INFO] ━━━━━━━━━━━━━━━━━━━━

[00:19:46] [INFO]   LLM OCR: True, Force OCR all: False

[00:19:46] [INFO]   Auto-detect scanned: True

[00:19:46] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:19:46] [INFO]   OCR retries: 2, Image max size: 1200

[00:19:46] [INFO]   Page range: all

[00:19:46] [INFO]   Selected chapters: 1 chapter(s)

[00:19:46] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[00:19:46] [INFO]   Segmentation: auto, Token limit: 2000

[00:19:46] [INFO]   Semantic: True, Page group: 10

[00:19:46] [INFO]   Generate summaries: True

[00:19:46] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:19:46] [INFO]   Fast model: , Heavy model: (disabled)

[00:19:46] [INFO]   Workers (requested): 1, Temperature: 0.7

[00:19:46] [INFO]   Self-consistency: False, Coverage threshold: 95%

[00:19:46] [INFO]   📈 Over-delivery: ENABLED (floor 95% → target 100%)

[00:19:46] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[00:19:46] [INFO]   Academic rigor: False

[00:19:46] [INFO]   Max context tokens: 128000

[00:19:46] [INFO]   Max output tokens: 32768

[00:19:46] [INFO]   Keep-alive: 30m

[00:19:46] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[00:19:46] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[00:19:46] [INFO]   Translation: disabled

[00:19:46] [INFO]   Clean markdown: True, Token saver: True

[00:19:46] [INFO]   Content filter: True

[00:19:46] [INFO]   Extract tables: False, Math: False, Figures: False

[00:19:46] [INFO]   Visual-region crops: True

[00:19:46] [INFO]   Layout analysis: False

[00:19:46] [INFO]   DOCX author: Elixir, TOC: True

[00:19:46] [INFO]   Output paths (V7.5 subfolders):

[00:19:46] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[00:19:46] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[00:19:46] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[00:19:46] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\packets

[00:19:46] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\podcast

[00:19:46] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\logs\quality_report.json

[00:19:46] [INFO]   Resume mode: enabled — will skip done chapters

[00:19:46] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[00:19:46] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[00:19:46] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[00:19:46] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[00:19:46] [DEBUG]   💾 Disk space: 22.9 GB free

[00:19:47] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\.checkpoint.json

[00:20:44] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[00:20:44] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[00:20:44] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[00:20:44] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[00:20:44] [INFO] [TOC] Using PDF outlines: 22 entries.

[00:20:44] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[00:20:44] [DEBUG]   [TOC] Entries passed to segmenter: 22

[00:20:44] [DEBUG]   [TOC] - p.7: Table of Contents

[00:20:44] [DEBUG]   [TOC] - p.9: FOREWORD

[00:20:44] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[00:20:44] [DEBUG]   [TOC] … and 19 more

[00:20:44] [INFO]   🎯 User selected 1 chapter(s):

[00:20:44] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[00:20:44] [INFO]   📸 front_cover → front_cover.jpg

[00:20:44] [INFO]   📸 back_cover → back_cover.jpg

[00:20:44] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[00:20:44] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[00:20:45] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[00:20:45] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[00:20:45] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[00:20:45] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[00:20:45] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[00:20:45] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[00:20:46] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[00:20:46] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[00:20:46] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[00:20:46] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[00:20:46] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[00:20:46] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[00:20:47] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[00:20:47] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[00:20:47] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[00:20:47] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[00:20:48] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[00:20:48] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[00:20:48] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[00:20:48] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[00:20:48] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[00:20:49] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[00:20:49] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[00:20:49] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[00:20:49] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[00:20:49] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[00:20:49] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[00:20:49] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[00:20:49] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[00:20:49] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[00:20:49] [INFO]   ✅ markitdown ready for digital-page extraction

[00:20:49] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[00:20:49] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[00:20:49] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[00:20:49] [INFO]      Pages needing OCR: [152, 153, 154]

[00:20:49] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[00:20:49] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[00:20:49] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[00:20:51] [INFO]   📄 140/397 pages processed (35%)

[00:20:56] [INFO]   🔍 OCR  page 152/397 (scanned)…

[00:21:04] [WARNING]   📸 V0.4.1: No vision-capable model found — will use Tesseract fallback

[00:21:07] [INFO]     ✅ Tesseract p.152: 953 chars

[00:21:07] [INFO]   🔍 OCR  page 153/397 (scanned)…

[00:21:10] [INFO]   🔍 OCR  page 154/397 (scanned)…

[00:21:15] [INFO]     ✅ Tesseract p.154: 871 chars

[00:21:17] [INFO]   📄 160/397 pages processed (40%)

[00:21:17] [WARNING]   ⚠️ 1 page(s) failed to extract: [153]

[00:21:17] [SUCCESS] ✅ PDF processing done: 23/397 pages extracted

[00:21:17] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[00:21:17] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[00:21:17] [DEBUG]   🧹 Header/footer removal: 7 chars stripped

[00:21:17] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[00:21:17] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[00:21:17] [INFO] 📝 Raw markdown: 52,964 chars | [93.1s]

[00:21:17] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[00:21:17] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[00:21:17] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[00:21:18] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[00:21:18] [INFO] [Segmenter] Attempting chapter-level segmentation…

[00:21:18] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[00:21:18] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[00:21:18] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[00:21:18] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[00:21:18] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[00:21:18] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[00:21:18] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[00:21:18] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[00:21:18] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[00:21:18] [INFO]   📑 Filtered segments: kept 1 of 17

[00:21:18] [INFO] 📚 1 segment(s) detected | [93.1s]

[00:21:18] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,968 tokens | p.137–160

[00:21:18] [INFO] 🌐 Detected language: en

[00:21:18] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[00:21:18] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[00:21:18] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\markdown\chapters

[00:21:18] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[00:21:18] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\markdown\chapters

[00:21:18] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (4032 bytes)

[00:21:18] [INFO]   ⏱️ Summary phase starting | [93.5s]

[00:21:20] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[00:21:20] [DEBUG]   ⏭️ Skipping page 152 in summarisation: High density of TOC‑like lines

[00:21:20] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[00:21:20] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[00:21:20] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[00:21:20] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[00:21:20] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[00:21:20] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[00:21:20] [INFO]   🌡️ Pre-flight: idle GPU temp = 62°C

[00:21:20] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 62°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[00:21:20] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[00:21:20] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[00:21:20] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[00:21:20] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[00:21:20] [DEBUG]   🎛️ Model profile: Default

[00:21:20] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[00:21:20] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[00:21:22] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[00:21:22] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[00:21:22] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[00:21:22] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[00:21:22] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[00:21:22] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[00:21:22] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[00:21:22] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[00:21:22] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[00:21:22] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[00:21:22] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[00:21:22] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[00:21:22] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[00:21:22] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[00:21:22] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (51893 chars)

[00:21:22] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[00:21:22] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[00:21:22] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[00:21:22] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[00:21:22] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.6

[00:21:22] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[00:21:22] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[00:21:22] [INFO]     📊 V17.2: Prepended deterministic analysis (3901 chars) — citation recall 78%→100%

[00:21:22] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,276 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,276 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[00:21:22] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[00:21:22] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[00:21:22] [INFO]     📦 V0.4: master-summary architecture (default) — input 11276 tok, output cap 32768

[00:21:23] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[00:21:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:21:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:21:27] [WARNING]     ⚠️ llama.cpp streaming transport failed — retrying non-streaming

[00:21:29] [WARNING] ⚠️ LLM call attempt 1 failed (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))) — retrying in 3.63s

[00:21:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:21:34] [WARNING]     ⚠️ llama.cpp streaming transport failed — retrying non-streaming

[00:21:36] [WARNING]     ⚠️ llama.cpp call failed: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))

[00:21:36] [WARNING]     ⚠️ llm_provider returned empty — falling back to inline call

[00:21:36] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:21:39] [WARNING] ⚠️ LLM call attempt 1 failed (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))) — retrying in 2.58s

[00:21:41] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:21:43] [WARNING]     ⚠️ llamacpp call failed: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))

[00:21:43] [WARNING]     ⚠️ Empty/short LLM response — retrying with nudge after 2s delay

[00:21:47] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:21:47] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:21:49] [WARNING]     ⚠️ llama.cpp streaming transport failed — retrying non-streaming

[00:21:51] [WARNING] ⚠️ LLM call attempt 1 failed (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))) — retrying in 3.02s

[00:21:54] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:21:56] [WARNING]     ⚠️ llama.cpp streaming transport failed — retrying non-streaming

[00:21:58] [WARNING]     ⚠️ llama.cpp call failed: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))

[00:21:58] [WARNING]     ⚠️ llm_provider returned empty — falling back to inline call

[00:21:58] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:22:00] [WARNING] ⚠️ LLM call attempt 1 failed (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=8080): Max retries exceeded with url: /v1/chat/completions (Caused by NewConnectionError("HTTPConnection(host='127.0.0.1', port=8080): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))) — retrying in 2.26s

[00:22:03] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:22:03] [WARNING]     ⚠️ llamacpp call failed: 503 Server Error: Service Unavailable for url: http://127.0.0.1:8080/v1/chat/completions

[00:22:03] [WARNING]     ⚠️ V0.3 Call 1/3 (master summary) returned empty — falling back

[00:22:03] [WARNING]     ⚠️ V0.4: master-summary architecture failed — falling back to 5-in-1 single-pass

[00:22:03] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:22:03] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:22:03] [WARNING] ⚠️ LLM call attempt 1 failed (HTTPError: HTTP 503 (unavailable_error): Loading model) — retrying in 3.16s

[00:22:06] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:22:06] [WARNING]     ⚠️ llama.cpp call failed: HTTP 503 (unavailable_error): Loading model

[00:22:06] [WARNING]     ⚠️ llm_provider returned empty — falling back to inline call

[00:22:06] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:22:06] [WARNING] ⚠️ LLM call attempt 1 failed (HTTPError: 503 Server Error: Service Unavailable for url: http://127.0.0.1:8080/v1/chat/completions) — retrying in 2.90s

[00:22:09] [INFO]     ☁️ llamacpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 attempt…

[00:22:09] [WARNING]     ⚠️ llamacpp call failed: 503 Server Error: Service Unavailable for url: http://127.0.0.1:8080/v1/chat/completions

[00:22:10] [WARNING]     ⚠️ Empty/short LLM response — retrying with nudge after 2s delay

[00:22:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:22:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:22:12] [WARNING] ⚠️ LLM call attempt 1 failed (HTTPError: HTTP 503 (unavailable_error): Loading model) — retrying in 3.59s

[00:22:15] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[00:34:19] [DEBUG]     📋 Raw response (first 500 chars): '<executive_summary>\nThis chapter provides a full survey of paranoid personality disorder, combining descriptive psychiatric and psychoanalytic literature to build a complete clinical profile. The author reviews early historical definitions from Magnan to Kraepelin, then moves through mid-century phenomenological and psychoanalytic views. Key contributors include Bleuler, Jaspers, Schneider, Leonhard, Shepherd, and Polatin in the descriptive track, and Freud, Klein, Winnicott, Erikson, Heimann, R'

[00:34:19] [DEBUG]     📝 Parsed: exec=1075 chars, bullets=87, thorough=25205 chars

[00:34:46] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[00:34:47] [DEBUG]     🔍 Coverage detail: 8/8 keywords found | missing: []

[00:34:48] [DEBUG]     🧹 Filtered 6 thinking + 0 narrative bullets + 0 truncated (kept 81)

[00:34:48] [INFO]     📋 Quarantine: 6 bullet drop(s) recorded. Stages: {'thinking_filter.too_long_500chars': 6}

[00:34:48] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (81 bullets, 134 exec words, 3147 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[00:34:50] [DEBUG]     🔍 Fact-check: all 81 bullets verified ✓

[00:34:50] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (81 bullets, 134 exec words, 3147 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[00:34:50] [WARNING]   ⏱️⚠️ Deadline exceeded (807s > 480s) — skipping optional phase: dedicated bullet expansion

[00:34:50] [INFO]     ✅ Final coverage 100%

[00:34:50] [DEBUG]     📏 F1: exec=134w, thorough=3147w (source=7274w; targets exec<=250w, thorough<=3273w)

[00:38:45] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[00:38:45] [DEBUG]     📖 F3: Reading level — source: 16.1, summary: 21.1 (diff: -5.0)

[00:38:45] [INFO]     ℹ️ F3: Summary is 5.0 grade levels denser than source — expected for a compressed academic summary.

[00:38:46] [DEBUG]     📊 I2: Chapter difficulty 0.58/1.0 (grade 16.1, strategy: multi_sample)

[00:38:46] [DEBUG]     🔄 J2: 64 cross-section redundancy(ies) found (exec↔bullets: 0, bullets↔thorough: 64)

[00:38:46] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 2 markers)

[00:38:46] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[00:38:46] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[00:38:46] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[00:38:58] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 9296 per-pair calls)

[00:38:58] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[00:39:09] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (81/81 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[00:39:09] [INFO]   ℹ️ Summary has substantial content (exec=1075 chars, thorough=25205 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[00:39:09] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[00:39:09] [WARNING]   ⏱️⚠️ Deadline exceeded (1067s > 480s) — skipping optional phase: scholar reflection

[00:39:09] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[00:39:09] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[00:39:09] [WARNING]   ⏱️⚠️ Deadline exceeded (1067s > 480s) — skipping optional phase: semantic dedup

[00:39:09] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[00:39:09] [DEBUG]     🧹 V16.0.2 Bullet normalization: 81 bullets normalized

[00:39:10] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[00:39:10] [WARNING]   ⏱️⚠️ Deadline exceeded (1067s > 480s) — skipping optional phase: bullet consolidation

[00:39:10] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[00:39:10] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.6

[00:39:10] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[00:39:10] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[00:39:10] [INFO]     📊 V18.14 Bullets-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Widiger', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Widiger and Frances', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Anthony', 'Kohut', 'Bach', 'Fenichel', 'Bergman', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Frances and Widiger', 'Mackinnon and Michels', 'Stone', 'Lowenthal', 'Morey', 'Ovessey', 'Walters', 'Munro', 'Gorton and Akhtar', 'Mackinnon', 'Michels']/75 authors in bullets (77%) — MISSING from bullets: ['Thomson', 'Akhtar and Thomson', 'Winokur', 'Kendler', 'Allodi']

[00:39:10] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances', 'Byrne', 'Akhtar and Byrne', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Widiger', 'Kendler', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Widiger and Frances', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Anthony', 'Kohut', 'Bach', 'Fenichel', 'Bergman', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Frances and Widiger', 'Mackinnon and Michels', 'Stone', 'Conlon', 'Reid', 'Lowenthal', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Munro', 'Siever', 'Mackinnon', 'Michels']/75 authors in thorough (84%) — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Winokur', 'Allodi', 'Jack']

[00:39:10] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Thomson', 'Akhtar and Thomson', 'Winokur', 'Kendler', 'Allodi']…

[00:39:10] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:39:10] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[00:39:25] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[00:39:25] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[00:39:25] [DEBUG]     📊 V18.14.1: After round 1, 7 still missing from bullets: ['Wurmser', 'Conlon', 'Reid', 'Croewe', 'Rettersol']…

[00:39:25] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 7 missing authors: ['Wurmser', 'Conlon', 'Reid', 'Croewe', 'Rettersol']…

[00:39:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:39:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[00:39:35] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)

[00:39:35] [INFO]     📋 Quarantine: 7 bullet drop(s) recorded. Stages: {'thinking_filter.too_long_500chars': 6, 'thinking_filter.truncated': 1}

[00:39:35] [DEBUG]     🎓 V18.12.2: Dropped gap-fill bullet (prompt-leakage/thinking): - Conlon (1984) emphasized it with his mnemonic description …

[00:39:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) are cited as one of the sources that offered…

[00:39:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) is listed alongside other works as a source on parano…

[00:39:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mellsop and Varghesi (1982) are cited among studies referenced in the …

[00:39:35] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1985) is also listed alongside other works as a source on par…

[00:39:35] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 2/7 bullets

[00:39:35] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (10.0s): response=7 bullet lines, dup=0, think-filtered=1, vetoed=0, filler=4, added=2

[00:39:35] [DEBUG]     📊 V18.14.1: After round 2, 5 still missing from bullets: ['Conlon', 'Croewe', 'Rettersol', 'Varghesi', 'Maj sey']

[00:39:35] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 5 missing authors: ['Conlon', 'Croewe', 'Rettersol', 'Varghesi', 'Maj sey']

[00:39:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:39:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[00:39:45] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) are cited as an example of textbook descript…

[00:39:45] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mellsop and Varghesi (1982) are cited jointly with Spitzer et al. as a…

[00:39:45] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) is referenced alongside Winokur (1985) as part of a g…

[00:39:45] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 2/5 bullets

[00:39:45] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (9.4s): response=5 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=2

[00:39:45] [INFO]     🔁 V18.20.3.7: 'Croewe' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[00:39:45] [INFO]     🔁 V18.20.3.7: 'Varghesi' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[00:39:45] [INFO]     🔁 V18.20.3.7: 'Maj sey' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[00:39:45] [DEBUG]     📊 V18.14.1: After round 3, 3 still missing from bullets: ['Croewe', 'Varghesi', 'Maj sey']

[00:39:45] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 3 missing authors: ['Croewe', 'Varghesi', 'Maj sey'] (mention-only: ['Croewe', 'Varghesi', 'Maj sey'])

[00:39:45] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:39:45] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[00:39:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mellsop and Varghesi (1982) conducted studies that were cited alongsid…

[00:39:51] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 2/3 bullets

[00:39:51] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (6.6s): response=3 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=2

[00:39:51] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Maj sey' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[00:39:51] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Varghesi' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[00:39:51] [DEBUG]     📊 V18.14.1: After round 4, 2 still missing from bullets: ['Varghesi', 'Maj sey']

[00:39:51] [INFO]     ⏹️  V18.20.3.4: No actionable authors left for gap-fill (2 persistent-veto author(s) given up): ['Maj sey', 'Varghesi']

[00:39:51] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 14 bullets across 5 round(s)

[00:39:51] [WARNING]     ⚠️ V18.14.1: 2 theorists still missing from bullets after gap-fill: ['Varghesi', 'Maj sey'] — of these, 2 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Varghesi', 'Maj sey']

[00:39:51] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[00:39:51] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[00:39:51] [DEBUG]     ✅ V0.4.23: enumeration guarantee — all 43 item(s) across 9 detected list(s) already covered (no bullets added)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 2 (sim=0.86 with bullet 1)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 39 (sim=0.85 with bullet 38)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 46 (sim=0.85 with bullet 45)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 50 (sim=0.86 with bullet 49)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 63 (sim=0.85 with bullet 1)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 67 (sim=0.88 with bullet 66)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 71 (sim=0.87 with bullet 69)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 83 (sim=0.93 with bullet 82)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 86 (sim=0.85 with bullet 62)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 87 (sim=0.85 with bullet 62)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 89 (sim=0.88 with bullet 85)

[00:39:52] [DEBUG]     🧹 Semantic dedup: removing bullet 94 (sim=0.87 with bullet 14)

[00:39:52] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 96 → 84 bullets (removed 12 gap-fill/conclusion duplicates; 1.0s, non-skippable per V18.20.3.4)

[00:39:52] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.6

[00:39:52] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[00:39:52] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3901 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[00:39:56] [INFO]     🛡️ V18.2.13 Post-checks: 15 fixed, 9 flagged (of 83 bullets + exec + thorough)

[00:39:56] [DEBUG]       [sentence_fusion/flag] bullet[16]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[00:39:56] [DEBUG]       [sentence_fusion/flag] bullet[17]: likely source-propagated fusion garble: 'selfrighteousness' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'righteousness' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-righteousness').  |  endacity with moralistic selfrighteousness in the paranoid characte

[00:39:56] [DEBUG]       [sentence_fusion/flag] bullet[37]: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  ighly structuralized and ego-syntonically embedded; core consists 

[00:39:56] [DEBUG]       [attribution/flag] bullet[65]: attribution mismatch: summary's claim about 'Kohut (1972)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …stic rage when pride injured (Kohut 1972); both display pred…

[00:39:56] [DEBUG]       [attribution/flag] bullet[81]: attribution mismatch: summary's claim about 'Rettersol (1985)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Rettersol (1985) is identified…

[00:39:56] [DEBUG]       [consistency/flag] exec: false 'missing' claim: 'missing' followed by 'core contradictions such as gullibility ' — but 7/7 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …-R criteria are critiqued for missing core contradictions su…

[00:39:56] [DEBUG]       [sentence_fusion/flag] thorough: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[00:39:56] [DEBUG]       [sentence_fusion/flag] thorough: likely source-propagated fusion garble: 'selfrighteousness' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'righteousness' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-righteousness').  |  endacity with moralistic selfrighteousness. The descriptive summary

[00:39:56] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  ighly structuralized and ego-syntonically embedded; core consists 

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   behind short-term paranoid developments showing idiosyncrat

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   in two types: combative (unpleasantly insistent, actively q

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the earliest developmental constellation of infantile ob

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as menace; maternal failures lead to disruption, anxiety, i

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects for projection, yet remain infiltrated wit

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   clues combined with loss of appreciation of context that gi

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   involves preoedipal problems. Interweaving Mahler's (1975) 

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   — ambivalently loved object felt both persecutory and neede

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   is improvement. However, both do not include superego uneve

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   that Bach (1977) noted. Risk exists that overt and covert g

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality. Phobic characters differ from paranoid persona

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   while paranoid feeling is 

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ; phobic lacks personalization and intentionality of outside

[00:39:56] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (Akhtar 1986) of phobic neurosis proper; paranoid personali

[00:39:56] [DEBUG]       [near_duplicate/fix] bullet[83]: near-duplicate of bullet[54] (token-set containment >= 0.8) — kept the first, dropped this one  |  **Conclusions**: (1) includes both phenomenological and psyc

[00:39:56] [INFO]     ℹ️ V0.4.23: 83 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[00:39:56] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 63/75 authors in thorough — MISSING from thorough: ['Thomson', 'Akhtar and Thomson', 'Winokur', 'Allodi', 'Jack']

[00:39:56] [WARNING]   ⏱️⚠️ Deadline exceeded (1113s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[00:39:56] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 12 of 75 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[00:39:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[00:39:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In addressing the specific clinical presentations that complicate diff…" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This distinction is critical when differentiating these transient stat…" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the realm of cognitive style and defensive elaboration, Wurmser (19…" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The therapeutic and developmental implications of these dynamics were …" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Gorton and Akhtar (1990) conducted a systematic review of the literatu…" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Thomson (1975) offered insights into the developmental origin…" — its name(s) never co-occur with the claim's key phrases in the source

[00:40:40] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 63/75 → 63/75 (1 chunked call(s), ≤12 names each)

[00:40:40] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 69/75 in final bullets (missing: ['Allodi', 'Jack', 'Siever and Kendler', 'Varghesi', 'Maj sey']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[00:40:40] [INFO]     📋 Quarantine: 7 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[00:40:40] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 1158s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 1158s of the budget.

[00:40:40] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[00:40:40] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":83,"exec_chars":1075,"chapter_done":true}

[00:40:40] [DEBUG]   📊 Progress: 1/1 done | 83 bullets | 1,075 chars exec summary

[00:40:40] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\checkpoints

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '2007' (ce:2007) NOT found in summary — possible omission.

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[00:40:40] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting: 2 source author(s) NOT found in the summary (Allodi, Jack). Added to the LLM verification prompt.

[00:40:40] [INFO] 📄 Building DOCX report…

[00:40:40] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[00:40:41] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[00:40:41] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.6_20260927-001944-3599809e_summary.md + DOCX

[00:40:41] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[00:40:41] [INFO]   🧮 Embedding cache: 63 hits / 83 misses (43% hit-rate), 5000 entries

[00:40:41] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.6_20260927-001944-3599809e_summary.md

[00:40:41] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries

[00:40:41] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[00:40:41] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.6_20260927-001944-3599809e.summary.md

[00:40:41] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[00:40:41] [INFO]   ⏱️ DOCX phase starting | [1256.2s]

[00:40:41] [INFO] 📄 Building DOCX report…

[00:40:41] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[00:40:41] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[00:40:42] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[00:40:43] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[00:42:29] [INFO]   🎯 K1+Classification: 83 bullets — 11 core, 57 supporting, 15 additional

[00:42:29] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[00:42:29] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[00:42:29] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[00:42:29] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[00:42:29] [INFO]   📊 Citation graph: no citations found in the text.

[00:42:29] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[00:42:29] [SUCCESS] ✅ Conversion complete.

[00:42:41] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\logs\quality_report.json

[00:42:41] [INFO] 

[00:42:41] [INFO] ━━━ Thermal Safety Report ━━━

[00:42:41] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[00:42:41] [INFO]   Session duration: 21.3 min

[00:42:41] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[00:42:41] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[00:42:41] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[00:42:41] [INFO] 

[00:42:41] [INFO] ━━━ Elixir v0.5.6 Conversion Diagnostic Summary ━━━

[00:42:41] [INFO]   Book: Broken Structures Salman Akhtar

[00:42:41] [INFO]   Total pages: 397

[00:42:41] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[00:42:41] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[00:42:41] [INFO]   Summaries generated: 1

[00:42:41] [INFO]     Success: 1, Failed: 0, Total bullets: 83

[00:42:41] [INFO]     Coverage: 100%

[00:42:41] [INFO]     Recall floor (deterministic, final set): theorists 69/75 (92%), conclusion items 3/3 (100%)

[00:42:41] [INFO]   Warnings: 0

[00:42:41] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar

[00:42:41] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.6_20260927-001944-3599809e.conversion.log.md

[00:42:41] [INFO]   Diagnostic JSONL: None

[00:42:41] [INFO]   Summary files (3):

[00:42:41] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.6_20260927-001944-3599809e_summary.md — generated-by v0.5.6 | run_id=20260927-001944-3599809e | started=2026-09-27T00:21:20 | bullets=83

[00:42:41] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.6 | run_id=20260927-001944-3599809e | started=2026-09-27T00:21:20 | bullets=83

[00:42:41] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.6_20260927-001944-3599809e.summary.md — generated-by v0.5.6 | run_id=20260927-001944-3599809e | started=2026-09-27T00:21:20 | bullets=83

[00:42:41] [INFO]   Models loaded at exit: (none — all unloaded)

[00:42:41] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[00:42:41] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[00:42:41] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[00:42:41] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[00:42:41] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[00:42:41] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[00:42:41] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[00:42:41] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\images

[00:42:41] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[00:42:46] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\images

[00:42:52] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[00:42:52] [INFO]   [pipeline] after de-dup: 2 regions

[00:42:52] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.6\Broken Structures Salman Akhtar\regions

[00:42:52] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[00:42:52] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 83 keypoints)


---
Finished at: 2026-09-27T00:42:52.604775
