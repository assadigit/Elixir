# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-09-28T15:58:51.889607

<!-- generated-by: Elixir v0.5.19.1 | run_id=20260928-155851-011587f0 -->

---

[15:58:51] [SUCCESS] 🚀 Starting conversion…

[15:58:51] [DEBUG]   🔍 importing 'pypdf'…

[15:58:51] [DEBUG]   ✅ 'pypdf' ok (0.0s)

[15:58:51] [DEBUG]   🔍 importing 'pdf2image'…

[15:58:51] [DEBUG]   ✅ 'pdf2image' ok (0.0s)

[15:58:51] [DEBUG]   🔍 importing 'tiktoken'…

[15:58:51] [DEBUG]   ✅ 'tiktoken' ok (0.0s)

[15:58:51] [DEBUG]   🔍 importing 'markitdown'…

[15:58:53] [DEBUG]   ✅ 'markitdown' ok (1.9s)

[15:58:53] [DEBUG]   🔍 importing 'rapidfuzz'…

[15:58:53] [DEBUG]   ✅ 'rapidfuzz' ok (0.0s)

[15:58:53] [DEBUG]   ⏭️ 'camelot' not needed for this conversion

[15:58:53] [DEBUG]   ⏭️ 'pix2tex' not needed for this conversion

[15:58:53] [DEBUG]   ⏭️ 'pdfplumber' not needed for this conversion

[15:58:53] [INFO]   ⏭️ sentence-transformers skipped — embedder 'nomic-embed-text' runs via Ollama (no Python package needed)

[15:58:53] [DEBUG]   ✅ 'torch' installed

[15:58:53] [DEBUG]   ✅ 'transformers' installed

[15:58:53] [DEBUG]   ✅ 'langextract' installed

[15:58:53] [DEBUG]   ✅ Pre-flight dependency check passed

[15:58:53] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[15:58:53] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[15:58:53] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar.pdf

[15:58:53] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar

[15:58:53] [INFO]   Source type: normal_book

[15:58:53] [INFO]   App version: 0.5.19.1

[15:58:53] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[15:58:53] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[15:58:53] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[15:58:53] [INFO]   Ollama reachable (localhost:11434): True

[15:58:53] [INFO]   Provider: llamacpp

[15:58:53] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[15:58:53] [INFO]   [Phase 1 (Extraction)]

[15:58:53] [INFO]     OCR: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[15:58:53] [INFO]   [Phase 2 (Summarization)]

[15:58:53] [INFO]     Summarization: Ternary-Bonsai-2-27B-Instruct-Vision (~12.9 GB)

[15:58:53] [INFO]   ────────────────────────────────────────

[15:58:53] [INFO]   Peak (max across phases): 12.9 GB / 12.0 GB available

[15:58:53] [INFO]   ❌ OVERBUDGET: Peak VRAM 12.9 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[15:58:53] [INFO] ━━━━━━━━━━━━━━━━━━━━

[15:58:53] [INFO]   LLM OCR: True, Force OCR all: False

[15:58:53] [INFO]   Auto-detect scanned: True

[15:58:53] [INFO]   Primary OCR model: Ternary-Bonsai-2-27B-Instruct-Vision

[15:58:53] [INFO]   OCR retries: 2, Image max size: 1200

[15:58:53] [INFO]   Page range: all

[15:58:53] [INFO]   Selected chapters: 1 chapter(s)

[15:58:53] [DEBUG]     → 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS

[15:58:53] [INFO]   Segmentation: auto, Token limit: 2000

[15:58:53] [INFO]   Semantic: True, Page group: 10

[15:58:53] [INFO]   Generate summaries: True

[15:58:53] [INFO]   Model: Ternary-Bonsai-2-27B-Instruct-Vision

[15:58:53] [INFO]   Fast model: , Heavy model: (disabled)

[15:58:53] [INFO]   Workers (requested): 1, Temperature: 0.7

[15:58:53] [INFO]   Self-consistency: False, Coverage threshold: 99%

[15:58:53] [INFO]   📈 Over-delivery: ENABLED (floor 99% → target 100%)

[15:58:53] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[15:58:53] [INFO]   Academic rigor: False

[15:58:53] [INFO]   Max context tokens: 128000

[15:58:53] [INFO]   Max output tokens: 32768

[15:58:53] [INFO]   Keep-alive: 30m

[15:58:54] [DEBUG]   Presence penalty: (Modelfile unreadable — run `ollama show Ternary-Bonsai-2-27B-Instruct-Vision` to verify 1.5)

[15:58:54] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[15:58:54] [INFO]   Translation: disabled

[15:58:54] [INFO]   Clean markdown: True, Token saver: True

[15:58:54] [INFO]   Content filter: True

[15:58:54] [INFO]   Extract tables: False, Math: False, Figures: False

[15:58:54] [INFO]   Visual-region crops: True

[15:58:54] [INFO]   Layout analysis: False

[15:58:54] [INFO]   DOCX author: Elixir, TOC: True

[15:58:54] [INFO]   Output paths (V7.5 subfolders):

[15:58:54] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[15:58:54] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[15:58:54] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[15:58:54] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\packets

[15:58:54] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\podcast

[15:58:54] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\logs\quality_report.json

[15:58:54] [INFO]   Resume mode: enabled — will skip done chapters

[15:58:54] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[15:58:54] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[15:58:54] [DEBUG]   🗄️ V0.05: Resume enabled — stale-artifact archiving skipped (existing chapter summaries are reused).

[15:58:54] [INFO]   ℹ️ V0.5.14: VRAM budget estimate (peak 12.9 GB) > total (12.0 GB), BUT nvidia-smi reports 0.18 GB free (GPU-wide, across all processes). The param-count estimate may be wrong for this model. Proceeding — llama.cpp will error at load time if the model truly doesn't fit.

[15:58:54] [DEBUG]   💾 Disk space: 35.9 GB free

[15:58:54] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\.checkpoint.json

[15:59:54] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[15:59:54] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[15:59:54] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[15:59:54] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[15:59:54] [INFO] [TOC] Using PDF outlines: 22 entries.

