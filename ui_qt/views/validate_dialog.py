"""Validation dialog — hallucination / coverage checker.

Replaces the old Tkinter ``ValidationView``.  Opened from the Tools menu.
Compares a source Markdown file against its summary and reports lexical
coverage, faithfulness, and key-term gaps.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components import FilePickerRow
from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager


class ValidateDialog(QDialog):
    """Modal validation tool."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Validate summaries")
        self.resize(640, 520)  # V7.4.0: was 760x640 — compact

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        head = QLabel("🔍  Validate summary quality")
        head.setObjectName("H1")
        root.addWidget(head)
        sub = QLabel("Compare a source Markdown file against its summary to check coverage and faithfulness.")
        sub.setObjectName("Caption")
        sub.setWordWrap(True)
        root.addWidget(sub)

        self.source_picker = FilePickerRow(
            "Source", mode="file", placeholder="Full Markdown (source)",
            filter="Markdown (*.md);;All files (*)",
        )
        root.addWidget(self.source_picker)

        self.summary_picker = FilePickerRow(
            "Summary", mode="file", placeholder="Summary file (optional)",
            filter="Markdown (*.md);;All files (*)",
        )
        root.addWidget(self.summary_picker)

        # action row
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.auto_btn = QPushButton("  Auto-detect from folder")
        self.auto_btn.setIcon(icon("search", theme_manager.palette.text_secondary, 14))
        self.auto_btn.clicked.connect(self._auto_detect)
        actions.addWidget(self.auto_btn)
        actions.addStretch()
        self.run_btn = QPushButton("  Run validation")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setIcon(icon("play", theme_manager.palette.text_on_accent, 15))
        self.run_btn.clicked.connect(self._run)
        actions.addWidget(self.run_btn)
        root.addLayout(actions)

        self.result = QTextBrowser()
        self.result.setOpenExternalLinks(False)
        self.result.setPlaceholderText("Results will appear here.")
        root.addWidget(self.result, 1)

    # ── auto-detect source + summary in a folder ─────────────────────────
    def _auto_detect(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose an output folder")
        if not folder:
            return
        fp = Path(folder)
        candidates = list(fp.glob("*.md"))
        main = [f for f in candidates if ".summary." not in f.name and ".Keypoints." not in f.name]
        if main:
            base = fp.name
            chosen = next((f for f in main if f.stem == base), main[0])
            self.source_picker.set_path(chosen)
        summ = [f for f in candidates if ".summary." in f.name]
        if summ:
            self.summary_picker.set_path(summ[0])

    # ── run validation ───────────────────────────────────────────────────
    def _run(self) -> None:
        src = self.source_picker.path()
        if not src or not src.exists():
            QMessageBox.critical(self, "No source", "Please select a valid source Markdown file.")
            return
        summ = self.summary_picker.path()
        if not summ or not summ.exists():
            # try sibling *.summary.md
            cand = src.parent / f"{src.stem}.summary.md"
            if cand.exists():
                summ = cand
                self.summary_picker.set_path(cand)
            else:
                ret = QMessageBox.question(
                    self, "No summary",
                    "No summary file found. Continue with source-only analysis?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if ret != QMessageBox.Yes:
                    return
                summ = None

        self.run_btn.setEnabled(False)
        self.result.setPlainText("Validating…")

        try:
            from core.validation.validator import Validator
            v = Validator(src, summ)
            if not v.load():
                self.result.setPlainText("❌ Failed to load files.")
                return
            report = v.generate_report()
            self.result.setPlainText(report)
        except Exception as e:  # noqa: BLE001
            self.result.setPlainText(f"❌ Error: {e}")
        finally:
            self.run_btn.setEnabled(True)
