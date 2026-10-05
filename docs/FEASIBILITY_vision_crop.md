# Feasibility: Vision-Driven PDF Region Cropping

> **STATUS (V0.4.25 audit):** HISTORICAL feasibility study — implemented and
> shipped in V0.4.3.

**Question (user):** "Model has vision — when model sees a chart/diagram/picture or any
imagery (everything that is not pure text, tables etc.), can it crop the PDF
and screenshot that? For example, model finds a table, takes a cropped snapshot
of it, for example by using Python."

**Short answer:** **Yes — feasible, and substantially already built.** The Elixir
V0.4.1 source has three relevant modules (`figure_table_cropper.py`,
`table_graph_extractor.py`, `vision_figure_extractor.py`) that together cover
~70% of the use case via PDF-metadata-driven detection. The remaining 30%
— vector-drawn diagrams with no embedded raster, VLM-driven region
detection, and inline markdown embedding — is filled by the prototype
`core/pdf/vision_region_cropper.py` (added this session, validated on a
synthetic 3-page PDF with a vector bar chart + embedded raster image).

---

## 1. What the Elixir stack already does (V0.4.1)

| Module | What it detects | How | Output |
|---|---|---|---|
| `core/pdf/figure_table_cropper.py` | Embedded raster images (photos, scanned figures) | PyMuPDF `page.get_images(full=True)` | crops to `graphs/` |
| `core/pdf/figure_table_cropper.py` | Tables | pdfplumber `page.find_tables()` | crops to `tables/` + `.md` |
| `core/pdf/table_graph_extractor.py` | "Visual pages" (page-level heuristic) | pdfplumber shape scoring (rects + curves + lines + images) | full-page screenshots to `graphs/` |
| `core/pdf/table_graph_extractor.py` | Tables (alternative path) | Camelot lattice flavor | markdown + screenshots |
| `core/pdf/vision_figure_extractor.py` | Embedded images | PyMuPDF `page.get_images()` | sends image to VLM (OlmOCR/Qwen3-VL) for **text extraction only** — does NOT preserve the image as a cropped asset |

**What this already covers:**
- Embedded raster images (photos, generated charts exported as PNG/JPG)
- Ruled tables (pdfplumber + Camelot)
- Page-level "this page has visual content" flagging

**What this does NOT cover (the gaps):**
1. **Vector-drawn diagrams** — a chart drawn with PDF vector commands
   (lines, curves, rects) has no embedded raster image, so
   `page.get_images()` returns `[]`. The page is flagged as "visual" by
   the shape scorer, but the existing code screenshots the WHOLE page
   rather than the diagram's bounding box.
2. **VLM-driven region detection** — there is no path that renders the
   page as an image, asks a VLM "where are the non-text regions?", and
   crops those regions. The existing `vision_figure_extractor.py` uses
   the VLM only for TEXT extraction from already-detected images.
3. **Inline markdown embedding** — crops are saved to folders and
   referenced in a manifest, but never embedded as `![Figure N](path)`
   directly in the chapter summary markdown.

---

## 2. The three-layer architecture (prototype)

The prototype (`core/pdf/vision_region_cropper.py`, ~450 LOC) is
content-agnostic and composable. Each layer can run independently.

### Layer 0 — PDF-metadata extractors (existing, reused)

Reuses Elixir's `figure_table_cropper.extract_figures_and_tables()`.
Returns existing `Region` objects with `source="pdfplumber_images"` or
`source="pdfplumber_tables"`. Confidence = 1.0 (deterministic).

### Layer A — Vector-graphics clustering (new, this session)

`detect_vector_regions()` uses pdfplumber to fetch every rect, line, and
curve on a page, then clusters them by spatial proximity (greedy
agglomerative clustering, distance threshold 50pt, minimum 5 shapes per
cluster). Each surviving cluster becomes a `Region` with
`source="vector_cluster"` and confidence 0.85.

