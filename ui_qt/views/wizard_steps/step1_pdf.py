"""Step 1: PDF Selection + Reading Mode — Step1Pdf.

V0.7.0 (wizard rework ②, item 2c — D1-D3): the six document-type cards
collapse into THREE honest mode cards — Digital / Scanned / Auto
("Recommended", the default). All 10 steps keep their identity (D1);
the modes replace the 6-preset surface, not the pipeline:

- **Digital** (assets/icons/normal_book.png): today's pipeline with
  figure-text + table extraction ON — honest copy: charts on text pages
  are EXTRACTED, not re-OCR'd (audit §W2: both extractors are real but
  page-level-blind and opt-in today).
- **Scanned** (assets/icons/full_ocr.png): every page through the
  dedicated vision-OCR engine set (D2). Copy promises READING the pages,
  not describing imagery (audit §6.1 — no description pass exists).
- **Auto** (assets/icons/mixed.png, "Recommended", default): today's
  always-on page-level detection + this step's detector banner.

The content-type detector (V9.1.0) stays: its banner now applies
``source_type`` (the content-preset axis) while the mode cards own
``ocr_mode`` (the reading axis) — the two no longer clobber each other.

The V7.5.0 configuration-profiles box is retired (D4, item 2e); with 3
cards and no profiles box the step fits its viewport (B10 closed).
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
from ui_qt.theme import FONT, WEIGHT, theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# V18.20.3.12 (F821) pattern, carried with the class: the
# best-effort ``logger.debug`` sites must not NameError on
# swallowed-exception paths (house pattern per queue_view).
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# Step 1: PDF Selection + Reading Mode
# ════════════════════════════════════════════════════════════════════════════

# V0.7.0 (item 2c, D1-D3): the three mode cards. ``png`` is the artwork
# under assets/icons/; ``icon`` is the SVG fallback name (the TypeCard
# contract). Copy is transcription-truthful per the audit (§6.1/§W2).
_MODE_CARDS: dict[str, dict[str, str | bool]] = {
    "digital": {
        "title": "Digital",
        "icon": "book",
        "png": "normal_book",
        "subtitle": (
            "Text-based PDF. Charts and tables on text pages are extracted, not re-OCR'd."
        ),
        "tooltip": (
            "The fast path: the PDF's own text layer, plus figure-text "
            "and table extraction for charts on text pages. No page is "
            "re-OCR'd."
        ),
        "recommended": False,
    },
    "scanned": {
        "title": "Scanned",
        "icon": "scan",
        "png": "full_ocr",
        "subtitle": ("Every page is read by the vision-OCR engine. For scans and photos of text."),
        "tooltip": (
            "Every page goes through the dedicated vision-OCR engine set "
            "(your vision model, then the OCR model, then OlmOCR/Qwen VL "
            "— never Tesseract). Slowest, most thorough."
        ),
        "recommended": False,
    },
    "auto": {
        "title": "Auto",
        "icon": "layers",
        "png": "mixed",
        "subtitle": "I detect which pages need OCR and read only those.",
        "tooltip": (
            "Recommended. I scan every page and OCR only the ones that "
            "need it, with the best available engine."
        ),
        "recommended": True,
    },
}


class Step1Pdf(WizardStep):
    """PDF file selection + the 3 reading-mode cards (V0.7.0)."""

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

        # Reading-mode cards (V0.7.0 item 2c: 6 type cards → 3 modes)
        type_label = QLabel("How should I read this PDF?")
        type_label.setObjectName("H3")
        lay.addWidget(type_label)

        # The detector banner sits between the label and the cards
        # (V9.1.0 banner, kept for Auto; pre-created hidden so there is
        # no insert-index math).
        self._detection_label = QLabel("")
        self._detection_label.setObjectName("Caption")
        self._detection_label.setWordWrap(True)
        self._detection_label.hide()
        lay.addWidget(self._detection_label)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._type_cards: dict[str, TypeCard] = {}
        for i, (key, spec) in enumerate(_MODE_CARDS.items()):
            cell = QVBoxLayout()
            cell.setSpacing(3)
            # Every cell carries the badge row (fixed height) so the
            # three cards stay pixel-aligned; only the recommended card
            # shows the pill.
            badge = QLabel("RECOMMENDED" if spec["recommended"] else "")
            badge.setFixedHeight(16)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if spec["recommended"]:
                p = theme_manager.palette
                badge.setStyleSheet(
                    f"color: {p.accent}; background: {p.accent_soft};"
                    f" border-radius: 7px; padding: 1px 10px;"
                    f" font-size: {FONT.micro}px; font-weight: {WEIGHT.semibold};"
                    f" letter-spacing: 0.6px;"
                )
            cell.addWidget(badge)
            tc = TypeCard(
                value=key,
                icon_name=str(spec["icon"]),
                title=str(spec["title"]),
                subtitle=str(spec["subtitle"]),
                png_name=str(spec["png"]),
            )
            tc.setToolTip(str(spec["tooltip"]))
            tc.selected.connect(self._on_mode_selected)
            self._type_cards[key] = tc
            cell.addWidget(tc)
            grid.addLayout(cell, 0, i)
        lay.addLayout(grid)

        lay.addStretch()

        # Restore the persisted mode (default auto → the Auto card).
        self._type_cards.get(self.state.ocr_mode, self._type_cards["auto"]).set_selected(True)
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
        sample from the PDF, then suggest the optimal content preset.

        Runs in a background thread so the UI doesn't freeze while the PDF
        is being sampled.  Shows a suggestion banner above the mode cards.
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
        self._detection_label.show()

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
        """Apply the detected content type to the wizard state.

        V0.7.0 (item 2c): the 6 type cards are gone — the detector owns
        ``source_type`` (the content-preset axis: prompts, segmentation
        defaults), the mode cards own ``ocr_mode`` (the reading axis).
        The two no longer clobber each other.
        """
        self.state.source_type = result.content_type
        self._detection_label.setText(
            f"✅ Applied <b>{result.label()}</b> content preset — "
            f"prompts and defaults optimized for this content type."
        )
        p = theme_manager.palette
        self._detection_label.setStyleSheet(
            f"color: {p.success}; background: transparent; font-size: 11px; padding: 4px;"
        )

    def _on_mode_selected(self, value: str) -> None:
        """Apply a mode card (V0.7.0 item 2c, D1-D3).

        The card sets the OCR mode + its honest defaults. ``source_type``
        is NOT touched — content detection (the banner) and the settings
        own it; the reading mode and the content type are orthogonal axes.
        """
        self.state.ocr_mode = value
        # The legacy alias never fights an explicit card choice.
        self.state.force_ocr_all_pages = False
        if value == "digital":
            # The Digital card's promise: figure-text + table extraction ON
            # (audit §W2 — both real, page-level-blind, opt-in today).
            self.state.extract_figure_text = True
            self.state.extract_tables = True
        elif value == "scanned":
            # Figure/table extraction is a digital-page feature — every
            # page is already fully read by the vision engine here.
            self.state.extract_figure_text = False
            self.state.extract_tables = False
        # auto: leave the Step-3 extract toggles as-is (today's behavior).
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
