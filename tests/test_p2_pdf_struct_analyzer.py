"""Phase 2 (Test-Net Deepening) — hermetic tests for ``core/pdf/analyzer.py``.

PdfAnalyzer decides the OCR strategy from per-page text quality:
>= 30% scanned -> LLM_OCR, 1-29% -> HYBRID, 0% -> NO_OCR.

Real PDFs are built with fitz (text pages, image-only pages, encrypted pages,
0-page documents via pypdf's PdfWriter). ``docling`` (optional dep) is absent
here — its import probe is exercised both ways (missing + stubbed present).
"""

from __future__ import annotations

import io
import sys
import types
from pathlib import Path


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    ``test_chapter_matcher_robust`` (and friends) install MagicMock stubs for
    heavy optional deps at collection time and never remove them; collection
    is alphabetical, so the stubs are already in place when this file is
    imported and would poison ``core.pdf.analyzer``'s own module-level
    ``from pypdf import PdfReader`` binding. Real modules are
    ``types.ModuleType`` instances — MagicMocks are not — so drop them BEFORE
    any pypdf-dependent import below and let those imports resolve the real
    installed packages.
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pypdf")
_ensure_real_module("PIL")

import fitz  # noqa: E402 — after stub cleanup
import pytest  # noqa: E402 — after stub cleanup
from pypdf import PdfReader, PdfWriter  # noqa: E402 — after stub cleanup
from pypdf.errors import PdfReadError  # noqa: E402 — after stub cleanup

import core.pdf.analyzer as _analyzer_module  # noqa: E402 — after stub cleanup
from core.models import PdfRecommendation  # noqa: E402 — after stub cleanup
from core.pdf.analyzer import EmptyPdfError, PdfAnalyzer  # noqa: E402 — after stub cleanup

# Repair a production binding that the stub cleanup above came too late for:
# ``test_chapter_matcher_robust`` installs the pypdf MagicMock BEFORE its own
# ``core.segmentation`` import, which transitively executes
# ``core/pdf/__init__.py`` -> ``core.pdf.analyzer`` while pypdf is still
# mocked — so the production module's module-level ``from pypdf import
# PdfReader`` bound a MagicMock for the rest of the session (every analyze()
# call then saw an "encrypted, 0-page" PDF). These tests are the first in the
# suite to exercise analyze() against real PDFs, so swap the real class back
# in (no reload needed — the class itself was defined correctly, only the
# pypdf name was poisoned).
if not isinstance(_analyzer_module.PdfReader, type):
    _analyzer_module.PdfReader = PdfReader

RICH = "A sufficiently long line of real extractable text for the analyzer to consider"


def _write(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


def _text_pdf(tmp_path: Path, n_pages: int = 3, name: str = "text.pdf") -> Path:
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page(width=612, height=792)
        y = 60
        for _ in range(6):
            page.insert_text((50, y), RICH, fontname="cour", fontsize=11)
            y += 16
    return _write(doc, tmp_path, name)


def _mixed_pdf(tmp_path: Path, n_text: int, n_blank: int, name: str = "mixed.pdf") -> Path:
    doc = fitz.open()
    for _ in range(n_text):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), RICH, fontname="cour", fontsize=11)
    for _ in range(n_blank):
        doc.new_page(width=612, height=792)  # no text -> "scanned"
    return _write(doc, tmp_path, name)


# ── _is_text_meaningful ─────────────────────────────────────────────────────


class TestIsTextMeaningful:
    def setup_method(self):
        self.analyzer = PdfAnalyzer()

    def test_empty_text(self):
        assert self.analyzer._is_text_meaningful("") is False
        assert self.analyzer._is_text_meaningful("   ") is False

    def test_short_text_with_too_few_words(self):
        assert self.analyzer._is_text_meaningful("ab") is False

    def test_short_all_caps_rejected(self):
        assert self.analyzer._is_text_meaningful("AB CD") is False

    def test_short_text_below_min_chars_rejected(self):
        # 2+ words but under the 30-char floor
        assert self.analyzer._is_text_meaningful("Hello World Foo") is False

    def test_short_text_with_two_words_and_enough_length(self):
        # under SCANNED_THRESHOLD (30) but >= MIN_TEXT_CHARS (30) with >= 2 words
        assert self.analyzer._is_text_meaningful("one two three four five six seven") is True

    def test_garbage_punctuation_rejected(self):
        # >= 30 chars so the short-text branch is skipped; garbage runs must
        # exceed 30% of the text length
        assert self.analyzer._is_text_meaningful("############ alpha beta gamma delta") is False
        assert self.analyzer._is_text_meaningful("!!!!!!!!!!!! more junk words here") is False

    def test_modest_punctuation_still_accepted(self):
        assert (
            self.analyzer._is_text_meaningful("some real prose with a single ! mark in it") is True
        )

    def test_normal_text_accepted(self):
        assert self.analyzer._is_text_meaningful(RICH) is True

    def test_mixed_script_words_counted(self):
        # Persian word pattern alternative in the word regex (>= 30 chars)
        persian = "کتاب خوب است اینجا و متن کافی لازم است"
        assert self.analyzer._is_text_meaningful(persian) is True


