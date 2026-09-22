"""Vision-Region Cropper — extend figure_table_cropper with VLM-driven detection.

The existing Elixir stack (V0.4.1) already detects non-text content via
PDF metadata:

  - ``core/pdf/figure_table_cropper.py`` uses PyMuPDF ``page.get_images()``
    to find embedded raster images, and pdfplumber ``page.find_tables()``
    to find tables. It crops both and saves to ``graphs/`` and ``tables/``.

  - ``core/pdf/table_graph_extractor.py`` adds a pdfplumber shape-scoring
    heuristic (rects + curves + lines + images) to flag "visual pages",
    then screenshots the WHOLE page to ``graphs/``.

  - ``core/pdf/vision_figure_extractor.py`` sends embedded images to a
    vision model (OlmOCR / Qwen3-VL) for TEXT extraction only — it does
    NOT preserve the image as a cropped asset, and does NOT detect regions.

What's MISSING — and what this module addresses:

  Gap 1 — Vector-drawn diagrams are invisible to PyMuPDF. A chart drawn
    with PDF vector commands (lines, curves, rects) has no embedded raster
    image, so ``page.get_images()`` returns []. pdfplumber's shape scoring
    flags the PAGE as visual, but the existing code screenshots the WHOLE
    page rather than the diagram's bounding box.

  Gap 2 — No VLM-driven region detection. The user's idea: "when model
    sees a chart/diagram/picture, can it crop the PDF and screenshot that?"
    This requires rendering the page as an image and asking a VLM to
    identify non-text regions — then mapping those regions back to PDF
    coordinates and cropping at high DPI.

  Gap 3 — No inline embedding in summary markdown. Crops are saved to
    folders and referenced in a manifest, but never embedded as
    ``![Figure N](path)`` in the actual chapter summary.

This module fills all three gaps with three content-agnostic layers:

  Layer A — Vector-graphics clustering: cluster pdfplumber rects/lines/
    curves into discrete diagram bounding boxes via spatial proximity.
    No hardcoded shapes — works on any vector content.

  Layer B — VLM region detection (optional): render page at low DPI, ask
    a VLM to return JSON bounding boxes of non-text regions, map back to
    PDF coordinates, crop at high DPI. Provider-agnostic (Ollama or
    llama.cpp — same probe pattern as V0.4.1's OCR module).

  Layer C — Inline embedding: generate markdown ``![Figure N](path)``
    tags positioned at the figure's source page, so the summary markdown
    renders the figures inline.

The three layers are composable and content-agnostic. Layer A is always
available (pure pdfplumber). Layer B requires a vision model. Layer C is
purely a markdown transform.

This is a PROTOTYPE for the feasibility investigation. It runs standalone
(no Elixir imports) so it can be validated independently. Integration
into Elixir would replace the standalone VLM call with
``utils.network.safe_ollama_request`` and ``core.llm.ModelManager`` (the
same pattern as ``vision_figure_extractor.py``).
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]

# ─── PDF coordinate conventions ──────────────────────────────────────────────
# PDF user-space units are points (1/72 inch). pdfplumber uses top-left
# origin (y increases downward); PyMuPDF uses top-left origin too. We
# standardize on pdfplumber's (x0, top, x1, bottom) tuple throughout.
# pdf2image renders at DPI (default 200); scale factor = dpi / 72.

DEFAULT_DPI_LOW = 100  # for VLM input (smaller = faster, fewer tokens)
DEFAULT_DPI_HIGH = 200  # for crop output (higher = sharper)


# ─── Data classes ───────────────────────────────────────────────────────────


@dataclass
class Region:
    """A detected non-text region on a page.

    bbox is in PDF user-space points (x0, top, x1, bottom) with top-left
    origin — the same convention as pdfplumber.
    """

    page: int  # 1-indexed page number
    bbox: tuple[float, float, float, float]  # (x0, top, x1, bottom) in points
    source: str  # "pdfplumber_images" | "pdfplumber_tables" | "vector_cluster" | "vlm"
    confidence: float = 1.0  # 0.0–1.0; 1.0 for deterministic sources
    label: str = ""  # optional: "Figure 3", "Table 2", "chart", "diagram"
    crop_path: str = ""  # filled after cropping
    caption: str = ""  # filled after caption extraction

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "bbox": self.bbox,
            "source": self.source,
            "confidence": self.confidence,
            "label": self.label,
            "crop_path": self.crop_path,
            "caption": self.caption,
        }


@dataclass
class CropResult:
    """Result of the full extraction pipeline."""

    regions: list[Region] = field(default_factory=list)
    manifest_md: str = ""
    inline_md: str = ""  # markdown with inline embeds at page markers


# ─── Layer A — Vector-graphics clustering ────────────────────────────────────


def _cluster_shapes(
    shapes: list[dict],
    distance_threshold: float = 80.0,
    min_shapes_per_cluster: int = 5,
) -> list[tuple[float, float, float, float]]:
    """Cluster pdfplumber shapes by spatial proximity.

    Each shape is a dict with at least ``x0, top, x1, bottom`` keys (the
    bounding box of the shape). Returns a list of cluster bounding boxes
    (x0, top, x1, bottom) in PDF points.

    Algorithm: greedy agglomerative clustering. Two passes:
      Pass 1 — assign each shape to the nearest existing cluster (by
      bbox-center distance), or start a new cluster if no cluster is
      within ``distance_threshold``.
      Pass 2 — merge clusters whose bboxes are within ``distance_threshold``
      of each other (catches cases where the cluster center drifted too
      far for later shapes to join, splitting one diagram into multiple
      small clusters).

    Clusters with fewer than ``min_shapes_per_cluster`` shapes are
    dropped (avoids treating stray underline-rule decorative lines as
    diagrams).

    Content-agnostic: works on any vector content (charts, diagrams,
    flowcharts, technical drawings). No hardcoded shapes.

    V0.4.3: distance_threshold raised from 50 to 80 (the V0.4.2 default
    was too tight — a 10-bar chart spread over 300pt got split into
    3-4 small clusters of 3-4 bars each, none reaching the 5-min).
    """
    if not shapes:
        return []

    def _center(bb):
        return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)

    def _dist(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])

    def _merge_bb(a, b):
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

    def _bb_distance(a, b):
        """Minimum distance between two bboxes (0 if they overlap)."""
        dx = max(0, max(a[0], b[0]) - min(a[2], b[2]))
        dy = max(0, max(a[1], b[1]) - min(a[3], b[3]))
        return math.hypot(dx, dy)

    # ── Pass 1: assign each shape to the nearest cluster, or start a new one.
    clusters: list[tuple[tuple, list[dict]]] = []  # (bbox, members)
    for shape in shapes:
        bb = (shape["x0"], shape["top"], shape["x1"], shape["bottom"])
        c = _center(bb)
        # Find nearest cluster by center distance.
        best_idx = -1
        best_d = float("inf")
        for i, (cluster_bb, _) in enumerate(clusters):
            cluster_c = _center(cluster_bb)
            d = _dist(c, cluster_c)
            if d < best_d:
                best_d = d
                best_idx = i
        if best_idx >= 0 and best_d < distance_threshold:
            cluster_bb, members = clusters[best_idx]
            clusters[best_idx] = (_merge_bb(cluster_bb, bb), members + [shape])
        else:
            clusters.append((bb, [shape]))

    # ── Pass 2: merge clusters whose bboxes are within distance_threshold.
    # This catches cases where pass 1 split one diagram into multiple
    # clusters because the cluster center drifted too far for later
    # shapes to join.
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                bb_i, members_i = clusters[i]
                bb_j, members_j = clusters[j]
                if _bb_distance(bb_i, bb_j) < distance_threshold:
                    # Merge cluster j into cluster i.
                    clusters[i] = (_merge_bb(bb_i, bb_j), members_i + members_j)
                    clusters.pop(j)
                    merged = True
                    break
            if merged:
                break

    # Filter clusters with too few shapes.
    result = []
    for cluster_bb, members in clusters:
        if len(members) >= min_shapes_per_cluster:
            result.append(cluster_bb)
    return result


def detect_vector_regions(
    pdf_path: Path,
    pages: list[int],
    log: LogFn | None = None,
    distance_threshold: float = 50.0,
    min_shapes_per_cluster: int = 5,
) -> list[Region]:
    """Layer A: detect vector-drawn diagrams via pdfplumber shape clustering.

    Scans each page's rects, lines, and curves, clusters them by spatial
    proximity, and returns clusters with enough shapes to be a real
    diagram (filters out stray underline-rules and decorative marks).

    Returns a list of :class:`Region` with ``source="vector_cluster"``.
    """
    log = log or (lambda msg, level="INFO": None)
    regions: list[Region] = []
    try:
        import pdfplumber
    except ImportError:
        log("  [vector-clusters] pdfplumber not installed — skipping", "WARNING")
        return regions

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num in pages:
                if page_num - 1 >= len(pdf.pages):
                    continue
                page = pdf.pages[page_num - 1]
                shapes: list[dict] = []
                # pdfplumber rects/lines/curves all have x0/top/x1/bottom.
                shapes.extend(page.rects or [])
                shapes.extend(page.lines or [])
                shapes.extend(page.curves or [])
                if not shapes:
                    continue
                clusters = _cluster_shapes(
                    shapes,
                    distance_threshold=distance_threshold,
                    min_shapes_per_cluster=min_shapes_per_cluster,
                )
                for i, bb in enumerate(clusters):
                    regions.append(
                        Region(
                            page=page_num,
                            bbox=bb,
                            source="vector_cluster",
                            confidence=0.85,  # heuristic — not 1.0
                            label=f"diagram_candidate_{i + 1}",
                        )
                    )
                if clusters:
                    log(
                        f"  [vector-clusters] page {page_num}: {len(clusters)} "
                        f"diagram candidate(s) from {len(shapes)} shapes",
                        "DEBUG",
                    )
    except Exception as e:
        log(f"  [vector-clusters] failed: {type(e).__name__}: {e}", "WARNING")
    return regions


# ─── Layer B — VLM-driven region detection ───────────────────────────────────

_VLM_PROMPT_TEMPLATE = """You are a precise document-layout analyst. Look at the page image and identify every NON-TEXT region — any chart, diagram, figure, photo, table, graph, equation block, or other visual element that is NOT a paragraph of prose.

