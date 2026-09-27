# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-28T02:24:01.046566

<!-- generated-by: Elixir v0.5.17 | run_id=20260928-022401-45d5434e -->

---

[02:24:01] [SUCCESS] 🚀 Starting conversion…

[02:24:01] [DEBUG]   🔍 importing 'pypdf'…

[02:24:01] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[02:24:01] [DEBUG]   🔍 importing 'pdf2image'…

[02:24:01] [DEBUG]   ✅ 'pdf2image' ok (0.1s)

[02:24:01] [DEBUG]   🔍 importing 'tiktoken'…

[02:24:01] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[02:24:01] [DEBUG]   🔍 importing 'markitdown'…

[02:24:08] [DEBUG]   ✅ 'markitdown' ok (7.2s)

[02:24:08] [DEBUG]   🔍 importing 'rapidfuzz'…

[02:24:08] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[02:24:08] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[02:24:08] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[02:24:08] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[02:24:08] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[02:24:08] [DEBUG]   ✅ 'torch' installed

[02:24:08] [DEBUG]   ✅ 'transformers' installed

[02:24:08] [DEBUG]   ✅ 'langextract' installed

[02:24:08] [DEBUG]   ✅ Pre-flight dependency check passed

[02:24:08] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[02:24:08] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[02:24:08] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar.pdf

[02:24:08] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar

[02:24:08] [INFO]   Source type: normal_book

[02:24:08] [INFO]   App version: 0.5.17

[02:24:08] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[02:24:08] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[02:24:08] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[02:24:08] [INFO]   Ollama reachable (localhost:11434): True

[02:24:08] [INFO]   Provider: llamacpp

[02:24:08] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[02:24:08] [INFO]   [Phase 1 (Extraction)]

[02:24:08] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[02:24:08] [INFO]   [Phase 2 (Summarization)]

[02:24:08] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[02:24:08] [INFO]   ────────────────────────────────────────

[02:24:08] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[02:24:08] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[02:24:08] [INFO] ━━━━━━━━━━━━━━━━━━━━

[02:24:08] [INFO]   LLM OCR: True, Force OCR all: False

[02:24:08] [INFO]   Auto-detect scanned: True

[02:24:08] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:24:08] [INFO]   OCR retries: 2, Image max size: 1200

[02:24:08] [INFO]   Page range: all

[02:24:08] [INFO]   Selected chapters: 1 chapter(s)

[02:24:08] [DEBUG]     → 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS

[02:24:08] [INFO]   Segmentation: auto, Token limit: 2000

[02:24:08] [INFO]   Semantic: True, Page group: 10

[02:24:08] [INFO]   Generate summaries: True

[02:24:08] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:24:08] [INFO]   Fast model: , Heavy model: (disabled)

[02:24:08] [INFO]   Workers (requested): 1, Temperature: 0.7

[02:24:08] [INFO]   Self-consistency: False, Coverage threshold: 98%

[02:24:08] [INFO]   📈 Over-delivery: ENABLED (floor 98% → target 100%)

[02:24:08] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[02:24:08] [INFO]   Academic rigor: False

[02:24:08] [INFO]   Max context tokens: 128000

[02:24:08] [INFO]   Max output tokens: 32768

[02:24:08] [INFO]   Keep-alive: 30m

[02:24:08] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[02:24:08] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[02:24:08] [INFO]   Translation: disabled

[02:24:08] [INFO]   Clean markdown: True, Token saver: True

[02:24:08] [INFO]   Content filter: True

[02:24:08] [INFO]   Extract tables: False, Math: False, Figures: False

[02:24:08] [INFO]   Visual-region crops: True

[02:24:08] [INFO]   Layout analysis: False

[02:24:08] [INFO]   DOCX author: Elixir, TOC: True

[02:24:08] [INFO]   Output paths (V7.5 subfolders):

[02:24:08] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[02:24:08] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[02:24:08] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[02:24:08] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\packets

[02:24:08] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\podcast

[02:24:08] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\logs\quality_report.json

[02:24:08] [INFO]   Resume mode: enabled — will skip done chapters

