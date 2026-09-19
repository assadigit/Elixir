"""V10.20.0: Multi-format input support — EPUB, DOCX, HTML, TXT.

Inspired by book-to-skill's multi-format extraction.  Previously the app
only accepted PDF; now it accepts:

  - PDF (existing — markitdown + OlmOCR)
  - EPUB (new — ebooklib + beautifulsoup4, or stdlib zipfile fallback)
  - DOCX (new — python-docx, or stdlib zipfile/XML fallback)
  - TXT/MD (new — direct read)
  - HTML (new — beautifulsoup4, or stdlib html.parser fallback)

All formats produce raw markdown text that feeds into the same pipeline
(postprocess → segment → summarize → outputs).

Usage (from the converter's extraction phase)::

    from core.pipeline.multi_format_reader import extract_text
    text, pages = extract_text(file_path, log_callback=log)
"""

from __future__ import annotations

import logging
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(
    file_path: Path,
    password: str | None = None,
    log_callback: Callable[[str, str], None] | None = None,
) -> tuple[str, int]:
    """Extract text from any supported file format.

    Args:
        file_path: path to the input file
        password: PDF password (optional, PDF only)
        log_callback: fn(message, level)

    Returns:
        (markdown_text, page_count) — the extracted text + estimated page count.
        For non-PDF formats, page_count is estimated (chars / 3000).
    """
    log = log_callback or (lambda msg, level="INFO": None)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_path, password, log)
    elif suffix == ".epub":
        return _extract_epub(file_path, log)
    elif suffix == ".docx":
        return _extract_docx(file_path, log)
    elif suffix in (".txt", ".md", ".rst", ".asciidoc", ".adoc"):
        return _extract_text_file(file_path, log)
    elif suffix in (".html", ".htm"):
        return _extract_html(file_path, log)
    else:
        # Try as text file
        log(f"  ⚠️ Unknown format '{suffix}' — trying as text file.", "WARNING")
        return _extract_text_file(file_path, log)


def _extract_pdf(file_path: Path, password: str | None, log) -> tuple[str, int]:
    """PDF extraction — delegates to the existing PdfAnalyzer + OCR pipeline.

    Returns a placeholder; the actual PDF extraction happens in the
    extraction phase (run_extraction).  This function is only called
    for non-PDF formats.
    """
    # PDF is handled by the main pipeline — this shouldn't be called.
    # Return empty (the caller should use the PDF pipeline instead).
    log("  ℹ️ PDF input detected — using main extraction pipeline.", "INFO")
    return "", 0


def _extract_epub(file_path: Path, log) -> tuple[str, int]:
    """Extract text from EPUB file.

    Uses ebooklib + beautifulsoup4 if available, falls back to stdlib zipfile.
    """
    log(f"  📖 Extracting EPUB: {file_path.name}", "INFO")

    try:
        import ebooklib
        from bs4 import BeautifulSoup
        from ebooklib import epub

        book = epub.read_epub(str(file_path), options={"ignore_ncx": True})
        chapters = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text and len(text) > 50:
                # Add page marker
                chapters.append(f"<!-- original page {len(chapters) + 1} -->\n{text}")

        text = "\n\n".join(chapters)
        page_count = max(1, len(text) // 3000)
        log(f"  ✅ EPUB: {len(chapters)} sections, ~{page_count} pages", "INFO")
        return text, page_count

    except ImportError:
        log("  ℹ️ EPUB: ebooklib not installed — using stdlib fallback.", "DEBUG")
        return _extract_epub_fallback(file_path, log)


def _extract_epub_fallback(file_path: Path, log) -> tuple[str, int]:
    """Fallback EPUB extraction using stdlib zipfile."""
    chapters = []
    with zipfile.ZipFile(str(file_path), "r") as zf:
        for name in zf.namelist():
            if name.endswith((".html", ".xhtml", ".htm")):
                content = zf.read(name).decode("utf-8", errors="ignore")
                # Strip HTML tags
                text = re.sub(r"<[^>]+>", " ", content)
                text = re.sub(r"\s+", " ", text).strip()
                if text and len(text) > 50:
                    chapters.append(f"<!-- original page {len(chapters) + 1} -->\n{text}")

    text = "\n\n".join(chapters)
    page_count = max(1, len(text) // 3000)
    log(f"  ✅ EPUB (fallback): {len(chapters)} sections, ~{page_count} pages", "INFO")
    return text, page_count


def _extract_docx(file_path: Path, log) -> tuple[str, int]:
    """Extract text from DOCX file.

    Uses python-docx if available, falls back to stdlib zipfile/XML.
    """
    log(f"  📄 Extracting DOCX: {file_path.name}", "INFO")

    try:
        import docx

        doc = docx.Document(str(file_path))
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                # Preserve heading structure
                if para.style and para.style.name.startswith("Heading"):
                    level = int(para.style.name.split()[-1]) if para.style.name[-1].isdigit() else 1
                    paragraphs.append(f"{'#' * level} {text}")
                else:
                    paragraphs.append(text)

        text = "\n\n".join(paragraphs)
        page_count = max(1, len(text) // 3000)
        log(f"  ✅ DOCX: {len(paragraphs)} paragraphs, ~{page_count} pages", "INFO")
        return text, page_count

    except ImportError:
        log("  ℹ️ DOCX: python-docx not installed — using stdlib fallback.", "DEBUG")
        return _extract_docx_fallback(file_path, log)


def _extract_docx_fallback(file_path: Path, log) -> tuple[str, int]:
    """Fallback DOCX extraction using stdlib zipfile/XML."""
    paragraphs = []
    with zipfile.ZipFile(str(file_path), "r") as zf:
        # Read word/document.xml
        if "word/document.xml" in zf.namelist():
            content = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            # Extract text from <w:t> tags
            # Split on paragraph breaks <w:p>
            para_texts = re.split(r"</w:p>", content)
            for para_xml in para_texts:
                para_text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para_xml))
                if para_text.strip():
                    paragraphs.append(para_text.strip())

    text = "\n\n".join(paragraphs)
    page_count = max(1, len(text) // 3000)
    log(f"  ✅ DOCX (fallback): {len(paragraphs)} paragraphs, ~{page_count} pages", "INFO")
    return text, page_count


def _extract_text_file(file_path: Path, log) -> tuple[str, int]:
    """Extract text from a plain text/markdown file."""
    log(f"  📝 Reading text file: {file_path.name}", "INFO")
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    page_count = max(1, len(text) // 3000)
    log(f"  ✅ Text: {len(text):,} chars, ~{page_count} pages", "INFO")
    return text, page_count


def _extract_html(file_path: Path, log) -> tuple[str, int]:
    """Extract text from an HTML file."""
    log(f"  🌐 Extracting HTML: {file_path.name}", "INFO")

    content = file_path.read_text(encoding="utf-8", errors="ignore")

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "html.parser")
        # Remove script/style tags
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    except ImportError:
        # Fallback: regex strip
        text = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

    page_count = max(1, len(text) // 3000)
    log(f"  ✅ HTML: {len(text):,} chars, ~{page_count} pages", "INFO")
    return text, page_count


def is_supported_format(file_path: Path) -> bool:
    """Check if the file format is supported."""
    return file_path.suffix.lower() in (
        ".pdf",
        ".epub",
        ".docx",
        ".txt",
        ".md",
        ".rst",
        ".asciidoc",
        ".adoc",
        ".html",
        ".htm",
    )
