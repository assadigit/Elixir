"""V10.22.0 (B3): SimpleWorker — a BaseWorker subclass that takes a callable.

Replaces the raw ``threading.Thread(target=_run, daemon=True).start()``
pattern with an idiomatic Qt QThread pattern.  The callable runs on a
background thread; the ``finished`` signal fires on the main thread.

Usage (replaces the old pattern)::

    # OLD (still works, but non-idiomatic):
    def _run():
        result = do_work()
        QMetaObject.invokeMethod(self, "_on_done", QueuedConnection)
    threading.Thread(target=_run, daemon=True).start()

    # NEW (idiomatic Qt):
    def _run():
        return do_work()
    worker = SimpleWorker(_run)
    worker.finished.connect(self._on_done)  # runs on main thread
    worker.start()

The worker auto-deletes after finishing (``worker.deleteLater()``).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ui_qt.components.base_worker import BaseWorker


class SimpleWorker(BaseWorker):
    """A BaseWorker that runs a single callable on a background thread.

    The callable's return value is emitted via the ``finished`` signal.
    If the callable raises, the error message is emitted via ``failed``.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        parent: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent=parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        # Auto-delete after finishing (prevent memory leaks)
        self.finished.connect(lambda _: self.deleteLater())
        self.failed.connect(lambda _: self.deleteLater())

    def run(self) -> None:
        """Run the callable.  Emits ``finished`` with the result or
        ``failed`` with the error message."""
        result = self._fn(*self._args, **self._kwargs)
        self.finished.emit(result)
