# Next Session Prompt — Elixir Session 4: M3 Polish + Regression

> **RESTART NOTE (2026-11-01, wrap-up session):** the first Session-4
> attempt ran out of context BEFORE Step 1 — no QA matrix was walked, no
> findings recorded, no `theme.py` edits, no screenshots, no version
> bump. Nothing was lost or half-done: the wrap-up session verified the
> working tree clean at `88bfd6f` (VERSION 0.6.70), `main` in sync with
> `origin/main`, the push path confirmed working ("Everything
> up-to-date"), and no stashes or stray milestone branches. The user
> re-confirmed that pushes are expected (Rule 7 stands). Execute the M3
> mission below from Step 1 as written — do not hunt for phantom prior
> work; there is none.

> This is the ROLLING next-session prompt (the M2 dashboard prompt it
> replaced is preserved in git history at commit `9ba8e20^` / the M2
> close commit). Repo: https://github.com/assadigit/elixir · branch
> `main`. **M2 closed at VERSION 0.6.70** (dashboard milestone, decision
> Q8): fixed sidebar + hero home view + Quick Tools + the experimental
> four behind About & System. `release_notes/V0.6.70.md` is DRAFTED but
> NOT published — no tag, no GitHub Release, no zip for V0.6.70 without
> the user's explicit authorization (AGENTS.md Rules 5–7; the M4
> milestone owns the release handoff).

## Read first

1. `AGENTS.md` — the **7 standing rules** (content-agnostic,
   evidence-first, net-green, provenance, zip-per-release,
   release-per-version, **commit-and-push-incrementally — Rule 7,
   added at V0.6.69 after the first M2 attempt was lost unpushed**).
2. `CHANGELOG.md` → the `## V0.6.70` heading — exactly what M2 shipped,
   including the two documented M2 decisions (Merge stays in the header;
   the tab-flash is dropped) and the provenance note (M2 was built
   twice — the Session-3 build died with its sandbox).
3. `docs/M0_RECON_REPORT.md` — still the code-grounded map (§8 carries
   the eight locked user decisions Q1–Q8).
4. The M2 surfaces: `ui_qt/components/sidebar.py` (the rail + nav data),
   `ui_qt/views/home_view.py` (hero + Quick Tools grid),
   `ui_qt/app.py` (`_build_top_bar` / `_build_content` /
   `switch_to_page` / `_on_page_changed`), `ui_qt/views/convert_view.py`
   (`_switch_to_tab` facade), `ui_qt/views/about_system_dialog.py`
   (experimental tools + full lights).
5. `tests/test_m2_dashboard.py` (21 structure pins) +
   `tests/test_m1_theme_tokens.py` (the M1 pins M2 legitimately rewrote:
   primitives-wired, facade-not-flash).

## Current milestone

**M3 — polish + regression ONLY.** The premise: M2's dashboard is ON
`main` as **V0.6.70** and the user's Windows machine is the authoritative
visual-QA environment (the sandbox has no `libEGL.so.1` and cannot
instantiate Qt widgets — every widget-level check below happens with the
user, on Windows). M3 walks the QA matrix WITH the user, fixes what is
fixable with **token-level changes in `ui_qt/theme.py` only**, records
everything else as structure work for M4, and closes at **V0.6.71**
(decision Q8).

## Your task this session (M3 scope)

1. **Confirm state:** `git status` (expect clean), `git log -3` (HEAD is
   the M2 close: VERSION 0.6.70 + CHANGELOG `## V0.6.70` + this prompt),
   `git fetch origin main` (nothing unpushed — Rule 7). Run
   `pytest tests/test_m1_theme_tokens.py tests/test_m2_dashboard.py -q`
   → expect **43 passed / 5 skipped** (libEGL sandbox skips) before you
   start.
