"""ModelDownloadDialog (V0.6.60) -- "Get Whisper models".

The V0.6.59 follow-up: when the GGUF is NOT on disk yet, the only fix
offered was a manual browser trip to Hugging Face + a folder pick. This
dialog closes the loop inside the app:

  - the curated handy-computer catalog (core/transcribe/
    model_downloader.py -- every entry live-verified against the HF
    API), one row per file: family · quant · exact size, the turbo
    Q5_K_M badged as RECOMMENDED (the V0.6.58 speed ledger's pick)
  - a details panel + per-row tooltips: repo, filename, params, the
    plain-language note (what the quant means for speed/accuracy)
  - destination shown up-front (default_download_dir: where the
    V0.6.59 scan looks FIRST) + an 📂 Open folder affordance
  - progress bar + live 'done / total · % · MB/s · ETA' line, resumable
    cancel (the .part survives; re-clicking Download continues it)
  - the finished file is VERIFIED from its own GGUF header (the
    V0.6.59 catalog gate) before install; on_installed(path) then
    hands it to the parent dialog, which saves the setting + selects
    it in the GGUF combo (download → selected, one flow)

Network NEVER touches the UI thread: probe/download/verify run on a
SimpleWorker (the house _llm_test_worker precedent); the worker's
progress signal drives the bar.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ui_qt.components.simple_worker import SimpleWorker

logger = logging.getLogger(__name__)


class ModelDownloadDialog(QDialog):
    """Download a Whisper GGUF from handy-computer's Hugging Face
    repos, verified + auto-selected on arrival."""

    def __init__(self, parent=None, on_installed=None):
        super().__init__(parent)
        self.setWindowTitle("⬇ Get Whisper models")
        self.setMinimumWidth(680)
        self._on_installed = on_installed
        self._cancel_flag = False
        self._worker = None

        from core.transcribe import model_downloader as md

        # Where the file lands: where the V0.6.59 scan looks first
        # (C:\transcribe.cpp\models on the rig). Best-effort: the
        # engine exe setting may be unset on a fresh install.
        exe = None
        try:
            from utils.settings import Settings

            _exe = Settings().get("transcribe.transcribe_cpp_exe", None)
            exe = str(_exe) if _exe else None
        except Exception:
            exe = None
        self._dest = Path(md.default_download_dir(exe_path=exe))

        root = QVBoxLayout(self)

        caption = QLabel(
            "Download a Whisper GGUF model from handy-computer's Hugging Face "
            "repos — the same source the 'GGUF model' dropdown reads from. "
            "The finished file is verified from its own GGUF header and "
            "selected automatically."
        )
        caption.setObjectName("Caption")
        caption.setWordWrap(True)
        root.addWidget(caption)

        # ── Destination row: shown up-front, one click to open ──────
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Save to:"))
        self.dest_label = QLabel(str(self._dest))
        self.dest_label.setObjectName("Caption")
        self.dest_label.setWordWrap(True)
        self.dest_label.setToolTip(
            "The folder lands in the app's model scan path, so the GGUF\n"
            "dropdown finds it the moment the download finishes."
        )
        dest_row.addWidget(self.dest_label, 1)
        self.open_folder_btn = QPushButton("📂 Open folder")
        self.open_folder_btn.setObjectName("Compact")
        self.open_folder_btn.setToolTip("Open the destination folder in the file explorer")
        self.open_folder_btn.clicked.connect(self._open_folder)
        dest_row.addWidget(self.open_folder_btn)
        root.addLayout(dest_row)

        # ── The catalog list ────────────────────────────────────────
        self.list_widget = QListWidget()
        self.list_widget.setToolTip(
            "Every downloadable handy-computer Whisper GGUF.\n"
            "Hover a row for its details; the ★ entry is the recommended pick."
        )
        for spec in md.DOWNLOAD_CATALOG:
            item = QListWidgetItem(spec.display())
            item.setData(Qt.ItemDataRole.UserRole, spec.key)
            item.setToolTip(spec.details())
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        root.addWidget(self.list_widget, 1)

        # ── The details panel (selection-driven) ────────────────────
        self.details_label = QLabel("")
        self.details_label.setObjectName("Caption")
        self.details_label.setWordWrap(True)
        root.addWidget(self.details_label)
        self._on_selection_changed(self.list_widget.currentRow())

        # ── Progress (bar + live speed/ETA line) ─────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)
        self.progress_line = QLabel("")
        self.progress_line.setObjectName("Caption")
        root.addWidget(self.progress_line)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.download_btn = QPushButton("⬇ Download")
        self.download_btn.setObjectName("Primary")
        self.download_btn.setToolTip(
            "Download (or resume) the selected model into the destination folder"
        )
        self.download_btn.clicked.connect(self._on_download_clicked)
        btn_row.addWidget(self.download_btn)
        self.cancel_btn = QPushButton("✖ Cancel")
        self.cancel_btn.setObjectName("Compact")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip(
            "Cancel the download — the partial file is kept, so clicking "
            "Download again resumes where it stopped"
        )
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self.cancel_btn)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("Compact")
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    # ── selection + folder ──────────────────────────────────────────

    def _selected_spec(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return None
        key = self.list_widget.item(row).data(Qt.ItemDataRole.UserRole)
        from core.transcribe import model_downloader as md

        return md.catalog_by_key(str(key) if key else "")

    def _on_selection_changed(self, row: int) -> None:
        spec = self._selected_spec()
        if spec is not None:
            self.details_label.setText(spec.details())

    def _open_folder(self) -> None:
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dest)))
        except Exception:
            logger.debug("best-effort open folder failed", exc_info=True)

    # ── the download flow (worker thread; never the UI thread) ─────

    def _on_download_clicked(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        target = self._dest / spec.filename
        if target.exists():
            # three ways out: use the file that is already there,
            # re-download it, or back off entirely.
            box = QMessageBox(self)
            box.setWindowTitle("Model already on disk")
            box.setText(
                f"{spec.filename} is already in the destination folder:\n"
                f"{target}\n\nUse it, or re-download it?"
            )
            use_btn = box.addButton("Use the existing file", QMessageBox.ButtonRole.AcceptRole)
            redl_btn = box.addButton("Re-download", QMessageBox.ButtonRole.ResetRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked is use_btn:
                self._install_existing(target, spec)
                return
            if clicked is not redl_btn:
                return  # cancelled
        self._cancel_flag = False
        self.download_btn.setEnabled(False)
        self.list_widget.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_line.setText("")
        self.status_label.setText(f"⬇ Downloading {spec.filename} …")

        # SimpleWorker takes the callable; self._worker is assigned
        # BEFORE start() below, so the closure's read of it on the
        # worker thread is safe (no signal round-trip before start).
        worker = SimpleWorker(self._download_work, spec)
        self._worker = worker
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_download_done)
        worker.failed.connect(self._on_download_failed)
        worker.start()

    def _download_work(self, spec):
        """Runs ON the worker thread: probe → download → verify. All
        UI feedback flows through the worker's signals; nothing here
        touches a widget."""
        from core.transcribe import model_downloader as md

        pr = md.probe(spec.url())
        if not pr["ok"]:
            return {"spec": spec.key, "phase": "probe", "ok": False, "error": pr["error"]}
        res = md.download(
            spec.url(),
            self._dest,
            filename=spec.filename,
            on_progress=lambda p: self._worker.progress.emit(
                int(p["pct"] or 0), md.format_progress_line(p)
            ),
            should_cancel=lambda: self._cancel_flag,
            # V0.6.61: the PUBLISHED sha256 — the downloaded stream is
            # hashed incrementally and a mismatch deletes the wrong
            # bytes (a corrupted file can never be installed).
            expected_sha256=getattr(spec, "sha256", None),
        )
        if not res["ok"]:
            return {"spec": spec.key, "phase": "download", **res}
        ver = md.verify_download(res["path"], spec=spec)
        return {"spec": spec.key, "phase": "done", **res, "verify": ver}

    def _restore_controls(self) -> None:
        self.download_btn.setEnabled(True)
        self.list_widget.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_worker_progress(self, pct: int, msg: str) -> None:
        self.progress_bar.setValue(int(pct))
        self.progress_line.setText(str(msg))

    def _on_cancel_clicked(self) -> None:
        self._cancel_flag = True
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("⏳ Cancelling — the partial file is kept for resume…")

    def _install_existing(self, target: Path, spec) -> None:
        """V0.6.60 review fix: 'Use the existing file' -- verify the
        file already on disk through the same GGUF-header gate, then
        hand it to on_installed (save + select)."""
        from core.transcribe import model_downloader as md

        ver = md.verify_download(target, spec=spec)
        if not ver.get("ok"):
            QMessageBox.warning(
                self,
                "⚠️ Existing file did not verify",
                (
                    f"{target.name} did not pass the Whisper GGUF check:\n\n"
                    f"{ver.get('problem')}\n\n"
                    "Re-download it instead?"
                ),
            )
            return
        try:
            if self._on_installed is not None:
                self._on_installed(str(target))
        except Exception:
            logger.debug("best-effort on_installed callback failed", exc_info=True)
        self.status_label.setText("✅ Existing model verified — selected")
        self.accept()

    def _on_download_done(self, result: dict) -> None:
        self._restore_controls()
        if not isinstance(result, dict):
            self.status_label.setText("⬇ Unexpected downloader result")
            return
        if result.get("phase") == "probe":
            self.progress_bar.setVisible(False)
            self.progress_line.setText("")
            self.status_label.setText(f"❌ Could not reach Hugging Face: {result.get('error')}")
            QMessageBox.critical(
                self,
                "❌ Download failed",
                (
                    f"Could not reach Hugging Face for this model:\n\n"
                    f"{result.get('error')}\n\n"
                    "Check the internet connection and try again."
                ),
            )
            return
        if result.get("cancelled"):
            self.progress_bar.setVisible(False)
            self.progress_line.setText("")
            self.status_label.setText("⬇ Cancelled — partial file kept; Download resumes it")
            return
        if not result.get("ok"):
            self.progress_bar.setVisible(False)
            self.progress_line.setText("")
            self.status_label.setText(f"❌ {result.get('error')}")
            QMessageBox.critical(self, "❌ Download failed", str(result.get("error") or "?"))
            return
        path = str(result.get("path") or "")
        ver = result.get("verify") or {}
        info = (ver.get("info") or {}) if isinstance(ver, dict) else {}
        if not ver.get("ok"):
            self.progress_bar.setVisible(False)
            self.progress_line.setText("")
            self.status_label.setText("⚠️ Downloaded, but the file did not verify as Whisper")
            QMessageBox.warning(
                self,
                "⚠️ Verification failed",
                (
                    f"The downloaded file did not pass the Whisper GGUF check:\n\n"
                    f"{ver.get('problem')}\n\n"
                    "The file was left on disk; delete it and try again."
                ),
            )
            return
        # verified: hand it to the parent (save setting + select in combo)
        try:
            if self._on_installed is not None:
                self._on_installed(path)
        except Exception:
            logger.debug("best-effort on_installed callback failed", exc_info=True)
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Downloaded + verified — selected in the GGUF dropdown")
        size_note = ""
        if ver.get("size_ok") is False:
            size_note = (
                "\n\nNote: the file's size differs from the catalog hint "
                "(the source may have been republished) — the GGUF header "
                "verified it is a Whisper model."
            )
        # V0.6.61: the sha256 verdict is part of the running record —
        # byte-identical to what Hugging Face published, or honestly
        # not checked (an old .part resumed before hashes existed).
        sha_note = "\nsha256: verified — byte-identical to the published file."
        if result.get("sha256_ok") is None:
            sha_note = "\nsha256: not checked (no published hash available)."
        QMessageBox.information(
            self,
            "✅ Model ready",
            (
                f"{Path(path).name} downloaded and verified from its own "
                f"GGUF header (architecture: "
                f"{info.get('architecture') or 'whisper'}).{sha_note}{size_note}\n\n"
                "It is selected in the 'GGUF model' dropdown."
            ),
        )
        self.accept()

    def _on_download_failed(self, error_msg) -> None:
        self._restore_controls()
        self.progress_bar.setVisible(False)
        self.progress_line.setText("")
        self.status_label.setText(f"❌ {error_msg}")
        QMessageBox.warning(self, "⚠️ Downloader error", str(error_msg))

    def reject(self) -> None:
        """V0.6.60 review fix: Close + Esc go through HERE (only the
        window X reached closeEvent) -- a download in flight is
        CANCELLED, not left running invisibly (a finishing message box
        would otherwise pop over the parent after the dialog is gone).
        The .part survives, so reopening + Download resumes."""
        if self._worker is not None and self._worker.is_running():
            self._cancel_flag = True
        super().reject()

    def closeEvent(self, event) -> None:
        """The window X: same policy as reject()."""
        if self._worker is not None and self._worker.is_running():
            self._cancel_flag = True
        super().closeEvent(event)
