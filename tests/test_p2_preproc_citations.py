"""P2 (Test-Net Deepening): hermetic tests for
``core/summarisation/text_preprocessor_citations.py``.

Covers all three public functions (43 stmts, 19% baseline coverage):

  - ``extract_citations``          — author-year / [N] bracket / (N) numerical
  - ``extract_reference_list``     — References section parsing
  - ``extract_figure_descriptions`` — Figure / Fig. / Table / markdown images

plus the backward-compat re-export surface in ``text_preprocessor_impl``.

Pure regex logic — fully hermetic. No mocks, no network.

Run: pytest tests/test_p2_preproc_citations.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import core.summarisation.text_preprocessor_citations as tc
import core.summarisation.text_preprocessor_impl as tpi

# ═══════════════════════════════════════════════════════════════════════════
# extract_citations
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractCitations:
    def test_author_year(self):
        out = tc.extract_citations("Smith (2020) found results.")
        assert out == [
            {"type": "author_year", "citation": "Smith (2020)", "author": "Smith", "year": "2020"}
        ]

    def test_author_year_with_letter_suffix(self):
        out = tc.extract_citations("Lee (2018a) reported.")
        assert out[0]["year"] == "2018a"
        assert out[0]["citation"] == "Lee (2018a)"

    def test_author_and_coauthor_year(self):
        out = tc.extract_citations("Smith and Jones (2020) found results.")
        assert out[0]["author"] == "Smith and Jones"
        assert out[0]["year"] == "2020"

    def test_et_al_author_year_not_matched(self):
        # CHARACTERIZATION (suspected bug — report only): the docstring
        # claims "Johnson et al. (2019)" is detected, but the optional
        # "et al." branch requires a following capitalized surname, so a
        # plain "Surname et al. (YEAR)" citation is MISSED entirely.
        out = tc.extract_citations("Johnson et al. (2019) agreed.")
        assert out == []

    def test_bracket_citations(self):
        text = "Data shows [1] and [2, 3] across studies."
        out = [c for c in tc.extract_citations(text) if c["type"] == "bracket"]
        assert out == [
            {"type": "bracket", "citation": "[1]", "numbers": "1"},
            {"type": "bracket", "citation": "[2, 3]", "numbers": "2, 3"},
        ]

    def test_numerical_citations(self):
        text = "Results hold (4) and (5, 6) in all cases."
        out = [c for c in tc.extract_citations(text) if c["type"] == "numerical"]
        assert out == [
            {"type": "numerical", "citation": "(4)", "numbers": "4"},
            {"type": "numerical", "citation": "(5, 6)", "numbers": "5, 6"},
        ]

    def test_large_single_number_not_citation(self):
        # Bare (N) with N > 100 is treated as a number, not a citation.
        out = [
            c
            for c in tc.extract_citations("There were (999999) items.")
            if c["type"] == "numerical"
        ]
        assert out == []

    def test_non_numeric_parenthetical_ignored(self):
        assert tc.extract_citations("The value (xyz) is ignored.") == []

    def test_empty(self):
        assert tc.extract_citations("") == []

    def test_all_types_collected_in_order(self):
        text = "Smith (2020) found [1] results (7) overall."
        types = [c["type"] for c in tc.extract_citations(text)]
        assert types == ["author_year", "bracket", "numerical"]


# ═══════════════════════════════════════════════════════════════════════════
# extract_reference_list
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractReferenceList:
    def test_no_section(self):
        assert tc.extract_reference_list("Just body text with no references header.") == []

    @pytest.mark.parametrize(
        "header", ["References", "Bibliography", "Works Cited", "Literature Cited"]
    )
    def test_header_variants(self, header):
        text = f"Body.\n{header}\nAuthor, A. 2020. Some Long Title of a Paper Here.\n"
        refs = tc.extract_reference_list(text)
        assert refs == ["Author, A. 2020. Some Long Title of a Paper Here."]

    def test_markdown_header_variant(self):
        text = "Body.\n## References\nAuthor, A. 2020. Some Long Title of a Paper Here.\n"
        assert tc.extract_reference_list(text) == [
            "Author, A. 2020. Some Long Title of a Paper Here."
        ]

    def test_bracket_references(self):
        text = (
            "Text before.\nReferences\n"
            "[1] Author, A. Title One. Journal, 2020.\n"
            "[2] Writer, B. Title Two. Journal, 2021.\n"
        )
        refs = tc.extract_reference_list(text)
        # CHARACTERIZATION (suspected bug — report only): the first bracketed
        # reference is DROPPED because the split pattern requires "\n[N]" and
        # the first "[1]" sits directly after the consumed header newline.
        assert "[2] Writer, B. Title Two. Journal, 2021." in refs
        assert len(refs) == 1

    def test_line_based_filtering(self):
        # Line-based parsing only runs when NO "\n[N]" bracket lines exist
        # (any bracket line switches to the bracket split).
        text = (
            "Works Cited\n"
            "Author, A. 2020. Some Long Title of a Paper.\n"  # ok (>20 chars, upper)
            "short line\n"  # too short
            "lowercase start of a sufficiently long line here\n"  # lowercase start
            "Bracketed start of a reference line here now.\n"  # ok
        )
        refs = tc.extract_reference_list(text)
        assert refs == [
            "Author, A. 2020. Some Long Title of a Paper.",
            "Bracketed start of a reference line here now.",
        ]

    def test_cap_at_fifty(self):
        lines = "\n".join(
            f"Author{i}, B. 20{i % 10}. Some Long Title of Paper Number {i:02d}." for i in range(60)
        )
        text = f"Body.\nReferences\n{lines}\n"
        assert len(tc.extract_reference_list(text)) == 50


# ═══════════════════════════════════════════════════════════════════════════
# extract_figure_descriptions
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractFigureDescriptions:
    def test_figure_caption(self):
        text = "See Figure 1: Chart showing sales data growth over time."
        out = tc.extract_figure_descriptions(text)
        assert out == [
            {
                "type": "figure",
                "number": "1",
                "description": "Chart showing sales data growth over time.",
            }
        ]

    def test_fig_abbreviation(self):
        text = "As shown in Fig. 7 the pipeline has three separate stages."
        out = tc.extract_figure_descriptions(text)
        assert out[0]["type"] == "figure"
        assert out[0]["number"] == "7"
        assert out[0]["description"].startswith("the pipeline")

    def test_table_caption(self):
        text = "Table 3: Regression results for the model are listed."
        out = tc.extract_figure_descriptions(text)
        assert out[0] == {
            "type": "table",
            "number": "3",
            "description": "Regression results for the model are listed.",
        }

    def test_markdown_image_alt(self):
        text = "Diagram: ![An image description here](img.png) follows."
        out = [f for f in tc.extract_figure_descriptions(text) if f["type"] == "image"]
        assert out == [{"type": "image", "number": "", "description": "An image description here"}]

    def test_short_description_ignored(self):
        # Descriptions must be ≥10 chars.
        assert tc.extract_figure_descriptions("Figure 2: tiny.") == []

    def test_empty(self):
        assert tc.extract_figure_descriptions("") == []

    def test_same_line_captions_greedy(self):
        # CHARACTERIZATION: the figure regex captures [^\n]{10,200} greedily,
        # so a second caption on the SAME line is swallowed into the first
        # description and never extracted separately.
        text = "Figure 1: First caption text here. Figure 2: Second caption text follows."
        out = [f for f in tc.extract_figure_descriptions(text) if f["type"] == "figure"]
        assert len(out) == 1
        assert "Figure 2" in out[0]["description"]


# ═══════════════════════════════════════════════════════════════════════════
# Backward-compat re-exports from text_preprocessor_impl
# ═══════════════════════════════════════════════════════════════════════════


class TestReExports:
    def test_impl_reexports_citation_api(self):
        assert tpi.extract_citations is tc.extract_citations
        assert tpi.extract_reference_list is tc.extract_reference_list
        assert tpi.extract_figure_descriptions is tc.extract_figure_descriptions
        assert tpi._AUTHOR_YEAR_PATTERN is tc._AUTHOR_YEAR_PATTERN
        assert tpi._BRACKET_CITATION_PATTERN is tc._BRACKET_CITATION_PATTERN
        assert tpi._NUMERICAL_CITATION_PATTERN is tc._NUMERICAL_CITATION_PATTERN

    def test_reexported_functions_work(self):
        assert tpi.extract_citations("Smith (2020) wrote.")[0]["author"] == "Smith"