**Why this is content-agnostic:**
- No hardcoded shapes (no "if rect.height > 50 and rect.width < 200
  then bar" logic).
- No hardcoded page-size thresholds — the distance and min-shapes
  parameters are in PDF points and shape counts, not inches or aspect
  ratios.
- Works on any vector content: bar charts, line graphs, flowcharts,
  circuit diagrams, org charts, technical drawings.

**Validation (synthetic PDF):** a 3-page synthetic PDF with a vector
bar chart on page 2 was correctly identified as a single
`vector_cluster` region with bbox `(72, 260, 372, 350)` — exactly
matching the chart's drawn area (10 bars + 5 axis lines). Page 1
(pure text) correctly returned 0 regions.

### Layer B — VLM-driven region detection (new, this session — optional)

`detect_vlm_regions()` renders the page at low DPI (default 100) using
`pdf2image`, encodes as PNG, sends to a VLM with this prompt:

> You are a precise document-layout analyst. Look at the page image and
> identify every NON-TEXT region — any chart, diagram, figure, photo,
> table, graph, equation block, or other visual element that is NOT a
> paragraph of prose. For each region, return a JSON object with "label"
> and "bbox" (percentages 0–100, top-left origin). Output ONLY the JSON
> array.

The VLM's JSON response is parsed, the percentage-based bounding boxes
are mapped back to PDF coordinates, and each becomes a `Region` with
`source="vlm"` and confidence 0.75.

**Provider-agnostic:** the VLM is invoked via a `vlm_callable(image_bytes,
prompt) -> str` parameter. In Elixir integration, the callable wraps
`utils.network.safe_ollama_request` or the llama.cpp equivalent — the
same pattern as V0.4.1's `vision_figure_extractor.py`. The probe logic
from V0.4.1 ("does the main model have vision?") can be reused to decide
whether to enable Layer B at runtime.

**Why percentages, not pixel coordinates:** VLMs return bounding boxes
more reliably as percentages of image dimensions than as absolute pixel
coordinates (which depend on the render DPI). The percentage-to-PDF
mapping is a single multiply, no lossy conversion.

**Why low-DPI input + high-DPI crop:** the VLM only needs to identify
regions, not read them — 100 DPI is enough and minimizes tokens. The
actual crop is rendered at 200 DPI for sharpness, using the PDF
coordinates the VLM helped identify.

### Layer C — Inline markdown embedding (new, this session)

`build_inline_markdown()` injects `![Figure N: caption](path)` tags at
the right `<!-- original page N -->` markers in the chapter markdown, so
the cropped figures appear inline in the summary output. Falls back to
appending at the end if the page marker isn't found.

---

## 3. Validation results

The synthetic-PDF validation harness (run with `_demo_with_synthetic_pdf()`)
creates a 3-page PDF and tests all four expectations:

```
=== Validation ===
  ✓ Page 1 has no regions                              (pure text — correct)
  ✓ Page 2 has ≥1 vector_cluster region                (Layer A works)
  ✓ Page 2 vector_cluster covers the chart area        (bbox 72→372 = 300pt wide, matches chart)
  ✓ Page 3 has ≥1 region (embedded image)              (Layer 0 / PyMuPDF works)

Overall: PASS
```

**Cropped output files (real images, not stubs):**
- `page002_vector_cluster_diagram_candidate_1.png` — 833×250 px (the bar chart)
- `page3_figure1.jpeg` — 400×200 px (the embedded raster)

Layer B (VLM) was not exercised in this run because the sandbox has no
vision model. The code path is ready — it requires only a
`vlm_callable` that wraps the Ollama/llama.cpp API.

---

## 4. Three integration approaches — trade-offs

### Approach 1: PDF-metadata only (current V0.4.1 + Layer A)

**Pros:**
- Zero new dependencies (pdfplumber + PyMuPDF already in stack).
- Deterministic — same input always yields same output.
- Fast — no LLM calls; the synthetic PDF (3 pages) processed in <2s.
- No VRAM/budget concerns.

**Cons:**
- Cannot detect regions that are "visually a chart" but have ambiguous
  vector content (e.g., a chart that's a single embedded SVG with no
  discrete shapes for clustering).
- Cannot classify the region type ("this is a bar chart" vs "this is a
  flowchart") — only "this is a non-text region".

**Verdict:** Ship as the default. Layer A is strict-improvement over
the existing `table_graph_extractor._detect_visual_pages` because it
returns discrete bounding boxes instead of just a page-level flag.

### Approach 2: VLM-driven (Layer B)

**Pros:**
- Catches everything Layer A misses.
- Classifies the region type (chart/diagram/figure/photo/table/equation).
- Can describe the region in natural language (useful for caption
  generation).

**Cons:**
- Requires a vision model (not all rigs have one — V0.4.1 added the
  live probe specifically to handle this).
- Cost: one VLM call per page (the synthetic demo would be 3 calls).
  For a 400-page book, that's 400 calls × ~2s each = ~13 minutes
  additional runtime.
- VRAM: the VLM needs to be loaded; V0.4.1's probe logic already
  handles this.
- Reliability: VLM bounding boxes are approximate (±5% of image
  dimensions is typical for Qwen2-VL-class models). The crop might miss
  a few pixels at the edge — acceptable for figures, problematic for
  tables where every cell matters.

**Verdict:** Ship as **opt-in** (gated by `enable_vlm=True` and a
non-None `vlm_callable`). When the user's rig has a vision model, it
runs; otherwise, the pipeline degrades gracefully to Layer A + Layer 0.

### Approach 3: Hybrid (recommended — what the prototype does)

Run Layer 0 (existing extractors) → Layer A (vector clusters) →
Layer B (VLM, optional). De-duplicate overlapping regions (prefer higher
confidence). Crop survivors at high DPI. Embed inline.

This gives the best of both:
- Deterministic baseline from Layer 0 + A.
- VLM fills gaps when available.
- The VLM only needs to find regions Layer A missed (could be
  prompt-tuned for "find regions NOT already covered by vector
  clustering" — future optimization).

---

## 5. Recommended integration path into Elixir main

### Short-term (low-risk, high-value)

1. **Merge `vision_region_cropper.py` into V0.4.1** as
   `core/pdf/vision_region_cropper.py` (already done in this session's
   prototype).
2. **Wire Layer A** (vector clustering) into the existing
   `figure_table_cropper.extract_figures_and_tables()` return path —
   after the existing PyMuPDF + pdfplumber steps, run Layer A and merge
   results.
3. **Surface the manifest** in the conversion log so the user can
   see how many vector-cluster regions were detected per chapter.

This is content-agnostic, requires no new dependencies, and adds no
LLM cost.

### Medium-term (opt-in VLM)

4. **Add a settings flag** `vision.region_detection.enabled` (default
   `false`).
5. **Reuse V0.4.1's vision probe** (`model_architecture` setting +
   `safe_ollama_request` / llama.cpp probe) to detect whether the main
   model or a separate OCR model has vision. If yes, enable Layer B.
6. **Add a per-chapter budget** for VLM calls (e.g., max 50 pages per
   chapter, ~100s additional runtime).

### Long-term (semantic caption generation)

7. **Use the VLM to generate captions** for each cropped region (not
   just classify it). The existing `vision_figure_extractor.py` already
   has the API plumbing — extend its prompt from "extract text" to
   "describe the figure in 1–2 sentences for a summary".
8. **Embed the captions** in the summary markdown inline with the
   cropped image (Layer C is ready for this).

---

## 6. What I did NOT do (and why)

- **Did not integrate the prototype into `controller.py`'s conversion
  pipeline.** The prototype is a standalone module that can be invoked
  manually. Full pipeline integration requires careful sequencing with
  the existing `figure_table_cropper` call site (which already runs per
  chapter) to avoid double-processing. Recommended for a follow-up
  commit.

- **Did not add VLM-call mocking for the sandbox validation.** Layer B
  is implemented but not runtime-validated because the sandbox has no
  vision model. The code path is ready; integration testing on the
  user's rig (which has Qwen3-VL per V0.4.1's OCR module) will validate
  it.

- **Did not change the existing `figure_table_cropper.py`**. Layer 0
  reuses it as-is (calls `extract_figures_and_tables()` and converts
  the return values to `Region` objects). This keeps the change purely
  additive — no risk of regressing the existing behavior.

- **Did not write tests** (per the session rules: "do not write any test
  code"). The synthetic-PDF validation harness in the module's
  `__main__` block is a demo, not a test suite.

---

## 7. Answer to the user's question, distilled

> "Can the model crop the PDF and screenshot non-text regions using Python?"

**Yes.** Three paths, in order of cost/reliability:

1. **Cheapest, deterministic** (Layer A, this session): cluster
   pdfplumber shapes to find vector-drawn diagrams. No LLM. Content-
   agnostic. Validated on synthetic PDF. **Recommended default.**

2. **Most capable, opt-in** (Layer B, this session): render page at low
   DPI, ask the VLM for region bounding boxes, map back to PDF coords,
   crop at high DPI. Reuses V0.4.1's vision-probe pattern. Requires a
   vision model. **Recommended when the rig has vision.**

3. **Already shipped** (V0.4.1 Layer 0): PyMuPDF embedded-image
   extraction + pdfplumber table extraction. No changes needed.

The prototype composes all three with de-duplication, so the user gets
the union of what each layer detects, with no double-cropping.
