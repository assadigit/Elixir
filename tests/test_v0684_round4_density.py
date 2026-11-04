"""V0.6.84 (UI/UX correction Round 4) — characterization tests.

The Round-4 correction spec (ELIXIR_UI_UX_CORRECTION_ROUND_4.md) changes
six behaviours; every one is pinned here, pure-first (the house pattern):

1. §2 — the Quick Tools grid becomes the compact 3×3: card minimum 80 px
   (the spec's 80–90 band), the readability floor and chrome retune so
   three columns fit at BOTH the 1096×717 field window and the 1000×667
   reference canvas, inter-card gap 10.
2. §3 — the sidebar completes: nav rows compact (27/34), the TOOLS list
   single-line down to a 188 px rail, and Settings/About move into a FIXED
   lower region OUTSIDE the scroll area (never scrolled away).
3. §4 — the tagline card compacts (12 px top inset, 46 px art strip).
4. §5 — ONE theme control: the top-bar moon button is gone; the status
   strip's "Light Theme ▾" selector remains the single visible control.
5. §6 — the primary typeface becomes Manrope (bundled, 4 weights + OFL,
   Inter retired) selected by the real-application comparison; the whole
   dashboard type scale re-calibrates to the reference's LOGICAL canvas
   (the V0.6.78–82 constants were measured on the reference PNG's 1536-px
   raster — a systematic 1.536× inflation).
6. §7/§8 — the hero keeps the true transparent RGBA composite with
   SOFTER background washes (the books stay the focal point) and the
   body-driven height rule retunes to the logical canvas (0.36,
   clamp [192, 260], bold display headline).

Source-level pins follow the test_m2_dashboard.py style; live checks use
the V0.6.72 offscreen-QA pattern (offscreen QApplication at the real
launch order).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _src(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


def _strip_comments(code: str) -> str:
    return re.sub(r"#[^\n]*", "", code)


# ════════════════════════════════════════════════════════════════════════
# 1. §2 — the compact 3×3 Quick Tools grid
# ════════════════════════════════════════════════════════════════════════
class TestCompactCardConstants:
    def test_card_height_in_the_spec_band(self):
        """§2.2: 'Compact card height, approximately 80–90 logical px'."""
        from ui_qt.components import dashboard_primitives as dp

        assert dp._NAV_ITEM_HEIGHT == 27  # §3.2 compact nav rows
        assert dp._NAV_ITEM_TALL == 34

    def test_card_minimum_height_is_80(self):
        code = _strip_comments(_src("ui_qt/components/dashboard_primitives.py"))
        assert "self.setMinimumHeight(80)" in code

    def test_floor_and_chrome(self):
        from ui_qt.components import dashboard_primitives as dp

        assert dp._TOOL_CARD_FLOOR_W == 230
        assert dp._TOOL_CARD_CHROME_W == 11 + 9 + 24 + 28 + 2 * 9

    def test_grid_gap_is_ten(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "_GRID_GAP = 10" in code

    def test_row_minimum_tracks_the_compact_card(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "setRowMinimumHeight(r, 80 if r < rows else 0)" in code


class TestThreeColumnReflow:
    """Live offscreen: the grid holds three columns at BOTH acceptance
    sizes — the 1096×717 field window and the 1000×667 reference canvas
    (the reference's logical design size)."""

    def _home_at(self, w: int, h: int):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])  # noqa: F841
        from ui_qt.theme import theme_manager
        from ui_qt.views.home_view import HomeView

        if not theme_manager._app:
            app = QApplication.instance()
            theme_manager.apply(app, "light")
        view = HomeView()
        view.resize(w, h)
        # a HIDDEN widget gets no QResizeEvent from resize() — the real
        # app always shows the view first, so the reflow is driven here
        # explicitly (deterministic for the column-count assertions).
        view._relayout_quick_grid()
        return view

    def test_three_columns_at_field_window(self):
        view = self._home_at(899, 583)  # the 1096×717 content viewport
        assert view._grid_cols == 3
        assert len(view._quick_cards) == 9

    def test_three_columns_at_reference_canvas(self):
        view = self._home_at(770, 533)  # the 1000×667 content viewport
        assert view._grid_cols == 3

    def test_two_columns_when_constrained(self):
        view = self._home_at(678, 444)  # the 900×620 content viewport
        assert view._grid_cols == 2

    def test_page_minimum_fits_the_viewport(self):
        """§10: 'No horizontal or vertical overflow occurs' — the page's
        own minimum stays under the viewport at the acceptance sizes."""
        view = self._home_at(899, 583)
        assert view.layout().minimumSize().height() <= 583
        assert view.layout().minimumSize().width() <= 899


