"""

Heading utilities – shared functions for normalisation, fuzzy matching,
and front‑matter detection.

Used by both toc_extractor.py and segmenter.py to avoid code duplication.
"""

import logging
import re

# ── Try to import rapidfuzz for faster fuzzy matching ─────────────────────

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    fuzz = None
    RAPIDFUZZ_AVAILABLE = False
    import difflib


# ── Front matter blocklist (copied from heading_segmenter) ──────────────
FRONT_MATTER_BLOCKLIST = frozenset({
    "TABLE OF CONTENTS", "CONTENTS", "INDEX", "REFERENCES", "BIBLIOGRAPHY",
    "ACKNOWLEDGMENTS", "ACKNOWLEDGEMENTS", "PREFACE", "FOREWORD", "DEDICATION",
    "ABOUT THE AUTHOR", "COPYRIGHT", "COLOPHON", "GLOSSARY",
    "فهرست مطالب", "فهرست", "منابع", "مراجع", "مقدمه ناشر", "سپاسگزاری",
})

# Patterns that indicate a heading is likely front matter
FRONT_MATTER_PATTERNS = [
    re.compile(r'(?i)^\s*(table\s+of\s+contents|contents)\s*$'),
    re.compile(r'(?i)^\s*فهرست\s+(مطالب)?\s*$'),
    re.compile(r'(?i)^\s*index\s*$'),
    re.compile(r'(?i)^\s*نمایه\s*$'),
    re.compile(r'(?i)^\s*(references|bibliography|works\s+cited|sources)\s*$'),
    re.compile(r'(?i)^\s*(منابع|مراجع|کتابنامه)\s*$'),
    re.compile(r'(?i)^\s*copyright\s*[©]?'),
    re.compile(r'(?i)^\s*©\s*\d{4}'),
    re.compile(r'(?i)^\s*all\s+rights?\s+reserved'),
    re.compile(r'(?i)^\s*dedication\s*$'),
    re.compile(r'(?i)^\s*تقدیم\s*(به)?\s*$'),
    re.compile(r'(?i)^\s*(acknowledgments|acknowledgements|thanks)\s*$'),
    re.compile(r'(?i)^\s*(سپاسگزاری|تقدیر|تشکر)\s*$'),
    re.compile(r'(?i)^\s*(preface|foreword|prologue)\s*$'),
    re.compile(r'(?i)^\s*(پیشگفتار|سخن\s+ناشر|یادداشت\s+مترجم)\s*$'),
]

# Patterns that indicate a heading is a chapter (for offset detection)
CHAPTER_LIKE_PATTERNS = [
    re.compile(r'^(?:Chapter|Part|Section|Appendix|فصل|بخش|قسمت|مبحث)\s+', re.IGNORECASE | re.UNICODE),
    re.compile(r'^\d+\s*[-–—.:]\s+', re.UNICODE),
]


def normalize_heading(heading: str) -> str:
    """
    Aggressively normalise a heading for matching:
    - Remove leading "Chapter", "Part", "Section" prefixes with numbers/roman.
    - Remove leading numbers and separators.
    - Remove trailing punctuation.
    - Collapse spaces and lower-case.
    - Handle Persian/Arabic prefixes.
    """
    h = heading.strip()
    # Remove common prefixes with numbers/roman: "Chapter 1", "Part II", "Section 3", etc.
    h = re.sub(r'^(?:Chapter|Part|Section|Appendix|فصل|بخش)\s+[IVX\d]+\s*[-–—:.]?\s*', '', h, flags=re.IGNORECASE)
    # Remove standalone numbers at start: "1 - ", "1. ", etc. (including sub-sections like "1.2.3")
    h = re.sub(r'^\d+(?:\.\d+)*\s*[-–—.:]\s*', '', h)
    # Remove trailing punctuation
    h = re.sub(r'[:.\-–—]\s*$', '', h)
    # Collapse multiple spaces, tabs, Unicode whitespace
    h = re.sub(r'\s+', ' ', h)
    return h.strip().lower()


def fuzzy_match_heading(
    search_heading: str,
    candidate_headings: list[tuple[int, str]],
    thresholds: list[float] = None,
    use_rapidfuzz: bool = True,
) -> tuple[int | None, str | None, float, str]:
    """
    Find the best fuzzy match for search_heading among candidates.

    Args:
        search_heading: The heading to search for.
        candidate_headings: List of (line_number, heading_text) tuples.
        thresholds: List of thresholds to try (default: [0.85, 0.75, 0.65]).
        use_rapidfuzz: If True, use rapidfuzz (faster). Falls back to difflib.

    Returns:
        (line_number, matched_text, score, method) or (None, None, 0, "failed")
    """
    if thresholds is None:
        thresholds = [0.85, 0.75, 0.65]

    if not candidate_headings:
        return None, None, 0.0, "failed"

    norm_search = normalize_heading(search_heading)
    if not norm_search:
        return None, None, 0.0, "failed"

    best_match = None
    best_score = 0.0
    best_method = "failed"

    for threshold in thresholds:
        for line_no, cand_text in candidate_headings:
            norm_cand = normalize_heading(cand_text)
            if not norm_cand:
                continue
            if use_rapidfuzz and RAPIDFUZZ_AVAILABLE:
                score = fuzz.ratio(norm_search, norm_cand) / 100.0
            else:
                score = difflib.SequenceMatcher(None, norm_search, norm_cand).ratio()
            if score >= threshold and score > best_score:
                best_score = score
                best_match = (line_no, cand_text)
                best_method = f"fuzzy_{threshold:.2f}".replace('.', '_')
        if best_match:
            break

    if best_match:
        return best_match[0], best_match[1], best_score, best_method

    return None, None, 0.0, "failed"


