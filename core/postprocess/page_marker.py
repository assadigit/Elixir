"""Page marker management – insert, preserve, and extract page boundaries."""

import re

from utils.logging import get_main_logger

logger = get_main_logger()

PAGE_COMMENT_PATTERN = re.compile(r"<!-- original page (\d+) -->")


def insert_page_markers(content_by_page: list[tuple[int, str]]) -> str:
    """
    Insert HTML comments at the start of each page's content.
    Args:
        content_by_page: list of (page_num, page_text)
    Returns:
        Single markdown string with page comments.
    """
    parts = []
    for page_num, text in content_by_page:
        parts.append(f"<!-- original page {page_num} -->\n{text}")
    return "\n\n".join(parts)


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


def preserve_markers_during_cleaning(markdown_text: str, cleaned_text: str) -> str:
    """Re-insert page markers if they were stripped during cleaning."""
    original_markers = extract_page_markers(markdown_text)
    if not original_markers:
        return cleaned_text
    cleaned_markers = extract_page_markers(cleaned_text)
    if len(cleaned_markers) == len(original_markers):
        return cleaned_text
    logger.warning("Page markers lost during cleaning — re-inserting at start")
    marker_lines = [f"<!-- original page {p} -->\n" for p, _ in original_markers]
    return "".join(marker_lines) + cleaned_text


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
