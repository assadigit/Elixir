"""V18.20.4.5 (T-b5): geometry validation helpers — Qt-free so they are
unit-testable without PySide6.

`_restore_geometry` (ui_qt/app.py) used to restore saved x/y blindly; a
monitor change (or a disconnected second monitor) left the window fully
off-screen — the app looked "dead on launch". The helpers below decide
whether a restored window is visible on any screen.
"""

from __future__ import annotations


def rects_intersect(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    """True if rectangles a=(x, y, w, h) and b share any positive area."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def restored_geometry_is_visible(
    x: int,
    y: int,
    w: int,
    h: int,
    screens: list[tuple[int, int, int, int]],
    min_overlap_area: int = 100,
) -> bool:
    """True if the restored window (x, y, w, h) overlaps any screen rect
    (each (x, y, w, h)) by at least ``min_overlap_area`` square pixels —
    a window merely grazing a screen edge by 1px is still effectively
    invisible. Degenerate inputs (no screens, non-positive w/h) → False
    (fail-safe: let the caller fall back to the default geometry)."""
    if not screens or w <= 0 or h <= 0:
        return False
    for s in screens:
        sx, sy, sw, sh = s
        ox = max(0, min(x + w, sx + sw) - max(x, sx))
        oy = max(0, min(y + h, sy + sh) - max(y, sy))
        if ox * oy >= min_overlap_area:
            return True
    return False


# ── V0.6.67: the restore-plan decision layer ────────────────────────────────
#
# Field evidence (Elixir-diagnostics.zip, 2026-10-25, real machine): every
# launch reached "Qt UI launch", the FIRST launch then sat in exec() with a
# window the user could not see, and every LATER launch ACKed the
# single-instance FOCUS protocol and exited(0) silently — "the app doesn't
# open" while a healthy invisible window ran all along. The restored-geometry
# visibility check existed but had two holes: it was SKIPPED for maximized
# restores (a saved "maximized on monitor #2" is maximized onto a monitor
# that may no longer be attached), and nothing re-validated the window's
# FINAL position after show(). The plan below closes the first hole; the
# post-show rescue in ui_qt/app.py closes the second.

DEFAULT_W, DEFAULT_H = 608, 432  # V13.31.0 (#3) defaults (mirrors app.py)
MAX_W, MAX_H = 900, 620  # V13.31.0 clamp ceilings (mirrors app.py)


def sanitize_restore_plan(
    data: dict,
    screens: list[tuple[int, int, int, int]],
) -> dict:
    """Decide how to apply a saved window-geometry dict to the CURRENT screens.

    Pure (Qt-free) so the off-screen decision logic is unit-testable on any
    OS. Returns a plan dict:

    * ``w`` / ``h`` — the clamped size to ``resize()`` to (never trusts a
      saved size above the V13.31.0 ceilings; missing keys → the defaults).
    * ``move_to`` — the saved (x, y) to ``move()`` to, or None when there
      is no saved position or the saved position is not on any CURRENT
      screen.  V0.6.67: the same validation now applies to MAXIMIZED
      restores — the saved position is the window's normal-restore target,
      and ``showMaximized()`` lands on whichever screen that target
      occupies, so honoring an off-screen target maximizes the window onto
      a disconnected monitor (the invisible-forever state).
    * ``center_default`` — True when the caller should center the window
      on the primary screen instead of using a saved position (no saved
      position, or the saved one failed validation).  V0.6.67: this is also
      the no-position default — the old code left first-run placement to
      Qt's default, which is normally visible but not guaranteed.
    * ``maximized`` — whether to ``showMaximized()`` after the move.
    * ``rejected`` — True when a saved position existed but failed the
      on-screen validation (the caller logs the reset — the T-b5 warning
      survives the V0.6.67 refactor).

    Fail-safe: unreadable/absent values degrade to the centered default,
    never to a blind restore.
    """
    try:
        w = min(int(data.get("w", DEFAULT_W) or DEFAULT_W), MAX_W)
        h = min(int(data.get("h", DEFAULT_H) or DEFAULT_H), MAX_H)
    except (TypeError, ValueError):
        w, h = DEFAULT_W, DEFAULT_H
    maximized = bool(data.get("maximized"))
    move_to: tuple[int, int] | None = None
    center_default = True
    rejected = False
    x, y = data.get("x"), data.get("y")
    if isinstance(x, int) and isinstance(y, int):
        # V0.6.67: validate the saved position for NORMAL and MAXIMIZED
        # restores alike (see the module note — the old code skipped the
        # check for maximized windows).
        if restored_geometry_is_visible(x, y, w, h, screens):
            move_to = (x, y)
            center_default = False
        else:
            move_to = None  # off-screen (monitor removed since last run)
            center_default = True
            rejected = True
    return {
        "w": w,
        "h": h,
        "move_to": move_to,
        "center_default": center_default,
        "maximized": maximized,
        "rejected": rejected,
    }
