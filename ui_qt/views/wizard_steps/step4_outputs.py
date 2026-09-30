"""Step 4: Output Selection — Step4Outputs (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step4Outputs
(back-compat facade).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 4: Output Selection
# ════════════════════════════════════════════════════════════════════════════


class Step4Outputs(WizardStep):
    """Output type selection (17 Output Studio types + 4 core = 21 total).

    V10.29.0 (Sprint 2): The Output Studio types now match
    ``core.outputs.registry.OUTPUT_REGISTRY`` exactly (was previously a
    hand-maintained list that drifted).  The core outputs remain
    wizard-specific (sub-options like exec/thorough summary don't belong
    in the shared registry).

    V0.6.8 (audit B19): the counts were corrected — the old docstring
    said "15 + 4 = 19" while the registry (and this list) carry 21
    OutputSpecs (17 studio + 4 core)."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Select outputs to generate")
        title.setObjectName("H2")
        lay.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setSpacing(8)

        # Core outputs
        core_label = QLabel("─ Core outputs ─")
        core_label.setObjectName("SectionTitle")
        host_lay.addWidget(core_label)

        self._core_cbs: dict[str, QCheckBox] = {}
        # V10.29.0 (Sprint 2.1): compact_summaries + _streaming_enabled are
        # now declared WizardState fields — getattr fallback removed.
        core_items = [
            ("generate_summaries", "Per-chapter summaries", self.state.generate_summaries),
            # V0.05 (rig audit F9b): the labels no longer promise absolute
            # word counts — every section target now SCALES to each
            # chapter's length (a summary section is never longer than a
            # fraction of its source). Promising "800-1200 words" here
            # while the engine scales down would be dishonest UI.
            (
                "include_executive_summary",
                "  Executive summary (short overview, scaled to chapter)",
                self.state.include_executive_summary,
            ),
            (
                "include_thorough_summary",
                "  Thorough summary (detailed prose, scaled to chapter)",
                self.state.include_thorough_summary,
            ),
            ("include_keypoints", "Keypoints (bullet points)", self.state.include_keypoints),
            (
                "simplified_keypoints_enabled",
                "Simplified keypoints (jargon-free)",
                self.state.simplified_keypoints_enabled,
            ),
            (
                "compact_summaries",
                "📦 Compact summaries (~1000 tokens/chapter)",
                self.state.compact_summaries,
            ),
            (
                "_streaming_enabled",
                "📡 Streaming LLM output (show partial summaries)",
                self.state._streaming_enabled,
            ),
            ("generate_docx", "DOCX report (Word document)", self.state.generate_docx),
        ]
        for key, label, checked in core_items:
            cb = QCheckBox(label)
            cb.setChecked(checked)
            host_lay.addWidget(cb)
            self._core_cbs[key] = cb

        # Output Studio
        studio_label = QLabel("─ Output Studio ─")
        studio_label.setObjectName("SectionTitle")
        studio_label.setContentsMargins(0, 8, 0, 0)
        host_lay.addWidget(studio_label)

        self._studio_cbs: dict[str, QCheckBox] = {}
        # V10.29.0 (Sprint 2.1): getattr fallbacks removed — the fields are
        # now declared on WizardState so they survive profile save/load.
        studio_items = [
            (
                "outputs_briefing",
                "Executive briefing (one-page synthesis)",
                self.state.outputs_briefing,
            ),
            (
                "outputs_podcast",
                "Podcast script (2-host dialogue text)",
                self.state.outputs_podcast,
            ),
            (
                "outputs_tts",
                "Podcast audio (TTS — requires podcast script enabled above)",
                self.state.outputs_tts,
            ),
            (
                "outputs_flashcards",
                "Flashcards (Anki-compatible TSV + MD)",
                self.state.outputs_flashcards,
            ),
            (
                "outputs_packets",
                "Packets of Knowledge (clustered synthesis + Q&A)",
                self.state.outputs_packets,
            ),
            (
                "outputs_obsidian",
                "Obsidian knowledge base (linked notes)",
                self.state.outputs_obsidian,
            ),
            (
                "outputs_study_guide",
                "Study guide (objectives, glossary, Q&A)",
                self.state.outputs_study_guide,
            ),
            (
                "outputs_social",
                "Social media pack (X thread + LinkedIn)",
                self.state.outputs_social,
            ),
            ("outputs_mindmap", "Mind map (Mermaid + outline)", self.state.outputs_mindmap),
            # V10.20.0 + V10.21.0: New output types
            ("outputs_qa", "❓ Study Questions (open-ended Q&A)", self.state.outputs_qa),
            (
                "outputs_glossary",
                "📖 Glossary (key terms + definitions)",
                self.state.outputs_glossary,
            ),
            ("outputs_patterns", "🔧 Patterns & Techniques", self.state.outputs_patterns),
            (
                "outputs_cheatsheet",
                "📋 Cheatsheet (decision tables)",
                self.state.outputs_cheatsheet,
            ),
            (
                "outputs_skill",
                "🤖 Agent Skill (SKILL.md for Claude/Copilot)",
                self.state.outputs_skill,
            ),
            (
                "outputs_evidence_map",
                "🗺️ Scientific Evidence Map (langextract)",
                self.state.outputs_evidence_map,
            ),
            # V10.36.0: New outputs
            ("outputs_epub", "📚 EPUB (annotated, for e-readers)", self.state.outputs_epub),
            (
                "outputs_quote_bank",
                "💬 Quote Bank (direct quotes with citations)",
                self.state.outputs_quote_bank,
            ),
        ]
        for key, label, checked in studio_items:
            cb = QCheckBox(label)
            cb.setChecked(checked)
            host_lay.addWidget(cb)
            self._studio_cbs[key] = cb

        host_lay.addStretch()
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)

    def save_to_state(self) -> None:
        for key, cb in self._core_cbs.items():
            setattr(self.state, key, cb.isChecked())
        for key, cb in self._studio_cbs.items():
            setattr(self.state, key, cb.isChecked())
