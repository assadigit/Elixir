"""V18.2.16: Deterministic OCR pre-scan — fast page-classification BEFORE
the OCR model loads.

WHY THIS EXISTS
---------------
The user's requirement (this session):

    "a deterministic script firstly check if the selected book/chapters have
    pages that need OCR (scanned pages which are not readable by model), it
    scans very fast, then OCR model use this info (it already knows where it
    should go) — it will save time for us."

The OCR model (Qwen2-VL / OlmOCR, ~6 GB) cannot coexist with the LLM model
in 12 GB VRAM — it must be a dedicated phase (load once → scan all needed
pages → unload → then LLM). Loading it takes several minutes. If we can
determine — BEFORE loading the model — exactly which pages need OCR, we
can:

  1. **Skip the model load entirely** when 0 pages need OCR (a fully
     digital book, or a chapter selection that contains only digital
     pages). This saves the entire multi-minute load + unload cycle.
  2. **Give the OCR model the exact page list** so it doesn't waste time
     on pages that already have extractable text.

The existing ``PdfAnalyzer`` already classifies every page as
scanned/text, but it runs over the WHOLE book at conversion start. When
chapter selection is active (``valid_pages`` set), this pre-scans pages
the user didn't select — wasted work. This module adds a focused,
selection-aware pre-scan that runs right before the OCR model load
decision.

HOW IT WORKS
------------
For each page in the candidate set (the intersection of
``pages_to_ocr`` and ``valid_pages``), the pre-scan:

  1. Calls ``page.extract_text()`` (pdfplumber/pypdf — milliseconds/page).
  2. Checks if the extracted text is "meaningful" (≥30 chars, ≥2 words,
     <30% garbage characters) — same heuristic as ``PdfAnalyzer``.
  3. Marks the page as ``needs_ocr`` (scanned/image-only) or ``digital``
     (has extractable text).

No model is loaded. No HTTP calls. No network. Pure text extraction +
heuristics. For a 200-page book this takes ~2-5 seconds total (vs.
several minutes to load the OCR model).

INTEGRATION
-----------
:func:`prescan_pages` is called by ``OCRService.process_pdf`` right
before the model-load decision. The result drives three paths:

  - ``needs_ocr_pages`` is empty → skip the OCR model load entirely
    (log: "✅ Pre-scan: 0 pages need OCR — skipping OCR model load").
  - ``needs_ocr_pages`` is non-empty → load the OCR model with this
    exact list (log: "📋 Pre-scan: N pages need OCR: [...] — loading
    model for these pages only").
  - The full original ``pages_to_ocr`` is preserved for the digital-
    text extraction path (those pages still get extracted via markitdown).

DESIGN PRINCIPLES
-----------------
- **Purely deterministic.** No model, no embedding, no network.
- **Fast.** ~10-50 ms/page (just text extraction). A 200-page book
  pre-scans in 2-10 seconds.
- **Fail-open.** If the pre-scan crashes, the OCR service falls back to
  the original ``pages_to_ocr`` list (loads the model as before). The
  crash is logged via :func:`log_swallow`.
- **Selection-aware.** Respects ``valid_pages`` (chapter selection) and
  ``page_range_start``/``page_range_end`` — only scans the pages the
  user actually selected.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Text-meaningful heuristic (mirrors PdfAnalyzer._is_text_meaningful) ────
# A page is "digital" (has extractable text) if it has ≥30 chars of text,
# ≥2 words, and <30% garbage characters. Otherwise it's "scanned"
# (image-only, needs OCR).
MIN_TEXT_CHARS = 30
MIN_WORDS = 2
SCANNED_TEXT_THRESHOLD = 30  # chars; below this, check words

# Garbage-char run: 5+ consecutive special chars indicates OCR/extraction
# garbage (not real text).
_GARBAGE_RE = re.compile(r'([!@#$%^&*()_+=\-{}\[\]:;"\'<>?,./]{5,})')
_WORD_RE = re.compile(r'[A-Za-z\u0600-\u06FF]{2,}')


def _is_text_meaningful(text: str) -> bool:
    """True if ``text`` looks like real digital text (not garbage/empty).

    Mirrors :meth:`PdfAnalyzer._is_text_meaningful` so the pre-scan and
    the full analyzer agree on what counts as "scanned".
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < SCANNED_TEXT_THRESHOLD:
        words = _WORD_RE.findall(stripped)
        if len(words) < MIN_WORDS:
            return False
        if len(stripped) < MIN_TEXT_CHARS or (len(stripped) < 15 and stripped.isupper()):
            return False
    # If >30% of the text is garbage-char runs, it's not meaningful.
    garbage_matches = _GARBAGE_RE.findall(text)
    if garbage_matches:
        garbage_len = sum(len(m) for m in garbage_matches)
        if garbage_len > len(text) * 0.3:
            return False
    return True


