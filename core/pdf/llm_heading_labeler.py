"""V10.12.9: Ultra-Precise TOC detection via LLM heading labeling.

When MarkItDown converts a PDF to text, the headings are often mangled by
OCR (especially for academic papers with two-column layouts).  The existing
``TocExtractor.locate_headings`` uses fuzzy text matching to find TOC
headings in the markdown — which fails when the OCR output doesn't contain
the exact heading text.

This module provides an LLM-based alternative: it sends the raw markdown
(with page markers) to the LLM and asks it to label EVERY heading with its
page number.  The LLM can recognize headings even when they're slightly
mangled, because it understands the semantic structure of the document.

Output format (what the LLM returns):

    1 Introduction (page 1)
    2 Currently Available New Treatments (page 2)
    2.1 Lasmiditan (page 3)
    2.1.1 Proposed Mode of Action (page 3)
    2.1.2 Trial Evidence in Migraine (page 3)

This is then parsed into (heading, page) tuples and fed to the segmenter,
which uses them as precise chapter boundaries — no fuzzy matching needed.

Usage (from the converter's segmentation phase)::

    from core.pdf.llm_heading_labeler import label_headings_with_llm

    headings = label_headings_with_llm(
        raw_markdown=raw_markdown,
        page_markers=page_markers,
        model=summarisation_model,
        log_callback=log,
    )
    # headings = [("1 Introduction", 1), ("2 Currently Available...", 2), ...]
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)


def label_headings_with_llm(
    raw_markdown: str,
    page_markers: list[tuple[int, int]],
    model: str,
    log_callback: Callable[[str, str], None] | None = None,
    ollama_url: str = "http://localhost:11434",
) -> list[tuple[str, int]]:
    """Label all headings in the markdown with their page numbers via LLM.

    Args:
        raw_markdown: the extracted markdown text (with ``<!-- original page N -->``
            markers).
        page_markers: the page-marker list (page_num, line_num) from
            ``extract_page_markers``.
        model: the Ollama model name to use for heading detection.
        log_callback: ``fn(message, level)`` for progress logging.
        ollama_url: the Ollama API base URL.

    Returns:
        A list of ``(heading_title, page_number)`` tuples, in document order.
        Empty list if the LLM call fails or produces no valid headings.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    if not raw_markdown or not model:
        return []

    log("  🎯 Ultra-Precise TOC: labeling headings with LLM…", "INFO")

    # Truncate the markdown to fit the LLM context window (~12k tokens for
    # the prompt + response).  Most heading structure is in the first 60%
    # of the document.  If the document is short enough, send it all.
    max_chars = 48000  # ~12k tokens
    if len(raw_markdown) > max_chars:
        # Send the first 60% + last 20% (heading at the end might matter)
        head = raw_markdown[: int(max_chars * 0.7)]
        tail = raw_markdown[-int(max_chars * 0.3) :]
        truncated = head + "\n\n[... content truncated ...]\n\n" + tail
        log(f"  📄 Markdown truncated to {len(truncated):,} chars for LLM", "DEBUG")
    else:
        truncated = raw_markdown

    # Build the prompt
    prompt = _build_heading_label_prompt(truncated)

    # Call the LLM
    try:
        from utils.network import safe_ollama_request

        url = f"{ollama_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # low temp for deterministic heading detection
                "num_predict": 4096,
            },
        }
        log(f"  🤖 Ultra-Precise TOC: calling LLM ({model})…", "INFO")
        resp = safe_ollama_request("POST", url, json=payload, timeout=180)
        text = resp.json().get("response", "").strip()
        if not text:
            log("  ⚠️ Ultra-Precise TOC: LLM returned empty response", "WARNING")
            return []
    except Exception as e:
        log(f"  ⚠️ Ultra-Precise TOC: LLM call failed: {e}", "WARNING")
        return []

    # Parse the LLM response
    headings = _parse_heading_labels(text)
    if not headings:
        log("  ⚠️ Ultra-Precise TOC: no headings parsed from LLM response", "WARNING")
        return []

    log(f"  ✅ Ultra-Precise TOC: {len(headings)} headings labeled", "INFO")
    for h, p in headings[:10]:
        log(f"    → '{h[:50]}' (page {p})", "DEBUG")
    if len(headings) > 10:
        log(f"    … and {len(headings) - 10} more", "DEBUG")

    return headings


def _build_heading_label_prompt(markdown_text: str) -> str:
    """Build the LLM prompt for heading labeling.

    The prompt asks the LLM to scan the markdown and output every heading
    with its page number, in the format "heading title (page N)".
    """
    from core.summarisation.prompt_manager import PromptManager

    _pm = PromptManager()
    rendered = _pm.render_template(
        "pdf/heading_label",
        markdown_text=markdown_text,
    )
    return rendered if rendered is not None else ""


def _parse_heading_labels(llm_response: str) -> list[tuple[str, int]]:
    """Parse the LLM's heading-label response into (heading, page) tuples.

    Expected format: "heading text (page N)" — one per line.

    Also handles:
    - "heading text (page N)" with extra spaces
    - "heading text p.N" (abbreviated)
    - "heading text, page N" (comma variant)
    - Numbered list: "1. heading text (page N)"
    - Bullet list: "- heading text (page N)"
    """
    headings: list[tuple[str, int]] = []

    # Strip thinking blocks if present
    text = re.sub(r"<think>.*?</think>", "", llm_response, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Pattern: "heading text (page N)" — the primary format
    # Also handles "p.N" and "page N" variants
    page_pattern = re.compile(
        r"^(.+?)\s*[\(](?:page|p\.?)\s*(\d+)[\)]\s*$",
        re.IGNORECASE,
    )

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Strip leading numbering/bullets: "1. ", "1) ", "- ", "* "
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        line = re.sub(r"^[-\*]\s*", "", line)

        # Try the primary pattern: "heading (page N)"
        m = page_pattern.match(line)
        if m:
            heading = m.group(1).strip()
            page = int(m.group(2))
            if heading and len(heading) > 2 and page > 0:
                headings.append((heading, page))
            continue

        # Fallback: try "heading, page N" (comma variant)
        m2 = re.match(r"^(.+?),\s*(?:page|p\.?)\s*(\d+)\s*$", line, re.IGNORECASE)
        if m2:
            heading = m2.group(1).strip()
            page = int(m2.group(2))
            if heading and len(heading) > 2 and page > 0:
                headings.append((heading, page))
            continue

        # Fallback: try "heading ... N" where N is at the end (page number)
        m3 = re.match(r"^(.+?)\s+\.\.\.\s+(\d+)\s*$", line)
        if m3:
            heading = m3.group(1).strip()
            page = int(m3.group(2))
            if heading and len(heading) > 2 and page > 0:
                headings.append((heading, page))
            continue

    # Deduplicate (keep first occurrence of each heading)
    seen = set()
    deduped: list[tuple[str, int]] = []
    for h, p in headings:
        key = h.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append((h, p))

    return deduped
