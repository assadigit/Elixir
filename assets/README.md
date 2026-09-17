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

Place PNG files here named after the preset keys to override the default SVG
icons on the home screen and in the Process Wizard. Recommended size: 128×128px
with transparent background.

| Preset Key              | File Name                    | Default SVG Icon | Shows On     |
|-------------------------|------------------------------|------------------|--------------|
| `normal_book`           | `icons/normal_book.png`      | book             | Home + Wizard |
| `academic_paper`        | `icons/academic_paper.png`   | file-text        | Home + Wizard |
| `visual_catalogue`      | `icons/visual_catalogue.png` | newspaper        | Home + Wizard |
| `infographics_slides`   | `icons/infographics_slides.png` | image         | Home + Wizard |
| `full_ocr`              | `icons/full_ocr.png`         | scan             | Wizard only   |
| `mixed`                 | `icons/mixed.png`            | layers           | Wizard only   |

## Placeholder Files

This directory ships with **.txt placeholder files** (not .png) so you know
exactly which files to create. Each .txt file contains:
- The expected filename (e.g., `normal_book.png`)
- The recommended size (128×128px, transparent)
- A description of what the icon represents

To customize:
1. Delete the .txt file (e.g., `icons/normal_book.txt`)
2. Add your PNG with the same name (e.g., `icons/normal_book.png`)
3. Restart the app — your custom icon appears automatically

## Fallback Behavior

If a PNG file does not exist, the app automatically falls back to the built-in
SVG icon (Lucide-style line icons rendered at runtime). You can safely delete
any placeholder you don't have custom artwork for — the SVG icons look clean
and match the theme.
