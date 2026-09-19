"""
Segmenter factory with robust page-bound recalc, contiguity enforcement,
manual segmentation override, and support for pre‑located TOC entries.

NEW in this version (Phase 4 + Sprint 2):
  - Accepts TOC entries as TOCResult from toc_extractor.locate_headings().
  - Uses rapidfuzz + page‑window search (with fallback to difflib).
  - Priority: manual > located TOC > fuzzy TOC > heading pipeline > semantic > token.
  - All existing heuristics (keyword overlap, same‑chapter merge) preserved.
  - Confidence‑based filtering – now lower threshold (0.3) to keep more sections.
  - Academic‑aware merging: lowers MIN_SEGMENT_TOKENS to 80 for academic papers.
  - Short‑segment merging is now applied in the located‑TOC branch (already done).
  - FIX: IndexError in _find_heading_in_markdown – clamps start_line/end_line to valid range.
  - FIX: Page mapping uses character positions, not line numbers, to correctly map to page markers.
  - FIX: Skip contiguity enforcement for located‑TOC segmentation to avoid spurious overlap warnings.
  - FIX: end_line calculation in _segment_with_located_headings – handles edge cases, prevents empty content.
  - NEW: All sections with confidence >= 0.3 are kept (previously 0.5).
  - NEW: _merge_duplicate_headings() method to eliminate duplicate headings.
"""

import re
from collections.abc import Callable

# ── Shared heading utilities ──────────────────────────────────────────────
from core.common import (
    fuzzy_match_heading,
    get_heading_candidates,
    normalize_heading,
)
from core.models import ConversionRequest, Segment, SegmentStrategy, TOCEntry, TOCResult
from core.pdf.toc_extractor import TocExtractor
from core.postprocess.page_marker import extract_page_markers
from core.segmentation.heading_segmenter import HeadingSegmenter
from core.segmentation.semantic_segmenter import SemanticSegmenter
from core.segmentation.token_segmenter import TokenSegmenter
from utils.logging import get_main_logger
from utils.token_counter import count_tokens

logger = get_main_logger()


# ── Dynamic MIN_SEGMENT_TOKENS based on source_type ──────────────────────
# V3.10.0: Now uses content presets for per-type configuration.
# Academic: 80 (short sections), Philosophy: 400 (long passages), Normal: 250
def get_min_segment_tokens(request: ConversionRequest) -> int:
    from core.llm.content_presets import get_content_preset

    source_type = getattr(request, "source_type", "normal_book")
    preset = get_content_preset(source_type)
    return preset.min_segment_tokens


MIN_TOC_SEGMENTS = 3
# Keyword overlap threshold: if heading shares < 20% of keywords with content, treat as false positive
KEYWORD_OVERLAP_THRESHOLD = 0.20

# Confidence thresholds – lowered to keep more sections
CONFIDENCE_HIGH = 0.7
CONFIDENCE_MEDIUM = 0.5
CONFIDENCE_LOW = 0.3  # NEW: keep entries with at least this confidence

# Stopwords for keyword extraction (copied from summarizer for independence)
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "but",
        "is",
        "it",
        "its",
        "this",
        "that",
        "was",
        "are",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "with",
        "from",
        "by",
        "as",
        "not",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "their",
        "our",
        "his",
        "her",
        "which",
        "who",
        "what",
        "when",
        "where",
        "how",
        "all",
        "one",
        "two",
        "three",
        "also",
        "can",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "do",
        "did",
        "such",
        "than",
        "then",
        "so",
        "if",
        "about",
        "up",
        "out",
        "more",
        "very",
        "just",
        "into",
        "over",
        "after",
        "before",
        "between",
        "through",
        "page",
        "pages",
        "copyright",
        "rights",
        "reserved",
        "published",
        "publisher",
        "publication",
        "press",
        "edition",
        "printing",
        "printed",
        "reprinted",
        "isbn",
        "library",
        "congress",
        "cataloging",
        "university",
        "college",
        "journal",
        "volume",
        "issue",
        "series",
        "revised",
        "translated",
        "author",
        "authors",
        "editor",
        "editors",
        "foreword",
        "preface",
        "introduction",
        "conclusion",
        "chapter",
        "chapters",
        "section",
        "part",
        "figure",
        "table",
        "appendix",
        "references",
        "bibliography",
        "index",
        "acknowledgments",
        "acknowledgements",
        "dedication",
        "contents",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "however",
        "therefore",
        "thus",
        "hence",
        "whereas",
        "although",
        "despite",
        "whether",
        "both",
        "each",
        "every",
        "other",
        "another",
        "same",
        "different",
        "various",
        "many",
        "some",
        "most",
        "much",
        "less",
        "well",
        "often",
        "always",
        "never",
        "already",
        "still",
        "even",
        "only",
        "further",
        "example",
    }
)


def compute_metadata_child_levels(by_level: dict[int, list]) -> dict[int, tuple[int, int]]:
    """V0.02 (false-success RCA): the metadata-children exclusion rule, extracted
    from ``_filter_to_chapter_level`` so the chapter-selection DIALOG applies
    the SAME rule when listing selectable chapters (single source of truth).

    A deeper outline level whose entries mostly (≥80%) START ON THE SAME PAGE
    as a shallower level's entries is a per-parent annotation level — the
    classic case is "97 Things Every Programmer Should Know", where every
    chapter-title bookmark (level 0) has an author-name bookmark (level 1) on
    the SAME page. Listing those in the chapter selector let users "select"
    authors as chapters — the selected author entries then polluted page
    derivation and the selection could end up summarizing nothing while the
    pipeline still reported success (see the V0.02 changelog).

    Args:
        by_level: mapping ``level → list of (title, page, …)`` sequences
            (only index 1 — the page — is read; extra elements ignored).
            Built exactly like ``_filter_to_chapter_level`` builds it.

    Returns:
        ``{excluded_level: (same_page_count, total_entries)}`` in ascending
        level order. Never contains level 0 (a level-0 entry can never be a
        "child" of anything shallower — defensive, same as the inline code).
    """
    _shallow_pages: set[int] = set()
    _excluded: dict[int, tuple[int, int]] = {}
    for _lvl in sorted(by_level.keys()):
        _entries = by_level[_lvl]
        if _shallow_pages and _entries:
            _same_page = sum(1 for e in _entries if e[1] in _shallow_pages)
            if _same_page >= 0.8 * len(_entries):
                _excluded[_lvl] = (_same_page, len(_entries))
                # Do NOT feed this level's pages forward as shallow pages —
                # an excluded annotation level must not "protect" deeper
                # real levels from exclusion (same as the inline rule).
                continue
        _shallow_pages.update(e[1] for e in _entries)
    _excluded.pop(0, None)
    return _excluded


