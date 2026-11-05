"""Step 7: Advanced Settings — Step7Advanced (V18.20.4.6, P5 / O-b1 split).

V0.7.5 (wizard rework ⑦, item 7a — audit §W11, D17-D19 + D13/B4): the
flat five-control panel collapses into ONE primary choice + a folded
advanced disclosure:

    Strategy: [auto ▾]  (+ the honest per-strategy copy underneath —
                         the AUTO cascade spelled out, semantic's extra
                         AI call and its ~3,500-token sample named)
    ▸ Show advanced settings      (folded by default)
        └ Token limit per segment: [✓ Auto — the default (2,000)]
           [spin]  — the manual field enables ONLY under the Token
           strategy (it only feeds TokenSegmenter,
           core/segmentation/token_segmenter.py:21; under every other
           strategy the limit is never read)
        └ [✓] Allow the semantic fallback …  (the enable_semantic
           toggle folded in here, default on — D17)

DELETED with this rework (the audit's dead / lying controls):
  - the academic-rigor checkbox (D19): its label lied ("temperature=0"
    no longer happens, summarizer_init.py:512-516). The REAL
    source-driven auto-enable stays in the backend
    (summarizer_init.py:496-511) and the Settings page keeps its toggle;
    the wizard stops forcing the state field over it.
  - the conservative-drops checkbox (D18): a debugging stance, not a
    quality setting. The backend + the quarantine panel stay untouched;
    the wizard stops exposing it.
  - the token-budget slider (D13) — live bug B4, doubly broken: the
    Step-4 sync checked ``hasattr(self, "step4")`` on the STEP-7 widget
    (never true, step7_advanced.py:206,211 pre-rework) and Step-4's
    ``save_to_state`` clobbered the slider's writes at Start
    (wizard_view.py:530-532). Its presets also force deprecated outputs
    on (presets.py:192-215). Deleted with it: the dead Step-4 sync and
    ``TOKEN_BUDGET_PRESETS``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.components.icons import icon
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 7: Advanced Settings
# ════════════════════════════════════════════════════════════════════════════

# V0.7.5 (item 7a): the honest strategy copy. The AUTO entry spells the
# REAL cascade out (core/segmentation/segmenter.py:1879-2087) and names
# semantic's cost honestly — one extra AI call that samples the first
# ~3,500 tokens (semantic_segmenter.py:52-113).
_STRAT_DESC = {
    "auto": (
        "Try each method in order until one fits: the book's own chapter "
        "outline → located table of contents → fuzzy TOC → headings → "
        "semantic (one extra AI call that samples the first ~3,500 tokens) "
        "→ page-group blocks → fixed tokens → the whole document as one "
        "section. Recommended for most books."
    ),
    "heading": (
        "Splits at markdown headings (#, ##). Best for documents with a clear heading hierarchy."
    ),
    "semantic": (
        "One AI call samples the first ~3,500 tokens and asks for logical "
        "boundaries. Under Auto it is only reached when outline, TOC and "
        "headings all fail; choosing it here forces it. Slower — one extra "
        "LLM call per document."
    ),
    "token": (
        "Splits at fixed token intervals (paragraph boundaries respected). "
        "The last resort — segments may break mid-topic. The token limit "
        "below is the only setting this strategy reads."
    ),
}

# V0.7.5 (item 7a): the token-limit note under the three gate states.
# The manual field only feeds TokenSegmenter — under any other strategy
# the limit is never read (audit §W11).
_TOKEN_NOTE_AUTO = "The default (2,000) applies — the settings-layer default."
_TOKEN_NOTE_OTHER_STRAT = (
    "This limit only feeds the Token strategy — under “{strat}” it is never "
    "read. (Auto uses it as its last-resort fallback only.)"
)
_TOKEN_NOTE_MANUAL = "Used by the fixed-token chunker (TokenSegmenter)."


class Step7Advanced(WizardStep):
    """Advanced: one primary choice (the split strategy) + a folded disclosure."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    # V0.7.5 (rework ⑦): segmentation is the step's whole topic now.
    STEP_HEADER = (
        7,
        "Advanced",
        "How the book is split into sections — the default suits most books.",
    )

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        box = QGroupBox("Segmentation")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(10, 10, 10, 8)
        box_lay.setSpacing(6)

        # ── The primary choice: the strategy ───────────────────────────
        strat_row = QHBoxLayout()
        strat_row.setSpacing(8)
        self.strat_combo = QComboBox()
        self.strat_combo.addItems(["auto", "heading", "semantic", "token"])
        self.strat_combo.setCurrentText(self.state.segment_strategy)
        self.strat_combo.setToolTip(
            "auto: chapter outline → TOC → fuzzy TOC → headings → semantic → "
            "page-groups → tokens → whole document (recommended)\n"
            "heading: split at markdown headings (#, ##)\n"
            "semantic: one extra AI call samples the first ~3,500 tokens and "
            "asks for boundaries\n"
            "token: fixed token intervals (last resort)"
        )
        strat_row.addWidget(QLabel("Split strategy:"))
        strat_row.addWidget(self.strat_combo)
        strat_row.addStretch()
        box_lay.addLayout(strat_row)

        # The honest per-strategy copy (updates on selection change).
        self.strat_desc_label = QLabel(_STRAT_DESC.get(self.state.segment_strategy, ""))
        self.strat_desc_label.setWordWrap(True)
        self.strat_desc_label.setStyleSheet(
            f"color: {theme_manager.palette.text_secondary}; font-size: 11px; padding: 2px 8px;"
        )
        box_lay.addWidget(self.strat_desc_label)
        self.strat_combo.currentTextChanged.connect(
            lambda txt: self.strat_desc_label.setText(_STRAT_DESC.get(txt, ""))
        )

        # ── The folded advanced disclosure ──────────────────────────────
        # V0.7.5 (item 7a, D17): folded by default; the fold toggle is a
        # checkable QToolButton with the chevron glyphs (D9 — professional
        # icons, no emoji).
        fold_row = QHBoxLayout()
        fold_row.setSpacing(6)
        self.fold_btn = QToolButton()
        self.fold_btn.setText("Show advanced settings")
        self.fold_btn.setCheckable(True)
        self.fold_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.fold_btn.setStyleSheet(
            f"color: {theme_manager.palette.text_secondary}; font-size: 11px;"
            " padding: 2px 4px; border: none; background: transparent;"
        )
        self.fold_btn.toggled.connect(self._on_fold_toggled)
        fold_row.addWidget(self.fold_btn)
        fold_row.addStretch()
        box_lay.addLayout(fold_row)

        self.disclosure = QWidget()
        disc_lay = QVBoxLayout(self.disclosure)
        disc_lay.setContentsMargins(8, 2, 8, 2)
        disc_lay.setSpacing(6)

        # Token limit per segment: Auto (default) + manual. The manual
        # field is enabled ONLY when the TOKEN strategy is actually in
        # play — it only feeds TokenSegmenter (token_segmenter.py:21).
        tok_row = QHBoxLayout()
        tok_row.setSpacing(8)
        self.token_auto_cb = QCheckBox("Auto — the default (2,000 tokens per segment)")
        self.token_auto_cb.setChecked(True)
        self.token_auto_cb.setToolTip(
            "Auto: the settings-layer default (2,000, segmentation.token_limit) "
            "applies.\n\nUncheck to set the number yourself — the field only "
            "enables under the Token strategy (under every other strategy "
            "the limit is never read; Auto uses it as its last-resort "
            "fallback only)."
        )
        self.token_spin = QSpinBox()
        self.token_spin.setRange(500, 32000)
        self.token_spin.setSingleStep(500)
        self.token_spin.setValue(self.state.token_limit)
        self.token_spin.setToolTip(
            "Maximum tokens per segment — read ONLY by the fixed-token "
            "chunker (TokenSegmenter).\n"
            "• Smaller values (500-1500): more segments, each comfortably "
            "inside the context window.\n"
            "• Larger values (2000-8000): fewer segments, but risk of "
            "truncation on long chapters.\n"
            "• The default 2,000 works for most models with a 32k context."
        )
        tok_row.addWidget(self.token_auto_cb)
        tok_row.addWidget(self.token_spin)
        tok_row.addStretch()
        disc_lay.addLayout(tok_row)

        self.token_note = QLabel(_TOKEN_NOTE_AUTO)
        self.token_note.setObjectName("Caption")
        self.token_note.setWordWrap(True)
        disc_lay.addWidget(self.token_note)

        # The semantic toggle, folded into the disclosure (D17). Default
        # ON; honest copy about what it actually gates (audit §W11: only
        # AUTO stage 4 — segmenter.py:2091; explicit strategies ignore it).
        self.semantic_cb = QCheckBox(
            "Allow the semantic fallback (one extra AI call — samples the first ~3,500 tokens)"
        )
        self.semantic_cb.setChecked(self.state.enable_semantic)
        self.semantic_cb.setToolTip(
            "Under Auto, this decides whether a paid LLM call is attempted "
            "(semantic boundary detection over the first ~3,500 tokens) "
            "before the fixed-token fallback. Turning it off skips that "
            "call — segmentation then falls straight to page-group blocks / "
            "fixed tokens.\n\nExplicit strategies ignore this toggle."
        )
        disc_lay.addWidget(self.semantic_cb)

        box_lay.addWidget(self.disclosure)
        self.disclosure.setVisible(False)
        self._sync_token_gate()

        self.token_auto_cb.toggled.connect(lambda _on: self._sync_token_gate())
        self.strat_combo.currentTextChanged.connect(lambda _txt: self._sync_token_gate())

        lay.addWidget(box)
        lay.addStretch()

    # ── disclosure / gate mechanics ────────────────────────────────────

    def _on_fold_toggled(self, checked: bool) -> None:
        p = theme_manager.palette
        self.fold_btn.setText("Hide advanced settings" if checked else "Show advanced settings")
        self.fold_btn.setIcon(
            icon(
                "chevron-down" if checked else "chevron-right",
                color=p.text_secondary,
                size=14,
            )
        )
        self.disclosure.setVisible(checked)

    def _sync_token_gate(self) -> None:
        """The manual token field enables ONLY when the TOKEN strategy is
        actually in play AND Auto is off (audit §W11 — the limit only
        feeds TokenSegmenter; every other strategy never reads it)."""
        strat = self.strat_combo.currentText()
        auto = self.token_auto_cb.isChecked()
        manual_live = (not auto) and strat == "token"
        self.token_spin.setEnabled(manual_live)
        if auto:
            self.token_note.setText(_TOKEN_NOTE_AUTO)
        elif not manual_live:
            self.token_note.setText(_TOKEN_NOTE_OTHER_STRAT.format(strat=strat))
        else:
            self.token_note.setText(_TOKEN_NOTE_MANUAL)

    def save_to_state(self) -> None:
        self.state.segment_strategy = self.strat_combo.currentText()
        self.state.token_limit = self.token_spin.value()
        self.state.enable_semantic = self.semantic_cb.isChecked()
        # V0.7.5 (rework ⑦, D19/D18): academic_rigor and conservative_drops
        # are NO LONGER written here — the checkboxes are gone from the
        # wizard. The backend mechanisms stay; the Settings page is the
        # only UI writer (the source-driven academic auto-enable in the
        # backend is untouched, summarizer_init.py:496-511).
