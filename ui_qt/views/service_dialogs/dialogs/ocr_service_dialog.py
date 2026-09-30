"""OCR Service dialog (V18.20.4.6, P5 / O-b2 split).

OcrServiceDialog moved VERBATIM from
ui_qt/views/service_dialogs/base_dialog.py — only this module's
top-of-file imports differ. ui_qt.views.service_dialogs.base_dialog
re-exports it (back-compat facade).

V0.6.10 (B17): the dialog migrated onto the shared BaseServiceDialog
(the tts/translation precedent) — __init__ delegates the common
skeleton (title, options container, output row, progress, status,
buttons) to the base with accept_files=False/accept_text=False (the
multi-file queue is an option row, not the base's single-file input).
The closeEvent override STAYS (the TTS preview-worker pattern): it
guards the extra test worker first, then delegates the main batch
worker to the base guard. The W-b5 worker flow
(_do_convert → _ocr_work → _on_convert_*) and every engine backend
stay as-is."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt

# V13.20.1: Master fix — import ALL QtWidgets so subagent edits that use
# any widget class (QTableWidget, QSpinBox, QRadioButton, QCheckBox, etc.)
# never hit NameError. This is the root-cause fix for the recurring
# "QPlainTextEdit is not defined" / "QTableWidget is not defined" errors.
from PySide6.QtWidgets import *  # noqa: F401,F403 — intentional wildcard
from PySide6.QtWidgets import (
    QFileDialog,
    QWidget,
)

from controller import Controller
from core.llm.model_taxonomy import VISION_MODEL_KEYWORDS
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.views.service_dialogs.dialogs.shared import (
    BaseServiceDialog,
    _confirm_close_with_running_worker,
    _show_success_modal,
)

logger = logging.getLogger(__name__)


class OcrServiceDialog(BaseServiceDialog):
    """V11: Standalone OCR Service — pick files → choose engine → Convert → done.

    V13.26.0 (P1.3): Now delegates to core OCR modules instead of duplicating:
    - ``QwenOCREngine._call_ollama_vision()`` for Ollama vision OCR (proper prompt,
      proper timeout, proxy-proof via safe_ollama_request pattern)
    - ``summarisation.endpoint`` for the Ollama URL (was ``ocr.ollama_url``)
    - Core OCR prompt (was a different, shorter prompt)

    Supports batch: add multiple files, each gets its own output.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None):
        # V0.6.10 (B17): dialog-specific state FIRST — the base __init__
        # calls _build_ui → _build_options, which creates the file-queue
        # row + engine combos. The typed _worker init stays verbatim — the
        # W-b5 re-entrancy guard in _do_convert depends on it.
        self._files: list = []
        # V18.20.4.5 (W-b5/T-b2): the background OCR worker (SimpleWorker).
        self._worker: SimpleWorker | None = None
        # V0.4.5: cache of Ollama OCR models discovered via /api/tags.
        self._ollama_ocr_models: list[str] = []
        # V0.6.10 (B17): accept_files=False/accept_text=False — the base
        # builds NO input section (the multi-file queue + engine rows are
        # this dialog's options; the base's single-file row does not fit
        # the batch shape).
        super().__init__(
            controller, "🔍 OCR Service", parent, accept_files=False, accept_text=False
        )
        self.setMinimumSize(560, 360)
        # V0.6.10 (B17): the base builds out_path_edit / process_btn with
        # its own labels; this dialog's historical attribute names
        # (out_edit / action_btn — pinned by the e2e drive tests) are
        # restored as aliases of the SAME widgets (single source of truth).
        self.out_edit = self.out_path_edit
        self.out_edit.setPlaceholderText("Choose where to save output files…")
        self.action_btn = self.process_btn
        self.action_btn.setText("Convert")
        # V0.4.5: bigger status label (RichText HTML progress) — the base's
        # plain Caption label gains the original formatting back.
        self.status_label.setMinimumHeight(40)
        self.status_label.setTextFormat(Qt.RichText)
        self.progress_bar.setFixedHeight(8)
        # V0.6.10 (B17): the base's live-log toggle + panel exist but this
        # dialog never streams log lines (its _on_convert_progress only
        # sets status text) — hide the dead toggle.
        self._log_toggle_btn.setVisible(False)

    def _build_options(self, layout) -> None:
        """V0.6.10 (B17): the OCR-specific rows, folded into the base's
        options container — the multi-file queue, the engine selector +
        hint, the format row + stylize hint, the Test OCR box and the
        Advanced button (the base already built the output row)."""
        from PySide6.QtWidgets import (
            QComboBox as _QCB,
        )
        from PySide6.QtWidgets import (
            QGroupBox as _QGroupBox,
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
        layout.addLayout(file_row)

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
        self.engine_combo.addItem("Auto (recommended) — picks the best engine per file", "auto")
        self.engine_combo.addItem("Tesseract (lightweight, fast, offline)", "tesseract")
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
        layout.addLayout(engine_row)

        # V0.4.5: one-line hint below the engine dropdown — explains what
        # the selected engine does, so the user doesn't have to guess.
        self.engine_hint = _QL("")
        self.engine_hint.setObjectName("Caption")
        self.engine_hint.setWordWrap(True)
        self.engine_hint.setStyleSheet(
            "color: var(--muted-foreground); margin-left: 60px; margin-top: -4px;"
        )
        layout.addWidget(self.engine_hint)
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
        self.fmt_combo.addItem("Stylized Markdown (.md) — Obsidian atomic notes", ".stylized.md")
        self.fmt_combo.addItem("Plain text (.txt)", ".txt")
        self.fmt_combo.addItem("Word document (.docx)", ".docx")
        self.fmt_combo.addItem("PDF (.pdf)", ".pdf")
        self.fmt_combo.setCurrentIndex(0)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # V0.4.10: hint for the Stylized Markdown option.
        self.stylize_hint = _QL(
            "💡 Stylized Markdown runs a second LLM pass on the OCR'd text to "
            "structure it into Obsidian-style atomic notes with YAML frontmatter, "
            "#tags, > [!note] callouts, and [[wikilinks]]. Uses your main "
            "summarization model (not the OCR model)."
        )
        self.stylize_hint.setObjectName("Caption")
        self.stylize_hint.setWordWrap(True)
        self.stylize_hint.setStyleSheet(
            "color: var(--muted-foreground); margin-left: 60px; margin-top: -4px;"
        )
        self.stylize_hint.setVisible(False)
        layout.addWidget(self.stylize_hint)
        # Show/hide the hint based on the selected format.
        self.fmt_combo.currentIndexChanged.connect(self._update_stylize_hint)
        _QTimer.singleShot(0, self._update_stylize_hint)

        # ── V0.4.8: Test OCR section — lets the user verify the selected
        # engine works before running a full conversion. Uses a bundled
        # test image (assets/ocr_test_sample.png) so the user doesn't need
        # to find their own file. Shows the extracted text inline.
        test_box = _QGroupBox("Test OCR engine")
        test_lay = _VL(test_box)
        test_lay.setContentsMargins(12, 8, 12, 8)
        test_lay.setSpacing(6)

        test_desc = _QL(
            'Click "Test OCR" to verify the selected engine can read text '
            "from a built-in sample image. This confirms your OCR setup "
            "(Ollama model / Tesseract) is working before you convert real files."
        )
        test_desc.setWordWrap(True)
        test_desc.setObjectName("Caption")
        test_lay.addWidget(test_desc)

        test_btn_row = _HL()
        test_btn_row.setSpacing(8)
        test_btn_row.addStretch()
        self.test_btn = _QPB("🧪 Test OCR")
        self.test_btn.setObjectName("Compact")
        self.test_btn.clicked.connect(self._on_test_ocr)
        test_btn_row.addWidget(self.test_btn)
        test_lay.addLayout(test_btn_row)

        # Result display — shows the extracted text after the test runs.
        self.test_result_label = _QL("")
        self.test_result_label.setWordWrap(True)
        self.test_result_label.setTextFormat(Qt.RichText)
        self.test_result_label.setStyleSheet(
            "padding: 8px; background: rgba(0,0,0,0.03); border-radius: 4px; "
            "font-family: monospace; font-size: 11px; max-height: 120px;"
        )
        self.test_result_label.setVisible(False)
        test_lay.addWidget(self.test_result_label)

        layout.addWidget(test_box)

        # ── V0.4.8: Advanced — now a MODAL dialog (not an expander).
        # The V0.4.5 expander had a layout bug (the screenshot 5454.png
        # showed labels overlapping with input fields). A modal dialog
        # is cleaner and matches the user's request: "clicking on advanced
        # setting must open a new modal inside ocr tool."
        adv_btn_row = _HL()
        adv_btn_row.addStretch()
        self.advanced_btn = _QPB("⚙ Advanced…")
        self.advanced_btn.setObjectName("Compact")
        self.advanced_btn.setToolTip(
            "Open the Advanced settings dialog (legacy engines + page range)"
        )
        self.advanced_btn.clicked.connect(self._open_advanced_modal)
        adv_btn_row.addWidget(self.advanced_btn)
        layout.addLayout(adv_btn_row)

        # V0.4.8: the page-range + legacy-engine state lives on self
        # (set by the Advanced modal) so the main dialog can read it
        # during _do_convert.
        self.range_edit = _QLE()
        self.range_edit.setText("all")
        self.legacy_engine_combo = _QCB()
        self.legacy_engine_combo.addItem("(use the main Engine dropdown above)", "__default__")
        self.legacy_engine_combo.addItem("pypdf (fast, digital PDFs only)", "pypdf")
        self.legacy_engine_combo.addItem(
            "Local VLM — llava/minicpm (better for infographics)", "vlm"
        )
        self.legacy_engine_combo.setCurrentIndex(0)

    # ── V0.4.5: Ollama OCR model auto-detection ───────────────────────────

    # OCR-related name keywords — a model is considered an OCR model if
    # its name (case-insensitive) contains any of these. Content-agnostic:
    # the list is the canonical set of OCR/vision model family names, not
    # hardcoded specific model versions.
    #
    # V0.6.7 (review-loop B4): the list is now a DIRECT reference to the
    # model_taxonomy SSOT (the union of the 3 keyword variants that had
    # drifted apart across the tree) — this dialog gains olmo/mmproj/
    # multimodal/bonsai detection and can never drift from the badge /
    # dependencies / llamacpp classifications again.
    _OCR_KEYWORDS = VISION_MODEL_KEYWORDS

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
            base_url = (
                s.get("summarisation.endpoint", "http://localhost:11434")
                or "http://localhost:11434"
            )
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
            hint = f"💡 Uses the Ollama vision model '{data}' for OCR. Good for scanned docs and images."
        else:
            hint = hints.get(data, "")
        self.engine_hint.setText(hint)

    def _update_stylize_hint(self) -> None:
        """V0.4.10: show/hide the Stylized Markdown hint based on format."""
        data = self.fmt_combo.currentData() if self.fmt_combo else ""
        self.stylize_hint.setVisible(data == ".stylized.md")

    def closeEvent(self, event) -> None:
        # V18.20.4.5 (T-b2): guard against closing while the OCR batch
        # worker runs — the "QThread: Destroyed while thread is still
        # running" abort class. Ask; on "close anyway" detach the worker
        # so the per-file loop's result is discarded, not crashed on.
        # V0.6.10 (B17): migrated onto BaseServiceDialog — the TTS
        # preview-worker pattern: this override guards the EXTRA test
        # worker (V0.4.8) first, then delegates the main batch worker
        # (self._worker) to the base class's guard via super().
        test_worker = getattr(self, "_test_worker", None)
        if not _confirm_close_with_running_worker(self, test_worker):
            event.ignore()
            return
        super().closeEvent(event)  # BaseServiceDialog guards self._worker

    # ── V0.4.8: Advanced modal + Test OCR ─────────────────────────────────

    def _open_advanced_modal(self) -> None:
        """V0.4.8: open the Advanced settings as a modal dialog.

        The V0.4.5 design used an inline expander, but the screenshot
        5454.png showed a layout bug (labels overlapping with input
        fields). A modal dialog is cleaner + matches the user's request:
        "clicking on advanced setting must open a new modal inside ocr
        tool."

        The modal edits self.range_edit + self.legacy_engine_combo in
        place (they're already created on self but hidden). The modal
        just shows them in a clean dialog layout.
        """
        from PySide6.QtWidgets import (
            QDialog as _QDialog,
        )
        from PySide6.QtWidgets import (
            QDialogButtonBox as _QDialogButtonBox,
        )
        from PySide6.QtWidgets import (
            QFormLayout as _QFormLayout,
        )
        from PySide6.QtWidgets import (
            QLabel as _QLabel,
        )
        from PySide6.QtWidgets import (
            QVBoxLayout as _QVBoxLayout,
        )

        dlg = _QDialog(self)
        dlg.setWindowTitle("Advanced OCR settings")
        dlg.setMinimumWidth(420)
        dlg_lay = _QVBoxLayout(dlg)
        dlg_lay.setContentsMargins(16, 12, 16, 12)
        dlg_lay.setSpacing(10)

        # Title + description
        title = _QLabel("⚙ Advanced OCR settings")
        title.setObjectName("H2")
        dlg_lay.addWidget(title)
        desc = _QLabel(
            "These settings are for advanced users. Most conversions work "
            "fine with the defaults (Auto engine + all pages)."
        )
        desc.setWordWrap(True)
        desc.setObjectName("Caption")
        dlg_lay.addWidget(desc)

        # Form layout for the two controls
        form = _QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 8, 0, 8)

        # Legacy engine
        form.addRow("Legacy engine:", self.legacy_engine_combo)
        legacy_hint = _QLabel(
            "Overrides the main Engine dropdown. Use only if you "
            "specifically need pypdf or a local VLM."
        )
        legacy_hint.setWordWrap(True)
        legacy_hint.setObjectName("Caption")
        form.addRow("", legacy_hint)

        # Page range
        form.addRow("Page range:", self.range_edit)
        range_hint = _QLabel(
            'PDFs only — e.g. "1-10" for pages 1–10, "1,3,5" for specific pages, "all" for every page.'
        )
        range_hint.setWordWrap(True)
        range_hint.setObjectName("Caption")
        form.addRow("", range_hint)

        dlg_lay.addLayout(form)

        # Buttons
        btn_box = _QDialogButtonBox(_QDialogButtonBox.Ok | _QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        dlg_lay.addWidget(btn_box)

        # V0.4.8: the range_edit + legacy_engine_combo are reparented
        # to the dialog while it's open, then reparented back to self
        # (hidden) on close. This keeps their state on self so
        # _do_convert can read them. We use a try/finally to ensure
        # reparenting back even if the user cancels.
        # (V0.4.19: the captured original parents were never used — the
        # finally reparents to `self` directly — dead locals removed.)
        try:
            dlg.exec()
        finally:
            # Reparent back to self (hidden) so the state persists.
            self.range_edit.setParent(self)
            self.legacy_engine_combo.setParent(self)

    def _on_test_ocr(self) -> None:
        """V0.4.8: run a quick OCR test on the bundled sample image to
        verify the selected engine works.

        Uses assets/ocr_test_sample.png (a 400x200 image with clear text)
        so the user doesn't need to find their own file. Shows the
        extracted text inline so the user can confirm the engine is
        reading correctly.

        Runs on a background worker (the Ollama/Tesseract call can
        take 5-30s) so the UI stays responsive.
        """
        from pathlib import Path as _P

        # Resolve the bundled test image path.
        # The image is shipped at assets/ocr_test_sample.png relative to
        # the repo root. We try a few candidate paths to be robust.
        candidates = [
            _P(__file__).resolve().parent.parent.parent.parent.parent
            / "assets"
            / "ocr_test_sample.png",
            _P(__file__).resolve().parent.parent.parent.parent / "assets" / "ocr_test_sample.png",
            _P.cwd() / "assets" / "ocr_test_sample.png",
        ]
        test_image = None
        for c in candidates:
            if c.exists():
                test_image = c
                break
        if test_image is None:
            self.test_result_label.setText(
                "❌ <b>Test image not found.</b> Expected at assets/ocr_test_sample.png"
            )
            self.test_result_label.setVisible(True)
            return

        # Disable the Test button + show "Running…" state.
        self.test_btn.setEnabled(False)
        self.test_btn.setText("🧪 Testing…")
        self.test_result_label.setText("⏳ <i>Running OCR on the sample image…</i>")
        self.test_result_label.setVisible(True)

        # Snapshot the engine choice on the main thread (the worker
        # reads it via the closure).
        engine = self.engine_combo.currentData()
        legacy_engine = self.legacy_engine_combo.currentData()
        if legacy_engine and legacy_engine != "__default__":
            engine = legacy_engine
        elif not engine:
            engine = "auto"

        # V0.4.8: persist the selected Ollama model name (same as
        # _do_convert does) so _ocr_ollama picks it up.
        if engine and engine not in ("auto", "tesseract", "pypdf", "vlm"):
            from utils.settings import Settings as _S

            _s = _S()
            _s.set("ocr.primary_model", engine)

        # Build the worker callable. It reads the test image bytes,
        # runs the same _ocr_ollama / _ocr_tesseract dispatch as
        # _ocr_work, and returns the extracted text.
        test_path = test_image

        def _do_test():
            path = test_path
            try:
                if engine == "tesseract":
                    return self._ocr_tesseract(path, pages=None)
                elif engine == "pypdf":
                    return "⚠️ pypdf only works on PDFs, not images. Pick a different engine for the test."
                elif engine == "vlm":
                    return self._ocr_ollama(path, vlm=True, pages=None)
                elif engine and engine not in ("auto", "tesseract", "pypdf", "vlm"):
                    # Ollama model name
                    return self._ocr_ollama(path, vlm=False, pages=None)
                else:
                    # auto — for an image, skip pypdf and go straight to Ollama/Tesseract
                    try:
                        text = self._ocr_ollama(path, vlm=False, pages=None)
                        if text and len(text.strip()) > 5:
                            return text
                    except Exception:
                        pass
                    return self._ocr_tesseract(path, pages=None)
            except Exception as e:
                return f"❌ {type(e).__name__}: {e}"

        # Reuse the SimpleWorker pattern from _do_convert.
        self._test_worker = SimpleWorker(_do_test)
        self._test_worker.finished.connect(self._on_test_finished)
        self._test_worker.failed.connect(self._on_test_failed)
        self._test_worker.start()

    def _on_test_finished(self, result) -> None:
        """V0.4.8: test worker finished — show the extracted text."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🧪 Test OCR")
        text = (result or "").strip()
        if not text:
            self.test_result_label.setText(
                "⚠️ <b>No text extracted.</b> The engine returned empty output. "
                "Try a different engine or check that the model is installed."
            )
        else:
            # Escape HTML special chars + show in a monospace block.
            import html as _html

            escaped = _html.escape(text)
            char_count = len(text)
            self.test_result_label.setText(
                f"✅ <b>OCR successful</b> ({char_count} chars):<br>"
                f'<pre style="margin:4px 0 0 0; white-space:pre-wrap;">{escaped}</pre>'
            )
        self.test_result_label.setVisible(True)

    def _on_test_failed(self, err: str) -> None:
        """V0.4.8: test worker raised — show the error."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🧪 Test OCR")
        import html as _html

        self.test_result_label.setText(f"❌ <b>Test failed:</b> {_html.escape(err)}")
        self.test_result_label.setVisible(True)

    def _pick_output(self):
        # V0.6.10 (B17): was _pick_output_folder — renamed to OVERRIDE the
        # base's file-save _pick_output (the base's output-row Browse button
        # connects to it). OCR outputs go to a FOLDER (one file per input),
        # so the folder picker stays (the B17 fold-in keeps it custom).
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

    def _on_process(self) -> None:
        # V0.6.10 (B17): the base wired the (aliased) action_btn to
        # _on_process; this dialog's dispatch is the _on_action chain
        # (Close-vs-Convert → _do_convert's W-b5 worker spawn).
        self._on_action()

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

        V0.6.0 (4-c): typographic dashes (en/em/minus — the pasted-from-PDF
        range family) are normalized to ASCII hyphen BEFORE parsing, so
        "2\u20134" now selects pages 2-4 instead of parsing as garbage.
        """
        text = text.strip().lower()
        # V0.6.0 (4-c): dash normalization (en, em, minus, figure dashes).
        for _dash in ("\u2013", "\u2014", "\u2212", "\u2012"):
            text = text.replace(_dash, "-")
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
        # V0.6.0 (4-c): a NON-EMPTY unparseable range ("abc", "0", "5-")
        # parses to None — which _ocr_work reads as EVERY page — so a typo
        # silently OCR'd the whole document. Refuse instead (the same
        # guard the PDF/DOCX Cutter got in V0.6.0).
        if pages is None and page_range_text.strip().lower() not in ("", "all"):
            self.status_label.setText(
                f"⚠️ Couldn't read that page range: \u201c{page_range_text.strip()}\u201d — "
                "use e.g. 1-10, 1,3,5, or all."
            )
            return
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
                    # V0.4.10: if Stylized Markdown is selected, run a second
                    # LLM pass to structure the raw OCR text into Obsidian-
                    # style atomic notes. Uses the main summarisation model
                    # (not the OCR model). Fail-open: if the LLM call fails,
                    # the raw text is written as-is.
                    actual_suffix = suffix
                    actual_text = text
                    if suffix == ".stylized.md":
                        if report is not None:
                            report(
                                int(i * 100 / total) if total else 0,
                                (
                                    f"<div style='font-size:15px; font-weight:600;'>"
                                    f"✨ Stylizing {i + 1}/{total}: <span style='color: var(--primary);'>{path.name}</span>"
                                    f"</div>"
                                    f"<div style='font-size:12px; color: var(--muted-foreground); margin-top:2px;'>"
                                    f"Running second LLM pass to structure into Obsidian atomic notes…"
                                    f"</div>"
                                ),
                            )
                        stylized = self._stylize_text(text, source_name=path.stem)
                        actual_text = stylized
                        actual_suffix = ".md"  # the file extension

                    # V11.18: support .docx / .pdf output via shared formatter
                    if actual_suffix in (".md", ".txt"):
                        out_path = _P(out_folder) / f"{path.stem}_ocr{actual_suffix}"
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_text(actual_text, encoding="utf-8")
                    else:
                        from core.outputs.service_formatters import write_output

                        out_path = _P(out_folder) / f"{path.stem}_ocr{actual_suffix}"
                        write_output(actual_text, out_path, fmt=actual_suffix, title=path.stem)
                    results.append(f"✅ {path.name} → {out_path.name} ({len(actual_text):,} chars)")
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
        from pathlib import Path

        from utils.settings import Settings

        s = Settings()
        tess_cmd = s.get("paths.tesseract", "")
        # V0.6.0 (4-c): resolve the tesseract binary the same way
        # OCRService.__init__ does. The default ``paths.tesseract`` value
        # is the Windows installer path (utils/settings.py:541) — on every
        # other host the image branch below crashes (subprocess can't exec
        # a non-existent path) and the PDF branch pins a broken
        # pytesseract.tesseract_cmd. Fall back to a PATH lookup; fail-open
        # (keep the configured value) when nothing is found.
        if not tess_cmd or not Path(tess_cmd).is_file():
            import shutil as _shutil

            _detected_tess = _shutil.which("tesseract")
            if _detected_tess:
                tess_cmd = _detected_tess

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

    # ── V0.4.10: Stylized Markdown (Obsidian atomic notes) ──────────────────

    _STYLIZE_PROMPT = """You are an expert at structuring raw OCR text into Obsidian-style atomic notes.