class Segmenter:
    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
        toc_entries: list[tuple[str, int]] | TOCResult | list[TOCEntry] | None = None,
    ):
        """
        Args:
            request: ConversionRequest with all settings.
            log_callback: logging function.
            toc_entries: Can be:
                - list of (heading, page) tuples (from legacy extractor)
                - TOCResult (from toc_extractor.locate_headings)
                - list of TOCEntry objects (with line numbers already matched)
        """
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._raw_toc_entries = toc_entries
        self.heading_segmenter = HeadingSegmenter(request, log_callback)
        self.semantic_segmenter = SemanticSegmenter(request, log_callback)
        self.token_segmenter = TokenSegmenter(request)

        # Normalise toc_entries into a list of TOCEntry objects (with optional line)
        self.toc_entries = self._normalise_toc_entries(toc_entries)

        # Detect if entries already have line numbers (i.e., located)
        self._toc_has_located_lines = False
        if self.toc_entries:
            self._toc_has_located_lines = any(e.line is not None for e in self.toc_entries)

        # Determine MIN_SEGMENT_TOKENS based on source type
        self.MIN_SEGMENT_TOKENS = get_min_segment_tokens(request)

    def _normalise_toc_entries(self, toc_data) -> list[TOCEntry]:
        """Convert various input formats to list of TOCEntry."""
        if not toc_data:
            return []

        # If it's already a TOCResult, extract its entries
        if isinstance(toc_data, TOCResult):
            return toc_data.entries

        # If it's a list of TOCEntry objects
        if isinstance(toc_data, list) and all(isinstance(e, TOCEntry) for e in toc_data):
            return toc_data

        # If it's a list of (heading, page) tuples
        if isinstance(toc_data, list) and all(
            isinstance(e, tuple) and len(e) == 2 for e in toc_data
        ):
            return [TOCEntry(title=h, page=p if p > 0 else None) for h, p in toc_data]

        # Fallback: empty
        self.log("[Segmenter] Unrecognised TOC format – treating as empty.", "WARNING")
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_chapter_number(self, heading: str) -> float:
        if not heading:
            return float("inf")
        m = re.search(r"(?:Chapter|Section|فصل|بخش)\s+(\d+(?:\.\d+)?)", heading, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        m = re.search(r"^\s*(\d+(?:\.\d+)?)", heading)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        persian = {
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
        }
        m = re.search(r"(?:فصل|بخش)\s+([۰-۹]+)", heading)
        if m:
            try:
                return float("".join(persian.get(c, c) for c in m.group(1)))
            except ValueError:
                pass
        return float("inf")

    # ─────────────────────────────────────────────────────────────────────────
    # V13.32.8: 3-Layer Chapter-Level Segmentation + tuple-compatible helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _toc_entry_title(e) -> str:
        if hasattr(e, "title"):
            return e.title
        elif isinstance(e, (tuple, list)) and len(e) >= 1:
            return e[0]
        return ""

    @staticmethod
    def _toc_entry_page(e):
        if hasattr(e, "page"):
            return e.page
        elif isinstance(e, (tuple, list)) and len(e) >= 2:
            return e[1]
        return None

    @staticmethod
    def _toc_entry_level(e) -> int:
        if hasattr(e, "level"):
            return e.level
        return 0

    def _has_outline_levels(self) -> bool:
        if not self.toc_entries:
            return False
        return any(self._toc_entry_level(e) > 0 for e in self.toc_entries)

    def _filter_to_chapter_level(self) -> list:
        """V18.3.3 (F3): prefer the most GRANULAR level that has real chapters.

        Before V18.3.3, this method kept ONLY level-0 (top-level) TOC entries.
        For books with a Part/Chapter hierarchy (Parts at level 0, Chapters at
        level 1), this kept the PARTS and discarded the CHAPTERS — the user
        could never select a chapter because the segmenter only had parts.

        Now: if level-1+ entries exist AND look like real chapters (contain
        "chapter", "lesson", a number, etc.), prefer them over level-0 entries.
        If level-1 entries don't exist or look like front-matter (Dedication,
        Epigraph, etc.), fall back to level 0.
        """
        if not self.toc_entries:
            return []

        # V18.3.3 (F3): group entries by level.
        by_level: dict[int, list] = {}
        for e in self.toc_entries:
            _p = self._toc_entry_page(e)
            if _p is None or _p <= 0:
                continue
            _lvl = self._toc_entry_level(e)
            by_level.setdefault(_lvl, []).append((self._toc_entry_title(e), _p, e))

        if not by_level:
            return []

        # V18.3.3 (F3): determine which level to use.
        # If there are entries at level 1+ (sub-entries), check if they look
        # like real chapters (not just front-matter). If yes, prefer them —
        # the user almost certainly wants to select by chapter, not by part.
        _FRONT_MATTER = {
            "dedication",
            "epigraph",
            "contents",
            "table of contents",
            "copyright",
            "title page",
            "about the author",
            "about the publisher",
            "acknowledgments",
            "acknowledgements",
            "author's note",
            "author note",
            "front matter",
            "cover",
        }

        # V18.20.4.10 (P0-b1): exclude "metadata children" levels BEFORE the
        # real-chapter scan. A deeper outline level whose entries mostly START
        # ON THE SAME PAGE as a shallower level's entries is a per-parent
        # annotation level — the classic case is "97 Things Every Programmer
        # Should Know", where every chapter-title bookmark (level 0) has an
        # author-name bookmark (level 1) on the SAME page:
        #     level 0: "Act with Prudence" (p.28)
        #     level 1:   "Seb Rose"        (p.28)
        # The V18.3.3 heuristic preferred level 1 ("Kevlin Henney" and
        # "Robert C. Martin (Uncle Bob)" are >10 chars → "real chapters"),
        # the 97 two-page author segments then cascaded through
        # _merge_short_chapters into ONE whole-book segment (see P0-b2), and
        # the summarizer entered a 675,817-token map-reduce that stalled the
        # pipeline for hours. Sub-SECTION levels survive this filter: a
        # section heading usually starts mid-chapter on its own page, so only
        # the first section of each chapter shares the chapter's start page
        # (≪80%). The Parts/Chapters shape also survives: a chapter start
        # page rarely equals a part start page.
        # V0.02: the rule now lives in ``compute_metadata_child_levels``
        # (module level above) — shared with the chapter-selection dialog —
        # behavior byte-identical.
        _mc_excluded = compute_metadata_child_levels(by_level)
        for _lvl, (_mc_sp, _mc_tot) in _mc_excluded.items():
            self.log(
                f"  [Segmenter] Layer 1: level {_lvl} excluded — "
                f"{_mc_sp}/{_mc_tot} entries start on the same "
                f"page as a shallower bookmark (metadata children such as "
                f"per-chapter author names, not chapters).",
                "INFO",
            )
        _excluded_levels: set[int] = set(_mc_excluded)

        def _is_real_chapter(title: str) -> bool:
            """True if the title looks like a real chapter (not front-matter)."""
            t = title.strip().lower()
            if not t or len(t) < 3:
                return False
            if t in _FRONT_MATTER:
                return False
            # "Chapter N", "Lesson N", "N. Title", "N Title", "Part N"
            if re.match(r"^(chapter|lesson|section|part)\s+\d+", t):
                return True
            if re.match(r"^\d+[\.\s\-]", t):
                return True
            # Any non-front-matter title with >10 chars is probably a real chapter
            if len(t) > 10:
                return True
            return False

        # Find the deepest level that has real chapters
        # V18.20.4.10 (P0-b1): skip metadata-children levels (see above).
        _chosen_level = 0
        for _lvl in sorted(by_level.keys()):
            if _lvl in _excluded_levels:
                continue
            entries_at_level = by_level[_lvl]
            real_chapters = [e for e in entries_at_level if _is_real_chapter(e[0])]
            if real_chapters:
                _chosen_level = _lvl

        # Extract the chosen level's entries (title, page)
        chapter_entries = [(e[0], e[1]) for e in by_level.get(_chosen_level, [])]

        if _chosen_level > 0:
            self.log(
                f"  [Segmenter] Layer 1: PDF outline has hierarchy — using level "
                f"{_chosen_level} ({len(chapter_entries)} entries, preferred over "
                f"level 0 because it has real chapters).",
                "INFO",
            )
        else:
            self.log(
                f"  [Segmenter] Layer 1: PDF outline has hierarchy — filtered to "
                f"{len(chapter_entries)} chapter-level entries (from {len(self.toc_entries)} total).",
                "INFO",
            )
        return chapter_entries

    def _filter_by_chapter_numbers(self) -> list:
        if not self.toc_entries:
            return []
        _STANDALONE = {
            "foreword",
            "preface",
            "acknowledgments",
            "introduction",
            "references",
            "bibliography",
            "index",
            "appendix",
            "conclusion",
            "afterword",
            "prologue",
            "epilogue",
            "about the author",
            "glossary",
        }
        chapter_entries = []
        for e in self.toc_entries:
            _page = self._toc_entry_page(e)
            if _page is None or _page <= 0:
                continue
            title = self._toc_entry_title(e).strip()
            title_lower = title.lower()
            has_primary = bool(re.match(r"^\d+\s*[-\u2013\u2014.:]\s+", title))
            has_chapter_word = bool(re.match(r"^(chapter|section)\s+\d+", title, re.IGNORECASE))
            # V13.33.5: has_bare removed — matched "10 -", "11 -" as chapters
            is_standalone = title_lower in _STANDALONE
            if has_primary or has_chapter_word or is_standalone:
                chapter_entries.append((title, _page))
        if chapter_entries:
            self.log(
                f"  [Segmenter] Layer 2: chapter-number filter \u2014 kept {len(chapter_entries)} chapter-level entries (from {len(self.toc_entries)} total).",
                "INFO",
            )
        return chapter_entries

    def _segment_by_chapters(self, markdown_text, total_pages, page_markers, chapter_entries):
        if not chapter_entries or not page_markers:
            return []
        page_to_pos = dict(page_markers)
        page_to_pos[total_pages + 1] = len(markdown_text)
        chapter_entries.sort(key=lambda x: x[1])
        deduped = []
        last_page = 0
        for heading, page in chapter_entries:
            if page != last_page:
                deduped.append((heading, page))
                last_page = page
        if len(deduped) < 2:
            return []
        # V0.03 (P0-4): the LAST chapter entry ends at the LAST EXTRACTED
        # page, not total_pages. With a selection-filtered TOC the extracted
        # markdown only contains the selected pages — the old `total_pages`
        # fallback made the last selected chapter claim the rest of the book
        # in its metadata (pages 15–119 for a 2-page essay in the V0.02 rig
        # shape). For full-book runs every page has a marker, so the max is
        # total_pages — behavior unchanged there.
        _last_extracted_page = max(
            (p for p in page_to_pos if p <= total_pages), default=total_pages
        )
        segments = []
        for idx, (heading, start_page) in enumerate(deduped):
            end_page = deduped[idx + 1][1] - 1 if idx + 1 < len(deduped) else _last_extracted_page
            if end_page < start_page:
                end_page = start_page
            # V18.20.4.10 (P0-b3): a missing start-page marker must resolve
            # to the NEAREST FOLLOWING marker — the old ``get(start_page, 0)``
            # fallback silently sliced from position 0, i.e. the segment
            # swallowed the WHOLE BOOK from the top (the '97 Things' Seg 1
            # carried 692,442 tokens because of exactly this). A missing
            # marker now yields at most an empty segment (which the
            # summarizer's <80-token gate fails loudly), never duplicated
            # content.
            start_pos = page_to_pos.get(start_page)
            if start_pos is None:
                _next_marker_page = min((p for p in page_to_pos if p > start_page), default=None)
                start_pos = (
                    page_to_pos[_next_marker_page]
                    if _next_marker_page is not None
                    else len(markdown_text)
                )
                self.log(
                    f"  [Segmenter] Page {start_page} has no marker for '{heading[:40]}' "
                    f"— starting at nearest following marker (page {_next_marker_page}).",
                    "DEBUG",
                )
            end_pos = page_to_pos.get(end_page + 1, len(markdown_text))
            # V18.20.4.10 (P0-b3): inverted bounds now yield EMPTY content
            # (visible, honest) instead of the whole tail from start_pos
            # (the old fallback duplicated the rest of the book into this
            # segment AND every later segment).
            content = markdown_text[start_pos:end_pos].strip() if start_pos < end_pos else ""
            segments.append(
                Segment(heading=heading, content=content, start_page=start_page, end_page=end_page)
            )
        self.log(
            f"  [Segmenter] Created {len(segments)} chapter-level segments (no sub-section splitting, no merging needed).",
            "INFO",
        )
        return segments

    def _merge_short_chapters(self, segments, min_pages=5, max_merge_pages=None):
        """Merge sub-``min_pages`` segments into their predecessor.

        V18.20.4.10 (P0-b2): the merge accumulator is now BOUNDED by
        ``max_merge_pages`` (default ``2 × min_pages``). Before this fix,
        EVERY short segment merged into ``merged[-1]`` with no size limit —
        in a book where every chapter is short ("97 Things": 97 two-page
        essays), the first segment accumulated ALL of them: the V18.20.4.9
        log shows 95 consecutive "merged short segment '…' into 'Seb Rose'"
        lines producing ONE 692,442-token whole-book segment, which the
        summarizer routed into a 675,817-token map-reduce that stalled the
        pipeline for hours. With the cap, short segments group until the
        group spans ~``max_merge_pages`` pages, then a new group starts.
        A short fragment following an already-large segment now stands
        alone (keeping its own real TOC heading) instead of being absorbed.

        V0.03 (P0-4, real-rig audit): the merge is DISABLED entirely when
        the user explicitly selected chapters. The V0.02 rig selected 10
        numbered essays; Layer 3 merged 7 of them into segment 1, and the
        run shipped 2 mislabeled mega-summaries ("eight core principles"
        under the heading of thing 1). GENERAL rule: an explicit selection
        IS the requested structure — each selected TOC entry stays its own
        segment. Merging remains available for full-book runs, where it
        protects against 1-page TOC fragments.
        """
        # V0.03 (P0-4): never merge explicitly selected chapters.
        if getattr(self.request, "selected_chapters", None):
            self.log(
                "  [Segmenter] Layer 3: short-segment merge SKIPPED — explicit "
                "chapter selection active (each selected entry stays its own "
                "segment; V0.03 P0-4).",
                "INFO",
            )
            return segments
        if len(segments) <= 2:
            return segments
        if max_merge_pages is None:
            max_merge_pages = min_pages * 2
        merged = [segments[0]]
        for seg in segments[1:-1]:
            page_count = seg.end_page - seg.start_page + 1
            if page_count < min_pages:
                prev = merged[-1]
                prev_pages = prev.end_page - prev.start_page + 1
                # V18.20.4.10 (P0-b2): bounded accumulator — stop the cascade.
                if prev_pages + page_count > max_merge_pages:
                    merged.append(seg)
                    self.log(
                        f"  [Segmenter] Layer 3: short segment '{seg.heading[:40]}' "
                        f"({page_count} pages) kept separate — merging into "
                        f"'{prev.heading[:40]}' ({prev_pages} pages) would exceed "
                        f"the {max_merge_pages}-page merge cap (cascade guard).",
                        "DEBUG",
                    )
                    continue
                prev.content = (prev.content + "\n\n" + seg.content).strip()
                prev.end_page = seg.end_page
                # V18.3.3 (F2): preserve the merged heading as an alias.
                if seg.heading and seg.heading != prev.heading:
                    if prev.aliases is None:
                        prev.aliases = []
                    if seg.heading not in prev.aliases:
                        prev.aliases.append(seg.heading)
                # Also carry over any aliases the merged segment had.
                for alias in getattr(seg, "aliases", None) or []:
                    if alias and alias != prev.heading and alias not in prev.aliases:
                        prev.aliases.append(alias)
                self.log(
                    f"  [Segmenter] Layer 3: merged short segment '{seg.heading[:40]}' ({page_count} pages) into '{prev.heading[:40]}'.",
                    "DEBUG",
                )
            else:
                merged.append(seg)
        merged.append(segments[-1])
        if len(merged) < len(segments):
            self.log(
                f"  [Segmenter] Layer 3: merged {len(segments) - len(merged)} short segment(s).",
                "INFO",
            )
        return merged

    @staticmethod
    def _better_heading(a: str, b: str) -> str:
        def clean(s: str) -> str:
            return re.sub(r" {2,}", " ", s).strip()

        ha, hb = clean(a), clean(b)
        return ha if len(ha.replace(" ", "")) >= len(hb.replace(" ", "")) else hb

    def _sort_segments(self, segments: list[Segment]) -> list[Segment]:
        if not segments:
            return segments
        numbered = [s for s in segments if self._extract_chapter_number(s.heading) != float("inf")]
        unnumbered = [
            s for s in segments if self._extract_chapter_number(s.heading) == float("inf")
        ]
        if not numbered:
            return sorted(segments, key=lambda s: s.start_page)
        numbered_sorted = sorted(
            numbered, key=lambda s: (self._extract_chapter_number(s.heading), s.start_page)
        )
        unnumbered_sorted = sorted(unnumbered, key=lambda s: s.start_page)
        result: list[Segment] = []
        u = 0
        for chap in numbered_sorted:
            while u < len(unnumbered_sorted) and unnumbered_sorted[u].start_page < chap.start_page:
                result.append(unnumbered_sorted[u])
                u += 1
            result.append(chap)
        while u < len(unnumbered_sorted):
            result.append(unnumbered_sorted[u])
            u += 1
        return result

    def _recalc_page_bounds(self, segment: Segment) -> None:
        markers = extract_page_markers(segment.content)
        if markers:
            segment.start_page = markers[0][0]
            segment.end_page = markers[-1][0]

    # ─────────────────────────────────────────────────────────────────────────
    # Keyword extraction and overlap (Phase 2.3)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_keywords(self, text: str, n: int = 30) -> list[str]:
        """Extract top n keywords from text (excluding stopwords)."""
        if not text:
            return []
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        counts: dict[str, int] = {}
        for w in words:
            if w not in _STOPWORDS:
                counts[w] = counts.get(w, 0) + 1
        sorted_words = sorted(counts, key=lambda w: counts[w], reverse=True)
        return sorted_words[:n]

    def _compute_heading_content_overlap(self, heading: str, content: str) -> float:
        """
        Compute the overlap ratio between heading keywords and content keywords.
        Returns 0.0 if either has no keywords, or the ratio of heading keywords
        that appear in the content's keyword set.
        """
        heading_keywords = set(self._extract_keywords(heading, n=15))
        content_keywords = set(self._extract_keywords(content, n=50))
        if not heading_keywords or not content_keywords:
            return 0.0
        overlap = len(heading_keywords.intersection(content_keywords))
        return overlap / len(heading_keywords)

    # ─────────────────────────────────────────────────────────────────────────
    # Enforce contiguity and fix overlaps/gaps
    # ─────────────────────────────────────────────────────────────────────────

    def _enforce_contiguity(
        self,
        segments: list[Segment],
        total_pages: int,
        markdown_text: str,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        if not segments:
            return segments

        sorted_segs = sorted(segments, key=lambda s: s.start_page)
        fixed: list[Segment] = []
        current_page = 1
        previous_end = 0

        page_to_pos = dict(page_markers)
        page_to_pos[total_pages + 1] = len(markdown_text)

        for seg in sorted_segs:
            if seg.start_page <= previous_end:
                # V10.1.16: Instead of pushing this segment's start page
                # forward (which cascades and pushes everything beyond the
                # PDF), TRIM the PREVIOUS segment's end page so there's no
                # overlap.  This keeps each segment on its own pages.
                #
                # The old code did: new_start = previous_end + 1
                #   → if previous_end was 17 (full PDF), new_start = 18 (phantom)
                #
                # The new code: trim the previous segment to end at
                # seg.start_page - 1, so both segments have valid page ranges.
                if previous_end > 0 and len(sorted_segs) > 1:
                    # Find the previous segment and trim its end page
                    for prev_seg in sorted_segs:
                        if prev_seg.end_page == previous_end and prev_seg is not seg:
                            prev_seg.end_page = max(prev_seg.start_page, seg.start_page - 1)
                            self.log(
                                f"  ✂️ Trimmed '{prev_seg.heading[:30]}' end page "
                                f"{previous_end} → {prev_seg.end_page} to resolve overlap "
                                f"with '{seg.heading[:30]}'",
                                "INFO",
                            )
                            # Recalculate the previous segment's content
                            start_pos = page_to_pos.get(prev_seg.start_page, 0)
                            end_pos = page_to_pos.get(prev_seg.end_page + 1, len(markdown_text))
                            if end_pos > start_pos:
                                prev_seg.content = markdown_text[start_pos:end_pos].strip()
                                self._recalc_page_bounds(prev_seg)
                            previous_end = prev_seg.end_page
                            break

                # Now check if this segment's start is still overlapping
                if seg.start_page <= previous_end:
                    new_start = previous_end + 1
                    if new_start > total_pages:
                        self.log(
                            f"  ⚠️ Overlap cascade: '{seg.heading[:30]}' would start at "
                            f"page {new_start} but PDF only has {total_pages} pages. "
                            f"Skipping this segment (phantom).",
                            "WARNING",
                        )
                        seg.content = ""
                        seg.start_page = total_pages + 1  # mark as invalid
                        seg.end_page = total_pages + 1
                        continue
                    self.log(
                        f"  ⚠️ Overlap detected: '{seg.heading[:30]}' start page {seg.start_page} <= previous end {previous_end}. Adjusting start to {new_start}",
                        "WARNING",
                    )
                    seg.start_page = new_start
                    if new_start <= total_pages:
                        start_pos = page_to_pos.get(new_start, 0)
                        if seg.end_page < new_start:
                            seg.end_page = new_start
                        end_pos = page_to_pos.get(seg.end_page + 1, len(markdown_text))
                        if end_pos > start_pos:
                            new_content = markdown_text[start_pos:end_pos].strip()
                            if new_content:
                                seg.content = new_content
                                self._recalc_page_bounds(seg)
                                self.log(
                                    f"  ✅ Content trimmed and recalculated for '{seg.heading[:30]}'",
                                    "INFO",
                                )
                    if not seg.content.strip():
                        seg.content = (
                            f"[No content extracted for pages {seg.start_page}–{seg.end_page}]"
                        )
            else:
                pass

            if seg.start_page > current_page:
                gap_heading = f"Gap (pages {current_page}–{seg.start_page - 1})"
                gap_content = (
                    f"[No content extracted for pages {current_page}–{seg.start_page - 1}]"
                )
                gap_seg = Segment(
                    heading=gap_heading,
                    content=gap_content,
                    start_page=current_page,
                    end_page=seg.start_page - 1,
                    segment_type="chunk",
                )
                fixed.append(gap_seg)
                self.log(f"  📄 Created gap segment: {gap_heading}", "INFO")

            if seg.end_page < seg.start_page:
                seg.end_page = seg.start_page

            fixed.append(seg)
            current_page = seg.end_page + 1
            previous_end = seg.end_page

        if current_page <= total_pages:
            gap_heading = f"Gap (pages {current_page}–{total_pages})"
            gap_content = f"[No content extracted for pages {current_page}–{total_pages}]"
            gap_seg = Segment(
                heading=gap_heading,
                content=gap_content,
                start_page=current_page,
                end_page=total_pages,
                segment_type="chunk",
            )
            fixed.append(gap_seg)
            self.log(f"  📄 Created trailing gap segment: {gap_heading}", "INFO")

        return fixed

    # ─────────────────────────────────────────────────────────────────────────
    # Manual segmentation creation
    # ─────────────────────────────────────────────────────────────────────────

    def _create_manual_segments(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
        manual_ranges: list[tuple[int, int]],
    ) -> list[Segment]:
        segments = []
        page_positions = {}
        for p, pos in page_markers:
            page_positions[p] = pos
        page_positions[total_pages + 1] = len(markdown_text)

        for idx, (start, end) in enumerate(manual_ranges, 1):
            start = max(1, start)
            end = min(total_pages, end)
            if start > end:
                continue
            start_pos = next((pos for p, pos in page_markers if p == start), 0)
            end_pos = next((pos for p, pos in page_markers if p == end + 1), len(markdown_text))
            content = markdown_text[start_pos:end_pos].strip()
            heading = f"Chapter {idx}"
            lines = content.splitlines()
            for line in lines:
                if line.strip().startswith("#"):
                    heading = line.strip().lstrip("#").strip()
                    break
            segments.append(
                Segment(
                    heading=heading,
                    content=content,
                    start_page=start,
                    end_page=end,
                    segment_type="chapter",
                )
            )
        return segments

    # ─────────────────────────────────────────────────────────────────────────
    # Pass 0 — TOC burst filter (only used in fallback)
    # ─────────────────────────────────────────────────────────────────────────

    def _remove_toc_bursts(self, segments: list[Segment]) -> list[Segment]:
        TOC_BURST_MIN = 4
        TOC_MAX_TOKENS = 20
        if not segments:
            return segments

        runs: list = []
        i = 0
        while i < len(segments):
            if count_tokens(segments[i].content) <= TOC_MAX_TOKENS:
                j = i
                while j < len(segments) and count_tokens(segments[j].content) <= TOC_MAX_TOKENS:
                    j += 1
                if j - i >= TOC_BURST_MIN:
                    runs.append((i, j - 1))
                i = j
            else:
                i += 1

        if not runs:
            return segments

        to_remove: set = set()
        for start, end in runs:
            preview = [segments[k].heading[:35] for k in range(start, end)]
            self.log(
                f"  [Segmenter] ⚠️ TOC burst: discarding {end - start} near-empty stubs "
                f"→ keeping '{segments[end].heading[:35]}'. Removed: {preview[:3]}{'…' if len(preview) > 3 else ''}",
                "WARNING",
            )
            for k in range(start, end):
                to_remove.add(k)

        result = [s for idx, s in enumerate(segments) if idx not in to_remove]
        if to_remove:
            self.log(f"  [Segmenter] TOC filter: {len(segments)} → {len(result)} segments", "INFO")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Pass 1 — Short segment merge with keyword-overlap check
    # ─────────────────────────────────────────────────────────────────────────

    def _merge_short_segments(self, segments: list[Segment]) -> list[Segment]:
        """
        Merge segments that are either:
        - Too short in token count (< MIN_SEGMENT_TOKENS), OR
        - Have low keyword overlap between heading and content (< KEYWORD_OVERLAP_THRESHOLD)

        V10.0.1: After merging, enforce a HARD minimum of 80 tokens on every
        segment.  Segments below 80 tokens are merged with the NEXT segment
        regardless of heading overlap — this prevents hallucination-prone
        near-empty segments from reaching the summarizer.
        """
        if not segments:
            return segments

        # V10.0.1: Hard minimum — 80 tokens.  Below this, the LLM will
        # hallucinate (it has essentially no source text to work with).
        HARD_MIN_TOKENS = 80

        result: list[Segment] = []
        i = 0

        while i < len(segments):
            seg = segments[i]
            tok = count_tokens(seg.content)
            # Compute heading-content overlap
            overlap = self._compute_heading_content_overlap(seg.heading, seg.content)

            # Condition: too short OR false-positive heading (low overlap)
            # V10.0.1: also merge if below HARD_MIN_TOKENS regardless of preset
            is_short = tok < self.MIN_SEGMENT_TOKENS
            is_hard_short = tok < HARD_MIN_TOKENS
            is_false_positive = overlap < KEYWORD_OVERLAP_THRESHOLD

            if (is_short or is_false_positive or is_hard_short) and i + 1 < len(segments):
                nxt = segments[i + 1]
                # V18.3.3 (F2): preserve the LOST heading as an alias on the
                # merged segment. _better_heading picks the "better" heading
                # to keep as the primary; the other becomes an alias. This
                # ensures the matcher can still find the merged segment by
                # EITHER heading (e.g. if "Dedication" was merged into "Title
                # Page", the user can still match on "Dedication").
                _better = self._better_heading(seg.heading, nxt.heading)
                _worse = seg.heading if _better == nxt.heading else nxt.heading
                _merged_aliases = list(getattr(seg, "aliases", []) or []) + list(
                    getattr(nxt, "aliases", []) or []
                )
                if _worse and _worse != _better:
                    _merged_aliases.append(_worse)
                merged = Segment(
                    heading=_better,
                    content=(seg.content.strip() + "\n\n" + nxt.content.strip()).strip(),
                    start_page=seg.start_page,
                    end_page=nxt.end_page,
                    segment_type="chapter",
                    aliases=_merged_aliases,
                )
                self._recalc_page_bounds(merged)
                reason = []
                if is_hard_short:
                    reason.append(f"{tok} tokens (< {HARD_MIN_TOKENS} HARD MINIMUM)")
                elif is_short:
                    reason.append(f"{tok} tokens (< {self.MIN_SEGMENT_TOKENS})")
                if is_false_positive:
                    reason.append(f"overlap {overlap:.0%} (< {KEYWORD_OVERLAP_THRESHOLD:.0%})")
                self.log(
                    f"  [Segmenter] Merged '{seg.heading[:35]}' → '{merged.heading[:35]}' "
                    f"({', '.join(reason)})",
                    "INFO",
                )
                result.append(merged)
                i += 2
                continue

            # Keep the segment
            seg.heading = re.sub(r" {2,}", " ", seg.heading).strip()
            result.append(seg)
            i += 1

        # V10.0.1: Final pass — if any segment in the result is still below
        # HARD_MIN_TOKENS (e.g., it was the last segment and couldn't merge
        # forward), merge it with the PREVIOUS segment.
        if len(result) > 1:
            final: list[Segment] = [result[0]]
            for seg in result[1:]:
                if count_tokens(seg.content) < HARD_MIN_TOKENS:
                    prev = final[-1]
                    prev.content = (prev.content.strip() + "\n\n" + seg.content.strip()).strip()
                    prev.end_page = seg.end_page
                    self._recalc_page_bounds(prev)
                    self.log(
                        f"  [Segmenter] V10.0.1: Merged '{seg.heading[:35]}' backward "
                        f"(below {HARD_MIN_TOKENS} token hard minimum)",
                        "WARNING",
                    )
                else:
                    final.append(seg)
            result = final

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Pass 2 — iterative same-chapter-number merge (fallback only)
    # ─────────────────────────────────────────────────────────────────────────

    def _merge_same_chapter_number(self, segments: list[Segment]) -> list[Segment]:
        if not segments:
            return segments
        changed = True
        while changed:
            changed = False
            result: list[Segment] = []
            i = 0
            while i < len(segments):
                seg = segments[i]
                if i + 1 < len(segments):
                    nxt = segments[i + 1]
                    n1 = self._extract_chapter_number(seg.heading)
                    n2 = self._extract_chapter_number(nxt.heading)
                    if n1 == n2 and n1 != float("inf"):
                        merged = Segment(
                            heading=self._better_heading(seg.heading, nxt.heading),
                            content=(seg.content.strip() + "\n\n" + nxt.content.strip()).strip(),
                            start_page=seg.start_page,
                            end_page=nxt.end_page,
                            segment_type="chapter",
                        )
                        self._recalc_page_bounds(merged)
                        self.log(
                            f"  [Segmenter] Merged dup ch.{int(n1)}: '{seg.heading[:30]}' + '{nxt.heading[:30]}'",
                            "INFO",
                        )
                        result.append(merged)
                        i += 2
                        changed = True
                        continue
                result.append(seg)
                i += 1
            segments = result
        return segments

    # ─────────────────────────────────────────────────────────────────────────
    # Pass 3 — Merge duplicate headings (NEW)
    # ─────────────────────────────────────────────────────────────────────────

    def _merge_duplicate_headings(self, segments: list[Segment]) -> list[Segment]:
        """
        Merge consecutive segments with the same heading.
        C4 fix: compare on the FULL original heading (case-insensitive,
        whitespace-normalised) — NOT the aggressively normalized form that
        strips "Chapter N" prefixes.  Previously, "Chapter 1: Methods" and
        "Chapter 2: Methods" both normalized to "methods" and were wrongly
        merged into one chapter, losing content.
        """
        if not segments:
            return segments

        def _full_norm(h: str) -> str:
            """Lightweight normalisation: lowercase + collapse whitespace only."""
            return re.sub(r"\s+", " ", h.strip().lower())

        merged = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            j = i + 1
            norm = _full_norm(seg.heading)
            # Look ahead for consecutive segments with the same full heading
            while j < len(segments) and _full_norm(segments[j].heading) == norm:
                # Merge content
                seg.content = (seg.content.strip() + "\n\n" + segments[j].content.strip()).strip()
                # Extend end_page to the merged segment's end
                if segments[j].end_page > seg.end_page:
                    seg.end_page = segments[j].end_page
                # Also merge segment_type if any is "chapter" (prefer chapter over chunk)
                if segments[j].segment_type == "chapter":
                    seg.segment_type = "chapter"
                self.log(
                    f"  [Segmenter] Merged duplicate heading '{seg.heading[:40]}' (was {j - i + 1} segments)",
                    "INFO",
                )
                j += 1
            merged.append(seg)
            i = j

        if len(merged) < len(segments):
            self.log(
                f"  [Segmenter] Reduced {len(segments)} → {len(merged)} segments by merging duplicate headings.",
                "INFO",
            )
        return merged

    # ─────────────────────────────────────────────────────────────────────────
    # TOC heading update (used in fallback)
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_toc_headings(self, segments: list[Segment]) -> list[Segment]:
        if not self.toc_entries:
            return segments
        toc_by_num: dict = {}
        toc_unnumbered: list = []
        toc_heading_norms: set = set()
        for e in self.toc_entries:
            h = e.title
            p = e.page if e.page is not None else 0
            toc_heading_norms.add(re.sub(r"\s+", " ", h).strip().lower())
            n = self._extract_chapter_number(h)
            if n != float("inf"):
                toc_by_num[n] = h
            else:
                toc_unnumbered.append((h, p))
        updated = 0
        for seg in segments:
            # V0.07 (output-regression fix): a segment already carrying an
            # EXACT TOC title is correctly titled — skip it. The page-
            # proximity repair used to re-title such segments with a
            # NEIGHBORING entry (±3-page tolerance): a chapter at p28 was
            # re-titled to the front-matter entry at p25, shifting every
            # subsequent title (latent bug, exposed once a full TOC reaches
            # the TOC-driven path again).
            if re.sub(r"\s+", " ", seg.heading).strip().lower() in toc_heading_norms:
                continue
            n = self._extract_chapter_number(seg.heading)
            if n != float("inf") and n in toc_by_num:
                if toc_by_num[n] != seg.heading:
                    self.log(f"  [TOC] '{seg.heading}' → '{toc_by_num[n][:50]}'", "INFO")
                    seg.heading = toc_by_num[n]
                    updated += 1
            else:
                # V0.07: page-proximity repair — pick the NEAREST entry, not
                # the FIRST within ±3 pages (first-match stole neighbor titles).
                _best = None
                for th, tp in toc_unnumbered:
                    if tp > 0:
                        _d = abs(seg.start_page - tp)
                        if _d <= 3 and (_best is None or _d < _best[0]):
                            _best = (_d, th)
                if _best is not None and _best[1] != seg.heading:
                    self.log(f"  [TOC] (page) '{seg.heading}' → '{_best[1][:50]}'", "INFO")
                    seg.heading = _best[1]
                    updated += 1
        if updated:
            self.log(f"  [TOC] Applied {updated} heading update(s) from TOC.", "INFO")
        return segments

    # ─────────────────────────────────────────────────────────────────────────
    # ── Helper: Map character position to page using binary search ────────
    # ─────────────────────────────────────────────────────────────────────────

    def _get_page_for_char_pos(
        self, char_pos: int, page_markers: list[tuple[int, int]], total_pages: int
    ) -> int:
        """
        Find the page number for a given character position using binary search on page markers.
        Returns 1 if markers are empty or char_pos is before the first marker.
        Returns total_pages if char_pos is after the last marker.
        """
        if not page_markers:
            return 1

        # page_markers is list of (page_num, char_position) sorted by char_position
        # We want the page whose marker position is <= char_pos, and the next marker > char_pos.
        lo, hi = 0, len(page_markers) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            _, pos = page_markers[mid]
            if pos <= char_pos:
                lo = mid + 1
            else:
                hi = mid - 1

        # lo is the first index with pos > char_pos, so the page is at lo-1
        idx = max(0, lo - 1)
        page = page_markers[idx][0]
        # Clamp to valid range
        return max(1, min(page, total_pages))

    # ─────────────────────────────────────────────────────────────────────────
    # ── Helper: Compute character position of the start of a line ────────
    # ─────────────────────────────────────────────────────────────────────────

    def _get_char_pos_for_line(self, line_no: int, lines: list[str]) -> int:
        """Return the character position of the start of the given line."""
        if line_no <= 0:
            return 0
        if line_no >= len(lines):
            return sum(len(line) for line in lines)
        return sum(len(lines[i]) for i in range(line_no))

    # ─────────────────────────────────────────────────────────────────────────
    # Segment using pre‑located TOC entries (from TocExtractor.locate_headings)
    # WITH confidence‑based filtering and binary search page mapping
    # NEW: Lower confidence threshold to keep more sections.
    # ─────────────────────────────────────────────────────────────────────────

    def _segment_with_located_headings(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        """
        Build segments using TOCEntry objects that already have line numbers.
        Applies confidence filtering with lower threshold:
        - confidence >= 0.7: use directly
        - 0.3 <= confidence < 0.7: use but warn
        - confidence < 0.3: discard and fall back to heading detection
        """
        if not self.toc_entries:
            return []

        # Filter entries that have a line number and high enough confidence
        located = []
        for e in self.toc_entries:
            if e.line is None:
                continue
            if e.confidence >= CONFIDENCE_HIGH:
                located.append(e)
            elif e.confidence >= CONFIDENCE_LOW:
                self.log(
                    f"  ⚠️ Low confidence ({e.confidence:.2f}) for '{e.title[:40]}' – using anyway (threshold lowered).",
                    "WARNING",
                )
                located.append(e)
            else:
                self.log(
                    f"  ⚠️ Very low confidence ({e.confidence:.2f}) for '{e.title[:40]}' – discarding.",
                    "WARNING",
                )

        if not located:
            self.log(
                "[Segmenter] No located TOC entries with confidence >= 0.3 – falling back.", "INFO"
            )
            return []

        # Sort by line
        located_sorted = sorted(located, key=lambda e: e.line)
        markers_sorted = sorted(page_markers, key=lambda x: x[1])
        lines = markdown_text.splitlines()

        segments = []

        for i, entry in enumerate(located_sorted):
            start_line = entry.line

            # ── FIX: end_line is the line of the NEXT heading (exclusive) ──
            if i + 1 < len(located_sorted):
                end_line = located_sorted[i + 1].line - 1  # Last line before next heading
            else:
                end_line = len(lines) - 1

            # ── FIX: If end_line < start_line, set end_line = start_line ──
            if end_line < start_line:
                end_line = start_line

            # Clamp to valid range
            if start_line >= len(lines):
                self.log(
                    f"  ⚠️ start_line {start_line} exceeds line count {len(lines)} for '{entry.title[:40]}'",
                    "WARNING",
                )
                continue
            if end_line >= len(lines):
                end_line = len(lines) - 1

            # Extract content
            content = "\n".join(lines[start_line : end_line + 1]).strip()

            # If content is empty, try to get at least some text
            if not content:
                self.log(
                    f"  ⚠️ Empty content for '{entry.title[:40]}' (lines {start_line}-{end_line}) – using fallback.",
                    "WARNING",
                )
                content = f"[No content extracted for this section]\n\n{entry.title}"

            # Compute character positions
            start_char = self._get_char_pos_for_line(start_line, lines)
            end_char = self._get_char_pos_for_line(end_line + 1, lines)

            # Map to pages
            start_page = self._get_page_for_char_pos(start_char, markers_sorted, total_pages)
            end_page = self._get_page_for_char_pos(
                end_char - 1 if end_char > start_char else start_char, markers_sorted, total_pages
            )

            if end_page < start_page:
                end_page = start_page

            seg = Segment(
                heading=entry.title,
                content=content,
                start_page=start_page,
                end_page=end_page,
                segment_type="chapter",
            )
            self._recalc_page_bounds(seg)
            segments.append(seg)

        if segments:
            self.log(f"[Segmenter] Located TOC segmentation: {len(segments)} segments.", "INFO")
        return segments

    # ─────────────────────────────────────────────────────────────────────────
    # Fuzzy heading matching (updated with rapidfuzz + window search)
    # Uses heading_utils for normalisation and fuzzy matching
    # FIX: IndexError – clamps start_line/end_line to valid range
    # ─────────────────────────────────────────────────────────────────────────

    def _find_heading_in_markdown(
        self,
        heading: str,
        markdown_text: str,
        start_pos: int = 0,
        fuzzy_threshold: float = 0.85,
        page_markers: list[tuple[int, int]] | None = None,
        suggested_page: int | None = None,
    ) -> tuple[int | None, str | None, float, str]:
        """
        Find heading in markdown using:
        - Exact match (regex) first.
        - Normalised exact match.
        - Fuzzy matching (rapidfuzz or difflib) with progressive thresholds.
        - If page_markers and suggested_page are given, search within a window.

        Returns (line_number, matched_text, confidence, match_method)
        """
        heading_stripped = heading.strip()
        if not heading_stripped:
            return None, None, 0.0, "failed"

        lines = markdown_text.splitlines(keepends=True)
        total_lines = len(lines)

        # If there are no lines, we cannot find anything
        if total_lines == 0:
            return None, None, 0.0, "failed"

        # Determine search window
        if page_markers and suggested_page is not None and suggested_page > 0:
            marker_map = dict(page_markers)
            marker_line = marker_map.get(suggested_page)
            if marker_line is not None:
                start_line = marker_line
                end_line = min(marker_line + 200, total_lines - 1)
            else:
                total_pages = max(p for p, _ in page_markers)
                estimated_line = int((suggested_page / total_pages) * total_lines)
                start_line = max(0, estimated_line - 150)
                end_line = min(total_lines - 1, estimated_line + 150)
        else:
            start_line = 0
            end_line = total_lines - 1

        # ── FIX: Clamp to valid range ──────────────────────────────────────
        start_line = max(0, min(start_line, total_lines - 1))
        end_line = max(0, min(end_line, total_lines - 1))
        if start_line > end_line:
            start_line, end_line = end_line, start_line

        # 1. Exact match (with optional # prefix)
        window_text = "".join(lines[start_line : end_line + 1])
        window_offset = sum(len(lines[i]) for i in range(start_line))

        pattern = re.compile(
            r"^(?:#+\s*)?" + re.escape(heading_stripped) + r"\s*$", re.MULTILINE | re.IGNORECASE
        )
        match = pattern.search(window_text)
        if match:
            pos = window_offset + match.start()
            # Find line number
            line_no = 0
            char_count = 0
            for i, line in enumerate(lines):
                if char_count <= pos < char_count + len(line):
                    line_no = i
                    break
                char_count += len(line)
            return line_no, match.group(0).strip(), 1.0, "exact"

        # 2. Normalised exact match
        normalised = normalize_heading(heading_stripped)
        if normalised and normalised != heading_stripped:
            pattern = re.compile(
                r"^(?:#+\s*)?" + re.escape(normalised) + r"\s*$", re.MULTILINE | re.IGNORECASE
            )
            match = pattern.search(window_text)
            if match:
                pos = window_offset + match.start()
                line_no = 0
                char_count = 0
                for i, line in enumerate(lines):
                    if char_count <= pos < char_count + len(line):
                        line_no = i
                        break
                    char_count += len(line)
                return line_no, match.group(0).strip(), 0.95, "normalised"

        # 3. Fuzzy matching with progressive thresholds
        candidates = get_heading_candidates(
            [line.rstrip("\n") for line in lines], start_line, end_line
        )

        if candidates:
            matched_line, matched_text, score, method = fuzzy_match_heading(
                heading,
                candidates,
                thresholds=[0.85, 0.75, 0.65],
                use_rapidfuzz=True,
            )
            if matched_line is not None:
                return matched_line, matched_text, score, method

        # 4. Global fallback (full text search)
        global_candidates = get_heading_candidates(
            [line.rstrip("\n") for line in lines],
            150,  # skip TOC area
            total_lines - 1,
        )
        if not global_candidates:
            global_candidates = get_heading_candidates(
                [line.rstrip("\n") for line in lines], 0, total_lines - 1
            )

        if global_candidates:
            matched_line, matched_text, score, method = fuzzy_match_heading(
                heading,
                global_candidates,
                thresholds=[0.65, 0.55],
                use_rapidfuzz=True,
            )
            if matched_line is not None:
                return matched_line, matched_text, score, method

        return None, None, 0.0, "failed"

    # ─────────────────────────────────────────────────────────────────────────
    # TOC‑driven segmentation (with fuzzy search and confidence filtering)
    # ─────────────────────────────────────────────────────────────────────────

    def _segment_by_toc(
        self, markdown_text: str, total_pages: int, page_markers: list[tuple[int, int]]
    ) -> list[Segment]:
        # V10.14.0 (D2): Try page-anchor segmentation FIRST (no text matching).
        # When the TOC entries have accurate page numbers (e.g. from the PDF's
        # native outline/bookmarks), we can split the markdown at page markers
        # directly — no fuzzy heading matching needed.  This eliminates the
        # 0/23 headings-located problem on OCR'd academic papers.
        if self.toc_entries and len(self.toc_entries) >= 2:
            page_anchor_segments = self._segment_by_toc_page_anchors(
                markdown_text, total_pages, page_markers
            )
            if page_anchor_segments and len(page_anchor_segments) >= 3:
                self.log(
                    f"[Segmenter] TOC page-anchor segmentation: created "
                    f"{len(page_anchor_segments)} segments (no fuzzy matching needed).",
                    "INFO",
                )
                return page_anchor_segments
            else:
                self.log(
                    "[Segmenter] TOC page-anchor segmentation produced <3 segments "
                    "— falling back to fuzzy-matched TOC.",
                    "DEBUG",
                )

        # Fallback: fuzzy-matched TOC segmentation (the original path)
        if not self.toc_entries or len(self.toc_entries) < 2:
            self.log("[Segmenter] TOC has fewer than 2 entries – cannot segment by TOC.", "INFO")
            return []

        toc_extractor = TocExtractor(log_callback=self.log)
        # Convert TOCEntry to tuples for validation
        toc_tuples = [(e.title, e.page if e.page is not None else 0) for e in self.toc_entries]
        corrected_toc = toc_extractor.validate_and_correct(
            toc_tuples,
            total_pages,
            markdown_text=markdown_text,
            page_markers=page_markers,
        )

        page_to_pos = dict(page_markers)
        page_to_pos[total_pages + 1] = len(markdown_text)

        segments = []
        last_pos = 0
        low_confidence_count = 0

        for idx, (heading, toc_page) in enumerate(corrected_toc):
            # Use the fuzzy search with window
            matched_line, matched_text, confidence, method = self._find_heading_in_markdown(
                heading,
                markdown_text,
                start_pos=last_pos,
                fuzzy_threshold=0.85,
                page_markers=page_markers,
                suggested_page=toc_page if toc_page > 0 else None,
            )

            if matched_line is not None:
                # Confidence filtering – also lowered here
                if confidence < CONFIDENCE_LOW:
                    self.log(
                        f"  ⚠️ Very low confidence ({confidence:.2f}) for '{heading[:40]}' – skipping TOC match, will rely on heading detection.",
                        "WARNING",
                    )
                    low_confidence_count += 1
                    continue

                if confidence < CONFIDENCE_HIGH:
                    self.log(
                        f"  ⚠️ Medium confidence ({confidence:.2f}) for '{heading[:40]}' – using TOC match with warning.",
                        "WARNING",
                    )

                # Find position in text
                lines = markdown_text.splitlines(keepends=True)
                pos = 0
                for i in range(matched_line):
                    pos += len(lines[i])
                last_pos = pos + len(matched_text)

                start_page = 1
                for p, marker_pos in page_markers:
                    if marker_pos <= pos:
                        start_page = p
                    else:
                        break
                if start_page < 1:
                    start_page = 1

                self.log(
                    f"[Segmenter] Found heading '{heading[:40]}' at page {start_page} (confidence: {confidence:.2f})",
                    "DEBUG",
                )
            else:
                if toc_page == 0:
                    self.log(
                        f"[Segmenter] Cannot locate heading '{heading[:40]}' even with fuzzy matching. Skipping.",
                        "WARNING",
                    )
                    continue
                else:
                    start_page = max(1, min(toc_page, total_pages))
                    self.log(
                        f"[Segmenter] Heading '{heading[:40]}' not found. Using TOC page {start_page} as anchor.",
                        "DEBUG",
                    )
                    pos = page_to_pos.get(start_page, 0)

            if idx + 1 < len(corrected_toc):
                next_heading = corrected_toc[idx + 1][0]
                next_toc_page = corrected_toc[idx + 1][1]
                next_matched, _, next_confidence, _ = self._find_heading_in_markdown(
                    next_heading,
                    markdown_text,
                    start_pos=last_pos,
                    fuzzy_threshold=0.85,
                    page_markers=page_markers,
                    suggested_page=next_toc_page if next_toc_page > 0 else None,
                )
                if next_matched is not None:
                    # Find the position of the next match
                    lines = markdown_text.splitlines(keepends=True)
                    next_pos = 0
                    for i in range(next_matched):
                        next_pos += len(lines[i])
                    end_page = 1
                    for p, marker_pos in page_markers:
                        if marker_pos <= next_pos:
                            end_page = p
                        else:
                            break
                    if end_page < start_page:
                        end_page = total_pages
                else:
                    if next_toc_page > 0 and next_toc_page > start_page:
                        end_page = next_toc_page - 1
                    else:
                        end_page = total_pages
            else:
                end_page = total_pages

            end_page = min(end_page, total_pages)
            if end_page < start_page:
                end_page = start_page

            start_pos = page_to_pos.get(start_page, 0)
            end_pos = page_to_pos.get(end_page + 1, len(markdown_text))
            if start_pos >= end_pos:
                content = markdown_text[start_pos:].strip()
            else:
                content = markdown_text[start_pos:end_pos].strip()
            if not content:
                content = f"[No content extracted for pages {start_page}–{end_page}]"

            seg = Segment(
                heading=heading,
                content=content,
                start_page=start_page,
                end_page=end_page,
                segment_type="chapter",
            )
            self._recalc_page_bounds(seg)
            segments.append(seg)

        if low_confidence_count > 0:
            self.log(
                f"[Segmenter] {low_confidence_count} entries skipped due to very low confidence.",
                "INFO",
            )

        if segments:
            self.log(
                f"[Segmenter] TOC‑driven segmentation: created {len(segments)} segments.", "INFO"
            )
            return segments
        else:
            self.log(
                "[Segmenter] No TOC headings could be matched. Falling back to heading‑based segmentation.",
                "INFO",
            )
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # V10.14.0 (D2): Page-anchor segmentation — use TOC page numbers directly
    # ─────────────────────────────────────────────────────────────────────────

    def _segment_by_toc_page_anchors(
        self, markdown_text: str, total_pages: int, page_markers: list[tuple[int, int]]
    ) -> list[Segment]:
        """V10.14.0 (D2): Segment using ONLY TOC page numbers (no text matching).

        When the TOC entries have accurate page numbers (e.g. from the PDF's
        native outline/bookmarks), we can split the markdown at page markers
        directly — no fuzzy heading matching needed.  This is more reliable
        than fuzzy matching on OCR'd text (which often fails with 0/23 located).

        Requirements:
        - At least 2 TOC entries with page numbers > 0
        - Page markers available (from extract_page_markers)

        The method splits the markdown at each TOC entry's page marker,
        creating one segment per TOC entry.  The heading text from the TOC
        is used as-is (no fuzzy matching against the markdown text).
        """
        if not self.toc_entries or not page_markers:
            return []

        # Build page → position map
        page_to_pos = dict(page_markers)
        page_to_pos[total_pages + 1] = len(markdown_text)

        # Filter TOC entries that have valid page numbers
        entries_with_pages = [
            (e.title, e.page)
            for e in self.toc_entries
            if e.page is not None and e.page > 0 and e.page <= total_pages
        ]
        if len(entries_with_pages) < 2:
            return []

        # Sort by page number (TOC entries should already be in order, but
        # some PDFs have out-of-order outlines)
        entries_with_pages.sort(key=lambda x: x[1])

        # Deduplicate: if two entries have the same page, keep only the first
        # (the second is likely a sub-section that starts on the same page)
        deduped = []
        last_page = 0
        for heading, page in entries_with_pages:
            if page != last_page:
                deduped.append((heading, page))
                last_page = page
            else:
                self.log(
                    f"  [Segmenter] Skipping duplicate TOC page {page}: '{heading[:40]}'",
                    "DEBUG",
                )

        if len(deduped) < 2:
            return []

        segments = []
        for idx, (heading, start_page) in enumerate(deduped):
            # End page = start of next entry - 1 (or total_pages for the last)
            if idx + 1 < len(deduped):
                end_page = deduped[idx + 1][1] - 1
            else:
                end_page = total_pages

            if end_page < start_page:
                end_page = start_page

            # Get markdown positions from page markers
            # V18.20.4.10 (P0-b3): nearest-following marker for a missing
            # start page (the pos-0 fallback swallowed the whole text —
            # same class as _segment_by_chapters, see the P0-b3 note there).
            start_pos = page_to_pos.get(start_page)
            if start_pos is None:
                _next_marker_page = min((p for p in page_to_pos if p > start_page), default=None)
                start_pos = (
                    page_to_pos[_next_marker_page]
                    if _next_marker_page is not None
                    else len(markdown_text)
                )
            end_pos = page_to_pos.get(end_page + 1, len(markdown_text))
            if start_pos >= end_pos:
                # V18.20.4.10 (P0-b3): inverted bounds → EMPTY (visible,
                # honest) instead of the whole remaining tail (duplicated
                # content across segments).
                content = ""
            else:
                content = markdown_text[start_pos:end_pos].strip()

            if not content:
                content = f"[No content extracted for pages {start_page}–{end_page}]"

            seg = Segment(
                heading=heading,
                content=content,
                start_page=start_page,
                end_page=end_page,
                segment_type="chapter",
            )
            segments.append(seg)

        return segments

    # ─────────────────────────────────────────────────────────────────────────
    # Fallback pipeline (heading-based)
    # ─────────────────────────────────────────────────────────────────────────

    def _heading_pipeline(self, markdown_text, total_pages, page_markers) -> list[Segment]:
        segs = self.heading_segmenter.segment(markdown_text, total_pages, page_markers)
        if not segs:
            return []

        segs = self._remove_toc_bursts(segs)

        before = len(segs)
        segs = self._merge_short_segments(segs)
        segs = self._sort_segments(segs)
        segs = self._merge_same_chapter_number(segs)
        after = len(segs)

        for s in segs:
            self._recalc_page_bounds(s)

        self.log(f"[Segmenter] {before} raw → {after} chapters after merge + sort.", "INFO")
        segs = self._apply_toc_headings(segs)

        segs = self._enforce_contiguity(segs, total_pages, markdown_text, page_markers)

        for s in segs:
            self._recalc_page_bounds(s)

        segs = sorted(segs, key=lambda s: s.start_page)

        return segs

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point (Phase 2.2 – Priority Cascade with located TOC support)
    # ─────────────────────────────────────────────────────────────────────────

    def _segments_meet_minimum(self, segments) -> bool:
        """V0.02 (false-success RCA): the ≥ ``MIN_TOC_SEGMENTS`` acceptance
        gates exist to reject garbage TOC segmentations on FULL-BOOK runs
        (a TOC that yields 1-2 accidental segments is usually wrong). When
        the user EXPLICITLY selected chapters, N segments for N picks is the
        correct answer — a 2-chapter selection must not be rejected into the
        fallback cascade, which re-segments by headings/semantics and can
        scramble the selection (the incident: selected chapters absorbed
        into a 'Preface' segment → skipped as front matter → 0 summaries →
        "✅ Conversion complete")."""
        if not segments:
            return False
        if len(segments) >= MIN_TOC_SEGMENTS:
            return True
        return bool(getattr(self.request, "selected_chapters", None))

    def segment(self, markdown_text, total_pages, page_markers) -> list[Segment]:
        # 0. Manual segments (highest priority)
        if self.request.manual_segments is not None and len(self.request.manual_segments) > 0:
            self.log(
                f"[Segmenter] Using manual segmentation: {len(self.request.manual_segments)} ranges",
                "INFO",
            )
            return self._create_manual_segments(
                markdown_text, total_pages, page_markers, self.request.manual_segments
            )

        # Get the user's strategy preference
        strategy = self.request.get_segment_strategy_enum()

        # ── If strategy is explicitly set (non-AUTO), respect it directly ──
        if strategy == SegmentStrategy.HEADING:
            self.log("[Segmenter] Using explicit HEADING strategy.", "INFO")
            return self._heading_pipeline(markdown_text, total_pages, page_markers)
        elif strategy == SegmentStrategy.SEMANTIC:
            self.log("[Segmenter] Using explicit SEMANTIC strategy.", "INFO")
            segments = self.semantic_segmenter.segment(markdown_text, total_pages, page_markers)
            if segments:
                return segments
            self.log("[Segmenter] SEMANTIC produced no segments; falling back to TOKEN.", "WARNING")
            return self.token_segmenter.segment(markdown_text, total_pages, page_markers)
        elif strategy == SegmentStrategy.TOKEN:
            self.log("[Segmenter] Using explicit TOKEN strategy.", "INFO")
            return self.token_segmenter.segment(markdown_text, total_pages, page_markers)

        # ── AUTO strategy: Priority Cascade ──────────────────────────────
        # V13.32.8: 0. Chapter-Level Segmentation (the new gold standard)
        if self.toc_entries and len(self.toc_entries) >= 2:
            chapter_entries = None
            if self._has_outline_levels():
                chapter_entries = self._filter_to_chapter_level()
            if not chapter_entries:
                chapter_entries = self._filter_by_chapter_numbers()
            if (
                chapter_entries and len(chapter_entries) >= 1
            ):  # V13.33.0: >=1 (not >=2) — user may select 1 chapter
                self.log("[Segmenter] Attempting chapter-level segmentation\u2026", "INFO")
                segments = self._segment_by_chapters(
                    markdown_text, total_pages, page_markers, chapter_entries
                )
                # V0.02: selection-aware acceptance (see _segments_meet_minimum)
                if self._segments_meet_minimum(segments):
                    segments = self._merge_short_chapters(segments)
                    segments = self._enforce_contiguity(
                        segments, total_pages, markdown_text, page_markers
                    )
                    for s in segments:
                        self._recalc_page_bounds(s)
                    segments = sorted(segments, key=lambda s: s.start_page)
                    # V18.20.4.10 (P0-b4): defense-in-depth monster-segment
                    # gate. With >=3 segments, no single chapter-level segment
                    # should span the majority of the book — if it does, the
                    # outline chapter data was wrong (that is exactly how the
                    # V18.20.4.9 run produced a 692,442-token 'Seb Rose'
                    # segment and a stalled 675,817-token map-reduce).
                    # WARNING, not abort: segmentation must still return
                    # something; the visible warning tells the user what
                    # happened and what to do about it.
                    if total_pages > 0 and len(segments) >= MIN_TOC_SEGMENTS:
                        _largest = max(
                            segments,
                            key=lambda s: (s.end_page or 0) - (s.start_page or 0) + 1,
                        )
                        _largest_span = (_largest.end_page or 0) - (_largest.start_page or 0) + 1
                        if _largest_span > 0.6 * total_pages:
                            self.log(
                                f"[Segmenter] ⚠️ MONSTER SEGMENT: '{_largest.heading[:60]}' "
                                f"spans pages {_largest.start_page}\u2013{_largest.end_page} "
                                f"({_largest_span} of {total_pages} pages) — the outline "
                                f"chapter data is suspect. Summarising it will trigger "
                                f"map-reduce (very slow on small-VRAM rigs). Consider "
                                f"manual page-range segmentation for this book.",
                                "WARNING",
                            )
                    self.log(
                        f"[Segmenter] Chapter-level segmentation produced {len(segments)} segments \u2013 using it. \u2713",
                        "INFO",
                    )
                    return segments
                else:
                    self.log(
                        f"[Segmenter] Chapter-level produced <{MIN_TOC_SEGMENTS} segments \u2014 falling back to TOC cascade.",
                        "INFO",
                    )

        self.log(
            "[Segmenter] AUTO strategy: Priority Cascade (Located TOC \u2192 TOC \u2192 Heading \u2192 Semantic \u2192 Token).",
            "INFO",
        )

        # 1. Located TOC (if entries already have line numbers)
        if self._toc_has_located_lines and len(self.toc_entries) >= 2:
            self.log("[Segmenter] Attempting located‑TOC segmentation…", "INFO")
            segments = self._segment_with_located_headings(markdown_text, total_pages, page_markers)
            # V10.0.0 Fix 3 + Guardrail D: Validate located-TOC results.
            # If any segment has < 50 tokens of content, the located-TOC
            # mis-located headings (common on two-column academic PDFs).
            # Fall through to TOC-driven or heading segmentation instead.
            _has_empty_segments = any(count_tokens(s.content) < 50 for s in (segments or []))
            if self._segments_meet_minimum(segments) and not _has_empty_segments:
                segments = self._apply_toc_headings(segments)
                # ── Merge duplicate headings and short segments ──────────
                segments = self._merge_duplicate_headings(segments)
                segments = self._merge_short_segments(segments)
                # ── FIX: Skip contiguity enforcement for located TOC ──────
                for s in segments:
                    self._recalc_page_bounds(s)
                segments = sorted(segments, key=lambda s: s.start_page)
                self.log(
                    f"[Segmenter] Located TOC produced {len(segments)} segments (≥ {MIN_TOC_SEGMENTS}) – using it.",
                    "INFO",
                )
                return segments
            elif _has_empty_segments:
                self.log(
                    "[Segmenter] Located TOC produced segments with < 50 tokens "
                    "(likely mis-located headings on two-column PDF). "
                    "Falling back to TOC-driven segmentation.",
                    "WARNING",
                )
            else:
                if segments:
                    self.log(
                        f"[Segmenter] Located TOC produced only {len(segments)} segments (< {MIN_TOC_SEGMENTS}). Falling back.",
                        "INFO",
                    )
                else:
                    self.log("[Segmenter] Located TOC produced no segments. Falling back.", "INFO")

        # 2. TOC-driven (with fuzzy search)
        if len(self.toc_entries) >= 2:
            self.log("[Segmenter] Attempting TOC-driven segmentation (with fuzzy search)…", "INFO")
            segments = self._segment_by_toc(markdown_text, total_pages, page_markers)
            # V0.02: selection-aware acceptance (see _segments_meet_minimum)
            if self._segments_meet_minimum(segments):
                segments = self._apply_toc_headings(segments)
                segments = self._merge_duplicate_headings(segments)
                segments = self._merge_short_segments(segments)
                segments = self._enforce_contiguity(
                    segments, total_pages, markdown_text, page_markers
                )
                for s in segments:
                    self._recalc_page_bounds(s)
                segments = sorted(segments, key=lambda s: s.start_page)
                self.log(
                    f"[Segmenter] TOC produced {len(segments)} segments (≥ {MIN_TOC_SEGMENTS}) – using it.",
                    "INFO",
                )
                return segments
            else:
                if segments:
                    self.log(
                        f"[Segmenter] TOC produced only {len(segments)} segments (< {MIN_TOC_SEGMENTS}). Falling back.",
                        "INFO",
                    )
                else:
                    self.log("[Segmenter] TOC produced no segments. Falling back.", "INFO")

        # 3. Heading-based (pattern + H1 + plain-text detection)
        self.log("[Segmenter] Attempting heading-based segmentation…", "INFO")
        segments = self._heading_pipeline(markdown_text, total_pages, page_markers)
        if segments:
            self.log(
                f"[Segmenter] Heading-based produced {len(segments)} segments – using it.", "INFO"
            )
            return segments

        # 4. Semantic (LLM-based)
        if self.request.enable_semantic_segmentation:
            self.log("[Segmenter] Attempting semantic segmentation…", "INFO")
            segments = self.semantic_segmenter.segment(markdown_text, total_pages, page_markers)
            if segments:
                self.log(
                    f"[Segmenter] Semantic produced {len(segments)} segments – using it.", "INFO"
                )
                return segments

        # 5. Token-based (fallback)
        self.log("[Segmenter] Falling back to token-based segmentation.", "INFO")
        segments = self.token_segmenter.segment(markdown_text, total_pages, page_markers)
        if segments:
            self.log(
                f"[Segmenter] Token-based produced {len(segments)} segments – using it.", "INFO"
            )
            return segments

        # 6. Ultimate fallback: single segment covering the whole document
        self.log(
            "[Segmenter] No segmentation method produced segments. Creating full-document fallback.",
            "WARNING",
        )
        self.log(
            "[Segmenter] 💡 Suggestion: Use manual segmentation in the Convert tab (enter page ranges).",
            "INFO",
        )
        return [
            Segment(
                heading="Full Document",
                content=markdown_text,
                start_page=1,
                end_page=max(1, total_pages),
                segment_type="chunk",
            )
        ]
