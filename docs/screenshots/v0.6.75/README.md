# V0.6.75 QA evidence — the hero matches the reference at the user's width

The answer to the user's report *"Still see the hero part of the visual
reference and compare with our output, you need to add those pictures.
FOR EXAMPLE YOU DIDN'T USE THIS: hero_books_quill.png"* (with the
reference mockup `508782d6-4b80-48be-9046-d081ce258b75.png`, also at the
repo root).

## What was actually wrong

The asset WAS wired (V0.6.71) — but the V0.6.72 evidence matrix only
covered 1280×800, 1440×900 and 560×400, and the sizing rule (fixed
200/260 px buckets, hidden below 760 px of content) meant the user's
actual ≈890 px window (≈660 px of content after the sidebar) rendered a
text-only hero. The reference mockup's hero is a two-column editorial
split with the books/inkwell/quill still-life filling ~half of it.

## The V0.6.75 rule

The illustration budget is **proportional**: ~45% of the view width,
clamped to 180–430 px in 20 px steps, hidden only below a 500 px content
floor (only the 560×400 minimum window's content band lands there).
Plus the reference hero's anatomy: the "WELCOME TO ELIXIR" eyebrow
(`QLabel#Eyebrow`), the reference support line, the pill CTA
(`border-radius: 18px` — Qt QSS does NOT clamp an oversized 999 px radius
to a pill; measured nearly square), the play glyph, and the tinted
`QFrame#HeroCard` container the mockup shows (the illustration now
flattens against `bg_elevated`, in sync with that rule).

**The deadlock escape (found by the 560-cell):** a QLabel's
content-derived layout minimum IS its pixmap size, so a proportional
pixmap can inflate the window's minimum above the width that would
shrink it — the 560 px minimum window became unreachable and even the
760×540 default geometry self-expanded. `setMinimumSize(1, 1)` on the
visual drops the layout minimum 357 → 78 px while the label still takes
its pixmap size when the room exists. Measured: 760×540 requested →
760 px wide kept, hero visible at 240 px.

## The matrix (measured on this tree)

| Cell | File | Hero (books/quill) | pixmap | unique colours |
|---|---|---|---|---|
| 894×645 light (the user's window) | `qa_894x645_light.png` | **visible** | 300 px | 10,827 |
| 894×645 dark | `qa_894x645_dark.png` | **visible** | 300 px | 11,178 |
| 1536×1024 light (reference width) | `qa_1536x1024_light.png` | **visible** | 420 px | 16,932 |
| 1536×1024 dark | `qa_1536x1024_dark.png` | **visible** | 420 px | 17,226 |
| 560×400 light (minimum window) | `qa_560x400_light.png` | hidden (spec §7) | — | — |
| 560×400 dark | `qa_560x400_dark.png` | hidden (spec §7) | — | — |

The content-width sweep (HomeView standalone): 660 px → 280 px visual
(was: HIDDEN — the user's case), 760 → 340, 900 → 400, 1100+ → 420.

## Method

Offscreen (`QT_QPA_PLATFORM=offscreen`), theme applied before any view
exists (the real launch order). **Composed shell**: the real `Sidebar` +
the real `HomeView` under the real QSS — not the full `ElixirWindow`
(that needs a live `Controller`; the V0.6.72 full-window rig was
throwaway and never landed in the repo). The renders are taller than the
requested heights because the composed mock lacks the real window's
`QScrollArea` wrapper (`ui_qt/app.py` `_wrap_scroll`) — width behaviour,
which is what the hero affects, is unaffected. A VLM pass against the
reference confirmed: illustration prominent, eyebrow/heading/support/pill
present, tinted container present, sidebar brand card present, no
blocking defects.

Structural pins: `tests/test_m2_dashboard.py` +
`tests/test_m1_theme_tokens.py` — 48 passed (the 5 Qt-instantiating
theme tests included, via a local libEGL extraction).
