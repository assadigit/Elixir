# ELIXIR — Full Wizard Rework, Round 1
## Phase 0: The Audit — what the wizard is, and what its backend actually does

**Session:** Wizard-rework session 1 (Phase 0).
**Method:** five parallel investigation passes over the real tree —
(A) the wizard UI surface (all 10 step modules + orchestrator),
(B) the OCR / document-type backend,
(C) the outputs / summarisation backend,
(D) the models + translation backend,
(E) the segmentation / fine-tune backend. Every claim below carries a
`file:line` citation from the current `main` (post-`e25eac6`). The
headline claims were re-verified in-session by direct read.

**Companion deliverable already shipped this session:** the document-type
PNG icon swap (commit `e25eac6`, §W1).

---

## 0. Executive summary — the ten findings that shape the rework

1. **The wizard is already closer to a 3-mode document model than its 6
   cards suggest.** Page-level scan detection is unconditional and
   deterministic (`core/pdf/analyzer.py:69-160`); what the presets
   actually vary is a handful of flags — and several of those flags are
   **dead** (§W2).
2. **`force_ocr_all_pages` only works for academic papers.** The
   "Scanned" promise of the future mode is currently *not honored* for
   any other source type — the Full-OCR and Infographics presets are
   broken by design (`core/pipeline/conversion/extraction.py:472-490`,
   verified in-session). This must be fixed before the 3-mode UI ships.
3. **The wizard's translation step silently wipes the harakat model.**
   `controller.list_ollama_models()` does not exist
   (`ui_qt/views/wizard_steps/step6_translation.py:85`, verified
   in-session) → both model combos are always empty → `save_to_state`
   writes `""` into `translation.harakat_model`
   (`wizard_view.py:949-959`). A live data-loss bug.
4. **The "📡 Streaming LLM output" checkbox is dead code.** It is not in
   `_REQUEST_FIELD_MAP`, not on `ConversionRequest`, and its only
   consumer reads a ghost attribute that is always `False`
   (`core/summarisation/summarizer_init.py:163`, verified in-session).
   The underlying streaming transport works but is only test-reachable.
   **Verdict: remove.**
5. **`page_group_size` does nothing.** No consumer anywhere in `core/`
   — it is logged and ignored (`core/pipeline/conversion/settings_logger.py:149`).
   The user's ask to "explain the optimal page group size" needs a
   decision: wire it or remove it (§W4).
6. **Executive and thorough summaries are generated in one primary LLM
   call from the raw chapter text**, with a guaranteed dedicated-thorough
   backstop and a cheap exec-from-thorough derivation when exec comes
   back empty (`chapter_phases.py:1695-1763`, `summarizer.py:667-676`),
   and exec is *always* derived from the master summary in map-reduce
   mode (`summarizer_chunking.py:70-210`). **Locking them as essential
   is safe and well-founded** (§W6).
7. **The token-budget slider is doubly broken**: its Step-4 checkbox
   sync checks `hasattr(self, "step4")` on the *Step-7 widget* — never
   true (`step7_advanced.py:206,211`); and Step 4's `save_to_state` at
   conversion start *clobbers* the slider's state writes
   (`wizard_view.py:530-532`). It currently only persists settings.json
   values. Hiding it by default is safe (§W11).
8. **Self-consistency is real but provider-gated to Ollama** — silently
   a no-op on llama.cpp / LM Studio / cloud, which includes the default
   provider — and it is a union-merge, not a majority vote, at ~3-4×
   cost (`bullet_pipeline.py:987-1014`) (§W12).
9. **The coverage-threshold spinbox is weakly coupled**: keyword-overlap
   metric, no regeneration loop, B3 voting gated behind a
   default-off setting not present in the wizard, and the default-on
   over-delivery target (1.0) dominates the effective target
   (`chapter_phases.py:1478-1567`) (§W12).
10. **The "Summarization limits" group on Step 7b is redundant and
    largely overridden**: Step 5 writes the same two state fields,
    Step 7b overwrites them by save order, and the Summarizer then
    force-raises context to ≥32768 and forces output to
    16000/8192/2048 by model class anyway (`summarizer_init.py:538-674`)
    (§W12).

