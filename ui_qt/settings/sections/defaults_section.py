"""V0.4.19 — DefaultsSection (default engines/models for service dialogs).

The V11.19 default-engines section moved VERBATIM from
``ui_qt/settings/sections.py`` during the V0.4.19 de-monolithization —
body byte-identical; only this docstring and the re-homed imports (the
badge / async model helpers via ``.helpers``) are new.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QPushButton, QWidget

from controller import Controller
from ui_qt.components.icons import icon
from ui_qt.settings.widgets import labeled_checkbox, make_form

from .helpers import _badge, _get_ollama_models, _refresh_models_async

# ════════════════════════════════════════════════════════════════════════════
# V11.19: Default Engines section — central place to pick the default
# model/engine/format for each standalone service dialog.
# ════════════════════════════════════════════════════════════════════════════


class DefaultsSection(QGroupBox):
    """Default engines/models/formats for the standalone service dialogs.

    Each tool's dialog (Summarize, OCR, PDF→MD, TTS, Translation) shows a
    "Default (change in Settings)" option that, when selected, reads from
    the ``quick_services.defaults`` settings block configured here.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Default engines & models", parent)
        self.controller = controller
        f = make_form()

        # ── Summarization ──────────────────────────────────────────────
        summ_lbl = QLabel("Summarization Service")
        summ_lbl.setObjectName("SectionTitle")
        f.addRow("", summ_lbl)

        self.summ_model_combo = QComboBox()
        self.summ_model_combo.setEditable(True)
        self.summ_model_combo.setMinimumWidth(300)
        self.summ_model_combo.setToolTip(
            "The default model used by the Summarization Service when "
            "'Default Model' is selected. Leave empty to use the main "
            "summarisation.model setting."
        )
        f.addRow("Default LLM model", self.summ_model_combo)

        self.summ_quality_combo = QComboBox()
        self.summ_quality_combo.addItem("Fast", "fast")
        self.summ_quality_combo.addItem("Standard", "standard")
        self.summ_quality_combo.addItem("Thorough", "thorough")
        f.addRow("Default quality", self.summ_quality_combo)

        self.summ_format_combo = QComboBox()
        self.summ_format_combo.addItem("Markdown (.md)", ".md")
        self.summ_format_combo.addItem("Word document (.docx)", ".docx")
        self.summ_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.summ_format_combo)

        self.summ_obsidian_cb = labeled_checkbox(
            "Obsidian-style markdown by default",
            checked=controller.get_setting("quick_services.defaults.summarize_obsidian", False),
            tooltip="Wrap summaries in YAML front-matter + Obsidian callouts.",
        )
        f.addRow(self.summ_obsidian_cb)

        # ── OCR ────────────────────────────────────────────────────────
        ocr_lbl = QLabel("OCR Service")
        ocr_lbl.setObjectName("SectionTitle")
        f.addRow("", ocr_lbl)

        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItem("Auto (cascade)", "auto")
        self.ocr_engine_combo.addItem("pypdf (digital PDFs)", "pypdf")
        self.ocr_engine_combo.addItem("Ollama Vision (OlmOCR/Qwen)", "ollama")
        self.ocr_engine_combo.addItem("Local VLM (llava)", "vlm")
        self.ocr_engine_combo.addItem("Tesseract", "tesseract")
        f.addRow("Default engine", self.ocr_engine_combo)

        self.ocr_model_combo = QComboBox()
        self.ocr_model_combo.setEditable(True)
        self.ocr_model_combo.setToolTip(
            "The default OCR model. Leave empty to use ocr.primary_model."
        )
        f.addRow("Default OCR model", self.ocr_model_combo)

        self.ocr_format_combo = QComboBox()
        self.ocr_format_combo.addItem("Markdown (.md)", ".md")
        self.ocr_format_combo.addItem("Plain text (.txt)", ".txt")
        self.ocr_format_combo.addItem("Word document (.docx)", ".docx")
        self.ocr_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.ocr_format_combo)

        # ── PDF → Markdown ─────────────────────────────────────────────
        pdf_lbl = QLabel("PDF → Markdown")
        pdf_lbl.setObjectName("SectionTitle")
        f.addRow("", pdf_lbl)

        self.pdf_format_combo = QComboBox()
        self.pdf_format_combo.addItem("Markdown (.md)", ".md")
        self.pdf_format_combo.addItem("Word document (.docx)", ".docx")
        self.pdf_format_combo.addItem("PDF (.pdf)", ".pdf")
        f.addRow("Default output format", self.pdf_format_combo)

        # ── TTS ────────────────────────────────────────────────────────
        tts_lbl = QLabel("TTS Service")
        tts_lbl.setObjectName("SectionTitle")
        f.addRow("", tts_lbl)

        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItem("Default (use tts.en_engine)", "")
        self.tts_engine_combo.addItem("Piper", "piper")
        self.tts_engine_combo.addItem("NeuTTS", "neutts")
        self.tts_engine_combo.addItem("Coqui XTTS v2", "coqui")
        f.addRow("Default engine", self.tts_engine_combo)

        # ── Translation ────────────────────────────────────────────────
        tr_lbl = QLabel("Translation Service")
        tr_lbl.setObjectName("SectionTitle")
        f.addRow("", tr_lbl)

        self.tr_backend_combo = QComboBox()
        self.tr_backend_combo.addItem("Default (use translation.backend)", "")
        # V13.31.0 (#13): NLLB backend removed from the UI. Only the
        # TranslateGemma (Ollama) backend is exposed.
        self.tr_backend_combo.addItem("Ollama (TranslateGemma)", "ollama")
        f.addRow("Default backend", self.tr_backend_combo)

        # ── Refresh button ─────────────────────────────────────────────
        # V18.20.4.5 (W-b11): stored on self so the async refresh can
        # disable/re-enable it while a fetch is in flight.
        self.refresh_btn = QPushButton("  Refresh Ollama models")
        self.refresh_btn.setIcon(icon("refresh", "#B8915A", 15))
        self.refresh_btn.clicked.connect(self._refresh_models)
        f.addRow("", self.refresh_btn)

        hint = QLabel(
            "These defaults are used by the standalone service dialogs (Tools → "
            "Summarize / OCR / PDF→Markdown / TTS / Translation). Each dialog "
            'shows a "Default (change in Settings)" option that, when selected, '
            "reads from this page."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)
        self._reload_widget_values()
        # V18.20.4.5 (W-b11): worker ref for the async model fetch (a
        # Python ref keeps the SimpleWorker QObject alive mid-run).
        self._models_worker = None
        self._refresh_models()

    def _reload_widget_values(self) -> None:
        """Load the saved settings into the widgets (non-model ones)."""
        c = self.controller
        # Quality
        q = c.get_setting("quick_services.defaults.summarize_quality", "standard")
        idx = self.summ_quality_combo.findData(q)
        if idx >= 0:
            self.summ_quality_combo.setCurrentIndex(idx)
        # Summarize format
        sf = c.get_setting("quick_services.defaults.summarize_format", ".md")
        idx = self.summ_format_combo.findData(sf)
        if idx >= 0:
            self.summ_format_combo.setCurrentIndex(idx)
        # OCR engine
        oe = c.get_setting("quick_services.defaults.ocr_engine", "auto")
        idx = self.ocr_engine_combo.findData(oe)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)
        # OCR format
        of = c.get_setting("quick_services.defaults.ocr_format", ".md")
        idx = self.ocr_format_combo.findData(of)
        if idx >= 0:
            self.ocr_format_combo.setCurrentIndex(idx)
        # PDF format
        pf = c.get_setting("quick_services.defaults.pdf_format", ".md")
        idx = self.pdf_format_combo.findData(pf)
        if idx >= 0:
            self.pdf_format_combo.setCurrentIndex(idx)
        # TTS engine
        te = c.get_setting("quick_services.defaults.tts_engine", "")
        idx = self.tts_engine_combo.findData(te)
        if idx >= 0:
            self.tts_engine_combo.setCurrentIndex(idx)
        # Translation backend
        tb = c.get_setting("quick_services.defaults.translation_backend", "")
        idx = self.tr_backend_combo.findData(tb)
        if idx >= 0:
            self.tr_backend_combo.setCurrentIndex(idx)

    def _refresh_models(self) -> None:
        """V18.20.4.5 (W-b11): fetch on a background worker — the 5s-timeout
        DependencyChecker HTTP call used to run ON the UI thread here, so
        opening Settings froze the app for up to 5s when Ollama was down.
        Populate happens on the main thread in _on_models_loaded; the
        fetch fn is widget-free (pure HTTP)."""
        controller = self.controller  # snapshot on the main thread
        _refresh_models_async(
            self, lambda: _get_ollama_models(controller), self._on_models_loaded, self.refresh_btn
        )

    def _on_models_loaded(self, models: list) -> None:
        """W-b11: worker finished — populate the model combos (MAIN thread)."""
        c = self.controller

        # Summarize model — has a "use main setting" empty option
        summ_current = c.get_setting("quick_services.defaults.summarize_model", "")
        summ_current_text = self.summ_model_combo.currentText().strip()
        self.summ_model_combo.clear()
        self.summ_model_combo.addItem("Default (use summarisation.model)", "")
        for m in models:
            self.summ_model_combo.addItem(_badge(m) + m, m)
        # Restore selection: saved setting → previously-typed text → first item
        target = summ_current or summ_current_text
        if target:
            idx = self.summ_model_combo.findData(target)
            if idx >= 0:
                self.summ_model_combo.setCurrentIndex(idx)
            else:
                self.summ_model_combo.setEditText(target)

        # OCR model — has a "use primary_model" empty option
        ocr_current = c.get_setting("quick_services.defaults.ocr_model", "")
        ocr_current_text = self.ocr_model_combo.currentText().strip()
        self.ocr_model_combo.clear()
        self.ocr_model_combo.addItem("Default (use ocr.primary_model)", "")
        for m in models:
            self.ocr_model_combo.addItem(_badge(m) + m, m)
        target = ocr_current or ocr_current_text
        if target:
            idx = self.ocr_model_combo.findData(target)
            if idx >= 0:
                self.ocr_model_combo.setCurrentIndex(idx)
            else:
                self.ocr_model_combo.setEditText(target)

    def save(self) -> None:
        c = self.controller
        c.update_setting(
            "quick_services.defaults.summarize_model", self.summ_model_combo.currentData() or ""
        )
        c.update_setting(
            "quick_services.defaults.summarize_quality",
            self.summ_quality_combo.currentData() or "standard",
        )
        c.update_setting(
            "quick_services.defaults.summarize_format",
            self.summ_format_combo.currentData() or ".md",
        )
        c.update_setting(
            "quick_services.defaults.summarize_obsidian", self.summ_obsidian_cb.isChecked()
        )
        c.update_setting(
            "quick_services.defaults.ocr_engine", self.ocr_engine_combo.currentData() or "auto"
        )
        c.update_setting(
            "quick_services.defaults.ocr_model", self.ocr_model_combo.currentData() or ""
        )
        c.update_setting(
            "quick_services.defaults.ocr_format", self.ocr_format_combo.currentData() or ".md"
        )
        c.update_setting(
            "quick_services.defaults.pdf_format", self.pdf_format_combo.currentData() or ".md"
        )
        c.update_setting(
            "quick_services.defaults.tts_engine", self.tts_engine_combo.currentData() or ""
        )
        c.update_setting(
            "quick_services.defaults.translation_backend", self.tr_backend_combo.currentData() or ""
        )

    def reload(self) -> None:
        self._reload_widget_values()
        self._refresh_models()
        self.summ_obsidian_cb.setChecked(
            self.controller.get_setting("quick_services.defaults.summarize_obsidian", False)
        )
