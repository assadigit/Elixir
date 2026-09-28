"""Hallucination Audit dialog (V18.20.4.6, P5 / O-b2 split).

_HallucinationAuditWorker + HallucinationAuditDialog moved VERBATIM
from ui_qt/views/service_dialogs/base_dialog.py — only this
module's top-of-file imports differ (the V13.20.0 banner they
shared with the Packets tool lives in packets_tool_dialog.py).
ui_qt.views.service_dialogs.base_dialog re-exports both names
(back-compat facade)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QTableWidgetItem,
)

from ui_qt.views.service_dialogs.dialogs.shared import (
    PlainTextTextEdit,
    _confirm_close_with_running_worker,
)

# V18.20.4.6: latent V13.20.x NameError fixed (botched rename)
_QTI = QTableWidgetItem


class _HallucinationAuditWorker(QThread):
    """Background thread for hallucination audit."""

    done_signal = Signal(list, str)

    def __init__(self, source_text, bullets, parent=None):
        super().__init__(parent)
        self._source = source_text
        self._bullets = bullets

    def run(self):
        try:
            from core.summarisation.hallucination_detector import HallucinationDetector

            detector = HallucinationDetector()
            filtered, reports = detector.detect_and_filter(self._bullets, self._source, "Audit")
            self.done_signal.emit(reports, "")
        except Exception as e:
            self.done_signal.emit([], f"{type(e).__name__}: {e}")


class HallucinationAuditDialog(QDialog):
    """Standalone Hallucination Audit tool — check bullets against source."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("🛡️ Hallucination Audit")
        self.setMinimumSize(700, 600)
        self.setModal(True)
        self._worker = None

        from PySide6.QtWidgets import (
            QHBoxLayout as _HL,
        )
        from PySide6.QtWidgets import (
            QHeaderView as _QHV,
        )
        from PySide6.QtWidgets import (
            QLabel as _QL,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QTableWidget as _QTW,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        title = _QL("🛡️ Hallucination Audit")
        title.setObjectName("H2")
        lay.addWidget(title)
        desc = _QL(
            "Paste source text and summary bullets. The audit checks each "
            "bullet against the source using 4 signals (verbatim match, "
            "semantic similarity, content-word overlap, number/quote check). "
            "Grounded bullets are ✅, suspicious ones ⚠️, hallucinations 🗑️."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Source text input
        lay.addWidget(_QL("📄 Source Text:"))
        self.source_input = PlainTextTextEdit()
        self.source_input.setPlaceholderText("Paste the original source text here...")
        self.source_input.setMinimumHeight(100)
        lay.addWidget(self.source_input)

        # Bullets input
        lay.addWidget(_QL("📋 Summary Bullets (one per line):"))
        self.bullets_input = PlainTextTextEdit()
        self.bullets_input.setPlaceholderText("- First bullet\n- Second bullet\n- ...")
        self.bullets_input.setMinimumHeight(100)
        lay.addWidget(self.bullets_input)

        # Audit button
        btn_row = _HL()
        self.audit_btn = _QPB("🛡️ Audit Bullets")
        self.audit_btn.setObjectName("Primary")
        self.audit_btn.clicked.connect(self._on_audit)
        btn_row.addStretch()
        btn_row.addWidget(self.audit_btn)
        lay.addLayout(btn_row)

        # Results table
        lay.addWidget(_QL("📊 Results:"))
        self.results_table = _QTW(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Bullet", "Verdict", "Reason", "Overlap", "Similarity"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(0, _QHV.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, _QHV.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, _QHV.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(3, _QHV.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, _QHV.ResizeToContents)
        lay.addWidget(self.results_table)

        # Copy button
        copy_row = _HL()
        copy_row.addStretch()
        self.copy_btn = _QPB("📋 Copy Filtered Bullets")
        self.copy_btn.clicked.connect(self._copy_filtered)
        copy_row.addWidget(self.copy_btn)
        lay.addLayout(copy_row)

        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        lay.addWidget(self.status_label)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the
        # _HallucinationAuditWorker QThread runs — it is PARENTED to this
        # dialog, so destroying the dialog mid-run is exactly the
        # "QThread: Destroyed while thread is still running" abort. The
        # shared guard handles raw-QThread workers (isRunning() + signal
        # disconnect + unparent on confirm).
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _on_audit(self):
        source = self.source_input.toPlainText().strip()
        bullets_text = self.bullets_input.toPlainText().strip()
        if not source or not bullets_text:
            QMessageBox.warning(self, "Need input", "Please paste both source text and bullets.")
            return
        # Parse bullets
        bullets = []
        for line in bullets_text.splitlines():
            line = line.strip()
            if line and (line.startswith("-") or line.startswith("*") or line.startswith("•")):
                clean = line.lstrip("-*• ").strip()
                if clean and len(clean) > 5:
                    bullets.append(clean)
            elif line and len(line) > 10:
                bullets.append(line)
        if not bullets:
            QMessageBox.warning(self, "No bullets", "No bullets found. Use - or * prefixes.")
            return

        self.audit_btn.setEnabled(False)
        self.audit_btn.setText("🛡️ Auditing...")
        self.status_label.setText(f"🛡️ Auditing {len(bullets)} bullets...")
        self.results_table.setRowCount(0)

        self._worker = _HallucinationAuditWorker(source, bullets, self)
        self._worker.done_signal.connect(self._on_done)
        self._worker.start()

    def _on_done(self, reports, error):
        self.audit_btn.setEnabled(True)
        self.audit_btn.setText("🛡️ Audit Bullets")
        if error:
            self.status_label.setText(f"❌ {error}")
            QMessageBox.critical(self, "❌ Audit Failed", error)
            return

        self.results_table.setRowCount(len(reports))
        grounded = 0
        flagged = 0
        dropped = 0
        for i, report in enumerate(reports):
            bullet = (
                report.get("bullet", "")[:80] + "..."
                if len(report.get("bullet", "")) > 80
                else report.get("bullet", "")
            )
            action = report.get("action", "kept")
            if action == "dropped":
                verdict = "🗑️ Dropped"
                dropped += 1
            elif action == "flagged":
                verdict = "⚠️ Flagged"
                flagged += 1
            else:
                verdict = "✅ Grounded"
                grounded += 1
            reason = report.get("reason", "")
            overlap = f"{report.get('source_overlap', 0):.0%}"
            similarity = f"{report.get('semantic_similarity', 0):.0%}"
            bullet_item = _QTI(bullet)
            # V0.6.0: keep the FULL bullet on the item — _copy_filtered used
            # the display text (truncated at 80 chars + a literal "..."),
            # so the copied "grounded bullets" were corrupted.
            bullet_item.setData(Qt.ItemDataRole.UserRole, report.get("bullet", ""))
            self.results_table.setItem(i, 0, bullet_item)
            self.results_table.setItem(i, 1, _QTI(verdict))
            self.results_table.setItem(i, 2, _QTI(reason))
            self.results_table.setItem(i, 3, _QTI(overlap))
            self.results_table.setItem(i, 4, _QTI(similarity))

        self.status_label.setText(
            f"✅ Audit complete: {grounded} grounded, {flagged} flagged, {dropped} dropped "
            f"(of {len(reports)} total)"
        )

    def _copy_filtered(self):
        """Copy only grounded bullets to clipboard (the FULL text — the
        table cell shows a truncated version for display)."""
        grounded = []
        for i in range(self.results_table.rowCount()):
            verdict_item = self.results_table.item(i, 1)
            bullet_item = self.results_table.item(i, 0)
            if verdict_item and "✅" in verdict_item.text() and bullet_item:
                full = bullet_item.data(Qt.ItemDataRole.UserRole)
                if not isinstance(full, str) or not full:
                    full = bullet_item.text()
                grounded.append(f"- {full}")
        if grounded:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText("\n".join(grounded))
            self.status_label.setText(f"📋 Copied {len(grounded)} grounded bullets to clipboard.")
        else:
            self.status_label.setText("No grounded bullets to copy.")
