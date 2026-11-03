# ELIXIR --- UI/UX Correction Round 4

## Dashboard density, sidebar usability, typography, and visual fidelity

**Purpose:** Correct the remaining dashboard differences between the
current implementation (`14.png`) and the approved reference
(`508782d6-4b80-48be-9046-d081ce258b75.png`).

**Primary objective:** Reproduce the reference's compact, balanced
dashboard while keeping the application usable, responsive, and
functionally unchanged.

**Current screenshot:** `14.png` (1096 × 717 image) **Approved
reference:** `508782d6-4b80-48be-9046-d081ce258b75.png` (1000 × 667
image)

The screenshots have different canvas and window dimensions. Do not
compare raw pixels until the application window has been captured at a
matched size and with consistent framing.

------------------------------------------------------------------------

# 1. Audit summary

The current implementation has improved substantially, but the following
issues remain:

  -----------------------------------------------------------------------
  Priority          Area              Current problem   Required result
  ----------------- ----------------- ----------------- -----------------
  Critical          Quick Tools       Two columns; only Three columns and
                                      four cards        three rows at
                                      visible           reference desktop
                                                        size

  Critical          Sidebar           Internal          All primary
                                      scrollbar;        navigation
                                      navigation        visible without
                                      entries clipped   scrolling

  Critical          Content density   Cards too large   Compact card
                                      and tall          dimensions and
                                                        reduced internal
                                                        padding

  High              Sidebar footer    Tagline panel     Compact, fully
                                      consumes too much readable footer
                                      space; text       panel
                                      clipped           

  High              Theme controls    Two visible theme One clear, fully
                                      controls          functional theme
                                                        selector

  High              Typography        Generic-looking   Distinctive,
                                      typeface and      consistent
                                      inconsistent      sans-serif
                                      hierarchy         typography

  Medium            Hero artwork      Decorative        Transparent
                                      background shapes isolated PNG
                                      compete with      integrated
                                      artwork           cleanly into hero

  Medium            Layout polish     Current page does Consistent
                                      not reproduce the spacing,
                                      reference's       proportions, and
                                      balanced density  alignment
  -----------------------------------------------------------------------

Do not treat the issue as simply a need to enlarge the window. The
current content viewport appears wide enough to support a three-column
grid if the grid's column constraints and card dimensions are corrected.

# 2. Primary target: Quick Tools grid

This is the most visible remaining mismatch and must be fixed first.

## 2.1 Required layout

At the reference desktop viewport, display all nine cards in a 3-column
× 3-row grid, matching the approved reference.

Expected card order:

Row 1: 1. Summarization 2. Document → Markdown 3. Translation

Row 2: 4. Packets of Knowledge 5. OCR Service 6. PDF/DOCX Cutter

Row 3: 7. Image Extractor 8. Markdown Styler 9. Full Conversion Wizard

Preserve the existing actual tool names, destinations, and behavior. Do
not invent tools or change their functionality.

## 2.2 Card sizing and density

The current cards are oversized. Reduce their dimensions and internal
spacing so that all nine fit naturally in the available main content
area.

Guidelines at the reference desktop size: - Three equal-width columns. -
Approximately 10--12 px horizontal and vertical gaps, adjusted to match
the reference proportions. - Compact card height, approximately 80--90
logical px, subject to actual font metrics. - Smaller internal padding
than the current implementation. - Icon, title, description, and arrow
must remain legible. - Use a consistent icon box and title baseline
across all cards. - Descriptions should occupy no more than two lines at
the reference size. - Arrow affordance should remain aligned
consistently near the card's right edge. - The Full Conversion Wizard
card should retain its distinctive dark green treatment.

Do not shrink typography excessively to force the grid to fit. First fix
the grid column count, parent width, card minimum width, and card height
constraints.

## 2.3 Grid behavior

Use the actual available content width to determine column count.

Recommended behavior: - Wide desktop: 3 columns. - Constrained desktop:
2 columns. - Narrow window: 1 column.

Do not hardcode a two-column grid. Do not allow one card per row at
ordinary desktop dimensions.

Inspect the Qt layout implementation for: - Fixed minimum widths on
cards. - Grid column stretch factors. - Nested layout margins. - Size
policies. - Scroll-area viewport width. - Parent widget minimum sizes. -
Layout spacing applied at multiple nesting levels.

The grid must use the available width evenly.

# 3. Sidebar correction

The sidebar must become a compact, complete navigation area.

## 3.1 Navigation visibility

At the reference desktop size, all primary navigation entries must be
visible without an internal vertical scrollbar.

