# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T17:37:40.106939

<!-- generated-by: Elixir v0.5.2 | run_id=20260926-173740-b001f210 -->

---

[17:37:40] [SUCCESS] 🚀 Starting conversion…

[17:37:40] [DEBUG]   🔍 importing 'pypdf'…

[17:37:40] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[17:37:40] [DEBUG]   🔍 importing 'pdf2image'…

[17:37:40] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[17:37:40] [DEBUG]   🔍 importing 'tiktoken'…

[17:37:40] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[17:37:40] [DEBUG]   🔍 importing 'markitdown'…

[17:37:41] [DEBUG]   ✅ 'markitdown' ok (1.8s)

[17:37:41] [DEBUG]   🔍 importing 'rapidfuzz'…

[17:37:41] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[17:37:41] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[17:37:41] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[17:37:41] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[17:37:41] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[17:37:41] [DEBUG]   🔍 importing 'torch'…

[17:37:41] [DEBUG]   ✅ 'torch' ok (0.0s)

[17:37:41] [DEBUG]   🔍 importing 'transformers'…

[17:37:53] [DEBUG]   ✅ 'transformers' ok (11.2s)

[17:37:53] [DEBUG]   🔍 importing 'langextract'…

[17:37:53] [DEBUG]   ✅ 'langextract' ok (0.1s)

[17:37:53] [DEBUG]   ✅ Pre-flight dependency check passed

[17:37:53] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[17:37:53] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[17:37:53] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar.pdf

[17:37:53] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar

[17:37:53] [INFO]   Source type: normal_book

[17:37:53] [INFO]   App version: 0.5.2

[17:37:53] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[17:37:53] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[17:37:53] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[17:37:53] [INFO]   Ollama reachable (localhost:11434): True

[17:37:53] [INFO]   Provider: llamacpp

[17:37:53] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[17:37:53] [INFO]   [Phase 1 (Extraction)]

[17:37:53] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[17:37:53] [INFO]   [Phase 2 (Summarization)]

[17:37:53] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[17:37:53] [INFO]   ────────────────────────────────────────

[17:37:53] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[17:37:53] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[17:37:53] [INFO] ━━━━━━━━━━━━━━━━━━━━

[17:37:53] [INFO]   LLM OCR: True, Force OCR all: False

[17:37:53] [INFO]   Auto-detect scanned: True

[17:37:53] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[17:37:53] [INFO]   OCR retries: 2, Image max size: 1200

[17:37:53] [INFO]   Page range: all

[17:37:53] [INFO]   Selected chapters: 1 chapter(s)

[17:37:53] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[17:37:53] [INFO]   Segmentation: auto, Token limit: 2000

[17:37:53] [INFO]   Semantic: True, Page group: 10

[17:37:53] [INFO]   Generate summaries: True

[17:37:53] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[17:37:53] [INFO]   Fast model: , Heavy model: (disabled)

[17:37:53] [INFO]   Workers (requested): 1, Temperature: 0.7

[17:37:53] [INFO]   Self-consistency: False, Coverage threshold: 85%

[17:37:53] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[17:37:53] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[17:37:53] [INFO]   Academic rigor: False

[17:37:53] [INFO]   Max context tokens: 128000

[17:37:53] [INFO]   Max output tokens: 32768

[17:37:53] [INFO]   Keep-alive: 30m

[17:37:53] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[17:37:53] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[17:37:53] [INFO]   Translation: disabled

[17:37:53] [INFO]   Clean markdown: True, Token saver: True

[17:37:53] [INFO]   Content filter: True

[17:37:53] [INFO]   Extract tables: False, Math: False, Figures: False

[17:37:53] [INFO]   Visual-region crops: True

[17:37:53] [INFO]   Layout analysis: False

[17:37:53] [INFO]   DOCX author: Elixir, TOC: True

[17:37:53] [INFO]   Output paths (V7.5 subfolders):

[17:37:53] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[17:37:53] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[17:37:53] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[17:37:53] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\packets

[17:37:53] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\podcast

[17:37:53] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\logs\quality_report.json

[17:37:53] [INFO]   Resume mode: enabled — will skip done chapters

