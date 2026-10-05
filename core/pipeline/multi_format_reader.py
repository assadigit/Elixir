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


def _detect_encoding_with_chardet(raw: bytes) -> str | None:
    """V0.6.19 (W-e1): use chardet for high-confidence encoding detection
    when the strict cascade fails. chardet is an OPTIONAL dependency —
    if it's not in the rig's venv (some minimal installs don't have it),
    this function returns None and the caller falls back to the cascade.

    Why this matters: the V0.6.18 four-step cascade (utf-8-sig → utf-8 →
    cp1252 → latin-1) covers ~99.9% of Western files, but a .txt saved
    in a non-Western encoding (Big5 for Traditional Chinese, Shift-JIS
    for Japanese, GB18030 for Simplified Chinese, EUC-KR for Korean)
    would "successfully" decode in cp1252 as garbage (the bytes are
    mostly in 0x80-0xFF, all defined in cp1252) and never reach the
    latin-1 catch-all with the right encoding. chardet's byte-frequency
    heuristics catch these cases. The worklog's LOW priority item #6
    named this gap explicitly.

    The function is deliberately conservative: only return an encoding
    if chardet's confidence is >= 0.7 (its own threshold for "fairly
    sure"). Below that, the cascade is more reliable than a guess.
    """
    try:
        import chardet  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        result = chardet.detect(raw)
    except Exception:  # noqa: BLE001 — best-effort, never crash
        return None
    encoding = result.get("encoding")
    confidence = result.get("confidence", 0.0)
    if not encoding or confidence < 0.7:
        return None
    # Normalize: chardet returns e.g. "SHIFT_JIS" / "iso-8859-1" /
    # "Windows-1252"; Python's codecs accepts case-insensitive + the
    # common aliases, but normalize to lowercase for safety.
    encoding = encoding.lower()
    # Map a few chardet names to Python's preferred aliases (so the
    # decode step below doesn't raise LookupError on a name Python
    # doesn't recognize).
    _ALIAS = {
        "shift-jis": "shift_jis",
        "shiftjis": "shift_jis",
        "sjis": "shift_jis",
        "windows-1252": "cp1252",
        "iso-8859-1": "latin-1",
        "iso8859-1": "latin-1",
        "gb2312": "gb18030",  # gb18030 is a superset
        "gbk": "gb18030",  # gb18030 is a superset
        "euc-kr": "euc_kr",
        "euckr": "euc_kr",
        "euc-jp": "euc_jp",
        "eucjp": "euc_jp",
        "ascii": "utf-8",  # ASCII is a subset of UTF-8
    }
    return _ALIAS.get(encoding, encoding)


