# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T21:43:48.749161

<!-- generated-by: Elixir v0.5.14 | run_id=20260927-214348-6774fcc0 -->

---

[21:43:48] [SUCCESS] 🚀 Starting conversion…

[21:43:48] [DEBUG]   🔍 importing 'pypdf'…

[21:43:48] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[21:43:48] [DEBUG]   🔍 importing 'pdf2image'…

[21:43:48] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[21:43:48] [DEBUG]   🔍 importing 'tiktoken'…

[21:43:48] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[21:43:48] [DEBUG]   🔍 importing 'markitdown'…

[21:43:50] [DEBUG]   ✅ 'markitdown' ok (1.6s)

[21:43:50] [DEBUG]   🔍 importing 'rapidfuzz'…

[21:43:50] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[21:43:50] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[21:43:50] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[21:43:50] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[21:43:50] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[21:43:50] [DEBUG]   ✅ 'torch' installed

[21:43:50] [DEBUG]   ✅ 'transformers' installed

[21:43:50] [DEBUG]   ✅ 'langextract' installed

[21:43:50] [DEBUG]   ✅ Pre-flight dependency check passed

[21:43:50] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[21:43:50] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[21:43:50] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar.pdf

[21:43:50] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar

[21:43:50] [INFO]   Source type: normal_book

[21:43:50] [INFO]   App version: 0.5.14

[21:43:50] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[21:43:50] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[21:43:50] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[21:43:50] [INFO]   Ollama reachable (localhost:11434): True

[21:43:50] [INFO]   Provider: llamacpp

[21:43:50] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[21:43:50] [INFO]   [Phase 1 (Extraction)]

[21:43:50] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:43:50] [INFO]   [Phase 2 (Summarization)]

[21:43:50] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[21:43:50] [INFO]   ────────────────────────────────────────

[21:43:50] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[21:43:50] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[21:43:50] [INFO] ━━━━━━━━━━━━━━━━━━━━

[21:43:50] [INFO]   LLM OCR: True, Force OCR all: False

[21:43:50] [INFO]   Auto-detect scanned: True

[21:43:50] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:43:50] [INFO]   OCR retries: 2, Image max size: 1200

[21:43:50] [INFO]   Page range: all

[21:43:50] [INFO]   Selected chapters: 1 chapter(s)

[21:43:50] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[21:43:50] [INFO]   Segmentation: auto, Token limit: 2000

[21:43:50] [INFO]   Semantic: True, Page group: 10

[21:43:50] [INFO]   Generate summaries: True

[21:43:50] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:43:50] [INFO]   Fast model: , Heavy model: (disabled)

[21:43:50] [INFO]   Workers (requested): 1, Temperature: 0.7

[21:43:50] [INFO]   Self-consistency: False, Coverage threshold: 85%

[21:43:50] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[21:43:50] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[21:43:50] [INFO]   Academic rigor: False

[21:43:50] [INFO]   Max context tokens: 128000

[21:43:50] [INFO]   Max output tokens: 32768

[21:43:50] [INFO]   Keep-alive: 30m

[21:43:50] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[21:43:50] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[21:43:50] [INFO]   Translation: disabled

[21:43:50] [INFO]   Clean markdown: True, Token saver: True

[21:43:50] [INFO]   Content filter: True

[21:43:50] [INFO]   Extract tables: False, Math: False, Figures: False

[21:43:50] [INFO]   Visual-region crops: True

[21:43:50] [INFO]   Layout analysis: False

[21:43:50] [INFO]   DOCX author: Elixir, TOC: True

[21:43:50] [INFO]   Output paths (V7.5 subfolders):

[21:43:50] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[21:43:50] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[21:43:50] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[21:43:50] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\packets

[21:43:50] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\podcast

[21:43:50] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\logs\quality_report.json

[21:43:50] [INFO]   Resume mode: enabled — will skip done chapters

