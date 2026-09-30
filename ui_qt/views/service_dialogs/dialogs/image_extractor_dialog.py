"""Image Extractor dialog (V18.20.4.6, P5 / O-b2 split).

ImageExtractorDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ delegates the common
skeleton (title, options container, output row, progress, status,
buttons) to the base and folds its byte-identical closeEvent guard +
_emit_progress helper away (inherited). The multi-file batch list is
the dialog's input UI, so ``accept_files=False, accept_text=False``
(the base builds no standard input row); the file-queue and option
rows fold into _build_options. The out_edit legacy name aliases the
base-built out_path_edit (a FOLDER — the _pick_output override keeps
the directory picker); the determinate 0-100 progress bar and the
"🖼️ Extract Images" button label are restored over the base defaults.
The W-b5 worker launch keeps its pinned shape: _on_process spawns the
SimpleWorker (the base's _process/_collect_options flow does not fit
the multi-file batch contract)."""

from __future__ import annotations

import logging
from pathlib import Path

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# V11.72.0: Image Extractor — extract all visuals from PDF/EPUB/DOCX
# ════════════════════════════════════════════════════════════════════════════


class ImageExtractorDialog(BaseServiceDialog):
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
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options (the file-queue + option rows),
        # which needs nothing pre-set; _files is the batch list _add_files
        # appends to. The base also initializes self._worker (its
        # closeEvent guards it).
        self._files: list = []
        super().__init__(
            controller, "🖼️ Image Extractor", parent, accept_files=False, accept_text=False
        )
        # V0.6.10 (B17): this dialog's original geometry over the base's
        # generic 560×480, plus its determinate 0-100 progress bar (the
        # base's is indeterminate).
        self.setMinimumSize(700, 600)
        self.progress_bar.setRange(0, 100)
        # V0.6.10 (B17): the base builds out_path_edit / process_btn with
        # its own labels; this dialog's historical attribute name
        # (out_edit — pinned by the e2e drive tests) and labels are
        # restored as aliases of the SAME widgets (single source of
        # truth).
        self.out_edit = self.out_path_edit
        self.out_edit.setPlaceholderText("Choose where to save extracted images…")
        self.process_btn.setText("🖼️ Extract Images")
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (its _on_progress override only
        # sets status text) — hide the dead toggle (the transcribe B17
        # precedent).
        self._log_toggle_btn.setVisible(False)

    def _build_options(self, layout: QVBoxLayout) -> None:
        """V0.6.10 (B17): the extractor's custom blocks — the multi-file
        batch list (the dialog's input UI; the reason accept_files=False,
        accept_text=False) and the page-range/full-pages/cropped/DPI
        options — folded into the base's options container. The old
        numbered group titles lost their "2. Output folder" sibling to
        the base's output row, so the numbering is gone too."""
        # ── Input files ───────────────────────────────────────────────
        input_group = QGroupBox("Input files (PDF / EPUB / DOCX):")
        input_lay = QVBoxLayout(input_group)
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(80)
        self.file_list.setMaximumHeight(120)
        file_btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Files…")
        add_btn.clicked.connect(self._add_files)
        rm_btn = QPushButton("➖ Remove")
        rm_btn.clicked.connect(self._remove_file)
        file_btn_row.addWidget(add_btn)
        file_btn_row.addWidget(rm_btn)
        file_btn_row.addStretch()
        hint = QLabel("Add multiple files for batch processing")
        hint.setObjectName("Caption")
        file_btn_row.addWidget(hint)
        input_lay.addWidget(self.file_list)
        input_lay.addLayout(file_btn_row)
        layout.addWidget(input_group)

        # ── Options ───────────────────────────────────────────────────
        opt_group = QGroupBox("Options:")
        opt_lay = QVBoxLayout(opt_group)

        # Page range
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Page range:"))
        self.cb_all_pages = QCheckBox("All pages")
        self.cb_all_pages.setChecked(True)
        self.cb_all_pages.stateChanged.connect(self._on_range_changed)
        range_row.addWidget(self.cb_all_pages)
        range_row.addWidget(QLabel("From:"))
        self.spin_from = QSpinBox()
        self.spin_from.setMinimum(1)
        self.spin_from.setMaximum(99999)
        self.spin_from.setEnabled(False)
        range_row.addWidget(self.spin_from)
        range_row.addWidget(QLabel("To:"))
        self.spin_to = QSpinBox()
        self.spin_to.setMinimum(1)
        self.spin_to.setMaximum(99999)
        self.spin_to.setEnabled(False)
        range_row.addWidget(self.spin_to)
        range_row.addStretch()
        opt_lay.addLayout(range_row)

        # Checkboxes
        self.cb_full_pages = QCheckBox("Extract full page renders (raw page as JPEG)")
        self.cb_full_pages.setChecked(True)
        opt_lay.addWidget(self.cb_full_pages)

        self.cb_cropped = QCheckBox("Detect and crop image regions (vector graphics)")
        self.cb_cropped.setChecked(True)
        opt_lay.addWidget(self.cb_cropped)

        # DPI
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Render DPI:"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setMinimum(72)
        self.spin_dpi.setMaximum(600)
        self.spin_dpi.setValue(150)  # V11.74.0: 150 = faster, still good quality
        dpi_row.addWidget(self.spin_dpi)
        dpi_row.addWidget(QLabel("(200 = good balance, 300 = high quality)"))
        dpi_lbl = dpi_row.itemAt(2).widget()
        dpi_lbl.setObjectName("Caption")
        dpi_row.addStretch()
        opt_lay.addLayout(dpi_row)

        layout.addWidget(opt_group)

    # V0.6.10 (B17): the closeEvent guard (identical to the base's —
    # _confirm_close_with_running_worker(self, self._worker)) and the
    # _emit_progress worker helper (byte-equivalent modulo docstring) are
    # now INHERITED from BaseServiceDialog; the pre-B17 copies were
    # deleted.

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select books to extract images from",
            "",
            "Books (*.pdf *.epub *.docx);;PDF (*.pdf);;EPUB (*.epub);;DOCX (*.docx);;All files (*.*)",
        )
        if files:
            for f in files:
                self._files.append(f)
                self.file_list.addItem(f)

    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0 and row < len(self._files):
            self._files.pop(row)
            self.file_list.takeItem(row)

    def _pick_output(self) -> None:
        # V0.6.10 (B17): override of the base's output-row Browse hook —
        # a DIRECTORY picker (the extractor writes a per-book folder
        # tree, not one file; the base's getSaveFileName + suffix append
        # never applied here). Body unchanged.
        folder = QFileDialog.getExistingDirectory(
            self, "Choose output folder for extracted images", ""
        )
        if folder:
            self.out_edit.setText(folder)

    def _get_service_name(self) -> str:
        # V0.6.10 (B17): base-class identity hook. This dialog persists no
        # controller settings (grep: zero controller.update_setting /
        # controller.get_setting calls), so the name is identity-only.
        # (_get_output_suffix is deliberately NOT implemented: the output
        # is a folder tree, not a suffixed file.)
        return "image_extractor"

    def _on_range_changed(self):
        all_pages = self.cb_all_pages.isChecked()
        self.spin_from.setEnabled(not all_pages)
        self.spin_to.setEnabled(not all_pages)

    def _on_process(self):
        # V0.6.10 (B17): kept override — the base's _on_process validates a
        # generic text/file input and spawns SimpleWorker(self._process, …);
        # this dialog's contract is the multi-file batch queue, the output
        # FOLDER, the inverted-range guard and its own completion pair
        # (no base-equivalent flow). Body unchanged.
        if not self._files:
            QMessageBox.warning(self, "No files", "Please add at least one file.")
            return
        out_folder = self.out_edit.text().strip()
        if not out_folder:
            QMessageBox.warning(self, "No output", "Please choose an output folder.")
            return

        # V0.6.0 (4-a/D2): an inverted page range (From > To — the two
        # spin boxes are independent) used to fall through to the service,
        # which processes an EMPTY page range and reports "✅ 0 images".
        # Refuse the impossible range up front (no worker spawned).
        page_range = None
        if not self.cb_all_pages.isChecked():
            range_from = self.spin_from.value()
            range_to = self.spin_to.value()
            if range_from > range_to:
                QMessageBox.warning(
                    self,
                    "Invalid page range",
                    "The 'From' page must not be greater than the 'To' page.",
                )
                return
            page_range = (range_from, range_to)

        self.process_btn.setEnabled(False)
        self.process_btn.setText("⏳ Extracting...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("🖼️ Starting extraction...")

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
            self._emit_progress(file_pct, f"📂 File {i + 1}/{len(files)}: {Path(filepath).name}")

            # Create subfolder per file
            file_stem = Path(filepath).stem
            file_output = str(Path(output_base) / file_stem)

            ext = Path(filepath).suffix.lower()
            try:
                if ext == ".pdf":
                    counts = extract_images_from_pdf(
                        filepath,
                        file_output,
                        page_range,
                        full_pages,
                        cropped,
                        dpi,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg, _base=file_pct: self._emit_progress(
                            int(_base + pct / len(files)), msg
                        ),
                    )
                elif ext == ".epub":
                    counts = extract_images_from_epub(
                        filepath,
                        file_output,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg, _base=file_pct: self._emit_progress(
                            int(_base + pct / len(files)), msg
                        ),
                    )
                elif ext == ".docx":
                    counts = extract_images_from_docx(
                        filepath,
                        file_output,
                        log_callback=lambda msg, level="INFO": self._emit_progress(-1, msg),
                        progress_callback=lambda pct, msg, _base=file_pct: self._emit_progress(
                            int(_base + pct / len(files)), msg
                        ),
                    )
                else:
                    results.append(f"❌ {file_stem}: unsupported format ({ext})")
                    continue

                # V0.6.0 (4-a/D1): a file the service could not open at all
                # must land as a ❌ line, not as "✅ 0 images".
                if counts.get("error"):
                    results.append(f"❌ {file_stem}: {counts['error']}")
                    continue

                results.append(
                    f"✅ {file_stem}: {counts['total']} images "
                    f"(photos: {counts['photos']}, charts: {counts['charts']}, "
                    f"tables: {counts['tables']}, diagrams: {counts['diagrams']}, "
                    f"figures: {counts['figures']}, full_pages: {counts['full_pages']})"
                )
            except Exception as e:
                results.append(f"❌ {file_stem}: {e}")

        return results

    def _on_progress(self, pct: int, msg: str):
        # V0.6.10 (B17): kept override — the base's _on_progress wraps the
        # status text in HTML + appends to the live log; this dialog's
        # contract (pinned by the e2e drive tests) is plain-text status
        # and a determinate 0-100 bar. Body unchanged.
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
            # V0.6.0 (4-a/D1): the status prefix + modal must reflect
            # per-file failures — "✅ Done!" for an all-failed batch was a
            # failure disguised as success.
            failures = sum(1 for r in results if r.startswith("❌"))
            out_folder = self.out_edit.text().strip()
            if failures and failures == len(results):
                self.status_label.setText(f"❌ Extraction failed\n{summary}")
                QMessageBox.critical(self, "❌ Extraction Failed", summary)
            else:
                prefix = "⚠️" if failures else "✅"
                self.status_label.setText(f"{prefix} Done!\n{summary}")
                # Success modal
                QMessageBox.information(
                    self,
                    "✅ Extraction Complete",
                    f"Image extraction complete!\n\n{summary}\n\nOutput: {out_folder}",
                )
        else:
            self.status_label.setText("⚠️ No images extracted")
