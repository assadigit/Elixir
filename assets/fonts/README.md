# The primary typeface — bundled (Round-4 UI/UX correction, V0.6.84)

This app renders its whole UI in **IBM Plex Sans** — an open-source
humanist sans-serif with an editorial, academic character that matches
the Quiet Grove design language (warm ivory paper, charcoal ink, muted
forest-green accents, books-and-quill hero: a "quiet reading room").

## Status: BUNDLED (since V0.6.84; replaced Inter)

The four production weights ship inside the app:

- `IBMPlexSans-Regular.ttf` (400)
- `IBMPlexSans-Medium.ttf` (500)
- `IBMPlexSans-SemiBold.ttf` (600)
- `IBMPlexSans-Bold.ttf` (700)
- `IBMPlexSans-OFL.txt` — the SIL Open Font License 1.1 (keep with the fonts)

`ui_qt/theme.py::load_primary_fonts()` registers them on startup (resolved
through `app_paths.bundle_dir()`, so frozen PyInstaller builds find them)
and the QSS stack (`FONT_FAMILY` in `ui_qt/theme.py`) resolves
`"IBM Plex Sans"` first — no settings change needed. When the files are
absent (thin bundles) the stack falls back to **Segoe UI Variable →
Segoe UI → Helvetica Neue → Arial**, and the dashboard's measured-reflow
logic adapts to whatever metrics the running stack reports.

The RTL/output side keeps its own bundled face: `Vazirmatn-Regular.ttf` /
`Vazirmatn-Bold.ttf` (SIL OFL 1.1) for Persian PDF/DOCX outputs
(`core/outputs/service_formatters.py`).

## Provenance

Static instances generated with fontTools `instancer` from the official
Google Fonts variable files (OFL 1.1):

- `IBMPlexSans[wdth,wght].ttf` — pinned to `wdth=100`, instantiated at
  wght 400/500/600/700, name records rewritten so Qt registers every
  weight under the single family **IBM Plex Sans** with the correct
  style (Regular/Medium/SemiBold/Bold — verified with
  `QFontDatabase.styles()` on the offscreen/Windows-compatible stack).
- Source: <https://github.com/google/fonts/tree/main/ofl/ibmplexsans>
  (© IBM Corp., SIL OFL 1.1 — the license file ships alongside).

## The Round-4 evaluation record (spec §6.1/§6.3)

`ELIXIR_UI_UX_CORRECTION_ROUND_4.md` required an in-app comparison of
**Manrope** (the preferred first candidate) and **IBM Plex Sans** before
finalizing the primary face. Both were bundled and rendered through the
production theme pipeline in the REAL dashboard — light + dark, at the
compact 1096×717 window and the 1536×1024 reference canvas — and reviewed
side by side (headline wrapping, card density, navigation legibility,
overall character):

- **Editorial character / brand fit** — Plex wins. The reference is
  "understated and editorial" (spec §6.2); Plex's humanist details,
  angled terminals, and reportorial lineage sit naturally with the
  books/quill identity, while Manrope reads as modern-SaaS geometric.
- **Compact-density metrics** — Plex wins. Narrower advance widths
  (the longest card title inks 152 px vs Manrope's 156 at 14 px):
  sidebar labels wrap less ("Packets of Knowledge" holds one line at
  the 197 px rail), the featured card's description lands two lines
  (91 px card) instead of three (95 px), and the page closes its
  height budget at the user's window with more slack.
- **Small-size crispness** — Plex wins. Taller x-height and slightly
  condensed forms keep 11–13 px card/sidebar text sharp; Manrope's
  rounder wide forms soften at the same sizes.
- **Manrope's** advantages — a warmer, rounder tagline voice and very
  open apertures at display sizes — did not outweigh the above for an
  understated editorial dashboard.

Decision: **IBM Plex Sans**, weights 400/500/600/700, bundled as above.
The evaluation harness (`scripts/r4_font_eval.py`) and both candidates'
captures are retained in the session evidence; no runtime font picker
exists in the UI (spec §6.3: "This is a design decision, not a new
user-facing feature").
