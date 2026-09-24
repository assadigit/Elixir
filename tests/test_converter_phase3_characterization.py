"""Phase 3 / Commit 0: characterization net for core/pipeline/converter_impl.py.

Locked BEFORE the planned VERBATIM extractions (Task 3-plan, commits 1-3:
conversion/reporting.py, conversion/summary_outputs.py,
conversion/finalization.py).  Whatever the current code does — including the
weird formatting — IS the spec; these tests exist so the extractions can be
verified behavior-identical.

What is pinned here (all hermetic: no ~/.elixir, no network, no Qt, no real
conversion — fake ``self`` objects per the test_v18202_system_fixes.py:974
precedent ``Converter._generate_quality_report(fake, ...)``):

  1. ``_match_chapter`` — the full matching ladder: normalized exact match,
     chapter-number matching (equality / parent-prefix / the V13.33.5
     substring guard), significant-word overlap (1-2 word ALL rule, 3+ word
     majority rule), and the rapidfuzz token_set_ratio >= 95 last resort.
  2. Terminal status strings from convert()'s completion assessment —
     all-chapters-failed ERROR, zero-summaries-with-selection hard fail,
     zero-summaries warning, cancelled-by-user, partial-failure line.  These
     paths only run inside the 1,054-line convert() body (extraction →
     segmentation → summarization state), so they are pinned as SOURCE PINS
     on the exact literals (house precedent: test_v002_false_success.py,
     test_v1820411_p2_tls_logs_literals.py) plus standalone evaluations of
     the guard expressions (the test_v002 ``test_semantics_matrix`` pattern).
  3. Diagnostic-summary line formats — header, Pages-processed variant,
     Segments/Success lines, Coverage (NN% and ``?``), recall-floor line,
     provenance-stamp lines.  Format literals are source-pinned; the
     callable computation pieces (stamp_diagnostic, _get_app_version, the
     ``:.0%``-or-``?`` coverage renderer) are unit-tested directly.
  4. ``_generate_quality_report`` — the exact quality_report.json shape
     (top-level keys, totals keys incl. the V18.20.3.5 recall_floor
     aggregate, per-chapter keys) + the hallucination quirk (success +
     0 bullets + <100 input tokens → flipped to failed).
  5. ``_cross_chapter_dedup`` — cross-chapter duplicate removal, the
     write-back indexing that skips bullet-less summaries, and its INFO log.
  6. ``_enforce_vram_budget`` — every ``local.vram_overbudget_policy``
     branch: proceed / ask+acknowledged / ask-unacknowledged / abort /
     unknown / empty, plus the fits / no-GPU / fail-open returns.
  7. Screenshots page-filter precedence — range → manual_segments →
     selected_chapters (the elif that makes manual segments win), plus
     ``_derive_page_ranges_from_toc`` (the helper behind filter 3).
  8. Simplified-keypoints skip/warning message strings + the
     infrastructure-keyword triage tuple.

All test data uses generic vocabulary (AGENTS.md Rule 1: content-agnostic —
no book, chapter, author, or theorist names).

Run: ``pytest tests/test_converter_phase3_characterization.py -v --no-cov``
"""

from __future__ import annotations

import ast
import json
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.models import ConversionRequest, Segment, SummaryResult
from core.pipeline import converter_impl as conv_impl
from core.pipeline.converter_impl import Converter

# ════════════════════════════════════════════════════════════════════════════
# Section 0 — helpers (hermetic fakes + source readers)
# ════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONV_SRC_PATH = PROJECT_ROOT / "core" / "pipeline" / "converter_impl.py"
# V0.4.26 (Phase 3 commit 1): the quality-report method + the end-of-run
# diagnostic block moved VERBATIM here from converter_impl.py.
_REPORTING_SRC_PATH = PROJECT_ROOT / "core" / "pipeline" / "conversion" / "reporting.py"


def conv_src() -> str:
    """The current converter_impl.py source (for the source-pin tests)."""
    return _CONV_SRC_PATH.read_text(encoding="utf-8")


def reporting_src() -> str:
    """The conversion/reporting.py source (the Phase-3 home of the moved
    quality-report method + diagnostic block — the pins follow the moved
    bodies)."""
    return _REPORTING_SRC_PATH.read_text(encoding="utf-8")


