"""BaseWorker — Qt-safe background worker pattern.

Replaces raw threading.Thread spawns in UI code with a QObject-based
worker that communicates via signals (thread-safe by design).

V10.5.0 audit (Phase 7B): all 20 existing ``threading.Thread`` sites in
``ui_qt/`` were audited and confirmed SAFE — every one either marshals
results back via ``QMetaObject.invokeMethod(..., QueuedConnection)``,
uses ``Signal.emit()``, or does pure compute with no widget access in
the worker body.  The raw ``threading.Thread`` usage is functionally
correct; it's just not idiomatic Qt.  **New code should use BaseWorker**
(subclass + override ``run()`` + connect to ``finished``/``failed``
signals) instead of spawning raw ``threading.Thread``.  Migrating the
existing 20 sites is a future code-quality task (not a correctness fix).

Usage::

    class MyWorker(BaseWorker):
        def run(self) -> None:
            result = do_expensive_work()
            self.finished.emit(result)

    worker = MyWorker()
    worker.start()  # spawns a QThread, moves worker to it, starts
    worker.finished.connect(self._on_done)  # runs on main thread
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot


class BaseWorker(QObject):
    """Base class for Qt-safe background workers.

    Subclasses override ``run()`` and emit ``finished`` or ``failed``.
    The worker is automatically moved to a QThread on ``start()``.

    Signals are thread-safe — emitting from the worker thread queues
    the connected slot onto the receiver's thread (main thread by
    default).  This is the official Qt-recommended pattern.
    """

    # Signals — emit these from run(), never touch Qt widgets directly.
    progress = Signal(int, str)    # (percentage, status_message)
    finished = Signal(object)      # (result: Any)
    failed = Signal(str)           # (error_message)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None

    def start(self) -> None:
        """Spawn a QThread, move this worker to it, and start execution."""
        if self._thread is not None and self._thread.isRunning():
            return  # already running
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._thread_started)
        self._thread.start()

    @Slot()
    def _thread_started(self) -> None:
        """Called when the QThread starts — calls run() and cleans up."""
        try:
            self.run()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if self._thread is not None:
                self._thread.quit()
                # V11.7.0: Do NOT call self._thread.wait() here — this slot
                # runs ON the worker thread (after moveToThread), so wait()
                # would block the thread from actually quitting → infinite hang.
                # The QThread will exit on its own after quit().

    def run(self) -> None:
        """Override this in subclasses. Do the background work here.

        Never access Qt widgets directly from this method. Use signals
        (``self.progress.emit()``, ``self.finished.emit()``) to
        communicate with the main thread.
        """
        raise NotImplementedError("Subclasses must override run()")

    def is_running(self) -> bool:
        """Check if the worker's thread is still running."""
        return self._thread is not None and self._thread.isRunning()

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Wait for the worker to finish. Returns True if finished."""
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)
