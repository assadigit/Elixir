"""V10.19.0: Token cost estimator — estimates total token usage for a conversion.

Reads the PDF, extracts text (fast — no OCR), and estimates:
  - Input tokens (the source text fed to the summarizer)
  - Output tokens (the expected summary/briefing/podcast/flashcard output)
  - Total tokens (input + output)

V13.31.0 (#14): The automatic cost estimation (provider pricing-based)
  has been **removed** — it was an unreliable guess. The estimator now
  returns **token counts only**. The :class:`TokenCostDialog` lets the
  user manually enter a cost-per-million-tokens value for an exact
  calculation.

The estimate is shown in a pre-conversion modal so the user knows the
token cost BEFORE committing to a potentially expensive cloud API run.

Usage (from the wizard's _start_conversion)::

    from core.pipeline.token_estimator import estimate_conversion_tokens
    estimate = estimate_conversion_tokens(request, log_callback=log)
    # estimate = {input_tokens, output_tokens, total_tokens, chapter_count, ...}

    from ui_qt.views.token_cost_dialog import TokenCostDialog
    dlg = TokenCostDialog(estimate, parent)
    if dlg.exec() != QDialog.Accepted:
        return  # user cancelled
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def estimate_conversion_tokens(
    pdf_path: Path,
    request: Any,
    password: str | None = None,
    log_callback: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Estimate total token usage for a conversion.

    Reads the PDF (fast text extraction — no OCR), counts tokens, and
    estimates the total token consumption based on the enabled outputs.

    Args:
        pdf_path: path to the PDF file
        request: the ConversionRequest (has output_* flags, summarisation settings)
        password: PDF password (optional)
        log_callback: fn(message, level)

    Returns:
        A dict with keys:
          - pdf_pages: int
          - extracted_chars: int
          - input_tokens: int (source text tokens — the input to the LLM)
          - output_tokens: int (estimated output tokens — summaries + outputs)
          - total_tokens: int (input + output)
          - chapter_count: int (estimated, based on TOC or segmentation heuristic)
          - llm_calls: int (estimated number of LLM API calls)
          - per_output: dict of {output_name: estimated_tokens}

        V13.36.0: When ``request.selected_chapters`` is set, the dict ALSO
        contains a parallel "selected_*" set of keys reflecting ONLY the
        selected chapters:
          - selected_chapter_count: int
          - selected_source_tokens: int
          - selected_input_tokens: int
          - selected_output_tokens: int
          - selected_total_tokens: int
          - selected_llm_calls: int
          - selected_avg_chapter_tokens: int
          - full_book_chapter_count: int (same as chapter_count — for clarity)

    V13.31.0 (#14): The ``estimated_cost`` field has been removed — cost
    is now calculated by the user via the :class:`TokenCostDialog`.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    try:
        from pypdf import PdfReader

        from utils.token_counter import count_tokens
    except ImportError as e:
        log(f"  ⚠️ Token estimator: missing dep ({e})", "WARNING")
        return {"error": str(e), "total_tokens": 0}

    # ── Step 1: Extract text from PDF (fast — no OCR) ────────────────
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted and password:
            reader.decrypt(password)
        pdf_pages = len(reader.pages)
        # V13.36.0: Keep per-page text so we can compute selected-chapter tokens
        page_texts = []
        all_text = ""
        for page in reader.pages:
            try:
                pt = page.extract_text() or ""
                page_texts.append(pt)
                all_text += pt + "\n"
            except Exception as _e:
                page_texts.append("")
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
    except Exception as e:
        log(f"  ⚠️ Token estimator: PDF read failed ({e})", "WARNING")
        return {"error": str(e), "total_tokens": 0}

    extracted_chars = len(all_text)
    source_tokens = count_tokens(all_text)

    # ── Step 2: Estimate chapter count ───────────────────────────────
    # V18.20.4.10 (P0-a): three-layer chapter count, most-trusted first.
    #
    # 1. PDF outline (bookmarks) — the authoritative chapter list when the
    #    PDF has one. Counting TOP-LEVEL bookmarks only (metadata children
    #    such as per-chapter author names live at deeper levels — the
    #    "97 Things" outline has 99 top-level titles + 97 author children,
    #    and the old heuristic saw neither).
    # 2. Heading-like lines (the V10.19 heuristic), now CAPPED at one
    #    "chapter" per two PDF pages. The uncapped regex
    #    `^\d+[\.\d]*\s+\S` matches ANY short numbered line — year lists,
    #    footnotes, numbered exercises — and counted 2,623 "chapters" in a
    #    257-page book (the user-facing ~5,000,000-token estimate was this
    #    count multiplied through every per-chapter output multiplier,
    #    ~7x the real total).
    # 3. ~1 chapter per 3000 tokens (unchanged last resort).
    outline_chapter_count = _count_outline_chapters(pdf_path, password, log)

    heading_count = 0
    for line in all_text.splitlines():
        line = line.strip()
        if not line or len(line) > 100:
            continue
        if re.match(r'^#{1,3}\s+', line) or re.match(r'^\d+[\.\d]*\s+\S', line):
            heading_count += 1

    if outline_chapter_count and outline_chapter_count >= 1:
        chapter_count = outline_chapter_count
        log(
            f"  📑 Chapter count from PDF outline: {chapter_count} "
            f"(top-level bookmarks — authoritative)",
            "INFO",
        )
    else:
        # V18.20.4.10 (P0-a): cap the heading heuristic at 1 per 2 pages —
        # a real chapter needs at least ~2 pages; numbered-list noise
        # cannot inflate the count past pdf_pages // 2 any more.
        _heading_cap = max(1, pdf_pages // 2) if pdf_pages else heading_count
        if heading_count > _heading_cap:
            log(
                f"  📑 Heading heuristic found {heading_count} heading-like lines "
                f"— capped to {_heading_cap} (1 per 2 PDF pages; numbered-list "
                f"noise was inflating the estimate ~7x).",
                "INFO",
            )
            heading_count = _heading_cap
        chapter_count = max(1, heading_count) if heading_count > 0 else max(1, source_tokens // 3000)

    # ── Step 3: Estimate input tokens per chapter ────────────────────
    # The summarizer sends the chapter content + prompt to the LLM.
    # Prompt overhead is ~500-1000 tokens (system prompt + instructions).
    # If using concept extraction, add ~200 tokens per chapter.
    prompt_overhead = 800  # tokens
    concept_overhead = 200  # tokens
    avg_chapter_tokens = source_tokens // chapter_count if chapter_count > 0 else source_tokens
    input_tokens_per_chapter = avg_chapter_tokens + prompt_overhead + concept_overhead
    total_input_tokens = input_tokens_per_chapter * chapter_count

    # ── Step 4: Estimate output tokens per output type ───────────────
    max_output = getattr(request, "summarisation_max_output_tokens", 4096)
    per_output: dict[str, int] = {}

    # Summarization (exec + bullets + thorough per chapter)
    if getattr(request, "generate_summaries", False):
        # V13.34.0: Realistic estimates (not worst-case).
        # Old code assumed 3x multi-sample + self-review + gap-fill for EVERY
        # chapter, inflating the estimate by ~6x. Now uses realistic numbers.
        # Base: 1 call per chapter
        summ_output = max_output * chapter_count
        # Self-review: only if academic rigor is on
        if getattr(request, "academic_rigor", False):
            summ_output += (max_output // 2) * chapter_count
        # Multi-sample: B3 no longer escalates temperature and rarely triggers
        # (coverage is usually ≥ threshold). Assume 20% of chapters need it.
        summ_output += int(max_output * 0.6 * chapter_count)  # 20% × 3 samples
        per_output["summaries"] = summ_output
        # Input tokens for multi-sample (20% of chapters × 3 samples)
        total_input_tokens += int(avg_chapter_tokens * 0.6 * chapter_count)

    # Keypoints
    if getattr(request, "include_keypoints", False):
        per_output["keypoints"] = max_output * 2  # 1-2 LLM calls for dedup/ordering

    # Executive briefing
    if getattr(request, "output_briefing", False):
        per_output["briefing"] = 8192  # 1 LLM call with all chapter summaries

    # Podcast script
    if getattr(request, "output_podcast", False):
        per_output["podcast_script"] = max_output * chapter_count

    # Flashcards
    if getattr(request, "output_flashcards", False):
        # 1 LLM call per batch of 10 keypoints
        estimated_keypoints = chapter_count * 10  # ~10 bullets per chapter
        batches = (estimated_keypoints + 9) // 10
        per_output["flashcards"] = max_output * batches

    # Q&A
    if getattr(request, "output_qa", False):
        per_output["qa"] = max_output * chapter_count

    # Study guide
    if getattr(request, "output_study_guide", False):
        per_output["study_guide"] = max_output * 2

    # Social media
    if getattr(request, "output_social", False):
        per_output["social"] = max_output

    # Mind map
    if getattr(request, "output_mindmap", False):
        per_output["mindmap"] = max_output  # deterministic, minimal LLM

    # Packets
    if getattr(request, "output_packets", False):
        per_output["packets"] = max_output * 2

    # Obsidian
    if getattr(request, "output_obsidian", False):
        per_output["obsidian"] = max_output  # mostly deterministic

    # LLM-as-judge grounding (V10.14.0 D6 — 1 call per chapter when grounding is off)
    per_output["llm_judge"] = 1024 * chapter_count  # small call per chapter

    # Gap-fill: only ~30% of chapters need it (realistic, not worst-case)
    per_output["gap_fill"] = int(max_output * 0.3 * chapter_count)

    total_output_tokens = sum(per_output.values())

    # ── Step 5: Count estimated LLM calls ────────────────────────────
    # V18.20.3.9 (Phase 3.a / C1 — call-count honesty): the old model
    # estimated ~6 calls/chapter (1 base + 3 multi-sample/self-review + 1
    # judge + 1 gap-fill). The V18.20.3.7/.3.8 rig characterizations
    # measured the REAL per-chapter fan-out: primary + additive followups
    # + (conditional) thorough expansion + semantic grounding + content
    # judge + scholar reflection + consolidation + up-to-5 gap-fill rounds
    # + keypoints = 13-18 typical, ~25 with escalation, ~40 worst case
    # (veto ladder x authors + multi-sample).
    # V18.20.3.11 (Phase 3.b / F7 — recalibrated against the C1 telemetry
    # registry): the .3.9 rig MEASURED 9 calls/chapter (the skip paths
    # explain the delta vs the 15 estimate: V17.4 deterministic-analysis
    # skip removes concept-extraction, expansion skip fires at 30+ bullets,
    # no self-consistency/B3 voting), and the .3.11 consolidation skip
    # removes one more on the probe-zero shape → 8 measured. Typical band
    # set to 10 (measured 8-9 + multi-round gap-fill variance); worst case
    # stays 40 (veto ladder + multi-sample + escalation).
    base_calls_per_chapter = 10
    worst_calls_per_chapter = 40
    llm_calls = chapter_count * base_calls_per_chapter
    for output_name in ["briefing", "podcast_script", "flashcards", "qa",
                        "study_guide", "social", "mindmap", "packets", "obsidian"]:
        if output_name in per_output:
            llm_calls += max(1, per_output[output_name] // max_output)
    llm_calls_worst = llm_calls + chapter_count * (worst_calls_per_chapter - base_calls_per_chapter)

    total_tokens = total_input_tokens + total_output_tokens

    # V13.31.0 (#14): Automatic cost estimation removed — was based on a
    # static PRICING table that didn't match real provider invoices, so
    # the user found the estimates misleading. The TokenCostDialog now
    # provides a manual "Cost per million tokens" input field so the user
    # can enter their actual pricing and get an exact calculation.

    # V10.20.0: Token budgeting — show what percentage each output consumes
    # This helps users understand which outputs are "expensive" and could
    # be disabled to save tokens (inspired by book-to-skill's density principle).
    per_output_budget = {}
    if total_output_tokens > 0:
        for name, tokens in per_output.items():
            pct = (tokens / total_output_tokens) * 100
            per_output_budget[name] = {"tokens": tokens, "pct": round(pct, 1)}

    result = {
        "pdf_pages": pdf_pages,
        "extracted_chars": extracted_chars,
        "source_tokens": source_tokens,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "chapter_count": chapter_count,
        "llm_calls": llm_calls,
        "llm_calls_worst_case": llm_calls_worst,
        "llm_calls_basis": "V18.20.3.11 telemetry-recalibrated fan-out: ~10 calls/chapter typical (rig-measured 8-9), ~40 worst case",
        "per_output": per_output,
        "per_output_budget": per_output_budget,
        "avg_chapter_tokens": avg_chapter_tokens,
        # V13.31.0 (#14): no more estimated_cost — user enters cost manually
        # in the TokenCostDialog.
    }

    # ═══════════════════════════════════════════════════════════════════════
    # V13.36.0: Per-selected-chapter estimate
    # When the user selected specific chapters, compute a parallel estimate
    # for ONLY those chapters. The dialog shows this as the PRIMARY headline
    # (with the full-book total as secondary context).
    # ═══════════════════════════════════════════════════════════════════════
    selected_chapters = getattr(request, "selected_chapters", None)
    if selected_chapters:
        selected_count = len(selected_chapters)
        # Compute the selected source tokens by finding the page ranges for
        # the selected chapters. We use the PDF outline (TOC) to map chapter
        # titles to page ranges, then sum the tokens of those pages.
        selected_source_tokens, _distinct_selected_pages = _compute_selected_source_tokens(
            pdf_path, page_texts, selected_chapters, count_tokens, log
        )

        # If we couldn't map chapters to pages, fall back to proportional estimate
        if selected_source_tokens <= 0 and chapter_count > 0:
            # Proportional: selected_count / chapter_count * source_tokens
            selected_source_tokens = int(source_tokens * (selected_count / chapter_count))

        # V18.20.4.10 (P0-a): the selection list can contain MORE entries
        # than there are real chapters — e.g. "97 Things" lists BOTH the
        # essay title AND its author as selectable "chapters" (198 entries
        # for 99 real chapters). Every per-chapter multiplier below would
        # then double-count. When the outline mapping succeeded, the number
        # of DISTINCT matched start pages is the honest chapter count.
        if _distinct_selected_pages and _distinct_selected_pages < selected_count:
            log(
                f"  📑 Selection lists {selected_count} entries but they map to "
                f"{_distinct_selected_pages} distinct chapter start pages — "
                f"estimating for {_distinct_selected_pages} real chapters "
                f"(duplicate/metadata entries such as author names no longer "
                f"multiply the estimate).",
                "INFO",
            )
            selected_count = _distinct_selected_pages

        selected_avg = selected_source_tokens // selected_count if selected_count > 0 else selected_source_tokens
        selected_input_per_ch = selected_avg + prompt_overhead + concept_overhead
        selected_total_input = selected_input_per_ch * selected_count

        # Scale per_output proportionally by chapter count
        ratio = selected_count / chapter_count if chapter_count > 0 else 1.0
        selected_per_output = {k: int(v * ratio) for k, v in per_output.items()}
        selected_total_output = sum(selected_per_output.values())

        selected_llm_calls = selected_count * base_calls_per_chapter
        for output_name in ["briefing", "podcast_script", "flashcards", "qa",
                            "study_guide", "social", "mindmap", "packets", "obsidian"]:
            if output_name in selected_per_output:
                selected_llm_calls += max(1, selected_per_output[output_name] // max_output)
        selected_llm_calls_worst = selected_llm_calls + selected_count * (worst_calls_per_chapter - base_calls_per_chapter)

        selected_total = selected_total_input + selected_total_output

        result["selected_chapter_count"] = selected_count
        result["selected_source_tokens"] = selected_source_tokens
        result["selected_input_tokens"] = selected_total_input
        result["selected_output_tokens"] = selected_total_output
        result["selected_total_tokens"] = selected_total
        result["selected_llm_calls"] = selected_llm_calls
        result["selected_llm_calls_worst_case"] = selected_llm_calls_worst
        result["selected_avg_chapter_tokens"] = selected_avg
        result["full_book_chapter_count"] = chapter_count
        result["selected_chapter_titles"] = selected_chapters[:5]  # first 5 for preview

    return result


def _count_outline_chapters(
    pdf_path: Path,
    password: str | None,
    log,
) -> int:
    """V18.20.4.10 (P0-a): count TOP-LEVEL PDF outline bookmarks.

    Returns 0 when the PDF has no usable outline (caller falls back to the
    heading heuristic). Only level-0 destinations are counted — deeper
    levels hold metadata children (per-chapter author names, sub-sections)
    that would multiply every per-chapter estimate.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted and password:
            reader.decrypt(password)
        outline = reader.outline if hasattr(reader, "outline") else []
        if not outline:
            return 0
        return sum(
            1
            for item in outline
            if hasattr(item, "title") and str(getattr(item, "title", "")).strip()
        )
    except Exception as e:
        log(f"  ⚠️ Token estimator: outline count failed ({e})", "DEBUG")
        return 0


