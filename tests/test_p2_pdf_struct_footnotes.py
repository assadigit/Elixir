"""Phase 2 (Test-Net Deepening) — hermetic tests for ``core/pdf/footnote_extractor.py``.

The module is a pure text-in/text-out pipeline (markdown with
``<!-- Page N -->`` markers in, footnotes/endnotes/cleaned-text out), so the
tests drive the real production functions directly with crafted text — no
PDF rendering, network, or subprocess involved.

Covered:
* endnote-section detection (``Notes`` / ``Endnotes`` / ``Footnotes`` headers,
  0–3 leading hashes), extraction and removal from the cleaned text,
* inline bottom-of-page footnote extraction with ``<!-- Page N -->`` markers
  (both ``1.`` and ``1)`` styles, >=10-char text guard, <=5-line pages,
  short-page guard, multi-page collection),
* ``format_footnotes_for_summary`` rendering for empty / footnote-only /
  endnote-only / mixed inputs.

Characterization notes (reported, not fixed):
* the ``page_markers`` parameter of ``extract_footnotes`` is accepted but
  never used by the implementation,
* a bare ``Notes`` header at the very end of the text (no trailing newline)
  is NOT recognised as an endnotes section by the regex.
"""

from __future__ import annotations

from core.pdf.footnote_extractor import extract_footnotes, format_footnotes_for_summary


def _page(*lines: str) -> str:
    """Assemble a ``<!-- Page 1 -->`` block from the given body lines."""
    return "<!-- Page 1 -->\n" + "\n".join(lines) + "\n"


_BODY = [f"Body narrative line number {i} of the page." for i in range(1, 7)]


# ────────────────────────────────────────────────────────────────────────────
# Plain text (no notes anywhere)
# ────────────────────────────────────────────────────────────────────────────


class TestExtractFootnotesPlain:
    def test_plain_text_unchanged(self):
        text = "Just an ordinary paragraph.\nAnd a second paragraph line.\n"
        result = extract_footnotes(text)
        assert result == {
            "footnotes": [],
            "endnotes": [],
            "cleaned_text": text,
            "total_notes": 0,
        }

    def test_page_markers_argument_is_accepted_but_unused(self):
        # CHARACTERIZATION (reported, not fixed): the documented
        # ``page_markers`` parameter is ignored by the implementation — the
        # result must be identical whether or not it is supplied.
        text = _page(*_BODY, "1. A footnote definition at the page bottom.")
        assert extract_footnotes(text) == extract_footnotes(text, page_markers=[(0, 1)])


# ────────────────────────────────────────────────────────────────────────────
# Endnotes section
# ────────────────────────────────────────────────────────────────────────────


class TestEndnotesSection:
    def test_endnotes_extracted_and_removed(self):
        text = (
            "Chapter body text stays.\n"
            "\n"
            "## Notes\n"
            "1. First endnote with enough text to match.\n"
            "2) Second endnote also with enough text.\n"
        )
        result = extract_footnotes(text)
        assert result["endnotes"] == [
            {"number": 1, "text": "First endnote with enough text to match.", "type": "endnote"},
            {"number": 2, "text": "Second endnote also with enough text.", "type": "endnote"},
        ]
        assert result["footnotes"] == []
        assert result["total_notes"] == 2
        assert result["cleaned_text"] == "Chapter body text stays."

    @staticmethod
    def _with_header(header: str) -> str:
        return f"Body.\n\n{header}\n1. An endnote line with plenty of text.\n"

    def test_header_variants_recognised(self):
        for header in ("Notes", "Endnotes", "Footnotes", "# Notes", "## Endnotes", "### Footnotes"):
            result = extract_footnotes(self._with_header(header))
            assert result["endnotes"] == [
                {"number": 1, "text": "An endnote line with plenty of text.", "type": "endnote"}
            ], header
            assert result["cleaned_text"] == "Body.", header

    def test_endnote_text_too_short_not_collected(self):
        # the definition regex requires >= 10 chars of note text
        text = "Body.\n\n# Notes\n1. Tiny.\n"
        result = extract_footnotes(text)
        assert result["endnotes"] == []
        assert result["total_notes"] == 0
        # the (empty) notes section is still removed from the cleaned text
        assert result["cleaned_text"] == "Body."

    def test_endnote_numbers_not_reset_across_lines(self):
        text = "Body.\n\nNotes\n3. Third endnote with plenty of text.\n12. Twelfth endnote with plenty of text.\n"
        result = extract_footnotes(text)
        assert [e["number"] for e in result["endnotes"]] == [3, 12]

    def test_header_without_trailing_newline_not_matched(self):
        # CHARACTERIZATION (reported, not fixed): the section regex requires
        # a newline after the header word, so a header at EOF is ignored.
        text = "Body text here.\n\n## Notes"
        result = extract_footnotes(text)
        assert result["endnotes"] == []
        assert result["cleaned_text"] == text


# ────────────────────────────────────────────────────────────────────────────
# Inline bottom-of-page footnotes
# ────────────────────────────────────────────────────────────────────────────


