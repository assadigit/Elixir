"""OCR Service dialog (V18.20.4.6, P5 / O-b2 split).

OcrServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt

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

logger = logging.getLogger(__name__)


class OcrServiceDialog(QDialog):
    """V11: Standalone OCR Service — pick files → choose engine → Convert → done.

    V13.26.0 (P1.3): Now delegates to core OCR modules instead of duplicating:
    - ``QwenOCREngine._call_ollama_vision()`` for Ollama vision OCR (proper prompt,
      proper timeout, proxy-proof via safe_ollama_request pattern)
    - ``summarisation.endpoint`` for the Ollama URL (was ``ocr.ollama_url``)
    - Core OCR prompt (was a different, shorter prompt)

    Supports batch: add multiple files, each gets its own output.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("🔍 OCR Service")
        self.setMinimumSize(560, 320)
        self.setModal(True)
        self._files: list = []
        # V18.20.4.5 (W-b5/T-b2): the background OCR worker (SimpleWorker).
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
            QListWidget as _QLW,
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

        title = _QL("🔍 OCR Service")
        title.setObjectName("H2")
        lay.addWidget(title)

        # File list + add/remove buttons
        file_row = _HL()
        file_row.setSpacing(8)
        self.file_list = _QLW()
        self.file_list.setMinimumHeight(80)
        self.file_list.setMaximumHeight(120)
        add_btn = _QPB("Add Files…")
        add_btn.clicked.connect(self._add_files)
        rm_btn = _QPB("Remove")
        rm_btn.clicked.connect(self._remove_file)
        file_btns = _VL()
        file_btns.setSpacing(4)
        file_btns.addWidget(add_btn)
        file_btns.addWidget(rm_btn)
        file_btns.addStretch()
        file_row.addWidget(self.file_list, 1)
        file_row.addLayout(file_btns)
        lay.addLayout(file_row)

        # Engine selector — V11.19: first option is "Default (change in Settings)".
        engine_row = _HL()
        engine_row.setSpacing(8)
        engine_row.addWidget(_QL("Engine:"))
        self.engine_combo = _QCB()
        self.engine_combo.addItem("Default (change in Settings)", "__default__")
        self.engine_combo.addItem("pypdf (fast, digital PDFs only)", "pypdf")
        self.engine_combo.addItem("Ollama Vision — OlmOCR/Qwen (local LLM)", "ollama")
        self.engine_combo.addItem("Local VLM — llava/minicpm (local LLM, better for infographics)", "vlm")
        self.engine_combo.addItem("Tesseract (lightweight, fast)", "tesseract")
        self.engine_combo.addItem("Auto (pypdf → Ollama → VLM → Tesseract)", "auto")
        # V11.19: default to "Default" (index 0). The old quick_services.ocr.engine
        # is still respected via the Defaults page.
        self.engine_combo.setCurrentIndex(0)
        engine_row.addWidget(self.engine_combo, 1)
        lay.addLayout(engine_row)

        # Output format — V11.18: added .docx + .pdf. V11.19: "Default" option.
        fmt_row = _HL()
        fmt_row.setSpacing(8)
        fmt_row.addWidget(_QL("Format:"))
        self.fmt_combo = _QCB()
        self.fmt_combo.addItem("Default (change in Settings)", "__default__")
        self.fmt_combo.addItem("Markdown (.md)", ".md")
        self.fmt_combo.addItem("Plain text (.txt)", ".txt")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.setCurrentIndex(0)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        lay.addLayout(fmt_row)

        # V11.20: Page range — lets the user OCR only a subset of a PDF.
        # Supports: "all" (or empty), "1-10", "1,3,5", "1-3,5,7-9".
        range_row = _HL()
        range_row.setSpacing(8)
        range_row.addWidget(_QL("Page range:"))
        self.range_edit = _QLE()
        self.range_edit.setPlaceholderText("all  (or e.g. 1-10, 1,3,5, 1-3,7-9)")
        self.range_edit.setText("all")
        self.range_edit.setMinimumWidth(200)
        range_row.addWidget(self.range_edit, 1)
        range_hint = _QL("💡 PDFs only — e.g. \"1-10\" for pages 1–10")
        range_hint.setObjectName("Caption")
        range_row.addWidget(range_hint)
        lay.addLayout(range_row)

        # Output folder picker
        out_row = _HL()
        out_row.setSpacing(8)
        out_row.addWidget(_QL("Output folder:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose where to save output files…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output_folder)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        lay.addLayout(out_row)

        # Status — V11.20: bigger + progress bar.
        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        self.status_label.setTextFormat(Qt.RichText)
        lay.addWidget(self.status_label)

        # V11.20: busy progress bar during OCR processing.
        from PySide6.QtWidgets import QProgressBar as _QPB2
        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        # Buttons — V11.18: added "Try Another File" so after a batch the
        # user can clear the list and OCR a different set without reopening.
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
        # V18.20.4.5 (T-b2): guard against closing while the OCR batch
        # worker runs — the "QThread: Destroyed while thread is still
        # running" abort class. Ask; on "close anyway" detach the worker
        # so the per-file loop's result is discarded, not crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _pick_output_folder(self):
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _add_files(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add documents", "",
            "Documents (*.pdf *.png *.jpg *.jpeg *.tif *.tiff);;All files (*.*)"
        )
        if paths:
            for p in paths:
                if p not in self._files:
                    self._files.append(p)
                    self.file_list.addItem(p)

    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0 and row < len(self._files):
            self._files.pop(row)
            self.file_list.takeItem(row)

    def _on_action(self):
        if self.action_btn.text() == "Close":
            self.accept()
            return
        self._do_convert()

    def _on_try_another(self):
        """V11.18: Clear the file list + results for a fresh OCR batch."""
        self._files.clear()
        self.file_list.clear()
        self.range_edit.setText("all")
        self.status_label.setText("Ready for the next batch — add files and click Convert.")
        self.again_btn.setVisible(False)
        self.action_btn.setText("Convert")
        self.action_btn.setEnabled(True)

    @staticmethod
    def _parse_page_range(text: str) -> list[int] | None:
        """V11.20: Parse a page-range string into a sorted list of 1-indexed
        page numbers, or None for "all" / empty.

        Supported formats:
          - "all" or "" → None (all pages)
          - "1-10" → [1,2,3,…,10]
          - "1,3,5" → [1,3,5]
          - "1-3,5,7-9" → [1,2,3,5,7,8,9]
        """
        text = text.strip().lower()
        if not text or text == "all":
            return None
        pages: set[int] = set()
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                lo, hi = part.split("-", 1)
                try:
                    lo_i, hi_i = int(lo.strip()), int(hi.strip())
                    if lo_i > hi_i:
                        lo_i, hi_i = hi_i, lo_i
                    pages.update(range(max(1, lo_i), hi_i + 1))
                except ValueError:
                    continue  # skip malformed
            else:
                try:
                    p = int(part)
                    if p >= 1:
                        pages.add(p)
                except ValueError:
                    continue
        return sorted(pages) if pages else None

    def _do_convert(self):
        # V18.20.4.5 (W-b5): re-entrancy guard — a second click while a
        # batch runs would spawn a second worker writing the same output
        # paths (the guard class V11.29.2 ported to this dialog).
        if self._worker is not None and self._worker.is_running():
            self.status_label.setText("⏳ Already converting — wait for the current batch to finish.")
            return

        if not self._files:
            self.status_label.setText("⚠️ Add at least one file first.")
            return

        out_folder = self.out_edit.text().strip()
        if not out_folder:
            self.status_label.setText("⚠️ Please choose an output folder.")
            return

        # V11.20: parse the page range (None = all pages).
        page_range_text = self.range_edit.text().strip()
        pages = self._parse_page_range(page_range_text)
        if pages is None:
            pages_desc = "all pages"
        else:
            pages_desc = f"pages {pages[0]}–{pages[-1]}" if len(pages) > 1 else f"page {pages[0]}"

        # V11.19: resolve "__default__" sentinels from quick_services.defaults.*
        from utils.settings import Settings as _S
        _s = _S()
        engine = self.engine_combo.currentData()
        if engine == "__default__" or not engine:
            engine = _s.get("quick_services.defaults.ocr_engine", "") or _s.get("quick_services.ocr.engine", "auto")
        suffix = self.fmt_combo.currentData()
        if suffix == "__default__" or not suffix:
            suffix = _s.get("quick_services.defaults.ocr_format", "") or _s.get("quick_services.ocr.format", ".md")

        # V11.19: only persist the legacy quick_services.ocr.* keys when the
        # user picked a concrete value (not "Default").
        if self.engine_combo.currentData() and self.engine_combo.currentData() != "__default__":
            _s.set("quick_services.ocr.engine", engine)
        if self.fmt_combo.currentData() and self.fmt_combo.currentData() != "__default__":
            _s.set("quick_services.ocr.format", suffix)
        _s.save()

        # V18.20.4.5 (W-b5): the blocking per-file OCR loop (minutes per
        # book on the Ollama/tesseract engines) moved OFF the UI thread.
        # OLD defect: the whole loop ran inline with a
        # QApplication.processEvents() repaint hack — the same re-entrancy/
        # freeze class V11.29.2 removed from BaseServiceDialog._on_progress,
        # never ported to this dialog. Per-file progress now rides the
        # worker's queued progress signal (BaseWorker contract) and the
        # completion UI lands in _on_convert_finished on the main thread.
        files = list(self._files)  # snapshot — the list can change mid-run now
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Processing…")
        self.progress_bar.setVisible(True)

        # The lambda referencing self._worker is safe: Python closures
        # late-bind, so at call time (worker thread) the attribute exists
        # and refers to THIS worker.
        self._worker = SimpleWorker(
            lambda: self._ocr_work(files, out_folder, engine, suffix,
                                   pages, pages_desc,
                                   report=self._worker.progress.emit))
        self._worker.progress.connect(self._on_convert_progress)
        self._worker.finished.connect(self._on_convert_finished)
        self._worker.failed.connect(self._on_convert_failed)
        self._worker.start()

    def _ocr_work(self, files, out_folder, engine, suffix, pages, pages_desc,
                  report=None) -> dict:
        """V18.20.4.5 (W-b5): the per-file OCR loop, worker-thread edition.

        Pure file/HTTP/LLM work — NO widget access. Per-file progress goes
        through ``report(pct, html)`` (the worker's queued progress signal →
        ``_on_convert_progress`` on the main thread) with the exact HTML
        label content the old inline loop built. Returns the plain result
        dict consumed by ``_on_convert_finished``.
        """
        from pathlib import Path as _P

        results = []
        total = len(files)
        for i, file_path in enumerate(files):
            # V11.20: bigger, bolder progress text (identical to the old
            # inline version, now emitted instead of set directly).
            if report is not None:
                report(int(i * 100 / total) if total else 0, (
                    f"<div style='font-size:15px; font-weight:600;'>"
                    f"🔍 OCR {i+1}/{total}: <span style='color: var(--primary);'>{_P(file_path).name}</span>"
                    f"</div>"
                    f"<div style='font-size:12px; color: var(--muted-foreground); margin-top:2px;'>"
                    f"engine: {engine}  |  format: {suffix}  |  {pages_desc}"
                    f"</div>"
                ))

            try:
                path = _P(file_path)
                out_path = _P(out_folder) / f"{path.stem}_ocr{suffix}"

                if engine == "auto":
                    text = self._ocr_auto(path, pages=pages)
                elif engine == "pypdf":
                    text = self._ocr_pypdf(path, pages=pages)
                elif engine == "ollama":
                    text = self._ocr_ollama(path, vlm=False, pages=pages)
                elif engine == "vlm":
                    text = self._ocr_ollama(path, vlm=True, pages=pages)
                elif engine == "tesseract":
                    text = self._ocr_tesseract(path, pages=pages)
                else:
                    text = self._ocr_auto(path, pages=pages)

                if text and len(text.strip()) >= 10:
                    # V11.18: support .docx / .pdf output via shared formatter
                    if suffix in (".md", ".txt"):
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text(text, encoding="utf-8")
                    else:
                        from core.outputs.service_formatters import write_output
                        write_output(text, out_path, fmt=suffix, title=path.stem)
                    results.append(f"✅ {path.name} → {out_path.name} ({len(text):,} chars)")
                else:
                    results.append(f"⚠️ {path.name} → little/no text (try another engine)")
            except Exception as e:
                results.append(f"❌ {path.name} → {type(e).__name__}: {e}")

        return {"results": results, "total": total, "pages_desc": pages_desc}

    def _on_convert_progress(self, pct: int, msg: str) -> None:
        # V18.20.4.5 (W-b5): main thread (queued signal) — safe to touch
        # widgets; no repaint hack needed (Qt repaints on return to the
        # event loop).
        self.status_label.setText(msg)

    def _on_convert_finished(self, result) -> None:
        # V18.20.4.5 (W-b5): main-thread completion — the old post-loop UI
        # block with identical strings.
        self.progress_bar.setVisible(False)
        result = result or {}
        results = result.get("results", [])
        total = result.get("total", 0)
        pages_desc = result.get("pages_desc", "all pages")

        summary = f"Done! {total} file(s) processed ({pages_desc}):\n\n" + "\n".join(results)
        self.status_label.setText(summary)
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Close")
        # V11.18: surface "Try Another File".
        self.again_btn.setVisible(True)

        # V11.25: success modal with "Try Another" + "Open File Location".
        # Use the output folder as the file_path (OCR outputs go to a folder).
        out_folder = self.out_edit.text().strip()
        _show_success_modal(
            self,
            "🔍 OCR Complete",
            summary,
            file_path=out_folder if out_folder else None,
            on_try_another=self._on_try_another,
        )

    def _on_convert_failed(self, err: str) -> None:
        # V18.20.4.5 (W-b5): the worker raised — surface on the main thread
        # and re-enable the button so the user can retry.
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ Error: {err}")
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Convert")

    def _ocr_auto(self, path, pages: list[int] | None = None) -> str:
        """Auto-cascade: pypdf → Ollama → VLM → Tesseract.

        V11.20: ``pages`` is a list of 1-indexed page numbers, or None for
        all pages. Only applies to PDFs; image files ignore it.
        """
        # 1. Try pypdf (fast, works for digital PDFs)
        if path.suffix.lower() == ".pdf":
            text = self._ocr_pypdf(path, pages=pages)
            if text and len(text.strip()) > 50:
                return text

        # 2. Try Ollama vision model
        try:
            text = self._ocr_ollama(path, vlm=False, pages=pages)
            if text and len(text.strip()) > 10:
                return text
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)

        # 3. Try local VLM
        try:
            text = self._ocr_ollama(path, vlm=True, pages=pages)
            if text and len(text.strip()) > 10:
                return text
        except Exception:
            logger.debug("best-effort op failed", exc_info=True)

        # 4. Last resort: Tesseract
        return self._ocr_tesseract(path, pages=pages)

    def _ocr_pypdf(self, path, pages: list[int] | None = None) -> str:
        """Extract text from PDF using pypdf (fast, digital pages only).

        V11.20: ``pages`` filters to specific 1-indexed page numbers.
        """
        import pypdf
        reader = pypdf.PdfReader(str(path))
        out_pages = []
        page_indices = pages if pages is not None else range(1, len(reader.pages) + 1)
        for pg_num in page_indices:
            idx = pg_num - 1  # 0-indexed
            if idx < 0 or idx >= len(reader.pages):
                continue  # page out of range — skip
            page_text = reader.pages[idx].extract_text() or ""
            if page_text.strip():
                out_pages.append(f"<!-- page {pg_num} -->\n{page_text}")
        return "\n\n".join(out_pages)

    def _ocr_ollama(self, path, vlm: bool = False, pages: list[int] | None = None) -> str:
        """V13.26.0 (P1.3): Run Ollama vision OCR using QwenOCREngine.

        Delegates the actual LLM call to ``QwenOCREngine._call_ollama_vision()``
        which uses the proper OCR prompt, proper timeout handling, and the
        canonical Ollama URL from ``summarisation.endpoint``.

        Previously this method called ``requests.post`` directly with a
        different prompt, wrong settings key (``ocr.ollama_url``), and no
        proxy-proofing.

        V11.20: ``pages`` filters to specific 1-indexed page numbers (PDFs
        only). Uses ``first_page``/``last_page`` in ``convert_from_path`` for
        efficiency, then filters to the exact set.
        """
        from core.ocr.qwen_ocr import QwenOCREngine
        from utils.settings import Settings
        s = Settings()

        if vlm:
            model = s.get("ocr.vlm_fallback_model", "llava:13b")
        else:
            model = s.get("ocr.primary_model", "OlmOCR-2-7B:latest")

        # V13.26.0: Read the canonical Ollama URL (was ocr.ollama_url)
        ollama_url = s.get("summarisation.endpoint", "http://localhost:11434")
        if not ollama_url:
            ollama_url = "http://localhost:11434"
        # Strip /v1 suffix — /api/generate needs the base URL
        if ollama_url.endswith("/v1"):
            ollama_url = ollama_url[:-3]
        ollama_url = ollama_url.rstrip("/")

        # Create the QwenOCREngine — it has the proper prompt + timeout
        engine = QwenOCREngine(
            model_name=model,
            ollama_base_url=ollama_url,
            timeout=180,
        )

        # Convert to image bytes
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            # Single image — page range doesn't apply.
            image_bytes = path.read_bytes()
            text = engine._call_ollama_vision(image_bytes)
            return text.strip() if text else ""
        else:
            # PDF: convert requested pages to images.
            from io import BytesIO

            from pdf2image import convert_from_path
            first_page = min(pages) if pages else None
            last_page = max(pages) if pages else None
            kwargs = {"dpi": 300}
            if first_page is not None:
                kwargs["first_page"] = first_page
                kwargs["last_page"] = last_page
            images = convert_from_path(str(path), **kwargs)
            all_text = []
            for i, img in enumerate(images):
                actual_page = (first_page or 1) + i
                if pages is not None and actual_page not in pages:
                    continue
                buf = BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
                page_text = engine._call_ollama_vision(image_bytes)
                if page_text and page_text.strip():
                    all_text.append(f"<!-- page {actual_page} -->\n{page_text.strip()}")
            return "\n\n".join(all_text) if all_text else ""

    def _ocr_tesseract(self, path, pages: list[int] | None = None) -> str:
        """Run Tesseract OCR.

        V11.20: ``pages`` filters to specific 1-indexed page numbers (PDFs
        only). Uses ``first_page``/``last_page`` in ``convert_from_path`` for
        efficiency, then filters to the exact set.
        """
        from utils.settings import Settings
        s = Settings()
        tess_cmd = s.get("paths.tesseract", "")

        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            # Direct image OCR — page range doesn't apply.
            import subprocess
            cmd = [tess_cmd, str(path), "-", "-l", "eng+fas"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.stdout.strip()
        else:
            # PDF: convert to images then OCR each.
            import pytesseract
            from pdf2image import convert_from_path
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
            # V11.20: if a page range is specified, only convert that range.
            first_page = min(pages) if pages else None
            last_page = max(pages) if pages else None
            kwargs = {"dpi": 300}
            if first_page is not None:
                kwargs["first_page"] = first_page
                kwargs["last_page"] = last_page
            images = convert_from_path(str(path), **kwargs)
            out_pages = []
            for i, img in enumerate(images):
                actual_page = (first_page or 1) + i
                # V11.20: skip pages not in the requested set.
                if pages is not None and actual_page not in pages:
                    continue
                text = pytesseract.image_to_string(img, lang="eng+fas")
                if text.strip():
                    out_pages.append(f"<!-- page {actual_page} -->\n{text}")
            return "\n\n".join(out_pages)
