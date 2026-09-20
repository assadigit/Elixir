"""Deterministic Text Preprocessor — pure Python, no LLM, no randomness.

V3.2.0 Tier 1 deterministic quality improvements:

  A2: repair_hyphenation()  — fix "net-\nworking" → "networking"
  A5: extract_definitions() — find book-specific jargon ("Focus Base", etc.)
  A7: extract_ngram_keywords() — bigrams/trigrams for better coverage scoring

These run BEFORE the LLM sees the text, improving quality deterministically.

V0.18 (Phase 5.3): this module was split by concern. The concept/keyword/
entity-extraction family moved VERBATIM (byte-identical bodies) to
``text_preprocessor_concepts.py``; the layout/structure family (hyphenation,
headers/footers, callouts, paragraph joining, sections) moved VERBATIM to
``text_preprocessor_structure.py``. This module keeps the scoring/validation
half — ``DeterministicPreprocessor``, ``verify_numbers_and_quotes``,
``normalize_sentence_boundaries``, the OCR/complexity/vocab scorers,
``compute_source_overlap`` / ``compute_bullet_confidence``, readability +
difficulty + redundancy + coherence, ``classify_bullet``,
``semantic_fact_check`` — and re-exports every moved name at the bottom
(compat facade, same object identities), so all existing importers of
``text_preprocessor_impl`` (the ``text_preprocessor.py`` facade,
function-local production imports, the test suite) keep working unchanged.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re

# V0.18 (Phase 5.3): shared runtime-state singleton — ``semantic_fact_check``
# reads/writes state attributes (D3). The spaCy half of the state usage
# moved to text_preprocessor_concepts.py, but the STATE object is shared
# (same import → same singleton), so patches via any module propagate.
from core.summarisation._runtime_state import state as _runtime_state

# Stopwords for concept filtering — common words that shouldn't be "concepts"
# V18.20.4.8 (P6 / O-a5): the literal moved to the single canonical
# structural-stopwords module (fixes W-a5's 3 drifting copies; also removes
# the duplicated goes entry that was in this line).
# Re-exported under the original private name so the text_preprocessor
# facade's explicit underscore re-export keeps working (W-a6 shim contract).
# V0.18 (Phase 5.3): re-export only — the using functions moved to
# text_preprocessor_concepts.py (which imports the canonical module itself).
from core.summarisation.structural_stopwords import (  # noqa: F401
    CONCEPT_STOPWORDS as _CONCEPT_STOPWORDS,
)

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

# ════════════════════════════════════════════════════════════════════════════
# V0.18 (Phase 5.3): the concept/keyword/entity-extraction family moved
# VERBATIM to text_preprocessor_concepts.py, and the layout/structure family
# moved VERBATIM to text_preprocessor_structure.py. Both are re-exported here
# for backward compat (same object identities) — every existing importer of
# THIS module keeps working unchanged.
# ════════════════════════════════════════════════════════════════════════════
from core.summarisation.text_preprocessor_concepts import (  # noqa: F401
    _ACADEMIC_TERM_PATTERNS,
    _CONCEPT_NOUN_PATTERN,
    _DEFINITION_VERB_PATTERN,
    _DOMAIN_TERMS,
    _KEYWORD_STOPWORDS,
    _LOCATION_PATTERN,
    _NER_EXCLUDE,
    _ORG_PATTERN,
    _PERSON_PATTERN,
    _QUOTED_TERM_PATTERN,
    _SPACY_LANG,
    _SPACY_NLP,
    _extract_conclusion_lists,
    _extract_position_weighted_concepts,
    _extract_proper_noun_theorists,
    _extract_section_headings,
    _filter_concepts_by_source,
    _is_valid_concept,
    _llm_assisted_concept_extraction,
    _load_spacy_model,
    _normalize_heading,
    _tokenize,
    extract_academic_terms,
    extract_all_concepts,
    extract_concepts_rich,
    extract_definitions,
    extract_implicit_concepts,
    extract_named_entities,
    extract_ngram_keywords,
    get_all_ner_entities,
)
from core.summarisation.text_preprocessor_structure import (  # noqa: F401
    _CALLOUT_PATTERN,
    _CALLOUT_PREFIX_PATTERN,
    _HEADING_PATTERN,
    _HYPHEN_PATTERN,
    _MAX_JOINED_WORD_LEN,
    _PAGE_MARKER,
    _SENTENCE_END,
    detect_sections,
    extract_callouts,
    remove_headers_footers,
    repair_hyphenation,
    smart_paragraph_joining,
)
