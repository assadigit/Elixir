"""PDF/DOCX Cutter dialog (V18.20.4.6, P5 / O-b2 split).

PdfDocxCutterDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade)."""

from __future__ import annotations

import logging

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


class PdfDocxCutterDialog(QDialog):
    """V11.30: PDF/DOCX Cutter — extract a range of pages from a PDF or DOCX
    and save the output in the same format.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("✂ PDF/DOCX Cutter")
        self.setMinimumSize(520, 280)
        self.setModal(True)
        # V18.20.4.5 (W-b5/T-b2): the background cut worker (SimpleWorker).
        self._worker: SimpleWorker | None = None

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

        title = _QL("✂ PDF/DOCX Cutter")
        title.setObjectName("H2")
        lay.addWidget(title)

        in_row = _HL()
        in_row.setSpacing(8)
        in_row.addWidget(_QL("Input:"))
        self.in_edit = _QLE()
        self.in_edit.setPlaceholderText("Pick a .pdf or .docx file…")
        in_browse = _QPB("Browse…")
        in_browse.clicked.connect(self._pick_input)
        in_row.addWidget(self.in_edit, 1)
        in_row.addWidget(in_browse)
        lay.addLayout(in_row)

        range_row = _HL()
        range_row.setSpacing(8)
        range_row.addWidget(_QL("Pages:"))
        self.range_edit = _QLE()
        self.range_edit.setPlaceholderText("e.g. 1-10, 1,3,5, or 'all'")
        self.range_edit.setText("all")
        self.range_edit.setMinimumWidth(200)
        range_row.addWidget(self.range_edit, 1)
        range_hint = _QL("💡 1-indexed page numbers")
        range_hint.setObjectName("Caption")
        range_row.addWidget(range_hint)
        lay.addLayout(range_row)

        out_row = _HL()
        out_row.setSpacing(8)
        out_row.addWidget(_QL("Save as:"))
        self.out_edit = _QLE()
        self.out_edit.setPlaceholderText("Choose where to save the cut file…")
        out_browse = _QPB("Browse…")
        out_browse.clicked.connect(self._pick_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_browse)
        lay.addLayout(out_row)

        self.status_label = _QL("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        btn_row = _HL()
        btn_row.addStretch()
        self.action_btn = _QPB("Cut")
        self.action_btn.setObjectName("Primary")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)
        lay.addLayout(btn_row)

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the cut worker
        # runs — the "QThread: Destroyed while thread is still running"
        # abort class. Ask; on "close anyway" detach the worker so the
        # cut result is discarded, not crashed on.
        if not _confirm_close_with_running_worker(self, self._worker):
            event.ignore()
            return
        super().closeEvent(event)

    def _pick_input(self):
        from pathlib import Path as _P

        path, _ = QFileDialog.getOpenFileName(
            self, "Pick a file", "", "Documents (*.pdf *.docx);;All files (*.*)"
        )
        if path:
            self.in_edit.setText(path)
            p = _P(path)
            # V11.31: default filename = {stem}-cut{ext} in source location.
            self.out_edit.setText(str(p.parent / f"{p.stem}-cut{p.suffix}"))

    def _pick_output(self):
        from pathlib import Path as _P

        in_path = self.in_edit.text().strip()
        ext = _P(in_path).suffix if in_path else ".pdf"
        filter_str = f"{'PDF' if ext == '.pdf' else 'Word'} (*{ext});;All files (*.*)"
        path, _ = QFileDialog.getSaveFileName(self, "Save cut file as", "", filter_str)
        if path:
            if not path.endswith(ext):
                path += ext
            self.out_edit.setText(path)

    def _on_action(self):
        if self.action_btn.text() == "Close":
            self.accept()
            return
        self._do_cut()

    @staticmethod
    def _parse_range(text: str) -> list[int] | None:
        text = text.strip().lower()
        if not text or text == "all":
            return None
        pages: set[int] = set()
        for part in text.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                try:
                    lo_i, hi_i = int(lo.strip()), int(hi.strip())
                    if lo_i > hi_i:
                        lo_i, hi_i = hi_i, lo_i
                    pages.update(range(max(1, lo_i), hi_i + 1))
                except ValueError:
                    continue
            else:
                try:
                    p = int(part)
                    if p >= 1:
                        pages.add(p)
                except ValueError:
                    continue
        return sorted(pages) if pages else None

    def _do_cut(self):
        # V18.20.4.5 (W-b5): re-entrancy guard — a second click while a cut
        # runs would spawn a second worker on the same paths.
        if self._worker is not None and self._worker.is_running():
            self.status_label.setText("⏳ Already cutting — wait for the current job to finish.")
            return

        in_path = self.in_edit.text().strip()
        out_path = self.out_edit.text().strip()
        if not in_path:
            self.status_label.setText("⚠️ Please pick an input file.")
            return
        if not out_path:
            self.status_label.setText("⚠️ Please choose where to save the output.")
            return
        pages = self._parse_range(self.range_edit.text())
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Processing…")
        # V18.20.4.5 (W-b5): the blocking cut (pypdf / python-docx work on
        # multi-hundred-page books) moved OFF the UI thread — the old code
        # ran it inline with a single QApplication.processEvents() repaint
        # hack, freezing the dialog for the whole cut. Completion lands in
        # _on_cut_finished on the main thread.

        # The lambda referencing self._worker is safe: Python closures
        # late-bind, so at call time (worker thread) the attribute exists
        # and refers to THIS worker.
        self._worker = SimpleWorker(
            lambda: self._cut_work(in_path, out_path, pages, report=self._worker.progress.emit)
        )
        self._worker.progress.connect(self._on_cut_progress)
        self._worker.finished.connect(self._on_cut_finished)
        self._worker.failed.connect(self._on_cut_failed)
        self._worker.start()

    def _cut_work(self, in_path: str, out_path: str, pages: list[int] | None, report=None) -> dict:
        """V18.20.4.5 (W-b5): the pypdf / python-docx cut, worker-thread
        edition.

        Pure file work — NO widget access (``_cut_pdf``/``_cut_docx`` were
        verified widget-free). ``report`` is accepted for pattern-parity
        with the other W-b5 dialogs; the cut itself has no per-page
        updates to stream (the old code had none either). Exceptions are
        caught and returned as error results so the exact old status
        strings survive the thread hop. Returns the plain result dict
        consumed by ``_on_cut_finished``.
        """
        from pathlib import Path as _P

        try:
            ext = _P(in_path).suffix.lower()
            if ext == ".pdf":
                self._cut_pdf(in_path, out_path, pages)
            elif ext == ".docx":
                self._cut_docx(in_path, out_path, pages)
            else:
                return {"error": "❌ Only .pdf and .docx are supported."}
            return {"out_path": out_path}
        except Exception as e:
            return {"error": f"❌ Error: {type(e).__name__}: {e}"}

    def _on_cut_progress(self, pct: int, msg: str) -> None:
        # V18.20.4.5 (W-b5): main thread (queued signal) — safe to touch
        # widgets; no repaint hack needed.
        self.status_label.setText(msg)

    def _on_cut_finished(self, result) -> None:
        # V18.20.4.5 (W-b5): main-thread completion — the old post-cut UI
        # block with identical strings (the button intentionally stays
        # disabled on success, exactly as before — the modal + window X
        # close the dialog).
        result = result or {}
        if result.get("error"):
            self.status_label.setText(result["error"])
            self.action_btn.setEnabled(True)
            self.action_btn.setText("Cut")
            return
        out_path = result.get("out_path", "")
        self.status_label.setText(f"✅ Done! Saved to: {out_path}")
        self.action_btn.setText("Close")
        _show_success_modal(self, "✂ Cut Complete", f"Saved to: {out_path}", file_path=out_path)

    def _on_cut_failed(self, err: str) -> None:
        # V18.20.4.5 (W-b5): the worker raised — surface on the main thread
        # and re-enable the button so the user can retry.
        self.status_label.setText(f"❌ Error: {err}")
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Cut")

    def _cut_pdf(self, in_path: str, out_path: str, pages: list[int] | None) -> None:
        from pathlib import Path as _P

        import pypdf

        reader = pypdf.PdfReader(in_path)
        writer = pypdf.PdfWriter()
        if pages is None:
            for page in reader.pages:
                writer.add_page(page)
        else:
            for pg in pages:
                idx = pg - 1
                if 0 <= idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
        out_p = _P(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "wb") as f:
            writer.write(f)

    def _cut_docx(self, in_path: str, out_path: str, pages: list[int] | None) -> None:
        """V11.31.1: Cut a DOCX by page breaks.

        Handles DOCX files converted from PDFs (which may have no page
        break elements — the content is in tables/text boxes). Falls back
        to splitting by paragraph count (approximating pages at ~40
        paragraphs per "page").
        """
        from pathlib import Path as _P

        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(in_path)

        # ── Strategy 1: Split at explicit page breaks (w:br type="page") ──
        page_groups: list[list] = []
        current_group: list = []

        for para in doc.paragraphs:
            current_group.append(para)
            has_break = False
            for run in para.runs:
                for elem in run._element:
                    if elem.tag == qn("w:br") and elem.get(qn("w:type")) == "page":
                        has_break = True
                        break
                if has_break:
                    break
            if has_break:
                page_groups.append(current_group)
                current_group = []

        if current_group:
            page_groups.append(current_group)

        # ── Strategy 2: If no page breaks, split by section breaks ──
        if len(page_groups) <= 1:
            # Try splitting at section breaks (w:sectPr).
            page_groups = []
            current_group = []
            for para in doc.paragraphs:
                current_group.append(para)
                # Check for section properties (page/section break).
                sect_pr = para._element.find(qn("w:pPr"))
                if sect_pr is not None:
                    sect = sect_pr.find(qn("w:sectPr"))
                    if sect is not None:
                        page_groups.append(current_group)
                        current_group = []
            if current_group:
                page_groups.append(current_group)

        # ── Strategy 3: If still no splits, approximate pages by paragraph count ──
        # ~40 paragraphs per "page" (rough heuristic for DOCX from PDF).
        if len(page_groups) <= 1 and len(doc.paragraphs) > 10:
            PARAS_PER_PAGE = 40
            page_groups = []
            for i in range(0, len(doc.paragraphs), PARAS_PER_PAGE):
                page_groups.append(doc.paragraphs[i : i + PARAS_PER_PAGE])

        # ── Strategy 4: Last resort — each paragraph is a "page" ──
        if not page_groups:
            page_groups = [[p] for p in doc.paragraphs]

        new_doc = Document()

        if pages is None:
            selected_groups = page_groups
        else:
            selected_groups = []
            for pg in pages:
                idx = pg - 1
                if 0 <= idx < len(page_groups):
                    selected_groups.append(page_groups[idx])

        # Copy paragraphs to the new document (preserving formatting).
        for group in selected_groups:
            for para in group:
                new_para = new_doc.add_paragraph()
                if para.style and para.style.name:
                    try:
                        new_para.style = new_doc.styles[para.style.name]
                    except Exception:
                        logger.debug("best-effort op failed", exc_info=True)
                for run in para.runs:
                    new_run = new_para.add_run(run.text)
                    if run.bold:
                        new_run.bold = True
                    if run.italic:
                        new_run.italic = True
                    if run.underline:
                        new_run.underline = True
                    if run.font.size:
                        new_run.font.size = run.font.size
                    if run.font.name:
                        new_run.font.name = run.font.name

        # V11.31.1: Also copy tables (DOCX from PDF often has content in tables).
        if pages is None:
            # Copy all tables.
            for table in doc.tables:
                new_table = new_doc.add_table(rows=0, cols=len(table.columns))
                for row in table.rows:
                    new_row = new_table.add_row()
                    for i, cell in enumerate(row.cells):
                        if i < len(new_row.cells):
                            new_row.cells[i].text = cell.text

        out_p = _P(out_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        new_doc.save(str(out_p))
