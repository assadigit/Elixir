"""V7.6.0 R4: Book title detection from PDF content.

The user's problem: a PDF named ``afsrf454.pdf`` should produce an output
folder named ``Black Swan`` (the actual book title), not ``Afsrf454``.

Strategy:
  1. If the PDF filename looks like a real book name (contains spaces or
     meaningful words, not just alphanumerics), use it as-is.
  2. Otherwise, scan the first ~80 lines of the extracted markdown for a
     title-like line:
     - The first ``# Heading`` (H1)
     - A short standalone line (< 80 chars, > 3 chars) that's Title Case
       or ALL CAPS, near the top of the document
  3. Sanitize the result for use as a folder name.

The detector is conservative: if it can't find a confident title, it falls
back to the PDF stem so the conversion never blocks on a guessing game.
"""

from __future__ import annotations

import logging
import re

# A "real" filename: contains at least one space OR is mostly letters.
# "Black_Swan.pdf" → stem "Black_Swan" → real (has underscore we replace).
# "afsrf454.pdf" → stem "afsrf454" → not real (7 letters + 3 digits, no spaces).

logger = logging.getLogger(__name__)


def _looks_like_real_name(stem: str) -> bool:
    """Return True if the PDF stem looks like a genuine book name."""
    # Replace underscores/hyphens with spaces for the check
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return False
    # Must have at least one space (multi-word) OR be a single word of 4+ alpha chars
    if " " in cleaned:
        # At least one word should be 3+ alpha chars
        words = cleaned.split()
        if any(len(w) >= 3 and w.isalpha() for w in words):
            return True
    # Single word: must be 4+ letters, not mixed with many digits
    if cleaned.isalpha() and len(cleaned) >= 4:
        return True
    # "BlackSwan" (camelCase) — check for mixed case without digits
    if cleaned.isalnum() and not cleaned.isdigit() and any(c.isupper() for c in cleaned[1:]):
        # camelCase: has an uppercase letter after the first char
        alpha_ratio = sum(1 for c in cleaned if c.isalpha()) / len(cleaned)
        if alpha_ratio > 0.7:
            return True
    return False


def _sanitize_title_for_folder(title: str) -> str:
    """Make a title safe for use as a folder/file name."""
    # Remove filesystem-illegal chars
    safe = re.sub(r'[\\/:*?"<>|]', "", title)
    # Collapse whitespace
    safe = re.sub(r"\s+", " ", safe).strip()
    # Truncate to reasonable length
    safe = safe[:80]
    return safe


def _scan_markdown_for_title(raw_markdown: str) -> str | None:
    """Scan the first ~80 lines of markdown for a title-like line.

    Looks for (in priority order):
      1. The first ``# H1 heading`` (most reliable — TOC/cover pages often
         have the book title as H1)
      2. A short standalone line (< 80 chars, > 3 chars) in Title Case or
         ALL CAPS, appearing in the first 20 non-empty lines

    Returns None if nothing confident is found.
    """
    lines = raw_markdown.splitlines()
    # Look at first 80 lines max
    head = lines[:80]

    # 1. First H1 heading
    for line in head:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            # Sanity: must be 3-80 chars, not a generic word like "Contents"
            if 3 <= len(title) <= 80 and title.lower() not in (
                "contents",
                "table of contents",
                "index",
                "preface",
                "introduction",
                "chapter",
                "chapter 1",
            ):
                return title

    # 2. Short Title Case / ALL CAPS line in first 20 non-empty lines
    non_empty = [line.strip() for line in head if line.strip()]
    for line in non_empty[:20]:
        # Skip lines that are clearly not titles
        if len(line) > 80 or len(line) < 3:
            continue
        # Skip lines with sentence-ending punctuation (titles don't end with .)
        if line.endswith((".", ",", ";", ":", "!", "?")):
            continue
        # Skip lines that start with common non-title markers
        if line.startswith(("-", "*", "•", "|", ">", "#")):
            continue
        # Skip lines that are mostly digits
        alpha_chars = sum(1 for c in line if c.isalpha())
        if alpha_chars < len(line) * 0.5:
            continue
        # Title Case check: most words start with uppercase
        words = line.split()
        if len(words) >= 1:
            title_case_words = sum(1 for w in words if w and w[0].isupper())
            if title_case_words >= len(words) * 0.6 and len(words) <= 12:
                return line
        # ALL CAPS check (at least 4 chars, all alpha uppercase)
        if len(line) >= 4 and line.replace(" ", "").isalpha() and line.isupper():
            return line.title()  # Convert to Title Case for nicer folder name

    return None


def detect_book_title(
    pdf_stem: str,
    raw_markdown: str = "",
    log_callback=None,
) -> str:
    """Detect the best book title for folder naming.

    Args:
        pdf_stem: the PDF filename without extension (e.g., "afsrf454").
        raw_markdown: the first-pass extracted markdown (may be empty during
            early init — in that case we fall back to the stem).
        log_callback: optional ``fn(msg, level)`` for diagnostics.

    Returns:
        A sanitized title string suitable for folder/file naming.
    """
    log = log_callback or (lambda msg, level: None)

    # Step 1: if the PDF stem looks like a real name, use it (cleaned up).
    stem_cleaned = pdf_stem.replace("_", " ").replace("-", " ").strip()
    if _looks_like_real_name(pdf_stem):
        title = stem_cleaned.title() if " " in stem_cleaned else stem_cleaned
        title = _sanitize_title_for_folder(title)
        log(f"  📖 Book title: using PDF filename ({title})", "DEBUG")
        return title

    # Step 2: scan the markdown content for a title.
    if raw_markdown:
        detected = _scan_markdown_for_title(raw_markdown)
        if detected:
            title = _sanitize_title_for_folder(detected)
            log(
                f"  📖 Book title: detected from content ({title}) "
                f"— PDF stem '{pdf_stem}' looked like a hash",
                "INFO",
            )
            return title

    # Step 3: fallback — use the stem, cleaned up.
    title = _sanitize_title_for_folder(stem_cleaned.title() if stem_cleaned else pdf_stem)
    log(
        f"  📖 Book title: using PDF stem as fallback ({title}) — could not detect from content",
        "DEBUG",
    )
    return title
