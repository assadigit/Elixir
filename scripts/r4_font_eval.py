"""Round-4 §6.3 — the in-app typeface comparison (Manrope vs IBM Plex Sans).

Renders the REAL dashboard with each candidate family (the production
theme pipeline, the production widget tree) and saves both captures for
the side-by-side review. Not shipped logic — an evaluation harness.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from utils import settings as _settings

_settings.user_data_dir = lambda: Path("/tmp/elixir-shot-profile")

import ui_qt.app as _appmod
import ui_qt.theme as _theme

_appmod._GEOMETRY_FILE = Path("/tmp/elixir-shot-profile/window_geometry.json")
_theme.theme_manager.settings_file = Path("/tmp/elixir-shot-profile/ui_theme.json")

FAMILIES = {
    "manrope": (
        "Manrope",
        ("Manrope-Regular.ttf", "Manrope-Medium.ttf", "Manrope-SemiBold.ttf", "Manrope-Bold.ttf"),
    ),
    "plex": (
        "IBM Plex Sans",
        (
            "IBMPlexSans-Regular.ttf",
            "IBMPlexSans-Medium.ttf",
            "IBMPlexSans-SemiBold.ttf",
            "IBMPlexSans-Bold.ttf",
        ),
    ),
}

from controller import Controller
from ui_qt.app import ElixirWindow


def capture(family: str, files: tuple, out: str, size: tuple, theme: str) -> None:
    # Patch the theme module's stack + file list, then apply fresh.
    _theme._PRIMARY_FILES = files
    _theme.FONT_FAMILY = (
        f'"{family}", "Segoe UI Variable", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
    )
    _theme.theme_manager._primary_loaded = False
    _theme.theme_manager.apply(app, theme)
    win = ElixirWindow(Controller())
    win.show()
    win.resize(*size)
    app.processEvents()
    if theme == "dark":
        _theme.theme_manager.apply(app, "dark")
        win._refresh_top_bar_icons()
        win._refresh_status_strip()
        win.home_view.refresh_theme()
        win.sidebar.refresh_theme()
        win.convert_view.refresh_theme()
        app.processEvents()
    pm = win.grab()
    pm.save(out)
    hv = win.home_view
    print(
        f"{family} {size} {theme}: hero={hv._hero.height()} "
        f"card0={hv._quick_cards[0].width()}x{hv._quick_cards[0].height()} "
        f"wizard={hv._quick_cards[-1].height()} cols={hv._grid_cols}"
    )
    win.close()
    app.processEvents()


for key, (fam, files) in FAMILIES.items():
    capture(fam, files, f"/tmp/font_eval_{key}_1096.png", (1096, 717), "light")
    capture(fam, files, f"/tmp/font_eval_{key}_1536.png", (1536, 1024), "light")
    capture(fam, files, f"/tmp/font_eval_{key}_1096_dark.png", (1096, 717), "dark")
print("done")