def is_likely_heading(line: str) -> bool:
    """
    Heuristic check if a line looks like a heading.
    Used to build candidate lists for fuzzy matching.
    """
    stripped = line.strip()
    if not stripped:
        return False
    # Skip code blocks, tables
    if stripped.startswith('```') or stripped.startswith('|'):
        return False
    # Length: 3 to 200 chars (allow short headings like "REFERENCES")
    if len(stripped) < 3 or len(stripped) > 200:
        return False

    # 1. Markdown heading
    if stripped.startswith('#'):
        return True
    # 2. All caps (e.g., "REFERENCES")
    if stripped.isupper():
        return True
    # 3. STARTS WITH chapter/part keywords (V0.07: start-anchored — the old
    #    substring test let body sentences like "In this Chapter we examine…"
    #    qualify as heading candidates for fuzzy TOC matching)
    if re.match(r"^(?:#+\s*)?(?:Chapter|Part|Section|CHAPTER|PART|SECTION)\b", stripped):
        return True
    # 4. Title‑case, short, no ending punctuation
    if (len(stripped) <= 80 and
        not re.search(r'[.;,]$', stripped) and
        stripped[0].isupper() and
        len(stripped.split()) >= 2):
        return True
    return False


def is_front_matter(heading: str) -> bool:
    """
    Check if a heading is likely front matter (TOC, Index, References, etc.).
    """
    heading_upper = heading.upper().strip()
    if heading_upper in FRONT_MATTER_BLOCKLIST:
        return True

    for pattern in FRONT_MATTER_PATTERNS:
        if pattern.search(heading):
            return True
    return False


def is_chapter_like(heading: str) -> bool:
    """
    Check if a heading looks like a chapter (for offset detection).
    """
    for pattern in CHAPTER_LIKE_PATTERNS:
        if pattern.search(heading):
            return True
    return False


def get_heading_candidates(
    markdown_lines: list[str],
    start_line: int = 0,
    end_line: int | None = None,
) -> list[tuple[int, str]]:
    """
    Extract all likely heading lines from markdown within a line range.
    Returns list of (line_number, heading_text).
    """
    if end_line is None:
        end_line = len(markdown_lines) - 1

    candidates = []
    for line_no in range(start_line, min(end_line + 1, len(markdown_lines))):
        line = markdown_lines[line_no]
        if is_likely_heading(line):
            candidates.append((line_no, line.strip()))
    return candidates


# V18.20.4.11 (P1): shared segment-filename slug helper. The heading→filename
# transformation lived as duplicated inline regexes in
# core/pipeline/conversion/output_save.py (segment write + deterministic-
# analysis write), and deterministic_analyzer.find_analysis_for_heading needs
# the SAME transformation to map a chapter heading back to its own
# *_analysis.md file — previously the heading was ignored and the FIRST
# analysis file tree-wide was injected into EVERY chapter (wrong-chapter
# authors/keywords in prompts, coverage probes, gap-fill and the floors).
# One canonical implementation; output_save keeps only its idx-dependent
# ``segment_{idx:03d}`` fallback at the call site.
def segment_filename_slug(heading: str) -> str:
    """Mirror output_save's heading→segment-filename slug (V18.20.4.11).

    Byte-identical to the former inline computation in
    core/pipeline/conversion/output_save.py (order of operations included):

        _h = re.sub(r"[\\t\\r\\n]+", " ", heading)
        _h = re.sub(r" {2,}", " ", _h).strip()
        safe = re.sub(r"[^\\w\\s\\-]", "", _h).strip()[:60]

    The caller composes the filename as ``{idx:03d}_{safe}.md`` (analysis:
    ``{idx:03d}_{safe}_analysis.md``) and falls back to
    ``segment_{idx:03d}`` when this returns "" (heading collapses to
    nothing after sanitisation).

    Args:
        heading: the raw segment heading (may contain tabs/newlines,
            special characters, arbitrary length).

    Returns:
        The sanitised slug, at most 60 chars; "" when the heading is empty
        or consists entirely of removable characters.
    """
    _h = re.sub(r"[\t\r\n]+", " ", heading or "")
    _h = re.sub(r" {2,}", " ", _h).strip()
    return re.sub(r"[^\w\s\-]", "", _h).strip()[:60]
