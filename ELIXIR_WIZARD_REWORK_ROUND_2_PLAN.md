# ELIXIR — Full Wizard Rework, Round 2
## Phase 1: The Implementation Plan — decisions locked, phases sequenced

**Session:** Wizard-rework session 2 (Phase 1 — planning).
**Inputs:** `ELIXIR_WIZARD_REWORK_ROUND_1_AUDIT.md` (the Phase-0 record,
commit `95a1e18`) + the owner's 21 decision answers + 2 new visual asks,
given in-session. Every technical claim below cites the audit (which
carries `file:line` evidence, re-verified this session — 17/17 spot
checks passed against `main` @ `65191d1`, V0.6.85).

**Standing rules:** `AGENTS.md` Rules 1-7 govern every phase
(content-agnostic fixes; evidence-first commits; net-green suite; zip +
GitHub Release per version; incremental push).

---

## 0. The decision register (owner-approved, session 2)

| # | Question | Decision |
|---|----------|----------|
| D1 | Step count | **Keep 10 steps**, each slimmed (3 cards, auto buttons, folded advanced) |
| D2 | Scanned-mode engine | **Never Tesseract** — always the dedicated, more accurate vision-OCR engine (vision-capable summarisation model → `primary_ocr_model` → OlmOCR → Qwen VL) |
| D3 | 3-mode switch | **New `ocr_mode` request field** (`digital` / `scanned` / `auto`); purge dead flags in the same pass |
| D4 | Profiles | **Retire entirely** — delete the Step-1 box AND `core/pipeline/profiles.py` |
| D5 | Page-group size | **Wire it to real behavior first**, then UI (Auto default + manual override) |
| D6 | Deprecated outputs | **Remove from wizard entirely**; backend generators stay |
| D7 | Essential outputs | Executive + thorough **locked on**; master "Generate summaries" switch stays the single off-switch |
| D8 | Studio categories | Audio · Learning · Knowledge · Documents · Reference |
| D9 | Emoji policy | **Professional icons on all controls**; emoji only where genuinely best (log lines) |
| D10 | Self-consistency | **Backend kept, default OFF**, honest copy; removed from wizard (Settings-level control) |
| D11 | Coverage threshold | **Make it 1:1 honest** — threshold 85 must deliver ≥ ~85% measured coverage (± small LLM-randomness tolerance), via a real regeneration loop |
| D12 | Summarization limits | **Single owner (Step 5)** + backend clamp as safety net + computed effective values shown |
| D13 | Token-budget slider | **Delete entirely** (doubly broken; presets force deprecated outputs) |
| D14 | Models step | **No auto-pick.** Fix per-backend listing (incl. LM Studio); manual picking; remember the user's picks via settings |
| D15 | Translation modes | Radio: "translate my selected outputs" (default) vs "choose manually"; + the two bug fixes |
| D16 | Harakat → TTS wiring | **Deferred** to the backlog (documented as manual-review output for now) |
| D17 | Segmentation | Auto default + advanced disclosure with honest strategy copy |
| D18 | Conservative drops | Remove from wizard; backend + quarantine panel stay |
| D19 | Academic rigor | Checkbox removed; source-driven auto-enable stays |
| D20 | Data-loss bugs | **Hotfix both as V0.6.86 immediately**, before any rework |
| D21 | Phasing | **7 phases, one per session** (below) |
| V1 | Step chips (new ask) | The dot-strip progress indicator is redesigned into **grouped stage chips** (professional, oriented to the current visual identity) |
| V2 | Wizard visual rework (new ask) | The whole wizard is restyled to the current visual identity (IBM Plex Sans, amber accent, card language, generous spacing) — applied phase-by-phase, shell first |

---

## 1. The phasing (7 phases + hotfix; each independently shippable)

Version ladder: ① `V0.6.86` (hotfix) → ② `V0.7.0` (the rework opens) →
③ `V0.7.1` → ④ `V0.7.2` → ⑤ `V0.7.3` → ⑥ `V0.7.4` → ⑦ `V0.7.5`.

