"""Phase-5 P1 / W8 (first tranche): characterization net for
``core/pipeline/conversion/visual_features.py`` (``ConverterVisualMixin``).

WHY THIS FILE EXISTS
--------------------
The Phase-7 SWOT (Task 12-19) flagged the 3 ``conversion/*`` stage runners
as the "extracted ≠ tested" debt (W8 / Phase-5 P1): ``postprocess`` (22%
cov), ``visual_features`` (25%), ``output_runner`` (38%).  This file is the
visual_features installment — the sibling of
``test_conversion_postprocess_characterization.py``.

The mixin (V0.4.19 VERBATIM de-monolithization from converter_impl.py)
carries 5 methods that read convert()-locals threaded as parameters:
``_extract_covers``, ``_re_extract_with_ocr``, ``_targeted_ocr_repair``,
``_run_visual_region_cropping``, ``_run_footnote_extraction``.  The first
tranche pins:

  1. The mixin class shape (the 5 documented methods are present).
  2. ``_targeted_ocr_repair`` — the V18.1 P8 binary-search page-marker
     mapping, the V18.2.15 traceable logging at both paths, the
     proportional-heuristic fallback, the pages_to_ocr intersection, the
     "produced no text" short-circuit, the anchor-splicing success path,
     and the per-range DEBUG replace log.
  3. ``_extract_covers`` — the [front] / [front, back] page-list logic,
     the V10.12.1 ``toc_entries=None`` skip guard, the chapter-screenshot
     INFO log, and the per-page fail-soft WARNING.
  4. ``_run_footnote_extraction`` — the cancel gate, the no-markdown /
     no-footnotes no-op paths, the success INFO log, and the footnotes
     file write.
  5. ``_run_visual_region_cropping`` — the extract_visual_regions=False
     DEBUG skip log, the cancel gate, and the "scanning N page(s)" +
     "0 region(s)" bookend logs (the cropper runs without a real PDF →
     0 regions, no partial failure).
  6. Source-pin tests: the exact log-message skeletons present in
     visual_features.py source (Phase-3 source-pin precedent — a future
     wording/level/emoji change breaks the test).

All hermetic (no ~/.elixir, no network, no Qt, no real conversion — fake
``self`` object providing the standard Converter surface; the
``_re_extract_with_ocr`` method is OVERRIDDEN on the fake so the test can
return canned OCR text without hitting the real PDF/OCR stack).

All expected values were probed empirically against the live code before
writing (no invented expected values); all fixtures use generic content
("My Book", "Chapter One", "hello world foo a b") per AGENTS.md Rule 1.

Run: ``pytest tests/test_conversion_visual_features_characterization.py -v --no-cov``
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.pipeline.conversion.visual_features import ConverterVisualMixin

# ════════════════════════════════════════════════════════════════════════════
# Section 0 — hermetic fakes (Phase-3 _RecordingSelf precedent)
# ════════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VISUAL_FEATURES_SRC_PATH = (
    _PROJECT_ROOT / "core" / "pipeline" / "conversion" / "visual_features.py"
)


def visual_features_src() -> str:
    """The current visual_features.py source (for source-pin tests)."""
    return _VISUAL_FEATURES_SRC_PATH.read_text(encoding="utf-8")


class _FakeSettings:
    """Stand-in for utils.settings.Settings (hermetic .get)."""

    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


class _FakePaths:
    """Stand-in for OutputPaths — provides screenshot(label), regions_dir,
    and footnotes(book_title) (the surface _extract_covers /
    _run_visual_region_cropping / _run_footnote_extraction read)."""

    def __init__(self, base_dir=None):
        self._base = base_dir or Path("/tmp/_vf_char_probe")
        self._base.mkdir(parents=True, exist_ok=True)
        self.regions_dir = self._base / "regions"
        self.screenshot_dir = self._base / "screenshots"

    def screenshot(self, label):
        return self.screenshot_dir / f"{label}.jpg"

    def footnotes(self, book_title):
        return self._base / f"{book_title}.footnotes.md"


class _FakeRequest:
    """Stand-in for ConversionRequest (visual_features reads input_path,
    selected_chapters, page_range_*, manual_segments, extract_visual_regions,
    password)."""

    def __init__(self, **overrides):
        self.input_path = "/nonexistent.pdf"
        self.selected_chapters = None
        self.page_range_start = None
        self.page_range_end = None
        self.manual_segments = None
        self.extract_visual_regions = True
        self.password = None
        for k, v in overrides.items():
            setattr(self, k, v)


class _FakeConverter:
    """Minimal fake ``self`` for the ConverterVisualMixin methods.

    Binds the mixin's _extract_covers, _targeted_ocr_repair,
    _run_visual_region_cropping, _run_footnote_extraction directly (the
    methods take ``self`` but only reach into the documented attributes —
    Phase-3 ``_RecordingSelf`` precedent).

    The mixin's ``_re_extract_with_ocr`` is OVERRIDDEN here so the test can
    return canned OCR text (None/empty/short/long) without hitting the real
    PDF/OCR stack — this is what makes the success-path tests hermetic.
    """

    def __init__(
        self,
        request=None,
        settings=None,
        paths=None,
        output_dir=None,
        full_markdown_path=None,
        cancel_returns=False,
        re_extract_return=None,
    ):
        self.request = request or _FakeRequest()
        self.settings = settings or _FakeSettings({"paths.poppler": None})
        self.paths = paths or _FakePaths()
        self.output_dir = output_dir or Path("/tmp/_vf_char_probe_out")
        self.full_markdown_path = full_markdown_path or Path("/tmp/_vf_char_probe/full.md")
        self._logs: list[tuple[str, str]] = []
        self._progress: list[float] = []
        self._statuses: list[str] = []
        self._partial_failures: list[tuple[str, str]] = []
        self._cancel_returns = cancel_returns
        self._re_extract_return = re_extract_return
        self._re_extract_calls: list[list[int]] = []
        # full_markdown_path is read by _run_footnote_extraction; ensure the
        # parent dir exists so test fixtures that write to it succeed.
        self.full_markdown_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str, level: str = "INFO") -> None:
        self._logs.append((message, level))

    def _update_progress(self, value: float) -> None:
        self._progress.append(value)

    def _update_status(self, message: str) -> None:
        self._statuses.append(message)

    def _cancel_requested(self, phase: str = "") -> bool:
        return self._cancel_returns

    def _record_partial_failure(self, subsystem: str, error: Exception) -> None:
        self._partial_failures.append((subsystem, str(error)))

    def _derive_page_ranges_from_toc(self, toc_entries, selected_chapters, total_pages):
        # Canned response — the chapter-page derivation lives elsewhere.
        return {1, 2, 3}

    def _re_extract_with_ocr(self, page_nums):
        # OVERRIDE the mixin's method so the test can return canned OCR
        # text without hitting the real PDF/OCR stack.
        self._re_extract_calls.append(list(page_nums))
        if self._re_extract_return is not None:
            return self._re_extract_return
        return ""

    def messages(self, level: str | None = None) -> list[str]:
        return [m for m, lvl in self._logs if level is None or lvl == level]

    # Bind the mixin methods (NOT _re_extract_with_ocr — we override above).
    _extract_covers = ConverterVisualMixin._extract_covers
    _targeted_ocr_repair = ConverterVisualMixin._targeted_ocr_repair
    _run_visual_region_cropping = ConverterVisualMixin._run_visual_region_cropping
    _run_footnote_extraction = ConverterVisualMixin._run_footnote_extraction


# ════════════════════════════════════════════════════════════════════════════
# 1. Mixin class shape (the 5 documented methods are present)
# ════════════════════════════════════════════════════════════════════════════


class TestMixinClassShape:
    """Pin the public surface of the ConverterVisualMixin class."""

    def test_mixin_has_5_documented_methods(self):
        """The mixin must define the 5 documented methods (module docstring)."""
        for name in (
            "_extract_covers",
            "_re_extract_with_ocr",
            "_targeted_ocr_repair",
            "_run_visual_region_cropping",
            "_run_footnote_extraction",
        ):
            assert hasattr(ConverterVisualMixin, name), f"missing method: {name}"

    def test_extract_covers_takes_total_pages_and_toc_entries(self):
        """_extract_covers(total_pages, toc_entries=None) — the V10.12.1 fix
        made toc_entries a parameter (was a bare name that caused NameError)."""
        import inspect

        sig = inspect.signature(ConverterVisualMixin._extract_covers)
        params = list(sig.parameters.keys())
        # 'self' is included because the method is unbound.
        assert params == ["self", "total_pages", "toc_entries"], f"params: {params}"
        assert sig.parameters["toc_entries"].default is None

    def test_run_visual_region_cropping_takes_total_pages_and_toc_entries(self):
        import inspect

        sig = inspect.signature(ConverterVisualMixin._run_visual_region_cropping)
        params = list(sig.parameters.keys())
        assert params == ["self", "total_pages", "toc_entries"], f"params: {params}"
        assert sig.parameters["toc_entries"].default is None

    def test_run_footnote_extraction_takes_book_title(self):
        import inspect

        sig = inspect.signature(ConverterVisualMixin._run_footnote_extraction)
        params = list(sig.parameters.keys())
        assert params == ["self", "book_title"], f"params: {params}"

    def test_targeted_ocr_repair_default_total_pages_is_17(self):
        """The default total_pages=17 (the documented module-marker count)."""
        import inspect

        sig = inspect.signature(ConverterVisualMixin._targeted_ocr_repair)
        assert sig.parameters["total_pages"].default == 17

    def test_targeted_ocr_repair_default_pages_to_ocr_is_none(self):
        import inspect

        sig = inspect.signature(ConverterVisualMixin._targeted_ocr_repair)
        assert sig.parameters["pages_to_ocr"].default is None


# ════════════════════════════════════════════════════════════════════════════
# 2. _targeted_ocr_repair — empty garbled_ranges early-exit
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairEmptyRanges:
    """The `if not garbled_ranges: return text` early-exit at the top of
    _targeted_ocr_repair — no logs, no OCR call, return text unchanged."""

    def test_empty_ranges_returns_text_unchanged(self):
        conv = _FakeConverter()
        result = conv._targeted_ocr_repair("some text", [], total_pages=10)
        assert result == "some text"

    def test_empty_ranges_emits_no_logs(self):
        conv = _FakeConverter()
        conv._targeted_ocr_repair("some text", [], total_pages=10)
        assert conv._logs == []

    def test_empty_ranges_does_not_call_re_extract(self):
        conv = _FakeConverter()
        conv._targeted_ocr_repair("some text", [], total_pages=10)
        assert conv._re_extract_calls == []


# ════════════════════════════════════════════════════════════════════════════
# 3. _targeted_ocr_repair — page-marker binary-search path (V18.1 P8)
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairPageMarkerPath:
    """When the text has ``<!-- original page N -->`` markers, the method uses
    bisect to map garbled char ranges to source pages (V18.1 P8 accurate
    mapping). The V18.2.15 INFO log records the mapping."""

    def test_page_marker_mapping_info_log(self):
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        info_msgs = conv.messages("INFO")
        # Empirically: "2 markers, 1 ranges" (after ±1 expansion: pages 1-2).
        assert any(
            "🎯 V18.2.15 Targeted OCR: page-marker mapping" in m
            and "2 markers" in m
            and "1 ranges" in m
            for m in info_msgs
        ), f"expected page-marker mapping INFO log, got: {info_msgs}"

    def test_targeted_ocr_pages_count_info_log(self):
        """The 'Targeted OCR: N page(s) to OCR' INFO log + the contiguous
        range hint ('pages A-B if contiguous, else scattered')."""
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        info_msgs = conv.messages("INFO")
        # Empirically: 2 pages (1-2), 66 chars original, 23 chars garbled.
        assert any(
            "🎯 Targeted OCR: 2 page(s) to OCR" in m
            and "pages 1-2 if contiguous" in m
            and "Original text:" in m
            and "garbled:" in m
            for m in info_msgs
        ), f"expected pages-count INFO log, got: {info_msgs}"

    def test_re_extract_called_with_sorted_ocr_pages(self):
        """The method calls _re_extract_with_ocr with the sorted ocr_pages
        list (after the ±1 expansion + intersection)."""
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        assert len(conv._re_extract_calls) == 1
        # ±1 expansion of page 1 = {1, 2} → sorted [1, 2].
        assert conv._re_extract_calls[0] == [1, 2]


# ════════════════════════════════════════════════════════════════════════════
# 4. _targeted_ocr_repair — proportional-heuristic fallback (no markers)
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairProportionalFallback:
    """When the text has no page markers, the method falls back to a
    proportional heuristic (char-offset / text_len * total_pages). A DEBUG
    log warns the fallback is less accurate."""

    def test_no_markers_emits_fallback_warning_debug_log(self):
        conv = _FakeConverter()
        text = "garbled text content " * 200  # ~4000 chars, no markers
        conv._targeted_ocr_repair(text, [(0, 100)], total_pages=10)
        debug_msgs = conv.messages("DEBUG")
        assert any(
            "No page markers found — falling back to proportional page mapping" in m
            and "less accurate on figure-heavy pages" in m
            for m in debug_msgs
        ), f"expected fallback DEBUG log, got: {debug_msgs}"


# ════════════════════════════════════════════════════════════════════════════
# 5. _targeted_ocr_repair — empty ocr_pages after intersection
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairEmptyIntersection:
    """When pages_to_ocr is provided AND the expanded valid set doesn't
    intersect with the garbled-derived ocr_pages, the method short-circuits
    with ONLY the page-marker mapping INFO log (no pages-count log, no OCR
    call) — the `if not ocr_pages: return text` guard."""

    def test_empty_intersection_returns_text_unchanged(self):
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        # pages_to_ocr=[100] doesn't intersect with garbled pages {1, 2, 3}
        # (expanded: {1, 2, 3} ∩ {99, 100, 101} = ∅).
        result = conv._targeted_ocr_repair(text, [(7, 30)], total_pages=10, pages_to_ocr=[100])
        assert result == text  # unchanged

    def test_empty_intersection_skips_pages_count_log(self):
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=10, pages_to_ocr=[100])
        info_msgs = conv.messages("INFO")
        # Only the page-marker mapping INFO log fires — NOT the pages-count log.
        assert any("page-marker mapping" in m for m in info_msgs)
        assert not any("page(s) to OCR" in m for m in info_msgs), (
            f"expected NO pages-count log on empty intersection, got: {info_msgs}"
        )

    def test_empty_intersection_does_not_call_re_extract(self):
        conv = _FakeConverter()
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=10, pages_to_ocr=[100])
        assert conv._re_extract_calls == []


# ════════════════════════════════════════════════════════════════════════════
# 6. _targeted_ocr_repair — "produced no text" short-circuit (< 100 chars)
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairProducedNoText:
    """When _re_extract_with_ocr returns falsy OR len < 100, the WARNING
    'produced no text' fires + the original text is returned unchanged."""

    def test_empty_ocr_return_emits_produced_no_text_warning(self):
        conv = _FakeConverter(re_extract_return="")
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        result = conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        warn_msgs = conv.messages("WARNING")
        assert "  ⚠️ Targeted OCR produced no text" in warn_msgs
        assert result == text  # unchanged

    def test_short_ocr_return_emits_produced_no_text_warning(self):
        """OCR text < 100 chars also triggers the 'produced no text' path."""
        conv = _FakeConverter(re_extract_return="x" * 99)  # 99 chars < 100
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        result = conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        assert "  ⚠️ Targeted OCR produced no text" in conv.messages("WARNING")
        assert result == text


# ════════════════════════════════════════════════════════════════════════════
# 7. _targeted_ocr_repair — anchor-splicing success path (OCR ≥ 100 chars)
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairSuccessPath:
    """When _re_extract_with_ocr returns ≥ 100 chars, the anchor-splicing
    path fires: a DEBUG 'Replaced garbled section (N chars) with OCR text
    (M chars)' log per range, and the result contains the OCR text."""

    def test_success_emits_replace_debug_log(self):
        # OCR return must be ≥ 100 chars (the `len(ocr_text) < 100` guard).
        long_ocr = "replacement text content. " * 10  # 250 chars
        conv = _FakeConverter(re_extract_return=long_ocr)
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        debug_msgs = conv.messages("DEBUG")
        assert any(
            "🔧 Replaced garbled section (" in m and "chars) with OCR text (" in m and "chars)" in m
            for m in debug_msgs
        ), f"expected replace DEBUG log, got: {debug_msgs}"

    def test_success_result_contains_ocr_text(self):
        long_ocr = "replacement text content. " * 10  # 250 chars
        conv = _FakeConverter(re_extract_return=long_ocr)
        text = "before<!-- original page 1 -->garbled<!-- original page 2 -->after"
        result = conv._targeted_ocr_repair(text, [(7, 30)], total_pages=2)
        # The OCR text is spliced into the result around the garbled section.
        # (The exact substring depends on the anchor-finding logic + the
        # .strip() applied to ocr_replacement; pin a stable substring that
        # survives both — the OCR text body.)
        assert "replacement text content." in result
        # And the splicing structure: \n + replacement + \n (the offset
        # bookkeeping uses +2 for the \n wrappers).
        assert "\nreplacement text content." in result

    def test_success_multiple_ranges_each_emit_replace_log(self):
        """Two garbled ranges → two DEBUG replace logs (the per-range loop)."""
        long_ocr = "replacement text content. " * 10  # 250 chars
        conv = _FakeConverter(re_extract_return=long_ocr)
        text = (
            "before<!-- original page 1 -->garbled1"
            "<!-- original page 2 -->middle"
            "<!-- original page 3 -->garbled2"
            "<!-- original page 4 -->after"
        )
        conv._targeted_ocr_repair(text, [(7, 15), (60, 70)], total_pages=4)
        debug_msgs = conv.messages("DEBUG")
        replace_logs = [m for m in debug_msgs if "Replaced garbled section" in m]
        assert len(replace_logs) == 2, (
            f"expected 2 replace DEBUG logs (one per range), got: {replace_logs}"
        )


