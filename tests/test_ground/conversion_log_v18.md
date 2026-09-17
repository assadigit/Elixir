# Conversion Log: Broken Structures Salman Akhtar

Started at: 2026-08-17T17:46:39.283024

---

[17:46:39] [SUCCESS] 🚀 Starting conversion…

[17:47:06] [DEBUG]   ✅ Pre-flight dependency check passed

[17:47:06] [INFO] ━━━━━━━━━━━ Conversion Settings ━━━━━━━━━━━

[17:47:06] [INFO]   Input file: Broken Structures Salman Akhtar.pdf

[17:47:06] [INFO]   Input path (full): C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar.pdf

[17:47:06] [INFO]   Output dir: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar

[17:47:06] [INFO]   Source type: normal_book

[17:47:06] [INFO]   App version: 18.0

[17:47:06] [INFO]   Python: 3.12.9 on Windows-10-10.0.19045-SP0

[17:47:06] [INFO]   PyTorch: 2.13.0+cu126, CUDA available: True

[17:47:06] [INFO]   GPU: NVIDIA GeForce RTX 3060, 12.0 GB total VRAM

[17:47:06] [INFO]   Ollama reachable (localhost:11434): True

[17:47:06] [INFO]   Provider: ollama

[17:47:06] [INFO] ━━━ VRAM Budget (by phase — peak is max, not sum) ━━━

[17:47:06] [INFO]   [Phase 1 (Extraction)]

[17:47:06] [INFO]     OCR: OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest (~6.4 GB)

[17:47:06] [INFO]   [Phase 2 (Summarization)]

[17:47:06] [INFO]     Summarization: Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (~20.2 GB)

[17:47:06] [INFO]   ────────────────────────────────────────

[17:47:06] [INFO]   Peak (max across phases): 20.2 GB / 12.0 GB available

[17:47:06] [INFO]   ❌ OVERBUDGET: Peak VRAM 20.2 GB exceeds available 12.0 GB. Reduce max_workers to 1, use a smaller model, or disable some features.

[17:47:06] [INFO] ━━━━━━━━━━━━━━━━━━━━

[17:47:06] [INFO]   LLM OCR: True, Force OCR all: False

[17:47:06] [INFO]   Auto-detect scanned: True

[17:47:06] [INFO]   Primary OCR model: OlmOCR-2-7B-1025-Q4_K_L-bartowski-allenai:latest

[17:47:06] [INFO]   OCR retries: 2, Image max size: 1200

[17:47:06] [INFO]   Page range: all

[17:47:06] [INFO]   Selected chapters: 1 chapter(s)

[17:47:06] [DEBUG]     → 1 - IDENTITY AND ITS ORIGINS

[17:47:06] [INFO]   Segmentation: auto, Token limit: 2000

[17:47:06] [INFO]   Semantic: True, Page group: 10

[17:47:06] [INFO]   Generate summaries: True

[17:47:06] [INFO]   Model: Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest

[17:47:06] [INFO]   Fast model: , Heavy model: (disabled)

[17:47:06] [INFO]   Workers (requested): 1, Temperature: 0.7

[17:47:06] [INFO]   Self-consistency: False, Coverage threshold: 85%

[17:47:06] [INFO]   📈 Over-delivery: ENABLED (floor 85% → target 100%)

[17:47:06] [DEBUG]   B3 voting: disabled (default since V15.1.1)

[17:47:06] [INFO]   Academic rigor: False

[17:47:06] [INFO]   Max context tokens: 32768

[17:47:06] [INFO]   Max output tokens: 8192

[17:47:06] [INFO]   Outputs: exec_summary, thorough_summary, keypoints, docx

[17:47:06] [INFO]   Translation: disabled

[17:47:06] [INFO]   Clean markdown: True, Token saver: False

[17:47:06] [INFO]   Content filter: True

[17:47:06] [INFO]   Extract tables: False, Math: False, Figures: False

[17:47:06] [INFO]   Layout analysis: False

[17:47:06] [INFO]   DOCX author: Elixir, TOC: True

[17:47:06] [INFO]   Output paths (V7.5 subfolders):

[17:47:06] [DEBUG]     markdown: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[17:47:06] [DEBUG]     summaries: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[17:47:06] [DEBUG]     keypoints: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.keypoints.md

[17:47:06] [DEBUG]     packets: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\packets

[17:47:06] [DEBUG]     podcast: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\podcast

[17:47:06] [DEBUG]     logs: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\logs\quality_report.json

[17:47:06] [INFO]   Resume mode: enabled — will skip done chapters

[17:47:06] [INFO]   📂 No previously-processed chapters found — all chapters will be summarized