class TestInlineFootnotes:
    def test_footnote_at_page_bottom_extracted_and_removed(self):
        text = _page(*_BODY, "1. A footnote definition sitting at the bottom.")
        result = extract_footnotes(text)
        assert result["footnotes"] == [
            {
                "number": 1,
                "text": "A footnote definition sitting at the bottom.",
                "type": "footnote",
            }
        ]
        assert result["endnotes"] == []
        assert result["total_notes"] == 1
        # the footnote line is stripped from the body, the body survives
        assert "1. A footnote definition" not in result["cleaned_text"]
        for i in (1, 2, 3, 6):
            assert f"Body narrative line number {i}" in result["cleaned_text"]
        # page markers survive the cleaning pass
        assert "<!-- Page 1 -->" in result["cleaned_text"]

    def test_parenthesis_marker_style(self):
        text = _page(*_BODY, "7) A parenthesis style footnote with text.")
        result = extract_footnotes(text)
        assert result["footnotes"] == [
            {"number": 7, "text": "A parenthesis style footnote with text.", "type": "footnote"}
        ]

    def test_short_definition_treated_as_body(self):
        text = _page(*_BODY, "3. Tiny.")
        result = extract_footnotes(text)
        assert result["footnotes"] == []
        assert "3. Tiny." in result["cleaned_text"]

    def test_short_page_part_kept_verbatim(self):
        # a page block with fewer than 3 lines is never scanned for notes
        text = "<!-- Page 9 -->\n1. A footnote line with plenty of text."
        result = extract_footnotes(text)
        assert result["footnotes"] == []
        assert result["cleaned_text"] == text

    def test_few_line_page_scans_all_lines(self):
        # <= 5 lines: body_lines starts empty and every non-note line is
        # appended back, so a lone footnote line is still found.
        text = _page("Only line one.", "Only line two.", "1. Lone footnote with plenty of text.")
        result = extract_footnotes(text)
        assert result["footnotes"] == [
            {"number": 1, "text": "Lone footnote with plenty of text.", "type": "footnote"}
        ]
        assert "Only line one." in result["cleaned_text"]
        assert "1. Lone footnote" not in result["cleaned_text"]

    def test_multiple_pages_both_collected(self):
        text = (
            "<!-- Page 1 -->\n"
            + "\n".join(f"First page body line {i}." for i in range(1, 7))
            + "\n1. First page footnote with enough text.\n"
            "<!-- Page 2 -->\n"
            + "\n".join(f"Second page body line {i}." for i in range(1, 7))
            + "\n2. Second page footnote with enough text.\n"
        )
        result = extract_footnotes(text)
        assert [f["number"] for f in result["footnotes"]] == [1, 2]
        assert result["total_notes"] == 2
        assert "First page body line 1." in result["cleaned_text"]
        assert "Second page body line 6." in result["cleaned_text"]
        assert "<!-- Page 2 -->" in result["cleaned_text"]

    def test_footnotes_and_endnotes_together(self):
        text = (
            "<!-- Page 1 -->\n"
            + "\n".join(f"Chapter body line {i} of the page." for i in range(1, 7))
            + "\n1. Page footnote with plenty of body text.\n"
            "\n## Notes\n1. First endnote entry with enough text.\n"
        )
        result = extract_footnotes(text)
        assert [f["number"] for f in result["footnotes"]] == [1]
        assert [e["number"] for e in result["endnotes"]] == [1]
        assert result["total_notes"] == 2
        assert "## Notes" not in result["cleaned_text"]
        assert "First endnote entry" not in result["cleaned_text"]


# ────────────────────────────────────────────────────────────────────────────
# Formatting for the summary
# ────────────────────────────────────────────────────────────────────────────


class TestFormatFootnotesForSummary:
    def test_empty_inputs_return_empty_string(self):
        assert format_footnotes_for_summary([], []) == ""

    def test_footnotes_and_endnotes_rendered(self):
        footnotes = [{"number": 1, "text": "First footnote body."}]
        endnotes = [{"number": 5, "text": "Fifth endnote body."}]
        assert format_footnotes_for_summary(footnotes, endnotes) == (
            "### Footnotes & Endnotes\n\n[^1]: First footnote body.\n\n[^5]: Fifth endnote body.\n"
        )

    def test_footnotes_only(self):
        out = format_footnotes_for_summary([{"number": 2, "text": "Note two."}], [])
        assert out == "### Footnotes & Endnotes\n\n[^2]: Note two.\n"

    def test_endnotes_only(self):
        out = format_footnotes_for_summary([], [{"number": 3, "text": "Note three."}])
        assert out == "### Footnotes & Endnotes\n\n[^3]: Note three.\n"

    def test_overlapping_numbers_rendered_separately(self):
        # footnote 1 and endnote 1 coexist — no cross-type deduplication
        out = format_footnotes_for_summary(
            [{"number": 1, "text": "Footnote one."}], [{"number": 1, "text": "Endnote one."}]
        )
        assert "[^1]: Footnote one." in out
        assert "[^1]: Endnote one." in out

    def test_roundtrip_with_extract_footnotes(self):
        text = _page(*_BODY, "1. A footnote definition at the page bottom.")
        result = extract_footnotes(text)
        rendered = format_footnotes_for_summary(result["footnotes"], result["endnotes"])
        assert "[^1]: A footnote definition at the page bottom." in rendered
