from core.models import TOCEntry, TOCResult

"""
Adaptive Table of Contents extractor – multi‑stage pipeline.

Stages:
1. Extract internal PDF outlines (bookmarks) – 100% accurate when present.
2. LLM‑based semantic extraction from the first 30 pages of Markdown.
3. Statistical heading clustering from the entire text.
4. Regex fallback (generic).

Returns a TOCResult with confidence score and method used.
"""

import copy
import json
import logging
import re
import threading
from collections import OrderedDict

# Optional: for clustering (Stage 3) – we use a simple density‑based fallback
from dataclasses import dataclass
from pathlib import Path

import pypdf
from markitdown import MarkItDown
from rapidfuzz import fuzz

# V18.20.4.11 (P3 / O-c5): pooled LLM transport (localhost → no-proxy
# pooled session, cloud → proxy-trusting pooled session).
from utils.network import session_for_url

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# V18.20.4.8 (P6 / O-c3): in-memory TOC LLM result cache.
#
# The Stage-2 LLM call re-extracted the same PDF's TOC on every run when
# nothing had changed (same input file, same model, same page-window) —
# the single most expensive re-run cost after OCR. The cache below is a
# per-process, FIFO-capped dict keyed by (resolved input path + mtime +
# size for BOTH the pdf and the markdown side-car, model, page-window).
# Fail-soft by construction: every cache read/write is wrapped and a miss
# (or any error) simply falls through to the real LLM call. Only
# SUCCESSFUL extractions are cached — a transient failure must retry on
# the next run, not be remembered. Entries are stored/returned as COPIES
# so locate_headings() mutating the returned TOCEntry objects can never
# poison a cached result.
# ─────────────────────────────────────────────────────────────────────────────

# Stage-2 prompt window: first ~30 pages (≈ first 2000 markdown lines).
_LLM_WINDOW_LINES = 2000

_TOC_LLM_RESULT_CACHE: "OrderedDict[tuple, list]" = OrderedDict()
_TOC_LLM_CACHE_LOCK = threading.Lock()
_TOC_LLM_CACHE_MAX = 16  # FIFO cap — a session converting >16 distinct PDFs evicts oldest


def _toc_llm_cache_key(pdf_path, md_path, model: str, window: int):
    """Build the TOC-LLM cache key; ``None`` → bypass the cache (fail-soft).

    The key covers every input that changes the LLM response: the resolved
    input path + mtime + size (pdf and, when present, the markdown
    side-car that actually feeds the prompt), the resolved model, and the
    page-window bound. Unreadable/missing inputs return ``None`` so they
    are never cached.
    """
    try:
        if pdf_path is None:
            return None
        pdf = Path(pdf_path)
        pdf_st = pdf.stat()
        pdf_sig = (str(pdf.resolve()), pdf_st.st_mtime_ns, pdf_st.st_size)
        md_sig = None
        if md_path is not None:
            mdp = Path(md_path)
            if mdp.exists():
                md_st = mdp.stat()
                md_sig = (str(mdp.resolve()), md_st.st_mtime_ns, md_st.st_size)
            else:
                md_sig = ("absent",)
        return (pdf_sig, md_sig, str(model), int(window))
    except Exception:
        return None


def _toc_llm_cache_get(key):
    """Cache read (fail-soft). Returns a list of entry COPIES or None."""
    if key is None:
        return None
    try:
        with _TOC_LLM_CACHE_LOCK:
            if key in _TOC_LLM_RESULT_CACHE:
                _TOC_LLM_RESULT_CACHE.move_to_end(key)
                return [copy.copy(e) for e in _TOC_LLM_RESULT_CACHE[key]]
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)  # never break conversion
    return None