def _skeletons_of(source: str) -> set[str]:
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.add("".join(v.value for v in node.values if isinstance(v, ast.Constant)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def literal_skeletons() -> set[str]:
    """Every string literal in converter_impl.py + conversion/reporting.py
    with f-string holes removed.

    Adjacent implicit concatenation (``f"a {x} "`` ``f"b"`` on separate
    lines) parses to a single JoinedStr, so this reassembles physically
    wrapped messages into one contiguous skeleton — the pin then survives
    any future line re-wrapping while still pinning the exact text.

    V0.4.26 (Phase 3 commit 1): the diagnostic-block + quality-report
    literals moved to conversion/reporting.py — the skeleton set is the
    UNION over both modules (house precedent: the union semantics of
    test_v18202_system_fixes.py::test_phase_gates_wired_in_converter_impl).
    """
    return _skeletons_of(conv_src()) | _skeletons_of(reporting_src())


class _RecordingSelf:
    """Minimal fake converter: captures ``_log(msg, level)`` calls."""

    def __init__(self, **attrs):
        self.logs: list[tuple[str, str]] = []
        for k, v in attrs.items():
            setattr(self, k, v)

    def _log(self, message: str, level: str = "INFO"):
        self.logs.append((message, level))

    def messages(self, level: str | None = None) -> list[str]:
        return [m for m, lvl in self.logs if level is None or lvl == level]


class _FakeSettings:
    """Stand-in for utils.settings.Settings (hermetic .get)."""

    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


def _match(heading: str, selected: str) -> bool:
    """Call Converter._match_chapter without building a Converter.

    The method body never touches ``self`` (verified by reading the source),
    so any stand-in first argument works.
    """
    return Converter._match_chapter(_RecordingSelf(), heading, selected)


def _make_summary(heading: str, bullets=None, *, success=True, input_tokens=900) -> SummaryResult:
    return SummaryResult(
        chapter_heading=heading,
        executive_summary="exec text" if success else "",
        thorough_summary="thorough text" if success else "",
        bullet_points=list(bullets or []),
        success=success,
        model_used="test-model",
        input_tokens=input_tokens,
        output_tokens=50,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. _match_chapter — normalized exact match (ladder rung 1)
# ════════════════════════════════════════════════════════════════════════════


class TestMatchChapterExactNormalized:
    def test_exact_match(self):
        assert _match("Results and Analysis", "Results and Analysis") is True

    def test_case_insensitive(self):
        assert _match("RESULTS AND ANALYSIS", "results and analysis") is True

    def test_surrounding_whitespace_stripped(self):
        assert _match("  Results and Analysis  ", "Results and Analysis") is True

    def test_punctuation_stripped_in_normalization(self):
        # normalize() removes [^\w\s]: "Results, Analysis!" == "Results Analysis"
        assert _match("Results, Analysis!", "Results Analysis") is True

    def test_unicode_ellipsis_stripped(self):
        # TOC titles are frequently truncated with "…" — normalize() drops it.
        assert _match("Results and Analysis…", "Results and Analysis") is True

    def test_ascii_ellipsis_stripped(self):
        assert _match("Results and Analysis ...", "Results and Analysis") is True


# ════════════════════════════════════════════════════════════════════════════
# 1b. _match_chapter — chapter-number matching (ladder rung 2)
# ════════════════════════════════════════════════════════════════════════════


class TestMatchChapterNumbers:
    def test_same_number_matches_even_with_disjoint_words(self):
        # "Both have numbers — match ONLY on the number"
        assert _match("3.6 Some Topic Name", "3.6 Completely Different Words") is True

    def test_different_numbers_never_match(self):
        assert _match("2.2 Topic A", "3.6 Topic B") is False

    def test_parent_prefix_selected_matches_child_heading(self):
        # "2" matches "2.1": heading number starts with selected + "."
        assert _match("2.1 Methods Overview", "2 Methods") is True

    def test_substring_guard_one_does_not_match_ten(self):
        # V13.33.5: "1" must NOT match "10" (substring bug fix)
        assert _match("10 Introductory Material", "1") is False

    def test_sibling_number_not_matched_via_prefix(self):
        # "2.1" does not match "2.10" (prefix must be followed by ".")
        assert _match("2.10 Something", "2.1") is False

    def test_nested_child_matched_via_parent(self):
        assert _match("2.2.1 Deep Subsection", "2.2 Subsection Group") is True


# ════════════════════════════════════════════════════════════════════════════
# 1c. _match_chapter — significant-word overlap (ladder rung 3)
# ════════════════════════════════════════════════════════════════════════════


class TestMatchChapterWordOverlap:
    def test_one_word_selection_matches(self):
        # "introduction"/"to" are common words; the single significant word
        # "methods" appears in the heading → 1-word rule matches.
        assert _match("Introduction to Methods", "Methods") is True

    def test_two_word_selection_requires_all(self):
        # "Results and Discussion" vs heading with only "Results" → no match.
        assert _match("Results and Analysis", "Results and Discussion") is False

    def test_two_word_selection_all_present_matches(self):
        # & normalizes away; "results" + "analysis" both in heading → match.
        assert _match("Results & Analysis", "Results and Analysis") is True

    def test_majority_rule_three_of_four_words_matches(self):
        # 4 significant selected words, threshold = max(3, 4//2) = 3;
        # heading "Growth and Patterns of Signals" shares 3 → match.
        assert _match("Growth and Patterns of Signals", "Growth Patterns Signals Today") is True

    def test_majority_rule_two_of_four_words_rejected(self):
        # Same selection vs a heading sharing only 2 → falls through to
        # fuzzy (token_set_ratio 85.7 < 95) → no match.
        assert _match("Growth Patterns Only", "Growth Patterns Signals Today") is False

    def test_all_common_words_collapses_to_no_word_match(self):
        # "Introduction" and "Conclusion" are both in _COMMON → both word
        # sets empty → word-overlap rung skipped entirely; fuzzy (low) → no.
        assert _match("Introduction", "Conclusion") is False

    def test_disjoint_generic_titles_do_not_match(self):
        assert _match("Introduction to Methods", "Results and Analysis") is False


# ════════════════════════════════════════════════════════════════════════════
# 1d. _match_chapter — rapidfuzz last resort (ladder rung 4)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.skipif(
    not conv_impl.RAPIDFUZZ_AVAILABLE, reason="fuzzy last-resort rung needs rapidfuzz"
)
class TestMatchChapterFuzzyLastResort:
    def test_single_typo_above_95_matches(self):
        # token_set_ratio("characteristic paterns", "characteristic patterns")
        # = 97.78 ≥ 95 → match (word-overlap rung failed: only 1 of 2 words).
        assert _match("Characteristic Paterns", "Characteristic Patterns") is True

    def test_different_words_below_95_rejected(self):
        # token_set_ratio = 85.0 < 95 → no match.
        assert _match("Character Pattern", "Characteristic Patterns") is False

    def test_token_subset_scores_100(self):
        # token_set_ratio quirk: a selected title whose tokens are a SUBSET
        # of the heading's tokens scores 100 (t0 == t2) → the bare "1"
        # (no trailing space → number extraction fails; its only word is
        # ≤2 chars → empty word set) still matches "1 Introduction".
        from rapidfuzz import fuzz

        assert fuzz.token_set_ratio("1 introduction", "1") == 100
        assert _match("1 Introduction", "1") is True


# ════════════════════════════════════════════════════════════════════════════
# 2. Terminal status strings (convert() completion assessment — source pins)
# ════════════════════════════════════════════════════════════════════════════


class TestTerminalStatusStrings:
    """The four completion branches only execute inside convert()'s 1,054-line
    body (needs extraction/segmentation/summarization state) — per the house
    source-pin precedent (test_v002_false_success.py:385-426,
    test_v1820411_p2_tls_logs_literals.py:566-580) the exact emitted strings
    are pinned on the source literals."""

    def test_all_chapters_failed_error_lines(self):
        src = conv_src()
        assert 'self._update_status("Conversion FAILED — all chapters returned empty")' in src
        assert (
            'self._log("❌ Conversion FAILED: all chapters returned empty responses.", "ERROR")'
            in src
        )

    def test_all_chapters_failed_hint_mentions_ollama_pull(self):
        skeletons = literal_skeletons()
        assert (
            "    chapter(s) failed — model produced no content. Likely causes: model not "
            "installed, VRAM insufficient, or quantization too aggressive for the prompt "
            "complexity. Try: ollama pull <model>, or switch to a less aggressive quant "
            "(IQ2_M instead of IQ2_XXS), or raise temperature to 1.0." in skeletons
        )
        # ...and it is logged at ERROR:
        src = conv_src()
        anchor = src.find("❌ Conversion FAILED: all chapters returned empty responses.")
        assert anchor > 0
        assert '"ERROR"' in src[anchor : anchor + 900]

    def test_zero_summaries_with_selection_hard_fail_lines(self):
        src = conv_src()
        assert 'self._update_status("Conversion FAILED — no selected chapters summarized")' in src
        skeletons = literal_skeletons()
        assert (
            "❌ Conversion FAILED: none of the  selected chapter(s) produced a summary — "
            "the selection matched no summarizable section (every surviving segment was "
            "skipped as front/reference matter). No summary outputs were written." in skeletons
        )
        assert (
            "   Try: re-open the chapter selector and re-pick chapters (per-chapter "
            "author/annotation bookmarks are no longer listed), or convert the whole book."
            in skeletons
        )

    def test_zero_summaries_warning_path_lines(self):
        src = conv_src()
        # Both the zero-summaries-warning path and the clean-success path emit
        # the same completion strings (2 occurrences each).
        assert src.count('self._update_status("Conversion completed!")') == 2
        assert src.count('self._log("✅ Conversion complete.", "SUCCESS")') == 2
        skeletons = literal_skeletons()
        assert (
            "   ⚠️ Zero sections were summarized — every segment was skipped as "
            "front/reference matter while summaries were requested. Markdown/DOCX "
            "outputs were still written; if you expected chapter summaries, disable "
            "the content filter or select chapters explicitly." in skeletons
        )

    def test_cancelled_by_user_lines(self):
        src = conv_src()
        assert 'self._update_status("Conversion cancelled")' in src
        assert (
            "⏹️ Conversion cancelled — partial summaries saved; downstream phases "
            "skipped." in literal_skeletons()
        )
        assert '"Cancelled by user"' in src

    def test_partial_failure_count_line(self):
        assert "   ⚠️  chapter(s) failed (empty response) —  succeeded." in literal_skeletons()

    def test_conversion_result_error_msg_literals(self):
        skeletons = literal_skeletons()
        assert (
            "All chapters returned empty responses — model may not be installed, "
            "VRAM insufficient, or quantization too aggressive. Try: ollama pull "
            "<model>, use IQ2_M instead of IQ2_XXS, or raise temperature to 1.0." in skeletons
        )
        assert (
            "None of the  selected chapter(s) were summarized — the selection matched "
            "no summarizable section. Re-pick chapters in the selector (per-chapter "
            "author bookmarks are no longer listed) or convert the whole book." in skeletons
        )


class TestCompletionSemantics:
    """The guard expressions, evaluated standalone (test_v002 precedent)."""

    @staticmethod
    def _valid(summaries):
        return [
            s
            for s in summaries
            if s
            and getattr(s, "success", True)
            and (s.executive_summary or s.bullet_points or s.thorough_summary)
        ]

    @staticmethod
    def _zero(summaries, generate, cancelled):
        return (not summaries) and bool(generate) and not cancelled

    def test_valid_summary_needs_success_and_some_content(self):
        ok = SimpleNamespace(
            success=True, executive_summary="e", bullet_points=[], thorough_summary=""
        )
        empty = SimpleNamespace(
            success=True, executive_summary="", bullet_points=[], thorough_summary=""
        )
        failed = SimpleNamespace(
            success=False, executive_summary="e", bullet_points=["b"], thorough_summary="t"
        )
        bullets_only = SimpleNamespace(
            success=True, executive_summary="", bullet_points=["b"], thorough_summary=""
        )
        assert self._valid([ok, empty, failed, bullets_only]) == [ok, bullets_only]

    def test_all_failed_and_failed_count_flags(self):
        # Mirrors: _all_failed = summaries and len(_valid_summaries) == 0;
        #          _failed_count = len(summaries) - len(_valid_summaries)
        #                          if summaries else 0
        empty_ok = SimpleNamespace(
            success=True, executive_summary="", bullet_points=[], thorough_summary=""
        )
        good = SimpleNamespace(
            success=True, executive_summary="e", bullet_points=[], thorough_summary=""
        )

        def flags(summaries):
            valid = self._valid(summaries)
            return (
                bool(summaries) and len(valid) == 0,
                len(summaries) - len(valid) if summaries else 0,
            )

        assert flags([]) == (False, 0)  # empty summaries → not all-failed, count 0
        assert flags([empty_ok, empty_ok]) == (True, 2)  # every chapter failed
        assert flags([good, empty_ok]) == (False, 1)  # partial failure: 1 failed

    def test_zero_summaries_flag_matrix(self):
        zero = self._zero
        assert zero([], True, False) is True  # the incident: flagged
        assert zero([], False, False) is False  # summaries off → fine
        assert zero([], True, True) is False  # cancelled branch owns it
        assert zero([object()], True, False) is False  # non-empty

    def test_success_expression_matrix(self):
        def success(summaries, all_failed, cancelled, zero, selection):
            return (
                (not all_failed if summaries else True)
                and not cancelled
                and not (zero and selection)
            )

        assert success([], False, False, False, False) is True  # empty + no selection
        assert success([], False, False, True, True) is False  # selection + zero → fail
        assert success([1], True, False, False, False) is False  # all failed → fail
        assert success([1], False, True, False, False) is False  # cancelled → fail
        assert success([1], False, False, False, False) is True  # clean success
        assert success([1], False, False, True, False) is True  # zero flag w/o selection


# ════════════════════════════════════════════════════════════════════════════
# 3. Diagnostic-summary line formats (conversion/reporting.py since the
#    Phase 3 commit-1 move — source pins)
# ════════════════════════════════════════════════════════════════════════════


class TestDiagnosticLineFormats:
    """Source pins for the end-of-run diagnostic block.

    V0.4.26 (Phase 3 commit 1): the block moved VERBATIM to
    core/pipeline/conversion/reporting.py (``run_diagnostic_summary``)
    with the mechanical ``self.`` -> ``converter.`` substitution — the
    pins follow the moved bodies (house precedent: the CoT-gate pins
    followed chapter_phases.py in test_v1820411_p2_tls_logs_literals.py).
    The literal skeletons (via ``literal_skeletons()``) span both modules.
    """

    def test_header_line_format(self):
        src = reporting_src()
        assert (
            'f"━━━ Elixir v{converter._get_app_version()} Conversion Diagnostic Summary ━━━"' in src
        )

    def test_book_and_total_pages_lines(self):
        src = reporting_src()
        assert 'converter._log(f"  Book: {book_title}", "INFO")' in src
        assert 'converter._log(f"  Total pages: {total_pages}", "INFO")' in src

    def test_pages_processed_variant_only_when_selection_active(self):
        src = reporting_src()
        # The line is emitted only when the processed count differs from the
        # whole-book total (the guard IS the "without selection" variant).
        assert "if _pages_processed != total_pages:" in src
        assert "  Pages processed:  (selection active —  of  pages)" in literal_skeletons()

    def test_segments_chapters_chunks_line(self):
        # Double space after "Segments:" — that is where the {len(segments)}
        # hole sits once the f-string fragments are reassembled.
        assert "  Segments:  (chapters: , chunks: )" in literal_skeletons()

    def test_summaries_generated_and_success_lines(self):
        src = reporting_src()
        assert (
            'converter._log(f"  Summaries generated: {len(summaries) if summaries else 0}", "INFO")'
            in src
        )
        assert 'f"    Success: {ok}, Failed: {failed}, Total bullets: {total_bullets}"' in src

    def test_coverage_line_format(self):
        src = reporting_src()
        assert 'converter._log(f"    Coverage: {_cov_str}", "INFO")' in src
        assert 'f"{_cov_val:.0%}" if isinstance(_cov_val, (int, float)) else "?"' in src

    def test_recall_floor_line_format(self):
        src = reporting_src()
        skeletons = literal_skeletons()
        assert "    Recall floor (deterministic, final set): theorists /" in skeletons
        assert ", conclusion items /" in skeletons
        # The optional percent suffixes render as "(NN%)" or are omitted.
        assert "f\" ({_rf['theorists_pct']:.0%})\"" in src
        assert "f\" ({_rf['conclusion_items_pct']:.0%})\"" in src

    def test_warnings_and_output_paths_lines(self):
        src = reporting_src()
        assert 'converter._log(f"  Warnings: {len(warnings)}", "INFO")' in src
        assert 'converter._log(f"    ⚠️ {w}", "WARNING")' in src
        assert 'converter._log(f"  Output dir: {converter.output_dir}", "INFO")' in src
        assert 'converter._log(f"  Log file: {converter.conv_logger.log_path}", "INFO")' in src
        assert (
            'converter._log(f"  Diagnostic JSONL: {converter.conv_logger.diagnostic_path}", "INFO")'
            in src
        )

    def test_provenance_stamps_header_line(self):
        assert "  Summary files ():" in literal_skeletons()
        # Each stamp line is the stamp_diagnostic() message, logged with the
        # level the helper returns — pinned in TestDiagnosticComputations.
        src = reporting_src()
        assert "stamp_diagnostic(" in src
        assert 'converter._log(f"    {_msg}", _level)' in src


class TestDiagnosticComputations:
    """The callable pieces the diagnostic block formats through."""

    def test_coverage_renderer_percent_and_question_mark(self):
        # Mirrors: _cov_str = f"{_cov_val:.0%}" if isinstance(...) else "?"
        def cov_str(val):
            return f"{val:.0%}" if isinstance(val, (int, float)) else "?"

        assert cov_str(0.876) == "88%"  # .0% rounds to nearest percent
        assert cov_str(0.5) == "50%"
        assert cov_str(1) == "100%"
        assert cov_str(0) == "0%"
        assert cov_str(None) == "?"
        assert cov_str("not-a-number") == "?"

    def test_stamp_diagnostic_fresh_file_info_line(self):
        from core.system.provenance import stamp_diagnostic

        text = (
            "# Results and Analysis\n\n"
            "<!-- generated-by: Elixir v0.4.25 | run_id=20260101-010203-abcd1234"
            " | started=2026-01-01T01:02:03 | bullets=41 -->\n\nbody\n"
        )
        level, msg = stamp_diagnostic("s.md", text, current_version="0.4.25")
        assert level == "INFO"
        assert msg == (
            "✓ s.md — generated-by v0.4.25 | run_id=20260101-010203-abcd1234"
            " | started=2026-01-01T01:02:03 | bullets=41"
        )

    def test_stamp_diagnostic_stale_version_escalates_to_warning(self):
        from core.system.provenance import stamp_diagnostic

        text = (
            "<!-- generated-by: Elixir v0.4.24 | run_id=20260101-010203-abcd1234"
            " | started=2026-01-01T01:02:03 | bullets=41 -->\n"
        )
        level, msg = stamp_diagnostic("s.md", text, current_version="0.4.25")
        assert level == "WARNING"
        assert msg.startswith("⚠️ s.md — STALE ARTIFACT: generated-by v0.4.24 (this app is v0.4.25)")
        assert "do NOT upload or audit it as this run's output" in msg

    def test_stamp_diagnostic_unstamped_file_warns(self):
        from core.system.provenance import stamp_diagnostic

        level, msg = stamp_diagnostic("s.md", "# no stamp here\nbody\n")
        assert level == "WARNING"
        assert msg == (
            "⚠️ s.md — NO generated-by stamp (pre-V18.20.3.7 artifact — verify "
            "before trusting or uploading it)"
        )

    def test_stamp_diagnostic_sentinel_only_counts_as_stamped(self):
        from core.system.provenance import stamp_diagnostic

        level, msg = stamp_diagnostic("s.md", "body\n<!-- COMPLETE run_id=run-42 -->\n")
        assert level == "INFO"
        assert msg == "✓ s.md — generated-by vunknown | run_id=run-42 | started=? | bullets=?"

    def test_get_app_version_reads_version_file(self):
        # Dynamic pin (not the literal "0.4.25") so a version bump doesn't
        # break the characterization — only the plumbing is pinned.
        version_file = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert Converter._get_app_version() == version_file


# ════════════════════════════════════════════════════════════════════════════
# 4. _generate_quality_report — JSON shape (hermetic, fake self)
# ════════════════════════════════════════════════════════════════════════════


class TestQualityReportJsonShape:
    def _run(self, tmp_path, segments, summaries):
        fake = _RecordingSelf(
            request=SimpleNamespace(input_path=Path("Sample_Book_Title.pdf")),
            paths=SimpleNamespace(quality_report=tmp_path / "logs" / "quality_report.json"),
        )
        Converter._generate_quality_report(fake, segments, summaries)
        report_path = fake.paths.quality_report
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        return fake, data

    def _fixture(self):
        segments = [
            Segment(
                heading="Results and Analysis",
                content="alpha beta gamma delta epsilon " * 10,
                start_page=1,
                end_page=2,
                segment_type="chapter",
            ),
            Segment(
                heading="Introduction to Methods",
                content="zeta eta theta " * 10,
                start_page=3,
                end_page=4,
                segment_type="chapter",
            ),
        ]
        good = SummaryResult(
            chapter_heading="Results and Analysis",
            executive_summary="alpha beta",
            thorough_summary="gamma delta",
            bullet_points=["b1", "b2"],
            success=True,
            model_used="test-model",
            input_tokens=900,
            output_tokens=100,
            recall_floor={
                "theorists_total": 10,
                "theorists_covered": 5,
                "conclusion_items_total": 8,
                "conclusion_items_covered": 6,
            },
        )
        return segments, [good, _make_summary("Introduction to Methods", input_tokens=42)]

    def test_top_level_shape_and_values(self, tmp_path):
        _, data = self._run(tmp_path, *self._fixture())
        assert set(data.keys()) == {"version", "timestamp", "book_title", "chapters", "totals"}
        assert data["version"] == "3.4.0"
        # stem "Sample_Book_Title" → replace _ with space → .title()
        assert data["book_title"] == "Sample Book Title"
        datetime.fromisoformat(data["timestamp"])  # ISO-format timestamp
        assert len(data["chapters"]) == 2

    def test_totals_shape_and_recall_floor_aggregate(self, tmp_path):
        _, data = self._run(tmp_path, *self._fixture())
        totals = data["totals"]
        assert set(totals.keys()) == {
            "chapters_summarized",
            "total_bullets",
            "total_concepts",
            "avg_coverage",
            "successful_summaries",
            "failed_summaries",
            "recall_floor",
        }
        assert isinstance(totals["avg_coverage"], float)
        assert isinstance(totals["total_concepts"], int)
        # Worked example: 2 chapters, 2 bullets, chapter 1 ok, chapter 2
        # flipped to failed by the hallucination quirk (see below).
        assert totals["chapters_summarized"] == 2
        assert totals["total_bullets"] == 2
        assert totals["successful_summaries"] == 1
        assert totals["failed_summaries"] == 1
        rf = totals["recall_floor"]
        assert set(rf.keys()) == {
            "theorists_covered",
            "theorists_total",
            "theorists_pct",
            "conclusion_items_covered",
            "conclusion_items_total",
            "conclusion_items_pct",
        }
        # Aggregated from chapter 1 only (chapter 2 has recall_floor=None → {}).
        assert rf["theorists_covered"] == 5
        assert rf["theorists_total"] == 10
        assert rf["theorists_pct"] == 0.5  # round(x, 4)
        assert rf["conclusion_items_covered"] == 6
        assert rf["conclusion_items_total"] == 8
        assert rf["conclusion_items_pct"] == 0.75

    def test_chapter_entry_shape_and_worked_example(self, tmp_path):
        _, data = self._run(tmp_path, *self._fixture())
        ch = data["chapters"][0]
        assert set(ch.keys()) == {
            "chapter_index",
            "heading",
            "success",
            "bullet_count",
            "model_used",
            "input_tokens",
            "output_tokens",
            "recall_floor",
            "concept_count",
            "concepts",
            "concepts_covered",
            "concepts_uncovered",
            "coverage",
        }
        assert ch["chapter_index"] == 1
        assert ch["heading"] == "Results and Analysis"
        assert ch["success"] is True
        assert ch["bullet_count"] == 2
        assert ch["model_used"] == "test-model"
        assert ch["input_tokens"] == 900
        assert ch["output_tokens"] == 100
        assert ch["recall_floor"] == {
            "theorists_total": 10,
            "theorists_covered": 5,
            "conclusion_items_total": 8,
            "conclusion_items_covered": 6,
        }
        # Deterministic worked example for the ngram-coverage estimate on
        # this fixed content: chapter 1 → 0.4, chapter 2 → 0.0, mean → 0.2.
        assert ch["coverage"] == pytest.approx(0.4)
        assert data["chapters"][1]["coverage"] == pytest.approx(0.0)
        assert data["totals"]["avg_coverage"] == pytest.approx(0.2)
        # concept accounting is internally consistent
        assert ch["concepts_covered"] + ch["concepts_uncovered"] == ch["concept_count"]
        assert ch["concept_count"] == len(ch["concepts"])

    def test_hallucination_quirk_zero_bullets_low_tokens_flips_success(self, tmp_path):
        fake, data = self._run(tmp_path, *self._fixture())
        ch = data["chapters"][1]
        # Fix 4: success=True + 0 bullets + <100 input tokens is a
        # hallucinated essay → marked failed with the error marker.
        assert ch["success"] is False
        assert ch["error"] == "Empty input — summary likely hallucinated"
        assert (
            "  ⚠️ Quality report: Chapter 2 'Introduction to Methods' has 0 bullets "
            "+ 42 input tokens — marking as FAILED (hallucination risk)" in fake.messages("WARNING")
        )
        # The odd `successful_summaries - 1 if not summ.success else ...`
        # arm is dead code (the branch requires summ.success) — the tally
        # keeps the other chapter's success and only increments failed.
        assert data["totals"]["successful_summaries"] == 1
        assert data["totals"]["failed_summaries"] == 1

    def test_write_line_and_atomic_output(self, tmp_path):
        fake, _ = self._run(tmp_path, *self._fixture())
        assert any(
            m.startswith("  📊 Quality report → ") and m.endswith("quality_report.json")
            for m in fake.messages("INFO")
        )

    def test_empty_summaries_edge(self, tmp_path):
        _, data = self._run(tmp_path, [], [])
        assert data["chapters"] == []
        assert data["totals"]["chapters_summarized"] == 0
        # avg_coverage stays 0.0 (guarded by `if summaries:`)
        assert data["totals"]["avg_coverage"] == 0.0
        assert data["totals"]["recall_floor"] == {
            "theorists_covered": 0,
            "theorists_total": 0,
            "theorists_pct": None,
            "conclusion_items_covered": 0,
            "conclusion_items_total": 0,
            "conclusion_items_pct": None,
        }

    def test_no_recall_floor_anywhere_yields_none_pcts(self, tmp_path):
        segments = [
            Segment(
                heading="Single",
                content="a b c " * 30,
                start_page=1,
                end_page=1,
                segment_type="chapter",
            )
        ]
        _, data = self._run(
            tmp_path, segments, [_make_summary("Single", bullets=["x"], input_tokens=500)]
        )
        assert data["totals"]["recall_floor"]["theorists_pct"] is None
        assert data["totals"]["recall_floor"]["conclusion_items_pct"] is None


# ════════════════════════════════════════════════════════════════════════════
# 5. _cross_chapter_dedup (hermetic, fake self)
# ════════════════════════════════════════════════════════════════════════════


class TestCrossChapterDedup:
    def test_exact_duplicate_removed_from_later_chapter(self):
        fake = _RecordingSelf()
        empty = _make_summary("First", bullets=[])
        second = _make_summary("Second", bullets=["Alpha beta gamma", "Delta epsilon zeta"])
        third = _make_summary("Third", bullets=["Alpha beta gamma", "Unique content here"])
        out = Converter._cross_chapter_dedup(fake, [empty, second, third])

        assert [s.chapter_heading for s in out] == ["First", "Second", "Third"]
        # First occurrence kept in the earlier chapter, dropped from the later.
        assert second.bullet_points == ["Alpha beta gamma", "Delta epsilon zeta"]
        assert third.bullet_points == ["Unique content here"]
        # Bullet-less summaries are skipped by the write-back indexing.
        assert empty.bullet_points == []
        # The INFO audit line + the DEBUG detail line.
        assert (
            "    🧹 cross_chapter_dedup: removed 1 cross-chapter duplicates (threshold 80%)"
            in fake.messages("INFO")
        )
        assert any(
            m.startswith("      🗑️ 'Alpha beta gamma...' (dup of 'Second...')")
            for m in fake.messages()
        )

    def test_unique_bullets_untouched_and_no_log(self):
        fake = _RecordingSelf()
        first = _make_summary("First", bullets=["Alpha beta gamma"])
        second = _make_summary("Second", bullets=["Delta epsilon zeta", "Another unique line"])
        Converter._cross_chapter_dedup(fake, [first, second])
        assert first.bullet_points == ["Alpha beta gamma"]
        assert second.bullet_points == ["Delta epsilon zeta", "Another unique line"]
        assert fake.logs == []  # nothing dropped → no log at all

    def test_near_duplicate_above_80_threshold_dropped(self):
        from rapidfuzz import fuzz

        # token_set_ratio 96.97 ≥ CROSS_CHAPTER_THRESHOLD (80)
        assert fuzz.token_set_ratio("alpha beta gamma", "alpha beta gammas") >= 80
        fake = _RecordingSelf()
        first = _make_summary("First", bullets=["Alpha beta gamma"])
        second = _make_summary("Second", bullets=["Alpha beta gammas"])
        Converter._cross_chapter_dedup(fake, [first, second])
        assert first.bullet_points == ["Alpha beta gamma"]
        assert second.bullet_points == []

    def test_cross_chapter_threshold_is_80(self):
        from core.summarisation.dedup_service import CROSS_CHAPTER_THRESHOLD

        assert CROSS_CHAPTER_THRESHOLD == 80


# ════════════════════════════════════════════════════════════════════════════
# 6. _enforce_vram_budget — policy branches (hermetic, monkeypatched calculator)
# ════════════════════════════════════════════════════════════════════════════


class TestVramBudgetPolicies:
    """core.vram_calculator is monkeypatched (pure stdlib module) so the
    policy logic runs against controlled peak/total numbers: peak 25.0 GB
    vs 16.0 GB total → overbudget in every enforcing case."""

    @staticmethod
    def _run(monkeypatch, policy_value, *, ack=False, total_vram=16.0, peak=25.0, error=None):
        import core.vram_calculator as vc

        request = ConversionRequest(input_path=Path("Sample_Book.pdf"), output_dir=Path("unused"))
        request.vram_overbudget_acknowledged = ack

        def _calc(**kwargs):
            if error is not None:
                raise error
            return ([], peak, total_vram, None)

        monkeypatch.setattr(vc, "get_total_vram", lambda: total_vram)
        monkeypatch.setattr(vc, "calculate_vram_budget", _calc)

        fake = _RecordingSelf(
            request=request,
            settings=_FakeSettings({"local.vram_overbudget_policy": policy_value}),
        )
        result = Converter._enforce_vram_budget(fake)
        return fake, result

    def test_fits_budget_returns_none_without_logs(self, monkeypatch):
        fake, result = self._run(monkeypatch, "proceed", total_vram=30.0)
        assert result is None
        assert fake.logs == []

    def test_no_gpu_detected_returns_none(self, monkeypatch):
        fake, result = self._run(monkeypatch, "proceed", total_vram=0.0)
        assert result is None
        assert fake.logs == []

    def test_proceed_policy_warns_and_continues(self, monkeypatch):
        fake, result = self._run(monkeypatch, "proceed")
        assert result is None
        assert fake.logs == [
            (
                "  ⚠️ VRAM OVERBUDGET (peak 25.0 GB > 16.0 GB) — "
                "local.vram_overbudget_policy=proceed: continuing at explicit user "
                "choice (expect heavy CPU offload).",
                "WARNING",
            )
        ]

    def test_ask_policy_with_acknowledgment_warns_and_continues(self, monkeypatch):
        fake, result = self._run(monkeypatch, "ask", ack=True)
        assert result is None
        assert fake.logs == [
            (
                "  ⚠️ VRAM OVERBUDGET (peak 25.0 GB > 16.0 GB) — acknowledged "
                "interactively by the user: continuing.",
                "WARNING",
            )
        ]

    def test_ask_policy_without_acknowledgment_aborts(self, monkeypatch):
        fake, result = self._run(monkeypatch, "ask", ack=False)
        assert result == (
            "VRAM overbudget: peak 25.0 GB > 16.0 GB available. Conversion aborted "
            "by local.vram_overbudget_policy='ask' before any work was done. "
            "Use a smaller model, or set local.vram_overbudget_policy='proceed' "
            "to continue anyway."
        )
        assert fake.messages("ERROR") == [
            "  🛑 VRAM OVERBUDGET — ABORTING: peak 25.0 GB > 16.0 GB available "
            "(model 'gemma3:12b' does not fit). A local model this large CPU-offloads "
            "at ~0.2 tokens/s — long chapters become hours-long map-reduce stalls. "
            "Fix: use a smaller model (fits 16 GB), or set "
            "local.vram_overbudget_policy='proceed' to force it, or start from the "
            "wizard and click 'Proceed anyway'."
        ]

    def test_abort_policy_aborts(self, monkeypatch):
        _, result = self._run(monkeypatch, "abort")
        assert result == (
            "VRAM overbudget: peak 25.0 GB > 16.0 GB available. Conversion aborted "
            "by local.vram_overbudget_policy='abort' before any work was done. "
            "Use a smaller model, or set local.vram_overbudget_policy='proceed' "
            "to continue anyway."
        )

    def test_policy_value_normalized_case_and_whitespace(self, monkeypatch):
        fake, result = self._run(monkeypatch, " PROCEED ")
        assert result is None
        assert "local.vram_overbudget_policy=proceed: continuing" in fake.messages("WARNING")[0]

    def test_unknown_policy_falls_through_to_abort(self, monkeypatch):
        _, result = self._run(monkeypatch, "nope")
        assert "local.vram_overbudget_policy='nope'" in result

    def test_empty_policy_reports_as_ask(self, monkeypatch):
        _, result = self._run(monkeypatch, "")
        assert "local.vram_overbudget_policy='ask'" in result

    def test_missing_setting_defaults_to_ask(self, monkeypatch):
        import core.vram_calculator as vc

        request = ConversionRequest(input_path=Path("b.pdf"), output_dir=Path("unused"))
        monkeypatch.setattr(vc, "get_total_vram", lambda: 16.0)
        monkeypatch.setattr(vc, "calculate_vram_budget", lambda **kw: ([], 25.0, 16.0, None))
        fake = _RecordingSelf(request=request, settings=_FakeSettings())
        result = Converter._enforce_vram_budget(fake)
        assert "local.vram_overbudget_policy='ask'" in result

    def test_calculator_failure_fails_open(self, monkeypatch):
        fake, result = self._run(monkeypatch, "abort", error=RuntimeError("calculator exploded"))
        assert result is None
        assert fake.logs == []


# ════════════════════════════════════════════════════════════════════════════
# 7. Screenshots page-filter precedence (source pins + helper unit tests)
# ════════════════════════════════════════════════════════════════════════════


class TestScreenshotsPageFilterPrecedence:
    def test_opt_in_gate_and_skip_line(self):
        src = conv_src()
        assert 'self.settings.get("outputs_optin.screenshots", False)' in src
        assert 'self._log("  ⏭️ Screenshots/graphs skipped (opt-in, disabled)", "DEBUG")' in src

    def test_filter_order_range_then_manual_segments_else_selected_chapters(self):
        src = conv_src()
        assert "page_list = list(range(1, total_pages + 1))" in src
        range_if = "if self.request.page_range_start or self.request.page_range_end:"
        manual_if = "if self.request.manual_segments:"
        chapters_elif = "elif self.request.selected_chapters:"
        assert range_if in src
        assert manual_if in src
        assert chapters_elif in src
        # Precedence: the full list is built, then the range filter, then
        # manual_segments; selected_chapters only applies via the ELIF —
        # manual segments win when both are set.
        assert src.index("page_list = list(range(1, total_pages + 1))") < src.index(range_if)
        assert src.index(range_if) < src.index(manual_if)
        assert src.index(manual_if) < src.index(chapters_elif)
        # manual_segments narrows the (already range-filtered) list:
        assert "page_list = [p for p in page_list if p in seg_pages]" in src
        # selected_chapters narrows through the TOC-derived page set:
        assert "page_list = [p for p in page_list if p in toc_page_set]" in src

    def test_tables_graphs_result_line(self):
        assert "  📊 Tables: , Graphs:  → tables.md + graphs.md" in literal_skeletons()


class TestDerivePageRangesFromToc:
    TOC = [
        ("Introduction to Methods", 1),
        ("Results and Analysis", 5),
        ("Discussion and Future Work", 9),
    ]

    def test_mid_chapter_spans_to_page_before_next_entry(self):
        fake = _RecordingSelf()
        result = Converter._derive_page_ranges_from_toc(
            fake, self.TOC, ["Results and Analysis"], 12
        )
        assert result == {5, 6, 7, 8}
        assert (
            "  [TOC-Range] Matched 'Results and Analysis…' → "
            "'Results and Analysis…' (p.5, score=1.00)" in fake.messages("DEBUG")
        )

    def test_last_chapter_extends_to_total_pages(self):
        result = Converter._derive_page_ranges_from_toc(
            _RecordingSelf(), self.TOC, ["Discussion and Future Work"], 12
        )
        assert result == {9, 10, 11, 12}

    def test_first_chapter_starts_at_its_own_page(self):
        result = Converter._derive_page_ranges_from_toc(
            _RecordingSelf(), self.TOC, ["Introduction to Methods"], 12
        )
        assert result == {1, 2, 3, 4}

    def test_multiple_selected_chapters_union(self):
        result = Converter._derive_page_ranges_from_toc(
            _RecordingSelf(),
            self.TOC,
            ["Introduction to Methods", "Discussion and Future Work"],
            12,
        )
        assert result == {1, 2, 3, 4, 9, 10, 11, 12}

    def test_no_toc_or_no_selection_returns_none(self):
        assert Converter._derive_page_ranges_from_toc(_RecordingSelf(), [], ["X"], 12) is None
        assert Converter._derive_page_ranges_from_toc(_RecordingSelf(), self.TOC, [], 12) is None

    def test_no_match_returns_none_with_warning(self):
        fake = _RecordingSelf()
        result = Converter._derive_page_ranges_from_toc(
            fake, [("Alpha Section", 3), ("Beta Section", 7)], ["Totally Different Words"], 12
        )
        assert result is None
        assert "  [TOC-Range] No TOC entries matched selected chapters." in fake.messages("WARNING")

    def test_same_page_toc_entries_deduped_to_first(self):
        # A metadata bookmark on the same page as its chapter must not
        # collapse the range to zero pages (V0.03 P0-4).
        toc = [("Chapter One", 4), ("Author Note", 4), ("Chapter Two", 8)]
        result = Converter._derive_page_ranges_from_toc(_RecordingSelf(), toc, ["Chapter One"], 12)
        assert result == {4, 5, 6, 7}

    def test_partial_title_match_via_fuzzy_score(self):
        # A partial/reordered selection still matches its chapter
        # (token_set_ratio-based score ≥ 0.3 gate).
        result = Converter._derive_page_ranges_from_toc(
            _RecordingSelf(), self.TOC, ["Results Analysis"], 12
        )
        assert result == {5, 6, 7, 8}


# ════════════════════════════════════════════════════════════════════════════
# 8. Simplified-keypoints skip messages (source pins + keyword semantics)
# ════════════════════════════════════════════════════════════════════════════


class TestSimplifiedKeypointsMessages:
    """The digest block runs inside convert() behind the summarization
    state — the emitted strings are source-pinned."""

    def test_entry_status_and_log_line(self):
        src = conv_src()
        assert 'self._update_status("Generating Simplified Keypoints Digest…")' in src
        # NOTE: "jargon‑free" uses a U+2011 non-breaking hyphen — pinned
        # verbatim so a refactor can't silently change the character.
        assert (
            'self._log("  📌 Generating simplified keypoints (jargon‑free digest)…", "INFO")' in src
        )

    def test_gate_requires_flag_summaries_and_no_cancel(self):
        src = conv_src()
        assert "self.request.simplified_keypoints_enabled" in src
        assert 'self._cancel_requested("simplified keypoints")' in src

    def test_success_line(self):
        assert "  ✅ Simplified keypoints saved to: " in literal_skeletons()

    def test_model_unavailable_branch_messages(self):
        src = conv_src()
        skeletons = literal_skeletons()
        # OSError/ConnectionError/TimeoutError branch:
        assert "  ⚠️ Simplification skipped (model unavailable): " in skeletons
        assert (
            "  ℹ️ Keypoints and summaries are still available without simplification." in skeletons
        )
        # The info line appears in BOTH except branches (2 occurrences).
        assert src.count("without simplification") == 2

    def test_infrastructure_keyword_branch_messages(self):
        src = conv_src()
        assert "  ⚠️ Simplification skipped (infrastructure error): " in literal_skeletons()
        # The keyword triage tuple (checked against str(e).lower()):
        anchor = src.find("for kw in (")
        assert anchor > 0
        window = src[anchor : anchor + 300]
        for kw in ("model", "load", "ollama", "connection", "timeout", "memory", "vram"):
            assert f'"{kw}"' in window, f"keyword {kw!r} missing from the triage tuple"

    def test_other_failure_line_logged_at_warning_not_error(self):
        src = conv_src()
        # Quirk pinned deliberately: the ❌ failure line is WARNING-level.
        assert 'self._log(f"  ❌ Failed to generate simplified keypoints: {e}", "WARNING")' in src

    def test_infrastructure_keyword_semantics(self):
        # Mirrors: any(kw in str(e).lower() for kw in KEYWORDS)
        keywords = ("model", "load", "ollama", "connection", "timeout", "memory", "vram")

        def is_infrastructure(err: Exception) -> bool:
            return any(kw in str(err).lower() for kw in keywords)

        assert is_infrastructure(RuntimeError("Model failed to load")) is True
        assert is_infrastructure(OSError("connection refused")) is True
        assert is_infrastructure(RuntimeError("CUDA out of MEMORY")) is True  # lowercased
        assert is_infrastructure(ValueError("bad bullet format")) is False


# ════════════════════════════════════════════════════════════════════════════
# 9. Status/progress plumbing used by the pinned blocks
# ════════════════════════════════════════════════════════════════════════════


class TestCallbackPlumbing:
    def test_update_status_passes_through_to_status_callback(self):
        seen = []
        fake = _RecordingSelf(status_callback=seen.append)
        Converter._update_status(fake, "Conversion completed!")
        assert seen == ["Conversion completed!"]

    def test_update_progress_clamps_to_unit_interval(self):
        seen = []
        fake = _RecordingSelf(progress_callback=seen.append)
        for value in (-0.5, 0.0, 0.42, 1.0, 1.5):
            Converter._update_progress(fake, value)
        assert seen == [0.0, 0.0, 0.42, 1.0, 1.0]

    def test_cancel_requested_gates_with_warning(self):
        event = threading.Event()
        fake = _RecordingSelf(cancel_event=event)
        assert Converter._cancel_requested(fake, "quality report") is False
        assert fake.logs == []
        event.set()
        assert Converter._cancel_requested(fake, "quality report") is True
        assert fake.messages("WARNING") == ["  ⏹️ Cancelled — skipping quality report"]


# ════════════════════════════════════════════════════════════════════════════
# 10. Phase 3 commit 1 — the reporting extraction itself (decomposition pins)
# ════════════════════════════════════════════════════════════════════════════

# The pre-move blob: the characterization commit (Phase 3 commit 0, whose
# 91 tests are the behavior spec).  Skipped when git/the ref is unavailable
# (the house skip-if-absent precedent: test_v182047's reference-zip checks).
_PRE_MOVE_REF = "29b6c58"


def _pre_move_src() -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "show", f"{_PRE_MOVE_REF}:core/pipeline/converter_impl.py"],
            capture_output=True,
            timeout=30,
            cwd=PROJECT_ROOT,
        )
    except Exception as e:  # pragma: no cover — environment-dependent
        pytest.skip(f"pre-move reference unavailable: {e}")
    if out.returncode != 0:  # pragma: no cover — shallow clone / missing ref
        pytest.skip(f"git show {_PRE_MOVE_REF} failed: {out.stderr.decode()[:120]}")
    return out.stdout.decode("utf-8")


