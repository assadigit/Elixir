"""Round-4 verification harness — captures the RUNNING application offscreen.

Usage (from repo root):
  QT_QPA_PLATFORM=offscreen python scripts/r4_screenshot.py \
      [--size WxH] [--theme light|dark] [--out FILE] [--wait ms]

This mirrors the Round-3 evidence workflow: a REAL QApplication + a REAL
ElixirWindow (the production widget tree, the production theme engine),
rendered offscreen and grabbed with widget.grab() — never a mockup.

The startup order mirrors ``ui_qt.app.run()`` EXACTLY: the theme is
applied to the QApplication BEFORE the window is constructed (the app
stylesheet, palette, and bundled fonts all land before any widget builds),
and the dark capture re-applies the theme + the same refresh hooks the
window's own ``_toggle_theme`` walks.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Run from any CWD — the repo root is the module root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Headless from the very first import (Qt plugins load at QApplication).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Keep the probe loop quiet in screenshots (no real backends here).
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1536x1024", help="WxH client size")
    ap.add_argument("--theme", default="light", choices=["light", "dark"])
    ap.add_argument("--out", default="shot.png")
    ap.add_argument("--wait", type=int, default=900, help="ms to settle")
    args = ap.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    # Isolate the harness from the developer's saved geometry/theme so the
    # captures are reproducible (the app persists both under ~/.elixir).
    from utils import settings as _settings

    _settings.user_data_dir = lambda: Path("/tmp/elixir-shot-profile")  # type: ignore[assignment]
    Path("/tmp/elixir-shot-profile").mkdir(parents=True, exist_ok=True)

    import ui_qt.app as _appmod
    import ui_qt.theme as _theme

    _appmod._GEOMETRY_FILE = Path("/tmp/elixir-shot-profile/window_geometry.json")
    _theme.theme_manager.settings_file = Path("/tmp/elixir-shot-profile/ui_theme.json")

    # run()'s exact order: theme FIRST (app stylesheet + palette + fonts),
    # then the window. The theme file is forced so captures are hermetic.
    Path("/tmp/elixir-shot-profile/ui_theme.json").write_text('{"theme": "light"}')
    _theme.theme_manager._mode = "light"
    _theme.theme_manager.apply(app, "light")

    from controller import Controller
    from ui_qt.app import ElixirWindow

    ctrl = Controller()
    win = ElixirWindow(ctrl)
    win.show()

    w, h = (int(v) for v in args.size.lower().split("x"))
    win.resize(w, h)
    app.processEvents()

    if args.theme == "dark":
        # The window's own toggle path: re-apply + every refresh hook.
        _theme.theme_manager.apply(app, "dark")
        win._refresh_top_bar_icons()
        win._refresh_status_strip()
        win.convert_view.refresh_theme()
        if hasattr(win, "home_view"):
            win.home_view.refresh_theme()
        if hasattr(win, "sidebar"):
            win.sidebar.refresh_theme()
        if hasattr(win, "queue_view"):
            win.queue_view.refresh_theme()
        if hasattr(win, "output_scanner_view"):
            win.output_scanner_view.refresh_theme()
        if hasattr(win, "quarantine_view"):
            win.quarantine_view.refresh_theme()
        app.processEvents()

    def _grab() -> None:
        app.processEvents()
        pm = win.grab()
        pm.save(args.out)
        print(f"saved {args.out} {pm.width()}x{pm.height()} theme={args.theme}")
        # Geometry report — the acceptance evidence numbers.
        sb = win.sidebar
        rail_w = sb.width()
        hv = getattr(win, "home_view", None)
        if hv is not None:
            from PySide6.QtWidgets import QScrollArea

            vp = None
            q = hv.parent()
            while q is not None:
                if isinstance(q, QScrollArea):
                    vp = q.viewport().width()
                    break
                q = q.parent()
            cards = getattr(hv, "_quick_cards", [])
            if cards:
                c0 = cards[0]
                print(
                    f"rail={rail_w} viewport={vp} hero_h={hv._hero.height()} "
                    f"card0={c0.width()}x{c0.height()} cols={getattr(hv, '_grid_cols', '?')}"
                )
        win.close()
        app.quit()

    QTimer.singleShot(args.wait, _grab)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