| Phase | Version | Scope | Bugs closed |
|-------|---------|-------|-------------|
| ① Hotfix | V0.6.86 | B1 `list_ollama_models` + B5 translation wipe — small, surgical, fully tested | B1, B5 |
| ② Shell + Step 1 | V0.7.0 | Stage-chip header (V1), wizard chrome restyle (V2 shell), 3 document-mode cards, `ocr_mode` backend, dead-flag purge, profiles retirement | B2, B10 |
| ③ Steps 2-3 | V0.7.1 | Page-range prominence, TOC button promotion, page-group wiring (D5), OCR auto-first rework | B3 |
| ④ Step 4 | V0.7.2 | Essentials locked, 5 category groups, deprecated cull, emoji→icons, streaming removal, simplified/compact relocation | B8, B9 |
| ⑤ Step 5 | V0.7.3 | Per-backend model listing, preference persistence, single-owner limits + computed effective values (Step-7b duplicate group deleted here) | B6 |
| ⑥ Step 6 | V0.7.4 | Translation radio modes, skip affordance, model pickers live, VRAM fix, dead settings keys | B7 |
| ⑦ Steps 7-7b | V0.7.5 | Advanced disclosure (token limit Auto+manual, strategy copy, semantic toggle folded), rigor + conservative-drops removal, slider deletion, self-consistency relocation, coverage-honesty rework, fine-tune recommended-defaults button | B4 (by deletion) |

One phase per session, ending with a fresh `NEW_SESSION_PROMPT.md` for
the next. Each phase: VERSION bump + tag + push + GitHub Release + zip
(Rules 5-6; the phasing approval in this session authorizes the
per-phase releases).

---

## 2. Phase designs

### Phase ① — V0.6.86 hotfix: the two data-loss bugs (B1, B5)

**B1 — `controller.list_ollama_models()` does not exist.**
Evidence: `step6_translation.py:85`, `translation_page.py:151` (both
wrap it in `try/except` → empty combos); `wizard_view.py:949-959` then
writes `""` into `translation.harakat_model` / `judge_model`.

Fix (evidence-first, smallest change):
1. Add `Controller.list_ollama_models() -> list[str]` delegating to
   `utils/network.list_ollama_models(base_url=<from settings>, timeout=5)`
   (`utils/network.py:173` — the audited fix route). No new HTTP code.
2. Defensive guard in `_save_translation_settings`: never overwrite a
   non-empty `translation.harakat_model` / `translation.judge_model`
   setting with an empty string (the wipe path). Log a line when the
   guard fires.

**B5 — the wizard force-disables translation every run.**
Evidence: `translation_enabled: bool = False` (`shared.py:85`) +
`_save_translation_settings` writes it unconditionally
(`wizard_view.py:953`).

Fix: load-then-save round-trip — `_load_settings_into_state` also reads
`translation.enabled` (and the four sibling translation fields) from
settings at wizard open, so the save writes back what the user already
chose unless the step changed it. No more silent override.

**Tests (new):** pin `Controller.list_ollama_models` exists + returns a
list (mocked socket); pin the empty-string guard (settings with
`harakat_model="qwen2.5"` survives a wizard save with empty state
field); characterization test: wizard open→close with
`translation.enabled=true` in settings keeps it true. Offscreen render:
Step 6 combos populated from a stubbed controller.
**Release:** V0.6.86 per Rules 5-6.

---

### Phase ② — V0.7.0: the wizard shell + Step 1 (3 modes, `ocr_mode`)

**2a. The stage-chip header (V1).** Replaces the 42px dot strip
(`wizard_view.py:174-207` — `●` + 10px label per step, `━` separators).
The 10 steps group into 5 named stages:

```
┌────────────────────────────────────────────────────────────────────┐
│  SOURCE ○──○──○    OUTPUTS ○    MODELS ○──○    TUNING ○──○   REVIEW │
│  pdf · range · ocr              models · transl  adv · fine         │
└────────────────────────────────────────────────────────────────────┘
```

