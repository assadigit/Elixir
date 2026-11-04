"""Round-5 §3 verification — the Full Conversion Wizard card's alignment,
measured from REAL widget geometry (never visual guesswork).

Checks (spec §3):
  1. The title+description text block is vertically centered in the card's
     content area: the gap above the block == the gap below it (±1 px).
  2. The icon's vertical center == the card's vertical center.
  3. The arrow's vertical center == the card's vertical center.
  4. The text is LEFT-aligned: the title and description labels share the
     same left edge (±1 px), and the text block starts after the icon.
  5. The arrow is right-aligned: it hugs the card's right inset.
  6. Equal, intentional spacing: icon→text gap == text→arrow gap (±4 px,
     the layout's own spacing contract).
  7. The grid still composes 3 columns × 3 rows at the field window.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Elixir")
    app.setOrganizationName("Elixir")

    from utils import settings as _settings

    _settings.user_data_dir = lambda: Path("/tmp/elixir-align-profile")  # type: ignore[assignment]
    Path("/tmp/elixir-align-profile").mkdir(parents=True, exist_ok=True)

    import ui_qt.app as _appmod
    import ui_qt.theme as _theme

    _appmod._GEOMETRY_FILE = Path("/tmp/elixir-align-profile/window_geometry.json")
    _theme.theme_manager.settings_file = Path("/tmp/elixir-align-profile/ui_theme.json")
    Path("/tmp/elixir-align-profile/ui_theme.json").write_text('{"theme": "light"}')
    _theme.theme_manager._mode = "light"
    _theme.theme_manager.apply(app, "light")

    from controller import Controller
    from ui_qt.app import ElixirWindow

    win = ElixirWindow(Controller())
    win.show()
    win.resize(1096, 717)  # the user's field window
    app.processEvents()

    hv = win.home_view
    cards = hv._quick_cards
    featured = [c for c in cards if c._featured]
    assert len(featured) == 1, "exactly one featured card"
    card = featured[0]
    app.processEvents()

    # ── absolute geometry inside the card ──────────────────────────────
    # (icon/arrow/labels are CHILDREN of the card — their x/y are
    # card-LOCAL; the card's own midline is height/2 in the same space)
    card_c = card.height() / 2
    icon = card._icon_label
    icon_c = icon.y() + icon.height() / 2
    arrow = card._arrow
    arrow_c = arrow.y() + arrow.height() / 2
    title = card._title_label
    desc = card._desc_label
    block_top = title.y()
    block_bottom = desc.y() + desc.height()
    block_c = (block_top + block_bottom) / 2

    lay = card.layout()
    m_left, m_top, m_right, m_bottom = lay.getContentsMargins()
    # The card's QSS 1px border insets the layout's contents rect — the
    # layout margins are relative to contentsRect(), not the widget rect.
    cr = card.contentsRect()
    content_right = cr.x() + cr.width()  # exclusive x of the content area

    gap_above = block_top  # card-local; the frame border shifts both gaps equally
    gap_below = card.height() - block_bottom
    icon_text_gap = title.x() - (icon.x() + icon.width())
    block_right = title.x() + max(title.width(), desc.width())
    text_arrow_gap = arrow.x() - block_right
    arrow_right_inset = content_right - m_right - (arrow.x() + arrow.width())

    checks = []

    def chk(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    chk(
        "text block vertically centered",
        abs(gap_above - gap_below) <= 1,
        f"gap_above={gap_above:.1f} gap_below={gap_below:.1f} (card {card.width()}x{card.height()})",
    )
    chk(
        "icon vertically centered",
        abs(icon_c - card_c) <= 1,
        f"icon_c={icon_c:.1f} card_c={card_c:.1f}",
    )
    chk(
        "arrow vertically centered",
        abs(arrow_c - card_c) <= 1,
        f"arrow_c={arrow_c:.1f} card_c={card_c:.1f}",
    )
    chk(
        "text block on the same optical midline",
        abs(block_c - card_c) <= 1.5,
        f"block_c={block_c:.1f} card_c={card_c:.1f}",
    )
    chk(
        "title/desc left-aligned",
        abs(title.x() - desc.x()) <= 1,
        f"title.x={title.x()} desc.x={desc.x()}",
    )
    chk(
        "text block follows the icon (not centered horizontally)",
        title.x() > icon.x() + icon.width(),
        f"title.x={title.x()} vs icon right edge {icon.x() + icon.width()}",
    )
    chk(
        "arrow right-aligned (hugs the right inset)",
        arrow_right_inset == 0,
        f"inset from the content-area right margin={arrow_right_inset} "
        f"(layout right margin {m_right}, frame border accounted)",
    )
    chk(
        "equal icon→text / text→arrow spacing (±4)",
        abs(icon_text_gap - text_arrow_gap) <= 4,
        f"icon→text={icon_text_gap} text→arrow={text_arrow_gap} (layout spacing {lay.spacing()})",
    )

    # The same geometry for a REGULAR card — the whole grid reads uniformly.
    regular = cards[0]
    r_title = regular._title_label
    r_desc = regular._desc_label
    r_block_c = (r_title.y() + (r_desc.y() + r_desc.height())) / 2
    r_card_c = regular.height() / 2
    chk(
        "regular card text block also centered",
        abs(r_block_c - r_card_c) <= 1.5,
        f"block_c={r_block_c:.1f} card_c={r_card_c:.1f}",
    )

    cols = hv._grid_cols
    rows = (len(cards) + cols - 1) // cols
    chk(
        "3×3 grid preserved",
        cols == 3 and rows == 3 and len(cards) == 9,
        f"cols={cols} rows={rows} cards={len(cards)}",
    )

    print(f"\nFeatured card geometry: {card.width()}x{card.height()}")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    failures = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failures)}/{len(checks)} checks passed")
    win.close()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
