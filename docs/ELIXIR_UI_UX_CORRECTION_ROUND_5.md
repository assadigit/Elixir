# ELIXIR — UI/UX Correction Round 5
## Functional status, cleaner header, card alignment, and a coherent icon family

**Current screenshot:** `369.png` (1095 × 718)  
**Approved reference:** `508782d6-4b80-48be-9046-d081ce258b75.png` (1000 × 667)

The current dashboard is substantially closer to the approved reference. This round is a refinement and correctness pass, not another full redesign. Preserve the existing successful layout and visual direction.

## 1. Audit summary

| Priority | Area | Current issue | Required result |
|---|---|---|---|
| Critical | Backend status | Bottom status reads `Ready` even when no configured local backend is running/reachable | Show truthful provider/connection state based on real checks |
| High | Header Settings | Settings appears in both the sidebar and header | Keep the sidebar destination; remove the header Settings control |
| High | Provider selection | `llama.cpp server` selector clutters the header | Move Local/API provider selection and related configuration into Settings |
| High | Full Conversion Wizard card | Text/icon grouping is not vertically centered consistently | Vertically center the icon and text group; retain left-aligned text and right-aligned arrow |
| High | Tool icons | Existing icon family lacks a clear consistent bespoke identity | Approve a visual style using one prototype, then create a coherent set |
| Medium | Hero decoration | Large concentric circles compete with the hero still-life | Reduce contrast/visual dominance while preserving the existing artwork and composition |
| Low | Overall layout | Slight differences remain, but structure is now close | Preserve the current 3 × 3 grid, sidebar, hero and status-bar composition |

Do not regress the improvements already achieved in the previous rounds.

## 2. Preserve the current dashboard composition

The current application has made meaningful progress:
- Fixed sidebar with the primary tools visible.
- Wide editorial hero area.
- Three-column, three-row Quick Tools grid.
- Distinctive dark green Full Conversion Wizard card.
- Bottom status bar and theme selector.

Do not redesign these areas from scratch. Use the approved reference as the visual target, but retain the current layout architecture where it is already working.

The current and reference screenshots have different dimensions. Compare normalized application-window geometry and use matched captures before making pixel-level judgments.

## 3. Full Conversion Wizard card alignment

The dark green Full Conversion Wizard card needs a precise alignment correction.

Required structure:
- Leading icon at the left.
- Title and description grouped together as one text block.
- Text block vertically centered within the card's content area.
- Title and description remain left-aligned, matching the other cards and the approved reference.
- Arrow affordance independently aligned at the right and vertically centered.
- Equal, intentional spacing between icon, text group, and arrow.

Do not horizontally center the text. The reference uses left-aligned text within this card. The requested “middle alignment” means vertical centering of the content group unless the implementation reveals a concrete reason otherwise.

Verify alignment using actual widget bounds/baselines or layout geometry, not visual guesswork alone.

## 4. Remove duplicate Settings and move provider selection

### 4.1 Settings destination

- Keep the existing Settings entry in the sidebar.
- Remove the duplicate Settings button from the top/header area.
- Do not remove the Settings page, settings route, or any settings functionality.
- Verify that the sidebar entry still opens the existing Settings interface.

### 4.2 LLM provider selection

Move the interactive selector currently displayed in the header (for example, `llama.cpp server`) into the existing Settings interface.

Inspect the actual supported providers and configuration model before changing the UI. The menu may include local providers such as Ollama/llama.cpp and remote API providers, but only show options the application actually supports.

Within Settings, organize the controls clearly, for example:
- Provider type: Local / API, if both modes are supported.
- Provider/backend selection.
- Endpoint/base URL where applicable.
- Model selection where applicable.
- API credentials using the existing secure configuration mechanism.
- Connection test or reconnect action if supported or added safely.

Do not invent unsupported providers or change backend integration logic. Reuse existing configuration and client classes.

### 4.3 Header after cleanup

Remove both the duplicate Settings action and the interactive provider-selection menu from the header. Keep the custom window controls functional. Redistribute remaining header spacing naturally; do not leave awkward empty placeholders.

