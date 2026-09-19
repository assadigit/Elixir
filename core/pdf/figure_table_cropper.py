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
) -> tuple[list[dict], list[dict]]:
    """Extract figures and tables from a scientific PDF.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: The book's output directory (graphs/ and tables/ created inside).
        total_pages: Total number of pages in the PDF.
        log_callback: fn(msg, level) for logging.
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
    graphs_dir = output_dir / "graphs"
    tables_dir = output_dir / "tables"
    # Folders are created lazily when the first figure/table is saved.

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
                        img_path = graphs_dir / f"page{page_num}_figure{fig_count}.{img_ext}"
                        graphs_dir.mkdir(parents=True, exist_ok=True)  # V10.2.2: lazy
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
        log(f"  ✅ Extracted {fig_count} figure(s) → {graphs_dir}", "INFO")

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
                tables_found = page.find_tables()

                for tbl_index, table in enumerate(tables_found):
                    try:
                        # Extract table as structured data
                        table_data = table.extract()
                        if not table_data or len(table_data) < 2:
                            continue  # skip single-row "tables"

                        # Crop the table region as an image
                        bbox = table.bbox  # (x0, top, x1, bottom)
                        if bbox and all(v is not None for v in bbox):
                            im = page.crop(bbox).to_image(resolution=200)
                            tbl_count += 1
                            img_path = tables_dir / f"page{page_num}_table{tbl_count}.jpg"
                            tables_dir.mkdir(parents=True, exist_ok=True)  # V10.2.2: lazy
                            im.save(str(img_path), format="JPEG")

                            # Also save as Markdown table
                            md_path = tables_dir / f"page{page_num}_table{tbl_count}.md"
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

        log(f"  ✅ Extracted {tbl_count} table(s) → {tables_dir}", "INFO")

    except ImportError:
        log("  ⚠️ pdfplumber not installed — table extraction skipped", "WARNING")
    except Exception as e:
        log(f"  ⚠️ Table extraction failed: {e}", "WARNING")

    return figures, tables


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
