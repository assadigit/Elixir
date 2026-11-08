# ELIXIR — UI/UX Correction Round 2

**Objective:** Correct the current dashboard implementation (`now2.png`) so that its composition, spacing, sizing, hierarchy, and component behavior closely match the approved reference (`508782d6-4b80-48be-9046-d081ce258b75.png`). This is a corrective pass, not a redesign.

**Primary visual target:** the approved reference image in the repository root.  
**Current baseline:** `now2.png` in the repository root.  
**Acceptance target:** at least 99% *perceived composition/style similarity* at a matched viewport, with no clipping, overlap, accidental scrolling, truncated text, or broken responsive behavior. Do not claim literal 99% pixel identity across different operating systems, display scaling, or font rasterizers.

---

## 1. Audit summary: what is visibly wrong in `now2.png`

The current screenshot has the correct general visual language, but the layout is not behaving like the reference. The key problem is not a lack of decorative polish: it is incorrect space allocation and content sizing. The sidebar consumes too much width, the central content is squeezed, the hero text is constrained, the Quick Tools area is clipped, and the vertical layout wastes space while showing too little content.

### P0 — Fix before any visual polishing

1. **The application window occupies too little of the captured canvas.** In `now2.png`, the app is inset by a large amount and part of another dark application/window is visible behind it, especially above and to the left. The reference fills nearly the entire image canvas. This makes the comparison misleading and reduces the usable dashboard area. Capture a clean app-window screenshot at the reference geometry; do not include unrelated desktop/window content.
2. **Sidebar is disproportionately wide.** In the current screenshot it takes roughly 28–31% of the visible app width, while the reference is approximately 18%. The sidebar squeezes the main page and is the main reason the hero and cards cannot breathe.
3. **Main content is horizontally clipped.** The Quick Tools heading's “View all” action is cut off; the second card is cut at the right edge; the third column is absent. There must be no unintended horizontal overflow or clipped cards.
4. **Hero content is clipped/over-constrained.** The headline wraps into an incomplete/extra line, body copy is squeezed, and the CTA appears visually compromised. The headline, description, and button must be fully visible, non-overlapping, and legible.
5. **Vertical content density is wrong.** The current dashboard shows only the first row of tools before reaching the bottom status area. The reference shows all three rows of the tool grid. The current cards are much taller than the reference and the gaps between sections are too generous.
6. **The dashboard scroll area is exposing a scrollbar at the reference-sized layout.** The reference dashboard fits without a visible vertical scrollbar. At the reference viewport, the complete hero, title row, all three card rows, sidebar items, and footer should fit.

### P1 — Correct the geometry and component proportions

7. **Top bar is too tall / vertically consumes too much space.** Reduce its height and align it with the compact header in the reference.
8. **Main page horizontal padding is too large for the available width.** Use consistent, smaller page insets matching the reference; do not let nested containers add multiple layers of padding.
9. **Quick Tools cards are oversized.** The current first card is far taller and wider than the compact reference card. Use a 3-column grid at the reference viewport, with uniform card dimensions and compact internal padding.
10. **Sidebar vertical rhythm is too loose and incomplete in the capture.** The reference shows the full tool list, Settings, About, and the anchored tagline panel. Ensure all intended navigation items are visible at the reference viewport.
11. **Bottom status bar is too tall.** Reduce its height and align its left status region with the sidebar boundary as in the reference.
12. **The hero artwork is too dominant relative to the available text column.** Preserve the approved books-and-quill artwork but rebalance the hero into a clear text region and artwork region.

### P2 — Fine visual matching

13. Refine typography sizes, weights, line heights, and text colors to match the reference hierarchy.
14. Match card border contrast, radius, subtle surface tint, arrow-button size, and icon scale.
15. Match the muted forest-green hero CTA and featured Full Conversion card, restrained shadows, and warm ivory surface tones.
16. Match alignment and baseline consistency across sidebar labels, card titles, icons, header controls, and footer labels.

---

## 2. Reference geometry and layout rules

Use the reference image as a composition guide, not as a reason to hardcode a single screenshot's pixel positions. Measure the actual target window/client area, then implement proportional layout with sensible minimums and breakpoints.

### Primary screenshot acceptance viewport

Use a clean captured image with the application window occupying approximately the same share of the canvas as the reference. The supplied reference image is 1000 × 667 pixels; its application frame occupies almost the full canvas. The current screenshot includes unrelated desktop/window content and a much smaller app frame. For the primary visual comparison:

