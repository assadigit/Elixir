"""M1 (UI/UX redesign): dashboard primitives — the M2/M3 building blocks.

Three small reusable widgets for the M2 dashboard milestone, built on the
M1 visual foundation (spec §4/§5 tokens + the new QSS label rules):

  • ``SectionLabel``      — the quiet uppercase group label ("TOOLS")
                            used above the sidebar's tool list.
  • ``SidebarNavItem``    — one compact fixed-sidebar destination row
                            (icon + label, hover/active states).
  • ``QuickToolCard``     — the Quick Tools grid card — V0.6.77
                            (visual-fidelity pass): the reference's
                            HORIZONTAL card (large sage outline icon at
                            the left, title + one-line description in the
                            middle, a pale circular arrow affordance at
                            the right) replacing the old vertical stack;
                            the ninth ``featured`` variant renders the
                            deep forest-green "Full Conversion Wizard"
                            card with light type and a botanical wash.

All three follow the ``ToolCard`` house pattern: objectName-scoped QSS
(``QFrame#QuickToolCard`` / ``QFrame#FeatureToolCard`` / the
``QWidget#SidebarNavItem`` rules in theme.py), ``_apply_style()``
derived from ``theme_manager.palette``, a public ``refresh_theme()``,
and no fixed coordinates (Qt layouts + size policies).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.components.icons import icon
from ui_qt.theme import RADIUS, theme_manager

# Hit-target floor (spec §10: "usable hit targets") — desktop compact.
# V0.6.77 (visual-fidelity pass): the reference's measured rhythm —
# ~37 px nav rows, ~120 px tool cards, 18 px nav glyphs, 26 px card
# glyphs, a ~36 px circular arrow affordance.
# V0.6.82 (Round-2 correction, ink-bbox calibrated against the
# reference): nav glyphs 21 px (reference icon ink 20px vs 16), nav rows
# 37 with the Home pill 45 (reference pill 232×45), tool glyphs 30 px
# (reference sigma ink 24px wide vs 20), the icon→text gap widened to
# match the reference's airier text column (title ink at card+90 vs 66).
# The dashboard glyphs render at stroke 2.05 (the reference's icons read
# visibly heavier than the 1.85 dialog default at the same size).
_ICON_STROKE_DASH = 2.05
_NAV_ITEM_HEIGHT = 37
_NAV_ITEM_TALL = 45
_ICON_SIZE_NAV = 21
_ICON_SIZE_TOOL = 30
_ARROW_SIZE = 18
_ARROW_CIRCLE = 36


class SectionLabel(QLabel):
    """Quiet uppercase group label (the sidebar's TOOLS label).

    Styled entirely by the ``QLabel#SidebarGroup`` QSS rule (caption size,
    semibold, muted, +0.8px tracking) so it tracks theme changes for free.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("SidebarGroup")


