# Elixir — M0 Repository Reconnaissance Report

**Session:** 1 of the UI/UX redesign programme (M0 — reconnaissance only, no code changes)
**Date:** 2026-11-01
**Repo state inspected:** branch `main`, HEAD `11aa7ff` ("Add files via upload" — adds only `ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip`), working tree clean, VERSION `0.6.69`, tag `V0.6.69` present.
**Package read:** `ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip` (extracted read-only to a temp dir outside the repo; all 7 documents + 8 images inspected).

---

## 1. Repository overview

### Technology stack

| Item | Value (verified in code) |
|---|---|
| Language | Python 3.12 (`pyproject.toml` pins `>=3.12,<3.13`) |
| Qt binding | **PySide6 ≥ 6.6** (`pyproject.toml`, `main.py` dep check, all imports) |
| UI toolkit usage | Qt Widgets + QSS stylesheets + embedded-SVG icon rendering (`QSvgRenderer`) |
| Entry point | `main.py` → `ui_qt.app.run()` |
| Architecture | Controller pattern: `controller.py` (`Controller`) ↔ `core/pipeline` (conversion engine) ↔ `ui_qt` (PySide6 views) with a Qt signal bridge (`ui_qt/controller_bridge.py`) for thread-safe callbacks |
| Settings | `utils/settings.py` → `Settings` singleton, JSON at `~/.elixir/settings.json` (frozen: `%LOCALAPPDATA%\Elixir`) |
| Theme persistence | `~/.elixir/ui_theme.json` (already exists — theme persistence is legitimately available) |
| Window geometry | `~/.elixir/window_geometry.json` (`utils/geometry.py`, schema-stamped) |
| Packaging | PyInstaller onedir + Inno Setup via `build_installer.py`; selftest mode (`Elixir.exe --selftest`); bundled ffmpeg/poppler/tiktoken |
| Tests | pytest, 305 files / 8,638 tests collected (incl. hypothesis property tests); ruff + mypy; `make eval` / `make eval-check` golden quality gates |
| CI | `.github/` workflows (launch-gate probes per commit history) |

### Important directories

```
main.py                     # entry point (launcher guard, torch-before-Qt, bootstrap)
controller.py               # Controller — conversion threads, settings bridge
ui_qt/
  app.py                    # ElixirWindow (top bar + QTabWidget) + run()
  theme.py                  # ★ theme system: tokens, Palette, QSS, ThemeManager
  controller_bridge.py      # thread-safe Qt signal bridge
  components/               # icons.py (Lucide SVG), tool_card, llm_lights, …
  views/
    convert_view.py         # "Convert" tab — hosts ToolDashboard, routes tool clicks
    tool_dashboard.py       # ★ the current dashboard (4×3 tool-card grid)
    wizard_view.py          # ★ Full Conversion Wizard orchestrator (modal dialog)
    wizard_steps/           # 10 step modules + shared.py (WizardState/WizardStep)
    queue_view.py           # Queue tab (experimental destination)
    output_scanner_view.py  # Output Scanner tab (experimental destination)
    quarantine_view.py      # Bullet Audit tab (experimental destination)
    service_dialogs/        # BaseServiceDialog + 12 tool dialogs
    podcast_maker_view.py, validate_dialog.py, about_system_dialog.py, …
  settings/                 # SettingsDialog (VLC-style rail) + sections
core/                       # conversion pipeline, outputs registry, llm, ocr, tts, …
assets/                     # elixir.ico/png, fonts/ (Vazirmatn only), icons/ placeholders
tests/                      # 305 test files
```

### Startup flow (verified in `main.py` + `ui_qt/app.py::run`)

launcher guard → frozen-env setup → pycache purge → crash visibility → **torch imported before PySide6** (Windows DLL-shadowing fix) → dependency check → numpy ABI probe → excepthook → `Bootstrap` (settings migration, prompts, keyring) → `ui_qt.app.run()` → QApplication → single-instance lock → `theme_manager.apply(app)` → splash → `Controller()` → `ElixirWindow`.

> ⚠️ M1 note: the torch-before-PySide6 import order and the launcher guard are load-bearing; any theme work must not reorder startup imports.

---

## 2. Dashboard architecture (current state)

**There is no sidebar today.** The shell is: a 48 px **top bar** + a **north-positioned `QTabWidget`** with 5 tabs.

### Files / classes responsible