[02:24:08] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[02:24:08] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:24:08] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[02:24:08] [INFO]   ℹ️ V0.5.14: VRAM budget estimate (peak 12.9 GB) > total (12.0 GB), BUT nvidia-smi reports 0.22 GB free (GPU-wide, across all processes). The param-count estimate may be wrong for this model. Proceeding — llama.cpp will error at load time if the model truly doesn't fit.

[02:24:08] [DEBUG]   💾 Disk space: 22.3 GB free

[02:24:08] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\.checkpoint.json

[02:25:19] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[02:25:19] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[02:25:19] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[02:25:19] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[02:25:19] [INFO] [TOC] Using PDF outlines: 22 entries.

[02:25:19] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[02:25:19] [DEBUG]   [TOC] Entries passed to segmenter: 22

[02:25:19] [DEBUG]   [TOC] - p.7: Table of Contents

[02:25:19] [DEBUG]   [TOC] - p.9: FOREWORD

[02:25:19] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[02:25:19] [DEBUG]   [TOC] … and 19 more

[02:25:19] [INFO]   🎯 User selected 1 chapter(s):

[02:25:19] [INFO]     → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE' (TOC page 222)

[02:25:20] [INFO]   📸 front_cover → front_cover.jpg

[02:25:20] [INFO]   📸 back_cover → back_cover.jpg

[02:25:20] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[02:25:20] [INFO]   📸 Screenshotting 21 selected chapter page(s)...

[02:25:20] [DEBUG]   📸 p.222 → chapter_page_222.jpg

[02:25:20] [DEBUG]   📸 p.223 → chapter_page_223.jpg

[02:25:20] [DEBUG]   📸 p.224 → chapter_page_224.jpg

[02:25:20] [DEBUG]   📸 p.225 → chapter_page_225.jpg

[02:25:21] [DEBUG]   📸 p.226 → chapter_page_226.jpg

[02:25:21] [DEBUG]   📸 p.227 → chapter_page_227.jpg

[02:25:21] [DEBUG]   📸 p.228 → chapter_page_228.jpg

[02:25:21] [DEBUG]   📸 p.229 → chapter_page_229.jpg

[02:25:21] [DEBUG]   📸 p.230 → chapter_page_230.jpg

[02:25:21] [DEBUG]   📸 p.231 → chapter_page_231.jpg

[02:25:22] [DEBUG]   📸 p.232 → chapter_page_232.jpg

[02:25:22] [DEBUG]   📸 p.233 → chapter_page_233.jpg

[02:25:22] [DEBUG]   📸 p.234 → chapter_page_234.jpg

[02:25:22] [DEBUG]   📸 p.235 → chapter_page_235.jpg

[02:25:22] [DEBUG]   📸 p.236 → chapter_page_236.jpg

[02:25:23] [DEBUG]   📸 p.237 → chapter_page_237.jpg

[02:25:23] [DEBUG]   📸 p.238 → chapter_page_238.jpg

[02:25:23] [DEBUG]   📸 p.239 → chapter_page_239.jpg

[02:25:23] [DEBUG]   📸 p.240 → chapter_page_240.jpg

[02:25:23] [DEBUG]   📸 p.241 → chapter_page_241.jpg

[02:25:23] [DEBUG]   📸 p.242 → chapter_page_242.jpg

[02:25:23] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[02:25:23] [INFO]   📄 Derived 21 pages from TOC for 1 selected chapter(s) (skipping 376 unselected pages)

[02:25:23] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[02:25:23] [INFO]   📄 OCR pages filtered: 31 → 0 (only scanning pages within selected chapters)

[02:25:23] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[02:25:23] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[02:25:24] [INFO]   ✅ markitdown ready for digital-page extraction

[02:25:24] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[02:25:24] [INFO]   📄 Processing 21/397 pages (chapter selection active — skipping 376 unselected pages)

[02:25:35] [INFO]   📄 240/397 pages processed (60%)

[02:25:36] [INFO]   📄 242/397 pages processed (61%)

[02:25:36] [SUCCESS] ✅ PDF processing done: 21/397 pages extracted

