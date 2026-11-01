"""M1 (UI/UX redesign): dashboard primitives — M2-ready, NOT yet wired in.

Three small reusable widgets for the M2 dashboard milestone, built on the
M1 visual foundation (spec §4/§5 tokens + the new QSS label rules):

  • ``SectionLabel``      — the quiet uppercase group label ("PROCESSING",
                            "AUDIO") used above sidebar groups / grid rows.
  • ``SidebarNavItem``    — one compact fixed-sidebar destination row
                            (icon + label, hover/active states).
  • ``QuickToolCard``     — the compact secondary-tool grid card
                            (icon + title + optional one-line description).

M1 scope note: these are deliberately UNUSED by any view yet (the M1
milestone changes no dashboard layout).  The M2 session wires them into
the new shell.  Until then this module is exercised by
``tests/test_m1_theme_tokens.py`` (source pins) only.

All three follow the ``ToolCard`` house pattern: objectName-scoped QSS,
``_apply_style()`` derived from ``theme_manager.palette``, a public
``refresh_theme()``, and no fixed coordinates (Qt layouts + size policies).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.components.icons import icon
from ui_qt.theme import FONT, RADIUS, theme_manager

# Hit-target floor (spec §10: "usable hit targets") — desktop compact.
_NAV_ITEM_HEIGHT = 34
_ICON_SIZE_NAV = 18
_ICON_SIZE_TOOL = 26


class SectionLabel(QLabel):
    """Quiet uppercase group label (sidebar groups, grid section headers).

    Styled entirely by the ``QLabel#SidebarGroup`` QSS rule (caption size,
    semibold, muted, +0.8px tracking) so it tracks theme changes for free.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("SidebarGroup")


class SidebarNavItem(QWidget):
    """One compact sidebar destination: outline icon + text label.

    Visual states (all token-driven):
      • default  — transparent bg, ``icon`` tint, ``SidebarLabel`` typography
      • hover    — ``bg_elevated`` wash
      • active   — ``accent_soft`` wash + accent-tinted icon and label
      • disabled — ``text_muted`` label, muted icon

    The active state is a Qt dynamic property (``active``) so the QSS
    selector ``[active="true"]`` restyles without re-building the widget.
    ``clicked`` is emitted on press; Space/Enter trigger it too (keyboard
    parity).  Navigation ROUTING is intentionally NOT implemented here —
    the M2 shell decides what a click means.
    """

    clicked = Signal()

    def __init__(self, icon_name: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("SidebarNavItem")
        self.setFixedHeight(_NAV_ITEM_HEIGHT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(8)

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
        self.style().unpolish(self)
        self.style().polish(self)

    # ── styling ─────────────────────────────────────────────────────────
    def _apply_style(self) -> None:
        p = theme_manager.palette
        self.setStyleSheet(
            f"""
            QWidget#SidebarNavItem {{
                background: transparent;
                border: none;
                border-radius: {RADIUS.sm}px;
            }}
            QWidget#SidebarNavItem:hover {{
                background: {p.bg_elevated};
            }}
            QWidget#SidebarNavItem:focus {{
                border: 1px solid {p.border_strong};
            }}
            QWidget#SidebarNavItem[active="true"] {{
                background: {p.accent_soft};
            }}
            """
        )
        tint = p.accent if self._active else p.icon
        self._icon_label.setPixmap(
            icon(self._icon_name, tint, _ICON_SIZE_NAV).pixmap(_ICON_SIZE_NAV, _ICON_SIZE_NAV)
        )
        color = p.accent if self._active else p.text_secondary
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


class QuickToolCard(QFrame):
    """Compact secondary-tool grid card: icon, title, optional one-line hint.

    Deliberately smaller than the legacy ``ToolCard`` (no giant icon well,
    no primary variant — the hero owns that role in M2).  Entire card is the
    click target; hover lifts the border to the accent, focus shows the
    strong outline (keyboard navigation), pressed dims to ``bg_elevated``.
    """

    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        title: str,
        description: str = "",
        icon_name: str = "file-text",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("QuickToolCard")
        self.setMinimumHeight(76)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_SIZE_TOOL, _ICON_SIZE_TOOL)
        lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignLeft)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("ToolTitle")
        lay.addWidget(self._title_label)

        if description:
            self._desc_label = QLabel(description)
            self._desc_label.setWordWrap(True)
            lay.addWidget(self._desc_label)
        else:
            self._desc_label = None

        self._apply_style()

    @property
    def key(self) -> str:
        return self._key

    def _apply_style(self) -> None:
        p = theme_manager.palette
        self.setStyleSheet(
            f"""
            QFrame#QuickToolCard {{
                background: {p.bg_surface};
                border: 1px solid {p.border};
                border-radius: {RADIUS.lg}px;
            }}
            QFrame#QuickToolCard:hover {{
                background: {p.bg_surface};
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
        self._icon_label.setPixmap(
            icon(self._icon_name, p.icon, _ICON_SIZE_TOOL).pixmap(_ICON_SIZE_TOOL, _ICON_SIZE_TOOL)
        )
        if self._desc_label is not None:
            self._desc_label.setStyleSheet(
                f"font-size: {FONT.caption}px; color: {p.text_muted};"
                f" background: transparent; border: none;"
            )

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles (theme toggle hook)."""
        self._apply_style()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)


__all__ = ["SectionLabel", "SidebarNavItem", "QuickToolCard"]