[15:59:54] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[15:59:54] [DEBUG]   [TOC] Entries passed to segmenter: 22

[15:59:54] [DEBUG]   [TOC] - p.7: Table of Contents

[15:59:54] [DEBUG]   [TOC] - p.9: FOREWORD

[15:59:54] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[15:59:54] [DEBUG]   [TOC] … and 19 more

[15:59:54] [INFO]   🎯 User selected 1 chapter(s):

[15:59:54] [INFO]     → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE' (TOC page 222)

[15:59:55] [INFO]   📸 front_cover → front_cover.jpg

[15:59:55] [INFO]   📸 back_cover → back_cover.jpg

[15:59:55] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[15:59:55] [INFO]   📸 Screenshotting 21 selected chapter page(s)...

[15:59:55] [DEBUG]   📸 p.222 → chapter_page_222.jpg

[15:59:55] [DEBUG]   📸 p.223 → chapter_page_223.jpg

[15:59:55] [DEBUG]   📸 p.224 → chapter_page_224.jpg

[15:59:55] [DEBUG]   📸 p.225 → chapter_page_225.jpg

[15:59:56] [DEBUG]   📸 p.226 → chapter_page_226.jpg

[15:59:56] [DEBUG]   📸 p.227 → chapter_page_227.jpg

[15:59:56] [DEBUG]   📸 p.228 → chapter_page_228.jpg

[15:59:56] [DEBUG]   📸 p.229 → chapter_page_229.jpg

[15:59:56] [DEBUG]   📸 p.230 → chapter_page_230.jpg

[15:59:56] [DEBUG]   📸 p.231 → chapter_page_231.jpg

[15:59:57] [DEBUG]   📸 p.232 → chapter_page_232.jpg

[15:59:57] [DEBUG]   📸 p.233 → chapter_page_233.jpg

[15:59:57] [DEBUG]   📸 p.234 → chapter_page_234.jpg

[15:59:57] [DEBUG]   📸 p.235 → chapter_page_235.jpg

[15:59:57] [DEBUG]   📸 p.236 → chapter_page_236.jpg

[15:59:58] [DEBUG]   📸 p.237 → chapter_page_237.jpg

[15:59:58] [DEBUG]   📸 p.238 → chapter_page_238.jpg

[15:59:58] [DEBUG]   📸 p.239 → chapter_page_239.jpg

[15:59:58] [DEBUG]   📸 p.240 → chapter_page_240.jpg

[15:59:58] [DEBUG]   📸 p.241 → chapter_page_241.jpg

[15:59:58] [DEBUG]   📸 p.242 → chapter_page_242.jpg

[15:59:58] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[15:59:58] [INFO]   📄 Derived 21 pages from TOC for 1 selected chapter(s) (skipping 376 unselected pages)

