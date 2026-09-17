"""V3.9.0 Queue Processing — process multiple books sequentially.

Allows the user to queue multiple PDFs for processing. Each book is
processed in order, with results indexed into the RAG database.

Usage:
    queue = BookQueue(controller, log_callback=log)
    queue.add("book1.pdf", chapters=["Chapter 1", "Chapter 2"])
    queue.add("book2.pdf", chapters=["Chapter 1"])
    queue.start()  # Processes all books sequentially
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class QueueItem:
    """A single book in the processing queue."""
    input_path: Path
    output_dir: Path | None = None
    selected_chapters: list[str] | None = None
    page_range: tuple[int, int] | None = None
    status: str = "pending"  # pending, processing, completed, failed
    error: str = ""
    result: Any | None = None


class BookQueue:
    """Manages a queue of books for sequential processing."""

    def __init__(self, log_callback: Callable[[str, str], None] | None = None):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._queue: list[QueueItem] = []
        self._current_idx = 0
        self._is_running = False
        self._cancel = False

    def add(
        self,
        input_path: Path,
        output_dir: Path | None = None,
        selected_chapters: list[str] | None = None,
        page_range: tuple[int, int] | None = None,
    ) -> int:
        """Add a book to the queue. Returns the queue position."""
        item = QueueItem(
            input_path=input_path,
            output_dir=output_dir,
            selected_chapters=selected_chapters,
            page_range=page_range,
        )
        self._queue.append(item)
        return len(self._queue) - 1

    def remove(self, idx: int) -> bool:
        """Remove a book from the queue."""
        if 0 <= idx < len(self._queue) and not self._is_running:
            self._queue.pop(idx)
            return True
        return False

    def get_queue(self) -> list[QueueItem]:
        """Get the current queue."""
        return self._queue.copy()

    def get_current(self) -> QueueItem | None:
        """Get the currently processing item."""
        if 0 <= self._current_idx < len(self._queue):
            return self._queue[self._current_idx]
        return None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def completed_count(self) -> int:
        return sum(1 for item in self._queue if item.status == "completed")

    def cancel(self) -> None:
        """Cancel processing after the current book."""
        self._cancel = True

    def clear(self) -> None:
        """Clear the queue."""
        if not self._is_running:
            self._queue.clear()
            self._current_idx = 0
