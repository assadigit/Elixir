"""V0.02 — the false-success incident ("97 Things", real-rig log on record).

The user selected 2 chapters ('Act with Prudence', 'Apply Functional
Programming Principles'); the wizard's chapter list showed per-chapter AUTHOR
bookmarks as selectable "chapters" too, so 4 entries were selected. The chain
that followed:

  1. Selection UI listed metadata children (authors) as chapters
     (chapter_selector_dialog.py) — 4 picks instead of 2.
  2. Page derivation: a title whose next outline entry shares its page
     yielded ZERO pages; the author entries yielded pages 28-31; ±1
     boundary pulled in p.27 ('Preface') and p.32 (an unselected chapter).
  3. The segmenter ran on the FULL 198-entry TOC against the 6 extracted
     pages → ~97 phantom "no marker" segments.
  4. Layer-3 merging absorbed the user's chapters into 'Preface'.
  5. The post-segmentation selection filter kept the merged 'Preface'.
  6. The front-matter skip list dropped 'Preface' from summarization.
  7. 0 summaries → "✅ Conversion complete." + empty DOCX + library entry.
     (converter_impl.py's V18.2.4 guard required non-empty ``summaries``;
     an empty list sailed past it, and the success expression treated
     ``summaries == []`` as unconditionally successful.)

This file pins the four fixes:
  FIX 1  dialog excludes metadata-children levels + same-page page-range fix
  FIX 2  segmentation is selection-aware (TOC pre-restricted; acceptance
         gates selection-aware)
  FIX 3  front-matter skip disabled when a selection is active
  FIX 4  zero-summaries completion: hard failure under a selection, loud
         WARNING otherwise

Headless: no PySide6 import (the dialog is covered by source pins).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# House pattern (test_v1820410): mock heavy optional deps ONLY when missing.
for _mod in ("markitdown", "pdfplumber", "pdf2image", "pytesseract",
             "spacy", "wordninja", "PIL", "docx"):
    if _mod in sys.modules:
        continue
    try:
        __import__(_mod)
    except Exception:
        sys.modules[_mod] = MagicMock()

from core.models.models import ConversionRequest
from core.models.toc import TOCEntry
from core.segmentation.chapter_matcher import filter_toc_entries_for_selection
from core.segmentation.segmenter import Segmenter, compute_metadata_child_levels


def _collect():
    logs: list[tuple[str, str]] = []
    def log(msg, level="INFO"):
        logs.append((level, msg))
    return logs, log


def _incident_toc() -> list[TOCEntry]:
    """The 97-Things outline shape: per-chapter title (level 0) + author
    (level 1) bookmarks on the SAME page. Scaled down: 5 essays, pages 28+,
    plus the front matter the boundary pages leak in."""
    entries = [
        TOCEntry(title="Contributions by Category", page=17, level=0),
        TOCEntry(title="Preface", page=25, level=0),
        TOCEntry(title="Act with Prudence", page=28, level=0),
        TOCEntry(title="Seb Rose", page=28, level=1),
        TOCEntry(title="Apply Functional Programming Principles", page=30, level=0),
        TOCEntry(title="Edward Garson", page=30, level=1),
        TOCEntry(title="Ask, \"What Would the User Do?\"", page=32, level=0),
        TOCEntry(title="Dan McCoy", page=32, level=1),
        TOCEntry(title="Automate Your Coding Standard", page=34, level=0),
        TOCEntry(title="Filip van Laenen", page=34, level=1),
        TOCEntry(title="Beauty Is in Simplicity", page=36, level=0),
        TOCEntry(title="Jørn Ølmheim", page=36, level=1),
    ]
    return entries


_INCIDENT_SELECTION = [
    "Act with Prudence", "Seb Rose",
    "Apply Functional Programming Principles", "Edward Garson",
]


# ═══════════════════════════════════════════════════════════════════════════
# FIX 1 — shared metadata-children rule (compute_metadata_child_levels)
# ═══════════════════════════════════════════════════════════════════════════

class TestComputeMetadataChildLevels:

    def test_authors_level_excluded_with_stats(self):
        by_level = {
            0: [(e.title, e.page) for e in _incident_toc() if e.level == 0],
            1: [(e.title, e.page) for e in _incident_toc() if e.level == 1],
        }
        excluded = compute_metadata_child_levels(by_level)
        # Level 1 (all 5 authors share a level-0 title's page) is excluded,
        # with the (same_page, total) stats the Layer-1 log line prints.
        assert excluded == {1: (5, 5)}

    def test_parts_chapters_shape_survives(self):
        by_level = {
            0: [("Part One", 25), ("Part Two", 109)],
            1: [("Chapter 1: Intro", 27), ("Chapter 2: Body", 60)],
        }
        assert compute_metadata_child_levels(by_level) == {}

    def test_level0_only_never_excluded(self):
        by_level = {0: [("Chapter 1", 5), ("Chapter 2", 9)]}
        assert compute_metadata_child_levels(by_level) == {}

    def test_empty(self):
        assert compute_metadata_child_levels({}) == {}

    def test_excluded_level_does_not_feed_pages_forward(self):
        # level 2 sections start on their OWN pages (not level-0 pages) —
        # an excluded level 1 in between must not shield them from the rule
        # (they wouldn't be excluded either way here, since they don't share
        # level-0 pages; the pin guards the continue-semantics).
        by_level = {
            0: [("Title A", 10), ("Title B", 20)],
            1: [("Author A", 10), ("Author B", 20)],      # excluded (2/2 same page)
            2: [("Section A.1", 11), ("Section B.1", 21)],  # own pages → kept
        }
        excluded = compute_metadata_child_levels(by_level)
        assert excluded == {1: (2, 2)}

    def test_partial_same_page_below_threshold_kept(self):
        # Only 1 of 3 level-1 entries shares a level-0 page (33% < 80%) —
        # a real sub-section level, must NOT be excluded.
        by_level = {
            0: [("Chapter 1", 10), ("Chapter 2", 20)],
            1: [("Section 1.1", 11), ("Section 1.2", 15), ("Section 2.1", 20)],
        }
        assert compute_metadata_child_levels(by_level) == {}


# ═══════════════════════════════════════════════════════════════════════════
# FIX 2 — selection-aware TOC restriction (filter_toc_entries_for_selection)
# ═══════════════════════════════════════════════════════════════════════════

class TestFilterTocEntriesForSelection:

    def test_incident_selection_yields_only_real_chapters(self):
        """The exact incident input: 4 picks (2 titles + 2 authors) against
        the metadata-children-cleaned TOC → only the 2 real chapter entries
        survive (the author picks match nothing — their bookmarks are gone)."""
        entries = _incident_toc()
        cleaned = [e for e in entries if e.level == 0]
        kept, dropped = filter_toc_entries_for_selection(cleaned, _INCIDENT_SELECTION)
        kept_titles = {e.title for e in kept}
        assert kept_titles == {"Act with Prudence", "Apply Functional Programming Principles"}
        assert dropped == len(cleaned) - 2

    def test_elements_returned_as_is(self):
        entries = _incident_toc()
        kept, _ = filter_toc_entries_for_selection(
            entries, ["Act with Prudence"])
        assert all(e is entries[i] for i, e in enumerate(entries) if e in kept)
        assert all(isinstance(e, TOCEntry) for e in kept)

    def test_tuple_entries_supported(self):
        entries = [("Alpha Chapter", 10), ("Beta Chapter", 20), ("Gamma", 30)]
        kept, dropped = filter_toc_entries_for_selection(entries, ["Beta Chapter"])
        assert kept == [("Beta Chapter", 20)]
        assert dropped == 2

    def test_no_match_returns_original_unchanged(self):
        """Safety-net contract: a selection matching NOTHING must not shrink
        the TOC (the post-segmentation filter's keep-all fallback stays)."""
        entries = _incident_toc()
        kept, dropped = filter_toc_entries_for_selection(entries, ["Nonexistent Chapter Title"])
        assert kept is entries
        assert dropped == 0

    def test_empty_inputs(self):
        entries = _incident_toc()
        assert filter_toc_entries_for_selection([], ["x"])[0] == []
        assert filter_toc_entries_for_selection(entries, [])[0] is entries


# ═══════════════════════════════════════════════════════════════════════════
# FIX 2 — full incident replay through the REAL Segmenter
# ═══════════════════════════════════════════════════════════════════════════

def _incident_markdown() -> str:
    """The 6 extracted pages (27-32) with page markers — what the extraction
    phase produces under the incident's chapter selection."""
    pages = {
        27: "Preface\n\nThis preface text leaked in via the ±1 boundary page.",
        28: "Act with Prudence\n\n" + ("prudence debt rewrite value " * 40),
        29: ("continuation of the prudence essay. " * 30),
        30: "Apply Functional Programming Principles\n\n" + ("pure functions avoid side effects " * 40),
        31: ("more functional programming guidance here. " * 30),
        32: "Ask, \"What Would the User Do?\"\n\nAn unselected chapter that leaked via the boundary page.",
    }
    parts = []
    for p in range(27, 33):
        parts.append(f"<!-- original page {p} -->\n{pages[p]}\n")
    return "\n".join(parts)


class TestIncidentReplaySelectionAwareSegmentation:

    def _run(self, selected):
        """Mirror run_segmentation's V0.02 composition: under a selection,
        metadata-children drop → selection filter → real Segmenter.segment().
        Without a selection the TOC passes through untouched (the guard in
        run_segmentation is `if request.selected_chapters`)."""
        toc = _incident_toc()
        if selected:
            by_level: dict[int, list] = {}
            for e in toc:
                if e.page and e.page > 0:
                    by_level.setdefault(e.level, []).append((e.title, e.page))
            mc = compute_metadata_child_levels(by_level)
            if mc:
                mc_levels = set(mc)
                toc = [e for e in toc if e.level not in mc_levels]
            toc, _dropped = filter_toc_entries_for_selection(toc, selected)

        request = ConversionRequest(
            input_path=Path("t.pdf"), output_dir=Path("out"),
            selected_chapters=selected or None,
        )
        logs, log = _collect()
        seg = Segmenter(request, log_callback=log, toc_entries=toc)
        markers = []
        import re as _re
        for m in _re.finditer(r'<!-- original page (\d+) -->', _incident_markdown()):
            markers.append((int(m.group(1)), m.start()))
        segments = seg.segment(_incident_markdown(), 257, markers)
        return segments, logs

    def test_selected_chapters_segment_as_themselves(self):
        """The incident's exact selection: every REAL segment is one of the
        selected chapters — no 'Preface', no author headings, no phantom
        whole-tail segments. (Gap-filler segments are expected — the text
        covers pages 27-32 of a 257-page book; the post-segmentation
        selection filter drops gap segments, which never match.)"""
        segments, logs = self._run(_INCIDENT_SELECTION)
        assert segments, "selection run must produce segments"
        allowed = {"Act with Prudence", "Apply Functional Programming Principles",
                   "Seb Rose", "Edward Garson"}
        real = [s for s in segments if not s.heading.strip().lower().startswith("gap (")]
        assert real, "selection run must produce non-gap segments"
        for s in real:
            assert s.heading in allowed, f"unexpected segment heading: {s.heading!r}"
            assert "Preface" not in s.heading
        # The user's chapter content actually made it into the segments.
        joined = "\n".join(s.content for s in real)
        assert "prudence debt" in joined
        assert "pure functions" in joined

    def test_selection_acceptance_below_min_toc_segments(self):
        """The ≥ MIN_TOC_SEGMENTS (3) acceptance gate must not reject a
        1-2 segment selection into the fallback cascade."""
        segments, logs = self._run(["Act with Prudence"])
        # One selected chapter → at least one segment containing its content.
        assert any("Act with Prudence" in s.heading for s in segments)
        assert any("falling back" not in m.lower() for _, m in logs)  # cascade not forced
        assert "prudence debt" in "\n".join(s.content for s in segments)

    def test_full_book_run_unchanged_no_selection(self):
        """No selection → the full TOC still segments and Layer-1 still
        excludes the author level internally (regression guard: the
        pre-filter only activates under a selection)."""
        segments, logs = self._run(None)
        assert segments
        # Layer-1 metadata-children exclusion still fires on the full TOC.
        assert any("level 1 excluded" in m for _, m in logs)
        # No author names surface as segment headings.
        headings = "\n".join(s.heading for s in segments)
        for author in ("Seb Rose", "Edward Garson", "Dan McCoy"):
            assert author not in headings


# ═══════════════════════════════════════════════════════════════════════════
# FIX 1 — dialog source pins (PySide6 absent in the sandbox)
# ═══════════════════════════════════════════════════════════════════════════

class TestDialogSourcePins:
    _DIALOG = Path("ui_qt/views/chapter_selector_dialog.py")

    def _src(self):
        return self._DIALOG.read_text(encoding="utf-8")

    def test_metadata_children_dropped_before_listing(self):
        src = self._src()
        assert "from core.segmentation.segmenter import compute_metadata_child_levels" in src
        assert "compute_metadata_child_levels(_by_level)" in src

    def test_same_page_neighbour_no_longer_spans_to_book_end(self):
        """Was: ``end = nxt - 1 if nxt > start else total`` — a title whose
        next (child) bookmark shared its page displayed as p.28–257."""
        src = self._src()
        assert "end = nxt - 1 if nxt > start else start" in src
        assert "end = nxt - 1 if nxt > start else total" not in src

    def test_hidden_count_surfaced_in_hint(self):
        src = self._src()
        assert "_hidden_metadata_count" in src
        assert "author/annotation bookmark(s) hidden" in src


# ═══════════════════════════════════════════════════════════════════════════
# FIX 3 — front-matter skip is selection-aware (source pins)
# ═══════════════════════════════════════════════════════════════════════════

class TestFrontMatterSkipSelectionAware:
    _SUMM = Path("core/pipeline/conversion/summarization.py")

    def test_selection_guard_precedes_skip_patterns(self):
        src = self._SUMM.read_text(encoding="utf-8")
        guard = src.find("if request.selected_chapters:")
        patterns = src.find("_skip_patterns = [")
        assert guard != -1 and patterns != -1
        assert guard < patterns, "the selection guard must come first"
        assert "front-matter skip disabled (selected sections are" in src

    def test_selection_branch_keeps_all_segments(self):
        src = self._SUMM.read_text(encoding="utf-8")
        assert "segments_for_summary = segments" in src

    def test_skip_patterns_themselves_unchanged(self):
        """The full-book skip list keeps its exact V10.24.0 shape."""
        import re as _re
        src = self._SUMM.read_text(encoding="utf-8")
        for pat in (r"\(r'\^preface', 'preface'\)", r"\(r'\^foreword', 'foreword'\)",
                    r"\(r'\^index\\s\*\$', 'index'\)"):
            assert _re.search(pat, src), pat


# ═══════════════════════════════════════════════════════════════════════════
# FIX 4 — zero-summaries completion is loud (source pins + semantics)
# ═══════════════════════════════════════════════════════════════════════════

class TestZeroSummariesLoudFailure:
    _CONV = Path("core/pipeline/converter_impl.py")

    def _src(self):
        return self._CONV.read_text(encoding="utf-8")

    def test_zero_summaries_flag_defined(self):
        src = self._src()
        assert "_zero_summaries = (" in src
        assert "not summaries and bool(self.request.generate_summaries)" in src

    def test_selection_zero_summaries_is_hard_failure_branch(self):
        src = self._src()
        assert "elif _zero_summaries and _selection_active:" in src
        assert "no selected chapters summarized" in src
        assert "None of the {len(self.request.selected_chapters)} selected chapter(s)" in src

    def test_success_expression_no_longer_treats_empty_as_success(self):
        src = self._src()
        assert "and not (_zero_summaries and _selection_active)" in src
        # The old unconditional-True-for-empty expression is gone.
        assert "success=(not _all_failed if summaries else True) and not _cancelled," not in src

    def test_full_book_zero_summaries_gets_warning(self):
        src = self._src()
        assert "elif _zero_summaries:" in src
        assert "Zero sections were summarized" in src

    def test_semantics_matrix(self):
        """The guard expression, evaluated standalone for all four cases."""
        def zero(summaries, generate, cancelled):
            return (not summaries) and bool(generate) and not cancelled

        # incident: 0 summaries, summaries requested, not cancelled → flagged
        assert zero([], True, False) is True
        # summaries off → legitimately empty → not flagged
        assert zero([], False, False) is False
        # cancelled → the cancelled branch owns it → not flagged
        assert zero([], True, True) is False
        # non-empty summaries → not flagged (the V18.2.4 guard owns it)
        assert zero([object()], True, False) is False


# ═══════════════════════════════════════════════════════════════════════════
# FIX 2 — wiring source pins (run_segmentation pre-filters before Segmenter)
# ═══════════════════════════════════════════════════════════════════════════

class TestSegmentationWiringPins:
    _SEG = Path("core/pipeline/conversion/segmentation.py")

    def test_run_segmentation_restricts_toc_under_selection(self):
        src = self._SEG.read_text(encoding="utf-8")
        assert "if request.selected_chapters and _seg_toc is not None:" in src
        assert "compute_metadata_child_levels" in src
        assert "filter_toc_entries_for_selection" in src
        # The Segmenter is constructed with the (possibly restricted) TOC.
        assert "toc_entries=_seg_toc," in src

    def test_segmenter_acceptance_gate_is_selection_aware(self):
        src = Path("core/segmentation/segmenter.py").read_text(encoding="utf-8")
        assert "def _segments_meet_minimum(self, segments) -> bool:" in src
        assert 'return bool(getattr(self.request, "selected_chapters", None))' in src
        # All three acceptance gates use the helper (no raw >= MIN_TOC_SEGMENTS
        # acceptance checks remain in segment()).
        import re as _re
        raw_gates = _re.findall(
            r"if segments and len\(segments\) >= MIN_TOC_SEGMENTS", src)
        assert raw_gates == [], "acceptance gates must go through _segments_meet_minimum"

    def test_segmenter_layer1_uses_shared_helper(self):
        """The Layer-1 exclusion now calls the shared helper (single source
        of truth with the dialog) — behavior pinned byte-identical by
        test_v1820410_p0_segmentation_vram.py."""
        src = Path("core/segmentation/segmenter.py").read_text(encoding="utf-8")
        assert "_mc_excluded = compute_metadata_child_levels(by_level)" in src