| Part | File | Class / members |
|---|---|---|
| Main window | `ui_qt/app.py` | `ElixirWindow(QMainWindow)` — `_build_top_bar()`, `_build_content()` |
| Top bar | `ui_qt/app.py` lines 114–200 | brand logo + "Elixir" H3 + subtitle "· PDF → Markdown + Summaries" + stretch + **LLM status lights** + **"✨ Process Wizard"** (Primary) + **"📚 Merge"** (Compact) + theme toggle + about + settings IconBtns |
| LLM lights | `ui_qt/components/llm_lights.py` | `build_status_lights()` → `LocalLLMLights` (Ollama / llama.cpp / LM Studio; width-adaptive: full→dots→mini; poll loop owned by `ElixirWindow._setup_llm_lights_monitoring()`, probe logic in `core/system/local_llm_monitor.py`) |
| Content | `ui_qt/app.py` lines 342–441 | `QTabWidget` tabs: **Convert** (rocket), **Queue** (list-checks), **Output Scanner** (scan), **Bullet Audit** (alert-triangle), **Hallucination Audit** (shield, inline launcher widget opening `HallucinationAuditDialog`) |
| Convert tab | `ui_qt/views/convert_view.py` | `ConvertView` — hosts `ToolDashboard`, `ProgressPanel`, hidden `LogViewer`; routes every tool click in `_on_tool_clicked()` |
| Tool grid | `ui_qt/views/tool_dashboard.py` | `ToolDashboard` + `TOOL_CARDS` (12 entries) + `ToolCard` (`ui_qt/components/tool_card.py`) |
| Theme toggle | `ui_qt/app.py::_toggle_theme` | `theme_manager.toggle()` then manual `refresh_theme()` on convert/queue/scanner/quarantine views + lights |

### Current dashboard content (the "Convert" tab)

`TOOL_CARDS` — a 4-row × 3-col `QGridLayout`, category label above each row, emoji icons, `ToolCard` min-height 140 (primary 160), radius 16/20 px:

| Row / category | Cards (key → label) |
|---|---|
| PROCESS | `full_conversion` **Full Conversion** (primary, "Complete 10-step wizard with all output types", 🚀) · `summarization` Summarization (Σ) · `pdf_to_markdown` Document → Markdown (📄) |
| TRANSFORM | `translation` Translation (🌐) · `markdown_styler` Markdown Styler (✨) · `packets_tool` Packets of Knowledge (📦) |
| EXTRACT | `ocr_service` OCR Service (🔍) · `pdf_docx_cutter` PDF/DOCX Cutter (✂️) · `image_extractor` Image Extractor (🖼️) |
| AUDIO | `tts_service` TTS Service (🔊) · `podcast_maker` Podcast Maker (🎙️) · `transcribe` Transcribe Service (📝) |

- **Wizard entry points (2):** top-bar "✨ Process Wizard" button AND the primary Full Conversion card → both open `WizardView` modal (convert_view also has `_open_wizard`; app.py `_open_wizard`).
- **Navigation behavior:** tab clicks; `_on_tab_changed` refreshes queue badge / quarantine auto-reload; window drag-and-drop accepts PDFs from any tab → Queue view; tab-switch highlight flashes amber `#D8AA78` (hardcoded).
- **Resizing:** `QScrollArea` wrappers (no horizontal scrollbar), geometry persisted with restore-validation + centering (`utils/geometry.py`); default 760×540, minimum 560×400, restore ceiling 1600×1000.

---

## 3. Complete feature inventory (verified against source)

### Primary workflow

| Feature (exact user-facing name) | Implementation | Access | Status |
|---|---|---|---|
| **Process Wizard / Full Conversion** ("✨ Process Wizard" btn; "Full Conversion" card) | `ui_qt/views/wizard_view.py::WizardView` + `wizard_steps/step1…step9` | Top-bar button; dashboard primary card | Functional (primary flow) |

### Secondary tools (all open modal `BaseServiceDialog` subclasses)

