"""Phase-5 P1 / W8 (first tranche): characterization net for
``core/pipeline/conversion/postprocess.py`` (``run_postprocess``).

WHY THIS FILE EXISTS
--------------------
The Phase-7 SWOT (Task 12-19) flagged the 3 ``conversion/*`` stage runners as
the "extracted ≠ tested" debt (W8 / Phase-5 P1): ``postprocess`` (22% cov),
``visual_features`` (25%), ``output_runner`` (38%).  The Phase-3
characterization net (``test_converter_phase3_characterization.py``, 2,336
lines) pins the converter-impl god-class behaviors; this file extends the
same discipline to the extracted ``run_postprocess`` runner — pinning its
contract, log-message formats, return-value shapes, and the key edge cases /
fail-soft paths so a future refactor can't silently change them.

This is the FIRST TRANCHE — a focused 30-test net pinning the runner's
public surface + the key status-string/return-shape behaviors.  The
exhaustive Phase-3-pattern net (which pins every branch and every
status-string variant) is a follow-up phase.  What is pinned here is what
the live code actually does (probed empirically before writing — no
invented expected values).

APPROACH
--------
The runner takes a ``converter`` first-arg that it reaches into for
``request``, ``temp_markdown_path``, ``output_dir``, ``_poppler_path``,
``_log``, ``_update_status``, ``_targeted_ocr_repair`` (see the module
docstring + the ConversionContext Protocol at
``core/pipeline/conversion_context.py``).  The real ``Converter`` pulls in
the whole pipeline (PDF/OCR/LLM deps), so we DO NOT instantiate it — we
build a minimal fake (``_FakeConverter`` below, the Phase-3
``_RecordingSelf`` precedent at ``test_converter_phase3_characterization.py
:153``) that records ``_log``/``_update_status`` calls and stubs
``_targeted_ocr_repair`` to return canned data.

All fixtures use generic content ("Chapter One", "Some text.", etc.) per
AGENTS.md Rule 1 (content-agnostic — no book-derived names).

Run: ``pytest tests/test_conversion_postprocess_characterization.py -v --no-cov``
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from core.pipeline.conversion.postprocess import run_postprocess

# ════════════════════════════════════════════════════════════════════════════
# Section 0 — hermetic fakes (Phase-3 _RecordingSelf precedent)
# ════════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_POSTPROCESS_SRC_PATH = _PROJECT_ROOT / "core" / "pipeline" / "conversion" / "postprocess.py"


def postprocess_src() -> str:
    """The current postprocess.py source (for source-pin tests)."""
    return _POSTPROCESS_SRC_PATH.read_text(encoding="utf-8")


class _FakeRequest:
    """Stand-in for ConversionRequest (postprocess reads source_type +
    extract_* flags + input_path + page_range_* + primary/fallback_ocr_model
    + table_extraction_method + math_model + password)."""

    def __init__(self, **overrides):
        # The defaults represent a "normal_book" request with ALL advanced
        # features OFF — the no-op path through run_postprocess.
        self.source_type = "normal_book"
        self.input_path = "/nonexistent.pdf"
        self.extract_tables = False
        self.extract_math = False
        self.layout_analysis = False
        self.extract_figure_text = False
        self.primary_ocr_model = "olmocr"
        self.fallback_ocr_model = None
        self.page_range_start = None
        self.page_range_end = None
        self.selected_chapters = None
        self.manual_segments = None
        self.password = None
        self.table_extraction_method = "auto"
        self.math_model = "default"
        for k, v in overrides.items():
            setattr(self, k, v)


class _FakeConverter:
    """Minimal fake converter: records _log/_update_status calls + stubs
    _targeted_ocr_repair to return a canned value (None by default = the
    "did not improve" path; pass a string to simulate the success path)."""

    def __init__(self, request=None, temp_path=None, targeted_ocr_repair_return=None):
        self.request = request or _FakeRequest()
        # A real temp file — postprocess writes the markdown back to it at
        # key checkpoints; we need write_text to succeed for the early
        # temp_path.write_text calls (steps 1b → 8).
        self.temp_markdown_path = temp_path or Path("/tmp/_pp_char_test.md")
        self.output_dir = Path("/tmp/_pp_char_out")
        self._poppler_path = None
        self.logs: list[tuple[str, str]] = []
        self.statuses: list[str] = []
        self._targeted_ocr_return = targeted_ocr_repair_return
        self._targeted_ocr_calls: list[dict] = []
        # postprocess may set _detected_abstract on the converter (academic
        # paper abstract-detection path, step 7).
        self._detected_abstract = None
        # Ensure the parent dir exists so write_text doesn't fail.
        self.temp_markdown_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str, level: str = "INFO") -> None:
        self.logs.append((message, level))

    def _update_status(self, message: str) -> None:
        self.statuses.append(message)

    def _targeted_ocr_repair(self, text, garbled_ranges, total_pages=17, pages_to_ocr=None):
        self._targeted_ocr_calls.append(
            {
                "text_len": len(text),
                "garbled_ranges": list(garbled_ranges),
                "total_pages": total_pages,
                "pages_to_ocr": pages_to_ocr,
            }
        )
        return self._targeted_ocr_return

    def messages(self, level: str | None = None) -> list[str]:
        return [m for m, lvl in self.logs if level is None or lvl == level]


def _make_analysis(total_pages: int = 17) -> SimpleNamespace:
    """Stub PdfAnalysisResult (postprocess only reads .total_pages)."""
    return SimpleNamespace(total_pages=total_pages)


def _garbled_text(n_chars: int = 2500) -> str:
    """Build text that find_garbled_ranges() flags as garbled.

    Single-char-per-line (no spaces) hits all 4 bad metrics in
    ``_is_section_garbled``: avg_word_len=1, short_ratio=1.0,
    line_ratio=1.0, space_ratio=0.0 → 4 signals ≥ 2 → garbled.
    """
    return "\n".join(["a"] * n_chars)


def _partial_garbled_text() -> str:
    """Build text that find_partial_garbled_ranges() flags but
    find_garbled_ranges() does NOT.

    Words: "hello world foo a b" repeated — avg word len = (5+5+3+1+1)/5 =
    3.0 ≥ 2.5 (main detector passes) but < 3.5 (partial detector fires).
    """
    return " ".join(["hello", "world", "foo", "a", "b"] * 200)


# ════════════════════════════════════════════════════════════════════════════
# 1. Signature / contract pins (the runner's public surface)
# ════════════════════════════════════════════════════════════════════════════


class TestPostprocessSignature:
    """Pin the function signature (the contract Converter.convert() relies on)."""

    def test_function_takes_8_params(self):
        """run_postprocess must take exactly 8 params (the documented contract
        from the module docstring + test_conversion_modules.py:467-479)."""
        import inspect

        sig = inspect.signature(run_postprocess)
        params = list(sig.parameters.keys())
        assert params == [
            "converter",
            "raw_markdown",
            "analysis",
            "pages_to_ocr",
            "effective_start_page",
            "effective_end_page",
            "valid_pages",
            "toc_entries",
        ], f"params: {params}"

    def test_function_returns_str(self):
        """run_postprocess must return a str (the post-processed markdown)."""
        result = run_postprocess(
            converter=_FakeConverter(),
            raw_markdown="some text",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert isinstance(result, str)

    def test_function_returns_post_processed_markdown_not_the_raw(self):
        """The returned string is the post-processed markdown (hyphenation
        repair + tab cleanup + paragraph joining may have mutated it)."""
        conv = _FakeConverter()
        raw = "This is net-\nworking text."
        result = run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        # hyphenation repair joined "net-\nworking" → "networking"
        assert "networking" in result
        assert "net-\nworking" not in result


# ════════════════════════════════════════════════════════════════════════════
# 2. The no-op / silent path (plain text, all features off)
# ════════════════════════════════════════════════════════════════════════════


class TestNoOpPath:
    """When all features are OFF and the text is short and clean, the runner
    is silent (no log lines, no status updates) — the no-op path."""

    def test_short_clean_text_emits_no_logs(self):
        """Plain text under 500 chars (so content auto-detection is skipped)
        with no garbling + no advanced features → zero log lines."""
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="Short clean text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert conv.logs == [], f"expected zero logs, got: {conv.logs}"

    def test_short_clean_text_emits_no_status_updates(self):
        """Same input → zero status updates."""
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="Short clean text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert conv.statuses == []

    def test_empty_input_returns_empty_str_silently(self):
        """Empty raw_markdown → empty return, zero logs (the early-exit path
        where every step is a no-op because the text is too short)."""
        conv = _FakeConverter()
        result = run_postprocess(
            converter=conv,
            raw_markdown="",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert result == ""
        assert conv.logs == []

    def test_short_text_writes_to_temp_path(self):
        """postprocess writes the markdown back to temp_markdown_path at the
        end of step 3 (header/footer removal) — verify the write happened."""
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="Some short text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert conv.temp_markdown_path.exists()
        assert conv.temp_markdown_path.read_text(encoding="utf-8") == "Some short text."


# ════════════════════════════════════════════════════════════════════════════
# 3. Step 1 — hyphenation repair (DEBUG log when joins happen)
# ════════════════════════════════════════════════════════════════════════════


class TestHyphenationRepair:
    """Step 1: deterministic hyphenation repair ('net-\\nworking' →
    'networking'). Logs a DEBUG line with the join count when the text
    changes."""

    def test_hyphenation_log_message_format(self):
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="This is net-\nworking text here.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        debug_msgs = conv.messages("DEBUG")
        assert any(m.startswith("  🔧 Hyphenation repair: ") for m in debug_msgs), (
            f"expected hyphenation repair DEBUG log, got: {debug_msgs}"
        )
        # Empirically: "2 line-break joins" (the joined word "networking" +
        # the surrounding line-joins = 2). Pin the count too.
        assert "  🔧 Hyphenation repair: 2 line-break joins" in debug_msgs

    def test_hyphenation_actually_joins(self):
        conv = _FakeConverter()
        result = run_postprocess(
            converter=conv,
            raw_markdown="net-\nworking",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert result == "networking"

    def test_no_hyphenation_log_when_no_change(self):
        """If the text has no hyphenation, the DEBUG log line is NOT emitted
        (the `if len(raw_markdown) != pre_len:` guard)."""
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="No hyphenation here.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert not any("Hyphenation repair:" in m for m in conv.messages("DEBUG"))


# ════════════════════════════════════════════════════════════════════════════
# 4. Step 1b — tab cleanup (DEBUG log when tabs are replaced)
# ════════════════════════════════════════════════════════════════════════════


class TestTabCleanup:
    """Step 1b: replace tabs with spaces + collapse runs of spaces (V13.33.2
    PDF-layout-artifact fix). DEBUG log with the tab count."""

    def test_tab_cleanup_log_message_format(self):
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="This\tview\tis\ta\tcomprehensive\tlist",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        debug_msgs = conv.messages("DEBUG")
        assert "  🧹 Tab cleanup: replaced 5 tab character(s) with spaces" in debug_msgs

    def test_tab_cleanup_replaces_tabs_with_single_spaces(self):
        conv = _FakeConverter()
        result = run_postprocess(
            converter=conv,
            raw_markdown="a\tb\tc",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert result == "a b c"

    def test_no_tab_cleanup_log_when_no_tabs(self):
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="No tabs here.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert not any("Tab cleanup:" in m for m in conv.messages("DEBUG"))


# ════════════════════════════════════════════════════════════════════════════
# 5. Step 3 — header/footer removal (DEBUG log when chars stripped)
# ════════════════════════════════════════════════════════════════════════════


class TestHeaderFooterRemoval:
    """Step 3: detect + strip repeating lines across pages. DEBUG log when
    chars are stripped (the `if len(raw_markdown) != pre_len:` guard)."""

    def test_header_footer_log_message_format(self):
        """Build text with a repeating header on 3 pages → the header gets
        stripped + a DEBUG log fires with the char count."""
        conv = _FakeConverter()
        header = "Running Header Line\n"
        body = "Body text content here that is long enough.\n"
        one_page = header + body + body + body + body
        raw = (
            "<!-- Page 1 -->\n"
            + one_page
            + "<!-- Page 2 -->\n"
            + one_page
            + "<!-- Page 3 -->\n"
            + one_page
        )
        run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=3,
        )
        debug_msgs = conv.messages("DEBUG")
        # Empirically: 981 chars stripped (header × 3 pages × 1 line each).
        assert any(
            m.startswith("  🧹 Header/footer removal: ") and "chars stripped" in m
            for m in debug_msgs
        ), f"expected header/footer DEBUG log, got: {debug_msgs}"

    def test_header_footer_actually_strips_repeating_header(self):
        conv = _FakeConverter()
        header = "Running Header Line\n"
        body = "Body text content here that is long enough.\n"
        one_page = header + body + body + body + body
        raw = (
            "<!-- Page 1 -->\n"
            + one_page
            + "<!-- Page 2 -->\n"
            + one_page
            + "<!-- Page 3 -->\n"
            + one_page
        )
        result = run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=3,
        )
        # The repeating header should be gone.
        assert "Running Header Line" not in result


# ════════════════════════════════════════════════════════════════════════════
# 6. Step 5 — targeted OCR repair (garbled text + academic-paper partial garbling)
# ════════════════════════════════════════════════════════════════════════════


class TestTargetedOcrRepairGarbled:
    """Step 5: when find_garbled_ranges() returns non-empty, log a WARNING +
    call converter._targeted_ocr_repair with the ranges + total_pages +
    pages_to_ocr. Two outcomes: improvement (SUCCESS log + replace) vs
    no-improvement (WARNING log + keep pre-OCR text)."""

    def test_garbled_warning_log_message_format(self):
        conv = _FakeConverter(targeted_ocr_repair_return=None)
        run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        warn_msgs = conv.messages("WARNING")
        # Empirically: "4,999 chars in 1 section(s)" (2500 single chars joined
        # by \n = 4999 chars total; one merged range 0..4999).
        assert any(
            m.startswith("  🔴 Garbled text detected: ")
            and "chars in" in m
            and "section(s). Running targeted OCR..." in m
            for m in warn_msgs
        ), f"expected garbled WARNING, got: {warn_msgs}"

    def test_targeted_ocr_repair_called_with_correct_args(self):
        """The fake converter records the call args; pin them."""
        conv = _FakeConverter(targeted_ocr_repair_return=None)
        run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(total_pages=17),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert len(conv._targeted_ocr_calls) == 1
        call = conv._targeted_ocr_calls[0]
        assert call["total_pages"] == 17
        assert call["pages_to_ocr"] == []
        # The garbled_ranges is a list of (start, end) tuples — pin that
        # there's exactly one range covering the whole text.
        assert len(call["garbled_ranges"]) == 1
        start, end = call["garbled_ranges"][0]
        assert start == 0
        assert end > 2000  # the merged range covers most of the 4999-char text

    def test_no_improvement_warning_when_ocr_returns_none(self):
        """When _targeted_ocr_repair returns None (falsy), the
        'did not improve' WARNING fires + the text is NOT replaced."""
        conv = _FakeConverter(targeted_ocr_repair_return=None)
        raw = _garbled_text(2500)
        result = run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        warn_msgs = conv.messages("WARNING")
        assert (
            "  ⚠️ Targeted OCR did not improve the text — continuing with original extraction."
            in warn_msgs
        )
        # The result is NOT the raw input (smart_paragraph_joining ran in
        # step 2, joining "a\na\na" → "a a\na a"); but it's also NOT the
        # None return from _targeted_ocr_repair.
        assert result is not None
        assert "a a" in result  # post-step-2 form

    def test_no_improvement_warning_when_ocr_returns_same_text(self):
        """When _targeted_ocr_repair returns a string equal to the input,
        the 'did not improve' WARNING fires (the `_fixed_text != raw_markdown`
        guard)."""

        # Use a fake that returns the SAME text it received.
        class _SameTextConverter(_FakeConverter):
            def _targeted_ocr_repair(self, text, garbled_ranges, total_pages=17, pages_to_ocr=None):
                self._targeted_ocr_calls.append({"text_len": len(text)})
                return text  # unchanged

        conv = _SameTextConverter()
        run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        warn_msgs = conv.messages("WARNING")
        assert (
            "  ⚠️ Targeted OCR did not improve the text — continuing with original extraction."
            in warn_msgs
        )

    def test_success_log_when_ocr_returns_fixed_text(self):
        """When _targeted_ocr_repair returns a different non-empty string,
        the SUCCESS log fires + the result IS the fixed text."""
        conv = _FakeConverter(targeted_ocr_repair_return="This is now clean text.")
        result = run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert result == "This is now clean text."
        # SUCCESS log with the clean-text char count + the parenthetical.
        success_msgs = conv.messages("SUCCESS")
        assert any(
            m.startswith("  ✅ Targeted OCR repair complete: ")
            and "chars of clean text (garbled sections replaced with OCR output)." in m
            for m in success_msgs
        ), f"expected SUCCESS log, got: {success_msgs}"

    def test_success_log_uses_clean_text_char_count(self):
        """The SUCCESS log uses len(raw_markdown) AFTER the replacement —
        i.e., the clean-text char count, not the original garbled count."""
        conv = _FakeConverter(targeted_ocr_repair_return="This is now clean text.")
        # 23 chars in the clean replacement.
        run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        success_msgs = conv.messages("SUCCESS")
        assert (
            "  ✅ Targeted OCR repair complete: 23 chars of clean text (garbled sections replaced with OCR output)."
            in success_msgs
        )


class TestTargetedOcrRepairPartialGarbling:
    """Step 5b: academic papers ALSO check find_partial_garbled_ranges()
    when find_garbled_ranges() is empty. This is the academic-paper-only
    partial-garbling path."""

    def test_partial_garbling_warning_log_format(self):
        """academic_paper source_type + partial-garbled text → the partial
        WARNING fires (different message from the main garbling path)."""
        conv = _FakeConverter(
            request=_FakeRequest(source_type="academic_paper"),
            targeted_ocr_repair_return=None,
        )
        run_postprocess(
            converter=conv,
            raw_markdown=_partial_garbled_text(),
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        warn_msgs = conv.messages("WARNING")
        # Empirically: "3,999 chars in 1 section(s)" — the partial detector
        # uses 1000-char windows with 300 overlap (step=700); 200 reps of
        # "hello world foo a b " = 1800 chars; but find_partial_garbled_ranges
        # extends to 3999 in one merged range.
        assert any(
            "Partial garbling detected in academic paper:" in m and "Running targeted OCR..." in m
            for m in warn_msgs
        ), f"expected partial-garbling WARNING, got: {warn_msgs}"

    def test_partial_garbling_success_log_omits_parenthetical(self):
        """The partial-garbling SUCCESS log says 'of clean text.' (no
        parenthetical — different from the main garbling path which says
        'of clean text (garbled sections replaced with OCR output).')."""
        conv = _FakeConverter(
            request=_FakeRequest(source_type="academic_paper"),
            targeted_ocr_repair_return="Clean academic text body.",
        )
        run_postprocess(
            converter=conv,
            raw_markdown=_partial_garbled_text(),
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        success_msgs = conv.messages("SUCCESS")
        # 25 chars in "Clean academic text body."
        assert any(
            m.startswith("  ✅ Targeted OCR repair complete: ")
            and "chars of clean text." in m
            and "garbled sections replaced" not in m
            for m in success_msgs
        ), f"expected partial-garbling SUCCESS log (no parenthetical), got: {success_msgs}"

    def test_partial_garbling_path_only_runs_for_academic_paper(self):
        """normal_book source_type + partial-garbled text → the partial
        WARNING does NOT fire (the path is academic-paper-only)."""
        conv = _FakeConverter(
            request=_FakeRequest(source_type="normal_book"),
            targeted_ocr_repair_return=None,
        )
        run_postprocess(
            converter=conv,
            raw_markdown=_partial_garbled_text(),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert not any("Partial garbling" in m for m in conv.messages("WARNING"))


# ════════════════════════════════════════════════════════════════════════════
# 7. Step 6 — content-type auto-detection (normal_book > 500 chars)
# ════════════════════════════════════════════════════════════════════════════


class TestContentAutoDetection:
    """Step 6: when source_type='normal_book' AND len(raw_markdown) > 500,
    run detect_content_type() and log the result. Two branches: (a) detection
    fires + switches preset (INFO log) OR (b) detection too low confidence /
    not recommended (DEBUG log keeping normal_book)."""

    def test_content_detection_info_log_message_format(self):
        """A long body of plain English words → detect_content_type returns
        'Non-Fiction Book' (== normal_book preset) at 100% confidence +
        recommended=True. Since recommended AND content_type == normal_book,
        NEITHER the auto-switch nor the 'too low' branch fires — only the
        'Content auto-detection:' INFO log fires (the implicit third branch).
        Pin all three observations via the live path."""
        conv = _FakeConverter()
        raw = "word " * 200  # 1000 chars
        run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        info_msgs = conv.messages("INFO")
        debug_msgs = conv.messages("DEBUG")
        # The "Content auto-detection:" INFO log always fires when the path
        # is entered (regardless of recommended/switch).
        assert any(m.startswith("  🔍 Content auto-detection: ") for m in info_msgs), (
            f"expected content auto-detection INFO log, got: {info_msgs}"
        )
        # Probe-verified: detect_content_type on plain words returns
        # content_type='normal_book' confidence=1.0 recommended=True → the
        # elif `not recommended` branch is NOT taken; no "too low" log fires.
        assert not any("Detection confidence too low" in m for m in debug_msgs), (
            f"expected NO 'too low' DEBUG log on plain-words input, got: {debug_msgs}"
        )
        # And the auto-switch INFO log doesn't fire either (content_type ==
        # normal_book, so the auto-switch `if` branch is skipped).
        assert not any("Auto-switching to" in m for m in info_msgs), (
            f"expected NO auto-switch INFO log on plain-words input, got: {info_msgs}"
        )

    def test_content_detection_too_low_debug_path(self):
        """When detect_content_type returns recommended=False (e.g., a
        garbled-text input the detector classifies as 'magazine' at low
        confidence), the 'too low' DEBUG log fires."""
        conv = _FakeConverter()
        # _garbled_text(2500) → detector returns magazine@50% recommended=False
        # (probed live). The text is > 500 chars so the path is entered.
        run_postprocess(
            converter=conv,
            raw_markdown=_garbled_text(2500),
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        debug_msgs = conv.messages("DEBUG")
        assert any(
            "Detection confidence too low" in m and "keeping normal_book preset" in m
            for m in debug_msgs
        ), f"expected 'too low' DEBUG log on garbled input, got: {debug_msgs}"

    def test_content_detection_skipped_when_text_under_500_chars(self):
        """The `len(raw_markdown) > 500` guard: short text skips the
        detector entirely (no 'Content auto-detection' INFO log)."""
        conv = _FakeConverter()
        run_postprocess(
            converter=conv,
            raw_markdown="Short text under 500 chars.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        assert not any("Content auto-detection:" in m for m in conv.messages("INFO"))

    def test_content_detection_skipped_when_source_type_not_normal_book(self):
        """academic_paper (or any non-normal_book preset) skips the
        auto-detection (the `if request.source_type == "normal_book"` guard)."""
        conv = _FakeConverter(request=_FakeRequest(source_type="academic_paper"))
        # academic_paper triggers the layout-reorder path instead.
        run_postprocess(
            converter=conv,
            raw_markdown="word " * 200,
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        assert not any("Content auto-detection:" in m for m in conv.messages("INFO"))


# ════════════════════════════════════════════════════════════════════════════
# 8. Step 7 — academic_paper layout-reorder block (the V18.15.3.2 guardrail)
# ════════════════════════════════════════════════════════════════════════════


class TestAcademicPaperLayoutReorder:
    """Step 7: when source_type='academic_paper', the V18.15.3.2 HARD
    GUARDRAIL samples 2 pages to check multi-column. If single-column (the
    common case), the entire layout-reorder block is skipped with an INFO
    log explaining why (avoids the false-activation on domain textbooks
    with citations)."""

    def test_layout_reorder_not_activated_info_log(self):
        """academic_paper + non-existent PDF → the guard's
        _detect_multi_column call fails (so _is_multi_column stays False) →
        the 'NOT activated' INFO log fires."""
        conv = _FakeConverter(request=_FakeRequest(source_type="academic_paper"))
        run_postprocess(
            converter=conv,
            raw_markdown="Just a sentence.",
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        # The exact log text (V18.15.3.2 string).
        assert any(
            "V18.15.3.2: Layout reorder NOT activated — content classified as 'academic_paper'" in m
            and "single-column layout" in m
            for m in info_msgs
        ), f"expected 'NOT activated' INFO log, got: {info_msgs}"

    def test_academic_paper_figure_caption_extraction(self):
        """academic_paper + text with 'Figure N: caption' lines → step 7
        extracts captions + appends a '## Figure Captions' block at the end."""
        conv = _FakeConverter(request=_FakeRequest(source_type="academic_paper"))
        raw = (
            "Abstract\nThe abstract body.\nKeywords: alpha\n\n"
            "1. Introduction\nIntro text.\n\n"
            "Figure 1: This is the first figure caption.\n\n"
            "Figure 2: Second caption goes here.\n\n"
        )
        result = run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        # The appended block.
        assert "## Figure Captions" in result
        assert "1. This is the first figure caption." in result
        assert "2. Second caption goes here." in result
        # DEBUG log with the count.
        debug_msgs = conv.messages("DEBUG")
        assert any("Extracted 2 figure caption(s) into markdown" in m for m in debug_msgs), (
            f"expected figure-captions DEBUG log, got: {debug_msgs}"
        )

    def test_academic_paper_abstract_detection_sets_converter_attr(self):
        """academic_paper + text matching the Abstract regex → step 7 sets
        converter._detected_abstract + logs an INFO line."""
        conv = _FakeConverter(request=_FakeRequest(source_type="academic_paper"))
        raw = "Abstract\nThis is the abstract body content that is long enough.\nKeywords: alpha, beta\n"
        run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        # The detected abstract is stored on the converter.
        assert conv._detected_abstract is not None
        assert "abstract body content" in conv._detected_abstract
        # INFO log with the char count.
        info_msgs = conv.messages("INFO")
        assert any(
            "Abstract detected" in m and "will guide executive summary generation" in m
            for m in info_msgs
        ), f"expected abstract-detected INFO log, got: {info_msgs}"

    def test_academic_paper_abstract_detection_supports_uppercase(self):
        """The Abstract regex matches both 'Abstract' and 'ABSTRACT'."""
        conv = _FakeConverter(request=_FakeRequest(source_type="academic_paper"))
        raw = "ABSTRACT\nUpper case abstract body content.\n1. Introduction starts here.\n"
        run_postprocess(
            converter=conv,
            raw_markdown=raw,
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        assert conv._detected_abstract is not None
        assert "Upper case abstract" in conv._detected_abstract


# ════════════════════════════════════════════════════════════════════════════
# 9. Step 8 — advanced document handling (tables / math / layout)
# ════════════════════════════════════════════════════════════════════════════


class TestAdvancedDocumentHandling:
    """Step 8: when any of extract_tables / extract_math / layout_analysis
    is True, run the matching extractor. Each branch has its own INFO log +
    fail-soft path. The block ends with a single '📝 Enhanced markdown
    saved (with advanced features).' INFO log + 'Applying advanced document
    features…' status update."""

    def test_extract_tables_triggers_advanced_handling(self):
        conv = _FakeConverter(request=_FakeRequest(extract_tables=True))
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        # Opening + per-feature logs.
        assert "  🧩 Running advanced document handling…" in info_msgs
        assert "  📊 Extracting tables…" in info_msgs
        # Closing log (always fires at end of step 8).
        assert "📝 Enhanced markdown saved (with advanced features)." in info_msgs
        # Status update.
        assert "Applying advanced document features…" in conv.statuses

    def test_extract_math_triggers_advanced_handling(self):
        conv = _FakeConverter(request=_FakeRequest(extract_math=True))
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        assert "  🧩 Running advanced document handling…" in info_msgs
        assert "  📐 Extracting math formulae…" in info_msgs

    def test_layout_analysis_triggers_advanced_handling(self):
        conv = _FakeConverter(request=_FakeRequest(layout_analysis=True))
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        assert "  🧩 Running advanced document handling…" in info_msgs
        assert "  📐 Analyzing layout…" in info_msgs

    def test_advanced_handling_skipped_when_all_features_off(self):
        """The `if request.extract_tables or extract_math or layout_analysis:`
        guard — when all three are False, step 8 is skipped entirely."""
        conv = _FakeConverter()  # all features OFF by default
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        assert not any("advanced document handling" in m for m in info_msgs)
        assert not any("Enhanced markdown saved" in m for m in info_msgs)


