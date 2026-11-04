# AGENT_HANDOFF.md — Round 4 UI/UX Correction (in progress)

## A. Original objective
Execute `ELIXIR_UI_UX_CORRECTION_ROUND_4.md` fully: compact 3-column Quick Tools
grid, complete sidebar navigation (no internal scrollbar at reference size,
Settings/About visible), compact readable tagline card, remove the duplicate
top-bar theme control (keep the status-bar selector), evaluate and select
Manrope or IBM Plex Sans with reliable packaging + fallback, verify the hero
artwork is a genuine transparent PNG, refine layout proportions, capture the
now5*.png evidence set, run functional/regression tests, commit, push, and
publish the release (repo: https://github.com/assadigit/Elixir, branch main).

## B. Requirements and decisions
- Spec: ELIXIR_UI_UX_CORRECTION_ROUND_4.md (authoritative).
- Reference: `508782d6-...png` = a 1000×667 LOGICAL canvas at 1.536× (the PNG
  is 1536×1024). The user's field window: 1096×717 (now5.png framing).
- User authorized full autonomous execution incl. git push and release.
- AGENTS.md rules: content-agnostic code, incremental commit+push, green
  tests, release = VERSION bump + tag + GitHub Release + zip in
  /home/z/my-project/download/.

## C. Completed work (this session)
- ENV: repo at /home/z/elixir-work/Elixir; PySide6 in /home/z/.venv; Qt libs
  at /home/z/qt-libs/root (source /home/z/qt-libs/env.sh); offscreen OK.
- ROOT CAUSE FOUND: the V0.6.78-82 calibrations read the reference PNG's
  RASTER pixels (1536-wide) as LOGICAL px → all dashboard typography/density
  inflated ~1.536×. Round-4 recalibrates to the logical canvas.
- FONT: Manrope selected (real side-by-side vs IBM Plex Sans on the final
  layout — Plex wrapped the hero to 3 lines + wrapped the longest sidebar
  label; Manrope clean). Bundled 4 weights + OFL in assets/fonts/; Inter
  TTFs removed; loader renamed load_bundle_font; FONT_FAMILY leads Manrope.
- IMPLEMENTED (all in working tree, uncommitted):
  - theme.py: FONT dashboard scale (hero 27, tool 13, tool_desc 10, sidebar
    12, group 11, section 17, brand 22, eyebrow 10.5, body_lg 14), QSS
    retunes (TopBarAction, BackendPill, HeroPrimary asymmetric padding base,
    WinCtrl 32x28, SidebarGroup padding-left 8, #Hero weight bold).
  - dashboard_primitives.py: nav 27/34, icons 18/17/24, arrow 28 (retuned
    painter), card min-h 80, floor 230, chrome 90 (11/9/24/28/2×9), insets
    11/11/9/11 spacing 9, text_col spacing 3.
  - sidebar.py: RAIL_COMPACT_BELOW 188; brand row (34 leaf/22 wordmark,
    margins 16/14/12/10); nav host (10,2,10,4) spacing 2; group spacings
    10/6; FIXED footer region (divider+Settings+About OUTSIDE the scroll);
    tagline card (top 12, strip 46, ~100 total); wrap margins (12,6,12,10).
  - home_view.py: hero ratio 0.36 clamp [192,260], rhythm base 236, headline
    27 @700, spacers (22,8,10,20,8), HBox (24,2,0,0) spacing 14, page
    margins 16/18, hero→tools gap 12, head→grid 7, GRID_GAP 10, rows 80,
    grid_w/card_w margin fix (16/18), CTA asymmetric padding (L24/R40
    floors — fixes the constrained "Conversio→n" collision), softer washes
    (22/17/13 alphas, cx 0.76), support caps 400/370.
  - app.py: top-bar moon theme button REMOVED (spacing 26/20/18, divider
    30); _refresh_top_bar_icons cleaned; _toggle_theme kept (status menu).
- EVIDENCE captured in repo root: now5.png (1096×717 light), now5_dark.png,
  now5_wide.png (1440×900), now5_constrained.png (900×620, 2-col),
  now5_overlay.png + now5_difference.png (app 1000×667 shell vs reference).
- VERIFIED (live offscreen + VLM review): 3×3 grid at 1096×717 AND
  1000×667 AND 1440×900 AND 1280×800 (rows 80/80/80; 1000-canvas 80/80/87);
  2-col at 900×620; page min < viewport at all acceptance sizes; sidebar
  complete, no scrollbar, single-line labels at 197 rail; tagline compact +
  fully readable; ONE theme control; dark theme coherent; hero art blends
  (no rectangle). Structural parity at the matched 1000×667 shell: hero
  220/220, grid-top 315/319, row3 495/495, gap 10/10, card 251×80 vs
  238×77, rail 188 vs 173, topbar 50 vs 45, status 42/42.
- TESTS: tests/test_v0684_round4_density.py (30 tests) ADDED; pins updated
  in test_m1_theme_tokens.py (Manrope bundling + FONT scale) and
  test_v0683_round3_geometry.py (RAIL_COMPACT_BELOW 188, card constants,
  hero rule, gap 12, compact boundary). All 4 UI test files: 108 passed.
- ruff check + format: CLEAN on all changed files.
- DOCS: release_notes/V0.6.84.md written; CHANGELOG entry inserted;
  VERSION → 0.6.84; assets/fonts/README.md rewritten for Manrope.

## D. Current state (final)
- Full-suite validation DONE (identical exclusions on both trees):
  pristine HEAD → 8,585 passed / 20 failed; Round-4 tree → 8,617 passed /
  20 failed — the failure sets are BYTE-IDENTICAL (all 20 pre-existing
  sandbox issues: optional deps, ffmpeg stubs, CC lint gates; the golden
  prompt-manifest failure reproduces on the untouched tree). Zero
  regressions; +32 passed (the 30 new Round-4 tests + the 2 updated-pin
  collections).
- The full suite SEGFAULTS mid-run in this sandbox on BOTH trees when the
  threaded model-scan dialog tests run to completion (a third
  order-dependent offscreen-Qt crash variant — the V0.6.83.1 hotfix
  repaired the two CI ones; this one is environmental). Worked around by
  the same three-file exclusion on both trees for the comparison.
- ruff check + format: clean. AGENTS.md deny-list: green.
- Release artifacts: VERSION 0.6.84, CHANGELOG entry, release_notes/
  V0.6.84.md, the now5 evidence set at the repo root.

## E. Remaining work (in order)
1. Commit the focused set (everything in git status EXCEPT nothing — the
   full status IS the Round-4 set) and push origin main.
2. Tag V0.6.84; publish the GitHub Release via tools/publish_release.py
   V0.6.84 --zip /home/z/my-project/download/Elixir-V0.6.84.zip --token
   <one-off token from the session prompt; never log it>.
3. Create the zip in /home/z/my-project/download/ (AGENTS.md Rule 5).
4. Final verification: pull, confirm the commit on GitHub, verify the
   release URL and assets.

## F. Problems and considerations
- Sandbox: no root; Qt libs in /home/z/qt-libs/root; source env.sh first.
- resize() on a HIDDEN Qt widget sends no resizeEvent — the test helper
  calls view._relayout_quick_grid() explicitly after resize.
- The m1 import-quarantine test forbids the literal "dashboard_primitives"
  string in theme.py (reworded the comment to "the primitives module").
- _strip_comments() eats objectName selectors (QLabel#Hero) — use raw _src
  for QSS-rule pins.
- now4*.png and older now*.png evidence files remain in the repo root
  (previous rounds' history) — keep them.
- The GitHub token is in the session prompt only; never commit/log it.
- Full suite known-baseline failures (pre-existing, sandbox): verify the
  count matches V0.6.83's tally; investigate any NEW failure.

## G. Git and deployment status
- Branch main, up to date with origin at session start (2c84662).
- No commits yet this session. Release target V0.6.84.

## H. Next action
Check /tmp/suite_run.log (the background full-suite run); if the tally
matches the pre-existing baseline (no new failures), proceed to the git
commit + push + release sequence (section E steps 3-6).