| Feature | Dialog class | File | Status |
|---|---|---|---|
| Summarization | `SummarizationServiceDialog` | `service_dialogs/dialogs/summarization_service_dialog.py` | Functional |
| Document → Markdown | `QuickConvertDialog` | `…/quick_convert_dialog.py` | Functional |
| Translation | `TranslationServiceDialog` | `…/translation_service_dialog.py` | Functional |
| Markdown Styler | `MarkdownStylerDialog` | `…/markdown_styler_dialog.py` | Functional |
| Packets of Knowledge | `PacketsToolDialog` | `…/packets_tool_dialog.py` | Functional |
| OCR Service | `OcrServiceDialog` | `…/ocr_service_dialog.py` | Functional |
| PDF/DOCX Cutter | `PdfDocxCutterDialog` | `…/pdf_docx_cutter_dialog.py` | Functional |
| Image Extractor | `ImageExtractorDialog` | `…/image_extractor_dialog.py` | Functional |
| TTS Service | `TtsServiceDialog` | `…/tts_service_dialog.py` | Functional |
| Transcribe Service | `TranscribeServiceDialog` (+ `live_transcribe.py`) | `…/transcribe_service_dialog.py` | Functional |
| Podcast Maker | `PodcastMakerView` inside a QDialog | `ui_qt/views/podcast_maker_view.py` | Functional (modal since V13.31.0) |

### Experimental destinations (approved to be hidden from primary nav)

| Feature (tab label) | View class | Registered at | Underlying code to preserve |
|---|---|---|---|
| Queue | `ui_qt/views/queue_view.py::QueueView` (+ `ui_qt/queue_parallel.py` cloud concurrency) | `app.py::_build_content` tab 2; DnD PDF routing; `convert_view` key `batch_queue` | whole view + `core` queue pipeline |
| Output Scanner | `ui_qt/views/output_scanner_view.py::OutputScannerView` | `app.py` tab 3; `convert_view` key `output_scanner` | view + `core/pipeline/output_scanner` |
| Bullet Audit | `ui_qt/views/quarantine_view.py::QuarantineView` | `app.py` tab 4 | view + `core/summarisation/quarantine` |
| Hallucination Audit | inline tab-5 widget → `HallucinationAuditDialog` | `app.py` tab 5 + `_open_hallucination_audit()`; `convert_view` key `hallucination_audit` (dialog also reachable from Packets output) | dialog + `core` audit services |

### Other surfaces

| Feature | Implementation | Access | Status |
|---|---|---|---|
| Merge (📚, multi-book summaries) | `app.py::_open_merge_dialog` → `core/pipeline/multi_pdf_merge.py` | Top-bar "Merge" button | Functional |
| Settings | `ui_qt/settings/settings_dialog.py::SettingsDialog` (rail: Presets / AI / OCR / Output + Podcast, Translation, TTS, Prompts, Dependencies pages) | Top-bar gear | Functional |
| About & System | `ui_qt/views/about_system_dialog.py` | Top-bar info button | Functional (dep checks, Ollama models, Tesseract/Poppler paths) |
| Theme toggle | `app.py::_toggle_theme` | Top-bar sun/moon | Functional (see §5 gaps) |
| Token cost estimate | `ui_qt/views/token_cost_dialog.py` | Auto-shown by wizard before conversion start | Functional |
| Chapter selector | `ui_qt/views/chapter_selector_dialog.py` | Wizard step 2 | Functional |
| Model download | `service_dialogs/model_download_dialog.py` | From model pickers | Functional |
| Validate (source-vs-summary checker) | `ui_qt/views/validate_dialog.py::ValidateDialog` | **NONE — `_open_validate()` has zero call sites (Tools menu removed V13.31.0). Orphaned UI, code intact** | Orphaned |
| Startup splash | `app.py::_StartupSplash` (hardcoded dark colors) | Automatic | Functional |
| Success sound | `ui_qt/components/sounds.py` | Conversion complete | Functional |

**Nothing was invented; every name above is the string that appears in the running UI.** Features that exist in code but have no current UI entry point: `ValidateDialog` (orphaned). No TTS/podcast "tabs" exist anymore (removed V13.31.0 — they are modals now).

---

## 4. Wizard architecture (Full Conversion — documented, NOT redesigned)

