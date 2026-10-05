"""V18.20.3.6 — honest ``pages_processed`` (fixtures from the real run).

The bug (user report, first real-world V18.20.3.5 run of "Broken
Structures", Salman Akhtar — Ch. 1 "Identity and Its Origins"):

    Converting ONE selected chapter (TOC pages 15–32 = 18 pages of a
    397-page book) showed "Pages processed: 397" in the completion
    modal — the whole book's total — because
    ``Converter.convert()`` filled ``ConversionResult.pages_processed``
    with ``analysis.total_pages`` (the PDF's page count), regardless of
    chapter selection or page range.

The fix is pure page arithmetic (chapter-agnostic by construction —
the user's standing rule: no chapter-derived data, only structural
rules that generalize to any book):

  precedence:  selected chapter/range pages  >  page range  >  whole doc

    * ``extraction.ExtractionResult.selected_pages`` — the user's
      explicit selection snapshot BEFORE the ±1 boundary overlap
      (the overlap pages are context-only, deduped in post-processing;
      reporting them would inflate 18 → 20).
    * ``converter_impl.compute_pages_processed`` — the precedence rule,
      applied to the modal number AND the diagnostic summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# (markitdown is not installed in this sandbox; the stub keeps the eager
# controller→pipeline→core.pdf import chain loadable).
from core.pipeline.conversion.extraction import (
    ExtractionResult,
    expand_with_overlap,
)
from core.pipeline.converter_impl import compute_pages_processed

# ── Real-run constants (Broken Structures, 2026-08-31 rig run) ────────────
BOOK_TOTAL = 397  # PDF page count (log: "31/397 pages are scanned")
CH1_START, CH1_END = 15, 32  # TOC: Ch. 1 starts p.15, Ch. 2 starts p.33
CH1_PAGES = set(range(CH1_START, CH1_END + 1))  # 18 pages — user expectation
CH1_WITH_OVERLAP = set(range(CH1_START - 1, CH1_END + 2))  # 20 pages


# ═══════════════════════════════════════════════════════════════════════════
# compute_pages_processed — the precedence rule
# ═══════════════════════════════════════════════════════════════════════════


def test_real_run_single_chapter_reports_chapter_pages():
    """THE reported bug: 1 selected chapter of a 397-page book → 18, not 397."""
    assert (
        compute_pages_processed(
            selected_pages=CH1_PAGES,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=BOOK_TOTAL,
            effective_total_pages=BOOK_TOTAL,
            total_pages=BOOK_TOTAL,
        )
        == 18
    )


def test_pre_overlap_set_not_overlap_inflated():
    """The ±1 boundary overlap (18 → 20) must NOT leak into the number."""
    assert len(expand_with_overlap(set(CH1_PAGES), BOOK_TOTAL)) == 20
    assert (
        compute_pages_processed(
            selected_pages=CH1_PAGES,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=BOOK_TOTAL,
            effective_total_pages=BOOK_TOTAL,
            total_pages=BOOK_TOTAL,
        )
        == 18
    )  # still 18 — selected_pages is the PRE-overlap snapshot


def test_multiple_selected_chapters_union():
    """Two chapters (any book, any pages) → the union of their page sets."""
    ch2 = set(range(33, 56))  # 23 pages
    selection = CH1_PAGES | ch2
    assert (
        compute_pages_processed(
            selected_pages=selection,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=BOOK_TOTAL,
            effective_total_pages=BOOK_TOTAL,
            total_pages=BOOK_TOTAL,
        )
        == 18 + 23
    )


def test_selection_intersects_page_range_when_both_set():
    """Chapter selection + page range → only pages inside BOTH count
    (extraction already filters OCR results to the effective range)."""
    # range 20–397 → keeps pages 20..32 of the chapter = 13 pages
    assert (
        compute_pages_processed(
            selected_pages=CH1_PAGES,
            page_range_start=20,
            page_range_end=None,
            effective_start_page=20,
            effective_end_page=397,
            effective_total_pages=378,
            total_pages=BOOK_TOTAL,
        )
        == 13
    )


def test_page_range_only_reports_range_size():
    """No chapter selection, page range 100–200 → 101, not 397."""
    assert (
        compute_pages_processed(
            selected_pages=None,
            page_range_start=100,
            page_range_end=200,
            effective_start_page=100,
            effective_end_page=200,
            effective_total_pages=101,
            total_pages=BOOK_TOTAL,
        )
        == 101
    )


def test_whole_book_unchanged():
    """No selection, no range → the previous (correct) whole-doc number."""
    assert (
        compute_pages_processed(
            selected_pages=None,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=BOOK_TOTAL,
            effective_total_pages=BOOK_TOTAL,
            total_pages=BOOK_TOTAL,
        )
        == BOOK_TOTAL
    )


def test_degenerate_empty_selection_reports_zero():
    """A selection that resolved to NO pages (e.g. out-of-bounds manual
    ranges) reports 0 — honest — instead of silently falling back to the
    book total."""
    assert (
        compute_pages_processed(
            selected_pages=set(),
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=BOOK_TOTAL,
            effective_total_pages=BOOK_TOTAL,
            total_pages=BOOK_TOTAL,
        )
        == 0
    )


def test_non_pdf_input_reports_all_pages():
    """The multi-format path (EPUB/DOCX/…) returns selected_pages=None and
    effective span 1..N — the number stays N."""
    assert (
        compute_pages_processed(
            selected_pages=None,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=120,
            effective_total_pages=120,
            total_pages=120,
        )
        == 120
    )


def test_single_page_book():
    """1-page document, whole-book mode → 1 (boundary sanity)."""
    assert (
        compute_pages_processed(
            selected_pages=None,
            page_range_start=None,
            page_range_end=None,
            effective_start_page=1,
            effective_end_page=1,
            effective_total_pages=1,
            total_pages=1,
        )
        == 1
    )


# ═══════════════════════════════════════════════════════════════════════════
# expand_with_overlap — the boundary helper (extracted for testability)
# ═══════════════════════════════════════════════════════════════════════════


def test_overlap_adds_one_page_each_side():
    out = expand_with_overlap(CH1_PAGES, BOOK_TOTAL)
    assert 14 in out and 33 in out  # boundary context pages
    assert len(out) == 20


def test_overlap_never_creates_page_zero_or_overflow():
    out = expand_with_overlap({1}, 1)  # single-page selection in 1-page doc
    assert out == {1}
    out2 = expand_with_overlap({1, 2}, 5)  # page 1 → no page 0
    assert 0 not in out2
    out3 = expand_with_overlap({5}, 5)  # last page → no page 6
    assert 6 not in out3


# ═══════════════════════════════════════════════════════════════════════════
# ExtractionResult contract
# ═══════════════════════════════════════════════════════════════════════════


def _minimal_extraction_result(**overrides):
    """An ExtractionResult with the minimum viable fields (defaults for
    the new field keep the dataclass backward-compatible with every
    existing constructor call)."""
    from core.models import PageAnalysis, PdfAnalysisResult, PdfRecommendation

    analysis = PdfAnalysisResult(
        total_pages=BOOK_TOTAL,
        scanned_pages=[],
        text_pages=[],
        recommendation=PdfRecommendation.NO_OCR,
        per_page=[
            PageAnalysis(
                page_num=i + 1,
                is_scanned=False,
                extracted_text_preview="",
                recommended_action="skip",
            )
            for i in range(BOOK_TOTAL)
        ],
    )
    kwargs = dict(
        raw_markdown="x",
        analysis=analysis,
        pages_to_ocr=[],
        effective_start_page=1,
        effective_end_page=BOOK_TOTAL,
        effective_total_pages=BOOK_TOTAL,
        toc_entries=[],
        valid_pages=None,
    )
    kwargs.update(overrides)
    return ExtractionResult(**kwargs)


def test_extraction_result_has_selected_pages_default_none():
    """New field, defaulted — old constructions keep working."""
    er = _minimal_extraction_result()
    assert er.selected_pages is None


def test_extraction_result_carries_pre_overlap_selection():
    """selected_pages (18) and valid_pages (20, post-overlap) are distinct
    by contract."""
    er = _minimal_extraction_result(
        valid_pages=CH1_WITH_OVERLAP,
        selected_pages=CH1_PAGES,
    )
    assert len(er.selected_pages) == 18
    assert len(er.valid_pages) == 20


# ═══════════════════════════════════════════════════════════════════════════
# Wiring guards (house-style policy tests — same approach as the .3.4/.3.5
# stoplist policy tests: assert the wiring exists so a refactor can't
# silently restore the whole-book number)
# ═══════════════════════════════════════════════════════════════════════════

_SRC_CONVERTER = "core/pipeline/converter_impl.py"
_SRC_EXTRACTION = "core/pipeline/conversion/extraction.py"
# V0.4.26 (Phase 3 commit 1): the end-of-run diagnostic block moved
# VERBATIM to conversion/reporting.py — the diagnostic-line pin follows the
# moved body (union semantics, like the phase-gate pins in
# test_v18202_system_fixes.py).
_SRC_REPORTING = "core/pipeline/conversion/reporting.py"


def _read_src(rel: str) -> str:
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / rel
    return p.read_text(encoding="utf-8")


def test_converter_wires_computed_pages_processed():
    """convert() must fill pages_processed from compute_pages_processed —
    never from the raw analysis.total_pages again."""
    src = _read_src(_SRC_CONVERTER)
    assert "pages_processed=_pages_processed" in src
    assert "pages_processed=total_pages" not in src
    assert "_pages_processed = compute_pages_processed(" in src


def test_converter_diagnostic_reports_selection_when_active():
    """The closing diagnostic summary shows the honest number next to the
    book total when a selection limited the run.

    V0.4.26 (Phase 3 commit 1): the diagnostic block lives in
    conversion/reporting.py now (run_diagnostic_summary) — read both
    modules so the pin keeps its union semantics over the moved body."""
    src = _read_src(_SRC_CONVERTER) + _read_src(_SRC_REPORTING)
    assert "Pages processed: {_pages_processed}" in src


def test_extraction_snapshots_pre_overlap_selection():
    """run_extraction must snapshot selected_pages BEFORE the overlap
    merge (the overlap inflates 18 → 20)."""
    src = _read_src(_SRC_EXTRACTION)
    assert "_selected_pages" in src
    assert "selected_pages=_selected_pages" in src
    # the snapshot must appear BEFORE the overlap expansion in the file
    # V18.20.3.12: pin modernized Optional[set] -> set | None (ruff UP045).
    assert src.index("_selected_pages: set | None") < src.index(
        "valid_pages = expand_with_overlap("
    )


def test_wizard_modal_reads_result_field():
    """The completion modal renders result.pages_processed — the single
    source of truth fixed at the pipeline level (no UI-side recompute
    that could drift)."""
    src = _read_src("ui_qt/views/wizard_view.py")
    assert "Pages processed: {result.pages_processed}" in src
