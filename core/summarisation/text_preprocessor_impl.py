"""Deterministic Text Preprocessor — pure Python, no LLM, no randomness.

V3.2.0 Tier 1 deterministic quality improvements:

  A2: repair_hyphenation()  — fix "net-\nworking" → "networking"
  A5: extract_definitions() — find book-specific jargon ("Focus Base", etc.)
  A7: extract_ngram_keywords() — bigrams/trigrams for better coverage scoring

These run BEFORE the LLM sees the text, improving quality deterministically.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re
from collections import Counter

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
# A5: Definition / Concept Extraction
# ════════════════════════════════════════════════════════════════════════════

# V3.2.1: Broadened patterns to catch lowercase quoted jargon terms.
# Some books use single-quoted lowercase multi-word jargon (book-specific
# vocabulary the author coins and reuses). The old patterns required
# uppercase first letter — missed everything.

# Pattern 1: Quoted terms (single or double quotes, curly quotes) — 1-4 words
# This is the primary pattern. Catches lowercase jargon phrases and
# Capitalized multi-word concept names alike.
_QUOTED_TERM_PATTERN = re.compile(
    r'["\u201c\u2018]([a-zA-Z][a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})["\u201d\u2019]'
)

# Pattern 2: "X" is defined as / means / refers to / is called / is known as
_DEFINITION_VERB_PATTERN = re.compile(
    r'["\u201c\u2018]?([a-zA-Z][a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})["\u201d\u2019]?\s*'
    r"(?:is\s+(?:defined\s+as|called|known\s+as)|means|refers\s+to)",
    re.IGNORECASE,
)

# Pattern 3: The X principle/technique/concept/strategy/framework/cycle
_CONCEPT_NOUN_PATTERN = re.compile(
    r'(?:the\s+)["\u201c\u2018]?([a-zA-Z][a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})["\u201d\u2019]?\s*'
    r"(?:principle|technique|concept|strategy|framework|method|approach|cycle|rule|list|base|zone)",
    re.IGNORECASE,
)

# Stopwords for concept filtering — common words that shouldn't be "concepts"
# V18.20.4.8 (P6 / O-a5): the literal moved to the single canonical
# structural-stopwords module (fixes W-a5's 3 drifting copies; also removes
# the duplicated goes entry that was in this line).
# Re-exported under the original private name so the text_preprocessor
# facade's explicit underscore re-export keeps working (W-a6 shim contract).
from core.summarisation.structural_stopwords import CONCEPT_STOPWORDS as _CONCEPT_STOPWORDS


def _is_valid_concept(term: str) -> bool:
    """V3.3.2: Validate that a term is a real concept, not a sentence fragment.

    Rules:
    - Must be 2-4 words OR an all-caps acronym (3+ letters)
    - Single words are too noisy (proper nouns are single words)
    - Terms >4 words are likely sentence fragments
    - Must not start with a common verb/conjunction (sentence fragment indicator)
    - Must not contain sentence-ending punctuation
    - Must not contain duplicated words ("Casing Casing")
    - Must not start with common sentence-start words from this book
    """
    term = term.strip()
    if not term or len(term) < 4 or len(term) > 50:
        return False

    words = term.split()

    # V3.3.2: Reject terms longer than 4 words (likely sentence fragments)
    if len(words) > 4:
        return False

    # All-caps acronyms (3+ letters) are valid single-word concepts: SADR, CIA
    if len(words) == 1:
        if term.isupper() and len(term) >= 3:
            return True
        return False  # single non-acronym words are too noisy

    # V3.3.2: Reject terms with duplicated words ("Casing Casing")
    word_lower = [w.lower() for w in words]
    if len(word_lower) != len(set(word_lower)):
        return False

    # 2+ words: check it's not a sentence fragment
    # Skip if first word is a common verb/conjunction (sentence fragment)
    _SENTENCE_FRAGMENT_STARTS = frozenset(
        [
            "do",
            "does",
            "did",
            "is",
            "are",
            "was",
            "were",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "must",
            "shall",
            "and",
            "or",
            "but",
            "if",
            "when",
            "where",
            "why",
            "how",
            "what",
            "which",
            "who",
            "that",
            "this",
            "these",
            "those",
            "there",
            "here",
            "now",
            "then",
            "because",
            "although",
            "though",
            "since",
            "until",
            "unless",
            "whether",
            "while",
            "during",
            "before",
            "after",
            "above",
            "below",
            "important",
            "never",
            "intelligence",
            "waitress",
            "want",
        ]
    )
    if words[0].lower() in _SENTENCE_FRAGMENT_STARTS:
        return False

    # Skip if contains sentence-ending punctuation (it's a sentence, not a term)
    if any(c in term for c in ".!?;"):
        return False

    # V13.37.0: Reject terms containing newlines/tabs/carriage returns.
    # The V13.32.5 changelog CLAIMED this filter was added, but it was never
    # implemented (or was reverted). PDF table extraction produces garbage
    # like "Nai\nB" (a word broken across lines) which the regex patterns
    # match as a single concept because they use \s+ (matches newlines).
    # This caused 13/16 false-uncovered concepts in the rig-test
    # conversion log, triggering 10 consecutive empty gap-fill LLM calls.
    if any(c in term for c in "\n\t\r"):
        return False

    # V18.20.3.9 (Phase 2 / residuals sweep): the hardcoded character-name
    # frozenset (harvested from one book's cast — "character names from the
    # book", its own comment said) is REMOVED. Name-keyed filtering is
    # replaced at the CALLER (extract_definitions) with runtime NER: the
    # person/place entities of THIS book's text, extracted at run time.
    # Book-agnostic by construction — the names come from the source, never
    # from our code.

    # V10.12.9: Reject common English bigrams that are NOT concepts but pass
    # the 2-word rule.  These are sentence fragments / common phrases that
    # the academic-rigor XML output leaks as "concepts" (e.g., "As A",
    # "Understanding Of", "Headache Physicians").  Any term where ALL words
    # are common English words is likely a fragment, not a domain concept.
    _COMMON_ENGLISH_WORDS = frozenset(
        [
            "as",
            "a",
            "a",
            "the",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "must",
            "shall",
            "this",
            "that",
            "these",
            "those",
            "there",
            "here",
            "now",
            "then",
            "who",
            "whom",
            "whose",
            "which",
            "what",
            "when",
            "where",
            "why",
            "how",
            "all",
            "any",
            "some",
            "no",
            "not",
            "nor",
            "so",
            "yet",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "than",
            "too",
            "very",
            "just",
            "only",
            "own",
            "same",
            "so",
            "too",
            "very",
            "understanding",
            "knowledge",
            "concept",
            "idea",
            "theory",
            "principle",
            "method",
            "approach",
            "strategy",
            "technique",
            "process",
            "system",
            "structure",
            "function",
            "form",
            "type",
            "kind",
            "sort",
            "way",
            "means",
            "part",
            "section",
            "chapter",
            "page",
            "line",
            "figure",
            "table",
            "headache",
            "migraine",
            "treatment",
            "preventive",
            "acute",
            "clinical",
            "trial",
            "phase",
            "study",
            "patients",
            "drug",
            "dose",
            "mg",
            "efficacy",
            "safety",
            "adverse",
            "events",
            "side",
            "effects",
        ]
    )
    if all(w.lower() in _COMMON_ENGLISH_WORDS for w in words):
        return False

    # V10.12.9: Reject truncated fragments (e.g., "Locus Coe" from "Locus Coeruleus")
    # — if the term ends mid-word (last word is < 4 chars and not an acronym),
    # it's likely a truncation artifact.
    # V13.40.3: Also reject 2-word concepts where BOTH words are short (≤4 chars).
    # "Nai B" (from PDF table extraction) passes the old check because 'B'.isupper()
    # is True. Now we reject if the AVERAGE word length is < 4 (catches "Nai B",
    # "Ego Id", "Self Is" — all garbage from table column headers).
    if len(words[-1]) < 4 and not words[-1].isupper():
        return False
    # V13.40.3: Reject if both words in a 2-word concept are short
    if len(words) == 2:
        _avg_len = sum(len(w) for w in words) / len(words)
        if _avg_len < 4.0:
            return False

    # V13.40.5: Reject 3+ word concepts where the last word is short (≤4 chars).
    # "Self Is Simp" (from PDF table extraction) passes the old checks because
    # "Self" and "Simp" are > 4 chars. But the last word "Simp" is a truncation
    # artifact (likely "Simple" cut off). Reject if last word < 5 chars and the
    # concept has 3+ words (multi-word concepts with a short last word are
    # almost always truncated table cell content).
    if len(words) >= 3 and len(words[-1]) < 5:
        return False

    # V13.40.5: Reject concepts that look like sentence fragments from tables.
    # "Conquest Of The World" and "Complex And Highly Elaborate" are valid
    # English phrases but not concepts — they're extracted from PDF table cells
    # or section headings, not from the running text. Reject concepts where
    # ALL words are capitalized (title-case) AND the concept is 4+ words —
    # real concepts are usually mixed-case multi-word phrases
    if len(words) >= 4 and all(w[0].isupper() for w in words if w):
        return False

    return True


def extract_definitions(text: str, max_terms: int = 25) -> list[str]:
    """Extract book-specific defined terms/jargon from the text.

    V3.2.2: Added _is_valid_concept() filter to reject:
    - Single words (proper nouns)
    - Sentence fragments ("Do You Think You", "And That Usually")
    - Terms containing character names

    Now catches quoted multi-word coinages and definitional-verb patterns
    (structural — no book vocabulary in this docstring, V18.20.3.9).

    Requires terms to appear 2+ times (frequency filter) to avoid noise.
    """
    found: Counter = Counter()

    # V18.20.3.9 (Phase 2 / residuals sweep): runtime NER name filter —
    # terms containing a PERSON/PLACE entity of THIS book are story-cast
    # references, not concepts. Replaces the hardcoded character-name
    # frozenset that previously lived in _is_valid_concept.
    try:
        _ner_tokens = set()
        for _ent in get_all_ner_entities(text):
            _ner_tokens.update(str(_ent).split())
    except Exception:
        _ner_tokens = set()

    def _term_ok(term: str) -> bool:
        if not _is_valid_concept(term):
            return False
        if any(w in _ner_tokens for w in term.split()):
            return False
        return True

    # Pattern 1: Quoted terms — primary catch-all for author's jargon
    for m in _QUOTED_TERM_PATTERN.finditer(text):
        term = m.group(1).strip()
        if not _term_ok(term):
            continue
        words = term.split()
        if all(w.lower() in _CONCEPT_STOPWORDS for w in words):
            continue
        term_title = term.title()
        found[term_title] += 1

    # Pattern 2: Definitional verb patterns
    for m in _DEFINITION_VERB_PATTERN.finditer(text):
        term = m.group(1).strip()
        if not _term_ok(term):
            continue
        words = term.split()
        if all(w.lower() in _CONCEPT_STOPWORDS for w in words):
            continue
        term_title = term.title()
        found[term_title] += 1

    # Pattern 3: Concept noun patterns (The X principle/technique/cycle)
    for m in _CONCEPT_NOUN_PATTERN.finditer(text):
        term = m.group(1).strip()
        if not _term_ok(term):
            continue
        words = term.split()
        if all(w.lower() in _CONCEPT_STOPWORDS for w in words):
            continue
        term_title = term.title()
        found[term_title] += 1

    # V3.2.1: Frequency filter — require 2+ occurrences to filter noise.
    filtered = [(term, count) for term, count in found.most_common(max_terms) if count >= 2]
    # If too few pass the frequency filter, fall back to all found terms
    if len(filtered) < 3:
        filtered = found.most_common(max_terms)
    return [term for term, _ in filtered]


# ════════════════════════════════════════════════════════════════════════════
# A7: N-Gram Keyword Extraction
# ════════════════════════════════════════════════════════════════════════════

# Common English stopwords for keyword extraction
_KEYWORD_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "to",
        "in",
        "on",
        "at",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "we",
        "us",
        "our",
        "you",
        "your",
        "he",
        "him",
        "his",
        "she",
        "her",
        "i",
        "me",
        "my",
        "if",
        "then",
        "else",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "now",
        "here",
        "there",
        "what",
        "which",
        "who",
        "whom",
        "because",
        "as",
        "while",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "once",
        "chapter",
        "part",
        "section",
        "appendix",
        "book",
        "page",
        "get",
        "got",
        "make",
        "made",
        "take",
        "took",
        "go",
        "went",
        "come",
        "came",
        "see",
        "saw",
        "know",
        "knew",
        "think",
        "thought",
        "say",
        "said",
        "tell",
        "told",
        "ask",
        "asked",
        "find",
        "found",
        "want",
        "wanted",
        "need",
        "needed",
        "try",
        "tried",
        "use",
        "used",
        "work",
        "worked",
        "look",
        "looked",
        "seem",
        "seemed",
        "feel",
        "felt",
        "become",
        "became",
        "leave",
        "left",
        "put",
        "set",
        "sit",
        "sat",
        "stand",
        "stood",
        "run",
        "ran",
        "walk",
        "walked",
        "talk",
        "talked",
        "give",
        "gave",
        "keep",
        "kept",
        "let",
        "begin",
        "began",
        "show",
        "showed",
        "hear",
        "heard",
        "play",
        "played",
        "turn",
        "turned",
        "start",
        "started",
        "move",
        "moved",
        "live",
        "lived",
        "believe",
        "believed",
        "bring",
        "brought",
        "happen",
        "happened",
        "write",
        "wrote",
        "read",
        "lead",
        "led",
        "understand",
        "understood",
        "meet",
        "met",
        "pay",
        "paid",
        "answer",
        "speak",
        "spoke",
        "allow",
        "add",
        "grow",
        "open",
        "learn",
        "change",
        "remember",
        "consider",
        "appear",
        "buy",
        "serve",
        "die",
        "send",
        "expect",
        "build",
        "stay",
        "fall",
        "cut",
        "reach",
        "kill",
        "remain",
        "suggest",
        "raise",
        "pass",
        "sell",
        "require",
        "report",
        "decide",
        "pull",
        "return",
        "explain",
        "hope",
        "develop",
        "carry",
        "break",
        "receive",
        "agree",
        "support",
        "hit",
        "produce",
        "eat",
        "cover",
        "catch",
        "draw",
        "choose",
        "point",
        "save",
        "design",
        "pick",
        "wear",
        "hall",
        "near",
        "tree",
        "side",
        "foot",
        "spring",
        "race",
        "lake",
        "corner",
        "answer",
        "train",
        "plane",
        "art",
        "front",
        "river",
        "car",
        "garden",
        "ball",
        "box",
        "office",
        "police",
        "court",
        "yard",
        "room",
        "house",
        "door",
        "window",
        "wall",
        "floor",
        "roof",
        "street",
        "road",
        "bridge",
        "park",
        "store",
        "shop",
        "market",
        "bank",
        "school",
        "church",
        "hospital",
        "library",
        "museum",
        "theater",
        "hotel",
        "restaurant",
        "farm",
        "factory",
        "station",
        "airport",
        "harbor",
        "path",
        "trail",
        "hill",
        "mountain",
        "valley",
        "forest",
        "desert",
        "island",
        "coast",
        "shore",
        "beach",
        "ocean",
        "sea",
        "water",
        "fire",
        "earth",
        "air",
        "wind",
        "rain",
        "snow",
        "ice",
        "fog",
        "storm",
        "cloud",
        "sun",
        "moon",
        "star",
        "light",
        "dark",
        "day",
        "night",
        "morning",
        "evening",
        "noon",
        "time",
        "year",
        "month",
        "week",
        "hour",
        "minute",
        "second",
        "man",
        "woman",
        "boy",
        "girl",
        "child",
        "baby",
        "person",
        "people",
        "family",
        "friend",
        "enemy",
        "stranger",
        "king",
        "queen",
        "prince",
        "princess",
        "president",
        "leader",
        "teacher",
        "student",
        "doctor",
        "nurse",
        "farmer",
        "soldier",
        "sailor",
        "pilot",
        "driver",
        "cook",
        "baker",
        "artist",
        "musician",
        "writer",
        "singer",
        "dancer",
        "actor",
        "lawyer",
        "judge",
        "priest",
        "monk",
        "table",
        "chair",
        "bed",
        "sofa",
        "desk",
        "shelf",
        "cabinet",
        "drawer",
        "basket",
        "bag",
        "purse",
        "wallet",
        "shirt",
        "pants",
        "dress",
        "skirt",
        "coat",
        "hat",
        "cap",
        "shoe",
        "sock",
        "boot",
        "glove",
        "scarf",
        "belt",
        "tie",
        "food",
        "bread",
        "meat",
        "fish",
        "fruit",
        "vegetable",
        "rice",
        "wheat",
        "corn",
        "bean",
        "pea",
        "soup",
        "stew",
        "pie",
        "cake",
        "cookie",
        "candy",
        "sugar",
        "salt",
        "pepper",
        "spice",
        "herb",
        "oil",
        "butter",
        "milk",
        "cheese",
        "yogurt",
        "egg",
        "chicken",
        "beef",
        "pork",
        "lamb",
        "duck",
        "turkey",
        "wine",
        "beer",
        "coffee",
        "tea",
        "juice",
        "soda",
        "dog",
        "cat",
        "horse",
        "cow",
        "pig",
        "sheep",
        "goat",
        "goose",
        "rabbit",
        "mouse",
        "rat",
        "bird",
        "snake",
        "frog",
        "turtle",
        "lizard",
        "spider",
        "ant",
        "bee",
        "fly",
        "worm",
        "tree",
        "flower",
        "grass",
        "bush",
        "leaf",
        "branch",
        "root",
        "seed",
        "berry",
        "nut",
        "bark",
        "wood",
        "stick",
        "stone",
        "rock",
        "sand",
        "dirt",
        "mud",
        "clay",
        "metal",
        "gold",
        "silver",
        "iron",
        "copper",
        "steel",
        "glass",
        "plastic",
        "rubber",
        "paper",
        "cloth",
        "leather",
        "cotton",
        "wool",
        "silk",
        "linen",
        "thread",
        "string",
        "rope",
        "wire",
        "chain",
        "nail",
        "screw",
        "bolt",
        "hammer",
        "saw",
        "knife",
        "fork",
        "spoon",
        "plate",
        "bowl",
        "cup",
        "glass",
        "bottle",
        "jar",
        "pot",
        "pan",
        "dish",
        "soap",
        "towel",
        "brush",
        "comb",
        "mirror",
        "lamp",
        "candle",
        "match",
        "fire",
        "flame",
        "smoke",
        "ash",
        "dust",
        "book",
        "letter",
        "map",
        "picture",
        "photo",
        "painting",
        "drawing",
        "sign",
        "flag",
        "ticket",
        "card",
        "music",
        "song",
        "dance",
        "game",
        "sport",
        "fight",
        "battle",
        "war",
        "peace",
        "love",
        "hate",
        "anger",
        "fear",
        "joy",
        "sad",
        "happy",
        "good",
        "bad",
        "big",
        "small",
        "tall",
        "short",
        "long",
        "wide",
        "narrow",
        "thick",
        "thin",
        "heavy",
        "light",
        "fast",
        "slow",
        "hot",
        "cold",
        "warm",
        "cool",
        "wet",
        "dry",
        "hard",
        "soft",
        "smooth",
        "rough",
        "sharp",
        "dull",
        "clean",
        "dirty",
        "old",
        "new",
        "young",
        "beautiful",
        "ugly",
        "plain",
        "rich",
        "poor",
        "strong",
        "weak",
        "smart",
        "stupid",
        "wise",
        "foolish",
        "brave",
        "shy",
        "quiet",
        "loud",
        "silent",
        "calm",
        "crazy",
        "right",
        "wrong",
        "true",
        "false",
        "real",
        "fake",
        "alive",
        "dead",
        "safe",
        "dangerous",
        "open",
        "closed",
        "full",
        "empty",
        "easy",
        "difficult",
        "simple",
        "complex",
        "possible",
        "impossible",
        "early",
        "late",
        "first",
        "last",
        "next",
        "previous",
        "same",
        "different",
        "important",
        "necessary",
        "ready",
        "example",
        "however",
        "whether",
        "though",
        "since",
        "unless",
        "toward",
        "around",
        "below",
        "above",
        "across",
        "behind",
        "looking",
        "making",
        "getting",
        "going",
        "coming",
        "taking",
        "thing",
        "things",
        "every",
        "makes",
        "might",
        "maybe",
        "opened",
        "really",
        "right",
        "started",
        "original",
        "wanted",
        "there",
        "myself",
        "someone",
        "something",
        "without",
        "throughout",
        "against",
        "between",
        "should",
        "would",
        "could",
        "before",
        "during",
        "after",
        "while",
        "being",
        "having",
        "their",
        "other",
        "about",
        "again",
        "still",
        "even",
        "only",
        "also",
        "just",
        "much",
        "many",
        "some",
        "most",
        "more",
        "less",
        "well",
        "often",
        "always",
        "never",
        "already",
        "further",
    ]
)


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase word tokens (4+ chars, no stopwords)."""
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return [w for w in words if w not in _KEYWORD_STOPWORDS]