def _toc_llm_cache_put(key, entries) -> None:
    """Cache write (fail-soft). Only successful non-empty extractions."""
    if key is None or not entries:
        return
    try:
        snapshot = [copy.copy(e) for e in entries]
        with _TOC_LLM_CACHE_LOCK:
            _TOC_LLM_RESULT_CACHE[key] = snapshot
            _TOC_LLM_RESULT_CACHE.move_to_end(key)
            while len(_TOC_LLM_RESULT_CACHE) > _TOC_LLM_CACHE_MAX:
                _TOC_LLM_RESULT_CACHE.popitem(last=False)
    except Exception as _e:
        logger.debug("ignored %s: %s", type(_e).__name__, _e)  # never break conversion


def clear_toc_llm_cache() -> int:
    """Test/ops hook: drop every cached TOC-LLM result. Returns entry count."""
    with _TOC_LLM_CACHE_LOCK:
        n = len(_TOC_LLM_RESULT_CACHE)
        _TOC_LLM_RESULT_CACHE.clear()
    return n


@dataclass
class TOCEntry:
    title: str
    page: int | None = None          # printed page number (if available)
    line: int | None = None          # line number in Markdown (if located)
    confidence: float = 1.0             # how sure we are this is correct
    is_heading_found: bool = False      # whether we later matched it in text
    match_method: str = ""              # "exact", "normalised", "fuzzy_0.85", "fuzzy_0.75", "fuzzy_0.65", "failed"


@dataclass
class TOCResult:
    entries: list[TOCEntry]
    method: str                         # "outlines", "llm", "clustering", "regex"
    confidence: float                   # overall confidence 0-1
    validation_report: str


