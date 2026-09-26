# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T08:02:58.073955

<!-- generated-by: Elixir v0.5.0 | run_id=20260926-080258-e5fb084b -->

---

[08:02:58] [SUCCESS] 🚀 Starting conversion…

[08:02:58] [DEBUG]   🔍 importing 'pypdf'…

[08:02:58] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[08:02:58] [DEBUG]   🔍 importing 'pdf2image'…

[08:02:58] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[08:02:58] [DEBUG]   🔍 importing 'tiktoken'…

[08:02:58] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[08:02:58] [DEBUG]   🔍 importing 'markitdown'…

[08:03:00] [DEBUG]   ✅ 'markitdown' ok (2.3s)

[08:03:00] [DEBUG]   🔍 importing 'rapidfuzz'…

[08:03:00] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[08:03:00] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[08:03:00] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[08:03:00] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[08:03:00] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[08:03:00] [DEBUG]   🔍 importing 'torch'…

[08:03:00] [DEBUG]   ✅ 'torch' ok (0.0s)

[08:03:00] [DEBUG]   🔍 importing 'transformers'…

[08:03:16] [DEBUG]   ✅ 'transformers' ok (15.8s)

[08:03:16] [DEBUG]   🔍 importing 'langextract'…

[08:03:16] [DEBUG]   ✅ 'langextract' ok (0.1s)

[08:03:16] [DEBUG]   ✅ Pre-flight dependency check passed

[08:03:16] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[08:03:16] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[08:03:16] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar.pdf

[08:03:16] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar

[08:03:16] [INFO]   Source type: normal_book

[08:03:16] [INFO]   App version: 0.5.0

[08:03:16] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[08:03:16] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[08:03:16] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[08:03:16] [INFO]   Ollama reachable (localhost:11434): True

[08:03:16] [INFO]   Provider: llamacpp

[08:03:16] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[08:03:16] [INFO]   [Phase 1 (Extraction)]

[08:03:16] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[08:03:16] [INFO]   [Phase 2 (Summarization)]

[08:03:16] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[08:03:16] [INFO]   ────────────────────────────────────────

[08:03:16] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[08:03:16] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[08:03:16] [INFO] ━━━━━━━━━━━━━━━━━━━━

[08:03:16] [INFO]   LLM OCR: True, Force OCR all: False

[08:03:16] [INFO]   Auto-detect scanned: True

[08:03:16] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:03:16] [INFO]   OCR retries: 2, Image max size: 1200

[08:03:16] [INFO]   Page range: all

[08:03:16] [INFO]   Selected chapters: 1 chapter(s)

[08:03:16] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[08:03:16] [INFO]   Segmentation: auto, Token limit: 2000

[08:03:16] [INFO]   Semantic: True, Page group: 10

[08:03:16] [INFO]   Generate summaries: True

[08:03:16] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:03:16] [INFO]   Fast model: , Heavy model: (disabled)

[08:03:16] [INFO]   Workers (requested): 1, Temperature: 0.7

[08:03:16] [INFO]   Self-consistency: False, Coverage threshold: 85%

[08:03:16] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[08:03:16] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[08:03:16] [INFO]   Academic rigor: False

[08:03:16] [INFO]   Max context tokens: 128000

[08:03:16] [INFO]   Max output tokens: 32768

[08:03:16] [INFO]   Keep-alive: 30m

[08:03:16] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[08:03:16] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[08:03:16] [INFO]   Translation: disabled

[08:03:16] [INFO]   Clean markdown: True, Token saver: True

[08:03:16] [INFO]   Content filter: True

[08:03:16] [INFO]   Extract tables: False, Math: False, Figures: False

[08:03:16] [INFO]   Visual-region crops: True

[08:03:16] [INFO]   Layout analysis: False

[08:03:16] [INFO]   DOCX author: Elixir, TOC: True

[08:03:16] [INFO]   Output paths (V7.5 subfolders):

[08:03:16] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[08:03:16] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[08:03:16] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[08:03:16] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\packets

[08:03:16] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\podcast

[08:03:16] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\logs\quality_report.json

[08:03:16] [INFO]   Resume mode: enabled — will skip done chapters