2. **THE QA MATRIX — walk it WITH the user, cell by cell** (the user
   runs Elixir on Windows; you record):
   - Sizes: **1280×800 · 1440×900 · 560×400 (the app minimum)**.
   - Themes: **light · dark** for each size (6 cells).
   - For every cell, record a verdict: OK / finding. Every failed or
     ugly cell becomes a numbered finding (**F1, F2, …**) with its cell,
     a plain-words description, and (if the user can) a screenshot.
   - Walk this checklist in each cell: every sidebar item opens the
     right tool/page; the hero heading/support/CTA/illustration do not
     overlap and the CTA opens the wizard; Quick Tools reflow (4/3/2
     columns) without clipping or horizontal scroll; the illustration
     hides below ~900 px content width; both themes look right on every
     surface (rail, cards, hero, About & System's new sections);
     drop-a-PDF anywhere → the Queue page OPENS with the books queued;
     About & System → "Experimental tools" rows switch to the hidden
     pages; the header shows ONE aggregate dot (hover for the summary);
     sidebar labels readable; no leftover tab-bar artifacts.
3. **Fix findings — TOKEN-LEVEL ONLY, in `ui_qt/theme.py`:** each finding
   gets the smallest token/QSS change that fixes it (a colour value, a
   radius, a font size inside the frozen-dialog constraint, a padding in
   a QSS rule). **One finding → one small commit → one immediate push**
   (Rule 7). Do NOT touch widget code, layouts, or logic — if a finding
   needs structure (a layout change, a widget move, a new control), do
   NOT fix it: record it on the **"M4 / needs-structure" list** in the
   session report (candidate list to seed it: the "📚" emoji on the
   header Merge link; the hero illustration's final keep/omit judgement
   on the real Windows background — Q5 explicitly allows omitting it;
   the hidden hallucination page's pre-existing emoji headings).
4. **Screenshots:** the 6 matrix cells' evidence → **exactly 6 PNGs into
   `docs/screenshots/v0.6.71/`** (home view composited with its natural
   empty state; `QWidget.grab()`; offscreen rendering acceptable where
   the sandbox allows, else the user's Windows captures — LABEL which).
   One **single evidence commit** at the end (not one per shot), pushed
   like every other.
5. **Full regression:** `ruff check core/ utils/ ui_qt/ tests/` (only
   the 1 pre-existing `B023` in `core/tts/_vibevoice_subprocess.py`) +
   the full suite vs **the M2 reference baseline: 8,403 passed /
   27 failed / 29 errors / 380 skipped** (sandbox, 2026-11-01 — count
   varies slightly with sandbox env packages; the invariant is ZERO NEW
   failure IDs; the 27+29 = 5 genuine pre-existing [prompt-manifest ×1,
   eval-baseline ×2, VibeVoice timeout pins ×2 — still do not fix them]
   + the documented libEGL environment class). Compare failure IDs, not
   just counts.
6. **Version bump (decision Q8):** `VERSION` → `0.6.71`, `CHANGELOG.md`
   gains `## V0.6.71` (the polish record + the QA matrix verdict table +
   the findings list with their fix commits), `release_notes/V0.6.71.md`
   MAY be drafted but is NOT published.
7. **Hand off:** REPLACE this file's content with the **Session 5 (M4 —
   documentation & release handoff)** prompt. The M4 prompt MUST state
   in its opening block that **every M4 release action (tag, GitHub
   Release, zip, push of a release commit) requires the user's EXPLICIT
   authorization in that session** (AGENTS.md Rules 5/6 — plain commits
   still push incrementally per Rule 7), and must carry the M4
   needs-structure list from your report.

## Acceptance criteria

- The 6-cell QA matrix walked with verdicts recorded; every non-OK cell
  is either fixed by a token-only `theme.py` commit or on the
  M4/needs-structure list.
- 6 screenshots in `docs/screenshots/v0.6.71/` (one evidence commit).
- Full suite: zero NEW failure IDs vs the M2 baseline; ruff: only the 1
  pre-existing B023; the 43 M1+M2 pins still green.
- `VERSION` = 0.6.71 + `CHANGELOG.md` `## V0.6.71`; no tag / GitHub
  Release / zip (user-authorized only).
- This file replaced with the Session 5 (M4) prompt (with the
  explicit-authorization gate stated).

## Explicitly do NOT

- Redesign the Wizard's 10 steps, touch backend/conversion behavior, or
  fix any pre-existing failure (the 5 genuine + the B023).
- Delete or disable any feature, view, or code path — hiding ≠ removing.
- Introduce new pip dependencies, controls, views, or mock data.
- Fix a finding with widget/layout code — that is M4 / needs-structure.
- Reset/rebase/force-push; tag; publish a GitHub Release; zip.
  (Plain pushes of `main` are REQUIRED after every commit — AGENTS.md
  Rule 7.)

## Required process

1. `git status` first; preserve user changes; read before editing.
2. One finding → one `ui:` commit (token-only) → push immediately; diff
   review each time; tests before committing.
3. Record exact commands + outcomes; never say "tested" without the
   command.
4. End with the full end-of-session report per `SESSION_WORKFLOW.md`:
   the QA matrix verdict table, the findings ledger (F# → fix commit /
   needs-structure), files changed, exact test numbers, the Windows
   checklist outcome, and the next-milestone recommendation.
