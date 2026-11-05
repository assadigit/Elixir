"""Step 4: Output Selection — Step4Outputs (V0.7.2, wizard rework ④).

The V0.7.2 rework (plan §2 Phase ④; audit §W6/§W7/§W8):

**4a — essentials locked (D7).** The Core card carries the master
``Generate summaries`` switch (the SINGLE off-switch — audit §W6:
``generate_summaries=False`` cleanly no-ops every downstream output)
with the two essentials below it, pre-checked AND disabled, captioned
"Always included — every other output builds on these." They are locked
BY CONSTRUCTION: the checkboxes are ``setChecked(True)`` +
``setEnabled(False)`` in ``_build`` and ``save_to_state`` writes literal
``True`` — the state can never carry anything else.

**4b — five category cards (D8, D6).** The 25 flat checkboxes
reorganize into five registry-driven cards — AUDIO (podcast script,
TTS audio), LEARNING (flashcards, Q&A, study guide, glossary, packets),
KNOWLEDGE (Obsidian KB, mind map), DOCUMENTS (DOCX, EPUB), and
REFERENCE (executive briefing, evidence map, + the relocated simplified
keypoints / compact summaries, audit §W8 — both are independent gates).
The 5 deprecated outputs (social, patterns, cheatsheet, skill,
quote_bank — registry.py) are gone from the wizard (D6; the backend
generators stay for old files). The streaming checkbox is deleted
(dead code, audit §W8 — never reached the request). Every checkbox
carries a tooltip (audit §W7: none existed). The TTS label tells the
truth: "built from the executive briefing" (audit §3 B9 — the generator
reads the briefing file, podcast_audio.py:108-131), and the evidence
map admits it needs the langextract extra.

**4c — icons (D9).** Every checkbox renders its professional SVG
line-icon from ``ui_qt/components/icons.py`` (the registry's
``icon_name`` — one glyph per output); the category headers carry the
accent-tinted card glyph. No emoji on any control label.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.outputs.registry import get_output_by_key
from ui_qt.components.icons import icon, pixmap
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 4: Output Selection
# ════════════════════════════════════════════════════════════════════════════

# The five categories (D8) — registry keys only; the labels, tooltips and
# state fields all come from the registry's wizard_attr/icon_name plus the
# presentation tables below. Deprecated keys are absent BY DESIGN (D6).
_CATEGORY_CARDS: list[tuple[str, str, str, list[str]]] = [
    # (card title, icon, one-line caption, registry keys in display order)
    ("Audio", "audio-lines", "Listen instead of read.", ["podcast", "tts"]),
    (
        "Learning",
        "graduation-cap",
        "Study and self-test material.",
        ["flashcards", "qa", "study_guide", "glossary", "packets"],
    ),
    ("Knowledge", "link", "Reusable, linked notes.", ["obsidian", "mindmap"]),
    (
        "Documents",
        "file-output",
        "Whole-book files for your reader or word processor.",
        ["docx", "epub"],
    ),
    (
        "Reference",
        "book-open",
        "Quick overviews and source-grounded views.",
        ["briefing", "evidence_map", "compact_summaries", "simplified_keypoints"],
    ),
]

# Short, honest labels (the registry's labels are the verbose Settings-
# dialog forms; the cards keep theirs compact — the details live in the
# tooltips, audit §W7).
_CARD_LABELS: dict[str, str] = {
    "podcast": "Podcast script (2-host dialogue)",
    "tts": "TTS audio — built from the executive briefing",
    "flashcards": "Flashcards (Anki-compatible)",
    "qa": "Study questions (Q&&A)",  # && escapes Qt's mnemonic (the V0.7.1 ampersand lesson)
    "study_guide": "Study guide",
    "glossary": "Glossary",
    "packets": "Packets of Knowledge",
    "obsidian": "Obsidian knowledge base",
    "mindmap": "Mind map (Mermaid)",
    "docx": "DOCX report (Word)",
    "epub": "EPUB (for e-readers)",
    "briefing": "Executive briefing (one page)",
    "evidence_map": "Evidence map — needs the langextract extra",
    "compact_summaries": "Compact summaries (~1000 tokens/chapter)",
    "simplified_keypoints": "Simplified keypoints (jargon-free)",
}

# Every checkbox gets a tooltip (audit §W7: none existed before V0.7.2).
_CARD_TOOLTIPS: dict[str, str] = {
    "podcast": (
        "A two-host conversational script generated from the chapter "
        "summaries — text only, no audio."
    ),
    "tts": (
        "Spoken audio built from the executive briefing — not from the "
        "podcast script. English uses NeuTTS/Kokoro, Farsi uses Coqui "
        "XTTS v2. Needs the TTS audio stack installed."
    ),
    "flashcards": "Anki-compatible flashcards (TSV) plus a readable Markdown set.",
    "qa": "Open-ended study questions with answers, one set per chapter.",
    "study_guide": "One study guide per chapter: objectives, glossary, Q&A, self-check.",
    "glossary": "Key terms and their definitions, extracted across the book.",
    "packets": "Related keypoints clustered and synthesised into cohesive paragraphs.",
    "obsidian": "A linked Obsidian vault: YAML frontmatter and wikilinks between notes.",
    "mindmap": "A Mermaid mind map plus outline — deterministic, no LLM call, instant.",
    "docx": "A formatted Word document with a table of contents.",
    "epub": "The book re-exported as an annotated EPUB with embedded summaries.",
    "briefing": "A one-page synthesis of the whole book.",
    "evidence_map": (
        "An interactive HTML map that highlights every claim in its "
        "source text. Needs the langextract extra — without it, Elixir "
        "writes a guidance page instead."
    ),
    "compact_summaries": (
        "Density mode: caps each chapter's summary at roughly 1,000 "
        "tokens — shorter, denser summaries."
    ),
    "simplified_keypoints": (
        "A plain-language rewrite of every keypoint. Slower — one rewrite call per bullet."
    ),
}

# The two essentials, locked BY CONSTRUCTION (D7 / item 4a). Audit §W6:
# the include_* flags merely gate prompt sections and discard content —
# locking them on costs nothing structural, and generate_summaries stays
# the single off-switch.
_ESSENTIALS_CAPTION = "Always included — every other output builds on these."
_MASTER_CAPTION = (
    "The single off-switch — turning summaries off skips every summary-dependent output below."
)


class Step4Outputs(WizardStep):
    """Output selection: the Core card (master switch + locked essentials)
    and the five category cards (D8), driven from the registry.

    The registry grew to 24 specs — 17 studio + 7 core = 24 total — so the
    Review line and the start-log can enumerate EVERY selected output from
    it (the summary sub-flags and compact summaries joined;
    selected_output_names is the one reader both surfaces share)."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    STEP_HEADER = (4, "Outputs", "Choose everything Elixir should produce.")

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setSpacing(10)

        p = theme_manager.palette

        # ── The Core card (item 4a — essentials locked, D7) ─────────────
        core_box = QGroupBox("Core outputs")
        core_lay = QVBoxLayout(core_box)
        core_lay.setContentsMargins(10, 8, 10, 8)
        core_lay.setSpacing(6)

        # The master "Generate summaries" switch — the SINGLE off-switch
        # (audit §W6: generate_summaries=False cleanly no-ops every
        # downstream output).
        self.master_cb = QCheckBox("Generate summaries")
        self.master_cb.setIcon(icon("file-text", color=p.icon, size=16))
        self.master_cb.setChecked(self.state.generate_summaries)
        self.master_cb.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.master_cb.setToolTip(
            "The single off-switch. Summaries are the base layer — every "
            "other output (briefing, flashcards, podcast…) is built from "
            "them. Turn this off to convert without any summarisation."
        )
        core_lay.addWidget(self.master_cb)

        master_caption = QLabel(_MASTER_CAPTION)
        master_caption.setObjectName("Caption")
        master_caption.setWordWrap(True)
        master_caption.setStyleSheet("margin-left: 24px;")
        core_lay.addWidget(master_caption)

        # The two locked essentials (D7): checked + disabled BY
        # CONSTRUCTION — see save_to_state, which writes literal True.
        self.exec_cb = QCheckBox("Executive summary (short overview, scaled to chapter)")
        self.exec_cb.setIcon(icon("zap", color=p.icon, size=16))
        self.exec_cb.setChecked(True)
        self.exec_cb.setEnabled(False)
        self.exec_cb.setToolTip(
            "A short overview of each chapter, scaled to its length. "
            "Always included — locked on (the master switch above is the "
            "only way to skip it)."
        )
        core_lay.addWidget(self.exec_cb)

        self.thorough_cb = QCheckBox("Thorough summary (detailed prose, scaled to chapter)")
        self.thorough_cb.setIcon(icon("book", color=p.icon, size=16))
        self.thorough_cb.setChecked(True)
        self.thorough_cb.setEnabled(False)
        self.thorough_cb.setToolTip(
            "The detailed prose summary of each chapter, scaled to its "
            "length. Always included — locked on (the master switch above "
            "is the only way to skip it)."
        )
        core_lay.addWidget(self.thorough_cb)

        essentials_caption = QLabel(_ESSENTIALS_CAPTION)
        essentials_caption.setObjectName("Caption")
        essentials_caption.setWordWrap(True)
        essentials_caption.setStyleSheet("margin-left: 24px;")
        core_lay.addWidget(essentials_caption)

        # Keypoints stays with the summary set (a summary sub-option,
        # generated in the primary call — audit §W6).
        self.keypoints_cb = QCheckBox("Keypoints (bullet points)")
        self.keypoints_cb.setIcon(icon("list-checks", color=p.icon, size=16))
        self.keypoints_cb.setChecked(self.state.include_keypoints)
        self.keypoints_cb.setToolTip(
            "All key points extracted from each chapter, as bullet points."
        )
        core_lay.addWidget(self.keypoints_cb)

        host_lay.addWidget(core_box)

        # ── The five category cards (item 4b — D8, D6) ──────────────────
        # Two-column grid; REFERENCE spans the full width below.
        self._category_cbs: dict[str, QCheckBox] = {}
        self._category_boxes: dict[str, QGroupBox] = {}
        grid = QGridLayout()
        grid.setSpacing(8)
        positions = {
            "Audio": (0, 0),
            "Learning": (0, 1),
            "Knowledge": (1, 0),
            "Documents": (1, 1),
            "Reference": (2, 0, 1, 2),
        }
        for title, cat_icon, caption, keys in _CATEGORY_CARDS:
            card = self._build_category_card(title, cat_icon, caption, keys, p)
            self._category_boxes[title] = card
            row, col, *span = positions[title]
            if span:
                grid.addWidget(card, row, col, span[0], span[1])
            else:
                grid.addWidget(card, row, col)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        host_lay.addLayout(grid)

        host_lay.addStretch()
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)

    def _build_category_card(
        self,
        title: str,
        cat_icon: str,
        caption: str,
        keys: list[str],
        palette,
    ) -> QGroupBox:
        """One category card: the accent-tinted header glyph + caption,
        then one icon-carrying checkbox per registry key (D9 — the
        registry's icon_name renders; no emoji anywhere)."""
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        glyph = QLabel()
        glyph.setPixmap(pixmap(cat_icon, color=palette.accent, size=18))
        glyph.setFixedSize(20, 20)
        head.addWidget(glyph)
        cap = QLabel(caption)
        cap.setObjectName("Caption")
        cap.setWordWrap(True)
        head.addWidget(cap, 1)
        lay.addLayout(head)

        for key in keys:
            spec = get_output_by_key(key)
            if spec is None or not spec.wizard_attr:
                continue  # unreachable: the tables list registry keys only
            cb = QCheckBox(_CARD_LABELS[key])
            cb.setIcon(icon(spec.icon_name, color=palette.icon, size=16))
            cb.setChecked(bool(getattr(self.state, spec.wizard_attr, False)))
            cb.setToolTip(_CARD_TOOLTIPS[key])
            lay.addWidget(cb)
            self._category_cbs[spec.wizard_attr] = cb
        return box

    def save_to_state(self) -> None:
        """Write the card choices to the wizard state.

        The essentials are locked BY CONSTRUCTION (D7): the two literals
        below are the lock — no checkbox state can ever write False into
        them (they display checked + disabled, and even a programmatic
        re-enable cannot change what lands in the state).
        """
        self.state.generate_summaries = self.master_cb.isChecked()
        self.state.include_executive_summary = True
        self.state.include_thorough_summary = True
        self.state.include_keypoints = self.keypoints_cb.isChecked()
        for attr, cb in self._category_cbs.items():
            setattr(self.state, attr, cb.isChecked())
