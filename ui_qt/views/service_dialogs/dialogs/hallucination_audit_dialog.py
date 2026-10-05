"""Hallucination Audit dialog (V18.20.4.6, P5 / O-b2 split).

_HallucinationAuditWorker + HallucinationAuditDialog moved VERBATIM
from ui_qt/views/service_dialogs/base_dialog.py — only this
module's top-of-file imports differ (the V13.20.0 banner they
shared with the Packets tool lives in packets_tool_dialog.py).
ui_qt.views.service_dialogs.base_dialog re-exports both names
(back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent). It is the dual-input custom-UI case:
``accept_files=False, accept_text=False`` so the base builds no
standard input row — the source + bullets inputs, the results table
and the copy row fold into ``_build_options``. The raw-QThread worker
(``_HallucinationAuditWorker`` + ``done_signal``) does not fit the
base's SimpleWorker flow, so the audit launch stays in ``_on_audit``
(driven from the base Process button via the ``_on_process``
override). The T-b2 closeEvent guard is now the INHERITED base guard —
it makes the same ``_confirm_close_with_running_worker(self,
self._worker)`` call the deleted override made, and the shared helper
already handles raw QThread workers (isRunning + unparent on
confirm)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    PlainTextTextEdit,
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


class HallucinationAuditDialog(BaseServiceDialog):
    """Standalone Hallucination Audit tool — check bullets against source."""

    def __init__(self, controller, parent=None):
        # V0.6.10 (B17): super().__init__ builds the base scaffolding and
        # calls _build_ui → _build_options (the custom dual-input UI), so
        # any dialog attribute _build_options needs must exist BEFORE the
        # super() call. This dialog needs none.
        super().__init__(
            controller,
            "🛡️ Hallucination Audit",
            parent,
            accept_files=False,
            accept_text=False,
        )
        # V0.6.10 (B17): restore this dialog's shape over the base's
        # generic scaffolding — its own geometry, the audit trigger text
        # on the base Process button (aliased; the base wires its click
        # to the _on_process override below), and hiding the save-to row
        # (this tool produces no output file).
        self.setMinimumSize(700, 600)
        self.audit_btn = self.process_btn
        self.audit_btn.setText("🛡️ Audit Bullets")
        self._hide_base_output_row()
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (the raw-QThread worker reports
        # only through done_signal) — hide the dead toggle (the transcribe
        # B17 precedent).
        self._log_toggle_btn.setVisible(False)

    def _hide_base_output_row(self) -> None:
        """V0.6.10 (B17): hide the base class's "Save to:" row — the audit
        writes no output file, so the row's location picker would be dead
        UI (nothing in this dialog ever reads ``out_path_edit``)."""
        root = self.layout()
        if root is None:
            return
        for i in range(root.count()):
            item = root.itemAt(i)
            row = item.layout() if item is not None else None
            if row is None or row.indexOf(self.out_path_edit) < 0:
                continue
            for j in range(row.count()):
                w = row.itemAt(j).widget()
                if w is not None:
                    w.setVisible(False)
            return

    def _build_options(self, layout: QVBoxLayout) -> None:
        """V0.6.10 (B17): the audit's custom dual-input UI (source +
        bullets), the results table and the copy row — the reason this
        dialog passes ``accept_files=False, accept_text=False`` (the base
        builds no standard input row; both inputs live here)."""
        desc = QLabel(
            "Paste source text and summary bullets. The audit checks each "
            "bullet against the source using 4 signals (verbatim match, "
            "semantic similarity, content-word overlap, number/quote check). "
            "Grounded bullets are ✅, suspicious ones ⚠️, hallucinations 🗑️."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Source text input
        layout.addWidget(QLabel("📄 Source Text:"))
        self.source_input = PlainTextTextEdit()
        self.source_input.setPlaceholderText("Paste the original source text here...")
        self.source_input.setMinimumHeight(100)
        layout.addWidget(self.source_input)

        # Bullets input
        layout.addWidget(QLabel("📋 Summary Bullets (one per line):"))
        self.bullets_input = PlainTextTextEdit()
        self.bullets_input.setPlaceholderText("- First bullet\n- Second bullet\n- ...")
        self.bullets_input.setMinimumHeight(100)
        layout.addWidget(self.bullets_input)

        # Results table
        layout.addWidget(QLabel("📊 Results:"))
        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Bullet", "Verdict", "Reason", "Overlap", "Similarity"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.results_table)

        # Copy button
        copy_row = QHBoxLayout()
        copy_row.addStretch()
        self.copy_btn = QPushButton("📋 Copy Filtered Bullets")
        self.copy_btn.clicked.connect(self._copy_filtered)
        copy_row.addWidget(self.copy_btn)
        layout.addLayout(copy_row)

    def _on_process(self) -> None:
        # V0.6.10 (B17): the base Process button (aliased as audit_btn)
        # drives the audit; the body stays in _on_audit — the pinned,
        # test-driven entry point.
        self._on_audit()

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

    def _get_service_name(self) -> str:
        # V0.6.10 (B17): base-class identity hook. This dialog persists no
        # controller settings (grep: zero controller.update_setting /
        # controller.get_setting calls), so the name is identity-only.
        return "hallucination_audit"