class AdaptiveTOCExtractor:
    def __init__(self, pdf_path: Path, md_path: Path | None = None):
        self.pdf_path = pdf_path
        self.md_path = md_path
        self.md_text = None
        self.md_lines = None
        self._load_markdown()

    def _load_markdown(self):
        """Convert PDF to Markdown if not already done, or load existing."""
        if self.md_path and self.md_path.exists():
            self.md_text = self.md_path.read_text(encoding='utf-8')
        else:
            md = MarkItDown()
            self.md_text = md.convert(str(self.pdf_path)).text_content
            if self.md_path:
                self.md_path.write_text(self.md_text, encoding='utf-8')
        self.md_lines = self.md_text.splitlines()

    # -----------------------------------------------------------------
    # Stage 1: Extract PDF Outlines (Bookmarks)
    # -----------------------------------------------------------------
    def _extract_outlines(self) -> list[TOCEntry] | None:
        """Use pypdf to read internal bookmarks."""
        try:
            reader = pypdf.PdfReader(self.pdf_path)
            outlines = reader.outline
            if not outlines:
                return None

            def flatten(outline_list, level=0):
                entries = []
                for item in outline_list:
                    if isinstance(item, pypdf.generic.Destination):
                        title = item.title
                        page = reader.get_destination_page_number(item) + 1  # 1‑based
                        entries.append(TOCEntry(title=title, page=page, confidence=1.0))
                    elif isinstance(item, list):
                        entries.extend(flatten(item, level+1))
                return entries

            raw = flatten(outlines)
            if not raw:
                return None
            # Remove duplicates (sometimes bookmarks repeat)
            seen = set()
            unique = []
            for e in raw:
                key = (e.title, e.page)
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            return unique
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return None

    # -----------------------------------------------------------------
    # Stage 2: LLM‑Based Extraction
    # -----------------------------------------------------------------
    def _extract_with_llm(self) -> list[TOCEntry] | None:
        """Send first 30 pages of Markdown to local LLM and ask for JSON TOC.

        V18.20.4.8 (P6 / O-c3): result is cached per (resolved input path,
        file mtime, model, page-window) — see ``_toc_llm_cache_key``. A hit
        skips the LLM call entirely; the cache only stores successful
        extractions and every read/write is fail-soft.
        """
        # Get first ~30 pages (roughly 30*50 lines = 1500 lines, but safer: first 2000 lines)
        front = self.md_lines[:_LLM_WINDOW_LINES]
        text = "\n".join(front)

        from core.summarisation.prompt_manager import PromptManager
        _pm = PromptManager()
        prompt = _pm.render_template(
            "pdf/adaptive_toc_extract",
            text=text,
        )
        if not prompt:
            return None
        # Call Ollama
        # V18.20.4.11 (P3 / O-c5): local `import requests` removed — unused after the pooled-transport swap
        # V18.20.4.3 (P2 / W-c7 + W-c9): this was the ONLY requests call
        # in the tree with NO timeout (a half-open connection hung the TOC
        # stage forever - no cancel path reaches it), a hardcoded model
        # (llama3.1:8b - not installed on the rig) and a hardcoded URL.
        # All three now resolve from Settings, mirroring the toc_extractor
        # pattern: fast model -> summarisation model -> literal; canonical
        # get_ollama_url(); ocr.timeout (120s default) as the bound.
        try:
            from utils.settings import Settings
            _s = Settings()
            _model = _s.get(
                "summarisation.fast_model",
                _s.get("summarisation.model", "llama3.1:8b"),
            )
            _url = _s.get_ollama_url()
            _timeout = int(_s.get("ocr.timeout", 120) or 120)
        except Exception:
            _model, _url, _timeout = "llama3.1:8b", "http://localhost:11434", 120
        # V18.20.4.8 (P6 / O-c3): same PDF + same model + same window →
        # reuse the previous successful extraction (fail-soft; the key
        # includes file mtime/size so any input change re-extracts).
        _cache_key = _toc_llm_cache_key(
            getattr(self, "pdf_path", None),
            getattr(self, "md_path", None),
            _model,
            _LLM_WINDOW_LINES,
        )
        _cached = _toc_llm_cache_get(_cache_key)
        if _cached is not None:
            logger.debug(
                "TOC LLM cache HIT (model=%s, window=%d lines) — extraction skipped",
                _model, _LLM_WINDOW_LINES,
            )
            return _cached
        try:
            # V18.20.4.11 (P3 / O-c5): pooled transport - same timeout
            # (bounded by ocr.timeout per W-c7) and same status handling;
            # connection reuse added.
            response = session_for_url(_url).post(
                f"{_url}/api/generate",
                json={"model": _model, "prompt": prompt, "stream": False},
                timeout=_timeout,
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
            _toc_llm_cache_put(_cache_key, entries)
            return entries if entries else None
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
            return None

    # -----------------------------------------------------------------
    # Stage 3: Statistical Heading Clustering (No TOC)
    # -----------------------------------------------------------------
    def _extract_by_clustering(self) -> list[TOCEntry] | None:
        """
        Scan entire Markdown for candidate headings, then cluster by line density.
        Each cluster becomes a chapter start.
        """
        # Heuristic: lines that are short, not in code blocks, and look like headings
        candidates = []
        for i, line in enumerate(self.md_lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip code blocks, tables, etc.
            if stripped.startswith('```') or stripped.startswith('|'):
                continue
            # Heuristic: length between 5 and 200 chars, and either:
            # - starts with # (Markdown heading)
            # - is all caps
            # - contains "Chapter", "Part", "Section", etc.
            if len(stripped) < 5 or len(stripped) > 200:
                continue
            if (stripped.startswith('#') or
                stripped.isupper() or
                any(key in stripped for key in ["Chapter", "Part", "Section", "CHAPTER", "PART", "SECTION"])):
                # Record line number and page estimate (if we have page markers)
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
                # start new cluster
                # use the first candidate of the cluster as the heading
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

    # -----------------------------------------------------------------
    # Stage 4: Regex Fallback
    # -----------------------------------------------------------------
    def _extract_with_regex(self) -> list[TOCEntry] | None:
        """
        Generic regex to catch lines with trailing page numbers (e.g., "Title .... 12").
        """
        # Use a broad pattern: any line ending with numbers after dots/spaces.
        pattern = re.compile(r'^(.*?)(?:\s*\.{2,}|\s+)\s*(\d+)\s*$')
        entries = []
        for line in self.md_lines[:500]:  # only first 50 pages
            m = pattern.match(line.strip())
            if m:
                title = m.group(1).strip()
                page = int(m.group(2))
                entries.append(TOCEntry(title=title, page=page, confidence=0.3))
        return entries if entries else None

    # -----------------------------------------------------------------
    # Helper: build page markers dict
    # -----------------------------------------------------------------
    def _build_marker_map(self) -> dict[int, int]:
        """Build a dict mapping page number to its first line number in the Markdown."""
        markers = {}
        for line_no, line in enumerate(self.md_lines):
            m = re.search(r'<!-- original page (\d+) -->', line)
            if m:
                page = int(m.group(1))
                if page not in markers:  # keep the first occurrence
                    markers[page] = line_no
        return markers

    # -----------------------------------------------------------------
    # Main extraction method
    # -----------------------------------------------------------------
    def extract(self) -> TOCResult:
        """Run stages in order, return first successful with confidence."""
        # Stage 1
        entries = self._extract_outlines()
        if entries:
            return TOCResult(entries=entries, method="outlines", confidence=1.0, validation_report="")

        # Stage 2
        entries = self._extract_with_llm()
        if entries:
            # Validate: check monotonic pages and enough entries
            pages = [e.page for e in entries if e.page is not None]
            if len(entries) >= 5 and all(pages[i] < pages[i+1] for i in range(len(pages)-1)):
                return TOCResult(entries=entries, method="llm", confidence=0.9, validation_report="LLM extraction passed monotonic check")

        # Stage 3
        entries = self._extract_by_clustering()
        if entries and len(entries) >= 3:
            return TOCResult(entries=entries, method="clustering", confidence=0.5, validation_report="Clustering-based segmentation (no page numbers)")

        # Stage 4
        entries = self._extract_with_regex()
        if entries and len(entries) >= 3:
            return TOCResult(entries=entries, method="regex", confidence=0.3, validation_report="Regex fallback used")

        # If all fail, return empty with low confidence
        return TOCResult(entries=[], method="none", confidence=0.0, validation_report="All extraction methods failed")

    # -----------------------------------------------------------------
    # Improved Normalization
    # -----------------------------------------------------------------
    def _normalize_heading(self, heading: str) -> str:
        """
        Aggressively normalise a heading for matching:
        - Remove leading "Chapter", "Part", "Section" prefixes with numbers/roman.
        - Remove leading numbers and separators.
        - Remove trailing punctuation.
        - Collapse spaces and lower-case.
        """
        h = heading.strip()
        # Remove common prefixes with numbers/roman: "Chapter 1", "Part II", "Section 3", etc.
        h = re.sub(r'^(?:Chapter|Part|Section|Appendix|فصل|بخش)\s+[IVX\d]+\s*[-–—:.]?\s*', '', h, flags=re.IGNORECASE)
        # Remove standalone numbers at start: "1 - ", "1. ", etc.
        h = re.sub(r'^\d+\s*[-–—.:]\s*', '', h)
        # Remove trailing punctuation
        h = re.sub(r'[:.\-–—]\s*$', '', h)
        # Collapse multiple spaces
        h = re.sub(r'\s+', ' ', h)
        return h.strip().lower()

    # -----------------------------------------------------------------
    # Enhanced Heading Location (with progressive fuzzy and dynamic skip)
    # -----------------------------------------------------------------
    def locate_headings(self, toc_result: TOCResult) -> TOCResult:
        """
        For each TOC entry, find its actual line number in the full Markdown.
        Uses:
        - Page markers if available (search within 200 lines after marker).
        - Page‑based estimation if no marker.
        - Progressive fuzzy thresholds (0.85, 0.75, 0.65).
        - Dynamic fallback: search after first 150 lines, then full global.
        """
        if not toc_result.entries:
            return toc_result

        total_lines = len(self.md_lines)
        total_pages = max(1, max((e.page for e in toc_result.entries if e.page is not None), default=1))

        # Build marker map
        marker_map = self._build_marker_map()

        # ---- Build expanded candidate list ----
        # We now include more types of lines that could be headings.
        candidates = []
        for line_no, line in enumerate(self.md_lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip code blocks, tables, etc.
            if stripped.startswith('```') or stripped.startswith('|'):
                continue
            # Length: 3 to 200 chars (allow short headings like "REFERENCES")
            if len(stripped) < 3 or len(stripped) > 200:
                continue

            is_heading = False
            # 1. Markdown heading
            if stripped.startswith('#') or stripped.isupper() or any(k in stripped for k in ["Chapter", "Part", "Section", "CHAPTER", "PART", "SECTION"]) or (len(stripped) <= 80 and
                  not re.search(r'[.;,]$', stripped) and
                  stripped[0].isupper() and
                  len(stripped.split()) >= 2):
                is_heading = True

            if is_heading:
                candidates.append((line_no, stripped))

        # ---- Define progressive thresholds ----
        thresholds = [0.85, 0.75, 0.65]

        # ---- Process each entry ----
        for entry in toc_result.entries:
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

            # Normalize entry title
            norm_title = entry.title.lower().strip()
            # Remove common prefixes for better matching
            norm_title = self._normalize_heading(entry.title)

            # ---- Progressive matching ----
            best_match = None
            best_score = 0
            best_method = "failed"

            for threshold in thresholds:
                for line_no, cand_text in window_candidates:
                    norm_cand = self._normalize_heading(cand_text)
                    score = fuzz.ratio(norm_title, norm_cand)
                    if score >= threshold and score > best_score:
                        best_score = score
                        best_match = (line_no, cand_text)
                        best_method = f"fuzzy_{threshold:.2f}".replace('.', '_')
                if best_match:
                    break

            if best_match and best_match[0] is not None:
                entry.line = best_match[0]
                entry.is_heading_found = True
                entry.confidence = min(1.0, entry.confidence + 0.1)
                entry.match_method = best_method
            else:
                # ---- Global fallback: search all candidates (skip first 150) ----
                global_candidates = [(ln, txt) for ln, txt in candidates if ln > 150]
                if not global_candidates:
                    global_candidates = candidates  # full global as last resort

                for threshold in thresholds:
                    for line_no, cand_text in global_candidates:
                        norm_cand = self._normalize_heading(cand_text)
                        score = fuzz.ratio(norm_title, norm_cand)
                        if score >= threshold and score > best_score:
                            best_score = score
                            best_match = (line_no, cand_text)
                            best_method = f"global_fuzzy_{threshold:.2f}".replace('.', '_')
                    if best_match:
                        break

                if best_match and best_match[0] is not None:
                    entry.line = best_match[0]
                    entry.is_heading_found = True
                    entry.confidence = min(1.0, entry.confidence + 0.1)
                    entry.match_method = best_method
                else:
                    entry.is_heading_found = False
                    entry.confidence = max(0.0, entry.confidence - 0.1)
                    entry.match_method = "failed"

        # ---- Recompute overall confidence ----
        found = sum(1 for e in toc_result.entries if e.is_heading_found)
        if toc_result.entries:
            toc_result.confidence = found / len(toc_result.entries)
            method_caps = {"outlines": 1.0, "llm": 0.95, "clustering": 0.6, "regex": 0.4, "none": 0.0}
            toc_result.confidence = min(toc_result.confidence, method_caps.get(toc_result.method, 0.5))
        else:
            toc_result.confidence = 0.0

        # ---- Detailed validation report with match methods ----
        method_counts = {}
        for e in toc_result.entries:
            method_counts[e.match_method] = method_counts.get(e.match_method, 0) + 1
        report_parts = []
        for method, count in sorted(method_counts.items(), key=lambda x: x[1], reverse=True):
            report_parts.append(f"{count} via {method}")
        toc_result.validation_report = (
            f"TOC entries: {len(toc_result.entries)}, located: {found}/{len(toc_result.entries)} "
            f"({found/len(toc_result.entries)*100:.1f}%) | " + ", ".join(report_parts)
        )
        return toc_result

