# ELIXIR — UI/UX Correction Round 3
## Window sizing, content container, responsive Quick Tools grid, and transparent hero artwork

**Purpose:** Correct the remaining structural differences between the current dashboard (`now3.png`) and the approved reference (`508782d6-4b80-48be-9046-d081ce258b75.png`).

**Priority:** The application window and main content container are the primary defects. Do not treat this as a minor spacing or styling pass.

**Visual source of truth:** `508782d6-4b80-48be-9046-d081ce258b75.png` in the repository root.

**Current screenshot:** `now3.png` in the repository root.

---

## 1. Audit summary

The current implementation retains the general visual language, but the usable dashboard area is too constrained.

Approximate observations from the supplied screenshots:

| Measurement | Current `now3.png` | Approved reference | Required direction |
|---|---:|---:|---|
| Screenshot canvas | 893 × 609 px | 1000 × 667 px | Use a larger, consistently framed app window for validation |
| Sidebar width | ~266 px (~30% of app width) | ~172 px (~17–18%) | Reduce sidebar share to ~17–19% |
| Main content start | ~307 px from image left | ~200 px from image left | Move main content substantially left by fixing sidebar allocation |
| Hero area | ~530 × 260 px | ~770 × 221 px | Give the hero a much wider content container and reduce its relative height |
| Quick Tools grid | One card per row | Three columns | Show 3 columns when space permits, 2 at normal/lower widths, 1 only when genuinely narrow |
| Hero artwork | Rectangular image with a visible background boundary | Artwork integrated into the hero background | Use an isolated transparent PNG foreground asset |

These are visual estimates from the screenshots, not source-code measurements. Confirm exact widget geometries at runtime before changing values.

### Core diagnosis

The small outer window and oversized sidebar compound each other:

1. The application window is too small for the intended desktop composition.
2. The sidebar consumes an excessive share of the available width.
3. The central content widget does not receive enough horizontal space.
4. The hero and tool grid are therefore forced into narrow layouts.
5. The Quick Tools grid collapses to one column even though the intended dashboard is a multi-column desktop layout.

Increasing only the window size will not fully fix the problem if the sidebar continues consuming approximately 30% of the width. Fix both levels.

---

## 2. Primary objective: give the application a properly sized desktop window

The approved dashboard is a desktop-first interface. Its default launch geometry must provide enough room for the hero and a useful multi-column tool grid without requiring the user to manually resize the window every time.

### 2.1 Startup window size

Inspect the current top-level window initialization and any saved geometry/state handling.

Implement this behavior:

- On a first launch with no saved user geometry, target a logical window size of approximately **1440 × 900 px**.
- Center the window on the active screen.
- Never request a window larger than the screen's available work area.
- If the available logical work area comfortably supports the target size, use the target size. Otherwise, use approximately 92% of the available work area, with sensible margins.
- On a screen whose available logical work area can comfortably support the target, the application may start maximized. Do not force fullscreen mode.
- On subsequent launches, restore the user's last valid window geometry/state, provided it fits the current screen. Do not keep restoring an old, accidentally tiny geometry from a previous version.
- When restoring saved geometry that is implausibly small for this dashboard, migrate/clamp it to a useful size or fall back to the new default.

Suggested desktop targets:

| Scenario | Desired behavior |
|---|---|
| Large desktop work area | Start around 1440 × 900, centered; maximize only if that is the established app convention and it improves the usable area |
| Typical 1366 × 768 logical work area | Use most of the available work area; retain a 2-column grid where possible |
| Smaller laptop / high Windows display scaling | Fit within the available logical work area; permit a 1-column fallback only when the content viewport is genuinely narrow |

**Important:** Qt widget dimensions are generally logical/device-independent pixels. Use `QScreen.availableGeometry()` and the actual Qt binding already used by the repository. Do not multiply dimensions by device pixel ratio manually unless the existing rendering architecture specifically requires it. Test Windows display scaling (100%, 125%, and 150%) where feasible.

### 2.2 Minimum size and resize behavior

- Define a useful minimum window size, but do not make the minimum larger than a small screen's available work area.
- Aim for a minimum logical width around 1100–1180 px on screens that can support it.
- Keep a practical minimum logical height around 700–760 px when the screen allows it.
- At the minimum supported size, the app must remain usable: no clipped navigation, overlapping controls, inaccessible buttons, or hidden content.
- If the usable height is insufficient, allow the **main content area** to scroll vertically. The sidebar and bottom status strip should remain stable. Do not create unnecessary nested scroll areas.