# ── analyze_page ────────────────────────────────────────────────────────────


class TestAnalyzePage:
    def test_text_page_is_not_scanned(self, tmp_path):
        analyzer = PdfAnalyzer()
        reader = PdfReader(str(_text_pdf(tmp_path)))
        result = analyzer.analyze_page(reader.pages[0], 1)
        assert result.page_num == 1
        assert result.is_scanned is False
        assert result.recommended_action == "skip"
        assert result.extracted_text_preview.startswith("A sufficiently")

    def test_blank_page_is_scanned(self, tmp_path):
        analyzer = PdfAnalyzer()
        path = _mixed_pdf(tmp_path, n_text=0, n_blank=1, name="blank.pdf")
        reader = PdfReader(str(path))
        result = analyzer.analyze_page(reader.pages[0], 1)
        assert result.is_scanned is True
        assert result.recommended_action == "ocr"
        assert result.extracted_text_preview == ""

    def test_extraction_exception_marks_scanned(self):
        analyzer = PdfAnalyzer()

        class _BoomPage:
            def extract_text(self):
                raise RuntimeError("cannot extract")

        result = analyzer.analyze_page(_BoomPage(), 7)
        assert result.is_scanned is True
        assert result.page_num == 7

    def test_preview_is_truncated_to_200_chars(self, tmp_path):
        analyzer = PdfAnalyzer()
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(
            (50, 60),
            "word " * 200,  # long line -> preview must be cut at 200 chars
            fontname="cour",
            fontsize=11,
        )
        path = _write(doc, tmp_path, "long.pdf")
        reader = PdfReader(str(path))
        result = analyzer.analyze_page(reader.pages[0], 1)
        assert len(result.extracted_text_preview) <= 200


# ── analyze (whole-document) ────────────────────────────────────────────────


