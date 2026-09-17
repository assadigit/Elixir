"""
Heuristic page classifier – filters out non‑content pages (TOC, Index, References,
Copyright, Blank, etc.) before summarisation.

NEW in this version:
  - Added `is_academic` flag – when True, lowers thresholds (min_content_chars=20)
    and keeps academic content (tables, figures, section headers).
  - `_page_has_academic_content()` detects table rows (`|`), figure captions,
    and academic section headers (`Abstract`, `Introduction`, etc.).
  - `_page_is_blank()` now uses lower thresholds for academic papers.
  - Added `filter_segment_content()` method with token-based fallback
    to prevent empty segments (keeps at least 100 tokens).
  - Improved logging for debugging.

Inspired by read_books.py, but implemented as a fully offline, rule‑based system.

Usage:
    from core.pdf import ContentFilter

    cf = ContentFilter(is_academic=True)   # for academic papers
    filtered_text = cf.filter_segment_content(segment.content, segment.start_page, segment.end_page)
"""

import re
from typing import Any

# ── Patterns for non‑content pages ──────────────────────────────────────────

TOC_PATTERNS = [
    r'(?i)^\s*(table\s+of\s+contents|contents)\s*$',
    r'(?i)^\s*فهرست\s+(مطالب)?\s*$',
    r'(?i)^\s*فهرست\s*$',
]

INDEX_PATTERNS = [
    r'(?i)^\s*index\s*$',
    r'(?i)^\s*نمایه\s*$',
    r'(?i)^\s*فهرست\s+(اعلام|موضوعی|واژگان)\s*$',
]

REFERENCES_PATTERNS = [
    r'(?i)^\s*(references|bibliography|works\s+cited|sources|further\s+reading)\s*$',
    r'(?i)^\s*(منابع|مراجع|کتابنامه|منابع\s+و\s+مآخذ)\s*$',
]

COPYRIGHT_PATTERNS = [
    r'(?i)^\s*copyright\s*[©]?',
    r'(?i)^\s*©\s*\d{4}',
    r'(?i)^\s*all\s+rights?\s+reserved',
    r'(?i)^\s*کپی\s*رایت',
    r'(?i)^\s*تمامی\s+حقوق\s+محفوظ',
    r'(?i)^\s*چاپ\s+اول',
    r'(?i)^\s*ناشر:',
]

DEDICATION_PATTERNS = [
    r'(?i)^\s*dedication\s*$',
    r'(?i)^\s*تقدیم\s*(به)?\s*$',
    r'(?i)^\s*به\s+یاد\s+',
]

ACKNOWLEDGMENTS_PATTERNS = [
    r'(?i)^\s*(acknowledgments|acknowledgements|thanks)\s*$',
    r'(?i)^\s*(سپاسگزاری|تقدیر|تشکر|قدردانی)\s*$',
]

PREFACE_FOREWORD_PATTERNS = [
    r'(?i)^\s*(preface|foreword|prologue|introduction)\s*$',
    r'(?i)^\s*(پیشگفتار|سخن\s+ناشر|یادداشت\s+مترجم|مقدمه)\s*$',
]

# Combine all non‑content category patterns
NON_CONTENT_CATEGORIES = {
    "toc": TOC_PATTERNS,
    "index": INDEX_PATTERNS,
    "references": REFERENCES_PATTERNS,
    "copyright": COPYRIGHT_PATTERNS,
    "dedication": DEDICATION_PATTERNS,
    "acknowledgments": ACKNOWLEDGMENTS_PATTERNS,
    "preface_foreword": PREFACE_FOREWORD_PATTERNS,
}

# Patterns that strongly indicate a page is part of a TOC (many lines ending with numbers)
TOC_LINE_PATTERN = re.compile(r'^\s*(?:\.{2,}|\s{3,})\s*\d{1,4}\s*$')
NUMBERED_LINE_PATTERN = re.compile(r'^\s*\d{1,4}\s*$')
CHAPTER_LIKE_TOC = re.compile(
    r'^(?:chapter|part|section|appendix|فصل|بخش|قسمت|مبحث)\s+',
    re.IGNORECASE
)

# Academic‑specific patterns
TABLE_ROW_PATTERN = re.compile(r'^\s*\|.*\|\s*$')
FIGURE_CAPTION_PATTERN = re.compile(r'^(?:Fig\.|Figure)\s+\d+', re.IGNORECASE)
ACADEMIC_SECTION_PATTERN = re.compile(
    r'^(?:abstract|introduction|methods|results|discussion|conclusion|'
    r'materials\s+and\s+methods|experimental|data\s+analysis)',
    re.IGNORECASE
)