[02:25:36] [DEBUG]   🔧 Hyphenation repair: 20 line-break joins

[02:25:36] [DEBUG]   🧹 Tab cleanup: replaced 6321 tab character(s) with spaces

[02:25:36] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[02:25:36] [INFO]   🔍 Content auto-detection: Academic Paper / Scientific Article (75% confidence) — 4 citations, 1 publisher marker(s)

[02:25:36] [INFO]   ℹ️ Detected 'Academic Paper / Scientific Article' at only 75% confidence (< the 85% academic-switch bar) — keeping normal_book preset. Domain textbooks with citations are the known false-positive class; a wrong switch silently enables Academic Rigor mode.

[02:25:36] [DEBUG]     academic_paper: score=3.0 (4 citations, 1 publisher marker(s))

[02:25:36] [DEBUG]     normal_book: score=1.0 (default (no strong signals for other types))

[02:25:36] [INFO] 📝 Raw markdown: 50,678 chars | [95.9s]

[02:25:36] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[02:25:36] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[02:25:36] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[02:25:36] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[02:25:36] [INFO] [Segmenter] Attempting chapter-level segmentation…

[02:25:36] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 137 has no marker for '6 - PARANOID PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[02:25:36] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[02:25:36] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[02:25:36] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[02:25:37] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[02:25:37] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[02:25:37] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[02:25:37] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[02:25:37] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[02:25:37] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[02:25:37] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[02:25:37] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[02:25:37] [DEBUG]      Selected: ['9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS']

[02:25:37] [INFO]   📑 Filtered segments: kept 1 of 17

[02:25:37] [INFO] 📚 1 segment(s) detected | [96.0s]

[02:25:37] [DEBUG]   ✅ Seg 1/1: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DI' | 10,848 tokens | p.222–242

[02:25:37] [INFO] 🌐 Detected language: en

[02:25:37] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[02:25:37] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[02:25:37] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\markdown\chapters

[02:25:37] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[02:25:37] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\markdown\chapters

[02:25:37] [DEBUG]    [V17.5] Analysis file: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3851 bytes)

[02:25:37] [INFO]   ⏱️ Summary phase starting | [96.4s]

[02:25:39] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[02:25:39] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[02:25:39] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[02:25:39] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[02:25:39] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[02:25:39] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[02:25:39] [INFO]   🌡️ Pre-flight: idle GPU temp = 62°C

[02:25:39] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 62°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[02:25:39] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[02:25:39] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[02:25:39] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[02:25:39] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[02:25:39] [DEBUG]   🎛️ Model profile: Default

[02:25:39] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[02:25:39] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[02:25:39] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[02:25:39] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[02:25:39] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[02:25:39] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[02:25:39] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 4 concepts — ['Charles Simic', 'Libidinal Types', 'Social Functioning Any', 'Related Differences Some']

[02:25:39] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Bleuler', 'Kernberg', 'Zetzel', 'Cooper', 'Lazare']

[02:25:39] [DEBUG]     🎯 V15.2.0 #3 (section headings): 2 concepts — ['Histrionic And Schizotypal\nPersonality Disorders', 'Mixed Forms And Extrinsic Influences On\nSymptomatology']

[02:25:39] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 4 concepts — ['mixed forms', 'level of social functioning', 'sex-related differences', 'changes in symptomatology over the life span, and']

[02:25:39] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[02:25:39] [DEBUG]     🎯 V15.2.0: merged 25 concepts before source-grounding

[02:25:39] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 25 concepts grounded ✓

[02:25:39] [INFO]     🎯 V15.2.0: FINAL 25 concepts (cap 50)

[02:25:39] [DEBUG]   🎯 '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI…': 25 concepts extracted (V15.2.0 enhanced)

[02:25:39] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[02:25:39] [INFO]   📖 Chapter 1/1: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE' (50656 chars)

[02:25:39] [INFO]   🎯 User selected: ['9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS']

[02:25:39] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[02:25:39] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[02:25:39] [INFO] 📚 Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS…

[02:25:39] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.17