[08:03:16] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[08:03:16] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[08:03:16] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[08:03:16] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[08:03:16] [DEBUG]   💾 Disk space: 24.5 GB free

[08:03:16] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\.checkpoint.json

[08:04:32] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[08:04:32] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[08:04:32] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[08:04:32] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[08:04:32] [INFO] [TOC] Using PDF outlines: 22 entries.

[08:04:32] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[08:04:32] [DEBUG]   [TOC] Entries passed to segmenter: 22

[08:04:32] [DEBUG]   [TOC] - p.7: Table of Contents

[08:04:32] [DEBUG]   [TOC] - p.9: FOREWORD

[08:04:32] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[08:04:32] [DEBUG]   [TOC] … and 19 more

[08:04:32] [INFO]   🎯 User selected 1 chapter(s):

[08:04:32] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[08:04:33] [INFO]   📸 front_cover → front_cover.jpg

[08:04:33] [INFO]   📸 back_cover → back_cover.jpg

[08:04:33] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[08:04:33] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[08:04:33] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[08:04:33] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[08:04:34] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[08:04:34] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[08:04:34] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[08:04:34] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[08:04:34] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[08:04:34] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[08:04:35] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[08:04:35] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[08:04:35] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[08:04:35] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[08:04:35] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[08:04:36] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[08:04:36] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[08:04:36] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[08:04:37] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[08:04:37] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[08:04:37] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[08:04:37] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[08:04:38] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[08:04:38] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[08:04:38] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[08:04:38] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[08:04:38] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[08:04:38] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[08:04:38] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[08:04:38] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[08:04:38] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[08:04:38] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[08:04:38] [INFO]   ✅ markitdown ready for digital-page extraction

[08:04:38] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[08:04:38] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[08:04:38] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[08:04:38] [INFO]      Pages needing OCR: [152, 153, 154]

[08:04:38] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[08:04:38] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[08:04:38] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[08:04:41] [INFO]   📄 140/397 pages processed (35%)

[08:04:48] [INFO]   🔍 OCR  page 152/397 (scanned)…

[08:04:51] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[08:06:10] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[08:06:10] [INFO]   🔍 OCR  page 153/397 (scanned)…

[08:07:17] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[08:07:17] [INFO]   🔍 OCR  page 154/397 (scanned)…

[08:08:31] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[08:08:34] [INFO]   📄 160/397 pages processed (40%)

[08:08:35] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[08:08:35] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[08:08:35] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[08:08:35] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[08:08:35] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[08:08:35] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[08:08:35] [INFO] 📝 Raw markdown: 53,157 chars | [337.0s]

[08:08:35] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[08:08:35] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[08:08:35] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[08:08:35] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[08:08:35] [INFO] [Segmenter] Attempting chapter-level segmentation…

[08:08:35] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[08:08:35] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[08:08:35] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[08:08:35] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[08:08:35] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[08:08:35] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[08:08:35] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[08:08:35] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[08:08:35] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[08:08:35] [INFO]   📑 Filtered segments: kept 1 of 17

[08:08:35] [INFO] 📚 1 segment(s) detected | [337.1s]

[08:08:35] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[08:08:35] [INFO] 🌐 Detected language: en

[08:08:35] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[08:08:35] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[08:08:35] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\markdown\chapters

[08:08:35] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[08:08:35] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\markdown\chapters

[08:08:35] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[08:08:35] [INFO]   ⏱️ Summary phase starting | [337.4s]

[08:08:37] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[08:08:37] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[08:08:37] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[08:08:37] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[08:08:37] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[08:08:37] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[08:08:37] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[08:08:37] [INFO]   🌡️ Pre-flight: idle GPU temp = 61°C

[08:08:37] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 61°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[08:08:37] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[08:08:37] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[08:08:37] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[08:08:37] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[08:08:37] [DEBUG]   🎛️ Model profile: Default

[08:08:37] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[08:08:37] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[08:08:37] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[08:08:37] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[08:08:37] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[08:08:37] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[08:08:37] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[08:08:37] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[08:08:37] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[08:08:37] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[08:08:37] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[08:08:37] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[08:08:37] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[08:08:37] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[08:08:37] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[08:08:37] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[08:08:37] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[08:08:37] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[08:08:37] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[08:08:37] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[08:08:37] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[08:08:38] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5

