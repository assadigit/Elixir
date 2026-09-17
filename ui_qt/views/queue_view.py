"""V4.3.0 Queue View — sequential batch processing of multiple PDFs.

A new top-level tab alongside the Convert screen. Lets the user queue
multiple PDFs and process them one at a time, in order, using the SAME
output-types / segmentation / summarisation settings currently selected
on the Convert screen (read from ``Controller.get_setting(...)``).

  ┌─ QueueView ───────────────────────────────────────────────────────┐
  │  ┌─ Card: Add books ───────────────────────────────────────────┐  │
  │  │  [ + Add books… ]  [ Clear all ]      N books in queue      │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  │  ┌─ Card: Queue list (scrollable) ─────────────────────────────┐  │
  │  │  filename.pdf  [pending]  ▓▓▓░░░ 40%   [trash]              │  │
  │  │  other.pdf     [done]     ▓▓▓▓▓▓ 100%  [trash]              │  │
  │  │  …                                                          │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  │  ┌─ Card: Processing ──────────────────────────────────────────┐  │
  │  │  [ Stop ]  [ ▶ Start Queue ]                                │  │
  │  │  Current book: name.pdf                                     │  │
  │  │  ▓▓▓░░░░░░░ 35%   (per-book bar)                            │  │
  │  │  ▓▓░░░░░░░░ 22%   (overall bar)                             │  │
  │  │  Status: Processing page 12…                                │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  │  ┌─ Card: Live log ────────────────────────────────────────────┐  │
  │  │  [LogViewer]                                                │  │
  │  └─────────────────────────────────────────────────────────────┘  │
  └───────────────────────────────────────────────────────────────────┘

Threading model
---------------
The queue runs in a single background ``threading.Thread`` (the "worker").
For each book, the worker calls a synchronous conversion (mirroring
``Controller._run_conversion``) which fires the controller's
``on_progress`` / ``on_status`` / ``on_log`` / ``on_complete`` callbacks.
Those callbacks are routed through the QueueView's own
:class:`QtControllerBridge`, whose signal emissions are marshalled to the
Qt main thread by Qt's queued-connection mechanism — so widget updates
are always safe.

Callback ownership
------------------
The Controller has a single ``set_callbacks()`` slot. The ConvertView
registers its bridge's emitters there during ``__init__``. While the
queue is running, the QueueView *saves* those callbacks and *installs
its own*, then *restores* the ConvertView's callbacks when the queue
finishes (or is cancelled). This guarantees the two views never step on
each other.

The worker thread also registers itself as ``controller.current_conversion_thread``
for the duration of the whole queue, so ``controller.is_converting()``
returns ``True`` and the ConvertView's ``Start Processing`` button is
correctly refused (its ``start_conversion`` checks ``is_converting()``).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.models import ConversionRequest, ConversionResult
from ui_qt.components import Card, LogViewer, StepHeader
from ui_qt.components.icons import icon
from ui_qt.controller_bridge import QtControllerBridge
from ui_qt.theme import theme_manager

logger = logging.getLogger(__name__)


# ── Status constants ────────────────────────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """A single book in the queue."""
    path: Path
    status: str = STATUS_PENDING
    progress: float = 0.0
    error: str = ""
    result: ConversionResult | None = None


# ════════════════════════════════════════════════════════════════════════════
# Row widget
# ════════════════════════════════════════════════════════════════════════════

class _QueueRow(QWidget):
    """One row in the queue list: filename | status badge | progress | remove."""

    remove_clicked = Signal(int)  # row index

    def __init__(
        self,
        index: int,
        item: QueueItem,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._item = item

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(9)

        # Filename (with full-path tooltip)
        self.name_label = QLabel(item.path.name)
        self.name_label.setObjectName("Body")
        self.name_label.setToolTip(str(item.path))
        lay.addWidget(self.name_label, 1)

        # Status badge
        self.status_label = QLabel(item.status)
        self.status_label.setMinimumWidth(74)
        self.status_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(int(item.progress * 100))
        self.progress.setFixedHeight(16)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.progress.setMinimumWidth(96)
        self.progress.setMaximumWidth(180)
        lay.addWidget(self.progress)

        # Remove button
        self.remove_btn = QPushButton()
        self.remove_btn.setObjectName("Compact")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setIcon(icon("trash", theme_manager.palette.text_secondary, 14))
        self.remove_btn.setToolTip("Remove from queue")
        self.remove_btn.setFixedSize(32, 28)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self._index))
        lay.addWidget(self.remove_btn)

        self._refresh_status_style()

    def set_index(self, index: int) -> None:
        """Update the row's index (after a removal shifts indices)."""
        self._index = index

    def update_status(self, status: str, error: str = "") -> None:
        self._item.status = status
        self._item.error = error
        self.status_label.setText(status)
        self._refresh_status_style()

    def update_progress(self, fraction: float) -> None:
        self._item.progress = max(0.0, min(1.0, float(fraction)))
        self.progress.setValue(int(self._item.progress * 100))

    def set_removable(self, removable: bool) -> None:
        self.remove_btn.setEnabled(removable)

    def _refresh_status_style(self) -> None:
        p = theme_manager.palette
        color_map = {
            STATUS_PENDING: (p.text_secondary, p.bg_input),
            STATUS_PROCESSING: (p.text_on_accent, p.accent),
            STATUS_DONE: (p.text_on_accent, p.success),
            STATUS_FAILED: (p.text_on_accent, p.error),
            STATUS_CANCELLED: (p.text_on_accent, p.warning),
        }
        fg, bg = color_map.get(self._item.status, (p.text_primary, p.bg_input))
        self.status_label.setStyleSheet(
            f"QLabel {{ color: {fg}; background-color: {bg};"
            f" border-radius: 7px; padding: 2px 8px;"
            f" font-size: 10px; font-weight: 600;"
            f" text-transform: capitalize; }}"
        )