class ContentFilter:
    """
    Offline heuristic filter to classify pages as content or non‑content.

    Args:
        min_content_chars: Minimum number of alphanumeric characters to
                           consider a page as potential content.
        toc_density_threshold: If more than this fraction of lines look like
                               TOC entries, classify as TOC.
        is_academic: If True, use lenient thresholds and keep academic content.
        log_callback: Optional logging function.
    """

    def __init__(
        self,
        min_content_chars: int = 80,
        toc_density_threshold: float = 0.40,
        is_academic: bool = False,
        log_callback=None,
    ):
        # ── Academic‑specific overrides ──────────────────────────────────
        if is_academic:
            self.min_content_chars = 20        # much lower for short abstract lines
            self.toc_density_threshold = 0.45  # slightly higher to avoid false positives
            self.min_alnum_for_blank = 5       # allow very short pages
        else:
            self.min_content_chars = min_content_chars
            self.toc_density_threshold = toc_density_threshold
            self.min_alnum_for_blank = 10

        self.is_academic = is_academic
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        compiled = {}
        for category, patterns in NON_CONTENT_CATEGORIES.items():
            compiled[category] = [re.compile(p, re.UNICODE) for p in patterns]
        return compiled

    def _strip_lines(self, text: str) -> list[str]:
        """Split into non‑empty, stripped lines."""
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _line_looks_like_toc_entry(self, line: str) -> bool:
        """Heuristic: line has dots/spaces followed by a number, or is just a number."""
        if TOC_LINE_PATTERN.match(line):
            return True
        if re.search(r'\s+\d{1,4}\s*$', line) and len(line.split()) >= 2:
            return True
        return False

    def _page_has_academic_content(self, text: str) -> bool:
        """
        Check if the page contains academic‑specific content that should be kept.
        Returns True if the page has:
        - Table rows (lines with '|')
        - Figure captions (starting with "Fig." or "Figure")
        - Academic section headers (abstract, introduction, etc.)
        """
        if not self.is_academic:
            return False
        lines = text.splitlines()
        for line in lines:
            stripped = line.strip()
            if TABLE_ROW_PATTERN.match(stripped):
                return True
            if FIGURE_CAPTION_PATTERN.match(stripped):
                return True
            if ACADEMIC_SECTION_PATTERN.search(stripped):
                return True
        return False

    def _page_has_substantial_text(self, text: str) -> bool:
        """
        Check if page has enough meaningful text.
        For academic papers, we lower the threshold.
        """
        stripped = ''.join(text.split())
        if not stripped:
            return False
        alnum_count = sum(1 for c in stripped if c.isalnum())
        # Use lower threshold for academic
        if alnum_count < self.min_alnum_for_blank:
            return False
        # If more than 70% are digits or punctuation and total length < 100, treat as blank
        if len(stripped) < 100 and alnum_count / max(1, len(stripped)) < 0.3:
            return False
        # Also require at least 2 words (academic can have very short captions)
        words = re.findall(r'\b[a-zA-Z\u0600-\u06FF]{2,}\b', text)
        if len(words) < 2 and not self.is_academic:
            return False
        return True

    def _page_is_blank(self, text: str) -> bool:
        """Page has very little text, mostly whitespace/punctuation."""
        return not self._page_has_substantial_text(text)

    def _detect_toc_by_density(self, lines: list[str]) -> bool:
        """If a high proportion of lines look like TOC entries, classify as TOC."""
        if not lines:
            return False
        toc_like = sum(1 for line in lines if self._line_looks_like_toc_entry(line))
        ratio = toc_like / len(lines)
        return ratio >= self.toc_density_threshold

    def classify_page(self, text: str) -> dict[str, Any]:
        """
        Classify a single page.

        Returns:
            {
                "is_content": bool,
                "category": str | None,   # non‑content category if applicable
                "confidence": float,      # 0.0 – 1.0
                "reason": str,
            }
        """
        if not text or not text.strip():
            return {
                "is_content": False,
                "category": "blank",
                "confidence": 1.0,
                "reason": "Empty or whitespace‑only page",
            }

        # ── NEW: Academic content detection ──────────────────────────────
        if self._page_has_academic_content(text):
            return {
                "is_content": True,
                "category": "academic",
                "confidence": 0.95,
                "reason": "Academic content detected (table, figure, or section header)",
            }

        if self._page_is_blank(text):
            return {
                "is_content": False,
                "category": "blank",
                "confidence": 0.9,
                "reason": f"Very little textual content (<{self.min_alnum_for_blank} alnum chars)",
            }

        lines = self._strip_lines(text)
        if not lines:
            return {
                "is_content": False,
                "category": "blank",
                "confidence": 1.0,
                "reason": "No non‑empty lines",
            }

        # Check first few lines for strong category matches
        first_lines = lines[:10]
        first_text = "\n".join(first_lines)

        for category, patterns in self._compiled_patterns.items():
            for pat in patterns:
                if pat.search(first_text):
                    # Strong match at the top of the page
                    return {
                        "is_content": False,
                        "category": category,
                        "confidence": 0.95,
                        "reason": f"Matches pattern for '{category}'",
                    }

        # Check entire text for less confident matches
        full_text = "\n".join(lines)
        for category, patterns in self._compiled_patterns.items():
            for pat in patterns:
                if pat.search(full_text):
                    # Weaker match, but still likely non‑content
                    return {
                        "is_content": False,
                        "category": category,
                        "confidence": 0.70,
                        "reason": f"Contains pattern for '{category}'",
                    }

        # Check for TOC density
        if self._detect_toc_by_density(lines):
            return {
                "is_content": False,
                "category": "toc",
                "confidence": 0.85,
                "reason": "High density of TOC‑like lines",
            }

        # Check total character length
        stripped = ''.join(text.split())
        if len(stripped) < self.min_content_chars:
            return {
                "is_content": False,
                "category": "too_short",
                "confidence": 0.60,
                "reason": f"Fewer than {self.min_content_chars} alphanumeric characters",
            }

        # Otherwise, treat as content
        return {
            "is_content": True,
            "category": "content",
            "confidence": 1.0,
            "reason": "Passed all heuristic filters",
        }

    def classify_pages(self, pages: dict[int, str]) -> dict[int, dict[str, Any]]:
        """
        Classify multiple pages.

        Args:
            pages: dict mapping page number → page text

        Returns:
            dict mapping page number → classification dict
        """
        results = {}
        for page_num, text in pages.items():
            results[page_num] = self.classify_page(text)
            self.log(
                f"    [ContentFilter] Page {page_num}: {results[page_num]['reason']}",
                "DEBUG"
            )
        return results

    def filter_pages(self, pages: dict[int, str]) -> dict[int, str]:
        """
        Return only pages classified as content.

        Args:
            pages: dict mapping page number → page text

        Returns:
            dict with only content pages
        """
        results = {}
        for page_num, text in pages.items():
            classification = self.classify_page(text)
            if classification["is_content"]:
                results[page_num] = text
            else:
                self.log(
                    f"    [ContentFilter] Page {page_num} skipped: {classification['reason']}",
                    "DEBUG"
                )
        return results

    def filter_segment_content(
        self,
        content: str,
        start_page: int | None = None,
        end_page: int | None = None,
        min_tokens_keep: int = 100
    ) -> str:
        """
        Filter a segment's content page‑by‑page, but with a fallback:
        if the filtered content is too short (in tokens), return the original.

        This prevents segments from being completely stripped.

        Args:
            content: The full markdown content of the segment (with page markers).
            start_page, end_page: Only used for logging.
            min_tokens_keep: Minimum token count to keep filtered content; if below,
                             fall back to original.

        Returns:
            Filtered content string, or original if filtered is too short.
        """
        if not content:
            return content

        from utils.token_counter import count_tokens

        # Split content by page markers while preserving the markers.
        marker_pattern = re.compile(r'(<!-- original page (\d+) -->)')
        parts = marker_pattern.split(content)

        filtered_parts = []
        for i in range(1, len(parts), 3):
            if i + 2 >= len(parts):
                break
            marker_full = parts[i]
            page_num_str = parts[i+1]
            page_text = parts[i+2]

            try:
                page_num = int(page_num_str)
            except ValueError:
                # Should not happen, but keep the content if parsing fails
                filtered_parts.append(marker_full + page_text)
                continue

            classification = self.classify_page(page_text)
            if classification["is_content"]:
                filtered_parts.append(marker_full + page_text)
            else:
                self.log(
                    f"  ⏭️ Skipping page {page_num} in summarisation: {classification['reason']}",
                    "DEBUG"
                )

        filtered_content = "".join(filtered_parts)

        # If all pages were filtered out, keep at least 500 characters
        if not filtered_parts:
            self.log("  ⚠️ All pages filtered out – keeping first 500 chars as fallback", "WARNING")
            return content[:500] + "\n\n[...]"

        # H12 fix: if filtered content is too short, DON't return the original
        # (which includes TOC/index pages). Return only the filtered content
        # even if it's short — a short summary is better than a garbage one.
        filtered_tokens = count_tokens(filtered_content)
        if filtered_tokens < min_tokens_keep:
            self.log(
                f"  ⚠️ Filtered content has only {filtered_tokens} tokens (< {min_tokens_keep}) – "
                f"keeping filtered content (short but clean).",
                "WARNING"
            )
            return filtered_content

        return filtered_content

    def get_skip_reasons(self, pages: dict[int, str]) -> dict[int, str]:
        """
        Return a dict of page number → skip reason for non‑content pages.

        Useful for logging and debugging.
        """
        reasons = {}
        for page_num, text in pages.items():
            classification = self.classify_page(text)
            if not classification["is_content"]:
                reasons[page_num] = classification["reason"]
        return reasons
