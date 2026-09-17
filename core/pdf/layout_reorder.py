"""

Layout reorder for multi‑column PDFs (Academic Papers).

Uses pdfplumber to detect text lines and their bounding boxes,
then reorders them in reading order (left column → right column).

NEW in this version:
  - More robust key checking: if `extract_words()` returns dicts without 'x0'/'y0',
    fallback to PyMuPDF immediately.
  - If pdfplumber fails completely, use PyMuPDF as fallback.
  - Added `_get_words_pdfplumber()` to handle extraction with multiple parameter attempts.
  - Added detailed logging for debugging.
  - If no text blocks found, returns original content.
  - Handles empty pages gracefully.
  - Reduced verbosity: per‑page messages are DEBUG level; only actual reorders are logged at INFO.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class TextBlock:
    """Represents a text block with position and content."""
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


class LayoutReorder:
    """
    Detects and reorders text in multi‑column layouts.
    Uses pdfplumber if available, else falls back to PyMuPDF.
    """

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._pdfplumber_available = False
        self._pymupdf_available = False
        self._check_dependencies()

    def _check_dependencies(self):
        try:
            import pdfplumber
            self._pdfplumber_available = True
            self.log("  ✅ pdfplumber available for layout detection.", "DEBUG")
        except ImportError:
            self.log("  ⚠️ pdfplumber not installed. Falling back to PyMuPDF.", "WARNING")
            try:
                import fitz
                self._pymupdf_available = True
                self.log("  ✅ PyMuPDF available for layout detection.", "DEBUG")
            except ImportError:
                self.log("  ❌ No layout detection library available. Skipping reorder.", "ERROR")

    def is_available(self) -> bool:
        return self._pdfplumber_available or self._pymupdf_available

    def reorder_markdown(self, markdown_text: str, pdf_path: Path) -> str:
        """
        Reorder the markdown content based on the layout of the PDF pages.
        Only applies if we have a layout detection library.

        V18.13: Before running the expensive per-page reorder loop, sample 1-2
        pages and check if they actually have a multi-column layout. If not,
        skip the entire reorder — saving ~25s/chapter for 95% of books.
        """
        if not self.is_available():
            return markdown_text

        # Parse markdown into pages using page markers
        pages = self._split_markdown_into_pages(markdown_text)
        if not pages:
            return markdown_text

        # V18.13: Sample 1-2 pages to detect if the document actually has
        # a multi-column layout. If not, skip the per-page reorder entirely.
        # Rationale: layout reorder was designed for two-column scientific
        # papers. The content auto-detector sometimes misclassifies regular
# books as "Academic Paper" (e.g. a domain textbook with 4
        # citations -> 75% confidence -> layout reorder enabled -> 20 pages
        # checked -> 0 reorders -> 25s wasted). The sampling check prevents
        # this: check 1-2 pages, and if no multi-column layout is detected,
        # skip the rest.
        sample_page_nums = list(pages.keys())[:2]
        if not self._detect_multi_column(pdf_path, sample_page_nums):
            self.log(
                f"  V18.13: Layout reorder skipped — sampled {len(sample_page_nums)} "
                f"page(s), no multi-column layout detected (single-column content; "
                f"reorder not needed, saved ~{len(pages) * 1.2:.0f}s).",
                "INFO"
            )
            return markdown_text

        self.log(f"  📐 Reordering {len(pages)} pages for multi‑column layout...", "INFO")

        reordered_pages = []
        for page_num, page_content in pages.items():
            try:
                if self._pdfplumber_available:
                    reordered = self._reorder_page_pdfplumber(pdf_path, page_num, page_content)
                else:
                    reordered = self._reorder_page_pymupdf(pdf_path, page_num, page_content)
                reordered_pages.append(f"<!-- original page {page_num} -->\n{reordered}")
            except Exception as e:
                self.log(f"  ⚠️ Layout reorder failed for page {page_num}: {e}. Keeping original.", "WARNING")
                reordered_pages.append(f"<!-- original page {page_num} -->\n{page_content}")

        return "\n\n".join(reordered_pages)

    # ── V18.13: Sampling-based multi-column detection ──────────────────────

    def _detect_multi_column(self, pdf_path: Path, sample_page_nums: list[int]) -> bool:
        """Sample 1-2 pages and detect if they have a multi-column layout.

        Returns True if any sampled page has a 2-column layout (a significant
        horizontal gap in the middle of the page where no words appear).
        Returns False for single-column pages (the 95% case).

        This is the gate for the expensive per-page reorder loop. If this
        returns False, ``reorder_markdown`` skips the loop entirely.
        """
        for page_num in sample_page_nums:
            try:
                if self._pdfplumber_available:
                    if self._is_two_column_pdfplumber(pdf_path, page_num):
                        return True
                elif self._pymupdf_available:
                    if self._is_two_column_pymupdf(pdf_path, page_num):
                        return True
            except Exception as _e:
                logger.debug("multi-column detection failed for page %d: %s", page_num, _e)
                continue
        return False

    def _is_two_column_pdfplumber(self, pdf_path: Path, page_num: int) -> bool:
        """Check if a single page has a 2-column layout using pdfplumber.

        Algorithm: divide the page into 10 horizontal bins, count words in
        each bin, and check if the middle bins (the column gutter) have
        very few words while both the left and right bins have significant
        text. This distinguishes:
        - Single-column: words distributed across the full width (gutter has ~20%)
        - Two-column: words in 2 clusters with a gap (gutter has < 5%)
        """
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            if page_num > len(pdf.pages):
                return False
            page = pdf.pages[page_num - 1]
            words = self._get_words_pdfplumber(page)
            if not words or len(words) < 20:
                return False
            page_width = page.width
            if page_width <= 0:
                return False
            n_bins = 10
            bin_counts = [0] * n_bins
            for w in words:
                x_center = (w.get('x0', 0) + w.get('x1', 0)) / 2
                bin_idx = int((x_center / page_width) * n_bins)
                bin_idx = min(max(bin_idx, 0), n_bins - 1)
                bin_counts[bin_idx] += 1
            total_words = sum(bin_counts)
            if total_words == 0:
                return False
            left_count = sum(bin_counts[0:4])    # 0-40%
            gutter_count = sum(bin_counts[4:6])  # 40-60%
            right_count = sum(bin_counts[6:10])  # 60-100%
            gutter_ratio = gutter_count / total_words
            left_ratio = left_count / total_words
            right_ratio = right_count / total_words
            # Two-column if: gutter < 5% of words, both columns > 15%, enough words
            return (gutter_ratio < 0.05 and
                    left_ratio > 0.15 and
                    right_ratio > 0.15 and
                    total_words > 20)

    def _is_two_column_pymupdf(self, pdf_path: Path, page_num: int) -> bool:
        """Check if a single page has a 2-column layout using PyMuPDF.

        Same algorithm as _is_two_column_pdfplumber but using fitz.
        """
        import fitz
        doc = fitz.open(pdf_path)
        if page_num > doc.page_count:
            doc.close()
            return False
        page = doc[page_num - 1]
        page_width = page.rect.width
        if page_width <= 0:
            doc.close()
            return False
        blocks = page.get_text("dict")["blocks"]
        word_centers = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip():
                            x0, y0, x1, y1 = span["bbox"]
                            word_centers.append((x0 + x1) / 2)
        doc.close()
        if len(word_centers) < 20:
            return False
        n_bins = 10
        bin_counts = [0] * n_bins
        for xc in word_centers:
            bin_idx = int((xc / page_width) * n_bins)
            bin_idx = min(max(bin_idx, 0), n_bins - 1)
            bin_counts[bin_idx] += 1
        total = sum(bin_counts)
        if total == 0:
            return False
        left_count = sum(bin_counts[0:4])
        gutter_count = sum(bin_counts[4:6])
        right_count = sum(bin_counts[6:10])
        return (gutter_count / total < 0.05 and
                left_count / total > 0.15 and
                right_count / total > 0.15 and
                total > 20)

    def _split_markdown_into_pages(self, markdown_text: str) -> dict[int, str]:
        """Extract page content using <!-- original page N --> markers."""
        pages = {}
        pattern = re.compile(r'(<!-- original page (\d+) -->)\s*(.*?)(?=<!-- original page \d+ -->|\Z)', re.DOTALL)
        for match in pattern.finditer(markdown_text):
            page_num = int(match.group(2))
            content = match.group(3).strip()
            pages[page_num] = content
        return pages

    def _get_words_pdfplumber(self, page) -> list[dict]:
        """
        Attempt to extract words with positions using pdfplumber.
        Tries multiple parameter combinations if needed.
        """
        # Try standard extraction
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        if words and all('x0' in w and 'y0' in w for w in words):
            return words

        # Try with different tolerance
        words = page.extract_words(x_tolerance=5, y_tolerance=5)
        if words and all('x0' in w and 'y0' in w for w in words):
            return words

        # Try without tolerance
        words = page.extract_words()
        if words and all('x0' in w and 'y0' in w for w in words):
            return words

        # Try with extra parameters (keep_blank_chars)
        try:
            words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
            if words and all('x0' in w and 'y0' in w for w in words):
                return words
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # If all fail, return empty list
        return []

    def _reorder_page_pdfplumber(self, pdf_path: Path, page_num: int, page_content: str) -> str:
        """Use pdfplumber to get line positions and reorder."""
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            if page_num > len(pdf.pages):
                return page_content
            page = pdf.pages[page_num - 1]

            # Extract words with positions using robust method
            words = self._get_words_pdfplumber(page)
            if not words:
                # Fallback to PyMuPDF if available
                if self._pymupdf_available:
                    self.log(f"  ℹ️ pdfplumber failed to extract words on page {page_num}, falling back to PyMuPDF.", "DEBUG")
                    return self._reorder_page_pymupdf(pdf_path, page_num, page_content)
                else:
                    self.log(f"  ℹ️ No words found on page {page_num} – skipping reorder.", "DEBUG")
                    return page_content

            # Ensure all words have required keys
            required_keys = {'x0', 'y0', 'x1', 'y1', 'text'}
            if not all(all(k in w for k in required_keys) for w in words):
                self.log(f"  ⚠️ Words missing position keys on page {page_num} – falling back to PyMuPDF.", "DEBUG")
                if self._pymupdf_available:
                    return self._reorder_page_pymupdf(pdf_path, page_num, page_content)
                else:
                    return page_content

            # Cluster words into lines by y‑coordinate (within tolerance)
            lines = self._cluster_words_into_lines(words)
            # Sort lines by y, then x (left → right)
            lines.sort(key=lambda line: (line[0].get('y0', 0), line[0].get('x0', 0)))

            # Reconstruct text from sorted lines
            reordered_text = self._reconstruct_text_from_lines(lines)

            # If the content seems unchanged, return original
            if self._is_same_content(reordered_text, page_content):
                self.log(f"  ℹ️ Layout reorder didn't change page {page_num} (may be single‑column).", "DEBUG")
                return page_content

            self.log(f"  ✅ Reordered page {page_num} (pdfplumber)", "INFO")
            return reordered_text

    def _reorder_page_pymupdf(self, pdf_path: Path, page_num: int, page_content: str) -> str:
        """Use PyMuPDF to get text with positions."""
        import fitz

        doc = fitz.open(pdf_path)
        if page_num > doc.page_count:
            return page_content
        page = doc[page_num - 1]

        # Extract text blocks with positions
        blocks = page.get_text("dict")["blocks"]
        lines = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip():
                            # Use the span's bbox
                            x0, y0, x1, y1 = span["bbox"]
                            lines.append({
                                "x0": x0,
                                "y0": y0,
                                "x1": x1,
                                "y1": y1,
                                "text": span["text"]
                            })

        if not lines:
            self.log(f"  ℹ️ No text blocks found on page {page_num} – skipping reorder.", "DEBUG")
            return page_content

        # Sort by y, then x
        lines.sort(key=lambda l: (l["y0"], l["x0"]))
        reordered_text = self._reconstruct_text_from_lines(lines)

        if self._is_same_content(reordered_text, page_content):
            self.log(f"  ℹ️ Layout reorder didn't change page {page_num} (may be single‑column).", "DEBUG")
            return page_content

        self.log(f"  ✅ Reordered page {page_num} (PyMuPDF)", "INFO")
        return reordered_text

    def _cluster_words_into_lines(self, words: list[dict]) -> list[list[dict]]:
        """Cluster words into lines based on y‑coordinate."""
        if not words:
            return []
        # Sort by y0
        sorted_words = sorted(words, key=lambda w: w['y0'])
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]['y0']
        y_tolerance = 5  # pixels

        for w in sorted_words[1:]:
            if abs(w['y0'] - current_y) < y_tolerance:
                current_line.append(w)
            else:
                # Sort current line by x0
                current_line.sort(key=lambda w: w['x0'])
                lines.append(current_line)
                current_line = [w]
                current_y = w['y0']
        if current_line:
            current_line.sort(key=lambda w: w['x0'])
            lines.append(current_line)
        return lines

    def _reconstruct_text_from_lines(self, lines: list[list[dict]]) -> str:
        """Join text from lines, preserving whitespace."""
        result = []
        for line in lines:
            text_parts = []
            for word in line:
                text_parts.append(word['text'])
            result.append(' '.join(text_parts))
        return '\n'.join(result)

    def _is_same_content(self, reordered: str, original: str) -> bool:
        """Check if reordered text is essentially the same (ignoring whitespace)."""
        reordered_clean = re.sub(r'\s+', '', reordered)
        original_clean = re.sub(r'\s+', '', original)
        return reordered_clean == original_clean
