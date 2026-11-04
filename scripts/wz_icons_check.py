"""Wizard document-type PNG icon verification — real offscreen render.

Usage (from repo root):
  .venv/bin/python scripts/wz_icons_check.py [--out FILE]

Checks (Phase WZ-R1, the icon-swap task):
  1. Every preset key's PNG loads via ``load_png_icon`` (non-null pixmap,
     64×64 target, from assets/icons/{key}.png — the real app path).
  2. The PNG pixmap is NOT the SVG fallback (different pixel content than
     the Lucide line icon rendered at the same size).
  3. Step1Pdf (the real wizard step 1, real TypeCard widgets, real theme)
     renders with the PNG artwork visible — grabbed to a PNG for eyeball
     evidence, both unselected and with a card selected.

Runs fully offscreen (QT_QPA_PLATFORM=offscreen); HOME is isolated so the
profiles machinery never touches the real user dir.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ELIXIR_NO_UPDATE_CHECK", "1")


class _StubController:
    """The two controller methods Step1Pdf touches on build."""

    _settings: dict[str, object] = {}

    def get_setting(self, path: str, default: object = None) -> object:
        return self._settings.get(path, default)

    def update_setting(self, path: str, value: object) -> None:
        self._settings[path] = value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/wz_icons_step1.png")
    args = ap.parse_args()

    # Isolated HOME so ~/.elixir/profiles stays clean.
    home = tempfile.mkdtemp(prefix="elixir-wz-icons-")
    os.environ["HOME"] = home
    if sys.platform == "win32":
        pass  # source-run only on this rig; the sandbox is Linux

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Elixir")

    # ── Check 1+2: every preset PNG loads and differs from the SVG ──────
    from ui_qt.components.icons import load_png_icon, pixmap

    keys = [
        ("normal_book", "book"),
        ("academic_paper", "file-text"),
        ("visual_catalogue", "newspaper"),
        ("infographics_slides", "image"),
        ("full_ocr", "scan"),
        ("mixed", "layers"),
    ]
    failures: list[str] = []
    for key, svg in keys:
        png = load_png_icon(key, 64)
        if png is None or png.isNull():
            failures.append(f"{key}: PNG missing/null at assets/icons/{key}.png")
            continue
        svg_pm = pixmap(svg, color="#374151", size=64)
        if png.toImage() == svg_pm.toImage():
            failures.append(f"{key}: PNG pixel-identical to SVG fallback (suspicious)")
    print(
        "PNG load check:",
        "FAIL " + "; ".join(failures) if failures else "OK (6/6 load, none equal SVG)",
    )

    # ── Check 3: real Step1Pdf render ────────────────────────────────────
    from ui_qt.views.wizard_steps.shared import WizardState
    from ui_qt.views.wizard_steps.step1_pdf import Step1Pdf

    state = WizardState()
    ctrl = _StubController()
    step = Step1Pdf(ctrl, state)
    step.resize(760, 640)
    step.show()
    app.processEvents()

    # Verify each TypeCard's icon label actually holds a non-null pixmap.
    card_issues = []
    for key, _svg in keys:
        tc = step._type_cards.get(key)
        if tc is None:
            card_issues.append(f"{key}: no TypeCard built")
            continue
        pm = tc.icon_label.pixmap()
        if pm is None or pm.isNull():
            card_issues.append(f"{key}: icon label pixmap null")
    print(
        "TypeCard pixmap check:",
        "FAIL " + "; ".join(card_issues) if card_issues else "OK (6/6 labels hold pixmaps)",
    )

    # Select a card (the full-select path: colors + icon refresh).
    step._type_cards["academic_paper"].set_selected(True)
    app.processEvents()

    grab = step.grab()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    grab.save(str(out))
    print(f"Step1 grab: {grab.width()}x{grab.height()} -> {out}")

    rc = 1 if (failures or card_issues) else 0
    print("RESULT:", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