- **Container:** `WizardView(QDialog)`, modal, title "Process Wizard — Step by Step Conversion", min 740×540, default 820×600. Opened modally from two CTAs; `WA_DeleteOnClose`.
- **10 steps** (`_STEP_LABELS`): `PDF · Range · OCR · Outputs · Models · Translation · Advanced · Fine-tune · Review · Logs` — step classes in `ui_qt/views/wizard_steps/` (`Step1Pdf` … `Step9Logs`; "Fine-tune" is `Step7bFineTune`), one `QStackedWidget`, shared `WizardState` dataclass (`shared.py`) seeded from saved settings (`_load_settings_into_state`).
- **Progress indicator:** 42 px header with 10 dot+label pairs; completed=muted green, current=accent pill (inline styles).
- **Navigation:** Next validates `save_to_state()`+`validate()` (blocking `QMessageBox.warning` on failure); Back disabled at ends; step 9 (Logs) hides nav buttons; Review (step 8) exposes Edit buttons → `_jump_to_step(0..8)`; Cancel asks confirmation; Reset rebuilds all steps.
- **Input selection (step 1):** `QFileDialog` browse + drop, 6 document-type `TypeCard` presets (Book, Research Paper, Journal, Infographics & Slides, Full OCR, Mixed Document — `ui_qt/settings/presets.py`) with auto content-type detection.
- **Output selection (step 4):** **multiple output types per run** — 8 core checkboxes (per-chapter summaries, exec/thorough summary, keypoints, simplified keypoints, compact summaries, streaming, DOCX) + 17 Output Studio checkboxes mirroring `core/outputs/registry.OUTPUT_REGISTRY` (21 specs total; README says "19 types" — minor doc drift, code says 21).
- **Processing initiation:** Review → `_start_conversion()`: saves steps → re-validates step 1 → builds `ConversionRequest` via `controller.build_request_from_ui` → token-cost confirm modal → jumps to Logs step → installs owner-tagged controller callbacks ("wizard") → VRAM budget check (`_check_vram_budget`, policy abort) → hardware monitor (auto-pause) + elapsed timer → `controller.start_conversion(request)` on a background thread.
- **Results/errors:** Step 9 live log viewer + progress bar + elapsed + time estimate; `_on_complete` → quality dashboard update from report + completion modal with Open Output/Summaries Folder; failures logged + error status. Post-completion action combo (persisted `ui.post_completion_action`). Wizard `closeEvent` hands callbacks back to ConvertView unless the queue owns them.
- **Step dependencies:** validation is per-step on Next; step 1 re-validated at start; VRAM/token gates before run; settings loaded into state up-front (models, translation, advanced).
- **Unknowns:** none material — the flow above is fully traceable in code. (Per instructions: wizard redesign is deferred until the user supplies screenshots.)

---

## 5. Theme architecture (current) and identified issues

### Implementation (`ui_qt/theme.py`, 875 lines — well centralized)

- **Token namespaces:** `SPACE` (4 px grid), `FONT` (9–22 px, compact density; body **11 px**), `WEIGHT`, `RADIUS` (3–10 px) + `FONT_FAMILY` = `"Inter", "Segoe UI Variable", "Segoe UI", …`.
- **`Palette` dataclass** (frozen): `bg_window / bg_surface / bg_elevated / bg_input(+hover) / border / border_strong / text_primary / text_secondary / text_muted / text_on_accent / accent(+hover/pressed/soft) / success / warning / error / info`.
- **Current palette "Editorial Quiet v2":** warm ivory + **terracotta-amber accent** (light `#B8704A`, dark `#D8AA78`) — *not* the approved forest-green/sage direction.
- **`ThemeManager` singleton** (`theme_manager`): `apply(app)` sets QPalette + full-app QSS (`_qss(p)`, ~540 lines covering every Qt control incl. `#Card`, `#Primary`, `#TopBar`, tabs, lists, menus…), persists to `ui_theme.json`, one-shot Inter load.
- **Toggle path:** top-bar button → `theme_manager.toggle()` → `app.setStyleSheet` re-polish + manual `refresh_theme()` calls for views that paint theme-dependent content inline (convert→tool cards, queue, scanner, quarantine, llm lights).
- **Fonts:** `assets/fonts/` contains **only Vazirmatn** (Persian); **Inter is NOT bundled** — the stack silently falls back to Segoe UI on Windows. `load_inter()` is already written and will pick up `Inter-{Regular,Medium,SemiBold,Bold}.ttf` if added to `assets/fonts/`.

### Issues / gaps found (verified)