def extract_ngram_keywords(text: str, n: int = 18) -> list[str]:
    """Extract top-n content keywords using unigrams + bigrams + trigrams.

    Replaces the old single-word keyword extraction. Bigrams and trigrams
    capture multi-word concepts (book-specific jargon phrases, capitalized
    concept names) that single-word extraction misses entirely.

    Returns a ranked list of keyword strings (may be 1, 2, or 3 words).
    """
    tokens = _tokenize(text)
    if not tokens:
        return []

    scores: Counter = Counter()

    # Unigrams (weight 1.0)
    for w in tokens:
        scores[w] += 1

    # Bigrams (weight 1.8 — higher because multi-word concepts are more
    # meaningful for coverage scoring)
    for i in range(len(tokens) - 1):
        bg = f"{tokens[i]} {tokens[i + 1]}"
        scores[bg] += 1.8

    # Trigrams (weight 2.2)
    for i in range(len(tokens) - 2):
        tg = f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"
        scores[tg] += 2.2

    # Sort by score descending, then alphabetically for determinism
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return [term for term, _ in ranked[:n]]


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
# Main preprocessor class — combines all steps
# ════════════════════════════════════════════════════════════════════════════


class DeterministicPreprocessor:
    """Runs all deterministic pre-processing on chapter text.

    Usage:
        pp = DeterministicPreprocessor()
        clean_text = pp.preprocess(raw_text)
        concepts = pp.extract_concepts(raw_text)
        callouts = pp.extract_callouts(raw_text)
    """

    def __init__(self) -> None:
        pass

    def preprocess(self, text: str) -> str:
        """Run all deterministic text cleaning steps (A2 + A3)."""
        if not text:
            return text
        # A2: Hyphenation repair
        text = repair_hyphenation(text)
        # A3: Smart paragraph joining
        text = smart_paragraph_joining(text)
        return text

    def extract_concepts(self, text: str) -> list[str]:
        """Extract must-cover concepts (A5)."""
        return extract_definitions(text)

    def extract_callouts(self, text: str) -> list[str]:
        """Extract high-value callout sentences."""
        return extract_callouts(text)

    def extract_keywords(self, text: str, n: int = 18) -> list[str]:
        """Extract n-gram keywords for coverage scoring (A7)."""
        return extract_ngram_keywords(text, n)

    def detect_sections(self, text: str) -> list[str]:
        """Detect sub-headings within a chapter (A6)."""
        return detect_sections(text)

    def analyze(self, text: str) -> dict:
        """Run all analyses and return a combined result.

        Used by the converter to pass pre-computed data to the summarizer.
        """
        return {
            "concepts": self.extract_concepts(text),
            "callouts": self.extract_callouts(text),
            "keywords": self.extract_keywords(text),
            "sections": self.detect_sections(text),
        }


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


# ════════════════════════════════════════════════════════════════════════════
# C4: Numeric / Quote Verification
# ════════════════════════════════════════════════════════════════════════════

# Extract numbers (including percentages, decimals, years)
_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?(?:%| percent)?\b")
# Extract quoted text
_QUOTE_PATTERN = re.compile(r'["\u201c]([^"]{10,200})["\u201d]')


def verify_numbers_and_quotes(bullet: str, source_text: str) -> tuple:
    """V3.3.0 C4: Verify numbers and quotes in a bullet against source.

    Returns (is_valid, reasons) where:
    - is_valid: True if all numbers/quotes are found in source
    - reasons: list of strings explaining any failures
    """
    reasons = []
    source_lower = source_text.lower()

    # Check numbers
    numbers = _NUMBER_PATTERN.findall(bullet)
    for num in numbers:
        # V9.0.0 P3-3: don't skip numbers 1-5 — a fabricated "3 steps" or
        # "5 users" should be caught.  Previously these were skipped, which
        # let invented small numbers pass verification.
        if num.lower() not in source_lower:
            reasons.append(f"number '{num}' not found in source")
            return False, reasons

    # Check quotes
    quotes = _QUOTE_PATTERN.findall(bullet)
    for quote in quotes:
        # Use fuzzy matching — the quote might be slightly paraphrased
        quote_lower = quote.lower()
        # Check if at least 60% of the quote appears in source
        words = quote_lower.split()
        if len(words) >= 5:
            found_words = sum(1 for w in words if w in source_lower)
            if found_words / len(words) < 0.6:
                reasons.append(f"quote '{quote[:40]}...' not found in source")
                return False, reasons

    return True, reasons


# ════════════════════════════════════════════════════════════════════════════
# C5: Sentence Boundary Normalization
# ════════════════════════════════════════════════════════════════════════════

