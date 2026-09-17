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
    return (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah)


def restored_geometry_is_visible(
    x: int, y: int, w: int, h: int,
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
