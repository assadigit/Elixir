"""Image Extractor dialog (V18.20.4.6, P5 / O-b2 split).

ImageExtractorDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import logging
from pathlib import Path

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker

from ui_qt.views.service_dialogs.dialogs.shared import (
    _confirm_close_with_running_worker,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.72.0: Image Extractor — extract all visuals from PDF/EPUB/DOCX
# ════════════════════════════════════════════════════════════════════════════

class ImageExtractorDialog(QDialog):
    """V11.72.0: Image Extractor — extract all images/charts/tables from books.

    Supports PDF (primary), EPUB, and DOCX.
    Extracts:
    - Embedded images (photos, graphics stored in the file)
    - Rendered page regions (vector graphics, charts, tables)
    - Full page renders (raw page as JPEG for reference)

    Organizes output by type:
      output_folder/
        photos/      — page_0005_img_003.jpg
        charts/      — page_0012_img_001.jpg
        tables/      — page_0008_img_002.jpg
        diagrams/    — page_0015_img_001.jpg
        figures/     — page_0020_img_001.jpg
        full_pages/  — page_0005.jpg (raw full page)

    Supports batch mode (multiple files) and page range selection.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("🖼️ Image Extractor")
        self.setMinimumSize(700, 600)
        self.setModal(True)
        self._worker = None
        self._files = []

        from PySide6.QtWidgets import (
            QCheckBox as _QChB,
        )
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
            QSpinBox as _QSB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("🖼️ Image Extractor")
        title.setObjectName("H2")
        lay.addWidget(title)

        desc = _QL("Extract all images, charts, tables, and diagrams from "
                   "PDF/EPUB/DOCX books. Output organized by type with "
                   "page numbers in filenames.")
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # ── Input files ───────────────────────────────────────────────
        input_group = _QGB("1. Input files (PDF / EPUB / DOCX):")
        input_lay = _VL(input_group)
        self.file_list = _QLW()
        self.file_list.setMinimumHeight(80)
        self.file_list.setMaximumHeight(120)
        file_btn_row = _HL()
        add_btn = _QPB("➕ Add Files…")
        add_btn.clicked.connect(self._add_files)
        rm_btn = _QPB("➖ Remove")
        rm_btn.clicked.connect(self._remove_file)
        file_btn_row.addWidget(add_btn)
        file_btn_row.addWidget(rm_btn)
        file_btn_row.addStretch()
        hint = _QL("Add multiple files for batch processing")
        hint.setObjectName("Caption")
        file_btn_row.addWidget(hint)
        input_lay.addWidget(self.file_list)
        input_lay.addLayout(file_btn_row)
        lay.addWidget(input_group)

        # ── Output folder ─────────────────────────────────────────────
        out_group = _QGB("2. Output folder:")
        out_lay = _VL(out_group)
        out_row = _HL()
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose where to save extracted images…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        out_lay.addLayout(out_row)
        lay.addWidget(out_group)

        # ── Options ───────────────────────────────────────────────────
        opt_group = _QGB("3. Options:")
        opt_lay = _VL(opt_group)

        # Page range
        range_row = _HL()
        range_row.addWidget(_QL("Page range:"))
        self.cb_all_pages = _QChB("All pages")
        self.cb_all_pages.setChecked(True)
        self.cb_all_pages.stateChanged.connect(self._on_range_changed)
        range_row.addWidget(self.cb_all_pages)
        range_row.addWidget(_QL("From:"))
        self.spin_from = _QSB()
        self.spin_from.setMinimum(1)
        self.spin_from.setMaximum(99999)
        self.spin_from.setEnabled(False)
        range_row.addWidget(self.spin_from)
        range_row.addWidget(_QL("To:"))
        self.spin_to = _QSB()
        self.spin_to.setMinimum(1)
        self.spin_to.setMaximum(99999)
        self.spin_to.setEnabled(False)
        range_row.addWidget(self.spin_to)
        range_row.addStretch()
        opt_lay.addLayout(range_row)

        # Checkboxes
        self.cb_full_pages = _QChB("Extract full page renders (raw page as JPEG)")
        self.cb_full_pages.setChecked(True)
        opt_lay.addWidget(self.cb_full_pages)

        self.cb_cropped = _QChB("Detect and crop image regions (vector graphics)")
        self.cb_cropped.setChecked(True)
        opt_lay.addWidget(self.cb_cropped)

        # DPI
        dpi_row = _HL()
        dpi_row.addWidget(_QL("Render DPI:"))
        self.spin_dpi = _QSB()
        self.spin_dpi.setMinimum(72)
        self.spin_dpi.setMaximum(600)
        self.spin_dpi.setValue(150)  # V11.74.0: 150 = faster, still good quality
        dpi_row.addWidget(self.spin_dpi)
        dpi_row.addWidget(_QL("(200 = good balance, 300 = high quality)"))
        dpi_lbl = dpi_row.itemAt(2).widget()
        dpi_lbl.setObjectName("Caption")
        dpi_row.addStretch()
        opt_lay.addLayout(dpi_row)

        lay.addWidget(opt_group)

        # ── Process button ────────────────────────────────────────────
        self.process_btn = _QPB("🖼️ Extract Images")
        self.process_btn.setObjectName("Primary")
        self.process_btn.clicked.connect(self._on_process)
        lay.addWidget(self.process_btn)

        # ── Progress ──────────────────────────────────────────────────
        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the image-
        # extraction SimpleWorker runs — the "QThread: Destroyed while
        # thread is still running" abort class. Ask; on "close anyway"
        # detach the worker so the batch's result is discarded, not
        # crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _add_files(self):
        from PySide6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select books to extract images from", "",
            "Books (*.pdf *.epub *.docx);;PDF (*.pdf);;EPUB (*.epub);;DOCX (*.docx);;All files (*.*)")
        if files:
            for f in files:
                self._files.append(f)
                self.file_list.addItem(f)

    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0 and row < len(self._files):
            self._files.pop(row)
            self.file_list.takeItem(row)

    def _pick_output(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Choose output folder for extracted images", "")
        if folder:
            self.out_edit.setText(folder)

    def _on_range_changed(self):
        all_pages = self.cb_all_pages.isChecked()
        self.spin_from.setEnabled(not all_pages)
        self.spin_to.setEnabled(not all_pages)

    def _on_process(self):
        if not self._files:
            QMessageBox.warning(self, "No files", "Please add at least one file.")
            return
        out_folder = self.out_edit.text().strip()
        if not out_folder:
            QMessageBox.warning(self, "No output", "Please choose an output folder.")
            return

        self.process_btn.setEnabled(False)
        self.process_btn.setText("⏳ Extracting...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("🖼️ Starting extraction...")

        page_range = None
        if not self.cb_all_pages.isChecked():
            page_range = (self.spin_from.value(), self.spin_to.value())

        options = {
            "files": list(self._files),
            "output_folder": out_folder,
            "page_range": page_range,
            "full_pages": self.cb_full_pages.isChecked(),
            "cropped": self.cb_cropped.isChecked(),
            "dpi": self.spin_dpi.value(),
        }

        def _work():
            return self._extract_all(options)

        from ui_qt.components.simple_worker import SimpleWorker
        self._worker = SimpleWorker(_work)
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _extract_all(self, options: dict) -> list:
        """Extract images from all files."""
        from core.extract.image_extractor import (
            extract_images_from_docx,
            extract_images_from_epub,
            extract_images_from_pdf,
        )

        results = []
        files = options["files"]
        output_base = options["output_folder"]
        page_range = options.get("page_range")
        full_pages = options.get("full_pages", True)
        cropped = options.get("cropped", True)
        dpi = options.get("dpi", 200)

        for i, filepath in enumerate(files):
            file_pct = int(i / len(files) * 100)
            self._emit_progress(file_pct, f"📂 File {i+1}/{len(files)}: {Path(filepath).name}")

            # Create subfolder per file
            file_stem = Path(filepath).stem
            file_output = str(Path(output_base) / file_stem)

            ext = Path(filepath).suffix.lower()
            try:
                if ext == ".pdf":
                    counts = extract_images_from_pdf(
                        filepath, file_output, page_range,
                        full_pages, cropped, dpi,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg: self._emit_progress(
                            int(file_pct + pct / len(files)), msg),
                    )
                elif ext == ".epub":
                    counts = extract_images_from_epub(
                        filepath, file_output,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg: self._emit_progress(
                            int(file_pct + pct / len(files)), msg),
                    )
                elif ext == ".docx":
                    counts = extract_images_from_docx(
                        filepath, file_output,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg: self._emit_progress(
                            int(file_pct + pct / len(files)), msg),
                    )
                else:
                    results.append(f"❌ {file_stem}: unsupported format ({ext})")
                    continue

                results.append(
                    f"✅ {file_stem}: {counts['total']} images "
                    f"(photos: {counts['photos']}, charts: {counts['charts']}, "
                    f"tables: {counts['tables']}, diagrams: {counts['diagrams']}, "
                    f"figures: {counts['figures']}, full_pages: {counts['full_pages']})")
            except Exception as e:
                results.append(f"❌ {file_stem}: {e}")

        return results

    def _emit_progress(self, pct: int, msg: str):
        """Emit progress to the worker signal."""
        worker = getattr(self, "_worker", None)
        if worker is not None:
            try:
                worker.progress.emit(pct, msg)
            except Exception:
                logger.debug("best-effort op failed", exc_info=True)

    def _on_progress(self, pct: int, msg: str):
        if pct >= 0:
            self.progress_bar.setValue(pct)
        self.status_label.setText(msg)

    def _on_failed(self, error_msg):
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("🖼️ Extract Images")
        self.status_label.setText(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "❌ Extraction Failed", error_msg)

    def _on_done(self, results):
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.process_btn.setText("🖼️ Extract Images")
        self.progress_bar.setValue(100)

        if isinstance(results, Exception):
            self.status_label.setText(f"❌ Error: {results}")
            return

        if results:
            summary = "\n".join(results)
            self.status_label.setText(f"✅ Done!\n{summary}")
            # Success modal
            out_folder = self.out_edit.text().strip()
            QMessageBox.information(
                self, "✅ Extraction Complete",
                f"Image extraction complete!\n\n{summary}\n\n"
                f"Output: {out_folder}")
        else:
            self.status_label.setText("⚠️ No images extracted")
