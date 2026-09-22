"""V10.2.0: Figure & Table cropper for scientific articles.

Extracts every figure, chart, and table from a scientific PDF as cropped
images, saved to the project's ``graphs/`` and ``tables/`` folders.

Uses:
  - PyMuPDF (fitz) for image extraction (detects embedded images)
  - pdfplumber for table detection (identifies table bounding boxes)
  - pdf2image for page rendering (crops table regions as images)

The crops are saved as JPEG files with descriptive filenames, and a
manifest is injected into the markdown so the summarizer knows about them.

Output structure:
  graphs/
    page3_figure1.jpg
    page5_chart.jpg
  tables/
    page2_table1.jpg
    page4_table2.jpg
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


def extract_figures_and_tables(
    pdf_path: Path,
    output_dir: Path,
    total_pages: int,
    log_callback: LogFn | None = None,
    valid_pages: set | None = None,
    vlm_callable=None,
) -> tuple[list[dict], list[dict]]:
    """Extract figures and tables from a scientific PDF.

    V0.4.17: added optional ``vlm_callable`` for VLM-based table/figure
    validation. When provided, each detected region is sent to the vision
    model with a "Is this a table, chart, diagram, or just text?" prompt.
    Only regions the VLM confirms as table/chart/diagram are saved. This
    replaces the V0.4.15 Python heuristic (_is_real_table) with a more
    intelligent vision-based filter.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: The book's output directory (images/ created inside).
        total_pages: Total number of pages in the PDF.
        log_callback: fn(msg, level) for logging.
        valid_pages: If set, only process these page numbers.
        vlm_callable: optional ``f(image_bytes, prompt) -> str`` for VLM
            validation. When None, falls back to the V0.4.15 heuristic.
        valid_pages: If set, only process these page numbers.

    Returns:
        (figures, tables) — lists of dicts with keys:
          - page: page number
          - path: path to the cropped image
          - caption: extracted caption text (if any)
          - type: "figure" or "table"
    """
    log = log_callback or (lambda msg, level="INFO": None)
    figures = []
    tables = []

    # V10.2.2: Don't create the folders upfront — only create them if
    # we actually find figures/tables.  This prevents empty folders.
    # V0.4.14: single umbrella folder for all cropped images.
    images_dir = output_dir / "images"
    # Folders are created lazily when the first image is saved.

    pages_to_process = sorted(valid_pages) if valid_pages else list(range(1, total_pages + 1))

    # ── Part 1: Extract embedded images (figures/charts) via PyMuPDF ──────
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        log(
            f"  📊 Figure extraction: scanning {len(pages_to_process)} pages with PyMuPDF...",
            "INFO",
        )

        fig_count = 0
        for page_num in pages_to_process:
            if page_num > len(doc):
                continue
            page = doc[page_num - 1]
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        img_bytes = base_image["image"]
                        # Skip tiny images (< 5KB — probably logos/icons)
                        if len(img_bytes) < 5000:
                            continue
                        img_ext = base_image.get("ext", "jpg")
                        fig_count += 1
                        img_path = images_dir / f"page{page_num}_image{fig_count}_figure.{img_ext}"
                        images_dir.mkdir(parents=True, exist_ok=True)  # V10.2.2: lazy
                        img_path.write_bytes(img_bytes)
                        figures.append(
                            {
                                "page": page_num,
                                "path": str(img_path),
                                "caption": _extract_caption(page, page_num, "figure"),
                                "type": "figure",
                            }
                        )
                except Exception as e:
                    log(f"  ⚠️ Figure extraction p.{page_num} img {img_index}: {e}", "DEBUG")

        doc.close()
        log(f"  ✅ Extracted {fig_count} figure(s) → {images_dir}", "INFO")

    except ImportError:
        log("  ⚠️ PyMuPDF (fitz) not installed — figure extraction skipped", "WARNING")
    except Exception as e:
        log(f"  ⚠️ Figure extraction failed: {e}", "WARNING")

    # ── Part 2: Extract tables via pdfplumber ─────────────────────────────
    try:
        import pdfplumber

        log(
            f"  📊 Table extraction: scanning {len(pages_to_process)} pages with pdfplumber...",
            "INFO",
        )

        tbl_count = 0
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num in pages_to_process:
                if page_num > len(pdf.pages):
                    continue
                page = pdf.pages[page_num - 1]
                # V0.4.13: try both "lattice" (border-based) and "stream"
                # (whitespace-based) table detection strategies. The V0.4.3
                # code only used the default (lattice), which misses
                # borderless tables like Table 3-1 in the NPD chapter
                # (a psychoanalytic textbook with space-aligned tables).
                #
                # V0.4.18: the text-strategy fallback is now CONDITIONAL on
                # having a VLM available. Without a VLM, the text strategy
                # produces too many false positives (text paragraphs
                # misidentified as tables — 24 false positives on the NPD
                # chapter). With a VLM, the text strategy finds borderless
                # tables AND the VLM filters out text paragraphs.
                #
                # Without a VLM: lattice strategy only (fewer crops, but no
                # false positives). Borderless tables will be missed.
                # With a VLM: lattice + text strategy + VLM validation
                # (finds borderless tables AND filters text).
                tables_found = page.find_tables()
                if not tables_found and vlm_callable:
                    # V0.4.18: only use the text-strategy fallback when a
                    # VLM is available to validate the results. Without a
                    # VLM, the text strategy's false positives (text
                    # paragraphs misidentified as tables) ship unchecked.
                    try:
                        tables_found = page.find_tables(
                            table_settings={
                                "vertical_strategy": "text",
                                "horizontal_strategy": "text",
                            }
                        )
                    except Exception:
                        pass

                for tbl_index, table in enumerate(tables_found):
                    try:
                        # Extract table as structured data
                        table_data = table.extract()
                        if not table_data or len(table_data) < 2:
                            continue  # skip single-row "tables"

                        # V0.4.15: validate this is actually a table, not a
                        # text paragraph misidentified by the "text" strategy.
                        # V0.4.17: use VLM validation when available, fall back
                        # to the V0.4.15 heuristic when no VLM.
                        _is_table = False
                        if vlm_callable:
                            # V0.4.17: VLM-based validation — render the crop
                            # and ask the vision model "Is this a table?"
                            bbox_check = table.bbox
                            if bbox_check and all(v is not None for v in bbox_check):
                                im_check = page.crop(bbox_check).to_image(resolution=150)
                                import io as _io

                                buf = _io.BytesIO()
                                try:
                                    im_check.save(buf, format="PNG")
                                except Exception:
                                    im_check.save(buf, format="JPEG")
                                vlm_result = _vlm_validate_region(
                                    buf.getvalue(), vlm_callable, log
                                )
                                if vlm_result == "TABLE":
                                    _is_table = True
                                elif vlm_result == "TEXT":
                                    log(
                                        f"  ⏭️ VLM rejected p.{page_num} tbl {tbl_index}: "
                                        f"classified as TEXT, not a table",
                                        "DEBUG",
                                    )
                                elif vlm_result is None:
                                    log(
                                        f"  ⚠️ VLM classification failed p.{page_num} tbl {tbl_index} "
                                        f"— falling back to heuristic",
                                        "DEBUG",
                                    )
                                    _is_table = _is_real_table(table_data)
                                else:
                                    # VLM said CHART/DIAGRAM/FIGURE — not a table
                                    log(
                                        f"  ⏭️ VLM classified p.{page_num} tbl {tbl_index} "
                                        f"as {vlm_result}, not TABLE — skipping",
                                        "DEBUG",
                                    )
                        else:
                            _is_table = _is_real_table(table_data)

                        if not _is_table:
                            log(
                                f"  ⏭️ Table extraction p.{page_num} tbl {tbl_index}: "
                                f"skipped — detected as text, not a real table",
                                "DEBUG",
                            )
                            continue

                        # Crop the table region as an image
                        bbox = table.bbox  # (x0, top, x1, bottom)
                        if bbox and all(v is not None for v in bbox):
                            im = page.crop(bbox).to_image(resolution=200)
                            tbl_count += 1
                            img_path = images_dir / f"page{page_num}_image{fig_count + tbl_count}_table.jpg"
                            images_dir.mkdir(parents=True, exist_ok=True)  # V10.2.2: lazy
                            # V0.4.14: fix "cannot write mode P as JPEG" —
                            # pdfplumber renders in palette mode ("P") which
                            # JPEG doesn't support. Convert to RGB first.
                            try:
                                im.save(str(img_path), format="JPEG")
                            except Exception:
                                # Fallback: save as PNG (supports all modes)
                                img_path = img_path.with_suffix(".png")
                                im.save(str(img_path), format="PNG")

                            # Also save as Markdown table
                            md_path = images_dir / f"page{page_num}_image{fig_count + tbl_count}_table.md"
                            md_content = _table_to_markdown(table_data)
                            md_path.write_text(md_content, encoding="utf-8")

                            tables.append(
                                {
                                    "page": page_num,
                                    "path": str(img_path),
                                    "caption": _extract_caption_pdfplumber(page, page_num, "table"),
                                    "type": "table",
                                    "data": table_data,
                                }
                            )
                    except Exception as e:
                        log(f"  ⚠️ Table extraction p.{page_num} tbl {tbl_index}: {e}", "DEBUG")

        log(f"  ✅ Extracted {tbl_count} table(s) → {images_dir}", "INFO")

    except ImportError:
        log("  ⚠️ pdfplumber not installed — table extraction skipped", "WARNING")
    except Exception as e:
        log(f"  ⚠️ Table extraction failed: {e}", "WARNING")

    return figures, tables


def _is_real_table(table_data: list) -> bool:
    """V0.4.15: validate that the extracted data is actually a table, not
    a text paragraph misidentified by pdfplumber's "text" strategy.

    The V0.4.13 text-strategy fallback detects multi-column text layouts
    as "tables" because text columns look like table columns. This
    function distinguishes real tables from text by checking:

    1. **Multi-column structure**: 2+ columns (a table needs at least 2).
    2. **Short cells**: the average cell length should be <80 chars.
       Table cells contain fragments (labels, numbers, short phrases),
       not full paragraphs. If the average is >80 chars, it's prose.
    3. **Consistent columns**: most rows have the same column count
       (tables have aligned columns; text paragraphs don't).
    4. **Low word-per-cell ratio**: a real table cell averages <15 words.
       A text paragraph cell has 20+ words.

    Content-agnostic: based purely on structural properties (cell length,
    column count, word count), not on content keywords.
    """
    if not table_data or len(table_data) < 2:
        return False

    # Check 1: need 2+ columns.
    col_counts = [len(row) for row in table_data if row]
    if not col_counts:
        return False
    max_cols = max(col_counts)
    if max_cols < 2:
        return False

    # Check 2: average cell length. Collect all non-empty cells.
    all_cells = []
    for row in table_data:
        if row:
            for cell in row:
                if cell and str(cell).strip():
                    all_cells.append(str(cell).strip())

    if not all_cells:
        return False

    avg_cell_len = sum(len(c) for c in all_cells) / len(all_cells)
    if avg_cell_len > 80:
        # Average cell is >80 chars — this is prose, not a table.
        return False

    # Check 3: column consistency. Most rows should have the same
    # column count (within 1 of the mode).
    from collections import Counter

    col_mode = Counter(col_counts).most_common(1)[0][0]
    consistent = sum(1 for c in col_counts if abs(c - col_mode) <= 1)
    consistency_ratio = consistent / len(col_counts) if col_counts else 0
    if consistency_ratio < 0.7:
        return False

    # Check 4: word-per-cell ratio. Real table cells are short.
    total_words = sum(len(c.split()) for c in all_cells)
    avg_words = total_words / len(all_cells)
    if avg_words > 15:
        return False

    return True


# ── V0.4.17: VLM-based table/figure validation ────────────────────────────

_VLM_CLASSIFY_PROMPT = """Look at this image and classify it as one of:
- TABLE: a structured table with rows and columns of data
- CHART: a chart, graph, or plot (bar, line, pie, scatter, etc.)
- DIAGRAM: a flowchart, schematic, org chart, or other diagram
- FIGURE: an illustration, photo, or infographic
- TEXT: just plain text paragraphs or headings (NOT a visual element)

Output ONLY one word: TABLE, CHART, DIAGRAM, FIGURE, or TEXT.
"""


def _vlm_validate_region(
    image_bytes: bytes,
    vlm_callable,
    log: LogFn,
) -> str | None:
    """V0.4.17: ask the VLM to classify the cropped region.

    Returns one of: "TABLE", "CHART", "DIAGRAM", "FIGURE", "TEXT", or
    None (if the VLM call fails or returns an unparseable response).
    """
    if not vlm_callable:
        return None  # no VLM — fall back to heuristic
    try:
        raw = vlm_callable(image_bytes, _VLM_CLASSIFY_PROMPT)
        if not raw:
            return None
        # Parse the response — the VLM should output one word.
        word = raw.strip().upper().split()[0] if raw.strip() else ""
        # Strip any punctuation.
        word = word.rstrip(".!?,;:")
        if word in ("TABLE", "CHART", "DIAGRAM", "FIGURE", "TEXT"):
            return word
        # Check if the word appears anywhere in the response.
        for kw in ("TABLE", "CHART", "DIAGRAM", "FIGURE", "TEXT"):
            if kw in raw.upper():
                return kw
        return None
    except Exception as e:
        log(f"  ⚠️ VLM classification failed: {type(e).__name__}: {e}", "DEBUG")
        return None


def _extract_caption(page, page_num: int, label: str) -> str:
    """Extract figure/table caption from a PyMuPDF page."""
    try:
        text = page.get_text()
        # Look for "Figure N" or "Table N" patterns
        pattern = rf"(?i)({label}\s*\d+[^.]*\.)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:200]
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
    return ""


def _extract_caption_pdfplumber(page, page_num: int, label: str) -> str:
    """Extract figure/table caption from a pdfplumber page."""
    try:
        text = page.extract_text() or ""
        pattern = rf"(?i)({label}\s*\d+[^.]*\.)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:200]
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
    return ""


def _table_to_markdown(data: list) -> str:
    """Convert a 2D table (list of lists) to Markdown format."""
    if not data:
        return ""
    lines = []
    # Header row
    header = data[0]
    lines.append("| " + " | ".join(str(c or "") for c in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    # Data rows
    for row in data[1:]:
        lines.append("| " + " | ".join(str(c or "") for c in row) + " |")
    return "\n".join(lines)


def build_figure_table_manifest(figures: list, tables: list) -> str:
    """Build a Markdown manifest of all extracted figures and tables.

    This is injected into the raw markdown so the summarizer knows about
    the figures and tables and can reference them in the summary.
    """
    lines = ["\n\n---\n## Extracted Figures and Tables\n"]
    if figures:
        lines.append("### Figures\n")
        for fig in figures:
            lines.append(
                f"- **{fig['caption'] or 'Figure'}** (page {fig['page']}) — `{fig['path']}`"
            )
    if tables:
        lines.append("\n### Tables\n")
        for tbl in tables:
            lines.append(
                f"- **{tbl['caption'] or 'Table'}** (page {tbl['page']}) — `{tbl['path']}`"
            )
    if not figures and not tables:
        lines.append("(No figures or tables detected in this document.)")
    lines.append("\n---\n")
    return "\n".join(lines)
