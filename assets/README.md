# Assets Directory

This directory holds optional PNG assets that override the built-in SVG icons.

## Brand Logo

**File:** `assets/logo.png`

If present, this image is used as the app logo in the top bar (instead of the
default book icon). Recommended size: 200×40px (or any aspect ratio that looks
good at 26px height). Transparent background recommended.

A `logo.txt` placeholder is shipped — it tells you the expected filename.
Delete it and add `logo.png` to customize.

## Preset Icons

**Directory:** `assets/icons/`

The six document-type modes ship with PNG artwork (256×256px, transparent
background, hand-drawn "mode" set supplied by the project owner — extracted
from `Elixir-Document-Type-Modes.zip` at the repo root). They replace the
Lucide SVG line icons on the home screen and in the Process Wizard.

| Preset Key              | File Name                    | Artwork                     | SVG Fallback | Shows On     |
|-------------------------|------------------------------|-----------------------------|--------------|--------------|
| `normal_book`           | `icons/normal_book.png`      | Book-mode                   | book         | Home + Wizard |
| `academic_paper`        | `icons/academic_paper.png`   | Academic-Paper-mode         | file-text    | Home + Wizard |
| `visual_catalogue`      | `icons/visual_catalogue.png` | Journal-mode                | newspaper    | Home + Wizard |
| `infographics_slides`   | `icons/infographics_slides.png` | Infographic-Slides-mode  | image        | Home + Wizard |
| `full_ocr`              | `icons/full_ocr.png`         | Full-OCR-Mode               | scan         | Wizard only   |
| `mixed`                 | `icons/mixed.png`            | Mixed-Mode                  | layers       | Wizard only   |

The artwork is cream/paper-toned with dark outlines, so it reads on both the
light and dark themes without recolouring.

## Replacing the Artwork

To customize any preset icon:
1. Replace the PNG (e.g., `icons/normal_book.png`) with your own — keep the
   same filename; 128–256px square, transparent background recommended.
2. Restart the app — your icon appears automatically.

## Fallback Behavior

If a PNG file does not exist, the app automatically falls back to the built-in
SVG icon (Lucide-style line icons rendered at runtime). You can safely delete
any placeholder you don't have custom artwork for — the SVG icons look clean
and match the theme.
