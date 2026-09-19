"""Quick Convert dialog (V18.20.4.6, P5 / O-b2 split).

QuickConvertDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import re

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    _confirm_close_with_running_worker,
    _show_success_modal,
)


class QuickConvertDialog(QDialog):
    """V15.0.0: Document → Markdown — pick a document, pick engine, Convert.

    Renamed from "PDF → Markdown" in V15.0.0. Now accepts ALL AnyDoc-
    supported formats (PDF, DOCX, DOC, EPUB, PPTX, XLSX, ODT, RTF, CSV, …)
    and offers two engines:

      * AnyDoc (default) — fast, proper headings/tables/formatting.
      * markitdown (fallback) — slower but handles a broader/different
        format set (HTML, JSON, images, audio, …).

    CRITICAL: AnyDoc is ONLY available in this tool. The main conversion
    pipeline still uses markitdown + OlmOCR exactly as V13.45.5.

    V18.20.4.5 (W-b5): the extraction + output write run on a SimpleWorker
    background thread. The old inline path froze the UI thread for the
    whole extraction and used a ``QApplication.processEvents()`` repaint
    hack (the docstring used to admit it); anydoc's per-step log lines now
    arrive through the worker's queued progress signal instead of a
    status-label-writing callback on the UI thread.
    """

    # AnyDoc engine, keyed by lowercase extension.
    _ANYDOC_EXTS = {
        ".pdf",
        ".docx",
        ".doc",
        ".epub",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
        ".odt",
        ".ods",
        ".odp",
        ".rtf",
        ".csv",
        ".pptm",
        ".ppsx",
        ".ppsm",
        ".docm",
        ".xlsm",
        ".xlsb",
        ".pps",
        ".pot",
    }
    _MARKITDOWN_EXTS = {
        ".pdf",
        ".docx",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".xml",
        ".epub",
        ".ipynb",
        ".jpg",
        ".jpeg",
        ".png",
        ".mp3",
        ".wav",
        ".txt",
        ".md",
    }

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("📄 Document → Markdown")
        self.setMinimumSize(560, 300)
        self.setModal(True)
        # V18.20.4.5 (W-b5/T-b2): the background extraction worker
        # (SimpleWorker).
        self._worker: SimpleWorker | None = None

        from PySide6.QtWidgets import (
            QComboBox as _QCB,
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
            QPushButton as _QPB,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _VL,
        )

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("Document → Markdown (Quick)")
        title.setObjectName("H2")
        lay.addWidget(title)

        hint = _QL(
            "Supports PDF, DOCX, DOC, EPUB, PPTX, XLSX, ODT, RTF, CSV … "
            "Choose engine and output format below."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # Input file picker
        in_row = _HL()
        in_row.setSpacing(8)
        in_row.addWidget(_QL("Document:"))
        self.pdf_edit = _QLE()  # keep attr name for back-compat with _refresh_output_path
        self.pdf_edit.setPlaceholderText("Pick a document file…")
        pdf_browse = _QPB("Browse…")
        pdf_browse.clicked.connect(self._pick_input)
        in_row.addWidget(self.pdf_edit, 1)
        in_row.addWidget(pdf_browse)
        lay.addLayout(in_row)

        # V15.0.0: Engine dropdown
        eng_row = _HL()
        eng_row.setSpacing(8)
        eng_row.addWidget(_QL("Engine:"))
        self.engine_combo = _QCB()
        self.engine_combo.addItem("AnyDoc (default)", "anydoc")
        self.engine_combo.addItem("markitdown (fallback)", "markitdown")
        # If AnyDoc isn't installed, default to markitdown and note it.
        try:
            from core.extract.anydoc_extractor import is_anydoc_available

            if not is_anydoc_available():
                self.engine_combo.setItemText(0, "AnyDoc (not installed)")
                self.engine_combo.setCurrentIndex(1)
        except Exception:
            self.engine_combo.setCurrentIndex(1)
        self.engine_combo.currentIndexChanged.connect(self._on_engine_or_format_changed)
        eng_row.addWidget(self.engine_combo)
        eng_row.addStretch()
        lay.addLayout(eng_row)

        # Output format
        fmt_row = _HL()
        fmt_row.setSpacing(8)
        fmt_row.addWidget(_QL("Format:"))
        self.fmt_combo = _QCB()
        self.fmt_combo.addItem("Default (change in Settings)", "__default__")
        self.fmt_combo.addItem("Markdown (.md)", ".md")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.setCurrentIndex(0)
        self.fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        lay.addLayout(fmt_row)

        # Output file picker
        out_row = _HL()
        out_row.setSpacing(8)
        out_row.addWidget(_QL("Save as:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose where to save the file…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        lay.addLayout(out_row)

        # Status
        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        # Buttons
        btn_row = _HL()
        btn_row.addStretch()
        self.again_btn = _QPB("🔄 Try Another File")
        self.again_btn.setObjectName("Compact")
        self.again_btn.setVisible(False)
        self.again_btn.clicked.connect(self._on_try_another)
        self.action_btn = _QPB("Convert")
        self.action_btn.setObjectName("Primary")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.again_btn)
        btn_row.addWidget(self.action_btn)
        lay.addLayout(btn_row)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the extraction
        # worker runs — the "QThread: Destroyed while thread is still
        # running" abort class. Ask; on "close anyway" detach the worker
        # so the extraction result is discarded, not crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    # ── File picking ────────────────────────────────────────────────────
    def _pick_input(self):
        # Accept AnyDoc + markitdown formats in one filter.
        filt = (
            "Documents (*.pdf *.docx *.doc *.epub *.pptx *.ppt *.xlsx *.xls "
            "*.odt *.ods *.odp *.rtf *.csv *.pptm *.ppsx *.ppsm *.docm "
            "*.xlsm *.xlsb *.pps *.pot *.html *.htm *.json *.xml *.ipynb "
            "*.txt *.md *.jpg *.jpeg *.png *.mp3 *.wav);;"
            "PDF (*.pdf);;"
            "Word (*.docx *.doc);;"
            "PowerPoint (*.pptx *.ppt);;"
            "Excel (*.xlsx *.xls);;"
            "OpenDocument (*.odt *.ods *.odp);;"
            "eBook (*.epub);;"
            "Rich Text (*.rtf);;"
            "CSV (*.csv);;"
            "HTML (*.html *.htm);;"
            "Text (*.txt *.md);;"
            "All files (*.*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Pick a document", "", filt)
        if path:
            self.pdf_edit.setText(path)
            self._refresh_output_path()
            self._validate_engine_format(silent=False)

    def _on_engine_or_format_changed(self):
        self._validate_engine_format(silent=False)

    # ── Output path / format helpers (unchanged behavior) ───────────────
    def _on_format_changed(self):
        self._refresh_output_path()

    def _resolve_ext(self) -> str:
        ext = self.fmt_combo.currentData()
        if ext == "__default__" or not ext:
            from utils.settings import Settings

            ext = Settings().get("quick_services.defaults.pdf_format", ".md") or ".md"
        return ext

    def _refresh_output_path(self):
        pdf_path = self.pdf_edit.text().strip()
        if not pdf_path:
            return
        from pathlib import Path as _P

        p = _P(pdf_path)
        ext = self._resolve_ext()
        self.out_edit.setText(str(p.parent / f"{p.stem}{ext}"))

    def _pick_output(self):
        ext = self._resolve_ext()
        default_name = self.out_edit.text().strip()
        if not default_name:
            pdf_path = self.pdf_edit.text().strip()
            if pdf_path:
                from pathlib import Path as _P

                default_name = str(_P(pdf_path).parent / f"{_P(pdf_path).stem}{ext}")
        filter_str = {
            ".md": "Markdown (*.md)",
            ".docx": "Word document (*.docx)",
            ".pdf": "PDF (*.pdf)",
        }.get(ext, "All files (*.*)")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save as", default_name, f"{filter_str};;All files (*.*)"
        )
        if path:
            if not path.endswith(ext):
                path += ext
            self.out_edit.setText(path)

    # ── V15.0.0: engine/format validation ───────────────────────────────
    def _selected_engine(self) -> str:
        data = self.engine_combo.currentData()
        return data if data else "anydoc"

    def _validate_engine_format(self, silent: bool = False) -> bool:
        """Return True if the current file extension is compatible with the
        selected engine.  Shows a status-label hint (and, when ``silent``
        is False, sets the Convert button enabled state) accordingly.
        """
        pdf_path = self.pdf_edit.text().strip()
        engine = self._selected_engine()
        # No file chosen yet — nothing to validate.
        if not pdf_path:
            self.action_btn.setEnabled(True)
            return True
        from pathlib import Path as _P

        ext = _P(pdf_path).suffix.lower()
        if engine == "anydoc":
            ok = ext in self._ANYDOC_EXTS
            if not ok:
                self.status_label.setText(
                    f"⚠️ AnyDoc does not support {ext or 'this'} files. "
                    f"Switch to the markitdown engine."
                )
                if not silent:
                    self.action_btn.setEnabled(False)
                return False
            else:
                if not silent:
                    self.status_label.setText(f"Engine: AnyDoc — {ext} supported. Click Convert.")
                    self.action_btn.setEnabled(True)
                return True
        else:  # markitdown
            ok = ext in self._MARKITDOWN_EXTS
            if not ok:
                self.status_label.setText(
                    f"⚠️ markitdown does not support {ext or 'this'} files. "
                    f"Switch to the AnyDoc engine."
                )
                if not silent:
                    self.action_btn.setEnabled(False)
                return False
            else:
                if not silent:
                    self.status_label.setText(
                        f"Engine: markitdown — {ext} supported. Click Convert."
                    )
                    self.action_btn.setEnabled(True)
                return True

    # ── Action handlers ─────────────────────────────────────────────────
    def _on_action(self):
        if self.action_btn.text() == "Close":
            self.accept()
            return
        self._do_convert()

    def _on_try_another(self):
        self.pdf_edit.clear()
        self.out_edit.clear()
        self.status_label.setText("Ready for the next document — pick a file and click Convert.")
        self.again_btn.setVisible(False)
        self.action_btn.setText("Convert")
        self.action_btn.setEnabled(True)

    def _do_convert(self):
        # V18.20.4.5 (W-b5): re-entrancy guard — a second click while a
        # document converts would spawn a second worker on the same paths.
        if self._worker is not None and self._worker.is_running():
            self.status_label.setText(
                "⏳ Already converting — wait for the current document to finish."
            )
            return

        pdf_path = self.pdf_edit.text().strip()
        out_path = self.out_edit.text().strip()
        if not pdf_path:
            self.status_label.setText("⚠️ Please pick a document file first.")
            return
        if not out_path:
            self.status_label.setText("⚠️ Please choose where to save the file.")
            return

        # V15.0.0: format validation (hard block before converting)
        from pathlib import Path as _P

        ext = _P(pdf_path).suffix.lower()
        engine = self._selected_engine()
        if engine == "anydoc" and ext not in self._ANYDOC_EXTS:
            self.status_label.setText(
                f"❌ AnyDoc does not support {ext} files. Use markitdown instead."
            )
            return
        if engine == "markitdown" and ext not in self._MARKITDOWN_EXTS:
            self.status_label.setText(
                f"❌ markitdown does not support {ext} files. Use AnyDoc instead."
            )
            return

        out_ext = self._resolve_ext()

        # Show "Processing…" — V18.20.4.5 (W-b5): the old code called
        # QApplication.processEvents() here to force a repaint before the
        # blocking call (the UI thread then froze for the whole
        # extraction). The blocking work now runs on a SimpleWorker; the
        # event loop repaints this label naturally while it runs.
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Processing…")
        self.status_label.setText(f"Extracting with {engine} …")

        # The lambda referencing self._worker is safe: Python closures
        # late-bind, so at call time (worker thread) the attribute exists
        # and refers to THIS worker.
        self._worker = SimpleWorker(
            lambda: self._convert_work(
                pdf_path, out_path, engine, ext, out_ext, report=self._worker.progress.emit
            )
        )
        self._worker.progress.connect(self._on_convert_progress)
        self._worker.finished.connect(self._on_convert_finished)
        self._worker.failed.connect(self._on_convert_failed)
        self._worker.start()

    def _convert_work(
        self, pdf_path: str, out_path: str, engine: str, ext: str, out_ext: str, report=None
    ) -> dict:
        """V18.20.4.5 (W-b5): the extraction + output write, worker-thread
        edition.

        Pure file/extraction work — NO widget access. anydoc's per-step
        log lines go through ``report(0, msg)`` (the worker's queued
        progress signal → main thread) instead of the old ``_cb`` that
        wrote the status label + QApplication.processEvents() on the UI
        thread. Returns a plain dict consumed by ``_on_convert_finished``.
        """
        from pathlib import Path as _P

        text = ""
        page_count = 0
        error_msg = None
        try:
            if engine == "anydoc":
                from core.extract.anydoc_extractor import (
                    extract_with_anydoc,
                    is_anydoc_available,
                )

                if not is_anydoc_available():
                    error_msg = (
                        "AnyDoc is not installed. Run: pip install anydoc  "
                        "(or switch to the markitdown engine)."
                    )
                else:
                    # V18.20.4.5 (W-b5): wrap report (int, str) down to
                    # anydoc's (str) log_callback shape.
                    log_cb = (lambda msg: report(0, msg)) if report is not None else None
                    text, page_count = extract_with_anydoc(pdf_path, log_callback=log_cb)
            else:
                # markitdown engine
                text, page_count = self._extract_with_markitdown(pdf_path, ext)
        except ImportError as e:
            error_msg = f"❌ Missing dependency: {e}"
        except FileNotFoundError as e:
            error_msg = f"❌ {e}"
        except Exception as e:
            error_msg = f"❌ {type(e).__name__}: {e}"

        if error_msg:
            return {"success": False, "status": error_msg}

        if not text or len(text.strip()) < 50:
            return {
                "success": False,
                "status": (
                    "⚠️ Very little text extracted. The document may be scanned "
                    "— use OCR Service or Full Conversion instead."
                ),
            }

        # Write the output (markdown / docx / pdf)
        out_p = _P(out_path)
        try:
            if out_ext == ".md":
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(text, encoding="utf-8")
            else:
                from core.outputs.service_formatters import write_output

                ok, msg = write_output(text, out_p, fmt=out_ext, title=_P(pdf_path).stem)
                if not ok:
                    return {"success": False, "status": f"⚠️ {msg}"}
        except Exception as e:
            return {"success": False, "status": f"❌ Write failed: {type(e).__name__}: {e}"}

        pages_str = str(page_count) if page_count else "?"
        p_out = _P(out_path)
        file_arg = str(p_out) if p_out.exists() else str(p_out.parent)
        return {
            "success": True,
            "status": (
                f"✅ Done!  Saved to: {out_path}\n"
                f"   Pages: {pages_str}  |  Engine: {engine}  |  Characters: {len(text):,}"
            ),
            "modal_message": (
                f"Saved to: {out_path}\nPages: {pages_str}  |  Engine: {engine}  |  Characters: {len(text):,}"
            ),
            "file_arg": file_arg,
        }

    def _on_convert_progress(self, pct: int, msg: str) -> None:
        # V18.20.4.5 (W-b5): main thread (queued signal) — safe to touch
        # widgets; no repaint hack needed.
        self.status_label.setText(msg)

    def _on_convert_finished(self, result) -> None:
        # V18.20.4.5 (W-b5): main-thread completion — the old post-
        # extraction UI block with identical strings and ordering.
        result = result or {}
        self.status_label.setText(result.get("status", ""))
        if result.get("success"):
            self.again_btn.setVisible(True)
            _show_success_modal(
                self,
                "📄 Document → Markdown Complete",
                result.get("modal_message", ""),
                file_path=result.get("file_arg"),
                on_try_another=self._on_try_another,
            )
            self.action_btn.setEnabled(True)
            self.action_btn.setText("Close")
        else:
            self.action_btn.setEnabled(True)
            self.action_btn.setText("Convert")

    def _on_convert_failed(self, err: str) -> None:
        # V18.20.4.5 (W-b5): the worker raised — surface on the main thread
        # and re-enable the button so the user can retry.
        self.status_label.setText(f"❌ Error: {err}")
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Convert")

    def _extract_with_markitdown(self, pdf_path: str, ext: str) -> tuple:
        """Fallback engine: use markitdown (or pypdf for plain PDFs).

        Returns ``(markdown, page_count)``.
        """
        # For PDFs, pypdf is fast and adds page markers the rest of the
        # pipeline understands. For everything else, use markitdown.
        if ext == ".pdf":
            import pypdf

            reader = pypdf.PdfReader(pdf_path)
            pages = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(f"<!-- page {i + 1} -->\n{page_text}")
            text = "\n\n".join(pages)
            return text, len(reader.pages)
        # markitdown for non-PDF
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(pdf_path)
        # markitdown result objects expose `.markdown` (str).
        md_text = getattr(result, "markdown", None) or str(result)
        # Best-effort page count from markers (markitdown doesn't always add them).
        page_count = len(re.findall(r"<!--\s*page\s+\d+\s*-->", md_text))
        return md_text, page_count
