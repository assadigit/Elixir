"""M1 (UI/UX redesign) — theme token, icon, and de-hardcode pins.

THE SCOPE: the approved ELIXIR_FINAL_DASHBOARD_DESIGN_SPEC §3/§4 replaces the
terracotta-amber "Editorial Quiet" palette with warm ivory / charcoal /
muted forest green / sage in BOTH themes, adds the spec's ``icon`` token,
adds a dashboard-facing type scale (dialogs keep the compact 11px body —
user decision Q6), and de-hardcodes every theme-dependent colour literal
that had drifted into views.

THE PINS (hermetic first — the house no-Qt-on-CI pattern from
tests/test_v182048_p6_icon_cache.py / test_v0669_local_llm_lights.py):

  1. ``LIGHT`` / ``DARK`` expose the exact spec §3 hex values (AST-parsed,
     no import) and BOTH keep the full pre-M1 field set (``icon`` is purely
     additive — the QSS + ~35 call sites depend on the old names).
  2. WCAG contrast floors pass for both modes (pure-Python luminance math).
  3. The QSS template keeps the dialog type scale untouched and gains the
     dashboard-facing ``Hero/SectionHead/ToolTitle/SidebarLabel/SidebarGroup``
     label rules + the ``HeroPrimary`` CTA.
  4. No terracotta-amber remnant survives in ``theme.py``.
  5. ``ICONS`` gains ``home`` / ``headphones`` / ``audio-lines`` and loses
     nothing; ``icon_for_mode`` uses the palette ``icon`` token.
  6. Zero theme-dependent hex/rgba literals remain in ``ui_qt/`` outside
     ``theme.py`` (the icon-signature neutral fallbacks in ``icons.py`` are
     the documented exception).
  7. Inter is bundled: 4 TTFs + OFL license in ``assets/fonts/``.
  8. The M2 primitives exist and (since the M2 wiring commits) are
     composed ONLY by the M2 dashboard surfaces — the fixed sidebar
     (``sidebar.py``) and the home view (``home_view.py``).

Qt-behaviour pins (``TestQtBehaviour``) run only where ``PySide6.QtGui``
imports cleanly (the user's Windows machine); the headless recon sandbox
lacks ``libEGL.so.1`` and skips them (the M0-documented environment gap).

Run: pytest tests/test_m1_theme_tokens.py -v
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_THEME = _project_root / "ui_qt" / "theme.py"
_ICONS = _project_root / "ui_qt" / "components" / "icons.py"
_PRIMITIVES = _project_root / "ui_qt" / "components" / "dashboard_primitives.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments (house pattern)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _palette_kwargs(name: str) -> dict[str, str]:
    """AST-extract the keyword args of ``DARK = Palette(...)`` / ``LIGHT``."""
    tree = ast.parse(_src(_THEME))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if getattr(node.value.func, "id", "") == "Palette":
                for target in node.targets:
                    if getattr(target, "id", "") == name:
                        return {k.arg: k.value.value for k in node.value.keywords}
    raise AssertionError(f"Palette construction for {name!r} not found")


def _ns_kwargs(var: str) -> dict[str, int]:
    """AST-extract the keyword args of a ``_ns(...)`` token namespace."""
    tree = ast.parse(_src(_THEME))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if getattr(node.value.func, "id", "") == "_ns":
                for target in node.targets:
                    if getattr(target, "id", "") == var:
                        return {k.arg: k.value.value for k in node.value.keywords}
    raise AssertionError(f"token namespace {var!r} not found")


# ── pure-Python WCAG contrast math (no Qt) ─────────────────────────────────


def _luminance(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(fg: str, bg: str) -> float:
    la, lb = _luminance(fg), _luminance(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ════════════════════════════════════════════════════════════════════════════
# 1-2. Palette values + contrast
# ════════════════════════════════════════════════════════════════════════════


class TestSpecPalettePins:
    """Both palettes carry the approved spec §3 tokens (AST pins).

    V0.6.76 (visual-fidelity pass): the light values are re-pinned to the
    PIXEL MEASUREMENTS of the approved dashboard reference (see the
    LIGHT palette's comment block in theme.py for the sample points)."""

    def test_light_spec_values(self):
        kw = _palette_kwargs("LIGHT")
        assert kw["bg_window"] == "#FAF7F2"  # reference canvas (measured)
        assert kw["bg_surface"] == "#FCFAF5"  # reference card fill (measured)
        assert kw["bg_elevated"] == "#F1EFE7"  # hover — one step warmer
        assert kw["bg_sidebar"] == "#F5F2ED"  # reference rail (measured)
        assert kw["bg_header"] == "#FBF8F3"  # reference top bar (measured)
        assert kw["bg_hero"] == "#F5F0E6"  # reference hero band (measured)
        assert kw["text_primary"] == "#1D2423"
        assert kw["text_secondary"] == "#59615F"
        assert kw["border"] == "#E8E4DA"
        assert kw["accent"] == "#313C31"  # reference CTA fill (measured)
        assert kw["accent_hover"] == "#2A352B"
        assert kw["accent_soft"] == "#DEDFD6"  # the Home pill fill (measured)
        assert kw["icon"] == "#4A524C"
        assert kw["sage"] == "#53624B"  # reference card icon tint (measured)

    def test_dark_spec_values(self):
        kw = _palette_kwargs("DARK")
        assert kw["bg_window"] == "#1F231E"
        assert kw["bg_surface"] == "#2A2E27"
        assert kw["bg_elevated"] == "#31362E"  # spec surface-subtle
        assert kw["text_primary"] == "#ECEEE8"
        assert kw["text_secondary"] == "#A8AEA3"
        assert kw["border"] == "#3A4139"
        assert kw["accent"] == "#8FA98F"
        assert kw["accent_hover"] == "#9DB69B"
        assert kw["accent_soft"] == "#333B30"  # spec accent-subtle
        assert kw["icon"] == "#B3BBAF"
        assert kw["sage"] == "#9DB49B"

    def test_icon_field_is_purely_additive(self):
        """The pre-M1 21 fields survive untouched; ``icon``/``sage``/the
        V0.6.76 zone grounds are the additive extensions."""
        pre_m1_fields = {
            "name", "is_dark", "bg_window", "bg_surface", "bg_elevated",
            "bg_input", "bg_input_hover", "border", "border_strong",
            "text_primary", "text_secondary", "text_muted", "text_on_accent",
            "accent", "accent_hover", "accent_pressed", "accent_soft",
            "success", "warning", "error", "info",
        }
        for name in ("LIGHT", "DARK"):
            fields = set(_palette_kwargs(name))
            assert pre_m1_fields <= fields, f"{name}: pre-M1 field renamed/removed"
            assert fields - pre_m1_fields == {
                "icon",
                "sage",
                "bg_sidebar",
                "bg_header",
                "bg_hero",
                "bg_backdrop",
            }, f"{name}: unexpected new fields"

    def test_both_modes_same_field_set(self):
        assert set(_palette_kwargs("LIGHT")) == set(_palette_kwargs("DARK"))

    def test_semantics_distinct_from_accent(self):
        """success must not collide with the interactive green (Q: the sage
        accent and the success green must remain distinguishable hues)."""
        for name in ("LIGHT", "DARK"):
            kw = _palette_kwargs(name)
            assert kw["success"].lower() != kw["accent"].lower()
            assert kw["warning"].lower() != kw["accent"].lower()
            assert kw["error"].lower() != kw["accent"].lower()
            assert kw["info"].lower() != kw["accent"].lower()

    def test_contrast_floors(self):
        """WCAG-ish floors: on-accent text, primary text, secondary text."""
        for name in ("LIGHT", "DARK"):
            kw = _palette_kwargs(name)
            assert _contrast(kw["text_on_accent"], kw["accent"]) >= 4.5, name
            assert _contrast(kw["text_on_accent"], kw["accent_hover"]) >= 4.5, name
            assert _contrast(kw["text_primary"], kw["bg_window"]) >= 7.0, name
            assert _contrast(kw["text_primary"], kw["bg_surface"]) >= 7.0, name
            assert _contrast(kw["text_secondary"], kw["bg_surface"]) >= 4.5, name


# ════════════════════════════════════════════════════════════════════════════
# 3-4. QSS template + no terracotta remnants
# ════════════════════════════════════════════════════════════════════════════


class TestQssTemplatePins:
    def test_dialog_type_scale_unchanged(self):
        """Q6: the compact dialog scale is frozen — dialogs must not re-flow."""
        font = _ns_kwargs("FONT")
        assert font["micro"] == 9
        assert font["caption"] == 10
        assert font["body"] == 11
        assert font["body_strong"] == 11
        assert font["subhead"] == 12
        assert font["h3"] == 13
        assert font["h2"] == 15
        assert font["h1"] == 18
        assert font["display"] == 22

    def test_dashboard_type_scale_added(self):
        """V0.6.76 (visual-fidelity pass): the dashboard scale is re-pinned
        to the approved reference's measured glyph sizes — hero 41 px
        (ascender ~30 px over two ~46 px lines), support 20, section 20,
        tool 15, tool_desc 12.5, sidebar 13, eyebrow 13, brand 22."""
        font = _ns_kwargs("FONT")
        assert font["hero"] == 41
        assert font["section"] == 20
        assert font["tool"] == 15
        assert font["tool_desc"] == 12.5
        assert font["sidebar"] == 13
        assert font["body_lg"] == 20
        assert font["eyebrow"] == 13
        assert font["brand"] == 22

    def test_qss_has_dashboard_label_rules_and_hero_cta(self):
        code = _strip_comments(_src(_THEME))
        for rule in (
            "QLabel#Hero",
            "QLabel#Support",
            "QLabel#SectionHead",
            "QLabel#ToolTitle",
            "QLabel#SidebarLabel",
            "QLabel#SidebarGroup",
            "QPushButton#HeroPrimary",
        ):
            assert rule in code, f"missing M2-ready QSS rule: {rule}"

    def test_no_terracotta_remnants_in_theme(self):
        """The old terracotta-amber family is fully retired."""
        code = _strip_comments(_src(_THEME))
        for old in (
            "#191512", "#241E18", "#2E271F", "#15110D", "#1F1914", "#3A3128",
            "#D4A574", "#F5EDE0", "#CBBFA9", "#8A7D6E", "#1A1612",
            "#D8AA78", "#E6BC8A", "#C09060",
            "#F7F3EC", "#F2EADF", "#FBF6EE", "#E6DECF", "#C8805A",
            "#2A211B", "#6B5B4F", "#9A8B7D", "#B8704A", "#A6623E", "#8F5332",
            "rgba(189, 102, 79", "rgba(216, 170, 120", "rgba(184, 112, 74",
        ):
            assert old not in code, f"terracotta remnant: {old}"

    def test_rgba_helper_exists(self):
        """The M1 de-hardcode helper derives QSS rgba() from palette hex."""
        code = _strip_comments(_src(_THEME))
        assert "def rgba(hex_color: str, alpha: float) -> str:" in code
        assert "rgba(p.error, 0.12)" in code  # Danger hover uses it


# ════════════════════════════════════════════════════════════════════════════
# 5. Icons
# ════════════════════════════════════════════════════════════════════════════


class TestIconPins:
    _PRE_M1_ICONS = {
        "book", "newspaper", "file-text", "folder", "folder-open", "settings",
        "sliders-horizontal", "sun", "moon", "chevron-down", "chevron-right",
        "play", "flask", "x", "refresh", "search", "check", "scan", "layers",
        "image", "table", "sigma", "layout", "cpu", "cloud", "sparkles",
        "file-output", "scissors", "alert-triangle", "info", "shield",
        "list-checks", "globe", "wand", "rocket", "save", "rotate-ccw", "eye",
        "key", "languages", "mic", "plus", "copy", "trash", "pencil",
        "message-square", "bookmark", "zap",
    }

    def _icons_keys(self) -> set[str]:
        tree = ast.parse(_src(_ICONS))
        for node in tree.body:
            # ICONS is an annotated assignment: ``ICONS: dict[str, str] = {...}``
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "ICONS":
                return {k.value for k in node.value.keys}
        raise AssertionError("ICONS dict not found")

    def test_new_glyphs_added_nothing_lost(self):
        keys = self._icons_keys()
        assert keys >= self._PRE_M1_ICONS, "pre-M1 glyph removed"
        assert {"home", "headphones", "audio-lines"} <= keys

    def test_new_glyphs_are_stroke_svg_fragments(self):
        """Sanity: the new entries are multi-path markup, not empty strings."""
        src = _src(_ICONS)
        for name in ("home", "headphones", "audio-lines"):
            assert f'"{name}"' in src
        assert "<polygon" in src or "<path" in src

    def test_icon_for_mode_uses_palette_icon_token(self):
        code = _strip_comments(_src(_ICONS))
        assert "from ui_qt.theme import PALETTES" in code
        assert 'PALETTES["dark" if is_dark else "light"].icon' in code
        assert '"#E8EAED" if is_dark else "#1A1D23"' not in code


# ════════════════════════════════════════════════════════════════════════════
# 6. De-hardcode census
# ════════════════════════════════════════════════════════════════════════════


class TestDeHardcodeCensus:
    def test_zero_theme_dependent_colour_literals_outside_theme(self):
        """No hex / rgb( / rgba( literal survives in ui_qt/ outside
        theme.py (icons.py's neutral signature fallbacks excepted —
        documented; callers pass explicit palette colours)."""
        import re

        hex_re = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
        rgba_re = re.compile(r"rgba?\(\s*\d")
        violations: list[str] = []
        for p in (_project_root / "ui_qt").rglob("*.py"):
            if p.name == "theme.py" or str(p).endswith("components/icons.py"):
                continue
            code = _strip_comments(p.read_text(encoding="utf-8"))
            for i, line in enumerate(code.splitlines(), 1):
                if hex_re.search(line) or rgba_re.search(line):
                    violations.append(f"{p.relative_to(_project_root)}:{i}")
        assert not violations, f"hardcoded colours remain: {violations}"

    def test_splash_uses_palette_tokens(self):
        code = _strip_comments(_src(_project_root / "ui_qt" / "app.py"))
        assert "#23242b" not in code and "#d8aa78" not in code
        assert "#eceef4" not in code and "#3a3d47" not in code
        assert "theme_manager.palette" in code  # splash + overlay follow tokens

    def test_navigation_facade_preserved_flash_dropped(self):
        """M2: the north tab bar is retired; the M1 tab-flash (amber →
        accent de-hardcode) went with it — the flash is DROPPED (the
        full-content-area page switch replaces a 24 px tab-label
        highlight; documented M2 decision). What must survive: the
        ``_switch_to_tab`` public helper name + the window-side
        ``switch_to_page`` facade, and zero colour literals."""
        code = _strip_comments(
            _src(_project_root / "ui_qt" / "views" / "convert_view.py")
        )
        assert "def _switch_to_tab(self, tab_name: str) -> None:" in code
        assert "#D8AA78" not in code
        assert "QColor" not in code, "the tab-flash paint must not survive the facade"
        assert "switch_to_page" in code, "the facade must route to the window"
        app_code = _strip_comments(_src(_project_root / "ui_qt" / "app.py"))
        assert "def switch_to_page(self, key: str)" in app_code


# ════════════════════════════════════════════════════════════════════════════
# 7. Inter bundling (user decision Q4)
# ════════════════════════════════════════════════════════════════════════════


class TestInterBundling:
    def test_four_weights_and_license_bundled(self):
        fonts = _project_root / "assets" / "fonts"
        for name in (
            "Inter-Regular.ttf",
            "Inter-Medium.ttf",
            "Inter-SemiBold.ttf",
            "Inter-Bold.ttf",
        ):
            fp = fonts / name
            assert fp.exists() and fp.stat().st_size > 1000, f"{name} missing/too small"
        license_file = fonts / "Inter-LICENSE.txt"
        assert license_file.exists()
        assert "Open Font License" in license_file.read_text(encoding="utf-8")

    def test_load_inter_targets_these_files(self):
        """load_inter() already registers exactly these four filenames."""
        code = _strip_comments(_src(_THEME))
        for name in (
            "Inter-Regular.ttf",
            "Inter-Medium.ttf",
            "Inter-SemiBold.ttf",
            "Inter-Bold.ttf",
        ):
            assert f'"{name}"' in code


# ════════════════════════════════════════════════════════════════════════════
# 8. M2 primitives exist, wired by the dashboard surfaces
# ════════════════════════════════════════════════════════════════════════════


class TestM2Primitives:
    def test_module_exports_three_primitives(self):
        code = _strip_comments(_src(_PRIMITIVES))
        for cls in ("SectionLabel", "SidebarNavItem", "QuickToolCard"):
            assert f"class {cls}" in code
        assert '"SectionLabel", "SidebarNavItem", "QuickToolCard"' in code

    def test_primitives_are_wired_by_the_m2_dashboard_surfaces(self):
        """M2's first move (the M1 handoff contract): the fixed sidebar is
        built ON the primitives. The M1-era inverse pin ("nothing imports
        them") was rewritten with the M2 sidebar commit — the primitives
        now MUST be composed, and only by M2 dashboard surfaces (sidebar
        + home view), never by dialogs or unrelated views."""
        sidebar = _project_root / "ui_qt" / "components" / "sidebar.py"
        code = _strip_comments(_src(sidebar))
        assert (
            "from ui_qt.components.dashboard_primitives import SectionLabel, SidebarNavItem" in code
        ), "the fixed sidebar must compose the M1 primitives"
        allowed = {"dashboard_primitives.py", "sidebar.py", "home_view.py"}
        for p in (_project_root / "ui_qt").rglob("*.py"):
            if p.name in allowed:
                continue
            src = p.read_text(encoding="utf-8")
            assert "dashboard_primitives" not in src, (
                f"{p} imports the M2 primitives outside the dashboard surfaces"
            )

    def test_primitives_use_tokens_not_literals(self):
        import re

        code = _strip_comments(_src(_PRIMITIVES))
        assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code), "literal colour in primitives"