# ════════════════════════════════════════════════════════════════════════════
# QueueView
# ════════════════════════════════════════════════════════════════════════════

class QueueView(QWidget):
    """V4.3.0 Queue tab — sequential batch processing of multiple PDFs."""

    # ── Internal signals (fired from the worker thread; Qt marshals the
    #    connected slots to the main thread via queued connections).
    book_started = Signal(int)               # book index
    book_finished = Signal(int, str, str)    # book index, status, error
    queue_started = Signal()
    queue_finished = Signal()

    def __init__(
        self,
        controller: Controller,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.bridge = QtControllerBridge()

        # ── Queue state ────────────────────────────────────────────────
        self._queue: list[QueueItem] = []
        self._rows: list[_QueueRow] = []
        self._is_running: bool = False
        self._cancel: threading.Event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._current_idx: int = -1
        self._current_result: ConversionResult | None = None
        # Saved ConvertView callbacks (restored when the queue finishes).
        self._saved_callbacks: tuple[Any | None, Any | None,
                                     Any | None, Any | None] = (
            None, None, None, None,
        )
        # V18.20.4.5 (W-b10): owner tag saved alongside the callbacks, so
        # _restore_convert_callbacks can hand them back with their original
        # owner (the wizard's closeEvent consults controller.callback_owner
        # before re-registering ConvertView's — an unconditional re-register
        # mid-queue used to steal the queue's callbacks: its on_complete
        # result capture stopped firing and per-book modals popped from a
        # hidden tab).
        self._saved_callback_owner: str | None = None

        self._build_ui()
        self._wire_signals()

    # ══════════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 6)
        root.setSpacing(7)

        # ── Step 1: Add books ──────────────────────────────────────────
        add_card = Card(padding=10, spacing=6)
        add_card.addWidget(StepHeader(
            1, "Add books to the queue",
            "Select multiple PDFs, or drag-and-drop them onto the window. "
            "Each book uses the current Convert-screen settings (output "
            "types, segmentation, summarisation).",
        ))
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.setSpacing(7)

        self.add_btn = QPushButton("  Add books…")
        self.add_btn.setObjectName("Primary")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setIcon(icon("plus", theme_manager.palette.text_on_accent, 16))
        self.add_btn.clicked.connect(self._on_add_books)
        add_row.addWidget(self.add_btn)

        self.clear_btn = QPushButton("  Clear all")
        self.clear_btn.setObjectName("Secondary")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setIcon(icon("trash", theme_manager.palette.text_primary, 16))
        self.clear_btn.clicked.connect(self._on_clear_all)
        add_row.addWidget(self.clear_btn)

        add_row.addStretch()

        self.count_lbl = QLabel("0 books in queue")
        self.count_lbl.setObjectName("Caption")
        add_row.addWidget(self.count_lbl)
        add_card.addLayout(add_row)
        root.addWidget(add_card)

        # ── Step 2: Queue list ─────────────────────────────────────────
        list_card = Card(padding=10, spacing=6)
        list_card.addWidget(StepHeader(
            2, "Queue",
            "Books will be processed one at a time, in order. Remove a "
            "book before processing starts if needed.",
        ))

        # Scrollable list of rows
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_scroll.setMinimumHeight(128)
        self.list_scroll.setMaximumHeight(340)
        p = theme_manager.palette
        self.list_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {p.border};"
            f" border-radius: 10px; background-color: {p.bg_input}; }}"
        )

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch()
        self.list_scroll.setWidget(self.list_container)
        list_card.addWidget(self.list_scroll)

        # Empty-state hint (centered inside the scroll area)
        self.empty_lbl = QLabel("No books queued. Click “Add books…” to get started.")
        self.empty_lbl.setObjectName("Caption")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setStyleSheet("padding: 27px; background: transparent;")
        list_card.addWidget(self.empty_lbl)
        self.empty_lbl.setVisible(True)

        root.addWidget(list_card)

        # ── Step 3: Processing ─────────────────────────────────────────
        proc_card = Card(padding=10, spacing=6)
        proc_card.addWidget(StepHeader(
            3, "Process the queue",
            "Starts sequential processing. If a book fails, the queue "
            "logs the error and continues to the next book.",
        ))

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(7)
        btn_row.addStretch()

        self.stop_btn = QPushButton("  Stop")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setIcon(icon("x", theme_manager.palette.error, 16))
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.start_btn = QPushButton("  Start Queue")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setIcon(icon("play", theme_manager.palette.text_on_accent, 17))
        self.start_btn.setMinimumWidth(144)
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)
        proc_card.addLayout(btn_row)

        # Current book label
        self.current_lbl = QLabel("Ready")
        self.current_lbl.setObjectName("Muted")
        proc_card.addWidget(self.current_lbl)

        # Per-book progress bar
        self.book_progress_bar = QProgressBar()
        self.book_progress_bar.setRange(0, 100)
        self.book_progress_bar.setValue(0)
        self.book_progress_bar.setFixedHeight(20)
        self.book_progress_bar.setTextVisible(True)
        self.book_progress_bar.setFormat("Current book: %p%")
        proc_card.addWidget(self.book_progress_bar)

        # Overall progress bar
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setFixedHeight(20)
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFormat("Overall: %p%")
        proc_card.addWidget(self.overall_progress_bar)

        # Status label
        self.status_lbl = QLabel("Idle")
        self.status_lbl.setObjectName("Caption")
        proc_card.addWidget(self.status_lbl)

        root.addWidget(proc_card)

        # ── Live log ───────────────────────────────────────────────────
        log_card = Card(padding=10, spacing=6)
        log_card.addWidget(StepHeader(
            4, "Live log",
            "Per-book progress messages, warnings, and errors.",
        ))
        self.log_viewer = LogViewer(max_lines=4000)
        self.log_viewer.setMinimumHeight(96)
        self.log_viewer.setMaximumHeight(240)
        log_card.addWidget(self.log_viewer)
        root.addWidget(log_card)

        root.addStretch()

    def _wire_signals(self) -> None:
        """Connect the bridge + internal signals to UI slots."""
        # Bridge signals — fired from the worker thread via the controller's
        # callbacks. Qt marshals them to the main thread automatically.
        self.bridge.connect_progress(self._on_bridge_progress)
        self.bridge.connect_status(self._on_bridge_status)
        self.bridge.connect_log(self._on_bridge_log)
        # Bridge's `complete` signal is intentionally NOT connected — the
        # worker thread handles completion directly via book_finished, and
        # the result is captured in `_current_result` (see _install_callbacks).

        # Internal signals — fired from the worker thread, marshalled to
        # the main thread.
        self.book_started.connect(self._on_book_started)
        self.book_finished.connect(self._on_book_finished)
        self.queue_started.connect(self._on_queue_started)
        self.queue_finished.connect(self._on_queue_finished)

    # ══════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════
    def is_running(self) -> bool:
        """True if the queue is currently processing."""
        return self._is_running

    def has_pending(self) -> bool:
        """True if there are books waiting to be processed."""
        return any(item.status == STATUS_PENDING for item in self._queue)

    def stop(self) -> None:
        """Public stop method — cancels the current book and stops the queue.

        Called from ``app.py``'s closeEvent. Does NOT show a confirmation
        dialog (unlike ``_on_stop`` which is the button handler).
        """
        if not self._is_running:
            return
        self._cancel.set()
        try:
            self.controller.cancel_conversion()
        except Exception as _e:
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    def handle_dropped_files(self, paths: list[Path]) -> bool:
        """Accept files dropped onto the window. Returns True if any accepted.

        Only PDFs are accepted (the queue is PDF-focused). Non-PDF files
        are silently skipped.
        """
        accepted = [p for p in paths
                    if p.suffix.lower() == ".pdf" and p.exists()]
        if not accepted:
            return False
        self._add_books(accepted)
        return True

    def refresh(self) -> None:
        """Called when the user switches to the Queue tab."""
        self._update_count()

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styling (called after a theme toggle)."""
        p = theme_manager.palette
        self.log_viewer.refresh_theme()
        self.list_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {p.border};"
            f" border-radius: 10px; background-color: {p.bg_input}; }}"
        )
        self.add_btn.setIcon(icon("plus", p.text_on_accent, 16))
        self.clear_btn.setIcon(icon("trash", p.text_primary, 16))
        self.stop_btn.setIcon(icon("x", p.error, 16))
        self.start_btn.setIcon(icon("play", p.text_on_accent, 17))
        for row in self._rows:
            row._refresh_status_style()
            row.remove_btn.setIcon(icon("trash", p.text_secondary, 14))

    # ══════════════════════════════════════════════════════════════════════
    # Adding / removing books
    # ══════════════════════════════════════════════════════════════════════
    def _on_add_books(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs to queue", str(Path.home()),
            "PDF (*.pdf);;All files (*)",
        )
        if not paths:
            return
        self._add_books([Path(p) for p in paths])

    def _add_books(self, paths: list[Path]) -> None:
        added = 0
        for p in paths:
            # skip duplicates (by path equality)
            if any(item.path == p for item in self._queue):
                continue
            self._queue.append(QueueItem(path=p))
            added += 1
        if added:
            self.log_viewer.append(f"Added {added} book(s) to the queue.", "INFO")
            self._rebuild_rows()
            self._update_count()

    def _on_clear_all(self) -> None:
        if self._is_running:
            QMessageBox.warning(
                self, "Queue running",
                "Stop the queue before clearing it.",
            )
            return
        if not self._queue:
            return
        ret = QMessageBox.question(
            self, "Clear queue",
            f"Remove all {len(self._queue)} book(s) from the queue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self._queue.clear()
        self._rebuild_rows()
        self._update_count()
        self.log_viewer.append("Queue cleared.", "INFO")

    def _remove_book(self, idx: int) -> None:
        if self._is_running:
            QMessageBox.warning(
                self, "Queue running",
                "Stop the queue before removing books.",
            )
            return
        if 0 <= idx < len(self._queue):
            removed = self._queue.pop(idx)
            self._rebuild_rows()
            self._update_count()
            self.log_viewer.append(f"Removed: {removed.path.name}", "INFO")

    def _rebuild_rows(self) -> None:
        """Rebuild the row widgets from ``self._queue`` (after add/remove)."""
        # clear existing rows (keep the trailing stretch)
        while self.list_layout.count() > 1:
            it = self.list_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()
        # add new rows
        for i, queue_item in enumerate(self._queue):
            row = _QueueRow(i, queue_item)
            row.remove_clicked.connect(self._remove_book)
            self._rows.append(row)
            self.list_layout.insertWidget(i, row)
        # empty-state hint lives OUTSIDE the scroll area, so toggle it here
        self.empty_lbl.setVisible(not self._queue)
        # disable remove buttons while running
        if self._is_running:
            for row in self._rows:
                row.set_removable(False)

    def _update_count(self) -> None:
        n = len(self._queue)
        if n == 0:
            self.count_lbl.setText("0 books in queue")
            return
        done = sum(1 for it in self._queue if it.status == STATUS_DONE)
        failed = sum(1 for it in self._queue if it.status == STATUS_FAILED)
        cancelled = sum(1 for it in self._queue if it.status == STATUS_CANCELLED)
        if self._is_running or done or failed or cancelled:
            parts = [f"{n} books"]
            if done:
                parts.append(f"{done} done")
            if failed:
                parts.append(f"{failed} failed")
            if cancelled:
                parts.append(f"{cancelled} cancelled")
            self.count_lbl.setText(" · ".join(parts))
        else:
            self.count_lbl.setText(f"{n} books in queue")

    # ══════════════════════════════════════════════════════════════════════
    # Start / stop
    # ══════════════════════════════════════════════════════════════════════
    def _on_start(self) -> None:
        if self._is_running:
            return
        if not self._queue:
            QMessageBox.information(
                self, "Empty queue",
                "Add some PDFs to the queue first.",
            )
            return
        if not self.has_pending():
            QMessageBox.information(
                self, "Nothing to process",
                "All books are already done, failed, or cancelled. "
                "Clear and re-add books to process them again.",
            )
            return
        # Refuse if the controller is already converting (e.g. the
        # ConvertView is running a single conversion).
        if self.controller.is_converting():
            QMessageBox.warning(
                self, "Conversion in progress",
                "A conversion is already running on the Convert tab. "
                "Wait for it to finish before starting the queue.",
            )
            return

        # reset cancel flag + UI state
        self._cancel.clear()
        self._is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        for row in self._rows:
            row.set_removable(False)

        self.queue_started.emit()

        self._worker_thread = threading.Thread(
            target=self._queue_worker, daemon=True,
        )
        self._worker_thread.start()

    def _on_stop(self) -> None:
        if not self._is_running:
            return
        ret = QMessageBox.question(
            self, "Stop queue",
            "Stop the queue?\n\nThe current book will be cancelled and "
            "remaining books will be skipped.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self.stop()
        self.log_viewer.append("Stopping queue…", "WARNING")
        self.status_lbl.setText("Stopping…")
        self.stop_btn.setEnabled(False)

    # ══════════════════════════════════════════════════════════════════════
    # Worker thread
    # ══════════════════════════════════════════════════════════════════════
    def _queue_worker(self) -> None:
        """Background thread that processes pending books sequentially."""
        # Register this thread as the controller's active conversion thread
        # so is_converting() returns True (prevents the ConvertView from
        # starting a parallel conversion). Held for the duration of the
        # whole queue — _run_one_conversion does NOT clear it.
        self.controller.current_conversion_thread = threading.current_thread()
        # Save the ConvertView's callbacks and install the queue's.
        self._install_queue_callbacks()
        try:
            for i, item in enumerate(self._queue):
                if item.status != STATUS_PENDING:
                    continue  # skip already-processed books (e.g. on re-run)
                if self._cancel.is_set():
                    item.status = STATUS_CANCELLED
                    self.book_finished.emit(i, STATUS_CANCELLED, "Cancelled by user")
                    continue

                self._current_idx = i
                item.status = STATUS_PROCESSING
                item.progress = 0.0
                self.book_started.emit(i)

                try:
                    request = self._build_request_for_item(item)
                    result = self._run_one_conversion(request)
                    if self._cancel.is_set():
                        item.status = STATUS_CANCELLED
                        item.error = "Cancelled"
                        self.book_finished.emit(i, STATUS_CANCELLED, "Cancelled")
                    elif result.success:
                        item.status = STATUS_DONE
                        item.progress = 1.0
                        item.result = result
                        self.book_finished.emit(i, STATUS_DONE, "")
                    else:
                        item.status = STATUS_FAILED
                        item.error = result.error_msg or "Unknown error"
                        self.book_finished.emit(i, STATUS_FAILED, item.error)
                except Exception as e:  # noqa: BLE001
                    logger.exception("Queue worker crashed on book %d", i)
                    item.status = STATUS_FAILED
                    item.error = str(e)
                    self.book_finished.emit(i, STATUS_FAILED, str(e))
        finally:
            self._current_idx = -1
            self.controller.current_conversion_thread = None
            self._restore_convert_callbacks()
            self._is_running = False
            self.queue_finished.emit()

    # ── Callback management ─────────────────────────────────────────────
    def _install_queue_callbacks(self) -> None:
        """Save the current controller callbacks and install the queue's."""
        self._saved_callbacks = (
            self.controller.on_progress,
            self.controller.on_status,
            self.controller.on_log,
            self.controller.on_complete,
        )
        # V18.20.4.5 (W-b10): remember WHO owned the callbacks we're
        # replacing, so the restore below reinstalls them with their
        # original owner tag (wizard_view.closeEvent reads that tag to
        # refuse stealing them back mid-queue).
        self._saved_callback_owner = getattr(self.controller, "callback_owner", None)
        self._current_result = None

        def on_complete(result: ConversionResult) -> None:
            # Capture the result so the worker thread can read it after
            # _run_one_conversion returns. (The controller's _safe_complete
            # routes through _tk_call which, without a scheduler/tk_root,
            # calls on_complete directly on the worker thread — so this
            # assignment happens synchronously before _run_one_conversion
            # returns.)
            self._current_result = result
            # Fire the bridge signal for any UI side-effects. Connected
            # slots run on the main thread via Qt's queued connection.
            self.bridge.emit_complete(result)

        self.controller.set_callbacks(
            on_progress=self.bridge.emit_progress,
            on_status=self.bridge.emit_status,
            on_log=self.bridge.emit_log,
            on_complete=on_complete,
            # V18.20.4.5 (W-b10): tag the queue as the owner for the whole
            # run — wizard_view.closeEvent checks this and leaves the
            # callbacks alone while the queue is running.
            owner="queue",
        )

    def _restore_convert_callbacks(self) -> None:
        """Restore the previously-saved controller callbacks."""
        on_progress, on_status, on_log, on_complete = self._saved_callbacks
        try:
            self.controller.set_callbacks(
                on_progress=on_progress,
                on_status=on_status,
                on_log=on_log,
                on_complete=on_complete,
                # V18.20.4.5 (W-b10): restore with the saved owner tag —
                # whoever owned them before the queue started owns them
                # again (usually "convert_view").
                owner=self._saved_callback_owner,
            )
        except Exception:
            logger.warning("Failed to restore ConvertView callbacks", exc_info=True)
        self._saved_callbacks = (None, None, None, None)
        self._saved_callback_owner = None

    # ── Per-book conversion ─────────────────────────────────────────────
    def _run_one_conversion(
        self, request: ConversionRequest
    ) -> ConversionResult:
        """Run a single conversion synchronously (in the worker thread).

        Mirrors ``Controller._run_conversion`` but:
          - Does NOT clear ``controller.current_conversion_thread`` (the
            queue worker thread holds it for the duration of the whole
            queue, so ``is_converting()`` stays True between books).
          - Returns the ``ConversionResult`` so the worker can mark the
            book done/failed without waiting for the async ``complete``
            signal.
        """
        from core.pipeline import Converter  # local import (heavier module)
        try:
            self.controller.cancel_event.clear()
            self.controller.converter = Converter(
                request=request,
                progress_callback=self.controller._safe_progress,
                status_callback=self.controller._safe_status,
                log_callback=self.controller._safe_log,
                cancel_event=self.controller.cancel_event,
            )
            result = self.controller.converter.convert()
            self.controller._safe_complete(result)
            if result.success and result.full_markdown_path:
                try:
                    self.controller.save_book_settings(
                        result.full_markdown_path.parent, request
                    )
                except Exception as e:
                    logger.warning("Failed to save book settings: %s", e)
            return result
        except Exception as e:
            logger.exception("Queue conversion crashed")
            self.controller._safe_log(f"Fatal error: {e}", "ERROR")
            return ConversionResult(success=False, error_msg=str(e))

    def _build_request_for_item(self, item: QueueItem) -> ConversionRequest:
        """Build a ConversionRequest for a queue item using current settings.

        Reads the same setting keys the Process Wizard does (V18.20.4.1: the
        former ``ConvertView._start_conversion`` was deleted with the V11.0.0
        legacy block) but forces ``input_path`` to the item's path and
        ``output_dir`` to the item's parent folder. Page-range,
        chapter-selection, and Full-OCR are NOT carried over (those are
        per-book UI selections, not global settings).
        """
        ui_data: dict[str, Any] = {
            "input_path": str(item.path),
            "output_dir": str(item.path.parent),
            "password": None,
            "use_llm_ocr": self.controller.get_setting("ocr.use_llm", True),
            "auto_detect_scanned": self.controller.get_setting(
                "ocr.auto_detect_scanned", True
            ),
            "force_ocr_all_pages": self.controller.get_setting(
                "ocr.force_ocr_all_pages", False
            ),
            "source_type": self.controller.get_setting(
                "source_type", "normal_book"
            ),
            "include_executive_summary": self.controller.get_setting(
                "summarisation.include_executive_summary", True
            ),
            "include_thorough_summary": self.controller.get_setting(
                "summarisation.include_thorough_summary", True
            ),
            "include_keypoints": self.controller.get_setting(
                "summarisation.include_keypoints", True
            ),
            "enable_content_filter": self.controller.get_setting(
                "content_filter.enabled", True
            ),
            "academic_rigor": self.controller.get_setting(
                "summarisation.academic_rigor", False
            ),
            "simplified_keypoints_enabled": self.controller.get_setting(
                "summarisation.simplified_keypoints_enabled", False
            ),
            "max_workers": self.controller.get_setting(
                "summarisation.max_workers", 2
            ),
            "extract_figure_text": self.controller.get_setting(
                "advanced.extract_figure_text", False
            ),
            "manual_segments": None,
            "page_range_start": None,
            "page_range_end": None,
            "selected_chapters": None,
        }
        return self.controller.build_request_from_ui(ui_data)

    # ══════════════════════════════════════════════════════════════════════
    # Slots — bridge signals (fired from worker thread, queued to main)
    # ══════════════════════════════════════════════════════════════════════
    def _on_bridge_progress(self, value: float) -> None:
        """Per-book progress update from the controller."""
        idx = self._current_idx
        if 0 <= idx < len(self._rows):
            self._rows[idx].update_progress(value)
            self.book_progress_bar.setValue(int(value * 100))
        self._update_overall_progress()

    def _on_bridge_status(self, message: str) -> None:
        self.status_lbl.setText(message)

    def _on_bridge_log(self, message: str, level: str) -> None:
        self.log_viewer.append(message, level)

    # ══════════════════════════════════════════════════════════════════════
    # Slots — internal signals (fired from worker thread, queued to main)
    # ══════════════════════════════════════════════════════════════════════
    @Slot(int)
    def _on_book_started(self, idx: int) -> None:
        if 0 <= idx < len(self._rows):
            self._rows[idx].update_status(STATUS_PROCESSING)
            self._rows[idx].update_progress(0.0)
        if 0 <= idx < len(self._queue):
            self.current_lbl.setText(f"Processing: {self._queue[idx].path.name}")
        self.book_progress_bar.setValue(0)
        self._update_count()

    @Slot(int, str, str)
    def _on_book_finished(self, idx: int, status: str, error: str) -> None:
        if 0 <= idx < len(self._rows):
            self._rows[idx].update_status(status, error)
            if status == STATUS_DONE:
                self._rows[idx].update_progress(1.0)
        if 0 <= idx < len(self._queue):
            item = self._queue[idx]
            if status == STATUS_DONE:
                msg = f"✓ Done: {item.path.name}"
                if item.result and item.result.full_markdown_path:
                    msg += f"  →  {item.result.full_markdown_path}"
                self.log_viewer.append(msg, "SUCCESS")
            elif status == STATUS_FAILED:
                self.log_viewer.append(
                    f"✗ Failed: {item.path.name} — {error}", "ERROR"
                )
            elif status == STATUS_CANCELLED:
                self.log_viewer.append(
                    f"⊘ Cancelled: {item.path.name}", "WARNING"
                )
        self._update_count()
        self._update_overall_progress()

    @Slot()
    def _on_queue_started(self) -> None:
        self.log_viewer.append("=" * 60, "INFO")
        self.log_viewer.append("Queue processing started.", "INFO")
        self.status_lbl.setText("Processing…")

    @Slot()
    def _on_queue_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        for row in self._rows:
            row.set_removable(True)

        done = sum(1 for it in self._queue if it.status == STATUS_DONE)
        failed = sum(1 for it in self._queue if it.status == STATUS_FAILED)
        cancelled = sum(1 for it in self._queue if it.status == STATUS_CANCELLED)
        total = len(self._queue)

        if failed or cancelled:
            self.status_lbl.setText(
                f"Finished — {done} done, {failed} failed, "
                f"{cancelled} cancelled of {total}"
            )
            self.log_viewer.append(
                f"Queue finished with errors: {done} done, {failed} failed, "
                f"{cancelled} cancelled.",
                "WARNING",
            )
        else:
            self.status_lbl.setText(f"Finished — {done} of {total} books done")
            self.log_viewer.append(
                f"Queue finished: {done} of {total} books done.", "SUCCESS"
            )

        self.current_lbl.setText("Idle")
        self.book_progress_bar.setValue(0)
        self._update_count()

        # success chime if all books succeeded (and not disabled in settings)
        if (
            done > 0
            and failed == 0
            and cancelled == 0
            and self.controller.get_setting("ui.play_success_sound", True)
        ):
            try:
                from ui_qt.components.sounds import play_success
                play_success()
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════
    def _update_overall_progress(self) -> None:
        """Overall = (done books + current book's partial fraction) / total."""
        if not self._queue:
            self.overall_progress_bar.setValue(0)
            return
        total = len(self._queue)
        done = sum(1 for it in self._queue if it.status == STATUS_DONE)
        partial = 0.0
        if 0 <= self._current_idx < len(self._queue):
            it = self._queue[self._current_idx]
            if it.status == STATUS_PROCESSING:
                partial = it.progress
        fraction = (done + partial) / total
        self.overall_progress_bar.setValue(int(fraction * 100))