1. **Accent color family conflicts with the approved spec** (terracotta vs. muted forest green) — palette values must change in M1.
2. **Hardcoded colors outside theme.py:** ~35 hex + 16 `rgba()` occurrences across 16 files — notably `app.py` splash (`#23242b`, `#d8aa78`, `#eceef4`), `convert_view.py:276` tab flash `#D8AA78`, `step5_models.py` (`#5B9BD5` blue, `#B0594F`), `settings/dependencies_page.py` (8), service dialogs, `token_cost_dialog`, `chapter_selector_dialog`, `about_system_dialog`, `podcast_maker_view`, `step_header`, settings sections.
3. **Emoji used as icons** in tool cards, top-bar buttons ("✨", "📚"), wizard Start ("🚀"), dialog titles — conflicts with the approved monochrome-outline icon direction (the Lucide `icons.py` system already exists and is theme-aware).
4. **Theme-refresh coverage is manual and partial:** only 4 views + lights are refreshed; open **modal** dialogs are protected by modality (toggle unreachable), but the Hallucination tab-5 widget and any future sidebar must be added to the refresh list. `BaseServiceDialog` has no `refresh_theme` (relies on global QSS — acceptable given modality).
5. **Wizard step dots** re-derive inline styles from the palette on every `_update_step` (would follow new tokens automatically — good).
6. **Density mismatch:** current compact 11 px body / 4 px grid vs. the spec's 13–14 px body / roomier dashboard — a deliberate M1 decision point (dashboard-scale typography vs. existing compact dialogs).
7. **No theme/unit tests exist** (`grep theme|palette|token` in `tests/` → none) — M1 should add a small palette/QSS regression test.
8. **`success` color** is already sage-green in both themes — aligns with the approved accent family; harmless overlap to be aware of when introducing green accents (avoid confusing "status green" with "interactive green").

---

## 6. Design implementation assessment (approved spec vs. codebase)

### Reusable as-is (strong foundations)

- **Centralized theme/QSS architecture** — exactly the "centralized tokens" the spec demands; only palette *values* + a few token additions are needed.
- **Lucide outline icon system** (`icons.py`, 48 icons, any color/size, cached) — the approved icon direction; needs ~6–10 new glyphs (e.g. `home`, `zap` exists, `download`, `headphones`, `audio-lines`, `file-output`, `printer`…), not a new system.
- **`ToolCard`** already supports icon-name sources (ASCII string → icon lookup) — swapping emoji → Lucide names is *data-only* in `TOOL_CARDS`.
- **Theme persistence** (`ui_theme.json`) already exists → allowed to keep per spec §8.
- **Settings dialog (VLC-style rail)** — a natural existing home for relocated backend controls; About & System dialog already shows backend/connection status.
- **Geometry/resize handling**, offscreen-testable patterns, `BaseServiceDialog` shared base, controller-bridge threading discipline.

### Needs visual refinement

- Palette values → warm ivory / charcoal / forest green / sage (both themes); type scale; radius/spacing per spec tokens; icon colors defaulting to a neutral `icon` token.
- Dashboard composition: hero panel + compact Quick Tools grid replacing the 4×3 equal card grid; category rows → sidebar groups.
- Top-bar declutter: subtitle, Wizard/Merge CTAs, lights relocation decision.

### Needs architectural change (M2 — contained)

- **Tab bar → fixed compact sidebar** (spec §5): replace `QTabWidget` (North) with a left rail + `QStackedWidget`, or a `West`-positioned `QTabWidget` restyled as a rail. All five tab views are already independent widgets in scroll areas — the change is confined to `ElixirWindow._build_content()` + QSS; the convert_view `_switch_to_tab` helper walks `parent.tab_widget` and must be adapted.
- **Experimental destinations hidden from primary nav without deletion:** keep `QueueView`/`OutputScannerView`/`QuarantineView`/hallucination tab instantiated (or lazily constructible) but not listed in the sidebar; their entry points must remain reachable via existing non-primary paths (e.g. About/Tools surface, convert_view keys) — **exact fallback access path is a user question (§8)**.
- **LLM lights relocation:** move the widget + its poll loop ownership into Settings/About or keep a minimal single status dot — **user question (§8)**.

### Compatibility risks

| Risk | Mitigation |
|---|---|
| `_switch_to_tab` in `convert_view.py` assumes `parent.tab_widget` QTabWidget API | Adapt during M2; keep an equivalent navigation facade |
| Tests import/construct tab structure (`test_v0600_internal_tabs_e2e.py`, `test_v1820314_ui_cta_crash.py`, `test_v182046_p5_wizard_split.py`, `test_v182049_bk1_ui_threading.py`, tool e2e suites) | Run UI-test subset per milestone; read tests before sidebar surgery |
| Window min 560×400 — a labeled sidebar must survive narrow widths | Spec allows icon+label; verify at min size; sidebar min-width budget ~180–200 px |
| AGENTS.md Rule 1 deny-list scans `ui_qt/` — no book-derived words in new UI copy | Use spec-approved copy only; run suite (deny-list tests run inside it) |
| Startup import order (torch before PySide6) | Don't touch `main.py` import order in M1/M2 |
| Headless CI can't screenshot | Tests run with `QT_QPA_PLATFORM=offscreen`; visual QA screenshots happen on the user's Windows machine (M3) |

