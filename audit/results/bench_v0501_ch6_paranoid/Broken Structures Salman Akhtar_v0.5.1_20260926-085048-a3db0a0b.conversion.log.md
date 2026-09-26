# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T08:50:48.637479

<!-- generated-by: Elixir v0.5.1 | run_id=20260926-085048-a3db0a0b -->

---

[08:50:48] [SUCCESS] 🚀 Starting conversion…

[08:50:48] [DEBUG]   🔍 importing 'pypdf'…

[08:50:48] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[08:50:48] [DEBUG]   🔍 importing 'pdf2image'…

[08:50:48] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[08:50:48] [DEBUG]   🔍 importing 'tiktoken'…

[08:50:48] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[08:50:48] [DEBUG]   🔍 importing 'markitdown'…

[08:50:51] [DEBUG]   ✅ 'markitdown' ok (2.6s)

[08:50:51] [DEBUG]   🔍 importing 'rapidfuzz'…

[08:50:51] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[08:50:51] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[08:50:51] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[08:50:51] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[08:50:51] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[08:50:51] [DEBUG]   🔍 importing 'torch'…

[08:50:51] [DEBUG]   ✅ 'torch' ok (0.0s)

[08:50:51] [DEBUG]   🔍 importing 'transformers'…

[08:51:11] [DEBUG]   ✅ 'transformers' ok (20.5s)

[08:51:11] [DEBUG]   🔍 importing 'langextract'…

[08:51:11] [DEBUG]   ✅ 'langextract' ok (0.1s)

[08:51:11] [DEBUG]   ✅ Pre-flight dependency check passed

[08:51:11] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[08:51:11] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[08:51:11] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar.pdf

[08:51:11] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar

[08:51:11] [INFO]   Source type: normal_book

[08:51:11] [INFO]   App version: 0.5.1

[08:51:11] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[08:51:11] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[08:51:11] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[08:51:11] [INFO]   Ollama reachable (localhost:11434): True

[08:51:11] [INFO]   Provider: llamacpp

[08:51:11] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[08:51:11] [INFO]   [Phase 1 (Extraction)]

[08:51:11] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[08:51:11] [INFO]   [Phase 2 (Summarization)]

[08:51:11] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[08:51:11] [INFO]   ────────────────────────────────────────

[08:51:11] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[08:51:11] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[08:51:11] [INFO] ━━━━━━━━━━━━━━━━━━━━

[08:51:11] [INFO]   LLM OCR: True, Force OCR all: False

[08:51:11] [INFO]   Auto-detect scanned: True

[08:51:11] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:51:11] [INFO]   OCR retries: 2, Image max size: 1200

[08:51:11] [INFO]   Page range: all

[08:51:11] [INFO]   Selected chapters: 1 chapter(s)

[08:51:11] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[08:51:11] [INFO]   Segmentation: auto, Token limit: 2000

[08:51:11] [INFO]   Semantic: True, Page group: 10

[08:51:11] [INFO]   Generate summaries: True

[08:51:11] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:51:11] [INFO]   Fast model: , Heavy model: (disabled)

[08:51:11] [INFO]   Workers (requested): 1, Temperature: 0.7

[08:51:11] [INFO]   Self-consistency: False, Coverage threshold: 85%

[08:51:11] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[08:51:11] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[08:51:11] [INFO]   Academic rigor: False

[08:51:11] [INFO]   Max context tokens: 128000

[08:51:11] [INFO]   Max output tokens: 32768

[08:51:11] [INFO]   Keep-alive: 30m

[08:51:11] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[08:51:11] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[08:51:12] [INFO]   Translation: disabled

[08:51:12] [INFO]   Clean markdown: True, Token saver: True

[08:51:12] [INFO]   Content filter: True

[08:51:12] [INFO]   Extract tables: False, Math: False, Figures: False

[08:51:12] [INFO]   Visual-region crops: True

[08:51:12] [INFO]   Layout analysis: False

[08:51:12] [INFO]   DOCX author: Elixir, TOC: True

[08:51:12] [INFO]   Output paths (V7.5 subfolders):

[08:51:12] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[08:51:12] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[08:51:12] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[08:51:12] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\packets

[08:51:12] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\podcast

[08:51:12] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\logs\quality_report.json

[08:51:12] [INFO]   Resume mode: enabled — will skip done chapters

[08:51:12] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[08:51:12] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[08:51:12] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[08:51:12] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[08:51:12] [DEBUG]   💾 Disk space: 24.5 GB free

