"""Page marker management – extract and update page-boundary markers."""

import re

PAGE_COMMENT_PATTERN = re.compile(r"<!-- original page (\d+) -->")


def extract_page_markers(markdown_text: str) -> list[tuple[int, int]]:
    """
    Extract page markers from markdown text.
    Returns list of (page_num, character_position).
    """
    markers = []
    for match in PAGE_COMMENT_PATTERN.finditer(markdown_text):
        page_num = int(match.group(1))
        markers.append((page_num, match.start()))
    return markers


def update_page_markers_after_segmentation(
    segments: list, original_markers: list[tuple[int, int]]
) -> list:
    """
    Update each segment's start_page and end_page from the marker positions
    embedded in its content.
    """
    if not original_markers:
        return segments
    for seg in segments:
        start_page = None
        end_page = None
        for marker_match in PAGE_COMMENT_PATTERN.finditer(seg.content):
            page = int(marker_match.group(1))
            if start_page is None or page < start_page:
                start_page = page
            if end_page is None or page > end_page:
                end_page = page
        if start_page is not None:
            seg.start_page = start_page
            seg.end_page = end_page or start_page
    return segments