[21:43:50] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[21:43:50] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[21:43:50] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[21:43:50] [INFO]   ℹ️ V0.5.14: VRAM budget estimate (peak 12.9 GB) > total (12.0 GB), BUT nvidia-smi reports 0.22 GB free (GPU-wide, across all processes). The param-count estimate may be wrong for this model. Proceeding — llama.cpp will error at load time if the model truly doesn't fit.

[21:43:50] [DEBUG]   💾 Disk space: 22.2 GB free

[21:43:50] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\.checkpoint.json

[21:44:59] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[21:44:59] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[21:44:59] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[21:44:59] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[21:44:59] [INFO] [TOC] Using PDF outlines: 22 entries.

[21:44:59] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[21:44:59] [DEBUG]   [TOC] Entries passed to segmenter: 22

[21:44:59] [DEBUG]   [TOC] - p.7: Table of Contents

[21:44:59] [DEBUG]   [TOC] - p.9: FOREWORD

[21:44:59] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[21:44:59] [DEBUG]   [TOC] … and 19 more

[21:44:59] [INFO]   🎯 User selected 1 chapter(s):

[21:44:59] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[21:45:00] [INFO]   📸 front_cover → front_cover.jpg

[21:45:00] [INFO]   📸 back_cover → back_cover.jpg

[21:45:00] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[21:45:00] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[21:45:00] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[21:45:00] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[21:45:01] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[21:45:01] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[21:45:01] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[21:45:01] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[21:45:01] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[21:45:02] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[21:45:02] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[21:45:02] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[21:45:02] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[21:45:03] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[21:45:03] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[21:45:03] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[21:45:03] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[21:45:04] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[21:45:04] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[21:45:04] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[21:45:04] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[21:45:04] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[21:45:05] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[21:45:05] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[21:45:05] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[21:45:05] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[21:45:05] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[21:45:05] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[21:45:05] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[21:45:05] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[21:45:05] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[21:45:05] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[21:45:05] [INFO]   ✅ markitdown ready for digital-page extraction

[21:45:05] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[21:45:05] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[21:45:05] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.1s)

[21:45:05] [INFO]      Pages needing OCR: [152, 153, 154]

[21:45:05] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[21:45:05] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[21:45:05] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[21:45:07] [INFO]   📄 140/397 pages processed (35%)

[21:45:13] [INFO]   🔍 OCR  page 152/397 (scanned)…

[21:45:15] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[21:46:07] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[21:46:07] [INFO]   🔍 OCR  page 153/397 (scanned)…

[21:46:53] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[21:46:53] [INFO]   🔍 OCR  page 154/397 (scanned)…

[21:47:47] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[21:47:49] [INFO]   📄 160/397 pages processed (40%)

[21:47:49] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[21:47:49] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[21:47:49] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[21:47:49] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[21:47:49] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[21:47:49] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[21:47:49] [INFO] 📝 Raw markdown: 53,157 chars | [241.1s]

[21:47:49] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[21:47:49] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[21:47:49] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[21:47:49] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[21:47:49] [INFO] [Segmenter] Attempting chapter-level segmentation…

[21:47:49] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[21:47:49] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[21:47:49] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[21:47:49] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[21:47:49] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[21:47:49] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[21:47:49] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[21:47:49] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[21:47:49] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[21:47:49] [INFO]   📑 Filtered segments: kept 1 of 17

[21:47:49] [INFO] 📚 1 segment(s) detected | [241.2s]

[21:47:50] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[21:47:50] [INFO] 🌐 Detected language: en

[21:47:50] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[21:47:50] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[21:47:50] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\markdown\chapters

[21:47:50] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[21:47:50] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\markdown\chapters

[21:47:50] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3938 bytes)

[21:47:50] [INFO]   ⏱️ Summary phase starting | [241.6s]