# Split text into sentences
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def normalize_sentence_boundaries(bullet: str, max_sentences: int = 2, max_words: int = 40) -> str:
    """V3.3.0 C5: Ensure each bullet is 1-2 complete sentences.

    - Splits run-on sentences at sentence boundaries
    - Merges fragments (lines without ending punctuation)
    - Truncates to max_sentences
    - Caps at max_words
    """
    if not bullet:
        return bullet

    bullet = bullet.strip()

    # Split into sentences
    sentences = _SENTENCE_SPLIT.split(bullet)

    # Filter out empty fragments
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]

    if not sentences:
        return bullet

    # Keep only first max_sentences
    kept = sentences[:max_sentences]

    # Join and cap at max_words
    result = " ".join(kept)
    words = result.split()
    if len(words) > max_words:
        result = " ".join(words[:max_words])
        # Add ellipsis if truncated mid-sentence
        if not result.endswith((".", "!", "?")):
            result += "…"

    # Ensure it ends with punctuation
    if result and result[-1] not in ".!?":
        result += "."

    return result


# ════════════════════════════════════════════════════════════════════════════
# E2: OCR Quality Scoring
# ════════════════════════════════════════════════════════════════════════════

# Top 100 common English words for OCR quality scoring
_COMMON_WORDS = frozenset(
    [
        "the",
        "be",
        "to",
        "of",
        "and",
        "a",
        "in",
        "that",
        "have",
        "i",
        "it",
        "for",
        "not",
        "on",
        "with",
        "he",
        "as",
        "you",
        "do",
        "at",
        "this",
        "but",
        "his",
        "by",
        "from",
        "they",
        "we",
        "say",
        "her",
        "she",
        "or",
        "an",
        "will",
        "my",
        "one",
        "all",
        "would",
        "there",
        "their",
        "what",
        "so",
        "up",
        "out",
        "if",
        "about",
        "who",
        "get",
        "which",
        "go",
        "me",
        "when",
        "make",
        "can",
        "like",
        "time",
        "no",
        "just",
        "him",
        "know",
        "take",
        "people",
        "into",
        "year",
        "your",
        "good",
        "some",
        "could",
        "them",
        "see",
        "other",
        "than",
        "then",
        "now",
        "look",
        "only",
        "come",
        "its",
        "over",
        "think",
        "also",
        "back",
        "after",
        "use",
        "two",
        "how",
        "our",
        "work",
        "first",
        "well",
        "way",
        "even",
        "new",
        "want",
        "because",
        "any",
        "these",
        "give",
        "day",
        "most",
        "us",
        "is",
        "are",
        "was",
        "were",
        "has",
        "had",
        "did",
        "been",
        "being",
        "am",
    ]
)


def score_ocr_quality(text: str) -> float:
    """V3.3.0 E2: Score OCR output quality 0.0-1.0.

    Scores based on:
    - Space ratio (normal English has ~12-15% spaces)
    - Common-word ratio (what % of words are in top-100 English words?)
    - Average word length (English avg ≈ 4.5-5.5 chars)
    - Alpha character ratio (should be > 70%)

    Returns 0.0 (garbage) to 1.0 (clean text).
    Below 0.4 = likely OCR failure.
    """
    if not text or len(text) < 20:
        return 0.0

    total_chars = len(text)
    spaces = text.count(" ")
    alpha_chars = sum(1 for c in text if c.isalpha())
    words = text.split()

    if not words:
        return 0.0

    # 1. Space ratio (ideal: 0.12-0.18)
    space_ratio = spaces / total_chars
    space_score = (
        1.0 if 0.10 <= space_ratio <= 0.22 else max(0.0, 1.0 - abs(space_ratio - 0.15) * 5)
    )

    # 2. Common-word ratio (ideal: > 20%)
    word_count = len(words)
    common_count = sum(1 for w in words if w.lower().strip(".,!?;:\"'") in _COMMON_WORDS)
    common_ratio = common_count / word_count if word_count else 0
    common_score = min(1.0, common_ratio * 4)  # 25% common = 1.0

    # 3. Average word length (ideal: 4.5-5.5)
    avg_len = sum(len(w.strip(".,!?;:\"'")) for w in words) / word_count
    len_score = 1.0 if 3.5 <= avg_len <= 7.0 else max(0.0, 1.0 - abs(avg_len - 5.0) * 0.3)

    # 4. Alpha character ratio (ideal: > 70%)
    alpha_ratio = alpha_chars / total_chars
    alpha_score = min(1.0, alpha_ratio / 0.70) if alpha_ratio < 0.70 else 1.0

    # Weighted average
    score = space_score * 0.2 + common_score * 0.4 + len_score * 0.2 + alpha_score * 0.2
    return score


# ════════════════════════════════════════════════════════════════════════════
# G1: Sentence Complexity Scoring
# ════════════════════════════════════════════════════════════════════════════

# Extended common English word list (top ~500 most frequent words)
_COMMON_500 = frozenset(
    [
        "the",
        "be",
        "to",
        "of",
        "and",
        "a",
        "in",
        "that",
        "have",
        "i",
        "it",
        "for",
        "not",
        "on",
        "with",
        "he",
        "as",
        "you",
        "do",
        "at",
        "this",
        "but",
        "his",
        "by",
        "from",
        "they",
        "we",
        "say",
        "her",
        "she",
        "or",
        "an",
        "will",
        "my",
        "one",
        "all",
        "would",
        "there",
        "their",
        "what",
        "so",
        "up",
        "out",
        "if",
        "about",
        "who",
        "get",
        "which",
        "go",
        "me",
        "when",
        "make",
        "can",
        "like",
        "time",
        "no",
        "just",
        "him",
        "know",
        "take",
        "people",
        "into",
        "year",
        "your",
        "good",
        "some",
        "could",
        "them",
        "see",
        "other",
        "than",
        "then",
        "now",
        "look",
        "only",
        "come",
        "its",
        "over",
        "think",
        "also",
        "back",
        "after",
        "use",
        "two",
        "how",
        "our",
        "work",
        "first",
        "well",
        "way",
        "even",
        "new",
        "want",
        "because",
        "any",
        "these",
        "give",
        "day",
        "most",
        "us",
        "is",
        "are",
        "was",
        "were",
        "has",
        "had",
        "did",
        "been",
        "being",
        "am",
        "very",
        "more",
        "many",
        "much",
        "such",
        "very",
        "great",
        "own",
        "old",
        "right",
        "left",
        "high",
        "low",
        "big",
        "small",
        "long",
        "short",
        "hard",
        "easy",
        "open",
        "close",
        "start",
        "stop",
        "begin",
        "end",
        "live",
        "dead",
        "give",
        "take",
        "find",
        "lose",
        "keep",
        "let",
        "make",
        "put",
        "set",
        "get",
        "go",
        "come",
        "see",
        "know",
        "think",
        "say",
        "tell",
        "ask",
        "call",
        "try",
        "need",
        "feel",
        "become",
        "leave",
        "seem",
        "help",
        "turn",
        "show",
        "run",
        "walk",
        "talk",
        "sit",
        "stand",
        "fall",
        "rise",
        "move",
        "play",
        "read",
        "write",
        "eat",
        "drink",
        "sleep",
        "wake",
        "dream",
        "love",
        "hate",
        "like",
        "want",
        "hope",
        "wish",
        "fear",
        "trust",
        "believe",
        "agree",
        "follow",
        "lead",
        "send",
        "bring",
        "buy",
        "sell",
        "pay",
        "cost",
        "spend",
        "save",
        "borrow",
        "lend",
        "owe",
        "earn",
        "win",
        "lose",
        "meet",
        "miss",
        "hit",
        "cut",
        "break",
        "build",
        "fix",
        "change",
        "stop",
        "start",
        "continue",
        "remain",
        "stay",
        "leave",
        "arrive",
        "depart",
        "enter",
        "exit",
        "join",
        "leave",
        "return",
        "visit",
        "travel",
        "drive",
        "ride",
        "fly",
        "sail",
        "walk",
        "run",
        "swim",
        "climb",
        "fall",
        "jump",
        "dance",
        "sing",
        "speak",
        "write",
        "read",
        "listen",
        "watch",
        "look",
        "see",
        "hear",
        "smell",
        "taste",
        "touch",
        "feel",
        "try",
        "use",
        "make",
        "do",
        "get",
        "have",
        "keep",
        "lose",
        "find",
        "give",
        "take",
        "put",
        "set",
        "business",
        "company",
        "group",
        "team",
        "people",
        "person",
        "man",
        "woman",
        "child",
        "friend",
        "family",
        "world",
        "life",
        "time",
        "way",
        "day",
        "year",
        "week",
        "month",
        "hour",
        "minute",
        "second",
        "place",
        "home",
        "work",
        "school",
        "book",
        "word",
        "number",
        "name",
        "part",
        "side",
        "point",
        "case",
        "fact",
        "question",
        "answer",
        "problem",
        "result",
        "reason",
        "idea",
        "plan",
        "method",
        "system",
        "process",
        "service",
        "product",
        "customer",
        "market",
        "money",
        "price",
        "cost",
        "value",
        "quality",
        "standard",
        "level",
        "type",
        "form",
        "kind",
        "sort",
        "class",
        "group",
        "set",
        "list",
        "line",
        "point",
        "area",
        "field",
        "room",
        "house",
        "building",
        "street",
        "road",
        "city",
        "town",
        "country",
        "state",
        "nation",
        "world",
        "north",
        "south",
        "east",
        "west",
        "left",
        "right",
        "front",
        "back",
        "top",
        "bottom",
        "side",
        "center",
        "middle",
        "end",
        "important",
        "possible",
        "necessary",
        "difficult",
        "different",
        "similar",
        "same",
        "new",
        "old",
        "first",
        "last",
        "next",
        "previous",
        "main",
        "major",
        "minor",
        "primary",
        "secondary",
        "general",
        "specific",
        "public",
        "private",
        "full",
        "empty",
        "complete",
        "partial",
        "total",
        "entire",
        "whole",
        "single",
        "double",
        "multiple",
        "complex",
        "simple",
        "true",
        "false",
        "right",
        "wrong",
        "good",
        "bad",
        "better",
        "worse",
        "best",
        "worst",
        "high",
        "low",
        "big",
        "small",
        "tall",
        "short",
        "long",
        "wide",
        "narrow",
        "thick",
        "thin",
        "heavy",
        "light",
        "fast",
        "slow",
        "hot",
        "cold",
        "warm",
        "cool",
        "dry",
        "wet",
        "able",
        "unable",
        "possible",
        "impossible",
        "available",
        "unavailable",
        "suitable",
        "unsuitable",
        "appropriate",
        "inappropriate",
        "relevant",
        "irrelevant",
        "effective",
        "ineffective",
        "efficient",
        "inefficient",
        "successful",
        "unsuccessful",
        "useful",
        "useless",
        "helpful",
        "unhelpful",
        "clear",
        "unclear",
        "obvious",
        "certain",
        "uncertain",
        "sure",
        "unsure",
        "definite",
        "indefinite",
        "exact",
        "approximate",
        "precise",
        "accurate",
        "inaccurate",
        "correct",
        "incorrect",
        "valid",
        "invalid",
        "real",
        "fake",
        "true",
        "false",
        "actual",
        "potential",
        "actual",
        "expected",
        "unexpected",
        "normal",
        "unusual",
        "common",
        "rare",
        "frequent",
        "occasional",
        "regular",
        "irregular",
        "consistent",
        "inconsistent",
        "stable",
        "unstable",
        "secure",
        "insecure",
        "safe",
        "dangerous",
        "healthy",
        "unhealthy",
        "strong",
        "weak",
        "powerful",
        "powerless",
        "active",
        "passive",
        "positive",
        "negative",
        "productive",
        "unproductive",
        "creative",
        "destructive",
        "constructive",
        "informative",
        "persuasive",
        "convincing",
        "credible",
        "reliable",
        "dependable",
        "trustworthy",
        "honest",
        "dishonest",
        "fair",
        "unfair",
        "just",
        "unjust",
        "equal",
        "unequal",
        "free",
        "restricted",
        "open",
        "closed",
        "public",
        "private",
        "personal",
        "professional",
        "social",
        "political",
        "economic",
        "cultural",
        "historical",
        "scientific",
        "technical",
        "practical",
        "theoretical",
        "abstract",
        "concrete",
        "general",
        "specific",
        "detailed",
        "brief",
        "thorough",
        "complete",
        "partial",
        "total",
        "entire",
        "whole",
        "comprehensive",
        "extensive",
        "limited",
        "broad",
        "narrow",
        "deep",
        "shallow",
        "simple",
        "complex",
        "complicated",
        "straightforward",
        "difficult",
        "easy",
        "hard",
        "challenging",
        "manageable",
        "achievable",
        "realistic",
        "unrealistic",
        "practical",
        "impractical",
        "functional",
        "dysfunctional",
        "operational",
        "effective",
        "successful",
        "proper",
        "improper",
        "appropriate",
        "inappropriate",
        "adequate",
        "inadequate",
        "sufficient",
        "insufficient",
        "excessive",
        "minimal",
        "maximum",
        "optimum",
        "optimal",
        "ideal",
        "perfect",
        "imperfect",
        "complete",
        "incomplete",
        "entire",
        "partial",
        "total",
        "full",
        "empty",
        "whole",
    ]
)


