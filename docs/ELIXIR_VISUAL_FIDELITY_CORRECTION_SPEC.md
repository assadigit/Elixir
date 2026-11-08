# ELIXIR — Visual Fidelity Correction Specification

**Purpose:** Bring the implemented ELIXIR dashboard as close as practically possible to the approved dashboard reference, with a target of at least 99% *perceived visual similarity* at the reference viewport.

**Repository:** https://github.com/assadigit/Elixir  
**Current implementation screenshot:** `now.png` at the repository root (currently showing v0.6.75)  
**Approved reference:** `reference/approved_dashboard_visual_reference.png` inside `ELIXIR_UI_UX_IMPLEMENTATION_PACKAGE.zip` (or the corresponding extracted file). The reference image supplied with this request is the visual authority.

---

## 1. Mission

This is a **fidelity correction pass**, not a new design exercise.

Recreate the composition, hierarchy, proportions, spacing, colors, typography, cards, sidebar, top bar, hero, footer, and window treatment of the approved reference as faithfully as possible using the application's existing Python/Qt architecture.

Do not redesign the interface based on personal taste. Do not introduce a new visual direction. Do not replace the reference with a generic modern dashboard. The reference is the target.

The current implementation already contains several correct ingredients: warm neutral surfaces, muted green accents, book-and-quill artwork, the welcome headline, a conversion CTA, and tool cards. Retain and refine these where they already match. The primary work is correcting structure, geometry, proportions, and component detail.

## 2. Required first steps

Before editing anything:

1. Read the approved design specification and implementation instructions in the ZIP package.
2. Open and inspect the approved reference image at full resolution.
3. Open and inspect the current root-level `now.png` at full resolution.
4. Confirm the current source branch, working tree, and uncommitted changes. Do not overwrite user work.
5. Identify the exact Qt binding, main window class, dashboard widgets, theme system, and current navigation implementation. Do not assume PySide6/PyQt or a particular architecture.
6. Run the application and capture a fresh baseline screenshot. `now.png` may be stale; compare the live application as well as the committed screenshot.
7. Establish a reproducible screenshot viewport of **1536 × 1024** for the primary comparison. Record the actual client/window dimensions and DPI scaling. The reference image itself is 1536 × 1024.

If the target image cannot be found inside the ZIP, stop and report the exact missing path. Do not substitute `now.png` for the reference.

## 3. Visual audit: differences to correct

### P0 — Overall window and application frame

**Current:** The current screenshot retains the native Windows title bar and conventional application frame. The application content begins below it.  
**Target:** The reference presents ELIXIR as one unified, softly elevated application surface with rounded outer corners, a subtle border/shadow, and integrated top chrome.

Implement a custom/frameless window treatment only after checking the existing Qt architecture and Windows behavior. Preserve all expected window operations:

- Drag the window from the intended top-bar region.
- Resize from all edges and corners.
- Minimize, maximize, restore, and close.
- Double-click the title-bar drag area to maximize/restore if supported by the platform convention.
- Keep system DPI scaling and multi-monitor behavior correct.
- Maintain keyboard accessibility and sensible focus behavior.

Do not fake the window controls as decorative icons. They must work. If a fully frameless shell creates unacceptable Windows behavior, implement the closest safe Qt-native alternative and document the remaining difference.

**Reference geometry at 1536 × 1024:** approximately 20–22 px outer margin, a 1495 × 980 px shell, and an outer corner radius around 17–20 px. Treat these as starting measurements; inspect the image and tune against the actual pixels.

### P0 — Main application layout

**Current:** Brand/application identity is in the top horizontal strip, while the sidebar starts with Home. The sidebar consumes too much width relative to the reference.

**Target:**

- Brand/leaf mark and “Elixir” wordmark are at the top of the sidebar.
- The top bar belongs to the main content area, not the full width of the window.
- Main content starts to the right of the fixed sidebar.
- The bottom status strip spans the complete inner application width.
- Sidebar remains fixed while the main content area can scroll when necessary.

At the 1536 × 1024 reference viewport, target sidebar width is approximately **265 px** (about 17.2% of the image width). Use the screenshot, not an arbitrary framework default, to tune this. The sidebar should not consume 23% of the window as it currently does in the smaller captured screenshot.

The reference's content starts around x=307 px. Main content padding is approximately 20–22 px.

### P0 — Sidebar

Recreate the reference's sidebar hierarchy and visual rhythm:

1. Brand row: leaf emblem + “Elixir” in a clean sans-serif wordmark.
2. Home item with a quiet, pale sage selected background.
3. Small uppercase “TOOLS” label.
4. Tool entries with consistent monochrome outline icons, labels, and compact row heights.
5. A subtle divider.
6. Settings and About near the bottom.
7. A compact knowledge/tagline panel anchored to the bottom, containing the leaf emblem, “Knowledge, distilled into clarity.”, and the muted landscape artwork.

The visible tool order in the reference is:

- Full Conversion
- Summarization
- Document → Markdown
- Translation
- Markdown Styler
- Packets of Knowledge
- OCR Service
- PDF/DOCX Cutter
- Image Extractor

Use the exact labels and existing routes/functions. Do not create placeholder routes or invent tools. Keep Settings and About separate from the main tools list. Hide experimental destinations from primary navigation as specified in the existing project brief, but do not delete their implementation.

Use consistent left alignment, icon-to-label spacing, and row height. Avoid the current appearance of a tall, independently scrolling navigation list unless the available height genuinely requires it. The reference sidebar is visually calm and compact.

### P0 — Header / top bar

**Target:** The top bar starts immediately to the right of the sidebar and contains, from left to right only as needed by available width:

- The selected backend status as a compact pill, e.g. green status dot + “Ollama” + dropdown chevron.
- A clearly labelled Settings action with a gear icon.
- A subtle divider.
- A moon/theme icon control.
- Window minimize, maximize/restore, and close controls at the far right.

Remove the old product subtitle from the top-left brand area; the brand belongs in the sidebar. Do not leave legacy header controls competing with the reference layout.

Backend connection details, secondary providers, Merge, Process Wizard, and other less-used actions should be moved to their existing appropriate settings/status surfaces rather than being added to the main top bar. Do not remove their functionality. Do not invent a new settings system if the application already has one.

### P0 — Hero panel geometry and content

This is one of the most important visual anchors.

**Current:** Hero is too tall for the available width in the captured smaller screenshot; the headline wraps into four short lines, making the panel feel narrow and vertically heavy.

**Target:** A wide, shallow editorial hero panel, approximately **1182 × 340 px** at the 1536 × 1024 reference viewport (aspect ratio about 3.48:1), beginning approximately 20–22 px from the main content edges.

Recreate:

- Pale warm cream surface with a very subtle border and rounded corners (around 15–17 px).
- Left text block, vertically balanced and aligned to a shared content inset.
- Right-side books, ink pot, and feather/quill composition.
- Soft translucent geometric circles/arcs and understated landscape curves behind the illustration.
- No loud gradients, neon glows, heavy shadows, or excessive decoration.

Use the reference wording, subject to verification against the actual product:

- Eyebrow: `WELCOME TO ELIXIR`
- Heading: `Turn documents into clear, structured knowledge.`
- Supporting copy: `Books, articles and documents — summarized, organized and ready for you to explore.`
- Primary CTA: `Start Conversion`

The heading should occupy **two lines** at the reference viewport. Match the reference's large, dark, semibold/bold sans-serif typography. Do not allow accidental narrow text wrapping due to excessive sidebar width, overly large left padding, or an incorrectly constrained text container.

The illustration should occupy approximately the right 40–45% of the hero and be visually balanced with the copy. Reuse the supplied hero artwork where possible. Do not stretch the artwork or use the full screenshot as a background. Preserve its aspect ratio and use a transparent crop/asset where appropriate. Recreate the background arcs/landscape as separate lightweight vector or image elements if they are not already present in the asset.

CTA requirements:

- Deep muted forest-green fill.
- Capsule/pill shape.
- White play icon at left.
- White label.
- Right-arrow affordance at right.
- Correct vertical alignment and generous horizontal padding.
- Must launch the existing Full Conversion Wizard; no new workflow.

### P0 — Quick Tools section and grid

The reference uses a single “Quick Tools” heading row. It does not insert category headers such as PROCESSING or UTILITIES between the heading and individual rows.

Heading row:

- Muted forest-green lightning icon.
- “Quick Tools” title.
- “View all tools →” action aligned to the far right.

Grid at the 1536 × 1024 reference viewport:

- Three equal columns.
- Three rows.
- Consistent horizontal and vertical gaps (approximately 14–16 px).
- Card heights approximately 125 px.
- Subtle warm border, very light cream/white surface, radius around 13–15 px.
- No thick outlines or strong drop shadows.

Reference card order:

1. Summarization
2. Document → Markdown
3. Translation
4. Packets of Knowledge
5. OCR Service
6. PDF/DOCX Cutter
7. Image Extractor
8. Markdown Styler
9. Full Conversion Wizard (distinctive dark-green feature card)

