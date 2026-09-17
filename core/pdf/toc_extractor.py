from core.models import TOCEntry, TOCResult

"""
Table of Contents extractor for PDF files – with OCR fallback and adaptive pipeline.

PHASE 3.3:
  - Vision OCR integration: if advanced.toc_vision_ocr is enabled, use Qwen3-VL
    to extract text from TOC pages when standard extraction yields < 50 chars.
  - Uses ModelManager to load/unload the vision model gracefully.

PHASE 4 (Adaptive Pipeline):
  - Merges the multi‑stage extractor from adaptive_toc.py:
    1. PDF outlines (bookmarks) – 100% accurate when present.
    2. LLM‑based semantic extraction from the first 30 pages of Markdown.
    3. Statistical heading clustering from the entire text.
    4. Rule‑based parsers (existing) with scoring.
  - Adds locate_headings() with rapidfuzz + page‑window search.
  - Provides a unified TOCResult with confidence and match details.

FIXES in this version:
  - Enhanced offset detection: skips front‑matter entries, uses first 5 chapter‑like entries.
  - Uses shared heading_utils for normalisation and fuzzy matching.
  - Adaptive offset correction: clusters offsets per entry, handles front‑matter vs body separately.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ── Shared heading utilities ──────────────────────────────────────────────
from core.common import (
    fuzzy_match_heading,
    get_heading_candidates,
    is_likely_heading,
)
from core.llm import ModelManager, ModelType
from utils.logging import get_main_logger
from utils.settings import Settings

logger = get_main_logger()


# ── Data classes for adaptive pipeline ─────────────────────────────────────


class TocExtractor:
    """Extract the Table of Contents from a PDF file, with adaptive pipeline."""

    TOC_PAGE_PATTERN = re.compile(
        r'\b(?:table\s+of\s+contents?|contents?|فهرست(?:\s+مطالب)?)\b',
        re.IGNORECASE | re.UNICODE,
    )

    ENTRY_PATTERNS = [
        re.compile(r'^(.+?)\s*[.·•\-]{3,}\s*(\d{1,4})\s*$'),
        re.compile(r'^(.+?)\t+(\d{1,4})\s*$'),
        re.compile(r'^(.{8,}?)\s{3,}(\d{1,4})\s*$'),
        re.compile(r'^(.{12,}?)\s{1,2}(\d{1,4})\s*$'),
    ]

    CHAPTER_LIKE = re.compile(
        r'^(?:'
        r'\d+[\.:]\s|'
        r'\d+\s*[-–—]\s|'
        r'Chapter\s+\d|Part\s+\d|Section\s+\d|Appendix|'
        r'Introduction|Conclusion|Foreword|Preface|Epilogue|Afterword|'
        r'فصل|بخش'
        r')',
        re.IGNORECASE | re.UNICODE,
    )

    NUMBERED_SECTION = re.compile(r'^(\d+)\s*[-–—.]\s+(.+)$', re.UNICODE)

    ROMAN_NUMERAL_PATTERN = re.compile(
        r'^(?P<roman>[IVXLCDM]+)\s*[.·•\-]\s+(?P<title>.+)$',
        re.IGNORECASE | re.UNICODE,
    )

    NOISE = re.compile(
        r'^(?:page|p\.?\s*\d|\d{1,4}\s*$|[ivxlcIVXLC]+\s*$)',
        re.IGNORECASE,
    )

    # Minimum acceptable score threshold (0-100)
    MIN_ACCEPTABLE_SCORE = 60

    # Confidence thresholds
    CONFIDENCE_HIGH = 0.7
    CONFIDENCE_MEDIUM = 0.5

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._settings = Settings()

        # Adaptive pipeline settings
        self._adaptive_enabled = self._settings.get("advanced.toc_adaptive", True)
        self._llm_model = self._settings.get(
            "summarisation.fast_model",
            self._settings.get("summarisation.model", "llama3.1:8b")
        )
        # V18.20.4.3 (P2 / W-c9): canonical URL from settings — the
        # hardcoded localhost split behavior on remote-Ollama rigs.
        self._ollama_base_url = self._settings.get_ollama_url()

    # ─────────────────────────────────────────────────────────────────────────
    # Main extraction (Phase 2.1 + Phase 3.3 Vision integration + Adaptive)
    # ─────────────────────────────────────────────────────────────────────────

    def extract(
        self,
        pdf_path: Path,
        password: str | None = None,
        max_scan_pages: int = 30,
    ) -> list[TOCEntry]:
        """
        Extract TOC entries using adaptive pipeline.
        V13.32.7: Returns list of TOCEntry objects (with level field for hierarchy).
        TOCEntry behaves like (title, page) tuples for backward compatibility.
        """
        from pypdf import PdfReader

        try:
            reader = PdfReader(str(pdf_path))
            if reader.is_encrypted and password:
                reader.decrypt(password)
        except Exception as e:
            self.log(f"[TOC] Cannot open PDF: {e}", "WARNING")
            return []

        total_pages = len(reader.pages)
        page_labels = None
        try:
            if hasattr(reader, 'page_labels') and reader.page_labels:
                page_labels = reader.page_labels
                self.log(f"[TOC] PDF page labels available: {page_labels[:10]}{'…' if len(page_labels)>10 else ''}", "DEBUG")
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

        # ── 1. Try PDF outlines (bookmarks) ──────────────────────────────────
        outlines = self._extract_outlines(reader)
        if outlines:
            self.log(f"[TOC] Using PDF outlines: {len(outlines)} entries.", "INFO")
            return outlines  # V13.32.7: return TOCEntry objects (with levels)

        # ── 2. Adaptive stages (LLM, clustering) ─────────────────────────────
        if self._adaptive_enabled:
            # We need markdown text for LLM and clustering.
            # We'll generate it on the fly using the first 30 pages.
            # Convert first 30 pages to markdown (using markitdown or fallback).
            md_text = self._get_markdown_preview(reader, max_pages=30)
            if md_text:
                # 2a. LLM extraction
                llm_entries = self._extract_with_llm(md_text)
                if llm_entries and len(llm_entries) >= 4:
                    self.log(f"[TOC] LLM extraction: {len(llm_entries)} entries.", "INFO")
                    # Validate: check monotonic pages and enough entries
                    pages = [e.page for e in llm_entries if e.page is not None]
                    if len(pages) >= 4 and all(pages[i] < pages[i+1] for i in range(len(pages)-1)):
                        return llm_entries  # V13.32.7: return TOCEntry objects
                    else:
                        self.log("[TOC] LLM entries failed monotonic check, falling back.", "DEBUG")

                # 2b. Clustering
                cluster_entries = self._extract_by_clustering(md_text)
                if cluster_entries and len(cluster_entries) >= 3:
                    self.log(f"[TOC] Clustering extraction: {len(cluster_entries)} entries.", "INFO")
                    return cluster_entries  # V13.32.7: return TOCEntry objects

        # ── 3. Rule‑based parsers (existing) ──────────────────────────────────
        # Find TOC page
        toc_idx = self._find_toc_page(reader, min(max_scan_pages, total_pages))
        if toc_idx is None:
            self.log("[TOC] No Table of Contents page found in first 30 pages.", "INFO")
            return []

        self.log(f"[TOC] Found TOC at PDF page {toc_idx + 1}.", "INFO")

        # ── Phase 3.3: Check if vision OCR is enabled ──────────────────────
        vision_engine = None
        model_manager = None
        model_name = None
        model_loaded = False

        if self._settings.get("advanced.toc_vision_ocr", False):
            self.log("[TOC] Vision OCR enabled for TOC extraction.", "INFO")
            model_manager = ModelManager()
            model_name = self._settings.get("ocr.primary_model", "qwen3-vl:8b")

            if model_manager.is_running() and model_manager.model_exists(model_name):
                self.log(f"[TOC] Loading vision model '{model_name}' for TOC OCR...", "INFO")
                if model_manager.acquire_model(model_name, ModelType.OCR):
                    model_loaded = True
                    self.log(f"[TOC] Vision model '{model_name}' loaded.", "INFO")
                    poppler_path = self._settings.get("paths.poppler") or None
                    from core.ocr.qwen_ocr import QwenOCREngine
                    vision_engine = QwenOCREngine(
                        model_name=model_name,
                        image_max_size=1200,
                        poppler_path=poppler_path,
                        timeout=180,
                        retries=1,
                    )
                else:
                    self.log(f"[TOC] Failed to load vision model '{model_name}'. Falling back to Tesseract.", "WARNING")
            else:
                self.log(f"[TOC] Vision model '{model_name}' not available. Falling back to Tesseract.", "WARNING")

        # ── Collect text from TOC pages ──────────────────────────────────────
        toc_lines: list[str] = []
        for page_idx in range(toc_idx, min(toc_idx + 4, total_pages)):
            text = self._extract_page_text(reader, page_idx, vision_engine=vision_engine)
            if text:
                toc_lines.extend(text.splitlines())
                if page_idx > toc_idx and self._looks_like_body(text.splitlines()):
                    break

        # ── Release vision model if loaded ──────────────────────────────────
        if model_loaded and model_manager and model_name:
            model_manager.release_model(model_name)
            self.log("[TOC] Released vision model.", "DEBUG")

        if not toc_lines:
            self.log("[TOC] No text extracted from TOC pages even with OCR fallback.", "WARNING")
            return []

        # Normalise tabs and collapse multiple spaces
        toc_lines = [re.sub(r"\t+", " ", l).strip() for l in toc_lines if l.strip()]
        toc_lines = [re.sub(r" {2,}", " ", l) for l in toc_lines]

        # Debug raw text
        raw_sample = "\n".join(toc_lines[:25])
        self.log(f"[TOC] Raw text sample (first 25 lines):\n{raw_sample}", "DEBUG")

        # ── Run ALL parsers and score them ──────────────────────────────────
        parser_results: list[tuple[str, list[tuple[str, int]]]] = [
            ("single_line", self._parse_single_line(toc_lines, total_pages)),
            ("multiline", self._parse_multiline(toc_lines, total_pages)),
            ("three_line", self._parse_three_line(toc_lines, total_pages)),
            ("column_layout", self._parse_column_layout(toc_lines, total_pages)),
            ("numbered_sections", self._parse_numbered_sections(toc_lines, total_pages)),
            ("headings_only", self._parse_headings_only(toc_lines, total_pages)),
            ("roman_numerals", self._parse_roman_numerals(toc_lines, total_pages, page_labels)),
        ]

        scored_results: list[tuple[str, list[tuple[str, int]], float]] = []
        for name, entries in parser_results:
            if not entries:
                continue
            seen = set()
            unique = []
            for h, p in entries:
                key = h.strip().lower()
                if key not in seen:
                    seen.add(key)
                    unique.append((h, p))
            entries = unique

            footer_pattern = re.compile(r'^(About the Author|Copyright|Credits|Permissions|Index|Glossary|Bibliography|References|Notes|Further Reading)\b', re.IGNORECASE)
            entries = [(h, p) for h, p in entries if not footer_pattern.match(h.strip())]

            if not entries:
                continue

            score = self._score_parser_result(entries, total_pages)
            scored_results.append((name, entries, score))
            self.log(f"[TOC] Parser '{name}': {len(entries)} entries, score {score:.1f}%", "DEBUG")

        if not scored_results:
            self.log("[TOC] No parser produced any valid entries.", "WARNING")
            return []

        best_name, best_entries, best_score = max(scored_results, key=lambda x: x[2])

        if best_score < self.MIN_ACCEPTABLE_SCORE:
            self.log(
                f"[TOC] Best parser '{best_name}' score {best_score:.1f}% below minimum "
                f"{self.MIN_ACCEPTABLE_SCORE}%. Using it anyway as a fallback.",
                "WARNING"
            )

        self.log(f"[TOC] Selected parser: '{best_name}' with score {best_score:.1f}%", "INFO")
        entries = best_entries

        if entries:
            self.log(f"[TOC] Extracted {len(entries)} entries.", "INFO")
            for h, p in entries[:6]:
                self.log(f"  p.{p:>3}: {h[:60]}", "INFO")
            if len(entries) > 6:
                self.log(f"  … and {len(entries) - 6} more", "INFO")
        else:
            self.log("[TOC] TOC page found but no entries could be parsed.", "WARNING")

        return entries

    # ─────────────────────────────────────────────────────────────────────────
    # Adaptive stages
    # ─────────────────────────────────────────────────────────────────────────

    def _get_markdown_preview(self, reader, max_pages: int = 30) -> str | None:
        """Convert first max_pages to markdown (or plain text) for LLM/clustering."""
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            # Write first max_pages to a temp PDF? Simpler: extract text page by page.
            # We'll use pypdf to extract text and combine with page markers.
            parts = []
            for i in range(min(max_pages, len(reader.pages))):
                text = reader.pages[i].extract_text() or ""
                parts.append(f"<!-- original page {i+1} -->\n{text}")
            return "\n\n".join(parts)
        except Exception as e:
            self.log(f"[TOC] Could not get markdown preview: {e}", "DEBUG")
            return None

    def _extract_with_llm(self, md_text: str) -> list[TOCEntry] | None:
        """Send first 30 pages of Markdown to local LLM and ask for JSON TOC."""
        if not md_text:
            return None
        # Get first ~30 pages (roughly 30*50 lines = 1500 lines, but safer: first 2000 lines)
        lines = md_text.splitlines()
        front = lines[:2000]
        text = "\n".join(front)

        from core.summarisation.prompt_manager import PromptManager
        _pm = PromptManager()
        prompt = _pm.render_template(
            "pdf/toc_extract",
            text=text,
        )
        if not prompt:
            return None
        import requests
        try:
            response = requests.post(
                f"{self._ollama_base_url}/api/generate",
                json={"model": self._llm_model, "prompt": prompt, "stream": False},
                timeout=120
            )
            if response.status_code != 200:
                return None
            data = response.json()
            raw = data.get("response", "")
            # Extract JSON block
            json_match = re.search(r'\[\s*\{.*\}\s*\]', raw, re.DOTALL)
            if not json_match:
                return None
            parsed = json.loads(json_match.group(0))
            entries = []
            for item in parsed:
                title = item.get("title", "").strip()
                if not title:
                    continue
                page = item.get("page")
                if page is not None:
                    try:
                        page = int(page)
                    except ValueError:
                        page = None
                entries.append(TOCEntry(title=title, page=page, confidence=0.9))
            return entries if entries else None
        except Exception as e:
            self.log(f"[TOC] LLM extraction failed: {e}", "DEBUG")
            return None

    def _extract_by_clustering(self, md_text: str) -> list[TOCEntry] | None:
        """
        Scan entire Markdown for candidate headings, then cluster by line density.
        Each cluster becomes a chapter start.
        """
        if not md_text:
            return None
        lines = md_text.splitlines()

        # Heuristic: lines that are short, not in code blocks, and look like headings
        candidates = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('```') or stripped.startswith('|'):
                continue
            if len(stripped) < 5 or len(stripped) > 200:
                continue
            if (stripped.startswith('#') or
                stripped.isupper() or
                any(key in stripped for key in ["Chapter", "Part", "Section", "CHAPTER", "PART", "SECTION"])):
                candidates.append((i, stripped))

        if len(candidates) < 3:
            return None

        # Simple density clustering: sort by line, group where gap > average_gap * 1.5
        sorted_candidates = sorted(candidates, key=lambda x: x[0])
        gaps = [sorted_candidates[i+1][0] - sorted_candidates[i][0] for i in range(len(sorted_candidates)-1)]
        if not gaps:
            return None
        avg_gap = sum(gaps) / len(gaps)
        threshold = avg_gap * 1.5

        clusters = []
        current_cluster = [sorted_candidates[0]]
        for i in range(1, len(sorted_candidates)):
            if sorted_candidates[i][0] - sorted_candidates[i-1][0] > threshold:
                clusters.append(current_cluster[0][1])
                current_cluster = [sorted_candidates[i]]
            else:
                current_cluster.append(sorted_candidates[i])
        if current_cluster:
            clusters.append(current_cluster[0][1])

        # Convert to TOC entries with page numbers estimated from line positions
        # We don't have exact pages, so set page=None and confidence low.
        entries = []
        for title in clusters:
            entries.append(TOCEntry(title=title, page=None, confidence=0.5))
        return entries

    # ─────────────────────────────────────────────────────────────────────────
    # PDF outlines extraction
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_outlines(self, reader) -> list[TOCEntry] | None:
        """Use pypdf to read internal bookmarks."""
        try:
            outlines = reader.outline
            if not outlines:
                return None

            def flatten(outline_list, level=0):
                entries = []
                for item in outline_list:
                    if hasattr(item, 'title') and hasattr(item, 'page'):
                        # It's a Destination
                        title = item.title
                        try:
                            page_num = reader.get_destination_page_number(item) + 1
                        except Exception as _e:
                            page_num = 0
                        entries.append(TOCEntry(title=title, page=page_num, confidence=1.0, level=level))
                    elif isinstance(item, list):
                        entries.extend(flatten(item, level+1))
                return entries

            raw = flatten(outlines)
            if not raw:
                return None
            # Remove duplicates
            seen = set()
            unique = []
            for e in raw:
                key = (e.title, e.page)
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            return unique
        except Exception as e:
            self.log(f"[TOC] Outlines extraction failed: {e}", "DEBUG")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Page text extraction with Vision OCR integration (Phase 3.3)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_page_text(
        self,
        reader,
        page_idx: int,
        vision_engine: Any | None = None,
    ) -> str:
        """
        Extract text from a PDF page.
        Priority: 1) pypdf text extraction, 2) Qwen3-VL (if enabled and provided),
        3) Tesseract OCR fallback.
        """
        # 1. pypdf text extraction
        try:
            text = reader.pages[page_idx].extract_text() or ""
            if text.strip() and len(text.strip()) > 50:
                return text
        except Exception as _e:
            text = ""

        # 2. Vision OCR (if engine provided and text is poor)
        if vision_engine and (not text.strip() or len(text.strip()) < 50):
            self.log(f"  [TOC] Vision OCR attempt for page {page_idx+1}...", "DEBUG")
            try:
                result = vision_engine.process_page(reader.pages[page_idx], page_idx + 1)
                if result.success and result.text.strip():
                    self.log(f"  [TOC] Vision OCR extracted {len(result.text)} chars from page {page_idx+1}", "INFO")
                    return result.text
            except Exception as e:
                self.log(f"  [TOC] Vision OCR failed: {e}", "WARNING")

        # 3. Tesseract OCR fallback
        try:
            import io

            import pytesseract
            from pdf2image import convert_from_bytes
            from PIL import Image
            from pypdf import PdfWriter

            writer = PdfWriter()
            writer.add_page(reader.pages[page_idx])
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)

            poppler_path = self._settings.get("paths.poppler") or None
            images = convert_from_bytes(
                buf.getvalue(),
                first_page=1,
                last_page=1,
                dpi=300,
                poppler_path=poppler_path,
            )
            if images:
                tesseract_cmd = self._settings.get(
                    "paths.tesseract",
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                )
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                ocr_text = pytesseract.image_to_string(images[0], lang="eng+fas")
                if ocr_text.strip():
                    self.log(f"  [TOC] Tesseract OCR extracted {len(ocr_text)} chars from page {page_idx+1}", "INFO")
                    return ocr_text
        except ImportError:
            pass
        except Exception as e:
            self.log(f"  [TOC] Tesseract OCR failed: {e}", "DEBUG")

        return text

    # ─────────────────────────────────────────────────────────────────────────
    # Roman numeral parser (Phase 3.1)
    # ─────────────────────────────────────────────────────────────────────────

    def _roman_to_int(self, roman: str) -> int:
        roman = roman.upper()
        values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
        total = 0
        prev = 0
        for ch in reversed(roman):
            val = values.get(ch, 0)
            if val < prev:
                total -= val
            else:
                total += val
            prev = val
        return total

    def _map_roman_page(self, roman_str: str, page_labels: list[str] | None = None) -> int:
        roman_str = roman_str.strip().upper()
        if not roman_str:
            return 0

        if page_labels:
            for idx, label in enumerate(page_labels):
                if label and label.strip().upper() == roman_str:
                    return idx + 1

        try:
            return self._roman_to_int(roman_str)
        except Exception as _e:
            return 0

    def _parse_roman_numerals(
        self,
        lines: list[str],
        total_pages: int,
        page_labels: list[str] | None = None,
    ) -> list[tuple[str, int]]:
        entries = []
        seen = set()
        for line in lines:
            s = line.strip()
            if not s or len(s) < 4 or self.TOC_PAGE_PATTERN.match(s) or self.NOISE.match(s):
                continue

            m = self.ROMAN_NUMERAL_PATTERN.match(s)
            if not m:
                continue

            roman_str = m.group('roman')
            title = m.group('title').strip()

            page_num = self._map_roman_page(roman_str, page_labels)

            if page_num < 1 or page_num > total_pages:
                if page_num > total_pages:
                    self.log(f"[TOC] Roman numeral '{roman_str}' maps to {page_num} > {total_pages}; treating as chapter number (page=0).", "DEBUG")
                    page_num = 0
                else:
                    continue

            if title and page_num >= 0:
                key = title.lower()
                if key not in seen:
                    seen.add(key)
                    entries.append((title, page_num))

        if entries:
            self.log(f"[TOC] Roman numeral parser: extracted {len(entries)} entries.", "INFO")
        return entries

    # ─────────────────────────────────────────────────────────────────────────
    # ADAPTIVE OFFSET DETECTION AND CORRECTION (NEW)
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_and_correct_offset(
        self,
        toc_entries: list[tuple[str, int]],
        markdown_text: str,
        page_markers: list[tuple[int, int]],
    ) -> list[tuple[str, int]]:
        """
        Detect and correct page offsets adaptively.
        Computes offset per entry by locating the heading in the markdown,
        then clusters offsets and applies the correct offset to each cluster.
        This handles front‑matter offsets separately from body offsets.
        """
        if not toc_entries or len(toc_entries) < 3:
            return toc_entries

        if not markdown_text or not page_markers:
            return toc_entries

        # Build marker map: page -> char position
        marker_map = {p: pos for p, pos in page_markers}
        total_pages = max(marker_map.keys()) if marker_map else 1

        # Prepare lines and fuzzy matching helpers
        lines = markdown_text.splitlines()
        total_lines = len(lines)

        # We'll compute actual page for each entry by locating the heading
        entry_offsets = []  # list of (heading, toc_page, actual_page, offset)
        for heading, toc_page in toc_entries:
            if toc_page <= 0 or toc_page > total_pages:
                continue

            # Try to find the heading in the markdown using fuzzy search
            # Use a window around the TOC page
            estimated_line = int((toc_page / total_pages) * total_lines)
            start_line = max(0, estimated_line - 200)
            end_line = min(total_lines - 1, estimated_line + 200)

            # Build candidate headings in that window
            candidates = []
            for i in range(start_line, end_line + 1):
                stripped = lines[i].strip()
                if is_likely_heading(stripped):
                    candidates.append((i, stripped))

            if not candidates:
                # Fallback to global search
                candidates = get_heading_candidates(lines, 0, total_lines - 1)

            # Fuzzy match
            matched_line, matched_text, score, _ = fuzzy_match_heading(
                heading, candidates, thresholds=[0.75, 0.65], use_rapidfuzz=True
            )

            if matched_line is None:
                # Could not locate – keep original page
                entry_offsets.append((heading, toc_page, toc_page, 0))
                continue

            # Find actual page from marker map by character position
            # Compute char position of matched line
            char_pos = 0
            for i in range(matched_line):
                char_pos += len(lines[i]) + 1  # +1 for newline

            # Binary search in marker_map to find page
            actual_page = 1
            for p, pos in sorted(marker_map.items()):
                if pos <= char_pos:
                    actual_page = p
                else:
                    break
            actual_page = max(1, min(actual_page, total_pages))

            offset = actual_page - toc_page
            entry_offsets.append((heading, toc_page, actual_page, offset))

        if not entry_offsets:
            return toc_entries

        # ---- Cluster offsets ----
        # We want to group entries that have the same (or very similar) offset.
        # Offsets are integers; we'll group if difference <= 2.
        offsets = [e[3] for e in entry_offsets]
        if not offsets:
            return toc_entries

        # Simple clustering: sort by offset and find gaps > 2
        sorted_offsets = sorted(set(offsets))
        clusters = []
        current_cluster = [sorted_offsets[0]]
        for off in sorted_offsets[1:]:
            if off - current_cluster[-1] <= 2:
                current_cluster.append(off)
            else:
                clusters.append(current_cluster)
                current_cluster = [off]
        clusters.append(current_cluster)

        # Build mapping: offset -> cluster median
        offset_to_median = {}
        for cluster in clusters:
            median = cluster[len(cluster) // 2]  # approximate median
            for off in cluster:
                offset_to_median[off] = median

        # Now apply correction
        corrected = []
        for heading, toc_page, actual_page, raw_offset in entry_offsets:
            # Determine if this entry should be corrected
            # If the raw_offset is in offset_to_median, apply the median
            # Otherwise, keep original (no correction)
            if raw_offset in offset_to_median:
                median_offset = offset_to_median[raw_offset]
                if median_offset != 0:
                    new_page = toc_page + median_offset
                    new_page = max(1, min(new_page, total_pages))
                    self.log(
                        f"[TOC] Adaptive offset: '{heading[:40]}' TOC p.{toc_page} → "
                        f"p.{new_page} (offset {median_offset:+d})",
                        "DEBUG"
                    )
                    corrected.append((heading, new_page))
                else:
                    corrected.append((heading, toc_page))
            else:
                corrected.append((heading, toc_page))

        # If we corrected any entries, log summary
        if any(c[1] != toc_entries[i][1] for i, c in enumerate(corrected)):
            self.log("[TOC] Adaptive offset correction applied to entries with consistent offsets.", "INFO")

        return corrected

    # ─────────────────────────────────────────────────────────────────────────
    # Scoring function (Phase 2.1)
    # ─────────────────────────────────────────────────────────────────────────

    def _score_parser_result(self, entries: list[tuple[str, int]], total_pages: int) -> float:
        if not entries:
            return 0.0

        valid_count = sum(1 for _, p in entries if 1 <= p <= total_pages)
        valid_ratio = valid_count / len(entries)

        pages = [p for _, p in entries if 1 <= p <= total_pages]
        is_sequential = False
        if pages and len(pages) >= 2 and total_pages > 100:
            sorted_pages = sorted(pages)
            if sorted_pages[0] <= 2:
                is_sequential = True
                for i in range(1, len(sorted_pages)):
                    if sorted_pages[i] - sorted_pages[i-1] != 1:
                        is_sequential = False
                        break
                if is_sequential:
                    self.log("[TOC] Detected sequential chapter numbers (penalty applied)", "DEBUG")

        entry_bonus = 0.0
        if valid_ratio >= 0.7:
            entry_bonus = min(20.0, len(entries) / 2.5)

        base_score = valid_ratio * 80.0
        if is_sequential:
            base_score *= 0.7

        score = min(100.0, base_score + entry_bonus)
        return score

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing strategies (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_single_line(self, lines, total_pages) -> list[tuple[str, int]]:
        entries, seen = [], set()
        for line in lines:
            s = line.strip()
            if not s or len(s) < 4 or self.TOC_PAGE_PATTERN.match(s) or self.NOISE.match(s):
                continue
            for pat in self.ENTRY_PATTERNS:
                m = pat.match(s)
                if not m:
                    continue
                heading = re.sub(r' {2,}', ' ', m.group(1).strip()).strip()
                page_num = int(m.group(2))
                if len(heading) < 3 or not (1 <= page_num <= total_pages):
                    continue
                key = (heading.lower(), page_num)
                if key not in seen:
                    seen.add(key)
                    entries.append((heading, page_num))
                break
        entries.sort(key=lambda x: x[1])
        return entries

    def _parse_multiline(self, lines, total_pages) -> list[tuple[str, int]]:
        entries, seen = [], set()
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            i += 1
            if not s or self.TOC_PAGE_PATTERN.match(s) or self.NOISE.match(s):
                continue
            if not self.CHAPTER_LIKE.match(s) or len(s.split()) < 2:
                continue
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines):
                continue
            nxt = lines[j].strip()
            m = re.match(r'^(\d{1,4})\s*$', nxt)
            if not m:
                continue
            page_num = int(m.group(1))
            if not (1 <= page_num <= total_pages):
                continue
            heading = re.sub(r' {2,}', ' ', s).strip()
            key = (heading.lower(), page_num)
            if key not in seen:
                seen.add(key)
                entries.append((heading, page_num))
            i = j + 1
        entries.sort(key=lambda x: x[1])
        return entries

    def _parse_column_layout(self, lines, total_pages) -> list[tuple[str, int]]:
        headings, pages = [], []
        for line in lines:
            s = line.strip()
            if not s or self.TOC_PAGE_PATTERN.match(s) or self.NOISE.match(s):
                continue
            m = re.match(r'^(\d{1,4})\s*$', s)
            if m:
                n = int(m.group(1))
                if 1 <= n <= total_pages:
                    pages.append(n)
                continue
            if self.CHAPTER_LIKE.match(s) and len(s.split()) >= 2:
                headings.append(re.sub(r' {2,}', ' ', s).strip())

        if not headings or not pages:
            return []
        min_len = min(len(headings), len(pages))
        if min_len == 0 or abs(len(headings) - len(pages)) > 3:
            return []
        self.log(f"[TOC] Column layout detected: {len(headings)} titles, {len(pages)} pages", "INFO")
        entries = [(headings[i], pages[i]) for i in range(min_len) if 1 <= pages[i] <= total_pages]
        entries.sort(key=lambda x: x[1])
        return entries

    def _parse_three_line(self, lines: list[str], total_pages: int) -> list[tuple[str, int]]:
        entries = []
        seen = set()
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            num_match = re.match(r"^(\d{1,4})\s*$", s)
            if num_match:
                page_num = int(num_match.group(1))
                if 1 <= page_num <= total_pages:
                    j = i - 1
                    heading = ""
                    while j >= 0 and not lines[j].strip():
                        j -= 1
                    if j >= 0:
                        candidate = lines[j].strip()
                        if (not self.NOISE.match(candidate) and
                            not re.match(r'^\d+$', candidate) and
                            len(candidate) > 3):
                            heading = candidate
                    if heading:
                        heading = re.sub(r' {2,}', ' ', heading).strip()
                        if heading.lower() not in seen:
                            seen.add(heading.lower())
                            entries.append((heading, page_num))
                    i += 1
                else:
                    i += 1
            else:
                i += 1
        entries.sort(key=lambda x: x[1])
        if entries:
            self.log(f"[TOC] Strategy 3 (three-line): extracted {len(entries)} entries.", "INFO")
        return entries

    def _parse_numbered_sections(self, lines: list[str], total_pages: int) -> list[tuple[str, int]]:
        entries = []
        seen = set()
        page_numbers = []
        for line in lines:
            s = line.strip()
            if re.match(r'^\d{1,4}\s*$', s):
                p = int(s)
                if 1 <= p <= total_pages:
                    page_numbers.append(p)

        page_index = 0
        for i, line in enumerate(lines):
            s = line.strip()
            m = self.NUMBERED_SECTION.match(s)
            if m:
                num = int(m.group(1))
                title = m.group(2).strip()
                page_num = 0
                num_at_end = re.search(r'\b(\d{1,4})\b$', s)
                if num_at_end:
                    p = int(num_at_end.group(1))
                    if 1 <= p <= total_pages:
                        page_num = p
                else:
                    if i + 1 < len(lines):
                        nxt = lines[i+1].strip()
                        if re.match(r'^\d{1,4}\s*$', nxt):
                            p = int(nxt)
                            if 1 <= p <= total_pages:
                                page_num = p
                if page_num == 0 and page_index < len(page_numbers):
                    page_num = page_numbers[page_index]
                    page_index += 1
                heading = f"{num} - {title}"
                if heading.lower() not in seen:
                    seen.add(heading.lower())
                    entries.append((heading, page_num if page_num else 0))
        entries.sort(key=lambda x: x[1])
        if entries:
            self.log(f"[TOC] Strategy 5 (numbered sections): extracted {len(entries)} entries.", "INFO")
        return entries

    def _parse_headings_only(self, lines: list[str], total_pages: int) -> list[tuple[str, int]]:
        entries = []
        seen = set()
        pending = ""
        for raw in lines:
            s = raw.strip()
            if not s or self.TOC_PAGE_PATTERN.match(s) or self.NOISE.match(s):
                if pending:
                    h = re.sub(r' {2,}', ' ', pending).strip()
                    page_num = 0
                    num_match = re.search(r'\b(\d{1,4})\b', pending)
                    if num_match:
                        page_num = int(num_match.group(1))
                        if not (1 <= page_num <= total_pages):
                            page_num = 0
                    if h.lower() not in seen:
                        seen.add(h.lower())
                        entries.append((h, page_num if page_num else 0))
                    pending = ""
                continue
            if re.match(r"^\d{1,4}\s*$", s):
                if pending:
                    page_num = int(s)
                    if 1 <= page_num <= total_pages:
                        h = re.sub(r" {2,}", " ", pending).strip()
                        if h.lower() not in seen:
                            seen.add(h.lower())
                            entries.append((h, page_num))
                        pending = ""
                continue
            if self.CHAPTER_LIKE.match(s) or self.NUMBERED_SECTION.match(s):
                if pending:
                    h = re.sub(r" {2,}", " ", pending).strip()
                    page_num = 0
                    num_match = re.search(r'\b(\d{1,4})\b', pending)
                    if num_match:
                        page_num = int(num_match.group(1))
                        if not (1 <= page_num <= total_pages):
                            page_num = 0
                    if h.lower() not in seen:
                        seen.add(h.lower())
                        entries.append((h, page_num if page_num else 0))
                pending = s
            else:
                _SECTION_STARTERS = re.compile(
                    r"^(About|Also|Acknowledgment|Index|Bibliography|References|"
                    r"Appendix|Credits|Notes|Further|Epilogue|Afterword|Glossary|"
                    r"Dedication|Copyright|Preface|Foreword)\b",
                    re.IGNORECASE,
                )
                if (pending and len(s.split()) >= 2
                        and not re.match(r"^[A-Z][A-Z\s]+$", s)
                        and not _SECTION_STARTERS.match(s)):
                    pending = pending + " " + s
        if pending:
            h = re.sub(r" {2,}", " ", pending).strip()
            page_num = 0
            num_match = re.search(r'\b(\d{1,4})\b', pending)
            if num_match:
                page_num = int(num_match.group(1))
                if not (1 <= page_num <= total_pages):
                    page_num = 0
            if h.lower() not in seen:
                entries.append((h, page_num if page_num else 0))
        return entries

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _find_toc_page(self, reader, scan_limit: int) -> int | None:
        for idx in range(scan_limit):
            try:
                text = reader.pages[idx].extract_text() or ""
                if not text.strip():
                    text = self._extract_page_text(reader, idx, vision_engine=None)
                if self.TOC_PAGE_PATTERN.search(text):
                    return idx
            except Exception as _e:
                continue
        return None

    def _looks_like_body(self, lines: list[str]) -> bool:
        return sum(1 for l in lines if len(l.strip()) > 90) > 3

    # ─────────────────────────────────────────────────────────────────────────
    # Validation and Correction (Phase 1.1 + Phase 3.1)
    # ─────────────────────────────────────────────────────────────────────────

    def _is_likely_chapter_number_sequence(self, page_numbers: list[int], total_pages: int) -> bool:
        if not page_numbers or total_pages <= 50:
            return False
        if any(p > 30 for p in page_numbers):
            return False
        sorted_nums = sorted(page_numbers)
        for i in range(1, len(sorted_nums)):
            if sorted_nums[i] - sorted_nums[i-1] != 1:
                return False
        if sorted_nums[0] > 3:
            return False
        return True

    def validate_and_correct(
        self,
        toc_entries: list[tuple[str, int]],
        total_pages: int,
        markdown_text: str | None = None,
        page_markers: list[tuple[int, int]] | None = None,
    ) -> list[tuple[str, int]]:
        if not toc_entries:
            return []

        pages = [p for _, p in toc_entries if p > 0]
        if not pages:
            return toc_entries

        if self._is_likely_chapter_number_sequence(pages, total_pages):
            self.log(
                "[TOC] Page numbers appear to be chapter numbers (sequential, <=30). "
                "Setting page numbers to 0; segmenter will locate by heading matching.",
                "WARNING"
            )
            return [(h, 0) for h, _ in toc_entries]

        corrected = []
        for heading, page in toc_entries:
            if page < 1 or page > total_pages:
                new_page = 1 if page < 1 else total_pages
                self.log(
                    f"[TOC] Page number {page} for '{heading[:40]}' out of range ({total_pages} total). Clamping to {new_page}.",
                    "WARNING"
                )
                page = new_page
            corrected.append((heading, page))

        if markdown_text is not None and page_markers is not None and page_markers:
            corrected = self._detect_and_correct_offset(corrected, markdown_text, page_markers)

        if markdown_text is not None and page_markers is not None and page_markers:
            marker_map = {p: pos for p, pos in page_markers}
            anchored = []
            for heading, page in corrected:
                if page == 0:
                    anchored.append((heading, page))
                    continue
                pattern = re.compile(r'^#+\s*' + re.escape(heading.strip()) + r'\s*$', re.MULTILINE | re.IGNORECASE)
                match = pattern.search(markdown_text)
                if match:
                    pos = match.start()
                    nearest_page = 1
                    for p, marker_pos in sorted(marker_map.items()):
                        if marker_pos <= pos:
                            nearest_page = p
                        else:
                            break
                    if nearest_page != page:
                        self.log(
                            f"[TOC] Anchored '{heading[:40]}': TOC page {page} → actual page {nearest_page}",
                            "INFO"
                        )
                        page = nearest_page
                anchored.append((heading, page))
            corrected = anchored

        return corrected

    # ─────────────────────────────────────────────────────────────────────────
    # locate_headings – matches TOC entries to actual markdown lines
    # Uses shared heading_utils (normalize_heading, fuzzy_match_heading)
    # ─────────────────────────────────────────────────────────────────────────

    def locate_headings(
        self,
        toc_entries: list[tuple[str, int]],
        markdown_text: str,
        page_markers: list[tuple[int, int]],
    ) -> TOCResult:
        """
        For each TOC entry, find its actual line number in the full Markdown.
        Uses:
        - Page markers if available (search within 200 lines after marker).
        - Page‑based estimation if no marker.
        - Progressive fuzzy thresholds (0.85, 0.75, 0.65).
        - Dynamic fallback: search after first 150 lines, then full global.

        Returns a TOCResult with entries containing line numbers and match details.
        """
        if not toc_entries:
            return TOCResult(entries=[], method="none", confidence=0.0, validation_report="No TOC entries")

        # Convert toc_entries to TOCEntry objects if they aren't already
        entries = []
        for h, p in toc_entries:
            entries.append(TOCEntry(title=h, page=p if p > 0 else None))

        total_lines = len(markdown_text.splitlines())
        total_pages = max(1, max((e.page for e in entries if e.page is not None), default=1))

        # Build marker map
        marker_map = self._build_marker_map(markdown_text)

        # ---- Build expanded candidate list using heading_utils ----
        markdown_lines = markdown_text.splitlines()
        candidates = get_heading_candidates(markdown_lines)

        # ---- Define progressive thresholds ----
        thresholds = [0.85, 0.75, 0.65]

        # ---- Process each entry ----
        for entry in entries:
            if entry.page is None:
                continue

            # 1. Try page marker if available
            marker_line = marker_map.get(entry.page)
            start_line = None
            end_line = None

            if marker_line is not None:
                start_line = marker_line
                end_line = min(marker_line + 200, total_lines - 1)
            else:
                # 2. Estimate line number from page
                estimated_line = int((entry.page / total_pages) * total_lines)
                start_line = max(0, estimated_line - 150)
                end_line = min(total_lines - 1, estimated_line + 150)

            # Candidates in window
            window_candidates = [(ln, txt) for ln, txt in candidates if start_line <= ln <= end_line]

            # If window empty, use fallback
            if not window_candidates:
                window_candidates = [(ln, txt) for ln, txt in candidates if ln > 150]  # skip TOC

            # ---- Progressive matching using shared fuzzy_match_heading ----
            matched_line, matched_text, best_score, match_method = fuzzy_match_heading(
                entry.title,
                window_candidates,
                thresholds=thresholds,
                use_rapidfuzz=True,
            )

            if matched_line is not None:
                entry.line = matched_line
                entry.is_heading_found = True
                entry.confidence = min(1.0, entry.confidence + 0.1)
                entry.match_method = match_method
            else:
                # ---- Global fallback: search all candidates (skip first 150) ----
                global_candidates = [(ln, txt) for ln, txt in candidates if ln > 150]
                if not global_candidates:
                    global_candidates = candidates  # full global as last resort

                matched_line, matched_text, best_score, match_method = fuzzy_match_heading(
                    entry.title,
                    global_candidates,
                    thresholds=[0.65, 0.55],  # Lower thresholds for global search
                    use_rapidfuzz=True,
                )

                if matched_line is not None:
                    entry.line = matched_line
                    entry.is_heading_found = True
                    entry.confidence = min(1.0, entry.confidence + 0.1)
                    entry.match_method = match_method
                else:
                    entry.is_heading_found = False
                    entry.confidence = max(0.0, entry.confidence - 0.1)
                    entry.match_method = "failed"

        # ---- Recompute overall confidence ----
        found = sum(1 for e in entries if e.is_heading_found)
        confidence = found / len(entries) if entries else 0.0

        # ---- Detailed validation report with match methods ----
        method_counts = {}
        for e in entries:
            method_counts[e.match_method] = method_counts.get(e.match_method, 0) + 1
        report_parts = []
        for method, count in sorted(method_counts.items(), key=lambda x: x[1], reverse=True):
            report_parts.append(f"{count} via {method}")
        validation_report = (
            f"TOC entries: {len(entries)}, located: {found}/{len(entries)} "
            f"({found/len(entries)*100:.1f}%) | " + ", ".join(report_parts)
        )

        method = "rule_based"
        return TOCResult(
            entries=entries,
            method=method,
            confidence=confidence,
            validation_report=validation_report
        )

    def _build_marker_map(self, markdown_text: str) -> dict[int, int]:
        """Build a dict mapping page number to its first line number in the Markdown."""
        markers = {}
        lines = markdown_text.splitlines()
        for line_no, line in enumerate(lines):
            m = re.search(r'<!-- original page (\d+) -->', line)
            if m:
                page = int(m.group(1))
                if page not in markers:  # keep the first occurrence
                    markers[page] = line_no
        return markers