class TestAnalyze:
    def test_all_text_pages_recommend_no_ocr(self, tmp_path):
        analyzer = PdfAnalyzer()
        result = analyzer.analyze(_text_pdf(tmp_path, n_pages=4))
        assert result.total_pages == 4
        assert result.scanned_pages == []
        assert result.text_pages == [1, 2, 3, 4]
        assert result.recommendation == PdfRecommendation.NO_OCR
        assert len(result.per_page) == 4
        assert all(not p.is_scanned for p in result.per_page)

    def test_one_blank_of_five_pages_recommend_hybrid(self, tmp_path):
        analyzer = PdfAnalyzer()
        result = analyzer.analyze(_mixed_pdf(tmp_path, n_text=4, n_blank=1))
        assert result.scanned_pages == [5]
        assert result.recommendation == PdfRecommendation.HYBRID

    def test_all_blank_pages_recommend_llm_ocr(self, tmp_path):
        analyzer = PdfAnalyzer()
        result = analyzer.analyze(_mixed_pdf(tmp_path, n_text=0, n_blank=3))
        assert result.scanned_pages == [1, 2, 3]
        assert result.recommendation == PdfRecommendation.LLM_OCR

    def test_majority_blank_recommend_llm_ocr(self, tmp_path):
        # 2 of 3 pages blank -> ratio 0.67 >= 0.30 -> LLM_OCR
        analyzer = PdfAnalyzer()
        result = analyzer.analyze(_mixed_pdf(tmp_path, n_text=1, n_blank=2))
        assert result.recommendation == PdfRecommendation.LLM_OCR

    def test_zero_page_pdf_raises_empty_pdf_error(self, tmp_path):
        writer = PdfWriter()
        buf = io.BytesIO()
        writer.write(buf)
        path = tmp_path / "empty.pdf"
        path.write_bytes(buf.getvalue())
        assert len(PdfReader(str(path)).pages) == 0
        with pytest.raises(EmptyPdfError, match="0 pages"):
            PdfAnalyzer().analyze(path)

    def test_corrupt_pdf_raises(self, tmp_path):
        bad = tmp_path / "garbage.pdf"
        bad.write_bytes(b"not a pdf")
        with pytest.raises(PdfReadError):
            PdfAnalyzer().analyze(bad)

    def test_encrypted_without_password_crashes(self, tmp_path):
        # CHARACTERIZATION (suspected bug, reported not fixed): the warning
        # "PDF is encrypted but no password provided" is logged, but the very
        # next statement (len(reader.pages)) is outside the try/except and
        # raises FileNotDecryptedError instead of a clean EmptyPdfError-style
        # failure.
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), RICH, fontname="cour", fontsize=11)
        path = tmp_path / "enc.pdf"
        path.write_bytes(
            doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
        )
        with pytest.raises(Exception, match="[Dd]ecrypt"):
            PdfAnalyzer().analyze(path)

    def test_encrypted_with_password_analyzed(self, tmp_path):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 60), RICH, fontname="cour", fontsize=11)
        path = tmp_path / "enc2.pdf"
        path.write_bytes(
            doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
        )
        result = PdfAnalyzer(password="u").analyze(path)
        assert result.recommendation == PdfRecommendation.NO_OCR
        assert result.total_pages == 1

    def test_docling_probe_reports_unavailable(self, tmp_path):
        # docling is not installed in this environment -> probe stays False
        analyzer = PdfAnalyzer()
        analyzer.analyze(_text_pdf(tmp_path, n_pages=1, name="probe.pdf"))
        assert analyzer._docling_available is False

    def test_docling_probe_with_stubbed_module(self, tmp_path, monkeypatch):
        stub = types.ModuleType("docling")
        monkeypatch.setitem(sys.modules, "docling", stub)
        analyzer = PdfAnalyzer()
        analyzer.analyze(_text_pdf(tmp_path, n_pages=1, name="probe2.pdf"))
        assert analyzer._docling_available is True


# ── get_pages_to_ocr ────────────────────────────────────────────────────────


class TestGetPagesToOcr:
    def _analysis(self, tmp_path, n_text, n_blank):
        return PdfAnalyzer().analyze(_mixed_pdf(tmp_path, n_text=n_text, n_blank=n_blank))

    def test_no_ocr_returns_empty(self, tmp_path):
        analysis = self._analysis(tmp_path, 3, 0)
        assert PdfAnalyzer().get_pages_to_ocr(analysis) == []

    def test_llm_ocr_returns_all_pages(self, tmp_path):
        analysis = self._analysis(tmp_path, 0, 3)
        assert PdfAnalyzer().get_pages_to_ocr(analysis) == [1, 2, 3]

    def test_hybrid_returns_scanned_only(self, tmp_path):
        analysis = self._analysis(tmp_path, 4, 1)
        assert PdfAnalyzer().get_pages_to_ocr(analysis) == [5]

    def test_user_override_no_ocr_wins(self, tmp_path):
        analysis = self._analysis(tmp_path, 0, 3)  # would be LLM_OCR
        result = PdfAnalyzer().get_pages_to_ocr(analysis, user_override=PdfRecommendation.NO_OCR)
        assert result == []

    def test_user_override_llm_ocr_wins(self, tmp_path):
        analysis = self._analysis(tmp_path, 3, 0)  # would be NO_OCR
        result = PdfAnalyzer().get_pages_to_ocr(analysis, user_override=PdfRecommendation.LLM_OCR)
        assert result == [1, 2, 3]

    def test_user_override_hybrid_wins(self, tmp_path):
        analysis = self._analysis(tmp_path, 3, 0)  # no scanned pages at all
        result = PdfAnalyzer().get_pages_to_ocr(analysis, user_override=PdfRecommendation.HYBRID)
        assert result == []

    def test_unknown_recommendation_returns_empty(self, tmp_path):
        analysis = self._analysis(tmp_path, 3, 0)

        class _FakeRec:
            value = "something_else"

            def __eq__(self, other):
                return False

            def __ne__(self, other):
                return True

        analysis.recommendation = _FakeRec()
        assert PdfAnalyzer().get_pages_to_ocr(analysis) == []