[17:47:06] [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[17:47:06] [DEBUG]   💾 Disk space: 16.4 GB free

[17:47:06] [DEBUG]   📋 Checkpoint system initialized → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\.checkpoint.json

[17:48:11] [INFO] PDF analysis: hybrid — 31/397 pages are scanned

[17:48:11] [INFO]   Scanned page numbers: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[17:48:11] [INFO] 📋 31 scanned pages will be OCR'd: [1, 2, 3, 67, 68, 69, 106, 107, 108, 129]…

[17:48:12] [DEBUG] [TOC] PDF page labels available: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']…

[17:48:12] [INFO] [TOC] Using PDF outlines: 22 entries.

[17:48:12] [INFO] 📑 TOC: 22 entries found → will be used for chapter headings

[17:48:12] [DEBUG]   [TOC] Entries passed to segmenter: 22

[17:48:12] [DEBUG]   [TOC] - p.7: Table of Contents

[17:48:12] [DEBUG]   [TOC] - p.9: FOREWORD

[17:48:12] [DEBUG]   [TOC] - p.12: PREFACE AND ACKNOWLEDGMENTS

[17:48:12] [DEBUG]   [TOC] … and 19 more

[17:48:12] [INFO]   🎯 User selected 1 chapter(s):

[17:48:12] [INFO]     → '1 - IDENTITY AND ITS ORIGINS' (TOC page 15)

[17:48:12] [INFO]   📸 front_cover → front_cover.jpg

[17:48:12] [INFO]   📸 back_cover → back_cover.jpg

[17:48:12] [DEBUG]   [TOC-Range] Matched '1 - IDENTITY AND ITS ORIGINS…' → '1 - IDENTITY AND ITS ORIGINS…' (p.15, score=1.00)

[17:48:12] [INFO]   📸 Screenshotting 18 selected chapter page(s)...

[17:48:13] [DEBUG]   📸 p.15 → chapter_page_15.jpg

[17:48:13] [DEBUG]   📸 p.16 → chapter_page_16.jpg

[17:48:13] [DEBUG]   📸 p.17 → chapter_page_17.jpg

[17:48:13] [DEBUG]   📸 p.18 → chapter_page_18.jpg

[17:48:13] [DEBUG]   📸 p.19 → chapter_page_19.jpg

[17:48:13] [DEBUG]   📸 p.20 → chapter_page_20.jpg

[17:48:14] [DEBUG]   📸 p.21 → chapter_page_21.jpg

[17:48:14] [DEBUG]   📸 p.22 → chapter_page_22.jpg

[17:48:14] [DEBUG]   📸 p.23 → chapter_page_23.jpg

[17:48:14] [DEBUG]   📸 p.24 → chapter_page_24.jpg

[17:48:14] [DEBUG]   📸 p.25 → chapter_page_25.jpg

[17:48:14] [DEBUG]   📸 p.26 → chapter_page_26.jpg

[17:48:14] [DEBUG]   📸 p.27 → chapter_page_27.jpg

[17:48:15] [DEBUG]   📸 p.28 → chapter_page_28.jpg

[17:48:15] [DEBUG]   📸 p.29 → chapter_page_29.jpg

[17:48:15] [DEBUG]   📸 p.30 → chapter_page_30.jpg

[17:48:15] [DEBUG]   📸 p.31 → chapter_page_31.jpg

[17:48:15] [DEBUG]   📸 p.32 → chapter_page_32.jpg

[17:48:15] [DEBUG]   [TOC-Range] Matched '1 - IDENTITY AND ITS ORIGINS…' → '1 - IDENTITY AND ITS ORIGINS…' (p.15, score=1.00)

[17:48:15] [INFO]   📄 Derived 18 pages from TOC for 1 selected chapter(s) (skipping 379 unselected pages)

[17:48:15] [INFO]   📄 OCR pages filtered: 31 → 0 (only scanning pages within selected chapters)

[17:48:15] [DEBUG]   🔧 OCR timeout set to 120s (requested: 120s)

[17:48:15] [INFO]   🔍 Poppler auto-detected: C:\poppler-26.02.0\Library\bin

[17:48:15] [INFO]   ✅ markitdown ready for digital-page extraction

[17:48:15] [INFO] 📖 Opening PDF: Broken Structures Salman Akhtar.pdf

[17:48:15] [INFO]   📄 Processing 20/397 pages (chapter selection active — skipping 377 unselected pages)

[17:48:19] [INFO]   📄 20/397 pages processed (5%)

[17:48:26] [INFO]   📄 33/397 pages processed (8%)

[17:48:26] [SUCCESS] ✅ PDF processing done: 20/397 pages extracted

[17:48:26] [DEBUG]   🔧 Hyphenation repair: 16 line-break joins

[17:48:26] [DEBUG]   🧹 Tab cleanup: replaced 5977 tab character(s) with spaces

[17:48:26] [DEBUG]   🧹 Header/footer removal: 4 chars stripped

[17:48:26] [INFO]   🔍 Content auto-detection: Academic Paper / Scientific Article (75% confidence) — 4 citations, 1 publisher marker(s)

[17:48:26] [INFO]   ✅ Auto-switching to 'Academic Paper / Scientific Article' preset (confidence 75%)

[17:48:26] [DEBUG]     academic_paper: score=3.0 (4 citations, 1 publisher marker(s))

[17:48:26] [DEBUG]     normal_book: score=1.0 (default (no strong signals for other types))

[17:48:26] [INFO]   📐 Detected Academic Paper – enabling layout reorder.

[17:48:26] [DEBUG]   ✅ pdfplumber available for layout detection.

[17:48:26] [INFO]   📐 Reordering 20 pages for multi‑column layout...

[17:48:27] [DEBUG]   ℹ️ No words found on page 14 – skipping reorder.

[17:48:27] [DEBUG]   ℹ️ No words found on page 15 – skipping reorder.

[17:48:28] [DEBUG]   ℹ️ No words found on page 16 – skipping reorder.

[17:48:28] [DEBUG]   ℹ️ No words found on page 17 – skipping reorder.

[17:48:29] [DEBUG]   ℹ️ No words found on page 18 – skipping reorder.

[17:48:29] [DEBUG]   ℹ️ No words found on page 19 – skipping reorder.

[17:48:30] [DEBUG]   ℹ️ No words found on page 20 – skipping reorder.

[17:48:31] [DEBUG]   ℹ️ No words found on page 21 – skipping reorder.

[17:48:32] [DEBUG]   ℹ️ No words found on page 22 – skipping reorder.

[17:48:32] [DEBUG]   ℹ️ No words found on page 23 – skipping reorder.

[17:48:33] [DEBUG]   ℹ️ No words found on page 24 – skipping reorder.

[17:48:33] [DEBUG]   ℹ️ No words found on page 25 – skipping reorder.

[17:48:34] [DEBUG]   ℹ️ No words found on page 26 – skipping reorder.

[17:48:34] [DEBUG]   ℹ️ No words found on page 27 – skipping reorder.

[17:48:35] [DEBUG]   ℹ️ No words found on page 28 – skipping reorder.

[17:48:36] [DEBUG]   ℹ️ No words found on page 29 – skipping reorder.

[17:48:36] [DEBUG]   ℹ️ No words found on page 30 – skipping reorder.

[17:48:37] [DEBUG]   ℹ️ No words found on page 31 – skipping reorder.

[17:48:38] [DEBUG]   ℹ️ No words found on page 32 – skipping reorder.

[17:48:38] [DEBUG]   ℹ️ No words found on page 33 – skipping reorder.

[17:48:38] [INFO]   ✅ Layout reorder complete.

[17:50:10] [INFO] 📝 Raw markdown: 44,757 chars | [211.0s]

[17:50:10] [INFO]   [Converter] PDF has 22 native outline entries — skipping LLM heading labeler (outlines are authoritative). The 3-Layer chapter-level segmentation will use these directly.

[17:50:10] [DEBUG]   [HeadingSegmenter] Loaded 223 patterns from patterns.json

[17:50:10] [INFO]   [Segmenter] Layer 2: chapter-number filter — kept 16 chapter-level entries (from 22 total).

[17:50:10] [INFO] [Segmenter] Attempting chapter-level segmentation…

[17:50:10] [INFO]   [Segmenter] Created 16 chapter-level segments (no sub-section splitting, no merging needed).

[17:50:10] [INFO]   📄 Created gap segment: Gap (pages 1–8)

[17:50:10] [INFO] [Segmenter] Chapter-level segmentation produced 17 segments – using it. ✓

[17:50:10] [DEBUG]   🔍 Chapter selection: 1 titles selected.

[17:50:10] [DEBUG]      Selected: ['1 - IDENTITY AND ITS ORIGINS']

[17:50:10] [DEBUG]      ❌ No match for selected against 'Gap (pages 1–8)'

[17:50:10] [DEBUG]      ❌ No match for selected against 'FOREWORD'

[17:50:10] [DEBUG]      ❌ No match for selected against '3 - NARCISSISTIC PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '4 - BORDERLINE PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '5 - SCHIZOID PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '6 - PARANOID PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '7 - HYPOMANIC PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '8 - ANTISOCIAL PERSONALITY DISORDER'

[17:50:10] [DEBUG]      ❌ No match for selected against '9 - HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS'

[17:50:10] [DEBUG]      ❌ No match for selected against '10 - INITIAL EVALUATION AND EARLY TREATMENT DECISIONS'

[17:50:10] [DEBUG]      ❌ No match for selected against '11 - PSYCHOANALYTIC PSYCHOTHERAPY'

[17:50:10] [DEBUG]      ❌ No match for selected against '12 - SUMMARY, CONCLUSION, AND RECOMMENDATIONS'

[17:50:10] [DEBUG]      ❌ No match for selected against 'REFERENCES'

[17:50:10] [DEBUG]      ❌ No match for selected against 'INDEX'

[17:50:10] [DEBUG]      ❌ No match for selected against 'ABOUT THE AUTHOR'

[17:50:10] [DEBUG]      ✅ Match: '1 - IDENTITY AND ITS ORIGINS' ↔ '1 - IDENTITY AND ITS ORIGINS'

[17:50:10] [DEBUG]      ❌ No match for selected against '2 - THE SYNDROME OF IDENTITY DIFFUSION'

[17:50:10] [INFO]   📑 Filtered segments: kept 1 of 17

[17:50:10] [INFO] 📚 1 segment(s) detected | [211.1s]

[17:50:10] [DEBUG]   ✅ Seg 1/1: '1 - IDENTITY AND ITS ORIGINS' | 9,139 tokens | p.15–32

[17:50:10] [INFO] 🌐 Detected language: en

[17:50:10] [DEBUG]   📖 Book title: using PDF filename (Broken Structures Salman Akhtar)

[17:50:10] [INFO] 💾 Full markdown → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\markdown\Broken Structures Salman Akhtar.md

[17:50:10] [INFO] 📂 1 segment files → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\markdown\chapters

[17:50:10] [INFO] 📊 V17.2 Deterministic analysis: 1/1 segments analyzed (regex-based, 100% reliable)

[17:50:10] [DEBUG]    [V17.5] Analysis files written to: C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\markdown\chapters

[17:50:10] [DEBUG]    [V17.5] Analysis file: 001_1 - IDENTITY AND ITS ORIGINS_analysis.md (2235 bytes)

[17:50:10] [INFO]   ⏱️ Summary phase starting | [211.5s]

[17:50:10] [INFO]   🔥 S19: Pre-warming summarisation model 'Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest'…

[17:50:12] [INFO]   🧹 Content filter enabled – removing non‑content pages.

[17:50:12] [WARNING]   🛡️❌ Source grounding ENABLED in settings but backend='ollama' (local). Local models CANNOT produce char_intervals — langextract's verbatim-grounding signal. Layer 8 DISABLED (saves ~7.5 min/chapter; confirmed 0% grounding on local backend in V15.0.3). Layers 1-7 (semantic checks + judge appeal) remain active. To enable langextract: Settings → Grounding → backend = 'cloud' (Google langextract / Gemini API).

[17:50:12] [INFO]   🎯 GPU detected: NVIDIA GeForce RTX 3060

[17:50:12] [INFO]   🌡️ Thermal profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection) — warning 72°C, caution 76°C, critical 80°C (hotspot delta ~18°C)

