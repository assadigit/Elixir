"""Unicode filename sanitization — handles zero-width joins and RTL marks.

Some PDF filenames contain Unicode characters that break filesystem
operations:
- Zero-width joiners (ZWJ, U+200D) — used in emoji sequences
- Zero-width non-joiners (ZWNJ, U+200C) — used in Persian/Arabic
- Left-to-right marks (LRM, U+200E) and RTL marks (RTL, U+200F)
- Byte order marks (BOM, U+FEFF)
- Soft hyphens (U+00AD)
- Various invisible Unicode characters

These are valid in filenames on most OSes but cause problems in:
- subprocess arguments (nvidia-smi, poppler, tesseract)
- shell commands
- cross-platform file copying
- logging output (invisible characters corrupt log parsing)
"""

from __future__ import annotations

import logging
import re
import unicodedata

# Invisible/problematic Unicode characters to strip

logger = logging.getLogger(__name__)

_INVISIBLE_CHARS = re.compile(
    "["
    "\u200b"  # zero-width space
    "\u200c"  # zero-width non-joiner (ZWNJ)
    "\u200d"  # zero-width joiner (ZWJ)
    "\u200e"  # left-to-right mark (LRM)
    "\u200f"  # right-to-left mark (RTL)
    "\ufeff"  # byte order mark (BOM)
    "\u00ad"  # soft hyphen
    "\u2060"  # word joiner
    "\u2061"  # function application
    "\u2062"  # invisible times
    "\u2063"  # invisible separator
    "\u2064"  # invisible plus
    "\u00a0"  # non-breaking space
    "]"
)

# Characters that are illegal in filenames on Windows
_WINDOWS_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize a filename for cross-platform safety.

    1. Strips invisible Unicode characters (ZWJ, ZWNJ, RTL marks, BOM, etc.)
    2. Replaces Windows-illegal characters with the replacement string
    3. Normalizes Unicode (NFC form)
    4. Trims leading/trailing whitespace and dots
    5. Limits length to 200 characters (for filesystem limits)
    """
    if not filename:
        return "unnamed"

    # 1. Strip invisible characters
    result = _INVISIBLE_CHARS.sub("", filename)

    # 2. Replace Windows-illegal characters
    result = _WINDOWS_ILLEGAL.sub(replacement, result)

    # 3. Normalize Unicode (NFC = composed form)
    result = unicodedata.normalize("NFC", result)

    # 4. Trim whitespace and dots (Windows doesn't allow trailing dots/spaces)
    result = result.strip().strip(".").strip()

    # 5. Limit length (keep extension if present)
    if len(result) > 200:
        # Try to preserve extension
        if "." in result:
            name, ext = result.rsplit(".", 1)
            result = name[: 200 - len(ext) - 1] + "." + ext
        else:
            result = result[:200]

    return result if result else "unnamed"


def sanitize_heading_for_filename(heading: str) -> str:
    """Sanitize a chapter heading for use as a filename component.

    More aggressive than sanitize_filename — also removes quotes,
    colons, and other punctuation that's technically legal but
    causes problems in log parsing.
    """
    if not heading:
        return "chapter"

    # Start with basic sanitization
    result = sanitize_filename(heading)

    # Remove additional problematic characters
    result = re.sub(r'["\'`' "]", "", result)
    result = re.sub(r"[:;]", "-", result)
    result = re.sub(r"\s+", "_", result)
    result = re.sub(r"_+", "_", result)  # collapse multiple underscores
    result = result.strip("_")

    return result if result else "chapter"
