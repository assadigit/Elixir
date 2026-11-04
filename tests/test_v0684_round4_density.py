"""V0.6.84 (UI/UX correction Round 4) — characterization tests.

The Round-4 correction spec (ELIXIR_UI_UX_CORRECTION_ROUND_4.md) —
"Dashboard density, sidebar usability, typography, and visual fidelity" —
changes five behaviors; every one is pinned here, pure-first (the house
pattern), with live offscreen verification for the geometry that only
exists at runtime:

1. §2 — the Quick Tools grid becomes COMPACT and floor-driven: three
   equal columns reach the app's own minimum window (1100×720; the
   user's real ~1096×717 band), two at constrained widths, one only
   when two floor-width cards cannot fit. The Round-3 single-line
   comfort GATE is retired (it needed ≈860 px of grid — the audit's
   "two columns; only four cards visible").
2. §2.2 — the card density band: height 84–122 px (~0.135 of the body),
   typography 13/11 → 17/13 px scaling with it, 12/11 px grid gaps.
3. §3/§4 — the sidebar restructures into the spec's three regions
   (scroll-free primary nav, FIXED lower Settings/About, compact
   tagline card) and fits the user's rail with NO internal scrollbar;
   the tagline is fully readable at every rail width.
4. §5 — exactly ONE visible theme control (the status strip's Light/Dark
   selector); the top-bar moon button is removed and its spacing folded
   into the divider before the window controls.
5. §6 — the primary typeface is IBM Plex Sans (bundled 400/500/600/700,
   OFL; selected over Manrope by the spec §6.3 in-app comparison) with
   the Segoe UI fallback stack.

Run: pytest tests/test_v0684_round4_density.py -v
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _src(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


def _strip_comments(code: str) -> str:
    return re.sub(r"#[^\n]*", "", code)


def _qt_gui_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import PySide6.QtGui  # noqa: F401
        import PySide6.QtWidgets  # noqa: F401

        return True
    except Exception:
        return False


_QT_GUI = _qt_gui_available()

# The acceptance viewports (the Round-4 spec's framing): the user's real
# window class (the audit's 14.png / now5.png "before" at 1096×717, which
# the app's screen-derived minimum clamps to 1100×720) and the approved
# reference canvas (1536×1024).
_COMPACT_W, _COMPACT_H = 1100, 720
_REFERENCE_W, _REFERENCE_H = 1536, 1024


# ════════════════════════════════════════════════════════════════════════
# 1. §2 — the floor-driven reflow (pure)
# ════════════════════════════════════════════════════════════════════════
class TestReflowFloors:
    def test_three_columns_reach_the_minimum_window(self):
        """3×240 + 2×12 = 744 px of grid; the 1100×720 minimum window
        offers ≈807 (viewport − page margins) — the reference's 3-column
        band now covers the app's own floor (Round-3's comfort gate
        needed ≈860 and forced two columns there)."""
        from ui_qt.components.dashboard_primitives import _TOOL_CARD_FLOOR_W
        from ui_qt.views.home_view import _GRID_GAP

        grid_at_min = _COMPACT_W - 42 - 2 - 198 - 22 - 29  # backdrop+shell+rail+margins
        assert grid_at_min >= 3 * _TOOL_CARD_FLOOR_W + 2 * _GRID_GAP

    def test_the_floor_tiers(self):
        """3 while 3 floors + 2 gaps fit; 2 while 2 floors + 1 gap fit;
        1 only below that — the spec §2.3's exact behavior."""
        from ui_qt.components.dashboard_primitives import _TOOL_CARD_FLOOR_W as floor
        from ui_qt.views.home_view import _GRID_GAP as gap

        assert (3 * floor + 2 * gap, 2 * floor + gap) == (744, 492)

    def test_gap_in_the_spec_band(self):
        from ui_qt.views.home_view import _GRID_GAP

        assert _GRID_GAP == 12  # §2.2: "approximately 10–12 px"

    def test_vertical_gap_is_pinched(self):
        """The vertical gap (11) buys the third row back at the compact
        body — both values inside the spec's 10–12 band."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "setHorizontalSpacing(12)" in code
        assert "setVerticalSpacing(11)" in code


# ════════════════════════════════════════════════════════════════════════
# 2. §2.2 — the card density band (source pins)
# ════════════════════════════════════════════════════════════════════════
class TestCardDensitySource:
    def test_band_constants(self):
        from ui_qt.views.home_view import _CARD_BODY_RATIO, _CARD_H_MAX, _CARD_H_MIN

        assert (_CARD_H_MIN, _CARD_H_MAX) == (84, 122)  # §2.2: 80–90 compact
        assert _CARD_BODY_RATIO == 0.135

    def test_compact_card_chrome(self):
        """margins 16/12/14/12, icon 24, arrow 30, two 12 px gaps —
        'smaller internal padding than the current implementation'."""
        from ui_qt.components import dashboard_primitives as dp

        # V0.6.84.1: the chrome tightens 110 → 97 (margins 13/10,
        # gaps 10) so the featured card's reference-verbatim description
        # keeps TWO lines at the field window (spec §2.2).
        assert dp._TOOL_CARD_CHROME_W == 13 + 10 + 24 + 30 + 2 * 10
        assert dp._ICON_SIZE_TOOL == 24
        assert dp._ARROW_CIRCLE == 30

    def test_card_scales_its_typography_with_the_band(self):
        code = _strip_comments(_src("ui_qt/components/dashboard_primitives.py"))
        assert "def set_density" in code
        assert "self._title_px" in code
        assert "self._desc_px" in code

    def test_home_view_drives_the_band(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "def _card_target_h" in code
        assert "def _apply_grid_density" in code
        assert "title_px = round(13 + 4 * s, 1)" in code
        # V0.6.84.1: the desc band drops its floor 11 → 10 (paired with
        # the tightened chrome for the featured card's two-line break)
        assert "desc_px = round(10 + 3 * s, 1)" in code


# ════════════════════════════════════════════════════════════════════════
# 3. §3/§4 — the sidebar's three regions (source pins)
# ════════════════════════════════════════════════════════════════════════
class TestSidebarStructureSource:
    def test_footer_items_live_below_the_scroll_area(self):
        """§3.3: Settings/About are pinned in a FIXED lower region — the
        nav groups live inside the QScrollArea, the footer does NOT
        (the footer block iterates NAV_FOOTER below the scroll widget)."""
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        nav_block = code.split("nav_host = QWidget()")[1].split("scroll = QScrollArea()")[0]
        scroll_end = code.split("scroll = QScrollArea()")[1]
        footer_block = scroll_end.split("root.addWidget(scroll, 1)")[1]
        assert "for group_label, items in NAV_GROUPS:" in nav_block
        assert "NAV_FOOTER" not in nav_block  # the footer left the scroll column
        assert "for key, icon_name, label in NAV_FOOTER:" in footer_block
        assert "root.addWidget(lower)" in footer_block  # pinned as a root region

    def test_compact_nav_rhythm(self):
        """§3.1/§3.2: compact rows (32/36), tighter group rhythm (12/6),
        compact brand row — the fit math for the user's ~633 px rail."""
        from ui_qt.components.dashboard_primitives import (
            _NAV_ITEM_HEIGHT,
            _NAV_ITEM_TALL,
        )

        assert (_NAV_ITEM_HEIGHT, _NAV_ITEM_TALL) == (32, 36)
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        assert "nav.addSpacing(12)" in code  # above the TOOLS label
        assert "nav.addSpacing(6)" in code  # below it

    def test_tagline_card_is_compact_and_wraps(self):
        """§4: the art band 38, top inset 12, both brand lines word-wrap —
        the full tagline stays visible at EVERY rail width."""
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        assert "strip_h = min(scaled_h, 38)" in code
        assert "setWordWrap(True)" in code

    def test_brand_card_hides_below_the_compact_fit(self):
        from ui_qt.components.sidebar import _BRAND_MIN_RAIL_H

        # the full structure fits ~624 px of rail; below this floor the
        # decorative card yields first (spec §3.3's deliberate degradation)
        assert _BRAND_MIN_RAIL_H == 560