[17:50:12] [WARNING]   🚨 EMERGENCY MODE: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection). If you see visual artifacts (red dots/lines on your monitor) during this conversion, STOP IMMEDIATELY — the VRAM is overheating.  The auto-pause will fire at 80°C core (est. 98°C VRAM).  If artifacts appear BELOW this threshold, the VRAM thermal pads need physical replacement — no software setting can fix that.

[17:50:13] [INFO]   🌡️ Pre-flight: idle GPU temp = 61°C

[17:50:13] [WARNING]   ⚠️ Pre-flight WARNING: GPU idle temp 61°C is above 55°C. The GPU is already warm before the conversion starts. Check that no other GPU-heavy apps are running, and consider improving case airflow before proceeding.

[17:50:13] [INFO]   🛡️ Thermal Safety System active. Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[17:50:13] [INFO]   🧊 Mandatory cool-downs: every 20 min, 3 min each. Thermal budget: 120 min above 70°C.

[17:50:13] [DEBUG]     🔧 HTTP timeout set to 600s (local mode)

[17:50:13] [INFO]   🔬 Academic Rigor auto-enabled (source_type=academic_paper).

[17:50:13] [INFO]   🔬 Academic Rigor mode enabled – structured JSON, self-review, citation guardrails (temperature stays at 0.7, NOT overridden to 0).

