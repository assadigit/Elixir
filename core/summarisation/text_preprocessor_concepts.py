"""V0.18 (Phase 5.3) — concept / keyword / entity-extraction family.

Moved VERBATIM (byte-identical bodies) from ``text_preprocessor_impl.py``
when that 4,577-LOC module was split by concern:

  - definition / quoted-term extraction (``_is_valid_concept``,
    ``extract_definitions`` + their patterns, the ``_KEYWORD_STOPWORDS``
    tokenizer + ``extract_ngram_keywords``)
  - the rich concept pipeline (``extract_concepts_rich`` + its six
    techniques, ``extract_academic_terms``, ``extract_all_concepts``,
    ``extract_implicit_concepts``)
  - regex NER + the spaCy loader (``extract_named_entities``,
    ``get_all_ner_entities``, ``_load_spacy_model``) — moved WITH this
    family because ``extract_definitions`` / ``extract_implicit_concepts``
    call ``get_all_ner_entities`` directly to reject story-cast names;
    ``text_preprocessor_impl`` re-exports it for its own scorers
    (``compute_bullet_confidence``, ``score_chapter_difficulty``).

``text_preprocessor_impl.py`` re-exports every name below (compat facade,
same object identities), so all existing importers keep working unchanged.
``logger`` keeps its historical channel name so log-record ``name`` fields
are unchanged (and it IS the same logger object the impl module holds).
"""

from __future__ import annotations

import logging
import re
from collections import Counter

# V0.18 (Phase 5.3): literal historical channel name (was
# ``logging.getLogger(__name__)`` in text_preprocessor_impl.py) — preserves
# the exact log-record ``name`` AND yields the SAME logger object the impl
# module's ``logger`` holds.
logger = logging.getLogger("core.summarisation.text_preprocessor_impl")

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
