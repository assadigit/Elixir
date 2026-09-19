"""Phase 2 (Test-Net Deepening) — hermetic tests for ``core/pdf/toc_extractor.py``.

Covers the adaptive extraction pipeline of ``TocExtractor`` against REAL
in-memory PDFs built with PyMuPDF (fitz):

* PDF outline (bookmark) extraction via pypdf (``doc.set_toc``),
* the adaptive stages (LLM semantic extraction, statistical clustering),
* the rule-based fallback (rendered "Contents" pages with dotted leaders),
* the Vision-OCR branch (ModelManager/QwenOCREngine mocked at their
  boundaries — no model is loaded),
* page-text extraction with OCR fallbacks,
* encrypted / corrupt / 0-page PDFs.

Only the LLM HTTP transport (``session_for_url``) and the vision-model
machinery are mocked; all parsing/matching logic is the real production code.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import fitz
import pytest

import core.pdf.toc_extractor as toc_mod
from core.pdf.toc_extractor import TocExtractor


def _ensure_real_module(name: str) -> None:
    """Swap a persistent MagicMock stub in ``sys.modules`` for the real package.

    ``test_chapter_matcher_robust`` (and friends) install MagicMock stubs for
    heavy optional deps (pypdf/pytesseract/pdf2image/docx/...) at collection time
    and never remove them; collection is alphabetical, so those stubs are
    already in place when this file is imported — they would break the
    ``pypdf.errors`` submodule import below (real pypdf probes PIL.__version__),
    and the docx stub would crash the PromptManager import inside the LLM
    stage (``from docx.shared import ...`` on a mock raises AttributeError).
    Real modules are ``types.ModuleType`` instances — MagicMocks are not — so
    drop them and let the late imports below resolve the real installed
    packages (all of them are core requirements).
    """
    mod = sys.modules.get(name)
    if mod is not None and not isinstance(mod, types.ModuleType):
        for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
            del sys.modules[key]


_ensure_real_module("pypdf")
_ensure_real_module("pytesseract")
_ensure_real_module("pdf2image")
_ensure_real_module("PIL")  # real pypdf probes PIL.__version__ at import
_ensure_real_module("docx")  # PromptManager chain imports docx.shared
from pypdf import PdfReader  # noqa: E402 — after stub cleanup
from pypdf.errors import FileNotDecryptedError  # noqa: E402 — after stub cleanup

# ────────────────────────────────────────────────────────────────────────────
# Helpers — fitz PDF factory + stubs
# ────────────────────────────────────────────────────────────────────────────

_LONG_BODY_LINE = (
    "this is a plain lowercase filler body line without any digits or chapter "
    "keywords padding words padding words padding words padding words padding"
)


class _StubSettings:
    """Deterministic replacement for the real Settings singleton."""

    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}

    def get(self, path, default=None):
        return self.overrides.get(path, default)

    def get_ollama_url(self):
        return self.overrides.get("ollama_url", "http://localhost:11434")


def _make_extractor(
    adaptive: bool = False,
    settings: dict | None = None,
) -> tuple[TocExtractor, list[tuple[str, str]]]:
    logs: list[tuple[str, str]] = []
    ex = TocExtractor(log_callback=lambda msg, level="INFO": logs.append((level, msg)))
    ex._settings = _StubSettings(settings or {})
    ex._adaptive_enabled = adaptive
    ex._llm_model = "test-model:latest"
    ex._ollama_base_url = "http://localhost:11434"
    return ex, logs


def _write_pdf(doc: fitz.Document, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(doc.tobytes())
    return path


def _bookmarked_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    for _ in range(4):
        doc.new_page(width=612, height=792)
    doc.set_toc(
        [
            [1, "Chapter One", 1],
            [2, "Section One A", 2],
            [1, "Chapter Two", 3],
            [1, "Chapter One", 1],  # duplicate -> must be deduplicated
        ]
    )
    return _write_pdf(doc, tmp_path, "bookmarked.pdf")


def _dotted_toc_pdf(tmp_path: Path) -> Path:
    """A rendered 'Contents' page with dotted leader lines + 9 body pages."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
    entries = [
        "1. Introduction .......... 3",
        "2. Methods .......... 5",
        "3. Results and Discussion .......... 7",
        "4. Conclusion .......... 9",
    ]
    y = 90
    for line in entries:
        page.insert_text((50, y), line, fontname="cour", fontsize=11)
        y += 20
    for i in range(9):
        pg = doc.new_page(width=612, height=792)
        yy = 60
        for _ in range(4):
            pg.insert_text((50, yy), _LONG_BODY_LINE, fontname="cour", fontsize=10)
            yy += 16
        if i == 1:
            # Distinctive marker on page 3 (index 2) — must never be collected
            # because the body-page break triggers at page 2 (index 1).
            pg.insert_text((50, yy), "zzz marker page three zzz", fontname="cour", fontsize=10)
    return _write_pdf(doc, tmp_path, "dotted_toc.pdf")


