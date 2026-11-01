# Inter Font — bundled (M1 of the UI/UX redesign)

This app is designed to use **Inter** — an open-source typeface that matches
SF Pro's class and renders crisply at both the compact 11px dialog body size
and the larger dashboard type of the approved redesign.

## Status: BUNDLED (since the M1 visual-foundation milestone)

The four production weights ship inside the app (decision §8 Q4 of the
M0 recon report, user-approved):

- `Inter-Regular.ttf` (400)
- `Inter-Medium.ttf` (500)
- `Inter-SemiBold.ttf` (600)
- `Inter-Bold.ttf` (700)
- `Inter-LICENSE.txt` — the SIL Open Font License 1.1 (keep with the fonts)

Source: the official [Inter 4.1 release](https://github.com/rsms/inter/releases)
(`extras/ttf/` static instances, byte-unmodified). `ui_qt/theme.py::
load_inter()` registers them on startup and the QSS stack
(`FONT_FAMILY` in `ui_qt/theme.py`) resolves `"Inter"` first — no settings
change needed.

The static instances carry the standard dual naming (legacy family
"Inter Medium"/"Inter SemiBold" for pre-RIBBI weights + typographic family
"Inter"); Qt's DirectWrite backend on Windows — the shipping platform —
registers all four under the family **Inter** with the correct weights, so
QSS `font-weight: 500/600` resolves as intended. On fontconfig platforms
those two weights may register as separate families and match approximately
(the visual fallback stack below still applies).

## If Inter is somehow absent

The app falls back transparently to:

    Segoe UI Variable  →  Segoe UI  →  Helvetica Neue  →  Arial

(Segoe UI Variable is the default on Windows 11; Segoe UI on Windows 10.)
The UI still looks clean and professional — Inter is an enhancement, not a
requirement. `Vazirmatn-Regular/Bold.ttf` (also OFL) remain bundled for
Persian/Arabic script coverage.