Do not add another Settings shortcut elsewhere.

## 5. Backend status must be truthful

The current bottom-left `Ready` label is misleading when no selected local LLM server is running or reachable.

Implement a small, explicit connection-state model based on the application's actual provider architecture.

### 5.1 Suggested states

Use only states that can be verified from the implementation:
- `Checking…` — a connection check is in progress.
- `Connected` — the selected provider has passed its real health/connectivity check.
- `Backend offline` — the selected local backend cannot be reached.
- `API unavailable` — the selected API provider cannot be reached or a valid response cannot be obtained.
- `Not configured` — no usable provider is configured.
- `Model unavailable` — the provider is reachable but the required/selected model is not usable, if the backend exposes enough information to verify this.

Do not display `Ready` merely because the GUI has launched or initialized.

If the application has a separate application-initialization status, keep it conceptually distinct from LLM/backend readiness. Do not conflate “the UI is running” with “AI operations can run”.

### 5.2 Real connection verification

- Inspect the existing backend adapters and their documented/implemented health checks.
- Use the correct mechanism for each supported provider.
- Respect configured endpoint/base URLs; do not hardcode assumed localhost ports.
- For API providers, distinguish missing credentials, connection failures, authentication errors, rate limits, and successful connectivity where feasible.
- Do not claim a model is loaded merely because the server process responds.
- Only show model-ready/operation-ready state when the evidence supports it.
- Trigger checks on application startup, provider/configuration changes, and relevant connection errors.
- Use non-blocking/asynchronous checks with sensible timeouts. Never freeze the GUI while waiting for network/backend responses.
- Avoid aggressive polling. Reuse existing signals, timers, or service patterns if present.
- If automatic retry is implemented, keep it bounded and avoid retry storms.

### 5.3 Status presentation

Use a compact dot + label in the existing bottom status area. Keep the reference's understated style:
- Muted green for verified connectivity.
- Amber for checking or partially configured/uncertain states.
- Muted red for unavailable/disconnected states.
- Neutral gray for not configured/unknown states.

Do not rely on color alone; the text label must communicate the state. Keep the bottom-right theme selector as the single visible theme control.

## 6. Icon family — approval-first workflow

The dashboard needs a coherent family of tool icons. Use the supplied prototype image `ELIXIR_ICON_SAMPLE_SUMMARIZATION.png` as the first style reference.

**Important:** this prototype is for visual approval. Do not generate the remaining icon set or replace the production icons with a complete new family until the user has approved the visual direction. The rest of the UI corrections in this specification can proceed independently.

### 6.1 Proposed visual direction

A quiet editorial outline family consistent with the approved Elixir dashboard:
- Simple, recognizable geometric forms.
- Single muted forest/olive-sage stroke color, coordinated with the existing card icons.
- Consistent stroke weight and rounded caps/joins.
- Minimal detail so icons remain clear at 20–28 logical pixels.
- Transparent background.
- No icon tiles, circles behind the icons, shadows, gradients, textures, or 3D effects.
- No labels or lettering embedded in icons unless the concept truly requires a conventional symbol (prefer no text).
- Centered visual mass and consistent optical padding.
- Each icon must have a distinct silhouette and remain recognizable at actual UI size.

The supplied sample is a document with source lines and a downward arrow leading to shorter summary lines. Treat it as a style prototype, not necessarily the final icon design if the user requests changes.

### 6.2 Icon inventory

The dashboard currently contains nine Quick Tools cards. Create a matching icon for every one, including Translation, even though it was omitted from the user's example list:

| Tool | Proposed visual concept |
|---|---|
| Summarization | Document with long content lines resolving into a shorter summary (prototype provided) |
| Document → Markdown | Document/page with a restrained Markdown/formatting cue or conversion marker |
| Translation | Globe or two language/speech forms connected by exchange arrows |
| Packets of Knowledge | Layered knowledge packet, stacked sheets, or structured cube |
| OCR Service | Scan frame/corner brackets around text lines |
| PDF/DOCX Cutter | Document divided into sections, or clean scissors/splitting motif |
| Image Extractor | Picture frame with a clear extraction cue |
| Markdown Styler | Pen/nib or brush refining a document |
| Full Conversion Wizard | Wand/spark plus document or book motif; keep it more distinctive for the featured card |