- **Chip anatomy:** each stage = a small-caps label (IBM Plex Sans
  SemiBold 11px) over a segmented track; one segment per step in that
  stage. States: *done* = filled amber segment + check glyph; *current*
  = filled + subtle emphasis ring; *future* = muted border segment.
  Stages separated by a thin connector (the user's
  `------ translation ------ fine-tuning` sketch).
- The current stage label takes the accent color; others muted. Hover
  tooltip lists that stage's steps. Below 780px width the sub-captions
  drop and chips compress to labels + segment counts.
- Implemented as a `StageBar` widget (new,
  `ui_qt/components/stage_bar.py`) — reusable, AST-pinnable, offscreen
  renderable; `wizard_view` consumes it. All 10 steps keep their
  identity (D1) — only the presentation groups them.

**2b. Wizard chrome restyle (V2 shell).** Apply the established
identity (per `theme.py`: IBM Plex Sans + JetBrains Mono, amber accent,
`palette()` tokens, the `StepHeader` numbered-badge pattern of
`ui_qt/components/step_header.py`):
- Every step gets the numbered `StepHeader` (badge + title + plain-word
  caption) — one visual grammar across all 10.
- Nav bar: Cancel (ghost) left; `‹ Back` (secondary) + `Next ›`
  (primary, amber) right; 40px+ targets; consistent 20px frame margins.
- The dialog frame, headers, and group boxes use the card language
  (rounded `QFrame` cards, `SPACE` tokens) instead of bare `QGroupBox`
  chrome.
- Per-step visual polish lands with each phase's functional rework
  (③-⑦); the *shell* (StageBar + nav + frame + step-header grammar)
  lands here so every later phase builds inside it.

