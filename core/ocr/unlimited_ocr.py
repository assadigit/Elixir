"""
UnlimitedOCREngine — wraps baidu/Unlimited-OCR (and compatible DeepSeek-OCR-2).

Key advantage over Qwen3-VL:
  - infer_multi() processes ALL scanned pages in ONE call (32K context).
  - For 31 scanned pages: 31 × 30s (Qwen) → ~2-4 min total (batch).
  - Designed specifically for document/book OCR, not general vision.

Requirements (install before use):
  pip install torch transformers pymupdf einops addict easydict matplotlib

Model paths (set in settings.json or Advanced tab):
  ocr.unlimited_ocr_path = "C:/path/to/unlimited-ocr-model-folder/"
                           (must contain config.json and model.safetensors)
  or "baidu/Unlimited-OCR"  (auto-download from Hugging Face)

If you encounter JSON parsing errors, config.json is likely corrupted.
Re-download the model or disable UnlimitedOCR by leaving the path empty.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from core.models import OcrEngine, OcrResult
from core.ocr.base import OCREngine
from utils.logging import get_main_logger

logger = get_main_logger()


class UnlimitedOCREngine(OCREngine):
    """
    Batch OCR engine using baidu/Unlimited-OCR or DeepSeek-OCR-2.

    Call process_batch() to OCR many pages at once (preferred).
    Falls back to single-page process_page() if batch is not used.
    """

    def __init__(
        self,
        model_path: str = "baidu/Unlimited-OCR",
        image_size: int = 1024,
        max_length: int = 32768,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.model_path = model_path
        self.image_size = image_size
        self.max_length = max_length
        self.log = log_callback or (lambda msg, lvl="INFO": None)
        self._model = None
        self._tokenizer = None

    def engine_name(self) -> str:
        name = Path(self.model_path).name if os.path.exists(self.model_path) else self.model_path
        return f"UnlimitedOCR ({name})"

    # ─────────────────────────────────────────────────────────────────────────
    # Model lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load model weights into VRAM.  Returns True on success."""
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            self.log(
                f"  ❌ UnlimitedOCR requires: pip install torch transformers "
                f"pymupdf einops addict easydict matplotlib\n  Missing: {e}",
                "ERROR",
            )
            return False

        # ─── Intelligent path resolution ─────────────────────────────────────
        load_path = self.model_path
        if load_path.endswith(".safetensors") and os.path.isfile(load_path):
            parent = str(Path(load_path).parent)
            if (Path(parent) / "config.json").exists():
                load_path = parent
                self.log(f"  🔍 Found config.json in parent, using: {load_path}", "INFO")
            else:
                grandparent = str(Path(parent).parent)
                if (Path(grandparent) / "config.json").exists():
                    load_path = grandparent
                    self.log(f"  🔍 Found config.json in grandparent, using: {load_path}", "INFO")
                else:
                    self.log(
                        "  ❌ No config.json found near the .safetensors file.\n"
                        "  Please set the path to the model FOLDER containing config.json.\n"
                        "  Alternatively, disable UnlimitedOCR by setting the path to empty.",
                        "ERROR",
                    )
                    return False

        try:
            self.log(f"  ⏳ Loading UnlimitedOCR from: {load_path}", "INFO")
            dtype = getattr(torch, "bfloat16", torch.float16)

            # ── Try loading, catching common errors ─────────────────────────
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(load_path, trust_remote_code=True)
                self._model = AutoModel.from_pretrained(
                    load_path,
                    trust_remote_code=True,
                    torch_dtype=dtype,
                )
            except json.JSONDecodeError as e:
                self.log(
                    f"  ❌ Failed to parse config.json: {e}\n"
                    "  The model's config.json file is corrupted or incomplete.\n"
                    "  Please re-download the model files or disable UnlimitedOCR.",
                    "ERROR",
                )
                self._model = None
                return False
            except ImportError as e:
                if "is_torch_fx_available" in str(e):
                    self.log(
                        "  ❌ Transformers version incompatibility.\n"
                        "  This model requires an older transformers version.\n"
                        "  Please downgrade to transformers==4.36.0:\n"
                        "    pip install transformers==4.36.0\n"
                        "  OR disable UnlimitedOCR by setting its path to empty.",
                        "ERROR",
                    )
                else:
                    self.log(f"  ❌ Import error: {e}", "ERROR")
                self._model = None
                return False
            except Exception as e:
                self.log(f"  ❌ Unexpected error: {e}", "ERROR")
                self._model = None
                return False

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = self._model.to(device).eval()
            self.log(
                f"  ✅ UnlimitedOCR loaded on {device} (dtype={str(dtype).split('.')[-1]})",
                "INFO",
            )
            return True

        except Exception as e:
            self.log(f"  ❌ UnlimitedOCR load failed: {e}", "ERROR")
            self._model = None
            return False

    def unload(self) -> None:
        """Release model from VRAM."""
        try:
            import torch

            if self._model is not None:
                del self._model
                self._model = None
            if self._tokenizer is not None:
                del self._tokenizer
                self._tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.log("  🔓 UnlimitedOCR unloaded from VRAM.", "INFO")
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # ─────────────────────────────────────────────────────────────────────────
    # Batch processing (main interface)
    # ─────────────────────────────────────────────────────────────────────────

    def process_batch(
        self,
        pages: list,  # list of pypdf PageObject
        page_numbers: list[int],
        image_max_size: int | None = None,
        poppler_path: str = "",
    ) -> dict[int, OcrResult]:
        """
        Process ALL scanned pages in a single model call.
        Returns dict mapping page_number → OcrResult.

        V0.6.0 (4-c): ``image_max_size`` was a dead parameter — the service
        passes ``request.image_max_size`` here (core/ocr/service.py:310)
        but the call below always used the constructor's ``image_size``.
        Honor the caller's value; fall back to the constructor value when
        the caller passes nothing.
        """
        if not page_numbers:
            return {}
        _img_size = image_max_size if image_max_size else self.image_size

        if self._model is None:
            if not self.load():
                return {
                    p: OcrResult(
                        page_num=p,
                        text="",
                        success=False,
                        engine_used=OcrEngine.NONE,
                        error_msg="UnlimitedOCR not loaded",
                    )
                    for p in page_numbers
                }

        # Render all scanned pages to JPEG images in a temp directory
        tmp_dir = Path(tempfile.mkdtemp(prefix="unlimited_ocr_"))
        image_paths: list[str] = []
        # V0.6.0 (4-c): keyed by image PATH, not by zip index — when an
        # earlier page fails rasterization, the image_paths enumeration
        # shifted relative to the zip enumeration and every later result
        # was keyed by the WRONG page number (or -1, a bogus key the
        # service loop then ignored).
        page_map: dict[str, int] = {}  # image_path → page_number

        try:
            from pdf2image import convert_from_bytes
            from pypdf import PdfWriter

            for page, page_num in zip(pages, page_numbers, strict=False):
                writer = PdfWriter()
                writer.add_page(page)
                buf = io.BytesIO()
                writer.write(buf)
                buf.seek(0)
                kwargs: dict = {
                    "first_page": 1,
                    "last_page": 1,
                    "dpi": 200,
                    "fmt": "jpeg",
                }
                if poppler_path:
                    kwargs["poppler_path"] = poppler_path
                imgs = convert_from_bytes(buf.getvalue(), **kwargs)
                if imgs:
                    img_path = str(tmp_dir / f"page_{page_num:04d}.jpg")
                    imgs[0].save(img_path, format="JPEG", quality=90)
                    image_paths.append(img_path)
                    page_map[img_path] = page_num

        except Exception as e:
            self.log(f"  ❌ UnlimitedOCR image prep failed: {e}", "ERROR")
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {
                p: OcrResult(
                    page_num=p, text="", success=False, engine_used=OcrEngine.NONE, error_msg=str(e)
                )
                for p in page_numbers
            }

        if not image_paths:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {}

        # Run infer_multi() — outputs files into tmp_dir/output/
        output_dir = tmp_dir / "output"
        output_dir.mkdir(exist_ok=True)
        results: dict[int, OcrResult] = {}

        try:
            self.log(
                f"  🏃 UnlimitedOCR: processing {len(image_paths)} pages in one batch…",
                "INFO",
            )
            self._model.infer_multi(
                self._tokenizer,
                prompt="<image>document parsing.",
                image_files=image_paths,
                output_path=str(output_dir),
                image_size=_img_size,
                max_length=self.max_length,
            )

            # Read output files — UnlimitedOCR writes per-image .md or .json files
            for img_path in image_paths:
                page_num = page_map.get(img_path, -1)
                stem = Path(img_path).stem

                # Try .md output first, then .json, then .txt
                text = ""
                for ext in (".md", ".json", ".txt"):
                    out_file = output_dir / (stem + ext)
                    if out_file.exists():
                        raw = out_file.read_text(encoding="utf-8", errors="replace")
                        if ext == ".json":
                            try:
                                data = json.loads(raw)
                                text = data.get("text", data.get("content", str(data)))
                            except json.JSONDecodeError:
                                text = raw
                        else:
                            text = raw
                        break

                if text.strip():
                    self.log(f"    ✅ UnlimitedOCR p.{page_num}: {len(text)} chars", "INFO")
                    results[page_num] = OcrResult(
                        page_num=page_num,
                        text=text.strip(),
                        success=True,
                        engine_used=OcrEngine.QWEN_VL,  # reuse enum for now
                    )
                else:
                    self.log(f"    ⚠️ UnlimitedOCR p.{page_num}: empty output", "WARNING")
                    results[page_num] = OcrResult(
                        page_num=page_num,
                        text="",
                        success=False,
                        engine_used=OcrEngine.QWEN_VL,
                        error_msg="UnlimitedOCR returned empty output",
                    )

        except Exception as e:
            self.log(f"  ❌ UnlimitedOCR inference failed: {e}", "ERROR")
            for page_num in page_numbers:
                if page_num not in results:
                    results[page_num] = OcrResult(
                        page_num=page_num,
                        text="",
                        success=False,
                        engine_used=OcrEngine.NONE,
                        error_msg=str(e),
                    )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Single-page interface (OCREngine ABC)
    # ─────────────────────────────────────────────────────────────────────────

    def process_page(self, page, page_num: int) -> OcrResult:
        """Single-page fallback.  Use process_batch() for efficiency."""
        batch = self.process_batch([page], [page_num])
        return batch.get(
            page_num,
            OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="Batch returned no result",
            ),
        )
