"""Step 2: Page Range — Step2Range (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step2Range
(back-compat facade).
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

from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 2: Page Range
# ════════════════════════════════════════════════════════════════════════════

class Step2Range(WizardStep):
    """Page range + page group size + auto-detect scanned + chapter selection."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("Page range and segmentation")
        title.setObjectName("H2")
        lay.addWidget(title)

        # Page range
        range_box = QGroupBox("Page range")
        range_lay = QVBoxLayout(range_box)
        range_lay.setContentsMargins(10, 10, 10, 8)
        range_lay.setSpacing(6)

        self.all_pages_cb = QCheckBox("Process all pages")
        self.all_pages_cb.setChecked(True)
        self.all_pages_cb.stateChanged.connect(self._on_all_changed)
        range_lay.addWidget(self.all_pages_cb)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 99999)
        self.start_spin.setValue(1)
        self.start_spin.setEnabled(False)
        custom_row.addWidget(QLabel("From page:"))
        custom_row.addWidget(self.start_spin)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(1, 99999)
        self.end_spin.setValue(99999)
        self.end_spin.setEnabled(False)
        custom_row.addWidget(QLabel("To page:"))
        custom_row.addWidget(self.end_spin)
        custom_row.addStretch()
        range_lay.addLayout(custom_row)
        lay.addWidget(range_box)

        # Chapter selection (TOC)
        chapter_box = QGroupBox("Chapter selection (optional)")
        chapter_lay = QVBoxLayout(chapter_box)
        chapter_lay.setContentsMargins(10, 10, 10, 8)
        chapter_lay.setSpacing(6)

        self.select_chapters_cb = QCheckBox("Select specific chapters from table of contents")
        self.select_chapters_cb.toggled.connect(self._on_chapter_toggled)
        chapter_lay.addWidget(self.select_chapters_cb)

        chapter_row = QHBoxLayout()
        chapter_row.setSpacing(8)
        self.chapter_btn = QPushButton("🔍 Detect chapters from TOC")
        self.chapter_btn.setObjectName("Secondary")
        self.chapter_btn.setCursor(Qt.PointingHandCursor)
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
        lay.addWidget(chapter_box)

        # Segmentation
        seg_box = QGroupBox("Segmentation")
        seg_lay = QVBoxLayout(seg_box)
        seg_lay.setContentsMargins(10, 10, 10, 8)
        seg_lay.setSpacing(6)

        self.auto_detect_cb = QCheckBox("Auto-detect scanned pages (recommended)")
        self.auto_detect_cb.setChecked(self.state.auto_detect_scanned)
        seg_lay.addWidget(self.auto_detect_cb)

        group_row = QHBoxLayout()
        group_row.setSpacing(8)
        self.group_spin = QSpinBox()
        self.group_spin.setRange(1, 100)
        self.group_spin.setValue(self.state.page_group_size)
        group_row.addWidget(QLabel("Page group size:"))
        group_row.addWidget(self.group_spin)
        group_row.addStretch()
        seg_lay.addLayout(group_row)
        lay.addWidget(seg_box)
        lay.addStretch()

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

    def _on_chapter_toggled(self, checked: bool) -> None:
        # V10.1.1: the button is no longer gated by this checkbox.
        # The checkbox is now a STATE REFLECTION: if the user unchecks it,
        # we clear the selection; if they check it, the button is already
        # enabled and ready.  Clicking the button auto-checks this box.
        if not checked:
            self._selected_chapters = None
            self.chapter_count_lbl.setText("")

    def _open_chapter_selector(self) -> None:
        """Open the TOC chapter selector dialog.

        V10.1.1: auto-checks the 'select specific chapters' checkbox when
        clicked, so the UI state is consistent without requiring the user
        to check the box first.
        """
        from PySide6.QtWidgets import QDialog

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
            return

        selected = dlg.get_selected_chapters()
        self._selected_chapters = selected
        if selected:
            self.chapter_count_lbl.setText(f"✓ {len(selected)} chapter(s) selected")
        else:
            self.chapter_count_lbl.setText("")
            self.select_chapters_cb.setChecked(False)

    def save_to_state(self) -> None:
        if self.all_pages_cb.isChecked():
            self.state.page_range_start = None
            self.state.page_range_end = None
        else:
            self.state.page_range_start = self.start_spin.value()
            self.state.page_range_end = self.end_spin.value()
        self.state.page_group_size = self.group_spin.value()
        self.state.auto_detect_scanned = self.auto_detect_cb.isChecked()
        # Store chapter selection in the state's to_ui_data via a dynamic attr
        self.state.selected_chapters = self._selected_chapters
