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

V0.6.84 (Round-4 §3.3/§4, compact density): the rail is restructured
into the spec's three regions — (1) a scroll-free PRIMARY navigation
area at the reference viewport (the brand row + Home + the nine tools:
32 px rows, tight group rhythm), (2) a FIXED lower navigation region
pinned BELOW the scroll area (the divider + Settings + About — always
visible, never pushed out of view), and (3) the compact tagline card
at the bottom (~40 px art band, the full brand line readable at the
13 px sidebar scale). The V0.6.77–83 layout carried the footer items
INSIDE the scroll area and the V0.6.82 reference rhythm (37 px rows,
the 22+28 brand insets, the 125 px tagline card) — which at the user's
real ~1096×717 window needed 834 px of rail against 675 available:
the internal scrollbar, the clipped last tool, and the clipped tagline
the Round-4 audit flags. The compact rhythm fits the same window in
~615 px with no scrollbar.

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

# The reference rail width — V0.6.77: re-measured from the approved reference
# (the shell starts at x=22, the rail/content boundary lands at x≈287 →
# 265 px; the old 210 px QA budget left the rail too narrow for the
# reference's rhythm and pushed the content start left of the target).
# V0.6.83 (Round-3 correction, spec §3.1): the rail is no longer FIXED at
# 265 — it is RESPONSIVE to the window width, ``clamp(180, 0.18*w, 260)``
# logical px, driven from ``ElixirWindow.resizeEvent`` via
# ``set_rail_width`` (the parent owns the rule; the rail only applies it).
# 265 stays the documented reference rail for the 1536-wide composition
# window (0.18*1536 = 276 clamps to 260 — the reference rail lands within
# the spec's 17–19% band) and as the wide-profile default before the
# first resize event.
SIDEBAR_WIDTH = 265

