"""P2 (Test-Net Deepening) — hermetic tests for core/pdf/content_filter.py.

Baseline: content_filter.py was 27% covered (113/154 lines missed). These
tests drive the REAL rule-based classifier (no mocks at all — the module is
pure-Python text heuristics):

  - constructor defaults + academic overrides
  - classify_page: blank / academic / category-pattern / TOC-density /
    too-short / content paths (English + Persian patterns)
  - _page_has_substantial_text branch-by-branch (alnum floor, digit-ratio
    floor, min-words floor, academic leniency)
  - classify_pages / filter_pages / get_skip_reasons
  - filter_segment_content: page-marker splitting, per-page filtering,
    all-filtered fallback, short-filtered (H12) behavior, no-marker fallback

Characterization notes pinned by these tests (see worklog-P2-B2):
  - the category patterns are ^/$-anchored WITHOUT re.MULTILINE, so a
    multi-line page whose first line is "Table of Contents" is NOT matched
    by the toc pattern (it falls through to the TOC-density heuristic);
  - the "weak match" (confidence 0.70) full-text loop is unreachable for
    any input (proof: a match requires the pattern to consume the whole
    joined text, which implies the first-10-lines check already matched).

Run: COVERAGE_FILE=.coverage.p2b2 python3 -m pytest tests/test_p2_pdf_tables_content_filter.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.pdf.content_filter import ContentFilter  # noqa: E402

FILLER = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod."


# ── Constructor ──────────────────────────────────────────────────────────────


class TestConstructor:
    def test_default_thresholds(self):
        cf = ContentFilter()
        assert cf.min_content_chars == 80
        assert cf.toc_density_threshold == 0.40
        assert cf.min_alnum_for_blank == 10
        assert cf.is_academic is False
        assert callable(cf.log)

    def test_academic_overrides(self):
        cf = ContentFilter(is_academic=True)
        assert cf.min_content_chars == 20
        assert cf.toc_density_threshold == 0.45
        assert cf.min_alnum_for_blank == 5
        assert cf.is_academic is True

    def test_custom_thresholds_respected(self):
        cf = ContentFilter(min_content_chars=42, toc_density_threshold=0.9)
        assert cf.min_content_chars == 42
        assert cf.toc_density_threshold == 0.9
        assert cf.min_alnum_for_blank == 10

    def test_log_callback_used(self):
        msgs: list[tuple[str, str]] = []

        def cb(msg, level="INFO"):
            msgs.append((msg, level))

        cf = ContentFilter(log_callback=cb)
        cf.classify_pages({3: "References"})
        assert msgs, "log callback should have been invoked by classify_pages"

    def test_compiled_patterns_cover_all_categories(self):
        cf = ContentFilter()
        assert set(cf._compiled_patterns) == {
            "toc",
            "index",
            "references",
            "copyright",
            "dedication",
            "acknowledgments",
            "preface_foreword",
        }


# ── classify_page — blank / empty ────────────────────────────────────────────


class TestClassifyBlank:
    def test_empty_string_is_blank(self):
        r = ContentFilter().classify_page("")
        assert r["is_content"] is False
        assert r["category"] == "blank"
        assert r["confidence"] == 1.0

    def test_whitespace_only_is_blank(self):
        r = ContentFilter().classify_page("   \n\t  \n  ")
        assert r["is_content"] is False
        assert r["category"] == "blank"

    def test_low_alnum_is_blank(self):
        # "hello" has 5 alnum < 10 floor → blank
        r = ContentFilter().classify_page("hello")
        assert r["is_content"] is False
        assert r["category"] == "blank"
        assert r["confidence"] == 0.9

    def test_digit_heavy_short_page_is_blank(self):
        # 10 alnum digits / 34 stripped chars = 0.29 ratio < 0.3 → blank
        r = ContentFilter().classify_page("............ 12345 ............ 67890")
        assert r["is_content"] is False
        assert r["category"] == "blank"

    def test_academic_digit_heavy_short_page_is_blank(self):
        # academic floor is 5 alnum (passes), but ratio 6/26 = 0.23 < 0.3 → blank
        r = ContentFilter(is_academic=True).classify_page(".......... 123456 ..........")
        assert r["is_content"] is False
        assert r["category"] == "blank"

    def test_single_word_page_is_blank_non_academic(self):
        # 15 alnum, ratio fine, but only 1 word → blank (words floor)
        r = ContentFilter().classify_page("Helloooooo 12345")
        assert r["is_content"] is False
        assert r["category"] == "blank"

    def test_substantial_single_word_kept_for_academic(self):
        # same page with is_academic: words floor skipped → passes blank check
        # (22 stripped chars ≥ the academic min_content_chars of 20)
        r = ContentFilter(is_academic=True).classify_page("Helloooooo 123456789012")
        assert r["is_content"] is True
        assert r["category"] == "content"


# ── classify_page — academic content detection ───────────────────────────────


class TestClassifyAcademic:
    def test_table_row_detected(self):
        cf = ContentFilter(is_academic=True)
        r = cf.classify_page("| col a | col b | col c |\n|---|---|---|\n| 1 | 2 | 3 |")
        assert r["is_content"] is True
        assert r["category"] == "academic"
        assert r["confidence"] == 0.95

    def test_figure_caption_detected(self):
        cf = ContentFilter(is_academic=True)
        r = cf.classify_page("Figure 3 shows the result of the experiment described above.")
        assert r["category"] == "academic"

    def test_fig_abbreviation_caption_detected(self):
        cf = ContentFilter(is_academic=True)
        r = cf.classify_page("Fig. 2 illustrates the growth curve over time.")
        assert r["category"] == "academic"

    def test_section_header_detected(self):
        cf = ContentFilter(is_academic=True)
        r = cf.classify_page("Abstract\n" + FILLER)
        assert r["category"] == "academic"

    def test_methods_header_detected(self):
        cf = ContentFilter(is_academic=True)
        r = cf.classify_page("Materials and Methods\n" + FILLER)
        assert r["category"] == "academic"

    def test_academic_detection_off_for_non_academic_filter(self):
        # with is_academic=False the academic gate is a hard False
        cf = ContentFilter()
        assert cf._page_has_academic_content("Figure 3 shows data.") is False

    def test_non_academic_page_with_table_row_not_academic(self):
        # non-academic filter: table row page falls through to the normal flow
        r = ContentFilter().classify_page("| col a | col b |\n| 1 | 2 |")
        assert r["category"] != "academic"


# ── classify_page — category patterns (strong first-line matches) ────────────


class TestClassifyCategories:
    def test_toc_header(self):
        r = ContentFilter().classify_page("Table of Contents")
        assert r["is_content"] is False
        assert r["category"] == "toc"
        assert r["confidence"] == 0.95

    def test_toc_header_with_entries_falls_to_density(self):
        # The ^…$ patterns lack re.MULTILINE: a TOC heading followed by entries
        # does NOT hit the toc pattern — it is caught by the density heuristic.
        text = "Table of Contents\nChapter One ......... 12\nChapter Two ......... 34"
        r = ContentFilter().classify_page(text)
        assert r["is_content"] is False
        assert r["category"] == "toc"
        assert r["confidence"] == 0.85

    def test_works_cited(self):
        r = ContentFilter().classify_page("Works Cited")
        assert r["category"] == "references"
        assert r["confidence"] == 0.95

    def test_further_reading(self):
        r = ContentFilter().classify_page("Further Reading")
        assert r["category"] == "references"

    def test_copyright_line_first(self):
        r = ContentFilter().classify_page("Copyright © 2024 Acme Press\n" + FILLER)
        assert r["category"] == "copyright"
        assert r["confidence"] == 0.95

    def test_copyright_symbol_year(self):
        r = ContentFilter().classify_page("© 2024 Acme Press")
        assert r["category"] == "copyright"

    def test_all_rights_reserved(self):
        r = ContentFilter().classify_page("All rights reserved by the publisher")
        assert r["category"] == "copyright"

    def test_persian_copyright(self):
        r = ContentFilter().classify_page("تمامی حقوق محفوظ است")
        assert r["category"] == "copyright"

    def test_persian_translator_note_is_preface(self):
        r = ContentFilter().classify_page("یادداشت مترجم")
        assert r["category"] == "preface_foreword"

    def test_persian_dedication(self):
        r = ContentFilter().classify_page("به یاد استادان بزرگ")
        assert r["category"] == "dedication"

    def test_copyright_not_first_line_is_not_matched(self):
        # Suspected bug (pinned): the patterns are ^-anchored without
        # re.MULTILINE, so a copyright line anywhere but the very start of
        # the page text is NOT matched — the page passes as content.
        text = "\n".join([FILLER, FILLER, "Copyright © 2024 Buried Line", FILLER])
        r = ContentFilter().classify_page(text)
        assert r["is_content"] is True
        assert r["category"] == "content"


# ── academic-mode single-word category pages ────────────────────────────────


class TestClassifyCategoriesAcademicMode:
    """Single-word pages are blank in non-academic mode (words floor), but the
    academic filter lowers the alnum floor to 5 and skips the words floor, so
    the one-line category patterns become reachable."""

    def test_index(self):
        r = ContentFilter(is_academic=True).classify_page("Index")
        assert r["category"] == "index"

    def test_contents(self):
        r = ContentFilter(is_academic=True).classify_page("Contents")
        assert r["category"] == "toc"

    def test_dedication(self):
        r = ContentFilter(is_academic=True).classify_page("Dedication")
        assert r["category"] == "dedication"

    def test_acknowledgments(self):
        r = ContentFilter(is_academic=True).classify_page("Acknowledgments")
        assert r["category"] == "acknowledgments"

    def test_preface(self):
        r = ContentFilter(is_academic=True).classify_page("Preface")
        assert r["category"] == "preface_foreword"

    def test_references(self):
        r = ContentFilter(is_academic=True).classify_page("References")
        assert r["category"] == "references"

    def test_persian_toc(self):
        r = ContentFilter(is_academic=True).classify_page("فهرست")
        assert r["category"] == "toc"

    def test_persian_index(self):
        r = ContentFilter(is_academic=True).classify_page("نمایه")
        assert r["category"] == "index"

    def test_persian_references(self):
        r = ContentFilter(is_academic=True).classify_page("منابع")
        assert r["category"] == "references"

    def test_persian_dedication(self):
        r = ContentFilter(is_academic=True).classify_page("تقدیم به")
        assert r["category"] == "dedication"

    def test_persian_acknowledgments(self):
        r = ContentFilter(is_academic=True).classify_page("سپاسگزاری")
        assert r["category"] == "acknowledgments"

    def test_persian_preface(self):
        r = ContentFilter(is_academic=True).classify_page("پیشگفتار")
        assert r["category"] == "preface_foreword"


# ── classify_page — density / too-short / content ────────────────────────────


class TestClassifyDensityAndLength:
    def test_toc_density(self):
        text = "\n".join(
            [
                "Settings Overview ......... 12",
                "Advanced Tabs ......... 34",
                "Profiles ........ 56",
                "Security ......... 78",
                FILLER,
            ]
        )
        r = ContentFilter().classify_page(text)
        assert r["is_content"] is False
        assert r["category"] == "toc"
        assert r["confidence"] == 0.85
        assert "density" in r["reason"].lower()

    def test_density_threshold_not_reached_is_content(self):
        # only 1 of 5 lines looks like a TOC entry → passes
        text = "\n".join([FILLER, FILLER, FILLER, FILLER, "Profiles ........ 56"])
        r = ContentFilter().classify_page(text)
        assert r["is_content"] is True
        assert r["category"] == "content"

    def test_too_short(self):
        r = ContentFilter().classify_page("Hello world foo bar baz qux.")
        assert r["is_content"] is False
        assert r["category"] == "too_short"
        assert r["confidence"] == 0.60

    def test_plain_content_page(self):
        r = ContentFilter().classify_page("\n".join([FILLER] * 5))
        assert r["is_content"] is True
        assert r["category"] == "content"
        assert r["confidence"] == 1.0


# ── helpers ─────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_strip_lines(self):
        cf = ContentFilter()
        assert cf._strip_lines(" a \n\n  b \n") == ["a", "b"]

    def test_line_looks_like_toc_entry_dot_leader(self):
        cf = ContentFilter()
        assert cf._line_looks_like_toc_entry(".......... 42") is True

    def test_line_looks_like_toc_entry_trailing_number(self):
        cf = ContentFilter()
        assert cf._line_looks_like_toc_entry("Chapter Two 34") is True

    def test_line_looks_like_toc_entry_plain_text(self):
        cf = ContentFilter()
        assert cf._line_looks_like_toc_entry("just some words here") is False

    def test_line_looks_like_toc_entry_lone_number(self):
        # a lone number: no dot leader, and only one whitespace token → False
        cf = ContentFilter()
        assert cf._line_looks_like_toc_entry("42") is False

    def test_detect_toc_by_density_empty(self):
        cf = ContentFilter()
        assert cf._detect_toc_by_density([]) is False


# ── batch APIs ──────────────────────────────────────────────────────────────


class TestBatchApis:
    def _pages(self):
        return {
            1: "Table of Contents",
            2: "\n".join([FILLER] * 5),
            3: "Hello world foo bar baz qux.",
        }

    def test_classify_pages(self):
        cf = ContentFilter()
        results = cf.classify_pages(self._pages())
        assert set(results) == {1, 2, 3}
        assert results[1]["category"] == "toc"
        assert results[2]["category"] == "content"
        assert results[3]["category"] == "too_short"

    def test_filter_pages_keeps_content_only(self):
        cf = ContentFilter()
        kept = cf.filter_pages(self._pages())
        assert set(kept) == {2}
        assert kept[2] == "\n".join([FILLER] * 5)

    def test_filter_pages_logs_skips(self):
        msgs: list[str] = []
        cf = ContentFilter(log_callback=lambda m, level="INFO": msgs.append(m))
        cf.filter_pages({1: "Table of Contents"})
        assert any("Page 1 skipped" in m for m in msgs)

    def test_get_skip_reasons(self):
        cf = ContentFilter()
        reasons = cf.get_skip_reasons(self._pages())
        assert 2 not in reasons
        assert "TOC" in reasons[1] or "toc" in reasons[1].lower()
        assert reasons[3]


# ── filter_segment_content ──────────────────────────────────────────────────


class TestFilterSegmentContent:
    def _marker_content(self):
        toc_page = "\n".join(
            ["Settings ......... 12", "Profiles ......... 34", "Security ......... 56"]
        )
        content_page = "\n".join([FILLER] * 6)
        return (
            f"<!-- original page 1 -->\n{toc_page}\n\n"
            f"<!-- original page 2 -->\n{content_page}\n\n"
            f"<!-- original page 3 -->\n{content_page}"
        )

    def test_empty_content_passthrough(self):
        cf = ContentFilter()
        assert cf.filter_segment_content("") == ""

    def test_toc_page_dropped_content_pages_kept(self):
        cf = ContentFilter()
        result = cf.filter_segment_content(self._marker_content(), 1, 3, min_tokens_keep=5)
        assert "original page 1" not in result
        assert "original page 2" in result
        assert "original page 3" in result

    def test_all_filtered_falls_back_to_first_500_chars(self):
        cf = ContentFilter()
        toc_page = "\n".join(["Settings ......... 12"] * 8)  # dense TOC → skipped
        content = f"<!-- original page 1 -->\n{toc_page}"
        result = cf.filter_segment_content(content, 1, 1)
        assert result == content[:500] + "\n\n[...]"

    def test_short_filtered_content_kept_not_original(self):
        # H12 fix: even when the filtered remainder is below the token floor
        # the filtered (clean) content is returned, NOT the original.
        cf = ContentFilter()
        content = (
            "<!-- original page 1 -->\nSettings ......... 12\n\n"
            f"<!-- original page 2 -->\n{FILLER}\n{FILLER}"
        )
        result = cf.filter_segment_content(content, 1, 2, min_tokens_keep=10_000)
        assert "original page 1" not in result
        assert "original page 2" in result
        assert FILLER in result

    def test_no_markers_falls_back(self):
        cf = ContentFilter()
        content = "\n".join([FILLER] * 4)
        result = cf.filter_segment_content(content, 1, 1)
        assert result == content[:500] + "\n\n[...]"

    def test_preamble_before_first_marker_is_dropped(self):
        # Suspected bug (pinned): text before the first page marker is NOT
        # re-emitted — parts[0] of the regex split is silently discarded.
        cf = ContentFilter()
        content = "PREAMBLE TEXT BEFORE MARKERS\n\n<!-- original page 1 -->\n" + "\n".join(
            [FILLER] * 6
        )
        result = cf.filter_segment_content(content, 1, 1, min_tokens_keep=5)
        assert "PREAMBLE" not in result

    def test_logging_of_skipped_page(self):
        msgs: list[str] = []
        cf = ContentFilter(log_callback=lambda m, level="INFO": msgs.append(m))
        cf.filter_segment_content(
            "<!-- original page 1 -->\nSettings ......... 12", 1, 1, min_tokens_keep=5
        )
        assert any("Skipping page 1" in m for m in msgs)
