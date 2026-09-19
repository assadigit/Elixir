"""Shared plumbing for the service dialogs (V18.20.4.6, P5 / O-b2 split).

Moved VERBATIM from ui_qt/views/service_dialogs/base_dialog.py
(one module per dialog): every segment below is byte-identical to
the pre-split definition — only this module's top-of-file imports
differ. Holds the cross-dialog pieces: PlainTextTextEdit (the
plain-text paste widget), the V11.25 shared success modal, the
V18.20.4.5 (T-b2) close-event guard helpers, and the
BaseServiceDialog base class (Translation + TTS subclass it).
ui_qt.views.service_dialogs.base_dialog re-exports everything
(back-compat facade)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMimeData, QThread

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# V11.31.1: PlainTextTextEdit — forces plain-text paste (strips all
# formatting: HTML, RTF, colors, fonts, sizes). Used by all service
# dialogs that accept pasted text (Summarize, Translation, TTS).
# ═══════════════════════════════════════════════════════════════════════


class PlainTextTextEdit(QTextEdit):
    """QTextEdit that strips ALL formatting on paste — only plain text."""

    def insertFromMimeData(self, source: QMimeData) -> None:
        """Override to force plain-text insertion regardless of source format."""
        if source.hasText():
            # Insert as plain text — strips HTML, RTF, colors, fonts.
            super().insertPlainText(source.text())
        elif source.hasHtml():
            # Extract plain text from HTML.
            super().insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


# ════════════════════════════════════════════════════════════════════════════
# V11.25: Shared success modal — used by all service dialogs after completion.
# Offers "Try Another" (reset dialog) + "Open File/Folder" (file explorer).
# ════════════════════════════════════════════════════════════════════════════


def _show_success_modal(
    parent, title: str, message: str, file_path: str | None = None, on_try_another=None
) -> None:
    """Show a success modal with 'Try Another' + 'Open File/Folder' buttons.

    Args:
        parent:        the parent QDialog (for modal positioning).
        title:         modal title (e.g. "OCR Complete").
        message:       the success summary text.
        file_path:     path to the output file (or folder). If it's a file,
                       the explorer opens with the file selected; if a folder,
                       the folder opens directly.
        on_try_another: callable invoked when the user clicks "Try Another".
                       If None, the button is hidden.
    """
    import subprocess
    import sys
    from pathlib import Path as _P

    from PySide6.QtWidgets import QMessageBox

    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Information)
    msg.setText(message)

    # Build custom buttons.
    open_btn = None
    again_btn = None
    if file_path:
        open_btn = msg.addButton("📂 Open File Location", QMessageBox.AcceptRole)
    if on_try_another:
        again_btn = msg.addButton("🔄 Try Another", QMessageBox.ActionRole)
    msg.addButton("✓ Close", QMessageBox.RejectRole)

    msg.exec()

    # Determine which button was clicked.
    clicked = msg.clickedButton()
    if clicked is not None and open_btn is not None and clicked == open_btn:
        # Open the file's containing folder in the OS file explorer.
        try:
            p = _P(file_path)
            if sys.platform == "win32":
                # Windows: `explorer /select,"file"` opens folder + selects file.
                if p.is_file():
                    subprocess.Popen(["explorer", "/select,", str(p)])
                else:
                    subprocess.Popen(["explorer", str(p)])
            elif sys.platform == "darwin":
                # macOS: `open -R` reveals the file in Finder.
                if p.is_file():
                    subprocess.Popen(["open", "-R", str(p)])
                else:
                    subprocess.Popen(["open", str(p)])
            else:
                # Linux: xdg-open the folder.
                folder = p.parent if p.is_file() else p
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)
    elif clicked is not None and again_btn is not None and clicked == again_btn:
        try:
            on_try_another()
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════
# V18.20.4.5 (T-b2): close-event guards for running workers.
#
# OLD DEFECT: no dialog in this file had a closeEvent override (grep: zero),
# so closing a dialog while its worker ran either aborted the process
# ("QThread: Destroyed while thread is still running" once the dialog was
# destroyed — the raw-QThread workers are parented to the dialog) or let
# queued finished/failed slots touch dead widgets mid-teardown. Every
# worker-owning dialog now funnels its closeEvent through the shared guard
# below: ask for confirmation, and on "close anyway" detach the worker
# (disconnect its signals; unparent raw QThreads) so its result is
# discarded instead of crashing.
# ════════════════════════════════════════════════════════════════════════════


def _worker_is_running(worker) -> bool:
    """V18.20.4.5 (T-b2): True if ``worker`` is actively running.

    Supports the two worker shapes living in this file:
    ``SimpleWorker``/``BaseWorker`` (``is_running()``) and raw ``QThread``
    workers (``isRunning()``).
    """
    if worker is None:
        return False
    try:
        if isinstance(worker, QThread):
            return bool(worker.isRunning())
        if hasattr(worker, "is_running"):
            return bool(worker.is_running())
    except Exception:
        logger.debug("best-effort op failed", exc_info=True)
    return False


def _detach_worker_signals(worker) -> None:
    """V18.20.4.5 (T-b2): disconnect every signal of ``worker``.

    Called only after the user confirms "close anyway" — the worker keeps
    running (its work is harmless), but its queued slots must never fire
    into a half-destroyed widget tree. SimpleWorker's internal auto-delete
    is re-armed afterwards (the blanket ``disconnect()`` removed it too);
    raw QThread workers parented to the dialog are unparented so a later
    delete of the dialog tree cannot destroy a live thread (the abort
    class this guard exists to prevent).
    """
    for name in ("finished", "failed", "progress", "done_signal", "log_signal"):
        sig = getattr(worker, name, None)
        if sig is None:
            continue
        try:
            sig.disconnect()
        except Exception:
            # Not connected / already disconnected — fine.
            logger.debug("best-effort disconnect failed", exc_info=True)
    if isinstance(worker, SimpleWorker):
        # Re-arm the auto-delete that SimpleWorker.__init__ wired
        # (finished/failed → deleteLater) so the detached worker still
        # frees itself once run() completes.
        try:
            worker.finished.connect(lambda _r: worker.deleteLater())
            worker.failed.connect(lambda _e: worker.deleteLater())
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)
    elif isinstance(worker, QThread):
        # Raw QThread workers (_PacketWorker, _HallucinationAuditWorker)
        # are constructed with parent=dialog; unparent so the dialog's
        # destruction cannot take the live thread object with it.
        try:
            worker.setParent(None)
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)


def _confirm_close_with_running_worker(dialog, worker) -> bool:
    """V18.20.4.5 (T-b2): shared close-event guard for worker-owning dialogs.

    Returns True when the close may proceed (nothing running, or the user
    confirmed); False when the close must be vetoed (the caller then calls
    ``event.ignore()``). On confirmation the worker is detached via
    ``_detach_worker_signals`` — the task continues, its result is
    discarded, and no slot ever touches a dead widget.
    """
    if not _worker_is_running(worker):
        return True
    ret = QMessageBox.question(
        dialog,
        "Work in progress",
        "A background task is still running.\n\nClose anyway? "
        "The task will continue but its result will be discarded.",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if ret != QMessageBox.Yes:
        return False
    _detach_worker_signals(worker)
    return True


class BaseServiceDialog(QDialog):
    """Base class for standalone service dialogs."""

    def __init__(
        self,
        controller: Controller,
        title: str,
        parent: QWidget | None = None,
        accept_files: bool = True,
        accept_text: bool = True,
    ):
        super().__init__(parent)
        self.controller = controller
        self._accept_files = accept_files
        self._accept_text = accept_text
        self._worker: SimpleWorker | None = None
        self._cancel_requested = False

        self.setWindowTitle(title)
        self.setMinimumSize(560, 480)
        self.setModal(True)
        self._build_ui()

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the service worker
        # runs — the "QThread: Destroyed while thread is still running"
        # abort class. No subclass overrides closeEvent (verified: zero in
        # this file before V18.20.4.5), so this ONE base-class guard covers
        # TranslationServiceDialog + TtsServiceDialog's main worker.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title_label = QLabel(self.windowTitle())
        title_label.setObjectName("H2")
        root.addWidget(title_label)

        # Input tabs
        if self._accept_text and self._accept_files:
            self.tabs = QTabWidget()
            text_tab = QWidget()
            text_lay = QVBoxLayout(text_tab)
            self.text_input = PlainTextTextEdit()
            self.text_input.setPlaceholderText("Paste your text here…")
            self.text_input.setAcceptRichText(False)  # V11.31: strip styling on paste
            text_lay.addWidget(self.text_input)
            self.tabs.addTab(text_tab, "📋 Paste Text")

            file_tab = QWidget()
            file_lay = QHBoxLayout(file_tab)
            self.file_path_edit = QLineEdit()
            self.file_path_edit.setPlaceholderText("Pick a file…")
            file_btn = QPushButton("Browse…")
            file_btn.clicked.connect(self._pick_file)
            file_lay.addWidget(self.file_path_edit)
            file_lay.addWidget(file_btn)
            self.tabs.addTab(file_tab, "📁 Pick File")
            root.addWidget(self.tabs)
        elif self._accept_text:
            self.text_input = PlainTextTextEdit()
            self.text_input.setPlaceholderText("Paste your text here…")
            self.text_input.setAcceptRichText(False)  # V11.31: strip styling on paste
            root.addWidget(self.text_input)
        elif self._accept_files:
            file_row = QHBoxLayout()
            self.file_path_edit = QLineEdit()
            self.file_path_edit.setPlaceholderText("Pick a file…")
            file_btn = QPushButton("Browse…")
            file_btn.clicked.connect(self._pick_file)
            file_row.addWidget(self.file_path_edit, 1)
            file_row.addWidget(file_btn)
            root.addLayout(file_row)

        # Service-specific options
        self._options_widget = QWidget()
        self._options_layout = QVBoxLayout(self._options_widget)
        self._options_layout.setContentsMargins(0, 0, 0, 0)
        self._options_layout.setSpacing(6)
        self._build_options(self._options_layout)
        root.addWidget(self._options_widget)

        # Output location
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        out_label = QLabel("Save to:")
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setPlaceholderText("Choose output location…")
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self._pick_output)
        out_row.addWidget(out_label)
        out_row.addWidget(self.out_path_edit, 1)
        out_row.addWidget(out_btn)
        root.addLayout(out_row)

        # Progress + status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        # V11.51.0: Live log panel (toggleable) — shows real-time log
        # messages from the engine (VibeVoice timing, CUDA status, etc.)
        # accumulated in a scrollable read-only text area.
        self._log_toggle_btn = QPushButton("📋 Show Live Log")
        self._log_toggle_btn.setObjectName("Compact")
        self._log_toggle_btn.setCheckable(True)
        self._log_toggle_btn.setChecked(False)
        self._log_toggle_btn.clicked.connect(self._toggle_live_log)
        root.addWidget(self._log_toggle_btn)

        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(180)
        self.live_log.setVisible(False)
        self.live_log.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; "
            "font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; "
            "border: 1px solid #3c3c3c; }"
        )
        root.addWidget(self.live_log)

        # Result preview
        self.result_preview = QTextEdit()
        self.result_preview.setReadOnly(True)
        self.result_preview.setPlaceholderText("Results will appear here…")
        self.result_preview.setVisible(False)
        root.addWidget(self.result_preview, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("Compact")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        # V11.18: "Try Another File" — after a successful run, clears input +
        # output so the user can process a different file without reopening.
        self.again_btn = QPushButton("🔄 Try Another File")
        self.again_btn.setObjectName("Compact")
        self.again_btn.setVisible(False)
        self.again_btn.clicked.connect(self._on_try_another)
        self.process_btn = QPushButton("Process")
        self.process_btn.setObjectName("Primary")
        self.process_btn.clicked.connect(self._on_process)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.again_btn)
        btn_row.addWidget(self.process_btn)
        root.addLayout(btn_row)

    def _build_options(self, layout: QVBoxLayout) -> None:
        pass

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pick a file", "", "All files (*.*)")
        if path:
            self.file_path_edit.setText(path)

    def _pick_output(self) -> None:
        suffix = self._get_output_suffix()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save output", "", f"Output (*{suffix});;All files (*.*)"
        )
        if path:
            if not path.endswith(suffix):
                path += suffix
            self.out_path_edit.setText(path)

    def _get_output_suffix(self) -> str:
        return ".txt"

    def _get_service_name(self) -> str:
        return "service"

    def _get_input_text(self) -> str:
        if self._accept_text and self._accept_files:
            if self.tabs.currentIndex() == 0:
                return self.text_input.toPlainText()
            else:
                path = self.file_path_edit.text().strip()
                if path and Path(path).exists():
                    return Path(path).read_text(encoding="utf-8", errors="replace")
                return ""
        elif self._accept_text:
            return self.text_input.toPlainText()
        elif self._accept_files:
            path = self.file_path_edit.text().strip()
            if path and Path(path).exists():
                return Path(path).read_text(encoding="utf-8", errors="replace")
            return ""
        return ""

    def _on_process(self) -> None:
        # For file-only dialogs, pass the file path (not content) to _process
        if not self._accept_text and self._accept_files:
            input_data = self.file_path_edit.text().strip()
            if not input_data:
                QMessageBox.warning(self, "No file", "Please pick a file.")
                return
        else:
            input_data = self._get_input_text()
            if not input_data.strip():
                QMessageBox.warning(self, "No input", "Please provide some text or pick a file.")
                return
        out_path = self.out_path_edit.text().strip()
        if not out_path:
            QMessageBox.warning(self, "No output", "Please choose where to save the output.")
            return
        self.process_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Processing…")
        self._cancel_requested = False
        options = self._collect_options()
        self._worker = SimpleWorker(self._process, input_data, options)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_error)
        # V11.21: wire the progress signal so subclasses can emit per-chunk
        # updates (translation, TTS) without rolling their own worker.
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        """V11.21: Receive a progress update from the background worker.

        ``pct`` is 0–100 (or -1 for indeterminate). ``msg`` is a status
        string. This runs on the MAIN thread (Qt queued signal) — safe to
        touch widgets. V11.29.2: removed QApplication.processEvents() which
        caused re-entrancy + thread-safety crashes (QTextDocument timer).
        V11.51.0: also appends the message to the live log panel.
        """
        if pct >= 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
        else:
            self.progress_bar.setRange(0, 0)  # indeterminate
        self.status_label.setText(f"<div style='font-size:14px; font-weight:600;'>{msg}</div>")
        # V11.51.0: also append to the live log panel (if it exists)
        if hasattr(self, "live_log"):
            self._append_live_log(msg)
        # V11.29.2: NO QApplication.processEvents() here — it causes
        # re-entrancy + QTextDocument thread-safety crashes. Qt signals
        # already queue to the main thread; processEvents is unnecessary.

    def _emit_progress(self, pct: int, msg: str) -> None:
        """V11.21: Emit a progress update from inside ``_process``.

        Safe to call from the background thread — Qt queues the signal to
        the main thread. No-op if no worker is running.
        """
        worker = getattr(self, "_worker", None)
        if worker is not None:
            try:
                worker.progress.emit(pct, msg)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

    def _toggle_live_log(self, checked: bool) -> None:
        """V11.51.0: Toggle the live log panel visibility."""
        self.live_log.setVisible(checked)
        self._log_toggle_btn.setText("📋 Hide Live Log" if checked else "📋 Show Live Log")

    def _append_live_log(self, msg: str) -> None:
        """V11.51.0: Append a message to the live log panel.

        Thread-safe — called from _on_progress on the main thread.
        Auto-scrolls to the bottom.
        """
        import datetime as _dt

        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self.live_log.appendPlainText(f"[{ts}] {msg}")
        # Auto-scroll to bottom
        sb = self.live_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_cancel(self) -> None:
        reply = QMessageBox.question(
            self, "Cancel?", "Are you sure you want to cancel?", QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._cancel_requested = True
            self._reset_ui()
            self.status_label.setText("Cancelled.")

    def _on_finished(self, result: Any) -> None:
        self._reset_ui()
        # V11.31.12: check for error strings returned by _process.
        if isinstance(result, str) and result.startswith("Error:"):
            self.status_label.setText(f"❌ {result}")
            self.again_btn.setVisible(True)
            return
        if result:
            if isinstance(result, str):
                self.result_preview.setPlainText(result)
                self.result_preview.setVisible(True)
            out_path = Path(self.out_path_edit.text().strip())
            # V11.27: _save_result may return the ACTUAL saved path (with
            # adjusted extension). If it returns None, fall back to out_path.
            actual_path = self._save_result(result, out_path)
            if actual_path is None:
                actual_path = str(out_path)
            from pathlib import Path as _P

            self.status_label.setText(f"✅ Done — saved to {_P(actual_path).name}")
            # V11.18: surface "Try Another File".
            self.again_btn.setVisible(True)
            # V11.30: defer the success modal via QTimer.singleShot(0, ...)
            # so the worker thread's deleteLater is processed first.
            # This prevents the QTextDocument thread-safety crash that
            # happened when QMessageBox.exec() created a nested event loop
            # while the worker thread was still cleaning up.
            p = _P(actual_path)
            file_arg = str(p) if p.exists() else (str(p.parent) if str(p.parent) != "." else None)
            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                0,
                lambda: _show_success_modal(
                    self,
                    f"✅ {self.windowTitle()} Complete",
                    f"Saved to: {actual_path}",
                    file_path=file_arg,
                    on_try_another=self._on_try_another
                    if hasattr(self, "_on_try_another")
                    else None,
                ),
            )
        else:
            self.status_label.setText("⚠️ No result returned.")

    def _on_error(self, error_msg: str) -> None:
        self._reset_ui()
        self.status_label.setText(f"❌ Error: {error_msg}")

    def _reset_ui(self) -> None:
        self.process_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)

    def _on_try_another(self) -> None:
        """V11.18: Reset the dialog for the next file.

        Clears the input text / file path, the output path, the result
        preview, and the status label — but keeps the service-specific
        options (language, voice, etc.) so the user doesn't have to
        re-configure them.
        """
        if self._accept_text and self._accept_files:
            self.text_input.clear()
            self.file_path_edit.clear()
            if hasattr(self, "tabs"):
                self.tabs.setCurrentIndex(1)  # jump to the "Pick File" tab
        elif self._accept_text:
            self.text_input.clear()
        elif self._accept_files:
            self.file_path_edit.clear()
        self.out_path_edit.clear()
        self.result_preview.clear()
        self.result_preview.setVisible(False)
        # V11.27: clear the multi-file queue if present.
        if hasattr(self, "_file_queue") and self._file_queue:
            self._file_queue.clear()
            if hasattr(self, "file_queue_list"):
                self.file_queue_list.clear()
        self.status_label.setText("Ready for the next file — pick a file and click Process.")
        self.again_btn.setVisible(False)
        self.process_btn.setVisible(True)

    def _collect_options(self) -> dict:
        return {}

    def _process(self, input_text: str, options: dict) -> Any:
        raise NotImplementedError

    def _save_result(self, result: Any, path: Path) -> str | None:
        """Save the result to ``path``. Returns the actual saved path (may
        differ from ``path`` if the subclass adjusted the extension).

        V11.27: returns the path so ``_on_finished`` can show the correct
        filename in the status + success modal.
        """
        if isinstance(result, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result, encoding="utf-8")
            return str(path)
        return None

    def _save_setting(self, key: str, value: Any) -> None:
        self.controller.update_setting(f"quick_services.{self._get_service_name()}.{key}", value)

    def _get_setting(self, key: str, default: Any = None) -> Any:
        return self.controller.get_setting(
            f"quick_services.{self._get_service_name()}.{key}", default
        )
