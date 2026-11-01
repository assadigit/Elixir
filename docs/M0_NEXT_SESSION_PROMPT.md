# Next Session Prompt — Elixir Session 3: M2 Dashboard

> This is the ROLLING next-session prompt (M0's original content — the M1
> handoff — is preserved in git history at commit `49872ac`). The permanent
> reconnaissance record lives in `docs/M0_RECON_REPORT.md` (§8 now carries all
> eight user decisions). Repo: https://github.com/assadigit/elixir · branch
> `main` · M1 ended at `19c6c52` (test pin commit); the M1 changelog + this
> rolling prompt landed at `ab97cab`. **Published 2026-11-01 with the user's
> explicit authorization:** `main` is now PUSHED to GitHub through the
> release commit, and the M1 tree is live as the pre-release tag
> **`V0.6.70-M1`** (`release_notes/V0.6.70-M1.md`; zip in the download
> folder; marked pre-release — V0.6.69-windows stays Latest; `VERSION`
> untouched). Working tree at publication: clean. VERSION is still `0.6.69`
> — the FIRST redesign bump (V0.6.70) happens at the END of M2, per user
> decision Q8.

## Read first

1. `docs/M0_RECON_REPORT.md` — the code-grounded map (§4 shell/nav, §5
   feature inventory, §6 theme analysis, §7 wizard map, §8 the decisions).
2. `CHANGELOG.md` → the `## Unreleased (M1 …)` heading — exactly what M1
   delivered and the suite reference baseline.
3. `ui_qt/theme.py` — the M1 foundation you build on: `Palette` (22 fields,
   incl. the spec `icon` token), `FONT` (frozen dialog scale + the
   dashboard scale `hero/section/tool/sidebar/body_lg`), `rgba()` helper,
   `CODE_EDITOR`, and the M2-ready QSS rules (`QLabel#Hero/#Support/
   #SectionHead/#ToolTitle/#SidebarLabel/#SidebarGroup`,
   `QPushButton#HeroPrimary`).
