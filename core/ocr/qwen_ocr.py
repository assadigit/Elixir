"""
Qwen3-VL OCR engine using Ollama vision API — proxy-proof.

KEY FIXES vs original:
  - json_data=payload → json=payload
    (requests library uses 'json=', not 'json_data='; the old code was sending
    an empty body to Ollama on every call, so OCR always returned empty strings)
  - poppler_path now wired from settings (required on Windows)
  - Constructor signature kept clean — caller must pass model_name as a string,
    not a ConversionRequest object (the bug was in the old service.py, not here)

NOTE: This module is now supplementary. The new core/ocr/service.py handles
Qwen OCR inline (no longer imports QwenOCREngine). This file is kept for
reference and future use if you want to use QwenOCREngine directly.
"""

import base64
import io
import time

from pdf2image import convert_from_bytes
from pypdf import PdfWriter

from core.models import OcrEngine, OcrResult
from core.ocr.base import OCREngine
from utils.logging import get_main_logger
from utils.network import safe_ollama_request

logger = get_main_logger()


class QwenOCREngine(OCREngine):
    def __init__(
        self,
        model_name: str = "qwen3-vl:8b",
        ollama_base_url: str = "http://localhost:11434",
        timeout: int = 180,
        retries: int = 2,
        image_max_size: int = 1200,
        poppler_path: str | None = None,   # NEW: required on Windows
    ):
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url
        self.timeout = timeout
        self.retries = retries
        self.image_max_size = image_max_size
        self.poppler_path = poppler_path or None

    def engine_name(self) -> str:
        return f"Qwen3-VL ({self.model_name})"

    def _page_to_image_bytes(self, page) -> bytes | None:
        try:
            writer = PdfWriter()
            writer.add_page(page)
            buffer = io.BytesIO()
            writer.write(buffer)
            buffer.seek(0)

            convert_kwargs = {
                "fmt": "png",
                "first_page": 1,
                "last_page": 1,
                "size": self.image_max_size,
            }
            # FIX: pass poppler_path when set (required on Windows)
            if self.poppler_path:
                convert_kwargs["poppler_path"] = self.poppler_path

            images = convert_from_bytes(buffer.getvalue(), **convert_kwargs)
            if images:
                img_buffer = io.BytesIO()
                images[0].save(img_buffer, format="PNG")
                img_buffer.seek(0)
                return img_buffer.getvalue()
        except ImportError:
            logger.error("pdf2image is not installed. Run: pip install pdf2image")
        except Exception as e:
            logger.warning(f"Page-to-image conversion failed: {e}")
        return None

    def _call_ollama_vision(self, image_bytes: bytes) -> str | None:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Extract all text from this image. Preserve the original layout, "
            "paragraph breaks, and heading hierarchy. Return ONLY the text content, "
            "no commentary, no markdown formatting, no extra spaces."
        )
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }
        url = f"{self.ollama_base_url}/api/generate"

        for attempt in range(self.retries):
            try:
                logger.debug(f"Qwen VL attempt {attempt + 1}/{self.retries}…")
                # FIX: json=payload (was json_data=payload — wrong kwarg, sent empty body)
                resp = safe_ollama_request(
                    "POST", url, json=payload, timeout=self.timeout
                )
                text = resp.json().get("response", "").strip()
                if text:
                    return text
                logger.warning(f"Empty Qwen response on attempt {attempt + 1}")
            except Exception as e:
                logger.warning(f"Qwen attempt {attempt + 1} error: {e}")

            if attempt < self.retries - 1:
                time.sleep(2 * (attempt + 1))
        return None

    def process_page(self, page, page_num: int) -> OcrResult:
        logger.info(f"Page {page_num}: Qwen VL OCR…")
        image_bytes = self._page_to_image_bytes(page)
        if not image_bytes:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="Failed to render page as image",
            )
        text = self._call_ollama_vision(image_bytes)
        if text:
            logger.info(f"Page {page_num}: Qwen OCR — {len(text)} chars")
            return OcrResult(
                page_num=page_num,
                text=text,
                success=True,
                engine_used=OcrEngine.QWEN_VL,
            )
        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.QWEN_VL,
            error_msg="Qwen VL returned no text after all retries",
        )
