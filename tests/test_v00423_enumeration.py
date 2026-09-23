"""V0.4.23 — the universal enumeration-capture system (user directive).

> "whether bullet points, a b c d, 1 2 3 4, II IV V VI, create a template
>  for all possible ways that authors and scientists might use in their
>  books, the point is never miss any listed items … for example if they
>  are seven, seven must be captured."

Covers: the ENUMERATION_TEMPLATE catalog, the whole-chapter detector
(every style), the prompt coverage block, the recall-floor probe, and the
ship-time consolidated-bullet guarantee.
"""

from __future__ import annotations

from core.summarisation.enumeration import (
    ENUMERATION_TEMPLATE,
    detect_enumerations,
    enumeration_coverage_block,
    enumeration_item_covered,
    stem_label,
)


def _pad(text: str) -> str:
    """The detector requires >=120 chars of source."""
    return "Introductory prose that sets the scene. " * 4 + "\n\n" + text


class TestTheTemplate:
    def test_template_covers_every_style_family(self):
        expected = {
            "bullet",
            "arabic",
            "arabic_paren",
            "lower_alpha",
            "upper_alpha",
            "lower_alpha_paren",
            "upper_alpha_paren",
            "roman_upper",
            "roman_lower",
            "roman_lower_paren",
            "greek",
            "labeled",
            "outline",
            "runin_arabic",
            "runin_alpha",
            "runin_roman",
            "ordinal",
        }
        assert expected <= set(ENUMERATION_TEMPLATE)