- Set the app to a matching client/window size and display scaling.
- Capture the app itself, not a partial desktop with another window visible behind it.
- Keep the same OS display scale and font environment between baseline and final capture where possible.
- Crop consistently to the outer app frame, with the same outer margin as the reference.
- Do not resize one screenshot non-uniformly to fake a match.

### Layout proportions to target

Use these as initial targets at the reference viewport; adjust only when required by the existing Qt window/client geometry:

| Region | Reference proportion / target | Required correction |
|---|---|---|
| Sidebar | About 17–19% of app width | Reduce substantially from current ~28–31% appearance |
| Content inset | About 14–18 px at 1000 px reference width | Remove excessive/nested padding |
| Top bar | Compact, around 44–48 px in the reference capture | Reduce current tall header area |
| Hero | Around 220 px high in the reference capture | Keep shallow/wide; do not let it dominate vertical space |
| Hero text area | Roughly 50–55% of hero width | Give heading/description/CTA sufficient width |
| Hero artwork | Roughly 45–50% of hero width | Keep artwork right-aligned and visually integrated |
| Quick Tools grid | 3 equal columns | All columns fully visible at reference viewport |
| Quick Tools card | Roughly 80–85 px high in reference capture | Reduce current oversized card height |
| Grid row/column gaps | Tight and consistent, around 7–12 px | Avoid large vertical gaps |
| Bottom status bar | Roughly 38–42 px high in reference capture | Reduce current oversized footer |

These pixel values describe the 1000 × 667 reference screenshot, not universal physical pixel sizes. Scale through layout proportions and device-independent Qt sizing.

### Sidebar

- Keep a fixed sidebar, but target approximately 18% of the app's inner width at the reference viewport.
- The sidebar must not force the content area below the width needed for the reference 3-column dashboard.
- Keep the brand mark/wordmark at the top, Home selected, the complete tool list, Settings and About, and the small tagline/landscape panel anchored near the bottom.
- Preserve the approved navigation order and exact feature names from the existing application.
- Use one consistent horizontal inset for sidebar logo, selected row, and menu items.
- Prevent the menu from being vertically clipped. At smaller window heights, allow the sidebar's menu region to scroll independently if required; keep brand and bottom utility behavior deliberate rather than letting content overlap.
- Do not add new navigation destinations.

### Top bar

- Keep the top bar aligned only with the main content area, not visually merged with the sidebar.
- Match the reference order and compact spacing: backend/server selector, Settings, theme icon/control, and native window controls.
- Keep text labels where the reference uses them (not merely isolated icons), especially Settings.
- Keep controls vertically centered and at one consistent height.
- The top bar must not consume excessive vertical space or push the hero down.
- Preserve real backend selection and Settings actions. Do not replace functional controls with decorative placeholders.

### Hero panel

- Use the wide, shallow hero proportion shown in the reference.
- Left content region must accommodate the headline in **exactly two lines** at the reference viewport:
  - `Turn documents into`
  - `clear, structured knowledge.`
- The full heading must remain visible. Never clip the final word, cut line height, or truncate via fixed label height.
- Description should display in two lines at the reference viewport:
  - `Books, articles and documents — summarized, organized`
  - `and ready for you to explore.`
- CTA sits beneath the description, with clear separation. No collision or overlap with the image or headline.
- Artwork remains on the right. It must not cover or constrain the text column.
- Keep the subtle translucent abstract forms and low-contrast landscape backdrop from the reference. Do not add stronger gradients, extra illustration elements, or visual effects.
- The hero should not become taller simply because the text label has an incorrect size policy. Fix its layout constraints.

### Quick Tools section

- Section title on the left with the green lightning icon.
- `View all tools →` on the far right, always fully visible and aligned to the title baseline.
- Use a true responsive grid with equal column widths and equal card heights.
- At the primary reference viewport: **3 columns × 3 rows**, including the dark green Full Conversion Wizard feature card in the bottom-right position, matching the reference.
- Keep the card order shown in the reference:
  1. Summarization
  2. Document → Markdown
  3. Translation
  4. Packets of Knowledge
  5. OCR Service
  6. PDF/DOCX Cutter
  7. Image Extractor
  8. Markdown Styler
  9. Full Conversion Wizard (featured dark green card)
- The Full Conversion Wizard card is a visual entry point to the existing wizard. It must route to the same existing action as the main hero CTA; do not create a second wizard, duplicate workflow, or new feature.
- Each standard card has: icon on the left, title and short description, circular arrow affordance on the right.
- Maintain readable text wrapping. Descriptions may use two lines; do not shrink text until it becomes tiny.
- Do not allow card width or content to exceed its grid cell. Do not let one card's minimum width force the grid off-screen.
- At smaller widths, collapse deliberately: 2 columns when 3 cannot fit comfortably, then 1 column when 2 cannot fit. Never clip cards or create horizontal scrolling.