Required structure: - Brand/logo at the top. - Home. - Tools section
with all currently implemented primary tools. - A visual separator. -
Settings and About in a fixed lower navigation region, provided these
destinations already exist in the application.

Keep the actual existing navigation destinations. Do not invent new
navigation features.

## 3.2 Sidebar sizing

Maintain the compact reference proportion, approximately 17--19% of the
application width.

Do not widen the sidebar to solve text wrapping. Instead: - Use compact
vertical spacing. - Use consistent icon/text alignment. - Use an
appropriate label font size. - Avoid unnecessary multi-line tool
labels. - Ensure the sidebar's content width is sufficient for the
longest real tool name.

If a label must wrap, do so intentionally and ensure its row height
accommodates it. Prefer the single-line treatment shown in the reference
whenever feasible.

## 3.3 Fixed lower navigation and footer

The sidebar must be divided into: 1. A scroll-free primary navigation
area at the reference viewport. 2. A lower navigation area for existing
Settings/About destinations. 3. A compact branding/tagline panel at the
bottom.

The lower area must not push primary tools out of view.

If the actual available height becomes too small on a constrained
window, allow a deliberate sidebar scrolling mode rather than clipping
controls. At the reference desktop size, however, all entries should fit
without scrolling.

# 4. Sidebar bottom card: remove wasted space

The current tagline card is too tall for its content, and the tagline is
clipped.

Keep the existing brand message:

**Knowledge, distilled into clarity.**

Correct the panel: - Reduce its height and internal padding. - Ensure
the full tagline is visible. - Keep the small botanical landscape
artwork restrained. - Avoid oversized blank areas. - Align it with the
sidebar's inner margins. - Do not let it overlap or displace navigation.

The user suggested making better use of the space. First use the space
to restore the missing Settings/About navigation in the appropriate
fixed lower area. Do not invent a dashboard widget, activity feed, or
new feature merely to fill space.

If the existing About destination or application version can be
presented compactly without duplication, that is acceptable. Otherwise
retain a clean, compact tagline card.

# 5. Theme controls: keep only one

The current interface exposes two theme controls: - Moon icon in the top
bar. - Light Theme selector in the bottom status bar.

Remove the top-bar moon theme control.

Keep the bottom status-bar theme selector as the single visible theme
control. It should: - Clearly display the active theme. - Allow
switching between Light and Dark. - Continue to work with the existing
theme engine. - Persist the selected theme if persistence already
exists. - Remain accessible and keyboard-operable.

Do not remove the underlying theme functionality. Remove only the
duplicate visible control.

Check the resulting top-bar spacing after removing the moon control.
Redistribute remaining controls naturally; do not leave a conspicuous
empty slot.

# 6. Typography refinement

The current typeface looks generic. Introduce a more distinctive but
professional sans-serif identity.

## 6.1 Typeface evaluation

Evaluate these candidates in the real application: 1. **Manrope** ---
preferred first candidate; modern, refined, geometric, and readable. 2.
**IBM Plex Sans** --- alternative with a more editorial and academic
character.

Use one primary type family consistently throughout the dashboard. Do
not mix typefaces arbitrarily.

Before selecting: - Verify actual font rendering in the target Qt
environment on Windows. - Check availability and packaging behavior. -
Confirm the font's license permits the intended distribution. - If
bundling is required, bundle the required weights and load them
reliably. - Provide a sensible fallback such as Segoe UI.

Do not rely on a font that only happens to be installed on the
developer's machine.

## 6.2 Typography hierarchy

Define a consistent hierarchy for: - Brand wordmark. - Hero headline. -
Hero body copy. - Section headings. - Tool card titles. - Tool
descriptions. - Sidebar labels. - Status bar text.

Use appropriate font weights and line heights. Avoid making every
heading bold or using excessive letter spacing.

The reference is understated and editorial. The typeface should improve
the product's character without making it look decorative or overly
fashionable.

## 6.3 Visual font comparison

Before finalizing the font: - Capture the dashboard with Manrope. -
Capture the dashboard with IBM Plex Sans. - Compare headline wrapping,
card density, navigation legibility, and overall character. - Choose the
better result and document why.

Do not leave a runtime font picker in the UI. This is a design decision,
not a new user-facing feature.

# 7. Hero artwork and composition

The hero artwork should remain an isolated transparent PNG.