def score_bullet_complexity(bullet: str) -> float:
    """V3.4.0 G1: Score a bullet's language complexity 0.0 (simple) to 1.0 (complex).

    Criteria:
    - Average word length (>5.5 = complex, +0.3 weight)
    - Sentence length in words (>25 = complex, +0.25 weight)
    - % of words NOT in top-500 common English list (>15% = complex, +0.3 weight)
    - Passive voice detection ("is/was/been + past participle", +0.15 weight)

    Returns 0.0 (very simple/plain) to 1.0 (very complex/technical).
    Below 0.3 = already plain — skip LLM simplification.
    """
    if not bullet or len(bullet) < 10:
        return 0.0

    words = bullet.split()
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # 1. Average word length (weight 0.3)
    avg_len = sum(len(w.strip(".,!?;:\"'")) for w in words) / word_count
    len_score = max(0.0, min(1.0, (avg_len - 3.5) / 3.0))  # 3.5→0, 6.5→1.0

    # 2. Sentence length (weight 0.25)
    sent_len_score = max(0.0, min(1.0, (word_count - 10) / 25.0))  # 10→0, 35→1.0

    # 3. % uncommon words (weight 0.3)
    common_count = sum(1 for w in words if w.lower().strip(".,!?;:\"'") in _COMMON_500)
    uncommon_ratio = 1.0 - (common_count / word_count)
    uncommon_score = max(0.0, min(1.0, uncommon_ratio / 0.30))  # 0%→0, 30%→1.0

    # 4. Passive voice detection (weight 0.15)
    passive_patterns = re.compile(
        r"\b(?:is|are|was|were|been|being|be)\s+\w+ed\b",
        re.IGNORECASE,
    )
    has_passive = bool(passive_patterns.search(bullet))
    passive_score = 1.0 if has_passive else 0.0

    # Weighted average
    complexity = (
        len_score * 0.30 + sent_len_score * 0.25 + uncommon_score * 0.30 + passive_score * 0.15
    )
    return min(1.0, complexity)


# ════════════════════════════════════════════════════════════════════════════
# G2: Vocabulary Overlap Pre-Check
# ════════════════════════════════════════════════════════════════════════════


def vocabulary_overlap_score(bullet: str) -> float:
    """V3.4.0 G2: Check what % of a bullet's words are common English.

    Returns 0.0 (all words are rare/jargon) to 1.0 (all words are common).
    > 0.90 = bullet is already in plain language — skip simplification.
    < 0.70 = bullet has significant jargon — prioritize for simplification.
    """
    if not bullet:
        return 1.0

    words = [w.lower().strip(".,!?;:\"'") for w in bullet.split()]
    if not words:
        return 1.0

    common_count = sum(1 for w in words if w in _COMMON_500)
    return common_count / len(words)


def should_skip_simplification(bullet: str) -> tuple:
    """V3.4.0 G1+G2: Determine if a bullet should skip LLM simplification.

    Returns (should_skip, reason) where:
    - should_skip: True if the bullet is already simple enough
    - reason: explanation string

    A bullet is skipped if:
    - G2: >90% of words are common English (already plain)
    - G1: complexity score < 0.3 (not complex enough to need simplification)
    """
    if not bullet or len(bullet.strip()) < 5:
        return True, "too short"

    vocab_score = vocabulary_overlap_score(bullet)
    if vocab_score > 0.90:
        return True, f"already plain ({vocab_score:.0%} common words)"

    complexity = score_bullet_complexity(bullet)
    if complexity < 0.30:
        return True, f"low complexity ({complexity:.2f}/1.0)"

    return False, f"needs simplification (vocab={vocab_score:.0%}, complexity={complexity:.2f})"


# ════════════════════════════════════════════════════════════════════════════
# I1: Named Entity Recognition (regex-based)
# ════════════════════════════════════════════════════════════════════════════

# Patterns for NER
_PERSON_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Professor)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    r'|"([A-Z][a-z]+)"\s+(?:said|told|went|met|decided|noticed|began|arrived|greeted|shook|introduced|called)'
    r"|\b([A-Z][a-z]+)\s+(?:said|told|went|met|decided|noticed|began|arrived|greeted|shook|introduced|called)\b"
)

_ORG_PATTERN = re.compile(
    r"(?:worked\s+for|company|firm|organization|corporation|agency|institute|university)\s+"
    r"(?:called|named|known\s+as)?\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})"
    r'|"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})"\s+(?:company|firm|corporation)'
)

_LOCATION_PATTERN = re.compile(
    r"\b(?:in|at|to|from|near|located\s+in)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
    r"(?:\s*,\s*([A-Z][a-z]+))?"
)

# Known false positives to exclude
_NER_EXCLUDE = frozenset(
    [
        "The",
        "This",
        "That",
        "These",
        "Those",
        "There",
        "Here",
        "Now",
        "Then",
        "Today",
        "Yesterday",
        "Tomorrow",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "Spring",
        "Summer",
        "Fall",
        "Winter",
        "North",
        "South",
        "East",
        "West",
        "Chapter",
        "Section",
        "Part",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Yes",
        "No",
        "OK",
    ]
)


def extract_named_entities(text: str) -> dict[str, list[str]]:
    """V3.4.0 I1 / V3.7.0 Phase 2.1: Extract named entities from text.

    V3.7.0: Upgraded to use spaCy if available (much more accurate).
    Falls back to regex patterns if spaCy is not installed.

    Used to:
    - Exclude proper nouns from keyword extraction
    - Reject terms containing NER entities in concept extraction
    - Detect narrative bullets (2+ NER entities = likely narrative)
    """
    # V3.7.0: Try spaCy first (much more accurate)
    try:
        # V10.31.0 (Sprint 4.6): use shared spacy singleton
        from core.llm.model_singletons import get_spacy_nlp

        _SPACY_NLP = get_spacy_nlp("en_core_web_sm")

        if _SPACY_NLP is not None:
            doc = _SPACY_NLP(text[:50000])  # Limit to prevent timeout on large texts
            persons = set()
            organizations = set()
            locations = set()
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    persons.add(ent.text.strip())
                elif ent.label_ == "ORG":
                    organizations.add(ent.text.strip())
                elif ent.label_ in ("GPE", "LOC"):
                    locations.add(ent.text.strip())

            return {
                "persons": sorted(persons),
                "organizations": sorted(organizations),
                "locations": sorted(locations),
            }
    except ImportError:
        pass  # spaCy not installed — fall back to regex
    except Exception as _e:
        logger.debug(
            "ignored %s: %s", type(_e).__name__, _e
        )  # Any spaCy error — fall back to regex

    # Fallback: regex-based NER (V3.4.0 original implementation)
    persons = set()
    organizations = set()
    locations = set()

    for m in _PERSON_PATTERN.finditer(text):
        for g in m.groups():
            if g and g not in _NER_EXCLUDE and len(g) > 2:
                persons.add(g.strip())

    for m in _ORG_PATTERN.finditer(text):
        for g in m.groups():
            if g and g not in _NER_EXCLUDE and len(g) > 2:
                organizations.add(g.strip())

    for m in _LOCATION_PATTERN.finditer(text):
        loc = m.group(1)
        if loc and loc not in _NER_EXCLUDE and len(loc) > 2:
            if loc[0].isupper() and not loc.endswith(("ing", "ed", "ly", "tion")):
                locations.add(loc.strip())

    return {
        "persons": sorted(persons),
        "organizations": sorted(organizations),
        "locations": sorted(locations),
    }


# V3.7.0: Cached spaCy model (loaded once, reused across calls)
# V3.9.0: Multi-language support — loads appropriate model based on language
# V18.20.1.0 (D3): centralized to _runtime_state.state.spacy_nlp + .spacy_lang.
# Backward-compat proxies kept so existing ``monkeypatch.setattr`` calls don't
# break (but the impl reads/writes state.spacy_nlp directly).
from core.summarisation._runtime_state import state as _runtime_state

_SPACY_NLP = None  # backward-compat proxy (impl uses _runtime_state.spacy_nlp)
_SPACY_LANG = None  # backward-compat proxy (impl uses _runtime_state.spacy_lang)


def _load_spacy_model(language: str = "en"):
    """V3.9.0: Load the appropriate spaCy model based on language.

    Supported languages:
    - en: en_core_web_sm (English)
    - fa: fa_core_news_sm (Persian/Farsi)
    - fr: fr_core_news_sm (French)
    - de: de_core_news_sm (German)
    - es: es_core_news_sm (Spanish)
    """
    # V18.20.1.0 (D3): read/write the centralized state object directly.
    # This is the fix for the order-dependent test failures: patches against
    # the re-export module (text_preprocessor._SPACY_NLP) OR the impl module
    # (text_preprocessor_impl._SPACY_NLP) both propagate because the impl
    # reads the shared _runtime_state.state object.

    # Map language codes to spaCy model names
    model_map = {
        "en": "en_core_web_sm",
        "fa": "fa_core_news_sm",
        "fr": "fr_core_news_sm",
        "de": "de_core_news_sm",
        "es": "es_core_news_sm",
        "it": "it_core_news_sm",
        "nl": "nl_core_news_sm",
        "pt": "pt_core_news_sm",
        "ru": "ru_core_news_sm",
        "zh": "zh_core_web_sm",
    }

    model_name = model_map.get(language, "en_core_web_sm")

    # Return cached model if same language
    if _runtime_state.spacy_nlp is not None and _runtime_state.spacy_lang == language:
        return _runtime_state.spacy_nlp

    # V10.31.0 (Sprint 4.6): use shared spacy singleton (one per model name)
    from core.llm.model_singletons import get_spacy_nlp

    _runtime_state.spacy_nlp = get_spacy_nlp(model_name)
    _runtime_state.spacy_lang = language
    return _runtime_state.spacy_nlp


def get_all_ner_entities(text: str) -> set:
    """V3.4.0 I1: Return all NER entities as a single set for quick lookup.

    Used by keyword extraction to exclude proper nouns, and by concept
    extraction to reject terms containing entity names.
    """
    entities = extract_named_entities(text)
    all_entities = set()
    for entity_list in entities.values():
        for e in entity_list:
            all_entities.add(e)
            for word in e.split():
                all_entities.add(word)
    return all_entities


# ════════════════════════════════════════════════════════════════════════════
# J1: Bullet Ordering by Topic Clustering
# ════════════════════════════════════════════════════════════════════════════


