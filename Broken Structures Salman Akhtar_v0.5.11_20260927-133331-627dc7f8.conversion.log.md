# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T13:33:31.541757

<!-- generated-by: Elixir v0.5.11 | run_id=20260927-133331-627dc7f8 -->

---

[13:33:31] [SUCCESS] 🚀 Starting conversion…

[13:33:31] [DEBUG]   🔍 importing 'pypdf'…

[13:33:31] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[13:33:31] [DEBUG]   🔍 importing 'pdf2image'…

[13:33:31] [DEBUG]   ✅ 'pdf2image' ok (0.1s)

[13:33:31] [DEBUG]   🔍 importing 'tiktoken'…

[13:33:31] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[13:33:31] [DEBUG]   🔍 importing 'markitdown'…

[13:33:37] [DEBUG]   ✅ 'markitdown' ok (5.9s)

[13:33:37] [DEBUG]   🔍 importing 'rapidfuzz'…

[13:33:37] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[13:33:37] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[13:33:37] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[13:33:37] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[13:33:37] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[13:33:37] [DEBUG]   ✅ 'torch' installed

[13:33:37] [DEBUG]   ✅ 'transformers' installed

[13:33:37] [DEBUG]   ✅ 'langextract' installed

[13:33:37] [DEBUG]   ✅ Pre-flight dependency check passed

[13:33:37] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[13:33:37] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[13:33:37] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar.pdf

[13:33:37] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar

[13:33:37] [INFO]   Source type: normal_book

[13:33:37] [INFO]   App version: 0.5.11

[13:33:37] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[13:33:37] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[13:33:37] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[13:33:37] [INFO]   Ollama reachable (localhost:11434): True

[13:33:37] [INFO]   Provider: llamacpp

[13:33:37] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[13:33:37] [INFO]   [Phase 1 (Extraction)]

[13:33:37] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[13:33:37] [INFO]   [Phase 2 (Summarization)]

[13:33:37] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[13:33:37] [INFO]   ────────────────────────────────────────

[13:33:37] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[13:33:37] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[13:33:37] [INFO] ━━━━━━━━━━━━━━━━━━━━

[13:33:37] [INFO]   LLM OCR: True, Force OCR all: False

[13:33:37] [INFO]   Auto-detect scanned: True

[13:33:37] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[13:33:37] [INFO]   OCR retries: 2, Image max size: 1200

[13:33:37] [INFO]   Page range: all

[13:33:37] [INFO]   Selected chapters: 1 chapter(s)

[13:33:37] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[13:33:37] [INFO]   Segmentation: auto, Token limit: 2000

[13:33:37] [INFO]   Semantic: True, Page group: 10

[13:33:37] [INFO]   Generate summaries: True

[13:33:37] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[13:33:37] [INFO]   Fast model: , Heavy model: (disabled)

[13:33:37] [INFO]   Workers (requested): 1, Temperature: 0.7

[13:33:37] [INFO]   Self-consistency: False, Coverage threshold: 95%

[13:33:37] [INFO]   📈 Over-delivery: ENABLED (floor 95% → target 100%)

[13:33:37] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[13:33:37] [INFO]   Academic rigor: False

[13:33:37] [INFO]   Max context tokens: 128000

[13:33:37] [INFO]   Max output tokens: 32768

[13:33:37] [INFO]   Keep-alive: 30m

[13:33:37] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[13:33:37] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[13:33:37] [INFO]   Translation: disabled

[13:33:37] [INFO]   Clean markdown: True, Token saver: True

[13:33:37] [INFO]   Content filter: True

[13:33:37] [INFO]   Extract tables: False, Math: False, Figures: False

[13:33:37] [INFO]   Visual-region crops: True

[13:33:37] [INFO]   Layout analysis: False

[13:33:37] [INFO]   DOCX author: Elixir, TOC: True

[13:33:37] [INFO]   Output paths (V7.5 subfolders):

[13:33:37] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[13:33:37] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[13:33:37] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[13:33:37] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\packets

[13:33:37] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\podcast

[13:33:37] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\logs\quality_report.json

[13:33:37] [INFO]   Resume mode: enabled — will skip done chapters

[13:33:37] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[13:33:37] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[13:33:37] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[13:33:37] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[13:33:37] [DEBUG]   💾 Disk space: 22.5 GB free

[13:33:37] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\.checkpoint.json

[13:34:34] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[13:34:34] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[13:34:34] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[13:34:34] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[13:34:34] [INFO] [TOC] Using PDF outlines: 22 entries.

