"""V11.0.0: ToolCard — flat card with hover elevation, SVG/PNG-ready icon system.

Replaces the preset TypeCard on the primary page. Each card represents a
tool or service (not a document preset). The "Full Conversion" card is
visually distinct (primary CTA — larger, accent border).

Icon system: currently uses emoji strings, but the ``icon_source``
parameter accepts either:
  - An emoji string (e.g. "🚀") — rendered as text
  - A file path (e.g. "assets/icons/rocket.svg") — rendered as QPixmap
  - An icon name (e.g. "rocket") — looked up in the existing icon system

This makes the transition to SVG/PNG icons a data-only change (no code
modification needed — just swap the emoji strings for file paths in the
dashboard definition).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.theme import FONT, theme_manager


class ToolCard(QFrame):
    """A flat tool card with hover elevation.

    Signals:
        clicked: Emitted when the card is clicked.

    Visual states:
        - Default: flat, subtle border
        - Hover: elevated (box-shadow simulation via border + background change)
        - Primary (is_primary=True): accent border + larger + bold title
    """

    clicked = Signal(str)  # emits the tool key

    def __init__(
        self,
        key: str,
        title: str,
        subtitle: str,
        icon_source: str = "",
        category: str = "",
        is_primary: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._key = key
        self._is_primary = is_primary
        self._hovered = False
        self.set_cursor = True  # accept cursor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ToolCard" if not is_primary else "ToolCardPrimary")
        self.setMinimumHeight(140 if not is_primary else 160)

        # Layout — V11.0.0: larger cards with more icon space
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)

        # Icon + title row — icon is on top, title below (vertical layout for more icon space)
        icon_row = QHBoxLayout()
        icon_row.setSpacing(0)

        # Icon (emoji or image) — V11.0.0: bigger icon area
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(48 if not is_primary else 56, 48 if not is_primary else 56)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_icon(icon_source)
        icon_row.addStretch()
        icon_row.addWidget(self._icon_label)
        icon_row.addStretch()
        lay.addLayout(icon_row)

        # Title (below icon, centered)
        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"font-size: {FONT.subhead + (2 if is_primary else 0)}px;"
            f" font-weight: {'700' if is_primary else '600'};"
            f" color: {theme_manager.palette.text_primary};"
            f" background: transparent; border: none;"
        )
        lay.addWidget(self._title_label)

        # Subtitle (centered, below title)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet(
            f"font-size: {FONT.caption}px;"
            f" color: {theme_manager.palette.text_muted};"
            f" background: transparent; border: none;"
        )
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._subtitle_label)

        # V13.31.0 (#8): Removed category label from bottom-right corner.
        # It was redundant with the section header above each row.
        # The category is still passed to the constructor for potential
        # future use, but not displayed on the card.

        self._apply_style()

    def _set_icon(self, icon_source: str) -> None:
        """Set the icon from emoji string, file path, or icon name.

        V11: supports emoji strings. Future: swap to SVG/PNG paths
        without changing this code — just pass a file path instead.
        """
        if not icon_source:
            self._icon_label.setText("📋")
            return

        # Check if it's a file path (has a file extension)
        if "." in icon_source and len(icon_source) > 4:
            p = Path(icon_source)
            if p.exists():
                pixmap = QPixmap(str(p))
                if not pixmap.isNull():
                    size = 48 if self._is_primary else 40
                    self._icon_label.setPixmap(
                        pixmap.scaled(
                            size,
                            size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    return

        # Check if it's an icon name (lookup in the icon system)
        if icon_source and not any(ord(c) > 127 for c in icon_source):
            # ASCII-only — might be an icon name
            try:
                from ui_qt.components.icons import icon

                p = theme_manager.palette
                size = 48 if self._is_primary else 40
                color = p.accent if self._is_primary else p.text_secondary
                qicon = icon(icon_source, color, size)
                if qicon is not None and not qicon.isNull():
                    self._icon_label.setPixmap(qicon.pixmap(size, size))
                    return
            except Exception:
                pass

        # Default: treat as emoji string
        size = 48 if self._is_primary else 40
        self._icon_label.setStyleSheet(
            f"font-size: {size}px; background: transparent; border: none;"
        )
        self._icon_label.setText(icon_source)

    def _apply_style(self) -> None:
        """Apply the flat card style with hover elevation.

        V13.30.0: Rounder boxes — border-radius increased from 10px → 16px
        (standard) and 12px → 20px (primary). Per user's UX preference
        for rounder boxes.
        """
        p = theme_manager.palette

        if self._is_primary:
            # V13.30.0: Rounder primary CTA — 20px radius (was 12px)
            self.setStyleSheet(f"""
                QFrame#ToolCardPrimary {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {p.accent_soft}, stop:1 {p.bg_surface});
                    border: 2px solid {p.accent};
                    border-radius: 20px;
                }}
                QFrame#ToolCardPrimary:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {p.accent_soft}, stop:0.5 {p.bg_surface});
                    border: 2px solid {p.accent};
                    border-radius: 20px;
                }}
            """)
        else:
            # V13.30.0: Rounder standard cards — 16px radius (was 10px)
            self.setStyleSheet(f"""
                QFrame#ToolCard {{
                    background: {p.bg_surface};
                    border: 1px solid {p.border};
                    border-radius: 16px;
                }}
                QFrame#ToolCard:hover {{
                    background: {p.bg_elevated};
                    border: 1px solid {p.accent};
                    border-radius: 16px;
                }}
            """)

    def refresh_theme(self) -> None:
        """Re-apply theme-dependent styles."""
        self._apply_style()
        # Re-apply title/subtitle colors
        self._title_label.setStyleSheet(
            f"font-size: {FONT.subhead + (2 if self._is_primary else 0)}px;"
            f" font-weight: {'700' if self._is_primary else '600'};"
            f" color: {theme_manager.palette.text_primary};"
            f" background: transparent; border: none;"
        )
        self._subtitle_label.setStyleSheet(
            f"font-size: {FONT.caption}px;"
            f" color: {theme_manager.palette.text_muted};"
            f" background: transparent; border: none;"
        )

    # ── Mouse events ────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)

    def enterEvent(self, event) -> None:
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        super().leaveEvent(event)

    @property
    def key(self) -> str:
        return self._key

    @property
    def is_primary(self) -> bool:
        return self._is_primary


__all__ = ["ToolCard"]
