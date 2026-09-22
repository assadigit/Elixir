"""V0.4.19 — the prompt-bank and quality settings sections.

``AiPromptSection``, ``QUALITY_PRESETS`` and ``AiQualitySection`` moved
VERBATIM from ``ui_qt/settings/sections.py`` during the V0.4.19
de-monolithization — bodies byte-identical; only this docstring and the
re-homed imports are new.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from controller import Controller
from ui_qt.settings.widgets import labeled_checkbox, labeled_spin, make_form
from ui_qt.theme import theme_manager

# ════════════════════════════════════════════════════════════════════════════
# A1: Prompt Bank — user-editable prompt templates
# ════════════════════════════════════════════════════════════════════════════


class AiPromptSection(QGroupBox):
    """Prompt Bank — select and edit summarisation prompt templates."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Prompt bank", parent)
        self.controller = controller
        f = make_form()

        # ── Prompt selector ─────────────────────────────────────────────
        from core.summarisation.prompt_manager import PromptManager

        self._pm = PromptManager()
        self._prompts = self._pm.list_prompts()
        saved_prompt = controller.get_setting("summarisation.prompt", "default")
        if saved_prompt not in self._prompts:
            saved_prompt = "default"

        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(self._prompts)
        idx = self.prompt_combo.findText(saved_prompt)
        if idx >= 0:
            self.prompt_combo.setCurrentIndex(idx)
        self.prompt_combo.currentTextChanged.connect(self._on_prompt_selected)
        f.addRow("Active prompt", self.prompt_combo)

        # ── Prompt editor ───────────────────────────────────────────────
        from PySide6.QtWidgets import QHBoxLayout

        editor_label = QLabel(
            "Edit prompt template (variables: {{heading}}, {{text}}, {{language}})"
        )
        editor_label.setObjectName("Caption")
        f.addRow("", editor_label)

        self.editor = QTextEdit()
        self.editor.setMinimumHeight(280)
        self.editor.setFont(__import__("PySide6").QtGui.QFont("Consolas", 10))
        f.addRow(self.editor)

        # Load the current prompt into the editor
        current = self.prompt_combo.currentText()
        content = self._pm.load_prompt(current)
        if content:
            self.editor.setPlainText(content)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self.save_btn = QPushButton("  Save")
        self.save_btn.setObjectName("Compact")
        self.save_btn.clicked.connect(self._save_prompt)
        btn_row.addWidget(self.save_btn)

        self.new_btn = QPushButton("  New…")
        self.new_btn.setObjectName("Compact")
        self.new_btn.clicked.connect(self._new_prompt)
        btn_row.addWidget(self.new_btn)

        self.delete_btn = QPushButton("  Delete")
        self.delete_btn.setObjectName("Compact")
        self.delete_btn.clicked.connect(self._delete_prompt)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()
        f.addRow("", btn_row)

        # Hint
        hint = QLabel(
            "Prompts are stored in ~/.elixir/prompts/. Changes apply on the next conversion."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def _on_prompt_selected(self, name: str) -> None:
        """Load the selected prompt into the editor."""
        content = self._pm.load_prompt(name)
        if content:
            self.editor.setPlainText(content)

    def _save_prompt(self) -> None:
        """Save the edited prompt to the user directory."""
        name = self.prompt_combo.currentText()
        content = self.editor.toPlainText()
        self._pm.save_prompt(name, content)
        # Update the active prompt in settings
        self.controller.update_setting("summarisation.prompt", name)

    def _new_prompt(self) -> None:
        """Create a new prompt template."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "New Prompt", "Prompt name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        # Start with the default template
        default = self._pm.load_prompt("default") or ""
        self._pm.save_prompt(name, default)
        # Add to combo and select
        if self.prompt_combo.findText(name) < 0:
            self.prompt_combo.addItem(name)
        self.prompt_combo.setCurrentText(name)
        self.editor.setPlainText(default)

    def _delete_prompt(self) -> None:
        """Delete the current prompt (only user-created ones)."""
        name = self.prompt_combo.currentText()
        if name in ("default", "academic", "technical", "creative"):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "Cannot delete", f"'{name}' is a built-in preset and cannot be deleted."
            )
            return
        from PySide6.QtWidgets import QMessageBox

        ret = QMessageBox.question(self, "Delete prompt", f"Delete prompt '{name}'?")
        if ret == QMessageBox.Yes:
            self._pm.delete_prompt(name)
            self.prompt_combo.removeItem(self.prompt_combo.currentIndex())
            # Switch to default
            self.prompt_combo.setCurrentText("default")

    def save(self) -> None:
        """Called when the settings dialog is saved."""
        name = self.prompt_combo.currentText()
        content = self.editor.toPlainText()
        self._pm.save_prompt(name, content)
        self.controller.update_setting("summarisation.prompt", name)

    def reload(self) -> None:
        """Re-read settings."""
        saved = self.controller.get_setting("summarisation.prompt", "default")
        self._prompts = self._pm.list_prompts()
        self.prompt_combo.clear()
        self.prompt_combo.addItems(self._prompts)
        idx = self.prompt_combo.findText(saved)
        if idx >= 0:
            self.prompt_combo.setCurrentIndex(idx)
        content = self._pm.load_prompt(saved)
        if content:
            self.editor.setPlainText(content)

    def set_simple_mode(self, simple: bool) -> None:
        pass  # always visible


QUALITY_PRESETS = {
    "Fast": {"temperature": 0.3, "self_consistency": False},
    "Balanced": {"temperature": 0.2, "self_consistency": False},
    # V7.5.1: was temperature=0.0 — too low for most models (Qwen/Gemma
    # produce empty/degenerate output at t=0).  Raised to 0.1 (minimum safe).
    "Maximum": {"temperature": 0.1, "self_consistency": True},
}


class AiQualitySection(QGroupBox):
    """Quality mode + fine controls + output selection."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Quality & summaries", parent)
        self.controller = controller
        f = make_form()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Fast", "Balanced", "Maximum"])
        self.quality_combo.setCurrentText(
            controller.get_setting("summarisation.quality_mode", "Balanced")
        )
        self.quality_combo.currentTextChanged.connect(self._apply_preset)
        f.addRow("Preset", self.quality_combo)

        from PySide6.QtWidgets import QSlider

        temp_row = QHBoxLayout()
        temp_row.setContentsMargins(0, 0, 0, 0)
        temp_row.setSpacing(8)
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 70)
        self.temp_slider.setValue(
            int(controller.get_setting("summarisation.temperature", 0.2) * 100)
        )
        self.temp_slider.setToolTip(
            "Sampling temperature.\n\n"
            "• 0.0 — deterministic, but many models (Qwen, Gemma, Llama) produce\n"
            "  degenerate or empty output at exactly 0. Use ≥ 0.1.\n"
            "• 0.2–0.4 — recommended for factual summaries.\n"
            "• 0.6–0.8 — more creative (podcast scripts)."
        )
        self.temp_entry = QLineEdit(f"{self.temp_slider.value() / 100:.2f}")
        self.temp_entry.setMaximumWidth(56)
        self.temp_entry.setAlignment(Qt.AlignCenter)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_entry.setText(f"{v / 100:.2f}"))
        # V7.5.1: live warning label when temperature < 0.1
        self.temp_warn_label = QLabel("")
        self.temp_warn_label.setObjectName("Caption")
        self.temp_slider.valueChanged.connect(self._check_temp_warning)
        self.temp_entry.editingFinished.connect(self._on_temp_entry)
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_entry)
        temp_row.addWidget(self.temp_warn_label)
        f.addRow("Temperature", temp_row)
        self._check_temp_warning(self.temp_slider.value())

        self.coverage_spin = labeled_spin(
            int(controller.get_setting("summarisation.coverage_threshold", 50)),
            minimum=30,
            maximum=90,
            suffix="%",
        )
        f.addRow("Coverage threshold", self.coverage_spin)
        # V15.1.0: Over-delivery — keep improving coverage past minimum threshold
        self.overdeliver_cb = labeled_checkbox(
            "📈 Over-deliver: keep gap-filling past minimum threshold toward target",
            checked=controller.get_setting("summarisation.overdeliver_enabled", True),
        )
        self.overdeliver_target_spin = labeled_spin(
            int(controller.get_setting("summarisation.overdeliver_target", 100)),
            minimum=85,
            maximum=100,
            suffix="%",
        )
        self.overdeliver_target_spin.setToolTip(
            "V15.1.1: Target coverage when over-delivery is enabled. Default 100% "
            "(the more the better). The pipeline keeps gap-filling until this target "
            "is reached (or no more concepts to fill). Must be >= coverage threshold."
        )
        f.addRow("Over-deliver target", self.overdeliver_target_spin)
        f.addRow("", self.overdeliver_cb)
        # V15.1.1: B3 voting toggle (disabled by default — damages depth)
        self.b3_voting_cb = labeled_checkbox(
            "🔄 B3 multi-sample voting (EXPERIMENTAL — disabled by default. "
            "Consensus voting dilutes conceptual depth. Enable to experiment.)",
            checked=controller.get_setting("summarisation.b3_voting_enabled", False),
        )
        f.addRow("", self.b3_voting_cb)
        self.self_consist_cb = labeled_checkbox(
            "Enable self-consistency (3× slower, more robust)",
            checked=controller.get_setting("summarisation.self_consistency", False),
        )
        self.academic_cb = labeled_checkbox(
            "🔬 Academic Rigor (temp 0, self-review, structured JSON)",
            checked=controller.get_setting("summarisation.academic_rigor", False),
        )
        # V0.03 (P0-1): dropped-letter auto-repair toggle — OFF by default
        # (the V0.02 rig run corrupted 12/13 valid paraphrase words). When
        # enabled, repairs require the English-lexicon guard + paragraph
        # corroboration + strict single-candidate uniqueness.
        self.dropped_letter_repair_cb = labeled_checkbox(
            "🔤 Garble Auto-Repair (guarded — OFF until rig-validated)",
            checked=controller.get_setting("summarisation.dropped_letter_auto_repair", False),
        )
        self.dropped_letter_repair_cb.setToolTip(
            "V0.03: auto-repairs non-word garbles ('emergs'→'emerges').\n\n"
            "DISABLED by default — the V0.02 rig run showed 12 of 13\n"
            "auto-repairs corrupted valid words ('contrast'→'contract',\n"
            "'teams'→'beams'). When enabled, a repair additionally\n"
            "requires: the token is NOT a valid English dictionary word,\n"
            "the candidate appears in a topically-matching source\n"
            "paragraph, and it is the ONLY edit-distance-1 candidate.\n\n"
            "Flags (log-only) always run regardless of this setting."
        )
        # V10.1.0: Source Grounding (langextract) — Layer 8 anti-hallucination.
        self.grounding_cb = labeled_checkbox(
            "🛡️ Source Grounding (langextract — verbatim claim verification). "
            "Requires `pip install langextract`.",
            checked=controller.get_setting("grounding.enabled", False),
        )
        self.grounding_cb.setToolTip(
            "Layer 8 of the anti-hallucination defense.\n\n"
            "When enabled, Google's langextract library extracts every\n"
            "factual claim from the source text with a verbatim character\n"
            "span (char_interval).  Claims that can't be located verbatim\n"
            "are flagged as potential hallucinations — a deterministic,\n"
            "binary signal stronger than the existing semantic similarity\n"
            "checks (Layers 1-7).\n\n"
            "Falls back gracefully to Layers 1-7 if langextract is missing\n"
            "or the backend is unreachable (with a loud warning in the log)."
        )
        # Backend selector (Ollama default / Cloud optional)
        self.grounding_backend = QComboBox()
        self.grounding_backend.addItems(["ollama", "cloud"])
        self.grounding_backend.setCurrentText(controller.get_setting("grounding.backend", "ollama"))
        self.grounding_backend.setToolTip(
            "Ollama (default): local, free, no API key. Matches the\n"
            "overnight-run reliability goal. Gets verbatim grounding but\n"
            "NOT schema-constrained output.\n\n"
            "Cloud: OpenAI-compatible endpoint (9Router / OpenRouter / OpenAI).\n"
            "Gets schema-constrained output where supported. Adds latency\n"
            "and cost. Use for maximum-rigor scientific articles."
        )
        # V10.1.6: Manual GPU thermal profile override.
        # Some Zotac cards report "NVIDIA GeForce RTX 3060" (no brand name)
        # to nvidia-smi, so auto-detection fails.  This dropdown lets the
        # user force the Zotac emergency profile manually.
        self.gpu_profile_combo = QComboBox()
        self.gpu_profile_combo.addItems(
            [
                "auto — detect from GPU name",
                "zotac_3060 — Zotac RTX 3060 Twin Edge (EMERGENCY)",
                "zotac_3060_ti — Zotac RTX 3060 Ti Twin Edge (EMERGENCY)",
                "zotac_3070 — Zotac RTX 3070 Twin Edge (EMERGENCY)",
                "generic — Standard NVIDIA (83°C/88°C)",
            ]
        )
        _current_override = controller.get_setting("hardware.gpu_profile_override", "auto")
        _override_idx = {
            "auto": 0,
            "zotac_3060": 1,
            "zotac_3060_ti": 2,
            "zotac_3070": 3,
            "generic": 4,
        }.get(_current_override, 0)
        self.gpu_profile_combo.setCurrentIndex(_override_idx)
        self.gpu_profile_combo.setToolTip(
            "GPU thermal profile override.\n\n"
            "Use this if your Zotac card is detected as 'NVIDIA GeForce RTX 3060' "
            "(without the 'ZOTAC' brand name) — nvidia-smi sometimes doesn't "
            "report the board partner name on Zotac cards.\n\n"
            "Setting this to 'Zotac RTX 3060 Twin Edge (EMERGENCY)' forces:\n"
            "  • Warning at 72°C (not 83°C)\n"
            "  • Critical auto-pause at 80°C (not 88°C)\n"
            "  • max_workers locked to 1 (VRAM protection)\n"
            "  • Mandatory 20-min cool-down cycles\n"
            "  • Emergency mode warnings in the log\n\n"
            "Leave on 'auto' if your card is correctly detected."
        )
        self.simplified_cb = labeled_checkbox(
            "📝 Generate Simplified Keypoints (jargon-free digest)",
            checked=controller.get_setting("summarisation.simplified_keypoints_enabled", False),
        )
        self.filter_cb = labeled_checkbox(
            "Enable content filter (skip TOC, index, blank pages)",
            checked=controller.get_setting("content_filter.enabled", True),
        )
        f.addRow(self.self_consist_cb)
        f.addRow(self.academic_cb)
        f.addRow(self.dropped_letter_repair_cb)  # V0.03 (P0-1)
        f.addRow("🛡️ Grounding backend", self.grounding_backend)
        f.addRow("🌡️ GPU thermal profile", self.gpu_profile_combo)
        f.addRow(self.grounding_cb)
        f.addRow(self.simplified_cb)
        f.addRow(self.filter_cb)
        self.setLayout(f)

    def _apply_preset(self, mode: str) -> None:
        p = QUALITY_PRESETS.get(mode)
        if not p:
            return
        self.temp_slider.setValue(int(p["temperature"] * 100))
        self.temp_entry.setText(f"{p['temperature']:.2f}")
        self.self_consist_cb.setChecked(p["self_consistency"])
        self.controller.update_setting("summarisation.quality_mode", mode)

    def _on_temp_entry(self) -> None:
        try:
            v = float(self.temp_entry.text())
            if 0.0 <= v <= 0.7:
                self.temp_slider.setValue(int(v * 100))
                return
        except ValueError:
            pass
        self.temp_entry.setText(f"{self.temp_slider.value() / 100:.2f}")

    # V7.5.1: live temperature warning — many models produce degenerate
    # output at t=0.  Mirrors the wizard's _check_temp_warning.
    def _check_temp_warning(self, value: int) -> None:
        t = value / 100.0
        p = theme_manager.palette
        if t < 0.1:
            self.temp_warn_label.setText("⚠️ t=0 → empty/repetitive output — use ≥ 0.1")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.warning}; background: transparent; font-size: 10px;"
            )
        elif t < 0.2:
            self.temp_warn_label.setText("low — ok for deterministic models")
            self.temp_warn_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 10px;"
            )
        else:
            self.temp_warn_label.setText("")

    def save(self) -> None:
        c = self.controller
        c.update_setting("summarisation.quality_mode", self.quality_combo.currentText())
        c.update_setting("summarisation.temperature", self.temp_slider.value() / 100)
        c.update_setting("summarisation.coverage_threshold", self.coverage_spin.value())
        # V15.1.0: over-delivery settings
        c.update_setting("summarisation.overdeliver_enabled", self.overdeliver_cb.isChecked())
        _od_target = self.overdeliver_target_spin.value()
        # Ensure target >= threshold
        if _od_target < self.coverage_spin.value():
            _od_target = self.coverage_spin.value()
            self.overdeliver_target_spin.setValue(int(_od_target))
        c.update_setting("summarisation.overdeliver_target", _od_target)
        c.update_setting("summarisation.b3_voting_enabled", self.b3_voting_cb.isChecked())
        c.update_setting("summarisation.self_consistency", self.self_consist_cb.isChecked())
        c.update_setting("summarisation.academic_rigor", self.academic_cb.isChecked())
        # V0.03 (P0-1): dropped-letter repair toggle
        c.update_setting(
            "summarisation.dropped_letter_auto_repair", self.dropped_letter_repair_cb.isChecked()
        )
        # V10.1.0: grounding settings
        c.update_setting("grounding.enabled", self.grounding_cb.isChecked())
        c.update_setting("grounding.backend", self.grounding_backend.currentText())
        # V10.1.6: GPU thermal profile override
        _override_keys = ["auto", "zotac_3060", "zotac_3060_ti", "zotac_3070", "generic"]
        _idx = self.gpu_profile_combo.currentIndex()
        _override_val = _override_keys[_idx] if 0 <= _idx < len(_override_keys) else "auto"
        c.update_setting("hardware.gpu_profile_override", _override_val)
        c.update_setting(
            "summarisation.simplified_keypoints_enabled", self.simplified_cb.isChecked()
        )
        c.update_setting("content_filter.enabled", self.filter_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        self.quality_combo.setCurrentText(c.get_setting("summarisation.quality_mode", "Balanced"))
        self.temp_slider.setValue(int(c.get_setting("summarisation.temperature", 0.2) * 100))
        self.temp_entry.setText(f"{self.temp_slider.value() / 100:.2f}")
        self.coverage_spin.setValue(int(c.get_setting("summarisation.coverage_threshold", 50)))
        # V15.1.0: over-delivery settings
        self.overdeliver_cb.setChecked(c.get_setting("summarisation.overdeliver_enabled", True))
        self.overdeliver_target_spin.setValue(
            int(c.get_setting("summarisation.overdeliver_target", 100))
        )
        self.b3_voting_cb.setChecked(c.get_setting("summarisation.b3_voting_enabled", False))
        self.self_consist_cb.setChecked(c.get_setting("summarisation.self_consistency", False))
        self.academic_cb.setChecked(c.get_setting("summarisation.academic_rigor", False))
        # V0.03 (P0-1): dropped-letter repair toggle
        self.dropped_letter_repair_cb.setChecked(
            c.get_setting("summarisation.dropped_letter_auto_repair", False)
        )
        # V10.1.0: grounding settings
        self.grounding_cb.setChecked(c.get_setting("grounding.enabled", False))
        self.grounding_backend.setCurrentText(c.get_setting("grounding.backend", "ollama"))
        # V10.1.6: GPU thermal profile override
        _current_override = c.get_setting("hardware.gpu_profile_override", "auto")
        _override_idx = {
            "auto": 0,
            "zotac_3060": 1,
            "zotac_3060_ti": 2,
            "zotac_3070": 3,
            "generic": 4,
        }.get(_current_override, 0)
        self.gpu_profile_combo.setCurrentIndex(_override_idx)
        self.simplified_cb.setChecked(
            c.get_setting("summarisation.simplified_keypoints_enabled", False)
        )
        self.filter_cb.setChecked(c.get_setting("content_filter.enabled", True))
