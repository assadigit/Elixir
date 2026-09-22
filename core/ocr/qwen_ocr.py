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

logger = get_main_logger()


# V0.4.9: custom exception for 400 Bad Request from Ollama vision endpoints.
# Carries the actual Ollama error body (e.g., "model does not support images")
# so the caller can show the specific reason to the user, not just "400".
class _Vision400Error(Exception):
    """Raised when Ollama returns 400 from a vision OCR endpoint.

    The ``detail`` attribute carries the Ollama error body so the
    caller can show the specific reason (e.g., "model does not support
    images" vs "model not found").
    """

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"400: {detail}")


class QwenOCREngine(OCREngine):
    def __init__(
        self,
        model_name: str = "qwen3-vl:8b",
        ollama_base_url: str = "http://localhost:11434",
        timeout: int = 180,
        retries: int = 2,
        image_max_size: int = 1200,
        poppler_path: str | None = None,  # NEW: required on Windows
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

        # V0.4.9: try both /api/generate AND /api/chat endpoints.
        # Some custom GGUF models (e.g., GLM-OCR-Q8_ggml-org) return 400
        # from /api/generate with an images payload but work with
        # /api/chat (which uses a messages array format). The fallback
        # is content-agnostic — it works for any model that supports
        # vision via either endpoint.
        generate_payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }
        chat_payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_image],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }

        for attempt in range(self.retries):
            try:
                logger.debug(f"Qwen VL attempt {attempt + 1}/{self.retries}…")

                # V0.4.9: try /api/generate first (the traditional endpoint).
                text = self._try_endpoint("/api/generate", generate_payload, "response")
                if text:
                    return text

                # V0.4.9: if /api/generate returned empty or errored, try
                # /api/chat (some models only work with the chat format).
                logger.debug("Qwen VL: /api/generate returned empty — trying /api/chat…")
                text = self._try_endpoint("/api/chat", chat_payload, "message.content")
                if text:
                    return text

                logger.warning(f"Empty Qwen response on attempt {attempt + 1} (both endpoints)")
            except _Vision400Error as e:
                # V0.4.9: both endpoints returned 400 — the model
                # genuinely doesn't support vision. Show the specific
                # Ollama error body so the user knows exactly why.
                logger.warning(
                    f"Qwen attempt {attempt + 1} error: 400 Bad Request\n"
                    f"  💡 The model '{self.model_name}' rejected image input from BOTH\n"
                    f"  /api/generate and /api/chat. Ollama's error was:\n"
                    f"    {e.detail}\n"
                    f"  This usually means one of:\n"
                    f"    • The model was imported as a text-only GGUF without its\n"
                    f"      vision projector (mmproj) file. Re-import with the mmproj:\n"
                    f"      ollama create {self.model_name} -f Modelfile\n"
                    f"      (where Modelfile includes a PROJECTOR line)\n"
                    f"    • The model genuinely doesn't support vision. Use a model\n"
                    f"      with a built-in vision projector (qwen2-vl, llava, minicpm-v,\n"
                    f"      OlmOCR, etc.) — run 'ollama pull qwen2-vl:7b' for example.\n"
                    f"    • In Elixir Settings → OCR, pick a vision-capable model."
                )
            except Exception as e:
                logger.warning(f"Qwen attempt {attempt + 1} error: {e}")

            if attempt < self.retries - 1:
                time.sleep(2 * (attempt + 1))
        return None

    def _try_endpoint(self, endpoint: str, payload: dict, response_key: str) -> str | None:
        """V0.4.9: try one Ollama endpoint and return the extracted text.

        Returns None on empty response. Raises _Vision400Error on 400
        (both endpoints' 400s are caught by the caller). Other HTTP
        errors propagate as generic exceptions.

        V0.4.19: routed through ``safe_ollama_request`` (was a raw
        ``get_shared_session().post`` — see the matching fix in
        core/ocr/service.py). A 400 is unwrapped from the HTTPError so
        the specific Ollama error body still reaches the user.
        """
        import requests as _requests

        from utils.network import safe_ollama_request

        url = f"{self.ollama_base_url}{endpoint}"
        try:
            resp = safe_ollama_request("POST", url, json=payload, timeout=self.timeout)
        except _requests.HTTPError as e:
            resp = e.response
            if resp is None or resp.status_code != 400:
                raise

        if resp.status_code == 400:
            # V0.4.9: capture the actual Ollama error body — it
            # contains the specific reason (e.g., "model does not
            # support images", "model not found", etc.)
            try:
                err_body = resp.json().get("error", resp.text[:200])
            except Exception:
                err_body = resp.text[:200]
            raise _Vision400Error(err_body)

        data = resp.json()
        # /api/generate → data["response"]
        # /api/chat → data["message"]["content"]
        if "." in response_key:
            # Navigate nested keys (e.g., "message.content")
            text = data
            for key in response_key.split("."):
                text = text.get(key, {}) if isinstance(text, dict) else ""
        else:
            text = data.get(response_key, "")
        return text.strip() if text else None

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
