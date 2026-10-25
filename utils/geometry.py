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

# V0.6.68: the compact-era defaults are RETIRED. The V13.31.0 "20% smaller"
# change (760x540 → 608x432, "more compact per user request") met every
# fresh install half a decade later: a new machine has no saved geometry,
# so the installed app opened at 608x432 — the 2026-10-26 field report
# ("not in the original container size … very compact and small … it has
# scroll"). The ORIGINAL pre-V13.31.0 dimension is restored, and the
# compact-era clamp ceilings rose with it — a deliberately resized
# 1000x700 window used to be silently scaled back down to 900x620 on every
# restart, the other face of "you scaled down the dimensions".
DEFAULT_W, DEFAULT_H = 760, 540  # V0.6.68 — the ORIGINAL pre-V13.31.0 default, restored
MAX_W, MAX_H = 1600, 1000  # V0.6.68 — was 900x620 (the compact-era ceiling)

# V0.6.68 migration: a saved geometry of EXACTLY the compact-era default is
# the fingerprint of "opened, never resized" — every V0.6.63–67 install
# saved it on close, so without a migration those machines would keep
# re-opening compact forever (the reporter's own window_geometry.json
# included). A legacy unstamped file at that exact size is treated as "no
# preference" and receives the restored 760x540 default; once a V0.6.68+
# save stamps GEOMETRY_SCHEMA_VERSION the choice is final — a deliberate
# hand-resize back to 608x432 persists from then on.
LEGACY_COMPACT_W, LEGACY_COMPACT_H = 608, 432
GEOMETRY_SCHEMA_VERSION = 2


def sanitize_restore_plan(
    data: dict,
    screens: list[tuple[int, int, int, int]],
) -> dict:
    """Decide how to apply a saved window-geometry dict to the CURRENT screens.

    Pure (Qt-free) so the off-screen decision logic is unit-testable on any
    OS. Returns a plan dict:

    * ``w`` / ``h`` — the clamped size to ``resize()`` to (never trusts a
      saved size above the ceilings; missing keys → the defaults). V0.6.68:
      an UNSTAMPED save at exactly the compact-era default (608x432) also
      falls back to the defaults — the never-resized fingerprint migration
      (see LEGACY_COMPACT_W above).
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
    if data.get("v") != GEOMETRY_SCHEMA_VERSION and (w, h) == (
        LEGACY_COMPACT_W,
        LEGACY_COMPACT_H,
    ):
        # V0.6.68: the never-resized fingerprint (see the module note) —
        # deliver the restored original default to compact-era installs.
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