# ════════════════════════════════════════════════════════════════════════════
# 10. Step 9 — vision OCR for figures
# ════════════════════════════════════════════════════════════════════════════


class TestVisionOcrForFigures:
    """Step 9: when request.extract_figure_text is True, build a
    VisionFigureExtractor + log '🖼️ Extracting text from figures using
    vision model…' INFO. The fake request's input_path doesn't exist → the
    extractor logs a failure + 'ℹ️ No figures found or no text extracted.'
    INFO (the fail-soft path)."""

    def test_vision_ocr_info_log_message_format(self):
        conv = _FakeConverter(request=_FakeRequest(extract_figure_text=True))
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=17,
        )
        info_msgs = conv.messages("INFO")
        assert "  🖼️ Extracting text from figures using vision model…" in info_msgs
        # The fail-soft tail log (no figures extracted).
        assert "  ℹ️ No figures found or no text extracted." in info_msgs
        # Status update.
        assert "Extracting text from figures…" in conv.statuses

    def test_vision_ocr_skipped_when_extract_figure_text_false(self):
        """The `if request.extract_figure_text:` guard — when False, step 9
        is skipped entirely (no vision-OCR logs even on academic_paper)."""
        conv = _FakeConverter(
            request=_FakeRequest(source_type="academic_paper", extract_figure_text=False)
        )
        run_postprocess(
            converter=conv,
            raw_markdown="Some text.",
            analysis=_make_analysis(total_pages=5),
            pages_to_ocr=[],
            effective_start_page=1,
            effective_end_page=5,
        )
        info_msgs = conv.messages("INFO")
        assert not any("Extracting text from figures" in m for m in info_msgs)