[17:50:13] [DEBUG]   ℹ️ Using user‑set context: 32768 tokens.

[17:50:13] [DEBUG]   🎛️ Model profile: Qwen3.5-9B (temp=0.6, max_bullets=30, dedup=60%)

[17:50:13] [INFO]   ℹ️ Heavy model fallback disabled (same as primary or empty).

[17:50:13] [INFO]   🚀 V16.0.9 concept extraction: single_local mode (heavy local model = Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest)

[17:50:13] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[17:50:13] [INFO]   📊 V17.4: Deterministic analysis found — skipping LLM concept extraction #5 + raising cap to 50 (saves ~3 min)

[17:50:13] [INFO]     🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)

[17:50:13] [DEBUG]     🎯 V15.2.0 #1 (intro+conclusion): 0 concepts — []

[17:50:13] [DEBUG]     🎯 V15.2.0 #2 (proper-noun theorists): 15 concepts — ['Erikson', 'Jacobson', 'Kernberg', 'Lichtenstein', 'Mahler']

[17:50:13] [DEBUG]     🎯 V15.2.0 #3 (section headings): 4 concepts — ['Identity And Its Origins', 'The Concept Of Identity', 'The Developmental Origins Of Personal\nIdentity', 'Conclusion']

[17:50:13] [DEBUG]     🎯 V15.2.0 #4 (conclusion lists): 5 concepts — ['a sustained feeling of selfsameness displaying roughly similar character traits to varied others', 'temporal continuity in the self-experience', 'genuineness and authenticity', 'a realistic body image', 'a sense of inner solidity and the associated capacity for peaceful solitude']