[13:34:34] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[13:34:34] [DEBUG]   [TOC] Entries passed to segmenter: 22

[13:34:34] [DEBUG]   [TOC] - p.7: Table of Contents

[13:34:34] [DEBUG]   [TOC] - p.9: FOREWORD

[13:34:34] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[13:34:34] [DEBUG]   [TOC] … and 19 more

[13:34:34] [INFO]   🎯 User selected 1 chapter(s):

[13:34:34] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[13:34:35] [INFO]   📸 front_cover → front_cover.jpg

[13:34:35] [INFO]   📸 back_cover → back_cover.jpg

[13:34:35] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[13:34:35] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[13:34:35] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[13:34:36] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[13:34:36] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[13:34:36] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[13:34:36] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[13:34:36] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[13:34:36] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[13:34:37] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[13:34:37] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[13:34:37] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[13:34:37] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[13:34:37] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[13:34:38] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[13:34:38] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[13:34:38] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[13:34:38] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[13:34:38] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[13:34:39] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[13:34:39] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[13:34:39] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[13:34:39] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[13:34:39] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[13:34:40] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[13:34:40] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[13:34:40] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[13:34:40] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[13:34:40] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[13:34:40] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[13:34:40] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[13:34:40] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[13:34:40] [INFO]   ✅ markitdown ready for digital-page extraction

[13:34:40] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[13:34:40] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[13:34:40] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.2s)

[13:34:40] [INFO]      Pages needing OCR: [152, 153, 154]

[13:34:40] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[13:34:40] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[13:34:40] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[13:34:42] [INFO]   📄 140/397 pages processed (35%)

[13:34:49] [INFO]   🔍 OCR  page 152/397 (scanned)…

[13:34:51] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[13:35:25] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[13:35:25] [INFO]   🔍 OCR  page 153/397 (scanned)…

[13:35:52] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[13:35:52] [INFO]   🔍 OCR  page 154/397 (scanned)…

[13:36:27] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[13:36:30] [INFO]   📄 160/397 pages processed (40%)

[13:36:30] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[13:36:30] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[13:36:30] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[13:36:30] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[13:36:30] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[13:36:30] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[13:36:30] [INFO] 📝 Raw markdown: 53,157 chars | [178.6s]

[13:36:30] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[13:36:30] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[13:36:30] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[13:36:30] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[13:36:30] [INFO] [Segmenter] Attempting chapter-level segmentation…

[13:36:30] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[13:36:30] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[13:36:30] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[13:36:30] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[13:36:30] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[13:36:30] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[13:36:30] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[13:36:30] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[13:36:30] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[13:36:30] [INFO]   📑 Filtered segments: kept 1 of 17

[13:36:30] [INFO] 📚 1 segment(s) detected | [178.7s]

[13:36:30] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[13:36:30] [INFO] 🌐 Detected language: en

[13:36:30] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[13:36:30] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[13:36:30] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\markdown\chapters

[13:36:30] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[13:36:30] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\markdown\chapters

[13:36:30] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3938 bytes)

[13:36:30] [INFO]   ⏱️ Summary phase starting | [179.0s]

[13:36:32] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[13:36:32] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[13:36:32] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[13:36:32] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[13:36:32] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[13:36:32] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[13:36:32] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[13:36:32] [INFO]   🌡️ Pre-flight: idle GPU temp = 63°C

[13:36:32] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 63°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[13:36:32] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[13:36:32] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[13:36:32] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[13:36:32] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[13:36:32] [DEBUG]   🎛️ Model profile: Default

[13:36:32] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[13:36:32] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[13:36:32] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[13:36:32] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[13:36:32] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[13:36:32] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[13:36:32] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[13:36:32] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[13:36:32] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[13:36:32] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[13:36:32] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[13:36:32] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[13:36:32] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[13:36:32] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[13:36:32] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[13:36:32] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[13:36:32] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[13:36:32] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[13:36:32] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[13:36:32] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[13:36:33] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[13:36:33] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.11

[13:36:33] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[13:36:33] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[13:36:33] [INFO]     📊 V17.2: Prepended deterministic analysis (3823 chars) — citation recall 78%→100%

[13:36:33] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[13:36:33] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[13:36:33] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[13:36:33] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[13:36:33] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[13:36:33] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:36:33] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[13:37:44] [INFO]     ✅ V0.3 Call 1/3: master summary = 751 words, 5994 chars