### Spec points needing clarification after code inspection → see §8 questions.

### Conflicts between package documents (reported, not silently resolved)

1. **Reference image vs. text spec — duplicate Full Conversion:** the approved visual reference shows a 9th Quick-Tools card "Full Conversion Wizard" (dark-green styled), while the text spec (§6, DoD) and the session brief **forbid** a duplicate tile. → Following the text spec (no duplicate tile).
2. **Reference image vs. text spec — header Ollama pill:** the image shows an Ollama model-selector pill in the header; the text spec (§5 "Header") requires backend indicators to move OUT of the header. → Following the text spec.
3. **Reference image vs. text spec — serif wordmark:** the image renders "Elixir" in a serif; the spec §4 forbids serif wordmarks. → Following the text spec (sans-serif).
4. **Reference image vs. text spec — sidebar IA:** the image shows a flat TOOLS list incl. "Full Conversion"; the spec §5 proposes grouped Processing/Utilities (subject to repository verification — the real inventory adds an Audio group). → Sidebar grouping to be confirmed with user (§8 Q1/Q2).
5. **Wizard step count:** spec says "10-step" — `_STEP_LABELS` = 10 (docstrings in older files say 9; module header in wizard_view.py lists 9 items but 7b exists). The 10-step figure is correct for the running app.
6. **Output-type count:** README says 19; `OUTPUT_REGISTRY`+core = 21 (17 studio + 4 core; step4 docstring documents the V0.6.8 correction). Code is authoritative.

---

## 7. Proposed implementation plan (NOT started — awaits approval)

### M1 — Visual foundation
- **Files:** `ui_qt/theme.py` (palette values, add `icon` + `surface_subtle`/`accent_subtle` tokens), `ui_qt/components/icons.py` (+6–10 Lucide glyphs), NEW `ui_qt/components/` reusable primitives (SidebarNavItem, SectionLabel, HeroPanel, QuickToolCard, PrimaryButton styling already in QSS) if needed, `assets/fonts/` (bundle Inter 4 weights — decision §8 Q4), targeted de-hardcoding of the ~35 hex colors (splash, step5, dependencies_page, …).
- **Changes:** swap DARK/LIGHT `Palette` values to spec tokens; keep field names (dataclass shape stable) or extend additively; verify contrast; no behavior changes.
- **Dependencies:** none external; font files must be legally bundled (Inter OFL — fine).
- **Risks:** QSS-wide color shifts expose hardcoded-color leftovers → de-hardcode pass included; tests that assert colors (none found) — safe.
- **Validation:** `ruff check`; full suite; NEW small test pinning palette tokens + QSS generation for both modes; offscreen screenshot harness if feasible; user visual check.
- **Done when:** both themes render spec tokens app-wide with zero hardcoded accent-color leftovers in dashboard-visible surfaces, suite green (minus documented environment failures), commit made.

### M2 — Dashboard
- **Files:** `ui_qt/app.py` (shell: sidebar + header), `ui_qt/views/convert_view.py` (`_switch_to_tab` facade), NEW `ui_qt/components/sidebar.py` + `ui_qt/views/home_view.py` (hero + Quick Tools), `ui_qt/views/tool_dashboard.py` (replaced by hero+grid composition; `TOOL_CARDS` data reused), `ui_qt/components/tool_card.py` (compact variant), `ui_qt/components/llm_lights.py` (relocation per user decision).
- **Changes:** fixed sidebar (icons+labels, groups Home/Processing/Utilities(/Audio?)/Settings/About); hero with "Start Conversion" CTA → `WizardView`; Quick Tools grid (no Full Conversion tile); hide Queue/Scanner/Bullet/Hallucination from primary nav (code intact + fallback access path per user decision); header reduced (brand + theme + settings + about).
- **Dependencies:** M1 tokens.
- **Risks:** tab-structure test breakage (read+adapt); narrow-window sidebar space; drag-drop overlay geometry; single-instance focus path.
- **Validation:** UI-test subset + full suite; manual QA matrix 1280×800 / 1440×900 / min 560×400; both themes; navigation opens every tool; experimental views reachable via agreed fallback; DnD still routes to Queue.
- **Done when:** dashboard matches spec composition and every navigation path works, suite green, commit made.

