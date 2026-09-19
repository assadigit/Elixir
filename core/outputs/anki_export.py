"""V10.18.0 (F5): Direct Anki .apkg export.

Generates a proper .apkg file from flashcards using the `genanki` library.
If genanki is not installed, falls back to the existing TSV export.

Usage (from output_runner or converter)::

    from core.outputs.anki_export import export_anki_deck
    export_anki_deck(flashcards, book_title, output_dir, log_callback=log)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def export_anki_deck(
    flashcards: list[tuple[str, str, str, str]],
    book_title: str,
    output_dir: Path,
    log_callback: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Export flashcards as an Anki .apkg file.

    Args:
        flashcards: list of (question, answer, tags, evidence) tuples
        book_title: the book title (used as deck name)
        output_dir: where to save the .apkg file
        log_callback: fn(message, level)

    Returns:
        Path to the .apkg file, or None if genanki not available.
    """
    log = log_callback or (lambda msg, level="INFO": None)

    if not flashcards:
        log("  📴 Anki: no flashcards to export.", "INFO")
        return None

    try:
        import genanki
    except ImportError:
        log("  ℹ️ Anki export: genanki not installed. Install with: pip install genanki", "DEBUG")
        return None

    # Create a unique model ID + deck ID (deterministic from book title)
    model_id = 1607392319 + (hash(book_title) % 100000)
    deck_id = 1607392319 + (hash(book_title + "deck") % 100000)

    # Define the Anki note model (Basic + tags + extra)
    model = genanki.Model(
        model_id,
        f"{book_title} Flashcards",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Tags"},
            {"name": "Extra"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{Front}}<hr id="answer">{{Back}}',
            },
        ],
        css=".card { font-family: sans-serif; font-size: 16px; text-align: center; color: black; background: white; } .tags { font-size: 10px; color: #888; margin-top: 10px; } .extra { font-size: 12px; color: #666; margin-top: 5px; font-style: italic; }",
    )

    # Create the deck
    deck = genanki.Deck(deck_id, book_title)

    # Add notes
    for q, a, tags, evidence in flashcards:
        note = genanki.Note(
            model=model,
            fields=[q, a, tags, evidence or ""],
            tags=_parse_tags(tags),
        )
        deck.add_note(note)

    # Package + save
    output_path = output_dir / f"{book_title}.apkg"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.write_to_file(str(output_path))
    log(f"  ✅ Anki deck: {len(flashcards)} cards → {output_path.name}", "SUCCESS")
    return output_path


def _parse_tags(tags_str: str) -> list[str]:
    """Parse the tags string into a list of Anki-safe tags."""
    if not tags_str:
        return []
    # Tags are space-separated, each tag is "key::value"
    raw_tags = tags_str.split()
    safe_tags = []
    for t in raw_tags:
        # Anki tags can't contain spaces
        safe = re.sub(r"\s+", "_", t)
        if safe:
            safe_tags.append(safe)
    return safe_tags