def _ref_diag_block(ref_src: str) -> str:
    """The pre-move end-of-run diagnostics block (L1771-1978 of the ref),
    located by anchors, not line numbers."""
    lines = ref_src.splitlines(keepends=True)
    start = next(
        i
        for i, ln in enumerate(lines)
        if ln.startswith("            # End-of-conversion diagnostic summary")
    )
    # The block ends on the long ━-rule closing log line (the only one past
    # the start that is >60 chars — the Output-Summary rules are shorter).
    end = next(
        i
        for i in range(start, len(lines))
        if lines[i].strip().startswith('self._log("━') and len(lines[i].strip()) > 60
    )
    return "".join(lines[start : end + 1])


class TestReportingExtraction:
    """Phase 3 / commit 1: the reporting responsibility (the
    ``_generate_quality_report`` method + the 208-line end-of-run
    diagnostic block) moved from converter_impl.py to
    core/pipeline/conversion/reporting.py.  These pins hold the MOVE
    itself: module shape, class wiring, byte-identity vs the pre-move blob
    (commit 29b6c58), and Rule-1 deny-list cleanliness."""

    def test_module_parses_and_carries_exactly_the_moved_surface(self):
        tree = ast.parse(reporting_src())
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        assert [c.name for c in classes] == ["ConverterReportingMixin"]
        methods = {n.name for n in classes[0].body if isinstance(n, ast.FunctionDef)}
        assert methods == {"_generate_quality_report"}
        top_fns = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assert top_fns == ["run_diagnostic_summary"]

    def test_mixin_method_byte_identical_to_pre_move_blob(self):
        ref_src = _pre_move_src()
        ref_tree = ast.parse(ref_src)
        ref_cls = next(
            n for n in ref_tree.body if isinstance(n, ast.ClassDef) and n.name == "Converter"
        )
        ref_fn = next(
            n
            for n in ref_cls.body
            if isinstance(n, ast.FunctionDef) and n.name == "_generate_quality_report"
        )
        rep_tree = ast.parse(reporting_src())
        rep_cls = next(
            n
            for n in rep_tree.body
            if isinstance(n, ast.ClassDef) and n.name == "ConverterReportingMixin"
        )
        rep_fn = next(
            n
            for n in rep_cls.body
            if isinstance(n, ast.FunctionDef) and n.name == "_generate_quality_report"
        )
        # get_source_segment drops the def line's indent + final newline on
        # BOTH sides — the comparison is otherwise byte-exact.
        assert ast.get_source_segment(ref_src, ref_fn) == ast.get_source_segment(
            reporting_src(), rep_fn
        ), "_generate_quality_report drifted in the Phase-3 move (must be byte-identical)"

    def test_diagnostic_block_byte_identical_to_pre_move_blob(self):
        expected = _ref_diag_block(_pre_move_src())
        # Guard the reference forms first (the guarded-substitution
        # precedent from test_v182047), so any extra drift still fails.
        assert 'getattr(self, "_cache_stats_start", None)' in expected
        assert "_level, _msg = stamp_diagnostic(\n" in expected
        # The documented mechanical transform: dedent one try-level (12→4
        # spaces), self.→converter., the ONE bare self→converter, plus the
        # single ruff-format reflow of the stamp_diagnostic call at the
        # shallower indent (AST-identical).
        moved = "".join(
            (ln[8:] if ln.strip() else ln) for ln in expected.splitlines(keepends=True)
        ).replace("self.", "converter.")
        moved = moved.replace("getattr(self,", "getattr(converter,")
        old_call = (
            "                    _level, _msg = stamp_diagnostic(\n"
            "                        str(_sf), _text, current_version=_app_ver\n"
            "                    )\n"
        )
        new_call = (
            "                    _level, _msg = stamp_diagnostic("
            "str(_sf), _text, current_version=_app_ver)\n"
        )
        assert old_call in moved
        moved = moved.replace(old_call, new_call)
        rep_tree = ast.parse(reporting_src())
        fn = next(
            n
            for n in rep_tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "run_diagnostic_summary"
        )
        assert isinstance(fn.body[0], ast.Expr)  # the docstring
        rep_lines = reporting_src().splitlines(keepends=True)
        actual = "".join(rep_lines[fn.body[0].end_lineno : fn.end_lineno])
        assert actual == moved, "run_diagnostic_summary body drifted from the pre-move block"

    def test_run_diagnostic_summary_signature_threads_the_exact_locals(self):
        import inspect

        from core.pipeline.conversion.reporting import run_diagnostic_summary

        params = list(inspect.signature(run_diagnostic_summary).parameters)
        assert params == [
            "converter",
            "book_title",
            "total_pages",
            "_pages_processed",
            "segments",
            "summaries",
            "warnings",
            "_t_start",
        ]
        kwonly = [
            p.name
            for p in inspect.signature(run_diagnostic_summary).parameters.values()
            if p.kind == inspect.Parameter.KEYWORD_ONLY
        ]
        assert kwonly == params[1:]  # everything but `converter` is keyword-only

    def test_converter_bases_and_mro_sane(self):
        assert [c.__name__ for c in Converter.__bases__] == [
            "ConverterExtractionMixin",
            "ConverterVisualMixin",
            "ConverterReportingMixin",  # appended last (the house pattern)
        ]
        assert [c.__name__ for c in Converter.__mro__] == [
            "Converter",
            "ConverterExtractionMixin",
            "ConverterVisualMixin",
            "ConverterReportingMixin",
            "object",
        ]

    def test_generate_quality_report_resolves_via_the_mixin(self):
        from core.pipeline.conversion.reporting import ConverterReportingMixin

        assert (
            Converter._generate_quality_report is ConverterReportingMixin._generate_quality_report
        )
        assert "def _generate_quality_report" not in conv_src()  # gone from the host
        # ...but the convert() call site is byte-identical (also pinned by
        # test_v1820411_p2_tls_logs_literals.py:576):
        assert "self._generate_quality_report(segments, summaries)" in conv_src()

    def test_convert_delegates_with_the_exact_locals(self):
        src = conv_src()
        assert "from core.pipeline.conversion.reporting import run_diagnostic_summary" in src
        assert "run_diagnostic_summary(\n                self," in src
        for arg in (
            "book_title=book_title",
            "total_pages=total_pages",
            "_pages_processed=_pages_processed",
            "segments=segments",
            "summaries=summaries",
            "warnings=warnings",
            "_t_start=_t_start",
        ):
            assert arg in src, f"the delegate call must thread {arg}"

    def test_moved_code_gone_from_converter_impl(self):
        src = conv_src()
        assert "Conversion Diagnostic Summary" not in src  # the moved header
        assert "atomic_write_json" not in src  # moved with the quality report
        assert "call_telemetry_summary" not in src  # moved with the block

    def test_reporting_is_an_acyclic_leaf_module(self):
        for node in ast.walk(ast.parse(reporting_src())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("core.pipeline"), (
                    "reporting.py must not import core.pipeline (acyclic leaf)"
                )

    def test_reporting_logger_is_the_main_elixir_logger(self):
        # The moved bodies' logger.debug traces keep their exact pre-move
        # routing — the "Elixir" main logger, not logging.getLogger(__name__).
        import core.pipeline.conversion.reporting as rep

        assert rep.logger is conv_impl.logger

    def test_reporting_no_book_vocabulary(self):
        # Rule 1 deny-list (compact copy of the test_v182039 vocabulary —
        # the permanent tree-wide guard lives there).
        deny = (
            "Erikson",
            "Kernberg",
            "Winnicott",
            "Mahler",
            "Akhtar",
            "Oedipus",
            "false self",
            "identity diffusion",
            "ego identity",
            "Broken Structures",
            "psychoanalysis",
        )
        offenders = [
            (i, term)
            for i, line in enumerate(reporting_src().splitlines(), 1)
            for term in deny
            if term.lower() in line.lower()
        ]
        assert not offenders, offenders
