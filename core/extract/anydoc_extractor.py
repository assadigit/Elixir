"""V15.0.0: AnyDoc extractor — isolated document → Markdown conversion.

This module is ONLY used by the "Document → Markdown" tool in the
QuickConvertDialog.  It does NOT touch the main conversion pipeline
(which uses markitdown + OlmOCR exactly as V13.45.5).

AnyDoc is a fast document-to-markdown converter with proper heading,
table, and formatting preservation for a wide range of office document
formats:

    PDF, DOCX, DOC, EPUB, PPTX, PPT, XLSX, XLS, ODT, ODS, ODP, RTF, CSV,
    PPTM, PPSX, PPSM, DOCM, XLSM, XLSB, PPS, POT

For PDFs, AnyDoc uses pdfminer/pypdf under the hood.  If the PDF is
malformed (truncated xref, broken objects), we repair it with pikepdf
before retrying — this rescues many "corrupt" PDFs that would otherwise
fail silently.

Public API
----------
- ``is_anydoc_available()``           — True if ``import anydoc`` works
- ``extract_with_anydoc(path, log)``  — returns ``(markdown, page_count)``
- ``ANYDOC_EXTENSIONS``               — set of supported extensions
- ``MARKITDOWN_EXTENSIONS``           — set of markitdown extensions (for
                                        format validation in the dropdown)
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None] | None

# ── Supported extensions (per V15 blueprint) ───────────────────────────────
# AnyDoc: office-document formats with rich structure (headings, tables).
ANYDOC_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".doc",
        ".epub",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
        ".odt",
        ".ods",
        ".odp",
        ".rtf",
        ".csv",
        ".pptm",
        ".ppsx",
        ".ppsm",
        ".docm",
        ".xlsm",
        ".xlsb",
        ".pps",
        ".pot",
    }
)

# markitdown: a different (broader, but differently-shaped) set of formats.
# Used by the fallback engine and for format-compatibility validation in
# the QuickConvertDialog engine dropdown.
MARKITDOWN_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".xml",
        ".epub",
        ".ipynb",
        ".jpg",
        ".jpeg",
        ".png",
        ".mp3",
        ".wav",
        ".txt",
        ".md",
    }
)


def is_anydoc_available() -> bool:
    """Return True if the ``anydoc`` package can be imported.

    Callers should check this before calling ``extract_with_anydoc()`` so
    they can show a helpful "AnyDoc not installed" message or fall back
    to the markitdown engine.
    """
    try:
        import anydoc  # noqa: F401

        return True
    except ImportError:
        return False
    except Exception:
        # Some packages raise exotic errors on import (missing native deps,
        # DLL load failures, etc.).  Treat them all as "not available".
        return False


def is_pikepdf_available() -> bool:
    """Return True if ``pikepdf`` is importable (used for PDF repair)."""
    try:
        import pikepdf  # noqa: F401

        return True
    except ImportError:
        return False
    except Exception:
        return False


def _log(log_callback: LogCallback, msg: str, level: str = "INFO") -> None:
    """Send a message to the optional callback AND the logger."""
    if log_callback:
        try:
            log_callback(msg)
        except Exception:
            pass
    if level == "WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)


# ── PDF repair ─────────────────────────────────────────────────────────────


def _repair_pdf_with_pikepdf(src_path: str) -> str | None:
    """Attempt to repair a malformed PDF using pikepdf.

    Writes the repaired copy to a temp file and returns its path, or
    ``None`` if pikepdf isn't installed or the repair itself failed.
    The caller is responsible for unlinking the temp file.
    """
    try:
        import pikepdf
    except ImportError:
        return None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="anydoc_repair_")
        os.close(tmp_fd)
        # Opening with pikepdf already performs a degree of repair on read;
        # saving then rewrites a clean, spec-compliant PDF.
        with pikepdf.open(src_path, allow_overwriting_input=False) as pdf:
            pdf.save(tmp_path)
        return tmp_path
    except Exception as exc:
        logger.warning(
            "pikepdf repair failed for %s: %s: %s",
            src_path,
            type(exc).__name__,
            exc,
        )
        return None


def _is_malformed_pdf_error(exc: BaseException) -> bool:
    """Heuristic: does this exception look like a malformed-PDF error?

    We look at both the exception class name and its message for the
    typical markers: ``MalformedError``, ``xref``, ``trailer``,
    ``parseerror``, ``syntax``, ``eof``.
    """
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    keywords = (
        "malformed",
        "xref",
        "trailer",
        "parseerror",
        "parse_error",
        "syntax",
        "eof",
        "unexpected eof",
        "invalid pdf",
    )
    blob = f"{name} {msg}"
    return any(kw in blob for kw in keywords)


# ── Core extraction ────────────────────────────────────────────────────────


def _count_page_markers(text: str) -> int:
    """Best-effort page count from ``<!-- page N -->`` markers."""
    return len(re.findall(r"<!--\s*page\s+\d+\s*-->", text))


def _coerce_page_count(value, text: str) -> int:
    """Normalise a best-effort page count to a non-negative int."""
    try:
        n = int(value)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass
    return _count_page_markers(text)


def _try_anydoc_extract(path: str, log_callback: LogCallback) -> tuple[str, int]:
    """Call anydoc to convert ``path`` → markdown.  Raises on failure.

    Tries the common anydoc API surface in order:
      1. ``anydoc.to_markdown(path)``
      2. ``anydoc.convert(path)`` (returns str / tuple / dict)
      3. ``anydoc.Document(path).to_markdown()``

    Returns ``(markdown, page_count)``.  ``page_count`` is best-effort
    (0 if AnyDoc doesn't report it).
    """
    import anydoc

    md_text = None
    page_count = 0

    # API attempt 1: anydoc.to_markdown(path) -> str
    if hasattr(anydoc, "to_markdown") and callable(anydoc.to_markdown):
        _log(log_callback, "AnyDoc: calling anydoc.to_markdown()")
        result = anydoc.to_markdown(str(path))
        if isinstance(result, tuple):
            md_text = result[0] if result else ""
            page_count = result[1] if len(result) > 1 else 0
        elif isinstance(result, dict):
            md_text = result.get("markdown") or result.get("text") or result.get("content")
            page_count = result.get("pages") or result.get("page_count") or 0
        else:
            md_text = result
    # API attempt 2: anydoc.convert(path) -> str / tuple / dict
    elif hasattr(anydoc, "convert") and callable(anydoc.convert):
        _log(log_callback, "AnyDoc: calling anydoc.convert()")
        result = anydoc.convert(str(path))
        if isinstance(result, tuple):
            md_text = result[0] if result else ""
            page_count = result[1] if len(result) > 1 else 0
        elif isinstance(result, dict):
            md_text = result.get("markdown") or result.get("text") or result.get("content")
            page_count = result.get("pages") or result.get("page_count") or 0
        else:
            md_text = result
    # API attempt 3: anydoc.Document(path).to_markdown()
    elif hasattr(anydoc, "Document"):
        _log(log_callback, "AnyDoc: calling anydoc.Document().to_markdown()")
        doc = anydoc.Document(str(path))
        if hasattr(doc, "to_markdown") and callable(doc.to_markdown):
            md_text = doc.to_markdown()
        elif hasattr(doc, "extract") and callable(doc.extract):
            md_text = doc.extract()
        else:
            md_text = str(doc)
        page_count = (
            getattr(doc, "page_count", None)
            or getattr(doc, "num_pages", None)
            or getattr(doc, "pages", None)
            or 0
        )

    if md_text is None:
        public_attrs = [a for a in dir(anydoc) if not a.startswith("_")]
        raise RuntimeError(
            f"anydoc module loaded but has no usable API "
            f"(checked to_markdown / convert / Document). "
            f"Available attrs: {public_attrs[:12]}"
        )

    md_str = str(md_text)
    if not md_str.strip():
        raise RuntimeError(
            "AnyDoc returned empty content — the document may be empty, "
            "scanned (image-only), or in an unsupported sub-format."
        )

    return md_str, _coerce_page_count(page_count, md_str)


def extract_with_anydoc(
    file_path: str,
    log_callback: LogCallback = None,
) -> tuple[str, int]:
    """Convert a document to Markdown using AnyDoc.

    Parameters
    ----------
    file_path:
        Path to the input document (PDF/DOCX/EPUB/PPTX/XLSX/RTF/CSV/...).
        Must exist on disk.
    log_callback:
        Optional ``callable(str)`` invoked with human-readable progress
        messages (used by the QuickConvertDialog status line).

    Returns
    -------
    (markdown, page_count)
        ``markdown`` is the extracted text as a string.
        ``page_count`` is a best-effort page count (0 if unknown — e.g.
        for DOCX/XLSX which have no natural "page" concept).

    Raises
    ------
    FileNotFoundError:
        ``file_path`` does not exist.
    ImportError:
        ``anydoc`` is not installed.  Callers should check
        :func:`is_anydoc_available` first, or catch this and fall back
        to the markitdown engine.
    RuntimeError:
        AnyDoc loaded but produced no content, OR a PDF was malformed
        and could not be repaired.
    Exception:
        Any other error from the underlying anydoc / pdfminer stack.
    """
    if not file_path:
        raise FileNotFoundError("Empty file path")
    if not Path(file_path).exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    ext = Path(file_path).suffix.lower()
    name = Path(file_path).name
    _log(log_callback, f"AnyDoc: extracting {name} ({ext or 'no-ext'})…")

    # ── PDF: malformed → repair → retry ───────────────────────────────
    if ext == ".pdf":
        try:
            return _try_anydoc_extract(file_path, log_callback)
        except Exception as first_err:
            if not _is_malformed_pdf_error(first_err):
                # Genuine failure (encrypted, permission-denied, etc.) —
                # don't attempt repair, propagate.
                raise
            _log(
                log_callback,
                f"AnyDoc: PDF appears malformed ({type(first_err).__name__}) — "
                f"attempting pikepdf repair…",
                "WARNING",
            )
            if not is_pikepdf_available():
                raise RuntimeError(
                    "PDF is malformed and pikepdf is not installed. "
                    "Install pikepdf (`pip install pikepdf`) to enable "
                    "automatic PDF repair, or use the markitdown engine."
                ) from first_err
            repaired = _repair_pdf_with_pikepdf(file_path)
            if not repaired:
                raise RuntimeError(
                    f"PDF is malformed and pikepdf could not repair it. Original error: {first_err}"
                ) from first_err
            try:
                _log(log_callback, "AnyDoc: retrying on repaired PDF…")
                md, pages = _try_anydoc_extract(repaired, log_callback)
                _log(log_callback, "AnyDoc: repaired-PDF extraction succeeded.")
                return md, pages
            finally:
                try:
                    os.unlink(repaired)
                except OSError:
                    pass

    # ── Non-PDF: direct call ──────────────────────────────────────────
    return _try_anydoc_extract(file_path, log_callback)


__all__ = [
    "ANYDOC_EXTENSIONS",
    "MARKITDOWN_EXTENSIONS",
    "is_anydoc_available",
    "is_pikepdf_available",
    "extract_with_anydoc",
]
