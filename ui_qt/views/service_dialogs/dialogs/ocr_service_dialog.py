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
        self.setMinimumSize(560, 360)
        self.setModal(True)
        self._files: list = []
        # V18.20.4.5 (W-b5/T-b2): the background OCR worker (SimpleWorker).
        self._worker: SimpleWorker | None = None
        # V0.4.5: cache of Ollama OCR models discovered via /api/tags.
        self._ollama_ocr_models: list[str] = []

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
        # V0.4.5: QToolButton for the Advanced expander toggle.
        from PySide6.QtWidgets import QToolButton as _QTB

        lay = _VL(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = _QL("🔍 OCR Service")
        title.setObjectName("H2")
        lay.addWidget(title)

        # ── V0.4.5: File list (compact — single row of buttons beside the list)
        file_row = _HL()
        file_row.setSpacing(8)
        self.file_list = _QLW()
        self.file_list.setMinimumHeight(60)
        self.file_list.setMaximumHeight(80)
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

        # ── V0.4.5: Engine selector — reorganized to minimize cognitive load.
        # OLD: 6 options including "Default (change in Settings)" + 5 named
        # engines + "Auto" buried at the bottom. User had to understand the
        # backend architecture (the Auto cascade: pypdf→Ollama→VLM→Tesseract)
        # just to pick an engine.
        # NEW: "Auto (recommended)" is first + default. Then the auto-detected
        # Ollama OCR models (queried live via /api/tags). Then Tesseract as
        # a lightweight fallback. The legacy named engines (pypdf, vlm) moved
        # under the Advanced expander for users who need them.
        engine_row = _HL()
        engine_row.setSpacing(8)
        engine_row.addWidget(_QL("Engine:"))
        self.engine_combo = _QCB()
        # "Auto" is the recommended default — it tries the best engine
        # automatically (digital PDFs → pypdf, scanned → Ollama vision,
        # fallback → Tesseract).
        self.engine_combo.addItem(
            "Auto (recommended) — picks the best engine per file", "auto"
        )
        self.engine_combo.addItem(
            "Tesseract (lightweight, fast, offline)", "tesseract"
        )
        # V0.4.5: populate Ollama OCR models via live /api/tags probe.
        # Done in _populate_ollama_models() below — runs async-ish (best-
        # effort; if Ollama is down, the user just sees the static options).
        self.engine_combo.setCurrentIndex(0)
        engine_row.addWidget(self.engine_combo, 1)
        # Refresh button — lets the user re-probe Ollama if they started it
        # after opening the dialog.
        self._refresh_ollama_btn = _QPB("🔄")
        self._refresh_ollama_btn.setToolTip("Re-scan Ollama for OCR models")
        self._refresh_ollama_btn.setFixedWidth(32)
        self._refresh_ollama_btn.clicked.connect(self._populate_ollama_models)
        engine_row.addWidget(self._refresh_ollama_btn)
        lay.addLayout(engine_row)

        # V0.4.5: one-line hint below the engine dropdown — explains what
        # the selected engine does, so the user doesn't have to guess.
        self.engine_hint = _QL("")
        self.engine_hint.setObjectName("Caption")
        self.engine_hint.setWordWrap(True)
        self.engine_hint.setStyleSheet("color: var(--muted-foreground); margin-left: 60px; margin-top: -4px;")
        lay.addWidget(self.engine_hint)
        self.engine_combo.currentIndexChanged.connect(self._update_engine_hint)
        # Populate on next tick (after the dialog is fully laid out) so
        # the hint shows the right text for the default "Auto" option.
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, self._update_engine_hint)
        _QTimer.singleShot(100, self._populate_ollama_models)

        # ── V0.4.5: Output format (kept simple — 4 options, "Auto" first)
        fmt_row = _HL()
        fmt_row.setSpacing(8)
        fmt_row.addWidget(_QL("Format:"))
        self.fmt_combo = _QCB()
        self.fmt_combo.addItem("Markdown (.md) — recommended", ".md")
        self.fmt_combo.addItem("Plain text (.txt)", ".txt")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.setCurrentIndex(0)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        lay.addLayout(fmt_row)

        # ── V0.4.5: Advanced expander — hidden by default. Contains the
        # page-range + output-folder + legacy engine options that most
        # users don't need. Collapsing these cuts the visible control
        # count from 4 to 2 (Engine + Format), the V0.4.4 screenshot's
        # main cognitive-load complaint.
        self.advanced_toggle = _QTB()
        self.advanced_toggle.setText("⚙ Advanced (page range, output folder, legacy engines)")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        lay.addWidget(self.advanced_toggle)

        self.advanced_widget = QWidget()
        adv_lay = _VL(self.advanced_widget)
        adv_lay.setContentsMargins(20, 4, 0, 0)
        adv_lay.setSpacing(8)

        # Legacy engine selector (for users who want pypdf/VLM specifically)
        legacy_engine_row = _HL()
        legacy_engine_row.setSpacing(8)
        legacy_engine_row.addWidget(_QL("Legacy engine:"))
        self.legacy_engine_combo = _QCB()
        self.legacy_engine_combo.addItem("(use the main Engine dropdown above)", "__default__")
        self.legacy_engine_combo.addItem("pypdf (fast, digital PDFs only)", "pypdf")
        self.legacy_engine_combo.addItem("Local VLM — llava/minicpm (better for infographics)", "vlm")
        self.legacy_engine_combo.setCurrentIndex(0)
        legacy_engine_row.addWidget(self.legacy_engine_combo, 1)
        adv_lay.addLayout(legacy_engine_row)

        # Page range
        range_row = _HL()
        range_row.setSpacing(8)
        range_row.addWidget(_QL("Page range:"))
        self.range_edit = _QLE()
        self.range_edit.setPlaceholderText("all  (or e.g. 1-10, 1,3,5, 1-3,7-9)")
        self.range_edit.setText("all")
        self.range_edit.setMinimumWidth(200)
        range_row.addWidget(self.range_edit, 1)
        range_hint = _QL('💡 PDFs only — e.g. "1-10" for pages 1–10')
        range_hint.setObjectName("Caption")
        range_row.addWidget(range_hint)
        adv_lay.addLayout(range_row)

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
        adv_lay.addLayout(out_row)

        lay.addWidget(self.advanced_widget)
        self.advanced_widget.setVisible(False)
        self.advanced_toggle.toggled.connect(self.advanced_widget.setVisible)
        # V0.4.5: toggle the arrow direction when expanded/collapsed.
        self.advanced_toggle.toggled.connect(
            lambda checked: self.advanced_toggle.setArrowType(
                Qt.DownArrow if checked else Qt.RightArrow
            )
        )

        # ── V0.4.5: Status (bigger + progress bar — same as V11.20)
        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        self.status_label.setTextFormat(Qt.RichText)
        lay.addWidget(self.status_label)

        from PySide6.QtWidgets import QProgressBar as _QPB2

        self.progress_bar = _QPB2()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        lay.addWidget(self.progress_bar)

        # ── V0.4.5: Buttons (unchanged — "Try Another File" + Convert)
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

    # ── V0.4.5: Ollama OCR model auto-detection ───────────────────────────

    # OCR-related name keywords — a model is considered an OCR model if
    # its name (case-insensitive) contains any of these. Content-agnostic:
    # the list is the canonical set of OCR/vision model family names, not
    # hardcoded specific model versions.
    _OCR_KEYWORDS = (
        "ocr",        # OlmOCR, ocr-vision, etc.
        "vision",     # qwen2-vl, llama-vision, etc.
        "vl",         # qwen2-vl, llava-vl, etc. (vision-language)
        "llava",      # llava family
        "minicpm",    # minicpm-v (vision)
        "moondream",  # moondream2 (vision)
        "bakllava",   # bakllava
        "llama-vision",  # meta llama-vision
        "qwen-vl",    # qwen vision-language
        "internvl",   # internvl
        "cogvlm",     # cogvlm
        "fuyu",       # adept fuyu
        "kosmos",     # microsoft kosmos
        "florence",   # microsoft florence
    )

    def _populate_ollama_models(self) -> None:
        """V0.4.5: query Ollama /api/tags and list every installed model
        whose name contains an OCR-related keyword.

        Reuses utils.network.list_ollama_models(). Content-agnostic —
        matches by name keyword, not by hardcoded model strings. Runs
        in the foreground (the dialog isn't usable until the user picks
        an engine anyway; a 50ms /api/tags call is fine).

        The discovered models are inserted into the engine_combo right
        after "Auto (recommended)" and before "Tesseract", so the user
        sees: Auto → [detected OCR models] → Tesseract. The static
        "Tesseract" option stays at the bottom as a guaranteed fallback.
        """
        from utils.network import list_ollama_models
        from utils.settings import Settings as _S

        try:
            s = _S()
            base_url = s.get("summarisation.endpoint", "http://localhost:11434") or "http://localhost:11434"
            # Strip /v1 suffix for /api/tags
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            base_url = base_url.rstrip("/")

            models = list_ollama_models(base_url)
            if not models:
                self._ollama_ocr_models = []
                return

            # Filter by OCR-related keywords (case-insensitive).
            ocr_models = []
            for m in models:
                m_lower = m.lower()
                if any(kw in m_lower for kw in self._OCR_KEYWORDS):
                    ocr_models.append(m)
            ocr_models.sort(key=str.lower)

            # If the list hasn't changed, no need to rebuild the combo.
            if ocr_models == self._ollama_ocr_models:
                return

            # Remember the current selection (if any) so we can restore it.
            prev_data = self.engine_combo.currentData()

            # Remove any previously-added Ollama model items (identified
            # by their data being a non-empty string that's not one of
            # the static sentinels: "auto", "tesseract").
            i = 0
            while i < self.engine_combo.count():
                data = self.engine_combo.itemData(i)
                if data and data not in ("auto", "tesseract"):
                    self.engine_combo.removeItem(i)
                else:
                    i += 1

            # Insert the discovered OCR models right after "Auto" (index 0)
            # and before "Tesseract" (which is now at index 1).
            insert_at = 1  # after Auto
            for model_name in ocr_models:
                # Use a user-friendly label: "Ollama: <model_name>".
                label = f"Ollama: {model_name}"
                self.engine_combo.insertItem(insert_at, label, model_name)
                insert_at += 1

            self._ollama_ocr_models = ocr_models

            # Restore the previous selection if it's still in the list.
            if prev_data:
                idx = self.engine_combo.findData(prev_data)
                if idx >= 0:
                    self.engine_combo.setCurrentIndex(idx)
        except Exception as e:
            logger.debug("Ollama OCR model probe failed (non-fatal): %s: %s", type(e).__name__, e)

    def _update_engine_hint(self) -> None:
        """V0.4.5: show a one-line explanation of the selected engine.

        Removes the user's need to understand the backend architecture
        (the V0.4.4 audit found the "Auto (pypdf → Ollama → VLM → Tesseract)"
        label forced users to understand the cascade just to pick an engine).
        """
        data = self.engine_combo.currentData()
        hints = {
            "auto": "💡 Tries the best engine automatically: digital PDFs use pypdf, scanned docs use Ollama vision, with Tesseract as a fallback.",
            "tesseract": "💡 Fast, offline, lightweight. Best for clear scans. May struggle with handwriting or complex layouts.",
            "pypdf": "💡 Fastest for digital (text-based) PDFs. Won't work on scanned/image PDFs.",
            "vlm": "💡 Local vision-language model (llava/minicpm). Best for infographics, charts, and diagrams with text.",
        }
        # For Ollama models (data is a model name, not a sentinel), show
        # a generic "uses the Ollama vision API" hint.
        if data and data not in ("auto", "tesseract", "pypdf", "vlm"):
            hint = f"💡 Uses the Ollama vision model \'{data}\' for OCR. Good for scanned docs and images."
        else:
            hint = hints.get(data, "")
        self.engine_hint.setText(hint)

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
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", "")
        if folder:
            self.out_edit.setText(folder)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add documents",
            "",
            "Documents (*.pdf *.png *.jpg *.jpeg *.tif *.tiff);;All files (*.*)",
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
            self.status_label.setText(
                "⏳ Already converting — wait for the current batch to finish."
            )
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
        # V0.4.5: the new UI structure — the main engine_combo has "auto",
        # "tesseract", or an Ollama model name (from the live /api/tags probe).
        # The legacy engines (pypdf, vlm) moved to the Advanced expander's
        # legacy_engine_combo. If the user picked a legacy engine there, it
        # overrides the main dropdown (which stays at "Auto").
        from utils.settings import Settings as _S

        _s = _S()
        engine = self.engine_combo.currentData()
        # V0.4.5: if the user expanded Advanced and picked a legacy engine,
        # that takes precedence (it's an explicit user choice).
        legacy_engine = self.legacy_engine_combo.currentData()
        if legacy_engine and legacy_engine != "__default__":
            engine = legacy_engine
        elif engine == "__default__" or not engine:
            engine = _s.get("quick_services.defaults.ocr_engine", "") or _s.get(
                "quick_services.ocr.engine", "auto"
            )
        # V0.4.5: persist the selected Ollama model name as the OCR primary
        # model, so the _ocr_ollama() backend call picks it up.
        if engine and engine not in ("auto", "tesseract", "pypdf", "vlm"):
            # engine is an Ollama model name — save it as the primary OCR model.
            _s.set("ocr.primary_model", engine)
        suffix = self.fmt_combo.currentData()
        # V0.4.5: the new fmt_combo has no "__default__" sentinel (the
        # first option is "Markdown (.md) — recommended" with data=".md").
        # Keep the legacy resolution for backward compat.
        if suffix == "__default__" or not suffix:
            suffix = _s.get("quick_services.defaults.ocr_format", "") or _s.get(
                "quick_services.ocr.format", ".md"
            )

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
            lambda: self._ocr_work(
                files,
                out_folder,
                engine,
                suffix,
                pages,
                pages_desc,
                report=self._worker.progress.emit,
            )
        )
        self._worker.progress.connect(self._on_convert_progress)
        self._worker.finished.connect(self._on_convert_finished)
        self._worker.failed.connect(self._on_convert_failed)
        self._worker.start()

    def _ocr_work(self, files, out_folder, engine, suffix, pages, pages_desc, report=None) -> dict:
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
                report(
                    int(i * 100 / total) if total else 0,
                    (
                        f"<div style='font-size:15px; font-weight:600;'>"
                        f"🔍 OCR {i + 1}/{total}: <span style='color: var(--primary);'>{_P(file_path).name}</span>"
                        f"</div>"
                        f"<div style='font-size:12px; color: var(--muted-foreground); margin-top:2px;'>"
                        f"engine: {engine}  |  format: {suffix}  |  {pages_desc}"
                        f"</div>"
                    ),
                )

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
                elif engine and engine not in ("auto", "tesseract", "pypdf", "vlm"):
                    # V0.4.5: engine is an Ollama model name (selected from
                    # the auto-detected list via /api/tags). The
                    # _do_convert() method already saved it as
                    # ocr.primary_model, so _ocr_ollama() will pick it up.
                    text = self._ocr_ollama(path, vlm=False, pages=pages)
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
