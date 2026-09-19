"""Abstract base class for all OCR engines."""

import logging
from abc import ABC, abstractmethod

from core.models import OcrResult

logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """Base interface for OCR engines."""

    @abstractmethod
    def process_page(self, page, page_num: int) -> OcrResult:
        """
        Process a single PDF page and return extracted text.
        Args:
            page: pypdf PageObject
            page_num: 1-based page number
        Returns:
            OcrResult with text, success flag, and engine info
        """

    @abstractmethod
    def engine_name(self) -> str:
        """Return human-readable engine name."""
