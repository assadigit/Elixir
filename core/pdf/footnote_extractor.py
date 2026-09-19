"""V3.9.0 Footnote/Endnote Extraction.

Detects footnotes (bottom-of-page notes) and endnotes (end-of-chapter/book notes)
and extracts them separately from the main text. This prevents footnotes from
being interleaved with body text in wrong positions.

Detection strategies:
1. Superscript numbers in text → match with bottom-of-page text
2. Lines starting with a number followed by a period at the bottom of pages
3. "Notes" or "Endnotes" sections at the end of chapters
"""

from __future__ import annotations

import logging
import re

# Patterns for footnote markers in text (superscript-like numbers)

logger = logging.getLogger(__name__)

_FOOTNOTE_MARKER = re.compile(r"(\d{1,3})\s")  # number followed by space

# Pattern for footnote definitions at bottom of page
_FOOTNOTE_DEF = re.compile(r"^(\d{1,3})[\.\)]\s+(.{10,500})", re.MULTILINE)

# Pattern for endnotes section
_ENDNOTES_SECTION = re.compile(
    r"(?:^|\n)#{0,3}\s*(?:Notes|Endnotes|Footnotes)\s*\n", re.IGNORECASE | re.MULTILINE
)


def extract_footnotes(text: str, page_markers: list | None = None) -> dict:
    """V3.9.0: Extract footnotes from text.

    Args:
        text: The full markdown text with page markers
        page_markers: Optional list of (char_offset, page_num) tuples

    Returns dict with:
    - footnotes: List of {number, text, page} dicts
    - cleaned_text: Text with footnote definitions removed from body
    - endnotes: List of endnote strings (from Notes/Endnotes section)
    """
    footnotes = []
    endnotes = []
    cleaned_text = text

    # 1. Extract endnotes section (if exists)
    endnotes_match = _ENDNOTES_SECTION.search(text)
    if endnotes_match:
        endnotes_text = text[endnotes_match.end() :]
        # Split into individual endnotes
        for m in _FOOTNOTE_DEF.finditer(endnotes_text):
            endnotes.append(
                {
                    "number": int(m.group(1)),
                    "text": m.group(2).strip(),
                    "type": "endnote",
                }
            )
        # Remove endnotes section from cleaned text
        cleaned_text = text[: endnotes_match.start()].rstrip()

    # 2. Extract inline footnotes (bottom-of-page patterns)
    # Look for patterns like "1. Some footnote text." that appear after page markers
    pages = re.split(r"(<!--\s*Page\s+\d+\s*-->)", cleaned_text)
    cleaned_parts = []

    for _i, part in enumerate(pages):
        if re.match(r"<!--\s*Page\s+\d+\s*-->", part):
            cleaned_parts.append(part)
            continue

        # In each page's text, look for footnote definitions at the bottom
        lines = part.splitlines()
        if len(lines) < 3:
            cleaned_parts.append(part)
            continue

        # Check the last 5 lines for footnote patterns
        bottom_lines = lines[-5:]
        footnote_lines = []
        body_lines = lines[:-5] if len(lines) > 5 else []

        for line in bottom_lines:
            m = _FOOTNOTE_DEF.match(line.strip())
            if m:
                footnote_lines.append(
                    {
                        "number": int(m.group(1)),
                        "text": m.group(2).strip(),
                        "type": "footnote",
                    }
                )
            else:
                body_lines.append(line)

        footnotes.extend(footnote_lines)
        cleaned_parts.append("\n".join(body_lines))

    cleaned_text = "".join(cleaned_parts)

    return {
        "footnotes": footnotes,
        "endnotes": endnotes,
        "cleaned_text": cleaned_text,
        "total_notes": len(footnotes) + len(endnotes),
    }


def format_footnotes_for_summary(footnotes: list[dict], endnotes: list[dict]) -> str:
    """Format footnotes/endnotes as markdown for inclusion in summary."""
    if not footnotes and not endnotes:
        return ""

    parts = ["### Footnotes & Endnotes\n"]
    for fn in footnotes:
        parts.append(f"[^{fn['number']}]: {fn['text']}\n")
    for en in endnotes:
        parts.append(f"[^{en['number']}]: {en['text']}\n")

    return "\n".join(parts)
