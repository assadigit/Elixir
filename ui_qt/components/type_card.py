"""Document-type selection card — V1.5 centered design with large 64px icons.

Layout (top to bottom, all centered):
  [64×64 SVG icon]
  [Title — bold]
  [Subtitle — small gray]
  [✓ Selected — when selected]

The large icon gives each preset a strong visual identity; the centered
stack keeps the card compact (no stretch, no void).
"""

from __future__ import annotations

from PySide6.QtCore import Property, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import pixmap, pixmap_with_png_fallback
from ui_qt.theme import theme_manager


class TypeCard(QFrame):
    """A single selectable document-type card (V1.5 centered, big-icon style).

    V4.7.25: Supports PNG icons from ``assets/icons/{png_name}.png`` with
    automatic SVG fallback. Pass ``png_name`` (typically the preset key) to
    enable PNG lookup. If the PNG doesn't exist, the SVG icon is used.
    """

    selected = Signal(str)  # value

    def __init__(
        self,
        value: str,
        icon_name: str,
        title: str,
        subtitle: str,
        png_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._selected = False
        self._icon_name = icon_name
        self._png_name = png_name

        self.setObjectName("TypeCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(160)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(6)

        # ── big icon (centered, 64×64) ──────────────────────────────────
        # V0.4.20: explicit AlignHCenter — a fixed-size QLabel added to a
        # QVBoxLayout with default alignment lands at the LEFT edge of the
        # cell (Qt keeps the origin-side position when the widget cannot
        # fill the cell), which rendered the icon top-LEFT of every card
        # (user-reported) despite the "centered" design intent since V1.5.
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(64, 64)
        lay.addWidget(self.icon_label, 0, Qt.AlignHCenter)

        # ── title (centered) ────────────────────────────────────────────
        self.title_label = QLabel(title)
        self.title_label.setObjectName("H3")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; background: transparent;"
        )
        lay.addWidget(self.title_label)

        # ── subtitle (centered, wraps) ──────────────────────────────────
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Caption")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("font-size: 11px; background: transparent;")
        lay.addWidget(self.subtitle_label)

        # ── selected hint row (checkmark + "Selected", centered) ────────
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        hint_row.setSpacing(5)
        hint_row.addStretch()
        self.check_label = QLabel()
        self.check_label.setFixedSize(14, 14)
        self.check_label.setVisible(False)
        hint_row.addWidget(self.check_label)
        self.hint_label = QLabel("Selected")
        self.hint_label.setObjectName("SelectionHint")
        self.hint_label.setStyleSheet(
            f"color: {theme_manager.palette.accent}; font-size: 11px;"
            f" font-weight: 500; background: transparent;"
        )
        self.hint_label.setVisible(False)
        hint_row.addWidget(self.hint_label)
        hint_row.addStretch()
        lay.addLayout(hint_row)

        self._refresh_colors()
        self._refresh_icon()

    # ── public API ───────────────────────────────────────────────────────
    @property
    def value(self) -> str:
        return self._value

    def get_value(self) -> str:
        return self._value

    @Property(bool)
    def is_selected(self) -> bool:  # type: ignore[override]
        return self._selected

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.check_label.setVisible(selected)
        self.hint_label.setVisible(selected)
        self._refresh_colors()
        self._refresh_icon()
        self.style().unpolish(self)
        self.style().polish(self)
        if selected:
            self.selected.emit(self._value)

    # ── internal ─────────────────────────────────────────────────────────
    def _refresh_colors(self) -> None:
        p = theme_manager.palette
        if self._selected:
            self.setStyleSheet(
                f"""
                QFrame#TypeCard {{
                    background-color: {p.accent_soft};
                    border: 1.5px solid {p.accent};
                    border-radius: 10px;
                }}
                QFrame#TypeCard:hover {{
                    border: 1.5px solid {p.accent_hover};
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame#TypeCard {{
                    background-color: {p.bg_surface};
                    border: 1px solid {p.border};
                    border-radius: 10px;
                }}
                QFrame#TypeCard:hover {{
                    border: 1px solid {p.border_strong};
                    background-color: {p.bg_elevated};
                }}
                """
            )

    def _refresh_icon(self) -> None:
        p = theme_manager.palette
        color = p.accent if self._selected else p.text_primary
        # V4.7.25: Try PNG first (assets/icons/{png_name}.png), fall back to SVG.
        # V5.3.3: Pass svg_fallback so the SVG icon name is used (not the preset key).
        if self._png_name:
            pm: QPixmap = pixmap_with_png_fallback(
                self._png_name, color=color, size=64, svg_fallback=self._icon_name
            )
        else:
            pm: QPixmap = pixmap(self._icon_name, color=color, size=64)
        self.icon_label.setPixmap(pm)
        self.check_label.setPixmap(pixmap("check", color=p.accent, size=14))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.set_selected(True)
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        self._refresh_colors()
        self._refresh_icon()
        self.style().unpolish(self)
        self.style().polish(self)