[08:51:12] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\.checkpoint.json

[08:52:26] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[08:52:26] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[08:52:26] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[08:52:26] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[08:52:26] [INFO] [TOC] Using PDF outlines: 22 entries.

[08:52:26] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[08:52:26] [DEBUG]   [TOC] Entries passed to segmenter: 22

[08:52:26] [DEBUG]   [TOC] - p.7: Table of Contents

[08:52:26] [DEBUG]   [TOC] - p.9: FOREWORD

[08:52:26] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[08:52:26] [DEBUG]   [TOC] … and 19 more

[08:52:26] [INFO]   🎯 User selected 1 chapter(s):

[08:52:26] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[08:52:26] [INFO]   📸 front_cover → front_cover.jpg

[08:52:26] [INFO]   📸 back_cover → back_cover.jpg

[08:52:26] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[08:52:26] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[08:52:26] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[08:52:27] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[08:52:27] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[08:52:27] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[08:52:27] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[08:52:27] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[08:52:28] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[08:52:28] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[08:52:28] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[08:52:28] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[08:52:29] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[08:52:29] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[08:52:29] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[08:52:29] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[08:52:29] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[08:52:29] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[08:52:30] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[08:52:30] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[08:52:30] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[08:52:30] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[08:52:30] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[08:52:31] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[08:52:31] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[08:52:31] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[08:52:31] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[08:52:31] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[08:52:31] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[08:52:31] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[08:52:31] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[08:52:31] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[08:52:31] [INFO]   ✅ markitdown ready for digital-page extraction

[08:52:31] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[08:52:31] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[08:52:31] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[08:52:31] [INFO]      Pages needing OCR: [152, 153, 154]

[08:52:31] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[08:52:31] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[08:52:31] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[08:52:33] [INFO]   📄 140/397 pages processed (35%)

[08:52:38] [INFO]   🔍 OCR  page 152/397 (scanned)…

[08:52:40] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[08:54:01] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[08:54:01] [INFO]   🔍 OCR  page 153/397 (scanned)…

[08:54:56] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[08:54:56] [INFO]   🔍 OCR  page 154/397 (scanned)…

[08:55:58] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[08:56:01] [INFO]   📄 160/397 pages processed (40%)

[08:56:01] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[08:56:01] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[08:56:01] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[08:56:01] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[08:56:01] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[08:56:01] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[08:56:01] [INFO] 📝 Raw markdown: 53,157 chars | [312.5s]

[08:56:01] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[08:56:01] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[08:56:01] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[08:56:01] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[08:56:01] [INFO] [Segmenter] Attempting chapter-level segmentation…

[08:56:01] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:56:01] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[08:56:01] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[08:56:01] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[08:56:01] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[08:56:01] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[08:56:01] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[08:56:01] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[08:56:01] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[08:56:01] [INFO]   📑 Filtered segments: kept 1 of 17

[08:56:01] [INFO] 📚 1 segment(s) detected | [312.6s]

[08:56:01] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[08:56:01] [INFO] 🌐 Detected language: en

[08:56:01] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[08:56:01] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[08:56:01] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\markdown\chapters

[08:56:01] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[08:56:01] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\markdown\chapters

[08:56:01] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[08:56:01] [INFO]   ⏱️ Summary phase starting | [313.0s]

[08:56:03] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[08:56:03] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[08:56:03] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[08:56:03] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[08:56:03] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[08:56:03] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[08:56:03] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[08:56:03] [INFO]   🌡️ Pre-flight: idle GPU temp = 61°C

[08:56:03] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 61°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[08:56:03] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[08:56:03] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[08:56:03] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[08:56:03] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[08:56:03] [DEBUG]   🎛️ Model profile: Default

[08:56:03] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[08:56:03] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[08:56:03] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[08:56:03] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[08:56:03] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[08:56:03] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[08:56:03] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[08:56:03] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[08:56:03] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[08:56:03] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[08:56:03] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[08:56:03] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[08:56:03] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[08:56:03] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[08:56:03] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[08:56:03] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[08:56:03] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[08:56:03] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[08:56:03] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[08:56:03] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[08:56:04] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[08:56:04] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.1

[08:56:04] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[08:56:04] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[08:56:04] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[08:56:04] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[08:56:04] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:56:04] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[08:56:04] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[08:56:04] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[08:56:04] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:56:04] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[08:57:19] [INFO]     ✅ V0.3 Call 1/3: master summary = 881 words, 6664 chars