### 2.3 Geometry persistence

- Save and restore normal window geometry and maximized state using the application's existing settings mechanism.
- Validate restored geometry against the current screen's available area.
- Handle monitor changes, resolution changes, and stale saved settings safely.
- Do not introduce a new settings dependency solely for this behavior.

---

## 3. Primary objective: expand the central content container

This is the most important internal layout correction.

### 3.1 Sidebar width

The current sidebar occupies approximately 30% of the window, which is far too wide for this design.

Target:

- Sidebar should occupy approximately **17–19%** of the application width.
- Use a responsive width rule approximately equivalent to `clamp(180, 0.18 * window_width, 260)` logical pixels, subject to the actual layout and Qt version.
- At a 1440 px window width, expect a sidebar around 245–260 px.
- At a 1000 px window width, expect a sidebar around 180 px.
- The sidebar must not grow indefinitely when the window gets larger.
- Preserve the existing navigation labels, order, icons, and functionality.
- Do not solve this by making navigation text illegibly small or clipping labels.

Use the existing Qt layout system. A responsive sidebar may be controlled from the parent resize/layout logic, but do not use manual absolute positioning.

### 3.2 Main content stretch

- The main content area must receive all remaining horizontal space after the sidebar and required margins.
- Set the central content widget and its main layouts to expanding/flexible size policies where appropriate.
- Inspect all ancestors between the top-level window and the dashboard content for restrictive `minimumWidth`, `maximumWidth`, fixed widths, stretch factors, nested margins, or accidental size constraints.
- Remove obsolete fixed dimensions that prevent expansion.
- Make the hero and Quick Tools containers fill the available content width.
- Keep consistent left and right content insets, approximately 14–20 logical px at desktop sizes.
- The main content must not be clipped by a parent widget or hidden behind an overlay.

Do not use a fixed 530 px hero width, a fixed content width, or fixed widget coordinates. The main container should expand naturally with the window.

### 3.3 Header alignment

- Keep the top bar aligned to the main content region, not the full combined sidebar-plus-content area.
- Preserve the approved control sequence and visual hierarchy: backend/provider indicator, Settings, theme control, and native/custom window controls as implemented by the project.
- Do not let header controls consume the hero's width or overlap the content.
- Keep the header compact, roughly 44–52 logical px in height.

---

## 4. Quick Tools: responsive multi-column grid

The current one-card-per-row layout is not acceptable at the intended desktop size.

### 4.1 Required column behavior

