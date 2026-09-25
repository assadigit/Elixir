# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T02:30:12.974977

<!-- generated-by: Elixir v0.4.36 | run_id=20260926-023012-00c5ef19 -->

---

[02:30:12] [SUCCESS] 🚀 Starting conversion…

[02:30:13] [DEBUG]   🔍 importing 'pypdf'…

[02:30:13] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[02:30:13] [DEBUG]   🔍 importing 'pdf2image'…

[02:30:13] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[02:30:13] [DEBUG]   🔍 importing 'tiktoken'…

[02:30:13] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[02:30:13] [DEBUG]   🔍 importing 'markitdown'…

[02:30:15] [DEBUG]   ✅ 'markitdown' ok (2.6s)

[02:30:15] [DEBUG]   🔍 importing 'rapidfuzz'…

[02:30:15] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[02:30:15] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[02:30:15] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[02:30:15] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[02:30:15] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[02:30:15] [DEBUG]   🔍 importing 'torch'…

[02:30:15] [DEBUG]   ✅ 'torch' ok (0.0s)

[02:30:15] [DEBUG]   🔍 importing 'transformers'…

[02:30:32] [DEBUG]   ✅ 'transformers' ok (17.2s)

[02:30:32] [DEBUG]   🔍 importing 'langextract'…

[02:30:32] [DEBUG]   ✅ 'langextract' ok (0.1s)

[02:30:32] [DEBUG]   ✅ Pre-flight dependency check passed

[02:30:32] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[02:30:32] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[02:30:32] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar.pdf

[02:30:32] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar

[02:30:32] [INFO]   Source type: normal_book

[02:30:32] [INFO]   App version: 0.4.36

[02:30:32] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[02:30:32] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[02:30:32] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[02:30:32] [INFO]   Ollama reachable (localhost:11434): True

[02:30:32] [INFO]   Provider: llamacpp

[02:30:32] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[02:30:32] [INFO]   [Phase 1 (Extraction)]

[02:30:32] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[02:30:32] [INFO]   [Phase 2 (Summarization)]

[02:30:32] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[02:30:32] [INFO]   ────────────────────────────────────────

[02:30:32] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[02:30:32] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[02:30:32] [INFO] ━━━━━━━━━━━━━━━━━━━━

[02:30:32] [INFO]   LLM OCR: True, Force OCR all: False

[02:30:32] [INFO]   Auto-detect scanned: True

[02:30:32] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:30:32] [INFO]   OCR retries: 2, Image max size: 1200

[02:30:32] [INFO]   Page range: all

[02:30:32] [INFO]   Selected chapters: 1 chapter(s)

[02:30:32] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[02:30:32] [INFO]   Segmentation: auto, Token limit: 2000

[02:30:32] [INFO]   Semantic: True, Page group: 10

[02:30:32] [INFO]   Generate summaries: True

[02:30:32] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:30:32] [INFO]   Fast model: , Heavy model: (disabled)

[02:30:32] [INFO]   Workers (requested): 1, Temperature: 0.7

[02:30:32] [INFO]   Self-consistency: False, Coverage threshold: 85%

[02:30:32] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[02:30:32] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[02:30:32] [INFO]   Academic rigor: False

[02:30:32] [INFO]   Max context tokens: 128000

[02:30:32] [INFO]   Max output tokens: 32768

[02:30:32] [INFO]   Keep-alive: 30m

[02:30:33] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[02:30:33] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[02:30:33] [INFO]   Translation: disabled

[02:30:33] [INFO]   Clean markdown: True, Token saver: True

[02:30:33] [INFO]   Content filter: True

[02:30:33] [INFO]   Extract tables: False, Math: False, Figures: False

[02:30:33] [INFO]   Visual-region crops: True

[02:30:33] [INFO]   Layout analysis: False

[02:30:33] [INFO]   DOCX author: Elixir, TOC: True

[02:30:33] [INFO]   Output paths (V7.5 subfolders):

[02:30:33] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[02:30:33] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[02:30:33] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[02:30:33] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\packets

[02:30:33] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\podcast

[02:30:33] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\logs\quality_report.json

[02:30:33] [INFO]   Resume mode: enabled — will skip done chapters

[02:30:33] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[02:30:33] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:30:33] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[02:30:33] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[02:30:33] [DEBUG]   💾 Disk space: 24.9 GB free

