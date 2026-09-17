"""
Tesseract OCR fallback engine.

KEY FIXES vs original:
  - pytesseract.tesseract_cmd is now set from a constructor argument
    (on Windows, Tesseract is never in PATH; without this line it always fails)
  - poppler_path is now passed to convert_from_bytes (required on Windows)
  - Constructor keeps clean scalar arguments — the old service.py was passing
    a ConversionRequest object instead of (image_max_size, lang), which silently
    assigned the request object to image_max_size (int expected), crashing on use

NOTE: This module is now supplementary. The new core/ocr/service.py handles
Tesseract inline. This file is kept for reference and standalone use.
"""

import io

import pytesseract
from pdf2image import convert_from_bytes
from pypdf import PdfWriter

from core.models import OcrEngine, OcrResult
from core.ocr.base import OCREngine
from utils.logging import get_main_logger

logger = get_main_logger()


class TesseractOCREngine(OCREngine):
    def __init__(
        self,
        image_max_size: int = 1200,
        lang: str = "eng+fas",
        poppler_path: str | None = None,   # NEW: required on Windows
        tesseract_cmd: str | None = None,   # NEW: required on Windows
    ):
        self.image_max_size = image_max_size
        self.lang = lang
        self.poppler_path = poppler_path or None
        # FIX: set tesseract binary path — it's not in PATH on Windows by default
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            logger.debug(f"Tesseract path set to: {tesseract_cmd}")

    def engine_name(self) -> str:
        return f"Tesseract (lang={self.lang})"

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
            # FIX: pass poppler_path when set
            if self.poppler_path:
                convert_kwargs["poppler_path"] = self.poppler_path

            images = convert_from_bytes(buffer.getvalue(), **convert_kwargs)
            if images:
                img_buffer = io.BytesIO()
                images[0].save(img_buffer, format="PNG")
                img_buffer.seek(0)
                return img_buffer.getvalue()
        except Exception as e:
            logger.warning(f"Tesseract page-to-image failed: {e}")
        return None

    def process_page(self, page, page_num: int) -> OcrResult:
        logger.info(f"Page {page_num}: Tesseract OCR [{self.lang}]…")
        image_bytes = self._page_to_image_bytes(page)
        if not image_bytes:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg="Could not convert page to image",
            )
        try:
            from PIL import Image
            pil_image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(pil_image, lang=self.lang)
            if text.strip():
                logger.info(f"Page {page_num}: Tesseract — {len(text)} chars")
                return OcrResult(
                    page_num=page_num,
                    text=text,
                    success=True,
                    engine_used=OcrEngine.TESSERACT,
                )
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg="Tesseract returned empty string",
            )
        except pytesseract.TesseractNotFoundError:
            msg = (
                "Tesseract binary not found. Set paths.tesseract in settings.json "
                "or install Tesseract to C:\\Program Files\\Tesseract-OCR\\"
            )
            logger.error(msg)
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg=msg,
            )
        except Exception as e:
            logger.error(f"Tesseract error on page {page_num}: {e}")
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg=str(e),
            )
