"""
Heading-based segmenter — detects chapter boundaries from markdown headings.

FIXES in this version:
  - Loads patterns from utils/patterns.json for flexible detection.
  - Added detection for numbered sections.
  - Refined plain heading detection to avoid sentence fragments.
"""

import json
import re
from collections.abc import Callable

from core.models import ConversionRequest, Segment
from utils.logging import get_main_logger

logger = get_main_logger()

BLOCKLIST = frozenset(
    {
        "TABLE OF CONTENTS",
        "CONTENTS",
        "INDEX",
        "REFERENCES",
        "BIBLIOGRAPHY",
        "ACKNOWLEDGMENTS",
        "ACKNOWLEDGEMENTS",
        "PREFACE",
        "FOREWORD",
        "DEDICATION",
        "ABOUT THE AUTHOR",
        "COPYRIGHT",
        "COLOPHON",
        "GLOSSARY",
        "فهرست مطالب",
        "فهرست",
        "منابع",
        "مراجع",
        "مقدمه ناشر",
        "سپاسگزاری",
    }
)

# Common stopwords that should not start a heading
HEADING_STOP_STARTS = frozenset(
    {
        "to",
        "of",
        "for",
        "with",
        "from",
        "by",
        "on",
        "at",
        "in",
        "into",
        "through",
        "during",
        "without",
        "against",
        "between",
        "among",
        "upon",
        "about",
        "after",
        "before",
        "under",
        "over",
        "toward",
    }
)


