"""Centralised theme system for the PySide6 UI — "Quiet Grove" (UI/UX redesign).

M1 of the approved UI/UX redesign.  Design language:
  - Warm ivory / charcoal neutrals (never pure black) + a single muted
    **forest-green** accent with sage support — paper, ink, and a quiet
    reading room (per ELIXIR_FINAL_DASHBOARD_DESIGN_SPEC §3).
  - **Inter** as the primary typeface — bundled in ``assets/fonts/`` since M1
    (4 static weights, OFL), falling back to the best Windows-native stack
    (Segoe UI Variable → Segoe UI).
  - A single source of truth: the ``SPACE`` / ``FONT`` / ``RADIUS`` / ``WEIGHT``
    token scales.  Views import these instead of hard-coding magic numbers so
    the whole app stays visually consistent.
  - Compact density for dialogs (4px spacing grid, 11px body, hairline
    borders, 5-8px radii — user decision Q6) plus a larger dashboard-facing
    type scale (``FONT.hero/section/tool/sidebar/body_lg``) for the M2
    hero / sidebar / quick-tool grid.

The ThemeManager owns the palette, generates the complete QSS for the active
mode (dark/light), persists the choice to
``~/.elixir/ui_theme.json``, loads any bundled Inter weights, and
applies everything to a QApplication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

# ─────────────────────────────────────────────────────────────────────────────
# Design tokens — the single source of truth for spacing / type / radius
# ─────────────────────────────────────────────────────────────────────────────


def _ns(**kw):
    return SimpleNamespace(**kw)


# 4px base spacing grid.  Import these in views:
#   from ui_qt.theme import SPACE
#   lay.setContentsMargins(*SPACE.lg_quad)   # (16,16,16,16)
#   lay.setSpacing(SPACE.sm)                 # 8
SPACE = _ns(
    zero=0,
    xs=3,  # hairline gaps
    sm=6,  # tight grouping
    md=8,  # default spacing
    lg=12,  # comfortable
    xl=16,  # roomy
    xxl=20,  # section gap (use sparingly)
    # convenience quads (left, top, right, bottom) — Qt margin order
    xs_quad=(3, 3, 3, 3),
    sm_quad=(6, 6, 6, 6),
    md_quad=(8, 8, 8, 8),
    lg_quad=(12, 12, 12, 12),
    xl_quad=(16, 16, 16, 16),
    # common page/content margins (h, v, h, v)
    page=(14, 10, 14, 6),  # top-level page padding (compact)
    card=(12, 10, 12, 10),  # inside a Card
    section=(12, 8, 12, 8),  # inside a step/section
)

# Font sizes (px).  Two scales, deliberately (user decision Q6):
#   • Dialog scale (unchanged, compact): Inter renders crisply at 11px;
#     Segoe UI fallback is fine too.  Wizard/settings/dialogs keep this.
#   • Dashboard scale (M1 additions, spec §4): hero/section/tool/sidebar/
#     body_lg feed the M2 hero, sidebar, and quick-tool grid.
FONT = _ns(
    micro=9,  # badges, counters — use rarely
    caption=10,  # hints, secondary captions
    body=11,  # default body text (dialogs)
    body_strong=11,
    subhead=12,  # small section labels
    h3=13,  # card titles, group headings
    h2=15,  # page titles
    h1=18,  # hero / dialog titles
    display=22,  # splash / numbers
    # ── M1 dashboard-facing additions (spec §4 ranges) ──────────────────
    # V0.6.76 (visual-fidelity pass): retuned to the PIXEL MEASUREMENTS of
    # the approved reference (1536×1024) — eyebrow cap ~11px, headline
    # ascender ~30px over two ~46px lines, support ~20px ascender 17px,
    # section heading cap ~16px, card titles ~15px, nav labels ~13px.
    eyebrow=13,  # hero eyebrow (tracked uppercase, reference cap ~11px)
    body_lg=20,  # dashboard body / hero support copy (reference ascender 17px)
    tool=15,  # quick-tool card titles (reference ~15px semibold)
    tool_desc=12.5,  # quick-tool card descriptions (reference ~12px)
    sidebar=13,  # sidebar nav labels, medium weight (reference ~13px)
    section=20,  # dashboard section headings ("Quick Tools", cap ~16px)
    hero=41,  # hero heading (reference ascender ~30px, 2×46px lines)
    brand=22,  # sidebar "Elixir" wordmark (reference band ~45px)
)

# Font weights (Inter ships these; Segoe UI maps 500/600→SemiBold reasonably)
WEIGHT = _ns(regular=400, medium=500, semibold=600, bold=700)

# Corner radii
RADIUS = _ns(xs=3, sm=5, md=6, lg=8, xl=10, nav=10, card=14, hero=16, shell=18)

# The deliberately theme-independent "code editor" surface (VS Code-like
# dark panel for live logs / script previews — dark in BOTH themes by
# design, so log text reads as terminal output, not app content).
# Centralised here (M1) so views carry zero hardcoded colours.
CODE_EDITOR = _ns(bg="#1E1E1E", text="#D4D4D4", border="#3C3C3C")

# The canonical font-family stack.  Inter first (if loaded), then the best
# Windows-native face, then cross-platform fallbacks.  Monospace for logs.
FONT_FAMILY = '"Inter", "Segoe UI Variable", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
FONT_FAMILY_MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", "Menlo", monospace'


# ─────────────────────────────────────────────────────────────────────────────
# Palette
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Palette:
    """A complete colour palette for one mode."""

    name: str
    is_dark: bool

    # surfaces
    bg_window: str  # outermost app background (the canvas right of the sidebar)
    bg_surface: str  # cards / panels
    bg_elevated: str  # hover / popups / raised elements
    bg_input: str  # line-edits, combos, text areas
    bg_input_hover: str
    # V0.6.76 (visual-fidelity pass): the reference's per-zone warm grounds —
    # the approved dashboard paints the sidebar, header strip, and hero in
    # three subtly different warm tones over the canvas.
    bg_sidebar: str  # the fixed nav rail
    bg_header: str  # the top bar + the bottom status strip
    bg_hero: str  # the hero panel's warm cream band
    bg_backdrop: str  # the desktop-like ground behind the floating shell

    # lines
    border: str  # hairline 1px
    border_strong: str  # focus / selected

    # text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str

    # accent (muted forest green — light mode; sage — dark mode)
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str  # subtle fill behind selected items (spec accent-subtle)
    icon: str  # default monochrome icon tint (spec `icon` token, M1)
    sage: str  # the reference's muted sage — card icons / decor / status dot

    # semantics (muted, not garish)
    success: str
    warning: str
    error: str
    info: str


# M1 (UI/UX redesign): the approved spec §3 dark palette — forest-tinted
# charcoal grounds, sage accent (brighter for dark-mode contrast), and the
# same ivory-first hierarchy as light mode (no global inversion).
DARK = Palette(
    name="dark",
    is_dark=True,
    bg_window="#1F231E",  # warm forest-tinted charcoal (spec background)
    bg_surface="#2A2E27",  # card surface (spec surface)
    bg_elevated="#31362E",  # hover / popups (spec surface-subtle)
    bg_input="#191D18",  # recessed input wells (darker than window)
    bg_input_hover="#232822",
    bg_sidebar="#242820",  # the rail — one step warmer than the canvas
    bg_header="#232720",  # the top bar / status strip
    bg_hero="#272B24",  # the hero's dusk band
    bg_backdrop="#161A15",  # the dimmed ground behind the shell
    border="#3A4139",  # sage-tinted hairline (spec border)
    border_strong="#5C6B5E",  # mid sage — focus / selected outlines
    text_primary="#ECEEE8",  # warm ivory (spec text-primary)
    text_secondary="#A8AEA3",  # sage-gray supporting text (spec text-secondary)
    text_muted="#7A8175",  # dim sage-gray
    text_on_accent="#1E231E",  # charcoal text on the sage accent
    accent="#8FA98F",  # muted sage green (spec accent)
    accent_hover="#9DB69B",  # spec accent-hover
    accent_pressed="#7E997C",  # derived: one step deeper than accent
    accent_soft="#333B30",  # quiet accent backgrounds (spec accent-subtle)
    icon="#B3BBAF",  # default icon tint (spec icon)
    sage="#9DB49B",  # card icons / status dot (light-mode #53624B's dark twin)
    success="#A9C178",  # yellow-leaning sage (distinct from the sage accent)
    warning="#D8BC66",  # warm gold
    error="#DC9484",  # warm terracotta-red
    info="#A294B8",  # muted mauve
)

# M1 (UI/UX redesign): the approved spec §3 light palette — warm ivory
# ground, white surfaces, deep forest-green accent, charcoal-olive text.
# V0.6.76 (visual-fidelity pass): every value re-measured against the
# approved dashboard reference PNG at 1536×1024 (canvas #FAF7F2 sampled at
# (500,700); sidebar #F5F2ED at (250,460); header #FBF8F3 at (800,60);
# hero #F5F0E6 at (500,300); cards #FCFAF5; the Home pill fill #DEDFD6;
# the CTA fill ~#313C31 averaged over its body; card icon strokes #53624B).
LIGHT = Palette(
    name="light",
    is_dark=False,
    bg_window="#FAF7F2",  # warm ivory canvas (reference main ground)
    bg_surface="#FCFAF5",  # near-white cream cards (reference card fill)
    bg_elevated="#F1EFE7",  # hover / popups (one step warmer than canvas)
    bg_input="#FFFFFF",  # white inputs (border-separated)
    bg_input_hover="#F7F8F3",  # barely-there green-tinted hover
    bg_sidebar="#F5F2ED",  # the rail's warm ivory (reference x∈[22,287])
    bg_header="#FBF8F3",  # the top bar / status strip cream
    bg_hero="#F5F0E6",  # the hero's warm cream band (reference fill)
    bg_backdrop="#EFECE5",  # the reference's desktop ground (warm grey)
    border="#E8E4DA",  # warm hairline (reference card borders)
    border_strong="#8FA08D",  # mid sage — focus / selected outlines
    text_primary="#1D2423",  # deep charcoal-ink (reference headline)
    text_secondary="#59615F",  # sage-gray supporting text
    text_muted="#9CA196",  # light sage-gray
    text_on_accent="#FFFFFF",  # white text on the deep forest accent
    accent="#313C31",  # deep forest (reference CTA fill, measured)
    accent_hover="#2A352B",  # one step deeper on hover
    accent_pressed="#242F25",  # pressed depth
    accent_soft="#DEDFD6",  # the Home pill's pale sage (measured fill)
    icon="#4A524C",  # dark sage-charcoal icons (reference nav strokes)
    sage="#53624B",  # card icons / status dot (reference card glyph tint)
    success="#6F9462",  # muted yellow-green sage (distinct from the forest accent)
    warning="#C99A3E",  # warm gold
    error="#BD664F",  # warm terracotta-red
    info="#7E6E94",  # muted mauve
)

PALETTES = {"dark": DARK, "light": LIGHT}


def rgba(hex_color: str, alpha: float) -> str:
    """Derive a QSS/HTML ``rgba()`` string from a palette hex token.

    M1 de-hardcode helper: views/banner styles that need a translucent wash
    of a SEMANTIC colour (success/error/warning/info tints, drop overlays)
    call this instead of hand-writing rgb triplets, so the tint always tracks
    the active palette.
    """
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha:g})"


# ─────────────────────────────────────────────────────────────────────────────
# Inter font loading
# ─────────────────────────────────────────────────────────────────────────────

_INTER_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "Inter-Bold.ttf",
)


def load_inter(app: QApplication) -> list[str]:
    """Register bundled Inter weights from ``assets/fonts/`` if present.

    Returns the list of family names that were successfully added (may be
    empty if the font files aren't installed yet — the stylesheet then
    transparently falls back to Segoe UI Variable / Segoe UI).
    """
    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    families: list[str] = []
    if not fonts_dir.is_dir():
        return families
    for name in _INTER_FILES:
        fp = fonts_dir / name
        if fp.exists() and fp.stat().st_size > 1000:
            fid = QFontDatabase.addApplicationFont(str(fp))
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                families.extend(fams)
    return families


# ─────────────────────────────────────────────────────────────────────────────
# QSS generation
# ─────────────────────────────────────────────────────────────────────────────


def _qss(p: Palette) -> str:
    """Build the complete application stylesheet for palette ``p``."""
    return f"""
    /* ════════════════════════════════════════════════════════════════════
       Global
       ════════════════════════════════════════════════════════════════════ */
    QWidget {{
        background-color: {p.bg_window};
        color: {p.text_primary};
        font-family: {FONT_FAMILY};
        font-size: {FONT.body}px;
    }}
    QWidget:disabled {{
        color: {p.text_muted};
    }}

    /* Tooltips — small, opaque, soft */
    QToolTip {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS.sm}px;
        padding: 4px 6px;
        font-size: {FONT.caption}px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Window & scroll-area backgrounds
       ════════════════════════════════════════════════════════════════════ */
    QMainWindow,
    QDialog {{
        background-color: {p.bg_window};
    }}
    QFrame#Card,
    QFrame#Surface {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS.lg}px;
    }}
    /* V0.6.75 (the reference comparison): the hero's own tinted container —
       the mockup's warm band sitting one step above the page ground. The
       hero illustration is flattened against THIS fill (home_view's
       _flattened_hero_pixmap — the two must stay in sync).
       V0.6.76 (visual-fidelity pass): the dedicated ``bg_hero`` token + the
       reference's ~16 px corner radius. */
    QFrame#HeroCard {{
        background-color: {p.bg_hero};
        border: 1px solid {p.border};
        border-radius: {RADIUS.hero}px;
    }}
    /* V0.6.76 (visual-fidelity pass): the unified floating application
       shell — the reference's softly elevated surface with rounded outer
       corners (18 px measured) living on a ~21 px backdrop margin. */
    QFrame#AppShell {{
        background-color: {p.bg_window};
        border: 1px solid {p.border};
        border-radius: {RADIUS.shell}px;
    }}
    QWidget#WindowBackdrop, QFrame#WindowBackdrop {{
        background-color: {p.bg_backdrop};
        border: none;
    }}
    /* The reference's Quick Tool cards — near-white cream, warm hairline,
       ~14 px radius, no shadow. */
    QFrame#QuickToolCard {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS.card}px;
    }}
    /* The ninth card — the deep forest feature card ("Full Conversion
       Wizard"), light type on the accent ground. */
    QFrame#FeatureToolCard {{
        background-color: {p.accent};
        border: 1px solid {p.accent};
        border-radius: {RADIUS.card}px;
        color: {p.text_on_accent};
    }}
    /* The persistent bottom status strip (reference ~56 px, full inner
       width, hairline top border, cream surface). It owns the shell's
       rounded BOTTOM corners (the sidebar owns the top-left, the header
       the top-right). */
    QFrame#StatusStrip {{
        background-color: {p.bg_header};
        border: none;
        border-top: 1px solid {p.border};
        border-bottom-left-radius: {RADIUS.shell}px;
        border-bottom-right-radius: {RADIUS.shell}px;
    }}
    /* Maximized: the floating shell goes edge-to-edge — square corners,
       no hairline (set via the dynamic property in ElixirWindow). */
    QFrame#AppShell[maximized="true"] {{
        border: none;
        border-radius: 0;
    }}
    QFrame#SidebarRail[maximized="true"] {{
        border-top-left-radius: 0;
    }}
    QFrame#TopBar[maximized="true"] {{
        border-top-left-radius: 0;
        border-top-right-radius: 0;
    }}
    QFrame#StatusStrip[maximized="true"] {{
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }}
    /* The top bar's labelled Settings action (gear + word). */
    QPushButton#TopBarAction {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: {RADIUS.sm}px;
        padding: 6px 10px;
        font-size: {FONT.sidebar}px; font-weight: {WEIGHT.medium};
        outline: none;
    }}
    QPushButton#TopBarAction:hover {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
    }}
    /* The reference's subtle vertical divider between the theme control
       and the window controls (also used by the status strip). */
    QFrame#VDivider {{
        background-color: {p.border};
        border: none;
        min-width: 1px; max-width: 1px;
    }}
    QFrame#SidebarBrandCard {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS.card}px;
    }}
    QFrame#StepBadge {{
        background-color: {p.accent};
        color: {p.text_on_accent};
        border-radius: 10px;
        min-width: 16px; min-height: 16px;
        max-width: 16px; max-height: 16px;
    }}
    QFrame#Divider {{
        background-color: {p.border};
        border: none;
        max-height: 1px; min-height: 1px;
    }}
    QFrame#TopBar {{
        background-color: {p.bg_header};
        border: none;
        border-top-left-radius: {RADIUS.shell}px;
        border-top-right-radius: {RADIUS.shell}px;
    }}
    /* M2 (UI/UX redesign): the fixed left nav rail — spec §5 "compact and
       fixed, always visible". V0.6.76 (visual-fidelity pass): the
       reference's warm ivory rail (``bg_sidebar``), hairline right edge,
       and the shell's rounded TOP-LEFT corner (the rail owns that corner
       of the floating shell; the status strip owns the bottom two). */
    QFrame#SidebarRail {{
        background-color: {p.bg_sidebar};
        border: none;
        border-right: 1px solid {p.border};
        border-top-left-radius: {RADIUS.shell}px;
    }}

    /* Scrollable content surfaces */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Labels — typographic hierarchy via object names
       ════════════════════════════════════════════════════════════════════ */
    QLabel {{
        background-color: transparent;
        color: {p.text_primary};
    }}
    QLabel#H1 {{ font-size: {FONT.h1}px; font-weight: {WEIGHT.semibold}; }}
    QLabel#H2 {{ font-size: {FONT.h2}px; font-weight: {WEIGHT.semibold}; }}
    QLabel#H3 {{ font-size: {FONT.h3}px; font-weight: {WEIGHT.semibold}; }}
    QLabel#Step {{
        font-size: {FONT.body}px; font-weight: {WEIGHT.semibold};
        letter-spacing: 0.2px; color: {p.text_primary};
    }}
    QLabel#Body {{ font-size: {FONT.body}px; font-weight: {WEIGHT.regular}; }}
    QLabel#Caption {{
        font-size: {FONT.caption}px; font-weight: {WEIGHT.regular};
        color: {p.text_muted};
    }}
    QLabel#Muted {{ color: {p.text_secondary}; }}
    QLabel#SectionTitle {{
        font-size: {FONT.caption}px; font-weight: {WEIGHT.semibold};
        color: {p.text_secondary};
        letter-spacing: 0.6px;
    }}
    QLabel#SelectionHint {{
        font-size: {FONT.caption}px; color: {p.accent}; font-weight: {WEIGHT.medium};
    }}

    /* M2-ready dashboard-facing labels (spec §4 type scale). V0.6.76
       (visual-fidelity pass): sizes retuned to the reference measurements
       — hero 41 px semibold, support 20 px, section 20 px, tool 15 px. */
    QLabel#Hero {{
        font-size: {FONT.hero}px; font-weight: {WEIGHT.semibold};
        color: {p.text_primary};
    }}
    QLabel#Eyebrow {{
        font-size: {FONT.eyebrow}px; font-weight: {WEIGHT.semibold};
        color: {p.sage};
        letter-spacing: 1.6px;
    }}
    QLabel#Support {{
        font-size: {FONT.body_lg}px; font-weight: {WEIGHT.regular};
        color: {p.text_secondary};
    }}
    QLabel#SectionHead {{
        font-size: {FONT.section}px; font-weight: {WEIGHT.semibold};
        color: {p.text_primary};
    }}
    QLabel#ToolTitle {{
        font-size: {FONT.tool}px; font-weight: {WEIGHT.medium};
        color: {p.text_primary};
    }}
    QLabel#ToolDesc {{
        font-size: {FONT.tool_desc}px; font-weight: {WEIGHT.regular};
        color: {p.text_muted};
    }}
    QLabel#SidebarLabel {{
        font-size: {FONT.sidebar}px; font-weight: {WEIGHT.medium};
        color: {p.text_secondary};
    }}
    QLabel#SidebarGroup {{
        font-size: {FONT.caption}px; font-weight: {WEIGHT.semibold};
        color: {p.text_muted};
        letter-spacing: 0.8px;
    }}
    QLabel#BrandWord {{
        font-size: {FONT.brand}px; font-weight: {WEIGHT.semibold};
        color: {p.text_primary};
        letter-spacing: 0.2px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Buttons
       ════════════════════════════════════════════════════════════════════ */
    QPushButton {{
        background-color: {p.bg_surface};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        padding: 5px 11px;
        font-size: {FONT.body}px; font-weight: {WEIGHT.medium};
    }}
    QPushButton:hover {{
        background-color: {p.bg_elevated};
        border-color: {p.border_strong};
    }}
    QPushButton:pressed {{
        background-color: {p.bg_input};
    }}
    QPushButton:disabled {{
        color: {p.text_muted};
        background-color: {p.bg_surface};
        border-color: {p.border};
    }}

    /* Primary CTA — muted forest green (light) / sage (dark) */
    QPushButton#Primary {{
        background-color: {p.accent};
        color: {p.text_on_accent};
        border: none;
        border-radius: {RADIUS.md}px;
        padding: 7px 18px;
        font-size: {FONT.body}px; font-weight: {WEIGHT.semibold};
        /* V18.15.9.1: Remove the default Qt focus rectangle (the thick
           misaligned border that looks like a selection box on the Proceed
           button). The hover/pressed states provide visual feedback instead. */
        outline: none;
    }}
    QPushButton#Primary:hover {{
        background-color: {p.accent_hover};
    }}
    QPushButton#Primary:pressed {{
        background-color: {p.accent_pressed};
    }}
    QPushButton#Primary:disabled {{
        background-color: {p.bg_input};
        color: {p.text_muted};
    }}

    /* M2-ready hero CTA — the single dominant dashboard action
       (dashboard-facing type scale; larger than the dialog Primary).
       V0.6.76 (visual-fidelity pass): the reference's measured capsule —
       ~258×57 px with a ~28 px radius (a true pill at this height),
       16 px label, generous horizontal padding. */
    QPushButton#HeroPrimary {{
        background-color: {p.accent};
        color: {p.text_on_accent};
        border: none;
        border-radius: 28px;
        padding: 14px 26px;
        font-size: 16px; font-weight: {WEIGHT.semibold};
        outline: none;
    }}
    QPushButton#HeroPrimary:hover {{
        background-color: {p.accent_hover};
    }}
    QPushButton#HeroPrimary:pressed {{
        background-color: {p.accent_pressed};
    }}
    QPushButton#HeroPrimary:disabled {{
        background-color: {p.bg_input};
        color: {p.text_muted};
    }}

    /* V0.6.76 (visual-fidelity pass): the top bar's backend status pill —
       the reference's compact capsule (green dot + "Ollama" + chevron),
       a barely-lighter fill on the header cream with a hairline border. */
    QPushButton#BackendPill {{
        background-color: {p.bg_surface};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 18px;
        padding: 6px 14px;
        font-size: {FONT.body_lg}px; font-weight: {WEIGHT.medium};
        outline: none;
    }}
    QPushButton#BackendPill:hover {{
        border-color: {p.border_strong};
        background-color: {p.bg_elevated};
    }}

    /* V0.6.76: the frameless shell's window controls — quiet glyph buttons
       at the reference's ~54 px pitch; the close hover gets the standard
       warm red affordance. */
    QPushButton#WinCtrl {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: {RADIUS.sm}px;
        min-width: 34px; min-height: 30px;
        max-width: 34px; max-height: 30px;
        font-size: {FONT.body}px;
        outline: none;
    }}
    QPushButton#WinCtrl:hover {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
    }}
    QPushButton#WinCtrl:pressed {{
        background-color: {p.bg_input};
    }}
    QPushButton#CloseBtn {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: {RADIUS.sm}px;
        min-width: 34px; min-height: 30px;
        max-width: 34px; max-height: 30px;
        font-size: {FONT.body}px;
        outline: none;
    }}
    QPushButton#CloseBtn:hover {{
        background-color: {p.error};
        color: {p.text_on_accent};
    }}
    QPushButton#CloseBtn:pressed {{
        background-color: {p.error};
        color: {p.text_on_accent};
    }}

    /* V0.6.76: the status strip's theme selector + the Quick Tools
       "View all tools →" action — quiet text buttons. */
    QPushButton#StatusThemeBtn {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-radius: {RADIUS.sm}px;
        padding: 6px 10px;
        font-size: {FONT.sidebar}px; font-weight: {WEIGHT.medium};
        outline: none;
    }}
    QPushButton#StatusThemeBtn:hover {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
    }}
    QPushButton#ViewAllLink {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        padding: 4px 6px;
        font-size: {FONT.sidebar}px; font-weight: {WEIGHT.medium};
        outline: none;
    }}
    QPushButton#ViewAllLink:hover {{
        color: {p.accent};
    }}
    /* V0.6.76: the sidebar nav rows — the reference's ~37 px rows with a
       10 px radius and the pale-sage active pill. */
    QWidget#SidebarNavItem {{
        background: transparent;
        border: none;
        border-radius: {RADIUS.nav}px;
    }}
    QWidget#SidebarNavItem:hover {{
        background: {rgba(p.text_primary, 0.05)};
    }}
    QWidget#SidebarNavItem[active="true"] {{
        background: {p.accent_soft};
    }}

    /* Secondary — outline */
    QPushButton#Secondary {{
        background-color: transparent;
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: {RADIUS.md}px;
        padding: 7px 14px;
        font-size: {FONT.body}px; font-weight: {WEIGHT.semibold};
    }}
    QPushButton#Secondary:hover {{
        background-color: {p.bg_elevated};
        border-color: {p.accent};
        color: {p.accent};
    }}

    /* Ghost / icon buttons in top bar */
    QPushButton#IconBtn {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS.sm}px;
        padding: 4px;
        min-width: 26px; min-height: 26px;
        max-width: 26px; max-height: 26px;
    }}
    QPushButton#IconBtn:hover {{
        background-color: {p.bg_elevated};
    }}
    QPushButton#IconBtn:pressed {{
        background-color: {p.bg_input};
    }}

    /* Small / compact button */
    QPushButton#Compact {{
        padding: 4px 8px;
        font-size: {FONT.caption}px;
        border-radius: {RADIUS.sm}px;
    }}

    /* Danger */
    QPushButton#Danger {{
        background-color: transparent;
        color: {p.error};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        padding: 5px 11px;
    }}
    QPushButton#Danger:hover {{
        background-color: {rgba(p.error, 0.12)};
        border-color: {p.error};
    }}

    /* ════════════════════════════════════════════════════════════════════
       Inputs — LineEdit, TextEdit, ComboBox, SpinBox
       ════════════════════════════════════════════════════════════════════ */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        padding: 4px 6px;
        selection-background-color: {p.accent};
        selection-color: {p.text_on_accent};
    }}
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
    QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {p.border_strong};
        background-color: {p.bg_input_hover};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {p.accent};
        background-color: {p.bg_input_hover};
    }}
    QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
        color: {p.text_muted};
        background-color: {p.bg_surface};
    }}
    QLineEdit[readOnly="true"] {{
        background-color: {p.bg_surface};
        color: {p.text_secondary};
    }}
    QLineEdit#Placeholder {{ color: {p.text_muted}; }}

    /* ComboBox dropdown */
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {p.text_secondary};
        width: 0; height: 0;
        margin-right: 7px;
    }}
    QComboBox::down-arrow:on {{
        border-top: none;
        border-bottom: 5px solid {p.accent};
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        padding: 3px;
        selection-background-color: {p.accent_soft};
        selection-color: {p.accent};
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 4px 8px;
        border-radius: {RADIUS.xs}px;
        min-height: 18px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background-color: {p.accent_soft};
    }}

    /* SpinBox arrows */
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border: none;
        width: 12px;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-bottom: 4px solid {p.text_secondary};
        width: 0; height: 0;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-top: 4px solid {p.text_secondary};
        width: 0; height: 0;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Checkboxes & Radio buttons
       ════════════════════════════════════════════════════════════════════ */
    QCheckBox, QRadioButton {{
        background-color: transparent;
        color: {p.text_primary};
        spacing: 6px;
        padding: 2px 0;
        font-size: {FONT.body}px;
    }}
    QCheckBox:hover, QRadioButton:hover {{ color: {p.text_primary}; }}
    QCheckBox:disabled, QRadioButton:disabled {{ color: {p.text_muted}; }}

    QCheckBox::indicator, QRadioButton::indicator {{
        background-color: {p.bg_input};
        border: 1px solid {p.border_strong};
        width: 14px; height: 14px;
        border-radius: {RADIUS.xs}px;
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {p.accent};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p.accent};
        border-color: {p.accent};
        image: none;
    }}
    QCheckBox::indicator:checked {{
        background-color: {p.accent};
        border-color: {p.accent};
    }}

    QRadioButton::indicator {{
        border-radius: 7px;
        width: 14px; height: 14px;
    }}
    QRadioButton::indicator:checked {{
        background-color: {p.bg_input};
        border: 1px solid {p.accent};
        border-width: 4px;
        border-radius: 7px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Sliders
       ════════════════════════════════════════════════════════════════════ */
    QSlider::groove:horizontal {{
        height: 4px;
        background-color: {p.border};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {p.accent};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background-color: {p.bg_surface};
        border: 2px solid {p.accent};
        width: 12px; height: 12px;
        margin: -5px 0;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: {p.accent};
        border-color: {p.accent_hover};
    }}

    /* ════════════════════════════════════════════════════════════════════
       Progress bar — slim + striped variant
       ════════════════════════════════════════════════════════════════════ */
    QProgressBar {{
        background-color: {p.bg_input};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        text-align: center;
        color: {p.text_secondary};
        font-size: {FONT.caption}px;
        min-height: 14px; max-height: 14px;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: 5px;
    }}
    QProgressBar#StripedBar {{
        background-color: {p.bg_input};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        min-height: 14px; max-height: 14px;
    }}
    QProgressBar#StripedBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #5A8060, stop:0.249 #5A8060,
            stop:0.25 #8FAB85, stop:0.499 #8FAB85,
            stop:0.5 #5A8060, stop:0.749 #5A8060,
            stop:0.75 #8FAB85, stop:1 #8FAB85);
        border-radius: 5px;
        margin: 1px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Group boxes (settings sections) — flat, hairline-separated, compact
       ════════════════════════════════════════════════════════════════════ */
    QGroupBox {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS.lg}px;
        margin-top: 7px;
        padding: 6px 7px 4px 7px;
        font-size: {FONT.caption}px;
        font-weight: {WEIGHT.semibold};
        color: {p.text_secondary};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 8px;
        background-color: {p.bg_window};
        color: {p.text_secondary};
    }}

    /* ════════════════════════════════════════════════════════════════════
       Tab bar (main tabs + settings dialog)
       ════════════════════════════════════════════════════════════════════ */
    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: {RADIUS.lg}px;
        background-color: {p.bg_surface};
        top: -1px;
    }}
    QTabBar {{
        background-color: transparent;
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {p.text_secondary};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 5px 12px;
        margin: 0 1px;
        font-size: {FONT.body}px;
        font-weight: {WEIGHT.medium};
        min-width: 0;
    }}
    QTabBar::tab:hover {{
        color: {p.text_primary};
        border-bottom: 2px solid {p.border_strong};
    }}
    QTabBar::tab:selected {{
        color: {p.accent};
        border-bottom: 2px solid {p.accent};
        background-color: transparent;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Scroll bars — slim, unobtrusive
       ════════════════════════════════════════════════════════════════════ */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 2px;
    }}
    QScrollBar::handle {{
        background: {p.border_strong};
        border-radius: 4px;
        min-height: 30px;
        min-width: 30px;
    }}
    QScrollBar::handle:hover {{
        background: {p.text_muted};
    }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
        border: none;
        height: 0; width: 0;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Text browser / log viewer
       ════════════════════════════════════════════════════════════════════ */
    QTextBrowser, QTextEdit[readOnly="true"] {{
        background-color: {p.bg_input};
        border: 1px solid {p.border};
        border-radius: {RADIUS.lg}px;
        padding: 7px;
        font-family: {FONT_FAMILY_MONO};
        font-size: {FONT.body}px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Dialog buttons (Save / Cancel)
       ════════════════════════════════════════════════════════════════════ */
    QDialogButtonBox QPushButton {{
        min-width: 68px;
        padding: 5px 12px;
    }}

    /* ════════════════════════════════════════════════════════════════════
       Menu bar / menus
       ════════════════════════════════════════════════════════════════════ */
    QMenuBar {{
        background-color: {p.bg_window};
        color: {p.text_primary};
        border-bottom: 1px solid {p.border};
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 4px 8px;
        border-radius: {RADIUS.sm}px;
    }}
    QMenuBar::item:selected {{
        background-color: {p.bg_elevated};
    }}
    QMenu {{
        background-color: {p.bg_elevated};
        border: 1px solid {p.border};
        border-radius: {RADIUS.md}px;
        padding: 3px;
    }}
    QMenu::item {{
        padding: 5px 20px 5px 10px;
        border-radius: {RADIUS.sm}px;
    }}
    QMenu::item:selected {{
        background-color: {p.accent_soft};
        color: {p.accent};
    }}

    /* ════════════════════════════════════════════════════════════════════
       List / tree views (queue, chapter selector)
       ════════════════════════════════════════════════════════════════════ */
    QListView, QTreeView, QTableView {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS.lg}px;
        padding: 2px;
        outline: none;
    }}
    QListView::item, QTreeView::item, QTableView::item {{
        padding: 3px 5px;
        border-radius: {RADIUS.xs}px;
    }}
    QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
        background-color: {p.accent_soft};
        color: {p.text_primary};
    }}
    QHeaderView::section {{
        background-color: {p.bg_surface};
        color: {p.text_secondary};
        border: none;
        border-bottom: 1px solid {p.border};
        padding: 4px 6px;
        font-size: {FONT.caption}px;
        font-weight: {WEIGHT.semibold};
    }}
    """


# ─────────────────────────────────────────────────────────────────────────────
# ThemeManager
# ─────────────────────────────────────────────────────────────────────────────


class ThemeManager:
    """Owns the active palette, generates QSS, persists the user's choice.

    V7.4.0: loads bundled Inter weights on first apply; the stylesheet falls
    back to Segoe UI Variable / Segoe UI when Inter is absent.
    """

    def __init__(self) -> None:
        # PACKAGING: user_data_dir() → %LOCALAPPDATA%\Elixir when frozen,
        # ~/.elixir from source (unchanged).
        from utils.settings import user_data_dir

        self.settings_file = user_data_dir() / "ui_theme.json"
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._mode: str = self._load_mode()
        self._app: QApplication | None = None
        self._inter_loaded: bool = False

    # ── persistence ──────────────────────────────────────────────────────
    def _load_mode(self) -> str:
        if self.settings_file.exists():
            try:
                with open(self.settings_file) as f:
                    return json.load(f).get("theme", "light")
            except Exception:
                pass  # best-effort (UI — never crash)
        return "light"

    def _save_mode(self, mode: str) -> None:
        try:
            with open(self.settings_file, "w") as f:
                json.dump({"theme": mode}, f)
        except Exception:
            pass

    # ── accessors ────────────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_dark(self) -> bool:
        return self._mode == "dark"

    @property
    def palette(self) -> Palette:
        return PALETTES[self._mode]

    def palette_for(self, mode: str) -> Palette:
        return PALETTES[mode]

    @property
    def inter_loaded(self) -> bool:
        return self._inter_loaded

    # ── application ──────────────────────────────────────────────────────
    def apply(self, app: QApplication, mode: str | None = None) -> None:
        """Apply the theme to ``app``.  If ``mode`` is None, uses current."""
        self._app = app
        if mode is not None:
            self._mode = mode
        # one-shot Inter registration
        if not self._inter_loaded:
            try:
                fams = load_inter(app)
                self._inter_loaded = bool(fams)
            except Exception:
                self._inter_loaded = False
        p = self.palette

        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(p.bg_window))
        pal.setColor(QPalette.WindowText, QColor(p.text_primary))
        pal.setColor(QPalette.Base, QColor(p.bg_input))
        pal.setColor(QPalette.AlternateBase, QColor(p.bg_surface))
        pal.setColor(QPalette.Text, QColor(p.text_primary))
        pal.setColor(QPalette.Button, QColor(p.bg_surface))
        pal.setColor(QPalette.ButtonText, QColor(p.text_primary))
        pal.setColor(QPalette.Highlight, QColor(p.accent))
        pal.setColor(QPalette.HighlightedText, QColor(p.text_on_accent))
        pal.setColor(QPalette.ToolTipBase, QColor(p.bg_elevated))
        pal.setColor(QPalette.ToolTipText, QColor(p.text_primary))
        pal.setColor(QPalette.PlaceholderText, QColor(p.text_muted))
        app.setPalette(pal)

        app.setStyleSheet(_qss(p))
        self._save_mode(self._mode)

    def toggle(self) -> str:
        """Flip dark↔light and re-apply. Returns the new mode."""
        new = "dark" if self._mode == "light" else "light"
        if self._app is not None:
            self.apply(self._app, new)
        else:
            self._mode = new
            self._save_mode(new)
        return new


# Module-level singleton — mirrors the original Tkinter theme_manager API so
# the rest of the app imports it the same way.
theme_manager = ThemeManager()
