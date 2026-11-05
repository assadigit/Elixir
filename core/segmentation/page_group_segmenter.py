"""Page-group block segmenter — V0.7.1 (wizard rework ③, item 3c, D5).

When TOC / chapter / heading / semantic segmentation all fail (the AUTO
cascade's tail), the pages are chunked into N-page BLOCKS instead of raw
fixed-token chunks: the blocks follow the book's physical page structure,
and a block boundary never cuts mid-line (it lands on an existing blank
line — the paragraph discipline the token chunker already follows, here
applied to page-sized groups).

``page_group_size`` semantics — the FIRST real reader of a previously
vestigial field (audit §W4: logged and ignored, zero core consumers):

    0            → AUTO: N is computed from the measured page token
                   density — target ≈ ``PAGE_GROUP_TARGET_TOKENS`` tokens
                   per block (the 4-6k band's midpoint), clamped to
                   4-25 pages. No density data → the historical 10.
    1 or more    → manual override: exactly N pages per block (the
                   wizard's override spin is 4-25, the backend trusts
                   any positive int).

``chunk_by_page_groups=False`` disables the block fallback entirely
(the cascade then falls through to the token chunker).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from core.models import ConversionRequest, Segment
from utils.logging import get_main_logger
from utils.token_counter import count_tokens

logger = get_main_logger()

# ── Block-sizing constants (content-agnostic — Rule 1) ─────────────────────
# Target ≈ 5,000 tokens/block: the midpoint of the plan's 4-6k band, a
# size the summariser's context/output clamps handle comfortably.
PAGE_GROUP_TARGET_TOKENS = 5000
PAGE_GROUP_MIN_PAGES = 4
PAGE_GROUP_MAX_PAGES = 25
# No density data measurable (empty/blank pages only) → the historical
# default block size, kept so the fallback never divides by nothing.
PAGE_GROUP_FALLBACK_SIZE = 10

# A page whose only content is the ``<!-- original page N -->`` marker
# comment has no readable text — a block made of such pages is skipped
# (same discipline as the located-TOC <50-token guard).
_PAGE_MARKER_RE = re.compile(r"<!-- original page \d+ -->", re.IGNORECASE)


def _strips_to_nothing(text: str) -> bool:
    """True when, minus page-marker comments, nothing readable remains."""
    return not _PAGE_MARKER_RE.sub("", text).strip()


def compute_auto_page_group_size(page_tokens: list[int]) -> int:
    """AUTO block size from measured per-page token counts (V0.7.1 3c).

    Pure content-agnostic sizing: mean page density → target tokens per
    block → clamp. No data / zero density → ``PAGE_GROUP_FALLBACK_SIZE``.
    """
    usable = [t for t in page_tokens if t > 0]
    if not usable:
        return PAGE_GROUP_FALLBACK_SIZE
    density = sum(usable) / len(usable)
    if density <= 0:
        return PAGE_GROUP_FALLBACK_SIZE
    n = round(PAGE_GROUP_TARGET_TOKENS / density)
    return max(PAGE_GROUP_MIN_PAGES, min(PAGE_GROUP_MAX_PAGES, n))


def resolve_page_group_size(request: ConversionRequest, page_tokens: list[int]) -> int:
    """Resolve the effective block size: manual value, else AUTO.

    ``page_group_size > 0`` is the manual override; ``0`` (or negative,
    defensively) means AUTO from the measured density. A non-positive
    manual value with no measurable density lands on the fallback size.
    """
    manual = int(getattr(request, "page_group_size", 0) or 0)
    if manual > 0:
        return manual
    return compute_auto_page_group_size(page_tokens)


class PageGroupSegmenter:
    """Chunks a document into N-page blocks (V0.7.1 3c, D5).

    Used by the AUTO cascade between the semantic attempt and the token
    chunker. Splits on the page markers (``<!-- original page N -->``);
    each block covers N consecutive marker pages, with the cut pulled
    back to the last blank line inside the block so no line is ever
    split across two blocks.
    """

    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)

    # ── public ────────────────────────────────────────────────────────────

    def segment(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        """Return the page-group blocks, or ``[]`` when impossible.

        ``[]`` (no page markers / no usable pages) lets the caller fall
        through to the next cascade stage — the same contract as the
        other fallback segmenters.
        """
        if not page_markers:
            self.log("[PageGroups] no page markers — cannot form page blocks.", "WARNING")
            return []

        # Per-page extents: [marker start, next marker start) — the last
        # page runs to the end of the document.
        markers = sorted(page_markers, key=lambda m: m[1])
        extents: list[tuple[int, int, int]] = []  # (page_num, start, end)
        for i, (p_num, pos) in enumerate(markers):
            end = markers[i + 1][1] if i + 1 < len(markers) else len(markdown_text)
            extents.append((p_num, pos, end))

        # Measured density → the block size (manual override wins).
        page_tokens = [count_tokens(markdown_text[s:e]) for (_p, s, e) in extents]
        n = resolve_page_group_size(self.request, page_tokens)
        density = next((t for t in page_tokens if t > 0), 0)
        _sizing = (
            f"manual ({n} pages/block)"
            if int(getattr(self.request, "page_group_size", 0) or 0) > 0
            else f"AUTO (density ≈ {density} tokens/page → {n} pages/block)"
        )
        logger.info(f"[PageGroups] Block size: {_sizing}")
        self.log(f"[PageGroups] Block size: {_sizing}", "INFO")

        segments: list[Segment] = []
        pos = extents[0][1]  # start of the first block
        for block_start in range(0, len(extents), n):
            block = extents[block_start : block_start + n]
            first_page = block[0][0]
            last_page = block[-1][0]
            is_final = block_start + n >= len(extents)

            if is_final:
                cut = len(markdown_text)
            else:
                # Pull the cut back to the last blank line inside the
                # block so the boundary never splits a line/paragraph —
                # the token chunker's discipline, applied to page groups.
                next_marker = extents[block_start + n][1]
                window = markdown_text[pos:next_marker]
                break_idx = window.rfind("\n\n")
                cut = pos + break_idx if break_idx > 0 else next_marker

            text = markdown_text[pos:cut].strip()
            if text and not _strips_to_nothing(text):
                # Readable content (blank pages / marker-only pages
                # contribute nothing — a block with nothing to summarise).
                segments.append(
                    Segment(
                        heading=f"Pages {first_page}-{last_page}",
                        content=text,
                        start_page=max(1, first_page),
                        end_page=max(1, last_page),
                        segment_type="chunk",
                    )
                )
            pos = cut  # the next block starts where this one ended

        logger.info(f"[PageGroups] Created {len(segments)} page blocks.")
        self.log(f"[PageGroups] Created {len(segments)} page blocks.", "INFO")
        return segments