[17:37:53] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[17:37:53] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[17:37:53] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[17:37:53] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[17:37:53] [DEBUG]   💾 Disk space: 23.2 GB free

[17:37:53] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\.checkpoint.json

[17:39:05] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[17:39:05] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[17:39:05] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[17:39:05] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[17:39:05] [INFO] [TOC] Using PDF outlines: 22 entries.

[17:39:05] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[17:39:05] [DEBUG]   [TOC] Entries passed to segmenter: 22

[17:39:05] [DEBUG]   [TOC] - p.7: Table of Contents

[17:39:05] [DEBUG]   [TOC] - p.9: FOREWORD

[17:39:05] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[17:39:05] [DEBUG]   [TOC] … and 19 more

[17:39:05] [INFO]   🎯 User selected 1 chapter(s):

[17:39:05] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[17:39:06] [INFO]   📸 front_cover → front_cover.jpg

[17:39:06] [INFO]   📸 back_cover → back_cover.jpg

[17:39:06] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[17:39:06] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[17:39:06] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[17:39:06] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[17:39:06] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[17:39:07] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[17:39:07] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[17:39:07] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[17:39:07] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[17:39:08] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[17:39:08] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[17:39:08] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[17:39:08] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[17:39:08] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[17:39:09] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[17:39:09] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[17:39:09] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[17:39:09] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[17:39:09] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[17:39:10] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[17:39:10] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[17:39:10] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[17:39:10] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[17:39:10] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[17:39:11] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[17:39:11] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[17:39:11] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[17:39:11] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[17:39:11] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[17:39:11] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[17:39:11] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[17:39:11] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[17:39:11] [INFO]   ✅ markitdown ready for digital-page extraction

[17:39:11] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[17:39:11] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[17:39:11] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[17:39:11] [INFO]      Pages needing OCR: [152, 153, 154]

[17:39:11] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[17:39:11] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[17:39:11] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[17:39:13] [INFO]   📄 140/397 pages processed (35%)

[17:39:19] [INFO]   🔍 OCR  page 152/397 (scanned)…

[17:39:21] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[17:39:55] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[17:39:55] [INFO]   🔍 OCR  page 153/397 (scanned)…

[17:40:23] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[17:40:23] [INFO]   🔍 OCR  page 154/397 (scanned)…

[17:40:59] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[17:41:01] [INFO]   📄 160/397 pages processed (40%)

[17:41:02] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[17:41:02] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[17:41:02] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[17:41:02] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[17:41:02] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[17:41:02] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[17:41:02] [INFO] 📝 Raw markdown: 53,157 chars | [202.0s]

[17:41:02] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[17:41:02] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[17:41:02] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[17:41:02] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[17:41:02] [INFO] [Segmenter] Attempting chapter-level segmentation…

[17:41:02] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[17:41:02] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[17:41:02] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[17:41:02] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[17:41:02] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[17:41:02] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[17:41:02] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[17:41:02] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[17:41:02] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[17:41:02] [INFO]   📑 Filtered segments: kept 1 of 17

[17:41:02] [INFO] 📚 1 segment(s) detected | [202.1s]

[17:41:02] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[17:41:02] [INFO] 🌐 Detected language: en

[17:41:02] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[17:41:02] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[17:41:02] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\markdown\chapters

[17:41:02] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[17:41:02] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\markdown\chapters

[17:41:02] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[17:41:02] [INFO]   ⏱️ Summary phase starting | [202.4s]

[17:41:04] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[17:41:04] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[17:41:04] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[17:41:04] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[17:41:04] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[17:41:04] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[17:41:04] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[17:41:04] [INFO]   🌡️ Pre-flight: idle GPU temp = 63°C

[17:41:04] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 63°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[17:41:04] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[17:41:04] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[17:41:04] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[17:41:04] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[17:41:04] [DEBUG]   🎛️ Model profile: Default

[17:41:04] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[17:41:04] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[17:41:04] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[17:41:04] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[17:41:04] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[17:41:04] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[17:41:04] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[17:41:04] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[17:41:04] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[17:41:04] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[17:41:04] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[17:41:04] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[17:41:04] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[17:41:04] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[17:41:04] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[17:41:04] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[17:41:04] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[17:41:04] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[17:41:04] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[17:41:04] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[17:41:05] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[17:41:05] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.2

