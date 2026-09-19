"""
Math Extractor – uses Pix2Tex or LaTeX-OCR to detect math in images and convert to LaTeX.
Requires the image to be rendered; we'll use pdf2image to extract pages as images.
"""

import re
from collections.abc import Callable
from pathlib import Path

from utils.logging import get_main_logger

logger = get_main_logger()


class MathExtractor:
    def __init__(
        self,
        log_callback: Callable[[str, str], None] | None = None,
        model: str = "pix2tex",
        poppler_path: str | None = None,
    ):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.model = model
        self.poppler_path = poppler_path
        self._pix2tex = None
        self._latexocr = None

    def _init_pix2tex(self) -> bool:
        try:
            from pix2tex import Pix2Tex

            self._pix2tex = Pix2Tex()
            self.log("  ✅ Pix2Tex loaded for math extraction.", "INFO")
            return True
        except ImportError:
            self.log("  ⚠️ Pix2Tex not installed. Run: pip install pix2tex", "WARNING")
            return False

    def _init_latexocr(self) -> bool:
        try:
            from latexocr import LatexOCR

            self._latexocr = LatexOCR()
            self.log("  ✅ LaTeX-OCR loaded for math extraction.", "INFO")
            return True
        except ImportError:
            self.log("  ⚠️ LaTeX-OCR not installed. Run: pip install latexocr", "WARNING")
            return False

    def extract_math_from_pdf(self, pdf_path: Path, pages: list[int]) -> dict[int, list[str]]:
        """
        Extract math from specified pages by rendering them to images and detecting formulas.
        Returns dict: page_num -> list of LaTeX strings.
        """
        results = {}
        if self.model == "pix2tex":
            if not self._init_pix2tex():
                return results
        else:
            if not self._init_latexocr():
                return results

        # Render pages to images
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(
                str(pdf_path),
                first_page=pages[0],
                last_page=pages[-1],
                poppler_path=self.poppler_path or None,
            )
            # We need to map images back to page numbers
            for idx, img in enumerate(images):
                page_num = pages[idx]
                # For each image, we need to detect math regions. This is complex.
                # For simplicity, we'll pass the whole image to the model.
                if self.model == "pix2tex":
                    latex = self._pix2tex(img)
                else:
                    latex = self._latexocr(img)
                if latex and latex.strip():
                    results.setdefault(page_num, []).append(latex)
                    self.log(f"  📐 Extracted math from page {page_num}", "DEBUG")
        except Exception as e:
            self.log(f"  ❌ Math extraction failed: {e}", "WARNING")
        return results

    def insert_math_into_markdown(self, markdown: str, math_by_page: dict[int, list[str]]) -> str:
        """
        Insert LaTeX blocks into the markdown.
        We'll insert them after the page marker for simplicity.
        """
        if not math_by_page:
            return markdown
        # We'll insert LaTeX blocks as fenced code with language "latex".
        # For each page, we'll find the page marker and insert after.
        lines = markdown.splitlines()
        new_lines = []
        for line in lines:
            new_lines.append(line)
            # Check for page marker
            m = re.search(r"<!-- original page (\d+) -->", line)
            if m:
                page_num = int(m.group(1))
                if page_num in math_by_page:
                    for latex in math_by_page[page_num]:
                        new_lines.append("```latex")
                        new_lines.append(latex)
                        new_lines.append("```")
                        new_lines.append("")
        return "\n".join(new_lines)