Implement a real responsive grid, using the available Qt layout architecture (for example, a `QGridLayout` with controlled reflow, or the project's existing responsive grid component).

Use the **actual available Quick Tools content width**, not the full screen width, to determine the column count.

Target behavior:

| Quick Tools viewport width | Columns |
|---:|---:|
| 900 px and above | 3 columns |
| 600–899 px | 2 columns |
| Below 600 px | 1 column |

Treat these as initial thresholds. Refine them based on card minimum width and runtime measurements. The key requirement is that the normal desktop window should show multiple cards per row.

At a first-launch window around 1440 × 900, target **3 columns**.
At a typical laptop size around 1280 × 800, prefer **3 columns if each card still has a comfortable width; otherwise 2 columns**.
At the current 893 px screenshot width, after correcting the sidebar, the grid should show **at least 2 columns** if card readability permits.

### 4.2 Grid contents and order

Preserve the approved 3 × 3 ordering at the large desktop layout:

1. Summarization
2. Document → Markdown
3. Translation
4. Packets of Knowledge
5. OCR Service
6. PDF/DOCX Cutter
7. Image Extractor
8. Markdown Styler
9. Full Conversion Wizard (featured dark green card)

The featured Full Conversion Wizard card is an intentional visual entry point in the approved reference. It must launch the same existing wizard as the hero CTA and sidebar entry. Do not create a second wizard or duplicate processing implementation.

### 4.3 Card sizing

- Cards must expand evenly to fill each grid row.
- Set a sensible minimum card width; do not force a single column when two or three columns can fit.
- Keep card height compact and consistent with the reference's proportions.
- Use balanced internal padding, icon/title alignment, description line spacing, and trailing circular arrow affordance.
- Text must wrap naturally without truncation at supported sizes.
- The cards must not become excessively tall because of a vertical expanding size policy.
- Use consistent row and column gaps, approximately 12–16 logical px at desktop sizes.

### 4.4 Reflow implementation

- Recalculate column count when the Quick Tools viewport changes size.
- Remove/reinsert/reparent cards safely when reflowing, or use a layout implementation that supports responsive columns without destroying widget state/connections.
- Ensure each card's click handler remains connected after reflow.
- Avoid creating duplicate widgets during resize events.
- Avoid resize-event loops and excessive layout rebuilds.
- Test resizing continuously across each breakpoint, not just at three static sizes.

---

## 5. Hero artwork: isolate the books and quill into a transparent PNG

The current hero artwork appears inside a rectangular image area with its own baked-in background. That creates a visible boundary and causes the image background to collide with the hero's decorative background.

### 5.1 Required asset

The hero foreground should be a **transparent PNG (RGBA)** containing only the still-life foreground elements:

- The stacked books.
- The quill.
- The ink bottle / inkwell.
- Their natural contact shadows, if they can be retained cleanly.

It must not contain a rectangular cream/white background, backdrop shapes, landscape, or a second independent panel.

Inspect the existing package asset `assets/hero_books_quill.png` first. Reuse it only if it is actually isolated and has clean alpha transparency. Do not assume that the `.png` extension means the background is transparent.

If the asset is unsuitable, prepare a properly isolated RGBA PNG. Do not fake transparency by placing an opaque image on a similar-colored rectangle. If a clean asset cannot be produced with the available project assets/tools, report the blocker instead of shipping a visibly boxed image.

### 5.2 Alpha and asset validation

Before integrating the asset:

- Confirm that the image has an alpha channel.
- Confirm that background pixels around the objects are transparent (alpha 0 or suitably feathered), not opaque cream pixels.
- Inspect the asset over both light and dark checkerboard backgrounds.
- Ensure edges are clean, with no white/gray matte fringe or hard rectangular boundary.
- Preserve enough resolution for high-DPI scaling; avoid enlarging a small raster asset until it looks blurred.
- Keep the asset within the project's existing asset directory and loading/resource conventions.

### 5.3 Hero composition and layering

Build the hero as layered composition:

1. Hero base surface and warm ivory gradient/tint, if already used in the design.
2. Subtle translucent background shapes / landscape elements belonging to the hero background.
3. Transparent foreground still-life PNG above the background.
4. Hero text and CTA in their protected text area.

The foreground PNG must blend with the existing hero background. It must not introduce a separate rectangular panel. Clip the complete composition to the hero's rounded corners if required.

- Keep the text area clear and readable.
- Keep the illustration on the right side.
- Scale with `KeepAspectRatio` / equivalent behavior; never stretch non-uniformly.
- Use intentional cropping only if it matches the approved composition and does not cut off the quill, books, or inkwell.
- The image must not spill into the Quick Tools section below the hero.
- Support both Light and Dark themes. A light-only baked background is not acceptable.

---

## 6. Vertical space and full dashboard visibility

A larger startup window should allow the intended dashboard to breathe. Do not compensate for a short window by shrinking all components until they become cramped.

At approximately 1440 × 900:

- Header: around 44–52 px.
- Hero: approximately 220–250 px, adapting gently to available space.
- Gap between hero and Quick Tools: approximately 24–32 px.
- Quick Tools heading: approximately 28–34 px high.
- Tool cards: compact and balanced; avoid excessive height.
- Bottom status strip: approximately 38–44 px.
- All three rows should be visible without requiring vertical scrolling at the target desktop size, provided the available height supports it.

At smaller window heights, vertical scrolling may be used for the main dashboard content. It must not cause clipping or overlap. The sidebar and status strip should not scroll with the cards unless the existing application architecture has a deliberate, documented reason.

---

## 7. Qt implementation diagnostics — mandatory

Before changing layout constants, inspect and record runtime geometry for:

- Top-level main window.
- Central widget.
- Main horizontal layout.
- Sidebar widget.
- Main content widget.
- Top bar.
- Hero container and text/artwork subregions.
- Quick Tools viewport/container.
- Quick Tools grid and individual cards.
- Bottom status strip.

For each relevant widget inspect:

- `geometry()` / `size()` / `contentsRect()`.
- `minimumSize()` and `maximumSize()`.
- `sizePolicy()`.
- Layout contents margins and spacing.
- Parent-child hierarchy.
- Horizontal and vertical stretch factors.

Check carefully for:

- `setFixedWidth`, `setFixedSize`, and oversized `setMinimumWidth` calls.
- A parent container with an unintended maximum width.
- A scroll area's child widget not expanding to viewport width.
- Wrong `QSizePolicy` values.
- Nested layouts adding margins multiple times.
- A grid configured with one column or cards inserted in a vertical layout.
- A `QSplitter` with incorrect initial sizes or stretch factors, if one is used.
- DPI scaling assumptions or manual multiplication by devicePixelRatio.
- Stale saved window geometry.

Use the repository's existing Qt binding and established coding conventions. Do not migrate frameworks or introduce new dependencies.

---

## 8. Visual acceptance tests

Capture screenshots of the actual running application—not a mockup—at these logical window sizes where the display supports them:

1. 1440 × 900 (primary acceptance target).
2. 1280 × 800 (laptop / constrained desktop).
3. 1100 × 760 (minimum-size stress test, or the closest feasible size).

Also test the actual maximized state on the development machine.

For each size:

- Capture the complete application window with no unrelated desktop/window content.
- Keep the same DPI scale and screenshot method for before/after comparisons.
- Ensure the application is not partially off-screen.
- Record the window size and available screen geometry in the report.

### Primary acceptance at 1440 × 900

- Window opens at a useful large size or maximized state, not the current compact geometry.
- Sidebar occupies approximately 17–19% of app width, not ~30%.
- Main content expands to use the available width.
- Hero is wide and balanced, not a narrow tall panel.
- Hero headline and description are fully visible.
- The hero still-life image has no rectangular background boundary.
- Quick Tools shows 3 columns with the expected card order.
- All nine Quick Tools cards are present, including the featured Full Conversion Wizard card.
- Cards are aligned and evenly spaced.
- No horizontal scrollbar is visible.
- No accidental clipping or overlap occurs.
- The status strip remains anchored at the bottom.

### Acceptance at 1280 × 800

- At least 2 columns; 3 if the measured card width remains comfortable.
- No text or controls clipped.
- No overlap between hero art and text.
- Layout remains balanced and usable.

### Acceptance at 1100 × 760 or the smallest supported size

- Use 2 columns if the available content width permits; use 1 only when necessary.
- No clipped navigation or inaccessible controls.
- Main content scrolls vertically only as necessary.
- The status strip does not cover content.

### Theme tests

Repeat the primary test in Light and Dark themes. The transparent hero PNG must blend correctly in both.

---

## 9. Screenshot evidence and comparison

Create these files in the repository root or the project's existing visual-QA directory:

- `now4_1440x900.png`
- `now4_1280x800.png`
- `now4_minimum.png`
- `now4_dark.png`
- `now4_reference_overlay.png` (normalized/aligned overlay when feasible)
- `now4_difference.png` (pixel difference image when feasible)

The supplied reference is 1000 × 667, so normalize image dimensions and align the application window bounds before overlaying. A raw overlay between differently sized screenshots is not a meaningful comparison.

Do not distort either image to force a match. Use consistent scaling/aspect-ratio handling and compare relative component geometry.

---

## 10. Implementation boundaries

- Preserve all existing tools and their behavior.
- Preserve the Full Conversion Wizard workflow and processing logic.
- Preserve backend integrations and provider selection.
- Preserve Light/Dark theme switching.
- Do not redesign unrelated screens.
- Do not add features unrelated to this correction.
- Do not replace real controls with decorative placeholders.
- Do not hide content to make the layout appear clean.
- Do not force fixed absolute positions.
- Do not solve the sidebar issue by shrinking text to an unreadable size.
- Do not use an opaque hero image with a fake matching background color.
- Do not introduce new runtime dependencies without a strong reason and explicit reporting.
- Do not delete existing functionality.
- Do not commit, push, publish a release, or deploy without explicit authorization.

---

## 11. Required final report

Provide:

1. Root causes found in the current window/container geometry.
2. Original and corrected window dimensions.
3. Original and corrected sidebar width and percentage.
4. Actual main content width before and after.
5. Quick Tools column count at each test size.
6. Hero PNG filename, pixel dimensions, color mode, and alpha validation result.
7. Exact files changed and why.
8. Screenshots listed in Section 9.
9. Light and Dark theme test results.
10. Functional/regression test results.
11. Remaining visual differences from the approved reference.
12. Final Git status, including whether any existing user changes remain untouched.

Do not claim 99% visual similarity without screenshot evidence. If the acceptance tests fail, identify the remaining blocker and continue correcting it where feasible.

**Completion condition:** The app must launch at a useful desktop size, allocate most of its width to the main content, display a 2- or 3-column Quick Tools grid at normal desktop sizes, and render the books/quill foreground as a clean transparent PNG integrated into the hero background.