[17:50:13] [DEBUG]     ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)

[17:50:13] [DEBUG]     🎯 V15.2.0: merged 24 concepts before source-grounding

[17:50:13] [DEBUG]     🎯 V15.2.0 #6 (source-grounded): all 24 concepts grounded ✓

[17:50:13] [INFO]     🎯 V15.2.0: FINAL 24 concepts (cap 50)

[17:50:13] [DEBUG]   🎯 '1 - IDENTITY AND ITS ORIGINS…': 24 concepts extracted (V15.2.0 enhanced)

[17:50:13] [INFO] 📚 Summarising 1 chapter(s) with 1 worker(s)...

[17:50:13] [INFO]   📖 Chapter 1/1: '1 - IDENTITY AND ITS ORIGINS' (43049 chars)

[17:50:13] [INFO]   🎯 User selected: ['1 - IDENTITY AND ITS ORIGINS']

[17:50:13] [INFO] 📚 Summarising 1 chapters with 1 worker(s)...

[17:50:13] [INFO] 📚 Chapter 1/1: 1 - IDENTITY AND ITS ORIGINS…

[17:50:13] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v1827b

[17:50:13] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_1 - IDENTITY AND ITS ORIGINS_analysis.md']

[17:50:13] [DEBUG]     [V17.5] Using analysis: 001_1 - IDENTITY AND ITS ORIGINS_analysis.md (2165 chars), segment: 001_1 - IDENTITY AND ITS ORIGINS.md

[17:50:13] [INFO]     📊 V17.2: Prepended deterministic analysis (2165 chars) — citation recall 78%→100%

[17:50:13] [INFO]     ⚡ Using primary model: Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest

[17:50:13] [DEBUG]     🎯 Injecting 24 concepts + 0 callouts into prompt

[17:50:13] [INFO]     📑 Chapter is long (9,127 tokens) — trying section map-reduce (B4)…

[17:50:13] [DEBUG]     📑 B4: Section map-reduce — 3 sections detected

[17:50:13] [INFO]     🎯 Pre-flight: extracting must-have items…

[17:50:13] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.30) attempt 1/2…

[17:50:42] [DEBUG]   ✅ S19: Pre-warmed 'Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest'

[17:50:57] [WARNING]     ⚠️ Empty response attempt 1

[17:51:00] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.30) attempt 2/2…

[17:51:01] [WARNING]     ⚠️ Empty response attempt 2

[17:51:01] [DEBUG]     ⚠️ Empty/short response — retrying with nudge after 2s delay

[17:51:03] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.30) attempt 1/2…

[17:52:10] [INFO]     🎯 Pre-flight: identified 7 must-have items: ['Identity diffusion as sine qua non of borderline/narcissistic disorders (Jacobson, Kernberg)', "Erikson's definition: ego identity as self-sameness plus shared essential character with others", "Tausk introduced term; Freud used it technically only once (1926a B'nai B'rith address)"]…

[17:52:10] [INFO]     🎯 Pre-flight: 7 must-have items injected into B4 prompts

[17:52:10] [DEBUG]     🧹 VRAM recovery (B4-section-2) — cache cleared, waiting 120s…

[17:54:10] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[17:54:24] [WARNING]     ⚠️ Empty response attempt 1

[17:54:27] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[17:54:28] [WARNING]     ⚠️ Empty response attempt 2

[17:54:28] [DEBUG]     ⚠️ Empty/short response — retrying with nudge after 2s delay

[17:54:30] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:00:04] [DEBUG]     📋 Raw response (first 500 chars): '{\n  "executive_summary": [\n    {\n      "claim": "The chapter addresses identity diffusion as a central problem in borderline and narcissistic character disorders, citing Jacobson (1964) and Kernberg (1967) who regard identity disturbances as a sine qua non of these conditions.",\n      "supporting_text": "many analytic theoreticians (Jacobson 1964, Kernberg 1967) regard disturbances of identity as a sine qua non of borderline and narcissistic character disorders",\n      "source_reference": "Jacob'

