# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-27T22:27:21.941529

<!-- generated-by: Elixir v0.5.15 | run_id=20260927-222721-7e69579b -->

---

[22:27:21] [SUCCESS] 🚀 Starting conversion…

[22:27:21] [DEBUG]   🔍 importing 'pypdf'…

[22:27:21] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[22:27:21] [DEBUG]   🔍 importing 'pdf2image'…

[22:27:21] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[22:27:21] [DEBUG]   🔍 importing 'tiktoken'…

[22:27:21] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[22:27:21] [DEBUG]   🔍 importing 'markitdown'…

[22:27:24] [DEBUG]   ✅ 'markitdown' ok (2.1s)

[22:27:24] [DEBUG]   🔍 importing 'rapidfuzz'…

[22:27:24] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[22:27:24] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[22:27:24] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[22:27:24] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[22:27:24] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[22:27:24] [DEBUG]   ✅ 'torch' installed

[22:27:24] [DEBUG]   ✅ 'transformers' installed

[22:27:24] [DEBUG]   ✅ 'langextract' installed

[22:27:24] [DEBUG]   ✅ Pre-flight dependency check passed

[22:27:24] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[22:27:24] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[22:27:24] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar.pdf

[22:27:24] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar

[22:27:24] [INFO]   Source type: normal_book

[22:27:24] [INFO]   App version: 0.5.15

[22:27:24] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[22:27:24] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[22:27:24] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[22:27:24] [INFO]   Ollama reachable (localhost:11434): True

[22:27:24] [INFO]   Provider: llamacpp

[22:27:24] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[22:27:24] [INFO]   [Phase 1 (Extraction)]

[22:27:24] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:27:24] [INFO]   [Phase 2 (Summarization)]

[22:27:24] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[22:27:24] [INFO]   ────────────────────────────────────────

[22:27:24] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[22:27:24] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[22:27:24] [INFO] ━━━━━━━━━━━━━━━━━━━━

[22:27:24] [INFO]   LLM OCR: True, Force OCR all: False

[22:27:24] [INFO]   Auto-detect scanned: True

[22:27:24] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:27:24] [INFO]   OCR retries: 2, Image max size: 1200

[22:27:24] [INFO]   Page range: all

[22:27:24] [INFO]   Selected chapters: 1 chapter(s)

[22:27:24] [DEBUG]     → 6 - PARANOID PERSONALITY DISORDER

[22:27:24] [INFO]   Segmentation: auto, Token limit: 2000

[22:27:24] [INFO]   Semantic: True, Page group: 10

[22:27:24] [INFO]   Generate summaries: True

[22:27:24] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:27:24] [INFO]   Fast model: , Heavy model: (disabled)

[22:27:24] [INFO]   Workers (requested): 1, Temperature: 0.7

[22:27:24] [INFO]   Self-consistency: False, Coverage threshold: 95%

[22:27:24] [INFO]   📈 Over-delivery: ENABLED (floor 95% → target 100%)

[22:27:24] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[22:27:24] [INFO]   Academic rigor: False

[22:27:24] [INFO]   Max context tokens: 128000

[22:27:24] [INFO]   Max output tokens: 32768

[22:27:24] [INFO]   Keep-alive: 30m

[22:27:24] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[22:27:24] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[22:27:24] [INFO]   Translation: disabled

[22:27:24] [INFO]   Clean markdown: True, Token saver: True

[22:27:24] [INFO]   Content filter: True

[22:27:24] [INFO]   Extract tables: False, Math: False, Figures: False

[22:27:24] [INFO]   Visual-region crops: True

[22:27:24] [INFO]   Layout analysis: False

[22:27:24] [INFO]   DOCX author: Elixir, TOC: True

[22:27:24] [INFO]   Output paths (V7.5 subfolders):

[22:27:24] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[22:27:24] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:27:24] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[22:27:24] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\packets

[22:27:24] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\podcast

[22:27:24] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\logs\quality_report.json

[22:27:24] [INFO]   Resume mode: enabled — will skip done chapters

[22:27:24] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[22:27:24] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:27:24] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[22:27:24] [INFO]   ℹ️ V0.5.14: VRAM budget estimate (peak 12.9 GB) > total (12.0 GB), BUT nvidia-smi reports 0.13 GB free (GPU-wide, across all processes). The param-count estimate may be wrong for this model. Proceeding — llama.cpp will error at load time if the model truly doesn't fit.

[22:27:24] [DEBUG]   💾 Disk space: 22.2 GB free

[22:27:24] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\.checkpoint.json

[22:28:38] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[22:28:38] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:28:38] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[22:28:38] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[22:28:38] [INFO] [TOC] Using PDF outlines: 22 entries.

[22:28:38] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[22:28:38] [DEBUG]   [TOC] Entries passed to segmenter: 22

[22:28:38] [DEBUG]   [TOC] - p.7: Table of Contents

[22:28:38] [DEBUG]   [TOC] - p.9: FOREWORD

