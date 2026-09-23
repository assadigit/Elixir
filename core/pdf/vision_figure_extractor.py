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

# V0.13 (Phase 0): PyMuPDF is an OPTIONAL dependency (undeclared before — its
# module-level import made the whole core.pdf → controller chain crash with
# ImportError on fresh installs). Guarded here; call sites degrade gracefully
# (figure extraction is an opt-in feature — see "extract_figure_text").
try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover — optional dependency
    fitz = None  # type: ignore[assignment]

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

        # V0.4.24: the llama-server vision route (None = Ollama transport).
        # Initialized here AND defaulted via getattr at the use sites so
        # object.__new__-style construction (tests) never breaks.
        self._llamacpp_provider = None
        self._llamacpp_provider_model = ""

    # ─────────────────────────────────────────────────────────────────────────
    # Main extraction
    # ─────────────────────────────────────────────────────────────────────────

    def extract(self, pages: list[int] | None = None) -> dict[int, list[str]]:
        """
        Extract text from figures on specified pages (or all pages if None).
        Returns dict: page_num -> list of extracted text strings.
        """
        self._page_figure_text.clear()

        if fitz is None:
            self.log(
                "  ⚠️ PyMuPDF (fitz) not installed — figure extraction skipped. "
                "Install with: pip install pymupdf",
                "WARNING",
            )
            return {}

        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            self.log(f"  ❌ Failed to open PDF for figure extraction: {e}", "ERROR")
            return {}

        total_pages = len(doc)
        target_pages = pages if pages else list(range(1, total_pages + 1))

        # Check if the vision model is available
        model_available = self.model_manager.model_exists(self.model_name)
        # V0.4.24 (V4.23 run post-mortem): the llama-server vision path.
        # When the Ollama model is absent AND the active provider is
        # llama.cpp, route figure extraction through the llama.cpp
        # provider's vision call instead of skipping the feature — the
        # V4.23 rig log showed "❌ No vision model available. Skipping
        # figure extraction." while llama-server was serving a
        # vision-capable model.
        self._llamacpp_provider = None
        self._llamacpp_provider_model = ""
        if not model_available:
            self.log(f"  ⚠️ Vision model '{self.model_name}' not found. Trying fallback.", "WARNING")
            if self.model_manager.model_exists(self.fallback_model):
                self.model_name = self.fallback_model
                model_available = True
            else:
                self._llamacpp_provider = self._create_llamacpp_vision_provider()
                if self._llamacpp_provider is None:
                    self.log("  ❌ No vision model available. Skipping figure extraction.", "ERROR")
                    doc.close()
                    return {}

        # Acquire the model (keep loaded for all pages) — Ollama path only;
        # the llama.cpp server is already serving its model.
        if self._llamacpp_provider is None and not self.model_manager.acquire_model(
            self.model_name, ModelType.OCR
        ):
            self.log(
                f"  ❌ Failed to load vision model '{self.model_name}'. Skipping figure extraction.",
                "ERROR",
            )
            doc.close()
            return {}

        self.log(
            "  🖼️ Extracting text from figures using "
            + (
                f"llama-server vision model ({self._llamacpp_provider_model})…"
                if self._llamacpp_provider is not None
                else f"{self.model_name}..."
            ),
            "INFO",
        )

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
                        self.log(
                            f"      ⚠️ Failed to process image {img_idx} on page {page_num}: {e}",
                            "WARNING",
                        )

                if extracted_texts:
                    self._page_figure_text[page_num] = extracted_texts
                    self.log(
                        f"    ✅ Page {page_num}: extracted text from {len(extracted_texts)} images",
                        "INFO",
                    )

        except Exception as e:
            self.log(f"  ❌ Figure extraction error: {e}", "ERROR")

        finally:
            # Release the model (Ollama path only — llama-server manages its
            # own model lifetime)
            if getattr(self, "_llamacpp_provider", None) is None:
                self.model_manager.release_model(self.model_name)
            doc.close()

        return self._page_figure_text

    # ─────────────────────────────────────────────────────────────────────────
    # V0.4.24: the llama-server vision path (provider-aware fallback)
    # ─────────────────────────────────────────────────────────────────────

    def _create_llamacpp_vision_provider(self):
        """V0.4.24: a vision-capable llama.cpp provider, or None.

        Only when the ACTIVE provider setting is ``llamacpp`` — probed
        live via ``supports_vision()`` (never a name-keyed guess; AGENTS.md
        Rule 1). The model name reported by llama-server is captured for
        the ``complete_with_image`` calls.
        """
        try:
            _prov = (
                (self.settings.get("summarisation.provider", "ollama") or "ollama").strip().lower()
            )
            if _prov != "llamacpp":
                return None
            from core.llm.llm_provider_impl import create_provider

            provider = create_provider("llamacpp", self.settings)
            if provider is not None and provider.supports_vision():
                self._llamacpp_provider_model = (
                    self.settings.get("summarisation.llamacpp_model", "") or self.model_name
                )
                return provider
            self.log(
                "  ℹ️ llama-server model is not vision-capable — figure "
                "extraction via llama.cpp unavailable.",
                "DEBUG",
            )
            return None
        except Exception as e:
            self.log(f"  ⚠️ V0.4.24: llama.cpp vision provider probe failed: {e}", "WARNING")
            return None

    def _extract_text_from_image(
        self, image_bytes: bytes, page_num: int, img_idx: int
    ) -> str | None:
        """
        Send a single image to the vision model and return extracted text.
        """
        prompt = (
            "Extract ALL text, labels, numbers, axis titles, and legends from this image. "
            "Do NOT describe the image itself. Do NOT describe colors, shapes, or styling. "
            "Only output the textual content found in the image. "
            "If there are multiple distinct text elements, list them one per line."
            "Output ONLY the extracted text, no commentary, no preamble."
        )

        # V0.4.24: the llama-server vision route (OpenAI-compatible image
        # call) — same prompt, same retries, different transport.
        if getattr(self, "_llamacpp_provider", None) is not None:
            for attempt in range(self.retries):
                try:
                    self.log(f"      🧠 Vision OCR attempt {attempt + 1}/{self.retries}…", "DEBUG")
                    text = self._llamacpp_provider.complete_with_image(
                        prompt,
                        image_bytes,
                        temperature=0.0,
                        max_tokens=1024,
                        model=self._llamacpp_provider_model,
                    )
                    if text and text.strip():
                        return text.strip()
                    self.log(f"      ⚠️ Empty response attempt {attempt + 1}", "WARNING")
                except Exception as e:
                    self.log(f"      ⚠️ Vision error attempt {attempt + 1}: {e}", "WARNING")
                if attempt < self.retries - 1:
                    time.sleep(2 * (attempt + 1))
            return None

        b64 = base64.b64encode(image_bytes).decode("utf-8")
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

        for line in lines:
            new_lines.append(line)

            # Check for page marker
            import re

            m = re.search(r"<!-- original page (\d+) -->", line)
            if m:
                page_num = int(m.group(1))
                if page_num in self._page_figure_text:
                    for fig_text in self._page_figure_text[page_num]:
                        # Clean and format the extracted text
                        clean_text = fig_text[:500]  # Truncate if too long
                        # Remove excessive newlines
                        clean_text = re.sub(r"\n{3,}", "\n", clean_text)
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
        if fitz is None:
            return False
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
        if fitz is None:
            self.log(
                "  ⚠️ PyMuPDF (fitz) not installed — figure scan skipped.",
                "WARNING",
            )
            return pages_with_figures
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