[21:47:52] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[21:47:52] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[21:47:52] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[21:47:52] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[21:47:52] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[21:47:52] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[21:47:52] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[21:47:52] [INFO]   🌡️ Pre-flight: idle GPU temp = 60°C

[21:47:52] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 60°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[21:47:52] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[21:47:52] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[21:47:52] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[21:47:52] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[21:47:52] [DEBUG]   🎛️ Model profile: Default

[21:47:52] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[21:47:52] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[21:47:52] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[21:47:52] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[21:47:52] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[21:47:52] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[21:47:52] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[21:47:52] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[21:47:52] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[21:47:52] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[21:47:52] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[21:47:52] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[21:47:52] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[21:47:52] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[21:47:52] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[21:47:52] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[21:47:52] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[21:47:52] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[21:47:52] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[21:47:52] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[21:47:52] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[21:47:52] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.14

[21:47:52] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[21:47:52] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[21:47:52] [INFO]     📊 V17.2: Prepended deterministic analysis (3823 chars) — citation recall 78%→100%

[21:47:52] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[21:47:52] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[21:47:52] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[21:47:52] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[21:47:52] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[21:47:52] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:47:52] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[21:49:02] [INFO]     ✅ V0.3 Call 1/3: master summary = 726 words, 5734 chars

[21:49:02] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[21:49:02] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:49:02] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[21:49:32] [INFO]     ✅ V0.3 Call 2/3: 28 bullets derived from master summary

[21:49:32] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[21:49:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:49:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[21:49:48] [INFO]     ✅ V0.3 Call 3/3: exec summary = 230 words

[21:49:49] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[21:49:49] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[21:53:38] [INFO]     📖 V0.5.7 source glossary (separate call) → C:\Users\Ali Assadi\Desktop\5.14\summaries\.glossaries\6 - PARANOID PERSONALITY DISORDER.glossary.md

[21:53:38] [DEBUG]     📝 Parsed: exec=1894 chars, bullets=28, thorough=5734 chars

[21:54:40] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[21:54:41] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[21:54:41] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 27)

[21:54:41] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1}

[21:54:41] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (27 bullets, 230 exec words, 726 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[21:54:42] [DEBUG]     🔍 Fact-check: all 27 bullets verified ✓

[21:54:42] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[21:54:42] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:54:42] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[21:55:34] [INFO]     ✅ Additive sections via followup call: key_distinctions=1743 chars, theoretical_tensions=1514 chars

[21:55:34] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (27 bullets, 230 exec words, 726 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[21:55:34] [WARNING]     ⚠️ thorough_summary too short (726 words < 800 threshold) — requesting dedicated expansion…

[21:55:34] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[21:55:34] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[21:56:47] [INFO]     📖 Attempt 1/3: dedicated thorough = 755 words

[21:56:47] [WARNING]   ⏱️⚠️ Deadline exceeded (535s > 480s) — skipping optional phase: dedicated thorough (attempt 2)

[21:56:47] [DEBUG]     ⏱️ Skipping thorough attempt 2 (chapter deadline exceeded)

[21:56:47] [WARNING]   ⏱️⚠️ Deadline exceeded (535s > 480s) — skipping optional phase: dedicated thorough (attempt 3)

[21:56:47] [DEBUG]     ⏱️ Skipping thorough attempt 3 (chapter deadline exceeded)

[21:56:47] [WARNING]   ⏱️⚠️ Deadline exceeded (535s > 480s) — skipping optional phase: dedicated thorough (attempt 4 length-directive)

[21:56:47] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=755) — keeping best-effort result

[21:56:47] [INFO]     ✅ thorough_summary expanded via dedicated call: 726 → 755 words

[21:56:47] [WARNING]   ⏱️⚠️ Deadline exceeded (535s > 480s) — skipping optional phase: dedicated bullet expansion

[21:56:47] [INFO]     ✅ Final coverage 100%

[21:56:47] [DEBUG]     📏 F1: exec=230w, thorough=755w (source=7405w; targets exec<=250w, thorough<=3332w)

