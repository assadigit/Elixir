"""M2 (UI/UX redesign): the fixed left sidebar — the primary nav.

V0.6.77 (visual-fidelity pass): the sidebar is re-measured against the
approved dashboard reference (1536×1024) —

  • width 265 px (17.3% of the reference window; the rail had been 210),
  • the BRAND ROW at the top (leaf emblem + "Elixir" wordmark) — the
    brand moved out of the top bar into the rail exactly as the
    reference draws it,
  • Home with the pale-sage selected pill,
  • ONE "TOOLS" group label above the nine core tools (Full Conversion
    first, then Summarization, Document → Markdown, Translation,
    Markdown Styler, Packets of Knowledge, OCR Service, PDF/DOCX Cutter,
    Image Extractor order per the reference),
  • a divider, then Settings and About,
  • the tagline card (leaf + "Knowledge, distilled into clarity." over
    the muted landscape artwork) anchored at the bottom.

The AUDIO group (TTS / Podcast Maker / Transcribe) left the primary
navigation — the reference rail carries only the nine core tools. The
tools themselves are untouched: they stay reachable via the Quick Tools
"View all tools →" page (the legacy tool dashboard carries every tool)
AND via About & System's "More tools & actions" rows. ``AUDIO_KEYS``
pins that relocation.

Navigation ROUTING is intentionally NOT implemented here, exactly like
the primitives' own contract: items emit ``navigate(key)`` and
``ElixirWindow`` decides what a click means (page switch, tool-dialog
dispatch via the existing ``convert_view`` tool-key dispatch, or one of
the two dialogs).

The experimental destinations (decision Q2 — Queue, Output Scanner,
Bullet Audit, Hallucination Audit) remain deliberately ABSENT from
``NAV_GROUPS`` / ``NAV_FOOTER``; they stay reachable via the About &
System "Experimental tools…" fallback and their existing routing.
``EXPERIMENTAL_KEYS`` is the pin anchor for that absence.

Styling: the rail chrome is the ``QFrame#SidebarRail`` QSS rule in
``theme.py``; every item/group label is token-driven (no colour
literals — the M1 zero-literal census covers this file).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.dashboard_primitives import SectionLabel, SidebarNavItem
from ui_qt.components.icons import icon
from ui_qt.theme import RADIUS, theme_manager

# The fixed rail width — V0.6.77: re-measured from the approved reference
# (the shell starts at x=22, the rail/content boundary lands at x≈287 →
# 265 px; the old 210 px QA budget left the rail too narrow for the
# reference's rhythm and pushed the content start left of the target).
SIDEBAR_WIDTH = 265

# ── Navigation data (the single source of truth for the sidebar IA) ─────────
# Group label ``None`` = ungrouped items (Home at the top; Settings/About in
# the footer).  Labels are the EXACT user-facing names verified against
# ``tool_dashboard.TOOL_CARDS`` + the M0 §5 inventory (never renamed).
NAV_GROUPS: list[tuple[str | None, list[tuple[str, str, str]]]] = [
    (None, [("home", "home", "Home")]),
    (
        "Tools",
        [
            ("full_conversion", "zap", "Full Conversion"),
            ("summarization", "sigma", "Summarization"),
            ("pdf_to_markdown", "file-text", "Document → Markdown"),
            ("translation", "globe", "Translation"),
            ("markdown_styler", "sparkles", "Markdown Styler"),
            ("packets_tool", "layers", "Packets of Knowledge"),
            ("ocr_service", "scan", "OCR Service"),
            ("pdf_docx_cutter", "scissors", "PDF/DOCX Cutter"),
            ("image_extractor", "image", "Image Extractor"),
        ],
    ),
]

# Pinned below the scrollable groups — always visible even at min height.
NAV_FOOTER: list[tuple[str, str, str]] = [
    ("settings", "settings", "Settings"),
    ("about", "info", "About"),
]

# V0.6.77 (visual-fidelity pass): the Audio group left the primary rail —
# the approved reference's sidebar carries only the nine core tools. The
# tools are NOT deleted: the convert page ("View all tools →") and the
# About & System "More tools & actions" rows both route to them.
AUDIO_KEYS = ("tts_service", "podcast_maker", "transcribe")

# Decision Q2: these destinations NEVER appear in the sidebar nav data.
# (Their views + routing stay intact behind About & System.)
EXPERIMENTAL_KEYS = ("batch_queue", "output_scanner", "quarantine", "hallucination_audit")


def nav_keys() -> list[str]:
    """Every navigation key the sidebar can emit (groups + footer)."""
    keys: list[str] = []
    for _group, items in NAV_GROUPS:
        keys.extend(key for key, _icon, _label in items)
    keys.extend(key for key, _icon, _label in NAV_FOOTER)
    return keys


# Below this rail height the brand card hides (spec §7 narrow-width rule:
# a 560×400 window keeps the nav + footer, drops the decorative moment).
_BRAND_MIN_RAIL_H = 520


class SidebarBrandCard(QFrame):
    """The approved reference's sidebar-bottom brand moment (M3 asset
    audit): a compact card — leaf glyph + the brand line — over the
    supplied ``assets/botanical_landscape.png`` misty-hills panorama.

    The landscape ships with a baked cream canvas (the package's
    ASSET_GUIDE flags it as an *optional* motif), so it is never pasted
    raw: it is composited onto the current card surface and muted with a
    surface scrim, which keeps it a quiet watermark in light theme and a
    dusk landscape in dark theme (token-only — the M1 zero-literal
    census covers this file).  If the asset is absent (thin bundles) the
    art hides and the card degrades to the text-only brand line.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarBrandCard")
        self._pm_key: tuple | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(0)

        # ── leaf glyph + the two-line brand text ──────────────────────
        row = QHBoxLayout()
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(8)
        self._leaf = QLabel()
        self._leaf.setFixedSize(16, 16)
        row.addWidget(self._leaf, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(0)
        line1 = QLabel("Knowledge,")
        line1.setObjectName("ToolTitle")
        text.addWidget(line1)
        self._line2 = QLabel("distilled into clarity.")
        text.addWidget(self._line2)
        row.addLayout(text, 1)
        root.addLayout(row)

        # ── the misty-hills panorama — full-bleed: spans the card width
        # and sits flush on the card's bottom edge (the approved
        # reference anchors the art to the card bottom, clipped by the
        # rounded corners).  The composite fades its top into the
        # surface so there is never a hard pasted-edge line.
        self._art = QLabel()
        self._art.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        art_wrap = QVBoxLayout()
        art_wrap.setContentsMargins(0, 8, 0, 0)
        art_wrap.addWidget(self._art)
        root.addLayout(art_wrap)

        self._apply_art()
        self._apply_text_style()

    # ── theming ───────────────────────────────────────────────────────────
    def refresh_theme(self) -> None:
        """Re-tint the glyph and re-composite the art (theme toggle hook)."""
        self._pm_key = None  # force a rebuild against the new surface
        self._apply_art()
        self._apply_text_style()

    def _apply_text_style(self) -> None:
        """Glyph tint + the secondary line colour (token-driven)."""
        from ui_qt.theme import FONT, WEIGHT

        p = theme_manager.palette
        self._leaf.setPixmap(icon("leaf", p.sage, 16).pixmap(16, 16))
        self._line2.setStyleSheet(
            f"font-size: {FONT.sidebar}px; font-weight: {WEIGHT.regular};"
            f"color: {p.text_secondary}; background: transparent;"
        )

    def _apply_art(self) -> None:
        """Composite the landscape as a full-bleed bottom strip.

        Same contract as the hero's ``_flattened_hero_pixmap`` (flatten
        onto the surface token) plus two integration steps the raw asset
        needs (its cream canvas is baked in — the package ASSET_GUIDE
        flags it as an optional motif, never paste it raw):

        1. a surface scrim mutes the canvas toward the card surface
           (light: a quiet watermark; dark: a dusk landscape);
        2. the strip's TOP fades into the surface over its upper 40%
           (alpha gradient) — no hard pasted-edge line — and the BOTTOM
           corners clip to the card radius so the art cannot poke out
           of the rounded card.

        Cached per (width, surface, scrim) key — a theme toggle or rail
        resize rebuilds it, nothing else does.
        """
        from app_paths import bundle_dir

        p = theme_manager.palette
        scrim = 0.45 if not p.is_dark else 0.55
        w = self._art.width() or max(1, self.width() - 2)
        key = (w, p.bg_surface, scrim)
        if key == self._pm_key:
            return
        self._pm_key = key

        src_path = bundle_dir() / "assets" / "botanical_landscape.png"
        src = QPixmap(str(src_path)) if src_path.exists() else QPixmap()
        if src.isNull():  # asset absent (thin bundles) → text-only card
            self._art.hide()
            self._art.clear()
            return
        scaled_h = max(1, round(src.height() * w / src.width()))
        scaled = src.scaled(
            w,
            scaled_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Keep the strip compact (V0.6.77: the reference card's art band
        # is ~50 px of the ~126 px card): crop from the TOP (the fade
        # erases the crop line) so the hills' lower band fills the strip.
        strip_h = min(scaled_h, 72)
        flat = QImage(w, strip_h, QImage.Format.Format_ARGB32_Premultiplied)
        flat.fill(QColor(p.bg_surface))
        painter = QPainter(flat)
        painter.drawPixmap(0, 0, scaled, 0, scaled_h - strip_h, w, strip_h)
        scrim_color = QColor(p.bg_surface)
        scrim_color.setAlphaF(scrim)
        painter.fillRect(0, 0, w, strip_h, scrim_color)
        painter.end()

        # Top fade: multiply the flattened strip by a vertical alpha
        # ramp (transparent at the top → opaque at 40% down) so the art
        # emerges out of the card surface instead of starting at a line.
        fade = QImage(w, strip_h, QImage.Format.Format_ARGB32_Premultiplied)
        fade.fill(QColor(0, 0, 0, 0))
        from PySide6.QtGui import QLinearGradient

        grad = QLinearGradient(0, 0, 0, strip_h)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.4, QColor(0, 0, 0, 255))
        grad.setColorAt(1.0, QColor(0, 0, 0, 255))
        fp = QPainter(fade)
        fp.fillRect(0, 0, w, strip_h, grad)
        fp.end()
        fp = QPainter(flat)
        fp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        fp.drawImage(0, 0, fade)
        fp.end()

        # Bottom-corner clip at the card radius (top is faded, not cut).
        clip = QPainterPath()
        r = float(RADIUS.card)
        clip.moveTo(0, 0)
        clip.lineTo(w, 0)
        clip.lineTo(w, strip_h - r)
        clip.quadTo(w, strip_h, w - r, strip_h)
        clip.lineTo(r, strip_h)
        clip.quadTo(0, strip_h, 0, strip_h - r)
        clip.closeSubpath()
        out = QPixmap(w, strip_h)
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipPath(clip)
        painter.drawImage(0, 0, flat)
        painter.end()

        self._art.setPixmap(out)
        self._art.show()

    # ── geometry ─────────────────────────────────────────────────────────
    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._apply_art()


class Sidebar(QFrame):
    """The fixed left rail: the reference's brand row + grouped nav +
    footer + bottom tagline card, always visible.

    Emits ``navigate(key)`` on click (routing belongs to the window) and
    tracks the active destination via ``set_active`` (the pale-sage
    active pill).  The grouped list scrolls vertically at short window
    heights; the Settings/About footer and the tagline card stay pinned
    below it.
    """

    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarRail")
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._items: dict[str, SidebarNavItem] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── the brand row (V0.6.77: the reference's leaf + wordmark,
        #    moved out of the top bar into the rail) ──────────────────
        brand_row = QWidget()
        bl = QHBoxLayout(brand_row)
        bl.setContentsMargins(18, 26, 16, 12)
        bl.setSpacing(10)
        self._brand_leaf = QLabel()
        self._brand_leaf.setFixedSize(26, 26)
        bl.addWidget(self._brand_leaf, 0, Qt.AlignmentFlag.AlignVCenter)
        self._brand_word = QLabel("Elixir")
        self._brand_word.setObjectName("BrandWord")
        bl.addWidget(self._brand_word, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addStretch(1)
        root.addWidget(brand_row)

        # ── scrollable grouped nav ────────────────────────────────────
        nav_host = QWidget()
        nav = QVBoxLayout(nav_host)
        nav.setContentsMargins(16, 2, 16, 10)
        nav.setSpacing(2)
        for group_label, items in NAV_GROUPS:
            if group_label is not None:
                nav.addSpacing(16)
                nav.addWidget(SectionLabel(group_label))
            for key, icon_name, label in items:
                item = SidebarNavItem(icon_name, label)
                item.clicked.connect(lambda k=key: self.navigate.emit(k))
                self._items[key] = item
                nav.addWidget(item)
        nav.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(nav_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # ScrollBarPolicy is a Qt-namespace enum — it is NOT exposed as a
        # QScrollArea class attribute on PySide6 >= 6.11 (AttributeError at
        # launch on the user's Windows run, V0.6.70 pre-release smoke), so
        # the address must be Qt.ScrollBarPolicy.* (Shape above IS a QFrame
        # class enum and stays as-is).
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        root.addWidget(scroll, 1)

        # ── divider + pinned footer (Settings / About) ────────────────
        divider_wrap = QVBoxLayout()
        divider_wrap.setContentsMargins(16, 10, 16, 0)
        divider = QFrame()
        divider.setObjectName("Divider")
        divider_wrap.addWidget(divider)
        root.addLayout(divider_wrap)
        footer = QVBoxLayout()
        footer.setContentsMargins(16, 8, 16, 2)
        footer.setSpacing(2)
        for key, icon_name, label in NAV_FOOTER:
            item = SidebarNavItem(icon_name, label)
            item.clicked.connect(lambda k=key: self.navigate.emit(k))
            self._items[key] = item
            footer.addWidget(item)
        root.addLayout(footer)

        # ── the brand moment (approved reference, sidebar bottom) ─────
        # M3 asset audit: hills panorama + leaf + the brand line.  Lives
        # BELOW the pinned footer exactly as in the approved dashboard
        # reference; hides on short rails (see resizeEvent).
        brand_wrap = QVBoxLayout()
        brand_wrap.setContentsMargins(16, 8, 16, 12)
        self._brand = SidebarBrandCard()
        brand_wrap.addWidget(self._brand)
        root.addLayout(brand_wrap)

        self._apply_brand_tints()

    # ── geometry ─────────────────────────────────────────────────────────
    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Spec §7 narrow-height rule: below _BRAND_MIN_RAIL_H the nav
        and pinned footer keep their space; the decorative brand card
        hides (it never displaces navigation)."""
        super().resizeEvent(event)
        if hasattr(self, "_brand"):
            self._brand.setVisible(self.height() >= _BRAND_MIN_RAIL_H)

    # ── state ───────────────────────────────────────────────────────────
    def set_active(self, key: str | None) -> None:
        """Mark ``key`` as the current destination (None clears all)."""
        for k, item in self._items.items():
            item.set_active(k == key)

    # ── theme ───────────────────────────────────────────────────────────
    def _apply_brand_tints(self) -> None:
        """The brand row's leaf tint (token-driven)."""
        p = theme_manager.palette
        self._brand_leaf.setPixmap(icon("leaf", p.accent, 26).pixmap(26, 26))

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles (theme toggle hook)."""
        for item in self._items.values():
            item.refresh_theme()
        self._apply_brand_tints()
        # M3 asset audit: the brand card re-composites its panorama and
        # re-tints the leaf glyph against the new surface tokens.
        if hasattr(self, "_brand"):
            self._brand.refresh_theme()
        # SectionLabel + the rail chrome are QSS-driven — nothing to redo.


__all__ = [
    "Sidebar",
    "SidebarBrandCard",
    "NAV_GROUPS",
    "NAV_FOOTER",
    "AUDIO_KEYS",
    "EXPERIMENTAL_KEYS",
    "SIDEBAR_WIDTH",
    "nav_keys",
]