# ════════════════════════════════════════════════════════════════════════════
# 8. _extract_covers — page list logic + V10.12.1 toc_entries guard
# ════════════════════════════════════════════════════════════════════════════


class TestExtractCoversPageList:
    """The page list is ``[1] + ([total_pages] if total_pages >= 2 else [])``.
    So 1 page → just front_cover; 2+ pages → front_cover + back_cover.
    Each page that fails emits a WARNING 'Cover p.N: <error>'."""

    def test_one_page_only_front_cover_attempted(self):
        """total_pages=1 → only page 1 attempted (front cover)."""
        conv = _FakeConverter()
        conv._extract_covers(1, toc_entries=None)
        warn_msgs = conv.messages("WARNING")
        # Empirically: 1 WARNING log per page attempted.
        cover_warnings = [m for m in warn_msgs if "Cover p." in m]
        assert len(cover_warnings) == 1, (
            f"expected 1 Cover WARNING (front only), got: {cover_warnings}"
        )
        assert any("Cover p.1:" in m for m in cover_warnings)

    def test_five_pages_front_and_back_cover_attempted(self):
        """total_pages=5 → pages [1, 5] attempted (front + back)."""
        conv = _FakeConverter()
        conv._extract_covers(5, toc_entries=None)
        warn_msgs = conv.messages("WARNING")
        cover_warnings = [m for m in warn_msgs if "Cover p." in m]
        assert len(cover_warnings) == 2, (
            f"expected 2 Cover WARNINGs (front + back), got: {cover_warnings}"
        )
        assert any("Cover p.1:" in m for m in cover_warnings)
        assert any("Cover p.5:" in m for m in cover_warnings)