[02:30:33] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\.checkpoint.json

[02:31:45] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[02:31:45] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[02:31:45] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[02:31:46] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[02:31:46] [INFO] [TOC] Using PDF outlines: 22 entries.

[02:31:46] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[02:31:46] [DEBUG]   [TOC] Entries passed to segmenter: 22

[02:31:46] [DEBUG]   [TOC] - p.7: Table of Contents

[02:31:46] [DEBUG]   [TOC] - p.9: FOREWORD

[02:31:46] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[02:31:46] [DEBUG]   [TOC] … and 19 more

[02:31:46] [INFO]   🎯 User selected 1 chapter(s):

[02:31:46] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[02:31:46] [INFO]   📸 front_cover → front_cover.jpg

[02:31:46] [INFO]   📸 back_cover → back_cover.jpg

[02:31:46] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[02:31:46] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[02:31:47] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[02:31:47] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[02:31:47] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[02:31:47] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[02:31:47] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[02:31:48] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[02:31:48] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[02:31:48] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[02:31:48] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[02:31:48] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[02:31:49] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[02:31:49] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[02:31:49] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[02:31:49] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[02:31:50] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[02:31:50] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[02:31:50] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[02:31:50] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[02:31:50] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[02:31:51] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[02:31:51] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[02:31:51] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[02:31:51] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[02:31:51] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[02:31:51] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[02:31:51] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[02:31:51] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[02:31:51] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[02:31:51] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[02:31:51] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[02:31:51] [INFO]   ✅ markitdown ready for digital-page extraction

[02:31:51] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[02:31:51] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[02:31:52] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[02:31:52] [INFO]      Pages needing OCR: [152, 153, 154]

[02:31:52] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[02:31:52] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[02:31:52] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[02:31:54] [INFO]   📄 140/397 pages processed (35%)

[02:32:00] [INFO]   🔍 OCR  page 152/397 (scanned)…

[02:32:02] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[02:33:29] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[02:33:29] [INFO]   🔍 OCR  page 153/397 (scanned)…

[02:34:57] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[02:34:57] [INFO]   🔍 OCR  page 154/397 (scanned)…

[02:36:29] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[02:36:33] [INFO]   📄 160/397 pages processed (40%)

[02:36:33] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[02:36:33] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[02:36:33] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[02:36:33] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[02:36:33] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[02:36:33] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[02:36:33] [INFO] 📝 Raw markdown: 53,157 chars | [380.1s]

[02:36:33] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[02:36:33] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[02:36:33] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[02:36:33] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[02:36:33] [INFO] [Segmenter] Attempting chapter-level segmentation…

[02:36:33] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[02:36:33] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[02:36:33] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[02:36:33] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[02:36:33] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[02:36:33] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[02:36:33] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[02:36:33] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[02:36:33] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[02:36:33] [INFO]   📑 Filtered segments: kept 1 of 17

[02:36:33] [INFO] 📚 1 segment(s) detected | [380.2s]

[02:36:33] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[02:36:33] [INFO] 🌐 Detected language: en

[02:36:33] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[02:36:33] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[02:36:33] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\markdown\chapters

[02:36:33] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[02:36:33] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\markdown\chapters

[02:36:33] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[02:36:33] [INFO]   ⏱️ Summary phase starting | [380.6s]

[02:36:35] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[02:36:35] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[02:36:35] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[02:36:35] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[02:36:35] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[02:36:35] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[02:36:35] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[02:36:35] [INFO]   🌡️ Pre-flight: idle GPU temp = 59°C

[02:36:35] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 59°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[02:36:35] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[02:36:35] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[02:36:35] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[02:36:35] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[02:36:35] [DEBUG]   🎛️ Model profile: Default

[02:36:35] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[02:36:35] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[02:36:35] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[02:36:35] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[02:36:35] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[02:36:35] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[02:36:35] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[02:36:35] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[02:36:35] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[02:36:35] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[02:36:35] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[02:36:35] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[02:36:35] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[02:36:35] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[02:36:35] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[02:36:35] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[02:36:35] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[02:36:35] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[02:36:35] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[02:36:35] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[02:36:35] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[02:36:36] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\436

[02:36:36] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[02:36:36] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[02:36:36] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[02:36:36] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[02:36:36] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:36:36] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[02:36:36] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[02:36:36] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[02:36:36] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:36:36] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[02:38:32] [INFO]     ✅ V0.3 Call 1/3: master summary = 1264 words, 9840 chars