[13:37:44] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[13:37:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:37:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[13:38:25] [INFO]     ✅ V0.3 Call 2/3: 34 bullets derived from master summary

[13:38:25] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[13:38:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:38:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[13:38:41] [INFO]     ✅ V0.3 Call 3/3: exec summary = 205 words

[13:38:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[13:38:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[13:41:10] [INFO]     📖 V0.5.7 source glossary (separate call) → C:\Users\Ali Assadi\Desktop\5.11\summaries\.glossaries\6 - PARANOID PERSONALITY DISORDER.glossary.md

[13:41:10] [DEBUG]     📝 Parsed: exec=1682 chars, bullets=34, thorough=5994 chars

[13:42:06] [INFO]     📊 Primary coverage: 92% | keywords: ['paranoid', 'disorder', 'self']

[13:42:07] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[13:42:07] [INFO]     ℹ️ Coverage 92% < 95% — B3 voting disabled, will rely on over-delivery + gap-fill + 3-Tier Guarantee to push toward 100%

[13:42:07] [INFO]     📈 Coverage 92% < effective target 100% (over-deliver: floor 95% → target 100%) — applying 3-Tier Guarantee

[13:42:08] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (34 bullets, 205 exec words, 751 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[13:42:09] [DEBUG]     🔍 Fact-check: all 34 bullets verified ✓

[13:42:09] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[13:42:09] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:42:09] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[13:42:53] [INFO]     ✅ Additive sections via followup call: key_distinctions=1421 chars, theoretical_tensions=1293 chars

[13:42:53] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (34 bullets, 205 exec words, 751 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[13:42:53] [WARNING]     ⚠️ thorough_summary too short (751 words < 800 threshold) — requesting dedicated expansion…

[13:42:53] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[13:42:53] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[13:44:04] [INFO]     📖 Attempt 1/3: dedicated thorough = 751 words

[13:44:04] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[13:44:07] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[13:44:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[13:44:55] [WARNING]   ⏱️⚠️ Deadline exceeded (503s > 480s) — skipping optional phase: dedicated thorough (attempt 3)

[13:44:55] [DEBUG]     ⏱️ Skipping thorough attempt 3 (chapter deadline exceeded)

[13:44:55] [WARNING]   ⏱️⚠️ Deadline exceeded (503s > 480s) — skipping optional phase: dedicated thorough (attempt 4 length-directive)

[13:44:55] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=751) — keeping best-effort result

[13:44:55] [DEBUG]     ℹ️ Dedicated thorough call returned 751 words (not longer than original 751) — keeping original

[13:44:55] [WARNING]   ⏱️⚠️ Deadline exceeded (503s > 480s) — skipping optional phase: dedicated bullet expansion

[13:44:55] [WARNING]     ⚠️ Final coverage 92% below 95% threshold

[13:44:55] [DEBUG]     📏 F1: exec=205w, thorough=751w (source=7405w; targets exec<=250w, thorough<=3332w)

[13:46:37] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[13:46:37] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 19.4 (diff: -3.1)

[13:46:37] [INFO]     ℹ️ F3: Summary is 3.1 grade levels denser than source — expected for a compressed academic summary.

[13:46:38] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[13:46:38] [DEBUG]     🔄 J2: 27 cross-section redundancy(ies) found (exec↔bullets: 3, bullets↔thorough: 24)

[13:46:38] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[13:46:38] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[13:46:38] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[13:46:38] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[13:47:11] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 4032 per-pair calls)

[13:47:11] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[13:47:13] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (34/34 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[13:47:13] [INFO]   ℹ️ Summary has substantial content (exec=1682 chars, thorough=5990 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[13:47:13] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[13:47:13] [WARNING]   ⏱️⚠️ Deadline exceeded (641s > 480s) — skipping optional phase: scholar reflection

[13:47:13] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[13:47:13] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[13:47:13] [WARNING]   ⏱️⚠️ Deadline exceeded (641s > 480s) — skipping optional phase: semantic dedup

[13:47:13] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[13:47:13] [DEBUG]     🧹 V16.0.2 Bullet normalization: 34 bullets normalized

[13:47:13] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[13:47:13] [WARNING]   ⏱️⚠️ Deadline exceeded (641s > 480s) — skipping optional phase: bullet consolidation

[13:47:13] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[13:47:13] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.11

[13:47:13] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[13:47:13] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[13:47:13] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Polatin', 'Klein', 'Winnicott', 'Bach', 'Erikson', 'Bursten']/74 authors in bullets (27%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Thomson', 'Rycroft', 'Frances']

[13:47:13] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Hamilton', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Polatin', 'Klein', 'Winnicott', 'Erikson', 'Bursten']/74 authors in thorough (26%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Rycroft', 'Frances']

[13:47:13] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Thomson', 'Rycroft', 'Frances']…

[13:47:13] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:47:13] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[13:47:27] [INFO]     ✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)

[13:47:27] [INFO]     ✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)

[13:47:27] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[13:47:27] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (14.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[13:47:27] [DEBUG]     📊 V18.14.1: After round 1, 43 still missing from bullets: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[13:47:27] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Salzman', 'Millon', 'Jacobson', 'Volkan', 'Winokur']…

[13:47:27] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:47:27] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[13:47:39] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) offered a textbook description of paranoid p…

[13:47:39] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[13:47:39] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (11.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[13:47:39] [DEBUG]     📊 V18.14.1: After round 2, 35 still missing from bullets: ['Winokur', 'Slater and Roth', 'Tobak', 'Mahler', 'Bak']…

[13:47:39] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Winokur', 'Slater and Roth', 'Tobak', 'Mahler', 'Bak']…

[13:47:39] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:47:39] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[13:47:52] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[13:47:52] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (13.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[13:47:52] [DEBUG]     📊 V18.14.1: After round 3, 25 still missing from bullets: ['Bergman', 'Allodi', 'Jack', 'Ndtei', 'Green']…

[13:47:52] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Bergman', 'Allodi', 'Jack', 'Ndtei', 'Green']…

[13:47:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:47:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[13:48:05] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 8/8 bullets

[13:48:05] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (12.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[13:48:05] [DEBUG]     📊 V18.14.1: After round 4, 16 still missing from bullets: ['Mackinnon and Michels', 'Stone', 'Wurmser', 'Conlon', 'Reid']…

[13:48:05] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Mackinnon and Michels', 'Stone', 'Wurmser', 'Conlon', 'Reid']…

[13:48:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:48:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[13:48:17] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe (1975) were cited as examples of textbook descripti…

[13:48:17] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Rettersol (1985) was referenced regarding paranoid disorders, distingu…

[13:48:17] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[13:48:17] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (12.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[13:48:17] [DEBUG]     📊 V18.14.1: After round 5, 8 still missing from bullets: ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters']…

[13:48:17] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 37 bullets across 5 round(s)

[13:48:17] [WARNING]     ⚠️ V18.14.1: 8 theorists still missing from bullets after gap-fill: ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Munro', 'Gorton and Akhtar'] — 8 never covered (round cap/deadline): ['Croewe', 'Rettersol', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Munro', 'Gorton and Akhtar']

[13:48:17] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[13:48:17] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (3 item(s) were uncovered; all 9 now carried verbatim)

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[13:48:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 26 (sim=0.86 with bullet 1)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 28 (sim=0.87 with bullet 1)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 31 (sim=0.86 with bullet 30)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 32 (sim=0.87 with bullet 30)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 41 (sim=0.95 with bullet 40)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 42 (sim=0.95 with bullet 37)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 60 (sim=0.90 with bullet 59)

[13:48:18] [DEBUG]     🧹 Semantic dedup: removing bullet 65 (sim=0.85 with bullet 47)

[13:48:18] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 78 → 70 bullets (removed 8 gap-fill/conclusion duplicates; 1.0s, non-skippable per V18.20.3.4)

[13:48:18] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.11

[13:48:18] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[13:48:18] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[13:48:20] [INFO]     🛡️ V18.2.13 Post-checks: 15 fixed, 15 flagged (of 68 bullets + exec + thorough)

[13:48:20] [DEBUG]       [attribution/flag] bullet[6]: attribution mismatch: summary's claim about 'Jaspers (1949)' has 40% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Jaspers (1949) described "self…

[13:48:20] [DEBUG]       [attribution/flag] bullet[8]: attribution mismatch: summary's claim about 'Polatin (1975)' has 42% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Polatin (1975) and Hamilton (1…

[13:48:20] [DEBUG]       [garble_llm_repair/flag] bullet[9]: semantic LLM repair returned empty/short text — original kept.  |  The descriptive literature identifies six core contradiction

[13:48:20] [DEBUG]       [dropped_letter/flag] bullet[9]: likely garbled token: 'erotomanic' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'erotomania' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  … sensitivity, asexuality with erotomanic vulnerability, mora…

[13:48:20] [DEBUG]       [attribution/flag] bullet[17]: attribution mismatch: summary's claim about 'Shapiro (1965)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Shapiro (1965) detailed parano…

[13:48:20] [DEBUG]       [consistency/flag] bullet[22]: false 'missing' claim: 'omitted' followed by 'key features such as superego unevenness' — but 4/4 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …-R (1987) diagnostic criteria omitted key features such as s…

[13:48:20] [DEBUG]       [space/fix] bullet[34]: split 'review' -> 're view' (source-validated)  |  Frances: Co-authored a 1985 review (Widiger and Frances) t…

[13:48:20] [DEBUG]       [parenthetical_promotion/fix] bullet[35]: dropped misattributed bullet: 'Byrne' is credited with a claim the source attributes to 'Socarides’s' ('Byrne' appears there only as a citation/list item). Verified via the generation-time active-subject veto.  |  Byrne: Co-authored an 1983 study with Akhtar describing the 

[13:48:20] [DEBUG]       [sentence_fusion/flag] bullet[45]: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  mendacity and moralistic self-righteousness as a characteristic cont

[13:48:20] [DEBUG]       [attribution/flag] bullet[55]: attribution mismatch: summary's claim about 'Pao (1969)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Pao (1969) conducted work on m…

[13:48:20] [DEBUG]       [attribution/flag] bullet[56]: attribution mismatch: summary's claim about 'Socarides (1966)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Socarides (1966) offered a vie…

[13:48:20] [DEBUG]       [sentence_fusion/flag] bullet[64]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[13:48:20] [DEBUG]       [truncated/flag] bullet[67]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[13:48:20] [DEBUG]       [truncated/flag] bullet[69]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[13:48:20] [DEBUG]       [garble_llm_repair/flag] thorough: semantic LLM repair returned empty/short text — original kept.  |  The chapter "Paranoid Personality Disorder" opens with a poe

[13:48:20] [DEBUG]       [dropped_letter/flag] thorough: likely garbled token: 'erotomanic' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'erotomania' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  … sensitivity, asexuality with erotomanic vulnerability, mora…

[13:48:20] [DEBUG]       [consistency/flag] thorough: false 'missing' claim: 'omitted' followed by 'key features such as superego unevenness' — but 4/4 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …bears grudges," both versions omitted key features such as s…

[13:48:20] [DEBUG]       [quote_verification/fix] bullet[24]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., arrogance, hypervigilance) and 

[13:48:20] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., hypervigilance) and 

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   into combative and eccentric types, while later contributor

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the developmental substrate of severe character patholog

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   leading to anxiety and paranoid traits, while Erikson (1950

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   but factually accurate, characterized by rigid mental sets 

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to describe the desperate effort to preserve an illusory co

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   both versions omitted key features such as superego unevenn

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., arrogance, hypervigilance, industria

[13:48:20] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   characteristics (e.g., timidity, gullibility, vulnerability

[13:48:20] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[13:48:20] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Descriptive psychiatry vs. psychoanalytic literature: The 

[13:48:20] [DEBUG]       [near_duplicate/fix] bullet[64]: near-duplicate of bullet[16] (token-set containment >= 0.8) — kept the first, dropped this one  |  **Cameron outlined four aspects of paranoid** — 4 items from

[13:48:20] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 19/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Rycroft', 'Frances']

[13:48:20] [WARNING]   ⏱️⚠️ Deadline exceeded (708s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[13:48:20] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 55 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[13:48:20] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:48:20] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[13:48:56] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Rycroft (1960), in reporting the psychoanalytic treatment of an indivi…" — its name(s) never co-occur with the claim's key phrases in the source

[13:49:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:49:17] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[13:50:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter extends its theoretical reach by incorporating the work of…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Further broadening the scope, the author references Bak (1946) regardi…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The discussion also includes Mahler (1975), whose theory of separation…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In addressing the clinical and nosological landscape, the text mention…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:03] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter also acknowledges Shepherd (1961) for providing a thorough…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:13] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[13:50:13] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[13:50:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bach (1977) identified the "mirror complementarity of the self" in the…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green (1986) examined the moral dimensions of the condition through hi…" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao’s (1969) work on morbid jealousy provided a critical link between …" — its name(s) never co-occur with the claim's key phrases in the source

[13:50:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the context of diagnostic classification, Siever and Kendler (1987)…" — its name(s) never co-occur with the claim's key phrases in the source

[13:51:17] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 19/74 → 35/74 (3 chunked call(s), ≤12 names each; 19 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[13:51:17] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[13:51:17] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 1 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[13:51:17] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 62/74 in final bullets (missing: ['Byrne', 'Akhtar and Byrne', 'Jack', 'Siever and Kendler', 'Croewe']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[13:51:17] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 885s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 885s of the budget.

[13:51:17] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[13:51:17] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":69,"exec_chars":1680,"chapter_done":true}

[13:51:17] [DEBUG]   📊 Progress: 1/1 done | 69 bullets | 1,680 chars exec summary

[13:51:17] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\checkpoints

[13:51:18] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 9 source author(s) NOT found in the summary (Bach, Croewe, Gorton, Jack, Morey, Munro, Ovessey, Rettersol, Walters). Glossary: (none). Cross-ref: confirmed=64, llm_only=2, regex_only=10.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1990' (ce:1990) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1955' (ce:1955) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1955' (ce:1955) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923a' (ce:1923) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923' (ce:1923) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[13:51:18] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 9 source author(s) NOT found in the summary (Bach, Croewe, Gorton, Jack, Morey, 

[13:51:18] [INFO] 📄 Building DOCX report…

[13:51:18] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[13:51:18] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[13:51:18] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.11_20260927-133331-627dc7f8_summary.md + DOCX

[13:51:18] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[13:51:18] [INFO]   🧮 Embedding cache: 63 hits / 36 misses (64% hit-rate), 5000 entries

[13:51:18] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.11_20260927-133331-627dc7f8_summary.md

[13:51:18] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries

[13:51:18] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[13:51:18] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.11_20260927-133331-627dc7f8.summary.md

[13:51:18] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[13:51:18] [INFO]   ⏱️ DOCX phase starting | [1067.0s]

[13:51:18] [INFO] 📄 Building DOCX report…

[13:51:18] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[13:51:18] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[13:51:20] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[13:51:22] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[13:52:57] [INFO]   🎯 K1+Classification: 69 bullets — 4 core, 57 supporting, 8 additional

[13:52:57] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[13:52:57] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[13:52:57] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[13:52:57] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[13:52:57] [INFO]   📊 Citation graph: no citations found in the text.

[13:52:57] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[13:52:57] [SUCCESS] ✅ Conversion complete.

[13:53:12] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\logs\quality_report.json

[13:53:12] [INFO] 

[13:53:12] [INFO] ━━━ Thermal Safety Report ━━━

[13:53:12] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[13:53:12] [INFO]   Session duration: 16.7 min

[13:53:12] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[13:53:12] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[13:53:12] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[13:53:12] [INFO] 

[13:53:12] [INFO] ━━━ Elixir v0.5.11 Conversion Diagnostic Summary ━━━

[13:53:12] [INFO]   Book: Broken Structures Salman Akhtar

[13:53:12] [INFO]   Total pages: 397

[13:53:12] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[13:53:12] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[13:53:12] [INFO]   Summaries generated: 1

[13:53:12] [INFO]     Success: 1, Failed: 0, Total bullets: 69

[13:53:12] [INFO]     Coverage: 94%

[13:53:12] [INFO]     Recall floor (deterministic, final set): theorists 62/74 (84%), conclusion items 3/3 (100%)

[13:53:12] [INFO]   Warnings: 0

[13:53:12] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar

[13:53:12] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.11_20260927-133331-627dc7f8.conversion.log.md

[13:53:12] [INFO]   Diagnostic JSONL: None

[13:53:12] [INFO]   Summary files (3):

[13:53:12] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.11_20260927-133331-627dc7f8_summary.md — generated-by v0.5.11 | run_id=20260927-133331-627dc7f8 | started=2026-09-27T13:36:32 | bullets=69

[13:53:12] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.11 | run_id=20260927-133331-627dc7f8 | started=2026-09-27T13:36:32 | bullets=69

[13:53:12] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.11_20260927-133331-627dc7f8.summary.md — generated-by v0.5.11 | run_id=20260927-133331-627dc7f8 | started=2026-09-27T13:36:32 | bullets=69

[13:53:12] [INFO]   Models loaded at exit: (none — all unloaded)

[13:53:12] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[13:53:12] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[13:53:12] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[13:53:12] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[13:53:12] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[13:53:12] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[13:53:12] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[13:53:12] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\images

[13:53:12] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[13:53:18] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\images

[13:53:24] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[13:53:24] [INFO]   [pipeline] after de-dup: 2 regions

[13:53:24] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.11\Broken Structures Salman Akhtar\regions

[13:53:24] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[13:53:24] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 69 keypoints)


---
Finished at: 2026-09-27T13:53:24.620768