[02:25:39] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[02:25:39] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3742 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[02:25:39] [INFO]     📊 V17.2: Prepended deterministic analysis (3742 chars) — citation recall 78%→100%

[02:25:39] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=10,845 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 10,845 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[02:25:39] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[02:25:39] [DEBUG]     🎯 Injecting 25 concepts + 0 callouts into prompt

[02:25:40] [INFO]     📦 V0.4: master-summary architecture (default) — input 10845 tok, output cap 32768

[02:25:40] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[02:25:40] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:25:40] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[02:26:50] [INFO]     ✅ V0.3 Call 1/3: master summary = 751 words, 5799 chars

[02:26:50] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[02:26:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:26:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[02:27:24] [INFO]     ✅ V0.3 Call 2/3: 27 bullets derived from master summary

[02:27:24] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[02:27:24] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:27:24] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[02:27:41] [INFO]     ✅ V0.3 Call 3/3: exec summary = 254 words

[02:27:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[02:27:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[02:29:50] [INFO]     📖 V0.5.7 source glossary (separate call) → C:\Users\Ali Assadi\Desktop\5.17\summaries\.glossaries\9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.glossary.md

[02:29:50] [DEBUG]     📝 Parsed: exec=2002 chars, bullets=27, thorough=5799 chars

[02:30:41] [INFO]     📊 Primary coverage: 100% | keywords: ['disorder']

[02:30:43] [DEBUG]     🔍 Coverage detail: 3/3 keywords found | missing: []

[02:30:43] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (27 bullets, 254 exec words, 751 thorough words) → .checkpoints/primary_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md

[02:30:44] [DEBUG]     🔍 Fact-check: all 27 bullets verified ✓

[02:30:44] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[02:30:44] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:30:44] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[02:31:30] [INFO]     ✅ Additive sections via followup call: key_distinctions=1368 chars, theoretical_tensions=1304 chars

[02:31:30] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (27 bullets, 254 exec words, 751 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md

[02:31:30] [WARNING]     ⚠️ thorough_summary too short (751 words < 800 threshold) — requesting dedicated expansion…

[02:31:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[02:31:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[02:32:39] [INFO]     📖 Attempt 1/3: dedicated thorough = 754 words

[02:32:39] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[02:32:42] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[02:32:42] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[02:33:27] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying (attempt 3/3)

[02:33:27] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[02:33:27] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[02:34:11] [INFO]     📖 Attempt 3/3: dedicated thorough = 755 words

[02:34:11] [WARNING]   ⏱️⚠️ Deadline exceeded (512s > 480s) — skipping optional phase: dedicated thorough (attempt 4 length-directive)

[02:34:11] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=755) — keeping best-effort result

[02:34:11] [INFO]     ✅ thorough_summary expanded via dedicated call: 751 → 755 words

[02:34:11] [WARNING]   ⏱️⚠️ Deadline exceeded (512s > 480s) — skipping optional phase: dedicated bullet expansion

[02:34:11] [INFO]     ✅ Final coverage 100%

[02:34:11] [DEBUG]     📏 F1: exec=254w, thorough=755w (source=7133w; targets exec<=250w, thorough<=3210w)

[02:35:28] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[02:35:28] [DEBUG]     📖 F3: Reading level — source: 15.5, summary: 19.8 (diff: -4.3)

[02:35:28] [INFO]     ℹ️ F3: Summary is 4.3 grade levels denser than source — expected for a compressed academic summary.

[02:35:30] [DEBUG]     📊 I2: Chapter difficulty 0.56/1.0 (grade 15.5, strategy: multi_sample)

[02:35:30] [DEBUG]     🔄 J2: 18 cross-section redundancy(ies) found (exec↔bullets: 6, bullets↔thorough: 12)

[02:35:30] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 4 markers)

[02:35:30] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[02:35:30] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[02:35:30] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[02:35:47] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 3248 per-pair calls)

[02:35:47] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[02:35:50] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (27/27 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[02:35:50] [INFO]   ℹ️ Summary has substantial content (exec=2002 chars, thorough=5816 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[02:35:50] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[02:35:50] [WARNING]   ⏱️⚠️ Deadline exceeded (611s > 480s) — skipping optional phase: scholar reflection

[02:35:50] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[02:35:50] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[02:35:50] [WARNING]   ⏱️⚠️ Deadline exceeded (611s > 480s) — skipping optional phase: semantic dedup

[02:35:50] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[02:35:50] [DEBUG]     🧹 V16.0.2 Bullet normalization: 27 bullets normalized

[02:35:50] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[02:35:50] [WARNING]   ⏱️⚠️ Deadline exceeded (611s > 480s) — skipping optional phase: bullet consolidation

[02:35:50] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[02:35:50] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.17

[02:35:50] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[02:35:50] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3742 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[02:35:50] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Lesser', 'Kety', 'Easser and Lesser', 'Rado', 'Easser', 'Reich', 'Meehl']/69 authors in bullets (12%) — MISSING from bullets: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Freud']

[02:35:50] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Lesser', 'Kety', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Meehl', 'Fenichel', 'Halleck', 'Hoch', 'Zilboorg', 'Hoch and Polatin', 'Polatin']/69 authors in thorough (28%) — MISSING from thorough: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']

[02:35:50] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Freud']…

[02:35:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:35:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:36:05] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[02:36:05] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.2s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[02:36:05] [DEBUG]     📊 V18.14.1: After round 1, 50 still missing from bullets: ['Marmor', 'Fenichel', 'Halleck', 'Cooper', 'Abse']…

[02:36:05] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Marmor', 'Fenichel', 'Halleck', 'Cooper', 'Abse']…

[02:36:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:36:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:36:21] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Wolman (1987) documented the overlap between narcissistic and antisoci…

[02:36:21] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 7/8 bullets

[02:36:21] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (15.4s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[02:36:21] [DEBUG]     📊 V18.14.1: After round 2, 43 still missing from bullets: ['Wolman', 'Lazare', 'Hoch', 'Klein', 'Bursten']…

[02:36:21] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Wolman', 'Lazare', 'Hoch', 'Klein', 'Bursten']…

[02:36:21] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:36:21] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:36:38] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Hoch' (grounded in glossary context, not verbatim quote)

