"""Step 6: Translation Settings — Step6Translation (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step6Translation
(back-compat facade).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui_qt.settings.translation_page import _TRANSLATABLE_OUTPUTS
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 6: Translation Settings
# ════════════════════════════════════════════════════════════════════════════

class Step6Translation(WizardStep):
    """Translation settings: backend, harakat, outputs."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Translation (EN ↔ FA)")
        title.setObjectName("H2")
        lay.addWidget(title)

        self.enable_cb = QCheckBox("Translate selected outputs after conversion")
        self.enable_cb.setChecked(self.state.translation_enabled)
        self.enable_cb.stateChanged.connect(self._on_enable_changed)
        lay.addWidget(self.enable_cb)

        # Settings container
        self.settings_widget = QWidget()
        settings_lay = QVBoxLayout(self.settings_widget)
        settings_lay.setContentsMargins(0, 8, 0, 0)
        settings_lay.setSpacing(8)

        # Backend
        settings_lay.addWidget(QLabel("Translator backend:"))
        self.backend_combo = QComboBox()
        # V13.31.0 (#13): NLLB removed from the UI. Only TranslateGemma
        # (Ollama) is exposed.
        self.backend_combo.addItem("📝 Ollama LLM (TranslateGemma)", "ollama")
        backend_current = self.state.translation_backend or self.controller.get_setting("translation.backend", "ollama")
        # V13.31.0 (#13): legacy "nllb" backends fall back to "ollama" in UI
        if backend_current == "nllb":
            backend_current = "ollama"
        idx = self.backend_combo.findData(backend_current)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        settings_lay.addWidget(self.backend_combo)

        # Target language
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        lang_row.addWidget(QLabel("Target language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Farsi / Persian (fa)", "fa")
        self.lang_combo.addItem("English (en)", "en")
        idx = self.lang_combo.findData(self.state.translation_target_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        settings_lay.addLayout(lang_row)

        # Harakat model
        try:
            models = self.controller.list_ollama_models()
        except Exception:
            models = []
        settings_lay.addWidget(QLabel("Harakat model (Farsi TTS diacritics — always Ollama):"))
        self.harakat_combo = QComboBox()
        for m in models:
            self.harakat_combo.addItem("📝 " + m, m)
        current_harakat = self.state.translation_harakat_model or self.controller.get_setting("translation.harakat_model", "")
        if current_harakat:
            idx = self.harakat_combo.findData(current_harakat)
            if idx >= 0:
                self.harakat_combo.setCurrentIndex(idx)
        settings_lay.addWidget(self.harakat_combo)

        # Judge model
        settings_lay.addWidget(QLabel("Judge model (validation — empty = use summarization model):"))
        self.judge_combo = QComboBox()
        self.judge_combo.addItem("  (use summarization model)", "")
        for m in models:
            self.judge_combo.addItem("📝 " + m, m)
        current_judge = self.state.translation_judge_model or self.controller.get_setting("translation.judge_model", "")
        if current_judge:
            idx = self.judge_combo.findData(current_judge)
            if idx >= 0:
                self.judge_combo.setCurrentIndex(idx)
        settings_lay.addWidget(self.judge_combo)

        # Per-output translation selection
        settings_lay.addWidget(QLabel("Which outputs to translate:"))
        self._tr_cbs: dict[str, QCheckBox] = {}
        for key, label, subtitle in _TRANSLATABLE_OUTPUTS:
            cb = QCheckBox(f"{label}  —  {subtitle}")
            cb.setChecked(self.state.translation_outputs.get(key, False))
            settings_lay.addWidget(cb)
            self._tr_cbs[key] = cb

        lay.addWidget(self.settings_widget)
        lay.addStretch()

        self._on_enable_changed()

    def _on_enable_changed(self) -> None:
        self.settings_widget.setEnabled(self.enable_cb.isChecked())

    def save_to_state(self) -> None:
        self.state.translation_enabled = self.enable_cb.isChecked()
        self.state.translation_backend = self.backend_combo.currentData()
        self.state.translation_target_lang = self.lang_combo.currentData()
        self.state.translation_harakat_model = self.harakat_combo.currentData() or ""
        self.state.translation_judge_model = self.judge_combo.currentData() or ""
        for key, cb in self._tr_cbs.items():
            self.state.translation_outputs[key] = cb.isChecked()