[22:28:38] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[22:28:38] [DEBUG]   [TOC] … and 19 more

[22:28:38] [INFO]   🎯 User selected 1 chapter(s):

[22:28:38] [INFO]     → '6 - PARANOID PERSONALITY DISORDER' (TOC page 137)

[22:28:38] [INFO]   📸 front_cover → front_cover.jpg

[22:28:39] [INFO]   📸 back_cover → back_cover.jpg

[22:28:39] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:28:39] [INFO]   📸 Screenshotting 24 selected chapter page(s)...

[22:28:39] [DEBUG]   📸 p.137 → chapter_page_137.jpg

[22:28:39] [DEBUG]   📸 p.138 → chapter_page_138.jpg

[22:28:39] [DEBUG]   📸 p.139 → chapter_page_139.jpg

[22:28:39] [DEBUG]   📸 p.140 → chapter_page_140.jpg

[22:28:40] [DEBUG]   📸 p.141 → chapter_page_141.jpg

[22:28:40] [DEBUG]   📸 p.142 → chapter_page_142.jpg

[22:28:40] [DEBUG]   📸 p.143 → chapter_page_143.jpg

[22:28:40] [DEBUG]   📸 p.144 → chapter_page_144.jpg

[22:28:40] [DEBUG]   📸 p.145 → chapter_page_145.jpg

[22:28:41] [DEBUG]   📸 p.146 → chapter_page_146.jpg

[22:28:41] [DEBUG]   📸 p.147 → chapter_page_147.jpg

[22:28:41] [DEBUG]   📸 p.148 → chapter_page_148.jpg

[22:28:41] [DEBUG]   📸 p.149 → chapter_page_149.jpg

[22:28:41] [DEBUG]   📸 p.150 → chapter_page_150.jpg

[22:28:42] [DEBUG]   📸 p.151 → chapter_page_151.jpg

[22:28:42] [DEBUG]   📸 p.152 → chapter_page_152.jpg

[22:28:42] [DEBUG]   📸 p.153 → chapter_page_153.jpg

[22:28:42] [DEBUG]   📸 p.154 → chapter_page_154.jpg

[22:28:43] [DEBUG]   📸 p.155 → chapter_page_155.jpg

[22:28:43] [DEBUG]   📸 p.156 → chapter_page_156.jpg

[22:28:43] [DEBUG]   📸 p.157 → chapter_page_157.jpg

[22:28:43] [DEBUG]   📸 p.158 → chapter_page_158.jpg

[22:28:43] [DEBUG]   📸 p.159 → chapter_page_159.jpg

[22:28:44] [DEBUG]   📸 p.160 → chapter_page_160.jpg

[22:28:44] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:28:44] [INFO]   📄 Derived 24 pages from TOC for 1 selected chapter(s) (skipping 373 unselected pages)

[22:28:44] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[22:28:44] [INFO]   📄 OCR pages filtered: 31 → 3 (only scanning pages within selected chapters)

[22:28:44] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[22:28:44] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[22:28:44] [INFO]   ✅ markitdown ready for digital-page extraction

[22:28:44] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[22:28:44] [INFO]   🔍 V18.2.16 Pre-scan: checking 3 page(s) for OCR necessity (deterministic, no model loaded)…

[22:28:44] [INFO]   📋 V18.2.16 Pre-scan result: 3 page(s) need OCR, 0 have digital text (took 0.3s)

[22:28:44] [INFO]      Pages needing OCR: [152, 153, 154]

[22:28:44] [INFO]   📋 V18.2.16 Pre-scan refined OCR target: 3 → 3 page(s) (0 had digital text, skipped OCR model for those).

[22:28:44] [DEBUG]   ℹ️ Provider is llama.cpp — page OCR routes via the llama-server vision provider (no Ollama model load).

[22:28:44] [INFO]   📄 Processing 24/397 pages (chapter selection active — skipping 373 unselected pages)

[22:28:47] [INFO]   📄 140/397 pages processed (35%)

[22:28:55] [INFO]   🔍 OCR  page 152/397 (scanned)…

[22:28:58] [INFO]   📸 V0.4.1: Main model 'Ternary-Bonsai-2-27B-Instruct-Vision' has vision — using it for OCR

[22:30:35] [INFO]   ✅ V0.4.1 vision OCR p.152: 1025 chars

[22:30:35] [INFO]   🔍 OCR  page 153/397 (scanned)…

[22:31:58] [INFO]   ✅ V0.4.1 vision OCR p.153: 87 chars

[22:31:58] [INFO]   🔍 OCR  page 154/397 (scanned)…

[22:33:27] [INFO]   ✅ V0.4.1 vision OCR p.154: 931 chars

[22:33:31] [INFO]   📄 160/397 pages processed (40%)

[22:33:31] [SUCCESS] ✅ PDF processing done: 24/397 pages extracted

[22:33:31] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[22:33:31] [DEBUG]   🧹 Tab cleanup: replaced 6345 tab character(s) with spaces

