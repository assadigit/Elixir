"""V3.9.0 + V4.7.2 Structured Table + Graph Extraction with Smart Filtering.

Extracts tables and graphs from PDFs as:
1. tables.md — Markdown tables with extracted data
2. graphs.md — Descriptions of charts/graphs (FILTERED to pages with visual elements)
3. tables/ folder — Screenshots of each table
4. graphs/ folder — Screenshots of pages with detected charts/diagrams only
5. screenshots/ folder — Full page screenshots of EVERY page in the processing range

V4.7.2: Uses pdfplumber's shape detection (rects, lines, curves, images) to
filter which pages contain visual elements (charts, diagrams, graphs). Only
those pages are included in graphs.md — reducing 174 screenshots to maybe
5-10 actual chart pages. A separate screenshots/ folder captures every page
for full visual reference.

Usage:
    extractor = TableGraphExtractor(log_callback=log)
    extractor.extract(input_pdf_path, output_dir, pages=[1,2,3...])
    # → output_dir/tables.md
    # → output_dir/graphs.md
    # → output_dir/tables/table_001_p5.png
    # → output_dir/graphs/graph_001_p7.png
    # → output_dir/screenshots/page_001.png  (every page)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class TableGraphExtractor:
    """Extract tables and graphs from PDF with screenshots for verification."""

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)

    def extract(
        self,
        pdf_path: Path,
        output_dir: Path,
        pages: list[int],
        book_title: str = "",
    ) -> dict:
        """Extract tables and graphs from specified pages.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Where to save tables.md, graphs.md, and folders.
            pages: List of page numbers to process (1-indexed).
            book_title: The book's title, used in screenshot filenames.
                        (e.g., "Agent of Influence" → page_005_Agent_of_Influence.jpg)

        Returns dict with:
        - tables_md: Path to tables.md
        - graphs_md: Path to graphs.md
        - table_count: Number of tables extracted
        - graph_count: Number of graph/chart pages detected
        - screenshot_count: Total page screenshots captured
        - screenshots: List of all screenshot paths
        """
        tables_dir = output_dir / "tables"
        graphs_dir = output_dir / "graphs"
        screenshots_dir = output_dir / "screenshots"
        tables_dir.mkdir(parents=True, exist_ok=True)
        graphs_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        table_entries = []
        graph_entries = []
        all_screenshots = []

        # ── 0. Detect visual pages using pdfplumber shape detection ──────
        visual_pages = self._detect_visual_pages(pdf_path, pages)
        self.log(
            f"  📈 Visual page detection: {len(visual_pages)}/{len(pages)} "
            f"pages have charts/diagrams/graphs",
            "INFO",
        )

        # ── 1. Extract tables using Camelot (if available) ────────────────
        table_count = 0
        try:
            import camelot

            for page_num in pages:
                try:
                    tables = camelot.read_pdf(str(pdf_path), pages=str(page_num), flavor="lattice")
                    for _i, table in enumerate(tables):
                        table_count += 1
                        df = table.df
                        md_table = (
                            df.to_markdown(index=False)
                            if hasattr(df, "to_markdown")
                            else self._df_to_markdown(df)
                        )

                        screenshot_path = tables_dir / f"table_{table_count:03d}_p{page_num}.png"
                        self._capture_page_screenshot(pdf_path, page_num, screenshot_path)
                        all_screenshots.append(screenshot_path)

                        table_entries.append(
                            {
                                "number": table_count,
                                "page": page_num,
                                "markdown": md_table,
                                "screenshot": str(screenshot_path),
                            }
                        )
                except Exception as e:
                    self.log(f"  ⚠️ Table extraction p.{page_num}: {e}", "DEBUG")
        except ImportError:
            self.log("  ℹ️ Camelot not installed — table extraction skipped", "DEBUG")

        # ── 2. Capture screenshots for visual pages (graphs/charts) ───────
        graph_count = 0
        for page_num in visual_pages:
            try:
                screenshot_path = graphs_dir / f"page_{page_num:03d}.png"
                if self._capture_page_screenshot(pdf_path, page_num, screenshot_path):
                    graph_count += 1
                    all_screenshots.append(screenshot_path)
                    graph_entries.append(
                        {
                            "number": graph_count,
                            "page": page_num,
                            "screenshot": str(screenshot_path),
                            "note": "Page with detected visual elements (chart/diagram/graph)",
                        }
                    )
            except Exception as e:
                self.log(f"  ⚠️ Graph screenshot p.{page_num}: {e}", "DEBUG")

        # ── 3. Capture EVERY page to screenshots/ folder (full reference) ─
        # V4.7.7: JPEG format + naming convention: page_NNN_bookname.jpg
        # Only captures pages in the selected chapters' range.
        import re as _re

        safe_title = _re.sub(r"[^\w\s-]", "", book_title).strip().replace(" ", "_")
        if not safe_title:
            safe_title = "page"
        screenshot_count = 0
        for page_num in pages:
            try:
                screenshot_path = screenshots_dir / f"page_{page_num:03d}_{safe_title}.jpg"
                if self._capture_page_screenshot(pdf_path, page_num, screenshot_path, jpeg=True):
                    screenshot_count += 1
                    all_screenshots.append(screenshot_path)
            except Exception as e:
                logger.debug("page %d screenshot failed: %s: %s", page_num, type(e).__name__, e)
        self.log(
            f"  📸 Full screenshots: {screenshot_count}/{len(pages)} pages → screenshots/ (JPEG)",
            "INFO",
        )

        # ── 4. Write tables.md ────────────────────────────────────────────
        tables_md_path = output_dir / "tables.md"
        tables_content = self._build_tables_md(table_entries)
        tables_md_path.write_text(tables_content, encoding="utf-8")
        if table_entries:
            self.log(f"  📊 Tables: {table_count} extracted → {tables_md_path}", "INFO")

        # ── 5. Write graphs.md (only visual pages) ────────────────────────
        graphs_md_path = output_dir / "graphs.md"
        graphs_content = self._build_graphs_md(graph_entries, len(pages), len(visual_pages))
        graphs_md_path.write_text(graphs_content, encoding="utf-8")
        self.log(f"  📈 Graphs: {graph_count} visual pages → {graphs_md_path}", "INFO")

        return {
            "tables_md": tables_md_path if table_entries else None,
            "graphs_md": graphs_md_path,
            "table_count": table_count,
            "graph_count": graph_count,
            "screenshot_count": screenshot_count,
            "screenshots": [str(s) for s in all_screenshots],
        }

    # ── V4.7.2: Visual page detection using pdfplumber ─────────────────────

    def _detect_visual_pages(self, pdf_path: Path, pages: list[int]) -> list[int]:
        """Detect which pages contain visual elements (charts, diagrams, graphs).

        Uses pdfplumber's shape detection:
        - ``page.rects`` — rectangles (chart bars, table cells)
        - ``page.lines`` — lines (axes, gridlines)
        - ``page.curves`` — curves (pie charts, line graphs)
        - ``page.images`` — embedded raster images

        A scoring system determines if a page is "visual":
        - Has images: +3 points
        - Has >10 rects: +2 points
        - Has >5 curves: +2 points
        - Has >20 lines: +1 point
        - Word count < 50 (mostly visual): +2 points

        Pages with score >= 3 are considered visual.
        """
        visual_pages = []
        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num in pages:
                    # pdfplumber uses 0-indexed pages
                    if page_num - 1 >= len(pdf.pages):
                        continue
                    page = pdf.pages[page_num - 1]
                    score = self._score_page_visual(page)
                    if score >= 3:
                        visual_pages.append(page_num)
        except Exception as e:
            self.log(f"  ⚠️ Visual detection failed ({e}), including all pages", "DEBUG")
            return pages  # fallback: include all pages
        return visual_pages

    @staticmethod
    def _score_page_visual(page) -> int:
        """Score a page's visual content. Returns 0-10.

        Higher score = more likely to contain a chart/diagram/graph.
        """
        score = 0
        try:
            rects = page.rects or []
            lines = page.lines or []
            curves = page.curves or []
            images = page.images or []
            words = page.extract_words() or []

            # Embedded images (strong signal)
            if len(images) > 0:
                score += 3

            # Many rectangles (chart bars, table grids)
            if len(rects) > 10:
                score += 2
            elif len(rects) > 5:
                score += 1

            # Curves (pie charts, line graphs, diagrams)
            if len(curves) > 5:
                score += 2
            elif len(curves) > 0:
                score += 1

            # Many lines (axes, gridlines)
            if len(lines) > 20:
                score += 1

            # Low word count = mostly visual page
            if len(words) < 50:
                score += 2
            elif len(words) < 100:
                score += 1
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return score

    def _df_to_markdown(self, df) -> str:
        """Convert DataFrame to markdown table (fallback if to_markdown unavailable)."""
        lines = []
        # Header
        lines.append("| " + " | ".join(str(c) for c in df.columns) + " |")
        lines.append("| " + " | ".join("---" for _ in df.columns) + " |")
        # Rows
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(v) for v in row) + " |")
        return "\n".join(lines)

    def _build_tables_md(self, entries: list[dict]) -> str:
        """Build tables.md content."""
        if not entries:
            return "# Tables\n\nNo tables detected in this document.\n"

        lines = ["# Tables", "", f"**Total tables extracted:** {len(entries)}", ""]
        lines.append("> ⚠️ Numbers are extracted by Camelot (deterministic, non-hallucinated).")
        lines.append("> Screenshots are included in the `tables/` folder for manual verification.")
        lines.append("")

        for entry in entries:
            lines.append(f"## Table {entry['number']} (Page {entry['page']})")
            lines.append(f"![Table {entry['number']}]({entry['screenshot']})")
            lines.append("")
            lines.append(entry["markdown"])
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _build_graphs_md(
        self, entries: list[dict], total_pages: int = 0, visual_count: int = 0
    ) -> str:
        """Build graphs.md content (only visual pages).

        V4.7.2: Now shows only pages with detected visual elements, not
        every page. Also reports the detection stats.
        """
        if not entries:
            return (
                "# Graphs & Charts\n\n"
                f"**Pages scanned:** {total_pages} | "
                f"**Visual pages detected:** {visual_count}\n\n"
                "No pages with charts, diagrams, or graphs were detected.\n"
                "Full page screenshots of all pages are in the `screenshots/` folder.\n"
            )

        lines = [
            "# Graphs & Charts",
            "",
            f"**Pages scanned:** {total_pages} | **Visual pages detected:** {visual_count}",
            "",
            "> 📈 Only pages with detected visual elements (charts, diagrams, "
            "graphs) are listed below. Detection uses pdfplumber's shape "
            "analysis (rectangles, curves, lines, embedded images).",
            "> Screenshots are in the `graphs/` folder.",
            "> Full page screenshots of ALL pages are in the `screenshots/` folder.",
            "> The LLM does NOT interpret these — all numbers must be verified by human.",
            "",
        ]

        for entry in entries:
            lines.append(f"## Page {entry['page']}")
            lines.append(f"![Page {entry['page']}]({entry['screenshot']})")
            lines.append(f"*{entry['note']}*")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _capture_page_screenshot(
        self, pdf_path: Path, page_num: int, output_path: Path, jpeg: bool = False
    ) -> bool:
        """Capture a full-page screenshot. Returns True on success.

        V4.7.7: Supports JPEG output (smaller files for screenshots folder).
        """
        try:
            from pdf2image import convert_from_path

            from utils.settings import Settings

            settings = Settings()
            poppler_path = settings.get("paths.poppler") or None

            images = convert_from_path(
                str(pdf_path),
                first_page=page_num,
                last_page=page_num,
                dpi=200,
                poppler_path=poppler_path,
            )
            if images:
                if jpeg:
                    images[0].save(str(output_path), "JPEG", quality=85)
                else:
                    images[0].save(str(output_path), "PNG")
                return True
        except Exception as e:
            self.log(f"  ⚠️ Screenshot p.{page_num}: {e}", "DEBUG")
        return False
