"""
Markdown post-processor — cleans OCR artefacts while preserving page markers.

KEY FIX vs original:
  - __init__ now accepts (request, log_callback) — converter.py was passing both
    but the original constructor took zero arguments, causing a TypeError crash.

NEW in this version:
  - Added reverse‑word filter to catch common PDF extraction artefacts like
    "Ycacffie" → "efficacy", "kcatta" → "attack", etc.
  - Uses a static mapping for common reversals; can be extended if needed.
  - ADDED: Dynamic reversal correction using wordfreq (or fallback word list)
    to detect and fix entire paragraphs that are reversed (common in two‑column PDFs).
"""

import re
from collections.abc import Callable

from utils.logging import get_main_logger
from utils.word_corrector import correct_reversed_paragraph

logger = get_main_logger()


class MarkdownCleaner:
    """
    Cleans OCR-generated Markdown:
    - Normalises whitespace and newlines
    - Removes noise lines (standalone page numbers, table artefacts)
    - Fixes common OCR punctuation errors
    - Preserves <!-- original page N --> markers (stripped later by converter)
    - NEW: Fixes reversed words (e.g., "Ycacffie" → "efficacy")
    - NEW: Dynamic reversal correction for whole‑paragraph reversals.
    """

    # Lines matching these patterns are noise and get dropped
    NOISE_PATTERNS = [
        # H13 fix: only drop standalone numbers that look like page numbers
        # (1-3 digits, NOT 4-digit years like 1888/2020).  4-digit numbers
        # that are years are kept; 4-digit page numbers >999 are rare.
        re.compile(r"^\s*\d{1,3}\s*$"),  # Standalone page numbers (1-999)
        re.compile(r"^\s*[•·]\s*$"),  # Orphan bullets
        re.compile(r"^\s*[-_=]{5,}\s*$"),  # Decorative rule lines
        re.compile(r"^\s*\|[\s|]+\|\s*$"),  # Empty table rows
    ]

    # ── Static reverse‑word mapping (fast, common cases) ──────────────────
    REVERSE_WORD_MAP = {
        "ycacffie": "efficacy",
        "kcatta": "attack",
        "gnirevocsid": "discovering",
        "gninepo": "opening",
        "gnidnats": "standing",
        "gnikrow": "working",
        "gnikool": "looking",
        "gnissecorp": "processing",
        "gnitcurtsnoc": "constructing",
        "gnitseuq": "questing",
        "gnitcetorp": "protecting",
        "gnitcelfer": "reflecting",
        "gnitcerid": "directing",
        "gnitcennoc": "connecting",
        "gnitpmet": "tempting",
        "gnitceles": "selecting",
        "gnitceffe": "effecting",
        "gnitceps": "expecting",
        "gnitceffa": "affecting",
        # Add more as needed
    }
    REVERSE_WORD_PATTERN = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in REVERSE_WORD_MAP) + r")\b", re.IGNORECASE
    )

    def __init__(
        self,
        request=None,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        """
        FIX: accepts request and log_callback so converter.py's call
             MarkdownCleaner(self.request, log_callback=self._log) works correctly.
        Both parameters are optional for backwards compatibility.
        """
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)

    def clean(self, text: str) -> str:
        """Full cleaning pipeline."""
        if not text:
            return ""

        # 1. Normalise line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Collapse 3+ consecutive blank lines → double blank line
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 3. Remove noise lines (preserve page-marker comments)
        lines = text.splitlines()
        clean_lines = []
        for line in lines:
            # Always keep page-marker HTML comments
            if re.match(r"^\s*<!--.*-->\s*$", line):
                clean_lines.append(line)
                continue
            # Drop noise
            if any(p.match(line) for p in self.NOISE_PATTERNS):
                continue
            clean_lines.append(line)
        text = "\n".join(clean_lines)

        # 4. Fix common OCR punctuation: missing space after sentence-ending punctuation
        text = re.sub(r"([.!?])([A-Z\u0600-\u06FF])", r"\1 \2", text)

        # 5. Normalise bullet markers to a single style
        text = re.sub(r"^(\s*)[*+•·]\s+", r"\1- ", text, flags=re.MULTILINE)

        # 6. Remove trailing whitespace on every line
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

        # 6b. Normalise multiple inline spaces within lines.
        #     PDF justified text often produces "word    word" with many spaces
        #     between words. Collapse 2+ spaces between non-whitespace chars
        #     to a single space. Preserves leading indentation and paragraph breaks.
        text = re.sub(r"(?<=\S) {2,}(?=\S)", " ", text)

        # 6c. Collapse fragmented paragraphs from multi-column PDF extraction.
        #     pypdf sometimes extracts each word or short phrase as a separate
        #     "paragraph" (double-newline separated).  The result in the DOCX is
        #     one paragraph-object per word, producing the word-explosion seen
        #     in Image 1 of the rig test.
        #     Heuristic: if a block has ≤ 4 words and doesn't look like a heading
        #     or page marker, join it with adjacent short blocks.
        text = self._collapse_word_fragments(text)

        # 7. Ensure page markers have breathing room (keeps them parseable)
        text = re.sub(r"(<!-- original page \d+ -->)", r"\n\n\1\n\n", text)

        # 8. Final newline normalisation
        text = re.sub(r"\n{3,}", "\n\n", text)

        # ── 9. Static reverse‑word filter ──────────────────────────────────
        text = self._fix_reversed_words(text)

        # ── 10. Dynamic paragraph‑level reversal correction ──────────────
        text = self._fix_reversed_text(text)

        return text.strip()

    def _collapse_word_fragments(self, text: str) -> str:
        """
        Join sequences of very-short paragraph blocks that are artefacts of
        multi-column PDF text extraction (pypdf splits each word into its own
        double-newline-separated block).

        Guards: standalone page numbers, footnote refs ([1], *), citations
        (Smith 2003), years (1987), and URLs are NOT joined.
        """
        PROTECTED = re.compile(r"^(#{1,3} |<!-- |[-*•] |\d+[.)]\s|https?://)", re.MULTILINE)
        # Patterns that should remain as standalone blocks (not joined)
        STANDALONE = re.compile(
            r"^(?:"
            r"\d{1,4}\s*$"  # bare page number or year alone
            r"|\[\d+\]"  # footnote ref [1]
            r"|\*+\s"  # asterisk footnotes
            r"|[ivxlcdmIVXLCDM]+\."  # Roman numeral list
            r"|[A-Z][a-z]+,?\s+\d{4}"  # citation: "Smith, 2003"
            r"|\([A-Za-z].{0,30}\d{4}\)"  # citation in parens
            r"|doi:|http|www\."  # URL / DOI
            r")",
        )
        blocks = re.split(r"\n{2,}", text)
        result: list = []
        pending: list = []

        def flush():
            if pending:
                result.append(" ".join(pending))
                pending.clear()

        for block in blocks:
            stripped = block.strip()
            if not stripped:
                flush()
                result.append("")
                continue

            if PROTECTED.match(stripped) or STANDALONE.match(stripped):
                flush()
                result.append(block)
                continue

            words = stripped.split()
            if len(words) <= 4:
                pending.append(stripped)
            else:
                if pending:
                    combined = " ".join(pending) + " " + stripped
                    pending.clear()
                    result.append(combined)
                else:
                    result.append(block)

        flush()
        return "\n\n".join(r for r in result if r != "" or not result)

    # ── Static reverse‑word filter ─────────────────────────────────────────

    def _fix_reversed_words(self, text: str) -> str:
        """
        Replace common reversed-word artefacts with their correct form.
        Uses the static REVERSE_WORD_MAP; case-insensitive replacement.
        """

        def replace_match(match):
            word = match.group(1)
            # Preserve original case when possible
            correction = self.REVERSE_WORD_MAP.get(word.lower(), word)
            if word.isupper():
                return correction.upper()
            elif word.istitle():
                return correction.title()
            else:
                return correction

        return self.REVERSE_WORD_PATTERN.sub(replace_match, text)

    # ── Dynamic paragraph‑level reversal correction ──────────────────────

    def _fix_reversed_text(self, text: str) -> str:
        """
        Apply paragraph‑level reversal correction using the wordfreq‑based
        utility (or fallback word list).  This catches whole‑paragraph reversals
        often seen in two‑column PDFs.
        """
        if not text:
            return text
        paragraphs = text.split("\n\n")
        corrected = [correct_reversed_paragraph(p) for p in paragraphs]
        return "\n\n".join(corrected)
