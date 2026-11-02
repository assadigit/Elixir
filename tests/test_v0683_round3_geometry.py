"""V0.6.83 (UI/UX correction Round 3) — characterization tests.

The Round-3 correction spec (ELIXIR_UI_UX_CORRECTION_ROUND_3.md) changes
four behaviors; every one is pinned here, pure-first (the house pattern):

1. §2.1 — the first-run window target moves to 1440×900
   (``target_default_size``), keeping the V0.6.81 ~92% rule on smaller
   work areas.
2. §2.2 — the window minimum becomes screen-derived
   (``minimum_window_size``: the 1100×720 band where supported, ~96% of
   the work area below that, 760×440 absolute floor) and implausibly
   small RESTORED geometries clamp up to it (``min_wh`` in
   ``sanitize_restore_plan``).
3. §3.1 — the sidebar rail becomes responsive,
   ``clamp(180, 0.18 * window_width, 260)``, applied via
   ``ElixirWindow._update_sidebar_rail`` → ``Sidebar.set_rail_width``
   (Qt-layout-driven; the compact profile swaps below RAIL_COMPACT_BELOW).
4. §4/§5/§6 — the Quick Tools reflow becomes tiered (measured comfort /
   readability floor), the hero height becomes body-driven (~0.325 of the
   viewport) with a scalable text rhythm, and the hero still-life renders
   as a TRUE transparent RGBA pixmap (no flattened rectangle).

Source-level pins follow the M2 test_m2_dashboard.py style; the pure
geometry pins follow test_v0667_window_visibility.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import utils.geometry as geom  # noqa: E402

_SCREEN = [(0, 0, 1920, 1040)]  # the V0.6.67 house screen fixture


def _src(rel: str) -> str:
    return (_project_root / rel).read_text(encoding="utf-8")


def _strip_comments(code: str) -> str:
    return re.sub(r"#[^\n]*", "", code)


# ════════════════════════════════════════════════════════════════════════
# 1. §2.1 — the first-run target (pure)
# ════════════════════════════════════════════════════════════════════════
class TestTargetDefaultSize:
    def test_band(self):
        assert (geom.TARGET_W, geom.TARGET_H) == (1440, 900)

    def test_large_work_area_gets_the_target(self):
        assert geom.target_default_size(1920, 1040) == (1440, 900)
        assert geom.target_default_size(1536, 1024) == (1440, 900)

    def test_exactly_the_target_is_not_comfortable(self):
        # 1440×900 of work area leaves zero margin — the ~92% rule applies.
        assert geom.target_default_size(1440, 900) == (1325, 828)

    def test_small_work_area_keeps_the_v0681_rule(self):
        # 1366×768-class work area: 92%, floored at 760×540.
        assert geom.target_default_size(1366, 728) == (1257, 670)

    def test_garbage_falls_back_to_the_module_default(self):
        for bad in (None, "x", -1, 0):
            assert geom.target_default_size(bad, 1920) == (geom.DEFAULT_W, geom.DEFAULT_H)
            assert geom.target_default_size(1920, bad) == (geom.DEFAULT_W, geom.DEFAULT_H)


# ════════════════════════════════════════════════════════════════════════
# 2. §2.2 — the screen-derived minimum (pure)
# ════════════════════════════════════════════════════════════════════════
class TestMinimumWindowSize:
    def test_band_constants(self):
        assert (geom.MIN_WIDE, geom.MIN_TALL) == (1100, 720)
        assert (geom.MIN_FLOOR_W, geom.MIN_FLOOR_H) == (760, 440)

    def test_large_work_area_gets_the_band_minimum(self):
        assert geom.minimum_window_size(1920, 1040) == (1100, 720)
        # a taskbar-sized 1366×728 work area: ~96% on the tight axis
        # (699) — "when the screen allows it" per §2.2.
        assert geom.minimum_window_size(1366, 768) == (1100, 720)
        assert geom.minimum_window_size(1366, 728) == (1100, 699)

    def test_small_work_area_scales_down(self):
        # ~96% of a 1024×600 work area — never above it, never below the floor.
        assert geom.minimum_window_size(1024, 600) == (983, 576)
        assert geom.minimum_window_size(1024, 600)[0] < 1024
        assert geom.minimum_window_size(1024, 600)[1] < 600

    def test_garbage_falls_back_to_the_absolute_floor(self):
        for bad in (None, "x", -5, 0):
            assert geom.minimum_window_size(bad, bad) == (760, 440)
            assert geom.minimum_window_size(1920, bad) == (760, 440)


class TestImplausiblySmallRestoreClamp:
    """Round-3 §2.1: never keep restoring an accidentally tiny geometry."""

    def test_now3_era_geometry_clamps_up(self):
        # the Round-3 audit's 893×609-class saved geometry (now3.png) can
        # never compose the dashboard — it clamps up with its position kept.
        plan = geom.sanitize_restore_plan(
            {"w": 893, "h": 609, "x": 10, "y": 10, "v": 2}, _SCREEN, min_wh=(1100, 720)
        )
        assert (plan["w"], plan["h"]) == (1100, 720)
        assert plan["move_to"] == (10, 10)

    def test_a_real_hand_resize_above_the_minimum_survives(self):
        plan = geom.sanitize_restore_plan(
            {"w": 1500, "h": 950, "x": 10, "y": 10, "v": 2}, _SCREEN, min_wh=(1100, 720)
        )
        assert (plan["w"], plan["h"]) == (1500, 950)

    def test_min_wh_none_keeps_the_legacy_behaviour(self):
        # the V0.6.67 pinned contract — no clamp when the caller passes none.
        plan = geom.sanitize_restore_plan({"w": 620, "h": 440, "x": 10, "y": 10}, _SCREEN)
        assert (plan["w"], plan["h"]) == (620, 440)

    def test_junk_min_wh_is_ignored_not_fatal(self):
        plan = geom.sanitize_restore_plan(
            {"w": 900, "h": 600, "x": 10, "y": 10}, _SCREEN, min_wh="junk"
        )
        assert (plan["w"], plan["h"]) == (900, 600)


# ════════════════════════════════════════════════════════════════════════
# 3. §3.1 — the responsive rail (source pins + live widget)
# ════════════════════════════════════════════════════════════════════════
class TestResponsiveRailSource:
    def test_window_owns_the_rule(self):
        code = _strip_comments(_src("ui_qt/app.py"))
        assert "def _update_sidebar_rail" in code
        assert "round(self.width() * 0.18)" in code
        assert "self._update_sidebar_rail()" in code

    def test_rail_bounds_and_profile(self):
        code = _strip_comments(_src("ui_qt/components/sidebar.py"))
        assert "RAIL_MIN, RAIL_MAX = 180, 260" in code
        assert "RAIL_COMPACT_BELOW = 232" in code
        assert "def set_rail_width" in code
        assert "def _apply_profile" in code

    def test_reference_rail_constant_untouched(self):
        # the M2 pin: SIDEBAR_WIDTH stays the documented reference rail.
        from ui_qt.components.sidebar import SIDEBAR_WIDTH

        assert SIDEBAR_WIDTH == 265


class TestResponsiveRailLive:
    """Live offscreen check of the clamp + compact switch (the V0.6.72
    QA pattern: offscreen QApplication at the real launch order)."""

    def test_clamp_and_compact(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])  # noqa: F841 — ensure a session exists
        from ui_qt.components.sidebar import RAIL_COMPACT_BELOW, Sidebar

        rail = Sidebar()
        # the WINDOW owns the formula (app._update_sidebar_rail); this
        # exercises the rail's application of the values it produces.
        for w, expect in (
            (1440, 259),
            (1280, 230),
            (1100, 198),
            (1000, 180),
            (700, 180),  # below the formula floor — 180 stays
            (2000, 260),  # the ceiling holds at very wide windows
        ):
            target = max(180, min(260, round(w * 0.18)))
            assert target == expect  # the formula matches the spec table
            rail.set_rail_width(target)
            assert rail.width() == expect, (w, rail.width(), expect)
        # the compact profile tracks the RAIL_COMPACT_BELOW switch exactly
        rail.set_rail_width(RAIL_COMPACT_BELOW)
        assert rail._compact is False
        rail.set_rail_width(RAIL_COMPACT_BELOW - 1)
        assert rail._compact is True
        rail.set_rail_width(198)
        assert rail._compact is True
        # the nav labels word-wrap (never clipped) — the item grows instead
        item = rail._items["pdf_to_markdown"]
        assert item._text_label.wordWrap() is True
        assert item.minimumHeight() >= 37


# ════════════════════════════════════════════════════════════════════════
# 4. §4/§5/§6 — reflow tiers, hero rhythm, transparent art (source pins)
# ════════════════════════════════════════════════════════════════════════
class TestQuickToolsTiersSource:
    def test_floor_and_chrome_constants(self):
        from ui_qt.components import dashboard_primitives as dp

        assert dp._TOOL_CARD_FLOOR_W == 272
        assert dp._TOOL_CARD_CHROME_W == 24 + 18 + 30 + 36 + 2 * 18

    def test_card_titles_wrap(self):
        code = _strip_comments(_src("ui_qt/components/dashboard_primitives.py"))
        assert "self._title_label.setWordWrap(True)" in code
        assert "self.setMinimumWidth(_TOOL_CARD_FLOOR_W)" in code

    def test_reflow_tier_decision(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "def _card_comfort_width" in code
        assert "grid_w >= 3 * comfort + 2 * _GRID_GAP" in code
        assert "grid_w >= 2 * floor + _GRID_GAP" in code


class TestHeroRound3Source:
    def test_body_driven_height_rule(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "_HERO_BODY_RATIO = 0.325" in code
        assert "_HERO_MIN_H = 240" in code
        assert "_HERO_MAX_H = 336" in code
        assert "def _hero_target_h" in code
        assert "def _body_height" in code

    def test_scalable_rhythm(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        # the spacers exist and are retuned by the scale pass
        assert "_hero_spacers" in code
        assert "item.changeSize" in code
        assert "setMinimumHeight(44)" in code  # the CTA touch floor

    def test_transparent_art_no_flatten(self):
        code = _strip_comments(_src("ui_qt/views/home_view.py"))
        assert "def _scaled_hero_pixmap" in code
        assert "_flattened_hero_pixmap" not in code  # the rectangle step is retired
        # §5.3: the art budget respects the text column FIRST
        assert "def _hero_text_need_w" in code

    def test_gap_in_band(self):
        # §6: hero→tools gap 24–32; 28 lands mid-band.
        code = _src("ui_qt/views/home_view.py")
        assert re.search(r"root\.addSpacing\(28\)", code)

    def test_chrome_heights_in_band(self):
        # §3.3/§6: header 44–52 (50), status strip 38–44 (42).
        app_src = _src("ui_qt/app.py")
        assert re.search(r"bar\.setFixedHeight\(50\)", app_src)
        assert re.search(r"strip\.setFixedHeight\(42\)", app_src)


class TestHeroAssetAlpha:
    """§5.2: the shipped asset really is isolated RGBA with transparent
    surroundings (this is why the direct composite has no rectangle)."""

    def test_asset_is_rgba_with_transparent_background(self):
        from PySide6.QtGui import QImage, QPixmap

        pm = QPixmap(str(_project_root / "assets" / "hero_books_quill.png"))
        assert not pm.isNull()
        img: QImage = pm.toImage()
        # corners are fully transparent; the ink is present
        assert img.pixel(2, 2) >> 24 == 0
        assert img.pixel(img.width() - 3, 2) >> 24 == 0
        assert img.pixel(2, img.height() - 3) >> 24 == 0
        found_ink = any(
            img.pixel(x, y) >> 24 > 200
            for y in range(0, img.height(), 8)
            for x in range(0, img.width(), 8)
        )
        assert found_ink, "the still-life foreground ink is missing"