### Bottom status bar

- Keep a persistent, compact status strip across the bottom.
- `Ready` status remains at the left, with its small green indicator.
- Theme control remains at the far right.
- Align the sidebar/content dividing line with the sidebar boundary.
- The footer must not cover the last row of cards or reduce the scroll viewport unexpectedly.

---

## 3. Diagnose and fix the layout root causes (do not patch symptoms)

Before changing style values, inspect the Qt widget/layout tree responsible for the dashboard. Identify why the sidebar is too wide, why content overflows, why hero labels clip, and why cards are too tall.

### Required technical audit

Check for:

- Hardcoded `setGeometry`, `move`, `resize`, fixed widths, fixed heights, and minimum sizes that conflict with the target layout.
- Layouts nested inside other layouts with duplicated margins or spacing.
- Child widgets with large `minimumSize` values that force overflow.
- `QSizePolicy.Fixed` or `Minimum` where `Expanding`/`Preferred` is appropriate.
- Grid columns without stretch factors or equal sizing.
- QLabel word-wrap settings, height-for-width behavior, font metrics, and fixed-height labels.
- Hero art widgets with oversized minimum widths or incorrect stretch factors.
- `QScrollArea` configured with `setWidgetResizable(False)` or a child content widget wider than its viewport.
- Scroll areas whose content widget has an explicit width that does not update when the viewport changes.
- A horizontal scrollbar or hidden overflow caused by nested widgets.
- Font/DPI scaling that changes widget dimensions unexpectedly.
- Footer/status widget inserted into the scrollable content instead of being anchored to the main window.
- Sidebar footer/tagline panel taking space from the menu without a deliberate layout strategy.

### Qt implementation rules

Adapt these to the repository's real binding and architecture; do not blindly rewrite everything:

- Prefer layout managers (`QHBoxLayout`, `QVBoxLayout`, `QGridLayout`) over manually positioned widgets.
- Use stretch factors to express the sidebar/content relationship and the hero text/art balance.
- Use a true equal-column `QGridLayout` for tool cards, with column stretch factors set equally.
- Use `QSizePolicy` deliberately. Text and card content should be allowed to expand or wrap rather than being clipped by fixed dimensions.
- Use `QLabel.setWordWrap(True)` where the design requires wrapping, but also give the label a sufficient width and appropriate size policy.
- Avoid setting fixed heights on text-bearing widgets unless their font metrics and all supported DPI scales have been verified.
- If a `QScrollArea` is needed, make the content widget track the viewport width and prevent accidental horizontal scrolling. Keep the bottom status strip outside the page scroll area.
- Apply layout margins and spacing at one clearly defined level; do not stack container padding unknowingly.
- Use device-independent dimensions and account for high-DPI scaling.
- Preserve the actual Qt binding, existing architecture, signal/slot connections, navigation, and business logic.

**Do not** solve clipping by shrinking all fonts, hiding text, turning off word wrap, forcing a tiny fixed window, or placing widgets over each other with manual coordinates.

---

## 4. Behavior and scope constraints

This is a dashboard layout correction. Preserve existing functionality.

- Do not redesign the 10-step Full Conversion Wizard in this task.
- Do not change conversion logic, settings semantics, model/backend connections, or tool behavior.
- Do not rename tools or invent features.
- Do not remove experimental backend functionality. Only retain the current approved navigation visibility decisions.
- Keep both Light and Dark themes functional. This correction may refine dashboard dimensions and shared styling, but must not break the other theme.
- Keep the hero CTA and featured wizard card connected to the same existing wizard launch path.
- Keep all secondary tool cards connected to their existing destinations.
- Preserve working native window behavior: drag, resize, minimize, maximize/restore, and close. If a custom title bar exists, do not regress it.
- Do not add dependencies unless absolutely necessary; justify any new dependency first.
- Avoid unrelated refactoring.

---

## 5. Required correction workflow

Do not make a large batch of speculative style edits. Work in controlled steps.

### Step 1 — Capture and measure

1. Launch the current application.
2. Capture the current dashboard at the same viewport and display scaling as the reference.
3. Record the actual outer-window size, client size, sidebar width, top bar height, hero size, content margins, card dimensions, and footer height.
4. Inspect widget/layout ownership for every visible clipping/overflow issue.
5. Write down the causes before changing code.

### Step 2 — Fix macro geometry

Correct in this order:

