"""Centralised theme system for the PySide6 UI — "Editorial Quiet" v2.

V7.4.0 overhaul.  Design language:
  - Graphite/ivory neutrals (never pure black) + a single warm terracotta-amber
    accent evoking paper, ink, and a cozy reading room.
  - **Inter** as the primary typeface (bundled in ``assets/fonts/`` if present),
    falling back to the best Windows-native stack (Segoe UI Variable → Segoe UI).
  - A single source of truth: the ``SPACE`` / ``FONT`` / ``RADIUS`` / ``WEIGHT``
    token scales.  Views import these instead of hard-coding magic numbers so
    the whole app stays visually consistent.
  - Compact density: 4px spacing grid, 11px body, hairline borders, 5-8px radii.

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

# Font sizes (px).  Inter renders crisply at 11px; Segoe UI fallback is fine too.
FONT = _ns(
    micro=9,  # badges, counters — use rarely
    caption=10,  # hints, secondary captions
    body=11,  # default body text
    body_strong=11,
    subhead=12,  # small section labels
    h3=13,  # card titles, group headings
    h2=15,  # page titles
    h1=18,  # hero / dialog titles
    display=22,  # splash / numbers
)

# Font weights (Inter ships these; Segoe UI maps 500/600→SemiBold reasonably)
WEIGHT = _ns(regular=400, medium=500, semibold=600, bold=700)

# Corner radii
RADIUS = _ns(xs=3, sm=5, md=6, lg=8, xl=10)

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
    bg_window: str  # outermost app background
    bg_surface: str  # cards / panels
    bg_elevated: str  # hover / popups / raised elements
    bg_input: str  # line-edits, combos, text areas
    bg_input_hover: str

    # lines
    border: str  # hairline 1px
    border_strong: str  # focus / selected

    # text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str

    # accent (terracotta-amber)
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str  # subtle fill behind selected items

    # semantics (muted, not garish)
    success: str
    warning: str
    error: str
    info: str


# V7.4.0: polished dark mode — brighter text_secondary + accent for contrast;
# warmer elevated surfaces so cards read clearly against the window bg.
DARK = Palette(
    name="dark",
    is_dark=True,
    bg_window="#191512",  # warm near-black charcoal-brown
    bg_surface="#241E18",  # warm dark brown card
    bg_elevated="#2E271F",  # lighter warm brown for hover/popups
    bg_input="#15110D",  # near-black warm input
    bg_input_hover="#1F1914",
    border="#3A3128",  # warm taupe hairline
    border_strong="#D4A574",  # warm amber strong border
    text_primary="#F5EDE0",  # warm cream (bumped for contrast)
    text_secondary="#CBBFA9",  # brighter beige for readability
    text_muted="#8A7D6E",  # warm taupe-gray
    text_on_accent="#1A1612",  # dark text on amber accent
    accent="#D8AA78",  # warm amber (brightened for dark mode pop)
    accent_hover="#E6BC8A",
    accent_pressed="#C09060",
    accent_soft="rgba(216, 170, 120, 0.16)",
    success="#94B088",  # muted sage green
    warning="#D8BC66",  # warm gold
    error="#DC9484",  # warm terracotta-red
    info="#A294B8",  # muted mauve
)

# V7.4.0: polished light mode — pure white surfaces for crisper card separation,
# deeper text_primary for contrast, richer terracotta accent.
LIGHT = Palette(
    name="light",
    is_dark=False,
    bg_window="#F7F3EC",  # warm ivory (slightly cooler for contrast)
    bg_surface="#FFFFFF",  # pure white cards — crisp separation
    bg_elevated="#F2EADF",  # warm cream hover
    bg_input="#FFFFFF",  # white inputs
    bg_input_hover="#FBF6EE",
    border="#E6DECF",  # warm taupe hairline
    border_strong="#C8805A",  # terracotta strong border
    text_primary="#2A211B",  # deeper warm brown for contrast
    text_secondary="#6B5B4F",  # warm brown
    text_muted="#9A8B7D",  # warm taupe-gray
    text_on_accent="#FFFFFF",
    accent="#B8704A",  # richer terracotta
    accent_hover="#A6623E",
    accent_pressed="#8F5332",
    accent_soft="rgba(184, 112, 74, 0.12)",
    success="#6F9462",  # muted sage green
    warning="#C99A3E",  # warm gold
    error="#BD664F",  # warm terracotta-red
    info="#7E6E94",  # muted mauve
)

PALETTES = {"dark": DARK, "light": LIGHT}


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
        background-color: {p.bg_window};
        border: none;
        border-bottom: 1px solid {p.border};
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

    /* Primary CTA — terracotta */
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
        background-color: rgba(189, 102, 79, 0.12);
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