class TestExtractCoversTocEntriesGuard:
    """V10.12.1 bugfix: when toc_entries is None, the chapter-screenshot
    block is SKIPPED (was a bare name that caused NameError whenever the
    user selected chapters but TOC wasn't extracted yet)."""

    def test_toc_entries_none_skips_chapter_screenshots(self):
        """selected_chapters + toc_entries=None → NO 'Screenshotting' log."""
        conv = _FakeConverter(request=_FakeRequest(selected_chapters=["Chapter One"]))
        conv._extract_covers(5, toc_entries=None)
        info_msgs = conv.messages("INFO")
        assert not any("Screenshotting" in m for m in info_msgs), (
            f"expected NO 'Screenshotting' log when toc_entries is None, got: {info_msgs}"
        )

    def test_toc_entries_present_with_selected_chapters_emits_screenshotting_log(self):
        """selected_chapters + toc_entries present → the chapter-screenshot
        block fires with the INFO '📸 Screenshotting N selected chapter
        page(s)...' log."""
        conv = _FakeConverter(request=_FakeRequest(selected_chapters=["Chapter One"]))
        conv._extract_covers(5, toc_entries=[("Chapter One", 1, 3)])
        info_msgs = conv.messages("INFO")
        # Empirically: "Screenshotting 3 selected chapter page(s)..." (the
        # canned _derive_page_ranges_from_toc returns {1, 2, 3}).
        assert any("📸 Screenshotting 3 selected chapter page(s)..." in m for m in info_msgs), (
            f"expected 'Screenshotting' INFO log, got: {info_msgs}"
        )

    def test_no_selected_chapters_skips_chapter_screenshots(self):
        """Even with toc_entries present, no selected_chapters → no
        chapter-screenshot block."""
        conv = _FakeConverter(request=_FakeRequest(selected_chapters=None))
        conv._extract_covers(5, toc_entries=[("Chapter One", 1, 3)])
        info_msgs = conv.messages("INFO")
        assert not any("Screenshotting" in m for m in info_msgs)


