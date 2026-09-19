"""Temporary file management and output folder creation."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from utils.filename import sanitize_filename

logger = logging.getLogger(__name__)


class TempFileManager:
    """Manages temporary files for a conversion session.

    V10.34.0 (Sprint 6.2): Added context-manager protocol (__enter__/__exit__)
    and __del__ so temp files are auto-cleaned even if the conversion crashes.
    Usage::

        with TempFileManager() as tfm:
            img_path = tfm.create_temp_file(".png")
            # ... use the temp file ...
        # __exit__ auto-cleans all registered files

    V10.34.0 (Sprint 6.3): The shared instance (get_shared_temp_manager())
    is used by core/ocr/service.py to register all OCR temp images so they
    are cleaned up at the end of the conversion, not leaked on disk.
    """

    # V10.34.0 (Sprint 6.3): shared instance for cross-module temp tracking.
    _shared: Optional["TempFileManager"] = None

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "elixir"
        self.base_dir.mkdir(exist_ok=True, parents=True)
        self.files: list[Path] = []
        self._cleaned = False

    def __enter__(self) -> "TempFileManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Auto-cleanup on context exit (even on exception)."""
        self.cleanup()

    def __del__(self) -> None:
        """Best-effort cleanup if the manager is garbage-collected without
        an explicit cleanup() call (e.g. on crash)."""
        try:
            if not self._cleaned:
                self.cleanup()
        except Exception:
            pass  # never crash in __del__

    def create_temp_file(self, suffix: str = ".tmp") -> Path:
        fd, path = tempfile.mkstemp(suffix=suffix, dir=self.base_dir)
        path = Path(path)
        self.files.append(path)
        return path

    def register(self, path: Path) -> None:
        """V10.34.0 (Sprint 6.3): Register an existing temp file for cleanup.

        Used by OCR service to register temp image files it creates via
        pdf2image (which doesn't go through create_temp_file).
        """
        self.files.append(Path(path))

    def cleanup(self) -> None:
        for p in self.files:
            try:
                if p.exists():
                    p.unlink()
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
        self.files.clear()
        self._cleaned = True

    def cleanup_all(self) -> None:
        self.cleanup()
        try:
            shutil.rmtree(self.base_dir, ignore_errors=True)
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)


def get_shared_temp_manager() -> TempFileManager:
    """V10.34.0 (Sprint 6.3): Return the shared TempFileManager instance.

    Used by OCR service + other phases to register temp files for central
    cleanup at the end of the conversion.
    """
    if TempFileManager._shared is None:
        TempFileManager._shared = TempFileManager()
    return TempFileManager._shared


def reset_shared_temp_manager() -> None:
    """V10.34.0 (Sprint 6.3): Clear the shared instance (for testing)."""
    if TempFileManager._shared is not None:
        TempFileManager._shared.cleanup()
        TempFileManager._shared = None


def create_output_folder(base_dir: Path, pdf_name: str, per_book: bool = True) -> Path:
    # V10.4.0 (Phase 6A-2): Sanitize the PDF-name-derived folder component.
    # ``pdf_name`` is typically ``request.input_path.stem`` — the user's PDF
    # filename without extension.  Persian/Arabic PDFs frequently contain
    # ZWNJ (U+200C) and RTL marks (U+200F) that are legal on the filesystem
    # but break subprocess args (nvidia-smi, poppler, tesseract), cross-OS
    # copy, and log parsing.  sanitize_filename() strips invisibles, NFC-
    # normalizes, removes Windows-illegal chars, and trims to 200 chars.
    pdf_name = sanitize_filename(pdf_name)
    if per_book:
        book_folder = base_dir / pdf_name
        book_folder.mkdir(parents=True, exist_ok=True)
        return book_folder
    else:
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir


def clean_temp_files(temp_dir: Path) -> None:
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)
