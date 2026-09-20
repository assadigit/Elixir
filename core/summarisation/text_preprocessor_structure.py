"""V0.18 (Phase 5.3) — layout / structure family of the text preprocessor.

Moved VERBATIM (byte-identical bodies) from ``text_preprocessor_impl.py``
during the Phase 5.3 split by concern:

  - ``repair_hyphenation``     — rejoin words broken across lines (A2)
  - ``remove_headers_footers`` — strip repeating PDF headers/footers (A1)
  - ``extract_callouts``       — [Spy Tip] / Exercise: callout sentences
  - ``smart_paragraph_joining``— rejoin mid-sentence line breaks (A3)
  - ``detect_sections``        — sub-heading detection (A6)

``text_preprocessor_impl.py`` re-exports every name below (compat facade,
same object identities), so all existing importers keep working unchanged.
"""

from __future__ import annotations

import re

# ════════════════════════════════════════════════════════════════════════════
# A2: Hyphenation Repair
# ════════════════════════════════════════════════════════════════════════════

# Pattern: letter + hyphen + newline + letter
# e.g. "net-\nworking" → "networking"
# V18.1 (O4): extended from [a-z] only to [a-zA-Z\u00C0-\u024F] so that
# proper nouns (hyphenated line-break splits) and accented Latin chars
# ("café-\nbar" → "cafébar", "Über-\nschrift" → "Überschrift") are also
# rejoined. The \u00C0-\u024F range covers Latin-1 Supplement + Latin
# Extended-A/B (À-ÿ and beyond).
_HYPHEN_PATTERN = re.compile(r"([a-zA-Z\u00C0-\u024F])-\n([a-zA-Z\u00C0-\u024F])")


# Don't join if the resulting word would be too long (likely a real hyphenated
# compound like "state-of-the-art" that got line-broken)
_MAX_JOINED_WORD_LEN = 25


