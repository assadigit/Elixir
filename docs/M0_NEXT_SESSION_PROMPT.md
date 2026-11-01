# Next Session Prompt — Elixir Session 2: M1 Visual Foundation

> Written at the end of Session 1 (M0 reconnaissance). The authoritative
> findings live in `docs/M0_RECON_REPORT.md` — read it before starting.
> Repo: https://github.com/assadigit/elixir · branch `main` · baseline HEAD
> `11aa7ff` (V0.6.69). Working tree at M0 end: clean apart from the two new
> untracked M0 docs (`docs/M0_RECON_REPORT.md`, `docs/M0_NEXT_SESSION_PROMPT.md`).

## Read first

1. `docs/M0_RECON_REPORT.md` — the code-grounded map (architecture, inventory, theme analysis, baseline).
2. `ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip` (repo root) → `docs/ELIXIR_FINAL_DASHBOARD_DESIGN_SPEC.md`, `AI_IMPLEMENTATION_INSTRUCTIONS.md`, `SESSION_WORKFLOW.md`.
3. `AGENTS.md` — the 6 standing rules (content-agnostic, evidence-first, net-green, provenance, zip-per-release, release-per-version).
4. `ui_qt/theme.py`, `ui_qt/components/icons.py`, `ui_qt/views/tool_dashboard.py`, `ui_qt/components/tool_card.py` — the exact files M1 touches.

## Current milestone

**M1 — Visual foundation ONLY.** Tokens, palette, typography, icons, shared styling, de-hardcoding. **No dashboard layout change, no sidebar, no wizard edits.**

## M0 findings that shape M1 (short version)

- PySide6 ≥ 6.6, Python 3.12, entry `main.py` → `ui_qt.app.run()`. **Import order is load-bearing: torch BEFORE PySide6. Do not reorder startup imports.**
- Theme system is already centralized in `ui_qt/theme.py`: `SPACE`/`FONT`/`WEIGHT`/`RADIUS` tokens + frozen `Palette` dataclass + `_qss()` full-app QSS + `ThemeManager` singleton persisting `~/.elixir/ui_theme.json`. Current accent is **terracotta-amber** — must become the approved **muted forest green / sage / warm ivory / charcoal** tokens.
- `Palette` fields: `bg_window, bg_surface, bg_elevated, bg_input, bg_input_hover, border, border_strong, text_primary, text_secondary, text_muted, text_on_accent, accent, accent_hover, accent_pressed, accent_soft, success, warning, error, info`. Add an `icon` token (spec) — ADD fields, do not rename existing ones (QSS + ~35 scattered call sites depend on them).
- Inter fonts are **NOT bundled** (`assets/fonts/` has only Vazirmatn). `load_inter()` already handles `Inter-{Regular,Medium,SemiBold,Bold}.ttf` if dropped in — pending the user's Q4 decision.
- Icon system: `ui_qt/components/icons.py` embeds **48 Lucide outline glyphs** rendered theme-aware (`icon(name, color, size)`). `ToolCard` already accepts icon *names* — swapping the dashboard's emoji for Lucide names is data-only in `TOOL_CARDS`.
- Hardcoded colors outside theme.py: ~35 hex + 16 rgba() in 16 files (splash in `app.py` ~L1165–1191, tab-flash `#D8AA78` in `convert_view.py:276`, `step5_models.py` `#5B9BD5`/`#B0594F`, `settings/dependencies_page.py` ×8, service dialogs, `token_cost_dialog`, `chapter_selector_dialog`, `about_system_dialog`, `podcast_maker_view`, `step_header`, settings sections).
- **Baseline (this sandbox):** full suite 8,346 P / 34 F / 29 E / 375 S; ~58 F+E are environment artifacts (headless sandbox lacks `libEGL.so.1`; `radon`/`ebooklib`/`genanki` were missing — installing them flipped their tests green). **5 genuine pre-existing failures at HEAD** (prompt-manifest drift ×1, eval-baseline drift ×2, VibeVoice timeout pin ×2) — all UI-unrelated; DO NOT fix them in M1. `ruff check` has 1 pre-existing error (`B023` in `core/tts/_vibevoice_subprocess.py:1053`) — leave it.
- Open user decisions that may affect M1 scope: Inter bundling (Q4), hero illustration asset (Q5), dialog density (Q6). Wait for the user's answers; if unanswered, proceed with values-only palette work (independent of all three) and flag the rest.

## Your task this session (M1 scope)