def _bullet_similarity(b1: str, b2: str) -> float:
    """Compute cosine similarity between two bullets using word overlap."""
    words1 = set(b1.lower().split())
    words2 = set(b2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def order_bullets_by_topic(bullets: list[str]) -> list[str]:
    """V3.4.1 J1: Order bullets by topic clustering for structured readability.

    Groups related bullets together using greedy clustering:
    1. Start with the first bullet
    2. Find the next most similar unused bullet
    3. Add it to the current cluster
    4. When similarity drops below threshold, start a new cluster

    This makes keypoints read like a structured outline instead of a random list.
    """
    if len(bullets) <= 2:
        return bullets

    ordered = []
    used = [False] * len(bullets)

    # Start with the first bullet
    ordered.append(bullets[0])
    used[0] = True
    current = bullets[0]

    for _ in range(len(bullets) - 1):
        best_idx = -1
        best_sim = -1.0
        for i, bp in enumerate(bullets):
            if used[i]:
                continue
            sim = _bullet_similarity(current, bp)
            if sim > best_sim:
                best_sim = sim
                best_idx = i
        if best_idx >= 0:
            ordered.append(bullets[best_idx])
            used[best_idx] = True
            current = bullets[best_idx]

    return ordered


# ════════════════════════════════════════════════════════════════════════════
# F1: Summary Length Validation
# ════════════════════════════════════════════════════════════════════════════


def validate_summary_length(
    text: str, min_words: int = 150, max_words: int = 1200, section: str = "summary"
) -> tuple:
    """V3.4.1 F1: Validate summary length and flag if out of bounds.

    Returns (is_valid, word_count, message).
    """
    if not text:
        return False, 0, f"{section}: empty"

    words = text.split()
    word_count = len(words)

    if word_count < min_words:
        return False, word_count, f"{section}: too short ({word_count} words, min {min_words})"
    if word_count > max_words:
        return False, word_count, f"{section}: too long ({word_count} words, max {max_words})"
    return True, word_count, f"{section}: OK ({word_count} words)"


def truncate_summary(text: str, max_words: int) -> str:
    """Truncate a summary to max_words at the sentence boundary."""
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    # Find the last complete sentence within max_words
    truncated = " ".join(words[:max_words])
    # Find the last sentence-ending punctuation
    last_end = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    if last_end > max_words * 0.7:  # Only truncate at sentence if we keep 70%+
        return truncated[: last_end + 1]
    return truncated + "…"


# ════════════════════════════════════════════════════════════════════════════
# F4: Source Overlap Verification (stronger fact-check)
# ════════════════════════════════════════════════════════════════════════════


def compute_source_overlap(bullet: str, source_text: str) -> float:
    """V3.4.1 F4: Compute content word overlap between bullet and source.

    Stronger than fuzzy string matching — extracts content words (nouns, verbs,
    5+ char words) from the bullet and checks what % appear in the source.

    Returns 0.0 (no overlap = likely hallucination) to 1.0 (all words grounded).
    Below 0.40 = flag as "weakly grounded."
    """
    if not bullet or not source_text:
        return 0.0

    # Extract content words from bullet (5+ chars, not stopwords)
    bullet_words = set()
    for w in re.findall(r"\b[a-z]{5,}\b", bullet.lower()):
        if w not in _COMMON_500:
            bullet_words.add(w)

    if not bullet_words:
        return 1.0  # No content words to check — can't flag

    source_lower = source_text.lower()
    found = sum(1 for w in bullet_words if w in source_lower)
    return found / len(bullet_words)


# ════════════════════════════════════════════════════════════════════════════
# K1: Confidence Score Per Bullet
# ════════════════════════════════════════════════════════════════════════════


def compute_bullet_confidence(
    bullet: str, source_text: str, concepts: list[str] | None = None
) -> int:
    """V3.4.1 K1: Compute a confidence score (0-100) for a bullet.

    Criteria:
    - Source word overlap (F4): >40% = +30, >60% = +40, >80% = +50
    - Contains extracted concept: +20
    - No thinking markers: +10
    - Length 10-35 words: +10
    - Starts with capital, ends with punctuation: +5
    - No person names (NER): +5

    Returns 0-100. Below 40 = low confidence (may be hallucinated).
    """
    if not bullet:
        return 0

    score = 0
    bp_lower = bullet.lower()

    # 1. Source word overlap (up to 50 points)
    overlap = compute_source_overlap(bullet, source_text)
    if overlap > 0.80:
        score += 50
    elif overlap > 0.60:
        score += 40
    elif overlap > 0.40:
        score += 30
    elif overlap > 0.20:
        score += 15

    # 2. Contains concept (+20)
    if concepts:
        for c in concepts:
            if c.lower() in bp_lower:
                score += 20
                break

    # 3. No thinking markers (+10)
    if not re.search(r"<think|<thinking|Analyze|Process|Draft|I\'ll|I will", bullet, re.IGNORECASE):
        score += 10

    # 4. Length 10-35 words (+10)
    word_count = len(bullet.split())
    if 10 <= word_count <= 35:
        score += 10
    elif 5 <= word_count <= 45:
        score += 5

    # 5. Starts with capital, ends with punctuation (+5)
    if bullet and bullet[0].isupper() and bullet[-1] in ".!?":
        score += 5

    # 6. No person names (+5)
    try:
        ner_entities = get_all_ner_entities(source_text)
        if not any(entity.lower() in bp_lower for entity in ner_entities if len(entity) > 3):
            score += 5
    except Exception as _e:
        score += 5  # Can't check — give benefit of the doubt

    return min(score, 100)


# ════════════════════════════════════════════════════════════════════════════
# K2 + H2: Source Excerpt + Page-Level Traceability
# ════════════════════════════════════════════════════════════════════════════


def find_source_excerpt(bullet: str, source_text: str, max_length: int = 200) -> str | None:
    """V3.4.1 K2: Find the best-matching source sentence for a bullet.

    Splits source into sentences, finds the one with highest word overlap
    with the bullet. Returns the sentence (truncated to max_length) or None.

    Used for:
    - K2: Source excerpt injection (include as sub-bullet in DOCX)
    - H2: Source-bullet traceability (page-level citations)
    """
    if not bullet or not source_text:
        return None

    # Split source into sentences
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", source_text)
    if not sentences:
        return None

    # Extract content words from bullet
    bullet_words = {w.lower() for w in re.findall(r"\b[a-z]{4,}\b", bullet.lower())}
    if not bullet_words:
        return None

    best_sentence = None
    best_overlap = 0.0

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20:
            continue
        sent_words = {w.lower() for w in re.findall(r"\b[a-z]{4,}\b", sent.lower())}
        if not sent_words:
            continue
        overlap = len(bullet_words & sent_words) / len(bullet_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_sentence = sent

    if best_sentence and best_overlap > 0.20:
        # Truncate if needed
        if len(best_sentence) > max_length:
            # Find a good break point
            truncated = best_sentence[:max_length]
            last_space = truncated.rfind(" ")
            if last_space > max_length * 0.7:
                best_sentence = truncated[:last_space] + "…"
            else:
                best_sentence = truncated + "…"
        return best_sentence

    return None


def find_source_page(bullet: str, source_text: str, page_markers: list | None = None) -> int | None:
    """V3.4.1 H2: Find the page number for a bullet's source excerpt.

    Uses page markers (from extract_page_markers) to determine which page
    the best-matching source sentence appears on.

    Returns page number or None if not determinable.
    """
    if not page_markers:
        return None

    excerpt = find_source_excerpt(bullet, source_text)
    if not excerpt:
        return None

    # Find the excerpt in the source text
    excerpt_pos = source_text.find(excerpt[:50])  # Use first 50 chars for matching
    if excerpt_pos < 0:
        return None

    # Find which page this position falls in
    # page_markers is a list of (char_offset, page_num) tuples
    # Sort by char_offset
    sorted_markers = sorted(page_markers, key=lambda x: x[0])
    current_page = sorted_markers[0][1] if sorted_markers else None
    for char_offset, page_num in sorted_markers:
        if char_offset > excerpt_pos:
            break
        current_page = page_num

    return current_page


# ════════════════════════════════════════════════════════════════════════════
# F3: Reading Level Assessment (Flesch-Kincaid)
# ════════════════════════════════════════════════════════════════════════════


def count_syllables(word: str) -> int:
    """Estimate syllable count for a word."""
    word = word.lower().strip(".,!?;:\"'")
    if not word:
        return 0
    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for c in word:
        is_vowel = c in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    # Adjust for silent 'e'
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_kincaid_grade(text: str) -> float:
    """V3.4.2 F3: Compute Flesch-Kincaid grade level for a text.

    Formula: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59

    Returns grade level (e.g., 8.5 = 8th grade reading level).
    Lower = easier to read.
    """
    if not text or len(text) < 20:
        return 0.0

    # Count sentences
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sent_count = max(1, len(sentences))

    # Count words and syllables
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    word_count = max(1, len(words))
    syllable_count = sum(count_syllables(w) for w in words)

    # Flesch-Kincaid Grade Level
    grade = 0.39 * (word_count / sent_count) + 11.8 * (syllable_count / word_count) - 15.59
    return max(0.0, grade)


def assess_reading_level(source: str, summary: str) -> dict:
    """V3.4.2 F3: Compare reading levels of source and summary.

    Returns dict with grade levels and whether summary is simpler.
    The summary should be 2+ grade levels easier than the source.
    """
    source_grade = flesch_kincaid_grade(source)
    summary_grade = flesch_kincaid_grade(summary)

    return {
        "source_grade": round(source_grade, 1),
        "summary_grade": round(summary_grade, 1),
        "difference": round(source_grade - summary_grade, 1),
        "summary_is_simpler": summary_grade < source_grade,
        "meets_threshold": (source_grade - summary_grade) >= 2.0,
    }


# ════════════════════════════════════════════════════════════════════════════
# I2: Chapter Difficulty Scoring
# ════════════════════════════════════════════════════════════════════════════


def score_chapter_difficulty(text: str) -> dict:
    """V3.4.2 I2: Score chapter difficulty for adaptive summarization strategy.

    Metrics:
    - Vocabulary diversity (unique words / total words)
    - Average sentence length
    - Technical term density (% of 12+ char words)
    - Named entity density
    - Reading grade level

    Returns dict with score 0.0 (easy) to 1.0 (very hard) and recommendations.
    """
    if not text or len(text) < 100:
        return {"score": 0.0, "strategy": "single_pass"}

    words = re.findall(r"\b[a-zA-Z]+\b", text)
    word_count = max(1, len(words))
    unique_words = len({w.lower() for w in words})

    # 1. Vocabulary diversity (0-1)
    vocab_diversity = unique_words / word_count

    # 2. Average sentence length
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sent_count = max(1, len(sentences))
    avg_sent_len = word_count / sent_count

    # 3. Technical term density (% of 12+ char words)
    long_words = sum(1 for w in words if len(w) >= 12)
    tech_density = long_words / word_count

    # 4. Named entity density
    try:
        ner_entities = get_all_ner_entities(text)
        ner_density = len(ner_entities) / max(1, word_count / 100)
    except Exception as _e:
        ner_density = 0.0

    # 5. Reading grade level
    grade_level = flesch_kincaid_grade(text)

    # Overall difficulty score (0.0 = easy, 1.0 = very hard)
    score = min(
        1.0,
        (
            vocab_diversity * 0.2
            + min(1.0, avg_sent_len / 30.0) * 0.2
            + min(1.0, tech_density / 0.10) * 0.25
            + min(1.0, ner_density / 5.0) * 0.15
            + min(1.0, grade_level / 16.0) * 0.20
        ),
    )

    # Strategy recommendation
    if score > 0.6:
        strategy = "section_map_reduce"  # B4: split into sections
    elif score > 0.4:
        strategy = "multi_sample"  # B3: multi-sample voting
    else:
        strategy = "single_pass"  # Standard single-pass

    return {
        "score": round(score, 2),
        "vocab_diversity": round(vocab_diversity, 2),
        "avg_sentence_length": round(avg_sent_len, 1),
        "tech_density": round(tech_density, 3),
        "ner_density": round(ner_density, 2),
        "grade_level": round(grade_level, 1),
        "strategy": strategy,
    }


# ════════════════════════════════════════════════════════════════════════════
# J2: Cross-Section Redundancy Check
# ════════════════════════════════════════════════════════════════════════════


def check_cross_section_redundancy(
    exec_summary: str, bullets: list[str], thorough_summary: str
) -> dict:
    """V3.4.2 J2: Check for redundant content between summary sections.

    Checks if the same information appears in multiple sections (exec + bullets,
    bullets + thorough, exec + thorough). Uses word overlap to detect semantic
    similarity.

    Returns dict with redundancy findings.
    """
    try:
        from rapidfuzz import fuzz

        _has_rf = True
    except ImportError:
        _has_rf = False

    findings = {
        "exec_vs_bullets_redundant": [],
        "bullets_vs_thorough_redundant": [],
        "exec_vs_thorough_redundant": [],
        "total_redundant": 0,
    }

    bullets_text = " ".join(bullets)

    # Check exec vs bullets
    if exec_summary and bullets_text and _has_rf:
        for i, bp in enumerate(bullets):
            sim = fuzz.token_set_ratio(exec_summary.lower(), bp.lower())
            if sim > 75:
                findings["exec_vs_bullets_redundant"].append(
                    {
                        "bullet_index": i,
                        "similarity": sim,
                        "bullet_preview": bp[:60],
                    }
                )

    # Check bullets vs thorough (expected — bullets SHOULD be in thorough)
    # Only flag if >90% (near-duplicate)
    if bullets_text and thorough_summary and _has_rf:
        for i, bp in enumerate(bullets):
            sim = fuzz.token_set_ratio(thorough_summary.lower(), bp.lower())
            if sim > 90:
                findings["bullets_vs_thorough_redundant"].append(
                    {
                        "bullet_index": i,
                        "similarity": sim,
                        "bullet_preview": bp[:60],
                    }
                )

    # Check exec vs thorough (flag if >80% — exec should be a summary, not a copy)
    if exec_summary and thorough_summary and _has_rf:
        sim = fuzz.token_set_ratio(exec_summary.lower(), thorough_summary.lower())
        if sim > 80:
            findings["exec_vs_thorough_redundant"].append(
                {
                    "similarity": sim,
                }
            )

    findings["total_redundant"] = (
        len(findings["exec_vs_bullets_redundant"])
        + len(findings["bullets_vs_thorough_redundant"])
        + len(findings["exec_vs_thorough_redundant"])
    )

    return findings


# ════════════════════════════════════════════════════════════════════════════
# J3: Executive Summary Coherence Check
# ════════════════════════════════════════════════════════════════════════════

# Discourse markers indicating coherent narrative flow
_DISCOURSE_MARKERS = re.compile(
    r"\b(?:however|therefore|additionally|furthermore|moreover|consequently|"
    r"as a result|in addition|similarly|in contrast|on the other hand|"
    r"for example|specifically|notably|ultimately|finally|in summary|"
    r"the chapter|the author|this approach|this method|this concept|"
    r"the core|the central|the main|the key|the primary)\b",
    re.IGNORECASE,
)


def check_exec_summary_coherence(exec_summary: str) -> dict:
    """V3.4.2 J3: Check executive summary coherence.

    A coherent executive summary should:
    - Contain discourse markers (transition words)
    - Start with a topic sentence
    - End with a conclusion
    - Be a narrative (not a list)

    Returns dict with coherence score and findings.
    """
    if not exec_summary or len(exec_summary) < 50:
        return {"coherent": False, "score": 0, "reason": "too short"}

    markers_found = _DISCOURSE_MARKERS.findall(exec_summary)
    marker_count = len(markers_found)

    # Check for topic sentence (first sentence is a complete statement)
    sentences = re.split(r"(?<=[.!?])\s+", exec_summary.strip())
    has_topic = len(sentences) > 0 and len(sentences[0]) > 30

    # Check for conclusion (last sentence ends with a period and is >20 chars)
    has_conclusion = len(sentences) > 1 and len(sentences[-1]) > 20

    # Check it's a narrative (not a list — no bullet markers)
    is_narrative = not bool(re.search(r"^[\-\*]\s", exec_summary, re.MULTILINE))

    # Score: 0-100
    score = 0
    if marker_count >= 2:
        score += 30
    elif marker_count >= 1:
        score += 15
    if has_topic:
        score += 25
    if has_conclusion:
        score += 25
    if is_narrative:
        score += 20

    return {
        "coherent": score >= 60,
        "score": score,
        "discourse_markers": marker_count,
        "markers_found": [m.lower() for m in markers_found[:5]],
        "has_topic_sentence": has_topic,
        "has_conclusion": has_conclusion,
        "is_narrative": is_narrative,
    }


# ════════════════════════════════════════════════════════════════════════════
# V3.6.0: Bullet Classification (Core / Supporting / Additional)
# ════════════════════════════════════════════════════════════════════════════

# Core concept indicators — bullets that define or explain a key concept
_CORE_INDICATORS = re.compile(
    r"(?:is defined as|refers to|means|involves|requires|consists of|"
    r"the concept of|the principle of|the technique of|the strategy of|"
    r"the method of|the framework of|the foundation of|"
    r"should|must|need to|essential to|crucial to|important to|"
    r"Establish|Create|Develop|Define|Identify|Leverage|Apply|"
    r"Use|Practice|Maintain|Avoid|Adapt|Assess|Conduct|"
    r"Limit|Diversify|Integrate|Prepare|Watch|Recognize|"
    r"Observe|Target|Pursue|Invest|Engage)",
    re.IGNORECASE,
)

# Supporting detail indicators — bullets with specific examples, numbers, or cases
_SUPPORTING_INDICATORS = re.compile(
    r"(?:e\.g\.|for example|such as|including|specifically|"
    r"\$\d|\d+%|\d{4}|\d{2,},\d{3}|"  # numbers, money, percentages, years
    r"case study|story|anecdote|instance|illustration|"
    # V18.20.3.9 (Phase 2 / residuals sweep): was a three-name character
    # alternation harvested from one book. Structural replacement:
    # scene-action fragments (the character-reference signal, any book).
    r"\bwent\s+to\s+(?:a|the)|\bmet\s+(?:a|the|his|her)|author|chapter|book)",
    re.IGNORECASE,
)


def classify_bullet(bullet: str, concepts: list[str] | None = None, source_text: str = "") -> str:
    """V3.6.0: Classify a bullet as Core Concept, Supporting Detail, or Additional Insight.

    Classification rules:
    - Core Concept: Contains an extracted concept keyword AND has core indicators
      (action verbs, definitions, principles). These are the must-know takeaways.
    - Supporting Detail: Contains specific examples, numbers, case studies, or
      character references. These illustrate concepts but aren't concepts themselves.
    - Additional Insight: Everything else — useful but not essential.

    Returns one of: "core", "supporting", "additional"
    """
    if not bullet:
        return "additional"

    bp_lower = bullet.lower()

    # Check if bullet contains an extracted concept
    has_concept = False
    if concepts:
        for c in concepts:
            if c.lower() in bp_lower:
                has_concept = True
                break

    # Check for core indicators
    has_core = bool(_CORE_INDICATORS.search(bullet))

    # Check for supporting indicators
    has_supporting = bool(_SUPPORTING_INDICATORS.search(bullet))

    # Classification logic
    if has_concept and has_core or has_core and not has_supporting:
        return "core"
    elif has_supporting:
        return "supporting"
    elif has_concept:
        return "core"  # Contains a concept even without core indicators
    else:
        return "additional"


# ════════════════════════════════════════════════════════════════════════════
# V3.7.0 Phase 2.2: Semantic Fact-Check with sentence-transformers
# ════════════════════════════════════════════════════════════════════════════

# V18.2.14 (M6): Removed dead ``_EMBED_MODEL = None`` module-level cache.
# It was superseded by the shared singleton in ``core.llm.model_singletons``
# (V10.31.0) but the var + its shim were never deleted. ``_get_embed_model()``
# below delegates entirely to ``get_embed_model()`` — the local cache was
# never read after the singleton migration, so removing it is safe. The
# ``_warned_no_embed_model`` flag is retained (it gates the one-time
# fail-closed WARNING).

# V18.1 (S1): one-time warning flag — fail-closed when embed model is
# unavailable so bullets don't silently pass the hallucination check.
# V18.20.1.0 (D3): centralized to _runtime_state.state.warned_no_embed_model.
_warned_no_embed_model = False  # backward-compat proxy (impl uses _runtime_state)


def _get_embed_model():
    """Get cached sentence-transformers model.

    V10.31.0 (Sprint 4.6): delegates to the shared singleton in
    ``core.llm.model_singletons`` so all callers share one model instance.
    """
    try:
        from core.llm.model_singletons import get_embed_model

        return get_embed_model()
    except Exception as _e:
        return None


def semantic_fact_check(bullet: str, source_text: str, threshold: float = 0.5) -> dict:
    """V3.7.0 Phase 2.2: Semantic fact-check using embedding similarity.

    Computes embeddings for the bullet and all source sentences, finds the
    best-matching source sentence. If max similarity < threshold, the bullet
    is flagged as a potential hallucination.

    This is MUCH stronger than string-matching fact-check:
    - a faithful paraphrase of the source → ~0.92 similarity with source
    - a plausible-sounding but unsupported variant → ~0.65 similarity (flagged)
    String matching can't distinguish these — embeddings can.

    Returns dict with:
    - is_grounded: True if best similarity >= threshold
    - best_similarity: float 0-1
    - best_source_sentence: the most similar source sentence
    - reason: optional failure reason when is_grounded is False due to a
      non-similarity cause (e.g. embed model unavailable).
    """
    # V18.20.1.0 (D3): read/write the centralized state object directly.
    embed_model = _get_embed_model()
    if not embed_model:
        # V18.1 (S1): fail-CLOSED when the embed model is unavailable
        # (e.g. no internet on first launch, model download failed).
        # Returning is_grounded=True would silently pass every bullet
        # through the hallucination check — a security hole. Instead
        # we conservatively flag the bullet so it goes through the
        # quarantine/recovery path.
        if not _runtime_state.warned_no_embed_model:
            logger.warning(
                "semantic_fact_check: embed model unavailable — failing "
                "CLOSED (bullets will be flagged, not auto-passed). "
                "Subsequent occurrences suppressed."
            )
            _runtime_state.warned_no_embed_model = True
        return {
            "is_grounded": False,
            "best_similarity": 0.0,
            "best_source_sentence": "",
            "reason": "embed_model_unavailable",
        }
    if not bullet or not source_text:
        # Degenerate input — fail-closed (no source to ground against).
        return {
            "is_grounded": False,
            "best_similarity": 0.0,
            "best_source_sentence": "",
            "reason": "empty_input",
        }

    try:
        import re

        # Split source into sentences
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", source_text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]

        if not sentences:
            # No usable sentences — fail-closed.
            return {
                "is_grounded": False,
                "best_similarity": 0.0,
                "best_source_sentence": "",
                "reason": "no_source_sentences",
            }

        # Compute embeddings
        bullet_emb = embed_model.encode([bullet], convert_to_numpy=True)
        source_embs = embed_model.encode(sentences, convert_to_numpy=True)

        # Compute cosine similarities
        import numpy as np

        bullet_norm = bullet_emb / (np.linalg.norm(bullet_emb, axis=1, keepdims=True) + 1e-8)
        source_norms = source_embs / (np.linalg.norm(source_embs, axis=1, keepdims=True) + 1e-8)
        similarities = np.dot(source_norms, bullet_norm[0])

        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        best_sentence = sentences[best_idx]

        return {
            "is_grounded": best_sim >= threshold,
            "best_similarity": round(best_sim, 3),
            "best_source_sentence": best_sentence[:200],
        }
    except Exception as e:
        # V18.1 (S1): fail-closed on unexpected errors too — never silently
        # pass a bullet that we couldn't actually verify.
        logger.warning("semantic_fact_check: embedding failure (%s) — failing CLOSED", e)
        return {
            "is_grounded": False,
            "best_similarity": 0.0,
            "best_source_sentence": "",
            "reason": "embedding_error",
            "error": str(e),
        }


# ════════════════════════════════════════════════════════════════════════════
# V3.7.0 Phase 2.3: Academic Concept Expansion
# ════════════════════════════════════════════════════════════════════════════

# Academic terminology patterns (beyond the existing quoted-term patterns)
_ACADEMIC_TERM_PATTERNS = [
    # "Term (definition)" — common in academic writing
    re.compile(r"\b([a-z]{4,}(?:\s+[a-z]{4,}){0,2})\s+\(([^)]{10,100})\)", re.IGNORECASE),
    # "Term: definition" — glossary style
    re.compile(r"^([A-Z][a-z]+(?:\s+[a-z]+){0,2}):\s+(.{10,100})", re.MULTILINE),
    # "Term is/are defined as" — explicit definition
    re.compile(
        r"([a-z]{4,}(?:\s+[a-z]{4,}){0,2})\s+(?:is|are)\s+(?:defined\s+as|called|known\s+as)\s+(.{10,100})",
        re.IGNORECASE,
    ),
    # Italicized terms (markdown) — *term* or _term_
    re.compile(r"\*([a-z]{4,}(?:\s+[a-z]{4,}){0,2})\*"),
    re.compile(r"_([a-z]{4,}(?:\s+[a-z]{4,}){0,2})_"),
]

# Domain-specific term lists for common academic fields
# V3.9.2: Changed from .split() to line-based parsing. The old .split() broke
# multi-word phrases like "brand positioning" into single words "brand" and
# "positioning", which then matched as single-word concepts ("Brand", "Target",
# "Market", "Customer", etc.). Now each LINE is a complete phrase.
_DOMAIN_TERMS = {
    "psychology": [
        "cognitive behavioral therapy",
        "mindfulness",
        "neuroplasticity",
        "conditioning",
        "reinforcement",
        "extroversion",
        "introversion",
        "personality trait",
        "attachment theory",
        "self-actualization",
        "hierarchy of needs",
        "intrinsic motivation",
        "extrinsic motivation",
        "learned helplessness",
        "confirmation bias",
        "cognitive dissonance",
        "heuristics",
        "availability heuristic",
        "stereotyping",
        "prejudice",
        "implicit bias",
        "emotional intelligence",
        "grit",
        "growth mindset",
    ],
    "philosophy": [
        "stoicism",
        "virtue ethics",
        "deontology",
        "utilitarianism",
        "consequentialism",
        "nihilism",
        "existentialism",
        "phenomenology",
        "epistemology",
        "metaphysics",
        "determinism",
        "free will",
        "moral relativism",
        "categorical imperative",
        "social contract",
        "tabula rasa",
        "dialectic",
        "syllogism",
        "a priori",
        "a posteriori",
        "noumenon",
        "phenomenon",
    ],
    "marketing": [
        "brand positioning",
        "value proposition",
        "customer segmentation",
        "target market",
        "competitive advantage",
        "unique selling proposition",
        "market penetration",
        "brand equity",
        "customer lifetime value",
        "conversion funnel",
        "A/B testing",
        "content marketing",
        "inbound marketing",
        "outbound marketing",
        "SEO",
        "SEM",
    ],
    "urban_planning": [
        "gentrification",
        "spatial segregation",
        "urban morphology",
        "zoning",
        "land use",
        "transit-oriented development",
        "smart growth",
        "urban sprawl",
        "density",
        "mixed-use development",
        "pedestrian-friendly",
        "sustainable urbanism",
        "brownfield redevelopment",
        "green infrastructure",
        "public realm",
    ],
    "management": [
        "agile",
        "lean",
        "six sigma",
        "kanban",
        "scrum",
        "stakeholder management",
        "strategic planning",
        "key performance indicators",
        "balanced scorecard",
        "organizational behavior",
        "transformational leadership",
        "servant leadership",
        "change management",
    ],
}


def extract_academic_terms(text: str, max_terms: int = 20) -> list[str]:
    """V3.7.0 Phase 2.3: Extract academic terminology from text.

    V3.9.2: Added _is_valid_concept() check to reject single words.
    Previously, domain terms like "customer", "target", "market" leaked
    through as single-word concepts because .split() broke multi-word
    phrases. Now each domain term is a complete phrase, and all terms
    must pass _is_valid_concept() (2+ words or all-caps acronym).

    Goes beyond quoted terms — catches:
    - Term (definition) patterns
    - Term: definition patterns
    - Italicized terms
    - Domain-specific terminology from built-in dictionaries

    Returns a list of academic terms found in the text.
    """
    found = set()

    # Pattern-based extraction
    for pattern in _ACADEMIC_TERM_PATTERNS:
        for m in pattern.finditer(text):
            term = m.group(1).strip().lower()
            # V3.9.2: Use _is_valid_concept() instead of just length check
            if _is_valid_concept(term) and term not in _CONCEPT_STOPWORDS:
                found.add(term.title())

    # Domain-specific term matching — V3.9.2: phrases, not split words
    text_lower = text.lower()
    for domain_terms in _DOMAIN_TERMS.values():
        for term in domain_terms:
            # V3.9.2: Only accept multi-word phrases or all-caps acronyms.
            # Single words from domain lists (e.g., "agile", "grit") are too
            # generic to be useful concepts — they match as false positives.
            words = term.split()
            if len(words) < 2 and not (term.isupper() and len(term) >= 3):
                continue
            if term.lower() in text_lower:
                found.add(term.title())

    # Filter: must appear 2+ times (frequency filter)
    filtered = []
    for term in found:
        if text_lower.count(term.lower()) >= 2:
            filtered.append(term)

    return filtered[:max_terms]


def _extract_proper_noun_theorists(text: str, max_terms: int = 15) -> list[str]:
    """V15.2.0 Technique #2: Extract proper-noun theorist names.

        Detects the "Surname (year)" citation pattern that academic authors use.
    This is the PRIMARY signal for theorist names — any cited
    author appears as "Surname (year)" in the source text.

    Also catches hyphenated names like "AuthorA-AuthorB".
    """
    import re as _re

    # Pattern: Capitalized surname (optionally hyphenated) + (year)
    # e.g., "AuthorA (1919)", "AuthorB (1958a,b)", "AuthorC-D (1983, 1984)"
    citation_pattern = _re.compile(
        r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\s*\((\d{4}[a-z]?(?:,\s*\d{4}[a-z]?)*)\)"
    )
    seen = {}
    for m in citation_pattern.finditer(text):
        name = m.group(1).strip()
        # Filter out common false positives
        _STOP = {
            "Chapter",
            "Figure",
            "Table",
            "Section",
            "Part",
            "Volume",
            "Appendix",
            "Note",
            "See",
            "Cf",
            "Op",
            "Loc",
            "Passim",
        }
        if name in _STOP or len(name) < 3:
            continue
        # Count occurrences to rank by frequency
        seen[name] = seen.get(name, 0) + 1
    # Sort by frequency (most-cited theorists first)
    ranked = sorted(seen, key=lambda n: seen[n], reverse=True)
    return ranked[:max_terms]


def _normalize_heading(h: str) -> str:
    """V16.0.4: Collapse newlines + multiple spaces into single spaces."""
    import re as _re

    return _re.sub(r"\s+", " ", h).strip()


def _extract_section_headings(text: str, max_terms: int = 12) -> list[str]:
    """V15.2.0 Technique #3: Extract section headings.

    Parses the chapter's own markdown headings (## ..., ### ...) and
    all-caps section markers (THE CONCEPT OF IDENTITY). The author
    literally tells us what each section is about — we should listen.

    Also detects bold terms (**Term**) used as subsection markers.
    """
    import re as _re

    headings = []
    seen = set()

    # Markdown headings: ## Heading, ### Heading
    for m in _re.finditer(r"^#{2,4}\s+(.+?)$", text, _re.MULTILINE):
        h = m.group(1).strip()
        # Skip if too long (probably a sentence, not a heading) or too short
        if 3 <= len(h) <= 80 and h.lower() not in seen:
            seen.add(h.lower())
            headings.append(h)

    # ALL-CAPS section markers (common in academic books): THE CONCEPT OF IDENTITY
    # V15.2.0: Keep original case for proper nouns, title-case for ALL-CAPS phrases
    for m in _re.finditer(r"^\s*([A-Z][A-Z\s]{4,60})\s*$", text, _re.MULTILINE):
        raw = m.group(1).strip()
        # If it's all caps, title-case it; otherwise keep as-is
        h = raw.title() if raw.isupper() else raw
        if h.lower() not in seen and 5 <= len(h) <= 80:
            seen.add(h.lower())
            headings.append(h)

    # Bold terms: **Term** or __Term__
    for m in _re.finditer(r"\*\*([A-Z][A-Za-z\s-]{3,60})\*\*", text):
        h = m.group(1).strip()
        if h.lower() not in seen and 5 <= len(h) <= 60:
            seen.add(h.lower())
            headings.append(h)

    return headings[:max_terms]


def _extract_conclusion_lists(text: str, max_terms: int = 10) -> list[str]:
    """V15.2.0 Technique #4: Detect numbered lists in the conclusion.

    The chapter's conclusion often has a formal list like:
        (1) a sustained feeling of selfsameness
        (2) temporal continuity in the self-experience
        (3) genuineness and authenticity
        ...

    This extracts each list item as a concept — these are the author's
    own summary of the key points.
    """
    import re as _re

    # V15.2.0: Find the conclusion section. Try explicit markers first
    # (## CONCLUSION, CONCLUSION, # CONCLUSION), then fall back to last 20%.
    conclusion_start = len(text)  # default: no conclusion section found
    for marker in [r"^##\s*CONCLUSION\s*$", r"^CONCLUSION\s*$", r"^#\s*CONCLUSION\s*$"]:
        m = _re.search(marker, text, _re.MULTILINE | _re.IGNORECASE)
        if m:
            conclusion_start = m.start()
            break
    if conclusion_start == len(text):
        # No explicit marker — use last 20%
        conclusion_start = int(len(text) * 0.80)
    conclusion_text = text[conclusion_start:]

    # Pattern: (N) item text — capture up to the next (N) or end of line.
    # V15.2.0 fix: use a non-greedy match that stops at the next numbered
    # item or a double-newline, so multi-item lists on one line work too.
    list_pattern = _re.compile(r"\((\d{1,2})\)\s+([^()\n]{5,150}?)(?=\s*\(\d{1,2}\)|\n\n|$)")
    items = []
    seen = set()
    for m in list_pattern.finditer(conclusion_text):
        item = m.group(2).strip().rstrip(",;")
        key = item.lower()
        # Filter generic phrases
        if key in seen or len(item) < 5:
            continue
        seen.add(key)
        items.append(item)
    return items[:max_terms]


def _extract_position_weighted_concepts(text: str, max_terms: int = 12) -> list[str]:
    """V15.2.0 Technique #1: Intro + Conclusion position-weighted extraction.

    Extracts Title Case phrases from the first 15% (intro) and last 15%
    (conclusion) of the chapter with 3x weight. Authors state their thesis
    in the intro and their conclusions in the conclusion — these positions
    are far more reliable for concept extraction than the body.

    This catches concepts that frequency-based methods miss because the
    concept appears only in the intro/conclusion (not repeated throughout).
    """
    from collections import Counter

    intro_end = int(len(text) * 0.15)
    concl_start = int(len(text) * 0.85)
    intro = text[:intro_end]
    conclusion = text[concl_start:]

    # Title Case phrase pattern (2-4 words)
    title_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

    _STOP = frozenset(
        [
            "The",
            "This",
            "That",
            "These",
            "Those",
            "There",
            "Here",
            "Now",
            "Then",
            "Will",
            "Would",
            "Could",
            "Should",
            "May",
            "Might",
            "Can",
            "Must",
            "Shall",
            "And",
            "Or",
            "But",
            "If",
            "When",
            "Where",
            "Why",
            "How",
            "What",
            "Which",
            "Who",
            "Of",
            "In",
            "On",
            "At",
            "For",
            "With",
            "By",
            "From",
            "To",
            "A",
            "An",
            "Is",
            "Are",
            "Was",
            "Were",
            "Be",
            "Been",
            "Being",
            "Have",
            "Has",
            "Had",
            "Do",
            "Does",
            "Did",
            "Not",
            "No",
            "Only",
            "Own",
            "Same",
            "So",
            "Than",
            "Too",
            "Very",
            "Just",
            "Also",
            "About",
            "Above",
            "Below",
            "Up",
            "Down",
            "Out",
            "Off",
            "Over",
            "Under",
            "Again",
            "Further",
            "Once",
            "Chapter",
            "Part",
            "Section",
            "Book",
            "Author",
            "Note",
        ]
    )

    counts = Counter()

    # V16.0.3: Expanded stopword list + sentence-boundary detection + frequency filter
    _STOP = frozenset(
        [
            "The",
            "This",
            "That",
            "These",
            "Those",
            "There",
            "Here",
            "Now",
            "Then",
            "Will",
            "Would",
            "Could",
            "Should",
            "May",
            "Might",
            "Can",
            "Must",
            "Shall",
            "And",
            "Or",
            "But",
            "If",
            "When",
            "Where",
            "Why",
            "How",
            "What",
            "Which",
            "Who",
            "Of",
            "In",
            "On",
            "At",
            "For",
            "With",
            "By",
            "From",
            "To",
            "A",
            "An",
            "Is",
            "Are",
            "Was",
            "Were",
            "Be",
            "Been",
            "Being",
            "Have",
            "Has",
            "Had",
            "Do",
            "Does",
            "Did",
            "Not",
            "No",
            "Only",
            "Own",
            "Same",
            "So",
            "Than",
            "Too",
            "Very",
            "Just",
            "Also",
            "About",
            "Above",
            "Below",
            "Up",
            "Down",
            "Out",
            "Off",
            "Over",
            "Under",
            "Again",
            "Further",
            "Once",
            "Chapter",
            "Part",
            "Section",
            "Book",
            "Author",
            "Note",
            "Although",
            "Despite",
            "Because",
            "Since",
            "While",
            "During",
            "Throughout",
            "Without",
            "However",
            "Moreover",
            "Furthermore",
            "Nevertheless",
            "Nonetheless",
            "Therefore",
            "Thus",
            "Hence",
            "Accordingly",
            "Consequently",
            "Similarly",
            "Likewise",
            "Instead",
            "Rather",
            "Building",
            "Following",
            "Later",
            "Earlier",
            "Around",
            "Between",
            "Among",
            "Across",
            "Within",
            "Toward",
            "Towards",
            "Dovetailing",
        ]
    )

    _SENTENCE_BOUNDARY = re.compile(r"\.\s+[A-Z]")

    def _is_clean_phrase(phrase: str) -> bool:
        if len(phrase) < 5 or len(phrase) > 50:
            return False
        if "\n" in phrase:
            return False
        if _SENTENCE_BOUNDARY.search(phrase):
            return False
        words = phrase.split()
        if len(words) < 2:
            return False
        if words[0] in _STOP or words[-1] in _STOP:
            return False
        if all(w in _STOP for w in words):
            return False
        # V16.0.3: Frequency check — ≥2 in full text OR ≥1 in intro/conclusion
        _phrase_lower = phrase.lower()
        if text.lower().count(_phrase_lower) >= 2:
            return True
        if intro.lower().count(_phrase_lower) >= 1 or conclusion.lower().count(_phrase_lower) >= 1:
            return True
        return False

    counts = Counter()

    for phrase_match in title_pattern.finditer(intro):
        phrase = phrase_match.group(1).strip()
        if not _is_clean_phrase(phrase):
            continue
        counts[phrase] += 3

    for phrase_match in title_pattern.finditer(conclusion):
        phrase = phrase_match.group(1).strip()
        if not _is_clean_phrase(phrase):
            continue
        counts[phrase] += 3

    # Sort by weighted frequency
    ranked = sorted(counts, key=lambda p: counts[p], reverse=True)
    return ranked[:max_terms]


def _llm_assisted_concept_extraction(text: str, llm_call_fn, log_fn=None) -> list[str]:
    """V15.2.0 Technique #5: LLM-assisted concept extraction.

        Asks the LLM to list the key concepts and theorists in the chapter.
        The LLM understands semantics — it catches concepts that don't appear
    as literal words (e.g., a multi-word concept vs. its single-word
        + "diffusion" as separate words).

        Args:
            text: The chapter source text (will be truncated to ~8000 chars).
            llm_call_fn: A callable(prompt) -> Optional[str] that invokes the LLM.
            log_fn: Optional log callback for progress messages.

        Returns:
            List of concept strings (may be empty if the LLM call fails).
    """
    if llm_call_fn is None:
        return []

    # Truncate to fit context window (leave room for the prompt)
    truncated = text[:8000]
    from core.summarisation.prompt_manager import PromptManager

    _pm = PromptManager()
    prompt = _pm.render_template(
        "summarisation/concept_extraction",
        truncated=truncated,
    )

    try:
        if log_fn:
            log_fn("    🎯 V15.2.0 #5: LLM-assisted concept extraction starting...", "DEBUG")
        raw = llm_call_fn(prompt)
        if not raw or len(raw.strip()) < 20:
            if log_fn:
                log_fn("    ⚠️ V15.2.0 #5: LLM returned empty/short response", "DEBUG")
            return []
        # Parse bullet lines: "- Concept Name" or "* Concept Name" or "1. Concept Name"
        import re as _re

        lines = _re.findall(r"(?:^|\n)\s*[-*\d.]\s*(.+?)(?=\n|$)", raw)
        concepts = []
        seen = set()
        for line in lines:
            c = line.strip().rstrip(".").strip()
            # Filter generic/empty
            if len(c) < 3 or len(c) > 100:
                continue
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            concepts.append(c)
        if log_fn:
            log_fn(f"    ✅ V15.2.0 #5: LLM extracted {len(concepts)} concepts", "DEBUG")
        return concepts
    except Exception as e:
        if log_fn:
            log_fn(f"    ⚠️ V15.2.0 #5: LLM concept extraction failed: {e}", "DEBUG")
        return []


def _filter_concepts_by_source(
    concepts: list[str], source_text: str, min_overlap_chars: int = 15
) -> list[str]:
    """V15.2.0 Technique #6: Source-grounded concept filter.

    Drops concepts that have NO source sentence containing them. This
    prevents gap-fill from chasing ghost concepts that don't exist in
    the text (the V15.1.1 bug where 8 concepts had no source sentences).

    A concept "passes" if at least one substring of min_overlap_chars
    appears in the source text. This handles multi-word concepts where
    the full phrase might not appear verbatim but a key fragment does.
    """
    source_lower = source_text.lower()
    passed = []
    dropped = []
    for concept in concepts:
        c = concept.lower().strip()
        # Full phrase match?
        if c in source_lower:
            passed.append(concept)
            continue
        # Try key fragments (first 3+ words or the longest word)
        words = c.split()
        if len(words) >= 2:
            # Try the first 2-3 words as a fragment
            fragment = " ".join(words[: min(3, len(words))])
            if len(fragment) >= min_overlap_chars and fragment in source_lower:
                passed.append(concept)
                continue
        # Try the longest single word (for hyphenated theorist names)
        longest = max(words, key=len) if words else c
        if len(longest) >= 6 and longest in source_lower:
            passed.append(concept)
            continue
        dropped.append(concept)
    return passed, dropped


def extract_concepts_rich(
    text: str, max_terms: int = 18, llm_call_fn=None, log_fn=None
) -> list[str]:
    """V15.2.0: Enhanced concept extraction — the foundation fix.

    Combines 6 techniques (the user's "خشت اول" / foundation-first principle):

    #1: Intro + Conclusion position-weighted extraction (3x weight)
    #2: Proper-noun theorist extraction (Surname + year citations)
    #3: Section-heading extraction (## headings + ALL-CAPS markers)
    #4: Conclusion-list detection (numbered (1)(2)(3) lists)
    #5: LLM-assisted concept extraction (semantic understanding)
    #6: Source-grounded concept filter (drop ghost concepts)

    Each technique logs its contribution so we can audit which one
    succeeded/failed in the conversion log.

    Args:
        text: The chapter source text.
        max_terms: Maximum concepts to return (default 18, raised from 10).
        llm_call_fn: Optional callable(prompt) -> str for Technique #5.
        log_fn: Optional log callback(msg, level) for progress logging.

    Returns:
        Deduplicated, source-grounded list of concept strings.
    """
    if log_fn is None:

        def _noop_log(msg: str, level: str = "DEBUG") -> None:
            pass

        log_fn = _noop_log

    log_fn("    🎯 V15.2.0: Enhanced concept extraction starting (6 techniques)", "INFO")

    # ── Technique #1: Position-weighted (intro + conclusion) ──
    try:
        t1 = _extract_position_weighted_concepts(text, max_terms=12)
        log_fn(f"    🎯 V15.2.0 #1 (intro+conclusion): {len(t1)} concepts — {t1[:5]}", "DEBUG")
    except Exception as e:
        log_fn(f"    ⚠️ V15.2.0 #1 failed: {e}", "DEBUG")
        t1 = []

    # ── Technique #2: Proper-noun theorists ──
    try:
        t2 = _extract_proper_noun_theorists(text, max_terms=15)
        log_fn(f"    🎯 V15.2.0 #2 (proper-noun theorists): {len(t2)} concepts — {t2[:5]}", "DEBUG")
    except Exception as e:
        log_fn(f"    ⚠️ V15.2.0 #2 failed: {e}", "DEBUG")
        t2 = []

    # ── Technique #3: Section headings ──
    try:
        t3 = _extract_section_headings(text, max_terms=12)
        log_fn(f"    🎯 V15.2.0 #3 (section headings): {len(t3)} concepts — {t3[:5]}", "DEBUG")
    except Exception as e:
        log_fn(f"    ⚠️ V15.2.0 #3 failed: {e}", "DEBUG")
        t3 = []

    # ── Technique #4: Conclusion lists ──
    try:
        t4 = _extract_conclusion_lists(text, max_terms=10)
        log_fn(f"    🎯 V15.2.0 #4 (conclusion lists): {len(t4)} concepts — {t4[:5]}", "DEBUG")
    except Exception as e:
        log_fn(f"    ⚠️ V15.2.0 #4 failed: {e}", "DEBUG")
        t4 = []

    # ── Technique #5: LLM-assisted (optional — needs llm_call_fn) ──
    t5 = []
    if llm_call_fn is not None:
        try:
            t5 = _llm_assisted_concept_extraction(text, llm_call_fn, log_fn)
            log_fn(f"    🎯 V15.2.0 #5 (LLM-assisted): {len(t5)} concepts — {t5[:5]}", "DEBUG")
        except Exception as e:
            log_fn(f"    ⚠️ V15.2.0 #5 failed: {e}", "DEBUG")
            t5 = []
    else:
        log_fn("    ℹ️ V15.2.0 #5 (LLM-assisted): skipped (no llm_call_fn provided)", "DEBUG")

    # ── Merge all sources (deduplicate, case-insensitive) ──
    seen = set()
    merged = []
    # Order: theorists (#2) first (most important for fact-check), then LLM (#5),
    # then headings (#3), conclusion lists (#4), position-weighted (#1)
    for term in t2 + t5 + t3 + t4 + t1:
        key = term.lower().strip()
        if key in seen or len(key) < 3:
            continue
        seen.add(key)
        merged.append(term)

    log_fn(f"    🎯 V15.2.0: merged {len(merged)} concepts before source-grounding", "DEBUG")

    # ── Technique #6: Source-grounded filter (drop ghost concepts) ──
    try:
        grounded, dropped = _filter_concepts_by_source(merged, text)
        if dropped:
            log_fn(
                f"    🎯 V15.2.0 #6 (source-grounded): kept {len(grounded)}, dropped {len(dropped)} ghost concepts — dropped: {dropped[:5]}",
                "DEBUG",
            )
        else:
            log_fn(
                f"    🎯 V15.2.0 #6 (source-grounded): all {len(grounded)} concepts grounded ✓",
                "DEBUG",
            )
    except Exception as e:
        log_fn(f"    ⚠️ V15.2.0 #6 failed: {e}", "DEBUG")
        grounded = merged  # fall back to unfiltered

    # ── Final cap ──
    final = grounded[:max_terms]
    log_fn(f"    🎯 V15.2.0: FINAL {len(final)} concepts (cap {max_terms})", "INFO")
    return final


def extract_all_concepts(text: str, max_terms: int = 25) -> list[str]:
    """V3.7.0 Phase 2.3 / V3.9.0: Combined concept extraction (quoted + academic + implicit).

    V3.9.0: Added implicit concept extraction via TF-IDF-style frequency analysis.
    Catches concepts that are never quoted or formally defined but appear
    frequently in the text (e.g., "the end game" used throughout without quotes).

    V3.9.2: Final safety-net filter — ALL terms must pass _is_valid_concept()
    (2+ words or all-caps acronym). This catches single-word leakage from ANY
    source, not just extract_implicit_concepts.
    """
    quoted = extract_definitions(text, max_terms=max_terms)
    academic = extract_academic_terms(text, max_terms=max_terms)
    implicit = extract_implicit_concepts(text, max_terms=max_terms)

    # Merge and deduplicate (case-insensitive)
    seen = set()
    merged = []
    for term in quoted + academic + implicit:
        key = term.lower()
        if key in seen:
            continue
        # V3.9.2: Final safety net — reject single words and invalid concepts
        if not _is_valid_concept(term):
            continue
        seen.add(key)
        merged.append(term)

    return merged[:max_terms]


def extract_implicit_concepts(text: str, max_terms: int = 15) -> list[str]:
    """V3.9.0 / V3.9.1: Extract implicit concepts via frequency analysis.

    V3.9.1: MUST be 2+ words (single words like "A", "Of", "Will" are
    useless as concepts). The regex already requires 2+ Title Case words,
    but we add an explicit check as a safety net.

    Finds capitalized multi-word phrases that appear 3+ times in the text
    but are never quoted or formally defined.
    """
    from collections import Counter

    # Find Title Case phrases (2-4 words) — V3.9.1: explicitly require 2+ words
    title_case_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

    # V3.9.1: Common words that should never be "concepts" even in multi-word phrases
    _IMPLICIT_STOPWORDS = frozenset(
        [
            "The",
            "This",
            "That",
            "These",
            "Those",
            "There",
            "Here",
            "Now",
            "Then",
            "Will",
            "Would",
            "Could",
            "Should",
            "May",
            "Might",
            "Can",
            "Must",
            "Shall",
            "And",
            "Or",
            "But",
            "If",
            "When",
            "Where",
            "Why",
            "How",
            "What",
            "Which",
            "Who",
            "Of",
            "In",
            "On",
            "At",
            "For",
            "With",
            "By",
            "From",
            "To",
            "A",
            "An",
            "Is",
            "Are",
            "Was",
            "Were",
            "Be",
            "Been",
            "Being",
            "Have",
            "Has",
            "Had",
            "Do",
            "Does",
            "Did",
            "Not",
            "No",
            "Only",
            "Own",
            "Same",
            "So",
            "Than",
            "Too",
            "Very",
            "Just",
            "Also",
            "About",
            "Above",
            "Below",
            "Up",
            "Down",
            "Out",
            "Off",
            "Over",
            "Under",
            "Again",
            "Further",
            "Once",
            "Chapter",
            "Part",
            "Section",
            "Book",
            "Author",
            "Note",
            "Tip",
            "Point",
            "Key",
            "Important",
            "Remember",
            "United",
            "States",
            "Public",
            "Key",
            "Target",
            "Alliance",
            "Change",
            "Intelligence",
            "Customer",
            "Development",
            "Use",
            "Unique",
            "Brand",
            "Market",
        ]
    )

    counts = Counter()
    for m in title_case_pattern.finditer(text):
        phrase = m.group(1).strip()
        if len(phrase) < 5 or len(phrase) > 50:
            continue
        words = phrase.split()
        # V3.9.1: Require 2+ words (safety net)
        if len(words) < 2:
            continue
        # Skip if ALL words are stopwords
        if all(w in _IMPLICIT_STOPWORDS for w in words):
            continue
        # Skip if first word is a common word
        if words[0] in _IMPLICIT_STOPWORDS:
            continue
        # Skip if any word is a proper noun (NER)
        try:
            ner_entities = get_all_ner_entities(text[:20000])
            if any(word in ner_entities for word in words):
                continue
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        counts[phrase] += 1

    # Filter: must appear 3+ times
    filtered = [(term, count) for term, count in counts.most_common(max_terms) if count >= 3]
    return [term for term, _ in filtered]


# ════════════════════════════════════════════════════════════════════════════

# V18.20.1.0 (D6): citation/reference/figure extraction moved to
# text_preprocessor_citations.py. Re-exported here for backward compat.
from core.summarisation.text_preprocessor_citations import (  # noqa: F401
    _AUTHOR_YEAR_PATTERN,
    _BRACKET_CITATION_PATTERN,
    _NUMERICAL_CITATION_PATTERN,
    extract_citations,
    extract_figure_descriptions,
    extract_reference_list,
)
