"""
OCR Service.

FIXES in this version:
  - Poppler auto-detection: scans common Windows installation paths for
    pdftoppm.exe. If found, uses it automatically without needing the user
    to set paths.poppler in settings.json.
  - Pre-flight poppler check before spending 7 minutes loading qwen3-vl:8b.
    If poppler is not available, image conversion will fail regardless of
    which OCR model is loaded, so we skip the model load and log clear
    instructions instead.
  - PaddleOCR integration as an additional fallback after Qwen.
    Set ocr.use_paddleocr = true in settings.json to enable.
  - PaddleOCR init: removed unsupported 'show_log' argument; now uses
    a simple try/except with minimal arguments.
    Updated to support PaddleOCR v3.x (use_textline_orientation instead of use_angle_cls)
    and removed show_log parameter.
  - NEW: Force CPU mode for PaddleOCR (use_gpu=False) to avoid cuDNN dependency.
  - OCR timeout: now forced to at least 120 seconds, with debug logging.
  - NEW: Tiered OCR strategy:
    1. markitdown (fast, digital pages)
    2. OlmoOCR (vision model for image-heavy pages)
    3. Qwen (fallback vision, if Olmo not available)
    4. Tesseract (lightweight fallback)
    5. pypdf extract_text() (last resort)
  - NEW: _olmo_ocr_single() method to handle OlmOCR-2-7B specifically.
  - NEW: Proactive offload of summarisation model before loading OCR model,
    to ensure VRAM is available even if torch VRAM detection fails.
  - NEW: acquire_model() called with skip_vram_check=True for OCR, to bypass
    the broken VRAM detection and load regardless.
  - NEW: status_callback support for UI progress during VRAM offloading and model loading.
"""

import base64
import contextlib
import glob
import io
import os
import platform
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from core.llm import ModelManager, ModelType
from core.models import ConversionRequest, OcrEngine, OcrResult, PdfAnalysisResult
from core.system.timeouts import SHORT_LLM_TIMEOUT_S
from utils.logging import get_main_logger
from utils.network import safe_ollama_request
from utils.settings import Settings
from utils.text_utils import insert_page_number_comments


# ── PaddleOCR CPU-only context manager ─────────────────────────────────────
# V18.1 (P1): Previously this module set ``CUDA_VISIBLE_DEVICES=-1`` at
# import time, which forced the *entire process* onto CPU and silently
# disabled CUDA for torch (and therefore the embedding model) loaded
# afterwards. PaddleOCR only needs CPU for its own inference, so we now
# scope the env-var override to JUST the PaddleOCR init + inference calls.
@contextlib.contextmanager
def _cpu_only_cuda():
    """Temporarily hide CUDA from torch (for PaddleOCR which needs CPU)."""
    old = os.environ.get("CUDA_VISIBLE_DEVICES")
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = old


logger = get_main_logger()


