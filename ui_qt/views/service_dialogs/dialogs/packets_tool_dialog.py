"""Packets of Knowledge tool (V18.20.4.6, P5 / O-b2 split).

_PacketWorker + PacketsToolDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. The V13.20.0 banner below (shared with
the Hallucination Audit tool, same release) is verbatim.
ui_qt.views.service_dialogs.base_dialog re-exports both names
(back-compat facade)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import QThread, Signal

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QMessageBox,
    QPlainTextEdit,
    QWidget,
)

from ui_qt.views.service_dialogs.dialogs.shared import (
    PlainTextTextEdit,
    _confirm_close_with_running_worker,
    _show_success_modal,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V13.20.0: Packets of Knowledge + Hallucination Audit — standalone tools
# ════════════════════════════════════════════════════════════════════════════

class _PacketWorker(QThread):
    """Background thread for packet generation."""
    log_signal = Signal(str, str)
    done_signal = Signal(str, str)

    def __init__(self, summaries, book_title, output_dir, mode="chapter", parent=None):
        super().__init__(parent)
        self._summaries = summaries
        self._book_title = book_title
        self._output_dir = output_dir
        # V13.23.0: Packets mode — "chapter" (default, author-aligned) or
        # "cross_chapter" (legacy semantic clustering).
        self._mode = mode if mode in ("chapter", "cross_chapter") else "chapter"

    def run(self):
        try:
            from pathlib import Path as _P

            from core.models import ConversionRequest
            from core.outputs.packets import PacketGenerator

            # V13.23.0: Persist the user-selected packets mode so the
            # PacketGenerator picks up chapter-aligned vs cross-chapter logic.
            from utils.settings import Settings
            try:
                s = Settings()
                s.set("packets.mode", self._mode)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)
            req = ConversionRequest(input_path=_P(self._output_dir),
                                    output_dir=_P(self._output_dir))
            gen = PacketGenerator(
                request=req,
                log_callback=lambda msg, level="INFO": self.log_signal.emit(msg, level))
            paths = gen.generate(summaries=self._summaries, book_title=self._book_title,
                                 output_dir=_P(self._output_dir))
            if paths:
                self.done_signal.emit(str(self._output_dir), "")
            else:
                self.done_signal.emit("", "No packets generated — need at least 10 keypoints.")
        except Exception as e:
            import traceback
            self.done_signal.emit("", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}")


class PacketsToolDialog(QDialog):
    """Standalone Packets of Knowledge tool — paste text or pick files → generate packets."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("📦 Packets of Knowledge")
        self.setMinimumSize(700, 680)
        self.setModal(True)
        self._worker = None
        self._files = []

        from PySide6.QtWidgets import (
            QGroupBox as _QGB,
        )
        from PySide6.QtWidgets import (
            QHBoxLayout as _HL,
        )
        from PySide6.QtWidgets import (
            QLabel as _QL,
        )
        from PySide6.QtWidgets import (
            QLineEdit as _QLE,
        )
        from PySide6.QtWidgets import (
            QListWidget as _QLW,
        )
        from PySide6.QtWidgets import (
            QProgressBar as _QPB2,
        )
        from PySide6.QtWidgets import (
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QTabWidget as _QTW,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )
        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        title = _QL("📦 Packets of Knowledge")
        title.setObjectName("H2")
        lay.addWidget(title)
        desc = _QL("Transform scattered notes into structured knowledge packets. "
                   "Each packet clusters ~5 related bullets, then synthesizes them "
                   "into a paragraph + TL;DR. Outputs: packets doc + one-page + map + coverage.")
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Input tabs
        self.tabs = _QTW()
        text_tab = QWidget()
        text_lay = _VL(text_tab)
        self.text_input = PlainTextTextEdit()
        self.text_input.setPlaceholderText(
            "Paste notes here. Use ## headings to separate chapters.\n\n"
            "## Chapter 1\n- First bullet\n- Second bullet\n\n## Chapter 2\n- ...\n\n"
            "Or paste a .Chapters.md file (with ### Executive Summary + "
            "### Bullet Points sections) for full chapter-aligned mode.")
        self.text_input.setAcceptRichText(False)
        text_lay.addWidget(self.text_input)
        self.tabs.addTab(text_tab, "📋 Paste Text")

        file_tab = QWidget()
        file_lay = _VL(file_tab)
        self.file_list = _QLW()
        self.file_list.setMinimumHeight(100)
        file_btn_row = _HL()
        add_btn = _QPB("Add Files…")
        add_btn.clicked.connect(self._add_files)
        rm_btn = _QPB("Remove")
        rm_btn.clicked.connect(self._remove_file)
        file_btn_row.addWidget(add_btn)
        file_btn_row.addWidget(rm_btn)
        file_btn_row.addStretch()
        file_lay.addWidget(self.file_list)
        file_lay.addLayout(file_btn_row)
        self.tabs.addTab(file_tab, "📁 Pick Files (multi)")
        lay.addWidget(self.tabs)

        # Options
        opt_group = _QGB("Options:")
        opt_lay = _VL(opt_group)
        title_row = _HL()
        title_row.addWidget(_QL("Book/Note title:"))
        self.title_edit = _QLE()
        self.title_edit.setPlaceholderText("e.g. My Research Notes")
        self.title_edit.setText("Knowledge Packets")
        title_row.addWidget(self.title_edit, 1)
        opt_lay.addLayout(title_row)
        out_row = _HL()
        out_row.addWidget(_QL("Output folder:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose where to save output files…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        opt_lay.addLayout(out_row)
        # V13.23.0: Packets mode selector — chapter-aligned (default, new
        # architecture) vs legacy cross-chapter semantic clustering.
        mode_row = _HL()
        mode_row.addWidget(_QL("Packets mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Chapter-aligned (recommended)", "chapter")
        self.mode_combo.addItem(
            "Cross-chapter clustering (legacy, may produce mismatched packets)",
            "cross_chapter")
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo, 1)
        opt_lay.addLayout(mode_row)
        self.mode_warning_label = _QL(
            "⚠️ Cross-chapter mode uses semantic clustering that may produce "
            "mismatched packets. Chapter-aligned mode uses the author's own "
            "chapter boundaries for better results.")
        self.mode_warning_label.setWordWrap(True)
        self.mode_warning_label.setStyleSheet(
            "QLabel { color: #cc8800; font-size: 11px; padding: 4px 8px; "
            "background: #fff8e1; border: 1px solid #e6c200; border-radius: 3px; }")
        self.mode_warning_label.setVisible(False)
        opt_lay.addWidget(self.mode_warning_label)
        lay.addWidget(opt_group)

        # Live log
        self._log_toggle_btn = _QPB("📋 Show Live Log")
        self._log_toggle_btn.setObjectName("Compact")
        self._log_toggle_btn.setCheckable(True)
        self._log_toggle_btn.setChecked(False)
        self._log_toggle_btn.clicked.connect(self._toggle_live_log)
        lay.addWidget(self._log_toggle_btn)
        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setMaximumHeight(150)
        self.live_log.setVisible(False)
        self.live_log.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; "
            "font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; "
            "border: 1px solid #3c3c3c; }")
        lay.addWidget(self.live_log)

        # Status + progress
        self.status_label = _QL("Ready — paste text or add files, then click Generate.")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)
        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)
        # Generate button
        self.gen_btn = _QPB("📦 Generate Packets")
        self.gen_btn.setObjectName("Primary")
        self.gen_btn.clicked.connect(self._on_generate)
        lay.addWidget(self.gen_btn)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the _PacketWorker
        # QThread runs — it is PARENTED to this dialog, so destroying the
        # dialog mid-run is exactly the "QThread: Destroyed while thread is
        # still running" abort. The shared guard handles raw-QThread
        # workers (isRunning() + signal disconnect + unparent on confirm).
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _add_files(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add note files", "",
            "Markdown/Text (*.md *.txt);;All files (*.*)")
        if paths:
            for p in paths:
                if p not in self._files:
                    self._files.append(p)
                    self.file_list.addItem(p)

    def _remove_file(self):
        row = self.file_list.currentRow()
        if 0 <= row < len(self._files):
            self._files.pop(row)
            self.file_list.takeItem(row)

    def _pick_output(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _on_mode_changed(self, _index: int) -> None:
        """V13.23.0: Toggle the cross-chapter warning label visibility."""
        mode = self.mode_combo.currentData()
        self.mode_warning_label.setVisible(mode == "cross_chapter")

    def _toggle_live_log(self, checked):
        self.live_log.setVisible(checked)
        self._log_toggle_btn.setText(
            "📋 Hide Live Log" if checked else "📋 Show Live Log")

    def _append_live_log(self, msg, level="INFO"):
        import datetime as _dt
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        self.live_log.appendPlainText(f"[{ts}] {msg}")

    @staticmethod
    def _extract_bullets(text):
        """Extract bullet lines from text — strips markdown bullet markers."""
        bullets = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = re.match(r"^[-*+•·▪◦‣]\s+(.+)$", stripped)
            if m:
                clean = m.group(1).strip()
                if clean and len(clean) > 5:
                    bullets.append(clean)
                continue
            m = re.match(r"^\d+[.):]\s+(.+)$", stripped)
            if m:
                clean = m.group(1).strip()
                if clean and len(clean) > 5:
                    bullets.append(clean)
        return bullets

    @staticmethod
    def _parse_pasted_text(text):
        """Split pasted text into chapters by ## headings; extract bullets."""
        from core.models import SummaryResult
        chunks = []
        current_heading = ""
        current_body = []
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^##(?!#)\s+(.+)$", stripped):
                if current_heading or current_body:
                    chunks.append((current_heading, "\n".join(current_body)))
                m = re.match(r"^##\s+(.+)$", stripped)
                current_heading = m.group(1).strip() if m else ""
                current_body = []
            else:
                current_body.append(line)
        if current_heading or current_body:
            chunks.append((current_heading, "\n".join(current_body)))
        if not chunks:
            chunks = [("Notes", text)]
        summaries = []
        for heading, body in chunks:
            bullets = PacketsToolDialog._extract_bullets(body)
            if not bullets:
                continue
            summaries.append(SummaryResult(
                chapter_heading=heading or f"Chapter {len(summaries)+1}",
                executive_summary="", thorough_summary="",
                bullet_points=bullets, success=True))
        return summaries

    @staticmethod
    def _parse_file(path):
        """Parse one .md/.txt file → list[SummaryResult] (or None on read error).

        V13.23.0: If the file looks like a ``.Chapters.md`` export (contains
        ``## Table of Contents`` + ``### Executive Summary`` + ``### Bullet
        Points``), delegate to :func:`read_chapters_md` so each chapter section
        becomes its own SummaryResult with executive_summary populated.
        Otherwise, fall back to legacy behavior (whole file = one chapter,
        bullets only, exec_summary="").
        """
        from core.models import SummaryResult
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
        if not text.strip():
            return None
        # V13.23.0: Detect chapters-md format and use the dedicated parser.
        if ("## Table of Contents" in text
                and "### Executive Summary" in text
                and "### Bullet Points" in text):
            try:
                from core.outputs.chapters_export import read_chapters_md
                _book_title, summaries = read_chapters_md(Path(path))
                return summaries if summaries else []
            except Exception:
                # Fall through to legacy parsing if chapters-md parse fails.
                pass
        heading = Path(path).stem
        bullets = PacketsToolDialog._extract_bullets(text)
        if not bullets:
            return []
        return [SummaryResult(chapter_heading=heading, executive_summary="",
                              thorough_summary="", bullet_points=bullets,
                              success=True)]

    def _on_generate(self):
        active_tab = self.tabs.currentIndex()
        summaries = []
        if active_tab == 0:
            text = self.text_input.toPlainText().strip()
            if not text or len(text) < 20:
                QMessageBox.warning(self, "Need more text",
                                    "Please paste some notes (at least 20 characters).")
                return
            summaries = self._parse_pasted_text(text)
        else:
            if not self._files:
                QMessageBox.warning(self, "No files", "Please add at least one .md or .txt file.")
                return
            for f in self._files:
                chunk = self._parse_file(f)
                if chunk:
                    summaries.extend(chunk)

        total_bullets = sum(len(s.bullet_points) for s in summaries)
        if total_bullets < 10:
            QMessageBox.warning(self, "Not enough keypoints",
                                f"Need at least 10 keypoints. Found {total_bullets}.")
            return

        out_folder = self.out_edit.text().strip()
        if not out_folder:
            QMessageBox.warning(self, "No output folder", "Please choose an output folder.")
            return

        book_title = self.title_edit.text().strip() or "Knowledge Packets"
        self.gen_btn.setEnabled(False)
        self.gen_btn.setText("📦 Generating...")
        self.progress_bar.setVisible(True)
        self.status_label.setText(
            f"📦 Generating packets from {total_bullets} keypoints in {len(summaries)} section(s)...")
        self.live_log.clear()
        if not self._log_toggle_btn.isChecked():
            self._log_toggle_btn.setChecked(True)
            self._toggle_live_log(True)
        self._append_live_log(f"📦 Input: {total_bullets} keypoints, {len(summaries)} sections")
        self._append_live_log(f"📦 Title: {book_title}")
        self._append_live_log(f"📦 Output: {out_folder}")

        mode = (self.mode_combo.currentData()
                if hasattr(self, "mode_combo") else "chapter")
        self._worker = _PacketWorker(summaries, book_title, out_folder,
                                     mode=mode, parent=self)
        self._worker.log_signal.connect(self._append_live_log)
        self._worker.done_signal.connect(self._on_done)
        self._worker.start()

    def _on_done(self, output_dir, error):
        self.progress_bar.setVisible(False)
        self.gen_btn.setEnabled(True)
        self.gen_btn.setText("📦 Generate Packets")
        if error:
            self.status_label.setText(f"❌ {error}")
            self._append_live_log(f"❌ {error}")
            QMessageBox.critical(self, "❌ Packets Failed", error)
        else:
            self.status_label.setText(f"✅ Packets generated in: {output_dir}")
            self._append_live_log(f"✅ Done! Output: {output_dir}")
            _show_success_modal(self, "📦 Packets of Knowledge Complete",
                                f"Packets generated successfully!\n\nOutput folder:\n{output_dir}",
                                file_path=output_dir, on_try_another=None)