def _many_entries_toc_pdf(tmp_path: Path) -> Path:
    """Dotted-leader TOC page with 8 entries + 10 body pages (pages 3..10)."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
    y = 90
    for i in range(1, 9):  # 8 entries -> log truncates after the first 6
        page.insert_text(
            (50, y),
            f"{i}. Chapter Topic Number {i} .......... {i + 2}",
            fontname="cour",
            fontsize=11,
        )
        y += 20
    for _ in range(10):
        pg = doc.new_page(width=612, height=792)
        yy = 60
        for _ in range(4):
            pg.insert_text((50, yy), _LONG_BODY_LINE, fontname="cour", fontsize=10)
            yy += 16
    return _write_pdf(doc, tmp_path, "many_entries_toc.pdf")


def _roman_low_score_pdf(tmp_path: Path) -> Path:
    """Roman-numeral TOC entries; one maps beyond the 5-page document."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
    y = 90
    for line in ["I. Valid Roman Title", "II. Another Roman Heading", "IX. Out Of Range Header"]:
        page.insert_text((50, y), line, fontname="cour", fontsize=11)
        y += 20
    for _ in range(4):
        pg = doc.new_page(width=612, height=792)
        yy = 60
        for _ in range(4):
            pg.insert_text((50, yy), _LONG_BODY_LINE, fontname="cour", fontsize=10)
            yy += 16
    return _write_pdf(doc, tmp_path, "roman_low.pdf")


def _roman_labels_pdf(tmp_path: Path) -> Path:
    """6-page PDF with lowercase-roman page labels i..vi and a roman TOC page."""
    doc = fitz.open()
    for _ in range(6):
        doc.new_page(width=612, height=792)
    doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1}])
    page = doc[0]
    page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
    y = 90
    for line in [
        "I. Alpha Preface Section",
        "II. Beta Preface Section",
        "III. Gamma Preface Section",
    ]:
        page.insert_text((50, y), line, fontname="cour", fontsize=11)
        y += 20
    return _write_pdf(doc, tmp_path, "roman_labels.pdf")


def _cluster_pdf(tmp_path: Path) -> Path:
    """3 pages whose extracted text forms 3 heading clusters (30 lines/page)."""
    doc = fitz.open()
    filler = "plain filler body sentence for clustering layout"
    for idx, name in enumerate(["One", "Two", "Three"]):
        page = doc.new_page(width=612, height=792)
        y = 60
        for i in range(30):
            if i == 0:
                text = f"# Chapter {name}"
            elif i == 4:
                text = f"# Section {chr(65 + idx)}"
            else:
                text = filler
            page.insert_text((50, y), text, fontname="cour", fontsize=10)
            y += 14
    return _write_pdf(doc, tmp_path, "cluster.pdf")


