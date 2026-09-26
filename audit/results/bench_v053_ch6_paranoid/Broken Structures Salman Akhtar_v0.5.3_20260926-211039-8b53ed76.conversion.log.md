# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-26T21:10:39.816189

<!-- generated-by: Elixir v0.5.3 | run_id=20260926-211039-8b53ed76 -->

---

[21:10:39] [SUCCESS] 🚀 Starting conversion…

[21:10:39] [DEBUG]   🔍 importing 'pypdf'…

[21:10:39] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[21:10:39] [DEBUG]   🔍 importing 'pdf2image'…

[21:10:39] [DEBUG]   ✅ 'pdf2image' ok (0.1s)

[21:10:39] [DEBUG]   🔍 importing 'tiktoken'…

[21:10:39] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[21:10:39] [DEBUG]   🔍 importing 'markitdown'…

[21:10:47] [DEBUG]   ✅ 'markitdown' ok (7.9s)

[21:10:47] [DEBUG]   🔍 importing 'rapidfuzz'…

[21:10:47] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[21:10:47] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[21:10:47] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[21:10:47] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[21:10:47] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[21:10:47] [DEBUG]   ✅ 'torch' installed

[21:10:47] [DEBUG]   ✅ 'transformers' installed

[21:10:47] [DEBUG]   ✅ 'langextract' installed

[21:10:47] [DEBUG]   ✅ Pre-flight dependency check passed

[21:10:47] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[21:10:47] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[21:10:47] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar.pdf

[21:10:47] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar

[21:10:47] [INFO]   Source type: normal_book

[21:10:47] [INFO]   App version: 0.5.3

[21:10:47] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[21:10:47] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[21:10:47] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[21:10:47] [INFO]   Ollama reachable (localhost:11434): True

[21:10:47] [INFO]   Provider: llamacpp

[21:10:47] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[21:10:47] [INFO]   [Phase 1 (Extraction)]

[21:10:47] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:10:47] [INFO]   [Phase 2 (Summarization)]

[21:10:47] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:10:47] [INFO]   ────────────────────────────────────────

[21:10:47] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[21:10:47] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[21:10:47] [INFO] ━━━━━━━━━━━━━━━━━━━━

[21:10:47] [INFO]   LLM OCR: True, Force OCR all: False

[21:10:47] [INFO]   Auto-detect scanned: True

[21:10:47] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:10:47] [INFO]   OCR retries: 2, Image max size: 1200

[21:10:47] [INFO]   Page range: all

[21:10:47] [INFO]   Selected chapters: 1 chapter(s)

[21:10:47] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[21:10:47] [INFO]   Segmentation: auto, Token limit: 2000

[21:10:47] [INFO]   Semantic: True, Page group: 10

[21:10:47] [INFO]   Generate summaries: True

[21:10:47] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:10:47] [INFO]   Fast model: , Heavy model: (disabled)

[21:10:47] [INFO]   Workers (requested): 1, Temperature: 0.7

[21:10:47] [INFO]   Self-consistency: False, Coverage threshold: 85%

[21:10:47] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[21:10:47] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[21:10:47] [INFO]   Academic rigor: False

[21:10:47] [INFO]   Max context tokens: 128000

[21:10:47] [INFO]   Max output tokens: 32768

[21:10:47] [INFO]   Keep-alive: 30m

[21:10:48] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[21:10:48] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[21:10:48] [INFO]   Translation: disabled

[21:10:48] [INFO]   Clean markdown: True, Token saver: True

[21:10:48] [INFO]   Content filter: True

[21:10:48] [INFO]   Extract tables: False, Math: False, Figures: False

[21:10:48] [INFO]   Visual-region crops: True

[21:10:48] [INFO]   Layout analysis: False

[21:10:48] [INFO]   DOCX author: Elixir, TOC: True

[21:10:48] [INFO]   Output paths (V7.5 subfolders):

[21:10:48] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[21:10:48] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[21:10:48] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[21:10:48] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\packets

[21:10:48] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\podcast

[21:10:48] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\logs\quality_report.json

[21:10:48] [INFO]   Resume mode: enabled — will skip done chapters