4. `ui_qt/components/dashboard_primitives.py` — `SectionLabel`,
   `SidebarNavItem`, `QuickToolCard` (built in M1, deliberately UNWIRED —
   wiring them in is M2's first move).
5. `AGENTS.md` — the 6 standing rules (content-agnostic, evidence-first,
   net-green, provenance, zip-per-release, release-per-version).
6. Key shell files: `ui_qt/app.py` (`_build_top_bar()` ~L114–200,
   `_build_content()` ~L342–441, `_setup_llm_lights_monitoring()`),
   `ui_qt/views/convert_view.py` (`_switch_to_tab`, card routing),
   `ui_qt/views/tool_dashboard.py` (`TOOL_CARDS` data),
   `ui_qt/components/llm_lights.py`, `ui_qt/views/about_system_dialog.py`.

## Current milestone

**M2 — Dashboard ONLY.** Fixed compact sidebar (icons + labels), Full
Conversion hero, compact Quick Tools grid, decluttered header,
experimental destinations hidden from primary nav (code intact). The
10-step Wizard itself is OUT OF SCOPE (later milestone). At the END of
M2: bump `VERSION` → `0.6.70` + `CHANGELOG.md` `## V0.6.70` heading (no
tag, no push, no GitHub Release **in that session** — the 2026-11-01
`V0.6.70-M1` pre-release was separately user-authorized; publishing
V0.6.70 proper stays M4/user-authorized, per AGENTS.md Rule 6 and
decision Q8).

## The eight user decisions (all locked — quote in the final report)

1. **Audio group IN** — sidebar/grid IA gains an Audio group (TTS Service,
   Podcast Maker, Transcribe Service) alongside Processing/Utilities.
2. **Experimental fallback = (a)** — an "Experimental tools…" section inside
   the existing **About & System dialog**; drop-a-PDF keeps opening the
   Queue view on drop (existing behavior preserved).
3. **LLM lights: ONE compact aggregate dot stays in the header** (the
   existing mini mode) — full details live in About & System.
4. **Inter bundled** — done in M1 (`assets/fonts/`, auto-registered).
5. **Hero visual = the supplied `assets/hero_books_quill.png`** at reduced
   size. M1 inspection: 632×330 RGBA, ~55% of content pixels solid,
   ivory + charcoal-olive ink, a soft halo quarter (p25 alpha=24), content
   fills ~98% of the canvas. M2 composites it onto the hero surface
   (flatten alpha against the surface colour or use QLabel pixmap), keeps
   it ≤ ~260 px wide, hides/simplifies it at narrow widths, and re-judges
   on the real background during the user's Windows QA. If it reads poorly,
   the spec allows omitting it — do NOT force it.
6. **Density: compact 11 px dialogs + larger dashboard type** — the M1
   `FONT` split already encodes this; consume `hero/section/tool/sidebar/
   body_lg` in the new dashboard surfaces and touch nothing dialog-facing.
7. **Header "✨ Process Wizard" button: REMOVE once the hero CTA exists** —
   land the hero and the removal in the SAME milestone so the primary
   entry never gaps. The hero CTA label: **"Start Conversion"** (spec §6)
   unless the M2 agent finds an exact established term in the codebase.
8. **Versioning: one bump at M2 (V0.6.70), then per milestone** (M3 →
   V0.6.71, M4 → V0.6.72).

## Your task this session (M2 scope)

1. **Confirm state:** `git status` (expect clean), `git log -3` (HEAD sits
   above the `V0.6.70-M1` release commit; `origin/main` is current — the
   pre-release tag already exists on the remote, do not touch it), read the
   M1 changelog entry. Run `pytest tests/test_m1_theme_tokens.py -q` —
   must be 22 passed + 5 skipped (libEGL sandbox) before you start.
2. **The shell (sidebar + header):**
   - Replace the north `QTabWidget` in `ElixirWindow._build_content()`
     with a fixed compact LEFT sidebar (icons + labels, ~200–220 px, always
     visible, no collapse) + a `QStackedWidget` content area. Either a new
     `ui_qt/components/sidebar.py` (preferred — build it on the M1
     `SidebarNavItem`/`SectionLabel` primitives) or a West-positioned
     restyled QTabWidget; prefer whichever keeps `_switch_to_tab`-style
     navigation simplest.
   - Sidebar IA: **Home** / **Processing** (Summarization, Document →
     Markdown, Translation) / **Utilities** (Markdown Styler, Packets of
     Knowledge, OCR Service, PDF/DOCX Cutter, Image Extractor) / **Audio**
     (TTS Service, Podcast Maker, Transcribe Service) / **Settings** /
     **About**. Verify every label against `TOOL_CARDS` + the M0 §5
     inventory before shipping; exact user-facing names only.
   - `QTabBar` QSS rules in `theme.py` stay (settings dialogs still use
     tabs); add sidebar QSS (rail background, nav-item rules already live
     in `dashboard_primitives.py` if you keep them self-styled).
   - **Header (`_build_top_bar()`):** brand + subtitle, stretch, ONE
     aggregate LLM dot (`LocalLLMLights` mini mode — see `llm_lights.py`
     width-adaptive ladder; force/lock mini in the header), theme toggle,
     settings, about IconBtns. REMOVE the "✨ Process Wizard" button
     (decision Q7 — hero owns the entry). The "📚 Merge" compact button:
     either keep it in the header (it is a real, functional action) or
     surface Merge as a Quick Tools tile — inspect `core/pipeline/
     multi_pdf_merge.py` + its current launcher first, then choose and
     DOCUMENT the choice in the session report (do not delete the feature).
   - **Llm-lights details → About & System:** the About & System dialog
     gains the full `LocalLLMLights` widget (it already has a Refresh
     scan; add the lights row + tooltips). Keep the poll loop in
     `ElixirWindow._setup_llm_lights_monitoring()` feeding both sinks.
3. **The home view (`ui_qt/views/home_view.py`, NEW):**
   - Concise purpose line, then the **Full Conversion hero**: editorial
     split — heading ("Turn documents into clear, structured knowledge."),
     supporting copy (verify against real capabilities), one
     `QPushButton#HeroPrimary` "Start Conversion" → the SAME modal
     `WizardView` entry the removed header button used (reuse `app.py::
     _open_wizard` / `convert_view._open_wizard` — do not fork the
     opening logic), and the hero visual per decision Q5.
   - **Quick Tools grid** beneath: `QuickToolCard`s fed from the existing
     `TOOL_CARDS` data (drop the `full_conversion` entry — NO duplicate
     hero tile; swap emoji strings for the M1 icon names: rocket, sigma,
     file-text, globe, sparkles, layers/bookmark for packets — pick from
     the 52 available glyphs), grouped Processing / Utilities / Audio with
     `SectionLabel`s. Card click routing REUSES the existing
     `convert_view` tool-key dispatch — do not re-implement launches.
   - Keep the hero compact: at 1280×800 the Quick Tools section must begin
     within the initial viewport.
4. **Experimental destinations (decision Q2):**
   - Queue / Output Scanner / Bullet Audit / Hallucination Audit leave the
     primary navigation. KEEP the views and all routing code intact —
     construct them lazily or keep them in the stack, unlisted.
   - Add an "Experimental tools…" section to the **About & System dialog**
     (four rows/buttons that switch to the hidden views via the navigation
     facade). Keep `dropEvent` → Queue routing exactly as-is (the surface
     stays reachable; the tab-flash highlight from M1 now uses the accent
     token — if the tab bar is gone, route the flash to the About&System
     entry or drop the flash; document which).
   - `convert_view` keys (`batch_queue`, `output_scanner`,
     `hallucination_audit`, quarantine) must keep working through the
     facade — Packets output still opens Hallucination Audit.
5. **Navigation facade:** adapt `convert_view._switch_to_tab` (it walks
   `parent.tab_widget`) to the sidebar+stack world — same public helper
   name/semantics, backed by the stacked index map. All existing callers
   (queue badge refresh, quarantine auto-reload, `_on_tab_changed`
   equivalents) must keep firing.
6. **Theme-refresh coverage:** add the sidebar + home view to the
   refresh-on-toggle path (the M0 §6 gap list — only 4 views + lights are
   refreshed today; the M2 surfaces must join them).
7. **Tests:** add `tests/test_m2_dashboard.py` (house source-pin style):
   sidebar IA pin (groups + exact labels), hero present + single
   "Start Conversion" CTA + NO Full Conversion tile in Quick Tools, the
   four experimental views absent from the sidebar nav data but their
   view modules + convert_view keys intact, About&System contains the
   "Experimental tools" surface, llm-lights header usage is the mini/
   aggregate mode, `_switch_to_tab` facade preserved. UPDATE the existing
   tab-structure pins that M2 legitimately changes:
   `test_v0600_internal_tabs_e2e.py`, `test_v1820314_ui_cta_crash.py`,
   `test_v182046_p5_wizard_split.py`, `test_v182049_bk1_ui_threading.py`,
   `test_v0610_b17_dialog_migration.py` — read each before touching; keep
   their intent (behavior pins), update their mechanics (tab → stack).
   Do NOT weaken a pin to make it pass; if a pin encodes user-visible
   behavior that the approved redesign intentionally changes, rewrite it
   to pin the NEW behavior and say so in the commit.
8. **Version bump (decision Q8):** at the very end, `VERSION` → `0.6.70`,
   `CHANGELOG.md` gains the `## V0.6.70` heading (convert the M1
   "Unreleased" section into it or append a new section — keep both
   records), `release_notes/V0.6.70.md` MAY be drafted but is NOT
   published. NO tag, NO push, NO GitHub Release, NO zip — those are
   M4/user-authorized only.
9. **Validation:** `ruff check core/ utils/ ui_qt/ tests/` (only the 1
   pre-existing B023); full suite vs the **M1 reference baseline: 8,374
   passed / 28 failed / 29 errors / 380 skipped / 7 xfailed** — zero NEW
   failures (the 28+29 are the documented pre-existing + libEGL
   environment set; 5 genuine: prompt-manifest ×1, eval-baseline ×2,
   VibeVoice timeout pins ×2 — still do not fix them). Visual QA on the
   user's Windows machine is the authority: ship the session report with
   a manual QA checklist (1280×800, 1440×900, min 560×400; both themes;
   every tool opens; DnD → Queue; hero/CTA/illustration no-overlap;
   sidebar labels readable; Quick Tools reflow).

## Acceptance criteria

- Fixed sidebar: icons + labels, grouped Home/Processing/Utilities/Audio/
  Settings/About, active/hover/focus states via tokens; always visible.
- Hero: single dominant action, one `HeroPrimary` CTA opening the SAME
  WizardView, supplied illustration at reduced size (or omitted with a
  documented reason), Quick Tools beginning in the initial 1280×800 view.
- Quick Tools: compact grid, NO Full Conversion tile, only verified tools,
  existing routing.
- Header: brand + one aggregate LLM dot + theme/settings/about; wizard
  button gone; Merge handled + documented.
- Experimental four: absent from primary nav, present via About&System
  "Experimental tools…", DnD→Queue unchanged, all code paths intact.
- Both themes correct on every new surface; refresh-on-toggle covers them.
- `VERSION` = 0.6.70 + changelog entry; no tag/push/release.
- Suite no worse than the M1 baseline; ruff clean (minus the pre-existing
  B023); new M2 pins green.

## Explicitly do NOT

- Redesign the Wizard's 10 steps, its dialogs, or any conversion/backend
  behavior (visual token side-effects only, no logic).
- Delete or disable any feature, view, or code path — hiding ≠ removing.
- Rename tools beyond the exact existing user-facing labels.
- Introduce new pip dependencies, mock data, fake statuses, recent-jobs,
  presets, or onboarding flows.
- Fix the 5 pre-existing failures, the ruff B023, or unrelated modules.
- Reset/rebase/force-push; tag; publish a Release; push without explicit
  authorization in that session.

## Required process

1. `git status` first; preserve user changes; read before editing.
2. Small reviewable commits (e.g. `ui: build the fixed sidebar shell`,
   `ui: add the Full Conversion hero home view`, `ui: compact Quick Tools
   grid with audio group`, `ui: hide experimental destinations behind
   About & System fallback`, `ui: reduce the header to brand + aggregate
   dot + essentials`, `test: pin the M2 dashboard structure`, `chore:
   bump VERSION to 0.6.70 for the dashboard milestone`) — tests before
   committing; diff review each time.
3. End with the full end-of-session report per `SESSION_WORKFLOW.md` and
   REPLACE this file's content with the Session 4 (M3 polish + regression)
   prompt, including the QA matrix results, the new baseline numbers, and
   the Windows visual-QA checklist outcome.
4. Record exact commands + outcomes; never say "tested" without the command.