[15:59:58] [INFO]   📄 Boundary overlap SKIPPED — TOC-derived page ranges are exact (V0.03 P0-4: ±1 expansion leaked the next unselected chapter's first page in the V0.02 rig run).

[15:59:58] [INFO]   📄 OCR pages filtered: 31 → 0 (only scanning pages within selected chapters)

[15:59:58] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[15:59:58] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[15:59:59] [INFO]   ✅ markitdown ready for digital-page extraction

[15:59:59] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[15:59:59] [INFO]   📄 Processing 21/397 pages (chapter selection active — skipping 376 unselected pages)

[16:00:08] [INFO]   📄 240/397 pages processed (60%)

[16:00:09] [INFO]   📄 242/397 pages processed (61%)

[16:00:09] [SUCCESS] ✅ PDF processing done: 21/397 pages extracted

[16:00:09] [DEBUG]   🔧 Hyphenation repair: 20 line-break joins

[16:00:09] [DEBUG]   🧹 Tab cleanup: replaced 6321 tab character(s) with spaces

[16:00:09] [DEBUG]   🧹 Header/footer removal: 2 chars stripped

[16:00:09] [INFO]   🔍 Content auto-detection: Academic Paper / Scientific Article (75% confidence) — 4 citations, 1 publisher marker(s)

[16:00:09] [INFO]   ℹ️ Detected 'Academic Paper / Scientific Article' at only 75% confidence (< the 85% academic-switch bar) — keeping normal_book preset. Domain textbooks with citations are the known false-positive class; a wrong switch silently enables Academic Rigor mode.

[16:00:09] [DEBUG]     academic_paper: score=3.0 (4 citations, 1 publisher marker(s))

[16:00:09] [DEBUG]     normal_book: score=1.0 (default (no strong signals for other types))

[16:00:09] [INFO] 📝 Raw markdown: 50,678 chars | [77.4s]

[16:00:09] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[16:00:09] [WARNING]   [Selection] Only 1 TOC entry matched the selected chapters — a 1-entry TOC would disable TOC segmentation (falls to heading-based). Segmenting the full TOC; the post-segmentation filter stays active.

[16:00:09] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[16:00:09] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[16:00:09] [INFO] [Segmenter] Attempting chapter-level segmentation…

[16:00:09] [DEBUG]   [Segmenter] Page 9 has no marker for 'FOREWORD' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 15 has no marker for '1 - IDENTITY AND ITS ORIGINS' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 33 has no marker for '2 - THE SYNDROME OF IDENTITY DIFFUSION' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 48 has no marker for '3 - NARCISSISTIC PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 77 has no marker for '4 - BORDERLINE PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 113 has no marker for '5 - SCHIZOID PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 137 has no marker for '6 - PARANOID PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 161 has no marker for '7 - HYPOMANIC PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 182 has no marker for '8 - ANTISOCIAL PERSONALITY DISORDER' — starting at nearest following marker (page 222).

[16:00:09] [DEBUG]   [Segmenter] Page 244 has no marker for '10 - INITIAL EVALUATION AND EARLY TREATM' — starting at nearest following marker (page 398).

[16:00:09] [DEBUG]   [Segmenter] Page 272 has no marker for '11 - PSYCHOANALYTIC PSYCHOTHERAPY' — starting at nearest following marker (page 398).

[16:00:09] [DEBUG]   [Segmenter] Page 312 has no marker for '12 - SUMMARY, CONCLUSION, AND RECOMMENDA' — starting at nearest following marker (page 398).

[16:00:09] [DEBUG]   [Segmenter] Page 331 has no marker for 'REFERENCES' — starting at nearest following marker (page 398).

[16:00:09] [DEBUG]   [Segmenter] Page 379 has no marker for 'INDEX' — starting at nearest following marker (page 398).

[16:00:09] [DEBUG]   [Segmenter] Page 397 has no marker for 'ABOUT THE AUTHOR' — starting at nearest following marker (page 398).

[16:00:09] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[16:00:09] [INFO]   [Segmenter] Layer 3: short-segment merge SKIPPED — explicit chapter selection active (each selected entry stays its own segment; V0.03 P0-4).

[16:00:09] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[16:00:09] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[16:00:09] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[16:00:09] [DEBUG]      Selected: ['9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS']

[16:00:09] [INFO]   📑 Filtered segments: kept 1 of 17

[16:00:09] [INFO] 📚 1 segment(s) detected | [77.5s]

[16:00:09] [DEBUG]   ✅ Seg 1/1: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DI' | 10,848 tokens | p.222–242

[16:00:09] [INFO] 🌐 Detected language: en

[16:00:09] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[16:00:09] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[16:00:09] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\markdown\chapters

[16:00:09] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[16:00:09] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\markdown\chapters

[16:00:09] [DEBUG]    [V17.5] Analysis file: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (4027 bytes)

[16:00:09] [INFO]   ⏱️ Summary phase starting | [77.8s]

[16:00:11] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[16:00:11] [INFO]   ⏭️ Chapter selection active (1 title(s)) — front-matter skip disabled (selected sections are always summarized).

[16:00:11] [INFO]   🛡️ Source grounding: Layer 8 (langextract verbatim) is DISABLED because backend='ollama' (local). Local models cannot produce char_intervals — this is by design (Decision #4). Layers 1-7 (semantic checks + judge appeal) remain active. To enable Layer 8: Settings → Grounding → backend = 'cloud'.

[16:00:11] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[16:00:11] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[16:00:11] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[16:00:11] [INFO]   🌡️ Pre-flight: idle GPU temp = 52°C

[16:00:11] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[16:00:11] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[16:00:11] [INFO]     ⏱️ V18.2.15 Per-chapter deadline: 480s (chapters exceeding this will be logged + marked failed)

[16:00:11] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[16:00:11] [DEBUG]   🎛️ Model profile: Default

[16:00:11] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[16:00:12] [INFO]   📝 Max output tokens: 32768 (context: 128000)

[16:00:12] [INFO]   🚀 V0.04 concept extraction: single_local mode (llama.cpp model = Ternary-Bonsai-2-27B-Instruct-Vision)

[16:00:12] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[16:00:12] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[16:00:12] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[16:00:12] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 4 concepts — ['Charles Simic', 'Libidinal Types', 'Social Functioning Any', 'Related Differences Some']

[16:00:12] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Bleuler', 'Kernberg', 'Zetzel', 'Cooper', 'Lazare']

[16:00:12] [DEBUG]     🎯 V15.2.0 #3 (section headings): 2 concepts — ['Histrionic And Schizotypal\nPersonality Disorders', 'Mixed Forms And Extrinsic Influences On\nSymptomatology']

[16:00:12] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 4 concepts — ['mixed forms', 'level of social functioning', 'sex-related differences', 'changes in symptomatology over the life span, and']

[16:00:12] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[16:00:12] [DEBUG]     🎯 V15.2.0: merged 25 concepts before source-grounding

[16:00:12] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 25 concepts grounded ✓

[16:00:12] [INFO]     🎯 V15.2.0: FINAL 25 concepts (cap 50)

[16:00:12] [DEBUG]   🎯 '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI…': 25 concepts extracted (V15.2.0 enhanced)

[16:00:12] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[16:00:12] [INFO]   📖 Chapter 1/1: '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE' (50656 chars)

[16:00:12] [INFO]   🎯 User selected: ['9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS']

[16:00:12] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ENABLED — each chapter (summary + DOCX) is saved the moment it completes; a crash/cancel never loses finished chapters.

[16:00:12] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[16:00:12] [INFO] 📚 Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS…

[16:00:12] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.19.1

[16:00:12] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[16:00:12] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3914 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[16:00:12] [INFO]     📊 V17.2: Prepended deterministic analysis (3914 chars) — citation recall 78%→100%

[16:00:12] [INFO]     🧭 V0.10 (P6): strategy=single_pass (src=10,845 tok / window=128,000 / output=32,768) — adaptive window 128,000 > 32,768: src 10,845 <= usable 94,020 (window - output 32,768 - margin 700 - overhead 512)

[16:00:12] [INFO]     ⚡ Using primary model: Ternary-Bonsai-2-27B-Instruct-Vision

[16:00:12] [DEBUG]     🎯 Injecting 25 concepts + 0 callouts into prompt

[16:00:12] [INFO]     📦 V0.4: master-summary architecture (default) — input 10845 tok, output cap 32768

[16:00:12] [INFO]     📦 V0.3 Call 1/3: Master Summary (comprehensive thorough)

[16:00:12] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:00:12] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=32768 streaming…

[16:01:05] [INFO]     ✅ V0.3 Call 1/3: master summary = 545 words, 4129 chars

[16:01:05] [INFO]     📦 V0.3 Call 2/3: Derive bullet points from master summary

[16:01:05] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:01:05] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2048 streaming…

[16:01:28] [INFO]     ✅ V0.3 Call 2/3: 19 bullets derived from master summary

[16:01:28] [INFO]     📦 V0.3 Call 3/3: Derive executive summary from master + bullets

[16:01:28] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:01:28] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1024 streaming…

[16:01:45] [INFO]     ✅ V0.3 Call 3/3: exec summary = 277 words

[16:01:45] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.30) via llm_provider.llamacpp…

[16:01:45] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.30 max=8192 streaming…

