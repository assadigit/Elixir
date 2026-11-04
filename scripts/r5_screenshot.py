"""Round-5 verification harness — captures the RUNNING application offscreen.

Usage (from repo root):
  python scripts/r5_screenshot.py --size WxH --theme light|dark --out FILE \
      [--wait ms] [--profile DIR] [--seed-settings JSON]

Mirrors the Round-4 evidence workflow (scripts/r4_screenshot.py): a REAL
QApplication + a REAL ElixirWindow (the production widget tree, the
production theme engine, the production backend-status model), rendered
offscreen and grabbed with widget.grab() — never a mockup.

``--seed-settings`` writes the given JSON into the ISOLATED profile's
settings.json BEFORE the Controller constructs, so provider configurations
for the backend-offline / backend-connected evidence flows go through the
app's REAL settings mechanism (nothing is monkeypatched in the window).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1536x1024", help="WxH client size")
    ap.add_argument("--theme", default="light", choices=["light", "dark"])
    ap.add_argument("--out", default="now6.png")
    ap.add_argument("--wait", type=int, default=2500, help="ms to settle (status probes land)")
    ap.add_argument("--profile", default="/tmp/elixir-r5-profile", help="isolated settings dir")
    ap.add_argument(
        "--seed-settings",
        default="",
        help="path to a JSON dict written into the profile's settings.json before launch",
    )
    args = ap.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    # Isolate the harness from the developer's saved geometry/theme so the
    # captures are reproducible (the app persists both under ~/.elixir).
    # NOTE: Settings binds its paths as CLASS ATTRIBUTES at import time
    # (utils/settings.py line ~164), so patching user_data_dir alone does
    # NOT redirect the settings file — the class attrs are retargeted
    # explicitly here for a truly hermetic profile.
    from utils import settings as _settings

    profile = Path(args.profile)
    profile.mkdir(parents=True, exist_ok=True)
    _settings.user_data_dir = lambda: profile  # type: ignore[assignment]
    _settings.Settings._settings_dir = profile
    _settings.Settings._settings_file = profile / "settings.json"

    # Seed the provider configuration through the REAL settings file —
    # BEFORE any import constructs the Settings singleton (the controller
    # import chain builds it at import time, and _load() runs then).
    if args.seed_settings:
        seeded = dict(json.loads(Path(args.seed_settings).read_text(encoding="utf-8")))
    else:
        seeded = {}
    (profile / "settings.json").write_text(json.dumps(seeded, indent=2), encoding="utf-8")

    import ui_qt.app as _appmod
    import ui_qt.theme as _theme

    _appmod._GEOMETRY_FILE = profile / "window_geometry.json"
    _theme.theme_manager.settings_file = profile / "ui_theme.json"

    # run()'s exact order: theme FIRST (app stylesheet + palette + fonts),
    # then the window. The theme file is forced so captures are hermetic.
    forced = "dark" if args.theme == "dark" else "light"
    (profile / "ui_theme.json").write_text(json.dumps({"theme": forced}))
    _theme.theme_manager._mode = forced
    _theme.theme_manager.apply(app, forced)

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
        # The status-strip evidence: the state word + severity the capture
        # actually rendered (printed for the report — never a guess).
        state = getattr(win, "_backend_state", None)
        label = win._backend_label.text() if hasattr(win, "_backend_label") else "?"
        detail = getattr(win, "_backend_detail", "")
        cfg = getattr(win, "_backend_cfg", None)
        provider = cfg.provider if cfg is not None else "?"
        print(f"saved {args.out} {pm.width()}x{pm.height()} theme={args.theme}")
        print(
            f"backend-status: provider={provider} state={state} label={label!r} detail={detail!r}"
        )
        hv = getattr(win, "home_view", None)
        if hv is not None:
            cards = getattr(hv, "_quick_cards", [])
            if cards:
                print(
                    f"layout: hero_h={hv._hero.height()} cols={getattr(hv, '_grid_cols', '?')} "
                    f"card0={cards[0].width()}x{cards[0].height()}"
                )
        win.close()
        app.quit()

    QTimer.singleShot(args.wait, _grab)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