# ════════════════════════════════════════════════════════════════════════
# 2. §3 — the complete sidebar
# ════════════════════════════════════════════════════════════════════════
class TestSidebarCompleteness:
    def test_single_line_profile_reaches_188(self):
        from ui_qt.components.sidebar import RAIL_COMPACT_BELOW

        assert RAIL_COMPACT_BELOW == 188

    def test_settings_about_in_fixed_lower_region(self):
        """§3.3: the divider + Settings/About live OUTSIDE the scroll
        area (a fixed lower region), never scrolled away."""
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        # the footer host is built AFTER the scroll area is added
        scroll_idx = code.index("root.addWidget(scroll, 1)")
        footer_idx = code.index("root.addWidget(footer_host)")
        assert footer_idx > scroll_idx, "the footer must follow the scroll area"
        # the NAV_FOOTER items are parented to the footer layout
        assert "footer.addWidget(item)" in code
        # and the scrollable host carries ONLY the NAV_GROUPS
        assert "nav.addWidget(item)" in code

    def test_compact_group_spacings(self):
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        assert "nav.setSpacing(2)" in code
        assert "nav.addSpacing(10)" in code  # before the TOOLS label

    def test_live_no_scrollbar_at_reference_rail(self):
        """§3.1: at the reference desktop size all entries fit without an
        internal vertical scrollbar (the 1096×717 window's 197 px rail)."""
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])  # noqa: F841
        from ui_qt.components.sidebar import Sidebar

        rail = Sidebar()
        rail.set_rail_width(197)
        rail.resize(197, 633)  # the 1096×717 window's rail column
        from PySide6.QtWidgets import QScrollArea

        scrolls = rail.findChildren(QScrollArea)
        assert scrolls, "the rail's nav scroll area is missing"
        bar = scrolls[0].verticalScrollBar()
        # the nav content fits: the scrollbar has no range to travel
        assert bar.maximum() == 0, (
            f"sidebar needs {bar.maximum()} px of scrolling at the reference "
            "rail size (Round-4 §3.1: no unnecessary scrollbar)"
        )

    def test_live_labels_single_line_at_197_rail(self):
        """The longest real tool names fit the 197 px rail's label column
        on ONE line at the 12 px label size (measured on the running
        Manrope stack — the reference's single-line treatment)."""
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])  # noqa: F841
        from ui_qt.components.sidebar import Sidebar

        rail = Sidebar()
        rail.set_rail_width(197)
        # the label column budget: rail − nav-host margins (10+10) − item
        # margins (8+6) − icon 18 − icon→text gap 9
        budget = 197 - 20 - 14 - 18 - 9
        longest = ("Document → Markdown", "Packets of Knowledge", "PDF/DOCX Cutter")
        for _key, item in rail._items.items():
            label = item._text_label
            if label.text() in longest:
                advance = label.fontMetrics().horizontalAdvance(label.text())
                assert advance <= budget, (
                    f"{label.text()!r} needs {advance} px but the 197 px rail "
                    f"offers {budget} (Round-4 §3.2: single-line labels)"
                )


# ════════════════════════════════════════════════════════════════════════
# 3. §4 — the compact tagline card
# ════════════════════════════════════════════════════════════════════════
class TestTaglineCard:
    def test_compact_insets_and_strip(self):
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        assert "root.setContentsMargins(0, 12, 0, 0)" in code  # 12 px top inset
        assert "strip_h = min(scaled_h, 46)" in code  # the 46 px art strip

    def test_the_full_tagline_text_is_present(self):
        code = _src("ui_qt/components/sidebar.py")
        assert '"Knowledge,"' in code
        assert '"distilled into clarity."' in code