[18:00:04] [DEBUG]     📑 B4 section 2/3: completed, 12 bullets, 2402 chars thorough

[18:00:04] [DEBUG]     🧹 VRAM recovery (B4-section-3) — cache cleared, waiting 120s…

[18:02:04] [DEBUG]     📑 B4 section 3/3: progressive context injected (200 chars)

[18:02:04] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:02:22] [WARNING]     ⚠️ Empty response attempt 1

[18:02:25] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:02:25] [WARNING]     ⚠️ Empty response attempt 2

[18:02:25] [DEBUG]     ⚠️ Empty/short response — retrying with nudge after 2s delay

[18:02:27] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:10:30] [DEBUG]     📋 Raw response (first 500 chars): '{\n  "executive_summary": [\n    {\n      "claim": "Tausk (1919) introduced the term identity into psychoanalytic literature.",\n      "supporting_text": "The term identity was introduced into the psychoanalytic literature by Tausk (1919), who examined how the child discovers his self and asserted that man must, throughout life, constantly find and experience himself anew.",\n      "source_reference": "Tausk (1919)"\n    },\n    {\n      "claim": "Freud used the term identity technically only once in a '

[18:10:30] [DEBUG]     📑 B4 section 3/3: completed, 25 bullets, 2333 chars thorough

[18:10:30] [INFO]     🔧 Dedup consolidation: 37 → 37 bullets (merged 0 duplicates)

[18:10:30] [DEBUG]     🧹 VRAM recovery (pre-thematic-synthesis) — cache cleared, waiting 10s…

[18:10:40] [INFO]     🔄 Thematic synthesis: reorganizing thorough summary by theme…

[18:10:40] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:12:55] [INFO]     🔄 Thematic synthesis: reorganized 4737 → 5740 chars thorough

[18:12:55] [INFO]     ✅ Section map-reduce succeeded

[18:12:55] [DEBUG]     🧹 VRAM recovery (post-B4-map-reduce) — cache cleared, waiting 10s…

[18:13:05] [DEBUG]     📝 Parsed: exec=1327 chars, bullets=37, thorough=5740 chars

[18:13:25] [INFO]     📊 Primary coverage: 85% | keywords: ['self', 'object', 'mother', 'self object', 'sense', 'identifications', 'formation']

[18:13:26] [DEBUG]     🔍 Coverage detail: 11/13 keywords found | missing: ['self object', 'identifications']

[18:13:26] [INFO]     📈 Coverage 85% < effective target 100% (over-deliver: floor 85% → target 100%) — applying 3-Tier Guarantee

[18:13:27] [DEBUG]     🔍 Fact-check: all 37 bullets verified ✓

[18:13:27] [INFO]     🔬 Running self‑review in BATCHES (37 bullets → 4 batches of 10)… [coverage 85%]

[18:13:27] [DEBUG]     🧹 VRAM recovery (pre-self-review) — cache cleared, waiting 20s…

[18:13:47] [INFO]     🔬 Batched self-review: 37 bullets → 4 batch(es) of 10

[18:13:47] [DEBUG]     🔬 Batch 1/4: reviewing claims 1-10…

[18:13:47] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:14:20] [WARNING]     ⚠️ Empty response attempt 1

[18:14:23] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:14:24] [WARNING]     ⚠️ Empty response attempt 2

[18:14:24] [WARNING]     ⚠️ Batch 1 returned empty — skipping

[18:14:24] [DEBUG]     🔬 Batch 2/4: reviewing claims 11-20…

[18:14:24] [DEBUG]     🧹 VRAM recovery (self-review-batch-2) — cache cleared, waiting 30s…

[18:14:54] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:15:29] [WARNING]     ⚠️ Empty response attempt 1

[18:15:32] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:15:34] [WARNING]     ⚠️ Empty response attempt 2

[18:15:34] [WARNING]     ⚠️ Batch 2 returned empty — skipping

[18:15:34] [DEBUG]     🔬 Batch 3/4: reviewing claims 21-30…

[18:15:34] [DEBUG]     🧹 VRAM recovery (self-review-batch-3) — cache cleared, waiting 30s…

[18:16:04] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:16:36] [WARNING]     ⚠️ Empty response attempt 1

[18:16:39] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:16:40] [WARNING]     ⚠️ Empty response attempt 2

[18:16:40] [WARNING]     ⚠️ Batch 3 returned empty — skipping

[18:16:40] [DEBUG]     🔬 Batch 4/4: reviewing claims 31-37…

[18:16:40] [DEBUG]     🧹 VRAM recovery (self-review-batch-4) — cache cleared, waiting 30s…

[18:17:10] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:17:43] [WARNING]     ⚠️ Empty response attempt 1