def _short_toc_pdf(tmp_path: Path, name: str = "short_toc.pdf") -> Path:
    """TOC page whose pypdf text is < 50 chars (triggers the vision/OCR path)."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 60), "Contents", fontname="cour", fontsize=14)
    pg = doc.new_page(width=612, height=792)
    yy = 60
    for _ in range(4):
        pg.insert_text((50, yy), _LONG_BODY_LINE, fontname="cour", fontsize=10)
        yy += 16
    return _write_pdf(doc, tmp_path, name)


def _encrypted_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 60), "some real text on the encrypted page", fontname="cour", fontsize=12)
    doc.new_page(width=612, height=792)
    doc.set_toc([[1, "Encrypted Chapter", 1]])
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(
        doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    )
    return path


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, response=None, raise_exc: Exception | None = None):
        self.response = response or _FakeResponse(500)
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


def _patch_llm(monkeypatch, session: _FakeSession) -> None:
    monkeypatch.setattr(toc_mod, "session_for_url", lambda url: session)


class _FakeVisionResult:
    def __init__(self, text: str, success: bool = True):
        self.text = text
        self.success = success


class _FakeVisionEngine:
    """Stands in for QwenOCREngine at the class boundary."""

    instances: list[_FakeVisionEngine] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.pages: list[int] = []
        _FakeVisionEngine.instances.append(self)

    def process_page(self, page, page_num: int):
        self.pages.append(page_num)
        return _FakeVisionResult(
            "1. Vision Chapter One ......... 1\n2. Vision Chapter Two ......... 2"
        )


class _FakeModelManager:
    instances: list[_FakeModelManager] = []

    def __init__(self):
        self.released: list[str] = []
        self.running = True
        self.exists = True
        self.acquire = True
        _FakeModelManager.instances.append(self)

    def is_running(self):
        return self.running

    def model_exists(self, model_name):
        return self.exists

    def acquire_model(self, model_name, model_type):
        return self.acquire

    def release_model(self, model_name):
        self.released.append(model_name)
        return True


# ────────────────────────────────────────────────────────────────────────────
# 1. PDF outline (bookmark) extraction
# ────────────────────────────────────────────────────────────────────────────


class TestExtractOutlines:
    def test_bookmarks_are_extracted_with_levels(self, tmp_path):
        ex, logs = _make_extractor()
        entries = ex.extract(_bookmarked_pdf(tmp_path))
        assert [(e.title, e.page, e.level) for e in entries] == [
            ("Chapter One", 1, 0),
            ("Section One A", 2, 1),
            ("Chapter Two", 3, 0),
        ]
        assert any("Using PDF outlines: 3 entries" in m for _, m in logs)

    def test_bookmarked_entries_are_tocentry_objects(self, tmp_path):
        ex, _ = _make_extractor()
        entries = ex.extract(_bookmarked_pdf(tmp_path))
        for e in entries:
            assert e[0] == e.title  # tuple-compat indexing
            assert e[1] == e.page
            assert len(e) == 2
            assert e.confidence == 1.0

    def test_encrypted_pdf_with_password_uses_outlines(self, tmp_path):
        ex, _ = _make_extractor()
        entries = ex.extract(_encrypted_pdf(tmp_path), password="user")
        assert [(e.title, e.page) for e in entries] == [("Encrypted Chapter", 1)]

    def test_encrypted_pdf_without_password_crashes(self, tmp_path):
        # CHARACTERIZATION (suspected bug, reported not fixed): extract() only
        # guards PdfReader construction + decrypt; `len(reader.pages)` on line
        # ~135 is OUTSIDE the try — an encrypted PDF without a password raises
        # FileNotDecryptedError instead of returning [] like other bad PDFs.
        ex, _ = _make_extractor()
        with pytest.raises(FileNotDecryptedError):
            ex.extract(_encrypted_pdf(tmp_path))

    def test_corrupt_pdf_returns_empty_list(self, tmp_path):
        bad = tmp_path / "garbage.pdf"
        bad.write_bytes(b"this is definitely not a pdf file at all")
        ex, logs = _make_extractor()
        assert ex.extract(bad) == []
        assert any("Cannot open PDF" in m for _, m in logs)

    def test_outlines_extraction_exception_returns_none(self):
        ex, _ = _make_extractor()

        class _Boom:
            @property
            def outline(self):
                raise RuntimeError("outline boom")

        assert ex._extract_outlines(_Boom()) is None

    def test_outlines_with_unresolvable_destination_keeps_page_zero(self):
        ex, _ = _make_extractor()

        class _Dest:
            title = "Broken Destination"
            page = object()

        class _Reader:
            outline = [_Dest()]

            @staticmethod
            def get_destination_page_number(dest):
                raise ValueError("unresolvable")

        result = ex._extract_outlines(_Reader())
        assert result is not None
        assert (result[0].title, result[0].page) == ("Broken Destination", 0)


# ────────────────────────────────────────────────────────────────────────────
# 2. Adaptive pipeline — LLM stage
# ────────────────────────────────────────────────────────────────────────────


class TestExtractLlmStage:
    def _plain_pdf(self, tmp_path: Path) -> Path:
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text(
            (50, 60), "some plain text page without any bookmarks", fontname="cour", fontsize=12
        )
        doc.new_page(width=612, height=792)
        return _write_pdf(doc, tmp_path, "plain.pdf")

    def test_llm_monotonic_entries_are_returned(self, tmp_path, monkeypatch):
        session = _FakeSession(
            _FakeResponse(
                200,
                {
                    "response": (
                        "Here is the TOC:\n"
                        '[{"title": "Chapter One", "page": 2}, {"title": "Chapter Two", "page": 3},'
                        ' {"title": "Chapter Three", "page": 4}, {"title": "Chapter Four", "page": 5}]'
                    )
                },
            )
        )
        _patch_llm(monkeypatch, session)
        ex, logs = _make_extractor(adaptive=True)
        entries = ex.extract(self._plain_pdf(tmp_path))
        assert [(e.title, e.page, e.confidence) for e in entries] == [
            ("Chapter One", 2, 0.9),
            ("Chapter Two", 3, 0.9),
            ("Chapter Three", 4, 0.9),
            ("Chapter Four", 5, 0.9),
        ]
        assert any("LLM extraction: 4 entries" in m for _, m in logs)
        # the real pooled transport was called with the configured model + prompt
        assert len(session.calls) == 1
        assert session.calls[0]["url"] == "http://localhost:11434/api/generate"
        assert session.calls[0]["json"]["model"] == "test-model:latest"
        assert (
            "Chapter" in session.calls[0]["json"]["prompt"]
            or "TOC" in session.calls[0]["json"]["prompt"]
        )

    def test_llm_non_monotonic_pages_fall_through(self, tmp_path, monkeypatch):
        session = _FakeSession(
            _FakeResponse(
                200,
                {
                    "response": (
                        '[{"title": "A", "page": 5}, {"title": "B", "page": 4},'
                        ' {"title": "C", "page": 7}, {"title": "D", "page": 9}]'
                    )
                },
            )
        )
        _patch_llm(monkeypatch, session)
        ex, logs = _make_extractor(adaptive=True)
        # No clustering candidates and no TOC page -> empty result
        assert ex.extract(self._plain_pdf(tmp_path)) == []
        assert any("failed monotonic check" in m for _, m in logs)

    def test_llm_too_few_entries_fall_through(self, tmp_path, monkeypatch):
        session = _FakeSession(
            _FakeResponse(
                200, {"response": '[{"title": "A", "page": 1}, {"title": "B", "page": 2}]'}
            )
        )
        _patch_llm(monkeypatch, session)
        ex, _ = _make_extractor(adaptive=True)
        assert ex.extract(self._plain_pdf(tmp_path)) == []

    def test_llm_unreachable_falls_to_rule_based(self, tmp_path, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(503)))
        ex, _ = _make_extractor(adaptive=True)
        # dotted TOC pdf still yields entries via rule-based parsers
        entries = ex.extract(_dotted_toc_pdf(tmp_path))
        assert ("1. Introduction", 3) in [(e[0], e[1]) for e in entries]


class TestLlmExtractionDirect:
    """Direct calls to _extract_with_llm (mocked HTTP boundary)."""

    def _extractor(self):
        ex, _ = _make_extractor(adaptive=True)
        return ex

    def test_empty_markdown_returns_none(self):
        assert self._extractor()._extract_with_llm("") is None

    def test_missing_prompt_template_returns_none(self, monkeypatch):
        from core.summarisation.prompt_manager import PromptManager

        monkeypatch.setattr(PromptManager, "render_template", lambda self, name, **variables: None)
        assert self._extractor()._extract_with_llm("some markdown text") is None

    def test_http_error_status_returns_none(self, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(500)))
        assert self._extractor()._extract_with_llm("page one text\npage two text") is None

    def test_response_without_json_block_returns_none(self, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(200, {"response": "no json here"})))
        assert self._extractor()._extract_with_llm("page one text") is None

    def test_http_exception_returns_none(self, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(raise_exc=ConnectionError("boom")))
        assert self._extractor()._extract_with_llm("page one text") is None

    def test_valid_response_parses_entries_with_edge_cases(self, monkeypatch):
        payload = {
            "response": (
                "```json\n"
                "[\n"
                '  {"title": "Chapter One", "page": 3},\n'
                '  {"title": "", "page": 4},\n'  # empty title skipped
                '  {"title": "Chapter Two", "page": "7"},\n'  # numeric string coerced
                '  {"title": "Chapter Three", "page": "not-a-number"},\n'  # page -> None
                '  {"title": "Chapter Four"}\n'  # missing page -> None
                "]\n"
                "```"
            )
        }
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(200, payload)))
        entries = self._extractor()._extract_with_llm("page one text")
        assert [(e.title, e.page) for e in entries] == [
            ("Chapter One", 3),
            ("Chapter Two", 7),
            ("Chapter Three", None),
            ("Chapter Four", None),
        ]
        assert all(e.confidence == 0.9 for e in entries)

    def test_empty_json_array_returns_none(self, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(200, {"response": "[]"})))
        assert self._extractor()._extract_with_llm("page one text") is None


# ────────────────────────────────────────────────────────────────────────────
# 3. Adaptive pipeline — clustering stage
# ────────────────────────────────────────────────────────────────────────────


class TestExtractClusteringStage:
    def test_clustering_entries_win_when_llm_fails(self, tmp_path, monkeypatch):
        _patch_llm(monkeypatch, _FakeSession(_FakeResponse(500)))
        ex, logs = _make_extractor(adaptive=True)
        entries = ex.extract(_cluster_pdf(tmp_path))
        assert [(e.title, e.page, e.confidence) for e in entries] == [
            ("# Chapter One", None, 0.5),
            ("# Chapter Two", None, 0.5),
            ("# Chapter Three", None, 0.5),
        ]
        assert any("Clustering extraction: 3 entries" in m for _, m in logs)


class TestClusteringDirect:
    def _extractor(self):
        ex, _ = _make_extractor()
        return ex

    def test_empty_markdown_returns_none(self):
        assert self._extractor()._extract_by_clustering("") is None

    def test_too_few_candidates_returns_none(self):
        md = "# Only Heading\nbody body body"
        assert self._extractor()._extract_by_clustering(md) is None

    def test_single_candidate_returns_none(self):
        # one candidate -> no gaps -> None
        md = "# Heading One\n" + "\n".join(f"plain filler line {i}" for i in range(10))
        assert self._extractor()._extract_by_clustering(md) is None

    def test_short_and_overlong_lines_are_not_candidates(self):
        # Cluster heads land at lines 4, 30, 60 with a 4-line member each:
        # gaps [26, 4, 26, 4] -> avg 15, threshold 22.5 -> 3 clusters.
        # If the <5-char filter broke, "# A" (line 0) would head cluster 1
        # instead of "# Chapter One"; if the >200-char filter broke, the
        # 250-char line (26) would head its own middle cluster.
        lines = ["plain filler sentence here"] * 90
        lines[0] = "# A"  # < 5 chars -> not a candidate
        lines[4] = "# Chapter One"
        lines[26] = "x" * 250  # > 200 chars -> not a candidate
        lines[30] = "# Chapter Two"
        lines[34] = "# Chapter Two Sub"
        lines[60] = "# Chapter Three"
        lines[64] = "# Chapter Three Sub"
        md = "\n".join(lines)
        entries = self._extractor()._extract_by_clustering(md)
        assert [e.title for e in entries] == ["# Chapter One", "# Chapter Two", "# Chapter Three"]

    def test_three_clusters_produce_three_entries(self):
        lines = ["plain filler sentence here"] * 90
        for cluster_start, title in (
            (0, "# Chapter One"),
            (30, "# Chapter Two"),
            (60, "# Chapter Three"),
        ):
            lines[cluster_start] = title
            lines[cluster_start + 4] = f"# Section {title[-1]}"
        md = "\n".join(lines)
        entries = self._extractor()._extract_by_clustering(md)
        assert [e.title for e in entries] == ["# Chapter One", "# Chapter Two", "# Chapter Three"]
        assert all(e.page is None for e in entries)

    def test_uppercase_and_keyword_candidates(self):
        lines = ["plain filler sentence here"] * 90
        # 3 clusters (two candidates each): gaps 4,26,4,26,4 -> avg 12.8,
        # threshold 19.2 -> breaks at the 26-gaps.
        lines[0] = "ALL CAPS HEADING LINE"
        lines[4] = "SECOND ALL CAPS MEMBER"
        lines[30] = "Chapter keyword heading"
        lines[34] = "ANOTHER ALL CAPS MEMBER"
        lines[60] = "PART TWO SECTION TEXT"
        lines[64] = "Section extra heading"
        md = "\n".join(lines)
        entries = self._extractor()._extract_by_clustering(md)
        assert [e.title for e in entries] == [
            "ALL CAPS HEADING LINE",
            "Chapter keyword heading",
            "PART TWO SECTION TEXT",
        ]

    def test_code_blocks_and_tables_skipped(self):
        lines = ["plain filler sentence here"] * 90
        lines[0] = "# Chapter One"
        lines[10] = "```python\nprint('hi')\n```".splitlines()[0]
        lines[20] = "| table | row |"
        lines[30] = "# Chapter Two"
        lines[60] = "# Chapter Three"
        md = "\n".join(lines)
        entries = self._extractor()._extract_by_clustering(md)
        titles = [e.title for e in entries]
        assert "```python" not in titles
        assert "| table | row |" not in titles


# ────────────────────────────────────────────────────────────────────────────
# 4. Rule-based fallback (rendered TOC pages)
# ────────────────────────────────────────────────────────────────────────────


class TestExtractRuleBased:
    def test_dotted_leader_toc_page_parses_single_line(self, tmp_path):
        ex, logs = _make_extractor(adaptive=False)
        entries = ex.extract(_dotted_toc_pdf(tmp_path))
        assert [(e[0], e[1]) for e in entries] == [
            ("1. Introduction", 3),
            ("2. Methods", 5),
            ("3. Results and Discussion", 7),
            ("4. Conclusion", 9),
        ]
        assert any("Selected parser: 'single_line'" in m for _, m in logs)
        # body-page break: the distinctive page-3 marker never leaks in
        assert not any("marker page three" in str(e[0]) for e in entries)

    def test_low_score_parser_is_used_as_fallback(self, tmp_path):
        ex, logs = _make_extractor(adaptive=False)
        entries = ex.extract(_roman_low_score_pdf(tmp_path))
        assert [(e[0], e[1]) for e in entries] == [
            ("Valid Roman Title", 1),
            ("Another Roman Heading", 2),
            ("Out Of Range Header", 0),  # IX -> 9 > 5 pages -> treated as chapter number
        ]
        assert any("below minimum" in m and "fallback" in m for _, m in logs)

    def test_more_than_six_entries_log_truncation(self, tmp_path):
        ex, logs = _make_extractor(adaptive=False)
        entries = ex.extract(_many_entries_toc_pdf(tmp_path))
        # 8 parsed entries -> first 6 logged, then the "and N more" summary
        assert [(e[0], e[1]) for e in entries] == [
            (f"{i}. Chapter Topic Number {i}", i + 2) for i in range(1, 9)
        ]
        assert any("Extracted 8 entries" in m for _, m in logs)
        assert any("… and 2 more" in m for _, m in logs)

    def test_roman_entries_mapped_via_page_labels(self, tmp_path):
        ex, logs = _make_extractor(adaptive=False)
        entries = ex.extract(_roman_labels_pdf(tmp_path))
        assert [(e[0], e[1]) for e in entries] == [
            ("Alpha Preface Section", 1),
            ("Beta Preface Section", 2),
            ("Gamma Preface Section", 3),
        ]
        assert any("PDF page labels available" in m for _, m in logs)

    def test_no_toc_page_found_returns_empty(self, tmp_path):
        doc = fitz.open()
        for _ in range(3):
            pg = doc.new_page(width=612, height=792)
            pg.insert_text((50, 60), "plain narrative page text", fontname="cour", fontsize=12)
        path = _write_pdf(doc, tmp_path, "no_toc.pdf")
        ex, logs = _make_extractor(adaptive=False)
        assert ex.extract(path) == []
        assert any("No Table of Contents page found" in m for _, m in logs)


# ────────────────────────────────────────────────────────────────────────────
# 5. Vision-OCR branch (Phase 3.3)
# ────────────────────────────────────────────────────────────────────────────


class TestExtractVisionOcr:
    def _vision_settings(self):
        return {
            "advanced.toc_vision_ocr": True,
            "ocr.primary_model": "test-vl:8b",
            "paths.poppler": None,
        }

    def test_vision_ocr_success(self, tmp_path, monkeypatch):
        _FakeVisionEngine.instances.clear()
        _FakeModelManager.instances.clear()
        monkeypatch.setattr(toc_mod, "ModelManager", _FakeModelManager)
        monkeypatch.setattr("core.ocr.qwen_ocr.QwenOCREngine", _FakeVisionEngine)
        ex, logs = _make_extractor(adaptive=False, settings=self._vision_settings())
        entries = ex.extract(_short_toc_pdf(tmp_path))
        assert [(e[0], e[1]) for e in entries] == [
            ("1. Vision Chapter One", 1),
            ("2. Vision Chapter Two", 2),
        ]
        # engine constructed with the configured model + released afterwards
        assert len(_FakeVisionEngine.instances) == 1
        assert _FakeVisionEngine.instances[0].kwargs["model_name"] == "test-vl:8b"
        assert _FakeVisionEngine.instances[0].kwargs["timeout"] == 180
        assert _FakeVisionEngine.instances[0].pages == [1]  # only the TOC page
        assert _FakeModelManager.instances[0].released == ["test-vl:8b"]
        assert any("Vision model 'test-vl:8b' loaded" in m for _, m in logs)

    def test_vision_model_not_running_falls_back(self, tmp_path, monkeypatch):
        _FakeModelManager.instances.clear()

        class _NotRunning(_FakeModelManager):
            def __init__(self):
                super().__init__()
                self.running = False

        monkeypatch.setattr(toc_mod, "ModelManager", _NotRunning)
        ex, logs = _make_extractor(adaptive=False, settings=self._vision_settings())
        entries = ex.extract(_short_toc_pdf(tmp_path))
        # TOC page holds only "Contents"; the (unavailable) Tesseract fallback
        # yields nothing parseable -> no entries.
        assert entries == []
        assert any("not available. Falling back to Tesseract" in m for _, m in logs)

    def test_vision_model_acquire_fails_falls_back(self, tmp_path, monkeypatch):
        class _NoAcquire(_FakeModelManager):
            def __init__(self):
                super().__init__()
                self.acquire = False

        monkeypatch.setattr(toc_mod, "ModelManager", _NoAcquire)
        ex, logs = _make_extractor(adaptive=False, settings=self._vision_settings())
        assert ex.extract(_short_toc_pdf(tmp_path)) == []
        assert any("Failed to load vision model" in m for _, m in logs)


# ────────────────────────────────────────────────────────────────────────────
# 6. Page text extraction + OCR fallbacks
# ────────────────────────────────────────────────────────────────────────────


class TestPageTextExtraction:
    def _reader(self, tmp_path, name="pages.pdf"):
        doc = fitz.open()
        rich = doc.new_page(width=612, height=792)
        rich.insert_text(
            (50, 60),
            "A sufficiently long line of real text so that pypdf extraction returns it directly",
            fontname="cour",
            fontsize=12,
        )
        doc.new_page(width=612, height=792)  # blank page
        path = _write_pdf(doc, tmp_path, name)
        return PdfReader(str(path))

    def test_rich_text_page_returned_directly(self, tmp_path):
        ex, _ = _make_extractor()
        reader = self._reader(tmp_path)
        text = ex._extract_page_text(reader, 0)
        assert "sufficiently long line" in text

    def test_vision_engine_success_on_short_page(self, tmp_path):
        ex, _ = _make_extractor()
        reader = self._reader(tmp_path)

        class _Engine:
            def process_page(self, page, page_num):
                return _FakeVisionResult("OCR produced this text from the vision model", True)

        text = ex._extract_page_text(reader, 1, vision_engine=_Engine())
        assert text == "OCR produced this text from the vision model"

    def test_vision_engine_failure_result_falls_through(self, tmp_path):
        ex, _ = _make_extractor()
        reader = self._reader(tmp_path)

        class _Engine:
            def process_page(self, page, page_num):
                return _FakeVisionResult("", False)

        # blank page + failed vision -> tesseract attempt (unavailable) -> ""
        assert ex._extract_page_text(reader, 1, vision_engine=_Engine()) == ""

    def test_vision_engine_exception_falls_through(self, tmp_path):
        ex, logs = _make_extractor()
        reader = self._reader(tmp_path)

        class _Engine:
            def process_page(self, page, page_num):
                raise RuntimeError("vision crashed")

        assert ex._extract_page_text(reader, 1, vision_engine=_Engine()) == ""
        assert any("Vision OCR failed" in m for _, m in logs)

    def test_tesseract_ocr_success(self, tmp_path, monkeypatch):
        """OCR success path — pytesseract mocked at the library boundary
        (the production call hardcodes lang='eng+fas'; this sandbox's tesseract
        has no 'fas' traineddata, so a real success is impossible here).
        Rasterization is mocked at the pdf2image boundary too — the test
        verifies the OCR CHAIN, not the poppler binary (absent on clean
        CI runners; found by the V0.15 CI canary)."""
        ex, logs = _make_extractor()
        reader = self._reader(tmp_path)
        monkeypatch.setattr("pdf2image.convert_from_bytes", lambda *a, **k: [object()])
        monkeypatch.setattr(
            "pytesseract.image_to_string", lambda img, lang=None: "tesseract extracted this line"
        )
        text = ex._extract_page_text(reader, 1)
        assert text == "tesseract extracted this line"
        assert any("Tesseract OCR extracted" in m for _, m in logs)

    def test_tesseract_ocr_failure_returns_empty(self, tmp_path):
        """Blank page, no vision: the Tesseract attempt fails (the default
        paths.tesseract is a Windows path that does not exist on Linux) and
        the empty pypdf text is returned."""
        ex, logs = _make_extractor()
        reader = self._reader(tmp_path)
        assert ex._extract_page_text(reader, 1) == ""
        assert any("Tesseract OCR failed" in m for _, m in logs)


# ────────────────────────────────────────────────────────────────────────────
# 7. Markdown preview
# ────────────────────────────────────────────────────────────────────────────


class TestMarkdownPreview:
    def test_preview_contains_page_markers(self, tmp_path):
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page(width=612, height=792)
            page.insert_text((50, 60), f"text of page {i + 1}", fontname="cour", fontsize=12)
        path = _write_pdf(doc, tmp_path, "preview.pdf")
        ex, _ = _make_extractor()
        reader = PdfReader(str(path))
        md = ex._get_markdown_preview(reader)
        assert md is not None
        assert "<!-- original page 1 -->" in md
        assert "<!-- original page 3 -->" in md
        assert "text of page 2" in md

    def test_preview_respects_max_pages(self, tmp_path):
        doc = fitz.open()
        for i in range(5):
            page = doc.new_page(width=612, height=792)
            page.insert_text((50, 60), f"text of page {i + 1}", fontname="cour", fontsize=12)
        path = _write_pdf(doc, tmp_path, "preview2.pdf")
        ex, _ = _make_extractor()
        reader = PdfReader(str(path))
        md = ex._get_markdown_preview(reader, max_pages=2)
        assert "page 2 -->" in md
        assert "page 3 -->" not in md

    def test_preview_exception_returns_none(self):
        ex, _ = _make_extractor()

        class _BoomPage:
            def extract_text(self):
                raise RuntimeError("extraction exploded")

        class _BoomReader:
            pages = [_BoomPage()]

        assert ex._get_markdown_preview(_BoomReader()) is None


# ────────────────────────────────────────────────────────────────────────────
# 8. Smokes for the module import surface
# ────────────────────────────────────────────────────────────────────────────


def test_module_exports_and_types():
    assert toc_mod.TOCEntry is not None
    assert hasattr(toc_mod, "ModelManager")
    assert isinstance(toc_mod.TocExtractor.ENTRY_PATTERNS, list)
    assert toc_mod.TocExtractor.MIN_ACCEPTABLE_SCORE == 60
    # a dummy types import keeps the module header honest under ruff F401 audits
    assert isinstance(types.ModuleType("x"), types.ModuleType)