[21:58:21] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[21:58:21] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 18.8 (diff: -2.6)

[21:58:21] [INFO]     ℹ️ F3: Summary is 2.5 grade levels denser than source — expected for a compressed academic summary.

[21:58:23] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[21:58:23] [DEBUG]     🔄 J2: 13 cross-section redundancy(ies) found (exec↔bullets: 5, bullets↔thorough: 8)

[21:58:23] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 7 markers)

[21:58:23] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[21:58:23] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[21:58:23] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[21:58:58] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 3248 per-pair calls)

[21:58:58] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[21:59:00] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (27/27 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[21:59:00] [INFO]   ℹ️ Summary has substantial content (exec=1894 chars, thorough=5937 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[21:59:00] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[21:59:00] [WARNING]   ⏱️⚠️ Deadline exceeded (668s > 480s) — skipping optional phase: scholar reflection

[21:59:00] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[21:59:00] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[21:59:00] [WARNING]   ⏱️⚠️ Deadline exceeded (668s > 480s) — skipping optional phase: semantic dedup

[21:59:00] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[21:59:00] [DEBUG]     🧹 V16.0.2 Bullet normalization: 27 bullets normalized

[21:59:00] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[21:59:00] [WARNING]   ⏱️⚠️ Deadline exceeded (668s > 480s) — skipping optional phase: bullet consolidation

[21:59:00] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[21:59:00] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.14

[21:59:00] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[21:59:00] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[21:59:00] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Freud', 'Klein', 'Erikson']/74 authors in bullets (7%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']

[21:59:00] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Shepherd', 'Klein', 'Winnicott', 'Erikson', 'Bursten']/74 authors in thorough (28%) — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[21:59:00] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Shapiro', 'Bleuler', 'Stanton']…

[21:59:00] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:59:00] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:59:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kernberg' (grounded in glossary context, not verbatim quote)

[21:59:18] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[21:59:18] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (17.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[21:59:18] [DEBUG]     📊 V18.14.1: After round 1, 58 still missing from bullets: ['Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[21:59:18] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Kretschmer', 'Hamilton', 'Rycroft', 'Cameron', 'Frances']…

[21:59:18] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:59:18] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:59:35] [INFO]     ✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)

[21:59:35] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets

[21:59:35] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (16.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[21:59:35] [DEBUG]     📊 V18.14.1: After round 2, 47 still missing from bullets: ['Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson']…

[21:59:35] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Jaspers', 'Schneider', 'Salzman', 'Millon', 'Jacobson']…

[21:59:35] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:59:35] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[21:59:47] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[21:59:47] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (12.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[21:59:47] [DEBUG]     📊 V18.14.1: After round 3, 37 still missing from bullets: ['Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Tobak']…

[21:59:47] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Leonhard', 'Shepherd', 'Polatin', 'Slater and Roth', 'Tobak']…

[21:59:47] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[21:59:47] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:00:00] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler’s (1975) theory of separation-individuation is referenced in th…

[22:00:00] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 7/8 bullets

