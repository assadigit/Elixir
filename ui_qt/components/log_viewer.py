"""Colour-coded, auto-scrolling log viewer based on QTextBrowser."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QTextBrowser, QWidget

from ui_qt.theme import theme_manager


class LogViewer(QTextBrowser):
    """Append-only log view with per-level colouring and auto-scroll.

    V4.7.12: Restored right-click context menu with Copy / Copy All /
    Clear options so users can copy logs for debugging.
    """

    LEVEL_COLORS = {
        "INFO": "text_secondary",
        "DEBUG": "text_muted",
        "WARNING": "warning",
        "ERROR": "error",
        "SUCCESS": "success",
    }

    def __init__(self, parent: QWidget | None = None, *, max_lines: int = 4000) -> None:
        super().__init__(parent)
        self._max_lines = max_lines
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setLineWrapMode(QTextBrowser.WidgetWidth)
        # V4.7.12: Ensure text selection + copy works
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._refresh_colors()

    # V4.7.12: Context menu with copy options
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        # V4.7.14: QAction is in QtGui, not QtWidgets in some PySide6 versions
        from PySide6.QtGui import QAction

        copy_all_action = QAction("📋  Copy All", self)
        copy_all_action.triggered.connect(self._copy_all)
        clear_action = QAction("🗑  Clear Log", self)
        clear_action.triggered.connect(self.clear)
        menu.insertAction(menu.actions()[0] if menu.actions() else None, copy_all_action)
        menu.insertAction(copy_all_action, clear_action)
        menu.addSeparator()
        menu.exec(event.globalPos())

    def _copy_all(self):
        """Copy all log text to clipboard."""
        text = self.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    # ── public API ───────────────────────────────────────────────────────
    def append(self, message: str, level: str = "INFO") -> None:  # type: ignore[override]
        """Append ``[HH:MM:SS] [LEVEL] message`` with colour for ``level``."""
        from PySide6.QtGui import QColor, QFont

        p = theme_manager.palette
        ts = datetime.now().strftime("%H:%M:%S")
        color_attr = self.LEVEL_COLORS.get(level.upper(), "text_secondary")
        color = getattr(p, color_attr)

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        # timestamp (muted)
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor(p.text_muted))
        cursor.setCharFormat(ts_fmt)
        cursor.insertText(f"[{ts}] ")

        # level tag (coloured, medium weight)
        lvl_fmt = QTextCharFormat()
        lvl_fmt.setForeground(QColor(color))
        lvl_fmt.setFontWeight(QFont.Weight.Medium)
        cursor.setCharFormat(lvl_fmt)
        cursor.insertText(f"[{level:<7}] ")

        # message body (primary)
        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(p.text_primary))
        cursor.setCharFormat(msg_fmt)
        cursor.insertText(message + "\n")

        # auto-scroll
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

        # trim if too long
        doc = self.document()
        if doc.blockCount() > self._max_lines:
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(
                QTextCursor.Down,
                QTextCursor.KeepAnchor,
                doc.blockCount() - self._max_lines,
            )
            cursor.removeSelectedText()
            cursor.deleteChar()

    def log(self, message: str, level: str = "INFO") -> None:
        """Alias for :pymeth:`append` — mirrors the old Tkinter API."""
        self.append(message, level)

    def clear(self) -> None:  # type: ignore[override]
        super().clear()

    def _refresh_colors(self) -> None:
        p = theme_manager.palette
        self.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {p.bg_input};
                border: 1px solid {p.border};
                border-radius: 10px;
                padding: 8px;
                color: {p.text_primary};
                font-family: "SF Mono", "JetBrains Mono", "Consolas", "Menlo", monospace;
                font-size: 12px;
            }}
            """
        )

    def refresh_theme(self) -> None:
        self._refresh_colors()
