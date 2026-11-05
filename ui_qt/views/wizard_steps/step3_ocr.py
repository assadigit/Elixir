"""Step 3: OCR Settings — Step3Ocr (V18.20.4.6, P5 / O-b1 split).

V0.7.1 (wizard rework ③, item 3d — audit §W5 / B3): the five flat
checkboxes collapse into ONE primary choice + a folded advanced
disclosure:

    ◉ Automatic — recommended   (the audit's honest auto copy)
    ○ Manual control            (opens the disclosure)

The disclosure is MODE-AWARE — Step 1 owns the reading-mode axis
(``ocr_mode``: digital / scanned / auto, landed V0.7.0); this step
never fights it:

- auto    → vision toggle + figure/table extraction + PaddleOCR
            fallback + timeout; the full per-page engine cascade.
- digital → no page-OCR controls (the text layer is read); figure/
            table extraction + timeout only.
- scanned → the engine set is FIXED by D2 (vision-OCR only; Tesseract,
            Paddle and the local-VLM fallback excluded) — the disclosure
            shows the set as information, not toggles that lie.

Choosing "Automatic" applies the plan's honest defaults on save
(vision on, Paddle off — the figure/table toggles stay as Step 1's
cards set them); "Manual control" saves exactly what the visible
controls say. Hidden controls are never saved over (a control the
mode makes meaningless is a no-op, not a lie).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.theme import theme_manager
from ui_qt.views.wizard_steps.shared import WizardStep

# ═══════════════════════════════════════════════════════════════════════════
# Step 3: OCR Settings
# ═══════════════════════════════════════════════════════════════════════════

# The per-mode honest copy (item 3d). The auto caption is the audit's
# §W5 honest-auto wording, kept identical to Step 1's Auto card so the
# two surfaces never disagree.
_MODE_CAPTIONS = {
    "auto": "I scan every page and OCR only the ones that need it, with the best available engine.",
    "digital": "The PDF's own text layer is read — no page is re-OCR'd. Charts and tables are extracted.",
    "scanned": "Every page is read by the vision-OCR engine set — no other engine is consulted.",
}

# The per-mode engine-set line shown inside the disclosure. Auto's is
# the real per-page cascade (audit §W5: vision probe → OlmOCR → Qwen →
# Paddle → VLM → Tesseract); scanned's is the D2 set; digital's is the
# honest "nothing is re-OCR'd" statement.
_ENGINE_SETS = {
    "auto": (
        "Engine set: your vision model → the OCR model → OlmOCR → Qwen VL "
        "→ Paddle (if enabled below) → local VLM → Tesseract. The first "
        "engine that succeeds wins."
    ),
    "digital": (
        "No page OCR — the PDF's own text layer is read. Charts and tables "
        "on text pages are extracted (figure-text vision pass + camelot/"
        "tabula), not re-OCR'd."
    ),
    "scanned": (
        "Engine set (locked): your vision model → the OCR model → OlmOCR → "
        "Qwen VL. Tesseract, PaddleOCR and the local-VLM fallback are "
        "excluded in this mode."
    ),
}


class Step3Ocr(WizardStep):
    """OCR engine settings — one primary choice + a mode-aware disclosure."""

    # V0.7.0 (item 2b): the numbered StepHeader grammar — the base
    # class inserts the badge+title+caption above the built content.
    STEP_HEADER = (3, "OCR settings", "How image text is read — the defaults suit most books.")

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        box = QGroupBox("Engine options")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(10, 10, 10, 8)
        box_lay.setSpacing(8)

        # ── The primary choice (item 3d) ───────────────────────────────
        self.auto_rb = QRadioButton("Automatic — recommended")
        self.auto_rb.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.auto_rb.setChecked(True)
        self.auto_rb.toggled.connect(self._on_mode_radio)
        box_lay.addWidget(self.auto_rb)

        self.auto_caption = QLabel(_MODE_CAPTIONS["auto"])
        self.auto_caption.setObjectName("Caption")
        self.auto_caption.setWordWrap(True)
        self.auto_caption.setStyleSheet("margin-left: 24px;")
        box_lay.addWidget(self.auto_caption)

        self.manual_rb = QRadioButton("Manual control")
        self.manual_rb.toggled.connect(self._on_mode_radio)
        box_lay.addWidget(self.manual_rb)

        # ── The advanced disclosure (visible under Manual control) ────
        self.disclosure = QWidget()
        disc_lay = QVBoxLayout(self.disclosure)
        disc_lay.setContentsMargins(24, 4, 4, 4)
        disc_lay.setSpacing(6)

        self.vision_cb = QCheckBox("Vision-model OCR pass (reads pages that need OCR)")
        self.vision_cb.setChecked(self.state.use_llm_ocr)
        self.vision_cb.setToolTip(
            "Uses the vision-capable model to read pages. In Scanned mode this "
            "is the whole engine set and cannot be turned off."
        )
        disc_lay.addWidget(self.vision_cb)

        self.figures_cb = QCheckBox("Figure & table text extraction (vision OCR)")
        self.figures_cb.setChecked(self.state.extract_figure_text)
        self.figures_cb.setToolTip(
            "Charts and tables on text pages are read out as text — the page "
            "itself is never re-OCR'd."
        )
        disc_lay.addWidget(self.figures_cb)

        self.tables_cb = QCheckBox("Tables (camelot / tabula)")
        self.tables_cb.setChecked(self.state.extract_tables)
        self.tables_cb.setToolTip("Extracts tables as structured text from text pages.")
        disc_lay.addWidget(self.tables_cb)

        self.paddleocr_cb = QCheckBox("PaddleOCR fallback (before Tesseract)")
        self.paddleocr_cb.setChecked(self.state.use_paddleocr)
        self.paddleocr_cb.setToolTip(
            "Adds PaddleOCR to the engine cascade before Tesseract. Needs the "
            "paddleocr package; runs CPU-only. Never used in Scanned mode "
            "(excluded by the vision engine set)."
        )
        disc_lay.addWidget(self.paddleocr_cb)

        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(8)
        self.timeout_combo = QComboBox()
        # V0.7.1 (wizard rework ③, B3): the 30/60/90 items were fiction —
        # the values never reached the backend (dropped by to_ui_data) and
        # the backend clamps to ≥120s anyway (ocr/service.py). Now the
        # control reaches the request through _REQUEST_FIELD_MAP and the
        # items are the honest 120/180/300 band.
        self.timeout_combo.addItems(["120", "180", "300"])
        _saved_timeout = str(self.state.ocr_timeout)
        if self.timeout_combo.findText(_saved_timeout) < 0:
            _saved_timeout = "120"  # a legacy sub-floor value → the honest floor
        self.timeout_combo.setCurrentText(_saved_timeout)
        self.timeout_combo.setToolTip(
            "Per-request timeout for the OCR engine calls. The backend clamps "
            "to a 120-second minimum whatever arrives."
        )
        timeout_row.addWidget(QLabel("OCR timeout (seconds):"))
        timeout_row.addWidget(self.timeout_combo)
        timeout_row.addStretch()
        disc_lay.addLayout(timeout_row)

        # The mode-aware engine-set line (information, never a fake toggle).
        self.engineset_lbl = QLabel(_ENGINE_SETS["auto"])
        self.engineset_lbl.setObjectName("Caption")
        self.engineset_lbl.setWordWrap(True)
        p = theme_manager.palette
        self.engineset_lbl.setStyleSheet(f"color: {p.text_muted};")
        disc_lay.addWidget(self.engineset_lbl)

        self.disclosure.setVisible(False)
        box_lay.addWidget(self.disclosure)
        lay.addWidget(box)
        lay.addStretch()

        self._refresh_mode_dependents()

    # ── mode-awareness (Step 1 owns ocr_mode; this step follows it) ─────

    def _effective_mode(self) -> str:
        mode = str(getattr(self.state, "ocr_mode", "auto") or "auto").strip().lower()
        return mode if mode in _MODE_CAPTIONS else "auto"

    def _refresh_mode_dependents(self) -> None:
        """Show only the controls the current reading mode makes real.

        digital  → no page-OCR controls (vision, paddle) — the text layer
                   is read; figure/table extraction stays.
        scanned  → engine set locked by D2: no vision/paddle toggles and
                   no extraction toggles (every page is already fully
                   read) — the timeout and the set line stay.
        auto     → everything.
        """
        mode = self._effective_mode()
        self.auto_caption.setText(_MODE_CAPTIONS[mode])
        self.engineset_lbl.setText(_ENGINE_SETS[mode])
        self.vision_cb.setVisible(mode == "auto")
        self.paddleocr_cb.setVisible(mode == "auto")
        self.figures_cb.setVisible(mode in ("auto", "digital"))
        self.tables_cb.setVisible(mode in ("auto", "digital"))
        # Timeout + engine-set line stay visible in every mode (the
        # figure-text pass and the vision calls are still engine calls).

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Step 1's mode may have changed after this step was built —
        refresh the mode-dependent surfaces on every show."""
        super().showEvent(event)
        self._refresh_mode_dependents()

    def _on_mode_radio(self, checked: bool) -> None:
        """Automatic collapses the disclosure; Manual opens it."""
        self.disclosure.setVisible(self.manual_rb.isChecked())

    # ── state ────────────────────────────────────────────────────────────

    def save_to_state(self) -> None:
        mode = self._effective_mode()
        if self.auto_rb.isChecked():
            # Automatic (plan 3d): the honest defaults — vision on, Paddle
            # off. The figure/table toggles are NOT clobbered here: Step
            # 1's mode cards own them (digital→on, scanned→off, auto→
            # today's). A control this mode makes meaningless is left
            # alone, never written over with a lie.
            self.state.use_llm_ocr = True
            self.state.use_paddleocr = False
        else:
            if mode == "auto":
                self.state.use_llm_ocr = self.vision_cb.isChecked()
                self.state.use_paddleocr = self.paddleocr_cb.isChecked()
            # digital: neither page-OCR toggle exists — leave both as-is
            # (no-ops in that mode). scanned: D2 forces both regardless.
            if mode in ("auto", "digital"):
                self.state.extract_figure_text = self.figures_cb.isChecked()
                self.state.extract_tables = self.tables_cb.isChecked()
            # scanned: Step 1's card already set both False — leave as-is.
        # The timeout applies in every mode and under both radio choices —
        # it flows from the combo (loaded from the user's last choice).
        self.state.ocr_timeout = int(self.timeout_combo.currentText())
