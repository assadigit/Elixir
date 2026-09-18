"""Step 3: OCR Settings — Step3Ocr (V18.20.4.6, P5 / O-b1 split).

Moved VERBATIM from ui_qt/views/wizard_view.py (one module per
wizard step): the class body below is byte-identical to the
pre-split definition — only this module's top-of-file imports
differ. ``ui_qt.views.wizard_view`` re-exports Step3Ocr
(back-compat facade).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from ui_qt.views.wizard_steps.shared import WizardStep

# ════════════════════════════════════════════════════════════════════════════
# Step 3: OCR Settings
# ════════════════════════════════════════════════════════════════════════════

class Step3Ocr(WizardStep):
    """OCR engine settings."""

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        title = QLabel("OCR settings")
        title.setObjectName("H2")
        lay.addWidget(title)

        box = QGroupBox("Engine options")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(10, 10, 10, 8)
        box_lay.setSpacing(6)

        self.llm_ocr_cb = QCheckBox("Use LLM OCR for scanned pages (vision model)")
        self.llm_ocr_cb.setChecked(self.state.use_llm_ocr)
        box_lay.addWidget(self.llm_ocr_cb)

        self.force_ocr_cb = QCheckBox("Force OCR on every page (slower, for unreliable text)")
        self.force_ocr_cb.setChecked(self.state.force_ocr_all_pages)
        box_lay.addWidget(self.force_ocr_cb)

        self.paddleocr_cb = QCheckBox("Enable PaddleOCR fallback (before Tesseract)")
        self.paddleocr_cb.setChecked(self.state.use_paddleocr)
        box_lay.addWidget(self.paddleocr_cb)

        self.figures_cb = QCheckBox("Extract text from figures/charts (vision OCR)")
        self.figures_cb.setChecked(self.state.extract_figure_text)
        box_lay.addWidget(self.figures_cb)

        self.tables_cb = QCheckBox("Extract tables (Camelot)")
        self.tables_cb.setChecked(self.state.extract_tables)
        box_lay.addWidget(self.tables_cb)

        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(8)
        self.timeout_combo = QComboBox()
        self.timeout_combo.addItems(["30", "60", "90", "120", "180"])
        self.timeout_combo.setCurrentText(str(self.state.ocr_timeout))
        timeout_row.addWidget(QLabel("OCR timeout (seconds):"))
        timeout_row.addWidget(self.timeout_combo)
        timeout_row.addStretch()
        box_lay.addLayout(timeout_row)
        lay.addWidget(box)
        lay.addStretch()

    def save_to_state(self) -> None:
        self.state.use_llm_ocr = self.llm_ocr_cb.isChecked()
        self.state.force_ocr_all_pages = self.force_ocr_cb.isChecked()
        self.state.use_paddleocr = self.paddleocr_cb.isChecked()
        self.state.extract_figure_text = self.figures_cb.isChecked()
        self.state.extract_tables = self.tables_cb.isChecked()
        self.state.ocr_timeout = int(self.timeout_combo.currentText())
