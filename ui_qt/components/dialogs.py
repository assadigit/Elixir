"""Small styled modal dialogs — password prompt, etc.

Kept here so the rest of the app imports a consistent, theme-aware dialog
instead of the default ``QInputDialog`` (which ignores the app QSS on some
platforms).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class PasswordDialog(QDialog):
    """A themed password prompt for encrypted PDFs.

    Returns the entered password via :pymeth:`password`, or ``None`` if the
    user cancelled.
    """

    def __init__(self, file_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Password required")
        self.setMinimumWidth(420)
        self._password: str | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        head = QLabel("🔒  This PDF is encrypted")
        head.setObjectName("H2")
        lay.addWidget(head)

        body = QLabel(f"“{file_name}” is password-protected. Enter the password to continue.")
        body.setObjectName("Body")
        body.setWordWrap(True)
        lay.addWidget(body)

        self.field = QLineEdit()
        self.field.setEchoMode(QLineEdit.Password)
        self.field.setPlaceholderText("Password")
        self.field.returnPressed.connect(self._on_accept)
        lay.addWidget(self.field)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("Secondary")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.field.setFocus()

    def _on_accept(self) -> None:
        self._password = self.field.text()
        self.accept()

    def password(self) -> str | None:
        return self._password


def ask_password(file_path: Path, parent: QWidget | None = None) -> str | None:
    """Convenience: open a :class:`PasswordDialog` and return the password."""
    dlg = PasswordDialog(file_path.name, parent)
    dlg.exec()
    return dlg.password()
