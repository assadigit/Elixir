"""Step 1: PDF Selection + Document Type — Step1Pdf (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step1Pdf
(back-compat facade).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui_qt.components.simple_worker import SimpleWorker
from ui_qt.components.type_card import TypeCard
from ui_qt.settings.presets import PRESETS
from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# V18.20.3.12 (F821) pattern, carried with the class: the
# best-effort ``logger.debug`` sites must not NameError on
# swallowed-exception paths (house pattern per queue_view).
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Step 1: PDF Selection + Document Type
# ════════════════════════════════════════════════════════════════════════════


class Step1Pdf(WizardStep):
    """PDF file selection + document type preset cards."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    STEP_HEADER = (
        1,
        "Select your PDF",
        "Pick the file, then choose how Elixir should read it — Auto suits most books.",
    )

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # PDF file picker
        pdf_box = QGroupBox("PDF file")
        pdf_lay = QHBoxLayout(pdf_box)
        pdf_lay.setContentsMargins(10, 10, 10, 8)
        self.pdf_edit = QLineEdit()
        self.pdf_edit.setPlaceholderText("Click Browse to select a PDF file...")
        self.pdf_edit.setReadOnly(True)
        pdf_lay.addWidget(self.pdf_edit, 1)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse)
        pdf_lay.addWidget(self.browse_btn)
        lay.addWidget(pdf_box)

        # Document type cards
        type_label = QLabel("Document type")
        type_label.setObjectName("H3")
        lay.addWidget(type_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._type_cards: dict[str, TypeCard] = {}
        for i, (key, preset) in enumerate(PRESETS.items()):
            tc = TypeCard(
                value=key,
                icon_name=preset["icon"],
                title=preset["label"],
                subtitle=preset["subtitle"],
                png_name=key,
            )
            tc.selected.connect(self._on_type_selected)
            self._type_cards[key] = tc
            grid.addWidget(tc, i // 3, i % 3)
        lay.addLayout(grid)

        lay.addStretch()

        # Select current source_type
        if self.state.source_type in self._type_cards:
            self._type_cards[self.state.source_type].set_selected(True)
        if self.state.input_path:
            self.pdf_edit.setText(self.state.input_path)

    def _browse(self) -> None:
        last_dir = self.controller.get_setting("output.last_input_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF file", last_dir, "PDF files (*.pdf)"
        )
        if path:
            self.pdf_edit.setText(path)
            self.controller.update_setting("output.last_input_dir", str(Path(path).parent))
            # V9.1.0: auto-detect content type from a quick text sample
            self._auto_detect_content_type(path)

    def _auto_detect_content_type(self, pdf_path: str) -> None:
        """V9.1.0: Run the deterministic content detector on a quick text
        sample from the PDF, then suggest the optimal preset to the user.

        Runs in a background thread so the UI doesn't freeze while the PDF
        is being sampled.  Shows a suggestion banner above the type cards.
        """

        def _detect():
            try:
                # Quick text extraction — just the first few pages
                # Use pdfplumber if available for a quick text sample
                sample_text = ""
                try:
                    import pdfplumber

                    with pdfplumber.open(pdf_path) as pdf:
                        for page in pdf.pages[:10]:  # first 10 pages
                            t = page.extract_text() or ""
                            sample_text += t + "\n"
                            if len(sample_text) > 20000:
                                break
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)

                if not sample_text or len(sample_text) < 200:
                    return  # can't detect — let the converter do it later

                from core.llm.content_detector import detect_content_type

                result = detect_content_type(sample_text)
                self._detection_result = result
                # Marshal to UI thread
                from PySide6.QtCore import QMetaObject
                from PySide6.QtCore import Qt as _Qt

                QMetaObject.invokeMethod(
                    self,
                    "_show_detection_suggestion",
                    _Qt.ConnectionType.QueuedConnection,
                )
            except Exception as _e:
                logger.debug(
                    "ignored %s: %s", type(_e).__name__, _e
                )  # detection is best-effort; don't block the user

        SimpleWorker(_detect).start()

    from PySide6.QtCore import Slot  # noqa: E402

    @Slot()
    def _show_detection_suggestion(self) -> None:
        """Show the auto-detection suggestion banner (UI thread)."""
        result = getattr(self, "_detection_result", None)
        if not result:
            return

        p = theme_manager.palette

        # Create or update the suggestion label
        if not hasattr(self, "_detection_label"):
            self._detection_label = QLabel("")
            self._detection_label.setObjectName("Caption")
            self._detection_label.setWordWrap(True)
            # Insert it above the type cards grid (find the grid layout's parent)
            # For simplicity, add it to the main layout before the grid
            self.layout().insertWidget(3, self._detection_label)

        if result.recommended and result.content_type != "normal_book":
            self._detection_label.setText(
                f"🔍 Auto-detected: <b>{result.label()}</b> "
                f"({result.confidence:.0%} confidence) — "
                f"<a href='apply'>click to apply optimal settings</a>"
            )
            self._detection_label.setStyleSheet(
                f"color: {p.accent}; background: {p.accent_soft}; "
                f"padding: 6px 10px; border-radius: 6px; font-size: 11px;"
            )
            self._detection_label.setTextFormat(Qt.RichText)
            self._detection_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self._detection_label.linkActivated.connect(lambda: self._apply_detection(result))
        else:
            self._detection_label.setText(
                f"🔍 Auto-detected: {result.label()} "
                f"({result.confidence:.0%} confidence) — "
                f"keeping default (normal_book)"
            )
            self._detection_label.setStyleSheet(
                f"color: {p.text_muted}; background: transparent; font-size: 11px; padding: 4px;"
            )

    def _apply_detection(self, result) -> None:
        """Apply the detected content type to the wizard state + type cards."""
        if result.content_type in self._type_cards:
            # Deselect all, then select the detected one
            for card in self._type_cards.values():
                card.set_selected(False)
            self._type_cards[result.content_type].set_selected(True)
            self._on_type_selected(result.content_type)
            self._detection_label.setText(
                f"✅ Applied <b>{result.label()}</b> preset — "
                f"settings optimized for this content type."
            )
            p = theme_manager.palette
            self._detection_label.setStyleSheet(
                f"color: {p.success}; background: transparent; font-size: 11px; padding: 4px;"
            )

    def _on_type_selected(self, value: str) -> None:
        self.state.source_type = value
        # Apply preset settings
        preset = PRESETS.get(value, {})
        for sk, sv in preset.get("settings", {}).items():
            if sk == "ocr.timeout":
                self.state.ocr_timeout = sv
            elif sk == "is_academic":
                pass  # handled by source_type
            elif sk == "ocr.force_ocr_all_pages":
                self.state.force_ocr_all_pages = sv
            elif sk == "advanced.extract_tables":
                self.state.extract_tables = sv
            elif sk == "advanced.extract_figure_text":
                self.state.extract_figure_text = sv
            elif sk == "segmentation.strategy":
                self.state.segment_strategy = sv
            elif sk == "segmentation.token_limit":
                self.state.token_limit = sv
        # Update card selection (exclusive)
        for k, tc in self._type_cards.items():
            if k != value:
                tc.set_selected(False)

    def validate(self) -> tuple[bool, str]:
        if not self.pdf_edit.text().strip():
            return False, "Please select a PDF file."
        if not Path(self.pdf_edit.text().strip()).exists():
            return False, "The selected PDF file does not exist."
        return True, ""

    def save_to_state(self) -> None:
        self.state.input_path = self.pdf_edit.text().strip()
