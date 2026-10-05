"""PDF/DOCX Cutter dialog (V18.20.4.6, P5 / O-b2 split).

PdfDocxCutterDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ delegates the common
skeleton (title, file row, options container, output row, progress,
status, buttons) to the base and folds its byte-identical closeEvent
guard away (inherited). The legacy widget names (in_edit / out_edit /
action_btn — pinned by the e2e drive tests) alias the base-built
file_path_edit / out_path_edit / process_btn; the page-range row folds
into _build_options; _pick_input / _on_action renamed onto the base
hooks the base's Browse/Process buttons already call (_pick_file /
_on_process). The W-b5 worker launch keeps its pinned shape: _do_cut
spawns the SimpleWorker (the base's _process/_collect_options flow
does not fit the cutter's pinned result-dict contract)."""

from __future__ import annotations

import logging

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    _show_success_modal,
)

logger = logging.getLogger(__name__)


class PdfDocxCutterDialog(BaseServiceDialog):
    """V11.30: PDF/DOCX Cutter — extract a range of pages from a PDF or DOCX
    and save the output in the same format.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options (the page-range row), which
        # needs nothing pre-set. The base also initializes self._worker
        # (its closeEvent guards it).
        super().__init__(
            controller, "✂ PDF/DOCX Cutter", parent, accept_files=True, accept_text=False
        )
        # V0.6.10 (B17): this dialog's original geometry over the base's
        # generic 560×480.
        self.setMinimumSize(520, 280)
        # V0.6.10 (B17): the base builds file_path_edit / out_path_edit /
        # process_btn ("Process"); this dialog's historical attribute names
        # (in_edit / out_edit / action_btn — pinned by the e2e drive tests)
        # and labels are restored as aliases of the SAME widgets (single
        # source of truth).
        self.in_edit = self.file_path_edit
        self.in_edit.setPlaceholderText("Pick a .pdf or .docx file…")
        self.out_edit = self.out_path_edit
        self.out_edit.setPlaceholderText("Choose where to save the cut file…")
        self.action_btn = self.process_btn
        self.action_btn.setText("Cut")
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (its _on_cut_progress override
        # only sets status text) — hide the dead toggle (the transcribe
        # B17 precedent).
        self._log_toggle_btn.setVisible(False)

    def _build_options(self, layout: QVBoxLayout) -> None:
        """V0.6.10 (B17): the cutter's only option row — the page range —
        folded into the base's options container (between the base's
        file row and its output row)."""
        range_row = QHBoxLayout()
        range_row.setSpacing(8)
        range_row.addWidget(QLabel("Pages:"))
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("e.g. 1-10, 1,3,5, or 'all'")
        self.range_edit.setText("all")
        self.range_edit.setMinimumWidth(200)
        range_row.addWidget(self.range_edit, 1)
        range_hint = QLabel("💡 1-indexed page numbers")
        range_hint.setObjectName("Caption")
        range_row.addWidget(range_hint)
        layout.addLayout(range_row)

    # V0.6.10 (B17): the closeEvent guard (identical to the base's —
    # _confirm_close_with_running_worker(self, self._worker)) is now
    # INHERITED from BaseServiceDialog; the pre-B17 copy was
    # byte-equivalent and was deleted.

    def _pick_file(self) -> None:
        # V0.6.10 (B17): override of the base's input-row Browse hook (was
        # _pick_input; renamed onto the hook the base's Browse button
        # already calls) — the cutter's document filter + the V11.31
        # {stem}-cut{ext} default output. Body unchanged.
        from pathlib import Path as _P

        path, _ = QFileDialog.getOpenFileName(
            self, "Pick a file", "", "Documents (*.pdf *.docx);;All files (*.*)"
        )
        if path:
            self.in_edit.setText(path)
            p = _P(path)
            # V11.31: default filename = {stem}-cut{ext} in source location.
            self.out_edit.setText(str(p.parent / f"{p.stem}-cut{p.suffix}"))

    def _pick_output(self) -> None:
        # V0.6.10 (B17): override of the base's output-row Browse hook —
        # the PDF/Word filter follows the INPUT's extension (extra
        # behavior the base's generic suffix picker does not have); the
        # extension now routes through the _get_output_suffix hook.
        ext = self._get_output_suffix()
        filter_str = f"{'PDF' if ext == '.pdf' else 'Word'} (*{ext});;All files (*.*)"
        path, _ = QFileDialog.getSaveFileName(self, "Save cut file as", "", filter_str)
        if path:
            if not path.endswith(ext):
                path += ext
            self.out_edit.setText(path)

    def _get_output_suffix(self) -> str:
        # V0.6.10 (B17): base-class hook — the cut keeps the INPUT's format,
        # so the suffix is the picked file's extension (.pdf before any
        # file is picked, as the pre-B17 _pick_output did).
        from pathlib import Path as _P

        in_path = self.in_edit.text().strip()
        return _P(in_path).suffix if in_path else ".pdf"

    def _get_service_name(self) -> str:
        # V0.6.10 (B17): base-class identity hook. This dialog persists no
        # controller settings (grep: zero controller.update_setting /
        # controller.get_setting calls), so the name is identity-only.
        return "pdf_docx_cutter"

    def _on_process(self) -> None:
        # V0.6.10 (B17): the base Process button (aliased as action_btn)
        # drives the old _on_action behavior — Close accepts the dialog,
        # otherwise cut. (Renamed onto the base hook; body unchanged.)
        if self.action_btn.text() == "Close":
            self.accept()
            return
        self._do_cut()

    @staticmethod
    def _parse_range(text: str) -> list[int] | None:
        # V0.6.0 (campaign C1): normalize typographic dashes (en/em/minus)
        # to ASCII hyphens BEFORE splitting — a range pasted from a PDF/TOC
        # ("2–4") previously failed every int() parse, returned None, and
        # the cut silently produced the WHOLE document. Punctuation-class
        # normalization only (Rule 1 clean).
        text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
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
        range_text = self.range_edit.text().strip()
        pages = self._parse_range(range_text)
        # V0.6.0 (campaign C1): a NON-EMPTY, non-"all" range that parses to
        # None (garbage, "0", "5-") used to silently cut the WHOLE document —
        # now the user is told and nothing runs. Empty/"all" still means all.
        if pages is None and range_text and range_text.strip().lower() != "all":
            self.status_label.setText(
                "⚠️ Couldn't read that page range — use e.g. 1-10, 1,3,5, or 'all'."
            )
            return
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
            added = 0
            for pg in pages:
                idx = pg - 1
                if 0 <= idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
                    added += 1
            # V0.6.0 (campaign C2): a range entirely beyond the page count
            # used to write a 0-page PDF and report success — now it errors
            # through the standard worker error path (nothing is written).
            if added == 0:
                raise ValueError(
                    f"no pages matched the range (document has {len(reader.pages)} pages)"
                )
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
            # V0.6.0 (campaign C2): same no-match guard as the PDF path —
            # an out-of-range DOCX selection errors instead of silently
            # saving an empty document.
            if not selected_groups:
                raise ValueError(
                    f"no pages matched the range (document has {len(page_groups)} pages)"
                )

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
