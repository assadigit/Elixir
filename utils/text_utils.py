"""Text processing utilities: Persian detection, page comments, space fixing, etc."""

import logging
import re

logger = logging.getLogger(__name__)
PERSIAN_UNICODE_RANGE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def detect_persian_text(text: str, threshold: float = 0.05) -> bool:
    """Return True if proportion of Persian/Arabic characters exceeds threshold."""
    if not text:
        return False
    total = len(text)
    if total == 0:
        return False
    persian_chars = len(PERSIAN_UNICODE_RANGE.findall(text))
    return (persian_chars / total) > threshold


def remove_page_number_headings(text: str) -> str:
    """Remove lines like '## Page 1' or '# Page 1' or '## 1'."""
    text = re.sub(r"^#+\s+Page\s+\d+\s*$\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s+\d+\s*$\n?", "", text, flags=re.MULTILINE)
    return text


def convert_separators_to_comments(text: str) -> str:
    """Replace legacy '--- page ---' with HTML comment."""
    return re.sub(r"--- page ---", "<!-- page break -->", text)


def insert_page_number_comments(text: str, page_num: int) -> str:
    """Insert HTML comment at beginning of text indicating original page number."""
    return f"<!-- original page {page_num} -->\n{text}"


def optimize_for_tokens(text: str, token_saver: bool = True) -> str:
    """Remove excessive blank lines, trailing spaces, normalise list markers."""
    if not token_saver:
        return text
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*)[*+•]\s+", r"\1- ", text, flags=re.MULTILINE)
    return text


def fix_missing_spaces(text: str, fix_spaces: bool, wordninja_available: bool) -> str:
    """Attempt to split run-together words (English only). Skip Persian text."""
    if not fix_spaces or not wordninja_available:
        return text
    if detect_persian_text(text):
        return text
    try:
        import wordninja

        pattern = re.compile(r"\b[a-z]{10,}\b")

        def split_match(m):
            w = m.group(0)
            spl = wordninja.split(w)
            return " ".join(spl) if len(spl) > 1 else w

        return pattern.sub(split_match, text)
    except ImportError:
        return text