class TestDetectEveryStyle:
    def test_bullets(self):
        src = _pad("Criteria:\n- precision of language\n- verifiability\n- attribution\n")
        enums = detect_enumerations(src)
        assert any(e.style == "bullet" and e.count == 3 for e in enums)

    def test_arabic_block(self):
        src = _pad("The steps:\n1. Extract\n2. Verify\n3. Score\n4. Report\n")
        enums = detect_enumerations(src)
        assert any(e.style == "arabic" and e.count == 4 for e in enums)

    def test_arabic_paren_block(self):
        src = _pad("(1) first consideration\n(2) second consideration\n(3) third item\n")
        enums = detect_enumerations(src)
        assert any(e.style == "arabic_paren" and e.count == 3 for e in enums)

    def test_lower_alpha(self):
        src = _pad("a) paren letter one\nb) paren letter two\nc) paren letter three\n")
        enums = detect_enumerations(src)
        assert any(e.style == "lower_alpha" and e.count == 3 for e in enums)

    def test_upper_alpha(self):
        src = _pad("A. The first distinction\nB. The second\nC. The third one here\n")
        enums = detect_enumerations(src)
        assert any(e.style == "upper_alpha" and e.count == 3 for e in enums)

    def test_roman_lower(self):
        src = _pad("i. roman one here\nii. roman two here\niii. roman three here\n")
        enums = detect_enumerations(src)
        assert any(e.style == "roman_lower" and e.count == 3 for e in enums)

    def test_roman_upper_four(self):
        src = _pad(
            "I. UPPER ROMAN ONE\nII. UPPER ROMAN TWO\nIII. UPPER ROMAN THREE\n"
            "IV. UPPER ROMAN FOUR\n"
        )
        enums = detect_enumerations(src)
        assert any(e.style == "roman_upper" and e.count == 4 for e in enums)

    def test_roman_lower_paren_legal(self):
        src = _pad(
            "(i) the buyer shall deliver\n(ii) the seller shall warrant\n"
            "(iii) the parties shall mediate\n(iv) the clause shall survive\n"
        )
        enums = detect_enumerations(src)
        assert any(e.style == "roman_lower_paren" and e.count == 4 for e in enums)

    def test_greek(self):
        src = _pad(
            "\u03b1. alpha consideration\n\u03b2. beta consideration\n\u03b3. gamma consideration\n"
        )
        enums = detect_enumerations(src)
        assert any(e.style == "greek" and e.count == 3 for e in enums)

    def test_labeled_steps(self):
        src = _pad("Step 1: gather the inputs\nStep 2: run the analysis\nStep 3: emit the report\n")
        enums = detect_enumerations(src)
        assert any(e.style == "labeled" and e.count == 3 for e in enums)

    def test_outline_numbering(self):
        src = _pad(
            "1.1 First subtopic matter\n1.2 Second subtopic matter\n1.3 Third subtopic matter\n"
        )
        enums = detect_enumerations(src)
        assert any(e.style == "outline" and e.count == 3 for e in enums)

    def test_runin_arabic_seven(self):
        """THE user ask: a list of seven must yield seven captured items."""
        src = _pad(
            "The seven characteristics are: (1) selfsameness; (2) temporal "
            "continuity; (3) authenticity; (4) body image; (5) inner "
            "solidity; (6) gender clarity; (7) ethnic solidarity."
        )
        enums = detect_enumerations(src)
        assert any(e.style == "runin_arabic" and e.count == 7 for e in enums), enums

    def test_runin_alpha(self):
        src = _pad(
            "Three options exist: (a) the conservative route; (b) the "
            "moderate route; (c) the radical route."
        )
        enums = detect_enumerations(src)
        assert any(e.style == "runin_alpha" and e.count == 3 for e in enums)

    def test_runin_roman(self):
        src = _pad(
            "The statute provides: (i) a duty of care; (ii) a standard of "
            "review; (iii) a remedy in damages."
        )
        enums = detect_enumerations(src)
        assert any(e.style == "runin_roman" and e.count == 3 for e in enums)

    def test_ordinal_discourse(self):
        src = _pad(
            "First, the theory was proposed. Second, it was tested "
            "broadly. Third, it was revised. Finally, it was accepted."
        )
        enums = detect_enumerations(src)
        assert any(e.style == "ordinal" and e.count == 4 for e in enums)

    def test_non_consecutive_markers_not_a_list(self):
        src = _pad("1. first line here\n3. third line here\n5. fifth line here\n")
        enums = detect_enumerations(src)
        assert not any(e.style == "arabic" for e in enums)

    def test_two_item_sequence_not_a_list(self):
        src = _pad("1. only one\n2. only two\n")
        enums = detect_enumerations(src)
        assert not any(e.style == "arabic" for e in enums)

    def test_mirrored_table_garbage_ignored(self):
        src = _pad(
            "TABLE 4-1. Features\n"
            "010331 TeUOT}BIOA 0\u06f2\u06f2\u06f6 8 \u0645\u0646\u0648\u062f\n"
            "| col | col | col |\n"
            "| a | b | c |\n"
        )
        enums = detect_enumerations(src)
        assert enums == []

    def test_frontmatter_skipped(self):
        src = (
            "---\nstart_page: 77\nend_page: 112\n---\n\n"
            + "Prose introduction repeated. " * 10
            + "\n\n1. first item here\n2. second item here\n3. third item here\n"
        )
        enums = detect_enumerations(src)
        assert any(e.style == "arabic" and e.count == 3 for e in enums)

    def test_blank_lines_between_items(self):
        src = _pad("The list:\n\n1. first item here\n\n2. second item here\n\n3. third item here\n")
        enums = detect_enumerations(src)
        assert any(e.style == "arabic" and e.count == 3 for e in enums)

    def test_wrapped_item_continuation(self):
        src = _pad(
            "1. first item that wraps\nonto a second line\n2. second item here\n3. third item here\n"
        )
        enums = detect_enumerations(src)
        runs = [e for e in enums if e.style == "arabic"]
        assert runs and runs[0].count == 3
        assert "onto a second line" in runs[0].items[0].text

    def test_never_raises(self):
        assert detect_enumerations("") == []
        assert detect_enumerations(None) == []  # type: ignore[arg-type]
        assert detect_enumerations("x" * 50) == []


class TestCoverageBlock:
    def test_block_states_the_contract(self):
        src = _pad(
            "The seven characteristics are: (1) selfsameness; (2) temporal "
            "continuity; (3) authenticity; (4) body image; (5) inner "
            "solidity; (6) gender clarity; (7) ethnic solidarity."
        )
        blk = enumeration_coverage_block(src)
        assert "ENUMERATED-LIST COVERAGE" in blk
        assert "all seven must be" in blk
        assert "selfsameness" in blk
        assert "ethnic solidarity" in blk

    def test_block_empty_when_no_lists(self):
        assert enumeration_coverage_block(_pad("Plain prose only. " * 30)) == ""

    def test_block_budget_degrades_gracefully(self):
        many = "\n\n".join(
            f"The set {i}: (1) alpha item {i}; (2) beta item {i}; (3) gamma item {i}."
            for i in range(30)
        )
        blk = enumeration_coverage_block(_pad(many), budget_chars=800)
        assert "reproduce ALL" in blk  # degraded tails keep the contract
        assert len(blk) < 8000


class TestItemCoverage:
    def test_verbatim_and_paraphrase_cover(self):
        hay = "the summary mentions selfsameness and temporal continuity of the self"
        assert enumeration_item_covered("selfsameness", hay)
        assert enumeration_item_covered("temporal continuity", hay)
        assert not enumeration_item_covered("ethnic solidarity", hay)

    def test_empty_item_counts_covered(self):
        assert enumeration_item_covered("", "")
        assert enumeration_item_covered("ab cd", "")