For each region, return a JSON object with:
- "label": a short type label — one of: "chart", "diagram", "figure", "photo", "table", "equation", "other"
- "bbox": the bounding box as [x0_pct, y0_pct, x1_pct, y1_pct], where each value is a percentage (0.0–100.0) of the image width/height, with (0,0) at the top-left.

Return a JSON array of objects. If there are no non-text regions, return [].

Output ONLY the JSON array — no preamble, no commentary, no code-fence."""


def _parse_vlm_json(raw: str) -> list[dict]:
    """Parse the VLM's JSON array response, tolerant of code-fences and preamble."""
    if not raw:
        return []
    # Strip code fences if present.
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    # Find the first '[' and last ']' to extract the JSON array.
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return []
    try:
        parsed = json.loads(raw[start : end + 1])
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return []


def _pct_bbox_to_pdf(
    bbox_pct: list[float],
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    """Convert a percentage bbox [x0, y0, x1, y1] (0–100) to PDF points."""
    x0_pct, y0_pct, x1_pct, y1_pct = bbox_pct
    x0 = (x0_pct / 100.0) * page_width
    y0 = (y0_pct / 100.0) * page_height
    x1 = (x1_pct / 100.0) * page_width
    y1 = (y1_pct / 100.0) * page_height
    # Clamp to page bounds.
    return (
        max(0.0, min(x0, page_width)),
        max(0.0, min(y0, page_height)),
        max(0.0, min(x1, page_width)),
        max(0.0, min(y1, page_height)),
    )


def detect_vlm_regions(
    pdf_path: Path,
    pages: list[int],
    vlm_callable: Callable[[bytes, str], str] | None = None,
    log: LogFn | None = None,
    dpi_low: int = DEFAULT_DPI_LOW,
) -> list[Region]:
    """Layer B: detect non-text regions using a VLM.

    For each page, render at low DPI, encode as PNG, send to the VLM with
    a prompt asking for JSON bounding boxes of non-text regions, then
    map the percentage-based boxes back to PDF coordinates.

    The VLM is invoked via a callable ``vlm_callable(image_bytes, prompt) -> str``
    so this module stays provider-agnostic. In Elixir integration, the
    callable wraps ``utils.network.safe_ollama_request`` or the
    llama.cpp equivalent — the same pattern as V0.4.1's
    ``vision_figure_extractor.py``.

    If ``vlm_callable`` is None, returns [] (graceful no-op — allows
    degrading to Layer A only when no vision model is available).

    Returns a list of :class:`Region` with ``source="vlm"``.
    """
    log = log or (lambda msg, level="INFO": None)
    if vlm_callable is None:
        log("  [vlm] no vlm_callable provided — skipping VLM detection", "DEBUG")
        return []

    regions: list[Region] = []
    try:
        import pdfplumber
        from pdf2image import convert_from_path
    except ImportError as e:
        log(f"  [vlm] missing dependency: {e}", "WARNING")
        return regions

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num in pages:
                if page_num - 1 >= len(pdf.pages):
                    continue
                page = pdf.pages[page_num - 1]
                page_w = float(page.width)
                page_h = float(page.height)

                # Render at low DPI for the VLM input.
                images = convert_from_path(
                    str(pdf_path),
                    first_page=page_num,
                    last_page=page_num,
                    dpi=dpi_low,
                )
                if not images:
                    continue
                img = images[0]

                # Encode as PNG bytes.
                import io

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()

                # Query the VLM.
                try:
                    raw = vlm_callable(image_bytes, _VLM_PROMPT_TEMPLATE)
                except Exception as e:
                    log(
                        f"  [vlm] page {page_num} call failed: {type(e).__name__}: {e}",
                        "WARNING",
                    )
                    continue

                parsed = _parse_vlm_json(raw)
                if not parsed:
                    log(f"  [vlm] page {page_num}: no regions parsed", "DEBUG")
                    continue

                for entry in parsed:
                    bbox_pct = entry.get("bbox")
                    label = entry.get("label", "other")
                    if not (isinstance(bbox_pct, list) and len(bbox_pct) == 4):
                        continue
                    try:
                        bbox_pct_floats = [float(v) for v in bbox_pct]
                    except (TypeError, ValueError):
                        continue
                    bbox_pdf = _pct_bbox_to_pdf(bbox_pct_floats, page_w, page_h)
                    regions.append(
                        Region(
                            page=page_num,
                            bbox=bbox_pdf,
                            source="vlm",
                            confidence=0.75,  # VLM — depends on model
                            label=label,
                        )
                    )
                log(
                    f"  [vlm] page {page_num}: {len(parsed)} region(s) detected",
                    "DEBUG",
                )
    except Exception as e:
        log(f"  [vlm] failed: {type(e).__name__}: {e}", "WARNING")
    return regions


# ─── Cropping ────────────────────────────────────────────────────────────────


def crop_region(
    pdf_path: Path,
    region: Region,
    output_dir: Path,
    dpi: int = DEFAULT_DPI_HIGH,
    log: LogFn | None = None,
) -> str:
    """Crop a single region from the PDF at high DPI.

    Uses pdf2image to render the page, then PIL to crop the bbox. Saves
    as PNG (or JPEG for large regions) and returns the output path.
    """
    log = log or (lambda msg, level="INFO": None)
    try:
        from pdf2image import convert_from_path
    except ImportError:
        log("  [crop] pdf2image not installed — cannot crop", "WARNING")
        return ""

    try:
        images = convert_from_path(
            str(pdf_path),
            first_page=region.page,
            last_page=region.page,
            dpi=dpi,
        )
        if not images:
            return ""
        img = images[0]
        # PDF points → pixels: scale = dpi / 72
        scale = dpi / 72.0
        x0, top, x1, bottom = region.bbox
        crop = img.crop(
            (
                int(x0 * scale),
                int(top * scale),
                int(x1 * scale),
                int(bottom * scale),
            )
        )
        # Skip tiny crops (< 50x50 px — likely noise).
        if crop.width < 50 or crop.height < 50:
            log(
                f"  [crop] page {region.page} {region.label}: too small "
                f"({crop.width}x{crop.height}px), skipping",
                "DEBUG",
            )
            return ""

        # Use JPEG for large crops (smaller file), PNG for small.
        suffix = ".jpg" if (crop.width * crop.height) > 250_000 else ".png"
        out_path = output_dir / f"page{region.page:03d}_{region.source}_{region.label}{suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".jpg":
            crop.save(str(out_path), "JPEG", quality=90)
        else:
            crop.save(str(out_path), "PNG")
        log(
            f"  [crop] page {region.page} {region.label} → {out_path.name} "
            f"({crop.width}x{crop.height}px)",
            "DEBUG",
        )
        return str(out_path)
    except Exception as e:
        log(f"  [crop] page {region.page} {region.label} failed: {type(e).__name__}: {e}", "WARNING")
        return ""


# ─── Caption extraction ─────────────────────────────────────────────────────


_FIG_CAPTION_RE = re.compile(
    r"(?i)(Figure|Fig\.?|Table|Chart|Diagram|Eq\.?|Equation)\s*"
    r"(\d+([.\-]\d+)*)\s*[:.\-–]?\s*([^\n.]{10,250}\.?)"
)


def extract_caption_near_region(
    pdf_path: Path,
    region: Region,
    search_window_chars: int = 200,
    log: LogFn | None = None,
) -> str:
    """Extract a caption for a region by searching the page text near the region.

    Heuristic: look for "Figure N", "Table N", "Chart N", "Diagram N"
    patterns in the page text, prefer ones whose bbox is within ~50pts
    of the region's bbox. Returns the caption text (truncated to 200
    chars) or "" if no caption found.

    Content-agnostic: the regex matches any figure/table label, not
    specific labels.
    """
    log = log or (lambda msg, level="INFO": None)
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if region.page - 1 >= len(pdf.pages):
                return ""
            page = pdf.pages[region.page - 1]
            words = page.extract_words(extra_attrs=["fontname", "size"]) or []
            if not words:
                return ""
            # Concatenate words into a text string with positions.
            text_line = " ".join(w["text"] for w in words)
            # Find caption patterns.
            for m in _FIG_CAPTION_RE.finditer(text_line):
                # Heuristic: prefer captions whose first word is near the
                # region's vertical center (within 1/3 of page height).
                first_word_idx = text_line[: m.start()].count(" ")
                if first_word_idx < len(words):
                    cap_word = words[first_word_idx]
                    cap_y = (cap_word["top"] + cap_word["bottom"]) / 2
                    region_y = (region.bbox[1] + region.bbox[3]) / 2
                    page_h = float(page.height)
                    if abs(cap_y - region_y) < page_h / 3:
                        return m.group(0).strip()[:200]
            # No near caption — return the first match (if any) as a fallback.
            m = _FIG_CAPTION_RE.search(text_line)
            if m:
                return m.group(0).strip()[:200]
    except Exception as e:
        log(f"  [caption] p{region.page}: {type(e).__name__}: {e}", "DEBUG")
    return ""


# ─── Inline markdown embedding (Layer C) ────────────────────────────────────


def build_inline_markdown(
    markdown_text: str,
    regions: list[Region],
    page_marker_regex: str = r"<!-- original page (\d+) -->",
) -> str:
    """Inject ``![Figure N](path)`` tags at the right page markers.

    For each region with a ``crop_path``, finds the page marker
    ``<!-- original page N -->`` in the markdown and inserts the image
    embed right after it. If no page marker exists, appends at the end.

    Content-agnostic: works on any markdown with the standard Elixir
    page-marker comment.
    """
    if not regions:
        return markdown_text
    by_page: dict[int, list[Region]] = {}
    for r in regions:
        if r.crop_path:
            by_page.setdefault(r.page, []).append(r)

    if not by_page:
        return markdown_text

    lines = markdown_text.splitlines()
    out_lines: list[str] = []
    pattern = re.compile(page_marker_regex)
    inserted_pages: set[int] = set()
    for line in lines:
        out_lines.append(line)
        m = pattern.search(line)
        if m:
            page_num = int(m.group(1))
            if page_num in by_page:
                for r in by_page[page_num]:
                    cap = f": {r.caption}" if r.caption else ""
                    out_lines.append("")
                    out_lines.append(
                        f"![{r.label}{cap}]({r.crop_path})"
                    )
                    out_lines.append("")
                inserted_pages.add(page_num)

    # Append any regions whose page marker wasn't found.
    for page_num, regs in by_page.items():
        if page_num in inserted_pages:
            continue
        out_lines.append("")
        out_lines.append(f"<!-- regions from page {page_num} (no page marker found) -->")
        for r in regs:
            cap = f": {r.caption}" if r.caption else ""
            out_lines.append(f"![{r.label}{cap}]({r.crop_path})")
        out_lines.append("")

    return "\n".join(out_lines)


# ─── V0.4.3: vlm_callable bridge (reuses V0.4.1 vision probe) ────────────────


def build_vlm_callable_from_request(request, log: LogFn | None = None) -> Callable[[bytes, str], str] | None:
    """Construct a ``vlm_callable`` from the conversion request's model config.

    Reuses V0.4.1's provider-agnostic vision probe: tries the main model
    first, then a separate OCR model, then returns None (Layer B disabled).

    The returned callable wraps the provider's vision call and returns the
    raw text response (parsed by the caller via ``_parse_vlm_json``).

    This is a thin adapter — it does NOT duplicate the probe logic, it just
    routes the existing ``core.llm`` provider infrastructure into the
    ``vlm_callable(image_bytes, prompt) -> str`` signature that
    ``detect_vlm_regions`` expects.

    Args:
        request: a ConversionRequest with ``model_architecture``,
            ``summarisation_model``, and ``primary_ocr_model`` fields.
        log: optional ``f(msg, level)`` callback.

    Returns:
        A callable, or None if no vision model is available.
    """
    log = log or (lambda msg, level="INFO": None)
    try:
        from core.llm.llm_provider_impl import create_provider
        from utils.settings import Settings as _S

        settings = _S()
        arch = getattr(request, "model_architecture", "single_local") or "single_local"

        # Determine the provider name from the architecture (mirror V0.4.1).
        if arch == "llamacpp":
            provider_name = "llamacpp"
        elif arch in ("single_api", "dual_api"):
            provider_name = settings.get("summarisation.cloud_provider", "openai_compatible")
        else:
            provider_name = "ollama"

        # Only local providers (Ollama or llama.cpp) are supported for the
        # vision-region probe (same constraint as V0.4.1's OCR path).
        if provider_name not in ("ollama", "llamacpp"):
            log(
                f"  [vlm-bridge] provider '{provider_name}' not supported for vision-region probe — Layer B disabled",
                "DEBUG",
            )
            return None

        # Try the main model first, then a separate OCR model.
        candidates = []
        main_model = getattr(request, "summarisation_model", "") or ""
        ocr_model = getattr(request, "primary_ocr_model", "") or ""
        if main_model:
            candidates.append(main_model)
        if ocr_model and ocr_model != main_model:
            candidates.append(ocr_model)

        for model_name in candidates:
            try:
                provider = create_provider(provider_name, settings)
                if provider and provider.supports_vision():
                    log(
                        f"  [vlm-bridge] model '{model_name}' has vision — using it for region detection",
                        "INFO",
                    )

                    def _callable(image_bytes: bytes, prompt: str, _prov=provider) -> str:
                        # Use the provider's complete_with_image method
                        # (signature: prompt, image_bytes, temperature, max_tokens).
                        # Returns the raw text response, or None on failure.
                        result = _prov.complete_with_image(
                            prompt=prompt,
                            image_bytes=image_bytes,
                            temperature=0.0,
                            max_tokens=1024,
                        )
                        return result or ""

                    return _callable
            except Exception as e:
                log(f"  [vlm-bridge] probe for '{model_name}' failed: {type(e).__name__}: {e}", "DEBUG")

        log(
            "  [vlm-bridge] no vision-capable model found — Layer B disabled (Layer A still runs)",
            "INFO",
        )
        return None
    except Exception as e:
        log(f"  [vlm-bridge] crashed (non-fatal): {type(e).__name__}: {e}", "WARNING")
        return None


# ─── Public pipeline entry ──────────────────────────────────────────────────


def extract_visual_regions(
    pdf_path: Path,
    output_dir: Path,
    pages: list[int],
    vlm_callable: Callable[[bytes, str], str] | None = None,
    log_callback: LogFn | None = None,
    enable_vector_clustering: bool = True,
    enable_vlm: bool = True,
    enable_existing_extractors: bool = True,
) -> CropResult:
    """Full pipeline: existing extractors + vector clusters + VLM regions.

    Layers run in this order (later layers can fill gaps left by earlier):
      1. Existing PDF-metadata extractors (PyMuPDF images, pdfplumber tables)
         — reuses Elixir's ``figure_table_cropper.extract_figures_and_tables``.
      2. Vector-graphics clustering (Layer A) — catches vector-drawn
         diagrams that have no embedded raster image.
      3. VLM region detection (Layer B) — catches anything the other
         layers miss (mixed content, unusual layouts).
      4. De-duplicate overlapping regions (prefer higher-confidence source).
      5. Crop all surviving regions at high DPI.
      6. Extract captions for each region.
      7. Build inline markdown (Layer C).

    Args:
        pdf_path: Path to the PDF.
        output_dir: Where to save cropped images (sub-folder ``regions/``).
        pages: 1-indexed page numbers to process.
        vlm_callable: optional ``f(image_bytes, prompt) -> str`` returning
            raw text (parsed as JSON array). If None, Layer B is skipped.
        log_callback: ``f(msg, level)`` for logging.
        enable_vector_clustering: if False, skip Layer A.
        enable_vlm: if False, skip Layer B.
        enable_existing_extractors: if False, skip the PyMuPDF/pdfplumber
            re-extraction (use this if the caller has already run
            ``figure_table_cropper`` and only wants the gap-fillers).

    Returns:
        :class:`CropResult` with regions, manifest markdown, and inline markdown.
    """
    log = log_callback or (lambda msg, level="INFO": None)
    regions: list[Region] = []
    crops_dir = output_dir / "regions"
    crops_dir.mkdir(parents=True, exist_ok=True)

    # ── Layer 0: existing PDF-metadata extractors ────────────────────────
    if enable_existing_extractors:
        try:
            # Import Elixir's existing extractor (the prototype falls back
            # to a no-op if the import fails — keeps the prototype runnable
            # standalone for the feasibility demo).
            from core.pdf.figure_table_cropper import extract_figures_and_tables

            figures, tables = extract_figures_and_tables(
                pdf_path=pdf_path,
                output_dir=output_dir,
                total_pages=max(pages) if pages else 0,
                log_callback=log,
                valid_pages=set(pages),
                vlm_callable=vlm_callable,  # V0.4.17: pass VLM for validation
            )
            for fig in figures:
                regions.append(
                    Region(
                        page=fig["page"],
                        bbox=(0, 0, 0, 0),  # figure_table_cropper doesn't return bbox
                        source="pdfplumber_images",
                        confidence=1.0,
                        label=fig.get("caption") or "figure",
                        crop_path=fig["path"],
                        caption=fig.get("caption", ""),
                    )
                )
            for tbl in tables:
                regions.append(
                    Region(
                        page=tbl["page"],
                        bbox=(0, 0, 0, 0),
                        source="pdfplumber_tables",
                        confidence=1.0,
                        label=tbl.get("caption") or "table",
                        crop_path=tbl["path"],
                        caption=tbl.get("caption", ""),
                    )
                )
        except ImportError:
            log(
                "  [pipeline] core.pdf.figure_table_cropper unavailable "
                "(standalone mode) — skipping Layer 0",
                "DEBUG",
            )
        except Exception as e:
            log(f"  [pipeline] Layer 0 failed: {type(e).__name__}: {e}", "WARNING")

    # ── Layer A: vector-graphics clustering ──────────────────────────────
    if enable_vector_clustering:
        vregions = detect_vector_regions(pdf_path, pages, log=log)
        regions.extend(vregions)
        log(f"  [pipeline] Layer A (vector clusters): +{len(vregions)} regions", "INFO")

    # ── Layer B: VLM region detection ────────────────────────────────────
    if enable_vlm and vlm_callable is not None:
        vregions = detect_vlm_regions(pdf_path, pages, vlm_callable=vlm_callable, log=log)
        regions.extend(vregions)
        log(f"  [pipeline] Layer B (VLM): +{len(vregions)} regions", "INFO")

    # ── De-duplicate overlapping regions ─────────────────────────────────
    regions = _deduplicate_regions(regions)
    log(f"  [pipeline] after de-dup: {len(regions)} regions", "INFO")

    # ── Crop all regions without a crop_path ─────────────────────────────
    for r in regions:
        if not r.crop_path and r.bbox != (0, 0, 0, 0):
            r.crop_path = crop_region(pdf_path, r, crops_dir, log=log)
        if not r.caption:
            r.caption = extract_caption_near_region(pdf_path, r, log=log)

    # ── Build manifest + inline markdown ────────────────────────────────
    manifest = _build_manifest(regions)
    inline = ""  # caller supplies source markdown to inject into
    return CropResult(regions=regions, manifest_md=manifest, inline_md=inline)


def _deduplicate_regions(regions: list[Region]) -> list[Region]:
    """Drop regions that significantly overlap a higher-confidence region.

    Two regions overlap if their bounding boxes intersect by >50% of
    the smaller region's area. When overlap is found, the LOWER-
    confidence region is dropped. Ties are broken by source priority:
    ``pdfplumber_*`` (1.0) > ``vector_cluster`` (0.85) > ``vlm`` (0.75).
    """
    if not regions:
        return []

    def _area(bb):
        return max(0, bb[2] - bb[0]) * max(0, bb[3] - bb[1])

    def _overlap_area(a, b):
        x0 = max(a[0], b[0])
        y0 = max(a[1], b[1])
        x1 = min(a[2], b[2])
        y1 = min(a[3], b[3])
        return max(0, x1 - x0) * max(0, y1 - y0)

    # Sort by confidence descending (high-confidence first).
    regions_sorted = sorted(regions, key=lambda r: (-r.confidence, r.source))
    kept: list[Region] = []
    for r in regions_sorted:
        if r.bbox == (0, 0, 0, 0):
            # No bbox (e.g., from existing extractors) — keep as-is.
            kept.append(r)
            continue
        r_area = _area(r.bbox)
        drop = False
        for k in kept:
            if k.bbox == (0, 0, 0, 0):
                continue
            ov = _overlap_area(r.bbox, k.bbox)
            if r_area > 0 and ov / r_area > 0.5:
                drop = True
                break
        if not drop:
            kept.append(r)
    return kept


def _build_manifest(regions: list[Region]) -> str:
    """Build a Markdown manifest of all extracted visual regions."""
    if not regions:
        return "\n\n---\n## Extracted Visual Regions\n\n(No visual regions detected.)\n---\n"
    lines = ["\n\n---\n## Extracted Visual Regions\n"]
    by_page: dict[int, list[Region]] = {}
    for r in regions:
        by_page.setdefault(r.page, []).append(r)
    for page in sorted(by_page):
        lines.append(f"\n### Page {page}\n")
        for r in by_page[page]:
            cap = f" — *{r.caption}*" if r.caption else ""
            conf = f" (conf={r.confidence:.2f})" if r.confidence < 1.0 else ""
            lines.append(
                f"- **{r.label}** [{r.source}]{conf}{cap} — "
                f"bbox=({r.bbox[0]:.0f}, {r.bbox[1]:.0f}, {r.bbox[2]:.0f}, {r.bbox[3]:.0f})"
            )
            if r.crop_path:
                lines.append(f"  ![{r.label}]({r.crop_path})")
    lines.append("\n---\n")
    return "\n".join(lines)


# ─── Demo / validation harness ──────────────────────────────────────────────


def _demo_with_synthetic_pdf() -> None:
    """Validate the pipeline on a synthetic PDF with a vector-drawn diagram.

    Creates a 3-page PDF:
      - Page 1: pure text (no diagram)
      - Page 2: text + a vector-drawn bar chart (10 rects + 5 lines)
      - Page 3: text + an embedded raster image (a generated PNG)

    Then runs the pipeline and reports what each layer detects.
    Requires reportlab + Pillow for synthetic PDF generation.
    """
    print("=== Vision-Region Cropper — synthetic-PDF validation ===\n")
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        print("reportlab not installed — skipping synthetic validation.")
        print("Install with: pip install reportlab pillow")
        return

    import tempfile

    tmpdir = Path(tempfile.mkdtemp(prefix="vision_crop_demo_"))
    pdf_path = tmpdir / "synthetic.pdf"

    # ── Build the synthetic PDF ──────────────────────────────────────────
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    w, h = letter  # 612 x 792 points

    # Page 1: pure text.
    c.drawString(72, h - 72, "This is a pure-text page. No diagrams here.")
    c.drawString(72, h - 100, "Just two paragraphs of prose for testing.")
    c.showPage()

    # Page 2: text + vector-drawn bar chart (10 bars + 5 axis lines).
    c.drawString(72, h - 72, "Page with a vector-drawn bar chart below.")
    chart_x0, chart_y0 = 72, h - 350
    # 10 vertical bars (rects)
    for i in range(10):
        bar_h = 30 + (i * 12)  # increasing heights
        c.rect(chart_x0 + i * 30, chart_y0, 20, bar_h, fill=1, stroke=1)
    # 5 axis lines (lines)
    c.line(chart_x0, chart_y0, chart_x0 + 300, chart_y0)  # x-axis
    c.line(chart_x0, chart_y0, chart_x0, chart_y0 + 200)  # y-axis
    c.line(chart_x0, chart_y0 + 50, chart_x0 + 300, chart_y0 + 50)  # gridline
    c.line(chart_x0, chart_y0 + 100, chart_x0 + 300, chart_y0 + 100)  # gridline
    c.line(chart_x0, chart_y0 + 150, chart_x0 + 300, chart_y0 + 150)  # gridline
    c.drawString(72, h - 380, "Figure 1: Sample bar chart for vector-clustering test.")
    c.showPage()

    # Page 3: text + embedded raster image.
    from PIL import Image

    # Generate a larger image (>5KB so it passes figure_table_cropper's
    # size filter — see core/pdf/figure_table_cropper.py:94).
    # Use a JPEG (more size-efficient for photo-like content) and add
    # noise so the file is comfortably above the 5KB threshold.
    img = Image.new("RGB", (400, 200))  # smaller — point() per-pixel is slow
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    # Gradient background.
    for x in range(400):
        for y in range(200):
            r = (x + y) % 256
            g = (x * 2) % 256
            b = (y * 3) % 256
            draw.point((x, y), fill=(r, g, b))
    # Bars on top.
    for i in range(10):
        bar_h = 20 + i * 12
        draw.rectangle([25 + i * 35, 200 - bar_h, 55 + i * 35, 200], fill="darkblue")
    img_path = tmpdir / "embedded.jpg"
    img.save(str(img_path), "JPEG", quality=85)
    img_size_kb = img_path.stat().st_size / 1024
    print(f"  Embedded image size: {img_size_kb:.1f} KB (must be >5 KB to pass filter)")
    c.drawString(72, h - 72, "Page with an embedded raster image below.")
    c.drawImage(str(img_path), 72, h - 350, width=400, height=200)
    c.drawString(72, h - 380, "Figure 2: Embedded raster image for PyMuPDF test.")
    c.showPage()

    c.save()
    print(f"  Synthetic PDF: {pdf_path} (3 pages)\n")

    # ── Run the pipeline (Layers A + 0, no VLM) ─────────────────────────
    output_dir = tmpdir / "output"
    result = extract_visual_regions(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages=[1, 2, 3],
        vlm_callable=None,  # no VLM in this demo — Layers A + 0 only
        enable_vlm=False,
        log_callback=lambda msg, level: print(f"    [{level}] {msg}") if level != "DEBUG" else None,
    )

    print(f"\n  Result: {len(result.regions)} regions detected")
    for r in result.regions:
        print(
            f"    - page {r.page} | source={r.source:25s} | "
            f"label={r.label:30s} | bbox={r.bbox} | crop={r.crop_path or '(none)'}"
        )

    print("\n  Manifest (first 500 chars):")
    print("  " + result.manifest_md[:500].replace("\n", "\n  "))

    # ── Validate expectations ───────────────────────────────────────────
    print("\n  === Validation ===")
    page2_regions = [r for r in result.regions if r.page == 2]
    page3_regions = [r for r in result.regions if r.page == 3]

    expectations = [
        ("Page 1 has no regions", len([r for r in result.regions if r.page == 1]) == 0),
        ("Page 2 has ≥1 vector_cluster region", len(page2_regions) >= 1),
        (
            "Page 2 vector_cluster covers the chart area",
            any(
                r.source == "vector_cluster"
                and r.bbox[2] - r.bbox[0] > 100  # wide enough to be the chart
                for r in page2_regions
            ),
        ),
        ("Page 3 has ≥1 region (embedded image)", len(page3_regions) >= 1),
    ]
    all_ok = True
    for label, ok in expectations:
        mark = "✓" if ok else "✗"
        print(f"    {mark} {label}")
        if not ok:
            all_ok = False

    print(f"\n  Overall: {'PASS' if all_ok else 'FAIL'}")
    print(f"  Output dir: {output_dir}")
    print(f"  (Synthetic test PDF kept at: {pdf_path})")


if __name__ == "__main__":
    _demo_with_synthetic_pdf()