[21:10:48] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[21:10:48] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[21:10:48] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[21:10:48] [WARNING]   ⚠️ VRAM OVERBUDGET (peak 12.9 GB > 12.0 GB) — acknowledged interactively by the user: continuing.

[21:10:48] [DEBUG]   💾 Disk space: 23.1 GB free

[21:10:48] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\.checkpoint.json

[21:11:58] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[21:11:58] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[21:11:58] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[21:11:58] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[21:11:58] [INFO] [TOC] Using PDF outlines: 22 entries.

[21:11:58] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[21:11:58] [DEBUG]   [TOC] Entries passed to segmenter: 22

[21:11:58] [DEBUG]   [TOC] - p.7: Table of Contents

[21:11:58] [DEBUG]   [TOC] - p.9: FOREWORD

[21:11:58] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[21:11:58] [DEBUG]   [TOC] … and 19 more

[21:11:58] [INFO]   🎯 User selected 1 chapter(s):

[21:11:58] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[21:11:58] [INFO]   📸 front_cover → front_cover.jpg

[21:11:58] [INFO]   📸 back_cover → back_cover.jpg

[21:11:58] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[21:11:58] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[21:11:58] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[21:11:59] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[21:11:59] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[21:11:59] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[21:11:59] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[21:12:00] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[21:12:00] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[21:12:00] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[21:12:00] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[21:12:00] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[21:12:00] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[21:12:01] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[21:12:01] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[21:12:01] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[21:12:01] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[21:12:01] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[21:12:01] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[21:12:02] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[21:12:02] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[21:12:02] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[21:12:02] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[21:12:02] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[21:12:03] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[21:12:03] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[21:12:03] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[21:12:03] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[21:12:03] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[21:12:03] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[21:12:03] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[21:12:03] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[21:12:03] [INFO]   ✅ markitdown ready for digital-page extraction

[21:12:03] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[21:12:03] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[21:12:03] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[21:12:03] [INFO]      Pages needing OCR: [152, 153, 154]

[21:12:03] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[21:12:03] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[21:12:03] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[21:12:05] [INFO]   📄 140/397 pages processed (35%)

[21:12:11] [INFO]   🔍 OCR  page 152/397 (scanned)…

[21:12:13] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[21:12:46] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[21:12:46] [INFO]   🔍 OCR  page 153/397 (scanned)…

[21:13:16] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[21:13:16] [INFO]   🔍 OCR  page 154/397 (scanned)…

[21:13:55] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[21:13:58] [INFO]   📄 160/397 pages processed (40%)

[21:13:58] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[21:13:58] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[21:13:58] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[21:13:58] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[21:13:58] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[21:13:58] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[21:13:58] [INFO] 📝 Raw markdown: 53,157 chars | [198.5s]

[21:13:58] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[21:13:58] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[21:13:58] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[21:13:58] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[21:13:58] [INFO] [Segmenter] Attempting chapter-level segmentation…

[21:13:58] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:13:58] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[21:13:58] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[21:13:58] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[21:13:58] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[21:13:58] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[21:13:58] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[21:13:58] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[21:13:58] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[21:13:58] [INFO]   📑 Filtered segments: kept 1 of 17

[21:13:58] [INFO] 📚 1 segment(s) detected | [198.6s]

[21:13:58] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[21:13:58] [INFO] 🌐 Detected language: en

[21:13:58] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[21:13:58] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[21:13:58] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\markdown\chapters

[21:13:58] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[21:13:58] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\markdown\chapters

[21:13:58] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3906 bytes)

[21:13:58] [INFO]   ⏱️ Summary phase starting | [198.9s]

[21:14:00] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[21:14:00] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[21:14:00] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[21:14:00] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[21:14:00] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[21:14:00] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[21:14:00] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[21:14:00] [INFO]   🌡️ Pre-flight: idle GPU temp = 62°C

[21:14:00] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 62°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[21:14:00] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[21:14:00] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[21:14:00] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[21:14:00] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[21:14:00] [DEBUG]   🎛️ Model profile: Default