The standard tool card contains:

- A large, clean outline icon at the left (muted forest/sage green).
- Tool title in dark semibold sans-serif.
- One short, subdued description beneath the title.
- A pale circular arrow affordance near the right edge.
- Consistent internal padding and vertical centering.

The ninth card is visually different: deep forest-green background, subtle botanical/landscape texture, light iconography and type, with a circular arrow affordance. It must remain legible and restrained.

**Important specification conflict:** An earlier project constraint said not to duplicate Full Conversion in the secondary grid, but the approved reference image clearly includes a Full Conversion Wizard card in the final grid position in addition to the hero CTA. For this strict visual-fidelity pass, reproduce the reference's ninth card. It must be a second entry point to the *same existing wizard*, not a new feature or duplicate implementation. If the owner explicitly reasserts the earlier no-duplicate constraint, remove this card and accept that this single area will intentionally differ from the reference.

Descriptions must accurately reflect the existing features. Use the reference wording only where it truthfully describes current functionality. Do not claim capabilities the code does not provide.

### P1 — Bottom status strip

The reference has a thin, persistent bottom strip across the whole inner application shell.

Recreate:

- Left side: small sage-green status dot and `Ready`.
- Right side: subtle divider, sun icon, `Light Theme`, and dropdown chevron.
- Fine top border separating it from the content.
- Warm translucent/cream surface consistent with the header.
- Height around 56 px at the reference viewport.

The theme selector must reflect the real application theme and work. The status text must be connected to actual application status; do not hardcode “Ready” when the application is busy or in an error state.

### P1 — Theme, color and surface refinement

Match the reference's subdued warm palette. The following are approximate starting points, not permission to recolor the entire application without inspecting the reference:

- Overall canvas: warm off-white / ivory, around `#F7F5EF`.
- Sidebar: slightly warmer/lighter ivory, around `#F5F3EC`.
- Hero: warm cream, around `#F5F1E7`.
- Standard cards: near-white cream, around `#FCFBF7`.
- Primary text: deep charcoal/ink, around `#1D2423`.
- Secondary text: muted charcoal-gray, around `#59615F`.
- Primary accent: deep forest green, around `#34483A`.
- Secondary accent: sage, around `#647B64`.
- Borders/dividers: low-contrast warm gray, around `#E8E4DA`.

Avoid saturated blue/purple, strong orange, cyan, neon green, excessive transparency, and large gradient fills.

The dark theme should preserve the same geometry and hierarchy, using deep charcoal/green surfaces and muted sage accents. Do not let light-theme changes break dark mode. The supplied reference is the light-theme acceptance target; capture and test dark mode separately for consistency and usability.

### P1 — Typography and icons

- Use a modern sans-serif family consistently (prefer the existing bundled/available font if it matches; otherwise Inter with robust Windows fallbacks such as Segoe UI/Noto Sans/Arial).
- Do not introduce serif display text.
- Match heading weight, line breaks, letter spacing, and size hierarchy to the reference.
- Use one consistent outline icon family with consistent stroke weight and optical size.
- Replace emoji/colored clip-art-style tool icons with crisp monochrome outline icons where the current implementation still uses them.
- Do not mix unrelated icon families or use raster screenshots as icons.
- Ensure icon sizes are set in logical Qt units and render sharply at common Windows scaling settings.

### P2 — Responsive behavior

The primary fidelity viewport is 1536 × 1024. However, the dashboard must still work at smaller windows.

Use explicit breakpoints based on actual available content width:

- Wide desktop: 3-column tool grid.
- Medium width: 2-column tool grid.
- Narrow width: 1-column grid, with sidebar collapse/compact behavior only if already supported and safe.

At smaller sizes, the hero may reduce in height and the text/image split may adapt, but preserve the same typography hierarchy, colors, and component style. Prevent four-line headline wrapping caused by a wrongly oversized sidebar or incorrect constraints. Avoid clipping the last card or hiding important controls behind scroll areas.

The fixed status strip must not overlap scrollable content. The sidebar tagline card should remain anchored near its bottom when sufficient height exists; at constrained heights, it may yield space to navigation rather than cover it.

## 4. Reference measurements and visual QA

Use the following approximate measurements as an initial layout guide at 1536 × 1024:

| Element | Reference target |
|---|---:|
| Outer window margin | 20–22 px |
| Outer corner radius | 17–20 px |
| Sidebar width | ~265 px |
| Main content left edge | ~307 px |
| Main content horizontal inset | 20–22 px |
| Top bar height | ~68–70 px |
| Hero | ~1182 × 340 px |
| Hero corner radius | ~15–17 px |
| Quick Tools heading top gap after hero | ~36–42 px |
| Tool grid columns | 3 |
| Tool card height | ~125 px |
| Tool card radius | ~13–15 px |
| Grid gap | ~14–16 px |
| Bottom status strip height | ~56 px |

These are estimates from the visual reference. Use pixel inspection and screenshot overlays to refine them rather than treating every value as exact.

### Required screenshot comparison process

For each major iteration:

1. Launch the real application at 1536 × 1024 with the same Windows DPI scaling where possible.
2. Capture a clean screenshot of the entire application window.
3. Compare it with the approved reference side by side.
4. Create a 50% opacity overlay or difference image to expose alignment and proportion errors.
5. Fix the largest visual differences first: window geometry, sidebar width, top bar, hero size, content grid, and status strip. Only then adjust typography, icons, borders, and micro-spacing.
6. Repeat until the composition is visually very close.

Do not claim 99% similarity based only on source-code inspection. Provide before/after screenshots. If a numeric metric is available, report it with its method and limitations; do not present a raw pixel score as equivalent to human-perceived similarity because font rasterization, shadows, DPI, and window-manager differences can affect it.

## 5. Functional and technical constraints

- Preserve all existing feature implementations and routes.
- No invented functionality, mock controls, dead buttons, or decorative controls that do nothing.
- Reuse the current application's actual Full Conversion Wizard entry point.
- Maintain real Light/Dark theme switching.
- Do not delete experimental tools; only keep them out of primary navigation as the existing brief specifies.
- Keep the code modular and consistent with the repository's current Qt binding and architecture.
- Avoid unnecessary dependencies.
- Do not hardcode pixel geometry in a way that breaks high-DPI or smaller-window layouts. Use Qt layouts, size policies, spacers, and carefully chosen minimum/maximum constraints.
- Keep all visible text and labels accurate to the real application's functionality.
- Do not change the wizard's internal 10-step workflow in this dashboard correction task.
- Avoid unrelated refactoring.

## 6. Implementation order

Work in this order; do not polish low-impact details while major structural differences remain:

1. Window frame and integrated shell.
2. Sidebar/content split and top-bar alignment.
3. Sidebar hierarchy and dimensions.
4. Hero geometry, typography, CTA, and artwork placement.
5. Quick Tools heading and 3-column card grid.
6. Bottom status strip.
7. Colors, surface treatments, icon family, typography refinements.
8. Responsive behavior and dark-theme verification.
9. Final screenshot comparison and regression testing.

After each major step, run the app and capture a screenshot. Do not implement all changes blindly and inspect only at the end.

## 7. Acceptance criteria

The task is complete only when all the following are true:

- At 1536 × 1024, the app's overall silhouette and composition closely match the approved reference.
- Sidebar width, brand placement, content start, header, hero, grid, and status strip align closely with the target.
- Hero has the correct wide/shallow proportions, correct copy hierarchy, balanced illustration, and functional CTA.
- Quick Tools uses the correct heading row and three-column arrangement at the target viewport.
- Cards match the reference's dimensions, borders, radius, padding, typography, icon scale, arrow affordances, and final dark-green feature-card treatment.
- No old header/sidebar structures remain visible where they conflict with the approved target.
- Light and Dark themes both work.
- Window controls, navigation, settings, backend status, theme selector, and conversion entry points work.
- Smaller viewports do not clip, overlap, or break navigation.
- Existing tool functionality and the Full Conversion Wizard's internal workflow remain unchanged.
- No experimental code has been deleted.
- Tests and relevant application launch checks pass.
- Before/after screenshots and a concise completion report are supplied.

**Do not describe the result as 99% complete unless the screenshots support that assessment.** If any reference difference remains, list it plainly and explain whether it is caused by platform constraints, an explicit product constraint, or incomplete implementation.

## 8. Required handoff

At the end of the correction session, report:

1. Files changed and why.
2. Which differences were corrected, grouped by priority.
3. Before/after screenshots at 1536 × 1024.
4. An overlay or difference image if feasible.
5. Test commands and results.
6. Confirmation that the wizard workflow and existing tools were not altered.
7. Remaining visual differences and their causes.
8. Current Git status and branch.
9. A proposed commit message. Do not commit, push, publish, or deploy unless explicitly authorized.

**Final instruction:** Treat the approved reference as the visual source of truth. Match its composition before adding polish. Do not redesign it.