[22:33:31] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[22:33:31] [INFO]   🔍 Content auto-detection: Non-Fiction Book (100% confidence) — default (no strong signals for other types)

[22:33:31] [DEBUG]   ℹ️ Detection confidence too low (100%) — keeping normal_book preset

[22:33:31] [INFO] 📝 Raw markdown: 53,157 chars | [369.5s]

[22:33:31] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[22:33:31] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[22:33:31] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[22:33:31] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[22:33:31] [INFO] [Segmenter] Attempting chapter-level segmentation…

[22:33:31] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 137).

[22:33:31] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 222 has no marker for '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[22:33:31] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[22:33:31] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[22:33:31] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[22:33:31] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[22:33:31] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[22:33:31] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[22:33:31] [DEBUG]      Selected: ['6 - PARANOID PERSONALITY DISORDER']

[22:33:31] [INFO]   📑 Filtered segments: kept 1 of 17

[22:33:31] [INFO] 📚 1 segment(s) detected | [369.6s]

[22:33:31] [DEBUG]   ✅ Seg 1/1: '6 - PARANOID PERSONALITY DISORDER' | 11,198 tokens | p.137–160

[22:33:31] [INFO] 🌐 Detected language: en

[22:33:31] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[22:33:31] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[22:33:31] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\markdown\chapters

[22:33:31] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[22:33:31] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\markdown\chapters

[22:33:31] [DEBUG]    [V17.5] Analysis file: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3938 bytes)

[22:33:31] [INFO]   ⏱️ Summary phase starting | [370.0s]

[22:33:33] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[22:33:33] [DEBUG]   ⏭️ Skipping page 153 in summarisation: Fewer than 80 alphanumeric characters

[22:33:33] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[22:33:34] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[22:33:34] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[22:33:34] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[22:33:34] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[22:33:34] [INFO]   🌡️ Pre-flight: idle GPU temp = 58°C

[22:33:34] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 58°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[22:33:34] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[22:33:34] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[22:33:34] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[22:33:34] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[22:33:34] [DEBUG]   🎛️ Model profile: Default

[22:33:34] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[22:33:34] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[22:33:34] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[22:33:34] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[22:33:34] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[22:33:34] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[22:33:34] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 1 concepts — ['Rabindranath Tagore Paranoid']

[22:33:34] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Freud', 'Kernberg', 'Schneider', 'Hamilton', 'Blum']

[22:33:34] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Descriptive Studies', 'Psychoanalytic Views', 'An Attempt At Synthesis', 'Comment']

[22:33:34] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 0 concepts — []

[22:33:34] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[22:33:34] [DEBUG]     🎯 V15.2.0: merged 20 concepts before source-grounding

[22:33:34] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 20 concepts grounded ✓

[22:33:34] [INFO]     🎯 V15.2.0: FINAL 20 concepts (cap 50)

[22:33:34] [DEBUG]   🎯 '6 - PARANOID PERSONALITY DISORDER…': 20 concepts extracted (V15.2.0 enhanced)

[22:33:34] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[22:33:34] [INFO]   📖 Chapter 1/1: '6 - PARANOID PERSONALITY DISORDER' (53017 chars)

[22:33:34] [INFO]   🎯 User selected: ['6 - PARANOID PERSONALITY DISORDER']

[22:33:34] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[22:33:34] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[22:33:34] [INFO] 📚 Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER…

[22:33:34] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.15

[22:33:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:33:34] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:33:34] [INFO]     📊 V17.2: Prepended deterministic analysis (3823 chars) — citation recall 78%→100%

[22:33:34] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=11,171 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 11,171 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[22:33:34] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[22:33:34] [DEBUG]     🎯 Injecting 20 concepts + 0 callouts into prompt

[22:33:34] [INFO]     📦 V0.4: master-summary architecture (default) — input 11171 tok, output cap 32768

[22:33:34] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[22:33:34] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:33:34] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[22:34:49] [INFO]     ✅ V0.3 Call 1/3: master summary = 756 words, 5781 chars

[22:34:49] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[22:34:49] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:34:49] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[22:35:38] [INFO]     ✅ V0.3 Call 2/3: 39 bullets derived from master summary

[22:35:38] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[22:35:38] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:35:38] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[22:35:56] [INFO]     ✅ V0.3 Call 3/3: exec summary = 237 words

[22:35:56] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[22:35:56] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[22:39:17] [INFO]     📖 V0.5.7 source glossary (separate call) → C:\Users\Ali Assadi\Desktop\5.15\summaries\.glossaries\6 - PARANOID PERSONALITY DISORDER.glossary.md

[22:39:17] [DEBUG]     📝 Parsed: exec=1896 chars, bullets=39, thorough=5781 chars

[22:39:50] [INFO]     📊 Primary coverage: 100% | keywords: ['paranoid', 'disorder', 'self']

[22:39:52] [DEBUG]     🔍 Coverage detail: 6/7 keywords found | missing: ['others']

[22:39:52] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (39 bullets, 237 exec words, 756 thorough words) → .checkpoints/primary_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[22:39:53] [DEBUG]     🔍 Fact-check: all 39 bullets verified ✓

