"""
Line‑based segmentation from located TOC headings.
Includes post‑processing to merge back‑matter segments.
"""

import re  # <-- ADD THIS LINE
from dataclasses import dataclass

from core.models import TOCResult


@dataclass
class ChapterSegment:
    title: str
    start_line: int
    end_line: int
    confidence: float
    segment_type: str = "chapter"  # "chapter", "part", "back_matter", "gap"


# Back‑matter patterns
BACK_MATTER_PATTERNS = [
    r'(?i)^(references|bibliography|credits|index|about\s+the\s+author|acknowledgments?|glossary|notes|further\s+reading)$'
]

def build_segments(toc_result: TOCResult, md_lines: list[str]) -> list[ChapterSegment]:
    """
    Create line‑based chapter segments from the located TOC entries.
    Also merges back‑matter entries into a single segment.
    """
    if not toc_result.entries:
        return []

    # Sort by line (if available), otherwise by page
    entries = sorted(toc_result.entries, key=lambda e: e.line if e.line is not None else 999999)

    segments = []
    # First pass: build base segments
    for i, entry in enumerate(entries):
        if entry.line is None:
            continue
        start = entry.line
        end = None
        # Look ahead for the next entry with a line
        for j in range(i+1, len(entries)):
            if entries[j].line is not None:
                end = entries[j].line - 1
                break
        if end is None:
            end = len(md_lines) - 1

        # Determine segment type
        seg_type = "chapter"
        title_lower = entry.title.lower()
        if "part" in title_lower:
            seg_type = "part"
        elif any(re.search(pattern, title_lower) for pattern in BACK_MATTER_PATTERNS):
            seg_type = "back_matter"

        segments.append(ChapterSegment(
            title=entry.title,
            start_line=start,
            end_line=end,
            confidence=entry.confidence,
            segment_type=seg_type
        ))

    # If no segments, create a fallback
    if not segments:
        segments.append(ChapterSegment(
            title="Full Document",
            start_line=0,
            end_line=len(md_lines)-1,
            confidence=0.0,
            segment_type="chapter"
        ))
        return segments

    # ---- Post‑processing: merge back‑matter segments ----
    merged_segments = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if seg.segment_type == "back_matter":
            # Collect all consecutive back‑matter segments
            back_matter_group = [seg]
            j = i + 1
            while j < len(segments) and segments[j].segment_type == "back_matter":
                back_matter_group.append(segments[j])
                j += 1
            # Merge into a single segment
            if back_matter_group:
                first = back_matter_group[0]
                last = back_matter_group[-1]
                merged = ChapterSegment(
                    title="Back Matter",
                    start_line=first.start_line,
                    end_line=last.end_line,
                    confidence=sum(s.confidence for s in back_matter_group) / len(back_matter_group),
                    segment_type="back_matter"
                )
                merged_segments.append(merged)
            i = j
        else:
            merged_segments.append(seg)
            i += 1

    return merged_segments