def _compute_selected_source_tokens(
    pdf_path: Path,
    page_texts: list,
    selected_chapters: list,
    count_tokens_fn,
    log,
) -> tuple[int, int]:
    """V13.36.0: Compute source tokens for only the selected chapters.

    Uses the PDF's outline (TOC) to map chapter titles to page ranges,
    then sums the tokens of those pages. Falls back to 0 if the outline
    can't be read or no chapters match (caller handles proportional fallback).

    V18.20.4.10 (P0-a): ALSO returns the number of DISTINCT chapter start
    pages the selection mapped to — the honest chapter count when the
    selection list contains duplicate/metadata entries (essay title +
    author both listed for the same chapter).
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        # Try to get the outline (TOC)
        outline = reader.outline if hasattr(reader, "outline") else []
        if not outline:
            return 0

        # Flatten the outline into (title, page_number) pairs
        toc_entries = []
        def _flatten(items, level=0):
            for item in items:
                if isinstance(item, list):
                    _flatten(item, level + 1)
                else:
                    try:
                        title = str(getattr(item, "title", "")).strip()
                        page_num = reader.get_destination_page_number(item)
                        if title:
                            toc_entries.append((title, page_num))
                    except Exception:
                        continue
        _flatten(outline)

        if not toc_entries:
            return 0

        # Sort by page number
        toc_entries.sort(key=lambda x: x[1])

        # Match selected chapters to TOC entries (fuzzy)
        from core.pipeline.converter import Converter
        converter = Converter.__new__(Converter)  # instantiate without __init__
        matched_pages = set()
        for selected_title in selected_chapters:
            for i, (toc_title, toc_page) in enumerate(toc_entries):
                if converter._match_chapter(toc_title, selected_title):
                    # Determine the page range: from this chapter's start page
                    # to the next chapter's start page (or end of book)
                    start_page = toc_page
                    if i + 1 < len(toc_entries):
                        end_page = toc_entries[i + 1][1]
                    else:
                        end_page = len(page_texts)
                    for p in range(start_page, min(end_page, len(page_texts))):
                        matched_pages.add(p)
                    break

        if not matched_pages:
            return 0, 0

        # V18.20.4.10 (P0-a): distinct START pages of the matched entries =
        # real chapter count for this selection (title + author entries
        # share one start page → counted once).
        distinct_start_pages: set[int] = set()
        for selected_title in selected_chapters:
            for toc_title, toc_page in toc_entries:
                if converter._match_chapter(toc_title, selected_title):
                    distinct_start_pages.add(toc_page)
                    break

        selected_text = "\n".join(page_texts[p] for p in sorted(matched_pages) if p < len(page_texts))
        return count_tokens_fn(selected_text), len(distinct_start_pages)
    except Exception as e:
        log(f"  ⚠️ Token estimator: selected-chapter mapping failed ({e})", "DEBUG")
        return 0, 0
