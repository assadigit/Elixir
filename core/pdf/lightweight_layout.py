"""V3.8.0 Phase 4.1: Lightweight layout detection — no detectron2 required.

Uses pdfplumber to detect multi-column layouts and reorder text accordingly.
This replaces the detectron2-based LayoutAnalyzer which always failed.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

class LightweightLayoutDetector:
    """Detect multi-column layouts using pdfplumber's word positions.

    Strategy:
    1. For each page, get word bounding boxes from pdfplumber
    2. Detect if the page has 2+ columns by analyzing word x-positions
    3. If multi-column, sort words by column then by y-position (reading order)
    4. Reconstruct text in correct reading order
    """

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)

    def detect_and_reorder(self, pdf_path: Path, pages: list[int]) -> dict[int, str]:
        """Detect multi-column layouts and return reordered text per page.

        Returns dict: page_num -> reordered text (empty if single-column or failed).
        """
        try:
            import pdfplumber
        except ImportError:
            return {}

        results = {}
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num in pages:
                    if page_num < 1 or page_num > len(pdf.pages):
                        continue
                    page = pdf.pages[page_num - 1]
                    words = page.extract_words(use_text_flow=False)

                    if not words or len(words) < 10:
                        continue

                    # Detect columns
                    columns = self._detect_columns(words, page.width)
                    if len(columns) <= 1:
                        continue  # Single column — no reordering needed

                    # Reorder words by column then y-position
                    reordered = self._reorder_by_columns(words, columns)
                    text = ' '.join(w['text'] for w in reordered)

                    # Clean up spacing
                    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
                    text = re.sub(r'\s{2,}', ' ', text)

                    results[page_num] = text
                    self.log(f"    📐 Multi-column detected on p.{page_num} ({len(columns)} columns) — reordered", "DEBUG")

        except Exception as e:
            self.log(f"  ⚠️ Layout detection failed: {e}", "DEBUG")

        return results

    def _detect_columns(self, words: list[dict], page_width: float) -> list[tuple]:
        """Detect column boundaries from word x-positions.

        Returns list of (x_start, x_end) tuples for each column.
        """
        # Collect all x0 (left edge) positions
        x0s = sorted([w['x0'] for w in words])

        # Find the gap — if there's a large gap in the middle, it's 2 columns
        mid_point = page_width / 2
        left_words = [w for w in words if w['x0'] < mid_point]
        right_words = [w for w in words if w['x0'] >= mid_point]

        if not left_words or not right_words:
            return [(0, page_width)]  # Single column

        # Check if there's a significant gap between left and right
        left_max_x = max(w['x1'] for w in left_words)
        right_min_x = min(w['x0'] for w in right_words)
        gap = right_min_x - left_max_x

        # If gap > 5% of page width, it's likely 2 columns
        if gap > page_width * 0.05:
            return [
                (min(w['x0'] for w in left_words), left_max_x),
                (right_min_x, max(w['x1'] for w in right_words)),
            ]

        return [(0, page_width)]  # Single column

    def _reorder_by_columns(self, words: list[dict], columns: list[tuple]) -> list[dict]:
        """Reorder words by column (left first, then right) then by y-position."""
        column_words = {i: [] for i in range(len(columns))}

        for w in words:
            # Find which column this word belongs to
            for i, (x_start, x_end) in enumerate(columns):
                if w['x0'] >= x_start and w['x0'] <= x_end:
                    column_words[i].append(w)
                    break

        # Sort each column by y-position (top to bottom)
        result = []
        for i in range(len(columns)):
            col_words = sorted(column_words[i], key=lambda w: (w['top'], w['x0']))
            result.extend(col_words)

        return result
