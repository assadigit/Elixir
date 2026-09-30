"""Packets of Knowledge tool (V18.20.4.6, P5 / O-b2 split).

_PacketWorker + PacketsToolDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. The V13.20.0 banner below (shared with
the Hallucination Audit tool, same release) is verbatim.
ui_qt.views.service_dialogs.base_dialog re-exports both names
(back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ delegates the common
skeleton (title, Paste Text tab, options container, output row, live
log, progress, status, buttons) to the base; the multi-file queue tab
replaces the base's single-file tab (index 1 — pinned by the e2e
drive tests), and the byte-identical closeEvent guard + live-log
toggle fold into the base. The raw-QThread _PacketWorker flow, the
(msg, level) log signature and the _on_generate validation chain stay
as-is."""

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
    QFileDialog,
    QMessageBox,
    QWidget,
)

from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
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
            req = ConversionRequest(
                input_path=_P(self._output_dir), output_dir=_P(self._output_dir)
            )
            gen = PacketGenerator(
                request=req, log_callback=lambda msg, level="INFO": self.log_signal.emit(msg, level)
            )
            paths = gen.generate(
                summaries=self._summaries,
                book_title=self._book_title,
                output_dir=_P(self._output_dir),
            )
            if paths:
                self.done_signal.emit(str(self._output_dir), "")
            else:
                self.done_signal.emit("", "No packets generated — need at least 10 keypoints.")
        except Exception as e:
            import traceback

            self.done_signal.emit("", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}")


