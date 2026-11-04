# Bundled fonts — Manrope (primary) + Vazirmatn (RTL PDF output)

## Manrope — the primary UI typeface (V0.6.84, Round-4 §6 selection)

The app's UI type family is **Manrope** — a modern, refined, geometric
sans-serif selected for the approved reference's understated editorial
character. It replaces Inter (the M1 choice) after the Round-4
real-application comparison against IBM Plex Sans: Manrope kept the hero
headline's exact two-line lockup, every sidebar label on a single line,
and the more balanced card rhythm; Plex wrapped the hero headline to
three lines and wrapped the longest sidebar label at the same sizes
(the comparison evidence is recorded in release_notes/V0.6.84.md).

The four production weights ship inside the app:

- `Manrope-Regular.ttf` (400)
- `Manrope-Medium.ttf` (500)
- `Manrope-SemiBold.ttf` (600)
- `Manrope-Bold.ttf` (700)
- `Manrope-OFL.txt` — the SIL Open Font License 1.1 (keep with the fonts)

Source: the official [google/fonts repository](https://github.com/google/fonts)
(`ofl/manrope`), static instances generated with fonttools from the
`Manrope[wght].ttf` variable font. `ui_qt/theme.py::load_bundle_font()`
registers them on startup via `app_paths.bundle_dir()` (source and frozen
builds both resolve) and the QSS stack (`FONT_FAMILY` in `ui_qt/theme.py`)
resolves `"Manrope"` first — no settings change needed. If registration
ever fails the stack falls back to `"Segoe UI Variable"` → `"Segoe UI"` →
`"Helvetica Neue"` → Arial.

Manrope's license (SIL OFL 1.1) permits bundling and redistribution with
the application, including the compiled installer.

## Vazirmatn — the RTL output face (unchanged)

`Vazirmatn-Regular.ttf` / `Vazirmatn-Bold.ttf` feed the Persian (RTL)
PDF service outputs (see `core/outputs/service_formatters.py`) — they are
NOT part of the UI type stack.
