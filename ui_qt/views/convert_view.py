"""Main conversion screen — the tool-dashboard home page.

V11.0.0 architecture: this page hosts the tool dashboard (9 cards), a
progress panel and a collapsible live log. All conversion runs through
the Process Wizard (launched from the Full Conversion card) or the
standalone service dialogs; batch PDFs go through the Queue tab, and
window-level drag-and-drop routes dropped PDFs to the Queue view
(V18.20.4.1 / W-b1). The legacy single-page flow (type cards, document
picker, page range, output toggle, chapter selection, Convert / Test
Book buttons) was removed in V11.0.0, and the last dead legacy methods
were deleted in V18.20.4.1 — closing the V18.20.3.14 crash class
structurally (see ``_build_ui`` and ``_set_cta_enabled``).

This view stays wired to the controller bridge so completions that
land here after the Process Wizard closes are still handled
(``_on_complete``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from controller import Controller
from core.models import ConversionResult
from ui_qt.components import (
    LogViewer,
    ProgressPanel,
)
from ui_qt.components.icons import icon
from ui_qt.controller_bridge import QtControllerBridge
from ui_qt.theme import theme_manager


class ConvertView(QWidget):
    """The tool-dashboard home page."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.bridge = QtControllerBridge()
        self.is_converting = False

        # register the bridge's emitters as the controller callbacks
        self._register_callbacks()

        self._build_ui()
        self._wire_bridge()
        self._load_basic_settings()

    def _register_callbacks(self) -> None:
        """Re-register this view's bridge as the controller's callback target.

        Called on init and when the Process Wizard dialog closes (to restore
        this view's callbacks after the wizard overrides them).
        """
        # V18.20.4.5 (W-b10): ownership tag — the wizard's closeEvent and
        # the queue's callback install/restore check this so nobody steals
        # callbacks that another component owns (queue) or restores them
        # unconditionally (wizard close).
        self.controller.set_callbacks(
            on_progress=self.bridge.emit_progress,
            on_status=self.bridge.emit_status,
            on_log=self.bridge.emit_log,
            on_complete=self.bridge.emit_complete,
            owner="convert_view",
        )

    # ══════════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 6)
        root.setSpacing(7)

        # V11.0.0: Tool dashboard replaces preset type cards.
        # The 9 tool cards are the primary entry point. The old preset
        # type cards (Book, Research Paper, etc.) move to the wizard's Step 1.
        from ui_qt.views.tool_dashboard import ToolDashboard

        self.tool_dashboard = ToolDashboard(self)
        self.tool_dashboard.tool_clicked.connect(self._on_tool_clicked)
        root.addWidget(self.tool_dashboard)

        # V18.20.4.1 (P0 / W-b13): the V11.0.0 legacy minefield is DELETED.
        # The removed single-page flow's widgets (type cards, document
        # picker, page range, output toggle, full OCR checkbox, chapter
        # selector, load-previous, Test Book / Convert buttons) no longer
        # exist as attributes at all — the ~350 lines of dead legacy
        # methods that dereferenced them were the V18.20.3.14 crash class
        # (``_on_complete`` → ``convert_btn.setEnabled`` on None) and
        # W-b1's drag-and-drop crash (``handle_dropped_file`` →
        # ``input_picker.set_path`` on None). What deliberately REMAINS
        # None: ``convert_btn`` / ``test_btn`` — pinned by the
        # V18.20.3.14 regression tests and still routed through the
        # None-guarded ``_set_cta_enabled`` — plus ``output_toggle_cb`` /
        # ``output_picker`` (read by ``apply_ui_preferences``).
        self._output_override: Path | None = None
        self.output_toggle_cb = None
        self.output_picker = None
        self.test_btn = None
        self.convert_btn = None

        # ── Progress panel (hidden when idle; shown during service operations) ──
        self.progress_panel = ProgressPanel(cancel_callback=self._cancel_any_operation)
        self.progress_panel.setVisible(False)
        root.addWidget(self.progress_panel)

        # Live log viewer (hidden — kept for bridge compatibility)
        self.log_viewer = LogViewer(max_lines=4000)
        self.log_viewer.setMaximumHeight(200)
        self.log_viewer.setVisible(False)

    # ══════════════════════════════════════════════════════════════════════
    # Wiring
    # ══════════════════════════════════════════════════════════════════════
    def _wire_bridge(self) -> None:
        self.bridge.connect_progress(self.progress_panel.set_value)
        self.bridge.connect_status(self._on_status)
        self.bridge.connect_log(self.log_viewer.append)
        self.bridge.connect_complete(self._on_complete)

    def _set_cta_enabled(self, enabled: bool) -> None:
        """V18.20.3.14 (user-reported crash fix): set the legacy CTA
        buttons' enabled state ONLY when the buttons exist.

        Since V11.0.0 the Convert / Test Book buttons are removed from
        this page and the attributes are deliberately None ("kept so
        existing methods don't crash" — except they did): the Process
        Wizard re-registers this view's bridge callbacks on close
        (wizard_view.closeEvent → convert_view._register_callbacks),
        so a wizard-run conversion that completes afterwards delivers
        _on_complete here, which called
        ``self.convert_btn.setEnabled(True)`` UNGUARDED and crashed
        with ``AttributeError: 'NoneType' object has no attribute
        'setEnabled'`` — skipping the completion status, the success
        log lines and the cancel-button cleanup. All four legacy
        touchers now route through this guard.
        """
        if self.convert_btn is not None:
            self.convert_btn.setEnabled(enabled)
        if self.test_btn is not None:
            self.test_btn.setEnabled(enabled)

    def _on_tool_clicked(self, tool_key: str) -> None:
        """Handle a tool card click — open a dialog, switch tab, or launch wizard."""
        if tool_key == "full_conversion":
            self._open_wizard()
        elif tool_key == "pdf_to_markdown":
            from ui_qt.views.service_dialogs.base_dialog import QuickConvertDialog

            dlg = QuickConvertDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "ocr_service":
            from ui_qt.views.service_dialogs.base_dialog import OcrServiceDialog

            dlg = OcrServiceDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "summarization":
            from ui_qt.views.service_dialogs.base_dialog import SummarizationServiceDialog

            dlg = SummarizationServiceDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "translation":
            from ui_qt.views.service_dialogs.base_dialog import TranslationServiceDialog

            dlg = TranslationServiceDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "tts_service":
            from ui_qt.views.service_dialogs.base_dialog import TtsServiceDialog

            dlg = TtsServiceDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "markdown_styler":
            from ui_qt.views.service_dialogs.base_dialog import MarkdownStylerDialog

            dlg = MarkdownStylerDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "packets_tool":
            from ui_qt.views.service_dialogs.base_dialog import PacketsToolDialog

            dlg = PacketsToolDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "hallucination_audit":
            from ui_qt.views.service_dialogs.base_dialog import HallucinationAuditDialog

            dlg = HallucinationAuditDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "pdf_docx_cutter":
            from ui_qt.views.service_dialogs.base_dialog import PdfDocxCutterDialog

            dlg = PdfDocxCutterDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "image_extractor":
            from ui_qt.views.service_dialogs.base_dialog import ImageExtractorDialog

            dlg = ImageExtractorDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "transcribe":
            from ui_qt.views.service_dialogs.base_dialog import TranscribeServiceDialog

            dlg = TranscribeServiceDialog(self.controller, self)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "podcast_maker":
            # V13.31.0 (#6): Podcast Maker now opens as modal dialog
            # (was: switch to tab — inconsistent with other tools)
            from PySide6.QtWidgets import QDialog, QVBoxLayout

            from ui_qt.views.podcast_maker_view import PodcastMakerView

            dlg = QDialog(self)
            dlg.setWindowTitle("🎙️ Podcast Maker")
            dlg.setMinimumSize(700, 600)
            dlg.setModal(True)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            pm_view = PodcastMakerView(self.controller)
            lay.addWidget(pm_view)
            # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
            dlg.setAttribute(Qt.WA_DeleteOnClose, True)
            dlg.exec()
        elif tool_key == "output_scanner":
            self._switch_to_tab("output_scanner")
        elif tool_key == "batch_queue":
            self._switch_to_tab("queue")
        else:
            self.log_viewer.append(f"Unknown tool: {tool_key}", "WARNING")

    def _switch_to_tab(self, tab_name: str) -> None:
        """Switch to a tab by name — finds the parent QTabWidget."""
        # V11.36.2: map tool keys to actual attribute names.
        attr_map = {
            "podcast_maker": "podcast_maker_view",
            "output_scanner": "output_scanner_view",
            "queue": "queue_view",
            "batch_queue": "queue_view",
        }
        attr_name = attr_map.get(tab_name, tab_name)
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "tab_widget"):
                # Find the tab by widget attribute name
                tw = parent.tab_widget
                for i in range(tw.count()):
                    widget = tw.widget(i)
                    inner = widget.widget() if hasattr(widget, "widget") else widget
                    if hasattr(parent, attr_name) and inner is getattr(parent, attr_name):
                        tw.setCurrentIndex(i)
                        # Briefly highlight the tab (Q17: instant + highlight)
                        tw.tabBar().setTabTextColor(
                            i, __import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#D8AA78")
                        )
                        from PySide6.QtCore import QTimer

                        def _reset_color(idx=i, tw=tw):
                            tw.tabBar().setTabTextColor(
                                idx, __import__("PySide6.QtGui", fromlist=["QColor"]).QColor()
                            )

                        QTimer.singleShot(1500, _reset_color)
                        return
            parent = parent.parent()
        self.log_viewer.append(f"Could not find tab: {tab_name}", "WARNING")

    def _open_wizard(self) -> None:
        """Launch the Process Wizard."""
        from ui_qt.views.wizard_view import WizardView

        dlg = WizardView(self.controller, self)
        # V18.20.4.5 (W-b9): delete the dialog tree on close — each open used to leak a hidden widget tree.
        # (The post-exec call below touches self, not dlg — safe to delete the dialog.)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.exec()
        # Re-register callbacks (wizard may have overridden them)
        self._register_callbacks()

    def _load_basic_settings(self) -> None:
        # V18.20.4.1 (W-b13): the legacy input/output handlers + output-count
        # badge were deleted with the V11.0.0 minefield — only the live-log
        # visibility + engine indicator remain.
        # apply live-log visibility from settings
        self._apply_live_log_visibility()
        # set the initial engine indicator
        self._refresh_engine_indicator()

    def _apply_live_log_visibility(self) -> None:
        """Show the live-log viewer only if the user enabled it in Settings."""
        show = self.controller.get_setting("ui.show_live_log", False)
        self.log_viewer.setVisible(bool(show))

    def apply_ui_preferences(self) -> None:
        """Called after the Settings dialog closes — refresh UI prefs that the
        user may have changed (output-folder override, live-log visibility,
        engine indicator)."""
        # output-folder override (empty → default to input folder)
        override = self.controller.get_setting("output.custom_dir", "")
        self._output_override = Path(override) if override else None
        # V11.31: guard against None (output_toggle_cb was removed in V11.0.0)
        if self.output_toggle_cb is not None:
            if override:
                if not self.output_toggle_cb.isChecked():
                    self.output_toggle_cb.blockSignals(True)
                    self.output_toggle_cb.setChecked(True)
                    self.output_toggle_cb.blockSignals(False)
                if hasattr(self, "output_picker") and self.output_picker:
                    self.output_picker.set_path(override)
                    self.output_picker.setVisible(True)
            else:
                if self.output_toggle_cb.isChecked():
                    self.output_toggle_cb.blockSignals(True)
                    self.output_toggle_cb.setChecked(False)
                    self.output_toggle_cb.blockSignals(False)
                if hasattr(self, "output_picker") and self.output_picker:
                    self.output_picker.setVisible(False)
        self._apply_live_log_visibility()
        self._refresh_engine_indicator()

    def _refresh_engine_indicator(self) -> None:
        """Update the pulsing engine dot behind the progress bar."""
        provider = self.controller.get_setting("summarisation.provider", "ollama")
        backend = self.controller.get_setting("ai.backend", "Ollama")
        api_type = self.controller.get_setting("ai.api_type", "OpenAI-Compatible")
        is_local = provider in ("ollama",)
        if is_local:
            label = f"Local · {backend}"
        else:
            label = f"API · {'Claude' if provider == 'claude' else api_type}"
        self.progress_panel.set_engine(label, is_local)

    def _cancel_conversion(self) -> None:
        if self.is_converting:
            self.controller.cancel_conversion()
            self.log_viewer.append("Cancelling…", "WARNING")
            self.progress_panel.set_status("Cancelling…", "error")
            self.progress_panel.enable_cancel(False)

    def _cancel_any_operation(self) -> None:
        # V18.20.4.1 (W-b13): the diagnostic-worker branch is gone with the
        # legacy Test Book flow — only the conversion cancel remains.
        if self.is_converting:
            self._cancel_conversion()

    # ══════════════════════════════════════════════════════════════════════
    # Bridge callbacks (run on main thread)
    # ══════════════════════════════════════════════════════════════════════
    def _on_status(self, message: str) -> None:
        self.progress_panel.set_status(message, "warning")

    def _on_complete(self, result: ConversionResult) -> None:
        self.is_converting = False
        self._set_cta_enabled(True)  # V18.20.3.14: None-guarded (was the crash)
        self.progress_panel.enable_cancel(False)
        if result.success:
            self.progress_panel.set_status("Conversion completed!", "success")
            self.log_viewer.append(f"Full markdown: {result.full_markdown_path}", "SUCCESS")
            if result.docx_path:
                self.log_viewer.append(f"DOCX: {result.docx_path}", "SUCCESS")
            # success chime (unless the user disabled it)
            if self.controller.get_setting("ui.play_success_sound", True):
                try:
                    from ui_qt.components.sounds import play_success

                    play_success()
                except Exception:
                    pass  # best-effort (UI — never crash)
            # V18.20.3.9 (Phase 2 / B1, V18.20.3.8 rig audit F1): success
            # dialog gains an "Open Summaries Folder" action — the canonical
            # provenance-stamped summaries live in <output>/summaries/, and
            # the wrong-folder pick was the recurring stale-file-upload
            # class. Also logged so the folder is copy-pasteable.
            from PySide6.QtWidgets import QMessageBox as _QMB

            _summ_dir = None
            if result.full_markdown_path:
                _walk = result.full_markdown_path.parent
                for _ in range(3):
                    if (_walk / "summaries").exists():
                        _summ_dir = _walk / "summaries"
                        break
                    _walk = _walk.parent
            if _summ_dir is not None:
                self.log_viewer.append(f"Summaries: {_summ_dir}", "SUCCESS")
            _box = _QMB(self)
            _box.setWindowTitle("Success")
            _box.setText(
                f"Conversion complete!\n\nMarkdown:\n{result.full_markdown_path}"
                + (f"\n\nDOCX:\n{result.docx_path}" if result.docx_path else "")
            )
            _open_summ = None
            if _summ_dir is not None:
                _open_summ = _box.addButton("Open Summaries Folder", _QMB.ActionRole)
            _box.addButton(_QMB.Close)
            _box.exec()
            if _open_summ is not None and _box.clickedButton() is _open_summ:
                try:
                    from PySide6.QtGui import QDesktopServices, QUrl

                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(_summ_dir)))
                except Exception:
                    pass  # best-effort (UI — never crash)
            # hide the progress panel after success — return to clean idle state
            self.progress_panel.setVisible(False)
        else:
            self.progress_panel.set_status(f"Failed: {result.error_msg}", "error")
            self.log_viewer.append(f"Failed: {result.error_msg}", "ERROR")

    # ══════════════════════════════════════════════════════════════════════
    # Theme refresh
    # ══════════════════════════════════════════════════════════════════════
    def refresh_theme(self) -> None:
        p = theme_manager.palette
        # V11.30.1: refresh tool dashboard cards (was missing — cards kept
        # light-mode background when switching to dark mode).
        if hasattr(self, "tool_dashboard") and self.tool_dashboard is not None:
            self.tool_dashboard.refresh_theme()
        # V18.20.4.1 (W-b13): the _type_cards / _type_head / _doc_head /
        # load_prev_btn branches never ran (those attributes were never
        # assigned after V11.0.0) — deleted with the legacy block.
        if hasattr(self, "log_viewer") and self.log_viewer is not None:
            self.log_viewer.refresh_theme()
        # V11.29.5: guard the optional CTA buttons (removed in V11.0.0)
        if getattr(self, "test_btn", None) is not None:
            self.test_btn.setIcon(icon("flask", p.text_primary, 16))
        if getattr(self, "convert_btn", None) is not None:
            self.convert_btn.setIcon(icon("rocket", p.text_on_accent, 17))
