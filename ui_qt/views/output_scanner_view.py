"""V7.8.0: Output Scanner tab — audits a converted book's output folder.

Pick a book's output folder → the scanner tells you what was generated,
what's missing, what failed, and what was skipped.  Catches the "I thought
packets were generated but the folder is empty" case.

See :mod:`core.pipeline.output_scanner` for the backend.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from core.pipeline.output_scanner import (
    OutputScanResult,
    ScanReport,
    scan_output_folder,
)
from ui_qt.components import Card, StepHeader
from ui_qt.components.icons import icon
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.theme import theme_manager


def _regenerable_keys() -> frozenset[str]:
    """Output keys ``controller.regenerate_output`` can regenerate.

    Single source of truth: the registry's regenerate map (the controller
    refuses anything not in it — controller.py ``_REGENERATE_MAP``).  The
    three former inline literals in this module had drifted apart: the
    Complete-All visibility check listed 17 keys while the row-button and
    batch-action sets listed 9 — a missing output the controller CAN
    regenerate showed no 🔄 button, and Complete All no-op'd behind a
    "Nothing to regenerate" info box while its button was visible.
    """
    try:
        from core.outputs.registry import get_regenerate_map

        return frozenset(get_regenerate_map())
    except Exception:  # registry unavailable — conservative core set
        return frozenset(
            {
                "briefing",
                "podcast_script",
                "packets",
                "flashcards",
                "obsidian",
                "study_guide",
                "social",
                "mindmap",
                "podcast_audio",
            }
        )


# Regenerable output keys — shared by the row 🔄 buttons (:_build_result_row),
# the Complete-All visibility check (:_render_results) and the Complete-All
# batch action (:_complete_all_requested).
_REGENERABLE_KEYS = _regenerable_keys()

# Status → (icon, color_name, label)
_STATUS_META = {
    "generated": ("✅", "success", "Generated"),
    "missing": ("❌", "error", "Missing"),
    "failed": ("⚠️", "error", "Failed"),
    "skipped": ("⏭️", "text_muted", "Skipped"),
    "not_requested": ("—", "text_muted", "Not requested"),
}

# Category display order + labels
_CATEGORIES = [
    ("markdown", "📄 Markdown"),
    ("summaries", "📝 Summaries & Keypoints"),
    ("outputs", "📤 Output Studio"),
    ("translation", "🌐 Translation"),
    ("logs", "📋 Logs & Reports"),
]


class OutputScannerView(QWidget):
    """Tab for scanning a book output folder and reporting what's present/missing."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._report: ScanReport | None = None
        # V18.20.4.9 (W-b18 remainder): worker ref (GC hazard) + retire
        # list (the T-b2 pattern — a replaced still-winding-down worker is
        # parked, never GC'd mid-run).
        self._regen_worker: SimpleWorker | None = None
        self._retired_workers: list[SimpleWorker] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 6)
        root.setSpacing(7)

        # ── Header card: folder picker + scan ────────────────────────────
        header_card = Card(padding=10, spacing=6)
        header_card.addWidget(
            StepHeader(
                1,
                "Output Scanner",
                "Select a book's output folder to check what was generated, "
                "what's missing, and what failed. Catches silent skips and "
                "ghost files.",
            )
        )

        pick_row = QHBoxLayout()
        pick_row.setContentsMargins(0, 0, 0, 0)
        pick_row.setSpacing(7)

        self.folder_btn = QPushButton("  Browse output folder…")
        self.folder_btn.setObjectName("Primary")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.setIcon(icon("folder", theme_manager.palette.text_on_accent, 16))
        self.folder_btn.clicked.connect(self._pick_folder)
        pick_row.addWidget(self.folder_btn)

        self.scan_btn = QPushButton("  Scan")
        self.scan_btn.setObjectName("Secondary")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setIcon(icon("scan", theme_manager.palette.text_primary, 16))
        self.scan_btn.clicked.connect(self._run_scan)
        self.scan_btn.setEnabled(False)
        pick_row.addWidget(self.scan_btn)

        pick_row.addStretch()

        self.folder_lbl = QLabel("No folder selected")
        self.folder_lbl.setObjectName("Caption")
        pick_row.addWidget(self.folder_lbl)
        header_card.addLayout(pick_row)

        # Summary line (populated after scan)
        self.summary_lbl = QLabel("")
        self.summary_lbl.setObjectName("Body")
        header_card.addWidget(self.summary_lbl)

        # V9.4.0: "Complete All Requested" button — batch-regenerates all
        # missing/failed outputs that the user originally requested.
        # Non-requested outputs are NOT auto-picked up.
        self.complete_all_btn = QPushButton("  ✅ Complete All Requested")
        self.complete_all_btn.setObjectName("Primary")
        self.complete_all_btn.setCursor(Qt.PointingHandCursor)
        self.complete_all_btn.setIcon(icon("check", theme_manager.palette.text_on_accent, 16))
        self.complete_all_btn.setToolTip(
            "Automatically regenerate all missing/failed outputs that you\n"
            "originally requested (enabled in the wizard).\n\n"
            "Outputs you didn't request (e.g. Obsidian) are NOT auto-generated.\n"
            "Use the 🔄 button on individual rows for those."
        )
        self.complete_all_btn.setVisible(False)
        self.complete_all_btn.clicked.connect(self._complete_all_requested)
        header_card.addWidget(self.complete_all_btn)

        root.addWidget(header_card)

        # ── Results scroll area ───────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            " QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.results_host = QWidget()
        self.results_lay = QVBoxLayout(self.results_host)
        self.results_lay.setContentsMargins(0, 0, 0, 0)
        self.results_lay.setSpacing(8)
        self.results_lay.addStretch()
        self.scroll.setWidget(self.results_host)
        root.addWidget(self.scroll, 1)

        self._selected_folder: Path | None = None

    # ── Actions ──────────────────────────────────────────────────────────

    def _pick_folder(self) -> None:
        last_dir = self.controller.get_setting("output.last_output_dir", "")
        folder = QFileDialog.getExistingDirectory(
            self, "Select book output folder", last_dir or str(Path.home())
        )
        if folder:
            self._selected_folder = Path(folder)
            self.folder_lbl.setText(str(self._selected_folder))
            self.scan_btn.setEnabled(True)
            self.controller.update_setting("output.last_output_dir", folder)
            # Auto-scan on folder pick
            self._run_scan()

    def _run_scan(self) -> None:
        if not self._selected_folder or not self._selected_folder.exists():
            return
        self.scan_btn.setEnabled(False)
        self.summary_lbl.setText("Scanning…")
        # Run the scan (synchronous — it's fast, just file checks)
        self._report = scan_output_folder(self._selected_folder)
        self._render_results()
        self.scan_btn.setEnabled(True)

    # ── Rendering ────────────────────────────────────────────────────────

    def _render_results(self) -> None:
        # Clear previous results
        while self.results_lay.count() > 1:
            item = self.results_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not self._report:
            self.summary_lbl.setText("No report.")
            return

        r = self._report
        p = theme_manager.palette

        # Summary line
        if r.layout == "unknown":
            self.summary_lbl.setText("⚠️ This folder doesn't look like a Elixir output directory.")
            self.summary_lbl.setStyleSheet(f"color: {p.warning};")
            return

        generated = r.generated_count
        missing = r.missing_count
        failed = r.failed_count
        not_req = r.summary_counts.get("not_requested", 0)
        skipped = r.summary_counts.get("skipped", 0)

        parts = [f"<b>{r.book_title or r.stem}</b>"]
        parts.append(f"layout: {r.layout}")
        parts.append(f"checkpoint: {'✓' if r.checkpoint_found else '✗'}")
        parts.append(f"settings: {'✓' if r.settings_found else '✗'}")
        parts.append(
            f"✅ {generated} generated · "
            f"❌ {missing} missing · "
            f"⚠️ {failed} failed · "
            f"⏭️ {skipped} skipped · "
            f"— {not_req} not requested"
        )
        self.summary_lbl.setText("  ·  ".join(parts))
        if missing > 0 or failed > 0:
            color = p.error if failed > 0 else p.warning
            self.summary_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            # V9.4.0: show "Complete All Requested" button if there are
            # missing/failed outputs that are regenerable.  We check ALL
            # missing/failed outputs (not just "requested" ones) because the
            # scanner's requested/not_requested detection is unreliable for
            # output_studio types (the settings file may not have those flags).
            _has_actionable = any(
                res.status in ("missing", "failed") and res.key in _REGENERABLE_KEYS
                for res in r.results
            )
            self.complete_all_btn.setVisible(_has_actionable)
        else:
            self.summary_lbl.setStyleSheet(
                f"color: {p.success}; font-size: 11px; font-weight: 600;"
            )
            self.complete_all_btn.setVisible(False)

        # Group results by category
        for cat_key, cat_label in _CATEGORIES:
            cat_results = [res for res in r.results if res.category == cat_key]
            if not cat_results:
                continue

            cat_header = QLabel(cat_label)
            cat_header.setObjectName("SectionTitle")
            cat_header.setContentsMargins(0, 8, 0, 4)
            self.results_lay.insertWidget(self.results_lay.count() - 1, cat_header)

            for res in cat_results:
                row = self._build_result_row(res, p)
                self.results_lay.insertWidget(self.results_lay.count() - 1, row)

    def _build_result_row(self, res: OutputScanResult, p) -> QFrame:
        """Build one output result row: status icon + name + detail."""
        status_icon, color_name, status_label = _STATUS_META.get(
            res.status, ("?", "text_muted", res.status)
        )
        color_map = {
            "success": p.success,
            "error": p.error,
            "warning": p.warning,
            "info": p.info,
            "text_muted": p.text_muted,
            "text_primary": p.text_primary,
        }
        color = color_map.get(color_name, p.text_muted)

        row = QFrame()
        row.setObjectName("ScanRow")
        bg = p.bg_surface if res.status == "generated" else p.bg_input
        border = (
            p.border
            if res.status == "generated"
            else (p.error if res.status in ("missing", "failed") else p.border)
        )
        row.setStyleSheet(
            f"QFrame#ScanRow {{ background-color: {bg};"
            f" border: 1px solid {border}; border-radius: 6px; }}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        # Status icon
        icon_lbl = QLabel(status_icon)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
        icon_lbl.setFixedWidth(20)
        lay.addWidget(icon_lbl)

        # Name + detail
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name = QLabel(res.display_name)
        name.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {p.text_primary}; background: transparent;"
        )
        text_col.addWidget(name)
        detail_text = res.detail
        if res.checkpoint_status and res.checkpoint_status != "done":
            detail_text += f"  [checkpoint: {res.checkpoint_status}]"
        elif res.checkpoint_status == "done" and res.status != "generated":
            detail_text += "  [checkpoint: done but file missing!]"
        detail = QLabel(detail_text)
        detail.setStyleSheet(f"font-size: 10px; color: {p.text_muted}; background: transparent;")
        detail.setWordWrap(True)
        text_col.addWidget(detail)
        lay.addLayout(text_col, 1)

        # Status badge
        badge = QLabel(status_label)
        badge.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {color};"
            f" background: {p.bg_elevated}; padding: 3px 8px;"
            f" border-radius: 8px;"
        )
        lay.addWidget(badge)

        # V7.9.0: Regenerate button for missing/failed regenerable outputs
        # (the shared module-level set — see _regenerable_keys).
        if res.key in _REGENERABLE_KEYS and res.status in ("missing", "failed", "skipped"):
            regen_btn = QPushButton("🔄")
            regen_btn.setObjectName("Compact")
            regen_btn.setCursor(Qt.PointingHandCursor)
            regen_btn.setToolTip(f"Regenerate {res.display_name} from existing summaries")
            regen_btn.setFixedSize(32, 28)
            regen_btn.clicked.connect(lambda checked=False, k=res.key: self._regenerate(k))
            lay.addWidget(regen_btn)

        return row

    # ── V7.9.0: Regenerate action ─────────────────────────────────────────

    def _complete_all_requested(self) -> None:
        """V9.4.0: Batch-regenerate all missing/failed REQUESTED outputs.

        Only regenerates outputs that the user originally requested (enabled
        in the wizard settings). Outputs that were not requested stay
        untouched — the user can still use the 🔄 button on those manually.
        """
        if not self._report or not self._selected_folder:
            return

        # All missing/failed regenerable outputs (the shared module-level
        # set — see _regenerable_keys).
        #
        # Collect all missing/failed outputs that are regenerable.
        # V9.4.1 fix: don't filter by "not_requested" — the scanner's
        # requested detection is unreliable. Include ALL missing/failed
        # regenerable outputs. The user sees a confirmation dialog listing
        # exactly what will be regenerated, so they can cancel if they
        # don't want something.
        to_regen = [
            res.key
            for res in self._report.results
            if res.status in ("missing", "failed") and res.key in _REGENERABLE_KEYS
        ]

        if not to_regen:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                "Nothing to regenerate",
                "No missing/failed regenerable outputs found.\n\n"
                "All outputs that can be regenerated are either already\n"
                "generated or not applicable to this content type.",
            )
            return

        from PySide6.QtWidgets import QMessageBox

        ret = QMessageBox.question(
            self,
            "Complete All Requested",
            f"Regenerate {len(to_regen)} missing/failed output(s)?\n\n"
            f"Outputs to regenerate:\n  • " + "\n  • ".join(to_regen) + "\n\n"
            "This re-runs each generator from existing summaries (no re-extraction\n"
            "or re-summarization). LLM-based outputs may take several minutes.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        # Disable UI + show progress
        self.scan_btn.setEnabled(False)
        self.complete_all_btn.setEnabled(False)
        self.complete_all_btn.setText("  Processing…")
        self._regen_queue = to_regen
        self._regen_results_log = []
        self._regen_current = 0
        self._regen_total = len(to_regen)
        self._regen_next()

    def _spawn_regen_worker(self, _run) -> None:
        """V18.20.4.9 (W-b18 remainder): shared spawn for the batch/single
        regeneration workers — keeps the ref (GC hazard), parks a
        still-winding-down predecessor on the retire list (T-b2 pattern),
        and connects ``failed`` → re-enable + fail-soft. The result slot
        (``_on_batch_item_done`` / ``_on_regen_done``) is only reached on
        success — a raising worker used to leave the scan + complete-all
        buttons disabled forever."""
        prev = self._regen_worker
        if prev is not None:
            try:
                if prev.is_running():
                    self._retired_workers.append(prev)
            except RuntimeError:
                pass  # already deleteLater'd itself
        w = SimpleWorker(_run)
        self._regen_worker = w
        w.failed.connect(self._on_regen_worker_failed)
        w.start()

    def _on_regen_worker_failed(self, msg: str) -> None:
        """W-b18 remainder: re-enable the buttons + the same failure
        display style ``_on_regen_done``'s failure branch uses (❌ + error
        color); a fresh scan is NOT auto-triggered (the worker state is
        unknown — the user can press Scan)."""
        self.scan_btn.setEnabled(True)
        self.complete_all_btn.setEnabled(True)
        self.complete_all_btn.setText("  ✅ Complete All Requested")
        p = theme_manager.palette
        self.summary_lbl.setText(f"❌ {msg}")
        self.summary_lbl.setStyleSheet(f"color: {p.error}; font-size: 11px;")

    def _regen_next(self) -> None:
        """Process the next item in the regeneration queue."""
        if not hasattr(self, "_regen_queue") or not self._regen_queue:
            self._on_batch_complete()
            return

        output_key = self._regen_queue.pop(0)
        self._regen_current += 1
        self.summary_lbl.setText(
            f"Completing {self._regen_current}/{self._regen_total}: {output_key}…"
        )

        def _run():
            ok, msg = self.controller.regenerate_output(
                self._selected_folder,
                output_key,
                log_callback=lambda m, lvl: None,
            )
            self._regen_results_log.append((output_key, ok, msg))
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self, "_on_batch_item_done", _Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                self._on_batch_item_done()

        self._spawn_regen_worker(_run)

    from PySide6.QtCore import Slot  # noqa: E402

    @Slot()
    def _on_batch_item_done(self) -> None:
        """Called after each batch item completes."""
        # Process next item
        if hasattr(self, "_regen_queue") and self._regen_queue:
            self._regen_next()
        else:
            self._on_batch_complete()

    def _on_batch_complete(self) -> None:
        """Called after all batch items are done."""
        self.scan_btn.setEnabled(True)
        self.complete_all_btn.setEnabled(True)
        self.complete_all_btn.setText("  ✅ Complete All Requested")
        p = theme_manager.palette

        # Summarize results
        succeeded = sum(1 for _, ok, _ in self._regen_results_log if ok)
        failed = sum(1 for _, ok, _ in self._regen_results_log if not ok)
        total = len(self._regen_results_log)

        if failed == 0:
            self.summary_lbl.setText(f"✅ Completed all {succeeded} output(s) successfully!")
            self.summary_lbl.setStyleSheet(
                f"color: {p.success}; font-size: 11px; font-weight: 600;"
            )
        else:
            failed_names = [k for k, ok, _ in self._regen_results_log if not ok]
            self.summary_lbl.setText(
                f"⚠️ {succeeded}/{total} succeeded, {failed} failed: {', '.join(failed_names)}"
            )
            self.summary_lbl.setStyleSheet(f"color: {p.warning}; font-size: 11px;")

        # Re-scan to show updated results
        self._run_scan()

    def _regenerate(self, output_key: str) -> None:
        """Regenerate a single output in a background thread."""
        if not self._selected_folder:
            return
        from PySide6.QtWidgets import QMessageBox

        # Confirm
        ret = QMessageBox.question(
            self,
            "Regenerate output",
            f"Regenerate '{output_key}' from existing summaries?\n\n"
            f"This re-runs just that output generator (no re-extraction or\n"
            f"re-summarization). It may take a few minutes for LLM-based outputs.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        # Disable the scan button + show status
        self.scan_btn.setEnabled(False)
        self.summary_lbl.setText(f"Regenerating {output_key}…")

        def _run():
            ok, msg = self.controller.regenerate_output(
                self._selected_folder,
                output_key,
                log_callback=lambda m, lvl: None,  # silent — the generator logs internally
            )
            self._regen_result = (ok, msg)
            try:
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self, "_on_regen_done", _Qt.ConnectionType.QueuedConnection
                )
            except Exception:
                self._on_regen_done()

        self._spawn_regen_worker(_run)

    @Slot()
    def _on_regen_done(self) -> None:
        """Called (on the UI thread) after regeneration completes."""
        ok, msg = getattr(self, "_regen_result", (False, "unknown"))
        self.scan_btn.setEnabled(True)
        p = theme_manager.palette
        if ok:
            self.summary_lbl.setText(f"✅ {msg}")
            self.summary_lbl.setStyleSheet(f"color: {p.success}; font-size: 11px;")
        else:
            self.summary_lbl.setText(f"❌ {msg}")
            self.summary_lbl.setStyleSheet(f"color: {p.error}; font-size: 11px;")
        # Re-scan to show updated results
        self._run_scan()

    def refresh_theme(self) -> None:
        """Re-render results with current palette (called on theme toggle)."""
        if self._report:
            self._render_results()