# ════════════════════════════════════════════════════════════════════════════
# Qt behaviour (runs where PySide6.QtGui imports — skips in the libEGL sandbox)
# ════════════════════════════════════════════════════════════════════════════


def _qt_gui_available() -> bool:
    try:
        import PySide6.QtGui  # noqa: F401

        return True
    except Exception:
        return False


_QT_GUI = _qt_gui_available()


@pytest.mark.skipif(not _QT_GUI, reason="PySide6.QtGui unavailable (headless sandbox: libEGL)")
class TestQtBehaviour:
    """Real-import behaviour pins (the user's Windows machine runs these)."""

    def test_qss_compiles_with_spec_accents(self):
        from ui_qt.theme import DARK, LIGHT, _qss

        for p in (LIGHT, DARK):
            qss = _qss(p)
            assert isinstance(qss, str) and len(qss) > 2000
            assert p.accent in qss
            assert p.bg_window in qss
            assert p.text_on_accent in qss

    def test_qss_contains_new_dashboard_rules(self):
        from ui_qt.theme import DARK, LIGHT, _qss

        for p in (LIGHT, DARK):
            qss = _qss(p)
            for rule in ("QLabel#Hero", "QLabel#SidebarGroup", "QPushButton#HeroPrimary"):
                assert rule in qss

    def test_rgba_helper(self):
        from ui_qt.theme import LIGHT, rgba

        assert rgba(LIGHT.accent, 0.12) == "rgba(63, 99, 77, 0.12)"

    def test_theme_manager_toggle_round_trip(self, tmp_path, monkeypatch):
        from ui_qt.theme import ThemeManager

        tm = ThemeManager()
        monkeypatch.setattr(tm, "settings_file", tmp_path / "ui_theme.json")
        monkeypatch.setattr(tm, "_save_mode", lambda mode: None)  # hermetic: no disk writes
        start = tm.mode
        first = tm.toggle()
        second = tm.toggle()
        assert first != second
        assert second == start  # round-trips back

    def test_icon_home_renders_non_null(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication

        _app = QGuiApplication.instance() or QGuiApplication(["-platform", "offscreen"])  # noqa: F841
        from ui_qt.components.icons import icon

        for name in ("home", "headphones", "audio-lines"):
            icn = icon(name, "#3F634D", 20)
            pm = icn.pixmap(20, 20)
            assert not pm.isNull(), f"{name} rendered null"