[18:17:46] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:17:47] [WARNING]     ⚠️ Empty response attempt 2

[18:17:47] [WARNING]     ⚠️ Batch 4 returned empty — skipping

[18:17:47] [WARNING]     ⚠️ Batched self-review produced no verdicts

[18:17:47] [WARNING]     ⚠️ Self‑review returned no response.

[18:17:47] [WARNING]     ⚠️ Final coverage 85% below 85% threshold

[18:17:47] [DEBUG]     📏 F1: exec=183w, thorough=746w

[18:17:55] [WARNING]     🗑️ Phase 2.2: Dropped 1 hallucinated bullet(s) (semantic similarity <0.50): ["The epigraph frames the speaker as a 'no"]…

[18:17:55] [DEBUG]     📖 F3: Reading level — source: 15.3, summary: 18.1 (diff: -2.8)

[18:17:55] [WARNING]     ⚠️ F3: Summary is HARDER to read than source!

[18:17:55] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.10) attempt 1/2…

[18:20:08] [DEBUG]     ℹ️ F3: Simplification rejected — too different (9% similar, expected >20%)

[18:20:08] [INFO]     ℹ️ F3: Simplification returned empty — keeping original (not retrying to save time)

[18:20:10] [DEBUG]     📊 I2: Chapter difficulty 0.56/1.0 (grade 15.3, strategy: multi_sample)

[18:20:10] [DEBUG]     🔄 J2: 11 cross-section redundancy(ies) found (exec↔bullets: 4, bullets↔thorough: 7)

[18:20:10] [DEBUG]     ✅ J3: Exec summary coherent (100/100, 6 markers)

[18:20:10] [DEBUG]     [V17.5] Analysis exists: 1 file(s) found — V17.4 skips ENABLED

[18:20:10] [INFO]     📊 V17.4: Deterministic analysis found — skipping old sequential gap-fill (V17.3 judge will handle it, saves ~20 min)

[18:20:10] [DEBUG]     🧹 VRAM recovery (pre-content-judge) — cache cleared, waiting 15s…

[18:20:40] [WARNING]   ⚠️ 🛡️ Source grounding is disabled in settings (grounding.enabled=False). Pipeline uses Layers 1-7 only.

[18:20:43] [INFO]     📊 Judge: coverage=72% (33/46 claims), grounding=61% (22/36 bullets), hallucinations=14, deviations=0, L8=OFF(grounding_disabled) — ❌ FAIL

[18:20:43] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:21:57] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:23:17] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:24:50] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:25:45] [DEBUG]     🔬 LLM grounding check: 4 call(s) for 36 bullets — 0 flagged ungrounded

[18:25:45] [DEBUG]   ℹ️ Source grounding DISABLED — LLM-as-judge grounding check passed all 36 bullets.

[18:25:45] [WARNING]     🔄 Judge: coverage 72% < 85% — gap-filling 13 uncovered claim(s)

[18:25:45] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.49) attempt 1/2…

[18:25:58] [WARNING]     ⚠️ Empty response attempt 1

[18:26:01] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.49) attempt 2/2…

[18:26:02] [WARNING]     ⚠️ Empty response attempt 2

[18:26:02] [INFO]   ℹ️ Summary has substantial content (exec=1327 chars, thorough=5736 chars) — Judge coverage check at 72% is likely a false positive for this source length. Auto-passing to preserve content.

[18:26:02] [INFO]   ♻️  Recovery pass: resurrected 1 quarantined bullet(s) with source overlap > 30%.

[18:26:02] [INFO]     ♻️  Recovery: re-inserted 1 quarantined bullet(s) with source overlap > 30%. Bullet count: 36 → 37.

[18:26:02] [INFO]     🎓 Running scholar reflection (gap analysis + gap-fill)…

[18:26:02] [DEBUG]     🎓 Theorist coverage check: 28 named author(s) found in source — verifying each is covered

[18:26:02] [DEBUG]     🧹 VRAM recovery (pre-scholar-reflection) — cache cleared, waiting 15s…

[18:26:17] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:32:38] [DEBUG]     🎓 Dropped gap-fill without quote: Klein (1948) and Loewenstein (1946) are cited as theoretical…

[18:32:38] [INFO]     🎓 Gap-fill: added 16 new bullet(s) from scholar reflection (source-grounded)

[18:32:38] [INFO]     🎓 Scholar reflection: identified 17 gap(s), filled 16 with new bullets

[18:32:38] [DEBUG]     🛡️ Anti-false-precision: no false-precision patterns found (0 rewrites)

[18:32:38] [DEBUG]     🧹 V16.0.2 Bullet normalization: 53 bullets normalized

[18:32:39] [DEBUG]     🧹 VRAM recovery (pre-bullet-consolidation) — cache cleared, waiting 30s…

[18:33:09] [INFO]     🔧 V16.0.2 Bullet consolidation: 53 bullets → LLM...

