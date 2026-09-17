"""Thread-safe bridge between the existing core ``Controller`` and Qt.

The original ``controller.py`` was written for Tkinter: it dispatches UI
callbacks via ``self._tk_root.after(0, ...)``.  Qt is stricter about
cross-thread widget access, but it gives us something Tkinter lacks: **signal
emission is itself thread-safe**.  Emitting a signal from a worker thread
automatically queues the connected slot onto the receiver object's thread
(the Qt main thread) via a ``QueuedConnection``.

So the bridge is delightfully simple: it exposes ``emit_progress`` /
``emit_status`` / ``emit_log`` / ``emit_complete`` bound methods that the
controller registers as its callbacks (``set_callbacks``).  When the
controller calls them from the background conversion thread, the signals fire
and the connected UI slots run on the main thread — no manual marshalling,
no ``set_tk_root``, no scheduler required.

Usage::

    bridge = QtControllerBridge()
    bridge.connect_progress(progress_panel.set_value)
    bridge.connect_status(progress_panel.set_status)
    bridge.connect_log(log_viewer.append)
    bridge.connect_complete(window.on_conversion_complete)

    controller.set_callbacks(
        on_progress=bridge.emit_progress,
        on_status=bridge.emit_status,
        on_log=bridge.emit_log,
        on_complete=bridge.emit_complete,
    )

The controller is then started exactly as before (``start_conversion``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal


class QtControllerBridge(QObject):
    """Carries Controller callbacks from background threads to the Qt main thread.

    The bridge is a ``QObject`` living on the Qt main thread.  Its signals are
    connected to UI widget slots (also on the main thread).  Emitting a signal
    from a worker thread queues the slot call onto the main thread, so widget
    updates are always safe.
    """

    progress = Signal(float)
    status = Signal(str)
    log = Signal(str, str)        # (message, level)
    complete = Signal(object)     # ConversionResult

    # ── emitters the controller registers as its callbacks ──────────────
    def emit_progress(self, value: float) -> None:
        self.progress.emit(float(value))

    def emit_status(self, message: str) -> None:
        self.status.emit(str(message))

    def emit_log(self, message: str, level: str = "INFO") -> None:
        self.log.emit(str(message), str(level))

    def emit_complete(self, result: Any) -> None:
        self.complete.emit(result)

    # ── convenience connectors ───────────────────────────────────────────
    # V18.20.4.1 (P0 / W-b3): the connectors are IDEMPOTENT — they
    # disconnect the same slot first, then connect. A plain ``connect``
    # let every repeated ``connect_*`` call add a DUPLICATE connection:
    # the wizard's ``_start_conversion`` reconnects all four signals on
    # every run ("Convert again" → step9.again_btn → _reset_wizard →
    # _start_conversion), so the second run in one wizard session
    # delivered every log line twice, fired ``_on_progress`` twice, and
    # fired ``_on_complete`` twice — two completion modals and a DOUBLE
    # post-completion action (two 60s shutdown countdowns or a double
    # QApplication.quit). Disconnecting the same slot first is a no-op
    # when not connected (TypeError) or when the receiver is already
    # gone (RuntimeError) — both tolerated. Qt removes ALL connections
    # between the signal and that slot, so pre-existing duplicates
    # self-heal on the next connect.
    def _connect_unique(self, signal, slot: Callable) -> None:
        try:
            signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass  # not connected (or receiver already destroyed) — plain connect below
        signal.connect(slot)

    def connect_progress(self, slot: Callable[[float], None]) -> None:
        self._connect_unique(self.progress, slot)

    def connect_status(self, slot: Callable[[str], None]) -> None:
        self._connect_unique(self.status, slot)

    def connect_log(self, slot: Callable[[str, str], None]) -> None:
        self._connect_unique(self.log, slot)

    def connect_complete(self, slot: Callable[[Any], None]) -> None:
        self._connect_unique(self.complete, slot)