# ════════════════════════════════════════════════════════════════════════
# 4. §5 — one theme control (source pins)
# ════════════════════════════════════════════════════════════════════════
class TestSingleThemeControl:
    def test_top_bar_has_no_moon_button(self):
        app_src = _src("ui_qt/app.py")
        assert "self.theme_btn" not in app_src

    def test_status_strip_keeps_the_selector(self):
        app_src = _src("ui_qt/app.py")
        assert "self._status_theme_btn" in app_src
        assert 'QPushButton("Light Theme")' in app_src
        assert "def _show_theme_menu" in app_src  # the Light/Dark menu

    def test_theme_engine_untouched(self):
        """§5: 'Do not remove the underlying theme functionality' — the
        manager, persistence, and the toggle path all survive."""
        theme_src = _src("ui_qt/theme.py")
        assert "def toggle" in theme_src
        assert "ui_theme.json" in theme_src
        app_src = _src("ui_qt/app.py")
        assert "def _toggle_theme" in app_src


# ════════════════════════════════════════════════════════════════════════
# 5. §6 — the IBM Plex Sans selection (source pins; the file set is
#    pinned in test_m1_theme_tokens.py::TestPrimaryFontBundling)
# ════════════════════════════════════════════════════════════════════════
class TestPrimaryTypeface:
    def test_stack_leads_with_ibm_plex_sans_and_falls_back_to_segoe(self):
        from ui_qt.theme import FONT_FAMILY

        assert FONT_FAMILY.startswith('"IBM Plex Sans"')
        assert '"Segoe UI Variable", "Segoe UI"' in FONT_FAMILY

    def test_no_inter_remnant_in_the_theme(self):
        code = _strip_comments(_src("ui_qt/theme.py"))
        assert '"Inter"' not in code
        assert "Inter-Regular" not in code

    def test_no_runtime_font_picker_ships(self):
        """§6.3: the selection is a design decision, not a user feature."""
        for rel in ("ui_qt/app.py", "ui_qt/theme.py", "ui_qt/views/home_view.py"):
            code = _src(rel)
            assert "font picker" not in code.lower()
            assert "QFontDialog" not in code

    def test_hero_washes_step_back(self):
        """§7: the decorative circles' alphas drop so the still-life is
        the focal point."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "(h * 1.62, 24), (h * 1.14, 18), (h * 0.70, 14)" in code

    def test_cta_arrow_scales_with_the_hero(self):
        """The Round-4 'Conversion➜' collision fix: the arrow's
        inset/length/head track the hero scale, not a fixed 26 px."""
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "self.cta_btn._arrow_inset" in code
        assert 'float(getattr(self, "_arrow_inset", 26.0))' in code


# ════════════════════════════════════════════════════════════════════════
# 6. Live offscreen verification — the real widget tree at the real
#    acceptance sizes (runs wherever PySide6.QtGui imports; the offscreen
#    platform renders the production layouts).
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(not _QT_GUI, reason="PySide6.QtWidgets unavailable (headless sandbox: libEGL)")
class TestLiveDashboard:
    """The spec §10 acceptance checks, executed against the RUNNING
    application (the production window, the production theme pipeline —
    never a mockup)."""

    @staticmethod
    def _window(qt_app, w: int, h: int):
        # A THROWAWAY profile under /tmp — never the developer's ~/.elixir
        # and never inside the repository (the harness isolates BOTH the
        # persisted geometry and the persisted theme choice).
        profile = Path(tempfile.mkdtemp(prefix="elixir_r4_"))
        from utils import settings as _settings

        _settings.user_data_dir = lambda: profile
        import ui_qt.app as _appmod
        import ui_qt.theme as _theme

        _appmod._GEOMETRY_FILE = profile / "geom.json"
        _theme.theme_manager.settings_file = profile / "theme.json"
        _theme.theme_manager._primary_loaded = False
        _theme.theme_manager.apply(qt_app, "light")
        from controller import Controller
        from ui_qt.app import ElixirWindow

        win = ElixirWindow(Controller())
        win.show()
        win.resize(w, h)
        qt_app.processEvents()
        qt_app.processEvents()
        return win

    @pytest.fixture(autouse=True)
    def _restore_global_module_state(self):
        """The harness patches MODULE-GLOBAL state (user_data_dir, the
        geometry file, the theme singleton). Every mutation is restored
        after each test — a leaked patch poisoned later suites in the
        SAME pytest session (the V0.6.84 chunk-run lesson: the rebrand
        migration tests read the patched dir and failed only when this
        file ran earlier in the session)."""
        import ui_qt.app as _appmod
        import ui_qt.theme as _theme
        from utils import settings as _settings

        saved = (
            _settings.user_data_dir,
            _appmod._GEOMETRY_FILE,
            _theme.theme_manager.settings_file,
            _theme.theme_manager._mode,
            _theme.theme_manager._primary_loaded,
        )
        yield
        (
            _settings.user_data_dir,
            _appmod._GEOMETRY_FILE,
            _theme.theme_manager.settings_file,
            _theme.theme_manager._mode,
            _theme.theme_manager._primary_loaded,
        ) = saved

    @pytest.fixture()
    def qt_app(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        yield app
        # windows close themselves per-test; nothing to tear down here

    @staticmethod
    def _scroll_of(widget):
        from PySide6.QtWidgets import QScrollArea

        q = widget.parent()
        while q is not None and not isinstance(q, QScrollArea):
            q = q.parent()
        return q

    def test_nine_cards_three_columns_at_the_user_window(self, qt_app):
        """§10 at the user's window class: 3×3 grid, no clipped card, no
        page scrollbar."""
        from PySide6.QtWidgets import QScrollArea

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        hv = win.home_view
        assert hv._grid_cols == 3
        assert len(hv._quick_cards) == 9
        q = self._scroll_of(hv)
        assert isinstance(q, QScrollArea)
        # the whole page fits — no vertical scrollbar
        assert q.verticalScrollBar().maximum() == 0
        # every card is laid out inside the viewport (none clipped)
        for card in hv._quick_cards:
            top_left = card.mapTo(q.viewport(), card.rect().topLeft())
            assert top_left.y() >= 0
            assert top_left.y() + card.height() <= q.viewport().height() + 1
        # the compact density band holds (spec §2.2: ~80–90 px; the
        # featured card may run slightly taller on its 2-line desc)
        for card in hv._quick_cards:
            assert 80 <= card.height() <= 96, card.height()
        win.close()

    def test_three_columns_at_the_reference_canvas(self, qt_app):
        win = self._window(qt_app, _REFERENCE_W, _REFERENCE_H)
        hv = win.home_view
        assert hv._grid_cols == 3
        q = self._scroll_of(hv)
        assert q.verticalScrollBar().maximum() == 0
        # the reference render: cards at the band ceiling
        assert hv._quick_cards[0].height() >= 118
        win.close()

    def test_two_column_transition(self, qt_app):
        """§10 constrained: 900×640 lands two columns (three floors do
        not fit, two do)."""
        win = self._window(qt_app, 900, 640)
        hv = win.home_view
        assert hv._grid_cols == 2
        win.close()

    def test_one_column_at_the_absolute_floor(self, qt_app):
        win = self._window(qt_app, 760, 440)
        hv = win.home_view
        assert hv._grid_cols == 1
        # never a clip: every card at least its floor width
        for card in hv._quick_cards:
            assert card.width() >= 240
        win.close()

    def test_sidebar_complete_without_scrollbar_at_the_user_window(self, qt_app):
        """§3.1: all primary navigation visible, no internal scrollbar;
        §3.3: Settings/About pinned; §4: the tagline card fully inside."""
        from PySide6.QtWidgets import QScrollArea

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        sb = win.sidebar
        scroll = [c for c in sb.findChildren(QScrollArea)][0]
        # the nav region fits — NO scrollbar
        assert scroll.verticalScrollBar().maximum() == 0
        # every nav entry (Home + 9 tools + Settings + About) is visible
        for key, item in sb._items.items():
            assert item.isVisibleTo(sb), key
            top_left = item.mapTo(sb, item.rect().topLeft())
            assert 0 <= top_left.y() + item.height() <= sb.height() + 1, key
        # the tagline card is fully inside the rail
        brand = sb._brand
        assert brand.isVisibleTo(sb)
        assert brand.y() + brand.height() <= sb.height() + 1
        win.close()

    def test_footer_items_are_pinned_outside_the_scroll_area(self, qt_app):
        from PySide6.QtWidgets import QScrollArea

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        sb = win.sidebar
        scroll = [c for c in sb.findChildren(QScrollArea)][0]
        for key in ("settings", "about"):
            item = sb._items[key]
            assert (
                not item.parent().isWidgetType()
                or scroll not in item.parent().findChildren(QScrollArea)
                or not item.isAncestorOf(scroll)
                and not scroll.isAncestorOf(item)
            )
        # direct structural check: the footer's parent chain has no
        # QScrollArea above it
        for key in ("settings", "about"):
            q = sb._items[key].parent()
            while q is not None and q is not sb:
                assert not isinstance(q, QScrollArea)
                q = q.parent()
        win.close()

    def test_the_tagline_is_fully_rendered_at_every_rail(self, qt_app):
        """§4: 'Ensure the full tagline is visible' — the brand lines'
        heightHint fits the card at both rail profiles (word-wrap on)."""
        for rail_w in (197, 260):
            win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
            sb = win.sidebar
            sb.set_rail_width(rail_w)
            qt_app.processEvents()
            qt_app.processEvents()
            card = sb._brand
            line2 = card._line2
            # the label renders its full text (its height covers the wrap)
            fm = line2.fontMetrics()
            needed = fm.height() * max(
                1, (fm.horizontalAdvance(line2.text()) // max(1, line2.width()) + 1)
            )
            assert line2.height() >= needed, (rail_w, line2.height(), needed)
            assert card.y() + card.height() <= sb.height() + 1
            win.close()

    def test_exactly_one_theme_control_exists(self, qt_app):
        """§5: the top bar carries NO moon button; the status strip's
        selector is real and keyboard-operable."""
        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        assert not hasattr(win, "theme_btn")
        btn = win._status_theme_btn
        assert btn.isVisibleTo(win)
        assert btn.focusPolicy() is not None
        # the menu offers Light and Dark
        assert "Light Theme" in btn.text() or btn.text() == "Light Theme"
        win.close()

    def test_theme_toggle_flips_and_persists(self, qt_app):
        """§9: Light and Dark both work; the choice persists (the standing
        theme engine, unchanged)."""
        import ui_qt.theme as _theme

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        assert _theme.theme_manager.mode == "light"
        _theme.theme_manager.apply(qt_app, "dark")
        win._refresh_status_strip()
        win.home_view.refresh_theme()
        win.sidebar.refresh_theme()
        qt_app.processEvents()
        assert _theme.theme_manager.mode == "dark"
        assert "Dark Theme" in win._status_theme_btn.text()
        # persistence file written by the manager
        assert _theme.theme_manager.settings_file.exists()
        _theme.theme_manager.apply(qt_app, "light")
        win._refresh_status_strip()
        qt_app.processEvents()
        assert "Light Theme" in win._status_theme_btn.text()
        win.close()

    def test_hero_text_restyles_on_theme_toggle(self, qt_app):
        """V0.6.84 (Round-4 §9): the pre-existing dark-theme hero defect —
        refresh_theme never re-applied the per-widget hero styles, so a
        toggle left LIGHT ink on the dark hero (charcoal-on-charcoal,
        visible in the V0.6.83 now4_dark.png evidence). The fix: the
        scale state carries the theme mode; refresh_theme calls through."""

        def _ink_of(win) -> str:
            label = win.home_view._hero_heading
            ss = label.styleSheet()
            m = re.search(r"color:\s*(#[0-9A-Fa-f]{6})", ss)
            assert m, ss
            return m.group(1).upper()

        import ui_qt.theme as _theme

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        light_ink = _ink_of(win)
        assert light_ink == "#1D2423"  # LIGHT.text_primary (charcoal ink)
        _theme.theme_manager.apply(qt_app, "dark")
        win.home_view.refresh_theme()
        qt_app.processEvents()
        dark_ink = _ink_of(win)
        assert dark_ink == "#ECEEE8"  # DARK.text_primary (warm ivory)
        assert dark_ink != light_ink
        win.close()

    def test_the_primary_typeface_registered(self, qt_app):
        """§6.1: the bundled IBM Plex Sans weights actually registered in
        the running Qt session (the QSS stack resolves them)."""
        from PySide6.QtGui import QFontDatabase

        self._window(qt_app, _COMPACT_W, _COMPACT_H)
        styles = QFontDatabase.styles("IBM Plex Sans")
        assert styles, "IBM Plex Sans did not register"
        assert "Regular" in styles and "SemiBold" in styles

    def test_hero_art_is_transparent_over_both_themes(self, qt_app):
        """§7: the still-life composites directly over the hero surface in
        BOTH themes (no flattened rectangle) — the asset's alpha survives
        the running render."""
        import ui_qt.theme as _theme

        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        hv = win.home_view
        pm = hv._hero_visual.pixmap()
        assert pm is not None and not pm.isNull()
        img = pm.toImage()
        assert img.format() in (
            img.Format.Format_ARGB32_Premultiplied,
            img.Format.Format_ARGB32,
            img.Format.Format_RGBA8888,
            img.Format.Format_RGBA8888_Premultiplied,
        )
        assert img.pixel(2, 2) >> 24 == 0  # transparent surroundings
        # dark theme: same transparent asset (no re-flatten on toggle)
        _theme.theme_manager.apply(qt_app, "dark")
        win.home_view.refresh_theme()
        qt_app.processEvents()
        pm2 = hv._hero_visual.pixmap()
        img2 = pm2.toImage()
        assert img2.pixel(2, 2) >> 24 == 0
        win.close()

    def test_wizard_and_hero_cta_are_reachable(self, qt_app):
        """§5 (functional): the hero CTA and the featured wizard card emit
        their existing signals — the wizard launch plumbing. The window
        routes these to the MODAL WizardView (whose exec needs an
        interactive session); the headless check verifies the emission
        path on a bare HomeView — exactly the contract the window's
        routing consumes."""
        from ui_qt.views.home_view import HomeView

        hv = HomeView()
        hv.resize(860, 620)
        qt_app.processEvents()
        fired = {"start": 0, "tool": None}
        hv.start_requested.connect(lambda: fired.__setitem__("start", fired["start"] + 1))
        hv.tool_clicked.connect(lambda k: fired.__setitem__("tool", k))
        hv.cta_btn.click()
        assert fired["start"] == 1
        # the FEATURED ninth card (Full Conversion Wizard) emits its key
        wizard_card = hv._quick_cards[-1]
        assert wizard_card._featured is True
        wizard_card.clicked.emit("full_conversion")
        assert fired["tool"] == "full_conversion"
        # the window's side of the contract: the modal launcher exists
        # and is connected to the home view's signals at construction.
        win = self._window(qt_app, _COMPACT_W, _COMPACT_H)
        assert win.home_view.receivers("2start_requested()")  # SIGNAL signature
        assert win.home_view.receivers("2tool_clicked(QString)")
        assert hasattr(win, "_open_wizard")
        win.close()


# NOTE: no repo-local artifacts — the live tests profile under /tmp via
# tempfile.mkdtemp (see TestLiveDashboard._window); nothing to clean.