class OCRService:
    OLLAMA_URL = "http://localhost:11434"  # legacy fallback (V18.20.4.3/W-c9: live calls resolve via _ollama_url())

    def _ollama_url(self) -> str:
        """V18.20.4.3 (P2 / W-c9): canonical Ollama URL from settings.

        Replaces the two ``f"{self.OLLAMA_URL}/api/generate"`` hardcodes
        below — a remote-Ollama rig previously had its OCR stage talking
        to localhost. Fail-soft: any Settings failure falls back to the
        legacy constant.
        """
        try:
            from utils.settings import Settings

            return Settings().get_ollama_url()
        except Exception:
            return self.OLLAMA_URL

    def __init__(
        self,
        request: ConversionRequest,
        analysis: PdfAnalysisResult,
        pages_to_ocr: list[int],
        log_callback: Callable[[str, str], None] | None = None,
        progress_callback: Callable[[float], None] | None = None,
        status_callback: Callable[[str], None] | None = None,  # NEW
        valid_pages: set | None = None,  # NEW: restrict processing to these pages
    ):
        self.request = request
        self.analysis = analysis
        self.pages_to_ocr = set(pages_to_ocr)
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._progress = progress_callback or (lambda v: None)
        self._status = status_callback or (lambda msg: None)  # NEW
        self.model_manager = ModelManager()
        # valid_pages: if set, only these page numbers will be processed
        # (both OCR and digital text extraction). None = process all pages.
        self.valid_pages = valid_pages
        settings = Settings()

        self._poppler_path = settings.get("paths.poppler") or ""
        self._tesseract_cmd = settings.get(
            "paths.tesseract",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        # V0.6.0 (4-c): tesseract auto-resolution. The shipped default for
        # ``paths.tesseract`` is the Windows installer path
        # (utils/settings.py:541); on every other host that value points at
        # a non-existent file, and ``_tesseract_ocr`` pins
        # ``pytesseract.pytesseract.tesseract_cmd`` to it → every call
        # raises (TesseractNotFoundError, or PermissionError for the
        # blanked value) and the page degrades to "all OCR methods failed"
        # even though a working tesseract sits on PATH. Mirror the poppler
        # auto-detection above: probe PATH and use the found binary when
        # the configured one is absent. Fail-open: keep the configured
        # value when nothing is found (behavior unchanged).
        if not self._tesseract_cmd or not os.path.isfile(self._tesseract_cmd):
            _detected_tess = shutil.which("tesseract")
            if _detected_tess:
                self.log(f"  🔍 Tesseract auto-detected: {_detected_tess}", "INFO")
                self._tesseract_cmd = _detected_tess
        self._image_dpi = settings.get("ocr.image_dpi", 300)

        # --- FIX: Force OCR timeout to at least 120 seconds ---
        raw_timeout = settings.get("ocr.timeout", 120)
        self._ocr_timeout = max(120, raw_timeout)  # enforce minimum
        self.log(
            f"  🔧 OCR timeout set to {self._ocr_timeout}s (requested: {raw_timeout}s)", "DEBUG"
        )

        # PaddleOCR toggle
        self._use_paddleocr = settings.get("ocr.use_paddleocr", False)
        self._paddle_ocr = None  # lazy‑initialised

        # V18.2.15 (P6): OCR page-processing parallelism. The OCR model is
        # loaded ONCE (acquire_model below), scans all needed pages, then
        # unloaded (release_model in finally block). This setting controls
        # how many pages are processed concurrently DURING that loaded
        # phase. Default 1 (sequential) — safe for the 6 GB OCR model which
        # is single-instance on Ollama (parallel HTTP calls just queue at
        # the server). Set to 2-4 only when using PaddleOCR/Tesseract
        # (CPU-bound, benefit from threads).
        self._ocr_parallel_workers = max(1, settings.get("local.ocr_parallel_workers", 1))
        if self._ocr_parallel_workers > 1:
            self.log(
                f"  🔧 V18.2.15 OCR parallelism: {self._ocr_parallel_workers} workers "
                f"(page-level, within the loaded-OCR phase)",
                "INFO",
            )

        # Auto-detect poppler if not configured
        if not self._poppler_path:
            detected = self._detect_poppler()
            if detected:
                self._poppler_path = detected
                self.log(f"  🔍 Poppler auto-detected: {detected}", "INFO")
            else:
                self._poppler_path = None

        # Initialise markitdown
        self._md_tool = None
        try:
            from markitdown import MarkItDown

            self._md_tool = MarkItDown()
            self.log("  ✅ markitdown ready for digital-page extraction", "INFO")
        except Exception as e:
            self.log(f"  ⚠️ markitdown unavailable ({e}), falling back to pypdf", "WARNING")

        # ── Initialise PaddleOCR if enabled (CPU-only) ────────────────────
        # V18.1 (P1): wrap import + init in ``_cpu_only_cuda()`` so the
        # CUDA_VISIBLE_DEVICES=-1 override is scoped to PaddleOCR only and
        # does not leak to torch (e.g. the embedding model) imported later.
        if self._use_paddleocr:
            try:
                with _cpu_only_cuda():
                    from paddleocr import PaddleOCR

                    # Force CPU with use_gpu=False
                    try:
                        # Try with show_log=False first
                        self._paddle_ocr = PaddleOCR(
                            lang="en",
                            use_gpu=False,
                            show_log=False,
                        )
                        self.log("  ✅ PaddleOCR initialised (CPU)", "INFO")
                    except TypeError:
                        # Fallback without show_log
                        try:
                            self._paddle_ocr = PaddleOCR(
                                lang="en",
                                use_gpu=False,
                            )
                            self.log("  ✅ PaddleOCR initialised (CPU)", "INFO")
                        except Exception as e:
                            self.log(f"  ❌ PaddleOCR init failed: {e}. Disabling.", "WARNING")
                            self._paddle_ocr = None
                            self._use_paddleocr = False
                    except Exception as e:
                        self.log(f"  ❌ PaddleOCR init failed: {e}. Disabling.", "WARNING")
                        self._paddle_ocr = None
                        self._use_paddleocr = False
            except ImportError:
                self.log("  ⚠️ PaddleOCR not installed. Run: pip install paddleocr", "WARNING")
                self._use_paddleocr = False
            except Exception as e:
                self.log(f"  ⚠️ PaddleOCR init failed: {e}. Disabling.", "WARNING")
                self._use_paddleocr = False

    # ─────────────────────────────────────────────────────────────────────────
    # Poppler auto-detection
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_poppler() -> str | None:
        """
        Scan common Windows installation paths for pdftoppm.exe.
        Returns the directory path (for use as poppler_path in pdf2image),
        or None if not found.
        """
        # PACKAGING (build_installer.py): a poppler copy bundled with the
        # installed app wins over everything else — the installer ships it
        # in <install>\Elixir\_internal\tools\ so OCR works out of the box.
        try:
            from app_paths import find_bundled_tool

            bundled = find_bundled_tool("pdftoppm.exe")
            if bundled is not None:
                return str(bundled.parent)
        except Exception:
            pass

        if platform.system() != "Windows":
            # On Linux/macOS poppler is normally on PATH — return "" (use default)
            return ""

        candidates = [
            r"C:\poppler-*\Library\bin",
            r"C:\poppler-*\bin",
            r"C:\poppler\bin",
            r"C:\Program Files\poppler-*\Library\bin",
            r"C:\Program Files (x86)\poppler-*\Library\bin",
            r"C:\tools\poppler\bin",
            r"C:\tools\poppler-*\Library\bin",
        ]
        # Dynamic candidates based on environment
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            candidates += [
                os.path.join(userprofile, "scoop", "apps", "poppler", "current", "bin"),
                os.path.join(userprofile, "poppler", "bin"),
            ]
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        if conda_prefix:
            candidates.append(os.path.join(conda_prefix, "Library", "bin"))

        for pattern in candidates:
            matches = sorted(glob.glob(pattern), reverse=True)  # newest version first
            for match in matches:
                exe = os.path.join(match, "pdftoppm.exe")
                if os.path.isfile(exe):
                    return match

        return None

    def _check_poppler(self) -> bool:
        """Return True if poppler is usable, False otherwise (with log message)."""
        if self._poppler_path is not None:
            return True
        self.log(
            "  ❌ Poppler not found — OCR for image pages is disabled.\n"
            "  To fix: download Poppler for Windows from\n"
            "  https://github.com/oschwartz10612/poppler-windows/releases\n"
            "  Extract it, then set paths.poppler in ~/.elixir/settings.json\n"
            '  Example:  "paths": { "poppler": "C:\\\\poppler-24.08.0\\\\Library\\\\bin" }',
            "WARNING",
        )
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def process_pdf(self, pdf_path: Path, password: str | None = None) -> dict[int, OcrResult]:
        self.log(f"📖 Opening PDF: {pdf_path.name}", "INFO")
        try:
            reader = PdfReader(str(pdf_path))
            if reader.is_encrypted and password:
                reader.decrypt(password)
        except Exception as e:
            self.log(f"❌ Cannot open PDF: {e}", "ERROR")
            return {}

        total_pages = len(reader.pages)
        results: dict[int, OcrResult] = {}

        # Check Poppler availability once — used by both UnlimitedOCR and Qwen paths
        poppler_ok = self._check_poppler()

        # ── UnlimitedOCR batch phase (optional, replaces Qwen for scanned pages) ──
        unlimited_path = Settings().get("ocr.unlimited_ocr_path", "")
        unlimited_used: set = set()
        if unlimited_path and self.pages_to_ocr and poppler_ok:
            from core.ocr.unlimited_ocr import UnlimitedOCREngine

            u_engine = UnlimitedOCREngine(
                model_path=unlimited_path,
                log_callback=self.log,
            )
            scanned_pages = [reader.pages[p - 1] for p in sorted(self.pages_to_ocr)]
            scanned_numbers = sorted(self.pages_to_ocr)
            self.log(
                f"  🏃 UnlimitedOCR: batch processing {len(scanned_numbers)} scanned pages…",
                "INFO",
            )
            batch_results = u_engine.process_batch(
                scanned_pages,
                scanned_numbers,
                image_max_size=self.request.image_max_size,
                poppler_path=self._poppler_path,
            )
            for pn, res in batch_results.items():
                results[pn] = res
                if res.success:
                    unlimited_used.add(pn)
            u_engine.unload()
            succeeded = sum(1 for r in batch_results.values() if r.success)
            self.log(
                f"  ✅ UnlimitedOCR batch done: {succeeded}/{len(scanned_numbers)} pages extracted",
                "INFO",
            )

        # ── Acquire Qwen model once — but only if poppler is available and
        # there are still pages that UnlimitedOCR didn't handle ──────────
        qwen_loaded = False
        remaining_ocr = self.pages_to_ocr - unlimited_used

        # V18.2.16: Deterministic OCR pre-scan — BEFORE loading the 6 GB OCR
        # model, do a fast text-density check on the remaining candidate pages.
        # This determines exactly which pages actually need OCR (scanned/image-
        # only) vs. which already have extractable digital text. When 0 pages
        # need OCR, the model load is skipped entirely — saving the multi-minute
        # load + unload cycle. When N pages need OCR, the model gets the exact
        # list (no wasted work on digital pages). See core/ocr/ocr_prescan.py.
        if remaining_ocr and self.request.use_llm_ocr and poppler_ok:
            try:
                from core.ocr.ocr_prescan import intersect_with_valid_pages, prescan_pages

                # Restrict the candidate set to selected chapters / page range
                # (when active) so we don't pre-scan pages the user didn't
                # select. Falls back to the full remaining_ocr set otherwise.
                _candidates = intersect_with_valid_pages(
                    pages_to_ocr=sorted(remaining_ocr),
                    valid_pages=self.valid_pages,
                    page_range_start=getattr(self.request, "page_range_start", None),
                    page_range_end=getattr(self.request, "page_range_end", None),
                    total_pages=total_pages,
                )
                _prescan = prescan_pages(
                    pdf_path=pdf_path,
                    candidate_pages=_candidates,
                    password=getattr(self.request, "password", None),
                    log_fn=self.log,
                )
                if _prescan.skip_model_load:
                    # No pages need OCR — skip the model load entirely.
                    self.log(
                        f"  ✅ V18.2.16 Pre-scan: 0 of {_prescan.total_scanned} "
                        f"candidate page(s) need OCR — SKIPPING OCR model load "
                        f"(saves several minutes). Digital pages will be "
                        f"extracted via markitdown.",
                        "INFO",
                    )
                    # Clear remaining_ocr so the model-load block below is skipped.
                    remaining_ocr = set()
                else:
                    # Some pages need OCR — refine remaining_ocr to ONLY those
                    # pages. Digital pages skip the OCR model entirely.
                    _before_count = len(remaining_ocr)
                    remaining_ocr = set(_prescan.scanned_pages) - unlimited_used
                    self.log(
                        f"  📋 V18.2.16 Pre-scan refined OCR target: "
                        f"{_before_count} → {len(remaining_ocr)} page(s) "
                        f"({len(_prescan.digital_pages)} had digital text, "
                        f"skipped OCR model for those).",
                        "INFO",
                    )
            except Exception as _e:
                # V18.2.14 (B4): traceable — fail-open to the original
                # remaining_ocr set so the OCR model loads as before.
                from utils.error_trace import log_swallow

                log_swallow("ocr_prescan", _e, detail="falling back to full pages_to_ocr set")

        # ── FIX: Before loading vision model, unload summarisation model if loaded ──
        summary_model = getattr(self.request, "summarisation_model", None)
        if summary_model:
            loaded = self.model_manager.get_loaded_models()
            if summary_model in loaded:
                self.log(
                    f"  🔓 Force-unloading summarisation model '{summary_model}' to free VRAM for OCR...",
                    "INFO",
                )
                self._status("Offloading summarisation model...")
                self.model_manager.force_unload(summary_model)
        else:
            self.log(
                "  ⚠️ No summarisation model specified in request; cannot proactively unload.",
                "DEBUG",
            )

        if remaining_ocr and self.request.use_llm_ocr and poppler_ok:
            model = self.request.primary_ocr_model
            # V0.4.24 (V4.23 run post-mortem): provider-aware load gate.
            # The V4.23 rig (provider=llamacpp) logged the misleading
            # "Model '…' not found in Ollama. Run: ollama pull …" — the
            # model lives on llama-server; the Ollama-only legacy path
            # (qwen_loaded) is irrelevant there and the provider-agnostic
            # vision OCR path (_provider_vision_ocr) does the routing.
            try:
                from utils.settings import Settings as _GateSettings

                _gate_provider = (
                    (_GateSettings().get("summarisation.provider", "ollama") or "ollama")
                    .strip()
                    .lower()
                )
            except Exception:
                _gate_provider = "ollama"
            # V0.6.14: model_architecture retired — the provider setting is
            # the single source.
            if _gate_provider == "llamacpp":
                self.log(
                    "  ℹ️ Provider is llama.cpp — page OCR routes via the "
                    "llama-server vision provider (no Ollama model load).",
                    "DEBUG",
                )
            elif self.model_manager.model_exists(model):
                # V18.2.15 (P6): Phase-boundary trace — OCR phase START.
                # This is a dedicated phase: the OCR model is loaded ONCE,
                # all pages are scanned, then the model is unloaded BEFORE
                # the summarizer phase begins. The 6 GB OCR model cannot
                # coexist with the LLM model in VRAM — this boundary is
                # critical. The trace below marks the load; the matching
                # unload trace is in the finally block below.
                import time as _ocr_t

                _ocr_load_start = _ocr_t.time()
                self.log(
                    "  ╔══ V18.2.15 OCR PHASE START ═══════════════════════════╗",
                    "INFO",
                )
                self.log(
                    f"  ║ Loading OCR model '{model}' (dedicated phase —     ║",
                    "INFO",
                )
                self.log(
                    "  ║ will unload BEFORE summarizer loads to free VRAM).  ║",
                    "INFO",
                )
                self.log(
                    f"  ║ Pages to OCR: {len(remaining_ocr)} | "
                    f"Workers: {self._ocr_parallel_workers}{' (sequential)' if self._ocr_parallel_workers == 1 else ''}",
                    "INFO",
                )
                self._status(f"Loading {model}...")
                # ── FIX: Force load without VRAM check ──────────────────────────
                qwen_loaded = self.model_manager.acquire_model(
                    model,
                    ModelType.OCR,
                    skip_vram_check=True,
                    status_callback=self._status,  # NEW: pass for UI updates
                )
                _ocr_load_elapsed = _ocr_t.time() - _ocr_load_start
                if qwen_loaded:
                    self.log(
                        f"  ✅ OCR model '{model}' loaded in {_ocr_load_elapsed:.0f}s "
                        f"— scanning {len(remaining_ocr)} page(s) now",
                        "INFO",
                    )
                else:
                    self.log(
                        f"  ⚠️ Could not load '{model}' (after {_ocr_load_elapsed:.0f}s), "
                        f"using Tesseract only",
                        "WARNING",
                    )
                    self._status(f"⚠️ Could not load {model}, using Tesseract.")
            else:
                self.log(
                    f"  ⚠️ Model '{model}' not found in Ollama. Run: ollama pull {model}", "WARNING"
                )
        elif self.pages_to_ocr and not poppler_ok:
            self.log("  ⚠️ Skipping OCR model load — poppler is required first.", "WARNING")
            self._status("⚠️ Poppler missing – OCR disabled.")

        try:
            # Determine which pages to process. If valid_pages is set (chapter
            # selection active), only process those pages — skip everything else.
            # This saves massive time on large PDFs where only a few chapters
            # are selected.
            if self.valid_pages is not None:
                pages_to_process_sorted = sorted(
                    p for p in self.valid_pages if 1 <= p <= total_pages
                )
                self.log(
                    f"  📄 Processing {len(pages_to_process_sorted)}/{total_pages} pages "
                    f"(chapter selection active — skipping {total_pages - len(pages_to_process_sorted)} unselected pages)",
                    "INFO",
                )
            else:
                pages_to_process_sorted = list(range(1, total_pages + 1))

            for page_num in pages_to_process_sorted:
                page = reader.pages[page_num - 1]
                if page_num in self.pages_to_ocr:
                    # Skip if UnlimitedOCR already handled this page successfully
                    if page_num in unlimited_used:
                        continue
                    self.log(f"  🔍 OCR  page {page_num}/{total_pages} (scanned)…", "INFO")
                    result = self._ocr_scanned_page(page, page_num, qwen_loaded, poppler_ok)
                else:
                    result = self._extract_digital_page(page, page_num)
                results[page_num] = result

                # Emit fine-grained progress: OCR phase maps to 10%–70% of overall bar
                ocr_frac = page_num / total_pages  # 0.0 → 1.0
                overall = 0.10 + ocr_frac * 0.60  # 0.10 → 0.70
                self._progress(overall)

                if page_num % 20 == 0 or page_num == pages_to_process_sorted[-1]:
                    pct = page_num / total_pages * 100
                    self.log(f"  📄 {page_num}/{total_pages} pages processed ({pct:.0f}%)", "INFO")
        finally:
            if qwen_loaded:
                # V18.2.15 (P6): Phase-boundary trace — OCR phase END.
                # The OCR model is now released. The summarizer phase can
                # safely load the LLM model without VRAM contention. This
                # trace is the matching close of the "OCR PHASE START" log
                # above — together they delimit the dedicated OCR window.
                _ocr_phase_elapsed = _ocr_t.time() - _ocr_load_start
                self.model_manager.release_model(self.request.primary_ocr_model)
                self.log(
                    "  ╚══ V18.2.15 OCR PHASE END ═══════════════════════════╝",
                    "INFO",
                )
                self.log(
                    f"  🔓 OCR model released (phase took {_ocr_phase_elapsed:.0f}s total) "
                    f"— VRAM free for summarizer",
                    "INFO",
                )
                self._status("OCR model released.")
                # V18.2.15 (P6): Best-effort VRAM cache clear after unload.
                # Ensures the OCR model's VRAM footprint is actually freed
                # before the summarizer requests its own model. Traceable.
                try:
                    import torch as _torch

                    if _torch.cuda.is_available():
                        _torch.cuda.empty_cache()
                        self.log("  🧹 VRAM cache cleared post-OCR", "DEBUG")
                except Exception as _e:
                    from utils.error_trace import log_swallow

                    log_swallow("ocr_phase_vram_clear", _e)

        ok_count = sum(1 for r in results.values() if r.success)
        failed_pages = sorted(p for p, r in results.items() if not r.success)
        if failed_pages:
            self.log(
                f"  ⚠️ {len(failed_pages)} page(s) failed to extract: {failed_pages}", "WARNING"
            )

        # V3.3.0 E2: OCR quality scoring — flag low-quality pages
        try:
            from core.summarisation.text_preprocessor import score_ocr_quality

            low_quality = []
            for pn, r in results.items():
                if r.success and r.text:
                    score = score_ocr_quality(r.text)
                    if score < 0.4:
                        low_quality.append((pn, score))
            if low_quality:
                self.log(
                    f"  ⚠️ OCR quality: {len(low_quality)} page(s) below quality threshold",
                    "WARNING",
                )
                for pn, sc in low_quality[:5]:
                    self.log(f"    p.{pn}: quality score {sc:.2f}/1.0", "DEBUG")
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)  # quality scoring is optional

        self.log(f"✅ PDF processing done: {ok_count}/{total_pages} pages extracted", "SUCCESS")
        self._status(f"PDF done: {ok_count}/{total_pages} pages.")
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Digital page extraction (Tiered strategy)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_digital_page(self, page, page_num: int) -> OcrResult:
        """
        Tiered extraction for pages that may be digital or image-heavy:
        1. markitdown (fast, accurate for digital PDFs)
        2. If text is short (< 50 alnum chars) OR page is marked scanned -> Vision OCR (OlmoOCR)
        3. Tesseract (lightweight fallback)
        4. pypdf extract_text() (last resort)
        """
        # 1. Try markitdown
        if self._md_tool is not None:
            text = self._markitdown_single_page(page, page_num)
            if text:
                alnum = len(re.sub(r"\s", "", text))
                if alnum > 50:
                    return OcrResult(
                        page_num=page_num, text=text, success=True, engine_used=OcrEngine.MARKITDOWN
                    )
                # If text is short, mark the page for vision OCR
                self.log(
                    f"  ⚠️ markitdown p.{page_num} returned only {alnum} alnum chars – falling back to vision.",
                    "DEBUG",
                )

        # 2. Check if this page is marked as scanned or image-heavy
        if page_num in self.pages_to_ocr:
            image_bytes = self._page_to_image_bytes(page, page_num)
            if image_bytes:
                # 2a. Try OlmoOCR (or Qwen if model name doesn't contain "olmocr")
                result = self._olmo_ocr_single(image_bytes, page_num, attempt=1)
                if result.success:
                    return result

                # 2b. Try Tesseract
                tess = self._tesseract_ocr(image_bytes, page_num)
                if tess.success and len(tess.text.strip()) >= 20:
                    self.log(f"    ⚠️ Tesseract recovered p.{page_num}", "WARNING")
                    return tess

        # 3. Fallback to pypdf extract_text()
        try:
            raw = page.extract_text() or ""
            if raw.strip():
                return OcrResult(
                    page_num=page_num, text=raw, success=True, engine_used=OcrEngine.MARKITDOWN
                )
        except Exception as e:
            self.log(f"  ⚠️ pypdf page {page_num}: {e}", "DEBUG")

        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.NONE,
            error_msg="No extractable text after all methods",
        )

    def _markitdown_single_page(self, page, page_num: int) -> str:
        tmp_path = None
        try:
            writer = PdfWriter()
            writer.add_page(page)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                writer.write(tmp)
                tmp_path = tmp.name
            result = self._md_tool.convert(tmp_path)
            return result.text_content or ""
        except Exception as e:
            self.log(f"  ⚠️ markitdown page {page_num}: {e}", "DEBUG")
            return ""
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    # Vision OCR – OlmoOCR (NEW)
    # ─────────────────────────────────────────────────────────────────────────

    def _olmo_ocr_single(self, image_bytes: bytes, page_num: int, attempt: int = 1) -> OcrResult:
        """
        Use OlmOCR-2-7B vision model to extract text from an image page.
        If the primary model is not Olmo, falls back to standard Qwen.
        """
        model = self.request.primary_ocr_model
        # If model is not Olmo, fallback to Qwen
        if "olmocr" not in model.lower():
            return self._qwen_ocr_single(image_bytes, page_num, attempt)

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": model,
            "prompt": (
                "Extract ALL text visible in this page image. "
                "Preserve headings, paragraphs, lists. "
                "Output ONLY the extracted text, no commentary."
            ),
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }
        url = f"{self._ollama_url()}/api/generate"
        try:
            self.log(f"    🧠 OlmoOCR attempt {attempt}…", "DEBUG")
            resp = safe_ollama_request("POST", url, json=payload, timeout=self._ocr_timeout)
            text = resp.json().get("response", "").strip()
            if text:
                self.log(f"    ✅ OlmoOCR p.{page_num}: {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num, text=text, success=True, engine_used=OcrEngine.QWEN_VL
                )
        except Exception as e:
            self.log(f"    ⚠️ OlmoOCR attempt {attempt}: {e}", "WARNING")
        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.QWEN_VL,
            error_msg=f"OlmoOCR attempt {attempt} failed",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Scanned page OCR (legacy, kept for compatibility)
    # ─────────────────────────────────────────────────────────────────────────

    def _ocr_scanned_page(
        self, page, page_num: int, qwen_loaded: bool, poppler_ok: bool
    ) -> OcrResult:
        if not poppler_ok:
            return OcrResult(
                page_num=page_num,
                text=f"[Page {page_num}: OCR skipped — poppler not installed]",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="Poppler not found. See log for installation instructions.",
            )

        image_bytes = self._page_to_image_bytes(page, page_num)
        if not image_bytes:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="Page-to-image conversion failed",
            )

        # ── V0.4.1: Try provider-agnostic vision OCR FIRST ───────────────
        # This checks the main model AND the OCR model for vision capability
        # (via a live API probe) and routes to whichever provider (Ollama or
        # llama.cpp) the vision model is on. If no vision model is found,
        # falls through to the existing Ollama-only Qwen path → Tesseract.
        if self.request.use_llm_ocr:
            result = self._provider_vision_ocr(image_bytes, page_num)
            if result.success:
                return result

        # ── Try Qwen if loaded (legacy Ollama-only path) ───────────────
        if qwen_loaded and self.request.use_llm_ocr:
            result = self._qwen_ocr_single(image_bytes, page_num, attempt=1)
            if result.success:
                return result

            # ── If Qwen fails, try PaddleOCR (if enabled) ─────────────────
            if self._use_paddleocr and self._paddle_ocr is not None:
                result_paddle = self._paddle_ocr_single(image_bytes, page_num)
                if result_paddle.success:
                    self.log(f"    ✅ PaddleOCR recovered p.{page_num}", "INFO")
                    return result_paddle

            # V10.35.0 (Sprint 7): Local VLM fallback before Tesseract.
            # When OlmOCR/Qwen returns <50 chars, use a capable local VLM
            # (e.g. llava, minicpm-v) via Ollama instead of degrading to
            # Tesseract.  Best-of-both: local for cheap, VLM for hard.
            vlm_result = self._vlm_ocr_fallback(image_bytes, page_num)
            if vlm_result.success and len(vlm_result.text.strip()) >= 20:
                self.log(
                    f"    ✅ Local VLM recovered p.{page_num} (OlmOCR/Qwen returned <50 chars)",
                    "INFO",
                )
                return vlm_result

            # ── Finally, try Tesseract ─────────────────────────────────────
            tess = self._tesseract_ocr(image_bytes, page_num)
            if tess.success and len(tess.text.strip()) >= 20:
                self.log(f"    ⚠️ Qwen failed p.{page_num} → Tesseract recovered", "WARNING")
                return tess

            if not tess.success or len(tess.text.strip()) < 20:
                self.log(
                    f"    ⚠️ p.{page_num}: all OCR methods returned < 20 chars "
                    f"— image-only page, skipping retries.",
                    "WARNING",
                )
                return OcrResult(
                    page_num=page_num,
                    text="",
                    success=False,
                    engine_used=OcrEngine.NONE,
                    error_msg=f"Page {page_num} appears to be image-only with no extractable text",
                )

            # If Tesseract gave partial results, still try one more Qwen pass
            result2 = self._qwen_ocr_single(image_bytes, page_num, attempt=2)
            if result2.success:
                return result2

            self.log(f"    ⚠️ Qwen failed p.{page_num} → Tesseract", "WARNING")
            return tess

        # ── Qwen not loaded: try PaddleOCR then Tesseract ──────────────────
        if self._use_paddleocr and self._paddle_ocr is not None:
            result_paddle = self._paddle_ocr_single(image_bytes, page_num)
            if result_paddle.success:
                return result_paddle

        result = self._tesseract_ocr(image_bytes, page_num)
        if not result.success:
            result.text = f"[Page {page_num}: all OCR methods failed]"
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # V0.4.1: Provider-agnostic vision OCR — the 3-step logic the owner
    # specified:
    #   1. Check if the MAIN model has vision → use it for OCR
    #   2. Check if a SEPARATE OCR model has vision → use it
    #   3. If neither has vision, use Tesseract fallback
    # Content-agnostic (AGENTS.md Rule 1): no hardcoded model names —
    # the vision capability is detected via a LIVE API probe, not a
    # name-keyed check. The provider (Ollama or llama.cpp) is determined
    # by the app's summarisation.provider setting, not hardcoded in the
    # OCR code.
    # ─────────────────────────────────────────────────────────────────────────

    def _get_vision_provider(self):
        """Return a tuple (provider, model_name) for the best vision-capable
        model, or (None, None) if no vision model is available.

        V0.4.1 fix: CACHED — the probe runs ONCE per conversion (not per
        page). The supports_vision() probe sends a live API request (15s
        timeout for llama.cpp, 10s for Ollama). Running it for every
        scanned page (31 pages × 15s = 465s) would exceed the chapter
        deadline and cause the summarization phase to fail with "empty
        responses."

        Logic (per the owner's specification):
          1. Check the MAIN summarisation model — if it has vision, use it
          2. Check a SEPARATE OCR model (if configured) — if it has vision, use it
          3. Return (None, None) if neither has vision
        """
        # V0.4.1: cache the result — probe once, reuse for all pages
        if hasattr(self, "_vision_provider_cache"):
            return self._vision_provider_cache

        from utils.settings import Settings as _S

        settings = _S()
        # V0.6.14: model_architecture retired — the provider setting routes.
        arch = (settings.get("summarisation.provider", "ollama") or "ollama").strip().lower()

        # Step 1: check the MAIN model
        main_model = getattr(self.request, "summarisation_model", "") or ""
        if main_model:
            provider = self._create_vision_provider(arch, main_model, settings)
            if provider and provider.supports_vision():
                self.log(
                    f"  📸 V0.4.1: Main model '{main_model}' has vision — using it for OCR",
                    "INFO",
                )
                self._vision_provider_cache = (provider, main_model)
                return provider, main_model

        # Step 2: check a separate OCR model
        ocr_model = getattr(self.request, "primary_ocr_model", "") or ""
        if ocr_model and ocr_model != main_model:
            provider = self._create_vision_provider(arch, ocr_model, settings)
            if provider and provider.supports_vision():
                self.log(
                    f"  📸 V0.4.1: OCR model '{ocr_model}' has vision — using it for OCR",
                    "INFO",
                )
                self._vision_provider_cache = (provider, ocr_model)
                return provider, ocr_model

        # Step 3: neither has vision
        self.log(
            "  📸 V0.4.1: No vision-capable model found — will use Tesseract fallback",
            "WARNING",
        )
        self._vision_provider_cache = (None, None)
        return None, None

    def _create_vision_provider(self, arch: str, model: str, settings):
        """Create a provider for the given model (for vision capability
        probing + image OCR calls). Returns None if the provider can't
        be created.

        V0.4.12: when the architecture is llamacpp AND the OCR model is
        different from the main model, try BOTH the llama.cpp provider
        AND an Ollama provider. The OCR model dropdown is populated from
        Ollama's /api/tags, so when the user picks an Ollama-hosted OCR
        model while running their main model on llama.cpp, we need to
        probe Ollama (not llama.cpp) for that OCR model.

        V0.4.24 (V4.23 run post-mortem): the ACTIVE provider setting
        (``summarisation.provider``) is authoritative. (V0.6.14: the old
        ``model_architecture`` cross-read is retired — the provider
        setting is the single source.)
        """
        try:
            from core.llm.llm_provider_impl import create_provider

            # Determine the provider name (V0.6.14: the canonical provider
            # setting — model_architecture retired; the arch param now
            # carries the provider name itself).
            _provider_setting = (
                (settings.get("summarisation.provider", "ollama") or "ollama").strip().lower()
            )
            if arch == "llamacpp" or _provider_setting == "llamacpp":
                provider_name = "llamacpp"
            elif arch in ("openai_compatible", "claude", "freellmapi"):
                # V0.6.14: a cloud-hosted model has NO local vision probe —
                # same result as the old cloud-architecture branch (the OCR
                # vision path is local-only by design).
                provider_name = None
            else:
                provider_name = "ollama"

            # Create the provider — but only if it's a local provider
            # (Ollama or llama.cpp). Cloud providers may support vision
            # but the OCR path requires a local model that can process
            # page images.
            if provider_name in ("ollama", "llamacpp"):
                provider = create_provider(provider_name, settings)
                if provider and provider.supports_vision():
                    return provider
                # V0.4.12: if the llama.cpp provider doesn't support
                # vision for this model, try Ollama as a fallback.
                # The OCR model dropdown is populated from Ollama's
                # /api/tags, so the model may be hosted on Ollama even
                # when the main model is on llama.cpp.
                if provider_name == "llamacpp":
                    try:
                        ollama_provider = create_provider("ollama", settings)
                        if ollama_provider and ollama_provider.supports_vision():
                            self.log(
                                f"  📸 V0.4.12: OCR model '{model}' not found on "
                                f"llama.cpp — using Ollama instead (cross-backend OCR)",
                                "INFO",
                            )
                            return ollama_provider
                    except Exception:
                        pass
                return provider
            return None
        except Exception as e:
            self.log(f"  ⚠️ V0.4.1: Could not create vision provider: {e}", "WARNING")
            return None

    def _provider_vision_ocr(self, image_bytes: bytes, page_num: int) -> OcrResult:
        """OCR a page image using the provider-agnostic vision call.

        This is the V0.4.1 replacement for _qwen_ocr_single and
        _olmo_ocr_single — it routes to whichever provider (Ollama or
        llama.cpp) the vision model is running on.
        """
        provider, model_name = self._get_vision_provider()
        if not provider:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="No vision-capable model available",
            )

        prompt = (
            "Extract ALL text visible in this page image. "
            "Preserve headings, paragraphs, lists. "
            "Output ONLY the extracted text, no commentary, no markdown."
        )
        try:
            # V0.4.12: pass the model name to complete_with_image so
            # cross-backend OCR uses the correct model (the OCR model
            # from Ollama, not the provider's default model which might
            # be the llama.cpp main model).
            text = provider.complete_with_image(
                prompt,
                image_bytes,
                temperature=0.0,
                max_tokens=4096,
                model=model_name,
            )
            if text and text.strip():
                self.log(f"  ✅ V0.4.1 vision OCR p.{page_num}: {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num,
                    text=text.strip(),
                    success=True,
                    engine_used=OcrEngine.QWEN_VL,  # reuse enum (any vision OCR)
                )
        except Exception as e:
            self.log(f"  ⚠️ V0.4.1 vision OCR p.{page_num} failed: {e}", "WARNING")

        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.QWEN_VL,
            error_msg="Vision OCR returned no text",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # OCR engine methods (Qwen, Paddle, Tesseract)
    # ─────────────────────────────────────────────────────────────────────────

    def _qwen_ocr_single(self, image_bytes: bytes, page_num: int, attempt: int) -> OcrResult:
        """Single Qwen OCR attempt without internal retry loop.

        V0.4.9: tries /api/chat as a fallback when /api/generate returns
        400 or empty — some custom GGUF models (e.g., GLM-OCR-Q8_ggml-org)
        only work with the chat endpoint.
        """
        model = self.request.primary_ocr_model
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Extract ALL text visible in this page image. "
            "Preserve headings, paragraphs, lists. "
            "Output ONLY the extracted text, no commentary."
        )
        generate_payload = {
            "model": model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }
        chat_payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        }
        try:
            self.log(f"    🧠 Qwen OCR attempt {attempt}…", "DEBUG")
            # V0.4.9: try /api/generate first, then /api/chat as fallback.
            text = self._try_ollama_vision_endpoint(
                "/api/generate", generate_payload, "response", model, page_num, attempt
            )
            if text:
                self.log(f"    ✅ Qwen OCR p.{page_num}: {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num, text=text, success=True, engine_used=OcrEngine.QWEN_VL
                )
            # V0.4.9: /api/generate returned empty — try /api/chat.
            self.log("    🧠 Qwen OCR: trying /api/chat fallback…", "DEBUG")
            text = self._try_ollama_vision_endpoint(
                "/api/chat", chat_payload, "message.content", model, page_num, attempt
            )
            if text:
                self.log(f"    ✅ Qwen OCR p.{page_num} (via /api/chat): {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num, text=text, success=True, engine_used=OcrEngine.QWEN_VL
                )
        except Exception as e:
            self.log(f"    ⚠️ Qwen attempt {attempt}: {e}", "WARNING")
        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.QWEN_VL,
            error_msg=f"Qwen OCR attempt {attempt} failed",
        )

    def _try_ollama_vision_endpoint(
        self,
        endpoint: str,
        payload: dict,
        response_key: str,
        model: str,
        page_num: int,
        attempt: int,
    ) -> str | None:
        """V0.4.9: try one Ollama vision endpoint and return the text.

        Returns None on empty. Logs the specific Ollama 400 error body
        (not just "400 Bad Request") so the user can diagnose the issue.

        V0.4.19: routed through ``safe_ollama_request`` again (the V0.4.9
        rewrite bypassed it with a raw ``get_shared_session().post`` —
        losing the monitored transport AND letting tests hit the real
        network when an Ollama server happens to be running). A 400 from
        Ollama is MEANINGFUL here (e.g. "model does not support images"),
        so the HTTPError raised by ``raise_for_status`` is unwrapped and
        its body inspected instead of being swallowed.
        """
        import requests as _requests

        url = f"{self._ollama_url()}{endpoint}"
        try:
            resp = safe_ollama_request("POST", url, json=payload, timeout=self._ocr_timeout)
        except _requests.HTTPError as e:
            # A 400 carries a diagnosable Ollama error body — inspect it
            # (safe_ollama_request already called raise_for_status).
            resp = e.response
            if resp is None or resp.status_code != 400:
                self.log(f"    ⚠️ {endpoint} HTTP error: {e}", "DEBUG")
                return None
        except Exception as e:
            self.log(f"    ⚠️ {endpoint} request failed: {e}", "DEBUG")
            return None

        if resp.status_code == 400:
            # V0.4.9: capture the actual Ollama error body.
            try:
                err_body = resp.json().get("error", resp.text[:200])
            except Exception:
                err_body = resp.text[:200]
            self.log(
                f"    ⚠️ {endpoint} returned 400: {err_body}",
                "WARNING",
            )
            return None

        data = resp.json()
        if "." in response_key:
            text = data
            for key in response_key.split("."):
                text = text.get(key, {}) if isinstance(text, dict) else ""
        else:
            text = data.get(response_key, "")
        return text.strip() if text else None

    def _paddle_ocr_single(self, image_bytes: bytes, page_num: int) -> OcrResult:
        """Single PaddleOCR attempt (CPU-only)."""
        if self._paddle_ocr is None:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="PaddleOCR not initialised",
            )
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            img_np = np.array(img)
            # PaddleOCR v3.x expects a list of images or a single image
            # V18.1 (P1): scope CUDA_VISIBLE_DEVICES=-1 to this call only
            # so torch (and the embedding model) loaded elsewhere can still
            # use the GPU.
            with _cpu_only_cuda():
                result = self._paddle_ocr.ocr(img_np, cls=True)
            if not result or not result[0]:
                return OcrResult(
                    page_num=page_num,
                    text="",
                    success=False,
                    engine_used=OcrEngine.NONE,
                    error_msg="PaddleOCR no text found",
                )
            # Extract text from the list of detections
            lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0].strip()
                    if text:
                        lines.append(text)
            text = "\n".join(lines)
            if text:
                self.log(f"    ✅ PaddleOCR p.{page_num}: {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num,
                    text=text,
                    success=True,
                    engine_used=OcrEngine.TESSERACT,  # reuse enum
                )
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg="PaddleOCR returned empty",
            )
        except Exception as e:
            self.log(f"    ⚠️ PaddleOCR p.{page_num}: {e}", "WARNING")
            # More informative message for the user
            error_msg = f"PaddleOCR failed: {e}. Ensure dependencies are installed correctly (numpy<2.0, opencv-python==4.6.0.66)."
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg=error_msg,
            )

    def _page_to_image_bytes(self, page, page_num: int) -> bytes | None:
        try:
            from pdf2image import convert_from_bytes

            writer = PdfWriter()
            writer.add_page(page)
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)

            kwargs: dict = {"fmt": "png", "first_page": 1, "last_page": 1, "dpi": self._image_dpi}
            if self._poppler_path:
                kwargs["poppler_path"] = self._poppler_path

            images = convert_from_bytes(buf.getvalue(), **kwargs)
            if not images:
                return None
            img_buf = io.BytesIO()
            images[0].save(img_buf, format="PNG")
            img_buf.seek(0)
            return img_buf.getvalue()
        except Exception as e:
            self.log(f"  ⚠️ Page {page_num} → image failed: {e}", "WARNING")
            return None

    def _vlm_ocr_fallback(self, image_bytes: bytes, page_num: int) -> OcrResult:
        """V10.35.0 (Sprint 7): Local VLM OCR fallback.

        When OlmOCR/Qwen returns <50 chars on a page, this method tries a
        capable local VLM (e.g. ``llava:13b``, ``minicpm-v:8b``, or the
        model configured in ``settings.json: ocr.vlm_fallback_model``).
        The VLM is prompted to transcribe the page text — it's better at
        complex layouts, handwriting, and mixed-language pages than
        Tesseract.

        The VLM model is configured via ``ocr.vlm_fallback_model`` in
        settings.json.  If not set or not available, this method returns
        a failed OcrResult and the cascade continues to Tesseract.
        """
        # Check if a VLM fallback model is configured
        from utils.settings import Settings

        _s = Settings()
        vlm_model = _s.get("ocr.vlm_fallback_model", "")
        if not vlm_model:
            # V18.1 (S2): no hardcoded default model — if the user hasn't
            # configured ``ocr.vlm_fallback_model`` in settings.json, skip
            # the VLM fallback entirely and let the OCR cascade continue
            # to Tesseract. Previously this defaulted to "llava:13b",
            # which would attempt to load a model the user may not have
            # pulled (causing 120s timeouts and noisy failures).
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.NONE,
                error_msg="VLM fallback model not configured (set ocr.vlm_fallback_model in settings.json)",
            )

        try:
            import base64

            # Build the VLM prompt — ask for plain text transcription
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            payload = {
                "model": vlm_model,
                "prompt": (
                    "Transcribe ALL the text visible in this image. "
                    "Output only the transcribed text — no preamble, no "
                    "commentary, no markdown formatting. Preserve "
                    "paragraph breaks. If the text is in Persian/Arabic, "
                    "transcribe it in the original script."
                ),
                "images": [b64_image],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 4096,
                },
            }

            ollama_url = _s.get("ocr.ollama_url", "http://localhost:11434")
            # V18.1 (S2): use safe_ollama_request (proxy-proof session with
            # trust_env=False) so corporate HTTP_PROXY env vars don't
            # silently break the local Ollama call. The wrapper returns a
            # requests.Response and calls raise_for_status() — non-2xx
            # responses are surfaced via the except branch below.
            resp = safe_ollama_request(
                "POST",
                f"{ollama_url}/api/generate",
                json=payload,
                timeout=SHORT_LLM_TIMEOUT_S,
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                # Strip thinking if present
                import re

                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                if text and len(text) >= 20:
                    return OcrResult(
                        page_num=page_num,
                        text=text,
                        success=True,
                        engine_used=OcrEngine.MARKITDOWN,  # closest enum
                        error_msg=f"VLM fallback ({vlm_model})",
                    )
                else:
                    self.log(
                        f"  ⚠️ VLM fallback p.{page_num}: {vlm_model} returned "
                        f"{len(text)} chars — too short",
                        "DEBUG",
                    )
            else:
                self.log(
                    f"  ⚠️ VLM fallback p.{page_num}: Ollama returned {resp.status_code}",
                    "DEBUG",
                )
        except Exception as e:
            self.log(
                f"  ℹ️ VLM fallback p.{page_num} skipped ({type(e).__name__}: {e})",
                "DEBUG",
            )

        return OcrResult(
            page_num=page_num,
            text="",
            success=False,
            engine_used=OcrEngine.NONE,
            error_msg="VLM fallback failed",
        )

    def _tesseract_ocr(self, image_bytes: bytes, page_num: int) -> OcrResult:
        try:
            import pytesseract
            from PIL import Image

            # V0.6.0 (4-c): only pin the global when a usable command was
            # resolved — assigning a blank/bogus value overrides
            # pytesseract's own PATH resolution with a broken binary path.
            if self._tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
            pil_image = Image.open(io.BytesIO(image_bytes))
            # V0.4.24 (V4.23 run post-mortem — p.107): the default pass is
            # byte-identical to V0.4.23; when it returns NOTHING, retry
            # with alternate page-segmentation modes before giving up (the
            # "OCR retries" setting only guarded the Qwen path — a scanned
            # page silently vanished from the chapter text). PSM 6 (assume
            # a uniform block of text) and PSM 4 (single column of variable
            # sizes) recover the common failure shapes. An exception on the
            # first pass still propagates to the outer handler with the
            # original message (the V0.4.23 error contract).
            text = pytesseract.image_to_string(pil_image, lang="eng+fas")
            _recovered_with = ""
            if not (text and text.strip()):
                for _psm_cfg in ("--psm 6", "--psm 4"):
                    try:
                        text = pytesseract.image_to_string(
                            pil_image, lang="eng+fas", config=_psm_cfg
                        )
                    except Exception:
                        continue
                    if text and text.strip():
                        _recovered_with = _psm_cfg
                        break
            if text and text.strip():
                if _recovered_with:
                    self.log(
                        f"    ✅ Tesseract p.{page_num}: {len(text)} chars "
                        f"(recovered with '{_recovered_with}')",
                        "INFO",
                    )
                else:
                    self.log(f"    ✅ Tesseract p.{page_num}: {len(text)} chars", "INFO")
                return OcrResult(
                    page_num=page_num, text=text, success=True, engine_used=OcrEngine.TESSERACT
                )
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg="Tesseract returned empty string (3 page-segmentation modes tried)",
            )
        except Exception as e:
            return OcrResult(
                page_num=page_num,
                text="",
                success=False,
                engine_used=OcrEngine.TESSERACT,
                error_msg=str(e),
            )

    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def build_markdown(results: dict[int, OcrResult]) -> str:
        parts = []
        for page_num in sorted(results.keys()):
            r = results[page_num]
            text = (
                r.text
                if r.success and r.text.strip()
                else f"[Page {page_num}: content unavailable]"
            )
            parts.append(insert_page_number_comments(text, page_num))
        return "\n\n".join(parts)