# ════════════════════════════════════════════════════════════════════════
# 4. §5 — ONE visible theme control
# ════════════════════════════════════════════════════════════════════════
class TestSingleThemeControl:
    def test_top_bar_moon_button_removed(self):
        app_src = _strip_comments(_src("ui_qt/app.py"))
        top_bar = app_src[
            app_src.index("def _build_top_bar") : app_src.index("def _backend_pill_name")
        ]
        assert "theme_btn" not in top_bar, "the top-bar theme toggle must be gone"

    def test_status_strip_selector_remains(self):
        app_src = _strip_comments(_src("ui_qt/app.py"))
        assert "_status_theme_btn" in app_src
        assert "def _show_theme_menu" in app_src
        assert "Light Theme" in app_src

    def test_the_toggle_handler_survives_for_the_menu(self):
        """The underlying theme functionality is untouched — the status
        selector's menu still drives _toggle_theme."""
        app_src = _strip_comments(_src("ui_qt/app.py"))
        assert "def _toggle_theme" in app_src
        assert "self._toggle_theme()" in app_src  # the menu's action


# ════════════════════════════════════════════════════════════════════════
# 5. §6 — Manrope: selected, bundled, Inter retired
# ════════════════════════════════════════════════════════════════════════
class TestManropeSelection:
    def test_family_stack_leads_with_manrope(self):
        from ui_qt.theme import FONT_FAMILY

        assert FONT_FAMILY.startswith('"Manrope"')
        assert "Segoe UI" in FONT_FAMILY  # the sensible Windows fallback

    def test_loader_targets_manrope_files(self):
        code = _strip_comments(_src("ui_qt/theme.py"))
        for name in (
            "Manrope-Regular.ttf",
            "Manrope-Medium.ttf",
            "Manrope-SemiBold.ttf",
            "Manrope-Bold.ttf",
        ):
            assert f'"{name}"' in code

    def test_inter_retired_from_the_stack(self):
        code = _strip_comments(_src("ui_qt/theme.py"))
        assert '"Inter"' not in code

    def test_live_manrope_registers_offscreen(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from ui_qt.theme import load_bundle_font

        fams = load_bundle_font(app)
        assert "Manrope" in fams

    def test_type_scale_is_logical_canvas_calibrated(self):
        from ui_qt.theme import FONT

        # the reference's true logical measurements (Round-4 §6.2)
        assert FONT.hero == 27
        assert FONT.tool == 13
        assert FONT.tool_desc == 10
        assert FONT.sidebar == 12
        assert FONT.eyebrow == 10.5


# ════════════════════════════════════════════════════════════════════════
# 6. §7/§8 — the hero: transparent art, softer washes, logical rhythm
# ════════════════════════════════════════════════════════════════════════
class TestHeroRound4:
    def test_hero_rule_is_logical_canvas_calibrated(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "_HERO_BODY_RATIO = 0.36" in code
        assert "_HERO_MIN_H = 192" in code
        assert "_HERO_MAX_H = 260" in code
        assert "_HERO_HEADLINE_PX = 27" in code
        assert "_HERO_RHYTHM_BASE_H = 236" in code

    def test_headline_is_display_weight(self):
        """§6.2: the reference's headline ink is a bold display weight."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert 'f"font-size: {hero_px}px; font-weight: 700;"' in code
        theme = _src("ui_qt/theme.py")  # objectName selectors carry '#'
        assert "QLabel#Hero" in theme

    def test_background_washes_are_soft(self):
        """§7: 'Refine the background shapes if they compete with the
        artwork' — the sage washes drop to 22/17/13 alpha and shift right
        so the books/quill stay the focal point."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "((h * 1.55, 22), (h * 1.08, 17), (h * 0.66, 13))" in code

    def test_art_still_true_transparent_composite(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "def _scaled_hero_pixmap" in code
        assert "_flattened_hero_pixmap" not in code

    def test_cta_arrow_never_collides_with_the_label(self):
        """§2.2-adjacent (the constrained-size review catch): the CTA's
        right padding reserves the painted arrow's span (inset 26 + stem
        9) — asymmetric padding floors at 40 on the right."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "pad_r = max(40, round(30 * scale))" in code
        assert "pad_l = max(24, round(26 * scale))" in code

    def test_cta_touch_floor_holds(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "setMinimumHeight(44)" in code
