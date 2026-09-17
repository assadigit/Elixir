from dataclasses import dataclass
from typing import Any


@dataclass
class TOCEntry:
    """A single TOC entry.

    V13.32.7: Behaves like a (title, page) tuple for backward compatibility
    (supports indexing [0], [1] and tuple unpacking `for heading, page in entries`),
    while also carrying the `level` field for the 3-Layer chapter-level segmentation.
    This is the PDF reader's sidebar TOC — the authoritative hierarchy from the
    PDF's native outline/bookmarks. No guesswork needed.
    """
    title: str
    page: int | None = None
    line: int | None = None
    confidence: float = 1.0
    is_heading_found: bool = False
    match_method: str = ""
    level: int = 0  # V13.32.0: outline hierarchy level (0=chapter, 1=sub-section)

    def __getitem__(self, index: int) -> Any:
        """Tuple-like indexing: [0]=title, [1]=page."""
        if index == 0:
            return self.title
        elif index == 1:
            return self.page
        raise IndexError(f"TOCEntry index out of range: {index}")

    def __iter__(self):
        """Tuple-like unpacking: `for heading, page in entries`."""
        yield self.title
        yield self.page

    def __len__(self) -> int:
        return 2

@dataclass
class TOCResult:
    entries: list[TOCEntry]
    method: str
    confidence: float
    validation_report: str
