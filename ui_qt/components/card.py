"""A flat surface card — hairline border, rounded corners, optional padding."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


class Card(QFrame):
    """A simple bordered, rounded surface used to group content."""

    def __init__(
        self, parent: QWidget | None = None, *, padding: int = 16, spacing: int = 4
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        # Tight internal spacing — the Card's job is to group, not to add air
        # between every child.  Override via ``spacing=`` if needed.
        self._layout.setSpacing(spacing)

    def addWidget(self, widget: QWidget) -> None:  # type: ignore[override]
        self._layout.addWidget(widget)

    def addLayout(self, layout) -> None:
        self._layout.addLayout(layout)

    def addStretch(self) -> None:
        self._layout.addStretch()

    @property
    def inner(self) -> QVBoxLayout:
        return self._layout