Inspect the current hero asset: - Confirm it is a genuine RGBA PNG with
a meaningful alpha channel. - Confirm the background outside the books,
quill, and inkwell is transparent. - Do not use a rectangular image with
an opaque background. - Preserve aspect ratio; never stretch the
artwork. - Use appropriate scaling and alignment. - Integrate the image
into the hero's existing background without a visible rectangular
boundary.

Refine the background shapes if they compete with the artwork. The books
and quill should be the focal point, not the decorative circles.

Do not generate or substitute a different illustration unless the
existing asset is demonstrably unsuitable.

# 8. Preserve the approved visual language

Maintain the approved design direction: - Warm ivory background. -
Charcoal/ink typography. - Muted forest-green and sage accents. - Subtle
borders and surface separation. - Restrained shadows. - Monochrome
outline icons. - Compact, editorial composition.

Do not introduce bright blue/purple gradients, excessive glass effects,
heavy shadows, ornamental decorations, or unrelated visual concepts.

Keep the existing custom window frame and controls unless a genuine
defect is found.

# 9. Layout and Qt implementation audit

Before modifying code, inspect the current widget tree and layout
structure.

Identify: - Main window layout. - Sidebar layout. - Header layout. -
Main content container. - Hero layout. - Quick Tools grid. -
Footer/status bar. - Theme selector. - Font-loading mechanism.

Inspect and correct: - Minimum/maximum sizes. - Fixed sizes. - Size
policies. - Grid column stretch. - Layout margins and spacing. -
Scroll-area behavior. - Widget size hints. - Text wrapping and label
sizing. - Duplicate theme-control registration.

Avoid absolute positioning and arbitrary per-widget coordinates. Use the
repository's existing Qt layout architecture.

Do not add multiple layers of margins that compound and consume the
available space.

# 10. Screenshot and validation requirements

Capture the actual running application, not a mockup.

Use consistent screenshot framing and record the actual application
client dimensions.

Required screenshots: - `now5.png` --- Light Theme at the reference
desktop size. - `now5_dark.png` --- Dark Theme at the same size. -
`now5_wide.png` --- wider desktop layout. - `now5_constrained.png` ---
constrained desktop layout. - `now5_overlay.png` --- aligned overlay
against the approved reference.

The reference is 1000 × 667 pixels. Match the application window's
dimensions and framing before using image overlays or difference images.

At the reference size verify: - All nine Quick Tools cards are
visible. - Grid is three columns by three rows. - No card is clipped. -
Sidebar tools are all visible. - Settings/About are accessible. -
Sidebar does not show an unnecessary scrollbar. - Tagline is fully
readable. - Only one visible theme control exists. - Hero text and
transparent illustration do not overlap. - Bottom status bar remains
visible. - No horizontal or vertical overflow occurs.

At constrained sizes, test intentional two-column and one-column
transitions. Do not allow clipped controls or overlapping content.

Test all tool navigation destinations and theme switching to ensure no
functionality regressed.

# 11. Scope and safety constraints

-   Preserve all existing tool functionality.
-   Do not modify document conversion, summarization, OCR, translation,
    or backend processing logic.
-   Do not redesign the Full Conversion Wizard.
-   Do not delete experimental code.
-   Do not invent features to fill visual space.
-   Do not introduce unnecessary dependencies.
-   Do not refactor unrelated parts of the application.
-   Do not commit, push, release, or deploy without explicit
    authorization.
-   Protect uncommitted user changes.

# 12. Definition of done

This round is complete only when:

1.  The Quick Tools section displays all nine cards in a 3 × 3 grid at
    the reference desktop size.
2.  Cards are compact, balanced, and readable.
3.  The sidebar displays all primary navigation without clipping or
    unnecessary scrolling at the reference size.
4.  Settings/About remain accessible in the lower sidebar area.
5.  The tagline card is compact and fully readable.
6.  Only one visible theme selector remains.
7.  A refined sans-serif typeface has been selected based on actual
    comparison and reliable packaging.
8.  The hero illustration is a genuine transparent PNG and blends into
    the hero.
9.  Light and Dark themes both work.
10. Screenshot evidence demonstrates the result.

# 13. Final report

Provide: - Root causes found. - Exact files modified and why. - Final
selected font and packaging method. - Quick Tools grid dimensions and
breakpoints. - Sidebar dimensions and navigation visibility. -
Confirmation of transparent PNG alpha. - Confirmation that only one
theme control remains. - Screenshots and overlay. -
Functional/regression test results. - Remaining discrepancies. - Final
Git status.

Do not claim 99% similarity unless the screenshots support that claim.

**Execute this correction round. Do not stop after producing another
audit or plan.**
