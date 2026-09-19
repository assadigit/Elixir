"""P2 (Test-Net Deepening): hermetic tests for text_preprocessor_impl
hyphenation / header-footer / paragraph / section detection logic.

Covers the low-coverage pure-text utilities of
``core/summarisation/text_preprocessor_impl.py``:

  - ``repair_hyphenation``        (A2 — PDF hyphenated line-break repair)
  - ``remove_headers_footers``    (A1 — repeating header/footer removal)
  - ``smart_paragraph_joining``   (A3 — mid-sentence line rejoining)
  - ``detect_sections``           (A6 — sub-heading detection)
  - ``DeterministicPreprocessor`` (facade class over A1-A7)

All tests are pure-function, input → expected-output. No LLM, no spacy,
no network, no filesystem.

Run: pytest tests/test_p2_preproc_hyphen_headers_paragraphs.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation import text_preprocessor_impl as tpi

# ═══════════════════════════════════════════════════════════════════════════
# A2: repair_hyphenation
# ═══════════════════════════════════════════════════════════════════════════


class TestRepairHyphenation:
    def test_basic_join(self):
        assert tpi.repair_hyphenation("net-\nworking") == "networking"

    def test_accented_latin_join(self):
        # V18.1 (O4): \u00C0-\u024F range covers accented Latin chars.
        assert tpi.repair_hyphenation("café-\nbar") == "cafébar"
        assert tpi.repair_hyphenation("Über-\nschrift") == "Überschrift"

    def test_capitalized_right_side_joined(self):
        # V18.2.18 (O4): capitalized + accented lookahead joins correctly.
        assert tpi.repair_hyphenation("word-\nNext") == "wordNext"

    def test_no_newline_no_change(self):
        # A real hyphenated compound without a line break is untouched.
        assert tpi.repair_hyphenation("state-of-the-art") == "state-of-the-art"

    def test_too_long_compound_not_joined(self):
        # Full joined word > _MAX_JOINED_WORD_LEN (25) → keep the break.
        text = "pneumonoultramicroscopic-\nsilicovolcanoconiosis"
        assert tpi.repair_hyphenation(text) == text

    def test_length_cap_uses_full_left_word(self):
        # V18.2.18 (O4): the look-BACK assembles the full left word, so a
        # long left fragment + short right side must NOT be joined. The
        # guard is len(full_left) + len(rest) > _MAX_JOINED_WORD_LEN (25).
        left = "a" * 12  # full_left = 13 chars (12 + captured char)
        right = "b" * 11  # rest = 11 chars
        assert len(left) + 1 + len(right) == 24  # ≤ 25 → joined
        assert tpi.repair_hyphenation(f"x {left}-\n{right}") == f"x {left}{right}"
        left31 = "b" * 30
        assert tpi.repair_hyphenation(f"x {left31}-\n{right}") == f"x {left31}-\n{right}"

    def test_digits_not_joined(self):
        # The pattern only matches letters around the hyphen-newline.
        assert tpi.repair_hyphenation("123-\n456") == "123-\n456"

    def test_multiple_breaks_in_one_text(self):
        text = "The net-\nworking layer and the pack-\net format."
        assert tpi.repair_hyphenation(text) == "The networking layer and the packet format."

    def test_empty_and_no_match(self):
        assert tpi.repair_hyphenation("") == ""
        assert tpi.repair_hyphenation("plain text only") == "plain text only"

    def test_boundary_exactly_25_chars_joined(self):
        # Joined word of exactly 25 chars → allowed; 26 chars → refused.
        left = "c" * 12  # full_left = 12
        right = "d" * 13  # rest = 13 → total 25 → joined
        assert tpi.repair_hyphenation(f"x {left}-\n{right}") == f"x {left}{right}"
        left13 = "c" * 13  # full_left = 13
        right13 = "e" * 13  # rest = 13 → total 26 → not joined
        assert tpi.repair_hyphenation(f"x {left13}-\n{right13}") == f"x {left13}-\n{right13}"


# ═══════════════════════════════════════════════════════════════════════════
# A1: remove_headers_footers
# ═══════════════════════════════════════════════════════════════════════════


def _page_filler(word: str) -> str:
    # ≥500 chars per page so the function's early-exit guard never fires.
    return (
        f"{word} content line with lots of text here to fill up the page nicely so we exceed five hundred characters. "
        * 8
    )


def _two_page_text() -> str:
    page1 = "Running Header\n" + _page_filler("Alpha") + "\n42"
    page2 = "Running Header\n" + _page_filler("Beta") + "\n43"
    return f"<!-- Page 1 -->\n{page1}\n<!-- Page 2 -->\n{page2}"


class TestRemoveHeadersFooters:
    def test_empty_and_short_text_unchanged(self):
        assert tpi.remove_headers_footers("") == ""
        short = "Some short text under 500 chars."
        assert tpi.remove_headers_footers(short) == short

    def test_repeated_header_and_page_numbers_removed(self):
        text = _two_page_text()
        assert len(text) >= 500
        out = tpi.remove_headers_footers(text)
        assert "Running Header" not in out
        assert not re.search(r"^\s*42\s*$", out, re.MULTILINE)
        assert not re.search(r"^\s*43\s*$", out, re.MULTILINE)
        # Page markers themselves are NOT page-number lines — they survive.
        assert out.count("<!-- Page") == 2
        # Body content survives.
        assert "Alpha content line" in out
        assert "Beta content line" in out

    def test_bracket_page_marker_style(self):
        page1 = "Running Header\n" + _page_filler("Alpha") + "\n7"
        page2 = "Running Header\n" + _page_filler("Beta") + "\n8"
        text = f"[Page 1]\n{page1}\n[Page 2]\n{page2}"
        out = tpi.remove_headers_footers(text)
        assert "Running Header" not in out

    def test_too_few_markers_strips_bare_page_numbers(self):
        # ≥500 chars but <2 page markers → only bare page-number lines stripped.
        text = (
            "Some text line\n\n99\n\nmore text here we keep going past five hundred characters total. "
            * 8
        )
        assert len(text) >= 500
        out = tpi.remove_headers_footers(text)
        assert not re.search(r"^\s*99\s*$", out, re.MULTILINE)
        assert "Some text line" in out

    def test_pages_under_two_returns_unchanged(self):
        # 2 markers but the second page is empty → <2 pages → unchanged.
        text = f"<!-- Page 1 -->\n{_page_filler('Alpha')}\n<!-- Page 2 -->\n\n"
        assert tpi.remove_headers_footers(text) == text

    def test_no_repeating_header_returns_unchanged(self):
        text = f"<!-- Page 1 -->\n{_page_filler('Alpha')}\n<!-- Page 2 -->\n{_page_filler('Beta')}"
        assert tpi.remove_headers_footers(text) == text

    def test_short_repeated_line_not_removed(self):
        # Repeated lines of ≤3 chars never qualify as headers (len(line) > 3).
        page1 = "AB\n" + _page_filler("Alpha") + "\n12"
        page2 = "AB\n" + _page_filler("Beta") + "\n13"
        text = f"<!-- Page 1 -->\n{page1}\n<!-- Page 2 -->\n{page2}"
        out = tpi.remove_headers_footers(text)
        assert "AB" in out

    def test_removal_collapses_triple_newlines(self):
        page1 = "Running Header\n" + _page_filler("Alpha") + "\n42"
        page2 = "Running Header\n" + _page_filler("Beta") + "\n43"
        page3 = "Running Header\n" + _page_filler("Gamma") + "\n44"
        text = f"<!-- Page 1 -->\n{page1}\n<!-- Page 2 -->\n{page2}\n<!-- Page 3 -->\n{page3}"
        out = tpi.remove_headers_footers(text)
        assert "Running Header" not in out
        assert "\n\n\n" not in out


# ═══════════════════════════════════════════════════════════════════════════
# A3: smart_paragraph_joining
# ═══════════════════════════════════════════════════════════════════════════


class TestSmartParagraphJoining:
    def test_empty(self):
        assert tpi.smart_paragraph_joining("") == ""

    def test_joins_mid_sentence_break(self):
        assert tpi.smart_paragraph_joining("This is a line that\ncontinues here.") == (
            "This is a line that continues here."
        )

    def test_no_join_after_sentence_end(self):
        text = "Complete sentence.\nNew sentence here."
        assert tpi.smart_paragraph_joining(text) == text

    def test_no_join_after_colon_or_quote(self):
        # _SENTENCE_END includes : " ” ’
        for ending in (":", '"', "\u201d", "\u2019", "!", "?"):
            text = f"Ends with {ending}\nlowercase follows."
            assert tpi.smart_paragraph_joining(text) == text, ending

    def test_no_join_when_next_starts_uppercase(self):
        text = "incomplete line\nUppercase start."
        assert tpi.smart_paragraph_joining(text) == text

    def test_no_join_when_next_is_bullet_or_number(self):
        for nxt in ("- bullet", "* bullet", "• bullet", "1. item", "2. item", "3. item"):
            text = f"some text\n{nxt}"
            assert tpi.smart_paragraph_joining(text) == text, nxt

    def test_no_join_when_current_is_markdown_heading(self):
        text = "## Heading\nlowercase follows."
        assert tpi.smart_paragraph_joining(text) == text

    def test_no_join_when_next_line_empty(self):
        text = "incomplete line\n\nmore text"
        assert tpi.smart_paragraph_joining(text) == text

    def test_three_line_chain_joins(self):
        # Line1 joins line2; the merged line no longer ends mid-sentence →
        # the result keeps line3 separate because it ends with a period and
        # line3 starts uppercase anyway.
        out = tpi.smart_paragraph_joining("alpha\nbeta\ngamma.")
        assert out == "alpha beta\ngamma."

    def test_join_strips_surrounding_whitespace(self):
        assert tpi.smart_paragraph_joining("text \n   next   ") == "text next"

    def test_preserves_blank_lines_between_paragraphs(self):
        text = "First paragraph done.\n\nSecond paragraph done."
        assert tpi.smart_paragraph_joining(text) == text


# ═══════════════════════════════════════════════════════════════════════════
# A6: detect_sections
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectSections:
    def test_empty(self):
        assert tpi.detect_sections("") == []

    def test_title_case_heading_detected(self):
        text = "Intro paragraph text here.\n\nSecond Heading\n\nBody follows."
        assert "Second Heading" in tpi.detect_sections(text)

    def test_heading_at_start_of_text_detected(self):
        assert tpi.detect_sections("First Heading\nbody text") == ["First Heading"]

    def test_all_caps_heading_detected(self):
        text = "intro text here\n\nALL CAPS TITLE\nbody"
        assert "ALL CAPS TITLE" in tpi.detect_sections(text)

    def test_max_sections_cap(self):
        lines = []
        for i in range(1, 12):
            lines.append(f"Heading Number {i:02d}")
            lines.append(f"body text {i}")
        text = "\n\n".join(lines)
        assert len(tpi.detect_sections(text, max_sections=4)) == 4
        assert len(tpi.detect_sections(text)) <= 8

    def test_line_with_ending_punctuation_skipped(self):
        text = "intro\n\nThis Ends With Period.\nbody"
        assert tpi.detect_sections(text) == []

    def test_pure_number_line_skipped(self):
        text = "intro\n\n42\nbody"
        assert tpi.detect_sections(text) == []

    def test_lowercase_start_skipped(self):
        text = "intro\n\nlowercase heading text\nbody"
        assert tpi.detect_sections(text) == []

    def test_long_line_skipped(self):
        text = "intro\n\n" + "X" * 81 + "\nbody"
        assert tpi.detect_sections(text) == []

    def test_no_blank_line_before_skipped(self):
        text = "text line before\nMid Paragraph Heading\nbody"
        assert tpi.detect_sections(text) == []

    def test_markdown_prefix_heading_not_detected(self):
        # CHARACTERIZATION (suspected bug — report only): "## First Section"
        # is skipped because stripped[0] == '#' fails the .isupper() check
        # BEFORE the markdown prefix is stripped. The "#"-prefix strip at
        # the end of the loop is unreachable for markdown headings.
        text = "intro text here.\n\n## First Section\n\nbody"
        assert tpi.detect_sections(text) == []

    def test_numbered_heading_not_detected(self):
        # CHARACTERIZATION: "1. Title" is skipped by the same isupper() gate
        # (the r"^\d+\." fallback in the word-count check is unreachable).
        text = "intro text here.\n\n1. Numbered Heading\n\nbody"
        assert tpi.detect_sections(text) == []


# ═══════════════════════════════════════════════════════════════════════════
# DeterministicPreprocessor facade
# ═══════════════════════════════════════════════════════════════════════════


class TestDeterministicPreprocessor:
    @pytest.fixture()
    def pp(self):
        return tpi.DeterministicPreprocessor()

    def test_preprocess_empty(self, pp):
        assert pp.preprocess("") == ""
        assert pp.preprocess(None) is None  # falsy pass-through

    def test_preprocess_runs_hyphenation_and_joining(self, pp):
        raw = "The net-\nworking layer\ncontinues here."
        out = pp.preprocess(raw)
        assert "networking" in out
        assert "continues here" in out

    def test_extract_concepts_delegates(self, pp):
        text = 'Use the "Focus Base" idea. Use the "Focus Base" again.'
        assert pp.extract_concepts(text) == tpi.extract_definitions(text)

    def test_extract_callouts_delegates(self, pp):
        text = "[Key Point]: This is a very important callout sentence here."
        assert pp.extract_callouts(text) == tpi.extract_callouts(text)

    def test_extract_keywords_delegates(self, pp):
        text = "network protocol routing network protocol routing network"
        assert pp.extract_keywords(text, n=3) == tpi.extract_ngram_keywords(text, n=3)

    def test_detect_sections_delegates(self, pp):
        text = "intro\n\nSome Heading\nbody"
        assert pp.detect_sections(text) == tpi.detect_sections(text)

    def test_analyze_returns_all_keys(self, pp):
        result = pp.analyze(
            "Some heading text and body words here repeated body words here repeated."
        )
        assert set(result) == {"concepts", "callouts", "keywords", "sections"}
        assert isinstance(result["concepts"], list)
        assert isinstance(result["callouts"], list)
        assert isinstance(result["keywords"], list)
        assert isinstance(result["sections"], list)


class TestGapClosing:
    """Second-wave branch coverage for the A1/A3/A6 utilities."""

    def test_pages_under_two_returns_unchanged_long_text(self):
        # ≥500 chars + 2 markers + only one non-empty page → early return.
        text = f"<!-- Page 1 -->\n{_page_filler('Alpha')}\n<!-- Page 2 -->\n\n"
        assert len(text) >= 500
        assert tpi.remove_headers_footers(text) == text

    def test_repeated_footer_removed(self):
        page1 = "Running Header\n" + _page_filler("Alpha") + "\nFooter Text Inc"
        page2 = "Running Header\n" + _page_filler("Beta") + "\nFooter Text Inc"
        text = f"<!-- Page 1 -->\n{page1}\n<!-- Page 2 -->\n{page2}"
        out = tpi.remove_headers_footers(text)
        assert "Running Header" not in out
        assert "Footer Text Inc" not in out
        assert "Alpha content" in out

    def test_detect_sections_single_word_heading_skipped(self):
        text = "intro\n\nHeading\nbody text follows"
        assert tpi.detect_sections(text) == []

    def test_detect_sections_mixed_case_skipped(self):
        # Not title-case (second word lowercase) and not all-caps → skipped.
        text = "intro\n\nFoo bar Baz\nbody text follows"
        assert tpi.detect_sections(text) == []

    def test_normalize_all_fragments_filtered_returns_original(self):
        # Fragments ≤3 chars (with an uppercase continuation so the split
        # actually happens) → no sentences survive → original returned.
        assert tpi.normalize_sentence_boundaries("ab. Cd.") == "ab. Cd."
