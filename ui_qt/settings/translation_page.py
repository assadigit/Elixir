"""V4.7.25: Translation settings page — a top-level head group in Settings.

Tab structure:
  1. **Model** — translator model selector (TranslateGemma-12B default),
     judge model selector, temperature, /no_think toggle, max chunk tokens.
  2. **Languages** — default target language (EN↔FA), auto-detect toggle.
  3. **Validation** — back-translation threshold, judge threshold, max retries.
  4. **Harakat** — harakat (اعراب‌گذاری) toggle for Farsi TTS output.
  5. **Outputs** — per-output translation selection (which of the 11 output
     types to translate when translation is enabled).
  6. **Preview** — live translation test box.

All settings persist under the ``translation.*`` namespace.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controller import Controller
from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.settings.widgets import make_form

# ════════════════════════════════════════════════════════════════════════════
# Model section
# ════════════════════════════════════════════════════════════════════════════


class TranslationModelSection(QGroupBox):
    """Backend selector + translator model + harakat model + judge model.

    V13.31.0 (#13): NLLB backend removed from the UI. Translation is now
    done exclusively by TranslateGemma (Ollama). The NLLB code path remains
    available as a deprecated fallback for users who manually set
    ``translation.backend = "nllb"`` in settings.json.
    """

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Translation models", parent)
        self.controller = controller
        f = make_form()

        # ── Backend selector ──────────────────────────────────────────
        # V13.31.0 (#13): Only "ollama" (TranslateGemma) is exposed in the
        # UI. The legacy "nllb" backend is intentionally omitted here —
        # it remains supported via direct settings.json edits.
        self.backend_combo = QComboBox()
        self.backend_combo.addItem(
            "📝 Ollama TranslateGemma (LLM — can do harakat, higher hallucination risk)",
            "ollama",
        )
        backend_current = controller.get_setting("translation.backend", "ollama")
        # V13.31.0 (#13): if a legacy "nllb" backend is set, fall back to
        # "ollama" in the UI (the underlying value is left untouched in
        # settings.json; a migration in utils/settings.py converts it).
        if backend_current == "nllb":
            backend_current = "ollama"
        idx = self.backend_combo.findData(backend_current)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        f.addRow("Translator backend", self.backend_combo)

        # ── Ollama translator model ────────────────────────────────────
        self.model_combo = QComboBox()
        self._populate_models(
            self.model_combo,
            controller.get_setting("translation.model", "translategemma:4b"),
        )
        f.addRow("Ollama model", self.model_combo)

        # ── Harakat model (always Ollama — needed for Farsi TTS) ──────
        self.harakat_combo = QComboBox()
        self._populate_harakat_models(
            self.harakat_combo,
            controller.get_setting("translation.harakat_model", "translategemma:4b"),
        )
        f.addRow("Harakat model (Farsi TTS diacritics)", self.harakat_combo)

        # ── Judge model (for validation) ──────────────────────────────
        self.judge_combo = QComboBox()
        self.judge_combo.addItem("  (use summarisation model)", "")
        judge_current = controller.get_setting("translation.judge_model", "")
        models = self._list_models()
        for m in models:
            self.judge_combo.addItem("📝 " + m, m)
        if judge_current:
            idx = self.judge_combo.findData(judge_current)
            if idx >= 0:
                self.judge_combo.setCurrentIndex(idx)
        f.addRow("Judge model (validation)", self.judge_combo)

        # ── Temperature ─────────────────────────────────────────────────
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.05)
        self.temp_spin.setDecimals(2)
        self.temp_spin.setValue(float(controller.get_setting("translation.temperature", 0.1)))
        self.temp_spin.setToolTip(
            "Translation temperature (Ollama backend — TranslateGemma).\n\n"
            "• 0.0 — many models produce empty output at exactly 0. Use ≥ 0.1.\n"
            "• 0.1–0.3 — recommended for translation (faithful, not creative).\n"
        )
        f.addRow("Temperature", self.temp_spin)

        # ── Max chunk tokens ─────────────────────────────────────────────
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(500, 8000)
        self.chunk_spin.setSingleStep(500)
        self.chunk_spin.setValue(int(controller.get_setting("translation.max_chunk_tokens", 2000)))
        f.addRow("Max tokens per chunk", self.chunk_spin)

        # ── /no_think toggle ────────────────────────────────────────────
        self.no_think_cb = QCheckBox("Send /no_think directive (prevents <think> blocks)")
        self.no_think_cb.setChecked(bool(controller.get_setting("translation.no_think", True)))
        f.addRow(self.no_think_cb)

        self.setLayout(f)
        # V13.31.0 (#13): only one backend now — no toggling needed.
        self._on_backend_changed()

    def _on_backend_changed(self) -> None:
        """Show/hide model fields based on selected backend.

        V13.31.0 (#13): With only the "ollama" backend exposed in the UI,
        this is now a no-op. Kept for backward-compat (the wizard page
        still calls it) and to support the deprecated "nllb" backend if
        a user manually constructs the combo with both items.
        """
        # No NLLB combo to toggle anymore — nothing to do.
        return

    def _list_models(self) -> list[str]:
        """Get available Ollama models."""
        try:
            return self.controller.list_ollama_models()
        except Exception:
            return []

    def _populate_models(self, combo: QComboBox, current: str) -> None:
        """Fill combo with all Ollama models, selecting ``current``."""
        combo.clear()
        combo.addItem("translategemma:4b (recommended — 2.5GB VRAM)", "translategemma:4b")
        combo.addItem("translategemma:12b (higher quality, 6.5GB VRAM)", "translategemma:12b")
        models = self._list_models()
        for m in models:
            if m in ("translategemma:4b", "translategemma:12b"):
                continue
            combo.addItem("📝 " + m, m)
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _populate_harakat_models(self, combo: QComboBox, current: str) -> None:
        """Fill combo with Ollama models for harakat generation."""
        combo.clear()
        combo.addItem("translategemma:4b (recommended)", "translategemma:4b")
        combo.addItem("translategemma:12b (higher quality)", "translategemma:12b")
        models = self._list_models()
        for m in models:
            if m in ("translategemma:4b", "translategemma:12b"):
                continue
            combo.addItem("📝 " + m, m)
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def save(self) -> None:
        c = self.controller
        c.update_setting("translation.backend", self.backend_combo.currentData())
        # V13.31.0 (#13): nllb_model is no longer user-editable, but we
        # preserve the existing value (if any) so legacy settings.json
        # entries aren't lost. We don't write a new value here.
        c.update_setting("translation.model", self.model_combo.currentData())
        c.update_setting("translation.harakat_model", self.harakat_combo.currentData())
        c.update_setting("translation.judge_model", self.judge_combo.currentData())
        c.update_setting("translation.temperature", self.temp_spin.value())
        c.update_setting("translation.max_chunk_tokens", self.chunk_spin.value())
        c.update_setting("translation.no_think", self.no_think_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        backend = c.get_setting("translation.backend", "ollama")
        # V13.31.0 (#13): legacy "nllb" backends are shown as "ollama" in UI
        if backend == "nllb":
            backend = "ollama"
        idx = self.backend_combo.findData(backend)
        if idx >= 0:
            self.backend_combo.setCurrentIndex(idx)
        current = c.get_setting("translation.model", "translategemma:4b")
        idx = self.model_combo.findData(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        harakat = c.get_setting("translation.harakat_model", "translategemma:4b")
        idx = self.harakat_combo.findData(harakat)
        if idx >= 0:
            self.harakat_combo.setCurrentIndex(idx)
        judge = c.get_setting("translation.judge_model", "")
        idx = self.judge_combo.findData(judge)
        if idx >= 0:
            self.judge_combo.setCurrentIndex(idx)
        self.temp_spin.setValue(float(c.get_setting("translation.temperature", 0.1)))
        self.chunk_spin.setValue(int(c.get_setting("translation.max_chunk_tokens", 2000)))
        self.no_think_cb.setChecked(bool(c.get_setting("translation.no_think", True)))
        self._on_backend_changed()


# ════════════════════════════════════════════════════════════════════════════
# Languages section
# ════════════════════════════════════════════════════════════════════════════


class TranslationLanguagesSection(QGroupBox):
    """Default target language selector."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Languages", parent)
        self.controller = controller
        f = make_form()

        self.target_combo = QComboBox()
        self.target_combo.addItem("🌐 Farsi / Persian (fa)", "fa")
        self.target_combo.addItem("🌐 English (en)", "en")
        current = controller.get_setting("translation.default_target_lang", "fa")
        idx = self.target_combo.findData(current)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        f.addRow("Default target language", self.target_combo)

        # Info label
        info = QLabel(
            "Source language is auto-detected from the text. "
            "If the source is already in the target language, the file is skipped."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10px; color: palette(text-muted); background: transparent;")
        f.addRow(info)

        self.setLayout(f)

    def save(self) -> None:
        self.controller.update_setting(
            "translation.default_target_lang", self.target_combo.currentData()
        )

    def reload(self) -> None:
        current = self.controller.get_setting("translation.default_target_lang", "fa")
        idx = self.target_combo.findData(current)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)


# ════════════════════════════════════════════════════════════════════════════
# Validation section
# ════════════════════════════════════════════════════════════════════════════


class TranslationValidationSection(QGroupBox):
    """Validation settings — back-translation + judge LLM thresholds."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Validation (zero hallucination tolerance)", parent)
        self.controller = controller
        f = make_form()

        self.enabled_cb = QCheckBox(
            "Enable triple-validation (back-translation + semantic similarity + judge LLM)"
        )
        self.enabled_cb.setChecked(
            bool(controller.get_setting("translation.validation_enabled", True))
        )
        f.addRow(self.enabled_cb)

        self.similarity_spin = QDoubleSpinBox()
        self.similarity_spin.setRange(0.0, 1.0)
        self.similarity_spin.setSingleStep(0.05)
        self.similarity_spin.setDecimals(2)
        self.similarity_spin.setValue(
            float(controller.get_setting("translation.back_translation_threshold", 0.6))
        )
        f.addRow("Back-translation similarity threshold", self.similarity_spin)

        self.judge_spin = QDoubleSpinBox()
        self.judge_spin.setRange(0.0, 1.0)
        self.judge_spin.setSingleStep(0.05)
        self.judge_spin.setDecimals(2)
        self.judge_spin.setValue(float(controller.get_setting("translation.judge_threshold", 0.7)))
        f.addRow("Judge LLM faithfulness threshold", self.judge_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 5)
        self.retries_spin.setValue(int(controller.get_setting("translation.max_retries", 1)))
        f.addRow("Max retries for failed chunks", self.retries_spin)

        info = QLabel(
            "Flagged chunks are retried with a stricter prompt. If still failing, "
            "the translation is kept but flagged in the report for manual review. "
            "Output is never blocked."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10px; color: palette(text-muted); background: transparent;")
        f.addRow(info)

        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("translation.validation_enabled", self.enabled_cb.isChecked())
        c.update_setting("translation.back_translation_threshold", self.similarity_spin.value())
        c.update_setting("translation.judge_threshold", self.judge_spin.value())
        c.update_setting("translation.max_retries", self.retries_spin.value())

    def reload(self) -> None:
        c = self.controller
        self.enabled_cb.setChecked(bool(c.get_setting("translation.validation_enabled", True)))
        self.similarity_spin.setValue(
            float(c.get_setting("translation.back_translation_threshold", 0.6))
        )
        self.judge_spin.setValue(float(c.get_setting("translation.judge_threshold", 0.7)))
        self.retries_spin.setValue(int(c.get_setting("translation.max_retries", 1)))


# ════════════════════════════════════════════════════════════════════════════
# Harakat section
# ════════════════════════════════════════════════════════════════════════════


class TranslationHarakatSection(QGroupBox):
    """Harakat (Persian diacritics) settings for TTS-friendly output."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Harakat (اعراب‌گذاری) for Farsi TTS", parent)
        self.controller = controller
        f = make_form()

        self.harakat_cb = QCheckBox("Generate harakat variant for Farsi outputs (.fa.harakat.md)")
        self.harakat_cb.setChecked(
            bool(controller.get_setting("translation.harakat_enabled", True))
        )
        f.addRow(self.harakat_cb)

        self.confident_cb = QCheckBox(
            "Confidence-first: only add harakat where confident (recommended)"
        )
        self.confident_cb.setChecked(
            bool(controller.get_setting("translation.harakat_confident_only", True))
        )
        f.addRow(self.confident_cb)

        info = QLabel(
            "Harakat adds vowel diacritics (فتحه، ضمه، کسره، سکون، تشدید) to "
            "Persian text for accurate TTS pronunciation. The harakat file is "
            "automatically used when generating Farsi podcast audio."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10px; color: palette(text-muted); background: transparent;")
        f.addRow(info)

        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("translation.harakat_enabled", self.harakat_cb.isChecked())
        c.update_setting("translation.harakat_confident_only", self.confident_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.harakat_cb.setChecked(bool(c.get_setting("translation.harakat_enabled", True)))
        self.confident_cb.setChecked(
            bool(c.get_setting("translation.harakat_confident_only", True))
        )


# ════════════════════════════════════════════════════════════════════════════
# Glossary section
# ════════════════════════════════════════════════════════════════════════════


class TranslationGlossarySection(QGroupBox):
    """Glossary (terminology consistency) settings."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Glossary (terminology consistency)", parent)
        self.controller = controller
        f = make_form()

        self.glossary_cb = QCheckBox(
            "Extract and use a terminology glossary (proper nouns, technical terms)"
        )
        self.glossary_cb.setChecked(
            bool(controller.get_setting("translation.glossary_enabled", True))
        )
        f.addRow(self.glossary_cb)

        info = QLabel(
            "The glossary is extracted from the first few chunks and passed as "
            "context to all subsequent chunks. This ensures consistent translation "
            'of names and terms (e.g., "Mark Manson" → "مارک منسون" throughout). '
            "Saved as translation_logs/Book.glossary.json for reuse."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10px; color: palette(text-muted); background: transparent;")
        f.addRow(info)

        self.setLayout(f)

    def save(self) -> None:
        self.controller.update_setting("translation.glossary_enabled", self.glossary_cb.isChecked())

    def reload(self) -> None:
        self.glossary_cb.setChecked(
            bool(self.controller.get_setting("translation.glossary_enabled", True))
        )


# ════════════════════════════════════════════════════════════════════════════
# Output selection section
# ════════════════════════════════════════════════════════════════════════════

# (setting_key, label, subtitle)
_TRANSLATABLE_OUTPUTS = [
    ("full_markdown", "Full book Markdown", "BookName.md + chapters/*.md (large)"),
    ("chapter_summaries", "Chapter summaries", "BookName.summary.md + per-chapter summaries"),
    ("keypoints", "Keypoints", "BookName.keypoints.md"),
    ("simplified_keypoints", "Simplified keypoints", "BookName.simplified_keypoints.md"),
    ("briefing", "Executive briefing", "BookName.briefing.md"),
    ("podcast", "Podcast script", "BookName.podcast.md (+ harakat for TTS)"),
    ("flashcards", "Flashcards", "BookName.flashcards.md"),
    ("obsidian", "Obsidian KB", "obsidian/*.md"),
    ("study_guide", "Study guide", "BookName.study_guide.md"),
    ("social", "Social media pack", "BookName.social.md"),
    ("mindmap", "Mind map", "BookName.mindmap.md"),
]


class TranslationOutputSelectionSection(QGroupBox):
    """Per-output translation selection — which outputs to translate."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Which outputs to translate", parent)
        self.controller = controller
        f = make_form()

        self._checkboxes: dict[str, QCheckBox] = {}
        for key, label, subtitle in _TRANSLATABLE_OUTPUTS:
            cb = QCheckBox(f"{label}  —  {subtitle}")
            cb.setChecked(bool(controller.get_setting(f"translation.outputs.{key}", False)))
            f.addRow(cb)
            self._checkboxes[key] = cb

        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        for key, cb in self._checkboxes.items():
            c.update_setting(f"translation.outputs.{key}", cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        for key, cb in self._checkboxes.items():
            cb.setChecked(bool(c.get_setting(f"translation.outputs.{key}", False)))


# ════════════════════════════════════════════════════════════════════════════
# Preview section
# ════════════════════════════════════════════════════════════════════════════


class TranslationPreviewSection(QGroupBox):
    """Live translation preview — test the translator with custom text."""

    translation_done = Signal(str, str)  # (translated_text, harakat_text)

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Preview", parent)
        self.controller = controller
        self._worker: threading.Thread | None = None

        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        # Input
        lay.addWidget(QLabel("Text to translate:"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Type or paste text here to test translation...")
        self.input_edit.setMaximumHeight(80)
        lay.addWidget(self.input_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.translate_btn = QPushButton("Translate")
        self.translate_btn.setObjectName("Primary")
        self.translate_btn.setCursor(Qt.PointingHandCursor)
        self.translate_btn.clicked.connect(self._on_translate)
        btn_row.addWidget(self.translate_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Output
        lay.addWidget(QLabel("Translation:"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setMaximumHeight(80)
        self.output_edit.setPlaceholderText("Translation will appear here...")
        lay.addWidget(self.output_edit)

        # Harakat output
        self.harakat_label = QLabel("Harakat variant (for TTS):")
        self.harakat_label.setVisible(False)
        lay.addWidget(self.harakat_label)
        self.harakat_edit = QTextEdit()
        self.harakat_edit.setReadOnly(True)
        self.harakat_edit.setMaximumHeight(80)
        self.harakat_edit.setPlaceholderText("Harakat variant will appear here (Farsi only)...")
        self.harakat_edit.setVisible(False)
        lay.addWidget(self.harakat_edit)

        # Connect signal
        self.translation_done.connect(self._on_translation_done)

    def _on_translate(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.translate_btn.setEnabled(False)
        self.output_edit.setPlainText("Translating...")
        self.harakat_label.setVisible(False)
        self.harakat_edit.setVisible(False)

        # Run in background thread
        SimpleWorker(self._translate_worker, text).start()

    def _translate_worker(self, text: str) -> None:
        try:
            from core.translation.service import TranslationService

            service = TranslationService.from_settings()
            if service is None:
                self.translation_done.emit("Error: no translation model configured", "")
                return
            translated = service.translate_text(text)
            harakat_text = ""
            if service.harakat_gen and service.harakat_enabled:
                harakat_text = service.harakat_gen.add_harakat_to_markdown(translated)
            self.translation_done.emit(translated, harakat_text)
        except Exception as e:
            self.translation_done.emit(f"Error: {e}", "")

    def _on_translation_done(self, translated: str, harakat: str) -> None:
        self.output_edit.setPlainText(translated)
        if harakat and harakat != translated:
            self.harakat_label.setVisible(True)
            self.harakat_edit.setVisible(True)
            self.harakat_edit.setPlainText(harakat)
        self.translate_btn.setEnabled(True)

    def save(self) -> None:
        pass  # no settings to save

    def reload(self) -> None:
        pass