[22:00:00] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (12.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[22:00:00] [DEBUG]     📊 V18.14.1: After round 4, 28 still missing from bullets: ['Mahler', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[22:00:00] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Mahler', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[22:00:00] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:00:00] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:00:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s 1972 work is cited for its description of narcissistic rage wi…

[22:00:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Jack’s work is cited alongside DSM criteria to support the view that r…

[22:00:14] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 6/8 bullets

[22:00:14] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (14.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[22:00:14] [DEBUG]     📊 V18.14.1: After round 5, 22 still missing from bullets: ['Kohut', 'Jack', 'Ndtei', 'Bursten', 'Green']…

[22:00:14] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 37 bullets across 5 round(s)

[22:00:14] [INFO]     ✨ V0.5.6 final-check: firing TARGETED round 4 for 20 glossary-grounded author(s) still missing after round 5: Bursten, Conlon, Frances et al., Green, Jack, Kohut, Lowenthal, Mackinnon and Mi

[22:00:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:00:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Bursten' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Conlon' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Frances et al.' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Green' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Jack' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kohut' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Lowenthal' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Mackinnon and Michels' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Morey' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Munro' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Ndtei' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Ovessey' (grounded in glossary context, not verbatim quote)

[22:00:33] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)

[22:00:33] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded. Stages: {'thinking_filter.truncated': 1, 'thinking_filter.citation_only': 1}

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Reid' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rettersol' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Socarides' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Stone' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Tagore' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Walters' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Wurmser' (grounded in glossary context, not verbatim quote)

[22:00:33] [INFO]     ✨ V0.5.6 final-check: round 4 added 19/20 glossary-grounded bullet(s)

[22:00:33] [WARNING]     ✨ V0.5.6 final-check: 62/63 authors (98%) — 1 still missing: ['Pao']. Glossary: (none)

[22:00:33] [WARNING]     ⚠️ V18.14.1: 1 theorists still missing from bullets after gap-fill: ['Pao'] — 1 never covered (round cap/deadline): ['Pao']

[22:00:33] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[22:00:33] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[22:00:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (3 item(s) were uncovered; all 4 now carried verbatim)

[22:00:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[22:00:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[22:00:33] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[22:00:34] [DEBUG]     🧹 Semantic dedup: removing bullet 20 (sim=0.87 with bullet 1)

[22:00:34] [DEBUG]     🧹 Semantic dedup: removing bullet 42 (sim=0.97 with bullet 41)

[22:00:34] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 88 → 86 bullets (removed 2 gap-fill/conclusion duplicates; 1.1s, non-skippable per V18.20.3.4)

[22:00:34] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.14

[22:00:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:00:34] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:00:37] [INFO]     🛡️ V18.2.13 Post-checks: 9 fixed, 10 flagged (of 84 bullets + exec + thorough)

[22:00:37] [DEBUG]       [consistency/flag] bullet[12]: false 'missing' claim: 'omitted' followed by 'from DSM-III-R include grandiosity' — but 2/2 of the concept's words DO appear in the source (summary may falsely claim it's missing)  |  Key features omitted from DSM-III-R include…

[22:00:37] [DEBUG]       [parenthetical_promotion/fix] bullet[27]: dropped misattributed bullet: 'Kernberg' is credited with a claim the source attributes to 'Kernberg’s' ('Kernberg' appears there only as a citation/list item). Verified via the generation-time active-subject veto.  |  Kernberg: Associated paranoid personality with a borderline 

[22:00:37] [DEBUG]       [garble_llm_repair/flag] bullet[44]: semantic LLM repair returned empty/short text — original kept.  |  Millon (1981) divided the features of paranoid personality i

[22:00:37] [DEBUG]       [dropped_letter/flag] bullet[44]: likely garbled token: 'paranoias' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …t the confidence and pride of paranoias cloak a hollow shell…

[22:00:37] [DEBUG]       [sentence_fusion/flag] bullet[53]: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  endacity with moralistic self-righteousness in the paranoid characte

[22:00:37] [DEBUG]       [garble_llm_repair/flag] bullet[58]: semantic LLM repair returned empty/short text — original kept.  |  Bach noted the “mirror complementarity of the self” and obse

[22:00:37] [DEBUG]       [dropped_letter/flag] bullet[58]: likely garbled token: 'paranoics' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'paranoids' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …acutely vigilant attention of paranoics.

[22:00:37] [DEBUG]       [grammar/flag] bullet[65]: no main verb detected in first 40 words of 'Green (1986) wrote an essay on moral nar…' — the bullet may be grammatically broken (generation/formatting failure)  |  Green (1986) wrote an essay on…

[22:00:37] [DEBUG]       [attribution/flag] bullet[66]: attribution mismatch: summary's claim about 'Jack (1984)' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Jack (1984, 1984 et al.) contr…

[22:00:37] [DEBUG]       [space/fix] bullet[70]: split 'review' -> 're view' (source-validated)  |  …orey (1988) conducted a major review of recent personality d…

[22:00:37] [DEBUG]       [parenthetical_promotion/fix] bullet[76]: dropped misattributed bullet: 'Socarides' is credited with a claim the source attributes to 'Socarides’s' ('Socarides' appears there only as a citation/list item). Verified via the generation-time active-subject veto.  |  Socarides (1966) viewed the affect of vengeance.

[22:00:37] [DEBUG]       [sentence_fusion/flag] bullet[82]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[22:00:37] [DEBUG]       [truncated/flag] bullet[84]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[22:00:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   which sets the thematic tone of seeking forgiveness from th

[22:00:37] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to Kraepelin’s (1905, 1921a) description of the 

[22:00:37] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  continued to exist independently of each other

[22:00:37] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   synthesis: The author introduces a conceptualization of cli

[22:00:37] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[22:00:37] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 2 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Descriptive psychiatry vs. psychoanalytic literature: The 

[22:00:37] [INFO]     ℹ️ V0.4.23: 84 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[22:00:37] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 21/74 authors in thorough — MISSING from thorough: ['Akhtar', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[22:00:37] [WARNING]   ⏱️⚠️ Deadline exceeded (765s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[22:00:37] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 53 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[22:00:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:00:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:01:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Akhtar (1984) is cited regarding his own descriptions of identity diff…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, the chapter acknowledges that while the composite profil…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In addressing the broader context of these diagnostic challenges, Volk…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:10] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Furthermore, the text references the work of Akhtar and Byrne (1983) o…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:22] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:01:22] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:01:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Mahler’s theory of separation-individuation is particularly significan…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This developmental lens complements the structural analysis provided b…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Furthermore, the chapter notes that Anthony’s delineation of the paran…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In terms of phenomenological detail and structural organization, Bak’s…" — its name(s) never co-occur with the claim's key phrases in the source

[22:01:58] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, the chapter highlights the indirect but significant bearing o…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:08] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:02:08] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Bergman emphasized the role of chronic hypomanic defenses in maintaini…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Jack described the paranoid individual’s cognitive rigidity, including…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Ndtei focused on the interpersonal dimension, noting the patient’s pro…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Slater and Roth specifically identified the "contradictory pride and l…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the realm of contemporary psychoanalytic synthesis, Green explored …" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Pao provided a focused analysis of morbid jealousy, detailing how such…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Siever and Kendler critically evaluated the DSM-III diagnostic criteri…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Frances and Widiger further addressed the nosological challenges by pr…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:47] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, Mackinnon and Michels integrated structural and developmental…" — its name(s) never co-occur with the claim's key phrases in the source

[22:02:54] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 21/74 → 23/74 (3 chunked call(s), ≤12 names each; 17 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[22:02:54] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 68/74 in final bullets (missing: ['Kernberg', 'Pao', 'Socarides', 'Siever and Kendler', 'Varghesi']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[22:02:54] [INFO]     📋 Quarantine: 2 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[22:02:54] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 902s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 902s of the budget.

[22:02:54] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[22:02:54] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":84,"exec_chars":1894,"chapter_done":true}

[22:02:54] [DEBUG]   📊 Progress: 1/1 done | 84 bullets | 1,894 chars exec summary

[22:02:54] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\checkpoints

[22:02:54] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 3 source author(s) NOT found in the summary (Frances et al., Kendler et al., Pao). Glossary: (none). Cross-ref: confirmed=59, llm_only=4, regex_only=15.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1980s' (decade:1980) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923a' (ce:1923) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923' (ce:1923) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1969' (ce:1969) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1966' (ce:1966) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1979' (ce:1979) NOT found in summary — possible omission.

[22:02:54] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 3 source author(s) NOT found in the summary (Frances et al., Kendler et al., Pao

[22:02:54] [DEBUG]     ✨ V0.5.1 verification: [verification_auto_apply_en_dash/fix] en-dash normalization: replaced 1 U+2013 en-dash(es) in year-range(s) with U+002D hyphen (the canonical ASCII form; matc

[22:02:54] [INFO] 📄 Building DOCX report…

[22:02:54] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:02:55] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[22:02:55] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.14_20260927-214348-6774fcc0_summary.md + DOCX

[22:02:55] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[22:02:55] [INFO]   🧮 Embedding cache: 63 hits / 29 misses (68% hit-rate), 5000 entries

[22:02:55] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.14_20260927-214348-6774fcc0_summary.md

[22:02:55] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries

[22:02:55] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:02:55] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.14_20260927-214348-6774fcc0.summary.md

[22:02:55] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[22:02:55] [INFO]   ⏱️ DOCX phase starting | [1146.4s]

[22:02:55] [INFO] 📄 Building DOCX report…

[22:02:55] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:02:55] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[22:02:57] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[22:02:59] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[22:05:03] [INFO]   🎯 K1+Classification: 84 bullets — 17 core, 50 supporting, 17 additional

[22:05:03] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:05:04] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:05:04] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:05:04] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:05:04] [INFO]   📊 Citation graph: no citations found in the text.