[08:57:19] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[08:57:19] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:57:19] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[08:57:58] [INFO]     ✅ V0.3 Call 2/3: 34 bullets derived from master summary

[08:57:58] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[08:57:58] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:57:58] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[08:58:15] [INFO]     ✅ V0.3 Call 3/3: exec summary = 216 words

[08:58:15] [DEBUG]     📝 Parsed: exec=1801 chars, bullets=34, thorough=6664 chars

[08:58:37] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[08:58:39] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[08:58:39] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (34 bullets, 216 exec words, 881 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[08:58:40] [DEBUG]     🔍 Fact-check: all 34 bullets verified ✓

[08:58:40] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[08:58:40] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:58:40] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[08:59:37] [INFO]     ✅ Additive sections via followup call: key_distinctions=2026 chars, theoretical_tensions=2249 chars

[08:59:38] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (34 bullets, 216 exec words, 881 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[08:59:38] [INFO]     V0.05: Skipping bullet expansion — 34 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[08:59:38] [INFO]     ✅ Final coverage 100%

[08:59:38] [DEBUG]     📏 F1: exec=216w, thorough=881w (source=7405w; targets exec<=250w, thorough<=3332w)

[09:01:33] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[09:01:33] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.3 (diff: -4.0)

[09:01:33] [INFO]     ℹ️ F3: Summary is 4.0 grade levels denser than source — expected for a compressed academic summary.

[09:01:35] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[09:01:35] [DEBUG]     🔄 J2: 24 cross-section redundancy(ies) found (exec↔bullets: 0, bullets↔thorough: 24)

[09:01:35] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 3 markers)

[09:01:35] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[09:01:35] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[09:01:35] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[09:01:49] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 4032 per-pair calls)

[09:01:49] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[09:01:51] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (34/34 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[09:01:51] [INFO]   ℹ️ Summary has substantial content (exec=1801 chars, thorough=6660 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[09:01:51] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[09:01:51] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[09:01:51] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[09:01:51] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[09:01:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:01:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[09:03:25] [DEBUG]     🎓 Dropped gap-fill without quote: Kretschmer (1927) observed that contradictory attitudes some…

[09:03:25] [DEBUG]     🎓 Dropped gap-fill without quote: Millon (1981) divided paranoid features into four categories…

[09:03:25] [INFO]     🎓 Gap-fill: added 17 new bullet(s) from scholar reflection (source-grounded)

[09:03:25] [INFO]     🎓 Scholar reflection: identified 17 gap(s), filled 17 with new bullets

[09:03:25] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[09:03:25] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[09:03:26] [DEBUG]     🧹 Semantic dedup: removing bullet 37 (sim=0.91 with bullet 7)

[09:03:26] [DEBUG]     🧹 Semantic dedup: removing bullet 38 (sim=0.91 with bullet 8)

[09:03:26] [DEBUG]     🧹 Semantic dedup: removing bullet 40 (sim=0.89 with bullet 10)

[09:03:26] [INFO]     🧹 Semantic dedup: 51 → 48 bullets (removed 3 semantic duplicates)

[09:03:26] [DEBUG]     🧹 V16.0.2 Bullet normalization: 48 bullets normalized

[09:03:26] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[09:03:26] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.1

[09:03:26] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[09:03:26] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[09:03:26] [INFO]     🔧 Bullet consolidation SKIPPED — deterministic probe found 0 mergeable pairs (48 bullets, LLM call not needed; rig .3.7-.3.9: the LLM merged 0 on the same input shape)

[09:03:26] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.1

[09:03:26] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[09:03:26] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[09:03:26] [INFO]     📊 V18.14 Bullets-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Thomson', 'Kretschmer', 'Rycroft', 'Cameron', 'Akhtar and Thomson', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Leonhard', 'Shepherd', 'Polatin', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Bergman', 'Erikson', 'Bursten', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Morey']/74 authors in bullets (45%) — MISSING from bullets: ['Stanton', 'Meissner', 'Hamilton', 'Frances', 'Byrne']

[09:03:26] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Leonhard', 'Shepherd', 'Polatin', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Morey']/74 authors in thorough (31%) — MISSING from thorough: ['Stanton', 'Meissner', 'Thomson', 'Hamilton', 'Frances']

[09:03:26] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Stanton', 'Meissner', 'Hamilton', 'Frances', 'Byrne']…

[09:03:26] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:03:26] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[09:03:39] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne (1983) described the behavioral correlates …' (source attributes this claim to 'Socarides’s', not 'Byrne')