[02:38:32] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[02:38:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:38:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[02:39:32] [INFO]     ✅ V0.3 Call 2/3: 39 bullets derived from master summary

[02:39:32] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[02:39:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:39:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[02:39:54] [INFO]     ✅ V0.3 Call 3/3: exec summary = 230 words

[02:39:54] [DEBUG]     📝 Parsed: exec=1883 chars, bullets=39, thorough=9840 chars

[02:40:18] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[02:40:20] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[02:40:20] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (39 bullets, 230 exec words, 1264 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[02:40:22] [DEBUG]     🔍 Fact-check: all 39 bullets verified ✓

[02:40:22] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[02:40:22] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:40:22] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[02:41:17] [INFO]     ✅ Additive sections via followup call: key_distinctions=1820 chars, theoretical_tensions=1595 chars

[02:41:17] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (39 bullets, 230 exec words, 1264 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[02:41:17] [INFO]     V0.05: Skipping bullet expansion — 39 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[02:41:17] [INFO]     ✅ Final coverage 100%

[02:41:17] [DEBUG]     📏 F1: exec=230w, thorough=1264w (source=7405w; targets exec<=250w, thorough<=3332w)

[02:43:33] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[02:43:33] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.9 (diff: -4.6)

[02:43:33] [INFO]     ℹ️ F3: Summary is 4.6 grade levels denser than source — expected for a compressed academic summary.

[02:43:34] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[02:43:34] [DEBUG]     🔄 J2: 24 cross-section redundancy(ies) found (exec↔bullets: 4, bullets↔thorough: 20)

[02:43:34] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 6 markers)

[02:43:34] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[02:43:34] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[02:43:35] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[02:43:50] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 4592 per-pair calls)

[02:43:50] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[02:43:52] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (39/39 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[02:43:52] [INFO]   ℹ️ Summary has substantial content (exec=1883 chars, thorough=9837 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[02:43:52] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[02:43:52] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[02:43:52] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[02:43:52] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[02:43:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:43:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[02:45:21] [INFO]     📜 Scholar response truncated — one additive continuation retry (V18.20.4.12 / O-a4)

[02:45:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:45:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[02:45:54] [INFO]     🎓 Gap-fill: added 21 new bullet(s) from scholar reflection (source-grounded)

[02:45:54] [INFO]     🎓 Scholar reflection: identified 8 gap(s), filled 21 with new bullets

[02:45:54] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[02:45:54] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[02:45:54] [WARNING]   ⏱️⚠️ Deadline exceeded (558s > 480s) — skipping optional phase: semantic dedup

[02:45:54] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[02:45:54] [DEBUG]     🧹 V16.0.2 Bullet normalization: 60 bullets normalized

[02:45:54] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[02:45:54] [WARNING]   ⏱️⚠️ Deadline exceeded (558s > 480s) — skipping optional phase: bullet consolidation

[02:45:54] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[02:45:54] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\436

[02:45:54] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[02:45:54] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[02:45:54] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Klein', 'Winnicott', 'Bergman', 'Erikson', 'Bursten', 'Conlon']/74 authors in bullets (32%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[02:45:54] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Frances', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Widiger', 'Leonhard', 'Shepherd', 'Polatin', 'Widiger and Frances', 'Klein', 'Winnicott', 'Fenichel', 'Bergman', 'Erikson', 'Bursten', 'Frances and Widiger', 'Mackinnon and Michels', 'Stone', 'Conlon', 'Ovessey', 'Walters', 'Mackinnon', 'Michels']/74 authors in thorough (47%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Byrne']

[02:45:54] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']…

[02:45:54] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:45:54] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:46:11] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[02:46:11] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (17.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[02:46:11] [DEBUG]     📊 V18.14.1: After round 1, 42 still missing from bullets: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Widiger']…

[02:46:11] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Widiger']…

[02:46:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:46:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:46:25] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1985) contributed to descriptions of paranoid disorders rathe…

[02:46:25] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 6/8 bullets

[02:46:25] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (13.2s): response=7 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=6

[02:46:25] [DEBUG]     📊 V18.14.1: After round 2, 31 still missing from bullets: ['Winokur', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[02:46:25] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Winokur', 'Tobak', 'Mahler', 'Bak', 'Anthony']…

[02:46:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:46:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:46:41] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut described narcissistic rage in 1972, which is cited alongside ot…

[02:46:41] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 7/8 bullets

[02:46:41] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (16.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[02:46:41] [DEBUG]     📊 V18.14.1: After round 3, 24 still missing from bullets: ['Kohut', 'Allodi', 'Jack', 'Ndtei', 'Green']…

[02:46:41] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Kohut', 'Allodi', 'Jack', 'Ndtei', 'Green']…

[02:46:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:46:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:46:56] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao (1969) provided work on morbid jealousy that was included among ke…

[02:46:56] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 7/8 bullets

[02:46:56] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (15.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[02:46:56] [DEBUG]     📊 V18.14.1: After round 4, 16 still missing from bullets: ['Pao', 'Mackinnon and Michels', 'Stone', 'Wurmser', 'Reid']…

[02:46:56] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Pao', 'Mackinnon and Michels', 'Stone', 'Wurmser', 'Reid']…

[02:46:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:46:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:47:09] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) were cited as offering relatively less clari…

[02:47:09] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) was cited in the context of research on paranoid diso…

[02:47:09] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[02:47:09] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (12.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[02:47:09] [DEBUG]     📊 V18.14.1: After round 5, 8 still missing from bullets: ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters']…

[02:47:09] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 34 bullets across 5 round(s)

[02:47:09] [WARNING]     ⚠️ V18.14.1: 8 theorists still missing from bullets after gap-fill: ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Munro', 'Gorton and Akhtar'] — 8 never covered (round cap/deadline): ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Munro', 'Gorton and Akhtar']

[02:47:09] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[02:47:09] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[02:47:09] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[02:47:09] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[02:47:09] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[02:47:09] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 32 (sim=0.86 with bullet 1)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 48 (sim=0.89 with bullet 41)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 50 (sim=0.91 with bullet 43)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 51 (sim=0.90 with bullet 44)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 52 (sim=0.91 with bullet 45)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 53 (sim=0.85 with bullet 46)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 54 (sim=0.94 with bullet 47)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 55 (sim=0.88 with bullet 41)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 56 (sim=0.96 with bullet 42)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 57 (sim=0.97 with bullet 43)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.97 with bullet 44)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 59 (sim=0.91 with bullet 45)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 60 (sim=0.97 with bullet 47)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 67 (sim=0.95 with bullet 66)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 68 (sim=0.93 with bullet 63)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 72 (sim=0.91 with bullet 65)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 84 (sim=0.86 with bullet 83)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 85 (sim=0.88 with bullet 83)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 88 (sim=0.86 with bullet 73)

[02:47:11] [DEBUG]     🧹 Semantic dedup: removing bullet 94 (sim=0.89 with bullet 47)

[02:47:11] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 99 → 79 bullets (removed 20 gap-fill/conclusion duplicates; 1.3s, non-skippable per V18.20.3.4)

[02:47:11] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\436

[02:47:11] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[02:47:11] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[02:47:14] [INFO]     ℹ️ V0.4.23: 79 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[02:47:14] [INFO]     🛡️ V18.2.13 Post-checks: 20 fixed, 22 flagged (of 79 bullets + exec + thorough)

[02:47:14] [DEBUG]       [consistency/flag] bullet[20]: false 'missing' claim: 'omitted' followed by 'superego unevenness' — but 2/2 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …eria to seven items but still omitted superego unevenness, s…

[02:47:14] [DEBUG]       [grammar/flag] bullet[22]: no main verb detected in first 40 words of 'In self-concept, an arrogant overt perso…' — the bullet may be grammatically broken (generation/formatting failure)  |  In self-concept, an arrogant o…

[02:47:14] [DEBUG]       [grammar/flag] bullet[23]: no main verb detected in first 40 words of 'In interpersonal relations, overt mistru…' — the bullet may be grammatically broken (generation/formatting failure)  |  In interpersonal relations, ov…

[02:47:14] [DEBUG]       [fragment_merge/flag] bullet[23]: word-fragment merge: 'naivety' — 'naive' is a known word but 'naivety' is not. The trailing 'ty' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …ust and aloofness mask covert naivety, fear of power, and te…

[02:47:14] [DEBUG]       [fragment_merge/flag] bullet[28]: word-fragment merge: 'models' — 'mode' is a known word but 'models' is not. The trailing 'ls' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …ts and aligns with prototypal models.

[02:47:14] [DEBUG]       [attribution/flag] bullet[65]: attribution mismatch: summary's claim about 'Kohut (1972)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kohut (1972) described narciss…

[02:47:14] [DEBUG]       [attribution/flag] bullet[74]: bold-name author 'Conclusions' not found in source — the summary attributes a claim to an author the source never mentions  |  **Conclusions**: (1) includes …

[02:47:14] [DEBUG]       [truncated/flag] bullet[76]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[02:47:14] [DEBUG]       [truncated/flag] bullet[78]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[02:47:14] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'naivety' — 'naive' is a known word but 'naivety' is not. The trailing 'ty' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …ust and aloofness mask covert naivety, fear of powerful peop…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Magnan (1893)' has 35% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …evolution of the concept from Magnan’s (1893) early identifi…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bleuler (1908)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  … onward to contributions from Bleuler (1908), who described …

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 38% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ntitlement versus inadequacy; Jaspers (1949), whose "self-in…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Schneider (1950)' has 34% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ion via compulsive formality; Schneider (1950), who distingu…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Shepherd (1961)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …sychopaths"; Leonhard (1959); Shepherd (1961), who profiled …

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Polatin (1975)' has 39% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ish proof of accusations; and Polatin (1975), who described …

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jacobson (1971)' has 44% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …s of contextual appreciation. Jacobson (1971) noted the role…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Fenichel (1946)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …sions). The phobic character (Fenichel 1946; Mackinnon & Mic…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Stone (1980)' has 43% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …46; Mackinnon & Michels 1971; Stone 1980) is distinguished b…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Conlon (1984)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …es some features (as noted by Conlon 1984) but differs in ch…

[02:47:14] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bergman (1978)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …ng integrity against despair (Bergman 1978), and discusses s…

[02:47:14] [DEBUG]       [consistency/flag] thorough: false 'missing' claim: 'omitted' followed by 'superego unevenness' — but 2/2 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  … "bearing grudges," but still omitted superego unevenness, s…

[02:47:14] [DEBUG]       [quote_verification/fix] bullet[42]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  bear grudges or are unforgiving of insults or slights

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   traits such as idiosyncratic thinking and suspiciousness, t

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   or paranoid personality—marked by marked distrust, litigiou

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   displayed overcompensation via compulsive formality; Schnei

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ; Leonhard (1959); Shepherd (1961), who profiled morbid jeal

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a developmental substrate involving projection, splittin

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   leading to suspiciousness and preoccupation with fantasies 

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects to project unacceptable attributes onto. R

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who might become a friend. Cameron (1963) outlined four asp

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by biased seizing of clues and loss of contex

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —an ambivalently loved object that cannot be allowed indepen

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but still omitted superego unevenness, self-esteem defects,

[02:47:14] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   without actual delusions). The phobic character (Fenichel 1

[02:47:14] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but lacks the personalization and intentionality (

[02:47:14] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   the chapter distinguishes them by noting that the narcissis

[02:47:14] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and seductiveness, whereas the paranoid is characterized by

[02:47:14] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., arrogance, vigilant attention) and 

[02:47:14] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., timidity, gullibility), arguing that