[21:14:00] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[21:14:01] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[21:14:01] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[21:14:01] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[21:14:01] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[21:14:01] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[21:14:01] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[21:14:01] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[21:14:01] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[21:14:01] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[21:14:01] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[21:14:01] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[21:14:01] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[21:14:01] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[21:14:01] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[21:14:01] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[21:14:01] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[21:14:01] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[21:14:01] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[21:14:01] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[21:14:01] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[21:14:01] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.3

[21:14:01] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[21:14:01] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[21:14:01] [INFO]     📊 V17.2: Prepended deterministic analysis (3791 chars) — citation recall 78%→100%

[21:14:01] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[21:14:01] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:14:01] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[21:14:01] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[21:14:01] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[21:14:01] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:14:01] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[21:15:36] [INFO]     ✅ V0.3 Call 1/3: master summary = 1049 words, 8171 chars

[21:15:36] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[21:15:36] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:15:36] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[21:16:21] [INFO]     ✅ V0.3 Call 2/3: 32 bullets derived from master summary

[21:16:21] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[21:16:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:16:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[21:16:43] [INFO]     ✅ V0.3 Call 3/3: exec summary = 262 words

[21:16:43] [DEBUG]     📝 Parsed: exec=2094 chars, bullets=32, thorough=8171 chars

[21:17:32] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[21:17:34] [DEBUG]     🔍 Coverage detail: 7/7 keywords found | missing: []

[21:17:34] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (32 bullets, 262 exec words, 1049 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[21:17:35] [DEBUG]     🔍 Fact-check: all 32 bullets verified ✓

[21:17:35] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[21:17:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:17:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[21:18:28] [INFO]     ✅ Additive sections via followup call: key_distinctions=1640 chars, theoretical_tensions=1479 chars

[21:18:29] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (32 bullets, 262 exec words, 1049 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[21:18:29] [INFO]     ⚠️ 32 bullets — requesting dedicated bullet expansion (full output budget)…

[21:18:29] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:18:29] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=8192 streaming…

[21:19:36] [INFO]     ✅ Final coverage 100%

[21:19:36] [DEBUG]     📏 F1: exec=262w, thorough=1049w (source=7405w; targets exec<=250w, thorough<=3332w)

[21:21:27] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[21:21:27] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 19.5 (diff: -3.2)

[21:21:27] [INFO]     ℹ️ F3: Summary is 3.2 grade levels denser than source — expected for a compressed academic summary.

[21:21:28] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[21:21:28] [DEBUG]     🔄 J2: 24 cross-section redundancy(ies) found (exec↔bullets: 3, bullets↔thorough: 21)

[21:21:28] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 2 markers)

[21:21:28] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[21:21:28] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[21:21:28] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[21:21:45] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3808 per-pair calls)

[21:21:45] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[21:21:47] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (32/32 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[21:21:47] [INFO]   ℹ️ Summary has substantial content (exec=2094 chars, thorough=8168 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[21:21:47] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[21:21:47] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[21:21:47] [DEBUG]     🎓 Theorist coverage check: 30 named author(s) found in source — verifying each is covered

[21:21:47] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared (delay disabled)

[21:21:47] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:21:47] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[21:23:08] [INFO]     📜 Scholar response truncated — one additive continuation retry (V18.20.4.12 / O-a4)

[21:23:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:23:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=6144 streaming…

[21:23:43] [DEBUG]     🎓 Dropped ungrounded gap-fill: Hamilton (1974, 1984), elaborating on Fish's work, distingui…

[21:23:43] [DEBUG]     🎓 Dropped gap-fill without quote: Kretschmer's sexual prowess contradiction is only partially …

[21:23:43] [DEBUG]     🎓 Dropped gap-fill without quote: Leonhard, Shepherd, Polatin, Hamilton, Tobak specific contri…

[21:23:43] [DEBUG]     🎓 Dropped gap-fill without quote: DSM-III specific omitted features (grandiosity, sexual diffi…

[21:23:43] [DEBUG]     🎓 Dropped gap-fill without quote: The six core contradictions summary is incomplete in previou…

[21:23:43] [DEBUG]     🎓 Dropped ungrounded gap-fill: Hamilton (1974, 1984) distinguished two kinds: "sensitive" (…

[21:23:43] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 27)

[21:23:43] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}

[21:23:43] [INFO]     🧩 V18.20.3.4: Filtered 1 thinking/scar bullet(s) from scholar gap-fill before merge

[21:23:43] [INFO]     🧽 V0.4.23: Filler floor dropped 1 citation-adjacency bullet(s) from scholar gap-fill before merge

[21:23:43] [INFO]     🎓 Gap-fill: added 26 new bullet(s) from scholar reflection (source-grounded)

[21:23:43] [INFO]     🎓 Scholar reflection: identified 12 gap(s), filled 26 with new bullets

[21:23:43] [DEBUG]     🎓 V18.2: Scholar reflections text suppressed (gap-fill only)

[21:23:43] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[21:23:43] [WARNING]   ⏱️⚠️ Deadline exceeded (583s > 480s) — skipping optional phase: semantic dedup

[21:23:43] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[21:23:43] [DEBUG]     🧹 V16.0.2 Bullet normalization: 58 bullets normalized

[21:23:43] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[21:23:43] [WARNING]   ⏱️⚠️ Deadline exceeded (583s > 480s) — skipping optional phase: bullet consolidation

[21:23:43] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[21:23:43] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.3

[21:23:43] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[21:23:43] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[21:23:43] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Polatin', 'Tobak', 'Klein', 'Winnicott', 'Bak', 'Erikson', 'Bursten', 'Morey']/74 authors in bullets (34%) — MISSING from bullets: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[21:23:43] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Kendler', 'Leonhard', 'Shepherd', 'Polatin', 'Klein', 'Winnicott', 'Bach', 'Fenichel', 'Bergman', 'Erikson', 'Bursten', 'Siever and Kendler', 'Stone', 'Morey', 'Ovessey', 'Walters', 'Varghesi', 'Gorton and Akhtar', 'Siever']/74 authors in thorough (47%) — MISSING from thorough: ['Stanton', 'Thomson', 'Hamilton', 'Frances', 'Byrne']

[21:23:43] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']…

[21:23:43] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:23:43] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:24:00] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Byrne: Co-authored descriptions of the behavioral correlates of splitt…