[17:41:05] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[17:41:05] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[17:41:05] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[17:41:05] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[17:41:05] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[17:41:05] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[17:41:05] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[17:41:05] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[17:41:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:41:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[17:42:07] [INFO]     ✅ V0.3 Call 1/3: master summary = 590 words, 4702 chars

[17:42:07] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[17:42:07] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:42:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[17:42:35] [INFO]     ✅ V0.3 Call 2/3: 20 bullets derived from master summary

[17:42:35] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[17:42:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:42:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[17:42:51] [INFO]     ✅ V0.3 Call 3/3: exec summary = 220 words

[17:42:51] [DEBUG]     📝 Parsed: exec=1778 chars, bullets=20, thorough=4702 chars

[17:43:16] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[17:43:17] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[17:43:17] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (20 bullets, 220 exec words, 590 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[17:43:18] [DEBUG]     🔍 Fact-check: all 20 bullets verified ✓

[17:43:18] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[17:43:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:43:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[17:44:05] [INFO]     ✅ Additive sections via followup call: key_distinctions=1591 chars, theoretical_tensions=1434 chars

[17:44:05] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (20 bullets, 220 exec words, 590 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[17:44:05] [WARNING]     ⚠️ thorough_summary too short (590 words < 800 threshold) — requesting dedicated expansion…

[17:44:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[17:44:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[17:48:55] [INFO]     📖 Attempt 1/3: dedicated thorough = 4733 words

[17:48:55] [INFO]     ✅ thorough_summary expanded via dedicated call: 590 → 4733 words

[17:48:55] [INFO]     ⚠️ 20 bullets — requesting dedicated bullet expansion (full output budget)…

[17:48:55] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:48:55] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=8192 streaming…

[17:49:43] [INFO]     ✅ Final coverage 100%

[17:49:43] [DEBUG]     ✂️ F1: Truncated thorough_summary to 4166 words (source-scaled cap)

[17:49:43] [DEBUG]     📏 F1: exec=220w, thorough=4693w (source=7405w; targets exec<=250w, thorough<=3332w)

[17:50:49] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[17:50:49] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 18.3 (diff: -2.0)

[17:50:49] [INFO]     ℹ️ F3: Summary is 2.0 grade levels denser than source — expected for a compressed academic summary.

[17:50:50] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[17:50:50] [DEBUG]     🔄 J2: 3 cross-section redundancy(ies) found (exec↔bullets: 3, bullets↔thorough: 0)

[17:50:50] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 3 markers)

[17:50:50] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[17:50:50] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[17:50:50] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[17:51:22] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 2464 per-pair calls)

[17:51:22] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[17:51:24] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (20/20 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[17:51:24] [INFO]   ℹ️ Summary has substantial content (exec=1778 chars, thorough=29918 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[17:51:24] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[17:51:24] [WARNING]   ⏱️⚠️ Deadline exceeded (619s > 480s) — skipping optional phase: scholar reflection

[17:51:24] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[17:51:24] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[17:51:24] [WARNING]   ⏱️⚠️ Deadline exceeded (619s > 480s) — skipping optional phase: semantic dedup

[17:51:24] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[17:51:24] [DEBUG]     🧹 V16.0.2 Bullet normalization: 20 bullets normalized

[17:51:24] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[17:51:24] [WARNING]   ⏱️⚠️ Deadline exceeded (619s > 480s) — skipping optional phase: bullet consolidation

[17:51:24] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[17:51:24] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.2

[17:51:24] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[17:51:24] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[17:51:24] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Meissner', 'Kretschmer', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Slater and Roth', 'Klein', 'Winnicott', 'Roth', 'Slater', 'Erikson', 'Bursten']/74 authors in bullets (28%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Heimann', 'Thomson', 'Hamilton']

[17:51:24] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Stanton', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Byrne', 'Akhtar and Byrne', 'Magnan', 'Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson', 'Volkan', 'Kendler', 'Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Tobak', 'Klein', 'Winnicott', 'Mahler', 'Bak', 'Anthony', 'Kohut', 'Bach', 'Roth', 'Slater', 'Erikson', 'Bursten', 'Green', 'Pao', 'Socarides', 'Siever and Kendler', 'Morey', 'Ovessey', 'Walters', 'Gorton and Akhtar', 'Siever']/74 authors in thorough (66%) — MISSING from thorough: ['Thomson', 'Frances', 'Akhtar and Thomson', 'Winokur', 'Widiger']

[17:51:24] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Heimann', 'Thomson', 'Hamilton']…

[17:51:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:51:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[17:51:37] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne: Described the behavioral correlates of splitting (Akh…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[17:51:37] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[17:51:37] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (12.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[17:51:37] [DEBUG]     📊 V18.14.1: After round 1, 41 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Salzman', 'Millon', 'Volkan']…

[17:51:37] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Salzman', 'Millon', 'Volkan']…

[17:51:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:51:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[17:51:48] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Byrne contributed to the literature on paranoid personality …' (source attributes this claim to 'Socarides’s', not 'Byrne')

[17:51:48] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Akhtar and Byrne described the behavioral correlates of spli…' (source attributes this claim to 'Socarides’s', not 'Byrne')

[17:51:48] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 6/8 bullets

[17:51:48] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (11.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=2, filler=0, added=6

[17:51:48] [DEBUG]     📊 V18.14.1: After round 2, 33 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Polatin', 'Tobak', 'Mahler']…

[17:51:48] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Byrne', 'Akhtar and Byrne', 'Polatin', 'Tobak', 'Mahler']… (mention-only: ['Byrne'])

[17:51:48] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:51:48] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[17:52:01] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne (1983) is cited by Akhtar as providing the behavioral correlates…

[17:52:01] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne (1983) described the behavioral correlates of splitti…

[17:52:01] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler's (1975) theory of separation-individuation is referenced by Bl…

[17:52:01] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut's (1972) description of narcissistic rage is cited as part of a …

[17:52:01] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 4/8 bullets

[17:52:01] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (12.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[17:52:01] [INFO]     🔁 V18.20.3.7: 'Akhtar and Byrne' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[17:52:01] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[17:52:01] [DEBUG]     📊 V18.14.1: After round 3, 29 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Mahler', 'Kohut', 'Bach']…

[17:52:01] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Akhtar and Byrne', 'Mahler', 'Kohut', 'Bach', 'Fenichel']… (mention-only: ['Akhtar and Byrne'])

[17:52:01] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:52:01] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[17:52:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne (1983) described the behavioral correlates of splitti…

[17:52:15] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bach (1977) noted the "mirror complementarity of the self," which was …

[17:52:15] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 6/8 bullets

[17:52:15] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (14.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[17:52:15] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Akhtar and Byrne' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[17:52:15] [DEBUG]     📊 V18.14.1: After round 4, 23 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Bach', 'Ndtei', 'Green']…

[17:52:15] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Bach', 'Ndtei', 'Green', 'Pao', 'Socarides']…

[17:52:15] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:52:15] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[17:52:31] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 8/8 bullets

[17:52:31] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (15.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[17:52:31] [DEBUG]     📊 V18.14.1: After round 5, 12 still missing from bullets: ['Byrne', 'Akhtar and Byrne', 'Wurmser', 'Conlon', 'Reid']…

[17:52:31] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 31 bullets across 5 round(s)

[17:52:31] [WARNING]     ⚠️ V18.14.1: 12 theorists still missing from bullets after gap-fill: ['Byrne', 'Akhtar and Byrne', 'Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Rettersol', 'Morey'] — of these, 2 given up on after a failed mention-only attempt (no attribution-safe bullet exists: every generated claim was vetoed as a misattribution): ['Byrne', 'Akhtar and Byrne'] — 10 never covered (round cap/deadline): ['Wurmser', 'Conlon', 'Reid', 'Lowenthal', 'Rettersol', 'Morey', 'Ovessey', 'Walters']

[17:52:31] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[17:52:31] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[17:52:31] [DEBUG]     ✅ V0.4.23: enumeration guarantee — all 43 item(s) across 9 detected list(s) already covered (no bullets added)

[17:52:31] [DEBUG]     🧹 Semantic dedup: removing bullet 41 (sim=0.88 with bullet 20)

[17:52:31] [DEBUG]     🧹 Semantic dedup: removing bullet 43 (sim=0.90 with bullet 42)

[17:52:31] [DEBUG]     🧹 Semantic dedup: removing bullet 45 (sim=0.90 with bullet 42)

[17:52:31] [DEBUG]     🧹 Semantic dedup: removing bullet 49 (sim=0.86 with bullet 32)

[17:52:31] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 52 → 48 bullets (removed 4 gap-fill/conclusion duplicates; 0.7s, non-skippable per V18.20.3.4)

[17:52:31] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.2

[17:52:31] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[17:52:31] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[17:52:34] [INFO]     🛡️ V18.2.13 Post-checks: 19 fixed, 4 flagged (of 48 bullets + exec + thorough)

[17:52:34] [DEBUG]       [space/fix] bullet[26]: split 'review' -> 're view' (source-validated)  |  Frances: Co-authored a review (Widiger and Frances 19…

[17:52:34] [DEBUG]       [prompt/fix] bullet[30]: stripped prompt-leakage: 'as noted in the source'  |  …dered less clear than others, as noted in the source text (W…

[17:52:34] [DEBUG]       [attribution/flag] bullet[36]: attribution mismatch: summary's claim about 'Anthony (1981)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Anthony (1981) delineated the …

[17:52:34] [DEBUG]       [attribution/flag] bullet[38]: attribution mismatch: summary's claim about 'Kohut (1972)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kohut (1972) described narciss…

[17:52:34] [DEBUG]       [attribution/flag] bullet[43]: attribution mismatch: summary's claim about 'Pao (1969)' has 47% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Pao’s (1969) work addressed mo…

[17:52:34] [DEBUG]       [interpretation/fix] thorough: stripped first-person interpretation: 'It should be noted that'  |  …iny and prevent misdiagnosis. It should be noted that the ov…

[17:52:34] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  ighly structuralized and ego-syntonically embedded in the personal

[17:52:34] [DEBUG]       [quote_verification/fix] bullet[14]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (arrogance, hypervigilance) and 

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  paucity of papers specifically devoted to its phenomenology,

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characterized by idiosyncratic thinking, undue sensitivity,

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Such an individual is vain, self-absorbed, sensitive, irrit

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ) or paranoid schizophrenia. It characterizes the condition 

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the earliest developmental constellation of infantile ob

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as a menace. The end of intrauterine bliss, with birth, pro

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   external objects on whom they might plausibly project their

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Shapiro regarded the paranoid person’s construction of a su

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   clues form their context and, on the other hand, a loss of 

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   unconscious desires are disavowed by projection. Their furt

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   the ambivalently loved object that is felt to be both perse

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and unemotional; pride taken in always being objective, rat

[17:52:34] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   is an improvement over DSM-III. However, in its emphasis on

[17:52:34] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid Personality Disorder vs. Schizophrenia: The chapt

[17:52:34] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian Formulation vs. Criticism (Meissner/Ovessey/Walte

[17:52:34] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 49/74 authors in thorough — MISSING from thorough: ['Thomson', 'Frances', 'Akhtar and Thomson', 'Winokur', 'Widiger']

[17:52:34] [WARNING]   ⏱️⚠️ Deadline exceeded (689s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[17:52:34] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 25 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[17:52:34] [INFO]     🎯 V0.4.37 F3: thorough (4160 words) meets its source-scaled target (3332 words) BUT coverage 49/74 = 66% < the engage fraction (70%) -- gap-fill runs (coverage-driven engagement, not word-count-driven)

[17:52:34] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:52:34] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[17:53:08] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Frances and Widiger (1986) proposed a prototypal model for classifying…" — its name(s) never co-occur with the claim's key phrases in the source

[17:53:08] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In parallel, Akhtar and Thomson (1982) contributed to the broader noso…" — its name(s) never co-occur with the claim's key phrases in the source

[17:53:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:53:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter further integrates the work of Mackinnon and Michels, who …" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser’s insights into the interplay of aggression and projection in …" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Reid’s work on cognitive biases and attentional styles in paranoid ind…" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Lowenthal’s contributions to the understanding of identity diffusion a…" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Munro’s contributions to the understanding of moralistic self-righteou…" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:00] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Mackinnon’s later work on the structural organization of para…" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:07] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[17:54:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[17:54:36] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "While the composite profile integrates findings from numerous theorist…" — its name(s) never co-occur with the claim's key phrases in the source

[17:54:46] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 49/74 → 53/74 (3 chunked call(s), ≤12 names each)

[17:54:46] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 57/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Bergman', 'Jack', 'Ndtei']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[17:54:46] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 822s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 822s of the budget.

[17:54:46] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[17:54:46] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":48,"exec_chars":1778,"chapter_done":true}

[17:54:46] [DEBUG]   📊 Progress: 1/1 done | 48 bullets | 1,778 chars exec summary

[17:54:46] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\checkpoints

[17:54:46] [INFO] 📄 Building DOCX report…

[17:54:46] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[17:54:47] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[17:54:47] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.2_20260926-173740-b001f210_summary.md + DOCX

[17:54:47] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[17:54:47] [INFO]   🧮 Embedding cache: 63 hits / 22 misses (74% hit-rate), 5000 entries

[17:54:47] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.2_20260926-173740-b001f210_summary.md

[17:54:47] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries

[17:54:47] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[17:54:47] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.2_20260926-173740-b001f210.summary.md

[17:54:47] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[17:54:47] [INFO]   ⏱️ DOCX phase starting | [1027.1s]

[17:54:47] [INFO] 📄 Building DOCX report…

[17:54:47] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[17:54:47] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[17:54:48] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[17:54:50] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[17:55:59] [INFO]   🎯 K1+Classification: 48 bullets — 8 core, 29 supporting, 11 additional

[17:55:59] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[17:55:59] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[17:55:59] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[17:55:59] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[17:55:59] [INFO]   📊 Citation graph: no citations found in the text.

[17:55:59] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[17:55:59] [SUCCESS] ✅ Conversion complete.

[17:56:15] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\logs\quality_report.json

[17:56:15] [INFO] 

[17:56:15] [INFO] ━━━ Thermal Safety Report ━━━

[17:56:15] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[17:56:15] [INFO]   Session duration: 15.2 min

[17:56:15] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[17:56:15] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[17:56:15] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[17:56:15] [INFO] 

[17:56:15] [INFO] ━━━ Elixir v0.5.2 Conversion Diagnostic Summary ━━━

[17:56:15] [INFO]   Book: Broken Structures Salman Akhtar

[17:56:15] [INFO]   Total pages: 397

[17:56:15] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[17:56:15] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[17:56:15] [INFO]   Summaries generated: 1

[17:56:15] [INFO]     Success: 1, Failed: 0, Total bullets: 48

[17:56:15] [INFO]     Coverage: 100%

[17:56:15] [INFO]     Recall floor (deterministic, final set): theorists 57/74 (77%), conclusion items 3/3 (100%)

[17:56:15] [INFO]   Warnings: 0

[17:56:15] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar

[17:56:15] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.2_20260926-173740-b001f210.conversion.log.md

[17:56:15] [INFO]   Diagnostic JSONL: None

[17:56:15] [INFO]   Summary files (3):

[17:56:15] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.2_20260926-173740-b001f210_summary.md — generated-by v0.5.2 | run_id=20260926-173740-b001f210 | started=2026-09-26T17:41:04 | bullets=48

[17:56:15] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.2 | run_id=20260926-173740-b001f210 | started=2026-09-26T17:41:04 | bullets=48

[17:56:15] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.2_20260926-173740-b001f210.summary.md — generated-by v0.5.2 | run_id=20260926-173740-b001f210 | started=2026-09-26T17:41:04 | bullets=48

[17:56:15] [INFO]   Models loaded at exit: (none — all unloaded)

[17:56:15] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[17:56:15] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[17:56:15] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[17:56:15] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[17:56:15] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[17:56:15] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[17:56:15] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[17:56:15] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\images

[17:56:15] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[17:56:21] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\images

[17:56:27] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[17:56:27] [INFO]   [pipeline] after de-dup: 2 regions

[17:56:28] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\v5.2\Broken Structures Salman Akhtar\regions

[17:56:28] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[17:56:28] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 48 keypoints)


---
Finished at: 2026-09-26T17:56:28.089290