@dataclass
class PreScanResult:
    """Result of the deterministic OCR pre-scan.

    Attributes:
        scanned_pages: list of page numbers (1-indexed) that need OCR.
        digital_pages: list of page numbers that have extractable text.
        total_scanned: total pages in the candidate set (for logging).
        elapsed_sec: wall-clock time the pre-scan took.
        skip_model_load: True if scanned_pages is empty (no OCR needed).
    """
    scanned_pages: list[int] = field(default_factory=list)
    digital_pages: list[int] = field(default_factory=list)
    total_scanned: int = 0
    elapsed_sec: float = 0.0

    @property
    def skip_model_load(self) -> bool:
        """True when no pages need OCR — the model load can be skipped."""
        return len(self.scanned_pages) == 0

    @property
    def needs_ocr_count(self) -> int:
        return len(self.scanned_pages)


def prescan_pages(
    pdf_path: Path,
    candidate_pages: list[int],
    password: str | None = None,
    log_fn: callable | None = None,
) -> PreScanResult:
    """Fast deterministic pre-scan: classify each candidate page as scanned/digital.

    For each page in ``candidate_pages``, extracts text via pypdf and
    checks if it's "meaningful" (≥30 chars, ≥2 words, <30% garbage).
    Pages with no/little extractable text are marked as needing OCR.

    **No model is loaded.** Pure text extraction — ~10-50 ms/page.

    Args:
        pdf_path: path to the PDF file.
        candidate_pages: 1-indexed page numbers to scan (already
            filtered to the selected chapter range / valid_pages).
        password: optional PDF password.
        log_fn: optional ``fn(msg, level)`` callback for traceable logs.

    Returns:
        :class:`PreScanResult` with the scanned/digital page split.
    """
    def _log(msg: str, level: str = "INFO") -> None:
        if log_fn:
            log_fn(msg, level)
        else:
            logger.log(getattr(logging, level, logging.INFO), msg)

    result = PreScanResult()
    if not candidate_pages:
        return result

    start = time.time()
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted and password:
            reader.decrypt(password)
    except Exception as e:
        # Fail-open: if we can't even open the PDF, return an empty result.
        # The OCR service's existing path will handle the error.
        _log(f"  ⚠️ Pre-scan: could not open PDF ({e}) — skipping pre-scan", "WARNING")
        result.elapsed_sec = time.time() - start
        return result

    result.total_scanned = len(candidate_pages)
    _log(
        f"  🔍 V18.2.16 Pre-scan: checking {len(candidate_pages)} page(s) "
        f"for OCR necessity (deterministic, no model loaded)…",
        "INFO",
    )

    scanned: list[int] = []
    digital: list[int] = []

    for page_num in candidate_pages:
        try:
            page = reader.pages[page_num - 1]
            extracted = page.extract_text() or ""
        except Exception:
            # If extraction fails, mark as scanned (conservative — let OCR try).
            scanned.append(page_num)
            continue

        if _is_text_meaningful(extracted):
            digital.append(page_num)
        else:
            scanned.append(page_num)

    result.scanned_pages = scanned
    result.digital_pages = digital
    result.elapsed_sec = time.time() - start

    # Traceable summary log — the key decision point.
    if scanned:
        _log(
            f"  📋 V18.2.16 Pre-scan result: {len(scanned)} page(s) need OCR, "
            f"{len(digital)} have digital text (took {result.elapsed_sec:.1f}s)",
            "INFO",
        )
        # Show the first 10 page numbers so the user can verify.
        _preview = scanned[:10]
        _more = f"… (+{len(scanned) - 10} more)" if len(scanned) > 10 else ""
        _log(
            f"     Pages needing OCR: {_preview}{_more}",
            "INFO",
        )
    else:
        _log(
            f"  ✅ V18.2.16 Pre-scan result: 0 pages need OCR — all "
            f"{len(digital)} candidate pages have digital text "
            f"(took {result.elapsed_sec:.1f}s). "
            f"OCR model load will be SKIPPED.",
            "INFO",
        )

    return result


def intersect_with_valid_pages(
    pages_to_ocr: list[int],
    valid_pages: set[int] | None,
    page_range_start: int | None,
    page_range_end: int | None,
    total_pages: int,
) -> list[int]:
    """Restrict the OCR candidate list to the selected chapter pages.

    When chapter selection is active (``valid_pages`` set) or a page range
    is applied, the pre-scan should only check those pages — not the whole
    book. This helper computes the intersection.

    Args:
        pages_to_ocr: the full list of pages the analyzer flagged as scanned.
        valid_pages: optional set of pages in selected chapters (None = all).
        page_range_start: optional 1-indexed start page.
        page_range_end: optional 1-indexed end page.
        total_pages: total pages in the PDF (for clamping).

    Returns:
        The filtered list of candidate pages for the pre-scan.
    """
    candidates = list(pages_to_ocr)

    # Apply page range filter
    if page_range_start is not None or page_range_end is not None:
        start = page_range_start or 1
        end = page_range_end or total_pages
        start = max(1, min(start, total_pages))
        end = max(start, min(end, total_pages))
        candidates = [p for p in candidates if start <= p <= end]

    # Apply valid_pages (chapter selection) filter
    if valid_pages is not None:
        valid_set = set(valid_pages) if not isinstance(valid_pages, set) else valid_pages
        candidates = [p for p in candidates if p in valid_set]

    return sorted(candidates)