# ════════════════════════════════════════════════════════════════════════════
# 11. Source-pin: the exact log-message literals are present in the source
# (the Phase-3 source-pin precedent — pin the literal skeletons so a future
# refactor that changes the wording breaks the test)
# ════════════════════════════════════════════════════════════════════════════


def _skeletons_of(source: str) -> set[str]:
    """Every string literal in source with f-string holes removed (Phase-3
    literal_skeletons() precedent at test_converter_phase3_characterization.py
    :113-150)."""
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.add("".join(v.value for v in node.values if isinstance(v, ast.Constant)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


class TestSourcePinLogLiterals:
    """Pin the exact log-message skeletons present in postprocess.py source.
    A future refactor that changes the wording, level, or emoji breaks the
    test (the Phase-3 source-pin precedent)."""

    def test_hyphenation_repair_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🔧 Hyphenation repair: " in skeletons
        assert " line-break joins" in skeletons

    def test_tab_cleanup_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🧹 Tab cleanup: replaced " in skeletons
        assert " tab character(s) with spaces" in skeletons

    def test_header_footer_removal_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🧹 Header/footer removal: " in skeletons
        assert " chars stripped" in skeletons

    def test_garbled_warning_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🔴 Garbled text detected: " in skeletons
        assert " chars in " in skeletons
        assert " section(s). Running targeted OCR..." in skeletons

    def test_targeted_ocr_no_improvement_warning_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert (
            "  ⚠️ Targeted OCR did not improve the text — continuing with original extraction."
            in skeletons
        )

    def test_targeted_ocr_success_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  ✅ Targeted OCR repair complete: " in skeletons
        assert " chars of clean text (garbled sections replaced with OCR output)." in skeletons

    def test_partial_garbling_warning_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🔴 Partial garbling detected in academic paper: " in skeletons

    def test_partial_garbling_success_log_skeleton(self):
        """The partial-garbling SUCCESS log omits the parenthetical (different
        from the main path)."""
        skeletons = _skeletons_of(postprocess_src())
        assert " chars of clean text." in skeletons

    def test_layout_reorder_not_activated_skeleton(self):
        """The 'NOT activated' log message is a 3-line implicit-concatenation
        string literal (so the AST Constant has the FULL concatenated value,
        not the partial). Use a substring check on the source instead."""
        src = postprocess_src()
        assert "V18.15.3.2: Layout reorder NOT activated — content classified as " in src
        assert "'academic_paper' but sampling confirms single-column layout" in src
        assert "(reorder unnecessary, skipped entire block)." in src

    def test_advanced_document_handling_skeletons(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🧩 Running advanced document handling…" in skeletons
        assert "  📊 Extracting tables…" in skeletons
        assert "  📐 Extracting math formulae…" in skeletons
        assert "  📐 Analyzing layout…" in skeletons
        assert "📝 Enhanced markdown saved (with advanced features)." in skeletons

    def test_vision_ocr_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  🖼️ Extracting text from figures using vision model…" in skeletons
        assert "  ℹ️ No figures found or no text extracted." in skeletons

    def test_abstract_detection_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  📄 Abstract detected (" in skeletons
        assert " chars) — will guide executive summary generation" in skeletons

    def test_figure_captions_log_skeleton(self):
        skeletons = _skeletons_of(postprocess_src())
        assert "  📊 Extracted " in skeletons
        assert " figure caption(s) into markdown" in skeletons

    def test_academic_switch_confidence_threshold_constant(self):
        """The 0.85 academic-switch confidence threshold is a hardcoded
        constant in the source (the Phase-3 source-pin pattern)."""
        src = postprocess_src()
        assert "_acad_min_conf = 0.85" in src