[22:05:04] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[22:05:04] [SUCCESS] ✅ Conversion complete.

[22:05:19] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\logs\quality_report.json

[22:05:19] [INFO] 

[22:05:19] [INFO] ━━━ Thermal Safety Report ━━━

[22:05:19] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[22:05:19] [INFO]   Session duration: 17.4 min

[22:05:19] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[22:05:19] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[22:05:19] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:05:19] [INFO] 

[22:05:19] [INFO] ━━━ Elixir v0.5.14 Conversion Diagnostic Summary ━━━

[22:05:19] [INFO]   Book: Broken Structures Salman Akhtar

[22:05:19] [INFO]   Total pages: 397

[22:05:19] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[22:05:19] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[22:05:19] [INFO]   Summaries generated: 1

[22:05:19] [INFO]     Success: 1, Failed: 0, Total bullets: 84

[22:05:19] [INFO]     Coverage: 100%

[22:05:19] [INFO]     Recall floor (deterministic, final set): theorists 68/74 (92%), conclusion items 3/3 (100%)

[22:05:19] [INFO]   Warnings: 0

[22:05:19] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar

[22:05:19] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.14_20260927-214348-6774fcc0.conversion.log.md

[22:05:19] [INFO]   Diagnostic JSONL: None

[22:05:19] [INFO]   Summary files (3):

[22:05:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.14_20260927-214348-6774fcc0_summary.md — generated-by v0.5.14 | run_id=20260927-214348-6774fcc0 | started=2026-09-27T21:47:52 | bullets=84

[22:05:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.14 | run_id=20260927-214348-6774fcc0 | started=2026-09-27T21:47:52 | bullets=84

[22:05:19] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.14_20260927-214348-6774fcc0.summary.md — generated-by v0.5.14 | run_id=20260927-214348-6774fcc0 | started=2026-09-27T21:47:52 | bullets=84

[22:05:19] [INFO]   Models loaded at exit: (none — all unloaded)

[22:05:19] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:05:19] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[22:05:19] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[22:05:19] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:05:19] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[22:05:19] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[22:05:19] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[22:05:19] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\images

[22:05:19] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[22:05:25] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\images

[22:05:31] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[22:05:31] [INFO]   [pipeline] after de-dup: 2 regions

[22:05:32] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.14\Broken Structures Salman Akhtar\regions

[22:05:32] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[22:05:32] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 84 keypoints)


---
Finished at: 2026-09-27T22:05:32.135978
