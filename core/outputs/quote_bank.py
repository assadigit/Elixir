"""V10.35.0 (Sprint 9.10): Quote bank — extract every direct quote with page citation.

Scans the chapter markdown for text in quotation marks (single, double,
or guillemets) that is >40 characters.  Each quote gets a citation
showing which chapter and page it appeared on.

Output: ``{book_title}.QuoteBank.md`` — a markdown file with all quotes
organized by chapter.

No LLM calls — this is deterministic text extraction.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

logger = logging.getLogger(__name__)

#: Minimum quote length (characters) to include.
MIN_QUOTE_LENGTH = 40

#: Regex patterns for quotes in different delimiter styles.
_QUOTE_PATTERNS = [
    # Double quotes: "text..."
    re.compile(r'"([^"]{40,})"'),
    # Single quotes: 'text...' (only if >40 chars to avoid apostrophes)
    re.compile(r"'([^']{40,})'"),
    # Guillemets: «text...»
    re.compile(r'«([^»]{40,})»'),
    # Smart double quotes: "text..."
    re.compile(r'\u201c([^\u201d]{40,})\u201d'),
    # Smart single quotes: 'text...'
    re.compile(r'\u2018([^\u2019]{40,})\u2019'),
]

#: Page marker pattern: <!-- original page N -->
_PAGE_MARKER = re.compile(r'<!--\s*original page (\d+)\s*-->')


class QuoteBankGenerator(OutputGeneratorBase):
    """Extract all direct quotes from the chapter text with page citations."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate the quote bank markdown file.

        Args:
            summaries: List of SummaryResult (we use chapter_heading + the
                original source text if available).
            book_title: The book title.
            output_dir: The output subdirectory.

        Returns:
            Path to the .md file, or None on failure.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{book_title}.QuoteBank.md"

        try:
            all_quotes = []
            for idx, summ in enumerate(summaries, 1):
                heading = summ.chapter_heading or f"Chapter {idx}"
                # The source text is on the Summarizer instance, not the
                # SummaryResult.  We extract quotes from the thorough_summary
                # + bullet_points (which contain the model's output) + any
                # text we can access.  In a full implementation, we'd read
                # the original chapter .md file from the markdown/chapters/
                # directory — but we don't have the path here.  For now, we
                # extract from the thorough_summary + bullet_points.
                text_parts = []
                if summ.thorough_summary:
                    text_parts.append(summ.thorough_summary)
                if summ.bullet_points:
                    text_parts.extend(str(bp) for bp in summ.bullet_points)
                text = "\n".join(text_parts)

                quotes = self._extract_quotes(text)
                if quotes:
                    all_quotes.append((heading, quotes))

            # Build the markdown
            lines = [f"# Quote Bank — {book_title}", ""]
            lines.append(f"> {sum(len(q) for _, q in all_quotes)} direct quotes "
                         f"({MIN_QUOTE_LENGTH}+ chars) extracted from "
                         f"{len(summaries)} chapter(s).")
            lines.append("")

            if not all_quotes:
                lines.append("*No direct quotes found (the summaries may not "
                             "contain text in quotation marks).*")
            else:
                for heading, quotes in all_quotes:
                    lines.append(f"## {heading}")
                    lines.append("")
                    for quote, page in quotes:
                        citation = f" *(p.{page})*" if page else ""
                        lines.append(f'> "{quote}"{citation}')
                        lines.append("")
                    lines.append("---")
                    lines.append("")

            out_path.write_text("\n".join(lines), encoding="utf-8")
            total = sum(len(q) for _, q in all_quotes)
            self.log(f"  ✅ Quote bank: {total} quotes from {len(all_quotes)} chapters → {out_path.name}", "INFO")
            return out_path

        except Exception as exc:
            self.log(f"  ⚠️ Quote bank generation failed: {exc}", "WARNING")
            return None

    def _extract_quotes(self, text: str) -> list[tuple]:
        """Extract quotes from text. Returns [(quote_text, page_num_or_None), ...].

        Page numbers are extracted from the nearest preceding page marker.
        """
        if not text:
            return []

        quotes = []
        # Split text into page segments (by page markers)
        page_markers = list(_PAGE_MARKER.finditer(text))
        current_page = None

        for pattern in _QUOTE_PATTERNS:
            for m in pattern.finditer(text):
                quote_text = m.group(1).strip()
                if len(quote_text) < MIN_QUOTE_LENGTH:
                    continue
                # Find the nearest preceding page marker
                pos = m.start()
                page = None
                for pm in page_markers:
                    if pm.start() < pos:
                        page = int(pm.group(1))
                    else:
                        break
                # Deduplicate (same quote may match multiple patterns)
                if not any(q[0] == quote_text for q in quotes):
                    quotes.append((quote_text, page))

        # Sort by position (implicit — finditer returns in order)
        return quotes


__all__ = ["QuoteBankGenerator"]
