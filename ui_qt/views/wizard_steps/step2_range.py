"""Step 2: Page Range — Step2Range (V18.20.4.6, P5 / O-b1 split).

V0.7.1 (wizard rework ③, items 3a+3b — audit §W4): the page range grows
into a proper card (larger controls, a live feedback line, tooltips —
"Process all pages" stays the default, the range fields enable on
uncheck), and the TOC detection button is promoted from a quiet
secondary action to a prominent card-level action (professional icon per
D9 — the old emoji-prefixed label is gone — + honest caption "Most
accurate — reads the book's own outline"). The backend
(ChapterSelectorDialog → 7 scored parsers) is untouched — this is pure
UI promotion, exactly what the audit prescribed.

The item-3c UI (the processing-blocks row) lives in the Segmentation
group; see tests/test_v0710_page_group_segmenter.py for its wiring.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ui_qt.components.icons import pixmap
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 2: Page Range
# ════════════════════════════════════════════════════════════════════════════


class Step2Range(WizardStep):
    """Page range (card) + TOC chapter selection (promoted action) + the
    processing-blocks row (V0.7.1 item 3c)."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    STEP_HEADER = (
        2,
        "Pages & chapters",
        "Process everything, a range, or pick chapters from the table of contents.",
    )

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ── Page range card (V0.7.1 item 3a) ───────────────────────────
        # The old group was small and quiet (audit §W4: "no tooltips, no
        # size hints"); the card gives it 15px field labels, 32px
        # spinboxes, a live feedback line, and tooltips.
        range_box = QGroupBox("Page range")
        range_lay = QVBoxLayout(range_box)
        range_lay.setContentsMargins(10, 10, 10, 8)
        range_lay.setSpacing(8)

        self.all_pages_cb = QCheckBox("Process all pages")
        self.all_pages_cb.setChecked(True)
        self.all_pages_cb.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.all_pages_cb.setToolTip(
            "Checked (default): every page of the PDF is processed.\n"
            "Uncheck to enter a specific page range — chapter selection is\n"
            "then disabled (a chapter can span outside a chosen range)."
        )
        self.all_pages_cb.stateChanged.connect(self._on_all_changed)
        range_lay.addWidget(self.all_pages_cb)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(12)
        self.start_spin = self._make_big_spin()
        self.start_spin.setEnabled(False)
        self.start_spin.setToolTip("First page to process (1-based).")
        self.end_spin = self._make_big_spin()
        self.end_spin.setValue(99999)
        self.end_spin.setEnabled(False)
        self.end_spin.setToolTip("Last page to process (1-based).")
        # The feedback line is LIVE: every spin change refreshes it.
        self.start_spin.valueChanged.connect(lambda *_: self._refresh_feedback())
        self.end_spin.valueChanged.connect(lambda *_: self._refresh_feedback())
        custom_row.addWidget(self._field_label("From page:"))
        custom_row.addWidget(self.start_spin)
        custom_row.addWidget(self._field_label("To page:"))
        custom_row.addWidget(self.end_spin)
        custom_row.addStretch()
        range_lay.addLayout(custom_row)

        # Live feedback line (item 3a): updates on every toggle/spin
        # change and after a chapter selection.
        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setObjectName("Caption")
        self.feedback_lbl.setWordWrap(True)
        range_lay.addWidget(self.feedback_lbl)
        lay.addWidget(range_box)

        # ── TOC detection card (V0.7.1 item 3b) ────────────────────────
        # The old emoji-prefixed "Detect chapters from TOC" secondary
        # button becomes a prominent card-level action: professional
        # icon (D9 — no emoji on controls) + title + honest caption. The
        # checkbox + dialog mechanics are UNCHANGED (the backend is
        # solid, audit §W4).
        chapter_box = QGroupBox("Chapters from the table of contents")
        chapter_lay = QVBoxLayout(chapter_box)
        chapter_lay.setContentsMargins(10, 10, 10, 8)
        chapter_lay.setSpacing(8)

        head_row = QHBoxLayout()
        head_row.setSpacing(10)
        p = theme_manager.palette
        self.toc_icon_lbl = QLabel()
        self.toc_icon_lbl.setPixmap(pixmap("list-checks", color=p.accent, size=22))
        self.toc_icon_lbl.setFixedSize(24, 24)
        head_row.addWidget(self.toc_icon_lbl)

        head_txt = QVBoxLayout()
        head_txt.setSpacing(1)
        toc_title = QLabel("Detect chapters from the table of contents")
        toc_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        head_txt.addWidget(toc_title)
        toc_caption = QLabel("Most accurate — reads the book's own outline.")
        toc_caption.setObjectName("Caption")
        toc_caption.setWordWrap(True)
        head_txt.addWidget(toc_caption)
        head_row.addLayout(head_txt, 1)
        chapter_lay.addLayout(head_row)

        self.select_chapters_cb = QCheckBox("Select specific chapters from table of contents")
        self.select_chapters_cb.toggled.connect(self._on_chapter_toggled)
        chapter_lay.addWidget(self.select_chapters_cb)

        chapter_row = QHBoxLayout()
        chapter_row.setSpacing(8)
        self.chapter_btn = QPushButton("Detect chapters…")
        self.chapter_btn.setObjectName("Primary")
        # The icon tint rides the palette's on-accent token (never a
        # hardcoded literal — the M1 de-hardcode census enforces this).
        self.chapter_btn.setIcon(pixmap("search", color=p.text_on_accent, size=16))
        self.chapter_btn.setCursor(Qt.PointingHandCursor)
        self.chapter_btn.setMinimumHeight(34)
        # V10.1.1 fix: button is always enabled (when the group is active).
        # The old behaviour disabled the button until the checkbox above it
        # was checked — users saw a greyed-out button and didn't realise
        # they needed to check the checkbox first.  Now the button IS the
        # primary action: clicking it auto-checks the checkbox and opens
        # the selector.  The checkbox becomes a reflection of state, not a
        # gate.
        self.chapter_btn.setEnabled(True)
        self.chapter_btn.setToolTip(
            "Click to scan the PDF's table of contents and pick which "
            "chapters to convert.  You can also check the box above first — "
            "either way works."
        )
        self.chapter_btn.clicked.connect(self._open_chapter_selector)
        chapter_row.addWidget(self.chapter_btn)
        self.chapter_count_lbl = QLabel("")
        self.chapter_count_lbl.setObjectName("Caption")
        chapter_row.addWidget(self.chapter_count_lbl)
        chapter_row.addStretch()
        chapter_lay.addLayout(chapter_row)

        self._selected_chapters: list[str] | None = None
        self._total_pages: int | None = None  # best-effort page count
        lay.addWidget(chapter_box)

        # ── Segmentation — the D5 UI (V0.7.1 item 3c) ──────────────────
        # The honest processing-blocks row. The old "Page group size" spin
        # was a dead control (audit §W4: logged and ignored); it is now
        # wired to the PageGroupSegmenter fallback — 0 = AUTO (measured
        # from the book's page density), 4-25 = manual override.
        seg_box = QGroupBox("Segmentation")
        seg_lay = QVBoxLayout(seg_box)
        seg_lay.setContentsMargins(10, 10, 10, 8)
        seg_lay.setSpacing(6)

        self.blocks_auto_cb = QCheckBox(
            "Auto — block size measured from this book (typically ≈ 8 pages)"
        )
        self.blocks_auto_cb.setChecked(self.state.page_group_size == 0)
        self.blocks_auto_cb.setToolTip(
            "When no chapters, table-of-contents entries, or headings can "
            "be detected, the pages are grouped into multi-page blocks. "
            "Auto sizes each block to roughly 4,000-6,000 tokens (usually "
            "about 8 pages for a normal book)."
        )
        self.blocks_auto_cb.toggled.connect(self._on_blocks_auto_changed)
        seg_lay.addWidget(self.blocks_auto_cb)

        override_row = QHBoxLayout()
        override_row.setSpacing(8)
        override_lbl = QLabel("Pages per block:")
        override_lbl.setEnabled(False)
        self._override_lbl = override_lbl
        self.group_spin = QSpinBox()
        self.group_spin.setRange(4, 25)
        _persisted = self.state.page_group_size
        self.group_spin.setValue(8 if _persisted <= 0 else min(25, max(4, _persisted)))
        self.group_spin.setEnabled(not self.blocks_auto_cb.isChecked())
        self.group_spin.setToolTip(
            "Manual override: how many pages each block covers (4-25). "
            "Used only when no chapter structure can be detected."
        )
        override_row.addWidget(override_lbl)
        override_row.addWidget(self.group_spin)
        override_row.addStretch()
        seg_lay.addLayout(override_row)

        blocks_hint = QLabel(
            "Blocks are used only when no chapter structure can be detected — "
            "pages are grouped into multi-page blocks, never arbitrary token slices."
        )
        blocks_hint.setObjectName("Caption")
        blocks_hint.setWordWrap(True)
        seg_lay.addWidget(blocks_hint)
        lay.addWidget(seg_box)
        lay.addStretch()

        self._read_total_pages()
        self._refresh_feedback()

    # ── card helpers (item 3a) ─────────────────────────────────────────

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 15px; font-weight: 500;")
        return lbl

    @staticmethod
    def _make_big_spin() -> QSpinBox:
        """A 32px-tall, 14px-text spinbox (the old ones were ~24px)."""
        spin = QSpinBox()
        spin.setRange(1, 99999)
        spin.setValue(1)
        spin.setFixedHeight(32)
        spin.setMinimumWidth(88)
        spin.setStyleSheet("font-size: 14px;")
        return spin

    # ── live feedback (item 3a) ────────────────────────────────────────

    def _read_total_pages(self) -> None:
        """Best-effort page count from the PDF chosen in Step 1.

        pypdf's xref parse is milliseconds even on large files; failure
        (no file yet / encrypted / unparsable) leaves the count unknown —
        the feedback line then omits it (honest, never guessed).
        """
        inp = self.state.input_path
        if not inp or not Path(inp).exists():
            self._total_pages = None
            return
        try:
            from pypdf import PdfReader

            self._total_pages = len(PdfReader(str(inp)).pages)
        except Exception:
            self._total_pages = None

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Refresh on every show — the PDF is picked in Step 1, AFTER this
        step was built (steps are constructed once at wizard open), so the
        page count and feedback must be recomputed here."""
        super().showEvent(event)
        self._read_total_pages()
        self._refresh_feedback()

    def _refresh_feedback(self) -> None:
        """The live feedback line — every state, honestly worded."""
        if self.all_pages_cb.isChecked():
            chapters = len(self._selected_chapters or [])
            if self._total_pages:
                base = f"All {self._total_pages} pages will be processed."
            else:
                base = "All pages will be processed."
            if chapters:
                base += f" {chapters} chapter(s) selected from the table of contents."
            self.feedback_lbl.setText(base)
            return
        start = self.start_spin.value()
        end = self.end_spin.value()
        span = max(0, end - start + 1)
        if start > end:
            self.feedback_lbl.setText(f"Pages {start}-{end} — 'from' must be ≤ 'to'.")
            return
        if self._total_pages:
            pct = round(span / self._total_pages * 100)
            self.feedback_lbl.setText(
                f"Pages {start}-{end} — {span} of {self._total_pages} pages "
                f"(~{pct}%) will be processed."
            )
        else:
            self.feedback_lbl.setText(f"Pages {start}-{end} — {span} pages will be processed.")

    # ── handlers ────────────────────────────────────────────────────────

    def _on_all_changed(self) -> None:
        all_pages = self.all_pages_cb.isChecked()
        self.start_spin.setEnabled(not all_pages)
        self.end_spin.setEnabled(not all_pages)
        if not all_pages:
            # Custom range disables chapter selection
            self.select_chapters_cb.setChecked(False)
            self.select_chapters_cb.setEnabled(False)
            # V10.1.1: also disable the button — chapter selection doesn't
            # make sense with a custom page range (chapters may span outside
            # the chosen range).
            self.chapter_btn.setEnabled(False)
        else:
            self.select_chapters_cb.setEnabled(True)
            # V10.1.1: button is always enabled when the group is active.
            self.chapter_btn.setEnabled(True)
        self._refresh_feedback()

    def _on_blocks_auto_changed(self, checked: bool) -> None:
        """V0.7.1 (3c): Auto checked → the override spin is disabled and
        0 (AUTO) flows to the request; unchecked → manual 4-25."""
        self.group_spin.setEnabled(not checked)
        self._override_lbl.setEnabled(not checked)

    def _on_chapter_toggled(self, checked: bool) -> None:
        # V10.1.1: the button is no longer gated by this checkbox.
        # The checkbox is now a STATE REFLECTION: if the user unchecks it,
        # we clear the selection; if they check it, the button is already
        # enabled and ready.  Clicking the button auto-checks this box.
        if not checked:
            self._selected_chapters = None
            self.chapter_count_lbl.setText("")
        self._refresh_feedback()

    def _open_chapter_selector(self) -> None:
        """Open the TOC chapter selector dialog.

        V10.1.1: auto-checks the 'select specific chapters' checkbox when
        clicked, so the UI state is consistent without requiring the user
        to check the box first.
        """

        from ui_qt.views.chapter_selector_dialog import ChapterSelectorDialog

        inp = self.state.input_path
        if not inp or not Path(inp).exists():
            QMessageBox.information(self, "No PDF", "Please select a PDF file first (Step 1).")
            self.select_chapters_cb.setChecked(False)
            return

        # V10.1.1: auto-check the checkbox — the user clicked the button,
        # which means they want to select chapters.  This keeps the checkbox
        # state in sync with the action without requiring a pre-check.
        if not self.select_chapters_cb.isChecked():
            self.select_chapters_cb.blockSignals(True)  # don't re-trigger _on_chapter_toggled
            self.select_chapters_cb.setChecked(True)
            self.select_chapters_cb.blockSignals(False)

        # V7.7.0: pass the likely output dir so the chapter selector can
        # show "✓ done" badges for chapters that already have summaries.
        try:
            stem = Path(inp).stem
            base_out = self.state.output_dir or str(Path(inp).parent)
            candidate_out = Path(base_out) / stem
        except Exception:
            candidate_out = None

        dlg = ChapterSelectorDialog(self, output_dir=candidate_out)
        dlg.set_input_file(Path(inp))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.select_chapters_cb.setChecked(False)
            self._selected_chapters = None
            self.chapter_count_lbl.setText("")
            self._refresh_feedback()
            return

        selected = dlg.get_selected_chapters()
        self._selected_chapters = selected
        if selected:
            self.chapter_count_lbl.setText(f"✓ {len(selected)} chapter(s) selected")
        else:
            self.chapter_count_lbl.setText("")
            self.select_chapters_cb.setChecked(False)
        self._refresh_feedback()

    # ── state ────────────────────────────────────────────────────────────

    def save_to_state(self) -> None:
        if self.all_pages_cb.isChecked():
            self.state.page_range_start = None
            self.state.page_range_end = None
        else:
            self.state.page_range_start = self.start_spin.value()
            self.state.page_range_end = self.end_spin.value()
        # V0.7.1 (3c): 0 = AUTO (the backend measures the block size);
        # a manual 4-25 overrides it.
        self.state.page_group_size = (
            0 if self.blocks_auto_cb.isChecked() else self.group_spin.value()
        )
        # Store chapter selection in the state's to_ui_data via a dynamic attr
        self.state.selected_chapters = self._selected_chapters