[16:04:43] [INFO]     📖 V0.5.7 source glossary (separate call) → C:\Users\Ali Assadi\Desktop\5.19.1\summaries\.glossaries\9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.glossary.md

[16:04:43] [DEBUG]     📝 Parsed: exec=2136 chars, bullets=19, thorough=4129 chars

[16:05:38] [INFO]     📊 Primary coverage: 100% | keywords: ['disorder']

[16:05:40] [DEBUG]     🔍 Coverage detail: 3/3 keywords found | missing: []

[16:05:40] [DEBUG]     💾 V18.20.1.2: primary checkpoint saved (19 bullets, 277 exec words, 545 thorough words) → .checkpoints/primary_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md

[16:05:41] [DEBUG]     🔍 Fact-check: all 19 bullets verified ✓

[16:05:41] [INFO]     📝 Additive sections missing — running followup call for distinctions + tensions…

[16:05:41] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:05:41] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=4096 streaming…

[16:06:30] [INFO]     ✅ Additive sections via followup call: key_distinctions=1902 chars, theoretical_tensions=1446 chars

[16:06:30] [DEBUG]     💾 V18.20.1.2: post-additive-sections checkpoint saved (19 bullets, 277 exec words, 545 thorough words, +key_distinctions, +theoretical_tensions) → .checkpoints/post-additive-sections_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.md

[16:06:30] [WARNING]     ⚠️ thorough_summary too short (545 words < 800 threshold) — requesting dedicated expansion…

[16:06:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[16:06:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[16:07:16] [INFO]     📖 Attempt 1/3: dedicated thorough = 436 words

[16:07:16] [DEBUG]     ⚠️ Attempt 1 empty/short — retrying with directive nudge after 3s

[16:07:19] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[16:07:19] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[16:07:51] [INFO]     📖 Attempt 2/3: dedicated thorough = 545 words

[16:07:51] [DEBUG]     ⚠️ Attempt 2 empty/short — retrying (attempt 3/3)

[16:07:51] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.35) via llm_provider.llamacpp…

[16:07:51] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.35 max=8192 streaming…

[16:08:24] [WARNING]   ⏱️⚠️ Deadline exceeded (492s > 480s) — skipping optional phase: dedicated thorough (attempt 4 length-directive)

[16:08:24] [WARNING]     ℹ️ All 4 thorough attempts returned < 800 words (best=545) — keeping best-effort result

[16:08:24] [DEBUG]     ℹ️ Dedicated thorough call returned 545 words (not longer than original 545) — keeping original

[16:08:24] [WARNING]   ⏱️⚠️ Deadline exceeded (492s > 480s) — skipping optional phase: dedicated bullet expansion

[16:08:24] [INFO]     ✅ Final coverage 100%

[16:08:24] [DEBUG]     📏 F1: exec=277w, thorough=545w (source=7133w; targets exec<=250w, thorough<=3210w)

[16:09:18] [DEBUG]     ✅ Phase 2.2: All bullets semantically grounded (≥0.50 similarity)

[16:09:18] [DEBUG]     📖 F3: Reading level — source: 15.5, summary: 19.8 (diff: -4.2)

[16:09:18] [INFO]     ℹ️ F3: Summary is 4.3 grade levels denser than source — expected for a compressed academic summary.

[16:09:20] [DEBUG]     📊 I2: Chapter difficulty 0.56/1.0 (grade 15.5, strategy: multi_sample)

[16:09:20] [DEBUG]     🔄 J2: 23 cross-section redundancy(ies) found (exec↔bullets: 8, bullets↔thorough: 14)

[16:09:20] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 6 markers)

[16:09:20] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[16:09:20] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[16:09:20] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared (delay disabled)

[16:09:54] [DEBUG]     📊 Batch coverage: 56/56 claims (2 batch encode calls via EmbeddingCache, was 2352 per-pair calls)

[16:09:54] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[16:09:55] [INFO]     📊 Judge: coverage=100% (56/56 claims), grounding=100% (19/19 bullets), hallucinations=0, deviations=0, L8=OFF(grounding_disabled) — ✅ PASS

[16:09:55] [INFO]   ℹ️ Summary has substantial content (exec=2136 chars, thorough=4126 chars) — Judge coverage check at 100% is likely a false positive for this source length. Auto-passing to preserve content.

[16:09:55] [DEBUG]   ♻️  Recovery pass: no bullets eligible for recovery (threshold 30%).

[16:09:55] [WARNING]   ⏱️⚠️ Deadline exceeded (583s > 480s) — skipping optional phase: scholar reflection

[16:09:55] [INFO]     ⏭️  Scholar reflection skipped (deadline exceeded)

[16:09:55] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[16:09:55] [WARNING]   ⏱️⚠️ Deadline exceeded (583s > 480s) — skipping optional phase: semantic dedup

[16:09:55] [INFO]     ⏭️  Semantic dedup skipped (deadline exceeded)

[16:09:55] [DEBUG]     🧹 V16.0.2 Bullet normalization: 19 bullets normalized

[16:09:55] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared (delay disabled)

[16:09:55] [WARNING]   ⏱️⚠️ Deadline exceeded (583s > 480s) — skipping optional phase: bullet consolidation

[16:09:55] [INFO]     ⏭️  Bullet consolidation skipped (deadline exceeded)

[16:09:55] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.19.1

[16:09:55] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[16:09:55] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3914 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[16:09:55] [INFO]     📊 V18.14 Bullets-only judge: ['Kernberg', 'Lesser', 'Kety', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Meehl', 'Halleck']/73 authors in bullets (19%) — MISSING from bullets: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']

[16:09:55] [WARNING]     📊 V18.14 Thorough-only judge: ['Kernberg', 'Lesser', 'Kety', 'Freud', 'Easser and Lesser', 'Bleuler', 'Rado', 'Spitzer', 'Easser', 'Wittels', 'Reich', 'Marmor', 'Meehl', 'Halleck']/73 authors in thorough (19%) — MISSING from thorough: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']

[16:09:55] [INFO]     🔍 V18.14.1: Batch gap-fill round 1: filling 8 missing authors: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']…