[18:33:09] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:33:25] [WARNING]     ⚠️ Empty response attempt 1

[18:33:28] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 2/2…

[18:33:28] [WARNING]     ⚠️ Empty response attempt 2

[18:33:28] [DEBUG]     ⚠️ Empty/short response — retrying with nudge after 2s delay

[18:33:30] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:39:34] [INFO]     ✅ Bullet consolidation: 53 → 53 bullets (merged 0)

[18:39:34] [DEBUG]     [V17.5] Searching for analysis files in: C:\Users\Ali Assadi\Desktop\v1827b

[18:39:34] [DEBUG]     [V17.5] Found 1 analysis file(s): ['001_1 - IDENTITY AND ITS ORIGINS_analysis.md']

[18:39:34] [DEBUG]     [V17.5] Using analysis: 001_1 - IDENTITY AND ITS ORIGINS_analysis.md (2165 chars), segment: 001_1 - IDENTITY AND ITS ORIGINS.md

[18:39:34] [INFO]     📊 V17.6 Deterministic judge: ['Erikson', 'Jacobson', 'Freud', 'Kernberg', 'Mahler', 'Winnicott', 'Blos', 'Lichtenstein', 'Greenacre', 'Fenichel', 'Hartmann', 'Tausk', 'Eissler', 'Fromm', 'Wheelis', 'Lynd', 'Lifton', 'Lasch', 'Kovel', 'Spiegel', 'Stoller', 'Galenson and Roiphe', 'Meyer', 'Loewald', 'Marx', 'Durkheim']/31 authors covered (84%) — MISSING: ['Loewenstein', 'Spitz', 'Klein', 'Searles', 'Khan']

[18:39:34] [INFO]     🔍 V17.8: Batch gap-filling 5 missing authors: ['Loewenstein', 'Spitz', 'Klein', 'Searles', 'Khan']

[18:39:34] [INFO]     🤖 Qwen3.8-27B-UD-IQ2_M_Unsloth-instruct:latest (t=0.70) attempt 1/2…

[18:40:29] [INFO]     ✅ V17.8: Batch gap-fill added 5/5 bullets (1 LLM call, was 5 calls)

[18:40:29] [INFO]     📝 V17.7: Injected Lists & Frameworks section (6 lists, all types)

[18:40:29] [INFO] ✅ Chapter 1/1: 1 - IDENTITY AND ITS ORIGINS… complete

[18:40:29] [DEBUG]   📊 Progress: 1/1 done | 58 bullets | 1,327 chars exec summary

[18:40:29] [DEBUG]   💾 Saved summary 1/1: 001_1_-_IDENTITY_AND_ITS_ORIGINS_summary.md

[18:40:29] [INFO] 📝 1 summaries → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\summaries

[18:40:29] [INFO] 📋 Book summary → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\summaries\Broken Structures Salman Akhtar.summary.md

[18:40:29] [DEBUG]   🧹 VRAM cache cleared (torch.cuda.empty_cache)

[18:40:29] [INFO]   ⏱️ DOCX phase starting | [3230.6s]

[18:40:29] [INFO] 📄 Building DOCX report…

[18:40:29] [INFO]   Adding chapter 1: 1 - IDENTITY AND ITS ORIGINS…

[18:40:30] [SUCCESS] ✅ DOCX saved to C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\Broken Structures Salman Akhtar.docx

[18:40:30] [DEBUG]   🧠 Embedding dedup: sentence-transformers loaded (shared singleton)

[18:40:31] [DEBUG]   📑 J1: Bullets reordered by topic clustering

[18:41:48] [INFO]   🎯 K1+Classification: 58 bullets — 12 core, 24 supporting, 22 additional

[18:41:48] [INFO]   📌 Keypoints MD → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[18:41:49] [INFO]   📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[18:41:49] [SUCCESS] 📌 Keypoints MD  → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.md

[18:41:49] [SUCCESS] 📌 Keypoints DOCX → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\keypoints\Broken Structures Salman Akhtar.Keypoints.docx

[18:41:49] [DEBUG]   ℹ️ No Output Studio outputs enabled (toggle them in Settings → Output Studio).

[18:41:49] [INFO]   📊 Citation graph: no citations found in the text.

[18:41:49] [SUCCESS] ✅ Conversion complete.

[18:41:58] [INFO]   📊 Quality report → C:\Users\Ali Assadi\Desktop\v1827b\Broken Structures Salman Akhtar\logs\quality_report.json

[18:41:58] [INFO] 

[18:41:58] [INFO] ━━━ Thermal Safety Report ━━━

[18:41:58] [INFO]   Profile: Zotac RTX 3060 Twin Edge OC (EMERGENCY — VRAM protection)

[18:41:58] [INFO]   Session duration: 51.8 min

