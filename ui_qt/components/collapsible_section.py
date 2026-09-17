"""Collapsible section — a header button that toggles a content area visible/hidden."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager


class CollapsibleSection(QFrame):
    """A disclosure widget: header row + collapsible content.

    The header shows a chevron that rotates conceptually (we swap the icon)
    and an optional title.  The body can host any single content widget.
    """

    def __init__(
        self,
        title: str = "",
        *,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Collapsible")
        self._expanded = expanded

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.header_btn = QPushButton()
        self.header_btn.setObjectName("CollapsibleHeader")
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(expanded)
        self.header_btn.setFlat(True)
        self.header_btn.setText("  " if not title else "  " + title)
        self.header_btn.clicked.connect(self._on_toggle)
        lay.addWidget(self.header_btn)

        self._content: QWidget | None = None
        self._content_lay = QVBoxLayout()
        self._content_lay.setContentsMargins(0, 4, 0, 0)
        self._content_lay.setSpacing(0)
        lay.addLayout(self._content_lay)

        self._refresh_style()
        self._apply_state()

    # ── public API ───────────────────────────────────────────────────────
    def set_content(self, widget: QWidget) -> None:
        if self._content is not None:
            self._content_lay.replaceWidget(self._content, widget)
            self._content.deleteLater()
        else:
            self._content_lay.addWidget(widget)
        self._content = widget
        self._apply_state()

    def set_title(self, title: str) -> None:
        self._title = title
        self.header_btn.setText("  " + title)
        self._apply_state()

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self.header_btn.setChecked(expanded)
        self._apply_state()

    def is_expanded(self) -> bool:
        return self._expanded

    # ── internal ─────────────────────────────────────────────────────────
    def _on_toggle(self) -> None:
        self._expanded = self.header_btn.isChecked()
        self._apply_state()

    def _apply_state(self) -> None:
        chev = "chevron-down" if self._expanded else "chevron-right"
        p = theme_manager.palette
        self.header_btn.setIcon(icon(chev, color=p.text_secondary, size=16))
        if self._content is not None:
            self._content.setVisible(self._expanded)

    def _refresh_style(self) -> None:
        p = theme_manager.palette
        self.setStyleSheet(
            f"""
            QFrame#Collapsible {{
                background: transparent;
                border: none;
            }}
            QPushButton#CollapsibleHeader {{
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 8px 10px;
                text-align: left;
                color: {p.text_primary};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#CollapsibleHeader:hover {{
                background-color: {p.bg_elevated};
            }}
            """
        )

    def refresh_theme(self) -> None:
        self._refresh_style()
        self._apply_state()