Plus one layout fact that the rework relieves for free: **Step 1 has no
scroll area but ~550px of content in a ~400-470px viewport**
(6 type cards ≈330px + profiles box ≈70px + picker ≈65px; the viewport
figure is documented at `step5_models.py:68-75`). Removing the profiles
box (§W3) and collapsing 6 cards to 3 (§W2) fixes the overflow.

---

## 1. The wizard today (the audited surface)

A modal `QDialog` `"Process Wizard — Step by Step Conversion"`
(740×540 minimum, 820×600 default; `wizard_view.py:160-163`), a fixed
42px progress strip of dot+label per step (`:174-207`), a 46px nav bar
(Cancel | Back | Next) (`:238-261`), and ten steps:

| # | Dot | Class / module | On-screen title | Scroll? |
|---|-----|----------------|-----------------|---------|
| 0 | PDF | `Step1Pdf` | Select your PDF and document type | **No** |
| 1 | Range | `Step2Range` | Page range and segmentation | No |
| 2 | OCR | `Step3Ocr` | OCR settings | No |
| 3 | Outputs | `Step4Outputs` | Select outputs to generate | Yes |
| 4 | Models | `Step5Models` | Model selection | Yes |
| 5 | Translation | `Step6Translation` | Translation (EN ↔ FA) | No |
| 6 | Advanced | `Step7Advanced` | Advanced settings | No |
| 7 | Fine-tune | `Step7bFineTune` | Fine-tuning | Yes |
| 8 | Review | `Step8Review` | Review all settings before starting | internal |
| 9 | Logs | `Step9Logs` | Conversion in progress | internal |

- **Only Step 1 validates** (PDF chosen + exists — `step1_pdf.py:391-396`);
  every other step is freely pass-through with defaults
  (`shared.py:247-249` is the only other `validate`). There is **no skip
  concept** anywhere.
- Navigation saves the current step then advances (`wizard_view.py:409-422`);
  Review's Edit-jump buttons skip `save_to_state` of the step being left
  (`:429-433`) — unsaved edits can be dropped.
- A complete **quick-mode implementation exists but is unwired**
  (`_apply_quick_defaults`, `wizard_view.py:493-524`; `_quick_mode`
  initialized `False` at `:157`, never read) — useful precedent for
  novice/advanced tiering.