### M3 — Polish & testing
- **Files:** as surfaced by QA (spacing, focus states, long labels, DPI text).
- **Validation:** theme-switch sweep across all views; keyboard/tab-order pass; screenshots both themes at 3 sizes on user's Windows machine; regression diff of before/after test runs.
- **Done when:** QA report accepted.

### M4 — Documentation & release handoff
- **Files:** `CHANGELOG.md`, `release_notes/V0.6.70.md` (version bump decision), `README.md` screenshots/sections if needed, root `NEW_SESSION_PROMPT.md` refresh (with user approval), this report chain.
- **Process:** per AGENTS.md Rules 2–6: conventional commits, suite green, zip in download folder + GitHub Release **only with explicit user authorization** (the package's SESSION_WORKFLOW overrides "every version gets a release" until the user authorizes publishing).
- **Done when:** docs/changelog updated, commits pushed (with approval), release prepared (publishing gated).

---

## 8. Questions and blockers (decisions needed before/at M1–M2)

> **RESOLVED — user decisions received 2026-11-01 (start of Session 2 / M1), quoted:**
> 1. "Add audio group" · 2. "Okay do it." · 3. "keep one compact aggregate dot in header" ·
> 4. "Bundle Inter TTFs" · 5. "use supplied hero_books_quill.png" ·
> 6. "keep compact 11 px dialogs, larger dashboard type (recommended)" ·
> 7. "emove [r] once hero CTA exists (recommended)" · 8. "one bump at M2 (e.g., V0.6.70), then per milestone."

1. **Sidebar IA — Audio group:** the real app has 3 audio tools (TTS, Podcast Maker, Transcribe) not present in the spec's proposed sidebar IA. Include an **Audio** group (recommended — they're real, functional tools), or omit audio from the sidebar?
   → **DECIDED: include the Audio group** (TTS Service, Podcast Maker, Transcribe Service) in the M2 sidebar/grid IA alongside Processing/Utilities.
2. **Fallback access for hidden experimental destinations:** when Queue / Output Scanner / Bullet Audit / Hallucination Audit leave primary navigation, where should they remain reachable? Options: (a) an "Experimental tools…" section inside the existing **About & System dialog**, (b) a Settings page, (c) keyboard/short-only. *(The drop-a-PDF → Queue behavior also depends on this: if Queue has no visible surface, should DnD open the Queue view on drop?)*
   → **DECIDED (user approved the recommended option): (a)** — an "Experimental tools…" section inside the existing About & System dialog; drop-a-PDF continues to open the Queue view on drop (existing behavior preserved, the surface remains reachable).
3. **LLM status lights placement:** spec says backend indicators move out of the header "after verifying behavior" — options: keep ONE compact aggregate dot in the header (mini mode already exists) with details in About & System; or move the full widget into About & System / Settings only.
   → **DECIDED: keep one compact aggregate dot in the header** (the existing mini/aggregate mode), with details in About & System.
4. **Inter font bundling:** `assets/fonts/` lacks Inter (falls back to Segoe UI on Windows). Bundle the 4 Inter TTFs (~1 MB, OFL) for brand consistency, or rely on Segoe UI (spec allows both)? *(Minor new "dependency" — files, not packages.)*
   → **DECIDED: bundle the 4 Inter TTFs** (Regular/Medium/SemiBold/Bold, OFL) in `assets/fonts/` — done in M1.
