"""Glossary manager — extracts and maintains a terminology glossary.

During the first chunk's translation, this module extracts:
  * Proper nouns (person names, organization names, places) via spaCy NER
    (already installed in the project) with a regex fallback.
  * Recurring technical terms (capitalized multi-word phrases).
  * Book titles and author names (if detectable).

The glossary is:
  1. Built from the first N chunks of source text.
  2. Passed as context to all subsequent translation chunks so "Mark Manson"
     consistently becomes "مارک منسون" rather than varying.
  3. Stored as ``translation_logs/Book.glossary.json`` for reuse/editing.

The glossary is language-agnostic (stores source terms). The translator
prompt instructs the LLM to use the glossary's translations consistently.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── spaCy lazy-load ───────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

_nlp_en = None
_nlp_available = None


def _get_nlp():
    """Lazy-load spaCy English model. Returns None if unavailable.

    V10.31.0 (Sprint 4.6): delegates to the shared singleton.
    """
    from core.llm.model_singletons import get_spacy_nlp

    nlp = get_spacy_nlp("en_core_web_sm")
    _nlp_available = nlp is not None
    return nlp


# ── Data structures ───────────────────────────────────────────────────────


@dataclass
class GlossaryEntry:
    """A single glossary term.

    Attributes:
        source:      the source-language term (e.g., "Mark Manson").
        translation: the target-language translation (e.g., "مارک منسون"),
                     or empty if not yet translated.
        entity_type: "PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART", or "TERM".
        frequency:   how many times the term appeared in the source text.
    """

    source: str
    translation: str = ""
    entity_type: str = "TERM"
    frequency: int = 1


@dataclass
class Glossary:
    """A collection of glossary entries."""

    entries: dict[str, GlossaryEntry] = field(default_factory=dict)
    source_lang: str = "en"
    target_lang: str = "fa"

    def add(self, term: str, entity_type: str = "TERM") -> None:
        """Add a term to the glossary (or increment its frequency)."""
        term = term.strip()
        if not term or len(term) < 2:
            return
        # Normalize: title-case for consistency
        key = term.lower()
        if key in self.entries:
            self.entries[key].frequency += 1
        else:
            self.entries[key] = GlossaryEntry(
                source=term,
                entity_type=entity_type,
            )

    def get_terms_for_prompt(self) -> str:
        """Format the glossary as a string for inclusion in the translation prompt.

        Returns a string like::

            Glossary (keep these translations consistent):
            - Mark Manson → مارک منسون
            - Atomic Habits → عادت‌های اتمی
            ...
        """
        if not self.entries:
            return ""
        lines = ["Glossary (keep these translations consistent):"]
        # Sort by frequency (most frequent first), take top 50
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (-e.frequency, e.source),
        )[:50]
        for entry in sorted_entries:
            if entry.translation:
                lines.append(f"  - {entry.source} -> {entry.translation}")
            else:
                lines.append(f"  - {entry.source} -> (translate consistently)")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "entries": {
                k: {
                    "source": e.source,
                    "translation": e.translation,
                    "entity_type": e.entity_type,
                    "frequency": e.frequency,
                }
                for k, e in self.entries.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> Glossary:
        """Deserialize from a dict."""
        g = cls(source_lang=d.get("source_lang", "en"), target_lang=d.get("target_lang", "fa"))
        for key, entry_d in d.get("entries", {}).items():
            g.entries[key] = GlossaryEntry(
                source=entry_d["source"],
                translation=entry_d.get("translation", ""),
                entity_type=entry_d.get("entity_type", "TERM"),
                frequency=entry_d.get("frequency", 1),
            )
        return g

    def save(self, path: Path) -> None:
        """Save the glossary to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> Glossary | None:
        """Load a glossary from a JSON file, or None if it doesn't exist."""
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except OSError:
            return None


# ── Glossary manager ─────────────────────────────────────────────────────


class GlossaryManager:
    """Extracts and manages a terminology glossary from source text.

    Usage::

        gm = GlossaryManager(source_lang="en", target_lang="fa")
        gm.extract_from_text(first_chunk_text)
        gm.extract_from_text(second_chunk_text)
        glossary_prompt = gm.glossary.get_terms_for_prompt()
        # ... pass glossary_prompt to translator ...
        gm.glossary.save(Path("translation_logs/MyBook.glossary.json"))
    """

    # Regex patterns for fallback entity extraction (when spaCy is unavailable)
    _CAPITALIZED_PHRASE_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
    # English book titles in quotes or italics
    _QUOTED_TITLE_RE = re.compile(r'["\u201c"]([^""]{3,60})["\u201d"]')

    def __init__(self, source_lang: str = "en", target_lang: str = "fa") -> None:
        self.glossary = Glossary(source_lang=source_lang, target_lang=target_lang)

    def extract_from_text(self, text: str, max_chars: int = 50000) -> None:
        """Extract terminology from a chunk of text.

        Only processes the first ``max_chars`` characters to keep it fast.
        Uses spaCy NER if available, with regex fallback.
        """
        if not text:
            return
        sample = text[:max_chars]

        # Only extract from English source text (NER models are English)
        if self.glossary.source_lang == "en":
            self._extract_en(sample)
        # For Farsi source, we skip NER (no good Farsi NER model in spaCy)
        # and rely on the translator to handle terminology.

    def _extract_en(self, text: str) -> None:
        """Extract entities from English text via spaCy + regex fallback."""
        nlp = _get_nlp()
        if nlp is not None:
            try:
                doc = nlp(text)
                for ent in doc.ents:
                    if ent.label_ in (
                        "PERSON",
                        "ORG",
                        "GPE",
                        "PRODUCT",
                        "WORK_OF_ART",
                        "NORP",
                        "EVENT",
                        "FAC",
                    ):
                        self.glossary.add(ent.text, ent.label_)
                return
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)  # fall through to regex

        # Regex fallback: capitalized multi-word phrases
        for m in self._CAPITALIZED_PHRASE_RE.finditer(text):
            phrase = m.group(1)
            # Skip common false positives
            if phrase.lower() in (
                "The",
                "This",
                "That",
                "These",
                "Those",
                "It Is",
                "There Is",
                "There Are",
            ):
                continue
            if len(phrase.split()) >= 2:  # only multi-word phrases
                self.glossary.add(phrase, "TERM")

        # Quoted titles
        for m in self._QUOTED_TITLE_RE.finditer(text):
            title = m.group(1)
            if len(title.split()) >= 2:
                self.glossary.add(title, "WORK_OF_ART")

    def update_translations(self, source_term: str, translation: str) -> None:
        """Update the translation for a glossary term (called when the
        translator first uses a term — subsequent chunks should reuse it)."""
        key = source_term.strip().lower()
        if key in self.glossary.entries:
            if not self.glossary.entries[key].translation:
                self.glossary.entries[key].translation = translation.strip()

    def get_context_for_prompt(self) -> str:
        """Return the glossary formatted for inclusion in the translation prompt."""
        return self.glossary.get_terms_for_prompt()