Avoid visually similar icons that are hard to distinguish at 24 px.

### 6.3 Production format after approval

After the user approves the sample style:
- Generate the complete set in a single consistent visual pass.
- Prefer editable SVG assets for Qt scaling if practical. If raster PNGs are used, export true transparent RGBA files at sufficiently high resolution and verify the alpha channel.
- Use one consistent viewBox/canvas size, optical padding, baseline, and stroke weight.
- Use neutral/currentColor-compatible SVG paths where supported by the Qt stack, or provide light/dark-safe color variants if necessary.
- If generating a contact sheet and cropping, inspect every crop individually for clipping, inconsistent padding, and alignment. Do not use the contact sheet itself as a production sprite unless the actual Qt implementation deliberately supports it.
- Keep an asset map naming each tool and its corresponding icon file.
- Test icons on both light and dark card surfaces, including the dark Full Conversion Wizard card.

Do not ship an icon pack that is just nine unrelated symbols with different line weights.

## 7. Hero refinement

Preserve the current books/quill artwork and hero layout, which are already close to the reference.

Refine only the visual competition from the large concentric background shapes:
- Reduce their contrast and/or opacity.
- Keep the books and quill as the focal point.
- Preserve the existing transparent artwork asset.
- Avoid adding another opaque rectangular illustration background.
- Check the result in both Light and Dark themes.

Do not replace the current illustration merely for novelty.

## 8. Functional constraints

- Keep all tool destinations and underlying operations intact.
- Both Full Conversion Wizard entry points, hero CTA and featured Quick Tools card, must continue opening the same existing wizard.
- Keep the selected theme control working and accessible.
- Preserve settings values and migration compatibility.
- Do not silently reset an existing provider configuration.
- Do not expose API keys or secrets in status labels, logs, screenshots, or changelogs.
- Do not change conversion, OCR, summarization, translation, or document-processing logic except where a minimal integration is strictly necessary for truthful connection status.
- Do not add unsupported backend providers.

## 9. Verification and acceptance criteria

Capture the actual running application in Light and Dark themes at the same dimensions as the approved reference, then at a wider desktop size.

Required checks:
1. Sidebar Settings is the only visible Settings entry on the dashboard.
2. No provider-selection dropdown remains in the header.
3. Supported local/API provider configuration is accessible in Settings.
4. Bottom status is truthful when Ollama/llama.cpp/API provider is unavailable.
5. A connected provider only appears connected after a real check.
6. Connection checks do not freeze the UI.
7. Full Conversion Wizard title/description group is vertically centered in its dark card; its text remains left-aligned.
8. The 3 × 3 grid and current dashboard geometry remain intact.
9. The theme selector remains in the bottom-right and works.
10. Hero artwork remains cleanly integrated; background decoration is less dominant.
11. Existing tools and wizard navigation work.
12. The proposed sample icon is presented for user review; do not silently assume approval for the complete icon family.

Capture:
- `now6.png` — Light Theme.
- `now6_dark.png` — Dark Theme.
- `now6_backend_offline.png` — selected backend deliberately unavailable; truthful status visible.
- `now6_backend_connected.png` — actual provider connected; truthful status visible, if a test backend is available.

Do not fake a successful connection for screenshot purposes.

## 10. Final report

Report:
- Files changed and why.
- How provider selection was moved into Settings.
- Which providers are actually supported.
- How each connection state is determined.
- Evidence that offline state is shown correctly.
- Evidence that connected state is genuine, if testable.
- Full Conversion Wizard card alignment result.
- Header controls removed.
- Hero decoration changes.
- Screenshots and test results.
- Any remaining issues.
- Git status.