[08:08:38] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[08:08:38] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[08:08:38] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[08:08:38] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[08:08:38] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[08:08:38] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[08:08:38] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[08:08:38] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[08:08:38] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:08:38] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[08:09:52] [INFO]     ✅ V0.3 Call 1/3: master summary = 589 words, 4665 chars

[08:09:52] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[08:09:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:09:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[08:10:30] [INFO]     ✅ V0.3 Call 2/3: 28 bullets derived from master summary

[08:10:30] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[08:10:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:10:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[08:10:49] [INFO]     ✅ V0.3 Call 3/3: exec summary = 210 words

[08:10:49] [DEBUG]     📝 Parsed: exec=1666 chars, bullets=28, thorough=4665 chars

[08:11:14] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[08:11:16] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[08:11:16] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (28 bullets, 210 exec words, 589 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[08:11:18] [DEBUG]     🔍 Fact-check: all 28 bullets verified ✓

[08:11:18] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[08:11:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:11:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[08:12:18] [INFO]     ✅ Additive sections via followup call: key_distinctions=1840 chars, theoretical_tensions=1614 chars

[08:12:18] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (28 bullets, 210 exec words, 589 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[08:12:18] [WARNING]     ⚠️ thorough_summary too short (589 words < 800 threshold) — requesting dedicated expansion…

[08:12:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[08:12:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[08:13:32] [INFO]     📖 Attempt 1/3: dedicated thorough = 589 words

[08:13:32] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[08:13:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[08:13:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[08:14:24] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying at temperature 0.0 (greedy)

[08:14:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.00) via llm_provider.llamacpp…

[08:14:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.00 max=8192 streaming…

[08:15:14] [DEBUG]     📏 V0.4.38 F2: attempt 4 — re-prompting with a quantified length directive (best was 589 < 800 min words)

[08:15:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[08:15:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[08:16:05] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=589) — keeping best-effort result

[08:16:05] [DEBUG]     ℹ️ Dedicated thorough call returned 589 words (not longer than original 589) — keeping original

[08:16:05] [INFO]     V0.05: Skipping bullet expansion — 28 bullets already meet the source-scaled target (27-40 for a 7405-word chapter; gap-fill will handle missing concepts).

[08:16:05] [INFO]     ✅ Final coverage 100%

[08:16:05] [DEBUG]     📏 F1: exec=210w, thorough=589w (source=7405w; targets exec<=250w, thorough<=3332w)

[08:18:00] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[08:18:00] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 18.3 (diff: -2.0)

[08:18:00] [INFO]     ℹ️ F3: Summary is 2.0 grade levels denser than source — expected for a compressed academic summary.

[08:18:02] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[08:18:02] [DEBUG]     🔄 J2: 4 cross-section redundancy(ies) found (exec↔bullets: 2, bullets↔thorough: 2)

[08:18:02] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 4 markers)

[08:18:02] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[08:18:02] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[08:18:02] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[08:18:19] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3360 per-pair calls)

[08:18:19] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[08:18:21] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (28/28 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[08:18:21] [INFO]   ℹ️ Summary has substantial content (exec=1666 chars, thorough=4662 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[08:18:21] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[08:18:21] [WARNING]   ⏱️⚠️ Deadline exceeded (584s > 480s) — skipping optional phase: scholar reflection

[08:18:21] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[08:18:21] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[08:18:21] [WARNING]   ⏱️⚠️ Deadline exceeded (584s > 480s) — skipping optional phase: semantic dedup

[08:18:21] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[08:18:21] [DEBUG]     🧹 V16.0.2 Bullet normalization: 28 bullets normalized

[08:18:21] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[08:18:21] [WARNING]   ⏱️⚠️ Deadline exceeded (584s > 480s) — skipping optional phase: bullet consolidation

[08:18:21] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[08:18:21] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5

[08:18:21] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[08:18:21] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[08:18:21] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Freud', 'Heimann', 'Magnan', 'Klein', 'Winnicott', 'Bach', 'Erikson']/74 authors in bullets (12%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']

[08:18:21] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Frances', 'Magnan', 'Jaspers', 'Schneider', 'Millon', 'Jacobson', 'Widiger', 'Leonhard', 'Shepherd', 'Polatin', 'Widiger and Frances', 'Klein', 'Winnicott', 'Bergman', 'Erikson', 'Bursten', 'Frances and Widiger', 'Gorton and Akhtar']/74 authors in thorough (41%) — MISSING from thorough: ['Stanton', 'Thomson', 'Hamilton', 'Byrne', 'Akhtar and Byrne']

[08:18:21] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']…

[08:18:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:18:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[08:18:46] [WARNING]     🚫 V18.20.3.2: gap-fill active-subject veto — dropped 'Kernberg: Associated paranoid personality with a borderline …' (source attributes this claim to 'Kernberg’s', not 'Kernberg')

[08:18:46] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[08:18:46] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (24.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=1, filler=0, added=7

[08:18:46] [DEBUG]     📊 V18.14.1: After round 1, 55 still missing from bullets: ['Kernberg', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[08:18:46] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kernberg', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[08:18:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:18:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[08:19:11] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akhtar and Byrne (1983) described the behavioral correlates of splitti…

[08:19:11] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[08:19:11] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (24.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[08:19:11] [DEBUG]     📊 V18.14.1: After round 2, 38 still missing from bullets: ['Schneider', 'Salzman', 'Millon', 'Jacobson', 'Winokur']…

[08:19:11] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Schneider', 'Salzman', 'Millon', 'Jacobson', 'Winokur']…

[08:19:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:19:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[08:19:26] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur (1985) is cited alongside Rettersol regarding the focus on par…

[08:19:26] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 7/8 bullets

[08:19:26] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[08:19:26] [DEBUG]     📊 V18.14.1: After round 3, 31 still missing from bullets: ['Winokur', 'Polatin', 'Slater and Roth', 'Tobak', 'Mahler']…

[08:19:26] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Winokur', 'Polatin', 'Slater and Roth', 'Tobak', 'Mahler']…

[08:19:26] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:19:26] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[08:19:56] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 8/8 bullets

[08:19:56] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (30.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[08:19:56] [DEBUG]     📊 V18.14.1: After round 4, 21 still missing from bullets: ['Allodi', 'Jack', 'Ndtei', 'Bursten', 'Siever and Kendler']…

[08:19:56] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Allodi', 'Jack', 'Ndtei', 'Bursten', 'Siever and Kendler']…

[08:19:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:19:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[08:20:19] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Allodi (1982) is cited in the text as part of a group of references us…

[08:20:19] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack (1984) is included among the authorities supporting the distincti…

[08:20:19] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ndtei (1986) is referenced in the context of differentiating reactive …

[08:20:19] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 5/8 bullets

[08:20:19] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (22.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[08:20:19] [DEBUG]     📊 V18.14.1: After round 5, 13 still missing from bullets: ['Allodi', 'Jack', 'Ndtei', 'Conlon', 'Reid']…

[08:20:19] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 34 bullets across 5 round(s)

[08:20:19] [WARNING]     ⚠️ V18.14.1: 13 theorists still missing from bullets after gap-fill: ['Allodi', 'Jack', 'Ndtei', 'Conlon', 'Reid', 'Lowenthal', 'Croewe', 'Grunberger'] — 13 never covered (round cap/deadline): ['Allodi', 'Jack', 'Ndtei', 'Conlon', 'Reid', 'Lowenthal', 'Croewe', 'Grunberger']

[08:20:19] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[08:20:19] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[08:20:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[08:20:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[08:20:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (2 item(s) were uncovered; all 9 now carried verbatim)

[08:20:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[08:20:19] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[08:20:20] [DEBUG]     🧹 Semantic dedup: removing bullet 25 (sim=0.89 with bullet 24)

[08:20:20] [DEBUG]     🧹 Semantic dedup: removing bullet 26 (sim=0.87 with bullet 24)

[08:20:20] [DEBUG]     🧹 Semantic dedup: removing bullet 57 (sim=0.88 with bullet 27)

[08:20:20] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.86 with bullet 36)

[08:20:20] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 68 → 64 bullets (removed 4 gap-fill/conclusion duplicates; 0.8s, non-skippable per V18.20.3.4)

[08:20:20] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5

[08:20:20] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[08:20:20] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[08:20:22] [INFO]     ℹ️ V0.4.23: 64 bullets ship (guidance floor was 27-40 for a 7405-word chapter) — NO CAP (user directive: full coverage; dedup/consolidation are the reducers, not truncation).

[08:20:22] [INFO]     🛡️ V18.2.13 Post-checks: 13 fixed, 5 flagged (of 64 bullets + exec + thorough)

[08:20:22] [DEBUG]       [truncated/flag] bullet[62]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[08:20:22] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …er (1908), Kretschmer (1927), Jaspers (1949), Schneider (195…

[08:20:22] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Polatin (1975)' has 34% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …hard (1959), Shepherd (1961), Polatin (1975), and Millon (19…

[08:20:22] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Millon (1981)' has 35% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …d (1961), Polatin (1975), and Millon (1981), consistently hi…

[08:20:22] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Bursten (1973a)' has 36% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …piro (1965), Jacobson (1971), Bursten (1973a), Kernberg (197…

[08:20:22] [DEBUG]       [quote_verification/fix] bullet[16]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (e.g., arrogance, hypervigilance) and 

[08:20:22] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —characterized by paradoxes such as profound mistrust coexis

[08:20:22] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and later contributions emphasizing early trauma, ego defic

[08:20:22] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (e.g., arrogance) and 

[08:20:22] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   of the PPD individual, characterized by contradictions such

[08:20:22] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the developmental substrate, involving projection of agg

[08:20:22] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   where the fear of betrayal maintains an illusory constant o

[08:20:22] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (e.g., arrogance, hypervigilance, moralistic rigidity) and 

[08:20:22] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   (e.g., timidity, gullibility, vulnerability to erotomania) 

[08:20:22] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (arrogance, mistrust) with the 

[08:20:22] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   ones (fear, gullibility), noting that this duality undersco

[08:20:22] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid Personality Disorder vs. Phobic Character: The ch

[08:20:22] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian Libidinal vs. Aggressive/Environmental Origins: T

[08:20:22] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 30/74 authors in thorough — MISSING from thorough: ['Stanton', 'Thomson', 'Hamilton', 'Byrne', 'Akhtar and Byrne']

[08:20:22] [WARNING]   ⏱️⚠️ Deadline exceeded (705s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[08:20:22] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 44 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[08:20:22] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:20:22] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[08:21:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater and Roth (1977) further highlighted the paradoxical nature of t…" — its name(s) never co-occur with the claim's key phrases in the source

[08:21:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Stanton (1978) contributed a nuanced observation regarding the dispari…" — its name(s) never co-occur with the claim's key phrases in the source

[08:21:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This period also saw Tobak (1989) identify a further contradiction in …" — its name(s) never co-occur with the claim's key phrases in the source

[08:21:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Volkan (1986) offered insights into man’s need for enemies and allies,…" — its name(s) never co-occur with the claim's key phrases in the source

[08:21:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Akhtar and Thomson (1982) developed a similar phenomenol…" — its name(s) never co-occur with the claim's key phrases in the source

[08:21:33] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:21:33] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, Bak (1946) is cited alongside Freud to support the idea …" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineates the paranoid adolescent, emphasizing how ear…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Kohut’s description of narcissistic rage provides context for understa…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bach’s observation of “mirror complementarity” informs the author’s co…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Fenichel’s work on masochism is implicitly referenced through discussi…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Roth contributes to the descriptive literature by noting the rigid, su…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Allodi’s insights on the role of actual childhood cruelty are echoed i…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack’s contributions, though less detailed in the provided text, likel…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei’s work is referenced in the context of developmental or clinical…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater and Roth’s joint contributions emphasize the contradictory prid…" — its name(s) never co-occur with the claim's key phrases in the source

[08:22:42] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[08:22:42] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[08:23:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon and Michels offered insights into the psychoanalytic dynamic…" — its name(s) never co-occur with the claim's key phrases in the source

[08:23:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser contributed to the broader discussion of paranoid pathology in…" — its name(s) never co-occur with the claim's key phrases in the source

[08:23:22] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Conlon and Reid made additional contributions to the descriptive and t…" — its name(s) never co-occur with the claim's key phrases in the source

[08:23:46] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 30/74 → 45/74 (3 chunked call(s), ≤12 names each; 8 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[08:23:46] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[08:23:46] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 1 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[08:23:46] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 60/74 in final bullets (missing: ['Bergman', 'Allodi', 'Jack', 'Ndtei', 'Bursten']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[08:23:46] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 909s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 909s of the budget.

[08:23:46] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[08:23:46] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":65,"exec_chars":1660,"chapter_done":true}

[08:23:46] [DEBUG]   📊 Progress: 1/1 done | 65 bullets | 1,660 chars exec summary

[08:23:46] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\checkpoints

[08:23:46] [INFO] 📄 Building DOCX report…

[08:23:46] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[08:23:47] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[08:23:47] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.0_20260926-080258-e5fb084b_summary.md + DOCX

[08:23:47] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[08:23:47] [INFO]   🧮 Embedding cache: 63 hits / 30 misses (68% hit-rate), 5000 entries

[08:23:47] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.0_20260926-080258-e5fb084b_summary.md

[08:23:47] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries

[08:23:47] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[08:23:47] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.0_20260926-080258-e5fb084b.summary.md

[08:23:47] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[08:23:47] [INFO]   ⏱️ DOCX phase starting | [1249.2s]

[08:23:47] [INFO] 📄 Building DOCX report…

[08:23:47] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[08:23:47] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[08:23:49] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[08:23:51] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[08:25:42] [INFO]   🎯 K1+Classification: 65 bullets — 12 core, 36 supporting, 17 additional

[08:25:42] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[08:25:42] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[08:25:42] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[08:25:42] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[08:25:42] [INFO]   📊 Citation graph: no citations found in the text.

[08:25:42] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[08:25:42] [SUCCESS] ✅ Conversion complete.

[08:25:59] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\logs\quality_report.json

[08:25:59] [INFO] 

[08:25:59] [INFO] ━━━ Thermal Safety Report ━━━

[08:25:59] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[08:25:59] [INFO]   Session duration: 17.4 min

[08:25:59] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[08:25:59] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[08:25:59] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[08:25:59] [INFO] 

[08:25:59] [INFO] ━━━ Elixir v0.5.0 Conversion Diagnostic Summary ━━━

[08:25:59] [INFO]   Book: Broken Structures Salman Akhtar

[08:25:59] [INFO]   Total pages: 397

[08:25:59] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[08:25:59] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[08:25:59] [INFO]   Summaries generated: 1

[08:25:59] [INFO]     Success: 1, Failed: 0, Total bullets: 65

[08:25:59] [INFO]     Coverage: 100%

[08:25:59] [INFO]     Recall floor (deterministic, final set): theorists 60/74 (81%), conclusion items 3/3 (100%)

[08:25:59] [INFO]   Warnings: 0

[08:25:59] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar

[08:25:59] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.0_20260926-080258-e5fb084b.conversion.log.md

[08:25:59] [INFO]   Diagnostic JSONL: None

[08:25:59] [INFO]   Summary files (3):

[08:25:59] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.0_20260926-080258-e5fb084b_summary.md — generated-by v0.5.0 | run_id=20260926-080258-e5fb084b | started=2026-09-26T08:08:37 | bullets=65

[08:25:59] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.0 | run_id=20260926-080258-e5fb084b | started=2026-09-26T08:08:37 | bullets=65

[08:25:59] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.0_20260926-080258-e5fb084b.summary.md — generated-by v0.5.0 | run_id=20260926-080258-e5fb084b | started=2026-09-26T08:08:37 | bullets=65

[08:25:59] [INFO]   Models loaded at exit: (none — all unloaded)

[08:25:59] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[08:25:59] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[08:25:59] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[08:25:59] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[08:25:59] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[08:26:00] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[08:26:00] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[08:26:00] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\images

[08:26:00] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[08:26:06] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\images

[08:26:13] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[08:26:13] [INFO]   [pipeline] after de-dup: 2 regions

[08:26:14] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\v5\Broken Structures Salman Akhtar\regions

[08:26:14] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[08:26:14] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 65 keypoints)


---
Finished at: 2026-09-26T08:26:14.258021