[22:39:53] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[22:39:53] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:39:53] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[22:40:42] [INFO]     ✅ Additive sections via followup call: key_distinctions=1618 chars, theoretical_tensions=1434 chars

[22:40:42] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (39 bullets, 237 exec words, 756 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_6_-_PARANOID_PERSONALITY_DISORDER_summary.md

[22:40:42] [WARNING]     ⚠️ thorough_summary too short (756 words < 800 threshold) — requesting dedicated expansion…

[22:40:42] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[22:40:42] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[22:41:56] [INFO]     📖 Attempt 1/3: dedicated thorough = 760 words

[22:41:56] [WARNING]   ⏱️⚠️ Deadline exceeded (502s > 480s) — skipping optional phase: dedicated thorough (attempt 2)

[22:41:56] [DEBUG]     ⏱️ Skipping thorough attempt 2 (chapter deadline exceeded)

[22:41:56] [WARNING]   ⏱️⚠️ Deadline exceeded (502s > 480s) — skipping optional phase: dedicated thorough (attempt 3)

[22:41:56] [DEBUG]     ⏱️ Skipping thorough attempt 3 (chapter deadline exceeded)

[22:41:56] [WARNING]   ⏱️⚠️ Deadline exceeded (502s > 480s) — skipping optional phase: dedicated thorough (attempt 4 length-directive)

[22:41:56] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=760) — keeping best-effort result

[22:41:56] [INFO]     ✅ thorough_summary expanded via dedicated call: 756 → 760 words

[22:41:56] [WARNING]   ⏱️⚠️ Deadline exceeded (502s > 480s) — skipping optional phase: dedicated bullet expansion

[22:41:56] [INFO]     ✅ Final coverage 100%

[22:41:56] [DEBUG]     📏 F1: exec=237w, thorough=760w (source=7405w; targets exec<=250w, thorough<=3332w)

[22:44:09] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[22:44:09] [DEBUG]     📖 F3: Reading level — source: 16.3, summary: 20.6 (diff: -4.4)

[22:44:09] [INFO]     ℹ️ F3: Summary is 4.3 grade levels denser than source — expected for a compressed academic summary.

[22:44:11] [DEBUG]     📊 I2: Chapter difficulty 0.57/1.0 (grade 16.3, strategy: multi_sample)

[22:44:11] [DEBUG]     🔄 J2: 27 cross-section redundancy(ies) found (exec↔bullets: 4, bullets↔thorough: 23)

[22:44:11] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 5 markers)

[22:44:11] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[22:44:11] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[22:44:11] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[22:44:27] [DEBUG]     📊 Batch coverage: 55/56 claims (2 batch encode calls via EmbeddingCache, was 4592 per-pair calls)

[22:44:27] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[22:44:30] [INFO]     📊 Judge: coverage=98% (55/56 claims), grounding=100% (39/39 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[22:44:30] [INFO]   ℹ️ Summary has substantial content (exec=1896 chars, thorough=5803 chars) — Judge coverage check at 98% is likely a false positive for this source length. Auto-passing to preserve content.

[22:44:30] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[22:44:30] [WARNING]   ⏱️⚠️ Deadline exceeded (656s > 480s) — skipping optional phase: scholar reflection

[22:44:30] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[22:44:30] [INFO]     🛡️ Anti-false-precision: rewrote 'Klein (1946) described the "paranoid-schizoid position" as a…' → 'Klein and Winnicott both described the "paranoid-schizoid po…' (source groups Klein + Winnicott)

[22:44:30] [DEBUG]     🛡️ Anti-false-precision: SKIPPED rewrite of 'Klein and others emphasize internal aggressive dispositions …' — claim1 is a fragment starting with 'and' (merge would produce broken grammar)

[22:44:30] [INFO]     🛡️ Anti-false-precision: rewrote 1 claim(s) that invented distinctions between authors the source groups together

[22:44:30] [WARNING]   ⏱️⚠️ Deadline exceeded (656s > 480s) — skipping optional phase: semantic dedup

[22:44:30] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[22:44:30] [DEBUG]     🧹 V16.0.2 Bullet normalization: 39 bullets normalized

[22:44:30] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[22:44:30] [WARNING]   ⏱️⚠️ Deadline exceeded (656s > 480s) — skipping optional phase: bullet consolidation

[22:44:30] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[22:44:30] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.15

[22:44:30] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:44:30] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:44:30] [INFO]     📊 V18.14 Bullets-only judge: ['Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Polatin', 'Klein', 'Winnicott', 'Erikson', 'Bursten', 'Wurmser', 'Morey']/74 authors in bullets (30%) — MISSING from bullets: ['Akhtar', 'Kernberg', 'Stanton', 'Thomson', 'Hamilton']