**2c. Step 1 becomes 3 cards (D1-D3).** Six `TypeCard`s → three:

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  [artwork]  │ │  [artwork]  │ │  [artwork]  │
│   Digital   │ │   Scanned   │ │    Auto     │
│ (book icon) │ │(full-ocr art)│ │(mixed art) │
│ Text-based  │ │ Every page  │ │  RECOMMENDED│
│ PDF. Charts │ │ image-OCR'd │ │ I detect   │
│ & tables    │ │ with the   │ │ which pages │
│ extracted.  │ │ vision eng.│ │ need OCR.   │
└─────────────┘ └─────────────┘ └─────────────┘
```

- **Digital** (`assets/icons/normal_book.png`): today's pipeline +
  `extract_figure_text` + `extract_tables` ON (audit §W2: both real,
  currently opt-in and page-level-blind — honest copy says charts on
  text pages are extracted, not re-OCR'd).
- **Scanned** (`assets/icons/full_ocr.png`): all pages through the
  dedicated vision-OCR engine (D2). **Engine set for scanned mode:
  vision-capable summarisation model → `primary_ocr_model` → OlmOCR →
  Qwen VL. Tesseract, PaddleOCR, and the local-VLM fallback are
  excluded** from this mode's cascade (audit's cascade map,
  `service.py:747-1411`).
- **Auto** (`assets/icons/mixed.png`, "Recommended" badge, default):
  today's always-on page-level detection (`analyzer.py:52-160`) + the
  Step-1 detector suggestion banner (already real,
  `step1_pdf.py:144-250`).
- Copy is transcription-truthful (audit §6.1): Scanned promises
  *reading* the pages, not describing imagery.

**2d. The `ocr_mode` backend (D3).** New
`ConversionRequest.ocr_mode: str = "auto"` (`core/models/models.py`);
`extraction.py` branches on it:
- `scanned` → mark all pages for OCR, recommendation `LLM_OCR`, engine
  set per D2. This **supersedes** the academic-only
  `force_ocr_all_pages` branch (`extraction.py:472-490`, bug B2) —
  the old flag becomes a deprecated alias mapped to
  `ocr_mode="scanned"` for one release, then purged.
- `digital` → detection off; figure/table extraction on.
- `auto` → exactly today's behavior.
- **Dead-flag purge (same pass):** `auto_detect_scanned` (log-only,
  `settings_logger.py:119`), preset `content_filter.min_*` (hardcoded
  80/0.40 in the filter), `is_academic` from `to_ui_data` — per the
  audit's dead-code register. Settings-dialog preset applier unified
  with the wizard's (audit's split-brain applier note, §W2).

**2e. Profiles retirement (D4).** Delete the Step-1 box + 3 handlers +
`_refresh_profiles` (`step1_pdf.py:92-122`) and
`core/pipeline/profiles.py` + its tests. With 3 cards and no profiles
box, Step 1 fits its viewport (B10 closed; audit §0.10).

**Tests:** AST-pins for `ocr_mode` on the request + the extraction
branch; engine-set pin (scanned mode never constructs Tesseract/
Paddle); dead-flag grep-pins (no `auto_detect_scanned` readers);
StageBar offscreen render + state-transition sweep; Step-1 3-card grab
(VLM-verified both themes); profiles-module deletion reflected in the
suite (net green).

---

### Phase ③ — V0.7.1: Steps 2-3 (range, TOC, page groups, OCR auto)

**3a. Page range (W4).** The group grows into a card: 15px-ish labels,
larger spinboxes, live feedback line ("Pages 12-340 — 329 pages,
~estimated chapters detected: 14"), tooltips. Keep "Process all pages"
as the default with the range fields enabling on uncheck.

**3b. TOC detection (W4).** The `🔍 Detect chapters from TOC` secondary
button (`step2_range.py:87-108`) becomes a prominent card-level action:
icon (professional, per D9) + "Detect chapters from table of contents" +
caption "Most accurate — reads the book's own outline". Backend is
solid (audit §W4); pure UI promotion.

**3c. Page-group wiring (D5 — wire before UI).**
- Backend: `page_group_size` becomes the block size of a **page-group
  chunking** fallback — when TOC/heading/semantic segmentation fail,
  pages chunk into N-page blocks (paragraph boundaries respected
  within the block) instead of raw token-fixed chunks. AUTO computes N
  from measured page token density (target ≈ 4-6k tokens/block,
  clamped 4-25 pages); the manual value overrides. `chunk_by_page_groups`
  gets its first real reader.
- UI (Step 2, inside the segmentation card): "Processing blocks: **Auto
  (≈ 8 pages)**" with an advanced override spin, and honest copy
  ("used only when chapter structure can't be detected").

**3d. OCR step (W5, B3).** One primary choice + a collapsed advanced
disclosure:

```
  ◉ Automatic — recommended        (big radio, caption:
  │    "I scan every page and OCR only the ones that need it,
  │     with the best available engine.")
  ○ Manual control                  (opens the disclosure)
     └ Engine overrides: [vision model ▾] [OlmOCR ▾] [Qwen VL ▾]
        Figure & table text extraction  [on]
        Tables (camelot/tabula)         [on]
        PaddleOCR fallback              [off]
        OCR timeout                     [120 s ▾]   (floor-clamped, honest)
```

- **B3 fix:** `ocr_timeout` + `use_paddleocr` enter
  `_REQUEST_FIELD_MAP` so the wizard controls actually reach the
  backend; timeout items become 120/180/300 (the backend clamps ≥120 —
  audit §W5).
- Auto = `use_llm_ocr=True, force=False, paddle=False, figure/tables
  per mode defaults` (audit's honest auto copy).

**Tests:** request-map pins (timeout/paddle now round-trip);
page-group chunker unit tests (block sizing, boundary respect, AUTO
density math); segmentation-cascade pin (page-group sits before token
fallback); Step-2/3 offscreen grabs + VLM check.

---

### Phase ④ — V0.7.2: Step 4 outputs (essentials, categories, icons)

**4a. Essentials locked (D7).** Executive + thorough pre-checked and
**disabled**, caption "Always included — every other output builds on
these." The master "Generate summaries" switch stays above them as the
single off-switch (audit §W6: `generate_summaries=False` cleanly no-ops
all downstream).

**4b. Five category cards (D8, D6):**

```
  CORE (always on):  [✓] Executive summary   [✓] Thorough summary
  ┌ AUDIO ──────────┐ ┌ LEARNING ────────────┐ ┌ KNOWLEDGE ───────┐
  │ ☐ Podcast script │ │ ☐ Flashcards  ☐ Q&A  │ │ ☐ Obsidian KB    │
  │ ☐ TTS audio *    │ │ ☐ Study guide        │ │ ☐ Mind map       │
  └──────────────────┘ │ ☐ Glossary ☐ Packets │ └──────────────────┘
                       └──────────────────────┘
  ┌ DOCUMENTS ──────┐ ┌ REFERENCE ───────────┐
  │ ☐ DOCX  ☐ EPUB  │ │ ☐ Executive briefing │
  └──────────────────┘ │ ☐ Evidence map **   │
                       │ ☐ Compact summaries │
                       │ ☐ Simplified keypoints│
                       └──────────────────────┘
```

- The 5 deprecated outputs (social, patterns, cheatsheet, skill,
  quote_bank — `registry.py:261-412`) are **gone from the wizard** (D6);
  generators stay for old files.
- **W8 moves:** simplified keypoints + compact summaries relocate here
  (Learning-adjacent/Reference; both are independent gates — audit
  §W8). The streaming checkbox is **deleted** (dead code, audit §W8).
- * TTS label fixed (B9): "built from the executive briefing" (audit:
  `podcast_audio.py:108-131`). ** evidence map copy: "needs the
  langextract extra — falls back to a guidance page without it."
- Every checkbox gets a tooltip (none exist today — audit §W7).

**4c. Icons (D9).** All control-label emojis (10 on Step 4 + the
scattered ones through Steps 2-8, audit §W6 inventory) replaced with
professional SVG line-icons from `ui_qt/components/icons.py` (extend the
set where a glyph is missing). Emoji survive only in log lines.

**4d. Review + start-log completeness (B8).** Step 8's outputs line and
the start-log enumerate **all non-deprecated selected outputs**
(`step8_review.py:156-183`, `wizard_view.py:880-909`) — driven from the
registry so it can never drift again.

**Tests:** AST-pin the locked essentials (checkboxes disabled + checked
by construction); deprecated-absence pin (Step 4 builds no deprecated
checkbox); review/start-log driven-from-registry pin; full-Step-4
offscreen grab both themes; icon-set render check.

---

### Phase ⑤ — V0.7.3: Step 5 models (listing, memory, single-owner limits)

**5a. Per-backend listing (B6, D14 — no auto-pick).**
- Ollama → `/api/tags` (existing path); **LM Studio → its own base
  URL** `/v1/models` (today it silently lists Ollama's —
  `step5_models.py:413-427,452-458`); llama.cpp → `/v1/models` +
  served-model autodetect (existing mixin path).
- All listing stays on `SimpleWorker` (the established pattern).

**5b. Preference memory (D14).** The wizard pre-fills the
summarisation/OCR combos from settings (last-used), and saves the
selections on a successful run — "manual picking, auto-remembered."

**5c. Single-owner limits (D12) + computed honesty.**
- Step 5 keeps the only "Model context / Model output" inputs;
  **Step 7b's duplicate "Summarization limits" group is deleted in this
  phase** (its save-order overwrite — audit §W12 — must not survive the
  single-owner change).
- Under the inputs, a read-only computed line shows the *effective*
  values after the backend's clamps (VRAM ladder, ≥32768 context floor,
  2048/8192/16000 output by model class — `summarizer_init.py:538-674`):
  `Effective after model limits: 32,768 ctx / 16,000 out`.
- Defaults unified (audit §5 table): one default per field, one owner —
  coverage 85 everywhere (state/settings/request 0.85), token-limit per
  segment → Auto (see Phase ⑦), context/output → Auto with the computed
  line as truth.

**Tests:** LM-Studio listing pin (mocked HTTP per backend);
preference-persistence round-trip; Step-7b group absence pin; computed
effective-value unit tests mirroring the clamp ladder; offscreen grabs.

---

### Phase ⑥ — V0.7.4: Step 6 translation (modes, truth, VRAM)

**6a. Two selection modes (D15):**

```
  ☑ Translate outputs (optional — runs after conversion)
     Target language: [Farsi ▾]
     What to translate:
       ◉ The outputs I selected in step 4      (default)
       ○ Let me choose:  [chapter summaries ✓] [keypoints ✓] …
     Quality (advanced):
       Harakat model  [qwen2.5 ▾]   Judge model  [llama3.1 ▾]
```

- The master checkbox + "optional" caption makes skipability visible
  (audit §W10).
- Mode A derives `translation.outputs` from the Step-4 selection at
  start (new mapping layer; backend unchanged — translation is a
  settings-driven post-conversion phase, `controller.py:432-492`).
- Model combos live (B1 fixed in ①), defaults from settings.

**6b. Honesty fixes.** The `.harakat.md` output documented as a
manual-review file (D16 defers TTS wiring — backlog). Dead settings
keys purged (`translation.outputs.packets`,
`harakat_confident_only` — audit dead-code register).

**6c. VRAM truth (B7).** The conversion-start VRAM check passes the
real harakat/judge models, not `summarisation_model` standing in for
the translator (`wizard_view.py:662`).

**Tests:** mode-A derivation pin (Step-4 selection → translation
outputs mapping); skip-visibility render; VRAM call-args pin; dead-key
absence pin; offscreen grabs both themes.

---

### Phase ⑦ — V0.7.5: Steps 7-7b (advanced, fine-tune, coverage honesty)

**7a. Advanced disclosure (W11, D17-D19, D13).**
- **Token limit per segment: Auto (default) + manual** — manual enabled
  only when the TOKEN strategy is actually in play (it only feeds
  `TokenSegmenter` — audit §W11).
- **Strategy copy, honest:** AUTO cascade spelled out
  (chapters → TOC → fuzzy-TOC → headings → semantic → page-groups (③) →
  tokens → whole-document); semantic noted as "one extra AI call that
  samples the first ~3,500 tokens" (`semantic_segmenter.py:52-113`).
  The `enable_semantic` toggle folds into this disclosure, default on.
- **Academic rigor checkbox removed**; the source-driven auto-enable
  stays (audit §W11: label lied, mechanism is real).
- **Conservative drops removed from the wizard** (D18); backend +
  quarantine panel untouched.
- **Token-budget slider deleted** (D13/B4) — with it dies the dead
  Step-4 sync (`step7_advanced.py:206,211`) and the deprecated-output
  presets (`presets.py:192-215`).

**7b. Self-consistency relocation (D10).** Removed from the wizard;
backend kept; **default off**; a Settings → AI-quality control carries
truthful copy: "Ollama-only; ~3-4× cost; merges sample agreement
(union), not majority vote" (audit §W12). A log line fires when it's
requested on an unsupported provider (no more silent no-op). The
all-engines fix stays on the backlog.

**7c. Coverage honesty (D11 — the real rework).** Owner's requirement:
*threshold 85 must mean ≥ ~85% measured coverage, within a few points
of LLM randomness.* Today: keyword-overlap metric, no regeneration
loop, over-delivery target 1.0 dominates, floor `max(0.60, t−0.10)`
WARNING-only (audit §W12) — the owner observed 100% set → 80-85%
delivered.

Rework (content-agnostic, Rule 1):
1. **One target:** the user threshold is *the* target. Over-delivery
   domination removed (over-delivery becomes the tolerance band, or is
   deleted); the `t−0.10` floor goes.
2. **Close-the-loop:** measure (existing concept-coverage metric,
   `summary_validator.py:810-856`) → if below `target − 3` → targeted
   gap-fill reprompt on the *missing concepts* (existing gap-fill
   machinery + prompts) → re-measure → repeat up to 3 rounds
   (cost-bounded) → **honest terminal report**: "Coverage 87% — target
   met" or "Reached 83% after 3 attempts; remaining gaps: …".
3. **Truth in UI:** Step 7b's spin reports what it now really does
   ("regenerates until measured coverage reaches this level, ±3 for
   model randomness, max 3 rounds").
4. Deferred backlog: embedding-based recall metric (semantic, not
   keyword) if the keyword metric proves gameable.

**7d. Fine-tune recommended defaults (W12).** A "Use recommended
settings" button applies the post-rework audited defaults (the honest
ones: coverage loop on, self-consistency off, Auto limits) — the
precedent is the Step-1 detector banner pattern (audit §W12).

**Tests:** coverage-loop unit tests (below-target triggers gap-fill;
3-round bound; honest report strings; tolerance ±3); strategy-copy
AST-pins; slider/rigor/drops absence pins; self-consistency
default-off + provider-log pin; fine-tune defaults pin; offscreen
grabs + full-wizard functional sweep (all 10 steps, both themes) as
the campaign close-out.

---

## 3. Test + verification plan (per phase, repo patterns)

- **AST-pin tests** (the `test_v182046_p5_dialog_split.py` family):
  pin every new widget/field/branch and every deletion the phase makes.
- **Offscreen render harnesses** (the `scripts/wz_icons_check.py`
  pattern): per-phase step grabs at 740×540 and 820×600, both themes,
  VLM-verified; StageBar gets a dedicated state-transition render test.
- **Functional sweeps** (the `scripts/r4_functional.py` pattern, with
  the modal-recorder intercept): drive the full wizard path per phase;
  final phase runs the all-steps close-out sweep.
- **Round-trip pins:** every state field the phase touches is pinned
  through `to_ui_data → _REQUEST_FIELD_MAP → ConversionRequest` (the
  audit's dead-control lesson — §1).
- **Net green:** full suite + `ruff` at every commit (Rule 3); golden
  fixtures re-frozen only if prompt content changes (only ⑦c touches
  prompts — gap-fill goldens re-freeze + eval re-baseline there).

## 4. Risk register

| Risk | Phases | Mitigation |
|------|--------|------------|
| Save-order overwrites (the 7b-wins pattern) recur | ⑤⑦ | Single-owner rule enforced by round-trip pins; delete the loser writer in the same phase |
| Dead-flag purge breaks hidden consumers | ② | Pre-purge grep sweep per flag (the audit's method); pins assert zero readers |
| New `ocr_mode` misses a call path | ② | Branch-pin tests for all 3 modes + deprecated-alias mapping for one release |
| Review/start-log drift again | ④⑦ | Registry-driven enumeration (B8 fix is structural, not enumerative) |
| Coverage loop cost blowup | ⑦ | 3-round bound + per-round token accounting in the log; loop OFF-able via the existing settings |
| Visual regressions on min-size / dark theme | ②-⑦ | Offscreen grabs at 740×540 both themes are a per-phase gate |
| Suite churn from deletions (profiles, slider, 7b group) | ②④⑤⑦ | Delete tests with their modules in-commit; net-green gate |
| Content-agnostic rule (Rule 1) | ⑦ especially | Coverage loop + gap-fill targets come from runtime analysis only; the deny-list tests run every commit |

## 5. Deferred backlog (recorded, not scheduled)

1. Harakat → TTS/podcast wiring (D16).
2. Self-consistency on all engines + true majority voting (D10 follow-up).
3. VL image-*description* pass for Scanned mode (audit §6.1).
4. Embedding-based coverage recall metric (⑦c stretch).
5. B3 bullet-voting exposure decision (default-off path exists).

---

*Plan complete. Phase ① (V0.6.86 hotfix) executes next session per
`NEW_SESSION_PROMPT.md`. No code was modified in this planning session
beyond documentation.*