def repair_hyphenation(text: str) -> str:
    """Fix words broken across lines by hyphenation.

        PDF extraction often produces "net-\\nworking" when a word is hyphenated
        at a line break. This rejoins them into "networking".

        V18.2.18 (O4): Fixed the lookahead to match Capitalized + accented chars.
        Previously ``word_rest = re.match(r'[a-z]+', after)`` only matched
    # line-break splits were missed
        (the 'son' part is lowercase, but the regex would fail to join if the
        left side was Capitalized because the combined check was inconsistent).
        Now the lookahead uses ``[a-zA-Z\\u00C0-\\u024F]+`` to match any letter,
        matching the main ``_HYPHEN_PATTERN``.
    """

    def _join(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        # Peek ahead to get the full word after the newline.
        # V18.2.18 (O4): use the same char class as _HYPHEN_PATTERN so
        # Capitalized + accented proper nouns are joined correctly.
        rest = right
        after = text[m.end() : m.end() + 30]
        word_rest = re.match(r"[a-zA-Z\u00C0-\u024F]+", after)
        if word_rest:
            rest += word_rest.group()
        # V18.2.18 (O4): Also look BACK to find the full word before the
        # hyphen (the regex only captures the last char before '-\n').
        # Without this, the length check only sees `left` (1 char) + `rest`,
        # so long compounds like "pneumono...coniosis-\nsuffix" pass the
        # <25 check even though the full joined word is 52 chars.
        before = text[max(0, m.start() - 30) : m.start()]
        word_before_match = re.search(r"[a-zA-Z\u00C0-\u024F]+$", before)
        full_left = (word_before_match.group() if word_before_match else "") + left
        # Don't join if the FULL combined word is too long (likely a real compound)
        if len(full_left) + len(rest) > _MAX_JOINED_WORD_LEN:
            return m.group(0)
        return left + right

    # V18.2.18 (O4): Use _join (with the length check + lookahead) instead
    # of the naive lambda. The old "simple version" ignored the length cap,
    # so real hyphenated compounds like "state-of-the-art" got joined
    # across newlines. Now _join is called for every match.
    return _HYPHEN_PATTERN.sub(_join, text)


# ════════════════════════════════════════════════════════════════════════════
# A1: Header/Footer Removal
# ════════════════════════════════════════════════════════════════════════════

# Page marker pattern — detect lines like "<!-- Page 12 -->" or "[Page 12]"
_PAGE_MARKER = re.compile(
    r"^(?:<!--\s*Page\s+\d+\s*-->|\[Page\s+\d+\])\s*$", re.MULTILINE | re.IGNORECASE
)


def remove_headers_footers(text: str) -> str:
    """V3.2.4 A1: Detect and remove repeating headers/footers from PDF text.

    PDFs often have running headers ("Chapter 2 — Spotting") and page numbers
    on every page. These pollute the text and waste tokens.

    Strategy: Split text by page markers. For each line position (first/last
    N lines of each page), check if the same line appears across 3+ pages.
    If so, it's a header/footer — remove it.

    Also removes standalone page-number lines (lines that are just a number).
    """
    if not text or len(text) < 500:
        return text

    # Find page marker positions
    markers = list(_PAGE_MARKER.finditer(text))
    # V18.1 (O5): lowered 3→2 so short PDFs (<3 page markers) still get
    # header/footer removal. The old 3-marker floor skipped detection
    # entirely for short PDFs (e.g. 2-page catalogues) and left running
    # headers in the text.
    if len(markers) < 2:
        # Not enough page markers to detect patterns — just strip bare page numbers
        text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)
        return text

    # Split text into page chunks
    pages = []
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        page_text = text[start:end].strip()
        if page_text:
            pages.append(page_text)

    # V18.1 (O5): lowered 3→2 (matches the marker threshold above).
    if len(pages) < 2:
        return text

    # Get the first 3 and last 3 lines of each page
    header_lines = []  # list of (line_text, page_idx)
    footer_lines = []
    for idx, page in enumerate(pages):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        if len(lines) >= 2:
            header_lines.append((lines[0], idx))
            if len(lines) >= 3:
                header_lines.append((lines[1], idx))
            footer_lines.append((lines[-1], idx))
            if len(lines) >= 3:
                footer_lines.append((lines[-2], idx))

    # Find lines that repeat across 2+ pages (V18.1/O5: lowered 3→2)
    from collections import Counter as _Counter

    header_counts = _Counter(line for line, _ in header_lines)
    footer_counts = _Counter(line for line, _ in footer_lines)

    to_remove = set()
    for line, count in header_counts.items():
        # V18.1 (O5): count threshold lowered 3→2 so a header appearing on
        # both pages of a short PDF is still detected.
        if count >= 2 and len(line) > 3:
            to_remove.add(line)
    for line, count in footer_counts.items():
        if count >= 2 and len(line) > 3:
            to_remove.add(line)

    # Also remove bare page-number lines
    for line, _ in header_lines + footer_lines:
        if re.match(r"^\d{1,4}$", line):
            to_remove.add(line)

    if not to_remove:
        return text

    # Remove the detected headers/footers from the full text
    removed_count = 0
    for line in to_remove:
        # Remove the line wherever it appears as a standalone line
        pattern = re.compile(r"^\s*" + re.escape(line) + r"\s*$", re.MULTILINE)
        matches = pattern.findall(text)
        removed_count += len(matches)
        text = pattern.sub("", text)

    # Clean up any triple+ newlines left by removals
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


# ════════════════════════════════════════════════════════════════════════════
# Convenience: Extract callout sentences ([Spy Tip], [Key Point], etc.)
# ════════════════════════════════════════════════════════════════════════════

# V3.9.6: Expanded callout patterns. The original only caught [Spy Tip] style
# bracket callouts. Now also catches common self-help/management book patterns:
# Exercise:, Worksheet:, Practice:, Try This:, Action Item:, Takeaway:,
# Key Insight:, Homework:, Reflection:, Question to Ponder:
_CALLOUT_PATTERN = re.compile(
    r"\[(?:Spy\s+Tip|Key\s+Point|Important|Note|Remember|Tip|Warning|Insight)\][:\s]\s*([^\[\]]{20,300})",
    re.IGNORECASE,
)


# V3.9.6: Non-bracket callout patterns (Exercise:, Try This:, etc.)
# These appear at the start of a line or after a newline, followed by a colon
# and 20-300 chars of content. Matches until end of line or next callout.
_CALLOUT_PREFIX_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Exercise|Worksheet|Practice|Try\s+This|Action\s+Item|Takeaway|"
    r"Key\s+Insight|Homework|Reflection|Question\s+to\s+Ponder|Activity|"
    r"Experiment|Challenge|Step\s+\d+|Task)\s*:\s*([^\n]{20,300})",
    re.IGNORECASE,
)