5. **Hero illustration asset:** use the supplied `hero_books_quill.png` (632×330 raster; the package itself warns about soft edges and requires inspection on the real background) at reduced size, ship the hero text-only initially, or authorize generating a cleaner minimal illustration later?
   → **DECIDED: use the supplied `hero_books_quill.png`** at reduced size (staged into the repo in M1; alpha/crop inspected; final judgement on the real background happens in M2 on the user's Windows machine).
6. **Density:** keep the app-wide compact 11 px-body density for dialogs (wizard, settings — recommended, out of redesign scope) while the dashboard/hero uses the spec's larger type, or re-scale everything?
   → **DECIDED: keep the compact 11 px dialog density; the dashboard/hero/sidebar use the spec's larger type scale** (new FONT tokens added in M1; shared tokens untouched so dialogs are unchanged).
7. **Wizard entry duplication:** with the hero "Start Conversion" CTA in the dashboard, should the top-bar "✨ Process Wizard" button remain (recommended: remove it from the header per "minimal header", the hero becomes the single dominant entry) — or stay?
   → **DECIDED: remove the header wizard button once the hero CTA exists** (M2 — removal and hero land together so there is never a gap in the primary entry point).
8. **Versioning/release:** UI milestones land on `main` as which version(s) (e.g. V0.6.70 at M2 or per-milestone bumps)? GitHub Releases per AGENTS.md Rule 6 only after M4 with your explicit go-ahead — confirm.
   → **DECIDED: one version bump at M2 → V0.6.70, then one bump per milestone** (M3 → V0.6.71, M4 → V0.6.72). M1 lands on `main` at VERSION 0.6.69 (no bump). GitHub Releases only after M4 with the user's explicit go-ahead.

**Blockers (environment, not code):** this reconnaissance sandbox is headless Linux without `libEGL` — Qt GUI tests that instantiate widgets beyond QSS level fail/skip here with `ImportError: libEGL.so.1` (8 failures/errors in the UI-focused baseline run, all traced to that single missing system library; none are code defects). The user's Windows machine remains the authoritative visual-QA environment. No other blockers found.

---

## 9. Baseline verification record (this session)

- `git status` at start and end: clean; only NEW untracked doc files added by M0 (listed in §10).
- `ruff check core/ utils/ ui_qt/ tests/`: **1 pre-existing error** (`B023` in `core/tts/_vibevoice_subprocess.py:1053` — loop-variable binding in a torch patch; unrelated to UI, not fixed per M0 rules).
- Test runs (sandbox venv: Python 3.12.16, PySide6-Essentials 6.12.0, pytest 9.0.2, offscreen):
  - Collection: **8,638 tests / 305 files**; 4 property-test collection errors resolved after installing `hypothesis`.
  - UI-focused subset (8 files incl. internal-tabs e2e, llm-lights, wizard-split, ui-threading, controller-mapping, tool e2e): **262 passed / 4 failed / 4 errors / 86 skipped** — all 8 failures+errors traced to missing `libEGL.so.1` (environment), 0 code defects.
  - **Full suite: 8,346 passed / 34 failed / 29 errors / 375 skipped / 7 xfailed in 274 s.** Failure triage:
    - **~58 of 63 failures+errors are environment artifacts** of this headless sandbox: missing system library `libEGL.so.1` (every test that instantiates PySide6 widgets: summarization/v0640 depth, internal-tabs, llamacpp, tts e2e, b17 dialog migration, v067 SSOT dialog pins, transcribe combo pin, vibevoice subprocess trio) plus initially-uninstalled optional pip packages (`radon`, `ebooklib`, `genanki`) — after installing those three, all of their tests pass (re-verified: `2 failed, 128 passed` on the affected files; the 2 remaining are below).
    - **5 genuine pre-existing failures at HEAD `11aa7ff`** (all UI-unrelated; existed before this redesign and must NOT be "fixed" during M1–M3 without user approval):
      1. `test_golden_freeze.py::test_prompt_manifest_matches_prompt_bank` — prompt-bank manifest hash drift.
      2. `test_p4_eval_gate.py::TestBaselineSync::test_fixtures_match_committed_baseline` — eval fixture/baseline drift.
      3. `test_p4_eval_gate.py::test_cli_check_from_fixtures_exits_zero` — follows from the same baseline drift.
      4. `test_v182044_p3_tts_subprocess.py::TestSourcePins::test_timeout_constants_exist_unchanged` — pinned VibeVoice line timeout changed 600→3600 s without updating the pin test.
      5. `test_v182044_p3_tts_subprocess.py::TestSourcePins::test_vibevoice_line_timeout_kill_unchanged_shape` — same root cause.
  - **Regression rule for M1+:** a milestone is "suite-green" when the full-suite result is **no worse than this baseline** (same 5 pre-existing failures ± documented environment artifacts), with zero NEW failures in `ui_qt/`-touching tests.
- `python main.py` (source launch): not launched to completion in the sandbox (headless, no display; launcher-guard precheck would block Qt). Launch procedure on Windows: `pip install -r requirements.txt`, `python main.py`.

## 10. Files created by this session (M0 only — nothing modified, nothing committed)

- `docs/M0_RECON_REPORT.md` (this file)
- `docs/M0_NEXT_SESSION_PROMPT.md` (Session 2 / M1 handoff prompt)

Application source, tests, styles, and all pre-existing documentation are untouched. No commits, pushes, tags, or releases were made. **Stopped after M0 as instructed — awaiting user review before M1.**
