"""V18.20.1.0 (D6): Citation/reference/figure extraction extracted from
text_preprocessor_impl.py.

The citation-extraction concern (extract_citations, extract_reference_list,
extract_figure_descriptions + their regex patterns) was lines 2588-2721 of the
pre-V18.20.1.0 text_preprocessor_impl.py. Extracted verbatim; the impl module
re-exports these for backward compat.
"""

from __future__ import annotations

import re

# V3.8.0 Phase 4.4: Citation Extraction
# ════════════════════════════════════════════════════════════════════════════

# Citation patterns
_AUTHOR_YEAR_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][a-z]+)?)\s*"
    r"\((\d{4}[a-z]?)\)"
)
_BRACKET_CITATION_PATTERN = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_NUMERICAL_CITATION_PATTERN = re.compile(r"\((\d+(?:,\s*\d+)*)\)")


def extract_citations(text: str) -> list[dict]:
    """V3.8.0 Phase 4.4: Extract citations from academic text.

    Detects:
    - Author (Year) format: Smith (2023), Johnson et al. (2019)
    - [N] bracket format: [1], [2, 3]
    - (N) numerical format: (1), (2, 3)

    Returns list of dicts with 'type', 'citation', 'author' (if available), 'year' (if available).
    """
    citations = []

    # Author (Year) format
    for m in _AUTHOR_YEAR_PATTERN.finditer(text):
        citations.append(
            {
                "type": "author_year",
                "citation": m.group(0),
                "author": m.group(1).strip(),
                "year": m.group(2),
            }
        )

    # [N] bracket format
    for m in _BRACKET_CITATION_PATTERN.finditer(text):
        citations.append(
            {
                "type": "bracket",
                "citation": m.group(0),
                "numbers": m.group(1),
            }
        )

    # (N) numerical format (be careful not to catch regular numbers)
    for m in _NUMERICAL_CITATION_PATTERN.finditer(text):
        nums = m.group(1)
        # Only count as citation if it looks like a reference (comma-separated or single small number)
        if "," in nums or (nums.isdigit() and int(nums) <= 100):
            citations.append(
                {
                    "type": "numerical",
                    "citation": m.group(0),
                    "numbers": nums,
                }
            )

    return citations


def extract_reference_list(text: str) -> list[str]:
    """V3.8.0 Phase 4.4: Extract reference list from academic text.

    Looks for "References", "Bibliography", "Works Cited" sections and
    extracts individual reference entries.
    """
    # Find the references section
    ref_section_match = re.search(
        r"(?:^|\n)#{0,3}\s*(?:References|Bibliography|Works\s+Cited|Literature\s+Cited)\s*\n",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not ref_section_match:
        return []

    ref_text = text[ref_section_match.end() :]

    # Split into individual references — each typically starts with [N] or Author, Year
    refs = []
    # Pattern 1: [1] Author, Title...
    bracket_refs = re.split(r"\n\[(\d+)\]\s+", ref_text)
    if len(bracket_refs) > 1:
        for i in range(1, len(bracket_refs), 2):
            if i < len(bracket_refs):
                ref_text_item = bracket_refs[i + 1].strip() if i + 1 < len(bracket_refs) else ""
                refs.append(f"[{bracket_refs[i]}] {ref_text_item}")
    else:
        # Pattern 2: Each line is a reference (Author, Year. Title...)
        lines = ref_text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if len(line) > 20 and (line[0].isupper() or line[0] == "["):
                refs.append(line)

    return refs[:50]  # Cap at 50 references


# ════════════════════════════════════════════════════════════════════════════
# V3.8.0 Phase 4.3: Chart/Diagram Description Extraction
# ════════════════════════════════════════════════════════════════════════════


def extract_figure_descriptions(text: str) -> list[dict]:
    """V3.8.0 Phase 4.3: Extract figure/chart descriptions from text.

    Detects:
    - "Figure 1: Description" patterns
    - "Fig. 1. Description" patterns
    - "Table 1: Description" patterns
    - Image alt text in markdown: ![Description](image.png)

    Returns list of dicts with 'type', 'number', 'description'.
    """
    figures = []

    # Figure patterns
    for m in re.finditer(r"(?:Figure|Fig\.?)\s+(\d+)[.:]?\s+([^\n]{10,200})", text, re.IGNORECASE):
        figures.append(
            {
                "type": "figure",
                "number": m.group(1),
                "description": m.group(2).strip(),
            }
        )

    # Table patterns
    for m in re.finditer(r"Table\s+(\d+)[.:]?\s+([^\n]{10,200})", text, re.IGNORECASE):
        figures.append(
            {
                "type": "table",
                "number": m.group(1),
                "description": m.group(2).strip(),
            }
        )

    # Markdown image alt text
    for m in re.finditer(r"!\[([^\]]{5,200})\]\([^)]+\)", text):
        figures.append(
            {
                "type": "image",
                "number": "",
                "description": m.group(1).strip(),
            }
        )

    return figures