1. App-window capture/geometry consistency.
2. Sidebar width and main-content allocation.
3. Main content margins and scroll viewport.
4. Top bar height and alignment.
5. Hero height, text/art split, text wrapping, and CTA position.
6. Quick Tools section and true 3-column grid.
7. Card dimensions and internal alignment.
8. Footer height and anchoring.

Do not spend time on tiny icon/color differences before the layout is correct.

### Step 3 — Fix responsive behavior

Test at minimum:

- Reference viewport: 1000 × 667 capture canvas / app nearly filling the canvas, matching the supplied reference.
- A wider desktop viewport (for example 1440 × 900).
- A reduced desktop viewport (for example 900 × 650).
- A smaller supported window size, if the app supports it.

At reference and wider desktop sizes, reproduce the 3-column dashboard and keep the full content visible. At smaller widths, collapse to 2/1 columns without clipping or horizontal scrolling. At shorter heights, allow vertical scrolling gracefully rather than overlapping the status bar or hiding content.

### Step 4 — Refine styling

Only after the geometry passes:

- Tune typography, line-height, and font weights.
- Match card surfaces, borders, corner radii, icon scale, and arrow affordances.
- Tune warm ivory/charcoal/forest-green/sage palette.
- Refine hero illustration crop and alignment.
- Verify Light and Dark theme consistency.

### Step 5 — Visual verification

Create:

- `now3.png`: final app screenshot at the exact reference geometry.
- `now3_dark.png`: dark-theme screenshot at the same geometry.
- `now3_overlay.png`: a 50% overlay of the current final screenshot and reference, aligned to the app frame.
- `now3_diff.png`: optional image-difference visualization, with the understanding that font rendering and anti-aliasing can create harmless pixel differences.

Compare by regions: window frame, sidebar, header, hero, Quick Tools heading, grid, and status bar. If a large region is misaligned, fix it before marking the task complete.

---

## 6. Acceptance checklist (all required)

### Geometry and fit
- [ ] App screenshot is cleanly framed and comparable to the reference.
- [ ] Sidebar is approximately 18% of app width at reference viewport.
- [ ] Main content has consistent insets and uses available width.
- [ ] No horizontal clipping anywhere.
- [ ] No visible vertical scrollbar at the reference viewport if the full dashboard fits.
- [ ] Full hero and all 9 tool cards are visible at reference viewport.
- [ ] No overlapping title, body text, CTA, icons, or card content.
- [ ] No card is cut off at the right or bottom edge.
- [ ] Footer is anchored and does not cover content.

### Visual match
- [ ] Header, hero, grid, and footer proportions closely match the reference.
- [ ] Hero headline appears in two complete lines at the reference viewport.
- [ ] Description is fully visible and wraps like the reference.
- [ ] CTA is fully visible and uses the approved dark green treatment.
- [ ] Quick Tools title/icon and View all tools action are both visible.
- [ ] Three equal card columns and three rows match the reference arrangement.
- [ ] Featured Full Conversion Wizard card appears bottom-right and launches the existing wizard.
- [ ] Sidebar includes all expected navigation items and bottom tagline panel.
- [ ] Colors, typography, icon style, border, radius, and spacing are close to the reference.

### Functional/regression
- [ ] Hero CTA opens the existing Full Conversion Wizard.
- [ ] Featured wizard card opens the same existing wizard.
- [ ] All secondary tool cards open the correct existing destinations.
- [ ] Settings and backend selector still work.
- [ ] Light theme works.
- [ ] Dark theme works.
- [ ] Window drag/resize/minimize/maximize/close work.
- [ ] No new startup errors, broken imports, or console exceptions.
- [ ] Existing relevant tests pass.

### Responsive behavior
- [ ] 3 columns at the reference and wide viewport.
- [ ] 2 columns when the available main-content width is insufficient for 3.
- [ ] 1 column when 2 cannot fit comfortably.
- [ ] No horizontal scrollbar at any supported viewport.
- [ ] At reduced heights, vertical scrolling is intentional and does not cause overlap.

---

## 7. Completion report

At the end, report:

1. Root causes discovered (not just symptoms).
2. Files changed and why.
3. Layout changes with before/after measurements.
4. Screenshots: `now3.png`, `now3_dark.png`, overlay, and optional diff.
5. Acceptance checklist results, with failures stated plainly.
6. Tests/commands run and results.
7. Remaining discrepancies and any limitation preventing a closer match.
8. Final Git status and uncommitted changes.

Do not claim 99% similarity without showing the aligned screenshot comparison. If any checklist item fails, list it as unresolved and continue correcting it within this task where feasible.

**No commit, push, GitHub release, or deployment without my explicit approval.**
