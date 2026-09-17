"""
Intelligent PDF analyzer.

FIX in this version:
  - Recommendation logic changed so that ANY scanned pages trigger HYBRID mode,
    not NO_OCR. Previously with 4/174 pages scanned (2.3%), the recommendation
    was NO_OCR which meant the cover (pages 1-2) and the introduction pages
    were never OCR'd, producing empty entries and missing the book's intro.

  New logic:
    >= 30% scanned  → LLM_OCR  (OCR every page)
     1–29% scanned  → HYBRID   (OCR only the scanned pages)
     0 scanned      → NO_OCR   (purely digital, skip OCR entirely)

  This ensures covers, charts, and any image-only pages are always processed
  through Qwen VL, regardless of how small a fraction of the book they are.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation
from utils.logging import get_main_logger

logger = get_main_logger()


class EmptyPdfError(ValueError):
    """Raised when a PDF has 0 extractable pages.

    A 0-page PDF is always pathological — either the file is corrupt, the
    decryption password is wrong, or pypdf failed to parse the page tree.
    Previously this flowed through and caused a ``ZeroDivisionError`` deep
    in the pipeline (e.g. ``scanned_ratio`` / ``total_pages`` or page-range
    arithmetic).  Now it fails fast with an actionable message.

    The converter's top-level ``except Exception`` in ``convert()`` catches
    this and surfaces ``str(e)`` to the UI via ``ConversionResult.error_msg``.
    """


class PdfAnalyzer:
    MIN_TEXT_CHARS    = 30
    SCANNED_THRESHOLD = 30
    LLM_OCR_THRESHOLD = 0.30   # >=30% scanned → OCR everything


    def __init__(self, password: str | None = None):
        self.password = password

    def _is_text_meaningful(self, text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) < self.SCANNED_THRESHOLD:
            word_pattern = re.compile(r'[A-Za-z\u0600-\u06FF]{2,}')
            words = word_pattern.findall(stripped)
            if len(words) < 2:
                return False
            if len(stripped) < self.MIN_TEXT_CHARS or (len(stripped) < 15 and stripped.isupper()):
                return False
        garbage = re.compile(r'([!@#$%^&*()_+=\-{}\[\]:;"\'<>?,./]{5,})')
        if garbage.search(text):
            if sum(len(m) for m in garbage.findall(text)) > len(text) * 0.3:
                return False
        return True

    def analyze_page(self, page, page_num: int) -> PageAnalysis:
        try:
            extracted_text = page.extract_text() or ""
        except Exception as e:
            logger.warning(f"Page {page_num}: text extraction failed: {e}")
            extracted_text = ""

        is_scanned = (
            not extracted_text.strip()
            or not self._is_text_meaningful(extracted_text)
        )
        preview = extracted_text[:200].replace('\n', ' ').strip()
        return PageAnalysis(
            page_num=page_num,
            is_scanned=is_scanned,
            extracted_text_preview=preview,
            recommended_action="ocr" if is_scanned else "skip",
        )

    def analyze(self, pdf_path: Path) -> PdfAnalysisResult:
        logger.info(f"Analyzing PDF: {pdf_path}")

        # V10.20.0: Check if docling is available for technical PDFs
        # (preserves tables + code blocks that markitdown mangles)
        self._docling_available = False
        try:
            import docling  # noqa: F401
            self._docling_available = True
            logger.info("Docling available — can use for technical PDF extraction")
        except ImportError:
            pass
        try:
            reader = PdfReader(str(pdf_path))
            if reader.is_encrypted:
                if self.password:
                    reader.decrypt(self.password)
                else:
                    logger.warning("PDF is encrypted but no password provided.")
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            raise

        total_pages  = len(reader.pages)

        # V10.4.0 (Phase 6A-1): Fail fast on 0-page PDFs.
        # A 0-page result is always pathological — corrupt file, wrong
        # decryption password, or a malformed page tree.  Letting it flow
        # through caused ZeroDivisionError deep in the pipeline (page-range
        # arithmetic, scanned_ratio, segmentation).  Now we raise a clear,
        # user-facing error that the converter surfaces via ConversionResult.
        if total_pages == 0:
            msg = (
                "This PDF contains 0 pages and cannot be converted. "
                "The file may be corrupt, empty, or password-protected "
                "with an incorrect password. Please verify the file opens "
                "in a regular PDF viewer and try again."
            )
            logger.error(msg)
            raise EmptyPdfError(msg)

        scanned_pages, text_pages, per_page = [], [], []

        for idx, page in enumerate(reader.pages, start=1):
            analysis = self.analyze_page(page, idx)
            per_page.append(analysis)
            if analysis.is_scanned:
                scanned_pages.append(idx)
            else:
                text_pages.append(idx)

        scanned_ratio = len(scanned_pages) / total_pages if total_pages > 0 else 0

        # FIX: three tiers instead of two
        #   >= 30%  → LLM_OCR  (all pages)
        #   1-29%   → HYBRID   (only the scanned pages — covers, charts, etc.)
        #    0%     → NO_OCR   (truly digital, nothing to OCR)
        if scanned_ratio >= self.LLM_OCR_THRESHOLD:
            recommendation = PdfRecommendation.LLM_OCR
        elif len(scanned_pages) > 0:
            recommendation = PdfRecommendation.HYBRID
        else:
            recommendation = PdfRecommendation.NO_OCR

        logger.info(
            f"PDF: {len(scanned_pages)} scanned / {len(text_pages)} text pages. "
            f"Ratio: {scanned_ratio:.1%}. Recommendation: {recommendation.value}"
        )
        return PdfAnalysisResult(
            total_pages=total_pages,
            scanned_pages=scanned_pages,
            text_pages=text_pages,
            recommendation=recommendation,
            per_page=per_page,
        )

    def get_pages_to_ocr(
        self,
        analysis: PdfAnalysisResult,
        user_override: PdfRecommendation | None = None,
    ) -> list[int]:
        effective = user_override if user_override is not None else analysis.recommendation
        if effective == PdfRecommendation.NO_OCR:
            return []
        elif effective == PdfRecommendation.LLM_OCR:
            return list(range(1, analysis.total_pages + 1))
        elif effective == PdfRecommendation.HYBRID:
            return analysis.scanned_pages
        return []