[22:44:30] [WARNING]     📊 V18.14 Thorough-only judge: ['Akhtar', 'Kraepelin', 'Blum', 'Shapiro', 'Bleuler', 'Freud', 'Heimann', 'Meissner', 'Kretschmer', 'Rycroft', 'Cameron', 'Magnan', 'Jaspers', 'Schneider', 'Jacobson', 'Leonhard', 'Polatin', 'Klein', 'Winnicott', 'Bursten', 'Wurmser', 'Morey', 'Gorton and Akhtar']/74 authors in thorough (31%) — MISSING from thorough: ['Kernberg', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[22:44:30] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Kernberg', 'Stanton', 'Thomson', 'Hamilton']…

[22:44:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:44:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:44:46] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kernberg' (grounded in glossary context, not verbatim quote)

[22:44:46] [INFO]     ✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)

[22:44:46] [INFO]     ✨ V0.5.10 gap-fill: accepted bullet for 'Byrne' (grounded in regex extract_citations, not verbatim quote)

[22:44:46] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[22:44:46] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[22:44:46] [DEBUG]     📊 V18.14.1: After round 1, 39 still missing from bullets: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[22:44:46] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Salzman', 'Millon', 'Volkan', 'Winokur', 'Kendler']…

[22:44:46] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:44:46] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:44:57] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets

[22:44:57] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (11.5s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[22:44:57] [DEBUG]     📊 V18.14.1: After round 2, 27 still missing from bullets: ['Mahler', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[22:44:57] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Mahler', 'Anthony', 'Kohut', 'Bach', 'Fenichel']…

[22:44:57] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:44:57] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:45:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Mahler’s (1975) theory of separation-individuation is cited to highlig…

[22:45:14] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) work is referenced for his description of narcissistic …

[22:45:14] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 6/8 bullets

[22:45:14] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (16.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=2, added=6

[22:45:14] [DEBUG]     📊 V18.14.1: After round 3, 20 still missing from bullets: ['Mahler', 'Kohut', 'Ndtei', 'Green', 'Pao']…

[22:45:14] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Mahler', 'Kohut', 'Ndtei', 'Green', 'Pao']…

[22:45:14] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:45:14] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:45:29] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Kohut’s (1972) work on narcissistic rage is cited among a list of cont…

[22:45:29] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is included in the list of re…

[22:45:29] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is referenced as part of the broa…

[22:45:29] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is cited within a l…

[22:45:29] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 4/8 bullets

[22:45:29] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (15.3s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[22:45:29] [INFO]     🔁 V18.20.3.7: 'Kohut' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:45:29] [DEBUG]     📊 V18.14.1: After round 4, 13 still missing from bullets: ['Kohut', 'Green', 'Pao', 'Socarides', 'Stone']…

[22:45:29] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Kohut', 'Green', 'Pao', 'Socarides', 'Stone']… (mention-only: ['Kohut'])

[22:45:29] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:45:29] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:45:42] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Anthony’s (1981) delineation of the paranoid adolescent is cited by Ak…

[22:45:42] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Green’s (1986) essay on moral narcissism is referenced by Akhtar withi…

[22:45:42] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Pao’s (1969) work on morbid jealousy is mentioned by Akhtar alongside …

[22:45:42] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Socarides’s (1966) view on the affect of vengeance is cited by Akhtar …

[22:45:42] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Volkan’s (1986) insights regarding man’s need for enemies and allies a…

[22:45:42] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 3/8 bullets

[22:45:42] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (13.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=5, added=3

[22:45:42] [INFO]     🔁 V18.20.3.7: 'Green' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:45:42] [INFO]     🔁 V18.20.3.7: 'Pao' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:45:42] [INFO]     🔁 V18.20.3.7: 'Socarides' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[22:45:42] [DEBUG]     📊 V18.14.1: After round 5, 10 still missing from bullets: ['Green', 'Pao', 'Socarides', 'Reid', 'Grunberger']…

[22:45:42] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 29 bullets across 5 round(s)

[22:45:42] [INFO]     ✨ V0.5.6 final-check: firing TARGETED round 4 for 12 glossary-grounded author(s) still missing after round 5: Frances et al., Green, Kendler and Grunberger, Morey, Munro, Ovessey, Pao, Reid,

[22:45:42] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:45:42] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Frances et al.' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Green' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kendler and Grunberger' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Morey' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Munro' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Ovessey' (grounded in glossary context, not verbatim quote)

[22:45:54] [DEBUG]     🧹 Filtered 1 thinking + 0 narrative bullets + 0 truncated (kept 0)

[22:45:54] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded. Stages: {'thinking_filter.citation_only': 1}

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Reid' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rettersol' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Socarides' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Tagore' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Walters' (grounded in glossary context, not verbatim quote)

[22:45:54] [INFO]     ✨ V0.5.6 final-check: round 4 added 11/12 glossary-grounded bullet(s)

[22:45:54] [WARNING]     ✨ V0.5.6 final-check: 62/63 authors (98%) — 1 still missing: ['Pao']. Glossary: (none)

[22:45:54] [WARNING]     ⚠️ V18.14.1: 1 theorists still missing from bullets after gap-fill: ['Pao'] — 1 never covered (round cap/deadline): ['Pao']