[16:09:55] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:09:55] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:10:11] [INFO]     ✅ V18.14.1: Batch gap-fill round 1 added 8/8 bullets

[16:10:11] [DEBUG]     📊 V18.20.3.7: round 1 telemetry (15.7s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[16:10:11] [DEBUG]     📊 V18.14.1: After round 1, 51 still missing from bullets: ['Abse', 'Siever', 'Kendler', 'Wolman', 'Lazare']…

[16:10:11] [INFO]     🔍 V18.14.1: Batch gap-fill round 2: filling 8 missing authors: ['Abse', 'Siever', 'Kendler', 'Wolman', 'Lazare']…

[16:10:11] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:10:11] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:10:25] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Hoch' (grounded in glossary context, not verbatim quote)

[16:10:25] [INFO]     ✅ V18.14.1: Batch gap-fill round 2 added 8/8 bullets

[16:10:25] [DEBUG]     📊 V18.20.3.7: round 2 telemetry (14.1s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=0, added=8

[16:10:25] [DEBUG]     📊 V18.14.1: After round 2, 39 still missing from bullets: ['Akiskal', 'Bergman', 'Lilienfeld', 'Robins', 'Rosenthal']…

[16:10:25] [INFO]     🔍 V18.14.1: Batch gap-fill round 3: filling 8 missing authors: ['Akiskal', 'Bergman', 'Lilienfeld', 'Robins', 'Rosenthal']…

[16:10:25] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:10:25] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:10:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akiskal is cited in the source as supporting the observation that hypo…

[16:10:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bergman is referenced regarding the prognosis of paranoid individuals,…

[16:10:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Robins et al. is cited as evidence for the literature on early antisoc…

[16:10:38] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Abraham’s early papers on the relationship between character traits an…

[16:10:38] [INFO]     ✅ V18.14.1: Batch gap-fill round 3 added 4/8 bullets

[16:10:38] [DEBUG]     📊 V18.20.3.7: round 3 telemetry (12.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=4, added=4

[16:10:38] [DEBUG]     📊 V18.14.1: After round 3, 34 still missing from bullets: ['Akiskal', 'Bergman', 'Robins', 'Abraham', 'Kretschmer']…

[16:10:38] [INFO]     🔍 V18.14.1: Batch gap-fill round 4: filling 8 missing authors: ['Akiskal', 'Bergman', 'Robins', 'Abraham', 'Kretschmer']…

[16:10:38] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:10:38] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:10:50] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akiskal is cited in the text as having made observations about hypoman…

[16:10:50] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bergman is referenced for noting that paranoid individuals may fare be…

[16:10:50] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Robins et al. are cited regarding the prevalence of narcissistic, anti…

[16:10:50] [INFO]     ✅ V18.14.1: Batch gap-fill round 4 added 5/8 bullets

[16:10:50] [DEBUG]     📊 V18.20.3.7: round 4 telemetry (11.9s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=3, added=5

[16:10:50] [INFO]     🔁 V18.20.3.7: 'Akiskal' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[16:10:50] [INFO]     🔁 V18.20.3.7: 'Bergman' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[16:10:50] [INFO]     🔁 V18.20.3.7: 'Robins' yielded no bullet for 2 consecutive rounds — switching to the mention-only prompt next round

[16:10:50] [DEBUG]     📊 V18.14.1: After round 4, 26 still missing from bullets: ['Akiskal', 'Bergman', 'Robins', 'Nanarello', 'Zilboorg']…

[16:10:50] [INFO]     🔍 V18.14.1: Batch gap-fill round 5: filling 8 missing authors: ['Akiskal', 'Bergman', 'Robins', 'Nanarello', 'Zilboorg']… (mention-only: ['Akiskal', 'Bergman', 'Robins'])

[16:10:50] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:10:50] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:11:04] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Akiskal (1984, 1986) is cited by the source as a parallel reference fo…

[16:11:04] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Bergman (1971, 1978) is referenced by the source to support the observ…

[16:11:04] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Robins et al. are cited by the source as part of a group of researcher…

[16:11:04] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Nanarello (1953) is listed among those who made significant contributi…

[16:11:04] [INFO]     🧽 V0.4.23: gap-fill filler floor — dropped citation-adjacency bullet: Frances (1980) is cited by the source as part of a group questioning w…

[16:11:04] [INFO]     ✅ V18.14.1: Batch gap-fill round 5 added 3/8 bullets

[16:11:04] [DEBUG]     📊 V18.20.3.7: round 5 telemetry (14.0s): response=8 bullet lines, dup=0, think-filtered=0, vetoed=0, filler=5, added=3

[16:11:04] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Robins' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[16:11:04] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Bergman' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[16:11:04] [WARNING]     ⏹️  V18.20.3.4: Giving up on 'Akiskal' — mention-only attempt also failed the attribution veto; no attribution-safe bullet exists for this author

[16:11:04] [DEBUG]     📊 V18.14.1: After round 5, 23 still missing from bullets: ['Akiskal', 'Bergman', 'Robins', 'Nanarello', 'Frances']…

[16:11:04] [INFO]     ✅ V18.14.1: Batch gap-fill complete — added 28 bullets across 5 round(s)

[16:11:04] [INFO]     ✨ V0.5.6 final-check: firing TARGETED round 4 for 25 glossary-grounded author(s) still missing after round 5: Akhtar and Thomson, Akhtar et al., Akiskal, Bergman, Bleiberg, Ekstein, Fairbair

[16:11:04] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:11:04] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=2000 streaming…

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Akhtar and Thomson' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Akhtar et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Akiskal' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Bergman' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Bleiberg' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Ekstein' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Fairbairn' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Frances' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Gorton and Akhtar' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Guntrip' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Hoch and Polatin' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Kohut and Wolf' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Nanarello' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Noble' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Reid' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rinsley' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Robins et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Rosenthal et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Siever and Gunderson' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Simic' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Snyder et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Spitzer et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Wender et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Widiger et al.' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 gap-fill: accepted bullet for 'Wolff and Chick' (grounded in glossary context, not verbatim quote)

