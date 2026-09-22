"""V0.4.19 — the OCR settings sections.

``OcrEngineSection``, ``OcrModelSection`` and ``OcrFiguresSection`` moved
VERBATIM from ``ui_qt/settings/sections.py`` during the V0.4.19
de-monolithization — bodies byte-identical; only this docstring and the
re-homed imports (the async model helpers via ``.helpers``) are new.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QLineEdit, QPushButton, QWidget

from controller import Controller
from ui_qt.components.icons import icon
from ui_qt.settings.widgets import labeled_checkbox, labeled_combo, make_form

from .helpers import _get_ollama_models, _populate_models, _refresh_models_async

# ════════════════════════════════════════════════════════════════════════════
# OCR sections
# ════════════════════════════════════════════════════════════════════════════


class OcrEngineSection(QGroupBox):
    """OCR engine toggles + timeout."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("OCR engine", parent)
        self.controller = controller
        f = make_form()
        self.llm_cb = labeled_checkbox(
            "Enable LLM OCR for scanned pages",
            checked=controller.get_setting("ocr.use_llm", True),
            tooltip="Use a vision LLM for scanned pages. Tesseract is the fallback.",
        )
        self.auto_cb = labeled_checkbox(
            "Auto-detect scanned pages",
            checked=controller.get_setting("ocr.auto_detect_scanned", True),
            tooltip="Only OCR pages with little extractable text.",
        )
        self.force_cb = labeled_checkbox(
            "Force OCR on every page",
            checked=controller.get_setting("ocr.force_ocr_all_pages", False),
            tooltip="Run OCR on all pages, even digital ones. Slower.",
        )
        self.paddle_cb = labeled_checkbox(
            "Enable PaddleOCR fallback",
            checked=controller.get_setting("ocr.use_paddleocr", False),
            tooltip="Try PaddleOCR before Tesseract if the vision model fails.",
        )
        f.addRow(self.llm_cb)
        f.addRow(self.auto_cb)
        f.addRow(self.force_cb)
        f.addRow(self.paddle_cb)
        self.timeout_combo = labeled_combo(
            ["30", "60", "90", "120", "180"],
            str(controller.get_setting("ocr.timeout", 60)),
            tooltip="Per-page OCR timeout in seconds.",
        )
        f.addRow("OCR timeout (s)", self.timeout_combo)
        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("ocr.use_llm", self.llm_cb.isChecked())
        c.update_setting("ocr.auto_detect_scanned", self.auto_cb.isChecked())
        c.update_setting("ocr.force_ocr_all_pages", self.force_cb.isChecked())
        c.update_setting("ocr.use_paddleocr", self.paddle_cb.isChecked())
        c.update_setting("ocr.timeout", int(self.timeout_combo.currentText()))

    def reload(self) -> None:
        c = self.controller
        self.llm_cb.setChecked(c.get_setting("ocr.use_llm", True))
        self.auto_cb.setChecked(c.get_setting("ocr.auto_detect_scanned", True))
        self.force_cb.setChecked(c.get_setting("ocr.force_ocr_all_pages", False))
        self.paddle_cb.setChecked(c.get_setting("ocr.use_paddleocr", False))
        to = str(c.get_setting("ocr.timeout", 60))
        idx = self.timeout_combo.findText(to)
        if idx >= 0:
            self.timeout_combo.setCurrentIndex(idx)


class OcrModelSection(QGroupBox):
    """Primary + fallback OCR model pickers — shows ALL Ollama models, badges
    them, and preselects the first model whose name contains 'ocr'."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("OCR models", parent)
        self.controller = controller
        f = make_form()
        self.primary_combo = QComboBox()
        self.fallback_combo = QComboBox()
        f.addRow("Primary model", self.primary_combo)
        f.addRow("Fallback model", self.fallback_combo)
        # V10.36.0: VLM fallback model for hard-to-OCR pages
        self.vlm_fallback_edit = QLineEdit(controller.get_setting("ocr.vlm_fallback_model", ""))
        self.vlm_fallback_edit.setPlaceholderText("e.g. llava:13b (leave empty to disable)")
        f.addRow("VLM fallback (local)", self.vlm_fallback_edit)
        _vlm_hint = QLabel(
            "When OlmOCR returns <50 chars on a page, this local VLM model "
            "is tried before Tesseract. Best for complex layouts / handwriting."
        )
        _vlm_hint.setObjectName("Caption")
        _vlm_hint.setWordWrap(True)
        f.addRow("", _vlm_hint)
        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)
        hint = QLabel(
            "All installed Ollama models are listed. Models with “ocr”, "
            "“vl”, or “vision” in the name are badged 🔍 and an OCR model "
            "is pre-selected automatically."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)
        self.setLayout(f)
        # V18.20.4.5 (W-b11): worker ref for the async model fetch (a
        # Python ref keeps the SimpleWorker QObject alive mid-run).
        self._models_worker = None
        self._refresh_models()

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — the 5s-timeout
        DependencyChecker HTTP call used to run ON the UI thread here, so
        opening Settings (or clicking Refresh) froze the app for up to 5s
        when Ollama was down. Populate happens on the main thread in
        _on_models_loaded; the fetch fn is widget-free (pure HTTP)."""
        controller = self.controller  # snapshot on the main thread
        _refresh_models_async(
            self, lambda: _get_ollama_models(controller), self._on_models_loaded, self.refresh_btn
        )

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate both combos (MAIN thread)."""
        _populate_models(
            self.primary_combo,
            models,
            current=self.controller.get_setting("ocr.primary_model", ""),
            prefer_ocr=True,
        )
        _populate_models(
            self.fallback_combo,
            models,
            current=self.controller.get_setting("ocr.fallback_model", ""),
            prefer_ocr=True,
        )

    def save(self) -> None:
        self.controller.update_setting("ocr.primary_model", self.primary_combo.currentData() or "")
        self.controller.update_setting(
            "ocr.fallback_model", self.fallback_combo.currentData() or ""
        )
        # V10.36.0: VLM fallback model (local VLM for hard-to-OCR pages)
        self.controller.update_setting(
            "ocr.vlm_fallback_model", self.vlm_fallback_edit.text().strip()
        )

    def reload(self) -> None:
        self._refresh_models()
        self.vlm_fallback_edit.setText(self.controller.get_setting("ocr.vlm_fallback_model", ""))


class OcrFiguresSection(QGroupBox):
    """Figure-text extraction + TOC vision OCR."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Figures & TOC", parent)
        self.controller = controller
        f = make_form()
        self.figures_cb = labeled_checkbox(
            "Extract text from figures (Vision OCR)",
            checked=controller.get_setting("advanced.extract_figure_text", False),
            tooltip="Detect images and OCR visible text/labels/numbers from them.",
        )
        self.toc_vision_cb = labeled_checkbox(
            "Use vision model for TOC extraction (slower, more accurate)",
            checked=controller.get_setting("advanced.toc_vision_ocr", False),
            tooltip="Render TOC page(s) as images and pass to the vision model.",
        )
        f.addRow(self.figures_cb)
        f.addRow(self.toc_vision_cb)
        self.setLayout(f)

    def save(self) -> None:
        self.controller.update_setting("advanced.extract_figure_text", self.figures_cb.isChecked())
        self.controller.update_setting("advanced.toc_vision_ocr", self.toc_vision_cb.isChecked())

    def reload(self) -> None:
        self.figures_cb.setChecked(
            self.controller.get_setting("advanced.extract_figure_text", False)
        )
        self.toc_vision_cb.setChecked(self.controller.get_setting("advanced.toc_vision_ocr", False))