1. **Confirm state:** `git status` (expect only the two M0 docs untracked unless the user committed them), `git log -1`, then read the M0 report.
2. **Palette swap** in `ui_qt/theme.py`: replace `LIGHT`/`DARK` values with the spec §3 tokens (light: bg `#F6F5F0`, surface `#FFFFFF`, surface-subtle `#EFEEE7`, text `#252923`/`#70756D`, border `#E2E1D9`, accent `#3F634D`, hover `#34543F`, accent-subtle `#E6EDE6`, icon `#626A60`; dark: bg `#20231F`, surface `#292D28`, subtle `#30362F`, text `#ECEEE8`/`#A8AEA3`, border `#3B423A`, accent `#91AD91`, hover `#A4BDA2`, accent-subtle `#354238`, icon `#B3BBAF`). Map onto existing fields (`bg_elevated`≈surface-subtle, `accent_soft`≈accent-subtle as rgba) and ADD `icon` + any missing semantic fields. Verify `text_on_accent` contrast for both accents. Keep `success/warning/error/info` semantics distinct from the new interactive green.
3. **Type scale review (dashboard-facing only):** adjust hero/section sizes toward spec §4 (hero 26–30 px semibold, section 16–18, tool title 14–15, body 13–14) via the `FONT` namespace WITHOUT breaking dialog layouts — per the user's Q6 answer if given; otherwise conservative bump and note it.
4. **Icons:** add the Lucide glyphs the sidebar/hero/grid will need in M2 (`home`, `headphones`/`audio-lines`, `file-output`, `zap` exists, plus any missing from: sigma, globe, wand, scan, scissors, image, layers, file-text, newspaper, mic, play, book) to `ICONS` in `icons.py` with consistent 24×24 stroke data. No emoji removal yet (that's M2 data-swap territory) except where trivially safe.
5. **De-hardcode pass:** replace the ~35 hex/16 rgba scattered colors with palette refs where a palette field exists (splash, tab-flash, step5 groupbox border, dependencies page status colors → success/warning/error, etc.). Where a color has no token, add one rather than inventing another hex.
6. **Reusable primitives (optional, only if time allows):** `SectionLabel`, `SidebarNavItem` (visual-only widget, unused yet), `QuickToolCard` compact card — placed in `ui_qt/components/` ready for M2. Do NOT wire them into the app yet.
7. **Tests:** add a focused pytest (e.g. `tests/test_m1_theme_tokens.py`) pinning: both `Palette` dataclasses expose the spec hex values; `_qss()` compiles and contains the accent tokens for both modes; `theme_manager.toggle()` round-trips modes; `icons.icon("home", ...)` renders non-null offscreen. Follow the repo's hermetic/no-Qt-on-CI patterns (guard with the existing offscreen skip markers — see `tests/test_v0669_local_llm_lights.py` for the house style).
8. **Validation:** `ruff check core/ utils/ ui_qt/ tests/` (no NEW errors vs the 1 pre-existing); run the full suite and compare against the M0 baseline (expect the same 5 pre-existing failures ± environment artifacts, ZERO new failures); offscreen-launch a screenshot harness if possible (`QT_QPA_PLATFORM=offscreen` + `QWidget.grab()`) for both themes, else state that visual verification is deferred to the user's Windows machine.

## Acceptance criteria

- Both themes use the approved token values app-wide; no terracotta remnants in QSS or dashboard-visible surfaces.
- No existing `Palette` field renamed/removed (only additions); `ui_theme.json` persistence unchanged.
- All 48+ icons render; new glyphs match Lucide stroke style.
- Hardcoded-color count outside `theme.py` reduced to zero for theme-dependent colors (status colors via semantic tokens).
- New token test green; full suite no worse than baseline; ruff no new errors.
- NOTHING in `ui_qt/views/wizard_view.py`, `wizard_steps/`, `service_dialogs/` behavior changed; no dashboard layout change; no sidebar yet.
- Commit(s) made with conventional messages (e.g. `ui: adopt muted forest/sage palette tokens for light and dark themes`, `ui: de-hardcode scattered widget colors into theme tokens`, `test: pin M1 theme tokens and QSS generation`) — **push only if the user has authorized push in this session**; otherwise report the local hash.

## Explicitly do NOT

- Redesign the dashboard/sidebar (M2), the wizard (later milestone), or any dialog layout.
- Delete or hide any feature, view, or tab (including Queue/Output Scanner/Bullet Audit/Hallucination Audit — hiding is M2 work).
- Rename tools, change navigation, settings schemas, conversion behavior, or backend integrations.
- Fix the 5 pre-existing test failures, the ruff B023, or anything outside `ui_qt/theme.py`, `ui_qt/components/icons.py`, the targeted de-hardcode files, new component files, and the new test file.
- Introduce new pip dependencies (Inter TTFs are files, pending user Q4 approval).
- Reset/rebase/force-push; publish releases (AGENTS.md Rule 6 releases happen only with explicit user authorization).

## Required process

1. Inspect `git status` first; preserve all user changes.
2. Read source before editing; small reviewable commits; run tests before committing.
3. End with the full end-of-session report per `SESSION_WORKFLOW.md` and REPLACE this file's content with the next session's prompt (M2 dashboard) including: exact files for the sidebar/hero/grid work, the tab→sidebar migration plan (`ElixirWindow._build_content`, `convert_view._switch_to_tab` facade, llm-lights relocation per user's Q3 answer), the experimental-destination hiding plan (fallback access per user's Q2 answer), and the test files that pin tab structure (`test_v0600_internal_tabs_e2e.py`, `test_v1820314_ui_cta_crash.py`, `test_v182046_p5_wizard_split.py`, `test_v182049_bk1_ui_threading.py`, `test_v0610_b17_dialog_migration.py`).
4. Record exact commands + outcomes; never say "tested" without the command.