# ════════════════════════════════════════════════════════════════════════════
# 9. _run_footnote_extraction — cancel + no-op paths + success path
# ════════════════════════════════════════════════════════════════════════════


class TestRunFootnoteExtraction:
    """The cancel gate skips the block. The no-markdown / no-footnotes
    paths silently no-op. The success path emits INFO '📝 Footnotes: N
    extracted' + writes the footnotes file."""

    def test_cancel_skips_block_silently(self):
        """When _cancel_requested returns True, the block is skipped — no
        logs, no partial failures, no file writes."""
        conv = _FakeConverter(cancel_returns=True)
        conv._run_footnote_extraction("My Book")
        assert conv._logs == []
        assert conv._partial_failures == []

    def test_no_markdown_file_no_ops_silently(self):
        """When full_markdown_path doesn't exist, full_text becomes "" → the
        `if full_text:` guard skips the block."""
        conv = _FakeConverter(full_markdown_path=Path("/tmp/_vf_char_nonexist/_nf.md"))
        conv._run_footnote_extraction("My Book")
        assert conv._logs == []
        assert conv._partial_failures == []

    def test_no_footnotes_in_text_no_ops_silently(self):
        """When extract_footnotes returns total_notes=0, no INFO log + no
        file write."""
        conv = _FakeConverter()
        conv.full_markdown_path.write_text("Just plain text with no footnotes here at all.")
        conv._run_footnote_extraction("My Book")
        info_msgs = conv.messages("INFO")
        assert not any("Footnotes:" in m for m in info_msgs)
        assert not conv.paths.footnotes("My Book").exists()

    def test_with_footnotes_emits_info_log_and_writes_file(self):
        """When extract_footnotes returns total_notes > 0, the INFO log fires
        + the footnotes file is written via paths.footnotes(book_title)."""
        conv = _FakeConverter()
        conv.full_markdown_path.write_text(
            "Intro.1\n\n1. First footnote content.\n\nMore text.2\n\n2. Second footnote here.\n"
        )
        conv._run_footnote_extraction("MyBook")
        info_msgs = conv.messages("INFO")
        # Empirically: "📝 Footnotes: 2 extracted"
        assert any("📝 Footnotes: 2 extracted" in m for m in info_msgs), (
            f"expected footnotes INFO log, got: {info_msgs}"
        )
        # The footnotes file was written.
        assert conv.paths.footnotes("MyBook").exists()
        content = conv.paths.footnotes("MyBook").read_text(encoding="utf-8")
        # The format_footnotes_for_summary output format.
        assert "### Footnotes & Endnotes" in content
        assert "[^1]: First footnote content." in content
        assert "[^2]: Second footnote here." in content