def _read_text_with_encoding_fallback(file_path: Path) -> str:
    """V0.6.19 (W-e1): read a plain-text file with encoding fallback.

    The pre-V0.6.18 path was ``file_path.read_text(encoding="utf-8",
    errors="ignore")`` which SILENTLY DROPPED every non-ASCII byte —
    smart quotes, em-dashes, accented Latin chars, the curly apostrophe
    in "it's", the en-dash in "1979–1985" — from any .txt saved by
    Windows Notepad in its default "ANSI" mode (cp1252 / Windows-1252).
    The operator's report named this gap explicitly:

        "cp1252-encoded .txt files fail to read (pre-existing; rare on
         modern systems)."

    V0.6.18 closed the Western gap with a four-step cascade (utf-8-sig
    → utf-8 → cp1252 → latin-1). V0.6.19 (W-e1) extends the cascade to
    cover the non-Western encodings the V0.6.18 worklog's LOW priority
    item #6 named (Big5, Shift-JIS, GB18030, EUC-KR), AND adds UTF-16 /
    UTF-32 BOM detection (Python's ``codecs`` recognizes the BOMs but
    the V0.6.18 cascade didn't try them), AND adds an OPTIONAL chardet
    detection step (high-confidence only — see
    ``_detect_encoding_with_chardet``) for genuinely ambiguous files.

    The full V0.6.19 cascade (first that decodes WITHOUT error wins):

      1. utf-8-sig       — UTF-8 with a BOM (Notepad's "UTF-8 with BOM").
      2. utf-16          — UTF-16 with a BOM (FF FE = LE, FE FF = BE).
      3. utf-32          — UTF-32 with a BOM (FF FE 00 00 = LE / 00 00 FE FF).
      4. utf-8           — the modern default; most .txt / .md / .rst.
      5. chardet (opt.)  — high-confidence detection (>=0.7); skips if
                           chardet not installed or confidence < 0.7.
      6. cp1252          — Windows-1252, Notepad's "ANSI" for Western
                           locales (the smart-quote / em-dash source).
      7. shift_jis       — Japanese (Shift-JIS; Windows codepage 932).
      8. euc_jp          — Japanese (EUC-JP; Unix-locale default).
      9. euc_kr          — Korean (EUC-KR; Unix-locale default).
     10. gb18030         — Simplified Chinese (superset of GBK/GB2312).
     11. big5            — Traditional Chinese (Taiwan / Hong Kong).
     12. latin-1         — ISO-8859-1; the catch-all that maps every
                           byte 0-255 (never raises, ``errors="replace"``).

    Order rationale: the STRICT encodings (utf-8, utf-16, utf-32 —
    they raise on the wrong byte patterns) are tried first; the
    PERMISSIVE encodings (cp1252 + the Asian ones — they decode most
    byte sequences without error) are tried in rough order of likelihood
    for the rig's locale (Western > Japanese > Korean > Chinese-
    Simplified > Chinese-Traditional); latin-1 is the catch-all.

    A genuine Western file stops at step 6 (cp1252); a genuine Japanese
    file stops at step 7 or 8 (its bytes are mostly in the 0x80-0xFF
    range, all defined in cp1252 — BUT the chardet step at 5 catches
    the high-confidence Japanese signature before reaching cp1252,
    which is the whole reason chardet is in the cascade).
    """
    raw = file_path.read_bytes()
    # 1. UTF-8 with BOM (utf-8-sig strips the BOM if present, and is a
    # strict superset of utf-8 for BOM-less files — but it RAISES on
    # invalid UTF-8 sequences, so we catch and fall through).
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    # 2-3. UTF-16 / UTF-32 — ONLY when the BOM is present at the start
    # of the byte stream. V0.6.19 first attempt tried them unconditionally
    # (raw.decode("utf-16") without a BOM) — that "succeeds" with GARBAGE
    # for any even-length ASCII file (utf-16 assumes native byte order
    # when no BOM, and decodes the bytes as garbage UTF-16-LE pairs).
    # The BOM bytes (UTF-32-LE = FF FE 00 00, UTF-32-BE = 00 00 FE FF,
    # UTF-16-LE = FF FE, UTF-16-BE = FE FF) are the ONLY reliable signal.
    # UTF-32 BOMs are checked FIRST because UTF-32-LE's BOM (FF FE 00 00)
    # is a 2-byte prefix of UTF-16-LE's BOM (FF FE) — checking UTF-16
    # first would mis-route a UTF-32 file to the UTF-16 decoder.
    if len(raw) >= 4 and raw[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        try:
            return raw.decode("utf-32")  # BOM picks the right endianness
        except (UnicodeDecodeError, UnicodeError):
            pass
    if len(raw) >= 2 and raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")  # BOM picks the right endianness
        except (UnicodeDecodeError, UnicodeError):
            pass
    # 4. UTF-8 (strict — the common modern case).
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # 5. chardet (OPTIONAL — high-confidence detection only). Skipped
    # silently if chardet isn't installed or its confidence < 0.7.
    _chardet_encoding = _detect_encoding_with_chardet(raw)
    if _chardet_encoding is not None:
        try:
            return raw.decode(_chardet_encoding)
        except (UnicodeDecodeError, LookupError, UnicodeError):
            pass  # chardet guessed wrong — fall through to the cascade
    # 6-10. The Asian encodings BEFORE cp1252 — the V0.6.18 order
    # (cp1252 first) produced GARBAGE for Asian files: cp1252 is
    # permissive (most bytes 0x80-0xFF are defined), so it "succeeds"
    # on a GB18030 / Big5 / EUC-KR file before the cascade reaches
    # the right encoding. Reversing the order is safe because the
    # Asian encodings are STRICTER about lead/trail byte pairs — a
    # typical Western cp1252 file (ASCII + smart quotes + em-dash +
    # accented Latin) has single high bytes that don't form valid
    # Asian 2-byte sequences, so the Asian encodings RAISE and the
    # cascade falls through to cp1252 (step 11). The rare cp1252 file
    # whose high bytes happen to form valid Asian pairs would be
    # mis-decoded as Asian garbage — acceptable: the operator can
    # re-save the file as UTF-8 to fix it (and modern Windows + the
    # app's own outputs are all UTF-8 already).
    for _asian_encoding in ("shift_jis", "euc_jp", "euc_kr", "gb18030", "big5"):
        try:
            return raw.decode(_asian_encoding)
        except (UnicodeDecodeError, LookupError, UnicodeError):
            pass
    # 11. cp1252 / Windows-1252 (Windows Notepad "ANSI" — the V0.6.18
    # bug source). Now the SAFETY-NET for Western files whose bytes
    # don't form valid Asian sequences (the typical case).
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        pass
    # 12. latin-1 / ISO-8859-1 — the catch-all (never raises).
    return raw.decode("latin-1", errors="replace")


def _extract_text_file(file_path: Path, log) -> tuple[str, int]:
    """Extract text from a plain text/markdown file.

    V0.6.18 (W-d4): routes through ``_read_text_with_encoding_fallback``
    so cp1252-encoded .txt files (Windows Notepad "ANSI" saves) decode
    correctly instead of silently losing their non-ASCII bytes.
    """
    log(f"  📝 Reading text file: {file_path.name}", "INFO")
    text = _read_text_with_encoding_fallback(file_path)
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