[22:45:54] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[22:45:54] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Conclusions bullet (all 3 items, verbatim from source) — not scattered

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (4 item(s) were uncovered; all 4 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 9-item runin_arabic list (1 item(s) were uncovered; all 9 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (4 item(s) were uncovered; all 4 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (3 item(s) were uncovered; all 4 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[22:45:55] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 34 (sim=0.85 with bullet 32)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 47 (sim=0.98 with bullet 46)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 61 (sim=0.86 with bullet 60)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 63 (sim=0.89 with bullet 60)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 71 (sim=0.93 with bullet 52)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 82 (sim=0.87 with bullet 18)

[22:45:56] [DEBUG]     🧹 Semantic dedup: removing bullet 87 (sim=0.88 with bullet 26)

[22:45:56] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 87 → 80 bullets (removed 7 gap-fill/conclusion duplicates; 1.0s, non-skippable per V18.20.3.4)

[22:45:56] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.15

[22:45:56] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_6 - PARANOID PERSONALITY DISORDER_analysis.md']

[22:45:56] [DEBUG]     [V17.5] Using analysis: 001_6 - PARANOID PERSONALITY DISORDER_analysis.md (3823 chars), segment: 001_6 - PARANOID PERSONALITY DISORDER.md

[22:45:59] [INFO]     🛡️ V18.2.13 Post-checks: 11 fixed, 20 flagged (of 80 bullets + exec + thorough)

[22:45:59] [DEBUG]       [garble_llm_repair/flag] bullet[9]: semantic LLM repair returned empty/short text — original kept.  |  The descriptive summary defines the condition through six pa

[22:45:59] [DEBUG]       [fragment_merge/flag] bullet[9]: word-fragment merge: 'erotomanial vulnerability' — 'erotomania' is a known word but 'erotomanial' is not. The 'l' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …, superficial asexuality with erotomanial vulnerability, mor…

[22:45:59] [DEBUG]       [dropped_letter/flag] bullet[9]: likely garbled token: 'erotomanial' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'erotomania' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …, superficial asexuality with erotomanial vulnerability, mor…

[22:45:59] [DEBUG]       [attribution/flag] bullet[18]: attribution mismatch: summary's claim about 'Shapiro (1965)' has 50% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Shapiro (1965) detailed the pa…

[22:45:59] [DEBUG]       [attribution/flag] bullet[19]: attribution mismatch: summary's claim about 'Jacobson (1971)' has 46% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Jacobson (1971) and Bursten (1…

[22:45:59] [DEBUG]       [parenthetical_promotion/flag] bullet[39]: V0.5.15: bullet for 'Kernberg' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Kernberg: Associated paranoid personality with a borderline 

[22:45:59] [DEBUG]       [parenthetical_promotion/flag] bullet[44]: V0.5.15: bullet for 'Byrne' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Byrne: Co-authored descriptions with Akhtar regarding the be

[22:45:59] [DEBUG]       [sentence_fusion/flag] bullet[52]: likely sentence-fusion garble: 'self-righteousness' is not in the source or English lexicon but ends with source-word 'righteous' + suffix 'ness' (4 chars, not a legitimate English inflection). The suffix is likely a remnant of a dropped sentence boundary.  |  endacity with moralistic self-righteousness in the paranoid characte

[22:45:59] [DEBUG]       [space/fix] bullet[53]: split 'review' -> 're view' (source-validated)  |  …d adolescent within a broader review of literature on relate…

[22:45:59] [DEBUG]       [space/fix] bullet[61]: split 'review' -> 're view' (source-validated)  |  …integrated into the chapter's review of related theoretical …

[22:45:59] [DEBUG]       [attribution/flag] bullet[64]: attribution mismatch: summary's claim about 'Frances et al (1988)' has 49% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Frances et al. (1988) question…

[22:45:59] [DEBUG]       [grammar/flag] bullet[65]: no main verb detected in first 40 words of 'Green (1986) wrote an essay on moral nar…' — the bullet may be grammatically broken (generation/formatting failure)  |  Green (1986) wrote an essay on…

[22:45:59] [DEBUG]       [space/fix] bullet[66]: split 'review' -> 're view' (source-validated)  |  …orey (1988) conducted a major review of recent personality d…

[22:45:59] [DEBUG]       [parenthetical_promotion/flag] bullet[71]: V0.5.15: bullet for 'Socarides' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Socarides (1966) viewed the affect of vengeance in personali

[22:45:59] [DEBUG]       [sentence_fusion/flag] bullet[75]: likely source-propagated fusion garble: 'selfinflation' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'inflation' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-inflation').  |  ing these to others, and selfinflation through grandiose fantas

[22:45:59] [DEBUG]       [truncated/flag] bullet[77]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **For signs of threat, or taking** — 4 items from the source

[22:45:59] [DEBUG]       [truncated/flag] bullet[79]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **And “exaggeration of difficulties”) less specific** — 3 it

[22:45:59] [DEBUG]       [garble_llm_repair/flag] thorough: semantic LLM repair returned empty/short text — original kept.  |  This chapter, titled "Paranoid Personality Disorder," serves

[22:45:59] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'erotomanial vulnerability' — 'erotomania' is a known word but 'erotomanial' is not. The 'l' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …, superficial asexuality with erotomanial vulnerability, mor…

[22:45:59] [DEBUG]       [fragment_merge/flag] thorough: word-fragment merge: 'pathologya lack' — 'pathology' is a known word but 'pathologya' is not. The 'a' may be a remnant of a dropped sentence boundary (e.g. '. To').  |  …ubstrate for severe character pathologya lack of basic trust…

[22:45:59] [DEBUG]       [dropped_letter/flag] thorough: likely garbled token: 'erotomanial' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'erotomania' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …, superficial asexuality with erotomanial vulnerability, mor…

[22:45:59] [DEBUG]       [dropped_letter/flag] thorough: likely garbled token: 'pathologya' is not in the source and is not a legitimate inflection of any source word, but is edit-distance-1 from 'pathology' (single-char insert/delete/substitute). V18.19.2.5: caught 'emergs'→'emerges' (non-word) class.  |  …ubstrate for severe character pathologya lack of basic trust…

[22:45:59] [DEBUG]       [attribution/flag] thorough: attribution mismatch: summary's claim about 'Wurmser (1981)' has 35% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  … phobic character (defined by Wurmser 1981 as avoidance of s…

[22:45:59] [DEBUG]       [quote_verification/fix] bullet[46]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  the confidence and pride of paranoys cloak but a hollow shel

[22:45:59] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and separation-individuation failures. The psychoanalytic s

[22:45:59] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   approach underscores the centrality of splitting and projec

[22:45:59] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   and the lack of actuarial data, but argues that this dynami

[22:45:59] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   noting that while both lack reality-testing, paranoid perso

[22:45:59] [DEBUG]       [quote_verification/fix] thorough: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   in their suspicions that is more diffuse. The text contrast

[22:45:59] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Paranoid personality disorder vs. paranoid schizophrenia: 

[22:45:59] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=137, end_page=160; ~ marks an ESTIMATED locator, not a verified one)  |  - Freudian formulation (paranoia as defense against latent h

[22:45:59] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 23/74 authors in thorough — MISSING from thorough: ['Kernberg', 'Stanton', 'Thomson', 'Hamilton', 'Frances']

[22:45:59] [WARNING]   ⏱️⚠️ Deadline exceeded (745s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[22:45:59] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 51 of 74 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[22:45:59] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:45:59] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:46:40] [INFO]   ✨ V0.5.15: recovered 3 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[22:47:13] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:47:13] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:47:47] [INFO]   ✨ V0.5.15: recovered 1 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[22:48:17] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[22:48:17] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[22:48:50] [INFO]   ✨ V0.5.15: recovered 3 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[22:49:15] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 23/74 → 54/74 (3 chunked call(s), ≤12 names each; 15 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[22:49:15] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[22:49:15] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 6-item runin_arabic list (1 item(s) were uncovered; all 6 now carried verbatim)

[22:49:15] [INFO]     🩹 V0.4.24: last-chance enumeration repair — 2 consolidated bullet(s) re-added after all ship-time filters (the floor's missing items are guaranteed on the set that actually ships).

[22:49:15] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 70/74 in final bullets (missing: ['Jack', 'Ndtei', 'Pao', 'Grunberger']); conclusion items 3/3; enumerated items (all lists, whole chapter) 43/43. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[22:49:15] [INFO]     📋 Quarantine: 1 bullet drop(s) recorded for this chapter → logs/drops.jsonl (NOT rendered in the delivered files).

[22:49:15] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 942s > 480s (heading='6 - PARANOID PERSONALITY DISORDER') — possible model stall. Summary kept, but this chapter consumed 942s of the budget.

[22:49:15] [INFO] ✅ Chapter 1/1: 6 - PARANOID PERSONALITY DISORDER… complete

[22:49:15] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":82,"exec_chars":1896,"chapter_done":true}

[22:49:15] [DEBUG]   📊 Progress: 1/1 done | 82 bullets | 1,896 chars exec summary

[22:49:15] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\checkpoints

[22:49:16] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 5 source author(s) NOT found in the summary (Frances et al., Jack, Kendler and Grunberger, Kendler et al., Ndtei). Glossary: (none). Cross-ref: confirmed=59, llm_only=4, regex_only=15.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1887-1902' (range:1887-1902) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1919' (ce:1919) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923a' (ce:1923) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1922' (ce:1922) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1923' (ce:1923) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1919' (ce:1919) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1976' (ce:1976) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1958' (ce:1958) NOT found in summary — possible omission.

[22:49:16] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 5 source author(s) NOT found in the summary (Frances et al., Jack, Kendler and G

[22:49:16] [INFO] 📄 Building DOCX report…

[22:49:16] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:49:16] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\checkpoints\chapters\001_6_-_PARANOID_PERSONALITY_DISORDER\001_6_-_PARANOID_PERSONALITY_DISORDER_summary.docx

[22:49:16] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '6 - PARANOID PERSONALITY DISORDER' → summaries/001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.15_20260927-222721-7e69579b_summary.md + DOCX

[22:49:16] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[22:49:16] [INFO]   🧮 Embedding cache: 63 hits / 41 misses (61% hit-rate), 5000 entries

[22:49:16] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.15_20260927-222721-7e69579b_summary.md

[22:49:16] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries

[22:49:16] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[22:49:16] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.15_20260927-222721-7e69579b.summary.md

[22:49:16] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[22:49:16] [INFO]   ⏱️ DOCX phase starting | [1314.7s]

[22:49:16] [INFO] 📄 Building DOCX report…

[22:49:16] [INFO]   Adding chapter 1: 6 - PARANOID PERSONALITY DISORDER…

[22:49:16] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[22:49:18] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[22:49:19] [INFO]   🧹 Keypoints dedup: removed 2 duplicate(s) (82 → 80 keypoints)

[22:49:19] [DEBUG]   🗑️ '**Cameron outlined four aspects of paranoid** — 4 items from...' (embedding sim > 0.85)

[22:49:20] [DEBUG]   🗑️ '**To this composite profile (Table 6-1),** — 6 items from th...' (embedding sim > 0.85)

[22:49:20] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[22:51:14] [INFO]   🎯 K1+Classification: 80 bullets — 6 core, 60 supporting, 14 additional

[22:51:14] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:51:14] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:51:14] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[22:51:14] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[22:51:14] [INFO]   📊 Citation graph: no citations found in the text.