def extract_callouts(text: str) -> list[str]:
    """Extract callout/highlight sentences from the text.

    Books often have [Spy Tip], [Key Point], [Important] callouts that contain
    the highest-value concept sentences. These are injected into the prompt
    as "must-cover" content.

    V3.9.6: Expanded to also catch non-bracket callouts common in self-help
    and management books: Exercise:, Worksheet:, Practice:, Try This:,
    Action Item:, Takeaway:, Key Insight:, Homework:, Reflection:, etc.
    """
    callouts = []
    # Pattern 1: Bracket callouts [Spy Tip], [Key Point], etc.
    for m in _CALLOUT_PATTERN.finditer(text):
        sentence = m.group(1).strip()
        if len(sentence) > 15:
            sentence = re.sub(r"\s+", " ", sentence)
            callouts.append(sentence)
    # V3.9.6: Pattern 2 — non-bracket callouts (Exercise:, Try This:, etc.)
    for m in _CALLOUT_PREFIX_PATTERN.finditer(text):
        sentence = m.group(1).strip()
        if len(sentence) > 15:
            sentence = re.sub(r"\s+", " ", sentence)
            # Avoid duplicates with bracket callouts
            if sentence not in callouts:
                callouts.append(sentence)
    return callouts[:15]  # cap at 15 to avoid prompt bloat


# ════════════════════════════════════════════════════════════════════════════
# A3: Smart Paragraph Joining
# ════════════════════════════════════════════════════════════════════════════

# Lines ending with these are complete — don't join with next line
_SENTENCE_END = re.compile(r'[.!?:"\u201d\u2019]\s*$')


def smart_paragraph_joining(text: str) -> str:
    """V3.3.0 A3: Join lines that were broken mid-sentence by PDF extraction.

    PDF extraction often breaks paragraphs at every newline. The LLM sees
    fragmented text. This function joins lines when:
    - The current line does NOT end with sentence-ending punctuation
    - The next line starts with a lowercase letter (continuation)

    Does NOT join when:
    - Current line ends with . ! ? : " (complete sentence)
    - Next line starts with uppercase (new sentence/heading)
    - Next line starts with a bullet/number (list item)
    """
    if not text:
        return text

    lines = text.splitlines()
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if we should join with the next line
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            curr_stripped = line.rstrip()
            # Join if: current doesn't end with sentence punctuation AND
            # next starts with lowercase AND current is not empty
            if (
                curr_stripped
                and next_line
                and not _SENTENCE_END.search(curr_stripped)
                and next_line[0].islower()
                and not next_line.startswith(("-", "*", "•", "1.", "2.", "3."))
                and not curr_stripped.startswith(("#", "##", "###"))
            ):
                # Join with space
                line = curr_stripped + " " + next_line
                i += 1  # skip the next line (consumed)
        result.append(line)
        i += 1

    return "\n".join(result)


# ════════════════════════════════════════════════════════════════════════════
# A6: Section / Heading Detection
# ════════════════════════════════════════════════════════════════════════════

# Heading patterns: short lines, title case or all caps, no ending punctuation
_HEADING_PATTERN = re.compile(
    r"^(?:#{1,4}\s+)?"  # optional markdown heading prefix
    r"([A-Z][A-Za-z0-9\s\-:,\&]+?)\s*$"  # title-case text
)


def detect_sections(text: str, max_sections: int = 8) -> list[str]:
    """V3.3.0 A6: Detect sub-headings within a chapter.

    Identifies likely section headings by:
    - Short lines (< 80 chars)
    - Title case or ALL CAPS
    - No ending punctuation (no . ! ?)
    - Not part of a paragraph (blank line before/after)
    - At least 3 words OR starts with a number ("1. ", "Section ")

    Returns a list of section heading strings. Used by B4 (section-by-section
    map-reduce) to split chapters for independent summarization.
    """
    if not text:
        return []

    lines = text.splitlines()
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue
        # Skip lines with ending punctuation (not headings)
        if stripped[-1] in ".!?;:":
            continue
        # Skip lines that are just numbers
        if re.match(r"^\d+$", stripped):
            continue
        # Skip lines starting with lowercase
        if not stripped[0].isupper():
            continue
        # Must have at least 2 words OR start with a number/section prefix
        words = stripped.split()
        if len(words) < 2 and not re.match(r"^\d+\.", stripped):
            continue
        # Check if it looks like a heading (title case or all caps)
        is_title_case = all(w[0].isupper() or not w[0].isalpha() for w in words)
        is_all_caps = stripped.isupper() and any(c.isalpha() for c in stripped)
        if not (is_title_case or is_all_caps):
            continue
        # Check for blank line before (or start of text) — headings are separated
        prev_blank = i == 0 or not lines[i - 1].strip()
        if not prev_blank:
            continue
        # Strip markdown prefix
        clean = re.sub(r"^#{1,4}\s+", "", stripped)
        headings.append(clean)
        if len(headings) >= max_sections:
            break

    return headings
