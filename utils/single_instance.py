"""V0.6.67: the single-instance FOCUS wire protocol — pure and Qt-free.

Why this module exists
======================
Field evidence (Elixir-diagnostics.zip, 2026-10-25): the V0.6.65 protocol
sent ``FOCUS`` and trusted ANY ``OK`` reply as "the primary just raised its
window", then exited(0).  On the reporting machine the primary's window was
shown but INVISIBLE (off-screen geometry) — it ACKed every FOCUS request
(``showNormal``/``raise_`` cannot rescue a window stranded on a detached
monitor), so every later double-click exited silently into a window the
user could not see.  The app "never opened" while a perfectly healthy
invisible window ran the whole time.

V0.6.67 makes the reply HONEST: the primary reports whether its window is
actually on a visible screen AFTER its self-heal attempt
(``ui_qt.app._ensure_window_onscreen``), and the second launch only defers
to a primary that can prove visibility — otherwise it takes over and shows
its own (force-onscreen) window.

Wire format (bytes over the existing QLocalSocket pair)::

    second instance → primary :  b"FOCUS"
    primary → second instance  :  b"OK-VISIBLE"    (window is on a screen)
                                  b"OK-INVISIBLE"  (still off-screen after healing)
                                  b"OK"            (legacy / no window to raise)

Cross-version compatibility falls out of the prefix: a NEW second instance
parses legacy ``OK`` as visible (the V0.6.65/66 primary did its best), and
an OLD second instance still matches ``b"OK" in reply`` for both new reply
shapes (so upgrades-in-place never wedge: the old behavior is the worst
case, never worse).

Everything here is stdlib-only and side-effect-free — pinned by
tests/test_v0667_window_visibility.py.
"""

from __future__ import annotations

FOCUS_REQUEST = b"FOCUS"
REPLY_VISIBLE = b"OK-VISIBLE"
REPLY_INVISIBLE = b"OK-INVISIBLE"
REPLY_LEGACY = b"OK"


def primary_reply(window_visible: bool) -> bytes:
    """The primary's answer to a FOCUS request, given its post-heal state."""
    return REPLY_VISIBLE if window_visible else REPLY_INVISIBLE


def focus_ack_indicates_visible(reply: bytes) -> bool:
    """True when a FOCUS reply proves the primary's window is on a screen.

    Accepts the legacy ``OK`` (no visibility claim — treat as visible, the
    V0.6.65/66 contract); rejects ``OK-INVISIBLE`` (the honest "my window
    is off-screen even after the self-heal" report — the caller takes over
    instead of exiting) and empty/garbage replies.
    """
    if not reply:
        return False
    if REPLY_INVISIBLE in reply:
        return False
    return REPLY_LEGACY in reply  # matches OK, OK-VISIBLE (prefix)


__all__ = [
    "FOCUS_REQUEST",
    "REPLY_VISIBLE",
    "REPLY_INVISIBLE",
    "REPLY_LEGACY",
    "primary_reply",
    "focus_ack_indicates_visible",
]
