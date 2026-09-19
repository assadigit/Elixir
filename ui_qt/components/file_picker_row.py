"""A labelled file/folder picker row: label + read-only path field + Browse button."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class FilePickerRow(QWidget):
    """A label + path field + browse button.

    ``mode`` controls what the Browse dialog accepts:
      - ``"file"``      → a single file (optionally filtered by ``filter``)
      - ``"folder"``    → a directory (alias: ``"dir"``, ``"directory"``)
      - ``"save_file"`` → a save path (file may not exist yet)

    Emits :pyattr:`path_changed(str)` whenever the chosen path changes.
    """

    path_changed = Signal(str)

    def __init__(
        self,
        label: str,
        mode: str = "file",
        *,
        placeholder: str = "",
        caption: str = "Browse…",
        filter: str = "All files (*)",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # V3.1.6: Normalize mode — accept "dir" and "directory" as aliases for "folder"
        # so a typo doesn't silently fall through to the file-open dialog.
        mode = mode.lower().strip()
        if mode in ("dir", "directory"):
            mode = "folder"
        self._mode = mode
        self._filter = filter
        self._caption = caption

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("Body")
        self.label.setMinimumWidth(72)
        lay.addWidget(self.label)

        self.field = QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText(placeholder)
        self.field.setObjectName("PathField")
        lay.addWidget(self.field, 1)

        self.browse_btn = QPushButton(caption)
        self.browse_btn.setObjectName("Compact")
        self.browse_btn.setCursor(__import__("PySide6").QtCore.Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._on_browse)
        lay.addWidget(self.browse_btn)

    # ── public API ───────────────────────────────────────────────────────
    def path(self) -> Path | None:
        text = self.field.text().strip()
        return Path(text) if text else None

    def set_path(self, path) -> None:
        self.field.setText(str(path) if path else "")

    def set_browse_enabled(self, enabled: bool) -> None:
        self.browse_btn.setEnabled(enabled)

    def set_label(self, label: str) -> None:
        self.label.setText(label)

    # ── browse ───────────────────────────────────────────────────────────
    def _on_browse(self) -> None:
        start_dir = self.field.text() or str(Path.home())

        if self._mode == "folder":
            chosen = QFileDialog.getExistingDirectory(self, self._caption, start_dir)
        elif self._mode == "save_file":
            chosen, _ = QFileDialog.getSaveFileName(self, self._caption, start_dir, self._filter)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, self._caption, start_dir, self._filter)

        if chosen:
            self.field.setText(chosen)
            self.path_changed.emit(chosen)
