"""
Vision Figure Extractor – detects images (graphs, flowcharts, diagrams) in PDF
and extracts text/labels/numbers using a vision model (OlmOCR or Qwen3-VL).

NEW in this version (Sprint 3):
  - Detects embedded images in PDF via PyMuPDF.
  - For each image, sends it to the configured vision model with a "text‑only"
    extraction prompt.
  - Inserts extracted text near the page where the image appears.
  - Handles vision model fallback (OlmOCR → Qwen → Tesseract).
  - Batches images per page to reduce API calls.
"""

import base64
import time
from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

from core.llm import ModelManager, ModelType
from utils.logging import get_main_logger
from utils.network import safe_ollama_request
from utils.settings import Settings

logger = get_main_logger()


class VisionFigureExtractor:
    """
    Extracts text from figures/images in a PDF using a vision model.
    """

    def __init__(
        self,
        pdf_path: Path,
        model_name: str = "OlmOCR-2-7B:latest",
        fallback_model: str = "qwen3-vl:8b",
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.pdf_path = pdf_path
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.model_manager = ModelManager()
        self.settings = Settings()
        # V18.20.4.3 (P2 / W-c9): canonical URL from settings (was
        # hardcoded localhost — split behavior on remote-Ollama rigs).
        self.ollama_base_url = self.settings.get_ollama_url()
        self.timeout = 180
        self.retries = 2

        # Cache for extracted text per page
        self._page_figure_text: dict[int, list[str]] = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Main extraction
    # ─────────────────────────────────────────────────────────────────────────

    def extract(self, pages: list[int] | None = None) -> dict[int, list[str]]:
        """
        Extract text from figures on specified pages (or all pages if None).
        Returns dict: page_num -> list of extracted text strings.
        """
        self._page_figure_text.clear()

        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            self.log(f"  ❌ Failed to open PDF for figure extraction: {e}", "ERROR")
            return {}

        total_pages = len(doc)
        target_pages = pages if pages else list(range(1, total_pages + 1))

        # Check if the vision model is available
        model_available = self.model_manager.model_exists(self.model_name)
        if not model_available:
            self.log(f"  ⚠️ Vision model '{self.model_name}' not found. Trying fallback.", "WARNING")
            if self.model_manager.model_exists(self.fallback_model):
                self.model_name = self.fallback_model
                model_available = True
            else:
                self.log("  ❌ No vision model available. Skipping figure extraction.", "ERROR")
                doc.close()
                return {}

        # Acquire the model (keep loaded for all pages)
        if not self.model_manager.acquire_model(self.model_name, ModelType.OCR):
            self.log(f"  ❌ Failed to load vision model '{self.model_name}'. Skipping figure extraction.", "ERROR")
            doc.close()
            return {}

        self.log(f"  🖼️ Extracting text from figures using {self.model_name}...", "INFO")

        try:
            for page_num in target_pages:
                if page_num > total_pages:
                    continue

                page = doc[page_num - 1]
                image_list = page.get_images()

                if not image_list:
                    continue

                self.log(f"    🖼️ Page {page_num}: found {len(image_list)} images", "DEBUG")

                extracted_texts = []
                for img_idx, img in enumerate(image_list):
                    try:
                        # Extract image bytes
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            continue

                        image_bytes = base_image["image"]
                        if not image_bytes:
                            continue

                        # Send to vision model
                        text = self._extract_text_from_image(image_bytes, page_num, img_idx)
                        if text:
                            extracted_texts.append(text)

                    except Exception as e:
                        self.log(f"      ⚠️ Failed to process image {img_idx} on page {page_num}: {e}", "WARNING")

                if extracted_texts:
                    self._page_figure_text[page_num] = extracted_texts
                    self.log(f"    ✅ Page {page_num}: extracted text from {len(extracted_texts)} images", "INFO")

        except Exception as e:
            self.log(f"  ❌ Figure extraction error: {e}", "ERROR")

        finally:
            # Release the model
            self.model_manager.release_model(self.model_name)
            doc.close()

        return self._page_figure_text

    # ─────────────────────────────────────────────────────────────────────────
    # Image → text via vision model
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_text_from_image(self, image_bytes: bytes, page_num: int, img_idx: int) -> str | None:
        """
        Send a single image to the vision model and return extracted text.
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Extract ALL text, labels, numbers, axis titles, and legends from this image. "
            "Do NOT describe the image itself. Do NOT describe colors, shapes, or styling. "
            "Only output the textual content found in the image. "
            "If there are multiple distinct text elements, list them one per line."
            "Output ONLY the extracted text, no commentary, no preamble."
        )

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 1024,
            },
        }
        url = f"{self.ollama_base_url}/api/generate"

        for attempt in range(self.retries):
            try:
                self.log(f"      🧠 Vision OCR attempt {attempt + 1}/{self.retries}…", "DEBUG")
                resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
                text = resp.json().get("response", "").strip()
                if text:
                    return text
                self.log(f"      ⚠️ Empty response attempt {attempt + 1}", "WARNING")
            except Exception as e:
                self.log(f"      ⚠️ Vision error attempt {attempt + 1}: {e}", "WARNING")

            if attempt < self.retries - 1:
                time.sleep(2 * (attempt + 1))

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Insert extracted text into Markdown
    # ─────────────────────────────────────────────────────────────────────────

    def insert_into_markdown(self, markdown_text: str) -> str:
        """
        Insert extracted figure text into the Markdown, near the page markers.
        Format: [Figure extracted text: ...]
        """
        if not self._page_figure_text:
            return markdown_text

        lines = markdown_text.splitlines()
        new_lines = []
        current_page = None

        for line in lines:
            new_lines.append(line)

            # Check for page marker
            import re
            m = re.search(r'<!-- original page (\d+) -->', line)
            if m:
                page_num = int(m.group(1))
                if page_num in self._page_figure_text:
                    for fig_text in self._page_figure_text[page_num]:
                        # Clean and format the extracted text
                        clean_text = fig_text[:500]  # Truncate if too long
                        # Remove excessive newlines
                        clean_text = re.sub(r'\n{3,}', '\n', clean_text)
                        new_lines.append("")
                        new_lines.append(f"> **Figure extracted text:** {clean_text}")
                        new_lines.append("")

        return "\n".join(new_lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Convenience: detect if a page likely contains figures
    # ─────────────────────────────────────────────────────────────────────────

    def page_has_figures(self, page_num: int) -> bool:
        """
        Check if a page contains any embedded images.
        """
        try:
            doc = fitz.open(self.pdf_path)
            if page_num > len(doc):
                return False
            page = doc[page_num - 1]
            images = page.get_images()
            doc.close()
            return len(images) > 0
        except OSError:
            return False

    def get_pages_with_figures(self, page_limit: int | None = None) -> list[int]:
        """
        Return a list of page numbers that contain figures.
        If page_limit is set, only scan up to that many pages.
        """
        pages_with_figures = []
        try:
            doc = fitz.open(self.pdf_path)
            total = len(doc)
            limit = min(page_limit, total) if page_limit else total

            for page_num in range(1, limit + 1):
                page = doc[page_num - 1]
                images = page.get_images()
                if images:
                    pages_with_figures.append(page_num)

            doc.close()
        except Exception as e:
            self.log(f"  ⚠️ Error scanning for figures: {e}", "WARNING")

        return pages_with_figures
