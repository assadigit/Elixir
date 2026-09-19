"""Step 9: Live Logs — Step9Logs (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step9Logs
(back-compat facade).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ui_qt.components.log_viewer import LogViewer
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 9: Live Logs
# ════════════════════════════════════════════════════════════════════════════


class Step9Logs(WizardStep):
    """Live progress + logs during conversion."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        title = QLabel("Conversion in progress")
        title.setObjectName("H2")
        lay.addWidget(title)

        self.status_label = QLabel("Preparing...")
        self.status_label.setObjectName("Caption")
        lay.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        lay.addWidget(self.progress)

        # V10.25.0: Live elapsed timer — shows time since conversion started
        self.elapsed_label = QLabel("⏱️ Elapsed: 00:00:00")
        self.elapsed_label.setObjectName("Caption")
        self.elapsed_label.setStyleSheet(
            f"font-size: 10px; color: {theme_manager.palette.text_muted};"
            f" background: {theme_manager.palette.bg_input};"
            f" padding: 3px 8px; border-radius: 4px;"
        )
        lay.addWidget(self.elapsed_label)

        # V8.1.0: Hardware monitor status bar (GPU/CPU/RAM)
        self.hw_label = QLabel("📊 Hardware: (starting monitor…)")
        self.hw_label.setObjectName("Caption")
        self.hw_label.setStyleSheet(
            f"font-size: 10px; color: {theme_manager.palette.text_muted};"
            f" background: {theme_manager.palette.bg_input};"
            f" padding: 3px 8px; border-radius: 4px;"
        )
        lay.addWidget(self.hw_label)

        # V10.16.0 (E2): Live quality dashboard — per-chapter coverage/progress
        self.quality_label = QLabel("📊 Quality: waiting for first chapter…")
        self.quality_label.setObjectName("Caption")
        self.quality_label.setStyleSheet(
            f"font-size: 10px; color: {theme_manager.palette.text_muted};"
            f" background: {theme_manager.palette.bg_input};"
            f" padding: 3px 8px; border-radius: 4px;"
        )
        lay.addWidget(self.quality_label)

        # V10.18.0 (E3): Output preview pane — shows first 500 chars of
        # the latest generated output (summary, briefing, etc.)
        self.preview_label = QLabel("📄 Preview: (waiting for first output…)")
        self.preview_label.setObjectName("Caption")
        self.preview_label.setStyleSheet(
            f"font-size: 10px; color: {theme_manager.palette.text_muted};"
            f" background: {theme_manager.palette.bg_input};"
            f" padding: 4px 8px; border-radius: 4px;"
            f" max-height: 60px;"
        )
        self.preview_label.setWordWrap(True)
        lay.addWidget(self.preview_label)

        # V10.18.0 (E4): Cancel-and-resume indicator — shows chapter status
        # (✅ done / 🔄 in-progress / ⏳ pending) during summarization.
        self.chapter_status_label = QLabel("📖 Chapters: (waiting…)")
        self.chapter_status_label.setObjectName("Caption")
        self.chapter_status_label.setStyleSheet(
            f"font-size: 10px; color: {theme_manager.palette.text_muted};"
            f" background: {theme_manager.palette.bg_input};"
            f" padding: 3px 8px; border-radius: 4px;"
        )
        lay.addWidget(self.chapter_status_label)

        self.log_viewer = LogViewer(max_lines=5000)
        lay.addWidget(self.log_viewer, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(self.cancel_btn)
        self.open_folder_btn = QPushButton("Open output folder")
        self.open_folder_btn.setVisible(False)
        btn_row.addWidget(self.open_folder_btn)
        # V18.20.3.9 (Phase 2 / B1, V18.20.3.8 rig audit F1): a dedicated
        # "open summaries folder" affordance on the completion row — the
        # stale-file-upload class (4 occurrences) always came from picking
        # the summary from the wrong folder; the canonical stamped file
        # lives in <output>/summaries/.
        self.open_summaries_btn = QPushButton("Open summaries folder")
        self.open_summaries_btn.setVisible(False)
        btn_row.addWidget(self.open_summaries_btn)
        self.again_btn = QPushButton("Convert another book")
        self.again_btn.setVisible(False)
        btn_row.addWidget(self.again_btn)
        lay.addLayout(btn_row)

    def reset(self) -> None:
        self.progress.setValue(0)
        self.status_label.setText("Preparing...")
        self.log_viewer.clear()
        self.cancel_btn.setVisible(True)
        self.open_folder_btn.setVisible(False)
        self.open_summaries_btn.setVisible(False)
        self.again_btn.setVisible(False)