class HeadingSegmenter:
    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._compile_patterns()

    def _load_patterns_from_json(self) -> list[str]:
        patterns = []
        try:
            from app_paths import resource_path  # V0.6.63: bundle-aware

            json_path = resource_path("utils", "patterns.json")
            if json_path.exists():
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                pattern_dict = data.get("patterns", {})
                for category in pattern_dict.values():
                    for lang_patterns in category.values():
                        patterns.extend(lang_patterns)
                self.log(
                    f"  [HeadingSegmenter] Loaded {len(patterns)} patterns from patterns.json",
                    "DEBUG",
                )
        except Exception as e:
            self.log(f"  [HeadingSegmenter] Error loading patterns.json: {e}", "DEBUG")
        return patterns

    def _compile_patterns(self):
        self.explicit_patterns: list[re.Pattern] = []
        self.h1_fallback = True

        # 1. User custom patterns
        for pat in self.request.custom_regex_patterns:
            try:
                self.explicit_patterns.append(re.compile(pat, re.IGNORECASE | re.UNICODE))
            except re.error as e:
                self.log(f"  Invalid custom regex '{pat}': {e}", "WARNING")

        # 2. English structural keywords
        self.explicit_patterns.append(
            re.compile(
                r"^#{1,2}\s+(?:Chapter|Part|Appendix|Unit|Module|Section|Lesson|Episode|Topic)\s+",
                re.IGNORECASE,
            )
        )
        self.explicit_patterns.append(
            re.compile(
                r"^(?:Chapter|Part|Appendix|Unit|Module|Section|Lesson|Episode|Topic)\s+\d+\s*(?:[:\-–—]|$)",
                re.IGNORECASE,
            )
        )
        self.explicit_patterns.append(
            re.compile(
                r"^(?i:Chapter|Part|Appendix|Unit|Module|Section|Lesson|Episode|Topic)\s+\d+\s+[A-Z]"
            )
        )

        # 3. Numbered sections
        self.explicit_patterns.append(
            re.compile(r"^\d{1,2}\s*[-–—]\s+[A-Z][A-Za-z\s,.:]{3,}$", re.UNICODE)
        )
        self.explicit_patterns.append(
            re.compile(r"^\d{1,2}\.\s+[A-Z][A-Za-z\s,.:]{3,}$", re.UNICODE)
        )
        # V3.8.0 Phase 4.2 / V3.9.6: Academic section numbering
        # V3.9.6 FIX: Only treat TOP-LEVEL academic sections (1., 2., 3.) as
        # chapter boundaries. Subsections (1.1, 1.2, 2.3.1) should NOT be
        # chapter boundaries — they would over-segment academic papers into
        # dozens of tiny segments. Subsections are now tracked separately
        # via _is_academic_subsection() for section-detection (A6) use.
        #
        # Top-level: "1. Introduction", "1. Introduction", "1: Introduction"
        self.explicit_patterns.append(
            re.compile(r"^\d{1,2}[.):]\s+[A-Z][A-Za-z\s,.:'\-]{3,}$", re.UNICODE)
        )
        self.explicit_patterns.append(
            re.compile(r"^#{1,2}\s+\d{1,2}[.):]?\s+[A-Z][A-Za-z\s,.:'\-]{3,}$", re.UNICODE)
        )
        # V3.9.6: Also match "Section 1", "Section 2: Title" patterns
        self.explicit_patterns.append(
            re.compile(r"^Section\s+\d+(?:[:\.\s\-–—]+[A-Z])?", re.IGNORECASE)
        )
        self.explicit_patterns.append(re.compile(r"^Part\s+[IVX]+", re.IGNORECASE))

        # 4. Persian structural keywords
        self.explicit_patterns.append(
            re.compile(r"^#{1,2}\s+(?:فصل|بخش|قانون|مبحث|قسمت|پیوست)", re.UNICODE)
        )
        self.explicit_patterns.append(
            re.compile(r"^(?:فصل|بخش|قانون|مبحث|قسمت|پیوست)\s+", re.UNICODE)
        )

        # 5. Load patterns from patterns.json
        json_patterns = self._load_patterns_from_json()
        for pat in json_patterns:
            try:
                self.explicit_patterns.append(re.compile(pat, re.IGNORECASE | re.UNICODE))
            except re.error:
                pass

        # 6. User custom keywords
        for kw in self.request.custom_keywords:
            if kw.strip():
                try:
                    self.explicit_patterns.append(
                        re.compile(
                            r"^(?:#{1,2}\s+)?" + re.escape(kw.strip()),
                            re.IGNORECASE | re.UNICODE,
                        )
                    )
                except re.error:
                    pass

    def _in_blocklist(self, line: str) -> bool:
        upper = line.upper().strip().lstrip("#").strip()
        return upper in BLOCKLIST

    def _is_explicit_chapter(self, line: str) -> bool:
        if self._in_blocklist(line):
            return False
        return any(p.match(line.strip()) for p in self.explicit_patterns)

    # V3.9.6: Academic subsection detection (1.1, 1.2, 2.3.1, etc.)
    # These are NOT chapter boundaries but ARE section boundaries for A6
    # (section-by-section map-reduce). This allows academic papers to be
    # segmented into chapters by top-level sections (1., 2., 3.) while
    # still detecting subsections for map-reduce summarization.
    _ACADEMIC_SUBSECTION_RE = re.compile(
        r"^#{1,3}\s+(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+[A-Z]",
        re.UNICODE,
    )
    _ACADEMIC_SUBSECTION_PLAIN_RE = re.compile(
        r"^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+[A-Z][A-Za-z\s,.:\'\-]{3,}$",
        re.UNICODE,
    )

    def is_academic_subsection(self, line: str) -> bool:
        """V3.9.6: Check if a line is an academic subsection (1.1, 2.3.1, etc.).

        Returns True for subsection headings like:
        - "1.1 Introduction"
        - "## 2.3.1 Methodology"
        - "1.1. Background"

        Returns False for:
        - Top-level sections: "1. Introduction" (these are chapter boundaries)
        - Regular text lines
        - Chapter headings
        """
        stripped = line.strip()
        if not stripped:
            return False
        # Check markdown heading version
        if self._ACADEMIC_SUBSECTION_RE.match(stripped):
            return True
        # Check plain text version
        if self._ACADEMIC_SUBSECTION_PLAIN_RE.match(stripped):
            return True
        return False

    def extract_academic_subsections(self, markdown_text: str) -> list[tuple[int, str]]:
        """V3.9.6: Extract all academic subsection headings from markdown.

        Returns list of (line_index, heading_text) tuples for subsections
        like "1.1 Introduction", "2.3.1 Methodology".
        Used by section detection (A6) for map-reduce summarization.
        """
        subsections = []
        for i, line in enumerate(markdown_text.splitlines()):
            if self.is_academic_subsection(line):
                heading = line.strip().lstrip("#").strip()
                subsections.append((i, heading))
        return subsections

    def _is_h1_chapter(self, line: str) -> bool:
        if not self.h1_fallback:
            return False
        stripped = line.strip()
        if not re.match(r"^#(?!#)\s+\S", stripped):
            return False
        if self._in_blocklist(stripped):
            return False
        heading_text = stripped.lstrip("#").strip()
        if len(heading_text) < 4:
            return False
        if heading_text.isupper() and len(heading_text.split()) <= 2:
            return False
        return True

    def _detect_plain_headings(
        self, lines: list[str], page_markers: list[tuple[int, int]]
    ) -> list[int]:
        """
        Detect plain text headings (no explicit pattern) based on page position and style.
        Returns list of line indices that are likely chapter headings.
        """
        heading_line_indices = []
        marker_lines = {idx for _, idx in page_markers}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Must be near a page marker (within 5 lines after)
            near_marker = False
            for offset in range(1, 6):
                if i - offset in marker_lines:
                    near_marker = True
                    break
            if not near_marker:
                continue

            # Heuristics:
            # - Short line (< 80 chars)
            if len(stripped) > 80:
                continue
            # - No ending punctuation (.;,)
            if re.search(r"[.;,]$", stripped):
                continue
            # - Must not start with a stopword (e.g., "to", "of", "for")
            first_word = stripped.split()[0].lower() if stripped.split() else ""
            if first_word in HEADING_STOP_STARTS:
                continue
            # - Contains at least one uppercase letter
            if not re.search(r"[A-Z]", stripped):
                continue
            # - At least 3 words
            words = stripped.split()
            if len(words) < 3:
                continue
            # - Check if it's title‑case or all caps
            title_case = all(re.match(r"^[A-Z]", w) for w in words if w)
            all_caps = stripped.isupper()
            if not (title_case or all_caps):
                continue

            heading_line_indices.append(i)

        return heading_line_indices

    def _normalise_heading(self, raw_line: str) -> str:
        text = raw_line.strip().lstrip("#").strip()
        text = re.sub(r"\t+", " ", text)
        text = re.sub(r" {2,}", " ", text)
        # V0.07 (output-regression fix): cap pathological headings. PDF
        # extraction frequently glues the chapter TITLE onto the first
        # sentence of the body text ("Chapter N <Title> <first body
        # sentence continues here…>"). Cut at the first sentence boundary,
        # then hard-cap at 80 chars on a word boundary — a headline must
        # never be a paragraph.
        if len(text) > 80:
            _m = re.search(r"[.!?]", text)
            if _m and _m.start() <= 80:
                text = text[: _m.start()].strip()
            else:
                _cut = text[:80].rsplit(" ", 1)[0]
                text = _cut.strip()
        return text

    def _is_chapter_boundary(self, line: str) -> bool:
        normalised = re.sub(r"\t+", " ", line)
        # V0.07 (output-regression fix): a line this long is a glued
        # title+body paragraph, not a heading. Accepting it made the whole
        # paragraph the chapter headline (user-reported regression).
        if len(normalised.strip()) > 120:
            return False
        return self._is_explicit_chapter(normalised) or self._is_h1_chapter(normalised)

    def segment(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        lines = markdown_text.splitlines()
        segments: list[Segment] = []
        current_heading = "Introduction"
        current_content: list[str] = []
        start_page = 1
        found_any_explicit = False

        for i, line in enumerate(lines):
            if self._is_chapter_boundary(line):
                if self._is_explicit_chapter(line):
                    found_any_explicit = True

                if current_content:
                    segments.append(
                        Segment(
                            heading=current_heading,
                            content="\n".join(current_content),
                            start_page=start_page,
                            end_page=self._get_end_page(i, page_markers, total_pages),
                            segment_type="chapter",
                        )
                    )

                current_heading = self._normalise_heading(line)
                current_content = []
                start_page = self._get_start_page(i, page_markers)
            else:
                current_content.append(line)

        if current_content:
            segments.append(
                Segment(
                    heading=current_heading,
                    content="\n".join(current_content),
                    start_page=start_page,
                    end_page=total_pages,
                    segment_type="chapter",
                )
            )

        # If no explicit chapters found, or only one, try plain heading detection
        if len(segments) <= 1:
            self.log(
                "  [HeadingSegmenter] Few or no explicit chapters; trying plain heading detection.",
                "INFO",
            )
            plain_heading_indices = self._detect_plain_headings(lines, page_markers)
            if plain_heading_indices:
                self.log(
                    f"  [HeadingSegmenter] Found {len(plain_heading_indices)} plain text headings.",
                    "INFO",
                )
                segments = []
                current_heading = "Introduction"
                current_content = []
                start_page = 1
                for i, line in enumerate(lines):
                    if i in plain_heading_indices:
                        if current_content:
                            segments.append(
                                Segment(
                                    heading=current_heading,
                                    content="\n".join(current_content),
                                    start_page=start_page,
                                    end_page=self._get_end_page(i, page_markers, total_pages),
                                    segment_type="chapter",
                                )
                            )
                        current_heading = self._normalise_heading(line)
                        current_content = []
                        start_page = self._get_start_page(i, page_markers)
                    else:
                        current_content.append(line)
                if current_content:
                    segments.append(
                        Segment(
                            heading=current_heading,
                            content="\n".join(current_content),
                            start_page=start_page,
                            end_page=total_pages,
                            segment_type="chapter",
                        )
                    )

        if segments and not found_any_explicit:
            self.log(
                f"  [HeadingSegmenter] {len(segments)} chapters via H1 headings or plain text detection.",
                "INFO",
            )
        elif segments:
            self.log(
                f"  [HeadingSegmenter] {len(segments)} chapters via explicit patterns.",
                "INFO",
            )

        return segments

    def _get_start_page(self, line_idx: int, page_markers: list[tuple[int, int]]) -> int:
        for p_num, p_idx in reversed(page_markers):
            if line_idx >= p_idx:
                return p_num
        return 1

    def _get_end_page(
        self, line_idx: int, page_markers: list[tuple[int, int]], total_pages: int
    ) -> int:
        for p_num, p_idx in page_markers:
            if p_idx > line_idx:
                return p_num
        return total_pages