[09:03:39] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[09:03:39] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (12.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[09:03:39] [DEBUG]     📊 V18.14.1: After round 1, 32 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Kendler']…

[09:03:39] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Volkan', 'Winokur', 'Kendler']…

[09:03:39] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:03:39] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[09:03:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne: The source text does not attribute any specific contribution to…

[09:03:51] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne: Their 1983 work described the behavioral c…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[09:03:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur: He is cited as an author whose 1975 work with Croewe, along w…

[09:03:51] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 5/8 bullets

[09:03:51] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (12.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=2, added=5

[09:03:51] [INFO]     🔁 V18.20.3.7: 'Akhtar and Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[09:03:51] [DEBUG]     📊 V18.14.1: After round 2, 24 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Bach', 'Fenichel']…

[09:03:51] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Bach', 'Fenichel']… (mention-only: ['Byrne', 'Akhtar and Byrne'])

[09:03:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:03:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[09:04:03] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne (1983) contributed the behavioral correlate…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[09:04:03] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)

[09:04:03] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.citation_only': 1}

[09:04:03] [DEBUG]     🎓 V18.12.2: Dropped gap-fill bullet (prompt-leakage/thinking): - The chapter cites Akhtar (1984) for a description of ident…

[09:04:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1975, 1985) is referenced in the context of descriptions that…

[09:04:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Allodi (1982) is cited regarding the differentiation of reactive or ac…

[09:04:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is cited in the context of differentiating reactive or acu…

[09:04:03] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is cited regarding the distinction between reactive or ac…

[09:04:03] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 2/8 bullets

[09:04:03] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (12.2s): response=8 bullet lines, dup=0, think-filtered=1, vetoed=1, filler=4, added=2

[09:04:03] [INFO]     🔁 V18.20.3.7: 'Winokur' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[09:04:03] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Akhtar and Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[09:04:03] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[09:04:03] [DEBUG]     📊 V18.14.1: After round 3, 22 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Allodi', 'Jack']…

[09:04:03] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Winokur', 'Allodi', 'Jack', 'Ndtei', 'Green']… (mention-only: ['Winokur'])

[09:04:03] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:04:03] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[09:04:17] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao (1969) developed work on morbid jealousy that was cited alongside …

[09:04:17] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur's (1985) description of paranoid disorders was referenced by t…

[09:04:17] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 6/8 bullets

[09:04:17] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (13.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[09:04:17] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Winokur' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[09:04:17] [DEBUG]     📊 V18.14.1: After round 4, 15 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Pao', 'Mackinnon and Michels']…

[09:04:17] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Pao', 'Mackinnon and Michels', 'Stone', 'Croewe', 'Rettersol']…

[09:04:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:04:17] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[09:04:29] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) were cited as offering less clarity than oth…

[09:04:29] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 7/8 bullets

[09:04:29] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (11.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[09:04:29] [DEBUG]     📊 V18.14.1: After round 5, 6 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Croewe', 'Munro']…

[09:04:29] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 27 bullets across 5 round(s)

[09:04:29] [WARNING]     ⚠️ V18.14.1: 6 theorists still missing from bullets after gap-fill: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Croewe', 'Munro', 'Gorton and Akhtar'] — of these, 3 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Byrne', 'Akhtar and Byrne', 'Winokur'] — 3 never covered (round cap/deadline): ['Croewe', 'Munro', 'Gorton and Akhtar']

[09:04:29] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[09:04:29] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[09:04:29] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[09:04:29] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[09:04:29] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[09:04:29] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[09:04:29] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[09:04:30] [DEBUG]     🧹 Semantic dedup: removing bullet 66 (sim=0.87 with bullet 64)

[09:04:30] [DEBUG]     🧹 Semantic dedup: removing bullet 74 (sim=0.88 with bullet 73)

[09:04:30] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 81 → 79 bullets (removed 2 gap-fill/conclusion duplicates; 0.8s, non-skippable per V18.20.3.4)

[09:04:30] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.1

[09:04:30] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[09:04:30] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[09:04:32] [INFO]     ℹ️ V0.4.23: 78 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[09:04:32] [INFO]     🛡️ V18.2.13 Post-checks: 23 fixed, 5 flagged (of 78 bullets + exec + thorough)

[09:04:32] [DEBUG]       [attribution/flag] bullet[55]: attribution mismatch: summary's claim about 'His (1986)' has 41% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Volkan: His 1986 insights addressed ma…

[09:04:32] [DEBUG]       [attribution/flag] bullet[58]: attribution mismatch: summary's claim about 'His (1981)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Anthony: His 1981 delineation described…

[09:04:32] [DEBUG]       [attribution/flag] bullet[59]: attribution mismatch: summary's claim about 'His (1972)' has 40% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kohut: His 1972 description focused o…

[09:04:32] [DEBUG]       [truncated/flag] bullet[77]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[09:04:32] [DEBUG]       [sentence_fusion/flag] exec: likely sentence-fusion garble: 'underrepresentation' is not in the source or English lexicon; it starts with source-word 'represent' + a 5-char suffix 'ation' that is itself a suffix of another source word (a dropped-prefix fusion — the model fused 'represent' with a source word ending in 'ation' but dropped that word's prefix).  |  addresses the historical underrepresentation of paranoid personality 

[09:04:32] [DEBUG]       [space/fix] thorough: split 'review' -> 're view' (source-validated)  |  …s. The descriptive literature review begins with Magnan (189…

[09:04:32] [DEBUG]       [dropped_digit_year/fix] thorough: dropped-digit year: 'Bursten (1973)' → 'Bursten (1973a)' (source has 5 digits, summary has 4 — the model dropped a digit)  |  …n (1963), Shapiro (1971), and Bursten (1973) further detaile…

[09:04:32] [DEBUG]       [quote_verification/fix] bullet[2]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  delusional states of degenerates

[09:04:32] [DEBUG]       [quote_verification/fix] bullet[23]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (arrogance, hypervigilance, moralistic rigid

[09:04:32] [DEBUG]       [quote_verification/fix] bullet[35]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  to solve difficulties of life by geographical moves

[09:04:32] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to Kraepelin’s description of the 

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   specifically devoted to its phenomenology compared to other

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by a fragile personality exhibiting idiosyncr

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   or paranoid personality as an individual who is always on t

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who mask their grinding self-depreciation with overcompensa

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   while Leonhard (1959) and Shepherd (1961) highlighted the a

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects. Kernberg (1975a) classified paranoid pers

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —an ambivalently loved figure that must be kept in a state o

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   both manuals fail to capture the superego unevenness, self-

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations—such as arrogance, hypervigilance, and moral

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   ones—such as timidity, gullibility, fear of dependence, and

[09:04:32] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (where suspicions are more encapsulated but lack the diffus

[09:04:32] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  : The text notes that while both conditions show few exacerb

[09:04:32] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but largely quantitative; paranoia involves actual delusion

[09:04:32] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  these two views... continue to exist independently of each o

[09:04:32] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   of the paranoid individual, but explicitly notes this creat

[09:04:32] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 3 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Libidinal vs. aggressive/relational origins of paranoia: F

[09:04:32] [DEBUG]       [near_duplicate/fix] bullet[71]: near-duplicate of bullet[49] (token-set containment >= 0.8) — kept the first, dropped this one  |  Ovessey (1955) criticized a formulation for overemphasizing 

[09:04:32] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 23/74 authors in thorough — MISSING from thorough: ['Stanton', 'Meissner', 'Thomson', 'Hamilton', 'Frances']

[09:04:32] [WARNING]   ⏱️⚠️ Deadline exceeded (509s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[09:04:32] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 51 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[09:04:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:04:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[09:05:05] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stanton (1978) highlighted the paradox of overt stubbornness masking h…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:05] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In terms of psychoanalytic dynamics, Meissner (1978b) argued that the …" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:05] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Volkan (1986) contributed an insight into the broader human need for e…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:05] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, the authors’ own work on identity diffusion (Akhtar 1984) and…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:05] [WARNING]     ⚠️ V0.4.24: Thorough gap-fill chunk fully dropped by the attribution-edge filter

[09:05:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:05:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[09:05:43] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mahler (1975) provided a theoretical framework for understanding the s…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:43] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bak (1946) contributed an early psychoanalytic perspective on paranoia…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:43] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the specific characteristics of the paranoid…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:43] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In addition to these psychoanalytic contributions, the chapter acknowl…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:43] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, the chapter references Slater and Roth (1977) and other autho…" — its name(s) never co-occur with the claim's key phrases in the source

[09:05:57] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[09:05:57] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack (1963) provided an early psychoanalytic case formulation that emp…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi (1984) contributed to the understanding of the cognitive rigidi…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green (1986) explored the concept of "moral narcissism," arguing that …" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1969) examined morbid jealousy within the context of paranoid per…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Socarides (1966) focused on the affective dimension of vengeance, sugg…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler (1987) critically evaluated the diagnostic criteria…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Frances and Widiger (1985) addressed the relative neglect of paranoid …" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon and Michels (1967) discussed the role of projection in maint…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stone (1982) examined the developmental trajectory of paranoid tendenc…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:41] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Roth (1973) provided a comprehensive review of the psychoanal…" — its name(s) never co-occur with the claim's key phrases in the source

[09:06:45] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 23/74 → 28/74 (3 chunked call(s), ≤12 names each; 15 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[09:06:45] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 65/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Winokur', 'Ndtei', 'Croewe']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[09:06:45] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[09:06:45] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 641s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 641s of the budget.

[09:06:45] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[09:06:45] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":78,"exec_chars":1799,"chapter_done":true}

[09:06:45] [DEBUG]   📊 Progress: 1/1 done | 78 bullets | 1,799 chars exec summary

[09:06:45] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\checkpoints

[09:06:45] [INFO] 📄 Building DOCX report…

[09:06:45] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[09:06:45] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[09:06:45] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.1_20260926-085048-a3db0a0b_summary.md + DOCX

[09:06:45] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[09:06:45] [INFO]   🧮 Embedding cache: 63 hits / 36 misses (64% hit-rate), 5000 entries

[09:06:45] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.1_20260926-085048-a3db0a0b_summary.md

[09:06:45] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries

[09:06:45] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[09:06:45] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.1_20260926-085048-a3db0a0b.summary.md

[09:06:45] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[09:06:45] [INFO]   ⏱️ DOCX phase starting | [957.1s]

[09:06:45] [INFO] 📄 Building DOCX report…

[09:06:45] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[09:06:46] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[09:06:48] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[09:06:50] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[09:08:53] [INFO]   🎯 K1+Classification: 78 bullets — 15 core, 38 supporting, 25 additional

[09:08:53] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[09:08:53] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[09:08:53] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[09:08:53] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[09:08:53] [INFO]   📊 Citation graph: no citations found in the text.

[09:08:53] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[09:08:53] [SUCCESS] ✅ Conversion complete.

[09:09:11] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\logs\quality_report.json

[09:09:11] [INFO] 

[09:09:11] [INFO] ━━━ Thermal Safety Report ━━━

[09:09:11] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[09:09:11] [INFO]   Session duration: 13.1 min

[09:09:11] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[09:09:11] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[09:09:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[09:09:11] [INFO] 

[09:09:11] [INFO] ━━━ Elixir v0.5.1 Conversion Diagnostic Summary ━━━

[09:09:11] [INFO]   Book: Broken Structures Salman Akhtar

[09:09:11] [INFO]   Total pages: 397

[09:09:11] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[09:09:11] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[09:09:11] [INFO]   Summaries generated: 1

[09:09:11] [INFO]     Success: 1, Failed: 0, Total bullets: 78

[09:09:11] [INFO]     Coverage: 100%

[09:09:11] [INFO]     Recall floor (deterministic, final set): theorists 65/74 (88%), conclusion items 3/3 (100%)

[09:09:11] [INFO]   Warnings: 0

[09:09:11] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar

[09:09:11] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.1_20260926-085048-a3db0a0b.conversion.log.md

[09:09:11] [INFO]   Diagnostic JSONL: None

[09:09:11] [INFO]   Summary files (3):

[09:09:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.1_20260926-085048-a3db0a0b_summary.md — generated-by v0.5.1 | run_id=20260926-085048-a3db0a0b | started=2026-09-26T08:56:03 | bullets=78

[09:09:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.1 | run_id=20260926-085048-a3db0a0b | started=2026-09-26T08:56:03 | bullets=78

[09:09:11] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.1_20260926-085048-a3db0a0b.summary.md — generated-by v0.5.1 | run_id=20260926-085048-a3db0a0b | started=2026-09-26T08:56:03 | bullets=78

[09:09:11] [INFO]   Models loaded at exit: (none — all unloaded)

[09:09:11] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[09:09:11] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[09:09:11] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[09:09:11] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[09:09:11] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[09:09:11] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[09:09:11] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[09:09:11] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\images

[09:09:11] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[09:09:17] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\images

[09:09:24] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[09:09:24] [INFO]   [pipeline] after de-dup: 2 regions

[09:09:24] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\v5.1\Broken Structures Salman Akhtar\regions

[09:09:24] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[09:09:24] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 78 keypoints)


---
Finished at: 2026-09-26T09:09:24.903507
