"""Round-4 §5 functional testing — every visible navigation destination,
the dialogs, and the wizard launch path, driven on the REAL window
offscreen. EVERY QDialog.exec is intercepted (recorded + rejected) so the
headless run verifies WHAT opens without ever blocking.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication(sys.argv)

# ── the global modal recorder: every dialog opens, is recorded, closes ────
opened: list[str] = []
_orig_exec = QDialog.exec


def _recording_exec(self, *a, **k):
    opened.append(self.metaObject().className())
    self.reject()
    return 0


QDialog.exec = _recording_exec  # type: ignore[method-assign]

from utils import settings as _settings

profile = Path(tempfile.mkdtemp(prefix="elixir_r4_func_"))
_settings.user_data_dir = lambda: profile
import ui_qt.app as _appmod
import ui_qt.theme as _theme

_appmod._GEOMETRY_FILE = profile / "geom.json"
_theme.theme_manager.settings_file = profile / "theme.json"
_theme.theme_manager.apply(app, "light")

from controller import Controller
from ui_qt.app import ElixirWindow

ctrl = Controller()
win = ElixirWindow(ctrl)
win.show()
win.resize(1100, 720)
app.processEvents()

results = {"nav": [], "errors": []}


def _say(msg: str) -> None:
    print(msg, flush=True)


# ── 1) every sidebar navigation destination ───────────────────────────────
NAV_KEYS = [
    "home",
    "full_conversion",
    "summarization",
    "pdf_to_markdown",
    "translation",
    "markdown_styler",
    "packets_tool",
    "ocr_service",
    "pdf_docx_cutter",
    "image_extractor",
    "settings",
    "about",
]
for key in NAV_KEYS:
    try:
        item = win.sidebar._items[key]
        item.clicked.emit()
        app.processEvents()
        active_now = [k for k, it in win.sidebar._items.items() if it.active]
        results["nav"].append((key, active_now[0] if active_now else None))
    except Exception as e:
        results["errors"].append(f"nav {key}: {e}")
_say(f"nav clicks done: {len(results['nav'])}/{len(NAV_KEYS)} ok")

# ── 2) the hero CTA → the Full Conversion Wizard ──────────────────────────
try:
    win.home_view.cta_btn.click()
    app.processEvents()
    _say("hero CTA fired")
except Exception as e:
    results["errors"].append(f"hero CTA: {e}")

# ── 3) the featured Quick Tools card → the same wizard ────────────────────
try:
    win.home_view._quick_cards[-1].clicked.emit("full_conversion")
    app.processEvents()
    _say("wizard card fired")
except Exception as e:
    results["errors"].append(f"wizard card: {e}")

# ── 4) the Quick Tools tool dispatch (each card key routes) ───────────────
for card in win.home_view._quick_cards[:-1]:
    try:
        card.clicked.emit(card.key)
        app.processEvents()
    except Exception as e:
        results["errors"].append(f"card {card.key}: {e}")
_say("tool card dispatch done")

# ── 5) theme switching through the window's own toggle ────────────────────
try:
    win._toggle_theme()
    app.processEvents()
    m1 = _theme.theme_manager.mode
    win._toggle_theme()
    app.processEvents()
    m2 = _theme.theme_manager.mode
    results["theme"] = (m1, m2)
    _say(f"theme toggle: {m1} → {m2}")
except Exception as e:
    results["errors"].append(f"theme toggle: {e}")

# ── 6) "View all tools →" ─────────────────────────────────────────────────
try:
    win.home_view._view_all_btn.click()
    app.processEvents()
    _say("view-all fired")
except Exception as e:
    results["errors"].append(f"view-all: {e}")

# ── 7) window resize sweep (the responsive transitions) ───────────────────
sweep = []
for w, h in [(1920, 1080), (1536, 1024), (1440, 900), (1100, 720), (900, 640), (760, 440)]:
    try:
        win.resize(w, h)
        app.processEvents()
        app.processEvents()
        sweep.append((w, win.home_view._grid_cols, win.sidebar.width()))
    except Exception as e:
        results["errors"].append(f"resize {w}x{h}: {e}")
_say(f"resize sweep: {sweep}")

# ── 8) close + shutdown cleanly ───────────────────────────────────────────
try:
    win.close()
    app.processEvents()
    results["close"] = True
    _say("window closed cleanly")
except Exception as e:
    results["errors"].append(f"close: {e}")

print("=== NAV (key → active pill after click):")
for k, active in results["nav"]:
    print(f"  {k:20} → {active}")
print("=== opened dialogs:", opened)
print("=== theme:", results.get("theme"))
print("=== clean close:", results.get("close"))
print("=== ERRORS:", results["errors"] or "NONE")