[22:51:14] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[22:51:14] [SUCCESS] ✅ Conversion complete.

[22:51:30] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\logs\quality_report.json

[22:51:30] [INFO] 

[22:51:30] [INFO] ━━━ Thermal Safety Report ━━━

[22:51:30] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[22:51:30] [INFO]   Session duration: 17.9 min

[22:51:30] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[22:51:30] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[22:51:30] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:51:30] [INFO] 

[22:51:30] [INFO] ━━━ Elixir v0.5.15 Conversion Diagnostic Summary ━━━

[22:51:30] [INFO]   Book: Broken Structures Salman Akhtar

[22:51:30] [INFO]   Total pages: 397

[22:51:30] [INFO]   Pages processed: 24 (selection active — 24 of 397 pages)

[22:51:30] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[22:51:30] [INFO]   Summaries generated: 1

[22:51:30] [INFO]     Success: 1, Failed: 0, Total bullets: 82

[22:51:30] [INFO]     Coverage: 100%

[22:51:30] [INFO]     Recall floor (deterministic, final set): theorists 70/74 (95%), conclusion items 3/3 (100%)

[22:51:30] [INFO]   Warnings: 0

[22:51:30] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar

[22:51:30] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.15_20260927-222721-7e69579b.conversion.log.md

[22:51:30] [INFO]   Diagnostic JSONL: None