# V0.6.83 (Round-3 §3.1): the responsive bounds — 17–19% of the window
# between a 180 floor and a 260 ceiling (“The sidebar must not grow
# indefinitely when the window gets larger”; “At a 1000 px window width,
# expect a sidebar around 180 px”). Below RAIL_COMPACT_BELOW the rail
# switches to the compact profile (tighter brand row, word-wrapped nav
# labels at smaller insets) so the labels stay fully legible — never
# clipped, never shrunk to an unreadable size.
RAIL_MIN, RAIL_MAX = 180, 260
RAIL_COMPACT_BELOW = 232

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
# V0.6.84 (Round-4 §3.3): the compact rail fits the full structure in
# ~615 px; below this floor the decorative tagline card yields first
# (the primary nav + the pinned footer keep their space).
_BRAND_MIN_RAIL_H = 560


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
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(7)
        self._leaf = QLabel()
        self._leaf.setFixedSize(14, 14)
        row.addWidget(self._leaf, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(0)
        # V0.6.79: the reference's card text — a dark-sage bold lead line
        # over the muted second line (measured #52614D / #8A8F86).
        self._line1 = QLabel("Knowledge,")
        self._line1.setObjectName("TaglineLead")
        text.addWidget(self._line1)
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
        art_wrap.setContentsMargins(0, 6, 0, 0)
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
        """Glyph tint + the two brand lines (token-driven).

        V0.6.84 (Round-4 §4): both lines word-wrap — the full brand line
        "Knowledge, distilled into clarity." stays visible at EVERY rail
        width (the wide rail keeps the reference's two-line break; the
        compact rail adds a third line rather than clipping — the exact
        defect the audit's "text clipped" row flags).
        """
        from ui_qt.theme import FONT, WEIGHT

        p = theme_manager.palette
        self._leaf.setPixmap(icon("leaf", p.sage, 14).pixmap(14, 14))
        self._line1.setWordWrap(True)
        self._line2.setWordWrap(True)
        self._line2.setStyleSheet(
            f"font-size: {FONT.sidebar}px; font-weight: {WEIGHT.regular};"
            f"color: {p.text_secondary}; background: transparent;"
        )
        self._line1.setStyleSheet(
            f"font-size: {FONT.sidebar}px; font-weight: {WEIGHT.semibold};"
            f"color: {p.sage}; background: transparent;"
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
        scrim = 0.38 if not p.is_dark else 0.55
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
        # V0.6.84 (Round-4 §4): 38 — the card lands ≈100 px with the 12 px
        # top inset (the V0.6.82 64 px strip was two-thirds of the card's
        # blank-heavy 125 px — the audit's "too tall for its content")
        # while the full three-line rail budget still closes at the
        # user's 633 px rail (58 brand + 370 nav + 78 lower + ~120 card).
        strip_h = min(scaled_h, 38)
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
        # V0.6.83 (Round-3 §3.1): the rail starts at the reference width; the
        # parent window's resize logic retunes it to clamp(180, 0.18*w, 260)
        # from the very first resize/show event.
        self._rail_w = SIDEBAR_WIDTH
        self._compact = False
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._items: dict[str, SidebarNavItem] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── the brand row (V0.6.77: the reference's leaf + wordmark,
        #    moved out of the top bar into the rail) ──────────────────
        # V0.6.84 (Round-4 §3.2, compact density): the reference rhythm
        # (48 px leaf, 24+28 insets) consumed 100 px of rail; the compact
        # row (32 px leaf, 14+12 insets) takes ~58 — part of how the full
        # nav fits the user's ~633 px rail without a scrollbar.
        brand_row = QWidget()
        bl = QHBoxLayout(brand_row)
        bl.setContentsMargins(20, 14, 12, 12)
        bl.setSpacing(10)
        self._brand_row_lay = bl
        self._brand_leaf = QLabel()
        self._brand_leaf.setFixedSize(32, 32)
        bl.addWidget(self._brand_leaf, 0, Qt.AlignmentFlag.AlignVCenter)
        self._brand_word = QLabel("Elixir")
        self._brand_word.setObjectName("BrandWord")
        bl.addWidget(self._brand_word, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addStretch(1)
        root.addWidget(brand_row)

        # ── Region 1 (Round-4 §3.3): the scrollable PRIMARY navigation ─
        # Brand row + Home + the TOOLS group. At the reference viewport
        # this region is scroll-free (the compact rhythm fits ~615 px of
        # rail); below it the area scrolls deliberately (spec §3.3:
        # "allow a deliberate sidebar scrolling mode rather than clipping
        # controls") while Regions 2+3 stay pinned.
        nav_host = QWidget()
        nav = QVBoxLayout(nav_host)
        nav.setContentsMargins(14, 2, 14, 6)
        nav.setSpacing(1)
        self._nav_host_lay = nav
        for group_label, items in NAV_GROUPS:
            if group_label is not None:
                # V0.6.84 (Round-4 §3.1): the reference's group rhythm at
                # the compact density — 12 px above the label, 6 below.
                nav.addSpacing(12)
                nav.addWidget(SectionLabel(group_label))
                nav.addSpacing(6)
            for key, icon_name, label in items:
                item = SidebarNavItem(icon_name, label, tall=(key == "home"))
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

        # ── Region 2 (Round-4 §3.3): the FIXED lower navigation ────────
        # The divider + Settings/About, pinned BELOW the scroll area so
        # the primary tools can never push them out of view (the V0.6.77-83
        # layout carried them inside the scrollable column — at the user's
        # real window the nine tools filled the viewport and the footer
        # vanished below the fold). Spec §3.1: "Settings and About in a
        # fixed lower navigation region".
        lower = QWidget()
        lower_lay = QVBoxLayout(lower)
        lower_lay.setContentsMargins(14, 4, 14, 2)
        lower_lay.setSpacing(1)
        divider = QFrame()
        divider.setObjectName("Divider")
        lower_lay.addWidget(divider)
        lower_lay.addSpacing(6)
        for key, icon_name, label in NAV_FOOTER:
            item = SidebarNavItem(icon_name, label)
            item.clicked.connect(lambda k=key: self.navigate.emit(k))
            self._items[key] = item
            lower_lay.addWidget(item)
        root.addWidget(lower)

        # ── Region 3 (Round-4 §3.3/§4): the compact tagline card ───────
        # M3 asset audit: hills panorama + leaf + the brand line. Pinned
        # at the rail's bottom; hides on short rails (see resizeEvent).
        brand_wrap = QVBoxLayout()
        brand_wrap.setContentsMargins(14, 6, 14, 8)
        self._brand = SidebarBrandCard()
        brand_wrap.addWidget(self._brand)
        root.addLayout(brand_wrap)

        self._apply_brand_tints()

    # ── geometry ─────────────────────────────────────────────────────────
    def set_rail_width(self, w: int) -> None:
        """V0.6.83 (Round-3 §3.1): apply the responsive rail width.

        The PARENT owns the rule (``clamp(180, 0.18 * window_width, 260)``
        logical px, called from ``ElixirWindow.resizeEvent`` so the rail is
        always Qt-layout-driven, never absolute-positioned). The rail only
        clamps to [RAIL_MIN, RAIL_MAX] and switches to the compact profile
        below RAIL_COMPACT_BELOW so the nav labels keep their full text at
        legible sizes — the spec forbids solving the narrow rail with
        microscopic type or clipped labels.
        """
        w = max(RAIL_MIN, min(RAIL_MAX, int(w)))
        if w == self._rail_w:
            return
        self._rail_w = w
        self.setFixedWidth(w)
        compact = w < RAIL_COMPACT_BELOW
        if compact != self._compact:
            self._compact = compact
            self._apply_profile()

    def _apply_profile(self) -> None:
        """Re-tune the rail's fixed insets for the active profile (the
        fluid parts — nav list, brand card — reflow on their own).

        Wide (≥ RAIL_COMPACT_BELOW): the Round-4 compact calibration.
        Compact: the narrow-rail adaptation — a tighter brand row
        (28 px leaf, 22 px wordmark) and tighter nav insets; the nav
        LABELS word-wrap to two lines (never clipped, never shrunk), so
        a 180 px rail still reads.
        """
        from ui_qt.theme import WEIGHT

        compact = self._compact
        # ── the brand row ─────────────────────────────────────────────
        self._brand_row_lay.setContentsMargins(*(16, 12, 10, 10) if compact else (20, 14, 12, 12))
        self._brand_row_lay.setSpacing(8 if compact else 10)
        leaf_px = 26 if compact else 32
        glyph_px = 24 if compact else 28
        self._brand_leaf.setFixedSize(leaf_px, leaf_px)
        p = theme_manager.palette
        self._brand_leaf.setPixmap(icon("leaf", p.accent, glyph_px).pixmap(glyph_px, glyph_px))
        if compact:
            self._brand_word.setStyleSheet(
                f"font-size: 20px; font-weight: {WEIGHT.semibold};"
                f"color: {p.text_primary}; letter-spacing: 0.2px;"
                "background: transparent;"
            )
        else:
            self._brand_word.setStyleSheet("background: transparent;")
        # ── the nav host + items ───────────────────────────────────────
        self._nav_host_lay.setContentsMargins(*(11, 2, 11, 6) if compact else (14, 2, 14, 6))
        for item in self._items.values():
            item.set_compact(compact)

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
        """The brand row's leaf tint (token-driven). V0.6.84 (Round-4
        compact): the glyph renders at 28 px inside its 32 px box (the
        V0.6.82 44 px mark was calibrated against the 1536 reference)."""
        p = theme_manager.palette
        self._brand_leaf.setPixmap(icon("leaf", p.accent, 28).pixmap(28, 28))

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
    "RAIL_MIN",
    "RAIL_MAX",
    "RAIL_COMPACT_BELOW",
    "nav_keys",
]
