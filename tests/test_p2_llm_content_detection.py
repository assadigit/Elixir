"""Phase 2 (Test-Net Deepening) — ``content_detector`` + ``content_presets``.

Baselines: content_detector.py 47/161 missed (71%),
content_presets.py 27/68 missed (60%).

Pure-Python heuristics — fully hermetic by construction (no I/O at all).
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from core.llm.content_detector import DetectionResult, detect_content_type  # noqa: E402
from core.llm.content_presets import (  # noqa: E402
    ContentPreset,
    detect_scanned_pdf,
    detect_source_type,
    get_all_presets,
    get_content_preset,
)


def _pad(text: str, min_len: int = 400) -> str:
    """Pad heuristic input past the detector's minimum-length gates."""
    if len(text) >= min_len:
        return text
    return text + " " + "filler prose. " * (min_len // 14 + 1)


# ════════════════════════════════════════════════════════════════════════════
# content_detector — detect_content_type
# ════════════════════════════════════════════════════════════════════════════


class TestDetectContentTypeGates:
    def test_empty_text_short_circuit(self):
        result = detect_content_type("")
        assert result.content_type == "normal_book"
        assert result.confidence == 0.0
        assert result.scores == {"normal_book": 1.0}
        assert result.signals["normal_book"] == "insufficient text for detection"
        assert result.recommended is False

    def test_short_text_short_circuit(self):
        result = detect_content_type("too short " * 5)
        assert result.content_type == "normal_book"
        assert result.recommended is False


class TestDetectContentTypeScanned:
    def test_high_scan_ratio_scores_scanned(self):
        text = _pad("plain book prose without special signals at all. ")
        result = detect_content_type(text, total_pages=10, scanned_page_count=9)
        assert result.scores["scanned_pdf"] == 10.0
        assert "9/10 pages scanned (90%)" in result.signals["scanned_pdf"]

    def test_low_scan_ratio_not_flagged(self):
        text = _pad("plain book prose without special signals at all. ")
        result = detect_content_type(text, total_pages=10, scanned_page_count=1)
        assert result.scores["scanned_pdf"] == 0.0
        assert "only 10% scanned" in result.signals["scanned_pdf"]

    def test_no_scan_data(self):
        text = _pad("plain book prose without special signals at all. ")
        result = detect_content_type(text, total_pages=0, scanned_page_count=0)
        assert result.scores["scanned_pdf"] == 0.0
        assert result.signals["scanned_pdf"] == "no scan data"


class TestDetectAcademicPaper:
    ACADEMIC = (
        "Abstract. We test the hypothesis empirically. "
        "Prior work (Smith, 2020), (Lee, 2021) and (Brown, 2022) agree; see DOI 10.1016/x.foo "
        "and 10.1007/y.bar. The result was statistically significant (p < 0.05).\n"
        "1.1 Introduction\n1.2 Methods\n2.3 Results\n3.4 Discussion\n4.5 Conclusion\n"
        "Elsevier ScienceDirect Springer Wiley IEEE Nature ScienceDirect.\n"
        "Received: 2020-01-01\nAccepted: 2020-02-01\nPublished: 2020-03-01\n"
        "methodology, hypothesis, empirical, qualitative. "
    )

    def test_academic_signals(self):
        result = detect_content_type(_pad(self.ACADEMIC))
        assert result.scores["academic_paper"] > 2.0
        sig = result.signals["academic_paper"]
        assert "citations" in sig
        assert "DOI(s)" in sig
        assert "p-value" in sig
        assert "numbered sections" in sig
        assert "has abstract" in sig
        assert "academic keywords" in sig
        assert "publisher marker(s)" in sig
        assert "known DOI prefix(es)" in sig
        assert "submission metadata fields" in sig

    def test_academic_beats_normal_book(self):
        result = detect_content_type(_pad(self.ACADEMIC))
        assert result.content_type == "academic_paper"
        assert result.recommended is True


class TestDetectSelfHelp:
    SELF_HELP = (
        "Transform your life and empower yourself to achieve your goals.\n"
        "Exercise: write your thoughts.\nTry this: breathe deeply.\nAction item: call a friend.\n"
        "Your journey to success starts with a breakthrough mindset. Step-by-step practice. "
    )

    def test_self_help_signals(self):
        result = detect_content_type(_pad(self.SELF_HELP))
        assert result.scores["self_help"] > 1.0
        sig = result.signals["self_help"]
        assert "exercise callouts" in sig
        assert "motivational keywords" in sig

    def test_no_self_help_signals(self):
        result = detect_content_type(_pad("dry technical reference material."))
        assert result.scores["self_help"] == 0.0
        assert result.signals["self_help"] == "no self-help signals"


class TestDetectPhilosophy:
    PHILOSOPHY = (
        "Epistemology and metaphysics address the ontological question. "
        "Phenomenology, existentialism, nihilism and determinism frame the dialectic. "
        "Nietzsche, Kant, Hegel, Sartre and Aristotle disagree on virtue ethics "
        "and the categorical imperative versus moral relativism and deontology. "
    )

    def test_philosophy_signals(self):
        result = detect_content_type(_pad(self.PHILOSOPHY))
        assert result.scores["philosophy"] > 1.0
        sig = result.signals["philosophy"]
        assert "philosophical terms" in sig
        assert "philosopher names" in sig

    def test_no_philosophy_signals(self):
        result = detect_content_type(_pad("plain cookbook recipes and ingredients."))
        assert result.scores["philosophy"] == 0.0
        assert result.signals["philosophy"] == "no philosophy signals"


class TestDetectCatalogue:
    CATALOGUE = (
        "Widget A $19.99, Widget B $29.99, Widget C $39.99, Widget D $49.99, "
        "Widget E $59.99.\n"
        "SKU-1001\nSKU-1002\nSKU-1003.\n"
        "Specifications: 12V, 2A, 300mm x 200mm. Add to cart — in stock, free shipping. "
    )

    def test_catalogue_signals(self):
        result = detect_content_type(_pad(self.CATALOGUE))
        assert result.scores["catalogue"] > 1.0
        sig = result.signals["catalogue"]
        assert "prices" in sig
        assert "product codes" in sig
        assert "has specifications" in sig

    def test_no_catalogue_signals(self):
        result = detect_content_type(_pad("a narrative story about a long journey."))
        assert result.scores["catalogue"] == 0.0
        assert result.signals["catalogue"] == "no catalogue signals"


class TestDetectMagazine:
    def test_magazine_keywords(self):
        text = _pad(
            "The cover story of this issue: our staff photographer shot a photo essay. "
            "A special feature interview with the editor-in-chief. Volume 12, issue 3. "
        )
        result = detect_content_type(text)
        assert result.scores["magazine"] > 0.0
        assert "magazine keywords" in result.signals["magazine"]

    def test_no_magazine_signals(self):
        result = detect_content_type(_pad("continuous dense prose with no keywords."))
        assert result.signals["magazine"] == "no magazine signals"

    def test_short_line_density_signal(self):
        text = "The issue and volume of this magazine. " + "\n".join(
            f"Caption {i} — a photo" for i in range(60)
        )
        result = detect_content_type(text)
        assert "high short-line density" in result.signals["magazine"]


class TestNormalBookBaseline:
    def test_prose_wins_by_default(self):
        # Long unbroken prose (no newlines) → high avg line length signal.
        prose = "This is a long flowing narrative sentence about ideas. " * 30
        result = detect_content_type(prose)
        assert result.content_type == "normal_book"
        assert result.scores["normal_book"] >= 2.0
        assert "long average line length" in result.signals["normal_book"]
        assert result.recommended is True

    def test_result_helpers(self):
        prose = "This is a long flowing narrative sentence about ideas. " * 30
        result = detect_content_type(prose)
        assert isinstance(result, DetectionResult)
        assert result.label() == "Non-Fiction Book"
        assert "Non-Fiction Book" in result.explanation()
        assert "confidence" in result.explanation()

    def test_label_unknown_type_falls_back(self):
        r = DetectionResult(
            content_type="weird", confidence=0.5, scores={}, signals={}, recommended=False
        )
        assert r.label() == "weird"

    def test_scanned_pdf_label(self):
        r = DetectionResult(
            content_type="scanned_pdf", confidence=0.9, scores={}, signals={}, recommended=True
        )
        assert r.label() == "Scanned PDF (OCR)"


# ════════════════════════════════════════════════════════════════════════════
# content_presets — detect_source_type / presets / detect_scanned_pdf
# ════════════════════════════════════════════════════════════════════════════


class TestDetectSourceType:
    def test_empty_text_returns_normal(self):
        assert detect_source_type("") == "normal_book"

    def test_short_text_returns_normal(self):
        assert detect_source_type("too short") == "normal_book"

    def test_academic_paper(self):
        text = _pad(
            "The abstract outlines our methodology and hypothesis. "
            "Prior work et al. in the Journal of Important Studies. "
            "DOI and arXiv references, proceedings, citations. "
            "Empirical qualitative quantitative regression analysis, p < 0.05, "
            "statistically significant. ",
            min_len=600,
        )
        assert detect_source_type(text) == "academic_paper"

    def test_self_help(self):
        text = _pad(
            "Transform your mindset. Empower yourself. Achieve your goals. "
            "Exercise: reflect. Try this: journal. Action item: plan. "
            "Motivation and success through breakthrough habits on your journey. ",
            min_len=600,
        )
        assert detect_source_type(text) == "self_help"

    def test_philosophy(self):
        text = _pad(
            "Epistemology and metaphysics; the ontological and phenomenological method. "
            "Existentialism, nihilism, determinism, a priori, dialectic, syllogism. "
            "The categorical imperative, moral relativism, virtue ethics, deontology. "
            "Nietzsche, Kant, Hegel, Sartre, Aristotle. ",
            min_len=600,
        )
        assert detect_source_type(text) == "philosophy"

    def test_plain_prose_returns_normal(self):
        text = _pad(
            "The factory produced widgets every day and the workers went home tired. "
            "Nothing motivational, academic or philosophical happens here. ",
            min_len=600,
        )
        assert detect_source_type(text) == "normal_book"


class TestPresets:
    def test_all_seven_presets_registered(self):
        presets = get_all_presets()
        assert set(presets) == {
            "normal_book",
            "academic_paper",
            "self_help",
            "philosophy",
            "catalogue",
            "magazine",
            "scanned_pdf",
        }
        assert all(isinstance(p, ContentPreset) for p in presets.values())

    def test_get_preset_known(self):
        p = get_content_preset("academic_paper")
        assert p.name == "academic_paper"
        assert p.preserve_domain_terms is True

    def test_get_preset_unknown_falls_back_to_normal(self):
        p = get_content_preset("mystery-type")
        assert p.name == "normal_book"

    def test_preset_defaults(self):
        p = get_content_preset("normal_book")
        assert p.recommended_outputs == ["chapter_summaries", "keypoints"]
        assert p.force_ocr_all_pages is False

    def test_catalogue_preset_flags(self):
        p = get_content_preset("catalogue")
        assert p.skip_summaries is True
        assert p.extract_images is True
        assert p.recommended_outputs == ["full_markdown", "screenshots"]

    def test_magazine_preset_flags(self):
        p = get_content_preset("magazine")
        assert p.skip_summaries is False
        assert p.extract_images is True
        assert p.narrative_filter_strictness == "lenient"

    def test_scanned_preset_forces_ocr(self):
        p = get_content_preset("scanned_pdf")
        assert p.force_ocr_all_pages is True

    def test_returned_dict_is_a_copy(self):
        presets = get_all_presets()
        presets.pop("normal_book")
        assert "normal_book" in get_all_presets()


class TestDetectScannedPdf:
    @pytest.mark.parametrize(
        ("scanned", "total", "expected"),
        [
            (0, 0, False),  # unknown page count → never scanned
            (0, 10, False),
            (6, 10, True),  # 60% exactly
            (5, 10, False),  # below threshold
            (10, 10, True),
        ],
    )
    def test_threshold(self, scanned, total, expected):
        assert detect_scanned_pdf(scanned, total) is expected
