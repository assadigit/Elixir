"""Step 7: Advanced Settings — Step7Advanced (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step7Advanced
(back-compat facade).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 7: Advanced Settings
# ════════════════════════════════════════════════════════════════════════════


class Step7Advanced(WizardStep):
    """Advanced: segmentation, token limit, semantic, academic rigor."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Advanced settings")
        title.setObjectName("H2")
        lay.addWidget(title)

        box = QGroupBox("Segmentation & quality")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(10, 10, 10, 8)
        box_lay.setSpacing(6)

        # Strategy
        strat_row = QHBoxLayout()
        strat_row.setSpacing(8)
        self.strat_combo = QComboBox()
        self.strat_combo.addItems(["auto", "heading", "semantic", "token"])
        self.strat_combo.setCurrentText(self.state.segment_strategy)
        self.strat_combo.setToolTip(
            "auto: Chapter-Level → TOC → Heading → Semantic → Token (recommended)\n"
            "heading: Split at markdown headings (#, ##)\n"
            "semantic: Split by semantic similarity (LLM-based)\n"
            "token: Split at fixed token intervals (last resort)"
        )
        strat_row.addWidget(QLabel("Strategy:"))
        strat_row.addWidget(self.strat_combo)
        strat_row.addStretch()
        box_lay.addLayout(strat_row)

        # V13.35.0: Strategy description (updates on selection change)
        _STRAT_DESC = {
            "auto": "Automatically selects the best strategy: Chapter-Level (if the PDF has outlines) → TOC → Heading → Semantic → Token. Recommended for most books.",
            "heading": "Splits at markdown headings (#, ##). Best for well-structured documents with a clear heading hierarchy.",
            "semantic": "Splits by semantic similarity between paragraphs using LLM-based boundary detection. Best for unstructured text without clear headings. Slower.",
            "token": "Splits at fixed token intervals. Guarantees segments fit the context window but may break mid-topic. Use as a last resort.",
        }
        self.strat_desc_label = QLabel(_STRAT_DESC.get(self.state.segment_strategy, ""))
        self.strat_desc_label.setWordWrap(True)
        self.strat_desc_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        box_lay.addWidget(self.strat_desc_label)
        self.strat_combo.currentTextChanged.connect(
            lambda txt: self.strat_desc_label.setText(_STRAT_DESC.get(txt, ""))
        )

        # Token limit
        tok_row = QHBoxLayout()
        tok_row.setSpacing(8)
        self.token_spin = QSpinBox()
        self.token_spin.setRange(500, 32000)  # V13.35.0: widened from 8000 to match settings dialog
        self.token_spin.setSingleStep(500)
        self.token_spin.setValue(self.state.token_limit)
        self.token_spin.setToolTip(
            "Maximum tokens per segment.\n"
            "• Smaller values (500-1500): more LLM calls, but each segment fits comfortably in the context window.\n"
            "• Larger values (2000-8000): fewer calls, but risk of truncation on long chapters.\n"
            "• Default 2000 works for most models with 32k context.\n"
            "• For Gemma 4 12B (32k context, ~10.9 GB VRAM), 1500-2000 is optimal."
        )
        tok_row.addWidget(QLabel("Token limit per segment:"))
        tok_row.addWidget(self.token_spin)
        tok_row.addStretch()
        box_lay.addLayout(tok_row)

        # Semantic
        self.semantic_cb = QCheckBox("Enable semantic segmentation (LLM-based boundaries)")
        self.semantic_cb.setChecked(self.state.enable_semantic)
        box_lay.addWidget(self.semantic_cb)

        # Academic rigor
        self.rigor_cb = QCheckBox("Academic rigor (temperature=0, self-review, structured JSON)")
        self.rigor_cb.setChecked(self.state.academic_rigor)
        box_lay.addWidget(self.rigor_cb)

        # V10.28.0 (Sprint 1): Conservative drop mode — keep every bullet
        # except thinking/prompt-leakage ones.  All other drops are logged
        # to the quarantine panel (drops.jsonl) but the bullets survive.
        self.conservative_cb = QCheckBox(
            "Conservative drop mode (keep all bullets except thinking/prompt-leakage) — "
            "log every would-be drop to the Quarantine panel"
        )
        self.conservative_cb.setChecked(self.state.conservative_drops)
        self.conservative_cb.setToolTip(
            "When enabled, the summariser disables every bullet-drop filter EXCEPT the "
            "thinking-process / prompt-leakage filter. F4 source-overlap, Phase 2.2 "
            "semantic fact-check, B3 dedup, Content Judge grounding, and the quality "
            "scorer are all logged to drops.jsonl but the bullets stay in your output. "
            "A recovery pass then resurrects any quarantined bullet with >30% source "
            "overlap. Use this when you suspect genuine bullets are being dropped."
        )
        box_lay.addWidget(self.conservative_cb)

        # V10.36.0: Token budget slider — Quick (5 min, $0) to Thorough (45 min, $2.50)
        budget_box = QGroupBox("Token Budget (output selection preset)")
        budget_lay = QVBoxLayout(budget_box)
        budget_lay.setContentsMargins(10, 8, 10, 8)
        budget_lay.setSpacing(4)

        self.budget_slider = QSlider(Qt.Horizontal)
        self.budget_slider.setRange(0, 100)
        self.budget_slider.setSingleStep(25)
        self.budget_slider.setPageStep(25)
        self.budget_slider.setValue(50)  # default: Enhanced
        self.budget_label = QLabel("Enhanced — ~25 min, ~$0.50")
        self.budget_label.setObjectName("Caption")
        self.budget_label.setAlignment(Qt.AlignCenter)
        self.budget_slider.valueChanged.connect(self._on_budget_changed)

        budget_lay.addWidget(self.budget_label)
        budget_lay.addWidget(self.budget_slider)

        _budget_hint = QLabel(
            "Drag to auto-select outputs: Quick (summaries only) → Thorough (all 17 outputs). "
            "Cost estimates assume cloud API; local Ollama is always $0."
        )
        _budget_hint.setObjectName("Caption")
        _budget_hint.setWordWrap(True)
        budget_lay.addWidget(_budget_hint)

        box_lay.addWidget(budget_box)

        lay.addWidget(box)
        lay.addStretch()

    def _on_budget_changed(self, value: int) -> None:
        """V10.36.0/V10.37.0: Apply the token budget preset when the slider moves.

        V10.37.0: Also syncs the Step4 checkboxes so the user sees the
        output selection change in real time.  Previously the slider
        applied settings to the controller but the checkboxes (which
        drive WizardState → to_ui_data → build_request_from_ui) overrode
        them at conversion time.
        """
        from ui_qt.settings.presets import TOKEN_BUDGET_PRESETS

        # Find the closest preset
        closest = min(TOKEN_BUDGET_PRESETS, key=lambda p: abs(p["position"] - value))
        self.budget_label.setText(
            f"{closest['label']} — {closest['time_estimate']}, ~{closest['cost_estimate']}"
        )
        # Apply the preset settings to the controller
        for key, val in closest.get("settings", {}).items():
            self.controller.update_setting(key, val)

        # V10.37.0: Sync the Step4 checkboxes to match the preset.
        # Map settings keys to WizardState checkbox attributes.
        _settings_to_checkbox = {
            "outputs.briefing": "outputs_briefing",
            "outputs.podcast": "outputs_podcast",
            "outputs.flashcards": "outputs_flashcards",
            "outputs.packets": "outputs_packets",
            "outputs.obsidian": "outputs_obsidian",
            "outputs.study_guide": "outputs_study_guide",
            "outputs.social": "outputs_social",
            "outputs.mindmap": "outputs_mindmap",
            "outputs.qa": "outputs_qa",
            "outputs.glossary": "outputs_glossary",
            "outputs.patterns": "outputs_patterns",
            "outputs.cheatsheet": "outputs_cheatsheet",
            "outputs.epub": "outputs_epub",
            "outputs.quote_bank": "outputs_quote_bank",
            "summarisation.simplified_keypoints_enabled": "simplified_keypoints_enabled",
            "docx.enabled": "generate_docx",
        }
        for settings_key, state_attr in _settings_to_checkbox.items():
            enabled = closest.get("settings", {}).get(settings_key, False)
            # Update WizardState
            if hasattr(self.state, state_attr):
                setattr(self.state, state_attr, bool(enabled))
            # Update the Step4 checkbox widget if it exists
            if hasattr(self, "step4") and hasattr(self.step4, "_studio_cbs"):
                cb = self.step4._studio_cbs.get(state_attr)
                if cb is not None:
                    cb.setChecked(bool(enabled))
            # Also update core output checkboxes
            if hasattr(self, "step4") and hasattr(self.step4, "_core_cbs"):
                cb = self.step4._core_cbs.get(state_attr)
                if cb is not None:
                    cb.setChecked(bool(enabled))

    def save_to_state(self) -> None:
        self.state.segment_strategy = self.strat_combo.currentText()
        self.state.token_limit = self.token_spin.value()
        self.state.enable_semantic = self.semantic_cb.isChecked()
        self.state.academic_rigor = self.rigor_cb.isChecked()
        self.state.conservative_drops = self.conservative_cb.isChecked()
