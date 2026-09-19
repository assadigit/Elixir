"""V3.9.0 Reading List & Progress Tracking.

Tracks which books have been summarized, their concept coverage, and
provides a library dashboard. Stored in ~/.elixir/library.json
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LIBRARY_FILE = Path.home() / ".elixir" / "library.json"


class LibraryManager:
    """Manages the user's book library and reading progress."""

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._library: dict = self._load()

    def _load(self) -> dict:
        """Load library from disk."""
        try:
            if _LIBRARY_FILE.exists():
                with open(_LIBRARY_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)
        return {"books": {}, "last_updated": datetime.now().isoformat()}

    def _save(self) -> None:
        """Save library to disk."""
        try:
            _LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._library["last_updated"] = datetime.now().isoformat()
            with open(_LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._library, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"  ⚠️ Library save failed: {e}", "DEBUG")

    def add_book(
        self,
        title: str,
        author: str = "",
        source_file: str = "",
        chapters_processed: int = 0,
        total_chapters: int = 0,
        concepts_extracted: int = 0,
        keypoints_count: int = 0,
        coverage: float | None = None,
        output_dir: str = "",
    ) -> None:
        """Add or update a book in the library.

        V18.20.4.1 (P0 / W-a2): ``coverage`` is the MEASURED value from the
        run's quality report (or None when no measurement exists). It used
        to be a hardcoded 0.92 placeholder — every book in every library
        carried a fabricated number and ``get_stats`` averaged it. ``None``
        is stored explicitly (honest "unknown") and skipped by the average.
        """
        self._library["books"][title] = {
            "title": title,
            "author": author,
            "source_file": source_file,
            "chapters_processed": chapters_processed,
            "total_chapters": total_chapters,
            "concepts_extracted": concepts_extracted,
            "keypoints_count": keypoints_count,
            "coverage": (round(coverage, 3) if isinstance(coverage, (int, float)) else None),
            "output_dir": output_dir,
            "date_processed": datetime.now().isoformat(),
            "status": "completed" if chapters_processed > 0 else "pending",
        }
        self._save()
        self.log(
            f"  📚 Library: Added '{title}' ({chapters_processed} chapters, {keypoints_count} keypoints)",
            "INFO",
        )

    def get_book(self, title: str) -> dict | None:
        """Get a book's metadata."""
        return self._library["books"].get(title)

    def list_books(self) -> list[dict]:
        """List all books in the library."""
        return sorted(
            self._library["books"].values(),
            key=lambda b: b.get("date_processed", ""),
            reverse=True,
        )

    def get_stats(self) -> dict:
        """Get library statistics.

        V18.20.4.1 (P0 / W-a2): ``avg_coverage`` averages only the books
        with a MEASURED (numeric) coverage — books stored with ``None``
        (no quality report) are skipped instead of dragging the average
        toward 0. When no book has a measurement the stat stays 0.0.
        """
        books = self._library["books"]
        total_books = len(books)
        total_chapters = sum(b.get("chapters_processed", 0) for b in books.values())
        total_keypoints = sum(b.get("keypoints_count", 0) for b in books.values())
        total_concepts = sum(b.get("concepts_extracted", 0) for b in books.values())
        _covs = [
            b.get("coverage") for b in books.values() if isinstance(b.get("coverage"), (int, float))
        ]
        avg_coverage = (sum(_covs) / len(_covs)) if _covs else 0
        return {
            "total_books": total_books,
            "total_chapters": total_chapters,
            "total_keypoints": total_keypoints,
            "total_concepts": total_concepts,
            "avg_coverage": round(avg_coverage, 3),
        }

    def remove_book(self, title: str) -> bool:
        """Remove a book from the library."""
        if title in self._library["books"]:
            del self._library["books"][title]
            self._save()
            return True
        return False