# ════════════════════════════════════════════════════════════════════════════
# 10. _run_visual_region_cropping — extract_visual_regions=False + cancel
# ════════════════════════════════════════════════════════════════════════════


class TestRunVisualRegionCroppingGuards:
    """The extract_visual_regions=False path emits a DEBUG skip log; the
    cancel path skips silently."""

    def test_extract_visual_regions_false_emits_skip_debug_log(self):
        conv = _FakeConverter(request=_FakeRequest(extract_visual_regions=False))
        conv._run_visual_region_cropping(5, toc_entries=None)
        debug_msgs = conv.messages("DEBUG")
        assert "  ⏭️ Visual-region cropper skipped (disabled in settings)" in debug_msgs

    def test_cancel_skips_cropper_silently(self):
        conv = _FakeConverter(cancel_returns=True)
        conv._run_visual_region_cropping(5, toc_entries=None)
        assert conv._logs == []
        assert conv._partial_failures == []


class TestRunVisualRegionCroppingScanningLog:
    """With a page_range set + extract_visual_regions=True, the cropper
    emits the '📐 Visual-region cropper: scanning N page(s)' INFO log +
    the closing '📐 Visual-region cropper: 0 region(s) (...)' INFO log
    (the cropper runs Layer A on a non-existent PDF → 0 regions, no
    partial failure — the fail-soft path)."""

    def test_scanning_info_log_message_format(self):
        conv = _FakeConverter(request=_FakeRequest(page_range_start=2, page_range_end=4))
        conv._run_visual_region_cropping(10, toc_entries=None)
        info_msgs = conv.messages("INFO")
        # Empirically: page_range 2-4 = 3 pages → "scanning 3 page(s) for
        # diagrams/charts/tables".
        assert any(
            "📐 Visual-region cropper: scanning 3 page(s) for diagrams/charts/tables" in m
            for m in info_msgs
        ), f"expected scanning INFO log, got: {info_msgs}"

    def test_zero_regions_closing_info_log(self):
        """When the cropper finds 0 regions (the no-PDF path), the closing
        INFO log '📐 Visual-region cropper: 0 region(s) (none) → <regions_dir>'
        fires (no partial failure recorded — the fail-soft path)."""
        conv = _FakeConverter(request=_FakeRequest(page_range_start=2, page_range_end=4))
        conv._run_visual_region_cropping(10, toc_entries=None)
        info_msgs = conv.messages("INFO")
        assert any(
            "📐 Visual-region cropper: 0 region(s)" in m and "none" in m for m in info_msgs
        ), f"expected 0-regions INFO log, got: {info_msgs}"
        # No partial failure recorded — the cropper found 0 regions cleanly.
        assert conv._partial_failures == []