Below is the raw text extracted from a document/image by OCR. Your task is to restructure it into a clean, well-organized Obsidian-compatible Markdown note following these rules:

STRUCTURE:
1. Start with YAML frontmatter (---) containing: title, source_type, ocr_date, tags
2. Use a single H1 (#) for the document title (infer from content if not explicit)
3. Use H2 (##) for major sections, H3 (###) for subsections
4. Break dense paragraphs into atomic notes (1-3 sentences each)
5. Use bullet points for lists, numbered lists for sequences
6. Convert tables to Markdown tables (| col | col |)
7. Use > [!note], > [!info], > [!warning], > [!tip] callouts for highlighted text
8. Add [[wikilinks]] around key terms, names, and concepts (3-7 per page max)
9. Add #tags at the bottom for: topic, content_type, source_format
10. Preserve ALL information — do not summarize or omit content

FORMATTING:
- Strip OCR artifacts (garbled characters, page markers like "<!-- page N -->")
- Fix obvious OCR errors (e.g., "rn" → "m", "0" → "O" in words)
- Preserve original language (English, Farsi, etc.)
- Use **bold** for key terms, *italic* for emphasis
- Use `code` blocks for formulas, code, or technical notation

OUTPUT:
- Output ONLY the Markdown note (with frontmatter)
- No commentary, no explanations, no "Here is the structured note:" preamble
- If the text is too short or garbled to structure, output it as-is with a minimal frontmatter

RAW OCR TEXT:
"""

    def _stylize_text(self, raw_text: str, source_name: str = "") -> str:
        """V0.4.10/V0.4.11: send raw OCR text to the main summarization model
        for structuring into Obsidian-style atomic notes.

        V0.4.11: added chunking for long documents. If the raw text exceeds
        ~6000 chars (roughly 1500 tokens), it's split into chunks, each
        stylized separately, and the results are concatenated. This prevents
        the 8192-token output limit from truncating long PDFs.

        Uses the user's configured summarisation model (NOT the OCR model)
        via the Ollama /api/generate endpoint. Content-agnostic — the
        prompt asks for structuring, not summarization, so no content is
        lost. If the LLM call fails, falls back to the raw text (best-
        effort — the user still gets output, just not stylized).

        Args:
            raw_text: the raw OCR-extracted text.
            source_name: the source filename (for the frontmatter title).

        Returns:
            The stylized Markdown text, or the raw text if the LLM call
            fails.
        """
        if not raw_text or len(raw_text.strip()) < 20:
            return raw_text  # too short to bother stylizing

        from utils.network import safe_ollama_request
        from utils.settings import Settings as _S

        try:
            s = _S()
            model = s.get("summarisation.model", "") or s.get("summarisation.primary_model", "")
            if not model:
                logger.warning(
                    "Stylize: no summarisation model configured — returning raw OCR text"
                )
                return raw_text

            ollama_url = s.get("summarisation.endpoint", "http://localhost:11434")
            if ollama_url.endswith("/v1"):
                ollama_url = ollama_url[:-3]
            ollama_url = ollama_url.rstrip("/")

            # V0.4.11: chunk long text. Each chunk is ~5000 chars to
            # leave room for the prompt + the 8192-token output limit.
            # Chunks are split at paragraph boundaries when possible.
            CHUNK_SIZE = 5000
            if len(raw_text) <= CHUNK_SIZE:
                # Short text — single pass (the original V0.4.10 path).
                return self._stylize_chunk(
                    raw_text,
                    source_name,
                    model,
                    ollama_url,
                    safe_ollama_request,
                    is_first=True,
                    is_last=True,
                )
            else:
                # Long text — chunk + multi-pass.
                logger.info(
                    f"Stylize: text is {len(raw_text)} chars — chunking into ~{CHUNK_SIZE}-char blocks"
                )
                chunks = self._split_text_into_chunks(raw_text, CHUNK_SIZE)
                results = []
                for i, chunk in enumerate(chunks):
                    is_first = i == 0
                    is_last = i == len(chunks) - 1
                    logger.info(
                        f"Stylize: processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)"
                    )
                    result = self._stylize_chunk(
                        chunk,
                        source_name,
                        model,
                        ollama_url,
                        safe_ollama_request,
                        is_first=is_first,
                        is_last=is_last,
                    )
                    results.append(result)
                # Concatenate the chunks. If any chunk failed (returned raw),
                # it's included as-is.
                combined = "\n\n---\n\n".join(results)
                return combined

        except Exception as e:
            logger.warning(
                "Stylize failed (non-fatal): %s: %s — returning raw text", type(e).__name__, e
            )
            return raw_text

    def _split_text_into_chunks(self, text: str, chunk_size: int) -> list[str]:
        """V0.4.11: split text into chunks at paragraph boundaries."""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        remaining = text
        while len(remaining) > chunk_size:
            # Find the last paragraph break before chunk_size.
            split_at = remaining.rfind("\n\n", 0, chunk_size)
            if split_at < 0:
                split_at = remaining.rfind("\n", 0, chunk_size)
            if split_at < 0:
                split_at = chunk_size  # hard split
            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            chunks.append(remaining)
        return chunks

    def _stylize_chunk(
        self,
        text: str,
        source_name: str,
        model: str,
        ollama_url: str,
        safe_ollama_request,
        is_first: bool,
        is_last: bool,
    ) -> str:
        """V0.4.11: stylize a single chunk. is_first/is_last control
        whether frontmatter/tags are included (only on first/last chunk)."""
        # For non-first chunks, use a simpler prompt (no frontmatter).
        if is_first:
            prompt = self._STYLIZE_PROMPT + f'\n---\nSource ("{source_name}"):\n\n{text}\n'
        else:
            prompt = (
                "Structure the following OCR text into clean Markdown with headings, "
                "bullet points, callouts, and wikilinks. Do NOT add frontmatter (this "
                "is a continuation chunk). Output ONLY the Markdown.\n\n"
                f'---\nSource ("{source_name}", continuation):\n\n{text}\n'
            )

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "system": "",
            "keep_alive": "30m",
            "options": {"temperature": 0.1, "num_predict": 8192, "top_p": 0.9},
        }
        url = f"{ollama_url}/api/generate"
        resp = safe_ollama_request("POST", url, json=payload, timeout=300)
        stylized = resp.json().get("response", "").strip()
        if stylized and len(stylized) >= 20:
            return stylized
        else:
            logger.warning("Stylize chunk: LLM returned empty — returning raw chunk")
            return text