class PacketsToolDialog(BaseServiceDialog):
    """Standalone Packets of Knowledge tool — paste text or pick files → generate packets."""

    def __init__(self, controller, parent=None):
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options, which fills the multi-file
        # queue tab. The base also initializes self._worker (its closeEvent
        # guards it — _confirm_close_with_running_worker handles the raw
        # QThread _PacketWorker shape via isRunning()).
        self._files: list = []
        super().__init__(
            controller, "📦 Packets of Knowledge", parent, accept_files=True, accept_text=True
        )
        self.setMinimumSize(700, 680)
        # V0.6.10 (B17): the base builds out_path_edit / process_btn with
        # its own labels; this dialog's historical attribute names
        # (out_edit / gen_btn — pinned by the e2e drive tests) are restored
        # as aliases of the SAME widgets (single source of truth).
        self.out_edit = self.out_path_edit
        self.out_edit.setPlaceholderText("Choose where to save output files…")
        self.gen_btn = self.process_btn
        self.gen_btn.setText("📦 Generate Packets")
        self.live_log.setMaximumHeight(150)
        # V0.6.10 (B17): restore this dialog's pasted-text placeholder (the
        # base's generic one loses the ##-headings / .Chapters.md guidance).
        self.text_input.setPlaceholderText(
            "Paste notes here. Use ## headings to separate chapters.\n\n"
            "## Chapter 1\n- First bullet\n- Second bullet\n\n## Chapter 2\n- ...\n\n"
            "Or paste a .Chapters.md file (with ### Executive Summary + "
            "### Bullet Points sections) for full chapter-aligned mode."
        )
        self.status_label.setText("Ready — paste text or add files, then click Generate.")

    def _build_options(self, layout) -> None:
        """V0.6.10 (B17): the packets-specific rows, folded into the base's
        options container — the multi-file queue tab (tab index 1), the
        book-title row, and the V13.23.0 mode selector."""
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
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        # V0.6.10 (B17): the base's tabs come with a single-file "Pick
        # File" tab at index 1; this dialog's contract is a MULTI-file
        # queue tab at that index (pinned: tabs.setCurrentIndex(1) in the
        # e2e drive tests). Swap the page, keeping a Python reference to
        # the removed page so the base's file_path_edit stays alive (Qt
        # returns ownership to Python on removeTab — a GC'd page would
        # destroy the base's line edit).
        self._base_file_tab = self.tabs.widget(1)
        self.tabs.removeTab(1)

        desc = _QL(
            "Transform scattered notes into structured knowledge packets. "
            "Each packet clusters ~5 related bullets, then synthesizes them "
            "into a paragraph + TL;DR. Outputs: packets doc + one-page + map + coverage."
        )
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Multi-file queue tab (tab index 1 — see the swap note above).
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

        # Options
        title_row = _HL()
        title_row.addWidget(_QL("Book/Note title:"))
        self.title_edit = _QLE()
        self.title_edit.setPlaceholderText("e.g. My Research Notes")
        self.title_edit.setText("Knowledge Packets")
        title_row.addWidget(self.title_edit, 1)
        layout.addLayout(title_row)
        # V13.23.0: Packets mode selector — chapter-aligned (default, new
        # architecture) vs legacy cross-chapter semantic clustering.
        mode_row = _HL()
        mode_row.addWidget(_QL("Packets mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Chapter-aligned (recommended)", "chapter")
        self.mode_combo.addItem(
            "Cross-chapter clustering (legacy, may produce mismatched packets)", "cross_chapter"
        )
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)
        self.mode_warning_label = _QL(
            "⚠️ Cross-chapter mode uses semantic clustering that may produce "
            "mismatched packets. Chapter-aligned mode uses the author's own "
            "chapter boundaries for better results."
        )
        self.mode_warning_label.setWordWrap(True)
        self.mode_warning_label.setStyleSheet(
            "QLabel { color: #cc8800; font-size: 11px; padding: 4px 8px; "
            "background: #fff8e1; border: 1px solid #e6c200; border-radius: 3px; }"
        )
        self.mode_warning_label.setVisible(False)
        layout.addWidget(self.mode_warning_label)

    # V0.6.10 (B17): the closeEvent guard (identical to the base's — it
    # guards self._worker through _confirm_close_with_running_worker,
    # which supports the raw-QThread isRunning() shape) and the live-log
    # _toggle_live_log are now INHERITED from BaseServiceDialog; the
    # pre-B17 copies were byte-equivalent and were deleted. _on_process
    # routes the base's process button to this dialog's _on_generate.

    def _on_process(self) -> None:
        # V0.6.10 (B17): the base wired the (aliased) gen_btn to
        # _on_process; packets' generate flow is the _on_generate chain
        # (multi-file/paste validation + _PacketWorker spawn).
        self._on_generate()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add note files", "", "Markdown/Text (*.md *.txt);;All files (*.*)"
        )
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
        # V0.6.10 (B17): override — packets write FOUR sibling files into a
        # FOLDER, not one file; the base's file-save picker does not fit.
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _on_mode_changed(self, _index: int) -> None:
        """V13.23.0: Toggle the cross-chapter warning label visibility."""
        mode = self.mode_combo.currentData()
        self.mode_warning_label.setVisible(mode == "cross_chapter")

    def _append_live_log(self, msg, level="INFO"):
        # V0.6.10 (B17): kept override — the base's _append_live_log takes
        # (msg) only; this dialog's worker log_signal carries (msg, level).
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
            summaries.append(
                SummaryResult(
                    chapter_heading=heading or f"Chapter {len(summaries) + 1}",
                    executive_summary="",
                    thorough_summary="",
                    bullet_points=bullets,
                    success=True,
                )
            )
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
        if (
            "## Table of Contents" in text
            and "### Executive Summary" in text
            and "### Bullet Points" in text
        ):
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
        return [
            SummaryResult(
                chapter_heading=heading,
                executive_summary="",
                thorough_summary="",
                bullet_points=bullets,
                success=True,
            )
        ]

    def _on_generate(self):
        active_tab = self.tabs.currentIndex()
        summaries = []
        if active_tab == 0:
            text = self.text_input.toPlainText().strip()
            if not text or len(text) < 20:
                QMessageBox.warning(
                    self, "Need more text", "Please paste some notes (at least 20 characters)."
                )
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
            QMessageBox.warning(
                self, "Not enough keypoints", f"Need at least 10 keypoints. Found {total_bullets}."
            )
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
            f"📦 Generating packets from {total_bullets} keypoints in {len(summaries)} section(s)..."
        )
        self.live_log.clear()
        if not self._log_toggle_btn.isChecked():
            self._log_toggle_btn.setChecked(True)
            self._toggle_live_log(True)
        self._append_live_log(f"📦 Input: {total_bullets} keypoints, {len(summaries)} sections")
        self._append_live_log(f"📦 Title: {book_title}")
        self._append_live_log(f"📦 Output: {out_folder}")

        mode = self.mode_combo.currentData() if hasattr(self, "mode_combo") else "chapter"
        self._worker = _PacketWorker(summaries, book_title, out_folder, mode=mode, parent=self)
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
            _show_success_modal(
                self,
                "📦 Packets of Knowledge Complete",
                f"Packets generated successfully!\n\nOutput folder:\n{output_dir}",
                file_path=output_dir,
                on_try_another=None,
            )