# ════════════════════════════════════════════════════════════════════════════
# 11. Source-pin: the exact log-message literals are present in the source
# (Phase-3 source-pin precedent)
# ════════════════════════════════════════════════════════════════════════════


def _skeletons_of(source: str) -> set[str]:
    """Every string literal in source with f-string holes removed (Phase-3
    literal_skeletons() precedent)."""
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.add("".join(v.value for v in node.values if isinstance(v, ast.Constant)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


class TestSourcePinLogLiterals:
    """Pin the exact log-message skeletons present in visual_features.py
    source (Phase-3 source-pin precedent)."""

    def test_no_markers_fallback_debug_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert (
            "  ⚠️ No page markers found — falling back to proportional page mapping "
            "(less accurate on figure-heavy pages)." in skeletons
        )

    def test_page_marker_mapping_info_skeleton(self):
        """The page-marker mapping log is an f-string with multiple constant
        segments — use the skeleton-set (which joins them) and check for
        any skeleton CONTAINING the key substrings."""
        skeletons = _skeletons_of(visual_features_src())
        matching = [
            s
            for s in skeletons
            if "🎯 V18.2.15 Targeted OCR: page-marker mapping " in s
            and " markers, " in s
            and " ranges)" in s
        ]
        assert matching, f"expected the page-marker mapping log skeleton; got: {skeletons}"

    def test_targeted_ocr_pages_count_info_skeleton(self):
        """The pages-count log is a multi-line f-string — check for any
        skeleton CONTAINING the key substrings (the constants are joined
        in the JoinedStr, so the full skeleton has the contiguous text)."""
        skeletons = _skeletons_of(visual_features_src())
        # The full concatenated skeleton contains all the constant
        # segments joined together.
        matching = [
            s
            for s in skeletons
            if "🎯 Targeted OCR: " in s
            and " page(s) to OCR " in s
            and "if contiguous, " in s
            and "else scattered). Original text: " in s
            and " chars, garbled: " in s
        ]
        assert matching, (
            f"expected the pages-count log skeleton with all key substrings; got: {skeletons}"
        )

    def test_targeted_ocr_produced_no_text_warning_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  ⚠️ Targeted OCR produced no text" in skeletons

    def test_replaced_garbled_section_debug_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  🔧 Replaced garbled section (" in skeletons
        assert " chars) with OCR text (" in skeletons

    def test_cover_warning_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  ⚠️ Cover p." in skeletons

    def test_screenshotting_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  📸 Screenshotting " in skeletons
        assert " selected chapter page(s)..." in skeletons

    def test_visual_region_cropper_skipped_debug_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  ⏭️ Visual-region cropper skipped (disabled in settings)" in skeletons

    def test_visual_region_cropper_scanning_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  📐 Visual-region cropper: scanning " in skeletons
        assert " page(s) for diagrams/charts/tables" in skeletons

    def test_visual_region_cropper_zero_regions_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  📐 Visual-region cropper: " in skeletons
        assert " region(s) (" in skeletons

    def test_footnotes_extracted_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  📝 Footnotes: " in skeletons
        assert " extracted" in skeletons

    def test_ocr_re_extraction_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  🔁 OCR re-extraction: rendering " in skeletons
        assert " page(s) as images..." in skeletons

    def test_inline_embed_info_skeleton(self):
        skeletons = _skeletons_of(visual_features_src())
        assert "  📐 Inline-embedded " in skeletons
        assert " region crop(s) into the markdown" in skeletons

    def test_visual_region_cropper_capping_debug_skeleton(self):
        """The 200-page cap on the VLM probe (Layer B cost control)."""
        skeletons = _skeletons_of(visual_features_src())
        assert "  📐 Visual-region cropper: " in skeletons
        assert " pages is a lot — capping to first 200 to control VLM cost" in skeletons