[02:36:38] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 8/8 bullets

[02:36:38] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (17.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[02:36:38] [DEBUG]     📊 V18.14.1: After round 3, 31 still missing from bullets: ['Kretschmer', 'Kasanin and Rosen', 'Terry and Rennie', 'Kallman', 'Nanarello']…

[02:36:38] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Kretschmer', 'Kasanin and Rosen', 'Terry and Rennie', 'Kallman', 'Nanarello']…

[02:36:38] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:36:38] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:36:50] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 8/8 bullets

[02:36:50] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (11.6s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[02:36:50] [DEBUG]     📊 V18.14.1: After round 4, 19 still missing from bullets: ['Frances', 'Fairbairn', 'Guntrip', 'Ekstein', 'Noble']…

[02:36:50] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Frances', 'Fairbairn', 'Guntrip', 'Ekstein', 'Noble']…

[02:36:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:36:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:37:01] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Ekstein helped popularize the notion of latent schizophrenia, a concep…

[02:37:01] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 7/8 bullets

[02:37:01] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (11.8s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=1, added=7

[02:37:01] [DEBUG]     📊 V18.14.1: After round 5, 11 still missing from bullets: ['Ekstein', 'Wolf', 'Akiskal', 'Thomson', 'Erikson']…

[02:37:01] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 38 bullets across 5 round(s)

[02:37:01] [INFO]     ✨ V0.5.6 final-check: firing TARGETED round 4 for 19 glossary-grounded author(s) still missing after round 5: Abraham, Akiskal, Bergman, Blacker and Tupin, Bleiberg, Ekstein, Gorton and Akht

[02:37:01] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:37:01] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Abraham' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Akiskal' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Bergman' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Blacker and Tupin' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Bleiberg' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Ekstein' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Gorton and Akhtar' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Gunderson and Siever' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kohut and Wolf' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Reich' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rinsley' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rosenthal et al.' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Simic' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Snyder et al.' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Spitzer et al.' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Thomson' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Wender et al.' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Widiger et al.' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Wolff and Chick' (grounded in glossary context, not verbatim quote)

[02:37:18] [INFO]     ✨ V0.5.6 final-check: round 4 added 19/19 glossary-grounded bullet(s)

[02:37:18] [INFO]     ✨ V0.5.6 final-check: 60/60 authors (100%) — full coverage achieved. Glossary: (none)

[02:37:18] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[02:37:18] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Characteristics bullet (all 5 items, verbatim from source) — not scattered

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 7-item runin_arabic list (7 item(s) were uncovered; all 7 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item runin_arabic list (3 item(s) were uncovered; all 5 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item roman_lower_paren list (4 item(s) were uncovered; all 5 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (1 item(s) were uncovered; all 3 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (3 item(s) were uncovered; all 8 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (2 item(s) were uncovered; all 3 now carried verbatim)

[02:37:18] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (1 item(s) were uncovered; all 3 now carried verbatim)

[02:37:19] [DEBUG]     🧹 Semantic dedup: removing bullet 8 (sim=0.90 with bullet 7)

[02:37:19] [DEBUG]     🧹 Semantic dedup: removing bullet 17 (sim=0.85 with bullet 3)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 39 (sim=0.87 with bullet 7)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 41 (sim=0.86 with bullet 31)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 54 (sim=0.89 with bullet 51)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 69 (sim=0.90 with bullet 30)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 82 (sim=0.90 with bullet 77)

[02:37:20] [DEBUG]     🧹 Semantic dedup: removing bullet 83 (sim=0.87 with bullet 72)

[02:37:20] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 95 → 87 bullets (removed 8 gap-fill/conclusion duplicates; 1.1s, non-skippable per V18.20.3.4)

[02:37:20] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.17

[02:37:20] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[02:37:20] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3742 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[02:37:22] [INFO]     🛡️ V18.2.13 Post-checks: 7 fixed, 9 flagged (of 87 bullets + exec + thorough)

[02:37:22] [DEBUG]       [sentence_fusion/flag] bullet[28]: likely source-propagated fusion garble: 'selfdestructive' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'destructive' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-destructive').  |  stible, and less overtly selfdestructive (1985a, 1983).

[02:37:22] [DEBUG]       [parenthetical_promotion/flag] bullet[40]: V0.5.15: bullet for 'Hoch' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Hoch made significant contributions to the description of sc

[02:37:22] [DEBUG]       [attribution/flag] bullet[65]: attribution mismatch: summary's claim about 'Gorton and Akhtar (1990)' has 42% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Gorton and Akhtar (1990) discu…

[02:37:22] [DEBUG]       [attribution/flag] bullet[66]: attribution mismatch: summary's claim about 'Gunderson and Siever (1983)' has 37% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  Gunderson and Siever (1983) co…

[02:37:22] [DEBUG]       [parenthetical_promotion/flag] bullet[68]: V0.5.15: bullet for 'Reich' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Reich (1933, 1987) emphasized genital fixation in hysterical

[02:37:22] [DEBUG]       [attribution/flag] bullet[76]: bold-name attribution mismatch: '**Characteristics**: (1) mixed forms; (2) level of social fun…' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  **Characteristics**: (1) mixed…

[02:37:22] [DEBUG]       [sentence_fusion/flag] thorough: likely sentence-fusion garble: 'borderline-antisocial' contains two source-words 'order' and 'social' separated by a 8-char gap 'lineanti' (not in source or English lexicon). The gap is likely a remnant of a dropped sentence boundary.  |  , narcissistic-paranoid, borderline-antisocial) and does not invalidate

[02:37:22] [DEBUG]       [quote_verification/fix] bullet[4]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who is stable and from intact families, and the 

[02:37:22] [DEBUG]       [quote_verification/fix] bullet[9]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality observed in relatives of schizophrenics and 

[02:37:22] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   to a distinct diagnosis, highlighting historical conflicts 

[02:37:22] [DEBUG]       [quote_verification/fix] exec: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   traits observed in schizophrenic relatives and 

[02:37:22] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   hysterical personality (characterized by ambition, competit

[02:37:22] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=222, end_page=242; ~ marks an ESTIMATED locator, not a verified one)  |  - Hysterical personality disorder vs. histrionic personality

[02:37:22] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=222, end_page=242; ~ marks an ESTIMATED locator, not a verified one)  |  - Phallic-oedipal vs. preoedipal determinants of hysterical 

[02:37:22] [DEBUG]       [near_duplicate/flag] bullet[46]: near-duplicate KEPT — uniquely covers source author(s) Kretschmer absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kretschmer (1925) made significant contributions to the desc

[02:37:22] [DEBUG]       [near_duplicate/flag] bullet[49]: near-duplicate KEPT — uniquely covers source author(s) Nanarello absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Nanarello (1953) made significant contributions to the descr

[02:37:22] [INFO]     ℹ️ V0.4.23: 87 bullets ship (>80 — the historical hard cap is REMOVED per the user's no-limit directive; dedup/consolidation/filler-floor are the reducers, never truncation).

[02:37:22] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 19/69 authors in thorough — MISSING from thorough: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']

[02:37:22] [WARNING]   ⏱️⚠️ Deadline exceeded (703s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[02:37:22] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 50 of 69 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[02:37:22] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:37:22] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:37:57] [INFO]   ✨ V0.5.15: recovered 1 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[02:38:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:38:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:38:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "These descriptive contributions laid the groundwork for the DSM-III cr…" — its name(s) never co-occur with the claim's key phrases in the source

[02:38:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Additionally, the chapter highlights the role of Bursten and Lilienfel…" — its name(s) never co-occur with the claim's key phrases in the source

[02:38:50] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The interplay between these diverse contributors—from Kretschmer’s des…" — its name(s) never co-occur with the claim's key phrases in the source

[02:38:50] [INFO]   ✨ V0.5.15: recovered 2 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[02:39:06] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[02:39:07] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[02:39:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The post-DSM-III evaluation of these criteria involved significant emp…" — its name(s) never co-occur with the claim's key phrases in the source

[02:39:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Concurrently, the conceptual boundaries between these severe disorders…" — its name(s) never co-occur with the claim's key phrases in the source

[02:39:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The chapter also addresses the differential diagnosis of borderline di…" — its name(s) never co-occur with the claim's key phrases in the source

[02:39:48] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Finally, the discussion on sex-related differences and cultural influe…" — its name(s) never co-occur with the claim's key phrases in the source

[02:40:04] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 19/69 → 41/69 (3 chunked call(s), ≤12 names each; 14 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[02:40:04] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 66/69 in final bullets (missing: ['Cooper', 'Kallman', 'Erikson']); conclusion items 5/5; enumerated items (all lists, whole chapter) 71/71. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[02:40:04] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 864s > 480s (heading='9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI') — possible model stall. Summary kept, but this chapter consumed 864s of the budget.

[02:40:04] [INFO] ✅ Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI… complete

[02:40:04] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":87,"exec_chars":1998,"chapter_done":true}

[02:40:04] [DEBUG]   📊 Progress: 1/1 done | 87 bullets | 1,998 chars exec summary

[02:40:04] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\checkpoints

[02:40:04] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 8 source author(s) NOT found in the summary (Kety et al., Lilienfeld et al., Robins et al., Rosenthal et al., Snyder et al., Spitzer et al., Wend). Glossary: (none). Cross-ref: confirmed=48, llm_only=12, regex_only=21.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1988' (ce:1988) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1905' (ce:1905) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1909' (ce:1909) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1911' (ce:1911) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1940s' (decade:1940) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1950s' (decade:1950) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1946' (ce:1946) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1911' (ce:1911) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1960s' (decade:1960) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970s' (decade:1970) NOT found in summary — possible omission.

[02:40:04] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 8 source author(s) NOT found in the summary (Kety et al., Lilienfeld et al., Rob

[02:40:04] [INFO] 📄 Building DOCX report…

[02:40:04] [INFO]   Adding chapter 1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…

[02:40:04] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\checkpoints\chapters\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.docx

[02:40:04] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' → summaries/001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.17_20260928-022401-45d5434e_summary.md + DOCX

[02:40:04] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[02:40:04] [INFO]   🧮 Embedding cache: 0 hits / 92 misses (0% hit-rate), 5000 entries

[02:40:04] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.17_20260928-022401-45d5434e_summary.md

[02:40:04] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries

[02:40:04] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[02:40:04] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.17_20260928-022401-45d5434e.summary.md

[02:40:04] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[02:40:04] [INFO]   ⏱️ DOCX phase starting | [963.8s]

[02:40:04] [INFO] 📄 Building DOCX report…

[02:40:04] [INFO]   Adding chapter 1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…

[02:40:05] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[02:40:06] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[02:40:09] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[02:42:19] [INFO]   🎯 K1+Classification: 87 bullets — 16 core, 56 supporting, 15 additional

[02:42:19] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[02:42:19] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[02:42:19] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[02:42:19] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[02:42:19] [INFO]   📊 Citation graph: no citations found in the text.

[02:42:19] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[02:42:19] [SUCCESS] ✅ Conversion complete.

[02:42:31] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\logs\quality_report.json

[02:42:31] [INFO] 

[02:42:31] [INFO] ━━━ Thermal Safety Report ━━━

[02:42:31] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[02:42:31] [INFO]   Session duration: 16.9 min

[02:42:31] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[02:42:31] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[02:42:31] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:42:31] [INFO] 

[02:42:31] [INFO] ━━━ Elixir v0.5.17 Conversion Diagnostic Summary ━━━

[02:42:31] [INFO]   Book: Broken Structures Salman Akhtar

[02:42:31] [INFO]   Total pages: 397

[02:42:31] [INFO]   Pages processed: 21 (selection active — 21 of 397 pages)

[02:42:31] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[02:42:31] [INFO]   Summaries generated: 1

[02:42:31] [INFO]     Success: 1, Failed: 0, Total bullets: 87

[02:42:31] [INFO]     Coverage: 100%

[02:42:31] [INFO]     Recall floor (deterministic, final set): theorists 66/69 (96%), conclusion items 5/5 (100%)

[02:42:31] [INFO]   Warnings: 0

[02:42:31] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar

[02:42:31] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.17_20260928-022401-45d5434e.conversion.log.md

[02:42:31] [INFO]   Diagnostic JSONL: None

[02:42:31] [INFO]   Summary files (3):

[02:42:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.17_20260928-022401-45d5434e_summary.md — generated-by v0.5.17 | run_id=20260928-022401-45d5434e | started=2026-09-28T02:25:39 | bullets=87

[02:42:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.17 | run_id=20260928-022401-45d5434e | started=2026-09-28T02:25:39 | bullets=87

[02:42:31] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.17_20260928-022401-45d5434e.summary.md — generated-by v0.5.17 | run_id=20260928-022401-45d5434e | started=2026-09-28T02:25:39 | bullets=87

[02:42:31] [INFO]   Models loaded at exit: (none — all unloaded)

[02:42:31] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[02:42:31] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[02:42:31] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[02:42:31] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[02:42:31] [INFO]   📐 Visual-region cropper: scanning 21 page(s) for diagrams/charts/tables

[02:42:31] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[02:42:31] [INFO]   📊 Figure extraction: scanning 21 pages with PyMuPDF...

[02:42:31] [INFO]   ✅ Extracted 0 figure(s) → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\images

[02:42:31] [INFO]   📊 Table extraction: scanning 21 pages with pdfplumber...

[02:42:36] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\images

[02:42:42] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[02:42:42] [INFO]   [pipeline] after de-dup: 0 regions

[02:42:42] [INFO]   📐 Visual-region cropper: 0 region(s) (none) → C:\Users\Ali Assadi\Desktop\5.17\Broken Structures Salman Akhtar\regions

[02:42:42] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 87 keypoints)


---
Finished at: 2026-09-28T02:42:42.503539