class SidebarNavItem(QWidget):
    """One compact sidebar destination: outline icon + text label.

    Visual states (all token-driven via the ``QWidget#SidebarNavItem``
    QSS rules in theme.py):
      • default  — transparent bg, ``icon`` tint, ``SidebarLabel`` typography
      • hover    — a 5% ink wash
      • active   — the reference's pale-sage pill (``accent_soft``) +
                   accent-tinted icon and label
      • focus    — the strong sage outline (keyboard navigation)

    The active state is a Qt dynamic property (``active``) so the QSS
    selector ``[active="true"]`` restyles without re-building the widget.
    ``clicked`` is emitted on press; Space/Enter trigger it too (keyboard
    parity).  Navigation ROUTING is intentionally NOT implemented here —
    the M2 shell decides what a click means.
    """

    clicked = Signal()

    def __init__(
        self,
        icon_name: str,
        label: str,
        tall: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("SidebarNavItem")
        # A plain QWidget paints app-stylesheet backgrounds ONLY with this
        # attribute — without it the pale-sage active pill silently
        # vanishes inside any real parent (the V0.6.79 overlay catch; a
        # direct widget grab hides the bug, a window render exposes it).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # V0.6.79: the reference's Home pill is ~45 px against the ~37 px
        # tool rows — the tall variant is the selected destination's
        # slightly roomier pill.
        self.setFixedHeight(_NAV_ITEM_TALL if tall else _NAV_ITEM_HEIGHT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 2, 12, 2)
        # V0.6.82: the reference's icon→label air — the label ink lands at
        # rail x≈93 (icon box [50..71] + 22), matching the measured x=93.
        lay.setSpacing(22)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_SIZE_NAV, _ICON_SIZE_NAV)
        lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignLeft)

        self._text_label = QLabel(label)
        self._text_label.setObjectName("SidebarLabel")
        lay.addWidget(self._text_label, 1)

        self._apply_style()

    # ── state ───────────────────────────────────────────────────────────
    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        """Mark this destination as the current one (restyles immediately)."""
        self._active = bool(active)
        self.setProperty("active", self._active)
        self._apply_style()
        # The QSS property selector ([active="true"]) only re-evaluates on
        # a style repolish — without these two lines the pale-sage pill
        # never paints (the V0.6.79 overlay catch).
        self.style().unpolish(self)
        self.style().polish(self)

    # ── styling ─────────────────────────────────────────────────────────
    def _apply_style(self) -> None:
        """Icon tint + label colour only — the surface states (idle wash,
        pale-sage active pill, focus ring) live in the app QSS rules."""
        p = theme_manager.palette
        tint = p.accent if self._active else p.icon
        self._icon_label.setPixmap(
            icon(self._icon_name, tint, _ICON_SIZE_NAV, _ICON_STROKE_DASH).pixmap(
                _ICON_SIZE_NAV, _ICON_SIZE_NAV
            )
        )
        color = p.accent if self._active else p.text_primary
        self._text_label.setStyleSheet(f"color: {color}; background: transparent;")

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles (theme toggle hook)."""
        self._apply_style()

    # ── interaction ─────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class _ArrowAffordance(QLabel):
    """The reference's pale circular arrow — a quiet disc with a right
    chevron, tinted per theme (on the featured card it inverts)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_ARROW_CIRCLE, _ARROW_CIRCLE)
        self._paint()

    def _paint(self) -> None:
        from PySide6.QtCore import QPointF, QSize
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

        p = theme_manager.palette
        featured = getattr(self, "_featured", False)
        disc = QColor(p.text_on_accent) if featured else QColor(p.bg_elevated)
        if featured:
            # the reference's disc is a SOFT ivory, not stark white
            disc.setAlpha(216)
        glyph = QColor(p.accent if featured else p.text_secondary)
        pm = QPixmap(_ARROW_CIRCLE, _ARROW_CIRCLE)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(disc)
        painter.drawEllipse(0, 0, _ARROW_CIRCLE, _ARROW_CIRCLE)
        # chevron-right glyph, stroke ~2px
        pen = QPen(glyph, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        # V0.6.82: the reference's arrow is a full arrow WITH A STEM (→),
        # not a bare chevron — the zoomed card comparison caught it.
        cx, cy = _ARROW_CIRCLE / 2, _ARROW_CIRCLE / 2
        painter.drawLine(QPointF(cx - 8, cy), QPointF(cx + 5, cy))
        path = QPainterPath()
        path.moveTo(QPointF(cx - 1, cy - 6))
        path.lineTo(QPointF(cx + 6, cy))
        path.lineTo(QPointF(cx - 1, cy + 6))
        painter.drawPath(path)
        painter.end()
        self.setPixmap(
            pm.scaled(
                QSize(_ARROW_CIRCLE, _ARROW_CIRCLE),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_featured(self, featured: bool) -> None:
        self._featured = featured
        self._paint()

    def refresh_theme(self) -> None:
        self._paint()


class QuickToolCard(QFrame):
    """The reference's Quick Tools grid card: a HORIZONTAL row — large
    sage outline icon at the left, title + one-line description stacked
    in the middle, the pale circular arrow affordance near the right
    edge. The ninth ``featured`` variant is the deep forest-green
    "Full Conversion Wizard" card (light type, inverted arrow disc).

    Entire card is the click target; hover lifts the border to the
    accent, focus shows the strong outline (keyboard navigation).
    """

    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        title: str,
        description: str = "",
        icon_name: str = "file-text",
        featured: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._icon_name = icon_name
        self._featured = featured
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("FeatureToolCard" if featured else "QuickToolCard")
        # V0.6.82 (Round-2 correction): the reference's card is ~124-125 px
        # tall (row bands measured [510..634]/[646..770]/[781..912] against
        # the previous 119-120) — the minimum rises so the rendered card
        # lands there (min + borders ≈ rendered).
        self.setMinimumHeight(122)
        self._arrow = _ArrowAffordance()
        self._arrow.set_featured(featured)

        # V0.6.80: the reference's card insets — the glyph sits ~32 px in
        # from the card's left edge, ~10 px to the title, ~26 px of air
        # before the arrow disc at the right. V0.6.82: the icon→text gap
        # widens to 24 so the title ink lands at card+~86 (reference +90,
        # was +66) — the reference's text column is visibly airier.
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 16, 20, 16)
        lay.setSpacing(24)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_SIZE_TOOL, _ICON_SIZE_TOOL)
        lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        # V0.6.82: the reference's text block is VERTICALLY CENTERED in the
        # card (title ink at card+26, desc ink ending card−23; the old
        # trailing-only stretch pinned it to the top, leaving ~49 px of dead
        # air under the description).
        text_col.addStretch(1)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("ToolTitle")
        text_col.addWidget(self._title_label)
        if description:
            self._desc_label = QLabel(description)
            self._desc_label.setObjectName("ToolDesc")
            # Wrap (never a single-line minimum): a card's width floor is
            # set by its TITLE, so the grid's 3-column minimum stays well
            # under the viewport — a one-line desc minimum would inflate
            # the whole home view past its scroll viewport.
            self._desc_label.setWordWrap(True)
            text_col.addWidget(self._desc_label)
        else:
            self._desc_label = None
        text_col.addStretch()
        lay.addLayout(text_col, 1)

        lay.addWidget(self._arrow, 0, Qt.AlignmentFlag.AlignVCenter)

        self._apply_style()

    @property
    def key(self) -> str:
        return self._key

    def _apply_style(self) -> None:
        p = theme_manager.palette
        if self._featured:
            self.setStyleSheet(
                f"""
                QFrame#FeatureToolCard {{
                    background-color: {p.accent};
                    border: 1px solid {p.accent};
                    border-radius: {RADIUS.card}px;
                }}
                QFrame#FeatureToolCard:hover {{
                    background-color: {p.accent_hover};
                    border: 1px solid {p.accent_hover};
                }}
                QFrame#FeatureToolCard:focus {{
                    border: 1px solid {p.text_on_accent};
                }}
                """
            )
            self._title_label.setStyleSheet(
                f"color: {p.text_on_accent}; background: transparent; border: none;"
            )
            if self._desc_label is not None:
                self._desc_label.setStyleSheet(
                    f"color: {p.text_on_accent}; background: transparent; border: none;"
                )
            self._icon_label.setPixmap(
                icon(self._icon_name, p.text_on_accent, _ICON_SIZE_TOOL, _ICON_STROKE_DASH).pixmap(
                    _ICON_SIZE_TOOL, _ICON_SIZE_TOOL
                )
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame#QuickToolCard {{
                    background-color: {p.bg_surface};
                    border: 1px solid {p.border};
                    border-radius: {RADIUS.card}px;
                }}
                QFrame#QuickToolCard:hover {{
                    background-color: {p.bg_surface};
                    border: 1px solid {p.accent};
                }}
                QFrame#QuickToolCard:focus {{
                    border: 1px solid {p.border_strong};
                }}
                QFrame#QuickToolCard:pressed {{
                    background: {p.bg_elevated};
                }}
                """
            )
            self._title_label.setStyleSheet("background: transparent; border: none;")
            if self._desc_label is not None:
                self._desc_label.setStyleSheet("background: transparent; border: none;")
            # The reference's card glyphs are the muted sage (#53624B).
            self._icon_label.setPixmap(
                icon(self._icon_name, p.sage, _ICON_SIZE_TOOL, _ICON_STROKE_DASH).pixmap(
                    _ICON_SIZE_TOOL, _ICON_SIZE_TOOL
                )
            )
        self._arrow.refresh_theme()

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles (theme toggle hook)."""
        self._apply_style()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)


__all__ = ["SectionLabel", "SidebarNavItem", "QuickToolCard"]