[22:51:30] [INFO]   Summary files (3):

[22:51:30] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries\001_6_-_PARANOID_PERSONALITY_DISORDER_v0.5.15_20260927-222721-7e69579b_summary.md — generated-by v0.5.15 | run_id=20260927-222721-7e69579b | started=2026-09-27T22:33:34 | bullets=82

[22:51:30] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.15 | run_id=20260927-222721-7e69579b | started=2026-09-27T22:33:34 | bullets=82

[22:51:30] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.15_20260927-222721-7e69579b.summary.md — generated-by v0.5.15 | run_id=20260927-222721-7e69579b | started=2026-09-27T22:33:34 | bullets=82

[22:51:30] [INFO]   Models loaded at exit: (none — all unloaded)

[22:51:30] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[22:51:30] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[22:51:30] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[22:51:30] [DEBUG]   [TOC-Range] Matched '6 - PARANOID PERSONALITY DISORDER…' → '6 - PARANOID PERSONALITY DISORDER…' (p.137, score=1.00)

[22:51:30] [INFO]   📐 Visual-region cropper: scanning 24 page(s) for diagrams/charts/tables

[22:51:30] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[22:51:30] [INFO]   📊 Figure extraction: scanning 24 pages with PyMuPDF...

[22:51:30] [INFO]   ✅ Extracted 2 figure(s) → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\images

[22:51:30] [INFO]   📊 Table extraction: scanning 24 pages with pdfplumber...

[22:51:36] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\images

[22:51:42] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[22:51:42] [INFO]   [pipeline] after de-dup: 2 regions

[22:51:43] [INFO]   📐 Visual-region cropper: 2 region(s) (pdfplumber_images=2) → C:\Users\Ali Assadi\Desktop\5.15\Broken Structures Salman Akhtar\regions

[22:51:43] [INFO]   📐 Inline-embedded 2 region crop(s) into the markdown

[22:51:43] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 80 keypoints)


---
Finished at: 2026-09-27T22:51:43.219539