[02:47:14] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[02:47:14] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian drive theory vs. object-relations/environmental a

[02:47:14] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 35/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Byrne']

[02:47:14] [WARNING]   ⏱️⚠️ Deadline exceeded (638s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[02:47:14] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 39 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[02:47:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:47:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:48:31] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:48:31] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater and Roth (1977) explicitly identified the “contradictory pride …" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the psychoanalytic domain, Mahler’s theory of separation-individuat…" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the paranoid adolescent, providing insight i…" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Kohut’s (1972) description of narcissistic rage helps clarify the affe…" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Jack (1980) and Allodi (1986) provided significant contr…" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei (1987) also contributed to the broader discussion of personality…" — its name(s) never co-occur with the claim's key phrases in the source

[02:49:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:49:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green’s (1986) essay on moral narcissism is cited as bearing significa…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Socarides’ (1966) analysis of the affect of vengeance clarifies the ag…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser’s contributions are referenced indirectly through his influenc…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Reid’s work is alluded to in the context of the cognitive rigidity and…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Lowenthal’s insights into the developmental origins of paranoid traits…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Croewe’s (1975) textbook description is cited alongside Winokur as an …" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Rettersol’s (1985) studies on paranoid disorders are cited to note tha…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:26] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Varghesi’s (1982) study on diagnostic reliability is referenc…" — its name(s) never co-occur with the claim's key phrases in the source

[02:50:36] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 35/74 → 48/74 (3 chunked call(s), ≤12 names each; 3 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[02:50:37] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 59/74 in final bullets (missing: ['Widiger', 'Widiger and Frances', 'Jack', 'Ndtei', 'Siever and Kendler']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[02:50:37] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 841s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 841s of the budget.

[02:50:37] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[02:50:37] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":79,"exec_chars":1883,"chapter_done":true}

[02:50:37] [DEBUG]   📊 Progress: 1/1 done | 79 bullets | 1,883 chars exec summary

[02:50:37] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\checkpoints

[02:50:37] [INFO] 📄 Building DOCX report…

[02:50:37] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[02:50:37] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[02:50:37] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.36_20260926-023012-00c5ef19_summary.md + DOCX

[02:50:37] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[02:50:37] [INFO]   🧮 Embedding cache: 63 hits / 41 misses (61% hit-rate), 5000 entries

[02:50:37] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.36_20260926-023012-00c5ef19_summary.md

[02:50:37] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries

[02:50:37] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[02:50:37] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.4.36_20260926-023012-00c5ef19.summary.md

[02:50:37] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[02:50:37] [INFO]   ⏱️ DOCX phase starting | [1224.5s]

[02:50:37] [INFO] 📄 Building DOCX report…

[02:50:37] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[02:50:38] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[02:50:40] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[02:50:42] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[02:52:57] [INFO]   🎯 K1+Classification: 79 bullets — 21 core, 25 supporting, 33 additional

[02:52:57] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[02:52:58] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[02:52:58] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[02:52:58] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[02:52:58] [INFO]   📊 Citation graph: no citations found in the text.

[02:52:58] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[02:52:58] [SUCCESS] ✅ Conversion complete.

[02:53:18] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\logs\quality_report.json

[02:53:18] [INFO] 

[02:53:18] [INFO] ━━━ Thermal Safety Report ━━━

[02:53:18] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[02:53:18] [INFO]   Session duration: 16.7 min

[02:53:18] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[02:53:18] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[02:53:18] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:53:18] [INFO] 

[02:53:18] [INFO] ━━━ Elixir v0.4.36 Conversion Diagnostic Summary ━━━

[02:53:18] [INFO]   Book: Broken Structures Salman Akhtar

[02:53:18] [INFO]   Total pages: 397

[02:53:18] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[02:53:18] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[02:53:18] [INFO]   Summaries generated: 1

[02:53:18] [INFO]     Success: 1, Failed: 0, Total bullets: 79

[02:53:18] [INFO]     Coverage: 100%

[02:53:18] [INFO]     Recall floor (deterministic, final set): theorists 59/74 (80%), conclusion items 3/3 (100%)

[02:53:18] [INFO]   Warnings: 0

[02:53:18] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar

[02:53:18] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.4.36_20260926-023012-00c5ef19.conversion.log.md

[02:53:18] [INFO]   Diagnostic JSONL: None

[02:53:18] [INFO]   Summary files (3):

[02:53:18] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.4.36_20260926-023012-00c5ef19_summary.md — generated-by v0.4.36 | run_id=20260926-023012-00c5ef19 | started=2026-09-26T02:36:35 | bullets=79

[02:53:18] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.4.36 | run_id=20260926-023012-00c5ef19 | started=2026-09-26T02:36:35 | bullets=79

[02:53:18] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.4.36_20260926-023012-00c5ef19.summary.md — generated-by v0.4.36 | run_id=20260926-023012-00c5ef19 | started=2026-09-26T02:36:35 | bullets=79

[02:53:18] [INFO]   Models loaded at exit: (none — all unloaded)

[02:53:18] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:53:18] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[02:53:18] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[02:53:18] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[02:53:18] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[02:53:18] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[02:53:19] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[02:53:19] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\images

[02:53:19] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[02:53:28] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\images

[02:53:34] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[02:53:34] [INFO]   [pipeline] after de-dup: 2 regions

[02:53:35] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\436\Broken Structures Salman Akhtar\regions

[02:53:35] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[02:53:35] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 79 keypoints)


---
Finished at: 2026-09-26T02:53:35.640492