class TestStemLabel:
    def test_label_from_stem(self):
        assert stem_label("The seven features of solid identity are:", 7) == (
            "Seven features of solid identity"
        )
        assert stem_label("", 3) == "Enumerated list (3 items)"


class TestRecallFloorProbe:
    def test_enumeration_keys(self):
        from core.summarisation.recall_floor import deterministic_recall_floor

        src = _pad(
            "The seven characteristics are: (1) selfsameness; (2) temporal "
            "continuity; (3) authenticity; (4) body image; (5) inner "
            "solidity; (6) gender clarity; (7) ethnic solidarity."
        )
        floor = deterministic_recall_floor(
            analysis="",
            bullets=["Mentions selfsameness and temporal continuity and authenticity."],
            thorough="Also body image and inner solidity appear in the thorough.",
            source_text=src,
        )
        assert floor["enumerations_total"] == 7
        assert floor["enumerations_covered"] == 5
        assert len(floor["enumerations_missing"]) == 2
        assert any("enumerated items" in p for p in floor["log_parts"])


class TestShipTimeGuarantee:
    """_ensure_enumeration_bullets: 'if they are seven, seven must be
    captured' — any list with an uncovered item gets ONE consolidated
    bullet carrying ALL items; fully covered lists add nothing."""

    def _mixin(self):
        from core.summarisation.additive_sections import SummarizerAdditiveMixin

        logs: list[tuple[str, str]] = []

        class _S(SummarizerAdditiveMixin):
            def log(self, msg, level="INFO"):
                logs.append((level, msg))

        return _S(), logs

    SRC = _pad(
        "The seven characteristics are: (1) selfsameness; (2) temporal "
        "continuity; (3) authenticity; (4) body image; (5) inner "
        "solidity; (6) gender clarity; (7) ethnic solidarity."
    )

    def test_missing_item_forces_the_consolidated_bullet(self):
        s, logs = self._mixin()
        result = {
            "bullet_points": [
                "Covers selfsameness, temporal continuity, authenticity, "
                "body image, inner solidity, and gender clarity."
            ],
            "thorough_summary": "",
        }
        s._ensure_enumeration_bullets("Chapter", self.SRC, result)
        added = [b for b in result["bullet_points"] if b.startswith("**")]
        assert len(added) == 1
        # ALL seven items carried verbatim — seven captured, not six
        for item in (
            "selfsameness",
            "temporal continuity",
            "authenticity",
            "body image",
            "inner solidity",
            "gender clarity",
            "ethnic solidarity",
        ):
            assert item in added[0], item
        assert "(7) ethnic solidarity" in added[0]
        assert any("enumeration guarantee" in m for _lvl, m in logs)

    def test_fully_covered_list_adds_nothing(self):
        s, logs = self._mixin()
        result = {
            "bullet_points": [
                "The seven characteristics are selfsameness, temporal "
                "continuity, authenticity, body image, inner solidity, "
                "gender clarity, and ethnic solidarity."
            ],
            "thorough_summary": "",
        }
        n_before = len(result["bullet_points"])
        s._ensure_enumeration_bullets("Chapter", self.SRC, result)
        assert len(result["bullet_points"]) == n_before

    def test_conclusion_bullet_covers_the_list(self):
        """The V18.15.9.1 consolidated conclusion bullet (verbatim items)
        already covers the list — the guarantee is a no-op (no double
        bullet)."""
        s, _logs = self._mixin()
        result = {
            "bullet_points": [
                "**Characteristics**: (1) selfsameness; (2) temporal "
                "continuity; (3) authenticity; (4) body image; (5) inner "
                "solidity; (6) gender clarity; (7) ethnic solidarity."
            ],
            "thorough_summary": "",
        }
        n_before = len(result["bullet_points"])
        s._ensure_enumeration_bullets("Chapter", self.SRC, result)
        assert len(result["bullet_points"]) == n_before

    def test_no_lists_no_op(self):
        s, _logs = self._mixin()
        result = {"bullet_points": ["One bullet."], "thorough_summary": ""}
        s._ensure_enumeration_bullets("Chapter", _pad("Plain prose. " * 30), result)
        assert result["bullet_points"] == ["One bullet."]

    def test_never_raises(self):
        s, _logs = self._mixin()
        result = {"bullet_points": [], "thorough_summary": ""}
        s._ensure_enumeration_bullets("Chapter", None, result)  # type: ignore[arg-type]
        assert result["bullet_points"] == []