- State is the `WizardState` dataclass (`shared.py:26-141`; full field
  inventory in Agent-A's table, reproduced in the working notes), and
  `_load_settings_into_state` (`wizard_view.py:291-343`) overwrites
  several defaults from settings.json at construction.
- The request is built declaratively: `to_ui_data()` (`shared.py:143-224`)
  → `_REQUEST_FIELD_MAP` (`controller.py:655-861`) →
  `ConversionRequest` (`core/models/models.py:224-397`). **Any state
  field not in the map is silently dropped** — this is how three of the
  wizard's controls turned out to be dead (§4).

---

## 2. Change-item audit (W1-W12, in the user's order)

### W1 — PNG icons for the document-type cards — **SHIPPED**

Extracted `Elixir-Document-Type-Modes.zip` (repo root, commit `44dad60`):
six 256×256 RGBA PNGs placed at `assets/icons/{preset_key}.png`
(Book-mode→`normal_book`, Academic-Paper-mode→`academic_paper`,
Journal-mode→`visual_catalogue`, Infographic-Slides-mode→
`infographics_slides`, Full-OCR-mode→`full_ocr`, Mixed-mode→`mixed`);
the six `.txt` placeholders deleted per their own instructions;
`assets/README.md` documents the set. **No code change needed** — the
V4.7.25 `pixmap_with_png_fallback` path already looked there
(`ui_qt/components/icons.py:311-375`; `type_card.py:173-181`). The
artwork is cream/paper-toned with dark outlines and reads on both
themes (VLM-verified on white and dark backgrounds).

**Verification** (`scripts/wz_icons_check.py`, real offscreen render):
6/6 PNGs load and are pixel-distinct from the SVG fallbacks; all six
TypeCards hold pixmaps; Step1Pdf renders the artwork with the selection
highlight intact; grab at 760×640 VLM-verified (6 cards, artwork
visible, no layout defects). The step *navigation* strip uses
dots+labels, not icons (`wizard_view.py:174-207`) — nothing else to
swap. Commit `e25eac6`, pushed.

### W2 — Concentrate document types into Digital / Scanned / Auto

**What the 6 presets actually differ by** (`ui_qt/settings/presets.py:13-116`):
`source_type` ∈ {normal_book, academic_paper, visual_catalogue},
`ocr.timeout`, `is_academic`, `ocr.force_ocr_all_pages`,
`ocr.auto_detect_scanned`, `content_filter.min_*`,
`advanced.extract_tables`, `advanced.extract_figure_text`,
`segmentation.*`. The wizard applies only a subset
(`step1_pdf.py:365-385`); the Settings dialog applies all of them
(`settings_dialog.py:247-257`) — a split-brain applier.

**Backend truth:**

- **Auto-detect scanned is unconditional.** `auto_detect_scanned` is
  carried on the request but **never read** — log-only
  (`core/pipeline/conversion/settings_logger.py:119`). Page detection
  always runs: text-layer heuristic (<30 chars & <2 words, or >30%
  garbage runs — `core/pdf/analyzer.py:52-67`), tiering ≥30% scanned →
  all-page LLM OCR, 1-29% → hybrid, 0 → no OCR (`analyzer.py:137-148`),
  plus a deterministic pre-scan that refines before the big model loads
  (`core/ocr/ocr_prescan.py:148-248`) and a ≥60%-scanned injection of
  the pseudo-type `scanned_pdf` (`extraction.py:270-282`).
- **`force_ocr_all_pages` is academic-only.** The all-pages-scanned
  branch requires `source_type == "academic_paper"` *and* the flag
  (`extraction.py:472-490`, verified in-session). For the Full-OCR
  preset (source_type=`normal_book`) and Infographics, **the flag does
  nothing** — a fully-digital PDF under "Full OCR" gets zero OCR.
- **OCR engine cascade (all real):** provider-agnostic vision OCR
  (first choice — probes whether the *summarisation model itself* is
  vision-capable via live API probe, else `primary_ocr_model`;
  `service.py:856-1032`) → OlmOCR (digital garble) → Qwen VL →
  PaddleOCR (settings-gated) → local VLM fallback (default off) →
  Tesseract (`service.py:747-1411`). UnlimitedOCR is an optional batch
  replacement (`core/ocr/unlimited_ocr.py`).
- **"Digital with OCR for charts/tables" exists but is opt-in and
  page-level-blind:** `extract_figure_text` (VisionFigureExtractor —
  vision model over embedded images, strict text-extraction prompt,
  `core/pdf/vision_figure_extractor.py:241-247`) and `extract_tables`
  (camelot/tabula, `postprocess.py:400-435`). A digital page with >50
  alnum chars of text is **not** otherwise OCR'd — the chart is skipped
  (`service.py:630-637`). The visual-region cropper (default ON) crops
  non-text regions and embeds them inline, harvesting nearby captions —
  but its Layer-B VLM returns bounding boxes, not descriptions
  (`core/pdf/vision_region_cropper.py:296-308`).
- **No image *description* pass exists anywhere in `core/`** — every
  "VL" touchpoint is transcription or detection. If "Scanned" mode is
  to promise VL *understanding* of imagery, that capability must be
  built (or the promise scoped to VL *transcription*).
- **`visual_catalogue` has no `ContentPreset`** — it falls back to the
  normal-book preset in `get_content_preset`
  (`core/llm/content_presets.py:252-257`), so dropping it as a distinct
  type loses nothing behaviorally.
- The deterministic content detector (`core/llm/content_detector.py:256-446`,
  no LLM) already detects 7 types and powers both the Step-1 suggestion
  banner and a pipeline auto-switch (`postprocess.py:236-293`) — the
  "Auto" mode has real machinery to stand on.

**Verdict / implication:** the 3-mode map is
Digital→`normal_book`-base + auto figure/table extraction,
Scanned→all-pages-OCR (needs the `force_ocr_all_pages` fix or a new
explicit `ocr_mode` field), Auto→today's always-on detection +
detector suggestion. Dead flags (`auto_detect_scanned`,
`content_filter.min_*`, preset `is_academic` drop) should be purged or
rewired in the same pass, and the applier unified.

### W3 — Remove the configuration-profiles box from Step 1

Current: `QGroupBox("Configuration profiles (optional)")` with combo +
Save…/Load/Delete (`step1_pdf.py:92-122`), backed by
`core/pipeline/profiles.py` (~/.elixir/profiles/*.json; save = full
`asdict(state)` minus per-book fields; load mirrors 9 key settings into
the controller). It consumes ~70px of a step that already overflows
(§0.10). Nothing else in the wizard reads profiles; the Settings dialog
does not expose them either.

**Implication:** removal from Step 1 is a pure UI deletion (the box,
the three handlers, `_refresh_profiles` call) plus a decision on the
`core/pipeline/profiles.py` module: keep it reachable elsewhere
(Settings dialog page) or retire it. The step-1 overflow is then fully
relieved by W2's 6→3 card collapse.

### W4 — Page range visibility, TOC button, page-group size

- **Page range group** (`step2_range.py:47-73`): "Process all pages"
  checkbox + From/To spinboxes (disabled while all-pages). **No
  tooltips**, no size hints — small controls in a quiet group. Making
  it bigger/visible is pure UI work.
- **"🔍 Detect chapters from TOC" button** (`step2_range.py:87-108`):
  `Secondary` objectName (outline style — transparent bg, 1px border,
  ~32px tall; `theme.py:761-768`), always enabled (V10.1.1), no
  explicit size hints. It opens the real `ChapterSelectorDialog`
  (500×500; outline → adaptive-LLM → clustering → 7 scored rule
  parsers, `core/pdf/toc_extractor.py`; resume badges, select-all/main-only
  helpers). Enlarging is pure UI work; the backend is solid.
- **`page_group_size` is vestigial** — no consumer in `core/`; logged
  and ignored (`settings_logger.py:149`; `chunk_by_page_groups` on the
  request likewise has zero core readers). "Explain the optimal page
  group size and keep it auto" therefore needs a **decision**: either
  (a) remove the control entirely (recommended — it does nothing), or
  (b) wire it into grouping behavior first. Auto+toggle as asked is
  implementable either way, but the explanation text cannot honestly
  describe an effect that does not exist.

### W5 — OCR settings: a primary auto option

Current Step 3 (`step3_ocr.py:40-74`): five checkboxes (LLM OCR on /
force all pages / PaddleOCR fallback / figure text / tables) + a
timeout combo. **No tooltips.** Two of these controls are dead from the
wizard: `ocr_timeout` and `use_paddleocr` are dropped by
`to_ui_data()` (never in `_REQUEST_FIELD_MAP`) — only their
settings.json twins (Settings dialog) work; and the backend clamps
timeout to ≥120s anyway (`service.py:144-148`), so the 30/60/90 combo
items are fiction. `force_ocr_all_pages` is academic-only (§W2).

**What "system auto-detect" already means today** (the honest copy for
the auto button): always-on page-level scan detection picks pages for
OCR; the engine cascade picks the best engine per page (vision model →
OlmOCR → Qwen → Paddle → VLM → Tesseract); the vision probe prefers
the summarisation model if it is vision-capable. Auto = defaults:
`use_llm_ocr=True, force=False, paddle=False, figure/table extraction
per W2-Digital`. The advanced panel would then expose engine
overrides.

### W6 — Essential outputs locked; emoji removal

- **Executive + thorough are safe to lock:** generated in the primary
  call from raw text (`prompt_builders.py:291-390`); dedicated thorough
  backstop when short (`chapter_phases.py:1695-1739`); exec derived
  *from* thorough when empty (`chapter_phases.py:1751-1763`;
  `summarizer.py:667-676`; derivative-call prompt at
  `prompt_assembly.py:203-252`) and always from master+bullets in
  map-reduce (`summarizer_chunking.py:70-210`). The `include_*` flags
  merely gate prompt sections and discard content
  (`chapter_phases.py:1393-1419`) — locking them on costs nothing
  structural. Note the master gate `generate_summaries=False` empties
  all summaries and no-ops every downstream output
  (`summarization.py:1392-1393`) — "summaries off" must remain the
  single top-level switch if the two essentials are locked.
- **Emoji inventory (labels/buttons only)** — 10 output-checkbox
  prefixes on Step 4: `📦 compact`, `📡 streaming`, `❓ qa`, `📖 glossary`,
  `🔧 patterns`, `📋 cheatsheet`, `🤖 skill`, `🗺️ evidence`, `📚 epub`,
  `💬 quote_bank` (`step4_outputs.py:88-186`); plus `🔍` TOC button
  (step2:87), `🏠/☁️/🔄/🔌/📝` through Step 5, `📝` in Step 6, `🦙`
  embed item (step7b:214), the Review section headers + `🚀` Start
  (step8:127-216), and Step 9's status prefixes. Removal is mechanical;
  the audit recommends keeping emojis out of *control labels* while log
  lines are out of scope.

### W7 — Output Studio categories

Today: two flat sections — "Core outputs" (8 checkboxes) and "Output
Studio" (17), no QGroupBox categorization, **no tooltips on any output
checkbox**. Backend reality per output (Agent C's table): podcast /
flashcards / qa / study_guide / glossary / packets / obsidian /
mindmap / docx / epub / briefing / social / patterns / cheatsheet /
skill / quote_bank / evidence_map / tts — all real generators; but
**five are flagged deprecated in the registry** (social, patterns,
cheatsheet, skill, quote_bank — `core/outputs/registry.py:261-412`),
**tts needs the `[tts]` stack and actually builds from the *briefing*
file, not the podcast script** (label is wrong —
`core/outputs/podcast_audio.py:108-131`), and **evidence_map needs the
langextract extra** (degrades to a guidance HTML — `evidence_map.py:120-138`).
Suggested category map for Phase 1 (backend-verified): **Audio**
(podcast script, tts), **Learning** (flashcards, qa, study guide,
glossary, packets), **Knowledge** (obsidian, mindmap), **Documents**
(docx, epub), **Reference** (briefing, evidence map, + deprecated set
pending a cull decision).

### W8 — Simplified keypoints / streaming / compact summaries

- **Simplified keypoints** (`simplified_keypoints_enabled`): real
  per-bullet jargon→plain rewrite, ~15s/bullet (cost tier "slow"),
  skipped for academic/philosophy presets
  (`core/summarisation/simplified_keypoints.py:333-346`). It is a
  post-summary add-on invoked from `summary_outputs.py:179-198` —
  **moves to Output Studio cleanly** (independent gate). Three
  divergent defaults exist today (wizard True / settings True /
  request False).
- **Streaming (`_streaming_enabled`): dead — remove.** Not in
  `_REQUEST_FIELD_MAP`, not on `ConversionRequest`, consumer reads a
  ghost attribute always `False` (verified in-session). The transport
  underneath (`OllamaProvider.complete_streaming`,
  `llm_dispatcher.py:107-120`) works but only tests reach it, and its
  "display" is DEBUG log lines, not a streaming pane. Removing the
  checkbox costs nothing backend-side.
- **Compact summaries** (`compact_summaries`): pure output-token cap
  (2048 clamp, `summarizer_init.py:596-606`) — no prompt change, no
  post-processing. **Moves to Output Studio cleanly.**

### W9 — Models step: auto-detect button

Current Step 5 (`step5_models.py`, 800 lines): arch combo (local/cloud),
backend combo (Ollama/llama.cpp/LM Studio), a **"🔄 Refresh models"**
button that lists models on a worker thread, summarisation + OCR model
combos, cloud preset/url/key + "🔌 Test connection", workers/temp/context/output
parameters. **"LM Studio" still lists Ollama models** — the LM Studio
URL is never used for discovery (`step5_models.py:413-427,452-458`).

**No "pick best model" logic exists anywhere.** But the probe stack to
build one is all real and reusable: Ollama `/api/tags` listing
(`utils/dependencies.py:122-138`), `/api/show` context-length probe +
6-rung `ModelRegistry` ladder (`core/llm/registry.py:209-245`),
llama.cpp `/v1/models` + two-stage connection test + served-model
auto-detect (`llamacpp_provider.py:779-977`, `llm_provider_impl.py:274-293`),
port auto-detect 8080→8000→9931 (`core/llm/local_fallback.py:71-83`),
vision-capability taxonomy (`core/llm/model_taxonomy.is_vision_model`),
and a tok/s CPU-fallback probe (`probe_llamacpp_generation`). The
single-model philosophy ("ONE model does every LLM task",
`step5_models.py:46-56`) means the auto button should find a
vision-capable model and fill provider+model+context+output in one
click. The VRAM budget check currently lives at conversion start, not
Step 5 (`wizard_view.py:638-738`), and mis-estimates the translator
model (`translation_model=s.summarisation_model` at `:662`).

### W10 — Translation step rework

- **Skip is invisible today**: the only affordance is the unchecked
  master checkbox (`step6_translation.py:41-44`); no tooltip, no
  "optional" copy. Sharp edge: the wizard **overwrites**
  `translation.enabled=False` on every run
  (`wizard_view.py:953`), silently disabling translation for users who
  enabled it in Settings.
- **Live bug (verified in-session):** `controller.list_ollama_models()`
  does not exist — both call sites (wizard step 6 at `:85`, Settings
  translation page at `:151`) catch the AttributeError and show empty
  combos; the wizard's save path then **wipes
  `translation.harakat_model` to `""`** (`wizard_view.py:949-959`).
  Fix: route through `utils/network.list_ollama_models` or add the
  controller method; guard the empty-string overwrite.
- **Harakat model: REAL backend.** Confidence-first Persian
  diacritization prompt, real LLM calls, output validation (length
  ratio, diacritic ratio, word preservation), fallback-model retry,
  disable-after-3-failures, markdown-aware
  (`core/translation/harakat.py:43-391`); VRAM-planned as a Phase-3
  resident (`core/vram_calculator.py:350-353`). Caveats: the
  `.harakat.md` output has **no downstream consumer** (podcast/TTS
  never reads it — the "feeds the Podcast Maker" claim is
  aspirational), and `translation.harakat_confident_only` is a dead
  setting.
- **Judge model: REAL backend.** SCORE/REASON faithfulness prompt at
  temperature 0, back-translation + embedding-cosine similarity, pass
  rule similarity ≥0.6 AND judge ≥0.7, one retry at temp−0.05,
  flagged-not-blocked outcomes, JSON+MD+HTML reports, per-chunk cache,
  auto-disable after 5 failures (`core/translation/validator.py`,
  `service.py:598-727`). The only decorative part is the wizard's
  unusable picker (the bug above).
- **Output selection today:** 11 checkboxes from
  `_TRANSLATABLE_OUTPUTS` (full_markdown, chapter_summaries,
  keypoints, simplified_keypoints, briefing, podcast, flashcards,
  obsidian, study_guide, social, mindmap); wizard state defaults 3 on;
  a 12th settings key `packets` is dead. Backend translates files by
  glob with a 30-minute freshness filter (`service.py:825-944`).
  **Translation is not part of `ConversionRequest`** — it is a
  settings-driven post-conversion phase (`controller.py:432-492`).
- **The user's two modes map cleanly:** "translate my desired outputs"
  = derive `translation.outputs` from the Step-4 selection at start
  time; "manually select" = today's checkbox list behind a radio
  choice. Backend needs no change; the mapping layer is new.

### W11 — Advanced panel

- **Token limit per segment:** consumed **only** by `TokenSegmenter`
  (`core/segmentation/token_segmenter.py:21`) — it does nothing unless
  the TOKEN strategy runs (explicit, or AUTO's stage-6 fallback).
  **Auto + advanced-manual is justified**; the manual field should
  only be relevant/enabled when token chunking is actually in play.
- **Strategy explanations:** the AUTO cascade is
  chapter-level → located-TOC → fuzzy-TOC → heading → semantic (LLM,
  gated by the toggle) → token → whole-document
  (`segmenter.py:1879-2087`). Heading = regex + keyword patterns
  (EN/FA); semantic = **one LLM call over the first ~3500 tokens
  asking for boundaries** (`semantic_segmenter.py:52-113`); token =
  fixed-size paragraph-boundary chunks. Current `_STRAT_DESC` copy is
  thin; honest copy must state semantic's cost and its 3500-token
  sample.
- **`enable_semantic` under Auto:** gates *only* AUTO stage 4
  (`segmenter.py:2051`); explicit SEMANTIC ignores it. Under Auto it
  matters only when outline/TOC/heading all fail — i.e., it decides
  whether a paid LLM call is attempted before the token fallback.
  **Recommendation:** default on (as today), fold into the advanced
  disclosure; it is needed but not as a top-level control.
- **Academic rigor:** NOT vestigial — JSON prompt+parser, always-on
  self-review, 16k output floor, +50% cost estimate
  (`prompt_builders.py:393-417`, `bullet_pipeline.py:1015-1077`,
  `llm_transport.py:53-54`, `token_estimator.py:189-190`) — but its
  label lies ("temperature=0" no longer happens —
  `summarizer_init.py:512-516`) and it **auto-enables itself** for
  academic papers on capable models (`summarizer_init.py:496-511`).
  **Removing the checkbox is safe**; keep the source-driven
  auto-enable.
- **Conservative drops:** fully wired and functional — gated filters
  re-append instead of drop, quarantine-logged, thinking/leakage
  always dropped (`filter_thinking.py:147-187`,
  `bullet_pipeline.py` passim), with a quarantine-viewer UI. Practical
  but niche (a debugging stance, not a quality setting). Removal from
  the wizard is low-risk; the backend and quarantine panel stay.
- **Token-budget slider:** default-off/display-off is safe — it is
  self-contained on Step 7 (`step7_advanced.py:128-155`) and already
  doubly broken (§0.7). Note its presets also force **deprecated**
  outputs on (Thorough = all 17, `presets.py:192-215`) — if it ever
  returns, it needs a category-aware rewrite.

### W12 — Fine-tune step: auto mode, self-consistency, coverage, limits

- **Auto-mode precedents:** the Step-1 detector banner (background
  detect → suggestion → apply; `step1_pdf.py:144-250`) is the best
  template; the budget slider's *lesson* (presets must write the state
  that builds the request, not just settings) is documented at
  `step7_advanced.py:160-214`.
- **Self-consistency:** real multi-sample (temps 0.1/0.3/0.5, 2-3 extra
  full chapter calls ≈ 3-4× cost) but (a) **silently no-op unless
  provider == "ollama"** (`bullet_pipeline.py:992`) — the default
  provider is llamacpp; (b) the "vote" is a **union-merge** with fuzzy
  dedup, exec/thorough picked by keyword coverage
  (`summarizer_chunking.py:274-327`) — no majority/agreement
  threshold. The separate B3 bullet-voting path exists but is
  default-off and absent from the wizard. If the checkbox stays, it
  must at minimum stop lying by omission (provider gating + cost).
- **Coverage threshold:** keyword/concept-overlap computation
  (`summary_validator.py:810-856`, no embeddings); below-threshold
  behavior = B3 voting (default-off, not in wizard) + the 3-tier
  guarantee that runs nearly regardless because over-delivery
  defaults on with target 1.0 (`chapter_phases.py:1478-1567`;
  `summarizer_init.py:413-415`); final acceptance floor
  `max(0.60, threshold−0.10)` with a WARNING only (`:1876-1917`).
  UI is int 0-100; request is float 0-1; defaults disagree (85/50/0.50
  across state/settings/request). The "reprompt trigger" label
  overstates. It *works*, weakly.
- **Summarization limits (the confusion):** Step 5's "Model context /
  Model output" spins and Step 7b's "Summarization limits" group write
  the **same two state fields**; Step 7b wins by save order
  (`wizard_view.py:530-532`); then the Summarizer force-raises context
  (VRAM ladder, floor 32768) and forces output by model class
  (2048/8192/16000) regardless (`summarizer_init.py:538-674`). **The
  group is redundant and advisory — collapse to a single owner**
  (Step 5, or an Auto) and let the backend clamp, with the clamps
  surfaced as computed text rather than a second input.

---

## 3. Live bug register (found during audit — exist on `main` today)

| # | Bug | Evidence | Suggested fix venue |
|---|-----|----------|---------------------|
| B1 | `controller.list_ollama_models()` does not exist; Step-6 + Settings translation combos always empty; wizard run wipes `translation.harakat_model` to `""` | `step6_translation.py:85`, `translation_page.py:151`, `wizard_view.py:949-959` (verified) | W10 rework or hotfix |
| B2 | `force_ocr_all_pages` honored only for academic papers — Full-OCR/Infographics presets are no-ops on digital PDFs | `extraction.py:472-490` (verified) | W2 rework |
| B3 | Wizard Step-3 `ocr_timeout` + `use_paddleocr` never reach the backend (dropped by `to_ui_data`) | `shared.py:143-224` vs `controller.py:655-861` | W5 rework |
| B4 | Token-budget slider's Step-4 sync is dead (`hasattr(self,"step4")` on the Step-7 widget) and Step-4 `save_to_state` clobbers the slider's state at start | `step7_advanced.py:206,211`; `wizard_view.py:530-532` | W11 rework (or delete slider) |
| B5 | Wizard overwrites `translation.enabled=False` every run (kills Settings-enabled translation) | `wizard_view.py:953` | W10 rework |
| B6 | Step-5 "LM Studio" backend lists Ollama models (URL never used for discovery) | `step5_models.py:413-427,452-458` | W9 rework |
| B7 | VRAM check passes the summarisation model as the translator model | `wizard_view.py:662` | W9/W10 |
| B8 | Review + start-log omit 9-10 of the newer outputs (packets/qa/glossary/patterns/cheatsheet/skill/evidence/epub/quote_bank/compact) | `step8_review.py:156-183`; `wizard_view.py:880-909` | any rework touching outputs |
| B9 | tts label says "requires podcast script" but the generator reads the *briefing* file | `step4_outputs.py:126-130` vs `podcast_audio.py:108-131` | W7 copy fix |
| B10 | Step-1 content overflows its viewport (no scroll area; ~550px content vs ~400-470px) | §0.10 | relieved by W2+W3 |

## 4. Dead / vestigial code register

| Item | Evidence | Disposition |
|------|----------|-------------|
| `_streaming_enabled` UI→backend | §W8 (verified) | remove checkbox (flag stays harmless) |
| `auto_detect_scanned` request flag | log-only | purge or make it the real "Auto" switch |
| `page_group_size` / `chunk_by_page_groups` | no core consumer | remove UI or wire |
| `content_filter.min_*` preset values | hardcoded 80/0.40 in filter | purge from presets |
| `ocr.retries` setting | never read | purge |
| `is_academic` in `to_ui_data` | not in request map; re-derived | purge from ui_data |
| `QwenOCREngine` standalone module | never imported by service | legacy, leave |
| Quick-mode (`_apply_quick_defaults`) | never called | precedent for tiering; revive or remove |
| `translation.outputs.packets` settings key | no backend map entry | purge |
| `harakat_confident_only` setting | never read | purge or wire |
| `.harakat.md` output | no downstream consumer | decide: wire to TTS or document as manual |
| KEYWORD segmentation enum | no UI, no branch | leave (harmless) |

## 5. Defaults-disagreement table (state vs settings vs request)

| Field | WizardState | settings.json | ConversionRequest |
|---|---|---|---|
| coverage_threshold | 85 (`shared.py:121`) | 50 | 0.50 (float) |
| token_limit_per_segment | 2000 | 2000 | 1200 |
| max_context_tokens | 32768 | 16000 | 131072 |
| max_output_tokens | 8192 (settings-load overrides to 16000) | 4096 | 4096 |
| simplified_keypoints | True | True | False |
| temperature | 1.0 | 0.6 | 0.6 |
| provider | — | llamacpp (migrated from ollama) | — |

These feed the "less cognitive load" goal directly: Phase 1 should
pick one default per field and one owner per field.

## 6. What Phase 1 must decide (the open questions)

1. **Scanned mode's VL promise** — transcription-only (today's real
   capability) vs building a description pass. Recommend: ship
   transcription-truthful copy now; description is a separate feature.
2. **Profiles** — retire `core/pipeline/profiles.py` or relocate to a
   Settings page.
3. **Page-group size** — remove (recommended) or wire.
4. **Deprecated outputs** (social/patterns/cheatsheet/skill/quote_bank)
   — cull from the wizard now, or keep in a "Legacy" category.
5. **Self-consistency** — keep with honest gating/cost copy, or fold
   into an "Advanced quality" disclosure; B3 voting's relationship to
   it.
6. **Coverage threshold** — keep as a soft floor with honest copy, or
   rework the trigger semantics.
7. **Summarization limits** — single owner (Step 5) + Auto, per §W12.
8. **Step architecture** — the 10-step linear flow vs a tiered
   novice/advanced split (the unwired quick-mode is precedent); the
   user's per-item asks are all compatible with keeping 10 steps, but
   the "less cognitive load" theme may justify fewer default-visible
   steps.

---

*Audit complete. No code was modified by the investigation; the only
commit from this session is the W1 icon swap (`e25eac6`). Phase 1
(implementation planning) builds on this document.*
