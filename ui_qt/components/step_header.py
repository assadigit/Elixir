"""Numbered step header — a small amber badge + title + optional caption."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui_qt.theme import FONT, SPACE, theme_manager


class StepHeader(QWidget):
    """A numbered step indicator: amber circular badge + title + caption.

    Renders like::

        ┌────┐
        │ 1  │  What are you converting?
        └────┘  Choose the document type to apply the right defaults.
    """

    def __init__(
        self,
        number: int,
        title: str,
        caption: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.md)

        self.badge = QFrame()
        self.badge.setObjectName("StepBadge")
        badge_lay = QVBoxLayout(self.badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        self.badge_label = QLabel(str(number))
        # V7.4.0: use palette text_on_accent (works in both light + dark modes)
        # instead of the hardcoded #1A1410 which was invisible in dark mode.
        self._badge_style()
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lay.addWidget(self.badge_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("Step")
        text_col.addWidget(self.title_label)
        if caption:
            self.caption_label = QLabel(caption)
            self.caption_label.setObjectName("Caption")
            text_col.addWidget(self.caption_label)
        else:
            self.caption_label = None  # type: ignore[assignment]

        lay.addWidget(self.badge)
        lay.addLayout(text_col)
        lay.addStretch()

    def _badge_style(self) -> None:
        p = theme_manager.palette
        self.badge_label.setStyleSheet(
            f"color: {p.text_on_accent}; font-weight: 700; font-size: {FONT.subhead}px;"
            " background: transparent; border: none;"
        )

    def refresh_theme(self) -> None:
        """V7.4.0: re-apply palette-dependent badge colour on theme toggle."""
        self._badge_style()

    def set_number(self, n: int) -> None:
        self.badge_label.setText(str(n))

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)
