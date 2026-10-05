"""V0.6.18 (W-d3): a thread-safe cancellation flag for podcast generation.

Why this exists
---------------
Before V0.6.18 the audio generator's line-by-line loop had no escape
hatch — once ``generate_podcast_audio`` was called, the only ways to
stop it were (a) wait for it to finish, or (b) kill the worker thread
hard (which leaks the TTS subprocess + the temp WAV files + the line
half-synthesized). Closing the wizard window left the worker running
in the background, still calling the TTS engine for every remaining
line. The operator's report named this gap explicitly:

    "Cancel button during generation? Right now, while a podcast
     generates, the wizard freezes navigation (closing the window
     leaves the generation running in the background — this has always
     been true, but the wizard makes it more visible). A real cancel
     needs a change inside the audio engine's line-by-line loop."

This module is that change. ``CancelToken`` is a tiny threading.Lock-
guarded bool. The wizard creates one per generation, hands it to
``generate_podcast_audio(cancel_token=...)``, and the line loop checks
``token.cancelled`` at the top of every iteration. The UI's cancel
button calls ``token.cancel()`` from the main thread; the worker
thread sees the flip on the next line and exits cleanly.

The token is deliberately minimal — no events, no threads, no Qt
dependency — so it is safe to import from any context (tests, CLI,
the engine itself) without dragging PySide6 in.
"""

from __future__ import annotations

import threading


class CancelToken:
    """A thread-safe cancellation flag.

    The flag starts ``False`` and flips to ``True`` exactly once, when
    :meth:`cancel` is called. Once cancelled it stays cancelled — there
    is no "un-cancel" path; a fresh generation creates a fresh token.

    Usage::

        token = CancelToken()
        # ... hand to a worker ...
        token.cancel()
        if token.cancelled:
            ...
    """

    __slots__ = ("_cancelled", "_lock", "_reason")

    def __init__(self) -> None:
        self._cancelled: bool = False
        self._lock = threading.Lock()
        self._reason: str | None = None

    def cancel(self, reason: str = "cancelled by user") -> None:
        """Flip the flag to True. Idempotent — calling twice is a no-op.

        Args:
            reason: a short, human-readable string the worker can log
                so the operator sees *why* the generation stopped.
                Defaults to "cancelled by user".
        """
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                self._reason = reason

    @property
    def cancelled(self) -> bool:
        """True once :meth:`cancel` has been called (and stays True)."""
        with self._lock:
            return self._cancelled

    @property
    def reason(self) -> str | None:
        """The reason string passed to :meth:`cancel`, or None."""
        with self._lock:
            return self._reason

    def __repr__(self) -> str:  # pragma: no cover — trivial
        with self._lock:
            state = "cancelled" if self._cancelled else "active"
            return f"<CancelToken {state} reason={self._reason!r}>"
