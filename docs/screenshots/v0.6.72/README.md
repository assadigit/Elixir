# V0.6.72 QA evidence — the six-cell matrix, offscreen renders

The M3 session's evidence set for the asset audit that answered the
user's report *"u still didn't use any image asset in the UI … you
can't find assets or you can't manage to display them?"*

| Cell | File | Hero (books/quill) | Sidebar brand card (misty hills) |
|---|---|---|---|
| 1280×800 light | `qa_1280x800_light.png` | visible, 260 px | visible |
| 1280×800 dark | `qa_1280x800_dark.png` | visible, 260 px | visible (dusk scrim) |
| 1440×900 light | `qa_1440x900_light.png` | visible, 260 px | visible |
| 1440×900 dark | `qa_1440x900_dark.png` | visible, 260 px | visible (dusk scrim) |
| 560×400 light | `qa_560x400_light.png` | hidden (spec §7 narrow rule) | hidden (rail < 520 px) |
| 560×400 dark | `qa_560x400_dark.png` | hidden (spec §7 narrow rule) | hidden (rail < 520 px) |

## Method (the corrected one)

Rendered offscreen (`QT_QPA_PLATFORM=offscreen`) at the **real launch
order** — `theme_manager.apply(app)` BEFORE the `ElixirWindow` exists,
exactly as `run()` does. An earlier probe pass skipped the apply step
and produced unstyled renders; those were discarded and every number in
the V0.6.71 changelog entry comes from the corrected method.

Programmatic assertions per cell (both themes): hero pixmap non-null +
visible + 1,506–1,577 unique colors in its rendered region; brand card
visible + 289–298 unique colors; top-bar background exactly `bg_window`;
toolbar icon luma spread ≈ 200. A VLM pass confirmed both assets render
cleanly with no layout defects (dark-theme hero glow noted as a taste
call for the user's verdict, not a defect).

## What the user should see on Windows

`Elixir-Setup-0.6.72.exe` (release `V0.6.72-windows`) — the first
installer cut from a tree that contains both image assets. The
V0.6.70 installer the user originally tested was built 2026-11-01
13:08 UTC, before either asset commit landed (13:26 / 17:13).