[21:24:00] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 7/8 bullets

[21:24:00] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (17.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[21:24:00] [DEBUG]     📊 V18.14.1: After round 1, 37 still missing from bullets: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[21:24:00] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[21:24:00] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:24:00] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:24:12] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets

[21:24:12] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (12.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[21:24:13] [DEBUG]     📊 V18.14.1: After round 2, 26 still missing from bullets: ['Kohut', 'Bach', 'Fenichel', 'Bergman', 'Allodi']…

[21:24:13] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Kohut', 'Bach', 'Fenichel', 'Bergman', 'Allodi']…

[21:24:13] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:24:13] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:24:28] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited among the key…

[21:24:28] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is included among the key con…

[21:24:28] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets

[21:24:28] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (15.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[21:24:28] [DEBUG]     📊 V18.14.1: After round 3, 20 still missing from bullets: ['Kohut', 'Green', 'Pao', 'Socarides', 'Siever and Kendler']…

[21:24:28] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Kohut', 'Green', 'Pao', 'Socarides', 'Siever and Kendler']…

[21:24:28] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:24:28] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:24:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) description of narcissistic rage is cited among the wor…

[21:24:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is included in the list of so…

[21:24:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is mentioned as part of the refer…

[21:24:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is cited alongside …

[21:24:39] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets

[21:24:39] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (10.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[21:24:39] [INFO]     🔁 V18.20.3.7: 'Kohut' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[21:24:39] [INFO]     🔁 V18.20.3.7: 'Green' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[21:24:39] [DEBUG]     📊 V18.14.1: After round 4, 13 still missing from bullets: ['Kohut', 'Green', 'Pao', 'Socarides', 'Conlon']…

[21:24:39] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Kohut', 'Green', 'Pao', 'Socarides', 'Conlon']… (mention-only: ['Kohut', 'Green'])

[21:24:39] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:24:39] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:24:51] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Winokur and Croewe’s work was noted as an example of textbook descript…

[21:24:51] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 7/8 bullets

[21:24:51] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (12.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[21:24:51] [DEBUG]     📊 V18.14.1: After round 5, 6 still missing from bullets: ['Croewe', 'Rettersol', 'Ovessey', 'Walters', 'Varghesi']…

[21:24:51] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 32 bullets across 5 round(s)

[21:24:51] [WARNING]     ⚠️ V18.14.1: 6 theorists still missing from bullets after gap-fill: ['Croewe', 'Rettersol', 'Ovessey', 'Walters', 'Varghesi', 'Munro'] — 6 never covered (round cap/deadline): ['Croewe', 'Rettersol', 'Ovessey', 'Walters', 'Varghesi', 'Munro']

[21:24:51] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[21:24:51] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[21:24:51] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[21:24:51] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[21:24:51] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 24 (sim=0.85 with bullet 1)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 46 (sim=0.85 with bullet 37)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 47 (sim=0.90 with bullet 38)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 48 (sim=0.85 with bullet 33)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 49 (sim=0.88 with bullet 34)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 52 (sim=0.95 with bullet 37)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 53 (sim=0.98 with bullet 38)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 57 (sim=0.95 with bullet 41)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.99 with bullet 42)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 65 (sim=0.95 with bullet 61)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 78 (sim=0.87 with bullet 77)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 79 (sim=0.90 with bullet 77)

[21:24:52] [DEBUG]     🧹 Semantic dedup: removing bullet 90 (sim=0.87 with bullet 76)

[21:24:52] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 94 → 81 bullets (removed 13 gap-fill/conclusion duplicates; 1.3s, non-skippable per V18.20.3.4)

[21:24:52] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v5.3

[21:24:52] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[21:24:52] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3791 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[21:24:55] [INFO]     🛡️ V18.2.13 Post-checks: 21 fixed, 13 flagged (of 81 bullets + exec + thorough)

[21:24:55] [DEBUG]       [sentence_fusion/flag] bullet[15]: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  structurally embedded in ego-syntonically personalities, often pre

[21:24:55] [DEBUG]       [consistency/flag] bullet[18]: false 'missing' claim: 'omitted' followed by 'crucial features such as self-esteem def' — but 7/8 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …ven items for consistency but omitted crucial features such …

[21:24:55] [DEBUG]       [attribution/flag] bullet[34]: attribution mismatch: summary's claim about 'Kretschmer (1927)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Kretschmer (1927) highlighted …

[21:24:55] [DEBUG]       [attribution/flag] bullet[35]: attribution mismatch: summary's claim about 'Jaspers (1949)' has 43% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Jaspers (1949) described how s…

[21:24:55] [DEBUG]       [attribution/flag] bullet[37]: attribution mismatch: summary's claim about 'Shepherd (1961)' has 45% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Shepherd (1961) detailed how s…

[21:24:55] [DEBUG]       [space/fix] bullet[53]: split 'review' -> 're view' (source-validated)  |  Frances: Co-authored a 1985 review with Widiger that attri…

[21:24:55] [DEBUG]       [space/fix] bullet[74]: split 'review' -> 're view' (source-validated)  |  …he affect of vengeance in his review of relevant psychologic…

[21:24:55] [DEBUG]       [truncated/flag] bullet[79]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[21:24:55] [DEBUG]       [garble_llm_repair/flag] exec: semantic LLM repair returned empty/short text — original kept.  |  This chapter presents a unified phenomenological framework f

[21:24:55] [DEBUG]       [dropped_letter/flag] exec: likely garbled token: 'paranoias' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …rentiating PPD from psychotic paranoias, phobic character, a…

[21:24:55] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'ego-syntonically' is not in the source or English lexicon but ends with source-word 'egosyntonic' + suffix 'ally' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  alization of paranoia in ego-syntonically embedded personalities, 

[21:24:55] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jaspers (1949)' has 36% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …n entitlement and inadequacy; Jaspers (1949) described "self…

[21:24:55] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Schneider (1950)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …iation with overcompensation; Schneider (1950) distinguished…

[21:24:55] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Jacobson (1971)' has 39% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  …nd a biased focus on "clues." Jacobson (1971) linked PPD to …

[21:24:55] [DEBUG]       [consistency/flag] thorough: false 'missing' claim: 'omitted' followed by 'crucial features such as superego uneven' — but 4/5 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  …bears grudges," both versions omitted crucial features such …

[21:24:55] [DEBUG]       [quote_verification/fix] bullet[21]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (e.g., arrogance) and 

[21:24:55] [DEBUG]       [quote_verification/fix] bullet[36]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  : combative types who are 

[21:24:55] [DEBUG]       [quote_verification/fix] bullet[36]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and seek justice, versus eccentric types who are 

[21:24:55] [DEBUG]       [quote_verification/fix] bullet[40]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  grandiosity, sexual difficulties, hidden feelings of inferio

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ; Leonhard (1959) noted their ambition and sensitivity to cr

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   as the developmental substrate of severe character patholog

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   interpretive style of paranoid cognition, characterized by 

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   Jacobson (1971) linked PPD to sadomasochistic family atmosp

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  —an ambivalently loved figure that must be both needed and f

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   both versions omitted crucial features such as superego une

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   manifestations (e.g., arrogance, hypervigilance, moralistic

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   features (e.g., timidity, gullibility, fear of loving), emp

[21:24:55] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   that prevents despair (Bergman 1978). It also discusses pot

[21:24:55] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   beliefs, whereas paranoid personality involves diffuse, les

[21:24:55] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  continued to exist independently of each other

[21:24:55] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ): The chapter highlights a central ambiguity in the paranoi

[21:24:55] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   features with the unconscious and 

[21:24:55] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[21:24:55] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian (libidinal) vs. Object-Relations/Anti-Freudian pe

[21:24:55] [INFO]     ℹ️ V0.4.23: 81 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[21:24:55] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 35/74 authors in thorough — MISSING from thorough: ['Stanton', 'Thomson', 'Hamilton', 'Frances', 'Byrne']

[21:24:55] [WARNING]   ⏱️⚠️ Deadline exceeded (655s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[21:24:55] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 39 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[21:24:55] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:24:55] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[21:25:39] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter further situates the differential diagnosis and diagnostic…" — its name(s) never co-occur with the claim's key phrases in the source

[21:25:39] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter’s proposed composite profile is argued to be superior to c…" — its name(s) never co-occur with the claim's key phrases in the source

[21:26:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:26:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[21:26:44] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Anthony (1981) delineated the paranoid adolescent, identifying a disti…" — its name(s) never co-occur with the claim's key phrases in the source

[21:26:44] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Furthermore, the chapter highlights the work of Bak (1946), whose insi…" — its name(s) never co-occur with the claim's key phrases in the source

[21:26:44] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the realm of differential diagnosis, Jack (1985) and Allodi (1970) …" — its name(s) never co-occur with the claim's key phrases in the source

[21:26:44] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Tobak (1989) contributed a significant descriptive observatio…" — its name(s) never co-occur with the claim's key phrases in the source

[21:26:47] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:26:48] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Green (1986) offered a critical essay on moral narcissism, highlightin…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao (1969) provided essential work on morbid jealousy, detailing the s…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Socarides (1966) contributed a nuanced view on the affect of vengeance…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mackinnon and Michels (1968) provided a psychoanalytic framework that …" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wurmser (1970) explored the role of projection and its variations, off…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Conlon (1964) described the phenomenon of "negative transference," whi…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Reid (1970) contributed to the understanding of paranoid cognition by …" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Lowenthal (1962) examined the affective dynamics of paranoia, noting h…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Croewe (1975) provided descriptive clarity on the behavioral manifesta…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Grunberger (1982) further elaborated on the cognitive style of paranoi…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:34] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Rettersol (1985) distinguished paranoid personality from delusional di…" — its name(s) never co-occur with the claim's key phrases in the source

[21:27:43] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 35/74 → 49/74 (3 chunked call(s), ≤12 names each; 3 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[21:27:43] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 65/74 in final bullets (missing: ['Jack', 'Ndtei', 'Lowenthal', 'Croewe', 'Rettersol']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[21:27:43] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[21:27:43] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 823s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 823s of the budget.

[21:27:43] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[21:27:43] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":81,"exec_chars":2094,"chapter_done":true}

[21:27:43] [DEBUG]   📊 Progress: 1/1 done | 81 bullets | 2,094 chars exec summary

[21:27:43] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\checkpoints

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '2026-09' (range:2026-2009) NOT found in source — possible fabrication.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '1887' (ce:1887) NOT found in source — possible fabrication.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '1902' (ce:1902) NOT found in source — possible fabrication.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: summary date '2026-09' (range:2026-2009) NOT found in source — possible fabrication.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1980s' (decade:1980) NOT found in summary — possible omission.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[21:27:43] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[21:27:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[21:27:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1945' (ce:1945) NOT found in summary — possible omission.

[21:27:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[21:27:44] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[21:27:44] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting: 7 source author(s) NOT found in the summary (Croewe, Jack, Lowenthal, Morey, Munro, Ndtei, Rettersol

[21:27:44] [INFO] 📄 Building DOCX report…

[21:27:44] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[21:27:44] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[21:27:44] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.3_20260926-211039-8b53ed76_summary.md + DOCX

[21:27:44] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[21:27:44] [INFO]   🧮 Embedding cache: 63 hits / 34 misses (65% hit-rate), 5000 entries

[21:27:44] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.3_20260926-211039-8b53ed76_summary.md

[21:27:44] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries

[21:27:44] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[21:27:44] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.3_20260926-211039-8b53ed76.summary.md

[21:27:44] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[21:27:44] [INFO]   ⏱️ DOCX phase starting | [1024.6s]

[21:27:44] [INFO] 📄 Building DOCX report…

[21:27:44] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[21:27:44] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[21:27:46] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[21:27:48] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[21:29:51] [INFO]   🎯 K1+Classification: 81 bullets — 16 core, 46 supporting, 19 additional

[21:29:51] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[21:29:51] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[21:29:51] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[21:29:51] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[21:29:51] [INFO]   📊 Citation graph: no citations found in the text.

[21:29:51] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[21:29:51] [SUCCESS] ✅ Conversion complete.

[21:30:08] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\logs\quality_report.json

[21:30:08] [INFO] 

[21:30:08] [INFO] ━━━ Thermal Safety Report ━━━

[21:30:08] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[21:30:08] [INFO]   Session duration: 16.1 min

[21:30:08] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[21:30:08] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[21:30:08] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[21:30:08] [INFO] 

[21:30:08] [INFO] ━━━ Elixir v0.5.3 Conversion Diagnostic Summary ━━━

[21:30:08] [INFO]   Book: Broken Structures Salman Akhtar

[21:30:08] [INFO]   Total pages: 397

[21:30:08] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[21:30:08] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[21:30:08] [INFO]   Summaries generated: 1

[21:30:08] [INFO]     Success: 1, Failed: 0, Total bullets: 81

[21:30:08] [INFO]     Coverage: 100%

[21:30:08] [INFO]     Recall floor (deterministic, final set): theorists 65/74 (88%), conclusion items 3/3 (100%)

[21:30:08] [INFO]   Warnings: 0

[21:30:08] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar

[21:30:08] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.3_20260926-211039-8b53ed76.conversion.log.md

[21:30:08] [INFO]   Diagnostic JSONL: None

[21:30:08] [INFO]   Summary files (3):

[21:30:08] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.3_20260926-211039-8b53ed76_summary.md — generated-by v0.5.3 | run_id=20260926-211039-8b53ed76 | started=2026-09-26T21:14:00 | bullets=81

[21:30:08] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.3 | run_id=20260926-211039-8b53ed76 | started=2026-09-26T21:14:00 | bullets=81

[21:30:08] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.3_20260926-211039-8b53ed76.summary.md — generated-by v0.5.3 | run_id=20260926-211039-8b53ed76 | started=2026-09-26T21:14:00 | bullets=81

[21:30:08] [INFO]   Models loaded at exit: (none — all unloaded)

[21:30:08] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[21:30:08] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[21:30:08] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[21:30:08] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[21:30:08] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[21:30:09] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[21:30:09] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[21:30:09] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\images

[21:30:09] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[21:30:16] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\images

[21:30:21] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[21:30:21] [INFO]   [pipeline] after de-dup: 2 regions

[21:30:22] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\v5.3\Broken Structures Salman Akhtar\regions

[21:30:22] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[21:30:22] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 81 keypoints)


---
Finished at: 2026-09-26T21:30:22.513049
