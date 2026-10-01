"""Step 8: Review — Step8Review (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step8Review
(back-compat facade).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 8: Review
# ════════════════════════════════════════════════════════════════════════════


class Step8Review(WizardStep):
    """Review ALL choices + start conversion. Shows every setting with Edit buttons."""

    start_requested = Signal()
    edit_step_requested = Signal(int)  # step index to jump to

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        title = QLabel("Review all settings before starting")
        title.setObjectName("H2")
        lay.addWidget(title)

        warning = QLabel(
            "⚠️ Conversion is resource and time intensive. Please review every category below before clicking Start."
        )
        warning.setObjectName("Caption")
        warning.setWordWrap(True)
        p = theme_manager.palette
        warning.setStyleSheet(f"color: {p.warning}; font-size: 11px; background: transparent;")
        lay.addWidget(warning)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setStyleSheet("font-size: 11px;")
        lay.addWidget(self.summary, 1)

        # Edit buttons row — jump to any step
        edit_row = QHBoxLayout()
        edit_row.setSpacing(4)
        edit_lbl = QLabel("Edit:")
        edit_lbl.setStyleSheet("font-size: 11px; background: transparent;")
        edit_row.addWidget(edit_lbl)
        edit_steps = [
            (0, "PDF"),
            (1, "Range"),
            (2, "OCR"),
            (3, "Outputs"),
            (4, "Models"),
            (5, "Translation"),
            (6, "Advanced"),
            (7, "Fine-tune"),
        ]
        self._edit_buttons: list[QPushButton] = []
        for step_idx, label in edit_steps:
            btn = QPushButton(label)
            btn.setObjectName("Compact")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda checked, idx=step_idx: self.edit_step_requested.emit(idx))
            edit_row.addWidget(btn)
            self._edit_buttons.append(btn)
        edit_row.addStretch()
        lay.addLayout(edit_row)

        # V8.1.0: Post-completion action (shutdown/sleep/quit) — for overnight runs
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(QLabel("After completion:"))
        self.post_action_combo = QComboBox()
        self.post_action_combo.addItem("Do nothing", "none")
        self.post_action_combo.addItem("Quit app", "quit")
        self.post_action_combo.addItem("Sleep computer", "sleep")
        self.post_action_combo.addItem("Hibernate computer", "hibernate")
        self.post_action_combo.addItem("Shut down computer", "shutdown")
        self.post_action_combo.setToolTip(
            "Choose what happens after the conversion (including translation\n"
            "and TTS) finishes completely.\n\n"
            "• Sleep/Hibernate/Shutdown: a 60-second countdown dialog appears\n"
            "  first, so you can cancel if you change your mind.\n"
            "• Quit: the app closes immediately after completion."
        )
        # Load saved preference
        saved_action = self.controller.get_setting("ui.post_completion_action", "none")
        idx = self.post_action_combo.findData(saved_action)
        if idx >= 0:
            self.post_action_combo.setCurrentIndex(idx)
        action_row.addWidget(self.post_action_combo, 1)
        lay.addLayout(action_row)

        self.start_btn = QPushButton("  🚀  Start Conversion")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setMinimumHeight(34)  # V7.4.0: was 40
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_requested.emit)
        lay.addWidget(self.start_btn)

    def refresh(self) -> None:
        """Update the summary text from the wizard state — shows ALL settings."""
        s = self.state
        lines = []

        # PDF & Document
        lines.append("<b>📄 PDF & Document</b>")
        lines.append(f"  File: {Path(s.input_path).name if s.input_path else '(none)'}")
        lines.append(f"  Type: {s.source_type}")
        lines.append("")

        # Range
        lines.append("<b>📐 Page Range</b>")
        if s.page_range_start is None:
            lines.append("  Pages: all")
        else:
            lines.append(f"  Pages: {s.page_range_start}-{s.page_range_end}")
        lines.append(f"  Page group size: {s.page_group_size}")
        lines.append(f"  Auto-detect scanned: {'yes' if s.auto_detect_scanned else 'no'}")
        if s.selected_chapters:
            lines.append(f"  Selected chapters: {len(s.selected_chapters)} chapter(s)")
        lines.append("")

        # OCR
        lines.append("<b>🔍 OCR</b>")
        lines.append(f"  LLM OCR: {'yes' if s.use_llm_ocr else 'no'}")
        lines.append(f"  Force OCR all pages: {'yes' if s.force_ocr_all_pages else 'no'}")
        lines.append(f"  PaddleOCR fallback: {'yes' if s.use_paddleocr else 'no'}")
        lines.append(f"  Extract figures: {'yes' if s.extract_figure_text else 'no'}")
        lines.append(f"  Extract tables: {'yes' if s.extract_tables else 'no'}")
        lines.append(f"  Timeout: {s.ocr_timeout}s")
        lines.append("")

        # Outputs
        lines.append("<b>📤 Outputs</b>")
        outs = []
        if s.generate_summaries and s.include_executive_summary:
            outs.append("exec summary")
        if s.generate_summaries and s.include_thorough_summary:
            outs.append("thorough summary")
        if s.include_keypoints:
            outs.append("keypoints")
        if s.simplified_keypoints_enabled:
            outs.append("simplified keypoints")
        if s.generate_docx:
            outs.append("DOCX")
        if s.outputs_briefing:
            outs.append("briefing")
        if s.outputs_podcast:
            outs.append("podcast script")
        if s.outputs_flashcards:
            outs.append("flashcards")
        if s.outputs_obsidian:
            outs.append("obsidian")
        if s.outputs_study_guide:
            outs.append("study guide")
        if s.outputs_social:
            outs.append("social")
        if s.outputs_mindmap:
            outs.append("mindmap")
        if s.outputs_tts:
            outs.append("TTS audio")
        lines.append("  " + (", ".join(outs) if outs else "(none)"))
        lines.append("")

        # Models
        lines.append("<b>🤖 Models</b>")
        lines.append(f"  Summarization: {s.summarisation_model or '(default)'}")
        lines.append(f"  OCR: {s.primary_ocr_model or '(default)'}")
        lines.append(f"  Workers: {s.max_workers}, Temperature: {s.temperature}")
        lines.append("")

        # Translation
        lines.append("<b>🌐 Translation</b>")
        if s.translation_enabled:
            lines.append("  Status: ENABLED")
            lines.append(f"  Backend: {s.translation_backend}")
            lines.append(f"  Target: {s.translation_target_lang}")
            lines.append(f"  Harakat model: {s.translation_harakat_model or '(default)'}")
            lines.append(f"  Judge model: {s.translation_judge_model or '(use summarization)'}")
            tr_outs = [k for k, v in s.translation_outputs.items() if v]
            lines.append(f"  Translate outputs: {', '.join(tr_outs) if tr_outs else '(none)'}")
        else:
            lines.append("  Status: disabled")
        lines.append("")

        # Advanced
        lines.append("<b>⚙️ Advanced</b>")
        lines.append(f"  Segmentation: {s.segment_strategy} (tokens: {s.token_limit})")
        lines.append(f"  Semantic: {'yes' if s.enable_semantic else 'no'}")
        lines.append(f"  Academic rigor: {'yes' if s.academic_rigor else 'no'}")
        lines.append(f"  Conservative drops: {'yes' if s.conservative_drops else 'no'}")
        lines.append("")

        # Fine-tuning
        lines.append("<b>🔧 Fine-tuning</b>")
        lines.append(f"  Clean markdown: {'yes' if s.clean_markdown else 'no'}")
        lines.append(f"  Fix missing spaces: {'yes' if s.fix_missing_spaces else 'no'}")
        lines.append(f"  Token saver: {'yes' if s.token_saver else 'no'}")
        lines.append(f"  Remove page headings: {'yes' if s.remove_page_number_headings else 'no'}")
        lines.append(f"  Convert separators: {'yes' if s.convert_separators_to_comments else 'no'}")
        lines.append(f"  DOCX author: {s.docx_author}")
        lines.append(f"  DOCX TOC: {'yes' if s.docx_include_toc else 'no'}")
        lines.append(f"  Self-consistency: {'yes' if s.self_consistency else 'no'}")
        lines.append(f"  Coverage threshold: {s.coverage_threshold}%")
        lines.append(
            f"  Resume mode: {'yes — skip done chapters' if s.resume_enabled else 'no — reprocess all'}"
        )
        lines.append(f"  Content filter: {'yes' if s.enable_content_filter else 'no'}")
        lines.append(f"  Max context: {s.max_context_tokens} tokens")
        lines.append(f"  Max output: {s.max_output_tokens} tokens")
        lines.append(f"  Cache: {'yes' if s.cache_enabled else 'no'}")
        lines.append(f"  Extract math: {'yes' if s.extract_math else 'no'}")
        lines.append(f"  Layout analysis: {'yes' if s.layout_analysis else 'no'}")
        # V18.2.1: Performance & Embeddings in review
        lines.append(f"  Embedding model: {s.embedding_model}")
        lines.append(f"  Embedding device: {s.embedding_device}")
        lines.append(f"  VRAM recovery delay: {s.vram_recovery_delay_sec}s")
        lines.append(f"  B4 max sections: {s.b4_max_sections} (0=unlimited)")
        lines.append(f"  B4 threshold: {s.b4_threshold_tokens} tokens")

        self.summary.setHtml("<br>".join(lines))