[16:11:28] [INFO]     ✨ V0.5.6 final-check: round 4 added 25/25 glossary-grounded bullet(s)

[16:11:28] [INFO]     ✨ V0.5.6 final-check: 62/62 authors (100%) — full coverage achieved. Glossary: (none)

[16:11:28] [DEBUG]     📝 V18.2.18: Lists & Frameworks section skipped (set summarisation.inject_lists_section=true to enable)

[16:11:28] [INFO]     ✅ V18.15.9.1: Added 1 consolidated Characteristics bullet (all 5 items, verbatim from source) — not scattered

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 7-item runin_arabic list (7 item(s) were uncovered; all 7 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item runin_arabic list (2 item(s) were uncovered; all 5 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item runin_arabic list (2 item(s) were uncovered; all 3 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 5-item roman_lower_paren list (4 item(s) were uncovered; all 5 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (2 item(s) were uncovered; all 3 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item roman_lower_paren list (2 item(s) were uncovered; all 4 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item runin_roman list (2 item(s) were uncovered; all 3 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (3 item(s) were uncovered; all 8 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 4-item runin_arabic list (2 item(s) were uncovered; all 4 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 8-item runin_arabic list (3 item(s) were uncovered; all 8 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item roman_lower_paren list (2 item(s) were uncovered; all 3 now carried verbatim)

[16:11:28] [INFO]     ✅ V0.4.23: enumeration guarantee — added 1 consolidated bullet for a 3-item ordinal list (2 item(s) were uncovered; all 3 now carried verbatim)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 7 (sim=0.86 with bullet 2)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 24 (sim=0.99 with bullet 22)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 25 (sim=0.98 with bullet 22)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 29 (sim=0.92 with bullet 23)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 38 (sim=0.91 with bullet 37)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 44 (sim=0.87 with bullet 41)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 49 (sim=0.86 with bullet 48)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 56 (sim=0.89 with bullet 20)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 58 (sim=0.89 with bullet 33)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 69 (sim=0.85 with bullet 6)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 70 (sim=0.90 with bullet 65)

[16:11:29] [DEBUG]     🧹 Semantic dedup: removing bullet 71 (sim=0.89 with bullet 55)

[16:11:29] [INFO]     🛡️ V0.5.18 semantic-dedup veto: KEPT bullet 44 (sim-twin) — uniquely covers source author(s) Kallman absent from the rest of the summary

[16:11:29] [INFO]     🛡️ V0.5.18 semantic-dedup veto: KEPT bullet 71 (sim-twin) — uniquely covers source author(s) Widiger absent from the rest of the summary

[16:11:29] [INFO]     🧹 V18.20.3.2: Post-gap-fill semantic dedup: 86 → 76 bullets (removed 10 gap-fill/conclusion duplicates; 1.1s, non-skippable per V18.20.3.4)

[16:11:29] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\5.19.1

[16:11:29] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md']

[16:11:29] [DEBUG]     [V17.5] Using analysis: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS_analysis.md (3914 chars), segment: 001_9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS.md

[16:11:32] [INFO]     🛡️ V18.2.13 Post-checks: 9 fixed, 8 flagged (of 76 bullets + exec + thorough)

[16:11:32] [DEBUG]       [sentence_fusion/flag] bullet[21]: likely source-propagated fusion garble: 'selfdestructive' is in the source but is NOT a real English word; it starts with the conventionally-always-hyphenated English morpheme 'self' + lexicon word 'destructive' (the source's own missing-hyphen typo was transmitted verbatim to the summary — the LLM faithfully reproduced the source's garble instead of normalising to 'self-destructive').  |  stible, and less overtly selfdestructive.

[16:11:32] [DEBUG]       [parenthetical_promotion/flag] bullet[28]: V0.5.15: bullet for 'Hoch' flagged as parenthetical promotion BUT KEPT — the author is in the regex extract_citations (the deterministic source roster). The regex IS the grounding.  |  Hoch (1910) made significant contributions to the descriptio

[16:11:32] [DEBUG]       [attribution/flag] bullet[62]: bold-name attribution mismatch: '**Characteristics**: (1) mixed forms; (2) level of social fun…' has 48% similarity to the source's claim about this author (threshold 50% — the claim may be misrepresented  |  **Characteristics**: (1) mixed…

[16:11:32] [DEBUG]       [truncated/flag] bullet[70]: enumeration-guarantee bullet LOOKS truncated — EXEMPT from the truncation drop (V0.4.24): its items are verbatim source text, verifiable against the source; no postcheck may silently drop a guaranteed bullet  |  **Similar ideas voiced by Zilboorg (1941,** — 8 items from t

[16:11:32] [DEBUG]       [quote_verification/fix] bullet[3]: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   who are stable and sexually inhibited, and 

[16:11:32] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   personality (characterized by sexual seductiveness, preoedi

[16:11:32] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   concept (described by Bleuler as an introverted individual 

[16:11:32] [DEBUG]       [quote_verification/fix] key_distinctions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   category, which was created because psychoanalytic usage di

[16:11:32] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   theory vs. distinct entity theory: There is a major debate 

[16:11:32] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |   in DSM-III was merely a renaming of the older 

[16:11:32] [DEBUG]       [quote_verification/fix] theoretical_tensions: quoted span is not verbatim in the source — shipped as a paraphrase (quotation marks stripped) instead of a misquote  |  ) and the observation of patients with core schizophrenia sy

[16:11:32] [DEBUG]       [page_ref_injector/fix] key_distinctions: injecting page refs: added (p. ~X) to 5 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=222, end_page=242; ~ marks an ESTIMATED locator, not a verified one)  |  - Hysterical personality disorder vs. histrionic personality

[16:11:32] [DEBUG]       [page_ref_injector/fix] theoretical_tensions: injecting page refs: added (p. ~X) to 4 bullet(s) that lacked page citations (model ignored the MANDATORY prompt instruction; pages estimated from start_page=222, end_page=242; ~ marks an ESTIMATED locator, not a verified one)  |  - DSM-III "renaming theory vs. distinct entity theory: There

[16:11:32] [DEBUG]       [near_duplicate/flag] bullet[35]: near-duplicate KEPT — uniquely covers source author(s) Kretschmer absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kretschmer made significant contributions to the description

[16:11:32] [DEBUG]       [near_duplicate/flag] bullet[38]: near-duplicate KEPT — uniquely covers source author(s) Kallman absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Kallman made significant contributions to the description of

[16:11:32] [DEBUG]       [near_duplicate/flag] bullet[49]: near-duplicate KEPT — uniquely covers source author(s) Guntrip absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Guntrip (1969) provided psychoanalytic understanding of the 

[16:11:32] [DEBUG]       [near_duplicate/flag] bullet[60]: near-duplicate KEPT — uniquely covers source author(s) Widiger absent from the rest of the summary (the V0.5.17 author-coverage veto)  |  Widiger et al. (1988) contributed to the debate on whether h

[16:11:32] [WARNING]     🎯 V18.20.3.13 Thorough theorist floor: 14/73 authors in thorough — MISSING from thorough: ['Akhtar', 'Zetzel', 'Tupin', 'Gunderson', 'Blacker and Tupin']

[16:11:32] [WARNING]   ⏱️⚠️ Deadline exceeded (680s > 480s) — skipping optional phase: thorough theorist floor gap-fill

[16:11:32] [WARNING]     ⏱️⚠️ V0.20: Deadline exceeded but the thorough theorist floor gap-fill is NON-SKIPPABLE (the thorough is missing 59 of 73 theorists — coverage deficit is the V0.20 campaign target; timing is not). Running the targeted calls anyway.

[16:11:32] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:11:32] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[16:12:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The psychoanalytic survey of the histrionic continuum was further refi…" — its name(s) never co-occur with the claim's key phrases in the source

[16:12:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "This conceptual trajectory culminated in Blacker and Tupin’s (1977) de…" — its name(s) never co-occur with the claim's key phrases in the source

[16:12:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "These findings, along with the work of Kendler (1985), informed the DS…" — its name(s) never co-occur with the claim's key phrases in the source

[16:12:13] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Wolman’s contributions to the broader understanding of personality pat…" — its name(s) never co-occur with the claim's key phrases in the source

[16:12:13] [INFO]   ✨ V0.5.15: recovered 1 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[16:12:30] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:12:30] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[16:13:14] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the context of psychoanalytic interpretations of schizoid phenomena…" — its name(s) never co-occur with the claim's key phrases in the source

[16:13:14] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "The concept of "schizotypal" was further grounded in empirical work by…" — its name(s) never co-occur with the claim's key phrases in the source

[16:13:14] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In the schizotypal section, the chapter details the genetic and clinic…" — its name(s) never co-occur with the claim's key phrases in the source

[16:13:14] [INFO]   ✨ V0.5.15: recovered 4 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[16:13:37] [INFO]     🤖 Ternary-Bonsai-2-27B-Instruct-Vision (t=0.70) via llm_provider.llamacpp…

[16:13:37] [INFO]     🦙 llama.cpp (Ternary-Bonsai-2-27B-Instruct-Vision) t=0.70 max=1536 streaming…

[16:14:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "In response to this conceptual blurring, Fairbairn (1940) provided an …" — its name(s) never co-occur with the claim's key phrases in the source

[16:14:28] [WARNING]     🧹 V0.4.24: gap-fill sentence dropped (attribution-edge): "Simultaneously, the clinical observation of latent or borderline schiz…" — its name(s) never co-occur with the claim's key phrases in the source

[16:14:28] [INFO]   ✨ V0.5.15: recovered 1 gap-fill sentence(s) whose authors are in the regex extract_citations (the attribution-edge dropped them but the regex IS the grounding)

[16:14:50] [INFO]     ✅ V18.20.3.13 Thorough gap-fill: floor 14/73 → 39/73 (3 chunked call(s), ≤12 names each; 23 name(s) beyond the 3-call bound remain thorough-uncovered — carried by the bullets/recall floor)

[16:14:50] [INFO]     📏 V18.20.3.4: Deterministic recall floor (final set): theorists 68/73 in final bullets (missing: ['Singer', 'Kraepelin', 'Erikson', 'Gorton and Akhtar', 'Gunderson and Singer']); conclusion items 5/5; enumerated items (all lists, whole chapter) 74/74. This regex-measured floor is the honest coverage number — the LLM judge's claim-recall measures a different thing and overstates content recall for long sources.

[16:14:50] [WARNING]   ⏱️⚠️ V18.2.15 Chapter 1/1 exceeded deadline: 878s > 480s (heading='9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI') — possible model stall. Summary kept, but this chapter consumed 878s of the budget.

[16:14:50] [INFO] ✅ Chapter 1/1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI… complete

[16:14:50] [DEBUG] ELIXIR_PROGRESS {"done":1,"total":1,"bullets":76,"exec_chars":2136,"chapter_done":true}

[16:14:50] [DEBUG]   📊 Progress: 1/1 done | 76 bullets | 2,136 chars exec summary

[16:14:50] [INFO]   🛟 V18.20.3.0 incremental chapter checkpointing ACTIVE — each chapter is saved (md + docx) the moment it completes; crash-safe via C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\checkpoints

[16:14:50] [INFO]     ✨ V0.5.6 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 2 source author(s) NOT found in the summary (Blacker and Tupin, Gorton and Akhtar). Glossary: (none). Cross-ref: confirmed=56, llm_only=5, regex_only=17.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1990' (ce:1990) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1945' (ce:1945) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1970' (ce:1970) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1905' (ce:1905) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1909' (ce:1909) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1945' (ce:1945) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1977' (ce:1977) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1977' (ce:1977) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1990' (ce:1990) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_date_check/flag] deterministic date-check: source date '1977' (ce:1977) NOT found in summary — possible omission.

[16:14:50] [WARNING]     ✨ V0.5.1 verification: [verification_coverage/flag] coverage-targeting (glossary-grounded): 2 source author(s) NOT found in the summary (Blacker and Tupin, Gorton and Akhta

[16:14:50] [INFO] 📄 Building DOCX report…

[16:14:50] [INFO]   Adding chapter 1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…

[16:14:51] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\checkpoints\chapters\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_summary.docx

[16:14:51] [DEBUG]   🛟 Checkpoint saved: chapter 1/1 '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALI' → summaries/001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.19.1_20260928-155851-011587f0_summary.md + DOCX

[16:14:51] [INFO]   💾 Response cache: 0 hits / 0 misses (0% hit-rate), 149/1000 entries, 0 evictions

[16:14:51] [INFO]   🧮 Embedding cache: 63 hits / 21 misses (75% hit-rate), 5000 entries

[16:14:51] [DEBUG]   💾 Summary 1/1 already saved — leaving untouched: 001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.19.1_20260928-155851-011587f0_summary.md

[16:14:51] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries

[16:14:51] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[16:14:51] [INFO] 💎 Run-stamped copy → Broken Structures Salman Akhtar.summary_v0.5.19.1_20260928-155851-011587f0.summary.md

[16:14:51] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[16:14:51] [INFO]   ⏱️ DOCX phase starting | [959.3s]

[16:14:51] [INFO] 📄 Building DOCX report…

[16:14:51] [INFO]   Adding chapter 1: 9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…

[16:14:51] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[16:14:53] [DEBUG]   🧠 Embedding dedup: embedder ready (shared singleton, backend=OllamaEmbedBackend)

[16:14:55] [INFO]   🧹 Keypoints dedup: removed 2 duplicate(s) (76 → 74 keypoints)

[16:14:55] [DEBUG]   🗑️ 'Kallman made significant contributions to the description of...' (embedding sim > 0.85)

[16:14:55] [DEBUG]   🗑️ 'Widiger et al. (1988) contributed to the debate on whether h...' (embedding sim > 0.85)

[16:14:55] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[16:16:46] [INFO]   🎯 K1+Classification: 74 bullets — 19 core, 39 supporting, 16 additional

[16:16:46] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[16:16:47] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[16:16:47] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[16:16:47] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[16:16:47] [INFO]   📊 Citation graph: no citations found in the text.

[16:16:47] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[16:16:47] [SUCCESS] ✅ Conversion complete.

[16:16:58] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\logs\quality_report.json

[16:16:58] [INFO] 

[16:16:58] [INFO] ━━━ Thermal Safety Report ━━━

[16:16:58] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[16:16:58] [INFO]   Session duration: 16.8 min

[16:16:58] [INFO]   Thermal budget: 0.0/120 min above 70°C (0%) — ✅ within budget

[16:16:58] [INFO]   Cool-downs triggered: 0 (every 20 min, 3 min each)

[16:16:58] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[16:16:58] [INFO] 

[16:16:58] [INFO] ━━━ Elixir v0.5.19.1 Conversion Diagnostic Summary ━━━

[16:16:58] [INFO]   Book: Broken Structures Salman Akhtar

[16:16:58] [INFO]   Total pages: 397

[16:16:58] [INFO]   Pages processed: 21 (selection active — 21 of 397 pages)

[16:16:58] [INFO]   Segments: 1 (chapters: 1, chunks: 0)

[16:16:58] [INFO]   Summaries generated: 1

[16:16:58] [INFO]     Success: 1, Failed: 0, Total bullets: 76

[16:16:58] [INFO]     Coverage: 100%

[16:16:58] [INFO]     Recall floor (deterministic, final set): theorists 68/73 (93%), conclusion items 5/5 (100%)

[16:16:58] [INFO]   Warnings: 0

[16:16:58] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar

[16:16:58] [INFO]   Log file: C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\logs\Broken Structures Salman Akhtar_v0.5.19.1_20260928-155851-011587f0.conversion.log.md

[16:16:58] [INFO]   Diagnostic JSONL: None

[16:16:58] [INFO]   Summary files (3):

[16:16:58] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries\001_9_-_HISTRIONIC_AND_SCHIZOTYPAL_PERSONALITY_DISORDERS_v0.5.19.1_20260928-155851-011587f0_summary.md — generated-by v0.5.19.1 | run_id=20260928-155851-011587f0 | started=2026-09-28T16:00:11 | bullets=76

[16:16:58] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md — generated-by v0.5.19.1 | run_id=20260928-155851-011587f0 | started=2026-09-28T16:00:11 | bullets=76

[16:16:58] [INFO]     ✓ C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary_v0.5.19.1_20260928-155851-011587f0.summary.md — generated-by v0.5.19.1 | run_id=20260928-155851-011587f0 | started=2026-09-28T16:00:11 | bullets=76

[16:16:58] [INFO]   Models loaded at exit: (none — all unloaded)

[16:16:58] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[16:16:58] [DEBUG]   ⏭️ RAG indexing removed — app produces RAG-friendly output only

[16:16:58] [DEBUG]   ⏭️ Screenshots/graphs skipped (opt-in, disabled)

[16:16:58] [DEBUG]   [TOC-Range] Matched '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' → '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDE…' (p.222, score=1.00)

[16:16:58] [INFO]   📐 Visual-region cropper: scanning 21 page(s) for diagrams/charts/tables

[16:16:58] [INFO]   [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)

[16:16:58] [INFO]   📊 Figure extraction: scanning 21 pages with PyMuPDF...

[16:16:58] [INFO]   ✅ Extracted 0 figure(s) → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\images

[16:16:58] [INFO]   📊 Table extraction: scanning 21 pages with pdfplumber...

[16:17:03] [INFO]   ✅ Extracted 0 table(s) → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\images

[16:17:09] [INFO]   [pipeline] Layer A (vector clusters): +0 regions

[16:17:09] [INFO]   [pipeline] after de-dup: 0 regions

[16:17:09] [INFO]   📐 Visual-region cropper: 0 region(s) (none) → C:\Users\Ali Assadi\Desktop\5.19.1\Broken Structures Salman Akhtar\regions

[16:17:09] [INFO]   📚 Library: Added 'Broken Structures Salman Akhtar' (1 chapters, 74 keypoints)


---
Finished at: 2026-09-28T16:17:09.613784
